"""Tests for scripts/26_discover_klpga_record_taxonomy.py — no network
access. Same FakeClient pattern as test_inspect_entry_list.py."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "26_discover_klpga_record_taxonomy.py"
FIXTURES = Path(__file__).parent / "fixtures"


def _load_module():
    spec = importlib.util.spec_from_file_location("discover_klpga_record_taxonomy_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


class FakeClient:
    def __init__(self, html: str):
        self.html = html

    def get_text(self, url, params=None, **kwargs):
        return self.html


def test_complete_static_tree_writes_all_three_artifacts_and_returns_zero(module, tmp_path, capsys):
    html = (FIXTURES / "record_menu_static_tree_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    rc = module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    assert rc == module.EXIT_COMPLETE
    out = capsys.readouterr().out
    assert "COMPLETE" in out
    assert "menu1 categories found:            3" in out

    json_path = tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
    csv_path = tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.csv"
    collision_path = tmp_path / "KLPGA_METRIC_COLLISION_REPORT.md"
    assert json_path.exists()
    assert csv_path.exists()
    assert collision_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["menu1_count"] == 3
    assert payload["menu3_combination_count"] == 4
    assert payload["source_url"] == "https://klpga.co.kr/fake-record-page"


def test_partial_tree_stops_and_reports_incomplete_categories(module, tmp_path, capsys):
    html = (FIXTURES / "record_menu_partial_tree_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    rc = module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    assert rc == module.EXIT_INCOMPLETE_NEEDS_INVESTIGATION
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out
    assert "menu1='Putting'" in out
    # Partial results are still written — a partial finding has value
    # and must not be discarded.
    assert (tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json").exists()


def test_collision_fixture_run_writes_a_populated_collision_report(module, tmp_path):
    html = (FIXTURES / "record_menu_collision_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    collision_text = (tmp_path / "KLPGA_METRIC_COLLISION_REPORT.md").read_text(encoding="utf-8")
    assert "010102" in collision_text


def test_blocked_response_does_not_write_any_artifact(module, tmp_path, capsys):
    from klpga.http_client import RateLimitBlockedError

    class BlockedClient:
        def get_text(self, url, params=None, **kwargs):
            raise RateLimitBlockedError("403 from fake url — site-side access restriction, not retrying")

    rc = module.run(BlockedClient(), "https://klpga.co.kr/fake-record-page", tmp_path)

    assert rc == module.EXIT_FETCH_FAILED
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert list(tmp_path.glob("*")) == []
