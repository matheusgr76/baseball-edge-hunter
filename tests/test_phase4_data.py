import json
import unittest
from pathlib import Path
import shutil
import uuid
from unittest.mock import Mock, patch

from ingestion.phase4_data import (
    fetch_home_plate_umpires,
    fetch_team_run_profiles,
    load_park_factors,
    load_team_oaa,
    load_umpire_tendencies,
    load_wrc_plus_splits,
)


class Phase4DataTests(unittest.TestCase):
    def test_loaders_accept_nested_team_maps(self):
        base = Path("tests/.tmp_phase4") / uuid.uuid4().hex
        base.mkdir(parents=True, exist_ok=True)

        try:
            (base / "park.json").write_text(
                json.dumps({"teams": {"Athletics": 97.0}}),
                encoding="utf-8",
            )
            (base / "wrc.json").write_text(
                json.dumps({"teams": {"Athletics": {"vs_lhp": 102, "vs_rhp": 98}}}),
                encoding="utf-8",
            )
            (base / "oaa.json").write_text(
                json.dumps({"teams": {"Athletics": 4.0}}),
                encoding="utf-8",
            )
            (base / "ump.json").write_text(
                json.dumps({"umpires": {"Joe Test": 0.8}}),
                encoding="utf-8",
            )

            park = load_park_factors(str(base / "park.json"))
            wrc = load_wrc_plus_splits(str(base / "wrc.json"))
            oaa = load_team_oaa(str(base / "oaa.json"))
            ump = load_umpire_tendencies(str(base / "ump.json"))

            self.assertIn("Oakland Athletics", park)
            self.assertEqual(wrc["Oakland Athletics"]["vs_lhp"], 102.0)
            self.assertEqual(oaa["Oakland Athletics"], 4.0)
            self.assertEqual(ump["Joe Test"], 0.8)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    @patch("ingestion.phase4_data.requests.get")
    def test_fetch_home_plate_umpires_parses_schedule_officials(self, mock_get):
        payload = {
            "dates": [
                {
                    "games": [
                        {
                            "teams": {
                                "home": {"team": {"name": "Boston Red Sox"}},
                                "away": {"team": {"name": "New York Yankees"}},
                            },
                            "officials": [
                                {
                                    "officialType": "Home Plate",
                                    "official": {"fullName": "Jordan Baker"},
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        out = fetch_home_plate_umpires("2026-04-12")
        self.assertEqual(
            out[("Boston Red Sox", "New York Yankees")],
            "Jordan Baker",
        )

    @patch("ingestion.phase4_data.requests.get")
    def test_fetch_team_run_profiles_computes_delta(self, mock_get):
        payload = {
            "records": [
                {
                    "teamRecords": [
                        {
                            "team": {"name": "Boston Red Sox"},
                            "wins": 12,
                            "losses": 8,
                            "runsScored": 96,
                            "runsAllowed": 88,
                        }
                    ]
                }
            ]
        }
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        profiles = fetch_team_run_profiles("2026-04-12")
        self.assertIn("Boston Red Sox", profiles)
        self.assertIn("delta_pp", profiles["Boston Red Sox"])


if __name__ == "__main__":
    unittest.main()
