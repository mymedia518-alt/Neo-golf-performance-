"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- build and freeze
the real, full-field Stableford V1 pre-event snapshot for all 108
official entrants.

Applies klpga.website_v2.stableford_2026_preevent.build_2026_field_
snapshot (the frozen V1 formula, completely unchanged) to:
  - content/website_v2/2026100004_CANONICAL_PLAYER_IDENTITY_V1.json
    (108 real entrants, playerCode-reconciled)
  - content/website_v2/STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json
    + evidence/stableford_prior_2026/ (24 real prior tournaments,
    SOURCE_PASS 24/24, 0 leakage)

No new network access. No new model, weights, or threshold. Writes a
frozen, hashed snapshot matching the same convention as the 2023/2024/
2025 STABLEFORD_<year>_FROZEN_PREEVENT_SNAPSHOT_V1.json artifacts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.website_v2.stableford_2026_preevent import build_2026_field_snapshot  # noqa: E402

CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
EVIDENCE_ROOT = KLPGA_PIPELINE_ROOT / "evidence"

IDENTITY_PATH = CONTENT_ROOT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
MANIFEST_PATH = CONTENT_ROOT / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
PRIOR_DIR = EVIDENCE_ROOT / "stableford_prior_2026"
OUT_PATH = CONTENT_ROOT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"


def main() -> int:
    records = build_2026_field_snapshot(IDENTITY_PATH, MANIFEST_PATH, PRIOR_DIR)
    payload = [asdict(r) for r in records]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=False, default=list)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    rankable = [r for r in records if r.pre_event_rank is not None]
    thin = [r for r in rankable if r.data_status == "DATA_LIMITED_THIN_SAMPLE"]
    no_data = [r for r in records if r.data_status == "DATA_LIMITED_NO_PRIOR_DATA"]

    out = {
        "schema_version": 1,
        "sha256": digest,
        "target_game_code": "2026100004",
        "target_start_date": "2026-10-08",
        "field_size": len(records),
        "eligible_count": len(rankable),
        "data_limited_thin_sample_count": len(thin),
        "data_limited_no_prior_data_count": len(no_data),
        "formula": "net_expected_value = 8*P(albatross) + 5*P(eagle) + 2*P(birdie) - 1*P(bogey) - 3*P(double_or_worse), "
                   "unchanged from klpga.website_v2.stableford_player_value.from_season_rates",
        "records": payload,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"field_size={len(records)} eligible={len(rankable)} "
          f"thin_sample={len(thin)} no_prior_data={len(no_data)}")
    print(f"sha256={digest}")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
