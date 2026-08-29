"""Tests for scripts/build_beta001_post_r3_homepage_preview.py — the
POST-R3 homepage preview CLI. Covers every HARD_STOP gate, a full
successful synthetic run, and read-only-ness against every source."""
from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_beta001_post_r3_homepage_preview.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "2026080099"

_RECOVERY_FIELDNAMES = [
    "player_code", "player_name", "match_status", "r2_rank", "r2_total_score",
    "r2_win_pct", "r2_top5_pct", "r2_top10_pct", "r2_top20_pct",
    "r3_win_pct", "r3_top5_pct", "r3_top10_pct", "r3_top20_pct", "r2_to_r3_win_change_pct",
]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "build_beta001_post_r3_homepage_preview_script")


def _base_db(tmp_path, *, with_r4=False, players=None):
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Test Open', 2026, '2026-08-27', '2026-08-31')",
        (GAME_CODE, GAME_CODE),
    )
    players = players or [
        ("p1", "Player One", -3, -2, -1, True, False, 3),
        ("p2", "Player Two", -1, -1, 0, True, False, 3),
        ("p3", "Player Three", 5, 6, None, False, False, 2),  # CUT
    ]
    for code, name, r1, r2, r3, made_cut, withdrawn, rounds_played in players:
        conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (code, name))
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2026-08-25T00:00:00Z')",
            (GAME_CODE, code, name),
        )
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, made_cut, withdrawn, rounds_played) "
            "VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, code, name, int(made_cut), int(withdrawn), rounds_played),
        )
        rounds = [(1, r1), (2, r2), (3, r3)]
        if with_r4:
            rounds.append((4, -1))
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


def _seed_stage_r3(tmp_path, module, entrants):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from klpga.neo_win.tournament_history import STAGE_R3, HistoryEntrant, HistoryStageSnapshot, RECORD_KIND, write_history_stage_atomic

    snap = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R3, record_kind=RECORD_KIND, recorded_at_utc="2026-08-29T00:00:00Z",
        source_prediction_id="001-C", source_model_version="MODEL_B", source_generated_at_utc="2026-08-29T00:00:00Z",
        tournament_name="Test Open", field_size=len(entrants),
        entrants=tuple(HistoryEntrant(**e) for e in entrants),
    )
    history_dir = tmp_path / "history"
    write_history_stage_atomic(snap, history_dir)
    return history_dir


def _seed_recovery_csv(tmp_path, rows):
    path = tmp_path / "R2_R3_RECOVERY_COMPARISON.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_RECOVERY_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _recovery_row(code, name, change):
    return {
        "player_code": code, "player_name": name, "match_status": "BOTH", "r2_rank": 1, "r2_total_score": -5,
        "r2_win_pct": 10.0, "r2_top5_pct": 20, "r2_top10_pct": 30, "r2_top20_pct": 40,
        "r3_win_pct": 10.0, "r3_top5_pct": 20, "r3_top10_pct": 30, "r3_top20_pct": 40,
        "r2_to_r3_win_change_pct": change,
    }


