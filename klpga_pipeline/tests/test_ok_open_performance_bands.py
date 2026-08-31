import json
from pathlib import Path

C = Path(__file__).parents[1] / "content" / "website_v2"


def test_approved_field_median_se_band_distribution_and_coverage():
    d = json.loads((C / "OK_OPEN_2026_PRE_PUBLIC_MASTER.json").read_text(encoding="utf-8"))
    assert d["entry_count"] == 120
    counts = {}
    for row in d["records"]:
        counts[row["neo_performance_band"]] = counts.get(row["neo_performance_band"], 0) + 1
    assert counts == {"VERY_HIGH": 9, "HIGH": 19, "TYPICAL": 48, "LOW": 23, "VERY_LOW": 10, "INSUFFICIENT_EVIDENCE": 11}


def test_bands_have_no_ordinal_neo_rank_and_keep_nulls_honest():
    d = json.loads((C / "OK_OPEN_2026_PRE_PUBLIC_MASTER.json").read_text(encoding="utf-8"))
    assert all(row.get("neo_pre_rank") is None for row in d["records"])
    assert any(row["neo_performance_band"] == "INSUFFICIENT_EVIDENCE" for row in d["records"])
    assert all("field_median" in row["band_statistics"] for row in d["records"])

