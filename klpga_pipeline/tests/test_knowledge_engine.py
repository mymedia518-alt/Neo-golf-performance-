"""Tests for the NEO Knowledge Engine (src/klpga/knowledge_engine)."""

from __future__ import annotations

import re

import pytest

from klpga.knowledge_engine import knowledge_engine as ke
from klpga.knowledge_engine import knowledge_rules as rules


# ---------------------------------------------------------------------------
# field_percentile
# ---------------------------------------------------------------------------


def test_field_percentile_higher_is_better():
    population = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert ke.field_percentile(5.0, population) == 100.0
    assert ke.field_percentile(1.0, population) == 20.0
    assert ke.field_percentile(3.0, population) == 60.0


def test_field_percentile_lower_is_better():
    population = [70.0, 71.0, 72.0, 73.0, 74.0]
    # best possible score (lowest) beats itself plus every other member
    assert ke.field_percentile(70.0, population, lower_is_better=True) == 100.0
    assert ke.field_percentile(74.0, population, lower_is_better=True) == 20.0


def test_field_percentile_empty_population_returns_none():
    assert ke.field_percentile(1.0, [], lower_is_better=False) is None


def test_field_percentile_none_value_returns_none():
    assert ke.field_percentile(None, [1.0, 2.0]) is None


# ---------------------------------------------------------------------------
# compute_season_profiles
# ---------------------------------------------------------------------------


def _warehouse_row(player_id, season, game_code, total, ott, app, arg, putt, scope="tournament_cumulative", identity_state="RETAINED", tournament="테스트 오픈"):
    return {
        "player_id": player_id,
        "season": season,
        "game_code": game_code,
        "tournament": tournament,
        "total": total,
        "off_the_tee": ott,
        "approach": app,
        "around_green": arg,
        "putting": putt,
        "scope": scope,
        "identity_state": identity_state,
    }


def test_compute_season_profiles_averages_within_season():
    warehouse = {
        "records": [
            _warehouse_row("P1", 2024, "2024010001", 1.0, 0.5, 0.2, 0.1, 0.2),
            _warehouse_row("P1", 2024, "2024020001", 3.0, 1.5, 0.6, 0.3, 0.6),
            _warehouse_row("P1", 2025, "2025010001", 2.0, 1.0, 0.4, 0.2, 0.4),
        ]
    }
    profiles = ke.compute_season_profiles("P1", warehouse)
    assert [p.season for p in profiles] == [2024, 2025]
    assert profiles[0].n_tournaments == 2
    assert profiles[0].avg_total == pytest.approx(2.0)
    assert profiles[1].avg_total == pytest.approx(2.0)


def test_compute_season_profiles_ignores_other_players_and_non_cumulative_rows():
    warehouse = {
        "records": [
            _warehouse_row("P1", 2024, "2024010001", 1.0, 0.5, 0.2, 0.1, 0.2),
            _warehouse_row("P2", 2024, "2024010001", 9.0, 9.0, 9.0, 9.0, 9.0),
            _warehouse_row("P1", 2024, "2024020001", 5.0, 5.0, 5.0, 5.0, 5.0, scope="single_round"),
            _warehouse_row("P1", 2024, "2024030001", 5.0, 5.0, 5.0, 5.0, 5.0, identity_state="UNRESOLVED_IDENTITY"),
        ]
    }
    profiles = ke.compute_season_profiles("P1", warehouse)
    assert len(profiles) == 1
    assert profiles[0].n_tournaments == 1
    assert profiles[0].avg_total == pytest.approx(1.0)


def test_compute_season_profiles_caps_at_max_seasons():
    warehouse = {
        "records": [
            _warehouse_row("P1", season, f"{season}010001", 1.0, 0.5, 0.2, 0.1, 0.2)
            for season in (2020, 2021, 2022, 2023, 2024)
        ]
    }
    profiles = ke.compute_season_profiles("P1", warehouse, max_seasons=4)
    assert [p.season for p in profiles] == [2021, 2022, 2023, 2024]


def test_season_profile_strongest_weakest_component():
    sp = ke.SeasonProfile(season=2024, n_tournaments=1, avg_total=1.0, avg_ott=0.9, avg_app=-0.2, avg_arg=0.1, avg_putt=0.2)
    assert sp.strongest_component == "avg_ott"
    assert sp.weakest_component == "avg_app"


# ---------------------------------------------------------------------------
# find_course_history
# ---------------------------------------------------------------------------


def test_find_course_history_matches_same_series():
    warehouse = {
        "records": [
            _warehouse_row("P1", 2023, "2023010001", 1.5, 0.5, 0.5, 0.2, 0.3, tournament="OK저축은행 읏맨 오픈"),
            _warehouse_row("P1", 2024, "2024010001", -1.0, -0.5, -0.2, -0.1, -0.2, tournament="OK저축은행 읏맨 오픈"),
        ]
    }
    history = ke.find_course_history("P1", warehouse, "OK저축은행 읏맨 오픈")
    assert len(history) == 2
    assert {h["season"] for h in history} == {2023, 2024}


