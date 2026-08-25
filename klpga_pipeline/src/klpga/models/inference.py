"""Read-only PRODUCTION inference layer for an UPCOMING tournament's
live entry list (`tournament_entry`), using the FROZEN v1 model M4
(`prior_avg_round_score_to_par` + `prior_recent_form_10` — see
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` and the freeze
decision recorded in `docs/SITE_STRUCTURE_TODO.md` section 10).

This module is orchestration ONLY. It builds no feature, no shrinkage
rule, no fitting procedure of its own — every one of those pieces is
imported unchanged from the already-frozen backtest/modeling layers:

  - `klpga.backtest.walk_forward.build_walk_forward_dataset` for the
    historical training corpus (feature rows + labels for every USABLE
    past tournament).
  - `klpga.backtest.point_in_time_features.compute_point_in_time_features`
    for each live entrant's point-in-time features, called with the
    SAME leakage-safe date-filtering machinery used everywhere else in
    this project.
  - `klpga.models.candidates.fit_candidate_model` / `predict_candidate_model`
    for M4's shrinkage/standardization/softmax mechanism, completely
    unmodified — no probability cap, manual weight, hand-set rookie
    probability, or post-hoc calibration is added anywhere in this
    module.
  - `klpga.models.math_utils.clip_and_renormalize` for the same
    pre-registered epsilon=1e-6 safety floor every other prediction in
    this project already goes through.

======================================================================
WHY `tournament_entry`, NOT `klpga.backtest.historical_field`
======================================================================
`historical_field.reconstruct_historical_field` is `player_event`
(RESULT-data) based and only valid for a tournament that has already
been played. An upcoming tournament (e.g. gameCode=2026080001) has no
`player_event` rows yet, so its field must instead come from
`tournament_entry` — the live, pre-tournament entry list collected by
`klpga.collectors.entry_list` (see schema.sql section 6). `tournament_entry`
has NO foreign key to `player_master` by design, because a real,
confirmed entrant (e.g. player_code=13355, "배윤철 0908(A)", confirmed
live 2026-08-25 against gameCode=2026080001) can be a rookie/unknown
player not yet in `player_master` — that row must still be stored and
predicted, never dropped.

======================================================================
STRICTLY-PRIOR CUTOFF POLICY (never guess "today")
======================================================================
An upcoming tournament typically has no resolvable date of its own
inside `tournament_master` (or may not have a `tournament_master` row
at all). This module NEVER defaults the historical cutoff to "today" or
any other guessed value. `resolve_cutoff_date` resolves the cutoff, in
order:

  1. An explicit `--cutoff-date` (a caller-supplied ISO-8601 date) —
     always wins if given.
  2. A `tournament_master` row for this `game_code`, IF one exists and
     its `effective_tournament_date` resolves to a real date.
  3. Otherwise: a hard `ValueError`. The caller must supply
     `--cutoff-date` explicitly rather than have this module guess.

Every population mean/std/shrinkage-k/beta/tau used by M4 in this
inference run is fit ONLY from historical (`tournament_master`-backed)
tournaments strictly before that resolved cutoff date — see
`_build_training_rows` below, which additionally excludes any target
tournament sharing this run's own `game_code` (defense in depth: the
live tournament has no `player_event` rows yet, so it could never
appear in `build_walk_forward_dataset()`'s output anyway, but this
guards against that assumption ever silently becoming false).

======================================================================
ROOKIE / UNMATCHED / SPARSE-HISTORY HANDLING
======================================================================
No new model-level logic exists here for these cases. A zero-history
entrant (`prior_events_n == 0`, whether a genuine rookie or an entrant
unmatched against `player_master`) already gets z=0 -> full shrinkage
to the training-fold population mean under M4's EXISTING mechanism
(`klpga.models.candidates.apply_shrinkage_and_standardize`) — this
module only adds DIAGNOSTIC REPORTING of which entrants fell into which
category (`EntrantPrediction.is_unmatched`, `.history_slice`, using the
same `ROOKIE_SLICES` bucketing as the backtest evaluation report), never
a different code path for computing their probability. Every entrant
receives a strictly-positive softmax probability by construction (see
`klpga.models.math_utils.softmax_from_logits`'s docstring) — none is
ever silently dropped, zeroed, or hand-assigned a probability.

======================================================================
HARD INVARIANTS (`_validate_invariants`)
======================================================================
Every probability must be finite and non-negative, and the field must
sum to `1.0 +/- 1e-6`. Failure of any invariant raises `RuntimeError`
and stops inference — this module contains NO silent-repair path.

Field-relative score is not Strokes Gained, and this v1 model contains
no SG/GIR/driving/putting/course-par proxy of any kind (see
`klpga.backtest.point_in_time_features`'s module docstring).
"""
from __future__ import annotations

