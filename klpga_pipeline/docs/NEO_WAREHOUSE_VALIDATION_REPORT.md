# NEO <-> Official (Profile + SG) Warehouse Validation (2026-09-12)

> Verdict: Warehouse construction succeeded (`WAREHOUSE_READY`). Official SG
> internally validates cleanly against itself (`OFFICIAL_SG_VALIDATION = PASS`).
> A real, moderate exposure-bias signal is confirmed
> (`EXPOSURE_BIAS_GATE = FAIL`). Per instruction, Warehouse readiness and NEO
> Ranking publication readiness are independent judgments: **`NEO_RANKING_PUBLICATION
> = BLOCKED`**, unchanged from the 2026-09-12 publication-validation report and the
> pre-existing `home_ranking.py` `FORMULA_STATE = BLOCKED_FORMULA_NOT_APPROVED` gate.
> No NEO weight, formula, or threshold was changed in this phase.

## 0. Safety / worktree

Worktree `wt_official_sg_val`, branch `feat/klpga-official-sg-validation-20260912`, base/production SHA `5dfdf20`. Primary checkout's 57 pre-existing dirty files (unrelated branch `feat/kb-pre-5probability-recovery`) were left untouched. No production, docs/, or HOME file was modified; no destructive git operation was run.

## 1-3. Source proof

| | Profile (Source A) | Official SG (Source B) |
|---|---|---|
| File | `raw_sources/KLPGA_RECORD_REPORT_2026_CAPTURE_B_EXPANDED.html` | `raw_sources/KLPGA_OFFICIAL_SG_2026_CAPTURE.html` |
| URL | `https://klpga.co.kr/web/record/totalRecord` | `https://klpga.co.kr/web/record/locationRecord` |
| SHA256 (re-verified fresh, matched expected) | `31ee0f10...` | `fbb5d3fa...` |
| Rows | 153 | 242 |
| Unique player codes | 153 | 242 |
| Duplicates / blank codes / blank names | 0 / 0 / 0 | 0 / 0 / 0 |
| Measured rounds range | n/a | min 1, max 73, median 22 |

Both re-hashed and matched their expected values exactly -- no HARD STOP triggered, no file substituted or reinterpreted.

## 4. Immutable raw snapshots

