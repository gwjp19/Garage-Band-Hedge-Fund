"""Settles open paper trades once both venues have resolved the game.

    python -m scanner.settle
"""
import time
from . import store
from .venues import kalshi, polymarket_us
from .venues.base import VenueGame, Side

def _kalshi_game(event):
    d = kalshi.S.get(f"{kalshi.API}/events/{event}")
    return VenueGame("kalshi", event, "", [Side(m["ticker"], m["yes_sub_title"]) for m in d["markets"]], 0)

def run():
    rows = store.read("trades.csv")
    if not any(r["status"] == "open" for r in rows): return
    cache, changed = {}, False
    for r in rows:
        if r["status"] != "open": continue
        key = (r["kalshi_event"], r["poly_slug"])
        if key not in cache:
            try:
                kg = _kalshi_game(r["kalshi_event"])
                kres = kalshi.result(kg)
                pres = polymarket_us.result(VenueGame("polymarket_us", r["poly_slug"], "", [], 0))
                cache[key] = (kg, kres, pres)
            except Exception as e:
                print("settle error", key, repr(e)[:200]); cache[key] = None
        if cache[key] is None: continue
        kg, kres, pres = cache[key]
        if kres is None or pres is None: continue
        if kres == "void" or pres == "void":
            r.update(status="void", kalshi_winner=kres, poly_winner=pres, settled_utc=store.now_iso()); changed = True; continue
        winner_name = kg.sides[kres].name
        p_idx, p_name = pres
        n = int(r["pairs"])
        k_won = winner_name == r["team_on_kalshi"]
        p_won = int(r["poly_side"]) == p_idx
        payout = n * (int(k_won) + int(p_won))
        status = "settled" if payout == n else "MISMATCH"   # both legs won or both lost = venues disagreed
        r.update(status=status, kalshi_winner=winner_name, poly_winner=p_name, payout=payout,
                 pnl=round(payout - float(r["total_cost"]), 4), settled_utc=store.now_iso()); changed = True
    if changed: store.rewrite("trades.csv", store.TRADES, rows)

if __name__ == "__main__":
    run()
