from klpga.tournament_engine import (
    RoundFacts,
    Stage,
    TournamentFacts,
    determine_stage,
    publication_allowed,
)


def rf(n, expected, official, incomplete=0, unresolved=0):
    return RoundFacts(n, expected, official, incomplete, unresolved)


def test_no_data_is_discovered():
    assert determine_stage(TournamentFacts()) == Stage.DISCOVERED


def test_entry_and_pre():
    assert determine_stage(
        TournamentFacts(entry_validated=True)
    ) == Stage.ENTRY_READY

    assert determine_stage(
        TournamentFacts(entry_validated=True, pre_validated=True)
    ) == Stage.PRE_READY


def test_r1_live_and_complete():
    assert determine_stage(
        TournamentFacts(rounds=(rf(1,120,120,3),))
    ) == Stage.R1_LIVE

    assert determine_stage(
        TournamentFacts(rounds=(rf(1,120,120,0),))
    ) == Stage.R1_COMPLETE


def test_r2_live_does_not_publish_cut():
    facts=TournamentFacts(
        rounds=(
            rf(1,120,120,0),
            rf(2,118,118,2),
        )
    )
    stage=determine_stage(facts)
    assert stage == Stage.R2_LIVE
    assert not publication_allowed(stage,"CUT")
    assert not publication_allowed(stage,"WIN_PROBABILITY")


def test_r2_complete_requires_cut_validation_for_cut_publish():
    facts=TournamentFacts(
        rounds=(
            rf(1,120,120,0),
            rf(2,118,118,0),
        )
    )
    stage=determine_stage(facts)
    assert stage == Stage.R2_COMPLETE
    assert not publication_allowed(stage,"CUT")


def test_cut_confirmed_unlocks_next_round_model():
    facts=TournamentFacts(
        rounds=(
            rf(1,120,120,0),
            rf(2,118,118,0),
        ),
        cut_validated=True,
    )
    stage=determine_stage(facts)
    assert stage == Stage.CUT_CONFIRMED
    assert publication_allowed(stage,"CUT")
    assert publication_allowed(stage,"NEXT_ROUND_FORECAST")
    assert publication_allowed(stage,"WIN_PROBABILITY")


def test_unresolved_player_blocks_round_completion():
    facts=TournamentFacts(
        rounds=(rf(2,118,118,0,1),)
    )
    assert determine_stage(facts) == Stage.DISCOVERED


def test_final_complete():
    facts=TournamentFacts(
        rounds=(
            rf(1,120,120,0),
            rf(2,118,118,0),
            rf(3,64,64,0),
            rf(4,64,64,0),
        ),
        cut_validated=True,
    )
    assert determine_stage(facts) == Stage.FINAL_COMPLETE


def test_three_round_tournament_supported_without_code_change():
    facts=TournamentFacts(
        rounds=(
            rf(1,120,120,0),
            rf(2,60,60,0),
            rf(3,60,60,0),
        ),
        cut_validated=True,
        final_round_number=3,
    )
    assert determine_stage(facts) == Stage.FINAL_COMPLETE
