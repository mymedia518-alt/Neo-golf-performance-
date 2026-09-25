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


def _chip(text: str, positive: bool = False) -> str:
    cls = "label-chip label-chip--positive" if positive else "label-chip"
    return f'<span class="{cls}">{escape(str(text))}</span>'


def _fmt(v, plus: bool = True) -> str:
    if v is None:
        return "--"
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


# ---------------------------------------------------------------------------
# PAGE 1 -- CAREER OVERVIEW
# ---------------------------------------------------------------------------

def _career_overview_html(co: dict, snapshot: Optional[dict]) -> str:
    rows = co["season_rows"]
    cols = ["season", "events", "wins", "top10", "sg_total", "sg_ott", "sg_app", "sg_arg", "sg_putt", "sg_sample_size"]
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
        + _chip(f'상위10위 {co["total_top10"]}회')
        + _chip(f'최근 대회: {latest_tournament_name} ({latest_season})')
        + "</div>"
    )
    floor_note = f'<p class="piq-current-detail">{escape(co["data_floor_note"])}</p>'

    snapshot_html = ""
    if snapshot:
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
        snapshot_html = (
            '<details class="evidence-detail pi-section" id="ph-snapshot" open>'
            f'<summary class="section-heading"><h2>{terms.PAGE_SNAPSHOT_TITLE}</h2></summary>'
            '<div class="pi-section__body">'
            f'<p class="piq-current-detail">{escape(snapshot["as_of_note"])}</p>'
            '<div class="piq-audit">'
            + _chip(f'공식 SG 랭크 {snapshot["official_sg_rank"]}위')
            + _chip(f'SG Total {_fmt(snapshot["official_sg_total"])}')
            + _chip(f'SG OTT {_fmt(snapshot["official_sg_ott"])}')
            + _chip(f'SG APP {_fmt(snapshot["official_sg_app"])}')
            + _chip(f'SG ARG {_fmt(snapshot["official_sg_arg"])}')
            + _chip(f'SG PUTT {_fmt(snapshot["official_sg_putt"])}')
            + _chip(f'공식 SG 라운드 {snapshot["official_sg_rounds"]}')
            + "</div>"
            + '<div class="piq-audit">'
            + money_chip + avg_score_chip + avg_putts_chip + birdie_chip + gir_chip + par_save_chip + par_break_chip + recovery_chip
            + "</div></div></details>"
        )

    return (
        '<details class="evidence-detail pi-section" id="ph-career-overview" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE1_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{totals}{floor_note}{table}</div></details>{snapshot_html}'
    )


# ---------------------------------------------------------------------------
# PAGE 2 -- CAREER EVOLUTION
# ---------------------------------------------------------------------------

_EVOLUTION_DISPLAY_ORDER = ["avg_total", "avg_ott", "avg_app", "avg_arg", "avg_putt"]


