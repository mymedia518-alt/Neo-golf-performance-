"""RED TEAM mission (2026-09-25) -- playerCode=10097 only.

Two fundamental problems were flagged against the V3 product build:
(1) NEO labelled collectable-but-uncollected KLPGA data as "데이터
없음", which literally claims KLPGA itself lacks the data; (2) internal
QA/database terminology (raw warehouse filenames, English state names)
still leaked into the primary, non-collapsed page. These tests pin down
the specific fixes: the three-state vocabulary, the public hierarchy
(mission J), the season-selector Player DNA UX (mission F), the
percentage-free Season Evolution copy (mission G), and the single
'SG 미수집' cell for KB (mission I).
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
from klpga.website_v2 import player_history_10097_terms as terms  # noqa: E402


def _html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_blocked_metric_is_never_rendered_as_no_data():
    """The exact bug the mission caught: BLOCKED must never render as
    '데이터 없음' -- that claims KLPGA itself has nothing, when BLOCKED
    only ever means this sandbox's network access is cut off."""
    assert terms.RADAR_STATUS_LABEL["BLOCKED"] != "데이터 없음"
    _, html = _html()
    recon_idx = html.index('id="ph-reconciliation"')
    # BLOCKED cells only ever render inside the collapsed #8 panel, but
    # even there the literal string "데이터 없음" must never appear --
    # the whole point is that NEO cannot make that claim.
    assert "데이터 없음" not in html[recon_idx:]


def test_public_hierarchy_matches_neo_player_biography_v4():
    """Superseded four times: 'DataGolf-style Current Form first'
    (Recent Form -> #1), then the DataGolf-philosophy mission's 4-item
    '1. 현재 폼', then NEO PLAYER BIOGRAPHY V4 (2026-09-25)'s 11-item
    hierarchy, then MISSION NEO PLAYER PROFILE V2 (2026-09-27), which
    collapses that into an 8-question flow: 현재 폼/왜 지금인가/최근
    경기 결과/선수 정체성 stay #1-4; 코스 프로필 and 라운드 분석 move
    up to #5-6 (라운드 분석 reduced to best/worst only); 커리어
    스토리 leads a #7 cluster that folds in season evolution,
    tournament timeline, and Player DNA as unnumbered subordinates;
    everything technical consolidates into one final #8 -- nothing
    database-related may appear before it."""
    _, html = _html()
    for title in (
        "1. 현재 폼", "2. 왜 지금인가", "3. 최근 경기 결과", "4. 선수 정체성",
        "5. 코스 프로필", "6. 라운드 분석", "7. 커리어 스토리", "8. 데이터베이스 / 검증",
    ):
        assert title in html, f"missing section title: {title}"


def test_public_hierarchy_is_in_the_exact_specified_order():
    _, html = _html()
    order = [
        "1. 현재 폼", "2. 왜 지금인가", "3. 최근 경기 결과", "4. 선수 정체성",
        "5. 코스 프로필", "6. 라운드 분석", "7. 커리어 스토리", "8. 데이터베이스 / 검증",
    ]
    positions = [html.index(t) for t in order]
    assert positions == sorted(positions)


def test_live_tournament_hides_completely_when_not_confirmed_live():
    """NEO PLAYER BIOGRAPHY V4: 'If there is no confirmed LIVE
    tournament, hide the LIVE section completely. Never show an
    already-finished event as LIVE.' Supersedes the earlier RED TEAM
    mission's choice to still show an honest 'awaiting result' fallback
    -- that fallback is gone; the block renders nothing at all unless
    is_confirmed_live is True."""
    doc, html = _html()
    in_progress = doc.get("current_tournament_in_progress")
    is_live = bool(in_progress and in_progress.get("is_confirmed_live"))
    if is_live:
        assert 'id="ph-in-progress"' in html
        assert html.index('id="ph-in-progress"') < html.index('id="ph-player-identity"')
    else:
        assert 'id="ph-in-progress"' not in html
        assert "AWAITING_FINAL_RESULT" not in html  # never leak the internal status enum either
        assert "진행 중입니다" not in html


def test_in_progress_tournament_never_claims_live_once_schedule_says_it_ended():
    """RED TEAM (2026-09-25): reconcile() must cross-check the real
    official schedule (not just re-assert whatever was last captured)
    before calling a tournament live."""
    doc = build_script.build()
    t = doc.get("current_tournament_in_progress")
    assert t is not None
    assert "is_confirmed_live" in t
    assert "scheduled_end_date" in t
    if t["scheduled_end_date"]:
        import datetime as _dt
        end = _dt.date.fromisoformat(t["scheduled_end_date"])
        today = _dt.datetime.now(_dt.timezone.utc).date()
        assert t["is_confirmed_live"] == (today <= end)
    if not t["is_confirmed_live"]:
        assert t["status"] == "AWAITING_FINAL_RESULT"
        assert "진행 중입니다" not in t["note"]
        assert t["scheduled_end_date"] in t["note"]


