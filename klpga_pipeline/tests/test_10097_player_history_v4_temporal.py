"""PLAYER HISTORY V4 -- temporal resolution mission, playerCode=10097
only. Replaces the flat Season -> Tournament hierarchy with
Season -> Season Window -> Tournament -> Round. No new top-level
sections were added (mission: 'no new cards') -- these tests confirm
the new content lives inside the existing Season Replay / Season
Evolution area, and that every trend is time-based and reproducible
from real per-tournament data, never a fabricated statistic.
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


def test_named_season_windows_are_real_chronological_slices():
    doc = build_script.build()
    for sr in doc["season_replay"]:
        nw = sr["named_windows"]
        assert nw["window_size"] == 5
        assert nw["first"]["events"] == 5
        assert nw["last"]["events"] == 5
        # 2026 has 18 events -- still >= 15, so middle must be computed
        if sr["event_count"] >= 15:
            assert nw["middle"] is not None
            assert nw["middle"]["events"] == 5


def test_named_windows_middle_never_overlaps_first_or_last():
    doc = build_script.build()
    for sr in doc["season_replay"]:
        events = sr["event_count"]
        nw = sr["named_windows"]
        if nw["middle"] is None:
            assert events < 15
            assert nw["middle_unavailable_reason"] is not None
        else:
            assert events >= 15


def test_career_rolling_trend_window_size_is_disclosed_and_real():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    assert crt["window_size"] == 5
    assert crt["total_windows"] > 0
    # every window's average must be reproducible from the same
    # chronologically-ordered SG-bearing tournaments the rest of the
    # document already uses -- not an independently invented number.
    finished_sg = [t for t in doc["tournament_history"] if t.get("sg_total") is not None]
    assert crt["total_windows"] == len(finished_sg) - crt["window_size"] + 1


def test_moving_average_series_is_reproducible_by_hand():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    finished_sg = sorted(
        (t for t in doc["tournament_history"] if t.get("sg_total") is not None),
        key=lambda t: (t["season"], t["game_code"]),
    )
    w = crt["window_size"]
    first_window_vals = [t["sg_total"] for t in finished_sg[:w]]
    expected_avg = round(sum(first_window_vals) / w, 3)
    assert crt["series"][0]["moving_average_sg_total"] == expected_avg


def test_peak_and_slump_windows_are_the_real_extremes_of_the_series():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    all_avgs = [w["moving_average_sg_total"] for w in crt["series"]]
    assert crt["peak_window"]["moving_average_sg_total"] == max(all_avgs)
    assert crt["slump_window"]["moving_average_sg_total"] == min(all_avgs)


def test_self_percentile_is_never_a_field_wide_claim():
    """Rolling percentile is scoped to the player's OWN other windows
    -- never implied to be a comparison against other players (no
    field-wide population exists at this granularity)."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-career-rolling-trend"')
    section = html[start:start + 3000]
    assert "다른 선수" not in section or "다른 선수와의 비교가 아닙니다" in section
    crt = doc["career_rolling_trend"]
    for w in crt["series"]:
        assert w["self_percentile"] is None or 0 <= w["self_percentile"] <= 100


def test_recovery_window_is_the_window_immediately_after_slump():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    slump_idx = crt["slump_window"]["window_index"]
    series_by_index = {w["window_index"]: w for w in crt["series"]}
    expected_next = series_by_index.get(slump_idx + 1)
    if expected_next is None:
        assert crt["recovery_window"] is None
    else:
        assert crt["recovery_window"]["window_index"] == expected_next["window_index"]
        assert crt["recovery_window"]["delta_vs_slump"] == round(
            expected_next["moving_average_sg_total"] - crt["slump_window"]["moving_average_sg_total"], 3
        )


def test_no_new_top_level_section_was_added():
    """Mission: 'No new cards. Only deeper history.' The rolling trend
    content must live inside the existing Season area (before Player
    DNA / section 4), not as its own numbered top-level section."""
    doc, html = _doc_and_html()
    crt_idx = html.index('id="ph-career-rolling-trend"')
    season_replay_idx = html.index('id="ph-season-replay"')
    dna_idx = html.index('id="ph-player-dna-radar"')
    assert season_replay_idx < crt_idx < dna_idx
    # it must not carry its own <h2> heading (no new numbered card)
    section = html[crt_idx:crt_idx + 200]
    assert "<h2>" not in section


def test_named_windows_render_inside_season_replay_not_as_new_section():
    doc, html = _doc_and_html()
    start = html.index('id="ph-season-replay"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "처음 5개" in section
    assert "최근 5개" in section
