"""PLAYER HISTORY GOLD STANDARD V1 renderer -- the generic engine.

Renders a dense, table/chart-first career archive from a real
PLAYER_HISTORY.json-shaped doc (playerCode=10097's is built by
scripts/build_10097_player_history.py). History first, explanation
second, speculation never -- this renderer adds no new claims, it only
formats what the builder already verified.

MISSION "PLAYER COMPARISON, ARCHITECTURE FIRST" (2026-09-28): "Kim
Min-seon 7 is no longer the goal. She is the template." Every function
below already took its data as plain arguments (doc, rows, values) --
the one real player-10097-specific thing left in this module was its
own hardcoded loading path, now replaced by player_provider.py's
generic load_player_history(player_code). render_player_history_html()
itself is unchanged: pure function, doc in, HTML out, works for any
player whose doc has this shape. This is a pure reorganization -- the
rendered output for playerCode=10097 is unchanged (verified byte-for-
byte against the pre-refactor build)."""
from __future__ import annotations

from html import escape
from typing import Optional

from klpga.website_v2 import player_history_terms as terms
from klpga.website_v2.player_provider import load_player_history


def load_report_cached(player_code: str = "10097") -> Optional[dict]:
    """Back-compat shim over player_provider.load_player_history --
    kept so nothing importing this name has to change, but the default
    player_code arg exists only for that reason. New call sites should
    call player_provider.load_player_history(player_code) directly, or
    go through PlayerProvider(player_code).history() (the same
    function, for a caller that wants a named object -- e.g. Compare
    Mode, which holds one provider per player)."""
    return load_player_history(player_code)


def _chip(text: str, positive: bool = False, negative: bool = False) -> str:
    # MISSION V12 (2026-09-25): .label-chip--negative already existed in
    # CSS (red) but no caller could ever reach it -- positive=False just
    # fell back to the bare .label-chip, which is visually IDENTICAL to
    # .label-chip--positive (both green). Every "this was the weak one"
    # chip on the page therefore looked exactly like a "this was the
    # strong one" chip, forcing the reader to read the number to tell
    # them apart. `negative` is opt-in (every existing call site keeps
    # its current look unless it explicitly passes negative=True for a
    # genuinely negative real value), so this never changes anything
    # already correct.
    if negative:
        cls = "label-chip label-chip--negative"
    elif positive:
        cls = "label-chip label-chip--positive"
    else:
        cls = "label-chip"
    return f'<span class="{cls}">{escape(str(text))}</span>'


def _chip_raw(inner_html: str, positive: bool = False, negative: bool = False) -> str:
    """MISSION V40 (2026-09-28): same shell as _chip(), for the rare
    chip that must contain real markup (a drill-down <a> link) instead
    of plain text. The caller is responsible for escaping every
    dynamic piece inside `inner_html` itself -- _chip() remains the
    default for a plain string, since it escapes automatically."""
    if negative:
        cls = "label-chip label-chip--negative"
    elif positive:
        cls = "label-chip label-chip--positive"
    else:
        cls = "label-chip"
    return f'<span class="{cls}">{inner_html}</span>'


def _tournament_link(name: str, game_code: Optional[str]) -> str:
    """MISSION V40 (2026-09-28): 'Every visualization must also be a
    navigation object... Career -> Season -> Tournament -> Round ->
    Hole.' Every place a specific real tournament is named becomes a
    real <a href="#t-{game_code}"> jump to that tournament's own row in
    the full tournament table (_tournament_table_html, which anchors
    every row by its real game_code) -- zero client-side script; a
    browser natively opens a closed <details> when navigating to an
    anchor inside it. Falls back to plain escaped text when no real
    game_code is available for this mention."""
    safe_name = escape(name)
    if not game_code:
        return safe_name
    return f'<a href="#t-{escape(str(game_code))}">{safe_name}</a>'


_NO_DATA = "—"  # em dash -- the one and only "not measured" glyph used in rendered output


def _fmt(v, plus: bool = True) -> str:
    if v is None:
        return _NO_DATA
    if isinstance(v, float):
        return f"{v:+.2f}" if plus else f"{v:.2f}"
    return str(v)


def _sparkline_svg(values: list, width: int = 200, height: int = 40) -> str:
    """Minimal inline-SVG line sparkline over real values only -- no
    external chart library, no decorative elements, axis-free by design
    (the numeric table next to every sparkline already carries the
    real values; the line exists only to show shape/direction)."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad = 4
    n = len(values)
    step = (width - 2 * pad) / (n - 1)
    points = []
    for i, v in enumerate(values):
        x = pad + i * step
        y = height - pad - ((v - lo) / span) * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")
    path = " ".join(points)
    dots = "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="2.4" fill="#0f5c46"/>' for p in points)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="추세선">'
        f'<polyline points="{path}" fill="none" stroke="#0f5c46" stroke-width="2"/>{dots}</svg>'
    )


def _marked_trend_svg(
    values: list,
    *,
    width: int = 640,
    height: int = 150,
    marks: Optional[dict] = None,
    x_labels: Optional[dict] = None,
    baseline: Optional[float] = None,
    baseline_label: str = "",
) -> str:
    """MISSION "PLAYER HISTORY V20" (2026-09-28): 'Every trend graph
    should show direction, volatility, turning point, latest value,
    best value, worst value, season markers.' One chart primitive for
    every trend on this page -- replaces the bare axis-free sparkline
    with a real line chart: direction is the line's own color (green
    if the series ends at or above where it started, red otherwise),
    `marks` labels any already-computed points worth calling out
    (best/worst/latest/turning point -- the caller decides which,
    never invented here), `x_labels` draws real season-boundary ticks
    along the bottom, `baseline` draws a real reference value (e.g.
    the career average) as a dashed line. No value plotted here is
    computed by this function -- it only lays out numbers the caller
    already has."""
    if len(values) < 2:
        return ""
    marks = marks or {}
    x_labels = x_labels or {}
    lo, hi = min(values + ([baseline] if baseline is not None else [])), max(values + ([baseline] if baseline is not None else []))
    span = (hi - lo) or 1.0
    top_pad, bottom_pad, side_pad = 22, (20 if x_labels else 8), 8
    plot_h = height - top_pad - bottom_pad
    n = len(values)
    step = (width - 2 * side_pad) / (n - 1)

    def _xy(i, v):
        x = side_pad + i * step
        y = top_pad + plot_h - ((v - lo) / span) * plot_h
        return x, y

    direction_color = "#0f5c46" if values[-1] >= values[0] else "#9b493f"
    pts = [_xy(i, v) for i, v in enumerate(values)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    parts = []
    if baseline is not None:
        by = _xy(0, baseline)[1]
        parts.append(
            f'<line x1="{side_pad}" y1="{by:.1f}" x2="{width - side_pad}" y2="{by:.1f}" '
            'stroke="#8a988f" stroke-width="1" stroke-dasharray="3 3"/>'
        )
        if baseline_label:
            parts.append(f'<text x="{width - side_pad}" y="{by - 4:.1f}" font-size="10" fill="#5d6964" text-anchor="end">{escape(baseline_label)}</text>')

    if x_labels:
        axis_y = top_pad + plot_h
        parts.append(f'<line x1="{side_pad}" y1="{axis_y:.1f}" x2="{width - side_pad}" y2="{axis_y:.1f}" stroke="#d5ddd7" stroke-width="1"/>')
        for i, label in sorted(x_labels.items()):
            x = _xy(i, values[i])[0]
            # text-anchor="middle" clips the first/last tick label
            # against the viewBox edge (e.g. "2023" rendering as
            # ":023") -- anchor start/end at the two ends, same fix
            # already used for the mark labels below.
            tick_anchor = "start" if x < side_pad + 20 else ("end" if x > width - side_pad - 20 else "middle")
            parts.append(f'<line x1="{x:.1f}" y1="{axis_y:.1f}" x2="{x:.1f}" y2="{axis_y + 5:.1f}" stroke="#8a988f" stroke-width="1"/>')
            parts.append(f'<text x="{x:.1f}" y="{axis_y + 15:.1f}" font-size="10" fill="#5d6964" text-anchor="{tick_anchor}">{escape(str(label))}</text>')

    parts.append(f'<polyline points="{path}" fill="none" stroke="{direction_color}" stroke-width="2"/>')
    for x, y in pts:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{direction_color}" fill-opacity="0.55"/>')

    # MISSION V60 (2026-09-28): "remove every numeric label drawn
    # inside charts... values appear only in tooltips or summary
    # cards." The always-visible mark labels this used to draw
    # directly on the line are gone -- every caller of this shared
    # primitive already has a real chip/card row of its own beneath
    # the chart carrying the same real values (with more context, e.g.
    # real tournament names), so nothing is lost. Each mark's real
    # detail (`title`, falling back to the old `label` text for any
    # caller that has not been updated) survives as a native hover
    # tooltip on its own dot.
    for i, m in sorted(marks.items()):
        if i < 0 or i >= n:
            continue
        x, y = pts[i]
        color = m.get("color", direction_color)
        title_text = m.get("title") or m.get("label") or ""
        title_html = f'<title>{escape(title_text)}</title>' if title_text else ""
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#fff" stroke-width="1.5">{title_html}</circle>')

    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="추세 그래프">'
        f'{"".join(parts)}</svg>'
    )


import math as _math


def _radar_svg(axes: list, size: int = 360) -> str:
    """5-axis percentile radar (0-100 scale only -- never a raw SG unit
    plotted directly). An axis with percentile=None is never plotted as
    if it were 0 -- it is simply left out of the polygon and reported as
    unavailable below the chart, per the mission's explicit 'render as
    unavailable, never estimate' rule."""
    available = [a for a in axes if a.get("percentile") is not None]
    if not available:
        return ""
    n = len(axes)
    cx = cy = size / 2
    radius = size / 2 - 95
    angle = lambda i: -_math.pi / 2 + i * 2 * _math.pi / n

    def point(i, pct):
        r = radius * (pct / 100.0)
        return cx + r * _math.cos(angle(i)), cy + r * _math.sin(angle(i))

    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{radius * f:.1f}" fill="none" stroke="#d8e2dc" stroke-width="1"/>'
        for f in (0.25, 0.5, 0.75, 1.0)
    )
    spokes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{cx + radius * _math.cos(angle(i)):.1f}" y2="{cy + radius * _math.sin(angle(i)):.1f}" stroke="#d8e2dc" stroke-width="1"/>'
        for i in range(n)
    )
    # MISSION V60 (2026-09-28): "remove every numeric label drawn
    # inside charts... values appear only in tooltips or summary
    # cards." Each axis dot now carries its own real percentile as a
    # <title> tooltip instead of always-visible text; the axis label
    # itself drops back to just the skill name. The exact number still
    # has a real, always-visible home in the delta table beneath this
    # chart (which prints 백분위 again since it is no longer the only
    # place showing it).
    poly_points = []
    dots = []
    for i, a in enumerate(axes):
        if a.get("percentile") is None:
            continue
        x, y = point(i, a["percentile"])
        poly_points.append(f"{x:.1f},{y:.1f}")
        axis_ko = terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"])
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#0f5c46"><title>{escape(axis_ko)} {a["percentile"]:.0f}</title></circle>')
    polygon = f'<polygon points="{" ".join(poly_points)}" fill="#0f5c4633" stroke="#0f5c46" stroke-width="2"/>' if len(poly_points) >= 3 else ""
    labels = []
    for i, a in enumerate(axes):
        lx = cx + (radius + 18) * _math.cos(angle(i))
        ly = cy + (radius + 18) * _math.sin(angle(i))
        anchor = "middle"
        if lx < cx - 5:
            anchor = "end"
        elif lx > cx + 5:
            anchor = "start"
        axis_ko = terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"])
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="10" fill="#3d4a43">{escape(axis_ko)}</text>')
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" class="ph-spark ph-spark--radar" role="img" aria-label="Performance Profile 레이더">'
        f'{rings}{spokes}{polygon}{"".join(dots)}{"".join(labels)}</svg>'
    )


def _radar_svg_overlay(axes_a: list, axes_b: list, label_a: str, label_b: str, size: int = 360) -> str:
    """Two-season comparison overlay -- only ever called when BOTH
    seasons have all 5 axes available (checked by the caller), so this
    never mixes a real polygon with a fabricated one."""
    n = len(axes_a)
    cx = cy = size / 2
    radius = size / 2 - 95
    angle = lambda i: -_math.pi / 2 + i * 2 * _math.pi / n

    def poly(axes, color):
        pts = []
        for i, a in enumerate(axes):
            r = radius * (a["percentile"] / 100.0)
            x = cx + r * _math.cos(angle(i))
            y = cy + r * _math.sin(angle(i))
            pts.append(f"{x:.1f},{y:.1f}")
        return f'<polygon points="{" ".join(pts)}" fill="{color}33" stroke="{color}" stroke-width="2"/>'

    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{radius * f:.1f}" fill="none" stroke="#d8e2dc" stroke-width="1"/>'
        for f in (0.25, 0.5, 0.75, 1.0)
    )
    spokes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{cx + radius * _math.cos(angle(i)):.1f}" y2="{cy + radius * _math.sin(angle(i)):.1f}" stroke="#d8e2dc" stroke-width="1"/>'
        for i in range(n)
    )
    labels = []
    for i, a in enumerate(axes_a):
        lx = cx + (radius + 18) * _math.cos(angle(i))
        ly = cy + (radius + 18) * _math.sin(angle(i))
        anchor = "middle"
        if lx < cx - 5:
            anchor = "end"
        elif lx > cx + 5:
            anchor = "start"
        axis_ko = terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"])
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="10" fill="#3d4a43">{escape(axis_ko)}</text>')
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" class="ph-spark ph-spark--radar" role="img" aria-label="{escape(label_a)} vs {escape(label_b)} 비교">'
        f'{rings}{spokes}{poly(axes_a, "#0f5c46")}{poly(axes_b, "#c98a1a")}{"".join(labels)}</svg>'
    )


