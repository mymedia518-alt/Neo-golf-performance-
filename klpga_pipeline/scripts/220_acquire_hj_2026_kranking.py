"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- acquire the real
official KLPGA K-RANKING for all 108 canonical entrants.

Reuses the already-built, already-provenance-tracked K-Ranking
collectors from scripts/72_collect_ok_open_public_master.py
(collect_rankings_live / collect_rankings_offline / _resolve_offline_
kranking) UNCHANGED -- this script does NOT touch win_probability, the
M4 forecast, SG rank, or any other part of that script's broader
pipeline. K-RANKING only, kept as its own separate column/evidence
artifact per explicit instruction (never blended with Stableford V1
into a single before/after narrative).

Checks for a sanctioned offline capture first (content/website_v2/
incoming_evidence/2026100004/*KRANKING*RAW.html) -- none exists yet
(confirmed this turn) -- so this falls back to the live fetch against
https://k-rankings.klpga.co.kr/allplayer.jsp, a single bulk POST (not
per-player), for the ranking week klpga.kranking_week.resolve_ranking_
week derives from 2026100004's own real start date (2026-10-08).

Usage (on a machine with real k-rankings.klpga.co.kr access):
    cd klpga_pipeline
    python scripts/220_acquire_hj_2026_kranking.py

Output:
  evidence/hj_2026100004_kranking_acquisition/KRANKING_REPORT.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.kranking_week import resolve_ranking_week  # noqa: E402

CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
IDENTITY_PATH = CONTENT_ROOT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
OUT_DIR = KLPGA_PIPELINE_ROOT / "evidence" / "hj_2026100004_kranking_acquisition"
GAME_CODE = "2026100004"
TARGET_START_DATE = "2026-10-08"


def _load_script_72():
    spec = importlib.util.spec_from_file_location(
        "collect_ok_open_72", KLPGA_PIPELINE_ROOT / "scripts" / "72_collect_ok_open_public_master.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    mod = _load_script_72()
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    target_ids = {r["player_code"] for r in identity["records"]}

    offline = mod._resolve_offline_kranking(target_ids, GAME_CODE)
    if offline is not None:
        payload = offline
        print("Used sanctioned OFFLINE K-Ranking capture (no live fetch).")
    else:
        rank_week_param, ranking_date_label, _ = resolve_ranking_week(TARGET_START_DATE)
        print(f"No offline capture found -- live fetch, requested week {ranking_date_label} "
              f"(param {rank_week_param})")
        payload = mod.collect_rankings_live(
            target_ids, rank_week_param=rank_week_param, ranking_date_label=ranking_date_label,
        )
    payload["game_code"] = GAME_CODE

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "KRANKING_REPORT.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    n_found = sum(1 for r in payload["records"] if r["validation_state"] == "PASS")
    print(f"collection_method={payload['collection_method']} week_evidence_state={payload['week_evidence_state']} "
          f"week_match={payload.get('week_match')}")
    print(f"K-RANKING found for {n_found}/{len(payload['records'])} entrants")
    print(f"Wrote {out_path}")
    print("\nNEXT: commit and push evidence/hj_2026100004_kranking_acquisition/ to neo-website-v2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
