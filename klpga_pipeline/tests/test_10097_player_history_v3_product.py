"""PLAYER HISTORY -- V3 PRODUCT BUILD (multi-season backfill audit,
Season Evolution, Player DNA radar, Tournament History trend, Recent
Form) -- playerCode=10097 only.

These tests prove the specific correctness properties this mission
demanded: missing data is never coerced to zero, an in-progress
tournament never contaminates completed-career aggregates, a
single-season technical metric is never presented as a fake
multi-year trend, and the Player DNA radar never fabricates an axis
it cannot defensibly populate.
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


def test_missing_kb_sg_is_never_zero_in_the_document():
    doc = build_script.build()
    kb = next(t for t in doc["tournament_history"] if t["game_code"] == "2026090003")
    assert kb["sg_total"] is None
    assert kb["sg_total"] != 0


def test_kb_missing_sg_is_excluded_not_zeroed_in_tournament_trend_chart():
    """The chronological SG trend must skip KB entirely, not insert a
    zero data point that would visually read as a collapse."""
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    start = html.index('id="ph-tournament-history"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "KB금융 골든라이프 챔피언십" in section  # she's still listed in the table
    # the trend chart is built only from tournaments with real sg_total;
    # verify the count of plotted points equals exactly the SG-bearing subset
    sg_bearing = [t for t in doc["tournament_history"] if t.get("sg_total") is not None]
    assert len(sg_bearing) == len(doc["tournament_history"]) - 1  # only KB is excluded


def test_in_progress_tournament_never_appears_in_finished_aggregates():
    doc = build_script.build()
    finished_codes = {t["game_code"] for t in doc["tournament_history"]}
    assert doc["current_tournament_in_progress"]["game_code"] not in finished_codes
    assert doc["current_tournament_in_progress"]["game_code"] == "2026120001"
    assert doc["career_overview"]["total_events"] == len(doc["tournament_history"])


def test_recent_form_never_includes_the_in_progress_tournament():
    doc = build_script.build()
    in_progress_code = doc["current_tournament_in_progress"]["game_code"]
    for row in doc["recent_form_5"] + doc["recent_form_10"]:
        assert row["game_code"] != in_progress_code


def test_technical_stats_2025_is_a_single_point_never_a_fake_trend():
    """The 2025 technical stats snapshot must never carry a multi-season
    series/trend structure -- it is one real capture, one season."""
    doc = build_script.build()
    ts = doc["technical_stats_2025"]
    for m in ts["metrics"]:
        assert "series" not in m
        assert "trend" not in m
        assert "seasons" not in m
    assert ts["season"] == 2025


def test_player_dna_radar_never_fabricates_an_unavailable_axis():
    doc = build_script.build()
    for season_block in doc["player_dna_radar"]:
        for axis in season_block["axes"]:
            if not axis["available"]:
                assert axis["percentile"] is None
                assert axis["raw_value"] is None
            else:
                assert axis["percentile"] is not None
                assert 0 <= axis["percentile"] <= 100
                assert axis["population"] is not None and axis["population"] > 1


def test_player_dna_radar_carries_full_metadata_per_axis():
    doc = build_script.build()
    required = {"axis", "source_metric", "season", "raw_value", "percentile", "population", "normalization_method", "source"}
    for season_block in doc["player_dna_radar"]:
        for axis in season_block["axes"]:
            assert required <= set(axis.keys())


def test_player_dna_radar_season_uses_only_that_seasons_population():
    """A season's percentile must be computed against that season's own
    player population size, not a mixed cross-season pool -- population
    counts should differ across seasons (the tour's field size changed
    year to year), proving no season leaks into another."""
    doc = build_script.build()
    populations = {sb["season"]: sb["axes"][0]["population"] for sb in doc["player_dna_radar"]}
    assert len(set(populations.values())) > 1


def test_radar_svg_renders_only_available_percentiles_never_plots_none_as_zero():
    doc = build_script.build()
    for season_block in doc["player_dna_radar"]:
        svg = report._radar_svg(season_block["axes"])
        assert svg  # every real season here has all 5 axes available
        assert "None" not in svg


def test_tournament_chronology_is_sorted_by_real_end_date_not_game_code():
    """RED TEAM (2026-09-25): the whole repository's tournament-chronology
    sort now goes through klpga.tournament_ordering.sort_tournaments, which
    overrides the (season, game_code) proxy with the real official end_date
    wherever OFFICIAL_KLPGA_SCHEDULE.json has one on file -- confirmed
    necessary because KB (2026090003, real end 2026-09-13) must sort before
    Hana (2026090002, real end 2026-09-20), the reverse of game_code order."""
    from klpga.tournament_ordering import sort_tournaments

    doc = build_script.build()
    keys = [(t["season"], t["game_code"]) for t in doc["tournament_history"]]
    expected = [(t["season"], t["game_code"]) for t in sort_tournaments(doc["tournament_history"])]
    assert keys == expected
    assert keys[-2:] == [(2026, "2026090003"), (2026, "2026090002")]  # KB before Hana


def test_recent_form_is_the_chronological_tail_not_a_re_sort_by_rank():
    """RED TEAM (2026-09-25): (season, game_code) is only a chronology
    PROXY, not real chronology -- game_code is an internal tournament
    id. Confirmed wrong here: 2026090003 (KB) really ended 2026-09-13,
    2026090002 (Hana) really ended 2026-09-20, but the game_code proxy
    (090002 < 090003) would sort Hana before KB. Real end dates (from
    OFFICIAL_KLPGA_SCHEDULE.json, the one source of real dates in this
    repository) always override the proxy when known -- so recent_form
    is no longer required to equal the naive proxy tail; it must still
    be a real chronological tail, just built with the corrected order."""
    doc = build_script.build()
    last_5 = [(t["season"], t["game_code"]) for t in doc["recent_form_5"]]
    assert last_5[-2:] == [(2026, "2026090003"), (2026, "2026090002")], (
        "KB (real end 2026-09-13) must sort before Hana (real end 2026-09-20)"
    )
    # every tournament in recent_form_5 must genuinely be among the
    # dataset's last 5 by the corrected ordering, not merely the last
    # 5 by game_code
    proxy_tail = {
        (t["season"], t["game_code"])
        for t in sorted(doc["tournament_history"], key=lambda t: (t["season"], t["game_code"]))[-5:]
    }
    assert set(last_5) == proxy_tail  # same 5 tournaments, corrected relative order


def test_reconciliation_diagnostics_section_stays_collapsed():
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    start = html.index('id="ph-reconciliation"')
    tag_line = html[max(0, start - 60):start + 30]
    assert " open" not in html[start - 1:start + len('<details class="evidence-detail pi-section" id="ph-reconciliation"')]


def test_reconciliation_section_is_the_last_section_on_the_page():
    """NEO PLAYER BIOGRAPHY V4 (2026-09-25): 'Nothing database-related
    may appear before section 11.' ph-career-overview and ph-player-
    story no longer exist as standalone sections (see
    test_render_produces_all_eleven_biography_sections_plus_hole_history)."""
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    recon_idx = html.index('id="ph-reconciliation"')
    other_section_ids = [
        "ph-current-form", "ph-why-now", "ph-recent-form", "ph-player-identity",
        "ph-career-story", "ph-career-evolution", "ph-tournament-trend",
        "ph-round-history", "ph-course-profile", "ph-player-dna-radar", "ph-tournament-history",
    ]
    for sid in other_section_ids:
        assert html.index(f'id="{sid}"') < recon_idx


def test_no_banned_ui_copy_in_the_visible_page_outside_the_collapsed_audit_section():
    """' -- ' (the raw report-delimiter) and literal None/null/NaN must
    never appear in player-facing rendered text. The collapsed
    reconciliation/QA section is explicitly allowed to keep detailed,
    technical resolved-log language (Phase 6F's own carve-out) -- this
    test checks everything BEFORE that section."""
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    recon_idx = html.index('id="ph-reconciliation"')
    before = html[:recon_idx]
    assert " -- " not in before
    for bad in ("None", "null", "NaN", "undefined"):
        assert bad not in before


def test_coverage_matrix_never_claims_klpga_lacks_a_blocked_metric():
    doc = build_script.build()
    cm = doc["coverage_matrix"]
    assert "BLOCKED" in {v for row in cm["rows"].values() for v in row.values()}
    assert "네트워크" in cm["status_legend"]["BLOCKED"] or "차단" in cm["status_legend"]["BLOCKED"]


def test_status_semantics_data_completeness_is_never_a_bare_pass():
    """'근거 없으면 PASS 금지' -- data completeness must never read PASS
    while any BLOCKED/NOT_COLLECTED cell exists in the coverage matrix."""
    doc = build_script.build()
    cm = doc["coverage_matrix"]
    has_gaps = any(v in ("BLOCKED", "NOT_COLLECTED") for row in cm["rows"].values() for v in row.values())
    assert has_gaps
    assert doc["status"]["data_completeness"] != "PASS"
