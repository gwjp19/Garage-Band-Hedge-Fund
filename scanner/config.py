"""Every setting the scanner uses. Change things here, not in the code."""

# Which sports to watch: (Kalshi series ticker, Polymarket US slug prefix)
SPORTS = {
    "cbb": ("KXNCAAMBGAME", "aec-cbb-"),
    "cfb": ("KXNCAAFGAME", "aec-cfb-"),
}

# When to watch a game, in minutes relative to its scheduled start
WATCH_FROM_MIN = -60        # start watching 60 min before tip/kickoff
WATCH_UNTIL_MIN = 4.5 * 60  # stop 4.5 hours after the start (covers overtime / long CFB games)

# Paper trading rule
PAIRS_PER_TRADE = 100       # max pairs to buy per gap (capped by what's on the book)
MIN_EDGE = 0.0              # trade when profit per $1 pair is above this, after fees
ONE_TRADE_PER_GAP = True    # don't buy again until the gap closes and reopens

# Fees
KALSHI_FEE_RATE = 0.07      # Kalshi: ceil(0.07 * contracts * p * (1-p)) to the cent, per order
POLY_US_FEE_RATE = 0.06     # Polymarket US: rate * contracts * p * (1-p). Rate NOT confirmed from the
                            # official fee page; check docs.polymarket.us/fees and update this.

# Prices
MIN_PRICE, MAX_PRICE = 0.03, 0.97   # ignore quotes outside this range (near-settled games)
MAX_QUOTE_GAP_SEC = 5.0             # both venues' books must be read within this many seconds

# Loop timing
POLL_SECONDS = 20           # time between scans of all live games
SNAPSHOT_EVERY_SEC = 60     # write a price snapshot per game at most this often
REMATCH_EVERY_MIN = 30      # refresh the list of games and the Kalshi <-> Polymarket match
COMMIT_EVERY_MIN = 10       # (GitHub Actions) push results this often
MAX_RUN_MIN = 5 * 60 + 40   # one run's max length; GitHub kills jobs at 6 h

# Rate limits (requests per second we allow ourselves)
KALSHI_RPS = 8
POLY_RPS = 10

DATA_DIR = "data"
