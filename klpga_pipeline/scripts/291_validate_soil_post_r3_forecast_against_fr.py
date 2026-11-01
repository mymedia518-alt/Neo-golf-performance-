"""Validate the FROZEN R3-point-in-time forecast for 제20회 S-OIL
챔피언십 (game_code 2026100001) against the real, final FR result.

Reads the forecast ONLY from the sha256-verified archive copy at
content/website_v2/archive/2026100001/r3/ (never the live working-tree
file, and never re-derives or recomputes a single probability) -- the
forecast itself is never touched by this script. Joins it against
SOIL_2026100001_FR_OFFICIAL_V1.json (scripts/289), the real final
result, and writes the comparison to a separate artifact
(SOIL_2026100001_R3_FORECAST_FR_VALIDATION_V1.json). Follows the same
pattern already established by
scripts/116_validate_frozen_r2_against_r3.py for a prior tournament.

Every forecast row and every actual-result row is preserved in the
join, mismatches included -- nothing here is ever hidden, dropped, or
rewritten to look better than it was.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100001"

ARCHIVE_MANIFEST = CONTENT / "archive" / GAME_CODE / "r3" / "R3_ARCHIVE_MANIFEST_V1.json"
FR_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_FR_OFFICIAL_V1.json"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_R3_FORECAST_FR_VALIDATION_V1.json"


def main() -> None:
    manifest = json.loads(ARCHIVE_MANIFEST.read_text(encoding="utf-8"))
    forecast_record = next(
        r for r in manifest["records"]
        if r["original_path"].endswith("SOIL_2026100001_POST_R3_FORECAST_V1.json")
    )
    forecast_path = ROOT.parent / forecast_record["archive_path"]
    forecast_bytes = forecast_path.read_bytes()
    actual_sha = hashlib.sha256(forecast_bytes).hexdigest()
    assert actual_sha == forecast_record["sha256"], (
        f"archived forecast sha256 mismatch: manifest says {forecast_record['sha256']}, "
        f"file is actually {actual_sha} -- refusing to validate against a file that may have "
        f"been altered since it was frozen"
    )
    forecast = json.loads(forecast_bytes)
    assert forecast["stage"] == "POST_R3"

    fr = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    actual_by_id = {r["player_id"]: r for r in fr["records"]}

    forecast_ids = {r["player_id"] for r in forecast["field_records"]}
    actual_ids = set(actual_by_id)
    assert forecast_ids == actual_ids, (
        f"forecast field != FR official field -- forecast-only: {sorted(forecast_ids - actual_ids)}, "
        f"FR-only: {sorted(actual_ids - forecast_ids)}"
    )

    joined = []
    for f in forecast["field_records"]:
        a = actual_by_id[f["player_id"]]
        joined.append({
            "player_id": f["player_id"],
            "player_name": f["player_name"],
            "forecast_known_r1_r2_r3_scores": {"r1": f["r1_score"], "r2": f["r2_score"], "r3": f["r3_score"]},
            "forecast_top20_probability": f["top20_probability"],
            "forecast_top10_probability": f["top10_probability"],
            "forecast_top5_probability": f["top5_probability"],
            "forecast_win_probability": f["win_probability"],
            "actual_final_rank": a["final_rank_numeric"],
            "actual_final_rank_label": a["final_rank"],
            "actual_tie": a["final_tie"],
            "actual_fr_score": a["r4_score"],
            "actual_total_score": a["total_score"],
            "actual_score_to_par": a["score_to_par"],
            "actual_status": a["status"],
        })

    top_pick = max(joined, key=lambda r: r["forecast_win_probability"])
    actual_winner = next(r for r in joined if r["actual_final_rank"] == 1)
    top_pick_matched_actual_winner = top_pick["player_id"] == actual_winner["player_id"]

    validation = {}
    for key, thr in (("win", 1), ("top5", 5), ("top10", 10), ("top20", 20)):
        actual_in_band = sorted(
            [r for r in joined if r["actual_final_rank"] <= thr],
            key=lambda r: r["actual_final_rank"],
        )
        forecast_top_n_by_prob = sorted(joined, key=lambda r: -r[f"forecast_{key}_probability"])[:thr]
        hits = sum(1 for r in forecast_top_n_by_prob if r["actual_final_rank"] <= thr)
        validation[key] = {
            "threshold": thr,
            "actual_players_in_band": [{"player_id": r["player_id"], "player_name": r["player_name"], "actual_final_rank": r["actual_final_rank"]} for r in actual_in_band],
            "forecast_top_n_by_probability": [{"player_id": r["player_id"], "player_name": r["player_name"], "probability": r[f"forecast_{key}_probability"], "actual_final_rank": r["actual_final_rank"]} for r in forecast_top_n_by_prob],
            "top_probability_selection_hits": hits,
            "top_probability_selection_hit_rate": hits / thr,
        }

    out = {
        "schema_version": "SOIL_2026100001_R3_FORECAST_FR_VALIDATION_V1",
        "game_code": GAME_CODE,
        "purpose": (
            "Compares the frozen R3-point-in-time forecast (TOP20/TOP10/TOP5/win "
            "probabilities, archived before any FR data existed) against the real "
            "final FR result. The forecast file itself is never modified by this "
            "script; this is a separate, additive artifact."
        ),
        "forecast_provenance": {
            "archive_path": str(forecast_path.relative_to(ROOT.parent)),
            "sha256": actual_sha,
            "generated_at": forecast["generated_at"],
            "sg_cutoff_exclusive": forecast["sg_cutoff_exclusive"],
        },
        "fr_result_provenance": {
            "path": f"content/website_v2/{FR_OFFICIAL_PATH.name}",
            "winner_player_id": fr["winner_player_id"],
            "winner_player_name": fr["winner_player_name"],
            "winner_score_to_par": fr["winner_score_to_par"],
        },
        "join": {
            "forecast_rows": len(joined),
            "actual_rows": len(actual_by_id),
            "matched": len(joined),
        },
        "outcome_definitions": {
            "WIN": "actual_final_rank == 1",
            "TOP5": "actual_final_rank <= 5",
            "TOP10": "actual_final_rank <= 10",
            "TOP20": "actual_final_rank <= 20",
        },
        "top_pick_vs_actual_result": {
            "forecast_top_win_probability_player": {"player_id": top_pick["player_id"], "player_name": top_pick["player_name"], "win_probability": top_pick["forecast_win_probability"]},
            "actual_winner": {"player_id": actual_winner["player_id"], "player_name": actual_winner["player_name"]},
            "matched": top_pick_matched_actual_winner,
            "note": (
                "Recorded as-is, not adjusted: the forecast's single highest win-probability pick "
                f"did {'' if top_pick_matched_actual_winner else 'NOT '}go on to win."
            ),
        },
        "validation": validation,
        "full_join": sorted(joined, key=lambda r: r["actual_final_rank"]),
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "top_pick_matched_actual_winner": top_pick_matched_actual_winner,
        "win_hit_rate": validation["win"]["top_probability_selection_hit_rate"],
        "top5_hit_rate": validation["top5"]["top_probability_selection_hit_rate"],
        "top10_hit_rate": validation["top10"]["top_probability_selection_hit_rate"],
        "top20_hit_rate": validation["top20"]["top_probability_selection_hit_rate"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
