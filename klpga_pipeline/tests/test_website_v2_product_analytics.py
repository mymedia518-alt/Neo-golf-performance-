from __future__ import annotations

import json
from html import unescape

import pytest

from klpga.website_v2.analytics import (
    SCORE_CLASSES, aggregate_holes, chart_json, checkpoint_series,
    classify_hole_score, hole_leaders, line_chart_svg, parse_rank,
)


@pytest.mark.parametrize(("strokes", "par", "label"), [
    (2, 4, "Eagle"), (3, 4, "Birdie"), (4, 4, "Par"),
    (5, 4, "Bogey"), (6, 4, "Double Bogey"), (7, 4, "Triple Bogey+"),
])
def test_hole_score_classification(strokes, par, label):
    assert classify_hole_score(strokes, par) == label


def test_hole_aggregation_and_actual_counts():
    rows = [
        {"hole": 1, "par": 4, "strokes": 3}, {"hole": 1, "par": 4, "strokes": 4},
        {"hole": 1, "par": 4, "strokes": 5}, {"hole": 2, "par": 3, "strokes": 5},
        {"hole": 2, "par": 3, "strokes": 6},
    ]
    aggregate = aggregate_holes(rows)
    assert aggregate[0]["average_score"] == 4
    assert [aggregate[0][label] for label in SCORE_CLASSES] == [0, 1, 1, 1, 0, 0]
    assert aggregate[1]["Double Bogey"] == 1 and aggregate[1]["Triple Bogey+"] == 1


def test_hardest_easiest_and_scoring_leaders_are_deterministic():
    aggregates = aggregate_holes([
        {"hole": 1, "par": 4, "strokes": 5}, {"hole": 1, "par": 4, "strokes": 5},
        {"hole": 2, "par": 4, "strokes": 3}, {"hole": 2, "par": 4, "strokes": 4},
        {"hole": 3, "par": 3, "strokes": 5}, {"hole": 3, "par": 3, "strokes": 6},
    ])
    assert hole_leaders(aggregates) == {"hardest": 3, "easiest": 2, "most_birdies": 2, "most_bogeys": 1, "most_double_plus": 3}
    assert hole_leaders([]) is None


def test_missing_checkpoint_is_not_interpolated_and_breaks_svg_line():
    series = checkpoint_series(["PRE", "R1", "R2", "R3"], {"PRE": 2.1, "R1": 3.2, "R3": 7.4})
    assert series[2] == {"stage": "R2", "value": None}
    svg = line_chart_svg(title="우승 확률", player="검증 선수", series=series, unit="%")
    assert "자료 없음" in svg
    assert svg.count("chart-line") == 1  # only PRE→R1; R3 remains disconnected


def test_rank_trend_inverts_rank_one_to_top_and_score_trend_is_real_svg():
    ranks = checkpoint_series(["R1", "R2", "R3", "FINAL"], {"R1": 39, "R2": 18, "R3": 1, "FINAL": 1})
    svg = line_chart_svg(title="순위 변화", player="신다인", series=ranks, unit="위", invert=True)
    assert "<svg" in svg and "chart-axis" in svg and "39위" in svg and "1위" in svg
    assert parse_rank("T5") == 5 and parse_rank("CUT") is None


def test_dense_chart_shows_at_most_5_labels_max_min_start_end_always_included():
    # LIVE VISUAL HOTFIX v2: a dense (many-point) chart no longer keeps
    # all 18 value labels permanently on screen -- only up to 5 (the
    # required max/min plus start/end/turning-points). Every point and
    # the line itself must still be present; the rest of a point's
    # exact value moves to a hover/keyboard-focus tooltip.
    values = [0.02, -0.14, -0.16, -0.08, 0.02, -0.03, -0.11, -0.04, 0.07,
              -0.05, 0.06, 0.06, 0.09, -0.23, 0.11, -0.13, -0.01, -0.03]
    series = checkpoint_series([str(i + 1) for i in range(18)], {str(i + 1): v for i, v in enumerate(values)})
    svg = line_chart_svg(title="홀별", player="전체 선수", series=series, unit="", dense=True)
    assert svg.count('<circle class="chart-point"') == 18
    assert svg.count('<polyline class="chart-line"') == 1
    label_count = svg.count('<text class="chart-value"')
    assert 1 <= label_count <= 5, label_count
    assert "+0.11" in svg and "-0.23" in svg  # required max/min always shown
    # every point's exact value is reachable via tooltip aria-label or a
    # permanent label -- never dropped entirely.
    for i, v in enumerate(values, start=1):
        text = f'{v:+.2f}'
        assert f'{i}번홀 · {text} SG' in svg or f'>{text}<' in svg, f"hole {i} value not reachable"


def test_dense_chart_tooltips_are_keyboard_focusable_and_never_overlap_a_static_label():
    values = [0.02, -0.14, -0.16, -0.08, 0.02, -0.03, -0.11, -0.04, 0.07,
              -0.05, 0.06, 0.06, 0.09, -0.23, 0.11, -0.13, -0.01, -0.03]
    series = checkpoint_series([str(i + 1) for i in range(18)], {str(i + 1): v for i, v in enumerate(values)})
    svg = line_chart_svg(title="홀별", player="전체 선수", series=series, unit="", dense=True)
    assert 'tabindex="0"' in svg
    assert svg.count('class="chart-point-wrap"') + svg.count('<text class="chart-value"') == 18
    # a tooltip's aria-label always carries the "N번홀 · value SG" format
    import re
    for m in re.finditer(r'aria-label="(\d+번홀 · [+-]\d\.\d\d SG)"', svg):
        assert "번홀 · " in m.group(1) and m.group(1).endswith(" SG")


def test_chart_data_serialization_is_machine_readable_and_has_no_nan():
    series = checkpoint_series(["R1", "R2"], {"R1": 70, "R2": None})
    assert json.loads(chart_json(series)) == series
    svg = line_chart_svg(title="라운드 스코어", player="신다인", series=series, unit="타")
    payload = unescape(svg.split('<script type="application/json" data-chart-series>', 1)[1].split("</script>", 1)[0])
    assert json.loads(payload) == series


def test_invalid_hole_rows_fail_closed():
    with pytest.raises(ValueError):
        aggregate_holes([{"hole": 1, "par": 4}])
    with pytest.raises(ValueError):
        aggregate_holes([{"hole": 1, "par": 4, "strokes": 4}, {"hole": 1, "par": 5, "strokes": 4}])
