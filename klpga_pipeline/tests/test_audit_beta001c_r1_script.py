"""Tests for scripts/45_audit_beta001c_r1.py — offline, against
hand-written frozen PRE (#001-C) + R1 (round-update) snapshots, a CSV
export, a tournament_history R1 record, and a synthetic DB. The script
itself is read-only; these tests only verify it reports correctly."""
from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "45_audit_beta001c_r1.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "R1AUDIT"
CUTOFF_DATE = "2027-01-01"
PLAYERS = ["A", "B", "C", "D", "E"]  # E is deliberately missing its R1 score below


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "audit_beta001c_r1_script")


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04')",
        (GAME_CODE, GAME_CODE),
    )
    for p in PLAYERS:
        conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (p, p))
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (GAME_CODE, p, p),
        )
    for i, p in enumerate(PLAYERS[:4]):  # E has no round_number=1 row
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 1, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, p, p, 70 - i, -i),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def db_path_full(tmp_path):
    """All 5 PLAYERS have a real round_number=1 row — no missing player."""
    path = tmp_path / "test_full.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04')",
        (GAME_CODE, GAME_CODE),
    )
    for p in PLAYERS:
        conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (p, p))
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (GAME_CODE, p, p),
        )
    for i, p in enumerate(PLAYERS):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 1, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, p, p, 70 - i, -i),
        )
    conn.commit()
    conn.close()
    return path


def _freeze_pre_c(c_predictions_dir, prediction_id="001-C-FINAL"):
    from klpga.neo_win.beta001c_archive import (
        NeoWinCEntrantSnapshot,
        NeoWinCPredictionSnapshot,
        RECORD_KIND as C_RECORD_KIND,
        write_neo_win_c_snapshot_atomic,
    )

    n = len(PLAYERS)
    entrants = tuple(
        NeoWinCEntrantSnapshot(
            rank=i + 1, player_code=p, player_name=p, win_probability=1.0 / n, prior_events_n=10,
            feature_values={"prior_avg_round_score_to_par": -1.0 - i * 0.2, "neo_consistency_stddev": 2.0},
        )
        for i, p in enumerate(PLAYERS)
    )
    snapshot = NeoWinCPredictionSnapshot(
        prediction_id=prediction_id, created_at_utc="2027-01-01T00:00:00Z", record_kind=C_RECORD_KIND,
        game_code=GAME_CODE, tournament_name="Live Test Open", cutoff_date=CUTOFF_DATE,
        cutoff_source="explicit_arg", selected_model_id="MODEL_A",
        model_features=("prior_avg_round_score_to_par", "neo_consistency_stddev"),
        selection_decision={"selected_model_id": "MODEL_A"}, training_tournament_count=8,
        field_size=n, entrants_predicted=n, probability_sum=1.0,
        minimum_probability=1.0 / n, maximum_probability=1.0 / n,
        duplicate_count=0, null_count=0, non_field_count=0, known_limitations=(),
        predictions=entrants,
    )
    write_neo_win_c_snapshot_atomic(snapshot, c_predictions_dir)
    return snapshot


