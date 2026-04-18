"""
MLB Edge Hunter - Data Models
Type-safe dataclasses for all pipeline layers
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
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
    bookmaker_std_pp: float = 0.0   # Std dev of devigged home probs across books (pp)
    raw_sources: List[RawBookmakerOdds] = field(default_factory=list)


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
# CALIBRATION DATA MODELS (Calibration Layer)
# ============================================================================

@dataclass
class ProbablePitcher:
    """Starting pitcher data for one team"""
    team: str            # Canonical team name
    name: str
    player_id: int
    fip: float           # Calculated from MLB Stats API components
    era: float           # Season ERA (fallback when IP too low)
    ip: float            # Innings pitched (season)
    hand: str            # "L" or "R"
    valid: bool = True   # False if sample too small (< 15 IP)


@dataclass
class BullpenStatus:
    """Recent bullpen usage for one team"""
    team: str
    pitches_last_48h: int    # Top-2 relievers combined pitches in last 48h
    fatigue_level: str       # "fresh" | "moderate" | "heavy"
    details: str             # Human-readable summary for output


@dataclass
class AdjustmentBreakdown:
    """Per-factor calibration adjustments for one team"""
    sp_quality: float = 0.0
    bullpen: float = 0.0
    park_factor: float = 0.0
    wrc_handedness: float = 0.0
    pythagorean_regression: float = 0.0
    oaa_defense: float = 0.0
    umpire_tendency: float = 0.0
    total: float = 0.0
    capped: bool = False     # True if total hit ±8pp hard cap


@dataclass
class CalibratedGame:
    """Game with true probabilities after situational calibration"""
    game_id: str
    home_team: str
    away_team: str
    commence_time: datetime

    # Original consensus (pre-calibration)
    consensus_home_prob: float
    consensus_away_prob: float

    # Calibrated "true" probabilities
    true_home_prob: float
    true_away_prob: float

    # Per-team adjustment breakdown
    home_adjustments: AdjustmentBreakdown
    away_adjustments: AdjustmentBreakdown

    # Factor rows for report output
    home_factors: List[FactorResult] = field(default_factory=list)
    away_factors: List[FactorResult] = field(default_factory=list)

    favorite: str = "home"

    # Carried from CanonicalGame for confidence calculation in edge.py
    num_bookmakers: int = 0
    bookmaker_std_pp: float = 0.0   # Std dev of devigged probs across books


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

    # Factor rows (for report_formatter)
    factors: List[FactorResult] = field(default_factory=list)

    # Metadata
    polymarket_condition_id: str = ""
    polymarket_question: str = ""
    polymarket_liquidity: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


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
    telegram_sent: Optional[bool] = None