def test_find_course_history_no_false_positive_on_generic_word_only():
    """'롯데 오픈' and 'OK저축은행 읏맨 오픈' only share the generic word '오픈'."""
    warehouse = {
        "records": [
            _warehouse_row("P1", 2023, "2023010001", 1.5, 0.5, 0.5, 0.2, 0.3, tournament="롯데 오픈"),
        ]
    }
    history = ke.find_course_history("P1", warehouse, "OK저축은행 읏맨 오픈")
    assert history == []
    assert "롯데 오픈" not in str(history)


def test_find_course_history_excludes_other_players_rows():
    warehouse = {
        "records": [
            _warehouse_row("P1", 2023, "2023010001", 1.5, 0.5, 0.5, 0.2, 0.3, tournament="OK저축은행 읏맨 오픈"),
            _warehouse_row("P2", 2024, "2024010001", 9.0, 9.0, 9.0, 9.0, 9.0, tournament="OK저축은행 읏맨 오픈"),
        ]
    }
    history = ke.find_course_history("P1", warehouse, "OK저축은행 읏맨 오픈")
    assert len(history) == 1
    assert history[0]["season"] == 2023


def test_find_course_history_empty_when_no_tournament_name():
    warehouse = {"records": [_warehouse_row("P1", 2023, "2023010001", 1.5, 0.5, 0.5, 0.2, 0.3)]}
    assert ke.find_course_history("P1", warehouse, None) == []


# ---------------------------------------------------------------------------
# classify_player_type
# ---------------------------------------------------------------------------


def _evidence(**overrides):
    base = dict(
        player_id="P1",
        player_name="테스트 선수",
        season_profiles=[],
        current_season=2025,
        current_season_components={},
        current_season_rate_stats={},
        field_percentiles={},
        recent_5_sg=None,
        recent_10_sg=None,
        long_term_sg=None,
        volatility=None,
        sample_count=0,
        course_history=[],
        career_avg_total_sg=None,
        sources=(),
    )
    base.update(overrides)
    return ke.Evidence(**base)


def test_classify_player_type_precision_ball_striker_fires():
    evidence = _evidence(field_percentiles={"sg_app": 80.0, "sg_ott": 78.0})
    result = ke.classify_player_type(evidence)
    assert result.key == "precision_ball_striker"
    assert result.citations


def test_classify_player_type_balanced_fallback():
    evidence = _evidence(field_percentiles={"sg_app": 50.0, "sg_ott": 50.0})
    result = ke.classify_player_type(evidence)
    assert result.key == "balanced"


def test_classify_player_type_recovery_specialist_requires_both_metrics():
    # only sg_arg strong, recovery_rate missing -> must not fire
    evidence = _evidence(field_percentiles={"sg_arg": 90.0})
    result = ke.classify_player_type(evidence)
    assert result.key != "recovery_specialist"

    evidence2 = _evidence(field_percentiles={"sg_arg": 90.0, "recovery_rate": 85.0})
    result2 = ke.classify_player_type(evidence2)
    assert result2.key == "recovery_specialist"


# ---------------------------------------------------------------------------
# generate_why_wins / generate_why_loses
# ---------------------------------------------------------------------------


def test_generate_why_wins_caps_at_three():
    evidence = _evidence(
        field_percentiles={
            "sg_total": 95.0,
            "sg_ott": 95.0,
            "sg_app": 95.0,
            "sg_arg": 95.0,
            "sg_putt": 95.0,
            "birdie_rate": 95.0,
            "gir_rate": 95.0,
            "par_save_rate": 95.0,
            "par_break_rate": 95.0,
            "recovery_rate": 95.0,
        }
    )
    reasons = ke.generate_why_wins(evidence, max_reasons=3)
    assert len(reasons) == 3


def test_generate_why_wins_prefers_structural_over_generic_elite():
    seasons = [
        ke.SeasonProfile(season=2023, n_tournaments=5, avg_total=1.0, avg_ott=0.1, avg_app=0.9, avg_arg=0.1, avg_putt=0.1),
        ke.SeasonProfile(season=2024, n_tournaments=5, avg_total=1.0, avg_ott=0.1, avg_app=0.9, avg_arg=0.1, avg_putt=0.1),
    ]
    evidence = _evidence(season_profiles=seasons, field_percentiles={"sg_app": 95.0})
    reasons = ke.generate_why_wins(evidence, max_reasons=3)
    assert len(reasons) == 1
    assert "연속" in reasons[0].text  # structural phrasing, not the generic "엘리트 수준" phrasing


def test_generate_why_wins_empty_when_nothing_fires():
    evidence = _evidence(field_percentiles={"sg_total": 50.0})
    assert ke.generate_why_wins(evidence) == ()


def test_generate_why_loses_empty_when_nothing_fires():
    evidence = _evidence(field_percentiles={"sg_total": 50.0})
    assert ke.generate_why_loses(evidence) == ()


