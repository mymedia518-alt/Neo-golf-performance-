"""MISSION V30 -- PLAYER HISTORY EXPLORER (2026-09-28), playerCode=10097
only.

"I no longer want report sections. I want a PLAYER HISTORY EXPLORER...
A graph that only connects 3 points is wasted... If there are only
three values, do not draw a graph, find another visualization...
Heatmaps replace many tables... Hover -> Tournament / Round / SG /
Finish... Never invent data. Only real warehouse data."

Before writing code this session re-audited the repository's two
player-scoped SQLite warehouses (PLAYER_DATABASE_V1.sqlite,
PLAYER_DATA_WAREHOUSE_V1.sqlite) for any real, unused per-season
dataset the mission's "LEFT: Prize / Ranking" panel could use.
Confirmed `season_stats.earnings/ranking/cuts` are NULL for every
season except the current one -- the exact same single-point-in-time
snapshot PLAYER_HISTORY.json already surfaces as `current_snapshot`.
There is no new real historical per-season prize/ranking/cuts data to
connect; inventing one would violate the mission's own rule, so
Season Replay's left-hand summary stays real events/wins/top5/10/20
only.

What this mission actually rebuilt, using only already-computed real
data:
1. Deleted Season Replay's named_windows entirely -- a 3-point chart
   (처음5/중반5/최근5), exactly the 'wasted graph' this mission bans.
2. Replaced it with two real per-season visuals: a full tournament-by-
   tournament SG Total chart (_season_tournament_chart_svg, every real
   tournament that season, never bucketed) and a real SG-component
   heatmap (_season_skill_heatmap_svg, one cell per real tournament
   per component).
3. Added native SVG <title> hover tooltips (tournament / finish rank /
   real SG) to every point on both the season chart and the full-
   career tournament timeline chart -- real interactivity without
   client-side script, since this site renders none.
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


def test_named_windows_is_gone_no_three_point_chart_survives():
    _, html = _doc_and_html()
    start = html.index('id="ph-season-replay"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "처음5" not in section
    assert "중반5" not in section
    assert "최근5" not in section
    assert "표본 부족" not in section


def test_every_season_gets_a_real_full_tournament_chart():
    """One dot per real tournament that season -- never a 3-point
    bucket chart."""
    doc, html = _doc_and_html()
    for r in doc["season_replay"]:
        season_rows = [t for t in doc["tournament_history"] if t["season"] == r["season"] and t.get("sg_total") is not None]
        svg = report._season_tournament_chart_svg([t for t in doc["tournament_history"] if t["season"] == r["season"]])
        if len(season_rows) >= 2:
            assert svg, f"{r['season']} has {len(season_rows)} real SG rows but no chart"
            assert svg.count("<circle") >= len(season_rows)
        else:
            assert svg == ""


def test_every_season_gets_a_real_sg_component_heatmap():
    doc, html = _doc_and_html()
    for r in doc["season_replay"]:
        season_rows = [t for t in doc["tournament_history"] if t["season"] == r["season"]]
        labeled = [t for t in season_rows if t.get("sg_components")]
        svg = report._season_skill_heatmap_svg(season_rows)
        if len(labeled) >= 2:
            assert svg, f"{r['season']} has {len(labeled)} real component rows but no heatmap"
            assert svg.count("<rect") == 4 * len(labeled)  # OTT/APP/ARG/PUTT x real tournaments
        else:
            assert svg == ""


def test_heatmap_cells_carry_real_hover_detail_never_invented():
    doc, html = _doc_and_html()
    season_2026 = [t for t in doc["tournament_history"] if t["season"] == 2026]
    svg = report._season_skill_heatmap_svg(season_2026)
    labeled = [t for t in season_2026 if t.get("sg_components")]
    assert svg
    for t in labeled[:3]:
        assert t["tournament"] in svg


def test_tournament_timeline_points_have_native_hover_tooltips():
    """MISSION V30: 'Hover -> Tournament / Round / SG / Finish.' No
    client-side script anywhere on this page -- real interactivity
    means the browser's own SVG <title>, not invented JS."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-tournament-trend"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert section.count("<title>") >= 2
    rows = [r for r in doc["tournament_history"] if r.get("sg_total") is not None]
    sample = rows[0]
    assert f'{sample["tournament"]} ({sample["season"]}) · 최종 {sample["rank"]}위' in section


def test_season_dashboard_never_invents_historical_prize_or_ranking():
    """The repository audit this mission ran found season_stats.
    earnings/ranking/cuts are real NULL for every historical season --
    Season Replay must never show a fabricated prize or rank for
    2023-2025, only the real per-season facts it has always had
    (events/wins/top5/10/20/volatility/peak/slump/recovery)."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-season-replay"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "상금" not in section
    assert "랭킹" not in section
    assert "컷" not in section


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("season_replay", "tournament_history"):
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
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new section id(s) introduced: {found_ids - known_ids}"
