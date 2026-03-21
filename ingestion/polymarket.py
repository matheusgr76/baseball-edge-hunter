"""
Ingestion Layer - Polymarket
Fetches MLB markets from Gamma API using direct slug construction.
Polymarket is the gatekeeper: games without markets are silently skipped.
"""

import json
import requests
from typing import Optional, Tuple
from datetime import datetime
from models import RawPolymarketMarket, PolymarketOpportunity
from normalization.teams import get_polymarket_abbr, normalize_team_name
import config


_HEADERS = {"User-Agent": "mlb-edge-hunter/1.0"}


def build_slug(away_canonical: str, home_canonical: str, game_date: datetime) -> str:
    """
    Construct Polymarket market slug.
    Pattern: mlb-{away_abbr}-{home_abbr}-{YYYY-MM-DD}
    """
    away_abbr = get_polymarket_abbr(away_canonical)
    home_abbr = get_polymarket_abbr(home_canonical)
    date_str = game_date.strftime("%Y-%m-%d")
    return f"{config.POLYMARKET_SLUG_PREFIX}-{away_abbr}-{home_abbr}-{date_str}"


def _fetch_raw_market(slug: str) -> Optional[RawPolymarketMarket]:
    """
    Fetch a single market by slug from Gamma API.
    Returns None if 404, low liquidity, or any fetch error.
    """
    url = f"{config.GAMMA_API_BASE}/markets/slug/{slug}"

    try:
        response = requests.get(url, headers=_HEADERS, timeout=config.REQUEST_TIMEOUT)
    except requests.exceptions.RequestException:
        return None

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
        market = response.json()
    except Exception:
        return None

    liquidity = float(market.get("liquidity", 0) or 0)
    if liquidity < config.MIN_POLYMARKET_LIQUIDITY:
        if config.DEBUG_MODE:
            print(f"  ⚠️  Skip {slug}: low liquidity (${liquidity:,.0f})")
        return None

    # Parse outcomes (may be JSON string or list)
    outcomes_raw = market.get("outcomes", "[]")
    try:
        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
    except (json.JSONDecodeError, TypeError):
        outcomes = []

    # Parse prices (may be JSON string or list of string floats)
    prices_raw = market.get("outcomePrices", "[]")
    try:
        prices_list = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
        outcome_prices = [float(p) for p in prices_list]
    except (json.JSONDecodeError, TypeError, ValueError):
        outcome_prices = []

    end_date_str = market.get("endDate") or market.get("end_date_iso", "")
    try:
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        end_date = datetime.now()

    return RawPolymarketMarket(
        condition_id=market.get("conditionId", ""),
        question=market.get("question", ""),
        outcomes=outcomes,
        outcome_prices=outcome_prices,
        end_date=end_date,
        volume=float(market.get("volume", 0) or 0),
        liquidity=liquidity,
        market_slug=slug,
    )


def get_polymarket_odds(
    away_canonical: str,
    home_canonical: str,
    game_date: datetime,
    game_id: str,
) -> Optional[Tuple[PolymarketOpportunity, PolymarketOpportunity]]:
    """
    Fetch Polymarket market for one game and return (home_opp, away_opp).

    Returns None if no market exists or liquidity is too low.
    The caller must skip games where this returns None (Polymarket gatekeeper rule).
    """
    slug = build_slug(away_canonical, home_canonical, game_date)
    market = _fetch_raw_market(slug)

    if market is None:
        return None

    # Outcome ordering: Polymarket typically lists home team first for MLB.
    # IMPORTANT: verify this against actual API response on first live run.
    # The outcomes list contains team names; we match them to home/away.
    outcomes = market.outcomes
    prices = market.outcome_prices

    if len(outcomes) < 2 or len(prices) < 2:
        print(f"  ⚠️  Unexpected market structure for {slug}: {outcomes}")
        return None

    # Match outcomes to home/away by name similarity
    home_idx, away_idx = _match_outcome_indices(outcomes, home_canonical, away_canonical)

    if home_idx is None or away_idx is None:
        # Fallback: assume index 0=home, 1=away (common Polymarket convention)
        home_idx, away_idx = 0, 1
        if config.DEBUG_MODE:
            print(f"  ⚠️  Outcome matching fallback for {slug}: {outcomes}")

    home_price = prices[home_idx] * 100  # Convert 0-1 → 0-100
    away_price = prices[away_idx] * 100

    print(
        f"  ✓ Polymarket: {away_canonical} @ {home_canonical} "
        f"(${market.liquidity:,.0f}) — home={home_price:.1f}% away={away_price:.1f}%"
    )

    home_opp = PolymarketOpportunity(
        game_id=game_id,
        condition_id=market.condition_id,
        question=market.question,
        team="home",
        team_name=home_canonical,
        polymarket_prob=round(home_price, 2),
        end_date=market.end_date,
        volume=market.volume,
        liquidity=market.liquidity,
        market_slug=slug,
    )
    away_opp = PolymarketOpportunity(
        game_id=game_id,
        condition_id=market.condition_id,
        question=market.question,
        team="away",
        team_name=away_canonical,
        polymarket_prob=round(away_price, 2),
        end_date=market.end_date,
        volume=market.volume,
        liquidity=market.liquidity,
        market_slug=slug,
    )
    return home_opp, away_opp


def _match_outcome_indices(
    outcomes: list,
    home_canonical: str,
    away_canonical: str,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Match outcome names to home/away indices by partial name match.
    Returns (home_idx, away_idx) or (None, None) if match fails.
    """
    home_idx = None
    away_idx = None

    home_key = home_canonical.lower().split()[-1]  # last word (e.g. "dodgers")
    away_key = away_canonical.lower().split()[-1]

    for i, name in enumerate(outcomes):
        name_lower = str(name).lower()
        if home_key in name_lower and home_idx is None:
            home_idx = i
        elif away_key in name_lower and away_idx is None:
            away_idx = i

    if home_idx == away_idx:
        return None, None

    return home_idx, away_idx
