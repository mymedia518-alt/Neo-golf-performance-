"""Build docs/deep-dive/index.html -- the real Deep Dive hub.

Links only to content that genuinely exists on disk: the real,
already-built player intelligence pages under docs/player/<id>/, and
the real tournament hub at /tournaments/. A placeholder page with no
real analysis yet (docs/player/9115/, still "공사중") is excluded --
never listed as if it had real content. No course-specific analysis
hub exists yet, so no "코스 분석" card is shown (nothing to link to
honestly); this is not filled with a decorative placeholder.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import (  # noqa: E402
    ensure_footer_copyright, inject_build_provenance, inject_global_navigation,
)

OUT_PAGE = REPO_ROOT / "docs" / "deep-dive" / "index.html"
PLAYER_DIR = REPO_ROOT / "docs" / "player"


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _real_player_pages() -> list[dict]:
    out = []
    for d in sorted(PLAYER_DIR.iterdir()):
        page = d / "index.html"
        if not page.is_file():
            continue
        html = page.read_text(encoding="utf-8")
        title_m = re.search(r"<title>(.*?)</title>", html)
        title = title_m.group(1) if title_m else ""
        if "공사중" in title or not title:
            continue
        name = title.split("·")[0].strip()
        out.append({"player_id": d.name, "name": name, "title": title})
    return out


def main() -> None:
    players = _real_player_pages()
    assert players, "no real player analysis pages found under docs/player/"

    cards = []
    for p in players:
        cards.append(
            "<li class='neo-card'>"
            f"<a href='/player/{escape(p['player_id'])}/'>{escape(p['name'])}</a>"
            "</li>"
        )

    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="neo-page-head"><p class="kicker">딥다이브</p>'
        "<h1>Deep Dive</h1>"
        "<p>검증된 선수·대회 분석으로 연결합니다. 실제 분석이 완료된 항목만 표시합니다.</p>"
        "</section>"
        '<section class="neo-panel"><h2>선수 분석</h2>'
        f"<ul class='neo-card-grid'>{''.join(cards)}</ul>"
        "</section>"
        '<section class="neo-panel"><h2>대회 기록</h2>'
        "<p>전체 대회의 공식 결과와 라운드별 기록은 <a class='neo-link-pill' href='/tournaments/'>대회 기록 보기 →</a></p>"
        "</section>"
        "</main>"
    )

    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Deep Dive · NEO GOLF DATA</title>"
        "<meta name='description' content='NEO GOLF DATA의 선수·대회 분석 모음입니다.'>"
        '<link rel="canonical" href="https://neogolfdata.com/deep-dive/">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        "</head><body>" + body +
        '<footer class="site-footer"><div class="site-footer__inner"><p>NEO GOLF DATA</p></div></footer>'
        "</body></html>"
    )

    html = inject_global_navigation(html, active_section="deep-dive")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE), "player_count": len(players)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
