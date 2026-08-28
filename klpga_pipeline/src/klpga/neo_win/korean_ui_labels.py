"""NEO GOLF DATA — Korean-first UI labels (task: "KOREAN UI + PLAYER
CARD MVP"). A plain data module: label text only, no rendering logic
and no model/prediction logic. Internationally-familiar golf/data
abbreviations are kept as-is (WIN%, R1/R2/R3, SG, WD, DQ, Brier Score);
brand names and proper nouns (NEO GOLF DATA) are never translated.
"""
from __future__ import annotations

KOREAN_LABELS: dict[str, str] = {
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
    "data_sample": "데이터 표본",
    "why_probability": "왜 이 우승 확률일까?",
    "cut_passed": "컷 통과",
    "cut_missed": "컷 탈락",
    "withdrawn": "기권 (WD)",
    "disqualified": "실격 (DQ)",
    "pre_stage": "대회 전",
}
"""english_key -> Korean UI text, per the task's own examples (section 1)
plus the same-pattern additions the rest of this task's spec explicitly
uses (data_sample/why_probability/cut states/pre_stage). Every key here
traces to an explicit example in the task; nothing invented beyond it."""

STAGE_DISPLAY_LABELS: dict[str, str] = {
    "PRE": "대회 전",
    "R1": "1R",
    "R2": "2R",
    "R3": "3R",
}
"""Stage code -> the short label used in probability-history rows
(section 4's own example: "대회 전 → 1R → 2R")."""

ROUND_COMPLETE_STATUS_LABELS: dict[int, str] = {1: "1라운드 종료", 2: "2라운드 종료", 3: "3라운드 종료"}
"""Status-pill text for a completed round — same "OO라운드 종료" pattern
as STAGE_DISPLAY_LABELS's "1R"/"2R", written out in full for the
header pill (analogous to the existing "Round 1 Complete" pill text,
never a mechanical word-for-word translation of that English string)."""

BRAND_NAME = "NEO GOLF DATA"
"""Proper noun — never translated, per the task's own explicit rule."""
