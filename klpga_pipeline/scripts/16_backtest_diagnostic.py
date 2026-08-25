"""Read-only point-in-time feature diagnostic — no DB writes.

For one historical target tournament (by --game-code) and a set of its
field players, prints exactly what klpga.backtest computed and why:
  - the target tournament and the feature cutoff date used (and whether
    it came from the confirmed start_date field or a end_date fallback)
  - the field reconstruction and its documented limitation
  - for each selected player: the EXACT prior tournaments used for
    every feature, the exact recent-form events used per window, and
    the final point-in-time feature values
  - the target tournament's actual result, printed SEPARATELY under a
    "LABEL" heading — never mixed into the feature listing above it

This is the audit tool for red-team requirement #9 — every number this
script prints comes straight from klpga.backtest.point_in_time_features
/ klpga.backtest.walk_forward, the same code path the walk-forward
dataset itself is built from (see that package for the leakage-test
guarantees this script lets a human spot-check by eye).

Usage (works against any DB already populated by 02_collect_leaderboards.py
/ 04_collect_single_tournament.py — no network access needed, this only
reads tournament_master/player_event/player_round):
    python scripts/16_backtest_diagnostic.py --db data/klpga.sqlite --game-code 2026080002
    python scripts/16_backtest_diagnostic.py --db data/klpga.sqlite --game-code 2026080002 --players 10296,9174
    python scripts/16_backtest_diagnostic.py --db data/klpga.sqlite --game-code 2026080002 --sample 5
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.backtest.historical_field import reconstruct_historical_field  # noqa: E402
from klpga.backtest.point_in_time_features import (  # noqa: E402
    FEATURE_COLUMNS,
    compute_point_in_time_features,
    load_corpus,
)
from klpga.backtest.temporal import effective_tournament_date  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def run(conn: sqlite3.Connection, game_code: str, player_codes: list[str] | None, sample: int) -> int:
    target_row = conn.execute(
        "SELECT event_id, game_code, event_name, start_date, end_date FROM tournament_master WHERE game_code = ?",
        (game_code,),
    ).fetchone()
    if target_row is None:
        print(f"ERROR: no tournament_master row for game_code={game_code!r}.")
        return 2
    target_event_id, target_game_code, target_name, start_date, end_date = target_row

    eff = effective_tournament_date(start_date, end_date)
    print("=" * 88)
    print(f"TARGET TOURNAMENT: {target_name!r}  game_code={target_game_code}  event_id={target_event_id}")
    print(f"  raw start_date={start_date!r}  raw end_date={end_date!r}")
    if eff.value is None:
        print("  NO RESOLVABLE EFFECTIVE DATE — this tournament cannot be used as a walk-forward "
              "target (see klpga.backtest.walk_forward); every feature below would be computed "
              "with zero history as a fail-safe, which would NOT reflect reality.")
        return 1
    print(f"  feature cutoff date (effective_date) = {eff.value.isoformat()} "
          f"({'exact: from confirmed start_date' if eff.is_exact else 'FALLBACK: start_date was NULL, used end_date instead'})")

    field_result = reconstruct_historical_field(conn, target_event_id)
    print(f"\nFIELD: {len(field_result.members)} player(s) reconstructed from: {field_result.source}")
    if not field_result.members:
        print("  Empty field — nothing to compute features for.")
        return 1

    members_by_code = {m.player_code: m for m in field_result.members}

    if player_codes:
        selected = []
        for code in player_codes:
            member = members_by_code.get(code)
            if member is None:
                print(f"\nNOTE: requested player_code={code!r} is NOT in this target's reconstructed field — skipping.")
                continue
            selected.append(member)
    else:
        selected = list(field_result.members)[:sample]

    if not selected:
        print("\nNo players selected/found to report on.")
        return 1

    corpus = load_corpus(conn)
    tournament_names = {
        row[0]: row[1]
        for row in conn.execute("SELECT event_id, event_name FROM tournament_master")
    }

    for member in selected:
        features = compute_point_in_time_features(
            corpus, target_event_id, eff.value, member.player_code, member.player_name
        )
        print("\n" + "-" * 88)
        print(f"PLAYER: {member.player_name} (player_code={member.player_code})")

        print(f"  Exact prior tournaments used ({features.prior_events_n}):")
        for event_id in features.prior_event_ids_used:
            name = tournament_names.get(event_id, "?")
            event_date = corpus.tournament_dates.get(event_id)
            date_str = event_date.value.isoformat() if event_date and event_date.value else "?"
            print(f"    - {event_id}  ({date_str})  {name!r}")
        if not features.prior_event_ids_used:
            print("    (none — zero prior events; this is a rookie/debuting-player row)")

        print("  Exact recent-form events used per window:")
        for window, event_ids in sorted(features.recent_form_event_ids_used.items()):
            print(f"    window={window}: {event_ids if event_ids else '(none)'}")

        print(f"  Prior (event_id, round_number) keys used for round-level features: "
              f"{len(features.prior_round_keys_used)}")

        print("  FEATURE VALUES (point-in-time, computed strictly from the tournaments above):")
        for col in FEATURE_COLUMNS:
            print(f"    {col} = {getattr(features, col)}")

        print("  LABEL (target tournament's own outcome — NOT a feature, shown separately):")
        print(f"    finish_position = {member.label_finish_position!r}")
        print(f"    finish_position_numeric = {member.label_finish_position_numeric!r}")
        print(f"    made_cut = {member.label_made_cut}")
        print(f"    is_winner = {member.label_is_winner}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True, dest="game_code")
    parser.add_argument("--players", default=None, help="comma-separated player_codes to inspect")
    parser.add_argument("--sample", type=int, default=5, help="if --players not given, inspect the first N field members")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        player_codes = [c.strip() for c in args.players.split(",")] if args.players else None
        return run(conn, args.game_code, player_codes, args.sample)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
