"""Tests for scripts/26_discover_klpga_record_taxonomy.py — no network
access. Same FakeClient pattern as test_inspect_entry_list.py."""
from __future__ import annotations

import csv
import importlib.util
import io
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
    assert "menu1 categories found:" in out

    json_path = tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
    csv_path = tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.csv"
    collision_path = tmp_path / "KLPGA_METRIC_COLLISION_REPORT.md"
    assert json_path.exists()
    assert csv_path.exists()
    assert collision_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["menu1_count"] == 3
    # Sg/Total is a menu2-level leaf (blank menu3) -> 1 menu2-level +
    # 3 menu3-level (Tee/010101, Approach/020104, Approach/020105).
    assert payload["menu2_level_leaf_count"] == 1
    assert payload["menu3_level_leaf_count"] == 3
    assert payload["menu3_combination_count"] == 3  # OLD-style name, same value as menu3_level_leaf_count
    assert payload["total_leaf_count"] == 4
    assert payload["source_url"] == "https://klpga.co.kr/fake-record-page"


def test_sg_only_category_no_longer_reported_incomplete(module, tmp_path, capsys):
    """The exact bug this patch fixes: a live run previously reported
    Sg (and All) as incomplete purely for lacking menu3 leaves. This
    fixture's Sg category resolves entirely via menu2-level leaves and
    must now be COMPLETE."""
    html = (FIXTURES / "record_menu_sg_menu2_leaf_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    rc = module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    assert rc == module.EXIT_COMPLETE
    out = capsys.readouterr().out
    assert "COMPLETE" in out
    assert "INCOMPLETE" not in out

    payload = json.loads((tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json").read_text(encoding="utf-8"))
    assert payload["menu2_level_leaf_count"] == 2
    assert payload["menu3_level_leaf_count"] == 0
    assert payload["incomplete_menu1_count"] == 0


def test_partial_tree_stops_and_reports_incomplete_categories(module, tmp_path, capsys):
    html = (FIXTURES / "record_menu_partial_tree_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    rc = module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    assert rc == module.EXIT_INCOMPLETE_NEEDS_INVESTIGATION
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out
    assert "menu1='Putting'" in out
    # "Sg" resolves via a menu2-level leaf now — must NOT be listed as
    # one of the incomplete categories.
    assert "menu1='Sg'" not in out
    # Partial results are still written — a partial finding has value
    # and must not be discarded.
    assert (tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json").exists()


def test_collision_fixture_run_writes_a_populated_collision_report(module, tmp_path):
    html = (FIXTURES / "record_menu_collision_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    collision_text = (tmp_path / "KLPGA_METRIC_COLLISION_REPORT.md").read_text(encoding="utf-8")
    assert "010102" in collision_text


# ---------------------------------------------------------------
# TEST 7 — nullable menu3 serializes correctly to JSON/CSV
# ---------------------------------------------------------------


def test_menu2_level_leaf_serializes_null_menu3_in_json(module, tmp_path):
    html = (FIXTURES / "record_menu_sg_menu2_leaf_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    payload = json.loads((tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json").read_text(encoding="utf-8"))
    sg_total = next(leaf for leaf in payload["leaves"] if leaf["menu2"] == "Total")
    assert sg_total["menu3"] is None
    assert sg_total["menu3_label"] is None
    assert sg_total["leaf_level"] == "menu2"


def test_menu2_level_leaf_serializes_empty_menu3_field_in_csv_not_a_fabricated_value(module, tmp_path):
    html = (FIXTURES / "record_menu_sg_menu2_leaf_sample.html").read_text(encoding="utf-8")
    client = FakeClient(html)

    module.run(client, "https://klpga.co.kr/fake-record-page", tmp_path)

    csv_text = (tmp_path / "KLPGA_RECORD_TAXONOMY_DISCOVERED.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    sg_row = next(r for r in rows if r["menu2"] == "Total")
    assert sg_row["menu3"] == ""
    assert sg_row["leaf_level"] == "menu2"


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
