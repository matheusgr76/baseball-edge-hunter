"""
MLB Edge Hunter - Report Formatter
Terminal output + CSV export matching basketball_edge_hunter format exactly.
Sport emoji: ⚾  |  Signal column: SIGNAL  |  Summary title: ANALYSIS SUMMARY
"""

import csv
import os
from datetime import datetime
from typing import Dict, List

from models import EdgeAnalysis, FactorResult


# ── Signal display ──────────────────────────────────────────────────────────

_SIGNAL_EMOJI = {
    "STRONG BET": "🔥 Strong Bet",
    "BET":        "✅ Bet",
    "SKIP":       "⏭️  Skip",
    "FADE":       "👎 Fade",
    "AVOID":      "🚫 AVOID",
}

_SIGNAL_LEGEND = (
    "Signal legend: 🔥 Strong Bet (≥3.0pp+conf≥80%) | ✅ Bet (≥2.5pp+conf≥70%) | "
    "⏭️ Skip (<2.5pp) | 👎 Fade (-1 to -3pp) | 🚫 AVOID (<-3pp)"
)

_VERDICT_ICON = {
    "STRONG BET": "🔥",
    "BET":        "✅",
    "SKIP":       "🔶",
    "FADE":       "🔄",
    "AVOID":      "⛔️",
}

# Phase 1 placeholder factor (no calibration yet)
_PLACEHOLDER_FACTOR = FactorResult(
    name="CONSENSUS MODEL",
    result=0.0,
    explanation="Devigged bookmaker consensus — no calibration factors in Phase 1",
    devil=0.0,
    devil_advocate="Phase 2 will add SP quality, bullpen, weather, splits",
)


# ============================================================================
# SESSION HEADER
# ============================================================================

def print_session_header() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print("╔" + "═" * 108 + "╗")
    print("║" + "  ⚾  MLB EDGE HUNTER — MARKET COMPARISON ENGINE".center(108) + "║")
    print("║" + f"  Run: {now}".ljust(108) + "║")
    print("╚" + "═" * 108 + "╝")


# ============================================================================
# PER-GAME REPORT
# ============================================================================

def print_game_section(
    away_team: str,
    home_team: str,
    home_edge: EdgeAnalysis,
    away_edge: EdgeAnalysis,
) -> None:
    """Print the per-game factor table and probability summary."""
    game_label = f"{away_team} @ {home_team}"

    print()
    print("=" * 110)
    print(f"  ⚾ PROCESSING: {game_label}")
    print("=" * 110)
    print()

    # Determine favorite for header
    fav = home_team if home_edge.true_prob >= away_edge.true_prob else away_team
    dog = away_team if fav == home_team else home_team
    print(f"  ## ⚾ {fav} (Fav) vs {dog} (Dog)")
    print()

    # Factor table header
    print(
        f"  {'FACTOR':<35} | {'RESULT':>8} | {'EXPLANATION':<58} | {'DEVIL':>7} | DEVIL ADVOCATE"
    )
    print(f"  {'-'*35}-+-{'-'*8}-+-{'-'*58}-+-{'-'*7}-+-{'-'*45}")

    # Use favorite's factors if available, else placeholder
    fav_edge = home_edge if fav == home_team else away_edge
    factors_to_show = fav_edge.factors if fav_edge.factors else [_PLACEHOLDER_FACTOR]

    for f in factors_to_show:
        res_str = f"{f.result:>+7.2f}%"
        dev_str = f"{f.devil:>+6.2f}%"
        expl = f.explanation[:55] + "..." if len(f.explanation) > 58 else f.explanation
        da = f.devil_advocate[:42] + "..." if len(f.devil_advocate) > 45 else f.devil_advocate
        print(f"  {f.name:<35} | {res_str} | {expl:<58} | {dev_str} | {da}")

    # Probability summary
    fav_prob = home_edge.true_prob if fav == home_team else away_edge.true_prob
    fav_conf = home_edge.confidence_pct if fav == home_team else away_edge.confidence_pct
    fav_consensus = home_edge.consensus_prob if fav == home_team else away_edge.consensus_prob
    print()
    print(f"  📊 PROBABILITY SUMMARY")
    print(
        f"  Calculated Probability: {fav_prob:.1f}% "
        f"| Consensus: {fav_consensus:.1f}% "
        f"| Analysis Confidence: ({fav_conf}%)"
    )
    print()


# ============================================================================
# SESSION SUMMARY TABLE
# ============================================================================