def _trend_svg_by_index(
    values: list, markers: list, seasons: Optional[list] = None, hover: Optional[list] = None,
    width: int = 640, height: int = 118, compare: Optional[dict] = None,
) -> str:
    """Chronological performance trend (x = tournament order, never
    rank -- equal spacing means equal chronological step, not equal
    performance). markers[i] in {'win','top10',None} highlights wins
    and top10s distinctly from ordinary finishes.

    MISSION "PLAYER HISTORY V20" (2026-09-28): 'latest value, best
    value, worst value, season markers' -- her single best and worst
    real SG Total in this chronological series are labeled directly on
    the line (already-computed values, just min()/max() over what is
    already plotted, no new metric), and `seasons` (real per-
    tournament season already on every row) draws real season-boundary
    ticks along the bottom, same as the other rebuilt charts.

    MISSION V30 (2026-09-28): 'Hover -> Tournament / Round / SG /
    Finish.' This site renders no client-side script anywhere (see
    every other chart on this page), so real interactivity means the
    browser's OWN native SVG <title> tooltip, not invented JS --
    `hover[i]` is one already-formatted real detail string per point.

    MISSION "PLAYER COMPARISON, ARCHITECTURE FIRST" (2026-09-28):
    'render the SAME visualization with another player using the
    identical scale, identical time axis, identical colors, identical
    calculations.' `compare`, when given, is a second real series
    {"values": [...], "markers": [...], "hover": [...] (optional),
    "label": "..."} plotted on this exact same primitive -- same y
    scale (computed across BOTH series, so neither is silently
    rescaled relative to the other), same win/top10 semantic dot
    colors, same x step. This is the only trend-chart function in the
    engine; `compare=None` (the default, every existing single-player
    call site) is byte-identical to this function before this
    parameter existed -- verified against the pre-refactor build."""
    if len(values) < 2:
        return ""
    all_values = list(values) + (list(compare["values"]) if compare else [])
    lo, hi = min(all_values), max(all_values)
    span = (hi - lo) or 1.0
    top_pad, bottom_pad, pad = 16, (18 if seasons else 6), 6
    plot_h = height - top_pad - bottom_pad
    n = len(values)
    step = (width - 2 * pad) / (n - 1)
    pts = []
    for i, v in enumerate(values):
        x = pad + i * step
        y = top_pad + plot_h - ((v - lo) / span) * plot_h
        pts.append((x, y))
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    dots = []
    for i, ((x, y), m) in enumerate(zip(pts, markers)):
        title = f'<title>{escape(hover[i])}</title>' if hover else ""
        if m == "win":
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#c98a1a" stroke="#7a5610" stroke-width="1">{title}</circle>')
        elif m == "top10":
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#0f5c46">{title}</circle>')
        else:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="#9db3a8">{title}</circle>')

    axis = []
    if seasons:
        axis_y = top_pad + plot_h
        axis.append(f'<line x1="{pad}" y1="{axis_y:.1f}" x2="{width - pad}" y2="{axis_y:.1f}" stroke="#d5ddd7" stroke-width="1"/>')
        seen: set = set()
        for i, s in enumerate(seasons):
            if s in seen:
                continue
            seen.add(s)
            x = pts[i][0]
            tick_anchor = "start" if x < pad + 20 else ("end" if x > width - pad - 20 else "middle")
            axis.append(f'<line x1="{x:.1f}" y1="{axis_y:.1f}" x2="{x:.1f}" y2="{axis_y + 5:.1f}" stroke="#8a988f" stroke-width="1"/>')
            axis.append(f'<text x="{x:.1f}" y="{axis_y + 15:.1f}" font-size="10" fill="#5d6964" text-anchor="{tick_anchor}">{escape(str(s))}</text>')

    # MISSION V60 (2026-09-28): "remove every numeric label drawn inside
    # charts... values appear only in tooltips or summary cards." The
    # always-visible "최고/최저 ±X.XX" text this used to draw on the
    # chart is gone -- the real best/worst tournament and value already
    # have a real summary-card home wherever this chart is called from
    # (the highlight cards under the tournament timeline, the peak/
    # slump chips under each season's chart), so nothing is lost, only
    # de-duplicated. The marker dot stays, now carrying its own real
    # <title> tooltip.
    best_i, worst_i = max(range(n), key=lambda i: values[i]), min(range(n), key=lambda i: values[i])
    marks = []
    for i, color, tag in ((best_i, "#0f5c46", "최고"), (worst_i, "#9b493f", "최저")):
        x, y = pts[i]
        marks.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#fff" stroke-width="1.5">'
            f'<title>{tag} {values[i]:+.2f}</title></circle>'
        )

    compare_svg = ""
    if compare:
        c_values = compare["values"]
        c_markers = compare.get("markers") or [None] * len(c_values)
        c_hover = compare.get("hover")
        c_n = len(c_values)
        c_step = (width - 2 * pad) / (c_n - 1) if c_n > 1 else 0
        c_pts = [(pad + i * c_step, top_pad + plot_h - ((v - lo) / span) * plot_h) for i, v in enumerate(c_values)]
        c_path = " ".join(f"{x:.1f},{y:.1f}" for x, y in c_pts)
        c_dots = []
        for i, ((x, y), m) in enumerate(zip(c_pts, c_markers)):
            c_title = f'<title>{escape(c_hover[i])}</title>' if c_hover else ""
            if m == "win":
                c_dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#c98a1a" stroke="#7a5610" stroke-width="1" fill-opacity="0.85">{c_title}</circle>')
            elif m == "top10":
                c_dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#0f5c46" fill-opacity="0.85">{c_title}</circle>')
            else:
                c_dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="#9db3a8" fill-opacity="0.85">{c_title}</circle>')
        # a dashed, distinctly-colored line keeps the second player's
        # trend visually separable from the primary -- win/top10 dots
        # stay the SAME semantic colors as the primary series (gold/
        # green), per "identical colors" for what a color MEANS.
        compare_svg = f'<polyline points="{c_path}" fill="none" stroke="#5a3d8a" stroke-width="1.5" stroke-dasharray="5 3"/>{"".join(c_dots)}'

    aria = f'{escape(compare.get("label", ""))} 비교' if compare else "대회별 SG Total 추세 (시간순)"
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="{aria}">'
        f'{"".join(axis)}<polyline points="{path}" fill="none" stroke="#0f5c46" stroke-width="1.5"/>{"".join(dots)}{"".join(marks)}{compare_svg}</svg>'
    )


# ---------------------------------------------------------------------------
# SEASON TABLE -- extracted, reused only at the tail of Career Story
# (#5), where real chronological seasons are revealed last.
# ---------------------------------------------------------------------------

def _season_table_html(co: dict) -> str:
    rows = co["season_rows"]
    cols = ["season", "events", "wins", "top5", "top10", "top20", "sg_total", "sg_ott", "sg_app", "sg_arg", "sg_putt", "sg_sample_size"]
    labels = terms.SEASON_TABLE_COLUMNS
    header = "".join(f"<th>{escape(labels[c])}</th>" for c in cols)
    body_rows = []
    for r in rows:
        cells = []
        for c in cols:
            v = r[c]
            cells.append(f"<td>{_fmt(v) if isinstance(v, float) else v}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    table_inner = f'<div class="table-scroll"><table class="data-table"><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
    # MISSION "PLAYER HISTORY V20" (2026-09-28): 'No more tables. Tables
    # should become graphics whenever possible.' Every metric this table
    # carries (SG Total/OTT/APP/ARG/PUTT, wins, Top5/10/20) is now a
    # real chart elsewhere on this page (Season Evolution, Momentum) --
    # the exact numbers stay real and available, just nested behind a
    # disclosure instead of sitting open as the primary view.
    table = (
        '<details class="ph-nested-detail">'
        '<summary>시즌별 전체 기록 보기</summary>'
        f'{table_inner}</details>'
    )

    latest = co.get("latest_tournament") or {}
    latest_tournament_name = escape(latest.get("tournament", ""))
    latest_season = latest.get("season")
    totals = (
        '<div class="piq-audit">'
        + _chip(f'{co["earliest_season_on_record"]}~{rows[-1]["season"]}시즌')
        + _chip(f'실측 {co["total_events"]}개 대회')
        + _chip(f'우승 {co["total_wins"]}회', positive=True)
        + _chip(f'Top5 {co["total_top5"]}회')
        + _chip(f'Top10 {co["total_top10"]}회')
        + _chip(f'Top20 {co["total_top20"]}회')
        + _chip(f'최근 대회: {latest_tournament_name} ({latest_season})')
        + "</div>"
    )
    floor_note = f'<p class="piq-current-detail">{escape(co["data_floor_note"])}</p>'
    return f'{totals}{floor_note}{table}'


# ---------------------------------------------------------------------------
# PAGE 2 -- CAREER EVOLUTION
# ---------------------------------------------------------------------------

_EVOLUTION_DISPLAY_ORDER = ["avg_total", "avg_ott", "avg_app", "avg_arg", "avg_putt"]


def _career_evolution_html(evolution: dict) -> str:
    """V6 mission (2026-09-25): 'spend the entire mission deleting.' The
    season-to-season delta TABLE (e.g. '2023→2024: 0.16타 개선') said
    exactly what the sparkline right above it already shows visually,
    plus what the peak/worst-season chips already flag as the extremes
    -- removing it does not make a reader understand her season-by-
    season trend any less, so it is gone. _delta_phrase_ko stays
    defined (still used elsewhere) even though this call site no
    longer needs it.

    MISSION "PLAYER HISTORY V20" (2026-09-28): 'Every trend graph
    should show direction, ... latest value, best value, worst value,
    season markers.' The peak/worst-season text chips this used to
    show below a bare sparkline are now drawn directly ON the chart
    (_marked_trend_svg) -- real season labels double as the x-axis, so
    nothing about this player's four real seasons is invented, only
    shown once instead of twice (as a mark on the line AND as a chip
    beneath it). Peak/worst/latest can land on the same real season
    (true for her SG Total, whose peak is also her current season) --
    merged into one label rather than two overlapping dots.

    MISSION V41 (2026-09-28): '15-second rule... no duplication.'
    Season Replay (#ph-season-replay, just below) already shows the
    same real season-by-season story per real tournament, richer (a
    chart plus an SG-component heatmap) than these four per-metric
    sparklines. Collapsed by default -- still real, still one click
    away for a reader who wants the per-metric breakdown, but no
    longer competing with the season replay for the same 15 seconds."""
    blocks = []
    for c in _EVOLUTION_DISPLAY_ORDER:
        data = evolution.get(c)
        if data is None:
            continue
        series = data["series"]
        values = [pt["value"] for pt in series]
        season_index = {pt["season"]: i for i, pt in enumerate(series)}
        peak_season, peak_raw = data["peak_season"]["season"], data["peak_season"]["value"]
        worst_season, worst_raw = data["worst_season"]["season"], data["worst_season"]["value"]
        latest_idx = len(series) - 1
        # MISSION V12: a "worst season" that is still a positive real
        # number is not a warning -- its marker stays neutral, never red.
        worst_color = "#9b493f" if worst_raw < 0 else "#5d6964"
        candidates = [
            (season_index[peak_season], "최고", _fmt(peak_raw), "#0f5c46"),
            (season_index[worst_season], "최저", _fmt(worst_raw), worst_color),
            (latest_idx, "현재", _fmt(values[latest_idx]), "#14201c"),
        ]
        marks: dict = {}
        for idx, tag, val_text, color in candidates:
            if idx in marks:
                marks[idx]["label"] = f'{marks[idx]["label"].split(" ")[0]}·{tag} {val_text}'
            else:
                marks[idx] = {"label": f"{tag} {val_text}", "color": color}
        x_labels = {i: pt["season"] for i, pt in enumerate(series)}
        chart = _marked_trend_svg(values, width=560, height=140, marks=marks, x_labels=x_labels)
        direction_label = terms.DIRECTION_LABEL.get(data["current_direction"], data["current_direction"])
        # MISSION V70 (2026-09-28): "No chart exists without a headline
        # insight... 5-second understanding." One real sentence, built
        # only from fields this block already computed (direction,
        # latest value, peak), placed ABOVE the chart so the reader
        # never has to read the chart to know what it says. Replaces
        # the old below-the-chart "현재 방향" chip, which said only the
        # direction word -- this headline says the same real direction
        # plus the two numbers that explain it, once.
        direction_css = {"UP": " piq-brief--positive", "DOWN": " piq-brief--negative"}.get(data["current_direction"], "")
        headline_html = (
            f'<div class="piq-brief{direction_css}"><p><strong>{escape(direction_label)}</strong> '
            f'현재 {_fmt(values[latest_idx])} · 커리어 최고 {_fmt(peak_raw)} ({escape(str(peak_season))}시즌)</p></div>'
        )
        blocks.append(
            '<div class="ph-evo-block">'
            f'<p class="piq-step-label piq-label-standalone">{escape(data["label"])}</p>'
            f'{headline_html}{chart}'
            "</div>"
        )
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-career-evolution">'
        f'<summary class="section-heading"><h2>{terms.PAGE2_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(blocks)}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 3 -- SEASON REPLAY
# ---------------------------------------------------------------------------

def _season_tournament_chart_svg(rows: list, width: int = 620) -> str:
    """MISSION V30 (2026-09-28): 'NO MORE first five/middle five/last
    five. Instead show Tournament 1, Tournament 2, ... If there are
    only three values, do not draw a graph.' Real per-tournament SG
    Total for every real tournament in one real season, chronological
    -- the same _trend_svg_by_index primitive the full-career timeline
    uses, scoped to one season, with hover detail on every point."""
    trend_rows = [r for r in rows if r.get("sg_total") is not None]
    if len(trend_rows) < 2:
        return ""
    values = [r["sg_total"] for r in trend_rows]
    markers = ["win" if r["is_win"] else ("top10" if r["is_top10"] else None) for r in trend_rows]
    hover = [f'{r["tournament"]} · 최종 {r["rank"]}위 · SG {_fmt(r["sg_total"])}' for r in trend_rows]
    return _trend_svg_by_index(values, markers, hover=hover, width=width, height=100)


def _season_replay_chart_svg(
    rows: list, peak: Optional[dict], slump: Optional[dict], recovery: Optional[dict], width: int = 1100,
) -> str:
    """MISSION V73 (2026-09-28): Season Replay's chart redesigned from
    scratch. 'Remove the unexplained SG heatmap... expand to nearly
    full desktop width... every tournament at its real position...
    tournament names visible on desktop... win/top10/best/worst/
    recovery distinguishable immediately, without reading text... the
    chart itself must explain the season.'

    Every real per-tournament row, plus the exact same real peak/
    slump/recovery facts _season_replay_html already computed for its
    chips, drawn on one wide chronological line -- no new computation.
    Win/top10/plain finishes are 3 real dot sizes+colors (same
    convention as every other trend chart on this page); peak/slump/
    recovery are a ring or marker drawn AROUND that same dot, so a
    tournament that is e.g. both a win and the season's peak shows
    both facts on one point, never two conflicting marks. The peak/
    slump/recovery numbers this used to say in prose are unchanged --
    still real, still on the page, just as a <title> tooltip and in
    the still-present (now collapsed, since the chart now carries the
    same conclusions) chip row beneath the chart."""
    trend_rows = [r for r in rows if r.get("sg_total") is not None]
    if len(trend_rows) < 2:
        return ""
    values = [r["sg_total"] for r in trend_rows]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(trend_rows)
    top_pad, bottom_pad, side_pad = 20, 92, 10
    height = 260
    plot_h = height - top_pad - bottom_pad
    step = (width - 2 * side_pad) / max(n - 1, 1)

    def _xy(i, v):
        x = side_pad + i * step
        y = top_pad + plot_h - ((v - lo) / span) * plot_h
        return x, y

    pts = [_xy(i, r["sg_total"]) for i, r in enumerate(trend_rows)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    peak_name = peak["tournament"] if peak else None
    slump_name = slump["tournament"] if slump else None
    recovery_name = recovery["tournament"] if recovery else None

    parts = [f'<polyline points="{path}" fill="none" stroke="#c3cec6" stroke-width="1.5"/>']
    labels = []
    for r, (x, y) in zip(trend_rows, pts):
        if r["is_win"]:
            color, radius = "#c98a1a", 6.5
        elif r["is_top10"]:
            color, radius = "#0f5c46", 4.5
        else:
            color, radius = "#9db3a8", 3
        title = f'{r["tournament"]} · 최종 {r["rank"]}위 · SG {_fmt(r["sg_total"])}'
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}"><title>{escape(title)}</title></circle>')
        if r["tournament"] == peak_name:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius + 4}" fill="none" stroke="#0f5c46" stroke-width="2">'
                f'<title>피크: {escape(title)}</title></circle>'
            )
        if r["tournament"] == slump_name:
            # MISSION V12: the ring is red only when this real SG Total
            # is actually negative -- a "slump" that is still a
            # positive number never renders as if it were bad.
            ring_color = "#9b493f" if r["sg_total"] < 0 else "#5d6964"
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius + 4}" fill="none" stroke="{ring_color}" stroke-width="2" '
                f'stroke-dasharray="2 2"><title>슬럼프: {escape(title)}</title></circle>'
            )
        if r["tournament"] == recovery_name:
            ty = y + radius + 10
            parts.append(
                f'<path d="M {x - 4:.1f} {ty:.1f} L {x:.1f} {ty - 5:.1f} L {x + 4:.1f} {ty:.1f} Z" fill="#0f5c46">'
                f'<title>슬럼프 직후 회복: {escape(title)}</title></path>'
            )
        short_name = r["tournament"][:7] + ("…" if len(r["tournament"]) > 7 else "")
        label_y = top_pad + plot_h + 14
        labels.append(
            f'<text class="ph-season-label" x="{x:.1f}" y="{label_y:.1f}" font-size="9.5" fill="#5d6964" '
            f'text-anchor="end" transform="rotate(-45 {x:.1f} {label_y:.1f})">{escape(short_name)}</text>'
        )
    parts.extend(labels)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" '
        f'role="img" aria-label="시즌 대회 타임라인">{"".join(parts)}</svg>'
    )


