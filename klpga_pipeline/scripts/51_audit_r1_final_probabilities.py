"""READ-ONLY audit of the real post-R1 WIN%/MAKE CUT% calculation
(src/klpga/neo_win/round_update.py, invoked by
scripts/35_predict_neo_win_post_r1.py) for BETA #001 R1 FINAL
validation — now focused on verifying the sample-size shrinkage fix
applied to round_update.py this round (expected_round_score_to_par /
spread now shrunk via the same real, backtested formula the PRE path
already uses).

Does NOT itself modify any model/inference/probability code, the
production DB (opened mode=ro), predictions/, or any frozen archive.
Writes nothing except stdout — it does NOT regenerate
outputs/beta001_r1/BETA001_R1_FULL.csv (re-run scripts/35 for that).

What this script does, precisely:
  1. Loads the REAL frozen PRE snapshot (neo_win_c_predictions) and the
     REAL Round-1 leaderboard scores from the DB, using the SAME
     adapter logic scripts/35 uses for --pre-family beta001c.
  2. Builds TWO sets of Monte Carlo sim inputs from the REAL,
     unmodified klpga.neo_win.round_update.build_sim_inputs_from_
     frozen_snapshot: OLD (no shrinkage, the prior behavior) and NEW
     (shrinkage applied via the same real, backtested params scripts/35
     now uses in production) — then runs simulate_post_round1 on both
     with an IDENTICAL seed, so any WIN%/CUT% difference is
     attributable only to the shrinkage fix, not Monte Carlo noise.
  3. Prints a per-player model-input deep dive (real historical
     event/round counts, raw values, shrunk values) for DEEP_DIVE_NAMES.
  4. Prints the OLD vs NEW comparison table for FINAL_COMPARE_NAMES,
     integrity checks on the NEW run (WIN sum, CUT range, null/dupe
     counts), and the specific sanity-check comparisons requested for
     BETA #001 R1 FINAL validation.

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
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.backtest.point_in_time_features import compute_point_in_time_features, load_corpus  # noqa: E402
from klpga.backtest.temporal import effective_tournament_date  # noqa: E402
from klpga.neo_win.beta001c_archive import archive_paths as c_archive_paths, read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.consistency import compute_consistency_feature  # noqa: E402
from klpga.neo_win.round_update import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_post_r1_n_lookup,
    build_sim_inputs_from_frozen_snapshot,
    estimate_cut_fraction,
    fit_post_r1_shrink_params,
    shrink_to_original_units,
    simulate_post_round1,
)

ROOT = Path(__file__).resolve().parents[1]

DEEP_DIVE_NAMES = ["이서윤4", "정수빈", "유아현", "서교림", "신지우", "백소원", "노승희"]
FINAL_COMPARE_NAMES = ["이서윤4", "정수빈", "유아현", "노승희", "서교림", "신지우", "백소원", "박현경"]


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


def _load_csv_rows(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _shrunk_value(raw: Optional[float], n: Optional[int], params) -> Optional[float]:
    """Display wrapper around the real klpga.neo_win.round_update.
    shrink_to_original_units (the SAME function main() uses to build the
    actual, production-applied NEW sim inputs) — rounds for readability."""
    result = shrink_to_original_units(raw, n, params)
    return None if result is None else round(result, 3)


def deep_dive_named_players(
    conn: sqlite3.Connection, game_code: str, cutoff_date_obj: date, csv_by_name: dict,
    params_avg, params_stddev,
) -> None:
    """Model-input diagnosis only — calls the REAL, unmodified
    klpga.backtest.point_in_time_features.compute_point_in_time_features
    and klpga.neo_win.consistency.compute_consistency_feature for
    DEEP_DIVE_NAMES. `params_avg`/`params_stddev` are the SAME
    fit_post_r1_shrink_params() result main() also uses for the actual
    fix, so these numbers match production exactly. Read-only; does not
    touch round_update.py, does not recompute any probability."""
    row = conn.execute(
        "SELECT event_id, start_date, end_date FROM tournament_master WHERE game_code = ?", (game_code,)
    ).fetchone()
    if row is None:
        print(f"CANNOT DEEP-DIVE: no tournament_master row for game_code={game_code!r}")
        return
    target_event_id, start_date, end_date = row
    target_effective_date = effective_tournament_date(start_date, end_date).value

    corpus = load_corpus(conn)

    print("=== MODEL INPUT DEEP DIVE (real DB, real point-in-time features, named players) ===")
    print()
    print(f"target_event_id={target_event_id!r}  target_effective_date={target_effective_date}")
    print(f"Shrinkage params fit on real training rows for THIS target (klpga.models.candidates.fit_shrinkage,"
          f" via klpga.neo_win.round_update.fit_post_r1_shrink_params — same params now applied in production):")
    print(f"  prior_avg_round_score_to_par: pop_mean={params_avg.pop_mean:.4f}  pop_std={params_avg.pop_std:.4f}  "
          f"k(median training n)={params_avg.k}")
    print(f"  neo_consistency_stddev: pop_mean={params_stddev.pop_mean:.4f}  pop_std={params_stddev.pop_std:.4f}  "
          f"k(median training n)={params_stddev.k}")
    print()

    for name in DEEP_DIVE_NAMES:
        rows = csv_by_name.get(name, [])
        if not rows:
            print(f"{name}: NOT FOUND in R1 CSV")
            print()
            continue
        for r in rows:
            code = r["player_code"]
            pit = compute_point_in_time_features(corpus, target_event_id, target_effective_date, code, name)
            cons, cons_n = compute_consistency_feature(corpus, target_event_id, target_effective_date, code)

            events_by_player = corpus.events_by_player.get(code, [])
            events_by_id = {e.event_id: e for e in events_by_player}
            recent10_ids = pit.recent_form_event_ids_used.get(10, ())
            recent10_raw = [events_by_id[eid].score_to_par for eid in recent10_ids if eid in events_by_id]

            rounds_by_player = corpus.rounds_by_player.get(code, [])
            stddev_raw_values = [
                rr.round_to_par for rr in rounds_by_player
                if rr.event_id != target_event_id and rr.round_to_par is not None
                and rr.effective_date is not None and target_effective_date is not None
                and rr.effective_date < target_effective_date
            ]

            print(f"PLAYER: {name}  (player_code={code})")
            print(f"  HISTORICAL EVENTS USED (prior_events_n, strictly before {target_effective_date}): {pit.prior_events_n}")
            print(f"  HISTORICAL ROUNDS USED for avg-score-to-par rate (sum of rounds_played, prior_avg_round_score_to_par_n): {pit.prior_avg_round_score_to_par_n}")
            print(f"  AVG SCORE TO PAR RAW: {pit.prior_avg_round_score_to_par!r}")
            print(f"  AVG SCORE TO PAR AFTER SHRINKAGE (weight=n/(n+k), same formula as klpga.models.candidates): "
                  f"{_shrunk_value(pit.prior_avg_round_score_to_par, pit.prior_avg_round_score_to_par_n, params_avg)!r}")
            print(f"  RECENT FORM 10 RAW INPUTS (most recent {pit.prior_recent_form_10_n} events' real score_to_par, newest first): {recent10_raw}")
            print(f"  RECENT FORM 10 RESULT: {pit.prior_recent_form_10!r}  (n={pit.prior_recent_form_10_n})")
            print(f"  STDDEV RAW INPUTS (player_round.round_to_par, prior rounds only, n={cons_n}): {stddev_raw_values}")
            print(f"  STDDEV RESULT (neo_consistency_stddev): {cons!r}")
            print(f"  STDDEV AFTER SHRINKAGE (same formula, using neo_consistency_stddev's own pop_mean/k): "
                  f"{_shrunk_value(cons, cons_n, params_stddev)!r}")
            print()


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

    cutoff_date_obj = date.fromisoformat(pre_snapshot.cutoff_date)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r1_scores = _read_r1_scores(conn, args.game_code)
        if not r1_scores:
            print(f"ERROR: no round_number=1 player_round rows for game_code={args.game_code!r}.")
            return 6
        cut_fraction = estimate_cut_fraction(conn)
        # Same real, backtested shrinkage now applied in production (scripts/35 + round_update.py) —
        # computed here identically so this comparison matches what --freeze will actually produce.
        avg_shrink_params, stddev_shrink_params = fit_post_r1_shrink_params(conn, args.game_code, cutoff_date_obj)
        n_lookup = build_post_r1_n_lookup(
            conn, args.game_code, cutoff_date_obj, [e.player_code for e in pre_snapshot.predictions]
        )
    finally:
        conn.close()

    sim_inputs_old, missing_r1 = build_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores)
    sim_inputs_new, _missing_r1_new = build_sim_inputs_from_frozen_snapshot(
        pre_snapshot, r1_scores,
        n_lookup=n_lookup, avg_shrink_params=avg_shrink_params, stddev_shrink_params=stddev_shrink_params,
    )

    # Same seed for both runs — any WIN%/CUT% difference below is attributable ONLY to the shrinkage
    # fix (different expected_round_score_to_par/spread inputs), not to independent Monte Carlo noise.
    common_seed = args.seed if args.seed is not None else 20260827
    old_result = simulate_post_round1(
        sim_inputs_old, cut_fraction=cut_fraction, n_simulations=args.n_simulations, rng=random.Random(common_seed)
    )
    new_result = simulate_post_round1(
        sim_inputs_new, cut_fraction=cut_fraction, n_simulations=args.n_simulations, rng=random.Random(common_seed)
    )

    csv_rows = _load_csv_rows(csv_path)
    csv_by_name: dict[str, list[dict]] = {}
    for r in csv_rows:
        csv_by_name.setdefault(r["player_name"], []).append(r)

    old_by_code = {p.player_code: p for p in sim_inputs_old}
    new_by_code = {p.player_code: p for p in sim_inputs_new}

    conn2 = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        deep_dive_named_players(conn2, args.game_code, cutoff_date_obj, csv_by_name, avg_shrink_params, stddev_shrink_params)
    finally:
        conn2.close()

    print("=== CHECKS 1-3 — CODE-VERIFIED CALCULATION PATH SUMMARY (POST-FIX) ===")
    print()
    print("Script: scripts/35_predict_neo_win_post_r1.py -> src/klpga/neo_win/round_update.py")
    print(f"n_simulations used: {args.n_simulations}  (both OLD and NEW runs use the same seed={common_seed})")
    print(f"Empirical cut_fraction (real player_event rounds_played=4 rate): {cut_fraction:.6f}")
    print("CHECK 1 (post_r1_win_pct path): WIN% = fraction of Monte Carlo trials in which this player has"
          " the lowest simulated 72-hole total (ACTUAL R1 + simulated R2/R3/R4, cutmakers only); ties split"
          " win credit fractionally. Unchanged this round.")
    print("CHECK 2 (post_r1_make_cut_pct path): CUT% = fraction of trials in which this player's simulated"
          " 36-hole total (ACTUAL R1 + simulated R2) is among the n_cutline lowest of the field that trial."
          " Unchanged this round.")
    print("CHECK 3 (R1 actual FIXED, not resimulated): unchanged — still added as a fixed constant every trial.")
    print("FIX APPLIED THIS ROUND: expected_round_score_to_par / spread are now shrunk toward the real,"
          " backtested population mean via klpga.neo_win.round_update.shrink_to_original_units (weight ="
          " n/(n+k), same k/pop_mean klpga.models.candidates.fit_shrinkage already fits for the PRE path)"
          " whenever a player's raw prior_avg_round_score_to_par / neo_consistency_stddev is present. A"
          " fully-missing value still falls back to the simple field population mean, unchanged."
          " prior_recent_form_10 is still NOT added to the model this round, per explicit instruction.")
    print("Cutline: dynamic per-trial — unchanged.")
    print()

    print("=== SHRINKAGE FIX — OLD vs NEW (real DB, real frozen PRE snapshot, real R1 scores) ===")
    print()
    print(f"{'PLAYER':<8} {'R1':>4} {'N(avg/std)':>11} {'OLD EXP':>8} {'NEW EXP':>8} {'OLD SD':>7} {'NEW SD':>7} "
          f"{'OLD WIN%':>9} {'NEW WIN%':>9} {'OLD CUT%':>9} {'NEW CUT%':>9}")
    for name in FINAL_COMPARE_NAMES:
        rows = csv_by_name.get(name, [])
        if not rows:
            print(f"{name}: NOT FOUND in R1 CSV")
            continue
        for r in rows:
            code = r["player_code"]
            op = old_by_code.get(code)
            npi = new_by_code.get(code)
            avg_n, stddev_n = n_lookup.get(code, (None, None))
            old_win = old_result.get(code, {}).get("win_pct")
            new_win = new_result.get(code, {}).get("win_pct")
            old_cut = old_result.get(code, {}).get("make_cut_pct")
            new_cut = new_result.get(code, {}).get("make_cut_pct")
            print(
                f"{name:<8} {r.get('r1_score_to_par'):>4} {f'{avg_n}/{stddev_n}':>11} "
                f"{(op.expected_round_score_to_par if op else float('nan')):>8.3f} "
                f"{(npi.expected_round_score_to_par if npi else float('nan')):>8.3f} "
                f"{(op.spread if op else float('nan')):>7.3f} {(npi.spread if npi else float('nan')):>7.3f} "
                f"{(old_win if old_win is not None else float('nan')):>9.4f} "
                f"{(new_win if new_win is not None else float('nan')):>9.4f} "
                f"{(old_cut if old_cut is not None else float('nan')):>9.4f} "
                f"{(new_cut if new_cut is not None else float('nan')):>9.4f}"
            )
    print()

    print("=== INTEGRITY CHECK (NEW / shrinkage-applied run) ===")
    print()
    new_win_values = [v["win_pct"] for v in new_result.values()]
    new_cut_values = [v["make_cut_pct"] for v in new_result.values()]
    new_win_sum = sum(new_win_values)
    out_of_range = [(code, v["make_cut_pct"]) for code, v in new_result.items() if not (0 <= v["make_cut_pct"] <= 100)]
    null_count = sum(1 for p in sim_inputs_new if p.r1_score_to_par is not None and p.player_code not in new_result)
    codes = [p.player_code for p in sim_inputs_new]
    dup_count = len(codes) - len(set(codes))
    print(f"WIN SUM: {new_win_sum:.4f}%  ({'PASS' if 99.99 <= new_win_sum <= 100.01 else 'OUT OF TOLERANCE'})")
    print(f"CUT MIN/MAX: {min(new_cut_values):.4f} / {max(new_cut_values):.4f}  "
          f"out_of_[0,100]={len(out_of_range)} {out_of_range[:10]}")
    print(f"NULL COUNT (playable player missing from result): {null_count}")
    print(f"DUPLICATE COUNT (player_code): {dup_count}")
    print(f"Missing R1 (excluded from simulation, unaffected by this fix): {len(missing_r1)} {missing_r1}")
    print()

    print("=== SANITY CHECK ===")
    print()
    for name in ("이서윤4", "정수빈", "유아현"):
        rows = csv_by_name.get(name, [])
        for r in rows:
            code = r["player_code"]
            old_cut = old_result.get(code, {}).get("make_cut_pct")
            new_cut = new_result.get(code, {}).get("make_cut_pct")
            print(f"{name} (R1 {r.get('r1_score_to_par')}): CUT% OLD={old_cut}  NEW={new_cut}  "
                  f"DELTA={None if old_cut is None or new_cut is None else round(new_cut - old_cut, 4)}")
    print()
    lsy_code = next((r["player_code"] for r in csv_by_name.get("이서윤4", [])), None)
    nsh_code = next((r["player_code"] for r in csv_by_name.get("노승희", [])), None)
    if lsy_code and nsh_code:
        old_gap = old_result.get(lsy_code, {}).get("win_pct"), old_result.get(nsh_code, {}).get("win_pct")
        new_gap = new_result.get(lsy_code, {}).get("win_pct"), new_result.get(nsh_code, {}).get("win_pct")
        print(f"이서윤4 vs 노승희 WIN%: OLD {old_gap[0]} vs {old_gap[1]}  "
              f"(ratio {None if not old_gap[1] else round(old_gap[1]/old_gap[0], 2) if old_gap[0] else None}x)")
        print(f"이서윤4 vs 노승희 WIN%: NEW {new_gap[0]} vs {new_gap[1]}  "
              f"(ratio {None if not new_gap[1] else round(new_gap[1]/new_gap[0], 2) if new_gap[0] else None}x)")
    print()
    print("Done. round_update.py / scripts/35 were modified this round (the authorized shrinkage fix only).")
    print("This script itself writes nothing — re-run scripts/35 (without --freeze) to regenerate the real"
          " outputs/beta001_r1/BETA001_R1_FULL.csv with these NEW, shrinkage-applied probabilities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
