import math
from . import config

def kalshi_fee(contracts, price):
    """Kalshi taker fee for one order, rounded UP to the next cent."""
    raw = config.KALSHI_FEE_RATE * contracts * price * (1 - price)
    return math.ceil(round(raw * 100, 6)) / 100

def poly_us_fee(contracts, price):
    """Polymarket US taker fee, rounded to the nearest $0.001 (minimum $0.001)."""
    raw = config.POLY_US_FEE_RATE * contracts * price * (1 - price)
    return 0.0 if raw == 0 else max(0.001, round(raw, 3))
