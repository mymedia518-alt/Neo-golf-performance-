from pathlib import Path

import pytest

from klpga.tournament_atomic_promotion import (
    PromotionBlocked,
    atomic_promote,
    file_sha256,
    validate_candidate_for_promotion,
)


SHA = "a" * 64


def html(game="FUTURE", rnd=3, sha=SHA):
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="neo-publication-mode" content="factual-only">
<meta name="neo-game-code" content="{game}">
<meta name="neo-round-number" content="{rnd}">
<meta name="neo-factual-sha256" content="{sha}">
</head>
<body>
<h1>?? ??</h1>
<table><tr><td>??? ??</td><td>18H</td></tr></table>
</body>
</html>
"""


def test_valid_utf8_candidate(tmp_path):
    p = tmp_path / "candidate.html"
    p.write_text(html(), encoding="utf-8")

    digest = validate_candidate_for_promotion(
        p,
        expected_game_code="FUTURE",
        expected_round_number=3,
        expected_factual_sha256=SHA,
    )

    assert digest == file_sha256(p)
    assert "?? ??" in p.read_text(encoding="utf-8")


def test_wrong_game_binding_blocks(tmp_path):
    p = tmp_path / "candidate.html"
    p.write_text(html(), encoding="utf-8")

    with pytest.raises(PromotionBlocked):
        validate_candidate_for_promotion(
            p,
            expected_game_code="OTHER",
            expected_round_number=3,
            expected_factual_sha256=SHA,
        )


def test_model_leak_blocks(tmp_path):
    p = tmp_path / "candidate.html"
    p.write_text(
        html() + "<div>???? 20%</div>",
        encoding="utf-8",
    )

    with pytest.raises(PromotionBlocked):
        validate_candidate_for_promotion(
            p,
            expected_game_code="FUTURE",
            expected_round_number=3,
            expected_factual_sha256=SHA,
        )


def test_atomic_promotion(tmp_path):
    candidate = tmp_path / "candidate.html"
    target = tmp_path / "docs" / "index.html"

    candidate.write_text(html(), encoding="utf-8")
    target.parent.mkdir(parents=True)
    target.write_text("OLD LIVE", encoding="utf-8")

    old_sha = file_sha256(target)

    result = atomic_promote(
        candidate,
        target,
        expected_game_code="FUTURE",
        expected_round_number=3,
        expected_factual_sha256=SHA,
    )

    assert result.before_sha256 == old_sha
    assert result.after_sha256 == file_sha256(candidate)
    assert target.read_bytes() == candidate.read_bytes()
    assert result.changed is True


def test_failure_preserves_live(tmp_path):
    candidate = tmp_path / "candidate.html"
    target = tmp_path / "docs" / "index.html"

    candidate.write_text(
        html(game="WRONG"),
        encoding="utf-8",
    )
    target.parent.mkdir(parents=True)
    target.write_text("CURRENT LIVE", encoding="utf-8")

    before = target.read_bytes()

    with pytest.raises(PromotionBlocked):
        atomic_promote(
            candidate,
            target,
            expected_game_code="RIGHT",
            expected_round_number=3,
            expected_factual_sha256=SHA,
        )

    assert target.read_bytes() == before


def test_invalid_utf8_blocks_and_preserves_live(tmp_path):
    candidate = tmp_path / "candidate.html"
    target = tmp_path / "docs" / "index.html"

    candidate.write_bytes(b"\xff\xfe\xfa")
    target.parent.mkdir(parents=True)
    target.write_text("CURRENT LIVE", encoding="utf-8")

    before = target.read_bytes()

    with pytest.raises(PromotionBlocked):
        atomic_promote(
            candidate,
            target,
            expected_game_code="FUTURE",
            expected_round_number=3,
            expected_factual_sha256=SHA,
        )

    assert target.read_bytes() == before
