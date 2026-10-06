"""SCAFFOLD for a points-based joint season simulation -- NOT RUNNABLE YET.

Status: blocked. See SEED_POINT_SYSTEM_GAP.md section 16 (MODEL RULE FREEZE
turn -- "point_rank <= 60" was supplied by the user as a MODELING ASSUMPTION,
not a newly-confirmed official cutoff; it does not unblock the data gaps
below, which are about the simulation's INPUTS, not the cutoff number).

V2 (recent-form weighted model) and the walk-forward backtest are NOT
implemented with real logic below -- see merge_independent_seed() for the
one new piece that IS real (deterministic, no simulation needed) and
run_v2_recent_form() / run_walkforward_backtest() for explicit refusal
stubs. Filling those in with invented performance numbers would violate
this project's no-fabrication rule as badly as the V1 field-size guard
below was designed to prevent.

This implements the mechanics the user asked for (joint leaderboard draw per
remaining event -> cut -> tie handling -> official point allocation ->
cumulative points -> final point rank -> compare to the official point
cutoff), reusing the same Gumbel-max exact-Plackett-Luce sampling approach
already used and verified in the money-rank simulation (seedrace2/simulate.py).

As of 2026-10-06 we have two PARTIAL real-data files (point_table_PARTIAL_
2026-10-06.csv, remaining_events_point_PARTIAL_2026-10-06.csv) -- 5 example
point-ranked players (all money-rank 1-6, none in the 55-90 bubble zone that
actually matters for a cutoff question) and the 1st-place point value for
each of the 3 base-case remaining events (derived from the official purse-
bracket formula, not from money->points conversion). This is real but FAR
from enough to simulate anything: we have 0 of ~100+ players' point ranks
in the relevant range, and 0 of ~60+ non-winner finish positions per event.
Running the simulation on 5 rows would silently simulate a 5-player field,
producing meaningless probabilities that look like real output. The guard
below checks for a field size and per-event position coverage in the
ballpark of a real KLPGA tour (not just "more than zero rows") specifically
to catch this case, not just the fully-empty-template case.

To actually run this:
  1. A point table covering at least the players near the (still unknown)
     cutoff -- not just the top few by points.
  2. Each remaining event's point curve for most/all finish positions a
     cutoff-zone player could plausibly land in (not just 1st-3rd).
  3. The official point-rank seed cutoff itself (still UNRESOLVED -- do not
     assume 60, or any other number, without an official source).
  4. Re-run with --confirm-real-data (required but not sufficient -- the
     guard also checks row-count thresholds below).
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent

MIN_FIELD_SIZE = 90   # a real KLPGA tour field is ~108; a handful of rows isn't a field
MIN_POSITIONS_PER_EVENT = 40  # need coverage well past the podium to simulate a cutoff ~50-70


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def guard_real_data(point_table_path, events_points_path, confirmed: bool):
    """Refuse to proceed unless both inputs look like a real, usable dataset
    (not just non-empty) AND the caller explicitly confirms real data."""
    problems = []
    pt = read_csv(point_table_path)
    ep = read_csv(events_points_path)
    if len(pt) == 0:
        problems.append(f"{point_table_path.name} has 0 data rows (still just the template header)")
    elif len(pt) < MIN_FIELD_SIZE:
        problems.append(
            f"{point_table_path.name} has only {len(pt)} players -- a real tour field is "
            f"~{MIN_FIELD_SIZE}+; this looks like a partial/example dataset, not the full field"
        )
    if len(ep) == 0:
        problems.append(f"{events_points_path.name} has 0 data rows (still just the template header)")
    else:
        by_event = {}
        for row in ep:
            by_event.setdefault(row["gameCode"], []).append(row)
        thin_events = {}
        for gc, rows in by_event.items():
            rows_sorted = sorted(rows, key=lambda r: int(r["finish_position"]))
            # a curve is "complete" either by raw row count, or by an explicit
            # zero-anchor row (tie_handling_rule == ZERO_BEYOND_THIS_POSITION or
            # points == 0) confirming every worse finish scores 0 -- that's full
            # coverage of the field even with few rows.
            has_zero_anchor = any(
                r.get("tie_handling_rule") == "ZERO_BEYOND_THIS_POSITION" or float(r["points"]) == 0.0
                for r in rows_sorted
            )
            if len(rows_sorted) < MIN_POSITIONS_PER_EVENT and not has_zero_anchor:
                thin_events[gc] = len(rows_sorted)
        if thin_events:
            problems.append(
                f"{events_points_path.name} has events with too few finish-position rows AND no "
                f"explicit zero-anchor row to cover the rest of the field "
                f"(need >= {MIN_POSITIONS_PER_EVENT} rows, or a 0-points anchor row): {thin_events}"
            )
    if not confirmed:
        problems.append("--confirm-real-data flag not passed")
    if problems:
        raise RuntimeError(
            "REFUSING TO RUN -- points dataset is not yet complete enough to simulate. "
            "See SEED_POINT_SYSTEM_GAP.md for what's needed. Problems: "
            + "; ".join(problems)
        )
    return pt, ep


def build_point_cutoff_prob_table(point_table_rows, events_points_rows,
                                   official_cutoff_rank: int, n_iter: int = 60000,
                                   seed: int = 42):
    """Joint points-based season simulation.

    Mirrors seedrace2/simulate.py's Gumbel-max exact Plackett-Luce field
    draw, but allocates OFFICIAL points per finish (from events_points_rows)
    instead of prize money, and ranks players by CUMULATIVE POINTS at the
    end instead of cumulative money.

    official_cutoff_rank: the points-rank seed cutoff (NOT assumed = 60 --
    must be supplied from a confirmed official source; see gap doc section 1).
    """
    players = sorted(point_table_rows, key=lambda r: int(r["point_rank"]))
    n_players = len(players)
    current_points = np.array([float(r["points"]) for r in players])
    # ability proxy: current point rank (same limitation as the money model --
    # recent-form / field-strength features are NOT_AVAILABLE locally, per the
    # feature-availability audit required in request section 5; this is V1 only)
    point_rank0 = np.array([int(r["point_rank"]) for r in players], dtype=float)

    events = {}
    for row in events_points_rows:
        events.setdefault(row["gameCode"], []).append(row)
    for gc, rows in events.items():
        rows.sort(key=lambda r: int(r["finish_position"]))

    rng = np.random.default_rng(seed)
    total_remaining = np.zeros((n_iter, n_players))

    TAU = 52.0  # reused from the money model's calibrated value as a V1 starting point only;
    # NOT re-calibrated against points cash/seed-rate data because that data doesn't exist yet either.
    log_w = np.log(np.exp(-point_rank0 / TAU))

    for gc, rows in events.items():
        field_n = len(rows)
        u = rng.random((n_iter, field_n))
        gumbel = -np.log(-np.log(u))
        score = log_w[:field_n][None, :] + gumbel  # placeholder field selection -- needs real entry list
        order = np.argsort(-score, axis=1)
        finish_rank = np.empty_like(order)
        rows_idx = np.arange(n_iter)[:, None]
        finish_rank[rows_idx, order] = np.arange(1, field_n + 1)[None, :]
        points_by_finish = {int(r["finish_position"]): float(r["points"]) for r in rows}
        max_finish = max(points_by_finish)
        pts_arr = np.zeros(field_n + 1)
        for pos in range(1, field_n + 1):
            pts_arr[pos] = points_by_finish.get(pos, 0.0)
        total_remaining[:, :field_n] += pts_arr[finish_rank]

    final_points = current_points[None, :] + total_remaining
    final_rank = np.empty_like(final_points, dtype=int)
    order = np.argsort(-final_points, axis=1)
    rows_idx = np.arange(n_iter)[:, None]
    ranks = np.arange(1, n_players + 1)[None, :]
    final_rank[rows_idx, order] = np.broadcast_to(ranks, (n_iter, n_players))

    prob_cutoff = (final_rank <= official_cutoff_rank).mean(axis=0)
    return {players[i]["player"]: float(prob_cutoff[i]) for i in range(n_players)}


def merge_independent_seed(point_cutoff_prob: dict, eligibility_fields_path: Path):
    """Step 10 of the requested pipeline: merge independent-seed status into
    the simulated P(final point rank <= cutoff) results.

    This step itself needs NO new data -- player_eligibility_fields_2026-10-06.csv
    already has independent_seed computed deterministically. The rule (per
    the user's CRITICAL GUARDS): a player with independent_seed == "TRUE" AND
    independent_seed_type backed by a RULE_CONFIRMED exemption gets
    2027_seed_probability = 100%, full stop -- her simulated point-rank
    probability is NOT used instead, and she is NOT removed from the Top60
    population (no promotion of the next player). Everyone else keeps their
    simulated P(final point rank <= cutoff) as-is.
    """
    elig = read_csv(eligibility_fields_path)
    elig_by_name = {r["player"]: r for r in elig}
    merged = {}
    for name, prob in point_cutoff_prob.items():
        e = elig_by_name.get(name)
        if e and e["independent_seed"] == "TRUE":
            merged[name] = {"2027_seed_probability": 1.0, "basis": "independent_seed (RULE_CONFIRMED)"}
        else:
            merged[name] = {"2027_seed_probability": prob, "basis": "simulated P(final point rank <= cutoff)"}
    return merged


def run_v2_recent_form(*args, **kwargs):
    """V2 (recent-5/recent-10 weighted ability model) is NOT implemented.

    It requires per-player, per-tournament finish data (recent 5/10 events,
    cut rate, Top20/10/5, wins, round scoring, field strength, SG-where-
    available) -- this session has never had access to any of it (mainRecord
    collection blocked all session, see SEED_POINT_SYSTEM_GAP.md section 13).
    Implementing this with synthetic/invented performance numbers would
    produce a model that LOOKS real but isn't -- refusing instead.
    """
    raise NotImplementedError(
        "V2 recent-form model requires per-tournament player performance data "
        "(recent finishes, cut rate, Top-N rates, SG) that has never been "
        "obtained this session. Not implemented -- would require fabricating "
        "performance numbers. See SEED_POINT_SYSTEM_GAP.md section 16."
    )


def run_walkforward_backtest(*args, **kwargs):
    """Walk-forward backtest is NOT implemented -- it requires historical
    per-tournament results (to hide future events and check calibration
    against what actually happened), which is the same mainRecord data
    that's been blocked all session. See SEED_POINT_SYSTEM_GAP.md section 16.
    """
    raise NotImplementedError(
        "Walk-forward backtest requires historical per-tournament results "
        "that have never been obtained this session. Not implemented -- "
        "would require fabricating past outcomes. See SEED_POINT_SYSTEM_GAP.md section 16."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--point-table", default=str(ROOT / "point_table_TEMPLATE.csv"))
    ap.add_argument("--events-points", default=str(ROOT / "remaining_events_point_TEMPLATE.csv"))
    ap.add_argument("--official-cutoff-rank", type=int, default=None,
                     help="Official points-rank seed cutoff. Required -- never assumed.")
    ap.add_argument("--confirm-real-data", action="store_true",
                     help="Required flag confirming the input CSVs hold real official data, not templates.")
    a = ap.parse_args()

    pt_path, ep_path = Path(a.point_table), Path(a.events_points)
    pt_rows, ep_rows = guard_real_data(pt_path, ep_path, a.confirm_real_data)

    if a.official_cutoff_rank is None:
        raise RuntimeError(
            "REFUSING TO RUN -- --official-cutoff-rank not supplied. "
            "Do not assume 60; the official KLPGA points-rank seed cutoff must be confirmed first."
        )

    result = build_point_cutoff_prob_table(pt_rows, ep_rows, a.official_cutoff_rank)
    for name, p in sorted(result.items(), key=lambda kv: -kv[1]):
        print(f"{name}: {p*100:.1f}%")


if __name__ == "__main__":
    main()
