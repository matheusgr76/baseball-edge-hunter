"""
MLB Edge Hunter - Report Formatter
Terminal output + CSV export matching basketball_edge_hunter format exactly.
Sport emoji: ⚾  |  Signal column: SIGNAL  |  Summary title: ANALYSIS SUMMARY
"""

import csv
import os
from datetime import datetime
from typing import List

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
    Print the final ANALYSIS SUMMARY table with one row per outcome per game,
    then the actionable callout section and signal legend.
    """
    print()
    print("=" * 140)
    print("  📊 ANALYSIS SUMMARY")
    print("=" * 140)
    print()

    # Table header
    print(
        f"  {'GAME':<50} | {'FAVORITE':<25} | {'PROB':>5} | "
        f"{'CONF':>4} | {'WCS':>5} | {'SIGNAL':<14} | {'MARKET':>6} | {'EDGE':>7}"
    )
    print(
        f"  {'-'*50}-+-{'-'*25}-+-{'-'*5}-+-"
        f"{'-'*4}-+-{'-'*5}-+-{'-'*14}-+-{'-'*6}-+-{'-'*7}"
    )

    actionable: List[EdgeAnalysis] = []

    for e in all_edges:
        game = f"{e.opponent} @ {e.team_name}" if e.team == "home" else f"{e.team_name} @ {e.opponent}"
        fav_name = e.team_name if e.true_prob >= 50.0 else e.opponent
        wcs = round(e.true_prob - 8.0, 1)  # Phase 1 WCS placeholder
        signal_display = _SIGNAL_EMOJI.get(e.signal, e.signal)

        game_trunc = game[:47] + "..." if len(game) > 50 else game
        fav_trunc = fav_name[:22] + "..." if len(fav_name) > 25 else fav_name

        print(
            f"  {game_trunc:<50} | {fav_trunc:<25} | "
            f"{e.true_prob:>4.1f}% | {e.confidence_pct:>3}% | "
            f"{wcs:>4.1f} | {signal_display:<14} | "
            f"{e.polymarket_prob:>5.1f}% | {e.edge_pp:>+6.2f}%"
        )

        if e.actionable:
            actionable.append(e)

    print()
    print("=" * 140)
    print()

    # Actionable callout
    if actionable:
        print(f"  🎯 ACTIONABLE EDGES: {len(actionable)} found")
        for e in actionable:
            emoji = "🔥" if e.signal == "STRONG BET" else "✅"
            print(
                f"     {emoji} {e.team_name} — Edge: {e.edge_pp:+.2f}pp "
                f"| Prob: {e.true_prob:.1f}% | Confidence: {e.confidence_pct}% "
                f"→ {e.signal}"
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
            wcs = round(e.true_prob - 8.0, 1)

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
            wcs = round(e.true_prob - 8.0, 1)
            writer.writerow([
                i, game, fav, dog,
                f"{e.true_prob:.2f}", e.confidence_pct, wcs,
                f"{e.polymarket_prob:.2f}", f"{e.edge_pp:+.2f}",
                e.signal, "YES" if e.actionable else "no",
                "", "", "", "",
            ])

    print(f"  📁 CSV exported: {filepath}")
    return filepath
