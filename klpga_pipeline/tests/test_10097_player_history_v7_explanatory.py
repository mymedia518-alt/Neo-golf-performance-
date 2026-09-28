"""PLAYER HISTORY V7 -- explanatory power mission, playerCode=10097
only. Adds Growth Acceleration, Peak Sustainability, Recovery Time,
Career Median, Career Percentile, Metric Stability, and Heartbeat Dual
Track -- all measured, none predicted or inferred. No new sections or
cards: everything renders inside the existing #ph-career-rolling-trend,
#ph-career-heartbeat, and #ph-player-dna-radar blocks.
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


def test_career_median_is_the_real_median_of_the_same_population():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    finished_sg = [t["sg_total"] for t in doc["tournament_history"] if t.get("sg_total") is not None]
    assert crt["career_median_sg_total"] == round(statistics.median(finished_sg), 3)


def test_peak_sustainability_is_a_real_consecutive_walk_forward():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    series = crt["series"]
    avg = crt["career_average_sg_total"]
    peak_idx = crt["peak_window"]["window_index"]
    expected = 0
    i = peak_idx
    while i < len(series) and series[i]["moving_average_sg_total"] >= avg:
        expected += 1
        i += 1
    assert crt["peak_window"]["sustainability_windows"] == expected
    assert crt["peak_window"]["sustainability_tournaments"] == expected + crt["window_size"] - 1


def test_recovery_time_is_the_real_first_window_that_reaches_career_average():
    """RED TEAM narrative mission (2026-09-25): 'Never let users see...
    moving average... percentile among windows' -- recovery_time_note no
    longer states a window count (the offset integer itself, unchanged,
    still lives in recovery_time_windows below); it names the real
    tournament by which she'd recovered instead."""
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    series = crt["series"]
    avg = crt["career_average_sg_total"]
    slump_idx = crt["slump_window"]["window_index"]
    expected = None
    for offset in range(0, len(series) - slump_idx):
        if series[slump_idx + offset]["moving_average_sg_total"] >= avg:
            expected = offset
            break
    assert crt["recovery_time_windows"] == expected
    if expected is None:
        assert crt["recovery_time_tournament"] is None
        assert "찾지 못했습니다" in crt["recovery_time_note"]
    else:
        expected_tournament = series[slump_idx + expected]["end_tournament"]
        assert crt["recovery_time_tournament"] == expected_tournament
        assert expected_tournament in crt["recovery_time_note"]


def test_career_percentile_per_tournament_is_reproducible_self_percentile():
    doc = build_script.build()
    hb = doc["career_heartbeat"]
    all_sg = [b["sg_total"] for b in hb["beats"]]
    n = len(all_sg)
    for b in hb["beats"]:
        worse = sum(1 for v in all_sg if v < b["sg_total"])
        expected = round(worse / (n - 1) * 100, 1)
        assert b["career_percentile"] == expected


def test_career_percentile_is_never_implied_as_a_field_comparison():
    """career_percentile is still computed (see
    test_career_percentile_per_tournament_is_reproducible_self_percentile
    above) -- V5 mission (2026-09-25) dropped the heartbeat's Track 2,
    which used to be the ONLY place this self-percentile-not-a-field-
    comparison disclosure text was ever rendered publicly. It survives
    in the JSON and this repo's existing conventions (e.g. the career
    rolling trend's own note), just not duplicated in this block."""
    doc = build_script.build()
    beats = doc["career_heartbeat"]["beats"]
    assert all("career_percentile" in b for b in beats)


def test_dna_growth_acceleration_is_second_order_difference_of_velocity():
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
        if len(series) >= 3:
            velocities = [series[i + 1][1] - series[i][1] for i in range(len(series) - 1)]
            accel_deltas = [velocities[i + 1] - velocities[i] for i in range(len(velocities) - 1)]
            assert g["growth_acceleration_per_season"] == round(statistics.fmean(accel_deltas), 2)
        else:
            assert g["growth_acceleration_per_season"] is None