def test_generate_why_loses_structural_weakness():
    seasons = [
        ke.SeasonProfile(season=2023, n_tournaments=5, avg_total=-1.0, avg_ott=-0.9, avg_app=-0.1, avg_arg=-0.1, avg_putt=-0.1),
        ke.SeasonProfile(season=2024, n_tournaments=5, avg_total=-1.0, avg_ott=-0.9, avg_app=-0.1, avg_arg=-0.1, avg_putt=-0.1),
    ]
    evidence = _evidence(season_profiles=seasons, field_percentiles={"sg_ott": 10.0})
    reasons = ke.generate_why_loses(evidence, max_reasons=3)
    assert len(reasons) == 1
    assert "구조적 약점" in reasons[0].text


# ---------------------------------------------------------------------------
# generate_evolution
# ---------------------------------------------------------------------------


def test_generate_evolution_insufficient_sample():
    evidence = _evidence(season_profiles=[ke.SeasonProfile(season=2025, n_tournaments=1, avg_total=1.0, avg_ott=0.1, avg_app=0.1, avg_arg=0.1, avg_putt=0.1)])
    result = ke.generate_evolution(evidence)
    assert result.status == "INSUFFICIENT_SAMPLE"


def test_generate_evolution_real_deltas():
    seasons = [
        ke.SeasonProfile(season=2023, n_tournaments=5, avg_total=0.5, avg_ott=0.1, avg_app=0.1, avg_arg=0.1, avg_putt=0.1),
        ke.SeasonProfile(season=2024, n_tournaments=5, avg_total=1.5, avg_ott=0.2, avg_app=0.2, avg_arg=0.2, avg_putt=0.2),
    ]
    evidence = _evidence(season_profiles=seasons)
    result = ke.generate_evolution(evidence)
    assert result.status == "OK"
    assert result.steps[1].delta_from_prev == pytest.approx(1.0)
    assert "상승" in result.narrative


# ---------------------------------------------------------------------------
# generate_if_today
# ---------------------------------------------------------------------------


def test_generate_if_today_omits_course_scenario_without_history():
    evidence = _evidence(course_history=[])
    scenarios = ke.generate_if_today(evidence)
    assert not any("대회 시리즈" in s.condition for s in scenarios)


def test_generate_if_today_includes_course_scenario_with_history():
    evidence = _evidence(course_history=[{"game_code": "g1", "tournament": "OK저축은행 읏맨 오픈", "season": 2024, "sg_total": 2.0}])
    scenarios = ke.generate_if_today(evidence)
    assert any("OK저축은행 읏맨 오픈" in s.condition and "대회 시리즈" in s.condition for s in scenarios)


def test_generate_if_today_caps_at_three():
    evidence = _evidence(
        course_history=[{"game_code": "g1", "tournament": "테스트 오픈", "season": 2024, "sg_total": 2.0}],
        recent_5_sg=3.0,
        long_term_sg=1.0,
        season_profiles=[
            ke.SeasonProfile(season=2023, n_tournaments=5, avg_total=-1.0, avg_ott=-0.9, avg_app=0.1, avg_arg=0.1, avg_putt=0.1),
            ke.SeasonProfile(season=2024, n_tournaments=5, avg_total=1.0, avg_ott=0.5, avg_app=0.1, avg_arg=0.1, avg_putt=0.1),
        ],
    )
    scenarios = ke.generate_if_today(evidence, max_scenarios=3)
    assert len(scenarios) <= 3


# ---------------------------------------------------------------------------
# generate_player_intelligence / to_json_dict round trip
# ---------------------------------------------------------------------------


def test_generate_player_intelligence_and_to_json_dict_round_trip():
    intel = ke.generate_player_intelligence("10097", tournament_context={"tournament_name": "OK저축은행 읏맨 오픈"})
    doc = ke.to_json_dict(intel)
    assert doc["player_id"] == "10097"
    assert doc["player_type"]["key"]
    assert isinstance(doc["why_wins"], list)
    assert isinstance(doc["why_loses"], list)
    assert doc["evolution"]["status"] in ("OK", "INSUFFICIENT_SAMPLE")
    assert isinstance(doc["if_today"], list)
    assert doc["sources"]
    assert doc["generated_at"]


def test_never_fabricates_missing_evidence_as_zero():
    """A player absent from every source file must not silently get zeroed-out stats."""
    evidence = ke.build_evidence("NO_SUCH_PLAYER_ID")
    assert evidence.field_percentiles == {}
    assert evidence.season_profiles == []
    assert evidence.recent_5_sg is None
    assert evidence.long_term_sg is None


def test_render_text_contains_no_markup():
    intel = ke.generate_player_intelligence("10097", tournament_context={"tournament_name": "OK저축은행 읏맨 오픈"})
    text = ke.render_text(intel)
    assert not re.search(r"<[a-zA-Z/][^>]*>", text)
    assert "<html" not in text.lower()


# ---------------------------------------------------------------------------
# Real integration smoke test (player 10097)
# ---------------------------------------------------------------------------


def test_integration_player_10097_precision_ball_striker_no_lotte_open_leak():
    intel = ke.generate_player_intelligence("10097", tournament_context={"tournament_name": "OK저축은행 읏맨 오픈"})
    assert intel.player_type.key == "precision_ball_striker"
    doc = ke.to_json_dict(intel)
    assert "롯데 오픈" not in str(doc)