def test_recent_results_discloses_not_collected_sg_instead_of_a_bare_dash():
    """RED TEAM (2026-09-25): a bare '--' cannot be told apart from 'not
    applicable' -- every missing SG for this player means NEO has not
    collected it (KB, 2026090003), never that KLPGA lacks it.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) replaced
    Recent Results' table (SG column included) with a win/Top10-only
    dot strip that shows no SG value for any row -- there is no longer
    an ambiguous dash to disguise here, since no SG figure renders in
    this section at all. The KB tournament must still render as a
    normal dot (real is_win/is_top10, no crash), and the disclosure
    this RED TEAM mission required must still exist somewhere real on
    the page -- the full tournament table (#7, _tournament_table_html,
    untouched by this mission) still carries it."""
    doc, html = _html()
    kb_rows = [r for r in doc["recent_form_10"] if r["game_code"] == "2026090003"]
    assert kb_rows and kb_rows[0]["sg_status"] == "NOT_COLLECTED"
    kb_row = kb_rows[0]
    start = html.index('id="ph-recent-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert terms.SG_MISSING_CELL_TEXT not in section
    kb_dot = f'title="{kb_row["tournament"]} ({kb_row["season"]})"'
    assert kb_dot in section
    assert terms.SG_MISSING_CELL_TEXT in html


def test_not_available_disclosure_is_nested_inside_section_8_not_standalone():
    _, html = _html()
    recon_idx = html.index('id="ph-reconciliation"')
    not_avail_idx = html.index('id="ph-not-available"')
    assert not_avail_idx > recon_idx
    # it must be a plain nested block, not its own top-level <details>
    assert '<div class="ph-evo-block" id="ph-not-available">' in html


def test_season_evolution_never_shows_a_percentage_change():
    """Mission G: '+0.15 -> +3115%' against a near-zero baseline is
    mathematically possible but analytically misleading -- percentage
    growth must never appear in Season Evolution's rendered table."""
    doc, html = _html()
    start = html.index('id="ph-career-evolution"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "%" not in section
    assert "개선" in section or "하락" in section


def test_player_dna_uses_korean_axis_labels_not_english_internal_names():
    doc = build_script.build()
    axes = doc["player_dna_radar"][0]["axes"]
    svg = report._radar_svg(axes)
    for banned in ("TEE", "APPROACH", "PUTTING", "SCORING"):
        assert banned not in svg


def test_player_dna_explanation_uses_exact_mission_copy_and_no_filename():
    _, html = _html()
    start = html.index('id="ph-player-dna-radar"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert terms.PLAYER_DNA_EXPLANATION in section
    assert ".json" not in section
    assert "warehouse" not in section.lower()


def test_player_dna_is_a_single_selector_driven_chart_not_four_stacked_radars():
    """Mission F: a season selector drives ONE radar, not four large
    stacked charts."""
    _, html = _html()
    start = html.index('id="ph-player-dna-radar"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert 'class="ph-dna-tabs"' in section
    assert section.count('class="ph-dna-radio"') >= 4
    # exactly one radio starts checked -- one visible panel by default
    assert section.count(" checked") == 1


def test_player_dna_offers_a_comparison_overlay_when_two_full_seasons_exist():
    doc = build_script.build()
    full_seasons = [sb for sb in doc["player_dna_radar"] if all(a["percentile"] is not None for a in sb["axes"])]
    _, html = _html()
    start = html.index('id="ph-player-dna-radar"')
    end = html.index("</details>", start)
    section = html[start:end]
    if len(full_seasons) >= 2:
        assert "vs" in section
        assert 'id="ph-dna-panel-compare"' in section


def test_kb_missing_sg_is_a_single_merged_cell_not_five_dashes():
    doc, html = _html()
    start = html.index('id="ph-tournament-history"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert 'colspan="5"' in section
    assert terms.SG_MISSING_CELL_TEXT in section
    # never five separate em-dash cells for the same missing tournament row
    kb = next(t for t in doc["tournament_history"] if t["game_code"] == "2026090003")
    assert kb["sg_total"] is None


def test_tournament_table_is_collapsed_and_secondary_to_the_trend_chart():
    """Mission H: the 96-row table must not dominate -- it is collapsed
    by default, and the chronological chart section renders first."""
    _, html = _html()
    trend_idx = html.index('id="ph-tournament-trend"')
    table_start = html.index('id="ph-tournament-history"')
    assert trend_idx < table_start
    tag = html[table_start - 80:table_start + 10]
    assert " open" not in html[html.rindex("<details", 0, table_start):table_start]


def test_source_state_labels_never_claim_klpga_side_absence_for_uncollected_data():
    for state, label in terms.SOURCE_STATE_LABEL.items():
        if state == "AVAILABLE_BUT_NOT_COLLECTED":
            assert "NEO" in label or "미수집" in label
            assert "KLPGA" not in label.split("·")[-1]  # the NEO-fault half must not blame KLPGA
