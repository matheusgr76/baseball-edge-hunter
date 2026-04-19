# TODO — MLB Edge Hunter

## DONE

### Documentation Sync + Operational Baseline ✅ (2026-04-19)
- [x] Normalize core documentation to current runtime truth:
  - `STRONG BET` = 4.0pp / 85%
  - `BET` = 3.5pp / 75%
  - calibration cap = ±6pp per team
  - reliability guards + rematch flip policy active
  - liquidity floor = $750
- [x] Replace malformed `CLAUDE.md` "IMPORTANT" block with explicit sections:
  - `## Debugging`
  - `## Workflow`
  - `## Git`
- [x] Create operator docs:
  - `README.md` (quickstart + operational policy)
  - `HANDOFF.md` (current status + runbook + risks)
- [x] Lock reliability policy in docs:
  - Dual gate: at least 20 resolved actionable signals + at least 55% actionable win-rate
  - Rollout mode: Shadow-Then-Act with conservative thresholds unchanged

### Reliability Operations Runtime ✅ (2026-04-19)
- [x] Add explicit reliability policy config in `config.py`
  - `RELIABILITY_ROLLOUT_MODE = SHADOW_THEN_ACT`
  - `RELIABILITY_GATE_MIN_RESOLVED_ACTIONABLE = 20`
  - `RELIABILITY_GATE_MIN_WIN_RATE_PCT = 55.0`
- [x] Add `reliability_gate_status()` in `output/clv_tracker.py`
  - Evaluates resolved-actionable sample and actionable win-rate dual gate
  - Exposes `dual_gate_met` and `retuning_allowed` booleans
- [x] Extend CLV terminal summary to print operational gate status
  - shows rollout mode and explicit gate blockers when not met
- [x] Add reliability-gate snapshot to run artifacts in `output/real_bets_logger.py`
  - persisted under `pipeline_summary.reliability_gate` in each run JSON
- [x] Add/update tests:
  - `tests/test_clv_tracker_outcomes.py` (dual-gate false/true scenarios)
  - `tests/test_real_bets_logger.py` (artifact includes reliability gate snapshot)
  - `tests/test_main_real_bets_logging.py` (run payload includes reliability gate snapshot)

### Phase 5 — Real Bets Logger ✅ (2026-04-18)
- [x] Add run-level logger module `output/real_bets_logger.py`
  - `start_run_session()` for run IDs and artifact paths
  - `tee_terminal_output()` to capture full stdout/stderr transcript while mirroring console
  - `write_run_artifacts()` to persist immutable run artifacts:
    - `output/real_bets/runs/YYYY-MM-DD/{run_id}.log`
    - `output/real_bets/runs/YYYY-MM-DD/{run_id}.json`
  - `append_daily_bets_index()` for actionable-only append ledger:
    - `output/real_bets/daily/real_bets_YYYY-MM-DD.jsonl`
- [x] Wire logger into `main.py` wrapper (`run_with_real_bets_logging()`)
  - Captures manual run transcript for every pipeline execution
  - Writes failed-run artifacts on exceptions and then re-raises
  - Logger errors are fail-open (warn to stderr, do not block pipeline)
- [x] Extend `PipelineResult` with best-effort `telegram_sent` status
- [x] Add tests:
  - `tests/test_real_bets_logger.py` (session paths, tee capture, append-without-dedupe)
  - `tests/test_main_real_bets_logging.py` (success actionable-only ledger + failure artifact write)

### Phase 3f — Outcome Auto-Resolution ✅ (2026-04-18)
- [x] Add automatic MLB final-score resolver in `output/clv_tracker.py`
  - Populates `final_winner`, `picked_team_won`, `game_result_date`, `game_resolved_at` for logged signals
  - Uses MLB Stats API schedule endpoint with timeout/retry and canonical team-name matching
- [x] Keep CLV semantics unchanged (no synthetic `closing_line` from settlement prices)
- [x] Wire auto-resolve step into pipeline (`orchestration/pipeline.py`) after `log_signals()`
- [x] Extend CLV terminal summary with actionable outcome progress (resolved/wins/losses/win-rate + Phase 4 20-signal gate reminder)
- [x] Add unit tests for outcome resolver and summary (`tests/test_clv_tracker_outcomes.py`)

