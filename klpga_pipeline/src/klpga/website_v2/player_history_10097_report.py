"""PLAYER HISTORY GOLD STANDARD V1 renderer -- playerCode=10097 only.

Player Intelligence is no longer the goal for this player: this renders
a dense, table/chart-first career archive from
scripts/build_10097_player_history.py's real-data-only JSON. History
first, explanation second, speculation never -- this renderer adds no
new claims, it only formats what the builder already verified. Not a
reusable framework; scoped to this one player.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR
from klpga.website_v2 import player_history_10097_terms as terms

REPORT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / "10097" / "PLAYER_HISTORY.json"


def load_report_cached() -> Optional[dict]:
    if not REPORT_PATH.exists():
        return None
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


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
    poly_points = []
    dots = []
    for i, a in enumerate(axes):
        if a.get("percentile") is None:
            continue
        x, y = point(i, a["percentile"])
        poly_points.append(f"{x:.1f},{y:.1f}")
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#0f5c46"/>')
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
        pct_text = f'{a["percentile"]:.0f}' if a.get("percentile") is not None else "N/A"
        axis_ko = terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"])
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="10" fill="#3d4a43">{escape(axis_ko)} {pct_text}</text>')
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="플레이어 DNA 레이더">'
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
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="{escape(label_a)} vs {escape(label_b)} 비교">'
        f'{rings}{spokes}{poly(axes_a, "#0f5c46")}{poly(axes_b, "#c98a1a")}{"".join(labels)}</svg>'
    )


def _trend_svg_by_index(values: list, markers: list, width: int = 640, height: int = 90) -> str:
    """Chronological performance trend (x = tournament order, never
    rank -- equal spacing means equal chronological step, not equal
    performance). markers[i] in {'win','top10',None} highlights wins
    and top10s distinctly from ordinary finishes."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad = 6
    n = len(values)
    step = (width - 2 * pad) / (n - 1)
    pts = []
    for i, v in enumerate(values):
        x = pad + i * step
        y = height - pad - ((v - lo) / span) * (height - 2 * pad)
        pts.append((x, y))
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    dots = []
    for (x, y), m in zip(pts, markers):
        if m == "win":
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#c98a1a" stroke="#7a5610" stroke-width="1"/>')
        elif m == "top10":
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#0f5c46"/>')
        else:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="#9db3a8"/>')
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="대회별 SG Total 추세 (시간순)">'
        f'<polyline points="{path}" fill="none" stroke="#0f5c46" stroke-width="1.5"/>{"".join(dots)}</svg>'
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
    table = f'<div class="table-scroll"><table class="data-table"><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'

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


def _delta_phrase_ko(delta: float) -> str:
    """Golf-meaningful absolute-unit phrasing (RED TEAM mission G) --
    never a percentage. A percentage change against a near-zero SG
    baseline (e.g. SG ARG +0.15 -> +3115%) is mathematically possible
    but analytically misleading, so it is never computed for display
    here at all -- only the real stroke-unit delta and its direction."""
    if delta > 0:
        return f"{delta:.2f}타 개선"
    if delta < 0:
        return f"{abs(delta):.2f}타 하락"
    return "변화 없음"


