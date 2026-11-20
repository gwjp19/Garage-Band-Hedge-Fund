"""The gap math: buy one team on Kalshi and the other team on Polymarket US. One of the two pays $1
per pair no matter who wins, so the trade locks in (pairs - total cost) if both legs fill."""
import math
from . import config
from .fees import kalshi_fee, poly_us_fee

def price_pair(k_price, k_qty, p_price, p_qty, max_pairs=None):
    """Returns dict with pairs, fees, total cost, locked profit and profit per pair.
    pairs is capped by what's available on both books (whole contracts)."""
    max_pairs = config.PAIRS_PER_TRADE if max_pairs is None else max_pairs
    n = int(math.floor(min(max_pairs, k_qty, p_qty)))
    size = n if n >= 1 else 1          # still report the 1-pair economics when the book is too thin
    kf = kalshi_fee(size, k_price); pf = poly_us_fee(size, p_price)
    cost = size * (k_price + p_price) + kf + pf
    return {"pairs": n, "kalshi_fee": round(kf, 3), "poly_fee": round(pf, 3), "total_cost": round(cost, 4),
            "locked_profit": round(size - cost, 4), "profit_per_pair": round((size - cost) / size, 5)}

def usable(p):
    return p is not None and config.MIN_PRICE <= p <= config.MAX_PRICE
