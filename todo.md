# TODO — MLB Edge Hunter

## Phase 1: Core Pipeline (Moneyline)

### 1a — Polymarket Ingestion
- [ ] Test gamma API: `GET /events?closed=false&tag=mlb&limit=5`
- [ ] If `mlb` tag fails, try: `baseball`, `mlb-baseball`, `major-league-baseball`
- [ ] Document actual market structure (2-way binary? event+markets?)
- [ ] Build `ingestion/polymarket.py` — fetch + parse into standardized format
- [ ] Handle edge cases: postponed games, missing markets, duplicate events
- [ ] **VERIFY:** Successfully parses ≥5 upcoming MLB games with valid probabilities

### 1b — Bookmaker Ingestion
- [ ] Build `ingestion/bookmakers.py` — fetch from The Odds API (`baseball_mlb`, `h2h`)
- [ ] Parse response into standardized format per game per book
- [ ] Handle: missing books, stale lines, API rate limits
- [ ] **VERIFY:** Returns odds from ≥3 bookmakers per game

### 1c — Normalization
- [ ] Build `normalization/devig.py` — Shin devig for 2-way markets
- [ ] Build `normalization/teams.py` — 30 MLB teams, ≥3 name variants each
- [ ] Include common abbreviations: NYY, LAD, SF, etc.
- [ ] Calculate weighted consensus across all books
- [ ] **VERIFY:** Devigged probs sum to 100% (±0.5%), all team names resolve

### 1d — Edge Detection
- [ ] Build `comparison/edge.py`
- [ ] EdgeAnalysis dataclass: team, opponent, consensus_prob, polymarket_prob, alpha, signal
- [ ] Signal logic: 🔥 Strong Bet (≥3.0pp+conf≥80%), ✅ Bet (≥2.5pp+conf≥70%), ⏭️ Skip (<2.5pp), 👎 Fade (-1 to -3pp), 🚫 AVOID (<-3pp)
- [ ] **VERIFY:** Test with synthetic data — signals assigned correctly at boundaries

### 1e — Pipeline Orchestration
- [ ] Build `orchestration/pipeline.py` with `run_pipeline()` entry point
- [ ] Wire: Ingestion → Normalization → Comparison → Output
- [ ] Build `output/report_formatter.py` — **MUST match basketball_edge_hunter format exactly:**
  - [ ] Session header: `╔═╗║╚═╝` box with ⚾ emoji + timestamp
  - [ ] Per-game factor table: FACTOR | RESULT | EXPLANATION | DEVIL | DEVIL ADVOCATE
  - [ ] Probability summary block: `📊 PROBABILITY SUMMARY`
  - [ ] Session summary table: GAME | FAVORITE | PROB | CONF | WCS | BET | MARKET | EDGE
  - [ ] Session summary title: `📊 ANALYSIS SUMMARY` (not "Session Summary")
  - [ ] Column: SIGNAL (not BET) — 🔥 Strong Bet, ✅ Bet, ⏭️ Skip, 👎 Fade, 🚫 AVOID
  - [ ] Anchor callout: `🎯 ACTIONABLE EDGES: N found` with 🔥/✅ per signal + legend at bottom
  - [ ] No-signal fallback: `⏳ No actionable edges today...`
  - [ ] CSV export: ROW_TYPE (HEADER/FACTOR/SUMMARY) per game, same columns as basketball
- [ ] Error handling: graceful degradation if one source fails
- [ ] Build `config.py` — API keys, thresholds, toggles
- [ ] Build `requirements.txt` (include `tabulate`)
- [ ] **VERIFY:** End-to-end run on live data produces formatted output matching basketball_edge_hunter

---

## Phase 2: Situational Calibration

### 2a — Starting Pitcher
- [ ] Build SP data fetch in `ingestion/mlb_data.py`
- [ ] Source: PyBaseball or MLB Stats API for today's probable pitchers
- [ ] Pull SIERA/FIP per pitcher (season + last 30 days)
- [ ] Adjustment logic: SP quality vs league avg → ±5pp bounded
- [ ] **VERIFY:** Known ace (e.g., top-5 SIERA) shifts consensus upward

### 2b — Bullpen Availability
- [ ] Track bullpen usage: pitches thrown per reliever in last 48h
- [ ] Define "fatigued": top 2 RPs threw 25+ pitches in 48h window
- [ ] Penalty: −2pp (moderate fatigue) to −4pp (severe fatigue)
- [ ] **VERIFY:** Team with blown bullpen yesterday shows reduced probability

### 2c — Calibration Integration
- [ ] Build `calibration/factors.py` — apply all Tier 1 factors
- [ ] Wire into pipeline between Normalization and Comparison
- [ ] Bound total calibration adjustment to ±8pp
- [ ] Recalculate signals post-calibration
- [ ] **VERIFY:** Calibrated probs still ~100%, pipeline output reflects adjustments

---

## Phase 3: Validation & CLV

### 3a — CLV Tracker
- [ ] Log every signal: timestamp, signal_line, game_id
- [ ] After game starts: record closing line
- [ ] Calculate CLV per signal
- [ ] Aggregate: CLV% (% of signals that beat closing line)
- [ ] **VERIFY:** Logging works for ≥1 full day of signals

### 3b — Historical Backtest
- [ ] Source historical odds (2024-2025 MLB season)
- [ ] Run pipeline retroactively against historical data
- [ ] Track: ROI, hit rate, CLV%, daily volume, max drawdown
- [ ] **VERIFY:** Sample size ≥200 signals before drawing conclusions

### 3c — Reporting
- [ ] Daily signal report (console + file)
- [ ] Weekly performance summary
- [ ] Cumulative P&L visualization
- [ ] **VERIFY:** Reports generate automatically after pipeline run

---

## Phase 5: Advanced Factors (Tier 2-3)
- [ ] Umpire tendencies (scrape UmpScorecards.com)
- [ ] wRC+ vs SP handedness (FanGraphs splits)
- [ ] Pythagorean W% regression flag
- [ ] OAA defensive adjustment
- [ ] Each factor: add → backtest → keep if +EV, remove if noise
- [ ] **VERIFY:** Each factor individually improves CLV% or remove it

---

## DONE
(move completed items here)
