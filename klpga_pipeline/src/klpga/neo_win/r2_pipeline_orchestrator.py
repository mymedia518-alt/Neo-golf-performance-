"""BETA #001 R1 -> R2 evaluation pipeline — Sections G & J's core,
importable orchestration logic (`scripts/run_beta001_r2_update.py` is
a thin CLI wrapper around `run_r2_evaluation_pipeline` below, adding
only the real DB/network glue: fetching the live official R2
leaderboard and running `klpga.neo_win.round_update_r2.
simulate_post_round2` against the real DB — neither of which this
module does itself, so this whole pipeline stays fully unit-testable
without a database or network access).

======================================================================
INPUTS THIS FUNCTION NEVER COLLECTS ITSELF
======================================================================
`official_r2` (Section B's real official R2 leaderboard, already
normalized via klpga.neo_win.round_reconciliation.normalize_official_
round), `official_r1` (that same normalization for Round 1 — optional,
but required for correct real-site CUT classification; see klpga.
neo_win.r1_to_r2_reconciliation's own docstring for why a player who
missed the cut has NO Round 2 row at all on the real site, so Round 1
presence/absence evidence is what classifies them), and
`r2_model_entrants` (Section G's real R2 model calculation,
already produced via klpga.neo_win.round_update_r2.
simulate_post_round2 against the real DB) are both supplied by the
caller. This keeps collection/DB/model-simulation concerns OUT of this
module entirely — it only reconciles, evaluates, freezes, renders, and
validates data it is handed, exactly the same "pure function, no I/O
of its own inputs" discipline klpga.neo_win.round_reconciliation.
reconcile_round already established.

======================================================================
OUTPUT ISOLATION — never the real production files
======================================================================
Every file this function writes lives under `output_root` (a directory
the CALLER chooses) — R1's frozen predictions.csv copy, the R2 player
evaluation CSV, the round-condition JSON, and the rendered R2 HTML.
This function NEVER writes to docs/index.html, docs/tournaments/.../r1/
index.html, or docs/tournaments/.../r2/index.html directly — Section
J's STEP9 (the real production update) is explicitly the CALLER's own,
separate, explicitly-gated action (see scripts/run_beta001_r2_update.py),
never performed automatically by this function.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from klpga.neo_win.cut_evaluation import calibration_report, summarize_cut_evaluation
from klpga.neo_win.r1_frozen_snapshot import (
    SOURCE_NONE,
    load_frozen_r1_snapshot,
    parse_published_r1_html,
    validate_rows_against_published_html,
    write_r1_predictions_csv,
)
from klpga.neo_win.r1_r2_evaluation_report import (
    build_player_cut_evaluation_rows,
    top5_best_and_biggest_misses,
    write_player_evaluation_csv,
)
from klpga.neo_win.r1_to_r2_reconciliation import reconcile_r1_to_r2
from klpga.neo_win.r2_html_render import (
    render_r1_model_scorecard_section,
    render_r2_page,
    render_r2_table_rows,
)
from klpga.neo_win.r2_pipeline_validation import (
    check_calibration_buckets_sum_to_evaluated,
    check_cut_probability_in_0_100_range,
    check_frozen_r1_values_unchanged,
    check_no_null_cut_probability_among_evaluated,
    check_player_codes_unique,
    check_r1_historical_html_unchanged,
    check_r2_path_never_overwrites_r1,
    check_unavailable_players_explicitly_handled,
    check_wd_dq_explicitly_handled,
    check_win_probability_in_0_100_range,
    check_win_sums_to_100_among_cutmakers,
    run_all_validations,
)
from klpga.neo_win.korean_ui_labels import ROUND_COMPLETE_STATUS_LABELS
from klpga.neo_win.round_condition_metadata import (
    build_r2_round_condition_metadata,
    round_condition_metadata_to_dict,
    write_round_condition_metadata_json,
)
from klpga.neo_win.win_interim_check import PlayerWinInterimRow, win_interim_summary

_R2_MODEL_CSV_FIELDNAMES: tuple[str, ...] = (
    "player_code", "player_name", "position", "score_to_par", "win_pct", "make_cut_pct",
)


def build_win_interim_rows(frozen_r1, reconciled_rows) -> list[PlayerWinInterimRow]:
    """Ranks the frozen R1 field by r1_win_probability_pct descending
    (ties broken by player_code, deterministic) to derive r1_win_rank
    — the frozen R1 snapshot has no rank-by-WIN% field of its own
    (r1_actual_rank is the R1 SCORE rank, a different thing)."""
    ranked = sorted(
        (f for f in frozen_r1 if f.r1_win_probability_pct is not None),
        key=lambda f: (-f.r1_win_probability_pct, f.player_code),
    )
    reconciled_by_code = {r.player_code: r for r in reconciled_rows}
    rows = []
    for rank, f in enumerate(ranked, start=1):
        r = reconciled_by_code.get(f.player_code)
        rows.append(
            PlayerWinInterimRow(
                player_code=f.player_code, player_name=f.player_name, r1_win_rank=rank,
                r1_win_pct=f.r1_win_probability_pct, r2_leaderboard_position=r.r2_position if r else None,
            )
        )
    return rows


def write_r2_model_csv(entrants: list[dict], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_R2_MODEL_CSV_FIELDNAMES)
        writer.writeheader()
        for e in entrants:
            writer.writerow({k: e.get(k) for k in _R2_MODEL_CSV_FIELDNAMES})
    return out_path


def run_r2_evaluation_pipeline(
    *,
    game_code: str,
    tournament_name: str,
    history_dir: Path,
    predictions_dir: Path,
    outputs_csv_path: Path,
    official_r2: dict,
    r2_model_entrants: list[dict],
    output_root: Path,
    r1_html_path: Optional[Path] = None,
    r1_html_expected_sha256: Optional[str] = None,
    official_r1: Optional[dict] = None,
) -> dict:
    """Runs STEP1-STEP8 and STEP10 (STEP9, the real production update,
    is never performed here — see module docstring). Returns
    {"status": "OK"/"VALIDATION_FAILED"/"HARD_STOP", "steps": {...}}."""
    output_root = Path(output_root)
    steps: dict = {"STEP1_OFFICIAL_R2_COLLECTION": {"n_players": len(official_r2)}}

    frozen_r1, provenance = load_frozen_r1_snapshot(
        game_code, history_dir=history_dir, predictions_dir=predictions_dir, outputs_csv_path=outputs_csv_path
    )
    steps["STEP_A_FROZEN_R1_SOURCE"] = provenance
    if provenance["source"] == SOURCE_NONE:
        return {"status": "HARD_STOP", "reason": "No frozen R1 source available under any of the 4 discovery tiers.", "steps": steps}

    r1_predictions_csv_path = output_root / "r1" / "predictions.csv"
    csv_action = write_r1_predictions_csv(frozen_r1, r1_predictions_csv_path)
    steps["STEP_A_PREDICTIONS_CSV"] = {"path": str(r1_predictions_csv_path), "action": csv_action}

    frozen_r1_reload, _reload_provenance = load_frozen_r1_snapshot(
        game_code, history_dir=history_dir, predictions_dir=predictions_dir, outputs_csv_path=outputs_csv_path
    )

    if r1_html_path is not None and Path(r1_html_path).exists():
        html_rows = parse_published_r1_html(Path(r1_html_path).read_text(encoding="utf-8"))
        steps["STEP_A_HTML_CROSS_CHECK"] = validate_rows_against_published_html(frozen_r1, html_rows)

    reconciled_rows, reconciliation_summary = reconcile_r1_to_r2(frozen_r1, official_r2, official_r1)
    steps["STEP2_RECONCILIATION"] = reconciliation_summary

    eval_rows, excluded = build_player_cut_evaluation_rows(frozen_r1, reconciled_rows)
    cut_summary = summarize_cut_evaluation(eval_rows)
    calibration = calibration_report(eval_rows)
    top5 = top5_best_and_biggest_misses(eval_rows)
    steps["STEP3_CUT_EVALUATION"] = cut_summary
    steps["STEP3_EXCLUDED_MISSING_R1_PROBABILITY"] = excluded

    win_rows = build_win_interim_rows(frozen_r1, reconciled_rows)
    win_interim = win_interim_summary(win_rows)
    steps["STEP3_WIN_INTERIM_CHECK"] = win_interim

    eval_csv_path = output_root / "r2" / "player_evaluation.csv"
    write_player_evaluation_csv(eval_rows, eval_csv_path)
    round_condition = build_r2_round_condition_metadata(game_code)
    round_condition_path = output_root / "r2" / "round_condition.json"
    write_round_condition_metadata_json(round_condition, round_condition_path)
    steps["STEP4_EVALUATION_FREEZE"] = {
        "player_evaluation_csv": str(eval_csv_path), "round_condition_json": str(round_condition_path),
    }

    r2_model_csv_path = output_root / "r2" / "BETA_R2_FULL.csv"
    write_r2_model_csv(r2_model_entrants, r2_model_csv_path)
    steps["STEP5_STEP6_R2_MODEL_CSV"] = {"path": str(r2_model_csv_path), "n_entrants": len(r2_model_entrants)}

    ranked_entrants = sorted(r2_model_entrants, key=lambda e: e.get("position") if e.get("position") is not None else 10**9)
    table_html = render_r2_table_rows(ranked_entrants)
    scorecard_html = render_r1_model_scorecard_section(
        cut_summary, calibration, top5, win_interim, round_condition_metadata_to_dict(round_condition)
    )
    page_html = render_r2_page(
        tournament_name=tournament_name, status_pill_text=ROUND_COMPLETE_STATUS_LABELS[2],
        table_rows_html=table_html, scorecard_html=scorecard_html,
    )
    r2_html_path = output_root / "r2" / "index.html"
    r2_html_path.parent.mkdir(parents=True, exist_ok=True)
    r2_html_path.write_text(page_html, encoding="utf-8")
    steps["STEP7_R2_HTML"] = str(r2_html_path)

    checks = [
        check_player_codes_unique(eval_rows),
        check_no_null_cut_probability_among_evaluated(eval_rows),
        check_cut_probability_in_0_100_range(eval_rows),
        check_win_probability_in_0_100_range(r2_model_entrants),
        check_win_sums_to_100_among_cutmakers(r2_model_entrants),
        check_wd_dq_explicitly_handled(reconciliation_summary),
        check_unavailable_players_explicitly_handled(excluded, reconciliation_summary),
        check_calibration_buckets_sum_to_evaluated(calibration, cut_summary["n_evaluated"]),
        check_frozen_r1_values_unchanged(frozen_r1, frozen_r1_reload),
    ]
    if r1_html_path is not None:
        checks.append(check_r2_path_never_overwrites_r1(r1_html_path, r2_html_path))
        if r1_html_expected_sha256 is not None:
            checks.append(check_r1_historical_html_unchanged(r1_html_path, r1_html_expected_sha256))

    validation = run_all_validations(checks)
    steps["STEP10_VALIDATION"] = validation

    return {
        "status": "OK" if validation["all_passed"] else "VALIDATION_FAILED",
        "steps": steps,
        "html_path": str(r2_html_path),
    }
