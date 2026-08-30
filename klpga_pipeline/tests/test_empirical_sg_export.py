import json
from pathlib import Path

def test_empirical_exports_have_real_warehouse_counts_and_windows():
    root = Path(__file__).resolve().parents[1]
    summary = json.loads((root / "content/website_v2/empirical_sg/export_summary.json").read_text(encoding="utf-8"))
    assert summary["event_series_rows"] == summary["cumulative_rows"] == 6609
    assert summary["round_rows"] == 23203
    assert summary["players"] == 305
    assert summary["history_depth"]["5_plus"] == 194
    assert summary["history_depth"]["multi_season"] == 180
    assert all(v == 0 for v in summary["component_missingness"].values())

def test_empirical_coverage_preserves_no_row_states():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "content/website_v2/empirical_sg/participation_sg_coverage.json").read_text(encoding="utf-8"))
    statuses = {row["status"] for row in data["coverage"]["events"]}
    assert "OFFICIAL_SG_NOT_AVAILABLE" in statuses
    assert "ROUND-SELECTION_ISSUE" in statuses
    assert "SG_AVAILABLE" in statuses
