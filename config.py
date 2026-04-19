"""
MLB Edge Hunter - Configuration
Centralized settings for all pipeline components
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# API CONFIGURATION
# ============================================================================

ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"
ODDS_SPORT: str = "baseball_mlb"
ODDS_REGIONS: str = "us"
ODDS_MARKETS: str = "h2h"
ODDS_BOOKMAKERS: str = "pinnacle,fanduel,draftkings,williamhill_us,betmgm,caesars"

# Sharp books get higher weight in consensus calculation.
# Pinnacle attracts professional money and closes efficiently.
SHARP_BOOKMAKERS: list = ["pinnacle"]
SHARP_BOOKMAKER_WEIGHT: int = 3   # Sharp books count 3x vs recreational books

# Polymarket Gamma API
GAMMA_API_BASE: str = "https://gamma-api.polymarket.com"
POLYMARKET_SLUG_PREFIX: str = "mlb"   # e.g. mlb-nyy-bos-2026-04-01
POLYMARKET_TIME_HORIZON_HOURS: int = 36   # MLB games can be afternoon/evening ET

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================================
# NORMALIZATION SETTINGS
# ============================================================================

DEVIG_METHOD: str = "multiplicative"
PROB_SUM_TOLERANCE: float = 0.5   # ±0.5pp from 100% is acceptable

# ============================================================================
# SIGNAL THRESHOLDS (percentage points vs Polymarket)
# ============================================================================

STRONG_BET_EDGE_PP: float = 4.0
STRONG_BET_CONF_PCT: int = 85

BET_EDGE_PP: float = 3.5
BET_CONF_PCT: int = 75

FADE_MIN_PP: float = -1.0     # Edge <= -1.0 enters fade territory
AVOID_THRESHOLD_PP: float = -3.0   # Edge < -3.0 → AVOID

# Edge-floor guards (reliability pass, 2026-04-17).
# False positives clustered in moderate-favorite bands with thin-moderate cushions.
MODERATE_FAV_BAND: tuple = (0.54, 0.66)     # Polymarket implied prob range (decimal)
MODERATE_FAV_MIN_EDGE: float = 4.5          # pp edge required to BET inside this band
HIGH_CONF_THRESHOLD: float = 0.62           # Above this, require materially larger edge
HIGH_CONF_MIN_EDGE: float = 6.5             # pp edge required to BET above this threshold

# Reliability guard: avoid actionable side-flips in short-series rematches unless
# the new edge is overwhelmingly large.
REMATCH_FLIP_GUARD_ENABLED: bool = True
REMATCH_FLIP_LOOKBACK_HOURS: int = 72
REMATCH_FLIP_MIN_PRIOR_EDGE: float = 5.0
REMATCH_FLIP_OVERRIDE_EDGE: float = 9.0
REMATCH_FLIP_CONF_PENALTY: int = 8

# Reliability operations policy.
# Dual gate controls when threshold/factor retuning may be considered.
RELIABILITY_ROLLOUT_MODE: str = "SHADOW_THEN_ACT"
RELIABILITY_GATE_MIN_RESOLVED_ACTIONABLE: int = 20
RELIABILITY_GATE_MIN_WIN_RATE_PCT: float = 55.0

# ============================================================================
# PIPELINE SETTINGS
# ============================================================================

MIN_POLYMARKET_LIQUIDITY: float = 750.0   # Raised from $500: thin markets have stale prices
MIN_BOOKMAKERS: int = 2                   # Minimum books to form consensus

REQUEST_TIMEOUT: int = 10
MAX_RETRIES: int = 3

# ============================================================================
# OUTPUT SETTINGS
# ============================================================================

OUTPUT_DIRECTORY: str = "output"
LOG_LEVEL: str = "INFO"
DEBUG_MODE: bool = False
