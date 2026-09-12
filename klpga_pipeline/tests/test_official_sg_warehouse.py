from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.website_v2.official_sg_warehouse import (
    OfficialSGParseError,
    OfficialSGSnapshotConflict,
    build_snapshot,
    parse_official_sg_html,
    sha256_file,
    write_snapshot_immutable,
)
from klpga.website_v2.record_report_warehouse import join_identity_by_player_code

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "content" / "website_v2" / "raw_sources"
CAPTURE_SG = RAW / "KLPGA_OFFICIAL_SG_2026_CAPTURE.html"
SHA_SG = "fbb5d3fa3e4cb123cf9197fb3def2679277f0d446ff54c4a1da8fae7806fa26c"


@pytest.fixture(scope="module")
def html_sg():
    return CAPTURE_SG.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def records_sg(html_sg):
    return parse_official_sg_html(html_sg)


def test_raw_sg_capture_has_the_verified_sha256():
    assert sha256_file(CAPTURE_SG) == SHA_SG


def test_242_row_real_sg_fixture(records_sg):
    assert len(records_sg) == 242


def test_sg_player_code_uniqueness(records_sg):
    codes = [r["playerCode"] for r in records_sg]
    assert len(set(codes)) == 242


def test_sg_component_sum_within_tolerance(records_sg):
    violations = 0
    for r in records_sg:
        total, ott, app, arg, putt = r["official_sg_total"], r["official_sg_ott"], r["official_sg_app"], r["official_sg_arg"], r["official_sg_putt"]
        if None in (total, ott, app, arg, putt):
            continue
        if abs(total - (ott + app + arg + putt)) > 0.05:
            violations += 1
    assert violations == 0


def test_blank_sg_cells_are_none_never_zero():
    fixture_html = """
    <table class="table table-record table-hover"><tbody>
    <tr><td><input _favoritplayercode="1"></td><td class="text-start"></td>
    <td><span></span></td><td class="text-start player_name">A선수</td>
    <td class="record" data-rank=""></td>
    <td class="data1" data-rank=""></td><td class="data2" data-rank=""></td>
    <td class="data3" data-rank=""></td><td class="data4" data-rank=""></td>
    <td class="data5"></td></tr>
    </tbody></table>
    """
    records = parse_official_sg_html(fixture_html)
    row = records[0]
    assert row["official_rank"] is None
    for field in ("official_sg_total", "official_sg_ott", "official_sg_app", "official_sg_arg", "official_sg_putt", "official_sg_rounds"):
        assert row[field] is None
        assert row[f"{field}_raw"] == ""


def test_player_name_without_anchor_link_is_still_parsed(records_sg):
    # a real row in the source (foreign player, no linked profile page) --
    # this must not be dropped or silently blank.
    row = next(r for r in records_sg if r["playerCode"] == "13502")
    assert row["player_name"] == "왕 즈쉬엔"


def test_no_name_only_fallback_in_official_join(records_sg):
    cohort = [{"player_id": "99999999_NOT_A_REAL_CODE", "player_name": "서교림"}]
    result = join_identity_by_player_code(records_sg, cohort)
    assert result["matched"] == []
    assert result["unmatched"] == [{"player_id": "99999999_NOT_A_REAL_CODE", "player_name": "서교림"}]


def test_unmatched_players_are_enumerated_not_dropped(records_sg):
    cohort = [{"player_id": "11134", "player_name": "서교림"}, {"player_id": "DOES_NOT_EXIST", "player_name": "없는선수"}]
    result = join_identity_by_player_code(records_sg, cohort)
    assert result["matched"] == ["11134"]
    assert result["unmatched"] == [{"player_id": "DOES_NOT_EXIST", "player_name": "없는선수"}]


def test_low_sample_player_is_preserved_not_dropped(records_sg):
    row = next(r for r in records_sg if r["playerCode"] == "1330")
    assert row["official_sg_rounds"] == 2
    assert row["official_sg_total"] == -14.50


