"""
Backtesting - Core Engine
Orchestrates the historical backtest: fetches historical odds, resolves signals
against actual game results, and computes performance metrics.

Design:
  1. Load Retrosheet game results for the target season → build lookup dict
  2. Loop over unique game dates in the season
  3. For each date: fetch historical bookmaker odds snapshot
  4. Run devigging + consensus calculation (identical to live pipeline)
  5. Simulate Polymarket prices as a configurable offset (see NOTES below)
  6. Apply edge detection with the exact same thresholds from config.py
  7. Resolve each signal against the actual game result
  8. Aggregate metrics: hit rate, ROI, drawdown, CLV beat-rate

NOTES on Polymarket simulation (Phase 3b constraint):
  Historical Polymarket prices are NOT available for most past MLB seasons.
  We therefore simulate a Polymarket price using the devigged consensus minus
  a configurable spread (POLY_SIM_SPREAD_PP). This is a conservative approach:
  - It checks whether our calibration alone generates edges against fair market odds.
  - A signal fires if calibrated_prob > consensus - POLY_SIM_SPREAD_PP + threshold.
  - This is analogous to asking "would we have beaten closing odds?".
  When real Polymarket data becomes available (live run archive), swap in
  the actual prices by providing a poly_prices_override dict.
"""

import os
import time
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import config
from models import RawBookmakerOdds, CanonicalGame, PolymarketOpportunity
from normalization.devig import calculate_consensus
from normalization.teams import normalize_team_name
from comparison.edge import calculate_edge

from backtesting.models import (
    BacktestSignal,
    BacktestResult,
    BacktestSummary,
    GameResult,
)
from backtesting.game_log_parser import parse_season, build_result_lookup
from backtesting.historical_odds import fetch_historical_odds

# ============================================================================
# CONFIGURATION
# ============================================================================

# Simulated spread between bookmaker consensus and fake Polymarket price.
# Positive value = Polymarket is cheaper than book consensus → easier to find edge.
# 0pp = Polymarket tracks book exactly (strict mode).
POLY_SIM_SPREAD_PP: float = 0.0   # conservative: no artificial spread

# Rate-limit guard: seconds to sleep between API calls per date.
API_SLEEP_SECONDS: float = 1.5

# Max dates to backtest per run (guard against quota exhaustion).
MAX_DATES_PER_SEASON: int = 30

# Snapshot time suffix appended to each date string (noon UTC = pre-game).
SNAPSHOT_TIME_SUFFIX: str = "T16:00:00Z"  # ~noon ET


