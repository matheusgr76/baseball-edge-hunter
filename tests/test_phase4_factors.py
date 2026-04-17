import unittest
from datetime import datetime

from calibration.factors import calibrate_game
from calibration.phase4 import (
    oaa_defense_factor,
    park_factor,
    pythagorean_regression_factor,
    umpire_tendency_factor,
    wrc_handedness_factor,
)
from models import CanonicalGame, ProbablePitcher


class Phase4FactorsTests(unittest.TestCase):
    def test_park_factor_applies_home_side_adjustment(self):
        home_factor, away_factor, home_adj, away_adj = park_factor(
            home_team="Colorado Rockies",
            away_team="Los Angeles Dodgers",
            park_factors={"Colorado Rockies": 112.0},
        )

        self.assertGreater(home_adj, 0.0)
        self.assertLess(away_adj, 0.0)
        self.assertAlmostEqual(home_adj, -away_adj, places=2)
        self.assertEqual(home_factor.name, "PARK FACTOR")

    def test_wrc_handedness_factor_uses_opposing_starter_hand(self):
        home_sp = ProbablePitcher(
            team="Boston Red Sox",
            name="Home SP",
            player_id=1,
            fip=4.0,
            era=4.0,
            ip=80.0,
            hand="R",
        )
        away_sp = ProbablePitcher(
            team="New York Yankees",
            name="Away SP",
            player_id=2,
            fip=4.0,
            era=4.0,
            ip=80.0,
            hand="L",
        )
        splits = {
            "Boston Red Sox": {"vs_lhp": 112.0, "vs_rhp": 98.0},
            "New York Yankees": {"vs_lhp": 95.0, "vs_rhp": 101.0},
        }

        _, _, home_adj, away_adj = wrc_handedness_factor(
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            home_sp=home_sp,
            away_sp=away_sp,
            wrc_plus_splits=splits,
        )

        self.assertGreater(home_adj, 0.0)
        self.assertLess(away_adj, 0.0)

    def test_pythag_and_oaa_factors_behave_directionally(self):
        _, _, home_pyth, away_pyth = pythagorean_regression_factor(
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            team_run_profiles={
                "Boston Red Sox": {"delta_pp": 4.0},
                "New York Yankees": {"delta_pp": -2.0},
            },
        )
        self.assertLess(home_pyth, 0.0)   # Overperforming team regresses down
        self.assertGreater(away_pyth, 0.0)

        _, _, home_oaa, away_oaa = oaa_defense_factor(
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            team_oaa={"Boston Red Sox": 12.0, "New York Yankees": -8.0},
        )
        self.assertGreater(home_oaa, 0.0)
        self.assertLess(away_oaa, 0.0)

    def test_umpire_factor_uses_named_bias(self):
        _, _, home_adj, away_adj = umpire_tendency_factor(
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            umpire_name="Joe Test",
            umpire_tendencies={"Joe Test": 0.9},
        )
        self.assertAlmostEqual(home_adj, 0.9, places=2)
        self.assertAlmostEqual(away_adj, -0.9, places=2)

    def test_calibrate_game_includes_phase4_adjustments(self):
        game = CanonicalGame(
            game_id="game-1",
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            commence_time=datetime(2026, 4, 12, 18, 0, 0),
            home_prob=52.0,
            away_prob=48.0,
            favorite="home",
            num_bookmakers=5,
            bookmaker_std_pp=1.1,
        )
        home_sp = ProbablePitcher(
            team="Boston Red Sox",
            name="Home SP",
            player_id=1,
            fip=3.4,
            era=3.5,
            ip=90.0,
            hand="R",
        )
        away_sp = ProbablePitcher(
            team="New York Yankees",
            name="Away SP",
            player_id=2,
            fip=4.7,
            era=4.6,
            ip=88.0,
            hand="L",
        )

        calibrated = calibrate_game(
            game,
            home_sp=home_sp,
            away_sp=away_sp,
            park_factors={"Boston Red Sox": 105.0},
            wrc_plus_splits={
                "Boston Red Sox": {"vs_lhp": 110.0, "vs_rhp": 97.0},
                "New York Yankees": {"vs_lhp": 96.0, "vs_rhp": 102.0},
            },
            team_run_profiles={
                "Boston Red Sox": {"delta_pp": 2.5},
                "New York Yankees": {"delta_pp": -1.5},
            },
            team_oaa={"Boston Red Sox": 5.0, "New York Yankees": -3.0},
            umpire_name="Joe Test",
            umpire_tendencies={"Joe Test": 0.7},
        )

        self.assertEqual(len(calibrated.home_factors), 7)
        self.assertEqual(len(calibrated.away_factors), 7)
        self.assertNotEqual(calibrated.home_adjustments.park_factor, 0.0)
        self.assertNotEqual(calibrated.home_adjustments.wrc_handedness, 0.0)
        self.assertNotEqual(calibrated.home_adjustments.pythagorean_regression, 0.0)
        self.assertNotEqual(calibrated.home_adjustments.oaa_defense, 0.0)
        self.assertNotEqual(calibrated.home_adjustments.umpire_tendency, 0.0)


if __name__ == "__main__":
    unittest.main()
