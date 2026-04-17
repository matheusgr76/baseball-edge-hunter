"""
Calibration Layer - Factors
Apply situational adjustments to devigged consensus probabilities.
Phase 2 Tier 1: SP quality + bullpen availability.
Phase 4: park, handedness split, pythagorean regression, OAA, umpire tendency.
Reliability pass (2026-04-17): conservative caps to limit false positives.
Total adjustment capped at ±6pp per team.
"""

from typing import Dict, Optional, Tuple
from models import (
    CanonicalGame, CalibratedGame, AdjustmentBreakdown,
    FactorResult, ProbablePitcher, BullpenStatus,
)
from calibration.phase4 import (
    oaa_defense_factor,
    park_factor,
    pythagorean_regression_factor,
    umpire_tendency_factor,
    wrc_handedness_factor,
)


_LEAGUE_AVG_FIP = 4.20   # Baseline for SP quality comparison
_SP_SCALE = 0.9          # Each FIP point delta → X pp adjustment
_SP_MAX_ADJ = 4.0        # Hard cap per SP factor
_BULLPEN_MAX_ADJ = 3.0   # Hard cap per bullpen factor
_BULLPEN_MODERATE_ADJ = 1.5
_TOTAL_CAP = 6.0         # Total calibration cap per team


# ============================================================================
# SP QUALITY FACTOR
# ============================================================================