def _season_skill_heatmap_svg(rows: list, width: int = 620) -> str:
    """MISSION V30 (2026-09-28): 'Heatmaps replace many tables...
    immediately visible.' Real per-tournament SG component breakdown
    (already computed by the SG warehouse reconciliation this whole
    document is built from) -- one real cell per real tournament per
    component, color intensity scaled to that component's own real
    range this season. Never a table, never an average."""
    labeled = [r for r in rows if r.get("sg_components")]
    if len(labeled) < 2:
        return ""
    comp_keys = [("ott", "OTT"), ("app", "APP"), ("arg", "ARG"), ("putt", "PUTT")]
    # MISSION V70 (2026-09-28): "Heatmaps must become readable from 2
    # meters away." Taller bands, a higher color-intensity floor (a
    # near-zero value no longer fades to almost-white), a wider row
    # label at a bigger bold font, and a higher minimum cell width all
    # make the real color-by-sign signal legible at a glance -- the
    # exact values themselves are unchanged, still exact-only in each
    # cell's own tooltip.
    row_h = 30
    label_w = 52
    n = len(labeled)
    cell_w = max((width - label_w) / n, 6)
    height = row_h * len(comp_keys) + 4
    parts = []
    for ri, (key, label) in enumerate(comp_keys):
        vals = [r["sg_components"].get(key) for r in labeled if r["sg_components"].get(key) is not None]
        vmax = max((abs(v) for v in vals), default=0) or 1.0
        y = ri * row_h
        parts.append(f'<text x="0" y="{y + row_h * 0.65:.1f}" font-size="14" font-weight="700" fill="#3d4a43">{label}</text>')
        for ci, r in enumerate(labeled):
            v = r["sg_components"].get(key)
            x = label_w + ci * cell_w
            if v is None:
                color = "#e5e9e6"
                title = f'{r["tournament"]}: {label} 미수집'
            else:
                intensity = min(abs(v) / vmax, 1.0)
                color = f'rgba(15,92,70,{0.3 + 0.6 * intensity:.2f})' if v >= 0 else f'rgba(155,73,63,{0.3 + 0.6 * intensity:.2f})'
                title = f'{r["tournament"]}: {label} {_fmt(v)}'
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 2:.1f}" width="{max(cell_w - 1.5, 3):.1f}" height="{row_h - 4}" fill="{color}">'
                f'<title>{escape(title)}</title></rect>'
            )
    return f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="시즌 SG 구성 요소 히트맵">{"".join(parts)}</svg>'


def _season_replay_html(replays: list, tournament_history: Optional[list] = None) -> str:
    """V6 mission (2026-09-25): the per-season quartile table (four
    columns of event-count + average SG) asked the same question the
    peak/slump chips already answer more precisely (this season's real
    best and worst tournaments), just at coarser resolution -- removing
    it does not make a reader understand a given season any less, so
    it is gone.

    MISSION V30 (2026-09-28): the First-5/Middle-5/Last-5 windows that
    replaced that table (a 3-point line, exactly the 'wasted graph'
    this mission bans) are gone too -- every real tournament in the
    season now renders as its own point on a real chronological chart.

    MISSION V73 (2026-09-28): 'Remove the unexplained SG heatmap...
    the chart itself must explain the season, supporting text should
    become optional.' _season_skill_heatmap_svg is gone from this
    section (its real per-tournament SG component numbers are
    unchanged and still fully on the page, in the full tournament
    table's OTT/APP/ARG/PUTT columns) -- replaced by
    _season_replay_chart_svg, which draws win/top10/peak/slump/
    recovery all on the one chronological line. The chip row that used
    to be the only place stating peak/slump/recovery is unchanged in
    content but now nested behind a disclosure, since the chart now
    carries those same conclusions visually."""
    tournament_history = tournament_history or []
    blocks = []
    for r in replays:
        season_rows = [t for t in tournament_history if t.get("season") == r["season"]]
        # MISSION V40 (2026-09-28): scoped to this season's own rows,
        # so a repeated tournament name across two different seasons
        # never resolves to the wrong game_code.
        game_code_by_name = {t["tournament"]: t["game_code"] for t in season_rows}
        recovery = r.get("recovery_next_event")
        peak = r.get("peak")
        slump = r.get("slump")
        season_chart = _season_replay_chart_svg(season_rows, peak, slump, recovery)
        if recovery:
            recovery_tournament = _tournament_link(recovery["tournament"], game_code_by_name.get(recovery["tournament"]))
            recovery_sg = _fmt(recovery["sg_total"])
            recovery_delta = recovery["delta_vs_slump"]
            recovery_chip = _chip_raw(f'슬럼프 직후: {recovery_tournament} {recovery_sg} ({recovery_delta:+.2f})')
        else:
            recovery_chip = _chip("슬럼프 직후 대회 없음 (시즌 마지막 대회)")
        volatility_chip = _chip(f'변동성(표준편차) {r["volatility_stddev"]}') if r["volatility_stddev"] is not None else ""
        top10_chip = _chip(f'상위10위율 {r["top10_rate_pct"]}%')
        peak_chip = (
            _chip_raw(f'피크: {_tournament_link(peak["tournament"], game_code_by_name.get(peak["tournament"]))} {_fmt(peak["sg_total"])}', positive=True)
            if peak else ""
        )
        # MISSION V12: red only when the slump tournament's real SG
        # Total was actually negative -- her "slump" within a strong
        # season can still be a positive number, which red would
        # misrepresent as a bad round.
        slump_chip = (
            _chip_raw(
                f'슬럼프: {_tournament_link(slump["tournament"], game_code_by_name.get(slump["tournament"]))} {_fmt(slump["sg_total"])}',
                negative=slump["sg_total"] < 0,
            )
            if slump else ""
        )
        detail_chips = volatility_chip + top10_chip + peak_chip + slump_chip + recovery_chip
        detail = (
            f'<details class="ph-nested-detail"><summary>수치로 보기</summary>'
            f'<div class="piq-audit">{detail_chips}</div></details>'
        ) if detail_chips else ""
        blocks.append(
            '<div class="ph-evo-block">'
            f'<p class="piq-step-label piq-label-standalone">{r["season"]}시즌 ({r["event_count"]}개 대회)</p>'
            f'{season_chart}{detail}'
            "</div>"
        )
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-season-replay" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE3_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(blocks)}</div></details>'
    )


def _career_form_story_html(stages: Optional[list]) -> str:
    """NEO V2 BRAND CONSISTENCY mission (2026-09-29): "Convert the season
    timeline from storytelling to analytics... no narrative sentences,
    no verbs, no interpretation, display measurements only." Replaces
    the former story-sentence-per-card layout (a generated clause like
    "SG APP가 이 시기를 이끌었습니다") with one dashboard row per stage:
    Phase / Career Delta / Best SG / Worst SG / Reference Events /
    Sample Size. Every value is a field _career_form_story()
    (scripts/build_10097_player_history.py) already computed -- Sample
    Size is real data that already existed in that function's own
    per-window decomposition (sg_component_sample_size) but was
    previously discarded before reaching this renderer; it is plumbed
    through, not newly computed.

    When her career peak (전성기) happened to fall inside the same real
    tournament range as one of the three season chapters -- true for
    this player as of this build -- the two labels are combined into
    one row instead of repeating identical numbers twice."""
    if not stages:
        return ""
    seen: dict = {}
    order = []
    for s in stages:
        key = (s["start_tournament"], s["end_tournament"])
        if key in seen:
            seen[key]["stage"] = seen[key]["stage"] + " · " + s["stage"]
        else:
            seen[key] = dict(s)
            order.append(key)
    merged = [seen[k] for k in order]

    def _sg(component, delta):
        return f'{escape(component)} {delta:+.2f}' if component and delta is not None else _NO_DATA

    rows = []
    for s in merged:
        start_t, end_t = escape(s["start_tournament"]), escape(s["end_tournament"])
        reference = start_t if s["start_tournament"] == s["end_tournament"] else f"{start_t} ~ {end_t}"
        delta = s.get("delta_vs_career_average")
        delta_cell = f'{delta:+.2f}' if delta is not None else _NO_DATA
        sample_size = s.get("sample_size")
        rows.append(
            "<tr>"
            f'<td>{escape(s["stage"])}</td>'
            f'<td>{delta_cell}</td>'
            f'<td>{_sg(s.get("best_component"), s.get("best_delta"))}</td>'
            f'<td>{_sg(s.get("worst_component"), s.get("worst_delta"))}</td>'
            f'<td>{reference}</td>'
            f'<td>{sample_size if sample_size is not None else _NO_DATA}</td>'
            "</tr>"
        )
    header = "".join(f"<th>{h}</th>" for h in ("Phase", "Career Delta", "Best SG", "Worst SG", "Reference Events", "Sample Size"))
    table = f'<div class="table-scroll"><table class="data-table"><thead><tr>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    return f'<div class="ph-form-story">{table}</div>'


def _career_rolling_trend_html(crt: Optional[dict], story: Optional[list] = None) -> str:
    """V4 mission originally built this as career-wide Moving Average /
    Peak / Slump / Recovery Window analysis over a real sliding window
    of finished tournaments. RED TEAM (2026-09-25): that computation is
    completely unchanged (see _career_rolling_trend in the builder) --
    only what's SHOWN changes. The Career Form Story
    (_career_form_story_html) now leads, story-first; window mechanics
    (window size, total window count, moving average, percentile among
    windows) are never rendered here -- career_rolling_trend's own JSON
    still carries them for anyone inspecting the raw data. Peak/slump/
    recovery stay as supporting, real detail beneath the story, reworded
    to name real tournaments/tournament counts instead of window counts."""
    if not crt or not crt.get("series"):
        note = crt.get("note") if crt else None
        return (
            '<div class="ph-evo-block" id="ph-career-rolling-trend">'
            '<p class="piq-current-detail">실측 대회 수가 아직 부족해 시즌 흐름을 정리할 수 없습니다.</p>'
            '</div>'
        )

    values = [w["moving_average_sg_total"] for w in crt["series"]]
    career_avg = crt.get("career_average_sg_total")

    # MISSION "PLAYER HISTORY V20" (2026-09-28): the bare axis-free
    # sparkline is replaced with a real chart -- peak/slump/recovery
    # windows (already-computed turning points), the career-average
    # baseline, and real season boundaries all drawn directly on the
    # line, using _marked_trend_svg. window_index already IS this
    # series' own list index (verified against the builder's output),
    # so no new lookup/computation is added here.
    season_ticks: dict = {}
    seen_seasons: set = set()
    for i, w in enumerate(crt["series"]):
        if w["start_season"] not in seen_seasons:
            season_ticks[i] = w["start_season"]
            seen_seasons.add(w["start_season"])
    mark_candidates = []
    if crt.get("peak_window"):
        pw = crt["peak_window"]
        mark_candidates.append((pw["window_index"], "전성기", _fmt(pw["moving_average_sg_total"]), "#0f5c46"))
    if crt.get("slump_window"):
        sw = crt["slump_window"]
        mark_candidates.append((sw["window_index"], "슬럼프", _fmt(sw["moving_average_sg_total"]), "#9b493f"))
    if crt.get("recovery_window"):
        rw = crt["recovery_window"]
        mark_candidates.append((rw["window_index"], "회복", _fmt(rw["moving_average_sg_total"]), "#0f5c46"))
    mark_candidates.append((len(values) - 1, "현재", _fmt(values[-1]), "#14201c"))
    marks: dict = {}
    for idx, tag, val_text, color in mark_candidates:
        if idx in marks:
            marks[idx]["label"] = f'{marks[idx]["label"].split(" ")[0]}·{tag} {val_text}'
        else:
            marks[idx] = {"label": f"{tag} {val_text}", "color": color}
    spark = _marked_trend_svg(
        values, width=640, height=150, marks=marks, x_labels=season_ticks,
        baseline=career_avg, baseline_label="커리어 평균" if career_avg is not None else "",
    )

    def _window_chip(label: str, w: Optional[dict], positive: bool = False) -> str:
        """V6 mission: lead with the delta vs career average, never the
        bare SG Total alone. RED TEAM (2026-09-25): self-percentile
        (rank among her own other windows) is never shown -- an
        implementation detail of how the window was found, not a story
        fact. MISSION V20 (2026-09-28): the trailing '(실측 SG X)'
        parenthetical is dropped -- that exact number is now the mark's
        own label directly on the chart above, so restating it here
        would be exactly the repeated text this mission forbids."""
        if not w:
            return ""
        vs_avg = w.get("delta_vs_career_average")
        vs_avg_text = f'커리어 평균 대비 {vs_avg:+.2f}' if vs_avg is not None else f'SG {_fmt(w["moving_average_sg_total"])}'
        is_negative = (vs_avg if vs_avg is not None else w["moving_average_sg_total"]) < 0
        return _chip(
            f'{label}: {escape(w["start_tournament"])}~{escape(w["end_tournament"])} {vs_avg_text}',
            positive=positive, negative=(not positive and is_negative),
        )

    recovery = crt.get("recovery_window")
    recovery_chip = (
        _chip(
            f'회복기: 슬럼프기 대비 {recovery["delta_vs_slump"]:+.2f} '
            f'(커리어 평균 대비 {recovery["delta_vs_career_average"]:+.2f})',
            positive=recovery["delta_vs_slump"] > 0,
        )
        if recovery else _chip("슬럼프기 이후 회복기 없음 (커리어 마지막 시기)")
    )
    career_median = crt.get("career_median_sg_total")
    career_median_chip = _chip(f'커리어 중앙값 SG {_fmt(career_median, plus=False)}') if career_median is not None else ""

    peak = crt.get("peak_window")
    # NEO V3 BRAND CONSISTENCY mission (2026-09-29): "이어졌습니다" verb
    # removed -- bare label + count, same real field.
    sustain_chip = (
        _chip(f'Peak Duration {peak["sustainability_tournaments"]} Tournaments', positive=True)
        if peak and peak.get("sustainability_windows") else ""
    )
    recovery_time_chip = _chip(crt.get("recovery_time_note", "")) if crt.get("recovery_time_windows") is not None else ""

    # V5 mission ("delete everything else"): career_avg_chip and a plain
    # 전성기 delta chip are dropped here -- the Current Form hero already
    # states the career average, and Career Form Story's own 전성기 card
    # (rendered just above, via _career_form_story_html) already covers
    # the peak with a real best/worst-skill sentence. Only what neither
    # of those two already says -- slump, recovery, and how long the
    # peak lasted -- survives as a chip here.
    decomposition_html = "".join(
        _window_decomposition_html(label, w)
        for label, w in (("슬럼프기", crt.get("slump_window")), ("회복기", recovery))
        if w
    )
    return (
        '<div class="ph-evo-block" id="ph-career-rolling-trend">'
        f'{_career_form_story_html(story)}'
        f'{spark}'
        '<p class="piq-step-label piq-label-standalone">슬럼프기 · 회복기</p>'
        '<div class="piq-audit">'
        + career_median_chip
        + _window_chip("슬럼프기", crt.get("slump_window"))
        + recovery_chip
        + sustain_chip
        + recovery_time_chip
        + '</div>'
        f'{decomposition_html}'
        '</div>'
    )


def _heartbeat_track_svg(beats: list, value_key: str, center_value: float, width: int = 900, height: int = 110) -> str:
    """One lane of the Career Heartbeat -- every finished tournament as
    one deviation-from-center bar (never an absolute value plotted
    directly). Win/Top10/normal are marked distinctly; the zero line is
    a real measured value (career average, or the percentile
    midpoint), never an arbitrary origin. Generic over which real
    per-beat field it plots, so Track 1 (SG deviation) and Track 2
    (self-percentile deviation) share one implementation."""
    if not beats:
        return ""
    n = len(beats)
    pad = 6
    step = (width - 2 * pad) / max(n - 1, 1)
    baseline = height / 2
    deviations = [b[value_key] - center_value for b in beats]
    max_abs = max(abs(d) for d in deviations) or 1.0
    scale = (baseline - 10) / max_abs
    bars = []
    for i, b in enumerate(beats):
        x = pad + i * step
        d = deviations[i]
        bar_h = abs(d) * scale
        y = baseline - bar_h if d >= 0 else baseline
        if b["is_win"]:
            color = "#c98a1a"
        elif b["is_top10"]:
            color = "#0f5c46"
        else:
            color = "#c3cec7"
        # MISSION V60 (2026-09-28): this chart already had no on-chart
        # numeric labels (bar height alone carries the comparison) --
        # only a real hover detail was missing, added here.
        title = f'{b["tournament"]} ({b["season"]}) · {"+" if d >= 0 else ""}{d:.2f}'
        bars.append(f'<rect x="{x - 1.6:.1f}" y="{y:.1f}" width="3.2" height="{max(bar_h, 1):.1f}" fill="{color}"><title>{escape(title)}</title></rect>')
    baseline_line = f'<line x1="{pad}" y1="{baseline:.1f}" x2="{width - pad}" y2="{baseline:.1f}" stroke="#8a988f" stroke-width="1" stroke-dasharray="2 2"/>'
    return f'{baseline_line}{"".join(bars)}'


