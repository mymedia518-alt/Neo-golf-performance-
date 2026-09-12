"""ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-v1-
20260912): the permanent validation ledger for gameCode 2026090003,
recording the three distinct evidence classes so the context-defective
original POST-R2 forecast is never later mixed into a formal
model-performance claim as if its tournament horizon were correctly
specified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
LEDGER_PATH = CONTENT / "2026090003_VALIDATION_LEDGER.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    classification = json.loads((CONTENT / "2026090003_POST_R2_FORECAST_AUDIT_CLASSIFICATION.json").read_text(encoding="utf-8"))
    post_r3 = json.loads((CONTENT / "2026090003_POST_R3_FINAL_FORECAST.json").read_text(encoding="utf-8"))

    ledger = {
        "schema_version": 1,
        "artifact_type": "tournament_validation_ledger",
        "game_code": "2026090003",
        "tournament_name": "KB금융 골든라이프 챔피언십",
        "round_context_correction": {
            "corrected_final_round_number": 4,
            "public_stage_sequence": ["pre", "r1", "r2", "r3", "fr", "final"],
            "fr_meaning": "FR = Final Round = the actual fourth competitive round (never publicly labeled 'r4')",
            "final_meaning": "FINAL = the distinct post-tournament result/validation stage that follows FR",
            "evidence_summary": "Official R3 leaderboard raw capture has its own '4R' column (_orderType=round4score) with every player's data-round4score attribute present (empty, pending); official schedule (OFFICIAL_KLPGA_SCHEDULE.json / KLPGA_2026_09_SCHEDULE_SCREENSHOT_EVIDENCE.json) records a 4-day Thu-Sun span (09.10-09.13), matching the confirmed 4-round 하나금융그룹 챔피언십's identical profile, versus the confirmed-3-round OK저축은행 웃맨오픈's 3-day Fri-Sun span.",
        },
        "evidence_classes": {
            "A_ORIGINAL_POST_R2_FORECAST": {
                "description": "The original, immutable POST-R2 forecast. Never rewritten.",
                "path": "content/website_v2/2026090003_POST_R2_FINAL_FORECAST.json",
                "sha256": classification["subject_artifact_sha256"],
                "classification": classification["classification"],
                "recorded_remaining_rounds": classification["defect"]["recorded_remaining_rounds"],
                "correct_remaining_rounds_at_time_of_build": classification["defect"]["correct_remaining_rounds_at_end_of_r2"],
                "context_error_discovered": True,
                "usable_for_formal_model_performance_claims": False,
                "usable_for": "diagnostic / historical-system-state comparison ONLY -- see R2_to_R3 comparison note below",
                "audit_classification_artifact": "content/website_v2/2026090003_POST_R2_FORECAST_AUDIT_CLASSIFICATION.json",
            },
            "B_POST_R3_FORECAST": {
                "description": "The genuine POST-R3 -> FR forecast, built with the corrected tournament context.",
                "path": "content/website_v2/2026090003_POST_R3_FINAL_FORECAST.json",
                "sha256": _sha256(CONTENT / "2026090003_POST_R3_FINAL_FORECAST.json"),
                "r3_freeze_path": "content/website_v2/2026090003_R3_FROZEN_EVIDENCE.json",
                "r3_freeze_sha256": _sha256(CONTENT / "2026090003_R3_FROZEN_EVIDENCE.json"),
                "final_round_number": post_r3["final_round_number"],
                "remaining_rounds": post_r3["remaining_rounds"],
                "feature_cutoff": post_r3["feature_cutoff"],
                "n_simulations": post_r3["n_simulations"],
                "seed": post_r3["seed"],
                "code_commit": post_r3["code_commit"],
                "build_id": post_r3["build_id"],
                "future_data_excluded": post_r3["future_data_excluded"],
                "context_correctly_specified": True,
                "usable_for_formal_model_performance_claims": True,
            },
            "C_FR_FINAL_TRUTH": {
                "description": "The real FR (competitive round 4) result and post-tournament FINAL outcome. Not yet available.",
                "status": "PENDING",
                "path": None,
                "sha256": None,
                "note": "No R4/FR/FINAL official data exists anywhere in this worktree as of this ledger's build -- confirmed by repo-wide search finding zero R4/FINAL-labeled artifacts for this game_code and every player's raw-evidence data-round4score attribute being present but empty.",
            },
        },
        "comparison_policy": (
            "Any R2-vs-R3(-vs-FR) predictive comparison MUST explicitly disclose evidence class A's "
            "round-context defect and must never present class A's hit-rates as proof of the model's "
            "true-final predictive performance -- only class B (and, once available, a genuine "
            "POST-R3-vs-class-C comparison) may be used for that claim."
        ),
    }
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return ledger


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
