"""BETA #001 R1 MAKE CUT evaluation against the real, double-verified
R2 x R3 ground truth (klpga.neo_win.ground_truth_diagnostic) —
Section M: the FINAL step of the ground-truth reconciliation work,
answering "how good were the frozen R1 CUT predictions, really."

Read-only against everything real: no DB is opened, no write ever
touches predictions/, neo_win_predictions/, neo_win_c_predictions/,
neo_tournament_history/, docs/, or the historical R1 HTML/hash. This
NEVER recomputes a frozen R1 probability — `klpga.neo_win.
r1_frozen_snapshot.load_frozen_r1_snapshot` loads them as-is, and
`check_frozen_r1_values_unchanged` proves they were not mutated
mid-run. Do NOT publish these numbers anywhere until a human reviews
them.

STEP 1-2 (real, live): the same GROUND TRUTH CHECK A/B this project's
scripts/diagnose_r2_r3_ground_truth.py performs — collects the real
official Round 2 leaderboard, then fetches and parses the real Round 3
grouping/tee-time page (klpga.parsers.group_page_parser). A fetch or
parse failure aborts the run loudly (non-zero exit), never silently
falls back to "not collected".

STEP 3 (explicit, human-verified evidence only): --explicit-status-json
accepts a REAL, human-verified override for players whose Round 2
evidence is otherwise ambiguous (e.g. the 999/INCOMPLETE sentinel) —
e.g. literal "WD" status text a human directly observed on the real
official leaderboard (a screenshot, a different page than the
roundLeaderboard endpoint this project's collectors already probe).
This is never inferred here; format is a JSON list of
{"player_code", "status": "WD"|"DQ"}. These are classified
WD_AFTER_R1_START (for "WD") — a status kept SEPARATE from a generic
WD and from the entirely separate population of players who never had
a frozen R1 prediction at all (already-unavailable-before-R1 players;
klpga.neo_win.r1_r2_evaluation_report.build_player_cut_evaluation_rows
excludes those mechanically, since it only ever iterates frozen_r1).

STEP 4-8: builds the ground truth table (klpga.neo_win.
ground_truth_diagnostic.build_ground_truth_table), bridges it to the
existing evaluation pipeline (klpga.neo_win.ground_truth_cut_evaluation),
and reuses klpga.neo_win.cut_evaluation / klpga.neo_win.
r1_r2_evaluation_report / klpga.neo_win.win_interim_check UNCHANGED for
every metric: N evaluated, actual made/missed cut, 50% threshold
accuracy, Brier score, log loss, mean predicted vs actual CUT rate, the
5 calibration buckets, and the auto-selected TOP 5 BEST / TOP 5 BIGGEST
MISSES (never a hand-curated list). The R1 WIN% interim check is
retained, clearly labeled "INTERIM CHECK — NOT FINAL WIN PROBABILITY
EVALUATION" per klpga.neo_win.win_interim_check's own discipline.

STEP 9: runs the full hard-validation gate (klpga.neo_win.
r2_pipeline_validation) — every failure is printed; nothing is hidden.
The eligibility population (which players actually get scored) is
determined MECHANICALLY (frozen R1 probability exists AND a real
resolved outcome exists AND status is not WD/DQ/WD_AFTER_R1_START/
unresolved) — never hand-picked; check_eligibility_population_is_mechanical
proves this.

Usage:
    python scripts/evaluate_r1_cut_ground_truth.py --game-code 2026080001
    python scripts/evaluate_r1_cut_ground_truth.py --game-code 2026080001 \\
        --explicit-status-json path/to/explicit_wd_status.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.group_page import fetch_group_page_html  # noqa: E402
from klpga.collectors.leaderboard import collect_all_rounds_for_game  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.neo_win.cut_evaluation import calibration_report, summarize_cut_evaluation  # noqa: E402
from klpga.neo_win.ground_truth_cut_evaluation import (  # noqa: E402
    summarize_ground_truth_reconciliation,
    to_player_r2_reconciled_rows,
)
from klpga.neo_win.ground_truth_diagnostic import R3GroupingRow, build_ground_truth_table  # noqa: E402
from klpga.neo_win.r1_frozen_snapshot import load_frozen_r1_snapshot, SOURCE_NONE  # noqa: E402
from klpga.neo_win.r1_r2_evaluation_report import (  # noqa: E402
    build_player_cut_evaluation_rows,
    top5_best_and_biggest_misses,
    write_player_evaluation_csv,
)
from klpga.neo_win.r2_pipeline_orchestrator import build_win_interim_rows  # noqa: E402
from klpga.neo_win.r2_pipeline_validation import (  # noqa: E402
    check_calibration_buckets_sum_to_evaluated,
    check_cut_probability_in_0_100_range,
    check_eligibility_population_is_mechanical,
    check_frozen_r1_values_unchanged,
    check_made_plus_missed_equals_n_evaluated,
    check_missed_cut_count_plausible_after_completed_cut,
    check_no_null_cut_probability_among_evaluated,
    check_no_wd_dq_unresolved_enters_scoring,
    check_player_codes_unique,
    check_unavailable_players_explicitly_handled,
    check_wd_dq_explicitly_handled,
    run_all_validations,
)
from klpga.neo_win.round_reconciliation import normalize_official_round  # noqa: E402
from klpga.neo_win.win_interim_check import win_interim_summary  # noqa: E402
from klpga.parsers.group_page_parser import parse_round_grouping  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUTS_CSV = ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "r1_cut_ground_truth_evaluation"
DEFAULT_CACHE_DIR = ROOT / "cache" / "http"
ROUND_NUMBER_FOR_CHECK_B = 3


def _load_explicit_status_overrides(path: str) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    overrides: dict[str, str] = {}
    for row in data:
        overrides[row["player_code"]] = row["status"]
    return overrides


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
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--outputs-csv-path", default=str(DEFAULT_OUTPUTS_CSV))
    parser.add_argument(
        "--explicit-status-json", default=None,
        help="Path to a JSON list of {\"player_code\", \"status\": \"WD\"|\"DQ\"} objects -- real, "
        "human-verified evidence only (e.g. explicit WD text observed on the real official leaderboard). "
        "Never inferred by this script.",
    )
    parser.add_argument(
        "--r3-grouping-json", default=None,
        help="Path to a real, already-structured Round 3 grouping/tee-time JSON file, overriding the "
        "parsed group-page result (same override this project's diagnose_r2_r3_ground_truth.py supports).",
    )
    parser.add_argument("--skip-group-page-fetch", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))

    print("=== BETA #001 R1 MAKE-CUT EVALUATION — real, double-verified ground truth ===")
    print("Read-only: no DB opened, frozen R1 predictions never recomputed, docs/ never touched.")
    print("DO NOT PUBLISH these numbers until a human reviews the report below.")
    print()

    frozen_r1, provenance = load_frozen_r1_snapshot(
        args.game_code, history_dir=Path(args.history_dir), predictions_dir=Path(args.predictions_dir),
        outputs_csv_path=Path(args.outputs_csv_path),
    )
    if provenance["source"] == SOURCE_NONE:
        print("FATAL: no frozen R1 source available under any discovery tier. Nothing evaluated.")
        return 2
    print(f"Frozen R1 loaded: {len(frozen_r1)} players (source={provenance['source']}).")
    print()

    print("=== GROUND TRUTH CHECK A: official Round 2 leaderboard (real, live) ===")
    rounds_data = collect_all_rounds_for_game(client, args.game_code, force_refresh_rounds=frozenset({2}))
    if 2 not in rounds_data or not rounds_data[2]:
        print(f"FATAL: official Round 2 leaderboard for game_code={args.game_code!r} is empty even after a "
              "forced, cache-bypassing fetch.")
        return 3
    r1_rows, r2_rows = rounds_data.get(1, []), rounds_data[2]
    official_r2_normalized = normalize_official_round(r2_rows, round_number=2)
    print(f"Round 1 rows: {len(r1_rows)}  Round 2 rows: {len(r2_rows)}")
    print()

    print("=== GROUND TRUTH CHECK B: official Round 3 grouping/tee-time page (real, live) ===")
    r3_grouping_rows: list[R3GroupingRow] = []
    if args.r3_grouping_json:
        r3_grouping_rows = _load_r3_grouping(args.r3_grouping_json)
        print(f"Loaded {len(r3_grouping_rows)} real, already-structured Round 3 rows from {args.r3_grouping_json}")
    elif not args.skip_group_page_fetch:
        try:
            status_code, group_page_html = fetch_group_page_html(client, args.game_code)
        except Exception as exc:
            print(f"FATAL: real fetch of the group page failed: {exc!r}")
            return 4
        out_html_path = (output_dir / "raw_group_page.html").resolve()
        out_html_path.parent.mkdir(parents=True, exist_ok=True)
        out_html_path.write_text(group_page_html, encoding="utf-8")
        print(f"HTTP {status_code} — {out_html_path.stat().st_size} bytes -> {out_html_path}")
        try:
            parsed = parse_round_grouping(group_page_html, round_number=ROUND_NUMBER_FOR_CHECK_B)
        except ValueError as exc:
            print(f"FATAL: could not parse Round {ROUND_NUMBER_FOR_CHECK_B} grouping: {exc}")
            return 5
        r3_grouping_rows = [
            R3GroupingRow(player_code=r.player_code, player_name=r.player_name, group=r.group,
                          tee_time=r.tee_time, starting_tee=r.starting_tee)
            for r in parsed
        ]
        print(f"Parsed {len(r3_grouping_rows)} real Round {ROUND_NUMBER_FOR_CHECK_B} grouping rows.")
    else:
        print("Skipped (--skip-group-page-fetch, no --r3-grouping-json).")
    print()

    explicit_overrides: dict[str, str] = {}
    if args.explicit_status_json:
        explicit_overrides = _load_explicit_status_overrides(args.explicit_status_json)
        print(f"=== EXPLICIT STATUS OVERRIDES (human-verified) === {len(explicit_overrides)} players: "
              f"{explicit_overrides}")
        print()

    ground_truth_rows, gt_summary = build_ground_truth_table(r1_rows, r2_rows, r3_grouping_rows)

    reconciled_rows, override_conflicts = to_player_r2_reconciled_rows(
        ground_truth_rows, official_r2_normalized, explicit_status_overrides=explicit_overrides
    )
    reconciliation_summary = summarize_ground_truth_reconciliation(frozen_r1, reconciled_rows, official_r2_normalized)

    if override_conflicts:
        print(f"=== OVERRIDE CONFLICTS ({len(override_conflicts)}) — kept UNRESOLVED, never silently resolved ===")
        for c in override_conflicts:
            print(f"  {c}")
        print()

    frozen_r1_reload, _ = load_frozen_r1_snapshot(
        args.game_code, history_dir=Path(args.history_dir), predictions_dir=Path(args.predictions_dir),
        outputs_csv_path=Path(args.outputs_csv_path),
    )

    eval_rows, excluded = build_player_cut_evaluation_rows(frozen_r1, reconciled_rows)
    cut_summary = summarize_cut_evaluation(eval_rows)
    calibration = calibration_report(eval_rows)
    top5 = top5_best_and_biggest_misses(eval_rows)

    eval_csv_path = output_dir / "player_cut_evaluation.csv"
    write_player_evaluation_csv(eval_rows, eval_csv_path)

    win_rows = build_win_interim_rows(frozen_r1, reconciled_rows)
    win_interim = win_interim_summary(win_rows)

    print("=== GROUND TRUTH RECONCILIATION SUMMARY ===")
    for k, v in reconciliation_summary.items():
        if k not in ("missing_player_diagnostics", "unmatched_player_codes"):
            print(f"  {k}: {v}")
    print()

    print("=== R1 MAKE-CUT EVALUATION (frozen R1 vs real ground truth) ===")
    for k, v in cut_summary.items():
        print(f"  {k}: {v}")
    print(f"  excluded_missing_r1_probability ({len(excluded)}): {excluded}")
    print()

    print("=== CALIBRATION (5 buckets) ===")
    for b in calibration:
        print(f"  {b}")
    print()

    print("=== AUTO-SELECTED TOP 5 BEST PREDICTIONS ===")
    for r in top5["top5_best"]:
        print(f"  {r}")
    print("=== AUTO-SELECTED TOP 5 BIGGEST MISSES ===")
    for r in top5["top5_biggest_misses"]:
        print(f"  {r}")
    print()

    print(f"=== {win_interim['label']} ===")
    for k, v in win_interim.items():
        if k != "label":
            print(f"  {k}: {v}")
    print()

    checks = [
        check_player_codes_unique(eval_rows),
        check_no_null_cut_probability_among_evaluated(eval_rows),
        check_cut_probability_in_0_100_range(eval_rows),
        check_wd_dq_explicitly_handled(reconciliation_summary),
        check_unavailable_players_explicitly_handled(excluded, reconciliation_summary),
        check_calibration_buckets_sum_to_evaluated(calibration, cut_summary["n_evaluated"]),
        check_frozen_r1_values_unchanged(frozen_r1, frozen_r1_reload),
        check_missed_cut_count_plausible_after_completed_cut(cut_summary),
        check_made_plus_missed_equals_n_evaluated(cut_summary),
        check_no_wd_dq_unresolved_enters_scoring(eval_rows),
        check_eligibility_population_is_mechanical(eval_rows, frozen_r1),
    ]
    validation = run_all_validations(checks)

    print("=== HARD VALIDATION ===")
    for c in validation["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']}: {c['detail']}")
    print()
    print(f"ALL_PASSED: {validation['all_passed']}")
    if not validation["all_passed"]:
        print(f"FAILED: {validation['failed']}")
    print()
    print(f"Player evaluation CSV: {eval_csv_path}")
    print("DO NOT PUBLISH. Nothing was written to predictions/, neo_win_predictions/, neo_win_c_predictions/, "
          "neo_tournament_history/, docs/, or the real DB.")

    return 0 if validation["all_passed"] else 6


if __name__ == "__main__":
    raise SystemExit(main())