def _career_heartbeat_html(hb: Optional[dict]) -> str:
    """V7 mission built this as a Dual Track (SG deviation + career-
    percentile deviation, stacked). V5 mission ('every chart must
    answer exactly ONE question') drops Track 2 -- the percentile
    track told the same story in a harder-to-read second unit -- and
    keeps only Track 1, the one real question this chart answers: how
    did each tournament compare to her career average, over time?
    career_percentile stays in the JSON (unchanged), it is simply not
    plotted a second time here."""
    if not hb or not hb.get("beats"):
        return ""
    beats = hb["beats"]
    width = 900
    track_h = 110
    track1 = _heartbeat_track_svg(beats, "delta_vs_career_average", 0.0, width=width, height=track_h)
    combined = (
        f'<svg viewBox="0 0 {width} {track_h}" width="{width}" height="{track_h}" class="ph-spark" role="img" aria-label="커리어 하트비트 (대회별 커리어 평균 대비 편차)">'
        f'{track1}'
        '</svg>'
    )
    return (
        '<div class="ph-evo-block" id="ph-career-heartbeat">'
        f'<p class="piq-step-label piq-label-standalone">커리어 하트비트 (실측 {len(beats)}개 대회, 시간순)</p>'
        f'{combined}'
        '<div class="piq-audit">'
        + _chip("🟡 우승", positive=True) + _chip("🟢 상위10위") + _chip("회색 = 그 외")
        + '</div>'
        f'<p class="piq-current-detail">기준선(점선)은 커리어 평균 SG {_fmt(hb["career_average_sg_total"])}입니다. '
        '막대는 절대 값이 아니라 이 기준선 대비 편차이며, 위로 갈수록 기준보다 좋았던 대회입니다.</p>'
        '</div>'
    )


_WINDOW_SKILL_LABEL = {"ott": "SG OTT", "app": "SG APP", "arg": "SG ARG", "putt": "SG PUTT"}


def _window_decomposition_html(label: str, w: dict) -> str:
    """V5 mission: 'Replace repeated numbers with visual comparison...
    every sentence must answer one question... delete everything
    else.' The old 4-column OTT/APP/ARG/PUTT table (plus a separate
    coverage-note paragraph and an almost-always-empty birdie/bogey
    table) is replaced by one real sentence naming which component was
    strongest and weakest in this window -- the same real decomposition
    values (_window_metric_decomposition, unchanged), just not restated
    as a second table after Career Form Story's cards already showed
    this exact shape of comparison."""
    d = w.get("decomposition")
    if not d:
        return ""
    vals = {k: d.get(k) for k in ("ott", "app", "arg", "putt") if d.get(k) is not None}
    if not vals:
        return ""
    best_key = max(vals, key=vals.get)
    worst_key = min(vals, key=vals.get)
    sample = f'{d["sg_component_sample_size"]}/{d["sg_component_window_size"]}개 대회'
    # NEO V3 BRAND CONSISTENCY mission (2026-09-29): "가장 강했고/약했습니다"
    # verb phrasing removed -- same real best/worst component values,
    # rendered as a bare label: value line (Best/Worst/Sample), no verb.
    if best_key == worst_key:
        line = f'{label}: {_WINDOW_SKILL_LABEL[best_key]} {vals[best_key]:+.2f} · Sample {sample}'
    else:
        line = (
            f'{label}: {_WINDOW_SKILL_LABEL[best_key]} {vals[best_key]:+.2f} (Best) · '
            f'{_WINDOW_SKILL_LABEL[worst_key]} {vals[worst_key]:+.2f} (Worst) · Sample {sample}'
        )
    return f'<p class="piq-current-detail">{escape(line)}</p>'


# ---------------------------------------------------------------------------
# PAGE 4 -- TOURNAMENT HISTORY
# ---------------------------------------------------------------------------

def _tournament_highlight_cards(rows: list) -> str:
    """Static highlight cards standing in for a hover tooltip -- this
    site renders no client-side script, so a card list next to the
    chart is the closest zero-JS equivalent to 'hover a point, see the
    detail'. Only ever built from real rows already in the document."""
    wins = [r for r in rows if r["is_win"]]
    sg_rows = [r for r in rows if r.get("sg_total") is not None]
    cards = []
    latest_win = None
    if wins:
        latest_win = wins[-1]
        cards.append(("🏆 최근 우승", latest_win))
    if sg_rows:
        best = max(sg_rows, key=lambda r: r["sg_total"])
        cards.append(("최고 SG Total", best))
        latest = sg_rows[-1]
        # MISSION V7 (2026-09-25): when her most recent tournament is
        # also her most recent win, "최근 우승" and "최근 대회" were the
        # exact same card twice in a row -- a reader who just read the
        # win card would hit an identical block immediately after. Only
        # add "최근 대회" when it tells her something the cards above it
        # do not already say.
        if latest is not best and latest is not latest_win:
            cards.append(("최근 대회", latest))
    parts = []
    for label, r in cards:
        comp = r.get("sg_components")
        comp_text = (
            f'OTT {_fmt(comp["ott"])} · APP {_fmt(comp["app"])} · ARG {_fmt(comp["arg"])} · PUTT {_fmt(comp["putt"])}'
            if comp else "SG 세부 항목 없음"
        )
        parts.append(
            '<div class="piq-brief"><p><strong>{label}</strong> {t} ({s}) — 최종 {rk}위, SG Total {sg}<br>'
            '<span class="piq-current-detail">{ct}</span></p></div>'.format(
                label=escape(label), t=_tournament_link(r["tournament"], r.get("game_code")), s=r["season"],
                rk=(r["rank"] if r["rank"] is not None else _NO_DATA), sg=_fmt(r.get("sg_total")), ct=escape(comp_text),
            )
        )
    return "".join(parts)


def _tournament_trend_html(rows: list) -> str:
    """Primary view for tournament-level performance (RED TEAM mission
    H): a chronological chart with win/top10/normal markers, plus a
    handful of highlight cards -- the full 96-row table is secondary
    and lives in its own collapsed section (see _tournament_table_html)."""
    trend_rows = [r for r in rows if r.get("sg_total") is not None]
    trend_svg = ""
    if len(trend_rows) >= 2:
        values = [r["sg_total"] for r in trend_rows]
        markers = ["win" if r["is_win"] else ("top10" if r["is_top10"] else None) for r in trend_rows]
        seasons = [r["season"] for r in trend_rows]
        hover = [f'{r["tournament"]} ({r["season"]}) · 최종 {r["rank"]}위 · SG {_fmt(r["sg_total"])}' for r in trend_rows]
        trend_svg = (
            '<div class="ph-evo-block">'
            f'{_trend_svg_by_index(values, markers, seasons, hover)}'
            '<div class="piq-audit">'
            + _chip("🟡 우승", positive=True) + _chip("🟢 상위10위") + _chip("회색 = 그 외")
            + '</div><p class="piq-current-detail">SG 데이터가 없는 대회(예: KB금융 골든라이프 챔피언십)는 이 추세선에서 제외됩니다. 0으로 대체하지 않습니다.</p>'
            '</div>'
        )
    cards_html = _tournament_highlight_cards(rows)
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-tournament-trend" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_TOURNAMENT_TREND_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">실측 {len(rows)}개 대회, 시즌순 정렬. 🏆=우승, •=상위10위.</p>{trend_svg}{cards_html}'
        '</div></details>'
    )


def _tournament_table_html(rows: list) -> str:
    """The full detailed table -- secondary and collapsed by default
    (RED TEAM mission H); the chart in _tournament_trend_html is the
    primary view. A tournament with no measured SG (KB) shows a single
    'SG 미수집' cell spanning all 5 SG columns instead of five separate
    '—' cells, per mission I -- never a claim that the value is zero,
    and never five cells that read like the data 'mysteriously
    disappeared'.

    MISSION V40 (2026-09-28): every row carries a real id
    (t-{game_code}) -- the Tournament-layer landing spot every
    _tournament_link() call elsewhere on the page jumps to. A modern
    browser opens this <details> natively on that navigation even
    though it starts collapsed; no script needed."""
    body_rows = []
    for r in rows:
        comp = r.get("sg_components")
        if r.get("sg_total") is None:
            sg_cells = f'<td colspan="5" class="piq-sg-missing">{escape(terms.SG_MISSING_CELL_TEXT)}</td>'
        elif comp:
            sg_cells = (
                f'<td>{_fmt(r["sg_total"])}</td><td>{_fmt(comp["ott"])}</td>'
                f'<td>{_fmt(comp["app"])}</td><td>{_fmt(comp["arg"])}</td><td>{_fmt(comp["putt"])}</td>'
            )
        else:
            sg_cells = f'<td>{_fmt(r["sg_total"])}</td>' + f"<td>{_NO_DATA}</td>" * 4
        badge = " 🏆" if r["is_win"] else (" •" if r["is_top10"] else "")
        body_rows.append(
            f'<tr id="t-{escape(str(r["game_code"]))}"><td>{r["season"]}</td><td>{escape(r["tournament"])}{badge}</td><td>{r["rank"] if r["rank"] is not None else _NO_DATA}</td>'
            f'{sg_cells}</tr>'
        )
    header = "".join(f"<th>{escape(v)}</th>" for v in terms.TOURNAMENT_COLUMNS.values())
    table = f'<div class="table-scroll"><table class="data-table"><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-tournament-history">'
        f'<summary class="section-heading"><h2>{terms.PAGE4_TITLE}</h2><span class="piq-current-detail">{escape(terms.PAGE_TOURNAMENT_TABLE_EXPAND_LABEL)}</span></summary>'
        f'<div class="pi-section__body">{table}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 5 -- ROUND HISTORY
# ---------------------------------------------------------------------------

def _round_card(label: str, r: Optional[dict], positive: bool = False) -> str:
    """MISSION V40 (2026-09-28): tournament name links to its real row
    (_tournament_link) when a game_code is present."""
    if not r:
        return ""
    season_suffix = f' ({r["season"]})' if "season" in r else ""
    detail = f'{_tournament_link(r["tournament"], r.get("game_code"))}{season_suffix} '
    sign_value = None
    if "round" in r:
        detail += f'R{r["round"]} SG Total {_fmt(r["sg_total"])}'
        sign_value = r["sg_total"]
    elif "delta" in r:
        detail += f'R{r["from_round"]}→R{r["to_round"]} {r["delta"]:+.2f}'
        sign_value = r["delta"]
    elif "stddev" in r:
        detail += f'표준편차 {r["stddev"]:.2f} ({r["rounds"]}라운드)'
    css_class = "piq-brief"
    if sign_value is not None:
        css_class += " piq-brief--negative" if sign_value < 0 else " piq-brief--positive"
    elif positive:
        css_class += " piq-brief--positive"
    return f'<div class="{css_class}"><p><strong>{escape(label)}</strong> {detail}</p></div>'


def _round_key(r: Optional[dict]) -> Optional[tuple]:
    if not r or "game_code" not in r or "from_round" not in r:
        return None
    return (r["game_code"], r["from_round"], r["to_round"])


def _round_history_html(rh: dict) -> str:
    """MISSION NEO PLAYER PROFILE V2 (2026-09-27): '언제 잘 치는가?
    ...최고 라운드/최악 라운드/최대 향상 같은 데이터베이스식 나열은
    지양.' Front9/Back9 or leading/chasing splits are not already
    computed anywhere in this document (hole_history covers exactly
    one tournament, not a career-wide split) -- inventing them would
    be new data this mission explicitly forbids. The honest fix within
    'only already-computed data' is density, not invention: her single
    best and single worst real round are the two facts that actually
    answer 'when does she play well', shown as one paired conclusion
    instead of a five-row enumeration. The other three already-real
    extremes (most_stable_tournament/most_improved_round/
    largest_recovery/largest_collapse) are not deleted -- they move to
    #8 Raw Data via _round_history_detail_html, the same real
    computation, just no longer competing with the two headline facts
    here.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): the full-
    sentence cards ('iM금융오픈 2026 (2026) R2 SG Total +10.37') become
    two big colored numbers with the tournament demoted to a small
    caption -- via _round_big_stat, not _round_card (still used
    unchanged by _round_history_detail_html's relocated #8 facts)."""
    cards = (
        _round_big_stat("최고 라운드", rh.get("best_round"))
        + _round_big_stat("최악 라운드", rh.get("worst_round"))
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-round-history" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE5_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><p class="piq-current-detail">실측 라운드 {rh["total_rounds"]}개 기준, 그녀의 가장 좋았던 라운드와 가장 안 좋았던 라운드입니다.</p>'
        f'<div class="ph-round-pair">{cards}</div></div></details>'
    )


def _round_big_stat(label: str, r: Optional[dict]) -> str:
    """The Round Analysis headline pair -- see _round_history_html.
    Color keys strictly off the real sign of r['sg_total'], never off
    the label, matching the same rule Mission V12 established for
    every other worst/slump chip on this page.

    MISSION V40 (2026-09-28): the tournament name is a real drill-down
    link to that tournament's own row (_tournament_link) -- Round is
    one layer below Tournament in the explorer's Career -> Season ->
    Tournament -> Round -> Hole chain."""
    if not r:
        return ""
    season_suffix = f' ({r["season"]})' if "season" in r else ""
    sign_class = "ph-round-big--negative" if r["sg_total"] < 0 else "ph-round-big--positive"
    return (
        f'<div class="ph-round-big {sign_class}">'
        f'<div class="ph-round-big-lbl">{escape(label)}</div>'
        f'<div class="ph-round-big-num">{_fmt(r["sg_total"])}</div>'
        f'<div class="ph-round-big-cap">{_tournament_link(r["tournament"], r.get("game_code"))}{season_suffix} · R{r["round"]}</div>'
        '</div>'
    )


def _round_history_detail_html(rh: Optional[dict]) -> str:
    """The three already-computed round_history extremes that MISSION
    NEO PLAYER PROFILE V2 asks not to show as a flat enumeration next
    to the headline best/worst pair (see _round_history_html) --
    relocated here, unchanged, as #8 Raw Data supporting detail."""
    if not rh:
        return ""
    most_improved = rh.get("most_improved_round")
    largest_recovery = rh.get("largest_recovery")
    same_round = _round_key(most_improved) is not None and _round_key(most_improved) == _round_key(largest_recovery)
    if same_round:
        improvement_recovery_cards = _round_card("최다 향상 라운드 (붕괴 이후 최대 회복이기도 함)", most_improved, positive=True)
    else:
        improvement_recovery_cards = (
            _round_card("최다 향상 라운드", most_improved, positive=True)
            + _round_card("최대 회복", largest_recovery, positive=True)
        )
    cards = (
        _round_card("가장 안정적인 대회", rh.get("most_stable_tournament"), positive=True)
        + improvement_recovery_cards
        + _round_card("최대 붕괴", rh.get("largest_collapse"))
    )
    if not cards:
        return ""
    return (
        '<div class="ph-evo-block" id="ph-round-history-detail">'
        f'<p class="piq-step-label piq-label-standalone">{terms.PAGE_ROUND_HISTORY_DETAIL_TITLE}</p>'
        f'{cards}</div>'
    )


# ---------------------------------------------------------------------------
# PAGE 7 -- CAREER DNA
# ---------------------------------------------------------------------------

