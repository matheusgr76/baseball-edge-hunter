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

## Phase 3d: Hotfix — First Live Run Bugs (2026-04-03) ✅

> 2026-03-29 live run: 0 actionable signals. Root causes identified and fixed.

- [x] **Bug 1 (CRITICAL):** Add `num_bookmakers: int = 0` to `CalibratedGame` in `models.py`
- [x] **Bug 1 (CRITICAL):** Populate `num_bookmakers` from `CanonicalGame` in `calibration/factors.py`
- [x] **Bug 1 (CRITICAL):** Use `game.num_bookmakers` in `comparison/edge.py` for `CalibratedGame`
- [x] **Bug 2 (CRITICAL):** Filter stale/resolved markets in `ingestion/polymarket.py` (skip if `endDate < now` or any price > 0.99)
- [x] **Bug 3 (MEDIUM):** Clamp probs to [0.1, 99.9] before renormalization in `calibration/factors.py`
- [x] Run today's live pipeline — 2 actionable signals generated (NYM +5.80pp, SEA +3.43pp) ✅
- [x] Commit hotfix and push

---

## Phase 3e: Backtest Hardening (branch: `hardening`) 🚧

> Codex code-review identified 5 logic bugs in the backtest engine. None affect the
> live pipeline. All 5 must be fixed before backtest metrics can be trusted.

### Bug B1 (CRITICAL) — Poly spread breaks market constraint
- **File:** `backtesting/backtester.py` lines 211–212
- **Problem:** Subtracting `poly_spread_pp` from both home AND away poly prices simultaneously
  violates the 100% market constraint. A positive spread manufactures synthetic edge on
  both teams at once, making backtest ROI mechanically inflated.
- **Fix:** Subtract spread from the target team only; set opponent poly = 100 - home_poly.
- [ ] Fix `_build_signals_for_date()` — correct poly price construction

### Bug B2 (CRITICAL) — P&L settled off `true_prob` instead of `polymarket_prob`
- **File:** `backtesting/backtester.py` lines 285–288
- **Problem:** Win payout = `100 - true_prob` and loss = `-true_prob`. Correct formula:
  win = `100 - polymarket_prob` (entry price paid), loss = `-polymarket_prob` (stake lost).
  Wrong fill price → wrong ROI.
- **Fix:** Replace `sig.true_prob` with `sig.polymarket_prob` in `_resolve_signals()`.
- [ ] Fix `_resolve_signals()` — use `polymarket_prob` for win/loss P&L

### Bug B3 (MEDIUM) — Doubleheaders not uniquely identified
- **Files:** `backtesting/game_log_parser.py` line 151, `backtesting/backtester.py` line 178
- **Problem:** Result lookup key = `(date, home, away)`. In a doubleheader, Game 2 silently
  overwrites Game 1. Retrosheet `col[1]` holds the game number (0/1/2) and is ignored.
  ~10–15 DH games/season are mis-resolved.
- **Fix:** Include game number in `GameResult`, key lookup as `(date, home, away, game_num)`;
  backtester groups by `(home, away, game_num)` from commence_time hour.
- [ ] Update `GameResult` model to store `game_num`
- [ ] Fix `build_result_lookup()` — add game_num to key
- [ ] Fix `_build_signals_for_date()` — use commence_time hour to infer game_num

### Bug B4 (LOW) — Sox name collision in outcome matching
- **File:** `ingestion/polymarket.py` lines 177–190
- **Problem:** `_match_outcome_indices` uses last word of team name (`"sox"` for both Red Sox
  and White Sox). When they play each other, `home_idx == away_idx` → silent fallback to (0,1).
- **Fix:** Fall back to full-name matching before the index fallback; log a warning with slug.
- [ ] Fix `_match_outcome_indices()` — full-name fallback before (0,1) default

### Bug B5 (CRITICAL) — CLV beat-rate is a tautology
- **File:** `backtesting/backtester.py` lines 321–322
- **Problem:** `clv_beat = [s for s in actionable if s.edge_pp > 0]`. All actionable signals
  already have `edge_pp >= 2.5pp` by definition, so this always returns 100%. Meaningless.
- **Fix:** Replace with real CLV metric: percentage of signals where our model prob >  
  closing bookmaker implied prob. Requires storing closing line from Retrosheet/Odds API.
  Short-term proxy: use `edge_pp > avg_edge_pp` to measure relative sharpness.
- [ ] Replace tautological CLV with meaningful relative-sharpness metric

### Structural tasks (from same review)
- [ ] Cache `fetch_bullpen_status()` per `(team, date)` — currently called once per game in loop
- [ ] Add comment warning on WCS = `true_prob - 8.0` placeholder in `report_formatter.py`

### Gate: do not start Phase 4 until all B1–B5 are resolved.

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
