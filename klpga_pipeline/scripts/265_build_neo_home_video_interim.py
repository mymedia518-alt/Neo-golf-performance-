"""Build docs/index.html -- the minimal, non-tournament-specific
interim HOME (owner interim-video-home-v1, see home_ownership_guard.py's
"OWNER SUPERSESSION 3" note).

Operator instruction (2026-10-23): move the Iceberg golf · 서울신문 오픈
tournament page OFF root HOME -- it stays published at its own stage
URLs (/tournaments/2026/2026100003/<stage>/) and listed in the 대회
기록 archive exactly as before (untouched by this script) -- and make
a season-wide KLPGA prize-money ranking video the centerpiece of root
HOME instead. This supersedes scripts/259's FR-mirror approach for
root HOME specifically; scripts/259 itself (and the real FR page it
reads from) are untouched.

No section here claims anything the data doesn't support: the brand
intro is one real sentence, the "최근 대회" line is resolved from the
same calendar-driven chronology resolver scripts/264 uses (never
hardcoded), and the video's own on-screen captions already carry their
source/as-of date -- this script adds no further claim about it.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import (  # noqa: E402
    ensure_footer_copyright, inject_build_provenance, inject_global_navigation,
)
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    COMPOSITE_HOME_OWNER, CURRENT_TOURNAMENT_OWNER, INTERIM_VIDEO_HOME_OWNER,
    TOP120_OWNER, assert_home_write_allowed, embed_owner, extract_owner,
)
from klpga.website_v2.official_schedule import load_official_schedule  # noqa: E402
from klpga.website_v2.previous_tournament_link import latest_published_stage_url  # noqa: E402
from klpga.website_v2.tournament_chronology import resolve_tournament_chronology  # noqa: E402

DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
VIDEO_SRC = "/assets/clips/klpga-2026-prize-money-top20.mp4"


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def main() -> None:
    import json
    registry = json.loads((CONTENT / "TOURNAMENT_SITE_REGISTRY.json").read_text(encoding="utf-8-sig"))["tournaments"]
    schedule = load_official_schedule(CONTENT / "OFFICIAL_KLPGA_SCHEDULE.json")
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date.today())
    current = chronology.get("current")
    last = chronology.get("last")
    featured = current or last

    recent_tournament_html = ""
    if featured is not None and featured.url_base:
        stage_url = latest_published_stage_url(featured.url_base, repo_root=REPO_ROOT)
        status_label = "진행 중" if current is not None else "최근 종료"
        result_line = ""
        if featured.winner:
            score = f" ({featured.winning_score})" if featured.winning_score else ""
            result_line = f" · 우승 {escape(featured.winner)}{escape(score)}"
        recent_tournament_html = (
            "<p class='meta'>"
            f"{escape(status_label)} 대회: <strong>{escape(featured.tournament_name)}</strong>"
            f"{result_line} · <a href='{escape(stage_url)}'>공식 기록 보기 →</a>"
            "</p>"
        )

    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="home-section home-brand-intro">'
        '<p class="kicker">NEO GOLF DATA</p>'
        "<h1>골프 기록을 분석해 경기력을 읽습니다</h1>"
        "<p>NEO GOLF DATA는 KLPGA 공식 기록을 수집·정리하고, 데이터를 분석합니다.</p>"
        "<p>대회별 공식 기록은 <a href='/tournaments/'>대회 기록</a>에서 확인할 수 있습니다.</p>"
        + recent_tournament_html +
        "</section>"
        '<section class="home-section" id="season-prize-video">'
        '<div class="section-heading"><div><p class="section-label">영상</p>'
        "<h2>2026 시즌 KLPGA 상금 순위</h2></div></div>"
        "<p class='meta'>대회별 상금 순위를 정리한 영상입니다. 출처: KLPGA 공식 기록 "
        "(영상 내 각 슬라이드에 기준일 표시).</p>"
        f"<video controls playsinline style='display:block;width:100%;max-width:28rem;height:auto;margin-top:.75rem' "
        f"src='{VIDEO_SRC}'></video>"
        "</section>"
        '<section class="home-section">'
        '<div class="section-heading"><div><p class="section-label">더 보기</p>'
        "<h2>랭킹 · Deep Dive · NEO LAB · 소개</h2></div></div>"
        "<p class='meta'>아래 메뉴는 준비 중입니다. 정리가 끝나면 차례로 공개합니다.</p>"
        "<ul class='neo-card-grid'>"
        "<li class='neo-card'><a href='/ranking/'>K-Ranking</a></li>"
        "<li class='neo-card'><a href='/deep-dive/'>Deep Dive</a></li>"
        "<li class='neo-card'><a href='/neo-lab/'>NEO LAB</a></li>"
        "<li class='neo-card'><a href='/about/'>소개</a></li>"
        "</ul>"
        "</section>"
        "</main>"
    )

    head = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        "<title>NEO GOLF DATA · 골프 데이터 분석</title>"
        "<meta name='description' content='NEO GOLF DATA는 KLPGA 공식 기록을 분석하는 데이터 분석 회사입니다.'>"
        '<link rel="canonical" href="https://neogolfdata.com/">'
        '<meta property="og:title" content="NEO GOLF DATA">'
        "<meta property='og:description' content='골프 기록을 분석해 경기력을 읽습니다.'>"
        '<meta property="og:url" content="https://neogolfdata.com/">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css">'
        "</head><body>"
    )
    html = head + body + '<footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'

    html = inject_global_navigation(html, active_section="home")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    html = embed_owner(html, INTERIM_VIDEO_HOME_OWNER)

    existing_owner = extract_owner(DOCS_INDEX.read_text(encoding="utf-8")) if DOCS_INDEX.is_file() else None
    transfer_from = existing_owner if existing_owner in (
        TOP120_OWNER, CURRENT_TOURNAMENT_OWNER, COMPOSITE_HOME_OWNER,
    ) else CURRENT_TOURNAMENT_OWNER
    assert_home_write_allowed(
        DOCS_INDEX, INTERIM_VIDEO_HOME_OWNER, repo_root=REPO_ROOT, allow_transfer_from=transfer_from,
    )

    DOCS_INDEX.write_text(html, encoding="utf-8", newline="\n")
    print({
        "written": str(DOCS_INDEX),
        "featured_tournament": featured.tournament_name if featured else None,
    })


if __name__ == "__main__":
    main()
