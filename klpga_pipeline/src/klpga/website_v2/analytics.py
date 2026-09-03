"""Pure, deterministic analytics and chart helpers for static NEO pages."""
from __future__ import annotations

import json
import hashlib
import math
import re
from collections import Counter, defaultdict
from html import escape

SCORE_CLASSES = ("Eagle", "Birdie", "Par", "Bogey", "Double Bogey", "Triple Bogey+")


def classify_hole_score(strokes: int, par: int) -> str:
    difference = int(strokes) - int(par)
    if difference <= -2:
        return "Eagle"
    if difference == -1:
        return "Birdie"
    if difference == 0:
        return "Par"
    if difference == 1:
        return "Bogey"
    if difference == 2:
        return "Double Bogey"
    return "Triple Bogey+"


def aggregate_holes(records: list[dict]) -> list[dict]:
    """Aggregate validated hole rows; no rows means no analytics."""
    grouped: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        required = {"hole", "par", "strokes"}
        if not required <= set(record):
            raise ValueError(f"hole record missing {sorted(required - set(record))}")
        grouped[int(record["hole"])].append(record)
    output = []
    for hole, rows in sorted(grouped.items()):
        pars = {int(row["par"]) for row in rows}
        if len(pars) != 1:
            raise ValueError(f"hole {hole} has inconsistent par")
        par = pars.pop()
        counts = Counter(classify_hole_score(int(row["strokes"]), par) for row in rows)
        average = sum(int(row["strokes"]) for row in rows) / len(rows)
        output.append({
            "hole": hole, "par": par, "average_score": round(average, 3),
            "average_vs_par": round(average - par, 3),
            **{label: counts[label] for label in SCORE_CLASSES},
        })
    return output


def hole_leaders(aggregates: list[dict]) -> dict[str, int] | None:
    if not aggregates:
        return None
    return {
        "hardest": max(aggregates, key=lambda row: (row["average_vs_par"], -row["hole"]))["hole"],
        "easiest": min(aggregates, key=lambda row: (row["average_vs_par"], row["hole"]))["hole"],
        "most_birdies": max(aggregates, key=lambda row: (row["Birdie"], -row["hole"]))["hole"],
        "most_bogeys": max(aggregates, key=lambda row: (row["Bogey"], -row["hole"]))["hole"],
        "most_double_plus": max(aggregates, key=lambda row: (row["Double Bogey"] + row["Triple Bogey+"], -row["hole"]))["hole"],
    }


