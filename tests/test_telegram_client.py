import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import config
from models import EdgeAnalysis
from orchestration.telegram_client import format_telegram_message, send_telegram_message


class TelegramClientTests(unittest.TestCase):
    def test_format_telegram_message_with_actionable_edges_and_lineup_warning(self):
        commence_time = datetime(2026, 4, 4, 19, 0, 0)
        home_edge = EdgeAnalysis(
            game_id="game-1",
            team="home",
            team_name="Boston Red Sox",
            opponent="New York Yankees",
            commence_time=commence_time,
            consensus_prob=52.0,
            true_prob=56.0,
            polymarket_prob=49.0,
            edge_pp=7.0,
            signal="STRONG BET",
            confidence_pct=84,
            actionable=True,
        )
        away_edge = EdgeAnalysis(
            game_id="game-1",
            team="away",
            team_name="New York Yankees",
            opponent="Boston Red Sox",
            commence_time=commence_time,
            consensus_prob=48.0,
            true_prob=44.0,
            polymarket_prob=51.0,
            edge_pp=-7.0,
            signal="AVOID",
            confidence_pct=84,
            actionable=False,
        )

        message = format_telegram_message(
            [home_edge, away_edge],
            warnings=[
                "LINEUP NOT CONFIRMED: New York Yankees @ Boston Red Sox — verify before acting on any signal",
                "Some unrelated warning",
            ],
        )

        self.assertIn("MLB EDGE HUNTER - Betting Signals", message)
        self.assertIn("NYY@BOS", message)
        self.assertIn("🎯 Actionable edges: 1", message)
        self.assertIn("Boston Red Sox", message)
        self.assertIn("⚠️ Lineup warnings", message)
        self.assertIn("LINEUP NOT CONFIRMED", message)
        self.assertIn("🔥", message)
        self.assertNotIn("Some unrelated warning", message)

    def test_format_telegram_message_with_no_edges(self):
        message = format_telegram_message([], warnings=[])

        self.assertIn("MLB EDGE HUNTER - Betting Signals", message)
        self.assertIn("No games analyzed today", message)

    def test_format_telegram_message_dedupes_lineup_warnings(self):
        message = format_telegram_message(
            [],
            warnings=[
                "LINEUP NOT CONFIRMED: Team A @ Team B — verify before acting on any signal",
                "LINEUP NOT CONFIRMED: Team A @ Team B — verify before acting on any signal",
            ],
        )

        self.assertEqual(message.count("LINEUP NOT CONFIRMED: Team A @ Team B"), 1)

    @patch.object(config, "TELEGRAM_BOT_TOKEN", "")
    @patch.object(config, "TELEGRAM_CHAT_ID", "")
    def test_send_telegram_message_skips_when_credentials_missing(self):
        result = send_telegram_message("hello")

        self.assertFalse(result)

    @patch.object(config, "TELEGRAM_BOT_TOKEN", "token")
    @patch.object(config, "TELEGRAM_CHAT_ID", "chat")
    @patch("orchestration.telegram_client.requests.post")
    def test_send_telegram_message_posts_to_telegram(self, mock_post):
        response = Mock()
        response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_post.return_value = response

        result = send_telegram_message("hello")

        self.assertEqual(result["result"]["message_id"], 123)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["chat_id"], "chat")
        self.assertEqual(kwargs["json"]["text"], "hello")
        self.assertEqual(kwargs["json"]["parse_mode"], "HTML")


if __name__ == "__main__":
    unittest.main()
