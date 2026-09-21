# NEO CMPRO FULL COLLECTION — FINAL QA
## 하나금융그룹 챔피언십 (Hana Financial Group Championship), game_code = 2026090002

**Status: FINAL DATA QA = PASS**

Evidence source: real, local script output from `scripts/qa_cmpro_full_collection.py`
run by the operator against the actual collected SQLite warehouse and
manifest, and from `scripts/collect_cmpro_shots.py`'s own SCHEMA
(structural guarantees). This document was compiled from that real
output — no number in this report was fabricated or estimated. Numbers
this session's sandbox could not independently re-derive (no access to
the real SQLite file — confirmed by an exhaustive filesystem search
earlier in this review) are attributed to the operator's own local run
and marked as such throughout.

---

## 1. Collection Scope

| Field | Value |
|---|---|
| game_code | 2026090002 |
| Tournament | 하나금융그룹 챔피언십 (Hana Financial Group Championship) |
| Entrants (manifest_player_count) | 108 |
| Planned holes (manifest_planned_holes_sum) | 6,012 |
| Planned-holes structure | 63 players × 72 holes + 1 × 54 + 38 × 36 + 3 × 18 + 3 × 0 = 6,012 (verified by pure arithmetic, independent of DB access) |
| Planned-holes bucket counts (real) | `{0: 3, 18: 3, 36: 38, 54: 1, 72: 63}` — exact match to the expected structure |
| Round scope | R1–R4 |

## 2. Database Integrity

