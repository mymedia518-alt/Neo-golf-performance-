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


def line_chart_svg(*, title: str, player: str, series: list[dict], unit: str, invert: bool = False) -> str:
    """Render a dependency-free, accessible line chart with gaps for missing values."""
    width, height = 680, 260
    left, right, top, bottom = 58, 18, 24, 48
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
    parts = [f'<svg class="line-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{chart_id}-title {chart_id}-desc">',
             f'<title id="{chart_id}-title">{escape(player)} {escape(title)}</title>',
             f'<desc id="{chart_id}-desc">' + ", ".join(f'{escape(str(x["stage"]))} {"자료 없음" if x["value"] is None else escape(str(x["value"])) + unit}' for x in series) + '</desc>',
             f'<line class="chart-axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>',
             f'<line class="chart-axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>']
    for tick in range(3):
        value = low + (high - low) * tick / 2
        y = top + (plot_h * tick / 2 if invert else plot_h * (1 - tick / 2))
        parts.append(f'<line class="chart-grid" x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}"/><text class="chart-y-label" x="{left-8}" y="{y+4:.1f}">{value:.1f}{escape(unit)}</text>')
    segment: list[str] = []
    for index, item in enumerate(series):
        x = left + plot_w * index / max(len(series) - 1, 1)
        parts.append(f'<text class="chart-x-label" x="{x:.1f}" y="{height-17}">{escape(str(item["stage"]))}</text>')
        if item["value"] is None:
            if len(segment) > 1: parts.append(f'<polyline class="chart-line" points="{" ".join(segment)}"/>')
            segment = []
            parts.append(f'<text class="chart-missing" x="{x:.1f}" y="{top+plot_h/2:.1f}">자료 없음</text>')
            continue
        px, py = xy(index, float(item["value"])); segment.append(f"{px:.1f},{py:.1f}")
        parts.append(f'<circle class="chart-point" cx="{px:.1f}" cy="{py:.1f}" r="5"><title>{escape(str(item["stage"]))}: {item["value"]}{escape(unit)}</title></circle>')
        parts.append(f'<text class="chart-value" x="{px:.1f}" y="{py-10:.1f}">{item["value"]}{escape(unit)}</text>')
    if len(segment) > 1: parts.append(f'<polyline class="chart-line" points="{" ".join(segment)}"/>')
    parts.append(f'<script type="application/json" data-chart-series>{chart_json(series).replace("<", "\\u003c")}</script></svg>')
    return "".join(parts)


def accessible_series_table(player: str, title: str, series: list[dict], unit: str) -> str:
    cells = "".join(f'<tr><th scope="row">{escape(str(item["stage"]))}</th><td>{"자료 없음" if item["value"] is None else escape(str(item["value"])) + escape(unit)}</td></tr>' for item in series)
    return f'<table class="sr-data"><caption>{escape(player)} {escape(title)}</caption><thead><tr><th>시점</th><th>값</th></tr></thead><tbody>{cells}</tbody></table>'
