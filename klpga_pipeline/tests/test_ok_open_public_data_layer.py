import json
from pathlib import Path

CONTENT = Path(__file__).parents[1] / "content" / "website_v2"


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def test_public_master_has_120_unique_identity_records():
    d = load("OK_OPEN_2026_CURRENT_PLAYER_MASTER.json")
    ids = [r["player_id"] for r in d["records"]]
    assert d["entry_count"] == 120
    assert len(ids) == len(set(ids)) == 120
    assert all(r.get("current_official_player_name") for r in d["records"])


def test_official_ranking_and_win_artifacts_are_traceable():
    ranking = load("OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json")
    forecast = load("OK_OPEN_2026_PRE_WIN_FORECAST.json")
    assert len(ranking["records"]) == 120
    assert ranking["official_source"].startswith("https://k-rankings.klpga.co.kr/")
    assert len(forecast["records"]) == 120
    values = [r["win_probability"] for r in forecast["records"]]
    assert all(v is not None and 0 <= v <= 1 for v in values)
    assert "top20_probability" not in forecast["records"][0]


def test_ranking_evidence_does_not_invent_neo_rank_or_top_modes():
    master = load("OK_OPEN_2026_CURRENT_PLAYER_MASTER.json")
    evidence = load("OK_OPEN_2026_NEO_PRE_RANKING_EVIDENCE.json")
    assert evidence["neo_pre_rank"] is None
    assert all(r["neo_pre_rank"] is None for r in master["records"])
    assert all(r["top20_probability"] is None and r["top10_probability"] is None and r["top5_probability"] is None for r in master["records"])


def test_kim_min_sol_current_identity_is_official_not_historical_suffix():
    master = load("OK_OPEN_2026_CURRENT_PLAYER_MASTER.json")
    row = next(r for r in master["records"] if r["player_id"] == "10725")
    assert row["current_official_player_name"] == "김민솔"
    assert row["current_player_status"] == "정회원"
    assert row["current_official_sponsor"] == "두산건설 We've"
    assert "김민솔 0606(A)" in row["historical_source_names"]

