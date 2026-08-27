"""READ-ONLY audit of the real post-R1 WIN%/MAKE CUT% calculation
(src/klpga/neo_win/round_update.py, invoked by
scripts/35_predict_neo_win_post_r1.py) for BETA #001 R1 FINAL
validation.

Does NOT modify any model/inference/probability code, the production
DB (opened mode=ro), predictions/, or any frozen archive. Writes
nothing except stdout.

What this script does, precisely:
  1. Loads the REAL frozen PRE snapshot (neo_win_c_predictions) and the
     REAL Round-1 leaderboard scores from the DB, using the SAME
     adapter logic scripts/35 uses for --pre-family beta001c.
  2. Calls the REAL, unmodified klpga.neo_win.round_update functions
     (build_sim_inputs_from_frozen_snapshot / estimate_cut_fraction /
     simulate_post_round1) to produce a FRESH Monte Carlo re-run —
     this checks whether the OLD numbers in BETA001_R1_FULL.csv
     reproduce (within Monte Carlo noise) from the real, unmodified
     model code and real, unmodified inputs.
  3. For a fixed list of named players, prints PRIOR AVG / RECENT FORM
     (present in the frozen snapshot's feature_values, confirmed NOT
     read by round_update.py at all) / STDDEV / EXPECTED R2 MEAN /
     OLD vs NEW WIN%/MAKE CUT%.
  4. A DIAGNOSTIC-ONLY instrumented re-simulation (faithfully mirrors
     round_update.simulate_post_round1's own R2/cutline formula line
     for line — does not call a different formula) that additionally
     records the per-trial cutline threshold thru-36 total, something
     the production function does not return. Used only to answer
     "how bad would this player's real R2 have needed to be to miss
     the cut" from the model's own actual dynamics — never a separate,
     independently-invented cutline rule.
  5. Field-integrity checks (STEP 6) computed directly from
     BETA001_R1_FULL.csv: WIN% sum, MAKE CUT% range, NaN/negative/
     >100, player_code duplicates, missing_r1_data consistency.

Usage:
    python scripts/51_audit_r1_final_probabilities.py --db data/klpga.sqlite \\
        --game-code 2026080001 --pre-prediction-id 001-C-FINAL \\
        --pre-cutoff-date 2026-08-27 --r1-csv outputs/beta001_r1/BETA001_R1_FULL.csv
"""
from __future__ import annotations

import argparse
import csv
import random
import sqlite3
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.beta001c_archive import archive_paths as c_archive_paths, read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.round_update import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_sim_inputs_from_frozen_snapshot,
    estimate_cut_fraction,
    simulate_post_round1,
)

ROOT = Path(__file__).resolve().parents[1]

CUT_NAMES = ["이서윤4", "정수빈", "유아현", "서교림", "신지우", "백소원"]
WIN_NAMES = ["이서윤4", "노승희", "박혜준", "성유진", "박현경", "최예림"]


@dataclass(frozen=True)
class _AdaptedPreEntrant:
    player_code: str
    player_name: str
    win_probability: Optional[float]
    prior_avg_round_score_to_par: Optional[float]
    neo_consistency_stddev: Optional[float]


@dataclass(frozen=True)
class _AdaptedPreSnapshot:
    prediction_id: str
    tournament_name: Optional[str]
    cutoff_date: str
    predictions: tuple


def _adapt_beta001c_snapshot(c_snapshot) -> _AdaptedPreSnapshot:
    """Identical field-mapping adapter to scripts/35's own
    `_adapt_beta001c_snapshot` — duplicated here (not imported, since
    scripts/35's filename starts with a digit and is not importable as
    a module) so this audit exercises the exact same real inputs the
    production post-R1 script consumes."""
    entrants = tuple(
        _AdaptedPreEntrant(
            player_code=e.player_code,
            player_name=e.player_name,
            win_probability=e.win_probability,
            prior_avg_round_score_to_par=e.feature_values.get("prior_avg_round_score_to_par"),
            neo_consistency_stddev=e.feature_values.get("neo_consistency_stddev"),
        )
        for e in c_snapshot.predictions
    )
    return _AdaptedPreSnapshot(
        prediction_id=c_snapshot.prediction_id,
        tournament_name=c_snapshot.tournament_name,
        cutoff_date=c_snapshot.cutoff_date,
        predictions=entrants,
    )


