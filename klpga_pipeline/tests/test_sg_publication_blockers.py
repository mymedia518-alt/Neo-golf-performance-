import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "content" / "website_v2"


def test_band_baseline_population_matches_eligible_population_and_uses_full_precision():
    d = json.loads((C / "OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_CORRECTED_V2.json").read_text(encoding="utf-8"))
    eligible = [p["windows"]["recent5"]["components"]["total"]["mean"] for p in d["profiles"] if p["windows"]["recent5"]["components"]["total"]["sample"] >= 5]
    assert len(eligible) == 117
    assert d["field_median"] == statistics.median(eligible)
    assert d["field_median"] == -0.46599999999999997


def test_boundary_controls_are_not_special_cased():
    d = json.loads((C / "OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_CORRECTED_V2.json").read_text(encoding="utf-8"))
    by = {p["player_id"]: p for p in d["profiles"]}
    assert by["9652"]["neo_performance_band"] == "HIGH"
    assert by["10178"]["neo_performance_band"] == "LOW"
    assert by["9652"]["band_statistics"]["z_vs_field_median"] < 1.96
    assert by["10178"]["band_statistics"]["z_vs_field_median"] > -1.96


def test_corrected_rank_provenance_cannot_point_at_legacy_warehouse():
    d = json.loads((C / "OK_OPEN_2026_PRE_SG_TOTAL_RANK_CORRECTED_V2.json").read_text(encoding="utf-8"))
    assert d["warehouse"] == "historical_sg_warehouse_corrected_v2.json"
    assert d["warehouse_sha256"] == "56da79abe8e97b82623fcb6b6368f3c864b51d1031fe421c2d69d98576653a62"
    assert all(r["sg_total_rank"] is None or r["sample_count"] >= 1 for r in d["records"])
