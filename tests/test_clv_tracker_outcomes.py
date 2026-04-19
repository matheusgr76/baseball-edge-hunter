import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import uuid

from output import clv_tracker


class ClvTrackerOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_log_file = clv_tracker._LOG_FILE
        test_dir = Path("output") / "_test_artifacts"
        test_dir.mkdir(parents=True, exist_ok=True)
        self._test_file = test_dir / f"predictions_log_{uuid.uuid4().hex}.json"
        clv_tracker._LOG_FILE = str(self._test_file)

    def tearDown(self) -> None:
        clv_tracker._LOG_FILE = self._old_log_file
        if self._test_file.exists():
            self._test_file.unlink()

    def _write_entries(self, entries) -> None:
        path = Path(clv_tracker._LOG_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _read_entries(self):
        return json.loads(Path(clv_tracker._LOG_FILE).read_text(encoding="utf-8"))

    def test_outcome_summary_counts_actionable_rows(self) -> None:
        self._write_entries(
            [
                {"actionable": True, "picked_team_won": True},
                {"actionable": True, "picked_team_won": False},
                {"actionable": True, "picked_team_won": None},
                {"actionable": False, "picked_team_won": True},
            ]
        )

        summary = clv_tracker.outcome_summary()

        self.assertEqual(summary["actionable_total"], 3)
        self.assertEqual(summary["actionable_resolved"], 2)
        self.assertEqual(summary["actionable_wins"], 1)
        self.assertEqual(summary["actionable_losses"], 1)
        self.assertEqual(summary["actionable_win_rate_pct"], 50.0)

    def test_reliability_gate_status_requires_dual_gate(self) -> None:
        self._write_entries(
            [
                {"actionable": True, "picked_team_won": True},
                {"actionable": True, "picked_team_won": False},
                {"actionable": True, "picked_team_won": None},
            ]
        )

        gate = clv_tracker.reliability_gate_status()

        self.assertFalse(gate["dual_gate_met"])
        self.assertEqual(gate["resolved_actionable"], 2)
        self.assertGreater(gate["resolved_remaining"], 0)
        self.assertTrue(gate["resolved_required"] >= 20)
        self.assertTrue(gate["win_rate_required_pct"] >= 55.0)

    def test_reliability_gate_status_met_when_conditions_pass(self) -> None:
        self._write_entries(
            [{"actionable": True, "picked_team_won": True} for _ in range(20)]
        )

        gate = clv_tracker.reliability_gate_status()

        self.assertTrue(gate["resolved_ok"])
        self.assertTrue(gate["win_rate_ok"])
        self.assertTrue(gate["dual_gate_met"])
        self.assertTrue(gate["retuning_allowed"])
        self.assertEqual(gate["resolved_remaining"], 0)
        self.assertEqual(gate["win_rate_gap_pct"], 0.0)

    @patch("output.clv_tracker._fetch_final_games_for_date")
    def test_resolve_game_outcomes_updates_actionable_entries(
        self,
        mock_fetch_final_games_for_date,
    ) -> None:
        commence = datetime.now(timezone.utc) - timedelta(days=2)
        commence_iso = commence.isoformat()
        entries = [
            {
                "entry_id": "g1_home",
                "team_name": "Boston Red Sox",
                "opponent": "New York Yankees",
                "commence_time": commence_iso,
                "actionable": True,
                "picked_team_won": None,
            },
            {
                "entry_id": "g1_away",
                "team_name": "New York Yankees",
                "opponent": "Boston Red Sox",
                "commence_time": commence_iso,
                "actionable": False,
                "picked_team_won": None,
            },
        ]
        self._write_entries(entries)

        mock_fetch_final_games_for_date.return_value = [
            {
                "home_team": "Boston Red Sox",
                "away_team": "New York Yankees",
                "winner": "Boston Red Sox",
                "game_date": commence.date().isoformat(),
                "game_time": commence,
            }
        ]

        result = clv_tracker.resolve_game_outcomes(actionable_only=True)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["actionable_updated"], 1)

        updated_entries = self._read_entries()
        actionable_row = updated_entries[0]
        non_actionable_row = updated_entries[1]

        self.assertEqual(actionable_row["final_winner"], "Boston Red Sox")
        self.assertTrue(actionable_row["picked_team_won"])
        self.assertIsNotNone(actionable_row["game_resolved_at"])
        self.assertIsNone(non_actionable_row["picked_team_won"])


if __name__ == "__main__":
    unittest.main()
