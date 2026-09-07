"""Build the NEO GOLF DATA HOME V4 "KLPGA PERFORMANCE TERMINAL" candidate.

CANDIDATE ONLY -- never promoted, merged, or wired into production.
Completely separate product concept from HOME V3 (candidate/neo-home-v3-shell,
commit 375bf9a, which is preserved untouched): V3 is a players-first page
with a large hero; V4 is a data terminal where the performance board and
summary strip dominate above-the-fold, brand copy is minimal, and every
metric beyond player name / K-RANK is deliberately withheld pending
validation (a stricter policy than V3's, reflecting what this session's
NEO Ranking V2 round-count audit actually found: the SG warehouse's
round-count semantics have an unresolved ~47% mismatch rate against the
official leaderboard, so even the "real" recent-SG figures V3 displayed
are not safe to present as validated here).

Reuses (read-only, never edits) klpga.website_v2.home_ranking.join_home_rows
-- the same production, formula-blocked HOME data contract -- for player_id/
player_name/k_rank only. The `features` block (recent/long-term SG,
volatility) is deliberately NOT used for display in V4: PERFORMANCE SG /
FORM / VOL / TREND / EVENTS render "—" for every row regardless of whether
a feature value exists, per the explicit V4 policy.
"""
from __future__ import annotations

import json
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ranking import join_home_rows, load_json  # noqa: E402

CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "home-v4-data-terminal"
DASH = "—"

# Same conclusion as HOME V3: no verified, official-KLPGA-profile-sourced
# sponsor field exists anywhere in this repository for the full 546-player
# regular-tour population (confirmed by repo-wide search). Kept as its own
# named constant (not shared with V3's build script) so the two candidate
# tracks stay fully independent, per instruction.
SPONSOR_SOURCE: dict[str, str] = {}

_SILHOUETTE_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">'
    '<circle cx="12" cy="8" r="3.4"/><path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7"/></svg>'
)

NAV_ITEMS = (("players", "PLAYERS", "/"), ("tournaments", "TOURNAMENTS", "/tournaments/"),
             ("neo-lab", "NEO LAB", "/neo-lab/"), ("about", "ABOUT", "/about/"))

# ------------------------------------------------------------- MODEL VALIDATION
# REVIEW PATCH (post-f51c323): detailed engineering/research evidence --
# the 1852-player gap, K-Ranking temporal-mapping unverified status, the
# SG-table-vs-official round-count disagreement rate, WD/DQ/CUT red-team
# wording -- belongs in NEO LAB (the methodology/evidence surface), not on
# the public HOME terminal. Each row below now carries three parts:
#   name         -- short label, shown on both HOME and NEO LAB
#   status       -- public-safe state only (VERIFIED / VALIDATING /
#                   NOT PUBLISHED), shown on both
#   evidence     -- the detailed, research-grade description, shown ONLY
#                   on NEO LAB, anchored so a HOME row can link to it
# anchor_id is derived from `name` (lowercased, spaces->hyphens) so HOME's
# compact row and NEO LAB's detailed row always point at the same place --
# see render_model_validation_panel(mode=...) below.
#
# Grounded in real repository evidence already established this session
# (NEO Ranking V2 round-count audit + mismatch diagnostic, the frozen V1
# baseline's own K_TEMPORAL_MAPPING_UNVERIFIED field, home_ranking.py's
# FORMULA_STATE). "VERIFIED" is used only where evidence genuinely
# supports it -- none of these six rows currently qualifies, which is
# itself the honest, correct state to display.
VALIDATION_ROWS = (
    ("DATA COVERAGE", "VALIDATING",
     "official KLPGA field size vs. SG-warehouse-linked players has a known, unexplained gap (1852 players)"),
    ("TEMPORAL INTEGRITY", "VALIDATING",
     "no leakage detected in the frozen baseline, but its own K-Ranking temporal mapping is marked unverified"),
    ("ROUND SEMANTICS", "VALIDATING",
     "SG-table round counts vs. official leaderboard round counts show an unresolved disagreement rate"),
    ("OUTCOME VALIDATION", "VALIDATING",
     "WD/DQ/CUT classification from official leaderboard evidence is still under red-team review"),
    ("NEO RANKING V2", "NOT PUBLISHED",
     "no approved ranking formula exists; zero NEO Rank values are published anywhere"),
    ("PUBLICATION", "NOT PUBLISHED",
     "no NEO performance metric has cleared validation for public display"),
)


def _validation_anchor(name: str) -> str:
    return "evidence-" + name.lower().replace(" ", "-")


