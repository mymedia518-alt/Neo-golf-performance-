from types import SimpleNamespace

import pytest

from klpga.tournament_official_ingest import (
    OfficialRoundSnapshot,
)

import neo_tournament_runtime as runtime


def player(
    pid,
    *,
    status="ACTIVE",
    holes=18,
):
    return SimpleNamespace(
        player_id=pid,
        status=status,
        holes_completed=holes,
    )


def snap(players, game="GAME", rnd=2):
    return OfficialRoundSnapshot(
        game_code=game,
        round_number=rnd,
        players=tuple(players),
    )


def state(
    *,
    game="GAME",
    final=3,
    current=2,
    stage="R2_LIVE",
    model=False,
):
    return runtime.RuntimeState(
        game_code=game,
        final_round_number=final,
        current_round_number=current,
        validated_stage=stage,
        cut_after_round=2,
        model_ready=model,
    )


def test_active_18h_is_complete():
    assert (
        runtime.player_is_unfinished(
            player("1", holes=18)
        )
        is False
    )


def test_incomplete_is_unfinished_even_with_holes():
    assert runtime.player_is_unfinished(
        player(
            "1",
            status="INCOMPLETE",
            holes=1,
        )
    )


def test_unknown_holes_fail_closed_as_unfinished():
    assert runtime.player_is_unfinished(
        player("1", holes=None)
    )


@pytest.mark.parametrize(
    "status",
    ["WD", "DQ", "DNS"],
)
def test_terminal_status_not_unfinished(status):
    assert (
        runtime.player_is_unfinished(
            player(
                "1",
                status=status,
                holes=None,
            )
        )
        is False
    )


def test_r2_live_remains_factual_only():
    decision = runtime.classify_live_snapshot(
        state(model=True),
        snap([
            player("1", holes=18),
            player(
                "2",
                status="INCOMPLETE",
                holes=7,
            ),
        ]),
    )

    assert decision.observed_stage == "R2_LIVE"
    assert decision.publication_mode == "FACTUAL_LIVE"
    assert decision.should_publish_factual is True
    assert decision.should_publish_model is False
    assert decision.should_disable_cycle is False
    assert decision.unfinished_count == 1


def test_r2_completion_stops_at_cut_gate():
    decision = runtime.classify_live_snapshot(
        state(),
        snap([
            player("1", holes=18),
            player("2", holes=18),
            player(
                "3",
                status="WD",
                holes=None,
            ),
        ]),
    )

    assert decision.observed_stage == "R2_COMPLETE"
    assert decision.next_gate == "CUT_CONFIRMATION"
    assert decision.should_publish_factual is True
    assert decision.should_publish_model is False
    assert decision.should_disable_cycle is True
    assert decision.unfinished_count == 0


def test_model_ready_never_bypasses_r2_cut_gate():
    decision = runtime.classify_live_snapshot(
        state(model=True),
        snap([
            player("1"),
            player("2"),
        ]),
    )

    assert decision.observed_stage == "R2_COMPLETE"
    assert decision.next_gate == "CUT_CONFIRMATION"
    assert decision.should_publish_model is False


def test_game_mismatch_blocks():
    with pytest.raises(runtime.RuntimeBlocked):
        runtime.classify_live_snapshot(
            state(game="RIGHT"),
            snap(
                [player("1")],
                game="WRONG",
            ),
        )


def test_round_mismatch_blocks():
    with pytest.raises(runtime.RuntimeBlocked):
        runtime.classify_live_snapshot(
            state(current=2),
            snap(
                [player("1")],
                rnd=1,
            ),
        )


def test_non_live_stage_not_accepted_by_runtime():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        raise AssertionError(
            "fetch must not occur"
        )

    with pytest.raises(runtime.RuntimeBlocked):
        runtime.run_once(
            state(stage="R2_COMPLETE"),
            cache_dir=None,
            fetcher=fetcher,
        )

    assert calls == []


def test_generic_future_game_fetch_arguments():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)

        return snap(
            [player("1", holes=7)],
            game=kwargs["game_code"],
            rnd=kwargs["round_number"],
        )

    _, decision = runtime.run_once(
        state(
            game="FUTURE-2030",
            final=4,
            current=3,
            stage="NEXT_ROUND_LIVE",
        ),
        cache_dir="CACHE",
        fetcher=fetcher,
    )

    assert calls == [{
        "game_code": "FUTURE-2030",
        "round_number": 3,
        "cache_dir": "CACHE",
    }]

    assert decision.should_publish_model is False



