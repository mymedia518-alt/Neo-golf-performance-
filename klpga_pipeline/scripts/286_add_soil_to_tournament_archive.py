"""Add the 제20회 S-OIL 챔피언십 (game_code 2026100001) entry to the
public tournament archive index (docs/tournaments/index.html). It was
never listed there -- every other built/published tournament has an
<article class="archive-card"> row, but S-OIL's was missing entirely,
so its archive-listing h2 link and stage-links row point at the latest
published stage (R3) the same way every other entry's h2 does (e.g.
iceberg's h2 points at its own latest stage, FR).

Inserted FIRST in the list (same newest-first date order the other
entries already follow: S-OIL 2026.10.29-11.01 is the most recent of
all listed tournaments).
"""
from __future__ import annotations

import json
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
ARCHIVE_INDEX = REPO_ROOT / "docs" / "tournaments" / "index.html"
GAME_CODE = "2026100001"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"

FIRST_EXISTING_CARD_MARKER = '<article class="archive-card" data-tournament-archive-card data-game-code="2026100003">'


def main() -> None:
    html = ARCHIVE_INDEX.read_text(encoding="utf-8")
    if FIRST_EXISTING_CARD_MARKER not in html:
        raise SystemExit("first existing archive card not found verbatim")
    if f'data-game-code="{GAME_CODE}"' in html:
        raise SystemExit(f"{GAME_CODE} already has an archive card -- refusing to add a duplicate")

    info = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    start, end = info["start_date"], info["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    event_name = info["event_name"]
    course_name = info["course_name"]

    new_card = (
        f'<article class="archive-card" data-tournament-archive-card data-game-code="{GAME_CODE}">'
        f'<h2><a href="/tournaments/2026/{GAME_CODE}/r3/">{event_name}</a></h2>'
        f'<p class="tournament-context__meta">{date_range} · {course_name}</p>'
        f'<div class="stage-links">'
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">사전 분석</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/r1/">R1</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/r2/">R2</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/r3/">R3</a>'
        f'</div></article>'
    )

    html2 = html.replace(FIRST_EXISTING_CARD_MARKER, new_card + FIRST_EXISTING_CARD_MARKER, 1)
    assert html2 != html
    ARCHIVE_INDEX.write_text(html2, encoding="utf-8")
    print(json.dumps({"written": str(ARCHIVE_INDEX), "event_name": event_name, "date_range": date_range}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
