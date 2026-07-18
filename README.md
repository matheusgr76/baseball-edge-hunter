# Baseball Edge Hunter

MLB moneyline edge detection for Polymarket.

The pipeline compares Polymarket prices against a devigged, Pinnacle-weighted bookmaker consensus, then applies conservative calibration and reliability guards before signaling.

## What It Does
- Fetches bookmaker moneyline odds (reference only)
- Builds consensus probability
- Applies Tier 1 + Phase 4 calibration factors
- Gates games by Polymarket availability/liquidity
- Scores per-outcome edge and confidence
- Emits `STRONG BET` / `BET` / `SKIP` / `FADE` / `AVOID`
- Writes reports, signal logs, outcome summaries, and run artifacts

## Hard Scope Rules
- Polymarket only for bet execution context
- Moneyline only
- No Polymarket market = game skipped

## Runtime Reliability Configuration
- `STRONG BET`: edge >= 4.0pp and confidence >= 85%
- `BET`: edge >= 3.5pp and confidence >= 75%
- Calibration cap: +/-6.0pp per team
- Liquidity floor: $750
- Reliability guards enabled:
  - moderate/high favorite edge-floor guards
  - rematch side-flip guard
  - fail-closed outcome matching when ambiguous

## Operational Policy (Current)
- Rollout mode: `Shadow-Then-Act`
- Conservative thresholds remain unchanged until dual gate is met:
  - at least 20 resolved actionable signals
  - at least 55% actionable win-rate
- Runtime now evaluates this gate automatically via `output.clv_tracker.reliability_gate_status()`.

## Quickstart
1. Install dependencies:
   - `pip install -r requirements.txt`
2. Configure environment:
   - `cp .env.example .env`
   - Fill in `ODDS_API_KEY` (required); `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` are optional — leave blank to disable outbound alerts.
3. Run:
   - `python main.py`

## Tests
```bash
pytest
```

## Automation
Runs daily via GitHub Actions ([`.github/workflows/daily-mlb-pipeline.yml`](.github/workflows/daily-mlb-pipeline.yml)) at 10:00 America/Sao_Paulo. Secrets (`ODDS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) are configured under repo Settings → Secrets and variables → Actions. Each run uploads `output/` as a workflow artifact (14-day retention) and can also be triggered manually via `workflow_dispatch`.

## Key Output Paths
- Daily reports: `output/daily_report_YYYY-MM-DD.txt`
- Signal log: `output/predictions_log.json`
- Run artifacts:
  - `output/real_bets/runs/YYYY-MM-DD/{run_id}.log`
  - `output/real_bets/runs/YYYY-MM-DD/{run_id}.json`
  - each run JSON includes `pipeline_summary.reliability_gate`
- Actionable ledger: `output/real_bets/daily/real_bets_YYYY-MM-DD.jsonl`

## Repo Guide
- `main.py`: entrypoint with real-bets run logger wrapper
- `orchestration/pipeline.py`: end-to-end pipeline
- `comparison/edge.py`: signal assignment + confidence + guards
- `calibration/factors.py`: Tier 1 + Phase 4 factor aggregation
- `output/clv_tracker.py`: signal logging, outcome resolver, summaries
- `todo.md`: execution log and open priorities
- `HANDOFF.md`: current operational status and next actions

## License
All rights reserved — see [`LICENSE`](LICENSE).
