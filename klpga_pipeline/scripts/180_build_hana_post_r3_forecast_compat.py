"""HANA FINAL VALIDATION -- schema-compatibility bridge.

JUDGMENT CALL (flagged explicitly to the operator; see the FINAL
validation report for the full explanation): the already-existing
generic modules klpga.neo_win.final_pre_freeze / final_validator were
built against, and so far only ever exercised against, the KB
(2026090003) PRE-FINAL forecast's exact JSON shape (content/website_v2/
2026090003_POST_R3_FINAL_FORECAST.json: stage="POST_R3",
future_data_excluded=true, an explicit r3_freeze_sha256, and a
per-player neo_final_rank already baked in from KB's own Monte Carlo
run). Hana's real, already-frozen, IMMUTABLE PRE-FINAL forecast
(content/website_v2/2026090002_POST_R4_FINAL_PREVIEW.json) carries the
SAME underlying probabilities (win_pct/top5_pct/top10_pct/top20_pct,
built exclusively from R1-R3 data, R3 SG explicitly excluded as a
predictive feature) but under different top-level metadata keys
(stage="post_r3_pre_final", no top-level future_data_excluded key) and
without a precomputed neo_final_rank per player.

This script produces content/website_v2/2026090002_POST_R3_FINAL_FORECAST.json
-- a mechanical, lossless schema bridge, NOT a recomputation:
  - win_pct / top5_pct / top10_pct / top20_pct / player_id / player_name
    are copied byte-for-byte (same float values, same precision) from
    the frozen 2026090002_POST_R4_FINAL_PREVIEW.json -- verified below
    by an exact-equality assertion against the original file's own
    values, and the original file's own sha256 is asserted unchanged
    both before and after this script runs.
  - neo_final_rank is DERIVED (not taken from any hidden field) by
    sorting all 64 players by win_pct descending, ties broken by
    top10_pct desc, then top5_pct desc, then top20_pct desc, then
    player_id ascending -- a fully deterministic, generic, disclosed
    proxy for "NEO's probability-ranked candidate order". This is NOT
    the same statistic as KB's own neo_final_rank (which came from each
    player's per-simulation mean finishing position across the full
    Monte Carlo run, a number the frozen preview artifact does not
    expose) -- it is reused here ONLY because Phase 6 of the FINAL
    build explicitly calls for "NEO's probability-ranked candidates",
    which is exactly what this ordering is.
  - stage/future_data_excluded/final_round_number/source_round/
    r3_freeze_sha256 are set to their real, true values for this
    tournament (Hana's final round IS round 4, so its PRE-FINAL
    snapshot legitimately follows R3; r3_freeze_sha256 is the REAL
    sha256 of content/website_v2/2026090002_R3_FROZEN_EVIDENCE.json,
    computed below, never fabricated).

This bridge changes NOTHING about final_pre_freeze.py / final_validator.py
themselves (zero risk of regressing the KB 2026090003 path or its own
tests) -- it only supplies those already-existing, already-tested
generic modules with an input in the one shape they already expect, so
they can be reused as-is rather than duplicated or forked.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

SOURCE_PATH = CONTENT / "2026090002_POST_R4_FINAL_PREVIEW.json"
R3_FREEZE_PATH = CONTENT / "2026090002_R3_FROZEN_EVIDENCE.json"
OUT_PATH = CONTENT / "2026090002_POST_R3_FINAL_FORECAST.json"


def _rank_key(r: dict) -> tuple:
    return (-r["win_pct"], -r["top10_pct"], -r["top5_pct"], -r["top20_pct"], int(r["player_id"]))


def main() -> None:
    source_bytes_before = SOURCE_PATH.read_bytes()
    source_sha_before = hashlib.sha256(source_bytes_before).hexdigest()
    source = json.loads(source_bytes_before)

    r3_freeze_bytes = R3_FREEZE_PATH.read_bytes()
    r3_freeze_sha256 = hashlib.sha256(r3_freeze_bytes).hexdigest()

    ordered = sorted(source["records"], key=_rank_key)
    records = []
    for rank, r in enumerate(ordered, start=1):
        records.append({
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "r1_score_to_par": r["r1_score_to_par"],
            "r2_score_to_par": r["r2_score_to_par"],
            "r3_score_to_par": r["r3_score_to_par"],
            "r3_total_to_par": r["r3_total_under_par"],
            "win_pct": r["win_pct"],
            "top5_pct": r["top5_pct"],
            "top10_pct": r["top10_pct"],
            "top20_pct": r["top20_pct"],
            "neo_final_rank": rank,
            "neo_final_rank_source": "derived_probability_rank_v1",
        })

    # Byte-exact verification: every probability value in the bridge
    # equals the frozen source's own value, no recomputation.
    by_id_source = {str(r["player_id"]): r for r in source["records"]}
    for rec in records:
        src = by_id_source[str(rec["player_id"])]
        for field in ("win_pct", "top5_pct", "top10_pct", "top20_pct"):
            assert rec[field] == src[field], f"value drift for {rec['player_id']} field {field}"

    out = {
        "schema_version": 1,
        "artifact": "post_r3_final_forecast",
        "game_code": "2026090002",
        "tournament_name": "하나금융그룹 챔피언십",
        "stage": "POST_R3",
        "source_round": 3,
        "final_round_number": 4,
        "remaining_rounds": 1,
        "r3_freeze_artifact": "2026090002_R3_FROZEN_EVIDENCE.json",
        "r3_freeze_sha256": r3_freeze_sha256,
        "future_data_excluded": True,
        "feature_cutoff": "END_OF_R3",
        "simulation_engine": source.get("simulation_engine"),
        "n_simulations": source.get("n_simulations"),
        "seed": source.get("seed"),
        "win_probability_sum_pct": source.get("win_probability_sum_pct"),
        "code_commit": "bridge_from_frozen_pre_final_preview_artifact",
        "build_id": "hana_post_r3_final_forecast_compat_bridge_v1",
        "bridge_provenance": {
            "derived_from_sha256": source_sha_before,
            "derived_from_note": (
                "mechanical schema bridge over the already-frozen, immutable Hana PRE-FINAL "
                "preview artifact (see scripts/180_build_hana_post_r3_forecast_compat.py for "
                "the exact field mapping and the neo_final_rank derivation method); no "
                "probability value is recomputed anywhere in this file"
            ),
            "neo_final_rank_derivation": (
                "sorted by win_pct desc, ties broken by top10_pct desc, top5_pct desc, "
                "top20_pct desc, player_id asc -- a probability-rank proxy, NOT the original "
                "per-simulation mean finishing position (not exposed by the frozen artifact)"
            ),
        },
        "records": records,
    }

    assert not OUT_PATH.exists(), f"refusing to overwrite existing bridge artifact: {OUT_PATH}"
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    source_sha_after = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    assert source_sha_after == source_sha_before, "REFUSING: frozen source forecast was modified by this script"

    print(f"wrote {OUT_PATH}")
    print(f"source (frozen, untouched) sha256: {source_sha_before}")
    print(f"r3_freeze_sha256: {r3_freeze_sha256}")
    print(f"num records: {len(records)}")


if __name__ == "__main__":
    main()
