from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026090003"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def paths():
    return (
        EVIDENCE / "KLPGA_KRANKING_2026_W36_PERIOD_EVIDENCE_RAW.html",
        EVIDENCE / "KLPGA_KRANKING_2026_W36_RAW.html",
    )


def test_week36_combines_literal_period_with_complete_ordered_table():
    mod = load_script("87_collect_kranking_top120.py")
    period, complete = paths()
    result = mod.combine_official_evidence(period, complete, "2026-09-09T00:00:00Z")
    assert result["ranking_week"] == "2026-W36"
    assert result["full_population_count"] == 756
    assert len(result["records"]) == 120
    assert [row["official_k_rank"] for row in result["records"]] == list(range(1, 121))
    assert result["source_sha256"] == {
        "period": "20a6b0b3cb10c8deaa8cbc3bd1dce9638b10aa6dea74447bd14562d095243224",
        "full_table": "d0b6c22287744c6bbabd2b8f172521c83085aa5ec63385a392b4fafccaa5b8c7",
    }
    assert result["crosscheck"]["overlap_count"] == 10
    assert result["crosscheck"]["mismatched"] == 0


@pytest.mark.parametrize("field", ["player_id", "player_name", "rating", "total_points", "event_count"])
def test_week36_top10_mismatch_fails_closed(field):
    mod = load_script("87_collect_kranking_top120.py")
    period, complete = paths()
    week, period_rows = mod.extract_period_top10(period.read_text(encoding="utf-8"))
    assert week == "2026-W36"
    full_rows = mod.extract_full_table(complete.read_text(encoding="utf-8"))
    changed = [dict(row) for row in period_rows]
    changed[0][field] = 999 if field == "event_count" else "MISMATCH"
    with pytest.raises(ValueError, match="TOP10 evidence mismatch"):
        mod._top10_crosscheck(changed, full_rows)


def test_tournament_ranking_resolver_uses_combined_evidence_only():
    mod = load_script("72_collect_ok_open_public_master.py")
    result = mod._resolve_offline_kranking({"10725", "11134", "10146"}, "2026090003")
    assert result["collection_method"] == "offline_combined_official_evidence"
    assert result["returned_rank_week"] == "2026-W36"
    assert result["evidence_crosscheck"]["mismatched"] == 0
    assert set(result["raw_response_sha256"]) == {"period", "full_table"}


def test_period_capture_alone_is_not_the_combined_publication_contract():
    mod = load_script("72_collect_ok_open_public_master.py")
    period, _ = paths()
    single = mod.collect_rankings_offline({"10725"}, period, game_code="2026090003")
    assert single["collection_method"] == "offline_import"
    combined = mod._resolve_offline_kranking({"10725"}, "2026090003")
    assert combined["collection_method"] == "offline_combined_official_evidence"
