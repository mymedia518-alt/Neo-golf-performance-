# NEO Prediction Archive

**Status: implemented 2026-08-26.** This document describes the
immutable, append-only record of what NEO predicted for a tournament
BEFORE it began — separate from, and never mutated by, the model
layer (`src/klpga/models/`) or any later post-tournament evaluation.

This archive package computes nothing. Every number in a prediction
snapshot is copied unchanged from an already-computed
`klpga.models.inference.InferenceResult` (the frozen v1 model, M4 —
see `docs/SITE_STRUCTURE_TODO.md` section 10 for the freeze decision).
`src/klpga/archive/prediction_archive.py` only reshapes and durably
writes that result; it never fits, shrinks, standardizes, or
softmaxes anything.

---

## Four things this archive keeps carefully separate

A single prediction can be described along four independent axes.
Confusing any two of them is exactly the kind of thing this archive
exists to prevent:

| Axis | What it answers | Where it lives |
|---|---|---|
| **MODEL VERSION** | Which frozen model produced this number? | `model_id` ("M4") + `model_version` ("v1") — fixed constants, identical across every prediction until a future model is frozen and promoted. |
| **PREDICTION ID** | Which specific archived record is this? | `prediction_id` ("001", "002", ...) — assigned explicitly by the operator on the CLI, never auto-incremented, never reused for the same `game_code`. |
| **PREDICTION DATE / CUTOFF** | As of what date was "prior" information cut off? | `cutoff_date` + `cutoff_source` — the strictly-prior boundary `run_inference()` actually used to fit M4 and compute features. This is NOT `created_at_utc`. |
| **POST-TOURNAMENT RESULT** | What actually happened, and how good was the prediction? | Not part of this archive at all — see "Post-tournament evaluation" below. Never written into the prediction file. |

A fifth, easily-confused timestamp is also kept separate on purpose:
**`created_at_utc`** is when the *archive file* was written (wall-clock,
at archiving time) — not when the original CMD run happened, and not
the tournament's cutoff date. For a `rerun_reconstruction`, this is
explicitly the *reconstruction* time, never a guess at the original
run's time (see "Provenance" below).

---

## Schema

One JSON object per prediction, written to
`predictions/<cutoff_year>/prediction_<id>_<game_code>.json`, plus a
`.csv` sibling containing only the per-entrant table:

```json
{
  "prediction_id": "001",
  "created_at_utc": "2026-08-26T00:02:35Z",
  "record_kind": "neo_prediction_archive_v1",
  "game_code": "2026080001",
  "tournament_name": "제15회 KG 레이디스 오픈",
  "cutoff_date": "2026-08-27",
  "cutoff_source": "explicit_arg",
  "model_id": "M4",
  "model_version": "v1",
  "model_features": ["prior_avg_round_score_to_par", "prior_recent_form_10"],
  "training_tournament_count": 100,
  "field_size": 120,
  "entrants_predicted": 120,
  "dropped_entrants": 0,
  "probability_sum": 1.0000000000000002,
  "minimum_probability": 0.00xxxx,
  "maximum_probability": 0.100967xxxxxx,
  "zero_history_count": 0,
  "unmatched_count": 1,
  "required_final_checks": {
    "entrants_parsed_eq_field_size": true,
    "entrants_predicted_eq_field_size": true,
    "dropped_entrants_eq_zero": true,
    "duplicate_player_codes_eq_zero": true,
    "probability_sum_within_tolerance": true
  },
  "known_limitations": ["Coarse calibration diagnostics suggest possible over-confidence ..."],
  "provenance": { "source": "live_atomic_inference" },
  "predictions": [
    { "rank": 1, "player_code": "11134", "player_name_display": "서교림",
      "win_probability": 0.100967..., "prior_events_n": ..., "prior_avg_round_score_to_par": ...,
      "prior_recent_form_10": ..., "prior_recent_form_10_n": ..., "history_slice": "...",
      "player_master_matched": true }
    /* ... one row per entrant ... */
  ]
}
```

The JSON is **authoritative**. The CSV (`utf-8-sig` encoded so Excel on
Windows renders Korean player names correctly without a manual
import-encoding step) is a **convenience representation of the
`predictions` array only** — it is always regenerable from the JSON
and is never treated as a second source of truth.

`json.dumps(..., indent=2)` is called with a **fixed, hand-authored key
order** (Python dict insertion order, not sorted-by-hash) — two calls
on equal data always produce byte-identical text, which is what makes
the archive meaningful in `git diff`.

---

## Immutability

`write_prediction_snapshot_atomic()`:

1. Writes the full, already-validated content to a temp file **in the
   same directory** as the final path, then `fsync`s it.
2. Claims the final filename with `os.link()` — an atomic,
   exists-fails hard-link create, not a check-then-write race. If the
   final path already exists, this raises `FileExistsError`, converted
   to `PredictionAlreadyArchivedError`, and **nothing is written**.
3. If hard links aren't supported by the target filesystem (rare), it
   falls back to an existence-check-then-`os.replace()`, which
   reopens a narrow TOCTOU race — disclosed here, not hidden. The
   primary path avoids this entirely.
4. The temp file is always removed, on every exit path.

There is **no UPDATE path anywhere in this module.** A duplicate
`(prediction_id, game_code)` always fails loudly, before any byte is
written at the final path. Existing prediction files are never
regenerated from newer data, never merged, never silently replaced.

JSON is written first. If the JSON claim succeeds but the CSV claim
then fails for any reason other than "already exists," the JSON is
left in place (it is already complete and valid) and a `RuntimeError`
names the CSV problem explicitly — never a corrupted-looking archive,
never silent data loss.

