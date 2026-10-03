"""MISSION V31 (2026-09-28), playerCode=10097 only.

"Stop organizing the page by DATA. Organize the page by QUESTIONS...
Never create a visualization unless it answers a question. Delete any
visualization that has no decision value. Build a 'Skill Chain'. Skill
-> Scoring Opportunity -> Scoring -> Result -> Career. Use only
verified repository data. Every visual must answer 'What changed?'
'When?' 'Why?' If it cannot answer one of those, remove it."

Two concrete changes, both using only already-computed real data:
1. A new Skill Chain (_skill_chain_html) in #2 왜 지금인가 -- five real
   facts (lead skill, GIR rate, average score, this season's wins/
   Top10, delta vs career) chained in one row, answering 'why' one
   real step further than the existing arrow grid alone. Renders
   nothing if any required real field is missing -- no invented link.
2. Player DNA's per-season delta table dropped its '백분위' column --
   that number was already printed, digit for digit, as each axis
   point's own label on the radar chart directly above it. Only the
   one real number the chart does not show (delta vs her career mean)
   survives in the table.
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


def test_skill_chain_renders_five_real_stages_inside_why_now():
    doc, html = _doc_and_html()
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert section.count('class="ph-chain-stage"') == 5
    assert section.count('class="ph-chain-arrow"') == 4


def test_skill_chain_stages_use_real_already_computed_values_only():
    doc, html = _doc_and_html()
    why_now = doc["why_now"]
    snap = doc["current_snapshot"]
    cvc = doc["current_vs_career"]
    current = doc["career_story"]["current"]
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert why_now["lead_component"].removeprefix("SG ") in section
    assert f'{why_now["lead_delta"]:+.2f}' in section
    assert f'{snap["gir_rate"]:.1f}%' in section
    assert f'{snap["average_score"]:.2f}' in section
    assert f'{current["wins"]}승' in section
    assert f'Top10 {current["top10"]}회' in section
    assert f'{cvc["delta_vs_career_average"]:+.2f}' in section


def test_skill_chain_has_at_most_one_confirming_sentence():
    """'The text confirms the answer in one sentence. Maximum.'"""
    doc, html = _doc_and_html()
    start = html.index('class="ph-skill-chain"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert section.count('<p class="piq-conclusion">') == 1


def test_skill_chain_renders_nothing_when_a_required_real_field_is_missing():
    """Never an invented link in the chain -- if any real stage's data
    is unavailable, the whole chain renders nothing rather than a
    partial or fabricated one."""
    html = report._skill_chain_html(None, {"gir_rate": 1.0, "average_score": 70.0}, {"delta_vs_career_average": 1.0}, {"wins": 1, "top10": 1, "season": 2026})
    assert html == ""
    html2 = report._skill_chain_html({"lead_component": "SG APP", "lead_delta": 0.1}, None, {"delta_vs_career_average": 1.0}, {"wins": 1, "top10": 1, "season": 2026})
    assert html2 == ""


def test_dna_radar_delta_numbers_survive_as_kpi_cards_not_a_table():
    """MISSION V31's reasoning for dropping the '백분위' column was that
    the number was 'already printed, digit for digit, as each axis
    point's own label on the radar chart directly above it.'

    MISSION V60 (2026-09-28): 'remove every numeric label drawn inside
    charts... values appear only in tooltips or summary cards.' The
    radar's axis labels no longer print the percentile number at all
    (it moved into each axis dot's <title> tooltip), so V31's premise
    no longer holds and the percentile briefly came back as a table
    column.

    MISSION V70 (2026-09-28): 'DNA radar must stand alone without
    supporting tables... replace paragraphs with visual KPI cards.'
    Both real numbers per axis (percentile, delta vs career mean)
    still survive -- now as a compact KPI-card grid instead of a
    table -- so no data is lost, only the table itself is gone."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-player-dna-radar"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "<table" not in section, "MISSION V70: the DNA radar must stand alone without a supporting table"
    assert "pi-kpi-grid" in section and "kpi-block" in section
    seasons_data = doc.get("player_dna_radar") or []
    latest = seasons_data[-1]
    for a in latest["axes"]:
        if a.get("percentile") is not None and a.get("delta_vs_career_mean") is not None:
            assert f'{a["percentile"]:.0f}' in section
            assert f'{a["delta_vs_career_mean"]:+.1f}' in section


def test_dna_radar_chart_carries_the_real_percentile_only_in_its_tooltip():
    """MISSION V60 (2026-09-28): the percentile is no longer a visible
    axis-point label -- it survives only as each axis dot's <title>
    tooltip, and the visible axis label (a plain <text>) is the bare
    skill name with no number in it."""
    from klpga.website_v2 import player_history_terms as terms
    doc, html = _doc_and_html()
    seasons_data = doc.get("player_dna_radar") or []
    assert seasons_data
    latest = seasons_data[-1]
    svg = report._radar_svg(latest["axes"])
    for a in latest["axes"]:
        if a.get("percentile") is not None:
            axis_ko = terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"])
            assert f'<title>{report.escape(axis_ko)} {a["percentile"]:.0f}</title>' in svg
            assert f'>{report.escape(axis_ko)}</text>' in svg


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("why_now", "current_snapshot", "current_vs_career", "career_story", "player_dna_radar"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_no_new_top_level_section_ids_were_introduced():
    import re
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
        # NEO Player History Engine V2 (2026-10-03): official_detail_record /
        # round_momentum / player_dna / course_fit_score, rendered generically
        # for any player_id -- see klpga.website_v2.official_detail_enrichment.
        "ph-official-statistics-v2", "ph-sg-profile-v2", "ph-round-momentum-v2",
        "ph-player-dna-v2", "ph-course-fit-score-v2", "ph-neo-evaluation-v2",
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"
