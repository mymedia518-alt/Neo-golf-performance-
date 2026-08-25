"""Audit: does scripts/17_eligibility_report.py's "target tournaments
retained" at a given threshold mean the same population as
scripts/21_data_coverage_report.py's "usable target tournament(s)"?

Reported symptom (real production DB): threshold=5 in script 17 shows
95 target tournaments / 11,189 player-target rows, while script 21
shows 100 usable target tournaments / 11,850 rows. This test proves,
from the code, whether that is a bug or two different (correctly
implemented) population definitions:

  - klpga.backtest.walk_forward.build_walk_forward_dataset() computes
    ONE population: every tournament with a resolvable effective date
    AND a non-empty reconstructed field (`result.target_order` /
    `result.rows`). Both scripts 17 and 21 call this exact same
    function — there are not two competing implementations.
  - scripts/21_data_coverage_report.py reports that population
    UNCONDITIONALLY — it never filters by prior-history sufficiency.
  - scripts/17_eligibility_report.py's eligibility_sweep() reports the
    SAME population but ADDITIONALLY FILTERED to tournaments with
    `prior_tournament_count >= threshold`. At threshold=0 that filter
    removes nothing (every rank is >= 0), so it MUST reduce to exactly
    script 21's numbers — proven below by direct construction, not by
    running the real DB. At threshold=k>0 it is expected, by design,
    to report a strict subset: exactly the k chronologically-earliest
    tournaments (and their field rows) are removed, because
    `prior_tournament_count` is literally each tournament's 0-based
    rank in ascending date order (see walk_forward.py's
    `_ordered_target_tournaments`).

Conclusion asserted here: for a fully-populated corpus (nothing skipped
for a missing date or an empty field), eligible_tournament_count at
threshold=k is EXACTLY (total_tournament_count - k), and the removed
row count is EXACTLY the sum of field sizes of the k earliest
tournaments — matching the real symptom (100-5=95; 11,850-11,189=661
removed rows, consistent with ~132-avg-sized fields for the 5 earliest
tournaments, itself consistent with this project's confirmed real
KLPGA field sizes, e.g. the live-verified 120-entrant KG Ladies Open
field). This is the expected behavior of two different population
definitions sharing one underlying dataset, not a bug — no filtering
logic is changed by this test or by the wording fix that follows it.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from klpga.backtest.walk_forward import build_walk_forward_dataset, eligibility_sweep

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
SCRIPT_17_PATH = Path(__file__).resolve().parents[1] / "scripts" / "17_eligibility_report.py"
SCRIPT_21_PATH = Path(__file__).resolve().parents[1] / "scripts" / "21_data_coverage_report.py"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def script17():
    return _load_module(SCRIPT_17_PATH, "eligibility_report_script_pop")


@pytest.fixture()
def script21():
    return _load_module(SCRIPT_21_PATH, "data_coverage_report_script_pop")


@pytest.fixture()
def ten_tournament_corpus():
    """10 tournaments, chronologically ordered, each with a DIFFERENT
    field size (10, 11, 12, ..., 19 players) so the exact row-count
    delta from excluding the earliest k tournaments is independently
    computable: sum(10..10+k-1)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    field_sizes = {}
    for i in range(10):
        event_id = f"T{i:02d}"
        month = i + 1
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, f"2026-{month:02d}-01", f"2026-{month:02d}-04"),
        )
        field_size = 10 + i
        field_sizes[event_id] = field_size
        for p in range(field_size):
            player_id = f"P{i:02d}_{p:02d}"
            conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
            conn.execute(
                "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
                "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
                "(?, ?, 2026, ?, ?, '1', 1, 1, 4, -2)",
                (event_id, event_id, player_id, player_id),
            )
    conn.commit()
    return conn, field_sizes