---

## Provenance: `live_atomic_inference` vs `rerun_reconstruction`

Every snapshot's `provenance.source` is exactly one of:

- **`"live_atomic_inference"`** — `run_inference()` was called exactly
  once, in the same process, immediately before archiving
  (`scripts/24_archive_prediction.py --source live_atomic_inference`).
  This is the **only** source that may ever be treated as the
  authoritative record of what NEO predicted. Prediction #002 onward
  always uses this path.

- **`"rerun_reconstruction"`** — the archived run is a deterministic
  re-execution of inference, standing in for an earlier real run whose
  complete 120-row output was never captured to a machine-readable
  file. **This is never labeled "original."** It carries additional,
  required fields:
  - `original_run_status` — what is known about the real first run
    (e.g. `"successful_pre_tournament_run_observed"`).
  - `original_machine_readable_snapshot_available` — always `false`
    for the known #001 situation.
  - `reconstruction_reason` — free text explaining why reconstruction
    was necessary.
  - `verification` — every observed fact from the real first run that
    the reconstruction was cross-checked against before being allowed
    to archive.

A reconstruction is **only ever archived if it passes
`verify_against_observed_facts()`** against operator-supplied
`--verify-*` flags. Any mismatch — training tournament count, field
size, dropped entrants, probability sum, the rank-1 player's code,
name, or 3-decimal-place display probability — **aborts before
anything is written**, with the specific mismatch printed.

The display-probability check compares the SAME rounding the CLI
prints (`round(probability * 100, 3)`), never the stored value — the
archive always keeps the reconstruction's own full-precision
probability. **The stored probability is never rounded or clamped to
match a previously-observed display value.**

---

## Database-state honesty

Because a reconstruction depends on the historical training database
being unchanged between the real first run and the reconstruction,
`scripts/24` always prints a **DATABASE-STATE DIAGNOSTIC** section
before archiving anything: historical training tournament count,
latest historical tournament date actually used (reusing
`klpga.models.inference._build_training_rows`, unmodified — not a
second implementation of the training-population rule), field size,
zero-history count, unmatched count.

**No pre-run database checksum/hash was captured before the first
production run**, so "the database has not materially changed since
then" cannot be cryptographically proven by this tool. The
`--verify-*` cross-check is an **operator-supplied consistency check
against independently recorded facts**, not a database integrity
proof. This limitation is disclosed here and printed by the CLI itself
— it is never silently assumed away.

---

## Future workflow (Prediction #002 onward)

```
collect official entry list
  -> run frozen production inference once (scripts/24, --source live_atomic_inference)
  -> required invariants PASS (enforced by run_inference() itself — raises otherwise)
  -> archive exact InferenceResult atomically (single command, same process)
  -> publish prediction
  -> tournament begins
  -> archive remains unchanged (append-only, no UPDATE path exists)
  -> after the tournament ends, evaluate the prediction separately (see below)
```

`scripts/24_archive_prediction.py` is the single sanctioned command
for this — it replaces the old two-step "run `scripts/23`, eyeball the
output, maybe write it down" flow that produced Prediction #001's gap
in the first place.

---

## Post-tournament evaluation — design only, not implemented

A future, separate module (e.g. `src/klpga/archive/evaluation.py`)
will read one `PredictionSnapshot` (via `read_prediction_snapshot()`,
which only ever opens a file for reading) plus that tournament's real
outcome, once available in `player_event`/`player_round`, and produce
a **separate** file, `prediction_<id>_<game_code>.evaluation.json` —
never writing into the original prediction file. It will report:

- winner probability (as predicted, from the archive — never
  recomputed)
- winner's pre-tournament rank
- Top1 / Top3 / Top5 / Top10 hit (yes/no)
- per-tournament log loss and normalized Brier

reusing `klpga.models.metrics.log_loss` / `brier_norm` / `winner_rank`
unchanged (the same evaluation math already used in the M0-M6
backtest), computed against the archived probabilities — never against
a fresh rerun. Prediction generation and post-tournament evaluation
are, and must remain, two separate commands operating on two separate
files.

---

## Known model limitation (restated, not corrected)

Every archived snapshot carries the same disclosed limitation
recorded at the M4 freeze decision (`docs/SITE_STRUCTURE_TODO.md`
section 10), verbatim, in `known_limitations`:

> Coarse calibration diagnostics suggest possible over-confidence in
> some higher probability bins, especially approximately 10-20%. Not
> corrected in this prediction.

Archiving a prediction never recalibrates, caps, or reweights its
probabilities — the archive is a record of what M4 actually produced,
limitation included.

---

## Windows commands

Live prediction (#002 onward):
```
python scripts\24_archive_prediction.py --db data\klpga.sqlite --game-code 2026080001 ^
  --prediction-id 002 --source live_atomic_inference
```

Prediction #001 reconstruction (see "Provenance" above — requires all
`--verify-*` flags, aborts on any mismatch):
```
python scripts\24_archive_prediction.py --db data\klpga.sqlite --game-code 2026080001 ^
  --cutoff-date 2026-08-27 --tournament-name "제15회 KG 레이디스 오픈" ^
  --prediction-id 001 --source rerun_reconstruction ^
  --verify-training-tournament-count 100 --verify-field-size 120 ^
  --verify-dropped-entrants 0 --verify-probability-sum 1.000000 ^
  --verify-top-player-code 11134 --verify-top-player-name "서교림" ^
  --verify-top-player-display-pct 10.097
```
