"""NEO HJ 2026 (gameCode 2026100004) Stableford V1 pre-event
application -- acquire the real 2026-season prior-tournament
scoreRecord captures (content/website_v2/STABLEFORD_2026_PRIOR_
TOURNAMENT_MANIFEST_V1.json, 24 tournaments, all real-dated strictly
before 2026100004's own 2026-10-08 start -- see scripts/217_build_2026
_prior_tournament_manifest.py).

Identical structure and identity-verification mechanism to
scripts/207/208/209 (the already-proven 2023/2024/2025 acquisitions)
-- same endpoint/collector/parser, same never-silently-overwrite
rule, same write_bytes fix (never write_text, which silently
translates \\n to \\r\\n on Windows and breaks its own recorded
sha256).

Two of these 24 tournaments (2026100005/하이트진로, 2026120001/OK저축은행)
already have SOME real hole-by-hole data captured elsewhere in this
repo under different, inconsistent capture methods/shapes (and, for
2026120001, only a mid-tournament snapshot at capture time). This
script does not reuse either -- it fetches ALL 24 fresh from the one
confirmed official scoreRecord endpoint, so every entry in
evidence/stableford_prior_2026/ is consistent and (for 2026120001,
whose tournament has since finished in real time) complete.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/218_acquire_2026_prior_tournaments.py
    python scripts/218_acquire_2026_prior_tournaments.py --force

Output:
  evidence/stableford_prior_2026/<gameCode>_scoreRecord.html  (raw, unmodified)
  evidence/stableford_prior_2026/ACQUISITION_REPORT.json       (per-entry status)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.collectors.score_record import extract_hole_outcomes, fetch_score_record_html  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

MANIFEST_PATH = (
    KLPGA_PIPELINE_ROOT / "content" / "website_v2" / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
)
OUT_DIR = KLPGA_PIPELINE_ROOT / "evidence" / "stableford_prior_2026"


def _identity_ok(html: str, game_code: str) -> bool:
    return re.search(rf'value="{re.escape(game_code)}"\s*selected', html) is not None


def _already_valid(path: Path, game_code: str) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False
    return _identity_ok(text, game_code)


def acquire_one(client: PoliteHttpClient, entry: dict, force: bool) -> dict:
    game_code = entry["game_code"]
    out_path = OUT_DIR / f"{game_code}_scoreRecord.html"
    result = {
        "game_code": game_code,
        "tournament_name": entry["tournament_name"],
        "start_date": entry["start_date"],
        "saved_to": str(out_path),
    }

    if not force and _already_valid(out_path, game_code):
        result.update(acquisition_status="ALREADY_ACQUIRED", source_pass_fail=None)
        return result

    try:
        status, html = fetch_score_record_html(client, game_code)
    except RateLimitBlockedError as e:
        result.update(acquisition_status="ACQUISITION_FAILED", error=f"RateLimitBlockedError: {e}")
        return result
    except Exception as e:  # noqa: BLE001
        result.update(acquisition_status="ACQUISITION_FAILED", error=f"{type(e).__name__}: {e}")
        return result

    identity_ok = _identity_ok(html, game_code)
    result.update(
        response_status=status,
        response_bytes=len(html.encode("utf-8")),
        sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        acquired_at_utc=datetime.now(timezone.utc).isoformat(),
        identity_verified=identity_ok,
    )

    if not identity_ok:
        result.update(
            acquisition_status="ACQUISITION_FAILED",
            source_pass_fail="SOURCE_FAIL",
            error=f'response does not contain value="{game_code}" selected -- wrong tournament or malformed page',
        )
        return result

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(html.encode("utf-8"))
    result["acquisition_status"] = "ACQUIRED"

    try:
        by_round = extract_hole_outcomes(html)
    except ValueError as e:
        result.update(source_pass_fail="SOURCE_FAIL", parser_error=str(e))
        return result

    result.update(
        source_pass_fail="SOURCE_PASS",
        unique_players_by_round={r: len(names) for r, names in by_round.items()},
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch even if a valid capture already exists")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["entries"]
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")

    results = []
    for entry in entries:
        print(f"=== {entry['game_code']} ({entry['tournament_name']}, {entry['start_date']}) ===")
        r = acquire_one(client, entry, args.force)
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        results.append(r)
        print()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "ACQUISITION_REPORT.json"
    report_path.write_text(
        json.dumps({"run_at_utc": datetime.now(timezone.utc).isoformat(), "results": results},
                    ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    n_pass = sum(1 for r in results if r.get("source_pass_fail") == "SOURCE_PASS")
    n_fail = sum(1 for r in results if r.get("source_pass_fail") == "SOURCE_FAIL")
    n_skip = sum(1 for r in results if r.get("acquisition_status") == "ALREADY_ACQUIRED")
    print(f"\nDONE. SOURCE_PASS={n_pass}  SOURCE_FAIL={n_fail}  ALREADY_ACQUIRED={n_skip}  total={len(results)}")
    print(f"Wrote {report_path}")
    print(
        "\nNEXT: commit and push evidence/stableford_prior_2026/ (the HTML captures + "
        "ACQUISITION_REPORT.json) to neo-website-v2 so HJ 2026100004's real pre-event "
        "Stableford V1 snapshot can be built for the full field."
    )
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
