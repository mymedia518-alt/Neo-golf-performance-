"""Site-wide global-nav normalizer (2026-10-07, operator instruction:
"사이트 navigation을 단순화해").

The global menu is simplified to exactly six items, consistently, on
EVERY already-published public page:

    홈 / 대회 기록 / 랭킹 / 딥다이브 / NEO LAB / 소개

Two things this removes:
  - "현재 대회" (only ever present on HOME/archive-index/HJ-scaffold,
    via global_header() in build_tournament_archive_and_hj_scaffold.py
    -- fixed at the source there; this script is a no-op on those 3
    once that fix has run).
  - the older "대회" self-link pattern (every hitejinro/KB/Hana/OK/KG/
    player/share page: a tab labeled "대회" pointing at THAT SAME page,
    marked active) -- replaced with a real, fixed "대회 기록" tab
    pointing at /tournaments/, matching the new canonical list. HOME
    is now the only "현재 대회" entry point (its own hero card/CTA),
    per the operator's explicit reasoning: never show 홈 and 현재 대회
    in the global menu at once.

Applied as a surgical, text-only patch directly to every already-
published docs/**/index.html -- same "never regenerate, might leak
later data into an earlier page" discipline this codebase already
established (see hitejinro_round_page.py's own docstring on exactly
that risk). Only the <nav class="neo-global-nav" ...>...</nav> block
is touched; nothing else in any file changes. Preserves each file's
own existing formatting (minified single-line vs the player pages'
pretty-printed multi-line nav) so every diff is minimal.

"active" (class="is-active" aria-current="page") is computed purely
from the file's own real URL path (never guessed per-generator):
  - 홈 active only at the site root "/"
  - 대회 기록 active for the archive index and every real tournament
    page under "/tournaments/" (PRE/R1/R2/R3/FR/FINAL/verification/
    course-analysis/deep-dive alike -- same "you are in the
    tournaments section" idea the old self-"대회" tab already carried)
  - 소개 active only at "/about/"
  - 랭�킹/딥다이브/NEO LAB never active from this script (no page in
    today's site lives under those paths yet)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

CANONICAL_ITEMS = [
    ("/", "홈"),
    ("/tournaments/", "대회 기록"),
    ("/ranking/", "랭킹"),
    ("/deep-dive/", "딥다이브"),
    ("/neo-lab/", "NEO LAB"),
    ("/about/", "소개"),
]

NAV_RE = re.compile(
    r'<nav class="neo-global-nav" aria-label="주요 메뉴">.*?</nav>',
    re.DOTALL,
)


def _url_path_for(file_path: Path) -> str:
    rel = file_path.relative_to(DOCS_ROOT)
    parent = rel.parent
    if str(parent) == ".":
        return "/"
    return "/" + parent.as_posix() + "/"


def _active_index(url_path: str) -> int | None:
    if url_path == "/":
        return 0
    if url_path == "/tournaments/" or url_path.startswith("/tournaments/"):
        return 1
    if url_path == "/about/":
        return 5
    return None


def _build_nav(url_path: str, *, pretty: bool) -> str:
    active = _active_index(url_path)
    items = []
    for i, (href, label) in enumerate(CANONICAL_ITEMS):
        cur = ' class="is-active" aria-current="page"' if i == active else ""
        items.append(f'<a href="{href}"{cur}>{label}</a>')
    sep = "\n" if pretty else ""
    inner = sep.join(items)
    if pretty:
        return f'<nav class="neo-global-nav" aria-label="주요 메뉴">\n{inner}\n</nav>'
    return f'<nav class="neo-global-nav" aria-label="주요 메뉴">{inner}</nav>'


def normalize_file(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    m = NAV_RE.search(html)
    if not m:
        return False
    old_nav = m.group(0)
    pretty = "\n" in old_nav
    url_path = _url_path_for(path)
    new_nav = _build_nav(url_path, pretty=pretty)
    if new_nav == old_nav:
        return False
    assert html.count(old_nav) == 1, f"{path}: nav block not uniquely matched"
    html = html.replace(old_nav, new_nav)
    path.write_text(html, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    changed = []
    unchanged = 0
    for path in sorted(DOCS_ROOT.rglob("index.html")):
        if normalize_file(path):
            changed.append(str(path.relative_to(REPO_ROOT)))
        else:
            unchanged += 1
    print(f"Normalized nav on {len(changed)} file(s); {unchanged} already correct or no nav found.")
    for c in changed:
        print(" -", c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
