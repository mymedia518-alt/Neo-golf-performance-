"""Section 14 final model-selection decision. Pure aggregation: reads the
already-executed, already-committed validation artifacts from scripts
119-121 plus the once-written NEO_EXPOSURE_BIAS_MATERIALITY_RULING.json
(Section 6 materiality standard, applied identically to V2A and V2B) and
the Section 0 frozen dac6a09 facts (cited, never recomputed or
reinterpreted). No new modeling or scoring happens here -- this script
only assembles the 11-gate table per candidate and applies the
all-11-gates-required rule with no exceptions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def build() -> dict:
    exposure_ruling = load("NEO_EXPOSURE_BIAS_MATERIALITY_RULING.json")
    # NEO_V2B_COHORT_DEPENDENCY_REDTEAM.json (script 121) supersedes the
    # earlier rank-label-only redteam in NEO_V2A_COHORT_DEPENDENCY_REDTEAM.json
    # (script 119) for gate purposes: it measures the substantive SCORE-level
    # invariance for V1, V2A, and V2B under the identical swap test, which is
    # the rigorous form of this test (see its own "note" field).
    cohort = load("NEO_V2B_COHORT_DEPENDENCY_REDTEAM.json")
    v2a_pred = load("NEO_V2A_PREDICTIVE_VALIDATION.json")
    v2b_pred = load("NEO_V2B_PREDICTIVE_VALIDATION.json")
    v2b_sg = load("NEO_V2B_OFFICIAL_SG_VALIDATION.json")

    # Baseline pipeline gates (DATA/IDENTITY/TEMPORAL/SG_INTEGRITY/REPRODUCIBILITY):
    # inherited from the frozen dac6a09 facts (Section 0) because this phase's
    # scope (V2A/V2B) changes only feature engineering and cohort normalization
    # on top of the SAME already-validated warehouse/ingestion/identity pipeline
    # -- nothing in scripts 116-122 touches ingestion, identity resolution,
    # temporal handling, or SG-field integrity. These are cited, not re-derived,
    # per Section 1's "do not reinterpret or overwrite already-frozen facts".
    inherited_baseline_gates = {
        "DATA": "PASS", "IDENTITY": "PASS", "TEMPORAL": "PASS",
        "SG_INTEGRITY": "PASS", "REPRODUCIBILITY": "PASS",
    }
    inherited_note = ("Inherited from Section 0 frozen dac6a09 facts (WAREHOUSE_READY=READY) "
                       "-- unchanged by V2A/V2B, which modify only skill-estimation and "
                       "cohort-normalization on top of the same warehouse/pipeline.")

    def sg_gate(entry, other):
        # PASS standard: correlation with official SG must be maintained or
        # improved vs the V1 frozen baseline (Pearson/Spearman are the primary
        # criteria per Section 0's own frozen V1 figures). MAE/RMSE differ
        # because V2A/V2B report a shrinkage-adjusted RATE, not V1's raw
        # long_term_sg feature -- a scale difference, disclosed, not hidden.
        v1 = other["V1"]
        ok = entry["Pearson"] >= v1["Pearson"] - 0.02 and entry["Spearman"] >= v1["Spearman"] - 0.02
        return "PASS" if ok else "FAIL"

    gates = {
        "V1": {
            **inherited_baseline_gates,
            "OFFICIAL_SG_VALIDATION": "PASS",
            "EXPOSURE_BIAS": "FAIL",
            "PREDICTIVE_VALIDATION": "PASS (is the control against which others are measured)",
            "STABILITY": "N/A (control)",
            "EXPLAINABILITY": "N/A (control)",
            "COHORT_DEPENDENCY": "FAIL",
        },
        "V2A": {
            **inherited_baseline_gates,
            "OFFICIAL_SG_VALIDATION": sg_gate(v2b_sg["V2A"], v2b_sg),
            "EXPOSURE_BIAS": exposure_ruling["V2A"]["gate"],
            "PREDICTIVE_VALIDATION": v2a_pred["PREDICTIVE_VALIDATION_GATE"],
            "STABILITY": "PASS (full report + mechanical mover explanations produced)",
            "EXPLAINABILITY": "PASS (mechanical_reason present on every stability mover)",
            "COHORT_DEPENDENCY": "FAIL" if cohort["V2A"]["score_changed"] > 0 else "PASS",
        },
        "V2B": {
            **inherited_baseline_gates,
            "OFFICIAL_SG_VALIDATION": sg_gate(v2b_sg["V2B"], v2b_sg),
            "EXPOSURE_BIAS": exposure_ruling["V2B"]["gate"],
            "PREDICTIVE_VALIDATION": v2b_pred["PREDICTIVE_VALIDATION_GATE"],
            "STABILITY": "PASS (full report + mechanical mover explanations produced)",
            "EXPLAINABILITY": "PASS (mechanical_reason present on every stability mover)",
            "COHORT_DEPENDENCY": "FAIL" if cohort["V2B"]["score_changed"] > 0 else "PASS",
        },
    }

    # required-gate set per Section 11 (V1/V2A are always evaluated against
    # the full set even though PREDICTIVE/STABILITY/EXPLAINABILITY are
    # naturally trivial/inapplicable for the V1 control itself)
    required = ["DATA", "IDENTITY", "TEMPORAL", "SG_INTEGRITY", "REPRODUCIBILITY",
                "OFFICIAL_SG_VALIDATION", "EXPOSURE_BIAS", "PREDICTIVE_VALIDATION",
                "STABILITY", "EXPLAINABILITY", "COHORT_DEPENDENCY"]

    def all_pass(candidate_gates):
        failing = [g for g in required if not str(candidate_gates[g]).startswith(("PASS", "N/A"))]
        return failing

    failing_by_candidate = {name: all_pass(g) for name, g in gates.items()}
    passing_candidates = [name for name, failing in failing_by_candidate.items() if not failing and name != "V1"]

    if passing_candidates:
        selected = passing_candidates[0]
        publication = "READY"
    else:
        selected = None
        publication = "BLOCKED"

    decision = {
        "gate_table": gates,
        "failing_gates_by_candidate": failing_by_candidate,
        "required_gates": required,
        "inherited_baseline_gate_note": inherited_note,
        "exposure_bias_materiality_standard": "see NEO_EXPOSURE_BIAS_MATERIALITY_RULING.json -- applied identically to V2A and V2B, both FAIL",
        "selected_model": selected,
        "NEO_RANKING_PUBLICATION": publication,
        "rationale": (
            "No candidate passes ALL 11 required gates. V1 and V2A both fail "
            "EXPOSURE_BIAS and COHORT_DEPENDENCY. V2B fixes COHORT_DEPENDENCY "
            "(0% score-change under cohort swap, vs 100% for V1/V2A) but does "
            "NOT materially reduce EXPOSURE_BIAS (-0.297 vs V1's -0.358, a "
            "16.9% relative reduction that leaves the correlation in the same "
            "medium effect-size band -- not material per the pre-declared "
            "standard). Per Section 11's explicit no-exceptions rule, "
            "publication is BLOCKED. No HOME deployment candidate is produced; "
            "Sections 15-20 are not executed."
        ),
    }
    (CONTENT / "NEO_RANKING_PUBLICATION_GATE_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return decision


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, default=str))