def _freeze_r1(predictions_dir, *, pre_prediction_id="001-C-FINAL", r1_prediction_id="001-C-R1",
               win_pcts=None, extra_duplicate=False, missing_players=("E",)):
    from klpga.neo_win.round_update_archive import (
        RECORD_KIND as RU_RECORD_KIND,
        RoundUpdateEntrantSnapshot,
        RoundUpdateSnapshot,
        write_round_update_snapshot_atomic,
    )

    scored = [p for p in PLAYERS if p not in missing_players]
    if win_pcts is None:
        win_pcts = {p: 100.0 / len(scored) for p in scored}  # sums to exactly 100%

    entrants = [
        RoundUpdateEntrantSnapshot(
            player_code=p, player_name=p, pre_win_probability=1.0 / len(PLAYERS),
            r1_score_to_par=-i, r1_position=i + 1, strokes_behind_leader=float(i),
            post_r1_win_pct=win_pcts[p], post_r1_top5_pct=win_pcts[p], post_r1_top10_pct=win_pcts[p],
            post_r1_top20_pct=win_pcts[p], post_r1_make_cut_pct=100.0,
            probability_change_from_pre=win_pcts[p] - (100.0 / len(PLAYERS)), missing_r1_data=False,
        )
        for i, p in enumerate(scored)
    ]
    for p in missing_players:
        entrants.append(
            RoundUpdateEntrantSnapshot(
                player_code=p, player_name=p, pre_win_probability=1.0 / len(PLAYERS),
                r1_score_to_par=None, r1_position=None, strokes_behind_leader=None,
                post_r1_win_pct=None, post_r1_top5_pct=None, post_r1_top10_pct=None, post_r1_top20_pct=None,
                post_r1_make_cut_pct=None, probability_change_from_pre=None, missing_r1_data=True,
            )
        )
    if extra_duplicate:
        entrants.append(entrants[0])

    snapshot = RoundUpdateSnapshot(
        prediction_id=r1_prediction_id, created_at_utc="2027-01-02T00:00:00Z", record_kind=RU_RECORD_KIND,
        game_code=GAME_CODE, tournament_name="Live Test Open", pre_prediction_id=pre_prediction_id,
        pre_cutoff_date=CUTOFF_DATE, round_number=1, cut_fraction_used=0.7,
        cut_format="single_36_hole_cut_no_subsequent_cut", n_simulations=1000, field_size=len(PLAYERS),
        entrants_scored=len(scored), missing_r1_players=tuple(missing_players),
        win_probability_sum_pct=sum(win_pcts.values()),
        leakage_check={"status": "PASS"}, known_limitations=(), predictions=tuple(entrants),
    )
    write_round_update_snapshot_atomic(snapshot, predictions_dir)
    return snapshot, entrants


