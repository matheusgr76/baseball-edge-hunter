"""
Backtesting - Retrosheet Game Log Parser
Parses past-seasons/glYYYY.txt (Retrosheet Game Logs) into GameResult objects.

Retrosheet Game Log column layout (0-indexed):
  col[0]  — date (YYYYMMDD)
  col[1]  — game number (0=single, 1=first DH game, 2=second DH game)
  col[2]  — day of week
  col[3]  — visiting team Retrosheet code (e.g. LAN, NYA, SDN)
  col[4]  — visiting league
  col[5]  — visiting game number
  col[6]  — home team Retrosheet code
  col[7]  — home league
  col[8]  — home game number
  col[9]  — visiting runs scored
  col[10] — home runs scored

Reference: https://www.retrosheet.org/gamelogs/glfields.txt
"""

import csv
import os
from datetime import date
from typing import List, Optional

from backtesting.models import GameResult


# ============================================================================
# Retrosheet 3-char code → canonical MLB team name
# ============================================================================
# Codes used in Retrosheet game logs differ from The Odds API and Polymarket.
# "LAN" = Los Angeles Dodgers, "NYA" = New York Yankees, etc.

RETRO_TO_CANONICAL: dict[str, str] = {
    "ANA": "Los Angeles Angels",    # Anaheim / Los Angeles (pre-2005)
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHA": "Chicago White Sox",     # Note: CHA = White Sox (American League)
    "CHN": "Chicago Cubs",          # Note: CHN = Cubs (National League)
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KCA": "Kansas City Royals",
    "LAN": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYA": "New York Yankees",      # American League
    "NYN": "New York Mets",         # National League
    "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDN": "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SFN": "San Francisco Giants",
    "SLN": "St. Louis Cardinals",
    "TBA": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals",
    # Legacy / alternate codes
    "FLO": "Miami Marlins",         # Florida Marlins (pre-2012)
    "MON": "Washington Nationals",  # Montreal Expos (pre-2005)
}


def retro_code_to_canonical(code: str) -> Optional[str]:
    """Return canonical team name for a Retrosheet 3-char code, or None if unknown."""
    return RETRO_TO_CANONICAL.get(code.strip().upper())


def parse_season(year: int, data_dir: str = "past-seasons") -> List[GameResult]:
    """
    Parse a single MLB season game log file into GameResult objects.

    Args:
        year: Season year (e.g. 2024).
        data_dir: Directory containing glYYYY.txt files.

    Returns:
        List of GameResult objects. Unknown team codes are skipped with a warning.
    """
    filename = os.path.join(data_dir, f"gl{year}.txt")
    if not os.path.exists(filename):
        print(f"  ⚠️  Game log not found: {filename}")
        return []

    results: List[GameResult] = []
    skipped = 0

    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 11:
                continue  # malformed row

            try:
                raw_date = row[0].strip()
                away_code = row[3].strip().upper()
                home_code = row[6].strip().upper()
                away_runs = int(row[9].strip())
                home_runs = int(row[10].strip())
            except (ValueError, IndexError):
                skipped += 1
                continue

            # Parse date  YYYYMMDD → date
            try:
                game_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
            except (ValueError, IndexError):
                skipped += 1
                continue

            # Resolve team codes
            home_canonical = retro_code_to_canonical(home_code)
            away_canonical = retro_code_to_canonical(away_code)

            if home_canonical is None or away_canonical is None:
                # Unknown code — skip silently (post-season games, All-Star, etc.)
                skipped += 1
                continue

            results.append(
                GameResult(
                    game_date=game_date,
                    home_team_code=home_canonical,
                    away_team_code=away_canonical,
                    home_runs=home_runs,
                    away_runs=away_runs,
                    home_won=(home_runs > away_runs),
                )
            )

    print(f"  ✓ Parsed gl{year}.txt → {len(results)} games ({skipped} skipped)")
    return results


def build_result_lookup(results: List[GameResult]) -> dict:
    """
    Build a lookup dict: (game_date_str, home_canonical, away_canonical) → GameResult.

    game_date_str format: "YYYY-MM-DD"
    """
    lookup = {}
    for r in results:
        key = (str(r.game_date), r.home_team_code, r.away_team_code)
        lookup[key] = r
    return lookup
