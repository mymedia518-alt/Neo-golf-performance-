"""BETA #001 R2 -> R3 evaluation pipeline — ONE-COMMAND workflow for
after Round 3 officially concludes. Two modes:

REAL MODE (default): STEP1 itself collects the real official Round 3
leaderboard live (network access required) and writes it into --db —
it does NOT assume round_number=3 already exists in player_round.
Reuses the SAME, already-established collection routine
scripts/run_beta001_r2_update.py's own STEP1 uses (klpga.collectors.
leaderboard.collect_all_rounds_for_game + klpga.collectors.aggregate.
build_rows + klpga.db.upsert), with the same targeted cache-bypass fix
(force_refresh_rounds={3}) for the same real bug: if Round 3 was ever
probed before it had actually been played, the site's real (empty)
response at the time got cached, and a plain re-run would keep serving
that stale empty page forever.

STEP3 reconciles the just-collected official Round 3 leaderboard
against the DB via klpga.neo_win.round_reconciliation.reconcile_round —
the SAME reusable gate scripts/50_validate_official_round.py already
uses for every round transition. A FAIL verdict HARD STOPS the whole
run before any prediction/CSV/freeze step.

STEP4 is a future-data-leakage guard: if even one round_number=4 row
already exists for --game-code, this HARD STOPS and generates nothing
— the same discipline scripts/46_predict_neo_win_post_r3.py's own
guard already established (see its module docstring).

STEP5-STEP8 reuse klpga.neo_win.round_update_r3.build_r3_sim_inputs_
from_frozen_snapshot / simulate_post_round3 (the SAME model math
scripts/46 uses, never modified or reimplemented) plus klpga.neo_win.
r3_pipeline_orchestrator.run_r3_evaluation_pipeline for reconciliation-
gated CSV writing and the optional STAGE_R3 freeze.

NEVER commits/pushes, NEVER writes to docs/index.html or any real
production page, NEVER touches the PRE/R1/R2 frozen artifacts.

DRY RUN MODE (--dry-run-fixture <path.json>): NEVER touches the
network, the real DB, or any real production/history file. Seeds an
isolated, temporary tournament-history directory from the fixture's
own "frozen_r2_entrants", then runs the exact same pipeline
(klpga.neo_win.r3_pipeline_orchestrator.run_r3_evaluation_pipeline)
against the fixture's "entry_r3" / "official_r3" / "db_r3" /
"r3_model_entrants" data, writing every output under --output-root
(never docs/, never neo_tournament_history/). See
scripts/fixtures/beta001_r3_dry_run_fixture.json.

Usage (dry run, proves the whole pipeline works today, no real R3 data needed):
    python scripts/run_beta001_r3_update.py --dry-run-fixture scripts/fixtures/beta001_r3_dry_run_fixture.json \\
        --game-code 2026080001 --output-root outputs/beta_r3_dry_run

Usage (real, once R3 officially finishes):
    python scripts/run_beta001_r3_update.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-cutoff-date 2026-08-27 --tournament-name "제15회 KG 레이디스 오픈" --freeze
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.player_status import (  # noqa: E402
    READINESS_HARD_STOP,
    READINESS_WARN,
    STATUS_COMPLETED,
    assess_field_readiness,
)
from klpga.neo_win.r3_pipeline_orchestrator import (  # noqa: E402
    reconciliation_report,
    run_r3_evaluation_pipeline,
)
from klpga.neo_win.round_reconciliation import (  # noqa: E402
    VERDICT_FAIL,
    NormalizedPlayer,
    normalize_db_round,
    normalize_official_round,
    reconcile_round,
)
from klpga.neo_win.round_update_r3 import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_r3_sim_inputs_from_frozen_snapshot,
    simulate_post_round3,
)
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_R2,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    write_history_stage_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "beta_r3"

_PASS = "PASS"
_FAIL = "FAIL"
_NA = "N/A (dry run)"


# ----------------------------------------------------------------
# Shared helpers (used by both dry-run and real mode)
# ----------------------------------------------------------------


def _normalized_players_from_fixture(rows: list[dict]) -> dict[str, NormalizedPlayer]:
    return {
        r["player_code"]: NormalizedPlayer(
            player_code=r["player_code"], player_name=r.get("player_name"),
            position_display=str(r["position"]) if r.get("position") is not None else r.get("status"),
            position=r.get("position"), round_score=r.get("round_score"), score_to_par=r.get("score_to_par"),
            status=r.get("status"),
        )
        for r in rows
    }


def _seed_dry_run_r2_history(history_dir: Path, game_code: str, tournament_name: str, entrants_fixture: list[dict]) -> None:
    entrants = tuple(
        HistoryEntrant(
            player_code=e["player_code"], player_name=e["player_name"], win_pct=e.get("win_pct"),
            top5_pct=e.get("top5_pct"), top10_pct=e.get("top10_pct"), top20_pct=e.get("top20_pct"),
            position=e.get("position"), score_to_par=e.get("score_to_par"),
        )
        for e in entrants_fixture
    )
    entry = HistoryStageSnapshot(
        game_code=game_code, stage=STAGE_R2, record_kind=RECORD_KIND, recorded_at_utc="DRY_RUN_FIXTURE",
        source_prediction_id="DRY_RUN", source_model_version="DRY_RUN", source_generated_at_utc="DRY_RUN_FIXTURE",
        tournament_name=tournament_name, field_size=len(entrants), entrants=entrants,
    )
    write_history_stage_atomic(entry, history_dir)


def _print_step9_report(*, dry_run: bool, collection, upsert, reconciliation, leakage, simulation,
                         win_sum_pct, r2_freeze_found, r3_freeze_status, csv_path, status) -> None:
    print("=== NEO GOLF DATA BETA #001 POST-R3 ===" + (" [DRY RUN]" if dry_run else ""))
    print()
    print(f"OFFICIAL R3 COLLECTION : {collection}")
    print(f"DATABASE UPSERT        : {upsert}")
    print(f"ROUND RECONCILIATION   : {reconciliation}")
    print(f"FUTURE DATA LEAKAGE    : {leakage}")
    print(f"SIMULATION             : {simulation}")
    print(f"WIN SUM                : {win_sum_pct}")
    print(f"R2 FREEZE              : {'FOUND' if r2_freeze_found else 'NOT FOUND'}")
    print(f"R3 FREEZE              : {r3_freeze_status}")
    print(f"CSV                    : {csv_path}")
    print(f"STATUS                 : {status}")


# ----------------------------------------------------------------
# DRY RUN MODE
# ----------------------------------------------------------------


def run_dry_run(args) -> int:
    fixture = json.loads(Path(args.dry_run_fixture).read_text(encoding="utf-8"))
    output_root = Path(args.output_root)
    history_dir = output_root / "_fixture_history"

    _seed_dry_run_r2_history(history_dir, args.game_code, args.tournament_name, fixture["frozen_r2_entrants"])

    entry_r3 = _normalized_players_from_fixture(fixture["entry_r3"])
    official_r3 = _normalized_players_from_fixture(fixture["official_r3"])
    db_r3 = _normalized_players_from_fixture(fixture["db_r3"])

    result = run_r3_evaluation_pipeline(
        game_code=args.game_code, tournament_name=args.tournament_name, history_dir=history_dir,
        entry_r3=entry_r3, official_r3=official_r3, db_r3=db_r3,
        r3_model_entrants=fixture["r3_model_entrants"], output_root=output_root,
        freeze=True,  # dry-run always exercises the freeze path, isolated under output_root/_fixture_history
        source_prediction_id="DRY_RUN", source_model_version="DRY_RUN", source_generated_at_utc="DRY_RUN_FIXTURE",
    )

    print("=== DRY RUN — BETA #001 R2 -> R3 EVALUATION PIPELINE ===")
    print("(no network, no real DB, no production files touched — fixture-driven only)")
    print()
    print(f"STATUS: {result['status']}")
    for step, detail in result.get("steps", {}).items():
        print(f"{step}: {detail}")
    print()

    reconciliation_verdict = result["steps"].get("STEP3_RECONCILIATION", {}).get("verdict")
    _print_step9_report(
        dry_run=True,
        collection=_NA, upsert=_NA,
        reconciliation=(_PASS if reconciliation_verdict != "FAIL" else _FAIL) if reconciliation_verdict else "N/A",
        leakage=_NA,
        simulation=_NA + " (fixture-supplied r3_model_entrants, simulate_post_round3 not exercised)",
        win_sum_pct=f"{result.get('win_sum_pct', 'unavailable')}%" if result.get("win_sum_pct") is not None else "unavailable",
        r2_freeze_found=result["steps"].get("STEP6_R2_TO_R3_DELTA_BASELINE", {}).get("found", False),
        r3_freeze_status=result.get("freeze_status", "N/A"),
        csv_path=result.get("csv_path", "N/A"),
        status="READY_FOR_REVIEW (dry run)" if result["status"] == "OK" else result["status"],
    )
    return 0 if result["status"] == "OK" else 5


# ----------------------------------------------------------------
# REAL MODE
# ----------------------------------------------------------------


def _collect_and_upsert_round3(conn: sqlite3.Connection, args) -> tuple[list, list, int]:
    """STEP1+STEP2 — real official R3 collection + upsert. Reuses the
    SAME, already-established collection routine
    scripts/run_beta001_r2_update.py's own STEP1 uses (klpga.collectors.
    leaderboard.collect_all_rounds_for_game + klpga.collectors.aggregate.
    build_rows), never a second, duplicate collector. `force_refresh_
    rounds={3}` bypasses any stale cached (possibly empty) Round 3
    response — the same fix STEP1's R2 counterpart already established.
    Returns (round3_rows, round2_rows, final_round_collected)."""
    from klpga.collectors.aggregate import build_rows, merge_player_rows
    from klpga.collectors.leaderboard import collect_all_rounds_for_game
    from klpga.db.upsert import upsert_player, upsert_player_event, upsert_player_round
    from klpga.http_client import PoliteHttpClient

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    rounds_data = collect_all_rounds_for_game(client, args.game_code, force_refresh_rounds=frozenset({3}))
    if 3 not in rounds_data or not rounds_data[3]:
        raise RuntimeError(
            f"official Round 3 leaderboard for game_code={args.game_code!r} is still empty after a forced, "
            "cache-bypassing fetch — Round 3 is not actually available on the official site yet. Nothing written."
        )

    season = int(args.season) if args.season else int(args.game_code[:4])
    final_round_collected = max(rounds_data.keys())
    merged = merge_player_rows(rounds_data)
    player_rows, player_event_rows, player_round_rows = build_rows(
        args.game_code, season, args.game_code, merged, final_round_collected
    )
    for row in player_rows:
        upsert_player(conn, row)
    for row in player_event_rows:
        upsert_player_event(conn, row)
    for row in player_round_rows:
        upsert_player_round(conn, row)
    conn.commit()

    return rounds_data[3], rounds_data.get(2, []), final_round_collected


def _normalize_entry_from_db(conn: sqlite3.Connection, game_code: str) -> dict[str, NormalizedPlayer]:
    """entry_r3's source: the local tournament_entry table (already
    collected by the entry-list collection layer) — deliberately not a
    second live entry-list fetch here (STEP1's official Round 3 fetch
    is the only new network call this script makes)."""
    rows = conn.execute(
        "SELECT player_code, player_name_display FROM tournament_entry WHERE game_code = ?", (game_code,)
    ).fetchall()
    return {
        code: NormalizedPlayer(
            player_code=code, player_name=name, position_display=None, position=None,
            round_score=None, score_to_par=None, status=None,
        )
        for code, name in rows
    }


def _r4_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 4", (game_code,)
    ).fetchone()[0]


def run_real(args) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(db_path)  # read-write — STEP1 writes real, freshly-collected Round 3 rows
    try:
        # STEP1 + STEP2 --------------------------------------------------
        try:
            official_round3_rows, official_round2_rows, final_round_collected = _collect_and_upsert_round3(conn, args)
        except RuntimeError as exc:
            print("STATUS: NOT_READY")
            print(f"REASON: {exc}")
            return 0
        print(f"STEP1: official R3 collection OK — {len(official_round3_rows)} Round 3 player rows fetched live "
              f"(cache bypassed) and upserted; final round collected so far: {final_round_collected}.")
        print("STEP2: upsert OK (player / player_event / player_round).")

        # STEP3 — reconciliation gate -------------------------------------
        entry_r3 = _normalize_entry_from_db(conn, args.game_code)
        official_r3 = normalize_official_round(official_round3_rows, round_number=3)
        db_r3 = normalize_db_round(conn, args.game_code, 3)

        reconciliation = reconcile_round(entry_r3, official_r3, db_r3, round_number=3)
        report = reconciliation_report(reconciliation)
        print(f"STEP3: reconciliation verdict={report['verdict']} "
              f"(SCORE_MISMATCH={len(report['score_mismatch'])} POSITION_MISMATCH={len(report['position_mismatch'])} "
              f"IDENTITY_MISMATCH={len(report['identity_mismatch'])} OFFICIAL_NOT_IN_DB={len(report['official_not_in_db'])} "
              f"DB_NOT_IN_OFFICIAL={len(report['db_not_in_official'])} ENTRY_ABSENT={len(report['entry_absent'])} "
              f"INCOMPLETE_OFFICIAL={len(report['incomplete_official'])} OFFICIAL_MISSING_IN_DB={len(report['official_missing_in_db'])})")
        if reconciliation.verdict == VERDICT_FAIL:
            print("STATUS: HARD_STOP")
            print(f"REASON: STEP3 official-vs-DB reconciliation returned FAIL — {report}. "
                  "No prediction, CSV, or freeze will be produced.")
            return 0

        # STEP4 — future data leakage guard --------------------------------
        r4_count = _r4_row_count(conn, args.game_code)
        leakage_ok = r4_count == 0
        if not leakage_ok:
            print("STATUS: HARD_STOP")
            print(f"REASON: FUTURE_DATA_LEAKAGE — {r4_count} round_number=4 row(s) already exist for "
                  f"game_code={args.game_code!r}. A POST-R3 snapshot generated now would leak Round-4 "
                  "information. Nothing written.")
            return 0

        readiness = assess_field_readiness(conn, args.game_code, round_number=3)
        status_by_code = {s.player_code: s for s in readiness.statuses}
        if readiness.verdict == READINESS_HARD_STOP:
            print("STATUS: HARD_STOP")
            print(f"REASON: {readiness.reason}")
            return 0

        r3_scores = dict(conn.execute(
            "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = 3 "
            "AND round_to_par IS NOT NULL", (args.game_code,),
        ).fetchall())
        r2_scores = dict(conn.execute(
            "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = 2 "
            "AND round_to_par IS NOT NULL", (args.game_code,),
        ).fetchall())
        r1_scores = dict(conn.execute(
            "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = 1 "
            "AND round_to_par IS NOT NULL", (args.game_code,),
        ).fetchall())
        made_cut = {
            pid: bool(mc) for pid, mc in conn.execute(
                "SELECT player_id, made_cut FROM player_event WHERE game_code = ?", (args.game_code,)
            )
        }

        # Prefer BETA #001-C's own PRE if a --pre-prediction-id wasn't forced (same convention scripts/46 uses).
        pre_snapshot = None
        pre_source = None
        if args.pre_prediction_id is None or args.pre_prediction_id == "001-C":
            c_path = Path(args.c_predictions_dir) / args.pre_cutoff_date[:4] / f"neo_win_c_001-C_{args.game_code}.json"
            if c_path.exists():
                pre_snapshot = read_neo_win_c_snapshot(c_path)
                pre_source = c_path
        if pre_snapshot is None:
            pid = args.pre_prediction_id or "001"
            pre_path, _c = archive_paths(Path(args.predictions_dir), pid, args.game_code, args.pre_cutoff_date)
            if not pre_path.exists():
                print(f"ERROR: no frozen PRE snapshot found at {pre_path} (or BETA #001-C equivalent).")
                return 4
            pre_snapshot = read_neo_win_snapshot(pre_path)
            pre_source = pre_path

        sim_inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
            pre_snapshot, r1_scores, r2_scores, r3_scores, made_cut
        )
    finally:
        conn.close()

    # STEP5 — simulation (after conn.close(), same ordering run_beta001_r2_update.py's run_real uses) -----
    rng = __import__("random").Random(args.seed) if args.seed is not None else None
    sim_result = simulate_post_round3(sim_inputs, n_simulations=args.n_simulations, rng=rng)

    positions_ordered = sorted(
        (
            (r1_scores.get(c, 0) + r2_scores.get(c, 0) + r3_scores.get(c, 0), c)
            for c in r3_scores if c in r1_scores and c in r2_scores
        ),
        key=lambda t: t[0],
    )
    position_by_code = {c: i + 1 for i, (_score, c) in enumerate(positions_ordered)}

    r3_model_entrants = []
    for inp in sim_inputs:
        code = inp.player_code
        sim = sim_result.get(code)
        has_full_score = code in r1_scores and code in r2_scores and code in r3_scores
        r3_model_entrants.append({
            "player_code": code, "player_name": inp.player_name,
            "position": position_by_code.get(code),
            "score_to_par": (r1_scores[code] + r2_scores[code] + r3_scores[code]) if has_full_score else None,
            "win_pct": sim["win_pct"] if sim else None,
            "top5_pct": sim["top5_pct"] if sim else None,
            "top10_pct": sim["top10_pct"] if sim else None,
            "top20_pct": sim["top20_pct"] if sim else None,
        })

    status_labels_by_code = {}
    for code, s in status_by_code.items():
        status_labels_by_code[code] = "ACTIVE" if s.classification == STATUS_COMPLETED else s.classification

    # STEP6-STEP8 — reconciliation is re-verified inside the pure pipeline (never trusts the caller's
    # verdict blindly); CSV write + optional freeze only happen if that verdict is not FAIL.
    result = run_r3_evaluation_pipeline(
        game_code=args.game_code, tournament_name=args.tournament_name, history_dir=Path(args.history_dir),
        entry_r3=entry_r3, official_r3=official_r3, db_r3=db_r3,
        r3_model_entrants=r3_model_entrants, output_root=Path(args.output_root),
        status_labels_by_code=status_labels_by_code, freeze=args.freeze,
        source_prediction_id=getattr(pre_snapshot, "prediction_id", ""),
        source_model_version=getattr(pre_snapshot, "model_version", None) or getattr(pre_snapshot, "selected_model_id", ""),
        source_generated_at_utc=getattr(pre_snapshot, "created_at_utc", ""),
    )

    print()
    for step, detail in result.get("steps", {}).items():
        print(f"{step}: {detail}")
    print()
    print(f"PRE source: {pre_source}")
    if missing:
        print(f"Missing r1/r2/r3/cut data (SKIP+LOG, excluded from simulation): {missing}")
    if readiness.verdict == READINESS_WARN:
        print(f"WARN: {readiness.reason}")

    reconciliation_verdict = result["steps"].get("STEP3_RECONCILIATION", {}).get("verdict")
    print()
    _print_step9_report(
        dry_run=False,
        collection=_PASS, upsert=_PASS,
        reconciliation=_PASS if reconciliation_verdict != "FAIL" else _FAIL,
        leakage=_PASS,
        simulation=_PASS,
        win_sum_pct=f"{result.get('win_sum_pct', 'unavailable')}%" if result.get("win_sum_pct") is not None else "unavailable",
        r2_freeze_found=result["steps"].get("STEP6_R2_TO_R3_DELTA_BASELINE", {}).get("found", False),
        r3_freeze_status=result.get("freeze_status", result.get("reason", "N/A")),
        csv_path=result.get("csv_path", "N/A"),
        status="READY_FOR_REVIEW" if result["status"] == "OK" else result["status"],
    )
    return 0 if result["status"] == "OK" else 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--tournament-name", default="")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--dry-run-fixture", default=None, help="Path to a JSON fixture; if set, runs in dry-run mode (no network/DB/production access).")
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--season", default=None, type=int,
                         help="Defaults to the first 4 digits of --game-code (e.g. 2026080001 -> season 2026).")
    parser.add_argument("--pre-cutoff-date", default=None)
    parser.add_argument("--pre-prediction-id", default=None)
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--c-predictions-dir", default=str(DEFAULT_C_PREDICTIONS_DIR))
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--cache-dir", default=str(ROOT / "cache" / "http"))
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--freeze", action="store_true", help="Freeze + record STAGE_R3 in tournament history after a successful run.")
    args = parser.parse_args()

    if args.dry_run_fixture:
        return run_dry_run(args)

    if not args.pre_cutoff_date:
        print("ERROR: --pre-cutoff-date is required in real mode (omit only with --dry-run-fixture).")
        return 2
    return run_real(args)


if __name__ == "__main__":
    raise SystemExit(main())