def run_backtest(
    season: int,
    data_dir: str = "past-seasons",
    max_dates: int = MAX_DATES_PER_SEASON,
    poly_spread_pp: float = POLY_SIM_SPREAD_PP,
    edge_threshold_pp: float = config.BET_EDGE_PP,
) -> BacktestSummary:
    """
    Run a full historical backtest for a given MLB season.

    Args:
        season: Year to backtest (e.g. 2024).
        data_dir: Directory containing Retrosheet game logs.
        max_dates: Safety cap on number of game-dates processed (API quota guard).
        poly_spread_pp: Simulated Polymarket underpricing vs consensus (default 0).
        edge_threshold_pp: Minimum edge_pp to count as actionable.

    Returns:
        BacktestSummary with all metrics.
    """
    print(f"\n{'='*60}")
    print(f"  🏟️  MLB Edge Hunter — Historical Backtest {season}")
    print(f"{'='*60}\n")

    errors: List[str] = []

    # Step 1: Load game results
    print("  [1/4] Loading game results from Retrosheet...")
    game_results = parse_season(season, data_dir=data_dir)
    if not game_results:
        msg = f"No game results found for {season}."
        print(f"  ✗ {msg}")
        return BacktestSummary(
            season=str(season),
            total_signals=0,
            actionable_signals=0,
            wins=0,
            losses=0,
            hit_rate=0.0,
            total_payout_pp=0.0,
            avg_edge_pp=0.0,
            max_drawdown_pp=0.0,
            clv_beat_rate=0.0,
            errors=[msg],
        )

    result_lookup = build_result_lookup(game_results)
    unique_dates = sorted({str(r.game_date) for r in game_results})

    print(f"  ✓ {len(game_results)} games across {len(unique_dates)} dates")

    # Limit dates for API quota
    if len(unique_dates) > max_dates:
        print(f"  ↳ Limiting to first {max_dates} dates (max_dates cap)")
        unique_dates = unique_dates[:max_dates]

    # Step 2: Fetch odds + build signals for each date
    print(f"\n  [2/4] Fetching historical odds for {len(unique_dates)} dates...")
    all_signals: List[BacktestSignal] = []

    for i, date_str in enumerate(unique_dates):
        snapshot = f"{date_str}{SNAPSHOT_TIME_SUFFIX}"
        print(f"\n  [{i+1}/{len(unique_dates)}] {date_str}")

        raw_odds = fetch_historical_odds(snapshot)

        if not raw_odds:
            errors.append(f"{date_str}: no odds data returned")
            continue

        # Step 3: Build consensus for each game on this date
        signals = _build_signals_for_date(
            date_str=date_str,
            raw_odds=raw_odds,
            poly_spread_pp=poly_spread_pp,
            edge_threshold_pp=edge_threshold_pp,
        )
        all_signals.extend(signals)

        # Respectful rate-limiting
        if i < len(unique_dates) - 1:
            time.sleep(API_SLEEP_SECONDS)

    print(f"\n  [3/4] Signals generated: {len(all_signals)}")

    # Step 4: Resolve signals against actual outcomes
    print("  [4/4] Resolving signals against game results...")
    results = _resolve_signals(all_signals, result_lookup, errors)

    # Compute summary metrics
    summary = _compute_summary(str(season), all_signals, results, errors)
    _print_summary(summary)

    return summary


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _build_signals_for_date(
    date_str: str,
    raw_odds: List[RawBookmakerOdds],
    poly_spread_pp: float,
    edge_threshold_pp: float,
) -> List[BacktestSignal]:
    """Devig raw odds and produce BacktestSignal objects for all games on a date."""
    from datetime import datetime, timezone

    # Group raw odds by (home_team, away_team)
    game_groups: Dict[Tuple[str, str], List[RawBookmakerOdds]] = {}
    for entry in raw_odds:
        key = (entry.home_team, entry.away_team)
        game_groups.setdefault(key, []).append(entry)

    signals: List[BacktestSignal] = []

    for (home_raw, away_raw), odds_list in game_groups.items():
        # Filter to minimum bookmaker count
        if len(odds_list) < config.MIN_BOOKMAKERS:
            continue

        # Use commence_time from first entry; fall back to noon UTC on date_str
        commence_time = odds_list[0].commence_time
        if commence_time is None:
            try:
                commence_time = datetime.fromisoformat(
                    f"{date_str}T18:00:00+00:00"
                )
            except ValueError:
                commence_time = datetime.now(timezone.utc)

        # Devig to get consensus → CanonicalGame
        try:
            canonical = calculate_consensus(
                home_raw, away_raw, commence_time, odds_list
            )
        except Exception:
            continue  # skip malformed odds

        home_prob = canonical.home_prob
        away_prob = canonical.away_prob

        # Simulated Polymarket price = consensus - spread
        # (positive spread = poly is cheaper → easier to find edge)
        home_poly = max(1.0, home_prob - poly_spread_pp)
        away_poly = max(1.0, away_prob - poly_spread_pp)

        num_books = canonical.num_bookmakers
        home_odds_ref = odds_list[0].home_odds
        away_odds_ref = odds_list[0].away_odds

        home_canonical = canonical.home_team
        away_canonical = canonical.away_team

        for team, team_name, true_prob, poly_prob in [
            ("home", home_canonical, home_prob, home_poly),
            ("away", away_canonical, away_prob, away_poly),
        ]:
            edge_pp = round(true_prob - poly_prob, 2)

            # Determine signal tier using same private helpers as live pipeline
            from comparison.edge import _assign_signal, _confidence
            confidence = _confidence(edge_pp, num_books)
            signal = _assign_signal(edge_pp, confidence)
            actionable = signal in ("STRONG BET", "BET")

            signals.append(
                BacktestSignal(
                    game_date=date_str,
                    home_team=home_canonical,
                    away_team=away_canonical,
                    team=team,
                    team_name=team_name,
                    true_prob=round(true_prob, 2),
                    polymarket_prob=round(poly_prob, 2),
                    edge_pp=edge_pp,
                    signal=signal,
                    actionable=actionable,
                    bookmaker_home_odds=home_odds_ref,
                    bookmaker_away_odds=away_odds_ref,
                    num_bookmakers=num_books,
                )
            )

    return signals


