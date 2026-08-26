"""Python-level integrity tests for klpga.site.build — the static-site
generator over the immutable prediction archive. Covers the required
data-integrity properties: the archived JSON is the only prediction
source (never the DB, never inference), every entrant renders, display
rounding never touches the stored value, ranking always follows the
archive's own rank field, and a corrupted archive hard-fails the build
rather than publishing a partial/wrong-looking page."""
from __future__ import annotations

import inspect
import json
import re

import pytest

from klpga.archive.prediction_archive import (
    EntrantSnapshot,
    PredictionSnapshot,
    archive_paths,
    build_live_atomic_provenance,
    write_prediction_snapshot_atomic,
)
from klpga.site import build as site_build
from klpga.site import templates as site_templates
from klpga.site.build import SiteBuildIntegrityError, build_site, load_predictions


def _entrant(rank, code, name, prob, n=10, avg=-2.5, form10=-3.0, form10_n=8, unmatched=False, slice_="moderate_10_19"):
    return EntrantSnapshot(
        rank=rank,
        player_code=code,
        player_name_display=name,
        win_probability=prob,
        prior_events_n=n,
        prior_avg_round_score_to_par=avg,
        prior_recent_form_10=form10,
        prior_recent_form_10_n=form10_n,
        history_slice=slice_,
        player_master_matched=not unmatched,
    )


def _snapshot(entrants, prediction_id="001", game_code="2026080001", cutoff_date="2026-08-27"):
    probs = [e.win_probability for e in entrants]
    return PredictionSnapshot(
        prediction_id=prediction_id,
        created_at_utc="2026-08-26T00:00:00Z",
        record_kind="neo_prediction_archive_v1",
        game_code=game_code,
        tournament_name="제15회 KG 레이디스 오픈",
        cutoff_date=cutoff_date,
        cutoff_source="explicit_arg",
        model_id="M4",
        model_version="v1",
        model_features=("prior_avg_round_score_to_par", "prior_recent_form_10"),
        training_tournament_count=100,
        field_size=len(entrants),
        entrants_predicted=len(entrants),
        dropped_entrants=0,
        probability_sum=sum(probs),
        minimum_probability=min(probs),
        maximum_probability=max(probs),
        zero_history_count=sum(1 for e in entrants if e.prior_events_n == 0),
        unmatched_count=sum(1 for e in entrants if not e.player_master_matched),
        required_final_checks={
            "entrants_parsed_eq_field_size": True,
            "entrants_predicted_eq_field_size": True,
            "dropped_entrants_eq_zero": True,
            "duplicate_player_codes_eq_zero": True,
            "probability_sum_within_tolerance": True,
        },
        known_limitations=("Coarse calibration diagnostics suggest possible over-confidence...",),
        provenance=build_live_atomic_provenance(),
        predictions=tuple(entrants),
    )


def _sample_entrants():
    return [
        _entrant(1, "11134", "서교림", 0.10096653550147967, n=55, slice_="established_20plus"),
        _entrant(2, "8881", "성유진", 0.0589928912997, n=67, slice_="established_20plus"),
        _entrant(3, "8284", "최예림", 0.0575112844584, n=97, slice_="established_20plus"),
        _entrant(4, "ROOKIE1", "루키선수", 0.02, n=0, avg=None, form10=None, form10_n=0, slice_="cold_0"),
        _entrant(5, "13355", "배윤설 0908(A)", 0.0028430214656763, n=0, avg=None, form10=None, form10_n=0,
                  unmatched=True, slice_="cold_0"),
    ]


def _write_archive(predictions_root, snapshot):
    return write_prediction_snapshot_atomic(snapshot, predictions_root)


@pytest.fixture()
def predictions_root(tmp_path):
    root = tmp_path / "predictions"
    snapshot = _snapshot(_sample_entrants())
    _write_archive(root, snapshot)
    return root, snapshot


# ----------------------------------------------------------------
# The archived JSON is the ONLY prediction source
# ----------------------------------------------------------------


def test_build_module_source_never_mentions_run_inference_or_sqlite():
    source = inspect.getsource(site_build) + inspect.getsource(site_templates)
    assert "run_inference" not in source
    assert "sqlite3" not in source


def test_build_module_does_not_import_run_inference_symbol():
    import klpga.site.build as b
    import klpga.site.templates as t

    assert not hasattr(b, "run_inference")
    assert not hasattr(t, "run_inference")
    assert "sqlite3" not in dir(b)
    assert "sqlite3" not in dir(t)


