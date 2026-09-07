"""Tests for scripts/115_build_public_players_top150.py -- NEO SITE V5
simplification: the public players board is K-Rank Top150 only, no
qualification-evidence classification."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_public_players_top150", ROOT / "scripts" / "115_build_public_players_top150.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def test_ranks_1_to_120_are_complete_and_contiguous():
    doc = mod.build()
    ranks = sorted(p["rank"] for p in doc["players"])
    assert ranks[:120] == list(range(1, 121))


def test_no_duplicate_ranks_or_player_ids():
    doc = mod.build()
    ranks = [p["rank"] for p in doc["players"]]
    ids = [p["player_id"] for p in doc["players"]]
    assert len(ranks) == len(set(ranks))
    assert len(ids) == len(set(ids))


def test_every_player_within_target_range():
    doc = mod.build()
    for p in doc["players"]:
        assert 1 <= p["rank"] <= 150


def test_missing_121_150_positions_are_explicit_never_fabricated():
    doc = mod.build()
    present = {p["rank"] for p in doc["players"]}
    for rank in range(121, 151):
        assert (rank in present) != (rank in doc["missing_rank_positions"])
    assert doc["confirmed_rank_count"] + len(doc["missing_rank_positions"]) == 150
    assert doc["collection_status"] == "PARTIAL_121_150_PENDING_LIVE_KLPGA_NETWORK_ACCESS"


def test_121_to_150_names_resolved_via_canonical_546_master_never_guessed():
    doc = mod.build()
    extra = [p for p in doc["players"] if p["rank"] > 120]
    assert extra, "expected the real 14-player 121-150 subset"
    for p in extra:
        assert p["player_name"]
        assert p["k_rank_source"]["artifact"] == "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"


def test_sponsor_is_real_or_blank_never_invented():
    doc = mod.build()
    for p in doc["players"]:
        assert p["official_sponsor"] is None or isinstance(p["official_sponsor"], str)
    # at least one real sponsor value actually present (not a trivially
    # all-blank population).
    assert any(p["official_sponsor"] for p in doc["players"])


def test_not_padded_or_truncated_to_exactly_150():
    doc = mod.build()
    assert doc["confirmed_rank_count"] == 134  # the real, current number -- not 150


def test_distinct_from_546_master_and_from_tournament_entry_list():
    doc = mod.build()
    assert "546" in doc["distinct_from"]
    assert "Entry List" in doc["distinct_from"]


def test_artifact_hash_is_a_real_sha256():
    doc = mod.build()
    assert len(doc["artifact_hash"]) == 64
    int(doc["artifact_hash"], 16)
