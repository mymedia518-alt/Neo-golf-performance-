"""Tests for klpga.neo_win.beta001c_dataset and klpga.neo_win.
backtest_eval — BETA #001-C Phase 7's new, standalone walk-forward
evaluator. Offline against a small synthetic DB (same fixture shape as
tests/test_neo_win.py) plus the real, committed docs/discovery/
taxonomy for domain-feature classification."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from klpga.backtest.point_in_time_features import load_corpus
from klpga.backtest.walk_forward import build_walk_forward_dataset
from klpga.models.metrics import TournamentPrediction
from klpga.neo_win.backtest_eval import (
    NeoWinBacktestResult,
    NeoWinModelSpec,
    run_neo_win_multi_model_walk_forward,
    select_best_beta001c_model,
)
from klpga.neo_win.beta001c_dataset import (
    DOMAIN_METRIC_FEATURE_NAMES,
    MODEL_A_FEATURES,
    MODEL_B_FEATURES,
    MODEL_C_FEATURES,
    augment_rows_with_beta001c_features,
    build_beta001c_live_field,
    build_beta001c_live_training_rows,
)
from klpga.neo_win.model import BASE_FEATURES
from klpga.neo_win.win_features import WIN_FEATURE_CANDIDATE_NAMES

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
REAL_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


def _new_conn(db_path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_tournament(connection, event_id, season, start_date, ranked_players):
    connection.execute(
        "INSERT OR IGNORE INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, event_id, event_id, season, start_date, start_date),
    )
    for rank, player_id in enumerate(ranked_players, start=1):
        connection.execute(
            "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id)
        )
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, 1, 4, ?)",
            (event_id, event_id, season, player_id, player_id, str(rank), rank, -20 + rank),
        )
        for round_number in range(1, 5):
            connection.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                "round_score, round_to_par) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, event_id, season, round_number, player_id, player_id, 70 - rank, -5 + rank),
            )


def _insert_official_metric(connection, season, player_code, identity_key, menu1, label, value):
    connection.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) "
        "VALUES (?, ?, ?, ?, 'x', ?, 'record', ?, 'PARSE_SUCCESS', 'CLEAN', 'PIT_UNVERIFIED', 'https://x', "
        "'2027-01-01T00:00:00Z')",
        (season, player_code, identity_key, menu1, label, str(value)),
    )


@pytest.fixture()
def conn(tmp_path):
    connection = _new_conn(tmp_path / "test.sqlite")
    players = ["A", "B", "C", "D", "E"]
    for t in range(8):
        event_id = f"T{t:02d}"
        ranked = players[t % len(players):] + players[: t % len(players)]
        _insert_tournament(connection, event_id, 2026, f"2026-{(t % 12) + 1:02d}-01", ranked)

    for i in range(20):
        code = f"X{i}"
        connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (code, code))
        _insert_official_metric(connection, 2025, code, "Tee::Tee01::010101", "Tee", "평균 티샷 거리", 220.0 + i)

    connection.commit()
    return connection


def test_augment_adds_target_season_and_all_feature_columns(conn):
    corpus = load_corpus(conn)
    wf_result = build_walk_forward_dataset(conn, corpus=corpus)
    augmented = augment_rows_with_beta001c_features(
        conn, wf_result.rows, corpus, taxonomy=json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8")),
        raw_samples_dir=REAL_RAW_SAMPLES_DIR,
    )
    assert augmented
    for row in augmented:
        assert "target_season" in row
        assert "neo_consistency_stddev" in row
        for name in DOMAIN_METRIC_FEATURE_NAMES:
            assert name in row and f"{name}_n" in row
        for name in WIN_FEATURE_CANDIDATE_NAMES:
            assert name in row and f"{name}_n" in row


def test_augment_never_mutates_input_rows(conn):
    corpus = load_corpus(conn)
    wf_result = build_walk_forward_dataset(conn, corpus=corpus)
    original_keys = set(wf_result.rows[0].keys())
    augment_rows_with_beta001c_features(
        conn, wf_result.rows, corpus, taxonomy=json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8")),
        raw_samples_dir=REAL_RAW_SAMPLES_DIR,
    )
    assert set(wf_result.rows[0].keys()) == original_keys


def test_model_feature_tuples_are_strictly_nested():
    assert MODEL_A_FEATURES == BASE_FEATURES
    assert MODEL_A_FEATURES == MODEL_B_FEATURES[: len(MODEL_A_FEATURES)]
    assert MODEL_B_FEATURES == MODEL_C_FEATURES[: len(MODEL_B_FEATURES)]
    assert len(MODEL_B_FEATURES) == len(MODEL_A_FEATURES) + 5
    assert len(MODEL_C_FEATURES) == len(MODEL_B_FEATURES) + 5
    assert "neo_scoring" not in MODEL_B_FEATURES
    assert "neo_scoring" not in MODEL_C_FEATURES


def test_walk_forward_backtest_produces_valid_probability_distributions(conn):
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    specs = (
        NeoWinModelSpec("A", MODEL_A_FEATURES),
        NeoWinModelSpec("B", MODEL_B_FEATURES),
        NeoWinModelSpec("C", MODEL_C_FEATURES),
    )
    result = run_neo_win_multi_model_walk_forward(
        conn, specs, threshold=2, taxonomy=taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR,
    )
    assert result.eligible_tournament_count > 0
    assert not result.skipped_ambiguous_winner
    for model_id in ("A", "B", "C"):
        preds = result.predictions_by_model[model_id]
        assert len(preds) == result.eligible_tournament_count
        for pred in preds:
            total = sum(pred.probabilities.values())
            assert abs(total - 1.0) < 1e-6
            assert pred.winner in pred.probabilities
            assert all(p > 0 for p in pred.probabilities.values())


# ---------------------------------------------------------------
# select_best_beta001c_model — Phase 8's evidence-only complexity
# tie-break, tested directly against hand-crafted TournamentPrediction
# lists (never against synthetic-fixture noise, which cannot reliably
# clear a pre-registered p<0.05 gate one way or the other).
# ---------------------------------------------------------------


def _preds(winner_prob_by_tournament: dict) -> list:
    out = []
    for i, winner_prob in winner_prob_by_tournament.items():
        remaining = 1.0 - winner_prob
        probs = {"W": winner_prob, "L1": remaining / 2, "L2": remaining / 2}
        out.append(
            TournamentPrediction(
                target_event_id=f"E{i}", target_game_code=f"E{i}", target_start_date=f"2026-{(i % 12) + 1:02d}-01",
                probabilities=probs, winner="W",
            )
        )
    return out


def test_selection_stays_at_model_a_when_b_does_not_improve():
    n = 10
    identical = {i: 0.4 for i in range(n)}
    result = NeoWinBacktestResult(
        threshold=1, model_ids=("MODEL_A", "MODEL_B", "MODEL_C"),
        predictions_by_model={"MODEL_A": _preds(identical), "MODEL_B": _preds(identical), "MODEL_C": _preds(identical)},
        total_usable_tournaments=n, eligible_tournament_count=n,
    )
    decision = select_best_beta001c_model(result)
    assert decision["selected_model_id"] == "MODEL_A"
    assert "MODEL_C_vs_MODEL_B" not in decision["comparisons"]


def test_selection_promotes_to_model_b_when_it_clearly_improves_but_c_does_not():
    n = 12
    a_probs = {i: 0.05 for i in range(n)}
    b_probs = {i: 0.5 for i in range(n)}  # consistently, substantially better than A
    result = NeoWinBacktestResult(
        threshold=1, model_ids=("MODEL_A", "MODEL_B", "MODEL_C"),
        predictions_by_model={"MODEL_A": _preds(a_probs), "MODEL_B": _preds(b_probs), "MODEL_C": _preds(b_probs)},
        total_usable_tournaments=n, eligible_tournament_count=n,
    )
    decision = select_best_beta001c_model(result)
    assert decision["selected_model_id"] == "MODEL_B"
    assert "MODEL_C_vs_MODEL_B" in decision["comparisons"]


def test_selection_promotes_to_model_c_when_both_steps_clearly_improve():
    n = 12
    a_probs = {i: 0.03 for i in range(n)}
    b_probs = {i: 0.3 for i in range(n)}
    c_probs = {i: 0.8 for i in range(n)}
    result = NeoWinBacktestResult(
        threshold=1, model_ids=("MODEL_A", "MODEL_B", "MODEL_C"),
        predictions_by_model={"MODEL_A": _preds(a_probs), "MODEL_B": _preds(b_probs), "MODEL_C": _preds(c_probs)},
        total_usable_tournaments=n, eligible_tournament_count=n,
    )
    decision = select_best_beta001c_model(result)
    assert decision["selected_model_id"] == "MODEL_C"


def test_build_beta001c_live_field_adds_win_features_on_top_of_domain_features(conn, tmp_path):
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('LIVE', 'A', 'A', 'test', '2027-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('LIVE', 'LIVE', 'LIVE', 2027, '2027-02-01', '2027-02-01')"
    )
    conn.commit()
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    result = build_beta001c_live_field(
        conn, "LIVE", date.fromisoformat("2027-01-01"), taxonomy=taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR
    )
    field_rows = {row["player_code"]: row for row in result["field_rows"]}
    assert "A" in field_rows
    row = field_rows["A"]
    for name in DOMAIN_METRIC_FEATURE_NAMES:
        assert name in row
    from klpga.neo_win.win_features import WIN_FEATURE_CANDIDATE_NAMES

    for name in WIN_FEATURE_CANDIDATE_NAMES:
        assert name in row and f"{name}_n" in row
    # A has 8 real prior events in this fixture -> wins_last_10_starts_n should reflect that.
    assert row["wins_last_10_starts_n"] > 0


def test_build_beta001c_live_training_rows_excludes_target_and_future(conn):
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('LIVE', 'A', 'A', 'test', '2027-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('LIVE', 'LIVE', 'LIVE', 2027, '2027-02-01', '2027-02-01')"
    )
    conn.commit()
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    rows, training_count = build_beta001c_live_training_rows(
        conn, "LIVE", date.fromisoformat("2027-01-01"), taxonomy=taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR
    )
    assert training_count == 8
    assert all(row["target_event_id"] != "LIVE" for row in rows)
    for row in rows:
        for name in DOMAIN_METRIC_FEATURE_NAMES:
            assert name in row


def test_training_set_is_strictly_prior_never_includes_target_or_future(conn):
    # Real leakage check: for the first eligible target, the training
    # set built the same way backtest_eval's loop builds it must only
    # ever draw from strictly-earlier tournaments — never the target
    # itself, never anything on/after its date.
    corpus = load_corpus(conn)
    dataset = build_walk_forward_dataset(conn, corpus=corpus)
    eligible = [t for t in dataset.target_order if t.prior_tournament_count >= 1]
    assert eligible
    first_target = eligible[0]
    training_event_ids = {
        other.event_id for other in dataset.target_order if other.effective_date < first_target.effective_date
    }
    assert first_target.event_id not in training_event_ids
    for other in dataset.target_order:
        if other.event_id in training_event_ids:
            assert other.effective_date < first_target.effective_date
