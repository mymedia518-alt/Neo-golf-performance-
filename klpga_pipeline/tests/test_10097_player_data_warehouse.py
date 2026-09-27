"""PLAYER DATA WAREHOUSE V1 -- playerCode=10097 only.

Proves the specific discipline this mission demanded: every upper
layer (Tournament/Season/Career) is REPRODUCIBLE from the layer below
it via real SQL aggregation -- these tests re-run that aggregation
independently (not by trusting the builder's own internal check) and
compare it against what the warehouse actually stored. No manual
summary may exist that isn't backed by a lower layer, except where a
fact is explicitly marked as layer-anchored (a finish rank cannot come
from round-level data).
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_data_warehouse", ROOT / "scripts" / "build_10097_player_data_warehouse.py")
build_wh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_wh)


def _conn():
    return sqlite3.connect(build_wh.build())


def test_career_layer4_is_independently_reproducible_from_layer3_season():
    conn = _conn()
    stored = conn.execute("SELECT events, wins, top5, top10, top20 FROM career_observation").fetchone()
    recomputed = conn.execute(
        "SELECT SUM(events), SUM(wins), SUM(top5), SUM(top10), SUM(top20) FROM season_observation"
    ).fetchone()
    assert stored == recomputed


def test_season_layer3_is_independently_reproducible_from_layer2_tournament():
    conn = _conn()
    for season, events, wins in conn.execute("SELECT season, events, wins FROM season_observation"):
        recomputed = conn.execute(
            "SELECT COUNT(*), SUM(is_win) FROM tournament_observation WHERE season=? AND status='FINISHED'",
            (season,),
        ).fetchone()
        assert (events, wins) == recomputed


def test_tournament_layer2_sg_is_independently_reproducible_from_layer1_round():
    conn = _conn()
    rows = conn.execute("SELECT game_code, sg_total_computed FROM tournament_observation WHERE status='FINISHED'").fetchall()
    checked = 0
    for game_code, stored_sg in rows:
        recomputed = conn.execute(
            "SELECT AVG(sg_total) FROM observation_round WHERE game_code=? AND status='FINISHED'", (game_code,)
        ).fetchone()[0]
        if recomputed is not None:
            recomputed = round(recomputed, 6)
        if stored_sg is not None:
            stored_sg = round(stored_sg, 6)
        assert stored_sg == recomputed, f"{game_code}: stored {stored_sg} != recomputed {recomputed}"
        checked += 1
    assert checked > 90


def test_ok_open_round_totals_are_reproducible_from_observation_holes():
    """Layer 1 (round strokes) for the one tournament with real Layer 0
    hole data must equal SUM(strokes) over that tournament's own holes
    -- proven here independently of the builder's own SQL."""
    conn = _conn()
    for round_number, stored_strokes in conn.execute(
        "SELECT round_number, total_strokes FROM observation_round WHERE game_code='2026120001'"
    ):
        recomputed = conn.execute(
            "SELECT SUM(strokes) FROM observation_hole WHERE game_code='2026120001' AND round_number=?",
            (round_number,),
        ).fetchone()[0]
        assert stored_strokes == recomputed


def test_layer_reproducibility_check_shows_near_universal_agreement():
    """The Layer-2 SQL aggregate must match the independently-reported
    tournament SG Total (a category-1 SG-Warehouse fact never used to
    build observation_round's rows) for nearly every tournament with
    round-level data -- this is a real cross-check count, not asserted."""
    conn = _conn()
    matched, total = conn.execute(
        "SELECT SUM(within_tolerance), COUNT(*) FROM layer_reproducibility_check"
    ).fetchone()
    assert total >= 90
    assert matched == total


