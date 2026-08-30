from __future__ import annotations
import json
from pathlib import Path
from klpga.website_v2.analytics import nice_ticks
from klpga.website_v2.round_end import (breakaway_timeline, build_infographic_story,
    build_story_object, field_relative_hole_value, validate_stage_freshness,
    validate_visual_claims, validate_evidence_precedence, validate_completion_gate,
    DETECTOR_REGISTRY)
ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = json.loads((ROOT / "content/website_v2/kg_2026080001_official.json").read_text(encoding="utf-8"))

def test_nice_ticks_are_editorial_values():
    assert nice_ticks(27.26, 0, target=7) == [0, 5, 10, 15, 20, 25, 30]

def test_stage_freshness_rejects_stale_component():
    assert not validate_stage_freshness(page_stage="FINAL", component_stage="R3", probability_checkpoint="R3", evidence_stage="R3", available_checkpoints=["R3"])["valid"]
    assert validate_stage_freshness(page_stage="R3", component_stage="R3", probability_checkpoint="R3", evidence_stage="R3", available_checkpoints=["R3"])["valid"]

def test_field_relative_hole_value_is_not_sg_and_is_scoped():
    records=[{"player_id":"a","hole":3,"par":4,"strokes":3,"relative_to_par":-1},{"player_id":"b","hole":3,"par":4,"strokes":5,"relative_to_par":1}]
    row=field_relative_hole_value(records,"a",[3])[0]
    assert row["metric"] == "field_relative_hole_value" and row["player_minus_field_average"] == -1 and "SG" not in row

def test_kg_breakaway_reference_has_18_holes_and_no_causal_claim():
    names=["\ub178\uc2b9\ud76c","\ubc15\ud61c\uc900","\uc2e0\ub2e4\uc778","\uc720\uc544\ud604"]
    ids={"9113":names[0],"9788":names[1],"9135":names[2],"10821":names[3]}
    holes=[dict(row, player=ids.get(str(row.get("player_id")), row.get("player"))) for row in OFFICIAL["holes"]]
    timeline=breakaway_timeline(holes, players=names, target_player="\uc2e0\ub2e4\uc778")
    assert len(timeline) == 18 and timeline[-1]["target_margin_vs_nearest_challenger"] == 3
    assert timeline[8]["hole"] == 9 and timeline[10]["hole"] == 11

def test_story_and_visual_claim_gate_separate_data_from_interpretation():
    story=build_story_object(story_id="x", stage="FINAL", players=["\uc2e0\ub2e4\uc778"], trigger={}, verified_facts=[{"value":271}], metrics={}, source_scope="official", interpretation=["\uac80\uc99d"], visual_spec={}, deep_dive_trigger="x")
    export=build_infographic_story(story, tournament="KG", headline="\uacb0\uacfc", visual_constraints=["no invented facts"])
    assert story["data_vs_interpretation"] == "separate" and export["do_not_invent"] is True
    assert validate_visual_claims([{"type":"DECORATIVE_NON_FACTUAL","text":"golf texture","factual":False}])["valid"]
    assert not validate_visual_claims([{"type":"UNSUPPORTED","text":"unplayable lie"}])["valid"]

def test_probability_chart_visual_contract():
    html=(ROOT/"candidate/website-v2/deep-dive/index.html").read_text(encoding="utf-8")
    css=(ROOT/"candidate/website-v2/assets/neo-site.css").read_text(encoding="utf-8")
    assert "R3 \uacf5\ub3d9\uc120\ub450 4\uba85\uc758 \uc6b0\uc2b9\ud655\ub960 \ubcc0\ud654" in html
    assert "\uac19\uc740 -9 \uacf5\ub3d9\uc120\ub450\uc600\uc9c0\ub9cc" in html
    assert all(x in html for x in ["\ub178\uc2b9\ud76c 15.04%","\ubc15\ud61c\uc900 11.56%","\uc2e0\ub2e4\uc778 7.47%","\uc720\uc544\ud604 0.24%","\ub178\uc2b9\ud76c R2: 27.26%"])
    assert all(f'>{x}%<' in html for x in ["0","5","10","15","20","25","30"])
    assert "chart-end-label" in html and "overflow:visible" in css and "min-width:31rem" not in css

def test_numeric_typography_is_korean_first_and_technical_only_for_evidence():
    css=(ROOT/"candidate/website-v2/assets/neo-site.css").read_text(encoding="utf-8")
    assert "--font-num:Pretendard" in css and "--font-tech:\"Roboto Mono\"" in css
    assert "--num:\"Roboto Mono\"" not in css

def test_protected_evidence_precedence_rejects_cycle3_conflict():
    result=validate_evidence_precedence(protected_value=7.47, candidate_values=[{"source":"claude-cycle-3","value":7.40}])
    assert not result["valid"] and result["conflicts"][0]["value"] == 7.40

def test_zero_touch_completion_gates_and_detector_registry():
    assert not validate_completion_gate(official_status="PLAYOFF", playoff_resolved=False)["valid"]
    assert not validate_completion_gate(official_status="COMPLETE", hole_completion_known=False)["valid"]
    assert {"STREAK","SAME_SCORE_DIVERGENCE","PROBABILITY_SURGE","BREAKAWAY","RESPONSE","WINNER_ACCELERATION"} <= set(DETECTOR_REGISTRY)