def _fmt_krank(value) -> str:
    return str(value) if value is not None else DASH


def _row_view(row: dict) -> dict:
    player_id = row["player_id"]
    k_rank = row.get("k_rank")
    return {
        "player_id": player_id,
        "player_name": row["player_name"],
        "sponsor": SPONSOR_SOURCE.get(player_id, ""),
        "k_rank": k_rank,
        "k_rank_display": _fmt_krank(k_rank),
        # V4 policy: every one of these is "—" regardless of feature data.
        "neo_rank_display": DASH,
        "performance_sg_display": DASH,
        "form_display": DASH,
        "vol_display": DASH,
        "trend_display": DASH,
        "events_display": DASH,
        "photo_license_status": "UNVERIFIED",
    }


def render_head(title: str) -> str:
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title>"
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="/assets/home-v4.css">'
        '<script src="/assets/home-v4.js" defer></script></head>'
    )


def render_terminal_bar(active: str) -> str:
    links = []
    for key, label, url in NAV_ITEMS:
        cls = ' class="is-active" aria-current="page"' if key == active else ""
        links.append(f'<a href="{url}"{cls}>{label}</a>')
    return f'''<header class="t-bar"><div class="t-bar__row">
<a class="t-brand" href="/"><span class="t-brand__name">NEO GOLF DATA</span><span class="t-brand__tag">KLPGA PERFORMANCE TERMINAL</span></a>
<button type="button" class="t-nav-toggle" data-t-nav-toggle aria-expanded="false" aria-controls="t-primary-nav" aria-label="메뉴">&#9776;</button>
<nav class="t-nav" id="t-primary-nav" data-t-nav aria-label="주요 메뉴">{"".join(links)}</nav>
<div class="t-bar__spacer"></div>
<div class="t-bar__meta"><span><b>2026</b> SEASON</span><span>DATA STATUS <span class="t-status-validating">VALIDATING</span></span></div>
</div></header>'''


def render_provenance_line() -> str:
    return '''<div class="t-provenance"><div class="t-provenance__row">
<span><b>SOURCE</b>KLPGA OFFICIAL DATA</span>
<span><b>UPDATE</b>ROUND-END</span>
<span><b>MODEL</b>NEO V2 &middot; VALIDATING</span>
</div></div>'''


def render_summary_strip(summary: dict, ranking_snapshot_label: str) -> str:
    """REVIEW PATCH (post-f51c323): every cell's label now states its exact
    source/definition in public language, per the independent review.

    - NEO PLAYER DATABASE (was "KLPGA PLAYER DB"): the old label implied
      this is KLPGA's own official player count. It is NOT -- it is NEO's
      own compiled historical regular-tour player master, whose match
      against the CURRENT official registry is explicitly unverified
      (HOME_REGULAR_TOUR_PLAYER_MASTER.json's own
      population_validation_state field). Relabeled and the sub-line
      states this plainly instead of implying total KLPGA membership.
    - K-RANK SNAPSHOT LINK (was "K-RANK COVERAGE"): kept as a real count
      (it is a real, verifiable join against one dated official snapshot),
      but the percentage is REMOVED (its denominator -- the player
      database above -- is itself not a verified "total" figure, so a
      percentage of it would misleadingly read as more precise than it
      is), and the exact snapshot (season/week + official source) is
      named instead of a vague "official snapshot".
    - NEO ARCHIVED EVENTS (was "HISTORICAL EVENTS", a raw count): the SG
      warehouse's 97-tournament count must not be presented as if it were
      complete official KLPGA historical coverage -- its own round-count
      semantics are still VALIDATING (see Model Validation). Per the
      review's option (B), this cell shows the dash on HOME; the real
      count and its full provenance are documented in NEO LAB instead
      (see render_neo_lab_page's evidence section), consistent with
      keeping this cell's status aligned with the ROUND SEMANTICS row
      below rather than contradicting it.
    - VALIDATION STATUS: unchanged.
    """
    cells = [
        ("NEO PLAYER DATABASE", str(summary["population_count"]),
         "NEO 자체 집계 · 역대 정규투어 선수 마스터 (현재 등록 명부 일치 여부 미확인)"),
        ("K-RANK SNAPSHOT LINK", str(summary["k_ranking_join_success"]),
         f"{ranking_snapshot_label} 공식 K-Rank 스냅샷과 연결된 선수 수"),
        ("NEO ARCHIVED EVENTS", DASH, "공개 방법론 확정 전 · NEO LAB에서 근거 확인"),
        ("VALIDATION STATUS", "VALIDATING", "NEO Ranking 공식 미승인"),
    ]
    body = []
    for label, value, sub in cells:
        is_dash = value == DASH
        body.append(
            f'<div class="t-summary__cell"><p class="t-summary__label">{escape(label)}</p>'
            f'<p class="t-summary__value{" is-dash" if is_dash else ""}">{escape(value)}</p>'
            f'<p class="t-summary__sub">{escape(sub)}</p></div>'
        )
    return f'<div class="t-summary"><div class="t-summary__row">{"".join(body)}</div></div>'