| Check | Real result |
|---|---|
| `hole_audit` rows for game | 6,012 |
| `hole_audit` rows with `qa_status=PASS` | 6,012 |
| Zero-shot PASS holes (a PASS hole_audit row with no shot_event rows) | 0 |
| Duplicate `shot_event` primary-key violations | 0 (also structurally guaranteed: `PRIMARY KEY(game_code,player_code,round_number,hole,shot_no)` in `collect_cmpro_shots.SCHEMA` makes this physically impossible to write) |
| Duplicate `hole_audit` primary-key violations | 0 (same structural guarantee via `PRIMARY KEY(game_code,player_code,round_number,hole)`) |
| `shot_no` continuity gaps (a hole whose recorded shot numbers aren't exactly 1..N) | 0 |
| PASS holes whose last shot doesn't end holed (`end_lie≠"홀인"` and `end_distance_yd≠0`) | 0 |
| **zero_distance_but_not_holed_lie_count** (`end_distance_yd=0.0` AND `end_lie≠"홀인"`) | **17** — see §9 Known Limitations. Does not affect hole-level `qa_status` or any count above; flagged forward for Expected Strokes modeling, where `holed` is now defined strictly from `end_lie=="홀인"`, never from distance alone. |

## 3. Manifest Coverage

| Check | Real result |
|---|---|
| Manifest player count | 108 |
| Manifest planned holes (sum) | 6,012 |
| Total missing planned holes (sum of per-player shortfalls, PASS holes < planned) | 0 |
| Total extra holes beyond plan (sum of per-player overages) | 0 |
| Players under their planned hole count | 0 |
| Players over their planned hole count | 0 |
| Duplicate player codes in manifest | `{}` (none) |

This closes the specific gap flagged in the prior review round: the
aggregate match (planned 6,012 = hole_audit 6,012) alone couldn't rule
out per-player missing/extra holes canceling out in the total. The
explicit per-player under/over-planned check above returns 0/0 — no
cancellation occurred.

## 4. Player/Round Coverage

| Check | Real result |
|---|---|
| Distinct players with any hole_audit row | 105 |
| Manifest players with 0 planned holes | 3 (see §8) |
| 105 + 3 = 108 | Consistent with manifest_player_count |
| Planned-holes bucket counts vs. expected | Exact match (§1) |

## 5. Shot Sequence Integrity

| Check | Real result |
|---|---|
| `shot_no` continuity gap holes | 0 |
| PASS holes with a non-holed last shot | 0 |
| Duplicate shot_event rows (PK) | 0 |
| Duplicate hole_audit rows (PK) | 0 |
| Zero-distance/non-홀인-lie shots (see §2, §9) | 17 |

## 6. Official Score Reconciliation

Official source: a real, operator-captured `scoreRecord` page for
game_code 2026090002 (klpga.co.kr `/web/tourRecord/scoreRecord`),
parsed with `klpga.collectors.score_record.parse_score_record_hole_by_hole`
(built and tested this review cycle against real captured markup — see
`tests/test_score_record_collector.py`).

| Round | Official player rows |
|---|---|
| R1 | 108 |
| R2 | 105 |
| R3 | 64 |
| R4 | 64 |

`official_score − cmpro_shot_count`, computed per real `hole_audit` row
(6,012 total):

| Classification | Count |
|---|---|
| MATCH (difference = 0) | 6,012 |
| OFFICIAL_PLUS_1 (difference = +1) | 0 |
| OFFICIAL_PLUS_2_OR_MORE (difference ≥ +2) | 0 |
| CMPRO_GREATER_THAN_OFFICIAL (difference < 0) | 0 |
| UNMATCHED (no official row found) | 0 |
| **PENALTY_REVIEW candidates** (+2-or-more or cmpro>official) | **0** |

Every single one of the 6,012 real holes reconciles exactly against
the independently-sourced official scorecard. No penalty-adjustment
ambiguity was found anywhere in the field.

## 7. 8+ Shot Review

14 real holes in the collection have `shot_count ≥ 8`. All 14 are
members of the 6,012-hole set reconciled in §6, where every hole
matched its official score exactly (MATCH=6,012, all other buckets 0)
— so all 14 of these high-shot-count holes are confirmed genuine
(official-reconciled), not collection artifacts.

Specifically verified example:

| player_code | player_name | round | hole | cmpro_shots | official_score | difference |
|---|---|---|---|---|---|---|
| 10867 | 양서후 | R2 | 18 | 12 | 12 | 0 |

(This is the same player independently confirmed elsewhere in this
review as a real, genuine new entrant not in the pre-tournament
population — see `HANA_2026090002_R1_PLAYER_RESULT_V1.json`'s own
`field_reconciliation.added_not_in_pre_population` note, an unrelated
artifact from earlier tournament-pipeline work, cross-referencing the
same player_code.)

The full itemized list of the other 13 holes (player/round/hole/shots)
was not individually re-transcribed into this session — their
inclusion in the zero-exception §6 reconciliation is the real evidence
for their correctness, not a re-listing.

## 8. Zero-Hole Player Review

Three manifest players have `planned_holes = 0`:

| player_code | player_name |
|---|---|
| 9702 | 김리안 |
| 9136 | 조혜림 |
| 12706 | 권은 0906(A) |

**Structurally confirmed** (real, cross-checked numbers): all three
have exactly 0 `hole_audit` rows, 0 `shot_event` rows, and are exactly
the `{0: 3}` entry in the real planned-holes bucket distribution (§1,
§4) — no orphaned or partial data exists for any of them anywhere in
the collection. This is a real, verified state, not an assumption.

**Not hardcoded, not assumed WD/DQ**: per operator instruction, these
three are never classified as WD/DQ without real playerScore/cache
evidence. `scripts/qa_cmpro_full_collection.py`'s `[NO PLAYED HOLES]`
section classifies each such player from their own real, cached
playerScore HTTP response into `NOT_APPLICABLE` / `FETCH_FAILED` /
`PARSE_FAILED_OR_STRUCTURE_CHANGED` / `UNVERIFIABLE` (never a single
hardcoded list) — that per-player classification's literal output was
not re-transcribed into this review session's chat, so it is **not**
restated here as a specific value for each of the three. **This is the
one open item in this report**: re-run
`qa_cmpro_full_collection.py`'s `[NO PLAYED HOLES]` section and confirm
each of the three lands on `NOT_APPLICABLE` (or another real,
evidence-backed non-WD/DQ classification) rather than
`UNVERIFIABLE`/`FETCH_FAILED`/`PARSE_FAILED_OR_STRUCTURE_CHANGED`, to
fully close this section with per-player evidence rather than
structural-only confirmation.

## 9. Known Limitations

1. **zero_distance_but_not_holed_lie_count = 17** (§2, §5). These 17
   real `shot_event` rows have `end_distance_yd = 0.0` but
   `end_lie ≠ "홀인"` — i.e., distance alone is not reliable evidence
   of holing out. Per explicit instruction, these are **not**
   reinterpreted as holed anywhere. `klpga.expected_strokes.transitions`
   (added this review cycle) now defines `holed` strictly from
   `end_lie=="홀인"` only — the collector's own QA-gate heuristic
   (`CmproShot.hole_out`, which OR's in `end_distance_yd==0.0`) is
   intentionally NOT reused for state modeling. Each of the 17 rows is
   preserved with an explicit `zero_distance_ambiguous=True` flag
   rather than dropped or silently reclassified. Full row-level detail
   (player/round/hole/shot_no) is available by re-running
   `scripts/build_expected_strokes_dataset.py` locally.
2. **Zero-hole player per-cache classification** (§8) — structurally
   confirmed, but the specific `NOT_APPLICABLE`/etc. classification
   text for each of the 3 players from a literal script run was not
   re-transcribed into this session.
3. **This report's numbers were not independently re-derived by this
   sandbox** — it has no access to the real collected SQLite file
   (confirmed earlier in this review via an exhaustive filesystem
   search: the sandbox is a fully isolated container with no mount or
   bridge to the operator's machine). All numbers above are the
   operator's own real local script output, cross-checked for internal
   arithmetic/structural consistency (bucket sums, 108−3=105 distinct
   players, PENALTY_REVIEW⊆all-mismatch-buckets, etc. — all consistent,
   no contradictions found) rather than independently re-queried.
4. Total `shot_event` row count (as opposed to `hole_audit`/hole-level
   counts) was not part of the specific gate re-confirmed this round
   and is not restated here as an aggregate number.

## 10. FINAL QA VERDICT

**FINAL DATA QA = PASS**

Basis: every one of the six specific gate numbers required before this
verdict (PLANNED_HOLES / PASS_HOLES / MISSING / EXTRA / DUPLICATES /
ZERO_SHOT_PASS) came back exactly at target — 6,012 / 6,012 / 0 / 0 /
0 / 0 — confirmed by real local script output, not inferred. Official
score reconciliation independently confirms all 6,012 holes with zero
exceptions in any mismatch category. Duplicate-key impossibility is
additionally guaranteed by the collection schema itself, not just the
observed data. The one open, disclosed item (§8's per-player cache
classification detail) is structural rather than a data-integrity
gap — it does not change any count in this report — and is carried
forward rather than blocking this verdict.

No re-collection, no DB modification, no production change occurred
in the production of this report.
