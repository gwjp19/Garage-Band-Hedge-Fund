"""Saves the scanner's CSV files to GitHub without ever deleting rows that another run already saved.

The old way (git pull --rebase -X theirs) let a run whose copy of the data was hours old overwrite
newer rows. Now, before every save, the scanner downloads the latest data from GitHub, combines it
with its own data row by row, and only then commits on top of the latest version.
"""
import csv, glob, io, os, subprocess, time
from . import config, store

# Which columns identify the same row in each file
KEYS = {"trades.csv": ["trade_id"],
        "gaps.csv": ["game_key", "combo", "opened_utc"],
        "games.csv": ["kalshi_event"],
        "rechecks.csv": ["trade_id","delay_sec"]}
SNAP_KEY = ["ts_utc", "kalshi_event"]
HEADERS = {"trades.csv": store.TRADES, "gaps.csv": store.GAPS, "games.csv": store.GAMES, "rechecks.csv": store.RECHECKS}
SORT_BY = {"trades.csv": "opened_utc", "gaps.csv": "opened_utc", "games.csv": "matched_at", "rechecks.csv": "trade_id"}
FINISHED = {"settled", "MISMATCH", "void"}   # a trade in one of these states never goes back to "open"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def read_local(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_remote(path):
    """The file as it is on GitHub right now (after `git fetch`). Empty if it doesn't exist there."""
    r = git("show", f"origin/main:{path}")
    return list(csv.DictReader(io.StringIO(r.stdout))) if r.returncode == 0 else []


def merge_rows(remote, local, key, is_trades=False):
    """Every row from both versions, once each. When both have the same row, the local one wins,
    except that a settled trade is never replaced by an older 'open' copy of itself."""
    merged = {}
    for row in remote + local:
        k = tuple(row.get(c, "") for c in key)
        old = merged.get(k)
        if is_trades and old is not None and old.get("status") in FINISHED and row.get("status") not in FINISHED:
            continue
        merged[k] = row
    return list(merged.values())


def write(path, header, rows, sort_col):
    rows = sorted(rows, key=lambda r: r.get(sort_col, ""))
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})
    os.replace(tmp, path)


def merge_with_github():
    """Folds GitHub's latest data into the local files. Returns the files this run should commit."""
    files = []
    for name, key in KEYS.items():
        path = os.path.join(config.DATA_DIR, name)
        local = read_local(path)
        if not local:
            continue                                     # this run never wrote the file; leave GitHub's copy alone
        rows = merge_rows(read_remote(path), local, key, is_trades=(name == "trades.csv"))
        write(path, HEADERS[name], rows, SORT_BY[name])
        files.append(path)
    for path in glob.glob(os.path.join(config.DATA_DIR, "snapshots", "*", "*.csv")):
        rows = merge_rows(read_remote(path), read_local(path), SNAP_KEY)
        write(path, store.SNAP, rows, "ts_utc")
        files.append(path)
    return files


def save(log=print, tries=5):
    """Merge with GitHub, commit only the data files on top of GitHub's latest commit, push.
    If someone else pushed in between, start over (up to `tries` times)."""
    if os.environ.get("GIT_COMMIT") != "1":
        return
    for attempt in range(tries):
        if git("fetch", "-q", "origin", "main").returncode != 0:
            log("git: fetch failed"); time.sleep(5); continue
        files = merge_with_github()
        git("reset", "-q", "--mixed", "origin/main")    # point at GitHub's latest commit; files on disk stay as they are
        if files:
            git("add", "--", *files)                     # stage ONLY our data files, never code or deletions
        if git("diff", "--cached", "--quiet").returncode == 0:
            return                                       # nothing new to save
        git("commit", "-q", "-m", f"scanner data {store.now_iso()}")
        push = git("push", "-q", "origin", "HEAD:main")
        if push.returncode == 0:
            return
        log("git: push rejected, retrying:", push.stderr.strip()[:200])
        time.sleep(3 * (attempt + 1))
    log("git: could not save after", tries, "tries; data stays on disk and will be included in the next save")
