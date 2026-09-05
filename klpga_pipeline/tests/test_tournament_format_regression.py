import pytest

from klpga.tournament_engine import (
    RoundFacts,
    Stage,
    TournamentFacts,
    determine_stage,
    publication_allowed,
)


def rf(n, expected=60, official=60, incomplete=0, unresolved=0):
    return RoundFacts(
        round_number=n,
        expected_players=expected,
        official_players=official,
        incomplete_players=incomplete,
        unresolved_players=unresolved,
    )


def test_54_hole_event_round3_is_final_live():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(
            rf(1, 120, 120, 0),
            rf(2, 118, 118, 0),
            rf(3, 60, 60, 10),
        ),
        cut_validated=True,
        final_round_number=3,
    )

    assert determine_stage(facts) == Stage.FINAL_LIVE


def test_54_hole_event_round3_complete_is_final_complete():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(
            rf(1, 120, 120, 0),
            rf(2, 118, 118, 0),
            rf(3, 60, 60, 0),
        ),
        cut_validated=True,
        final_round_number=3,
    )

    assert determine_stage(facts) == Stage.FINAL_COMPLETE


def test_72_hole_event_round3_is_not_final():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(
            rf(1),
            rf(2),
            rf(3, incomplete=12),
        ),
        cut_validated=True,
        final_round_number=4,
    )

    assert determine_stage(facts) == Stage.R3_LIVE


def test_72_hole_event_round3_complete_is_r3_complete():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(rf(1), rf(2), rf(3)),
        cut_validated=True,
        final_round_number=4,
    )

    assert determine_stage(facts) == Stage.R3_COMPLETE


def test_72_hole_round4_is_final_live():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(rf(1), rf(2), rf(3), rf(4, incomplete=7)),
        cut_validated=True,
        final_round_number=4,
    )

    assert determine_stage(facts) == Stage.FINAL_LIVE


def test_72_hole_round4_complete_is_final_complete():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(rf(1), rf(2), rf(3), rf(4)),
        cut_validated=True,
        final_round_number=4,
    )

    assert determine_stage(facts) == Stage.FINAL_COMPLETE


def test_cut_must_be_confirmed_before_forecast_publication():
    assert not publication_allowed(
        Stage.R2_COMPLETE,
        "WIN_PROBABILITY",
    )

    assert publication_allowed(
        Stage.CUT_CONFIRMED,
        "WIN_PROBABILITY",
    )

    assert not publication_allowed(
        Stage.R2_COMPLETE,
        "NEXT_ROUND_FORECAST",
    )

    assert publication_allowed(
        Stage.CUT_CONFIRMED,
        "NEXT_ROUND_FORECAST",
    )


def test_incomplete_round_cannot_be_complete():
    r = rf(
        2,
        expected=118,
        official=118,
        incomplete=2,
    )

    assert r.validated
    assert not r.complete


def test_unresolved_player_blocks_round_validation():
    r = rf(
        2,
        expected=118,
        official=118,
        incomplete=0,
        unresolved=1,
    )

    assert not r.validated
    assert not r.complete


@pytest.mark.parametrize(
    "final_round_number",
    [3, 4],
)
def test_same_engine_supports_both_formats(final_round_number):
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(rf(1), rf(2)),
        cut_validated=True,
        final_round_number=final_round_number,
    )

    assert determine_stage(facts) == Stage.CUT_CONFIRMED
