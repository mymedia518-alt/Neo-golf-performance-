"""Tests for klpga.neo_win.r1_frozen_snapshot — Section A of the
R1->R2 evaluation pipeline (the frozen R1 input contract). Covers the
4-tier source discovery order, each loader against a synthetic fixture
of that exact shape, the idempotent/refuse-to-clobber CSV writer, and
the published-HTML cross-check (by rank, never by name)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.neo_win.r1_frozen_snapshot import (
    SOURCE_CSV_FALLBACK,
    SOURCE_NONE,
    SOURCE_RAW_R1_C,
    SOURCE_RAW_R1_LEGACY,
    SOURCE_TOURNAMENT_HISTORY,
    PlayerR1Frozen,
    load_frozen_r1_snapshot,
    locate_frozen_r1_source,
    parse_published_r1_html,
    validate_rows_against_published_html,
    write_r1_predictions_csv,
)
from klpga.neo_win.tournament_history import (
    STAGE_R1,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    build_missing_stage_marker,
    write_history_stage_atomic,
)

GAME_CODE = "2026080001"


def _empty_dirs(tmp_path):
    return {
        "history_dir": tmp_path / "neo_tournament_history",
        "predictions_dir": tmp_path / "neo_win_predictions",
        "outputs_csv_path": tmp_path / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv",
    }


# ---------------------------------------------------------------
# locate_frozen_r1_source — 4-tier discovery order
# ---------------------------------------------------------------


def test_locate_returns_none_when_nothing_exists(tmp_path):
    dirs = _empty_dirs(tmp_path)
    source, path = locate_frozen_r1_source(GAME_CODE, **dirs)
    assert source == SOURCE_NONE
    assert path is None


def test_locate_prefers_tournament_history_over_everything(tmp_path):
    dirs = _empty_dirs(tmp_path)
    entry = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R1, record_kind=RECORD_KIND, recorded_at_utc="2026-08-27T00:00:00Z",
        source_prediction_id="001-C-R1", source_model_version="round_update", source_generated_at_utc="2026-08-27T00:00:00Z",
        tournament_name="KG Ladies Open", field_size=1,
        entrants=(HistoryEntrant(player_code="p1", player_name="A", win_pct=10.0, make_cut_pct=80.0, position=1, score_to_par=-3.0),),
    )
    write_history_stage_atomic(entry, dirs["history_dir"])
    # Also drop a raw R1-C json — history must still win.
    raw_dir = dirs["predictions_dir"] / "2026"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"neo_win_001-C-R1_{GAME_CODE}.json").write_text("{}", encoding="utf-8")

    source, path = locate_frozen_r1_source(GAME_CODE, **dirs)
    assert source == SOURCE_TOURNAMENT_HISTORY
    assert path == dirs["history_dir"] / GAME_CODE / f"{STAGE_R1}.json"


def test_locate_skips_history_when_it_is_only_a_missing_marker(tmp_path):
    dirs = _empty_dirs(tmp_path)
    marker = build_missing_stage_marker(GAME_CODE, STAGE_R1, reason="not found", recorded_at_utc="2026-08-27T00:00:00Z")
    write_history_stage_atomic(marker, dirs["history_dir"])
    raw_dir = dirs["predictions_dir"] / "2026"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"neo_win_001-C-R1_{GAME_CODE}.json").write_text("{}", encoding="utf-8")

    source, _path = locate_frozen_r1_source(GAME_CODE, **dirs)
    assert source == SOURCE_RAW_R1_C  # falls through the missing marker to the next real tier


def test_locate_prefers_001_c_r1_over_legacy_001_r1(tmp_path):
    dirs = _empty_dirs(tmp_path)
    raw_dir = dirs["predictions_dir"] / "2026"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"neo_win_001-C-R1_{GAME_CODE}.json").write_text("{}", encoding="utf-8")
    (raw_dir / f"neo_win_001-R1_{GAME_CODE}.json").write_text("{}", encoding="utf-8")

    source, _path = locate_frozen_r1_source(GAME_CODE, **dirs)
    assert source == SOURCE_RAW_R1_C


def test_locate_falls_back_to_legacy_001_r1(tmp_path):
    dirs = _empty_dirs(tmp_path)
    raw_dir = dirs["predictions_dir"] / "2026"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"neo_win_001-R1_{GAME_CODE}.json").write_text("{}", encoding="utf-8")

    source, _path = locate_frozen_r1_source(GAME_CODE, **dirs)
    assert source == SOURCE_RAW_R1_LEGACY


def test_locate_falls_back_to_csv_when_no_json_source_exists(tmp_path):
    dirs = _empty_dirs(tmp_path)
    dirs["outputs_csv_path"].parent.mkdir(parents=True)
    dirs["outputs_csv_path"].write_text("player_code,player_name\n", encoding="utf-8")

    source, path = locate_frozen_r1_source(GAME_CODE, **dirs)
    assert source == SOURCE_CSV_FALLBACK
    assert path == dirs["outputs_csv_path"]


# ---------------------------------------------------------------
# load_frozen_r1_snapshot — real per-tier parsing, synthetic fixtures
# ---------------------------------------------------------------


def test_load_from_tournament_history(tmp_path):
    dirs = _empty_dirs(tmp_path)
    entry = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R1, record_kind=RECORD_KIND, recorded_at_utc="2026-08-27T00:00:00Z",
        source_prediction_id="001-C-R1", source_model_version="round_update", source_generated_at_utc="2026-08-27T00:00:00Z",
        tournament_name="KG Ladies Open", field_size=1,
        entrants=(HistoryEntrant(player_code="p1", player_name="A", win_pct=10.0, make_cut_pct=80.0, position=1, score_to_par=-3.0),),
    )
    write_history_stage_atomic(entry, dirs["history_dir"])

    rows, provenance = load_frozen_r1_snapshot(GAME_CODE, **dirs)
    assert provenance["source"] == SOURCE_TOURNAMENT_HISTORY
    assert len(rows) == 1
    assert rows[0].player_code == "p1"
    assert rows[0].r1_win_probability_pct == 10.0
    assert rows[0].r1_make_cut_probability_pct == 80.0
    assert rows[0].r1_actual_rank == 1
    assert rows[0].r1_actual_score_to_par == -3.0


def test_load_from_raw_round_update_json(tmp_path):
    dirs = _empty_dirs(tmp_path)
    raw_dir = dirs["predictions_dir"] / "2026"
    raw_dir.mkdir(parents=True)
    data = {
        "prediction_id": "001-C-R1",
        "created_at_utc": "2026-08-27T00:00:00Z",
        "predictions": [
            {
                "player_code": "p1", "player_name": "A", "r1_position": 2, "r1_score_to_par": -2.0,
                "post_r1_win_pct": 5.0, "post_r1_make_cut_pct": 70.0,
            }
        ],
    }
    (raw_dir / f"neo_win_001-C-R1_{GAME_CODE}.json").write_text(json.dumps(data), encoding="utf-8")

    rows, provenance = load_frozen_r1_snapshot(GAME_CODE, **dirs)
    assert provenance["source"] == SOURCE_RAW_R1_C
    assert rows[0].player_code == "p1"
    assert rows[0].r1_actual_rank == 2
    assert rows[0].model_version == "001-C-R1"


def test_load_from_csv_fallback(tmp_path):
    dirs = _empty_dirs(tmp_path)
    dirs["outputs_csv_path"].parent.mkdir(parents=True)
    dirs["outputs_csv_path"].write_text(
        "player_code,player_name,r1_position,r1_score_to_par,post_r1_win_pct,post_r1_make_cut_pct\n"
        "p1,A,3,-1.0,2.5,60.0\n",
        encoding="utf-8",
    )

    rows, provenance = load_frozen_r1_snapshot(GAME_CODE, **dirs)
    assert provenance["source"] == SOURCE_CSV_FALLBACK
    assert rows[0].player_code == "p1"
    assert rows[0].r1_actual_rank == 3
    assert rows[0].r1_win_probability_pct == 2.5


def test_load_returns_empty_and_reports_not_available_when_nothing_found(tmp_path):
    dirs = _empty_dirs(tmp_path)
    rows, provenance = load_frozen_r1_snapshot(GAME_CODE, **dirs)
    assert rows == []
    assert provenance["source"] == SOURCE_NONE
    assert provenance["source_path"] is None
    assert provenance["n_players"] == 0


# ---------------------------------------------------------------
# write_r1_predictions_csv — idempotent, refuses to clobber
# ---------------------------------------------------------------


def _row(code="p1", name="A", rank=1, score=-3.0, win=10.0, cut=80.0):
    return PlayerR1Frozen(
        tournament_id=GAME_CODE, player_code=code, player_name=name, r1_actual_rank=rank,
        r1_actual_score_to_par=score, r1_win_probability_pct=win, r1_make_cut_probability_pct=cut,
        model_version="001-C-R1", prediction_generated_at="2026-08-27T00:00:00Z",
    )


def test_write_predictions_csv_first_time(tmp_path):
    out_path = tmp_path / "r1" / "predictions.csv"
    action = write_r1_predictions_csv([_row()], out_path)
    assert action == "WRITTEN"
    assert out_path.exists()
    assert "p1" in out_path.read_text(encoding="utf-8")


def test_write_predictions_csv_identical_rewrite_is_no_change(tmp_path):
    out_path = tmp_path / "r1" / "predictions.csv"
    write_r1_predictions_csv([_row()], out_path)
    action = write_r1_predictions_csv([_row()], out_path)
    assert action == "NO_CHANGE"


def test_write_predictions_csv_refuses_to_clobber_different_content(tmp_path):
    out_path = tmp_path / "r1" / "predictions.csv"
    write_r1_predictions_csv([_row()], out_path)
    with pytest.raises(ValueError):
        write_r1_predictions_csv([_row(win=99.0)], out_path)
    # Original content must be untouched after the refused write.
    assert "10.0" in out_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------
# parse_published_r1_html / validate_rows_against_published_html
# ---------------------------------------------------------------


def _html_row(rank, name, score, win, cut):
    return f'<tr><td class="c-pos">{rank}</td><td class="c-name">{name}</td><td class="c-score">{score}</td><td class="c-pct">{win}</td><td class="c-pct">{cut}</td></tr>'


def test_parse_published_html_handles_even_par_and_signed_scores():
    html = _html_row(1, "A", "-8", "2.56%", "87.22%") + _html_row(2, "B", "E", "0.02%", "8.74%") + _html_row(3, "C", "+2", "0.00%", "1.98%")
    rows = parse_published_r1_html(html)
    assert rows[0] == {"rank": 1, "player_name": "A", "score_to_par": -8.0, "win_pct": 2.56, "make_cut_pct": 87.22}
    assert rows[1]["score_to_par"] == 0.0
    assert rows[2]["score_to_par"] == 2.0


def test_validate_matching_rows_reports_no_mismatches():
    html = _html_row(1, "A", "-8", "2.56%", "87.22%")
    html_rows = parse_published_r1_html(html)
    frozen_rows = [_row(rank=1, name="A", score=-8.0, win=2.56, cut=87.22)]
    result = validate_rows_against_published_html(frozen_rows, html_rows)
    assert result["valid"] is True
    assert result["mismatches"] == []


def test_validate_detects_name_mismatch():
    html = _html_row(1, "A", "-8", "2.56%", "87.22%")
    html_rows = parse_published_r1_html(html)
    frozen_rows = [_row(rank=1, name="DIFFERENT_NAME", score=-8.0, win=2.56, cut=87.22)]
    result = validate_rows_against_published_html(frozen_rows, html_rows)
    assert result["valid"] is False
    assert result["mismatches"][0]["reason"] == "NAME_MISMATCH"


def test_validate_detects_value_mismatch_outside_tolerance():
    html = _html_row(1, "A", "-8", "2.56%", "87.22%")
    html_rows = parse_published_r1_html(html)
    frozen_rows = [_row(rank=1, name="A", score=-8.0, win=99.0, cut=87.22)]
    result = validate_rows_against_published_html(frozen_rows, html_rows)
    assert result["valid"] is False
    assert result["mismatches"][0]["reason"] == "WIN_PCT_VALUE_MISMATCH"


def test_validate_reports_rank_present_in_html_missing_from_frozen():
    html = _html_row(1, "A", "-8", "2.56%", "87.22%")
    html_rows = parse_published_r1_html(html)
    result = validate_rows_against_published_html([], html_rows)
    assert result["valid"] is False
    assert result["mismatches"][0]["reason"] == "PRESENT_IN_HTML_MISSING_FROM_FROZEN_SOURCE"
