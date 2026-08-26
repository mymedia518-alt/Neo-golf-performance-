"""Tests for klpga.discovery.response_parser — against fixture HTML
only. See the module's own docstring: this parser's row/column-
extraction logic is a working assumption pending real captured HTML,
not yet independently verified against a live response."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.response_parser import parse_record_response

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_020104_with_metadata_block_is_confirmed():
    """The 020104 fixture includes an embedded metadata block, so
    parse_status must reach CONFIRMED (the strongest evidence tier),
    not merely DISCOVERED_NOT_VALIDATED."""
    result = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    assert result.parse_status == "CONFIRMED"
    assert result.metadata.found is True
    assert result.metadata.menu_name == "그린 적중률"


def test_020104_row_values_match_the_real_reported_evidence():
    result = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.player_code == "P_KIMSJ"
    assert row.player_name == "김수지"
    assert row.rank == "1"
    assert row.values["record"] == "70.49"
    assert row.values["record1"] == "43"
    assert row.values["record2"] == "61"
    assert row.values["record3"] == "73"
    assert row.values["record4"] == "-0.0465"


def test_020105_without_metadata_falls_back_to_table_header_and_is_discovered_not_validated():
    """The 020105 fixture deliberately omits the metadata block —
    parse_status must be DISCOVERED_NOT_VALIDATED, and column
    semantics must come from the table header, not invented."""
    result = parse_record_response(_read("loadLocationRecord_approach_020105_sample.html"))
    assert result.parse_status == "DISCOVERED_NOT_VALIDATED"
    assert result.metadata.found is False

    labels = {c.field_name: c.label for c in result.column_semantics}
    assert labels["record"] == "GIR"
    assert labels["record1"] == "성공"
    assert labels["record2"] == "시도"
    assert labels["record3"] == "측정라운드"
    assert labels["record4"] == "RTP"
    assert all(c.source == "table_header" for c in result.column_semantics)


def test_020105_row_values_match_the_real_reported_evidence():
    result = parse_record_response(_read("loadLocationRecord_approach_020105_sample.html"))
    row = result.rows[0]
    assert row.player_name == "임희정"
    assert row.values["record"] == "74.45"
    assert row.values["record1"] == "169"
    assert row.values["record2"] == "227"
    assert row.values["record3"] == "84"
    assert row.values["record4"] == "-0.0769"


def test_sample_definition_is_derived_only_from_real_labels_020105():
    result = parse_record_response(_read("loadLocationRecord_approach_020105_sample.html"))
    sd = result.sample_definition
    assert sd.numerator_semantics == "성공"
    assert sd.denominator_semantics == "시도"
    assert sd.sample_definition_text == "성공 / 시도"


def test_020104_and_020105_are_parsed_independently_not_from_shared_state():
    """Both fixtures use the same record/record1..4 field NAMES, but
    each response must be parsed fresh — evidenced by the two reaching
    different parse_status (metadata found vs. not) despite otherwise
    similar structure, and by neither response's rows leaking into the
    other's result."""
    r1 = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    r2 = parse_record_response(_read("loadLocationRecord_approach_020105_sample.html"))
    assert r1.metadata.found is True
    assert r2.metadata.found is False
    assert r1.parse_status != r2.parse_status
    assert [row.player_name for row in r1.rows] == ["김수지"]
    assert [row.player_name for row in r2.rows] == ["임희정"]


def test_empty_response_is_empty_not_failed():
    html = "<html><body><table><thead><tr><th>없음</th></tr></thead><tbody></tbody></table></body></html>"
    result = parse_record_response(html)
    assert result.parse_status == "EMPTY"
    assert result.rows == []


def test_malformed_html_is_failed_not_a_crash():
    result = parse_record_response("<<<not html at all>>>")
    assert result.parse_status in {"EMPTY", "FAILED", "AMBIGUOUS"}


def test_row_with_no_recognizable_attributes_is_skipped_not_fabricated():
    html = """
    <table><tbody>
      <tr><td>공지: 데이터 없음</td></tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    assert result.rows == []
    assert result.parse_status == "EMPTY"
