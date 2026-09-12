from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.website_v2.record_report_warehouse import (
    RecordReportParseError,
    RecordReportSnapshotConflict,
    build_snapshot,
    join_identity_by_player_code,
    parse_record_report_html,
    sha256_file,
    write_snapshot_immutable,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "content" / "website_v2" / "raw_sources"
CAPTURE_A = RAW / "KLPGA_RECORD_REPORT_2026_CAPTURE_A_10ROW.html"
CAPTURE_B = RAW / "KLPGA_RECORD_REPORT_2026_CAPTURE_B_EXPANDED.html"
SHA_A = "198df55cf31b05a141deb83c5269fe40c46a5d20ad623093dc86ab647e0a9538"
SHA_B = "31ee0f1096f7e552bb4fd235dc4c8533f694f265c4aaa445d44a327fbac05ae0"


@pytest.fixture(scope="module")
def html_b():
    return CAPTURE_B.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def records_b(html_b):
    return parse_record_report_html(html_b)


def test_raw_captures_have_the_verified_sha256():
    assert sha256_file(CAPTURE_A) == SHA_A
    assert sha256_file(CAPTURE_B) == SHA_B


def test_153_row_real_fixture(records_b):
    assert len(records_b) == 153


def test_player_code_uniqueness(records_b):
    codes = [r["playerCode"] for r in records_b]
    assert len(set(codes)) == 153


def test_original_10_reconciliation(records_b):
    html_a = CAPTURE_A.read_text(encoding="utf-8")
    records_a = parse_record_report_html(html_a)
    assert len(records_a) == 10
    by_code_b = {r["playerCode"]: r for r in records_b}
    compare_keys = ("money", "average_score", "average_putts", "birdie_rate", "gir_rate", "par_save_rate", "par_break_rate", "recovery_rate")
    for ra in records_a:
        rb = by_code_b.get(ra["playerCode"])
        assert rb is not None, f"original player {ra['playerCode']} missing from expanded capture"
        for key in compare_keys:
            assert ra[key] == rb[key], f"{ra['playerCode']} field {key} diverges: {ra[key]!r} != {rb[key]!r}"


def test_10725_kim_min_sol_present(records_b):
    row = next(r for r in records_b if r["playerCode"] == "10725")
    assert row["player_name"] == "김민솔"


def test_null_tail_metrics_never_become_zero(records_b):
    tail = [r for r in records_b if r["official_rank"] == 152]
    assert len(tail) == 2
    for row in tail:
        assert row["playerCode"] and row["player_name"]
        assert row["money"] is not None
        for field in ("average_score", "average_putts", "birdie_rate", "gir_rate", "par_save_rate", "par_break_rate", "recovery_rate"):
            assert row[field] is None, f"{field} must be NULL, not 0, when the source cell is empty"
            assert row[f"{field}_raw"] == ""


def test_tied_official_rank_is_allowed_not_deduplicated(records_b):
    ranks = [r["official_rank"] for r in records_b]
    assert ranks.count(152) == 2  # a genuine tie, not an error
    # uniqueness is enforced on playerCode only, never on official_rank
    assert len(set(r["playerCode"] for r in records_b)) == len(records_b)


def test_raw_and_normalized_fields_are_both_preserved(records_b):
    row = next(r for r in records_b if r["playerCode"] == "10725")
    assert row["money_raw"] == "1,366,629,428"
    assert row["money"] == 1366629428
    assert row["average_score_raw"] == "70.3279"
    assert row["average_score"] == pytest.approx(70.3279)


def test_snapshot_build_from_capture_b(html_b):
    snapshot = build_snapshot(
        html=html_b, source_sha256=SHA_B, source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All", expanded_view=True,
    )
    assert snapshot.source_rows == 153
    assert snapshot.unique_players == 153
    assert snapshot.population_completeness == "UNVERIFIED"
    assert snapshot.source_type == "klpga_official_record_report_total_view"
    # this must never be a tournament-round artifact
    assert not hasattr(snapshot, "game_code")
    assert not hasattr(snapshot, "round")
    assert "game_code" not in snapshot.records[0]
    assert "round" not in snapshot.records[0]


def test_population_completeness_stays_unverified_regardless_of_row_count(html_b):
    snapshot = build_snapshot(
        html=html_b, source_sha256=SHA_B, source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All", expanded_view=True,
    )
    # 153 > 10 must NOT flip completeness to PASS -- no official totalCount exists in source.
    assert snapshot.population_completeness == "UNVERIFIED"


def test_same_source_ingestion_is_idempotent(tmp_path, html_b):
    snapshot = build_snapshot(
        html=html_b, source_sha256=SHA_B, source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All", expanded_view=True,
    )
    path = tmp_path / "snapshot.json"
    assert write_snapshot_immutable(snapshot, path) is True
    first_content = path.read_text(encoding="utf-8")
    # re-ingest the SAME source a second time
    snapshot_again = build_snapshot(
        html=html_b, source_sha256=SHA_B, source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All", expanded_view=True,
    )
    assert write_snapshot_immutable(snapshot_again, path) is False  # idempotent no-op
    assert path.read_text(encoding="utf-8") == first_content


def test_conflicting_content_under_same_snapshot_identity_is_rejected(tmp_path, html_b):
    snapshot = build_snapshot(
        html=html_b, source_sha256=SHA_B, source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All", expanded_view=True,
    )
    path = tmp_path / "snapshot.json"
    write_snapshot_immutable(snapshot, path)
    # tamper with the written file's normalized_sha256 to simulate a conflicting write attempt
    # under the SAME snapshot_id (same source_sha256) but with different content -- e.g. a
    # parser bug that would otherwise silently overwrite a previously-written snapshot.
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["normalized_sha256"] = "deadbeef" * 8
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RecordReportSnapshotConflict):
        write_snapshot_immutable(snapshot, path)


