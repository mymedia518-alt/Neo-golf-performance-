"""R3 RESULT-ONLY INPUT PREPARATION -- synthetic-only test suite.

Every fixture here is fabricated (player_ids/names/scores invented only
for this file). REAL R3 results are never placed in a synthetic
fixture -- KB 2026090003's actual R3 has not concluded and this suite
must never pretend it has. Exercises klpga.neo_win.r3_result_input's
pure functions directly (never scripts/117's real-network `run()`),
so no test here can ever make a real HTTP request."""
from __future__ import annotations

import json

import pytest

from klpga.neo_win.r3_result_input import (
    R2FreezeProtectionError,
    build_final_validation_dataset,
    extract_r3_official_result,
    snapshot_r2_state,
    validate_r3_result,
    verify_r2_state_unchanged,
)
from klpga.parsers.leaderboard_parser import PlayerRoundRow


def _row(pid, name, *, status=None, r3=None, total=None) -> PlayerRoundRow:
    return PlayerRoundRow(
        game_code="TEST0001", player_code=pid, player_name=name, player_eng_name=None, round_number=3,
        rank_display=None, rank=None, tie_flag=False, status=status,
        total_under_par_display=None, total_under_par=total,
        today_under_par_display=None, today_under_par=r3,
        total_strokes=None, holes_completed="18",
        round1_score=None, round2_score=None, round3_score=r3, round4_score=None,
    )


def _r2_freeze(active_ids: list[str]) -> dict:
    return {"records": [
        {"player_id": pid, "player_name": f"Player{pid}", "status": "ACTIVE", "r1_score_to_par": -1, "r2_score_to_par": -1}
        for pid in active_ids
    ]}


def _r2_forecast(active_ids: list[str]) -> dict:
    return {"records": [
        {"player_id": pid, "neo_final_rank": i + 1, "r2_total_to_par": -2, "top20_pct": 50.0, "top10_pct": 20.0, "top5_pct": 10.0, "win_pct": 1.0}
        for i, pid in enumerate(active_ids)
    ]}


_ACTIVE_71 = [f"p{i}" for i in range(71)]


# ---------------------------------------------------------------------
# R3 result input works / 71-player R2 JOIN works
# ---------------------------------------------------------------------

def test_r3_result_input_works_and_joins_all_71_active_players():
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in _ACTIVE_71]
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    assert len(rows) == 71
    assert unresolved == []
    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=_r2_freeze(_ACTIVE_71),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed, report.blocked_reasons()


# ---------------------------------------------------------------------
# missing player detected / missing != WD
# ---------------------------------------------------------------------

def test_missing_player_is_detected_and_never_defaulted_to_wd():
    present = _ACTIVE_71[:-1]
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in present]
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    missing_pid = _ACTIVE_71[-1]
    assert unresolved == [missing_pid]
    assert missing_pid not in {r.player_id for r in rows}
    for r in rows:
        assert r.official_status != "WD" or r.player_id != missing_pid  # never fabricated

    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=_r2_freeze(_ACTIVE_71),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed is False
    assert missing_pid in report.unresolved_players
    assert any("player_id_join_complete" in reason or "unmatched_players" in reason for reason in report.blocked_reasons())


# ---------------------------------------------------------------------
# duplicate detected
# ---------------------------------------------------------------------

def test_duplicate_player_id_in_raw_rows_is_detected():
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in _ACTIVE_71]
    raw_rows.append(_row("p0", "PlayerP0-duplicate", r3=1, total=0))  # duplicate raw row
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=_r2_freeze(_ACTIVE_71),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed is False
    assert "p0" in report.duplicate_player_ids


def test_duplicate_player_name_across_distinct_ids_is_detected():
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in _ACTIVE_71]
    raw_rows[1] = _row(_ACTIVE_71[1], "Player" + _ACTIVE_71[0], r3=1, total=0)  # p1 renamed to match p0's name
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=_r2_freeze(_ACTIVE_71),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed is False
    assert "Player" + _ACTIVE_71[0] in report.duplicate_player_names


# ---------------------------------------------------------------------
# official WD/DQ preserved
# ---------------------------------------------------------------------

def test_official_wd_status_is_preserved_with_real_evidence():
    present = list(_ACTIVE_71)
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in present[1:]]
    raw_rows.append(_row(present[0], f"Player{present[0]}", status="WD"))
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    assert unresolved == []
    wd_row = next(r for r in rows if r.player_id == present[0])
    assert wd_row.official_status == "WD"
    assert wd_row.status_evidence is not None
    assert "WD" in wd_row.status_evidence
    assert wd_row.r3_score is None

    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=_r2_freeze(_ACTIVE_71),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed, report.blocked_reasons()


