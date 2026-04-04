"""
MLB Edge Hunter - Entry Point

Usage:
  python main.py

Optional env vars for outbound Telegram summary:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

from orchestration.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()
