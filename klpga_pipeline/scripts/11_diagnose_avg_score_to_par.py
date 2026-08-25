"""Red-team diagnostic for derived_avg_score_to_par (see
src/klpga/analytics/player_stats.py) against the REAL production DB.

Trigger: derived_avg_score_to_par values around -4.7 to -4.9 for real
players (이예원, 박지영, 김민솔) looked unrealistically low IF this were
"average ROUND score relative to par." This script exists to verify —
against real production rows, not by re-reading the code — exactly
which field feeds derived_avg_score_to_par, whether tournament-level
and round-level to-par values are ever mixed, and whether the resulting
numbers are internally self-consistent.

CODE TRACE (for the record — this script's job is to confirm it
against real data, not to replace the check):
    derived_avg_score_to_par = mean(player_event.score_to_par) across a
    player's events (src/klpga/analytics/player_stats.py).
    player_event.score_to_par = entry["total_under_par"]
    (src/klpga/collectors/aggregate.py build_rows()), which is set ONLY
    from the summary section of merge_player_rows() —
    entry["total_under_par"] = row.total_under_par, taken from the
    LAST (highest-round) PlayerRoundRow a player appears in.
    PlayerRoundRow.total_under_par is parsed from the raw
    `data-totunderpar` HTML attribute — CONFIRMED to be the
    TOURNAMENT-CUMULATIVE total-to-par (e.g. -8 for a full 4-round
    280-stroke total on a 288 field par), NOT a single round's to-par.
    That per-round figure exists separately as
    PlayerRoundRow.today_under_par / player_round.round_to_par
    (`data-todayunderpar`) and is NEVER read into player_event or
    derived_avg_score_to_par anywhere in the codebase — grep confirms
    `total_under_par` and `today_under_par` are assigned in entirely
    separate code paths and never cross-assigned.
    So: derived_avg_score_to_par is "average TOURNAMENT-total
    score-to-par across events," not "average per-round score-to-par."
    An elite player's tournament-total to-par (summed over ~4 rounds,
    or ~2 for a missed cut) commonly runs -5 to -15 in a made-cut event,
    so a multi-event average around -4 to -5 is the expected order of
    magnitude for this metric — NOT what you'd expect if it were
    mislabeled as a single round's to-par.

This script does not just repeat that trace — it independently verifies
it against real rows: for each player, it prints every collected
round's raw strokes, the site's own per-round to-par when directly
queried (`round_to_par`, sparse — only populated for rounds actually
fetched, see klpga.collectors.leaderboard), the tournament's final
total_strokes and score_to_par, and an INDEPENDENTLY reverse-engineered
"implied par" per event: implied_total_par = total_strokes -
score_to_par. If score_to_par really is a tournament-cumulative
strokes-vs-par figure, implied_total_par / rounds_played should land
close to a real golf hole-count par (68-74) for every event, for every
player — if it doesn't (e.g. way outside that range, or wildly
inconsistent between events for the same player), that's evidence of
an actual bug, not just an appearance of one.

Read-only: only SELECTs from tournament_master/player_master/
player_event/player_round. Never writes anything.

Usage:
    python scripts/11_diagnose_avg_score_to_par.py --db data/klpga.sqlite
    python scripts/11_diagnose_avg_score_to_par.py --db data/klpga.sqlite --names "이예원,박지영,김민솔,서교림,박민지"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_DEFAULT_NAMES = ["이예원", "박지영", "김민솔", "서교림", "박민지"]

# A real golf course's total par is virtually always in this range per
# round (par 68-74) — used only to flag an implausible implied_par for
# a human to look at, never to silently correct/estimate anything.
_PLAUSIBLE_PAR_PER_ROUND = (68, 74)


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _pick_players(conn: sqlite3.Connection, names: list[str], fill_to: int) -> list[sqlite3.Row]:
    """Look up players by exact name match first (the representative
    names the user flagged); if fewer than `fill_to` are found, fill
    the rest with the players who have the most tournaments_played in
    the derived snapshot, so the sample stays at 5 even if a requested
    name doesn't match (e.g. a romanization/spacing difference)."""
    found: list[sqlite3.Row] = []
    seen_ids = set()
    for name in names:
        row = conn.execute(
            "SELECT player_id, player_name FROM player_master WHERE player_name = ? LIMIT 1",
            (name,),
        ).fetchone()
        if row is not None and row["player_id"] not in seen_ids:
            found.append(row)
            seen_ids.add(row["player_id"])

    if len(found) < fill_to:
        extra = conn.execute(
            """
            SELECT p.player_id, p.player_name
            FROM player_stats_snapshot s
            JOIN player_master p ON s.player_id = p.player_id
            WHERE s.snapshot_type = 'derived_trailing100'
            ORDER BY s.derived_tournaments_played DESC
            """
        ).fetchall()
        for row in extra:
            if len(found) >= fill_to:
                break
            if row["player_id"] not in seen_ids:
                found.append(row)
                seen_ids.add(row["player_id"])

    return found[:fill_to]