### Phase 4 — Advanced Factors ✅ (2026-04-17)
- [x] Add park-factor adjustment (data-driven via `data/park_factors.json`)
- [x] Add wRC+ vs SP-handedness adjustment (data-driven via `data/wrc_plus_splits.json`)
- [x] Add pythagorean regression adjustment (live MLB standings run-profile feed)
- [x] Add OAA defensive adjustment (data-driven via `data/team_oaa.json`)
- [x] Add umpire tendency adjustment (home-plate assignment + `data/umpire_tendencies.json`)
- [x] Wire Phase 4 data ingestion in pipeline (`ingestion/phase4_data.py`)
- [x] Add smoke/unit tests for Phase 4 factor math + ingestion parsing
- [x] Verify test suite passes (`python -m unittest discover -s tests -p "test_*.py"`)

### Reliability Hardening — Pre-Phase 4 ✅ (2026-04-17)
- [x] Tighten actionable thresholds in `config.py`
  - `BET`: edge 2.5pp → 3.5pp, confidence 70% → 75%
  - `STRONG BET`: edge 3.0pp → 4.0pp, confidence 80% → 85%
- [x] Raise edge-floor guards in `config.py` for moderate/high implied favorites
- [x] Add rematch flip reliability guard in `comparison/edge.py`
  - Downgrades actionable signals to `SKIP` when the same matchup flips sides within 72h after a strong prior actionable edge, unless override edge is very large
- [x] Recalibrate confidence scoring in `comparison/edge.py`
  - Lower baseline, lower bonuses, stronger penalties for sparse factors and bookmaker disagreement
- [x] Reduce calibration aggressiveness in `calibration/factors.py`
  - SP scale 1.2 → 0.9
  - SP cap ±5pp → ±4pp
  - Bullpen penalties: -2/-4pp → -1.5/-3pp
  - Total calibration cap ±8pp → ±6pp
- [x] Harden Polymarket outcome mapping in `ingestion/polymarket.py`
  - Removed `(0,1)` fallback when outcome matching is ambiguous
  - Ambiguous markets are now skipped (fail-closed)

### Reliability Audit — Week 3 Outcome Check ✅ (2026-04-17)
- [x] Matched `output/daily_report_2026-04-10.txt` and `output/daily_report_2026-04-11.txt` games to official MLB final scores (Stats API)
- [x] Saved audit dataset: `output/week3_outcome_check_2026-04-17.json`
- [x] Actionable signals resolved: 8 total, 3 wins, 5 false positives (37.5% hit rate)
- [x] Observation: 72% confidence BET bucket underperformed (2-5), including high-edge misses (`ARI@PHI`, `SF@BAL`)
- [x] Recommendation before Phase 4: recalibrate confidence/edge gating and validate reliability checks first

### Utility — WhatsApp Link Import ✅ (2026-04-11)
- [x] Build `whatsapp_links_to_obsidian.py` — standard-library script that converts exported WhatsApp URLs into Obsidian Markdown notes
- [x] Verify script syntax without reading the private chat export or writing to Google Drive

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
- [x] Historical Phase 2 cap was ±8pp per team (current production cap is ±6pp after reliability hardening)
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
- [x] Apr 5 manual market-move review completed (2026-04-11)
  - File: `output/apr5_market_move_review_2026-04-11.md`
  - Result: zero actionable bets; pregame market moves mostly flat; edge direction not predictive on this 14-game sample
  - Note: `CHC@CLE` doubleheader slug/time ambiguity requires caution in future manual snapshots

### 3b — Historical Backtest ~~(removed 2026-04-04)~~
- Deleted: backtesting folder and all associated CLI flags from main.py
- Reason: historical Polymarket prices don't exist; backtest was simulating against bookmaker consensus, not Polymarket — a different question. CLV tracking on live runs is the real validation loop.

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

## Phase 3e: Backtest Hardening ~~(cancelled 2026-04-04)~~
- Entire backtesting module deleted. B1–B5 are moot.
- B4 (Sox collision in `ingestion/polymarket.py`) is a live pipeline bug — tracked separately below.

