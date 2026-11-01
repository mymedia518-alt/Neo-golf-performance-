"""Enable the FR stage-nav tab link on PRE/R1/R2/R3 (game_code
2026100001), now that the real FR page exists (scripts/292).

Surgical, single-pattern replacement only: the disabled FR placeholder
span -> a real link to /tournaments/2026/2026100001/fr/, byte-for-byte
identical to the already-working PRE/R1/R2/R3 cross-links on these same
pages. No other markup is touched. Asserts the placeholder is found
exactly once per page before replacing, and that nothing else in the
file changes.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAME_CODE = "2026100001"
PAGES = ["pre", "r1", "r2", "r3"]

OLD = "<span class='stage-nav__disabled' aria-disabled='true'>FR</span>"
NEW = f"<a class='stage-nav__link' href='/tournaments/2026/{GAME_CODE}/fr/'>FR</a>"


def main() -> None:
    for stage in PAGES:
        path = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / stage / "index.html"
        html = path.read_text(encoding="utf-8")
        count = html.count(OLD)
        assert count == 1, f"{path}: expected exactly 1 disabled FR placeholder, found {count}"
        new_html = html.replace(OLD, NEW, 1)
        assert new_html != html
        path.write_text(new_html, encoding="utf-8", newline="\n")
        print(f"enabled FR link on {path}")


if __name__ == "__main__":
    main()
