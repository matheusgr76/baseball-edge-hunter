"""
Normalization Layer - Devig
Convert American odds to fair probabilities using multiplicative devig
"""

import math
from typing import List, Tuple
from datetime import datetime
from models import RawBookmakerOdds, CanonicalGame
from normalization.teams import normalize_team_name
import config


def american_to_probability(odds: int) -> float:
    """
    Convert American odds to implied probability (percentage, 0-100).

    Negative odds (e.g. -150): favorite. Bet 150 to win 100.
    Positive odds (e.g. +130): underdog. Bet 100 to win 130.
    """
    if odds < 0:
        prob = abs(odds) / (abs(odds) + 100)
    else:
        prob = 100 / (odds + 100)
    return prob * 100


def devig_multiplicative(home_prob: float, away_prob: float) -> Tuple[float, float]:
    """
    Remove bookmaker vig using multiplicative (proportional) method.

    Normalizes implied probabilities to sum to 100% by dividing each by total.
    Returns (fair_home_pct, fair_away_pct) as percentages summing to 100.

    Example:
        home=60%, away=45% (total=105%, 5% vig)
        → home=57.14%, away=42.86% (total=100%)
    """
    total = home_prob + away_prob
    if total <= 0:
        raise ValueError(f"Invalid probability pair: home={home_prob}, away={away_prob}")
    return (home_prob / total) * 100, (away_prob / total) * 100


def _devig_single_bookmaker(odds_list: List[RawBookmakerOdds]) -> dict:
    """Devig one bookmaker's odds. Returns dict with home_prob, away_prob, bookmaker."""
    odds = odds_list[0]
    home_implied = american_to_probability(odds.home_odds)
    away_implied = american_to_probability(odds.away_odds)
    home_fair, away_fair = devig_multiplicative(home_implied, away_implied)
    return {
        "home_prob": home_fair,
        "away_prob": away_fair,
        "bookmaker": odds.bookmaker,
    }


def calculate_consensus(
    home_team: str,
    away_team: str,
    commence_time: datetime,
    raw_odds: List[RawBookmakerOdds],
) -> CanonicalGame:
    """
    Calculate consensus devigged probabilities across multiple bookmakers.

    Process:
    1. Group odds by bookmaker
    2. Devig each bookmaker independently
    3. Average devigged probabilities (equal weight per bookmaker)
    4. Final normalize to exactly 100%

    Returns CanonicalGame with consensus home/away probabilities.
    """
    by_bookmaker: dict[str, List[RawBookmakerOdds]] = {}
    for o in raw_odds:
        by_bookmaker.setdefault(o.bookmaker, []).append(o)

    devigged = []
    for bm, odds_list in by_bookmaker.items():
        try:
            result = _devig_single_bookmaker(odds_list)
            weight = (
                config.SHARP_BOOKMAKER_WEIGHT
                if bm in config.SHARP_BOOKMAKERS
                else 1
            )
            devigged.append({**result, "weight": weight})
        except Exception as e:
            print(f"  ⚠️  Devig error for {bm}: {e}")

    if not devigged:
        raise ValueError(f"No valid bookmaker odds to devig for {away_team} @ {home_team}")

    total_weight = sum(d["weight"] for d in devigged)
    consensus_home = sum(d["home_prob"] * d["weight"] for d in devigged) / total_weight
    consensus_away = sum(d["away_prob"] * d["weight"] for d in devigged) / total_weight

    # Final normalize (handles floating-point drift)
    total = consensus_home + consensus_away
    consensus_home = round((consensus_home / total) * 100, 2)
    consensus_away = round((consensus_away / total) * 100, 2)

    favorite = "home" if consensus_home >= consensus_away else "away"
    game_id = f"{home_team}_{away_team}_{commence_time.strftime('%Y%m%d_%H%M')}"

    # Bookmaker variance: std dev of devigged home probs across books (unweighted).
    # High variance = books disagree = lower confidence in consensus.
    home_probs = [d["home_prob"] for d in devigged]
    if len(home_probs) >= 2:
        mean_hp = sum(home_probs) / len(home_probs)
        variance = sum((p - mean_hp) ** 2 for p in home_probs) / len(home_probs)
        bm_std_pp = round(math.sqrt(variance), 2)
    else:
        bm_std_pp = 0.0

    return CanonicalGame(
        game_id=game_id,
        home_team=normalize_team_name(home_team),
        away_team=normalize_team_name(away_team),
        commence_time=commence_time,
        home_prob=consensus_home,
        away_prob=consensus_away,
        favorite=favorite,
        num_bookmakers=len(devigged),
        bookmaker_std_pp=bm_std_pp,
        raw_sources=raw_odds,
    )