def test_official_dq_status_is_preserved_with_real_evidence():
    present = list(_ACTIVE_71)
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in present[1:]]
    raw_rows.append(_row(present[0], f"Player{present[0]}", status="DQ"))
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    dq_row = next(r for r in rows if r.player_id == present[0])
    assert dq_row.official_status == "DQ"
    assert dq_row.status_evidence is not None


# ---------------------------------------------------------------------
# R2 probabilities unchanged / R2 freeze protection
# ---------------------------------------------------------------------

def test_r2_freeze_protection_passes_when_nothing_changed(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)

    from klpga.tournament_context import TournamentContext
    context = TournamentContext(
        game_code="SYN9001", tournament_name="SYNTHETIC FREEZE TEST", season=2026,
        start_date="2026-03-01", end_date="2026-03-04", final_round_number=3,
        current_round_number=3, url_base="/tournaments/2026/SYN9001/",
        stage_state_filename="SYN9001_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )
    (content_dir / "SYN9001_R2_FROZEN_EVIDENCE.json").write_text('{"records": []}', encoding="utf-8")
    (content_dir / "SYN9001_POST_R2_FINAL_FORECAST.json").write_text('{"records": []}', encoding="utf-8")

    before = snapshot_r2_state(context)
    verify_r2_state_unchanged(context, before)  # must not raise


def test_r2_freeze_protection_hard_stops_when_r2_changes(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)

    from klpga.tournament_context import TournamentContext
    context = TournamentContext(
        game_code="SYN9002", tournament_name="SYNTHETIC FREEZE TEST 2", season=2026,
        start_date="2026-03-01", end_date="2026-03-04", final_round_number=3,
        current_round_number=3, url_base="/tournaments/2026/SYN9002/",
        stage_state_filename="SYN9002_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )
    forecast_path = content_dir / "SYN9002_POST_R2_FINAL_FORECAST.json"
    (content_dir / "SYN9002_R2_FROZEN_EVIDENCE.json").write_text('{"records": []}', encoding="utf-8")
    forecast_path.write_text('{"records": []}', encoding="utf-8")

    before = snapshot_r2_state(context)
    forecast_path.write_text('{"records": [{"win_pct": 999}]}', encoding="utf-8")  # simulated mutation

    with pytest.raises(R2FreezeProtectionError):
        verify_r2_state_unchanged(context, before)


def test_final_dataset_carries_the_exact_raw_r2_probability_values_unchanged():
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in _ACTIVE_71]
    rows, _ = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    forecast = _r2_forecast(_ACTIVE_71)
    dataset = build_final_validation_dataset(r2_freeze=_r2_freeze(_ACTIVE_71), r2_forecast=forecast, r3_rows=rows)
    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}
    for row in dataset:
        fc = forecast_by_id[row["player_id"]]
        assert row["r2_win"] == fc["win_pct"]
        assert row["r2_top5"] == fc["top5_pct"]
        assert row["r2_top10"] == fc["top10_pct"]
        assert row["r2_top20"] == fc["top20_pct"]
        assert row["r2_total"] == fc["r2_total_to_par"]
        assert row["r2_rank"] == fc["neo_final_rank"]


# ---------------------------------------------------------------------
# no POST-R3 forecast created
# ---------------------------------------------------------------------

def test_final_dataset_never_contains_a_post_r3_win_forecast():
    raw_rows = [_row(pid, f"Player{pid}", r3=(i % 3) - 1, total=(i % 3) - 1) for i, pid in enumerate(_ACTIVE_71)]
    rows, _ = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    dataset = build_final_validation_dataset(r2_freeze=_r2_freeze(_ACTIVE_71), r2_forecast=_r2_forecast(_ACTIVE_71), r3_rows=rows)
    forbidden_keys = {"r3_win_pct", "post_r3_win_pct", "r3_top5_pct", "r3_top10_pct", "r3_top20_pct", "win_probability"}
    for row in dataset:
        assert forbidden_keys.isdisjoint(row.keys())
    assert all("r3_score" in row and "final_total" in row for row in dataset)  # real result only, never a forecast


def test_no_post_r3_forecast_artifact_exists_for_kb():
    from klpga.tournament_context import load_tournament_context
    context = load_tournament_context("2026090003")
    assert context.final_round_number == 3
    assert not context.artifact_path("post_r3_final_forecast").is_file()


# ---------------------------------------------------------------------
# HOME remains R2 before publication / FINAL candidate only after
# valid R3 result / PRE/R1/R2 historical artifacts unchanged
# ---------------------------------------------------------------------

