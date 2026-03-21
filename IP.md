# MLB Edge Hunter — Implementation Plan

## Strategy
Market-vs-market comparison (Polymarket vs bookmaker consensus), NOT sabermetric modeling.
Same 5-layer architecture as NBA/Soccer Edge Hunter. MLB-specific adaptations below.

**Scope constraints:**
- **Moneyline only.** No totals, no run lines, no props.
- **Polymarket is where we bet.** Bookmaker odds are reference data only.
- **No Polymarket market = game doesn't exist.** Polymarket is the gatekeeper.

---

## Phase 1: Core Pipeline ✅ COMPLETE (2026-03-21)

All files built and smoke-tested. GitHub: https://github.com/matheusgr76/baseball-edge-hunter

**Architecture decisions locked:**
- Devig: multiplicative 2-way (same as NBA reference)
- Polymarket: slug-based fetch (`mlb-{away_abbr}-{home_abbr}-{date}`)
- EdgeAnalysis: per-outcome (2 per game), 5-tier signal
- Phase 1 true_prob == consensus_prob (no calibration yet)

**Current folder structure:**
```
baseball_edge_hunter/
├── CLAUDE.md
├── IP.md
├── todo.md
├── config.py
├── models.py
├── main.py
├── requirements.txt
├── ingestion/
│   ├── bookmakers.py        ✅
│   └── polymarket.py        ✅
├── normalization/
│   ├── devig.py             ✅
│   └── teams.py             ✅
├── comparison/
│   └── edge.py              ✅
├── orchestration/
│   └── pipeline.py          ✅
└── output/
    └── report_formatter.py  ✅
```

**Pending first live-run verifications:**
- Confirm Polymarket MLB slug format (`mlb-{away}-{home}-{date}`) resolves correctly
- Confirm outcome ordering in Gamma API response (index 0 = home, 1 = away)
- Verify Chicago/NY/LA abbreviations match actual Polymarket slugs (cws/chc, nyy/nym, lad/laa)

---

## Phase 2: Situational Calibration (IN PROGRESS)

**Goal:** Add Tier 1 factors that adjust consensus before edge comparison.
Calibration is additive to consensus, bounded at ±8pp total per team.

### New files:
- `ingestion/mlb_data.py` — probable pitchers + bullpen usage
- `calibration/__init__.py`
- `calibration/factors.py` — apply SP + bullpen factors

### Model additions to `models.py`:
```python
@dataclass
class ProbablePitcher:
    team: str
    name: str
    player_id: int
    siera: float      # Season SIERA (lower = better)
    fip: float        # Season FIP
    hand: str         # "L" or "R"

@dataclass
class BullpenStatus:
    team: str
    pitches_last_48h: int   # Top-2 RPs combined
    fatigue_level: str      # "fresh" | "moderate" | "heavy"

@dataclass
class AdjustmentBreakdown:
    sp_quality: float = 0.0
    bullpen: float = 0.0
    total: float = 0.0
    capped: bool = False    # True if hit ±8pp cap

@dataclass
class CalibratedGame:
    game_id: str
    home_team: str
    away_team: str
    commence_time: datetime
    consensus_home_prob: float
    consensus_away_prob: float
    true_home_prob: float     # After calibration
    true_away_prob: float
    home_adjustments: AdjustmentBreakdown
    away_adjustments: AdjustmentBreakdown
    home_factors: List[FactorResult]
    away_factors: List[FactorResult]
    favorite: str
```

### Data sources:
- **Probable pitchers:** MLB Stats API (free)
  `GET https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=probablePitcher`
- **SIERA/FIP:** PyBaseball `pitching_stats(year)` → FanGraphs pull
- **Bullpen usage:** MLB Stats API game logs per pitcher
  `GET https://statsapi.mlb.com/api/v1/people/{id}/stats?stats=gameLog&season={year}`

### SP adjustment logic:
```
MLB avg SIERA ≈ 4.20
delta = avg_siera - pitcher_siera   (positive = better than avg)
raw_adj = delta * 1.2               (scale factor, empirical)
adj = clamp(raw_adj, -5.0, +5.0)   (hard cap per factor)
```

### Bullpen adjustment logic:
```
pitches_48h < 25        →  0.0pp   (fresh)
25 <= pitches_48h < 40  → -2.0pp   (moderate fatigue)
pitches_48h >= 40       → -4.0pp   (heavy use)
```

### Pipeline change (pipeline.py):
```
Bookmakers → Consensus (CanonicalGame)
           → Calibration (CalibratedGame)   ← NEW
           → Polymarket gatekeeper
           → Edge detection
           → Report + CSV
```

### report_formatter.py change:
Replace Phase 1 placeholder factor row with real factor rows from `CalibratedGame.home_factors` / `away_factors`.

---

## Phase 3: Validation & CLV Tracking

**Goal:** Prove the system generates real edge, not noise.

- CLV tracker: log signal_time + signal_line, update with closing_line post-game
- Target: ≥55% CLV beat-rate over 100+ bets
- Historical backtest: 2024/2025 season
- THE metric is CLV%, not ROI (too small sample otherwise)

---

## Phase 4: Advanced Factors (Tier 2-3)

Each factor added individually, backtested before inclusion:
- Umpire tendencies (UmpScorecards.com)
- wRC+ vs SP handedness (FanGraphs)
- Pythagorean W% regression flag
- OAA defensive adjustment
- Park factors (`data/park_factors.json`)
