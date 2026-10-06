# Stableford Pre-Event Blind Backtest — Gate Decision (2026-10-06)

Continues from commit `b9c2092` (2023/2024/2025 scoreRecord reconstruction, all 3 SOURCE PASS).

## Decision

**BACKTEST DATA NOT READY**

## What was built this turn (real, tested, not blocked)

- `klpga.website_v2.stableford_historical_dates` — real event_start_date for all 3 events, derived from each event's own captured page's literal `"* 라운드 마감 : <timestamp>"` round-close text (not guessed from the gameCode's month digits, not estimated from 2026's calendar slot). Tested against the raw HTML directly.
- `klpga.website_v2.stableford_backtest_snapshot` — the temporal snapshot builder, with an automated leakage assertion (`assert_no_leakage`) that fails loudly on any source row whose (season, month) is not strictly before the target's own (season, month).
- `klpga.website_v2.stableford_player_value` — the official formula's components (positive scoring contribution / bogey cost / double+ downside / net expectation), decomposed rather than collapsed to one number. Refuses a non-zero albatross rate unless a real source is named — never invents one (every real event sample captured has 0 albatross-classed cells).
- `klpga.website_v2.stableford_vs_strokeplay` — real, data-grounded demonstration of *why* a player's value differs between stroke-play and Stableford scoring (step 6): birdie (+2) is worth exactly double what bogey (−1) costs, where ordinary stroke-play treats them symmetrically (−1/+1). Verified against real 2025100001 data: 박민지 (birdie 14, bogey 9) improves from stroke-play rank 42 to Stableford rank 28; 이예원 (birdie 16, bogey 3, a *better* stroke-play card) lands at the same 29 Stableford points but barely moves rank (22→27) — the asymmetry rewards the birdie:bogey *trade ratio*, not the raw total.
- `klpga_pipeline/content/website_v2/STABLEFORD_BACKTEST_DATA_COVERAGE_V1.json` — the full per-feature coverage report below, machine-readable.
- 35 new tests across 4 new test files, all passing against real data (no fabricated fixtures).

## Why NOT READY — the blocking gap

Step 3's required formula (`8·P(Albatross) + 5·P(Eagle) + 2·P(Birdie) − P(Bogey) − 3·P(Double+)`) needs each player's **pre-event per-hole outcome rates**. Investigated exhaustively this turn (background agent + direct verification of every claim):

| Source checked | Real? | Covers birdie/eagle/par/bogey/double rate? |
|---|---|---|
| `klpga_pipeline/data/klpga.sqlite` (`player_round` table) | Schema has `birdies/eagles/pars/bogeys/double_bogey_plus` columns | **0 rows** — confirmed via direct `SELECT COUNT(*)` |
| `historical_sg_warehouse_corrected_v2.json` (104 tournaments, 2023-2026) | Real, 94-97% field coverage | **No** — Strokes Gained components only, no outcome counts |
| `historical_kranking_snapshots_v1/*.html.gz` | Real (k-rankings.klpga.co.kr) | **No** — rank/points/event-count only, and doesn't cover before Aug 2025 anyway |
| `historical_r1_groupings_blocker_resolution_v1/*.html.gz` | Real tee-time pairings | **No** — no scores at all, and doesn't even include these 3 gameCodes' exact neighbors |
| `official_tournament_warehouse_v1/*.json` | Real but thin | **No** — 3 tournaments, Sept 2023 only, R1 only |

No real source of pre-event birdie/eagle/par/bogey/double-or-worse rate exists anywhere in this repo or accessible session, for any of the 3 target events. `stableford_player_value.from_season_rates()` is built and tested, but there is nothing real to feed it for an actual player. Running it with invented rates to "see what happens" would be exactly the fabrication this entire task's instructions forbid.

A secondary, honest gap: the SG warehouse's own records carry no exact calendar date, only (season, month) via `game_code` — this turn's leakage rule is therefore conservative at **month granularity** (any same-October record is excluded entirely, not risked), which is safe but coarser than the day-level precision step 1 asked for.

## What this means for steps 4-5

Recency-window comparison (step 4) and blind evaluation — Spearman correlation, Top10/20 precision/recall, winner's predicted rank (step 5) — all require a real player-value number per the step-3 formula. Running them against SG totals instead would be a **different, unauthorized model substitution**, not what was asked for, so neither was run. The infrastructure (`stableford_backtest_snapshot.EventSnapshot`, real leakage-checked SG aggregates) is ready to receive real birdie/eagle/bogey rate data the moment a real source is found or collected — nothing needs to be rebuilt, only populated.

## Concrete next step, if the user wants to unblock this

Capture `scoreRecord?gameCode=<prior-tournament-code>` (the same already-validated endpoint and parser used for the 3 Stableford events) for each of the ~21-22 prior-season tournaments per year already identified in the SG warehouse — that would populate real `birdies/eagles/pars/bogeys/double_bogey_plus` counts per player per prior tournament, using `klpga.collectors.score_record.extract_hole_outcomes` exactly as already built and tested. This is a real, bounded, concrete acquisition task (not a vague "more data" ask) — roughly 60-70 total page fetches (22ish × 3 years, with overlap), one-time, from a machine with real klpga.co.kr access.

## Constraints honored

- No Iksan CC course coefficient computed or referenced for transplant to A-One CC (step 7) — the Stableford-vs-stroke-play mechanism demonstration above uses only the scoring-table transformation, never a course/hole effect.
- No Monte Carlo run. No 2026 win/Top5/Top10 probability generated or published.
- No test touched a real/original SQLite file — `klpga.sqlite` was only read via direct `sqlite3`/the existing read-only `scripts/21_data_coverage_report.py`, never written to.
- `neo_klpga_shot_source/` and Blue Heron/CMPro assets untouched.
- Explicit `git add <path>` staging only.
