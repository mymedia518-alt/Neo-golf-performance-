"""Tests for klpga.neo_win.round_reconciliation — the shared official-
vs-DB round validation gate. Offline: reconcile_round() itself is pure
(no I/O), so most scenarios construct NormalizedPlayer dicts directly;
a few exercise normalize_official_round()/normalize_entry_rows() with
real EntryRow/PlayerRoundRow objects to prove the fetch-side adapters
(duplicate rows, tie positions) behave correctly too."""
from __future__ import annotations

from klpga.neo_win.round_reconciliation import (
    CLASS_DB_NOT_IN_OFFICIAL,
    CLASS_ENTRY_ABSENT,
    CLASS_NAME_MISMATCH,
    CLASS_OFFICIAL_MISSING_IN_DB,
    CLASS_POSITION_MISMATCH,
    CLASS_POSSIBLE_IDENTITY_MISMATCH,
    CLASS_SCORE_MISMATCH,
    NormalizedPlayer,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_WARN,
    normalize_entry_rows,
    normalize_official_round,
    reconcile_round,
)
from klpga.parsers.entry_list_parser import EntryRow
from klpga.parsers.leaderboard_parser import PlayerRoundRow


def _np(code, *, name="X", position=None, position_display=None, round_score=None, score_to_par=None, status=None):
    return NormalizedPlayer(
        player_code=code, player_name=name, position_display=position_display, position=position,
        round_score=round_score, score_to_par=score_to_par, status=status,
    )


def _row(
    code, name, round_number, *, rank_display="1", rank=1, tie_flag=False, status=None,
    total_under_par=-1, today_under_par=-1, round_score=68,
):
    round_scores = {1: None, 2: None, 3: None, 4: None}
    round_scores[round_number] = round_score
    return PlayerRoundRow(
        game_code="G", player_code=code, player_name=name, player_eng_name=None, round_number=round_number,
        rank_display=rank_display, rank=rank, tie_flag=tie_flag, status=status,
        total_under_par_display=str(total_under_par), total_under_par=total_under_par,
        today_under_par_display=str(today_under_par), today_under_par=today_under_par,
        total_strokes=round_score, holes_completed="18",
        round1_score=round_scores[1], round2_score=round_scores[2],
        round3_score=round_scores[3], round4_score=round_scores[4],
    )


# ---------------------------------------------------------------
# 1. 120 ENTRY / 120 official / 120 DB -> PASS
# ---------------------------------------------------------------
def test_120_field_fully_matched_is_pass():
    codes = [f"P{i:03d}" for i in range(120)]
    entry = {c: _np(c, name=c) for c in codes}
    official = {c: _np(c, name=c, position=i + 1, position_display=str(i + 1), round_score=70 - i, score_to_par=-i) for i, c in enumerate(codes)}
    db = {c: _np(c, name=c, position=i + 1, position_display=str(i + 1), round_score=70 - i, score_to_par=-i) for i, c in enumerate(codes)}

    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_PASS
    assert len(result.entry_and_official_and_db) == 120
    assert not result.entry_only
    assert not result.official_only
    assert not result.db_only
    assert len(result.eligible) == 120
    assert not result.excluded
    assert not result.unresolved


# ---------------------------------------------------------------
# 2. 120 ENTRY / 118 official (2 absent) / 118 matching DB -> must NOT fail
#    solely because field count changed (product rule).
# ---------------------------------------------------------------
def test_field_count_shrinking_is_not_itself_a_failure():
    codes = [f"P{i:03d}" for i in range(120)]
    absent = {"P010", "P011"}
    played = [c for c in codes if c not in absent]

    entry = {c: _np(c, name=c) for c in codes}
    official = {c: _np(c, name=c, position=i + 1, position_display=str(i + 1), round_score=70, score_to_par=-1) for i, c in enumerate(played)}
    db = {c: _np(c, name=c, position=i + 1, position_display=str(i + 1), round_score=70, score_to_par=-1) for i, c in enumerate(played)}

    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_WARN  # ENTRY_ABSENT is WARN, never FAIL by itself
    assert len(result.eligible) == 118
    assert set(result.excluded) == absent
    for code in absent:
        matching = [a for a in result.anomalies if a["player_code"] == code]
        assert len(matching) == 1
        assert matching[0]["classification"] == CLASS_ENTRY_ABSENT
        # never fabricated: excluded players carry no round_score/score_to_par anywhere in the result.
        assert code not in official
        assert code not in db


