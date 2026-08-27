"""Roadmap #3 — evidence-only accuracy evaluation of frozen NEO
predictions (PRE/R1/R2/R3) against real, recorded FINAL results.
Read-only against neo_tournament_history/ (never writes there, never
touches a frozen prediction artifact); never fits or tunes anything.

Reports, per stage: EVALUATED (with sample size, Brier, LogLoss,
calibration, Top-3/5/10 hit rate — all via klpga.models.metrics's
already-generic primitives) or INSUFFICIENT_EVIDENCE (zero tournaments
cleared every evidence check) — never a manufactured score.

Usage:
    python scripts/43_evaluate_prediction_accuracy.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.accuracy_evaluation import (  # noqa: E402
    PREDICTION_STAGES,
    discover_game_codes,
    evaluate_all_stages,
    load_tournament_histories,
)
from klpga.neo_win.tournament_history import STAGE_FINAL, STATUS_RECORDED  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    args = parser.parse_args()

    history_dir = Path(args.history_dir)
    game_codes = discover_game_codes(history_dir)
    histories = load_tournament_histories(history_dir, game_codes)

    evaluable_tournaments = sum(
        1 for h in histories.values()
        if h.get(STAGE_FINAL) is not None and h[STAGE_FINAL].status == STATUS_RECORDED
    )

    results = evaluate_all_stages(histories)

    print("=== ROADMAP #3 — ACCURACY EVALUATION ===")
    print()
    print(f"Tournaments in history: {len(game_codes)}")
    print(f"EVALUABLE TOURNAMENTS (FINAL recorded): {evaluable_tournaments}")
    print()
    for stage in PREDICTION_STAGES:
        r = results[stage]
        print(f"--- {stage} ---")
        print(f"STATUS: {r.status}")
        print(f"SAMPLE SIZE: {r.sample_size}")
        if r.status == "EVALUATED":
            s = r.summary
            print(f"BRIER (norm): {s.mean_brier_norm:.4f}")
            print(f"LOG LOSS: {s.mean_log_loss:.4f}")
            print(f"TOP-3 / TOP-5 / TOP-10 HIT RATE: {s.top3_rate*100:.1f}% / {s.top5_rate*100:.1f}% / {s.top10_rate*100:.1f}%")
            print("CALIBRATION:")
            for cb in r.calibration:
                print(f"  [{cb.lo:.2f}, {cb.hi:.2f}) rows={cb.row_count} expected={cb.expected_wins:.2f} "
                      f"actual={cb.actual_wins} tournaments={cb.contributing_tournament_count}")
        else:
            print("BRIER: N/A  LOG LOSS: N/A  CALIBRATION: N/A  TOP-N HIT RATE: N/A")
        if r.exclusions:
            print(f"MISSING/EXCLUDED ({len(r.exclusions)}):")
            for ex in r.exclusions:
                print(f"  {ex.game_code}: {ex.reason}")
        else:
            print("MISSING/EXCLUDED: none")
        print()

    leakage_flags = [
        f"{stage}/{ex.game_code}: {ex.reason}"
        for stage in PREDICTION_STAGES
        for ex in results[stage].exclusions
        if "leakage guard" in ex.reason
    ]
    print(f"LEAKAGE CHECK: {len(leakage_flags)} flagged {leakage_flags}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