def _career_evolution_html(evolution: dict) -> str:
    """V6 mission (2026-09-25): 'spend the entire mission deleting.' The
    season-to-season delta TABLE (e.g. '2023→2024: 0.16타 개선') said
    exactly what the sparkline right above it already shows visually,
    plus what the peak/worst-season chips already flag as the extremes
    -- removing it does not make a reader understand her season-by-
    season trend any less, so it is gone. _delta_phrase_ko stays
    defined (still used elsewhere) even though this call site no
    longer needs it."""
    blocks = []
    for c in _EVOLUTION_DISPLAY_ORDER:
        data = evolution.get(c)
        if data is None:
            continue
        values = [pt["value"] for pt in data["series"]]
        spark = _sparkline_svg(values)
        peak_season, peak_raw = data["peak_season"]["season"], data["peak_season"]["value"]
        worst_season, worst_raw = data["worst_season"]["season"], data["worst_season"]["value"]
        direction_label = terms.DIRECTION_LABEL.get(data["current_direction"], data["current_direction"])
        blocks.append(
            '<div class="ph-evo-block">'
            f'<p class="piq-step-label piq-label-standalone">{escape(data["label"])}</p>'
            f'{spark}'
            '<div class="piq-audit">'
            + _chip(f'최고 시즌 {peak_season} ({_fmt(peak_raw)})', positive=True)
            # MISSION V12: "worst season" only reads as a genuine warning
            # (red) when her real number that season was actually
            # negative -- her weakest season can still be a solidly
            # positive one, and coloring that red would be misleading,
            # not merely "worst" among her own strong seasons.
            + _chip(f'최저 시즌 {worst_season} ({_fmt(worst_raw)})', negative=worst_raw < 0)
            + _chip(f'현재 방향: {direction_label}')
            + "</div>"
            + "</div>"
        )
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-career-evolution" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE2_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(blocks)}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 3 -- SEASON REPLAY
# ---------------------------------------------------------------------------

def _named_windows_html(nw: Optional[dict]) -> str:
    """First-5 / Middle-5 / Last-5 real chronological windows for one
    season (V4 mission: Season -> Season Window -> Tournament). Middle
    is omitted with a disclosed reason when the season is too short to
    isolate a non-overlapping middle window."""
    if not nw:
        return ""
    cells = []
    for w in (nw["first"], nw["middle"], nw["last"]):
        if w is None:
            cells.append("<td>표본 부족</td>")
            continue
        avg = _fmt(w["avg_sg_total"]) if w["avg_sg_total"] is not None else _NO_DATA
        cells.append(f'<td>{w["label"]}: SG {avg} (우승 {w["wins"]}, Top10 {w["top10"]})</td>')
    note = f'<p class="piq-current-detail">{escape(nw["middle_unavailable_reason"])}</p>' if nw.get("middle_unavailable_reason") else ""
    return (
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        '<th>처음 5개</th><th>중반 5개</th><th>최근 5개</th></tr></thead>'
        f'<tbody><tr>{"".join(cells)}</tr></tbody></table></div>{note}'
    )


def _season_replay_html(replays: list) -> str:
    """V6 mission (2026-09-25): the per-season quartile table (four
    columns of event-count + average SG) asked the same question the
    peak/slump chips already answer more precisely (this season's real
    best and worst tournaments), just at coarser resolution -- removing
    it does not make a reader understand a given season any less, so
    it is gone. named_windows (First 5/Middle 5/Last 5) stays: it is
    real chronological granularity the chips do not cover."""
    blocks = []
    for r in replays:
        named_windows_html = _named_windows_html(r.get("named_windows"))
        recovery = r.get("recovery_next_event")
        if recovery:
            recovery_tournament = escape(recovery["tournament"])
            recovery_sg = _fmt(recovery["sg_total"])
            recovery_delta = recovery["delta_vs_slump"]
            recovery_chip = _chip(f'슬럼프 직후: {recovery_tournament} {recovery_sg} ({recovery_delta:+.2f})')
        else:
            recovery_chip = _chip("슬럼프 직후 대회 없음 (시즌 마지막 대회)")
        volatility_chip = _chip(f'변동성(표준편차) {r["volatility_stddev"]}') if r["volatility_stddev"] is not None else ""
        top10_chip = _chip(f'상위10위율 {r["top10_rate_pct"]}%')
        peak = r.get("peak")
        peak_chip = _chip(f'피크: {escape(peak["tournament"])} {_fmt(peak["sg_total"])}', positive=True) if peak else ""
        slump = r.get("slump")
        # MISSION V12: red only when the slump tournament's real SG
        # Total was actually negative -- her "slump" within a strong
        # season can still be a positive number, which red would
        # misrepresent as a bad round.
        slump_chip = _chip(f'슬럼프: {escape(slump["tournament"])} {_fmt(slump["sg_total"])}', negative=slump["sg_total"] < 0) if slump else ""
        blocks.append(
            '<div class="ph-evo-block">'
            f'<p class="piq-step-label piq-label-standalone">{r["season"]}시즌 ({r["event_count"]}개 대회)</p>'
            f'{named_windows_html}'
            '<div class="piq-audit">'
            + volatility_chip + top10_chip + peak_chip + slump_chip + recovery_chip
            + "</div></div>"
        )
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-season-replay" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE3_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(blocks)}</div></details>'
    )


