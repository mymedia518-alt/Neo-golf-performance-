from types import SimpleNamespace
from pathlib import Path
import pytest

import klpga.tournament_runtime_publication as bridge


def request(promote=False):
    return bridge.RuntimePublicationRequest(
        tournament_name="TEST EVENT",
        game_code="GAME",
        round_number=2,
        frozen_root=Path("frozen"),
        candidate_root=Path("candidate"),
        target_path=Path("target.html"),
        promote=promote,
    )


def snapshot(game="GAME", rnd=2):
    return SimpleNamespace(
        game_code=game,
        round_number=rnd,
        row_count=1,
    )


def decision(factual=True, model=False):
    return SimpleNamespace(
        should_publish_factual=factual,
        should_publish_model=model,
    )


def test_factual_block_is_fail_closed():
    with pytest.raises(bridge.RuntimePublicationBlocked):
        bridge.publish_runtime_snapshot(
            request(), snapshot(), decision(factual=False)
        )


def test_model_cannot_leak_through_factual_bridge():
    with pytest.raises(bridge.RuntimePublicationBlocked):
        bridge.publish_runtime_snapshot(
            request(), snapshot(), decision(model=True)
        )


def test_game_mismatch_blocks():
    with pytest.raises(bridge.RuntimePublicationBlocked):
        bridge.publish_runtime_snapshot(
            request(), snapshot(game="WRONG"), decision()
        )


def test_round_mismatch_blocks():
    with pytest.raises(bridge.RuntimePublicationBlocked):
        bridge.publish_runtime_snapshot(
            request(), snapshot(rnd=1), decision()
        )


def test_exact_snapshot_reaches_runner(monkeypatch):
    seen = {}

    def fake_runner(req, snap, *, collected_at=None):
        seen["req"] = req
        seen["snap"] = snap
        seen["collected_at"] = collected_at
        return "PASS"

    monkeypatch.setattr(
        bridge, "run_factual_publication", fake_runner
    )

    snap = snapshot()

    result = bridge.publish_runtime_snapshot(
        request(),
        snap,
        decision(),
        collected_at="2026-09-05T00:00:00Z",
    )

    assert result == "PASS"
    assert seen["snap"] is snap
    assert seen["req"].game_code == "GAME"
    assert seen["req"].round_number == 2
    assert seen["req"].promote is False


def test_promotion_is_explicit(monkeypatch):
    seen = {}

    def fake_runner(req, snap, *, collected_at=None):
        seen["promote"] = req.promote
        return "PASS"

    monkeypatch.setattr(
        bridge, "run_factual_publication", fake_runner
    )

    bridge.publish_runtime_snapshot(
        request(promote=True),
        snapshot(),
        decision(),
    )

    assert seen["promote"] is True
