"""Korean terminology for the PLAYER HISTORY GOLD STANDARD V1 report
(playerCode=10097 / 김민선7 only). Player Intelligence is no longer the
goal for this player -- this is a dense, table/chart-first career
archive built strictly from verified data. Not a reusable framework."""
from __future__ import annotations

HERO_TITLE = "PLAYER HISTORY"
HERO_SUBTITLE = "실측 기록만으로 재구성한 커리어 아카이브"

PAGE1_TITLE = "1. 커리어 개요"
PAGE2_TITLE = "2. 커리어 진화"
PAGE3_TITLE = "3. 시즌 리플레이"
PAGE4_TITLE = "4. 대회 기록"
PAGE5_TITLE = "5. 라운드 기록"
PAGE6_TITLE = "6. 선수 성장 탐지"
PAGE7_TITLE = "7. 커리어 DNA"
PAGE8_TITLE = "8. 선수 스토리"
PAGE_HOLE_TITLE = "홀 기록 (실측 1개 대회)"
PAGE_SNAPSHOT_TITLE = "현재 시즌 공식 스냅샷"
PAGE_NOT_AVAILABLE_TITLE = "실측되지 않아 제외한 항목"

SEASON_TABLE_COLUMNS = {
    "season": "시즌", "events": "대회", "wins": "우승", "top10": "상위10위",
    "sg_total": "SG Total", "sg_ott": "SG OTT", "sg_app": "SG APP", "sg_arg": "SG ARG", "sg_putt": "SG PUTT",
    "sg_sample_size": "SG 표본",
}

DIRECTION_LABEL = {"UP": "상승", "DOWN": "하락", "FLAT": "보합"}

TOURNAMENT_COLUMNS = {
    "season": "시즌", "tournament": "대회", "rank": "최종 순위", "sg_total": "SG Total",
    "ott": "SG OTT", "app": "SG APP", "arg": "SG ARG", "putt": "SG PUTT",
}

DECISION_NONE_TEXT = "실측 데이터에 없음 -- 표시하지 않습니다."
