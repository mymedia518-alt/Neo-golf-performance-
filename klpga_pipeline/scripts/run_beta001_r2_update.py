"""BETA #001 R1 -> R2 evaluation pipeline — Section J's ONE-COMMAND
workflow. Two modes:

REAL MODE (default): STEP1 itself collects the real official Round 2
leaderboard live (network access required) and writes it into --db —
it does NOT assume round_number=2 already exists in player_round.
Reuses the same, already-established, CUT/WD/DQ-correct collection
routine scripts/04_collect_single_tournament.py itself uses
(klpga.collectors.leaderboard.collect_all_rounds_for_game +
klpga.collectors.aggregate.build_rows + klpga.db.upsert), with a
targeted cache-bypass fix (force_refresh_rounds={2}) for the real bug
this project hit: if Round 2 was ever probed before it had actually
been played, the site's real (empty) response at the time got cached,
and a plain re-run would keep serving that stale empty page forever.
Requires the frozen PRE snapshot for --game-code to exist on disk.
NEVER commits/pushes, NEVER writes to the real docs/index.html
production page or the R1 historical snapshot — those are STEP9's
job, and STEP9 only ever runs when explicitly requested via
--write-production AND only after STEP10's validation gate passes
(see klpga.neo_win.r2_pipeline_orchestrator).

DRY RUN MODE (--dry-run-fixture <path.json>): NEVER touches the
network, the real DB, or any real production/history file. Seeds an
isolated, temporary tournament-history directory from the fixture's
own "frozen_r1_entrants", then runs the exact same pipeline
(klpga.neo_win.r2_pipeline_orchestrator.run_r2_evaluation_pipeline)
against the fixture's "official_r2" / "r2_model_entrants" data,
writing every output under --output-root (never docs/, never
neo_tournament_history/). This is Section L's dry run, runnable as a
literal single command — see scripts/fixtures/beta001_r2_dry_run_fixture.json.

Usage (dry run, proves the whole pipeline works today, no real R2 data needed):
    python scripts/run_beta001_r2_update.py --dry-run-fixture scripts/fixtures/beta001_r2_dry_run_fixture.json \\
        --game-code 2026080001 --output-root outputs/beta_r2_dry_run

Usage (real, once R2 officially finishes):
    python scripts/run_beta001_r2_update.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-cutoff-date 2026-08-27 --tournament-name "제15회 KG 레이디스 오픈"
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
from klpga.neo_win.r2_pipeline_orchestrator import run_r2_evaluation_pipeline  # noqa: E402
from klpga.neo_win.round_reconciliation import NormalizedPlayer  # noqa: E402
from klpga.neo_win.round_update_r2 import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_r2_sim_inputs_from_frozen_snapshot,
    simulate_post_round2,
)
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_R1,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    write_history_stage_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUTS_CSV = ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "beta_r2"


def _seed_dry_run_history(history_dir: Path, game_code: str, tournament_name: str, entrants_fixture: list[dict]) -> None:
    entrants = tuple(
        HistoryEntrant(
            player_code=e["player_code"], player_name=e["player_name"], win_pct=e.get("win_pct"),
            make_cut_pct=e.get("make_cut_pct"), position=e.get("position"), score_to_par=e.get("score_to_par"),
        )
        for e in entrants_fixture
    )
    entry = HistoryStageSnapshot(
        game_code=game_code, stage=STAGE_R1, record_kind=RECORD_KIND, recorded_at_utc="DRY_RUN_FIXTURE",
        source_prediction_id="DRY_RUN", source_model_version="DRY_RUN", source_generated_at_utc="DRY_RUN_FIXTURE",
        tournament_name=tournament_name, field_size=len(entrants), entrants=entrants,
    )
    write_history_stage_atomic(entry, history_dir)


def _normalized_players_from_fixture(rows: list[dict]) -> dict:
    return {
        r["player_code"]: NormalizedPlayer(
            player_code=r["player_code"], player_name=r.get("player_name"),
            position_display=str(r["position"]) if r.get("position") is not None else r.get("status"),
            position=r.get("position"), round_score=r.get("round_score"), score_to_par=r.get("score_to_par"),
            status=r.get("status"),
        )
        for r in rows
    }


def run_dry_run(args) -> int:
    fixture = json.loads(Path(args.dry_run_fixture).read_text(encoding="utf-8"))
    output_root = Path(args.output_root)
    history_dir = output_root / "_fixture_history"

    _seed_dry_run_history(history_dir, args.game_code, args.tournament_name, fixture["frozen_r1_entrants"])
    official_r2 = _normalized_players_from_fixture(fixture["official_r2"])

    result = run_r2_evaluation_pipeline(
        game_code=args.game_code, tournament_name=args.tournament_name,
        history_dir=history_dir, predictions_dir=output_root / "_no_raw_predictions_dir",
        outputs_csv_path=output_root / "_no_csv_fallback.csv",
        official_r2=official_r2, r2_model_entrants=fixture["r2_model_entrants"],
        output_root=output_root,
    )

    print("=== DRY RUN — BETA #001 R1 -> R2 EVALUATION PIPELINE ===")
    print("(no network, no real DB, no production files touched — fixture-driven only)")
    print()
    print(f"STATUS: {result['status']}")
    for step, detail in result["steps"].items():
        print(f"{step}: {detail}")
    print()
    print(f"R2 HTML written to (isolated, non-production): {result.get('html_path')}")
    return 0 if result["status"] == "OK" else 5


def _collect_and_upsert_round2(conn: sqlite3.Connection, args) -> tuple[list, int]:
    """STEP1 — real official R2 collection. Reuses the SAME, already-
    established, CUT/WD/DQ-correct multi-round collection routine
    scripts/04_collect_single_tournament.py itself uses
    (klpga.collectors.leaderboard.collect_all_rounds_for_game +
    klpga.collectors.aggregate.build_rows), never a second, duplicate
    collector. `force_refresh_rounds={2}` is the fix for the real,
    confirmed bug: a prior collection run (before Round 2 existed)
    would have cached an EMPTY Round 2 response, and without this fix
    a later run would keep serving that stale empty page forever —
    silently never obtaining the real, now-complete Round 2 data (see
    klpga.collectors.leaderboard.collect_all_rounds_for_game's own
    docstring for the full mechanism). Writes real, freshly-collected
    rows via the same klpga.db.upsert functions 04 uses — never a
    second, parallel write path. Returns (round2_rows, final_round_
    collected) where round2_rows are the real PlayerRoundRow objects
    just fetched (reused directly for reconciliation — no second live
    fetch of the same data)."""
    from klpga.collectors.aggregate import build_rows, merge_player_rows
    from klpga.collectors.leaderboard import collect_all_rounds_for_game
    from klpga.db.upsert import upsert_player, upsert_player_event, upsert_player_round
    from klpga.http_client import PoliteHttpClient

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    rounds_data = collect_all_rounds_for_game(client, args.game_code, force_refresh_rounds=frozenset({2}))
    if 2 not in rounds_data or not rounds_data[2]:
        raise RuntimeError(
            f"official Round 2 leaderboard for game_code={args.game_code!r} is still empty after a forced, "
            "cache-bypassing fetch — Round 2 is not actually available on the official site yet. Nothing written."
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

    return rounds_data[2], final_round_collected


def run_real(args) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(db_path)  # read-write — STEP1 writes real, freshly-collected Round 2 rows
    try:
        try:
            official_round2_rows, final_round_collected = _collect_and_upsert_round2(conn, args)
        except RuntimeError as exc:
            print("STATUS: NOT_READY")
            print(f"REASON: {exc}")
            return 0
        print(f"STEP1: official R2 collection OK — {len(official_round2_rows)} Round 2 player rows fetched live "
              f"(cache bypassed) and upserted; final round collected so far: {final_round_collected}.")

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

        pre_snapshot = None
        if args.pre_prediction_id is None or args.pre_prediction_id == "001-C-FINAL":
            c_path = Path(args.c_predictions_dir) / args.pre_cutoff_date[:4] / f"neo_win_c_001-C-FINAL_{args.game_code}.json"
            if c_path.exists():
                pre_snapshot = read_neo_win_c_snapshot(c_path)
        if pre_snapshot is None:
            pid = args.pre_prediction_id or "001"
            pre_path, _c = archive_paths(Path(args.predictions_dir), pid, args.game_code, args.pre_cutoff_date)
            if not pre_path.exists():
                print(f"ERROR: no frozen PRE snapshot found at {pre_path} (or BETA #001-C equivalent).")
                return 4
            pre_snapshot = read_neo_win_snapshot(pre_path)

        sim_inputs, _missing = build_r2_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores, r2_scores, made_cut)
        sim_result = simulate_post_round2(sim_inputs, n_simulations=args.n_simulations)

        positions_ordered = sorted(
            ((r1_scores.get(c, 0) + r2_scores.get(c, 0), c) for c in r2_scores if c in r1_scores), key=lambda t: t[0]
        )
        position_by_code = {c: i + 1 for i, (_score, c) in enumerate(positions_ordered)}

        r2_model_entrants = []
        for inp in sim_inputs:
            sim = sim_result.get(inp.player_code)
            r2_model_entrants.append({
                "player_code": inp.player_code, "player_name": inp.player_name,
                "position": position_by_code.get(inp.player_code),
                "score_to_par": (r1_scores[inp.player_code] + r2_scores[inp.player_code]) if (inp.player_code in r1_scores and inp.player_code in r2_scores) else None,
                "win_pct": sim["win_pct"] if sim else None,
                "make_cut_pct": sim["make_cut_pct"] if sim else None,
            })

        from klpga.neo_win.round_reconciliation import normalize_official_round

        # Reuses the SAME real Round 2 rows STEP1 just fetched live — never a second request.
        official_r2 = normalize_official_round(official_round2_rows, round_number=2)
    finally:
        conn.close()

    result = run_r2_evaluation_pipeline(
        game_code=args.game_code, tournament_name=args.tournament_name,
        history_dir=Path(args.history_dir), predictions_dir=Path(args.predictions_dir),
        outputs_csv_path=Path(args.outputs_csv_path), official_r2=official_r2,
        r2_model_entrants=r2_model_entrants, output_root=Path(args.output_root),
        r1_html_path=Path(args.r1_html_path) if args.r1_html_path else None,
        r1_html_expected_sha256=args.r1_html_expected_sha256,
    )

    print("=== BETA #001 R1 -> R2 EVALUATION PIPELINE ===")
    print()
    print(f"STATUS: {result['status']}")
    for step, detail in result["steps"].items():
        print(f"{step}: {detail}")
    print()
    print(f"R2 HTML written to (NOT production — copy to docs/ manually after review): {result.get('html_path')}")
    print("STEP9 (real production docs/index.html update): NOT PERFORMED by this script. "
          "Review the output above, then copy the files manually.")
    return 0 if result["status"] == "OK" else 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--tournament-name", default="")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--dry-run-fixture", default=None, help="Path to a JSON fixture; if set, runs in dry-run mode (no network/DB/production access).")
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--season", default=None, type=int,
                         help="Defaults to the first 4 digits of --game-code (the real, established game_code "
                              "convention, e.g. 2026080001 -> season 2026) — override only if that ever doesn't hold.")
    parser.add_argument("--pre-cutoff-date", default=None)
    parser.add_argument("--pre-prediction-id", default=None)
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--c-predictions-dir", default=str(DEFAULT_C_PREDICTIONS_DIR))
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--outputs-csv-path", default=str(DEFAULT_OUTPUTS_CSV))
    parser.add_argument("--cache-dir", default=str(ROOT / "cache" / "http"))
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--r1-html-path", default=None, help="Real docs/tournaments/.../r1/index.html path, for the unchanged-hash validation check.")
    parser.add_argument("--r1-html-expected-sha256", default=None)
    args = parser.parse_args()

    if args.dry_run_fixture:
        return run_dry_run(args)

    if not args.pre_cutoff_date:
        print("ERROR: --pre-cutoff-date is required in real mode (omit only with --dry-run-fixture).")
        return 2
    return run_real(args)


if __name__ == "__main__":
    raise SystemExit(main())
