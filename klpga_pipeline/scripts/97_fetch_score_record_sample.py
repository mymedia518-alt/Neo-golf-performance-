"""First-contact diagnostic for the URL-confirmed-but-DOM-unconfirmed
scoreRecord ("대회기록") endpoint. Read-only, no DB writes, no parsing
-- see klpga.collectors.score_record's module docstring for why this
project never guesses DOM structure.

Fetches the scoreRecord page for ONE gameCode (default: 2026120001, OK
Open -- this project's current active tournament), saves the raw HTML
to data/raw_cache/score_record_sample_<gameCode>.html, and prints:
  - the real HTTP status code and response length
  - whether each of a handful of candidate WD/DQ/final-score marker
    strings ("기권", "실격", "WD", "DQ", 박결/김아현's real player names
    as an identity sanity check) appears anywhere in the page at all
  - up to 300 characters of context around every occurrence of each
    marker found, so the real surrounding markup is visible without
    this project guessing it

This script deliberately extracts NOTHING structured. Its only job is
to produce a real fixture (to be saved as
tests/fixtures/score_record_sample.html) that a real parser
(klpga.parsers.score_record_parser, not yet written) can be built and
tested against -- matching the entry_list_parser.py /
player_profile precedent.

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts\\97_fetch_score_record_sample.py
    python scripts\\97_fetch_score_record_sample.py --game-code 2026120001
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

print("[STEP 01] script started (stdlib imports complete)", flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.score_record import fetch_score_record_html  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_CACHE_DIR = ROOT / "data" / "raw_cache"

DEFAULT_GAME_CODE = "2026120001"  # OK 저축은행 읏맨 오픈 -- this project's current active tournament
CANDIDATE_MARKERS = ["기권", "실격", "WD", "DQ", "박결", "김아현"]


def _context_snippets(html: str, needle: str, radius: int = 300) -> list[str]:
    snippets = []
    start = 0
    while True:
        idx = html.find(needle, start)
        if idx == -1:
            break
        lo = max(0, idx - radius)
        hi = min(len(html), idx + len(needle) + radius)
        snippets.append(html[lo:hi])
        start = idx + len(needle)
    return snippets


def inspect_score_record(client: PoliteHttpClient, game_code: str) -> int:
    print(f"\n{'=' * 80}", flush=True)
    print(f"[REQUEST] gameCode={game_code}", flush=True)
    try:
        status, html = fetch_score_record_html(client, game_code)
    except RateLimitBlockedError as exc:
        print(f"BLOCKED: {exc}", flush=True)
        return 1
    except Exception as exc:  # real fetch failure -- surface it loudly
        print(f"FETCH FAILED: {type(exc).__name__}: {exc}", flush=True)
        return 1

    print(f"[RESPONSE] status={status} length={len(html)} chars", flush=True)

    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_CACHE_DIR / f"score_record_sample_{game_code}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[SAVED] {out_path}", flush=True)

    if status != 200:
        print(f"  NOTE: non-200 status ({status}) -- page content below may be an error page.", flush=True)

    for marker in CANDIDATE_MARKERS:
        found = marker in html
        print(f"[MARKER CHECK] {marker!r} present in raw HTML: {found}", flush=True)
        if found:
            for i, snippet in enumerate(_context_snippets(html, marker), start=1):
                print(f"  --- {marker!r} occurrence {i} (raw, unescaped) ---", flush=True)
                print(f"  {snippet!r}", flush=True)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-code", default=DEFAULT_GAME_CODE, help="gameCode to fetch. Default: current OK Open (2026120001).")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"), help="PoliteHttpClient's on-disk cache dir (same convention as the other scripts/ diagnostics) -- irrelevant here since fetch_score_record_html always fetches live, but required by the client's constructor.")
    args = parser.parse_args()

    print(f"[STEP 02] target gameCode: {args.game_code}", flush=True)
    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))

    exit_code = inspect_score_record(client, args.game_code)

    print(f"\n{'=' * 80}", flush=True)
    print(
        "Next step: review the printed marker context snippets and the saved "
        "data/raw_cache/score_record_sample_*.html file, then share it back so a real "
        "parser (klpga.parsers.score_record_parser) can be written against the actual "
        "markup -- this script deliberately does not guess it. See "
        "klpga.neo_win.r1_final_reconciliation for the intended downstream contract.",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