def _read_r1_scores(conn: sqlite3.Connection, game_code: str) -> dict:
    rows = conn.execute(
        "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = 1 "
        "AND round_to_par IS NOT NULL",
        (game_code,),
    ).fetchall()
    return {player_id: round_to_par for player_id, round_to_par in rows}


def _feature_values_by_code(c_snapshot) -> dict:
    return {e.player_code: e.feature_values for e in c_snapshot.predictions}


def _load_csv_rows(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _f(v):
    v = (v or "").strip() if isinstance(v, str) else v
    if v in ("", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def field_integrity_check(csv_rows: list[dict]) -> None:
    print("=== STEP 6 — FIELD PROBABILITY INTEGRITY (from real BETA001_R1_FULL.csv) ===")
    print()
    win_vals = [(_f(r["post_r1_win_pct"]), r) for r in csv_rows]
    win_present = [(v, r) for v, r in win_vals if v is not None]
    win_sum = sum(v for v, _ in win_present)
    print(f"WIN SUM (present-only, N={len(win_present)}): {win_sum:.4f}%  "
          f"({'PASS' if 99.99 <= win_sum <= 100.01 else 'OUT OF TOLERANCE (99.99-100.01 expected)'})")

    cut_vals = [(_f(r["post_r1_make_cut_pct"]), r) for r in csv_rows]
    cut_present = [(v, r) for v, r in cut_vals if v is not None]
    out_of_range = [(v, r["player_name"]) for v, r in cut_present if v < 0 or v > 100]
    print(f"MAKE CUT range: min={min((v for v, _ in cut_present), default=None)}  "
          f"max={max((v for v, _ in cut_present), default=None)}  out_of_[0,100]={len(out_of_range)} {out_of_range[:10]}")

    nan_negative = []
    for r in csv_rows:
        for field_name in ("post_r1_win_pct", "post_r1_make_cut_pct"):
            v = r.get(field_name, "")
            if v.strip() != "" and v.strip().lower() in ("nan", "-nan"):
                nan_negative.append((r["player_name"], field_name, v))
    print(f"NaN literal values found: {len(nan_negative)} {nan_negative[:10]}")

    negatives = [(r["player_name"], v) for v, r in win_present if v < 0] + \
                [(r["player_name"], v) for v, r in cut_present if v < 0]
    print(f"Negative probability values: {len(negatives)} {negatives[:10]}")

    codes = [r["player_code"] for r in csv_rows]
    dupes = {c for c in codes if codes.count(c) > 1}
    print(f"Duplicate player_code in output: {len(dupes)} {sorted(dupes)[:10]}")

    missing_flagged = [r for r in csv_rows if r.get("missing_r1_data", "").strip().lower() in ("true", "1")]
    missing_but_has_prob = [
        r["player_name"] for r in missing_flagged
        if _f(r["post_r1_win_pct"]) is not None or _f(r["post_r1_make_cut_pct"]) is not None
    ]
    print(f"missing_r1_data=True rows: {len(missing_flagged)}  "
          f"(of these, rows that STILL carry a non-null win/cut probability — should be 0: "
          f"{len(missing_but_has_prob)} {missing_but_has_prob})")
    print()


def _diagnostic_cutline_resim(sim_inputs, cut_fraction: float, n_simulations: int, rng: random.Random) -> dict:
    """Faithfully mirrors round_update.simulate_post_round1's own R2 /
    cutline formula (same Normal draw, same sort, same n_cutline slice)
    — the ONLY difference is this additionally records, per trial, the
    thru-36 total of the LAST player who makes the cut (the empirical
    cutline threshold for that trial), which the production function
    does not return. Does not call, replace, or modify round_update.py;
    used only to report an average cutline threshold for the STEP 4
    'how bad would R2 need to be to miss the cut' sanity check."""
    playable = [p for p in sim_inputs if p.r1_score_to_par is not None]
    n_cutline = max(1, round(len(playable) * cut_fraction))
    thresholds = []
    for _ in range(n_simulations):
        r2 = {p.player_code: rng.normalvariate(p.expected_round_score_to_par, p.spread) for p in playable}
        thru36 = sorted(playable, key=lambda p: p.r1_score_to_par + r2[p.player_code])
        cutline_player = thru36[n_cutline - 1]
        thresholds.append(cutline_player.r1_score_to_par + r2[cutline_player.player_code])
    return {
        "n_cutline": n_cutline,
        "field_size": len(playable),
        "avg_cutline_thru36_total": statistics.mean(thresholds),
        "stdev_cutline_thru36_total": statistics.pstdev(thresholds),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--c-predictions-dir", default=str(ROOT / "neo_win_c_predictions"))
    parser.add_argument("--pre-prediction-id", default="001-C-FINAL")
    parser.add_argument("--pre-cutoff-date", required=True)
    parser.add_argument("--r1-csv", default=str(ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"))
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    csv_path = Path(args.r1_csv)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} does not exist.")
        return 4

    pre_json_path, _c = c_archive_paths(
        Path(args.c_predictions_dir), args.pre_prediction_id, args.game_code, args.pre_cutoff_date
    )
    if not pre_json_path.exists():
        print(f"ERROR: frozen PRE snapshot not found at {pre_json_path}.")
        return 5
    c_snapshot = read_neo_win_c_snapshot(pre_json_path)
    pre_snapshot = _adapt_beta001c_snapshot(c_snapshot)
    fv_by_code = _feature_values_by_code(c_snapshot)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r1_scores = _read_r1_scores(conn, args.game_code)
        if not r1_scores:
            print(f"ERROR: no round_number=1 player_round rows for game_code={args.game_code!r}.")
            return 6
        cut_fraction = estimate_cut_fraction(conn)
    finally:
        conn.close()

    sim_inputs, missing_r1 = build_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores)

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    new_sim = simulate_post_round1(sim_inputs, cut_fraction=cut_fraction, n_simulations=args.n_simulations, rng=rng)

    csv_rows = _load_csv_rows(csv_path)
    csv_by_name: dict[str, list[dict]] = {}
    for r in csv_rows:
        csv_by_name.setdefault(r["player_name"], []).append(r)

    sim_by_code = {p.player_code: p for p in sim_inputs}

    print("=== STEP 1/2/3 — CODE-VERIFIED CALCULATION SUMMARY ===")
    print()
    print("Script: scripts/35_predict_neo_win_post_r1.py -> src/klpga/neo_win/round_update.py")
    print(f"n_simulations used: {args.n_simulations}")
    print(f"Empirical cut_fraction (real player_event rounds_played=4 rate): {cut_fraction:.6f}")
    print("Expected per-round score for R2/R3/R4: PlayerSimInput.expected_round_score_to_par ="
          " prior_avg_round_score_to_par (population-mean-shrunk if missing). prior_recent_form_10 is"
          " present in the frozen snapshot's feature_values but is NOT read anywhere in round_update.py.")
    print("Spread: neo_consistency_stddev (population-mean-shrunk if missing), floored at 0.5.")
    print("R1 actual: read once into PlayerSimInput.r1_score_to_par, added as a FIXED constant in every"
          " trial (never resimulated) for both the 36-hole cut total and the 72-hole win total — confirmed"
          " by direct code reading of simulate_post_round1.")
    print("Cutline: dynamic per-trial — n_cutline = round(field_size * cut_fraction); the n_cutline lowest"
          " thru-36 (actual R1 + simulated R2) totals make the cut. Not a fixed score threshold.")
    print()

    print("=== STEP 4 — MAKE CUT SANITY CHECK (real inputs + fresh re-run + cutline threshold) ===")
    print()
    cutline_info = _diagnostic_cutline_resim(sim_inputs, cut_fraction, args.n_simulations, random.Random(args.seed))
    print(f"n_cutline={cutline_info['n_cutline']} of field_size={cutline_info['field_size']}  "
          f"avg cutline thru-36 total={cutline_info['avg_cutline_thru36_total']:.3f}  "
          f"stdev={cutline_info['stdev_cutline_thru36_total']:.3f}")
    print()
    for name in CUT_NAMES:
        rows = csv_by_name.get(name, [])
        if not rows:
            print(f"{name}: NOT FOUND in {csv_path.name}")
            print()
            continue
        for r in rows:
            code = r["player_code"]
            sim_p = sim_by_code.get(code)
            fv = fv_by_code.get(code, {})
            old_cut = r.get("post_r1_make_cut_pct", "")
            new_cut = new_sim.get(code, {}).get("make_cut_pct")
            print(f"PLAYER: {name}  (player_code={code})")
            print(f"  R1 ACTUAL: {r.get('r1_score_to_par')}")
            print(f"  PRIOR AVG (prior_avg_round_score_to_par): {fv.get('prior_avg_round_score_to_par')!r}")
            print(f"  RECENT FORM (prior_recent_form_10, NOT used by round_update.py): {fv.get('prior_recent_form_10')!r}")
            print(f"  STDDEV (neo_consistency_stddev, spread used): {sim_p.spread if sim_p else 'N/A'}")
            print(f"  EXPECTED R2 MEAN (expected_round_score_to_par used): {sim_p.expected_round_score_to_par if sim_p else 'N/A'}")
            print(f"  OLD MAKE CUT%: {old_cut}")
            print(f"  NEW MAKE CUT% (fresh re-run, real code, same real inputs): {new_cut}")
            if sim_p is not None:
                required_r2_total = cutline_info["avg_cutline_thru36_total"] - float(r.get("r1_score_to_par", 0) or 0)
                z = (required_r2_total - sim_p.expected_round_score_to_par) / sim_p.spread if sim_p.spread else None
                print(f"  R2 SCORE NEEDED TO MISS CUT (approx, vs avg cutline threshold): worse than {required_r2_total:.2f}"
                      f" to-par  (z={z:.3f} stddevs from this player's own expected R2 mean)" if z is not None else "  z: N/A")
            print()

    print("=== STEP 5 — WIN SANITY CHECK (real inputs + fresh re-run) ===")
    print()
    for name in WIN_NAMES:
        rows = csv_by_name.get(name, [])
        if not rows:
            print(f"{name}: NOT FOUND in {csv_path.name}")
            print()
            continue
        for r in rows:
            code = r["player_code"]
            sim_p = sim_by_code.get(code)
            old_win = r.get("post_r1_win_pct", "")
            new_win = new_sim.get(code, {}).get("win_pct")
            print(f"PLAYER: {name}  (player_code={code})")
            print(f"  R1 ACTUAL: {r.get('r1_score_to_par')}  CURRENT POSITION: {r.get('r1_position')}")
            print(f"  PRIOR STRENGTH (expected_round_score_to_par): {sim_p.expected_round_score_to_par if sim_p else 'N/A'}")
            print(f"  STDDEV (spread): {sim_p.spread if sim_p else 'N/A'}")
            print(f"  OLD WIN%: {old_win}")
            print(f"  NEW WIN% (fresh re-run, real code, same real inputs): {new_win}")
            print()

    field_integrity_check(csv_rows)

    win_sum_new = sum(v["win_pct"] for v in new_sim.values())
    print("=== NEW RUN MODEL CHECK ===")
    print(f"Players simulated: {len(sim_inputs)}  Missing R1: {len(missing_r1)}")
    print(f"NEW WIN sum: {win_sum_new:.4f}%")
    print()
    print("Done. No model/prediction/frozen file was modified by this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
