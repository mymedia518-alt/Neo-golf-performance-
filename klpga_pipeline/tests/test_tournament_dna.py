"""Tests for src/klpga/knowledge_engine/tournament_dna.py (Sprint 4)."""

from __future__ import annotations

import pytest

from klpga.knowledge_engine import tournament_dna as tdna
from klpga.tournament_context import _load_context_from_schedule_and_registry as load_tournament_context


def _row(game_code, tournament, player_id, rank, total, ott, app, arg, putt, season=2024):
    return {
        "game_code": game_code,
        "tournament": tournament,
        "player_id": player_id,
        "rank": rank,
        "season": season,
        "total": total,
        "off_the_tee": ott,
        "approach": app,
        "around_green": arg,
        "putting": putt,
        "scope": "tournament_cumulative",
        "identity_state": "RETAINED",
    }


def _warehouse(rows):
    return {"records": rows}


# ---------------------------------------------------------------------------
# matching_game_codes (reuses knowledge_engine's own token matcher)
# ---------------------------------------------------------------------------


def test_matching_game_codes_finds_same_series():
    warehouse = _warehouse(
        [
            _row("g1", "OK저축은행 읏맨 오픈", "P1", 1, 2.0, 1.0, 0.5, 0.3, 0.2),
            _row("g2", "OK저축은행 읏맨 오픈", "P2", 1, 1.5, 0.5, 0.3, 0.2, 0.5),
        ]
    )
    matched = tdna.matching_game_codes("OK저축은행 읏맨 오픈", warehouse)
    assert set(matched) == {"g1", "g2"}


def test_matching_game_codes_excludes_generic_word_only_match():
    warehouse = _warehouse([_row("g1", "롯데 오픈", "P1", 1, 2.0, 1.0, 0.5, 0.3, 0.2)])
    matched = tdna.matching_game_codes("OK저축은행 읏맨 오픈", warehouse)
    assert matched == ()


def test_matching_game_codes_empty_for_no_name():
    assert tdna.matching_game_codes("", _warehouse([])) == ()


# ---------------------------------------------------------------------------
# compute_course_dna
# ---------------------------------------------------------------------------


def test_compute_course_dna_no_history_returns_empty():
    dna = tdna.compute_course_dna("존재하지 않는 대회", _warehouse([]))
    assert dna.axes == ()
    assert dna.sample_events == 0


def test_compute_course_dna_real_shape():
    warehouse = _warehouse(
        [
            _row("g1", "테스트 오픈", "P1", 1, 3.0, 1.0, 1.0, 0.5, 0.5),
            _row("g1", "테스트 오픈", "P2", 2, 1.0, 0.2, 0.2, 0.1, 0.5),
            _row("g2", "테스트 오픈", "P1", 1, 0.5, -0.5, 0.2, 0.1, 0.7),
            _row("other", "완전히 다른 대회", "P3", 1, -1.0, -0.5, -0.3, -0.1, -0.1),
        ]
    )
    dna = tdna.compute_course_dna("테스트 오픈", warehouse)
    assert dna.sample_events == 2
    assert set(dna.matched_game_codes) == {"g1", "g2"}
    keys = {a.key for a in dna.axes}
    assert keys == {"driving", "iron", "recovery", "putting", "scoring"}
    for a in dna.axes:
        assert 0.0 <= a.percentile <= 100.0


# ---------------------------------------------------------------------------
# compute_winning_profile
# ---------------------------------------------------------------------------


def test_compute_winning_profile_uses_only_rank_1_rows():
    warehouse = _warehouse(
        [
            _row("g1", "테스트 오픈", "WINNER", 1, 3.0, 1.5, 1.0, 0.3, 0.2),
            _row("g1", "테스트 오픈", "LOSER", 2, 1.0, 0.1, 0.1, 0.1, 0.1),
        ]
    )
    profile = tdna.compute_winning_profile("테스트 오픈", warehouse)
    assert len(profile) == 5
    scoring = next(p for p in profile if p.key == "scoring")
    assert scoring.threshold_sg == pytest.approx(3.0)
    assert scoring.sample_size == 1


def test_compute_winning_profile_empty_without_history():
    assert tdna.compute_winning_profile("존재하지 않는 대회", _warehouse([])) == ()


# ---------------------------------------------------------------------------
# compute_field_composition / compute_best_fits (real player_intelligence docs)
# ---------------------------------------------------------------------------


