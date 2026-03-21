"""
Backtesting - Historical Odds Fetcher
Fetches historical bookmaker odds from The Odds API (paid tier required).

The Odds API historical endpoint:
  GET /v4/sports/{sport}/odds-history
  Parameters: apiKey, regions, markets, date (ISO 8601 snapshot time)

NOTE: This endpoint requires a paid tier plan. On a free key the endpoint
returns HTTP 401/403. We handle this gracefully: on failure we attempt to
fall back to the standard /odds endpoint (today's odds) so the backtest
can still run in a degraded mode using live odds as a proxy.

The caller (backtester.py) decides whether to proceed or abort based on
the return value. An empty list means no odds could be retrieved.
"""

import time
import requests
from datetime import datetime, timezone
from typing import List, Optional

import config
from models import RawBookmakerOdds

_HEADERS = {"User-Agent": "mlb-edge-hunter-backtest/1.0"}
_HISTORY_URL = f"{config.ODDS_API_BASE}/sports/{config.ODDS_SPORT}/odds-history"
_LIVE_URL = f"{config.ODDS_API_BASE}/sports/{config.ODDS_SPORT}/odds"


def fetch_historical_odds(snapshot_date: str) -> List[RawBookmakerOdds]:
    """
    Fetch historical bookmaker odds for a given UTC snapshot date.

    Args:
        snapshot_date: ISO 8601 datetime string, e.g. "2024-04-01T18:00:00Z"
                       The API returns odds as they appeared at that moment.

    Returns:
        List of RawBookmakerOdds. Empty list on any error.
    """
    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": config.ODDS_REGIONS,
        "markets": config.ODDS_MARKETS,
        "oddsFormat": "american",
        "bookmakers": config.ODDS_BOOKMAKERS,
        "date": snapshot_date,
    }

    try:
        response = requests.get(
            _HISTORY_URL,
            params=params,
            headers=_HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        )

        if response.status_code in (401, 403):
            print(
                f"  ⚠️  Historical odds API requires paid tier "
                f"(HTTP {response.status_code}). "
                "Falling back to live odds for this slot."
            )
            return _fetch_live_odds_fallback()

        response.raise_for_status()

    except requests.exceptions.RequestException as exc:
        print(f"  ⚠️  Historical odds request failed: {exc}")
        return []

    data = response.json()
    # History endpoint wraps results in {"data": [...]}
    if isinstance(data, dict) and "data" in data:
        events = data["data"]
    elif isinstance(data, list):
        events = data
    else:
        print(f"  ⚠️  Unexpected historical odds response shape")
        return []

    return _parse_events(events, snapshot_date)


def _fetch_live_odds_fallback() -> List[RawBookmakerOdds]:
    """
    Use the standard live-odds endpoint as a fallback.
    Useful for testing on a free API key.
    """
    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": config.ODDS_REGIONS,
        "markets": config.ODDS_MARKETS,
        "oddsFormat": "american",
        "bookmakers": config.ODDS_BOOKMAKERS,
    }
    try:
        response = requests.get(
            _LIVE_URL,
            params=params,
            headers=_HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"  ⚠️  Live odds fallback failed: {exc}")
        return []

    return _parse_events(response.json(), snapshot="live-fallback")


def _parse_events(events: list, snapshot: str) -> List[RawBookmakerOdds]:
    """Parse a list of Odds API event objects into RawBookmakerOdds."""
    raw_odds: List[RawBookmakerOdds] = []

    for event in events:
        sport_key = event.get("sport_key", config.ODDS_SPORT)
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        commence_str = event.get("commence_time", "")

        try:
            commence_time = datetime.fromisoformat(
                commence_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            continue

        for bookmaker_data in event.get("bookmakers", []):
            bookmaker = bookmaker_data.get("key", "")

            for market in bookmaker_data.get("markets", []):
                if market.get("key") != "h2h":
                    continue

                home_odds = None
                away_odds = None

                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    price = outcome.get("price")
                    if name == home_team:
                        home_odds = price
                    elif name == away_team:
                        away_odds = price

                if home_odds is not None and away_odds is not None:
                    raw_odds.append(
                        RawBookmakerOdds(
                            bookmaker=bookmaker,
                            home_team=home_team,
                            away_team=away_team,
                            home_odds=int(home_odds),
                            away_odds=int(away_odds),
                            timestamp=datetime.now(timezone.utc),
                            sport_key=sport_key,
                            commence_time=commence_time,
                        )
                    )

    game_count = len({(o.home_team, o.away_team) for o in raw_odds})
    print(
        f"  ✓ Historical odds ({snapshot}): "
        f"{game_count} games, {len(raw_odds)} lines"
    )
    return raw_odds