def _write_csv(output_dir, entrants, *, omit_code=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank", "player_code", "player_name", "pre_win_probability_pct", "r1_score_to_par", "r1_position",
        "strokes_behind_leader", "post_r1_win_pct", "post_r1_top5_pct", "post_r1_top10_pct", "post_r1_top20_pct",
        "post_r1_make_cut_pct", "neo_r3_pct", "neo_final_pct", "probability_change_from_pre", "missing_r1_data",
    ]
    with open(output_dir / "BETA001_R1_FULL.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rank, e in enumerate(entrants, start=1):
            if omit_code and e.player_code == omit_code:
                continue
            writer.writerow({
                "rank": rank, "player_code": e.player_code, "player_name": e.player_name,
                "pre_win_probability_pct": "" if e.pre_win_probability is None else round(e.pre_win_probability * 100, 4),
                "r1_score_to_par": "" if e.r1_score_to_par is None else e.r1_score_to_par,
                "r1_position": "" if e.r1_position is None else e.r1_position,
                "strokes_behind_leader": "" if e.strokes_behind_leader is None else e.strokes_behind_leader,
                "post_r1_win_pct": "" if e.post_r1_win_pct is None else e.post_r1_win_pct,
                "post_r1_top5_pct": "" if e.post_r1_top5_pct is None else e.post_r1_top5_pct,
                "post_r1_top10_pct": "" if e.post_r1_top10_pct is None else e.post_r1_top10_pct,
                "post_r1_top20_pct": "" if e.post_r1_top20_pct is None else e.post_r1_top20_pct,
                "post_r1_make_cut_pct": "" if e.post_r1_make_cut_pct is None else e.post_r1_make_cut_pct,
                "neo_r3_pct": "" if e.post_r1_make_cut_pct is None else e.post_r1_make_cut_pct,
                "neo_final_pct": "" if e.post_r1_make_cut_pct is None else e.post_r1_make_cut_pct,
                "probability_change_from_pre": "" if e.probability_change_from_pre is None else round(e.probability_change_from_pre, 4),
                "missing_r1_data": e.missing_r1_data,
            })


def _base_argv(db_path, c_predictions_dir, predictions_dir, full_csv, history_dir):
    return [
        "45_audit_beta001c_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--pre-cutoff-date", CUTOFF_DATE,
        "--c-predictions-dir", str(c_predictions_dir), "--pre-prediction-id", "001-C-FINAL",
        "--predictions-dir", str(predictions_dir), "--r1-prediction-id", "001-C-R1",
        "--full-csv", str(full_csv), "--history-dir", str(history_dir),
    ]


def _run(module, argv):
    argv_backup = sys.argv
    sys.argv = argv
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    return rc


def test_audit_warns_only_on_missing_player_when_everything_else_clean(module, db_path, tmp_path, capsys):
    from klpga.neo_win.tournament_history import HistoryEntrant, HistoryStageSnapshot, RECORD_KIND as HIST_RECORD_KIND
    from klpga.neo_win.tournament_history import write_history_stage_atomic, STAGE_R1

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)
    _write_csv(output_dir, entrants)

    history_entrants = tuple(
        HistoryEntrant(player_code=e.player_code, player_name=e.player_name, win_pct=e.post_r1_win_pct)
        for e in entrants
    )
    write_history_stage_atomic(
        HistoryStageSnapshot(
            game_code=GAME_CODE, stage=STAGE_R1, record_kind=HIST_RECORD_KIND, recorded_at_utc="2027-01-02T00:00:00Z",
            source_prediction_id="001-C-R1", source_model_version="001-C-FINAL",
            source_generated_at_utc="2027-01-02T00:00:00Z", tournament_name="Live Test Open",
            field_size=len(entrants), entrants=history_entrants,
        ),
        history_dir,
    )

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "PRE source confirmed BETA #001-C: True" in out
    assert "VERDICT: WARN" in out
    assert "[WARN] 1 player(s) missing R1 data" in out
    assert "DURABLY RECORDED" in out
    assert "Missing/skipped players (1):" in out
    assert "E (E): no Round-1 score found" in out


def test_audit_passes_when_field_is_complete_and_history_recorded(module, db_path_full, tmp_path, capsys):
    from klpga.neo_win.tournament_history import HistoryEntrant, HistoryStageSnapshot, RECORD_KIND as HIST_RECORD_KIND
    from klpga.neo_win.tournament_history import write_history_stage_atomic, STAGE_R1

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir, missing_players=())
    _write_csv(output_dir, entrants)

    history_entrants = tuple(
        HistoryEntrant(player_code=e.player_code, player_name=e.player_name, win_pct=e.post_r1_win_pct)
        for e in entrants
    )
    write_history_stage_atomic(
        HistoryStageSnapshot(
            game_code=GAME_CODE, stage=STAGE_R1, record_kind=HIST_RECORD_KIND, recorded_at_utc="2027-01-02T00:00:00Z",
            source_prediction_id="001-C-R1", source_model_version="001-C-FINAL",
            source_generated_at_utc="2027-01-02T00:00:00Z", tournament_name="Live Test Open",
            field_size=len(entrants), entrants=history_entrants,
        ),
        history_dir,
    )

    rc = _run(module, _base_argv(db_path_full, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: PASS" in out
    assert "Missing/skipped players (0):" in out
    assert "(none)" in out


def test_audit_warns_when_r1_history_slot_holds_missing_marker(module, db_path, tmp_path, capsys):
    from klpga.neo_win.tournament_history import build_missing_stage_marker, write_history_stage_atomic

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)
    _write_csv(output_dir, entrants)
    write_history_stage_atomic(
        build_missing_stage_marker(GAME_CODE, "R1", reason="stale legacy marker", recorded_at_utc="2027-01-01T00:00:00Z"),
        history_dir,
    )

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: WARN" in out
    assert "[WARN] PRE->R1 movement is NOT durably recorded" in out
    assert "NOT DURABLY RECORDED — a stale MISSING marker" in out


def test_audit_fails_when_db_has_r1_row_for_player_not_in_frozen_snapshot_at_all(module, db_path, tmp_path, capsys):
    """A round_number=1 DB row for a player_code absent from the frozen
    R1 snapshot entirely (neither scored nor missing_r1_data) is a
    SEPARATE anomaly from the ordinary 'a missing player now scored'
    provenance case — must FAIL, not be silently folded into a WARN."""
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('ZZZ', 'Ghost')")
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 1, 'ZZZ', 'Ghost', 68, -4)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)
    _write_csv(output_dir, entrants)

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: FAIL" in out
    assert "[FAIL] DB has real round_number=1 row(s) for player_code(s) not present" in out
    assert "'ZZZ'" in out