def _avatar_html() -> str:
    return f'<span class="t-avatar" aria-hidden="true">{_SILHOUETTE_SVG}</span>'


def render_performance_board(views: list[dict], population_count: int) -> str:
    head = (
        "<thead><tr>"
        '<th scope="col">NEO</th><th scope="col" class="t-col-player">PLAYER</th>'
        '<th scope="col">SPONSOR</th><th scope="col">K-RANK</th>'
        '<th scope="col">PERFORMANCE SG</th><th scope="col">FORM</th>'
        '<th scope="col">VOL</th><th scope="col">TREND</th><th scope="col">EVENTS</th>'
        "</tr></thead>"
    )
    desktop_rows = []
    mobile_rows = []
    for v in views:
        common_attrs = (
            f'data-player-row tabindex="0" role="button" '
            f'aria-label="{escape(v["player_name"])} 성과 검사기 열기" '
            f'data-player-name="{escape(v["player_name"].casefold())}" '
            f'data-player-display-name="{escape(v["player_name"])}" '
            + (f'data-k-rank="{v["k_rank"]}" ' if v["k_rank"] is not None else "")
            + f'data-k-rank-display="{escape(v["k_rank_display"])}"'
        )
        desktop_rows.append(
            f'<tr {common_attrs}>'
            f'<td><span class="t-dash">{v["neo_rank_display"]}</span></td>'
            f'<th scope="row"><span class="t-player-cell">{_avatar_html()}{escape(v["player_name"])}</span></th>'
            f'<td class="t-sponsor-cell">{escape(v["sponsor"])}</td>'
            f'<td class="{"t-krank-real" if v["k_rank"] is not None else "t-dash"}">{escape(v["k_rank_display"])}</td>'
            f'<td class="t-dash">{v["performance_sg_display"]}</td>'
            f'<td class="t-dash">{v["form_display"]}</td>'
            f'<td class="t-dash">{v["vol_display"]}</td>'
            f'<td class="t-dash">{v["trend_display"]}</td>'
            f'<td class="t-dash">{v["events_display"]}</td>'
            "</tr>"
        )
        mobile_rows.append(
            f'<div class="t-mobile-row" {common_attrs}>'
            f'<span class="t-mobile-row__rank t-dash">{v["neo_rank_display"]}</span>'
            f'<span class="t-mobile-row__name">{escape(v["player_name"])}</span>'
            f'<span class="t-mobile-row__krank {"t-krank-real" if v["k_rank"] is not None else "t-dash"}">{escape(v["k_rank_display"])}</span>'
            "</div>"
        )
    table = f'<table class="t-board">{head}<tbody data-t-board-body>{"".join(desktop_rows)}</tbody></table>'
    return f'''<section class="t-section" id="performance-board" aria-labelledby="board-heading"><div class="t-wrap">
<div class="t-section__head"><h2 class="t-section__title" id="board-heading">NEO Performance Board</h2>
<span class="t-badge t-badge--validating">NEO RANKING &middot; VALIDATING</span></div>
<div class="t-toolbar">
<label for="t-search">SEARCH</label><input id="t-search" type="search" placeholder="player name" autocomplete="off">
<label for="t-sort">SORT</label><select id="t-sort"><option value="name">PLAYER</option><option value="k-rank">K-RANK</option></select>
<output id="t-visible-count">{population_count}</output>
</div>
<div class="t-board-scroll">{table}</div>
<div class="t-mobile-list" data-t-mobile-list>{"".join(mobile_rows)}</div>
<p class="t-section__meta" style="margin-top:8px;">NEO RANK, PERFORMANCE SG, FORM, VOL, TREND, EVENTS는 검증이 승인되기 전까지 &mdash;로 표기합니다. K-RANK는 공식 스냅샷과 연결된 경우에만 표시합니다. 스폰서는 KLPGA 공식 프로필에서 확인된 경우에만 표기하며, 그 외에는 비워둡니다.</p>
</div></section>'''


