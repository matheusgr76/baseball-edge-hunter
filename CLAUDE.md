# MLB Edge Hunter - Project Briefing

## What this is
MLB betting edge detection system. Finds mispriced MLB outcomes by comparing Polymarket prediction market odds against calibrated bookmaker consensus. Third project in the Edge Hunter family (NBA → Soccer → MLB).

## HARD RULES — Read first
1. **Bets are placed on Polymarket ONLY.** If a game has no Polymarket market, it does not exist. Skip it. Do not output it. Do not flag it.
2. **Moneyline ONLY.** No totals, no run lines, no props. The entire pipeline is binary: Team A wins or Team B wins.
3. **Bookmaker odds are REFERENCE data** — used to build consensus probability. We do NOT bet on bookmaker platforms.
4. **No Polymarket market = no pipeline run for that game.** Polymarket is the gatekeeper, not The Odds API.

## Architecture (5 layers — same as NBA/Soccer Edge Hunter)

```
mlb_edge_hunter/
├── CLAUDE.md                  # This file — read every session
├── config.py                  # API keys, thresholds, league config
├── requirements.txt
├── ingestion/
│   ├── bookmakers.py          # The Odds API → MLB bookmaker odds
│   ├── polymarket.py          # Gamma API → prediction market odds
│   └── mlb_data.py            # MLB stats API → injuries, bullpen, weather
├── normalization/
│   ├── devig.py               # 2-way devig (moneyline only)
│   └── teams.py               # Team name standardization across sources
├── calibration/
│   └── factors.py             # Situational adjustments (bullpen, weather, umpire, park)
├── comparison/
│   └── edge.py                # Edge detection + signal generation
├── orchestration/
│   └── pipeline.py            # Entry point: run_pipeline()
├── output/
│   └── ...                    # Signal reports, logs
└── tests/
```

## Core strategy
We are NOT building a sabermetric model. We are doing market-vs-market comparison:
1. Fetch Polymarket MLB markets (gamma API) — **this is step 1, the gatekeeper**
2. For each Polymarket game, fetch bookmaker consensus (The Odds API) → devig → "sharp probability"
3. Apply situational modifiers as FILTERS (not signal generators)
4. Compare: if edge > threshold → signal
5. Bet is placed on **Polymarket** (the prediction market), not on bookmakers

The edge comes from PRICE DISCREPANCY between Polymarket and sharp book consensus.
If Polymarket doesn't list a game, that game doesn't enter the pipeline.

## Polymarket API — MLB structure

### Discovery endpoint
```
GET https://gamma-api.polymarket.com/events?closed=false&tag={league_slug}&limit=100
```

### MLB slug (verify at project start)
Likely: `mlb` — MUST verify before coding. Check:
```
GET https://gamma-api.polymarket.com/events?closed=false&tag=mlb&limit=5
```

### Market structure expectation
MLB is binary (Team A wins / Team B wins) — simpler than soccer's 3-way.
- Each game should have one event with two binary markets
- Similar to NBA: "Will {Team} win {Game}?" → Yes/No
- Parse via `gamma-api.polymarket.com/markets?event_slug={slug}`

### CRITICAL: Verify market structure before building parser
NBA = 2-way binary (simple)
Soccer = 3-way via 3 separate binaries (complex)
MLB = likely 2-way binary like NBA — but VERIFY first

## Bookmaker odds (reference data only — we do NOT bet here)
```
GET https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?regions=us&markets=h2h&apiKey={key}
```
- `h2h` = moneyline (the only market we care about)
- Free tier: 500 requests/month

## Devig method
- Moneyline (2-way): Shin devigging or multiplicative — same as NBA

## Critical rules
- Entry point: `run_pipeline()` in `orchestration/pipeline.py`
- **Polymarket is the gatekeeper.** Only process games that exist on Polymarket.
- EdgeAnalysis is **PER-OUTCOME** (Team A ML, Team B ML) — moneyline only
- Alpha threshold: **2.5pp minimum** for actionable signals
- **Signal tiers (5 levels):**
  - 🔥 **Strong Bet** — edge ≥ 3.0pp + confidence ≥ 80%
  - ✅ **Bet** — edge ≥ 2.5pp + confidence ≥ 70%
  - ⏭️ **Skip** — edge < 2.5pp (not enough edge)
  - 👎 **Fade** — edge −1pp to −3pp (market overpriced on Polymarket)
  - 🚫 **AVOID** — edge < −3pp (strong negative edge, stay away)
