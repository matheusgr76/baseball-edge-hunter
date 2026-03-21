# TODO — MLB Edge Hunter

## DONE

### Phase 1: Core Pipeline ✅ (2026-03-21)
- [x] Build `models.py` — all dataclasses (RawBookmakerOdds, CanonicalGame, PolymarketOpportunity, EdgeAnalysis, PipelineResult)
- [x] Build `config.py` — API keys from env, signal thresholds, liquidity floor
- [x] Build `ingestion/bookmakers.py` — The Odds API (`baseball_mlb`, `h2h`)
- [x] Build `ingestion/polymarket.py` — Gamma API slug fetch (`mlb-{away}-{home}-{date}`)
- [x] Build `normalization/devig.py` — multiplicative 2-way devig
- [x] Build `normalization/teams.py` — 30 MLB teams, slug abbreviations, raw→canonical mapping
- [x] Build `comparison/edge.py` — 5-tier signal per outcome (STRONG BET/BET/SKIP/FADE/AVOID)
- [x] Build `output/report_formatter.py` — terminal report + CSV (basketball_edge_hunter format)
- [x] Build `orchestration/pipeline.py` — `run_pipeline()` entry point, full wire-up
- [x] Build `main.py` + `requirements.txt`
- [x] Smoke tests pass (imports, devig math, signal boundaries, slug construction)
- [x] GitHub repo created: https://github.com/matheusgr76/baseball-edge-hunter

---

## Phase 2: Situational Calibration (IN PROGRESS)

### 2a — Starting Pitcher Quality
- [ ] Build `ingestion/mlb_data.py`
  - [ ] Fetch today's probable pitchers from MLB Stats API
    - `GET https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=probablePitcher`
  - [ ] Pull SIERA/FIP per pitcher from PyBaseball (`pitching_stats()`)
  - [ ] Return `ProbablePitcher(team, name, player_id, siera, fip, hand)`
- [ ] Build `calibration/factors.py`
  - [ ] `sp_quality_adjustment(home_sp, away_sp) -> Tuple[float, float]`
  - [ ] Logic: compare each SP's SIERA vs league average (4.20), scale to ±5pp
  - [ ] FactorResult output: SIERA delta, explanation, devil's advocate
- [ ] **VERIFY:** Known ace (low SIERA ~2.8) shifts prob +3–5pp vs replacement-level SP

### 2b — Bullpen Availability
- [ ] Extend `ingestion/mlb_data.py`
  - [ ] Fetch recent game logs per relief pitcher (MLB Stats API)
  - [ ] Track pitches thrown in last 48h per team's top-2 RPs
  - [ ] Return `BullpenStatus(team, fatigue_level, pitches_48h)`
- [ ] Extend `calibration/factors.py`
  - [ ] `bullpen_adjustment(home_bp, away_bp) -> Tuple[float, float]`
  - [ ] Thresholds: 25–40 pitches → −2pp, 40+ pitches → −4pp
  - [ ] FactorResult output with usage details

### 2c — Calibration Integration
- [ ] Add `CalibratedGame` + `AdjustmentBreakdown` dataclasses to `models.py`
- [ ] Update `comparison/edge.py` to accept `CalibratedGame` (true_prob ≠ consensus_prob)
- [ ] Update `orchestration/pipeline.py`: insert calibration step after normalization
- [ ] Update `output/report_formatter.py`: replace placeholder factor row with real factors
- [ ] Bound total adjustment to ±8pp per team
- [ ] **VERIFY:** Calibrated probs still sum to ~100%, factor table shows real values

---

## Phase 3: Validation & CLV
- [ ] CLV tracker — log signal_line, record closing_line, calculate beat-rate
- [ ] Historical backtest — 2024/2025 season retroactive run
- [ ] Weekly performance reporting + P&L chart

---

## Phase 4: Advanced Factors (Tier 2-3)
- [ ] Umpire tendencies (UmpScorecards.com)
- [ ] wRC+ vs SP handedness (FanGraphs splits)
- [ ] Pythagorean W% regression flag
- [ ] OAA defensive adjustment
