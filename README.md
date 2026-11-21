# Live cross-venue gap scanner (Kalshi vs Polymarket US)

Watches college basketball and college football game-winner markets on Kalshi and Polymarket US,
and paper-trades every time buying one team on one venue and the other team on the other venue
costs less than $1 per pair after fees. One of the two legs pays $1 whoever wins, so a filled pair
locks in `$1 - cost`. Nothing here places real orders.

Runs on GitHub Actions (free unlimited minutes for public repos) and commits its results to `data/`
as CSV files for the dashboard to read.

## Setup

1. Push this folder to a **public** GitHub repo.
2. Repo **Settings → Actions → General → Workflow permissions**: choose **Read and write permissions**
   (lets the job commit `data/`).
3. **Actions** tab → enable workflows → open **live scanner** → **Run workflow** to start it once by hand.
   After that it starts itself every 30 minutes; if a run is already going, the next one waits.

Run locally:

```bash
pip install -r requirements.txt
python -m scanner.run --minutes 10     # scan for 10 minutes (no git commits unless GIT_COMMIT=1)
python -m scanner.settle               # settle finished paper trades
python tests/test_pricing.py           # fee / pricing / order-book checks
```

## How a run works

1. Lists open game-winner markets on both venues, matches them by team names (start times can
   disagree by a couple of hours between venues, so names do the work), and records matches in
   `data/games.csv`.
2. Every `POLL_SECONDS`, for each game from 60 min before the start to 4.5 h after it, reads both
   order books and works out the cheapest way to buy each team on each venue:
   - **Kalshi:** YES on that team's market (1 − best NO bid) or NO on the other team's market
     (1 − best YES bid), whichever is cheaper.
   - **Polymarket US:** the market's "long" team at the best offer; the other team at 1 − best bid.
3. For both combinations (team A on Kalshi + team B on Polymarket US, and the reverse) it prices
   up to `PAIRS_PER_TRADE` pairs, capped by the contracts available at the best price on each book,
   including both venues' taker fees.
4. A positive result opens a **gap** and logs one **paper trade** (another only after the gap closes
   and reopens). When the gap closes, its length and best price go to `data/gaps.csv`.
5. Once a minute per game it writes a price snapshot.
6. Every 10 minutes it settles finished trades and commits `data/` to the repo.
7. It stops when no game is live or starting within 90 minutes, or after 5 h 40 m.

## Files in `data/`

| File | One row per | Key columns |
|---|---|---|
| `games.csv` | matched game | both venues' ids, both start times, team names on each venue, match score |
| `trades.csv` | paper trade | prices, contracts available, `pairs`, both fees, `total_cost`, `locked_profit`, `profit_per_pair`, `quote_gap_sec`; after settling: `status`, winners, `payout`, `pnl` |
| `gaps.csv` | gap from open to close | `seconds_open`, `best_profit_per_pair`, `best_pairs`, `polls`, `phase_at_open`, `min_from_start_at_open` |
| `snapshots/YYYY-MM-DD/HH.csv` | game per minute | best buy price and contracts for each team on each venue, best combo's profit |

`status` in `trades.csv`:
- `open`: game not settled on both venues yet
- `settled`: exactly one leg won, as it should
- `MISMATCH`: both legs won or both lost, meaning the venues settled the game differently. This is a
  real risk of the strategy and worth watching.
- `void`: a venue voided the market

## Settings (`scanner/config.py`)

`PAIRS_PER_TRADE`, `MIN_EDGE`, `ONE_TRADE_PER_GAP`, watch window, poll speed, price limits, and
the fee rates.

- **Kalshi fee:** 0.07 × contracts × p × (1 − p), rounded up to the cent per order.
- **Polymarket US fee:** `POLY_US_FEE_RATE` × contracts × p × (1 − p). **The 0.06 rate is not
  confirmed from Polymarket US's official fee page.** Check `docs.polymarket.us/fees` and update it.

## Known limits

- **Not simultaneous.** The two books are read about a second apart (`quote_gap_sec`). Trades with
  a quote gap above `MAX_QUOTE_GAP_SEC` (5 s) are skipped.
- **Fills are assumed.** A real order could miss if the book moves first; the logs show how much
  was available at the best price but not whether you'd have got it.
- **Polling, not streaming.** Gaps shorter than one poll cycle (~20 s or more with many live games)
  can be missed or partly seen. Both venues offer WebSocket feeds if you want to go faster later.
- **GitHub schedule jitter.** Scheduled runs can start late, so a few minutes between runs may be
  missed.

## Adding Novig or ProphetX

Both need keys from your account (Novig: a key from your profile, with signed requests; ProphetX:
market data keys by email request). Write `scanner/venues/<name>.py` with the same three functions
as `polymarket_us.py`: `list_games`, `quote` and `result`. Keep keys in GitHub repo
**Settings → Secrets and variables → Actions** and read them from environment variables. Never
put keys in the code: the repo is public.

## Updates and Changes

- **Fee Update (Nov 21, 2026):** The Polymarket US taker coefficient was changed from the assumed 0.06 to the actual Tier One 0.095. It will be held at 0.095 during the full paper testing to ensure the model is profitable even less favorable conditions. It is worth noting that any trades before this date are slightly optimistic.