- Situational modifiers are FILTERS on existing signals — they do NOT generate signals alone

## Calibration factors (situational filters)

### Tier 1 — High impact, apply always
| Factor | Source | Impact range | Notes |
|--------|--------|-------------|-------|
| SP matchup quality | FanGraphs/PyBaseball | ±5pp | Use SIERA or FIP, not ERA |
| Bullpen availability | Manual tracking or API | ±4pp | Penalize if top 2 RPs threw 25+ pitches in 48h |
| Weather (totals only) | Weather API | ±3pp | Temp, wind speed/direction, humidity |

### Tier 2 — Moderate impact, apply when data available
| Factor | Source | Impact range | Notes |
|--------|--------|-------------|-------|
| Team wRC+ vs SP handedness | FanGraphs | ±3pp | L/R splits matter enormously in MLB |
| Park factors | FanGraphs | ±2pp | Coors Field alone can swing totals 3+ runs |
| Umpire strike zone | UmpScorecards.com | ±2pp | "Pitcher's ump" + high-K SP = under lean |

### Tier 3 — Marginal, nice-to-have
| Factor | Source | Impact range | Notes |
|--------|--------|-------------|-------|
| Pythagorean W% delta | Baseball Reference | flag only | Teams due for regression |
| OAA (defense) | Baseball Savant | ±1pp | Ground-ball pitcher + bad infield = risk |

## Known bugs from previous Edge Hunters (avoid repeating)
- Don't call non-existent functions (NBA: `fetch_polymarket_odds` didn't exist)
- EdgeAnalysis must be per-outcome, not per-game
- User-Agent header required for all API calls
- Polymarket.com frontend is blocked from some servers — use `gamma-api.polymarket.com` directly
- Team name normalization is CRITICAL — build mapping dict from day 1

## Build order
1. **Phase 1a**: `ingestion/polymarket.py` — verify MLB tag, fetch + parse markets
2. **Phase 1b**: `ingestion/bookmakers.py` — fetch moneyline odds only
3. **Phase 1c**: `normalization/devig.py` — Shin devig for 2-way markets
4. **Phase 1d**: `normalization/teams.py` — cross-platform name mapping
5. **Phase 1e**: `comparison/edge.py` — edge detection per-outcome
6. **Phase 1f**: `orchestration/pipeline.py` — wire it together, validate output
7. **Phase 2**: `calibration/factors.py` — SP quality, bullpen availability
8. **Phase 3**: Validation, CLV tracking, backtest
9. **Phase 4**: Advanced factors (umpire, park, wRC+ splits)

## Output format — MUST MATCH basketball_edge_hunter

The output must replicate the basketball_edge_hunter report format. Two sections per game:

### 1. Per-game factor table (terminal)
```
╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║  ⚾  MLB EDGE HUNTER — FACTOR ANALYSIS ENGINE                                                               ║
║  Run: 2026-03-21 14:30:00                                                                                   ║
╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

============================================================================================================
  ⚾ PROCESSING: New York Mets @ Los Angeles Dodgers
============================================================================================================

  FACTOR                              | RESULT   | EXPLANATION                                              | DEVIL   | DEVIL ADVOCATE
  ------------------------------------+----------+----------------------------------------------------------+---------+----------------------------------------------
  SP QUALITY (SIERA/FIP)              |  +3.21%  | Dodgers SP (2.85 SIERA) vs Mets SP (4.12 SIERA)        | +0.00%  | Both pitchers on full rest
  BULLPEN AVAILABILITY                |  -1.50%  | Dodgers top 2 RPs threw 28+25 pitches in 48h            | -1.00%  | Fatigued bullpen may not hold lead
  TEAM wRC+ vs SP HANDEDNESS          |  +0.85%  | Dodgers 118 wRC+ vs RHP; Mets SP is RHP                 | +0.00%  | Split advantage confirmed
  MOMENTUM (L10)                      |  -0.42%  | Dodgers (L10 6-4) vs Mets (L10 7-3)                     | +0.00%  | Sequence without relevant distortion
  HOME/AWAY                           |  +1.20%  | Dodgers home advantage (Dodger Stadium)                  | +0.00%  | Standard home field
  INJURIES                            |  -2.10%  | Dodgers missing key position player (wOBA .380)          | -1.50%  | Lineup depth absorbs loss
  PYTHAGOREAN REGRESSION              |   FLAG   | Mets overperforming by +4 wins vs Pythagorean            | +0.00%  | Regression candidate flagged
  ...

  📊 PROBABILITY SUMMARY
  Calculated Probability: 62.4% | Analysis Confidence: (85%)
```

