import json
from pathlib import Path

def test_r2_readiness_artifact_waits_before_official_data():
    path = Path(__file__).resolve().parents[1] / "content/website_v2/OK_OPEN_2026_R2_READINESS.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["decision"] == "WAIT"
    assert data["cut_inferred"] is False
    assert data["stage_sequence"] == ["PRE", "R1", "R2", "FINAL"]
    assert data["operator_action_count"] == 0