def _chart_cell(title: str, legend: str) -> str:
    svg = f'''<svg class="t-chart-svg" data-t-chart-svg viewBox="0 0 400 180" role="img" aria-label="{escape(title)} -- 검증된 데이터가 없어 좌표축만 표시합니다">
<line class="t-chart-axis" x1="34" y1="10" x2="34" y2="150"/>
<line class="t-chart-axis" x1="34" y1="150" x2="390" y2="150"/>
{"".join(f'<line class="t-chart-grid" x1="34" y1="{10+i*28}" x2="390" y2="{10+i*28}"/>' for i in range(1, 5))}
{"".join(f'<line class="t-chart-grid" x1="{34+i*51}" y1="10" x2="{34+i*51}" y2="150"/>' for i in range(1, 7))}
<g data-t-tooltip-anchor></g>
</svg>'''
    # legend is built from a fixed, code-controlled set of strings (never
    # user input) and intentionally carries a pre-escaped &middot; entity,
    # so it is inserted verbatim -- escaping it again would show the
    # literal text "&middot;" instead of a rendered middle dot.
    return f'''<div class="t-chart-cell"><div class="t-chart-cell__head"><span class="t-chart-cell__title">{escape(title)}</span>
<span class="t-badge t-badge--validating">VALIDATING</span></div>
<div class="t-chart-legend">{legend}</div>
<div class="t-chart-cell__body">{svg}
<div class="t-chart-empty"><span class="t-chart-empty__badge">데이터 검증 후 공개</span></div>
</div></div>'''


def render_analytics_grid() -> str:
    cells = [
        _chart_cell("NEO Performance Race", "X: TOURNAMENT SEQUENCE &middot; Y: NEO PERFORMANCE"),
        _chart_cell("SG Distribution", "OTT &middot; APP &middot; ARG &middot; PUTT"),
        _chart_cell("K-RANK vs NEO", "X: K-RANK &middot; Y: NEO RANK"),
        _chart_cell("Form / Volatility", "FORM &middot; VOLATILITY"),
    ]
    # the first cell carries the decorative pulse dot referenced in the
    # "signature visualization" section -- purely structural, no data.
    cells[0] = cells[0].replace(
        '<g data-t-tooltip-anchor></g>',
        '<g data-t-tooltip-anchor></g><circle class="t-chart-pulse" cx="212" cy="80" r="4" fill="#147a4d"/>'
    )
    return f'''<section class="t-section" aria-labelledby="analytics-heading"><div class="t-wrap">
<div class="t-section__head"><h2 class="t-section__title" id="analytics-heading">Analytics Grid</h2></div>
<div class="t-grid2">{cells[0]}{cells[1]}</div>
<div class="t-grid2" style="margin-top:14px;">{cells[2]}{cells[3]}</div>
</div></section>'''


_BADGE_CLASS = {"VERIFIED": "t-badge--verified", "VALIDATING": "t-badge--validating", "NOT PUBLISHED": "t-badge--not-published"}


def render_model_validation_panel(mode: str = "home") -> str:
    """REVIEW PATCH (post-f51c323): HOME shows ONLY the six short public
    states (name + badge) -- no research-grade description text, per the
    independent review ("engineering/research details... belong in NEO
    LAB / methodology evidence, not the HOME terminal"). Each HOME row
    links to its NEO LAB evidence anchor (evidence-link architecture, so
    a future methodology/audit source can be attached per row without
    restructuring this table again). NEO LAB mode renders the same six
    rows WITH their full evidence paragraph and a matching id="..." so
    the HOME link resolves to the right place."""
    if mode == "home":
        rows = "".join(
            f'<tr id="{_validation_anchor(name)}-home"><td>{escape(name)} '
            f'<a href="/neo-lab/#{_validation_anchor(name)}" class="t-section__meta">근거 &#8594;</a></td>'
            f'<td><span class="t-badge {_BADGE_CLASS[status]}">{escape(status)}</span></td></tr>'
            for name, status, _evidence in VALIDATION_ROWS
        )
    else:
        rows = "".join(
            f'<tr id="{_validation_anchor(name)}"><td>{escape(name)}'
            f'<span class="t-validation-desc">{escape(evidence)}</span></td>'
            f'<td><span class="t-badge {_BADGE_CLASS[status]}">{escape(status)}</span></td></tr>'
            for name, status, evidence in VALIDATION_ROWS
        )
    return f'''<section class="t-section" aria-labelledby="validation-heading"><div class="t-wrap">
<div class="t-section__head"><h2 class="t-section__title" id="validation-heading">Model Validation</h2></div>
<table class="t-validation-table">{rows}</table>
</div></section>'''