def test_audit_fails_on_r2_leakage(module, db_path, tmp_path, capsys):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 2, 'A', 'A', 68, -2)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)
    _write_csv(output_dir, entrants)

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: FAIL" in out
    assert "[FAIL] LEAKAGE: 1 round_number=2 row" in out


def test_audit_fails_on_duplicate_player_and_win_sum_drift(module, db_path, tmp_path, capsys):
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(
        predictions_dir, win_pcts={"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0}, extra_duplicate=True
    )
    _write_csv(output_dir, entrants)

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: FAIL" in out
    assert "[FAIL] DUPLICATES: 1" in out
    assert "[FAIL] WIN SUM off target" in out


def test_audit_fails_when_csv_and_json_player_sets_disagree(module, db_path, tmp_path, capsys):
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)
    _write_csv(output_dir, entrants, omit_code="B")  # CSV silently missing a player vs. the JSON

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: FAIL" in out
    assert "[FAIL] JSON/CSV PLAYER SET MISMATCH" in out


def test_audit_fails_when_pre_prediction_id_is_legacy_001(module, db_path, tmp_path, capsys):
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir, prediction_id="001")
    _snapshot, entrants = _freeze_r1(predictions_dir, pre_prediction_id="001")
    _write_csv(output_dir, entrants)

    argv = _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir)
    argv[argv.index("001-C-FINAL")] = "001"
    rc = _run(module, argv)
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: FAIL" in out
    assert "[FAIL] PRE SOURCE NOT CONFIRMED" in out