def test_official_sg_field_names_never_collide_with_neo_field_names(records_sg):
    neo_field_names = {"neo_rank", "neo_validation_rank", "long_term_sg", "recent_5_sg", "recent_10_sg", "sample_count", "validation_score"}
    for row in records_sg[:5]:
        assert not (set(row) & neo_field_names), "official SG row must never carry a NEO-namespaced field"
    for field in records_sg[0]:
        if field not in ("playerCode", "player_name", "official_rank"):
            assert field.startswith("official_sg_"), f"non-official-namespaced field leaked into official SG schema: {field}"


def test_snapshot_build_from_capture_sg(html_sg):
    snapshot = build_snapshot(
        html=html_sg, source_sha256=SHA_SG, source_url="https://klpga.co.kr/web/record/locationRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All",
    )
    assert snapshot.source_rows == 242
    assert snapshot.unique_players == 242
    assert snapshot.population_completeness == "UNVERIFIED"
    assert snapshot.source_type == "klpga_official_sg_location_record"


def test_same_source_ingestion_is_idempotent(tmp_path, html_sg):
    snapshot = build_snapshot(
        html=html_sg, source_sha256=SHA_SG, source_url="https://klpga.co.kr/web/record/locationRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All",
    )
    path = tmp_path / "sg_snapshot.json"
    assert write_snapshot_immutable(snapshot, path) is True
    first_content = path.read_text(encoding="utf-8")
    snapshot_again = build_snapshot(
        html=html_sg, source_sha256=SHA_SG, source_url="https://klpga.co.kr/web/record/locationRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All",
    )
    assert write_snapshot_immutable(snapshot_again, path) is False
    assert path.read_text(encoding="utf-8") == first_content


def test_conflicting_content_under_same_snapshot_identity_is_rejected(tmp_path, html_sg):
    snapshot = build_snapshot(
        html=html_sg, source_sha256=SHA_SG, source_url="https://klpga.co.kr/web/record/locationRecord",
        capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All",
    )
    path = tmp_path / "sg_snapshot.json"
    write_snapshot_immutable(snapshot, path)
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["normalized_sha256"] = "deadbeef" * 8
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(OfficialSGSnapshotConflict):
        write_snapshot_immutable(snapshot, path)


def test_duplicate_player_code_within_sg_source_is_rejected():
    fake_html = """
    <table class="table table-record table-hover"><tbody>
    <tr><td><input _favoritplayercode="1"></td><td class="text-start">1</td>
    <td><span></span></td><td class="text-start player_name"><a href="?playerCode=1">A선수</a></td>
    <td class="record" data-rank="1">1.00</td>
    <td class="data1" data-rank="1">0.50</td><td class="data2" data-rank="1">0.20</td>
    <td class="data3" data-rank="1">0.10</td><td class="data4" data-rank="1">0.20</td>
    <td class="data5">10</td></tr>
    <tr><td><input _favoritplayercode="1"></td><td class="text-start">2</td>
    <td><span></span></td><td class="text-start player_name"><a href="?playerCode=1">B선수</a></td>
    <td class="record" data-rank="2">0.50</td>
    <td class="data1" data-rank="2">0.10</td><td class="data2" data-rank="2">0.10</td>
    <td class="data3" data-rank="2">0.10</td><td class="data4" data-rank="2">0.20</td>
    <td class="data5">5</td></tr>
    </tbody></table>
    """
    with pytest.raises(OfficialSGParseError):
        build_snapshot(
            html=fake_html, source_sha256="fake", source_url="https://klpga.co.kr/web/record/locationRecord",
            capture_timestamp="TEST_FIXTURE", effective_season=2026, menu_mode="All",
        )


def test_reproducible_parse_of_full_real_capture(html_sg):
    a = parse_official_sg_html(html_sg)
    b = parse_official_sg_html(html_sg)
    assert a == b
