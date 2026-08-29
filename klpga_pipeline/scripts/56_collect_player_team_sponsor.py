"""Real, live collection of team_or_sponsor (소속) for all 62
game_code=2026080001 POST-R3 finalists, via the confirmed
klpga.co.kr player-profile endpoint.

Reads the roster from data/roster/r3_finalists_2026080001.csv
(generated once by scripts/55_export_r3_finalist_roster.py from the
already-validated production docs/index.html Player Journey rows —
NOT re-derived here).

For every roster player, in order:
  1. Real HTTP fetch (klpga.collectors.player_profile.fetch_player_profile_html)
  2. player_name identity check against the fetched page
  3. team_or_sponsor extraction (klpga.parsers.player_profile_parser)

Raw HTML is always saved to data/raw_cache/player_profile/<player_code>.html
whenever the fetch itself succeeded, even for a player that later fails
identity or parse validation — so a failure can be investigated from
the actual response, not just this script's summary.

The output CSV (data/csv/player_team_sponsor_2026080001.csv;
player_code,player_name,team_or_sponsor) is written ONLY if every
single roster player reached the OK outcome. Any FETCH/IDENTITY/PARSE
failure blocks the CSV write entirely and exits non-zero — a partial
or disguised-as-blank result is never produced. Re-running this script
is always safe: PoliteHttpClient's own throttle/retry policy is reused
unchanged, and get_text_with_status is always-live (never served from
its disk cache), so a rerun re-verifies rather than trusting a stale
result.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

print("[STEP 01] script started (stdlib imports complete)", flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.player_team_sponsor import (  # noqa: E402
    RosterIntegrityError,
    collect_roster,
)
from klpga.http_client import PoliteHttpClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROSTER_PATH = ROOT / "data" / "roster" / "r3_finalists_2026080001.csv"
RAW_HTML_DIR = ROOT / "data" / "raw_cache" / "player_profile"
OUTPUT_CSV_PATH = ROOT / "data" / "csv" / "player_team_sponsor_2026080001.csv"


def load_roster(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [(row["player_code"], row["player_name"]) for row in reader]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", default=str(DEFAULT_ROSTER_PATH))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    roster_path = Path(args.roster)
    roster = load_roster(roster_path)
    print(f"[STEP 02] loaded {len(roster)} roster rows from {roster_path}", flush=True)

    finalists_count = len(roster)
    print(f"FINALISTS {finalists_count}", flush=True)

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))

    try:
        results = collect_roster(client, roster)
    except RosterIntegrityError as exc:
        print(f"HARD FAIL (roster integrity, before any network call): {exc}", flush=True)
        return 1

    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    for r in results:
        if r.raw_html is not None:
            (RAW_HTML_DIR / f"{r.player_code}.html").write_text(r.raw_html, encoding="utf-8")

    fetch_ok = sum(1 for r in results if r.outcome != "FETCH_FAILURE")
    identity_ok = sum(1 for r in results if r.outcome not in ("FETCH_FAILURE", "IDENTITY_FAILURE"))
    parse_failures = [r for r in results if r.outcome == "PARSE_FAILURE"]
    team_present = sum(1 for r in results if r.outcome == "OK" and r.team_or_sponsor != "")
    team_empty = sum(1 for r in results if r.outcome == "OK" and r.team_or_sponsor == "")

    print(f"\n{'=' * 80}", flush=True)
    print(f"FINALISTS {finalists_count}", flush=True)
    print(f"PROFILE FETCH {fetch_ok}/{finalists_count}", flush=True)
    print(f"IDENTITY MATCH {identity_ok}/{finalists_count}", flush=True)
    print(f"TEAM PRESENT {team_present}", flush=True)
    print(f"TEAM EMPTY {team_empty}", flush=True)
    print(f"PARSE FAILURE {len(parse_failures)}", flush=True)
    print("DUPLICATE 0  (roster passed validate_roster before any fetch)", flush=True)
    print(f"{team_present} + {team_empty} = {team_present + team_empty}", flush=True)

    failures = [r for r in results if r.outcome != "OK"]
    if failures:
        print(f"\n{len(failures)} player(s) did NOT reach OK — listed below, NOT written to output CSV:", flush=True)
        for r in failures:
            print(f"  [{r.outcome}] player_code={r.player_code} player_name={r.player_name}: {r.detail}", flush=True)
        print(
            "\nHARD FAIL: refusing to write the output CSV — every roster player "
            "must reach OK first. Investigate the raw HTML saved under "
            f"{RAW_HTML_DIR} for the failing player_code(s) above.",
            flush=True,
        )
        return 1

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["player_code", "player_name", "team_or_sponsor"])
        for r in results:
            writer.writerow([r.player_code, r.player_name, r.team_or_sponsor])

    print(f"\n[WRITTEN] {OUTPUT_CSV_PATH} ({len(results)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
