"""Build the Hana PRE validation artifact with the frozen M4 pipeline.

This is a candidate-only adapter.  It reuses the production M4 fitting,
point-in-time feature extraction, cut model, and Plackett--Luce Monte Carlo
implementation; it never writes to the inference database and never changes
production artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.point_in_time_features import (  # noqa: E402
    compute_point_in_time_features,
    features_as_flat_dict,
    load_corpus,
)
from klpga.models.candidates import fit_candidate_model, predict_candidate_model  # noqa: E402
from klpga.models.inference import _build_training_rows  # noqa: E402
from klpga.models.math_utils import clip_and_renormalize  # noqa: E402
from klpga.neo_win.pre_v2 import (  # noqa: E402
    combine_probabilities,
    fit_cut_model,
    predict_cut,
    simulate_finish_tiers,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(game_code: str, cutoff: date, db_path: Path, entry_path: Path,
          simulations: int, seed: int, generated_at: str) -> dict:
    entry_doc = load(entry_path)
    entries = entry_doc["records"]
    if len(entries) != 108:
        raise RuntimeError(f"Hana official entry population must be 108, got {len(entries)}")
    codes = [str(row["player_id"]) for row in entries]
    if len(set(codes)) != len(codes):
        raise RuntimeError("Hana official entry list contains duplicate player_id values")

    conn = sqlite3.connect(db_path)
    try:
        target_events, target_rounds = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM player_event pe JOIN tournament_master tm ON tm.event_id=pe.event_id WHERE tm.game_code=?), "
            "(SELECT COUNT(*) FROM player_round pr JOIN tournament_master tm ON tm.event_id=pr.event_id WHERE tm.game_code=?)",
            (game_code, game_code),
        ).fetchone()
        if target_events or target_rounds:
            raise RuntimeError("target Hana rows already exist in inference DB; PRE temporal isolation failed")

        training_rows, training_tournaments = _build_training_rows(conn, game_code, cutoff)
        corpus = load_corpus(conn)
        field_rows = []
        features_by_code = {}
        for row in entries:
            code = str(row["player_id"])
            name = row["official_display_name"]
            flat = features_as_flat_dict(
                compute_point_in_time_features(corpus, game_code, cutoff, code, name)
            )
            features_by_code[code] = flat
            field_rows.append({"player_code": code, "player_name": name, **flat})

        fitted = fit_candidate_model("M4", training_rows)
        win = clip_and_renormalize(predict_candidate_model(fitted, field_rows))
        cut = predict_cut(fit_cut_model(training_rows), field_rows)
        tiers = simulate_finish_tiers(win, n_simulations=simulations, seed=seed)
        probabilities = combine_probabilities(cut, win, tiers)
    finally:
        conn.close()

    by_code = {str(row["player_id"]): row for row in entries}
    records = []
    for code, values in probabilities.items():
        feature = features_by_code[code]
        n = int(feature.get("prior_events_n") or 0)
        recent_n = int(feature.get("prior_recent_form_10_n") or 0)
        status = "DATA_INSUFFICIENT" if n == 0 or recent_n == 0 else "PASS"
        records.append({
            "playerCode": code,
            "playerName": by_code[code]["official_display_name"],
            "entry_category": by_code[code].get("entry_category"),
            "neo_rank": None,
            "neo_score_display": round(values["win_probability"] * 100, 2),
            "neo_score_unit": "win_probability_pct",
            "analysis_status": status,
            "data_status": "데이터 부족" if status == "DATA_INSUFFICIENT" else "검증 가능",
            **values,
            "features": feature,
        })
    records.sort(key=lambda r: (-r["win_probability"], r["playerCode"]))
    for rank, row in enumerate(records, 1):
        row["neo_rank"] = rank

    return {
        "schema_version": "HANA_2026090002_PRE_M4_60000_CANDIDATE_V1",
        "gameCode": game_code,
        "stage": "PRE",
        "tournament_name": "하나금융그룹 챔피언십",
        "publication_class": "VALIDATION_MODEL_NOT_PRODUCTION",
        "official_field_count": 108,
        "input_cutoff": f"{cutoff.isoformat()}T00:00:00+09:00",
        "model_version": "NEO_PRE_5PROB_V2",
        "win_model": "M4",
        "win_model_features": ["prior_avg_round_score_to_par", "prior_recent_form_10"],
        "simulation_count": simulations,
        "random_seed": seed,
        "training_tournament_count": training_tournaments,
        "training_player_event_count": len(training_rows),
        "target_player_event_rows": target_events,
        "target_player_round_rows": target_rounds,
        "generated_at": generated_at,
        "source_hashes": {
            "entry_list_sha256": sha256(entry_path),
            "database_sha256": sha256(db_path),
        },
        "summary": {
            "field_count": len(records),
            "analysis_pass": sum(r["analysis_status"] == "PASS" for r in records),
            "data_insufficient": sum(r["analysis_status"] == "DATA_INSUFFICIENT" for r in records),
            "probability_sum": round(sum(r["win_probability"] for r in records), 12),
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--entry", default=str(ROOT / "content/website_v2/HANA_2026090002_OFFICIAL_ENTRY_LIST_V1.json"), type=Path)
    parser.add_argument("--output", default=str(ROOT / "content/website_v2/HANA_2026090002_PRE_M4_60000_CANDIDATE_V1.json"), type=Path)
    parser.add_argument("--cutoff", default="2026-09-17")
    parser.add_argument("--simulations", default=60000, type=int)
    parser.add_argument("--seed", default=20260915, type=int)
    args = parser.parse_args()
    if args.simulations != 60000:
        raise SystemExit("This Hana validation run is fixed at --simulations 60000")
    result = build("2026090002", date.fromisoformat(args.cutoff), args.db, args.entry,
                   args.simulations, args.seed,
                   datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    print("output", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
