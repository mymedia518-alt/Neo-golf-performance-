"""Build docs/tournaments/index.html (real archive index, replacing the
"공사중" placeholder), docs/tournaments/2026/2026100004/index.html (new
HJ중공업·동부건설 scaffold, prediction-locked), and rebuild docs/index.html
(root HOME, current-tournament-v1 owner) to point at HJ as the current
tournament.

Ground truth for "what stages really exist" per archive tournament comes
from the actual directory listing on disk, NOT from any one page's
embedded stage-nav (those are point-in-time snapshots and go stale -- KB's
own pre/ page, for example, predates its own fr/ and final/ pages).

Does not touch any file under docs/tournaments/2026/{2026090002,2026090003,
2026100005,ok-savings-bank-open,kg-ladies-open}/ -- those stay byte-identical.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOURNAMENTS_DIR = ROOT / "docs" / "tournaments" / "2026"
CONTENT = ROOT / "klpga_pipeline" / "content" / "website_v2"
HJ_GAME_CODE = "2026100004"

STAGE_LABELS = {
    "pre": "사전 분석",
    "r1": "R1",
    "r2": "R2",
    "r3": "R3",
    "fr": "FR",
    "final": "FINAL",
    "verification": "최종 검증",
    "course-analysis": "코스 분석",
    "deep-dive": "딥 다이브",
}
STAGE_ORDER = ["pre", "r1", "r2", "r3", "fr", "final", "verification", "course-analysis", "deep-dive"]


NOT_YET_MARKERS = ("NEO GOLF DATA - 공사중", "아직 시작 전", "공식 FINAL 데이터가 아직 없습니다")
# a page can carry real-looking content but still be explicitly self-flagged
# as not meant for public exposure yet -- found on 2026100005/deep-dive/
# (neo-stage-publication-ready=false, neo-mock-data=true) while every other
# page carrying the same meta tag says ready=true with no mock flag. Treat
# this as authoritative: never link to a page that says it isn't ready.
NOT_PUBLICATION_READY_MARKERS = ('neo-stage-publication-ready" content="false"', 'neo-mock-data" content="true"')

# PUBLIC_STAGE_ALLOWLIST: an explicit, hand-curated editorial decision about
# which real, publication-ready stages are actually shown on the public
# archive -- separate from auto-discovery (real_stages below), which only
# proves a stage exists on disk and isn't a stub/mock. A stage can be 100%
# real and ready and still not belong in the public archive navigation (e.g.
# 2026100005's "최종 검증"/"코스 분석" -- internal validation/analysis pages
# NEO chose to keep off the public click-through path). When a tournament
# has an entry here, its public stages are real_stages() INTERSECTED with
# this allowlist -- so even if a future rebuild's auto-discovery would
# otherwise re-surface a newly-"ready" verification/course-analysis page,
# it stays hidden unless this allowlist is explicitly edited to include it.
# A tournament absent from this dict falls back to showing all real_stages().
PUBLIC_STAGE_ALLOWLIST: dict[str, set[str]] = {
    "2026100005": {"pre", "r1", "r2", "r3", "fr"},  # excludes: 최종 검증(verification), 코스 분석(course-analysis)
}


def real_stages(dirname: str) -> list[str]:
    """Stages that exist on disk AND actually carry real, publication-ready
    NEO analysis -- excludes the generic '공사중' construction stub, a stage
    that exists as a file but explicitly says its real content was never
    produced (e.g. a FINAL page that says "아직 시작 전"), and any page
    that self-flags as not publication-ready / mock data. Does NOT yet apply
    PUBLIC_STAGE_ALLOWLIST -- see public_stages() for the editorially-curated
    subset actually shown in navigation."""
    tdir = TOURNAMENTS_DIR / dirname
    out = []
    for stage in STAGE_ORDER:
        f = tdir / stage / "index.html"
        if not f.exists():
            continue
        html = f.read_text(encoding="utf-8")
        if any(marker in html for marker in NOT_YET_MARKERS):
            continue
        if any(marker in html for marker in NOT_PUBLICATION_READY_MARKERS):
            continue
        out.append(stage)
    return out


def public_stages(dirname: str) -> list[str]:
    """The stages actually shown in public navigation: real_stages(),
    narrowed by PUBLIC_STAGE_ALLOWLIST when the tournament has one. This is
    the function the archive builder must call -- real_stages() alone is
    only a 'does this exist and look real' check, not an editorial publish
    decision."""
    discovered = real_stages(dirname)
    allowlist = PUBLIC_STAGE_ALLOWLIST.get(dirname)
    if allowlist is None:
        return discovered
    return [s for s in discovered if s in allowlist]


ARCHIVE_TOURNAMENTS = [
    # (dirname, display_name, date_range, venue, primary_stage_for_card_name_link)
    ("2026100005", "제26회 하이트진로 챔피언십", "2026.10.01 — 10.04", "블루헤런", "fr"),
    ("2026090002", "하나금융그룹 챔피언십", "2026.09.17 — 09.20", "더헤븐", "final"),
    ("2026090003", "KB금융 골든라이프 챔피언십", "2026.09.10 — 09.13", "블랙스톤 이천", "final"),
    ("ok-savings-bank-open", "OK저축은행 읏맨 오픈", "2026.09.04 — 09.06", "포천아도니스", "r3"),
    ("kg-ladies-open", "제15회 KG 레이디스 오픈", "2026.08.27 — 08.30", "써닝포인트", "final"),
]

GLOBAL_HEAD_LINKS = (
    '<link rel="stylesheet" href="/assets/neo-site.css">'
    '<link rel="stylesheet" href="/assets/neo.css">'
)


def global_header(active: str) -> str:
    """active: 'home' | 'current' | 'archive' | other (no is-active match)."""
    def item(href, label, key):
        cur = ' class="is-active" aria-current="page"' if key == active else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    nav = "".join([
        item("/", "홈", "home"),
        item("/tournaments/2026/2026100004/", "현재 대회", "current"),
        item("/tournaments/", "대회 기록", "archive"),
        item("/ranking/", "랭킹", "other"),
        item("/deep-dive/", "딥다이브", "other"),
        item("/neo-lab/", "NEO LAB", "other"),
        item("/about/", "소개", "other"),
    ])
    return (
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/">'
        '<span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend">'
        '<span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span>'
        '</span></a>'
        f'<nav class="neo-global-nav" aria-label="주요 메뉴">{nav}</nav>'
        '</div></header>'
    )


FOOTER = '<footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer>'


def breadcrumb(*crumbs):
    """crumbs: list of (label, href_or_None). Last one has no href (current page)."""
    parts = []
    for i, (label, href) in enumerate(crumbs):
        if i:
            parts.append('<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>')
        if href:
            parts.append(f'<a href="{href}">{label}</a>')
        else:
            parts.append(f'<span aria-current="page">{label}</span>')
    return f'<nav class="breadcrumb" aria-label="현재 위치">{"".join(parts)}</nav>'


# ---------------------------------------------------------------- archive index
def build_archive_index() -> str:
    cards = []
    for dirname, name, dates, venue, primary_stage in ARCHIVE_TOURNAMENTS:
        stages = public_stages(dirname)
        if primary_stage and primary_stage in stages:
            name_html = f'<h2><a href="/tournaments/2026/{dirname}/{primary_stage}/">{name}</a></h2>'
        else:
            name_html = f'<h2>{name}</h2>'
        if stages:
            links = "".join(
                f'<a href="/tournaments/2026/{dirname}/{s}/">{STAGE_LABELS[s]}</a>'
                for s in stages
            )
            stage_html = f'<div class="stage-links">{links}</div>'
        else:
            stage_html = '<p class="unavailable">실제 기록 준비 중 — 아직 공개된 NEO 분석이 없습니다.</p>'
        cards.append(
            f'<article class="archive-card" data-tournament-archive-card data-game-code="{dirname}">'
            f'{name_html}'
            f'<p class="tournament-context__meta">{dates} · {venue}</p>'
            f'{stage_html}'
            f'</article>'
        )
    cards_html = "\n".join(cards)

    head = (
        "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>NEO GOLF DATA · 대회 기록</title>"
        "<meta name=\"description\" content=\"NEO GOLF DATA가 분석한 모든 KLPGA 대회 기록 — 사전 분석부터 최종 결과까지 다시 볼 수 있습니다.\">"
        "<link rel=\"canonical\" href=\"https://neogolfdata.com/tournaments/\">"
        f"{GLOBAL_HEAD_LINKS}</head>"
    )
    body = (
        "<body>"
        + global_header("archive")
        + "<main>"
        + breadcrumb(("홈", "/"), ("대회 기록", None))
        + '<section class="page-intro"><h1>대회 기록</h1>'
        + '<p>NEO가 분석했던 모든 대회를 언제든 다시 꺼내 볼 수 있습니다. 대회명을 선택하면 사전 분석부터 최종 결과까지, 당시 NEO가 만든 기록을 그대로 다시 볼 수 있습니다.</p></section>'
        + f'<section aria-label="대회 목록">{cards_html}</section>'
        + "</main>"
        + FOOTER
        + "</body>"
    )
    return f"<!doctype html><html lang=\"ko\">{head}{body}</html>"


# ---------------------------------------------------------------- HJ scaffold (2026100004)
def build_hj_scaffold() -> str:
    head = (
        "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>NEO GOLF DATA · HJ중공업·동부건설 챔피언십</title>"
        "<meta name=\"description\" content=\"HJ중공업·동부건설 챔피언십 — NEO GOLF DATA 현재 대회. 변형 스테이블포드 방식으로 진행되며, 경기 방식에 맞춘 NEO 분석은 준비되는 대로 공개합니다.\">"
        "<link rel=\"canonical\" href=\"https://neogolfdata.com/tournaments/2026/2026100004/\">"
        f"{GLOBAL_HEAD_LINKS}</head>"
    )
    body = (
        "<body>"
        + global_header("current")
        + "<main>"
        + breadcrumb(("홈", "/"), ("대회 기록", "/tournaments/"), ("HJ중공업·동부건설 챔피언십", None))
        + '<div class="tournament-context"><h1>HJ중공업·동부건설 챔피언십</h1>'
        + '<p class="tournament-context__meta">NEO GOLF DATA 현재 대회</p></div>'
        + '<div class="fixture-notice">이번 대회는 변형 스테이블포드 방식으로 진행됩니다. '
        + '경기 방식에 맞춘 NEO 분석은 준비되는 대로 공개합니다.</div>'
        + '<section class="page-intro"><p>대회가 진행되면 이 페이지를 통해 NEO의 실제 분석(사전 분석, 라운드별 결과 등)을 확인할 수 있습니다. 아직 공개된 분석은 없습니다.</p></section>'
        + "</main>"
        + FOOTER
        + "</body>"
    )
    return f"<!doctype html><html lang=\"ko\">{head}{body}</html>"


# ---------------------------------------------------------------- HOME (root)
def _hj_top5_preview_html() -> str:
    """Top-5 Stableford 사전평가 preview, rendered live from the frozen
    V1 snapshot -- never hardcoded names/ranks. Falls back to no
    preview block (not a placeholder) if the snapshot is ever absent."""
    snapshot_path = CONTENT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"
    if not snapshot_path.is_file():
        return ""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("target_game_code") != HJ_GAME_CODE:
        return ""
    ranked = sorted(
        (r for r in snapshot["records"] if r["pre_event_rank"] is not None),
        key=lambda r: r["pre_event_rank"],
    )[:5]
    if not ranked:
        return ""
    items = "".join(
        f"<li style='padding:.4rem 0;border-bottom:1px solid var(--line)'><strong>#{r['pre_event_rank']}</strong> {r['player_name']}"
        f"<span style='color:var(--muted);font-size:.82rem'> {r.get('official_sponsor') or ''}</span></li>"
        for r in ranked
    )
    return (
        '<section class="page-intro"><h2>Stableford 사전평가 TOP 5</h2>'
        f'<ol style="list-style:none;margin:0;padding:0;max-width:28rem">{items}</ol>'
        f'<p><a href="/tournaments/2026/{HJ_GAME_CODE}/pre/">전체 {snapshot["field_size"]}명 보기 →</a></p></section>'
    )


def build_home() -> str:
    head = (
        "<head><meta name=\"neo-home-owner\" content=\"current-tournament-v1\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>NEO GOLF DATA · HJ중공업·동부건설 챔피언십</title>"
        "<meta name=\"description\" content=\"HJ중공업·동부건설 챔피언십 · 같은 경기력도 Stableford에서는 가치가 달라진다 · NEO GOLF DATA\">"
        "<link rel=\"canonical\" href=\"https://neogolfdata.com/\">"
        "<meta property=\"og:title\" content=\"NEO GOLF DATA\">"
        "<meta property=\"og:description\" content=\"HJ중공업·동부건설 챔피언십 · 같은 경기력도 Stableford에서는 가치가 달라진다\">"
        "<meta property=\"og:url\" content=\"https://neogolfdata.com/\">"
        "<meta property=\"og:type\" content=\"website\">"
        "<meta name=\"twitter:card\" content=\"summary_large_image\">"
        f"{GLOBAL_HEAD_LINKS}</head>"
    )
    body = (
        "<body>"
        + global_header("home")
        + "<main>"
        + breadcrumb(("홈", None))
        + '<section class="hero" id="tournament"><div><p class="eyebrow">현재 대회</p>'
        + '<h1>HJ중공업·동부건설 챔피언십</h1>'
        + '<p class="meta">같은 경기력도 Stableford에서는 가치가 달라진다.</p></div></section>'
        + '<div class="fixture-notice">'
        + '<strong>이번 대회는 변형 스테이블포드 방식으로 진행됩니다.</strong> '
        + '버디 +2, 이글 +5, 보기 -1, 더블보기 이상 -3. '
        + 'NEO는 선수들의 대회 전 기록을 이 점수제에 다시 대입해 '
        + '이번 대회에서 어떤 선수의 경기 스타일이 더 높은 가치를 갖는지 평가합니다.'
        + '</div>'
        + _hj_top5_preview_html()
        + '<section class="page-intro"><h2>지난 대회 기록</h2>'
        + '<p>NEO가 분석했던 모든 대회는 <a href="/tournaments/">대회 기록</a>에서 다시 볼 수 있습니다.</p></section>'
        + "</main>"
        + FOOTER
        + "</body>"
    )
    return f"<!doctype html><html lang=\"ko\">{head}{body}</html>"


def main():
    archive_html = build_archive_index()
    hj_html = build_hj_scaffold()
    home_html = build_home()

    (ROOT / "docs" / "tournaments" / "index.html").write_text(archive_html, encoding="utf-8")
    hj_dir = TOURNAMENTS_DIR / "2026100004"
    hj_dir.mkdir(parents=True, exist_ok=True)
    (hj_dir / "index.html").write_text(hj_html, encoding="utf-8")
    (ROOT / "docs" / "index.html").write_text(home_html, encoding="utf-8")

    print("wrote docs/tournaments/index.html", len(archive_html), "bytes")
    print("wrote docs/tournaments/2026/2026100004/index.html", len(hj_html), "bytes")
    print("wrote docs/index.html", len(home_html), "bytes")


if __name__ == "__main__":
    main()
