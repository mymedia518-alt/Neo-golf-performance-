"""Tests for klpga.discovery.request_log — including the redaction
guarantee itself (TEST 20)."""
from __future__ import annotations

import json

from klpga.discovery.request_log import RequestLogEntry, build_log_entry, to_log_csv, to_log_jsonl


def _entry(**overrides):
    defaults = dict(
        timestamp="2026-08-26T00:00:00Z",
        endpoint="https://klpga.co.kr/load/record/loadLocationRecord",
        method="POST",
        season="2025",
        menu1="Approach",
        menu2="Approach01",
        menu3="020104",
        canonical_identity="Approach::Approach01::020104",
        http_status=200,
        response_size=1234,
        parse_status="CONFIRMED",
    )
    defaults.update(overrides)
    return build_log_entry(**defaults)


def test_build_log_entry_round_trips_all_fields():
    e = _entry()
    assert e.season == "2025"
    assert e.canonical_identity == "Approach::Approach01::020104"
    assert e.http_status == 200


def test_menu3_is_nullable_in_the_log():
    e = _entry(menu1="Sg", menu2="Total", menu3=None, canonical_identity="Sg::Total")
    assert e.menu3 is None


# ---------------------------------------------------------------
# TEST 20 — request log redaction
# ---------------------------------------------------------------


def test_log_entry_schema_has_no_field_capable_of_holding_secrets():
    """Structural redaction: the dataclass itself has no headers/
    cookie/auth field — not a filter that could be forgotten, an
    absence enforced by the schema."""
    field_names = {f for f in RequestLogEntry.__dataclass_fields__}
    forbidden_substrings = ["header", "cookie", "auth", "token", "secret", "session"]
    for name in field_names:
        lowered = name.lower()
        assert not any(bad in lowered for bad in forbidden_substrings), f"log field {name!r} looks like it could hold a secret"


def test_jsonl_output_never_contains_forbidden_keys():
    e = _entry()
    jsonl = to_log_jsonl([e])
    parsed = json.loads(jsonl)
    forbidden = {"headers", "cookies", "authorization", "token", "session_id"}
    assert forbidden.isdisjoint(parsed.keys())


def test_csv_output_never_contains_forbidden_columns():
    e = _entry()
    csv_text = to_log_csv([e])
    header_row = csv_text.splitlines()[0]
    for bad in ("header", "cookie", "auth", "token", "secret"):
        assert bad not in header_row.lower()


def test_to_log_jsonl_one_line_per_entry():
    entries = [_entry(), _entry(menu3="020105", canonical_identity="Approach::Approach01::020105")]
    jsonl = to_log_jsonl(entries)
    lines = jsonl.splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["menu3"] == "020104"
    assert json.loads(lines[1])["menu3"] == "020105"


def test_to_log_csv_serializes_none_menu3_as_empty_not_the_word_none():
    e = _entry(menu1="Sg", menu2="Total", menu3=None, canonical_identity="Sg::Total")
    csv_text = to_log_csv([e])
    rows = csv_text.splitlines()
    assert "None" not in rows[1]
