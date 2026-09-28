"""MISSION V40 -- PLAYER HISTORY EXPLORER, navigation edition (2026-09-28),
playerCode=10097 only.

"Stop adding sections. Start deleting sections. The user should never
wonder 'What do I click next?' There must always be one obvious next
action. Career -> Season -> Tournament -> Round -> Hole. No section
should exist without a navigation purpose. Every visualization must
also be a navigation object. If a chart cannot take the user deeper,
reconsider whether it belongs. Build a Player History Explorer. Not a
Player History Report. Think Google Maps. You don't read the map. You
explore it."

This site renders zero client-side script -- true drill-down here means
real `<a href="#anchor">` links, relying on the real, modern browser
behaviour that a closed <details> auto-opens when navigated to a
fragment anchor inside it. This mission wires every real mention of a
specific tournament anywhere on the page to that tournament's own row
in the full tournament table (#ph-tournament-history), completing the
Tournament layer of the chain, plus the one real Tournament -> Round ->
Hole case this player's data supports: the in-progress tournament links
down to Hole History exactly when their real game_codes match, never
otherwise.

No new top-level sections were added -- only real navigation was wired
into sections that already existed.
"""
from __future__ import annotations

import importlib.util
import re
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


def test_tournament_link_falls_back_to_plain_text_without_a_real_game_code():
    assert report._tournament_link("Some Open", None) == "Some Open"
    assert report._tournament_link("Some Open", "") == "Some Open"


def test_tournament_link_escapes_the_name_and_points_at_the_real_game_code():
    link = report._tournament_link("A & B Open", "GC1")
    assert link == '<a href="#t-GC1">A &amp; B Open</a>'


def test_every_tournament_table_row_carries_a_real_game_code_anchor():
    doc, html = _doc_and_html()
    start = html.index('id="ph-tournament-history"')
    end = html.index("</details>", start)
    section = html[start:end]
    for r in doc["tournament_history"]:
        assert f'id="t-{r["game_code"]}"' in section


def test_every_rendered_tournament_link_resolves_to_a_real_anchor_on_the_page():
    """Every #t-{game_code} href this mission wires anywhere on the page
    must land on a real row this build actually produced -- never a
    dangling link to a tournament that doesn't exist in this render."""
    doc, html = _doc_and_html()
    real_anchor_ids = {f't-{r["game_code"]}' for r in doc["tournament_history"]}
    hrefs = set(re.findall(r'href="#(t-[^"]+)"', html))
    assert hrefs
    assert hrefs <= real_anchor_ids


def test_round_cards_and_round_big_stats_link_to_their_real_tournament_row():
    doc, html = _doc_and_html()
    rh = doc.get("round_history") or {}
    for key in ("best_round", "worst_round"):
        r = rh.get(key)
        if r and r.get("game_code"):
            assert f'href="#t-{r["game_code"]}"' in html


def test_course_profile_best_and_worst_tournaments_link_to_their_real_row():
    doc, html = _doc_and_html()
    profiles = doc.get("course_profile") or []
    if not profiles:
        return
    start = html.index('id="ph-course-profile"')
    end = html.index("</details>", start)
    section = html[start:end]
    game_code_by_name = {t["tournament"]: t["game_code"] for t in doc["tournament_history"]}
    for p in profiles:
        best_gc = game_code_by_name.get(p["best_tournament"])
        worst_gc = game_code_by_name.get(p["worst_tournament"])
        if best_gc:
            assert f'href="#t-{best_gc}"' in section
        if worst_gc:
            assert f'href="#t-{worst_gc}"' in section


def test_season_replay_peak_slump_recovery_chips_link_to_their_real_season_scoped_row():
    """A season-scoped lookup, never global -- a repeated tournament
    name across two different seasons must never resolve to the wrong
    game_code."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-season-replay"')
    end = html.index("</details>", start)
    section = html[start:end]
    for sr in doc["season_replay"]:
        season_rows = [t for t in doc["tournament_history"] if t["season"] == sr["season"]]
        game_code_by_name = {t["tournament"]: t["game_code"] for t in season_rows}
        for key in ("peak", "slump", "recovery_next_event"):
            entry = sr.get(key)
            if entry and entry.get("tournament"):
                gc = game_code_by_name.get(entry["tournament"])
                if gc:
                    assert f'href="#t-{gc}"' in section


def test_in_progress_links_to_hole_history_only_when_game_codes_really_match():
    live = {
        "tournament": "Live Open", "game_code": "LIVE1", "season": 2026, "note": "n",
        "is_confirmed_live": True, "rounds_completed": [{"round": 1, "strokes": 70}],
        "partial_round_sg": None,
    }
    assert "홀 기록 보기" in report._in_progress_html(live, {"game_code": "LIVE1"})
    assert "홀 기록 보기" not in report._in_progress_html(live, {"game_code": "OTHER"})
    assert "홀 기록 보기" not in report._in_progress_html(live, None)
    assert report._in_progress_html(None, {"game_code": "LIVE1"}) == ""


def test_in_progress_never_shown_when_not_confirmed_live_even_with_a_hole_history_match():
    not_live = {
        "tournament": "Finished Open", "game_code": "F1", "season": 2026, "note": "n",
        "is_confirmed_live": False, "rounds_completed": [], "partial_round_sg": None,
    }
    assert report._in_progress_html(not_live, {"game_code": "F1"}) == ""


def test_hole_history_links_back_up_to_its_own_real_tournament_row_when_reconciled():
    """The link back up only exists once the tournament has a real row
    in tournament_history -- never a dangling link to a game_code with
    no anchor on the page (e.g. the tournament is still in progress and
    not yet reconciled into the finished table)."""
    hh = {
        "tournament": "Live Open", "game_code": "LIVE1", "course": "Course A",
        "capture_note": "note", "rounds": [],
    }
    reconciled = [{"tournament": "Live Open", "game_code": "LIVE1"}]
    html_reconciled = report._hole_history_html(hh, reconciled)
    assert 'href="#t-LIVE1"' in html_reconciled

    html_not_reconciled = report._hole_history_html(hh, [])
    assert 'href="#t-LIVE1"' not in html_not_reconciled
    assert "Live Open" in html_not_reconciled


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("tournament_history", "round_history", "course_profile", "season_replay",
                "current_tournament_in_progress", "hole_history"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_no_new_top_level_section_ids_were_introduced():
    """MISSION V40: 'Stop adding sections.' Only real navigation was
    wired into sections that already existed -- no new top-level
    pi-section id anywhere."""
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"