def print_session_summary(all_edges: List[EdgeAnalysis]) -> None:
    """
    Print the final ANALYSIS SUMMARY table in the compact basketball-style format.
    One row per game, using the favorite-side analysis.
    """
    summary_rows = _build_summary_rows(all_edges)

    print()
    print("=" * 78)
    print("  📊 ANALYSIS SUMMARY")
    print("=" * 78)
    print()
    print(f"   {'GAME':<8} | {'FAV':<5} | {'T%':>2} | {'P%':>2} | {'C%':>2} | {'E':>5} | VERDICT")
    print(f"   {'-'*8}-+-{'-'*5}-+-{'-'*2}-+-{'-'*2}-+-{'-'*2}-+-{'-'*5}-+-{'-'*11}")

    actionable: List[Dict[str, object]] = []

    for row in summary_rows:
        print(
            f"{row['prefix']} {row['game']:<8} | {row['fav']:<5} | "
            f"{row['true_pct']:>2} | {row['poly_pct']:>2} | {row['conf_pct']:>2} | "
            f"{row['edge']:>+5.1f} | {row['verdict']:<10} {row['icon']}"
        )
        if row["signal"] in ("STRONG BET", "BET"):
            actionable.append(row)

    print()
    print("=" * 78)
    print()

    if actionable:
        print(f"  🎯 ACTIONABLE EDGES: {len(actionable)} found")
        for row in actionable:
            print(
                f"     {row['fav_full']} — Edge: {row['edge']:+.2f}pp "
                f"| T={row['true_pct']}% P={row['poly_pct']}% C={row['conf_pct']}% "
                f"→ {row['verdict']} {row['icon']}"
            )
    else:
        print("  ⏳ No actionable edges today...")
        print("     Markets appear efficient — wait for line movement or injury news.")

    print()
    print(f"  {_SIGNAL_LEGEND}")
    print()


# ============================================================================
# CSV EXPORT
# ============================================================================

def export_csv(all_edges: List[EdgeAnalysis], output_dir: str = "output") -> str:
    """
    Export per-outcome analysis to CSV.

    Structure per outcome:
        HEADER row  — game metadata
        FACTOR row  — one row (Phase 1 placeholder)
        SUMMARY row — edge metrics

    Followed by FINAL SUMMARY block at end of file.
    """
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"mlb_signals_{date_str}.csv")

    columns = [
        "ROW_TYPE", "GAME", "FAVORITE", "DOG",
        "FACTOR", "RESULT (%)", "EXPLANATION",
        "DEVIL (%)", "DEVIL ADVOCATE",
        "CALC_PROB (%)", "CONFIDENCE (%)", "WCS", "SIGNAL", "MARKET (%)", "EDGE (pp)",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)

        for e in all_edges:
            game = (
                f"{e.opponent} @ {e.team_name}"
                if e.team == "home"
                else f"{e.team_name} @ {e.opponent}"
            )
            fav = e.team_name if e.true_prob >= 50.0 else e.opponent
            dog = e.opponent if e.true_prob >= 50.0 else e.team_name
            wcs = round(e.true_prob - 8.0, 1)  # NOTE: WCS placeholder — not a real worst-case model

            # HEADER
            writer.writerow([
                "HEADER", game, fav, dog,
                "", "", "", "", "",
                f"{e.true_prob:.2f}", e.confidence_pct, wcs,
                e.signal, f"{e.polymarket_prob:.2f}", f"{e.edge_pp:+.2f}",
            ])

            # FACTOR rows (real calibration factors, or placeholder if none)
            factor_rows = e.factors if e.factors else [_PLACEHOLDER_FACTOR]
            for f_row in factor_rows:
                writer.writerow([
                    "FACTOR", game, fav, dog,
                    f_row.name, f"{f_row.result:.2f}", f_row.explanation,
                    f"{f_row.devil:.2f}", f_row.devil_advocate,
                    "", "", "", "", "", "",
                ])

            # SUMMARY
            writer.writerow([
                "SUMMARY", game, fav, dog,
                "PROBABILITY SUMMARY", "", "", "", "",
                f"{e.true_prob:.2f}", e.confidence_pct, wcs,
                e.signal, f"{e.polymarket_prob:.2f}", f"{e.edge_pp:+.2f}",
            ])

            # Blank separator
            writer.writerow([""] * 15)

        # ── FINAL SUMMARY block ──────────────────────────────────────────
        writer.writerow([""] * 15)
        writer.writerow([""] * 15)
        writer.writerow(["FINAL SUMMARY", "ALL GAMES"] + [""] * 13)
        writer.writerow([""] * 15)
        writer.writerow([
            "#", "GAME", "FAVORITE", "DOG",
            "CALC_PROB (%)", "CONFIDENCE (%)", "WCS",
            "MARKET (%)", "EDGE (pp)", "SIGNAL", "ACTIONABLE",
            "", "", "", "",
        ])

        for i, e in enumerate(all_edges, 1):
            game = (
                f"{e.opponent} @ {e.team_name}"
                if e.team == "home"
                else f"{e.team_name} @ {e.opponent}"
            )
            fav = e.team_name if e.true_prob >= 50.0 else e.opponent
            dog = e.opponent if e.true_prob >= 50.0 else e.team_name
            wcs = round(e.true_prob - 8.0, 1)  # NOTE: WCS placeholder — not a real worst-case model
            writer.writerow([
                i, game, fav, dog,
                f"{e.true_prob:.2f}", e.confidence_pct, wcs,
                f"{e.polymarket_prob:.2f}", f"{e.edge_pp:+.2f}",
                e.signal, "YES" if e.actionable else "no",
                "", "", "", "",
            ])

    print(f"  📁 CSV exported: {filepath}")
    return filepath


