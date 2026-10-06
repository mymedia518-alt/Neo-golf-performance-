"""NEO HJ 2026 (gameCode 2026100004) Stableford three-winner pre-event
profile validation -- acquire official KLPGA season-stat detail
(Driving Distance / Fairway Accuracy / GIR / Par5 scoring / Average
Score) for the full 2023/2024/2025 pre-event Stableford fields, using
the confirmed-real `publicRecordSeasonDetail` endpoint
(klpga.collectors.public_record_season_detail).

Reuses the manifest already built from this project's own held data
(no guessing): STABLEFORD_OFFICIAL_SEASON_STAT_ACQUISITION_MANIFEST_V1
.json -- 102/103/103 players across 2023/2024/2025, each with a real
playerCode (resolved from the mainRecord?playerCode= links already
embedded in the committed scoreRecord captures), their own
chronologically-last pre-cutoff gameCode, and their own independently-
known real pre-cutoff round count (from the already-verified
scoreRecord hole-by-hole extraction) -- used below as the cross-check.

CRITICAL TEMPORAL SAFETY CHECK (per explicit instruction -- never
assume the season-final value is safe):
  config.py's own documentation says gameCode="" means "전체/all
  tournaments that season" (the FULL-SEASON final, i.e. likely
  CONTAMINATED by post-cutoff tournaments). Whether passing a SPECIFIC
  gameCode instead scopes the response to "cumulative through that
  tournament" is UNCONFIRMED. This script fetches BOTH:
    (a) gameCode=<player's own last real pre-cutoff tournament> --
        the HYPOTHESIZED temporal-safe call
    (b) gameCode="" -- the full-season reference, explicitly logged
        as NOT temporal-safe, kept only for comparison/diagnosis
  then checks (a)'s own returned "라운드수" (rounds) field against the
  player's independently-known real pre-cutoff round count. A match
  (or a sensible, lower, explainable subset -- e.g. KLPGA's own stat
  only counts certain tournament types) is evidence the hypothesis
  holds for that player; any other result is reported as
  SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED for that player's 3
  endpoint-only metrics (Driving Distance/Fairway Accuracy/GIR -- Avg
  Score/Par5 scoring are independently reconstructed elsewhere from
  hole-level data and don't depend on this at all).

Never silently trusts (a) just because it returned 200 -- the
cross-check runs for every single player, every time.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/210_acquire_official_season_stats.py
    python scripts/210_acquire_official_season_stats.py --year 2025   # one year only
    python scripts/210_acquire_official_season_stats.py --force

Output (per year):
  evidence/stableford_official_stats_<year>/<playerCode>_last.html   (gameCode-scoped, hypothesized temporal-safe)
  evidence/stableford_official_stats_<year>/<playerCode>_full.html   (gameCode="", full season -- reference only)
  evidence/stableford_official_stats_<year>/ACQUISITION_REPORT.json  (per-player status + both parsed results + cross-check verdict)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.public_record_season_detail import (  # noqa: E402
    fetch_public_record_season_detail,
    parse_public_record_season_detail_html,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

MANIFEST_PATH = (
    KLPGA_PIPELINE_ROOT / "content" / "website_v2"
    / "STABLEFORD_OFFICIAL_SEASON_STAT_ACQUISITION_MANIFEST_V1.json"
)

TARGET_METRIC_LABELS = {
    "average_score": "평균타수",
    "par5_scoring": "파5성적",
    "fairway_accuracy": "페어웨이 안착률",
    "driving_distance": "드라이브 거리",
    "gir": "그린적중률",
}


def _acquire_one_call(client: PoliteHttpClient, player_code: str, season: int, game_code: str) -> dict:
    try:
        status, html = fetch_public_record_season_detail(client, player_code, season, game_code)
    except RateLimitBlockedError as e:
        return {"error": f"RateLimitBlockedError: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    result = {
        "response_status": status,
        "response_bytes": len(html.encode("utf-8")),
        "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if status != 200:
        result["error"] = f"non-200 status {status}"
        return result
    try:
        parsed = parse_public_record_season_detail_html(html)
    except Exception as e:  # noqa: BLE001
        result["parse_error"] = f"{type(e).__name__}: {e}"
        return result
    if not parsed:
        result["error"] = "parser returned no rows -- not a real publicRecordSeasonDetail fragment"
        return result
    result["parsed"] = {
        key: parsed.get(label) for key, label in TARGET_METRIC_LABELS.items()
    }
    result["html"] = html
    return result


def acquire_player(client: PoliteHttpClient, entry: dict, out_dir: Path, force: bool) -> dict:
    player_name = entry["player_name"]
    player_code = entry["player_code"]
    season = entry["season"]
    last_code = entry["last_pre_cutoff_game_code"]
    expected_rounds = entry["expected_pre_cutoff_rounds_total"]

    last_path = out_dir / f"{player_code}_last.html"
    full_path = out_dir / f"{player_code}_full.html"
    result = {"player_name": player_name, "player_code": player_code, "season": season,
               "last_pre_cutoff_game_code": last_code, "expected_pre_cutoff_rounds_total": expected_rounds}

    if not force and last_path.exists() and full_path.exists():
        result["acquisition_status"] = "ALREADY_ACQUIRED"
        return result

    last_call = _acquire_one_call(client, player_code, season, last_code)
    full_call = _acquire_one_call(client, player_code, season, "")

    for call, path in [(last_call, last_path), (full_call, full_path)]:
        if "html" in call:
            out_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(call["html"].encode("utf-8"))

    result["last_pre_cutoff_call"] = {k: v for k, v in last_call.items() if k != "html"}
    result["full_season_call"] = {k: v for k, v in full_call.items() if k != "html"}

    if "parsed" not in last_call:
        # no usable response at all for the hypothesized temporal-safe call --
        # this is a real access/fetch failure (network error, non-200, or a
        # response that didn't even parse as a real season-detail fragment),
        # never a temporal-scoping question (that requires a parsed response
        # to cross-check in the first place).
        result["status"] = "SOURCE_EXISTS_BUT_ACCESS_BLOCKED"
        result["reason"] = last_call.get("error") or last_call.get("parse_error")
        return result

    returned_rounds_raw = last_call["parsed"]["average_score"]
    returned_rounds = None
    if returned_rounds_raw and returned_rounds_raw.get("detail", {}).get("라운드수"):
        try:
            returned_rounds = int(float(returned_rounds_raw["detail"]["라운드수"]))
        except ValueError:
            returned_rounds = None

    temporal_consistent = returned_rounds is not None and returned_rounds <= expected_rounds
    result["returned_rounds_for_last_pre_cutoff_gamecode"] = returned_rounds
    result["temporal_cross_check_consistent"] = temporal_consistent

    result["status"] = "SOURCE_EXISTS_AND_ACQUIRED" if temporal_consistent else "SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED"
    result["metrics"] = last_call["parsed"]
    result["metrics_full_season_reference_NOT_temporal_safe"] = full_call.get("parsed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", choices=["2023", "2024", "2025"], default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifests = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    years = [args.year] if args.year else list(manifests.keys())
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")

    for year in years:
        m = manifests[year]
        out_dir = KLPGA_PIPELINE_ROOT / "evidence" / f"stableford_official_stats_{year}"
        print(f"\n=== {year} (target {m['target_game_code']}, cutoff {m['target_cutoff']}) -- {len(m['entries'])} players ===")
        results = []
        for entry in m["entries"]:
            r = acquire_player(client, entry, out_dir, args.force)
            print(f"  {entry['player_name']} ({entry['player_code']}): {r.get('acquisition_status') or r.get('status')}")
            results.append(r)

        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "ACQUISITION_REPORT.json"
        report_path.write_text(
            json.dumps({"run_at_utc": datetime.now(timezone.utc).isoformat(), "year": year, "results": results},
                        ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        statuses = [r.get("status") or r.get("acquisition_status") for r in results]
        from collections import Counter
        print(f"  {year} summary:", dict(Counter(statuses)))
        print(f"  Wrote {report_path}")

    print(
        "\nNEXT: commit and push evidence/stableford_official_stats_<year>/ to neo-website-v2 "
        "so the three-winner pre-event profile report can be updated with real Driving Distance/"
        "Fairway Accuracy/GIR/Par5/Average Score values and field percentiles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
