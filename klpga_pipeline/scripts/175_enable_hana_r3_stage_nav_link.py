"""HANA R3 -> FINAL PIPELINE, STEP 8 (operator instruction, 2026-09-19):
retroactively enable the R3 stage-nav link on the already-built,
already-published PRE/R1/R2 pages, mirroring scripts/161's own
established `_enable_r2_stage_nav_link` pattern exactly: idempotent
(no-op if already linked), fail-loud (raises if the expected disabled-
R3 placeholder isn't found exactly once -- never guesses). The ONLY
effect: replacing that one <li> substring with a real link to R3's
real route. Every other byte of PRE/R1/R2 is left untouched.
"""
from __future__ import annotations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAME_CODE = "2026090002"

DISABLED_R3_ITEM = '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
R3_LINK_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r3/">R3</a></li>'
R3_CURRENT_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r3/" aria-current="page">R3</a></li>'

TARGET_PAGES = [
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html",
]


def _enable(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if R3_LINK_ITEM in html or R3_CURRENT_ITEM in html:
        print(f"[NAV] {path} already linked -- no-op")
        return False
    count = html.count(DISABLED_R3_ITEM)
    if count != 1:
        raise ValueError(f"{path}: expected exactly one disabled R3 stage-nav placeholder, found {count} -- refusing to guess")
    updated = html.replace(DISABLED_R3_ITEM, R3_LINK_ITEM, 1)
    path.write_text(updated, encoding="utf-8")
    print(f"[NAV] {path} updated: R3 link enabled")
    return True


def main():
    for path in TARGET_PAGES:
        _enable(path)


if __name__ == "__main__":
    main()
