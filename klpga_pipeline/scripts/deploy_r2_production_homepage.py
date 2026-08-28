"""BETA #001 R2 PRODUCTION DEPLOYMENT — Section O. Publishes the R2
FROZEN FORECAST as the real, public production homepage:
`docs/index.html` (root) and the new immutable
`docs/tournaments/2026/kg-ladies-open/r2/index.html`.

======================================================================
READS ONLY ALREADY-FROZEN, REAL FILES — NEVER RECOMPUTES A PROBABILITY
======================================================================
This script does NOT run any simulation and does NOT touch the model.
It reads two already-generated real CSVs from a prior, real Windows
run:
  --cut-eval-csv    scripts/evaluate_r1_cut_ground_truth.py's own
                     player_cut_evaluation.csv (the FINAL, frozen R1
                     CUT evaluation)
  --forecast-csv    scripts/generate_r2_frozen_forecast.py's own
                     BETA001_R2_FORECAST_<game_code>.csv (the FINAL,
                     frozen R2 forecast for the real confirmed Round 3
                     continuers)
plus the frozen R1 prediction source (klpga.neo_win.r1_frozen_snapshot,
same discovery convention every other script in this project uses) for
the player card's real PRE/R1 win% history points. Every number
written to docs/ is read verbatim from one of these real sources —
nothing here is generated, estimated, or interpolated.

======================================================================
THE R1 IMMUTABLE HISTORICAL PAGE IS NEVER WRITTEN TO
======================================================================
`docs/tournaments/2026/kg-ladies-open/r1/index.html` is opened for
READING ONLY (to compute its SHA-256 before and after this script
runs, and to prove it is byte-identical both times). This script has
no code path that opens that file for writing.

======================================================================
HARD GATE — nothing is written unless EVERY check passes
======================================================================
See klpga.neo_win.r2_production_validation for the forecast/CUT-eval
cross-checks and klpga.neo_win.r2_pipeline_validation.
check_r1_historical_html_unchanged for the R1-immutability proof. All
of them run against the fully rendered HTML BEFORE any file is
written; a single failure aborts with a non-zero exit code and writes
nothing.

Usage:
    python scripts/deploy_r2_production_homepage.py --game-code 2026080001 \\
        --tournament-name "제15회 KG 레이디스 오픈" \\
        --pre-cutoff-date 2026-08-27 \\
        --cut-eval-csv outputs/r1_cut_ground_truth_evaluation/player_cut_evaluation.csv \\
        --forecast-csv outputs/r2_frozen_forecast/2026080001/BETA001_R2_FORECAST_2026080001.csv \\
        --expected-population 62
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.cut_evaluation import (  # noqa: E402
    CUT_OUTCOME_MADE,
    PlayerCutEvaluationRow,
    calibration_report,
    summarize_cut_evaluation,
    threshold_bucket_survival,
)
from klpga.neo_win.korean_ui_labels import ROUND_COMPLETE_STATUS_LABELS  # noqa: E402
from klpga.neo_win.player_card import (  # noqa: E402
    PlayerCardData,
    ProbabilityHistoryPoint,
    build_why_text,
    render_player_card_html,
)
from klpga.neo_win.r1_frozen_snapshot import SOURCE_NONE, load_frozen_r1_snapshot  # noqa: E402
from klpga.neo_win.r2_pipeline_validation import check_r1_historical_html_unchanged, run_all_validations  # noqa: E402
from klpga.neo_win.r2_html_render import derive_score_to_par  # noqa: E402
from klpga.neo_win.r2_production_page import (  # noqa: E402
    render_calibration_section,
    render_production_hero_section,
    render_production_page,
    render_r2_forecast_section,
    render_r2_forecast_table_rows,
)
from klpga.neo_win.r2_production_validation import (  # noqa: E402
    check_forecast_population_matches_expected,
    check_ga4_present_exactly_once,
    check_monotonicity_from_source,
    check_no_excluded_status_players_in_forecast,
    check_no_fabricated_extra_rows,
    check_player_card_present_for_every_row,
    check_probabilities_render_exactly,
    check_score_to_par_matches_par_arithmetic,
    check_win_sum_from_source,
)

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT_DEFAULT = ROOT.parent
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUTS_CSV = ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"
CUT_HEADLINE_THRESHOLD_PCT = 40.0
DEFAULT_COURSE_PAR = 72  # KG 레이디스 오픈, user-confirmed; override with --course-par for a different course.


def _load_pre_snapshot(args):
    if args.pre_prediction_id is None or args.pre_prediction_id == "001-C-FINAL":
        c_path = Path(args.c_predictions_dir) / args.pre_cutoff_date[:4] / f"neo_win_c_001-C-FINAL_{args.game_code}.json"
        if c_path.exists():
            return read_neo_win_c_snapshot(c_path)
    pid = args.pre_prediction_id or "001"
    pre_path, _c = archive_paths(Path(args.predictions_dir), pid, args.game_code, args.pre_cutoff_date)
    if not pre_path.exists():
        return None
    return read_neo_win_snapshot(pre_path)


def _read_cut_eval_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_forecast_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "player_code": row["player_code"],
                    "player_name": row["player_name"],
                    "r2_rank": row["r2_rank"],
                    "r2_total_score": int(row["r2_total_score"]) if row["r2_total_score"] not in ("", None) else None,
                    "top20_pct": float(row["top20_pct"]),
                    "top10_pct": float(row["top10_pct"]),
                    "top5_pct": float(row["top5_pct"]),
                    "win_pct": float(row["win_pct"]),
                }
            )
    return rows


def _reconstruct_eval_rows(cut_eval_csv_rows: list[dict]) -> list[PlayerCutEvaluationRow]:
    """Rebuilds the real PlayerCutEvaluationRow objects from the
    already-frozen CSV. The derived fields (predicted_cut_at_50,
    actual_cut, absolute_probability_error) are recomputed by the
    dataclass's own __post_init__ — the SAME pure, deterministic
    function that produced them originally, given the same real
    r1_make_cut_pct/r2_outcome inputs read verbatim from the CSV."""
    rows = []
    for r in cut_eval_csv_rows:
        rows.append(
            PlayerCutEvaluationRow(
                player_code=r["player_code"],
                player_name=r["player_name"],
                r1_rank=int(r["r1_rank"]) if r["r1_rank"] not in ("", None) else None,
                r1_score_to_par=float(r["r1_score_to_par"]) if r["r1_score_to_par"] not in ("", None) else None,
                r1_make_cut_pct=float(r["r1_make_cut_pct"]),
                r2_outcome=r["actual_r2_status"],
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--tournament-name", default="")
    parser.add_argument("--pre-cutoff-date", required=True)
    parser.add_argument("--pre-prediction-id", default=None)
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--c-predictions-dir", default=str(DEFAULT_C_PREDICTIONS_DIR))
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--outputs-csv-path", default=str(DEFAULT_OUTPUTS_CSV))
    parser.add_argument("--cut-eval-csv", required=True)
    parser.add_argument("--forecast-csv", required=True)
    parser.add_argument("--repo-root", default=str(REPO_ROOT_DEFAULT))
    parser.add_argument("--r1-html-path", default=None, help="Defaults to <repo-root>/docs/tournaments/2026/kg-ladies-open/r1/index.html")
    parser.add_argument("--r2-html-path", default=None, help="Defaults to <repo-root>/docs/tournaments/2026/kg-ladies-open/r2/index.html")
    parser.add_argument("--root-index-path", default=None, help="Defaults to <repo-root>/docs/index.html")
    parser.add_argument("--expected-population", type=int, default=None)
    parser.add_argument(
        "--course-par", type=int, default=DEFAULT_COURSE_PAR,
        help="Per-round course par, used only to derive the R2 to-par '스코어' column/player-card field "
        "from the already-official cumulative r2_total_score (par_total = course_par * 2). "
        f"Defaults to {DEFAULT_COURSE_PAR} (KG 레이디스 오픈).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run every gate and print the report, but write nothing.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    r1_html_path = Path(args.r1_html_path) if args.r1_html_path else repo_root / "docs" / "tournaments" / "2026" / "kg-ladies-open" / "r1" / "index.html"
    r2_html_path = Path(args.r2_html_path) if args.r2_html_path else repo_root / "docs" / "tournaments" / "2026" / "kg-ladies-open" / "r2" / "index.html"
    root_index_path = Path(args.root_index_path) if args.root_index_path else repo_root / "docs" / "index.html"

    print("=== BETA #001 R2 PRODUCTION DEPLOYMENT ===")
    print("Reads only already-frozen real CSVs -- no simulation, no model logic here.")
    print()

    if not r1_html_path.exists():
        print(f"FATAL: R1 immutable historical page not found at {r1_html_path}.")
        return 2
    r1_sha_before = hashlib.sha256(r1_html_path.read_bytes()).hexdigest()
    print(f"R1 immutable page: {r1_html_path}")
    print(f"R1 SHA-256 (before): {r1_sha_before}")
    print()

    cut_eval_csv_path, forecast_csv_path = Path(args.cut_eval_csv), Path(args.forecast_csv)
    if not cut_eval_csv_path.exists():
        print(f"FATAL: real CUT evaluation CSV not found at {cut_eval_csv_path}.")
        return 3
    if not forecast_csv_path.exists():
        print(f"FATAL: real R2 forecast CSV not found at {forecast_csv_path}.")
        return 3

    cut_eval_csv_rows = _read_cut_eval_csv(cut_eval_csv_path)
    forecast_rows = _read_forecast_csv(forecast_csv_path)
    print(f"Loaded {len(cut_eval_csv_rows)} real CUT evaluation rows from {cut_eval_csv_path}")
    print(f"Loaded {len(forecast_rows)} real R2 forecast rows from {forecast_csv_path}")
    print()

    eval_rows = _reconstruct_eval_rows(cut_eval_csv_rows)
    cut_summary = summarize_cut_evaluation(eval_rows)
    calibration = calibration_report(eval_rows)
    threshold_survival = threshold_bucket_survival(eval_rows, CUT_HEADLINE_THRESHOLD_PCT)

    frozen_r1, provenance = load_frozen_r1_snapshot(
        args.game_code, history_dir=Path(args.history_dir), predictions_dir=Path(args.predictions_dir),
        outputs_csv_path=Path(args.outputs_csv_path),
    )
    frozen_r1_by_code = {f.player_code: f for f in frozen_r1} if provenance["source"] != SOURCE_NONE else {}
    pre_snapshot = _load_pre_snapshot(args)
    pre_win_pct_by_code: dict[str, float] = {}
    if pre_snapshot is not None:
        for e in pre_snapshot.predictions:
            pre_win_pct_by_code[e.player_code] = e.win_probability * 100.0

    r2_par_total = args.course_par * 2

    # === render (in memory) -- nothing is written to disk yet ===
    hero_html = render_production_hero_section(cut_summary, threshold_survival, calibration)
    calibration_html = render_calibration_section(calibration)
    table_rows_html = render_r2_forecast_table_rows(forecast_rows, clickable=True, par_total=r2_par_total)
    forecast_section_html = render_r2_forecast_section(table_rows_html, show_score_to_par=True)

    player_cards_html_parts = []
    for row in forecast_rows:
        code = row["player_code"]
        probability_history = []
        if code in pre_win_pct_by_code:
            probability_history.append(ProbabilityHistoryPoint(stage="PRE", win_pct=pre_win_pct_by_code[code]))
        f = frozen_r1_by_code.get(code)
        if f is not None and f.r1_win_probability_pct is not None:
            probability_history.append(ProbabilityHistoryPoint(stage="R1", win_pct=f.r1_win_probability_pct))
        probability_history.append(ProbabilityHistoryPoint(stage="R2", win_pct=row["win_pct"]))

        total_strokes = row["r2_total_score"]
        score_to_par = derive_score_to_par(total_strokes, r2_par_total)

        data = PlayerCardData(
            player_code=code, player_name=row["player_name"], tournament_name=args.tournament_name,
            stage_display="2라운드", win_pct=row["win_pct"], current_position=row["r2_rank"],
            current_score_to_par=score_to_par, total_strokes=total_strokes,
            cut_status=CUT_OUTCOME_MADE, cut_pct=None,
            probability_history=tuple(probability_history), round_scores=(),
            total_score_to_par=None, sample_size_rounds=None, expected_round_score=None, consistency_stddev=None,
            why_text=build_why_text("R2"), tournament_id=args.game_code, stage="R2",
        )
        player_cards_html_parts.append(render_player_card_html(data))
    player_cards_html = "".join(player_cards_html_parts)

    page_html = render_production_page(
        tournament_name=args.tournament_name, status_pill_text=ROUND_COMPLETE_STATUS_LABELS[2],
        hero_html=hero_html, calibration_html=calibration_html, forecast_section_html=forecast_section_html,
        player_cards_html=player_cards_html, include_player_card_assets=True,
    )

    # === HARD GATE -- every check runs against the in-memory render; nothing written yet ===
    checks = [
        check_forecast_population_matches_expected(forecast_rows, args.expected_population),
        check_win_sum_from_source(forecast_rows),
        check_monotonicity_from_source(forecast_rows),
        check_no_excluded_status_players_in_forecast(forecast_rows, cut_eval_csv_rows),
        check_probabilities_render_exactly(forecast_rows, page_html),
        check_no_fabricated_extra_rows(forecast_rows, page_html),
        check_ga4_present_exactly_once(page_html),
        check_player_card_present_for_every_row(forecast_rows, page_html),
        check_score_to_par_matches_par_arithmetic(forecast_rows, r2_par_total, page_html),
    ]
    validation = run_all_validations(checks)

    print("=== PRODUCTION INTEGRITY GATES ===")
    for c in validation["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']}: {c['detail']}")
    print(f"ALL_PASSED: {validation['all_passed']}")
    print()

    if not validation["all_passed"]:
        print(f"FAILED: {validation['failed']}")
        print("Aborting -- nothing was written.")
        return 4

    if args.dry_run:
        print("--dry-run: all gates passed, but nothing was written (as requested).")
        return 0

    r2_html_path.parent.mkdir(parents=True, exist_ok=True)
    r2_html_path.write_text(page_html, encoding="utf-8")
    root_index_path.parent.mkdir(parents=True, exist_ok=True)
    root_index_path.write_text(page_html, encoding="utf-8")

    r1_check = check_r1_historical_html_unchanged(r1_html_path, r1_sha_before)
    r1_sha_after = hashlib.sha256(r1_html_path.read_bytes()).hexdigest()
    print("=== R1 IMMUTABILITY (post-write) ===")
    print(f"  [{'PASS' if r1_check['passed'] else 'FAIL'}] {r1_check['check']}: {r1_check['detail']}")
    if not r1_check["passed"]:
        print("FATAL: the R1 immutable historical page changed during this run. This must never happen.")
        return 5

    print()
    print("=== RESULT ===")
    print(f"Production player count: {len(forecast_rows)}")
    print(f"WIN sum: {sum(r['win_pct'] for r in forecast_rows):.4f}")
    print(f"Course par: {args.course_par} (R2 par total: {r2_par_total})")
    print(f"R1 SHA-256 before: {r1_sha_before}")
    print(f"R1 SHA-256 after:  {r1_sha_after}")
    print(f"Root homepage: {root_index_path}")
    print(f"Immutable R2 page: {r2_html_path}")
    print()
    print("Next: git add the two written docs/ files ONLY, commit, push. See this script's own README/instructions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
