"""P0 STALE-DATA INCIDENT -- unit tests for klpga.website_v2.freshness_gate,
the pure decision logic behind the hard release gate."""
import datetime

import pytest

from klpga.website_v2.freshness_gate import (
    STALE_NOTICE_MARKER,
    STALE_THRESHOLD_SECONDS,
    FreshnessGateError,
    assert_completed_round_has_no_incomplete_holes,
    assert_no_silent_staleness,
    is_snapshot_stale,
    snapshot_age_seconds,
)

NOW = datetime.datetime(2026, 9, 4, 11, 9, 19, tzinfo=datetime.timezone.utc)


def test_snapshot_age_seconds_matches_the_real_incident():
    # the actual incident: collected_at 07:43:00Z, "now" 11:09:19Z
    age = snapshot_age_seconds("2026-09-04T07:43:00Z", NOW)
    assert age == pytest.approx(3 * 3600 + 26 * 60 + 19, abs=1)


def test_fresh_snapshot_is_not_stale():
    recent = (NOW - datetime.timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    assert is_snapshot_stale(recent, NOW) is False


def test_snapshot_older_than_threshold_is_stale():
    old = (NOW - datetime.timedelta(seconds=STALE_THRESHOLD_SECONDS + 1)).isoformat().replace("+00:00", "Z")
    assert is_snapshot_stale(old, NOW) is True


def test_snapshot_exactly_at_threshold_is_not_yet_stale():
    edge = (NOW - datetime.timedelta(seconds=STALE_THRESHOLD_SECONDS)).isoformat().replace("+00:00", "Z")
    assert is_snapshot_stale(edge, NOW) is False


def test_no_collected_at_is_never_stale():
    assert is_snapshot_stale(None, NOW) is False
    assert is_snapshot_stale("", NOW) is False


def test_real_incident_timestamp_is_stale_under_the_default_threshold():
    assert is_snapshot_stale("2026-09-04T07:43:00Z", NOW) is True


def test_assert_no_silent_staleness_passes_when_fresh_even_without_marker():
    recent = (NOW - datetime.timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    assert_no_silent_staleness("<p>no marker here</p>", collected_at_iso=recent, now=NOW, label="t")


def test_assert_no_silent_staleness_raises_when_stale_and_marker_missing():
    with pytest.raises(FreshnessGateError):
        assert_no_silent_staleness("<p>라이브 업데이트 주기 30분</p>", collected_at_iso="2026-09-04T07:43:00Z", now=NOW, label="t")


def test_assert_no_silent_staleness_passes_when_stale_but_marker_present():
    html = f"<p>{STALE_NOTICE_MARKER}</p>"
    assert_no_silent_staleness(html, collected_at_iso="2026-09-04T07:43:00Z", now=NOW, label="t")


def test_assert_completed_round_ok_when_not_marked_complete():
    incomplete_rows = [{"player_name": "A", "holes_completed": "9", "status": None}]
    assert_completed_round_has_no_incomplete_holes(incomplete_rows, round_complete=False, label="t")


def test_assert_completed_round_raises_when_complete_but_holes_incomplete():
    rows = [{"player_name": "A", "holes_completed": "9", "status": None}, {"player_name": "B", "holes_completed": "18", "status": None}]
    with pytest.raises(FreshnessGateError) as exc:
        assert_completed_round_has_no_incomplete_holes(rows, round_complete=True, label="t")
    assert "A" in str(exc.value)
    assert "B" not in str(exc.value)


def test_assert_completed_round_passes_when_all_18_or_wd_dq_cut():
    rows = [
        {"player_name": "A", "holes_completed": "18", "status": None},
        {"player_name": "B", "holes_completed": "F", "status": None},
        {"player_name": "C", "holes_completed": "9", "status": "WD"},
        {"player_name": "D", "holes_completed": "5", "status": "DQ"},
        {"player_name": "E", "holes_completed": None, "status": "CUT"},
    ]
    assert_completed_round_has_no_incomplete_holes(rows, round_complete=True, label="t")


def test_assert_completed_round_passes_when_incomplete_status_present():
    # status="INCOMPLETE" (klpga.parsers.leaderboard_parser's real, only
    # ever observed did-not-complete signal -- the raw "999" sentinel) is
    # exempt from the 18-hole requirement exactly like WD/DQ/CUT. Without
    # this, klpga.neo_win.r1_readiness.assess_r1 correctly closing a
    # round that exempted an INCOMPLETE player would still fail THIS
    # gate and HARD_STOP the promotion right after -- a real bug found
    # against the real R1 snapshot (박결/김아현), not a hypothetical.
    rows = [
        {"player_name": "A", "holes_completed": "18", "status": None},
        {"player_name": "박결", "holes_completed": "10", "status": "INCOMPLETE"},
    ]
    assert_completed_round_has_no_incomplete_holes(rows, round_complete=True, label="t")