DEFAULT_ENTRANTS = [
    {"player_code": "p1", "player_name": "Player One", "win_pct": 60.0, "top5_pct": 80.0, "top10_pct": 90.0, "top20_pct": 95.0},
    {"player_code": "p2", "player_name": "Player Two", "win_pct": 40.0, "top5_pct": 70.0, "top10_pct": 85.0, "top20_pct": 92.0},
    {"player_code": "p3", "player_name": "Player Three", "win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0},
]


def _argv(db_path, history_dir, recovery_csv, tmp_path):
    return [
        "build_beta001_post_r3_homepage_preview.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--history-dir", str(history_dir), "--r2-recovery-csv", str(recovery_csv),
        "--tournament-name", "Test Open", "--output-dir", str(tmp_path / "out"), "--no-png",
    ]


def test_r4_present_hard_stops(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path, with_r4=True)
    history_dir = _seed_stage_r3(tmp_path, module, DEFAULT_ENTRANTS)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "FUTURE_DATA_LEAKAGE" in out
    assert not (tmp_path / "out").exists()


def test_stage_r3_missing_hard_stops(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, tmp_path / "no_history", recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "STAGE_R3 not found" in out
    assert not (tmp_path / "out").exists()


def test_recovery_csv_missing_hard_stops(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    history_dir = _seed_stage_r3(tmp_path, module, DEFAULT_ENTRANTS)
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, tmp_path / "does_not_exist.csv", tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "R2 recovery CSV not found" in out


def test_duplicate_player_code_in_stage_r3_hard_stops(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    dup_entrants = DEFAULT_ENTRANTS + [{"player_code": "p1", "player_name": "Player One Dup", "win_pct": 5.0, "top5_pct": 10.0, "top10_pct": 15.0, "top20_pct": 20.0}]
    history_dir = _seed_stage_r3(tmp_path, module, dup_entrants)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "duplicate player_code" in out


def test_win_sum_off_hard_stops(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    bad_entrants = [
        {"player_code": "p1", "player_name": "Player One", "win_pct": 1.0, "top5_pct": 2.0, "top10_pct": 3.0, "top20_pct": 4.0},
        {"player_code": "p2", "player_name": "Player Two", "win_pct": 1.0, "top5_pct": 2.0, "top10_pct": 3.0, "top20_pct": 4.0},
        {"player_code": "p3", "player_name": "Player Three", "win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0},
    ]
    history_dir = _seed_stage_r3(tmp_path, module, bad_entrants)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "WIN SUM" in out


def test_probability_invariant_violation_hard_stops(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    bad_entrants = [
        {"player_code": "p1", "player_name": "Player One", "win_pct": 80.0, "top5_pct": 70.0, "top10_pct": 60.0, "top20_pct": 50.0},
        {"player_code": "p2", "player_name": "Player Two", "win_pct": 20.0, "top5_pct": 40.0, "top10_pct": 60.0, "top20_pct": 80.0},
        {"player_code": "p3", "player_name": "Player Three", "win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0},
    ]
    history_dir = _seed_stage_r3(tmp_path, module, bad_entrants)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "probability invariant violations" in out.lower() or "invariant" in out.lower()


def test_end_to_end_success_writes_html_and_matches_top10(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    history_dir = _seed_stage_r3(tmp_path, module, DEFAULT_ENTRANTS)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "STATUS: VALIDATION_PASSED" in out
    assert "=== TOP 10 (R3 POSITION ascending / tied WIN% descending) ===" in out
    # Player One (-6) and Player Two (-2) have distinct scores -- no real
    # tie, so neither gets a T-prefix.
    assert "1. Player One" in out and "T1. Player One" not in out
    assert "2. Player Two" in out and "T2. Player Two" not in out

    html_path = tmp_path / "out" / GAME_CODE / "preview.html"
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "Player One" in html and "Player Two" in html
    assert "Player Three" in html  # in non-advancing section
    assert "60.00%" in html
    assert '<td class="c-pos">1</td>' in html  # solo rank -- no T-prefix
    # Player One: r1=-3, r2=-2, r3=-1, cumulative=-6 -- 3R and 합계 must render as separate cells.
    assert '<td class="c-score">-1</td><td class="c-score">-6</td>' in html
    assert "Probabilities represent NEO model estimates for the final tournament result after Round 4." in html


def test_end_to_end_real_tie_shows_t_prefix_only_for_tied_players(module, tmp_path, capsys, monkeypatch):
    """End-to-end confirmation of the fixed rule: p1/p2 share the same
    real cumulative score (-6) and must both show T1; p3, alone at -2,
    must show plain '3' (competition ranking skips to 3 after the
    2-way tie) -- no T -- even though it's a genuine STAGE_R3 ACTIVE
    player."""
    import sys

    players = [
        ("p1", "Tied One", -3, -2, -1, True, False, 3),   # cumulative -6
        ("p2", "Tied Two", -1, -3, -2, True, False, 3),   # cumulative -6
        ("p3", "Solo Three", -1, -1, 0, True, False, 3),  # cumulative -2
    ]
    db_path = _base_db(tmp_path, players=players)
    entrants = [
        {"player_code": "p1", "player_name": "Tied One", "win_pct": 55.0, "top5_pct": 70.0, "top10_pct": 85.0, "top20_pct": 95.0},
        {"player_code": "p2", "player_name": "Tied Two", "win_pct": 40.0, "top5_pct": 65.0, "top10_pct": 80.0, "top20_pct": 92.0},
        {"player_code": "p3", "player_name": "Solo Three", "win_pct": 5.0, "top5_pct": 10.0, "top10_pct": 20.0, "top20_pct": 40.0},
    ]
    history_dir = _seed_stage_r3(tmp_path, module, entrants)
    recovery_csv = _seed_recovery_csv(tmp_path, [
        _recovery_row("p1", "Tied One", 3.0), _recovery_row("p2", "Tied Two", 2.0), _recovery_row("p3", "Solo Three", 0.0),
    ])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: VALIDATION_PASSED" in out
    assert "T1. Tied One" in out
    assert "T1. Tied Two" in out
    assert "3. Solo Three" in out and "T3. Solo Three" not in out

    html = (tmp_path / "out" / GAME_CODE / "preview.html").read_text(encoding="utf-8")
    assert html.count('<td class="c-pos">T1</td>') == 2
    assert '<td class="c-pos">3</td>' in html


def test_readonly_never_modifies_sources(module, tmp_path, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    history_dir = _seed_stage_r3(tmp_path, module, DEFAULT_ENTRANTS)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])

    db_bytes_before = db_path.read_bytes()
    stage_r3_path = history_dir / GAME_CODE / "R3.json"
    stage_r3_bytes_before = stage_r3_path.read_bytes()
    recovery_bytes_before = recovery_csv.read_bytes()

    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    assert rc == 0

    assert db_path.read_bytes() == db_bytes_before
    assert stage_r3_path.read_bytes() == stage_r3_bytes_before
    assert recovery_csv.read_bytes() == recovery_bytes_before


def test_no_png_flag_skips_capture(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _base_db(tmp_path)
    history_dir = _seed_stage_r3(tmp_path, module, DEFAULT_ENTRANTS)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "PNG: skipped (--no-png)" in out
    assert not (tmp_path / "out" / GAME_CODE / "preview.png").exists()


def test_deep_dive_and_collapsed_non_advancing_present_in_end_to_end_output(module, tmp_path, capsys, monkeypatch):
    """DEFAULT_ENTRANTS has no real tie and no one-stroke-back inversion,
    so NEO DEEP DIVE correctly stays absent; the non-advancing section
    must always render as a collapsed <details>/<summary>, regardless."""
    import sys

    db_path = _base_db(tmp_path)
    history_dir = _seed_stage_r3(tmp_path, module, DEFAULT_ENTRANTS)
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "Player One", -3.0), _recovery_row("p2", "Player Two", 9.72)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    assert rc == 0

    html = (tmp_path / "out" / GAME_CODE / "preview.html").read_text(encoding="utf-8")
    assert "<summary>최종라운드 비진출 선수 1명 보기</summary>" in html
    assert "<h3>" not in html


# ---------------------------------------------------------------
# Golden-value regression guard (game_code 2026080001 only)
# ---------------------------------------------------------------

GOLDEN_GAME_CODE = "2026080001"


def _golden_db(tmp_path, *, srihee_win_pct):
    db_path = tmp_path / "golden.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Golden Open', 2026, '2026-08-27', '2026-08-31')",
        (GOLDEN_GAME_CODE, GOLDEN_GAME_CODE),
    )
    players = [("g1", "노승희", -9, -9, -9, True, False, 3)]
    for code, name, r1, r2, r3, made_cut, withdrawn, rounds_played in players:
        conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (code, name))
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2026-08-25T00:00:00Z')",
            (GOLDEN_GAME_CODE, code, name),
        )
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, made_cut, withdrawn, rounds_played) "
            "VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
            (GOLDEN_GAME_CODE, GOLDEN_GAME_CODE, code, name, int(made_cut), int(withdrawn), rounds_played),
        )
        for rn, val in [(1, r1), (2, r2), (3, r3)]:
            conn.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, "
                "player_name, round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, 70, ?)",
                (GOLDEN_GAME_CODE, GOLDEN_GAME_CODE, rn, code, name, val),
            )
    conn.commit()
    conn.close()
    return db_path


def _golden_stage_r3(tmp_path, module, *, srihee_win_pct):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from klpga.neo_win.tournament_history import STAGE_R3, HistoryEntrant, HistoryStageSnapshot, RECORD_KIND, write_history_stage_atomic

    entrant = HistoryEntrant(player_code="g1", player_name="노승희", win_pct=srihee_win_pct, top5_pct=30.0, top10_pct=50.0, top20_pct=70.0)
    snap = HistoryStageSnapshot(
        game_code=GOLDEN_GAME_CODE, stage=STAGE_R3, record_kind=RECORD_KIND, recorded_at_utc="2026-08-29T00:00:00Z",
        source_prediction_id="001-C", source_model_version="MODEL_B", source_generated_at_utc="2026-08-29T00:00:00Z",
        tournament_name="Golden Open", field_size=1, entrants=(entrant,),
    )
    history_dir = tmp_path / "golden_history"
    write_history_stage_atomic(snap, history_dir)
    return history_dir


def _golden_argv(db_path, history_dir, recovery_csv, tmp_path):
    return [
        "build_beta001_post_r3_homepage_preview.py", "--db", str(db_path), "--game-code", GOLDEN_GAME_CODE,
        "--history-dir", str(history_dir), "--r2-recovery-csv", str(recovery_csv),
        "--tournament-name", "Golden Open", "--output-dir", str(tmp_path / "out"), "--no-png",
    ]


def test_golden_value_mismatch_hard_stops_for_2026080001(module, tmp_path, capsys, monkeypatch):
    import sys

    db_path = _golden_db(tmp_path, srihee_win_pct=99.99)
    history_dir = _golden_stage_r3(tmp_path, module, srihee_win_pct=99.99)  # wrong value -- known-verified is 15.04
    recovery_csv = _seed_recovery_csv(tmp_path, [{
        "player_code": "g1", "player_name": "노승희", "match_status": "BOTH", "r2_rank": 1, "r2_total_score": -9,
        "r2_win_pct": 10.0, "r2_top5_pct": 20, "r2_top10_pct": 30, "r2_top20_pct": 40,
        "r3_win_pct": 99.99, "r3_top5_pct": 30, "r3_top10_pct": 50, "r3_top20_pct": 70, "r2_to_r3_win_change_pct": 0.0,
    }])
    monkeypatch.setattr(sys, "argv", _golden_argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "golden-value mismatch" in out
    assert not (tmp_path / "out").exists()


def test_golden_value_check_skipped_for_other_game_codes(module, tmp_path, capsys, monkeypatch):
    """The exact same 'wrong' 99.99% value for 노승희 must NOT trigger a
    HARD_STOP under a different game_code -- the guard is scoped to
    2026080001 only, never a general check applied to every tournament."""
    import sys

    db_path = _base_db(tmp_path, players=[("p1", "노승희", -9, -9, -9, True, False, 3)])
    history_dir = _seed_stage_r3(tmp_path, module, [
        {"player_code": "p1", "player_name": "노승희", "win_pct": 99.99, "top5_pct": 100.0, "top10_pct": 100.0, "top20_pct": 100.0},
    ])
    recovery_csv = _seed_recovery_csv(tmp_path, [_recovery_row("p1", "노승희", 0.0)])
    monkeypatch.setattr(sys, "argv", _argv(db_path, history_dir, recovery_csv, tmp_path))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: VALIDATION_PASSED" in out
    assert "golden-value" not in out
