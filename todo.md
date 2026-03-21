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

### Phase 2: Situational Calibration ✅ (2026-03-21)
- [x] Build `ingestion/mlb_data.py` — MLB Stats API: probable pitchers + bullpen game logs
  - Note: FanGraphs blocked (403) → FIP computed from components (HR, BB, HBP, K, IP)
- [x] Build `calibration/factors.py` — `sp_quality_factor` (±5pp), `bullpen_factor` (±4pp), `calibrate_game()`
- [x] Add `ProbablePitcher`, `BullpenStatus`, `AdjustmentBreakdown`, `CalibratedGame` to `models.py`
- [x] Update `comparison/edge.py` — accepts `CanonicalGame` or `CalibratedGame`; passes factors to EdgeAnalysis
- [x] Update `orchestration/pipeline.py` — calibration step wired between consensus and Polymarket gatekeeper
- [x] Update `output/report_formatter.py` — real factor rows (SP + bullpen); shows consensus vs calibrated prob
- [x] Total calibration cap: ±8pp per team
- [x] Smoke tests pass (FIP math, calibration direction, prob normalization)

---

## Phase 3: Validation & CLV

### Phase 3a — CLV Tracker ✅ (2026-03-21)
- [x] On each pipeline run: log `{game_id, team, signal, true_prob, polymarket_prob, edge_pp, timestamp}`
  - File: `output/predictions_log.json` (append mode, idempotent dedup by entry_id)
- [x] After game resolves: record closing line via `resolve_signal(game_id, team, closing_line)`
- [x] Calculate CLV per signal: `closing_line - signal_line`
- [x] Aggregate: `clv_summary()` → CLV% = % of signals that beat closing line
- [x] **Target:** ≥55% CLV beat-rate over 100+ signals

### 3b — Historical Backtest ✅ (2026-03-21)
- [x] `backtesting/models.py` — `BacktestSignal`, `BacktestResult`, `BacktestSummary`, `GameResult`
- [x] `backtesting/game_log_parser.py` — Retrosheet GL parser (2020–2025 from `past-seasons/`)
- [x] `backtesting/historical_odds.py` — The Odds API historical endpoint (paid tier; free fallback)
- [x] `backtesting/backtester.py` — core engine: devig replay → signal detection → resolve vs actual results
- [x] `main.py` — `--backtest --season YYYY --max-dates N --spread X.X` CLI flags
- [x] Track per signal: hit rate, ROI (pp), max drawdown, CLV beat-rate
- [x] **Target:** Positive EV at 2.5pp threshold over ≥200 signal sample
- Note: paid Odds API key required for true historical odds; free key will use live odds today as proxy

### 3c — Reporting ✅ (2026-03-21)
- [x] Daily signal report persisted to `output/daily_report_{date}.txt`
- [x] Weekly performance summary (CLV%, beat-rate, volume) — `print_weekly_summary()`
- [x] Cumulative P&L chart (Unicode terminal sparkline) — `print_pnl_chart()`

---

## Phase 4: Advanced Factors (Tier 2-3)
- [ ] Umpire tendencies (scrape UmpScorecards.com)
- [ ] wRC+ vs SP handedness (FanGraphs splits — needs auth workaround)
- [ ] Pythagorean W% regression flag
- [ ] OAA defensive adjustment
- [ ] Each factor: add → backtest → keep if CLV% improves, remove if noise

---

## First Live Run Checklist (Regular Season ~April 1)
- [ ] Verify Polymarket slug format: `mlb-{away}-{home}-{date}` resolves correctly
- [ ] Confirm outcome ordering in Gamma API (index 0 = home, 1 = away)
- [ ] Verify Chicago/NY/LA abbreviations: `cws`/`chc`, `nyy`/`nym`, `lad`/`laa`
- [ ] Confirm `Athletics` name (Oakland/Sacramento relocation) in MLB Stats API