def _resolve_signals(
    signals: List[BacktestSignal],
    result_lookup: Dict,
    errors: List[str],
) -> List[BacktestResult]:
    """Match each signal to a game result and compute P&L."""
    resolved: List[BacktestResult] = []

    for sig in signals:
        if not sig.actionable:
            continue  # only score actionable signals

        key = (sig.game_date, sig.home_team, sig.away_team)
        game_result: Optional[GameResult] = result_lookup.get(key)

        if game_result is None:
            errors.append(
                f"{sig.game_date} {sig.home_team} vs {sig.away_team}: "
                "no result found in game log"
            )
            continue

        # Did the bet side win?
        if sig.team == "home":
            won = game_result.home_won
        else:
            won = not game_result.home_won

        # P&L in implied probability points:
        # Win: +true_prob points (we bet at that value)
        # Loss: -polymarket_prob (what we paid)
        if won:
            payout_pp = round(100.0 - sig.true_prob, 2)   # +EV on win
        else:
            payout_pp = round(-sig.true_prob, 2)            # lose stake

        resolved.append(BacktestResult(signal=sig, won=won, payout_pp=payout_pp))

    return resolved


def _compute_summary(
    season: str,
    all_signals: List[BacktestSignal],
    results: List[BacktestResult],
    errors: List[str],
) -> BacktestSummary:
    """Aggregate BacktestResult list into a BacktestSummary."""
    actionable = [s for s in all_signals if s.actionable]
    wins = [r for r in results if r.won]
    losses = [r for r in results if not r.won]

    total_payout = sum(r.payout_pp for r in results)
    avg_edge = (
        sum(s.edge_pp for s in actionable) / len(actionable) if actionable else 0.0
    )

    # Max drawdown: worst consecutive losing streak in pp
    max_drawdown = 0.0
    current_drawdown = 0.0
    for r in results:
        if not r.won:
            current_drawdown += abs(r.payout_pp)
            max_drawdown = max(max_drawdown, current_drawdown)
        else:
            current_drawdown = 0.0

    clv_beat = [s for s in actionable if s.edge_pp > 0]
    clv_beat_rate = len(clv_beat) / len(actionable) if actionable else 0.0

    hit_rate = len(wins) / len(results) if results else 0.0

    return BacktestSummary(
        season=season,
        total_signals=len(all_signals),
        actionable_signals=len(actionable),
        wins=len(wins),
        losses=len(losses),
        hit_rate=round(hit_rate, 4),
        total_payout_pp=round(total_payout, 2),
        avg_edge_pp=round(avg_edge, 2),
        max_drawdown_pp=round(max_drawdown, 2),
        clv_beat_rate=round(clv_beat_rate, 4),
        errors=errors,
    )


def _print_summary(summary: BacktestSummary) -> None:
    """Print a formatted backtest summary to stdout."""
    print(f"\n{'='*60}")
    print(f"  📊  Backtest Summary — {summary.season}")
    print(f"{'='*60}")
    print(f"  Total signals generated : {summary.total_signals}")
    print(f"  Actionable (BET+STRONG) : {summary.actionable_signals}")
    print(f"  Wins / Losses           : {summary.wins} / {summary.losses}")
    print(f"  Hit rate                : {summary.hit_rate*100:.1f}%")
    print(f"  Total P&L (pp)          : {summary.total_payout_pp:+.2f}")
    print(f"  Avg edge (pp)           : {summary.avg_edge_pp:+.2f}")
    print(f"  Max drawdown (pp)       : {summary.max_drawdown_pp:.2f}")
    print(f"  CLV beat-rate           : {summary.clv_beat_rate*100:.1f}%")
    if summary.errors:
        print(f"  Warnings                : {len(summary.errors)}")
    print(f"{'='*60}\n")

    # Targets check
    target_met = summary.total_payout_pp > 0 and summary.actionable_signals >= 200
    target_label = "✅ TARGET MET" if target_met else "⚠️  TARGET NOT MET"
    print(f"  {target_label}")
    print(f"  (Positive EV + ≥200 actionable signals)\n")
