# NEO EXPECTED STROKES -- DATA CONTRACT v1

**Status: Phase 1 data-layer contract. No model fit. No SG. No player ranking.**

Scope: this document freezes the decisions from the 2026-09-21 red-team
review of the Phase 1 transition dataset built from the real cmpro
shot-level collection for game_code 2026090002 (Hana Financial Group
Championship, 108 players, 6,012 planned holes -- see
`cmpro_2026090002_final_qa.md`, FINAL DATA QA = PASS). It defines the
canonical schema, rules, and open items a future Expected
Strokes/Strokes-Gained model must build on. It is a contract for future
work, not a model, and not a training-data release.

Evidence basis: the real transition dataset run the operator reported
(shot rows = 24,667; STATE CONTINUITY mismatch_count = 0; FIRST SHOT
rows = 6,012, start_distance all NULL, start_lie all "티"; PAR
distribution par_3=3,970/par_4=13,890/par_5=6,807/unknown=0), plus the
real blank-lie (641 rows) and bunker (74 rows: par_4=46/par_5=28,
shot_no 2=66/3=7/4=1) evidence the operator supplied from running this
review cycle's own diagnostic tooling
(`klpga.expected_strokes.investigations`) against the real DB. This
sandbox has no direct access to that DB; every number above is the
operator's own real local output, not independently re-queried here.

---

## 1. Canonical State Schema

A shot's state is `(distance, lie, par-context)` at a point in a hole.
`TransitionRow` (`klpga.expected_strokes.transitions.TransitionRow`) is
the canonical row shape:

| Field | Type | Notes |
|---|---|---|
| `game_code`, `player_code`, `player_name`, `round_number`, `hole`, `shot_no` | identity | never null |
| `par` | `int \| None` | `None` until a real per-hole PAR source is supplied (`parse_score_record_hole_par` against a real captured page) |
| `start_distance_yd` | `float \| None` | `None` for every `shot_no==1` row until `course_yardage` (§4) is populated |
| `start_lie` | `str \| None` | raw value, always preserved (§2) |
| `end_distance_yd` | `float` | never null (parser always emits a value) |
| `end_lie` | `str` | raw value, always preserved (§2) |
| `holed` | `bool` | strict rule, §3 |
| `zero_distance_ambiguous` | `bool` | flag, §3 |
| `official_hole_score` | `int \| None` | `None` until real per-hole official-score evidence is supplied |

One row = one real shot_event record. No row is synthesized, merged, or
dropped by this schema.

## 2. Raw vs. Normalized Fields