def _dna_growth_velocity_html(growth: Optional[dict]) -> str:
    """V6 mission: 'Compute Growth Velocity for every DNA axis.' One
    static table, season-independent (applies regardless of which tab
    is selected) -- never a new section, just additional content
    inside the existing Player DNA panel."""
    if not growth:
        return ""
    rows = []
    for axis_en, label_ko in terms.RADAR_AXIS_LABEL_KO.items():
        g = growth.get(axis_en)
        if not g:
            continue
        vel = f'{g["growth_velocity_per_season"]:+.2f}/시즌' if g["growth_velocity_per_season"] is not None else _NO_DATA
        accel = f'{g["growth_acceleration_per_season"]:+.2f}' if g.get("growth_acceleration_per_season") is not None else _NO_DATA
        stability = _fmt(g.get("stability_stddev"), plus=False) if g.get("stability_stddev") is not None else _NO_DATA
        mean = _fmt(g["career_mean_percentile"], plus=False) if g["career_mean_percentile"] is not None else _NO_DATA
        rows.append(
            f'<tr><td>{escape(label_ko)}</td><td>{mean}</td><td>{vel}</td><td>{accel}</td>'
            f'<td>{stability}</td><td>{g["sample_size"]}개 시즌</td></tr>'
        )
    if not rows:
        return ""
    return (
        '<div class="ph-evo-block" id="ph-dna-growth-velocity">'
        '<p class="piq-step-label piq-label-standalone">DNA 성장 속도 · 가속도 · 안정성 (커리어 전체 기준)</p>'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        '<th>영역</th><th>커리어 평균 백분위</th><th>성장 속도</th><th>성장 가속도</th><th>안정성(표준편차)</th><th>표본</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="piq-current-detail">성장 속도는 실측된 연속 시즌 간 백분위 변화의 평균, 가속도는 그 속도 변화의 평균입니다 '
        '(시즌이 비어 있으면 그 구간은 계산에서 제외됩니다). 안정성은 시즌별 백분위의 표준편차로, 낮을수록 안정적입니다.</p>'
        '</div>'
    )


def _player_dna_radar_html(seasons_data: list, career_dna: Optional[dict] = None) -> str:
    """Single radar chart driven by a pure-CSS season selector (this
    site renders no client-side script anywhere, so the tabs are plain
    radio inputs + `:checked` sibling selectors -- no JS is added).
    Every value is a percentile within that season's real player
    population, never a raw SG unit plotted directly, per the
    mission's explicit normalization requirement. An optional
    'A vs B' comparison overlay is offered only when both seasons have
    every axis available.

    MISSION V41 (2026-09-28): the two real facts that used to be their
    own standalone section (#ph-career-dna, 'DNA 요약') move here as a
    one-line caption instead -- they describe this exact chart, so a
    reader never had a reason to find them anywhere else on the page.
    No new section for two sentences."""
    if not seasons_data:
        return ""
    dna_items = [
        ("가장 빠르게 성장한 요소", (career_dna or {}).get("fastest_growing_component")),
        ("가장 변동성 큰 요소", (career_dna or {}).get("most_volatile_component")),
    ]
    dna_caption = " · ".join(f'{k}: {escape(str(v))}' for k, v in dna_items if v)
    dna_caption_html = f'<p class="piq-current-detail">{dna_caption}</p>' if dna_caption else ""
    tab_inputs = []
    tab_labels = []
    panels = []
    # MISSION V7 (2026-09-25): the tab that opens by default was the
    # OLDEST season (i == 0) -- on a page whose own thesis is "current
    # form comes first, history exists only to explain the current
    # player," landing on a stale, years-old DNA profile by default was
    # exactly backwards. Default to her most recent season instead.
    default_index = len(seasons_data) - 1
    for i, sd in enumerate(seasons_data):
        tab_id = f"ph-dna-tab-{i}"
        checked = " checked" if i == default_index else ""
        tab_inputs.append(f'<input type="radio" name="ph-dna-tab" id="{tab_id}" class="ph-dna-radio"{checked}>')
        tab_labels.append(f'<label for="{tab_id}" class="ph-dna-tab-label">{sd["season"]}</label>')
        svg = _radar_svg(sd["axes"])
        unavailable = [terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"]) for a in sd["axes"] if a.get("percentile") is None]
        unavailable_note = (
            f'<p class="piq-current-detail">이번 시즌은 아직 확인되지 않았습니다: {escape(", ".join(unavailable))}</p>' if unavailable else ""
        )
        sample = next((a["population"] for a in sd["axes"] if a.get("population")), None)
        # MISSION V31 (2026-09-28) dropped 백분위 here because it
        # repeated the radar SVG's own on-chart axis label. MISSION V60
        # (2026-09-28) moved that number off the chart entirely (into a
        # hover tooltip, per "values appear only in tooltips or summary
        # cards") and briefly restored it as a table column. MISSION V70
        # (2026-09-28), "DNA radar must stand alone without supporting
        # tables... replace paragraphs with visual KPI cards": the same
        # two real numbers per axis (percentile, delta vs career mean)
        # survive here as a compact KPI-card grid instead of a table --
        # no data lost, no table beneath the chart.
        delta_cards = "".join(
            f'<div class="kpi-block"><p class="kpi-label">{escape(terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"]))}</p>'
            f'<p class="kpi-value">{a["percentile"]:.0f}</p>'
            f'<p class="piq-current-detail">커리어 평균 대비 {a["delta_vs_career_mean"]:+.1f}</p></div>'
            for a in sd["axes"] if a.get("delta_vs_career_mean") is not None and a.get("percentile") is not None
        )
        delta_table = f'<div class="pi-kpi-grid">{delta_cards}</div>' if delta_cards else ""
        panels.append(
            f'<div class="ph-dna-panel" id="ph-dna-panel-{sd["season"]}">'
            f'<p class="piq-step-label piq-label-standalone">{sd["season"]}시즌 (같은 시즌 KLPGA 선수 {sample}명과 비교)</p>'
            f'{svg}{unavailable_note}{delta_table}'
            '</div>'
        )

    full_seasons = [sd for sd in seasons_data if all(a.get("percentile") is not None for a in sd["axes"])]
    if len(full_seasons) >= 2:
        first, last = full_seasons[0], full_seasons[-1]
        cmp_id = f"ph-dna-tab-{len(seasons_data)}"
        tab_inputs.append(f'<input type="radio" name="ph-dna-tab" id="{cmp_id}" class="ph-dna-radio">')
        tab_labels.append(f'<label for="{cmp_id}" class="ph-dna-tab-label">{first["season"]} vs {last["season"]}</label>')
        overlay_svg = _radar_svg_overlay(first["axes"], last["axes"], f'{first["season"]}시즌', f'{last["season"]}시즌')
        panels.append(
            '<div class="ph-dna-panel" id="ph-dna-panel-compare">'
            f'<p class="piq-step-label piq-label-standalone">{first["season"]}시즌 vs {last["season"]}시즌 비교</p>'
            f'{overlay_svg}'
            '<div class="piq-audit">'
            + _chip(f'초록 = {first["season"]}시즌', positive=True) + _chip(f'주황 = {last["season"]}시즌')
            + '</div></div>'
        )

    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-player-dna-radar" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_PLAYER_DNA_RADAR_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(terms.PLAYER_DNA_EXPLANATION)}</p>'
        f'{dna_caption_html}'
        '<div class="ph-dna-tabs">'
        f'{"".join(tab_inputs)}'
        f'<div class="ph-dna-tab-bar">{"".join(tab_labels)}</div>'
        f'<div class="ph-dna-panels">{"".join(panels)}</div>'
        '</div>'
        '</div></details>'
    )


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 -- SECTION 1: CURRENT FORM
# ---------------------------------------------------------------------------

_FORM_INDICATOR_LABEL = {"UP": "상승세", "DOWN": "하락세", "FLAT": "보합세"}


def _story_layer_html(doc: dict) -> str:
    """MISSION V71/V72 built this as a narrative "magazine cover" layer
    (plain-language conclusion headlines). MISSION V96 (2026-09-29):
    "Switch from storytelling to analytics... every card starts with a
    measurable statistic... no emotional or narrative language...
    Headline = metric, Subtitle = comparison, Footer = evidence." Same
    five real, already-computed values as before (career-vs-current SG,
    the component driving the current delta, the largest real season
    jump, the strongest individual skill, the strongest venue) -- only
    the presentation changed, from a conclusion sentence to a metric
    with its comparison and evidence. No new computation; every number
    below is a field this function already read before this mission."""
    cards = []

    cvc = doc.get("current_vs_career")
    if cvc:
        snap = doc.get("current_snapshot")
        footer = f'Tour Rank {snap["official_sg_rank"]}' if snap and snap.get("official_sg_rank") is not None else None
        cards.append((
            "SEASON SG", _fmt(cvc["current_season_sg_total"]),
            f'vs Career {cvc["delta_vs_career_average"]:+.2f}', footer, "#ph-current-form",
        ))

    why_now = doc.get("why_now")
    if why_now and why_now.get("lead_component"):
        lead = why_now["lead_component"].removeprefix("SG ")
        lead_delta = why_now.get("lead_delta", 0)
        top_arrows = sorted(why_now.get("arrows", []), key=lambda a: abs(a["delta"]), reverse=True)[:3]
        subtitle = " · ".join(f'{a["component"].removeprefix("SG ")} {a["delta"]:+.2f}' for a in top_arrows)
        cards.append((
            "SG BREAKDOWN", f'{lead} {lead_delta:+.2f}',
            subtitle, "vs Career Average", "#ph-why-now",
        ))

    story = doc.get("career_story")
    if story:
        breakthrough = next(
            (m for c in story.get("chapters", []) if c["chapter"] == "경기력 도약" for m in c["milestones"]), None
        )
        if breakthrough:
            # breakthrough["detail"] is real, already-formatted text:
            # "{from_season}→{to_season} {delta:+.2f}" -- parsed back
            # out here (never re-derived from breakthrough["season"]
            # alone, which is only to_season and cannot recover
            # from_season if a season was skipped).
            season_pair, delta = breakthrough["detail"].split()
            from_season, to_season = season_pair.split("→")
            cards.append((
                "SEASON GROWTH", delta,
                f'{from_season} → {to_season}', "SG Total Δ, Season-over-Season", "#ph-career-story",
            ))

    radar_seasons = doc.get("player_dna_radar") or []
    if radar_seasons:
        latest = radar_seasons[-1]
        # excludes the aggregate axis ("SCORING"/종합 경기력) so the
        # answer is a real individual skill, not the tautological sum
        # of the others -- same exclusion this doc's career_dna
        # fastest/most-volatile fields already use.
        best_axis = max(
            (a for a in latest["axes"] if a.get("percentile") is not None and a["axis"] != "SCORING"),
            key=lambda a: a["percentile"], default=None,
        )
        if best_axis:
            axis_ko = terms.RADAR_AXIS_LABEL_KO.get(best_axis["axis"], best_axis["axis"])
            cards.append((
                "BEST SKILL", f'P{best_axis["percentile"]:.0f}',
                axis_ko, f'{latest["season"]} Season Percentile', "#ph-player-dna-radar",
            ))

    profiles = doc.get("course_profile")
    if profiles:
        strongest = profiles[0]
        appearances = strongest.get("appearances")
        footer = f'Avg SG, {appearances} Appearances' if appearances else "Avg SG"
        cards.append((
            "BEST EVENT", _fmt(strongest["avg_sg_total"]),
            strongest["tournament_family"], footer, "#ph-course-profile",
        ))

    if not cards:
        return ""

    card_html = "".join(
        f'<a class="ph-story-card" href="{href}"><p class="ph-story-label">{escape(label)}</p>'
        f'<p class="ph-story-headline">{escape(headline)}</p>'
        f'<p class="ph-story-subtitle">{escape(subtitle)}</p>'
        + (f'<p class="ph-story-footer">{escape(footer)}</p>' if footer else "")
        + '</a>'
        for label, headline, subtitle, footer, href in cards
    )
    player_name = doc.get("player_name") or doc.get("player_id") or ""
    return (
        f'<section class="ph-story-layer" id="ph-story-layer" aria-label="{escape(str(player_name))} 시즌 분석 요약">'
        f'<div class="ph-story-grid">{card_html}</div>'
        '</section>'
        '<p class="ph-layer2-marker">분석 근거</p>'
    )


def _current_form_hero_html(cvc: Optional[dict], current_snapshot: Optional[dict], indicator: Optional[dict]) -> str:
    """NEO PLAYER BIOGRAPHY V4: 'The first screen must be understandable
    in under 5 seconds... Do NOT overload the hero. Do NOT show
    implementation.' Exactly the six facts the mission names -- Current
    SG, Career SG, Difference, Recent trend, Current ranking, Current
    form indicator. Everything else (skill breakdown, official season
    snapshot) is pushed to subordinate blocks, never into this hero.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): '읽게 하지
    말고 보이게 만들어라... 사용자는 읽는 것이 아니라 훑는다.' The four
    chips + trend caption this used to show are replaced by one big
    number (unchanged), two bare supporting numbers, and a single
    colored trend arrow -- the same six real facts the V4 mission
    named, just as few characters as possible per fact."""
    if not cvc:
        return ""
    season = cvc["current_season"]
    delta = cvc["delta_vs_career_average"]
    headline_class = "ph-hero-stat ph-hero-stat--positive" if delta >= 0 else "ph-hero-stat"
    headline = (
        '<div class="ph-hero-stat-block">'
        '<p class="ph-hero-stat-label">커리어 평균 대비</p>'
        f'<p class="{headline_class}">{delta:+.2f}</p>'
        '</div>'
    )
    stats = [
        f'<div class="ph-scan-stat"><span class="ph-scan-stat-num">{_fmt(cvc["current_season_sg_total"])}</span>'
        f'<span class="ph-scan-stat-lbl">{season}시즌 SG</span></div>'
    ]
    if current_snapshot and current_snapshot.get("official_sg_rank") is not None:
        stats.append(
            f'<div class="ph-scan-stat"><span class="ph-scan-stat-num">{current_snapshot["official_sg_rank"]}위</span>'
            '<span class="ph-scan-stat-lbl">공식 SG 랭크</span></div>'
        )
    trend_html = ""
    if indicator:
        trend = indicator["trend"]
        trend_class = " ph-scan-trend--up" if trend == "UP" else (" ph-scan-trend--down" if trend == "DOWN" else "")
        trend_html = (
            f'<div class="ph-scan-trend{trend_class}"><span class="ph-scan-trend-arrow">{_ARROW.get(trend, "")}</span>'
            f'{escape(_FORM_INDICATOR_LABEL.get(trend, trend))}</div>'
        )
    return (
        '<details class="evidence-detail pi-section" id="ph-current-form" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_CURRENT_FORM_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'{headline}'
        f'<div class="ph-scan-stats">{"".join(stats)}{trend_html}</div>'
        '</div></details>'
    )


def _official_snapshot_html(snapshot: Optional[dict]) -> str:
    """Subordinate to #1 (Current Form). V5 mission: 'increase
    information density... delete everything else.' The SG-rank/SG-
    component chips this used to lead with duplicated the Current Form
    hero (rank, SG Total) and Why Now (the full component table) word
    for word -- deleted here, kept only where they already live. What
    remains is the genuinely new information this snapshot alone has
    (money, scoring average, putts, birdie/GIR/par-save/par-break/
    recovery rates), collapsed by default since a reader who already
    got 현재 폼 + 왜 지금인가 does not need it for a 30-second read."""
    if not snapshot:
        return ""
    money = snapshot.get("money")
    money_chip = _chip(f'상금 {money:,}원') if money is not None else ""
    avg_score = snapshot.get("average_score")
    avg_score_chip = _chip(f'평균 타수 {_fmt(avg_score, plus=False)}') if avg_score is not None else ""
    avg_putts = snapshot.get("average_putts")
    avg_putts_chip = _chip(f'평균 퍼트 {_fmt(avg_putts, plus=False)}') if avg_putts is not None else ""
    birdie = snapshot.get("birdie_rate")
    birdie_chip = _chip(f'버디율 {_fmt(birdie, plus=False)}%') if birdie is not None else ""
    gir = snapshot.get("gir_rate")
    gir_chip = _chip(f'GIR {_fmt(gir, plus=False)}%') if gir is not None else ""
    par_save = snapshot.get("par_save_rate")
    par_save_chip = _chip(f'파세이브 {_fmt(par_save, plus=False)}%') if par_save is not None else ""
    par_break = snapshot.get("par_break_rate")
    par_break_chip = _chip(f'파브레이크 {_fmt(par_break, plus=False)}%') if par_break is not None else ""
    recovery = snapshot.get("recovery_rate")
    recovery_chip = _chip(f'리커버리 {_fmt(recovery, plus=False)}%') if recovery is not None else ""
    return (
        '<details class="evidence-detail pi-section" id="ph-snapshot">'
        f'<summary class="section-heading"><h2>{terms.PAGE_SNAPSHOT_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(snapshot["as_of_note"])}</p>'
        '<div class="piq-audit">'
        + money_chip + avg_score_chip + avg_putts_chip + birdie_chip + gir_chip + par_save_chip + par_break_chip + recovery_chip
        + "</div></div></details>"
    )


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 -- SECTION 2: WHY NOW
# ---------------------------------------------------------------------------

