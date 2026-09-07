"""Tests for scripts/109_build_home_v4_data_terminal.py -- the NEO GOLF DATA
HOME V4 "KLPGA PERFORMANCE TERMINAL" candidate (branch
candidate/neo-home-v4-data-terminal). A completely separate product concept
from HOME V3 (candidate/neo-home-v3-shell, preserved untouched): V4 is
stricter about what it displays -- only player name, K-RANK, and (blank)
sponsor may show real values; NEO RANK/PERFORMANCE SG/FORM/VOL/TREND/EVENTS
are always the dash, regardless of whatever SG-warehouse feature data
exists, reflecting this session's own round-count-semantics findings.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "build_home_v4_data_terminal", ROOT / "scripts" / "109_build_home_v4_data_terminal.py"
)
build_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = build_mod
spec.loader.exec_module(build_mod)  # type: ignore[union-attr]

OUTPUT = ROOT / "candidate" / "home-v4-data-terminal"


def _home_html() -> str:
    return (OUTPUT / "index.html").read_text(encoding="utf-8")


def _summary() -> dict:
    return json.loads((OUTPUT / "data" / "home-v4-summary.json").read_text(encoding="utf-8"))


# --------------------------------------------------------- zero fabrication


def test_neo_rank_column_is_always_dash():
    html = _home_html()
    neo_cells = re.findall(r'<td><span class="t-dash">([^<]*)</span></td>\s*<th scope="row">', html)
    assert len(neo_cells) == 546
    assert set(neo_cells) == {"—"}


def test_performance_sg_form_vol_trend_events_are_always_dash_regardless_of_sg_data():
    """V4's stricter policy: unlike HOME V3, these columns never show a
    computed SG-warehouse value -- always the dash, for every row.
    (K-RANK also uses the same t-dash class for its 427 unjoined players,
    so the total is 5 always-dash columns plus those K-RANK gaps.)"""
    html = _home_html()
    summary = _summary()
    dash_cells = re.findall(r'<td class="t-dash">([^<]*)</td>', html)
    expected = 546 * 5 + summary["k_ranking_join_failure"]
    assert len(dash_cells) == expected
    assert set(dash_cells) == {"—"}


def test_row_view_never_uses_features_block_for_display():
    row = {
        "player_id": "p1", "player_name": "Test Player", "k_rank": 7,
        "features": {"recent_5_sg": 3.5, "volatility": 1.2, "sample_count": 10},
    }
    view = build_mod._row_view(row)
    assert view["performance_sg_display"] == "—"
    assert view["form_display"] == "—"
    assert view["vol_display"] == "—"
    assert view["trend_display"] == "—"
    assert view["events_display"] == "—"
    assert view["neo_rank_display"] == "—"


def test_no_tbd_or_na_or_zero_placeholder_strings():
    html = _home_html()
    assert "TBD" not in html
    assert "N/A" not in html


def test_summary_strip_numbers_are_real_and_match_join_summary():
    html = _home_html()
    summary = _summary()
    assert f'>{summary["population_count"]}<' in html
    assert f'>{summary["k_ranking_join_success"]}<' in html
    assert summary["historical_events"] == 97  # locked real count from the SG warehouse (NEO LAB only, see below)


def test_validation_status_shows_validating_not_a_fabricated_percentage():
    html = _home_html()
    strip = re.search(r'<div class="t-summary">.*?</div></div>', html, re.S).group()
    assert "VALIDATING" in strip
    assert "%" not in strip  # REVIEW PATCH: no percentage anywhere in the summary strip


# ------------------------------------------------- REVIEW PATCH: public provenance


def test_summary_strip_labels_never_imply_complete_klpga_historical_coverage():
    """The old 'KLPGA PLAYER DB' / 'HISTORICAL EVENTS' labels could read as
    official KLPGA totals. Both must be gone; the replacements must state
    their real, NEO-internal definition instead."""
    html = _home_html()
    assert "KLPGA PLAYER DB" not in html
    assert "HISTORICAL EVENTS" not in html
    assert "K-RANK COVERAGE" not in html
    assert "NEO PLAYER DATABASE" in html
    assert "K-RANK SNAPSHOT LINK" in html
    assert "NEO ARCHIVED EVENTS" in html


def test_home_does_not_expose_the_ambiguous_coverage_percentage():
    html = _home_html()
    assert "%" not in html


def test_home_does_not_expose_the_raw_archived_event_count():
    """Per the review's option (B): the SG warehouse's 97-tournament count
    must not appear on HOME at all -- it stays a dash until the public
    methodology is approved, since round-count semantics are still
    VALIDATING (see the Model Validation panel) and presenting 97 as if it
    were verified, complete coverage would contradict that."""
    html = _home_html()
    summary = _summary()
    assert f'>{summary["historical_events"]}<' not in html
    events_cell = re.search(r'<p class="t-summary__label">NEO ARCHIVED EVENTS</p>\s*<p[^>]*>([^<]*)</p>', html)
    assert events_cell is not None
    assert events_cell.group(1) == "—"


def test_home_never_exposes_1852_or_round_mismatch_or_redteam_wording():
    html = _home_html()
    for forbidden in ("1852", "disagreement rate", "WD/DQ/CUT", "red-team", "temporal mapping"):
        assert forbidden not in html, f"HOME leaked research-grade wording: {forbidden!r}"


def test_neo_lab_retains_the_full_evidence_including_1852_and_97():
    """Section 2's instruction is explicit: 'Do not hide evidence;
    separate public status from research evidence.' NEO LAB must still
    carry the real numbers and the detailed engineering context."""
    lab_html = (OUTPUT / "neo-lab" / "index.html").read_text(encoding="utf-8")
    assert "1852" in lab_html
    assert "97" in lab_html
    assert "disagreement rate" in lab_html
    assert "WD/DQ/CUT" in lab_html
    assert "2026-W35" in lab_html  # real snapshot label also documented here


def test_evidence_link_architecture_home_rows_link_to_matching_neo_lab_anchor():
    home_html = _home_html()
    lab_html = (OUTPUT / "neo-lab" / "index.html").read_text(encoding="utf-8")
    for name, _status, _evidence in build_mod.VALIDATION_ROWS:
        anchor = build_mod._validation_anchor(name)
        assert f'href="/neo-lab/#{anchor}"' in home_html, f"missing HOME evidence link for {name}"
        assert f'id="{anchor}"' in lab_html, f"missing NEO LAB anchor for {name}"


def test_ranking_snapshot_label_is_a_real_dated_identifier_not_vague_text():
    html = _home_html()
    assert "official snapshot" not in html.lower()
    # the real ranking_date value ("2026-W35") must appear verbatim near the K-RANK cell
    assert re.search(r"\d{4}-W\d{2}", html)


def test_home_validation_panel_carries_no_evidence_prose_only_lab_does():
    home_panel = re.search(
        r'<section class="t-section" aria-labelledby="validation-heading">.*?</section>', _home_html(), re.S
    ).group()
    lab_html = (OUTPUT / "neo-lab" / "index.html").read_text(encoding="utf-8")
    lab_panel = re.search(
        r'<section class="t-section" aria-labelledby="validation-heading">.*?</section>', lab_html, re.S
    ).group()
    assert "t-validation-desc" not in home_panel
    assert "t-validation-desc" in lab_panel


# --------------------------------------------------------------- K-RANK / sponsor


def test_official_k_rank_displays_when_present():
    html = _home_html()
    real_k = re.findall(r'<td class="t-krank-real">([^<]*)</td>', html)
    summary = _summary()
    assert len(real_k) == summary["k_ranking_join_success"]
    assert all(v.isdigit() for v in real_k)


def test_blank_sponsor_allowed_for_all_rows_no_verified_source_exists():
    assert build_mod.SPONSOR_SOURCE == {}
    html = _home_html()
    sponsor_cells = re.findall(r'<td class="t-sponsor-cell">([^<]*)</td>', html)
    assert len(sponsor_cells) == 546
    assert set(sponsor_cells) == {""}


def test_sponsor_never_inferred_for_unknown_player():
    row = {"player_id": "unknown", "player_name": "X", "k_rank": None}
    assert build_mod._row_view(row)["sponsor"] == ""


# ----------------------------------------------------------- photo policy


def test_neutral_silhouette_fallback_no_photo_hotlink():
    html = _home_html()
    assert "<img" not in html
    assert "klpga.co.kr" not in html
    avatars = re.findall(r'<span class="t-avatar"[^>]*>(.*?)</span>', html)
    assert len(avatars) == 546
    assert all("<svg" in a for a in avatars)


def test_no_unauthorized_photo_row_view_always_unverified():
    row = {"player_id": "p1", "player_name": "X", "k_rank": None}
    assert build_mod._row_view(row)["photo_license_status"] == "UNVERIFIED"


# ------------------------------------------------------------ chart integrity


def test_analytics_grid_never_draws_a_fabricated_series():
    html = _home_html()
    grid = re.search(r'<section class="t-section" aria-labelledby="analytics-heading">.*?</section>', html, re.S).group()
    assert "<polyline" not in grid
    assert "<path" not in grid
    assert grid.count("데이터 검증 후 공개") == 4  # one honest empty-state per chart cell
    assert grid.count("VALIDATING") >= 4


def test_player_inspector_chart_is_also_empty_no_fake_history():
    html = _home_html()
    inspector = re.search(r'<aside class="t-inspector".*?</aside>', html, re.S).group()
    assert "<polyline" not in inspector
    assert "<path" not in inspector
    assert "데이터 검증 후 공개" in inspector
    for label in ("SG TOTAL", "SG OTT", "SG APP", "SG ARG", "SG PUTT", "SHORT", "MID", "LONG",
                  "CUT", "TOP20", "TOP10", "TOP5", "WIN"):
        assert label in inspector


# --------------------------------------------------------- wording / policy


def test_no_betting_or_gambling_wording_anywhere():
    html = _home_html().lower()
    for word in ("bet", "odds", "wager", "gambl", "casino"):
        assert word not in html


def test_no_internal_engineering_blocker_strings_exposed():
    html = _home_html()
    for forbidden in ("BLOCKED_FORMULA_NOT_APPROVED", "K_TEMPORAL_MAPPING_UNVERIFIED",
                       "BLOCKED_ROUND_COUNT_SEMANTICS", "NOT_FOUND_IN_AVAILABLE_OFFICIAL_SNAPSHOT"):
        assert forbidden not in html


def test_model_validation_panel_uses_only_public_safe_states():
    html = _home_html()
    panel = re.search(r'<section class="t-section" aria-labelledby="validation-heading">.*?</section>', html, re.S).group()
    statuses = re.findall(r'<span class="t-badge [^"]*">([^<]*)</span>', panel)
    assert len(statuses) == 6
    assert set(statuses) <= {"VERIFIED", "VALIDATING", "NOT PUBLISHED"}


def test_model_validation_rows_match_the_required_six():
    names = {name for name, _, _ in build_mod.VALIDATION_ROWS}
    assert names == {"DATA COVERAGE", "TEMPORAL INTEGRITY", "ROUND SEMANTICS",
                      "OUTCOME VALIDATION", "NEO RANKING V2", "PUBLICATION"}


def test_hero_copy_present_but_does_not_dominate_above_the_fold():
    html = _home_html()
    assert "순위 너머의 경기력을 측정하다" not in html  # V4 deliberately omits the V3 hero slogan from the terminal shell
    assert "KLPGA PERFORMANCE TERMINAL" in html


# ---------------------------------------------------------------- navigation


def test_nav_labels_match_required_spec():
    html = _home_html()
    nav = re.search(r'<nav class="t-nav".*?</nav>', html, re.S).group()
    for label in ("PLAYERS", "TOURNAMENTS", "NEO LAB", "ABOUT"):
        assert f">{label}<" in nav


def test_no_internal_link_from_home_or_neo_lab_is_broken():
    files_present = {"/" + str(p.relative_to(OUTPUT)).replace("\\", "/") for p in OUTPUT.rglob("*") if p.is_file()}

    def missing(html: str) -> list[str]:
        hrefs = set(re.findall(r'href="(/[^"#]*)"', html))
        out = []
        for h in hrefs:
            candidate = (h + "index.html") if h.endswith("/") else h
            if candidate not in files_present:
                out.append(h)
        return out

    assert missing(_home_html()) == []
    assert missing((OUTPUT / "neo-lab" / "index.html").read_text(encoding="utf-8")) == []


# -------------------------------------------------------- historical pages


def test_preserved_routes_exist():
    for route in ("tournaments/index.html", "ranking/index.html", "deep-dive/index.html",
                  "about/index.html", "neo-lab/index.html"):
        assert (OUTPUT / route).is_file(), route


def test_historical_tournament_stage_pages_preserved():
    assert (OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / "final" / "index.html").is_file()
    assert (OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open" / "pre" / "index.html").is_file()


# ---------------------------------------------------------------- responsive


def test_desktop_board_and_mobile_list_both_present_in_markup():
    html = _home_html()
    assert 't-board-scroll' in html
    assert 'data-t-mobile-list' in html
    desktop_rows = html.count("data-player-row")
    mobile_rows = html.count('class="t-mobile-row"')
    assert mobile_rows == 546
    assert desktop_rows == 546 * 2  # one <tr> + one mobile row per player


def test_nav_toggle_present_for_mobile():
    html = _home_html()
    assert "data-t-nav-toggle" in html
    css = (ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v4.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in css


# ------------------------------------------------------------ accessibility


def test_board_rows_are_keyboard_focusable_with_role_button():
    html = _home_html()
    assert html.count('tabindex="0"') >= 546
    assert html.count('role="button"') >= 546


def test_inspector_close_button_is_a_real_button_element():
    html = _home_html()
    assert '<button type="button" class="t-inspector__close"' in html


# ------------------------------------------------------------- isolation


def test_v4_build_never_imports_v2_validation_or_v3_shell_modules():
    # A docstring mention of V3 (documenting that it is preserved) is fine
    # and expected -- what must never appear is an actual import/exec-load
    # of a V2 validation script or the V3 builder module.
    src = (ROOT / "scripts" / "109_build_home_v4_data_terminal.py").read_text(encoding="utf-8")
    for forbidden in (
        "import scripts.103", "103_round_count_audit.py",
        "104_official_archive_reconstruction.py", "105_round_count_audit_v2.py",
        "106_round_count_mismatch_diagnostic.py", "round_count_audit_lib",
        "108_build_home_v3_shell.py", "home-v3.css", "home-v3.js",
    ):
        assert forbidden not in src, f"HOME V4 build script must not reference: {forbidden}"


def test_production_home_ranking_module_unmodified():
    from klpga.website_v2 import home_ranking
    assert home_ranking.FORMULA_STATE == "BLOCKED_FORMULA_NOT_APPROVED"
    assert home_ranking.NEO_RANKING_VERSION is None


def test_v4_output_path_is_distinct_from_v3_output_path():
    assert build_mod.OUTPUT.name == "home-v4-data-terminal"
    assert build_mod.OUTPUT != ROOT / "candidate" / "home-v3-shell"


# ------------------------------------------------- k-rank missing-state


def test_missing_k_rank_never_uses_a_synthetic_numeric_sentinel():
    html = _home_html()
    for sentinel in ("999999", "9999", "-1"):
        assert f'data-k-rank="{sentinel}"' not in html


def test_missing_k_rank_rows_omit_the_data_k_rank_attribute_entirely():
    html = _home_html()
    rows = re.findall(r"<tr data-player-row[^>]*>", html)
    assert len(rows) == 546
    with_rank = [r for r in rows if "data-k-rank=" in r]
    without_rank = [r for r in rows if "data-k-rank=" not in r]
    summary = _summary()
    assert len(with_rank) == summary["k_ranking_join_success"]
    assert len(without_rank) == 546 - summary["k_ranking_join_success"]
    # a row with a real rank always still carries a dash-free display value
    for r in with_rank:
        assert 'data-k-rank-display="—"' not in r
    # a row missing a rank always shows the em-dash display, never a number
    for r in without_rank:
        assert 'data-k-rank-display="—"' in r


def test_missing_k_rank_mobile_rows_also_omit_the_sentinel_attribute():
    html = _home_html()
    mobile_rows = re.findall(r'<div class="t-mobile-row" data-player-row[^>]*>', html)
    assert len(mobile_rows) == 546
    assert not any("999999" in r for r in mobile_rows)


def test_sort_js_treats_missing_k_rank_as_a_distinct_missing_state():
    js = (ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v4.js").read_text(
        encoding="utf-8"
    )
    # missing-state must be checked explicitly, not derived from Number(undefined)
    assert "dataset.kRank !== undefined" in js
    assert "aHas !== bHas" in js
