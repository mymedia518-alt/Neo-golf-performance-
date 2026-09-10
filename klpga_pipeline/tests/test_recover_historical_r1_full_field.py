"""scripts/106_recover_historical_r1_full_field.py -- regression tests.

Uses the real, already-proven round_leaderboard_sample.html fixture
(byte-faithful to a confirmed live capture, includes a real CUT-status
row) through the real parser, with only the network fetch itself
injected/faked -- so these tests exercise the actual recovery,
archiving, fail-closed, resumability, and audit logic, not a mock of
it. No network access is used or required.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "round_leaderboard_sample.html"

sys.path.insert(0, str(ROOT / "src"))
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "recover_historical_r1_full_field", ROOT / "scripts" / "106_recover_historical_r1_full_field.py"
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)  # type: ignore[union-attr]

SAMPLE_HTML = FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    """Every test gets its own content/evidence/output paths so nothing
    touches the real repo files or a previous test's state."""
    content = tmp_path / "content"
    content.mkdir()
    evidence = tmp_path / "evidence"

    grouping = {
        "records": [
            {"game_code": "G1", "player_count": 3, "field_provenance": "VERIFIED_R1_STARTER"},
            {"game_code": "G2", "player_count": 3, "field_provenance": "VERIFIED_R1_STARTER"},
        ]
    }
    (content / "HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json").write_text(json.dumps(grouping), encoding="utf-8")

    truth_warehouse = {
        "records": [
            {"game_code": "G1", "player_id": "11134", "tournament_start_date": "2024-01-01", "outcome": {"made_cut": True}},
            {"game_code": "G1", "player_id": "20099", "tournament_start_date": "2024-01-01", "outcome": {"made_cut": True}},
            {"game_code": "G1", "player_id": "30055", "tournament_start_date": "2024-01-01", "outcome": {"made_cut": False}},
            {"game_code": "G2", "player_id": "11134", "tournament_start_date": "2024-02-01", "outcome": {"made_cut": True}},
        ]
    }
    (content / "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json").write_text(json.dumps(truth_warehouse), encoding="utf-8")

    monkeypatch.setattr(mod, "CONTENT", content)
    monkeypatch.setattr(mod, "EVIDENCE_DIR", evidence)
    monkeypatch.setattr(mod, "OUTPUT_PATH", content / "NEO_HISTORICAL_R1_FULL_FIELD_V1.json")
    monkeypatch.setattr(mod, "AUDIT_PATH", content / "NEO_HISTORICAL_R1_FULL_FIELD_V1_AUDIT.json")
    monkeypatch.setattr(mod, "GROUPING_EVIDENCE_PATH", content / "HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json")
    monkeypatch.setattr(mod, "TRUTH_WAREHOUSE_PATH", content / "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    yield


def test_recover_one_happy_path_parses_real_fixture():
    rec = mod.recover_one(
        "G1", fetch=lambda gc: SAMPLE_HTML,
        expected_size=3, event_date="2024-01-01",
        parse_fn=parse_round_leaderboard_html,
    )
    assert rec["status"] == "OK"
    assert rec["player_row_count"] == 3
    assert rec["duplicate_player_code_count"] == 0
    codes = {p["player_code"] for p in rec["players"]}
    assert "11134" in codes
    # the real fixture includes a genuine CUT-status row -- prove it survives
    statuses = {p["r1_status"] for p in rec["players"]}
    assert "CUT" in statuses


def test_archived_evidence_is_persisted_and_content_addressed():
    mod.recover_one("G1", fetch=lambda gc: SAMPLE_HTML, expected_size=3, event_date=None, parse_fn=parse_round_leaderboard_html)
    files = list(mod.EVIDENCE_DIR.glob("G1_r1_*.html.gz"))
    assert len(files) == 1
    import gzip
    assert gzip.open(files[0], "rb").read().decode("utf-8") == SAMPLE_HTML


def test_fails_closed_on_http_error():
    def boom(gc):
        raise RuntimeError("connection refused")
    rec = mod.recover_one("G1", fetch=boom, expected_size=3, event_date=None, parse_fn=parse_round_leaderboard_html)
    assert rec["status"] == "FAILED"
    assert "HTTP_ERROR" in rec["error"]


def test_fails_closed_on_empty_response():
    rec = mod.recover_one("G1", fetch=lambda gc: "", expected_size=3, event_date=None, parse_fn=parse_round_leaderboard_html)
    assert rec["status"] == "FAILED"
    assert rec["error"] == "EMPTY_RESPONSE"


def test_fails_closed_on_empty_parsed_result():
    rec = mod.recover_one("G1", fetch=lambda gc: "<html><body>no table here</body></html>", expected_size=3, event_date=None, parse_fn=parse_round_leaderboard_html)
    assert rec["status"] == "FAILED"
    assert rec["error"] == "EMPTY_RESULT"


def test_fails_closed_on_duplicate_player_code():
    def fake_parse(html, game_code=None, round_number=None):
        row = parse_round_leaderboard_html(SAMPLE_HTML, game_code=game_code, round_number=round_number)[0]
        return [row, row]  # duplicate the same player_code
    rec = mod.recover_one("G1", fetch=lambda gc: SAMPLE_HTML, expected_size=3, event_date=None, parse_fn=fake_parse)
    assert rec["status"] == "FAILED"
    assert rec["error"] == "DUPLICATE_PLAYER_CODE"


def test_fails_closed_on_impossible_row_count():
    # real fixture has 3 rows; declare an expected field size wildly larger
    rec = mod.recover_one("G1", fetch=lambda gc: SAMPLE_HTML, expected_size=120, event_date=None, parse_fn=parse_round_leaderboard_html)
    assert rec["status"] == "FAILED"
    assert "IMPOSSIBLE_ROW_COUNT" in rec["error"]


def test_never_fabricates_players_on_any_failure_path():
    for rec in (
        mod.recover_one("G1", fetch=lambda gc: (_ for _ in ()).throw(RuntimeError("x")), expected_size=3, event_date=None, parse_fn=parse_round_leaderboard_html),
        mod.recover_one("G1", fetch=lambda gc: "", expected_size=3, event_date=None, parse_fn=parse_round_leaderboard_html),
    ):
        assert "players" not in rec


def test_run_recovery_is_resumable_and_skips_already_ok_tournaments(monkeypatch):
    calls = []

    def fetch(gc):
        calls.append(gc)
        return SAMPLE_HTML

    mod.run_recovery(fetch, parse_round_leaderboard_html)
    assert calls == ["G1", "G2"]

    calls.clear()
    result2 = mod.run_recovery(fetch, parse_round_leaderboard_html)
    assert calls == []  # nothing re-fetched -- both already recovered
    assert all(r["status"] == "OK" for r in result2["records"])


def test_run_recovery_resumes_after_a_failure_without_losing_prior_success():
    call_count = {"n": 0}

    def flaky_fetch(gc):
        call_count["n"] += 1
        if gc == "G2" and call_count["n"] <= 1:
            raise RuntimeError("simulated network drop")
        return SAMPLE_HTML

    result1 = mod.run_recovery(lambda gc: SAMPLE_HTML if gc == "G1" else flaky_fetch(gc), parse_round_leaderboard_html)
    statuses = {r["game_code"]: r["status"] for r in result1["records"]}
    assert statuses["G1"] == "OK"
    assert statuses["G2"] == "FAILED"

    result2 = mod.run_recovery(lambda gc: SAMPLE_HTML, parse_round_leaderboard_html)
    statuses2 = {r["game_code"]: r["status"] for r in result2["records"]}
    assert statuses2["G1"] == "OK"
    assert statuses2["G2"] == "OK"  # recovered on retry, G1 was not re-fetched


def test_build_audit_computes_real_cut_coverage_numbers():
    full_field = mod.run_recovery(lambda gc: SAMPLE_HTML, parse_round_leaderboard_html)
    audit = mod.build_audit(full_field)
    assert audit["events_expected"] == 2
    assert audit["events_recovered"] == 2
    assert audit["events_failed"] == 0
    # G1's truth-warehouse fixture declares 1 cut-survivor + 2 cut-missers,
    # all three of whom appear in the real fixture's 3 parsed rows.
    assert audit["cut_survivor_coverage"]["total"] >= 1
    assert audit["cut_misser_coverage"]["total"] >= 1
    assert audit["cut_misser_coverage"]["covered"] >= 1  # the whole point: no longer near-zero


def test_final_status_line_pass_partial_fail():
    all_ok = {"records": [{"status": "OK"}, {"status": "OK"}]}
    assert mod.final_status_line(all_ok) == "R1_FULL_FIELD_RECOVERY_PASS"

    mixed = {"records": [{"status": "OK"}, {"status": "FAILED"}]}
    assert mod.final_status_line(mixed) == "R1_FULL_FIELD_RECOVERY_PARTIAL"

    all_failed = {"records": [{"status": "FAILED"}, {"status": "FAILED"}]}
    assert mod.final_status_line(all_failed) == "R1_FULL_FIELD_RECOVERY_FAIL"


def test_output_never_written_by_importing_this_module():
    """Guard against accidental import-time side effects (e.g. main()
    running at module scope) -- importing must never touch the real repo."""
    real_output = ROOT / "content" / "website_v2" / "NEO_HISTORICAL_R1_FULL_FIELD_V1.json"
    assert not real_output.exists()