def test_compute_field_composition_real_players():
    entries, unclassified = tdna.compute_field_composition(["10097", "10002"])
    assert unclassified == 0
    assert sum(e.count for e in entries) == 2


def test_compute_field_composition_unclassified_for_missing_player():
    entries, unclassified = tdna.compute_field_composition(["NO_SUCH_PLAYER_XYZ"])
    assert unclassified == 1
    assert entries == ()


def test_compute_best_fits_never_empty_with_real_course_dna_and_players():
    warehouse = tdna.ke.load_warehouse()
    course_dna = tdna.compute_course_dna("OK저축은행 읏맨 오픈", warehouse)
    fits = tdna.compute_best_fits(["10097", "10002", "10725"], course_dna, max_fits=2)
    assert len(fits) <= 2
    for fit in fits:
        assert fit.why  # a real WHY sentence, not just a ranking position


def test_compute_best_fits_empty_without_course_dna():
    empty_dna = tdna.CourseDNA(axes=(), sample_events=0, matched_game_codes=())
    assert tdna.compute_best_fits(["10097"], empty_dna) == ()


# ---------------------------------------------------------------------------
# hole stats / danger / opportunity holes
# ---------------------------------------------------------------------------


def _hole_row(hole, par, relative_to_par):
    return {"hole": hole, "par": par, "relative_to_par": relative_to_par}


def test_compute_hole_stats_requires_minimum_sample():
    rows = [_hole_row(1, 4, 0) for _ in range(2)]  # below MIN_HOLE_SAMPLE
    assert tdna.compute_hole_stats(rows) == ()


def test_compute_hole_stats_real_rates():
    rows = (
        [_hole_row(1, 4, 1) for _ in range(3)]  # 3 bogeys
        + [_hole_row(1, 4, 0) for _ in range(7)]
    )
    stats = tdna.compute_hole_stats(rows)
    assert len(stats) == 1
    assert stats[0].bogey_rate == pytest.approx(30.0)
    assert stats[0].sample == 10


def test_danger_and_opportunity_holes_are_disjoint_by_rate_direction():
    rows = (
        [_hole_row(1, 4, 1) for _ in range(9)] + [_hole_row(1, 4, 0) for _ in range(1)]  # hole 1: mostly bogey
        + [_hole_row(2, 5, -1) for _ in range(9)] + [_hole_row(2, 5, 0) for _ in range(1)]  # hole 2: mostly birdie
    )
    stats = tdna.compute_hole_stats(rows)
    danger = tdna.compute_danger_holes(stats)
    opportunity = tdna.compute_opportunity_holes(stats)
    assert danger[0].hole == 1
    assert opportunity[0].hole == 2


def test_discover_hole_rows_empty_when_no_real_artifact():
    context = load_tournament_context("2026120001")
    assert tdna.discover_hole_rows(context) == []


def test_discover_hole_rows_real_kg_ladies_open():
    context = load_tournament_context("2026080001")
    rows = tdna.discover_hole_rows(context)
    assert len(rows) > 1000
    assert all("hole" in r and "par" in r for r in rows[:5])


# ---------------------------------------------------------------------------
# watch list
# ---------------------------------------------------------------------------


def test_compute_watch_list_real_players_returns_real_deltas():
    watch_list = tdna.compute_watch_list(["10097", "10002", "9784"], max_entries=3)
    assert len(watch_list) <= 3
    for entry in watch_list:
        assert entry.direction in ("개선", "하락")


# ---------------------------------------------------------------------------
# story / verdict
# ---------------------------------------------------------------------------


def test_build_tournament_verdict_max_two_sentences():
    identity = tdna.TournamentIdentity(
        game_code="g1", tournament_name="테스트 오픈", venue="테스트 코스", par=72, holes=54,
        purse=None, cut_after_round=None, field_size=100, sources=(),
    )
    course_dna = tdna.CourseDNA(
        axes=(tdna.CourseDNAAxis(key="putting", label="퍼팅", avg_sg=0.5, percentile=90.0),),
        sample_events=2, matched_game_codes=("g1", "g2"),
    )
    verdict = tdna.build_tournament_verdict(identity, course_dna, ())
    assert verdict.summary.count(".") <= 2
    assert "테스트 오픈" in verdict.summary


def test_build_tournament_story_never_fabricates_without_evidence():
    identity = tdna.TournamentIdentity(
        game_code="g1", tournament_name="새 대회", venue=None, par=None, holes=None,
        purse=None, cut_after_round=None, field_size=None, sources=(),
    )
    empty_dna = tdna.CourseDNA(axes=(), sample_events=0, matched_game_codes=())
    story = tdna.build_tournament_story(identity, empty_dna, (), ())
    assert story == ()  # no real evidence anywhere -- never a fabricated fact


