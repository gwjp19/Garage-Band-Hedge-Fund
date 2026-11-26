"""Polymarket US public market data (no login needed). One market per game; its 'long' side is one
team (buy at the best offer) and its 'short' side is the other (buy at 1 - best bid)."""
import time, datetime as dt
from ..http import RateLimitedSession
from .. import config
from .base import Side, VenueGame, Quote

API = "https://gateway.polymarket.us/v1"
S = RateLimitedSession(config.POLY_RPS, "polymarket_us")

def _ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

def list_games(sport, prefix):
    """All open moneyline markets for this sport (a few pages, ~1 second)."""
    out, off = {}, 0
    while True:
        ms = S.get(f"{API}/markets", {"limit": 500, "offset": off, "closed": "false",
                                       "marketTypes": "moneyline"}).get("markets", [])
        for m in ms:
            if m.get("slug", "").startswith(prefix) and m.get("gameStartTime"):
                out[m["slug"]] = m
        off += len(ms)
        if len(ms) < 500: break
    games = []
    for slug, m in out.items():
        sides = m.get("marketSides", [])
        if len(sides) != 2: continue
        long_i = 0 if sides[0].get("long") else 1
        names = [s["team"].get("safeName") or s["team"]["name"] for s in sides]
        g = VenueGame("polymarket_us", slug, sport,
                      [Side("long" if i == long_i else "short", names[i]) for i in (0, 1)],
                      _ts(m["gameStartTime"]), {"alt_names": [s["team"]["name"] for s in sides]})
        games.append(g)
    return games

def quote(game):
    md = S.get(f"{API}/markets/{game.game_id}/book", {"nc": random.getrandbits(48)}).get("marketData", {})
    ts = time.time()
    if md.get("state") != "MARKET_STATE_OPEN":
        return Quote([None, None], [0, 0], ["", ""], ts, False, md.get("state", "no data"))
    bids = [(float(b["px"]["value"]), float(b["qty"])) for b in md.get("bids", [])]
    offers = [(float(o["px"]["value"]), float(o["qty"])) for o in md.get("offers", [])]
    if not bids or not offers:
        return Quote([None, None], [0, 0], ["", ""], ts, False, "empty book")
    best_offer = min(offers, key=lambda x: x[0]); best_bid = max(bids, key=lambda x: x[0])
    by_role = {"long": (best_offer[0], best_offer[1], "buy long @ best offer"),
               "short": (round(1 - best_bid[0], 4), best_bid[1], "buy short @ 1 - best bid")}
    ask, qty, route = [], [], []
    for s in game.sides:
        p, q, r = by_role[s.key]; ask.append(p); qty.append(q); route.append(r)
    return Quote(ask, qty, route, ts)

def result(game):
    m = S.get(f"{API}/market/slug/{game.game_id}")["market"]
    if m.get("status") != "MARKET_STATUS_RESOLVED": return None
    prices = [s.get("price") for s in m.get("marketSides", [])]
    if sorted(prices) != ["0", "1"]: return "void"
    # marketSides come back in the same order list_games saw them; return (index, team name)
    i = prices.index("1"); t = m["marketSides"][i]["team"]
    return i, (t.get("safeName") or t["name"])
