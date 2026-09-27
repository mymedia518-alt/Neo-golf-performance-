"""MISSION NEO PLAYER PROFILE V2 (2026-09-27), playerCode=10097 only.

"우리는 Player Database를 만드는 것이 아니다. 우리는 골퍼가 선수
이름을 클릭했을 때 30초 안에 '이 선수가 지금 어떤 선수인가'를 이해할
수 있는 페이지를 만든다."

"삭제, 통합, 재배치, 단순화만 허용한다. 한 줄도 새 데이터를 만들지
않는다. 한 줄도 새로운 계산을 만들지 않는다. 이미 계산되어 있는
데이터만 이용한다."

This mission collapsed NEO PLAYER BIOGRAPHY V4's 11-section hierarchy
into an 8-question flow: 코스 프로필 and 라운드 분석 moved up to #5-6
(라운드 분석 reduced to its best/worst pair only); 커리어 스토리 now
leads a #7 cluster that folds in season evolution, tournament
timeline, and Player DNA as unnumbered subordinates; everything named
in the mission's "NO DATABASE UI" list (career heartbeat, DNA growth-
velocity/acceleration/stability, and round_history's other real
extremes) relocated into #8 Raw Data. No new data, section, chart,
metric, JSON field, or SQLite table was introduced -- every real
number below already existed in PLAYER_HISTORY.json before this
mission; these tests confirm only WHERE it now renders, and that
nothing was lost.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.website_v2 import player_history_10097_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_eight_question_hierarchy_is_present_in_order():
    _, html = _doc_and_html()
    order = [
        "1. 현재 폼", "2. 왜 지금인가", "3. 최근 경기 결과", "4. 선수 정체성",
        "5. 코스 프로필", "6. 라운드 분석", "7. 커리어 스토리", "8. 데이터베이스 / 검증",
    ]
    positions = [html.index(t) for t in order]
    assert positions == sorted(positions)


def test_no_other_numbered_top_level_section_exists():
    """Only these 8 digit-prefixed <h2> titles may appear -- 시즌 변화/
    대회 타임라인/플레이어 DNA must never carry their own digit again."""
    import re
    _, html = _doc_and_html()
    numbered = re.findall(r'<h2>(\d+)\. ', html)
    assert numbered == [str(i) for i in range(1, 9)], f"unexpected numbered sections: {numbered}"


def test_course_profile_and_round_analysis_moved_before_career_story():
    """MISSION: '5. 어떤 대회에서 강한가' and '6. 언제 잘 치는가' now
    outrank the whole career-evolution cluster, matching the mission's
    PAGE FLOW."""
    _, html = _doc_and_html()
    assert html.index('id="ph-course-profile"') < html.index('id="ph-career-story"')
    assert html.index('id="ph-round-history"') < html.index('id="ph-career-story"')


def test_round_analysis_shows_only_best_and_worst_no_flat_enumeration():
    """MISSION: '최고 라운드/최악 라운드/최대 향상 같은 데이터베이스식
    나열은 지양.' #6 must show exactly the best/worst pair -- the other
    three already-real extremes must NOT appear inside it."""
    _, html = _doc_and_html()
    start = html.index('id="ph-round-history"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "최고 라운드" in section
    assert "최악 라운드" in section
    assert "가장 안정적인 대회" not in section
    assert "최다 향상 라운드" not in section
    assert "최대 붕괴" not in section


def test_relocated_round_extremes_render_intact_in_raw_data():
    """The three relocated facts are not deleted -- same real numbers,
    now living in #8 via _round_history_detail_html."""
    doc, html = _doc_and_html()
    rh = doc["round_history"]
    start = html.index('id="ph-round-history-detail"')
    end = html.index("</div></details>", start)
    section = html[start:end]
    assert "가장 안정적인 대회" in section
    assert rh["most_stable_tournament"]["tournament"] in section
    assert "최대 붕괴" in section
    assert rh["largest_collapse"]["tournament"] in section


def test_career_heartbeat_relocated_to_raw_data_unchanged():
    doc, html = _doc_and_html()
    hb = doc["career_heartbeat"]
    reconciliation_start = html.index('id="ph-reconciliation"')
    heartbeat_idx = html.index('id="ph-career-heartbeat"')
    assert reconciliation_start < heartbeat_idx
    assert f'실측 {len(hb["beats"])}개 대회' in html[heartbeat_idx:heartbeat_idx + 300]


def test_dna_growth_velocity_relocated_to_raw_data_unchanged():
    doc, html = _doc_and_html()
    reconciliation_start = html.index('id="ph-reconciliation"')
    growth_idx = html.index('id="ph-dna-growth-velocity"')
    assert reconciliation_start < growth_idx
    section = html[growth_idx:html.index("</div>", growth_idx)]
    assert "성장 속도" in section
    assert "성장 가속도" in section
    assert "안정성" in section


def test_demoted_subordinates_carry_the_demotion_class_and_no_digit():
    """시즌 변화/대회 타임라인/플레이어 DNA lost their own number and
    must now render as visually-demoted subordinates of #7."""
    _, html = _doc_and_html()
    for section_id, old_title_fragment in (
        ("ph-career-evolution", "시즌 변화"),
        ("ph-tournament-trend", "대회 타임라인"),
        ("ph-player-dna-radar", "플레이어 DNA"),
    ):
        start = html.index(f'id="{section_id}"')
        tag_start = html.rindex("<details", 0, start)
        tag_end = html.index(">", start)
        assert "pi-section--sub" in html[tag_start:tag_end], f"{section_id} should be demoted"
        summary_end = html.index("</summary>", start)
        heading = html[start:summary_end]
        assert f"<h2>{old_title_fragment}</h2>" in heading
        assert f"<h2>6. {old_title_fragment}</h2>" not in heading
        assert f"<h2>7. {old_title_fragment}</h2>" not in heading


def test_no_new_section_ids_were_introduced():
    """The full set of pi-section <details> ids must remain a subset
    of the pre-mission set -- this mission only reorders/relocates/
    demotes, it never adds a new section."""
    import re
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"


def test_no_golf_statistic_changed_between_consecutive_builds():
    """Purely a reorder/relocate/demote mission -- no calculation may
    have become nondeterministic as a side effect."""
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in (
        "current_vs_career", "tournament_history", "career_overview", "round_history",
        "career_evolution", "season_replay", "career_heartbeat", "player_dna_growth",
        "player_dna_radar", "career_dna",
    ):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_red_team_checklist_no_database_word_before_section_eight():
    """RED TEAM item 4: '4. Database처럼 보이는가 아니면 Player
    Profile처럼 보이는가?' -- nothing database-flavored may appear
    before #8."""
    _, html = _doc_and_html()
    section_eight_start = html.index("8. 데이터베이스 / 검증")
    before = html[:section_eight_start]
    assert "커리어 하트비트" not in before
    assert "성장 속도" not in before
    assert "성장 가속도" not in before
    assert "가장 안정적인 대회" not in before
    assert "최다 향상 라운드" not in before
    assert "최대 붕괴" not in before
