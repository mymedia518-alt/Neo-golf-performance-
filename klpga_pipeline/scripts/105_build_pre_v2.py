"""Build and optionally freeze a validated NEO_PRE_5PROB_V2 snapshot."""
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

from klpga.backtest.point_in_time_features import (
    compute_point_in_time_features,
    features_as_flat_dict,
    load_corpus,
)
from klpga.models.candidates import fit_candidate_model, predict_candidate_model
from klpga.models.inference import _build_training_rows
from klpga.models.math_utils import clip_and_renormalize
from klpga.neo_win.pre_v2 import (
    CUT_MODEL_ID,
    DEFAULT_N_SIMULATIONS,
    MODEL_FEATURES,
    MODEL_ID,
    combine_probabilities,
    fit_cut_model,
    predict_cut,
    simulate_finish_tiers,
)
from klpga.tournament_context import load_tournament_context


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(game_code: str, db_path: Path, simulations: int, seed: int, generated_at: str) -> tuple[dict, dict]:
    context = load_tournament_context(game_code)
    cutoff = date.fromisoformat(context.start_date)
    entry_path = context.artifact_path("entry_snapshot")
    master_path = context.artifact_path("current_player_master")
    performance_path = context.artifact_path("pre_performance_snapshot")
    public_master_path = context.artifact_path("pre_public_master")
    evaluation_path = ROOT / "content" / "website_v2" / "NEO_PRE_5PROB_V2_WALK_FORWARD.json"
    for required in (entry_path, master_path, performance_path, public_master_path, evaluation_path, db_path):
        if not required.is_file():
            raise FileNotFoundError(required)
    evaluation = load(evaluation_path)
    if evaluation.get("overall_frozen_win_gate_pass") is not True:
        raise RuntimeError("V2 frozen publication criterion is not PASS")

    entry = load(entry_path)
    master = load(master_path)
    prior_public_master = load(public_master_path)
    entries = entry["entries"]
    records = master["records"]
    if int(entry["player_count"]) != 120 or len(entries) != 120 or len(records) != 120:
        raise RuntimeError("official KB field must contain exactly 120 entrants")
    entry_codes = [str(row["player_id"]) for row in entries]
    if len(set(entry_codes)) != 120:
        raise RuntimeError("official entry contains duplicate player IDs")
    master_by_code = {str(row["player_id"]): row for row in records}
    if set(master_by_code) != set(entry_codes):
        raise RuntimeError("current player master is not the exact official entry population")

    conn = sqlite3.connect(db_path)
    try:
        target_events = conn.execute(
            "SELECT COUNT(*) FROM player_event pe JOIN tournament_master tm ON tm.event_id=pe.event_id WHERE tm.game_code=?",
            (game_code,),
        ).fetchone()[0]
        target_rounds = conn.execute(
            "SELECT COUNT(*) FROM player_round pr JOIN tournament_master tm ON tm.event_id=pr.event_id WHERE tm.game_code=?",
            (game_code,),
        ).fetchone()[0]
        if target_events or target_rounds:
            raise RuntimeError("target tournament rows exist in inference DB; PRE temporal isolation failed")
        training_rows, training_tournaments = _build_training_rows(conn, game_code, cutoff)
        corpus = load_corpus(conn)
        field_rows = []
        features_by_code = {}
        for entry_row in entries:
            code = str(entry_row["player_id"])
            name = master_by_code[code].get("current_official_player_name") or entry_row["player_name"]
            features = compute_point_in_time_features(corpus, game_code, cutoff, code, name)
            flat = features_as_flat_dict(features)
            features_by_code[code] = flat
            field_rows.append({"player_code": code, "player_name": name, **flat})

        m4 = fit_candidate_model("M4", training_rows)
        win = clip_and_renormalize(predict_candidate_model(m4, field_rows))
        cut_model = fit_cut_model(training_rows)
        cut = predict_cut(cut_model, field_rows)
        tiers = simulate_finish_tiers(win, n_simulations=simulations, seed=seed)
        probabilities = combine_probabilities(cut, win, tiers)
    finally:
        conn.close()

    predictions = []
    for code in entry_codes:
        master_row = master_by_code[code]
        feature = features_by_code[code]
        predictions.append(
            {
                "playerCode": code,
                "playerName": master_row.get("current_official_player_name"),
                **probabilities[code],
                "prior_events_n": int(feature.get("prior_events_n") or 0),
                "feature_missing_rule": "training_fold_population_mean" if not feature.get("prior_events_n") else None,
            }
        )
    prediction_hash = canonical_hash(predictions)
    snapshot = {
        "schema_version": "NEO_PRE_5PROB_V2_FROZEN_V1",
        "gameCode": game_code,
        "stage": "PRE",
        "official_field_count": 120,
        "input_cutoff": f"{cutoff.isoformat()}T00:00:00+09:00",
        "model_version": MODEL_ID,
        "win_model": "M4",
        "win_model_features": list(MODEL_FEATURES),
        "cut_model": CUT_MODEL_ID,
        "cut_truth": "player_event.made_cut",
        "simulation_count": simulations,
        "random_seed": seed,
        "training_tournament_count": training_tournaments,
        "training_player_event_count": len(training_rows),
        "generated_at": generated_at,
        "source_hashes": {
            "entry_snapshot_sha256": sha256(entry_path),
            "current_player_master_sha256": sha256(master_path),
            "pre_performance_snapshot_sha256": sha256(performance_path),
            "database_sha256": sha256(db_path),
            "walk_forward_evaluation_sha256": sha256(evaluation_path),
            "model_source_sha256": sha256(ROOT / "src" / "klpga" / "neo_win" / "pre_v2.py"),
        },
        "temporal_validation": {
            "target_player_event_rows": target_events,
            "target_player_round_rows": target_rounds,
            "future_data_excluded": True,
            "later_wd_status_used": False,
            "later_wd_players_retained": ["11374", "9788"],
        },
        "prediction_values_sha256": prediction_hash,
        "predictions": predictions,
    }
    public_master = dict(prior_public_master)
    public_master.update(
        {
            "schema_version": "neo_tournament_pre_public_master_v2",
            "game_code": game_code,
            "cutoff": snapshot["input_cutoff"],
            "entry_count": 120,
            "generated_at": generated_at,
            "pre_probability_publication": {
                "status": "APPROVED",
                "model_version": MODEL_ID,
                "frozen_snapshot": f"{game_code}_PRE_5PROB_V2_FROZEN.json",
                "prediction_values_sha256": prediction_hash,
            },
            "no_unsupported_top_probabilities": False,
            "probability_distribution_contract": {
                "schema": ["cut_probability", "top20_probability", "top10_probability", "top5_probability", "win_probability"],
                "model_status": "VALIDATED",
                "publication_status": "APPROVED",
                "model_version": MODEL_ID,
                "checkpoint": "PRE",
                "provenance": f"{game_code}_PRE_5PROB_V2_FROZEN.json",
            },
        }
    )
    updated_records = []
    by_code = {row["playerCode"]: row for row in predictions}
    prior_records = prior_public_master.get("records", [])
    prior_by_code = {str(row.get("player_id")): row for row in prior_records}
    if set(prior_by_code) != set(entry_codes):
        raise RuntimeError("prior PRE public master is not the exact official entry population")
    for code in entry_codes:
        row = prior_by_code[code]
        item = dict(row)
        values = by_code[code]
        for key in ("cut_probability", "top20_probability", "top10_probability", "top5_probability", "win_probability"):
            item[key] = values[key]
        item["validation_status"] = "PASS"
        item.setdefault("provenance", {})["pre_probability"] = f"{game_code}_PRE_5PROB_V2_FROZEN.json"
        updated_records.append(item)
    public_master["records"] = updated_records
    return snapshot, public_master


def write_immutable(path: Path, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise RuntimeError(f"refusing to overwrite a different frozen snapshot: {path}")
    path.write_text(payload, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--generated-at", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    snapshot, public_master = build(args.game_code, args.db, args.simulations, args.seed, args.generated_at)
    content = ROOT / "content" / "website_v2"
    if args.freeze:
        write_immutable(content / f"{args.game_code}_PRE_5PROB_V2_FROZEN.json", snapshot)
        (content / f"{args.game_code}_PRE_PUBLIC_MASTER.json").write_text(
            json.dumps(public_master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    print(json.dumps({"gameCode": args.game_code, "field": len(snapshot["predictions"]), "prediction_values_sha256": snapshot["prediction_values_sha256"], "frozen": args.freeze}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
