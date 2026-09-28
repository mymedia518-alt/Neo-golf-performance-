"""Compare Mode -- a rendering capability, not a destination.

MISSION "PLAYER COMPARISON, ARCHITECTURE FIRST" (2026-09-28):
"Comparison is a capability, not a destination. Every major
visualization must expose a Compare action. When Compare is selected,
render the SAME visualization with another player using the identical
scale, identical time axis, identical colors, identical calculations.
Never duplicate components. Player Comparison must reuse 100% of the
existing Player History components. No duplicate code. No duplicate
pages."

This module owns ZERO chart-drawing logic of its own. Every function
below is a thin reshaping wrapper around two real player docs (each
from player_provider.load_player_history / PlayerProvider) into the
SAME primitives player_history_report.py already renders single-player
sections with:
  - _radar_svg_overlay: already a real two-series primitive, built for
    the existing season-vs-season DNA tab -- reused here unchanged for
    player-vs-player.
  - _trend_svg_by_index(..., compare=...): the SAME single trend-chart
    function every single-player chart on the page already calls, now
    accepting an optional second real series on the identical scale.
    There is no second trend-chart implementation anywhere.

Supported modes, per the mission:
  - Player vs Player: pass two different players' docs.
  - Player vs Self (different season): pass the SAME doc twice with
    different season_a/season_b -- no special case needed, since
    nothing below was ever season- or identity-aware to begin with.
  - Player vs Tour Average / Player vs Winner Benchmark: named as
    FUTURE by the mission. Not implemented here -- no built doc
    carries a tour-average or field-winner series yet, and adding one
    would be new data, explicitly out of this pass's scope
    ("Data second. Players last.").

Nothing here is wired into any page or route yet. This is the
capability layer only; where/how a real "Compare" action is triggered
in the UI is a later, separate decision.
"""
from __future__ import annotations

from html import escape
from typing import Optional

from klpga.website_v2.player_history_report import _chip, _fmt, _radar_svg_overlay, _trend_svg_by_index


def _dna_season(doc: Optional[dict], season: Optional[int] = None) -> Optional[dict]:
    """The one real season-shaped DNA entry to compare with -- the
    requested real season if present, else this player's own most
    recent real season. Never a fabricated or blended season."""
    radar = (doc or {}).get("player_dna_radar") or []
    if not radar:
        return None
    if season is not None:
        return next((r for r in radar if r.get("season") == season), None)
    return radar[-1]


def compare_dna_radar_html(doc_a: dict, doc_b: dict, season_a: Optional[int] = None, season_b: Optional[int] = None) -> str:
    """Player-vs-player (or player-vs-self, different season) DNA
    radar overlay -- reuses _radar_svg_overlay exactly as the existing
    single-player season-vs-season DNA tab does; zero new chart code.
    Renders nothing if either side's real percentiles aren't fully
    available for the season being compared, the same 'never a partial
    polygon next to a real one' rule the single-player overlay already
    enforces."""
    sd_a = _dna_season(doc_a, season_a)
    sd_b = _dna_season(doc_b, season_b)
    if not sd_a or not sd_b:
        return ""
    axes_a, axes_b = sd_a["axes"], sd_b["axes"]
    if not all(a.get("percentile") is not None for a in axes_a):
        return ""
    if not all(a.get("percentile") is not None for a in axes_b):
        return ""
    label_a = f'{(doc_a or {}).get("player_name", "A")} {sd_a["season"]}'
    label_b = f'{(doc_b or {}).get("player_name", "B")} {sd_b["season"]}'
    svg = _radar_svg_overlay(axes_a, axes_b, label_a, label_b)
    return (
        '<div class="ph-compare-block">'
        f'<p class="piq-step-label piq-label-standalone">{escape(label_a)} vs {escape(label_b)}</p>'
        f'{svg}'
        '<div class="piq-audit">'
        + _chip(label_a, positive=True) + _chip(label_b)
        + '</div></div>'
    )


