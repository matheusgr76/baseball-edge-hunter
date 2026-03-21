"""
MLB Edge Hunter - CLV Tracker (Phase 3a)
-----------------------------------------
Responsibilities:
  1. log_signals()  — append EdgeAnalysis results to predictions_log.json on each pipeline run
  2. resolve_signal() — record closing Polymarket line after game resolves + compute CLV
  3. clv_summary()  — aggregate CLV% and beat-rate over all resolved signals

File: output/predictions_log.json
Schema per entry:
  {
    "entry_id":       str  (game_id + "_" + team),
    "game_id":        str,
    "team":           str,   # "home" | "away"
    "team_name":      str,
    "opponent":       str,
    "commence_time":  str (ISO-8601),
    "signal":         str,   # STRONG BET | BET | SKIP | FADE | AVOID
    "true_prob":      float, # calibrated probability (0-100)
    "polymarket_prob":float, # signal-time Polymarket price (0-100)
    "edge_pp":        float, # true_prob - polymarket_prob
    "confidence_pct": int,
    "actionable":     bool,
    "logged_at":      str (ISO-8601),
    "closing_line":   float | null,   # filled in post-game
    "clv":            float | null,   # closing_line - polymarket_prob (pp)
    "resolved_at":    str | null
  }
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from models import EdgeAnalysis


# ── Constants ────────────────────────────────────────────────────────────────

_LOG_FILE = os.path.join("output", "predictions_log.json")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _entry_id(game_id: str, team: str) -> str:
    return f"{game_id}_{team}"


def _load_log() -> List[Dict[str, Any]]:
    """Load existing log file, return empty list if missing or corrupt."""
    if not os.path.exists(_LOG_FILE):
        return []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_log(entries: List[Dict[str, Any]]) -> None:
    """Persist log entries to disk (atomic overwrite)."""
    os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)
    tmp_path = _LOG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, _LOG_FILE)


def _edge_to_entry(edge: EdgeAnalysis, now: str) -> Dict[str, Any]:
    return {
        "entry_id":        _entry_id(edge.game_id, edge.team),
        "game_id":         edge.game_id,
        "team":            edge.team,
        "team_name":       edge.team_name,
        "opponent":        edge.opponent,
        "commence_time":   edge.commence_time.isoformat(),
        "signal":          edge.signal,
        "true_prob":       round(edge.true_prob, 4),
        "polymarket_prob": round(edge.polymarket_prob, 4),
        "edge_pp":         round(edge.edge_pp, 4),
        "confidence_pct":  edge.confidence_pct,
        "actionable":      edge.actionable,
        "logged_at":       now,
        "closing_line":    None,
        "clv":             None,
        "resolved_at":     None,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def log_signals(edges: List[EdgeAnalysis]) -> int:
    """
    Append new EdgeAnalysis results to predictions_log.json.

    Skips duplicates — same entry_id is never written twice (idempotent on
    same-day re-runs).

    Returns:
        Number of new entries written.
    """
    if not edges:
        return 0

    now = datetime.now().isoformat()
    existing = _load_log()
    existing_ids = {e["entry_id"] for e in existing}

    new_entries = []
    for edge in edges:
        eid = _entry_id(edge.game_id, edge.team)
        if eid not in existing_ids:
            new_entries.append(_edge_to_entry(edge, now))
            existing_ids.add(eid)

    if new_entries:
        _save_log(existing + new_entries)

    return len(new_entries)


def resolve_signal(
    game_id: str,
    team: str,
    closing_line: float,
) -> Optional[float]:
    """
    Record the closing Polymarket price for a resolved signal and compute CLV.

    CLV (Closing Line Value) = closing_line - signal_time_polymarket_prob (pp).
    Positive CLV = we had better odds than the market settled at (good).

    Args:
        game_id:      Matches EdgeAnalysis.game_id.
        team:         "home" or "away".
        closing_line: Final Polymarket price before market closed (0-100 scale).

    Returns:
        CLV in percentage points, or None if entry not found.
    """
    eid = _entry_id(game_id, team)
    entries = _load_log()

    for entry in entries:
        if entry["entry_id"] == eid:
            clv = round(closing_line - entry["polymarket_prob"], 4)
            entry["closing_line"] = round(closing_line, 4)
            entry["clv"] = clv
            entry["resolved_at"] = datetime.now().isoformat()
            _save_log(entries)
            return clv

    return None


def clv_summary() -> Dict[str, Any]:
    """
    Compute aggregate CLV statistics over all resolved signals.

    Returns a dict with:
        total_signals      — all entries ever logged
        resolved           — entries with a closing line recorded
        actionable         — subset that were STRONG BET or BET
        clv_beat_rate_pct  — % of resolved actionable signals with CLV > 0
        avg_clv_pp         — mean CLV across resolved actionable signals
        target_met         — True if beat-rate >= 55% over >= 100 resolved actionable signals
    """
    entries = _load_log()

    resolved = [e for e in entries if e.get("clv") is not None]
    actionable_resolved = [e for e in resolved if e.get("actionable")]

    beat_count = sum(1 for e in actionable_resolved if e["clv"] > 0)
    n = len(actionable_resolved)

    beat_rate = round(beat_count / n * 100, 2) if n > 0 else 0.0
    avg_clv = round(sum(e["clv"] for e in actionable_resolved) / n, 4) if n > 0 else 0.0

    return {
        "total_signals":     len(entries),
        "resolved":          len(resolved),
        "actionable":        n,
        "clv_beat_rate_pct": beat_rate,
        "avg_clv_pp":        avg_clv,
        "target_met":        n >= 100 and beat_rate >= 55.0,
    }


def weekly_summary() -> List[Dict[str, Any]]:
    """
    Group resolved actionable signals by ISO calendar week of game date.
    Returns list of week dicts sorted newest-first.
    """
    entries = _load_log()
    resolved_actionable = [
        e for e in entries
        if e.get("actionable") and e.get("clv") is not None
    ]

    weeks: Dict[str, List] = defaultdict(list)
    for e in resolved_actionable:
        try:
            dt = datetime.fromisoformat(e["commence_time"])
        except (KeyError, ValueError):
            dt = datetime.fromisoformat(e["logged_at"])
        weeks[dt.strftime("%Y-W%V")].append(e)

    result = []
    for wk in sorted(weeks.keys(), reverse=True):
        rows = weeks[wk]
        n = len(rows)
        beat = sum(1 for r in rows if r["clv"] > 0)
        result.append({
            "week":          wk,
            "volume":        n,
            "beat_count":    beat,
            "beat_rate_pct": round(beat / n * 100, 1),
            "avg_clv_pp":    round(sum(r["clv"] for r in rows) / n, 4),
            "total_clv_pp":  round(sum(r["clv"] for r in rows), 4),
        })
    return result


def print_weekly_summary() -> None:
    """Print weekly CLV performance table. No-op if no resolved data yet."""
    weeks = weekly_summary()
    if not weeks:
        return

    print()
    print("=" * 74)
    print("  📅 WEEKLY PERFORMANCE SUMMARY")
    print("=" * 74)
    print(
        f"  {'WEEK':<12} | {'SIGNALS':>7} | {'BEAT':>4} | "
        f"{'BEAT%':>6} | {'AVG CLV':>8} | {'TOTAL CLV':>9}"
    )
    print(f"  {'-'*12}-+-{'-'*7}-+-{'-'*4}-+-{'-'*6}-+-{'-'*8}-+-{'-'*9}")
    for w in weeks:
        flag = "✅" if w["beat_rate_pct"] >= 55.0 else "⚠️ "
        print(
            f"  {w['week']:<12} | {w['volume']:>7} | {w['beat_count']:>4} | "
            f"{w['beat_rate_pct']:>5.1f}% | {w['avg_clv_pp']:>+7.2f}pp | "
            f"{w['total_clv_pp']:>+8.2f}pp  {flag}"
        )
    print("=" * 74)
    print()


# ── P&L sparkline ─────────────────────────────────────────────────────────────

_SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(values: List[float], width: int = 60) -> str:
    """Map a list of floats to a Unicode block sparkline (last `width` points)."""
    vals = values[-width:]
    lo, hi = min(vals), max(vals)
    if lo == hi:
        return "─" * len(vals)
    span = hi - lo
    return "".join(_SPARK[int((v - lo) / span * (len(_SPARK) - 1))] for v in vals)


def print_pnl_chart() -> None:
    """Print cumulative CLV P&L sparkline for resolved actionable signals."""
    entries = _load_log()
    resolved = sorted(
        [e for e in entries if e.get("actionable") and e.get("clv") is not None],
        key=lambda e: e.get("logged_at", ""),
    )
    if not resolved:
        return

    cumulative, running = [], 0.0
    for e in resolved:
        running += e["clv"]
        cumulative.append(round(running, 4))

    total = cumulative[-1]
    n = len(cumulative)
    print()
    print("=" * 74)
    print("  📈 CUMULATIVE CLV P&L CHART")
    print("=" * 74)
    print(f"  Signals: {n}  |  Total CLV: {total:+.2f}pp  |  Per-signal avg: {total/n:+.2f}pp")
    print()
    print(f"  {_sparkline(cumulative)}")
    print(f"  {'↑ positive drift' if total >= 0 else '↓ negative drift'}")
    print("=" * 74)
    print()


def print_clv_summary() -> None:
    """Print a formatted CLV summary to the terminal."""
    s = clv_summary()

    print()
    print("=" * 70)
    print("  📈 CLV TRACKER SUMMARY")
    print("=" * 70)
    print(f"  Total signals logged : {s['total_signals']}")
    print(f"  Resolved             : {s['resolved']}")
    print(f"  Actionable resolved  : {s['actionable']}")
    print(f"  CLV beat-rate        : {s['clv_beat_rate_pct']:.1f}%  (target ≥ 55%)")
    print(f"  Avg CLV              : {s['avg_clv_pp']:+.2f}pp")
    if s["actionable"] < 100:
        remaining = 100 - s["actionable"]
        print(f"  ⚠️  Need {remaining} more resolved actionable signals to hit sample target")
    if s["target_met"]:
        print("  ✅ TARGET MET — system generating real edge")
    print("=" * 70)
    print()
