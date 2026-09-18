"""HANA R2 -- retroactively enable the R2 stage-nav link on the
already-built, already-published PRE and R1 pages, mirroring KB's own
established `_enable_r2_stage_nav_link` pattern (scripts/112) exactly:
idempotent (no-op if already linked), fail-loud (raises if the
expected disabled-R2 placeholder isn't found exactly once -- never
guesses). This is the ONLY effect: replacing that one <li> substring
with a real link to R2's real route. Every other byte of PRE/R1 is
left untouched.
"""
from __future__ import annotations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAME_CODE = "2026090002"

DISABLED_R2_ITEM = '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li>'
R2_LINK_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/">R2</a></li>'
R2_CURRENT_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/" aria-current="page">R2</a></li>'

TARGET_PAGES = [
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",
]


def _enable(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if R2_LINK_ITEM in html or R2_CURRENT_ITEM in html:
        print(f"[NAV] {path} already linked -- no-op")
        return False
    count = html.count(DISABLED_R2_ITEM)
    if count != 1:
        raise ValueError(f"{path}: expected exactly one disabled R2 stage-nav placeholder, found {count} -- refusing to guess")
    updated = html.replace(DISABLED_R2_ITEM, R2_LINK_ITEM, 1)
    path.write_text(updated, encoding="utf-8")
    print(f"[NAV] {path} updated: R2 link enabled")
    return True


def main():
    for path in TARGET_PAGES:
        _enable(path)


if __name__ == "__main__":
    main()
