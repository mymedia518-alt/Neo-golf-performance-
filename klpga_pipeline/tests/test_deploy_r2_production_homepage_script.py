"""End-to-end test for scripts/deploy_r2_production_homepage.py — the
R2 PRODUCTION DEPLOYMENT. Fully synthetic: real-shaped CSV files and a
real-shaped R1 immutable HTML fixture, all written under tmp_path. No
network, no real DB, no simulation (this script never runs one)."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "deploy_r2_production_homepage.py"
GAME_CODE = "2026080099"

_R1_HTML_FIXTURE = "<html><body>R1 IMMUTABLE HISTORICAL PAGE -- never modified by this script</body></html>"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "deploy_r2_production_homepage_script")


def _write_cut_eval_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["player_code", "player_name", "r1_rank", "r1_score_to_par", "r1_make_cut_pct",
                  "predicted_cut_at_50", "actual_r2_status", "actual_cut", "absolute_probability_error"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def _write_forecast_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["player_code", "player_name", "r2_rank", "r2_total_score", "top20_pct", "top10_pct", "top5_pct", "win_pct"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def _base_args(tmp_path, argv_extra=()):
    repo_root = tmp_path / "repo"
    r1_html = repo_root / "docs" / "tournaments" / "2026" / "kg-ladies-open" / "r1" / "index.html"
    r1_html.parent.mkdir(parents=True, exist_ok=True)
    r1_html.write_text(_R1_HTML_FIXTURE, encoding="utf-8")

    return [
        "deploy_r2_production_homepage.py",
        "--game-code", GAME_CODE,
        "--tournament-name", "Test Open",
        "--pre-cutoff-date", "2026-08-27",
        "--cut-eval-csv", str(tmp_path / "player_cut_evaluation.csv"),
        "--forecast-csv", str(tmp_path / "forecast.csv"),
        "--history-dir", str(tmp_path / "neo_tournament_history"),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
        "--outputs-csv-path", str(tmp_path / "BETA001_R1_FULL.csv"),
        "--repo-root", str(repo_root),
        *argv_extra,
    ], r1_html


def _run(module, argv):
    with patch("sys.argv", argv):
        return module.main()


def _cut_eval_rows():
    return [
        {"player_code": "p1", "player_name": "A", "r1_rank": "1", "r1_score_to_par": "-2", "r1_make_cut_pct": "80.0", "actual_r2_status": "MADE_CUT"},
        {"player_code": "p2", "player_name": "B", "r1_rank": "2", "r1_score_to_par": "-1", "r1_make_cut_pct": "70.0", "actual_r2_status": "MADE_CUT"},
        {"player_code": "p3", "player_name": "C", "r1_rank": "3", "r1_score_to_par": "0", "r1_make_cut_pct": "20.0", "actual_r2_status": "MISSED_CUT"},
        {"player_code": "p4", "player_name": "D", "r1_rank": "4", "r1_score_to_par": "1", "r1_make_cut_pct": "50.0", "actual_r2_status": "WD_AFTER_R1_START"},
    ]


def _forecast_rows(win1=60.0, win2=40.0):
    return [
        {"player_code": "p1", "player_name": "A", "r2_rank": "1", "r2_total_score": "140", "top20_pct": "95.0", "top10_pct": "85.0", "top5_pct": "70.0", "win_pct": f"{win1}"},
        {"player_code": "p2", "player_name": "B", "r2_rank": "2", "r2_total_score": "142", "top20_pct": "90.0", "top10_pct": "70.0", "top5_pct": "50.0", "win_pct": f"{win2}"},
    ]


def test_end_to_end_deployment_writes_r2_page_and_blocks_root_home(module, tmp_path, capsys):
    """P0-4 HOME OWNERSHIP GUARD: this script is scoped to the KG R2
    route only and must never be able to claim or overwrite the
    production root HOME (docs/index.html) -- that page belongs
    exclusively to the TOP120 canonical publisher. The R2 route write
    must still succeed even though the root write is blocked."""
    argv, r1_html = _base_args(tmp_path, argv_extra=["--expected-population", "2"])
    _write_cut_eval_csv(Path(tmp_path / "player_cut_evaluation.csv"), _cut_eval_rows())
    _write_forecast_csv(Path(tmp_path / "forecast.csv"), _forecast_rows())

    exit_code = _run(module, argv)
    captured = capsys.readouterr().out
    assert exit_code == 6, captured
    assert "ALL_PASSED: True" in captured
    assert "HOME OWNERSHIP GUARD" in captured
    assert "[BLOCKED]" in captured

    repo_root = tmp_path / "repo"
    r2_html_path = repo_root / "docs" / "tournaments" / "2026" / "kg-ladies-open" / "r2" / "index.html"
    root_index_path = repo_root / "docs" / "index.html"
    assert r2_html_path.is_file()
    assert not root_index_path.exists()

    r2_html = r2_html_path.read_text(encoding="utf-8")
    assert 'data-player-code="p1"' in r2_html and 'data-player-code="p2"' in r2_html
    assert 'data-player-code="p3"' not in r2_html  # p3 (missed cut) never enters
    assert 'data-player-code="p4"' not in r2_html  # p4 (WD_AFTER_R1_START) never enters
    assert "2R 종료 후 우승 경쟁 예측" in r2_html
    assert "NEO 첫 실전 검증" in r2_html

    assert r1_html.read_text(encoding="utf-8") == "<html><body>R1 IMMUTABLE HISTORICAL PAGE -- never modified by this script</body></html>"


def test_wd_player_leaking_into_forecast_aborts_and_writes_nothing(module, tmp_path, capsys):
    argv, _r1_html = _base_args(tmp_path)
    _write_cut_eval_csv(Path(tmp_path / "player_cut_evaluation.csv"), _cut_eval_rows())
    leaked_rows = _forecast_rows() + [
        {"player_code": "p4", "player_name": "D", "r2_rank": "3", "r2_total_score": "150", "top20_pct": "10.0", "top10_pct": "5.0", "top5_pct": "2.0", "win_pct": "0.5"},
    ]
    _write_forecast_csv(Path(tmp_path / "forecast.csv"), leaked_rows)

    exit_code = _run(module, argv)
    captured = capsys.readouterr().out
    assert exit_code == 4, captured
    assert "ALL_PASSED: False" in captured
    assert "NO_WD_OR_MISSED_CUT_PLAYERS_IN_FORECAST" in captured

    repo_root = tmp_path / "repo"
    assert not (repo_root / "docs" / "tournaments" / "2026" / "kg-ladies-open" / "r2" / "index.html").exists()


def test_expected_population_mismatch_aborts(module, tmp_path, capsys):
    argv, _r1_html = _base_args(tmp_path, argv_extra=["--expected-population", "62"])
    _write_cut_eval_csv(Path(tmp_path / "player_cut_evaluation.csv"), _cut_eval_rows())
    _write_forecast_csv(Path(tmp_path / "forecast.csv"), _forecast_rows())

    exit_code = _run(module, argv)
    captured = capsys.readouterr().out
    assert exit_code == 4, captured
    assert "FORECAST_POPULATION_MATCHES_EXPECTED" in captured


def test_dry_run_passes_gates_but_writes_nothing(module, tmp_path, capsys):
    argv, _r1_html = _base_args(tmp_path, argv_extra=["--dry-run"])
    _write_cut_eval_csv(Path(tmp_path / "player_cut_evaluation.csv"), _cut_eval_rows())
    _write_forecast_csv(Path(tmp_path / "forecast.csv"), _forecast_rows())

    exit_code = _run(module, argv)
    captured = capsys.readouterr().out
    assert exit_code == 0, captured
    assert "ALL_PASSED: True" in captured
    assert "nothing was written" in captured

    repo_root = tmp_path / "repo"
    assert not (repo_root / "docs" / "tournaments" / "2026" / "kg-ladies-open" / "r2" / "index.html").exists()
    assert not (repo_root / "docs" / "index.html").exists()


def test_missing_source_csv_fails_loudly(module, tmp_path, capsys):
    argv, _r1_html = _base_args(tmp_path)
    # neither CSV written
    exit_code = _run(module, argv)
    captured = capsys.readouterr().out
    assert exit_code == 3, captured
    assert "FATAL" in captured
