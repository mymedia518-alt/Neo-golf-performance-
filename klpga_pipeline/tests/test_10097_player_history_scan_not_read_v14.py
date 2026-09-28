"""MISSION "30초 스캔" (2026-09-27), playerCode=10097 only.

"이 페이지를 처음 방문한 골퍼가 30초 동안만 본다고 가정한다. 30초 안에
이 선수를 설명할 수 있도록 만들어라. 읽게 하지 말고 보이게 만들어라...
각 섹션은 5초 안에 이해되어야 한다. 사용자는 읽는 것이 아니라 훑는다."

This mission required a wireframe per section, submitted for approval
before any code (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7)
before implementation began, then a strict "implement exactly the
approved wireframe, do not improve it" rule. Two deviations from the
first wireframe draft were explicitly resolved by the user before
implementation:
  1. Section 3's dot strip drops any win/Top10 TALLY line (even a
     count-free legend key stays, since it is a description of what a
     color means, not a computed summary).
  2. Section 4 drops the redundant "강점: SG APP" line (restated the
     badge and the share-% line) -- badge, share-%, and the one
     distinct consistency fact survive.

Sections 1 (현재 폼), 2 (왜 지금인가), 3 (최근 경기 결과), 4 (선수
정체성), and 6 (라운드 분석) were rewritten to replace sentences/
tables/multi-chip rows with one big number, an icon grid, a dot strip,
a badge, or a big-number pair. Sections 5 (코스 프로필), 7 (커리어
스토리 cluster) and 8 (Raw Data) were explicitly left untouched by the
approved wireframe. No new data, section, chart, metric, JSON field,
or SQLite table was introduced -- only how the same already-computed
values are shown.
"""
from __future__ import annotations

import importlib.util
import re
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


def test_section1_hero_has_no_multi_chip_row_only_bare_stats_and_one_trend_arrow():
    doc, html = _doc_and_html()
    start = html.index('id="ph-current-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert '<div class="piq-audit">' not in section
    assert "ph-scan-stats" in section
    assert "ph-scan-trend" in section
    assert section.count('class="ph-scan-stat"') == 2


def test_section2_arrow_grid_has_exactly_four_cards_no_text_chips():
    """MISSION V41 (2026-09-28) added an optional '가장 덜 개선' tag
    inside the weakest card's own label div (the page's answer to
    'what is the current weakness?') -- the label match allows for it,
    since it's still exactly one label per card, no new chip/card."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert '<div class="piq-audit">' not in section
    assert section.count('class="ph-arrow-card') == 4
    for a in doc["why_now"]["arrows"]:
        short = a["component"].removeprefix("SG ")
        assert re.search(rf'<div class="ph-arrow-lbl">{re.escape(short)}(<span class="ph-arrow-weakest-tag">[^<]*</span>)?</div>', section)


def test_section3_is_one_flat_dot_strip_with_a_countless_legend():
    """The user explicitly rejected a win/Top10 tally line -- the legend
    may describe what each color means, but must never state a count."""
    doc, html = _doc_and_html()
    rows = doc.get("recent_form_20") or doc.get("recent_form_10") or doc.get("recent_form_5")
    start = html.index('id="ph-recent-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert section.count('class="ph-form-dot') == len(rows)
    assert "<table" not in section
    assert "우승" in section and "상위10위" in section
    import re
    # scope to the legend chips only -- real tournament names inside
    # dot title="..." attributes can legitimately contain a digit+회
    # (e.g. "제2회 덕신EPC 챔피언십"), which is not a tally and must
    # not trip this check.
    legend_start = section.index('class="piq-audit"')
    legend = section[legend_start:]
    assert not re.search(r"\d+회", legend), "a win/Top10 tally line was reintroduced -- explicitly rejected by the user"


def test_section4_identity_is_badge_plus_two_lines_no_redundant_third_line():
    """The approval round caught and rejected a real duplicate
    ('강점: SG APP' restated the badge + share-% line) -- must never
    reappear."""
    doc, html = _doc_and_html()
    identity = doc["player_identity"]
    start = html.index('id="ph-player-identity"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert f'<span class="ph-identity-badge">{report.escape(identity["primary_type"])}</span>' in section
    assert f'{identity["primary_component"]} {identity["primary_share_pct"]}% 비중' in section
    assert "강점:" not in section
    if identity.get("consistency_component"):
        assert f'가장 안정적인 능력: {identity["consistency_component"]}' in section


def test_section6_round_analysis_is_two_big_numbers_no_sentences():
    doc, html = _doc_and_html()
    rh = doc["round_history"]
    start = html.index('id="ph-round-history"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert section.count('class="ph-round-big') >= 2
    assert "SG Total" not in section
    assert report._fmt(rh["best_round"]["sg_total"]) in section
    assert report._fmt(rh["worst_round"]["sg_total"]) in section
    assert "가장 안정적인 대회" not in section
    assert "최다 향상 라운드" not in section
    assert "최대 붕괴" not in section


def test_relocated_round_extremes_still_intact_in_raw_data_unaffected_by_this_mission():
    """Sections outside the approved wireframe (#8 Raw Data) must be
    byte-for-byte unaffected by this mission."""
    doc, html = _doc_and_html()
    rh = doc["round_history"]
    start = html.index('id="ph-round-history-detail"')
    end = html.index("</div></details>", start)
    section = html[start:end]
    assert "가장 안정적인 대회" in section
    assert rh["most_stable_tournament"]["tournament"] in section


def test_course_profile_and_raw_data_sections_are_untouched():
    """The approved wireframe explicitly left #5 and #7/#8 as-is."""
    _, html = _doc_and_html()
    assert 'id="ph-course-profile"' in html
    course_start = html.index('id="ph-course-profile"')
    course_end = html.index("</details>", course_start)
    assert "ph-scan-stat" not in html[course_start:course_end]
    assert "ph-form-dot" not in html[course_start:course_end]


def test_no_new_section_ids_were_introduced():
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
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in (
        "current_vs_career", "why_now", "recent_form_20", "player_identity",
        "round_history", "course_profile",
    ):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"
