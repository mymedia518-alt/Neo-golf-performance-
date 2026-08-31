import json
from pathlib import Path

C = Path(__file__).parents[1] / "content" / "website_v2"


def audit():
    return json.loads((C / "OK_OPEN_2026_DATA_CENTER_PROFILE_AUDIT.json").read_text(encoding="utf-8"))


def test_datacenter_audit_has_one_consistent_120_player_snapshot():
    d = audit()
    assert d["entry_count"] == 120
    assert d["ranking_week"] == "2026-W35"
    assert d["official_source"] == "https://k-rankings.klpga.co.kr/kranking.jsp"
    assert len({r["player_id"] for r in d["records"]}) == 120


def test_datacenter_control_cases():
    controls = {r["player_id"]: r for r in audit()["control_cases"]}
    assert controls["11134"]["current_player_name"] == "서교림"
    assert controls["11134"]["current_team"] == "삼천리"
    assert controls["11134"]["current_k_ranking"] == 2
    assert controls["10725"]["current_player_name"] == "김민솔"
    assert controls["10725"]["current_team"] == "두산건설 We've"
    assert controls["10725"]["current_k_ranking"] == 1


def test_team_nulls_are_classified_not_guessed():
    d = audit()
    assert d["coverage"]["official_blank_team"] == 22
    assert all(r["team_state"] in {"PARSED", "OFFICIAL_BLANK", "ACCESS_FAILURE"} for r in d["records"])
    assert all(r.get("current_team") is None for r in d["records"] if r["team_state"] != "PARSED")


def test_profile_access_failure_does_not_invalidate_entry_or_publish_fake_fields():
    gate = json.loads((C / "OK_OPEN_2026_DATA_CENTER_PUBLICATION_GATE.json").read_text(encoding="utf-8"))
    assert gate["player_id"] == "7963"
    assert gate["identity"]["validation_state"] == "PASS"
    assert gate["datacenter_profile_state"] == "PROFILE_ACCESS_FAILURE"
    assert gate["gate_classification"] == "SOURCE_TEMPORARILY_UNAVAILABLE"
    assert gate["publication_decision"].startswith("SAFE_CONTINUE")
