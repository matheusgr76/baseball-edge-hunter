"""
Ingestion Layer - MLB Data
Fetches probable pitchers and bullpen usage from MLB Stats API (free, no auth required).
FIP is computed from raw components (HR, BB, HBP, K, IP) — no FanGraphs dependency.
"""

import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from models import ProbablePitcher, BullpenStatus
from normalization.teams import normalize_team_name


_BASE = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "mlb-edge-hunter/1.0"}
_TIMEOUT = 10

# League-average FIP baseline (~2025 MLB environment)
_LEAGUE_AVG_FIP = 4.20
_FIP_CONSTANT = 3.17  # Makes FIP scale to ERA; cancels in delta math
_MIN_IP_FOR_FIP = 15.0  # Below this, FIP is unreliable → use ERA instead

# MLB Stats API team IDs (canonical name → team ID)
_TEAM_IDS: Dict[str, int] = {
    "Arizona Diamondbacks": 109,
    "Athletics": 133,
    "Oakland Athletics": 133,
    "Atlanta Braves": 144,
    "Baltimore Orioles": 110,
    "Boston Red Sox": 111,
    "Chicago Cubs": 112,
    "Chicago White Sox": 145,
    "Cincinnati Reds": 113,
    "Cleveland Guardians": 114,
    "Colorado Rockies": 115,
    "Detroit Tigers": 116,
    "Houston Astros": 117,
    "Kansas City Royals": 118,
    "Los Angeles Angels": 108,
    "Los Angeles Dodgers": 119,
    "Miami Marlins": 146,
    "Milwaukee Brewers": 158,
    "Minnesota Twins": 142,
    "New York Mets": 121,
    "New York Yankees": 147,
    "Philadelphia Phillies": 143,
    "Pittsburgh Pirates": 134,
    "San Diego Padres": 135,
    "San Francisco Giants": 137,
    "Seattle Mariners": 136,
    "St. Louis Cardinals": 138,
    "Tampa Bay Rays": 139,
    "Texas Rangers": 140,
    "Toronto Blue Jays": 141,
    "Washington Nationals": 120,
}


# ============================================================================
# PROBABLE PITCHERS
# ============================================================================

def fetch_probable_pitchers(date_str: str) -> Dict[str, ProbablePitcher]:
    """
    Fetch today's probable starters from MLB Stats API schedule endpoint.

    Args:
        date_str: Date in "YYYY-MM-DD" format

    Returns:
        Dict keyed by canonical team name → ProbablePitcher
        Missing teams return no entry (caller handles graceful degradation).
    """
    url = f"{_BASE}/schedule"
    params = {
        "sportId": 1,
        "date": date_str,
        "hydrate": "probablePitcher",
    }

    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  ⚠️  MLB Stats API (schedule) error: {e}")
        return {}

    result: Dict[str, ProbablePitcher] = {}
    dates = data.get("dates", [])
    if not dates:
        return {}

    year = int(date_str[:4])

    for game in dates[0].get("games", []):
        for side in ("home", "away"):
            team_data = game.get("teams", {}).get(side, {})
            team_name_raw = team_data.get("team", {}).get("name", "")
            canonical = normalize_team_name(team_name_raw)
            if not canonical:
                continue

            sp_data = team_data.get("probablePitcher")
            if not sp_data:
                continue

            player_id = sp_data.get("id")
            full_name = sp_data.get("fullName", "Unknown")

            if player_id:
                pitcher = _build_probable_pitcher(canonical, full_name, player_id, year)
                if pitcher:
                    result[canonical] = pitcher

    return result


def _build_probable_pitcher(
    team: str, name: str, player_id: int, year: int
) -> Optional[ProbablePitcher]:
    """Fetch season stats for one pitcher and return ProbablePitcher."""
    stats = _fetch_pitcher_season_stats(player_id, year)
    if not stats:
        # Try previous year as fallback (e.g. Spring Training)
        stats = _fetch_pitcher_season_stats(player_id, year - 1)
    if not stats:
        return ProbablePitcher(
            team=team, name=name, player_id=player_id,
            fip=_LEAGUE_AVG_FIP, era=_LEAGUE_AVG_FIP,
            ip=0.0, hand="R", valid=False,
        )

    ip = _parse_ip(stats.get("inningsPitched", "0.0"))
    hr = int(stats.get("homeRuns", 0) or 0)
    bb = int(stats.get("baseOnBalls", 0) or 0)
    hbp = int(stats.get("hitByPitch", 0) or 0)
    k = int(stats.get("strikeOuts", 0) or 0)
    era = float(stats.get("era", _LEAGUE_AVG_FIP) or _LEAGUE_AVG_FIP)

    fip = _calculate_fip(hr, bb, hbp, k, ip) if ip >= _MIN_IP_FOR_FIP else era
    valid = ip >= _MIN_IP_FOR_FIP

    # Fetch handedness
    hand = _fetch_pitcher_hand(player_id)

    return ProbablePitcher(
        team=team, name=name, player_id=player_id,
        fip=round(fip, 2), era=round(era, 2),
        ip=round(ip, 1), hand=hand, valid=valid,
    )