import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Optional

from klpga.backtest.point_in_time_features import (
    compute_point_in_time_features,
    features_as_flat_dict,
    load_corpus,
)
from klpga.backtest.temporal import effective_tournament_date, is_strictly_before
from klpga.backtest.walk_forward import build_walk_forward_dataset
from klpga.models.candidates import MODEL_FEATURES, fit_candidate_model, predict_candidate_model
from klpga.models.math_utils import clip_and_renormalize
from klpga.models.walk_forward_eval import _slice_for_n

PRODUCTION_MODEL_ID = "M4"
CLIP_EPSILON = 1e-6
SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class LiveFieldEntrant:
    game_code: str
    player_code: str
    player_name_display: str
    in_player_master: bool


@dataclass(frozen=True)
class EntrantPrediction:
    rank: int
    player_code: str
    player_name: str
    win_probability: float
    prior_events_n: int
    prior_avg_round_score_to_par: Optional[float]
    prior_recent_form_10: Optional[float]
    prior_recent_form_10_n: int
    history_slice: str
    is_unmatched: bool


@dataclass(frozen=True)
class InferenceResult:
    game_code: str
    tournament_name: Optional[str]
    tournament_name_source: str  # "explicit_arg" | "tournament_master" | "unavailable"
    field_size: int
    cutoff_date: str  # ISO-8601
    cutoff_date_source: str  # "explicit_arg" | "tournament_master_fallback"
    training_tournament_count: int
    model_id: str
    model_features: tuple[str, ...]
    predictions: tuple[EntrantPrediction, ...]
    sum_probability: float
    min_probability: float
    max_probability: float
    zero_history_count: int
    unmatched_count: int
    predicted_count: int
    entrants_parsed: int
    dropped_entrants: int
    duplicate_player_codes: int


def resolve_cutoff_date(
    conn: sqlite3.Connection, game_code: str, cutoff_date_arg: Optional[str] = None
) -> tuple[str, str]:
    """Explicit-arg-first, `tournament_master`-fallback-second,
    error-if-neither cutoff resolution. Never guesses "today"."""
    if cutoff_date_arg is not None:
        try:
            date.fromisoformat(cutoff_date_arg)
        except ValueError as exc:
            raise ValueError(
                f"--cutoff-date {cutoff_date_arg!r} is not a valid ISO-8601 date (YYYY-MM-DD)"
            ) from exc
        return cutoff_date_arg, "explicit_arg"

    row = conn.execute(
        "SELECT start_date, end_date FROM tournament_master WHERE game_code = ?", (game_code,)
    ).fetchone()
    if row is not None:
        eff = effective_tournament_date(row[0], row[1])
        if eff.value is not None:
            return eff.value.isoformat(), "tournament_master_fallback"

    raise ValueError(
        f"No resolvable historical cutoff date for game_code={game_code!r}: no tournament_master "
        "row (or no usable start_date/end_date) exists for this gameCode. Pass --cutoff-date "
        "YYYY-MM-DD explicitly rather than guessing a default."
    )