# ---------------------------------------------------------------
# 3. official player has score but DB misses the player -> FAIL
# ---------------------------------------------------------------
def test_official_complete_but_missing_in_db_is_fail():
    entry = {"9431": _np("9431", name="박보겸")}
    official = {"9431": _np("9431", name="박보겸", position=27, position_display="T27", round_score=69, score_to_par=-3)}
    db = {}

    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_FAIL
    assert "9431" in result.unresolved
    anomaly = next(a for a in result.anomalies if a["player_code"] == "9431")
    assert anomaly["classification"] == CLASS_OFFICIAL_MISSING_IN_DB
    assert "69" in anomaly["detail"] or "-3" in anomaly["detail"]


# ---------------------------------------------------------------
# 4. official score differs from DB score -> FAIL
# ---------------------------------------------------------------
def test_score_mismatch_is_fail():
    entry = {"A": _np("A")}
    official = {"A": _np("A", name="A", position=1, position_display="1", round_score=69, score_to_par=-3)}
    db = {"A": _np("A", name="A", position=1, position_display="1", round_score=70, score_to_par=-2)}

    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_FAIL
    anomaly = next(a for a in result.anomalies if a["player_code"] == "A")
    assert anomaly["classification"] == CLASS_SCORE_MISMATCH
    assert "A" in result.unresolved
    assert "A" not in result.eligible


# ---------------------------------------------------------------
# 5. DB player not present in official leaderboard -> anomaly (WARN, not FAIL by itself)
# ---------------------------------------------------------------
def test_db_not_in_official_is_reported_anomaly():
    entry = {"A": _np("A")}
    official = {}
    db = {"A": _np("A", name="A", position=1, position_display="1", round_score=69, score_to_par=-3)}

    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_WARN
    assert "A" in result.db_not_in_official
    anomaly = next(a for a in result.anomalies if a["player_code"] == "A")
    assert anomaly["classification"] == CLASS_DB_NOT_IN_OFFICIAL


# ---------------------------------------------------------------
# 6. player_code identity mismatch (same code, conflicting name) -> FAIL
# ---------------------------------------------------------------
def test_same_code_conflicting_name_is_fail_never_auto_reconciled():
    entry = {"A": _np("A")}
    official = {"A": _np("A", name="김하니", position=1, position_display="1", round_score=69, score_to_par=-3)}
    db = {"A": _np("A", name="박보겸", position=1, position_display="1", round_score=69, score_to_par=-3)}

    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_FAIL
    anomaly = next(a for a in result.anomalies if a["player_code"] == "A")
    assert anomaly["classification"] == CLASS_NAME_MISMATCH
    assert "A" not in result.eligible
    assert "A" in result.unresolved


# ---------------------------------------------------------------
# 7. WD/DQ/DNS/unknown absence must never receive a fabricated score
# ---------------------------------------------------------------
def test_absent_player_never_gets_fabricated_score():
    entry = {"A": _np("A"), "B": _np("B", name="B_played")}
    official = {"B": _np("B", name="B_played", position=1, position_display="1", round_score=69, score_to_par=-3)}
    db = {"B": _np("B", name="B_played", position=1, position_display="1", round_score=69, score_to_par=-3)}

    result = reconcile_round(entry, official, db, round_number=1)
    assert "A" in result.excluded
    assert "A" not in result.eligible
    assert "A" not in official and "A" not in db  # no row was invented for A anywhere
    anomaly = next(a for a in result.anomalies if a["player_code"] == "A")
    assert anomaly["classification"] == CLASS_ENTRY_ABSENT
    assert result.verdict == VERDICT_WARN


