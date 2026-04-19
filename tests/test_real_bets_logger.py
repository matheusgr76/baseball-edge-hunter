import io
import json
import shutil
import sys
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import config
from models import EdgeAnalysis, PipelineResult
from output.real_bets_logger import (
    append_daily_bets_index,
    start_run_session,
    tee_terminal_output,
    write_run_artifacts,
)


def _edge(actionable: bool, signal: str, edge_pp: float) -> EdgeAnalysis:
    return EdgeAnalysis(
        game_id="g1",
        team="home",
        team_name="Boston Red Sox",
        opponent="New York Yankees",
        commence_time=datetime(2026, 4, 18, 19, 5, 0),
        consensus_prob=55.0,
        true_prob=57.0,
        polymarket_prob=50.0,
        edge_pp=edge_pp,
        signal=signal,
        confidence_pct=80,
        actionable=actionable,
    )


class RealBetsLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_root = Path("output") / "_test_artifacts" / f"real_bets_{uuid.uuid4().hex}"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.output_patch = patch.object(config, "OUTPUT_DIRECTORY", str(self.test_root))
        self.output_patch.start()

    def tearDown(self) -> None:
        self.output_patch.stop()
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_start_run_session_creates_unique_paths(self) -> None:
        run_a = start_run_session(datetime(2026, 4, 18, 12, 0, 0, 111111))
        run_b = start_run_session(datetime(2026, 4, 18, 12, 0, 0, 111112))

        self.assertNotEqual(run_a.run_id, run_b.run_id)
        self.assertIn("2026-04-18", str(run_a.log_path))
        self.assertTrue(str(run_a.log_path).endswith(".log"))
        self.assertTrue(str(run_a.json_path).endswith(".json"))

    def test_tee_capture_and_artifact_write(self) -> None:
        session = start_run_session(datetime(2026, 4, 18, 12, 10, 0, 222222))
        fake_stdout = io.StringIO()
        fake_stderr = io.StringIO()
        result = PipelineResult(
            timestamp=datetime(2026, 4, 18, 12, 10, 0),
            games_analyzed=1,
            polymarket_markets_found=1,
            edges_detected=1,
            edges=[_edge(actionable=True, signal="BET", edge_pp=7.0)],
            warnings=["LINEUP NOT CONFIRMED: NYY @ BOS"],
            execution_time_seconds=2.5,
            telegram_sent=True,
        )

        with patch("sys.stdout", fake_stdout), patch("sys.stderr", fake_stderr):
            with tee_terminal_output(session):
                print("terminal-line")
                print("stderr-line", file=sys.stderr)

        payload = write_run_artifacts(
            session=session,
            run_status="success",
            pipeline_result=result,
            telegram_sent=True,
        )

        self.assertIn("terminal-line", fake_stdout.getvalue())
        self.assertIn("stderr-line", fake_stderr.getvalue())

        log_text = session.log_path.read_text(encoding="utf-8")
        self.assertIn("terminal-line", log_text)
        self.assertIn("stderr-line", log_text)
        self.assertEqual(payload["run_status"], "success")
        self.assertIn("reliability_gate", payload["pipeline_summary"])
        self.assertTrue(session.json_path.exists())

    def test_daily_jsonl_keeps_duplicate_game_side_across_runs(self) -> None:
        first = start_run_session(datetime(2026, 4, 18, 13, 0, 0, 111111))
        second = start_run_session(datetime(2026, 4, 18, 13, 5, 0, 222222))

        result = PipelineResult(
            timestamp=datetime(2026, 4, 18, 13, 0, 0),
            games_analyzed=1,
            polymarket_markets_found=1,
            edges_detected=1,
            edges=[_edge(actionable=True, signal="BET", edge_pp=6.5)],
            execution_time_seconds=1.0,
            telegram_sent=False,
        )

        write_run_artifacts(first, "success", result, telegram_sent=False)
        write_run_artifacts(second, "success", result, telegram_sent=False)

        written_a = append_daily_bets_index(first, result, "success", telegram_sent=False)
        written_b = append_daily_bets_index(second, result, "success", telegram_sent=False)

        self.assertEqual(written_a, 1)
        self.assertEqual(written_b, 1)

        lines = first.daily_jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        row_a = json.loads(lines[0])
        row_b = json.loads(lines[1])
        self.assertEqual(row_a["game_id"], row_b["game_id"])
        self.assertEqual(row_a["team"], row_b["team"])
        self.assertNotEqual(row_a["run_id"], row_b["run_id"])


if __name__ == "__main__":
    unittest.main()
