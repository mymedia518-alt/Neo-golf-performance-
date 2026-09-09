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
from klpga.tournament_entry_bootstrap import (  # noqa: E402
    EntryListBootstrapBlocked,
    collect_entry_list_snapshot,
    collect_entry_list_snapshot_from_offline_html,
)

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


def test_offline_import_collects_the_same_real_entries_with_honest_provenance(tmp_path, monkeypatch):
    """The sanctioned offline-import path (for a session with no live
    klpga.co.kr access but a real, externally-captured page) must run
    the identical parser/identity-match logic as the live path, and
    must record collection_method/source_description/source_sha256 --
    never claim a live fetch happened."""
    import hashlib

    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = resolve_context(IDENTITY, REGISTRY)

    out_path = collect_entry_list_snapshot_from_offline_html(
        context, FIXTURE,
        source_description="saved via browser view-source, operator-provided",
        captured_at="2026-09-08T00:00:00Z",
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["game_code"] == "TEST0001"
    assert payload["player_count"] > 0
    assert payload["player_count"] == len(payload["entries"])
    assert payload["collection_method"] == "offline_import"
    assert payload["retrieved_at"] == "2026-09-08T00:00:00Z"
    assert payload["source_description"] == "saved via browser view-source, operator-provided"
    assert payload["source_sha256"] == hashlib.sha256(FIXTURE.encode("utf-8")).hexdigest()
    assert "imported_at" in payload


def test_offline_import_fails_closed_on_a_table_less_db_file_instead_of_crashing(tmp_path, monkeypatch):
    """A DB *file* existing (e.g. left behind by an earlier not-yet-
    provisioned sqlite3.connect(), exactly how data/klpga.sqlite can
    end up as a real but table-less file in a fresh checkout) must
    never surface as a raw sqlite3.OperationalError -- identity match
    must fail closed to "not attempted", matching every other
    table-less-DB guard in this codebase."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = resolve_context(IDENTITY, REGISTRY)

    empty_db = tmp_path / "empty.sqlite"
    empty_db.touch()

    out_path = collect_entry_list_snapshot_from_offline_html(
        context, FIXTURE,
        source_description="saved via browser view-source", captured_at="2026-09-08T00:00:00Z",
        db_path=empty_db,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["identity_matched"] == "not attempted (no player_master DB in this run)"
    assert all(e["identity_match"] is None for e in payload["entries"])


def test_offline_import_still_refuses_an_empty_or_unusable_page(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = resolve_context(IDENTITY, REGISTRY)

    import pytest
    with pytest.raises(EntryListBootstrapBlocked):
        collect_entry_list_snapshot_from_offline_html(
            context, "<html><body>not published</body></html>",
            source_description="saved via browser view-source", captured_at="2026-09-08T00:00:00Z",
        )
    assert not context.artifact_path("entry_snapshot").exists()
