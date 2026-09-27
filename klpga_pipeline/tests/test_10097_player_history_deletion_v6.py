"""MISSION V6 (2026-09-25), playerCode=10097 only.

"No new sections. No new cards. No new charts. Spend the entire
mission deleting. For every visible element ask: 'If I remove this,
does the user understand Kim Minsun7 less?' If the answer is NO,
delete it. Continue until nothing removable remains."

These tests pin down the specific deletions this mission made -- no
section IDs change (V6 removes CONTENT, not sections), and every real
computation stays in the JSON even where the HTML no longer repeats it.
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
    """Same subset check as V5's test, extended: V6 must not introduce
    any section id beyond what V5 already had."""
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    import re
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"


def test_why_now_has_no_chart_and_no_table_just_sentence_and_arrows():
    """MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): each arrow
    card's label drops the "SG " prefix ("SG OTT" -> "OTT") -- still
    no chart, no table, and the real component + real delta both still
    appear, just shorter."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "<table" not in section
    assert "<svg" not in section
    for a in doc["why_now"]["arrows"]:
        assert a["component"].removeprefix("SG ") in section
        assert f'{a["delta"]:+.2f}' in section


def test_career_evolution_drops_the_season_to_season_delta_table_keeps_the_chart():
    """The sparkline + peak/worst/direction chips (the real chart +
    real extremes) must survive; the redundant delta TABLE must not."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-career-evolution"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "<table" not in section
    assert section.count("<svg") == len([c for c in doc["career_evolution"].values() if c])
    assert "최고 시즌" in section and "현재 방향" in section


def test_season_replay_drops_the_quartile_table_keeps_named_windows():
    doc, html = _doc_and_html()
    start = html.index('id="ph-season-replay"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "분기" not in section  # the old quartile column header ("1분기" etc)
    assert "처음 5개" in section  # named_windows survives
    assert "피크:" in section and "슬럼프:" in section  # real chips survive


def test_technical_stats_2025_is_collapsed_by_default():
    """Real, non-duplicated 2025-season data -- kept, but not needed
    for a 30-second read, so collapsed rather than open."""
    _, html = _doc_and_html()
    start = html.index('id="ph-technical-stats-2025"')
    tag_end = html.index(">", start)
    assert " open" not in html[start:tag_end]


def test_every_deleted_number_is_still_a_real_field_in_the_json():
    """'Delete' means delete from the RENDERED page, never from the
    underlying computation -- every value this mission stopped
    displaying must still be a real, present field in the JSON."""
    doc = build_script.build()
    for c in doc["career_evolution"].values():
        if c:
            assert c["deltas"]  # season-to-season deltas still computed
    for r in doc["season_replay"]:
        assert r["quartiles"]  # quartiles still computed
    csvc = doc["current_skill_vs_career"]
    assert csvc and csvc["components"]  # current/career/diff still computed