# ---------------------------------------------------------------------------
# Real integration: generate_tournament_dna end to end
# ---------------------------------------------------------------------------


def test_generate_tournament_dna_real_ok_open():
    context = load_tournament_context("2026120001")
    result = tdna.generate_tournament_dna(context)
    assert result.identity.game_code == "2026120001"
    assert result.identity.venue == "포천아도니스"
    assert result.identity.par == 72
    assert result.course_dna.sample_events >= 1
    assert result.field_composition
    assert result.best_fits
    assert result.verdict.summary.count(".") <= 2


def test_generate_tournament_dna_real_kg_ladies_open_has_hole_data():
    context = load_tournament_context("2026080001")
    result = tdna.generate_tournament_dna(context)
    assert result.identity.par == 72
    assert len(result.danger_holes) > 0
    assert len(result.opportunity_holes) > 0
    assert all(h.bogey_rate >= result.danger_holes[-1].bogey_rate for h in result.danger_holes)


def test_to_json_dict_round_trips_real_data():
    context = load_tournament_context("2026120001")
    result = tdna.generate_tournament_dna(context)
    doc = tdna.to_json_dict(result)
    assert doc["identity"]["game_code"] == "2026120001"
    for section in ("course_dna", "winning_profile", "field_composition", "best_fits", "danger_holes", "opportunity_holes", "story", "watch_list", "verdict"):
        assert section in doc


# ---------------------------------------------------------------------------
# No hidden globals / determinism: the same game_code must always
# produce the same TournamentDNA, regardless of which tournament (if
# any) config/active_tournament.json currently names.
# ---------------------------------------------------------------------------


def test_load_tournament_identity_never_reads_cut_after_round():
    """cut_after_round only ever exists in the mutable, currently-
    active-only config/active_tournament.json -- there is no other real
    deterministic per-game_code source for it, so it must always be
    None, never populated by reading that file."""
    context = load_tournament_context("2026120001")
    identity = tdna.load_tournament_identity(context)
    assert identity.cut_after_round is None
    assert not any("active_tournament" in s for s in identity.sources)


def test_generate_tournament_dna_deterministic_regardless_of_active_tournament(monkeypatch, tmp_path):
    """Same game_code, twice, with config/active_tournament.json
    pointing at a DIFFERENT tournament the second time -- must still
    produce byte-identical TournamentDNA content (generated_at aside)."""
    from klpga import tournament_context as tc

    context = load_tournament_context("2026120001")
    doc1 = tdna.to_json_dict(tdna.generate_tournament_dna(context))

    fake_active = tmp_path / "active_tournament.json"
    fake_active.write_text('{"game_code": "2026080001", "tournament_name": "다른 대회"}', encoding="utf-8")
    monkeypatch.setattr(tc, "ACTIVE_TOURNAMENT_PATH", fake_active)

    context2 = load_tournament_context("2026120001")
    doc2 = tdna.to_json_dict(tdna.generate_tournament_dna(context2))

    doc1.pop("generated_at")
    doc2.pop("generated_at")
    assert doc1 == doc2


def test_generate_tournament_dna_deterministic_even_when_this_game_code_is_active(monkeypatch, tmp_path):
    """The reverse case: config/active_tournament.json DOES name this
    exact game_code -- output must still match the never-active-aware
    resolution, since the engine must never depend on that file at all."""
    from klpga import tournament_context as tc

    context_never_active = load_tournament_context("2026120001")
    doc_never_active = tdna.to_json_dict(tdna.generate_tournament_dna(context_never_active))

    fake_active = tmp_path / "active_tournament.json"
    fake_active.write_text(
        '{"game_code": "2026120001", "tournament_name": "OK저축은행 읏맨 오픈", '
        '"season": 2026, "start_date": "2026-09-04", "end_date": "2026-09-06", '
        '"final_round_number": 3, "current_round_number": 3, "cut_after_round": 2}',
        encoding="utf-8",
    )
    monkeypatch.setattr(tc, "ACTIVE_TOURNAMENT_PATH", fake_active)

    context_while_active = load_tournament_context("2026120001")
    doc_while_active = tdna.to_json_dict(tdna.generate_tournament_dna(context_while_active))

    doc_never_active.pop("generated_at")
    doc_while_active.pop("generated_at")
    assert doc_never_active == doc_while_active
