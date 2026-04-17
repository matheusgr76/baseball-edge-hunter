# Log Apr 5 MLB Research Snapshot

## Summary
Create a separate historical snapshot flow for manual research entries, without touching the existing live CLV log behavior.

This snapshot will capture:
- The full Polymarket MLB Week 2 board shown in the attached PDF.
- The Apr 5, 2026 bot run shown in the attached screenshot.
- A built-in follow-up section due on April 12, 2026 for results plus market-move review.

## Key Changes
- Add new research-side models in `models.py` for:
  - `MarketBoardEntry`
  - `BotSummaryRow`
  - `HistoricalSnapshot`
  - `HistoricalReviewRow`
- Add a new sidecar tracker module, for example `output/historical_tracker.py`, with functions to:
  - create and save a snapshot JSON
  - load/list pending snapshots
  - mark follow-up rows as reviewed one week later
- Store the first snapshot as a new dated JSON under `output/historical_snapshots/`, not inside `predictions_log.json`.
- Copy the attached source artifacts into `output/historical_snapshots/artifacts/` so the dataset does not depend on external paths later.
- Seed the first snapshot with:
  - every MLB market row visible in the Week 2 PDF from Fri Apr 3 through Tue Apr 7
  - the Apr 5 bot summary rows from the screenshot and/or `output/daily_report_2026-04-05.txt`
  - the lineup warnings shown in the bot output
  - `review_goal="results_and_market_move"`
  - `review_due_date="2026-04-12"`

## Data Shape
Each snapshot should include:
- Snapshot metadata: `snapshot_id`, `captured_at`, `week_label`, `review_due_date`, `review_status`
- Source artifacts: copied PDF, copied PNG, linked daily report path
- `market_board`: date, time, away team, home team, away price %, home price %, volume when visible
- `bot_run`: 14 Apr 5 summary rows with game, favorite, T%, P%, C%, edge, verdict, actionable flag
- `lineup_warnings`: the 4 warnings shown in the screenshot
- `follow_up_rows`: one row per logged game with blank fields for final winner, closing prices, CLV delta, notes, completed_at

Important constraint:
- Do not change the schema or behavior of `output/clv_tracker.py`. This historical snapshot log stays separate from the live pipeline log.

## Test Plan
- Unit test snapshot save/load and pending-review lookup.
- Unit test artifact path generation and stable snapshot IDs.
- Unit test bot-row parsing/serialization with the Apr 5 no-actionable slate.
- Acceptance check: first seeded snapshot contains 14 Apr 5 bot rows, 4 lineup warnings, and all visible Week 2 board rows from the PDF.
- Acceptance check: April 12 review lookup returns this snapshot as pending.

## Assumptions
- This is a research dataset, not a betting/execution feature.
- The first market-board seed will be transcribed from the attached PDF into structured JSON; no OCR dependency will be introduced for v1.
- The existing daily report and predictions log remain the source of truth for normal pipeline runs; the new snapshot file is only for manual historical capture from external artifacts.

## Post-Phase-4 Follow-Up (2026-04-17)

- This manual snapshot remains a valid pre-Phase-4 baseline for reliability comparisons.
- Phase 4 factors are now integrated in live pipeline runtime, so future weekly reviews should tag runs as:
  - `pre_phase4` for historical baselines like Apr 5
  - `phase4_live` for new calibrated runs
- Keep this file unchanged as a frozen planning artifact for the Apr 5 snapshot workflow.
