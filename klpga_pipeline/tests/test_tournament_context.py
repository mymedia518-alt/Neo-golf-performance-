from __future__ import annotations

import pytest

from klpga.tournament_context import (
    TournamentContext,
    TournamentContextError,
    load_active_tournament_context,
    resolve_context,
)

OK_OPEN_IDENTITY = {
    "game_code": "2026120001",
    "tournament_name": "OK저축은행 읏맨 오픈",
    "season": 2026,
    "start_date": "2026-09-04",
    "end_date": "2026-09-06",
    "final_round_number": 3,
    "current_round_number": 2,
}
OK_OPEN_REGISTRY_ENTRY = {
    "url_base": "/tournaments/2026/ok-savings-bank-open/",
    "stage_state_filename": "OK_OPEN_STAGE_STATE.json",
    "stage_order": ["pre", "r1", "r2", "r3", "final"],
    "venue": "포천아도니스",
    "holes": 54,
    "format": "스트로크 플레이",
}


def test_load_active_tournament_context_matches_ok_open_real_values():
    # The exact values every currently-hardcoded constant used to carry
    # (tournament_state.py's OK_DISPLAY_NAME/OK_BASE/OK_DATE_RANGE/
    # OK_GAME_CODE/STAGE_ORDER) -- proves the real config/active_
    # tournament.json + TOURNAMENT_SITE_REGISTRY.json on disk resolve to
    # the identical, previously-hardcoded identity.
    ctx = load_active_tournament_context()
    assert ctx.game_code == "2026120001"
    assert ctx.tournament_name == "OK저축은행 읏맨 오픈"
    assert ctx.url_base == "/tournaments/2026/ok-savings-bank-open/"
    assert ctx.display_date_range == "2026.09.04 — 09.06"
    assert ctx.stage_order == ("pre", "r1", "r2", "r3", "final")
    assert ctx.stage_labels == {"pre": "사전 분석 PRE", "r1": "R1", "r2": "R2", "r3": "R3", "final": "FINAL"}


def test_resolve_context_is_pure_and_reproduces_ok_open():
    ctx = resolve_context(OK_OPEN_IDENTITY, {"2026120001": OK_OPEN_REGISTRY_ENTRY})
    assert ctx == TournamentContext(
        game_code="2026120001",
        tournament_name="OK저축은행 읏맨 오픈",
        season=2026,
        start_date="2026-09-04",
        end_date="2026-09-06",
        final_round_number=3,
        current_round_number=2,
        url_base="/tournaments/2026/ok-savings-bank-open/",
        stage_state_filename="OK_OPEN_STAGE_STATE.json",
        stage_order=("pre", "r1", "r2", "r3", "final"),
        venue="포천아도니스",
        holes=54,
        format="스트로크 플레이",
    )


def test_dry_run_against_a_different_past_game_code_never_touches_ok_open_data():
    # NEO TOURNAMENT PIPELINE validation #3: dry-run resolution against a
    # completely different, past tournament's game_code -- proves the
    # resolver is generic, not secretly keyed to "2026120001" anywhere in
    # its own logic. Uses the real KG Ladies Open identity (2026, 4
    # rounds) as the synthetic "past tournament" input.
    kg_identity = {
        "game_code": "2026080001",
        "tournament_name": "제15회 KG 레이디스 오픈",
        "season": 2026,
        "start_date": "2026-08-27",
        "end_date": "2026-08-30",
        "final_round_number": 4,
        "current_round_number": 4,
    }
    kg_registry_entry = {
        "url_base": "/tournaments/2026/kg-ladies-open/",
        "stage_state_filename": "KG_LADIES_OPEN_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
    ctx = resolve_context(kg_identity, {"2026080001": kg_registry_entry})
    assert ctx.game_code == "2026080001"
    assert ctx.tournament_name == "제15회 KG 레이디스 오픈"
    assert ctx.url_base == "/tournaments/2026/kg-ladies-open/"
    assert ctx.display_date_range == "2026.08.27 — 08.30"
    # Never a trace of the other tournament's identity leaking through.
    assert "2026120001" not in (ctx.game_code, ctx.tournament_name, ctx.url_base)
    assert "OK" not in ctx.tournament_name


def test_four_round_tournament_stage_labels_generalize_beyond_ok_open_three_rounds():
    # NEO TOURNAMENT PIPELINE validation #4: a 4-round tournament's
    # stage_labels are computed by the exact same generic rule as OK
    # Open's 3-round stage_labels (mechanical: pre/rN/final), not a
    # 3-round-only formula.
    identity = {
        "game_code": "9999999999",
        "tournament_name": "TEST 4-ROUND EVENT",
        "season": 2099,
        "start_date": "2099-01-01",
        "end_date": "2099-01-04",
        "final_round_number": 4,
        "current_round_number": 1,
    }
    registry_entry = {
        "url_base": "/tournaments/2099/test-4-round-event/",
        "stage_state_filename": "TEST_4R_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "r4", "final"],
    }
    ctx = resolve_context(identity, {"9999999999": registry_entry})
    assert ctx.stage_labels == {
        "pre": "사전 분석 PRE",
        "r1": "R1",
        "r2": "R2",
        "r3": "R3",
        "r4": "R4",
        "final": "FINAL",
    }


def test_missing_registry_entry_fails_closed_never_guesses():
    with pytest.raises(TournamentContextError, match="no TOURNAMENT_SITE_REGISTRY.json entry"):
        resolve_context(OK_OPEN_IDENTITY, {})
