"""Read-only PRODUCTION-DATA leakage invariance check — no DB writes,
does not touch tournament_master/player_master/player_event/
player_round/tournament_entry.

The automated adversarial tests in tests/test_point_in_time_features.py
insert SYNTHETIC rows to prove no leakage. This script instead picks a
REAL historical target tournament and a REAL player who has genuine
events both before AND after that target in the actual production
corpus, computes that player's point-in-time features for the target,
and then explicitly:
  1. Lists EVERY one of that player's real events in the whole corpus,
     classified as "used" (strictly before the target's cutoff) or
     "excluded" (on/after the cutoff, or the target itself).
  2. Confirms — by direct set comparison, not sampling — that
     `prior_event_ids_used` equals EXACTLY the "used" set: nothing
     excluded leaked in, and nothing that should have been used was
     dropped either.

This is an auditable example against real data, not a repeat of the
synthetic leakage tests.

Usage (on a machine with the real production data/klpga.sqlite):
    python scripts/18_leakage_invariance_check.py --db data/klpga.sqlite
    python scripts/18_leakage_invariance_check.py --db data/klpga.sqlite --game-code 2026030001 --player-code 10296
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.backtest.point_in_time_features import compute_point_in_time_features, load_corpus  # noqa: E402
from klpga.backtest.temporal import is_strictly_before  # noqa: E402
from klpga.backtest.walk_forward import build_walk_forward_dataset  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _auto_select_target(target_order):
    """The tournament nearest the middle of the corpus, chronologically
    — maximizes the chance real prior AND real later tournaments both
    exist around it, for a meaningful demonstration either way."""
    if not target_order:
        return None
    return target_order[len(target_order) // 2]


def _auto_select_player(corpus, target_event_id, target_effective_date):
    """The player with the most total player_event rows in the corpus
    who ALSO has at least one real event strictly before the target and
    at least one real event NOT strictly before it — a deterministic,
    non-arbitrary choice ("most prolific player with something to
    demonstrate on both sides"), not a hand-picked example."""
    candidates = []
    for player_id, events in corpus.events_by_player.items():
        before = [e for e in events if is_strictly_before(e.effective_date, target_effective_date)]
        not_before = [e for e in events if not is_strictly_before(e.effective_date, target_effective_date)]
        if before and not_before:
            candidates.append((len(events), player_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def run(conn: sqlite3.Connection, game_code: str | None, player_code: str | None) -> dict:
    corpus = load_corpus(conn)
    result = build_walk_forward_dataset(conn, corpus=corpus)

    if game_code:
        target = next((t for t in result.target_order if t.game_code == game_code), None)
        if target is None:
            print(f"ERROR: game_code={game_code!r} is not a usable target tournament (unknown or undated).")
            return {"status": "error"}
    else:
        target = _auto_select_target(result.target_order)
        if target is None:
            print("ERROR: no usable (dated) target tournaments in this DB.")
            return {"status": "error"}
        print(f"(auto-selected target: game_code={target.game_code}, the middle tournament chronologically)")

    if player_code:
        all_events = corpus.events_by_player.get(player_code, [])
        if not all_events:
            print(f"ERROR: player_code={player_code!r} has no player_event rows in this DB.")
            return {"status": "error"}
    else:
        player_code = _auto_select_player(corpus, target.event_id, target.effective_date)
        if player_code is None:
            print(
                "ERROR: no player in this corpus has BOTH a real event strictly before "
                f"AND a real event on/after target game_code={target.game_code} — cannot "
                "demonstrate exclusion for this target. Try --game-code for a tournament "
                "with more corpus on both sides of it."
            )
            return {"status": "error"}
        print(f"(auto-selected player: player_code={player_code}, the most prolific player "
              f"with real events on both sides of this target's cutoff)")
        all_events = corpus.events_by_player[player_code]

    print("=" * 92)
    print(f"TARGET: game_code={target.game_code}  event_id={target.event_id}  "
          f"effective_date={target.effective_date.isoformat()} "
          f"({'exact' if target.date_is_exact else 'end_date fallback'})")
    print(f"PLAYER: player_code={player_code}  ({len(all_events)} total player_event row(s) in the whole corpus)")

    used = [e for e in all_events if is_strictly_before(e.effective_date, target.effective_date)]
    excluded = [e for e in all_events if not is_strictly_before(e.effective_date, target.effective_date)]
    used.sort(key=lambda e: e.effective_date)
    excluded.sort(key=lambda e: (e.effective_date is None, e.effective_date))

    print(f"\nEvents classified as USED (strictly before {target.effective_date.isoformat()}): {len(used)}")
    for e in used:
        print(f"    - {e.event_id}  ({e.effective_date.isoformat()})")

    print(f"\nEvents classified as EXCLUDED (on/after cutoff, the target itself, or undated): {len(excluded)}")
    for e in excluded:
        reason = "IS THE TARGET" if e.event_id == target.event_id else (
            "undated" if e.effective_date is None else "on/after cutoff"
        )
        date_str = e.effective_date.isoformat() if e.effective_date else "?"
        print(f"    - {e.event_id}  ({date_str})  [{reason}]")

    features = compute_point_in_time_features(
        corpus, target.event_id, target.effective_date, player_code, player_code
    )

    used_ids = {e.event_id for e in used}
    actual_ids = set(features.prior_event_ids_used)
    passed = used_ids == actual_ids

    print("\n" + "-" * 92)
    print(f"prior_event_ids_used returned by compute_point_in_time_features: {sorted(actual_ids)}")
    print(f"Expected (our independent classification above):                {sorted(used_ids)}")
    print(f"\n{'PASS' if passed else 'FAIL'}: prior_event_ids_used {'==' if passed else '!='} the independently-classified USED set.")
    if not passed:
        print(f"  Leaked in (present in features but should be excluded): {sorted(actual_ids - used_ids)}")
        print(f"  Wrongly dropped (should be used but missing): {sorted(used_ids - actual_ids)}")

    excluded_that_leaked = {e.event_id for e in excluded} & actual_ids
    print(f"\n{'PASS' if not excluded_that_leaked else 'FAIL'}: none of the {len(excluded)} EXCLUDED events "
          f"(on/after cutoff or the target itself) appear in prior_event_ids_used.")

    return {
        "status": "success",
        "target_event_id": target.event_id,
        "player_code": player_code,
        "used_count": len(used),
        "excluded_count": len(excluded),
        "passed": passed and not excluded_that_leaked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", default=None, dest="game_code")
    parser.add_argument("--player-code", default=None, dest="player_code")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        outcome = run(conn, args.game_code, args.player_code)
    finally:
        conn.close()

    if outcome["status"] != "success":
        return 2
    return 0 if outcome["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
