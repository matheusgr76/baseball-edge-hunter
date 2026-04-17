# Apr 5, 2026 MLB Market-Move Review

## Scope

Reviewed `output/backtest_snapshot_2026-04-05.json` against final MLB outcomes and Polymarket pregame market moves.

No bets were placed. The bot produced zero actionable signals, so this is not a realized P&L review and not a true CLV beat-rate sample.

## Method

- Results source: ESPN Apr 5 MLB scoreboard.
- Official first-pitch source: MLB Stats API schedule endpoint for 2026-04-05.
- Market metadata source: Polymarket Gamma API by slug.
- Pregame closing price source: Polymarket CLOB `prices-history`.
- Closing sample: last available CLOB price before official MLB `gameDate`.
- Compared the sampled pregame close against the bot `P%` for the model-favorite side.

## Summary

- Games reviewed: 14
- Actionable signals: 0
- Favorite wins by Polymarket-resolved/model-favorite side: 2 / 14
- Average model-favorite market move vs bot `P%`: -0.07pp
- Edge-sign alignment with pregame market move: 6 / 13 nonzero-edge rows
- Positive-edge rows: 3 / 8 moved in the model's direction
- Negative-edge rows: 3 / 5 moved in the model's direction

The outcome slate was extremely underdog-heavy, but pregame market movement was mostly small. The model did not show useful directional outcome fit on this sample, and edge direction did not strongly predict pregame closing movement. The risk gate did its job: no actionable bets were emitted.

## Rows

| Game | Favorite | Signal | Edge | Bot P% | Close % | Move | Result | Fav Won |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| CHC@CLE | CHC | AVOID | -3.8 | 54 | 54.5 | +0.5 | CHC 1, CLE 0 | Yes |
| BAL@PIT | PIT | SKIP | -0.5 | 54 | 53.5 | -0.5 | PIT 8, BAL 2 | Yes |
| SD@BOS | BOS | SKIP | -0.3 | 60 | 59.5 | -0.5 | SD 8, BOS 6 | No |
| MIL@KC | KC | SKIP | -0.9 | 54 | 52.5 | -1.5 | MIL 8, KC 5 | No |
| TB@MIN | MIN | SKIP | +0.0 | 50 | 50.5 | +0.5 | TB 4, MIN 1 | No |
| TOR@CWS | TOR | SKIP | +0.1 | 60 | 60.5 | +0.5 | CWS 3, TOR 0 | No |
| CIN@TEX | TEX | SKIP | +0.8 | 54 | 53.5 | -0.5 | CIN 2, TEX 1 | No |
| MIA@NYY | NYY | SKIP | +1.1 | 72 | 72.5 | +0.5 | MIA 7, NYY 6 | No |
| PHI@COL | PHI | SKIP | +2.5 | 58 | 57.5 | -0.5 | COL 4, PHI 1 | No |
| HOU@OAK | HOU | SKIP | +1.0 | 54 | 53.5 | -0.5 | OAK 12, HOU 10 | No |
| NYM@SF | SF | SKIP | +0.3 | 52 | 52.5 | +0.5 | NYM 5, SF 2 | No |
| SEA@LAA | SEA | SKIP | +0.5 | 60 | 59.5 | -0.5 | LAA 8, SEA 7 | No |
| ATL@ARI | ATL | SKIP | +0.5 | 50 | 49.5 | -0.5 | ARI 6, ATL 5 | No |
| STL@DET | DET | SKIP | -0.3 | 56 | 57.5 | +1.5 | STL 5, DET 3 | No |

## Notes

- `CHC@CLE` is doubleheader-sensitive. The Polymarket slug resolved to Chicago Cubs and sampled as the first Cubs/Guardians market. The local snapshot `game_time_est` is ambiguous and appears unreliable for this game.
- The local snapshot time labels were not reliable enough for closing-price sampling. Official MLB `gameDate` was used instead.
- `PHI@COL` was the most important near-miss: edge was +2.5pp but confidence was only 63%, so the confidence gate blocked a bad bet.
- This sample supports keeping the current edge and confidence gates. It does not support loosening thresholds.

## Addendum (2026-04-17)

- Phase 4 advanced factors are now live in pipeline calibration.
- This Apr 5 review should be treated as a reliability baseline from the pre-Phase-4 configuration.
- Recalibration decisions should use fresh post-Phase-4 outcomes (target: at least 20 resolved actionable signals) before changing thresholds or factor weights.