_ARROW = {"UP": "▲", "DOWN": "▼", "FLAT": "—"}


def _skill_chain_html(why_now: Optional[dict], current_snapshot: Optional[dict], current_vs_career: Optional[dict], career_current: Optional[dict]) -> str:
    """MISSION V31 (2026-09-28): 'Build a Skill Chain. Skill -> Scoring
    Opportunity -> Scoring -> Result -> Career. Use only verified
    repository data.' Five real, already-computed facts chained in one
    row -- never a new calculation, never a claim of causation beyond
    what the real sequence already shows: which skill led this season
    (why_now.lead_component), the real scoring chances it produced
    (current_snapshot.gir_rate), the real stroke outcome
    (average_score), the real tournament result (wins/top10 this
    season), and where that leaves her against her own career
    (delta_vs_career_average). Renders nothing when any required real
    field is missing -- never a chain with an invented link."""
    if not (why_now and current_snapshot and current_vs_career and career_current):
        return ""
    stages = [
        ("스킬", f'{why_now["lead_component"].removeprefix("SG ")} {why_now["lead_delta"]:+.2f}'),
        ("스코어링 기회", f'GIR {current_snapshot["gir_rate"]:.1f}%'),
        ("스코어링", f'평균 {current_snapshot["average_score"]:.2f}타'),
        ("결과", f'{career_current["wins"]}승 · Top10 {career_current["top10"]}회'),
        ("커리어", f'{current_vs_career["delta_vs_career_average"]:+.2f}'),
    ]
    cards = []
    for i, (label, num) in enumerate(stages):
        if i > 0:
            cards.append('<span class="ph-chain-arrow">→</span>')
        cards.append(
            '<div class="ph-chain-stage">'
            f'<div class="ph-chain-stage-lbl">{escape(label)}</div>'
            f'<div class="ph-chain-stage-num">{escape(num)}</div>'
            '</div>'
        )
    # NEO V3 BRAND CONSISTENCY mission (2026-09-29): a causal "X 상승이
    # ...으로 이어졌습니다" sentence used to follow here, restating the
    # exact same five values as the card row above with a causation
    # claim added on top. Removed -- the card row already is the
    # Metric -> Comparison -> Evidence sequence this mission requires;
    # a sentence saying it again, plus a claim of causation neither
    # this function nor its inputs actually establish, added nothing.
    return f'<div class="ph-skill-chain">{"".join(cards)}</div>'


def _why_now_html(
    why_now: Optional[dict], current_snapshot: Optional[dict] = None,
    current_vs_career: Optional[dict] = None, career_current: Optional[dict] = None,
) -> str:
    """'Do NOT explain every metric. Answer only: why is she playing
    well now? Lead with change... One sentence only.' The sentence
    leads; arrows follow -- exactly the 'APP ▲ OTT ▲ PUTT ▼' format the
    mission asked for verbatim.

    V6 mission (2026-09-25): 'spend the entire mission deleting... if
    removing this does not make the user understand her less, delete
    it.' V5's dot-plot chart said the same four numbers the arrows
    already say, just slower to read -- removed.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): the text+number
    chips ('APP ▲ +0.57') become a 4-card icon grid -- one big colored
    arrow per component, the real delta demoted to a small number
    beneath it.

    MISSION V31 (2026-09-28): 'Organize the page by QUESTIONS... Build
    a Skill Chain.' This section already answers 'which skill changed';
    the chain below extends the same real answer one real step further
    -- into the scoring chances, the score, and the result it produced
    -- so the section fully answers 'why is she playing well now', not
    only 'which skill'."""
    if not why_now:
        return ""
    # MISSION V41 (2026-09-28): '현재 약점은 무엇인가?' was answerable
    # nowhere on the first screen -- every real arrow here was already
    # rendered, just never ranked. The smallest real delta among these
    # same four numbers (no new field, no new computation beyond min())
    # is her weakest current momentum, labeled directly on its own
    # already-existing card.
    weakest_component = min(why_now["arrows"], key=lambda a: a["delta"])["component"] if why_now["arrows"] else None
    arrow_cards = "".join(
        '<div class="ph-arrow-card{down}">'
        '<span class="ph-arrow-big">{arrow}</span>'
        '<div class="ph-arrow-lbl">{label}{weakest_tag}</div>'
        '<div class="ph-arrow-num">{delta:+.2f}</div>'
        '</div>'.format(
            down=" ph-arrow-card--down" if a["direction"] == "DOWN" else "",
            arrow=_ARROW.get(a["direction"], ""),
            label=escape(a["component"].removeprefix("SG ")),
            weakest_tag='<span class="ph-arrow-weakest-tag">Min Δ</span>' if a["component"] == weakest_component else "",
            delta=a["delta"],
        )
        for a in why_now["arrows"]
    )
    skill_chain_html = _skill_chain_html(why_now, current_snapshot, current_vs_career, career_current)
    # MISSION V72 (2026-09-28): "Remove duplicated narrative. If the
    # Story layer already tells the conclusion, the detailed section
    # below becomes evidence only." The Story layer's own card already
    # states this same real conclusion (which component is driving the
    # trend) -- this section keeps only the evidence for it (the arrow
    # grid, the skill chain), not a second copy of the sentence.
    return (
        '<details class="evidence-detail pi-section" id="ph-why-now" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_WHY_NOW_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<div class="ph-arrow-grid">{arrow_cards}</div>'
        f'{skill_chain_html}'
        '</div></details>'
    )


def _recent_form_html(rows_5: list, rows_10: list, rows_20: Optional[list] = None) -> str:
    """NEO PLAYER BIOGRAPHY V4 section 3: 'Last 5. Last 10. Last 20.
    Nothing else.' Distinct from career/season aggregates by design --
    only the last N COMPLETED tournaments, chronological, never mixing
    in the in-progress tournament. made_cut is never shown (see
    NOT_AVAILABLE: unreliable historically).

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): the 5-row
    table plus its nested 6th-20th-row toggle become one scannable
    "form strip" -- one dot per tournament, oldest to newest, colored
    by real is_win/is_top10. Every real row this used to print in a
    table still exists on the page, unabridged, in the full tournament
    table (#7, _tournament_table_html) -- this section only changes
    HOW the same last-20 rows are shown, never adds a count or rate
    that is not already a per-row field."""
    rows = rows_20 or rows_10 or rows_5
    if not rows:
        return ""
    dots = "".join(
        f'<span class="ph-form-dot{" ph-form-dot--win" if r["is_win"] else (" ph-form-dot--top10" if r["is_top10"] else "")}"'
        f' title="{escape(r["tournament"])} ({r["season"]})">{"🏆" if r["is_win"] else ""}</span>'
        for r in rows
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-recent-form" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_RECENT_RESULTS_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        '<p class="piq-current-detail">완료된 대회만 포함합니다. 진행 중인 대회는 이 최근 폼에 포함되지 않고 '
        '별도 섹션에서 표시됩니다.</p>'
        f'<div class="ph-form-strip">{dots}</div>'
        f'<div class="ph-form-strip-axis"><span>{len(rows)}경기 전</span><span>최근</span></div>'
        '<div class="piq-audit">'
        + _chip("🏆 우승", positive=True) + _chip("상위10위") + _chip("회색 = 그 외")
        + '</div>'
        '</div></details>'
    )


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 -- SECTION 4: PLAYER IDENTITY
# ---------------------------------------------------------------------------

def _player_identity_html(identity: Optional[dict]) -> str:
    """'What kind of golfer is she?' Every label maps directly to
    career_dna's already-computed real fields -- never invented.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): the one-
    sentence conclusion becomes a badge; 'winning_note' (always null
    for this player) and the consistency full sentence are dropped in
    favor of two short labels. The badge's own approval round also
    caught and removed a real duplicate ('강점: SG APP' restated what
    the badge and share-% line already say) -- every remaining line
    states a fact no other line already states."""
    if not identity:
        return ""
    parts = [
        f'<span class="ph-identity-badge">{escape(identity["primary_type"])}</span>',
        f'<div class="ph-scan-stat"><span class="ph-scan-stat-lbl">{escape(identity["primary_component"])} '
        f'{identity["primary_share_pct"]}% 비중</span></div>',
    ]
    if identity.get("consistency_component"):
        parts.append(f'<div class="ph-scan-stat"><span class="ph-scan-stat-lbl">가장 안정적인 능력: {escape(identity["consistency_component"])}</span></div>')
    return (
        '<details class="evidence-detail pi-section" id="ph-player-identity" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_PLAYER_IDENTITY_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(parts)}</div></details>'
    )


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 -- SECTION 5: CAREER STORY (told backwards)
# ---------------------------------------------------------------------------

# MISSION V77 REDESIGN (2026-09-28), replacing the earlier V77 pass:
# "Timeline = Navigation... Each milestone should contain ONLY icon /
# title / year. Nothing else... Avoid emoji. Use vector or CSS shapes
# only." One fixed (shape, color) per real chapter concept -- never
# per player -- drawn as real SVG primitives instead of an emoji glyph
# (a plain colored dot/star/triangle/diamond/ring, matching this
# page's own existing palette: gray for a neutral fact, gold for a
# win, green for everything positive -- never a new color system).
_STORY_CHAPTER_MARKER = {
    "기준점": ("circle", "#8a988f"),
    "첫 우승": ("star", "#c98a1a"),
    "경기력 도약": ("triangle", "#0f5c46"),
    "최고 경기력": ("diamond", "#0f5c46"),
    "현재 경기력": ("ring", "#0f5c46"),
}
# When a chapter groups more than one real milestone (true only for
# 최고 경기력, which holds both her first win and her career-best
# season), this says which of its own real milestone labels the
# single timeline point should take its year from -- the one that
# most literally matches the chapter's own name. Every other chapter
# has exactly one milestone, so no entry is needed for it.
_STORY_CHAPTER_REPRESENTATIVE_LABEL = {"최고 경기력": "커리어 최고 SG Total 시즌"}


def _timeline_marker_svg(shape: str, cx: float, cy: float, color: str, size: float = 6.5) -> str:
    """One real vector primitive per shape name -- no emoji, no
    external icon font, per MISSION V77 REDESIGN's 'vector or CSS
    shapes only.'"""
    if shape == "star":
        pts = []
        for i in range(10):
            ang = -_math.pi / 2 + i * _math.pi / 5
            r = size if i % 2 == 0 else size * 0.42
            pts.append(f"{cx + r * _math.cos(ang):.1f},{cy + r * _math.sin(ang):.1f}")
        return f'<polygon points="{" ".join(pts)}" fill="{color}"/>'
    if shape == "triangle":
        return (
            f'<polygon points="{cx:.1f},{cy - size:.1f} {cx + size:.1f},{cy + size * 0.8:.1f} '
            f'{cx - size:.1f},{cy + size * 0.8:.1f}" fill="{color}"/>'
        )
    if shape == "diamond":
        return (
            f'<polygon points="{cx:.1f},{cy - size:.1f} {cx + size:.1f},{cy:.1f} '
            f'{cx:.1f},{cy + size:.1f} {cx - size:.1f},{cy:.1f}" fill="{color}"/>'
        )
    if shape == "ring":
        return (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size * 0.38:.1f}" fill="{color}"/>'
        )
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="{color}"/>'


def _story_timeline_points(chapters: list, current: Optional[dict]) -> list:
    """One real (chapter, season) point per chapter concept -- never
    one per individual milestone-fact. Reused by both the desktop SVG
    and the mobile vertical list so the two can never drift apart.

    `chapters` arrives in the backwards-narrative order the text cards
    below use (최고 경기력 -> ... -> 기준점) -- right for prose, wrong
    for a timeline, where 기준점(2023) mid-list between two 2025
    points would read as a mistake. Sorted chronologically (oldest
    first) here instead, matching the desktop SVG's own left-to-right
    real season axis."""
    points = []
    for c in chapters:
        ms = c["milestones"]
        wanted = _STORY_CHAPTER_REPRESENTATIVE_LABEL.get(c["chapter"])
        best = next((m for m in ms if m["label"] == wanted), None) or max(ms, key=lambda m: m["season"])
        points.append((c["chapter"], best["season"]))
    if current:
        points.append(("현재 경기력", current["season"]))
    return sorted(points, key=lambda p: p[1])


def _career_milestones_timeline_svg(chapters: list, seasons: list, current: Optional[dict] = None, width: int = 1180) -> str:
    """MISSION "PLAYER HISTORY V20 continued" (2026-09-28): 'career
    milestones' as a real visual, not a chapter-by-chapter paragraph
    list. Every real chapter placed on one real chronological career
    timeline -- when several chapters share a real season, they stack
    straight up from the spine, one level per chapter, instead of
    overlapping. Points only ever stack ABOVE the spine, never below:
    an earlier version alternated above/below and a below-spine label
    collided with the season tick labels directly underneath the axis.

    MISSION V77 REDESIGN (2026-09-28): 'Timeline = Navigation... ONLY
    icon / title / year... Move all explanations below... Timeline =
    index. Cards = detail.' Every real milestone's own detail sentence
    and numbers (already shown once, in the stage card this chart sits
    above) are gone from this chart -- each point is now only its
    chapter's real vector marker, the chapter's own name as its title,
    and the real season of its representative milestone. Desktop-only
    (see .ph-timeline-svg in neo-site.css, ~85% of the content width,
    hidden under the tablet breakpoint); _career_milestones_timeline_
    mobile_html renders the identical real points as a vertical list
    for narrower viewports."""
    points = _story_timeline_points(chapters, current)
    if not points or len(seasons) < 2:
        return ""
    by_season: dict = {}
    for chapter, season in points:
        by_season.setdefault(season, []).append(chapter)
    max_stack = max(len(items) for items in by_season.values())

    side_pad, top_pad, bottom_pad, row_h = 44, 30, 46, 52
    axis_y = top_pad + max_stack * row_h
    height = axis_y + bottom_pad

    lo, hi = min(seasons), max(seasons)
    span = (hi - lo) or 1

    def _x(season):
        return side_pad + (season - lo) / span * (width - 2 * side_pad)

    parts = [
        f'<line x1="{side_pad}" y1="{axis_y:.1f}" x2="{width - side_pad}" y2="{axis_y:.1f}" '
        'stroke="#c3cec6" stroke-width="3" stroke-linecap="round"/>'
    ]
    for s in seasons:
        x = _x(s)
        anchor = "start" if x < side_pad + 24 else ("end" if x > width - side_pad - 24 else "middle")
        parts.append(f'<line x1="{x:.1f}" y1="{axis_y - 5:.1f}" x2="{x:.1f}" y2="{axis_y + 5:.1f}" stroke="#8a988f" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{axis_y + 24:.1f}" font-size="13" fill="#8a988f" text-anchor="{anchor}">{s}</text>')

    for season, chapter_list in by_season.items():
        x = _x(season)
        anchor = "start" if x < side_pad + 110 else ("end" if x > width - side_pad - 110 else "middle")
        for depth, chapter in enumerate(chapter_list):
            icon_y = axis_y - 22 - depth * row_h
            title_y = icon_y - 16
            shape, color = _STORY_CHAPTER_MARKER.get(chapter, ("circle", "#0f5c46"))
            parts.append(_timeline_marker_svg(shape, x, icon_y, color))
            parts.append(f'<text x="{x:.1f}" y="{title_y:.1f}" font-size="17" font-weight="500" fill="#14201c" text-anchor="{anchor}">{escape(chapter)}</text>')
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark ph-timeline-svg" '
        'role="img" aria-label="커리어 마일스톤 타임라인">'
        f'{"".join(parts)}</svg>'
    )


