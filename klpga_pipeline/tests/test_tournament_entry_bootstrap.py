"""NEO TOURNAMENT PIPELINE Phase 3 item 2: the generic ENTRY LIST /
IDENTITY prerequisite must produce a real entry_snapshot artifact from
the confirmed official entry-list page shape, and must refuse (never
fabricate) when the page isn't usable yet."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga import config  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_entry_bootstrap import EntryListBootstrapBlocked, collect_entry_list_snapshot  # noqa: E402

FIXTURE = (Path(__file__).parent / "fixtures" / "entry_list_sample.html").read_text(encoding="utf-8")

IDENTITY = {
    "game_code": "TEST0001", "tournament_name": "Test Open", "season": 2026,
    "start_date": "2026-01-01", "end_date": "2026-01-03",
    "final_round_number": 3, "current_round_number": 1,
}
REGISTRY = {"TEST0001": {"url_base": "/tournaments/2026/test-open/", "stage_state_filename": "X.json", "stage_order": ["pre", "r1", "r2", "r3", "final"]}}


class FakeClient:
    def __init__(self, html_by_key):
        self.html_by_key = html_by_key

    def get_text(self, url, params=None, **kwargs):
        key = (url, params.get("gameCode") if params else None)
        return self.html_by_key[key]


def test_collects_real_entries_from_the_official_page_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = resolve_context(IDENTITY, REGISTRY)
    client = FakeClient({(config.ENTRY_LIST_ENDPOINT, "TEST0001"): FIXTURE})

    out_path = collect_entry_list_snapshot(context, cache_dir=tmp_path / "cache", client=client)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["game_code"] == "TEST0001"
    assert payload["player_count"] > 0
    assert payload["player_count"] == len(payload["entries"])
    assert all(e["identity_match"] is None for e in payload["entries"])


def test_refuses_to_write_an_empty_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = resolve_context(IDENTITY, REGISTRY)
    client = FakeClient({(config.ENTRY_LIST_ENDPOINT, "TEST0001"): "<html><body>not published</body></html>"})

    import pytest
    with pytest.raises(EntryListBootstrapBlocked):
        collect_entry_list_snapshot(context, cache_dir=tmp_path / "cache", client=client)

    assert not context.artifact_path("entry_snapshot").exists()
