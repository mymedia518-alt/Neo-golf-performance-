"""Tests for scripts/215_acquire_hj_2026100004_entry_list.py --
orchestration and reconciliation logic only (the underlying fetch/
parse/sponsor building blocks each already have their own test
coverage: test_entry_list_parser.py, test_player_team_sponsor.py-style
coverage via klpga.collectors.player_team_sponsor itself). Uses a fake
client so no real network call happens."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "215_acquire_hj_2026100004_entry_list.py"
ENTRY_FIXTURE = Path(__file__).parent / "fixtures" / "entry_list_sample.html"


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_215", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_215"] = module
    spec.loader.exec_module(module)
    return module


PROFILE_FRAGMENT = """
<html><body>
<div class="player-title">{name}</div>
<div class="col-3">
    <label class="text-neongreen">소속</label>
    <h5 class="text-white">{sponsor}</h5>
</div>
</body></html>
"""


def test_reconcile_entry_classifies_new_matched_and_conflict():
    mod = _load_module()
    from klpga.parsers.entry_list_parser import EntryRow

    index = {
        "100": {"name": "홍길동", "source_file": "x_CURRENT_PLAYER_MASTER.json"},
        "200": {"name": None, "source_file": None, "conflicting_names": ["A", "B"]},
    }
    matched = mod.reconcile_entry(
        EntryRow(player_code="100", player_name="홍길동", nationality="KOR",
                  qualification_category="자격자", qualification_reason=None),
        index,
    )
    assert matched["identity_reconciliation_status"] == "MATCHED_EXISTING"

    conflict = mod.reconcile_entry(
        EntryRow(player_code="100", player_name="다른이름", nationality="KOR",
                  qualification_category="자격자", qualification_reason=None),
        index,
    )
    assert conflict["identity_reconciliation_status"] == "NAME_CONFLICT_WITH_EXISTING_SOURCE"

    new_player = mod.reconcile_entry(
        EntryRow(player_code="999", player_name="신인", nationality="USA",
                  qualification_category="초청자", qualification_reason=None),
        index,
    )
    assert new_player["identity_reconciliation_status"] == "NEW_PLAYER"

    source_conflict = mod.reconcile_entry(
        EntryRow(player_code="200", player_name="A", nationality="KOR",
                  qualification_category="자격자", qualification_reason=None),
        index,
    )
    assert source_conflict["identity_reconciliation_status"] == "NAME_CONFLICT_ACROSS_EXISTING_SOURCES"


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeClient:
    """Serves the real entry-list fixture for the entry-list GET, and a
    synthetic 소속 fragment (or a 404) for each per-player profile GET
    -- keyed by player_code so different players can exercise
    different sponsor outcomes."""

    def __init__(self, profile_by_code: dict[str, tuple[int, str, str]]):
        # profile_by_code: player_code -> (status, name_to_embed, sponsor)
        self.profile_by_code = profile_by_code
        self.calls: list[str] = []

    def get_text(self, url, params=None):
        return ENTRY_FIXTURE.read_text(encoding="utf-8")

    def get_text_with_status(self, url, params=None):
        code = params["playerCode"]
        self.calls.append(code)
        if code not in self.profile_by_code:
            raise ConnectionError(f"simulated real fetch failure for playerCode={code}")
        status, name, sponsor = self.profile_by_code[code]
        return (status, PROFILE_FRAGMENT.format(name=name, sponsor=sponsor))


def test_resolve_sponsors_uses_cache_then_falls_back_to_live_fetch(monkeypatch, tmp_path):
    mod = _load_module()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "cross_tournament_verified_sponsor_cache", lambda: {"9174": "캐시스폰서"})

    from klpga.parsers.entry_list_parser import EntryRow
    rows = [
        EntryRow(player_code="9174", player_name="강가율", nationality="KOR",
                  qualification_category="자격자", qualification_reason=None),
        EntryRow(player_code="10623", player_name="강지선", nationality="KOR",
                  qualification_category="자격자", qualification_reason=None),
    ]
    client = FakeClient({"10623": (200, "강지선", "라이브스폰서")})
    sponsors = mod.resolve_sponsors(client, rows)

    assert sponsors["9174"]["sponsor"] == "캐시스폰서"
    assert sponsors["9174"]["sponsor_source"] == "CACHED_CROSS_TOURNAMENT"
    assert "9174" not in client.calls  # never fetched live -- cache hit skipped the network call

    assert sponsors["10623"]["sponsor"] == "라이브스폰서"
    assert sponsors["10623"]["sponsor_source"] == "LIVE_FETCH"
    assert sponsors["10623"]["outcome"] == "OK"
    assert (tmp_path / "profile_10623.html").exists()


def test_resolve_sponsors_records_fetch_failure_without_blocking_others(monkeypatch, tmp_path):
    mod = _load_module()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "cross_tournament_verified_sponsor_cache", lambda: {})

    from klpga.parsers.entry_list_parser import EntryRow
    rows = [
        EntryRow(player_code="999", player_name="신인", nationality="USA",
                  qualification_category="초청자", qualification_reason=None),
        EntryRow(player_code="10623", player_name="강지선", nationality="KOR",
                  qualification_category="자격자", qualification_reason=None),
    ]
    client = FakeClient({"10623": (200, "강지선", "라이브스폰서")})  # 999 not in dict -> 404/FETCH_FAILURE
    sponsors = mod.resolve_sponsors(client, rows)

    assert sponsors["999"]["outcome"] == "FETCH_FAILURE"
    assert sponsors["999"]["sponsor"] is None
    assert sponsors["10623"]["outcome"] == "OK"


def test_main_writes_reconciliation_report_covering_every_parsed_row(monkeypatch, tmp_path):
    mod = _load_module()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "cross_tournament_verified_sponsor_cache", lambda: {})
    monkeypatch.setattr(mod, "_existing_identity_index", lambda: {})
    monkeypatch.setattr(mod, "PoliteHttpClient", lambda cache_dir: FakeClient({}))

    exit_code = mod.main()

    report = json.loads((tmp_path / "RECONCILIATION_REPORT.json").read_text(encoding="utf-8"))
    assert report["parsed_entrant_rows"] == len(report["records"])
    assert report["reconciliation_complete_100pct"] is True
    assert exit_code == 0
    assert all(r["identity_reconciliation_status"] == "NEW_PLAYER" for r in report["records"])
