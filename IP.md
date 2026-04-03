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
│   ├── bookmakers.py        ✅ Phase 1
│   ├── polymarket.py        ✅ Phase 1
│   └── mlb_data.py          ✅ Phase 2 — SP (FIP) + bullpen usage
├── normalization/
│   ├── devig.py             ✅ Phase 1
│   └── teams.py             ✅ Phase 1
├── calibration/
│   └── factors.py           ✅ Phase 2 — SP ±5pp, bullpen ±4pp, ±8pp cap
├── comparison/
│   └── edge.py              ✅ Phase 1+2 — accepts CanonicalGame or CalibratedGame
├── orchestration/
│   └── pipeline.py          ✅ Phase 1+2 — calibration step wired
├── output/
│   ├── report_formatter.py  ✅ Phase 1+2 — real factor rows
│   └── clv_tracker.py       ✅ Phase 3a — signal log, CLV resolution, beat-rate summary
```

**Pending first live-run verifications (regular season ~April 1):**
- Confirm Polymarket MLB slug format (`mlb-{away}-{home}-{date}`) resolves correctly
- Confirm outcome ordering in Gamma API response (index 0 = home, 1 = away)
- Verify Chicago/NY/LA abbreviations match actual Polymarket slugs (cws/chc, nyy/nym, lad/laa)
- Verify `Athletics` team name in MLB Stats API (relocation: Oakland → Sacramento/Las Vegas)

---

## Phase 2: Situational Calibration ✅ COMPLETE (2026-03-21)

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

## Phase 3: Validation & CLV Tracking ✅ COMPLETE (2026-03-21)

### Phase 3a — CLV Tracker ✅ COMPLETE (2026-03-21)

**Goal:** Log every pipeline signal at signal-time and track edge quality via CLV beat-rate.

**File:** `output/clv_tracker.py`

**API:**
- `log_signals(edges)` — called by `pipeline.py` after edge detection; appends to `output/predictions_log.json` (idempotent, dedupes by `entry_id`)
- `resolve_signal(game_id, team, closing_line)` — records closing Polymarket price post-game; computes `CLV = closing_line - signal_time_prob`
- `clv_summary()` → dict with beat-rate, avg CLV, target status
- `print_clv_summary()` — prints running stats in terminal at end of every pipeline run

**Target:** ≥55% CLV beat-rate over ≥100 resolved actionable signals

**Integration:** Pipeline Steps 8 (log) → 9 (CSV) → 10 (CLV summary print)

### Phase 3c — Reporting ✅ COMPLETE (2026-03-21)

**Goal:** Persist reports and surface weekly/cumulative performance in terminal.

**New functions added:**
- `output/report_formatter.py` → `save_daily_report(all_edges, output_dir)` — writes `output/daily_report_{date}.txt` on every pipeline run (even no-edge days)
- `output/clv_tracker.py` → `weekly_summary()` — groups resolved actionable signals by ISO week; returns beat-rate, avg CLV, total CLV per week
- `output/clv_tracker.py` → `print_weekly_summary()` — terminal table; ✅ flag when ≥55% beat-rate
- `output/clv_tracker.py` → `print_pnl_chart()` — Unicode sparkline of cumulative CLV P&L over all resolved signals

**Pipeline integration (pipeline.py):**
```
Step 7b: save_daily_report()          ← NEW (after print_session_summary)
Step 10: print_clv_summary()
         print_weekly_summary()       ← NEW
         print_pnl_chart()            ← NEW
```

---

## Phase 3d: Hotfix — First Live Run Bugs (2026-04-03)

**Root cause:** 2026-03-29 live run produced 0 actionable signals due to 3 bugs:

### Bug 1 — `num_bookmakers` not carried through calibration (CRITICAL)
- `CalibratedGame` does not store `num_bookmakers`
- `edge.py` hardcodes `0` when receiving a `CalibratedGame`
- `_confidence()` base = 50%, never reaches 70%/80% thresholds for BET/STRONG BET
- **Fix:** Add `num_bookmakers: int = 0` field to `CalibratedGame` in `models.py`; populate from `CanonicalGame` in `factors.py`; consume in `edge.py`

### Bug 2 — Stale/resolved Polymarket markets bypass liquidity filter
- Opening week markets (Tokyo series) had already resolved but still had high volume
- Resulted in `polymarket_prob` near 0.05% → fictitious +85pp edges
- **Fix:** In `polymarket.py`, skip markets where `endDate < now` OR any `outcomePrices` > 0.99 (resolved indicator)

### Bug 3 — Probability values outside [0, 100]
- Additive calibration on extreme favorites pushes probs past physical limits before renormalization
- e.g., Tampa Bay Rays `true_prob: 101.08%`, St. Louis Cardinals `-1.08%`
- **Fix:** Clamp each team's prob to [0.1, 99.9] in `calibrate_game()` before renormalization

### Files modified:
- `models.py` — add `num_bookmakers` to `CalibratedGame`
- `calibration/factors.py` — pass `canonical.num_bookmakers` into `CalibratedGame`
- `comparison/edge.py` — use `game.num_bookmakers` when game is `CalibratedGame`
- `ingestion/polymarket.py` — filter resolved/stale markets

---

## Phase 4: Advanced Factors (Tier 2-3)

Each factor added individually, backtested before inclusion:
- Umpire tendencies (UmpScorecards.com)
- wRC+ vs SP handedness (FanGraphs)
- Pythagorean W% regression flag
- OAA defensive adjustment
- Park factors (`data/park_factors.json`)
