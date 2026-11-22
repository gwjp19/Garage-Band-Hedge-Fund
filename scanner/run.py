"""Live scanner: finds Kalshi vs Polymarket US price gaps on college games and paper-trades them.

    python -m scanner.run                 # loop until no games are left (or MAX_RUN_MIN)
    python -m scanner.run --minutes 10    # stop after 10 minutes
    python -m scanner.run --once          # one pass, for testing
"""
import argparse, os, sys, time, traceback, uuid, threading
from . import config, store, settle, sync
from .pricing import price_pair, usable
from .venues import kalshi, polymarket_us
from .venues.base import VenueGame, Side
from .match import match

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def find_games():
    kg, pg = [], []
    for sport, (series, prefix) in config.SPORTS.items():
        kg += kalshi.list_games(sport, series)
        pg += polymarket_us.list_games(sport, prefix)
    pairs = match(kg, pg)
    log(f"kalshi games {len(kg)}, polymarket US games {len(pg)}, matched {len(pairs)}")
    return pairs

def record_matches(pairs, seen):
    rows = []
    for kg, pg, k2p, sc in pairs:
        if kg.game_id in seen: continue
        seen.add(kg.game_id)
        rows.append({"matched_at": store.now_iso(), "sport": kg.sport, "start_utc": store.now_iso(start_of(kg, pg)), "kalshi_start_est_utc": store.now_iso(kg.start_ts), "poly_start_utc": store.now_iso(pg.start_ts),
                     "kalshi_event": kg.game_id, "poly_slug": pg.game_id,
                     "kalshi_team0": kg.sides[0].name, "kalshi_team1": kg.sides[1].name,
                     "poly_team_for_kalshi0": pg.sides[k2p[0]].name, "poly_team_for_kalshi1": pg.sides[k2p[1]].name,
                     "k_to_p": f"{k2p[0]}{k2p[1]}", "match_score": round(sc, 1)})
    store.append("games.csv", store.GAMES, rows)

def start_of(kg, pg):
    """Venues sometimes disagree on start time; use the earlier one."""
    return min(kg.start_ts, pg.start_ts)

def watching(kg, pg, now):
    """From WATCH_FROM_MIN before the earlier listed start to WATCH_UNTIL_MIN after the later one."""
    return (now - min(kg.start_ts, pg.start_ts)) / 60 >= config.WATCH_FROM_MIN and \
           (now - max(kg.start_ts, pg.start_ts)) / 60 <= config.WATCH_UNTIL_MIN

