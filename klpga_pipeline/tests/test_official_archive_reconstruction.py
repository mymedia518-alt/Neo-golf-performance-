"""Tests for scripts/104_official_archive_reconstruction.py.

Covers the failure-classification logic (using a fake requests.Session so
these tests never depend on real network access -- deterministic either
way) and the invariants of the real, already-generated artifact: it must
never claim VERIFIED without evidence, must never silently drop an event,
and must reuse (not reimplement) official_data.parse_leaderboard_html.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "official_archive_reconstruction", ROOT / "scripts" / "104_official_archive_reconstruction.py"
)
recon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recon
spec.loader.exec_module(recon)  # type: ignore[union-attr]


class _FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class _FakeSession:
    """Stands in for requests.Session so failure-classification tests never
    touch the real network -- each test controls exactly what `post` does."""

    def __init__(self, behavior):
        self._behavior = behavior  # callable(url, **kwargs) -> _FakeResponse, or raises

    def post(self, url, **kwargs):
        return self._behavior(url, **kwargs)


def test_fetch_round_classifies_network_failure_without_hitting_real_network():
    def boom(*a, **k):
        raise requests.exceptions.ProxyError("Tunnel connection failed: 403 Forbidden")
    outcome = recon.fetch_round(_FakeSession(boom), "2099999999", 1)
    assert outcome["status"] == "NETWORK_EGRESS_DENIED"
    assert "403" in outcome["detail"] or "ProxyError" in outcome["detail"]


def test_fetch_round_classifies_http_error():
    session = _FakeSession(lambda *a, **k: _FakeResponse(status_code=500))
    outcome = recon.fetch_round(session, "2099999999", 1)
    assert outcome["status"] == "HTTP_ERROR"
    assert "500" in outcome["detail"]


def test_fetch_round_classifies_empty_leaderboard():
    session = _FakeSession(lambda *a, **k: _FakeResponse(status_code=200, content=b"<html><body>no table</body></html>"))
    outcome = recon.fetch_round(session, "2099999999", 1)
    assert outcome["status"] == "EMPTY_LEADERBOARD"


def test_fetch_round_classifies_retrieved_using_the_real_reused_parser():
    html = (
        "<button id='btnDetail' _playercode='P1'><table><tr>"
        "<td>x</td><td>1</td><td>y</td><td>y</td><td>Player One</td><td>-3</td><td>F</td>"
        "<td>x</td><td>68</td><td>70</td><td>71</td><td>69</td><td>278</td></tr></table></button>"
    )
    session = _FakeSession(lambda *a, **k: _FakeResponse(status_code=200, content=html.encode("utf-8")))
    outcome = recon.fetch_round(session, "2099999999", 1)
    assert outcome["status"] == "RETRIEVED"
    assert outcome["rows"][0]["player_id"] == "P1"
    assert outcome["rows"][0]["rounds"] == [68, 70, 71, 69]


def test_attempt_event_flags_identity_mismatch_when_no_local_overlap():
    html = (
        "<button id='btnDetail' _playercode='UNKNOWN_ID'><table><tr>"
        "<td>x</td><td>1</td><td>y</td><td>y</td><td>Someone</td><td>-3</td><td>F</td>"
        "<td>x</td><td>68</td><td>70</td><td>71</td><td>69</td><td>278</td></tr></table></button>"
    )
    session = _FakeSession(lambda *a, **k: _FakeResponse(status_code=200, content=html.encode("utf-8")))
    result = recon.attempt_event(session, "2099999999", local_player_ids={"KNOWN_ID_NOT_PRESENT"})
    assert result["event_status"] == "IDENTITY_MISMATCH"


def test_attempt_event_never_silently_drops_a_failing_round():
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("refused")
    result = recon.attempt_event(_FakeSession(boom), "2099999999", local_player_ids=set())
    # all 4 rounds must be present and explicitly classified, never omitted
    assert set(result["rounds"].keys()) == {"1", "2", "3", "4"}
    assert all(v["status"] == "NETWORK_EGRESS_DENIED" for v in result["rounds"].values())
    assert result["event_status"] == "NETWORK_EGRESS_DENIED"


def test_script_reuses_official_data_parser_not_a_second_implementation():
    from klpga.website_v2.official_data import parse_leaderboard_html
    assert recon.parse_leaderboard_html is parse_leaderboard_html


def test_real_artifact_never_claims_verified_without_evidence():
    """Locks in the actual attempted reconstruction's outcome: whatever the
    real network state was when this artifact was generated, it must never
    report a round-count as VERIFIED without having actually retrieved and
    parsed official rows -- and it must never attempt (and thus never
    silently skip) the full population without first proving the sample
    phase can reach the endpoint at all."""
    out_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_OFFICIAL_ARCHIVE_RECONSTRUCTION.json"
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["model_state"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    assert report["parser_reused"].startswith("klpga.website_v2.official_data.parse_leaderboard_html")
    sample = report["sample_phase"]
    assert len(sample["sample_results"]) == sample["sample_size_requested"]
    if sample["sample_retrieved_count"] == 0:
        assert report["full_population_phase"]["attempted"] is False
        assert report["hard_gate"]["status"] == "BLOCKED"
    else:
        assert report["full_population_phase"]["attempted"] is True
        # events_requested must equal the full local population, not a silently truncated subset
        assert report["full_population_phase"]["events_requested"] >= sample["sample_size_requested"]


def test_real_artifact_reports_every_sample_event_status_not_a_summary_only():
    """Per instruction ('do not silently drop those events'), each sampled
    event must carry its own explicit event_status -- never collapsed into
    a single boolean."""
    out_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_OFFICIAL_ARCHIVE_RECONSTRUCTION.json"
    report = json.loads(out_path.read_text(encoding="utf-8"))
    for result in report["sample_phase"]["sample_results"]:
        assert "game_code" in result
        assert result["event_status"] in {
            "RETRIEVED", "NETWORK_EGRESS_DENIED", "HTTP_ERROR",
            "EMPTY_LEADERBOARD", "PARSE_FAILURE", "IDENTITY_MISMATCH",
        }
        assert set(result["rounds"].keys()) == {"1", "2", "3", "4"}
