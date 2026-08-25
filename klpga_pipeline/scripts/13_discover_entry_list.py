"""Discovery script for STEP 2 of the entry-list investigation — does
NOT assume any entry-list endpoint exists or guess its shape. It only:

  1. Calls the ALREADY-CONFIRMED getGameList endpoint for a season and
     prints every entry's gameFinish value, so a non-"F" (i.e. not yet
     completed) tournament — a real upcoming/in-progress candidate —
     can be identified from data this project already trusts. Prints
     that candidate's FULL raw JSON (every field, not just the ones
     this project currently parses) in case an entry-count or
     entry-list hint already exists there and was never looked for
     because every getGameList call so far has been scoped to
     gameFinish="F".
  2. Fetches robots.txt + the site/data-center home pages (same as
     scripts/00_discover_site.py) but with a broadened keyword list
     that actually includes entry/participant/roster terms in English
     and Korean — the original list in 00 never did.
  3. Follows every keyword-matched link ONE hop further (e.g. a
     schedule or gameinfo page) and re-scans THAT page's own links
     with the same broadened keyword list — still only surfacing real
     links the site itself served, never constructing a URL by hand.

Read-only, makes no DB writes. Uses the same PoliteHttpClient
(rate-limited, disk-cached) as every other collector.

This script cannot, by design, produce a final confirmed entry-list
endpoint on its own — see the printed guidance at the end for the
required human-in-the-loop step (a real browser DevTools Network
capture on the candidate tournament's own page), which is how every
other endpoint in this project has actually been confirmed.

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts/13_discover_entry_list.py --season 2026
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.tournaments import fetch_game_list  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DISCOVER_DIR = ROOT / "data" / "raw_cache" / "discover"

DOMAINS = [
    "https://www.klpga.co.kr",
    "https://data.klpga.co.kr",
]

# Broadened from scripts/00_discover_site.py's list: adds entry/roster/
# participant terms in English and Korean, per the investigation brief
# (참가선수, 출전선수, 엔트리, entry, participant, roster, application).
KEYWORDS = [
    "schedule", "gameinfo", "game_info", "ranking", "record", "stats",
    "player", "result", "tour", "일정", "성적", "기록", "선수", "순위",
    "entry", "participant", "roster", "application", "playerlist",
    "player_list", "entrylist", "entry_list", "entry-list",
    "참가선수", "출전선수", "엔트리", "선수명단", "출전", "참가", "신청선수",
]


def _keyword_links(base_url: str, html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for tag, attr in [("a", "href"), ("script", "src"), ("iframe", "src")]:
        for el in soup.find_all(tag):
            val = el.get(attr)
            if not val:
                continue
            full = urljoin(base_url, val)
            if any(kw in full.lower() for kw in KEYWORDS):
                links.add(full)
    return links


def discover_game_list(client: PoliteHttpClient, season: int) -> None:
    print("=" * 100)
    print(f"STEP 2a: getGameList season={season}, tourType={config.TOUR_TYPE_REGULAR} — full gameFinish breakdown")
    print("=" * 100)
    listings = fetch_game_list(client, season=season, tour_type=config.TOUR_TYPE_REGULAR)
    by_finish: dict[str, int] = {}
    for listing in listings:
        by_finish[listing.game_finish] = by_finish.get(listing.game_finish, 0) + 1
    print(f"{len(listings)} total entries. gameFinish breakdown: {by_finish}")

    candidates = [l for l in listings if l.game_finish != config.GAME_FINISH_DONE]
    if not candidates:
        print(
            f"No non-'{config.GAME_FINISH_DONE}' (i.e. upcoming/in-progress) entries found for "
            f"season={season}. Try a season closer to the current date, or --season for next year."
        )
        return

    candidates.sort(key=lambda l: l.start_date_raw or "")
    print(f"\n{len(candidates)} candidate (non-completed) tournament(s), soonest startDate first:")
    for c in candidates:
        print(f"  gameCode={c.game_code}  gameFinish={c.game_finish!r}  start={c.start_date_raw}  end={c.end_date_raw}  title={c.game_title!r}")

    chosen = candidates[0]
    print(f"\n--- FULL raw getGameList entry for the soonest candidate (gameCode={chosen.game_code}) ---")
    print(json.dumps(chosen.raw, ensure_ascii=False, indent=2))
    print(
        "\nInspect every key above for anything entry/participant/count-shaped "
        "(e.g. an entryCnt/playerCnt-style field) that was never looked for before "
        "since prior getGameList calls only ever targeted gameFinish='F' rows."
    )


def discover_site_links(client: PoliteHttpClient) -> None:
    print("\n" + "=" * 100)
    print("STEP 2b/2c: site + data-center home pages, broadened keyword links, one hop deeper")
    print("=" * 100)
    DISCOVER_DIR.mkdir(parents=True, exist_ok=True)

    for base in DOMAINS:
        robots_url = urljoin(base, "/robots.txt")
        try:
            robots_text = client.get_text(robots_url)
            (DISCOVER_DIR / f"robots_{urlparse(base).netloc}.txt").write_text(robots_text, encoding="utf-8")
            print(f"[robots] {robots_url} saved")
        except Exception as exc:  # noqa: BLE001
            print(f"[robots] {robots_url} -> ERROR {exc}")

        try:
            home_html = client.get_text(base)
        except Exception as exc:  # noqa: BLE001
            print(f"[home] {base} -> ERROR {exc}")
            continue

        (DISCOVER_DIR / f"home_{urlparse(base).netloc}.html").write_text(home_html, encoding="utf-8")
        first_hop = _keyword_links(base, home_html)
        print(f"[home] {base}: {len(first_hop)} keyword-matching link(s)")
        for link in sorted(first_hop):
            print(f"    {link}")

        second_hop: set[str] = set()
        for link in sorted(first_hop):
            try:
                page_html = client.get_text(link)
            except Exception as exc:  # noqa: BLE001
                print(f"    [1-hop] {link} -> ERROR {exc}")
                continue
            found = _keyword_links(link, page_html)
            new_links = found - first_hop - {base}
            if new_links:
                print(f"    [1-hop] {link}: {len(new_links)} NEW keyword-matching link(s)")
                for nl in sorted(new_links):
                    print(f"        {nl}")
            second_hop |= new_links

        all_links = sorted(first_hop | second_hop)
        out_path = DISCOVER_DIR / f"entry_links_{urlparse(base).netloc}.txt"
        out_path.write_text("\n".join(all_links), encoding="utf-8")
        print(f"[home] {base}: {len(all_links)} total link(s) (1+2 hop) -> {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    discover_game_list(client, args.season)
    discover_site_links(client)

    print("\n" + "=" * 100)
    print("REQUIRED NEXT STEP — cannot be automated further without guessing")
    print("=" * 100)
    print(
        "This script can only surface links the site already serves and getGameList's own\n"
        "raw fields — it cannot discover a JSON API that isn't linked from an HTML anchor/script\n"
        "tag (e.g. an AJAX call fired by clicking a tab). To actually confirm the entry-list\n"
        "source, per this project's established method for every other endpoint:\n"
        "  1. Open the candidate tournament's own page in a real browser (use the gameCode\n"
        "     printed above, and/or the links just printed, to find it).\n"
        "  2. Look for a tab/section such as '출전선수' / '참가선수' / '엔트리' / 'Field'.\n"
        "  3. Open DevTools -> Network, click that tab, and capture the exact request made\n"
        "     (method, URL, params, response body) — the same way getGameList and\n"
        "     roundLeaderboard were originally confirmed.\n"
        "  4. Report the captured request/response back before any diagnostic script for it\n"
        "     is written."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
