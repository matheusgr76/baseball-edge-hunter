"""
Ingestion Layer - Phase 4 Data
Loads advanced-factor datasets and fetches lightweight MLB context.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

from normalization.teams import normalize_team_name

_BASE = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "mlb-edge-hunter/1.0"}
_TIMEOUT = 10

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_park_factors(file_path: Optional[str] = None) -> Dict[str, float]:
    """
    Return team -> park factor index (100 = neutral).
    Supports either:
      - flat map {team: factor}
      - nested map {"teams": {team: factor}}
    """
    payload = _load_payload("park_factors.json", file_path)
    source = payload.get("teams", payload)
    return _normalize_float_map(source)


def load_wrc_plus_splits(file_path: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    """
    Return team -> {"vs_lhp": float, "vs_rhp": float}.
    Supports either:
      - flat map {team: {"vs_lhp": x, "vs_rhp": y}}
      - nested map {"teams": {...}}
    """
    payload = _load_payload("wrc_plus_splits.json", file_path)
    source = payload.get("teams", payload)
    out: Dict[str, Dict[str, float]] = {}

    if not isinstance(source, dict):
        return out

    for raw_team, value in source.items():
        if not isinstance(value, dict):
            continue
        team = normalize_team_name(str(raw_team))
        vs_lhp = _safe_float(value.get("vs_lhp"), default=100.0)
        vs_rhp = _safe_float(value.get("vs_rhp"), default=100.0)
        out[team] = {"vs_lhp": vs_lhp, "vs_rhp": vs_rhp}

    return out


def load_team_oaa(file_path: Optional[str] = None) -> Dict[str, float]:
    """
    Return team -> OAA value.
    Supports either:
      - flat map {team: oaa}
      - nested map {"teams": {team: oaa}}
    """
    payload = _load_payload("team_oaa.json", file_path)
    source = payload.get("teams", payload)
    return _normalize_float_map(source)


def load_umpire_tendencies(file_path: Optional[str] = None) -> Dict[str, float]:
    """
    Return umpire name -> home bias in percentage points.
    Supports either:
      - flat map {umpire_name: home_bias_pp}
      - nested map {"umpires": {...}}
    """
    payload = _load_payload("umpire_tendencies.json", file_path)
    source = payload.get("umpires", payload)
    out: Dict[str, float] = {}

    if not isinstance(source, dict):
        return out

    for umpire_name, bias in source.items():
        name = str(umpire_name).strip()
        if not name:
            continue
        out[name] = _safe_float(bias, default=0.0)
    return out


def fetch_home_plate_umpires(date_str: str) -> Dict[Tuple[str, str], str]:
    """
    Return (home_team, away_team) -> home plate umpire full name.
    Missing umpire assignments are omitted.
    """
    url = f"{_BASE}/schedule"
    params = {"sportId": 1, "date": date_str, "hydrate": "officials"}

    try:
        response = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}

    out: Dict[Tuple[str, str], str] = {}
    for date_row in payload.get("dates", []):
        for game in date_row.get("games", []):
            teams = game.get("teams", {})
            home_raw = teams.get("home", {}).get("team", {}).get("name", "")
            away_raw = teams.get("away", {}).get("team", {}).get("name", "")
            home_team = normalize_team_name(home_raw)
            away_team = normalize_team_name(away_raw)
            if not home_team or not away_team:
                continue

            umpire = _extract_home_plate_umpire(game)
            if umpire:
                out[(home_team, away_team)] = umpire

    return out


def fetch_team_run_profiles(date_str: str) -> Dict[str, Dict[str, float]]:
    """
    Return team season run profile for pythagorean-regression factor.
    Output per team:
      wins, losses, runs_scored, runs_allowed, actual_win_pct,
      pythag_win_pct, delta_pp (actual - pythag, in percentage points)
    """
    season = int(date_str[:4])
    url = f"{_BASE}/standings"
    params = {
        "leagueId": "103,104",
        "season": season,
        "standingsTypes": "regularSeason",
    }

    try:
        response = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}

    out: Dict[str, Dict[str, float]] = {}
    for record in payload.get("records", []):
        for team_row in record.get("teamRecords", []):
            team_name_raw = team_row.get("team", {}).get("name", "")
            team_name = normalize_team_name(team_name_raw)
            if not team_name:
                continue

            wins = _safe_float(team_row.get("wins"), default=0.0)
            losses = _safe_float(team_row.get("losses"), default=0.0)
            runs_scored = _safe_float(team_row.get("runsScored"), default=0.0)
            runs_allowed = _safe_float(team_row.get("runsAllowed"), default=0.0)

            games = wins + losses
            if games <= 0:
                continue

            actual_win_pct = wins / games
            pythag_win_pct = _pythagorean_win_pct(runs_scored, runs_allowed)
            delta_pp = (actual_win_pct - pythag_win_pct) * 100.0

            out[team_name] = {
                "wins": wins,
                "losses": losses,
                "runs_scored": runs_scored,
                "runs_allowed": runs_allowed,
                "actual_win_pct": actual_win_pct,
                "pythag_win_pct": pythag_win_pct,
                "delta_pp": delta_pp,
            }

    return out


def _extract_home_plate_umpire(game_row: dict) -> str:
    officials = game_row.get("officials", [])
    for official_row in officials:
        official_type = str(official_row.get("officialType", "")).strip().lower()
        if official_type != "home plate":
            continue

        official_data = official_row.get("official", {})
        name = str(
            official_data.get("fullName")
            or official_data.get("name")
            or official_row.get("fullName")
            or ""
        ).strip()
        if name:
            return name
    return ""


def _normalize_float_map(raw_map: object) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not isinstance(raw_map, dict):
        return out

    for raw_key, raw_value in raw_map.items():
        team = normalize_team_name(str(raw_key))
        out[team] = _safe_float(raw_value, default=0.0)
    return out


def _load_payload(default_filename: str, file_path: Optional[str]) -> dict:
    path = Path(file_path) if file_path else (_DATA_DIR / default_filename)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pythagorean_win_pct(
    runs_scored: float,
    runs_allowed: float,
    exponent: float = 1.83,
) -> float:
    if runs_scored <= 0 and runs_allowed <= 0:
        return 0.5
    if runs_scored <= 0:
        return 0.0
    if runs_allowed <= 0:
        return 1.0

    scored_term = runs_scored ** exponent
    allowed_term = runs_allowed ** exponent
    denom = scored_term + allowed_term
    if denom <= 0:
        return 0.5
    return scored_term / denom