def _stage_narrative(s: dict) -> str:
    """RED TEAM (2026-09-25) narrative mission: story-first sentence for
    one Career Form Story stage, built only from real numbers already
    on `s` (delta_vs_career_average, best/worst component and their
    real deltas vs career average). Never claims a 'decline' when the
    real delta is still positive -- only the RELATIVE ranking among her
    four components changes wording, the sign of the real number
    decides the verb."""
    delta = s.get("delta_vs_career_average")
    if delta is not None and delta > 0:
        tone = "커리어 평균을 웃돌던 시기였습니다"
    elif delta is not None and delta < 0:
        tone = "커리어 평균에 못 미치던 시기였습니다"
    else:
        tone = "실측 SG 데이터가 부족한 시기였습니다"

    best, best_delta = s.get("best_component"), s.get("best_delta")
    worst, worst_delta = s.get("worst_component"), s.get("worst_delta")
    clauses = []
    if best:
        verb = "이 시기를 이끌었습니다" if best_delta is not None and best_delta > 0 else "그나마 가장 선방했습니다"
        clauses.append(f"{best}가 {verb}")
    if worst:
        verb = "가장 부진했습니다" if worst_delta is not None and worst_delta < 0 else "상대적으로 가장 덜 강했습니다"
        clauses.append(f"{worst}는 {verb}")
    skill_text = ", ".join(clauses) if clauses else "SG 세부 항목을 비교할 실측 데이터가 부족합니다"
    return f"{tone} — {skill_text}."


