# HANDOFF - MLB Edge Hunter

## Current State (2026-04-19)
- Documentation synchronized to runtime behavior (`AGENTS.md`, `CLAUDE.md`, `IP.md`, `todo.md`, `README.md`, `HANDOFF.md`).
- Runtime policy remains reliability-first with conservative thresholds.
- Reliability runtime changes implemented:
  - dual-gate evaluator in `output/clv_tracker.py` (`reliability_gate_status()`)
  - CLV summary now prints dual-gate blockers/unlock state
  - run artifact JSON includes `pipeline_summary.reliability_gate`

## Operational Mode
- Mode: `Shadow-Then-Act`
- Thresholds unchanged:
  - `STRONG BET`: 4.0pp / 85%
  - `BET`: 3.5pp / 75%
- Calibration cap: +/-6.0pp
- Liquidity floor: $750

## Reliability Gate (for retuning decisions)
Retune thresholds/factor weights only when both conditions are met:
1. At least 20 resolved actionable signals
2. At least 55% actionable win-rate

## Latest Tracker Snapshot (2026-04-19)
- `outcome_summary()`:
  - actionable_total: 14
  - actionable_resolved: 14
  - actionable_wins: 11
  - actionable_losses: 3
  - actionable_win_rate_pct: 78.57
- `clv_summary()` currently shows unresolved closing-line sample (`resolved: 0`), so CLV beat-rate is not yet decision-grade.
- `reliability_gate_status()`:
  - rollout_mode: `SHADOW_THEN_ACT`
  - resolved_actionable: `14/20` (remaining: 6)
  - win_rate_pct: `78.57%` (meets 55% threshold)
  - dual_gate_met: `False` (blocked by sample size only)

## Runbook
1. Execute pipeline:
   - `python main.py`
2. Review outputs:
   - `output/daily_report_YYYY-MM-DD.txt`
   - `output/predictions_log.json`
   - `output/real_bets/daily/real_bets_YYYY-MM-DD.jsonl`
3. Check reliability progress:
   - `python -c "from output.clv_tracker import outcome_summary; print(outcome_summary())"`
4. Keep `todo.md` and `HANDOFF.md` updated after each meaningful change.

## Open Priorities
1. Reach dual-gate sample depth (`20 + 55%`) with post-Phase-4 actionable outcomes.
2. Replace seed data files (`wRC+`, `OAA`, `umpire`) with production-grade values and re-verify.
3. Complete remaining live-checklist validations (slug/outcome ordering/team-name edge cases).

## Risks / Watch Items
- Small actionable sample can overstate short-term performance.
- CLV tracking is currently under-populated for closing-line evaluation.
- External API schema/name changes (MLB/Polymarket) can silently reduce coverage if normalization mappings drift.
