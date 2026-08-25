"""Adversarial + integration tests for klpga.models.walk_forward_eval —
proving the M0-M6 walk-forward comparison engine satisfies every
hard constraint in this stage's instructions and the frozen
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`:

  - field probabilities sum to 1 / are finite / non-negative
  - target tournament cannot affect its own fitted parameters
  - future tournament cannot affect an earlier prediction
  - changing future results does not change earlier probabilities
  - rookie remains in field, with probability > 0
  - field-size changes are handled correctly
  - deterministic inputs produce deterministic predictions

This is on top of (not a replacement for) the existing
tests/test_point_in_time_features.py leakage tests, which this layer
still fully relies on (klpga.backtest.walk_forward is never re-derived
here).
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest

from klpga.models.candidates import MODEL_IDS
from klpga.models.walk_forward_eval import run_multi_model_walk_forward

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _tournament(conn, event_id, start_date):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, 2026, ?, ?)",
        (event_id, event_id, event_id, start_date, start_date),
    )


def _player(conn, player_id):
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))


def _event_row(conn, event_id, player_id, finish, score_to_par=-2, rounds_played=4):
    _player(conn, player_id)
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, 1, ?, ?)",
        (event_id, event_id, player_id, player_id, str(finish), finish, rounds_played, score_to_par),
    )


def _round_row(conn, event_id, player_id, round_number, round_score):
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_score) "
        "VALUES (?, ?, 2026, ?, ?, ?, ?)",
        (event_id, event_id, round_number, player_id, player_id, round_score),
    )


def _build_base_corpus(conn, n_tournaments=10, players=("A", "B", "C", "D", "E")):
    """n_tournaments, each with the same field, ranked A best..E worst
    on average with light variation so MLE has something to fit."""
    strengths = {p: -3.0 + i * 0.6 for i, p in enumerate(players)}
    for t in range(n_tournaments):
        event_id = f"T{t:02d}"
        _tournament(conn, event_id, f"2026-{(t % 12) + 1:02d}-01")
        # deterministic pseudo-noise via a simple hash-based offset so
        # rankings vary a bit without needing `random` (keeps every test
        # in this file fully deterministic without a seed argument).
        scores = {p: strengths[p] + ((t * 7 + i * 3) % 5) * 0.15 for i, p in enumerate(players)}
        ranked = sorted(players, key=lambda p: scores[p])
        for rank, p in enumerate(ranked, start=1):
            _event_row(conn, event_id, p, rank, score_to_par=int(round(scores[p] * 4)))
            for r in range(1, 5):
                _round_row(conn, event_id, p, r, 70 + int(round(scores[p])))
    conn.commit()


def _assert_probs_equal(a: dict, b: dict, tol: float = 1e-9):
    """Approximate equality — insertion order can differ between two
    runs when rows are deleted/re-inserted in a different order (e.g.
    the leakage tests below rewrite a tournament's own rows), which can
    shift floating-point SUMMATION order in softmax's normalization by
    a ULP or two. That is a numerical-precision artifact, not a
    leakage signal — leakage would show up as a REAL, non-trivial
    probability shift, not a difference at the 1e-15 level."""
    assert set(a.keys()) == set(b.keys())
    for k in a:
        assert math.isclose(a[k], b[k], rel_tol=tol, abs_tol=tol), f"{k}: {a[k]} != {b[k]}"


def _assert_valid_field_distribution(probs: dict, expected_players: set):
    assert set(probs.keys()) == expected_players
    for player, p in probs.items():
        assert math.isfinite(p), f"{player} probability not finite: {p}"
        assert p >= 0, f"{player} probability negative: {p}"
    total = sum(probs.values())
    assert abs(total - 1.0) < 1e-6, f"field probabilities sum to {total}, not 1.0"


# ----------------------------------------------------------------
# Hard constraints (Section 2 of this stage's instructions)
# ----------------------------------------------------------------


def test_every_model_every_tournament_sums_to_one_finite_nonnegative(conn):
    _build_base_corpus(conn)
    result = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    assert result.eligible_tournament_count > 0
    for model_id in MODEL_IDS:
        preds = result.predictions_by_model[model_id]
        assert len(preds) == result.eligible_tournament_count
        for pred in preds:
            _assert_valid_field_distribution(pred.probabilities, set(pred.probabilities.keys()))


def test_rookie_remains_in_field_with_positive_probability(conn):
    _build_base_corpus(conn, n_tournaments=5, players=("A", "B", "C"))
    # A debuting player F, with zero prior history, added to the LAST
    # tournament's field only.
    _tournament(conn, "T05", "2026-06-01")
    for rank, p in enumerate(["A", "B", "C"], start=1):
        _event_row(conn, "T05", p, rank, score_to_par=-2)
    _event_row(conn, "T05", "F", 4, score_to_par=5)  # rookie, finishes last, never wins
    conn.commit()

    result = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    target_pred = next(p for p in result.predictions_by_model["M1"] if p.target_event_id == "T05")

    assert "F" in target_pred.probabilities
    assert target_pred.probabilities["F"] > 0
    assert target_pred.prior_events_n_by_player["F"] == 0


def test_field_size_changes_handled_correctly(conn):
    # T00: 3-player field. T01: 8-player field.
    _tournament(conn, "T00", "2026-01-01")
    for rank, p in enumerate(["A", "B", "C"], start=1):
        _event_row(conn, "T00", p, rank, score_to_par=-rank)
    _tournament(conn, "T01", "2026-02-01")
    big_field = [f"P{i}" for i in range(8)]
    for rank, p in enumerate(big_field, start=1):
        _event_row(conn, "T01", p, rank, score_to_par=-rank)
    conn.commit()

    result = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=0)
    by_target = {p.target_event_id: p for p in result.predictions_by_model["M1"]}
    assert len(by_target["T00"].probabilities) == 3
    assert len(by_target["T01"].probabilities) == 8
    _assert_valid_field_distribution(by_target["T00"].probabilities, set(by_target["T00"].probabilities))
    _assert_valid_field_distribution(by_target["T01"].probabilities, set(by_target["T01"].probabilities))


def test_deterministic_inputs_produce_deterministic_predictions(conn):
    _build_base_corpus(conn)
    result_a = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    result_b = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)

    for model_id in MODEL_IDS:
        preds_a = result_a.predictions_by_model[model_id]
        preds_b = result_b.predictions_by_model[model_id]
        assert len(preds_a) == len(preds_b)
        for pa, pb in zip(preds_a, preds_b):
            assert pa.target_event_id == pb.target_event_id
            assert pa.probabilities == pb.probabilities, f"{model_id}/{pa.target_event_id} non-deterministic"


# ----------------------------------------------------------------
# Leakage adversarial tests (Section 10 of this stage's instructions)
# ----------------------------------------------------------------


def test_target_tournament_cannot_affect_its_own_prediction(conn):
    """Changing a target tournament's OWN outcome (finish positions,
    scores) must not change the probabilities predicted FOR that same
    tournament — its field members' predictions come entirely from
    THEIR prior history, never from T's own result."""
    _build_base_corpus(conn, n_tournaments=6, players=("A", "B", "C", "D"))
    result_before = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    target_before = {p.target_event_id: dict(p.probabilities) for p in result_before.predictions_by_model["M1"]}

    # Mutate T05's OWN outcome to something extreme (winner flips,
    # scores rewritten) — this only changes T05's LABEL, not any
    # player's prior-history features.
    conn.execute("DELETE FROM player_event WHERE event_id = 'T05'")
    for rank, p in enumerate(["D", "C", "B", "A"], start=1):  # reversed order, extreme scores
        _event_row(conn, "T05", p, rank, score_to_par=-50 if rank == 1 else 50)
    conn.commit()

    result_after = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    target_after = {p.target_event_id: dict(p.probabilities) for p in result_after.predictions_by_model["M1"]}

    _assert_probs_equal(target_before["T05"], target_after["T05"])
    # Every OTHER (earlier) tournament's prediction must also be unaffected.
    for event_id in target_before:
        if event_id == "T05":
            continue
        _assert_probs_equal(target_before[event_id], target_after[event_id])


