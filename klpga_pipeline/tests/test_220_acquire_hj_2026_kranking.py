"""Tests for scripts/220_acquire_hj_2026_kranking.py -- confirms no
sanctioned offline K-Ranking capture exists yet for 2026100004 (so the
live path is the correct one), and that the live collector (reused
unchanged from scripts/72) is wired correctly against a fake session."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "220_acquire_hj_2026_kranking.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_220", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_220"] = module
    spec.loader.exec_module(module)
    return module


def test_no_offline_kranking_capture_exists_yet_for_2026100004():
    mod = _load_module()
    script72 = mod._load_script_72()
    result = script72._resolve_offline_kranking({"10095", "10725"}, "2026100004")
    assert result is None


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, post_html: str):
        self.post_html = post_html
        self.headers = {}
        self.posted_with: dict | None = None

    def get(self, url, timeout=None):
        return FakeResponse(b"")

    def post(self, url, data=None, timeout=None):
        self.posted_with = data
        return FakeResponse(self.post_html.encode("utf-8"))


REAL_SHAPED_RANKING_HTML = """
<html><body>
<table id="example"><tbody>
<tr><td>1</td><td><a href="profile.jsp?player_code=10095">방신실</a></td></tr>
<tr><td>2</td><td><a href="profile.jsp?player_code=10725">김민솔</a></td></tr>
</tbody></table>
</body></html>
"""


def test_live_collection_finds_target_ids_and_leaves_others_unavailable():
    mod = _load_module()
    script72 = mod._load_script_72()
    session = FakeSession(REAL_SHAPED_RANKING_HTML)
    result = script72.collect_rankings_live(
        {"10095", "10725", "99999"}, rank_week_param="202640", ranking_date_label="2026-W40",
        session=session,
    )
    by_id = {r["player_id"]: r for r in result["records"]}
    assert by_id["10095"]["official_rank"] == 1
    assert by_id["10095"]["validation_state"] == "PASS"
    assert by_id["10725"]["official_rank"] == 2
    assert by_id["99999"]["validation_state"] == "UNAVAILABLE"
    assert by_id["99999"]["official_rank"] is None
    assert session.posted_with["Rank_week"] == "202640"
