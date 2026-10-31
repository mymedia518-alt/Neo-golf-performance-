"""Update the S-OIL archive card already on docs/tournaments/index.html
(added by the operator's own "Add current S-OIL event to tournament
archive" commit, which pointed at R2 since R3 did not exist yet) to
point at R3 -- the h2 link and a new R3 stage-link, following exactly
the same markup every other tournament's card already uses.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_INDEX = REPO_ROOT / "docs" / "tournaments" / "index.html"
GAME_CODE = "2026100001"

OLD = (
    f'<article class="archive-card" data-tournament-archive-card data-game-code="{GAME_CODE}">'
    f'<h2><a href="/tournaments/2026/{GAME_CODE}/r2/">제20회 S-OIL 챔피언십</a></h2>'
    f'<p class="tournament-context__meta">2026.10.29 — 11.01 · 엘리시안 제주</p>'
    f'<div class="stage-links">'
    f'<a href="/tournaments/2026/{GAME_CODE}/pre/">사전 분석</a>'
    f'<a href="/tournaments/2026/{GAME_CODE}/r1/">R1</a>'
    f'<a href="/tournaments/2026/{GAME_CODE}/r2/">R2</a>'
    f'</div></article>'
)
NEW = (
    f'<article class="archive-card" data-tournament-archive-card data-game-code="{GAME_CODE}">'
    f'<h2><a href="/tournaments/2026/{GAME_CODE}/r3/">제20회 S-OIL 챔피언십</a></h2>'
    f'<p class="tournament-context__meta">2026.10.29 — 11.01 · 엘리시안 제주</p>'
    f'<div class="stage-links">'
    f'<a href="/tournaments/2026/{GAME_CODE}/pre/">사전 분석</a>'
    f'<a href="/tournaments/2026/{GAME_CODE}/r1/">R1</a>'
    f'<a href="/tournaments/2026/{GAME_CODE}/r2/">R2</a>'
    f'<a href="/tournaments/2026/{GAME_CODE}/r3/">R3</a>'
    f'</div></article>'
)


def main() -> None:
    html = ARCHIVE_INDEX.read_text(encoding="utf-8")
    if OLD not in html:
        raise SystemExit("existing S-OIL archive card not found verbatim")
    html2 = html.replace(OLD, NEW, 1)
    assert html2 != html
    ARCHIVE_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(ARCHIVE_INDEX))


if __name__ == "__main__":
    main()