def resolve_tournament_name(
    conn: sqlite3.Connection, game_code: str, tournament_name_arg: Optional[str] = None
) -> tuple[Optional[str], str]:
    if tournament_name_arg is not None:
        return tournament_name_arg, "explicit_arg"
    row = conn.execute(
        "SELECT event_name FROM tournament_master WHERE game_code = ?", (game_code,)
    ).fetchone()
    if row is not None and row[0]:
        return row[0], "tournament_master"
    return None, "unavailable"


def _detect_duplicate_player_codes(rows: list[tuple[str, str]]) -> list[str]:
    counts = Counter(player_code for player_code, _ in rows)
    return sorted(code for code, n in counts.items() if n > 1)


def fetch_tournament_entry(conn: sqlite3.Connection, game_code: str) -> list[LiveFieldEntrant]:
    """Authoritative live-field fetch — see module docstring. Ordered by
    player_code so run-to-run reproducibility (identical output on
    repeated execution) and insertion-order-independence both hold by
    construction, without needing any post-hoc sort-stability trick."""
    raw = conn.execute(
        "SELECT player_code, player_name_display FROM tournament_entry "
        "WHERE game_code = ? ORDER BY player_code",
        (game_code,),
    ).fetchall()
    if not raw:
        raise ValueError(f"tournament_entry has 0 rows for game_code={game_code!r} — nothing to predict.")

    dupes = _detect_duplicate_player_codes(raw)
    if dupes:
        raise RuntimeError(
            f"duplicate player_code(s) in tournament_entry for game_code={game_code!r}: {dupes} — "
            "inference stopped rather than silently deduplicating."
        )

    player_codes = [player_code for player_code, _ in raw]
    matched: set[str] = set()
    placeholders = ",".join("?" for _ in player_codes)
    for (player_id,) in conn.execute(
        f"SELECT player_id FROM player_master WHERE player_id IN ({placeholders})", player_codes
    ):
        matched.add(player_id)

    return [
        LiveFieldEntrant(
            game_code=game_code,
            player_code=player_code,
            player_name_display=player_name_display,
            in_player_master=(player_code in matched),
        )
        for player_code, player_name_display in raw
    ]


def _build_training_rows(
    conn: sqlite3.Connection, game_code: str, cutoff_date_obj: date
) -> tuple[list[dict], int]:
    """Every row belonging to a USABLE historical tournament strictly
    before `cutoff_date_obj`, excluding this run's own `game_code` (see
    module docstring). No feature/label from the target tournament
    itself, and no future-tournament row, can enter this training set."""
    dataset = build_walk_forward_dataset(conn)
    rows_by_target: dict[str, list[dict]] = {}
    for row in dataset.rows:
        rows_by_target.setdefault(row["target_event_id"], []).append(row)

    eligible = [
        t
        for t in dataset.target_order
        if t.game_code != game_code and is_strictly_before(t.effective_date, cutoff_date_obj)
    ]
    training_rows: list[dict] = []
    for target in eligible:
        training_rows.extend(rows_by_target.get(target.event_id, []))
    return training_rows, len(eligible)


def _validate_invariants(probs: dict[str, float], expected_codes: set[str]) -> None:
    """Hard-fails (raises) on any violation — no silent repair. See
    module docstring's "HARD INVARIANTS" section."""
    actual_codes = set(probs.keys())
    if actual_codes != expected_codes:
        missing = sorted(expected_codes - actual_codes)
        extra = sorted(actual_codes - expected_codes)
        raise RuntimeError(
            f"probability-field mismatch: missing={missing} extra={extra} — "
            "inference stopped rather than silently repairing the field."
        )
    for player_code, p in probs.items():
        if not math.isfinite(p) or p < 0:
            raise RuntimeError(
                f"invariant violated: player_code={player_code!r} probability={p!r} is not "
                "finite and non-negative."
            )
    total = sum(probs.values())
    if abs(total - 1.0) > SUM_TOLERANCE:
        raise RuntimeError(
            f"invariant violated: sum(probability)={total!r}, expected 1.0 +/- {SUM_TOLERANCE}."
        )


