"""
Normalization Layer - Teams
Bidirectional lookup: canonical MLB name <-> Polymarket slug abbreviation
Also handles raw API name variants -> canonical name
"""

# ============================================================================
# CANONICAL NAME -> POLYMARKET SLUG ABBREVIATION
# ============================================================================
# Critical collision pairs (distinct abbreviations required):
#   Chicago White Sox (cws) vs Chicago Cubs (chc)
#   New York Yankees (nyy) vs New York Mets (nym)
#   Los Angeles Dodgers (lad) vs Los Angeles Angels (laa)
#
# IMPORTANT: These abbreviations are assumed from the mlb-{away}-{home}-{date}
# slug pattern. VERIFY against actual Polymarket API responses on first live run.

MLB_TEAMS: dict[str, str] = {
    "Arizona Diamondbacks": "ari",
    "Atlanta Braves": "atl",
    "Baltimore Orioles": "bal",
    "Boston Red Sox": "bos",
    "Chicago White Sox": "cws",
    "Chicago Cubs": "chc",
    "Cincinnati Reds": "cin",
    "Cleveland Guardians": "cle",
    "Colorado Rockies": "col",
    "Detroit Tigers": "det",
    "Houston Astros": "hou",
    "Kansas City Royals": "kc",
    "Los Angeles Angels": "laa",
    "Los Angeles Dodgers": "lad",
    "Miami Marlins": "mia",
    "Milwaukee Brewers": "mil",
    "Minnesota Twins": "min",
    "New York Mets": "nym",
    "New York Yankees": "nyy",
    "Oakland Athletics": "oak",
    "Philadelphia Phillies": "phi",
    "Pittsburgh Pirates": "pit",
    "San Diego Padres": "sd",
    "San Francisco Giants": "sf",
    "Seattle Mariners": "sea",
    "St. Louis Cardinals": "stl",
    "Tampa Bay Rays": "tb",
    "Texas Rangers": "tex",
    "Toronto Blue Jays": "tor",
    "Washington Nationals": "was",
}

# ============================================================================
# RAW API NAME -> CANONICAL NAME
# ============================================================================
# The Odds API generally uses full names, but some variants exist.
# All 30 canonical names map to themselves as the baseline.

_CANONICAL_SELF_MAP: dict[str, str] = {name: name for name in MLB_TEAMS}

_RAW_VARIANTS: dict[str, str] = {
    # Common short forms
    "NY Yankees": "New York Yankees",
    "NY Mets": "New York Mets",
    "LA Dodgers": "Los Angeles Dodgers",
    "LA Angels": "Los Angeles Angels",
    # Period-less variant
    "St Louis Cardinals": "St. Louis Cardinals",
    # Legacy / relocation variants
    "Cleveland Indians": "Cleveland Guardians",
    "Oakland A's": "Oakland Athletics",
    "Athletics": "Oakland Athletics",
    "Sacramento Athletics": "Oakland Athletics",
    "Las Vegas Athletics": "Oakland Athletics",
    # Tampa Bay variants
    "TB Rays": "Tampa Bay Rays",
    # Chicago no-city variants
    "White Sox": "Chicago White Sox",
    "Cubs": "Chicago Cubs",
}

RAW_TO_CANONICAL: dict[str, str] = {**_CANONICAL_SELF_MAP, **_RAW_VARIANTS}


# ============================================================================
# PUBLIC API
# ============================================================================

def normalize_team_name(raw: str) -> str:
    """Return canonical team name for any known raw form. Returns raw if unknown."""
    return RAW_TO_CANONICAL.get(raw, raw)


def get_polymarket_abbr(canonical: str) -> str:
    """Return lowercase slug abbreviation for a canonical team name."""
    abbr = MLB_TEAMS.get(canonical)
    if abbr:
        return abbr
    # Fallback: first 3 chars lowercase (will log a warning in pipeline)
    return canonical[:3].lower()


def teams_match(name1: str, name2: str) -> bool:
    """True if two raw team names resolve to the same canonical team."""
    return normalize_team_name(name1).lower() == normalize_team_name(name2).lower()


def get_all_canonical_names() -> list[str]:
    """Return sorted list of all 30 canonical MLB team names."""
    return sorted(MLB_TEAMS.keys())
