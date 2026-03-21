# MLB Edge Hunter — Implementation Plan

## Strategy
Market-vs-market comparison (Polymarket vs bookmaker consensus), NOT sabermetric modeling.
Same 5-layer architecture as NBA/Soccer Edge Hunter. MLB-specific adaptations below.

**Scope constraints:**
- **Moneyline only.** No totals, no run lines, no props.
- **Polymarket is where we bet.** Bookmaker odds are reference data only.
- **No Polymarket market = game doesn't exist.** Pipeline starts with Polymarket, not bookmakers.

---

## Phase 1: Core Pipeline (Moneyline)
**Goal:** Working edge detection for MLB moneyline markets.

### 1a — Polymarket ingestion
- Verify MLB tag exists on gamma API (`mlb`, `baseball`, etc.)
- Map market structure (expect 2-way binary like NBA)
- Build `ingestion/polymarket.py` — fetch events, parse into standardized format
- Output: `{game_id, home_team, away_team, home_prob, away_prob, event_slug}`
- **Acceptance:** Successfully fetches and parses ≥5 upcoming MLB games

### 1b — Bookmaker ingestion
- Build `ingestion/bookmakers.py` using The Odds API
- Fetch `h2h` (moneyline) market for `baseball_mlb`
- Output: `{game_id, home_team, away_team, bookmakers: [{name, home_odds, away_odds}]}`
- **Acceptance:** Returns odds from ≥3 bookmakers per game

### 1c — Normalization
- Build `normalization/devig.py` — Shin devigging for 2-way markets
- Build `normalization/teams.py` — name mapping (30 MLB teams × ~3 variants each)
- Calculate consensus probability across all books
- **Acceptance:** Devigged probabilities sum to 100% (±0.5%), teams match across sources

### 1d — Edge detection
- Build `comparison/edge.py`
- Per-outcome alpha: `calibrated_prob - polymarket_prob`
- Filter by threshold (2.5pp moneyline)
- Signal assignment: 🔥 Strong Bet / ✅ Bet / ⏭️ Skip / 👎 Fade / 🚫 AVOID
- **Acceptance:** Correctly identifies edges on test data, no false positives below threshold

### 1e — Pipeline orchestration
- Build `orchestration/pipeline.py` — `run_pipeline()` entry point
- Wire: Ingestion → Normalization → Comparison → Output
- Console output: formatted table of signals
- **Acceptance:** End-to-end run produces valid output for today's games

---

## Phase 2: Situational Calibration (Tier 1)
**Goal:** Add high-impact filters that adjust raw consensus before comparison.

### 2a — Starting pitcher adjustment
- Build `ingestion/mlb_data.py` — fetch SP for today's games
- Pull SIERA/FIP from PyBaseball or FanGraphs
- Adjustment logic: compare SP quality vs league average → ±5pp
- **Acceptance:** SP adjustment moves consensus in correct direction for known mismatches

### 2b — Bullpen availability
- Track recent bullpen usage (pitches thrown in last 48h)
- Penalize teams with fatigued top relievers (−2pp to −4pp)
- Data source: MLB Stats API or manual roster tracking
- **Acceptance:** Correctly flags back-to-back heavy bullpen usage

### 2c — Integration
- Wire calibration into pipeline: Ingestion → Normalization → **Calibration** → Comparison → Output
- Calibration is additive to consensus, bounded (no single factor > ±5pp, total cap ±8pp)
- **Acceptance:** Calibrated probabilities still sum to ~100%, signals change when factors apply

---

## Phase 3: Validation & CLV Tracking
**Goal:** Prove the system generates real edge, not noise.

### 3a — CLV tracker
- Log every signal with: signal_time, signal_line, closing_line
- Calculate CLV: did we beat the closing line?
- This is THE metric — ROI lies over small samples, CLV doesn't
- **Acceptance:** ≥55% of signals beat closing line over 100+ bets

### 3b — Historical backtest
- Use 2024/2025 season data (historical odds from The Odds API or paid source)
- Run pipeline retroactively, compare signals to actual results
- Track: ROI, hit rate, CLV%, volume per day
- **Acceptance:** Positive expected value at signal threshold

### 3c — Reporting
- Daily signal report (console + optional file output)
- Weekly performance summary
- Cumulative P&L chart (reuse visualizer pattern from montecarlo_soccer)

---

## Phase 4: Advanced Factors (Tier 2-3)
**Goal:** Marginal gains from deeper data.

- Umpire tendencies (UmpScorecards.com scraping)
- wRC+ vs SP handedness splits
- Pythagorean W% regression flags
- OAA defensive adjustments
- Each factor added individually, backtested for impact before inclusion

---

## Folder structure
```
mlb_edge_hunter/
├── CLAUDE.md
├── IP.md
├── todo.md
├── config.py
├── requirements.txt
├── ingestion/
│   ├── __init__.py
│   ├── bookmakers.py
│   ├── polymarket.py
│   └── mlb_data.py
├── normalization/
│   ├── __init__.py
│   ├── devig.py
│   └── teams.py
├── calibration/
│   ├── __init__.py
│   └── factors.py
├── comparison/
│   ├── __init__.py
│   └── edge.py
├── orchestration/
│   ├── __init__.py
│   └── pipeline.py
├── output/
│   └── report_formatter.py    # Terminal report + CSV export (matches basketball_edge_hunter format)
├── data/
│   └── park_factors.json
└── tests/
    ├── test_devig.py
    ├── test_edge.py
    └── test_pipeline.py
```
