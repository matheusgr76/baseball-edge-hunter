import json
import shutil
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import config
import main
from models import EdgeAnalysis, PipelineResult


def _edge(game_id: str, actionable: bool, signal: str, edge_pp: float) -> EdgeAnalysis:
    return EdgeAnalysis(
        game_id=game_id,
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


class MainRealBetsLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_root = Path("output") / "_test_artifacts" / f"main_real_bets_{uuid.uuid4().hex}"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.output_patch = patch.object(config, "OUTPUT_DIRECTORY", str(self.test_root))
        self.output_patch.start()

    def tearDown(self) -> None:
        self.output_patch.stop()
        shutil.rmtree(self.test_root, ignore_errors=True)

    @patch("main.run_pipeline")
    def test_success_run_logs_only_actionable_rows(self, mock_run_pipeline) -> None:
        result = PipelineResult(
            timestamp=datetime(2026, 4, 18, 13, 0, 0),
            games_analyzed=2,
            polymarket_markets_found=2,
            edges_detected=1,
            edges=[
                _edge("g1", actionable=True, signal="BET", edge_pp=6.2),
                _edge("g2", actionable=False, signal="SKIP", edge_pp=1.0),
            ],
            warnings=["LINEUP NOT CONFIRMED: NYY @ BOS"],
            execution_time_seconds=1.2,
            telegram_sent=True,
        )
        mock_run_pipeline.return_value = result

        returned = main.run_with_real_bets_logging()
        self.assertEqual(returned.edges_detected, 1)

        runs_root = self.test_root / "real_bets" / "runs"
        run_json_files = list(runs_root.rglob("*.json"))
        run_log_files = list(runs_root.rglob("*.log"))
        self.assertEqual(len(run_json_files), 1)
        self.assertEqual(len(run_log_files), 1)

        payload = json.loads(run_json_files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["run_status"], "success")
        self.assertTrue(payload["telegram_sent"])
        self.assertIn("reliability_gate", payload["pipeline_summary"])

        daily_files = list((self.test_root / "real_bets" / "daily").glob("*.jsonl"))
        self.assertEqual(len(daily_files), 1)
        lines = daily_files[0].read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual(row["signal"], "BET")
        self.assertTrue(row["actionable"])
        self.assertEqual(row["lineup_warnings"], ["LINEUP NOT CONFIRMED: NYY @ BOS"])

    @patch("main.run_pipeline")
    def test_failure_run_still_writes_failed_artifacts(self, mock_run_pipeline) -> None:
        mock_run_pipeline.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            main.run_with_real_bets_logging()

        runs_root = self.test_root / "real_bets" / "runs"
        run_json_files = list(runs_root.rglob("*.json"))
        run_log_files = list(runs_root.rglob("*.log"))
        self.assertEqual(len(run_json_files), 1)
        self.assertEqual(len(run_log_files), 1)

        payload = json.loads(run_json_files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["run_status"], "failed")
        self.assertIn("RuntimeError", payload["error_message"])


if __name__ == "__main__":
    unittest.main()