def test_future_tournament_cannot_affect_earlier_predictions(conn):
    _build_base_corpus(conn, n_tournaments=6, players=("A", "B", "C", "D"))
    result_before = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    before_by_target = {
        mid: {p.target_event_id: dict(p.probabilities) for p in result_before.predictions_by_model[mid]}
        for mid in MODEL_IDS
    }

    # Insert a brand-new, chronologically LATER tournament with an
    # extreme, implausible outcome for the same players.
    _tournament(conn, "FUTURE", "2026-12-25")
    for rank, p in enumerate(["A", "B", "C", "D"], start=1):
        _event_row(conn, "FUTURE", p, rank, score_to_par=-999 if rank == 1 else 999)
        _round_row(conn, "FUTURE", p, 1, 1 if rank == 1 else 200)
    conn.commit()

    result_after = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=1)
    after_by_target = {
        mid: {p.target_event_id: dict(p.probabilities) for p in result_after.predictions_by_model[mid]}
        for mid in MODEL_IDS
    }

    for model_id in MODEL_IDS:
        for event_id, probs_before in before_by_target[model_id].items():
            probs_after = after_by_target[model_id][event_id]
            _assert_probs_equal(probs_before, probs_after)


def test_changing_future_results_does_not_change_earlier_probabilities(conn):
    """A variant of the leakage test that mutates an EXISTING later
    tournament's results (rather than inserting a brand new one) and
    confirms every strictly-earlier prediction is untouched."""
    _build_base_corpus(conn, n_tournaments=8, players=("A", "B", "C", "D"))
    result_before = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=2)
    before = {p.target_event_id: dict(p.probabilities) for p in result_before.predictions_by_model["M4"]}

    # T07 is the last (latest) tournament — mutate its results extremely.
    conn.execute("DELETE FROM player_round WHERE event_id = 'T07'")
    conn.execute("DELETE FROM player_event WHERE event_id = 'T07'")
    for rank, p in enumerate(["A", "B", "C", "D"], start=1):
        _event_row(conn, "T07", p, rank, score_to_par=-999 if rank == 1 else 999)
    conn.commit()

    result_after = run_multi_model_walk_forward(conn, MODEL_IDS, threshold=2)
    after = {p.target_event_id: dict(p.probabilities) for p in result_after.predictions_by_model["M4"]}

    earlier_targets = [eid for eid in before if eid != "T07"]
    assert earlier_targets, "test setup produced no earlier tournaments to check"
    for event_id in earlier_targets:
        _assert_probs_equal(before[event_id], after[event_id])