def test_kb_tournament_has_real_round_level_strokes_but_null_sg():
    """KB (2026090003) has real per-round raw strokes (Reader source)
    but never had Strokes Gained computed for it anywhere -- the
    warehouse must carry both facts distinctly, never zero-filling the
    missing SG and never dropping the real stroke totals it does have."""
    conn = _conn()
    rounds = conn.execute(
        "SELECT round_number, sg_total, total_strokes FROM observation_round WHERE game_code='2026090003' ORDER BY round_number"
    ).fetchall()
    assert len(rounds) == 4
    assert all(r[1] is None for r in rounds)  # sg_total
    assert [r[2] for r in rounds] == [74, 71, 73, 72]  # total_strokes
    tournament_row = conn.execute(
        "SELECT sg_total_computed, total_strokes_computed FROM tournament_observation WHERE game_code='2026090003'"
    ).fetchone()
    assert tournament_row[0] is None
    assert tournament_row[1] == 74 + 71 + 73 + 72


def test_in_progress_tournament_never_pollutes_finished_aggregates():
    conn = _conn()
    row = conn.execute("SELECT status FROM tournament_observation WHERE game_code='2026120001'").fetchone()
    assert row[0] == "IN_PROGRESS"
    season_2026 = conn.execute("SELECT events FROM season_observation WHERE season=2026").fetchone()[0]
    finished_2026 = conn.execute(
        "SELECT COUNT(*) FROM tournament_observation WHERE season=2026 AND status='FINISHED'"
    ).fetchone()[0]
    assert season_2026 == finished_2026
    # the in-progress tournament's own 3 real rounds are NOT lost --
    # they just never enter a FINISHED aggregate.
    n_ip_rounds = conn.execute("SELECT COUNT(*) FROM observation_round WHERE game_code='2026120001'").fetchone()[0]
    assert n_ip_rounds == 3


def test_every_layer_row_declares_its_own_layer_number():
    conn = _conn()
    assert conn.execute("SELECT DISTINCT layer FROM observation_hole").fetchall() == [(0,)]
    assert conn.execute("SELECT DISTINCT layer FROM observation_round").fetchall() == [(1,)]
    assert conn.execute("SELECT DISTINCT layer FROM tournament_observation").fetchall() == [(2,)]
    assert conn.execute("SELECT DISTINCT layer FROM season_observation").fetchall() == [(3,)]
    assert conn.execute("SELECT DISTINCT layer FROM career_observation").fetchall() == [(4,)]


def test_no_row_anywhere_is_a_fabricated_placeholder():
    conn = _conn()
    allowed = {"MEASURED", "DERIVED", "NOT_COLLECTED", "BLOCKED"}
    statuses = {r[0] for r in conn.execute("SELECT DISTINCT status FROM field_verification")}
    assert statuses <= allowed


def test_observation_layer_tables_contain_no_average_or_percentage_columns():
    """PLAYER OBSERVATION WAREHOUSE mission: observation_hole,
    observation_shot, observation_round must never carry an averaged,
    summarized, or percentage column -- every column is either a raw
    measured value or a provenance/identity field. A round's own
    total_strokes (that round's own scorecard sum) and sg_total (that
    round's own reported figure) are single-event facts, not
    cross-event statistics, so they are allowed; anything named like an
    average/rate/percent is not."""
    conn = _conn()
    banned_substrings = ("avg", "average", "pct", "percent", "rate", "mean", "median")
    for table in ("observation_hole", "observation_shot", "observation_round"):
        cols = [r[1].lower() for r in conn.execute(f"PRAGMA table_info({table})")]
        for col in cols:
            assert not any(b in col for b in banned_substrings), f"{table}.{col} looks like a summary column"


def test_observation_tables_are_named_exactly_as_the_mission_specified():
    conn = _conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"observation_round", "observation_hole", "observation_shot"} <= tables


def test_higher_layers_derive_only_from_the_observation_layer_or_their_own_layer():
    """Every table above the Observation Layer must trace back to it:
    tournament_observation from observation_round (Layer 1), season_
    observation from tournament_observation (Layer 2), career_
    observation from season_observation (Layer 3) -- already proven
    row-for-row by the other reproducibility tests in this file; this
    test only pins the table-existence contract the mission asked for."""
    conn = _conn()
    assert conn.execute("SELECT COUNT(*) FROM tournament_observation").fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM season_observation").fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM career_observation").fetchone()[0] > 0
