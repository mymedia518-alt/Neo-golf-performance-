# NEO GOLF — Tournament Dashboard Spec (v0.1, design-only)

Status: **SPEC ONLY — no web app implemented in this round.** Read-only
UI/data-interface design over existing BETA #001-C artifacts. Does not
change the model, the DB schema, or any collection/prediction script.
Roadmap position: item 4 in `docs/NEO_TOURNAMENT_DASHBOARD_SPEC.md`'s
own guard (Section 10) — behind BETA #001-C stabilization, PRE/R1/R2/R3
recording, and post-tournament accuracy evaluation.

## 1. Core screen

One page, one tournament, full field.

**HEADER**: `NEO GOLF`, tournament name, `stage` (`PRE`/`R1`/`R2`/`R3`/`FINAL`),
last-updated timestamp, field size, model version.

**STAGE SWITCHER**: `[ PRE ] [ R1 ] [ R2 ] [ R3 ] [ FINAL ]` — each stage
maps 1:1 to one frozen prediction artifact (Section 5). Switching stage
never recomputes anything; it re-reads a different already-frozen file.

## 2. Main table

One sortable row per field player. Required columns:

| Column | Source |
|---|---|
| RANK | rank order within the loaded stage's frozen predictions |
| PLAYER | `player_name` |
| CURRENT POS | live leaderboard position — **not yet produced by any script in this repo**; PRE stage has no position at all (tournament hasn't started) |
| SCORE | live score-to-par — same gap as CURRENT POS |
| NEO WIN % | `win_probability` × 100, from the loaded stage's frozen prediction |
| CHANGE | delta vs. the immediately prior stage, same player_code (Section 3) |
| MAKE CUT % | only produced today by `klpga.neo_win.round_update` (BETA #001-R1); PRE stage has no cut-probability field yet |
| TOP 10 % | not yet produced by any script — `klpga.neo_win.model`/`beta001c_dataset` only produce WIN %, no TOP-k probabilities |
| FINAL ROUND % | not produced anywhere in this repo today |
| NEO SIGNAL | see Section 3 |

Default sort: NEO WIN % descending. All probability columns
click-sortable. Player-name search box filters rows client-side.

**Any column with no producing script today renders `--`, never a
computed placeholder.** Section 9 defines what actually gets built
before those columns can show real numbers.

## 3. NEO SIGNAL

Shows the probability change between two stages for one player, e.g.:

```
PRE 3.29%
R1  4.68%
CHANGE = +1.39p
```

`CHANGE` = `(current_stage_win_pct) - (prior_stage_win_pct)`, matched
by `player_code` (never by name — see Section 6).

**SIGNAL (RISING / STABLE / FALLING) threshold: UNDEFINED.**
No "NEO SIGNAL specification" with a numeric threshold exists anywhere
in this repository (`src/`, `docs/`, `tests/`) as of this spec. Per
this round's explicit instruction not to invent one, this field is
**NOT IMPLEMENTED** until a threshold is supplied. Until then the
dashboard must render the raw `CHANGE` value only and leave the
RISING/STABLE/FALLING label blank — never a guessed cutoff.

## 3a. Per-stage probability visibility (design rule, not yet implemented)

Confirmed real evidence (`klpga.neo_win.round_update`, `round_update_r2.py`):
this tournament format has exactly ONE cut, after Round 2 — so "make cut"
and "advances to R3/FINAL" are the SAME real event, never two independent
numbers (both modules already document and enforce this: `round_update_
r2.py`'s `neo_r3_pct`/`neo_final_pct` are literal, documented aliases of
`make_cut_pct`, never separately simulated). A future dashboard must never
render both a "CUT %" column and an "R3 qualification %" column side by
side as if they measured different things — pick ONE label per stage:

| Stage | Show | Never show | Why |
|---|---|---|---|
| PRE | WIN % | anything cut-related | round 1 hasn't happened; no cut concept exists yet |
| R1 | WIN %, CUT/R3-qualification % (one label, one number — `round_update.py`'s `post_r1_make_cut_pct`, still a genuine Monte Carlo probability since round 2 hasn't happened), CHANGE vs PRE | a separate "R3 %" alongside "CUT %" | same underlying simulated event |
| R2 | WIN %, CHANGE vs R1 | CUT probability | the cut is now a REAL, KNOWN fact (`player_event.made_cut`) — not a probability any more; `round_update_r2.py` already returns 100/0 (a resolved outcome), never a genuine forecast, so a dashboard must not present it as one |
| R3 | WIN %, final-round outcome probabilities where a real one is defined, CHANGE vs R2 | any recomputed cut/R3-qualification number | round 3 has already been played; nothing left to forecast about reaching it |

`round_update_r3.py` (scripts/46) now computes real TOP5/TOP10/TOP20 %
over the single remaining round (R4) — these ARE the "final-round
outcome probabilities where a real one is defined" this row refers to,
alongside WIN %. No cut/qualification-style column exists at R3 (there
is nothing left to forecast about reaching R4 — see the table above).

## 4. Player detail

Opens on row click (side panel or detail view). Shows:

- PLAYER, CURRENT SCORE, CURRENT POSITION (same live-leaderboard gap as
  Section 2)
- NEO WIN %, and PRE → CURRENT change (Section 3, same UNDEFINED-signal
  caveat)
- MAKE CUT %, TOP 10 %, FINAL ROUND % (same gaps as Section 2)
- **Performance Profile**: DRIVING / APPROACH / SHORT GAME / PUTTING /
  RECENT FORM / CONSISTENCY — read straight from the frozen #001-C
  snapshot's `predictions[i].feature_values` (see schema Section 5.2):
  `neo_driving`, `neo_approach`, `neo_short_game`, `neo_putting`,
  `prior_recent_form_10`, `neo_consistency_stddev`. **A `null` feature
  value renders exactly `N/A` — never estimated, never interpolated,
  never defaulted to a population mean for display purposes** (the
  model already handles missing data internally via shrinkage; the UI
  must not re-guess on top of that).

## 5. Data source — read-only

No new database. No new tables. No migration. The dashboard reads:

- `data/klpga.sqlite` — read-only (`mode=ro`), for live leaderboard
  fields only, if/when a live-leaderboard column becomes wired (today:
  not wired, see table gaps in Section 2).
- `neo_win_predictions/<year>/neo_win_<id>_<game_code>.json` — BETA
  #001's own frozen snapshots (`klpga.neo_win.archive`), for a PRE/R1
  stage predating #001-C.
- `neo_win_c_predictions/<year>/neo_win_c_<id>_<game_code>.json` — BETA
  #001-C's frozen snapshots (`klpga.neo_win.beta001c_archive`).
- `outputs/beta001_c/*.csv` / `*.md` — regenerable working output
  (feature matrix, backtest report, comparison, red-team), never the
  frozen source of truth.

**A frozen prediction file is never modified by the dashboard.** No
write path to `neo_win_predictions/`, `neo_win_c_predictions/`, or
`data/klpga.sqlite` exists in this spec.

## 6. Data integrity gate

Before rendering a stage's data as valid model output, verify (reusing
existing, already-tested functions — never reimplemented):

- Every row's `player_code` is in the tournament's field (`tournament_entry`
  for that `game_code`) — field-player-only.
- `duplicate player_code count == 0` within the loaded stage.
- `null probability count == 0` — every row has a real `win_probability`.
- `sum(win_probability) == 100%` within tolerance (`klpga.neo_win.leakage.
  validate_probability_sum`, already used by BETA #001/#001-C).
- Identity status preferred CLEAN (`klpga.neo_win.identity_resolution.
  build_full_identity_crosswalk`) — PARTIAL/AMBIGUOUS/BROKEN/UNMATCHED
  rows are shown, never hidden, but flagged (mirrors `klpga.neo_win.
  redteam`'s CLEAN/DATA_WARNING/IDENTITY_WARNING/MODEL_WARNING severity).

**On any failure the dashboard MUST NOT display the stage as valid
model output.** Show `DATA VALIDATION REQUIRED` in place of the table,
with the specific failed check(s) listed — never a partial or
silently-degraded table (same hard-fail convention as
`klpga.site.build`'s existing predictions-site generator).

## 7. Mobile

Priority columns only: PLAYER, SCORE, NEO WIN %, CHANGE, NEO SIGNAL.
Everything else (MAKE CUT %, TOP 10 %, FINAL ROUND %, Performance
Profile) moves to player detail only.

## 8. THREADS connection

A "TOP 10 WIN %" card must be generated FROM the same dashboard data
the table already validated — never a second, manually re-typed number.

```
MODEL → FROZEN PREDICTION → DASHBOARD → THREADS CARD
```

Concretely: the card-generation step reads the SAME already-validated,
already-loaded stage data structure (Section 5.2 schema) the table
rendered from, slices the top 10 rows by NEO WIN %, and formats them —
it never re-queries the DB, never re-runs the model, and never accepts
a hand-typed override.

## 9. Current scope (this round)

Built this round:
- `docs/NEO_TOURNAMENT_DASHBOARD_SPEC.md` (this file)
- `docs/NEO_DASHBOARD_DATA_SCHEMA.json`

NOT built this round: any web app, any UI code, any new script. No
existing BETA #001 / #001-C prediction artifact, model, or DB migration
was touched.

**Known gaps a future implementation round must close before Section 2's
table is fully real** (SKIP + LOG, not fixed here — out of this round's
scope):
1. CURRENT POS / SCORE — no live-leaderboard-to-prediction join exists.
2. FINAL ROUND % (a genuinely distinct final-round-outcome probability,
   not the make-cut alias) — WIN % exists for every stage; MAKE CUT % /
   R1-forecast-vs-R2-fact exists for R1 (`round_update.py`) and R2
   (`round_update_r2.py`) per Section 3a. TOP 10 % is now produced for
   R1, R2, AND R3 (`round_update_r3.py`, scripts/46 — also TOP5/TOP20).
   PRE still has none (no cut concept exists before Round 1).
3. NEO SIGNAL's RISING/STABLE/FALLING threshold — undefined, needs a
   real, disclosed specification before implementation (Section 3).
4. Section 3a's per-stage visibility rule is a design constraint only —
   no dashboard code exists yet to enforce it (Section 9's own "not
   built this round" still applies).

## 10. Roadmap guard

Current priority order (unchanged by this spec):
1. BETA #001-C stabilization
2. PRE/R1/R2/R3 prediction recording
3. Post-tournament prediction-accuracy evaluation
4. Dashboard v0.1 implementation

A mid-conversation question about a new feature is a question, not a
roadmap change, unless explicitly marked `ROADMAP CHANGE`. New ideas
raised go to **BACKLOG** below, not into scope.

### BACKLOG
(empty — nothing raised yet)

## 11. Data schema

See `docs/NEO_DASHBOARD_DATA_SCHEMA.json` for the machine-readable
interface (header, main-table row, player-detail, validation-result
shapes), each field traced to the real script/module that produces it
or marked `null`/absent with the reason.
