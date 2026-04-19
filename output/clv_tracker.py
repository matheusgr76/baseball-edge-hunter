"""
MLB Edge Hunter - CLV Tracker (Phase 3a)
-----------------------------------------
Responsibilities:
  1. log_signals()  — append EdgeAnalysis results to predictions_log.json on each pipeline run
  2. resolve_signal() — record closing Polymarket line after game resolves + compute CLV
  3. clv_summary()  — aggregate CLV% and beat-rate over all resolved signals
  4. reliability_gate_status() — evaluate dual-gate operational readiness

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
    "resolved_at":    str | null,
    "final_winner":   str | null,     # canonical team name
    "picked_team_won": bool | null,   # True when logged side won
    "game_result_date": str | null,   # YYYY-MM-DD from MLB schedule
    "game_resolved_at": str | null
  }
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from models import EdgeAnalysis
from normalization.teams import normalize_team_name
import config


# ── Constants ────────────────────────────────────────────────────────────────

_LOG_FILE = os.path.join("output", "predictions_log.json")
_MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
_HTTP_HEADERS = {"User-Agent": "mlb-edge-hunter/1.0"}
_FINAL_STATES = {"Final", "Completed Early", "Game Over"}


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
        "final_winner":    None,
        "picked_team_won": None,
        "game_result_date": None,
        "game_resolved_at": None,
    }


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _request_json_with_retry(url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=_HTTP_HEADERS,
                timeout=config.REQUEST_TIMEOUT,
            )
            print(
                "  [MLB API]",
                f"{datetime.now().isoformat()}",
                f"status={response.status_code}",
                f"attempt={attempt}",
                f"params={params}",
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == config.MAX_RETRIES:
                return None
    return None


def _fetch_final_games_for_date(date_str: str) -> List[Dict[str, Any]]:
    payload = _request_json_with_retry(
        _MLB_SCHEDULE_URL,
        {"sportId": 1, "date": date_str},
    )
    if not payload:
        return []

    finals: List[Dict[str, Any]] = []
    for block in payload.get("dates", []):
        for game in block.get("games", []):
            detailed_state = (game.get("status") or {}).get("detailedState", "")
            if detailed_state not in _FINAL_STATES:
                continue

            teams = game.get("teams") or {}
            home_team_raw = (((teams.get("home") or {}).get("team") or {}).get("name", ""))
            away_team_raw = (((teams.get("away") or {}).get("team") or {}).get("name", ""))
            if not home_team_raw or not away_team_raw:
                continue

            home_team = normalize_team_name(home_team_raw)
            away_team = normalize_team_name(away_team_raw)
            home_score = (teams.get("home") or {}).get("score")
            away_score = (teams.get("away") or {}).get("score")
            if not isinstance(home_score, int) or not isinstance(away_score, int):
                continue
            if home_score == away_score:
                continue

            winner = home_team if home_score > away_score else away_team
            game_dt = _parse_iso_datetime(game.get("gameDate"))
            finals.append(
                {
                    "home_team": home_team,
                    "away_team": away_team,
                    "winner": winner,
                    "game_date": block.get("date", date_str),
                    "game_time": game_dt,
                }
            )
    return finals


def _candidate_dates(commence_time: Optional[datetime]) -> Set[str]:
    if commence_time is None:
        return set()
    dates = {commence_time.date()}
    dates.add((commence_time - timedelta(days=1)).date())
    dates.add((commence_time + timedelta(days=1)).date())
    return {d.isoformat() for d in dates}


def _match_final_game(
    entry: Dict[str, Any],
    finals_by_date: Dict[str, List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    team_name = normalize_team_name(str(entry.get("team_name", "")))
    opponent = normalize_team_name(str(entry.get("opponent", "")))
    if not team_name or not opponent:
        return None

    commence_time = _parse_iso_datetime(entry.get("commence_time"))
    date_candidates = sorted(_candidate_dates(commence_time))
    match_key = tuple(sorted((team_name.lower(), opponent.lower())))

    candidates: List[Dict[str, Any]] = []
    for date_key in date_candidates:
        for game in finals_by_date.get(date_key, []):
            game_key = tuple(
                sorted((game["home_team"].lower(), game["away_team"].lower()))
            )
            if game_key == match_key:
                candidates.append(game)

    if not candidates:
        return None
    if len(candidates) == 1 or commence_time is None:
        return candidates[0]

    def _distance_seconds(game_row: Dict[str, Any]) -> float:
        game_time = game_row.get("game_time")
        if not isinstance(game_time, datetime):
            return float("inf")
        return abs((game_time - commence_time).total_seconds())

    return min(candidates, key=_distance_seconds)


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


def resolve_game_outcomes(actionable_only: bool = True) -> Dict[str, Any]:
    """
    Resolve logged entries against official MLB final scores.

    This function updates outcome fields only (`final_winner`, `picked_team_won`),
    and intentionally does not infer or overwrite CLV closing lines.
    """
    entries = _load_log()
    if not entries:
        return {
            "entries_scanned": 0,
            "eligible_unresolved": 0,
            "updated": 0,
            "actionable_updated": 0,
            "requested_dates": 0,
        }

    now_utc = datetime.now(timezone.utc)
    unresolved: List[Dict[str, Any]] = []
    all_dates: Set[str] = set()

    for entry in entries:
        if actionable_only and not entry.get("actionable", False):
            continue
        if entry.get("picked_team_won") is not None:
            continue

        commence_time = _parse_iso_datetime(entry.get("commence_time"))
        if commence_time is None or commence_time >= now_utc:
            continue

        unresolved.append(entry)
        all_dates.update(_candidate_dates(commence_time))

    if not unresolved:
        return {
            "entries_scanned": len(entries),
            "eligible_unresolved": 0,
            "updated": 0,
            "actionable_updated": 0,
            "requested_dates": 0,
        }

    finals_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for date_key in sorted(all_dates):
        finals_by_date[date_key] = _fetch_final_games_for_date(date_key)

    updated = 0
    actionable_updated = 0
    resolved_at = datetime.now().isoformat()
    for entry in unresolved:
        match = _match_final_game(entry, finals_by_date)
        if not match:
            continue

        winner = match["winner"]
        team_name = normalize_team_name(str(entry.get("team_name", "")))
        picked_team_won = team_name.lower() == winner.lower()

        entry["final_winner"] = winner
        entry["picked_team_won"] = picked_team_won
        entry["game_result_date"] = match.get("game_date")
        entry["game_resolved_at"] = resolved_at
        updated += 1
        if entry.get("actionable", False):
            actionable_updated += 1

    if updated:
        _save_log(entries)

    return {
        "entries_scanned": len(entries),
        "eligible_unresolved": len(unresolved),
        "updated": updated,
        "actionable_updated": actionable_updated,
        "requested_dates": len(all_dates),
    }


def outcome_summary() -> Dict[str, Any]:
    """Summarize resolved game outcomes over logged actionable signals."""
    entries = _load_log()
    actionable = [e for e in entries if e.get("actionable", False)]
    resolved = [e for e in actionable if e.get("picked_team_won") is not None]
    wins = sum(1 for e in resolved if e.get("picked_team_won") is True)
    losses = sum(1 for e in resolved if e.get("picked_team_won") is False)
    n = len(resolved)
    win_rate = round((wins / n) * 100, 2) if n else 0.0

    return {
        "actionable_total": len(actionable),
        "actionable_resolved": n,
        "actionable_wins": wins,
        "actionable_losses": losses,
        "actionable_win_rate_pct": win_rate,
    }


def reliability_gate_status() -> Dict[str, Any]:
    """
    Evaluate operational dual gate for reliability-driven retuning decisions.

    Gate conditions:
      1) resolved actionable outcomes >= RELIABILITY_GATE_MIN_RESOLVED_ACTIONABLE
      2) actionable win-rate >= RELIABILITY_GATE_MIN_WIN_RATE_PCT
    """
    summary = outcome_summary()
    resolved_required = int(config.RELIABILITY_GATE_MIN_RESOLVED_ACTIONABLE)
    win_rate_required = float(config.RELIABILITY_GATE_MIN_WIN_RATE_PCT)

    resolved = int(summary["actionable_resolved"])
    win_rate = float(summary["actionable_win_rate_pct"])

    resolved_ok = resolved >= resolved_required
    win_rate_ok = win_rate >= win_rate_required
    dual_gate_met = resolved_ok and win_rate_ok

    return {
        "rollout_mode": str(config.RELIABILITY_ROLLOUT_MODE),
        "resolved_actionable": resolved,
        "resolved_required": resolved_required,
        "resolved_remaining": max(0, resolved_required - resolved),
        "win_rate_pct": round(win_rate, 2),
        "win_rate_required_pct": round(win_rate_required, 2),
        "win_rate_gap_pct": round(max(0.0, win_rate_required - win_rate), 2),
        "resolved_ok": resolved_ok,
        "win_rate_ok": win_rate_ok,
        "dual_gate_met": dual_gate_met,
        "retuning_allowed": dual_gate_met,
    }


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
    o = outcome_summary()
    gate = reliability_gate_status()

    print()
    print("=" * 70)
    print("  📈 CLV TRACKER SUMMARY")
    print("=" * 70)
    print(f"  Total signals logged : {s['total_signals']}")
    print(f"  Resolved             : {s['resolved']}")
    print(f"  Actionable resolved  : {s['actionable']}")
    print(f"  CLV beat-rate        : {s['clv_beat_rate_pct']:.1f}%  (target ≥ 55%)")
    print(f"  Avg CLV              : {s['avg_clv_pp']:+.2f}pp")
    print()
    print("  Outcome tracking (actionable only):")
    print(
        "  "
        f"resolved={o['actionable_resolved']}/{o['actionable_total']}  "
        f"wins={o['actionable_wins']}  "
        f"losses={o['actionable_losses']}  "
        f"win-rate={o['actionable_win_rate_pct']:.1f}%"
    )
    print(f"  Rollout mode          : {gate['rollout_mode']}")
    if not gate["dual_gate_met"]:
        if not gate["resolved_ok"]:
            print(
                "  ⚠️  Need "
                f"{gate['resolved_remaining']} more resolved actionable outcomes "
                "for reliability dual gate"
            )
        if not gate["win_rate_ok"]:
            print(
                "  ⚠️  Need "
                f"+{gate['win_rate_gap_pct']:.1f}pp actionable win-rate "
                "to meet reliability dual gate"
            )
        print("  ⚠️  Retuning remains locked until dual gate is satisfied")
    else:
        print("  ✅ Reliability dual gate met — retuning review is unlocked")
    if s["actionable"] < 100:
        remaining = 100 - s["actionable"]
        print(f"  ⚠️  Need {remaining} more resolved actionable signals to hit sample target")
    if s["target_met"]:
        print("  ✅ TARGET MET — system generating real edge")
    print("=" * 70)
    print()
