"""Tests for scripts/recover_r2_frozen_forecast_and_compare_r3.py — the
READ-ONLY recovery/compare tool for the confirmed real incident where
scripts/run_beta001_r2_update.py's real-mode pipeline never freezes
STAGE_R2. Every test proves the tool never writes to anything except
its own --output-dir: the recovered R2 CSV and the frozen STAGE_R3
record are both opened read-only."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "recover_r2_frozen_forecast_and_compare_r3.py"
GAME_CODE = "2026080001"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "recover_r2_frozen_forecast_and_compare_r3_script")


def _write_r2_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "player_code", "player_name", "r2_rank", "r2_total_score",
            "top20_pct", "top10_pct", "top5_pct", "win_pct",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _seed_r3_history(module, history_dir, entrants):
    from klpga.neo_win.tournament_history import STAGE_R3, HistoryEntrant, HistoryStageSnapshot, RECORD_KIND, write_history_stage_atomic

    snap = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R3, record_kind=RECORD_KIND, recorded_at_utc="2026-08-29T00:00:00Z",
        source_prediction_id="001-C", source_model_version="MODEL_B", source_generated_at_utc="2026-08-29T00:00:00Z",
        tournament_name="Test Open", field_size=len(entrants),
        entrants=tuple(HistoryEntrant(**e) for e in entrants),
    )
    write_history_stage_atomic(snap, history_dir)


# ---------------------------------------------------------------
# read_r2_csv / check_* pure functions
# ---------------------------------------------------------------


def test_read_r2_csv_matches_real_confirmed_schema(module, tmp_path):
    """The exact real, confirmed column schema and example values the
    user reported from the real recovered CSV."""
    csv_path = _write_r2_csv(tmp_path / "r2.csv", [
        {"player_code": "p_a", "player_name": "A", "r2_rank": 1, "r2_total_score": -9,
         "top20_pct": 94.98, "top10_pct": 64.72, "top5_pct": 27.26, "win_pct": 7.26},
        {"player_code": "p_b", "player_name": "B", "r2_rank": 7, "r2_total_score": -4,
         "top20_pct": 62.32, "top10_pct": 34.32, "top5_pct": 10.72, "win_pct": 1.88},
    ])
    rows, problems = module.read_r2_csv(csv_path)
    assert problems == []
    assert len(rows) == 2
    a = next(r for r in rows if r.player_code == "p_a")
    assert a.r2_rank == 1
    assert a.r2_total_score == -9.0
    assert a.win_pct == 7.26 and a.top5_pct == 27.26 and a.top10_pct == 64.72 and a.top20_pct == 94.98


def test_read_r2_csv_wrong_header_reports_problem_not_silent_coercion(module, tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("player_code,player_name,win_pct\np1,A,10.0\n", encoding="utf-8")
    rows, problems = module.read_r2_csv(csv_path)
    assert rows == []
    assert len(problems) == 1
    assert "expected columns" in problems[0]


def test_check_player_code_uniqueness_finds_real_duplicate(module):
    R2Row = module.R2Row
    rows = [
        R2Row("p1", "A", 1, -9.0, 10.0, 20.0, 30.0, 40.0),
        R2Row("p1", "A dup", 2, -8.0, 5.0, 10.0, 15.0, 20.0),
        R2Row("p2", "B", 3, -7.0, 5.0, 10.0, 15.0, 20.0),
    ]
    assert module.check_player_code_uniqueness(rows) == ["p1"]


def test_check_probability_invariants_flags_violation_never_corrects(module):
    R2Row = module.R2Row
    rows = [R2Row("p1", "A", 1, -9.0, win_pct=80.0, top5_pct=70.0, top10_pct=60.0, top20_pct=50.0)]  # reversed
    violations = module.check_probability_invariants(rows, label="R2")
    assert len(violations) == 1
    assert "p1" in violations[0]


def test_check_probability_invariants_passes_valid_monotonic_row(module):
    R2Row = module.R2Row
    rows = [R2Row("p1", "A", 1, -9.0, win_pct=7.26, top5_pct=27.26, top10_pct=64.72, top20_pct=94.98)]
    assert module.check_probability_invariants(rows, label="R2") == []


def test_check_r2_rank_score_monotonic_flags_out_of_order(module):
    R2Row = module.R2Row
    rows = [
        R2Row("p1", "A", 1, -9.0, None, None, None, None),   # best rank, best (lowest) score
        R2Row("p2", "B", 2, -10.0, None, None, None, None),  # worse rank but a LOWER score -- contradiction
    ]
    problems = module.check_r2_rank_score_monotonic(rows)
    assert len(problems) == 1


def test_build_comparison_never_fabricates_missing_side(module):
    R2Row = module.R2Row

    class _FakeEntrant:
        def __init__(self, player_code, player_name, win_pct):
            self.player_code = player_code
            self.player_name = player_name
            self.win_pct = win_pct
            self.top5_pct = self.top10_pct = self.top20_pct = None

    r2_rows = [R2Row("p1", "A", 1, -9.0, win_pct=10.0, top5_pct=20.0, top10_pct=30.0, top20_pct=40.0)]
    r3_entrants = [_FakeEntrant("p2", "B", 15.0)]
    comparison = module.build_comparison(r2_rows, r3_entrants)
    by_code = {c["player_code"]: c for c in comparison}
    assert by_code["p1"]["match_status"] == module.MATCH_R2_ONLY
    assert by_code["p1"]["r3_win_pct"] is None
    assert by_code["p1"]["r2_to_r3_win_change_pct"] is None
    assert by_code["p2"]["match_status"] == module.MATCH_R3_ONLY
    assert by_code["p2"]["r2_win_pct"] is None


def test_build_comparison_computes_real_delta_for_matched_player(module):
    R2Row = module.R2Row

    class _FakeEntrant:
        def __init__(self, player_code, player_name, win_pct):
            self.player_code = player_code
            self.player_name = player_name
            self.win_pct = win_pct
            self.top5_pct = self.top10_pct = self.top20_pct = None

    r2_rows = [R2Row("p1", "A", 1, -9.0, win_pct=7.26, top5_pct=27.26, top10_pct=64.72, top20_pct=94.98)]
    r3_entrants = [_FakeEntrant("p1", "A", 42.0)]
    comparison = module.build_comparison(r2_rows, r3_entrants)
    assert comparison[0]["match_status"] == module.MATCH_BOTH
    assert comparison[0]["r2_to_r3_win_change_pct"] == pytest.approx(42.0 - 7.26)


# ---------------------------------------------------------------
# main() end-to-end — proves read-only-ness and provenance content
# ---------------------------------------------------------------


def test_main_writes_only_under_output_dir_never_touches_sources(module, tmp_path, capsys):
    r2_csv = _write_r2_csv(tmp_path / "recovered" / "r2.csv", [
        {"player_code": "p1", "player_name": "A", "r2_rank": 1, "r2_total_score": -9,
         "top20_pct": 94.98, "top10_pct": 64.72, "top5_pct": 27.26, "win_pct": 7.26},
    ])
    r2_csv_bytes_before = r2_csv.read_bytes()
    history_dir = tmp_path / "history"
    _seed_r3_history(module, history_dir, [
        {"player_code": "p1", "player_name": "A", "win_pct": 42.0, "top5_pct": 78.0, "top10_pct": 88.0, "top20_pct": 94.0},
    ])
    history_files_before = sorted(p.name for p in (history_dir / GAME_CODE).iterdir())

    output_dir = tmp_path / "output"
    argv_module_main = module.main
    import sys
    monkeypatch_argv = [
        "recover_r2_frozen_forecast_and_compare_r3.py",
        "--r2-csv", str(r2_csv), "--game-code", GAME_CODE,
        "--history-dir", str(history_dir), "--output-dir", str(output_dir),
    ]
    old_argv = sys.argv
    sys.argv = monkeypatch_argv
    try:
        rc = argv_module_main()
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert rc == 0
    assert "RECOVERY SOURCE VALID: YES" in out
    assert "READY FOR R2->R3 COMPARISON: YES" in out
    assert "R2.JSON REQUIRED: NO" in out
    assert "RECALCULATION REQUIRED: NO" in out
    assert "FROZEN ARTIFACT MODIFICATION REQUIRED: NO" in out

    # Sources untouched, byte-for-byte.
    assert r2_csv.read_bytes() == r2_csv_bytes_before
    assert sorted(p.name for p in (history_dir / GAME_CODE).iterdir()) == history_files_before

    comparison_csv = output_dir / GAME_CODE / "R2_R3_RECOVERY_COMPARISON.csv"
    provenance_json = output_dir / GAME_CODE / "R2_R3_RECOVERY_PROVENANCE.json"
    assert comparison_csv.exists()
    assert provenance_json.exists()

    provenance = json.loads(provenance_json.read_text(encoding="utf-8"))
    assert provenance["source_type"] == "recovered_from_frozen_r2_forecast"
    assert provenance["source_path"] == str(r2_csv)
    assert provenance["recovered_after_stage"] == "R3"
    assert provenance["recalculated"] is False
    assert provenance["source_sha256"] == __import__("hashlib").sha256(r2_csv_bytes_before).hexdigest()


def test_main_reports_r3_not_found_without_crashing(module, tmp_path, capsys):
    r2_csv = _write_r2_csv(tmp_path / "r2.csv", [
        {"player_code": "p1", "player_name": "A", "r2_rank": 1, "r2_total_score": -9,
         "top20_pct": 94.98, "top10_pct": 64.72, "top5_pct": 27.26, "win_pct": 7.26},
    ])
    output_dir = tmp_path / "output"
    import sys
    old_argv = sys.argv
    sys.argv = [
        "recover_r2_frozen_forecast_and_compare_r3.py",
        "--r2-csv", str(r2_csv), "--game-code", GAME_CODE,
        "--history-dir", str(tmp_path / "no_history_here"), "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert rc == 0
    assert "R3 PLAYER COUNT: 0 (STAGE_R3 NOT FOUND" in out
    assert "READY FOR R2->R3 COMPARISON: NO" in out


def test_main_withholds_comparison_csv_when_source_invalid(module, tmp_path, capsys):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("player_code,win_pct\np1,10.0\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    import sys
    old_argv = sys.argv
    sys.argv = [
        "recover_r2_frozen_forecast_and_compare_r3.py",
        "--r2-csv", str(bad_csv), "--game-code", GAME_CODE,
        "--history-dir", str(tmp_path / "history"), "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert rc == 0
    assert "RECOVERY SOURCE VALID: NO" in out
    assert not (output_dir / GAME_CODE / "R2_R3_RECOVERY_COMPARISON.csv").exists()
    assert (output_dir / GAME_CODE / "R2_R3_RECOVERY_PROVENANCE.json").exists()
