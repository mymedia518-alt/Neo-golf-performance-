"""NEO PUBLIC SITE -- APPROVED-ROUTES-ONLY LOCKDOWN.

Locks the published GitHub Pages tree (docs/) down to the main page
and explicitly publication-approved routes. Every other real HTML page and the one stray data JSON
file under docs/ is MOVED (never deleted) to docs_internal_archive/
at the repo root -- a path outside GitHub Pages' publish root (docs/),
so it is never served -- and replaced in place with a minimal
"under construction" placeholder page at the exact same URL path, so
direct URL access returns the placeholder rather than a 404 or the
real content.

docs/index.html, docs/CNAME, docs/.nojekyll, and docs/assets/** are
left completely untouched (main page content/layout, and the shared
CSS/JS assets every page -- including the placeholder -- depends on).

Idempotent: re-running after a previous lockdown is a no-op (files
already under docs_internal_archive/ are skipped; placeholder files
already in place are left as-is).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"
ARCHIVE = REPO_ROOT / "docs_internal_archive"

PLACEHOLDER_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow"><title>NEO GOLF DATA - 공사중</title><style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0b0f14;color:#f5f6f7;font-family:"Noto Sans KR",system-ui,sans-serif;text-align:center}main{padding:24px}h1{font-size:20px;font-weight:700;letter-spacing:.02em;margin:0 0 18px}p.status{font-size:28px;font-weight:800;margin:0 0 10px}p.msg{font-size:15px;color:#9aa4ad;margin:0 0 28px}a.home{display:inline-block;padding:10px 22px;border:1px solid #3a4550;border-radius:6px;color:#f5f6f7;text-decoration:none;font-size:14px}a.home:hover{background:#171d24}</style></head><body><main><h1>NEO GOLF DATA</h1><p class="status">공사중</p><p class="msg">준비 중입니다.</p><a class="home" href="/">홈으로</a></main></body></html>
"""
"""The four required lines (NEO GOLF DATA / 공사중 / 준비 중입니다. /
[홈으로]) are rendered exactly, with [홈으로] as a real <a href="/">
button labeled 홈으로 rather than literal bracket characters -- the
brackets in the spec denote "this is a button/link", not literal text."""

# Every real path under docs/ that must be locked down, EXCEPT index.html,
# CNAME, .nojekyll, and everything under assets/. Enumerated explicitly
# (not path-pattern-matched) so a future new file under docs/ is never
# silently swept in or left exposed without a deliberate review of this list.
LOCKED_HTML_PATHS = [
    "about/index.html",
    "archive/beta001/r1/index.html",
    "archive/beta001/r2/index.html",
    "archive/beta001/r3/index.html",
    "deep-dive/index.html",
    "neo-lab/index.html",
    "ranking/index.html",
    "tournaments/index.html",
    "tournaments/2026/kg-ladies-open/index.html",
    "tournaments/2026/kg-ladies-open/final/index.html",
    "tournaments/2026/kg-ladies-open/pre/index.html",
    "tournaments/2026/kg-ladies-open/r1/index.html",
    "tournaments/2026/kg-ladies-open/r2/index.html",
    "tournaments/2026/kg-ladies-open/r3/index.html",
    "tournaments/2026/ok-savings-bank-open/final/index.html",
    "tournaments/2026/ok-savings-bank-open/pre/index.html",
    "tournaments/2026/ok-savings-bank-open/r1/index.html",
    "tournaments/2026/ok-savings-bank-open/r2/index.html",
    "tournaments/2026/ok-savings-bank-open/r3/index.html",
]

