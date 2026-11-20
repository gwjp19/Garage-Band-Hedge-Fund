"""Pair each Kalshi game with the same Polymarket US game, and line up which side is which team."""
import re
from rapidfuzz import fuzz

ALIASES = {
    "uconn": "connecticut", "lsu": "louisiana state", "byu": "brigham young", "tcu": "texas christian",
    "smu": "southern methodist", "ucf": "central florida", "vcu": "virginia commonwealth",
    "unlv": "nevada las vegas", "utep": "texas el paso", "utsa": "texas san antonio",
    "umbc": "maryland baltimore county", "uab": "alabama birmingham", "ole miss": "mississippi",
    "unc": "north carolina", "uncw": "north carolina wilmington", "usc": "southern california",
    "ucla": "california los angeles", "umass": "massachusetts", "fiu": "florida international",
    "fau": "florida atlantic", "fgcu": "florida gulf coast", "liu": "long island", "njit": "new jersey tech",
    "siue": "southern illinois edwardsville", "etsu": "east tennessee state", "mtsu": "middle tennessee",
    "sfa": "stephen f austin", "pitt": "pittsburgh", "penn": "pennsylvania", "app state": "appalachian state",
    "nc state": "north carolina state", "wvu": "west virginia", "southern miss": "southern mississippi",
    "ul monroe": "louisiana monroe", "ulm": "louisiana monroe", "usf": "south florida",
    "uic": "illinois chicago", "uni": "northern iowa", "ecu": "east carolina", "uta": "texas arlington",
    "miami (fl)": "miami", "miami fl": "miami", "miami (oh)": "miami ohio", "miami oh": "miami ohio",
    "umkc": "kansas city", "csun": "cal state northridge", "csub": "cal state bakersfield",
}

def norm(s):
    s = s.lower().replace("&", " and ").replace("-", " ").replace("'", "")
    s = re.sub(r"\bst\.?$", "state", s.strip())             # "Ohio St." -> "ohio state"
    s = re.sub(r"\bst\.?\s(?=\w)", lambda m: "saint " if s.startswith(m.group(0)) else "state ", s)
    s = re.sub(r"[^a-z0-9() ]", " ", s); s = re.sub(r"\s+", " ", s).strip()
    for k in sorted(ALIASES, key=len, reverse=True):
        if s == k or s.startswith(k + " "):
            s = ALIASES[k] + s[len(k):]; break
    return " ".join(t for t in s.split() if t not in {"university", "of", "the", "college"})

def sim(a, b):
    return 0.6 * fuzz.token_set_ratio(a, b) + 0.4 * fuzz.ratio(a, b)

def side_score(k_name, p_names):
    k = norm(k_name)
    return max(sim(k, norm(n)) for n in p_names)

def match(kalshi_games, poly_games, max_start_diff_h=6, min_score=150):
    """Returns list of (kalshi_game, poly_game, k_to_p) where k_to_p[i] = Polymarket side index for
    Kalshi side i. Each game is used once; best scores win. The venues sometimes disagree on start
    time by a couple of hours, so the window is wide; team names do the real work."""
    cands = []
    for kg in kalshi_games:
        for pg in poly_games:
            if kg.sport != pg.sport or abs(kg.start_ts - pg.start_ts) > max_start_diff_h * 3600:
                continue
            pnames = [[s.name] + ([pg.extra["alt_names"][j]] if pg.extra.get("alt_names") else []) for j, s in enumerate(pg.sides)]
            for flip in (0, 1):
                sc = side_score(kg.sides[0].name, pnames[flip]) + side_score(kg.sides[1].name, pnames[1 - flip])
                if sc >= min_score:
                    cands.append((sc, kg, pg, [flip, 1 - flip]))
    cands.sort(key=lambda c: -c[0]); used_k, used_p, out = set(), set(), []
    for sc, kg, pg, k2p in cands:
        if kg.game_id in used_k or pg.game_id in used_p: continue
        used_k.add(kg.game_id); used_p.add(pg.game_id); out.append((kg, pg, k2p, sc))
    return out
