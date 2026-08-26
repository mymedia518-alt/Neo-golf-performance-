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
    assert len(result.rows) == 2  # 김수지 (Round 3 Phase A) + 배소현 (Round 3 Phase B), both real reported evidence
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
    assert labels["record"] == "그린 적중률(%)"
    assert labels["record1"] == "그린 적중 횟수"
    assert labels["record2"] == "샷 시도 횟수"
    assert labels["record3"] == "측정 라운드"
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
    assert sd.numerator_semantics == "그린 적중 횟수"
    assert sd.denominator_semantics == "샷 시도 횟수"
    assert sd.sample_definition_text == "그린 적중 횟수 / 샷 시도 횟수"


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
    assert [row.player_name for row in r1.rows] == ["김수지", "배소현"]
    assert [row.player_name for row in r2.rows] == ["임희정"]


def test_empty_response_is_empty_not_failed():
    html = "<html><body><table><thead><tr><th>없음</th></tr></thead><tbody></tbody></table></body></html>"
    result = parse_record_response(html)
    assert result.parse_status == "EMPTY"
    assert result.rows == []


def test_malformed_html_is_failed_not_a_crash():
    result = parse_record_response("<<<not html at all>>>")
    assert result.parse_status in {"EMPTY", "FAILED", "AMBIGUOUS"}


def test_sg_total_response_discovers_six_record_fields_not_fixed_at_five():
    """The real SG Total evidence needs 6 named values (Total + 4
    components + measured rounds) — response_parser.py's record-field
    count must be discovered per-response, not hardcoded at 5."""
    result = parse_record_response(_read("loadLocationRecord_sg_total_sample.html"))
    row = result.rows[0]
    assert set(row.values.keys()) == {"record", "record1", "record2", "record3", "record4", "record5"}
    assert row.values["record"] == "2.38"
    assert row.values["record1"] == "0.67"
    assert row.values["record2"] == "1.00"
    assert row.values["record3"] == "0.17"
    assert row.values["record4"] == "0.54"
    assert row.values["record5"] == "61"


def test_sg_total_response_resolves_player_code_via_href_fallback():
    """No data-playercode attribute exists on this fixture's row —
    player_code must come from the /web/profile/mainRecord?playerCode=
    link instead, per the user's directly reported evidence."""
    result = parse_record_response(_read("loadLocationRecord_sg_total_sample.html"))
    row = result.rows[0]
    assert row.player_code == "11134"
    assert row.player_code_source == "href_query_param"
    assert row.player_name == "서교림"


def test_data_attribute_player_code_is_preferred_over_href_when_both_present():
    html = """
    <table><tbody>
      <tr data-playercode="99999" data-name="테스트">
        <td><a href="/web/profile/mainRecord?playerCode=11134">테스트</a></td>
      </tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    row = result.rows[0]
    assert row.player_code == "99999"
    assert row.player_code_source == "data_attribute"


def test_row_with_no_recognizable_attributes_is_skipped_not_fabricated():
    html = """
    <table><tbody>
      <tr><td>공지: 데이터 없음</td></tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    assert result.rows == []
    assert result.parse_status == "EMPTY"


# ---------------------------------------------------------------
# Phase B1 — CONFIRMED root cause for CLASS 1 (real 231-row responses
# classifying as EMPTY_SCHEMA): KLPGA fills header text client-side via
# jQuery from separate `var record = "...";` JS declarations, not the
# JSON-object metadata shape this parser previously looked for. These
# tests use a fixture modeled directly on real cached-response evidence
# (see the fixture's own header comment for the exact reported values).
# ---------------------------------------------------------------


def _dynamic_header_html() -> str:
    return _read("loadLocationRecord_dynamic_header_sample.html")


def test_dynamic_header_response_schema_is_not_empty():
    """The core regression: a real-shaped response with 231-row-style
    evidence (here, 2 sanitized rows) must NOT classify as
    EMPTY_SCHEMA merely because its <th> text is blank — the real
    labels must be recovered from the `var record...` declarations."""
    result = parse_record_response(_dynamic_header_html())
    assert result.parse_status != "EMPTY"
    assert result.parse_status != "AMBIGUOUS"
    labels = {c.field_name: c.label for c in result.column_semantics}
    assert labels["record"] == "그린 적중률(%)"


def test_dynamic_header_recovers_all_four_nonblank_labels():
    result = parse_record_response(_dynamic_header_html())
    labels = {c.field_name: c.label for c in result.column_semantics}
    assert labels["record"] == "그린 적중률(%)"
    assert labels["record1"] == "그린 적중 횟수"
    assert labels["record2"] == "샷 시도 횟수"
    assert labels["record3"] == "측정 라운드"
    sources = {c.field_name: c.source for c in result.column_semantics}
    assert sources["record"] == "dynamic_header_vars"
    assert sources["record1"] == "dynamic_header_vars"
    assert sources["record2"] == "dynamic_header_vars"
    assert sources["record3"] == "dynamic_header_vars"


def test_dynamic_header_blank_record4_does_not_create_a_fake_metric():
    """var record4 = ""; must NOT be stored as a real label — it must
    resolve to label=None / source="unknown", exactly like no label
    being found at all, never an empty-string "label" that could later
    be mistaken for real evidence."""
    result = parse_record_response(_dynamic_header_html())
    record4 = next(c for c in result.column_semantics if c.field_name == "record4")
    assert record4.label is None
    assert record4.source == "unknown"


def test_dynamic_header_values_map_to_the_correct_labeled_fields():
    result = parse_record_response(_dynamic_header_html())
    row1 = next(r for r in result.rows if r.player_name == "김새로미")
    assert row1.values["record"] == "40"
    assert row1.values["record1"] == "36"
    assert row1.values["record2"] == "90"
    assert row1.values["record3"] == "5"
    assert row1.values["record4"] == "0.0"

    row2 = next(r for r in result.rows if r.player_name == "전예성")
    assert row2.values["record"] == "33.33"
    assert row2.values["record1"] == "12"
    assert row2.values["record2"] == "36"
    assert row2.values["record3"] == "5"
    assert row2.values["record4"] == "0.0"


def test_dynamic_header_playercode_is_recovered():
    result = parse_record_response(_dynamic_header_html())
    codes = {r.player_name: (r.player_code, r.player_code_source) for r in result.rows}
    assert codes["김새로미"] == ("9807", "data_attribute")
    assert codes["전예성"] == ("9812", "data_attribute")


def test_dynamic_header_static_table_th_text_is_never_used_when_blank():
    """Documents WHY the old table-header fallback alone produced
    EMPTY_SCHEMA for this real response shape: the <th> elements exist
    (so header_labels is non-empty) but their text is blank, and blank
    table-header text must never be treated as a found label."""
    result = parse_record_response(_dynamic_header_html())
    assert all(c.source != "table_header" for c in result.column_semantics)


def test_static_blank_th_alone_without_dynamic_vars_is_unknown_not_a_fake_label():
    """Isolates the table-header-blank-text behavior from the dynamic-
    header fix: with NO `var record...` declarations at all, blank
    <th> text must resolve to unknown, not an empty-string
    "table_header" label (a real regression risk introduced by this
    round's fix — a blank header must never silently become
    "confirmed" evidence of anything)."""
    html = """
    <table><thead><tr><th></th><th></th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="1" data-record1="2">
      <td>1</td><td>테스트</td><td></td><td></td>
    </tr></tbody></table>
    """
    result = parse_record_response(html)
    assert all(c.label is None and c.source == "unknown" for c in result.column_semantics)
    assert result.parse_status == "AMBIGUOUS"
