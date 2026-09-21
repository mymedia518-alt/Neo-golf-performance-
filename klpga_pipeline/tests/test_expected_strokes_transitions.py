"""Tests for klpga.expected_strokes.transitions -- Phase 1: transition
dataset construction, state-continuity checking, lie taxonomy, and
distribution helpers. Uses a small synthetic in-memory shot_event/
hole_audit DB (never the real 2026090002 data, unreachable from this
sandbox) built with the SAME schema collect_cmpro_shots.SCHEMA defines,
so these tests prove correctness of the logic against realistic shapes."""
from __future__ import annotations

import sqlite3

import pytest

from klpga.expected_strokes.transitions import (
    LIE_TAXONOMY,
    RAW_LIE_VALUES_FROM_PARSER,
    build_transition_dataset,
    check_state_continuity,
    distance_stats,
    lie_distribution,
    par_distribution,
    taxonomy_gaps,
)
from scripts.collect_cmpro_shots import SCHEMA


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def _insert(conn, game, player_code, player_name, rnd, hole, shot_no, sdist, slie, edist, elie, qa="PASS"):
    conn.execute(
        "INSERT INTO shot_event VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (game, player_code, player_name, rnd, hole, shot_no, sdist, slie, abs((sdist or 0) - edist), edist, elie, "h", "t", qa),
    )


def test_build_transition_dataset_real_shape_and_ordering():
    conn = _make_conn()
    # hole 1: 2 shots, continuous, holed on shot 2
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 150.0, "페어웨이")
    _insert(conn, "G", "P1", "선수1", 1, 1, 2, 150.0, "페어웨이", 0.0, "홀인")
    conn.commit()

    rows = build_transition_dataset(conn, "G")
    assert len(rows) == 2
    assert rows[0].shot_no == 1 and rows[1].shot_no == 2
    assert rows[0].par is None and rows[0].official_hole_score is None  # no evidence supplied
    assert rows[1].holed is True
    assert rows[0].holed is False


def test_build_transition_dataset_applies_supplied_par_and_official_score():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 0.0, "홀인")
    conn.commit()
    rows = build_transition_dataset(
        conn, "G",
        par_by_round_hole={(1, 1): 4},
        official_score_by_player_round_hole={("선수1", 1, 1): 4},
    )
    assert rows[0].par == 4
    assert rows[0].official_hole_score == 4


def test_check_state_continuity_flags_real_mismatch_not_shot_one():
    conn = _make_conn()
    # shot 2's start doesn't match shot 1's end -- a real mismatch
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 150.0, "페어웨이")
    _insert(conn, "G", "P1", "선수1", 1, 1, 2, 140.0, "러프", 0.0, "홀인")  # should have been 150.0/페어웨이
    conn.commit()
    rows = build_transition_dataset(conn, "G")
    mismatches = check_state_continuity(rows)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.shot_no == 2
    assert m.reason == "distance+lie"
    assert m.previous_end_distance == 150.0
    assert m.current_start_distance == 140.0


def test_check_state_continuity_never_flags_shot_one():
    conn = _make_conn()
    # two separate holes, each starting fresh -- shot_no==1 rows must
    # never be compared against the previous hole's last shot.
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 0.0, "홀인")
    _insert(conn, "G", "P1", "선수1", 1, 2, 1, None, "티", 0.0, "홀인")
    conn.commit()
    rows = build_transition_dataset(conn, "G")
    assert check_state_continuity(rows) == []


def test_check_state_continuity_resets_across_players_and_rounds():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 150.0, "페어웨이")
    _insert(conn, "G", "P2", "선수2", 1, 1, 1, None, "티", 0.0, "홀인")  # different player -- not a mismatch vs P1
    conn.commit()
    rows = build_transition_dataset(conn, "G")
    assert check_state_continuity(rows) == []


def test_taxonomy_gaps_real_values_all_covered():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 150.0, "페어웨이")
    _insert(conn, "G", "P1", "선수1", 1, 1, 2, 150.0, "페어웨이", 0.0, "홀인")
    conn.commit()
    gaps = taxonomy_gaps(conn, "G")
    assert gaps["unmapped_values"] == []
    assert "티" in gaps["distinct_start_lie"]
    assert "홀인" in gaps["distinct_end_lie"]


def test_taxonomy_gaps_flags_a_real_unrecognized_value():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 30.0, "카트도로")  # not in RAW_LIE_VALUES_FROM_PARSER
    conn.commit()
    gaps = taxonomy_gaps(conn, "G")
    assert "카트도로" in gaps["unmapped_values"]


def test_raw_lie_values_from_parser_matches_live_collector_literals():
    from klpga.collectors.cmpro_shots import parse_cmpro_shots
    sample = '<div class="map-playertext">SHOT 1 비거리 100.0 yds / 벙커 / 남은거리 10.0 yds</div>'
    shots = parse_cmpro_shots(sample)
    assert shots[0].end_lie in RAW_LIE_VALUES_FROM_PARSER
    assert shots[0].start_lie in RAW_LIE_VALUES_FROM_PARSER


def test_lie_distribution_groups_by_raw_lie_and_reports_percentiles():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 150.0, "페어웨이")
    _insert(conn, "G", "P1", "선수1", 1, 1, 2, 150.0, "페어웨이", 60.0, "그린")
    _insert(conn, "G", "P1", "선수1", 2, 1, 1, None, "티", 140.0, "페어웨이")
    conn.commit()
    rows = build_transition_dataset(conn, "G")
    dist = lie_distribution(rows)
    assert "티" not in dist  # start_distance_yd is None for tee shots -- excluded entirely, never coerced to 0
    assert dist["페어웨이"]["shots"] == 1
    assert dist["페어웨이"]["min"] == 150.0


def test_par_distribution_reports_unknown_when_no_par_supplied():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 0.0, "홀인")
    conn.commit()
    rows = build_transition_dataset(conn, "G")
    dist = par_distribution(rows)
    assert dist["par_unknown_shots"] == 1
    assert dist["by_par"] == {}


def test_par_distribution_buckets_when_par_supplied():
    conn = _make_conn()
    _insert(conn, "G", "P1", "선수1", 1, 1, 1, None, "티", 0.0, "홀인")
    _insert(conn, "G", "P1", "선수1", 1, 2, 1, None, "티", 0.0, "홀인")
    conn.commit()
    rows = build_transition_dataset(conn, "G", par_by_round_hole={(1, 1): 4, (1, 2): 3})
    dist = par_distribution(rows)
    assert dist["by_par"] == {"par_3": 1, "par_4": 1}
    assert dist["par_unknown_shots"] == 0


def test_distance_stats_empty_and_nonempty():
    assert distance_stats([])["shots"] == 0
    stats = distance_stats([10.0, 20.0, 30.0, 40.0])
    assert stats["shots"] == 4
    assert stats["min"] == 10.0
    assert stats["max"] == 40.0
    assert stats["median"] == 25.0
