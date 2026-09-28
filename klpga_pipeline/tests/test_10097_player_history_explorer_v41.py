"""MISSION V41 (2026-09-28), playerCode=10097 only. PURE UX -- no new
features, charts, or analysis; only deletion, redesign, and relabeling
of already-computed real facts.

"Pretend you are a KLPGA player who has never seen this page. 15
seconds. Can you answer: (1) biggest strength, (2) when did she become
good, (3) why did she start winning, (4) current weakness, (5) what to
click next? DELETE MODE: for every component, does it help answer one
of the five questions? No duplication: if two components answer the
same question, keep only the better one. THE WOW RULE."

Audit findings and the five changes made:
1. #ph-player-evolution (시즌 변화 하이라이트) deleted entirely -- its
   headline sentence ('2024->2025 시즌, ... 가장 크게 향상되었습니다')
   was a verbatim duplicate of the SAME already-computed
   biggest_improvement fact career_story already narrates as its
   '도약의 순간' milestone (see scripts/build_10097_player_history.py
   line ~1138). Two sections answering 'when did she become good?'
   with the identical real number -- only the richer one (career
   story's full timeline) survives.
2. #ph-career-dna (DNA 요약) deleted as a standalone section -- its two
   real sentences (fastest-growing / most-volatile component) describe
   the DNA radar chart directly above where it used to sit, so they
   move into that chart's own caption instead of a separate details
   block nobody had a reason to look for separately.
3. #ph-career-evolution (시즌 변화, 4 stacked per-metric line charts)
   collapsed by default -- season_replay, immediately below it, already
   tells the same real season-by-season story per real tournament,
   richer (a full chart plus an SG-component heatmap). Still real,
   still one click away.
4. #ph-hole-history collapsed by default -- 51 real hole-by-hole rows
   for one tournament is depth, not first-15-second orientation. The
   MISSION V40 anchor link into it (a real browser auto-opening a
   closed <details> on fragment navigation) still works unchanged.
5. #ph-why-now's arrow grid now labels the smallest of its own four
   already-rendered real deltas as '가장 덜 개선' (least improved) --
   the page's answer to 'what is the current weakness', using nothing
   but min() over data that was already on the page.
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


def test_player_evolution_section_is_gone():
    """Its one real fact survives inside career_story's own timeline."""
    _, html = _doc_and_html()
    assert 'id="ph-player-evolution"' not in html
    assert not hasattr(report, "_player_evolution_html")
    assert not hasattr(report, "_momentum_bars_svg")


def test_career_dna_is_no_longer_a_standalone_section_but_survives_as_a_dna_radar_caption():
    doc, html = _doc_and_html()
    assert 'id="ph-career-dna"' not in html
    assert not hasattr(report, "_career_dna_html")
    dna = doc.get("career_dna") or {}
    start = html.index('id="ph-player-dna-radar"')
    end = html.index("</details>", start)
    section = html[start:end]
    if dna.get("fastest_growing_component"):
        assert dna["fastest_growing_component"] in section
    if dna.get("most_volatile_component"):
        assert dna["most_volatile_component"] in section


def test_dna_radar_caption_renders_nothing_when_career_dna_is_missing():
    """Never an invented caption -- if career_dna has no real fields,
    the radar chart renders exactly as it did before this mission."""
    html_with_none = report._player_dna_radar_html([{"season": 2026, "axes": []}], None)
    html_with_empty = report._player_dna_radar_html([{"season": 2026, "axes": []}], {})
    assert "가장 빠르게 성장한 요소" not in html_with_none
    assert "가장 빠르게 성장한 요소" not in html_with_empty


def test_career_evolution_is_collapsed_by_default():
    _, html = _doc_and_html()
    assert re.search(r'<details class="[^"]*" id="ph-career-evolution">', html)
    assert not re.search(r'id="ph-career-evolution"\s+open', html)
    # the real content is still there, just not pre-opened
    start = html.index('id="ph-career-evolution"')
    end = html.index("</details>", start)
    assert "<svg" in html[start:end]


def test_hole_history_is_collapsed_by_default():
    doc, html = _doc_and_html()
    if not doc.get("hole_history"):
        return
    assert re.search(r'<details class="[^"]*" id="ph-hole-history">', html)
    assert not re.search(r'id="ph-hole-history"\s+open', html)


def test_hole_history_collapsed_state_does_not_break_v40_anchor_navigation():
    """The MISSION V40 drill-down link still targets a real id that
    exists on the page -- a browser auto-opens a closed <details> on
    fragment navigation regardless of its default open/closed state,
    already verified with Playwright for the tournament table; this
    pins that #ph-hole-history keeps the same real, stable id."""
    _, html = _doc_and_html()
    assert 'id="ph-hole-history"' in html


def test_why_now_labels_the_smallest_real_delta_as_the_current_weakness():
    doc, html = _doc_and_html()
    why_now = doc.get("why_now")
    if not why_now or not why_now.get("arrows"):
        return
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert section.count("가장 덜 개선") == 1
    weakest = min(why_now["arrows"], key=lambda a: a["delta"])
    label = weakest["component"].removeprefix("SG ")
    idx = section.index("가장 덜 개선")
    # the tag must be attached to the real weakest component's own card,
    # not a different one -- the label appears right after that card's name
    nearby = section[max(0, idx - 60):idx]
    assert label in nearby


def test_why_now_weakest_tag_uses_only_already_rendered_real_deltas():
    """No new computation beyond min() over data already on the page --
    every arrow's delta is untouched and still printed."""
    doc, html = _doc_and_html()
    why_now = doc.get("why_now")
    if not why_now or not why_now.get("arrows"):
        return
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    for a in why_now["arrows"]:
        assert f'{a["delta"]:+.2f}' in section


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("why_now", "career_dna", "career_evolution", "career_story", "hole_history"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_no_new_top_level_section_ids_were_introduced_and_two_were_removed():
    """MISSION V41: 'Stop adding sections. Start deleting sections.'
    ph-player-evolution and ph-career-dna are gone from the known set;
    nothing new was added."""
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-reconciliation", "ph-not-available",
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"
    assert "ph-player-evolution" not in found_ids
    assert "ph-career-dna" not in found_ids
