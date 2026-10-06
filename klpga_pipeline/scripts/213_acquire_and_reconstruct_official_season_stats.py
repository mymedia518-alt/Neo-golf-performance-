"""NEO Stableford three-winner pre-event profile validation -- acquire
EVERY pre-cutoff tournament's own publicRecordSeasonDetail record per
player and reconstruct a true season-to-date CUMULATIVE Driving
Distance / Fairway Accuracy / GIR (not the single-tournament snapshot
scripts/210 produced -- see STABLEFORD_THREE_WINNER_PRE_EVENT_PROFILE_
V1.md's "Critical finding" for why that was wrong).

Uses content/website_v2/STABLEFORD_OFFICIAL_SEASON_STAT_RECONSTRUCTION
_MANIFEST_V1.json (built by scripts/212, no new network access): for
every one of the 102/103/103 resolved players across 2023/2024/2025,
every pre-cutoff tournament they ACTUALLY played, with the real,
independently-known round count for THAT tournament (ground truth from
already-verified scoreRecord captures).

TWO-LAYER GATE (per the explicit instruction not to repeat script
210's mistake of assuming the response's scope without verifying it):

  1. PRE-FLIGHT PILOT (run once before the full acquisition): fetches
     a handful of (player, specific pre-cutoff gameCode) pairs with
     known ground truth and checks the returned 라운드수 matches
     exactly. If this fails, KLPGA's endpoint behavior differs from
     what scripts/210's discovery established (e.g. the site changed),
     and the full run ABORTS rather than mass-acquiring under a wrong
     assumption.

  2. PER-CALL GATE (every single call, not just the pilot): compares
     that one call's own returned 라운드수 against the ground truth for
     THAT SPECIFIC tournament. A mismatch means this one tournament's
     data is excluded from the aggregation (never silently summed in),
     and is recorded as a gate failure for that player/tournament.

Aggregation (klpga.collectors.official_season_stat_reconstruction):
weighted sum of numerator/denominator across every gate-passed
tournament -- NEVER a simple average of per-tournament percentages.

Scale: ~1,769 (2023) + ~2,165 (2024) + ~2,134 (2025) = ~6,068 total
(player, tournament) calls. Raw HTML is NOT saved by default (that
many files would be impractical to commit) -- pass --save-html to
also write each response (useful for a small --year/--limit-players
debug run). Every call's sha256 + exact parsed values are always
recorded in the output JSON regardless, so the evidence trail is
preserved without the raw files.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/213_acquire_and_reconstruct_official_season_stats.py
    python scripts/213_acquire_and_reconstruct_official_season_stats.py --year 2025
    python scripts/213_acquire_and_reconstruct_official_season_stats.py --force

Output (per year):
  evidence/stableford_official_stats_reconstructed_<year>/RECONSTRUCTION_REPORT.json
    -- per player: every tournament's raw numerator/denominator/gate
    result, plus the final reconstructed cumulative value for Driving
    Distance/Fairway Accuracy/GIR.
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

from klpga.collectors.official_season_stat_reconstruction import (  # noqa: E402
    TournamentCallRecord,
    reconstruct_driving_distance,
    reconstruct_fairway_accuracy,
    reconstruct_gir,
    scope_gate_passes,
)
from klpga.collectors.public_record_season_detail import (  # noqa: E402
    fetch_public_record_season_detail,
    parse_public_record_season_detail_html,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

MANIFEST_PATH = (
    KLPGA_PIPELINE_ROOT / "content" / "website_v2"
    / "STABLEFORD_OFFICIAL_SEASON_STAT_RECONSTRUCTION_MANIFEST_V1.json"
)

PILOT_SAMPLE_SIZE = 5


def _fetch_one(client: PoliteHttpClient, player_code: str, season: int, game_code: str) -> dict:
    try:
        status, html = fetch_public_record_season_detail(client, player_code, season, game_code)
    except RateLimitBlockedError as e:
        return {"error": f"RateLimitBlockedError: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    result = {"response_status": status, "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
              "acquired_at_utc": datetime.now(timezone.utc).isoformat()}
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
    result["parsed"] = parsed
    result["html"] = html
    return result


def _returned_rounds(parsed: dict) -> int | None:
    detail = (parsed.get("평균타수") or {}).get("detail") or {}
    raw = detail.get("라운드수")
    if raw is None:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def run_preflight_pilot(client: PoliteHttpClient, entries: list[dict]) -> tuple[bool, list[dict]]:
    """Layer 1 gate: sample a handful of (player, specific pre-cutoff
    gameCode) pairs with known ground truth; abort the whole run if
    KLPGA's own scoping behavior no longer matches what scripts/210's
    discovery established."""
    samples = []
    for entry in entries:
        for t in entry["pre_cutoff_tournaments"]:
            samples.append((entry["player_code"], entry["season"], t["game_code"], t["real_rounds_this_tournament"]))
            if len(samples) >= PILOT_SAMPLE_SIZE:
                break
        if len(samples) >= PILOT_SAMPLE_SIZE:
            break

    pilot_results = []
    all_passed = True
    for player_code, season, game_code, real_rounds in samples:
        call = _fetch_one(client, player_code, season, game_code)
        returned = _returned_rounds(call.get("parsed", {})) if "parsed" in call else None
        passed = scope_gate_passes(returned, real_rounds)
        all_passed = all_passed and passed
        pilot_results.append({"player_code": player_code, "game_code": game_code,
                               "real_rounds": real_rounds, "returned_rounds": returned, "gate_passed": passed})
    return all_passed, pilot_results


def acquire_and_reconstruct_player(client: PoliteHttpClient, entry: dict, save_html: bool, out_dir: Path) -> dict:
    player_code = entry["player_code"]
    season = entry["season"]
    call_records = []
    tournament_call_records: list[TournamentCallRecord] = []

    for t in entry["pre_cutoff_tournaments"]:
        game_code = t["game_code"]
        real_rounds = t["real_rounds_this_tournament"]
        call = _fetch_one(client, player_code, season, game_code)
        parsed = call.get("parsed")
        returned_rounds = _returned_rounds(parsed) if parsed else None
        gate_passed = scope_gate_passes(returned_rounds, real_rounds)

        dd_num = dd_den = fw_num = fw_den = gir_num = None
        if gate_passed and parsed:
            dd = parsed.get("드라이브 거리") or {}
            fw = parsed.get("페어웨이 안착률") or {}
            gir = parsed.get("그린적중률") or {}
            dd_num = _as_float((dd.get("detail") or {}).get("전체 비거리"))
            dd_den = _as_float((dd.get("detail") or {}).get("전체 측정 홀"))
            fw_num = _as_float((fw.get("detail") or {}).get("페어웨이 안착 수"))
            fw_den = _as_float((fw.get("detail") or {}).get("전체 측정 홀"))
            gir_num = _as_float((gir.get("detail") or {}).get("그린적중수"))

        tournament_call_records.append(TournamentCallRecord(
            game_code=game_code, gate_passed=gate_passed,
            driving_distance_numerator=dd_num, driving_distance_denominator=dd_den,
            fairway_numerator=fw_num, fairway_denominator=fw_den, gir_numerator=gir_num,
            real_rounds_this_tournament=real_rounds,
        ))
        call_records.append({
            "game_code": game_code, "start_date": t["start_date"], "real_rounds_this_tournament": real_rounds,
            "returned_rounds": returned_rounds, "gate_passed": gate_passed,
            "response_status": call.get("response_status"), "sha256": call.get("sha256"),
            "error": call.get("error") or call.get("parse_error"),
            "driving_distance_numerator": dd_num, "driving_distance_denominator": dd_den,
            "fairway_numerator": fw_num, "fairway_denominator": fw_den, "gir_numerator": gir_num,
        })
        if save_html and "html" in call:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{player_code}_{game_code}.html").write_bytes(call["html"].encode("utf-8"))

    dd_result = reconstruct_driving_distance(tournament_call_records)
    fw_result = reconstruct_fairway_accuracy(tournament_call_records)
    gir_result = reconstruct_gir(tournament_call_records)

    return {
        "player_name": entry["player_name"], "player_code": player_code, "season": season,
        "expected_pre_cutoff_rounds_total": entry["expected_pre_cutoff_rounds_total"],
        "n_tournaments_total": len(call_records),
        "n_tournaments_gate_passed": sum(1 for c in call_records if c["gate_passed"]),
        "tournament_calls": call_records,
        "reconstructed": {
            "driving_distance": dd_result.__dict__,
            "fairway_accuracy": fw_result.__dict__,
            "gir": gir_result.__dict__,
        },
    }


def _as_float(text) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", choices=["2023", "2024", "2025"], default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--save-html", action="store_true")
    parser.add_argument("--limit-players", type=int, default=None, help="debug: only the first N players")
    args = parser.parse_args()

    manifests = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    years = [args.year] if args.year else list(manifests.keys())
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")

    for year in years:
        m = manifests[year]
        entries = m["entries"][: args.limit_players] if args.limit_players else m["entries"]
        out_dir = KLPGA_PIPELINE_ROOT / "evidence" / f"stableford_official_stats_reconstructed_{year}"
        report_path = out_dir / "RECONSTRUCTION_REPORT.json"
        if not args.force and report_path.exists():
            print(f"{year}: already reconstructed ({report_path}), skipping. Use --force to redo.")
            continue

        print(f"\n=== {year} (cutoff {m['target_cutoff']}) -- pre-flight pilot ===")
        pilot_ok, pilot_results = run_preflight_pilot(client, entries)
        print(json.dumps(pilot_results, ensure_ascii=False, indent=2))
        if not pilot_ok:
            print(f"ABORT {year}: pre-flight pilot gate FAILED -- the gameCode-scoped endpoint's behavior "
                  "no longer matches the ground truth this manifest assumes. Do not proceed; investigate "
                  "before re-running.")
            continue

        print(f"Pilot passed ({len(pilot_results)}/{len(pilot_results)}). "
              f"Acquiring {len(entries)} players, {sum(len(e['pre_cutoff_tournaments']) for e in entries)} "
              "total (player, tournament) calls...")
        results = []
        for i, entry in enumerate(entries, 1):
            r = acquire_and_reconstruct_player(client, entry, args.save_html, out_dir)
            results.append(r)
            if i % 10 == 0 or i == len(entries):
                print(f"  [{i}/{len(entries)}] {r['player_name']}: "
                      f"DD={r['reconstructed']['driving_distance']['value']} "
                      f"FW={r['reconstructed']['fairway_accuracy']['value']} "
                      f"GIR={r['reconstructed']['gir']['value']} "
                      f"(gate {r['n_tournaments_gate_passed']}/{r['n_tournaments_total']})")

        out_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({"run_at_utc": datetime.now(timezone.utc).isoformat(), "year": year,
                        "pilot_results": pilot_results, "results": results},
                       ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Wrote {report_path}")

    print(
        "\nNEXT: commit and push evidence/stableford_official_stats_reconstructed_<year>/ to neo-website-v2 "
        "so the three-winner pre-event profile report can be finalized with real season-to-date cumulative "
        "Driving Distance/Fairway Accuracy/GIR values and field percentiles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