def _career_milestones_timeline_mobile_html(chapters: list, current: Optional[dict]) -> str:
    """MISSION V77 REDESIGN (2026-09-28): 'Mobile: keep the same
    information. Convert to a vertical timeline. Never shrink fonts
    below readability.' A zero-client-side-JS static site cannot
    reflow one SVG from horizontal to vertical, so this is a second,
    CSS-only rendering of the exact same real (chapter, season) points
    _career_milestones_timeline_svg draws -- shown only below the
    tablet breakpoint (see .ph-timeline-mobile in neo-site.css), the
    SVG shown only above it. Icon shapes are pure CSS (border-radius/
    clip-path/rotate), never emoji, matching the desktop marker's own
    shape+color per chapter exactly."""
    points = _story_timeline_points(chapters, current)
    if not points:
        return ""
    rows = "".join(
        f'<div class="ph-timeline-mobile-row">'
        f'<span class="ph-timeline-mobile-icon ph-timeline-mobile-icon--{_STORY_CHAPTER_MARKER.get(chapter, ("circle", ""))[0]}"></span>'
        f'<span class="ph-timeline-mobile-title">{escape(chapter)}</span>'
        f'<span class="ph-timeline-mobile-year">{season}</span>'
        '</div>'
        for chapter, season in points
    )
    return f'<div class="ph-timeline-mobile">{rows}</div>'


def _career_story_html(story: Optional[dict], career_overview: dict) -> str:
    """'Do NOT start with 2023, 2024, 2025. Instead start with Current
    -> Winning Stage -> Breakthrough -> Development -> Adaptation. Only
    afterwards reveal seasons.' Every chapter reuses one of
    _player_story's already-computed milestones (build_10097_player_
    history.py) -- this renderer only reorders and relabels them.
    career_overview is the same real dict #1's hero and #11's audit
    section already use -- the season table tail is not a second,
    independently-built summary.

    MISSION "PLAYER HISTORY V20 continued" (2026-09-28): 'Every chart
    must replace at least 300 words... the page should tell the story
    of a golfer's career.' A real chronological timeline
    (_career_milestones_timeline_svg) now leads as the map of when
    everything happened; the chapter text stays -- backwards, on
    purpose, per the V4 mission above -- but each milestone line drops
    its own '{season}시즌 —' prefix, since the timeline already places
    it in time."""
    if not story:
        return ""
    current = story["current"]
    current_html = (
        '<div class="ph-bio-stage">'
        '<p class="piq-step-label piq-label-standalone">현재 경기력</p>'
        f'<p class="piq-current-detail">{current["season"]}시즌, SG Total {_fmt(current["sg_total"])}, '
        f'우승 {current["wins"]}회, 상위10위 {current["top10"]}회 ({current["events"]}개 대회 표본).</p>'
        '</div>'
    )
    timeline_svg = _career_milestones_timeline_svg(story["chapters"], [r["season"] for r in career_overview["season_rows"]], story["current"])
    timeline_mobile = _career_milestones_timeline_mobile_html(story["chapters"], story["current"])
    chapter_blocks = []
    for c in story["chapters"]:
        milestone_lines = "".join(
            f'<p class="piq-current-detail">{escape(m["label"])}: {escape(m["detail"])}</p>'
            for m in c["milestones"]
        )
        chapter_blocks.append(
            '<div class="ph-bio-stage">'
            f'<p class="piq-step-label piq-label-standalone">{escape(c["chapter"])}</p>'
            f'{milestone_lines}'
            '</div>'
        )
    season_table_html = (
        '<p class="piq-step-label piq-label-standalone">시즌별 기록</p>'
        f'{_season_table_html(career_overview)}'
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-career-story" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_CAREER_STORY_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'{timeline_svg}{timeline_mobile}'
        f'<div class="ph-bio-story">{current_html}{"".join(chapter_blocks)}</div>'
        f'{season_table_html}'
        '</div></details>'
    )


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 -- SECTION 9: COURSE PROFILE
# ---------------------------------------------------------------------------

def _course_strength_bars_svg(profiles: list, width: int = 620, row_h: int = 28) -> str:
    """One chart, one question: which recurring tournaments has she
    been strongest/weakest at? Replaces scanning a long numeric table
    with a single shared-scale bar comparison (V5 mission)."""
    if not profiles:
        return ""
    vals = [p["avg_sg_total"] for p in profiles]
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    span = (hi - lo) or 1.0
    label_w = 210
    plot_w = width - label_w - 60
    zero_x = label_w + (0.0 - lo) / span * plot_w
    height = row_h * len(profiles) + 10
    rows = []
    for i, p in enumerate(profiles):
        y = 8 + i * row_h
        v = p["avg_sg_total"]
        bar_x = label_w + (v - lo) / span * plot_w
        x0, x1 = (zero_x, bar_x) if v >= 0 else (bar_x, zero_x)
        color = "#0f5c46" if v >= 0 else "#9a6b3f"
        # MISSION V60 (2026-09-28): the end-of-bar number is gone --
        # the bar's own length already shows the comparison; the exact
        # real value is a hover away (<title>) and, for the full real
        # set (not just this top/bottom highlight), one click away in
        # the already-existing full table below this chart.
        rows.append(
            f'<text x="0" y="{y + row_h * 0.65:.1f}" font-size="11" fill="#3d4a43">{escape(p["tournament_family"])}</text>'
            f'<rect x="{x0:.1f}" y="{y + 4:.1f}" width="{max(x1 - x0, 1):.1f}" height="{row_h - 12:.1f}" fill="{color}">'
            f'<title>{escape(p["tournament_family"])} {v:+.2f}</title></rect>'
        )
    zero_line = f'<line x1="{zero_x:.1f}" y1="0" x2="{zero_x:.1f}" y2="{height}" stroke="#8a988f" stroke-width="1" stroke-dasharray="2 2"/>'
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="반복 대회 강세·약세 비교">'
        f'{zero_line}{"".join(rows)}</svg>'
    )


def _course_profile_html(profiles: Optional[list], tournament_history: Optional[list] = None) -> str:
    """'Strength by course. Weakness by course. Nothing speculative.'
    Real venue/course names are not reliably on file for most
    tournaments (see NOT_AVAILABLE) -- this groups by repeated real
    tournament name instead (a disclosed, real proxy for a recurring
    host course), never a guessed venue.

    V5 mission ('replace repeated numbers with visual comparison...
    delete everything else'): the full numeric table used to be the
    whole section -- now a single bar chart shows the real top-3/
    bottom-3 at a glance, and the complete list moves into a nested,
    collapsed detail for anyone who wants every row.

    MISSION V40 (2026-09-28): best/worst tournament names link to
    their real row via _tournament_link. tournament_history's own
    names are unique enough in this player's real data (repeats
    already carry a distinguishing year, e.g. 'S-OIL 챔피언십 2023' vs
    '...2024') for one global name lookup here."""
    if not profiles:
        return ""
    top = profiles[:3]
    bottom = [p for p in profiles[-3:] if p not in top]
    highlight = top + bottom
    bars = _course_strength_bars_svg(highlight)
    # MISSION V70 (2026-09-28): "No chart exists without a headline
    # insight." profiles is already sorted strongest-to-weakest by real
    # avg SG Total -- its own first/last rows answer "where is she
    # strongest/weakest" before the bar chart does, no new data.
    #
    # MISSION V72 (2026-09-28): "Remove duplicated narrative." The
    # Story layer's own card now states the strongest venue as its
    # headline conclusion -- only the weakest-venue half survives here,
    # since that fact is not said anywhere above this section.
    strongest, weakest = profiles[0], profiles[-1]
    course_headline = (
        f'<div class="piq-brief piq-brief--negative"><p><strong>{escape(weakest["tournament_family"])}</strong> '
        f'가장 약한 대회 · 평균 SG {_fmt(weakest["avg_sg_total"])}</p></div>'
    ) if strongest is not weakest else ""

    game_code_by_name = {t["tournament"]: t["game_code"] for t in (tournament_history or [])}
    rows = "".join(
        f'<tr><td>{escape(p["tournament_family"])}</td><td>{p["appearances"]}</td>'
        f'<td>{_fmt(p["avg_sg_total"])}</td>'
        f'<td>{_tournament_link(p["best_tournament"], game_code_by_name.get(p["best_tournament"]))} ({_fmt(p["best_sg_total"])})</td>'
        f'<td>{_tournament_link(p["worst_tournament"], game_code_by_name.get(p["worst_tournament"]))} ({_fmt(p["worst_sg_total"])})</td></tr>'
        for p in profiles
    )
    full_table = (
        '<details class="ph-nested-detail">'
        f'<summary>반복 대회 전체 {len(profiles)}개 보기</summary>'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        '<th>반복 대회</th><th>출전</th><th>평균 SG Total</th><th>최고 성적</th><th>최저 성적</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>'
        '</details>'
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-course-profile" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_COURSE_PROFILE_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        # MISSION V61 (2026-09-28): "데이터 커버리지" is developer
        # language -- the real reason (course names aren't well
        # recorded) reads the same to a golfer without that word.
        '<p class="piq-current-detail">대회별 코스명은 기록이 많지 않아, 같은 이름으로 반복 개최된 대회'
        '(2회 이상 출전)를 기준으로 강세·약세를 정리합니다.</p>'
        f'{course_headline}'
        f'{bars}'
        f'{full_table}'
        '</div></details>'
    )


# ---------------------------------------------------------------------------
# HOLE HISTORY + NOT AVAILABLE
# ---------------------------------------------------------------------------

def _hole_history_html(hh: Optional[dict], tournament_history: Optional[list] = None) -> str:
    """MISSION V40 (2026-09-28): links back up to its own real row in
    the full tournament table -- but ONLY when that tournament is
    actually reconciled into tournament_history yet. The one real hole
    history this player has belongs to the tournament currently in
    progress, which has no row there until it finishes; linking to a
    game_code with no anchor on the page would be a dangling link, so
    this checks first rather than assuming every hole history has a
    finished counterpart.

    MISSION V41 (2026-09-28): collapsed by default -- 51 hole-by-hole
    rows for one tournament is real depth, not first-15-second
    orientation. It stays exactly one click away, and the V40 anchor
    link (a real browser auto-opening a closed <details> on fragment
    navigation, already verified) still lands here and opens it."""
    if not hh:
        return ""
    known_game_codes = {t["game_code"] for t in (tournament_history or [])}
    round_blocks = []
    for r in hh["rounds"]:
        cells = "".join(f'<td>{h["hole"]}</td>' for h in r["holes"])
        strokes = "".join(f'<td>{h["strokes"]}</td>' for h in r["holes"])
        rel = "".join(f'<td>{h["relative_to_par"]:+d}</td>' if h["relative_to_par"] else '<td>E</td>' for h in r["holes"])
        round_blocks.append(
            f'<p class="piq-step-label piq-label-standalone">R{r["round"]} ({r["holes_recorded"]}홀 실측)</p>'
            f'<div class="table-scroll"><table class="data-table"><thead><tr><th>홀</th>{cells}</tr></thead>'
            f'<tbody><tr><th>타수</th>{strokes}</tr><tr><th>파 대비</th>{rel}</tr></tbody></table></div>'
        )
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-hole-history">'
        f'<summary class="section-heading"><h2>{terms.PAGE_HOLE_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{_tournament_link(hh["tournament"], hh.get("game_code") if hh.get("game_code") in known_game_codes else None)} ({hh["game_code"]}, {escape(hh["course"] or "")}). {escape(hh["capture_note"])}</p>'
        f'{"".join(round_blocks)}</div></details>'
    )


def _coverage_matrix_html(cm: Optional[dict]) -> str:
    if not cm:
        return ""
    seasons = cm["seasons"]
    header = "".join(f"<th>{s}</th>" for s in seasons)
    trs = "".join(
        f'<tr><td>{escape(metric)}</td>' + "".join(f'<td>{escape(terms.RADAR_STATUS_LABEL.get(row.get(str(s)) or row.get(s), row.get(str(s)) or row.get(s)))}</td>' for s in seasons) + '</tr>'
        for metric, row in cm["rows"].items()
    )
    # MISSION V11 (2026-09-25): 'never expose internal labels such as
    # MEASURED, DERIVED, IMPUTED' -- this legend's own JSON keys ARE
    # those raw internal labels (plus coverage_matrix's own BLOCKED).
    # Translated through the same terms.RADAR_STATUS_LABEL table the
    # per-cell values above already use, instead of printing the key
    # verbatim as this line used to.
    legend = "".join(f'<li><strong>{escape(terms.RADAR_STATUS_LABEL.get(k, k))}</strong> — {escape(v)}</li>' for k, v in cm["status_legend"].items())
    return (
        '<div class="ph-evo-block">'
        f'<p class="piq-step-label piq-label-standalone">{terms.PAGE_COVERAGE_MATRIX_TITLE}</p>'
        f'<p class="piq-current-detail">{escape(cm["note"])}</p>'
        f'<div class="table-scroll"><table class="data-table"><thead><tr><th>항목</th>{header}</tr></thead>'
        f'<tbody>{trs}</tbody></table></div>'
        f'<ul class="piq-checklist">{legend}</ul>'
        '</div>'
    )


def _status_semantics_html(status: Optional[dict]) -> str:
    if not status:
        return ""
    detail = status.get("data_completeness_detail", {})
    available_items = "".join(f"<li>{escape(x)}</li>" for x in detail.get("confirmed_available", []))
    unverified_items = "".join(f"<li>{escape(x)}</li>" for x in detail.get("still_locally_absent_source_not_independently_verified", []))
    return (
        '<div class="ph-evo-block">'
        '<p class="piq-step-label piq-label-standalone">데이터 상태 요약 (하나의 통합 PASS가 아닙니다)</p>'
        '<div class="piq-audit">'
        + _chip(f'출처 충돌: {status["source_conflicts"]}', positive=status["source_conflicts"] == "PASS")
        + _chip(f'데이터 완전성: {status["data_completeness"]}', positive=status["data_completeness"] == "PASS")
        + _chip(f'산출 지표: {status["derived_metrics"]}', positive=status["derived_metrics"] == "PASS")
        + '</div>'
        + (f'<p class="piq-current-detail">{escape(detail.get("note", ""))}</p>' if detail.get("note") else "")
        + (f'<p class="piq-step-label">확인됨</p><ul class="piq-checklist">{available_items}</ul>' if available_items else "")
        + (f'<p class="piq-step-label">로컬 미확인 (KLPGA 부재를 의미하지 않음)</p><ul class="piq-excluded-list">{unverified_items}</ul>' if unverified_items else "")
        + '</div>'
    )


def _data_confidence_html(
    page_confidence: Optional[dict],
    field_confidence_legend: Optional[dict],
    provenance_summary: Optional[dict],
    data_confidence_roadmap: Optional[list],
    data_quality_timeline: Optional[list],
) -> str:
    """MISSION V11 (2026-09-25): 'Translate developer provenance into
    user trust... Never expose internal labels such as MEASURED,
    DERIVED, IMPUTED. The purpose is to answer: How much should I
    trust what I am reading?' Every string below comes straight from
    the builder's already-translated copy (page_confidence/
    field_confidence_legend/provenance_summary/data_confidence_roadmap/
    data_quality_timeline) -- this function never prints a raw
    provenance label itself, only the Korean copy the builder already
    chose for it. Nested inside #11 (supporting evidence, collapsed,
    last) -- the one exception is the small trust line the hero also
    carries, since 'how much should I trust this' deserves to be
    answerable before a reader has scrolled past ten sections."""
    if not page_confidence:
        return ""
    summary_chips = "".join(
        _chip(f'{row["short"]} {row["count"]}개 ({row["pct"]}%)', positive=(row["tier"] == "high"))
        for row in (provenance_summary or {}).get("rows", [])
    )
    legend_items = "".join(
        f'<li><strong>{escape(entry["short"])}</strong> — {escape(entry["detail"])}</li>'
        for entry in (field_confidence_legend or {}).values()
    )
    roadmap_items = "".join(
        f'<li><strong>{escape(item["title"])}</strong> — {item["field_count"]}개 항목</li>'
        for item in (data_confidence_roadmap or [])
    )
    timeline_rows = "".join(
        f'<tr><td>{row["season"]}</td><td>{row["available_pct"]}%</td><td>{escape(row["summary"])}</td></tr>'
        for row in (data_quality_timeline or [])
    )
    timeline_html = (
        '<p class="piq-step-label piq-label-standalone">' + terms.PAGE_DATA_QUALITY_TIMELINE_TITLE + '</p>'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        '<th>시즌</th><th>확인 가능</th><th>요약</th>'
        f'</tr></thead><tbody>{timeline_rows}</tbody></table></div>'
    ) if timeline_rows else ""
    roadmap_html = (
        '<p class="piq-step-label piq-label-standalone">' + terms.PAGE_DATA_CONFIDENCE_ROADMAP_TITLE + '</p>'
        f'<ul class="piq-checklist">{roadmap_items}</ul>'
    ) if roadmap_items else ""
    return (
        '<div class="ph-evo-block" id="ph-data-confidence">'
        f'<p class="piq-step-label piq-label-standalone">{terms.PAGE_DATA_CONFIDENCE_TITLE}</p>'
        f'<p class="piq-conclusion">{escape(page_confidence["headline"])}</p>'
        f'<div class="piq-audit">{summary_chips}</div>'
        f'<ul class="piq-checklist">{legend_items}</ul>'
        f'{roadmap_html}'
        f'{timeline_html}'
        '</div>'
    )


