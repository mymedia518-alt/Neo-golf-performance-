"""Tests for klpga.collectors.player_team_sponsor's batch collection
logic (roster validation + per-player OK/FETCH_FAILURE/
IDENTITY_FAILURE/PARSE_FAILURE outcomes), against a FakeClient.

The HTML bodies used here are SYNTHETIC control-flow fixtures for
made-up player codes/names — they reuse the one confirmed real
structure (<label>소속</label> followed by a <h5> value, see
tests/fixtures/player_profile_sample_11134.html) but are not claimed
to be real KLPGA markup for these specific (fake) players. Real-data
coverage lives in tests/test_player_profile_parser.py."""
from __future__ import annotations

import pytest

from klpga.collectors.player_team_sponsor import (
    RosterIntegrityError,
    collect_one,
    collect_roster,
    validate_roster,
)


def _profile_html(name: str, sponsor: str | None) -> str:
    sponsor_html = f"<h5 class='text-white'>{sponsor}</h5>" if sponsor is not None else "<h5 class='text-white'></h5>"
    return (
        f"<html><body>"
        f"<h1>{name}</h1>"
        f"<div class='col-3'><label class='text-neongreen'>소속</label>{sponsor_html}</div>"
        f"</body></html>"
    )


def _no_sponsor_field_html(name: str) -> str:
    """A page that fetched fine and carries the player's name, but does
    NOT carry a 소속 label at all — a structural mismatch, must be
    PARSE_FAILURE, never confused with 'no sponsor'."""
    return f"<html><body><h1>{name}</h1><p>no profile fields at all</p></body></html>"


class FakeClient:
    def __init__(self, responses_by_code: dict[str, tuple[int, str]], error_codes: frozenset = frozenset()):
        self.responses_by_code = responses_by_code
        self.error_codes = error_codes
        self.calls: list[str] = []

    def get_text_with_status(self, url, params=None, **kwargs):
        code = (params or {}).get("playerCode")
        self.calls.append(code)
        if code in self.error_codes:
            raise ConnectionError(f"simulated real network failure for playerCode={code}")
        return self.responses_by_code[code]


def test_collect_one_ok_with_sponsor_value():
    client = FakeClient({"1001": (200, _profile_html("가나다", "테스트건설"))})
    result = collect_one(client, "1001", "가나다")
    assert result.outcome == "OK"
    assert result.team_or_sponsor == "테스트건설"


def test_collect_one_ok_with_blank_sponsor_is_empty_string_not_a_failure():
    client = FakeClient({"1002": (200, _profile_html("라마바", None))})
    result = collect_one(client, "1002", "라마바")
    assert result.outcome == "OK"
    assert result.team_or_sponsor == ""


def test_collect_one_fetch_failure_does_not_crash():
    client = FakeClient({}, error_codes=frozenset({"1003"}))
    result = collect_one(client, "1003", "사아자")
    assert result.outcome == "FETCH_FAILURE"
    assert result.team_or_sponsor is None
    assert result.raw_html is None


def test_collect_one_identity_failure_when_name_not_in_page():
    client = FakeClient({"1004": (200, _profile_html("다른이름", "테스트건설"))})
    result = collect_one(client, "1004", "차카타")
    assert result.outcome == "IDENTITY_FAILURE"
    assert result.team_or_sponsor is None
    assert result.raw_html is not None


def test_collect_one_parse_failure_when_label_missing():
    client = FakeClient({"1005": (200, _no_sponsor_field_html("파하거"))})
    result = collect_one(client, "1005", "파하거")
    assert result.outcome == "PARSE_FAILURE"
    assert result.team_or_sponsor is None
    assert result.raw_html is not None


def test_validate_roster_rejects_duplicate_player_code():
    with pytest.raises(RosterIntegrityError):
        validate_roster([("1001", "가"), ("1001", "나")])


def test_validate_roster_rejects_duplicate_player_name():
    with pytest.raises(RosterIntegrityError):
        validate_roster([("1001", "가"), ("1002", "가")])


def test_validate_roster_rejects_kim_na_young_code_mismatch():
    """Documented real historical typo: 11014 instead of the correct
    10114 for 김나영 — this must never pass validation."""
    with pytest.raises(RosterIntegrityError):
        validate_roster([("11014", "김나영")])


def test_validate_roster_accepts_kim_na_young_correct_code():
    validate_roster([("10114", "김나영")])  # must not raise


def test_collect_roster_stops_before_any_network_call_on_integrity_error():
    client = FakeClient({"1001": (200, _profile_html("가", "테스트"))})
    with pytest.raises(RosterIntegrityError):
        collect_roster(client, [("1001", "가"), ("1001", "가")])
    assert client.calls == []


def test_collect_roster_collects_every_player_independently():
    """One player's failure must not abort the rest — all outcomes for
    a full run should be visible in a single pass."""
    client = FakeClient(
        {
            "1001": (200, _profile_html("가", "테스트건설")),
            "1002": (200, _no_sponsor_field_html("나")),
        },
        error_codes=frozenset({"1003"}),
    )
    results = collect_roster(client, [("1001", "가"), ("1002", "나"), ("1003", "다")])
    outcomes = {r.player_code: r.outcome for r in results}
    assert outcomes == {"1001": "OK", "1002": "PARSE_FAILURE", "1003": "FETCH_FAILURE"}
