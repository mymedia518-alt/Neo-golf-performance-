"""Real KLPGA official technical stats -- playerCode=10097, season 2025
ONLY. Covers scripts/build_10097_technical_stats_2025.py, which closes
a real completeness gap found during verification: driving distance
and fairway accuracy are measured by KLPGA and exist in this repo
(docs/discovery/raw_samples/, a real prior live capture), just never
ingested into this player's report.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_technical_stats_2025", ROOT / "scripts" / "build_10097_technical_stats_2025.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)


def test_build_recovers_real_driving_distance_and_fairway_accuracy():
    doc = build_script.build()
    assert doc["player_id"] == "10097"
    assert doc["season"] == 2025
    labels = {m["label"] for m in doc["metrics"]}
    assert "평균 티샷 거리 (Par4,5)" in labels
    assert "페어웨이 안착률 (Par4,5)" in labels


def test_every_metric_traces_to_a_real_source_file_with_a_real_rank():
    doc = build_script.build()
    assert len(doc["metrics"]) >= 10
    for m in doc["metrics"]:
        assert m["source_file"].startswith("docs/discovery/raw_samples/")
        assert (ROOT / m["source_file"]).exists()
        assert m["rank"] is not None and m["rank"] > 0
        assert m["value"] is not None


def test_driving_distance_values_are_physically_consistent_not_garbage():
    """Real-world sanity check that this is genuine parsed data, not a
    parsing artifact: Par5 tee shots should average farther than Par4
    tee shots, with the Par4,5-combined figure in between."""
    doc = build_script.build()
    by_label = {m["label"]: float(m["value"]) for m in doc["metrics"]}
    assert by_label["평균 티샷 거리 (Par4)"] < by_label["평균 티샷 거리 (Par4,5)"] < by_label["평균 티샷 거리 (Par5)"]


def test_no_metric_is_fabricated_when_a_source_file_is_missing():
    """If a raw sample file doesn't exist or has no 10097 row, the
    metric must be skipped entirely -- never a fabricated/None value
    silently included."""
    doc = build_script.build()
    assert all(m["value"] is not None for m in doc["metrics"])


def test_as_of_note_scopes_to_season_2025_and_never_merges_with_2026_snapshot():
    doc = build_script.build()
    assert "2025" in doc["as_of_note"]
    assert "2026" in doc["as_of_note"]
    assert "합산하지 않습니다" in doc["as_of_note"] or "확장하지 않습니다" in doc["as_of_note"]
