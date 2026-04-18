"""
MLB Edge Hunter - Entry Point

Usage:
  python main.py

Optional env vars for outbound Telegram summary:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import sys
import traceback
from types import TracebackType
from typing import Optional, Tuple

from models import PipelineResult
from orchestration.pipeline import run_pipeline
from output.real_bets_logger import (
    append_daily_bets_index,
    start_run_session,
    tee_terminal_output,
    write_run_artifacts,
)


def run_with_real_bets_logging() -> PipelineResult:
    """
    Run the pipeline and persist immutable real-bets run artifacts.

    Logger failures are fail-open and never block pipeline execution.
    """
    session = start_run_session()
    result: Optional[PipelineResult] = None
    run_status = "failed"
    error_message: Optional[str] = None
    captured_exc: Optional[Tuple[type, BaseException, TracebackType]] = None

    with tee_terminal_output(session):
        try:
            result = run_pipeline()
            run_status = "success"
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            captured_exc = (type(exc), exc, exc.__traceback__)
            traceback.print_exc()

    try:
        telegram_sent = result.telegram_sent if result is not None else None
        write_run_artifacts(
            session=session,
            run_status=run_status,
            pipeline_result=result,
            error_message=error_message,
            telegram_sent=telegram_sent,
        )
        append_daily_bets_index(
            session=session,
            pipeline_result=result,
            run_status=run_status,
            telegram_sent=telegram_sent,
        )
    except Exception as logger_error:
        print(
            f"[real_bets_logger] WARNING: failed to persist run artifacts: {logger_error}",
            file=sys.stderr,
        )

    if captured_exc is not None:
        exc_type, exc_value, exc_tb = captured_exc
        raise exc_value.with_traceback(exc_tb)

    if result is None:
        raise RuntimeError("Pipeline returned no result and no exception.")
    return result


if __name__ == "__main__":
    run_with_real_bets_logging()
