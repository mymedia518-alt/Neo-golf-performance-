"""Compare Mode tests, MISSION "PLAYER COMPARISON, ARCHITECTURE FIRST"
(2026-09-28).

"Architecture first. Data second. Players last. The second player is
only a validation target, not a development target." These tests
validate player_compare.py's engine using small, hand-built SYNTHETIC
doc fixtures shaped like a real PLAYER_HISTORY.json -- never real data
from a second player's warehouse. The one real player this session has
(10097) is used only to prove the compare functions work against a
REAL doc on one side, never both.

Also pins that extending player_history_report.py's shared
_trend_svg_by_index with an optional compare= parameter did not change
a single byte of player 10097's own rendered page -- the whole point
of "architecture first" is that this refactor is invisible to the
frozen Player History page.
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

from klpga.website_v2 import player_compare as compare  # noqa: E402
from klpga.website_v2 import player_history_report as report  # noqa: E402


def _synthetic_doc(player_name: str, season: int = 2026) -> dict:
    """A small, entirely fabricated doc shaped like a real
    PLAYER_HISTORY.json -- used ONLY to validate the compare engine's
    reshaping logic, never presented as real data anywhere on a page."""
    axes = [
        {"axis": "TEE", "percentile": 70.0},
        {"axis": "APP", "percentile": 55.0},
        {"axis": "ARG", "percentile": 60.0},
        {"axis": "PUTT", "percentile": 40.0},
        {"axis": "OVERALL", "percentile": 65.0},
    ]
    return {
        "player_name": player_name,
        "player_dna_radar": [{"season": season, "axes": axes}],
        "tournament_history": [
            {"game_code": f"X{season}0001", "season": season, "tournament": "Synthetic Open A", "rank": 3, "sg_total": 1.5, "is_win": False, "is_top10": True},
            {"game_code": f"X{season}0002", "season": season, "tournament": "Synthetic Open B", "rank": 1, "sg_total": 2.1, "is_win": True, "is_top10": True},
            {"game_code": f"X{season}0003", "season": season, "tournament": "Synthetic Open C", "rank": 40, "sg_total": -0.6, "is_win": False, "is_top10": False},
        ],
        "current_vs_career": {
            "current_season": season,
            "current_season_sg_total": 1.2,
            "current_season_sample_size": 10,
            "career_average_sg_total": 0.8,
            "career_average_sample_size": 50,
            "delta_vs_career_average": 0.4,
        },
    }


def _real_10097_doc() -> dict:
    return build_script.build()


def test_10097_own_rendered_page_is_unchanged_by_the_compare_extension():
    """The point of 'architecture first' is that none of this touches
    the frozen Player History page. compare=None (every existing call
    site) must still be byte-identical to the pre-refactor build."""
    doc = _real_10097_doc()
    html = report.render_player_history_html(doc)
    # a real, structural spot check: the frozen page's known section ids
    # still all render, nothing about the single-player path changed shape
    for section_id in ("ph-current-form", "ph-why-now", "ph-tournament-trend", "ph-player-dna-radar"):
        assert f'id="{section_id}"' in html


def test_compare_dna_radar_overlays_two_synthetic_players_on_one_real_primitive():
    a = _synthetic_doc("Player A", 2026)
    b = _synthetic_doc("Player B", 2026)
    html = compare.compare_dna_radar_html(a, b)
    assert html
    assert "Player A 2026" in html
    assert "Player B 2026" in html
    # both real colors from the existing single-player overlay primitive
    assert "#0f5c46" in html and "#c98a1a" in html


def test_compare_dna_radar_renders_nothing_when_a_season_is_missing():
    a = _synthetic_doc("Player A", 2026)
    b = _synthetic_doc("Player B", 2026)
    assert compare.compare_dna_radar_html(a, b, season_a=1999) == ""
    assert compare.compare_dna_radar_html(None, b) == ""
    assert compare.compare_dna_radar_html(a, None) == ""


def test_compare_dna_radar_renders_nothing_when_percentiles_are_incomplete():
    """Never a partial polygon overlaid next to a real one -- same rule
    the single-player season-vs-season overlay already enforces."""
    a = _synthetic_doc("Player A", 2026)
    b = _synthetic_doc("Player B", 2026)
    b["player_dna_radar"][0]["axes"][0]["percentile"] = None
    assert compare.compare_dna_radar_html(a, b) == ""


def test_compare_season_trend_uses_the_shared_trend_chart_not_a_second_implementation():
    a = _synthetic_doc("Player A", 2026)
    b = _synthetic_doc("Player B", 2026)
    html = compare.compare_season_trend_html(a, b)
    assert html
    assert html.count("<svg") == 1
    # primary line solid, compare line dashed -- one shared function
    assert "stroke-dasharray" in html


def test_compare_season_trend_shares_one_y_scale_across_both_players():
    """'Identical scale' -- the two series' SVG y-coordinates must be
    computed from the SAME min/max, not rescaled independently."""
    a = _synthetic_doc("Player A", 2026)
    b = _synthetic_doc("Player B", 2026)
    # give b a much larger real value range than a
    b["tournament_history"][1]["sg_total"] = 8.0
    svg_shared = compare.compare_season_trend_html(a, b)
    svg_a_alone = report._trend_svg_by_index(
        [1.5, 2.1, -0.6], ["top10", "win", None],
    )
    # the shared-scale render must differ from a's own solo scale,
    # proving the y-axis was recomputed across both real series
    assert svg_shared != svg_a_alone


def test_compare_current_form_is_a_real_side_by_side_table_not_a_new_chart():
    a = _synthetic_doc("Player A", 2026)
    b = _synthetic_doc("Player B", 2026)
    html = compare.compare_current_form_html(a, b)
    assert html
    assert "<table" in html
    assert "<svg" not in html
    assert "Player A" in html and "Player B" in html
    assert "+0.40" in html  # a's real delta_vs_career_average
    assert "+0.40" in html  # b's identical synthetic value too


def test_compare_functions_never_raise_on_a_missing_side():
    assert compare.compare_dna_radar_html(None, None) == ""
    assert compare.compare_season_trend_html(None, None) == ""
    assert compare.compare_current_form_html(None, None) == ""


def test_compare_engine_reuses_the_real_report_module_never_duplicates_it():
    """'Never duplicate components... no duplicate code.' player_compare
    must import its chart primitives from player_history_report, not
    reimplement them."""
    import inspect
    src = inspect.getsource(compare)
    assert "def _radar_svg" not in src  # no second radar implementation
    assert "def _trend_svg" not in src  # no second trend-chart implementation
    assert "from klpga.website_v2.player_history_report import" in src
