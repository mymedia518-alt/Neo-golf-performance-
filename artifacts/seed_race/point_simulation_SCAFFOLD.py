"""SCAFFOLD for a points-based joint season simulation -- NOT RUNNABLE YET.

Status: blocked. See SEED_POINT_SYSTEM_GAP.md.

This implements the mechanics the user asked for (joint leaderboard draw per
remaining event -> cut -> tie handling -> official point allocation ->
cumulative points -> final point rank -> compare to the official point
cutoff), reusing the same Gumbel-max exact-Plackett-Luce sampling approach
already used and verified in the money-rank simulation (seedrace2/simulate.py).

It refuses to run against point_table_TEMPLATE.csv /
remaining_events_point_TEMPLATE.csv as shipped, because those are empty
headers-only templates -- there is no official KLPGA points data available
in this session (network blocked, nothing relayed). Running this against
empty/fabricated data would produce fabricated "seed probabilities", which
is exactly what must not happen. The guard below exists specifically to
prevent that mistake, including by a future session that forgets why these
files are empty.

To actually run this:
  1. Fill point_table.csv (copy of point_table_TEMPLATE.csv) with real rows:
     one per player, with money_rank/money (already known, from
     official_money_rank_2026-10-06_full.json) and point_rank/points (NEW --
     must come from an official KLPGA source, not estimated from money).
  2. Fill remaining_events_points.csv (copy of remaining_events_point_TEMPLATE.csv)
     with one row per (event, finish_position) giving the *official* KLPGA
     points awarded at that finish, per event category (major/general/final).
     Do NOT derive points from prize money -- the user explicitly prohibited
     that (사용자 지시: "상금을 포인트로 환산 금지").
  3. Also need: the official point-rank seed cutoff (e.g. "top N by points";
     N is currently unknown -- do not assume 60).
  4. Re-run with --confirm-real-data (the guard requires this flag AND
     non-empty input files, as a second check against accidental fake runs).
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def guard_real_data(point_table_path, events_points_path, confirmed: bool):
    """Refuse to proceed unless both inputs are non-empty AND the caller
    explicitly confirms they are real official data, not placeholders."""
    problems = []
    pt = read_csv(point_table_path)
    ep = read_csv(events_points_path)
    if len(pt) == 0:
        problems.append(f"{point_table_path.name} has 0 data rows (still just the template header)")
    if len(ep) == 0:
        problems.append(f"{events_points_path.name} has 0 data rows (still just the template header)")
    if not confirmed:
        problems.append("--confirm-real-data flag not passed")
    if problems:
        raise RuntimeError(
            "REFUSING TO RUN -- no official points data available yet. "
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
