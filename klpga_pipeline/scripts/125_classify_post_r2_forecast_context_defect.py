"""ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-v1-
20260912): classifies the already-frozen 2026090003_POST_R2_FINAL_FORECAST.json
as historical evidence carrying a discovered round-context defect --
WITHOUT touching that file in any way.

The original forecast was built when TournamentContext resolved
final_round_number=3 for gameCode 2026090003 (a mechanical undercount
-- see TOURNAMENT_SITE_REGISTRY.json's own "_final_round_number_comment"
for the official 4R-column/schedule evidence that corrected it to 4).
klpga.neo_win.post_r2_forecast.run_post_r2_forecast computed
`remaining_rounds = context.final_round_number - 2` and passed it
straight into `simulate_post_round2(..., remaining_rounds=remaining_rounds)`,
which draws exactly that many independent Normal-distributed round-score
variates per player. The frozen artifact's own `remaining_rounds: 1`
field is direct evidence it was built with only ONE round of simulated
future variance, when a genuine 4-round tournament has TWO remaining
rounds (R3 and R4) at the POST-R2 checkpoint.

This script writes ONLY a separate audit-classification artifact. It
never rewrites, regenerates, or replaces the original forecast -- the
original stays byte-identical forever, exactly as required by Section 3
of the fix task ("PRESERVE THE ORIGINAL POST-R2 FORECAST").
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

ORIGINAL_PATH = CONTENT / "2026090003_POST_R2_FINAL_FORECAST.json"
CLASSIFICATION_PATH = CONTENT / "2026090003_POST_R2_FORECAST_AUDIT_CLASSIFICATION.json"

EXPECTED_SHA256 = "ad65227f59c19562005b3140c5bbdcf9713d90ae61f2df00e46d9ab9e97c8367"


def build() -> dict:
    raw = ORIGINAL_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != EXPECTED_SHA256:
        raise SystemExit(
            f"REFUSING TO CLASSIFY: {ORIGINAL_PATH} sha256={actual_sha256} does not match "
            f"expected {EXPECTED_SHA256} -- the original forecast may have been altered"
        )
    forecast = json.loads(raw.decode("utf-8"))

    classification = {
        "schema_version": 1,
        "artifact_type": "post_r2_forecast_audit_classification",
        "subject_artifact_path": "content/website_v2/2026090003_POST_R2_FINAL_FORECAST.json",
        "subject_artifact_sha256": actual_sha256,
        "subject_artifact_immutable": True,
        "subject_artifact_modified_by_this_script": False,
        "classification": "HISTORICAL_FORECAST_WITH_ROUND_CONTEXT_ERROR",
        "defect": {
            "recorded_remaining_rounds": forecast.get("remaining_rounds"),
            "correct_remaining_rounds_at_end_of_r2": 2,
            "recorded_final_round_number_at_build_time": forecast.get("final_round_number"),
            "correct_final_round_number": 4,
            "root_cause": (
                "TournamentContext.final_round_number for gameCode 2026090003 was "
                "mechanically derived by counting 'rN' stages already present in "
                "TOURNAMENT_SITE_REGISTRY.json's stage_order (pre,r1,r2,r3,final = 3), "
                "which reflects how many round pages had been built so far, not the "
                "tournament's true round count. Official evidence (the R3 leaderboard's "
                "own 4R column / round4score attributes, plus the official 4-day "
                "Thu-Sun schedule) proves this is a genuine 4-round event. "
                "post_r2_forecast.py computed remaining_rounds = final_round_number - 2 "
                "= 1 and passed it directly into simulate_post_round2(remaining_rounds=1), "
                "which drew only ONE round's worth of Monte Carlo variance per player "
                "instead of the correct TWO (R3 and R4)."
            ),
            "practical_effect": (
                "The frozen forecast's WIN/TOP5/TOP10/TOP20 percentages were calibrated "
                "to predict 'leader after R3', not the true tournament winner after R4/FR. "
                "Its filename and public label ('POST_R2_FINAL_FORECAST') implies a "
                "true-final forecast; this classification exists precisely because that "
                "implication is not correct for the underlying computation performed."
            ),
        },
        "handling_rule": (
            "Do not rewrite this artifact's metadata or regenerate its predictions. It "
            "is preserved exactly as originally computed, as real historical evidence of "
            "system state at build time. It must never be presented as, or substituted "
            "for, a correctly-specified true-final forecast, and must never be mixed into "
            "formal model-performance claims as if its tournament horizon were correctly "
            "specified -- see 2026090003_VALIDATION_LEDGER.json's evidence-class A entry."
        ),
        "corrective_action_taken": (
            "TOURNAMENT_SITE_REGISTRY.json's 2026090003 entry now carries an explicit, "
            "evidence-backed final_round_number=4 field; a genuine POST-R3 forecast "
            "(content/website_v2/2026090003_POST_R3_FINAL_FORECAST.json) has been built "
            "with the corrected remaining_rounds=1 at the END_OF_R3 checkpoint. This is a "
            "forward-only correction -- the original POST-R2 artifact is never replaced."
        ),
    }
    CLASSIFICATION_PATH.write_text(
        json.dumps(classification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return classification


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
