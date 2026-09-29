"""Korean terminology for the NEO PLAYER PROFILE V2 report. Not a
database viewer, not a warehouse browser, not a report -- a profile a
golfer can read in 30 seconds and understand "what kind of player is
this, right now?"

MISSION "PLAYER COMPARISON, ARCHITECTURE FIRST" (2026-09-28): every
label below is generic UI copy (a section title, a column header, a
template sentence with real values interpolated in) -- none of it was
ever a fact about playerCode=10097 specifically, so nothing in this
file needed to change to serve any other player through the same
engine (player_history_report.py). Kim Min-seon 7's own facts live only
in her real PLAYER_HISTORY.json, never here.

MISSION NEO PLAYER PROFILE V2 (2026-09-27) replaced the earlier NEO
PLAYER BIOGRAPHY V4 11-section numbering with an 8-question flow.
Every numbered section must answer exactly one of these questions; a
section that cannot is either merged into one that can or demoted to
an unnumbered subordinate block. No new data, section, chart, metric,
JSON field, or SQLite table was introduced to do this -- every real
number below already existed in PLAYER_HISTORY.json before this
mission; only what is SHOWN, and in what order, changed.

Page numbering (NEO PLAYER PROFILE V2, 2026-09-27):
  1 현재 폼 (현재 얼마나 잘 치는가?) -- understandable without
    scrolling; no table, no complex chart
  2 왜 지금인가 (왜 잘 치는가?) -- one sentence, then component arrows
  3 최근 경기 결과 (최근 어떤 흐름인가?) -- one flowing 최근 20 view
    (5 open + 6-20th nested), never three separate tables;
    진행 중인 대회 (Live Tournament) nests here ONLY when actually
    confirmed live, otherwise hidden completely
  4 선수 정체성 (어떤 유형의 선수인가?) -- conclusion + two supporting
    lines, nothing more
  5 코스 프로필 (어떤 대회에서 강한가?) -- bar chart, Top3/Bottom3,
    full list behind "더보기"
  6 라운드 분석 (언제 잘 치는가?) -- her single best and worst real
    round only, paired as one conclusion; the rest of round_history's
    already-computed extremes (가장 안정적인 대회/최다 향상 라운드/
    최대 붕괴) are supporting detail, relocated to #8 -- a flat
    five-row "database" enumeration is exactly what this section must
    not be
  7 커리어 스토리 (커리어는 어떻게 변했는가?) -- every historical
    chart this page has (career story told backwards, season
    evolution, season replay, career form story/rolling trend,
    2025 technical stats, tournament timeline, DNA radar, DNA summary)
    nests here as one cluster of unnumbered subordinate blocks --
    real, allowed, but never more prominent than the first screen
  8 데이터베이스 / 검증 (Raw Data) -- collapsed, always last;
    everything technical (warehouse, reconciliation, coverage,
    unknowns, career heartbeat, DNA growth-velocity/acceleration/
    stability, and round_history's relocated extra facts) lives ONLY
    here

Every non-numbered block is a subordinate block nested beside the
numbered section it elaborates -- never numbered on its own, so the
visible page never contradicts this 8-item hierarchy."""
from __future__ import annotations

HERO_TITLE = "PLAYER HISTORY"
# NEO V3 BRAND CONSISTENCY mission (2026-09-29): "Remove every
# remaining storytelling sentence... the page must resemble a
# Bloomberg Terminal / Opta / Statcast / DataGolf product rather than a
# sports article." "스토리" (story) framing removed from the hero
# subtitle; the real claim (only measured records, nothing estimated)
# survives without it.
HERO_SUBTITLE = "실측 기록 전용 선수 리포트"

