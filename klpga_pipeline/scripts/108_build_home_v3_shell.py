"""Build the NEO GOLF DATA HOME V3 candidate shell.

CANDIDATE ONLY -- never promoted, merged, or wired into production by this
script. Writes to candidate/home-v3-shell/ under a brand-new branch
(candidate/neo-home-v3-shell), completely separate from the NEO Ranking V2
validation track (scripts 104-107, the SG warehouse, the frozen V1
baseline) -- this script only READS klpga.website_v2.home_ranking (the
existing, already-production, formula-blocked HOME data contract) and
never touches any of those files.

CORE RULE enforced throughout: FAKE DATA = 0. Every cell whose real value
depends on unfinished validation renders the literal em dash "—" -- never
0, N/A, TBD, or an invented number. Sponsor is rendered ONLY when a
verified source provides it (none exists for the full player population
in this repository today, so every sponsor cell is honestly blank -- see
SPONSOR_SOURCE below). Player photos always fall back to a neutral
silhouette icon; no scraping, no AI-generated lookalikes.
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
OUTPUT = ROOT / "candidate" / "home-v3-shell"
DASH = "—"

# No verified, official-KLPGA-profile-sourced sponsor data exists anywhere
# in this repository for the full 546-player regular-tour population (only
# a handful of single-tournament live snapshots carry a sponsor string, and
# those are scoped to one event's field, not this permanent population) --
# confirmed by a repo-wide search for a "sponsor" key before writing this
# script. Per the explicit sponsor rule ("never infer... leave the cell
# BLANK"), SPONSOR_SOURCE stays empty rather than joining a narrow,
# tournament-scoped source that would silently look complete but is not.
SPONSOR_SOURCE: dict[str, str] = {}

_SILHOUETTE_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">'
    '<circle cx="12" cy="8" r="3.4"/><path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7"/></svg>'
)


def _fmt_signed(value) -> str:
    if value is None:
        return DASH
    return f"{value:+.2f}"


def _fmt_plain(value, decimals=2) -> str:
    if value is None:
        return DASH
    return f"{value:.{decimals}f}"


def _row_view(row: dict) -> dict:
    """Reduce one home_ranking row to exactly what the V3 templates need,
    with every unresolved field defaulting to the DASH -- never 0/N/A/TBD."""
    feature = row.get("features") or {}
    player_id = row["player_id"]
    k_rank = row.get("k_rank")
    recent5 = feature.get("recent_5_sg")
    recent10 = feature.get("recent_10_sg")
    long_term = feature.get("long_term_sg")
    volatility = feature.get("volatility")
    sample_count = feature.get("sample_count")
    return {
        "player_id": player_id,
        "player_name": row["player_name"],
        "sponsor": SPONSOR_SOURCE.get(player_id, ""),  # verified-only; blank otherwise, never inferred
        "k_rank": k_rank,
        "k_rank_display": str(k_rank) if k_rank is not None else DASH,
        "performance_sg_display": _fmt_signed(long_term) if long_term is not None else DASH,
        "performance_sg_title": (
            f"최근 5개 {_fmt_signed(recent5)} · 최근 10개 {_fmt_signed(recent10)} · "
            f"장기 {_fmt_signed(long_term)} · 표본 {sample_count}개"
        ) if feature else "검증 대기 · SG warehouse 매칭 없음",
        "recent_form_display": _fmt_signed(recent5),
        "recent_form_raw": recent5,
        "volatility_display": _fmt_plain(volatility) if feature else DASH,
        "trend_display": DASH,  # no verified period-over-period trend source exists yet
        "events_display": str(sample_count) if sample_count is not None else DASH,
        "photo_license_status": "UNVERIFIED",  # always -- no photo pipeline exists; silhouette only
    }


def render_head(title: str) -> str:
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title>"
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="/assets/home-v3.css">'
        '<script src="/assets/home-v3.js" defer></script></head>'
    )


NAV_ITEMS = (("players", "PLAYERS", "/"), ("tournaments", "TOURNAMENTS", "/tournaments/"),
             ("neo-lab", "NEO LAB", "/neo-lab/"), ("about", "ABOUT", "/about/"))


def render_header(active: str) -> str:
    links = []
    for key, label, url in NAV_ITEMS:
        cls = ' class="is-active" aria-current="page"' if key == active else ""
        links.append(f'<a href="{url}"{cls}>{label}</a>')
    return (
        '<header class="v3-header"><div class="v3-header__inner">'
        '<a class="v3-brand" href="/">NEO GOLF DATA<small>Measure Performance</small></a>'
        '<button type="button" class="v3-nav-toggle" data-v3-nav-toggle aria-expanded="false" '
        'aria-controls="v3-primary-nav" aria-label="메뉴 열기">&#9776;</button>'
        f'<nav class="v3-nav" id="v3-primary-nav" data-v3-nav aria-label="주요 메뉴">{"".join(links)}</nav>'
        "</div></header>"
    )


def render_hero() -> str:
    return (
        '<section class="v3-hero"><div class="v3-container">'
        '<p class="v3-hero__eyebrow">NEO GOLF DATA</p>'
        "<h1>순위 너머의 경기력을 측정하다.</h1>"
        '<p class="v3-hero__sub">MEASURE PERFORMANCE. NOT RESULTS.</p>'
        '<p class="v3-hero__body">NEO GOLF DATA는 결과 순위만이 아니라 '
        "선수가 실제로 보여준 경기력을 측정하고 비교한다.</p>"
        "</div></section>"
    )


def render_provenance_bar() -> str:
    items = [
        ("DATA SOURCE", "KLPGA Official Data"),
        ("UPDATE", "라운드 종료 후 업데이트"),
        ("VALIDATION", "NEO 검증 시스템"),
    ]
    body = "".join(f'<span class="v3-provenance__item"><b>{escape(k)}</b><span>{escape(v)}</span></span>' for k, v in items)
    return f'<div class="v3-provenance"><div class="v3-provenance__inner">{body}</div></div>'


def _avatar_html() -> str:
    return f'<span class="v3-avatar" aria-hidden="true">{_SILHOUETTE_SVG}</span>'


def render_ranking_table(views: list[dict]) -> str:
    head = (
        "<thead><tr>"
        '<th scope="col">NEO RANK</th><th scope="col" class="v3-col-player">선수</th>'
        '<th scope="col">스폰서</th><th scope="col">K-RANK</th>'
        '<th scope="col">PERFORMANCE SG</th><th scope="col">RECENT FORM</th>'
        '<th scope="col">VOLATILITY</th><th scope="col">TREND</th><th scope="col">EVENTS</th>'
        "</tr></thead>"
    )
    body_rows = []
    for v in views:
        body_rows.append(
            f'<tr data-player-row data-player-name="{escape(v["player_name"].casefold())}" '
            f'data-k-rank="{v["k_rank"] if v["k_rank"] is not None else 999999}" '
            f'data-recent-sg="{v["recent_form_raw"] if v["recent_form_raw"] is not None else ""}">'
            f'<td><span class="v3-pending">{DASH}</span></td>'
            f'<th scope="row"><span class="v3-player-cell">{_avatar_html()}{escape(v["player_name"])}</span></th>'
            f'<td class="v3-sponsor-cell">{escape(v["sponsor"])}</td>'
            f'<td>{escape(v["k_rank_display"])}</td>'
            f'<td class="v3-metric" title="{escape(v["performance_sg_title"])}">{escape(v["performance_sg_display"])}</td>'
            f'<td class="v3-metric">{escape(v["recent_form_display"])}</td>'
            f'<td class="v3-metric">{escape(v["volatility_display"])}</td>'
            f'<td><span class="v3-trend-chip">{escape(v["trend_display"])}</span></td>'
            f'<td class="v3-metric">{escape(v["events_display"])}</td>'
            "</tr>"
        )
    return f'<table class="v3-rank-table">{head}<tbody data-v3-rank-body>{"".join(body_rows)}</tbody></table>'


def render_ranking_cards(views: list[dict]) -> str:
    cards = []
    for v in views:
        cards.append(
            f'<div class="v3-rank-card" data-player-row data-player-name="{escape(v["player_name"].casefold())}" '
            f'data-k-rank="{v["k_rank"] if v["k_rank"] is not None else 999999}" '
            f'data-recent-sg="{v["recent_form_raw"] if v["recent_form_raw"] is not None else ""}">'
            f'<span class="v3-rank-card__rank">{DASH}</span>'
            f'<span><span class="v3-rank-card__name">{escape(v["player_name"])}</span>'
            f'<div class="v3-rank-card__meta">K-RANK {escape(v["k_rank_display"])}'
            f'{" · " + escape(v["sponsor"]) if v["sponsor"] else ""}</div></span>'
            f'<span class="v3-rank-card__sg">{escape(v["performance_sg_display"])}</span>'
            '<span class="v3-rank-card__more">'
            f'<span>RECENT <b>{escape(v["recent_form_display"])}</b></span>'
            f'<span>VOL <b>{escape(v["volatility_display"])}</b></span>'
            f'<span>TREND <b>{escape(v["trend_display"])}</b></span>'
            f'<span>EVENTS <b>{escape(v["events_display"])}</b></span>'
            "</span></div>"
        )
    return f'<div class="v3-rank-cards" data-v3-rank-cards>{"".join(cards)}</div>'


def render_ranking_section(rows: list[dict], summary: dict) -> str:
    views = [_row_view(r) for r in rows]
    return f'''<section class="v3-section" id="neo-ranking" aria-labelledby="v3-ranking-heading"><div class="v3-container">
<div class="v3-section__head"><div><p class="v3-section__label">NEO RANKING</p>
<h2 id="v3-ranking-heading">전체 선수</h2></div>
<span class="v3-status-chip">NEO Ranking · 데이터 검증 중</span></div>
<div class="v3-toolbar">
<label for="v3-player-search">선수 검색</label>
<input id="v3-player-search" type="search" placeholder="선수명 입력" autocomplete="off">
<label for="v3-sort">정렬</label>
<select id="v3-sort"><option value="neo">선수명</option><option value="k-rank">K-Ranking</option><option value="recent-sg">Recent SG</option></select>
<output id="v3-visible-count">{summary["population_count"]}명</output>
</div>
<div class="v3-table-scroll v3-desktop-only">{render_ranking_table(views)}</div>
{render_ranking_cards(views)}
<p class="note" style="font-size:12px;color:var(--v3-gray-500);margin-top:14px;">NEO RANK는 공식이 검증되기 전까지 발행하지 않습니다. 스폰서는 KLPGA 공식 프로필에서 확인된 경우에만 표기하며, 확인되지 않은 경우 비워둡니다.</p>
</div></section>'''


def render_performance_race_section() -> str:
    svg = '''<svg class="v3-race-svg" data-v3-race-svg viewBox="0 0 720 260" role="img" aria-label="NEO Performance Race -- 검증된 데이터가 없어 빈 좌표축만 표시합니다">
<line class="v3-race-axis" x1="56" y1="20" x2="56" y2="220"/>
<line class="v3-race-axis" x1="56" y1="220" x2="700" y2="220"/>
{grid}
<text class="v3-race-axis-title" x="56" y="242">TOURNAMENT SEQUENCE / TIME &#8594;</text>
<text class="v3-race-axis-title" x="20" y="16" transform="rotate(-90 20 16)" text-anchor="end">NEO PERFORMANCE (SG-R)</text>
<circle class="v3-race-pulse" cx="378" cy="120" r="5" fill="#146c48"/>
</svg>'''
    grid_lines = []
    for i in range(1, 6):
        y = 20 + i * 33
        grid_lines.append(f'<line class="v3-race-grid" x1="56" y1="{y}" x2="700" y2="{y}"/>')
    for i in range(1, 8):
        x = 56 + i * 82
        grid_lines.append(f'<line class="v3-race-grid" x1="{x}" y1="20" x2="{x}" y2="220"/>')
    svg = svg.replace("{grid}", "".join(grid_lines))
    return f'''<section class="v3-section" aria-labelledby="v3-race-heading"><div class="v3-container">
<div class="v3-section__head"><div><p class="v3-section__label">NEO PERFORMANCE RACE</p>
<h2 id="v3-race-heading">선수 경기력 추이</h2></div>
<span class="v3-status-chip">데이터 검증 후 공개</span></div>
<div class="v3-race-shell">{svg}
<div class="v3-race-empty"><span class="v3-race-empty__badge">검증된 경기력 시계열이 없습니다 · 데이터 검증 후 공개</span></div>
</div>
<p class="note" style="font-size:12px;color:var(--v3-gray-500);margin-top:10px;">X축은 대회 순서/시간, Y축은 NEO Performance(SG-R)입니다. 검증되지 않은 선수 경기력 곡선은 그리지 않습니다.</p>
</div></section>'''


def render_tournaments_section() -> str:
    return '''<section class="v3-section" aria-labelledby="v3-tournaments-heading"><div class="v3-container">
<div class="v3-section__head"><div><p class="v3-section__label">TOURNAMENTS</p>
<h2 id="v3-tournaments-heading">대회</h2></div><a class="v3-card__link" href="/tournaments/">모든 대회 보기 &#8594;</a></div>
<div class="v3-tournament-row"><div><span class="v3-status-chip">종료</span><h4>제15회 KG 레이디스 오픈</h4>
<small>2026.08.27&ndash;8.30 &middot; 우승 신다인 &middot; 271 (-17)</small></div>
<a class="v3-card__link" href="/tournaments/2026/kg-ladies-open/final/">예측 기록 보기 &#8594;</a></div>
<div class="v3-tournament-row"><div><span class="v3-status-chip">예정</span><h4>OK저축은행 읏맨 오픈</h4>
<small>2026.09.04&ndash;09.06 &middot; 포천아도니스 &middot; 54홀 스트로크 플레이</small></div>
<a class="v3-card__link" href="/tournaments/2026/ok-savings-bank-open/pre/">사전 분석 보기 &#8594;</a></div>
</div></section>'''


def render_insights_section() -> str:
    return '''<section class="v3-section" aria-labelledby="v3-insights-heading"><div class="v3-container">
<div class="v3-section__head"><div><p class="v3-section__label">LATEST INSIGHTS</p>
<h2 id="v3-insights-heading">최신 인사이트</h2></div></div>
<div class="v3-grid">
<div class="v3-insight-card"><p class="v3-insight-kicker">준비 중</p><p class="v3-insight-empty">검증된 인사이트가 준비되면 이곳에 게시됩니다.</p></div>
<div class="v3-insight-card"><p class="v3-insight-kicker">준비 중</p><p class="v3-insight-empty">검증된 인사이트가 준비되면 이곳에 게시됩니다.</p></div>
<div class="v3-insight-card"><p class="v3-insight-kicker">준비 중</p><p class="v3-insight-empty">검증된 인사이트가 준비되면 이곳에 게시됩니다.</p></div>
</div></div></section>'''


def render_neo_lab_teaser() -> str:
    return '''<section class="v3-section" aria-labelledby="v3-lab-heading"><div class="v3-container">
<div class="v3-section__head"><div><p class="v3-section__label">NEO LAB</p>
<h2 id="v3-lab-heading">NEO 방법론 &amp; 검증</h2></div><a class="v3-card__link" href="/neo-lab/">NEO LAB 자세히 보기 &#8594;</a></div>
<div class="v3-card"><p>NEO LAB은 NEO Ranking의 방법론, 데이터 검증 절차, 연구 노트를 다루는 공간입니다. 공식이 검증되기 전까지 순위 수치는 공개하지 않으며, 검증 과정 자체를 투명하게 기록합니다.</p>
<a class="v3-card__link" href="/neo-lab/">방법론 보기 &#8594;</a></div>
</div></section>'''


def render_footer() -> str:
    return '''<footer class="v3-footer"><div class="v3-container">
<p><strong>NEO GOLF DATA</strong> &middot; 검증되지 않은 숫자는 공개하지 않습니다.</p>
<nav class="v3-footer__links" aria-label="바닥글 링크">
<a href="/">PLAYERS</a><a href="/tournaments/">TOURNAMENTS</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">ABOUT</a>
</nav></div></footer>'''


def render_home(rows: list[dict], summary: dict) -> str:
    return (
        f"{render_head('NEO GOLF DATA · 순위 너머의 경기력을 측정하다')}<body class=\"home-v3\">"
        f"{render_header('players')}<main>"
        f"{render_hero()}{render_provenance_bar()}"
        f"{render_ranking_section(rows, summary)}"
        f"{render_performance_race_section()}"
        f"{render_tournaments_section()}"
        f"{render_insights_section()}"
        f"{render_neo_lab_teaser()}"
        f"</main>{render_footer()}</body></html>"
    )


def render_neo_lab_page() -> str:
    return (
        f"{render_head('NEO LAB · NEO GOLF DATA')}<body class=\"home-v3\">"
        f"{render_header('neo-lab')}<main>"
        '<section class="v3-hero"><div class="v3-container">'
        '<p class="v3-hero__eyebrow">NEO LAB</p>'
        "<h1>NEO 방법론과 검증 과정</h1>"
        '<p class="v3-hero__body">NEO LAB은 NEO Ranking 공식의 설계, 데이터 검증, 리서치 과정을 '
        "공개하는 공간입니다. 검증이 끝나지 않은 수치는 이곳에서도 발표하지 않습니다.</p>"
        "</div></section>"
        '<section class="v3-section"><div class="v3-container"><div class="v3-grid">'
        '<div class="v3-card"><h3>방법론</h3><p>NEO Performance는 결과(순위)가 아니라 '
        "선수가 실제로 만들어낸 경기력(Strokes Gained 기반 지표)을 측정하는 것을 목표로 합니다.</p></div>"
        '<div class="v3-card"><h3>데이터 검증</h3><p>NEO Ranking 공식은 라운드 수 검증, '
        "컷/기권/실격 처리, 표본 크기 등 여러 단계의 내부 검증을 통과해야 공개됩니다.</p></div>"
        '<div class="v3-card"><h3>공개 원칙</h3><p>검증되지 않은 숫자는 절대 발표하지 않습니다. '
        "확인되지 않은 값은 항상 &mdash;로 표기합니다.</p></div>"
        "</div></div></section></main>" + render_footer() + "</body></html>"
    )


def _copy_preserved_site(output: Path) -> None:
    """Bring in the full, already-live/verified site tree (docs/) so every
    existing route -- /tournaments/, /ranking/, /deep-dive/, /about/,
    /protected/ and all historical tournament stage pages -- stays
    reachable inside this candidate preview. Nothing here is generated or
    altered; it is a byte-for-byte copy of already-published content,
    exactly the pattern scripts/86_build_neo_data_home_candidate.py
    already uses for the same purpose."""
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

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT, ignore_errors=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    _copy_preserved_site(OUTPUT)

    (OUTPUT / "index.html").write_text(render_home(rows, summary), encoding="utf-8", newline="\n")

    neo_lab_dir = OUTPUT / "neo-lab"
    neo_lab_dir.mkdir(parents=True, exist_ok=True)
    (neo_lab_dir / "index.html").write_text(render_neo_lab_page(), encoding="utf-8", newline="\n")

    assets = OUTPUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v3.css", assets / "home-v3.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "home-v3.js", assets / "home-v3.js")
    # neo-site.css already ships with the preserved docs/ copy above --
    # re-copy defensively so the V3 pages never depend on it having been
    # present in that snapshot.
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", assets / "neo-site.css")

    (OUTPUT / "data").mkdir(exist_ok=True)
    (OUTPUT / "data" / "home-v3-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    print(f"WROTE candidate: {OUTPUT / 'index.html'}")
    return summary


if __name__ == "__main__":
    build()
