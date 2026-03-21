"""
MLB Edge Hunter - Data Models
Type-safe dataclasses for all pipeline layers
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


# ============================================================================
# RAW DATA MODELS (Ingestion Layer)
# ============================================================================

@dataclass
class FactorResult:
    """Single factor evaluation result (Phase 2+ use)"""
    name: str
    result: float         # Signed percentage points
    explanation: str
    devil: float          # Devil's advocate adjustment
    devil_advocate: str


@dataclass
class RawBookmakerOdds:
    """Raw odds from a single bookmaker for one game"""
    bookmaker: str
    home_team: str        # Raw name from The Odds API
    away_team: str
    home_odds: int        # American odds (e.g. -150, +130)
    away_odds: int
    timestamp: datetime
    sport_key: str        # "baseball_mlb"
    commence_time: datetime


@dataclass
class RawPolymarketMarket:
    """Raw market data from Polymarket Gamma API"""
    condition_id: str
    question: str
    outcomes: List[str]           # Team names or Yes/No
    outcome_prices: List[float]   # Share prices (0-1 scale)
    end_date: datetime
    volume: float
    liquidity: float
    market_slug: str


# ============================================================================
# NORMALIZED DATA MODELS (Normalization Layer)
# ============================================================================

@dataclass
class CanonicalGame:
    """Normalized game with devigged consensus probabilities"""
    game_id: str
    home_team: str        # Canonical team name
    away_team: str
    commence_time: datetime

    # Devigged consensus probabilities (0-100 scale)
    home_prob: float
    away_prob: float

    favorite: str         # "home" or "away"
    num_bookmakers: int
    raw_sources: List[RawBookmakerOdds]


@dataclass
class PolymarketOpportunity:
    """Matched Polymarket contract for one team outcome"""
    game_id: str
    condition_id: str
    question: str

    team: str             # "home" or "away"
    team_name: str

    polymarket_prob: float   # 0-100 scale

    end_date: datetime
    volume: float
    liquidity: float
    market_slug: str


# ============================================================================
# COMPARISON DATA MODELS (Comparison Layer)
# ============================================================================

@dataclass
class EdgeAnalysis:
    """Final edge calculation for one betting outcome (per team)"""
    game_id: str
    team: str             # "home" or "away"
    team_name: str
    opponent: str
    commence_time: datetime

    # Probabilities (0-100 scale)
    consensus_prob: float     # Devigged bookmaker consensus
    true_prob: float          # == consensus_prob in Phase 1; calibrated in Phase 2+
    polymarket_prob: float

    # Edge metric (percentage points, signed)
    edge_pp: float            # true_prob - polymarket_prob

    # Signal classification (5-tier)
    signal: str               # "STRONG BET" | "BET" | "SKIP" | "FADE" | "AVOID"
    confidence_pct: int       # 0-100
    actionable: bool          # True for STRONG BET and BET only

    # Metadata
    polymarket_condition_id: str
    polymarket_question: str
    polymarket_liquidity: float
    timestamp: datetime


# ============================================================================
# OUTPUT MODEL (Orchestration Layer)
# ============================================================================

@dataclass
class PipelineResult:
    """Complete pipeline execution result"""
    timestamp: datetime
    games_analyzed: int
    polymarket_markets_found: int
    edges_detected: int

    edges: List[EdgeAnalysis]

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0