Flat, content-addressed files under `content/website_v2/` (the repo's existing convention -- confirmed by inspecting `KLPGA_RECORD_REPORT_WAREHOUSE_V1.json` and other `*_NORMALIZED.json`/`*_WAREHOUSE_V1.json` artifacts already in this tree; the deeply-nested `warehouse/<source>/<season>/<date>/raw|normalized/manifest.json` layout in the mission's own illustrative example was NOT adopted, per the mission's own instruction to prefer existing convention):

- `OFFICIAL_PROFILE_NORMALIZED.json` (`snapshot_id=record_report_record_report_v1_31ee0f1096f7e552`, `normalized_sha256=1960c502...`)
- `OFFICIAL_SG_NORMALIZED.json` (`snapshot_id=official_sg_official_sg_v1_fbb5d3fa3e4cb123`, `normalized_sha256=e1c5abcc...`)

Both write-once: re-running `scripts/116_build_official_profile_and_sg_warehouse.py` against identical source bytes is a verified no-op (idempotent); a second write attempt with different normalized content under the same `snapshot_id` raises `RecordReportSnapshotConflict`/`OfficialSGSnapshotConflict` (covered by focused tests). Manifest fields present: `source_url`, `capture_timestamp` (marked `UNKNOWN_BROWSER_CAPTURE_TIME` -- honestly, since neither raw HTML embeds an actual capture time; the upload timestamp is a processing artifact, never presented as source provenance), `source_sha256`, `source_rows`, `unique_players`, `parser_version`, plus the raw source file path.

## 5. Player identity join

**Profile <-> SG** (playerCode only): 150 matched, 3 profile-only, 89 SG-only, **0 name conflicts**.

**Warehouse <-> current NEO** (W36 TOP120 cohort): 112 of the combined Profile+SG playerCode universe matched a TOP120 player_id. 16 NEO players have no official Profile row; 9 have no official SG row (all subsets of the same 16 -- see Section 2 of the Record Report phase for their identities).

**AMBIGUOUS / name differences for the same playerCode**: 3 found (재-confirmed here, consistent with the Record Report phase's own finding) -- `11770`/`1485` carry a foreign-player `(I)` suffix on Profile+SG but not on the NEO cohort name; `11391` carries a birth-date+amateur `(A)` suffix on Profile only (absent from SG entirely). All 3 classified **NORMALIZATION_ONLY_DIFFERENCE**: each official name is the NEO base name plus a disambiguating suffix, a pattern independently observed on multiple *other*, unrelated rows in the same sources (see `NEO_OFFICIAL_IDENTITY_AUDIT.json` for the evidence trail). **No case of one playerCode resolving to two different actual identities was found.**

**108/109 discrepancy -- resolved with a fresh source check, not reused from memory alone**: `CURRENT_NEO_RANKED_COUNT = 108`, `VALIDATION_PENDING_COUNT = 12`, `SOURCE_OF_TRUTH_FILE = HOME_PLAYER_MASTER_TOP120_2026_W36.json`, `SOURCE_SHA256 = 5817d5cc87e07c7a9b039b2905b6f0c79da79a09dc5edd808fa511f35e4bcae3` (re-hashed in this worktree, matches the value already established in the 2026-09-12 NEO Ranking Publication Validation report -- W35's snapshot gives 109 due to normal weekly K-Ranking TOP120 cohort churn, not a bug; W36 is current).

## 6. Unified official player snapshot

`OFFICIAL_PLAYER_UNIFIED_SNAPSHOT.json`: 245 player_code rows (153 Profile ∪ 242 SG, deduplicated by code), each carrying independent `profile_source_provenance`/`sg_source_provenance` markers so every field's origin snapshot is traceable. Profile and Official-SG values are never merged into a shared field name.

## 7. Official SG internal integrity

Across all 242 rows with complete data: **0 SG_TOTAL vs (OTT+APP+ARG+PUTT) violations** at tolerance 0.05 (2 rows differ by exactly -0.02, inside tolerance -- a display-rounding artifact, not a real inconsistency). Distributions (`SG_TOTAL`: mean -1.14, median -0.62, std 2.51, min -14.50, max 3.81, p10 -4.18, p90 1.31 -- consistent with a season-cumulative-average metric across a wide skill range from a few extreme low-sample outliers to established tour players; full component distributions in `NEO_SAMPLE_RELIABILITY_AUDIT_INPUT_SG_INTEGRITY.json`). No outlier was deleted; the extreme low end (e.g. playerCode `1330`, `official_sg_rounds=2`, `SG_TOTAL=-14.50`) is flagged but preserved verbatim.

## 8. NEO SG <-> Official SG

NEO's only frozen, player-level, already-computed SG figure is `long_term_sg` (career mean of every historical event total, from `top120_validation.evaluate()`/`home_ranking.build_features()` -- used exactly as computed, never recomputed here). No frozen per-player NEO OTT/APP/ARG/PUTT feature exists anywhere in the codebase (`build_features()` only ever aggregates the warehouse's `total` field), so those four sub-component comparisons are genuinely **NOT_EVALUABLE**, not fabricated.

| | N | Pearson | Spearman | MAE | RMSE | mean bias (NEO-Official) |
|---|---|---|---|---|---|---|
| TOTAL | 104 | 0.733 | 0.737 | 0.629 | 0.819 | -0.384 |
| OTT/APP/ARG/PUTT | -- | NOT_EVALUABLE (no frozen NEO sub-component feature exists) |

Strong positive agreement (Pearson/Spearman both ~0.73-0.74). The -0.38 mean bias is flagged as an **observation**, explicitly not attributed to a cause: NEO's `long_term_sg` is a *career* average from the frozen warehouse; Official SG TOTAL is klpga.co.kr's own *season-2026-only* figure -- a genuine difference in time window by construction, offered as context, not asserted as the explanation for any individual player's divergence. Top-15 divergences in both directions are in `NEO_OFFICIAL_SG_CROSS_VALIDATION.json`.

## 9. Exposure bias audit

| official_sg_rounds bin | N | mean Off.SG | median Off.SG | mean NEO SG | median NEO SG | mean NEO rank | median NEO rank |
|---|---|---|---|---|---|---|---|
| 1-4 | 2 | 0.45 | 0.45 | 1.72 | 1.72 | 17.5 | 17.5 |
| 5-9 | 5 | -0.19 | -1.07 | -0.57 | -0.53 | 71.0 | 91 |
| 10-19 | 4 | 0.03 | -0.15 | -0.17 | -0.37 | 66.5 | 79.0 |
| 20-39 | 7 | -0.21 | -0.08 | -0.41 | -0.62 | 72.7 | 68 |
| 40-59 | 43 | 0.25 | 0.30 | -0.08 | 0.01 | 58.7 | 56 |
| 60+ | 43 | 0.86 | 0.86 | 0.30 | 0.33 | 41.9 | 38 |

`Spearman(official_sg_rounds, NEO_rank) = -0.358` (more measured rounds correlates with a **better/lower** NEO rank number -- a real, moderate effect). `Spearman(rounds, NEO_SG) = 0.215` (weak-positive: more rounds also mildly associates with a somewhat better NEO SG value itself, not purely a ranking artifact). `Spearman(rounds, NEO sample_count) = 0.267` (weak-positive; official rounds-this-season and NEO's own career tournament-sample count are related but not the same measure).

**Red-team question**: "측정 라운드가 많다는 이유만으로 NEO Ranking이 높아지는 경향이 존재하는가?" **Answer: 부분적으로 그렇다 (partially yes, evidenced)** -- a real, moderate (-0.358), not overwhelming, raw correlation exists. This is a *raw* correlation: SG performance level is not held constant in this single calculation (a full performance-controlled analysis is `NOT_EVALUABLE` within one snapshot -- would need matched-skill subgroups or a longitudinal design). The bin table's own small-N edges (N=2, N=4, N=7) mean the exact bin-to-bin shape should not be over-read; the aggregate Spearman is the more defensible number. Tournament-level exposure (`event_count`/`cut_count`/3R-4R completion) at the TOP120-cohort granularity is **NOT_EVALUABLE** in this worktree -- that specific breakdown exists only in the separate, unmerged `research/neo-ranking-v2` branch's Phase B/cut-selection work, not in this production-based tree.

## 10. Official Profile <-> Official SG sanity

| pair | N | Pearson | Spearman |
|---|---|---|---|
| average_score vs SG_TOTAL | 150 | -0.966 | -0.965 |
| GIR vs SG_APP | 150 | 0.778 | 0.784 |
| average_putts vs SG_PUTT | 150 | -0.810 | -0.784 |
| recovery_rate vs SG_ARG | 150 | 0.574 | 0.617 |
| birdie_rate vs SG_TOTAL | 150 | 0.821 | 0.818 |

All strongly signed in the theoretically-expected direction (a consistency check on the official data itself, not a causal claim) -- confirms internal coherence of KLPGA's own two published datasets.

## 11. NEO Ranking external validation

Spearman(NEO rank, official metric), matched population (N=99):

| metric | Spearman |
|---|---|
| official_sg_total | -0.836 |
| average_score | 0.839 |
| GIR | -0.683 |
| birdie_rate | -0.612 |
| recovery_rate | -0.543 |

All correctly signed (better official metric -> better/lower NEO rank number) and strong (|Spearman| 0.54-0.84). **Answering the four required questions:**
1. NEO 상위 선수들이 공식 SG에서도 대체로 강한가? **Yes** -- Top10/20/50 mean official_sg_total/average_score/GIR are consistently stronger than the full matched population's mean (see `NEO_OFFICIAL_RANK_DIVERGENCE_INPUT_EXTERNAL_VALIDATION.json` for the exact top-N distribution table).
2. 큰 rank disagreement는 누구인가? See Section 12's divergence table.
3. disagreement가 낮은 official sample size로 설명될 가능성이 있는가? Partially -- several top divergence rows carry the `LOW_SAMPLE` flag (official_sg_rounds < 10); flagged per-row rather than asserted as the universal explanation.
4. NEO가 공식 결과지표보다 먼저 잡아낸 것으로 보이는 선수가 있는가? **EARLY_SIGNAL = NOT_EVALUABLE_SINGLE_SNAPSHOT** -- exactly as instructed; no past value was backfilled into this snapshot to manufacture an answer.

## 12. Rank divergence table

`NEO_OFFICIAL_RANK_DIVERGENCE.json` holds the top 20 positive and top 20 negative `NEO_rank - Official_SG_rank` divergences, each with `playerCode`, `player_name`, both ranks, `official_sg_total`, `official_sg_rounds`, `average_score`, `GIR`, `birdie_rate`, and an explicit `LOW_SAMPLE` flag at the stated threshold (`official_sg_rounds < 10`). No cause is asserted in the artifact itself.

## 13. Sample reliability red team

| threshold | N | Spearman | Pearson | MAE |
|---|---|---|---|---|
| >=5 | 102 | 0.777 | 0.790 | 0.600 |
| >=8 | 98 | 0.793 | 0.799 | 0.592 |
| >=10 | 97 | 0.788 | 0.797 | 0.597 |
| >=12 | 95 | 0.793 | 0.799 | 0.602 |
| >=15 | 94 | 0.793 | 0.800 | 0.599 |
| >=20 | 93 | 0.791 | 0.798 | 0.603 |

Essentially flat across 5-20 (N only shrinks 102->93 since this already-NEO-ranked, already-TOP120 population is mostly high-exposure). **No threshold is selected or recommended here** -- observation only, per instruction.

## 14. No model tuning

Confirmed by construction: no file under `src/klpga/website_v2/{home_ranking,neo_ranking_backtest,top120_validation}.py` or `content/website_v2/NEO_RANKING_VALIDATION_MODEL_V1.json` was modified in this phase (verified in the diff at commit time -- see Files Changed).

## 15. Red team

| # | Attack | Verdict | Evidence |
|---|---|---|---|
| A | name-only identity contamination | PASS (not vulnerable) | Every join in this phase is coded to require `playerCode`/`player_id` match; `join_identity_by_player_code` (reused from the Record Report Warehouse) has no name-based path at all |
| B | duplicate playerCode | PASS | 0 duplicates in both real captures (153/153, 242/242 unique); parser raises `OfficialSGParseError`/`RecordReportParseError` on a synthetic duplicate (test-covered) |
| C | same playerCode / different name | PASS (handled, not silently resolved) | 3 real cases found, all classified NORMALIZATION_ONLY with evidence; 0 genuine identity conflicts; a synthetic genuine-conflict case is test-covered and reported, never auto-corrected |
| D | missing SG component | PASS | Rows with any missing component are excluded from the sum-check, not zero-filled; NULL preserved in the unified snapshot |
| E | blank interpreted as zero | PASS | `_clean_float`/`_clean_int` return `None` for an empty raw string, never `0`; test-covered for both warehouses |
| F | tiny official sample giving extreme SG | CONFIRMED but NOT a NEO vulnerability | Real case found (playerCode `1330`, 2 rounds, SG_TOTAL -14.50) -- but that player is **not in the TOP120 cohort at all**, so NEO never ranks or is exposed to this extreme value |
| G | more rounds mechanically improving NEO rank | CONFIRMED (real, moderate effect) | Spearman(official_sg_rounds, NEO_rank) = -0.358 (Section 9) -- a genuine, evidenced, moderate-not-overwhelming exposure bias |
| H | CUT players disadvantaged by fewer rounds | NOT_EVALUABLE | No frozen per-player cut/round-completion feature exists at TOP120-cohort granularity in this codebase (only on the separate research branch) |
| I | one hot tournament dominating NEO | NOT_EVALUABLE | Would require NEO's own per-event contribution breakdown for a specific player over time; out of scope for a single-snapshot cross-validation and not built here |
| J | current/future snapshot leakage | PASS | This phase makes no temporal claim about NEO's own history (already separately gated by `run_backtest`'s hard leakage assertion, unmodified); the official captures are both dated after NEO's frozen warehouse and are never fed back into it |
| K | official snapshot overwritten | PASS | `write_snapshot_immutable` raises on conflicting content under the same `snapshot_id`; verified via idempotent re-run (no-op) and a tampered-content re-write attempt (raises), both test-covered |
| L | NEO and official SG accidentally merged into same field | PASS | Every official field is prefixed `official_sg_*`/is a Profile field; NEO's own fields (`long_term_sg`, `neo_validation_rank`, etc.) are read from `top120_validation.evaluate()` output directly and never written into the official snapshot schema -- test-covered |
| M | rank ties incorrectly converted to unique ranks | PASS | 0 NEO rank ties observed (deterministic player_id tie-break, unmodified); Official SG rank ties are preserved as-is where they occur (2 tied ranks were found in the Record Report Profile phase and left tied, not force-split) |
| N | unmatched player silently dropped | PASS | Every unmatched playerCode/player_id from every join in this phase is enumerated explicitly in the JSON output (`PROFILE_ONLY`, `SG_ONLY`, `WAREHOUSE_UNMATCHED_TO_NEO`, `NEO_WITHOUT_OFFICIAL_PROFILE`, `NEO_WITHOUT_OFFICIAL_SG`) -- none are counted-and-discarded |
| O | current 108/109 NEO count discrepancy hidden | PASS | Restated explicitly in Section 5 with a fresh source-file hash check, not silently picked or omitted |

## 16. Validation gates

| Gate | Status | Evidence | Metric | Threshold | Measured | Artifact | SHA |
|---|---|---|---|---|---|---|---|
| SOURCE_PROFILE | PASS | fresh SHA256 re-check | rows/dupes/blanks | 0 dupes/blanks | 153/153/0/0 | OFFICIAL_PROFILE_NORMALIZED.json | 31ee0f10... |
| SOURCE_OFFICIAL_SG | PASS | fresh SHA256 re-check | rows/dupes/blanks | 0 dupes/blanks | 242/242/0/0 | OFFICIAL_SG_NORMALIZED.json | fbb5d3fa... |
| RAW_IMMUTABILITY | PASS | idempotent re-run + conflict-rejection test | write-once | n/a | verified twice | scripts/116 | n/a |
| IDENTITY | PASS | Section 5/15-C | genuine identity conflicts | 0 | 0 (3 normalization-only) | NEO_OFFICIAL_IDENTITY_AUDIT.json | n/a |
| PROFILE_SG_JOIN | PASS | Section 5 | matched/unmatched enumerated | n/a | 150 matched, 0 conflicts | NEO_OFFICIAL_IDENTITY_AUDIT.json | n/a |
| NEO_IDENTITY_JOIN | PASS | Section 5 | matched/unmatched enumerated | n/a | 112 matched | NEO_OFFICIAL_IDENTITY_AUDIT.json | n/a |
| SG_INTERNAL_INTEGRITY | PASS | Section 7 | component-sum violations | tol 0.05 | 0/242 | NEO_SAMPLE_RELIABILITY_AUDIT_INPUT_SG_INTEGRITY.json | n/a |
| TEMPORAL | PASS | red team J | future leakage | 0 | 0 | n/a (relies on unmodified run_backtest assertion) | n/a |
| **EXPOSURE_BIAS** | **FAIL** | Section 9 | Spearman(rounds, rank) | n/a (observational) | -0.358 | NEO_EXPOSURE_BIAS_AUDIT.json | n/a |
| NEO_OFFICIAL_SG_AGREEMENT | PASS | Section 8 | Spearman | n/a | 0.737 (N=104) | NEO_OFFICIAL_SG_CROSS_VALIDATION.json | n/a |
| RANK_DIVERGENCE | PASS (informational) | Section 12/11 | Spearman(rank, official metrics) | n/a | 0.54-0.84 | NEO_OFFICIAL_RANK_DIVERGENCE.json | n/a |
| SAMPLE_RELIABILITY | PASS | Section 13 | Spearman range across thresholds | n/a | 0.777-0.793 | NEO_SAMPLE_RELIABILITY_AUDIT.json | n/a |
| REPRODUCIBILITY | PASS | red team K | idempotent write | n/a | verified twice | scripts/116 | n/a |

No gate above is marked PASS without the cited evidence column populated -- none is a bare assertion.

## 17-18. Artifacts and tests

All 10 required artifacts written under `content/website_v2/` (existing flat convention): `OFFICIAL_PROFILE_NORMALIZED.json`, `OFFICIAL_SG_NORMALIZED.json`, `OFFICIAL_PLAYER_UNIFIED_SNAPSHOT.json`, `NEO_OFFICIAL_IDENTITY_AUDIT.json`, `NEO_OFFICIAL_SG_CROSS_VALIDATION.json`, `NEO_EXPOSURE_BIAS_AUDIT.json`, `NEO_OFFICIAL_RANK_DIVERGENCE.json`, `NEO_SAMPLE_RELIABILITY_AUDIT.json`, plus this report. (`OFFICIAL_PROFILE_RAW_MANIFEST.json`/`OFFICIAL_SG_RAW_MANIFEST.json` are folded into each `*_NORMALIZED.json`'s own manifest fields rather than duplicated as separate files, consistent with the Record Report Warehouse's existing single-file convention.)

14 new focused tests in `tests/test_official_sg_warehouse.py` covering: SG parser (real 242-row fixture, component-sum tolerance, blank!=zero, no-name-link row shape), playerCode identity/duplicate rejection, immutable snapshot idempotency + conflict rejection, official-vs-NEO namespace separation (no field-name collision), low-sample preservation (never dropped), rank-tie preservation, unmatched-player enumeration (never silently dropped), and reproducibility.

## 19-20. Commit / production

All work committed on `feat/klpga-official-sg-validation-20260912` only; `neo-website-v2` untouched.

**WAREHOUSE_READY = READY**
**OFFICIAL_SG_VALIDATION = PASS**
**EXPOSURE_BIAS_GATE = FAIL**
**NEO_RANKING_PUBLICATION = BLOCKED**