# ---------------------------------------------------------------
# 8. duplicate official rows must normalize correctly
# ---------------------------------------------------------------
def test_duplicate_official_rows_normalize_without_crashing_or_duplicating():
    rows = [
        _row("A", "A", 1, rank_display="1", rank=1, round_score=68, today_under_par=-4, total_under_par=-4),
        _row("A", "A", 1, rank_display="1", rank=1, round_score=68, today_under_par=-4, total_under_par=-4),
    ]
    normalized = normalize_official_round(rows, round_number=1)
    assert len(normalized) == 1
    assert normalized["A"].round_score == 68
    assert normalized["A"].score_to_par == -4


# ---------------------------------------------------------------
# 9. tied positions (e.g. T27/T38) must normalize correctly
# ---------------------------------------------------------------
def test_tied_positions_normalize_to_matching_numeric_rank():
    from klpga.neo_win.round_reconciliation import normalize_db_round  # local import: needs sqlite3
    import sqlite3

    rows = [_row("9431", "박보겸", 1, rank_display="T27", rank=27, tie_flag=True, round_score=69, today_under_par=-3, total_under_par=-3)]
    official = normalize_official_round(rows, round_number=1)
    assert official["9431"].position == 27
    assert official["9431"].position_display == "T27"

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE player_round (event_id TEXT, game_code TEXT, season INT, round_number INT, player_id TEXT, "
        "player_name TEXT, round_score INT, round_to_par INT, finish_position_after_round TEXT)"
    )
    conn.execute(
        "INSERT INTO player_round VALUES ('E', 'G', 2026, 1, '9431', '박보겸', 69, -3, 'T27')"
    )
    db = normalize_db_round(conn, "G", 1)
    assert db["9431"].position == 27
    assert db["9431"].position_display == "T27"

    entry = normalize_entry_rows([EntryRow(player_code="9431", player_name="박보겸", nationality=None, qualification_category=None, qualification_reason=None)])
    result = reconcile_round(entry, official, db, round_number=1)
    assert result.verdict == VERDICT_PASS
    assert "9431" in result.eligible


# ---------------------------------------------------------------
# 10. Korean names must not be used as primary identity key
# ---------------------------------------------------------------
def test_names_never_used_as_primary_key_two_codes_same_name_stay_separate():
    """CODE1 (official-only, real score) and CODE2 (DB-only) share the
    exact same name. They must NEVER be merged into one entity just
    because the names match — each keeps its own, independent
    classification (CODE1 correctly still FAILs on its own real
    evidence gap: OFFICIAL_COMPLETE_MISSING_IN_DB; CODE2 still gets its
    own DB_NOT_IN_OFFICIAL). The shared name only ever adds an
    ADDITIONAL, separate POSSIBLE_IDENTITY_MISMATCH hint on top — it
    never substitutes for, or auto-resolves, either code's own
    evidence-based classification."""
    entry = {"CODE1": _np("CODE1", name="김하니"), "CODE2": _np("CODE2", name="김하니")}
    official = {"CODE1": _np("CODE1", name="김하니", position=1, position_display="1", round_score=69, score_to_par=-3)}
    db = {"CODE2": _np("CODE2", name="김하니", position=1, position_display="1", round_score=70, score_to_par=-2)}

    result = reconcile_round(entry, official, db, round_number=1)
    # never merged into one entity: both codes remain individually tracked.
    assert "CODE1" in result.official_not_in_db
    assert "CODE2" in result.db_not_in_official
    classes_by_code = {a["player_code"]: a["classification"] for a in result.anomalies}
    assert classes_by_code["CODE1"] == CLASS_OFFICIAL_MISSING_IN_DB
    assert classes_by_code["CODE2"] == CLASS_DB_NOT_IN_OFFICIAL
    # same-name-different-code pairing is an ADDITIONAL, separate hint — never a merge, never used
    # to silently resolve either code's own real-evidence-based classification above.
    identity_anomalies = [a for a in result.anomalies if a["classification"] == CLASS_POSSIBLE_IDENTITY_MISMATCH]
    assert len(identity_anomalies) == 1
    assert identity_anomalies[0]["player_code"] == "CODE1/CODE2"
    # CODE1's real evidence gap correctly drives the verdict to FAIL — the identity hint doesn't
    # soften or replace that real finding.
    assert result.verdict == VERDICT_FAIL
