"""Build the 제20회 S-OIL 챔피언십 (game_code 2026100001) PRE M4
win-probability candidate -- ported line-for-line from scripts/242_
build_iceberg_2026100003_pre_m4.py (itself ported line-for-line from
193/130's real, production M4 fitting / point-in-time feature
extraction / cut model / Plackett-Luce Monte Carlo pipeline). Zero
changes to the fitting/feature/cut/simulation logic itself -- same
procedure, same settings (same candidate id "M4", same feature set,
same n_simulations=60000), only this tournament's own identity/paths/
field-size differ. Never a new, unvalidated methodology.

WAREHOUSE: scripts/274_build_m4_training_warehouse_soil.py rebuilds the
same 10-tournament corpus scripts/241 already built for 2026100003's
own PRE M4 run (2026090002, 2026090003, 2026100005, 2026080001-4,
2026070001-3 -- all real official round-by-round scores via neo-sync
stage="results"), re-validated against THIS target's 2026-10-29 start
date (clears MIN_TRAINING_TOURNAMENTS=10 with zero leakage, an even
wider margin than 2026100003's own run had).

VALIDATION EVIDENCE ALREADY IN THIS REPO (not re-derived here): the
underlying V2B_M4_PL_PLUS_CUT_LOGIT model (M4 win weights + a
fold-fitted cut logistic) is the one frozen and walk-forward-validated
in klpga_pipeline/content/website_v2/NEO_PRE_5PROB_V2_WALK_FORWARD.json
-- 97 historical tournament instances, WIN log-loss gate PASS at
thresholds 5/8/10 vs both M0 (uniform) and M1 (single-feature)
baselines (overall_frozen_win_gate_pass=true), CUT AUC ~0.70 vs 0.50
uniform. This script does not re-run that backtest; it applies the
SAME already-gated model to a new field, exactly as 242 did for
2026100003.
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

from klpga.ops.paths import db_path as _resolve_db_path  # noqa: E402
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

GAME_CODE = "2026100001"
TOURNAMENT_NAME = "제20회 S-OIL 챔피언십"
OFFICIAL_FIELD_COUNT = 96
MIN_TRAINING_TOURNAMENTS = 10  # same floor 193/242 already enforce, unchanged


class InsufficientWarehouseError(RuntimeError):
    """Raised (never silently caught) when --db exists but does not
    hold enough real cross-tournament data to train M4 responsibly."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _preflight_check_corpus(conn: sqlite3.Connection) -> int:
    try:
        (n_tournaments,) = conn.execute("SELECT COUNT(DISTINCT event_id) FROM player_event").fetchone()
    except sqlite3.OperationalError as exc:
        raise InsufficientWarehouseError(f"--db does not implement the expected schema: {exc}") from exc
    if n_tournaments < MIN_TRAINING_TOURNAMENTS:
        raise InsufficientWarehouseError(
            f"--db has only {n_tournaments} distinct tournaments in player_event; "
            f"refusing to fit M4 on fewer than {MIN_TRAINING_TOURNAMENTS} (never estimate from an inadequate corpus)."
        )
    return n_tournaments


