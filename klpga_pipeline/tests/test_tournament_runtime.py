from types import SimpleNamespace

import pytest

from klpga.tournament_official_ingest import (
    OfficialRoundSnapshot,
)

import neo_tournament_runtime as runtime


def player(
    pid,
    *,
    status="ACTIVE",
    holes=18,
):
    return SimpleNamespace(
        player_id=pid,
        status=status,
        holes_completed=holes,
    )


def snap(players, game="GAME", rnd=2):
    return OfficialRoundSnapshot(
        game_code=game,
        round_number=rnd,
        players=tuple(players),
    )


def state(
    *,
    game="GAME",
    final=3,
    current=2,
    stage="R2_LIVE",
    model=False,
):
    return runtime.RuntimeState(
        game_code=game,
        final_round_number=final,
        current_round_number=current,
        validated_stage=stage,
        model_ready=model,
    )


def test_active_18h_is_complete():
    assert (
        runtime.player_is_unfinished(
            player("1", holes=18)
        )
        is False
    )


def test_incomplete_is_unfinished_even_with_holes():
    assert runtime.player_is_unfinished(
        player(
            "1",
            status="INCOMPLETE",
            holes=1,
        )
    )


def test_unknown_holes_fail_closed_as_unfinished():
    assert runtime.player_is_unfinished(
        player("1", holes=None)
    )


@pytest.mark.parametrize(
    "status",
    ["WD", "DQ", "DNS"],
)
def test_terminal_status_not_unfinished(status):
    assert (
        runtime.player_is_unfinished(
            player(
                "1",
                status=status,
                holes=None,
            )
        )
        is False
    )


def test_r2_live_remains_factual_only():
    decision = runtime.classify_live_snapshot(
        state(model=True),
        snap([
            player("1", holes=18),
            player(
                "2",
                status="INCOMPLETE",
                holes=7,
            ),
        ]),
    )

    assert decision.observed_stage == "R2_LIVE"
    assert decision.publication_mode == "FACTUAL_LIVE"
    assert decision.should_publish_factual is True
    assert decision.should_publish_model is False
    assert decision.should_disable_cycle is False
    assert decision.unfinished_count == 1


def test_r2_completion_stops_at_cut_gate():
    decision = runtime.classify_live_snapshot(
        state(),
        snap([
            player("1", holes=18),
            player("2", holes=18),
            player(
                "3",
                status="WD",
                holes=None,
            ),
        ]),
    )

    assert decision.observed_stage == "R2_COMPLETE"
    assert decision.next_gate == "CUT_CONFIRMATION"
    assert decision.should_publish_factual is True
    assert decision.should_publish_model is False
    assert decision.should_disable_cycle is True
    assert decision.unfinished_count == 0


def test_model_ready_never_bypasses_r2_cut_gate():
    decision = runtime.classify_live_snapshot(
        state(model=True),
        snap([
            player("1"),
            player("2"),
        ]),
    )

    assert decision.observed_stage == "R2_COMPLETE"
    assert decision.next_gate == "CUT_CONFIRMATION"
    assert decision.should_publish_model is False


def test_game_mismatch_blocks():
    with pytest.raises(runtime.RuntimeBlocked):
        runtime.classify_live_snapshot(
            state(game="RIGHT"),
            snap(
                [player("1")],
                game="WRONG",
            ),
        )


def test_round_mismatch_blocks():
    with pytest.raises(runtime.RuntimeBlocked):
        runtime.classify_live_snapshot(
            state(current=2),
            snap(
                [player("1")],
                rnd=1,
            ),
        )


def test_non_live_stage_not_accepted_by_runtime():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        raise AssertionError(
            "fetch must not occur"
        )

    with pytest.raises(runtime.RuntimeBlocked):
        runtime.run_once(
            state(stage="R2_COMPLETE"),
            cache_dir=None,
            fetcher=fetcher,
        )

    assert calls == []


def test_generic_future_game_fetch_arguments():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)

        return snap(
            [player("1", holes=7)],
            game=kwargs["game_code"],
            rnd=kwargs["round_number"],
        )

    _, decision = runtime.run_once(
        state(
            game="FUTURE-2030",
            final=4,
            current=3,
            stage="NEXT_ROUND_LIVE",
        ),
        cache_dir="CACHE",
        fetcher=fetcher,
    )

    assert calls == [{
        "game_code": "FUTURE-2030",
        "round_number": 3,
        "cache_dir": "CACHE",
    }]

    assert decision.should_publish_model is False


def test_no_tournament_specific_identifiers():
    source = runtime.Path(
        runtime.__file__
    ).read_text(encoding="utf-8")

    for forbidden in (
        "2026120001",
        "OK????",
        "KG ????",
        "99_ok_open",
        "96_ok_open",
    ):
        assert forbidden not in source
