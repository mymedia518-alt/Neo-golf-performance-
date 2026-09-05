from pathlib import Path

import pytest

from klpga.tournament_official_ingest import (
    OfficialPlayerRound,
    OfficialRoundSnapshot,
)
from klpga.tournament_publication_runner import (
    PublicationRunBlocked,
    PublicationRunRequest,
    run_factual_publication,
)


def snap(game="FUTURE-GAME", rnd=4):
    return OfficialRoundSnapshot(
        game_code=game,
        round_number=rnd,
        players=(
            OfficialPlayerRound(
                player_id="1001",
                player_name="Future Player",
                rank_display="1",
                status="ACTIVE",
                raw_inghole=18,
                holes_completed=18,
                holes_completed_display="18H",
                starting_tee_assumed=False,
                today_under_par_display="-5",
                total_under_par_display="-12",
            ),
            OfficialPlayerRound(
                player_id="1002",
                player_name="Future Player 2",
                rank_display="2",
                status="ACTIVE",
                raw_inghole=17,
                holes_completed=17,
                holes_completed_display="17H",
                starting_tee_assumed=False,
                today_under_par_display="-3",
                total_under_par_display="-10",
            ),
        ),
    )


def req(tmp_path, game="FUTURE-GAME", rnd=4, promote=False):
    return PublicationRunRequest(
        tournament_name="Future Tournament",
        game_code=game,
        round_number=rnd,
        frozen_root=tmp_path / "frozen",
        candidate_root=tmp_path / "candidate",
        target_path=tmp_path / "live" / "index.html",
        promote=promote,
    )


def test_dry_run_never_touches_live(tmp_path):
    target = tmp_path / "live" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text("OLD LIVE", encoding="utf-8")
    before = target.read_bytes()

    result = run_factual_publication(
        req(tmp_path, promote=False),
        snap(),
        collected_at="2040-01-01T00:00:00Z",
    )

    assert result.promoted is False
    assert result.promotion is None
    assert result.candidate_path.exists()
    assert target.read_bytes() == before


def test_explicit_promotion_changes_live(tmp_path):
    result = run_factual_publication(
        req(tmp_path, promote=True),
        snap(),
        collected_at="2040-01-01T00:00:00Z",
    )

    assert result.promoted is True
    assert result.promotion is not None

    target = tmp_path / "live" / "index.html"

    assert target.exists()
    assert target.read_bytes() == result.candidate_path.read_bytes()
    assert result.promotion.after_sha256 == result.candidate_sha256


def test_game_code_mismatch_blocks_before_live(tmp_path):
    target = tmp_path / "live" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text("CURRENT LIVE", encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(PublicationRunBlocked):
        run_factual_publication(
            req(tmp_path, game="RIGHT", promote=True),
            snap(game="WRONG"),
            collected_at="2040-01-01T00:00:00Z",
        )

    assert target.read_bytes() == before


def test_round_mismatch_blocks_before_live(tmp_path):
    target = tmp_path / "live" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text("CURRENT LIVE", encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(PublicationRunBlocked):
        run_factual_publication(
            req(tmp_path, rnd=4, promote=True),
            snap(rnd=3),
            collected_at="2040-01-01T00:00:00Z",
        )

    assert target.read_bytes() == before


def test_arbitrary_game_and_round_need_no_code_change(tmp_path):
    result = run_factual_publication(
        req(
            tmp_path,
            game="YEAR-LATER-UNKNOWN-EVENT",
            rnd=5,
            promote=False,
        ),
        snap(
            game="YEAR-LATER-UNKNOWN-EVENT",
            rnd=5,
        ),
        collected_at="2045-01-01T00:00:00Z",
    )

    assert result.game_code == "YEAR-LATER-UNKNOWN-EVENT"
    assert result.round_number == 5
    assert result.promoted is False


def test_model_fields_absent_from_candidate(tmp_path):
    result = run_factual_publication(
        req(tmp_path, promote=False),
        snap(),
        collected_at="2040-01-01T00:00:00Z",
    )

    html = result.candidate_path.read_text(encoding="utf-8")

    assert "win_pct" not in html
    assert "top5_pct" not in html
    assert "top10_pct" not in html
    assert "top20_pct" not in html
    assert 'content="factual-only"' in html