def _fetch_pitcher_season_stats(player_id: int, year: int) -> Optional[dict]:
    """Return raw pitching stat dict from MLB Stats API, or None on failure."""
    url = f"{_BASE}/people/{player_id}/stats"
    try:
        r = requests.get(
            url,
            params={"stats": "season", "season": year, "group": "pitching"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        splits = data.get("stats", [{}])[0].get("splits", [])
        return splits[0]["stat"] if splits else None
    except Exception:
        return None


def _fetch_pitcher_hand(player_id: int) -> str:
    """Return pitcher's throwing hand ('L' or 'R'). Defaults to 'R' on failure."""
    try:
        r = requests.get(
            f"{_BASE}/people/{player_id}",
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        people = data.get("people", [{}])
        ph = people[0].get("pitchHand", {})
        return ph.get("code", "R")
    except Exception:
        return "R"


def _calculate_fip(hr: int, bb: int, hbp: int, k: int, ip: float) -> float:
    """
    FIP = ((13*HR + 3*(BB+HBP) - 2*K) / IP) + FIP_constant
    Lower is better. League average ≈ 4.20.
    """
    if ip <= 0:
        return _LEAGUE_AVG_FIP
    return ((13 * hr + 3 * (bb + hbp) - 2 * k) / ip) + _FIP_CONSTANT


def _parse_ip(ip_str: str) -> float:
    """
    Convert MLB IP string to decimal innings.
    '48.2' → 48 + 2/3 = 48.667  (the .N means N outs, not N tenths)
    """
    try:
        parts = str(ip_str).split(".")
        full = int(parts[0])
        outs = int(parts[1]) if len(parts) > 1 else 0
        return full + outs / 3
    except (ValueError, IndexError):
        return 0.0


# ============================================================================
# BULLPEN AVAILABILITY
# ============================================================================

def fetch_bullpen_status(team_canonical: str, date_str: str) -> BullpenStatus:
    """
    Estimate bullpen fatigue for a team by checking the top relievers'
    pitch counts across the last 2 days.

    Strategy:
    1. Fetch active roster for the team
    2. Identify relievers (gamesStarted == 0 in season stats)
    3. For each reliever, sum pitches thrown in games on date_str-1 and date_str-2
    4. Sum pitches for the top 2 relievers by usage
    """
    team_id = _TEAM_IDS.get(team_canonical)
    if not team_id:
        return _unknown_bullpen(team_canonical)

    # Date window: yesterday + day before
    base_dt = datetime.strptime(date_str, "%Y-%m-%d")
    window_dates = [
        (base_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        (base_dt - timedelta(days=2)).strftime("%Y-%m-%d"),
    ]
    year = base_dt.year

    reliever_ids = _get_reliever_ids(team_id, year)
    if not reliever_ids:
        return _unknown_bullpen(team_canonical)

    # Get pitches thrown per reliever in the date window
    usage: Dict[int, int] = {}
    for pid in reliever_ids[:8]:   # Check top 8 pitchers on roster max
        pitches = _pitches_in_window(pid, window_dates, year)
        if pitches > 0:
            usage[pid] = pitches

    if not usage:
        return BullpenStatus(
            team=team_canonical,
            pitches_last_48h=0,
            fatigue_level="fresh",
            details="No recent bullpen usage found",
        )

    # Top 2 relievers by pitches thrown
    sorted_usage = sorted(usage.values(), reverse=True)
    top2_pitches = sum(sorted_usage[:2])

    fatigue_level = _fatigue_level(top2_pitches)
    details = f"Top-2 RPs threw {top2_pitches} pitches in last 48h"

    return BullpenStatus(
        team=team_canonical,
        pitches_last_48h=top2_pitches,
        fatigue_level=fatigue_level,
        details=details,
    )


def _get_reliever_ids(team_id: int, year: int) -> List[int]:
    """Return player IDs for pitchers on active roster who are relievers."""
    try:
        r = requests.get(
            f"{_BASE}/teams/{team_id}/roster",
            params={"rosterType": "active"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        roster = r.json().get("roster", [])
    except Exception:
        return []

    pitcher_ids = [
        p["person"]["id"]
        for p in roster
        if p.get("position", {}).get("type") == "Pitcher"
    ]

    # Filter to relievers: season gamesStarted == 0
    reliever_ids = []
    for pid in pitcher_ids:
        stats = _fetch_pitcher_season_stats(pid, year)
        if stats and int(stats.get("gamesStarted", 0) or 0) == 0:
            reliever_ids.append(pid)

    return reliever_ids


def _pitches_in_window(player_id: int, dates: List[str], year: int) -> int:
    """Return total pitches thrown by player_id on any of the given dates."""
    try:
        r = requests.get(
            f"{_BASE}/people/{player_id}/stats",
            params={"stats": "gameLog", "season": year, "group": "pitching"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        splits = data.get("stats", [{}])[0].get("splits", [])
    except Exception:
        return 0

    total = 0
    for entry in splits:
        entry_date = entry.get("date", "")
        if entry_date in dates:
            total += int(entry.get("stat", {}).get("numberOfPitches", 0) or 0)
    return total


def _fatigue_level(pitches: int) -> str:
    if pitches >= 40:
        return "heavy"
    if pitches >= 25:
        return "moderate"
    return "fresh"


def _unknown_bullpen(team: str) -> BullpenStatus:
    return BullpenStatus(
        team=team,
        pitches_last_48h=0,
        fatigue_level="fresh",
        details="Bullpen data unavailable — assuming fresh",
    )