def diagnose(db_path: Path, names: list[str], fill_to: int) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        players = _pick_players(conn, names, fill_to)
        if not players:
            print(
                "No matching players found (and no derived_trailing100 rows to fall "
                "back on — run scripts/09_build_player_stats_snapshot.py first).",
                file=sys.stderr,
            )
            return 1

        for player in players:
            player_id, player_name = player["player_id"], player["player_name"]
            print(f"\n{'=' * 100}")
            print(f"{player_name}  (player_id={player_id})")
            print(f"{'=' * 100}")

            events = conn.execute(
                """
                SELECT pe.event_id, tm.event_name, tm.end_date, pe.rounds_played,
                       pe.total_score, pe.score_to_par, pe.made_cut
                FROM player_event pe
                JOIN tournament_master tm ON pe.event_id = tm.event_id
                WHERE pe.player_id = ?
                ORDER BY tm.end_date DESC
                """,
                (player_id,),
            ).fetchall()

            to_par_values = []
            implied_par_per_round_values = []
            implausible_events = []

            for ev in events:
                rounds = conn.execute(
                    "SELECT round_number, round_score, round_to_par, course_par "
                    "FROM player_round WHERE event_id = ? AND player_id = ? ORDER BY round_number",
                    (ev["event_id"], player_id),
                ).fetchall()
                round_scores = ", ".join(f"r{r['round_number']}={_fmt(r['round_score'])}" for r in rounds)
                round_to_pars = ", ".join(
                    f"r{r['round_number']}={_fmt(r['round_to_par'])}" for r in rounds if r["round_to_par"] is not None
                ) or "(none directly queried)"
                course_pars = {r["course_par"] for r in rounds}

                implied_total_par = None
                implied_avg_par = None
                if ev["total_score"] is not None and ev["score_to_par"] is not None and ev["rounds_played"]:
                    implied_total_par = ev["total_score"] - ev["score_to_par"]
                    implied_avg_par = implied_total_par / ev["rounds_played"]
                    implied_par_per_round_values.append(implied_avg_par)
                    if not (_PLAUSIBLE_PAR_PER_ROUND[0] <= implied_avg_par <= _PLAUSIBLE_PAR_PER_ROUND[1]):
                        implausible_events.append((ev["event_id"], implied_avg_par))

                if ev["score_to_par"] is not None:
                    to_par_values.append(ev["score_to_par"])

                print(
                    f"\n  {ev['event_id']} | {ev['event_name']} | {ev['end_date']} | "
                    f"made_cut={ev['made_cut']} | rounds_played={ev['rounds_played']}"
                )
                print(f"    round_score (raw, player_round):      {round_scores or '(none)'}")
                print(f"    round_to_par (data-todayunderpar):    {round_to_pars}")
                print(f"    course_par (player_round, confirmed): {course_pars if course_pars else '(none)'} (always NULL — never a confirmed field)")
                print(f"    total_strokes (player_event):         {_fmt(ev['total_score'])}")
                print(f"    score_to_par (player_event, site's own data-totunderpar, TOURNAMENT total): {_fmt(ev['score_to_par'])}")
                print(
                    f"    implied_total_par = total_strokes - score_to_par: {_fmt(implied_total_par)}"
                    f"   implied_avg_par/round: {_fmt(implied_avg_par)}"
                )

            print(f"\n  --- {player_name} summary ---")
            print(f"  events with a real score_to_par: {len(to_par_values)} / {len(events)}")
            if to_par_values:
                mean_to_par = sum(to_par_values) / len(to_par_values)
                print(f"  mean(score_to_par) across those events = {mean_to_par:.2f}  <- should match derived_avg_score_to_par in player_stats_snapshot")
            if implied_par_per_round_values:
                mean_implied_par = sum(implied_par_per_round_values) / len(implied_par_per_round_values)
                print(f"  mean(implied_avg_par/round) across those events = {mean_implied_par:.2f}  <- sanity check: should be within {_PLAUSIBLE_PAR_PER_ROUND}")
            if implausible_events:
                print(f"  ⚠ IMPLAUSIBLE implied par in {len(implausible_events)} event(s) (outside {_PLAUSIBLE_PAR_PER_ROUND}): {implausible_events}")
            else:
                print(f"  no implausible implied-par events found — score_to_par looks internally consistent with total_strokes for every event above.")
    finally:
        conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument(
        "--names", default=",".join(_DEFAULT_NAMES),
        help="comma-separated player names to look up first (default: the flagged players + a couple more)",
    )
    parser.add_argument("--count", type=int, default=5, help="total number of players to show (default 5)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    names = [n.strip() for n in args.names.split(",") if n.strip()]
    return diagnose(db_path, names, args.count)


if __name__ == "__main__":
    raise SystemExit(main())