- **Raw fields** (`start_lie`, `end_lie`) always carry the exact string
  the collector's own parser produced (one of `RAW_LIE_VALUES_FROM_PARSER
  = ("티","페어웨이","러프","그린","벙커","홀인","")`). Never discarded,
  never overwritten by a normalized label.
- **Normalized field**: `LIE_TAXONOMY[raw_value]` maps each raw value to
  one of `TEE / FAIRWAY / ROUGH / SAND / GREEN / HOLED / UNKNOWN`. This
  mapping is metadata computed alongside a row (via `taxonomy_gaps()` /
  `LIE_TAXONOMY` lookup), never stored in place of the raw value, and
  never used to silently reinterpret a row.
- 2026-09-21 decision: `""` -> `UNKNOWN` (previously `RECOVERY_OTHER`).
  `""` is the parser's own unrecognized-text catch-all -- see
  `transitions.py`'s block comment reading the parser's source directly.
  It is explicitly **not** treated as a golf lie. Real evidence: 641
  real blank-start rows span distance 0.0-567.4yd with repeated
  unchanged-distance chains, and every one of the 17 real
  `zero_distance_ambiguous` rows belongs to a blank-state chain -- a
  single physical "recovery lie" cannot explain that range. No single
  meaning (parser gap, penalty/ruling artifact, tee/transition artifact)
  is asserted for `UNKNOWN`; only structured evidence is reported
  (`blank_lie_investigation()` -- by shot_no/par/previous_lie/next_lie/
  distance bucket/top-30 examples), pending the operator's real-number
  review of that breakdown.
- `SAND` (raw `"벙커"`) is kept as its own real, distinct bucket -- not
  merged into `UNKNOWN`, not discarded. Real evidence (74 real
  start-bunker rows): `par_4=46, par_5=28` (sums to 74),
  `shot_no: 2=66, 3=7, 4=1` (sums to 74) -- a distance range inconsistent
  with a simple greenside-sand assumption. `SAND` is flagged **sparse**
  for modeling (`SPARSE_LIES = {"벙커"}`, used by the eligibility flag
  in §5) -- not an error classification, not excluded from the raw
  dataset, just insufficient/too-heterogeneous for an independent SAND
  expected-strokes curve yet.

## 3. HOLED Rule

```
holed = (end_lie == "홀인")   # strict, lie-only
```

Distance is never used as holed evidence, even at `end_distance_yd ==
0.0`. This is a real, DB-confirmed correction: 17 real rows on
2026090002 have `end_distance_yd == 0.0` with `end_lie != "홀인"`. The
collector's own QA-gate heuristic (`CmproShot.hole_out`) ORs in
`end_distance_yd==0.0` for a different, looser purpose (`validate_
cmpro_hole`'s "does this hole's last shot look holed out" check) and is
intentionally **not** reused here.

## 4. UNKNOWN Rule

```
zero_distance_ambiguous = (end_distance_yd == 0.0) and (end_lie != "홀인")
```

2026-09-21 decision: a row matching this condition is classified
**UNKNOWN/INVALID state**, never HOLED and never silently assigned any
other specific meaning. All such rows are preserved in the raw dataset
(`holed=False`, `zero_distance_ambiguous=True`) -- never deleted, never
excluded from CSV export. Full per-row detail (player/round/hole/
shot_no/start+end lie+distance/next shot's start lie/`is_final_shot`) is
available via `zero_distance_ambiguous_detail()`. The real 17-case
detail from this branch's tooling is pending the operator's local run;
the operator's own real-number review already established these 17
belong to blank-state chains (§2), which the full per-row detail will
make independently checkable rather than merely asserted.

## 5. First-Shot Yardage Requirement

`start_distance_yd` for `shot_no==1` stays `None` unless a real,
evidence-backed per-hole yardage record exists. **TEE+PAR+HOLE_ID is
explicitly rejected as a substitute Expected Strokes state** (2026-09-21
decision item 4) -- it was only ever a proposal pending review, and the
review's answer is: build the real ingestion contract instead.

`klpga.expected_strokes.course_yardage` defines that contract without
populating it:

```sql
CREATE TABLE course_yardage(
    game_code TEXT NOT NULL, round_number INTEGER NOT NULL, hole INTEGER NOT NULL,
    par INTEGER, yardage_yd REAL, source TEXT NOT NULL, source_hash TEXT NOT NULL,
    PRIMARY KEY(game_code, round_number, hole)
);
```

`load_course_yardage(conn, game_code)` is a pure, read-only loader:
returns `{}` if the table doesn't exist or has no rows for the game
(the real, current state of every existing collection) -- never
fabricates or back-calculates a value. It is wired into
`build_expected_strokes_dataset.py`'s `[FIRST-SHOT START STATE]` output,
which reports `BLOCKED` when empty, exactly like a real ingestion
pipeline would.

**Investigation result** (real, repo-search-based, no network access):
no official per-hole yardage source exists anywhere in the files
reachable from this QA branch's own git history. Checked: the real
scoreRecord per-hole PAR row (has PAR, no yardage), `klpga.discovery.
response_schema`'s `KIND_DISTANCE` field classifier (a generic
statistical-field-kind matcher, not a per-hole course source),
`klpga.collectors.cmpro_shots` itself (shot-level distances only, no
course yardage field), and no course/venue artifact for game_code
2026090002 anywhere in this branch's tree. See `course_yardage.py`'s own
module docstring for the exact list, including a documented **evidentiary
correction**: an earlier report in this review round cited two modules
(`klpga.neo_win.final_course_deep_dive`, `klpga.official_tournament_
warehouse.build_round_exposure()`) that are real files in this GitHub
repository, but live on other branches (`neo-website-v2` and several
`feat/hana-2026090002-*` branches) that are **not ancestors of this QA
branch** -- `git merge-base --is-ancestor` confirms neither is reachable
from this branch's HEAD. `final_course_deep_dive`'s own BLOCKED result
is additionally for a different tournament (game_code 2026090003) and a
different data shape (course-level aggregate stats, not per-hole
yardage -- yardage isn't even in its `REQUIRED_FIELDS`). Citing them as
if verified within this branch's own search was imprecise; it is
corrected here rather than repeated. No real per-hole yardage endpoint
has been identified in this collection's actual HTTP traffic on any
branch; discovering one (if it exists at all) is future work, not
attempted this round per "do not implement until reviewed."

## 6. Model Training Eligibility Flags

`klpga.expected_strokes.investigations.classify_model_eligibility(row)`
/ `model_eligibility_summary(rows)`. Named states (2026-09-21 decision,
replacing the prior review's provisional A-F letters):

| State | Condition |
|---|---|
| `ELIGIBLE` | none of the below apply |
| `FIRST_SHOT_DISTANCE_MISSING` | `shot_no==1` (§5 unresolved) |
| `UNKNOWN_LIE` | `start_lie==""` or `end_lie==""` (§2 UNKNOWN) |
| `ZERO_DISTANCE_UNKNOWN` | `row.zero_distance_ambiguous` (§4) |
| `SAND_SPARSE` | `start_lie` or `end_lie` in `SPARSE_LIES` (currently `{"벙커"}`) |
| `MULTIPLE_FLAGS` | 2+ of the above apply -- exact combination recorded in `MULTIPLE_FLAGS_combinations`, never collapsed or double-counted |

`sum_check` always equals `total_shots` exactly (self-tested, including
an explicit overlap/`MULTIPLE_FLAGS` case). Raw data is never altered or
dropped by this classification -- it is a label computed alongside the
24,667 raw rows, kept fully separate from the CSV export and the raw
DB.

**Recomputation note** (decision item 6): this flag scheme already
computes `UNKNOWN_LIE` from the raw `start_lie==""/end_lie==""` check
directly, not from the taxonomy label -- so the earlier "" -> UNKNOWN
rename (§2) changes the *label* shown in `[LIE TAXONOMY]` output but
does **not** change any eligibility count. The real
`A_fully_usable_transition=17,451` figure the operator reported under
the prior letter-based scheme is therefore expected to equal the new
`ELIGIBLE` count once the operator re-runs this branch's updated
tooling locally -- this has not been independently re-verified against
the real DB from this sandbox, and no such re-verification is asserted
here without that real re-run.

**IMPORTANT (decision item 7, restated in code and in every tool's own
output):** `ELIGIBLE` is a **QA/data-readiness classification only**,
not an approved training sample set. No Expected Strokes model has been
fit. No SG value has been computed. No player ranking has been
produced, published, or implied anywhere in this branch.

## 7. Exclusion / Retention Policy

**Nothing is excluded from the raw dataset by any rule in this
document.** All 24,667 real shot rows remain in the transition dataset
and its CSV export, regardless of eligibility state. Eligibility flags
are advisory labels for a future modeling step to filter on
deliberately and explicitly -- not a preprocessing step that silently
shrinks the data. Specifically:

- `zero_distance_ambiguous` rows: retained, `holed=False`, flagged, not
  deleted (§4).
- `""`/`UNKNOWN`-lie rows: retained with their raw `""` value intact
  (§2).
- `SAND`/bunker rows: retained as their own taxonomy bucket, not merged
  away (§2).
- First-shot rows: retained with `start_distance_yd=None` (§5).

A future model-training step decides, with its own explicit and
reviewed rationale, whether/how to filter by eligibility state -- that
decision is out of scope for this document and has not been made.

## 8. Future Multi-Tournament Accumulation Design

Not built this round; this section records the shape a future extension
would need, so it isn't designed ad hoc later:

- `build_transition_dataset(conn, game_code, ...)` already takes
  `game_code` as a parameter and is DB-agnostic beyond that -- calling
  it once per tournament and concatenating the resulting `TransitionRow`
  lists is the natural accumulation path. No schema change is needed to
  support this.
- `course_yardage` (§5) is already keyed by `(game_code, round_number,
  hole)`, not scoped to a single tournament's file -- a single
  `course_yardage` table can span every collected tournament once real
  data exists.
- Cross-tournament lie-taxonomy drift: `taxonomy_gaps()` should be run
  per tournament, not assumed stable -- a new tournament's cmpro capture
  could in principle surface a raw lie value `RAW_LIE_VALUES_FROM_PARSER`
  doesn't yet cover (the parser's own "" catch-all exists precisely
  because this has already been observed as a real gap once).
  `unmapped_values` is designed to catch this per-tournament, not
  once globally.
- `SPARSE_LIES`/eligibility thresholds are per-dataset-size judgments,
  not fixed constants -- what counts as "sparse" for SAND at 74
  observations in one tournament may not hold at N-tournament scale;
  revisiting `SPARSE_LIES` membership is expected future work once
  real multi-tournament volume exists, not a decision this document
  makes now.
- None of this is implemented in code this round -- only the schema/
  function shapes already in place are confirmed compatible with it.

---

## Next Steps (explicitly NOT this round)

- Do not fit an Expected Strokes model.
- Do not compute SG for any shot or player.
- Do not calculate or publish any player ranking.
- Do not treat `ELIGIBLE`/`A_fully_usable_transition` counts as an
  approved training sample without a separate, explicit review of that
  decision.

This contract is the reference point for that future review. Real
per-item numbers for the blank-lie, bunker, zero-distance, and
eligibility breakdowns described above (beyond what the operator has
already reported) require running this branch's updated
`scripts/build_expected_strokes_dataset.py` against the real DB, since
this sandbox has no direct access to it.

**Then stop for review**, per explicit instruction.
