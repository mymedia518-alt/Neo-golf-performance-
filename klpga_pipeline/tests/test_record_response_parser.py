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


# ---------------------------------------------------------------
# Round 8 — real player_name row-markup evidence (Sg::Around,
# docs/discovery/raw_samples/Sg__Around__2025.html, pasted directly by
# the user via a targeted regex extraction, 2026-08-26): the Sg
# family's real rows carry NO data-name/data-playername attribute on
# the <tr> at all — the fresh bounded B1 rerun reported
# missing_player_name=231/231 despite missing_player_code=0/231 (the
# href-based playerCode fallback already worked). The name is the text
# of a <a href=".../mainRecord?playerCode=...">Name</a> nested inside
# a <td class="text-start player_name"> cell. See
# _extract_player_name_from_cell in response_parser.py.
# ---------------------------------------------------------------


def test_player_name_extracted_from_player_name_cell_when_no_data_attribute():
    html = """
    <table><tbody>
      <tr>
        <td class="td-like">
          <div class="form-check form-check-like">
            <input class="form-check-input" type="checkbox" _favoritPlayerCode="9134">
          </div>
        </td>
        <td class="text-start">1<!-- <span class="ms-2 tb-rank-up">1</span> --></td>
        <td><span class="tb-flag" style="background-image: url('/resources/web/images/country/KOR.png');"></span></td>
        <td class="text-start player_name">
          <a href="/web/profile/mainRecord?playerCode=9134">김새로미</a>
        </td>
      </tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    row = result.rows[0]
    assert row.player_code == "9134"
    assert row.player_code_source == "href_query_param"
    assert row.player_name == "김새로미"


def test_data_attribute_player_name_is_preferred_over_cell_fallback_when_both_present():
    html = """
    <table><tbody>
      <tr data-name="데이터속성이름">
        <td class="text-start player_name"><a href="/web/profile/mainRecord?playerCode=1">셀텍스트이름</a></td>
      </tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    row = result.rows[0]
    assert row.player_name == "데이터속성이름"


def test_player_name_cell_fallback_uses_cell_text_when_no_anchor_present():
    html = """
    <table><tbody>
      <tr>
        <td data-playercode="9812"></td>
        <td class="text-start player_name">전예성</td>
      </tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    row = result.rows[0]
    assert row.player_name == "전예성"


def test_player_code_recovered_from_favorite_checkbox_when_no_href_present():
    """Round 9 follow-up: real evidence (docs/discovery/raw_samples/
    Sg__Around__2025.html) showed 9 of 232 real Sg::Around rows have a
    td.player_name cell with NO nested <a> at all — missing_player_name
    stayed 0 (the cell-text fallback still supplies a name), but
    missing_player_code was 9 (nothing previously read the row's
    _favoritPlayerCode checkbox attribute). This is that exact shape:
    no data-playercode attribute, no <a> anywhere in the row, only the
    checkbox's _favoritPlayerCode value."""
    html = """
    <table><tbody>
      <tr>
        <td class="td-like">
          <div class="form-check form-check-like">
            <input class="form-check-input" type="checkbox" _favoritPlayerCode="9999">
          </div>
        </td>
        <td class="text-start">3</td>
        <td><span class="tb-flag" style="background-image: url('/resources/web/images/country/KOR.png');"></span></td>
        <td class="text-start player_name">이름없는선수</td>
      </tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    row = result.rows[0]
    assert row.player_code == "9999"
    assert row.player_code_source == "favorite_checkbox_attribute"
    assert row.player_name == "이름없는선수"


def test_href_derived_player_code_is_preferred_over_favorite_checkbox_when_both_present():
    """Precedence must not regress: the already-working href-based
    extraction (223/232 real rows) must still win over the new
    checkbox fallback when both sources are present on the same row."""
    html = """
    <table><tbody>
      <tr>
        <td class="td-like">
          <div class="form-check form-check-like">
            <input class="form-check-input" type="checkbox" _favoritPlayerCode="9134">
          </div>
        </td>
        <td class="text-start player_name">
          <a href="/web/profile/mainRecord?playerCode=1111">김새로미</a>
        </td>
      </tr>
    </tbody></table>
    """
    result = parse_record_response(html)
    row = result.rows[0]
    assert row.player_code == "1111"
    assert row.player_code_source == "href_query_param"


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


# ---------------------------------------------------------------
# Round 12 — value/rank extraction from <td class="record"/"record1"/
# ...> cell TEXT, the real record-family row shape (no data-* on the
# <tr> at all — everything lives on child <td> cells). This is the
# exact gap the Sg-family fixture's Round 9 comment documented as
# unresolvable for lack of un-truncated real evidence
# (`values["record"] correctly None`); Round 12's real, complete
# Approach/Tee/Around/Putt raw_samples/ evidence supplies it.
# ---------------------------------------------------------------


def _cell_value_html(record_html: str) -> str:
    return f"""
    <table>
      <thead><tr><th></th><th></th><th></th></tr></thead>
      <tbody>
        <tr>
          <td class="text-start player_name"><a href="/web/profile/mainRecord?playerCode=10112">고지우</a></td>
          {record_html}
        </tr>
      </tbody>
    </table>
    """


def test_value_recovered_from_record_cell_text_when_no_data_attribute():
    html = _cell_value_html(
        '<td class="record" data-rank="1">6.26</td><td class="record1">5,444.38</td>'
    )
    result = parse_record_response(html)
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.values["record"] == "6.26"
    assert row.values["record1"] == "5,444.38"


def test_rank_recovered_from_record_cell_data_rank_when_no_data_attribute_on_tr():
    html = _cell_value_html('<td class="record" data-rank="1">6.26</td>')
    result = parse_record_response(html)
    assert result.rows[0].rank == "1"


def test_html_comment_inside_record_cell_is_excluded_from_the_value():
    """Real evidence: `<td class="record" data-rank="1">6.26 <!--
    <span class="tb-rank-up">50</span> --></td>` — the trailing rank-
    change comment must never leak into the extracted value text."""
    html = _cell_value_html(
        '<td class="record" data-rank="1">6.26 <!-- <span class="ms-2 tb-rank-up">50</span> --></td>'
    )
    result = parse_record_response(html)
    assert result.rows[0].values["record"] == "6.26"


def test_data_attribute_value_is_preferred_over_cell_text_when_both_present():
    html = f"""
    <table>
      <thead><tr><th></th></tr></thead>
      <tbody>
        <tr data-record="9.99">
          <td class="record">6.26</td>
        </tr>
      </tbody>
    </table>
    """
    result = parse_record_response(html)
    assert result.rows[0].values["record"] == "9.99"


def test_empty_record_cell_yields_none_not_empty_string():
    html = _cell_value_html('<td class="record"></td>')
    result = parse_record_response(html)
    assert result.rows[0].values["record"] is None


REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


def test_real_approach02_evidence_recovers_the_first_players_real_values():
    """Pinned to the REAL, committed Approach::Approach02::020201 raw
    response — 고지우 (playerCode=10112)'s real first row:
    record=6.26, record1=5,444.38, record2=870, record3=83,
    record4=0.0, rank=1."""
    html = (REAL_RAW_SAMPLES_DIR / "Approach__Approach02__020201__2025.html").read_text(encoding="utf-8")
    result = parse_record_response(html)
    row = next(r for r in result.rows if r.player_code == "10112")
    assert row.rank == "1"
    assert row.values["record"] == "6.26"
    assert row.values["record1"] == "5,444.38"
    assert row.values["record2"] == "870"
    assert row.values["record3"] == "83"
    assert row.values["record4"] == "0.0"