# MISSION V72 (2026-09-28): "Remove section numbering (1,2,3...). The
# page should read as a continuous story, not seven independent
# reports." Numbering stripped from every title Player History itself
# renders; the Data Quality page's own PAGE_RECONCILIATION_TITLE below
# is untouched -- that page is a different, sanctioned technical report
# (per MISSION V50/V61), not part of this page's continuous story.
PAGE_CURRENT_FORM_TITLE = "현재 폼"
PAGE_WHY_NOW_TITLE = "Performance Drivers"  # NEO V3: was "왜 지금인가"
PAGE_RECENT_RESULTS_TITLE = "최근 경기 결과"
PAGE_IN_PROGRESS_TITLE = "진행 중인 대회"  # subordinate to 최근 경기 결과, only when is_confirmed_live -- otherwise hidden completely
PAGE_PLAYER_IDENTITY_TITLE = "Player Profile"  # NEO V3: was "선수 정체성"
PAGE_COURSE_PROFILE_TITLE = "코스 프로필"
PAGE5_TITLE = "라운드 분석"
PAGE_HOLE_TITLE = "홀 기록 (실측 1개 대회)"  # subordinate to 라운드 분석
PAGE_ROUND_HISTORY_DETAIL_TITLE = "라운드 세부 기록"  # relocated to Data Quality page's raw-data cluster
PAGE_CAREER_STORY_TITLE = "Career Timeline"  # NEO V3: was "커리어 스토리"
PAGE2_TITLE = "시즌 변화"  # subordinate to #7 (MISSION V13: demoted, no longer its own numbered section)
PAGE3_TITLE = "시즌 리플레이"  # subordinate to #7 (season_replay)
PAGE_TECHNICAL_STATS_TITLE = "2025시즌 기술 기록"  # subordinate to #7 (technical_stats_2025)
PAGE_TOURNAMENT_TREND_TITLE = "대회 타임라인"  # subordinate to #7 (MISSION V13: demoted)
PAGE4_TITLE = "전체 대회 기록"  # subordinate to #7 (collapsed table)
PAGE_PLAYER_DNA_RADAR_TITLE = "Performance Profile"  # NEO V3: was "플레이어 DNA". subordinate to #7 (MISSION V13: demoted)
PAGE_SNAPSHOT_TITLE = "현재 시즌 공식 스냅샷"  # subordinate to #1 (current form)
PAGE_RECONCILIATION_TITLE = "8. 데이터베이스 / 검증"
PAGE_NOT_AVAILABLE_TITLE = "실측되지 않아 제외한 항목"  # nested inside #8
PAGE_COVERAGE_MATRIX_TITLE = "시즌별 데이터 커버리지"  # nested inside #8
PAGE_DATA_CONFIDENCE_TITLE = "데이터 신뢰도"  # NEO V3: was "이 페이지, 얼마나 믿을 수 있나요". nested inside #8 (MISSION V11, 2026-09-25)
PAGE_DATA_CONFIDENCE_ROADMAP_TITLE = "앞으로 추가될 항목"  # nested inside the block above
PAGE_DATA_QUALITY_TIMELINE_TITLE = "시즌별 확인 비율"  # NEO V3: was "시즌별로 얼마나 확인할 수 있나요". nested inside the block above
PAGE_TOURNAMENT_TABLE_EXPAND_LABEL = "전체 대회 기록 보기"

# Three explicit source states (RED TEAM mission A). "BLOCKED" in the
# season coverage matrix must NEVER read as "데이터 없음" -- that
# literally claims KLPGA doesn't have it, which is exactly the
# conflation this mission exists to eliminate. Every label here says,
# in plain Korean, who is responsible for the gap (NEO's pipeline vs.
# an unverifiable network block vs. a confirmed absence) instead of
# implying KLPGA-side non-existence.
RADAR_STATUS_LABEL = {
    "MEASURED": "실측",
    "DERIVED": "산출",
    "NOT_COLLECTED": "NEO 미수집",
    "BLOCKED": "미확인 (네트워크 차단)",
}

# Public-facing translation of the three internal states named in the
# mission (AVAILABLE_AND_COLLECTED / AVAILABLE_BUT_NOT_COLLECTED /
# CONFIRMED_UNAVAILABLE). Never used to claim KLPGA lacks a metric
# merely because NEO has not ingested it.
SOURCE_STATE_LABEL = {
    "AVAILABLE_AND_COLLECTED": "실측 완료",
    "AVAILABLE_BUT_NOT_COLLECTED": "KLPGA 게시 가능성 있음 · NEO 미수집",
    "CONFIRMED_UNAVAILABLE": "KLPGA 페이지에도 없음 (확인됨)",
    "SOURCE_BLOCKED": "이번 세션 네트워크 차단으로 확인 불가",
}

# Player DNA axis labels (RED TEAM mission E) -- Korean-only, no
# English internal jargon (TEE/APPROACH/PUTTING/SCORING) in public copy.
RADAR_AXIS_LABEL_KO = {
    "TEE": "티샷",
    "APPROACH": "어프로치",
    "쇼트게임": "쇼트게임",
    "PUTTING": "퍼팅",
    "SCORING": "종합 경기력",
}

PLAYER_DNA_EXPLANATION = (
    "같은 시즌 KLPGA 선수들과 비교한 경기력 백분위입니다. "
    "숫자가 높을수록 해당 영역의 상대적 경기력이 높습니다."
)

RECONCILIATION_LABELS = {
    "total_tournaments": "전체 대회",
    "found_in_warehouse": "SG 웨어하우스에서 발견",
    "found_in_reader": "Reader(리더보드 수집)에서 발견",
    "found_in_live": "실시간 스냅샷에서 발견",
    "merged": "2개 이상 출처 병합",
    "missing": "누락",
    "conflicts_detected": "충돌 발견",
}

SEASON_TABLE_COLUMNS = {
    "season": "시즌", "events": "대회", "wins": "우승", "top5": "Top5", "top10": "Top10", "top20": "Top20",
    "sg_total": "SG Total", "sg_ott": "SG OTT", "sg_app": "SG APP", "sg_arg": "SG ARG", "sg_putt": "SG PUTT",
    "sg_sample_size": "SG 표본",
}

DIRECTION_LABEL = {"UP": "상승", "DOWN": "하락", "FLAT": "보합"}

TOURNAMENT_COLUMNS = {
    "season": "시즌", "tournament": "대회", "rank": "최종 순위", "sg_total": "SG Total",
    "ott": "SG OTT", "app": "SG APP", "arg": "SG ARG", "putt": "SG PUTT",
}

DECISION_NONE_TEXT = "실측 데이터에 없어 표시하지 않습니다."

SG_MISSING_CELL_TEXT = "SG 미수집"
