"""MISSION "PLAYER HISTORY V20 continued -- DOCUMENTARY, NOT REPORT"
(2026-09-28), playerCode=10097 only.

"STOP MAKING REPORTS. START BUILDING A PLAYER HISTORY... Every chart
must replace at least 300 words. If a graph and a paragraph say the
same thing, delete the paragraph. If a season average hides evolution,
replace it with a rolling trend. The page should tell the story of a
golfer's career, not summarize statistics."

Three further audits of already-existing report-style content, no new
data introduced:
1. Season Replay's named_windows (처음5/중반5/최근5) was a 3-cell
   TABLE of season-window averages -- exactly 'a season average that
   hides evolution'. Replaced with a real chart (_marked_trend_svg)
   showing the within-season shape.
2. Career Form Story's per-stage sentence used to open with a clause
   ('커리어 평균을 웃돌던 시기였습니다') that only restated the sign of
   a delta already shown by the rolling-trend chart above it AND by
   this same card's own delta chip -- a graph-and-paragraph duplicate,
   deleted.
3. Career Story's four narrative chapters had no visual at all -- a
   real chronological timeline (_career_milestones_timeline_svg) now
   leads them, built from the same five already-computed milestones,
   stacked by real season without inventing a date any milestone
   doesn't already carry.
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


def test_named_windows_is_a_chart_not_a_table():
    # MISSION V73 (2026-09-28): the chip row is now nested inside its
    # own <details class="ph-nested-detail"> disclosure per season, so
    # the naive first "</details>" is that inner disclosure's close,
    # not this whole section's -- bound by the next sibling instead.
    doc, html = _doc_and_html()
    start = html.index('id="ph-season-replay"')
    end = html.index('id="ph-career-rolling-trend"', start)
    section = html[start:end]
    assert "<table" not in section
    real_seasons = {r["season"] for r in doc["season_replay"] if r.get("named_windows")}
    assert real_seasons, "fixture has no season with named_windows to check"
    assert section.count("<svg") >= len(real_seasons)


def test_career_form_story_sentence_drops_the_redundant_direction_clause():
    """The delta chip beneath each card already states the real number
    more precisely than a vague 'above/below career average' clause
    ever could -- that clause must not reappear."""
    doc, html = _doc_and_html()
    for banned in ("커리어 평균을 웃돌던 시기였습니다", "커리어 평균에 못 미치던 시기였습니다"):
        assert banned not in html


def test_career_form_story_still_names_the_real_best_and_worst_component():
    """The one fact neither the rolling-trend chart nor the delta chip
    carries -- which SG component led/lagged -- must survive the trim."""
    doc, html = _doc_and_html()
    stages = doc.get("career_form_story") or []
    for s in stages:
        if s.get("best_component"):
            assert s["best_component"] in html
        if s.get("worst_component"):
            assert s["worst_component"] in html


def test_career_story_leads_with_a_real_chronological_milestone_timeline():
    doc, html = _doc_and_html()
    story = doc["career_story"]
    start = html.index('id="ph-career-story"')
    timeline_svg_start = html.index("<svg", start)
    story_block_start = html.index('class="ph-bio-story"', start)
    assert timeline_svg_start < story_block_start, "timeline must lead, before the chapter text"
    section = html[start:html.index("</details>", start)]
    for c in story["chapters"]:
        for m in c["milestones"]:
            assert report.escape(m["label"]) in section


def test_career_story_milestone_lines_drop_the_redundant_season_prefix():
    """The timeline chart already places every milestone in time -- the
    old '{season}시즌 —' prefix on each chapter line would just repeat
    that same real year in text."""
    doc, html = _doc_and_html()
    story = doc["career_story"]
    for c in story["chapters"]:
        for m in c["milestones"]:
            assert f'{m["season"]}시즌 — {report.escape(m["label"])}' not in html


def test_career_milestones_never_overlap_a_season_axis_tick():
    """Regression for a real bug this mission's own screenshot pass
    caught: a milestone stacked below the spine collided with the
    season tick label directly under it. Milestones must only stack
    ABOVE the axis line now.

    MISSION V77 REDESIGN (2026-09-28): the spine's x1 (side_pad) moved
    from 20 to 44, and the on-chart typography changed (milestone
    titles: font-size 17, font-weight 500; season ticks: font-size 13,
    fill #8a988f) -- this regression check now matches the current
    real markup instead of the pre-redesign one, same intent."""
    doc, html = _doc_and_html()
    story = doc["career_story"]
    seasons = [r["season"] for r in doc["career_overview"]["season_rows"]]
    svg = report._career_milestones_timeline_svg(story["chapters"], seasons)
    assert svg
    import re
    # the axis line's y is the second <line> y1 value; every milestone
    # <text> y must be strictly less than it (drawn above, in SVG's
    # top-down coordinate space) and every season-tick <text> y must be
    # strictly greater (drawn below).
    axis_y = float(re.search(r'<line x1="44\.0" y1="([\d.]+)"', svg).group(1))
    for m in re.finditer(r'<text x="[\d.]+" y="([\d.]+)" font-size="17" font-weight="500"', svg):
        assert float(m.group(1)) < axis_y
    for m in re.finditer(r'<text x="[\d.]+" y="([\d.]+)" font-size="13" fill="#8a988f"', svg):
        assert float(m.group(1)) > axis_y


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("season_replay", "career_form_story", "career_story", "career_overview"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"