def test_at_threshold_zero_eligibility_sweep_exactly_equals_the_unconditional_population(ten_tournament_corpus):
    """Proves, by direct assertion on the real return values (not
    inference from printed numbers), that threshold=0 is definitionally
    identical to the unconditional 'usable' population script 21
    reports — the two scripts are not computing different things at
    the baseline."""
    conn, _ = ten_tournament_corpus
    result = build_walk_forward_dataset(conn)
    sweep = eligibility_sweep(result, thresholds=(0,))
    row0 = sweep[0]

    assert row0["eligible_tournament_count"] == len(result.target_order) == 10
    assert row0["eligible_field_row_count"] == len(result.rows) == sum(10 + i for i in range(10))


def test_threshold_k_removes_exactly_the_k_earliest_tournaments(ten_tournament_corpus):
    """Proves the reported 95-vs-100 difference is exactly what
    prior_tournament_count = rank implies: threshold=k keeps
    (total - k) tournaments, dropping precisely the k earliest ones by
    date — not an arbitrary or buggy subset."""
    conn, field_sizes = ten_tournament_corpus
    result = build_walk_forward_dataset(conn)
    total_tournaments = len(result.target_order)
    total_rows = len(result.rows)

    for k in range(0, total_tournaments + 1):
        sweep = eligibility_sweep(result, thresholds=(k,))
        row = sweep[0]
        assert row["eligible_tournament_count"] == total_tournaments - k, f"threshold={k}"

        # The k earliest tournaments are T00..T{k-1} by construction
        # (ascending start_date). Their combined field size is the
        # exact expected row-count reduction.
        excluded_ids = [f"T{i:02d}" for i in range(k)]
        expected_removed_rows = sum(field_sizes[eid] for eid in excluded_ids)
        assert row["eligible_field_row_count"] == total_rows - expected_removed_rows, f"threshold={k}"


def test_script_17_and_21_agree_exactly_at_the_unconditional_baseline(script17, script21, ten_tournament_corpus, capsys):
    """End-to-end proof at the SCRIPT level (not just the library
    function): script 17's threshold=0 row and script 21's printed
    totals must be numerically identical, since both call
    build_walk_forward_dataset() on the same connection."""
    conn, _ = ten_tournament_corpus

    report17 = script17.run(conn, thresholds=(0,))
    out17 = capsys.readouterr().out
    outcome21 = script21.run(conn)
    out21 = capsys.readouterr().out

    result = build_walk_forward_dataset(conn)
    sweep = eligibility_sweep(result, thresholds=(0,))
    assert sweep[0]["eligible_tournament_count"] == len(result.target_order)
    assert sweep[0]["eligible_field_row_count"] == outcome21["total_rows"] == len(result.rows)

    # Both printed reports must surface the same underlying total row
    # count and tournament count somewhere in their text.
    assert str(len(result.rows)) in report17
    assert str(len(result.rows)) in out21
    assert str(len(result.target_order)) in out17


def test_reproduces_the_reported_symptom_shape_100_minus_5_equals_95():
    """A minimal, direct arithmetic reproduction of the exact reported
    symptom (100 usable, 95 at threshold=5) against a same-shaped
    100-tournament synthetic corpus, confirming the relationship holds
    at that scale too, not just at n=10."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    for i in range(100):
        event_id = f"E{i:03d}"
        day = (i % 28) + 1
        month = (i % 12) + 1
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2020, ?, ?)",
            (event_id, event_id, event_id, f"2020-{month:02d}-{day:02d}", f"2020-{month:02d}-{day:02d}"),
        )
        player_id = f"P{i:03d}"
        conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2020, ?, ?, '1', 1, 1, 4, -2)",
            (event_id, event_id, player_id, player_id),
        )
    conn.commit()

    result = build_walk_forward_dataset(conn)
    assert len(result.target_order) == 100
    sweep = eligibility_sweep(result, thresholds=(0, 5))
    assert sweep[0]["eligible_tournament_count"] == 100
    assert sweep[1]["eligible_tournament_count"] == 95
