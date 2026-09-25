"""PLAYER HISTORY GOLD STANDARD V1 -- playerCode=10097 only.

Covers scripts/build_10097_player_history.py (real-data-only builder)
and src/klpga/website_v2/player_history_10097_report.py (renderer).
Player Intelligence is no longer the goal for this player -- these
tests check the new history report, not the old question-organized one.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.website_v2 import player_history_10097_report as report  # noqa: E402

_SPECULATIVE_WORDS = ("아마", "추정됩니다", "추측", "예상됩니다", "가능성이 높습니다", "확인할 수 없습니다")


def test_build_returns_only_player_10097():
    doc = build_script.build()
    assert doc["player_id"] == "10097"
    assert doc["player_name"] == "김민선7"
    assert "playerCode=10097" in doc["scope_note"]


def test_career_overview_has_real_four_season_history():
    doc = build_script.build()
    rows = doc["career_overview"]["season_rows"]
    assert len(rows) == 4
    seasons = [r["season"] for r in rows]
    assert seasons == sorted(seasons)
    assert seasons[0] == doc["career_overview"]["earliest_season_on_record"]
    # every season row's event/win/top10 counts must be non-negative integers
    for r in rows:
        assert r["events"] >= 0 and isinstance(r["events"], int)
        assert r["wins"] >= 0 and isinstance(r["wins"], int)
        assert r["top10"] >= 0 and isinstance(r["top10"], int)
        assert r["top10"] <= r["events"]
        assert r["wins"] <= r["top10"] or r["top10"] == 0 and r["wins"] == 0 or r["wins"] <= r["events"]


def test_career_overview_totals_reconcile_with_season_rows():
    doc = build_script.build()
    co = doc["career_overview"]
    rows = co["season_rows"]
    assert co["total_wins"] == sum(r["wins"] for r in rows)
    assert co["total_top10"] == sum(r["top10"] for r in rows)
    assert co["total_events"] == len(doc["tournament_history"])


def test_data_floor_note_never_claims_debut():
    doc = build_script.build()
    note = doc["career_overview"]["data_floor_note"]
    assert "데뷔" in note  # must mention debut only to explicitly deny it
    assert "아니다" in note or "아닙니다" in note or "근거는 아닙니다" in note


def test_current_snapshot_is_single_point_in_time_never_extrapolated():
    doc = build_script.build()
    snap = doc["current_snapshot"]
    assert snap is not None
    assert "스냅샷" in snap["as_of_note"]
    # explicit disclosure it does not extend to other seasons
    assert "과거" in snap["as_of_note"]


def test_career_evolution_covers_all_five_sg_components():
    doc = build_script.build()
    evo = doc["career_evolution"]
    assert set(evo.keys()) == {"avg_total", "avg_ott", "avg_app", "avg_arg", "avg_putt"}
    for c, data in evo.items():
        assert len(data["series"]) == 4
        assert len(data["deltas"]) == 3
        assert data["current_direction"] in {"UP", "DOWN", "FLAT"}


def test_evolution_deltas_are_real_consecutive_differences():
    doc = build_script.build()
    for data in doc["career_evolution"].values():
        series = data["series"]
        for (a, b), d in zip(zip(series, series[1:]), data["deltas"]):
            assert round(b["value"] - a["value"], 2) == d["delta"]


def test_season_replay_only_covers_seasons_with_at_least_four_events():
    doc = build_script.build()
    for r in doc["season_replay"]:
        assert r["event_count"] >= 4
        assert len(r["quartiles"]) <= 4
        assert 0 <= r["top10_rate_pct"] <= 100


def test_tournament_history_is_chronological_and_matches_win_flags():
    doc = build_script.build()
    th = doc["tournament_history"]
    seasons = [t["season"] for t in th]
    assert seasons == sorted(seasons)
    win_count = sum(1 for t in th if t["is_win"])
    assert win_count == doc["career_overview"]["total_wins"]
    for t in th:
        if t["is_win"]:
            assert t["is_top10"]  # a win is always a top-10 finish


def test_round_history_extremes_are_internally_consistent():
    doc = build_script.build()
    rh = doc["round_history"]
    assert rh["best_round"]["sg_total"] >= rh["worst_round"]["sg_total"]
    if rh.get("largest_collapse"):
        assert rh["largest_collapse"]["delta"] <= 0
    if rh.get("most_improved_round"):
        assert rh["most_improved_round"]["delta"] >= 0
    if rh.get("largest_recovery"):
        assert rh["largest_recovery"]["delta"] > 0


def test_player_evolution_never_invents_a_decline_that_does_not_exist():
    doc = build_script.build()
    pe = doc["player_evolution"]
    deltas = [d["delta"] for d in doc["career_evolution"]["avg_total"]["deltas"]]
    has_real_decline = any(d < 0 for d in deltas)
    assert pe["no_decline_observed"] == (not has_real_decline)
    if not has_real_decline:
        assert pe["biggest_decline"] is None


def test_player_story_is_sorted_and_has_no_duplicate_season_label_pairs():
    doc = build_script.build()
    story = doc["player_story"]
    seasons = [m["season"] for m in story]
    assert seasons == sorted(seasons)
    keys = [(m["season"], m["label"]) for m in story]
    assert len(keys) == len(set(keys))


def test_hole_history_scoped_to_exactly_one_real_tournament():
    doc = build_script.build()
    hh = doc["hole_history"]
    if hh is not None:
        assert hh["total_hole_records"] == sum(r["holes_recorded"] for r in hh["rounds"])
        assert "1개" in hh["capture_note"]


def test_not_available_list_is_disclosed_and_non_empty():
    doc = build_script.build()
    assert len(doc["not_available"]) >= 5
    joined = " ".join(doc["not_available"])
    for term in ("드라이빙", "보기율", "전반", "후반", "컷"):
        assert term in joined


def test_report_never_uses_banned_speculative_language():
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    for word in _SPECULATIVE_WORDS:
        assert word not in html, f"banned speculative phrase found: {word!r}"


def test_render_produces_all_eight_pages_plus_hole_history():
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    for section_id in [
        "ph-career-overview", "ph-career-evolution", "ph-season-replay",
        "ph-tournament-history", "ph-round-history", "ph-player-evolution",
        "ph-career-dna", "ph-player-story", "ph-hole-history", "ph-not-available",
    ]:
        assert f'id="{section_id}"' in html, f"missing section {section_id}"


def test_render_has_no_page_breaking_raw_python_repr_leak():
    """A common HTML-string bug: an f-string that accidentally renders a
    Python dict/list repr (e.g. "{'a': 1}") instead of formatted text."""
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    assert not re.search(r"\{'[a-z_]+':", html)


def test_career_evolution_renders_sg_total_first_not_alphabetically():
    """Regression: json.dumps(sort_keys=True) on disk alphabetizes
    avg_app/avg_arg/avg_ott/avg_putt/avg_total, which would silently put
    SG APP before SG Total in the rendered page if the renderer trusted
    dict iteration order instead of an explicit display sequence."""
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    start = html.index('id="ph-career-evolution"')
    end = html.index("</details>", start)
    section = html[start:end]
    labels = re.findall(r'piq-label-standalone">([^<]+)</p>', section)
    assert labels == ["SG Total", "SG OTT", "SG APP", "SG ARG", "SG PUTT"]


def test_round_history_never_shows_the_same_round_as_two_different_cards():
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    start = html.index('id="ph-round-history"')
    end = html.index("</details>", start)
    section = html[start:end]
    cards = re.findall(r"<strong>([^<]+)</strong>\s*([^<]+)", section)
    details = [c[1].strip() for c in cards]
    assert len(details) == len(set(details)), f"duplicate round card content: {details}"


def test_player_evolution_never_shows_the_same_delta_as_two_different_cards():
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    start = html.index('id="ph-player-evolution"')
    end = html.index("</details>", start)
    section = html[start:end]
    items = re.findall(r"<li><strong>[^<]+</strong>\s*—\s*([^<]+)</li>", section)
    assert len(items) == len(set(items)), f"duplicate evolution finding: {items}"


def test_9431_is_unaffected_by_the_10097_player_history_switch():
    from klpga.website_v2 import player_intelligence_v2

    html = player_intelligence_v2.build_or_placeholder("9431")
    assert "PLAYER HISTORY" not in html
    assert len(html) > 1000


def test_10097_now_renders_player_history_not_old_player_intelligence():
    from klpga.website_v2 import player_intelligence_v2

    html = player_intelligence_v2.build_or_placeholder("10097")
    assert "커리어 개요" in html
    assert "PLAYER HISTORY" in html


# ---------------------------------------------------------------------------
# UNIFIED RECONCILIATION -- Player History must never depend on one warehouse.
# See test_reconcile_10097_player_history.py for the reconciliation module's
# own tests; these check the builder/renderer actually use its output.
# ---------------------------------------------------------------------------

def test_career_overview_includes_all_three_previously_missing_tournaments():
    """Regression: Hana (2026090002) used to be patched in alone (missing
    R4, wrong SG mean); KB (2026090003) and the in-progress OK Open
    (2026120001) were not accounted for anywhere in Player History at
    all. Reconciliation must surface all three correctly, each in its
    right place (finished vs. in-progress)."""
    doc = build_script.build()
    codes = {t["game_code"] for t in doc["tournament_history"]}
    assert {"2026090002", "2026090003"} <= codes
    assert doc["current_tournament_in_progress"]["game_code"] == "2026120001"
    assert doc["career_overview"]["total_events"] == len(doc["tournament_history"])


def test_hana_win_reflects_the_real_four_round_cumulative_sg():
    doc = build_script.build()
    hana = next(t for t in doc["tournament_history"] if t["game_code"] == "2026090002")
    assert hana["is_win"]
    assert abs(hana["sg_total"] - 4.5) < 0.02


def test_kb_tournament_has_no_fabricated_sg():
    doc = build_script.build()
    kb = next(t for t in doc["tournament_history"] if t["game_code"] == "2026090003")
    assert kb["rank"] == 16
    assert kb["sg_total"] is None
    assert kb["sg_components"] is None
    assert kb["round_scores"] is not None


def test_reconciliation_report_is_present_and_clean():
    doc = build_script.build()
    r = doc["reconciliation"]
    assert r["status"] == "RECONCILED_OK"
    assert r["missing"] == 0
    assert r["conflicts_detected"] == 0
    assert r["total_tournaments"] == doc["career_overview"]["total_events"] + 1  # + the in-progress tournament


def test_render_includes_reconciliation_and_in_progress_sections():
    doc = build_script.build()
    html = report.render_player_history_html(doc)
    assert 'id="ph-reconciliation"' in html
    assert 'id="ph-in-progress"' in html
    assert "RECONCILED_OK" in html


def test_a_failed_reconciliation_stops_the_report_never_silently_patches():
    """build() must propagate ReconciliationError, not catch it and fall
    back to a partial report -- the whole point of this mission."""
    real_discover = build_script.recon_module._discover_special_game_codes

    def fake_discover():
        found = real_discover()
        found.add("8888888888")
        return found

    build_script.recon_module._discover_special_game_codes = fake_discover
    try:
        with pytest.raises(build_script.recon_module.ReconciliationError):
            build_script.build()
    finally:
        build_script.recon_module._discover_special_game_codes = real_discover
