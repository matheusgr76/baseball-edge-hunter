# MLB Edge Hunter - Project Briefing

## What this is
MLB moneyline edge detection for Polymarket. The system compares Polymarket prices against a calibrated bookmaker consensus and emits reliability-gated signals.

## Hard Rules
1. Bets are placed on Polymarket only.
2. Moneyline only (no totals, run lines, or props).
3. Bookmaker odds are reference data only.
4. No Polymarket market means the game is skipped.

## Runtime Truth (Production)
- Actionable thresholds:
  - `STRONG BET`: edge >= 4.0pp and confidence >= 85%
  - `BET`: edge >= 3.5pp and confidence >= 75%
- Fade/avoid bands:
  - `FADE`: -3.0pp <= edge < -1.0pp
  - `AVOID`: edge < -3.0pp
- Reliability controls:
  - Moderate/high-favorite edge floors enabled
  - Rematch side-flip guard enabled (72h lookback)
  - Ambiguous Polymarket outcome mapping fail-closed
- Calibration cap: total adjustment capped at +/-6.0pp per team.
- Liquidity floor: minimum Polymarket liquidity is $750.

## Operational Reliability Policy
- Dual gate for reliability recalibration decisions:
  - At least 20 resolved actionable signals
  - At least 55% actionable win rate
- Until dual gate is satisfied, rollout mode is `Shadow-Then-Act`:
  - Keep conservative thresholds unchanged
  - Continue full logging/reporting and manual review
  - Act conservatively on actionable output only
- Runtime gate evaluator: `output.clv_tracker.reliability_gate_status()`
- Run-level audit snapshot: `pipeline_summary.reliability_gate` in real-bets run JSON artifacts

## Architecture
```
baseball_edge_hunter/
├── config.py
├── main.py
├── models.py
├── ingestion/
│   ├── bookmakers.py
│   ├── polymarket.py
│   ├── mlb_data.py
│   └── phase4_data.py
├── normalization/
│   ├── devig.py
│   └── teams.py
├── calibration/
│   ├── factors.py
│   └── phase4.py
├── comparison/
│   └── edge.py
├── orchestration/
│   ├── pipeline.py
│   └── telegram_client.py
├── output/
│   ├── clv_tracker.py
│   ├── report_formatter.py
│   └── real_bets_logger.py
├── data/
└── tests/
```

## Pipeline Flow
1. Fetch bookmaker odds.
2. Build devigged weighted consensus (Pinnacle weighted).
3. Apply calibration factors (Tier 1 + Phase 4), capped at +/-6pp.
4. Gate by Polymarket availability/liquidity.
5. Compute per-outcome edge + confidence and assign signal.
6. Print/export reports.
7. Log signals, auto-resolve outcomes, print CLV/outcome summaries.
8. Archive run artifacts in `output/real_bets/`.

## Validation Note
- Historical backtest module was removed on 2026-04-04.
- Live validation is now outcome tracking + CLV workflow from real runs.

## Output Contract
Summary output format is locked to the basketball_edge_hunter style. Do not change column widths, alignment, or prefix/icon mapping without updating this spec and dependent tests.

## Known Pitfalls
- Do not call non-existent ingestion functions.
- Team normalization must be explicit and consistent.
- Always send a User-Agent on external API calls.
- Never infer Polymarket outcome mapping when ambiguous.

## Debugging
When debugging, read the actual source code path first before diagnosing. Trace code flow directly instead of inferring root cause from symptoms.

## Workflow
After code changes, update relevant docs (`todo.md`, `HANDOFF.md`, `IP.md`, `README.md`) in the same task so project state remains synchronized.

## Git
Default workflow: commit with descriptive messages, then push to the current branch. Only pause for confirmation when branch target or scope is ambiguous.

## Dev Environment
- Python 3.x
- Windows + WSL2/Ubuntu
- VS Code or terminal
- Git

## Quality Gates
- Smoke tests for every module
- No hardcoded API keys (env/config only)
- Log API calls with timestamp and status
- Verify pipeline outputs before marking complete
