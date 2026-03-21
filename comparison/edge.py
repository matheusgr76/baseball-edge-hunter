"""
Comparison Layer - Edge Detection
Calculate edge per outcome and assign 5-tier signal.
EdgeAnalysis is per-outcome (two per game: home + away).
"""

from typing import List, Tuple
from datetime import datetime
from models import CanonicalGame, PolymarketOpportunity, EdgeAnalysis
import config


def calculate_edge(
    canonical: CanonicalGame,
    poly_home: PolymarketOpportunity,
    poly_away: PolymarketOpportunity,
) -> List[EdgeAnalysis]:
    """
    Calculate edge for both outcomes of a game.

    In Phase 1, true_prob == consensus_prob (no calibration yet).
    Phase 2 will pass a CalibratedGame with adjusted true probs.

    Returns:
        [home_edge, away_edge] — always two EdgeAnalysis objects.
    """
    home_edge = _single_edge(
        game_id=canonical.game_id,
        team="home",
        team_name=canonical.home_team,
        opponent=canonical.away_team,
        commence_time=canonical.commence_time,
        consensus_prob=canonical.home_prob,
        true_prob=canonical.home_prob,   # Phase 1: no calibration
        poly=poly_home,
        num_bookmakers=canonical.num_bookmakers,
    )
    away_edge = _single_edge(
        game_id=canonical.game_id,
        team="away",
        team_name=canonical.away_team,
        opponent=canonical.home_team,
        commence_time=canonical.commence_time,
        consensus_prob=canonical.away_prob,
        true_prob=canonical.away_prob,   # Phase 1: no calibration
        poly=poly_away,
        num_bookmakers=canonical.num_bookmakers,
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
) -> EdgeAnalysis:
    edge_pp = round(true_prob - poly.polymarket_prob, 2)
    confidence_pct = _confidence(edge_pp, num_bookmakers)
    signal = _assign_signal(edge_pp, confidence_pct)
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
        polymarket_condition_id=poly.condition_id,
        polymarket_question=poly.question,
        polymarket_liquidity=poly.liquidity,
        timestamp=datetime.now(),
    )


def _assign_signal(edge_pp: float, confidence_pct: int) -> str:
    """
    Assign 5-tier signal based on edge and confidence.

    Tiers (from CLAUDE.md):
        STRONG BET  — edge >= 3.0pp AND confidence >= 80%
        BET         — edge >= 2.5pp AND confidence >= 70%
        SKIP        — edge in [-1.0, 2.5)   (insufficient or no edge)
        FADE        — edge in [-3.0, -1.0)  (market overpriced on Polymarket)
        AVOID       — edge < -3.0           (strong negative edge)
    """
    if edge_pp >= config.STRONG_BET_EDGE_PP and confidence_pct >= config.STRONG_BET_CONF_PCT:
        return "STRONG BET"
    if edge_pp >= config.BET_EDGE_PP and confidence_pct >= config.BET_CONF_PCT:
        return "BET"
    if edge_pp < config.AVOID_THRESHOLD_PP:
        return "AVOID"
    if edge_pp < config.FADE_MIN_PP:
        return "FADE"
    return "SKIP"


def _confidence(edge_pp: float, num_bookmakers: int) -> int:
    """
    Derive confidence percentage from edge magnitude and bookmaker count.

    Bookmaker count increases confidence (more data = more reliable consensus).
    Edge magnitude also boosts confidence.
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

    return min(base, 95)


def filter_actionable(edges: List[EdgeAnalysis]) -> List[EdgeAnalysis]:
    """Return only edges with signal STRONG BET or BET."""
    return [e for e in edges if e.actionable]


def rank_by_edge(edges: List[EdgeAnalysis]) -> List[EdgeAnalysis]:
    """Sort edges descending by edge_pp (highest alpha first)."""
    return sorted(edges, key=lambda x: x.edge_pp, reverse=True)