def render_tournaments_strip() -> str:
    return '''<section class="t-section t-section--tight" aria-labelledby="tournaments-heading"><div class="t-wrap">
<div class="t-section__head"><h2 class="t-section__title" id="tournaments-heading">Tournaments</h2>
<a href="/tournaments/" class="t-section__meta">ALL TOURNAMENTS &#8594;</a></div>
<table class="t-validation-table">
<tr><td>제15회 KG 레이디스 오픈<span class="t-validation-desc">2026.08.27&ndash;8.30 &middot; 우승 신다인 &middot; 271 (-17)</span></td>
<td><a href="/tournaments/2026/kg-ladies-open/final/" class="t-section__meta">FINAL &#8594;</a></td></tr>
<tr><td>OK저축은행 읏맨 오픈<span class="t-validation-desc">2026.09.04&ndash;09.06 &middot; 포천아도니스 &middot; 54홀 스트로크 플레이</span></td>
<td><a href="/tournaments/2026/ok-savings-bank-open/pre/" class="t-section__meta">PRE &#8594;</a></td></tr>
</table></div></section>'''


def render_player_inspector() -> str:
    def group(title, rows):
        body = "".join(f'<div class="t-inspector__row"><span>{escape(k)}</span><span class="t-dash">{DASH}</span></div>' for k in rows)
        return f'<div class="t-inspector__group"><h4>{escape(title)}</h4>{body}</div>'

    svg = '''<svg viewBox="0 0 300 100" role="img" aria-label="선수 경기력 이력 -- 검증된 데이터 없음">
<line class="t-chart-axis" x1="20" y1="6" x2="20" y2="84"/><line class="t-chart-axis" x1="20" y1="84" x2="290" y2="84"/>
<line class="t-chart-grid" x1="20" y1="45" x2="290" y2="45"/>
</svg>'''
    return f'''<div class="t-scrim" data-t-scrim></div>
<aside class="t-inspector" data-t-inspector aria-hidden="true" aria-label="선수 성과 검사기">
<div class="t-inspector__head"><div><p class="t-inspector__title">Player Performance</p>
<h3 class="t-inspector__name" data-t-inspector-name>&nbsp;</h3></div>
<button type="button" class="t-inspector__close" data-t-inspector-close aria-label="닫기">&times;</button></div>
<div class="t-inspector__row"><span>K-RANK</span><span data-t-inspector-krank>{DASH}</span></div>
<div class="t-inspector__row"><span>NEO RANK</span><span class="t-dash">{DASH}</span></div>
{group("Performance", ["SG TOTAL", "SG OTT", "SG APP", "SG ARG", "SG PUTT"])}
{group("Form Window", ["SHORT", "MID", "LONG"])}
{group("Probability", ["CUT", "TOP20", "TOP10", "TOP5", "WIN"])}
<div class="t-inspector__group"><h4>Performance History</h4><div class="t-inspector__chart">{svg}</div>
<p class="t-inspector__footnote">데이터 검증 후 공개</p></div>
</aside>'''


def render_footer() -> str:
    return '''<footer class="t-footer"><div class="t-wrap">
<p><strong>NEO GOLF DATA</strong> &middot; 검증되지 않은 숫자는 공개하지 않습니다.</p>
<nav class="t-footer__links" aria-label="바닥글 링크">
<a href="/">PLAYERS</a><a href="/tournaments/">TOURNAMENTS</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">ABOUT</a>
</nav></div></footer>'''


def render_home(rows: list[dict], summary: dict, ranking_snapshot_label: str) -> str:
    views = [_row_view(r) for r in rows]
    return (
        f"{render_head('NEO GOLF DATA · KLPGA PERFORMANCE TERMINAL')}<body class=\"home-v4\">"
        f"{render_terminal_bar('players')}{render_provenance_line()}{render_summary_strip(summary, ranking_snapshot_label)}"
        "<main>"
        f"{render_performance_board(views, summary['population_count'])}"
        f"{render_analytics_grid()}"
        f"{render_model_validation_panel(mode='home')}"
        f"{render_tournaments_strip()}"
        "</main>"
        f"{render_player_inspector()}{render_footer()}</body></html>"
    )


