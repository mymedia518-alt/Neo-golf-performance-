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
# "분석 근거"는 이제 감사 자료 묶음이 아니라 Tour Performance Department식
# 5단계 구조(퍼포먼스 분석 -> 핵심 발견 -> 코치의 해석 -> 선수 실행 지침 ->
# 데이터 근거) 전체를 여는 하나의 접이식 섹션 제목입니다. 펼치는 즉시 1~4번은
# 바로 보이고, 원본 파일명/필드명/함수 호출 같은 구현 세부사항은 그 안의
# "데이터 근거" 하위 접이식 섹션을 한 번 더 펼쳐야만 보입니다.
EVIDENCE_TOGGLE_LABEL = "분석 근거"

# V10: 분석 근거 내부 5단계 구조 라벨. 순서를 바꾸지 않습니다 -- 퍼포먼스
# 분석 -> 핵심 발견 -> 코치의 해석 -> 선수 실행 지침 -> 데이터 근거.
PERFORMANCE_ANALYSIS_TITLE = "퍼포먼스 분석"
KEY_FINDINGS_TITLE = "핵심 발견"
COACH_INTERPRETATION_TITLE = "코치의 해석"
PLAYER_ACTION_TITLE = "선수 실행 지침"
DATA_EVIDENCE_TOGGLE_LABEL = "데이터 근거 (원본 출처)"
DECISION_LABEL = "결정"
FULL_PROTOCOL_LABEL = "실행 지침 전체 (모니터링 프로토콜 포함)"

# V12: MECHANISM -> IMPACT -> REPRODUCIBILITY -> COACH DECISION. "mechanism"
# renders inside PERFORMANCE ANALYSIS (why/how, not just what); "why_it_matters"
# already carries IMPACT; "reproducibility" renders next to the PLAYER ACTION
# decision (the condition under which that decision holds); COACH DECISION is
# the existing PLAYER_ACTION_TITLE box. Present only when a question actually
# has a mechanism field -- never rendered as an empty/invented placeholder.
MECHANISM_LABEL = "메커니즘"
REPRODUCIBILITY_LABEL = "재현 조건"
PLAYER_PLAYBOOK_TITLE = "플레이어 플레이북"
PLAYBOOK_CATEGORY_LABEL = {
    "ATTACK": "공략",
    "AVOID": "지양",
    "MONITOR": "모니터링",
    "TRUST": "신뢰",
    "NEVER_CHANGE": "변경 금지",
}
# V13 (Performance Lab): ROOT CAUSE is its own visible step, between
# MECHANISM and COACH INTERPRETATION -- never invented deeper than the
# real data allows; when the true root (swing mechanics, decision
# process) sits below this repository's real data floor, the field says
# so explicitly rather than guessing past it.
ROOT_CAUSE_LABEL = "근본 원인"
PERFORMANCE_LAB_LABEL = "퍼포먼스 랩"
COACH_CONSOLE_TITLE = "코치 콘솔"
COACH_CONSOLE_CATEGORY_LABEL = {
    "KEEP": "유지",
    "CHANGE": "변경",
    "MONITOR": "모니터링",
    "AVOID": "지양",
    "DO_NOT_TOUCH": "손대지 않음",
}
PLAYBOOK_CATEGORY_LABEL_V13 = {
    "ATTACK": "공략",
    "DEFEND": "방어",
    "ACCEPT": "수용",
    "AVOID": "지양",
    "TRUST": "신뢰",
}

# V16: the performance funnel. Golf is not Technique -> Winning; it is
# Technique -> Opportunity -> Conversion -> Competition -> Winning. No
# stage is ever collapsed into a synthetic "efficiency %" -- every number
# stays independently real and directly explainable.
PERFORMANCE_FUNNEL_TITLE = "퍼포먼스 퍼널"
LEAK_MAP_TITLE = "리크 맵 (핵심 손실 지점 3가지)"
LAYER_LABEL = {"TECHNIQUE": "기술", "OPPORTUNITY": "기회 창출", "CONVERSION": "기회 전환", "COMPETITION": "경쟁"}
LEAK_FIELD_LABEL = {"where": "위치", "why": "이유", "performance_loss": "성과 손실", "coach_decision": "코치 결정"}

