"""Tests for src/klpga/discovery/season_metric_collector.py — fully
offline. `--live`-equivalent acquisition is exercised against a fake
in-process client double, exactly like tests/test_bounded_missing_
evidence_request_plan_script.py."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from klpga.db.init_db import SCHEMA_PATH
from klpga.discovery.season_metric_collector import (
    STATUS_MATCH_CONFIRMED,
    STATUS_MATCH_NO_DATA,
    STATUS_MATCH_NONE,
    STATUS_MATCH_PARTIAL,
    _extract_confirmed_unit,
    acquire_season_metrics,
    build_official_metric_value_rows,
    build_season_metric_request_plan,
    extract_player_codes_from_raw_samples,
    ingest_official_metric_value_rows,
    verify_player_code_identity_space,
)
from klpga.http_client import RateLimitBlockedError

REAL_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


def _leaf(menu1, menu2, menu3, leaf_level, label):
    return {
        "menu1": menu1,
        "menu1_label": menu1,
        "menu2": menu2,
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": menu3,
        "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else ""),
    }


def _table_response_html(column_labels: list[str], menu_name: str = "") -> str:
    ths = "".join(f"<th>{label}</th>" for label in column_labels)
    record_attrs = " ".join(
        f'data-record{"" if i == 0 else i}="{i + 1}"' for i in range(len(column_labels) - 2)
    )
    tds = "".join(f"<td>{i}</td>" for i in range(len(column_labels)))
    menu_script = f'<script>var menuName = "{menu_name}";</script>' if menu_name else ""
    return f"""
    {menu_script}
    <table><thead><tr>{ths}</tr></thead>
      <tbody><tr data-rank="1" data-name="테스트" {record_attrs}>{tds}</tr></tbody>
    </table>
    """


class _FakeClient:
    def __init__(self, *, html_by_identity=None, raise_by_identity=None):
        self.html_by_identity = html_by_identity or {}
        self.raise_by_identity = raise_by_identity or {}
        self.calls: list[str] = []

    @staticmethod
    def _identity_key_from_form(data: dict) -> str:
        menu1, menu2, menu3 = data.get("menu1"), data.get("menu2"), data.get("menu3")
        return f"{menu1}::{menu2}::{menu3}" if menu3 else f"{menu1}::{menu2}"

    def post_text(self, url, data=None, use_cache=True, headers=None):
        key = self._identity_key_from_form(data or {})
        self.calls.append(key)
        if key in self.raise_by_identity:
            raise self.raise_by_identity[key]
        return self.html_by_identity.get(key, "<html><body><table><thead><tr></tr></thead><tbody></tbody></table></body></html>")


# ---------------------------------------------------------------
# build_season_metric_request_plan — the FULL canonical set, not just
# the collision audit's insufficient-evidence subset.
# ---------------------------------------------------------------


def test_plan_covers_every_canonical_identity_when_none_evidenced(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Putt", "Putt01", "040101", "menu3", "평균 퍼트수"),
        ]
    }
    rows = build_season_metric_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert {r["identity_key"] for r in rows} == {"Tee::Tee01::010101", "Putt::Putt01::040101"}


def test_plan_excludes_identities_already_evidenced(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Putt", "Putt01", "040101", "menu3", "평균 퍼트수"),
        ]
    }
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text("<html></html>", encoding="utf-8")
    rows = build_season_metric_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert {r["identity_key"] for r in rows} == {"Putt::Putt01::040101"}


def test_plan_covers_colliding_identity_once_not_per_label(tmp_path):
    """A collision-audit-resolved identity (2 labels, 1 request) still
    only produces ONE plan row — this function is not scoped to
    collisions at all, but the underlying request count is the same
    either way."""
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt02", "040201", "menu3", "라운드당 퍼트수"),
            _leaf("Putt", "Putt02", "040201", "menu3", "평균 퍼트수"),
        ]
    }
    rows = build_season_metric_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert len(rows) == 1
    assert rows[0]["identity_key"] == "Putt::Putt02::040201"


# ---------------------------------------------------------------
# acquire_season_metrics
# ---------------------------------------------------------------


def test_acquire_fires_only_for_the_full_missing_set(tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    client = _FakeClient(html_by_identity={"Tee::Tee01::010101": _table_response_html(["순위", "선수명", "평균 티샷 거리(yds)"])})
    result = acquire_season_metrics(client, taxonomy, "2025", tmp_path, log=lambda m: None)
    assert result["season"] == "2025"
    assert result["expected_identities"] == 1
    assert client.calls == ["Tee::Tee01::010101"]
    assert result["items"][0]["http_outcome"] == "HTTP_SUCCESS"


def test_acquire_hard_stops_on_rate_limit(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Around", "Around09", "030901", "menu3", "라벨A"),
            _leaf("Putt", "Putt09", "040901", "menu3", "라벨B"),
        ]
    }
    client = _FakeClient(raise_by_identity={"Around::Around09::030901": RateLimitBlockedError("429")})
    result = acquire_season_metrics(client, taxonomy, "2025", tmp_path, log=lambda m: None)
    assert result["hard_stop"] is not None
    assert client.calls == ["Around::Around09::030901"]  # Putt::Putt09 never attempted


# ---------------------------------------------------------------
# _extract_confirmed_unit
# ---------------------------------------------------------------


def test_extract_confirmed_unit_recognizes_yds_and_percent():
    assert _extract_confirmed_unit("평균 남은 거리(yds)") == "yds"
    assert _extract_confirmed_unit("성공률(%)") == "%"


def test_extract_confirmed_unit_returns_none_for_non_unit_parenthetical():
    assert _extract_confirmed_unit("그린 적중률(RTP)") is None


def test_extract_confirmed_unit_returns_none_when_no_parenthetical():
    assert _extract_confirmed_unit("평균 남은 거리") is None
    assert _extract_confirmed_unit(None) is None


# ---------------------------------------------------------------
# build_official_metric_value_rows + ingest_official_metric_value_rows
# ---------------------------------------------------------------


def test_ingestion_builds_one_row_per_player_per_mapped_label(tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    # A single data-record="" marker (matching this family's ONE real
    # value column) tells _discover_record_fields the true field count
    # is 1, not the 5-field fallback — the ACTUAL value still comes
    # from the <td class="record"> cell's text, per this round's fix.
    html = f"""
    <table><thead><tr><th>순위</th><th>선수명</th><th>평균 티샷 거리(yds)</th></tr></thead>
      <tbody>
        <tr data-record=""><td class="text-start player_name"><a href="/web/profile/mainRecord?playerCode=111">A</a></td>
            <td class="record" data-rank="1">250.5</td></tr>
        <tr data-record=""><td class="text-start player_name"><a href="/web/profile/mainRecord?playerCode=222">B</a></td>
            <td class="record" data-rank="2">240.1</td></tr>
      </tbody>
    </table>
    """
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(html, encoding="utf-8")

    rows, mapping = build_official_metric_value_rows(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert len(rows) == 2
    by_player = {r["player_code"]: r for r in rows}
    assert by_player["111"]["value_raw"] == "250.5"
    assert by_player["111"]["unit"] == "yds"
    assert by_player["222"]["value_raw"] == "240.1"
    assert all(r["identity_key"] == "Tee::Tee01::010101" for r in rows)
    assert len(mapping) == 1
    assert mapping[0].status == "MAPPED"


def test_ingestion_skips_player_rows_with_no_player_code(tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>평균 티샷 거리(yds)</th></tr></thead>
      <tbody>
        <tr><td class="text-start player_name">이름없음</td>
            <td class="record" data-rank="1">250.5</td></tr>
      </tbody>
    </table>
    """
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(html, encoding="utf-8")
    rows, _mapping = build_official_metric_value_rows(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert rows == []


def test_ingestion_never_produces_rows_for_unmapped_identities(tmp_path):
    """No raw evidence at all -> UNMAPPED_PENDING_EVIDENCE -> zero
    official_metric_value rows, never fabricated."""
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    rows, mapping = build_official_metric_value_rows(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert rows == []
    assert mapping[0].status == "UNMAPPED_PENDING_EVIDENCE"


def test_ingest_official_metric_value_rows_writes_and_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    row = {
        "season": 2025, "player_code": "111", "identity_key": "Tee::Tee01::010101",
        "menu1": "Tee", "menu2": "Tee01", "menu3": "010101", "official_label": "평균 티샷 거리",
        "field_name": "record", "value_raw": "250.5", "unit": "yds",
        "response_column_label": "평균 티샷 거리(yds)", "schema_fingerprint": "DISTANCE",
        "parse_status": "DISCOVERED_NOT_VALIDATED", "validation_status": "CLEAN",
        "pit_status": "PIT_UNVERIFIED", "source_url": "https://klpga.co.kr/load/record/loadLocationRecord",
        "raw_sample_path": "x.html", "acquired_at": "2026-08-26T00:00:00+00:00",
    }
    n1 = ingest_official_metric_value_rows(conn, [row])
    n2 = ingest_official_metric_value_rows(conn, [row])
    assert n1 == 1 and n2 == 1
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == 1
    conn.close()


# ---------------------------------------------------------------
# Real-evidence integration pin
# ---------------------------------------------------------------


def test_real_evidence_ingests_into_a_real_schema_without_error():
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    rows, mapping = build_official_metric_value_rows(taxonomy, season="2025", raw_samples_dir=REAL_RAW_SAMPLES_DIR)
    assert rows  # real evidence must produce real rows, not silently nothing
    assert all(r["value_raw"] is not None for r in rows)  # Round 12's value-extraction bug fix

    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    n = ingest_official_metric_value_rows(conn, rows)
    assert n == len(rows)
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == len(rows)
    conn.close()


# ---------------------------------------------------------------
# Player identity verification — pure comparison, never fabricates
# either input set. Only synthetic sets are used for the comparison
# LOGIC itself; a real player_master set does not exist in this
# sandbox (no production database file is present) — see
# docs/HISTORICAL_METRICS_COLLECTION_DESIGN.md's LOCAL_EXECUTION_
# REQUIRED note.
# ---------------------------------------------------------------


def test_verify_identity_space_confirmed_when_full_overlap():
    result = verify_player_code_identity_space({"111", "222"}, {"111", "222", "333"})
    assert result["overall_status"] == STATUS_MATCH_CONFIRMED
    assert result["matched"] == 2
    assert result["match_rate"] == 1.0


def test_verify_identity_space_partial_when_some_overlap():
    result = verify_player_code_identity_space({"111", "222", "999"}, {"111", "222"})
    assert result["overall_status"] == STATUS_MATCH_PARTIAL
    assert result["matched"] == 2
    assert result["unmatched_loadlocationrecord_only"] == 1
    assert result["sample_unmatched"] == ["999"]


def test_verify_identity_space_none_when_zero_overlap():
    result = verify_player_code_identity_space({"aaa", "bbb"}, {"111", "222"})
    assert result["overall_status"] == STATUS_MATCH_NONE
    assert result["match_rate"] == 0.0


def test_verify_identity_space_no_data_when_either_set_empty():
    assert verify_player_code_identity_space(set(), {"111"})["overall_status"] == STATUS_MATCH_NO_DATA
    assert verify_player_code_identity_space({"111"}, set())["overall_status"] == STATUS_MATCH_NO_DATA
    assert verify_player_code_identity_space(set(), set())["overall_status"] == STATUS_MATCH_NO_DATA


def test_verify_identity_space_never_fabricates_a_match_from_nothing():
    """Both sets non-empty but disjoint -> honestly reports zero
    matches, never assumes compatibility."""
    result = verify_player_code_identity_space({"only_in_llr"}, {"only_in_pm"})
    assert result["matched"] == 0
    assert result["overall_status"] == STATUS_MATCH_NONE


def test_extract_player_codes_from_raw_samples_empty_dir_returns_empty_set(tmp_path):
    assert extract_player_codes_from_raw_samples(tmp_path) == set()


def test_extract_player_codes_from_raw_samples_missing_dir_returns_empty_set(tmp_path):
    assert extract_player_codes_from_raw_samples(tmp_path / "does_not_exist") == set()


def test_extract_player_codes_from_real_raw_samples_returns_real_codes():
    codes = extract_player_codes_from_raw_samples(REAL_RAW_SAMPLES_DIR)
    assert len(codes) > 0
    assert "10112" in codes  # 고지우, confirmed real evidence from Approach::Approach02::020201
    assert all(isinstance(c, str) and c for c in codes)
