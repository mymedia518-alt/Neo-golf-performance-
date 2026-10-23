"""Build the 공사중 (under construction) placeholder for the four routes
the operator asked to take offline until they're finished: /ranking/,
/deep-dive/, /neo-lab/, /about/ (2026-10-23 instruction).

Only root HOME and 대회 기록 (the tournament archive + each
tournament's own stage pages) stay publicly live with real content.
This script does NOT touch, run, or delete scripts/260-263 (the real
builders for these four pages) or any data file they read -- it only
overwrites what's currently published at each of their four routes
with a short, fixed notice. Re-running 260-263 later (once a page is
actually finished) is exactly how a route comes back online; no
un-delete or restore step is needed.

Exact operator-specified notice text, unchanged: "페이지를 준비하고
있습니다. 정리가 끝나면 공개하겠습니다." -- no page-specific wording,
no partial/teaser content, no internal status detail.
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

# (route dir under docs/, nav active_section key, page title)
ROUTES = (
    ("ranking", "ranking", "K-Ranking"),
    ("deep-dive", "deep-dive", "Deep Dive"),
    ("neo-lab", "neo-lab", "NEO LAB"),
    ("about", "about", "소개"),
)


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def build_one(route_dir: str, active_section: str, title: str) -> Path:
    out_page = REPO_ROOT / "docs" / route_dir / "index.html"

    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="under-construction">'
        f'<p class="kicker">{title}</p>'
        '<h1>공사중</h1>'
        f'<p>{NOTICE_TEXT}</p>'
        "<p class='section-link-row'><a href='/'>홈으로 돌아가기 →</a></p>"
        '</section>'
        "</main>"
    )

    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        f"<title>{title} · NEO GOLF DATA</title>"
        f"<meta name='description' content='{NOTICE_TEXT}'>"
        f'<link rel="canonical" href="https://neogolfdata.com/{route_dir}/">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        "</head><body>" + body +
        '<footer class="site-footer"><div class="site-footer__inner"><p>NEO GOLF DATA</p></div></footer>'
        "</body></html>"
    )

    html = inject_global_navigation(html, active_section=active_section)
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    out_page.parent.mkdir(parents=True, exist_ok=True)
    out_page.write_text(html, encoding="utf-8", newline="\n")
    return out_page


def main() -> None:
    written = []
    for route_dir, active_section, title in ROUTES:
        p = build_one(route_dir, active_section, title)
        written.append(str(p))
    print({"written": written})


if __name__ == "__main__":
    main()
