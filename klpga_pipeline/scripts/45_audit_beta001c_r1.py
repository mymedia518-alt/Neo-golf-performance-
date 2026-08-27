"""RED-TEAM AUDIT — scripts/45_audit_beta001c_r1.py

READ-ONLY. Audits an already-frozen BETA #001-C POST-R1 result
(produced by `scripts/35_predict_neo_win_post_r1.py --pre-family
beta001c --freeze`) against its own frozen PRE source, its own CSV
export, the real DB, and tournament_history.

Never writes to the DB (opened `mode=ro`), never modifies or
regenerates any prediction artifact, never touches the model. This
script only reads five already-existing files/tables and reports what
they say:
  - data/klpga.sqlite (round_number=1/2 player_round rows, field size)
  - neo_win_c_predictions/<year>/neo_win_c_<pre-prediction-id>_<game_code>.json
  - neo_win_predictions/<year>/neo_win_<r1-prediction-id>_<game_code>.json
  - outputs/beta001_r1/BETA001_R1_FULL.csv
  - neo_tournament_history/<game_code>/R1.json

======================================================================
CHECKS
======================================================================
FAIL (hard, printed as [FAIL]):
  - the R1 snapshot's own `pre_prediction_id` disagrees with the PRE
    file it claims to have used, or that id is the legacy '001'
  - any round_number=2 row exists in the DB for this game_code (future-
    round leakage into an R1-stage snapshot)
  - duplicate player_code, non-field player_code, or WIN sum more than
    1 percentage point off 100%
  - the CSV export and the JSON snapshot disagree on the player set
    (drift/corruption between the two files scripts/35 wrote together)

WARN (soft, printed as [WARN]):
  - players missing real R1 data (disclosed exclusion, not a defect —
    but worth surfacing)
  - the DB's real round_number=1 row count no longer matches the
    snapshot's `entrants_scored` (DB rows may have changed since freeze)
  - tournament_history's R1 slot is absent or occupied by a
    HISTORICAL_SNAPSHOT_MISSING marker (PRE->R1 movement is then only
    preserved in the append-only round-update JSON/CSV, not in
    tournament_history)

VERDICT is FAIL if any [FAIL] fired, else WARN if any [WARN] fired,
else PASS.

======================================================================
PROVENANCE — never changes the frozen snapshot
======================================================================
Two read-only, evidence-only cross-checks against the DB, reported
purely as information (never used to alter the already-frozen R1
result):
  - which of the snapshot's own `missing_r1_data` players now have a
    real round_number=1 row in the current DB (DB changed after freeze).
  - for every `missing_r1_data` player, a WD / DQ / DNS-or-collection-
    gap / UNKNOWN classification read from `player_event`'s confirmed
    `withdrawn`/`disqualified` flags — never guessed, never WD/DQ
    unless the DB's own boolean flag says so.

Usage:
    python scripts/45_audit_beta001c_r1.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-cutoff-date 2026-08-27 --pre-prediction-id 001-C-FINAL --r1-prediction-id 001-C-R1
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import archive_paths  # noqa: E402
from klpga.neo_win.beta001c_archive import (  # noqa: E402
    archive_paths as c_archive_paths,
    read_neo_win_c_snapshot,
)
from klpga.neo_win.player_status import classify_player_round_status  # noqa: E402
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_R1,
    STATUS_HISTORICAL_SNAPSHOT_MISSING,
    STATUS_RECORDED,
    history_stage_path,
    read_effective_history_stage,
)

ROOT = Path(__file__).resolve().parents[1]


def _r2_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 2", (game_code,)
    ).fetchone()[0]


def _r1_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 1 AND round_to_par IS NOT NULL",
        (game_code,),
    ).fetchone()[0]


def _r1_player_codes(conn: sqlite3.Connection, game_code: str) -> set:
    return {
        player_id
        for (player_id,) in conn.execute(
            "SELECT DISTINCT player_id FROM player_round WHERE game_code = ? AND round_number = 1 "
            "AND round_to_par IS NOT NULL",
            (game_code,),
        )
    }


def _field_size(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT player_code) FROM tournament_entry WHERE game_code = ?", (game_code,)
    ).fetchone()[0]


def _r1_row_detail(conn: sqlite3.Connection, game_code: str, player_code: str) -> Optional[dict]:
    """Full real detail for a player's round_number=1 player_round row
    — used only for provenance reporting (item 7's 115-vs-116
    investigation), never to alter the already-frozen snapshot."""
    row = conn.execute(
        "SELECT player_name, round_score, round_to_par, finish_position_after_round "
        "FROM player_round WHERE game_code = ? AND round_number = 1 AND player_id = ?",
        (game_code, player_code),
    ).fetchone()
    if row is None:
        return None
    player_name, round_score, round_to_par, finish_position_after_round = row
    return {
        "player_name": player_name, "round_score": round_score, "round_to_par": round_to_par,
        "finish_position_after_round": finish_position_after_round,
        # round_to_par IS NOT NULL is exactly the condition _r1_player_codes/_r1_row_count already
        # require — so any row reaching this helper already represents a completed R1 score, never
        # a bare status-only record with no score.
        "is_completed_score": round_to_par is not None,
    }


def _classify_missing_r1_player(conn: sqlite3.Connection, game_code: str, player_code: str):
    """Thin wrapper: R1-specific call into the shared, reusable
    klpga.neo_win.player_status classifier (also used by scripts/44 for
    R2, and any future R3/R4 script) — never a locally-duplicated copy
    of the classification logic."""
    return classify_player_round_status(conn, game_code, player_code, round_number=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", default="2026080001")
    parser.add_argument("--pre-cutoff-date", required=True, help="cutoff_date used to freeze both PRE and R1.")
    parser.add_argument("--c-predictions-dir", default=str(ROOT / "neo_win_c_predictions"))
    parser.add_argument("--pre-prediction-id", default="001-C-FINAL")
    parser.add_argument("--predictions-dir", default=str(ROOT / "neo_win_predictions"))
    parser.add_argument("--r1-prediction-id", default="001-C-R1")
    parser.add_argument("--full-csv", default=str(ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"))
    parser.add_argument("--history-dir", default=str(ROOT / "neo_tournament_history"))
    args = parser.parse_args()

    fails: list[str] = []
    warns: list[str] = []

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    # --- PRE (#001-C) ---
    pre_json_path, _ = c_archive_paths(
        Path(args.c_predictions_dir), args.pre_prediction_id, args.game_code, args.pre_cutoff_date
    )
    if not pre_json_path.exists():
        print(f"ERROR: frozen BETA #001-C PRE snapshot not found at {pre_json_path}.")
        return 5
    pre_snapshot = read_neo_win_c_snapshot(pre_json_path)
    pre_win_by_code = {e.player_code: e.win_probability for e in pre_snapshot.predictions}
    pre_field_codes = {e.player_code for e in pre_snapshot.predictions}

    # --- R1 round-update snapshot (raw dict: round_update_archive.py has no dedicated reader —
    # same convention klpga.neo_win.tournament_history.history_entry_from_round_update_dict uses) ---
    r1_json_path, _ = archive_paths(Path(args.predictions_dir), args.r1_prediction_id, args.game_code, args.pre_cutoff_date)
    if not r1_json_path.exists():
        print(f"ERROR: frozen R1 snapshot not found at {r1_json_path}.")
        return 6
    r1_data = json.loads(r1_json_path.read_text(encoding="utf-8"))
    r1_predictions = r1_data.get("predictions", [])

    pre_source_confirmed = (
        r1_data.get("pre_prediction_id") == pre_snapshot.prediction_id == args.pre_prediction_id
        and args.pre_prediction_id != "001"
    )
    if not pre_source_confirmed:
        fails.append(
            f"PRE SOURCE NOT CONFIRMED: R1 snapshot's pre_prediction_id={r1_data.get('pre_prediction_id')!r}, "
            f"PRE file's own prediction_id={pre_snapshot.prediction_id!r}, expected={args.pre_prediction_id!r}"
        )

    # --- CSV cross-check ---
    csv_path = Path(args.full_csv)
    csv_rows: list[dict] = []
    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig") as f:
            csv_rows = list(csv.DictReader(f))
    else:
        warns.append(f"CSV not found at {csv_path} — skipping JSON/CSV cross-check.")

    json_codes = {p["player_code"] for p in r1_predictions}
    csv_codes = {r["player_code"] for r in csv_rows} if csv_rows else set()
    if csv_rows and json_codes != csv_codes:
        fails.append(
            f"JSON/CSV PLAYER SET MISMATCH: json={len(json_codes)} csv={len(csv_codes)} "
            f"only_in_json={sorted(json_codes - csv_codes)[:5]} only_in_csv={sorted(csv_codes - json_codes)[:5]}"
        )

    # --- validations ---
    codes = [p["player_code"] for p in r1_predictions]
    duplicates = len(codes) - len(set(codes))
    non_field = [c for c in codes if c not in pre_field_codes]
    missing = [p["player_code"] for p in r1_predictions if p.get("missing_r1_data")]
    win_values = [p["post_r1_win_pct"] for p in r1_predictions if p.get("post_r1_win_pct") is not None]
    win_sum = sum(win_values)
    nulls = sum(1 for p in r1_predictions if p.get("post_r1_win_pct") is None)

    if duplicates:
        fails.append(f"DUPLICATES: {duplicates}")
    if non_field:
        fails.append(f"NON-FIELD PLAYERS: {len(non_field)} {non_field[:5]}")
    if abs(win_sum - 100.0) > 1.0:
        fails.append(f"WIN SUM off target: {win_sum:.4f}% (expected ~100%)")
    if missing:
        warns.append(f"{len(missing)} player(s) missing R1 data (disclosed, not fabricated): {missing}")

    # --- DB cross-check (leakage + real field counts + provenance, read-only) ---
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r2_count = _r2_row_count(conn, args.game_code)
        r1_db_count = _r1_row_count(conn, args.game_code)
        r1_db_codes = _r1_player_codes(conn, args.game_code)
        field_size_db = _field_size(conn, args.game_code)
        missing_classification = {code: _classify_missing_r1_player(conn, args.game_code, code) for code in missing}
        newly_available_row_detail = {}  # filled below, inside this same connection
        snapshot_all_codes = {p["player_code"] for p in r1_predictions}
        unexplained_r1_db_codes = sorted(r1_db_codes - snapshot_all_codes)
        entrants_scored = r1_data.get("entrants_scored")
        newly_available_players: list[str] = []
        if entrants_scored is not None and entrants_scored != r1_db_count:
            # provenance only — never changes the frozen snapshot. First: which of the snapshot's OWN
            # missing_r1_data players now have a real DB row (per item 6, POSITIVE evidence required —
            # `_r1_player_codes` already only returns rows with round_to_par IS NOT NULL, i.e. a real
            # completed score, never a bare status marker).
            newly_available_players = sorted(set(missing) & r1_db_codes)
            for code in newly_available_players:
                newly_available_row_detail[code] = _r1_row_detail(conn, args.game_code, code)
    finally:
        conn.close()

    if r2_count > 0:
        fails.append(
            f"LEAKAGE: {r2_count} round_number=2 row(s) exist in the DB for this game_code — an R1-stage "
            "snapshot must never have been generated once R2 data existed."
        )

    if entrants_scored is not None and entrants_scored != r1_db_count:
        warns.append(
            f"entrants_scored in snapshot ({entrants_scored}) != real round_number=1 row count in DB now "
            f"({r1_db_count}) — DB rows changed since the snapshot was frozen"
            + (f"; newly available since freeze: {newly_available_players}" if newly_available_players else "")
        )
    if unexplained_r1_db_codes:
        fails.append(
            f"DB has real round_number=1 row(s) for player_code(s) not present anywhere in the frozen R1 "
            f"snapshot (neither scored nor missing_r1_data): {unexplained_r1_db_codes} — NOT explained by a "
            "previously-missing player now scoring; this needs separate investigation as a possible field/"
            "identity mismatch, not assumed to be the same thing as the entrants_scored count change above."
        )

    # --- tournament_history (effective status: resolves a superseding RECORDED
    # event over a stale HISTORICAL_SNAPSHOT_MISSING marker — see
    # klpga.neo_win.tournament_history.read_effective_history_stage) ---
    history_path = history_stage_path(Path(args.history_dir), args.game_code, STAGE_R1)
    history_entry = read_effective_history_stage(Path(args.history_dir), args.game_code, STAGE_R1)

    if history_entry is None:
        history_status_line = f"NOT RECORDED — no R1 history record found under {args.history_dir}"
        durable_status = "NOT DURABLY RECORDED anywhere yet — only the append-only round-update JSON/CSV snapshot exists."
        warns.append("PRE->R1 movement is not durably recorded in tournament_history.")
    elif history_entry.status == STATUS_RECORDED:
        supersede_note = (
            f" (supersedes a MISSING marker recorded at {history_entry.supersedes_recorded_at_utc!r} — "
            "that marker is preserved untouched)"
            if history_entry.supersedes_recorded_at_utc
            else ""
        )
        history_status_line = (
            f"RECORDED (source_prediction_id={history_entry.source_prediction_id!r}, "
            f"field_size={history_entry.field_size}){supersede_note}"
        )
        durable_status = f"DURABLY RECORDED under {args.history_dir}/{args.game_code}/R1*.json{supersede_note}."
    elif history_entry.status == STATUS_HISTORICAL_SNAPSHOT_MISSING:
        history_status_line = (
            f"NOT RECORDED — slot occupied by a HISTORICAL_SNAPSHOT_MISSING marker "
            f"(reason: {history_entry.missing_reason!r})"
        )
        durable_status = "NOT DURABLY RECORDED — a stale MISSING marker occupies the (game_code, R1) slot."
        warns.append("PRE->R1 movement is NOT durably recorded — a stale MISSING marker occupies the slot.")
    else:
        history_status_line = f"UNKNOWN status {history_entry.status!r} at {history_path}"
        durable_status = "UNKNOWN."
        warns.append(f"Unexpected tournament_history status: {history_entry.status!r}")

    # --- TOP 20 ---
    ranked = sorted(
        r1_predictions,
        key=lambda p: (p.get("post_r1_win_pct") is None, -(p.get("post_r1_win_pct") or 0)),
    )[:20]

    # --- report ---
    print("=== BETA #001-C R1 AUDIT (READ-ONLY) ===")
    print()
    print(f"PRE source: {pre_json_path}")
    print(
        f"  prediction_id={pre_snapshot.prediction_id!r}  tournament={pre_snapshot.tournament_name!r}  "
        f"field_size={len(pre_field_codes)}"
    )
    print(f"  PRE source confirmed BETA #001-C: {pre_source_confirmed}")
    print(f"R1 source: {r1_json_path}")
    print(
        f"  prediction_id={r1_data.get('prediction_id')!r}  pre_prediction_id={r1_data.get('pre_prediction_id')!r}  "
        f"round_number={r1_data.get('round_number')}"
    )
    print()
    print(f"R1 player count (snapshot): {len(r1_predictions)}")
    print(f"R1 player count (real DB, round_number=1): {r1_db_count}")
    print(f"PRE field size (real DB tournament_entry): {field_size_db}")
    print()
    print(f"Missing/skipped players ({len(missing)}):")
    if missing:
        by_code = {p["player_code"]: p for p in r1_predictions}
        for code in missing:
            name = by_code[code].get("player_name")
            newly_available_note = " [PROVENANCE: DB now has a real R1 row for this player — see below]" if code in newly_available_players else ""
            status = missing_classification.get(code)
            print(
                f"  - {name} ({code}): no Round-1 score found in player_round at freeze time — excluded from the "
                "Monte Carlo field, reported with null post-R1 probabilities (round_update.py's "
                f"missing_r1_players).{newly_available_note}"
            )
            if status is not None:
                print(f"      ENTRY_FIELD: {status.in_entry_field}")
                print(f"      COMPLETED_R1: {status.completed_this_round}")
                print(f"      STARTED_R1: {status.started_this_round}")
                print(f"      rounds_played (whole tournament): {status.rounds_played_total!r}")
                print(f"      event_status (player_event flags): {status.event_status}")
                print(f"      finish_position: {status.finish_position!r}")
                print(f"      classification: {status.classification} — {status.detail}")
            else:
                print("      classification: UNKNOWN — not classified")
    else:
        print("  (none)")
    print()
    if newly_available_players or unexplained_r1_db_codes:
        print("=== PROVENANCE: DB CHANGED SINCE FREEZE (audit info only, frozen snapshot NOT modified) ===")
        print()
    if newly_available_players:
        print(f"{len(newly_available_players)} player(s) the frozen snapshot marked missing_r1_data=True now "
              f"have a real round_number=1 row in the current DB — never assumed to be 'a previously missing "
              "score', shown here with the actual row so you can judge:")
        for code in newly_available_players:
            detail = newly_available_row_detail.get(code)
            if detail is None:
                print(f"  - {code}: row disappeared between the two queries — re-run to confirm")
                continue
            print(
                f"  - {detail['player_name']} ({code}): round_score={detail['round_score']!r} "
                f"round_to_par={detail['round_to_par']!r} finish_position_after_round="
                f"{detail['finish_position_after_round']!r} — represents a COMPLETED R1 score "
                f"(round_to_par is not null): {detail['is_completed_score']}"
            )
        print("This does not change the already-frozen snapshot — it only explains why "
              f"entrants_scored ({entrants_scored}) differs from the DB's current round_number=1 row count "
              f"({r1_db_count}). When/where this row was inserted (a specific collection run) is not recorded "
              "anywhere in the schema — collected_at exists on tournament_entry, not on player_round.")
    if unexplained_r1_db_codes:
        print(f"{len(unexplained_r1_db_codes)} round_number=1 row(s) in the DB belong to player_code(s) not "
              f"present anywhere in the frozen R1/PRE snapshot at all: {unexplained_r1_db_codes} — this is a "
              "SEPARATE anomaly from the count above, not automatically the same explanation.")
    if newly_available_players or unexplained_r1_db_codes:
        print()
    print("=== TOP 20 — PRE WIN% -> R1 WIN% (delta) ===")
    print()
    for i, p in enumerate(ranked, start=1):
        pre_pct = round((pre_win_by_code.get(p["player_code"]) or 0) * 100, 3)
        r1_pct = p.get("post_r1_win_pct")
        delta = p.get("probability_change_from_pre")
        delta_str = "" if delta is None else f"{delta:+.4f}%"
        print(f"{i}. {p['player_name']} ({p['player_code']}): PRE {pre_pct}% -> R1 {r1_pct}% ({delta_str})")
    print()
    print("=== VALIDATION ===")
    print()
    print(f"WIN sum: {win_sum:.4f}%")
    print(f"Duplicates: {duplicates}")
    print(f"Nulls (no post_r1_win_pct): {nulls}")
    print(f"Non-field players: {len(non_field)} {non_field}")
    print(f"Leakage (round_number=2 rows in DB): {r2_count}")
    print()
    print("=== TOURNAMENT HISTORY (R1) ===")
    print()
    print(history_status_line)
    print()
    print("=== PRE->R1 DURABLE-RECORD STATUS ===")
    print()
    print(durable_status)
    print()

    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    print("=== RED TEAM VERDICT ===")
    print()
    print(f"VERDICT: {verdict}")
    for f in fails:
        print(f"  [FAIL] {f}")
    for w in warns:
        print(f"  [WARN] {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
