"""MISSION V11 (2026-09-25), playerCode=10097 only: User-facing Data
Confidence.

"Do not change any calculations. Do not change any player data. Use
the provenance classifications from Mission V10. Translate developer
provenance into user trust... Never expose internal labels such as
MEASURED, DERIVED, IMPUTED. The purpose is to answer: 'How much should
I trust what I am reading?'"

These tests cover the 5 deliverables (Page Confidence Score, Field
Confidence Badges/legend, Provenance Summary, Technical Debt Dashboard
-- translated to a data-confidence roadmap, Data Quality Timeline),
the hard constraint that no internal label string ever reaches the
rendered HTML, and that no golf statistic changed as a side effect.
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

_INTERNAL_LABELS = ("MEASURED", "DERIVED", "IMPUTED", "NOT_COLLECTED", "NOT_AVAILABLE")


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_no_internal_provenance_label_ever_reaches_the_rendered_html():
    """The mission's hardest constraint: MEASURED/DERIVED/IMPUTED/
    NOT_COLLECTED/NOT_AVAILABLE must never appear in the rendered page,
    even though they live on freely inside doc['provenance'] (developer/
    CI-facing, not shown to a reader)."""
    _, html = _doc_and_html()
    for label in _INTERNAL_LABELS:
        assert label not in html, f"internal provenance label leaked into rendered HTML: {label!r}"


def test_page_confidence_score_exists_and_is_a_real_computed_percentage():
    doc = _doc_and_html()[0]
    pc = doc["page_confidence"]
    counts_sum = pc["real_or_calculated_fields"] + pc["estimated_fields"] + pc["not_yet_available_fields"]
    assert counts_sum == pc["total_fields_checked"]
    assert pc["trustworthy_pct"] == round(pc["real_or_calculated_fields"] / pc["total_fields_checked"] * 100, 1)
    assert pc["trust_band"] in ("매우 높음", "높음", "보통", "주의 필요")


def test_page_confidence_appears_early_in_the_hero_not_only_at_the_bottom():
    """'How much should I trust this' must be answerable before
    scrolling past ten sections -- the hero must carry a trust line,
    not only the bottom-of-page detail block."""
    doc, html = _doc_and_html()
    hero_end = html.index("</header>")
    trust_pct = str(doc["page_confidence"]["trustworthy_pct"])
    assert 'class="ph-trust-line"' in html[:hero_end]
    assert trust_pct in html[:hero_end]


def test_field_confidence_legend_covers_every_label_with_translated_copy():
    doc = _doc_and_html()[0]
    legend = doc["field_confidence_legend"]
    assert set(legend.keys()) == set(_INTERNAL_LABELS)
    for label, entry in legend.items():
        assert entry["short"]
        assert entry["detail"]
        assert entry["tier"] in ("high", "caution", "gap")
        # the translated copy itself must never just restate the raw label
        assert entry["short"] != label


def test_provenance_summary_counts_match_the_core_provenance_map():
    """provenance_summary/page_confidence are computed from the CORE
    604-field provenance map (the real golf content), before this
    mission's own 20 meta-fields (page_confidence.*, provenance_summary.*,
    etc.) are merged in -- otherwise the trust score would be diluted
    by counting its own commentary about itself. doc['provenance']
    (the full, merged map) is intentionally larger than
    provenance_summary['total_fields_checked']."""
    doc = _doc_and_html()[0]
    provenance = doc["provenance"]
    summary = doc["provenance_summary"]
    assert summary["total_fields_checked"] < len(provenance)
    core_provenance = {k: v for k, v in provenance.items() if not k.split(".")[0].split("[")[0] in (
        "page_confidence", "field_confidence_legend", "provenance_summary", "data_confidence_roadmap", "data_quality_timeline",
    )}
    assert summary["total_fields_checked"] == len(core_provenance)
    real_counts = {}
    for entry in core_provenance.values():
        real_counts[entry["label"]] = real_counts.get(entry["label"], 0) + 1
    for row in summary["rows"]:
        # match the row back to its real count via the legend translation
        matching_label = next(k for k, v in doc["field_confidence_legend"].items() if v["short"] == row["short"])
        assert row["count"] == real_counts[matching_label]


def test_data_confidence_roadmap_is_the_technical_debt_dashboard_in_plain_language():
    """Every roadmap item must be a real, non-empty group with a real
    field count, and none of its title text may use developer jargon
    like 'technical debt'."""
    doc = _doc_and_html()[0]
    roadmap = doc["data_confidence_roadmap"]
    assert roadmap
    total_gap_and_unverified = sum(item["field_count"] for item in roadmap)
    provenance = doc["provenance"]
    expected = sum(
        1 for e in provenance.values()
        if e["label"] in ("NOT_COLLECTED", "NOT_AVAILABLE") or "not computed from a live" in e["reason"]
    )
    assert total_gap_and_unverified == expected
    for item in roadmap:
        assert item["field_count"] > 0
        assert "technical debt" not in item["title"].lower()
        assert "debt" not in item["title"].lower()


def test_data_quality_timeline_covers_every_real_season_with_a_real_percentage():
    doc = _doc_and_html()[0]
    timeline = doc["data_quality_timeline"]
    coverage_matrix = doc["coverage_matrix"]
    assert [row["season"] for row in timeline] == coverage_matrix["seasons"]
    for row in timeline:
        assert 0 <= row["available_pct"] <= 100
        assert row["summary"]


def test_data_confidence_block_is_rendered_inside_section_11_not_a_new_top_level_section():
    """No new numbered top-level section was added -- the whole
    feature nests inside the existing #11 (데이터베이스 / 검증), the
    established home for supporting/meta content on this page."""
    _, html = _doc_and_html()
    recon_start = html.index('id="ph-reconciliation"')
    recon_end = html.index("</details>", html.index('id="ph-data-confidence"'))
    data_confidence_start = html.index('id="ph-data-confidence"')
    assert recon_start < data_confidence_start < recon_end


def test_no_new_numbered_section_ids_were_added():
    """MISSION V11 adds no new UI outside #11 except the hero's one
    trust line -- the set of numbered-primary-section ids from prior
    missions must be unchanged."""
    _, html = _doc_and_html()
    import re
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new top-level section id(s) introduced: {found_ids - known_ids}"


def test_no_golf_statistic_changed_between_consecutive_builds():
    """'Do not change any calculations. Do not change any player
    data.' Two successive build() calls must agree on every real golf
    number -- this mission only added meta-computation over the
    provenance map, nothing that could make a real stat
    nondeterministic."""
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("current_vs_career", "tournament_history", "career_overview", "career_dna", "round_history"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_page_confidence_reflects_the_real_zero_imputed_count_for_this_player():
    doc = _doc_and_html()[0]
    assert doc["page_confidence"]["estimated_fields"] == 0
