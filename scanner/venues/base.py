"""What every venue module provides. To add Novig or ProphetX later, write a module with these
three functions and register it in run.py."""
from dataclasses import dataclass, field

@dataclass
class Side:
    key: str          # venue's id for buying this team (Kalshi market ticker / Polymarket side)
    name: str         # team name as the venue shows it

@dataclass
class VenueGame:
    venue: str
    game_id: str      # Kalshi event ticker / Polymarket slug
    sport: str
    sides: list       # two Side objects
    start_ts: float   # scheduled start, unix seconds (Kalshi's is an estimate)
    extra: dict = field(default_factory=dict)

@dataclass
class Quote:
    """Cheapest way to BUY each team right now, and how many contracts are there at that price."""
    ask: list         # [price to buy side 0, price to buy side 1]
    qty: list         # [contracts available, contracts available]
    route: list       # how each side would be bought (for the log)
    ts: float         # when the book was read
    ok: bool = True
    note: str = ""
