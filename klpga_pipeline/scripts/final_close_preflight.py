"""FINAL CLOSE preflight — ONE reusable command that performs, in
order, every check this project had to debug manually file-by-file for
game_code=2026080001's Round-4 close, so a future tournament's round
close never needs that again:

  1. STALE-CACHE evidence for --expected-final-round (read-only,
     BEFORE collecting — never deletes/modifies the cache)
  2. Real collection with that round force-refreshed
     (klpga.collectors.single_tournament.collect_and_persist_tournament),
     HARD STOPPING (never a misleading success message) if the round
     actually discovered still falls short of --expected-final-round
  3. Real DB verification (player_round counts by round, WD/DQ/
     made_cut counts, tournament_master metadata, tournament_entry
     field-size sanity)
  4. Finalist identity reconciliation: --finalists roster vs. the
     official round fetch vs. the DB, with evidence-backed WD/DQ
     classification (klpga.neo_win.finalist_reconciliation)
  5. The existing field-readiness gate
     (klpga.neo_win.player_status.assess_field_readiness)
  6. A read-only existence check for the canonical frozen PRE/#001-C
     snapshot evaluate_r3_to_r4.py needs — reports MISSING honestly,
     never recreates or fabricates one

Ends with ONE consolidated GO / WARN / HARD_STOP verdict. HARD STOPs
rather than guessing whenever real evidence is missing or contradictory.

======================================================================
WHAT THIS SCRIPT NEVER DOES (by construction — none of these modules
are imported, so there is no code path that could)
======================================================================
  - freeze/write neo_r3_r4_evaluation/ (that's evaluate_r3_to_r4.py
    --freeze)
  - freeze/write neo_tournament_history/ (that's
    scripts/47_record_final_result.py --freeze)
  - touch docs/index.html or any docs/tournaments/.../index.html
  - modify, overwrite, or fabricate any PRE/R1/R2/R3
    neo_win_predictions/neo_win_c_predictions artifact — it only
    checks whether one exists
  - commit or push anything

Usage:
    python scripts/final_close_preflight.py \\
        --db data/klpga.sqlite --season 2026 --game-code 2026080001 \\
        --expected-final-round 4 --finalists data/roster/r3_finalists_2026080001.csv
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.cache_inspection import inspect_round_leaderboard_cache  # noqa: E402
from klpga.collectors.single_tournament import (  # noqa: E402
    STATUS_GAME_CODE_NOT_FOUND,
    STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND,
    collect_and_persist_tournament,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402
from klpga.neo_win.finalist_reconciliation import load_roster_csv, reconcile_finalists  # noqa: E402
from klpga.neo_win.player_status import READINESS_HARD_STOP, READINESS_WARN, assess_field_readiness  # noqa: E402
from klpga.neo_win.round_reconciliation import VERDICT_FAIL, normalize_db_round, normalize_official_round  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

GO, WARN, HARD_STOP = "GO", "WARN", "HARD_STOP"


def _write_json(json_out: str | None, summary: dict) -> None:
    """Best-effort machine-readable summary write. Never raises past
    this function — a JSON-write problem must never mask the real
    preflight result already printed to the console."""
    if not json_out:
        return
    try:
        path = Path(json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        summary.setdefault("generated_at_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: could not write --json-out {json_out!r}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--game-code", required=True, dest="game_code")
    parser.add_argument("--expected-final-round", type=int, required=True, dest="expected_final_round")
    parser.add_argument("--finalists", required=True, help="roster CSV: player_code,player_name")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument("--predictions-dir", default=str(ROOT / "neo_win_predictions"))
    parser.add_argument("--c-predictions-dir", default=str(ROOT / "neo_win_c_predictions"))
    parser.add_argument(
        "--json-out", default=None,
        help="Optional path to also write a machine-readable JSON summary (verdict, reasons, key counts) to.",
    )
    args = parser.parse_args()

    summary: dict = {
        "game_code": args.game_code, "season": args.season,
        "expected_final_round": args.expected_final_round, "verdict": None,
    }

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        summary["verdict"] = HARD_STOP
        summary["hard_stop_reasons"] = [f"--db {db_path} does not exist"]
        _write_json(args.json_out, summary)
        return 3

    finalists_path = Path(args.finalists)
    if not finalists_path.exists():
        print(f"ERROR: {finalists_path} does not exist.")
        summary["verdict"] = HARD_STOP
        summary["hard_stop_reasons"] = [f"--finalists {finalists_path} does not exist"]
        _write_json(args.json_out, summary)
        return 3
    roster_rows = load_roster_csv(finalists_path)

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    conn = sqlite3.connect(str(db_path))

    hard_stop_reasons: list[str] = []
    warn_reasons: list[str] = []

    print("=== BETA #001 FINAL CLOSE PREFLIGHT ===")
    print(f"game_code={args.game_code} season={args.season} expected_final_round={args.expected_final_round} "
          f"finalists={len(roster_rows)}")
    print()

    # --- STEP 1: stale-cache evidence (read-only, BEFORE collecting) ---
    print("=== STEP 1: STALE-CACHE CHECK (pre-collection, read-only) ===")
    pre_cache = inspect_round_leaderboard_cache(client, args.game_code, args.expected_final_round)
    if not pre_cache.exists:
        print(f"CACHE ENTRY: none at {pre_cache.cache_path} — nothing cached yet for round "
              f"{args.expected_final_round}.")
    else:
        print(f"CACHE ENTRY: {pre_cache.cache_path}")
        print(f"  mtime (UTC): {pre_cache.mtime_utc}")
        print(f"  body length: {pre_cache.body_length}")
        print(f"  parsed player rows: {pre_cache.player_row_count}")
        print(f"  STALE-EMPTY: {pre_cache.is_empty}")
        if pre_cache.is_empty:
            print("  -> Matches the exact signature of a round probed before it was actually played.")
    print()

    # --- STEP 2: force-refresh + collect ---
    print(f"=== STEP 2: COLLECT (force-refresh round {args.expected_final_round}) ===")
    try:
        collection = collect_and_persist_tournament(
            conn, client, args.season, args.game_code,
            force_refresh_rounds=frozenset({args.expected_final_round}),
            expected_final_round=args.expected_final_round,
            collection_run_source="final_close_preflight",
        )
    except RateLimitBlockedError as exc:
        print(f"BLOCKED: {exc}")
        conn.close()
        summary["verdict"] = HARD_STOP
        summary["hard_stop_reasons"] = [f"BLOCKED fetching live data: {exc}"]
        _write_json(args.json_out, summary)
        return 1
    except requests.exceptions.RequestException as exc:
        print(f"NETWORK ERROR: {exc}")
        conn.close()
        summary["verdict"] = HARD_STOP
        summary["hard_stop_reasons"] = [f"NETWORK ERROR fetching live data: {exc}"]
        _write_json(args.json_out, summary)
        return 1

    if collection.status == STATUS_GAME_CODE_NOT_FOUND:
        print(f"  STATUS: {collection.status}")
        print(f"  REASON: {collection.reason}")
        conn.close()
        print()
        print("=== FINAL VERDICT ===")
        print("VERDICT: HARD_STOP")
        print(f"  - COLLECTION: {collection.reason}")
        summary["verdict"] = HARD_STOP
        summary["hard_stop_reasons"] = [f"COLLECTION: {collection.reason}"]
        summary["collection_status"] = collection.status
        _write_json(args.json_out, summary)
        return 6

    for rnd, rows in sorted(collection.rounds_data.items()):
        print(f"  round={rnd}: {len(rows)} player rows")
    print(f"  final_round discovered: {collection.final_round}")
    print(f"  status: {collection.status}")
    if collection.status == STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND:
        print(f"  REASON: {collection.reason}")
        hard_stop_reasons.append(f"COLLECTION: {collection.reason}")
    print()

    summary["stale_cache"] = {
        "exists": pre_cache.exists, "is_empty": pre_cache.is_empty,
        "mtime_utc": pre_cache.mtime_utc, "player_row_count": pre_cache.player_row_count,
        "cache_path": str(pre_cache.cache_path),
    }
    summary["collection_status"] = collection.status
    summary["final_round_discovered"] = collection.final_round
    summary["official_rows_by_round"] = {str(r): len(rows) for r, rows in collection.rounds_data.items()}

    # --- STEP 3: DB verification (read-only) ---
    print("=== STEP 3: DB VERIFICATION (read-only) ===")
    round_counts = dict(conn.execute(
        "SELECT round_number, COUNT(*) FROM player_round WHERE game_code = ? "
        "GROUP BY round_number ORDER BY round_number",
        (args.game_code,),
    ).fetchall())
    if round_counts:
        for rnd in sorted(round_counts):
            print(f"  player_round round={rnd}: {round_counts[rnd]} rows")
    else:
        print("  player_round: NO ROWS for this game_code at all")
    r4_total = round_counts.get(args.expected_final_round, 0)
    r4_completed = conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = ? AND round_score IS NOT NULL",
        (args.game_code, args.expected_final_round),
    ).fetchone()[0]
    print(f"  round={args.expected_final_round} total rows: {r4_total}, completed-score rows: {r4_completed}")

    wd_sum, dq_sum, made_cut_sum = conn.execute(
        "SELECT SUM(withdrawn), SUM(disqualified), SUM(made_cut) FROM player_event WHERE game_code = ?",
        (args.game_code,),
    ).fetchone()
    print(f"  player_event: withdrawn={wd_sum or 0} disqualified={dq_sum or 0} made_cut={made_cut_sum or 0}")

    tm = conn.execute(
        "SELECT winner, winner_score, end_date, rounds_completed FROM tournament_master WHERE game_code = ?",
        (args.game_code,),
    ).fetchone()
    if tm:
        print(f"  tournament_master: winner={tm[0]!r} winner_score={tm[1]!r} end_date={tm[2]!r} "
              f"rounds_completed={tm[3]!r}")
    else:
        print("  tournament_master: NO ROW")

    entry_field_count = conn.execute(
        "SELECT COUNT(*) FROM tournament_entry WHERE game_code = ?", (args.game_code,)
    ).fetchone()[0]
    entry_warning = (
        " -- WARNING: zero rows means STEP 5's readiness gate below is VACUOUS (nothing to classify), "
        "NOT a real GO; run scripts/15_collect_entry_list.py first"
        if entry_field_count == 0 else ""
    )
    print(f"  tournament_entry rows: {entry_field_count}{entry_warning}")
    print()

    summary["db_verification"] = {
        "player_round_counts_by_round": {str(k): v for k, v in round_counts.items()},
        "expected_final_round_total_rows": r4_total,
        "expected_final_round_completed_score_rows": r4_completed,
        "player_event_withdrawn": wd_sum or 0, "player_event_disqualified": dq_sum or 0,
        "player_event_made_cut": made_cut_sum or 0,
        "tournament_master": (
            {"winner": tm[0], "winner_score": tm[1], "end_date": tm[2], "rounds_completed": tm[3]}
            if tm else None
        ),
        "tournament_entry_row_count": entry_field_count,
    }

    # --- STEP 4: 62-finalist identity reconciliation ---
    print("=== STEP 4: FINALIST RECONCILIATION (read-only) ===")
    official_rows_for_round = collection.rounds_data.get(args.expected_final_round, [])
    official_normalized = normalize_official_round(official_rows_for_round, args.expected_final_round)
    db_normalized = normalize_db_round(conn, args.game_code, args.expected_final_round)
    finalist_report = reconcile_finalists(
        conn, args.game_code, args.expected_final_round, roster_rows, official_normalized, db_normalized,
    )
    print(f"  EXPECTED FINALISTS: {finalist_report.expected_finalists}")
    print(f"  OFFICIAL R{args.expected_final_round}: {finalist_report.official_round_total} total "
          f"({finalist_report.official_round_in_roster} in roster)")
    print(f"  DB R{args.expected_final_round}: {finalist_report.db_round_total}")
    print(f"  MATCHED: {len(finalist_report.matched)}")
    print(f"  MISSING: {len(finalist_report.missing)} {finalist_report.missing}")
    print(f"  EXTRA: {len(finalist_report.extra)} {finalist_report.extra}")
    print(f"  WD: {len(finalist_report.wd)} {finalist_report.wd}")
    print(f"  DQ: {len(finalist_report.dq)} {finalist_report.dq}")
    print(f"  UNRESOLVED: {len(finalist_report.unresolved)} {finalist_report.unresolved}")
    print(f"  reconciliation verdict (roster-scoped): {finalist_report.verdict}")
    print()

    unexplained_missing = [
        c for c in finalist_report.missing if c not in finalist_report.wd and c not in finalist_report.dq
    ]
    if unexplained_missing:
        hard_stop_reasons.append(
            f"FINALIST RECONCILIATION: {len(unexplained_missing)} roster player(s) missing from official "
            f"R{args.expected_final_round} AND DB with NO WD/DQ evidence: {unexplained_missing}"
        )
    elif finalist_report.verdict == VERDICT_FAIL:
        hard_stop_reasons.append(
            f"FINALIST RECONCILIATION: verdict=FAIL — see anomalies: {finalist_report.anomalies}"
        )

    summary["finalist_reconciliation"] = {
        "expected_finalists": finalist_report.expected_finalists,
        "official_round_total": finalist_report.official_round_total,
        "official_round_in_roster": finalist_report.official_round_in_roster,
        "db_round_total": finalist_report.db_round_total,
        "matched": finalist_report.matched, "missing": finalist_report.missing,
        "extra": finalist_report.extra, "unresolved": finalist_report.unresolved,
        "wd": finalist_report.wd, "dq": finalist_report.dq,
        "verdict": finalist_report.verdict,
    }

    # --- STEP 5: readiness gate ---
    print(f"=== STEP 5: READINESS GATE (round={args.expected_final_round}) ===")
    if entry_field_count == 0:
        print("  SKIPPED — tournament_entry has zero rows for this game_code (see STEP 3 warning).")
        warn_reasons.append("READINESS: tournament_entry empty, readiness gate not meaningfully evaluable")
        summary["readiness"] = {"verdict": "SKIPPED", "reason": "tournament_entry empty"}
    else:
        readiness = assess_field_readiness(conn, args.game_code, round_number=args.expected_final_round)
        print(f"  VERDICT: {readiness.verdict}")
        print(f"  REASON: {readiness.reason}")
        if readiness.verdict == READINESS_HARD_STOP:
            hard_stop_reasons.append(f"READINESS: {readiness.reason}")
        elif readiness.verdict == READINESS_WARN:
            warn_reasons.append(f"READINESS: {readiness.reason}")
        summary["readiness"] = {"verdict": readiness.verdict, "reason": readiness.reason}
    print()

    # --- STEP 6: canonical frozen snapshot prerequisite (read-only existence check) ---
    print("=== STEP 6: CANONICAL FROZEN SNAPSHOT PREREQUISITE (read-only) ===")
    predictions_dir = Path(args.predictions_dir)
    c_predictions_dir = Path(args.c_predictions_dir)
    found = sorted(predictions_dir.glob(f"*/*{args.game_code}*.json")) + \
        sorted(c_predictions_dir.glob(f"*/*{args.game_code}*.json"))
    if found:
        print(f"  FOUND: {[str(p) for p in found]}")
    else:
        print(f"  MISSING: no file matching *{args.game_code}*.json under {predictions_dir} or {c_predictions_dir}")
        print("  This blocks evaluate_r3_to_r4.py — it cannot run without a real frozen PRE snapshot to compare "
              "against, and this script never fabricates or recreates one retroactively.")
        hard_stop_reasons.append(
            f"CANONICAL SNAPSHOT: no neo_win_predictions/neo_win_c_predictions file found for "
            f"game_code={args.game_code!r}."
        )
    print()
    summary["canonical_snapshot_found"] = [str(p) for p in found]

    conn.close()

    # --- FINAL VERDICT ---
    print("=== FINAL VERDICT ===")
    if hard_stop_reasons:
        verdict = HARD_STOP
    elif warn_reasons:
        verdict = WARN
    else:
        verdict = GO
    print(f"VERDICT: {verdict}")
    if hard_stop_reasons:
        print("HARD_STOP reasons:")
        for r in hard_stop_reasons:
            print(f"  - {r}")
    if warn_reasons:
        print("WARN reasons:")
        for r in warn_reasons:
            print(f"  - {r}")
    if verdict == GO:
        print("Every check passed. This script still never freezes/deploys anything itself — proceeding to "
              "47_record_final_result.py / evaluate_r3_to_r4.py / homepage work still requires your explicit "
              "approval.")

    summary["verdict"] = verdict
    summary["hard_stop_reasons"] = hard_stop_reasons
    summary["warn_reasons"] = warn_reasons
    _write_json(args.json_out, summary)

    return 0 if verdict != HARD_STOP else 6


if __name__ == "__main__":
    raise SystemExit(main())