def test_reading_archive_for_the_site_never_needs_write_access(predictions_root, tmp_path):
    root, snapshot = predictions_root
    json_path, _ = archive_paths(root, snapshot.prediction_id, snapshot.game_code, snapshot.cutoff_date)
    import os
    import stat

    os.chmod(json_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        result = build_site(root, tmp_path / "dist")
        assert result.predictions_rendered == 1
    finally:
        os.chmod(json_path, stat.S_IRUSR | stat.S_IWUSR)


# ----------------------------------------------------------------
# All entrants rendered/available; no silent drop
# ----------------------------------------------------------------


def test_all_entrants_rendered_and_available(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    for entrant in snapshot.predictions:
        assert entrant.player_name_display in html
        assert f'data-code="{entrant.player_code}"' in html
    assert html.count('class="pred-row"') == snapshot.field_size


# ----------------------------------------------------------------
# Ranking follows archive order; rounding is display-only
# ----------------------------------------------------------------


def test_displayed_ranking_follows_archive_order(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    ranks_in_html = [int(m) for m in re.findall(r'data-rank="(\d+)"', html)]
    expected = [e.rank for e in sorted(snapshot.predictions, key=lambda e: e.rank)]
    assert ranks_in_html == expected


def test_display_probability_derives_from_archived_probability_rounded_2dp(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    top = snapshot.predictions[0]
    expected_pct = f"{top.win_probability * 100:.2f}%"
    assert expected_pct in html
    assert expected_pct == "10.10%"


def test_probability_rounding_does_not_touch_the_stored_value(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="prediction-data">(.*?)</script>', html)
    embedded = json.loads(match.group(1))
    top_entrant = snapshot.predictions[0]
    embedded_top = next(p for p in embedded["predictions"] if p["player_code"] == top_entrant.player_code)
    # Full precision, not rounded to 2dp — bit-for-bit the archive's own float.
    assert embedded_top["win_probability"] == top_entrant.win_probability


# ----------------------------------------------------------------
# Zero-history and unmatched entrants remain visible
# ----------------------------------------------------------------


def test_zero_history_entrant_remains_visible(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    assert "루키선수" in html
    assert "출전 이력 없음" in html


def test_unmatched_entrant_remains_visible(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    assert "배윤설 0908(A)" in html
    assert "선수 데이터베이스 미매칭" in html


# ----------------------------------------------------------------
# Hard-fail on a corrupted archive (decision #6)
# ----------------------------------------------------------------


def test_build_hard_fails_if_field_size_mismatches_row_count(tmp_path):
    entrants = _sample_entrants()
    snapshot = _snapshot(entrants)
    # Corrupt field_size without changing the row count.
    import dataclasses
    corrupted = dataclasses.replace(snapshot, field_size=999)
    root = tmp_path / "predictions"
    _write_archive(root, corrupted)

    with pytest.raises(SiteBuildIntegrityError, match="field_size"):
        build_site(root, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


def test_build_hard_fails_on_a_rank_gap(tmp_path):
    entrants = _sample_entrants()
    import dataclasses
    entrants[-1] = dataclasses.replace(entrants[-1], rank=99)  # gap: 1,2,3,4,99
    snapshot = _snapshot(entrants)
    root = tmp_path / "predictions"
    _write_archive(root, snapshot)

    with pytest.raises(SiteBuildIntegrityError, match="gap-free"):
        build_site(root, tmp_path / "dist")


def test_build_hard_fails_on_non_positive_maximum_probability(tmp_path):
    import dataclasses
    entrants = _sample_entrants()
    snapshot = _snapshot(entrants)
    corrupted = dataclasses.replace(snapshot, maximum_probability=0.0)
    root = tmp_path / "predictions"
    _write_archive(root, corrupted)

    with pytest.raises(SiteBuildIntegrityError, match="maximum_probability"):
        build_site(root, tmp_path / "dist")


def test_build_hard_fails_with_no_archives_at_all(tmp_path):
    root = tmp_path / "predictions"
    root.mkdir()
    with pytest.raises(SiteBuildIntegrityError, match="nothing to build"):
        build_site(root, tmp_path / "dist")


# ----------------------------------------------------------------
# load_predictions / multi-prediction ordering
# ----------------------------------------------------------------


def test_load_predictions_orders_by_cutoff_date(tmp_path):
    root = tmp_path / "predictions"
    snap_a = _snapshot(_sample_entrants(), prediction_id="002", game_code="G2", cutoff_date="2026-09-01")
    snap_b = _snapshot(_sample_entrants(), prediction_id="001", game_code="G1", cutoff_date="2026-08-27")
    _write_archive(root, snap_a)
    _write_archive(root, snap_b)

    loaded = load_predictions(root)
    assert [s.prediction_id for s in loaded] == ["001", "002"]


def test_build_writes_a_permalink_per_prediction_and_latest_as_home(tmp_path):
    root = tmp_path / "predictions"
    snap_older = _snapshot(_sample_entrants(), prediction_id="001", game_code="G1", cutoff_date="2026-08-20")
    snap_newer = _snapshot(_sample_entrants(), prediction_id="002", game_code="G2", cutoff_date="2026-08-27")
    _write_archive(root, snap_older)
    _write_archive(root, snap_newer)

    result = build_site(root, tmp_path / "dist")
    assert result.latest_prediction_id == "002"
    assert (result.output_root / "predictions" / "001" / "index.html").exists()
    assert (result.output_root / "predictions" / "002" / "index.html").exists()
    # Home (`/`) and the latest prediction's permalink render the SAME
    # underlying table/data — they intentionally differ only in page
    # <title> and which nav item is marked active.
    home_html = (result.output_root / "index.html").read_text(encoding="utf-8")
    detail_html = (result.output_root / "predictions" / "002" / "index.html").read_text(encoding="utf-8")
    home_table = re.search(r"<table.*?</table>", home_html, re.DOTALL).group(0)
    detail_table = re.search(r"<table.*?</table>", detail_html, re.DOTALL).group(0)
    assert home_table == detail_table
