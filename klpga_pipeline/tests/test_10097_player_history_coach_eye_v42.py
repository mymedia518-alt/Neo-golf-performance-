"""MISSION V42 (2026-09-28), playerCode=10097 only -- the "coach eye"
follow-up to MISSION V41.

"Close your IDE. Forget your code. Forget your implementation. Open
the page. Would a professional golf coach actually use this page? If
not, why? Write down the first ten reasons. Fix those. Only then
commit."

This mission was done by actually rendering the page (via a local HTTP
server, since the site's CSS uses root-relative /assets/ paths that
only resolve when served, not opened as a file://) and looking at real
Playwright screenshots, not the source code. Ten honest reasons a coach
might not trust/use the page, and what happened to each:

1. Mobile top nav is visibly cut off ("NEO LAB"->"NE", "소개" missing)
   at a real phone width. NOT FIXED here -- global_navigation.py is a
   shared header rendered on every page of the site, out of this
   session's playerCode=10097-only scope to change unilaterally.
2. The DNA summary caption ("가장 빠르게 성장한 요소" / "가장 변동성
   큰 요소") kept naming 'SG Total' for BOTH labels -- confirmed a real
   bug, not a coincidence: SG Total is the SUM of the four real
   components (OTT/APP/ARG/PUTT) it was being compared against, so it
   mechanically wins both "most volatile" and "fastest growing" almost
   every time (a sum of several moving parts moves more than any one
   part), telling a coach nothing about which actual skill is driving
   it. FIXED at the source (_career_dna in build_10097_player_history.py
   now excludes avg_total from the candidate pool for both fields).
3. The one visible "current weakness" signal (가장 덜 개선 on the
   weakest real arrow delta) was a small plain-gray caption under a
   green up-arrow identical to the three "improving" cards beside it --
   easy to miss in a 15-second scan. FIXED (a small gold pill, gold
   because the underlying number is still a real positive delta, never
   red/decline).
4. The 최고/최저 (best/worst) labels on the dense tournament-timeline
   and season charts (up to 96 real points in one chart) could land
   close enough to a *different* real point's own dot to become hard
   to read against it. FIXED with a white halo behind the label text
   (paint-order puts the stroke behind the fill) -- legible wherever it
   lands, without moving or hiding any real dot.
5. Every chart's supplementary per-point detail (native SVG <title>
   hover) is reachable only by mouse hover -- unreachable on any
   touchscreen, which is how a coach most likely checks this on the
   road. NOT FIXED -- a real fix needs either client-side script
   (forbidden by this site's zero-JS architecture) or redesigning many
   charts to show detail without hover, which is new-feature scope
   beyond a pure-UX pass; flagged as an honest structural limitation.
6-10. Reviewed and judged acceptable as-is: the season-replay SG
   heatmap has no per-column axis labels, but the same peak/slump
   tournament names it would label are already named in real text
   chips directly below it; the career-story timeline stacks three
   real same-season milestones as vertically staggered text (a prior
   mission's deliberate, tested mitigation for season-level data
   granularity, not a new bug); ph-snapshot and ph-technical-stats-2025
   are real but off-topic stat dumps, already collapsed by default so
   they do not compete with the 15-second scan; ph-tournament-table and
   ph-round-history-detail are correctly demoted reference tables.
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


def test_career_dna_never_names_sg_total_as_fastest_growing_or_most_volatile():
    """SG Total is the sum of the four real components, not a skill of
    its own -- it must never win a 'which skill' comparison against its
    own parts. Real regression: before this mission it always did."""
    doc = build_script.build()
    dna = doc["career_dna"]
    assert dna.get("fastest_growing_component") != "SG Total"
    assert dna.get("most_volatile_component") != "SG Total"
    assert dna.get("most_consistent_component") != "SG Total"


def test_career_dna_fastest_and_most_volatile_are_real_components_when_present():
    doc = build_script.build()
    dna = doc["career_dna"]
    real_components = {"SG OTT", "SG APP", "SG ARG", "SG PUTT"}
    if dna.get("fastest_growing_component"):
        assert dna["fastest_growing_component"] in real_components
    if dna.get("most_volatile_component"):
        assert dna["most_volatile_component"] in real_components
    if dna.get("most_consistent_component"):
        assert dna["most_consistent_component"] in real_components


def test_tournament_timeline_best_worst_marks_are_tooltip_only_no_halo_needed():
    """A coach-eye screenshot review found the 최고/최저 label text could
    sit close enough to a *different* real point's own dot (not its
    own) to become hard to read in a dense chart, which is why a white
    halo used to sit behind the always-visible label text.

    MISSION V60 (2026-09-28): 'remove every numeric label drawn inside
    charts... values appear only in tooltips.' The best/worst marks no
    longer draw visible text at all -- they are a plain <circle> with a
    <title> tooltip -- so the legibility-halo problem this test used to
    guard against cannot occur anymore, and the halo itself is gone."""
    import re
    doc, html = _doc_and_html()
    start = html.index('id="ph-tournament-trend"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert 'stroke="#f4f6f4"' not in section, "no visible label text remains, so no halo should be drawn either"
    assert re.search(r'<circle[^>]*>\s*<title>[^<]*최고[^<]*</title>', section)
    assert re.search(r'<circle[^>]*>\s*<title>[^<]*최저[^<]*</title>', section)


def test_weakest_arrow_tag_is_visually_distinct_from_plain_caption_text():
    """The first version of the '가장 덜 개선' tag (MISSION V41) was
    plain gray text indistinguishable from every other caption on the
    page -- a coach-eye review found it disappeared in a 15-second
    scan. It must now render as its own visually distinct element."""
    css = (ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css").read_text()
    assert ".ph-arrow-weakest-tag{" in css
    import re
    rule = re.search(r"\.ph-arrow-weakest-tag\{([^}]*)\}", css)
    assert rule
    assert "background" in rule.group(1)


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("career_dna", "tournament_history", "season_replay"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"
