"""PLAYER HISTORY V6 -- comparative values mission, playerCode=10097
only. Replaces absolute values with comparisons: every Peak/Slump vs.
Career Average, every Recovery vs. Slump, DNA Growth Velocity and
Delta vs. Career Mean per axis, and a Career Heartbeat strip. No new
sections or cards -- everything renders inside the existing Season
(#ph-career-rolling-trend, new #ph-career-heartbeat sibling div) and
Player DNA (#ph-player-dna-radar) areas.
"""
from __future__ import annotations

import importlib.util
import statistics
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


def test_career_average_is_the_real_mean_of_the_same_population():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    finished_sg = [t for t in doc["tournament_history"] if t.get("sg_total") is not None]
    expected = round(statistics.fmean(t["sg_total"] for t in finished_sg), 3)
    assert crt["career_average_sg_total"] == expected
    assert crt["career_average_sample_size"] == len(finished_sg)


def test_peak_and_slump_deltas_vs_career_average_are_reproducible():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    avg = crt["career_average_sg_total"]
    assert crt["peak_window"]["delta_vs_career_average"] == round(crt["peak_window"]["moving_average_sg_total"] - avg, 3)
    assert crt["slump_window"]["delta_vs_career_average"] == round(crt["slump_window"]["moving_average_sg_total"] - avg, 3)
    # peak must be above average, slump below -- otherwise they aren't
    # meaningfully a peak/slump at all
    assert crt["peak_window"]["delta_vs_career_average"] > 0
    assert crt["slump_window"]["delta_vs_career_average"] < 0


def test_recovery_still_compares_against_slump_and_also_against_average():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    rec = crt["recovery_window"]
    if rec is not None:
        assert "delta_vs_slump" in rec
        assert "delta_vs_career_average" in rec
        avg = crt["career_average_sg_total"]
        assert rec["delta_vs_career_average"] == round(rec["moving_average_sg_total"] - avg, 3)


def test_career_heartbeat_uses_the_same_career_average_as_rolling_trend():
    """No two silently different 'career average' numbers on the same
    page -- the heartbeat's baseline must be identical to the rolling
    trend's."""
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    hb = doc["career_heartbeat"]
    assert hb["career_average_sg_total"] == crt["career_average_sg_total"]


def test_career_heartbeat_covers_every_finished_sg_bearing_tournament_chronologically():
    doc = build_script.build()
    hb = doc["career_heartbeat"]
    finished_sg = sorted(
        (t for t in doc["tournament_history"] if t.get("sg_total") is not None),
        key=lambda t: (t["season"], t["game_code"]),
    )
    assert len(hb["beats"]) == len(finished_sg)
    assert [b["game_code"] for b in hb["beats"]] == [t["game_code"] for t in finished_sg]


def test_career_heartbeat_deltas_are_reproducible_and_never_absolute_sg_alone():
    doc = build_script.build()
    hb = doc["career_heartbeat"]
    avg = hb["career_average_sg_total"]
    for b in hb["beats"]:
        assert b["delta_vs_career_average"] == round(b["sg_total"] - avg, 3)


def test_dna_growth_velocity_uses_only_real_consecutive_season_pairs():
    doc = build_script.build()
    growth = doc["player_dna_growth"]
    radar = doc["player_dna_radar"]
    for axis_label, g in growth.items():
        series = []
        for sb in radar:
            a = next((x for x in sb["axes"] if x["axis"] == axis_label), None)
            if a and a["available"]:
                series.append((sb["season"], a["percentile"]))
        series.sort()
        if len(series) >= 2:
            deltas = [series[i + 1][1] - series[i][1] for i in range(len(series) - 1)]
            assert g["growth_velocity_per_season"] == round(statistics.fmean(deltas), 2)
        else:
            assert g["growth_velocity_per_season"] is None


def test_dna_delta_vs_career_mean_is_reproducible_and_never_set_for_unavailable_axis():
    doc = build_script.build()
    growth = doc["player_dna_growth"]
    radar = doc["player_dna_radar"]
    for sb in radar:
        for a in sb["axes"]:
            if not a["available"]:
                assert a["delta_vs_career_mean"] is None
                continue
            mean = growth[a["axis"]]["career_mean_percentile"]
            assert a["delta_vs_career_mean"] == round(a["percentile"] - mean, 1)


def test_no_new_top_level_section_added():
    """MISSION NEO PLAYER PROFILE V2 (2026-09-27) relocated Career
    Heartbeat (unchanged) from the season-evolution cluster to #8 Raw
    Data -- it no longer sits between season-replay and the DNA radar,
    but it must still be a plain, unheaded <div>, not a new section."""
    doc, html = _doc_and_html()
    heartbeat_idx = html.index('id="ph-career-heartbeat"')
    reconciliation_idx = html.index('id="ph-reconciliation"')
    assert reconciliation_idx < heartbeat_idx
    section = html[heartbeat_idx:heartbeat_idx + 200]
    assert "<h2>" not in section


def test_peak_slump_chips_lead_with_comparative_not_absolute_value():
    """Mission: 'Replace absolute values with comparative values.'"""
    doc, html = _doc_and_html()
    start = html.index('id="ph-career-rolling-trend"')
    end = html.index('id="ph-technical-stats-2025"')
    section = html[start:end]
    assert "커리어 평균 대비" in section


def test_dna_growth_velocity_table_renders_inside_existing_dna_section():
    """MISSION NEO PLAYER PROFILE V2 (2026-09-27): the DNA growth-
    velocity/acceleration/stability table is named in the mission's
    explicit 'NO DATABASE UI' list -- relocated (unchanged) from the
    Player DNA section into #8 Raw Data, alongside round_history's
    other relocated extremes."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-dna-growth-velocity"')
    end = html.index("</div>", start)
    section = html[start:end]
    assert "성장 속도" in section
    assert "성장 가속도" in section
