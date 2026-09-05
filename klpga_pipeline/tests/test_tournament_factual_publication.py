from pathlib import Path

import pytest

from klpga.tournament_factual_publication import (
    FactualPublicationBlocked,
    build_publication_candidate,
    freeze_factual_snapshot,
    validate_publication_candidate,
    verify_factual_snapshot,
)
from klpga.tournament_official_ingest import (
    OfficialPlayerRound,
    OfficialRoundSnapshot,
)


def snapshot(game="FUTURE-EVENT", rnd=2):
    return OfficialRoundSnapshot(
        game_code=game,
        round_number=rnd,
        players=(
            OfficialPlayerRound(
                player_id="100",
                player_name="Player",
                rank_display="1",
                status="ACTIVE",
                raw_inghole=18,
                holes_completed=18,
                holes_completed_display="18H",
                starting_tee_assumed=False,
                today_under_par_display="-3",
                total_under_par_display="-7",
            ),
        ),
    )


def test_freeze_and_verify(tmp_path):
    ref = freeze_factual_snapshot(
        snapshot(),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )

    payload = verify_factual_snapshot(ref)

    assert payload["game_code"] == "FUTURE-EVENT"
    assert payload["round_number"] == 2
    assert payload["model_data_included"] is False


def test_same_snapshot_is_idempotent(tmp_path):
    a = freeze_factual_snapshot(
        snapshot(),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )
    b = freeze_factual_snapshot(
        snapshot(),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )

    assert a.sha256 == b.sha256
    assert a.path == b.path


def test_tamper_blocks(tmp_path):
    ref = freeze_factual_snapshot(
        snapshot(),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )

    ref.path.write_text("tampered", encoding="utf-8")

    with pytest.raises(FactualPublicationBlocked):
        verify_factual_snapshot(ref)


def test_candidate_is_factual_only(tmp_path):
    ref = freeze_factual_snapshot(
        snapshot("ANY-GAME", 5),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )

    candidate = build_publication_candidate(ref)
    validate_publication_candidate(candidate, ref)

    assert candidate["publish_factual"] is True
    assert candidate["publish_model"] is False


def test_model_cannot_sneak_through_factual_gate(tmp_path):
    ref = freeze_factual_snapshot(
        snapshot(),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )

    candidate = build_publication_candidate(ref)
    candidate["publish_model"] = True

    with pytest.raises(FactualPublicationBlocked):
        validate_publication_candidate(candidate, ref)


def test_no_tournament_specific_assumption(tmp_path):
    ref = freeze_factual_snapshot(
        snapshot("YEAR-LATER-NEW-GAME", 4),
        output_root=tmp_path,
        collected_at="2040-01-01T00:00:00Z",
    )

    candidate = build_publication_candidate(ref)

    assert candidate["game_code"] == "YEAR-LATER-NEW-GAME"
    assert candidate["round_number"] == 4
