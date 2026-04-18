import unittest
from datetime import datetime
from unittest.mock import patch

from models import (
    AdjustmentBreakdown,
    CalibratedGame,
    CanonicalGame,
    EdgeAnalysis,
    PolymarketOpportunity,
    RawBookmakerOdds,
)
from orchestration.pipeline import run_pipeline


class PipelineTelegramTests(unittest.TestCase):
    @patch("orchestration.pipeline.send_telegram_message")
    @patch("orchestration.pipeline.format_telegram_message")
    @patch("orchestration.pipeline.print_pnl_chart")
    @patch("orchestration.pipeline.print_weekly_summary")
    @patch("orchestration.pipeline.print_clv_summary")
    @patch("orchestration.pipeline.resolve_game_outcomes")
    @patch("orchestration.pipeline.export_csv")
    @patch("orchestration.pipeline.log_signals")
    @patch("orchestration.pipeline.save_daily_report")
    @patch("orchestration.pipeline.print_session_summary")
    @patch("orchestration.pipeline.print_game_section")
    @patch("orchestration.pipeline.rank_by_edge")
    @patch("orchestration.pipeline.calculate_edge")
    @patch("orchestration.pipeline.get_polymarket_odds")
    @patch("orchestration.pipeline.calibrate_game")
    @patch("orchestration.pipeline.fetch_bullpen_status")
    @patch("orchestration.pipeline.fetch_lineup_status")
    @patch("orchestration.pipeline.fetch_probable_pitchers")
    @patch("orchestration.pipeline.calculate_consensus")
    @patch("orchestration.pipeline.get_unique_games")
    @patch("orchestration.pipeline.fetch_bookmaker_odds")
    @patch("orchestration.pipeline.print_session_header")
    @patch("builtins.print")
    def test_pipeline_sends_one_final_telegram_message(
        self,
        mock_print,
        mock_print_session_header,
        mock_fetch_bookmaker_odds,
        mock_get_unique_games,
        mock_calculate_consensus,
        mock_fetch_probable_pitchers,
        mock_fetch_lineup_status,
        mock_fetch_bullpen_status,
        mock_calibrate_game,
        mock_get_polymarket_odds,
        mock_calculate_edge,
        mock_rank_by_edge,
        mock_print_game_section,
        mock_print_session_summary,
        mock_save_daily_report,
        mock_log_signals,
        mock_export_csv,
        mock_resolve_game_outcomes,
        mock_print_clv_summary,
        mock_print_weekly_summary,
        mock_print_pnl_chart,
        mock_format_telegram_message,
        mock_send_telegram_message,
    ):
        commence_time = datetime(2026, 4, 4, 19, 0, 0)
        raw_odds = RawBookmakerOdds(
            bookmaker="pinnacle",
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            home_odds=-110,
            away_odds=100,
            timestamp=datetime(2026, 4, 4, 10, 0, 0),
            sport_key="baseball_mlb",
            commence_time=commence_time,
        )

        canonical = CanonicalGame(
            game_id="game-1",
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            commence_time=commence_time,
            home_prob=52.0,
            away_prob=48.0,
            favorite="home",
            num_bookmakers=3,
            raw_sources=[raw_odds],
        )

        calibrated = CalibratedGame(
            game_id="game-1",
            home_team="Boston Red Sox",
            away_team="New York Yankees",
            commence_time=commence_time,
            consensus_home_prob=52.0,
            consensus_away_prob=48.0,
            true_home_prob=55.0,
            true_away_prob=45.0,
            home_adjustments=AdjustmentBreakdown(),
            away_adjustments=AdjustmentBreakdown(),
            favorite="home",
            num_bookmakers=3,
        )

        home_poly = PolymarketOpportunity(
            game_id="game-1",
            condition_id="c1",
            question="Will Boston win?",
            team="home",
            team_name="Boston Red Sox",
            polymarket_prob=49.0,
            end_date=commence_time,
            volume=1000.0,
            liquidity=2000.0,
            market_slug="mlb-nyy-bos-2026-04-04",
        )
        away_poly = PolymarketOpportunity(
            game_id="game-1",
            condition_id="c1",
            question="Will New York win?",
            team="away",
            team_name="New York Yankees",
            polymarket_prob=51.0,
            end_date=commence_time,
            volume=1000.0,
            liquidity=2000.0,
            market_slug="mlb-nyy-bos-2026-04-04",
        )

        home_edge = EdgeAnalysis(
            game_id="game-1",
            team="home",
            team_name="Boston Red Sox",
            opponent="New York Yankees",
            commence_time=commence_time,
            consensus_prob=52.0,
            true_prob=55.0,
            polymarket_prob=49.0,
            edge_pp=6.0,
            signal="STRONG BET",
            confidence_pct=85,
            actionable=True,
        )
        away_edge = EdgeAnalysis(
            game_id="game-1",
            team="away",
            team_name="New York Yankees",
            opponent="Boston Red Sox",
            commence_time=commence_time,
            consensus_prob=48.0,
            true_prob=45.0,
            polymarket_prob=51.0,
            edge_pp=-6.0,
            signal="AVOID",
            confidence_pct=85,
            actionable=False,
        )

        mock_fetch_bookmaker_odds.return_value = [raw_odds]
        mock_get_unique_games.return_value = [
            ("Boston Red Sox", "New York Yankees", commence_time)
        ]
        mock_calculate_consensus.return_value = canonical
        mock_fetch_probable_pitchers.return_value = {}
        mock_fetch_lineup_status.return_value = {
            ("Boston Red Sox", "New York Yankees"): False
        }
        mock_fetch_bullpen_status.return_value = None
        mock_calibrate_game.return_value = calibrated
        mock_get_polymarket_odds.return_value = (home_poly, away_poly)
        mock_calculate_edge.return_value = [home_edge, away_edge]
        mock_rank_by_edge.return_value = [home_edge, away_edge]
        mock_log_signals.return_value = 1
        mock_resolve_game_outcomes.return_value = {
            "entries_scanned": 2,
            "eligible_unresolved": 0,
            "updated": 0,
            "actionable_updated": 0,
            "requested_dates": 0,
        }
        mock_format_telegram_message.return_value = "telegram summary"
        mock_send_telegram_message.return_value = {"ok": True}

        result = run_pipeline()

        self.assertEqual(result.edges_detected, 1)
        mock_format_telegram_message.assert_called_once()
        format_args, format_kwargs = mock_format_telegram_message.call_args
        self.assertEqual(format_args[0], [home_edge, away_edge])
        self.assertEqual(len(format_kwargs["warnings"]), 1)
        self.assertIn("LINEUP NOT CONFIRMED", format_kwargs["warnings"][0])
        mock_send_telegram_message.assert_called_once_with("telegram summary")
        mock_print_game_section.assert_called_once()
        mock_save_daily_report.assert_called_once()
        mock_export_csv.assert_called_once()


if __name__ == "__main__":
    unittest.main()