def test_no_tournament_specific_identifiers():
    source = runtime.Path(
        runtime.__file__
    ).read_text(encoding="utf-8")

    # ASCII-safe invariant:
    # engine source must never contain event IDs or legacy
    # tournament-specific script names.
    for forbidden in (
        "2026120001",
        "2026080001",
        "99_ok_open",
        "96_ok_open",
        "ok_open_r1",
        "kg_ladies_open",
    ):
        assert forbidden not in source.lower()


def test_runtime_source_has_no_replacement_character():
    source = runtime.Path(
        runtime.__file__
    ).read_text(encoding="utf-8")

    assert "\ufffd" not in source


def test_publication_uses_exact_snapshot(monkeypatch, tmp_path):
    snap_obj = snap([
        player("1", holes=18),
        player(
            "2",
            status="INCOMPLETE",
            holes=7,
        ),
    ])

    seen = {}

    def fetcher(**kwargs):
        return snap_obj

    def publisher(req, snapshot, decision):
        seen["request"] = req
        seen["snapshot"] = snapshot
        seen["decision"] = decision
        return "PUBLICATION"

    monkeypatch.setattr(
        runtime,
        "publish_runtime_snapshot",
        publisher,
    )

    snapshot, decision, publication = (
        runtime.run_publication_once(
            state(),
            tournament_name="TEST EVENT",
            cache_dir=tmp_path / "cache",
            frozen_root=tmp_path / "frozen",
            candidate_root=tmp_path / "candidate",
            target_path=tmp_path / "target.html",
            fetcher=fetcher,
        )
    )

    assert snapshot is snap_obj
    assert seen["snapshot"] is snap_obj
    assert seen["decision"] is decision
    assert publication == "PUBLICATION"
    assert seen["request"].promote is False


def test_publication_promotion_is_explicit(
    monkeypatch,
    tmp_path,
):
    snap_obj = snap([
        player(
            "1",
            status="INCOMPLETE",
            holes=7,
        ),
    ])

    seen = {}

    def fetcher(**kwargs):
        return snap_obj

    def publisher(req, snapshot, decision):
        seen["promote"] = req.promote
        return "PUBLICATION"

    monkeypatch.setattr(
        runtime,
        "publish_runtime_snapshot",
        publisher,
    )

    runtime.run_publication_once(
        state(),
        tournament_name="TEST EVENT",
        cache_dir=tmp_path / "cache",
        frozen_root=tmp_path / "frozen",
        candidate_root=tmp_path / "candidate",
        target_path=tmp_path / "target.html",
        promote=True,
        fetcher=fetcher,
    )

    assert seen["promote"] is True


def test_cut_gate_is_config_driven():
    s = runtime.RuntimeState(
        game_code="GAME",
        final_round_number=4,
        current_round_number=1,
        validated_stage="R1_LIVE",
        cut_after_round=1,
    )

    snapshot = runtime.OfficialRoundSnapshot(
        game_code="GAME",
        round_number=1,
        players=(player("1", holes=18),),
    )

    d = runtime.classify_live_snapshot(
        s,
        snapshot,
    )

    assert d.observed_stage == "ROUND_1_COMPLETE"
    assert d.next_gate == "CUT_CONFIRMATION"
    assert d.should_disable_cycle is True


def test_round_two_is_not_implicitly_cut():
    s = runtime.RuntimeState(
        game_code="GAME",
        final_round_number=4,
        current_round_number=2,
        validated_stage="R2_LIVE",
        cut_after_round=3,
    )

    d = runtime.classify_live_snapshot(
        s,
        snap([player("1", holes=18)]),
    )

    assert d.observed_stage == "ROUND_2_COMPLETE"
    assert d.next_gate == "NEXT_STAGE_VALIDATION"


def test_no_cut_tournament_supported():
    s = runtime.RuntimeState(
        game_code="GAME",
        final_round_number=3,
        current_round_number=2,
        validated_stage="R2_LIVE",
        cut_after_round=None,
    )

    d = runtime.classify_live_snapshot(
        s,
        snap([player("1", holes=18)]),
    )

    assert d.observed_stage == "ROUND_2_COMPLETE"
    assert d.next_gate == "NEXT_STAGE_VALIDATION"


