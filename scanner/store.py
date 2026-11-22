"""CSV files the dashboard reads. Everything is appended; nothing is rewritten except trades.csv
when trades settle."""
import csv, os, datetime as dt
from . import config

GAMES = ["matched_at", "sport", "start_utc", "kalshi_start_est_utc", "poly_start_utc", "kalshi_event", "poly_slug", "kalshi_team0", "kalshi_team1",
         "poly_team_for_kalshi0", "poly_team_for_kalshi1", "k_to_p", "match_score"]
TRADES = ["trade_id", "opened_utc", "sport", "kalshi_event", "poly_slug", "phase", "min_from_start",
          "team_on_kalshi", "kalshi_route", "kalshi_price", "kalshi_qty_avail", "kalshi_fee",
          "team_on_poly", "poly_route", "poly_price", "poly_qty_avail", "poly_fee",
          "pairs", "total_cost", "locked_profit", "profit_per_pair", "quote_gap_sec",
          "kalshi_side", "poly_side", "status", "kalshi_winner", "poly_winner", "payout", "pnl", "settled_utc"]
GAPS = ["game_key", "sport", "combo", "opened_utc", "closed_utc", "seconds_open", "phase_at_open",
        "min_from_start_at_open", "best_profit_per_pair", "best_pairs", "polls", "traded"]
SNAP = ["ts_utc", "sport", "kalshi_event", "poly_slug", "min_from_start", "team0", "team1",
        "k_ask0", "k_qty0", "k_ask1", "k_qty1", "p_ask0", "p_qty0", "p_ask1", "p_qty1",
        "best_profit_per_pair", "best_combo"]
RECHECKS = ["trade_id","delay_sec","still_profitable","profit_per_pair","pairs","kalshi_price","poly_price"]

def path(name): return os.path.join(config.DATA_DIR, name)

def now_iso(ts=None):
    return dt.datetime.fromtimestamp(ts or dt.datetime.now().timestamp(), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def append(name, header, rows):
    if not rows: return
    p = path(name); os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    new = not os.path.exists(p)
    with open(p, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if new: w.writeheader()
        for r in rows: w.writerow({k: r.get(k, "") for k in header})

def append_snapshots(rows):
    """One small CSV per hour: data/snapshots/YYYY-MM-DD/HH.csv"""
    by_file = {}
    for r in rows:
        by_file.setdefault(f"snapshots/{r['ts_utc'][:10]}/{r['ts_utc'][11:13]}.csv", []).append(r)
    for name, rs in by_file.items():
        append(name, SNAP, rs)

def read(name):
    p = path(name)
    if not os.path.exists(p): return []
    with open(p, newline="") as f: return list(csv.DictReader(f))

def rewrite(name, header, rows):
    p = path(name); tmp = p + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header); w.writeheader()
        for r in rows: w.writerow({k: r.get(k, "") for k in header})
    os.replace(tmp, p)
