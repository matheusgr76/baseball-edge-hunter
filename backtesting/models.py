"""
Backtesting - Data Models
Dataclasses specific to the historical backtest workflow.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date


@dataclass
class GameResult:
    """
    Actual outcome of a historical MLB game.
    Sourced from Retrosheet Game Logs (past-seasons/glYYYY.txt).
    """
    game_date: date          # YYYY-MM-DD
    home_team_code: str      # Retrosheet 3-char code e.g. "NYA"
    away_team_code: str
    home_runs: int
    away_runs: int
    home_won: bool           # True if home team won


@dataclass
class BacktestSignal:
    """
    A synthetic EdgeAnalysis produced from historical data.
    Mirrors EdgeAnalysis fields but stripped to what we can replay.
    """
    game_date: str           # YYYY-MM-DD string
    home_team: str           # Canonical name
    away_team: str
    team: str                # "home" or "away"
    team_name: str           # Canonical name of bet target
    true_prob: float         # Devigged bookmaker consensus (0-100)
    polymarket_prob: float   # Simulated Polymarket price (0-100)
    edge_pp: float           # true_prob - polymarket_prob
    signal: str              # "STRONG BET" | "BET" | "SKIP" | "FADE" | "AVOID"
    actionable: bool
    bookmaker_home_odds: int  # Raw American odds used in backtest
    bookmaker_away_odds: int
    num_bookmakers: int


@dataclass
class BacktestResult:
    """
    Resolved backtest record — signal + actual outcome.
    """
    signal: BacktestSignal
    won: bool                # Did the bet team actually win?
    payout_pp: float         # Raw PnL in implied probability points
    # ROI% = payout_pp / abs(stake) — normalised later at summary level

    @property
    def game_date(self) -> str:
        return self.signal.game_date

    @property
    def team_name(self) -> str:
        return self.signal.team_name

    @property
    def edge_pp(self) -> float:
        return self.signal.edge_pp

    @property
    def signal_tier(self) -> str:
        return self.signal.signal


@dataclass
class BacktestSummary:
    """
    Aggregate statistics for a completed backtest run.
    """
    season: str                     # e.g. "2024"
    total_signals: int
    actionable_signals: int         # BET + STRONG BET only
    wins: int
    losses: int
    hit_rate: float                 # wins / actionable_signals (0-1)
    total_payout_pp: float          # cumulative PnL in pp units
    avg_edge_pp: float              # mean edge across actionable signals
    max_drawdown_pp: float          # worst consecutive pp loss streak
    clv_beat_rate: float            # fraction of signals where edge_pp > 0
    errors: list = field(default_factory=list)
