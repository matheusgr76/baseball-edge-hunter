"""
MLB Edge Hunter - Telegram Client
Safe outbound Telegram summary delivery for completed pipeline runs.
"""

from __future__ import annotations

import html
import logging
from typing import Iterable, List, Optional

import requests

import config
from models import EdgeAnalysis
from output.report_formatter import _build_summary_rows

logger = logging.getLogger(__name__)

_ACTIONABLE_SIGNALS = {"STRONG BET", "BET"}
_LINEUP_WARNING_PREFIX = "LINEUP NOT CONFIRMED"
_VERDICT_EMOJI = {
    "STRONG BET": "🔥",
    "BET": "✅",
    "SKIP": "🔶",
    "FADE": "🔄",
    "AVOID": "⛔",
}


def send_telegram_message(text: str) -> dict | bool:
    """
    Send an HTML-formatted message to the configured Telegram chat.
    Returns the Telegram response JSON on success, False otherwise.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing. Skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        if not data.get("ok"):
            logger.error("Telegram API error: %s", data.get("description"))
            return False
        return data
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        return False


def format_telegram_message(
    all_edges: List[EdgeAnalysis],
    warnings: Optional[Iterable[str]] = None,
) -> str:
    """
    Format the final Telegram summary in the same spirit as basketball_edge_hunter:
    bold header, monospace table, and inline verdict emojis.
    """
    summary_rows = _build_summary_rows(all_edges)
    actionable_rows = [row for row in summary_rows if row["signal"] in _ACTIONABLE_SIGNALS]
    lineup_warnings = _extract_lineup_warnings(warnings or [])

    lines = ["<b>⚾ MLB EDGE HUNTER - Betting Signals</b>", ""]

    if summary_rows:
        lines.append("<pre><code class=\"language-diff\">")
        lines.append(
            f"   {'GAME':<8} | {'FAV':<5} | {'T%':>2} | {'P%':>2} | {'C%':>2} | {'E':^5} | VERDICT"
        )
        lines.append(
            f"   {'-' * 8}-+-{'-' * 5}-+-{'-' * 2}-+-{'-' * 2}-+-{'-' * 2}-+-{'-' * 5}-+-{'-' * 10}"
        )
        for row in summary_rows:
            emoji = _VERDICT_EMOJI.get(str(row["signal"]), "")
            game = html.escape(f"{row['game']:<8}")
            fav = html.escape(f"{row['fav']:<5}")
            verdict = html.escape(f"{row['verdict']:<10}")
            lines.append(
                f"{row['prefix']} {game} | {fav} | "
                f"{row['true_pct']:>2} | {row['poly_pct']:>2} | {row['conf_pct']:>2} | "
                f"{row['edge']:>+5.1f} | {verdict} {emoji}"
            )
        lines.append("</code></pre>")
    else:
        lines.append("🤷 No games analyzed today.")

    if actionable_rows:
        lines.append("")
        lines.append(f"<b>🎯 Actionable edges: {len(actionable_rows)}</b>")
        for row in actionable_rows:
            emoji = _VERDICT_EMOJI.get(str(row["signal"]), "")
            lines.append(
                f"• {html.escape(str(row['fav_full']))}: "
                f"{row['edge']:+.2f}pp | T={row['true_pct']}% P={row['poly_pct']}% C={row['conf_pct']} {emoji}"
            )
    elif summary_rows:
        lines.append("")
        lines.append("⏳ No actionable edges today.")
        lines.append("Markets look efficient right now. No bets to push.")

    if lineup_warnings:
        lines.append("")
        lines.append("<b>⚠️ Lineup warnings</b>")
        for warning in lineup_warnings:
            lines.append(f"• {html.escape(warning)}")

    return "\n".join(lines).strip()


def _extract_lineup_warnings(warnings: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for warning in warnings:
        normalized = warning.strip()
        if not normalized:
            continue
        if _LINEUP_WARNING_PREFIX in normalized and normalized not in seen:
            cleaned.append(normalized)
            seen.add(normalized)
    return cleaned
