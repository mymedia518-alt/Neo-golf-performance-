from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
CONTENT = PIPELINE_ROOT / "content" / "website_v2"


def _load_collector():
    path = PIPELINE_ROOT / "scripts" / "collect_sg_from_leaderboard.py"
    spec = importlib.util.spec_from_file_location("collect_sg_from_leaderboard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_identity_lookup_resolves_kim_minseon7(tmp_path: Path) -> None:
    collector = _load_collector()
    lookup = collector.load_repository_id_lookup()
    assert lookup["김민선7"] == "10097"

    warehouse = tmp_path / "warehouse.json"
    warehouse.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "player": "김민선7",
                        "player_name": "김민선7",
                        "raw_player_name": "김민선7",
                        "player_id": "",
                        "identity_state": "UNRESOLVED_IDENTITY",
                        "game_code": "2026090003",
                        "scope": "tournament_cumulative",
                        "round": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = collector.merge_into_warehouse([], warehouse)
    row = json.loads(warehouse.read_text(encoding="utf-8"))["records"][0]
    assert result["identities_resolved"] == 1
    assert row["player_id"] == "10097"
    assert row["identity_state"] == "RETAINED"


def test_kb_sg_is_present_in_history_and_production_page() -> None:
    history_path = CONTENT / "knowledge_engine" / "player_intelligence" / "10097" / "PLAYER_HISTORY.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    kb = next(row for row in history["tournament_history"] if row["game_code"] == "2026090003")

    assert kb["rank"] == 16
    assert kb["sg_total"] == 2.05
    assert kb["sg_components"] == {"ott": 0.98, "app": 1.43, "arg": -0.42, "putt": 0.07}
    assert not any("2026090003" in item for item in history["not_available"])

    html = (REPO_ROOT / "docs" / "player" / "10097" / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<tr id="t-2026090003">.*?</tr>', html)
    assert match is not None
    row_html = match.group(0)
    for expected in (
        "KB금융 골든라이프 챔피언십",
        "<td>16</td>",
        "<td>+2.05</td>",
        "<td>+0.98</td>",
        "<td>+1.43</td>",
        "<td>-0.42</td>",
        "<td>+0.07</td>",
    ):
        assert expected in row_html
    assert "SG 미수집" not in row_html
    assert "SG 데이터가 없는 대회(예: KB금융 골든라이프 챔피언십)" not in html
