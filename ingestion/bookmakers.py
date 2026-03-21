"""
Ingestion Layer - Bookmakers
Fetches MLB moneyline (h2h) odds from The Odds API
"""

import requests
from typing import List
from datetime import datetime
from models import RawBookmakerOdds
import config


_HEADERS = {"User-Agent": "mlb-edge-hunter/1.0"}


def fetch_bookmaker_odds() -> List[RawBookmakerOdds]:
    """
    Fetch today's MLB games from The Odds API.

    Returns:
        List of RawBookmakerOdds — one entry per bookmaker per game.
        Returns empty list on API error (caller handles graceful degradation).
    """
    url = f"{config.ODDS_API_BASE}/sports/{config.ODDS_SPORT}/odds"
    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": config.ODDS_REGIONS,
        "markets": config.ODDS_MARKETS,
        "oddsFormat": "american",
        "bookmakers": config.ODDS_BOOKMAKERS,
    }

    print(f"  📡 Fetching bookmaker odds ({config.ODDS_SPORT})...")

    try:
        response = requests.get(
            url, params=params, headers=_HEADERS, timeout=config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"  ⚠️  Odds API HTTP error: {e}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  Odds API request failed: {e}")
        return []

    data = response.json()
    raw_odds: List[RawBookmakerOdds] = []

    for event in data:
        sport_key = event.get("sport_key", "baseball_mlb")
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
                            timestamp=datetime.now(),
                            sport_key=sport_key,
                            commence_time=commence_time,
                        )
                    )

    game_count = len({(o.home_team, o.away_team) for o in raw_odds})
    print(f"  ✓ Bookmaker odds: {game_count} games, {len(raw_odds)} lines fetched")
    return raw_odds


def get_unique_games(raw_odds: List[RawBookmakerOdds]) -> List[tuple]:
    """
    Extract unique game matchups from raw odds.

    Returns:
        List of (home_team, away_team, commence_time) tuples, deduplicated.
    """
    seen: set = set()
    games = []
    for o in raw_odds:
        key = (o.home_team, o.away_team, o.commence_time)
        if key not in seen:
            seen.add(key)
            games.append(key)
    return games