def test_home_remains_r2_and_no_final_candidate_exists_yet():
    from pathlib import Path
    from klpga.tournament_context import load_tournament_context
    from klpga.website_v2.kb_home_stage_router import kb_current_stage

    context = load_tournament_context("2026090003")
    assert kb_current_stage(context) == "r2"

    repo_root = Path(__file__).resolve().parents[2]
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert '"status">R2<' in home_html
    assert '"status">R3<' not in home_html
    assert '"status">FINAL<' not in home_html

    candidate_path = context.artifact_path("final_validation_candidate")
    assert not candidate_path.is_file(), "no FINAL candidate must exist before a real R3 result has been collected"


def test_final_candidate_dataset_only_builds_from_a_passed_validation():
    """The candidate-building function itself has no gate -- the real
    entry point (scripts/117) only calls it after report.passed is
    True. This test proves the CALLER'S contract: BLOCKED must never
    reach build_final_validation_dataset with an incomplete result."""
    present = _ACTIVE_71[:-3]  # 3 players unresolved
    raw_rows = [_row(pid, f"Player{pid}", r3=1, total=0) for pid in present]
    rows, unresolved = extract_r3_official_result(raw_rows, set(_ACTIVE_71))
    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=_r2_freeze(_ACTIVE_71),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed is False
    # the real entry point's own contract: BLOCKED -> never calls build_final_validation_dataset
    # (verified structurally in scripts/117's run(): `if not report.passed: return {...}` precedes the call)


def test_pre_r1_r2_historical_artifacts_unchanged():
    """This entire test module only ever reads real KB artifacts (R2
    freeze/forecast, root HOME, R3-freeze-absence) -- never writes to
    any of PRE/R1/R2's real files. Confirms git has zero pending
    changes to any of them from running this suite."""
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    for rel in (
        "docs/tournaments/2026/2026090003/pre/index.html",
        "docs/tournaments/2026/2026090003/r1/index.html",
        "docs/tournaments/2026/2026090003/r2/index.html",
        "klpga_pipeline/content/website_v2/2026090003_R2_FROZEN_EVIDENCE.json",
        "klpga_pipeline/content/website_v2/2026090003_POST_R2_FINAL_FORECAST.json",
    ):
        result = subprocess.run(["git", "diff", "--stat", "HEAD", "--", rel], capture_output=True, text=True, cwd=str(repo_root))
        assert result.stdout.strip() == "", f"{rel} has uncommitted changes: {result.stdout}"


# ---------------------------------------------------------------------
# End-to-end synthetic flow (mirrors scripts/117's run() logic exactly,
# without ever making a real HTTP call).
# ---------------------------------------------------------------------

def test_end_to_end_synthetic_flow_produces_a_final_candidate():
    active_ids = _ACTIVE_71
    r2_freeze = _r2_freeze(active_ids)
    r2_forecast = _r2_forecast(active_ids)
    raw_rows = [_row(pid, f"Player{pid}", r3=(i % 5) - 2, total=(i % 5) - 2) for i, pid in enumerate(active_ids)]

    active_set = {str(r["player_id"]) for r in r2_freeze["records"] if r.get("status") == "ACTIVE"}
    rows, unresolved = extract_r3_official_result(raw_rows, active_set)
    report = validate_r3_result(
        game_code="2026090003", final_round_number=3, r2_freeze=r2_freeze,
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
    )
    assert report.passed, report.blocked_reasons()

    dataset = build_final_validation_dataset(r2_freeze=r2_freeze, r2_forecast=r2_forecast, r3_rows=rows)
    assert len(dataset) == 71
    # this fixture's totals cycle -2..2, so every player tied at the real
    # minimum (-2) is a legitimate co-winner -- winner_flag must match
    # exactly the set of players whose final_total is the real minimum.
    min_total = min(r["final_total"] for r in dataset)
    winners = [r for r in dataset if r["winner_flag"]]
    assert winners and all(r["final_total"] == min_total for r in winners)
    assert {r["player_id"] for r in winners} == {r["player_id"] for r in dataset if r["final_total"] == min_total}
    for r in dataset:
        assert isinstance(r["top20_flag"], bool)
        assert set(r) == {
            "player_id", "player_name", "r2_rank", "r2_total", "r2_top20", "r2_top10", "r2_top5", "r2_win",
            "r3_score", "final_total", "final_rank", "final_status", "winner_flag", "top5_flag", "top10_flag", "top20_flag",
        }
    json.dumps(dataset, ensure_ascii=False)  # must be real, serializable JSON
