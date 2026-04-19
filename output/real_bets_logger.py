"""
Run-level real bets logger.

This logger is an immutable audit layer for manual pipeline runs:
  - Captures full terminal transcript (stdout + stderr).
  - Persists one run artifact pair (.log + .json) per run.
  - Appends actionable bets to a daily JSONL ledger.
"""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import config
from models import PipelineResult


_LINEUP_WARNING_PREFIX = "LINEUP NOT CONFIRMED"


class _TeeWriter:
    """Mirror stream writes to two targets."""

    def __init__(self, primary: Any, mirror: Any) -> None:
        self.primary = primary
        self.mirror = mirror

    def write(self, data: str) -> int:
        self.primary.write(data)
        self.mirror.write(data)
        return len(data)

    def flush(self) -> None:
        self.primary.flush()
        self.mirror.flush()

    def isatty(self) -> bool:
        return bool(getattr(self.primary, "isatty", lambda: False)())


@dataclass
class RunSession:
    run_id: str
    run_started_at: datetime
    source_report_date: str
    run_dir: Path
    log_path: Path
    json_path: Path
    daily_jsonl_path: Path
    transcript_buffer: io.StringIO = field(default_factory=io.StringIO)
    run_finished_at: Optional[datetime] = None


def start_run_session(now: Optional[datetime] = None) -> RunSession:
    """Create deterministic run file paths for the current run."""
    start_dt = now or datetime.now()
    date_str = start_dt.strftime("%Y-%m-%d")
    run_id = f"run_{start_dt.strftime('%Y%m%d_%H%M%S_%f')}"

    root = Path(config.OUTPUT_DIRECTORY) / "real_bets"
    run_dir = root / "runs" / date_str
    daily_dir = root / "daily"

    return RunSession(
        run_id=run_id,
        run_started_at=start_dt,
        source_report_date=date_str,
        run_dir=run_dir,
        log_path=run_dir / f"{run_id}.log",
        json_path=run_dir / f"{run_id}.json",
        daily_jsonl_path=daily_dir / f"real_bets_{date_str}.jsonl",
    )


@contextmanager
def tee_terminal_output(session: RunSession) -> Generator[None, None, None]:
    """
    Capture terminal output while still printing live to console.

    Captures both stdout and stderr into session.transcript_buffer.
    """
    out_tee = _TeeWriter(sys.stdout, session.transcript_buffer)
    err_tee = _TeeWriter(sys.stderr, session.transcript_buffer)
    with redirect_stdout(out_tee), redirect_stderr(err_tee):
        yield


def _lineup_warnings(warnings: List[str]) -> List[str]:
    cleaned: List[str] = []
    for warning in warnings:
        text = str(warning).strip()
        if text and _LINEUP_WARNING_PREFIX in text:
            cleaned.append(text)
    return cleaned


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    os.replace(tmp_path, path)


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def _reliability_gate_snapshot() -> Dict[str, Any]:
    """
    Best-effort runtime snapshot of reliability gate status.

    Fail-open by design: if the tracker cannot be read here, include an error
    payload instead of raising.
    """
    try:
        from output.clv_tracker import reliability_gate_status

        return reliability_gate_status()
    except Exception as exc:  # pragma: no cover - defensive snapshot path
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_payload(
    session: RunSession,
    run_status: str,
    pipeline_result: Optional[PipelineResult],
    error_message: Optional[str],
    telegram_sent: Optional[bool],
) -> Dict[str, Any]:
    edge_count = len(pipeline_result.edges) if pipeline_result else 0
    actionable_count = (
        sum(1 for edge in pipeline_result.edges if edge.actionable)
        if pipeline_result
        else 0
    )
    warnings = list(pipeline_result.warnings) if pipeline_result else []
    errors = list(pipeline_result.errors) if pipeline_result else []

    return {
        "run_id": session.run_id,
        "run_status": run_status,
        "run_started_at": session.run_started_at.isoformat(),
        "run_finished_at": session.run_finished_at.isoformat(),
        "source_report_date": session.source_report_date,
        "telegram_sent": telegram_sent,
        "error_message": error_message,
        "pipeline_summary": {
            "games_analyzed": pipeline_result.games_analyzed if pipeline_result else 0,
            "polymarket_markets_found": (
                pipeline_result.polymarket_markets_found if pipeline_result else 0
            ),
            "edges_detected": pipeline_result.edges_detected if pipeline_result else 0,
            "edge_rows_total": edge_count,
            "actionable_edges_total": actionable_count,
            "execution_time_seconds": (
                pipeline_result.execution_time_seconds if pipeline_result else 0.0
            ),
            "warnings": warnings,
            "errors": errors,
            "lineup_warnings": _lineup_warnings(warnings),
            "reliability_gate": _reliability_gate_snapshot(),
        },
        "artifacts": {
            "transcript_log": str(session.log_path),
            "run_json": str(session.json_path),
            "daily_jsonl": str(session.daily_jsonl_path),
        },
    }


def write_run_artifacts(
    session: RunSession,
    run_status: str,
    pipeline_result: Optional[PipelineResult],
    error_message: Optional[str] = None,
    telegram_sent: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Persist run transcript + run metadata JSON.

    Returns the JSON payload written to disk.
    """
    session.run_finished_at = datetime.now()
    transcript = session.transcript_buffer.getvalue()
    payload = _run_payload(
        session=session,
        run_status=run_status,
        pipeline_result=pipeline_result,
        error_message=error_message,
        telegram_sent=telegram_sent,
    )

    _atomic_write_text(session.log_path, transcript)
    _atomic_write_json(session.json_path, payload)
    return payload


def append_daily_bets_index(
    session: RunSession,
    pipeline_result: Optional[PipelineResult],
    run_status: str,
    telegram_sent: Optional[bool] = None,
) -> int:
    """
    Append actionable rows to a daily JSONL ledger.

    No dedupe is performed: repeated same-day reruns are intentionally preserved.
    """
    if pipeline_result is None:
        return 0

    actionable_edges = [edge for edge in pipeline_result.edges if edge.actionable]
    if not actionable_edges:
        return 0

    run_finished_at = (
        session.run_finished_at.isoformat()
        if session.run_finished_at is not None
        else datetime.now().isoformat()
    )
    lineup_warnings = _lineup_warnings(list(pipeline_result.warnings))

    session.daily_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with open(session.daily_jsonl_path, "a", encoding="utf-8") as handle:
        for edge in actionable_edges:
            row = {
                "run_id": session.run_id,
                "run_started_at": session.run_started_at.isoformat(),
                "run_finished_at": run_finished_at,
                "run_status": run_status,
                "source_report_date": session.source_report_date,
                "game_id": edge.game_id,
                "team": edge.team,
                "team_name": edge.team_name,
                "opponent": edge.opponent,
                "commence_time": edge.commence_time.isoformat(),
                "signal": edge.signal,
                "actionable": edge.actionable,
                "true_prob": edge.true_prob,
                "polymarket_prob": edge.polymarket_prob,
                "edge_pp": edge.edge_pp,
                "confidence_pct": edge.confidence_pct,
                "lineup_warnings": lineup_warnings,
                "telegram_sent": telegram_sent,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows_written += 1
    return rows_written