UNSUPPORTED_MODULES_TITLE = "실측 데이터 없이는 답할 수 없는 분석"
UNSUPPORTED_MODULES_DESCRIPTION = (
    "이 리포트가 다루는 실측 데이터의 최소 단위는 라운드·대회입니다. 아래 분석은 홀 단위, 거리 구간, 핀 위치, "
    "샷 시퀀스, 판단 과정 등 더 세밀한 실측 기록이 있어야 답할 수 있으며, 이 저장소에는 그 기록이 없습니다. "
    "추측 대신 정직한 제외를 선택했습니다."
)

# V17: UNKNOWN is a roadmap, not a dead end. Every distinct root cause
# behind this report's UNKNOWN markers and unsupported modules is one
# concrete future data-acquisition task here -- what is missing, how it
# could be collected, and how many currently-UNKNOWN items it would
# resolve (a real, computed count -- never an invented score).
DATA_ROADMAP_TITLE = "데이터 로드맵 (NEO 인텔리전스 엔진의 다음 확장 과제)"
DATA_ROADMAP_DESCRIPTION = (
    "UNKNOWN은 분석의 끝이 아니라 다음에 무엇을 수집해야 하는지를 알려주는 로드맵입니다. 아래는 이 리포트의 "
    "모든 UNKNOWN·미지원 분석이 실제로 어떤 데이터 부재에서 비롯되는지를 근본 원인별로 묶고, 확보 방법과 "
    "해결 시 전환되는 항목 수를 명시한 것입니다."
)
DATA_ROADMAP_FIELD_LABEL = {
    "missing_data": "무엇이 없는가",
    "why_missing": "왜 없는가",
    "collection_method": "어떻게 확보할 수 있는가",
    "value": "얼마나 가치 있는가",
    "unlocks": "해결 시 전환되는 항목",
}

# NEO 운영 원칙: NEO는 샷을 평가하지 않습니다. NEO는 그 샷을 만든 결정을
# 평가합니다. 모든 스코어는 일련의 결정이 낳은 결과입니다. 이 리포트는
# 어떤 결정이 성과를 만들었는지, 어떤 결정이 성과를 무너뜨렸는지, 다음
# 대회 전에 어떤 결정이 바뀌어야 하는지를 항상 함께 제시합니다 -- 결과만
# 놓고 평가하지 않습니다.
#
# 단, 결정은 실측 데이터로 관찰되거나 강하게 추론될 수 있을 때만 평가
# 대상입니다. 관찰되지 않은 결정을 사실처럼 서술하지 않습니다: 데이터가
# 결과만 뒷받침하면 결과를, 메커니즘을 뒷받침하면 메커니즘을, 결정을
# 뒷받침하면 결정을 분석합니다. 그 외에는 UNKNOWN으로 표시합니다. 이
# 저장소에는 전략·클럽 선택 등 결정 자체를 직접 기록한 데이터가 없으므로
# (이미 공개된 "Decision Quality" 미지원 모듈과 동일한 이유), 아래 필드는
# 결정이 실제로 관찰되었다고 주장하지 않고 그 관찰 가능성 자체를
# 정직하게 밝힙니다.
NEO_PRINCIPLE_TITLE = "NEO 원칙"
NEO_PRINCIPLE_TEXT = (
    "NEO는 샷을 평가하지 않습니다. NEO는 결정을 평가합니다. 모든 샷은 결정에서 시작되고, "
    "모든 스코어는 일련의 결정이 낳은 결과입니다. 이 리포트의 모든 결론은 어떤 결정이 성과를 "
    "만들었는지, 어떤 결정이 성과를 무너뜨렸는지, 다음 대회 전 어떤 결정이 바뀌어야 하는지를 "
    "함께 제시합니다 -- 결과만 두고 평가하지 않습니다. 단, 결정 자체가 실측 데이터로 관찰되거나 "
    "강하게 추론될 때만 결정을 평가합니다 -- 관찰되지 않은 결정은 사실처럼 서술하지 않고 "
    "UNKNOWN으로 표시합니다."
)
DECISION_CONTEXT_LABEL = "결정 관찰 가능성"

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
