"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- acquire the real
season-to-date cumulative Driving Distance / Fairway Accuracy / GIR
for the real 108-player field.

This is a thin wrapper: it imports and reuses, completely unchanged,
scripts/213_acquire_and_reconstruct_official_season_stats.py's
run_preflight_pilot() and acquire_and_reconstruct_player() -- the same
two-layer-gated reconstruction already proven against the three
historical winners' fields (commit eadf36f, 6,068 calls, 0 scope
mismatches). The only new thing here is pointing those same functions
at the new 2026 manifest (scripts/222) instead of the 2023/2024/2025
one -- no new acquisition method, no new gate logic, no new
aggregation formula.

Scale: 108 players, 2,264 total (player, tournament) calls (vs. the
previous ~2,000/year across a full field -- comparable order of
magnitude).

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/223_acquire_hj_2026_gir_dd.py
    python scripts/223_acquire_hj_2026_gir_dd.py --force

Output:
  evidence/hj_2026100004_gir_dd_reconstructed/RECONSTRUCTION_REPORT.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.http_client import PoliteHttpClient  # noqa: E402

CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
MANIFEST_PATH = CONTENT_ROOT / "HJ_2026100004_GIR_DD_RECONSTRUCTION_MANIFEST_V1.json"
OUT_DIR = KLPGA_PIPELINE_ROOT / "evidence" / "hj_2026100004_gir_dd_reconstructed"


def _load_script_213():
    spec = importlib.util.spec_from_file_location(
        "acquire_213", KLPGA_PIPELINE_ROOT / "scripts" / "213_acquire_and_reconstruct_official_season_stats.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--save-html", action="store_true")
    parser.add_argument("--limit-players", type=int, default=None, help="debug: only the first N players")
    args = parser.parse_args()

    mod213 = _load_script_213()
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = data["entries"][: args.limit_players] if args.limit_players else data["entries"]
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")

    report_path = OUT_DIR / "RECONSTRUCTION_REPORT.json"
    if not args.force and report_path.exists():
        print(f"already reconstructed ({report_path}), skipping. Use --force to redo.")
        return 0

    print(f"=== HJ 2026100004 (cutoff {data['target_cutoff']}) -- pre-flight pilot ===")
    pilot_ok, pilot_results = mod213.run_preflight_pilot(client, entries)
    print(json.dumps(pilot_results, ensure_ascii=False, indent=2))
    if not pilot_ok:
        print("ABORT: pre-flight pilot gate FAILED -- the gameCode-scoped endpoint's behavior "
              "no longer matches the ground truth this manifest assumes. Investigate before re-running.")
        return 1

    print(f"Pilot passed. Acquiring {len(entries)} players, "
          f"{sum(len(e['pre_cutoff_tournaments']) for e in entries)} total (player, tournament) calls...")
    results = []
    for i, entry in enumerate(entries, 1):
        r = mod213.acquire_and_reconstruct_player(client, entry, args.save_html, OUT_DIR)
        results.append(r)
        if i % 10 == 0 or i == len(entries):
            print(f"  [{i}/{len(entries)}] {r['player_name']}: "
                  f"DD={r['reconstructed']['driving_distance']['value']} "
                  f"FW={r['reconstructed']['fairway_accuracy']['value']} "
                  f"GIR={r['reconstructed']['gir']['value']} "
                  f"(gate {r['n_tournaments_gate_passed']}/{r['n_tournaments_total']})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"run_at_utc": datetime.now(timezone.utc).isoformat(), "game_code": "2026100004",
                    "pilot_results": pilot_results, "results": results},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Wrote {report_path}")
    print("\nNEXT: commit and push evidence/hj_2026100004_gir_dd_reconstructed/ to neo-website-v2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
