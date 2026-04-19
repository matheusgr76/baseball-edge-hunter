# MLB Edge Hunter - Implementation Plan (Current State)

## Pipeline Fluxogram
```text
                +---------------------------+
                |        python main.py     |
                | run_with_real_bets_logging|
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | orchestration.run_pipeline|
                +-------------+-------------+
                              |
             +----------------+----------------+
             v                                 v
 +------------------------+         +------------------------+
 | ingestion/bookmakers   |         | ingestion/mlb_data +   |
 | moneyline odds feed    |         | ingestion/phase4_data  |
 +-----------+------------+         +-----------+------------+
             |                                  |
             +----------------+-----------------+
                              v
                +---------------------------+
                | normalization/devig       |
                | weighted consensus (sharp)|
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | calibration/factors       |
                | Tier1 + Phase4, cap +/-6 |
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | ingestion/polymarket      |
                | gatekeeper + liquidity    |
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | comparison/edge           |
                | signal + confidence +     |
                | reliability guards        |
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | output/report_formatter   |
                | terminal + daily + csv    |
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | output/clv_tracker        |
                | log + outcome resolve +   |
                | dual-gate status          |
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                | output/real_bets_logger   |
                | transcript + run json +   |
                | actionable daily jsonl    |
                +---------------------------+
```

## Strategy
Market-vs-market MLB moneyline analysis:
- Polymarket is the betting venue and gatekeeper.
- Bookmaker odds are reference inputs for a devigged consensus.
- Calibration factors are conservative filters, not standalone signal generators.

## Scope Constraints
- Moneyline only.
- No Polymarket market = no game in output.
- No historical synthetic backtest for validation decisions.

## Operational Status (as of 2026-04-19)
- Phase 4 factors are live in production flow.
- Reliability hardening controls are active:
  - `STRONG BET`: 4.0pp / 85%
  - `BET`: 3.5pp / 75%
  - Moderate/high-favorite edge-floor guards
  - Rematch side-flip guard
  - Fail-closed Polymarket outcome matching
- Calibration cap: +/-6pp per team.
- Polymarket liquidity floor: $750.
- Outcome auto-resolution is integrated in pipeline runtime.
- Real-bets run artifact logging is integrated in `main.py` wrapper.
- Dual-gate reliability status is now computed in runtime (`reliability_gate_status()`).
- Run artifact JSON now includes a reliability gate snapshot for each run.

## Reliability Policy
- Dual gate before threshold/factor loosening:
  - >=20 resolved actionable signals
  - >=55% actionable win rate
- Until gate is met, rollout mode is `Shadow-Then-Act` with conservative settings unchanged.
- Current dual-gate snapshot (2026-04-19): `resolved=14/20`, `win_rate=78.57%`, `dual_gate_met=False`.

## Current Architecture
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

## Calibration Runtime Truth
- SP quality uses FIP vs league baseline with conservative scaling.
- Bullpen penalties:
  - 25-39 pitches (top relievers / 48h): -1.5pp
  - >=40 pitches: -3.0pp
- Phase 4 factors included:
  - Park factor
  - wRC+ vs SP handedness
  - Pythagorean regression
  - OAA defense
  - Umpire tendency
- Total per-team adjustment is clamped to +/-6.0pp and probabilities are clamped to [0.1, 99.9] before renormalization.

## Validation Model
- Live validation = outcome tracking + CLV tracking from real runs.
- Historical backtest module was removed on 2026-04-04 and remains cancelled.

## Historical Timeline (Preserved)
- Phase 1 core pipeline completed (2026-03-21).
- Phase 2 Tier-1 calibration completed (2026-03-21).
- Phase 3 logging/reporting/CLV framework completed (2026-03-21 onward).
- Live reliability hotfixes and hardening completed (2026-04-03 to 2026-04-17).
- Phase 4 advanced factors completed (2026-04-17).
- Outcome auto-resolution + real-bets run logger completed (2026-04-18).
- Reliability dual-gate runtime enforcement + audit snapshot added (2026-04-19).

## Open Work
1. Reach dual-gate sample (`20 + 55%`) with post-Phase-4 actionable outcomes.
2. Replace seed datasets (`wRC+`, `OAA`, `umpire`) with production-grade values.
3. Complete remaining live-run checklist items (slug/outcome-order/name validations).
