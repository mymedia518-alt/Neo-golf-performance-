"""Verify klpga.parsers.player_profile_parser against the raw HTML
files scripts/53_fetch_player_profile_sample.py already saved on a
real Windows run (data/raw_cache/player_profile_sample_<code>.html).

This is deliberately a SEPARATE step from fetching: it re-parses
files already captured from a real klpga.co.kr response, so it also
works offline / repeatably without hitting the site again.

The parser (klpga.parsers.player_profile_parser) was written against
ONE directly-observed real fragment (playerCode=11134, 서교림 →
삼천리, pasted verbatim in chat — see
tests/fixtures/player_profile_sample_11134.html). The playerCode=9788
(박혜준) expected value "두산건설 We've" was reported in chat but its
real markup has NOT been directly seen by this project — this script's
job is to make that a real, checkable extraction rather than an
assumption: it reads the actual saved 9788 file (if present) and
reports PASS/FAIL/MISMATCH honestly, it does not assume the parser
will succeed on it.

Usage (from a machine that already ran scripts/53 against the real
site):
    python scripts\\54_verify_player_profile_parser.py
    python scripts\\54_verify_player_profile_parser.py --player-code 9788 --expect-name 박혜준 --expect-sponsor "두산건설 We've"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

print("[STEP 01] script started (stdlib imports complete)", flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.parsers.player_profile_parser import (  # noqa: E402
    PlayerProfileParseError,
    parse_team_or_sponsor,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_CACHE_DIR = ROOT / "data" / "raw_cache"

DEFAULT_TARGETS = [
    ("9788", "박혜준", "두산건설 We've"),
    ("11134", "서교림", "삼천리"),
]


def verify_one(player_code: str, expect_name: str | None, expect_sponsor: str | None) -> int:
    print(f"\n{'=' * 80}", flush=True)
    html_path = RAW_CACHE_DIR / f"player_profile_sample_{player_code}.html"
    print(f"[FILE] {html_path}", flush=True)

    if not html_path.exists():
        print(
            f"  MISSING: no saved fixture for playerCode={player_code} — run "
            "scripts/53_fetch_player_profile_sample.py first (on a machine with "
            "real network access to klpga.co.kr).",
            flush=True,
        )
        return 1

    html = html_path.read_text(encoding="utf-8")

    if expect_name:
        name_present = expect_name in html
        print(f"[IDENTITY CHECK] expected name '{expect_name}' present in page: {name_present}", flush=True)
        if not name_present:
            print(
                f"  HARD FAIL: playerCode={player_code} did not surface the expected name "
                f"'{expect_name}' anywhere in the saved page — refusing to trust its 소속 "
                "value for that identity.",
                flush=True,
            )
            return 1

    try:
        sponsor = parse_team_or_sponsor(html)
    except PlayerProfileParseError as exc:
        print(f"[PARSE FAILED] {exc}", flush=True)
        print(
            "  This is a structural parse failure (the 소속 label was not found at "
            "all), NOT the same as 'no sponsor' — do not store this as an empty "
            "team_or_sponsor value.",
            flush=True,
        )
        return 1

    print(f"[PARSED] team_or_sponsor = {sponsor!r}", flush=True)

    if expect_sponsor is not None:
        if sponsor == expect_sponsor:
            print(f"[RESULT] PASS — matches expected {expect_sponsor!r}", flush=True)
            return 0
        print(f"[RESULT] MISMATCH — expected {expect_sponsor!r}, got {sponsor!r}", flush=True)
        return 1

    print("[RESULT] PARSED (no --expect-sponsor given, so not checked against a specific value)", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-code", action="append")
    parser.add_argument("--expect-name", action="append")
    parser.add_argument("--expect-sponsor", action="append")
    args = parser.parse_args()

    if args.player_code:
        codes = args.player_code
        names = args.expect_name or [None] * len(codes)
        sponsors = args.expect_sponsor or [None] * len(codes)
        if len(names) != len(codes) or len(sponsors) != len(codes):
            print(
                "ERROR: --expect-name / --expect-sponsor counts must each match "
                "--player-code count (or be omitted entirely).",
                flush=True,
            )
            return 2
        targets = list(zip(codes, names, sponsors))
    else:
        targets = DEFAULT_TARGETS

    print(f"[STEP 02] targets: {targets}", flush=True)

    exit_code = 0
    for player_code, expect_name, expect_sponsor in targets:
        rc = verify_one(player_code, expect_name, expect_sponsor)
        exit_code = exit_code or rc

    print(f"\n{'=' * 80}", flush=True)
    print("DONE." if exit_code == 0 else "DONE WITH FAILURES — see MISMATCH/MISSING/PARSE FAILED lines above.", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