def build(game_code: str, cutoff: date, db_path: Path, entry_path: Path,
          simulations: int, seed: int, generated_at: str) -> dict:
    entry_doc = load(entry_path)
    entries = entry_doc["entries"]
    if len(entries) != OFFICIAL_FIELD_COUNT:
        raise RuntimeError(f"official entry population must be {OFFICIAL_FIELD_COUNT}, got {len(entries)}")
    codes = [str(row["player_id"]) for row in entries]
    if len(set(codes)) != len(codes):
        raise RuntimeError("official entry list contains duplicate player_id values")

    if not db_path.is_file() or db_path.stat().st_size == 0:
        raise InsufficientWarehouseError(
            f"no warehouse database at {db_path} (missing or empty) -- run scripts/274 first."
        )

    conn = sqlite3.connect(db_path)
    try:
        training_tournaments = _preflight_check_corpus(conn)

        target_events, target_rounds = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM player_event pe JOIN tournament_master tm ON tm.event_id=pe.event_id WHERE tm.game_code=?), "
            "(SELECT COUNT(*) FROM player_round pr JOIN tournament_master tm ON tm.event_id=pr.event_id WHERE tm.game_code=?)",
            (game_code, game_code),
        ).fetchone()
        if target_events or target_rounds:
            raise RuntimeError("target game's own rows already exist in inference DB; PRE temporal isolation failed")

        training_rows, training_tournaments = _build_training_rows(conn, game_code, cutoff)
        corpus = load_corpus(conn)
        field_rows = []
        features_by_code = {}
        for row in entries:
            code = str(row["player_id"])
            name = row["player_name"]
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

    # OPERATOR-DIRECTED VALIDATION GATE (this build only, not a change to
    # 242/193's own output contract): a player's own cut/top20/top10/top5/
    # win probabilities must be monotonically non-increasing
    # (cut_probability >= top20 >= top10 >= top5 >= win_probability) --
    # finishing top5 implies finishing top20 implies making the cut, so
    # a player cannot coherently be MORE likely to reach a narrower tier
    # than a wider one. The cut model (fold-fitted logistic) and the
    # finish-tier simulation (Plackett-Luce Monte Carlo) are fit
    # independently, so for a small share of borderline players their
    # combination can produce a tiny internal inconsistency -- a known
    # characteristic of this exact engine (the already-published
    # ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json has the same pattern,
    # 3 of 108 rows). Rather than publish a number known to be internally
    # inconsistent for a specific player, that player's row is excluded
    # here (treated the same as "데이터 부족", never silently kept).
    by_code = {str(row["player_id"]): row for row in entries}
    records = []
    for code, values in probabilities.items():
        feature = features_by_code[code]
        n = int(feature.get("prior_events_n") or 0)
        recent_n = int(feature.get("prior_recent_form_10_n") or 0)
        tier_vals = [
            values["cut_probability"], values["top20_probability"],
            values["top10_probability"], values["top5_probability"], values["win_probability"],
        ]
        monotonic = all(tier_vals[i] >= tier_vals[i + 1] - 1e-9 for i in range(len(tier_vals) - 1))
        if n == 0 or recent_n == 0:
            status = "DATA_INSUFFICIENT"
        elif not monotonic:
            status = "DATA_INSUFFICIENT"
        else:
            status = "PASS"
        records.append({
            "playerCode": code,
            "playerName": by_code[code]["player_name"],
            "qualification_category": by_code[code].get("qualification_category"),
            "neo_rank": None,
            "neo_score_display": round(values["win_probability"] * 100, 2),
            "neo_score_unit": "win_probability_pct",
            "analysis_status": status,
            "data_status": "데이터 부족" if status == "DATA_INSUFFICIENT" else "검증 가능",
            "monotonic_consistency_check": "pass" if monotonic else "fail",
            **values,
            "features": feature,
        })
    records.sort(key=lambda r: (-r["win_probability"], r["playerCode"]))
    for rank, row in enumerate(records, 1):
        row["neo_rank"] = rank

    return {
        "schema_version": "SOIL_2026100001_PRE_M4_CANDIDATE_V1",
        "gameCode": game_code,
        "stage": "PRE",
        "tournament_name": TOURNAMENT_NAME,
        "publication_class": "VALIDATION_MODEL_NOT_PRODUCTION",
        "official_field_count": OFFICIAL_FIELD_COUNT,
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
            "data_insufficient_no_prior_history": sum(
                r["analysis_status"] == "DATA_INSUFFICIENT" and r["monotonic_consistency_check"] == "pass" for r in records
            ),
            "data_insufficient_consistency_check_failed": sum(
                r["monotonic_consistency_check"] == "fail" for r in records
            ),
            "probability_sum": round(sum(r["win_probability"] for r in records), 12),
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(_resolve_db_path()), type=Path)
    parser.add_argument("--entry", default=str(ROOT / "content/website_v2/2026100001_KE_ENTRY_SNAPSHOT.json"), type=Path)
    parser.add_argument("--output", default=str(ROOT / "content/website_v2/SOIL_2026100001_PRE_M4_CANDIDATE_V1.json"), type=Path)
    parser.add_argument("--cutoff", default="2026-10-28")
    parser.add_argument("--simulations", default=60000, type=int)
    parser.add_argument("--seed", default=20261028, type=int)
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        doc = build(GAME_CODE, date.fromisoformat(args.cutoff), args.db, args.entry, args.simulations, args.seed, generated_at)
    except InsufficientWarehouseError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "gameCode": GAME_CODE, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "written", "path": str(args.output), "summary": doc["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
