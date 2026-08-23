import sqlite3

from klpga import db
from klpga.models import Player, PlayerEvent, RoundResult, Tournament


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_db(conn)
    return conn


def test_upsert_tournament_idempotent():
    conn = _make_conn()
    t = Tournament(
        tournament_id="T1", tournament_name="Test Open", season=2025,
        tournament_type="정규투어", status="완료", in_model_scope=True,
    )
    db.upsert_tournament(conn, t)
    db.upsert_tournament(conn, t)
    count = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
    assert count == 1


def test_player_event_and_round_roundtrip():
    conn = _make_conn()
    db.upsert_tournament(conn, Tournament(tournament_id="T1", tournament_name="Test Open"))
    db.upsert_player(conn, Player(player_id="P1", player_name="Test Player"))
    db.upsert_player_event(
        conn,
        PlayerEvent(
            tournament_id="T1", player_id="P1", final_rank="1", final_rank_numeric=1,
            win=True, top5=True, top10=True, top20=True,
        ),
    )
    db.upsert_round(conn, RoundResult(tournament_id="T1", player_id="P1", round_number=1, strokes=68))

    row = conn.execute(
        "SELECT * FROM player_events WHERE tournament_id='T1' AND player_id='P1'"
    ).fetchone()
    assert row["win"] == 1

    round_row = conn.execute(
        "SELECT * FROM rounds WHERE tournament_id='T1' AND player_id='P1' AND round_number=1"
    ).fetchone()
    assert round_row["strokes"] == 68


def test_round_upsert_does_not_duplicate():
    conn = _make_conn()
    db.upsert_tournament(conn, Tournament(tournament_id="T1", tournament_name="Test Open"))
    db.upsert_player(conn, Player(player_id="P1", player_name="Test Player"))
    db.upsert_player_event(conn, PlayerEvent(tournament_id="T1", player_id="P1"))
    db.upsert_round(conn, RoundResult(tournament_id="T1", player_id="P1", round_number=1, strokes=68))
    db.upsert_round(conn, RoundResult(tournament_id="T1", player_id="P1", round_number=1, strokes=70))

    rows = conn.execute(
        "SELECT strokes FROM rounds WHERE tournament_id='T1' AND player_id='P1' AND round_number=1"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["strokes"] == 70


def test_collection_run_lifecycle():
    conn = _make_conn()
    run_id = db.start_collection_run(conn, 100)
    db.finish_collection_run(
        conn, run_id, tournaments_collected=0, players_collected=0,
        status="failed", error_message="network blocked",
    )
    row = conn.execute("SELECT * FROM collection_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["status"] == "failed"
    assert row["error_message"] == "network blocked"
