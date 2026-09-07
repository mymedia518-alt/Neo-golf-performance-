"""Tests for scripts/108_build_home_v3_shell.py -- the NEO GOLF DATA HOME V3
candidate shell (branch candidate/neo-home-v3-shell). This is a candidate
UI/UX track, completely separate from NEO Ranking V2 validation: these
tests enforce the CORE RULE (fake data = 0, UI completeness = 100%),
verify real player identity data is used (never invented), verify the
sponsor/photo policies, verify existing routes are preserved, verify
responsive structure, and verify the NEO Ranking V2 validation files and
production home_ranking.py were never touched by this track.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "build_home_v3_shell", ROOT / "scripts" / "108_build_home_v3_shell.py"
)
build_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = build_mod
spec.loader.exec_module(build_mod)  # type: ignore[union-attr]

OUTPUT = ROOT / "candidate" / "home-v3-shell"


def _built_home_html() -> str:
    return (OUTPUT / "index.html").read_text(encoding="utf-8")


# ------------------------------------------------------------ core rule


def test_neo_rank_is_never_a_fabricated_number():
    html = _built_home_html()
    neo_rank_cells = re.findall(r'<td><span class="v3-pending">([^<]*)</span></td>', html)
    assert len(neo_rank_cells) > 0
    assert set(neo_rank_cells) == {"—"}, "NEO RANK must always be the dash -- the formula is not approved"


def test_no_tbd_or_na_placeholder_strings_anywhere():
    html = _built_home_html()
    assert "TBD" not in html
    assert "N/A" not in html


def test_trend_column_is_always_dash_no_verified_trend_source_exists():
    html = _built_home_html()
    trend_cells = re.findall(r'<span class="v3-trend-chip">([^<]*)</span>', html)
    assert len(trend_cells) > 0
    assert set(trend_cells) == {"—"}


def test_k_rank_dash_and_real_counts_match_join_summary():
    html = _built_home_html()
    summary_text = (OUTPUT / "data" / "home-v3-summary.json").read_text(encoding="utf-8")
    import json
    summary = json.loads(summary_text)
    k_rank_cells = re.findall(r'<td>([^<]*)</td>\s*<td class="v3-metric"', html)
    dash_count = sum(1 for c in k_rank_cells if c == "—")
    real_count = sum(1 for c in k_rank_cells if c != "—")
    assert dash_count == summary["k_ranking_join_failure"]
    assert real_count == summary["k_ranking_join_success"]


def test_performance_race_section_never_draws_a_fake_series():
    html = _built_home_html()
    race_section = re.search(r'<section class="v3-section" aria-labelledby="v3-race-heading">.*?</section>', html, re.S).group()
    # only structural/decorative elements (axes, grid, one pulse dot) --
    # never a <polyline>/<path> that would represent an invented player series.
    assert "<polyline" not in race_section
    assert "<path" not in race_section
    assert "데이터 검증 후 공개" in race_section


def test_latest_insights_never_fabricates_article_content():
    html = _built_home_html()
    insights = re.search(r'<section class="v3-section" aria-labelledby="v3-insights-heading">.*?</section>', html, re.S).group()
    assert "검증된 인사이트가 준비되면" in insights
    # no article title/date/author-shaped content
    assert not re.search(r'<h4>(?!.{0,3}</h4>)', insights.replace("최신 인사이트", ""))


# ---------------------------------------------------------------- sponsor


def test_sponsor_source_is_empty_no_verified_klpga_profile_source_exists():
    assert build_mod.SPONSOR_SOURCE == {}


def test_no_sponsor_cell_contains_a_value_since_no_verified_source_exists():
    html = _built_home_html()
    sponsor_cells = re.findall(r'<td class="v3-sponsor-cell">([^<]*)</td>', html)
    assert len(sponsor_cells) > 0
    assert set(sponsor_cells) == {""}, "every sponsor cell must be blank -- no verified KLPGA-profile sponsor source exists"


def test_row_view_never_infers_a_sponsor_for_an_unknown_player():
    row = {"player_id": "does-not-exist", "player_name": "Test Player", "features": None, "k_rank": None}
    view = build_mod._row_view(row)
    assert view["sponsor"] == ""


# ------------------------------------------------------------- player photo


def test_every_player_row_renders_the_neutral_silhouette_not_a_photo():
    html = _built_home_html()
    avatar_count = html.count('<span class="v3-avatar"')
    # one avatar per desktop row -- must be the inline silhouette svg, not an <img>
    assert avatar_count > 0
    avatars = re.findall(r'<span class="v3-avatar"[^>]*>(.*?)</span>', html)
    assert all("<svg" in a for a in avatars)
    assert "<img" not in html.split('id="v3-primary-nav"')[1].split("</table>")[0]


def test_row_view_photo_license_status_is_always_unverified():
    row = {"player_id": "p1", "player_name": "Someone", "features": None, "k_rank": None}
    view = build_mod._row_view(row)
    assert view["photo_license_status"] == "UNVERIFIED"


# -------------------------------------------------------- real player data


def test_real_canonical_player_names_are_used_not_invented():
    html = _built_home_html()
    assert "Atthaya Thitikul" in html or "ATTHAYA THITIKUL" in html.upper()
    summary_path = OUTPUT / "data" / "home-v3-summary.json"
    import json
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["population_count"] == 546


def test_real_performance_sg_values_are_not_all_zero_or_dash():
    html = _built_home_html()
    metric_cells = re.findall(r'<td class="v3-metric" title="[^"]*">([^<]*)</td>', html)
    real_values = [c for c in metric_cells if c != "—"]
    assert len(real_values) > 0
    assert not all(v in ("0.00", "+0.00", "0") for v in real_values)


# --------------------------------------------------------- preserved routes


def test_preserved_routes_exist_in_the_candidate_output():
    for route in ("tournaments/index.html", "ranking/index.html", "deep-dive/index.html",
                  "about/index.html", "neo-lab/index.html"):
        assert (OUTPUT / route).is_file(), f"missing preserved route: {route}"


def test_historical_tournament_stage_pages_still_reachable():
    kg_final = OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / "final" / "index.html"
    assert kg_final.is_file()


def test_no_internal_link_from_home_or_neo_lab_is_broken():
    files_present = {"/" + str(p.relative_to(OUTPUT)).replace("\\", "/") for p in OUTPUT.rglob("*") if p.is_file()}

    def missing_links(html: str) -> list[str]:
        hrefs = set(re.findall(r'href="(/[^"#]*)"', html))
        missing = []
        for h in hrefs:
            candidate = (h + "index.html") if h.endswith("/") else h
            if candidate == "/index.html" and h == "/":
                candidate = "/index.html"
            if candidate not in files_present:
                missing.append(h)
        return missing

    assert missing_links(_built_home_html()) == []
    assert missing_links((OUTPUT / "neo-lab" / "index.html").read_text(encoding="utf-8")) == []


# ------------------------------------------------------------- responsive


def test_desktop_table_and_mobile_cards_both_present_in_markup():
    # Both the desktop table and the mobile card list are server-rendered
    # up front (one row's worth of markup each, per player) -- CSS media
    # queries decide which is visible, so mobile never depends on JS to
    # produce a readable layout.
    html = _built_home_html()
    assert 'class="v3-table-scroll v3-desktop-only"' in html
    assert "data-v3-rank-cards" in html
    desktop_rows = html.count("data-player-row")
    card_rows = html.count('class="v3-rank-card"')
    assert card_rows > 0
    assert card_rows * 2 == desktop_rows  # one <tr> + one card per player


def test_nav_toggle_and_reduced_motion_rule_present():
    css = (ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v3.css").read_text(encoding="utf-8")
    assert "data-v3-nav-toggle" not in css  # selector lives in JS/HTML, not CSS
    assert "prefers-reduced-motion: reduce" in css
    assert ".v3-race-pulse { animation: none" in css.replace("\n", " ") or "animation: none" in css
    html = _built_home_html()
    assert "data-v3-nav-toggle" in html
    assert 'data-v3-race-svg' in html


def test_nav_labels_match_the_required_brand_spec():
    html = _built_home_html()
    nav = re.search(r'<nav class="v3-nav".*?</nav>', html, re.S).group()
    for label in ("PLAYERS", "TOURNAMENTS", "NEO LAB", "ABOUT"):
        assert f">{label}<" in nav


def test_hero_copy_matches_the_required_brand_spec():
    html = _built_home_html()
    assert "순위 너머의 경기력을 측정하다" in html
    assert "MEASURE PERFORMANCE. NOT RESULTS." in html
    # no tournament win-probability numbers in the hero section
    hero = re.search(r'<section class="v3-hero">.*?</section>', html, re.S).group()
    assert "%" not in hero


# --------------------------------------------------- isolation from V2 track


def test_home_v3_never_imports_or_touches_v2_validation_scripts():
    src = (ROOT / "scripts" / "108_build_home_v3_shell.py").read_text(encoding="utf-8")
    for forbidden in ("103_round_count_audit", "104_official_archive_reconstruction",
                       "105_round_count_audit_v2", "106_round_count_mismatch_diagnostic",
                       "107_", "NEO_RANKING_V2_", "round_count_audit_lib"):
        assert forbidden not in src, f"HOME V3 build script must not reference V2 validation artifact: {forbidden}"


def test_production_home_ranking_module_unmodified_by_this_track():
    # home_ranking.py is READ (imported), never edited -- FORMULA_STATE and
    # NEO_RANKING_VERSION must remain exactly as production defines them.
    from klpga.website_v2 import home_ranking
    assert home_ranking.FORMULA_STATE == "BLOCKED_FORMULA_NOT_APPROVED"
    assert home_ranking.NEO_RANKING_VERSION is None


def test_sg_warehouse_and_v1_baseline_paths_not_referenced_for_writing():
    src = (ROOT / "scripts" / "108_build_home_v3_shell.py").read_text(encoding="utf-8")
    assert "historical_sg_warehouse_corrected.json" in src  # read-only input, expected
    assert "write_text" not in src.split("historical_sg_warehouse_corrected.json")[0][-200:]
    assert "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1" not in src
    assert "NEO_RANKING_V1_REDTEAM_BACKTEST" not in src
