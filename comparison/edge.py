"""
Comparison Layer - Edge Detection
Calculate edge per outcome and assign 5-tier signal.
EdgeAnalysis is per-outcome (two per game: home + away).
Accepts CanonicalGame (Phase 1) or CalibratedGame (Phase 2+).
"""

from typing import List, Union
from datetime import datetime
from models import CanonicalGame, CalibratedGame, PolymarketOpportunity, EdgeAnalysis
import config


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
        STRONG BET  — edge >= 3.0pp AND confidence >= 80%
        BET         — edge >= 2.5pp AND confidence >= 70%
        SKIP        — edge in [-1.0, 2.5)   (insufficient or no edge)
        FADE        — edge in [-3.0, -1.0)  (market overpriced on Polymarket)
        AVOID       — edge < -3.0           (strong negative edge)

    Edge-floor guards (proactive, from basketball 19W/5L analysis):
        Moderate favorite band (55-65%): requires >= 3.5pp edge
        High confidence zone (>65%): requires >= 5.0pp edge
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
        1. Base: 50
        2. Bookmaker count bonus: +6/+12/+20 (more books = sharper consensus)
        3. Edge magnitude bonus: +3/+6/+10/+15
        4. Factor agreement: +5 if SP & bullpen agree, -5 if they conflict
        5. Data completeness: -5 per missing factor (SP or bullpen)
        6. Bookmaker variance: -5 if std dev > 3pp (books disagree on price)

    Capped at 95% — no model is perfect.
    """
    base = 50

    # Bookmaker count bonus
    if num_bookmakers >= 5:
        base += 20
    elif num_bookmakers >= 3:
        base += 12
    elif num_bookmakers >= 2:
        base += 6

    # Edge magnitude bonus
    abs_edge = abs(edge_pp)
    if abs_edge >= 5.0:
        base += 15
    elif abs_edge >= 3.0:
        base += 10
    elif abs_edge >= 2.0:
        base += 6
    elif abs_edge >= 1.0:
        base += 3

    # Factor agreement + data completeness (requires factors list)
    if factors:
        nonzero_factors = [f for f in factors if f.result != 0.0]
        missing_count = len(factors) - len(nonzero_factors)

        # Data completeness penalty: -5 per missing factor
        base -= missing_count * 5

        # Factor agreement: do all nonzero factors point the same direction?
        if len(nonzero_factors) >= 2:
            positive = sum(1 for f in nonzero_factors if f.result > 0)
            negative = len(nonzero_factors) - positive
            if positive == len(nonzero_factors) or negative == len(nonzero_factors):
                base += 5   # All factors agree → boost
            else:
                base -= 5   # Factors conflict → penalty

    # Bookmaker variance penalty: books disagree on the true price
    if bm_std_pp > 3.0:
        base -= 5

    return max(40, min(base, 95))


def filter_actionable(edges: List[EdgeAnalysis]) -> List[EdgeAnalysis]:
    """Return only edges with signal STRONG BET or BET."""
    return [e for e in edges if e.actionable]


def rank_by_edge(edges: List[EdgeAnalysis]) -> List[EdgeAnalysis]:
    """Sort edges descending by edge_pp (highest alpha first)."""
    return sorted(edges, key=lambda x: x.edge_pp, reverse=True)
