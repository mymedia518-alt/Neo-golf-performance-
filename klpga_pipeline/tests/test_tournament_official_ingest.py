from types import SimpleNamespace

import pytest

from klpga.tournament_official_ingest import (
    OfficialIngestBlocked,
    reconcile_official_round,
)


def lb(
    pid,
    *,
    status="ACTIVE",
    raw=1,
):
    return SimpleNamespace(
        player_code=pid,
        player_name=f"P{pid}",
        status=status,
        rank_display="1",
        holes_completed=raw,
        today_under_par_display="-1",
        total_under_par_display="-2",
    )


def group(pid):
    return SimpleNamespace(
        player_code=pid,
    )


def resolver(mapping):
    def _resolve(rows, groups):
        return mapping
    return _resolve


def progress(
    completed,
    *,
    assumed=False,
):
    return SimpleNamespace(
        completed=completed,
        display=f"{completed}H",
        assumed_default_start=assumed,
    )


def test_generic_game_code_and_round():
    snap = reconcile_official_round(
        game_code="FUTURE-2040-XYZ",
        round_number=5,
        leaderboard_rows=[lb("1")],
        grouping_rows=[group("1")],
        progress_resolver=resolver({
            "1": progress(7),
        }),
    )

    assert snap.game_code == "FUTURE-2040-XYZ"
    assert snap.round_number == 5
    assert snap.row_count == 1
    assert snap.players[0].holes_completed == 7


def test_missing_grouping_for_normal_player_hard_stops():
    with pytest.raises(OfficialIngestBlocked):
        reconcile_official_round(
            game_code="ANY",
            round_number=2,
            leaderboard_rows=[lb("1")],
            grouping_rows=[group("2")],
            progress_resolver=resolver({}),
        )


def test_incomplete_player_may_have_null_progress():
    snap = reconcile_official_round(
        game_code="ANY",
        round_number=2,
        leaderboard_rows=[
            lb("1", status="INCOMPLETE"),
        ],
        grouping_rows=[group("2")],
        progress_resolver=resolver({}),
    )

    row = snap.players[0]

    assert row.holes_completed is None
    assert row.holes_completed_display is None
    assert row.rank_display is None
    assert row.today_under_par_display is None
    assert row.total_under_par_display is None


def test_assumed_starting_tee_is_never_publishable():
    with pytest.raises(OfficialIngestBlocked):
        reconcile_official_round(
            game_code="ANY",
            round_number=2,
            leaderboard_rows=[lb("1")],
            grouping_rows=[group("1")],
            progress_resolver=resolver({
                "1": progress(
                    7,
                    assumed=True,
                ),
            }),
        )


def test_duplicate_player_identity_hard_stops():
    with pytest.raises(OfficialIngestBlocked):
        reconcile_official_round(
            game_code="ANY",
            round_number=1,
            leaderboard_rows=[
                lb("1"),
                lb("1"),
            ],
            grouping_rows=[group("1")],
            progress_resolver=resolver({}),
        )


def test_zero_leaderboard_rows_hard_stops():
    with pytest.raises(OfficialIngestBlocked):
        reconcile_official_round(
            game_code="ANY",
            round_number=1,
            leaderboard_rows=[],
            grouping_rows=[group("1")],
        )