def run_inference(
    conn: sqlite3.Connection,
    game_code: str,
    cutoff_date_arg: Optional[str] = None,
    tournament_name_arg: Optional[str] = None,
) -> InferenceResult:
    """The single entry point real production inference should call —
    see module docstring for the full pipeline. Read-only: never
    executes an INSERT/UPDATE/DELETE against `conn`."""
    entrants = fetch_tournament_entry(conn, game_code)
    entrants_parsed = len(entrants)

    cutoff_date_str, cutoff_source = resolve_cutoff_date(conn, game_code, cutoff_date_arg)
    cutoff_date_obj = date.fromisoformat(cutoff_date_str)
    tournament_name, tournament_name_source = resolve_tournament_name(conn, game_code, tournament_name_arg)

    training_rows, training_tournament_count = _build_training_rows(conn, game_code, cutoff_date_obj)
    fitted = fit_candidate_model(PRODUCTION_MODEL_ID, training_rows)

    corpus = load_corpus(conn)
    field_rows: list[dict] = []
    feature_by_code: dict[str, dict] = {}
    for entrant in entrants:
        features = compute_point_in_time_features(
            corpus, game_code, cutoff_date_obj, entrant.player_code, entrant.player_name_display
        )
        flat = features_as_flat_dict(features)
        feature_by_code[entrant.player_code] = flat
        field_rows.append({"player_code": entrant.player_code, **flat})

    raw_probs = predict_candidate_model(fitted, field_rows)
    final_probs = clip_and_renormalize(raw_probs, epsilon=CLIP_EPSILON)

    expected_codes = {entrant.player_code for entrant in entrants}
    _validate_invariants(final_probs, expected_codes)

    ordered = sorted(entrants, key=lambda e: (-final_probs[e.player_code], e.player_code))
    predictions: list[EntrantPrediction] = []
    zero_history_count = 0
    unmatched_count = 0
    for rank, entrant in enumerate(ordered, start=1):
        flat = feature_by_code[entrant.player_code]
        n = flat["prior_events_n"]
        if n == 0:
            zero_history_count += 1
        if not entrant.in_player_master:
            unmatched_count += 1
        predictions.append(
            EntrantPrediction(
                rank=rank,
                player_code=entrant.player_code,
                player_name=entrant.player_name_display,
                win_probability=final_probs[entrant.player_code],
                prior_events_n=n,
                prior_avg_round_score_to_par=flat["prior_avg_round_score_to_par"],
                prior_recent_form_10=flat["prior_recent_form_10"],
                prior_recent_form_10_n=flat["prior_recent_form_10_n"],
                history_slice=_slice_for_n(n),
                is_unmatched=not entrant.in_player_master,
            )
        )

    probs_values = list(final_probs.values())
    return InferenceResult(
        game_code=game_code,
        tournament_name=tournament_name,
        tournament_name_source=tournament_name_source,
        field_size=entrants_parsed,
        cutoff_date=cutoff_date_str,
        cutoff_date_source=cutoff_source,
        training_tournament_count=training_tournament_count,
        model_id=PRODUCTION_MODEL_ID,
        model_features=MODEL_FEATURES[PRODUCTION_MODEL_ID],
        predictions=tuple(predictions),
        sum_probability=sum(probs_values),
        min_probability=min(probs_values),
        max_probability=max(probs_values),
        zero_history_count=zero_history_count,
        unmatched_count=unmatched_count,
        predicted_count=len(predictions),
        entrants_parsed=entrants_parsed,
        dropped_entrants=entrants_parsed - len(predictions),
        duplicate_player_codes=0,
    )
