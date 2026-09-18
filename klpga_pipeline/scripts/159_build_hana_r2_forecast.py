"""Build 2026090002_POST_R2_FINAL_FORECAST.json for Hana (하나금융그룹
챔피언십) via klpga.neo_win.post_r2_forecast.run_post_r2_forecast --
the SAME already-existing, generic production Monte Carlo engine
KB (2026090003) uses (klpga.neo_win.round_update_r2.simulate_post_
round2 underneath). No new forecast logic, no new model.

Inputs, all real:
  - context.final_round_number=4 (registry) -> remaining_rounds =
    4 - 2 = 2, computed by run_post_r2_forecast itself, never passed
    explicitly -- matches the operator's exact "remaining_rounds=2"
    requirement with zero override code.
  - real R1 + real R2 to-par scores, from the R2 freeze built by
    scripts/158 (itself joined from real official evidence, never
    fabricated).
  - expected_round_score_to_par / spread: derived from
    2026090002_PRE_PERFORMANCE_SNAPSHOT.json (scripts/157), the same
    historical-SG-window logic already used for Hana's PRE stage.
    This function has NO current-round-SG input field at all -- Hana's
    (or KB's) live SG is never added to this baseline, matching the
    operator's explicit "SG는 historical baseline에 추가하지 않는다"
    instruction.
  - n_simulations=60000: the operator's explicit instruction, matching
    Hana's own already-established PRE-stage Monte Carlo convention
    (HANA_2026090002_PRE_M4_60000_CANDIDATE_V2.json: simulation_count=
    60000). run_post_r2_forecast's n_simulations parameter is a normal,
    fully generic argument (default DEFAULT_N_SIMULATIONS=10000 for
    KB's own production_simulation_gate contract) -- KB's contract
    module is a separate, opt-in gate only KB's own operator script
    (112) invokes; passing a different, deliberate value here for a
    different tournament with its own established convention changes
    nothing about KB's contract or any shared code.
  - Only ACTIVE (cut-survivor) records are simulated -- matches the
    operator's "cut 통과 64명만 probability validation 대상" requirement
    structurally (run_post_r2_forecast filters freeze["records"] to
    status=="ACTIVE" before building sim_inputs).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402
from klpga.neo_win.post_r2_forecast import run_post_r2_forecast, post_r2_forecast_status, STAGE_CREATED  # noqa: E402

GAME_CODE = "2026090002"
SEED = 20260918
N_SIMULATIONS = 60000


def main():
    context = load_tournament_context(GAME_CODE)
    if post_r2_forecast_status(context) == STAGE_CREATED:
        print(f"[FORECAST] {context.artifact_path('post_r2_final_forecast')} already exists (immutable) -- not rebuilding")
        return

    snapshot = json.loads(context.artifact_path("pre_performance_snapshot").read_text(encoding="utf-8"))
    payload = run_post_r2_forecast(
        context,
        pre_performance_snapshot=snapshot,
        repo_root=REPO_ROOT,
        build_id=f"hana_r2_forecast_seed{SEED}_n{N_SIMULATIONS}",
        seed=SEED,
        n_simulations=N_SIMULATIONS,
    )
    print(f"[FORECAST] remaining_rounds={payload['remaining_rounds']} n_simulations={payload['n_simulations']} seed={payload['seed']}")
    print(f"[FORECAST] official_advancing_field_size={payload['official_advancing_field_size']} simulated_field_size={payload['simulated_field_size']}")
    print(f"[FORECAST] missing_players={len(payload['missing_players'])}: {payload['missing_players']}")
    print(f"[FORECAST] win_probability_sum_pct={payload['win_probability_sum_pct']:.4f}")
    top5 = sorted(payload["records"], key=lambda r: -r["win_pct"])[:5]
    for r in top5:
        print(f"  #{r['neo_final_rank']} {r['player_name']} win={r['win_pct']:.2f}% top5={r['top5_pct']:.2f}% top10={r['top10_pct']:.2f}% top20={r['top20_pct']:.2f}%")


if __name__ == "__main__":
    main()
