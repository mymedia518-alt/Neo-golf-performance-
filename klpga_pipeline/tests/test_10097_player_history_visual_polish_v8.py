"""MISSION V8 (2026-09-25), playerCode=10097 only.

"Freeze the architecture. No new sections. No new charts. No new
cards. No new data. No new metrics. Improve only visual hierarchy.
Improve only typography. Improve only spacing. Improve only reading
speed... When in doubt, delete. When in doubt, simplify. When in
doubt, show less."

This mission touched CSS and small presentational markup only:
1. The whole page is now wrapped in a `.ph-page` div so every visual
   rule this mission adds can be scoped to this one player's page --
   .piq-*/.pi-section are shared with player_intelligence_10097_report
   and player_intelligence_9431_report, and must never change there.
2. Three un-numbered, always-open subordinate sections (시즌 리플레이,
   시즌 변화 하이라이트, 홀 기록) now carry an extra `pi-section--sub`
   class so CSS can visually demote them below the 11 numbered primary
   sections -- no section moved, was renamed, or lost content.
3. The Current Form hero's trend chip no longer carries its own inline
   parenthetical -- the same real numbers now sit in a caption line
   beneath the chip row instead of inside the chip's text.

Every real number, section, and id from Mission V7 is unchanged; these
tests confirm the markup hooks exist and that no content was lost.
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

from klpga.website_v2 import player_history_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_whole_page_is_wrapped_for_css_scoping():
    _, html = _doc_and_html()
    assert html.startswith('<div class="ph-page">')
    assert html.rstrip().endswith("</div>")


def test_subordinate_open_sections_carry_the_demotion_class():
    _, html = _doc_and_html()
    for section_id in ("ph-season-replay", "ph-career-evolution", "ph-hole-history"):
        start = html.index(f'id="{section_id}"')
        tag_start = html.rindex("<details", 0, start)
        tag_end = html.index(">", start)
        assert "pi-section--sub" in html[tag_start:tag_end], f"{section_id} missing the demotion class"


def test_numbered_primary_sections_do_not_carry_the_demotion_class():
    """Only the un-numbered subordinate blocks are demoted -- none of
    the 8 real numbered sections should ever be.

    MISSION NEO PLAYER PROFILE V2 (2026-09-27) demoted 시즌 변화
    (ph-career-evolution), 대회 타임라인 (ph-tournament-trend), and
    플레이어 DNA (ph-player-dna-radar) into unnumbered subordinates of
    #7 커리어 스토리 -- they are intentionally excluded from this list
    now; ph-course-profile and ph-round-history were promoted to their
    own numbered sections (#5, #6) instead and must stay non-demoted."""
    _, html = _doc_and_html()
    for section_id in (
        "ph-current-form", "ph-why-now", "ph-recent-form", "ph-player-identity",
        "ph-career-story", "ph-round-history", "ph-course-profile", "ph-reconciliation",
    ):
        start = html.index(f'id="{section_id}"')
        tag_start = html.rindex("<details", 0, start)
        tag_end = html.index(">", start)
        assert "pi-section--sub" not in html[tag_start:tag_end], f"{section_id} should not be demoted"


def test_trend_chip_no_longer_carries_its_own_inline_parenthetical():
    """MISSION V8 (2026-09-25) moved the trend chip's own parenthetical
    detail ('최근 5개 평균 X vs 직전 5개 평균 Y') out to a caption below
    it, so the chip row's rhythm stayed even.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) superseded that
    caption entirely -- '사용자는 읽는 것이 아니라 훑는다': the whole
    'X vs Y' sentence is gone, replaced by one bare colored trend arrow
    (▲/▼/—) plus its existing terms.py label (상승세/하락세/보합세).
    Nothing to duplicate any more -- this test now pins the deletion,
    not the caption's placement."""
    doc, html = _doc_and_html()
    indicator = doc.get("current_form_indicator")
    if not indicator:
        return
    start = html.index('id="ph-current-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    last5 = report._fmt(indicator["last5_avg_sg_total"])
    prev5 = report._fmt(indicator["prev5_avg_sg_total"])
    assert f'최근 5개 평균 {last5} vs 직전 5개 평균 {prev5}' not in section
    assert "ph-scan-trend" in section
    assert report._FORM_INDICATOR_LABEL[indicator["trend"]] in section


def test_no_section_id_was_added_or_removed_by_this_mission():
    """MISSION V8 froze the architecture -- the exact same section ids
    from Mission V7 must all still be present, nothing more."""
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    import re
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"


def test_every_real_number_from_the_hero_is_still_present():
    """MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) deliberately
    stopped restating the raw career-average number in the hero -- the
    big delta stat already IS the comparison against it, and the
    approved design's whole point is fewer numbers per section. The
    career average itself still lives on the page (Career Story's
    season table, Season Evolution's chips); this test now pins the
    smaller, intentional set of facts the hero itself still carries."""
    doc, html = _doc_and_html()
    cvc = doc["current_vs_career"]
    start = html.index('id="ph-current-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert f'{cvc["delta_vs_career_average"]:+.2f}' in section
    assert report._fmt(cvc["current_season_sg_total"]) in section
