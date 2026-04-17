"""
Calibration Layer - Phase 4 Factors
Advanced factors applied with conservative caps.
"""

from typing import Dict, Optional, Tuple

from models import FactorResult, ProbablePitcher

_PARK_MAX_ADJ = 2.0
_WRC_SPLIT_MAX_ADJ = 3.0
_PYTHAG_MAX_ADJ = 1.5
_OAA_MAX_ADJ = 1.0
_UMPIRE_MAX_ADJ = 1.5


def park_factor(
    home_team: str,
    away_team: str,
    park_factors: Optional[Dict[str, float]],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Park factor index is centered at 100.
    Positive factor slightly favors the home side in familiar context.
    """
    park_idx = _safe_lookup(park_factors, home_team, default=100.0)
    home_adj = _clamp((park_idx - 100.0) * 0.10, -_PARK_MAX_ADJ, _PARK_MAX_ADJ)
    away_adj = -home_adj

    home_factor = FactorResult(
        name="PARK FACTOR",
        result=round(home_adj, 2),
        explanation=f"{home_team} park index {park_idx:.1f} (100 = neutral)",
        devil=round(-home_adj * 0.25, 2),
        devil_advocate="Park effects are volatile game-to-game",
    )
    away_factor = FactorResult(
        name="PARK FACTOR",
        result=round(away_adj, 2),
        explanation=f"{home_team} park index {park_idx:.1f} (road context for {away_team})",
        devil=round(-away_adj * 0.25, 2),
        devil_advocate="Road team can neutralize park effect with profile fit",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


def wrc_handedness_factor(
    home_team: str,
    away_team: str,
    home_sp: Optional[ProbablePitcher],
    away_sp: Optional[ProbablePitcher],
    wrc_plus_splits: Optional[Dict[str, Dict[str, float]]],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Compare offense-vs-handedness profile for each side.
    Uses team wRC+ split data keyed by team and pitcher handedness.
    """
    home_vs_hand = _split_key(away_sp.hand if away_sp else "R")
    away_vs_hand = _split_key(home_sp.hand if home_sp else "R")

    home_wrc = _split_lookup(wrc_plus_splits, home_team, home_vs_hand)
    away_wrc = _split_lookup(wrc_plus_splits, away_team, away_vs_hand)

    diff = home_wrc - away_wrc
    home_adj = _clamp(diff * 0.06, -_WRC_SPLIT_MAX_ADJ, _WRC_SPLIT_MAX_ADJ)
    away_adj = -home_adj

    home_factor = FactorResult(
        name="wRC+ VS SP HAND",
        result=round(home_adj, 2),
        explanation=(
            f"{home_team} {home_vs_hand.upper()}={home_wrc:.1f} vs "
            f"{away_team} {away_vs_hand.upper()}={away_wrc:.1f}"
        ),
        devil=round(-home_adj * 0.30, 2),
        devil_advocate="Split edges shrink with bullpen matchups after starter exits",
    )
    away_factor = FactorResult(
        name="wRC+ VS SP HAND",
        result=round(away_adj, 2),
        explanation=(
            f"{away_team} {away_vs_hand.upper()}={away_wrc:.1f} vs "
            f"{home_team} {home_vs_hand.upper()}={home_wrc:.1f}"
        ),
        devil=round(-away_adj * 0.30, 2),
        devil_advocate="Manager platoon usage can blunt handedness edge",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


def pythagorean_regression_factor(
    home_team: str,
    away_team: str,
    team_run_profiles: Optional[Dict[str, Dict[str, float]]],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Teams outperforming pythag expectation are mildly regressed downward.
    delta_pp is actual win% - pythag win%, in percentage points.
    """
    home_delta_pp = _profile_lookup(team_run_profiles, home_team, "delta_pp")
    away_delta_pp = _profile_lookup(team_run_profiles, away_team, "delta_pp")

    home_adj = _clamp(-home_delta_pp * 0.08, -_PYTHAG_MAX_ADJ, _PYTHAG_MAX_ADJ)
    away_adj = _clamp(-away_delta_pp * 0.08, -_PYTHAG_MAX_ADJ, _PYTHAG_MAX_ADJ)

    home_factor = FactorResult(
        name="PYTHAG REGRESSION",
        result=round(home_adj, 2),
        explanation=f"{home_team} delta={home_delta_pp:+.2f}pp (actual vs expected)",
        devil=round(-home_adj * 0.20, 2),
        devil_advocate="High-leverage bullpen performance can sustain overperformance",
    )
    away_factor = FactorResult(
        name="PYTHAG REGRESSION",
        result=round(away_adj, 2),
        explanation=f"{away_team} delta={away_delta_pp:+.2f}pp (actual vs expected)",
        devil=round(-away_adj * 0.20, 2),
        devil_advocate="Run distribution noise can distort short-season pythag deltas",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


def oaa_defense_factor(
    home_team: str,
    away_team: str,
    team_oaa: Optional[Dict[str, float]],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Defensive OAA difference applies a small correction.
    """
    home_oaa = _safe_lookup(team_oaa, home_team, default=0.0)
    away_oaa = _safe_lookup(team_oaa, away_team, default=0.0)
    diff = home_oaa - away_oaa

    home_adj = _clamp(diff * 0.04, -_OAA_MAX_ADJ, _OAA_MAX_ADJ)
    away_adj = -home_adj

    home_factor = FactorResult(
        name="OAA DEFENSE",
        result=round(home_adj, 2),
        explanation=f"{home_team} OAA {home_oaa:+.1f} vs {away_team} {away_oaa:+.1f}",
        devil=round(-home_adj * 0.25, 2),
        devil_advocate="Ball-in-play variance can overwhelm small OAA edges",
    )
    away_factor = FactorResult(
        name="OAA DEFENSE",
        result=round(away_adj, 2),
        explanation=f"{away_team} OAA {away_oaa:+.1f} vs {home_team} {home_oaa:+.1f}",
        devil=round(-away_adj * 0.25, 2),
        devil_advocate="Defensive shifts and positioning can change nightly",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


def umpire_tendency_factor(
    home_team: str,
    away_team: str,
    umpire_name: Optional[str],
    umpire_tendencies: Optional[Dict[str, float]],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Apply optional home-bias tendency by assigned home plate umpire.
    """
    bias = 0.0
    if umpire_name and umpire_tendencies:
        bias = float(umpire_tendencies.get(umpire_name, 0.0) or 0.0)

    home_adj = _clamp(bias, -_UMPIRE_MAX_ADJ, _UMPIRE_MAX_ADJ)
    away_adj = -home_adj

    ump_label = umpire_name if umpire_name else "TBD"
    home_factor = FactorResult(
        name="UMPIRE TENDENCY",
        result=round(home_adj, 2),
        explanation=f"Home plate umpire: {ump_label} | home_bias={bias:+.2f}pp",
        devil=round(-home_adj * 0.20, 2),
        devil_advocate="Umpire edges are weak and can reverse in small samples",
    )
    away_factor = FactorResult(
        name="UMPIRE TENDENCY",
        result=round(away_adj, 2),
        explanation=f"Home plate umpire: {ump_label} | away_effect={away_adj:+.2f}pp",
        devil=round(-away_adj * 0.20, 2),
        devil_advocate="Pitcher command quality can dominate zone-tendency effects",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


def _split_key(hand: str) -> str:
    return "vs_lhp" if str(hand).upper() == "L" else "vs_rhp"


def _split_lookup(
    splits: Optional[Dict[str, Dict[str, float]]],
    team: str,
    split_key: str,
) -> float:
    if not splits:
        return 100.0
    team_splits = splits.get(team, {})
    if not isinstance(team_splits, dict):
        return 100.0
    return float(team_splits.get(split_key, 100.0) or 100.0)


def _profile_lookup(
    profiles: Optional[Dict[str, Dict[str, float]]],
    team: str,
    key: str,
) -> float:
    if not profiles:
        return 0.0
    team_profile = profiles.get(team, {})
    if not isinstance(team_profile, dict):
        return 0.0
    return float(team_profile.get(key, 0.0) or 0.0)


def _safe_lookup(mapping: Optional[Dict[str, float]], key: str, default: float = 0.0) -> float:
    if not mapping:
        return default
    return float(mapping.get(key, default) or default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))

