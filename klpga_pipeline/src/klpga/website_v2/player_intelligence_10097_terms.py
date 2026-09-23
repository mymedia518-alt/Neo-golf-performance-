"""Single Korean terminology dictionary for the playerCode=10097 Player
Intelligence report -- the ONLY place these words are defined. Both
scripts/build_10097_player_intelligence_report.py (generates the report
content) and player_intelligence_10097_report.py (renders it) import
from here, so the wording is identical everywhere it appears.

Localization, not translation: every label below is natural Korean,
written the way a KLPGA performance analyst would write it for a
Korean player -- never a literal English translation, and never a
heading that mixes a bare English UI label with Korean. Only the
standard golf terms below stay in English, always spelled exactly as
listed: SG, GIR, APP, PUTT, ARG, OTT, Birdie, Bogey, Driver, Iron,
Wedge, Fairway, Green.

The four Strokes Gained components are always written SG-prefixed
("SG APP", not a bare "APP") -- a bare "APP"/"OTT"/"ARG"/"PUTT" reads
ambiguously in Korean prose (e.g. "APP" alone reads as a phone app),
so this report never uses them without the "SG " prefix, for the stat
itself and for the underlying shot category alike. "SG Total" (not in
the source word list) is kept in English too: it is the established
name the frozen Knowledge Engine's own Korean output already uses for
this exact stat (e.g. "SG Total +0.79"), so translating it here would
break consistency with the quoted citations this report reuses
verbatim from that frozen output.
"""
from __future__ import annotations

# SG 세부 항목 라벨 -- 통계 지표와 해당 샷 영역을 가리킬 때 모두 이 표기만 사용합니다.
SG_COMPONENT = {
    "approach": "SG APP",
    "putting": "SG PUTT",
    "off_the_tee": "SG OTT",
    "around_green": "SG ARG",
}
SG_TOTAL = "SG Total"

# 모니터링 프로토콜의 측정 단위
UNIT = {"tournament": "대회", "round": "라운드", "season": "시즌", "appearance": "출전"}

# 현재 상태 칩 라벨
STATUS_LABEL = {"NORMAL": "정상", "WATCH": "관찰 필요", "WARNING": "경고", "AT_FLOOR": "역대 최저치"}

# 지속성 판단 라벨
DURABILITY_LABEL = {
    "LONG_TERM_CHARACTERISTIC": "장기적 특성",
    "RECENT_TREND": "최근 추세 — 시즌이 하나 더 지나면 바뀔 수 있음",
    "CONFIRMED_HISTORICAL_EVENT": "확정된 사실 — 이미 종료된 경기",
}

# 신뢰도 라벨
CONFIDENCE_LABEL = {"HIGH": "높음", "MEDIUM": "중간", "LOW": "낮음", "UNKNOWN": "알 수 없음"}

# 카드 본문 섹션 라벨
SECTION_LABEL = {
    "fact": "사실",
    "evidence": "근거",
    "analysis": "분석",
    "conclusion": "결론",
    "why_it_matters": "왜 중요한가",
    "player_takeaway": "선수 체크포인트",
    "coach_focus": "코치 체크포인트",
    "durability": "지속성",
    "why_this_matters": "핵심 요약",
    "action": "실행 지침",
    "monitoring_protocol": "모니터링 프로토콜",
}

# 근거 점수 / 표본 크기 / 신뢰도 칩 라벨
CHIP_LABEL = {
    "evidence_score": "근거 점수",
    "sample_size": "표본 크기",
    "confidence": "신뢰도",
}

# 모니터링 프로토콜 다섯 항목 + 현재 상태 라벨
PROTOCOL_ROW_LABEL = {
    "metric": "1. 모니터링 지표",
    "source": "데이터 출처",
    "normal_range": "2. 정상 기준",
    "warning_threshold": "3. 저하 기준",
    "next_review": "4. 다음 점검",
    "explanatory_metric": "5. 변화를 가장 잘 설명하는 지표",
}
CURRENT_STATUS_LABEL = "현재 상태"
CURRENT_READING_LABEL = "최근 실측값"
NEXT_REVIEW_LABEL = "다음 점검"

# V5: real SG decomposition, contribution breakdown. "DNA" is already an
# established term in this exact codebase (player_intelligence's own
# player_dna/axes fields), so these three fixed compound labels stay in
# English like the loanwords above -- never a bare "WIN"/"LOSS"/"TREND"
# on its own, only inside these three exact compounds.
WIN_DNA = "WIN DNA"
LOSS_DNA = "LOSS DNA"
TREND_DNA = "TREND DNA"
CONTRIBUTION_LABEL = "기여도 분해"
TOP_CONTRIBUTOR_LABEL = "가장 크게 기여한 요소"
CONTRIBUTION_UNAVAILABLE = "공식 SG 세부 데이터 없음"

# UI 리팩터(Gold Standard): 결론 우선 구조에서 쓰는 라벨.
# "분석 근거"는 fact/evidence/analysis/why_it_matters/선수·코치 체크포인트/
# 지속성/근거 감사 칩/실행 지침(원본 데이터 출처 포함)/모니터링 프로토콜 5개
# 항목 전체를 묶는 하나의 접이식 섹션 제목입니다 -- 이 라벨을 펼치기 전에는
# 원본 파일명, 필드명, 함수 호출 같은 구현 세부사항이 화면에 보이지 않습니다.
EVIDENCE_TOGGLE_LABEL = "분석 근거"

# 페이지 상단 / 섹션 제목
HERO_TITLE = "선수 퍼포먼스 리포트 — 최고 수준 분석"
CHECKLIST_TITLE = "대회 전 모니터링 체크리스트"
CHECKLIST_DESCRIPTION = (
    "모든 모니터링 지표의 상태를 가장 최근 실측값 기준으로 정리했습니다 -- 예측이 아니라 실제 기록을 "
    "점검한 결과입니다. 대회 전에 반드시 확인하십시오."
)
EXCLUDED_TITLE = "검토했지만 답하지 않은 질문"
EXCLUDED_DESCRIPTION = (
    "이 리포트가 실제로 검토했지만 채택하지 않은 질문들입니다. 근거가 이 리포트의 기준을 통과하지 못해 "
    "추측 대신 제외를 선택했습니다."
)
