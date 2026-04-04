"""
Orchestration Layer - Pipeline
Entry point: run_pipeline()
Flow: Bookmakers → Consensus → Calibration → Polymarket (gatekeeper) → Edge → Report + CSV
"""

import time
from datetime import datetime
from typing import List

from ingestion.bookmakers import fetch_bookmaker_odds, get_unique_games
from ingestion.polymarket import get_polymarket_odds
from ingestion.mlb_data import fetch_probable_pitchers, fetch_bullpen_status, fetch_lineup_status
from normalization.devig import calculate_consensus
from normalization.teams import normalize_team_name
from calibration.factors import calibrate_game
from comparison.edge import calculate_edge, rank_by_edge
from output.report_formatter import (
    print_session_header,
    print_game_section,
    print_session_summary,
    export_csv,
    save_daily_report,
)
from output.clv_tracker import (
    log_signals,
    print_clv_summary,
    print_weekly_summary,
    print_pnl_chart,
)
from models import EdgeAnalysis, PipelineResult
import config


def run_pipeline() -> PipelineResult:
    """
    Run the full MLB edge detection pipeline for today's games.

    Returns:
        PipelineResult with all edges and diagnostics.
    """
    start_time = time.time()
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")

    print_session_header()

    errors: List[str] = []
    warnings: List[str] = []
    all_edges: List[EdgeAnalysis] = []
    games_analyzed = 0
    polymarket_markets_found = 0

    # ── Step 1: Fetch bookmaker odds ─────────────────────────────────────────
    print()
    raw_odds = fetch_bookmaker_odds()

    if not raw_odds:
        print("  ⚠️  No bookmaker odds returned — check API key or season status.")
        _print_no_edges()
        return _empty_result(timestamp, start_time, errors, warnings)

    unique_games = get_unique_games(raw_odds)
    print(f"  📋 {len(unique_games)} unique games found in bookmaker data")

    # ── Step 2: Fetch MLB calibration data (SP + bullpen + lineups) ─────────
    print()
    print("  🔍 Fetching MLB calibration data...")
    probable_pitchers = fetch_probable_pitchers(date_str)
    print(f"  ✓ Probable pitchers: {len(probable_pitchers)} teams with data")
    lineup_status = fetch_lineup_status(date_str)
    confirmed_count = sum(1 for v in lineup_status.values() if v)
    print(f"  ✓ Lineup status: {confirmed_count}/{len(lineup_status)} games confirmed")

    # ── Step 3-6: Per-game processing ────────────────────────────────────────
    print()
    for home_team_raw, away_team_raw, commence_time in unique_games:
        home_canonical = normalize_team_name(home_team_raw)
        away_canonical = normalize_team_name(away_team_raw)

        try:
            # Step 3: Build devigged consensus
            game_odds = [
                o for o in raw_odds
                if o.home_team == home_team_raw and o.away_team == away_team_raw
            ]
            canonical = calculate_consensus(
                home_canonical, away_canonical, commence_time, game_odds
            )

            if canonical.num_bookmakers < config.MIN_BOOKMAKERS:
                warnings.append(
                    f"Low bookmaker count ({canonical.num_bookmakers}) for "
                    f"{away_canonical} @ {home_canonical} — skipping"
                )
                continue

            # Step 4: Calibrate (SP + bullpen factors)
            home_sp = probable_pitchers.get(home_canonical)
            away_sp = probable_pitchers.get(away_canonical)
            home_bp = fetch_bullpen_status(home_canonical, date_str)
            away_bp = fetch_bullpen_status(away_canonical, date_str)

            calibrated = calibrate_game(
                canonical,
                home_sp=home_sp,
                away_sp=away_sp,
                home_bp=home_bp,
                away_bp=away_bp,
            )

            # Step 4b: Lineup confirmation warning
            lineup_confirmed = lineup_status.get((home_canonical, away_canonical))
            if lineup_confirmed is False:
                msg = (
                    f"  ⚠️  LINEUP NOT CONFIRMED: {away_canonical} @ {home_canonical} "
                    "— verify before acting on any signal"
                )
                print(msg)
                warnings.append(msg.strip())

            # Step 5: Polymarket gatekeeper
            result = get_polymarket_odds(
                away_canonical, home_canonical, commence_time, canonical.game_id
            )

            if result is None:
                # No Polymarket market — game does not enter pipeline (hard rule)
                continue

            poly_home, poly_away = result
            polymarket_markets_found += 1
            games_analyzed += 1

            # Step 6: Calculate edge (per outcome, using calibrated true probs)
            edges = calculate_edge(calibrated, poly_home, poly_away)
            all_edges.extend(edges)

            # Per-game terminal report
            print_game_section(
                away_team=away_canonical,
                home_team=home_canonical,
                home_edge=edges[0],
                away_edge=edges[1],
            )

        except Exception as e:
            msg = f"Error processing {away_canonical} @ {home_canonical}: {e}"
            errors.append(msg)
            print(f"  ⚠️  {msg}")
            continue

    # ── Step 7: Summary output ───────────────────────────────────────────────
    ranked_edges = rank_by_edge(all_edges)
    print_session_summary(ranked_edges)

    # ── Step 7b: Persist daily report ────────────────────────────────────────
    save_daily_report(ranked_edges, config.OUTPUT_DIRECTORY)

    # ── Step 8: CLV logging ──────────────────────────────────────────────────
    new_logged = log_signals(ranked_edges)
    if new_logged:
        print(f"  📝 CLV tracker: {new_logged} new signal(s) logged → output/predictions_log.json")

    # ── Step 9: CSV export ───────────────────────────────────────────────────
    if ranked_edges:
        export_csv(ranked_edges, config.OUTPUT_DIRECTORY)

    # ── Step 10: CLV running summary + weekly + P&L chart ────────────────────
    print_clv_summary()
    print_weekly_summary()
    print_pnl_chart()

    elapsed = round(time.time() - start_time, 2)
    actionable_count = sum(1 for e in ranked_edges if e.actionable)

    print(
        f"  ✅ Pipeline complete in {elapsed}s — "
        f"{games_analyzed} games | {polymarket_markets_found} Polymarket markets | "
        f"{actionable_count} actionable edges"
    )

    return PipelineResult(
        timestamp=timestamp,
        games_analyzed=games_analyzed,
        polymarket_markets_found=polymarket_markets_found,
        edges_detected=actionable_count,
        edges=ranked_edges,
        errors=errors,
        warnings=warnings,
        execution_time_seconds=elapsed,
    )


def _print_no_edges() -> None:
    from output.report_formatter import print_session_header
    print()
    print("  ⏳ No actionable edges today — no bookmaker data returned.")
    print()


def _empty_result(
    timestamp: datetime,
    start_time: float,
    errors: List[str],
    warnings: List[str],
) -> PipelineResult:
    elapsed = round(time.time() - start_time, 2)
    return PipelineResult(
        timestamp=timestamp,
        games_analyzed=0,
        polymarket_markets_found=0,
        edges_detected=0,
        edges=[],
        errors=errors,
        warnings=warnings,
        execution_time_seconds=elapsed,
    )
