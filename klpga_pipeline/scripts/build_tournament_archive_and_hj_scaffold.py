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
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOURNAMENTS_DIR = ROOT / "docs" / "tournaments" / "2026"
CONTENT = ROOT / "klpga_pipeline" / "content" / "website_v2"
HJ_GAME_CODE = "2026100004"

sys.path.insert(0, str(ROOT / "klpga_pipeline" / "src"))
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER,
    assert_home_write_allowed,
)
from klpga.website_v2.hj_pre_video_section import hj_pre_video_section_html  # noqa: E402

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
    """active: 'home' | 'archive' | other (no is-active match).

    2026-10-07 nav simplification (operator instruction): the former
    'current' ("현재 대회") item is removed -- HOME is now the current
    tournament's own entry point (hero card/CTA), so the global menu
    never shows HOME and "현재 대회" at once. Every tournament page
    (archive index, any tournament/stage page) marks 대회 기록 active,
    matching the global nav normalizer (scripts/229) applied to every
    already-published page site-wide."""
    def item(href, label, key):
        cur = ' class="is-active" aria-current="page"' if key == active else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    nav = "".join([
        item("/", "홈", "home"),
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

# UI cleanup (2026-10-07, operator instruction): same three-line
# 경기 방식/점수/NEO 설명 text as scripts/225_build_hj_2026100004_pre_
# page.py's own STABLEFORD_EXPLANATION_HTML -- operator requires HOME
# and PRE to show the identical explanation (tested by extracting both
# pages' plain text and comparing). Only the existing .fixture-notice
# box + spacing/line-height/font-weight/line-break -- no new CSS class,
# no per-score cards, no added color or icon.
STABLEFORD_EXPLANATION_HTML = (
    '<div class="fixture-notice">'
    '<p style="margin:0 0 .6rem;font-weight:800;line-height:1.5">이번 대회는 변형 스테이블포드 방식으로 진행됩니다.</p>'
    '<p style="margin:0 0 .7rem;font-weight:700;line-height:1.8">'
    '<span style="white-space:nowrap">알바트로스 +8</span> · <span style="white-space:nowrap">이글 +5</span> · <span style="white-space:nowrap">버디 +2</span><br>'
    '<span style="white-space:nowrap">파 0</span> · <span style="white-space:nowrap">보기 -1</span> · <span style="white-space:nowrap">더블보기 이상 -3</span>'
    '</p>'
    '<p style="margin:0;font-weight:400;line-height:1.6">NEO는 선수들의 대회 전 기록을 이 점수제에 다시 대입해,<br>'
    '이번 대회에서 어떤 선수의 경기 스타일이 더 높은 가치를 갖는지 평가합니다.</p>'
    '</div>'
)


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
HJ_STAGE_LABELS = [("pre", "PRE"), ("r1", "R1"), ("r2", "R2"), ("r3", "R3"), ("fr", "FR")]


def build_hj_scaffold() -> str:
    """2026-10-07 rewrite (operator instruction): the old copy claimed
    "경기 방식에 맞춘 NEO 분석은 준비되는 대로 공개합니다"/"아직 공개된
    분석은 없습니다" -- both false now that PRE is real and published.
    Replaced with a concise root page: name, real game format, a PRE
    entry link, and a stage-nav that only ever links to a stage whose
    page actually exists on disk (same real-file-exists check every
    other stage-nav in this codebase already uses) -- never implies a
    round result is public before it is."""
    tourney = json.loads((CONTENT / f"{HJ_GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    event_name = tourney["event_name"]

    stage_items = []
    for key, label in HJ_STAGE_LABELS:
        href = f"/tournaments/2026/{HJ_GAME_CODE}/{key}/"
        if (TOURNAMENTS_DIR / HJ_GAME_CODE / key / "index.html").is_file():
            stage_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='{href}'>{label}</a></li>")
        else:
            stage_items.append(f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>{label}</span></li>")
    stage_nav = (
        "<nav class='stage-nav' aria-label='대회 단계' data-stage-nav><ol class='stage-nav__list'>"
        + "".join(stage_items) + "</ol></nav>"
    )

    head = (
        "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {event_name}</title>"
        f"<meta name=\"description\" content=\"{event_name} — 변형 스테이블포드 방식 · Stableford 사전평가(PRE) 공개 중\">"
        "<link rel=\"canonical\" href=\"https://neogolfdata.com/tournaments/2026/2026100004/\">"
        f"{GLOBAL_HEAD_LINKS}</head>"
    )
    body = (
        "<body>"
        + global_header("archive")
        + "<main>"
        + breadcrumb(("홈", "/"), ("대회 기록", "/tournaments/"), (event_name, None))
        + f'<div class="tournament-context"><h1>{event_name}</h1>'
        + '<p class="tournament-context__meta">변형 스테이블포드 방식으로 진행됩니다.</p></div>'
        + '<p><a href="/tournaments/2026/2026100004/pre/">Stableford 사전평가 PRE 보기 →</a></p>'
        + stage_nav
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


def _hj_neo_verification_html() -> str:
    """Full-field HOME table: flag + player + sponsor + Stableford rank +
    public NEO verification in the locked order 본선 진출 → TOP 20 → 우승."""
    result_path = CONTENT / "HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
    snapshot_path = CONTENT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"
    if not result_path.is_file() or not snapshot_path.is_file():
        return ""
    result = json.loads(result_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if result.get("target_game_code") != HJ_GAME_CODE or snapshot.get("target_game_code") != HJ_GAME_CODE:
        return ""

    sim_by_pid = {str(p["player_code"]): p for p in result.get("players", [])}
    records = list(snapshot.get("records", []))
    records.sort(key=lambda r: (
        r.get("pre_event_rank") is None,
        r.get("pre_event_rank") or 9999,
        r.get("player_name") or "",
    ))

    rows = []
    for r in records:
        pid = str(r["player_code"])
        sim = sim_by_pid.get(pid)
        country = r.get("nationality") or ""
        flag = (
            f"<img src='/assets/flags/{country}.svg' alt='' width='16' height='12' "
            "style='display:inline-block;vertical-align:middle;margin-right:6px'>"
            if country else ""
        )
        sponsor = r.get("official_sponsor") or ""
        player = (
            f"{flag}<strong>{_esc(r['player_name'])}</strong>"
            + (f"<span style='color:var(--muted);font-size:.82rem;margin-left:.4rem'>{_esc(sponsor)}</span>" if sponsor else "")
        )
        rank = (
            f"#{r['pre_event_rank']}"
            if r.get("data_status") == "OK" and (r.get("rounds") or 0) >= 10 and r.get("pre_event_rank") is not None
            else "<span style='color:var(--muted)'>데이터 부족</span>"
        )
        if sim and sim.get("data_status") == "OK":
            cut = f"{sim['make_cut_pct']:.1f}%"
            top20 = f"{sim['top20_pct']:.1f}%"
            win = f"{sim['win_pct']:.1f}%"
        else:
            cut = top20 = win = "<span style='color:var(--muted)'>데이터 부족</span>"
        rows.append(
            "<tr>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{player}</th>"
            f"<td data-label='Stableford 사전평가'>{rank}</td>"
            f"<td data-label='본선 진출'>{cut}</td>"
            f"<td data-label='TOP 20'>{top20}</td>"
            f"<td data-label='우승'><strong>{win}</strong></td>"
            "</tr>"
        )

    return (
        '<section class="panel leaderboard-panel" id="neo-verification">'
        '<div class="leaderboard-head"><p class="eyebrow" style="margin-bottom:.35rem">NEO 검증</p></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        '<th>선수</th><th>Stableford 사전평가</th><th>본선 진출</th><th>TOP 20</th><th>우승</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
        '<p class="meta" style="margin-top:.7rem">※ 데이터 부족: 대회 전 분석에 필요한 최소 10라운드 기준 미달.</p>'
        '</section>'
    )


def build_home() -> str:
    head = (
        "<head><meta name=\"neo-home-owner\" content=\"current-tournament-v1\">"
        f"<meta name=\"neo-home-game-code\" content=\"{HJ_GAME_CODE}\"><meta charset=\"utf-8\">"
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
        + STABLEFORD_EXPLANATION_HTML
        # PRE->HOME PARITY FIX (2026-10-07, operator instruction): while
        # the tournament hasn't started, HOME *is* the current PRE
        # screen, so it must show the same video PRE shows, in the same
        # position (nav -> Stableford 설명 -> 영상 -> NEO 검증 table) --
        # shared with 225_build_hj_2026100004_pre_page.py via
        # hj_pre_video_section_html so a future rebuild of either page
        # can never drop it again (see that module's docstring).
        + hj_pre_video_section_html(HJ_GAME_CODE)
        + _hj_neo_verification_html()
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

    # HOME ownership guard (added 2026-10-07, incident fix): home_html
    # already embeds both the owner and game_code markers literally in
    # its own head (see build_home() above) -- this assert is this
    # script's own claim-and-protect declaration, so a stale tournament
    # script (156/109/192, etc, now all updated to pass their own fixed
    # writer_game_code) gets hard-stopped if it ever runs again while HJ
    # is the current tournament -- see home_ownership_guard.
    assert_home_write_allowed(
        ROOT / "docs" / "index.html",
        CURRENT_TOURNAMENT_OWNER,
        repo_root=ROOT,
        allow_transfer_from=CURRENT_TOURNAMENT_OWNER,
        writer_game_code=HJ_GAME_CODE,
    )
    (ROOT / "docs" / "index.html").write_text(home_html, encoding="utf-8")

    print("wrote docs/tournaments/index.html", len(archive_html), "bytes")
    print("wrote docs/tournaments/2026/2026100004/index.html", len(hj_html), "bytes")
    print("wrote docs/index.html", len(home_html), "bytes")


if __name__ == "__main__":
    main()
