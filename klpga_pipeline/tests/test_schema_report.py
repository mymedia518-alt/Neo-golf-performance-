"""Tests for the newer klpga.discovery.schema_report outputs added on
top of the sample-based Phase B1 build: KLPGA_RAW_COUNT_METRICS.csv,
KLPGA_RESPONSE_FAILURES.csv, KLPGA_PLAYER_IDENTITY_REPORT.md. Pure
formatting over hand-built records/identity records — no network,
no dependency on the full script pipeline (see
test_klpga_response_schema_sample_script.py for the end-to-end path)."""
from __future__ import annotations

from klpga.discovery.response_schema import PlayerIdentityRecord
from klpga.discovery.schema_report import (
    render_player_identity_report_markdown,
    write_raw_count_metrics_csv,
    write_response_failures_csv,
)


def _record(**overrides):
    defaults = dict(
        identity_key="Approach::Approach01::020104",
        menu1="Approach",
        menu2="Approach01",
        menu3="020104",
        metric_label="그린 적중률",
        parse_status="CONFIRMED",
        raw_pair_status="CONFIRMED_RAW_PAIR",
        raw_pair_numerator_field="record1",
        raw_pair_denominator_field="record2",
        rate_validation={"max_abs_difference": 0.01, "checked_rows": 2},
        sample_size_fields=[{"sample_size_type": "측정 라운드", "field_name": "record3", "example_values": ["73"]}],
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------
# KLPGA_RAW_COUNT_METRICS.csv
# ---------------------------------------------------------------


def test_raw_count_metrics_csv_includes_confirmed_and_partial_pairs():
    records = [
        _record(),
        _record(identity_key="X::Y", raw_pair_status="PARTIAL_RAW_PAIR", raw_pair_denominator_field=None),
        _record(identity_key="Z::W", raw_pair_status="COUNT_ONLY", raw_pair_numerator_field=None, raw_pair_denominator_field=None),
    ]
    csv_text = write_raw_count_metrics_csv(records)
    assert "Approach::Approach01::020104" in csv_text
    assert "X::Y" in csv_text
    assert "Z::W" in csv_text


def test_raw_count_metrics_csv_excludes_rate_only_and_not_applicable():
    records = [
        _record(identity_key="RateOnly", raw_pair_status="RATE_ONLY"),
        _record(identity_key="NA", raw_pair_status="NOT_APPLICABLE"),
        _record(identity_key="Unk", raw_pair_status="UNKNOWN"),
    ]
    csv_text = write_raw_count_metrics_csv(records)
    lines = csv_text.strip().splitlines()
    assert len(lines) == 1  # header only


def test_raw_count_metrics_csv_carries_the_rate_validation_delta():
    csv_text = write_raw_count_metrics_csv([_record()])
    assert "0.01" in csv_text


# ---------------------------------------------------------------
# KLPGA_RESPONSE_FAILURES.csv
# ---------------------------------------------------------------


def test_response_failures_csv_includes_failed_ambiguous_and_empty():
    records = [
        _record(identity_key="F", parse_status="FAILED"),
        _record(identity_key="A", parse_status="AMBIGUOUS"),
        _record(identity_key="E", parse_status="EMPTY"),
        _record(identity_key="OK", parse_status="CONFIRMED"),
    ]
    csv_text = write_response_failures_csv(records)
    assert "F" in csv_text and "A" in csv_text and "E" in csv_text
    lines = csv_text.strip().splitlines()
    assert len(lines) == 4  # header + 3 failures, CONFIRMED excluded


def test_response_failures_csv_carries_optional_notes():
    records = [_record(identity_key="F", parse_status="FAILED")]
    csv_text = write_response_failures_csv(records, notes_by_key={"F": ["HTML parse error: boom"]})
    assert "HTML parse error: boom" in csv_text


def test_response_failures_csv_empty_when_nothing_failed():
    csv_text = write_response_failures_csv([_record()])
    lines = csv_text.strip().splitlines()
    assert len(lines) == 1


# ---------------------------------------------------------------
# KLPGA_PLAYER_IDENTITY_REPORT.md
# ---------------------------------------------------------------


def test_player_identity_report_renders_confirmed_status():
    records = [
        PlayerIdentityRecord(player_name="김수지", codes_by_metric={"a": "1", "b": "1"}, consistent=True),
    ]
    report = render_player_identity_report_markdown("CONFIRMED", records)
    assert "`CONFIRMED`" in report
    assert "김수지" in report


def test_player_identity_report_flags_inconsistent_players_as_no():
    records = [
        PlayerIdentityRecord(player_name="배소현", codes_by_metric={"a": "1", "b": "2"}, consistent=False),
    ]
    report = render_player_identity_report_markdown("PARTIAL", records)
    assert "`PARTIAL`" in report
    assert "NO" in report


def test_player_identity_report_separates_single_metric_players():
    records = [
        PlayerIdentityRecord(player_name="임희정", codes_by_metric={"a": "1"}, consistent=True),
    ]
    report = render_player_identity_report_markdown("NOT_AVAILABLE", records)
    assert "`NOT_AVAILABLE`" in report
    assert "Single-metric players (1" in report
    assert "Cross-checkable players (0" in report