def _career_form_story_html(stages: Optional[list]) -> str:
    """RED TEAM (2026-09-25): 'Keep every real computation. Hide every
    implementation detail.' career_rolling_trend's real sliding-window
    series, self-percentile, and window mechanics are never shown here
    -- only the already-computed values selected by
    _career_form_story() (scripts/build_10097_player_history.py),
    translated into named chapters (시즌 초반/중반/후반, 전성기, 현재
    폼) that each answer one question: which skill improved, which
    skill declined. A story sentence leads every card; the real numbers
    are supporting chips underneath, never the headline.

    When her career peak (전성기) happened to fall inside the same real
    tournament range as one of the three season chapters -- true for
    this player as of this build -- the two labels are combined into
    one card instead of repeating identical numbers twice."""
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

    cards = []
    for s in merged:
        start_t, end_t = escape(s["start_tournament"]), escape(s["end_tournament"])
        range_text = start_t if s["start_tournament"] == s["end_tournament"] else f"{start_t} ~ {end_t}"
        sentence = escape(_stage_narrative(s))
        delta = s.get("delta_vs_career_average")
        chips = _chip(f'커리어 평균 대비 {delta:+.2f}', positive=delta > 0) if delta is not None else ""
        if s.get("best_component"):
            chips += _chip(f'{s["best_component"]} {s["best_delta"]:+.2f}', positive=True)
        if s.get("worst_component"):
            chips += _chip(f'{s["worst_component"]} {s["worst_delta"]:+.2f}', negative=s["worst_delta"] < 0)
        cards.append(
            '<div class="ph-form-stage">'
            f'<p class="piq-step-label piq-label-standalone">{escape(s["stage"])}</p>'
            f'<p class="piq-current-detail">{sentence}</p>'
            f'<p class="piq-current-detail">{range_text}</p>'
            f'<div class="piq-audit">{chips}</div>'
            '</div>'
        )
    return '<div class="ph-form-story">' + "".join(cards) + '</div>'


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
    spark = _sparkline_svg(values, width=640, height=90)
    career_avg = crt.get("career_average_sg_total")

    def _window_chip(label: str, w: Optional[dict], positive: bool = False) -> str:
        """V6 mission: lead with the delta vs career average, never the
        bare SG Total alone. RED TEAM (2026-09-25): self-percentile
        (rank among her own other windows) is never shown -- an
        implementation detail of how the window was found, not a story
        fact."""
        if not w:
            return ""
        vs_avg = w.get("delta_vs_career_average")
        vs_avg_text = f'커리어 평균 대비 {vs_avg:+.2f}' if vs_avg is not None else f'SG {_fmt(w["moving_average_sg_total"])}'
        # MISSION V12: red only when this window's real delta vs her own
        # career average is actually negative -- the same "color the
        # real sign, never the label" rule as the other worst/slump
        # chips above.
        is_negative = (vs_avg if vs_avg is not None else w["moving_average_sg_total"]) < 0
        return _chip(
            f'{label}: {escape(w["start_tournament"])}~{escape(w["end_tournament"])} {vs_avg_text} (실측 SG {_fmt(w["moving_average_sg_total"])})',
            positive=positive, negative=(not positive and is_negative),
        )

    recovery = crt.get("recovery_window")
    recovery_chip = (
        _chip(
            f'회복기: 슬럼프기 대비 {recovery["delta_vs_slump"]:+.2f} '
            f'(커리어 평균 대비 {recovery["delta_vs_career_average"]:+.2f}, 실측 SG {_fmt(recovery["moving_average_sg_total"])})',
            positive=recovery["delta_vs_slump"] > 0,
        )
        if recovery else _chip("슬럼프기 이후 회복기 없음 (커리어 마지막 시기)")
    )
    career_median = crt.get("career_median_sg_total")
    career_median_chip = _chip(f'커리어 중앙값 SG {_fmt(career_median, plus=False)}') if career_median is not None else ""

    peak = crt.get("peak_window")
    sustain_chip = (
        _chip(f'이 전성기는 이후 실측 {peak["sustainability_tournaments"]}개 대회 동안 이어졌습니다', positive=True)
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
        bars.append(f'<rect x="{x - 1.6:.1f}" y="{y:.1f}" width="3.2" height="{max(bar_h, 1):.1f}" fill="{color}"/>')
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
    if best_key == worst_key:
        sentence = f'{label}에는 {_WINDOW_SKILL_LABEL[best_key]} {vals[best_key]:+.2f}만 실측되어 있습니다 ({sample}).'
    else:
        sentence = (
            f'{label}에는 {_WINDOW_SKILL_LABEL[best_key]}({vals[best_key]:+.2f})가 가장 강했고, '
            f'{_WINDOW_SKILL_LABEL[worst_key]}({vals[worst_key]:+.2f})가 가장 약했습니다 ({sample} 실측).'
        )
    return f'<p class="piq-current-detail">{escape(sentence)}</p>'


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
                label=escape(label), t=escape(r["tournament"]), s=r["season"],
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
        trend_svg = (
            '<div class="ph-evo-block">'
            f'{_trend_svg_by_index(values, markers)}'
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
    disappeared'."""
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
            f'<tr><td>{r["season"]}</td><td>{escape(r["tournament"])}{badge}</td><td>{r["rank"] if r["rank"] is not None else _NO_DATA}</td>'
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
    if not r:
        return ""
    season_suffix = f' ({r["season"]})' if "season" in r else ""
    detail = f'{escape(r["tournament"])}{season_suffix} '
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
    every other worst/slump chip on this page."""
    if not r:
        return ""
    season_suffix = f' ({r["season"]})' if "season" in r else ""
    sign_class = "ph-round-big--negative" if r["sg_total"] < 0 else "ph-round-big--positive"
    return (
        f'<div class="ph-round-big {sign_class}">'
        f'<div class="ph-round-big-lbl">{escape(label)}</div>'
        f'<div class="ph-round-big-num">{_fmt(r["sg_total"])}</div>'
        f'<div class="ph-round-big-cap">{escape(r["tournament"])}{season_suffix} · R{r["round"]}</div>'
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
# PAGE 6 -- PLAYER EVOLUTION
# ---------------------------------------------------------------------------

def _delta_line(d: Optional[dict]) -> str:
    if not d:
        return ""
    return f'{d["from_season"]}→{d["to_season"]} SG Total {_delta_phrase_ko(d["delta"])}'


def _delta_key(d: Optional[dict]) -> Optional[tuple]:
    if not d:
        return None
    return (d["from_season"], d["to_season"])


def _player_evolution_html(pe: dict) -> str:
    if not pe:
        return ""
    # Any two of these five detections can point to the exact same real
    # season-to-season transition (e.g. the smallest delta can also be
    # the first positive one) -- every pair is checked, not just one
    # hardcoded pair, and merged into a single combined-label card, per
    # the "if the same insight appears twice, delete one" mission rule.
    fallback_text = {
        "최대 하락": "실측 시즌 전환 중 하락 없음. 4개 시즌 전부 상승했습니다.",
        "추세 반전": "실측 데이터에 추세 반전 없음",
    }
    slots = [
        ("첫 향상", pe.get("first_improvement")),
        ("최대 향상", pe.get("biggest_improvement")),
        ("최대 하락", pe.get("biggest_decline") if not pe.get("no_decline_observed") else None),
        ("추세 반전", pe.get("trend_reversal")),
        ("정체에 가장 가까운 구간", pe.get("closest_to_plateau")),
    ]
    merged: dict = {}
    standalone: list = []
    for label, d in slots:
        key = _delta_key(d)
        if key is None:
            text = fallback_text.get(label)
            if text:
                standalone.append((label, text))
            continue
        if key in merged:
            merged[key][0].append(label)
        else:
            merged[key] = ([label], d)

    items = [("이자 ".join(labels), _delta_line(d)) for labels, d in merged.values()] + standalone
    rows = "".join(f'<li><strong>{escape(k)}</strong> — {escape(v)}</li>' for k, v in items if v)
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-player-evolution" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE6_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{rows}</ul></div></details>'
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


def _player_dna_radar_html(seasons_data: list) -> str:
    """Single radar chart driven by a pure-CSS season selector (this
    site renders no client-side script anywhere, so the tabs are plain
    radio inputs + `:checked` sibling selectors -- no JS is added).
    Every value is a percentile within that season's real player
    population, never a raw SG unit plotted directly, per the
    mission's explicit normalization requirement. An optional
    'A vs B' comparison overlay is offered only when both seasons have
    every axis available."""
    if not seasons_data:
        return ""
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
        delta_rows = "".join(
            f'<tr><td>{escape(terms.RADAR_AXIS_LABEL_KO.get(a["axis"], a["axis"]))}</td>'
            f'<td>{a["percentile"]:.0f}</td>'
            f'<td>{a["delta_vs_career_mean"]:+.1f}</td></tr>'
            for a in sd["axes"] if a.get("delta_vs_career_mean") is not None
        )
        delta_table = (
            '<div class="table-scroll"><table class="data-table"><thead><tr>'
            '<th>영역</th><th>백분위</th><th>커리어 평균 대비</th></tr></thead>'
            f'<tbody>{delta_rows}</tbody></table></div>'
        ) if delta_rows else ""
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
        '<div class="ph-dna-tabs">'
        f'{"".join(tab_inputs)}'
        f'<div class="ph-dna-tab-bar">{"".join(tab_labels)}</div>'
        f'<div class="ph-dna-panels">{"".join(panels)}</div>'
        '</div>'
        '</div></details>'
    )


def _career_dna_html(dna: dict) -> str:
    """V5 mission: 'delete everything else.' most_consistent_component,
    career_foundation and winning_foundation are already narrated in
    #4 선수 정체성 (Player Identity) -- repeating them here as a second
    checklist was exactly the 'repeated numbers' the mission targets.
    Only the two facts Identity does NOT already state survive here."""
    if not dna:
        return ""
    items = [
        ("가장 빠르게 성장한 요소", dna.get("fastest_growing_component")),
        ("가장 변동성 큰 요소", dna.get("most_volatile_component")),
    ]
    rows = "".join(f'<li><strong>{escape(k)}</strong> — {escape(str(v))}</li>' for k, v in items if v)
    if not rows:
        return ""
    return (
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-career-dna">'
        f'<summary class="section-heading"><h2>{terms.PAGE7_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{rows}</ul></div></details>'
    )


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 -- SECTION 1: CURRENT FORM
# ---------------------------------------------------------------------------

_FORM_INDICATOR_LABEL = {"UP": "상승세", "DOWN": "하락세", "FLAT": "보합세"}


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


def _why_now_html(why_now: Optional[dict], csvc: Optional[dict]) -> str:
    """'Do NOT explain every metric. Answer only: why is she playing
    well now? Lead with change... One sentence only.' The sentence
    leads; arrows follow -- exactly the 'APP ▲ OTT ▲ PUTT ▼' format the
    mission asked for verbatim.

    V6 mission (2026-09-25): 'spend the entire mission deleting... if
    removing this does not make the user understand her less, delete
    it.' V5's dot-plot chart said the same four numbers the arrows
    already say, just slower to read -- removed. csvc is still passed
    in (unused) only so this signature does not need to change again
    if a future mission wants the raw table back; it renders nothing
    on its own now.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): the text+number
    chips ('APP ▲ +0.57') become a 4-card icon grid -- one big colored
    arrow per component, the real delta demoted to a small number
    beneath it."""
    if not why_now:
        return ""
    arrow_cards = "".join(
        '<div class="ph-arrow-card{down}">'
        '<span class="ph-arrow-big">{arrow}</span>'
        '<div class="ph-arrow-lbl">{label}</div>'
        '<div class="ph-arrow-num">{delta:+.2f}</div>'
        '</div>'.format(
            down=" ph-arrow-card--down" if a["direction"] == "DOWN" else "",
            arrow=_ARROW.get(a["direction"], ""),
            label=escape(a["component"].removeprefix("SG ")),
            delta=a["delta"],
        )
        for a in why_now["arrows"]
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-why-now" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_WHY_NOW_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-conclusion">{escape(why_now["sentence"])}</p>'
        f'<div class="ph-arrow-grid">{arrow_cards}</div>'
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

def _career_story_html(story: Optional[dict], career_overview: dict) -> str:
    """'Do NOT start with 2023, 2024, 2025. Instead start with Current
    -> Winning Stage -> Breakthrough -> Development -> Adaptation. Only
    afterwards reveal seasons.' Every chapter reuses one of
    _player_story's already-computed milestones (build_10097_player_
    history.py) -- this renderer only reorders and relabels them.
    career_overview is the same real dict #1's hero and #11's audit
    section already use -- the season table tail is not a second,
    independently-built summary."""
    if not story:
        return ""
    current = story["current"]
    current_html = (
        '<div class="ph-bio-stage">'
        '<p class="piq-step-label piq-label-standalone">지금</p>'
        f'<p class="piq-current-detail">{current["season"]}시즌, SG Total {_fmt(current["sg_total"])}, '
        f'우승 {current["wins"]}회, 상위10위 {current["top10"]}회 ({current["events"]}개 대회 표본).</p>'
        '</div>'
    )
    chapter_blocks = []
    for c in story["chapters"]:
        milestone_lines = "".join(
            f'<p class="piq-current-detail">{m["season"]}시즌 — {escape(m["label"])}: {escape(m["detail"])}</p>'
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
        rows.append(
            f'<text x="0" y="{y + row_h * 0.65:.1f}" font-size="11" fill="#3d4a43">{escape(p["tournament_family"])}</text>'
            f'<rect x="{x0:.1f}" y="{y + 4:.1f}" width="{max(x1 - x0, 1):.1f}" height="{row_h - 12:.1f}" fill="{color}"/>'
            f'<text x="{width - 4}" y="{y + row_h * 0.65:.1f}" font-size="11" fill="#3d4a43" text-anchor="end">{v:+.2f}</text>'
        )
    zero_line = f'<line x1="{zero_x:.1f}" y1="0" x2="{zero_x:.1f}" y2="{height}" stroke="#8a988f" stroke-width="1" stroke-dasharray="2 2"/>'
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" class="ph-spark" role="img" aria-label="반복 대회 강세·약세 비교">'
        f'{zero_line}{"".join(rows)}</svg>'
    )


def _course_profile_html(profiles: Optional[list]) -> str:
    """'Strength by course. Weakness by course. Nothing speculative.'
    Real venue/course names are not reliably on file for most
    tournaments (see NOT_AVAILABLE) -- this groups by repeated real
    tournament name instead (a disclosed, real proxy for a recurring
    host course), never a guessed venue.

    V5 mission ('replace repeated numbers with visual comparison...
    delete everything else'): the full numeric table used to be the
    whole section -- now a single bar chart shows the real top-3/
    bottom-3 at a glance, and the complete list moves into a nested,
    collapsed detail for anyone who wants every row."""
    if not profiles:
        return ""
    top = profiles[:3]
    bottom = [p for p in profiles[-3:] if p not in top]
    highlight = top + bottom
    bars = _course_strength_bars_svg(highlight)

    rows = "".join(
        f'<tr><td>{escape(p["tournament_family"])}</td><td>{p["appearances"]}</td>'
        f'<td>{_fmt(p["avg_sg_total"])}</td>'
        f'<td>{escape(p["best_tournament"])} ({_fmt(p["best_sg_total"])})</td>'
        f'<td>{escape(p["worst_tournament"])} ({_fmt(p["worst_sg_total"])})</td></tr>'
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
        '<p class="piq-current-detail">대회별 코스명은 실측 커버리지가 낮아, 같은 이름으로 반복 개최된 대회(2회 이상 '
        '출전)를 실제 근거로 삼아 강세/약세를 정리합니다.</p>'
        f'{bars}'
        f'{full_table}'
        '</div></details>'
    )


# ---------------------------------------------------------------------------
# HOLE HISTORY + NOT AVAILABLE
# ---------------------------------------------------------------------------

def _hole_history_html(hh: Optional[dict]) -> str:
    if not hh:
        return ""
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
        '<details class="evidence-detail pi-section pi-section--sub" id="ph-hole-history" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_HOLE_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(hh["tournament"])} ({hh["game_code"]}, {escape(hh["course"] or "")}). {escape(hh["capture_note"])}</p>'
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


def _in_progress_html(t: Optional[dict]) -> str:
    """NEO PLAYER BIOGRAPHY V4: 'If there is no confirmed LIVE
    tournament, hide the LIVE section completely. Never show an
    already-finished event as LIVE.' is_confirmed_live is set by
    reconcile() against the real official schedule, never assumed --
    when it is False (schedule says the tournament is over but NEO has
    no final result), this section renders nothing at all, rather than
    the earlier RED TEAM mission's honest-but-still-visible fallback."""
    if not t or not t.get("is_confirmed_live"):
        return ""
    rounds = "".join(f'<td>R{r["round"]}</td>' for r in t["rounds_completed"])
    strokes = "".join(f'<td>{r["strokes"]}</td>' for r in t["rounds_completed"])
    partial = t.get("partial_round_sg")
    partial_chip = (
        _chip(f'R{partial["round"]} 진행 중 SG Total {_fmt(partial["total"])} (완주 라운드 아님, 참고용)')
        if partial else ""
    )
    return (
        f'<details class="evidence-detail pi-section" id="ph-in-progress" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_IN_PROGRESS_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(t["tournament"])} ({t["game_code"]}, {t["season"]}). {escape(t["note"])}</p>'
        f'<div class="table-scroll"><table class="data-table"><thead><tr>{rounds}</tr></thead>'
        f'<tbody><tr>{strokes}</tr></tbody></table></div>'
        f'<div class="piq-audit">{partial_chip}</div>'
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


def render_player_history_html(doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None) -> str:
    """Pure function: PLAYER_HISTORY.json in, page body HTML out.

    MISSION NEO PLAYER PROFILE V2 (2026-09-27): "우리는 골퍼가 선수
    이름을 클릭했을 때 30초 안에 '이 선수가 지금 어떤 선수인가'를
    이해할 수 있는 페이지를 만든다." Not a feature mission -- every
    real number, chart, and section below already existed under NEO
    PLAYER BIOGRAPHY V4; this mission only reordered, consolidated,
    relocated, and demoted them so the page reads as one Q&A flow
    instead of a database. No new data, section, chart, metric, JSON
    field, or SQLite table was added. Strict order, one question per
    numbered section:
      1 현재 폼 (현재 얼마나 잘 치는가?, 5-second hero)
      2 왜 지금인가 (왜 잘 치는가?, one sentence + arrows)
      3 최근 경기 결과 (최근 어떤 흐름인가?; Live Tournament nests
        here ONLY when actually confirmed live -- otherwise hidden
        completely, never shown as if a finished event were still
        live)
      4 선수 정체성 (어떤 유형의 선수인가?)
      5 코스 프로필 (어떤 대회에서 강한가?)
      6 라운드 분석 (언제 잘 치는가? -- best/worst pair only; the
        other three already-real round extremes relocate to #8)
      7 커리어 스토리 (커리어는 어떻게 변했는가? -- leads a cluster of
        unnumbered subordinate blocks: season evolution, season
        replay, career form story/rolling trend, 2025 technical
        stats, tournament timeline, DNA radar, DNA summary)
      8 데이터베이스 / 검증 (Raw Data, collapsed, always last --
        everything technical, including the relocated career
        heartbeat/DNA growth-velocity/round extremes, lives ONLY here)
    Every non-numbered block below is subordinate, nested beside the
    numbered section it elaborates -- never numbered on its own, so
    the visible page never contradicts this 8-item hierarchy."""
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
        + _current_form_hero_html(doc.get("current_vs_career"), doc.get("current_snapshot"), doc.get("current_form_indicator"))  # 1
        + _official_snapshot_html(doc.get("current_snapshot"))                                 # 1 (subordinate)
        + _why_now_html(doc.get("why_now"), doc.get("current_skill_vs_career"))                # 2
        + _recent_form_html(doc.get("recent_form_5", []), doc.get("recent_form_10", []), doc.get("recent_form_20"))  # 3
        + _in_progress_html(doc.get("current_tournament_in_progress"))                          # 3 (subordinate, only if confirmed live)
        + _player_identity_html(doc.get("player_identity"))                                     # 4
        + _course_profile_html(doc.get("course_profile"))                                       # 5
        + _round_history_html(doc["round_history"])                                            # 6
        + _hole_history_html(doc.get("hole_history"))                                          # 6 (subordinate)
        + _career_story_html(doc.get("career_story"), doc["career_overview"])                  # 7
        + _career_evolution_html(doc["career_evolution"])                                      # 7 (subordinate)
        + _player_evolution_html(doc["player_evolution"])                                      # 7 (subordinate)
        + _season_replay_html(doc["season_replay"])                                            # 7 (subordinate)
        + _career_rolling_trend_html(doc.get("career_rolling_trend"), doc.get("career_form_story"))  # 7 (subordinate)
        + _technical_stats_html(doc.get("technical_stats_2025"))                               # 7 (subordinate)
        + _tournament_trend_html(doc["tournament_history"])                                    # 7 (subordinate)
        + _tournament_table_html(doc["tournament_history"])                                    # 7 (subordinate, collapsed)
        + _player_dna_radar_html(doc.get("player_dna_radar", []))                               # 7 (subordinate)
        + _career_dna_html(doc["career_dna"])                                                  # 7 (subordinate)
        + _reconciliation_html(
            doc.get("reconciliation"), doc.get("status"), doc.get("coverage_matrix"), doc.get("not_available", []),
            extra_raw_data=(
                _career_heartbeat_html(doc.get("career_heartbeat"))
                + _dna_growth_velocity_html(doc.get("player_dna_growth"))
                + _round_history_detail_html(doc.get("round_history"))
            ),
            data_confidence=_data_confidence_html(
                doc.get("page_confidence"), doc.get("field_confidence_legend"),
                doc.get("provenance_summary"), doc.get("data_confidence_roadmap"), doc.get("data_quality_timeline"),
            ),
        )  # 8
    )
    return f'<div class="ph-page">{body}</div>'
