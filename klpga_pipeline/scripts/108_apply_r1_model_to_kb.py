"""Apply the frozen NEO_R1_MODEL_V1 to KB 2026090003's 118 R1-active
players, exactly once, no refitting. Requires
content/website_v2/TOURNAMENT_MASTER_DATES_V1.json to already exist
(produced by scripts/107_extract_tournament_master_dates.py against a
real local sqlite corpus) -- refuses to run without it rather than
falling back to an unverified date source.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.kb_neo_v1_score import score_cohort  # noqa: E402
from klpga.neo_win.r1_model_v1 import field_relative_r1_z, predict_r1_tiers  # noqa: E402

GAME_CODE = "2026090003"
KB_CUTOFF = "2026-09-10"


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def sha(name: str) -> str:
    return hashlib.sha256((CONTENT / name).read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    dates_path = CONTENT / "TOURNAMENT_MASTER_DATES_V1.json"
    if not dates_path.exists():
        print("TOURNAMENT_MASTER_DATES_V1.json missing -- run scripts/107_extract_tournament_master_dates.py against the local sqlite corpus first.", file=sys.stderr)
        return 1

    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    assert sha("NEO_RANKING_VALIDATION_MODEL_V1.json") == "0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643"
    weights = {name: float(spec["weight"]) for name, spec in config["features"].items()}
    minimum = int(config["eligibility"]["minimum_sg_events"])

    sg_warehouse = load("historical_sg_warehouse_corrected.json")
    tm_dates = load("TOURNAMENT_MASTER_DATES_V1.json")
    gc_date = dict(tm_dates["dates"])

    entry = load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    kb_ids = [e["player_id"] for e in entry["entries"]]
    assert len(kb_ids) == 120

    kb_scores, kb_contrib = score_cohort(kb_ids, KB_CUTOFF, sg_warehouse, gc_date, weights, minimum)

    r1ev = load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    active_players = r1ev["players"]
    wd_players = r1ev["official_wd"]
    assert len(active_players) == 118
    assert len(wd_players) == 2
    entry_ids = {e["player_id"] for e in entry["entries"]}
    assert entry_ids == ({p["playerCode"] for p in active_players} | {w["playerCode"] for w in wd_players})

    topars = [int(p["toPar"]) for p in active_players]
    field_mean = statistics.mean(topars)
    field_std = statistics.pstdev(topars) or 1.0

    predictions = []
    excluded = []
    for p in active_players:
        pid = p["playerCode"]
        r1_to_par = int(p["toPar"])
        r1_z = field_relative_r1_z(r1_to_par, field_mean, field_std)
        if pid not in kb_scores:
            excluded.append({"player_id": pid, "player_name": p["name"], "reason": "INSUFFICIENT_PRE_HISTORY_FOR_NEO_V1_SCORE"})
            continue
        pre_score = kb_scores[pid]
        tiers = predict_r1_tiers(pre_score, r1_z)
        if not tiers.is_coherent():
            raise AssertionError(f"coherence violation for {pid}: {tiers}")
        predictions.append({
            "player_id": pid, "player_name": p["name"],
            "r1_score": p["r1Score"], "r1_to_par": r1_to_par, "r1_rank_display": p["rank"],
            "pre_score": round(pre_score, 8), "r1_z": round(r1_z, 8),
            "cut": round(tiers.cut, 8), "top20": round(tiers.top20, 8),
            "top10": round(tiers.top10, 8), "top5": round(tiers.top5, 8), "win": round(tiers.win, 8),
        })

    prediction_values_sha256 = hashlib.sha256(
        json.dumps(predictions, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    freeze = {
        "schema_version": "kb_r1_5prob_frozen_v1",
        "game_code": GAME_CODE,
        "model_id": "NEO_R1_MODEL_V1",
        "model_freeze_sha256": sha("NEO_R1_MODEL_V1_FREEZE.json"),
        "neo_v1_score_config_sha256": sha("NEO_RANKING_VALIDATION_MODEL_V1.json"),
        "tournament_master_dates_sha256": sha("TOURNAMENT_MASTER_DATES_V1.json"),
        "official_r1_evidence_sha256": sha(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json"),
        "entry_snapshot_sha256": sha(f"{GAME_CODE}_ENTRY_SNAPSHOT.json"),
        "generated_at_utc": now(),
        "official_entry_count": 120,
        "r1_active_count": 118,
        "official_wd_count": 2,
        "official_wd": wd_players,
        "predicted_count": len(predictions),
        "excluded_count": len(excluded),
        "excluded_players": excluded,
        "r1_field_mean_to_par": field_mean,
        "r1_field_stddev_to_par": field_std,
        "cutoff": KB_CUTOFF,
        "future_data_excluded": True,
        "refit_performed": False,
        "prediction_values_sha256": prediction_values_sha256,
        "predictions": predictions,
    }

    output_path = CONTENT / f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json"
    output_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output_path), "predicted_count": len(predictions), "excluded_count": len(excluded),
        "prediction_values_sha256": prediction_values_sha256,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
