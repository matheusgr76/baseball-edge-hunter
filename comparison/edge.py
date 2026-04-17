"""
Comparison Layer - Edge Detection
Calculate edge per outcome and assign 5-tier signal.
EdgeAnalysis is per-outcome (two per game: home + away).
Accepts CanonicalGame (Phase 1) or CalibratedGame (Phase 2+).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta, timezone

from models import CanonicalGame, CalibratedGame, PolymarketOpportunity, EdgeAnalysis
import config

_SIGNAL_HISTORY_CACHE: Optional[Dict[Tuple[str, str], List[dict]]] = None


def calculate_edge(
    game: Union[CanonicalGame, CalibratedGame],
    poly_home: PolymarketOpportunity,
    poly_away: PolymarketOpportunity,
) -> List[EdgeAnalysis]:
    """
    Calculate edge for both outcomes of a game.

    Accepts either CanonicalGame (Phase 1, true_prob == consensus_prob) or
    CalibratedGame (Phase 2+, true_prob reflects situational adjustments).

    Returns:
        [home_edge, away_edge] — always two EdgeAnalysis objects.
    """
    if isinstance(game, CalibratedGame):
        home_consensus = game.consensus_home_prob
        away_consensus = game.consensus_away_prob
        home_true = game.true_home_prob
        away_true = game.true_away_prob
        home_factors = game.home_factors
        away_factors = game.away_factors
        num_bookmakers = game.num_bookmakers   # Bug 1 fix: was hardcoded to 0
        bm_std_pp = game.bookmaker_std_pp
    else:
        home_consensus = away_consensus = 0.0  # unused in Phase 1
        home_true = game.home_prob
        away_true = game.away_prob
        home_consensus = game.home_prob
        away_consensus = game.away_prob
        home_factors = []
        away_factors = []
        num_bookmakers = game.num_bookmakers
        bm_std_pp = game.bookmaker_std_pp

    home_edge = _single_edge(
        game_id=game.game_id,
        team="home",
        team_name=game.home_team,
        opponent=game.away_team,
        commence_time=game.commence_time,
        consensus_prob=home_consensus,
        true_prob=home_true,
        poly=poly_home,
        num_bookmakers=num_bookmakers,
        factors=home_factors,
        bm_std_pp=bm_std_pp,
    )
    away_edge = _single_edge(
        game_id=game.game_id,
        team="away",
        team_name=game.away_team,
        opponent=game.home_team,
        commence_time=game.commence_time,
        consensus_prob=away_consensus,
        true_prob=away_true,
        poly=poly_away,
        num_bookmakers=num_bookmakers,
        factors=away_factors,
        bm_std_pp=bm_std_pp,
    )
    return [home_edge, away_edge]


def _single_edge(
    game_id: str,
    team: str,
    team_name: str,
    opponent: str,
    commence_time: datetime,
    consensus_prob: float,
    true_prob: float,
    poly: PolymarketOpportunity,
    num_bookmakers: int,
    factors: list = None,
    bm_std_pp: float = 0.0,
) -> EdgeAnalysis:
    edge_pp = round(true_prob - poly.polymarket_prob, 2)
    confidence_pct = _confidence(edge_pp, num_bookmakers, factors, bm_std_pp)
    signal = _assign_signal(edge_pp, confidence_pct, poly.polymarket_prob)

    if signal in ("STRONG BET", "BET") and _is_rematch_flip_risk(
        team_name=team_name,
        opponent=opponent,
        commence_time=commence_time,
        edge_pp=edge_pp,
    ):
        confidence_pct = max(35, confidence_pct - config.REMATCH_FLIP_CONF_PENALTY)
        signal = "SKIP"

    actionable = signal in ("STRONG BET", "BET")

    return EdgeAnalysis(
        game_id=game_id,
        team=team,
        team_name=team_name,
        opponent=opponent,
        commence_time=commence_time,
        consensus_prob=round(consensus_prob, 2),
        true_prob=round(true_prob, 2),
        polymarket_prob=round(poly.polymarket_prob, 2),
        edge_pp=edge_pp,
        signal=signal,
        confidence_pct=confidence_pct,
        actionable=actionable,
        factors=factors or [],
        polymarket_condition_id=poly.condition_id,
        polymarket_question=poly.question,
        polymarket_liquidity=poly.liquidity,
        timestamp=datetime.now(),
    )


def _assign_signal(edge_pp: float, confidence_pct: int, polymarket_prob: float = 0.0) -> str:
    """
    Assign 5-tier signal based on edge and confidence.

    Tiers (from CLAUDE.md):
        STRONG BET  — edge >= STRONG_BET_EDGE_PP AND confidence >= STRONG_BET_CONF_PCT
        BET         — edge >= BET_EDGE_PP AND confidence >= BET_CONF_PCT
        SKIP        — edge in [FADE_MIN_PP, BET_EDGE_PP)   (insufficient or no edge)
        FADE        — edge in [-3.0, -1.0)  (market overpriced on Polymarket)
        AVOID       — edge < -3.0           (strong negative edge)

    Edge-floor guards (reliability pass, 2026-04-17):
        Moderate favorite band: requires moderate edge cushion
        Higher implied favorite probability: requires larger edge cushion
    """
    if edge_pp >= config.STRONG_BET_EDGE_PP and confidence_pct >= config.STRONG_BET_CONF_PCT:
        signal = "STRONG BET"
    elif edge_pp >= config.BET_EDGE_PP and confidence_pct >= config.BET_CONF_PCT:
        signal = "BET"
    elif edge_pp < config.AVOID_THRESHOLD_PP:
        return "AVOID"
    elif edge_pp < config.FADE_MIN_PP:
        return "FADE"
    else:
        return "SKIP"

    # --- Edge-floor guards ---
    # Learned from basketball: moderate favorites with thin edges are the loss zone.
    # Downgrade actionable signals to SKIP when cushion is too thin.
    market_prob_dec = polymarket_prob / 100.0
    in_moderate_band = (config.MODERATE_FAV_BAND[0]
                        <= market_prob_dec
                        <= config.MODERATE_FAV_BAND[1])
    if in_moderate_band and edge_pp < config.MODERATE_FAV_MIN_EDGE:
        return "SKIP"

    if market_prob_dec > config.HIGH_CONF_THRESHOLD and edge_pp < config.HIGH_CONF_MIN_EDGE:
        return "SKIP"

    return signal


def _confidence(
    edge_pp: float,
    num_bookmakers: int,
    factors: list = None,
    bm_std_pp: float = 0.0,
) -> int:
    """
    Derive confidence percentage from edge magnitude, bookmaker count,
    factor agreement, data completeness, and bookmaker variance.

    Components:
        1. Base: 48
        2. Bookmaker count bonus: +4/+10/+16
        3. Edge magnitude bonus: +2/+4/+6/+9/+12
        4. Factor agreement: +4 if aligned, -6 if conflicting
        5. Data completeness: -4 per missing core Tier-1 factor
        6. Sparse-factor guard: -4 when only one non-zero factor contributes
        7. Bookmaker variance: -6/-10 for disagreement
        8. Volatility penalty: -4 for large-edge + moderate variance combos

    Reliability-first cap: 93%.
    """
    base = 48

    # Bookmaker count bonus
    if num_bookmakers >= 5:
        base += 16
    elif num_bookmakers >= 3:
        base += 10
    elif num_bookmakers >= 2:
        base += 4

    # Edge magnitude bonus
    abs_edge = abs(edge_pp)
    if abs_edge >= 8.0:
        base += 12
    elif abs_edge >= 5.0:
        base += 9
    elif abs_edge >= 3.0:
        base += 6
    elif abs_edge >= 2.0:
        base += 4
    elif abs_edge >= 1.0:
        base += 2

    required_factor_names = {"SP QUALITY (FIP)", "BULLPEN AVAILABILITY"}

    # Factor agreement + data completeness
    if factors:
        nonzero_factors = [f for f in factors if abs(f.result) > 0.001]
        missing_required = [
            f for f in factors
            if f.name in required_factor_names and abs(f.result) <= 0.001
        ]

        # Data completeness penalty only for core Tier-1 factors
        base -= len(missing_required) * 4

        # Factor agreement: do all nonzero factors point the same direction?
        if len(nonzero_factors) >= 2:
            positive = sum(1 for f in nonzero_factors if f.result > 0)
            negative = len(nonzero_factors) - positive
            if positive == len(nonzero_factors) or negative == len(nonzero_factors):
                base += 4
            else:
                base -= 6
        elif len(nonzero_factors) == 1:
            base -= 4

    # Bookmaker variance penalty: books disagree on the true price
    if bm_std_pp > 4.5:
        base -= 10
    elif bm_std_pp > 3.0:
        base -= 6

    if abs_edge >= 6.0 and bm_std_pp > 2.5:
        base -= 4

    return max(35, min(base, 93))


def _is_rematch_flip_risk(
    team_name: str,
    opponent: str,
    commence_time: datetime,
    edge_pp: float,
) -> bool:
    if not config.REMATCH_FLIP_GUARD_ENABLED:
        return False

    if abs(edge_pp) >= config.REMATCH_FLIP_OVERRIDE_EDGE:
        return False

    pair_key = _pair_key(team_name, opponent)
    history = _load_signal_history().get(pair_key, [])
    if not history:
        return False

    current_dt = _to_utc(commence_time)
    if current_dt is None:
        return False

    lookback_floor = current_dt - timedelta(hours=config.REMATCH_FLIP_LOOKBACK_HOURS)
    prior_candidates = [
        row
        for row in history
        if row["commence_time"] < current_dt and row["commence_time"] >= lookback_floor
    ]
    if not prior_candidates:
        return False

    previous = prior_candidates[-1]
    if previous["team_name"].lower() == team_name.lower():
        return False

    if abs(previous["edge_pp"]) < config.REMATCH_FLIP_MIN_PRIOR_EDGE:
        return False

    print(
        "  ⚠️  Reliability guard: rematch side flip detected "
        f"({team_name} vs {opponent}); previous actionable edge "
        f"was on {previous['team_name']} ({previous['edge_pp']:+.2f}pp). "
        "Downgrading to SKIP."
    )
    return True


def _load_signal_history() -> Dict[Tuple[str, str], List[dict]]:
    global _SIGNAL_HISTORY_CACHE
    if _SIGNAL_HISTORY_CACHE is not None:
        return _SIGNAL_HISTORY_CACHE

    history_path = (
        Path(__file__).resolve().parent.parent
        / config.OUTPUT_DIRECTORY
        / "predictions_log.json"
    )
    by_pair: Dict[Tuple[str, str], List[dict]] = {}

    try:
        raw = history_path.read_text(encoding="utf-8")
        entries = json.loads(raw) if raw.strip() else []
    except Exception:
        _SIGNAL_HISTORY_CACHE = {}
        return _SIGNAL_HISTORY_CACHE

    if not isinstance(entries, list):
        _SIGNAL_HISTORY_CACHE = {}
        return _SIGNAL_HISTORY_CACHE

    for row in entries:
        if not isinstance(row, dict):
            continue
        if not row.get("actionable", False):
            continue
        if row.get("signal") not in ("BET", "STRONG BET"):
            continue

        team_name = str(row.get("team_name", "")).strip()
        opponent = str(row.get("opponent", "")).strip()
        if not team_name or not opponent:
            continue

        commence_raw = row.get("commence_time") or row.get("logged_at")
        commence_dt = _to_utc(commence_raw)
        if commence_dt is None:
            continue

        edge_pp = float(row.get("edge_pp", 0.0) or 0.0)
        key = _pair_key(team_name, opponent)
        by_pair.setdefault(key, []).append(
            {
                "team_name": team_name,
                "opponent": opponent,
                "edge_pp": edge_pp,
                "commence_time": commence_dt,
            }
        )

    for key in by_pair:
        by_pair[key].sort(key=lambda item: item["commence_time"])

    _SIGNAL_HISTORY_CACHE = by_pair
    return _SIGNAL_HISTORY_CACHE


def _pair_key(team_a: str, team_b: str) -> Tuple[str, str]:
    return tuple(sorted((team_a.strip().lower(), team_b.strip().lower())))


def _to_utc(value: Union[datetime, str, None]) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_actionable(edges: List[EdgeAnalysis]) -> List[EdgeAnalysis]:
    """Return only edges with signal STRONG BET or BET."""
    return [e for e in edges if e.actionable]


def rank_by_edge(edges: List[EdgeAnalysis]) -> List[EdgeAnalysis]:
    """Sort edges descending by edge_pp (highest alpha first)."""
    return sorted(edges, key=lambda x: x.edge_pp, reverse=True)
