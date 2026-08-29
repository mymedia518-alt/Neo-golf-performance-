"""First-contact diagnostic for the REPORTED (not yet independently
confirmed) player-profile endpoint. Read-only, no DB writes, no
parsing — see klpga.collectors.player_profile's module docstring for
why this project never guesses DOM structure.

Fetches ONE or MORE playerCode profile pages (default: the two
examples reported in chat, 9788 박혜준 and 11134 서교림 — both already
independently verified elsewhere in this project as real players in
game_code=2026080001), saves the raw HTML to
data/raw_cache/player_profile_sample_<playerCode>.html, and prints:
  - the real HTTP status code
  - response length
  - whether the literal text "소속" appears in the page at all
  - up to 300 characters of context around every "소속" occurrence,
    so the real surrounding markup (table? dl/dt/dd? something else?)
    is visible without this project guessing it
  - whether the player's own name (if --expect-name is given) appears
    on the page, as a cheap identity sanity check

This script deliberately extracts NOTHING structured. Its only job is
to produce a real fixture (e.g. to be saved as
tests/fixtures/player_profile_sample.html) that a real parser
(klpga.parsers.player_profile_parser, not yet written) can be built
and tested against — matching the entry_list_parser.py precedent.

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts\\53_fetch_player_profile_sample.py
    python scripts\\53_fetch_player_profile_sample.py --player-code 9788 --expect-name 박혜준
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

print("[STEP 01] script started (stdlib imports complete)", flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.player_profile import fetch_player_profile_html  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_CACHE_DIR = ROOT / "data" / "raw_cache"

DEFAULT_TARGETS = [
    ("9788", "박혜준"),
    ("11134", "서교림"),
]


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


def inspect_player_profile(client: PoliteHttpClient, player_code: str, expect_name: str | None) -> int:
    print(f"\n{'=' * 80}", flush=True)
    print(f"[REQUEST] playerCode={player_code}", flush=True)
    try:
        status, html = fetch_player_profile_html(client, player_code)
    except RateLimitBlockedError as exc:
        print(f"BLOCKED: {exc}", flush=True)
        return 1
    except Exception as exc:  # real fetch failure — surface it loudly
        print(f"FETCH FAILED: {type(exc).__name__}: {exc}", flush=True)
        return 1

    print(f"[RESPONSE] status={status} length={len(html)} chars", flush=True)

    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_CACHE_DIR / f"player_profile_sample_{player_code}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[SAVED] {out_path}", flush=True)

    if status != 200:
        print(f"  NOTE: non-200 status ({status}) — page content below may be an error page.", flush=True)

    has_field = "소속" in html
    print(f"[FIELD CHECK] '소속' present in raw HTML: {has_field}", flush=True)
    if has_field:
        for i, snippet in enumerate(_context_snippets(html, "소속"), start=1):
            print(f"  --- 소속 occurrence {i} (raw, unescaped) ---", flush=True)
            print(f"  {snippet!r}", flush=True)
    else:
        print("  NOTE: '소속' not found anywhere in the raw response text.", flush=True)

    if expect_name:
        name_present = expect_name in html
        print(f"[IDENTITY CHECK] expected name '{expect_name}' present in page: {name_present}", flush=True)
        if not name_present:
            print(
                f"  HARD FAIL CANDIDATE: playerCode={player_code} did not surface the expected "
                f"name '{expect_name}' anywhere in the response — do not trust this fixture for "
                f"that player without investigating.",
                flush=True,
            )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-code", action="append", help="playerCode to fetch (repeatable). Default: the two reported examples.")
    parser.add_argument("--expect-name", action="append", help="Expected player name for the matching --player-code (same order, repeatable).")
    args = parser.parse_args()

    if args.player_code:
        codes = args.player_code
        names = args.expect_name or [None] * len(codes)
        if len(names) != len(codes):
            print("ERROR: --expect-name count must match --player-code count (or be omitted entirely).", flush=True)
            return 2
        targets = list(zip(codes, names))
    else:
        targets = DEFAULT_TARGETS

    print(f"[STEP 02] targets: {targets}", flush=True)
    client = PoliteHttpClient()

    exit_code = 0
    for player_code, expect_name in targets:
        rc = inspect_player_profile(client, player_code, expect_name)
        exit_code = exit_code or rc

    print(f"\n{'=' * 80}", flush=True)
    print(
        "Next step: review the printed '소속' context snippets and the saved "
        "data/raw_cache/player_profile_sample_*.html files, then share them back "
        "so a real parser (klpga.parsers.player_profile_parser) can be written "
        "against the actual markup — this script deliberately does not guess it.",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
