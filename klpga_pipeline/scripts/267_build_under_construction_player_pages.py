"""Extend the 공사중 (under construction) treatment from scripts/266 to
every existing player-intelligence page (docs/player/{id}/index.html).

Why: these pages ARE the "Deep Dive" feature in concrete form -- every
tournament leaderboard that stays public (per the 2026-10-23 operator
instruction) still links a player's name to /player/{id}/ via the
single shared contract in website_v2/player_link.py. Placeholdering
only the /deep-dive/ nav route left this real, detailed analysis
content (Strokes Gained breakdowns, form timelines, slump/peak labels)
one click away from every public tournament page -- exactly what the
operator's "미완성 페이지의 기존 분석 내용이나 불완전한 데이터를
방문자에게 노출하지 마라" instruction rules out.

This script does NOT touch, run, or delete scripts/187
(player_intelligence_v2 builder) or any knowledge_engine data file --
it only overwrites what's currently published at each existing
/player/{id}/ route with the same fixed notice scripts/266 uses.
Re-running 187 later for a finished player report is exactly how that
player's page comes back online.

One pre-existing page (player 9115) already carried an ad hoc,
differently-styled "공사중" placeholder from an earlier, unrelated
cleanup (no shared header/nav, old hex palette). This script folds it
into the same unified system as every other 공사중 surface so the
notice looks and behaves identically site-wide, per the operator's
"공사중 표시는 데스크톱과 모바일에서 같은 방식으로 보이도록 해라"
instruction.

Player IDs are discovered from disk (every existing docs/player/*/
directory), never hardcoded -- a future player report is excluded
automatically once scripts/187 overwrites that one directory's
index.html with real content.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import (  # noqa: E402
    ensure_footer_copyright, inject_build_provenance, inject_global_navigation,
)

NOTICE_TEXT = "페이지를 준비하고 있습니다. 정리가 끝나면 공개하겠습니다."


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def build_one(player_id: str, route_suffix: str = "") -> Path:
    """route_suffix='' for /player/{id}/, 'data-quality' for the nested
    /player/{id}/data-quality/ reconciliation-audit sub-page -- just as
    internal/unfinished-facing as the main page, so it gets the same
    notice rather than being left reachable once bookmarked/guessed."""
    out_dir = REPO_ROOT / "docs" / "player" / player_id
    if route_suffix:
        out_dir = out_dir / route_suffix
    out_page = out_dir / "index.html"
    canonical_path = f"/player/{player_id}/{route_suffix + '/' if route_suffix else ''}"

    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="under-construction">'
        '<p class="kicker">Deep Dive · Player Intelligence</p>'
        '<h1>공사중</h1>'
        f'<p>{NOTICE_TEXT}</p>'
        "<p class='section-link-row'><a href='/'>홈으로 돌아가기 →</a></p>"
        '</section>'
        "</main>"
    )

    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        "<title>Deep Dive · NEO GOLF DATA</title>"
        f"<meta name='description' content='{NOTICE_TEXT}'>"
        '<meta name="robots" content="noindex, nofollow">'
        f'<link rel="canonical" href="https://neogolfdata.com{canonical_path}">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        "</head><body>" + body +
        '<footer class="site-footer"><div class="site-footer__inner"><p>NEO GOLF DATA</p></div></footer>'
        "</body></html>"
    )

    html = inject_global_navigation(html, active_section="deep-dive")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    out_page.write_text(html, encoding="utf-8", newline="\n")
    return out_page


def main() -> None:
    player_root = REPO_ROOT / "docs" / "player"
    player_dirs = sorted(
        p.name for p in player_root.iterdir()
        if p.is_dir() and (p / "index.html").is_file()
    )
    written = [str(build_one(pid)) for pid in player_dirs]
    for pid in player_dirs:
        dq = player_root / pid / "data-quality" / "index.html"
        if dq.is_file():
            written.append(str(build_one(pid, "data-quality")))
    print({"player_ids": player_dirs, "written": written})


if __name__ == "__main__":
    main()
