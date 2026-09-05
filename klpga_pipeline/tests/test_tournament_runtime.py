import pytest

from klpga.tournament_engine import RoundFacts, Stage
from klpga.tournament_runtime import (
    CutValidation,
    PlayerEventFact,
    TournamentConfig,
    resolve_runtime_stage,
    validate_cut,
)


def config(final_round_number=4):
    return TournamentConfig(
        game_code="TEST-GAME",
        tournament_name="TEST EVENT",
        final_round_number=final_round_number,
        cut_after_round=2,
    )


def test_config_is_data_not_hardcoded():
    a = TournamentConfig("A", "EVENT A", 4, 2)
    b = TournamentConfig("B", "EVENT B", 4, 2)

    assert a.game_code != b.game_code
    assert a.tournament_name != b.tournament_name


def test_invalid_cut_round_rejected():
    with pytest.raises(ValueError):
        TournamentConfig("A", "EVENT", 4, 4)


def test_cut_blocked_until_round_complete():
    result = validate_cut(
        [
            PlayerEventFact("1", "", True),
            PlayerEventFact("2", "", False),
        ],
        round_complete=False,
    )

    assert not result.validated


def test_cut_requires_explicit_fact():
    result = validate_cut(
        [
            PlayerEventFact("1", "", True),
            PlayerEventFact("2", "", None),
        ],
        round_complete=True,
    )

    assert not result.validated
    assert result.unresolved == ("2",)


def test_wd_dq_dns_are_not_fake_cut_failures():
    result = validate_cut(
        [
            PlayerEventFact("1", "", True),
            PlayerEventFact("2", "", False),
            PlayerEventFact("3", "WD", None),
            PlayerEventFact("4", "DQ", None),
            PlayerEventFact("5", "DNS", None),
        ],
        round_complete=True,
    )

    assert result.validated
    assert result.advancing == ("1",)
    assert result.eliminated == ("2",)
    assert result.exempt_status == ("3", "4", "5")


def test_cut_validation_advances_generic_state():
    cfg = config()

    cut = validate_cut(
        [
            PlayerEventFact("1", "", True),
            PlayerEventFact("2", "", False),
        ],
        round_complete=True,
    )

    stage = resolve_runtime_stage(
        cfg,
        entry_validated=True,
        pre_validated=True,
        rounds=(
            RoundFacts(1, 2, 2, 0),
            RoundFacts(2, 2, 2, 0),
        ),
        cut_validation=cut,
    )

    assert stage == Stage.CUT_CONFIRMED


def test_same_runtime_supports_different_tournaments():
    rounds = (
        RoundFacts(1, 2, 2, 0),
        RoundFacts(2, 2, 2, 0),
    )

    cut = CutValidation(
        validated=True,
        advancing=("1",),
        eliminated=("2",),
        exempt_status=(),
        unresolved=(),
    )

    for cfg in (
        TournamentConfig("GAME-A", "EVENT A", 4, 2),
        TournamentConfig("GAME-B", "EVENT B", 4, 2),
        TournamentConfig("GAME-C", "EVENT C", 3, 2),
    ):
        assert resolve_runtime_stage(
            cfg,
            entry_validated=True,
            pre_validated=True,
            rounds=rounds,
            cut_validation=cut,
        ) == Stage.CUT_CONFIRMED
