"""MISSION V5 (2026-09-25), playerCode=10097 only.

"Do not add any new sections. Do not add more cards. Increase
information density instead... Replace statistics with golf language.
Replace implementation with identity. Replace repeated numbers with
visual comparison... Every chart must answer one question. Every
sentence must answer one question. Delete everything else."

No section IDs change in this mission -- these tests pin down that the
SAME sections now say less, never twice, and that nothing was added as
a new top-level card.
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


def test_no_new_section_ids_were_added():
    """The full set of top-level ids after V5 must be a SUBSET of the
    set after V4 -- density work only removes/merges, never adds."""
    _, html = _doc_and_html()
    v4_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    import re
    # only ids on <details class="...pi-section..."> elements count as
    # "sections" -- ph-dna-tab-N/ph-dna-panel-* are pre-existing radio-
    # tab sub-panel ids inside the DNA radar, not sections of their own.
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= v4_ids, f"new section id(s) introduced: {found_ids - v4_ids}"


def test_career_average_sg_total_is_stated_once_not_twice():
    """The hero (#1) states the career average SG Total; the rolling-
    trend chip block used to restate the exact same figure a second
    time -- deleted (V5: 'delete everything else')."""
    doc, html = _doc_and_html()
    career_avg = doc["career_rolling_trend"]["career_average_sg_total"]
    phrase = f'커리어 평균 SG Total {career_avg:+.2f}'
    assert html.count(phrase) <= 1


def test_career_dna_no_longer_repeats_player_identity():
    """career_foundation/winning_foundation/most_consistent_component
    are narrated in #4 Player Identity -- the DNA summary (folded into
    #ph-player-dna-radar's own caption as of MISSION V41, no longer a
    standalone #ph-career-dna checklist) must not restate them."""
    doc, html = _doc_and_html()
    dna = doc["career_dna"]
    assert 'id="ph-career-dna"' not in html
    start = html.index('id="ph-player-dna-radar"')
    end = html.index("</details>", start)
    section = html[start:end]
    if dna.get("career_foundation"):
        assert f'{dna["career_foundation"]} (' not in section
    if dna.get("most_consistent_component"):
        assert "가장 일관된 요소" not in section


def test_why_now_never_repeats_the_arrow_deltas_in_a_second_table():
    """V5 replaced the raw table with a chart; V6 mission (2026-09-25)
    removed the chart too -- it repeated the same four numbers the
    arrow chips already state. See test_why_now_leads_with_one_
    sentence_before_the_arrow_chips (biography_v4 suite) for the
    current, chart-free shape."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "<table" not in section
    assert "<svg" not in section


def test_course_profile_shows_a_bar_chart_and_a_collapsed_full_table():
    """V5: 'replace repeated numbers with visual comparison.' The
    visible surface is a bar chart of the real top/bottom performers;
    the complete numeric table still exists, but only behind a nested
    disclosure -- never deleted, never shown all at once."""
    doc, html = _doc_and_html()
    profiles = doc["course_profile"]
    start = html.index('id="ph-course-profile"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "<svg" in section
    assert 'class="ph-nested-detail"' in section
    nested_start = section.index('class="ph-nested-detail"')
    assert "<table" not in section[:nested_start]  # no raw table before the toggle
    assert "<table" in section[nested_start:]
    for p in profiles[:3]:
        assert p["tournament_family"] in section


def test_heartbeat_chart_answers_exactly_one_question():
    """'Every chart must answer exactly one question.' Career Heartbeat
    used to be a dual-track chart (two questions in one SVG) -- now a
    single track.

    MISSION NEO PLAYER PROFILE V2 (2026-09-27) relocated this block
    (unchanged) from the season-evolution cluster into #8 Raw Data, so
    it is no longer its own top-level <details> -- bounded here by its
    own closing </div> (found via the block's unique closing caption
    text) instead of the enclosing #8 section's </details>, which now
    also contains unrelated relocated content (e.g. the DNA growth
    table's '백분위' column header) after it."""
    _, html = _doc_and_html()
    start = html.index('id="ph-career-heartbeat"')
    end = html.index("</svg>", start)
    section = html[start:end]
    assert section.count("<svg") == 1
    own_block_end = html.index("위로 갈수록 기준보다 좋았던 대회입니다.</p>", start)
    assert "백분위" not in html[start:own_block_end]


def test_official_snapshot_is_collapsed_and_never_repeats_sg_components():
    """The SG-rank/SG-component chip row this block used to lead with
    duplicated the Current Form hero and Why Now word for word --
    deleted. What remains (money/score/putts/rates) is real, new
    information, collapsed since it is not needed for a 30-second
    read."""
    _, html = _doc_and_html()
    start = html.index('id="ph-snapshot"')
    open_tag_end = html.index(">", start)
    assert " open" not in html[start:open_tag_end]
    end = html.index("</details>", start)
    section = html[start:end]
    assert "SG OTT" not in section
    assert "SG APP" not in section
    assert "공식 SG 랭크" not in section