def _page_confidence_chip_html(page_confidence: Optional[dict]) -> str:
    """The one small early-visibility piece of MISSION V11: a reader
    should be able to answer 'how much should I trust this' before
    scrolling past ten sections, not only after reaching the bottom.
    One line, no chip row, so it never competes with the hero's own
    tightly-tuned chip rhythm (see MISSION V8's trend-chip fix)."""
    if not page_confidence or page_confidence.get("trust_band") is None:
        return ""
    return f'<p class="ph-trust-line">데이터 신뢰도 {escape(page_confidence["trust_band"])} ({page_confidence["trustworthy_pct"]}%)</p>'


def _data_trust_html(page_confidence: Optional[dict], provenance_summary: Optional[dict], data_quality_url: str = "") -> str:
    """MISSION V50 (2026-09-28): 'Remove Developer Thinking from Player
    History... keep only one small trust block.' The four real numbers
    below are not new -- they are page_confidence.trustworthy_pct and
    the three provenance_summary.rows counts (공식 기록/실측 기반 계산/
    확인 불가), which used to sit buried inside the much larger #8
    reconciliation cluster (_data_confidence_html) alongside pipeline
    vocabulary ('웨어하우스', 'PASS/PARTIAL', coverage matrices, a
    roadmap, a timeline) this mission explicitly bans from the public
    page. This function prints ONLY the four numbers plus a link to
    the separate Data Quality Report where that technical detail now
    lives -- never the pipeline language itself."""
    if not page_confidence:
        return ""
    rows_by_short = {r["short"]: r for r in (provenance_summary or {}).get("rows", [])}
    official = rows_by_short.get("공식 기록")
    measured = rows_by_short.get("실측 기반 계산")
    unknown = rows_by_short.get("확인 불가")
    stats = "".join(
        f'<div class="ph-trust-stat"><span class="ph-trust-stat-num">{row["count"]}</span><span class="ph-trust-stat-lbl">{escape(label)}</span></div>'
        for label, row in (("공식 기록", official), ("실측 기반 계산", measured), ("확인 불가", unknown))
        if row
    )
    link = f'<a class="ph-trust-link" href="{escape(data_quality_url)}">데이터 품질 보고서 보기 →</a>' if data_quality_url else ""
    return (
        '<div class="ph-trust-block" id="ph-data-trust">'
        '<p class="ph-trust-block-title">DATA TRUST</p>'
        f'<div class="ph-trust-headline"><span class="ph-trust-headline-num">{page_confidence["trustworthy_pct"]}%</span>'
        '<span class="ph-trust-headline-lbl">데이터 신뢰도</span></div>'
        f'<div class="ph-trust-stats">{stats}</div>'
        f'{link}'
        '</div>'
    )


def _reconciliation_html(
    report: Optional[dict], status: Optional[dict] = None, coverage_matrix: Optional[dict] = None,
    not_available: Optional[list] = None, data_confidence: str = "", extra_raw_data: str = "",
) -> str:
    """Transparency section: Player History is never built from one
    warehouse alone -- this shows exactly how many of her tournaments
    came from each of the 7 verified source categories, how many were
    merged across categories, and every real cross-source check that
    was run before this report was allowed to generate at all. Kept
    collapsed and last on the page by design -- this is supporting
    evidence for a player history, not the product itself.

    MISSION NEO PLAYER PROFILE V2 (2026-09-27): `extra_raw_data` is
    where the "NO DATABASE UI" relocations land -- career heartbeat,
    DNA growth-velocity/acceleration/stability, and round_history's
    three relocated extremes. Same real computations as before this
    mission, just moved here instead of competing with the first
    screen a golfer reads."""
    if not report:
        return ""
    count_keys = ["total_tournaments", "found_in_warehouse", "found_in_reader", "found_in_live", "merged", "missing", "conflicts_detected"]
    chips = "".join(_chip(f'{terms.RECONCILIATION_LABELS[k]} {report[k]}', positive=(k in ("total_tournaments", "found_in_warehouse") or (k in ("missing", "conflicts_detected") and report[k] == 0))) for k in count_keys)
    status_chip = _chip(f'상태: {report["status"]}', positive=report["status"] == "RECONCILED_OK")
    resolved_items = "".join(f"<li>{escape(line)}</li>" for line in report.get("resolved", []))
    resolved_html = f'<ul class="piq-checklist">{resolved_items}</ul>' if resolved_items else ""
    return (
        '<details class="evidence-detail pi-section" id="ph-reconciliation">'
        f'<summary class="section-heading"><h2>{terms.PAGE_RECONCILIATION_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">이 문서의 모든 대회 기록은 7개 카테고리 실측 소스를 대조(reconciliation)한 뒤에만 생성됩니다. '
        '하나의 웨어하우스에만 의존하지 않습니다.</p>'
        f'<div class="piq-audit">{status_chip}{chips}</div>'
        f'{resolved_html}'
        f'{_status_semantics_html(status)}'
        f'{_coverage_matrix_html(coverage_matrix)}'
        f'{_not_available_html(not_available or [])}'
        f'{extra_raw_data}'
        f'{data_confidence}'
        '</div></details>'
    )


def _in_progress_html(t: Optional[dict], hole_history: Optional[dict] = None) -> str:
    """NEO PLAYER BIOGRAPHY V4: 'If there is no confirmed LIVE
    tournament, hide the LIVE section completely. Never show an
    already-finished event as LIVE.' is_confirmed_live is set by
    reconcile() against the real official schedule, never assumed --
    when it is False (schedule says the tournament is over but NEO has
    no final result), this section renders nothing at all, rather than
    the earlier RED TEAM mission's honest-but-still-visible fallback.

    MISSION V40 (2026-09-28): when this real in-progress tournament is
    also the one real tournament with hole-level data (true for this
    player as of this build), a real link completes the explorer's
    Tournament -> Round -> Hole chain down to it -- never a link when
    the game_codes genuinely differ."""
    if not t or not t.get("is_confirmed_live"):
        return ""
    rounds = "".join(f'<td>R{r["round"]}</td>' for r in t["rounds_completed"])
    strokes = "".join(f'<td>{r["strokes"]}</td>' for r in t["rounds_completed"])
    partial = t.get("partial_round_sg")
    partial_chip = (
        _chip(f'R{partial["round"]} 진행 중 SG Total {_fmt(partial["total"])} (완주 라운드 아님, 참고용)')
        if partial else ""
    )
    hole_link = (
        f'<p class="piq-current-detail"><a href="#ph-hole-history">홀 기록 보기 →</a></p>'
        if hole_history and hole_history.get("game_code") == t["game_code"] else ""
    )
    return (
        f'<details class="evidence-detail pi-section" id="ph-in-progress" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_IN_PROGRESS_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(t["tournament"])} ({t["game_code"]}, {t["season"]}). {escape(t["note"])}</p>'
        f'<div class="table-scroll"><table class="data-table"><thead><tr>{rounds}</tr></thead>'
        f'<tbody><tr>{strokes}</tr></tbody></table></div>'
        f'<div class="piq-audit">{partial_chip}</div>'
        f'{hole_link}'
        '</div></details>'
    )


def _technical_stats_html(doc: Optional[dict]) -> str:
    """Real KLPGA official locationRecord capture, season 2025 only --
    driving distance, fairway accuracy, GIR, sand save, scrambling,
    putting. Recovered from docs/discovery/raw_samples/ during
    verification; a genuinely different season and source than the
    2026 current-season snapshot above, never merged with it."""
    if not doc:
        return ""
    import re as _re

    def _unit(label: Optional[str]) -> str:
        m = _re.search(r"\(([^)]+)\)\s*$", label or "")
        return m.group(1) if m else ""

    rows = "".join(
        f'<tr><td>{escape(m["label"])}</td><td>{escape(str(m["value"]))} {escape(_unit(m["value_label"]))}</td>'
        f'<td>{m["rank"] if m["rank"] is not None else _NO_DATA}</td>'
        f'<td>{escape(str(m["numerator"])) if m["numerator"] is not None else _NO_DATA} / {escape(str(m["denominator"])) if m["denominator"] is not None else _NO_DATA}</td>'
        f'<td>{escape(str(m["measured_rounds"])) if m["measured_rounds"] is not None else _NO_DATA}</td></tr>'
        for m in doc["metrics"]
    )
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-technical-stats-2025">'
        f'<summary class="section-heading"><h2>{terms.PAGE_TECHNICAL_STATS_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(doc["as_of_note"])}</p>'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        '<th>항목</th><th>값</th><th>순위</th><th>분자/분모</th><th>측정 라운드</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>'
        '</div></details>'
    )


def _not_available_html(items: list) -> str:
    """Nested inside the #8 data-detail section (RED TEAM mission J:
    'detailed reconciliation belongs ONLY inside #8') -- no longer a
    standalone top-level section on the public page."""
    if not items:
        return ""
    rows = "".join(f"<li>{escape(i)}</li>" for i in items)
    return (
        '<div class="ph-evo-block" id="ph-not-available">'
        f'<p class="piq-step-label piq-label-standalone">{terms.PAGE_NOT_AVAILABLE_TITLE}</p>'
        f'<ul class="piq-excluded-list">{rows}</ul></div>'
    )


def _hero_html(doc: dict) -> str:
    return (
        '<header class="pi-hero hero-data">'
        f'<p class="section-label">{terms.HERO_TITLE}</p>'
        f'<h1>{escape(doc["player_name"])}</h1>'
        f'<p class="pi-hero__meta">{escape(terms.HERO_SUBTITLE)}</p>'
        f'{_page_confidence_chip_html(doc.get("page_confidence"))}'
        "</header>"
    )


def render_player_history_html(
    doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None, data_quality_url: str = "",
) -> str:
    """Pure function: PLAYER_HISTORY.json in, page body HTML out.

    MISSION V50 (2026-09-28): "Remove Developer Thinking from Player
    History... Every section must answer 'what does this tell me about
    the player,' NOT 'how did NEO build the database.'"

    MISSION V50.1 (2026-09-28), a correction to V50's first pass: "Do
    NOT optimize for fewer sections. Optimize for zero repetition...
    Player History is allowed to be long. It is NOT allowed to repeat
    itself... Never summarize away the evidence that explains career
    evolution... If a section teaches something unique, keep it."
    V50's first pass wrongly treated 'developer-facing' and 'just
    numbers' as the same problem and moved BOTH kinds out. Only the
    first kind (source-reconciliation status, PASS/PARTIAL/BLOCKED
    semantics, the coverage matrix, the not-yet-available list, the
    field-confidence legend, the collection roadmap, the quality
    timeline -- none of it about the player, all of it about NEO's own
    pipeline) genuinely belongs on the separate Data Quality Report.
    The rest -- the official season snapshot, per-metric season-
    evolution charts, the rolling-trend/momentum chart, the 2025
    technical stats table, the DNA growth-velocity table, the career
    heartbeat, and the three other real round extremes -- teaches
    something no other section states, and is restored here. Nothing
    was ever deleted in either pass: every function below is the same
    real, already-tested function that existed before V50.

    Order, one question anchoring each numbered section:
      1 현재 폼 (지금 얼마나 잘 치는가? -- official season snapshot as
        its real supporting detail)
      2 왜 지금인가 (왜 잘 치는가?, one sentence + arrows + skill chain)
      3 최근 경기 결과 (최근 어떤 흐름인가?; Live Tournament nests here
        ONLY when actually confirmed live)
      4 선수 정체성 (어떤 유형의 선수인가? -- the DNA radar chart and
        its growth-velocity table sit directly beside this as real
        evidence, instead of being buried in a raw-data cluster)
      5 코스 프로필 (어떤 대회에서 강한가?)
      6 라운드 분석 (언제 잘 치는가? -- best/worst pair, plus the other
        three real extremes: most stable tournament, most improved
        round, largest collapse/recovery)
      7 커리어 스토리 (커리어는 어떻게 변했는가? -- season evolution,
        season replay, the rolling momentum trend, the career
        heartbeat, 2025 technical stats, and the tournament timeline/
        table are ALL real, non-repeating evidence for this question,
        not a database)
      8 DATA TRUST (a small, non-technical trust summary -- 신뢰도 %,
        공식 기록/실측 기반 계산/확인 불가 counts, and a link to the
        separate Data Quality Report for the pipeline mechanics)
    Every non-numbered block below is subordinate, nested beside the
    numbered section it elaborates."""
    from klpga.website_v2.player_intelligence_v2 import prev_next_html

    # MISSION V8 (2026-09-25): "freeze the architecture -- improve only
    # visual hierarchy, typography, spacing." Every rule that pass adds
    # (neo-site.css, "MISSION V8" block) is scoped under this one
    # wrapper class instead of touching the shared .piq-*/.pi-section
    # selectors directly -- those classes are also rendered by
    # player_intelligence_10097_report.py and player_intelligence_9431_
    # report.py, and this player's page must never leak style changes
    # onto another player's.
    body = (
        prev_next_html(prev_link, next_link)
        + _hero_html(doc)
        + _story_layer_html(doc)                                                                 # V71 Layer 1: Story
        + _current_form_hero_html(doc.get("current_vs_career"), doc.get("current_snapshot"), doc.get("current_form_indicator"))  # 1
        + _official_snapshot_html(doc.get("current_snapshot"))                                 # 1 (subordinate, restored by V50.1)
        + _why_now_html(doc.get("why_now"), doc.get("current_snapshot"), doc.get("current_vs_career"), doc.get("career_story", {}).get("current"))  # 2
        + _recent_form_html(doc.get("recent_form_5", []), doc.get("recent_form_10", []), doc.get("recent_form_20"))  # 3
        + _in_progress_html(doc.get("current_tournament_in_progress"), doc.get("hole_history"))  # 3 (subordinate, only if confirmed live)
        + _player_identity_html(doc.get("player_identity"))                                     # 4
        + _player_dna_radar_html(doc.get("player_dna_radar", []), doc.get("career_dna"))        # 4 (subordinate -- moved beside identity)
        + _dna_growth_velocity_html(doc.get("player_dna_growth"))                              # 4 (subordinate, restored by V50.1)
        + _course_profile_html(doc.get("course_profile"), doc.get("tournament_history"))        # 5
        + _round_history_html(doc["round_history"])                                            # 6
        + _round_history_detail_html(doc.get("round_history"))                                 # 6 (subordinate, restored by V50.1)
        + _hole_history_html(doc.get("hole_history"), doc.get("tournament_history"))           # 6 (subordinate)
        + _career_story_html(doc.get("career_story"), doc["career_overview"])                  # 7
        + _career_evolution_html(doc["career_evolution"])                                      # 7 (subordinate, restored by V50.1)
        + _season_replay_html(doc["season_replay"], doc["tournament_history"])                 # 7 (subordinate)
        + _career_rolling_trend_html(doc.get("career_rolling_trend"), doc.get("career_form_story"))  # 7 (subordinate, restored by V50.1)
        + _career_heartbeat_html(doc.get("career_heartbeat"))                                  # 7 (subordinate, restored by V50.1)
        + _technical_stats_html(doc.get("technical_stats_2025"))                               # 7 (subordinate, restored by V50.1)
        + _tournament_trend_html(doc["tournament_history"])                                    # 7 (subordinate)
        + _tournament_table_html(doc["tournament_history"])                                    # 7 (subordinate, collapsed)
        + _data_trust_html(doc.get("page_confidence"), doc.get("provenance_summary"), data_quality_url)  # 8
    )
    return f'<div class="ph-page">{body}</div>'