def _season_trend_series(doc: Optional[dict], season: Optional[int] = None) -> Optional[dict]:
    """Real per-tournament SG Total series for one real season (this
    player's own most recent real season if none given) -- the same
    real rows the single-player season chart already draws from,
    reshaped for _trend_svg_by_index's compare parameter."""
    rows = (doc or {}).get("tournament_history") or []
    if not rows:
        return None
    if season is None:
        seasons_present = sorted({r["season"] for r in rows})
        if not seasons_present:
            return None
        season = seasons_present[-1]
    season_rows = [r for r in rows if r.get("season") == season and r.get("sg_total") is not None]
    if len(season_rows) < 2:
        return None
    markers = ["win" if r["is_win"] else ("top10" if r["is_top10"] else None) for r in season_rows]
    hover = [f'{r["tournament"]} ({r["season"]}) · SG {r["sg_total"]:+.2f}' for r in season_rows]
    return {"values": [r["sg_total"] for r in season_rows], "markers": markers, "hover": hover, "season": season}


def compare_season_trend_html(doc_a: dict, doc_b: dict, season_a: Optional[int] = None, season_b: Optional[int] = None) -> str:
    """Player-vs-player (or player-vs-self) season SG Total trend on
    the SAME chart, SAME scale -- built entirely from the shared
    _trend_svg_by_index's real compare= parameter. Renders nothing if
    either side has fewer than two real SG Total rows in the season
    being compared."""
    series_a = _season_trend_series(doc_a, season_a)
    series_b = _season_trend_series(doc_b, season_b)
    if not series_a or not series_b:
        return ""
    label_a = f'{(doc_a or {}).get("player_name", "A")} {series_a["season"]}'
    label_b = f'{(doc_b or {}).get("player_name", "B")} {series_b["season"]}'
    svg = _trend_svg_by_index(
        series_a["values"], series_a["markers"], hover=series_a["hover"],
        compare={"values": series_b["values"], "markers": series_b["markers"], "hover": series_b["hover"], "label": label_b},
    )
    if not svg:
        return ""
    return (
        '<div class="ph-compare-block">'
        f'<p class="piq-step-label piq-label-standalone">{escape(label_a)} vs {escape(label_b)}</p>'
        f'{svg}'
        '<div class="piq-audit">'
        + _chip(f'실선 = {label_a}', positive=True) + _chip(f'점선 = {label_b}')
        + '</div></div>'
    )


def compare_current_form_html(doc_a: dict, doc_b: dict) -> str:
    """Side-by-side real current-season-vs-career deltas -- the same
    real fields the single-player current-form hero already shows,
    reshaped as two columns instead of a chart (no existing chart
    primitive fits a single pair of numbers better than a plain
    comparison table, so this is a table, not an invented new chart)."""
    cvc_a = (doc_a or {}).get("current_vs_career")
    cvc_b = (doc_b or {}).get("current_vs_career")
    if not cvc_a or not cvc_b:
        return ""
    name_a = (doc_a or {}).get("player_name", "A")
    name_b = (doc_b or {}).get("player_name", "B")
    rows = [
        ("커리어 평균 대비", _fmt(cvc_a["delta_vs_career_average"]), _fmt(cvc_b["delta_vs_career_average"])),
        (f'{cvc_a["current_season"]}시즌 SG Total', _fmt(cvc_a["current_season_sg_total"]), _fmt(cvc_b["current_season_sg_total"])),
        ("커리어 평균 SG Total", _fmt(cvc_a["career_average_sg_total"]), _fmt(cvc_b["career_average_sg_total"])),
    ]
    body = "".join(f'<tr><td>{escape(label)}</td><td>{a}</td><td>{b}</td></tr>' for label, a, b in rows)
    return (
        '<div class="ph-compare-block">'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th>항목</th><th>{escape(name_a)}</th><th>{escape(name_b)}</th>'
        f'</tr></thead><tbody>{body}</tbody></table></div>'
        '</div>'
    )
