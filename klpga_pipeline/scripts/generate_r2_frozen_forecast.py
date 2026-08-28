"""BETA #001 R2 FROZEN FORECAST — Section N. Freezes the tournament
state at the END OF ROUND 2 (before Round 3 starts) and computes
TOP20/TOP10/TOP5/WIN probabilities for every real, double-verified
Round 3 continuer, using ONLY the already-validated BETA #001
remaining-round Monte Carlo simulation
(klpga.neo_win.round_update_r2.simulate_post_round2) — no new model
weights, no shrinkage change, no tuning after seeing the R2
leaderboard. Round 3 has not started: only real, fixed Round 1/Round 2
scores are inputs; Round 3 and Round 4 are simulated as future,
unobserved rounds, exactly as this same function already does for
BETA #001's real post-R2 pipeline.

Read-only against everything real: no DB is opened, no write ever
touches predictions/, neo_win_predictions/, neo_win_c_predictions/,
neo_tournament_history/, docs/, or the historical R1 HTML. The R1 CUT
evaluation (klpga.neo_win.cut_evaluation / klpga.neo_win.
ground_truth_cut_evaluation) is RE-DERIVED here only to render the
public "NEO 첫 실전 검증" headline on the new page — the same real
inputs through the same, unmodified functions produce the same real
numbers; nothing about that evaluation is changed or re-tuned.

CRITICAL DATA GATES (all real, all checked, never assumed):
  - GROUND TRUTH CHECK A/B (same real collectors as
    scripts/diagnose_r2_r3_ground_truth.py / scripts/
    evaluate_r1_cut_ground_truth.py) — a fetch or parse failure aborts
    loudly, never silently falls back to "not collected".
  - The simulation population is restricted to EXACTLY the players
    whose `final_ground_truth_status == MADE_CUT_CONFIRMED` (real
    Round 3 grouping presence) — WD_AFTER_R1_START, DQ, missed-cut,
    pre-R1-unavailable, and unresolved players never enter
    `simulate_post_round2`'s input at all.
    `check_forecast_population_matches_confirmed_continuers` proves
    this mechanically after simulation.
  - `check_probability_monotonicity` proves WIN <= TOP5 <= TOP10 <=
    TOP20 for every player; `check_win_sum_approximately_100` proves
    the WIN% pool sums to ~100%. Both are mathematically guaranteed by
    simulate_post_round2's own mechanics (nested rank thresholds per
    trial), checked here as an explicit, never-assumed gate.

Usage:
    python scripts/generate_r2_frozen_forecast.py --game-code 2026080001 \\
        --pre-cutoff-date 2026-08-27 --tournament-name "제15회 KG 레이디스 오픈" \\
        --explicit-status-json explicit-status.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.group_page import fetch_group_page_html  # noqa: E402
from klpga.collectors.leaderboard import collect_all_rounds_for_game  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.neo_win.archive import archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.cut_evaluation import (  # noqa: E402
    CUT_OUTCOME_MADE,
    calibration_report,
    summarize_cut_evaluation,
    threshold_bucket_survival,
)
from klpga.neo_win.ground_truth_cut_evaluation import to_player_r2_reconciled_rows  # noqa: E402
from klpga.neo_win.ground_truth_diagnostic import R3GroupingRow, STATUS_MADE_CUT, build_ground_truth_table  # noqa: E402
from klpga.neo_win.korean_ui_labels import ROUND_COMPLETE_STATUS_LABELS  # noqa: E402
from klpga.neo_win.player_card import (  # noqa: E402
    PlayerCardData,
    ProbabilityHistoryPoint,
    RoundScoreRow,
    build_why_text,
    render_player_card_html,
)
from klpga.neo_win.r1_frozen_snapshot import SOURCE_NONE, load_frozen_r1_snapshot  # noqa: E402
from klpga.neo_win.r1_r2_evaluation_report import build_player_cut_evaluation_rows  # noqa: E402
from klpga.neo_win.r2_forecast import (  # noqa: E402
    build_r2_forecast_rows,
    check_forecast_population_matches_confirmed_continuers,
    check_probability_monotonicity,
    check_win_sum_approximately_100,
    write_r2_forecast_csv,
)
from klpga.neo_win.r2_html_render import (  # noqa: E402
    render_r1_cut_headline_section,
    render_r2_forecast_page,
    render_r2_forecast_table_rows,
)
from klpga.neo_win.round_reconciliation import normalize_official_round  # noqa: E402
from klpga.neo_win.round_update_r2 import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_r2_sim_inputs_from_frozen_snapshot,
    simulate_post_round2,
)
from klpga.parsers.group_page_parser import parse_round_grouping  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUTS_CSV = ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "r2_frozen_forecast"
DEFAULT_CACHE_DIR = ROOT / "cache" / "http"
ROUND_NUMBER_FOR_CHECK_B = 3
CUT_HEADLINE_THRESHOLD_PCT = 40.0


def _load_explicit_status_overrides(path: str) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["player_code"]: row["status"] for row in data}


def _load_r3_grouping(path: str) -> list[R3GroupingRow]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        R3GroupingRow(
            player_code=row["player_code"], player_name=row.get("player_name"),
            group=row.get("group"), tee_time=row.get("tee_time"), starting_tee=row.get("starting_tee"),
        )
        for row in data
    ]


def _load_pre_snapshot(args):
    """Same discovery order scripts/run_beta001_r2_update.py's real
    mode already uses: prefer BETA #001-C's frozen FINAL snapshot,
    fall back to the plain archive path. Never re-derives a
    probability — only reads an already-frozen file."""
    if args.pre_prediction_id is None or args.pre_prediction_id == "001-C-FINAL":
        c_path = Path(args.c_predictions_dir) / args.pre_cutoff_date[:4] / f"neo_win_c_001-C-FINAL_{args.game_code}.json"
        if c_path.exists():
            return read_neo_win_c_snapshot(c_path)
    pid = args.pre_prediction_id or "001"
    pre_path, _c = archive_paths(Path(args.predictions_dir), pid, args.game_code, args.pre_cutoff_date)
    if not pre_path.exists():
        return None
    return read_neo_win_snapshot(pre_path)


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
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--explicit-status-json", default=None)
    parser.add_argument("--r3-grouping-json", default=None)
    parser.add_argument("--skip-group-page-fetch", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))

    print("=== BETA #001 R2 FROZEN FORECAST (end of Round 2, before Round 3) ===")
    print("Read-only: no DB opened, frozen R1 predictions never recomputed, docs/ and the R1 page never touched.")
    print("DO NOT PUBLISH until a human reviews the report below.")
    print()

    frozen_r1, provenance = load_frozen_r1_snapshot(
        args.game_code, history_dir=Path(args.history_dir), predictions_dir=Path(args.predictions_dir),
        outputs_csv_path=Path(args.outputs_csv_path),
    )
    if provenance["source"] == SOURCE_NONE:
        print("FATAL: no frozen R1 source available under any discovery tier.")
        return 2

    pre_snapshot = _load_pre_snapshot(args)
    if pre_snapshot is None:
        print("FATAL: no frozen PRE snapshot found (checked BETA #001-C FINAL and the plain archive path).")
        return 2
    print(f"Frozen R1 loaded: {len(frozen_r1)} players (source={provenance['source']}). "
          f"Frozen PRE snapshot loaded: {len(pre_snapshot.predictions)} players.")
    print()

    print("=== GROUND TRUTH CHECK A: official Round 2 leaderboard (real, live) ===")
    rounds_data = collect_all_rounds_for_game(client, args.game_code, force_refresh_rounds=frozenset({2}))
    if 2 not in rounds_data or not rounds_data[2]:
        print(f"FATAL: official Round 2 leaderboard for game_code={args.game_code!r} is empty even after a "
              "forced, cache-bypassing fetch.")
        return 3
    r1_rows, r2_rows = rounds_data.get(1, []), rounds_data[2]
    official_r1_normalized = normalize_official_round(r1_rows, round_number=1)
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
        out_html_path = (output_dir / args.game_code / "raw_group_page.html").resolve()
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

    ground_truth_rows, _gt_summary = build_ground_truth_table(r1_rows, r2_rows, r3_grouping_rows)
    reconciled_rows, _conflicts = to_player_r2_reconciled_rows(
        ground_truth_rows, official_r2_normalized, explicit_status_overrides=explicit_overrides
    )

    # === R1 CUT evaluation, RE-DERIVED (not modified) purely to render the real headline numbers ===
    eval_rows, _excluded = build_player_cut_evaluation_rows(frozen_r1, reconciled_rows)
    cut_summary = summarize_cut_evaluation(eval_rows)
    calibration = calibration_report(eval_rows)
    threshold_survival = threshold_bucket_survival(eval_rows, CUT_HEADLINE_THRESHOLD_PCT)

    # === Simulation population: EXACTLY the real, confirmed Round 3 continuers ===
    confirmed_continuer_codes = {g.player_code for g in ground_truth_rows if g.final_ground_truth_status == STATUS_MADE_CUT}
    print(f"=== SIMULATION POPULATION: {len(confirmed_continuer_codes)} confirmed Round 3 continuers ===")
    print()

    r1_scores = {code: p.score_to_par for code, p in official_r1_normalized.items() if p.score_to_par is not None}
    r2_scores = {code: p.score_to_par for code, p in official_r2_normalized.items() if p.score_to_par is not None}
    made_cut_by_player = {code: True for code in confirmed_continuer_codes}
    sim_inputs, missing = build_r2_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores, r2_scores, made_cut_by_player)
    missing_in_population = sorted(set(missing) & confirmed_continuer_codes)
    if missing_in_population:
        print(f"FATAL: {len(missing_in_population)} confirmed continuer(s) missing real R1/R2 score data, "
              f"cannot simulate without fabricating: {missing_in_population}")
        return 6

    sim_result = simulate_post_round2(sim_inputs, n_simulations=args.n_simulations)

    checks = [
        check_forecast_population_matches_confirmed_continuers(sim_result, confirmed_continuer_codes),
        check_probability_monotonicity(sim_result),
        check_win_sum_approximately_100(sim_result),
    ]
    print("=== HARD VALIDATION ===")
    for c in checks:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']}: {c['detail']}")
    all_passed = all(c["passed"] for c in checks)
    print(f"ALL_PASSED: {all_passed}")
    print()
    if not all_passed:
        print("Aborting — a hard gate failed. Nothing was written.")
        return 7

    forecast_rows = build_r2_forecast_rows(ground_truth_rows, sim_result, official_r2_normalized)

    csv_path = output_dir / args.game_code / f"BETA001_R2_FORECAST_{args.game_code}.csv"
    write_r2_forecast_csv(forecast_rows, csv_path)

    # === HTML preview (frozen, isolated — never docs/, never the R1 page) ===
    headline_html = render_r1_cut_headline_section(cut_summary, threshold_survival, calibration)
    table_rows_html = render_r2_forecast_table_rows(forecast_rows, clickable=True)

    frozen_r1_by_code = {f.player_code: f for f in frozen_r1}
    sim_inputs_by_code = {p.player_code: p for p in sim_inputs}
    r1_rows_by_code = {p.player_code: p for p in r1_rows if p.player_code}
    r2_rows_by_code = {p.player_code: p for p in r2_rows if p.player_code}

    player_cards_html_parts = []
    for row in forecast_rows:
        code = row["player_code"]
        f = frozen_r1_by_code.get(code)
        sim_in = sim_inputs_by_code.get(code)
        r1_raw, r2_raw = r1_rows_by_code.get(code), r2_rows_by_code.get(code)
        r1_to_par = official_r1_normalized.get(code).score_to_par if code in official_r1_normalized else None
        r2_to_par = official_r2_normalized.get(code).score_to_par if code in official_r2_normalized else None
        total_to_par = (r1_to_par + r2_to_par) if (r1_to_par is not None and r2_to_par is not None) else None

        round_scores = []
        if r1_raw is not None and r1_raw.round1_score is not None and r1_to_par is not None:
            round_scores.append(RoundScoreRow(round_number=1, round_score=r1_raw.round1_score, score_to_par=r1_to_par))
        if r2_raw is not None and r2_raw.round2_score is not None and r2_to_par is not None:
            round_scores.append(RoundScoreRow(round_number=2, round_score=r2_raw.round2_score, score_to_par=r2_to_par))

        probability_history = []
        if f is not None and f.r1_win_probability_pct is not None:
            probability_history.append(ProbabilityHistoryPoint(stage="R1", win_pct=f.r1_win_probability_pct))
        probability_history.append(ProbabilityHistoryPoint(stage="R2", win_pct=row["win_pct"]))

        data = PlayerCardData(
            player_code=code, player_name=row["player_name"], tournament_name=args.tournament_name,
            stage_display="2라운드", win_pct=row["win_pct"], current_position=row["r2_rank"],
            current_score_to_par=total_to_par, cut_status=CUT_OUTCOME_MADE, cut_pct=None,
            probability_history=tuple(probability_history), round_scores=tuple(round_scores),
            total_score_to_par=total_to_par, sample_size_rounds=len(round_scores) or None,
            expected_round_score=sim_in.expected_round_score_to_par if sim_in else None,
            consistency_stddev=sim_in.spread if sim_in else None,
            why_text=build_why_text("R2"), tournament_id=args.game_code, stage="R2",
        )
        player_cards_html_parts.append(render_player_card_html(data))

    page_html = render_r2_forecast_page(
        tournament_name=args.tournament_name, status_pill_text=ROUND_COMPLETE_STATUS_LABELS[2],
        headline_html=headline_html, table_rows_html=table_rows_html,
        player_cards_html="".join(player_cards_html_parts), include_player_card_assets=True,
    )
    html_path = output_dir / args.game_code / f"r2_forecast_{args.game_code}.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(page_html, encoding="utf-8")

    win_sum = sum(s["win_pct"] for s in sim_result.values())
    top10_by_win = sorted(forecast_rows, key=lambda r: -r["win_pct"])[:10]

    print("=== RESULT ===")
    print(f"Simulation population count: {len(sim_result)}")
    print(f"WIN probability sum: {win_sum:.4f}")
    print("Top 10 players by WIN%:")
    for r in top10_by_win:
        print(f"  {r['player_code']} {r['player_name']} — WIN {r['win_pct']:.2f}%")
    print()
    print(f"Generated CSV: {csv_path}")
    print(f"Generated HTML preview: {html_path}")
    print()
    print("Nothing was written to predictions/, neo_win_predictions/, neo_win_c_predictions/, "
          "neo_tournament_history/, docs/, or the historical R1 HTML. DO NOT PUBLISH.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
