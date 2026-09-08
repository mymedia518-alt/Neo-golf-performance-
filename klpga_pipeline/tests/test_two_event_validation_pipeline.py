from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_two_event_validation_pipeline.py"
spec = importlib.util.spec_from_file_location("two_event_validation", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def manifest_for(tmp_path: Path, result_path: str = "result.json") -> dict:
    return {
        "manifest_id": "TEST",
        "policy": {
            "54_hole_forecast_stage_names": ["PRE", "R1", "R2", "POST_R2_PRE_FINAL", "FINAL_FORECAST"]
        },
        "events": [{
            "game_code": "123",
            "name": "Test Open",
            "format_holes": 54,
            "forecast": {"stage": "POST_R2_PRE_FINAL", "path": "forecast.json", "required": True, "legacy_artifact": False},
            "result": {"path": result_path, "required": True},
        }],
    }


def forecast_payload() -> dict:
    return {
        "game_code": "123",
        "future_data_excluded": True,
        "n_simulations": 100000,
        "records": [
            {"player_id": "a", "win_pct": 70, "top5_pct": 90, "top10_pct": 98, "top20_pct": 100},
            {"player_id": "b", "win_pct": 30, "top5_pct": 80, "top10_pct": 95, "top20_pct": 100},
        ],
    }


def result_payload() -> dict:
    return {"game_code": "123", "records": [{"player_id": "a", "rank": 1}, {"player_id": "b", "rank": 2}]}


def test_missing_official_result_is_wait_not_fabricated(tmp_path: Path):
    write_json(tmp_path / "forecast.json", forecast_payload())
    report = module.build_report(tmp_path, manifest_for(tmp_path))
    assert report["global_status"] == module.WAIT
    assert report["model_tuning"] == "BLOCKED"
    assert report["next_event_mode"] == "SHADOW_ONLY"


def test_explicit_future_data_failure_is_hard_stop(tmp_path: Path):
    payload = forecast_payload()
    payload["future_data_excluded"] = False
    write_json(tmp_path / "forecast.json", payload)
    write_json(tmp_path / "result.json", result_payload())
    report = module.build_report(tmp_path, manifest_for(tmp_path))
    assert report["global_status"] == module.HARD_STOP


def test_pass_requires_result_and_probability_invariants(tmp_path: Path):
    write_json(tmp_path / "forecast.json", forecast_payload())
    write_json(tmp_path / "result.json", result_payload())
    report = module.build_report(tmp_path, manifest_for(tmp_path))
    assert report["global_status"] == module.PASS
    assert report["postmortem_freeze"] == "READY"
    assert report["model_tuning"] == "ALLOWED_ONLY_AFTER_FREEZE"


def test_freeze_copies_evidence_and_refuses_second_write(tmp_path: Path):
    write_json(tmp_path / "forecast.json", forecast_payload())
    write_json(tmp_path / "result.json", result_payload())
    manifest = manifest_for(tmp_path)
    report = module.build_report(tmp_path, manifest)
    output = tmp_path / "outputs"
    freeze_dir = module.freeze_report(tmp_path, manifest, report, output)
    assert (freeze_dir / "manifest.json").is_file()
    assert (freeze_dir / "validation_report.json").is_file()
    assert (freeze_dir / "FROZEN_EVIDENCE_INDEX.json").is_file()