def test_audit_reports_recorded_via_superseding_event_not_stale_marker(module, db_path_full, tmp_path, capsys):
    """RED TEAM follow-up: once a stale MISSING marker has been
    corrected by a superseding event, the audit must report the
    EFFECTIVE (RECORDED) status, note it supersedes the marker, and no
    longer WARN about a missing durable record."""
    from klpga.neo_win.tournament_history import (
        HistoryEntrant,
        HistoryStageSnapshot,
        RECORD_KIND as HIST_RECORD_KIND,
        STAGE_R1,
        build_missing_stage_marker,
        write_history_stage_atomic,
        write_superseding_stage_event_atomic,
    )

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir, missing_players=())
    _write_csv(output_dir, entrants)

    write_history_stage_atomic(
        build_missing_stage_marker(GAME_CODE, "R1", reason="stale, before real R1 existed", recorded_at_utc="2027-01-01T00:00:00Z"),
        history_dir,
    )
    real_history_entrants = tuple(
        HistoryEntrant(player_code=e.player_code, player_name=e.player_name, win_pct=e.post_r1_win_pct)
        for e in entrants
    )
    write_superseding_stage_event_atomic(
        HistoryStageSnapshot(
            game_code=GAME_CODE, stage=STAGE_R1, record_kind=HIST_RECORD_KIND, recorded_at_utc="2027-01-02T00:00:00Z",
            source_prediction_id="001-C-R1", source_model_version="001-C-FINAL",
            source_generated_at_utc="2027-01-02T00:00:00Z", tournament_name="Live Test Open",
            field_size=len(entrants), entrants=real_history_entrants,
        ),
        history_dir,
    )

    rc = _run(module, _base_argv(db_path_full, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: PASS" in out
    assert "RECORDED (source_prediction_id='001-C-R1'" in out
    assert "supersedes a MISSING marker recorded at '2027-01-01T00:00:00Z'" in out
    assert "DURABLY RECORDED" in out
    assert "[WARN] PRE->R1 movement is NOT durably recorded" not in out


def test_audit_reports_provenance_when_db_gains_a_player_after_freeze(module, db_path, tmp_path, capsys):
    """Item 7: a player the frozen snapshot marked missing_r1_data=True
    (excluded at freeze time) later gets a real round_number=1 row in
    the DB — the audit must surface this as provenance/audit info only,
    never mutate the already-frozen snapshot."""
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)  # E missing, matches db_path's 4/5 real R1 rows
    _write_csv(output_dir, entrants)

    # DB changes AFTER the freeze: E now has a real round_number=1 row.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 1, 'E', 'E', 69, -1)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "PROVENANCE: DB CHANGED SINCE FREEZE" in out
    assert "['E']" in out
    assert "newly available since freeze" in out
    assert "round_to_par=-1" in out
    assert "represents a COMPLETED R1 score" in out
    assert "COMPLETED R1 score (round_to_par is not null): True" in out


def _classify_db(tmp_path, name="classify.sqlite"):
    conn = sqlite3.connect(tmp_path / name)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('E1', 'G1', 'T', 2026, '2027-01-01', '2027-01-04')"
    )
    conn.commit()
    return conn


def test_classify_missing_r1_player_delegates_to_shared_module_with_round_1(module, tmp_path):
    """scripts/45's classifier is now a thin round_number=1 wrapper
    around klpga.neo_win.player_status.classify_player_round_status —
    the full classification-logic test matrix (WD/DQ/DNS/CUT/
    COLLECTION_MISSING/UNKNOWN) lives in tests/test_player_status.py;
    this only proves the wrapper delegates correctly."""
    from klpga.neo_win.player_status import STATUS_WD, classify_player_round_status

    conn = _classify_db(tmp_path)
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('9750', 'X')")
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, withdrawn, disqualified, rounds_played, score_to_par) VALUES "
        "('E1', 'G1', 2026, '9750', 'X', 'WD', NULL, 0, 1, 0, 1, NULL)"
    )
    conn.commit()

    wrapper_result = module._classify_missing_r1_player(conn, "G1", "9750")
    direct_result = classify_player_round_status(conn, "G1", "9750", round_number=1)
    assert wrapper_result == direct_result
    assert wrapper_result.round_number == 1
    assert wrapper_result.classification == STATUS_WD
    conn.close()


def test_audit_prints_classification_for_each_missing_player(module, db_path, tmp_path, capsys):
    """Integration: the audit report includes a classification line for
    every missing_r1_data player, sourced from real player_event data."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, withdrawn, disqualified, rounds_played, score_to_par) VALUES "
        f"({GAME_CODE!r}, {GAME_CODE!r}, 2026, 'E', 'E', 'WD', NULL, 0, 1, 0, 1, NULL)"
    )
    conn.commit()
    conn.close()

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1"

    _freeze_pre_c(c_predictions_dir)
    _snapshot, entrants = _freeze_r1(predictions_dir)  # E missing
    _write_csv(output_dir, entrants)

    rc = _run(module, _base_argv(db_path, c_predictions_dir, predictions_dir, output_dir / "BETA001_R1_FULL.csv", history_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "classification: WD —" in out


def test_audit_errors_cleanly_when_pre_snapshot_missing(module, db_path, tmp_path):
    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    rc = _run(module, _base_argv(
        db_path, tmp_path / "neo_win_c_predictions", predictions_dir,
        tmp_path / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv", history_dir,
    ))
    assert rc == 5
