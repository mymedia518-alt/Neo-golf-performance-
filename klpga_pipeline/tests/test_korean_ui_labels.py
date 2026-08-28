"""Tests for klpga.neo_win.korean_ui_labels — pins the exact label
mapping given in the task spec, so a future edit can't silently drift
from the approved Korean text."""
from __future__ import annotations

from klpga.neo_win.korean_ui_labels import (
    BRAND_NAME,
    KOREAN_LABELS,
    ROUND_COMPLETE_STATUS_LABELS,
    STAGE_DISPLAY_LABELS,
)

_EXPECTED = {
    "tournament_prediction": "대회 예측",
    "current_position": "현재 순위",
    "score": "스코어",
    "win_probability": "우승 확률",
    "make_cut": "컷 통과 확률",
    "prediction_history": "우승 확률 변화",
    "tournament_result": "이번 대회 성적",
    "player_data": "선수 데이터",
    "historical_rounds": "과거 데이터",
    "expected_round": "예상 라운드 성적",
    "consistency": "경기력 변동폭",
    "round_condition": "라운드 환경",
    "model_check": "예측 검증",
    "withdrawn": "기권 (WD)",
    "disqualified": "실격 (DQ)",
}


def test_all_spec_examples_present_with_exact_text():
    for key, value in _EXPECTED.items():
        assert KOREAN_LABELS[key] == value


def test_brand_name_stays_english():
    assert BRAND_NAME == "NEO GOLF DATA"


def test_stage_display_labels_keep_r_abbreviations():
    assert STAGE_DISPLAY_LABELS["R1"] == "1R"
    assert STAGE_DISPLAY_LABELS["R2"] == "2R"
    assert STAGE_DISPLAY_LABELS["PRE"] == "대회 전"


def test_round_complete_labels_are_korean():
    assert ROUND_COMPLETE_STATUS_LABELS[1] == "1라운드 종료"
    assert ROUND_COMPLETE_STATUS_LABELS[2] == "2라운드 종료"