# Public pages that have independently passed their publication gate. Keeping
# this allow-list explicit makes a release reviewable without weakening the
# recursive check for every other HTML file under docs/.
RELEASED_HTML_PATHS = {
    "tournaments/2026/2026090003/pre/index.html",
    "tournaments/2026/2026090003/r1/index.html",
    # R2 HOUSE (20260911): a real, truthful WAIT-state page (no
    # fabricated leaderboard/SG/CUT/probability -- klpga.neo_win.
    # r2_wait_page.render_r2_wait_page) is intentionally public even
    # before real R2 data exists. This is NOT the same as an early
    # leak of real results -- the HOME STATE ROUTER separately refuses
    # to ever advance root HOME to this page (see scripts/88's
    # STAGE_READINESS_MARKER) until its own publication gate passes.
    "tournaments/2026/2026090003/r2/index.html",
}

# Non-HTML real content that is not an asset and is not linked from the
# main page -- also locked down (removed from docs/, archived, NOT
# replaced with a placeholder since it is a raw data path nothing is
# expected to fetch, not a page a person clicks to).
LOCKED_DATA_PATHS_NO_PLACEHOLDER = [
    "data/neo-top120-evaluation.json",
]

PRESERVED_TOP_LEVEL = {"index.html", "CNAME", ".nojekyll", "assets"}


def _archive(relative_path: str) -> None:
    src = DOCS / relative_path
    dst = ARCHIVE / relative_path
    if not src.is_file():
        return
    if dst.is_file():
        # Already archived by a prior run -- do not overwrite a
        # preserved original with whatever is currently sitting at the
        # public path (which may already be the placeholder).
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def apply_lockdown() -> dict:
    archived, placeholdered, removed_no_placeholder = [], [], []

    for rel in LOCKED_HTML_PATHS:
        target = DOCS / rel
        if not target.is_file():
            print(f"WARNING: expected locked path missing, skipping: {rel}", file=sys.stderr)
            continue
        current = target.read_text(encoding="utf-8")
        if current != PLACEHOLDER_HTML:
            _archive(rel)
            archived.append(rel)
            target.write_text(PLACEHOLDER_HTML, encoding="utf-8")
        placeholdered.append(rel)

    for rel in LOCKED_DATA_PATHS_NO_PLACEHOLDER:
        target = DOCS / rel
        if target.is_file():
            _archive(rel)
            archived.append(rel)
            target.unlink()
            removed_no_placeholder.append(rel)

    return {
        "archived": archived,
        "placeholdered_html_paths": placeholdered,
        "removed_no_placeholder_paths": removed_no_placeholder,
    }


def verify_lockdown() -> list[str]:
    """Returns a list of problems (empty == clean). Walks the ENTIRE
    docs/ tree -- not just the enumerated list above -- so a file this
    script's author forgot to enumerate is still caught."""
    problems = []

    top_level = {p.name for p in DOCS.iterdir()}
    unexpected_top_level = top_level - PRESERVED_TOP_LEVEL - {"archive", "deep-dive", "neo-lab", "ranking", "tournaments", "about", "data"}
    if unexpected_top_level:
        problems.append(f"unexpected new top-level entries under docs/: {sorted(unexpected_top_level)}")

    for html_file in DOCS.rglob("*.html"):
        rel = str(html_file.relative_to(DOCS))
        if rel == "index.html" or rel.replace("\\", "/") in RELEASED_HTML_PATHS:
            continue
        content = html_file.read_text(encoding="utf-8")
        if content != PLACEHOLDER_HTML:
            problems.append(f"non-placeholder HTML still exposed at docs/{rel}")

    for data_file in DOCS.rglob("*.json"):
        problems.append(f"raw JSON still exposed at docs/{data_file.relative_to(DOCS)}")

    return problems


if __name__ == "__main__":
    result = apply_lockdown()
    problems = verify_lockdown()
    print(f"archived {len(result['archived'])} file(s) to {ARCHIVE}")
    print(f"placeholdered {len(result['placeholdered_html_paths'])} HTML path(s)")
    print(f"removed (no placeholder) {len(result['removed_no_placeholder_paths'])} path(s)")
    if problems:
        print("VERIFY FAILED:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("VERIFY OK: only docs/index.html, approved routes, and docs/assets/** serve real content.")
