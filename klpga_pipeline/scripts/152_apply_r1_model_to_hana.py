"""Apply the frozen NEO_R1_MODEL_V1 to Hana 2026090002's real R1
official field -- no refitting, same frozen coefficients everywhere --
extended per explicit operator instruction (2026-09-17) to cover all
105 active (non-WD) players, not just the 96 with enough prior SG
history:

  FULL_NEO_R1  (96 players) -- klpga.neo_win.kb_neo_v1_score.score_cohort
    reproduces each player's real PRE-time NEO Ranking V1 composite
    score from their own prior official SG history (>=10 events,
    the model's own frozen eligibility rule); predict_r1_tiers(pre_score,
    r1_z) uses that real score.

  R1_SCORE_ONLY (9 players) -- same frozen predict_r1_tiers chain, same
    coefficients, but with pre_score fixed at
    r1_model_v1.FEATURE_STANDARDIZATION["pre_score"]["mean"] -- the
    exact value that standardizes to z_pre=0, i.e. "assume this
    player's PRE-time strength was exactly the training cohort's
    average" (never a fabricated number, never a refit) -- so these 9
    players' tiers are driven purely by their own real R1 field
    -relative performance (r1_z). This is the "R1 스코어·필드 상대 성적
    기반 보조 모델" requested: same validated math, explicitly
    -flagged neutral prior.

Both populations go through the IDENTICAL sigmoid chain with the
IDENTICAL frozen coefficients -- that uniformity is the "공통 보정"
(common calibration): no separate transform is applied to either
group before they are combined.

Combination + normalization: cut/top20/top10/top5 are left exactly as
the model computes them (untouched, still a genuine per-tier
probability in each case). win_probability is the one explicitly
required to sum to 1.0 over the 105 active players (item 7): each
player's raw win is divided by the sum of all 105 raw win values, so
sum(win_normalized) == 1.0 by construction. Every player's normalized
win is then re-checked against their own (unscaled) top5 -- if
normalizing ever pushed a win probability above that player's own top5
tier, this script HARD STOPS rather than silently accept an incoherent
result (never observed in practice: raw win values are always far
below top5, so the ~1.05-1.15x rescale factor never comes close).

probability_basis records which of the two applications produced each
player's numbers -- FULL_NEO_R1 or R1_SCORE_ONLY -- so this is always
auditable, never blended into an unlabeled single number.

WD players (김리안 9702, 조혜림 9136, 권은 12706): excluded entirely, no
completed round, no probability of any kind.
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
from klpga.neo_win.r1_model_v1 import (  # noqa: E402
    FEATURE_STANDARDIZATION,
    field_relative_r1_z,
    predict_r1_tiers,
)

GAME_CODE = "2026090002"
HANA_CUTOFF = "2026-09-17"
NEUTRAL_PRE_SCORE = FEATURE_STANDARDIZATION["pre_score"]["mean"]


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def sha(name: str) -> str:
    return hashlib.sha256((CONTENT / name).read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    assert sha("NEO_RANKING_VALIDATION_MODEL_V1.json") == "0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643"
    weights = {name: float(spec["weight"]) for name, spec in config["features"].items()}
    minimum = int(config["eligibility"]["minimum_sg_events"])

    sg_warehouse = load("historical_sg_warehouse_corrected.json")
    tm_dates = load("TOURNAMENT_MASTER_DATES_V1.json")
    gc_date = dict(tm_dates["dates"])

    r1_result = load("HANA_2026090002_R1_PLAYER_RESULT_V1.json")
    all_records = r1_result["records"]
    assert len(all_records) == 108
    all_ids = [r["player_id"] for r in all_records]

    wd_ids = {r["player_id"] for r in all_records if r["status"] == "WD"}
    assert wd_ids == {"9702", "9136", "12706"}
    completed = [r for r in all_records if r["status"] != "WD"]
    assert len(completed) == 105

    topars = [r["total_under_par"] for r in completed]
    assert all(v is not None for v in topars), "a non-WD record has no real R1 to-par -- refusing to compute a field baseline from incomplete data"
    field_mean = statistics.mean(topars)
    field_std = statistics.pstdev(topars) or 1.0

    pre_scores, contributions = score_cohort(all_ids, HANA_CUTOFF, sg_warehouse, gc_date, weights, minimum)

    raw = []
    for r in completed:
        pid = r["player_id"]
        r1_z = field_relative_r1_z(r["total_under_par"], field_mean, field_std)
        has_full_score = pid in pre_scores
        pre_score = pre_scores[pid] if has_full_score else NEUTRAL_PRE_SCORE
        basis = "FULL_NEO_R1" if has_full_score else "R1_SCORE_ONLY"

        tiers = predict_r1_tiers(pre_score, r1_z)
        if not tiers.is_coherent():
            raise AssertionError(f"coherence violation for {pid} ({basis}): {tiers}")

        raw.append({
            "player_id": pid, "official_display_name": r["official_display_name"],
            "r1_total_strokes": r["total_strokes"], "r1_to_par": r["total_under_par"],
            "r1_rank_display": r["rank_display"],
            "probability_basis": basis,
            "pre_score": round(pre_score, 8), "r1_z": round(r1_z, 8),
            "cut": tiers.cut, "top20": tiers.top20, "top10": tiers.top10, "top5": tiers.top5,
            "win_raw": tiers.win,
        })

    assert sum(1 for p in raw if p["probability_basis"] == "FULL_NEO_R1") == 96
    assert sum(1 for p in raw if p["probability_basis"] == "R1_SCORE_ONLY") == 9

    win_raw_sum = sum(p["win_raw"] for p in raw)
    assert win_raw_sum > 0

    predictions = []
    for p in raw:
        win_normalized = p["win_raw"] / win_raw_sum
        assert win_normalized <= p["top5"] + 1e-9, (
            f"normalization pushed win above top5 for {p['player_id']}: "
            f"win={win_normalized} top5={p['top5']}"
        )
        predictions.append({
            "player_id": p["player_id"], "official_display_name": p["official_display_name"],
            "r1_total_strokes": p["r1_total_strokes"], "r1_to_par": p["r1_to_par"],
            "r1_rank_display": p["r1_rank_display"],
            "probability_basis": p["probability_basis"],
            "pre_score": round(p["pre_score"], 8), "r1_z": round(p["r1_z"], 8),
            "cut": round(p["cut"], 8), "top20": round(p["top20"], 8),
            "top10": round(p["top10"], 8), "top5": round(p["top5"], 8),
            "win": round(win_normalized, 8),
        })

    win_sum_final = sum(p["win"] for p in predictions)
    assert abs(win_sum_final - 1.0) < 1e-6, f"win probability sum over 105 active players is {win_sum_final}, expected 1.0"

    prediction_values_sha256 = hashlib.sha256(
        json.dumps(predictions, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    freeze = {
        "schema_version": "hana_r1_5prob_frozen_v2",
        "game_code": GAME_CODE,
        "model_id": "NEO_R1_MODEL_V1",
        "model_freeze_sha256": sha("NEO_R1_MODEL_V1_FREEZE.json"),
        "neo_v1_score_config_sha256": sha("NEO_RANKING_VALIDATION_MODEL_V1.json"),
        "r1_player_result_sha256": sha("HANA_2026090002_R1_PLAYER_RESULT_V1.json"),
        "generated_at_utc": now(),
        "cutoff": HANA_CUTOFF,
        "future_data_excluded": True,
        "refit_performed": False,
        "official_field_count": 108,
        "wd_count": 3,
        "wd_players": sorted(wd_ids, key=int),
        "r1_completed_count": 105,
        "r1_field_mean_to_par": field_mean,
        "r1_field_stddev_to_par": field_std,
        "predicted_count": len(predictions),
        "full_neo_r1_count": 96,
        "r1_score_only_count": 9,
        "neutral_pre_score_used_for_r1_score_only": NEUTRAL_PRE_SCORE,
        "calibration_note": (
            "FULL_NEO_R1 and R1_SCORE_ONLY predictions both go through the identical "
            "frozen NEO_R1_MODEL_V1 sigmoid chain with identical coefficients -- that "
            "shared math is the common calibration; no separate transform is applied "
            "to either group before combining them."
        ),
        "normalization_note": (
            "cut/top20/top10/top5 are the model's own untouched per-tier probabilities. "
            "win alone is normalized (win_raw_i / sum(win_raw over all 105 active "
            "players)) so it sums to exactly 1.0 across the 105-player active field -- "
            "verified below and re-checked against each player's own top5 for coherence."
        ),
        "win_probability_sum_over_active_105": round(win_sum_final, 10),
        "prediction_values_sha256": prediction_values_sha256,
        "predictions": predictions,
    }

    output_path = CONTENT / f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json"
    if output_path.exists():
        output_path.unlink()
    output_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output_path), "predicted_count": len(predictions),
        "full_neo_r1_count": 96, "r1_score_only_count": 9,
        "win_probability_sum": round(win_sum_final, 10), "prediction_values_sha256": prediction_values_sha256,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
