"""BETA #001 R1 -> R2 ground-truth CUT-status diagnostic — DOUBLE
VERIFICATION phase. Read-only against everything: no DB is opened, no
model/prediction/evaluation logic runs, docs/ is never touched. Only
collects real official Round 1/Round 2 leaderboard data live, writes
it to disk in full (every raw field), and builds the comparison table
requested for establishing real CUT/MISSED_CUT ground truth.

GROUND TRUTH CHECK A (Round 2, real, always run by this script):
reuses klpga.collectors.leaderboard.collect_all_rounds_for_game with
force_refresh_rounds={2} (the same real-data fix used by
scripts/run_beta001_r2_update.py's STEP1 — bypasses any stale cached-
empty Round 2 response) against the real, confirmed roundLeaderboard
endpoint. Writes raw_r1.csv and raw_r2.csv preserving EVERY raw
PlayerRoundRow field.

GROUND TRUTH CHECK B (Round 3 grouping/tee-time): NO CONFIRMED
ENDPOINT EXISTS in this codebase for this page — every other endpoint
this project uses was discovered from a real, human-captured browser
Network-tab request before any collector was written against it (see
docs/SITE_STRUCTURE_TODO.md). This script therefore NEVER guesses a
URL for it. Pass --r3-grouping-json pointing to a JSON file (a list of
{"player_code", "player_name", "group", "tee_time", "starting_tee"}
objects) built from real data once the real endpoint/page is confirmed
(the same "capture it, then build a real parser" precedent
klpga.parsers.entry_list_parser followed for the entry-list page).
Omitting it is a real, honest "not collected yet" state — the
comparison table and printed counts say so explicitly, never silently
filling in a guess.

Usage:
    python scripts/diagnose_r2_r3_ground_truth.py --game-code 2026080001
    python scripts/diagnose_r2_r3_ground_truth.py --game-code 2026080001 \\
        --r3-grouping-json path/to/real_r3_grouping.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.leaderboard import collect_all_rounds_for_game  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.neo_win.ground_truth_diagnostic import (  # noqa: E402
    STATUS_UNRESOLVED,
    R3GroupingRow,
    build_ground_truth_table,
    raw_round_row_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "ground_truth_diagnostic"
DEFAULT_CACHE_DIR = ROOT / "cache" / "http"

_RAW_CSV_FIELDNAMES = (
    "game_code", "player_code", "player_name", "player_eng_name", "round_number",
    "rank_display", "rank", "tie_flag", "status",
    "total_under_par_display", "total_under_par",
    "today_under_par_display", "today_under_par",
    "total_strokes", "holes_completed",
    "round1_score", "round2_score", "round3_score", "round4_score",
)

_COMPARISON_CSV_FIELDNAMES = (
    "player_code", "official_name", "R1_present", "R2_present", "R2_raw_rank", "R2_raw_status",
    "R2_round_score", "R2_total_score", "R3_grouping_present", "R3_group", "R3_tee_time",
    "proposed_cut_status", "reason",
)


def _write_raw_csv(rows: list, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_RAW_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(raw_round_row_to_dict(row))


def _write_comparison_csv(rows, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_COMPARISON_CSV_FIELDNAMES)
        for r in rows:
            writer.writerow(
                [
                    r.player_code, r.official_name, r.r1_present, r.r2_present, r.r2_raw_rank, r.r2_raw_status,
                    r.r2_round_score, r.r2_total_score, r.r3_grouping_present, r.r3_group, r.r3_tee_time,
                    r.proposed_cut_status, r.reason,
                ]
            )


def _load_r3_grouping(path: str) -> list[R3GroupingRow]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        R3GroupingRow(
            player_code=row["player_code"], player_name=row.get("player_name"),
            group=row.get("group"), tee_time=row.get("tee_time"), starting_tee=row.get("starting_tee"),
        )
        for row in data
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--r3-grouping-json", default=None,
        help="Path to a real Round 3 grouping/tee-time JSON file (see module docstring). Omit if not yet collected.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    print("=== GROUND TRUTH DIAGNOSTIC — BETA #001 R1 -> R2 (double verification) ===")
    print("Read-only: no DB opened, no model/evaluation logic runs, docs/ never touched.")
    print()

    print("=== GROUND TRUTH CHECK A: official Round 2 leaderboard (real, live) ===")
    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    rounds_data = collect_all_rounds_for_game(client, args.game_code, force_refresh_rounds=frozenset({2}))
    if 2 not in rounds_data or not rounds_data[2]:
        print(f"ERROR: official Round 2 leaderboard for game_code={args.game_code!r} is empty even after a "
              "forced, cache-bypassing fetch. Nothing written.")
        return 3
    r1_rows = rounds_data.get(1, [])
    r2_rows = rounds_data[2]
    _write_raw_csv(r1_rows, output_dir / "raw_r1.csv")
    _write_raw_csv(r2_rows, output_dir / "raw_r2.csv")
    print(f"Round 1 rows collected: {len(r1_rows)} -> {output_dir / 'raw_r1.csv'}")
    print(f"Round 2 rows collected: {len(r2_rows)} -> {output_dir / 'raw_r2.csv'}")
    print()

    print("=== GROUND TRUTH CHECK B: official Round 3 grouping/tee-time list ===")
    if args.r3_grouping_json:
        r3_grouping_rows = _load_r3_grouping(args.r3_grouping_json)
        print(f"Loaded {len(r3_grouping_rows)} real Round 3 grouping/tee-time rows from {args.r3_grouping_json}")
    else:
        r3_grouping_rows = []
        print("NOT AVAILABLE — no confirmed KLPGA endpoint exists in this codebase for Round 3 grouping/tee-time "
              "data (see this script's own module docstring). Pass --r3-grouping-json once a real capture is "
              "available. Proceeding with an empty Round 3 dataset — every player will report "
              f"proposed_cut_status={STATUS_UNRESOLVED!r} unless explicit WD/DQ evidence exists.")
    print()

    rows, summary = build_ground_truth_table(r1_rows, r2_rows, r3_grouping_rows)
    _write_comparison_csv(rows, output_dir / "comparison_table.csv")

    print("=== COMPARISON TABLE ===")
    print(f"Written: {output_dir / 'comparison_table.csv'}")
    print()
    print(f"total tournament players: {summary['total_tournament_players']}")
    print(f"R3 grouping player count: {summary['r3_grouping_player_count']}")
    print(f"R3 absent count: {summary['r3_absent_count']}")
    print(f"explicit WD count: {summary['explicit_wd_count']}")
    print(f"explicit DQ count: {summary['explicit_dq_count']}")
    print(f"unexplained count: {summary['unexplained_count']}")
    print()

    unresolved = [r for r in rows if r.proposed_cut_status == STATUS_UNRESOLVED]
    if unresolved:
        print(f"=== FULL RAW ROUND 2 EVIDENCE FOR ALL {len(unresolved)} UNRESOLVED PLAYERS ===")
        for r in unresolved:
            print(
                f"  player_code={r.player_code} name={r.official_name!r} "
                f"R1_present={r.r1_present} R2_present={r.r2_present} "
                f"R2_raw_rank={r.r2_raw_rank!r} R2_raw_status={r.r2_raw_status!r} "
                f"R2_round_score={r.r2_round_score!r} R2_total_score={r.r2_total_score!r} "
                f"reason={r.reason!r}"
            )
    print()
    print("No CUT status was guessed. Nothing was written to any DB, model, prediction, or docs/ file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