def test_final_round_wins_over_cut_configuration():
    with pytest.raises(ValueError):
        runtime.RuntimeState(
            game_code="GAME",
            final_round_number=3,
            current_round_number=3,
            validated_stage="FINAL_LIVE",
            cut_after_round=3,
        )


def test_invalid_cut_round_zero_rejected():
    with pytest.raises(ValueError):
        runtime.RuntimeState(
            game_code="GAME",
            final_round_number=4,
            current_round_number=1,
            validated_stage="R1_LIVE",
            cut_after_round=0,
        )


def test_cut_decision_is_not_implicitly_round_two():
    s = runtime.RuntimeState(
        game_code="GAME",
        final_round_number=4,
        current_round_number=2,
        validated_stage="R2_LIVE",
        cut_after_round=3,
    )

    d = runtime.classify_live_snapshot(
        s,
        snap([player("1", holes=18)]),
    )

    assert d.next_gate != "CUT_CONFIRMATION"
    assert d.next_gate == "NEXT_STAGE_VALIDATION"


def test_cut_reconciliation_closes_ambiguous_incomplete_rows(tmp_path):
    import sqlite3

    db = tmp_path / "klpga.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE player_event (
            game_code TEXT,
            player_id TEXT,
            made_cut INTEGER
        );
        CREATE TABLE player_round (
            game_code TEXT,
            round_number INTEGER,
            player_id TEXT
        );
    """)
    con.executemany(
        "INSERT INTO player_event VALUES ('GAME', ?, ?)",
        [("1", 1), ("2", 1), ("3", 0)],
    )
    con.executemany(
        "INSERT INTO player_round VALUES ('GAME', 2, ?)",
        [("1",), ("2",)],
    )
    con.commit()
    con.close()

    d = runtime.classify_live_snapshot(
        state(),
        snap([
            player("1", holes=18),
            player("2", holes=18),
            player("3", status="INCOMPLETE", holes=1),
        ]),
        db_path=db,
    )

    assert d.observed_stage == "R2_COMPLETE"
    assert d.next_gate == "CUT_CONFIRMATION"
    assert d.unfinished_count == 0


def test_cut_reconciliation_fails_closed_on_unknown_cut(tmp_path):
    import sqlite3

    db = tmp_path / "klpga.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE player_event (
            game_code TEXT,
            player_id TEXT,
            made_cut INTEGER
        );
        CREATE TABLE player_round (
            game_code TEXT,
            round_number INTEGER,
            player_id TEXT
        );
    """)
    con.executemany(
        "INSERT INTO player_event VALUES ('GAME', ?, ?)",
        [("1", 1), ("2", None)],
    )
    con.execute(
        "INSERT INTO player_round VALUES ('GAME', 2, '1')"
    )
    con.commit()
    con.close()

    d = runtime.classify_live_snapshot(
        state(),
        snap([
            player("1", holes=18),
            player("2", status="INCOMPLETE", holes=1),
        ]),
        db_path=db,
    )

    assert d.observed_stage == "R2_LIVE"
    assert d.next_gate == "WAIT"
    assert d.unfinished_count == 1


def test_cut_reconciliation_blocks_survivor_marked_incomplete(tmp_path):
    import sqlite3

    db = tmp_path / "klpga.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE player_event (
            game_code TEXT,
            player_id TEXT,
            made_cut INTEGER
        );
        CREATE TABLE player_round (
            game_code TEXT,
            round_number INTEGER,
            player_id TEXT
        );
    """)
    con.executemany(
        "INSERT INTO player_event VALUES ('GAME', ?, ?)",
        [("1", 1), ("2", 0)],
    )
    con.execute(
        "INSERT INTO player_round VALUES ('GAME', 2, '1')"
    )
    con.commit()
    con.close()

    d = runtime.classify_live_snapshot(
        state(),
        snap([
            player("1", status="INCOMPLETE", holes=1),
            player("2", holes=18),
        ]),
        db_path=db,
    )

    assert d.observed_stage == "R2_LIVE"
    assert d.next_gate == "WAIT"