### 2. Analysis summary table (terminal) — CANONICAL FORMAT (locked 2026-04-04)

This format is locked to match basketball_edge_hunter exactly. Do not change column widths,
separator style, prefix chars, or alignment without updating this spec.

```
======================================================================
  📊 ANALYSIS SUMMARY
======================================================================

   GAME     | FAV   | T% | P% | C% |   E   | VERDICT
   --------+-------+----+----+----+-------+-----------
- PHX@CHA   | CHA   | 50 | 66 | 71 | -17.0 | AVOID     ⛔️
+ MIN@DET   | DET   | 71 | 60 | 81 | +10.3 | BET       ✅
  LAL@OKC   | OKC   | 76 | 76 | 78 |  +0.1 | SKIP      🔶
```

**Column spec (MUST NOT change):**
- Prefix: 1 char (`+` BET/STRONG BET, `-` FADE/AVOID, ` ` SKIP) + 1 space
- GAME: `<9` (abbr@abbr, e.g. `NYM@LAD  `)  ← data uses `<9` to align with 3-space header prefix
- FAV: `<5` (canonical abbreviation)
- T%, P%, C%: `>2` (integer percentage, no % sign)
- E: `>+5.1f` (signed float, e.g. `+10.3`, ` -3.1`)
- E header: `^5` (centered — matches basketball brand)
- VERDICT: `<10` + space + icon emoji
- Separator: `   {'-'*8}+{'-'*7}+{'-'*4}+{'-'*4}+{'-'*4}+{'-'*7}+-----------`
  Produces: `   --------+-------+----+----+----+-------+-----------`

**Prefix/icon mapping:**
| Signal     | Prefix | Icon |
|------------|--------|------|
| STRONG BET | `+`    | ✅   |
| BET        | `+`    | ✅   |
| SKIP       | ` `    | 🔶   |
| FADE       | `-`    | 🔄   |
| AVOID      | `-`    | ⛔️   |

### 3. CSV export
Same structure as basketball_edge_hunter: ROW_TYPE (HEADER/FACTOR/SUMMARY), one row per factor per game.
Columns: `ROW_TYPE, GAME, FAVORITE, DOG, FACTOR, RESULT (%), EXPLANATION, DEVIL (%), DEVIL ADVOCATE, CALC_PROB (%), CONFIDENCE (%), WCS, SIGNAL, MARKET (%), EDGE (pp)`

### Key formatting rules
- Session header: double-line box with `╔═╗║╚═╝` characters
- Sport emoji: ⚾ (not 🏀)
- Per-game separator: `=` line, 110 chars wide
- Factor table: pipe-separated, left-aligned names, right-aligned numbers
- Summary section title: `📊 ANALYSIS SUMMARY` (not "Session Summary")
- Column name: `SIGNAL` (not "BET")
- Signal emojis: 🔥 Strong Bet, ✅ Bet, ⏭️ Skip, 👎 Fade, 🚫 AVOID
- Actionable = Strong Bet + Bet only (listed under 🎯)
- No-signal fallback: `⏳ No actionable edges today...`
- Include signal legend at bottom of summary
- Summary table column widths are locked — see canonical format spec above
- E header must be centered (`^5`), GAME data rows must use `<9` (not `<8`)

## Dev environment
- Python 3.x
- Windows + WSL2/Ubuntu
- Claude Code in VS Code (or terminal)
- Git for version control

## Quality gates
- Every module must have at least smoke tests
- No hardcoded API keys — use `config.py` or env vars
- Log all API calls with timestamp and response status
- Verify pipeline output before marking task complete
- CLV (Closing Line Value) tracking from Phase 3 onward — this is the real validation metric

## IMPORTANT
- Add under a ## Debugging section at the top level of CLAUDE.md\n\nWhen debugging issues, ALWAYS
read
- the actual source code of relevant functions before diagnosing. Do not guess at root causes based
on symptoms alone — trace the logic through the code first.
- Add under a ## Workflow section in CLAUDE.md\n\nAfter completing code changes, always update
relevant documentation files (todo.md, HANDOFF.md, IP.md, README.md) to reflect the current state of
the project.
- Add under a ## Git section in CLAUDE.md\n\nDefault git workflow: commit changes with descriptive
messages, push to the current branch. Do not ask for confirmation on routine git operations unless
the target branch is ambiguous.