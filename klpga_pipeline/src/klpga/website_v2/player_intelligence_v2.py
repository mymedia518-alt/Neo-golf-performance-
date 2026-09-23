"""Player Intelligence page integration (Sprint 3).

Integration only, never redesign: this module loads the already-generated
content/website_v2/knowledge_engine/player_intelligence/<id>/latest.json
(the frozen Sprint 1 Knowledge Engine's Sprint 2 output) and renders it as
a 13-section HTML page. It never calculates anything itself -- every
number, label and reason on the page is read straight out of the JSON
document.

If latest.json does not exist yet, renders a "Generating Player
Intelligence..." placeholder and queues generation -- never an empty page.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Optional

from klpga.knowledge_engine import knowledge_rules as rules
from klpga.tournament_context import CONTENT_DIR

KNOWLEDGE_ENGINE_PI_DIR = CONTENT_DIR / "knowledge_engine" / "player_intelligence"
GENERATION_QUEUE_PATH = CONTENT_DIR / "knowledge_engine" / "generation_queue.json"

# QA Sprint (dedup): SG-component and rate-stat labels, and the
# percentile-phrase rule (상위 N% / 평균 수준 / 하위 N%), used to live
# here as a second, drifting copy of knowledge_rules.py's own
# SG_COMPONENT_LABELS / FIELD_METRIC_LABELS / pctl_phrase(). The UI
# layer never renders raw numbers or invents labels, so it reads them
# straight from the one place that defines them.
SG_COMPONENT_LABELS = rules.SG_COMPONENT_LABELS
RATE_STAT_LABELS = rules.FIELD_METRIC_LABELS

# Percent-shaped rate stats (2 decimals + %); the other two rate stats
# (average_score, average_putts) are counts, formatted with their own
# unit in _rate_stat_value() below -- never mixed with a % sign.
_PERCENT_RATE_STAT_KEYS = {"birdie_rate", "gir_rate", "par_save_rate", "par_break_rate", "recovery_rate"}

_DOC_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Loading / caching / queueing
# ---------------------------------------------------------------------------


def latest_json_path(player_id: str) -> Path:
    return KNOWLEDGE_ENGINE_PI_DIR / str(player_id) / "latest.json"


def load_document_cached(player_id: str) -> Optional[dict]:
    """mtime-keyed cache: a rewritten latest.json (a tournament
    regeneration) is picked up automatically on its next read, an
    unchanged file is served from memory. No explicit invalidation call
    is needed -- correctness follows from the generator only ever
    rewriting a file when its content actually changed (Sprint 2's
    input-signature skip)."""
    path = latest_json_path(player_id)
    if not path.exists():
        _DOC_CACHE.pop(str(player_id), None)
        return None

    mtime = path.stat().st_mtime
    cached = _DOC_CACHE.get(str(player_id))
    if cached is not None and cached[0] == mtime:
        return cached[1]

    doc = json.loads(path.read_text(encoding="utf-8"))
    _DOC_CACHE[str(player_id)] = (mtime, doc)
    return doc


def enqueue_generation(player_id: str, *, player_name: Optional[str] = None) -> None:
    """Idempotent: adds player_id to the real generation queue file if
    not already present. A background job (player_intelligence_generator)
    is expected to drain this queue -- this function only ever records
    the request, it never generates anything itself."""
    GENERATION_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if GENERATION_QUEUE_PATH.exists():
        try:
            queue = json.loads(GENERATION_QUEUE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            queue = {"pending": []}
    else:
        queue = {"pending": []}

    pending = queue.setdefault("pending", [])
    if not any(str(p.get("player_id")) == str(player_id) for p in pending):
        pending.append({"player_id": str(player_id), "player_name": player_name})
        GENERATION_QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Small render helpers
# ---------------------------------------------------------------------------


def _sg(value) -> str:
    return "—" if value is None else f"{value:+.2f}"


def _pctl(value) -> str:
    return "—" if value is None else rules.pctl_phrase(value)


def _rate_stat_value(key: str, value) -> str:
    if value is None:
        return "—"
    if key in _PERCENT_RATE_STAT_KEYS:
        return f"{value:.2f}%"
    if key == "average_score":
        return f"{value:.2f}타"
    if key == "average_putts":
        return f"{value:.2f}개"
    return f"{value:.2f}"


def _citations_detail(citations: list) -> str:
    if not citations:
        return ""
    rows = "".join(
        f"<dt>{escape(str(c.get('field_path', '')))}</dt><dd><code>{escape(str(c.get('source', '')))} = {escape(str(c.get('value', '')))}</code></dd>"
        for c in citations
    )
    return f'<details class="evidence-detail"><summary>ⓘ 근거</summary><dl>{rows}</dl></details>'


def _section(section_id: str, heading: str, body_html: str, *, open_by_default: bool = True) -> str:
    open_attr = " open" if open_by_default else ""
    return (
        f'<details class="evidence-detail pi-section" id="{escape(section_id)}"{open_attr}>'
        f'<summary class="section-heading"><h2>{escape(heading)}</h2></summary>'
        f'<div class="pi-section__body">{body_html}</div>'
        f"</details>"
    )


# ---------------------------------------------------------------------------
# 13 sections
# ---------------------------------------------------------------------------


def _hero_html(doc: dict) -> str:
    hero = doc.get("hero", {})
    pt = doc.get("player_type", {})
    name = hero.get("player_name") or hero.get("player_id") or ""
    season = hero.get("current_season")
    season_text = f"{season}시즌" if season else "시즌 데이터 없음"
    return (
        '<header class="pi-hero hero-data">'
        f'<p class="section-label">PLAYER INTELLIGENCE</p>'
        f"<h1>{escape(str(name))}</h1>"
        f'<p class="pi-hero__type"><span class="label-chip">{escape(pt.get("label_ko", ""))}'
        f'<span class="pi-hero__type-en">{escape(pt.get("label_en", ""))}</span></span></p>'
        f'<p class="pi-hero__meta">{escape(season_text)} · 표본 {hero.get("sample_count", 0)}건</p>'
        "</header>"
    )


def _player_type_html(doc: dict) -> str:
    pt = doc.get("player_type", {})
    body = f"<p>{escape(pt.get('evidence_text', ''))}</p>" + _citations_detail(pt.get("citations", []))
    return _section("player-type", "선수 유형", body)


def _player_dna_html(doc: dict) -> str:
    axes = doc.get("player_dna", {}).get("axes", [])
    if not axes:
        return _section("player-dna", "선수 DNA", '<p class="pi-empty">이 선수의 SG 세부 지표 데이터가 없습니다.</p>')

    n = len(axes)
    cx, cy, r = 165, 120, 70
    import math

    def point(i, frac):
        angle = -math.pi / 2 + (2 * math.pi * i / n)
        return cx + r * frac * math.cos(angle), cy + r * frac * math.sin(angle)

    grid_rings = "".join(
        f'<polygon class="pi-radar-grid" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, frac) for i in range(n)))}" />'
        for frac in (0.33, 0.66, 1.0)
    )
    fill_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, a["percentile"] / 100.0) for i, a in enumerate(axes)))

    def _anchor_for(x):
        if x > cx + 5:
            return "start"
        if x < cx - 5:
            return "end"
        return "middle"

    labels = "".join(
        (lambda lx, ly: f'<text class="pi-radar-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{_anchor_for(lx)}">{escape(a["label"])}</text>')(*point(i, 1.22))
        for i, a in enumerate(axes)
    )
    svg = (
        f'<svg class="pi-radar" viewBox="0 0 340 240" role="img" aria-label="선수 DNA 레이더 차트">'
        f"{grid_rings}"
        f'<polygon class="pi-radar-fill" points="{fill_points}" />'
        f"{labels}"
        f"</svg>"
    )
    table = "".join(f"<li>{escape(a['label'])}: {_pctl(a['percentile'])}</li>" for a in axes)
    return _section("player-dna", "선수 DNA", f'{svg}<ul class="pi-radar-legend">{table}</ul>')


def _key_kpis_html(doc: dict) -> str:
    form = doc.get("current_form", {})
    shot = doc.get("shot_profile", {})
    kpis = [
        ("최근 5R SG", _sg(form.get("recent_5_sg"))),
        ("최근 10R SG", _sg(form.get("recent_10_sg"))),
        ("장기 SG", _sg(form.get("long_term_sg"))),
        (f"{shot.get('season', '')}시즌 SG Total", _sg(shot.get("avg_total"))),
    ]
    cells = "".join(f'<div class="kpi-block"><span class="kpi-label">{escape(label)}</span><strong class="kpi-value">{escape(value)}</strong></div>' for label, value in kpis)
    return _section("key-kpis", "핵심 지표", f'<div class="pi-kpi-grid">{cells}</div>')


def _current_form_html(doc: dict) -> str:
    form = doc.get("current_form", {})
    rate_stats = form.get("rate_stats", {})
    rows = "".join(
        f"<tr><th scope='row'>{escape(RATE_STAT_LABELS.get(k, k))}</th><td>{_rate_stat_value(k, v)}</td></tr>"
        for k, v in rate_stats.items()
    )
    volatility = form.get("volatility")
    body = (
        f'<p>변동성(최근 10R SG 표준편차): {"—" if volatility is None else f"{volatility:.2f}"}</p>'
        f'<table class="data-table pi-kv-table"><tbody>{rows}</tbody></table>'
        if rate_stats
        else '<p class="pi-empty">현재 시즌 기록 데이터가 없습니다.</p>'
    )
    return _section("current-form", "최근 경기력", body)


def _shot_profile_html(doc: dict) -> str:
    shot = doc.get("shot_profile", {})
    components = ("avg_ott", "avg_app", "avg_arg", "avg_putt")
    if all(shot.get(c) is None for c in components):
        return _section("shot-profile", "샷 특성", '<p class="pi-empty">시즌 SG 세부 기록이 없습니다.</p>')
    rows = "".join(f"<tr><th scope='row'>{escape(SG_COMPONENT_LABELS[c])}</th><td>{_sg(shot.get(c))}</td></tr>" for c in components)
    body = f'<table class="data-table pi-kv-table"><tbody>{rows}</tbody></table>'
    return _section("shot-profile", "샷 특성", body)


def _course_fit_html(doc: dict) -> str:
    history = doc.get("course_fit", {}).get("history", [])
    if not history:
        return _section("course-fit", "코스 적합도", '<p class="pi-empty">이 대회 시리즈 과거 출전 기록이 없습니다.</p>')

    def _history_row(h):
        sg_text = _sg(h.get("sg_total"))
        return f"<tr><td>{h.get('season', '')}</td><td>{escape(h.get('tournament') or '')}</td><td>{sg_text}</td></tr>"

    rows = "".join(_history_row(h) for h in history)
    body = f'<div class="table-scroll"><table class="data-table"><thead><tr><th>시즌</th><th>대회</th><th>SG Total</th></tr></thead><tbody>{rows}</tbody></table></div>'
    return _section("course-fit", "코스 적합도", body)


def _metric_list_html(section_id: str, heading: str, items: list) -> str:
    if not items:
        return _section(section_id, heading, '<p class="pi-empty">해당 없음</p>')
    rows = "".join(f"<li>{escape(item['label'])}: {_pctl(item['percentile'])}</li>" for item in items)
    return _section(section_id, heading, f'<ul class="pi-metric-list">{rows}</ul>')


def _reason_list_html(section_id: str, heading: str, reasons: list, *, tone: str) -> str:
    if not reasons:
        return _section(section_id, heading, '<p class="pi-empty">해당 없음</p>')
    chip_class = "label-chip--positive" if tone == "positive" else "label-chip--negative"
    items = "".join(
        f'<li class="pi-reason"><span class="label-chip {chip_class}">{escape(r["text"])}</span>{_citations_detail(r.get("citations", []))}</li>'
        for r in reasons
    )
    return _section(section_id, heading, f'<ul class="pi-reason-list">{items}</ul>')


def _evolution_html(doc: dict) -> str:
    evolution = doc.get("evolution", {})
    steps = evolution.get("steps", [])
    narrative = evolution.get("narrative", "")
    if not steps:
        body = f"<p>{escape(narrative)}</p>"
    else:
        items = "".join(
            f"<li>{s['season']}시즌: SG Total {_sg(s.get('avg_total'))}"
            + (f" ({s['delta_from_prev']:+.2f})" if s.get("delta_from_prev") is not None else "")
            + "</li>"
            for s in steps
        )
        body = f"<p>{escape(narrative)}</p><ul class='pi-evolution-list'>{items}</ul>" + _citations_detail(evolution.get("citations", []))
    return _section("evolution", "최근 변화", body)


def _neo_verdict_html(doc: dict) -> str:
    verdict = doc.get("neo_verdict", {}).get("summary", "")
    return (
        '<details class="pi-verdict" id="neo-verdict" open>'
        '<summary><h2>NEO 한줄평</h2></summary>'
        f"<p>{escape(verdict)}</p>"
        "</details>"
    )


def _prev_next_html(prev_link: Optional[dict], next_link: Optional[dict]) -> str:
    if not prev_link and not next_link:
        return ""
    prev_html = f'<a href="{escape(prev_link["href"])}">← {escape(prev_link["name"])}</a>' if prev_link else "<span></span>"
    next_html = f'<a href="{escape(next_link["href"])}">{escape(next_link["name"])} →</a>' if next_link else "<span></span>"
    return f'<nav class="player-prev-next">{prev_html}{next_html}</nav>'


# ---------------------------------------------------------------------------
# Top-level page render
# ---------------------------------------------------------------------------


def render_player_intelligence_v2_html(doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None) -> str:
    """Pure function: JSON document in, full page body HTML out. Never
    reads a file, never calculates a statistic -- every value here was
    already computed by the frozen Knowledge Engine (Sprint 1) and
    assembled by the generator (Sprint 2)."""
    sections = [
        _hero_html(doc),
        _player_type_html(doc),
        _player_dna_html(doc),
        _key_kpis_html(doc),
        _current_form_html(doc),
        _shot_profile_html(doc),
        _course_fit_html(doc),
        _metric_list_html("strengths", "강점", doc.get("strengths", [])),
        _metric_list_html("risks", "주의할 점", doc.get("weaknesses", [])),
        _evolution_html(doc),
        _reason_list_html("why-wins", "우승 요인", doc.get("why_wins", []), tone="positive"),
        _reason_list_html("why-loses", "주의할 점", doc.get("why_loses", []), tone="negative"),
        _neo_verdict_html(doc),
    ]
    return _prev_next_html(prev_link, next_link) + "".join(sections)


def render_generating_placeholder_html(player_id: str, player_name: Optional[str] = None) -> str:
    """Never an empty page: a visible, real status message plus a
    client-side auto-refresh so the visitor sees the real page the
    moment generation finishes, with no manual reload needed."""
    label = escape(player_name) if player_name else escape(str(player_id))
    return (
        '<div class="pi-generating">'
        f"<h1>{label}</h1>"
        "<p>Generating Player Intelligence...</p>"
        '<p class="trend-summary">잠시 후 다시 확인해 주세요.</p>'
        '<meta http-equiv="refresh" content="15">'
        "</div>"
    )


def build_or_placeholder(
    player_id: str,
    *,
    player_name: Optional[str] = None,
    prev_link: Optional[dict] = None,
    next_link: Optional[dict] = None,
) -> str:
    """The single integration entry point every page-builder calls:
    real document -> real page; missing document -> visible placeholder
    plus a queued generation request. Never returns an empty string."""
    doc = load_document_cached(player_id)
    if doc is None:
        enqueue_generation(player_id, player_name=player_name)
        return render_generating_placeholder_html(player_id, player_name=player_name)
    return render_player_intelligence_v2_html(doc, prev_link=prev_link, next_link=next_link)
