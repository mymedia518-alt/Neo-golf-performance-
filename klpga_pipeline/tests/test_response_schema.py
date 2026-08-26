"""Tests for klpga.discovery.response_schema — Phase B1 core analysis.
Fixture/inline HTML only, no network access."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.response_parser import parse_record_response
from klpga.discovery.response_schema import (
    PIT_STATUS,
    analyze_response,
    build_schema_fingerprint,
    classify_column_kind,
    classify_historical_availability,
    detect_rtp_status,
    detect_sample_size_fields,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------
# TEST 9/10 — schema fingerprint generation
# ---------------------------------------------------------------


def test_classify_column_kind_priority_order():
    assert classify_column_kind("RTP") == "RTP"
    assert classify_column_kind("측정 라운드") == "ROUNDS"
    assert classify_column_kind("그린 적중률(%)") == "RATE"
    assert classify_column_kind("샷 시도 횟수") == "COUNT"
    assert classify_column_kind("평균 티샷 거리") == "DISTANCE"
    assert classify_column_kind("평균") == "AVERAGE"
    assert classify_column_kind("아무거나") == "UNKNOWN"
    assert classify_column_kind(None) == "UNKNOWN"


def test_approach_020104_fingerprint_matches_real_confirmed_column_order():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    fingerprint = build_schema_fingerprint(parsed.column_semantics)
    assert fingerprint == "RATE_COUNT_COUNT_ROUNDS_RTP"


def test_two_metrics_with_identical_column_structure_get_the_same_fingerprint():
    r1 = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    r2 = parse_record_response(_read("loadLocationRecord_approach_020105_sample.html"))
    assert build_schema_fingerprint(r1.column_semantics) == build_schema_fingerprint(r2.column_semantics)


def test_empty_schema_fingerprint_for_no_labeled_columns():
    assert build_schema_fingerprint([]) == "EMPTY_SCHEMA"


# ---------------------------------------------------------------
# TEST 7 — raw numerator/denominator detection
# ---------------------------------------------------------------


def test_confirmed_raw_pair_detected_for_approach_gir():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    analysis = analyze_response(parsed)
    assert analysis.raw_pair.status == "CONFIRMED_RAW_PAIR"
    assert analysis.raw_pair.numerator_field == "record1"
    assert analysis.raw_pair.denominator_field == "record2"


def test_raw_pair_validation_matches_the_real_confirmed_arithmetic():
    """43/61*100 = 70.49...% — matches the displayed 70.49% within
    ordinary rounding tolerance."""
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    analysis = analyze_response(parsed)
    validation = analysis.raw_pair.validation
    assert validation is not None
    assert validation.checked_rows == 2  # 김수지 + 배소현, both real reported evidence
    assert validation.matches_within_tolerance == 2
    assert validation.max_abs_difference < 0.5


def test_raw_pair_status_not_applicable_when_no_rate_or_count_columns():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>평균 티샷 거리</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="270.5"><td>1</td><td>테스트</td><td>270.5</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.raw_pair.status == "NOT_APPLICABLE"


def test_raw_pair_status_rate_only_when_no_count_columns():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>성공률(%)</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="55.0"><td>1</td><td>테스트</td><td>55.0</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.raw_pair.status == "RATE_ONLY"


def test_raw_pair_status_partial_when_only_one_count_column():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>성공률(%)</th><th>시도 횟수</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="55.0" data-record1="20"><td>1</td><td>테스트</td><td>55.0</td><td>20</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.raw_pair.status == "PARTIAL_RAW_PAIR"


def test_raw_pair_status_unknown_when_column_semantics_all_unresolved():
    analysis = analyze_response(parse_record_response("<table><tbody></tbody></table>"))
    assert analysis.raw_pair.status in ("UNKNOWN", "NOT_APPLICABLE")


# ---------------------------------------------------------------
# TEST 8 — measured-round / sample-size detection
# ---------------------------------------------------------------


def test_sample_size_fields_preserve_distinct_types_not_merged():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    fields = detect_sample_size_fields(parsed.column_semantics, parsed.rows)
    types = {f.sample_size_type for f in fields}
    # 성공 횟수 (COUNT), 시도 횟수 (COUNT), 측정 라운드 (ROUNDS) must all
    # stay distinct — never merged into one generic "sample size".
    assert len(types) == 3
    assert any("라운드" in t for t in types)


def test_sample_size_field_example_values_come_from_real_rows():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    fields = detect_sample_size_fields(parsed.column_semantics, parsed.rows)
    rounds_field = next(f for f in fields if "라운드" in f.sample_size_type)
    assert rounds_field.example_values == ["73", "87"]  # 김수지, 배소현


# ---------------------------------------------------------------
# TEST 9 — RTP detection
# ---------------------------------------------------------------


def test_rtp_present_for_confirmed_approach_metric():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    status, example = detect_rtp_status(parsed.column_semantics, parsed.rows)
    assert status == "RTP_PRESENT"
    assert example == "-0.0465"


def test_rtp_absent_when_no_rtp_column():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>평균 티샷 거리</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="270.5"><td>1</td><td>테스트</td><td>270.5</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    status, example = detect_rtp_status(parsed.column_semantics, parsed.rows)
    assert status == "RTP_ABSENT"
    assert example is None


def test_rtp_never_treated_as_sg():
    """Documentation-as-test: RTP detection only checks for the
    literal 'RTP' label — it must never fire on an SG-labeled column,
    proving RTP and SG are never conflated."""
    assert classify_column_kind("SG Total") != "RTP"
    assert classify_column_kind("RTP") == "RTP"


# ---------------------------------------------------------------
# TEST 11/12/13/14/15 — data quality checks
# ---------------------------------------------------------------


def test_no_anomalies_in_the_clean_confirmed_fixture():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    analysis = analyze_response(parsed)
    assert analysis.data_quality.any_flagged is False


def test_missing_player_code_and_name_detected():
    html = """
    <table><tbody>
      <tr data-rank="1" data-record="50.0"><td>1</td><td>익명</td><td>50.0</td></tr>
    </tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.missing_player_code == 1
    assert analysis.data_quality.missing_player_name == 1


