"""Generic sitemap.xml generator for the whole NEO GOLF DATA site --
never tournament-specific, so the SAME script keeps working for every
future tournament without being touched again.

    python scripts/build_sitemap.py

Walks docs/ for every index.html and includes a URL only if it is a
real, representative, indexable page:
  - excluded if the page itself carries <meta name="robots"
    content="noindex...> (covers every scripts/apply_public_site_
    lockdown.py placeholder page, and any private player page --
    e.g. docs/player/9115/ -- the exact same signal a crawler itself
    would honor, never a second, separately-maintained list).
  - excluded under docs/share/ (OG-card mirror, duplicate content,
    not meant to be crawled as a destination) and docs/archive/
    (legacy, superseded snapshots).
  - excluded for docs/player/<id>/data-quality/ (an operator-facing
    QA page, not a page a search user is meant to land on).
  - a docs/player/<id>/index.html is included only if that id is
    currently "reviewed" per klpga.website_v2.player_link's own real
    production-readiness signal (player_report_exists) -- the exact
    same rule that decides whether this site itself links to that
    player anywhere, so the sitemap never advertises a page nothing
    on the real site points to either.

lastmod is each URL's own real git last-commit timestamp
(`git log -1 --format=%aI -- <path>`) -- never "now" on every build,
so a page that genuinely did not change keeps its real previous
lastmod, and only a page actually touched in a given run gets a new
one, once that change is committed.

DISCOVERABILITY, not just existence: a page is included only if it is
real (responds, not noindex, not mock data) AND actually reachable
from HOME via the site's own real `<a href="/...">` links -- a plain
`rglob` would otherwise have included known orphans found by hand
while building this (docs/2026090002/ -- a stale top-level duplicate
mirror of Hana's own real /tournaments/2026/2026090002/... pages;
docs/tournaments/2026/2026100005/course-analysis/ -- a standalone
page nothing on the real site links to; docs/tournaments/2026/
2026100005/deep-dive/ -- explicitly `<meta name="neo-mock-data"
content="true">`, fabricated placeholder data). Never advertises a
URL the site's own real navigation would never lead a visitor (or a
crawler) to.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"
SITE_ORIGIN = "https://neogolfdata.com"

sys.path.insert(0, str(ROOT / "src"))
from klpga.website_v2.player_link import player_report_exists  # noqa: E402

_EXCLUDED_PREFIXES = ("share/", "archive/")
_NOINDEX_RE = re.compile(r'<meta\s+name="robots"\s+content="[^"]*noindex')
_MOCK_DATA_RE = re.compile(r'<meta\s+name="neo-mock-data"\s+content="true"')
_NOT_READY_RE = re.compile(r'<meta\s+name="neo-stage-publication-ready"\s+content="false"')
_HREF_RE = re.compile(r'''href=["'](/[^"'#?]*)["']''')


def _git_lastmod(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "-1", "--format=%aI", "--", str(path.relative_to(REPO_ROOT))],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return out or None


def _url_path_to_file(url_path: str) -> Path:
    rel = url_path.strip("/")
    return DOCS / rel / "index.html" if rel else DOCS / "index.html"


def _reachable_from_home() -> set[str]:
    """BFS over real on-site <a href="/..."> links, starting from HOME
    -- the set of URL paths an actual visitor (or crawler) can reach by
    clicking through the real, already-built site. Never static/asset
    links (only internal pages whose own index.html exists)."""
    seen: set[str] = set()
    queue: deque[str] = deque(["/"])
    while queue:
        url_path = queue.popleft()
        if url_path in seen:
            continue
        file_path = _url_path_to_file(url_path)
        if not file_path.is_file():
            continue
        seen.add(url_path)
        html = file_path.read_text(encoding="utf-8")
        for href in _HREF_RE.findall(html):
            next_path = href if href.endswith("/") or "." not in href.rsplit("/", 1)[-1] else None
            if next_path and next_path not in seen:
                queue.append(next_path)
    return seen


def collect_urls() -> list[tuple[str, str | None]]:
    reachable = _reachable_from_home()
    urls: list[tuple[str, str | None]] = []
    for index_html in sorted(DOCS.rglob("index.html")):
        rel = index_html.relative_to(DOCS).as_posix()
        if rel == "index.html":
            url_path = "/"
        else:
            url_path = "/" + rel[: -len("index.html")]

        rel_no_index = rel[: -len("index.html")]
        if any(rel_no_index.startswith(p) for p in _EXCLUDED_PREFIXES):
            continue
        if re.match(r"^player/[^/]+/data-quality/$", rel_no_index):
            continue
        if url_path not in reachable:
            continue

        m = re.match(r"^player/([^/]+)/$", rel_no_index)
        if m and not player_report_exists(m.group(1)):
            continue

        html = index_html.read_text(encoding="utf-8")
        if _NOINDEX_RE.search(html) or _MOCK_DATA_RE.search(html) or _NOT_READY_RE.search(html):
            continue

        lastmod = _git_lastmod(index_html)
        urls.append((url_path, lastmod))
    return urls


def build_sitemap_xml(urls: list[tuple[str, str | None]]) -> str:
    entries = []
    for url_path, lastmod in urls:
        lastmod_tag = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        entries.append(f"<url><loc>{SITE_ORIGIN}{url_path}</loc>{lastmod_tag}</url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(entries)
        + "</urlset>\n"
    )


def main() -> None:
    urls = collect_urls()
    xml = build_sitemap_xml(urls)
    out_path = DOCS / "sitemap.xml"
    out_path.write_text(xml, encoding="utf-8")
    print(f"wrote {out_path} ({len(urls)} URLs)")


if __name__ == "__main__":
    main()
