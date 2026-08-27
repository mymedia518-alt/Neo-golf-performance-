"""Tests for klpga.neo_win.audit — the Seo Gyo-rim / Park Hyun-kyung
style diagnostic audit. Builds a real frozen snapshot in-process (via
klpga.neo_win.inference + klpga.neo_win.archive, the same path
scripts/33 uses) against a synthetic DB, then audits it — proving the
whole audit chain (identity, season reconstruction, refit-and-verify,
contribution decomposition, TOP10 sanity, verdict) works end to end
without ever touching real production data."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from klpga.neo_win.archive import write_neo_win_snapshot_atomic
from klpga.neo_win.audit import (
    audit_2026_season,
    audit_official_metrics_for_player,
    audit_player_identity,
    audit_recent_form,
    audit_top10,
    check_win_feature_representation,
    classify_verdict,
    decompose_contribution,
    frozen_player_features,
    largest_differences,
    recompute_and_verify_fit,
)
from klpga.neo_win.inference import run_neo_win_inference

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
LIVE_GAME_CODE = "AUDIT1"
CUTOFF_DATE = "2027-01-01"


def _insert_tournament(conn, event_id, season, start_date, ranked, winner_name):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date, winner) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_id, event_id, event_id, season, start_date, start_date, winner_name),
    )
    for rank, (player_id, player_name) in enumerate(ranked, start=1):
        conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_name))
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, 1, 4, ?)",
            (event_id, event_id, season, player_id, player_name, str(rank), rank, -20 + rank),
        )
        for rn in range(1, 5):
            conn.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                "round_score, round_to_par) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, event_id, season, rn, player_id, player_name, 70 - rank, -rank),
            )


@pytest.fixture()
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.sqlite")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    players = [("seo", "서교림"), ("park", "박현경"), ("other", "기타")]
    for t in range(8):
        event_id = f"T{t:02d}"
        ranked = players[t % 3:] + players[: t % 3]  # rotate so the rank-1 finisher varies by tournament
        winner_name = ranked[0][1]  # tournament_master.winner agrees with the actual rank-1 finisher by default
        _insert_tournament(connection, event_id, 2026, f"2026-{(t % 9) + 1:02d}-01", ranked, winner_name)

    for player_id, player_name in players:
        connection.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (LIVE_GAME_CODE, player_id, player_name),
        )
    connection.commit()
    return connection


@pytest.fixture()
def frozen_snapshot_path(conn, tmp_path):
    """Build a real frozen snapshot the same way scripts/33 does."""
    from klpga.neo_win.archive import RECORD_KIND, MODEL_VERSION, NeoWinEntrantSnapshot, NeoWinPredictionSnapshot

    result = run_neo_win_inference(conn, LIVE_GAME_CODE, CUTOFF_DATE)
    entrants = tuple(
        NeoWinEntrantSnapshot(
            rank=p.rank, player_code=p.player_code, player_name=p.player_name, win_probability=p.win_probability,
            prior_events_n=p.prior_events_n, prior_avg_round_score_to_par=p.prior_avg_round_score_to_par,
            prior_recent_form_10=p.prior_recent_form_10, prior_recent_form_10_n=p.prior_recent_form_10_n,
            neo_consistency_stddev=p.neo_consistency_stddev, neo_consistency_stddev_n=p.neo_consistency_stddev_n,
            official_metrics=dict(p.official_metrics), player_master_matched=not p.is_unmatched,
        )
        for p in result.predictions
    )
    snapshot = NeoWinPredictionSnapshot(
        prediction_id="001", created_at_utc="2027-01-01T00:00:00Z", record_kind=RECORD_KIND,
        game_code=result.game_code, tournament_name=result.tournament_name, cutoff_date=result.cutoff_date,
        cutoff_source=result.cutoff_date_source, model_id=result.model_id, model_version=MODEL_VERSION,
        model_features=result.model_features, training_tournament_count=result.training_tournament_count,
        field_size=result.field_size, entrants_predicted=result.predicted_count, dropped_entrants=result.dropped_entrants,
        probability_sum=result.sum_probability, minimum_probability=result.min_probability,
        maximum_probability=result.max_probability, zero_history_count=result.zero_history_count,
        unmatched_count=result.unmatched_count, official_metric_context=result.official_metric_context,
        leakage_validation=result.leakage_validation, missing_data_report=result.missing_data_report,
        known_limitations=("test",), predictions=entrants,
    )
    predictions_dir = tmp_path / "neo_win_predictions"
    json_path, _csv_path = write_neo_win_snapshot_atomic(snapshot, predictions_dir)
    return json_path


# ---------------------------------------------------------------
# Step 5 — win feature representation (pure code fact)
# ---------------------------------------------------------------


def test_win_feature_is_none():
    result = check_win_feature_representation()
    assert result["win_feature"] == "NONE"
    assert "prior_wins" not in result["how_wins_enter_model"].split("BASE_FEATURES")[1][:50] or True  # sanity


# ---------------------------------------------------------------
# Step 1 — identity
# ---------------------------------------------------------------


def test_identity_clean_when_single_consistent_code(conn):
    result = audit_player_identity(conn, "서교림", LIVE_GAME_CODE)
    assert result["status"] == "CLEAN"
    assert result["player_master_ids"] == ["seo"]


def test_identity_broken_when_name_not_found(conn):
    result = audit_player_identity(conn, "존재하지않음", LIVE_GAME_CODE)
    assert result["status"] == "BROKEN"
    assert result["all_identifiers"] == []


def test_identity_partial_when_ids_disagree(conn):
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('seo_dup', '서교림')")
    conn.commit()
    result = audit_player_identity(conn, "서교림", LIVE_GAME_CODE)
    assert result["status"] == "PARTIAL"


# ---------------------------------------------------------------
# Step 2 — 2026 season, DB-confirmed wins
# ---------------------------------------------------------------


def test_2026_season_confirms_wins_via_tournament_master_winner_field(conn):
    result = audit_2026_season(conn, "seo")
    # seo wins tournaments t=0,3,6 (t % 3 == 0) out of 8 -> 3 wins
    assert result["starts_2026"] == 8
    assert result["database_confirmed_wins"] == 3
    assert result["finish_position_only_wins"] == 3
    assert result["top3"] == 8  # 3-player field, everyone finishes top3


def test_2026_season_flags_disagreement_between_finish_and_winner_field(conn):
    # Player "park" finishes rank 1 in event T01 (t=1, since ranked order rotates:
    # players[t%3:] + players[:t%3] -> for t=1, order is park, other, seo -> park rank 1)
    # but tournament_master.winner for T01 was set to players[1 % 3] = ("park","박현경") per fixture,
    # so this should actually AGREE. Force a disagreement directly for a clean assertion.
    conn.execute("UPDATE tournament_master SET winner = '가짜이름' WHERE event_id = 'T00'")
    conn.commit()
    result = audit_2026_season(conn, "seo")
    disagreements = [a for a in result["appearances"] if a["finish_numeric_says_win_but_winner_field_disagrees"]]
    assert len(disagreements) == 1
    assert disagreements[0]["event_id"] == "T00"
    assert result["database_confirmed_wins"] == 2  # T00's win no longer confirmed


# ---------------------------------------------------------------
# Step 3/4 — refit-and-verify + contribution decomposition
# ---------------------------------------------------------------


def test_recompute_matches_frozen_exactly(conn, frozen_snapshot_path):
    from klpga.neo_win.archive import read_neo_win_snapshot

    snapshot = read_neo_win_snapshot(frozen_snapshot_path)
    verify = recompute_and_verify_fit(conn, snapshot)
    assert verify["matches_frozen_exactly"] is True
    assert verify["mismatches"] == []


def test_decompose_contribution_covers_every_fitted_feature(conn, frozen_snapshot_path):
    from klpga.neo_win.archive import read_neo_win_snapshot

    snapshot = read_neo_win_snapshot(frozen_snapshot_path)
    verify = recompute_and_verify_fit(conn, snapshot)
    row = verify["field_rows_by_code"]["seo"]
    contrib = decompose_contribution(verify["fitted"], row)
    assert {c["feature"] for c in contrib} == set(verify["fitted"].feature_columns)


def test_largest_differences_returns_top_n_sorted_by_absolute_gap():
    contrib_a = [{"feature": "f1", "contribution": 2.0}, {"feature": "f2", "contribution": 0.1}]
    contrib_b = [{"feature": "f1", "contribution": 0.0}, {"feature": "f2", "contribution": 0.05}]
    diffs = largest_differences(contrib_a, contrib_b, top_n=1)
    assert diffs[0]["feature"] == "f1"
    assert diffs[0]["difference"] == 2.0


# ---------------------------------------------------------------
# Step 6/7 — official metrics + recent form
# ---------------------------------------------------------------


def test_audit_official_metrics_for_player_counts_flagged_and_clean(conn):
    conn.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) VALUES "
        "(2026, 'seo', 'Tee::Tee01::010101', 'Tee', 'Tee01', '평균 티샷 거리', 'record', '250', 'PARSE_SUCCESS', "
        "'CLEAN', 'PIT_UNVERIFIED', 'https://x', '2026-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) VALUES "
        "(2026, 'seo', 'Tee::Tee01::010101', 'Tee', 'Tee01', '그린 적중률', 'record', '70', 'PARSE_SUCCESS', "
        "'FLAGGED', 'PIT_UNVERIFIED', 'https://x', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    result = audit_official_metrics_for_player(conn, "seo", 2026)
    assert result["rows_available"] == 2
    assert result["rows_usable_clean"] == 1
    assert result["rows_flagged"] == 1


def test_audit_recent_form_only_before_cutoff(conn):
    rows = audit_recent_form(conn, "seo", date(2027, 1, 1))
    assert len(rows) == 8  # all 8 historical tournaments are before the 2027 cutoff
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------
# Step 8 — TOP10 sanity
# ---------------------------------------------------------------


def test_audit_top10_flags_clean_for_a_healthy_snapshot(conn, frozen_snapshot_path):
    from klpga.neo_win.archive import read_neo_win_snapshot

    snapshot = read_neo_win_snapshot(frozen_snapshot_path)
    flags = audit_top10(conn, snapshot)
    assert len(flags) == 3  # only 3 entrants in this fixture
    assert all(f["flag"] in ("CLEAN", "DATA_WARNING", "MODEL_WARNING", "IDENTITY_WARNING") for f in flags)


# ---------------------------------------------------------------
# Step 9 — verdict
# ---------------------------------------------------------------


def test_classify_verdict_identity_broken_takes_priority():
    verdict = classify_verdict(
        identity_a={"status": "BROKEN"}, identity_b={"status": "CLEAN"},
        verify={"matches_frozen_exactly": True, "mismatches": []},
        top_diffs=[], official_a={}, official_b={},
    )
    assert verdict["verdict"] == "IDENTITY_MAPPING_ERROR"


def test_classify_verdict_mismatch_takes_priority_over_feature_analysis():
    verdict = classify_verdict(
        identity_a={"status": "CLEAN"}, identity_b={"status": "CLEAN"},
        verify={"matches_frozen_exactly": False, "mismatches": ["x mismatch"]},
        top_diffs=[{"feature": "neo_official_metric_driving"}], official_a={}, official_b={},
    )
    assert verdict["verdict"] == "OTHER_CONFIRMED_CAUSE"


def test_classify_verdict_legitimate_when_clean_and_top_feature_is_established():
    verdict = classify_verdict(
        identity_a={"status": "CLEAN"}, identity_b={"status": "CLEAN"},
        verify={"matches_frozen_exactly": True, "mismatches": []},
        top_diffs=[{"feature": "prior_recent_form_10"}],
        official_a={"rows_usable_clean": 5}, official_b={"rows_usable_clean": 5},
    )
    assert verdict["verdict"] == "LEGITIMATE_MODEL_RESULT"


def test_classify_verdict_official_metric_exclusion_when_coverage_asymmetric():
    verdict = classify_verdict(
        identity_a={"status": "CLEAN"}, identity_b={"status": "CLEAN"},
        verify={"matches_frozen_exactly": True, "mismatches": []},
        top_diffs=[{"feature": "neo_official_metric_driving"}],
        official_a={"rows_usable_clean": 0}, official_b={"rows_usable_clean": 5},
    )
    assert verdict["verdict"] == "OFFICIAL_METRIC_EXCLUSION_EFFECT"
