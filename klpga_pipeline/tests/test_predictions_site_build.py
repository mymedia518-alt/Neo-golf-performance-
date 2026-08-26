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


# ----------------------------------------------------------------
# v1.1 public-copy regression tests: normal reader-facing UI must
# never expose model name/version, calibration-limitation text,
# internal docs references, or a false SG/GIR/driving/putting usage
# claim — while the archive JSON itself, and the page's transparency
# JSON blob (explicitly internal/archive metadata, not prose), must
# stay untouched. See docs/PREDICTIONS_SITE.md "Public copy — model
# explanation, v1.1".
# ----------------------------------------------------------------

_EXCLUDED_STAT_TERMS = ("스트로크게인드", "Strokes Gained", "그린적중률", "GIR", "드라이빙", "퍼팅")


def _visible_text_excluding_transparency_blob(html: str) -> str:
    """The embedded `<script type="application/json" id="prediction-data">`
    block is internal/archive-provenance metadata (see
    `templates._embedded_data_json`'s docstring), not reader-facing
    prose — strip it before asserting on what an ordinary reader
    actually sees."""
    return re.sub(
        r'<script type="application/json" id="prediction-data">.*?</script>', "", html, flags=re.DOTALL
    )


def test_public_page_never_mentions_model_name_or_version_in_visible_text(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    visible = _visible_text_excluding_transparency_blob(html)

    assert "M4" not in visible
    assert "Production v1" not in visible
    # The transparency blob is the ONE sanctioned place model_id/
    # model_version legitimately appear — confirm they're actually
    # there (not silently dropped from the archive-metadata artifact).
    assert '"model_id": "M4"' in html
    assert '"model_version": "v1"' in html


def test_public_page_never_shows_calibration_limitation_or_internal_docs_reference(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    visible = _visible_text_excluding_transparency_blob(html)

    assert "보정" not in visible
    assert "calibration" not in visible.lower()
    assert "SITE_STRUCTURE_TODO" not in html  # not even in the transparency blob
    assert "docs/" not in visible


def test_public_page_only_mentions_excluded_stats_inside_the_negative_disclaimer(predictions_root, tmp_path):
    """SG/GIR/driving/putting terms may appear ONLY inside the fixed
    'NEO does not currently use...' disclaimer — never anywhere that
    could read as a claim they were used for this prediction."""
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")
    visible = _visible_text_excluding_transparency_blob(html)

    assert site_templates.METHODOLOGY_EXCLUSION_KO in visible
    remainder = visible.replace(site_templates.METHODOLOGY_EXCLUSION_KO, "")
    for term in _EXCLUDED_STAT_TERMS:
        assert term not in remainder, f"{term!r} appears outside the negative disclaimer"


def test_why_section_shows_rank1_player_with_archived_values(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")

    why_match = re.search(r'<section class="why-panel".*?</section>', html, re.DOTALL)
    assert why_match is not None
    why_html = why_match.group(0)

    top = sorted(snapshot.predictions, key=lambda e: e.rank)[0]
    assert top.player_name_display in why_html
    assert f"우승확률 {top.win_probability * 100:.2f}%" in why_html
    assert f"예측순위 {top.rank}위" in why_html
    assert f"{top.prior_events_n}회" in why_html


def test_recent_form_10_is_never_described_as_a_per_round_figure(predictions_root, tmp_path):
    """prior_recent_form_10 is a per-EVENT (whole tournament) average,
    not a per-round rate — see point_in_time_features.py's module
    docstring. The page must state this explicitly and must never
    pair the recent-form-10 value with '라운드당'/'per round' framing."""
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")

    assert site_templates.WHY_RECENT_FORM_NOTE_KO in html
    assert "라운드 평균이 아닌" in html
    # The one metric that IS legitimately per-round keeps that label...
    assert site_templates.WHY_LONG_TERM_LABEL_KO in html
    # ...but recent-form-10's own label must never claim "per round."
    why_match = re.search(r'<section class="why-panel".*?</section>', html, re.DOTALL)
    recent_form_block = re.search(
        r"최근 10개 대회 흐름</dt><dd>(.*?)</dd>", why_match.group(0), re.DOTALL
    )
    assert recent_form_block is not None
    assert "라운드당" not in recent_form_block.group(1)


def test_prior_avg_round_score_to_par_is_a_genuine_per_round_rate_by_formula():
    """Ground the WHY section's 'per round' label in the actual
    formula, not an assumption: point_in_time_features.py computes it
    as sum(score_to_par)/sum(rounds_played) — this test fails loudly
    if that source formula's identity ever changes without this test
    (and the label it justifies) being revisited."""
    import inspect as _inspect

    from klpga.backtest import point_in_time_features

    source = _inspect.getsource(point_in_time_features)
    assert "rate_num / rate_den" in source or "sum(e.score_to_par" in source
    assert "avg_round_score_to_par" in source


def test_summary_strip_shows_the_four_required_facts(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")

    strip_match = re.search(r'<div class="summary-strip">.*?</div>\s*</div>', html, re.DOTALL)
    assert strip_match is not None
    strip_html = strip_match.group(0)
    assert f"과거 {snapshot.training_tournament_count}개 대회" in strip_html
    assert site_templates.CORPUS_PLAYER_TOURNAMENT_ROWS_APPROX in strip_html
    assert f"출전선수 {snapshot.field_size}명" in strip_html
    assert "100%" in strip_html


def test_prediction_record_shows_only_the_simplified_public_fields(predictions_root, tmp_path):
    root, snapshot = predictions_root
    result = build_site(root, tmp_path / "dist")
    html = (result.output_root / "index.html").read_text(encoding="utf-8")

    record_match = re.search(r"<summary>Prediction Record</summary>.*?</details>", html, re.DOTALL)
    assert record_match is not None
    record_html = record_match.group(0)

    assert f"Prediction #{snapshot.prediction_id}" in record_html
    assert snapshot.cutoff_date in record_html
    assert "PRE-TOURNAMENT" in record_html
    assert "LOCKED" in record_html
    # No model name/version and no reconstruction/provenance jargon in
    # the simplified public panel — that stays internal to the archive.
    assert "M4" not in record_html
    assert "재구성" not in record_html
    assert "CMD" not in record_html


def test_archive_json_provenance_is_unaffected_by_the_site_build(tmp_path):
    """The exact scenario this stage must never touch: a
    rerun_reconstruction-provenance archive, built into the site,
    must come out of the build with its ORIGINAL archive file
    completely unchanged — full provenance intact on disk, even
    though the public HTML no longer displays it."""
    from klpga.archive.prediction_archive import build_rerun_reconstruction_provenance, read_prediction_snapshot

    provenance = build_rerun_reconstruction_provenance(
        original_run_status="successful_pre_tournament_run_observed",
        original_machine_readable_snapshot_available=False,
        reconstruction_reason="test reconstruction",
        verification={"first_run_top_player_code": "11134"},
    )
    entrants = _sample_entrants()
    snapshot = _snapshot(entrants)
    import dataclasses

    snapshot = dataclasses.replace(snapshot, provenance=provenance)
    root = tmp_path / "predictions"
    json_path, _ = _write_archive(root, snapshot)
    original_bytes = json_path.read_bytes()

    build_site(root, tmp_path / "dist")

    assert json_path.read_bytes() == original_bytes
    reread = read_prediction_snapshot(json_path)
    assert reread.provenance["source"] == "rerun_reconstruction"
    assert reread.provenance["verification"]["first_run_top_player_code"] == "11134"