def render_data_coverage_evidence(historical_events: int, ranking_snapshot_label: str) -> str:
    """REVIEW PATCH (post-f51c323): the real archived-event count and its
    full provenance now live here (NEO LAB), not on the public HOME
    summary strip, per the independent review's option (B). This is the
    only place in the whole candidate that states the raw 97 number."""
    return f'''<section class="t-section" aria-labelledby="data-evidence-heading"><div class="t-wrap">
<div class="t-section__head"><h2 class="t-section__title" id="data-evidence-heading">Data Coverage Evidence</h2></div>
<table class="t-validation-table">
<tr><td>NEO PLAYER DATABASE<span class="t-validation-desc">역대 정규투어 선수 마스터(player_master) 기준 546명 · 현재 KLPGA 등록 명부와의 완전 일치는 증명되지 않음</span></td><td></td></tr>
<tr><td>K-RANK SNAPSHOT<span class="t-validation-desc">{escape(ranking_snapshot_label)} 공식 K-Rank 스냅샷(출처: k-rankings.klpga.co.kr) · 546명 중 119명 연결</span></td><td></td></tr>
<tr><td>NEO ARCHIVED EVENTS<span class="t-validation-desc">corrected SG warehouse 기준 {historical_events}개 대회 · 이 수치가 KLPGA 전체 대회 이력을 의미하지는 않으며, 라운드 수 검증(ROUND SEMANTICS)이 완료되지 않아 공개 방법론이 확정될 때까지 HOME에는 표기하지 않음</span></td><td></td></tr>
</table></div></section>'''


def render_neo_lab_page(historical_events: int, ranking_snapshot_label: str) -> str:
    return (
        f"{render_head('NEO LAB · NEO GOLF DATA')}<body class=\"home-v4\">"
        f"{render_terminal_bar('neo-lab')}{render_provenance_line()}"
        '<main><section class="t-section"><div class="t-wrap">'
        '<div class="t-section__head"><h2 class="t-section__title">NEO LAB</h2></div>'
        '<p style="max-width:680px;font-size:13px;line-height:1.7;color:var(--t-text-dim);">'
        "NEO LAB은 NEO Ranking 공식의 설계, 데이터 검증, 라운드 수/결과 검증 리서치를 공개하는 공간입니다. "
        "검증이 끝나지 않은 지표는 어디에서도 공개하지 않으며, 검증 과정 자체를 투명하게 기록합니다.</p>"
        "</div></section>"
        f"{render_model_validation_panel(mode='lab')}"
        f"{render_data_coverage_evidence(historical_events, ranking_snapshot_label)}"
        "</main>" + render_footer() + "</body></html>"
    )


def _copy_preserved_site(output: Path) -> None:
    docs_source = REPO / "docs"
    if not docs_source.is_dir():
        raise FileNotFoundError(f"preserved site source missing: {docs_source}")
    shutil.copytree(docs_source, output, dirs_exist_ok=True)


def build() -> dict:
    population = load_json(CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    ranking = load_json(CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json")
    warehouse = load_json(CONTENT / "historical_sg_warehouse_corrected.json")
    rows, summary = join_home_rows(population, ranking, warehouse)
    rows = sorted(rows, key=lambda r: r["player_name"].casefold())
    historical_events = len({r.get("game_code") for r in warehouse.get("records", ()) if r.get("game_code")})
    # real, dated identity of the one specific official snapshot K-RANK is
    # joined against -- never a vague "official snapshot" label.
    ranking_snapshot_label = f"{ranking.get('ranking_date', DASH)}"

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT, ignore_errors=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    _copy_preserved_site(OUTPUT)

    (OUTPUT / "index.html").write_text(render_home(rows, summary, ranking_snapshot_label), encoding="utf-8", newline="\n")

    neo_lab_dir = OUTPUT / "neo-lab"
    neo_lab_dir.mkdir(parents=True, exist_ok=True)
    (neo_lab_dir / "index.html").write_text(
        render_neo_lab_page(historical_events, ranking_snapshot_label), encoding="utf-8", newline="\n"
    )

    assets = OUTPUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v4.css", assets / "home-v4.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v4.js", assets / "home-v4.js")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", assets / "neo-site.css")

    (OUTPUT / "data").mkdir(exist_ok=True)
    out_summary = dict(summary)
    out_summary["historical_events"] = historical_events
    (OUTPUT / "data" / "home-v4-summary.json").write_text(
        json.dumps(out_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out_summary, ensure_ascii=False))
    print(f"WROTE candidate: {OUTPUT / 'index.html'}")
    return out_summary


if __name__ == "__main__":
    build()
