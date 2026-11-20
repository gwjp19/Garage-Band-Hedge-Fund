"""python -m pytest tests  (or python tests/test_pricing.py)"""
import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scanner.fees import kalshi_fee, poly_us_fee
from scanner.pricing import price_pair
from scanner.venues import kalshi
from scanner.venues.base import VenueGame, Side

def test_kalshi_fee_rounds_up():
    assert kalshi_fee(100, 0.50) == 1.75          # 0.07*100*.25 = 1.75 exactly
    assert kalshi_fee(100, 0.36) == 1.62          # 1.6128 -> 1.62
    assert kalshi_fee(1, 0.50) == 0.02            # 0.0175 -> 0.02

def test_pair_locks_profit():
    # 55c on Kalshi + 40c on Polymarket US, 100 pairs available
    pr = price_pair(0.55, 500, 0.40, 300)
    assert pr["pairs"] == 100
    expected = 100 - (55 + 40 + kalshi_fee(100, .55) + poly_us_fee(100, .40))
    assert abs(pr["locked_profit"] - expected) < 1e-9

def test_size_capped_by_book():
    assert price_pair(0.55, 37.5, 0.40, 300)["pairs"] == 37

def test_kalshi_quote_picks_cheaper_route(monkeypatch=None):
    books = {"A": {"yes_dollars": [["0.40", "10"]], "no_dollars": [["0.55", "20"]]},   # YES A costs 1-.55 = .45
             "B": {"yes_dollars": [["0.58", "5"]], "no_dollars": [["0.38", "8"]]}}     # NO B costs 1-.58 = .42 -> cheaper A
    kalshi.S.get = lambda url, params=None: {"orderbook_fp": books[url.split("/")[-2]]}
    q = kalshi.quote(VenueGame("kalshi", "E", "cbb", [Side("A", "a"), Side("B", "b")], 0))
    assert q.ask[0] == 0.42 and q.qty[0] == 5 and q.route[0] == "NO B"
    assert q.ask[1] == 0.60 and q.route[1] == "NO A"                                     # min(1-.38, 1-.40)

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
