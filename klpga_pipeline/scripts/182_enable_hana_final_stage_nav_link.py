"""HANA FINAL -- retroactively enable the FINAL stage-nav link on the
already-published PRE/R1/R2/R3 pages, mirroring scripts/161/175's own
established `_enable_r2/r3_stage_nav_link` pattern exactly: idempotent
(no-op if already linked), fail-loud (raises if the expected disabled
"FR" placeholder isn't found exactly once -- never guesses). The ONLY
effect: replacing that one <li> substring with a real link to FINAL's
real route. Every other byte of PRE/R1/R2/R3 is left untouched.

Hana's stage_order registry entry (TOURNAMENT_SITE_REGISTRY.json) lists
["pre","r1","r2","r3","fr","final"] with round 4 (the tournament's own
final competitive round) publicly labeled "FR" per the project's
permanent public-stage-naming convention. No separate "FR" (raw round-4
leaderboard) page was ever built for Hana -- the operator's FINAL build
task asked only for the post-tournament forecast-vs-result FINAL page
at /final/, so the existing disabled "FR" nav placeholder is replaced
directly with a working FINAL link, never left dangling.
"""
from __future__ import annotations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAME_CODE = "2026090002"

DISABLED_FR_ITEM = '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li>'
FINAL_LINK_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/final/">FINAL</a></li>'
FINAL_CURRENT_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/final/" aria-current="page">FINAL</a></li>'

TARGET_PAGES = [
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r3" / "index.html",
]


def _enable(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if FINAL_LINK_ITEM in html or FINAL_CURRENT_ITEM in html:
        print(f"[NAV] {path} already linked -- no-op")
        return False
    count = html.count(DISABLED_FR_ITEM)
    if count != 1:
        raise ValueError(f"{path}: expected exactly one disabled FR stage-nav placeholder, found {count} -- refusing to guess")
    updated = html.replace(DISABLED_FR_ITEM, FINAL_LINK_ITEM, 1)
    path.write_text(updated, encoding="utf-8")
    print(f"[NAV] {path} updated: FINAL link enabled")
    return True


def main():
    for path in TARGET_PAGES:
        _enable(path)


if __name__ == "__main__":
    main()
