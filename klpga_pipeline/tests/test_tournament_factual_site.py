from klpga.tournament_factual_publication import (
    build_publication_candidate,
    freeze_factual_snapshot,
)
from klpga.tournament_factual_site import (
    build_factual_site_candidate,
    candidate_sha256,
    validate_factual_html,
    FactualSiteBlocked,
)
from klpga.tournament_official_ingest import (
    OfficialPlayerRound,
    OfficialRoundSnapshot,
)
import pytest


def snap(game="FUTURE-X", rnd=3):
    return OfficialRoundSnapshot(
        game_code=game,
        round_number=rnd,
        players=(
            OfficialPlayerRound(
                player_id="1",
                player_name="??? ??",
                rank_display="1",
                status="ACTIVE",
                raw_inghole=18,
                holes_completed=18,
                holes_completed_display="18H",
                starting_tee_assumed=False,
                today_under_par_display="-4",
                total_under_par_display="-9",
            ),
        ),
    )


def test_generic_candidate_build(tmp_path):
    ref = freeze_factual_snapshot(
        snap("YEAR-2042-EVENT", 5),
        output_root=tmp_path / "frozen",
        collected_at="2042-01-01T00:00:00Z",
    )
    candidate = build_publication_candidate(ref)

    path = build_factual_site_candidate(
        tournament_name="?? ??",
        candidate=candidate,
        ref=ref,
        output_root=tmp_path / "candidate",
    )

    html = path.read_text(encoding="utf-8")
    assert "?? ??" in html
    assert "??? ??" in html
    assert "18H" in html
    assert ref.sha256 in html
    assert len(candidate_sha256(path)) == 64


def test_no_model_fields(tmp_path):
    ref = freeze_factual_snapshot(
        snap(),
        output_root=tmp_path / "frozen",
        collected_at="2040-01-01T00:00:00Z",
    )
    candidate = build_publication_candidate(ref)

    path = build_factual_site_candidate(
        tournament_name="ANY",
        candidate=candidate,
        ref=ref,
        output_root=tmp_path / "candidate",
    )

    html = path.read_text(encoding="utf-8")
    assert "????" not in html
    assert "win_pct" not in html
    assert 'content="factual-only"' in html


def test_tampered_binding_blocks(tmp_path):
    ref = freeze_factual_snapshot(
        snap(),
        output_root=tmp_path / "frozen",
        collected_at="2040-01-01T00:00:00Z",
    )
    candidate = build_publication_candidate(ref)

    path = build_factual_site_candidate(
        tournament_name="ANY",
        candidate=candidate,
        ref=ref,
        output_root=tmp_path / "candidate",
    )

    html = path.read_text(encoding="utf-8").replace(
        ref.sha256, "bad-sha"
    )

    with pytest.raises(FactualSiteBlocked):
        validate_factual_html(
            html,
            ref=ref,
            expected_rows=1,
        )
