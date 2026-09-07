"""NEO TOURNAMENT PIPELINE Phase 3 item 2: run_tournament.py must perform
DISCOVERY itself and bootstrap config/active_tournament.json for a
genuinely new game_code, instead of hard-failing when the file doesn't
exist yet or names a different tournament -- fail-closed only when a
real fact (final_round_number) truly isn't confirmed anywhere, never
fabricated."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_discovery import TournamentDiscoveryBlocked  # noqa: E402
from klpga.tournament_lifecycle import (  # noqa: E402
    TournamentLifecycleError,
    bootstrap_lifecycle_state,
    load_lifecycle_state,
    resolve_or_bootstrap_lifecycle,
)


def _make_db(tmp_path, rows):
    db_path = tmp_path / "klpga.sqlite"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE tournament_master (game_code TEXT, event_name TEXT, season INT, "
        "start_date TEXT, end_date TEXT, rounds_scheduled INT)"
    )
    con.executemany(
        "INSERT INTO tournament_master VALUES (?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    con.close()
    return db_path


def test_bootstrap_fails_closed_without_confirmed_round_count():
    from klpga.tournament_discovery import DiscoveredTournament
    discovered = DiscoveredTournament(
        game_code="NEW001", tournament_name="Brand New Open", season=2028,
        start_date="2028-01-01", end_date="2028-01-03", rounds_scheduled=None,
    )
    import pytest
    with pytest.raises(TournamentLifecycleError, match="never fabricated"):
        bootstrap_lifecycle_state(discovered)


def test_bootstrap_accepts_explicit_final_round_override():
    from klpga.tournament_discovery import DiscoveredTournament
    discovered = DiscoveredTournament(
        game_code="NEW001", tournament_name="Brand New Open", season=2028,
        start_date="2028-01-01", end_date="2028-01-04", rounds_scheduled=None,
    )
    payload = bootstrap_lifecycle_state(discovered, final_round_number=4)
    assert payload["final_round_number"] == 4
    assert payload["current_round_number"] == 1
    assert payload["validated_stage"] == "DISCOVERED"
    assert payload["cut_after_round"] == 2
    assert payload["lifecycle_source"] == "bootstrap"


def test_resolve_bootstraps_brand_new_game_code_with_no_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "ACTIVE_TOURNAMENT_PATH", tmp_path / "active_tournament.json")
    import klpga.tournament_lifecycle as lifecycle_mod
    monkeypatch.setattr(lifecycle_mod, "ACTIVE_TOURNAMENT_PATH", tmp_path / "active_tournament.json")

    db_path = _make_db(tmp_path, [("NEW002", "Another New Open", 2028, "2028-02-01", "2028-02-04", 3)])
    payload = resolve_or_bootstrap_lifecycle(game_code="NEW002", db_path=db_path)
    assert payload["game_code"] == "NEW002"
    assert payload["final_round_number"] == 3
    assert payload["validated_stage"] == "DISCOVERED"

    on_disk = load_lifecycle_state(tmp_path / "active_tournament.json")
    assert on_disk["game_code"] == "NEW002"


def test_resolve_bootstraps_a_different_game_code_replacing_the_old_one(tmp_path, monkeypatch):
    config_path = tmp_path / "active_tournament.json"
    monkeypatch.setattr(tournament_context, "ACTIVE_TOURNAMENT_PATH", config_path)
    import klpga.tournament_lifecycle as lifecycle_mod
    monkeypatch.setattr(lifecycle_mod, "ACTIVE_TOURNAMENT_PATH", config_path)

    import json
    config_path.write_text(json.dumps({
        "game_code": "OLD001", "tournament_name": "Old Open", "season": 2027,
        "start_date": "2027-01-01", "end_date": "2027-01-03", "final_round_number": 3,
        "current_round_number": 3, "validated_stage": "FINAL_COMPLETE", "cut_after_round": 2,
        "model_ready": False,
    }), encoding="utf-8")

    db_path = _make_db(tmp_path, [("NEW003", "Yet Another Open", 2028, "2028-03-01", "2028-03-04", 4)])
    payload = resolve_or_bootstrap_lifecycle(game_code="NEW003", db_path=db_path)
    assert payload["game_code"] == "NEW003"
    assert payload["validated_stage"] == "DISCOVERED"

    on_disk = load_lifecycle_state(config_path)
    assert on_disk["game_code"] == "NEW003"
    assert "OLD001" not in json.dumps(on_disk)


def test_resolve_falls_back_to_existing_file_when_db_missing(tmp_path, monkeypatch):
    """A sandbox with no klpga.sqlite at all must not lose an
    already-validated lifecycle just because discovery can't run."""
    config_path = tmp_path / "active_tournament.json"
    monkeypatch.setattr(tournament_context, "ACTIVE_TOURNAMENT_PATH", config_path)
    import klpga.tournament_lifecycle as lifecycle_mod
    monkeypatch.setattr(lifecycle_mod, "ACTIVE_TOURNAMENT_PATH", config_path)

    import json
    config_path.write_text(json.dumps({
        "game_code": "OK001", "tournament_name": "OK Open", "season": 2026,
        "start_date": "2026-09-04", "end_date": "2026-09-06", "final_round_number": 3,
        "current_round_number": 2, "validated_stage": "R2_LIVE", "cut_after_round": 2,
        "model_ready": False,
    }), encoding="utf-8")

    missing_db = tmp_path / "does_not_exist.sqlite"
    payload = resolve_or_bootstrap_lifecycle(game_code="OK001", db_path=missing_db)
    assert payload["game_code"] == "OK001"
    assert payload["validated_stage"] == "R2_LIVE"


def test_resolve_with_no_file_and_no_game_code_uses_dated_discovery(tmp_path, monkeypatch):
    config_path = tmp_path / "active_tournament.json"
    monkeypatch.setattr(tournament_context, "ACTIVE_TOURNAMENT_PATH", config_path)
    import klpga.tournament_lifecycle as lifecycle_mod
    monkeypatch.setattr(lifecycle_mod, "ACTIVE_TOURNAMENT_PATH", config_path)

    db_path = _make_db(tmp_path, [("NEW004", "Today's Open", 2028, "2028-04-01", "2028-04-04", 4)])
    payload = resolve_or_bootstrap_lifecycle(game_code=None, db_path=db_path, as_of=date(2028, 4, 2))
    assert payload["game_code"] == "NEW004"


def test_resolve_never_invents_a_game_code_not_in_tournament_master(tmp_path, monkeypatch):
    config_path = tmp_path / "active_tournament.json"
    monkeypatch.setattr(tournament_context, "ACTIVE_TOURNAMENT_PATH", config_path)
    import klpga.tournament_lifecycle as lifecycle_mod
    monkeypatch.setattr(lifecycle_mod, "ACTIVE_TOURNAMENT_PATH", config_path)

    db_path = _make_db(tmp_path, [])
    import pytest
    with pytest.raises(TournamentDiscoveryBlocked):
        resolve_or_bootstrap_lifecycle(game_code="GHOST001", db_path=db_path)
