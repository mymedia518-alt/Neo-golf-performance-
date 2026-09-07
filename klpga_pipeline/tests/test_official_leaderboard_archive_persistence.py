"""Tests for scripts/104_official_archive_reconstruction.py's leaderboard
ARCHIVE persistence (not just retrieval-status counts). Red-team finding:
the first version only stored per-round status/counts, which is useless as
evidence for the round-count audit -- these tests lock in that the actual
parsed player rows (player_id, R1-R4 arrays, official status) survive into
the persisted artifact shape, using constructed fixture data so nothing
here depends on real network access.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "official_archive_reconstruction", ROOT / "scripts" / "104_official_archive_reconstruction.py"
)
recon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recon
spec.loader.exec_module(recon)  # type: ignore[union-attr]


def _row(player_id, player, rounds, status="FINISHED", rank="1"):
    return {
        "rank": rank, "rank_numeric": 1, "tie": False, "player": player, "player_id": player_id,
        "to_par": "-3", "through": "F", "rounds": rounds, "total": sum(r for r in rounds if r is not None),
        "status": status,
    }


def test_build_leaderboard_archive_persists_actual_rows_not_just_counts():
    event_result = {
        "game_code": "2099999999",
        "event_status": "RETRIEVED",
        "rounds": {
            "1": {"status": "RETRIEVED", "detail": "1 rows parsed",
                  "rows": [_row("P1", "Player One", [68, None, None, None])], "retrieved_at": "2026-01-01T00:00:00Z"},
            "2": {"status": "NETWORK_EGRESS_DENIED", "detail": "blocked", "rows": None, "retrieved_at": "2026-01-01T00:01:00Z"},
            "3": {"status": "NETWORK_EGRESS_DENIED", "detail": "blocked", "rows": None, "retrieved_at": "2026-01-01T00:02:00Z"},
            "4": {"status": "NETWORK_EGRESS_DENIED", "detail": "blocked", "rows": None, "retrieved_at": "2026-01-01T00:03:00Z"},
        },
        "any_retrieved": True,
    }
    events = recon.build_leaderboard_archive([event_result])
    event = events["2099999999"]
    assert event["event_retrieval_state"] == "PARTIAL"

    round1 = event["rounds"]["1"]
    assert round1["round_retrieval_state"] == "RETRIEVED"
    assert round1["row_count"] == 1
    player_row = round1["players"][0]
    # per instruction: every player row must carry, at minimum, game_code,
    # requested_round, player_id, player, rank, status, rounds.
    for field in ("game_code", "requested_round", "player_id", "player", "rank", "status", "rounds"):
        assert field in player_row, f"missing required field {field}"
    assert player_row["game_code"] == "2099999999"
    assert player_row["requested_round"] == 1
    assert player_row["player_id"] == "P1"
    assert player_row["player"] == "Player One"
    assert player_row["rounds"] == [68, None, None, None]
    assert player_row["retrieved_at"] == "2026-01-01T00:00:00Z"

    round2 = event["rounds"]["2"]
    assert round2["round_retrieval_state"] == "NETWORK_EGRESS_DENIED"
    assert round2["row_count"] == 0
    assert round2["players"] == []


def test_build_leaderboard_archive_all_four_rounds_retrieved_is_fully_retrieved():
    event_result = {
        "game_code": "2099999999", "event_status": "RETRIEVED",
        "rounds": {
            str(n): {"status": "RETRIEVED", "detail": "1 rows parsed",
                     "rows": [_row("P1", "Player One", [68, 70, 71, 69][:n] + [None] * (4 - n))],
                     "retrieved_at": "2026-01-01T00:00:00Z"}
            for n in (1, 2, 3, 4)
        },
        "any_retrieved": True,
    }
    events = recon.build_leaderboard_archive([event_result])
    assert events["2099999999"]["event_retrieval_state"] == "RETRIEVED"


def test_build_leaderboard_archive_all_failed_keeps_the_original_failure_reason():
    event_result = {
        "game_code": "2099999999", "event_status": "NETWORK_EGRESS_DENIED",
        "rounds": {
            str(n): {"status": "NETWORK_EGRESS_DENIED", "detail": "blocked", "rows": None, "retrieved_at": "2026-01-01T00:00:00Z"}
            for n in (1, 2, 3, 4)
        },
        "any_retrieved": False,
    }
    events = recon.build_leaderboard_archive([event_result])
    assert events["2099999999"]["event_retrieval_state"] == "NETWORK_EGRESS_DENIED"
    for round_data in events["2099999999"]["rounds"].values():
        assert round_data["players"] == []
        assert round_data["row_count"] == 0


def test_strip_rows_for_summary_removes_rows_but_keeps_status_and_never_mutates_original():
    event_result = {
        "game_code": "2099999999", "event_status": "RETRIEVED",
        "rounds": {
            "1": {"status": "RETRIEVED", "detail": "1 rows parsed",
                  "rows": [_row("P1", "Player One", [68, None, None, None])], "retrieved_at": "2026-01-01T00:00:00Z"},
        },
        "any_retrieved": True,
    }
    slim = recon.strip_rows_for_summary(event_result)
    assert "rows" not in slim["rounds"]["1"]
    assert "retrieved_at" not in slim["rounds"]["1"]
    assert slim["rounds"]["1"]["status"] == "RETRIEVED"
    # the original, richer dict must be untouched -- the leaderboard archive
    # builder still needs its "rows" key after the summary is stripped.
    assert "rows" in event_result["rounds"]["1"]
    assert event_result["rounds"]["1"]["rows"][0]["player_id"] == "P1"


def test_real_leaderboard_archive_never_fabricates_a_round_that_was_not_retrieved():
    """Locks in the actual persisted archive's invariant: a round whose
    round_retrieval_state is not RETRIEVED must carry zero player rows --
    whatever the real network state was when this artifact was generated."""
    import json
    archive_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json"
    archive = json.loads(archive_path.read_text(encoding="utf-8"))
    assert archive["model_state"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    assert archive["parser_reused"].startswith("klpga.website_v2.official_data.parse_leaderboard_html")
    for game_code, event in archive["events"].items():
        for rnd, round_data in event["rounds"].items():
            if round_data["round_retrieval_state"] != "RETRIEVED":
                assert round_data["players"] == [], (
                    f"{game_code} round {rnd} claims players despite round_retrieval_state="
                    f"{round_data['round_retrieval_state']!r} -- this would be a fabricated round"
                )
            else:
                for row in round_data["players"]:
                    for field in ("game_code", "requested_round", "player_id", "player", "rank", "status", "rounds"):
                        assert field in row
