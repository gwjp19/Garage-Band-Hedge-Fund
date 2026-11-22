"""One-time fix: brings back rows that were lost from data/trades.csv and data/gaps.csv.

Git kept a full copy of each file every time the scanner saved. This goes through every saved copy,
oldest to newest, and keeps every row that ever existed. For trades it keeps the newest version of
each trade, but never lets an older "open" copy replace a settled one.

Run from the repo's main folder, after `git pull`:
    python tools/restore_from_history.py
Then commit and push data/trades.csv and data/gaps.csv. Trades that come back as "open" get settled
by the scanner's next run.
"""
import os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scanner import sync, store
import csv, io

def versions(path):
    """Every committed copy of a file, oldest first."""
    commits = subprocess.run(["git", "log", "--format=%h", "--", path], capture_output=True, text=True).stdout.split()
    for c in reversed(commits):
        r = subprocess.run(["git", "show", f"{c}:{path}"], capture_output=True, text=True)
        if r.returncode == 0:
            yield list(csv.DictReader(io.StringIO(r.stdout)))

for name in ["trades.csv", "gaps.csv"]:
    path = os.path.join("data", name)
    current = sync.read_local(path)
    rows = []
    for old in versions(path):
        rows = sync.merge_rows(rows, old, sync.KEYS[name], is_trades=(name == "trades.csv"))
    rows = sync.merge_rows(rows, current, sync.KEYS[name], is_trades=(name == "trades.csv"))
    sync.write(path, sync.HEADERS[name], rows, sync.SORT_BY[name])
    print(f"{name}: {len(current)} rows before, {len(rows)} after ({len(rows) - len(current)} restored)")
