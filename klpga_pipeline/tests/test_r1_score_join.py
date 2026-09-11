"""Task I (fix/kb-r2-official-cut-gate-20260911): REAL LIVE EXECUTION
CORRECTION -- R1 score join into the R2 collection/freeze.

A real `python scripts/112_kb_r2_active_cycle.py --live` run against
gameCode=2026090003 progressed all the way through official CUT
evidence, 양서후 WD reconciliation, starting-tee handling, and R2
completion -- successfully CREATED the R2 snapshot and the POST-R2
forecast -- then HARD_STOPped at the probability gate:

    R2_SNAPSHOT = CREATED
    POST_R2_FORECAST = CREATED
    R2_PUBLICATION_READY = false
    HARD_STOP: population mismatch: 71 missing, 0 unexpected extra

The generated forecast's own missing_players evidence showed, for every
one of those 71 players: profile=true, r1_score=false, r2_score=true.
"records": [] and "win_probability_sum_pct": 0.

ROOT CAUSE: scripts/112's _collect_live_r2() hardcodes
`"r1_score_to_par": None` on every row it builds -- R1's real score was
never joined into R2 collection at all. klpga.neo_win.post_r2_forecast.
run_post_r2_forecast reads r1_score_to_par directly off the FROZEN r2
freeze record (never re-derives it) and excludes any row where it is
None from `sim_inputs`/`records` -- exactly reproducing the real
HARD_STOP's own evidence: real r2_score present, real profile present,
r1_score permanently absent, so every ACTIVE row was excluded and the
forecast came back empty.

FIX: scripts/112's new _load_r1_score_by_player + _apply_r1_scores join
the real R1 to-par score from the SAME real, committed R1 evidence
artifact expected_player_ids is already derived from (NEO_KB_..._R1_
OFFICIAL_RESULT_EVIDENCE_V1.json's players[].toPar) onto every row by
player_id, wired into run_cycle() right after the existing R1-guaranteed-
18-holes cumulative-completion join (e902bd5) -- never re-derived via
arithmetic, never re-fetched live.

This test proves the FULL real chain end-to-end: real R1 evidence
artifact -> _load_r1_score_by_player -> _apply_r1_scores (joins r1_score
onto synthetic-but-real-identity R2 rows) -> a real (tmp_path-isolated,
never production content/website_v2/) R2 freeze -> post_r2_forecast.
run_post_r2_forecast -> non-empty simulation records -> win_probability_
sum_pct ~= 100 -> r2_probability_gate.validate_probability_gate passes.

Isolation: this test NEVER writes to the real content/website_v2/ tree
-- klpga.tournament_context.CONTENT_DIR is monkeypatched to a pytest
tmp_path, the exact same established pattern tests/test_r2_house.py
already uses for every real-freeze-writing test in this repo."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from klpga.neo_win.post_r2_forecast import run_post_r2_forecast
from klpga.neo_win.r2_freeze import build_r2_frozen_evidence, write_r2_freeze_immutable
from klpga.neo_win.r2_probability_gate import validate_probability_gate
from klpga.tournament_context import TournamentContext

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
REAL_R1_EVIDENCE_PATH = Path(__file__).resolve().parents[1] / "content" / "website_v2" / "NEO_KB_2026090003_R1_OFFICIAL_RESULT_EVIDENCE_V1.json"
GAME_CODE = "TESTR1JOIN"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_r1_score_join_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


@pytest.fixture()
def context(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    monkeypatch.setattr(tc, "CONTENT_DIR", tmp_path / "content")
    (tmp_path / "content").mkdir()
    return TournamentContext(
        game_code=GAME_CODE, tournament_name="TEST R1 JOIN OPEN", season=2026,
        start_date="2026-09-09", end_date="2026-09-12", final_round_number=3,
        current_round_number=2, url_base=f"/tournaments/2026/{GAME_CODE}/",
        stage_state_filename=f"{GAME_CODE}_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )


# ---------------------------------------------------------------------
# Unit-level: _load_r1_score_by_player / _apply_r1_scores against the
# real, committed R1 evidence artifact directly.
# ---------------------------------------------------------------------

def test_load_r1_score_by_player_reads_real_to_par_from_real_artifact(module):
    assert REAL_R1_EVIDENCE_PATH.is_file()
    r1_evidence = json.loads(REAL_R1_EVIDENCE_PATH.read_text(encoding="utf-8"))
    scores = module._load_r1_score_by_player(r1_evidence)
    # Real first entry confirmed during investigation: playerCode 10586, toPar "-5".
    assert scores["10586"] == -5.0
    assert len(scores) == len(r1_evidence["players"])


def test_apply_r1_scores_overwrites_the_hardcoded_none_placeholder(module):
    rows = [{"player_id": "10586", "player_name": "홍진영2", "status": "ACTIVE", "r1_score_to_par": None, "r2_score_to_par": -2.0}]
    reconciled = module._apply_r1_scores(rows, {"10586": -5.0})
    assert reconciled[0]["r1_score_to_par"] == -5.0


def test_apply_r1_scores_leaves_row_untouched_when_no_real_score_available(module):
    rows = [{"player_id": "99999999", "player_name": "선수Z", "status": "ACTIVE", "r1_score_to_par": None, "r2_score_to_par": -1.0}]
    reconciled = module._apply_r1_scores(rows, {"10586": -5.0})
    assert reconciled[0]["r1_score_to_par"] is None  # never fabricated


# ---------------------------------------------------------------------
# Full real chain: real R1 evidence -> r1 join -> r2 join -> non-empty
# simulation records -> probability sum ~= 100% -> population match ->
# probability gate passes.
# ---------------------------------------------------------------------

def test_full_chain_real_r1_join_plus_r2_reaches_a_passing_probability_gate(module, context, tmp_path):
    assert REAL_R1_EVIDENCE_PATH.is_file()
    real_r1_evidence = json.loads(REAL_R1_EVIDENCE_PATH.read_text(encoding="utf-8"))
    r1_score_by_player = module._load_r1_score_by_player(real_r1_evidence)

    # A small real-identity subset of the real R1-forward population --
    # real player_id/name/r1-to-par taken directly from the real
    # artifact (never fabricated identities), standing in for the R2
    # collection's own rows (this test's job is to prove the JOIN and
    # DOWNSTREAM WIRING, not to re-collect a live R2 leaderboard).
    real_players = real_r1_evidence["players"][:6]
    active_player_ids = {str(p["playerCode"]) for p in real_players}

    rows = [
        {
            "player_id": str(p["playerCode"]), "player_name": p["name"], "status": "ACTIVE",
            "r1_score_to_par": None,  # exactly _collect_live_r2's real hardcoded placeholder, pre-fix
            "r2_score_to_par": -1.0,  # a real-shaped R2-round-to-par value
        }
        for p in real_players
    ]

    # Prove the placeholder is real (this is what the live HARD_STOP's
    # own evidence showed: r1_score=false for every affected player).
    assert all(r["r1_score_to_par"] is None for r in rows)

    joined_rows = module._apply_r1_scores(rows, r1_score_by_player)
    assert all(r["r1_score_to_par"] is not None for r in joined_rows)
    for row in joined_rows:
        assert row["r1_score_to_par"] == r1_score_by_player[row["player_id"]]

    # Build a real (tmp_path-isolated) R2 freeze from the joined rows --
    # this is the SAME build_r2_frozen_evidence call scripts/112's own
    # _publish_and_close makes, just against an isolated test context.
    pre = tmp_path / "PRE_FREEZE.json"
    pre.write_text(json.dumps({"schema": "pre"}), encoding="utf-8")
    r1_freeze = tmp_path / "R1_FREEZE.json"
    r1_freeze.write_text(json.dumps({"schema": "r1"}), encoding="utf-8")

    evidence = build_r2_frozen_evidence(
        context=context, official_source_identity="test-real-r1-join", official_source_url=None,
        collection_timestamp="2026-09-11T00:00:00Z", raw_official_response=b"{}",
        records=joined_rows, expected_field_count=len(joined_rows),
        status_counts={"ACTIVE": len(joined_rows), "CUT": 0, "WD": 0, "DQ": 0, "DNS": 0},
        cut_wd_dq_evidence=[], pre_freeze_path=pre, r1_freeze_path=r1_freeze, repo_root=tmp_path, build_id="TEST",
    )
    write_r2_freeze_immutable(context, evidence)

    pre_performance_snapshot = {
        "profiles": [
            {"player_id": str(p["playerCode"]), "windows": {"recent5": {"components": {"total": {"mean": 0.2}}}}}
            for p in real_players
        ]
    }

    forecast = run_post_r2_forecast(
        context, pre_performance_snapshot=pre_performance_snapshot, repo_root=tmp_path,
        build_id="TEST", seed=20260911, n_simulations=2000,
    )

    # Non-empty simulation records -- the real HARD_STOP's own
    # "records": [] is what this fix must never reproduce.
    assert forecast["missing_players"] == []
    assert len(forecast["records"]) == len(active_player_ids)
    observed_ids = {r["player_id"] for r in forecast["records"]}
    assert observed_ids == active_player_ids  # expected eligible population matches probability population

    # Probability sum approximately 100% (each simulation has exactly
    # one winner, split on ties -- see simulate_post_round2).
    assert abs(forecast["win_probability_sum_pct"] - 100.0) < 1.0

    # The actual gate that produced the real HARD_STOP -- must now pass.
    validate_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids=active_player_ids)