### Structural tasks (carried forward)
- [x] Cache `fetch_bullpen_status()` per `(team, date)` — module-level dict cache in `mlb_data.py`
- [x] Add comment warning on WCS = `true_prob - 8.0` placeholder in `report_formatter.py`
- [x] Fix Sox name collision in `_match_outcome_indices()` — full-name fallback + always-on warning log

---

## Phase 4a: Signal Quality Improvements ✅ (2026-04-04)

### Fix 1 — Pinnacle-weighted consensus
- **Files:** `config.py`, `normalization/devig.py`
- **Problem:** All bookmakers weighted equally. DraftKings/FanDuel are recreational books with stale lines. Pinnacle is sharp and should dominate the consensus.
- **Fix:** Add `pinnacle` to bookmaker feed. Introduce `SHARP_BOOKMAKERS` and `SHARP_BOOKMAKER_WEIGHT` in config. Weighted average in `calculate_consensus()`.
- [x] Add `pinnacle` to `ODDS_BOOKMAKERS` in `config.py`
- [x] Add `SHARP_BOOKMAKERS` list + `SHARP_BOOKMAKER_WEIGHT` multiplier to `config.py`
- [x] Update `calculate_consensus()` in `devig.py` — weighted average by bookmaker sharpness

### Fix 2 — Lineup confirmation check ✅
- **Files:** `ingestion/mlb_data.py`, `orchestration/pipeline.py`
- **Problem:** Pipeline runs at 10 AM. A player scratched at noon is invisible to the model but visible to Polymarket immediately, creating a false edge.
- **Fix:** Fetch lineup status from MLB Stats API schedule endpoint (hydrate=lineups). Flag games where lineup is not yet confirmed. Print warning in pipeline output before user acts on signal.
- [x] Add `fetch_lineup_status(date_str)` to `mlb_data.py` — returns `{(home, away): bool}`
- [x] Integrate in `pipeline.py` — fetch once, warn per game if lineup unconfirmed

### Fix 3 — Outbound Telegram summary ✅ (2026-04-04)
- **Files:** `config.py`, `orchestration/telegram_client.py`, `orchestration/pipeline.py`
- **Problem:** MLB pipeline only printed to terminal / files. No push notification to the existing Telegram bot.
- **Fix:** Port outbound-only Telegram delivery from `basketball_edge_hunter`. Send one final HTML summary after report/export/CLV steps complete.
- [x] Add env-driven `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `config.py`
- [x] Add safe Telegram client + MLB summary formatter in `orchestration/telegram_client.py`
- [x] Integrate final Telegram send in `run_pipeline()` without changing core pipeline return behavior
- [x] Gracefully skip send when Telegram credentials are absent
- [x] Add unit tests for formatter, send wrapper, and pipeline notification hook

---

## Phase 4: Advanced Factors (Tier 2-3)
- [x] Umpire tendencies (data file + home-plate assignment integration)
- [x] wRC+ vs SP handedness (data-file integration, no-auth ingestion path)
- [x] Pythagorean W% regression factor
- [x] OAA defensive adjustment
- [x] Park factors (`data/park_factors.json`) integrated
- [ ] Calibrate factor weights using fresh CLV sample after at least 20 resolved actionable signals
- [ ] Replace seed wRC+/OAA/umpire datasets with production values and re-verify

---

## Operationalization — Reliability First
- [ ] Maintain Shadow-Then-Act operation until reliability gate is met
- [ ] Reach dual gate for recalibration decisions:
  - at least 20 resolved actionable signals
  - at least 55% actionable win-rate
- [ ] Perform formal reliability review immediately after gate is met:
  - false-positive analysis by confidence bucket
  - factor contribution review
  - go/no-go decision on threshold/factor retuning

---

## First Live Run Checklist (Regular Season ~April 1)
- [ ] Verify Polymarket slug format: `mlb-{away}-{home}-{date}` resolves correctly
- [ ] Confirm outcome ordering in Gamma API (index 0 = home, 1 = away)
- [ ] Verify Chicago/NY/LA abbreviations: `cws`/`chc`, `nyy`/`nym`, `lad`/`laa`
- [ ] Confirm `Athletics` name (Oakland/Sacramento relocation) in MLB Stats API
