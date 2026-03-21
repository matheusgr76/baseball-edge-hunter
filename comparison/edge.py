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
        num_bookmakers = 0  # not carried on CalibratedGame; use 3 as default
    else:
        home_consensus = away_consensus = 0.0  # unused in Phase 1
        home_true = game.home_prob
        away_true = game.away_prob
        home_consensus = game.home_prob
        away_consensus = game.away_prob
        home_factors = []
        away_factors = []
        num_bookmakers = game.num_bookmakers

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
        factors=factors or [],
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
