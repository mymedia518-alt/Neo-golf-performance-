import pytest

from klpga.tournament_engine import (
    RoundFacts,
    Stage,
    TournamentFacts,
    determine_stage,
)


def complete(number, players):
    return RoundFacts(
        round_number=number,
        expected_players=players,
        official_players=players,
        incomplete_players=0,
    )


def live(number, players):
    return RoundFacts(
        round_number=number,
        expected_players=players,
        official_players=players,
        incomplete_players=1,
    )


def test_54_hole_event_goes_from_cut_to_final():
    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(
            complete(1, 120),
            complete(2, 60),
        ),
        cut_validated=True,
        final_round_number=3,
    )

    assert determine_stage(facts) == Stage.CUT_CONFIRMED

    facts = TournamentFacts(
        entry_validated=True,
        pre_validated=True,
        rounds=(
            complete(1, 120),
            complete(2, 60),
            live(3, 60),
        ),
        cut_validated=True,
        final_round_number=3,
    )

    assert determine_stage(facts) == Stage.FINAL_LIVE


def test_72_hole_event_has_intermediate_round():
    facts = TournamentFacts(
        rounds=(
            complete(1, 120),
            complete(2, 60),
            live(3, 60),
        ),
        cut_validated=True,
        final_round_number=4,
    )

    assert determine_stage(facts) == Stage.NEXT_ROUND_LIVE

    facts = TournamentFacts(
        rounds=(
            complete(1, 120),
            complete(2, 60),
            complete(3, 60),
        ),
        cut_validated=True,
        final_round_number=4,
    )

    assert (
        determine_stage(facts)
        == Stage.NEXT_ROUND_COMPLETE
    )


def test_five_round_event_needs_no_code_change():
    facts = TournamentFacts(
        rounds=(
            complete(1, 100),
            complete(2, 50),
            complete(3, 50),
            live(4, 50),
        ),
        cut_validated=True,
        final_round_number=5,
    )

    assert determine_stage(facts) == Stage.NEXT_ROUND_LIVE


def test_post_evaluation_requires_final_completion():
    facts = TournamentFacts(
        rounds=(
            complete(1, 100),
            complete(2, 50),
        ),
        cut_validated=True,
        final_round_number=3,
        post_evaluated=True,
    )

    with pytest.raises(ValueError):
        determine_stage(facts)


def test_negative_counts_are_rejected():
    with pytest.raises(ValueError):
        RoundFacts(
            round_number=1,
            expected_players=-1,
            official_players=0,
            incomplete_players=0,
        )


def test_duplicate_rounds_are_rejected():
    with pytest.raises(ValueError):
        TournamentFacts(
            rounds=(
                complete(1, 100),
                complete(1, 100),
            ),
            final_round_number=3,
        )
