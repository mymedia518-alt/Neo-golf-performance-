from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.pre_v2 import (
    combine_probabilities,
    fit_cut_model,
    predict_cut,
    simulate_finish_tiers,
)


def _training_rows():
    rows = []
    for index in range(40):
        rows.append(
            {
                "player_code": str(index),
                "prior_avg_round_score_to_par": -2.0 if index < 20 else 2.0,
                "prior_avg_round_score_to_par_n": 10,
                "prior_recent_form_10": -1.0 if index < 20 else 1.0,
                "prior_recent_form_10_n": 10,
                "label_made_cut": index < 20,
                # Deliberately contradictory: this column must have no effect.
                "rounds_played": 3 if index < 20 else 4,
            }
        )
    return rows


def test_cut_model_uses_explicit_made_cut_not_rounds_played():
    rows = _training_rows()
    model_a = fit_cut_model(rows)
    changed = [{**row, "rounds_played": 99 - row["rounds_played"]} for row in rows]
    model_b = fit_cut_model(changed)
    assert model_a.coefficients == model_b.coefficients
    predictions = predict_cut(model_a, rows)
    assert predictions["0"] > predictions["39"]


def test_cut_model_fails_without_explicit_truth():
    with pytest.raises(ValueError, match="explicit label_made_cut"):
        fit_cut_model([{key: value for key, value in _training_rows()[0].items() if key != "label_made_cut"}])


def test_finish_tiers_are_deterministic_and_nested():
    weights = {str(index): index + 1.0 for index in range(30)}
    a = simulate_finish_tiers(weights, n_simulations=5000, seed=42)
    b = simulate_finish_tiers(weights, n_simulations=5000, seed=42)
    assert a == b
    for row in a.values():
        assert 0 <= row["top5_probability"] <= row["top10_probability"] <= row["top20_probability"] <= 1


def test_combine_rejects_population_mismatch():
    with pytest.raises(ValueError, match="populations"):
        combine_probabilities({"1": .5}, {"1": 1.0}, {})


def test_real_kb_freeze_has_exact_pre_population_and_no_r1_leakage():
    frozen = json.loads((ROOT / "content/website_v2/2026090003_PRE_5PROB_V2_FROZEN.json").read_text(encoding="utf-8"))
    assert frozen["gameCode"] == "2026090003"
    assert frozen["stage"] == "PRE"
    assert frozen["official_field_count"] == len(frozen["predictions"]) == 120
    assert len({row["playerCode"] for row in frozen["predictions"]}) == 120
    assert {"11374", "9788"} <= {row["playerCode"] for row in frozen["predictions"]}
    assert frozen["temporal_validation"]["target_player_event_rows"] == 0
    assert frozen["temporal_validation"]["target_player_round_rows"] == 0
    assert frozen["temporal_validation"]["later_wd_status_used"] is False
    for row in frozen["predictions"]:
        chain = [row["win_probability"], row["top5_probability"], row["top10_probability"], row["top20_probability"]]
        assert 0 <= row["cut_probability"] <= 1
        assert 0 <= chain[0] <= chain[1] <= chain[2] <= chain[3] <= 1


def test_real_walk_forward_gate_passes_all_frozen_thresholds():
    report = json.loads((ROOT / "content/website_v2/NEO_PRE_5PROB_V2_WALK_FORWARD.json").read_text(encoding="utf-8"))
    assert report["cut_truth"] == "player_event.made_cut only"
    assert report["overall_frozen_win_gate_pass"] is True
    assert {report["thresholds"][str(value)]["n"] for value in (5, 8, 10)} == {97, 94, 92}
    for value in (5, 8, 10):
        assert report["thresholds"][str(value)]["WIN"]["primary_gate_pass"] is True


def test_real_kb_renderer_has_five_probabilities_and_sponsor_slot_per_player():
    script = ROOT / "scripts/84_build_ok_open_pre_website_candidate.py"
    spec = importlib.util.spec_from_file_location("builder84_pre_v2", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = module.build("2026090003")
    html = (out / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")
    assert html.count("class='player-name'") == 120
    assert html.count("class='player-sponsor'") == 120
    for label in ("TOP20", "TOP10", "TOP5"):
        assert html.count(label) >= 120
    assert html.count("class='win'") == 600
    assert "999999" not in html
    assert "BLOCKED" not in html and "VALIDATING" not in html