class Scanner:
    def __init__(self):
        self.open_gaps = {}      # (kalshi_event, combo) -> gap episode dict
        self.last_snap = {}      # kalshi_event -> ts
        self.snaps = []
        self.recheck_rows = []
        self.recheck_lock = threading.Lock()

    def scan_game(self, kg, pg, k2p):
        pq = polymarket_us.quote(pg); kq = kalshi.quote(kg)
        now = time.time(); mins = (now - start_of(kg, pg)) / 60
        phase = "pregame" if mins < 0 else "in-game"
        gap_sec = abs(kq.ts - pq.ts)
        p_ask = [pq.ask[k2p[i]] for i in (0, 1)]; p_qty = [pq.qty[k2p[i]] for i in (0, 1)]   # aligned to Kalshi sides
        best = None
        if kq.ok and pq.ok and gap_sec <= config.MAX_QUOTE_GAP_SEC:
            for i in (0, 1):                      # combo i: team i on Kalshi, other team on Polymarket US
                j = 1 - i
                if not (usable(kq.ask[i]) and usable(p_ask[j])): continue
                pr = price_pair(kq.ask[i], kq.qty[i], p_ask[j], p_qty[j])
                if best is None or pr["profit_per_pair"] > best[1]["profit_per_pair"]: best = (i, pr)
                self.update_gap(kg, pg, k2p, i, pr, kq, pq, p_ask, p_qty, phase, mins, gap_sec)
        # snapshot once a minute per game
        if now - self.last_snap.get(kg.game_id, 0) >= config.SNAPSHOT_EVERY_SEC:
            self.last_snap[kg.game_id] = now
            self.snaps.append({"ts_utc": store.now_iso(now), "sport": kg.sport, "kalshi_event": kg.game_id,
                "poly_slug": pg.game_id, "min_from_start": round(mins, 1), "team0": kg.sides[0].name, "team1": kg.sides[1].name,
                "k_ask0": kq.ask[0], "k_qty0": kq.qty[0], "k_ask1": kq.ask[1], "k_qty1": kq.qty[1],
                "p_ask0": p_ask[0], "p_qty0": p_qty[0], "p_ask1": p_ask[1], "p_qty1": p_qty[1],
                "best_profit_per_pair": best[1]["profit_per_pair"] if best else "", "best_combo": best[0] if best else ""})

    def update_gap(self, kg, pg, k2p, i, pr, kq, pq, p_ask, p_qty, phase, mins, gap_sec):
        key = (kg.game_id, i); is_gap = pr["profit_per_pair"] > config.MIN_EDGE and pr["pairs"] >= 1
        g = self.open_gaps.get(key)
        if is_gap:
            if g is None:
                g = self.open_gaps[key] = {"game_key": kg.game_id, "sport": kg.sport, "combo": i,
                    "opened_ts": time.time(), "phase_at_open": phase, "min_from_start_at_open": round(mins, 1),
                    "best_profit_per_pair": pr["profit_per_pair"], "best_pairs": pr["pairs"], "polls": 0, "traded": False}
            g["polls"] += 1
            if pr["profit_per_pair"] > g["best_profit_per_pair"]:
                g["best_profit_per_pair"] = pr["profit_per_pair"]; g["best_pairs"] = pr["pairs"]
            if not (g["traded"] and config.ONE_TRADE_PER_GAP):
                self.paper_trade(kg, pg, k2p, i, pr, kq, pq, p_ask, p_qty, phase, mins, gap_sec); g["traded"] = True
        elif g is not None:
            self.close_gap(key)

    def close_gap(self, key):
        g = self.open_gaps.pop(key); now = time.time()
        store.append("gaps.csv", store.GAPS, [{**g, "opened_utc": store.now_iso(g["opened_ts"]), "closed_utc": store.now_iso(now),
                                               "seconds_open": round(now - g["opened_ts"])}])

    def paper_trade(self, kg, pg, k2p, i, pr, kq, pq, p_ask, p_qty, phase, mins, gap_sec):
        j = 1 - i
        row = {"trade_id": uuid.uuid4().hex[:10], "opened_utc": store.now_iso(), "sport": kg.sport,
               "kalshi_event": kg.game_id, "poly_slug": pg.game_id, "phase": phase, "min_from_start": round(mins, 1),
               "team_on_kalshi": kg.sides[i].name, "kalshi_route": kq.route[i], "kalshi_price": kq.ask[i],
               "kalshi_qty_avail": kq.qty[i], "team_on_poly": pg.sides[k2p[j]].name, "poly_route": pq.route[k2p[j]],
               "poly_price": p_ask[j], "poly_qty_avail": p_qty[j], "quote_gap_sec": round(gap_sec, 2),
               "kalshi_side": i, "poly_side": k2p[j], "status": "open", **pr}
        store.append("trades.csv", store.TRADES, [row])
        log(f"PAPER TRADE {kg.game_id}: {pr['pairs']} pairs, {kg.sides[i].name} on Kalshi @ {kq.ask[i]}, "
            f"{pg.sides[k2p[j]].name} on Polymarket US @ {p_ask[j]}, locks ${pr['locked_profit']:.2f}")

    def flush(self):
        store.append_snapshots(self.snaps); self.snaps = []

    def close_all(self):
        for key in list(self.open_gaps): self.close_gap(key)

    def recheck(self, kg, pg, k2p, i, trade_id, trade_ts):
        """Runs in its own thread after a paper trade. Re-reads both books at each delay in
        config.RECHECK_SECONDS and records whether the same combo is still profitable."""
        j = 1 - i
        for delay in config.RECHECK_SECONDS:
            time.sleep(max(0, trade_ts + delay - time.time()))      # wait until `delay` seconds after the trade
            try:
                pq = polymarket_us.quote(pg); kq = kalshi.quote(kg)
            except Exception as e:
                log("recheck error", kg.game_id, repr(e)[:150]); continue
            p_ask = [pq.ask[k2p[s]] for s in (0, 1)]; p_qty = [pq.qty[k2p[s]] for s in (0, 1)]   # aligned to Kalshi sides
            row = {"trade_id": trade_id, "delay_sec": delay, "actual_sec": round(time.time() - trade_ts, 2),
                   "kalshi_price": kq.ask[i], "poly_price": p_ask[j]}
            if kq.ok and pq.ok and usable(kq.ask[i]) and usable(p_ask[j]):
                pr = price_pair(kq.ask[i], kq.qty[i], p_ask[j], p_qty[j])
                row.update(still_profitable=pr["profit_per_pair"] > config.MIN_EDGE and pr["pairs"] >= 1,
                           profit_per_pair=pr["profit_per_pair"], pairs=pr["pairs"])
            else:
                row.update(still_profitable=False, profit_per_pair="", pairs=0)   # book empty, closed, or price out of range
            with self.recheck_lock:                  # several rechecks can finish at the same moment
                self.recheck_rows.append(row)

def git_push():
    sync.save(log)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--once", action="store_true"); ap.add_argument("--minutes", type=float)
    a = ap.parse_args()
    limit = (a.minutes if a.minutes is not None else config.MAX_RUN_MIN) * 60
    t0 = time.time(); sc = Scanner(); seen = {r["kalshi_event"] for r in store.read("games.csv")}
    pairs, last_match, last_commit, last_settle = [], 0, time.time(), 0
    while True:
        now = time.time()
        try:
            if now - last_match >= config.REMATCH_EVERY_MIN * 60:
                pairs = find_games(); record_matches(pairs, seen); last_match = now
            live = [(kg, pg, k2p) for kg, pg, k2p, _ in pairs if watching(kg, pg, now)]
            soon = [p for p in pairs if 0 < (start_of(p[0], p[1]) - now) / 60 <= 90]
            for kg, pg, k2p in live:
                try: sc.scan_game(kg, pg, k2p)
                except Exception as e: log("scan error", kg.game_id, repr(e)[:200])
            sc.flush()
            if now - last_settle >= 600: settle.run(); last_settle = now
        except Exception:
            traceback.print_exc()
        if now - last_commit >= config.COMMIT_EVERY_MIN * 60: git_push(); last_commit = now
        done = a.once or time.time() - t0 >= limit or (not live and not soon and last_match)
        if done: break
        log(f"watching {len(live)} games, {len(sc.open_gaps)} gaps open")
        time.sleep(max(0, config.POLL_SECONDS - (time.time() - now)))
    sc.close_all(); sc.flush(); settle.run(); git_push()
    log("stopped")

if __name__ == "__main__":
    main()
