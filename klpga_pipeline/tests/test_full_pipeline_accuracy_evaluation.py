"""End-to-end regression test — roadmap #3's "wire accuracy evaluation
to R3/FINAL" work. klpga.neo_win.accuracy_evaluation was already built
generically (PREDICTION_STAGES = STAGE_ORDER minus FINAL, using only
each stage's win_pct field) and tests/test_accuracy_evaluation.py +
tests/test_evaluate_prediction_accuracy_script.py already lock that in
against hand-built HistoryStageSnapshot objects. What was NOT yet
verified is that the REAL stage-producing scripts (33/44/46/47) — each
built independently, each with its own HistoryEntrant field shape
(R2 has make_cut_pct but no top5/top20 surfaced; R3 has top5/top10/
top20 but no make_cut_pct at all) — actually chain together and
evaluate cleanly end-to-end through scripts/43. This file runs the
REAL scripts against a synthetic DB (never a real DB, never the
production archive) and asserts scripts/43 reports R2 and R3 as
EVALUATED with a real, non-fabricated sample."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_33 = ROOT / "scripts" / "33_predict_neo_win.py"
SCRIPT_42 = ROOT / "scripts" / "42_record_tournament_history.py"
SCRIPT_44 = ROOT / "scripts" / "44_predict_neo_win_post_r2.py"
SCRIPT_46 = ROOT / "scripts" / "46_predict_neo_win_post_r3.py"
SCRIPT_47 = ROOT / "scripts" / "47_record_final_result.py"
SCRIPT_43 = ROOT / "scripts" / "43_evaluate_prediction_accuracy.py"
SCHEMA_PATH = ROOT / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "E2ETEST"
CUTOFF_DATE = "2027-01-01"
PLAYERS = ["A", "B", "C", "D", "E"]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(module, argv):
    argv_backup = sys.argv
    sys.argv = argv
    try:
        return module.main()
    finally:
        sys.argv = argv_backup


def _base_db(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    for t in range(8):
        event_id = f"T{t:02d}"
        ranked = PLAYERS[t % 5:] + PLAYERS[: t % 5]
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, f"2026-0{(t % 9) + 1:01d}-01", f"2026-0{(t % 9) + 1:01d}-01"),
        )
        for rank, player_id in enumerate(ranked, start=1):
            conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
            conn.execute(
                "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
                "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
                "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
                (event_id, event_id, player_id, player_id, str(rank), rank, -10 + rank),
            )
            for rn in range(1, 5):
                conn.execute(
                    "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                    "round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
                    (event_id, event_id, rn, player_id, player_id, 70 - rank, -rank),
                )
    for player_id in PLAYERS:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (GAME_CODE, player_id, player_id),
        )
    # A wins outright; B-E are real, confirmed CUT players (made_cut=0, rounds_played=2).
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date, winner, field_size) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04', 'A', 5)",
        (GAME_CODE, GAME_CODE),
    )
    for i, player_id in enumerate(PLAYERS):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 1, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 71 - i, -i - 1),
        )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, 'A', 'A', '1', 1, 1, 3, -8)",
        (GAME_CODE, GAME_CODE),
    )
    for player_id in PLAYERS[1:]:
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, 'CUT', NULL, 0, 2, -2)",
            (GAME_CODE, GAME_CODE, player_id, player_id),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def workspace(tmp_path):
    db_path = _base_db(tmp_path)
    return {
        "db": db_path,
        "predictions_dir": tmp_path / "neo_win_predictions",
        "history_dir": tmp_path / "neo_tournament_history",
        "tmp_path": tmp_path,
    }


def test_full_pre_r2_r3_final_chain_evaluates_cleanly(workspace, capsys):
    predict_module = _load(SCRIPT_33, "e2e_predict_pre")
    assert _run(predict_module, [
        "33_predict_neo_win.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--cutoff-date", CUTOFF_DATE, "--freeze", "--prediction-id", "001",
        "--predictions-dir", str(workspace["predictions_dir"]),
        "--output-dir", str(workspace["tmp_path"] / "pre_outputs"),
    ]) == 0

    record_module = _load(SCRIPT_42, "e2e_record_pre_history")
    assert _run(record_module, [
        "42_record_tournament_history.py", "--game-code", GAME_CODE,
        "--predictions-dir", str(workspace["predictions_dir"]),
        "--c-predictions-dir", str(workspace["tmp_path"] / "neo_win_c_predictions"),
        "--history-dir", str(workspace["history_dir"]),
    ]) == 0

    r2_module = _load(SCRIPT_44, "e2e_predict_r2")
    assert _run(r2_module, [
        "44_predict_neo_win_post_r2.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--predictions-dir", str(workspace["predictions_dir"]), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(workspace["tmp_path"] / "r2_outputs"), "--history-dir", str(workspace["history_dir"]),
        "--n-simulations", "300", "--seed", "5", "--freeze",
    ]) == 0

    # Add A's real R3 row only AFTER R2 was frozen (scripts/44 has its own round_number=3 leakage guard).
    conn = sqlite3.connect(workspace["db"])
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 3, 'A', 'A', 66, -6)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    r3_module = _load(SCRIPT_46, "e2e_predict_r3")
    assert _run(r3_module, [
        "46_predict_neo_win_post_r3.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--predictions-dir", str(workspace["predictions_dir"]), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(workspace["tmp_path"] / "r3_outputs"), "--history-dir", str(workspace["history_dir"]),
        "--n-simulations", "300", "--seed", "7", "--freeze",
    ]) == 0

    final_module = _load(SCRIPT_47, "e2e_record_final")
    assert _run(final_module, [
        "47_record_final_result.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--history-dir", str(workspace["history_dir"]), "--freeze",
    ]) == 0

    from klpga.neo_win.tournament_history import (
        STAGE_FINAL,
        STAGE_PRE,
        STAGE_R2,
        STAGE_R3,
        STATUS_RECORDED,
        read_effective_history_stage,
    )

    for stage in (STAGE_PRE, STAGE_R2, STAGE_R3, STAGE_FINAL):
        effective = read_effective_history_stage(workspace["history_dir"], GAME_CODE, stage)
        assert effective is not None, f"{stage} was not recorded"
        assert effective.status == STATUS_RECORDED, f"{stage} status={effective.status}"

    accuracy_module = _load(SCRIPT_43, "e2e_evaluate_accuracy")
    rc = _run(accuracy_module, ["43_evaluate_prediction_accuracy.py", "--history-dir", str(workspace["history_dir"])])
    assert rc == 0
    out = capsys.readouterr().out

    assert "EVALUABLE TOURNAMENTS (FINAL recorded): 1" in out
    # PRE, R2, and R3 all have a real winner (A) with a real win_pct and join cleanly against FINAL.
    for stage in ("PRE", "R2", "R3"):
        section = out.split(f"--- {stage} ---")[1].split("--- ")[0]
        assert "STATUS: EVALUATED" in section, f"{stage} did not evaluate: {section}"
        assert "SAMPLE SIZE: 1" in section, f"{stage} sample size wrong: {section}"
    assert "LEAKAGE CHECK: 0" in out


def test_confirmed_winner_r2_r3_never_shows_a_leakage_flag(workspace, capsys):
    """The R2/R3 scripts stamp source_generated_at_utc at freeze time,
    strictly before scripts/47's FINAL freeze — the leakage guard in
    accuracy_evaluation.build_tournament_prediction must never fire on
    this real, correctly-ordered chain."""
    predict_module = _load(SCRIPT_33, "e2e_leak_predict_pre")
    _run(predict_module, [
        "33_predict_neo_win.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--cutoff-date", CUTOFF_DATE, "--freeze", "--prediction-id", "001",
        "--predictions-dir", str(workspace["predictions_dir"]),
        "--output-dir", str(workspace["tmp_path"] / "pre_outputs"),
    ])
    record_module = _load(SCRIPT_42, "e2e_leak_record_pre_history")
    _run(record_module, [
        "42_record_tournament_history.py", "--game-code", GAME_CODE,
        "--predictions-dir", str(workspace["predictions_dir"]),
        "--c-predictions-dir", str(workspace["tmp_path"] / "neo_win_c_predictions"),
        "--history-dir", str(workspace["history_dir"]),
    ])
    r2_module = _load(SCRIPT_44, "e2e_leak_predict_r2")
    _run(r2_module, [
        "44_predict_neo_win_post_r2.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--predictions-dir", str(workspace["predictions_dir"]), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(workspace["tmp_path"] / "r2_outputs"), "--history-dir", str(workspace["history_dir"]),
        "--n-simulations", "300", "--seed", "5", "--freeze",
    ])
    conn = sqlite3.connect(workspace["db"])
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 3, 'A', 'A', 66, -6)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()
    r3_module = _load(SCRIPT_46, "e2e_leak_predict_r3")
    _run(r3_module, [
        "46_predict_neo_win_post_r3.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--predictions-dir", str(workspace["predictions_dir"]), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(workspace["tmp_path"] / "r3_outputs"), "--history-dir", str(workspace["history_dir"]),
        "--n-simulations", "300", "--seed", "7", "--freeze",
    ])
    final_module = _load(SCRIPT_47, "e2e_leak_record_final")
    _run(final_module, [
        "47_record_final_result.py", "--db", str(workspace["db"]), "--game-code", GAME_CODE,
        "--history-dir", str(workspace["history_dir"]), "--freeze",
    ])

    accuracy_module = _load(SCRIPT_43, "e2e_leak_evaluate_accuracy")
    rc = _run(accuracy_module, ["43_evaluate_prediction_accuracy.py", "--history-dir", str(workspace["history_dir"])])
    assert rc == 0
    out = capsys.readouterr().out
    assert "LEAKAGE CHECK: 0 flagged []" in out
