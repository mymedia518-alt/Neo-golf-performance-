"""Reconnaissance script — run this FIRST once network access to
klpga.co.kr / data.klpga.co.kr is available.

It does NOT assume any endpoint structure. It:
  1. Fetches and saves robots.txt for both domains (and prints a summary
     of any Disallow rules so later steps can respect them).
  2. Fetches the main site and data-center home pages.
  3. Extracts every internal link/script src referencing schedule,
     game info, ranking, or stats pages so we can identify the real
     endpoints (HTML pages vs JSON APIs) to build the real collectors
     against, instead of guessing selectors blind.

Output goes to data/raw_cache/discover/ for manual + follow-up
programmatic inspection. Nothing here writes to the CSV/DB outputs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.http_client import PoliteHttpClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "raw_cache"
DISCOVER_DIR = ROOT / "data" / "raw_cache" / "discover"
DISCOVER_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = [
    "https://www.klpga.co.kr",
    "https://data.klpga.co.kr",
]

KEYWORDS = [
    "schedule", "gameinfo", "game_info", "ranking", "record", "stats",
    "player", "result", "tour", "일정", "성적", "기록", "선수", "순위",
]


def check_robots(client: PoliteHttpClient, base: str) -> None:
    url = urljoin(base, "/robots.txt")
    try:
        text = client.get_text(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[robots] {url} -> ERROR {exc}")
        return
    out_path = DISCOVER_DIR / f"robots_{urlparse(base).netloc}.txt"
    out_path.write_text(text, encoding="utf-8")
    disallow_lines = [ln for ln in text.splitlines() if ln.strip().lower().startswith("disallow")]
    print(f"[robots] {url} saved -> {out_path}")
    print(f"[robots] {len(disallow_lines)} Disallow rules (see file for full list)")


def crawl_home(client: PoliteHttpClient, base: str) -> None:
    try:
        html = client.get_text(base)
    except Exception as exc:  # noqa: BLE001
        print(f"[home] {base} -> ERROR {exc}")
        return

    out_path = DISCOVER_DIR / f"home_{urlparse(base).netloc}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[home] {base} saved -> {out_path}")

    soup = BeautifulSoup(html, "lxml")
    links = set()
    for tag, attr in [("a", "href"), ("script", "src"), ("iframe", "src")]:
        for el in soup.find_all(tag):
            val = el.get(attr)
            if not val:
                continue
            full = urljoin(base, val)
            if any(kw in full.lower() for kw in KEYWORDS):
                links.add(full)

    out_links = DISCOVER_DIR / f"links_{urlparse(base).netloc}.txt"
    out_links.write_text("\n".join(sorted(links)), encoding="utf-8")
    print(f"[home] {len(links)} keyword-matching links -> {out_links}")


def main() -> None:
    client = PoliteHttpClient(cache_dir=CACHE_DIR / "http")
    for base in DOMAINS:
        check_robots(client, base)
        crawl_home(client, base)
    print("\nDone. Inspect data/raw_cache/discover/*.html and links_*.txt")
    print("to identify the real schedule / gameinfo / ranking endpoints,")
    print("then update src/klpga/collectors/*.py accordingly.")


if __name__ == "__main__":
    main()
