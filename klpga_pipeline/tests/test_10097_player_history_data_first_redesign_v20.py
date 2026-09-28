"""MISSION "PLAYER HISTORY V20" -- DATA-FIRST REDESIGN (2026-09-28),
playerCode=10097 only.

"Less text. More information. Much stronger visualization... Every
trend graph should show direction, volatility, turning point, latest
value, best value, worst value, season markers... No more tables.
Tables should become graphics whenever possible... If the graph says
APP increased, never write 'APP increased.' Instead write the
insight."

Before touching code this session confirmed the mission's banned
vocabulary (Mechanism/Root Cause/Performance Lab/Coach Check/Decision
Layer/etc.) does not exist anywhere in player_history_report.py
-- it belongs to the unrelated player_intelligence_10097_report.py,
which this player's routing does not use. The real, actionable work
here was chart quality: replacing bare axis-free sparklines with a
real chart primitive (_marked_trend_svg) that draws direction, real
best/worst/latest markers, real season-boundary ticks, and a real
baseline -- applied to Season Evolution, Career Rolling Trend, and the
Tournament Timeline -- plus a new momentum bar chart for season-to-
season deltas, and demoting the season table behind a disclosure since
its numbers are now charted. No new data, metric, or calculation was
introduced anywhere; every mark is a min/max/lookup over an
already-computed value.
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

from klpga.website_v2 import player_history_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_ai_report_jargon_does_not_exist_on_this_page():
    """The mission's explicit ban list -- confirmed never present on
    this page in the first place (it belongs to the unrelated
    player_intelligence_10097_report.py), pinned here so it stays
    true."""
    _, html = _doc_and_html()
    for banned in (
        "Mechanism", "Root Cause", "Performance Lab", "Coach Console", "Coach Check",
        "Player Check", "Decision Layer", "Decision Context", "Technical Layer",
        "Scoring Layer", "Competitive Layer", "Reproducibility", "UNKNOWN", "Win Simulator", "Risk Map",
    ):
        assert banned not in html, f"AI-report jargon leaked onto Player History: {banned!r}"


def test_season_evolution_charts_have_real_marks_and_season_ticks():
    """Every Season Evolution chart must mark its real peak, worst, and
    latest season directly on the line, plus real season-year ticks --
    _marked_trend_svg, not the old bare _sparkline_svg.

    MISSION V60 (2026-09-28): "remove every numeric label drawn inside
    charts... values appear only in tooltips." The peak/worst marks are
    no longer visible <text> -- they are a <circle> with a <title>
    tooltip. Season-year ticks are unaffected (V60 targets value
    labels, not axis ticks) and still render as <text>."""
    doc, html = _doc_and_html()
    for metric in doc["career_evolution"].values():
        label_idx = html.index(f'>{report.escape(metric["label"])}</p>')
        block_end = html.index("</div></div>", label_idx)
        block = html[label_idx:block_end]
        assert "<svg" in block
        for season in (pt["season"] for pt in metric["series"]):
            assert f">{season}</text>" in block, f"missing season tick {season} for {metric['label']}"
        assert re.search(r'<circle[^>]*>\s*<title>[^<]*최고[^<]*</title>', block), f"no 최고 mark for {metric['label']}"
        assert re.search(r'<circle[^>]*>\s*<title>[^<]*최저[^<]*</title>', block), f"no 최저 mark for {metric['label']}"


def test_career_evolution_no_longer_uses_the_bare_sparkline_helper():
    """The chart-generating call sites must use the new marked chart,
    not the old axis-free sparkline (still defined, but only for
    anything not yet touched by this mission)."""
    import inspect
    src = inspect.getsource(report._career_evolution_html)
    assert "_marked_trend_svg" in src
    assert "_sparkline_svg" not in src


def test_career_rolling_trend_chart_marks_peak_slump_recovery_and_baseline():
    doc, html = _doc_and_html()
    crt = doc["career_rolling_trend"]
    start = html.index('id="ph-career-rolling-trend"')
    end = html.index("</details>", start) if "</details>" in html[start:start + 20000] else len(html)
    block_end = html.index("2025시즌 기술 기록", start) if "2025시즌 기술 기록" in html[start:] else start + 20000
    section = html[start:block_end]
    assert section.count("<svg") >= 1
    assert "커리어 평균" in section, "career-average baseline label missing"
    if crt.get("peak_window"):
        assert "전성기" in section
    if crt.get("slump_window"):
        assert "슬럼프" in section
    if crt.get("recovery_window"):
        assert "회복" in section


def test_tournament_timeline_chart_marks_best_and_worst_values():
    doc, html = _doc_and_html()
    rows = [r for r in doc["tournament_history"] if r.get("sg_total") is not None]
    best = max(r["sg_total"] for r in rows)
    worst = min(r["sg_total"] for r in rows)
    start = html.index('id="ph-tournament-trend"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert f'최고 {best:+.2f}' in section
    assert f'최저 {worst:+.2f}' in section


def test_momentum_bar_chart_section_is_gone():
    """MISSION V41 (2026-09-28): #ph-player-evolution (the momentum bar
    chart this test used to pin) was deleted entirely -- its one real
    conclusion (the single biggest season-to-season jump) was a
    verbatim duplicate of career_story's own '도약의 순간' milestone,
    already built from the exact same biggest_improvement fact."""
    _, html = _doc_and_html()
    assert 'id="ph-player-evolution"' not in html


def test_season_table_is_collapsed_behind_a_disclosure():
    """MISSION: 'No more tables... only where comparison is impossible
    visually.' Every metric the season table carries now has a real
    chart (Season Evolution) -- the raw table survives, nested."""
    _, html = _doc_and_html()
    start = html.index('id="ph-career-story"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert '<details class="ph-nested-detail">' in section
    assert "시즌별 전체 기록 보기" in section
    disclosure_start = section.index('<details class="ph-nested-detail">')
    assert "<table" in section[disclosure_start:]
    assert "<table" not in section[:disclosure_start], "a table renders before the disclosure that is meant to hold it"


def test_worst_season_mark_colored_by_real_sign_never_by_label():
    """Mission V12's rule survives the chart rewrite: a 'worst' season
    that is still a genuinely positive number must never render red.

    MISSION V60 (2026-09-28): the mark is now a <circle fill="..."> with
    a <title> tooltip instead of a visible <text fill="...">; the
    real-sign color rule applies to the circle's own fill exactly as it
    did to the old text's fill."""
    doc, html = _doc_and_html()
    for metric in doc["career_evolution"].values():
        worst_raw = metric["worst_season"]["value"]
        label_idx = html.index(f'>{report.escape(metric["label"])}</p>')
        block_end = html.index("</div></div>", label_idx)
        block = html[label_idx:block_end]
        m = re.search(r'<circle[^>]*fill="(#[0-9a-f]{6})"[^>]*>\s*<title>([^<]*최저[^<]*)</title>', block)
        assert m
        if worst_raw < 0:
            assert m.group(1) == "#9b493f"
        else:
            assert m.group(1) != "#9b493f"


def test_no_golf_statistic_changed_between_consecutive_builds():
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("career_evolution", "career_rolling_trend", "tournament_history", "player_evolution", "career_overview"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_no_new_top_level_section_ids_were_introduced():
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