def _career_evolution_html(evolution: dict) -> str:
    blocks = []
    for c in _EVOLUTION_DISPLAY_ORDER:
        data = evolution.get(c)
        if data is None:
            continue
        values = [pt["value"] for pt in data["series"]]
        spark = _sparkline_svg(values)
        delta_rows = "".join(
            f'<tr><td>{d["from_season"]}→{d["to_season"]}</td><td>{_fmt(d["delta"])}</td>'
            f'<td>{d["growth_pct"]:+.1f}%</td></tr>' if d["growth_pct"] is not None else
            f'<tr><td>{d["from_season"]}→{d["to_season"]}</td><td>{_fmt(d["delta"])}</td><td>--</td></tr>'
            for d in data["deltas"]
        )
        peak_season, peak_value = data["peak_season"]["season"], _fmt(data["peak_season"]["value"])
        worst_season, worst_value = data["worst_season"]["season"], _fmt(data["worst_season"]["value"])
        direction_label = terms.DIRECTION_LABEL.get(data["current_direction"], data["current_direction"])
        blocks.append(
            '<div class="ph-evo-block">'
            f'<p class="piq-step-label piq-label-standalone">{escape(data["label"])}</p>'
            f'{spark}'
            '<div class="piq-audit">'
            + _chip(f'최고 시즌 {peak_season} ({peak_value})', positive=True)
            + _chip(f'최저 시즌 {worst_season} ({worst_value})')
            + _chip(f'현재 방향: {direction_label}')
            + "</div>"
            + '<div class="table-scroll"><table class="data-table"><thead><tr><th>구간</th><th>변화량</th><th>증감률</th></tr></thead>'
            + f'<tbody>{delta_rows}</tbody></table></div>'
            + "</div>"
        )
    return (
        '<details class="evidence-detail pi-section" id="ph-career-evolution" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE2_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(blocks)}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 3 -- SEASON REPLAY
# ---------------------------------------------------------------------------

def _season_replay_html(replays: list) -> str:
    blocks = []
    for r in replays:
        q_cells = "".join(
            f'<td>{q["events"]}개, {_fmt(q["avg_sg_total"])}</td>' if q.get("avg_sg_total") is not None else f'<td>{q["events"]}개</td>'
            for q in r["quartiles"]
        )
        q_header = "".join(f"<th>{q['quarter']}분기</th>" for q in r["quartiles"])
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
        slump_chip = _chip(f'슬럼프: {escape(slump["tournament"])} {_fmt(slump["sg_total"])}') if slump else ""
        blocks.append(
            '<div class="ph-evo-block">'
            f'<p class="piq-step-label piq-label-standalone">{r["season"]}시즌 ({r["event_count"]}개 대회)</p>'
            f'<div class="table-scroll"><table class="data-table"><thead><tr>{q_header}</tr></thead>'
            f'<tbody><tr>{q_cells}</tr></tbody></table></div>'
            '<div class="piq-audit">'
            + volatility_chip + top10_chip + peak_chip + slump_chip + recovery_chip
            + "</div></div>"
        )
    return (
        '<details class="evidence-detail pi-section" id="ph-season-replay" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE3_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{"".join(blocks)}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 4 -- TOURNAMENT HISTORY
# ---------------------------------------------------------------------------

def _tournament_history_html(rows: list) -> str:
    body_rows = []
    for r in rows:
        comp = r.get("sg_components")
        comp_cells = (
            f'<td>{_fmt(comp["ott"])}</td><td>{_fmt(comp["app"])}</td><td>{_fmt(comp["arg"])}</td><td>{_fmt(comp["putt"])}</td>'
            if comp else "<td>--</td><td>--</td><td>--</td><td>--</td>"
        )
        badge = " 🏆" if r["is_win"] else (" •" if r["is_top10"] else "")
        body_rows.append(
            f'<tr><td>{r["season"]}</td><td>{escape(r["tournament"])}{badge}</td><td>{r["rank"] if r["rank"] is not None else "--"}</td>'
            f'<td>{_fmt(r["sg_total"])}</td>{comp_cells}</tr>'
        )
    header = "".join(f"<th>{escape(v)}</th>" for v in terms.TOURNAMENT_COLUMNS.values())
    table = f'<div class="table-scroll"><table class="data-table"><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
    return (
        '<details class="evidence-detail pi-section" id="ph-tournament-history" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE4_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><p class="piq-current-detail">실측 {len(rows)}개 대회, 시즌순 정렬. 🏆=우승, •=상위10위.</p>{table}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 5 -- ROUND HISTORY
# ---------------------------------------------------------------------------

def _round_card(label: str, r: Optional[dict], positive: bool = False) -> str:
    if not r:
        return ""
    season_suffix = f' ({r["season"]})' if "season" in r else ""
    detail = f'{escape(r["tournament"])}{season_suffix} '
    if "round" in r:
        detail += f'R{r["round"]} SG Total {_fmt(r["sg_total"])}'
    elif "delta" in r:
        detail += f'R{r["from_round"]}→R{r["to_round"]} {r["delta"]:+.2f}'
    elif "stddev" in r:
        detail += f'표준편차 {r["stddev"]:.2f} ({r["rounds"]}라운드)'
    return f'<div class="piq-brief"><p><strong>{escape(label)}</strong> {detail}</p></div>'


def _round_key(r: Optional[dict]) -> Optional[tuple]:
    if not r or "game_code" not in r or "from_round" not in r:
        return None
    return (r["game_code"], r["from_round"], r["to_round"])


def _round_history_html(rh: dict) -> str:
    most_improved = rh.get("most_improved_round")
    largest_recovery = rh.get("largest_recovery")
    # Two independent real criteria (single largest positive delta;
    # largest positive delta following a negative round) can point to
    # the exact same real round -- shown once, not twice, per the
    # "if the same insight appears twice, delete one" mission rule.
    same_round = _round_key(most_improved) is not None and _round_key(most_improved) == _round_key(largest_recovery)
    if same_round:
        improvement_recovery_cards = _round_card("최다 향상 라운드 (붕괴 이후 최대 회복이기도 함)", most_improved, positive=True)
    else:
        improvement_recovery_cards = (
            _round_card("최다 향상 라운드", most_improved, positive=True)
            + _round_card("최대 회복", largest_recovery, positive=True)
        )
    cards = (
        _round_card("최고 라운드", rh.get("best_round"), positive=True)
        + _round_card("최악 라운드", rh.get("worst_round"))
        + _round_card("가장 안정적인 대회", rh.get("most_stable_tournament"), positive=True)
        + improvement_recovery_cards
        + _round_card("최대 붕괴", rh.get("largest_collapse"))
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-round-history" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE5_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><p class="piq-current-detail">실측 라운드 {rh["total_rounds"]}개 기준.</p>{cards}</div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 6 -- PLAYER EVOLUTION
# ---------------------------------------------------------------------------

def _delta_line(d: Optional[dict]) -> str:
    if not d:
        return ""
    return f'{d["from_season"]}→{d["to_season"]} SG Total {d["delta"]:+.2f} ({d["growth_pct"]:+.1f}%)'


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
        "최대 하락": "실측 시즌 전환 중 하락 없음 -- 4개 시즌 전부 상승",
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
        '<details class="evidence-detail pi-section" id="ph-player-evolution" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE6_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{rows}</ul></div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 7 -- CAREER DNA
# ---------------------------------------------------------------------------

def _career_dna_html(dna: dict) -> str:
    if not dna:
        return ""
    items = [
        ("가장 일관된 요소", dna.get("most_consistent_component")),
        ("가장 빠르게 성장한 요소", dna.get("fastest_growing_component")),
        ("가장 변동성 큰 요소", dna.get("most_volatile_component")),
        ("커리어 기반 요소", f'{dna["career_foundation"]} ({dna["career_foundation_share_pct"]:+.1f}%)' if dna.get("career_foundation") else None),
        ("우승 기반 요소", f'{dna["winning_foundation"]} ({dna["winning_foundation_share_pct"]:+.1f}%)' if dna.get("winning_foundation") else None),
    ]
    rows = "".join(f'<li><strong>{escape(k)}</strong> — {escape(str(v))}</li>' for k, v in items if v)
    return (
        '<details class="evidence-detail pi-section" id="ph-career-dna" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE7_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{rows}</ul></div></details>'
    )


# ---------------------------------------------------------------------------
# PAGE 8 -- PLAYER STORY
# ---------------------------------------------------------------------------

def _player_story_html(story: list) -> str:
    if not story:
        return ""
    items = "".join(
        f'<li class="piq-roadmap-item"><p class="piq-step"><span class="piq-label">{m["season"]}</span>{escape(m["label"])}</p>'
        f'<p class="piq-current-detail">{escape(m["detail"])}</p></li>'
        for m in story
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-player-story" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE8_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-roadmap-list">{items}</ul></div></details>'
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
        '<details class="evidence-detail pi-section" id="ph-hole-history" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_HOLE_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(hh["tournament"])} ({hh["game_code"]}, {escape(hh["course"] or "")}) -- {escape(hh["capture_note"])}</p>'
        f'{"".join(round_blocks)}</div></details>'
    )


def _reconciliation_html(report: Optional[dict]) -> str:
    """Transparency section: Player History is never built from one
    warehouse alone -- this shows exactly how many of her tournaments
    came from each of the 7 verified source categories, how many were
    merged across categories, and every real cross-source check that
    was run before this report was allowed to generate at all."""
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
        '</div></details>'
    )


def _in_progress_html(t: Optional[dict]) -> str:
    if not t:
        return ""
    rounds = "".join(f'<td>R{r["round"]}</td>' for r in t["rounds_completed"])
    strokes = "".join(f'<td>{r["strokes"]}</td>' for r in t["rounds_completed"])
    partial = t.get("partial_round_sg")
    partial_chip = (
        _chip(f'R{partial["round"]} 진행 중 SG Total {_fmt(partial["total"])} (완주 라운드 아님, 참고용)')
        if partial else ""
    )
    return (
        '<details class="evidence-detail pi-section" id="ph-in-progress" open>'
        f'<summary class="section-heading"><h2>{terms.PAGE_IN_PROGRESS_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="piq-current-detail">{escape(t["tournament"])} ({t["game_code"]}, {t["season"]}) -- {escape(t["note"])}</p>'
        f'<div class="table-scroll"><table class="data-table"><thead><tr>{rounds}</tr></thead>'
        f'<tbody><tr>{strokes}</tr></tbody></table></div>'
        f'<div class="piq-audit">{partial_chip}</div>'
        '</div></details>'
    )


def _not_available_html(items: list) -> str:
    if not items:
        return ""
    rows = "".join(f"<li>{escape(i)}</li>" for i in items)
    return (
        '<details class="evidence-detail pi-section" id="ph-not-available">'
        f'<summary class="section-heading"><h2>{terms.PAGE_NOT_AVAILABLE_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-excluded-list">{rows}</ul></div></details>'
    )


def _hero_html(doc: dict) -> str:
    return (
        '<header class="pi-hero hero-data">'
        f'<p class="section-label">{terms.HERO_TITLE}</p>'
        f'<h1>{escape(doc["player_name"])}</h1>'
        f'<p class="pi-hero__meta">{escape(terms.HERO_SUBTITLE)}</p>'
        "</header>"
    )


def render_player_history_html(doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None) -> str:
    """Pure function: PLAYER_HISTORY.json in, page body HTML out."""
    from klpga.website_v2.player_intelligence_v2 import prev_next_html

    return (
        prev_next_html(prev_link, next_link)
        + _hero_html(doc)
        + _reconciliation_html(doc.get("reconciliation"))
        + _career_overview_html(doc["career_overview"], doc.get("current_snapshot"))
        + _in_progress_html(doc.get("current_tournament_in_progress"))
        + _career_evolution_html(doc["career_evolution"])
        + _season_replay_html(doc["season_replay"])
        + _tournament_history_html(doc["tournament_history"])
        + _round_history_html(doc["round_history"])
        + _player_evolution_html(doc["player_evolution"])
        + _career_dna_html(doc["career_dna"])
        + _player_story_html(doc["player_story"])
        + _hole_history_html(doc.get("hole_history"))
        + _not_available_html(doc.get("not_available", []))
    )
