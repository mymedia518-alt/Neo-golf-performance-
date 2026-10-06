"""NEO HJ 2026 (gameCode 2026100004) Stableford pre-event backtest --
acquire the real prior-season scoreRecord captures for the bounded
2025 manifest (klpga_pipeline/content/website_v2/
STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json, 23 tournaments,
all real-dated strictly before 2025100001's own 2025-10-01 start --
see klpga.website_v2.stableford_prior_tournament_manifest).

Reuses the already-validated endpoint/collector/parser unmodified:
  klpga.collectors.score_record.fetch_score_record_html (GET
  scoreRecord?gameCode=<code>, via PoliteHttpClient)
  klpga.collectors.score_record.extract_hole_outcomes (the per-round
  hole-outcome parser, SOURCE-PASS verified against 2023100002/
  2024100009/2025100001 already)

Does NOT fetch anything outside the manifest's 23 game_codes -- no
other years/events are touched.

IDENTITY VERIFICATION (real, not a guess): every real scoreRecord page
this project has captured embeds a tournament-selector <select> with
the REQUESTED gameCode marked `selected` (confirmed by direct
inspection of all 3 already-captured Stableford pages, e.g.
`<option value="2025100001" selected>2025 동부건설 · 한국토지신탁
챔피언십</option>`). A response that does NOT contain
`value="<gameCode>" selected` for the gameCode actually requested is
treated as NOT corresponding to that tournament and is never saved as
if it were a valid capture.

NEVER OVERWRITES a valid existing capture silently: if the target file
already exists AND its own identity check already passes, this script
skips it (reports status="ALREADY_ACQUIRED") unless --force is passed.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/207_acquire_2025_prior_tournaments.py
    python scripts/207_acquire_2025_prior_tournaments.py --force   # re-fetch everything

Output:
  evidence/stableford_prior_2025/<gameCode>_scoreRecord.html  (raw, unmodified)
  evidence/stableford_prior_2025/ACQUISITION_REPORT.json       (per-entry status)
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
    KLPGA_PIPELINE_ROOT / "content" / "website_v2" / "STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json"
)
OUT_DIR = KLPGA_PIPELINE_ROOT / "evidence" / "stableford_prior_2025"


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
    # write_bytes, not write_text: on Windows, text-mode write silently
    # translates every \n to \r\n, which changes the on-disk bytes from
    # whatever `html` held when its sha256 above was computed -- found
    # for real when verifying the first 23 captures (identity/parsing
    # were still fine, but every recorded sha256 failed to re-verify
    # against the committed file for exactly this reason). Writing the
    # same encoded bytes that were hashed guarantees they match.
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
        "\nNEXT: commit and push evidence/stableford_prior_2025/ (the HTML captures + "
        "ACQUISITION_REPORT.json) to neo-website-v2 so 김민솔's real pre-event hole-outcome "
        "history can be reconstructed."
    )
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
