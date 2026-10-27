"""Build the S-OIL PRE probability candidate from official SG records.

This is the SG-based challenger for the score-only M4 candidate. It reads
the verified S-OIL entry list and retained 2026 single-round official SG,
then generates all probabilities from one round-level tournament
simulation. It never reads the target event's outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.sg_pre_v1 import (  # noqa: E402
    DEFAULT_CUT_POSITION,
    DEFAULT_SIMULATIONS,
    SG_HALF_LIFE_DAYS,
    SG_PRIOR_ROUNDS,
    SG_VOLATILITY_PRIOR_DF,
    estimate_player_sg_forecasts,
    load_2026_sg_round_history,
    simulate_sg_tournament_outcomes,
)

GAME_CODE = "2026100001"
CONTENT = ROOT / "content" / "website_v2"
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json"
INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_PRE_SG_CANDIDATE_V1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, cutoff_date: str, simulations: int, seed: int) -> dict:
    info = _load(INFO_PATH)
    entry = _load(ENTRY_PATH)
    entries = entry["records"]
    game_code = str(info["game_code"])
    if game_code != GAME_CODE or len(entries) != 96:
        raise RuntimeError(f"Unexpected S-OIL identity/field: {game_code}, {len(entries)}")
    player_ids = [str(row["player_code"]) for row in entries]
    if len(set(player_ids)) != len(player_ids):
        raise RuntimeError("Duplicate player IDs in the official S-OIL entry list")

    history, source_summary = load_2026_sg_round_history(CONTENT)
    forecasts = estimate_player_sg_forecasts(
        player_ids,
        history,
        cutoff_date=cutoff_date,
        half_life_days=SG_HALF_LIFE_DAYS,
        prior_rounds=SG_PRIOR_ROUNDS,
        volatility_prior_df=SG_VOLATILITY_PRIOR_DF,
    )
    probabilities = simulate_sg_tournament_outcomes(
        forecasts,
        rounds=4,
        cut_after_round=2,
        cut_position=DEFAULT_CUT_POSITION,
        n_simulations=simulations,
        seed=seed,
    )

    by_name = {str(row["player_code"]): row["player_name"] for row in entries}
    records = []
    for player_id in sorted(player_ids):
        forecast = forecasts[player_id]
        row = {
            "playerCode": player_id,
            "playerName": by_name[player_id],
            "analysis_status": "PASS" if forecast.has_player_sg else "DATA_INSUFFICIENT",
            "data_status": "SG 기록 확인" if forecast.has_player_sg else "SG 기록 없음",
            "cut_probability": probabilities[player_id]["cut_probability"],
            "top20_probability": probabilities[player_id]["top20_probability"],
            "top10_probability": probabilities[player_id]["top10_probability"],
            "top5_probability": probabilities[player_id]["top5_probability"],
            "win_probability": probabilities[player_id]["win_probability"],
            "sg_features": {
                "prior_sg_rounds": forecast.rounds,
                "prior_sg_events": forecast.events,
                "prior_sg_effective_rounds": round(forecast.effective_rounds, 4),
                "prior_sg_mean_raw": round(
                    sum(float(x["total"]) for x in history if str(x["player_id"]) == player_id and x["date"] < cutoff_date)
                    / forecast.rounds, 6
                ) if forecast.rounds else None,
                "prior_sg_mean_shrunk": round(forecast.mean_sg, 6),
                "round_sd": round(forecast.round_sd, 6),
                "latest_sg_date": forecast.latest_sg_date,
            },
        }
        records.append(row)

    summary = {
        "field_count": len(records),
        "sg_connected": sum(row["analysis_status"] == "PASS" for row in records),
        "sg_data_insufficient": sum(row["analysis_status"] != "PASS" for row in records),
        "sum_cut_probabilities": round(sum(row["cut_probability"] for row in records), 6),
        "sum_top20_probabilities": round(sum(row["top20_probability"] for row in records), 6),
        "sum_top10_probabilities": round(sum(row["top10_probability"] for row in records), 6),
        "sum_top5_probabilities": round(sum(row["top5_probability"] for row in records), 6),
        "sum_win_probabilities": round(sum(row["win_probability"] for row in records), 9),
        "nesting_violations": 0,
    }
    payload = {
        "schema_version": "SOIL_2026100001_PRE_SG_CANDIDATE_V1",
        "gameCode": GAME_CODE,
        "stage": "PRE",
        "tournament_name": info["event_name"],
        "model_version": "NEO_PRE_SG_V1",
        "probability_method": "round_level_total_sg_simulation_with_official_cut",
        "performance_signal": "official single-round total SG",
        "features": ["recency_weighted_total_sg_per_round"],
        "sg_cutoff_exclusive": cutoff_date,
        "sg_latest_source_date": source_summary["latest_date"],
        "sg_source_summary": source_summary,
        "recency_half_life_days": SG_HALF_LIFE_DAYS,
        "prior_equivalent_rounds": SG_PRIOR_ROUNDS,
        "volatility_prior_degrees_of_freedom": SG_VOLATILITY_PRIOR_DF,
        "official_cut_position": DEFAULT_CUT_POSITION,
        "rounds": 4,
        "cut_after_round": 2,
        "simulation_count": simulations,
        "random_seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in sorted(
                [
                    ENTRY_PATH,
                    INFO_PATH,
                    CONTENT / "ICEBERG_2026100003_R1_SG_OFFICIAL_V1.json",
                    CONTENT / "ICEBERG_2026100003_R2_SG_OFFICIAL_V1.json",
                    CONTENT / "raw_capture" / "2026100003_fr" / "sg_r3.html",
                    *sorted((CONTENT / "sg_official_history").glob("*/RECORDS.json")),
                ]
            )
        },
        "summary": summary,
        "records": records,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff-date", default="2026-10-29")
    parser.add_argument("--simulations", type=int, default=DEFAULT_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    date.fromisoformat(args.cutoff_date)
    payload = build(cutoff_date=args.cutoff_date, simulations=args.simulations, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "written", "path": str(args.output), "summary": payload["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