def test_percentage_out_of_range_flagged():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>성공률(%)</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="145.0"><td>1</td><td>테스트</td><td>145.0</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.percentage_out_of_range == 1


def test_successes_exceed_attempts_flagged():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>성공률(%)</th><th>성공 횟수</th><th>시도 횟수</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="90.0" data-record1="50" data-record2="10">
      <td>1</td><td>테스트</td><td>90.0</td><td>50</td><td>10</td>
    </tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.successes_exceed_attempts == 1


def test_negative_and_non_positive_rounds_flagged():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>측정 라운드</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="-5"><td>1</td><td>테스트</td><td>-5</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.negative_counts == 1
    assert analysis.data_quality.non_positive_measured_rounds == 1


def test_non_numeric_value_in_a_numeric_field_flagged():
    html = """
    <table><thead><tr><th>순위</th><th>선수명</th><th>측정 라운드</th></tr></thead>
    <tbody><tr data-rank="1" data-name="테스트" data-record="많음"><td>1</td><td>테스트</td><td>많음</td></tr></tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.non_numeric_numeric_fields == 1


def test_duplicate_player_code_row_flagged():
    html = """
    <table><tbody>
      <tr data-playercode="123" data-name="선수1" data-record="50"><td>1</td><td>선수1</td><td>50</td></tr>
      <tr data-playercode="123" data-name="선수1" data-record="60"><td>2</td><td>선수1</td><td>60</td></tr>
    </tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.duplicate_player_rows == 1


def test_duplicate_rank_flagged():
    html = """
    <table><tbody>
      <tr data-rank="1" data-playercode="1" data-name="A" data-record="50"><td>1</td><td>A</td><td>50</td></tr>
      <tr data-rank="1" data-playercode="2" data-name="B" data-record="60"><td>1</td><td>B</td><td>60</td></tr>
    </tbody></table>
    """
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    assert analysis.data_quality.duplicate_ranks == 1


# ---------------------------------------------------------------
# TEST 18/19 — historical season classification, no PIT-safe promotion
# ---------------------------------------------------------------


def test_pit_status_is_always_the_unverified_constant():
    parsed = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    analysis = analyze_response(parsed)
    assert analysis.pit_status == "PIT_UNVERIFIED"
    assert PIT_STATUS == "PIT_UNVERIFIED"


def test_no_function_in_this_module_can_emit_a_pit_safe_string():
    """Static/structural check: the literal string "PIT_SAFE" (or
    anything implying safety) must not appear anywhere in this
    module's source — a compile-time-adjacent guard against silently
    adding a PIT-safe promotion path later."""
    import inspect

    import klpga.discovery.response_schema as module

    source = inspect.getsource(module)
    assert "PIT_SAFE" not in source
    assert "PIT-SAFE" not in source


def test_historical_availability_confirmed_when_values_genuinely_differ():
    current = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    historical_html = _read("loadLocationRecord_approach_020104_sample.html").replace("70.49", "65.00")
    historical = parse_record_response(historical_html)
    assert classify_historical_availability(current, historical) == "HISTORICAL_SEASON_AVAILABLE"


def test_historical_availability_unknown_when_response_is_identical():
    """An endpoint that silently echoes the current season for any
    season value must NOT be misclassified as historically available —
    identical values classify as UNKNOWN, not HISTORICAL_SEASON_AVAILABLE."""
    current = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    historical = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    assert classify_historical_availability(current, historical) == "UNKNOWN"


def test_historical_availability_current_only_when_historical_response_is_empty():
    current = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    historical = parse_record_response("<table><tbody></tbody></table>")
    assert classify_historical_availability(current, historical) == "CURRENT_ONLY"