# ============================================================================
# DAILY REPORT PERSISTENCE
# ============================================================================

def save_daily_report(
    all_edges: List[EdgeAnalysis],
    output_dir: str = "output",
) -> str:
    """
    Persist today's analysis summary to output/daily_report_{date}.txt.
    Written even when all_edges is empty (records a no-edge day).
    Returns the file path written.
    """
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filepath = os.path.join(output_dir, f"daily_report_{date_str}.txt")

    summary_rows = _build_summary_rows(all_edges)

    lines = [
        "╔" + "═" * 108 + "╗",
        "║" + f"  ⚾  MLB EDGE HUNTER — DAILY SIGNAL REPORT  |  {now_str}".ljust(108) + "║",
        "╚" + "═" * 108 + "╝",
        "",
        "=" * 78,
        "  📊 ANALYSIS SUMMARY",
        "=" * 78,
        "",
        f"   {'GAME':<8} | {'FAV':<5} | {'T%':>2} | {'P%':>2} | {'C%':>2} | {'E':>5} | VERDICT",
        f"   {'-'*8}-+-{'-'*5}-+-{'-'*2}-+-{'-'*2}-+-{'-'*2}-+-{'-'*5}-+-{'-'*11}",
    ]

    actionable = []
    for row in summary_rows:
        lines.append(
            f"{row['prefix']} {row['game']:<8} | {row['fav']:<5} | "
            f"{row['true_pct']:>2} | {row['poly_pct']:>2} | {row['conf_pct']:>2} | "
            f"{row['edge']:>+5.1f} | {row['verdict']:<10} {row['icon']}"
        )
        if row["signal"] in ("STRONG BET", "BET"):
            actionable.append(row)

    lines += ["", "=" * 78, ""]

    if actionable:
        lines.append(f"  🎯 ACTIONABLE EDGES: {len(actionable)} found")
        for row in actionable:
            lines.append(
                f"     {row['fav_full']} — Edge: {row['edge']:+.2f}pp "
                f"| T={row['true_pct']}% P={row['poly_pct']}% C={row['conf_pct']}% "
                f"→ {row['verdict']} {row['icon']}"
            )
    else:
        lines.append("  ⏳ No actionable edges today...")

    lines += ["", f"  {_SIGNAL_LEGEND}", ""]

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"  📄 Daily report saved: {filepath}")
    return filepath


def _build_summary_rows(all_edges: List[EdgeAnalysis]) -> List[Dict[str, object]]:
    """
    Collapse per-outcome edges into one row per game, showing the favorite side.
    Deduplicates by canonical game key (away@home) so the same matchup never
    appears twice even if both outcome edges are in the list.
    """
    # First group by game_id to pair home + away edges
    games: Dict[str, List[EdgeAnalysis]] = {}
    for edge in all_edges:
        games.setdefault(edge.game_id, []).append(edge)

    # Deduplicate by canonical matchup label (away_abbr@home_abbr) — keeps
    # the version with the higher |edge_pp| when duplicates exist.
    seen_matchups: Dict[str, Dict[str, object]] = {}

    for game_edges in games.values():
        fav_edge = max(game_edges, key=lambda e: e.true_prob)
        away_edge = next((e for e in game_edges if e.team == "away"), fav_edge)
        home_edge = next((e for e in game_edges if e.team == "home"), fav_edge)

        matchup_key = f"{_abbr(away_edge.team_name)}@{_abbr(home_edge.team_name)}"
        verdict = _verdict_label(fav_edge.signal)
        row = {
            "game": matchup_key,
            "fav": _abbr(fav_edge.team_name),
            "fav_full": fav_edge.team_name,
            "true_pct": int(round(fav_edge.true_prob)),
            "poly_pct": int(round(fav_edge.polymarket_prob)),
            "conf_pct": int(round(fav_edge.confidence_pct)),
            "edge": round(fav_edge.edge_pp, 1),
            "signal": fav_edge.signal,
            "verdict": verdict,
            "icon": _VERDICT_ICON.get(fav_edge.signal, ""),
            "prefix": _row_prefix(verdict),
            "commence_time": fav_edge.commence_time,
        }

        existing = seen_matchups.get(matchup_key)
        if existing is None or abs(row["edge"]) > abs(existing["edge"]):
            seen_matchups[matchup_key] = row

    return sorted(seen_matchups.values(), key=lambda r: (r["commence_time"], r["game"]))


def _abbr(team_name: str) -> str:
    from normalization.teams import get_polymarket_abbr

    return get_polymarket_abbr(team_name).upper()


def _verdict_label(signal: str) -> str:
    # Keep STRONG BET as distinct from BET for prefix/icon logic
    return signal


def _row_prefix(verdict: str) -> str:
    if verdict in ("STRONG BET", "BET"):
        return "+"
    if verdict in ("AVOID", "FADE"):
        return "-"
    return " "
