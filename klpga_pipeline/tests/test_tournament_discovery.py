from datetime import date
import json
import sqlite3

import pytest

from klpga.tournament_discovery import (
    TournamentDiscoveryBlocked,
    build_validated_config,
    discover_tournament,
    refresh_active_config,
)


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE tournament_master (
            game_code TEXT,
            event_name TEXT,
            season INTEGER,
            start_date TEXT,
            end_date TEXT,
            rounds_scheduled INTEGER
        )
        """
    )
    con.executemany(
        """
        INSERT INTO tournament_master
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    con.close()


def validated(game_code):
    return {
        "schema_version": 1,
        "game_code": game_code,
        "tournament_name": "old",
        "final_round_number": 3,
        "current_round_number": 2,
        "validated_stage": "R2_LIVE",
        "cut_after_round": 2,
        "model_ready": False,
    }


def test_discovers_only_active_tournament(tmp_path):
    db = tmp_path / "x.sqlite"
    make_db(db, [
        ("A", "Past", 2026, "2026-08-01", "2026-08-03", 3),
        ("B", "Current", 2026, "2026-09-04", "2026-09-06", 3),
    ])

    found = discover_tournament(
        db,
        as_of=date(2026, 9, 5),
    )

    assert found.game_code == "B"
    assert found.tournament_name == "Current"


def test_ambiguous_active_tournament_fails_closed(tmp_path):
    db = tmp_path / "x.sqlite"
    make_db(db, [
        ("A", "One", 2026, "2026-09-04", "2026-09-06", 3),
        ("B", "Two", 2026, "2026-09-05", "2026-09-07", 3),
    ])

    with pytest.raises(
        TournamentDiscoveryBlocked,
        match="ambiguous",
    ):
        discover_tournament(
            db,
            as_of=date(2026, 9, 5),
        )


def test_new_game_never_reuses_old_lifecycle():
    from klpga.tournament_discovery import DiscoveredTournament

    tournament = DiscoveredTournament(
        game_code="NEW",
        tournament_name="Next",
        season=2026,
        start_date="2026-09-10",
        end_date="2026-09-13",
        rounds_scheduled=4,
    )

    with pytest.raises(
        TournamentDiscoveryBlocked,
        match="no validated lifecycle",
    ):
        build_validated_config(
            tournament,
            previous_config=validated("OLD"),
        )


def test_round_count_conflict_fails_closed():
    from klpga.tournament_discovery import DiscoveredTournament

    tournament = DiscoveredTournament(
        game_code="A",
        tournament_name="Event",
        season=2026,
        start_date="2026-09-04",
        end_date="2026-09-06",
        rounds_scheduled=4,
    )

    with pytest.raises(
        TournamentDiscoveryBlocked,
        match="round-count conflict",
    ):
        build_validated_config(
            tournament,
            previous_config=validated("A"),
        )


def test_refresh_is_atomic_and_preserves_validated_state(tmp_path):
    db = tmp_path / "x.sqlite"
    config = tmp_path / "active.json"

    make_db(db, [
        ("A", "Official Name", 2026, "2026-09-04", "2026-09-06", None),
    ])

    config.write_text(
        json.dumps(validated("A")),
        encoding="utf-8",
    )

    result = refresh_active_config(
        db_path=db,
        config_path=config,
        as_of=date(2026, 9, 5),
    )

    saved = json.loads(
        config.read_text(encoding="utf-8")
    )

    assert saved == result
    assert saved["tournament_name"] == "Official Name"
    assert saved["current_round_number"] == 2
    assert saved["validated_stage"] == "R2_LIVE"
    assert saved["identity_source"] == "tournament_master"
    assert saved["lifecycle_source"] == "validated_state"
    assert not config.with_suffix(".json.tmp").exists()