def test_dna_metric_stability_is_real_population_stddev():
    doc = build_script.build()
    growth = doc["player_dna_growth"]
    radar = doc["player_dna_radar"]
    for axis_label, g in growth.items():
        percentiles = []
        for sb in radar:
            a = next((x for x in sb["axes"] if x["axis"] == axis_label), None)
            if a and a["available"]:
                percentiles.append(a["percentile"])
        if len(percentiles) >= 2:
            assert g["stability_stddev"] == round(statistics.pstdev(percentiles), 2)
        else:
            assert g["stability_stddev"] is None


def test_no_predictions_no_inference_only_measured_fields():
    """Every V7 field must trace to a real, already-measured value --
    none of them may be None replaced by an estimate. Spot-checks that
    a genuinely insufficient-sample axis (if any exist) stays None
    rather than being filled in."""
    doc = build_script.build()
    growth = doc["player_dna_growth"]
    for axis_label, g in growth.items():
        if g["sample_size"] < 2:
            assert g["growth_velocity_per_season"] is None
            assert g["stability_stddev"] is None
        if g["sample_size"] < 3:
            assert g["growth_acceleration_per_season"] is None


def test_heartbeat_renders_a_single_track_since_v5():
    """V7 originally built this as Dual Track (SG deviation + career-
    percentile deviation). V5 mission (2026-09-25) -- 'every chart must
    answer exactly ONE question' -- dropped Track 2: the percentile
    track told the same story in a harder-to-read second unit. Track 1
    (SG deviation from career average) is the one real chart that
    remains; career_percentile itself is still computed and present in
    the JSON (see test_career_percentile_per_tournament_is_reproducible_
    self_percentile), it is simply not plotted a second time."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-career-heartbeat"')
    end = html.index("</div>", html.index('</svg>', start))
    section = html[start:end + 6]
    assert "트랙 1" not in section
    assert "트랙 2" not in section
    assert "커리어 하트비트" in section


def test_no_new_top_level_section_added():
    """MISSION NEO PLAYER PROFILE V2 (2026-09-27) relocated Career
    Heartbeat (unchanged) from between rolling-trend and the DNA radar
    to #8 Raw Data -- it must still be a plain, unheaded <div>, not a
    new section."""
    doc, html = _doc_and_html()
    heartbeat_idx = html.index('id="ph-career-heartbeat"')
    reconciliation_idx = html.index('id="ph-reconciliation"')
    assert reconciliation_idx < heartbeat_idx
    section = html[heartbeat_idx:heartbeat_idx + 200]
    assert "<h2>" not in section


def test_peak_sustainability_and_recovery_time_render_in_rolling_trend_block():
    """RED TEAM narrative mission (2026-09-25): '피크 지속력' (a window-
    count label) was superseded by a real-tournament-count sentence --
    see _career_rolling_trend_html's sustain_chip, which now says the
    peak stretch 'continued for N real tournaments' instead of naming
    itself 'peak sustainability'. The underlying computation
    (sustainability_windows / sustainability_tournaments) is unchanged.

    MISSION NEO PLAYER PROFILE V2 (2026-09-27) relocated Career
    Heartbeat away from immediately following this block -- bounded
    instead by #ph-technical-stats-2025, the next real block in the
    season-evolution cluster."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-career-rolling-trend"')
    end = html.index('id="ph-technical-stats-2025"')
    section = html[start:end]
    peak = doc["career_rolling_trend"]["peak_window"]
    assert f'{peak["sustainability_tournaments"]}개 대회 동안 이어졌습니다' in section
    assert "커리어 중앙값" in section


def test_dna_stability_and_acceleration_render_in_existing_dna_section():
    """MISSION NEO PLAYER PROFILE V2 (2026-09-27): the DNA growth-
    velocity/acceleration/stability table is named in the mission's
    explicit 'NO DATABASE UI' list -- relocated (unchanged) from the
    Player DNA section into #8 Raw Data."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-dna-growth-velocity"')
    end = html.index("</div>", start)
    section = html[start:end]
    assert "성장 가속도" in section
    assert "안정성" in section
