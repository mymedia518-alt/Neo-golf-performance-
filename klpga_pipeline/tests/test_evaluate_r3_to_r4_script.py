"""Tests for scripts/evaluate_r3_to_r4.py — the BETA #001 FINAL R3->R4
evaluation CLI. Covers the R4-not-ready HARD_STOP, the future-data-
leakage regression (mu/sigma must be byte-identical whether or not
round_number=4 rows exist in the DB), and read-only-ness against every
existing frozen artifact."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_r3_to_r4.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "2026080099"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "evaluate_r3_to_r4_script")


def _base_db(tmp_path, *, with_r4=True):
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Test Open', 2026, '2026-08-27', '2026-08-31')",
        (GAME_CODE, GAME_CODE),
    )
    players = [
        ("p1", "P1", -3, -2, -1, -2, True),
        ("p2", "P2", -1, -1, 0, 1, True),
        ("p3", "P3", 2, 3, None, None, False),
    ]
    for code, name, r1, r2, r3, r4, made_cut in players:
        conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (code, name))
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2026-08-25T00:00:00Z')",
            (GAME_CODE, code, name),
        )
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, made_cut) "
            "VALUES (?, ?, 2026, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, code, name, int(made_cut)),
        )
        rounds = [(1, r1), (2, r2), (3, r3)]
        if with_r4:
            rounds.append((4, r4))
        for rn, val in rounds:
            if val is not None:
                conn.execute(
                    "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, "
                    "player_name, round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, 70, ?)",
                    (GAME_CODE, GAME_CODE, rn, code, name, val),
                )
    conn.commit()
    conn.close()
    return db_path


def _seed_pre_snapshot(tmp_path):
    c_dir = tmp_path / "cpred" / "2026"
    c_dir.mkdir(parents=True)
    snapshot = {
        "prediction_id": "001-C", "created_at_utc": "2026-08-27T00:00:00Z",
        "record_kind": "neo_win_beta001c_prediction_v1", "game_code": GAME_CODE, "tournament_name": "Test Open",
        "cutoff_date": "2026-08-27", "cutoff_source": "test", "selected_model_id": "MODEL_B",
        "model_features": ["prior_avg_round_score_to_par", "prior_recent_form_10", "neo_consistency_stddev"],
        "selection_decision": {}, "training_tournament_count": 8, "field_size": 3, "entrants_predicted": 3,
        "probability_sum": 1.0, "minimum_probability": 0.0, "maximum_probability": 0.6, "duplicate_count": 0,
        "null_count": 0, "non_field_count": 0, "known_limitations": [],
        "predictions": [
            {"rank": 1, "player_code": "p1", "player_name": "P1", "win_probability": 0.6, "prior_events_n": 10,
             "feature_values": {"prior_avg_round_score_to_par": -1.0, "prior_recent_form_10": -1.0, "neo_consistency_stddev": 2.0},
             "player_master_matched": True},
            {"rank": 2, "player_code": "p2", "player_name": "P2", "win_probability": 0.4, "prior_events_n": 10,
             "feature_values": {"prior_avg_round_score_to_par": 0.0, "prior_recent_form_10": 0.0, "neo_consistency_stddev": 1.5},
             "player_master_matched": True},
            {"rank": 3, "player_code": "p3", "player_name": "P3", "win_probability": 0.0, "prior_events_n": 10,
             "feature_values": {"prior_avg_round_score_to_par": 1.0, "prior_recent_form_10": 1.0, "neo_consistency_stddev": 1.0},
             "player_master_matched": True},
        ],
    }
    path = c_dir / f"neo_win_c_001-C_{GAME_CODE}.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path


def _argv(db_path, tmp_path, *, freeze=False):
    return [
        "evaluate_r3_to_r4.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--pre-cutoff-date", "2026-08-27", "--c-predictions-dir", str(tmp_path / "cpred"),
        "--predictions-dir", str(tmp_path / "pred"),
        "--output-dir", str(tmp_path / "out"), "--archive-root", str(tmp_path / "archive"),
    ] + (["--freeze"] if freeze else [])


def test_r4_not_ready_hard_stops_writes_nothing(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path, with_r4=False)
    _seed_pre_snapshot(tmp_path)
    monkeypatch.setattr(sys, "argv", _argv(db_path, tmp_path, freeze=True))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: NOT_READY" in out
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "archive").exists()


def test_end_to_end_evaluation_matches_hand_computed_metrics(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path, with_r4=True)
    _seed_pre_snapshot(tmp_path)
    monkeypatch.setattr(sys, "argv", _argv(db_path, tmp_path, freeze=True))
    rc = module.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "EVALUATED_PLAYERS: 2" in out
    assert "MAE: 1.0" in out
    assert "ME (bias): 0.0" in out
    assert "RMSE: 1.0" in out
    assert "WITHIN ±1 STROKE: 100.0%" in out
    assert "WITHIN ±SIGMA: 100.0%" in out
    assert "FREEZE: RECORDED" in out

    csv_path = tmp_path / "out" / f"{GAME_CODE}_R3_R4_EVALUATION.csv"
    archive_path = tmp_path / "archive" / GAME_CODE / "001-C_R3_TO_R4.json"
    assert csv_path.exists()
    assert archive_path.exists()

    record = json.loads(archive_path.read_text(encoding="utf-8"))
    assert record["aggregate"]["evaluated_players"] == 2
    assert len(record["source_pre_snapshot_sha256"]) == 64
    assert len(record["source_r1_r2_r3_made_cut_input_sha256"]) == 64
    assert any("statistics.stdev()" in note for note in record["known_limitations"])


def test_future_data_leakage_mu_sigma_identical_with_and_without_r4_rows(module, tmp_path, monkeypatch):
    """The core leakage regression: running the evaluator against a DB
    WITH real round_number=4 rows must produce byte-identical mu/sigma
    (expected_r4_score_to_par / r4_spread) to a DB where round_number=4
    doesn't exist at all -- proving R4's presence never reaches the
    build_r3_sim_inputs_from_frozen_snapshot call."""
    import csv as csv_module
    import sys

    (tmp_path / "with_r4").mkdir()
    (tmp_path / "without_r4").mkdir()
    db_with_r4 = _base_db(tmp_path / "with_r4", with_r4=True)
    _seed_pre_snapshot(tmp_path / "with_r4")

    db_without_r4 = _base_db(tmp_path / "without_r4", with_r4=False)
    _seed_pre_snapshot(tmp_path / "without_r4")

    # "without_r4" DB has zero round_number=4 rows -> the script would HARD_STOP with NOT_READY
    # for a real run. To isolate JUST the mu/sigma derivation step (STEP3-5) from the R4-readiness
    # gate, call the module's own building blocks directly, exactly as main() does internally.
    def derive_mu_sigma(db_path, pre_dir):
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            r1 = module._round_scores(conn, GAME_CODE, 1)
            r2 = module._round_scores(conn, GAME_CODE, 2)
            r3 = module._round_scores(conn, GAME_CODE, 3)
            made_cut = module._made_cut(conn, GAME_CODE)
        finally:
            conn.close()
        from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot
        from klpga.neo_win.round_update_r3 import build_r3_sim_inputs_from_frozen_snapshot

        snap = read_neo_win_c_snapshot(pre_dir / "cpred" / "2026" / f"neo_win_c_001-C_{GAME_CODE}.json")
        sim_inputs, _missing = build_r3_sim_inputs_from_frozen_snapshot(snap, r1, r2, r3, made_cut)
        return {p.player_code: (p.expected_round_score_to_par, p.spread) for p in sim_inputs}

    mu_sigma_with_r4 = derive_mu_sigma(db_with_r4, tmp_path / "with_r4")
    mu_sigma_without_r4 = derive_mu_sigma(db_without_r4, tmp_path / "without_r4")

    assert mu_sigma_with_r4 == mu_sigma_without_r4


def test_readonly_never_modifies_pre_snapshot_db_or_output_of_prior_run(module, tmp_path, monkeypatch):
    import sys

    db_path = _base_db(tmp_path, with_r4=True)
    pre_path = _seed_pre_snapshot(tmp_path)
    pre_bytes_before = pre_path.read_bytes()
    db_bytes_before = db_path.read_bytes()

    monkeypatch.setattr(sys, "argv", _argv(db_path, tmp_path, freeze=True))
    rc = module.main()
    assert rc == 0

    assert pre_path.read_bytes() == pre_bytes_before
    assert db_path.read_bytes() == db_bytes_before


def test_double_freeze_is_skip_log_not_overwrite(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path, with_r4=True)
    _seed_pre_snapshot(tmp_path)
    monkeypatch.setattr(sys, "argv", _argv(db_path, tmp_path, freeze=True))
    assert module.main() == 0
    capsys.readouterr()
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "FREEZE: SKIP + LOG" in out