def sp_quality_factor(
    home_sp: Optional[ProbablePitcher],
    away_sp: Optional[ProbablePitcher],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Compare each SP's FIP against league average and derive probability adjustment.

    Logic:
        delta_fip = LEAGUE_AVG_FIP - pitcher_fip   (positive = better than avg)
        raw_adj   = delta_fip * _SP_SCALE
        adj       = clamp(raw_adj, -_SP_MAX_ADJ, +_SP_MAX_ADJ)

    A team with a sub-3.0 FIP ace gets up to +4pp.
    A team with a 5.5+ FIP replacement gets up to -4pp.

    Returns:
        (home_factor, away_factor, home_adj_pp, away_adj_pp)
    """
    home_fip = home_sp.fip if (home_sp and home_sp.valid) else _LEAGUE_AVG_FIP
    away_fip = away_sp.fip if (away_sp and away_sp.valid) else _LEAGUE_AVG_FIP

    home_adj = _clamp((_LEAGUE_AVG_FIP - home_fip) * _SP_SCALE, -_SP_MAX_ADJ, _SP_MAX_ADJ)
    away_adj = _clamp((_LEAGUE_AVG_FIP - away_fip) * _SP_SCALE, -_SP_MAX_ADJ, _SP_MAX_ADJ)

    # Devil's advocate: regression to mean, sample size, ballpark effects
    home_devil = round(-home_adj * 0.3, 2)
    away_devil = round(-away_adj * 0.3, 2)

    home_name = home_sp.name if home_sp else "TBD"
    away_name = away_sp.name if away_sp else "TBD"
    home_hand = home_sp.hand if home_sp else "?"
    away_hand = away_sp.hand if away_sp else "?"

    home_factor = FactorResult(
        name="SP QUALITY (FIP)",
        result=round(home_adj, 2),
        explanation=(
            f"Home SP {home_name} ({home_hand}) FIP {home_fip:.2f} "
            f"vs away SP {away_name} ({away_hand}) FIP {away_fip:.2f}"
        ),
        devil=home_devil,
        devil_advocate="Small sample or park factor regression possible",
    )
    away_factor = FactorResult(
        name="SP QUALITY (FIP)",
        result=round(away_adj, 2),
        explanation=(
            f"Away SP {away_name} ({away_hand}) FIP {away_fip:.2f} "
            f"vs home SP {home_name} ({home_hand}) FIP {home_fip:.2f}"
        ),
        devil=away_devil,
        devil_advocate="Small sample or park factor regression possible",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


# ============================================================================
# BULLPEN FACTOR
# ============================================================================

def bullpen_factor(
    home_bp: Optional[BullpenStatus],
    away_bp: Optional[BullpenStatus],
) -> Tuple[FactorResult, FactorResult, float, float]:
    """
    Penalize teams with fatigued bullpens based on pitches thrown in last 48h.

    Thresholds (combined top-2 RPs):
        < 25 pitches   →  0.0pp  (fresh)
        25-39 pitches  → -1.5pp  (moderate fatigue)
        ≥ 40 pitches   → -3.0pp  (heavy use)

    Returns:
        (home_factor, away_factor, home_adj_pp, away_adj_pp)
    """
    home_adj = _bullpen_penalty(home_bp)
    away_adj = _bullpen_penalty(away_bp)

    home_detail = home_bp.details if home_bp else "Bullpen data unavailable"
    away_detail = away_bp.details if away_bp else "Bullpen data unavailable"
    home_level = home_bp.fatigue_level if home_bp else "unknown"
    away_level = away_bp.fatigue_level if away_bp else "unknown"

    # Devil: relievers may not be needed if starter goes deep
    home_devil = round(home_adj * 0.4, 2) if home_adj < 0 else 0.0
    away_devil = round(away_adj * 0.4, 2) if away_adj < 0 else 0.0

    home_factor = FactorResult(
        name="BULLPEN AVAILABILITY",
        result=round(home_adj, 2),
        explanation=f"Home: {home_detail} ({home_level})",
        devil=home_devil,
        devil_advocate="Starter may go 7+ IP; bullpen may not be needed",
    )
    away_factor = FactorResult(
        name="BULLPEN AVAILABILITY",
        result=round(away_adj, 2),
        explanation=f"Away: {away_detail} ({away_level})",
        devil=away_devil,
        devil_advocate="Starter may go 7+ IP; bullpen may not be needed",
    )
    return home_factor, away_factor, round(home_adj, 2), round(away_adj, 2)


def _bullpen_penalty(bp: Optional[BullpenStatus]) -> float:
    if not bp:
        return 0.0
    if bp.pitches_last_48h >= 40:
        return -_BULLPEN_MAX_ADJ
    if bp.pitches_last_48h >= 25:
        return -_BULLPEN_MODERATE_ADJ
    return 0.0


# ============================================================================
# CALIBRATION ENTRY POINT
# ============================================================================

def calibrate_game(
    canonical: CanonicalGame,
    home_sp: Optional[ProbablePitcher] = None,
    away_sp: Optional[ProbablePitcher] = None,
    home_bp: Optional[BullpenStatus] = None,
    away_bp: Optional[BullpenStatus] = None,
    park_factors: Optional[Dict[str, float]] = None,
    wrc_plus_splits: Optional[Dict[str, Dict[str, float]]] = None,
    team_run_profiles: Optional[Dict[str, Dict[str, float]]] = None,
    team_oaa: Optional[Dict[str, float]] = None,
    umpire_name: Optional[str] = None,
    umpire_tendencies: Optional[Dict[str, float]] = None,
) -> CalibratedGame:
    """
    Apply all available factors and return a CalibratedGame.

    If a data source is missing (None), that factor is skipped (0pp adjustment).
    Total adjustment per team is bounded to ±_TOTAL_CAP (6pp).
    """
    # SP factor
    sp_home_factor, sp_away_factor, sp_home_adj, sp_away_adj = sp_quality_factor(
        home_sp, away_sp
    )

    # Bullpen factor
    bp_home_factor, bp_away_factor, bp_home_adj, bp_away_adj = bullpen_factor(
        home_bp, away_bp
    )

    # Phase 4 factors
    park_home_factor, park_away_factor, park_home_adj, park_away_adj = park_factor(
        canonical.home_team,
        canonical.away_team,
        park_factors,
    )
    wrc_home_factor, wrc_away_factor, wrc_home_adj, wrc_away_adj = wrc_handedness_factor(
        canonical.home_team,
        canonical.away_team,
        home_sp,
        away_sp,
        wrc_plus_splits,
    )
    pyth_home_factor, pyth_away_factor, pyth_home_adj, pyth_away_adj = (
        pythagorean_regression_factor(
            canonical.home_team,
            canonical.away_team,
            team_run_profiles,
        )
    )
    oaa_home_factor, oaa_away_factor, oaa_home_adj, oaa_away_adj = oaa_defense_factor(
        canonical.home_team,
        canonical.away_team,
        team_oaa,
    )
    ump_home_factor, ump_away_factor, ump_home_adj, ump_away_adj = umpire_tendency_factor(
        canonical.home_team,
        canonical.away_team,
        umpire_name,
        umpire_tendencies,
    )

    # Aggregate per team (additive)
    home_total_raw = (
        sp_home_adj
        + bp_home_adj
        + park_home_adj
        + wrc_home_adj
        + pyth_home_adj
        + oaa_home_adj
        + ump_home_adj
    )
    away_total_raw = (
        sp_away_adj
        + bp_away_adj
        + park_away_adj
        + wrc_away_adj
        + pyth_away_adj
        + oaa_away_adj
        + ump_away_adj
    )

    home_capped = abs(home_total_raw) > _TOTAL_CAP
    away_capped = abs(away_total_raw) > _TOTAL_CAP

    home_total = _clamp(home_total_raw, -_TOTAL_CAP, _TOTAL_CAP)
    away_total = _clamp(away_total_raw, -_TOTAL_CAP, _TOTAL_CAP)

    # Bug 3 fix: clamp to physical limits before renormalization
    true_home = _clamp(round(canonical.home_prob + home_total, 2), 0.1, 99.9)
    true_away = _clamp(round(canonical.away_prob + away_total, 2), 0.1, 99.9)

    # Re-normalize to keep sum = 100%
    total = true_home + true_away
    if total > 0:
        true_home = round((true_home / total) * 100, 2)
        true_away = round((true_away / total) * 100, 2)

    favorite = "home" if true_home >= true_away else "away"

    home_adj = AdjustmentBreakdown(
        sp_quality=sp_home_adj,
        bullpen=bp_home_adj,
        park_factor=park_home_adj,
        wrc_handedness=wrc_home_adj,
        pythagorean_regression=pyth_home_adj,
        oaa_defense=oaa_home_adj,
        umpire_tendency=ump_home_adj,
        total=home_total,
        capped=home_capped,
    )
    away_adj = AdjustmentBreakdown(
        sp_quality=sp_away_adj,
        bullpen=bp_away_adj,
        park_factor=park_away_adj,
        wrc_handedness=wrc_away_adj,
        pythagorean_regression=pyth_away_adj,
        oaa_defense=oaa_away_adj,
        umpire_tendency=ump_away_adj,
        total=away_total,
        capped=away_capped,
    )

    return CalibratedGame(
        game_id=canonical.game_id,
        home_team=canonical.home_team,
        away_team=canonical.away_team,
        commence_time=canonical.commence_time,
        consensus_home_prob=canonical.home_prob,
        consensus_away_prob=canonical.away_prob,
        true_home_prob=true_home,
        true_away_prob=true_away,
        home_adjustments=home_adj,
        away_adjustments=away_adj,
        home_factors=[
            sp_home_factor,
            bp_home_factor,
            park_home_factor,
            wrc_home_factor,
            pyth_home_factor,
            oaa_home_factor,
            ump_home_factor,
        ],
        away_factors=[
            sp_away_factor,
            bp_away_factor,
            park_away_factor,
            wrc_away_factor,
            pyth_away_factor,
            oaa_away_factor,
            ump_away_factor,
        ],
        favorite=favorite,
        num_bookmakers=canonical.num_bookmakers,   # Bug 1 fix
        bookmaker_std_pp=canonical.bookmaker_std_pp,
    )


# ============================================================================
# HELPERS
# ============================================================================

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