def parse_rank(value: str | int | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def checkpoint_series(checkpoints: list[str], values: dict[str, float | int | None]) -> list[dict]:
    """Serialize only supplied checkpoints. Missing values stay explicit and disconnected."""
    return [{"stage": stage, "value": values.get(stage)} for stage in checkpoints]


def chart_json(series: list[dict]) -> str:
    return json.dumps(series, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def nice_ticks(maximum: float, minimum: float = 0.0, target: int = 6) -> list[float]:
    """Return human-readable 1/2/5-step ticks for editorial charts."""
    if maximum <= minimum:
        maximum = minimum + 1
    raw = (maximum - minimum) / max(target - 1, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    normalized = raw / magnitude
    step = 1 if normalized <= 1 else 2 if normalized <= 2 else 5 if normalized <= 5 else 10
    step *= magnitude
    start = math.floor(minimum / step) * step
    end = math.ceil(maximum / step) * step
    ticks = []
    value = start
    while value <= end + step * 0.001:
        ticks.append(round(value, 6)); value += step
    return ticks


def _estimate_label_box(px: float, py: float, y_offset: float, text: str, anchor: str, font_size: float = 14) -> tuple[float, float, float, float]:
    """Rough (left, right, top, bottom) bounding box of a <text> label in
    SVG user-unit space, from its anchor point and CSS text-anchor. Not
    exact glyph metrics -- deliberately generous (a slightly-too-wide/
    tall box only risks an unnecessary flip, never a missed real
    collision) so it is safe to use as an above/below placement gate."""
    char_w = font_size * 0.72
    w = len(text) * char_w
    # A generous +15% margin: real Chromium rendering caught two labels
    # ("39위", "64타") a plain 1.2x line-height box judged clear of
    # their line but that still grazed a corner in practice.
    h = font_size * 1.38
    baseline = py + y_offset
    top, bottom = baseline - h * 0.8, baseline + h * 0.3
    if anchor == "start":
        left, right = px, px + w
    elif anchor == "end":
        left, right = px - w, px
    else:
        left, right = px - w / 2, px + w / 2
    return left, right, top, bottom


def _segment_hits_box(p1: tuple[float, float], p2: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    """Sampled line-segment-vs-rectangle overlap test (20 sample points is
    ample for a short chart segment against a small label box)."""
    left, right, top, bottom = box
    for step in range(21):
        t = step / 20
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + (p2[1] - p1[1]) * t
        if left <= x <= right and top <= y <= bottom:
            return True
    return False


def line_chart_svg(*, title: str, player: str, series: list[dict], unit: str, invert: bool = False, dense: bool = False) -> str:
    """Render a dependency-free, accessible line chart with gaps for missing values.

    dense=True is for many-point charts (e.g. 18 holes): point-value text
    is rounded to 2 decimals with an explicit sign (0.017 -> "+0.02"),
    display formatting only -- the underlying series values (used in the
    chart's title/desc and its data-chart-series JSON payload) are never
    altered. Point labels also alternate a small vertical offset so
    adjacent close-together labels don't stack on top of each other.
    """
    width, height = 680, 260
    # left=92 (not 58): a y-axis tick label like "-10.0%" or "-20.0위",
    # right-anchored well clear of x=0, needs more clearance than even
    # 70 gave it once the sandbox's fallback (non-Pretendard) font
    # metrics are accounted for -- real Chromium rendering showed it
    # still clipping past the SVG's own left edge at 70, a defect no
    # static/string check could ever see.
    left, right, top, bottom = 92, 24, 24, 48
    values = [float(item["value"]) for item in series if item["value"] is not None]
    if not values:
        return ""
    low, high = min(values), max(values)
    if math.isclose(low, high):
        low -= 1; high += 1
    padding = max((high - low) * .12, .25)
    low -= padding; high += padding
    plot_w, plot_h = width - left - right, height - top - bottom

    def xy(index: int, value: float) -> tuple[float, float]:
        x = left + (plot_w * index / max(len(series) - 1, 1))
        ratio = (value - low) / (high - low)
        y = top + (plot_h * ratio if invert else plot_h * (1 - ratio))
        return x, y

    chart_id = "chart-" + hashlib.sha1(f"{title}:{player}".encode("utf-8")).hexdigest()[:10]
    svg_class = "line-chart line-chart--dense" if dense else "line-chart"
    parts = [f'<svg class="{svg_class}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{chart_id}-title {chart_id}-desc">',
             f'<title id="{chart_id}-title">{escape(player)} {escape(title)}</title>',
             f'<desc id="{chart_id}-desc">' + ", ".join(f'{escape(str(x["stage"]))} {"자료 없음" if x["value"] is None else escape(str(x["value"])) + unit}' for x in series) + '</desc>',
             f'<line class="chart-axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>',
             f'<line class="chart-axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>']
    # nice_ticks() floor/ceil-rounds to a "nice" step and can produce a
    # tick value outside [low, high] (e.g. 40.0 when the padded domain
    # only reaches 37.2) -- its y-coordinate then falls outside the plot
    # box entirely, clipped by the SVG's own overflow:hidden. Only ticks
    # that land inside the real plotted domain are ever drawn; this was
    # invisible to any static check and only showed up in real
    # Chromium-measured getBoundingClientRect() geometry.
    ticks = [t for t in nice_ticks(high, low, target=5) if low - 1e-9 <= t <= high + 1e-9]
    for value in ticks:
        ratio = (value - low) / (high - low)
        y = top + (plot_h * ratio if invert else plot_h * (1 - ratio))
        parts.append(f'<line class="chart-grid" x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}"/><text class="chart-y-label" x="{left-16}" y="{y+4:.1f}">{value:.1f}{escape(unit)}</text>')
    last_index = len(series) - 1
    # Real Chromium measurement: a dense-mode chart-value label renders
    # ~15 SVG-user-units tall (its own font-size 14 plus line-height/
    # descent); 20 gives real clearance rather than a hairline gap.
    DENSE_LABEL_MIN_GAP = 20
    # A dense label is ~45 SVG units wide (measured) against ~34 units of
    # horizontal point spacing -- it will always horizontally overlap its
    # immediate neighbors' point markers (radius 5), just not its own
    # (the vertical offset below already clears that). CIRCLE_CLEARANCE
    # keeps the label's vertical span off of a NEIGHBOR's marker too --
    # real Chromium rendering showed this specific gap (label-vs-a-
    # different-point's-circle, not label-vs-label) still overlapping
    # after only the label-vs-label spacing above was fixed.
    CIRCLE_CLEARANCE = 16
    prev_label_y: float | None = None
    point_positions: list[tuple[float, float] | None] = [
        xy(i, float(it["value"])) if it["value"] is not None else None
        for i, it in enumerate(series)
    ]
    segment: list[str] = []
    for index, item in enumerate(series):
        x = left + plot_w * index / max(len(series) - 1, 1)
        # Edge-aware anchoring: the first/last label anchors away from
        # the plot edge (start/end) instead of centering on it, so it
        # can never clip past the chart's own viewBox.
        edge = " chart-x-label--start" if index == 0 else (" chart-x-label--end" if index == last_index else "")
        parts.append(f'<text class="chart-x-label{edge}" x="{x:.1f}" y="{height-17}">{escape(str(item["stage"]))}</text>')
        if item["value"] is None:
            if len(segment) > 1: parts.append(f'<polyline class="chart-line" points="{" ".join(segment)}"/>')
            segment = []
            parts.append(f'<text class="chart-missing" x="{x:.1f}" y="{top+plot_h/2:.1f}">자료 없음</text>')
            continue
        px, py = xy(index, float(item["value"])); segment.append(f"{px:.1f},{py:.1f}")
        # data-point-index lets QA tooling tell "this label overlaps its
        # OWN point's marker" (expected -- the label sits close to the
        # point it labels) apart from "this label overlaps a DIFFERENT
        # point's marker" (a real collision).
        parts.append(f'<circle class="chart-point" data-point-index="{index}" cx="{px:.1f}" cy="{py:.1f}" r="5"><title>{escape(str(item["stage"]))}: {item["value"]}{escape(unit)}</title></circle>')
        # Display formatting only, never a change to the underlying
        # value used above in the circle's <title>, the chart's own
        # <desc>, or the data-chart-series JSON payload: a probability
        # value can carry 3 decimals in the source (win_probability
        # rounded to .3f elsewhere), which a real user's browser showed
        # rendering as "2.877%" -- unify every percentage chart to 2
        # decimals for *display*. Non-percentage sparse charts (rank,
        # raw score) keep their natural value as-is.
        if dense:
            display_value = f'{float(item["value"]):+.2f}'
        elif unit == "%":
            display_value = f'{float(item["value"]):.2f}'
        else:
            display_value = item["value"]
        if dense:
            # Real Chromium measurement showed a fixed index-parity
            # stagger (alternating a couple of preset offsets) is not
            # data-aware: when two adjacent points already sit far apart
            # (a real vertical gap in the data), blindly pulling each
            # label toward a preset level can actually pull them BACK
            # toward each other and cause the exact collision it was
            # meant to prevent (the "11~13번/17~18번 label collision"
            # defect found on the 18-hole SG chart). Instead, only push a
            # label away from the previous one when they'd actually end
            # up within MIN_GAP of each other -- most adjacent holes have
            # different enough values that no push is needed at all.
            candidate_y = py - 10
            if prev_label_y is not None and abs(candidate_y - prev_label_y) < DENSE_LABEL_MIN_GAP:
                candidate_y = (
                    prev_label_y - DENSE_LABEL_MIN_GAP if candidate_y <= prev_label_y
                    else prev_label_y + DENSE_LABEL_MIN_GAP
                )
            for neighbor in (index - 1, index + 1):
                if 0 <= neighbor < len(point_positions) and point_positions[neighbor] is not None:
                    _, neighbor_py = point_positions[neighbor]
                    if abs(candidate_y - neighbor_py) < CIRCLE_CLEARANCE:
                        candidate_y = (
                            neighbor_py - CIRCLE_CLEARANCE if candidate_y <= neighbor_py
                            else neighbor_py + CIRCLE_CLEARANCE
                        )
            y_offset = candidate_y - py
            # Never let the push move a label above the plot's own top
            # margin -- real Chromium rendering showed a point near the
            # top of the chart clipping past the SVG's top edge once
            # pushed upward (the "+1.47 clips chart edge" defect).
            if py + y_offset < top + 12:
                y_offset = (top + 12) - py
            prev_label_y = py + y_offset
        else:
            # A plain fixed "always above" offset ignores the connecting
            # line's own slope: a value label sitting just above its
            # point still lands squarely on top of a steeply-sloped
            # incoming/outgoing segment (a real, visually confirmed
            # defect on the R2->R3 win-probability chart -- "15.04%"
            # rendered with the connecting line drawn straight through
            # its own digits, found by re-inspecting a real Chromium
            # screenshot after the automated label/circle-only collision
            # check reported zero findings, since that check never
            # considered the <polyline> itself). Only flip the label
            # below the point -- mirroring the dense-mode "only push when
            # actually needed" rule -- when the adjacent segment(s)
            # genuinely intersect the estimated label box; most points
            # (a shallow slope, or both neighbors on the same side) never
            # trigger this and keep the plain default.
            anchor = "start" if index == 0 else ("end" if index == last_index else "middle")
            label_text = f'{display_value}{unit}'
            above_offset = -10
            above_box = _estimate_label_box(px, py, above_offset, label_text, anchor)
            collides = False
            if index > 0 and point_positions[index - 1] is not None:
                collides = collides or _segment_hits_box(point_positions[index - 1], (px, py), above_box)
            if index < last_index and point_positions[index + 1] is not None:
                collides = collides or _segment_hits_box((px, py), point_positions[index + 1], above_box)
            y_offset = above_offset
            if collides:
                below_offset = 22
                # Don't flip into the x-axis line/label strip at the
                # bottom of the plot -- if there isn't room below, keep
                # the (still imperfect, but not worse) above placement.
                if py + below_offset + 8 < height - bottom:
                    below_box = _estimate_label_box(px, py, below_offset, label_text, anchor)
                    below_collides = False
                    if index > 0 and point_positions[index - 1] is not None:
                        below_collides = below_collides or _segment_hits_box(point_positions[index - 1], (px, py), below_box)
                    if index < last_index and point_positions[index + 1] is not None:
                        below_collides = below_collides or _segment_hits_box((px, py), point_positions[index + 1], below_box)
                    if not below_collides:
                        y_offset = below_offset
                if y_offset == above_offset:
                    # Flipping below wasn't safe (too close to the x-axis
                    # strip) or didn't clear the line either -- as a last
                    # resort, push further in the same (above) direction
                    # for more clearance rather than leaving the label
                    # sitting right on the line.
                    farther_offset = -22
                    farther_box = _estimate_label_box(px, py, farther_offset, label_text, anchor)
                    farther_collides = False
                    if index > 0 and point_positions[index - 1] is not None:
                        farther_collides = farther_collides or _segment_hits_box(point_positions[index - 1], (px, py), farther_box)
                    if index < last_index and point_positions[index + 1] is not None:
                        farther_collides = farther_collides or _segment_hits_box((px, py), point_positions[index + 1], farther_box)
                    if not farther_collides and py + farther_offset > top + 12:
                        y_offset = farther_offset
        # Edge-anchoring the first/last VALUE label (unlike the x-axis
        # stage label, which stays edge-anchored in every mode) helps a
        # sparse chart's wide left margin but actively backfires in
        # dense mode: real measurement showed the first point's
        # start-anchored label extending rightward far enough to
        # overlap the very next point's label, in a chart where points
        # sit only ~34 units apart -- dense mode's generous left/right
        # margins already keep a plain middle-anchored label in bounds.
        value_edge = "" if dense else (" chart-value--start" if index == 0 else (" chart-value--end" if index == last_index else ""))
        parts.append(f'<text class="chart-value{value_edge}" data-point-index="{index}" x="{px:.1f}" y="{py+y_offset:.1f}">{display_value}{escape(unit)}</text>')
    if len(segment) > 1: parts.append(f'<polyline class="chart-line" points="{" ".join(segment)}"/>')
    parts.append(f'<script type="application/json" data-chart-series>{chart_json(series).replace("<", "\\u003c")}</script></svg>')
    return "".join(parts)


def accessible_series_table(player: str, title: str, series: list[dict], unit: str) -> str:
    cells = "".join(f'<tr><th scope="row">{escape(str(item["stage"]))}</th><td>{"자료 없음" if item["value"] is None else escape(str(item["value"])) + escape(unit)}</td></tr>' for item in series)
    return f'<table class="sr-data"><caption>{escape(player)} {escape(title)}</caption><thead><tr><th>시점</th><th>값</th></tr></thead><tbody>{cells}</tbody></table>'


def multi_line_chart_svg(*, title: str, series_by_player: dict[str, list[dict]], unit: str = "%") -> str:
    """Responsive accessible multi-player chart; missing points break lines."""
    width, height, left, right, top, bottom = 920, 390, 62, 170, 34, 58
    stages = next(iter(series_by_player.values()))
    values = [float(p["value"]) for series in series_by_player.values() for p in series if p["value"] is not None]
    high = max(values) if values else 1.0
    ticks = nice_ticks(high, 0, target=7)
    high = ticks[-1]
    colors = ("#0f5c46", "#b08b3e", "#537da6", "#9b493f")
    plot_w, plot_h = width-left-right, height-top-bottom
    parts = [f'<svg class="line-chart multi-line-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">']
    for value in ticks:
        y=top+plot_h*(1-value/high)
        label=f"{value:g}{unit}"
        parts.append(f'<line class="chart-grid" x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}"/><text class="chart-y-label" x="{left-9}" y="{y+4:.1f}">{label}</text>')
    for index,item in enumerate(stages):
        x=left+plot_w*index/max(len(stages)-1,1); parts.append(f'<text class="chart-x-label" x="{x:.1f}" y="{height-22}">{escape(item["stage"])}</text>')
    for color,(player,series) in zip(colors,series_by_player.items()):
        segments=[]; current=[]
        for i,item in enumerate(series):
            if item["value"] is None:
                if len(current)>1: segments.append(current)
                current=[]; continue
            x=left+plot_w*i/max(len(series)-1,1); y=top+plot_h*(1-float(item["value"])/high); current.append((x,y,item))
        if len(current)>1: segments.append(current)
        for segment in segments: parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{" ".join(f"{x:.1f},{y:.1f}" for x,y,_ in segment)}"/>')
        for i,item in enumerate(series):
            if item["value"] is None: continue
            x=left+plot_w*i/max(len(series)-1,1); y=top+plot_h*(1-float(item["value"])/high)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="white" stroke="{color}" stroke-width="3"><title>{escape(player)} {item["stage"]}: {item["value"]}{unit}</title></circle>')
    # Direct labels at the latest available checkpoint make identity independent of color.
    endpoints=[]
    for color,(player,series) in zip(colors,series_by_player.items()):
        index=next((i for i in range(len(series)-1,-1,-1) if series[i]["value"] is not None),None)
        if index is None: continue
        value=float(series[index]["value"]); y=top+plot_h*(1-value/high)
        endpoints.append([y, color, player, value, index])
    endpoints.sort(key=lambda item:item[0])
    min_gap=25
    for i,item in enumerate(endpoints):
        if i and item[0] < endpoints[i-1][0]+min_gap: item[0]=endpoints[i-1][0]+min_gap
    if endpoints and endpoints[-1][0] > top+plot_h:
        shift=endpoints[-1][0]-(top+plot_h)
        for item in endpoints: item[0]-=shift
    for y,color,player,value,index in endpoints:
        x=left+plot_w*index/max(len(stages)-1,1); label_x=width-right+12
        display_value = f'{value:.2f}' if unit == "%" else f'{value:g}'
        parts.append(f'<path class="chart-label-leader" d="M{x:.1f},{top+plot_h*(1-value/high):.1f} L{label_x-5},{y:.1f}" stroke="{color}"/><text class="chart-end-label" x="{label_x}" y="{y+5:.1f}">{escape(player)} {display_value}{escape(unit)}</text>')
    payload={p:s for p,s in series_by_player.items()}; parts.append(f'<script type="application/json" data-chart-series>{chart_json(payload).replace("<","\\u003c")}</script></svg>')
    return "".join(parts)


def bar_chart_svg(title: str, values: dict[str, float], unit: str = "") -> str:
    # right=70 (not 28): the peak-magnitude bar's value label sits past
    # the bar's own right edge (x + span + 7) with room for its own
    # text width -- 28px left the label clipping past the SVG's right
    # edge for any bar close to the field's peak magnitude, confirmed by
    # real Chromium rendering ("+1.47 clips chart edge").
    width,height,left,right,top,bottom=760,300,120,70,30,36
    peak=max(abs(v) for v in values.values()) or 1; row=(height-top-bottom)/len(values); zero=left+(width-left-right)/2
    parts=[f'<svg class="bar-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">']
    for i,(label,value) in enumerate(values.items()):
        y=top+i*row+5; span=(width-left-right)/2*abs(value)/peak; x=zero if value>=0 else zero-span
        parts.append(f'<text class="bar-label" x="{left-10}" y="{y+15}">{escape(label)}</text><rect x="{x:.1f}" y="{y:.1f}" width="{span:.1f}" height="20" class="bar-value"/><text class="bar-number" x="{(x+span+7 if value>=0 else x-7):.1f}" y="{y+15:.1f}">{value:+.2f}{escape(unit)}</text>')
    parts.append('</svg>'); return ''.join(parts)
