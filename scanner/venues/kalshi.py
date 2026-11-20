"""Kalshi public market data (no login needed)."""
import time, datetime as dt
from ..http import RateLimitedSession
from .. import config
from .base import Side, VenueGame, Quote

API = "https://api.elections.kalshi.com/trade-api/v2"
S = RateLimitedSession(config.KALSHI_RPS, "kalshi")

def _ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

def list_games(sport, series):
    """Open game-winner events in a series. Each game is one event with two markets (one per team)."""
    markets, cursor = [], None
    while True:
        p = {"series_ticker": series, "status": "open", "limit": 1000}
        if cursor: p["cursor"] = cursor
        d = S.get(f"{API}/markets", p)
        markets += d.get("markets", []); cursor = d.get("cursor")
        if not cursor or not d.get("markets"): break
    by_event = {}
    for m in markets:
        by_event.setdefault(m["event_ticker"], []).append(m)
    games = []
    for ev, ms in by_event.items():
        if len(ms) != 2: continue
        # Kalshi's expected expiration is about 3 h after the start for these series
        start = _ts(ms[0]["expected_expiration_time"]) - 3 * 3600
        games.append(VenueGame("kalshi", ev, sport, [Side(m["ticker"], m["yes_sub_title"]) for m in ms], start))
    return games

def _best_bid(levels):
    """Kalshi lists resting BIDS in ascending price; best is the highest. Returns (price, qty)."""
    if not levels: return None, 0.0
    p, q = max(((float(a), float(b)) for a, b in levels), key=lambda x: x[0])
    return p, q

def quote(game):
    """Two ways to buy team X on Kalshi: YES on X's market (pay 1 - best NO bid on X),
    or NO on the other team's market (pay 1 - best YES bid there). Take the cheaper."""
    books = []
    for side in game.sides:
        ob = S.get(f"{API}/markets/{side.key}/orderbook").get("orderbook_fp", {})
        books.append((_best_bid(ob.get("yes_dollars")), _best_bid(ob.get("no_dollars"))))
    ts = time.time(); ask, qty, route = [], [], []
    for i in (0, 1):
        (yes_i, _), (no_i, no_i_q) = books[i][0], books[i][1]
        (yes_o, yes_o_q), _ = books[1 - i][0], books[1 - i][1]
        opts = []
        if no_i is not None: opts.append((round(1 - no_i, 4), no_i_q, f"YES {game.sides[i].key}"))
        if yes_o is not None: opts.append((round(1 - yes_o, 4), yes_o_q, f"NO {game.sides[1-i].key}"))
        if not opts:
            return Quote([None, None], [0, 0], ["", ""], ts, False, "empty book")
        p, q, r = min(opts, key=lambda x: x[0])
        ask.append(p); qty.append(q); route.append(r)
    return Quote(ask, qty, route, ts)

def result(game):
    """Index of the side that won, "void" if settled with no winner, None if not settled yet."""
    ms = [S.get(f"{API}/markets/{side.key}")["market"] for side in game.sides]
    for i, m in enumerate(ms):
        if m.get("result") == "yes":
            return i
    if all(m.get("status") in ("settled", "finalized") for m in ms):
        return "void"
    return None