def test_no_tournament_r2_semantics_required(records_b):
    for row in records_b:
        assert "game_code" not in row
        assert "round" not in row
        assert "END_OF_R2" not in row


def test_identity_join_is_by_player_code_only(records_b):
    cohort = [{"player_id": "10725", "player_name": "ANY DIFFERENT NAME STRING"}]
    result = join_identity_by_player_code(records_b, cohort)
    # matched purely by code, even though the name string differs -- proving there is
    # no name-based gate on the match itself (name divergence is reported, not blocking).
    assert result["matched"] == ["10725"]
    assert result["name_conflicts"] == [{
        "player_id": "10725", "record_report_name": "김민솔", "cohort_name": "ANY DIFFERENT NAME STRING",
    }]


def test_name_conflict_is_detected_and_never_silently_overwrites_either_source(records_b):
    cohort = [{"player_id": "10725", "player_name": "이름이다름"}]
    result = join_identity_by_player_code(records_b, cohort)
    assert len(result["name_conflicts"]) == 1
    conflict = result["name_conflicts"][0]
    # both original strings survive untouched in the report -- neither is overwritten.
    assert conflict["record_report_name"] == "김민솔"
    assert conflict["cohort_name"] == "이름이다름"


def test_no_name_only_fallback_when_player_code_is_absent(records_b):
    cohort = [{"player_id": "99999999_NOT_IN_RECORD_REPORT", "player_name": "김민솔"}]
    result = join_identity_by_player_code(records_b, cohort)
    # even though a player NAMED 김민솔 exists in records_b (under a different code),
    # a code-mismatch must be reported as unmatched, never rescued by matching on name.
    assert result["matched"] == []
    assert result["unmatched"] == [{"player_id": "99999999_NOT_IN_RECORD_REPORT", "player_name": "김민솔"}]


def test_duplicate_player_code_within_source_is_rejected():
    fake_html = """
    <table class="table table-record table-hover">
    <thead><tr></tr></thead>
    <tbody>
    <tr><td><input _favoritplayercode="1"></td><td class="text-start">1</td>
    <td class="text-start"><a href="?playerCode=1">A선수</a></td>
    <td class="record">1,000</td>
    <td class="data1">70</td><td class="data2">30</td><td class="data3">10</td>
    <td class="data4">70</td><td class="data5">80</td><td class="data6">10</td><td class="data7">50</td></tr>
    <tr><td><input _favoritplayercode="1"></td><td class="text-start">2</td>
    <td class="text-start"><a href="?playerCode=1">B선수</a></td>
    <td class="record">500</td>
    <td class="data1">71</td><td class="data2">31</td><td class="data3">11</td>
    <td class="data4">71</td><td class="data5">81</td><td class="data6">11</td><td class="data7">51</td></tr>
    </tbody></table>
    """
    with pytest.raises(RecordReportParseError):
        build_snapshot(
            html=fake_html, source_sha256="fake", source_url="https://klpga.co.kr/web/record/totalRecord",
            capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All", expanded_view=False,
        )


def test_blank_player_code_or_name_is_rejected():
    blank_code_html = """
    <table class="table table-record table-hover"><tbody>
    <tr><td><input _favoritplayercode=""></td><td class="text-start">1</td>
    <td class="text-start"><a href="?playerCode=1">A선수</a></td>
    <td class="record">1,000</td>
    <td class="data1">70</td><td class="data2">30</td><td class="data3">10</td>
    <td class="data4">70</td><td class="data5">80</td><td class="data6">10</td><td class="data7">50</td></tr>
    </tbody></table>
    """
    with pytest.raises(RecordReportParseError):
        parse_record_report_html(blank_code_html)
