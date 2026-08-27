"""Player-level diagnostic audit for a frozen NEO WIN v0.1 snapshot —
read-only, never touches the frozen artifact, never re-derives a
different prediction. Built for the Seo Gyo-rim / Park Hyun-kyung
BETA #001 audit but not hardcoded to either player.

======================================================================
"RECONSTRUCT THE EXACT FROZEN INPUT" — WITHOUT RERUNNING
======================================================================
Every RAW feature value (prior_avg_round_score_to_par, prior_recent_
form_10, neo_consistency_stddev, official_metrics) that actually
entered the frozen prediction is already stored verbatim in the
snapshot's `NeoWinEntrantSnapshot` rows — `frozen_player_features`
below reads those directly, never recomputes them. This satisfies "do
not rerun with today's data and call it equivalent" for the values
themselves.

The FITTED model (tau, per-feature shrinkage pop_mean/pop_std/k) is
NOT persisted in the archive schema — only the resulting win_probability
is. To decompose the frozen probability into per-feature contributions,
`recompute_and_verify_fit` re-fits the model using the SAME cutoff_date
the snapshot recorded (`klpga.neo_win.dataset.build_neo_win_live_
training_rows`), which is a DETERMINISTIC function of every tournament
STRICTLY BEFORE that cutoff — data this project treats as an immutable,
already-validated historical record (never edited after the fact). The
refit is therefore mathematically identical to what freeze time
computed, not "different data" — and this module PROVES that rather
than asserting it: it recomputes the full field's probabilities and
compares every one against the frozen snapshot's stored values. Any
mismatch is reported as a first-class finding (real drift, e.g. the
historical corpus changed), never silently ignored.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from klpga.neo_win.archive import NeoWinEntrantSnapshot, NeoWinPredictionSnapshot
from klpga.neo_win.dataset import build_neo_win_live_field, build_neo_win_live_training_rows
from klpga.neo_win.model import build_feature_columns, fit_neo_win_model, predict_neo_win_model


# ---------------------------------------------------------------
# Step 5 — how wins are treated. A pure code fact, needs no data.
# ---------------------------------------------------------------


def check_win_feature_representation() -> dict:
    from klpga.neo_win.model import BASE_FEATURES

    win_named_features = [f for f in BASE_FEATURES if "win" in f.lower()]
    return {
        "win_feature": win_named_features if win_named_features else "NONE",
        "how_wins_enter_model": (
            "Not directly. klpga.neo_win.model.BASE_FEATURES = "
            f"{BASE_FEATURES} contains no win-count or win-flag feature. "
            "klpga.backtest.point_in_time_features.PointInTimeFeatures DOES compute "
            "prior_wins for every player, but klpga.neo_win.dataset.augment_rows_with_"
            "neo_features / build_neo_win_live_field never copy it into a model feature "
            "column — it is computed and then discarded. A win can only influence the "
            "model INDIRECTLY, through prior_recent_form_10 and prior_avg_round_score_to_"
            "par, and only to the extent that tournament's score_to_par pulls those "
            "rolling averages down — a win is never counted as a win by the model."
        ),
        "code_path": "klpga.neo_win.model.BASE_FEATURES (fixed tuple, no wins field)",
    }


# ---------------------------------------------------------------
# Step 1 — identity
# ---------------------------------------------------------------


def audit_player_identity(conn: sqlite3.Connection, player_name: str, game_code: Optional[str] = None) -> dict:
    """Real, evidence-only identity trace for every row this exact
    displayed name appears under. Never assumes a single player_code is
    correct — reports every one found and flags a mismatch."""
    player_master_rows = conn.execute(
        "SELECT player_id, player_name FROM player_master WHERE player_name = ?", (player_name,)
    ).fetchall()
    player_event_codes = {
        row[0] for row in conn.execute(
            "SELECT DISTINCT player_id FROM player_event WHERE player_name = ?", (player_name,)
        )
    }
    tournament_entry_codes: set[str] = set()
    if game_code is not None:
        tournament_entry_codes = {
            row[0] for row in conn.execute(
                "SELECT DISTINCT player_code FROM tournament_entry WHERE game_code = ? AND player_name_display = ?",
                (game_code, player_name),
            )
        }

    player_master_ids = {row[0] for row in player_master_rows}
    all_ids = player_master_ids | player_event_codes | tournament_entry_codes
    consistent = len(all_ids) <= 1 and len(player_master_ids) == 1

    if not player_master_ids and not player_event_codes and not tournament_entry_codes:
        status = "BROKEN"
    elif consistent:
        status = "CLEAN"
    else:
        status = "PARTIAL"

    return {
        "player_name": player_name,
        "player_master_ids": sorted(player_master_ids),
        "player_event_player_ids": sorted(player_event_codes),
        "tournament_entry_player_codes": sorted(tournament_entry_codes),
        "all_identifiers": sorted(all_ids),
        "identity_deterministic": consistent,
        "status": status,
    }


# ---------------------------------------------------------------
# Step 2 — 2026 season audit, from DB result rows only
# ---------------------------------------------------------------


def audit_2026_season(conn: sqlite3.Connection, player_id: str) -> dict:
    """Every 2026 player_event row for `player_id`, cross-checked
    against tournament_master.winner (the winner's NAME, an
    INDEPENDENT field from finish_position — never inferred from score
    alone). A "confirmed win" requires BOTH finish_position_numeric==1
    AND tournament_master.winner matching this player's own name;
    disagreement is reported, never silently resolved either way."""
    rows = conn.execute(
        "SELECT pe.event_id, tm.event_name, tm.start_date, tm.end_date, pe.finish_position, "
        "pe.finish_position_numeric, pe.made_cut, pe.withdrawn, pe.disqualified, pe.rounds_played, "
        "pe.total_score, pe.score_to_par, tm.winner, pe.player_name "
        "FROM player_event pe JOIN tournament_master tm ON tm.event_id = pe.event_id "
        "WHERE pe.player_id = ? AND pe.season = 2026 ORDER BY tm.start_date, tm.end_date",
        (player_id,),
    ).fetchall()

    appearances = []
    confirmed_wins = 0
    label_only_wins = 0
    top3 = top5 = top10 = cuts = wd_dq = 0
    finishes_for_avg: list[int] = []
    for (event_id, event_name, start_date, end_date, finish_position, finish_position_numeric, made_cut,
         withdrawn, disqualified, rounds_played, total_score, score_to_par, tm_winner, player_name) in rows:
        finish_numeric_is_win = finish_position_numeric == 1
        winner_field_agrees = tm_winner is not None and tm_winner == player_name
        confirmed_win = finish_numeric_is_win and winner_field_agrees
        if finish_numeric_is_win:
            label_only_wins += 1
        if confirmed_win:
            confirmed_wins += 1
        if finish_position_numeric is not None:
            if finish_position_numeric <= 3:
                top3 += 1
            if finish_position_numeric <= 5:
                top5 += 1
            if finish_position_numeric <= 10:
                top10 += 1
            finishes_for_avg.append(finish_position_numeric)
        if made_cut:
            cuts += 1
        if withdrawn or disqualified:
            wd_dq += 1
        appearances.append(
            {
                "event_id": event_id,
                "event_name": event_name,
                "date": start_date or end_date,
                "finish_position": finish_position,
                "finish_position_numeric": finish_position_numeric,
                "made_cut": bool(made_cut),
                "withdrawn": bool(withdrawn),
                "disqualified": bool(disqualified),
                "rounds_played": rounds_played,
                "total_score": total_score,
                "score_to_par": score_to_par,
                "tournament_master_winner": tm_winner,
                "confirmed_win": confirmed_win,
                "finish_numeric_says_win_but_winner_field_disagrees": finish_numeric_is_win and not winner_field_agrees,
            }
        )

    return {
        "appearances": appearances,
        "starts_2026": len(appearances),
        "database_confirmed_wins": confirmed_wins,
        "finish_position_only_wins": label_only_wins,  # may exceed confirmed_wins if tm.winner disagrees/missing
        "top3": top3,
        "top5": top5,
        "top10": top10,
        "cuts": cuts,
        "wd_dq": wd_dq,
        "avg_finish": round(sum(finishes_for_avg) / len(finishes_for_avg), 2) if finishes_for_avg else None,
    }


# ---------------------------------------------------------------
# Step 3/4 — frozen feature reconstruction + contribution decomposition
# ---------------------------------------------------------------


def frozen_player_features(snapshot: NeoWinPredictionSnapshot, player_code: str) -> Optional[NeoWinEntrantSnapshot]:
    """The exact stored per-entrant record from the frozen archive —
    read only, no recomputation."""
    return next((e for e in snapshot.predictions if e.player_code == player_code), None)


def recompute_and_verify_fit(conn: sqlite3.Connection, snapshot: NeoWinPredictionSnapshot) -> dict:
    """Re-fits the model using the SAME game_code/cutoff_date the
    snapshot recorded, then compares every recomputed probability
    against the frozen value. See module docstring for why this is a
    verification, not a "rerun with different data.\""""
    cutoff_date_obj = date.fromisoformat(snapshot.cutoff_date)
    field_data = build_neo_win_live_field(conn, snapshot.game_code, cutoff_date_obj)
    field_rows = field_data["field_rows"]
    feature_columns = build_feature_columns(field_data["official_metric_context"]["selected_slots"])

    training_rows, _n = build_neo_win_live_training_rows(conn, snapshot.game_code, cutoff_date_obj)
    fitted = fit_neo_win_model(training_rows, feature_columns=feature_columns)
    recomputed_probs = predict_neo_win_model(fitted, field_rows)

    mismatches = []
    frozen_by_code = {e.player_code: e.win_probability for e in snapshot.predictions}
    for code, frozen_prob in frozen_by_code.items():
        recomputed = recomputed_probs.get(code)
        if recomputed is None:
            mismatches.append(f"{code}: present in frozen snapshot but not in the recomputed field")
        elif abs(recomputed - frozen_prob) > 1e-6:
            mismatches.append(f"{code}: frozen={frozen_prob!r} recomputed={recomputed!r}")

    return {
        "matches_frozen_exactly": not mismatches,
        "mismatches": mismatches,
        "fitted": fitted,
        "field_rows_by_code": {r["player_code"]: r for r in field_rows},
        "recomputed_probs": recomputed_probs,
    }


def decompose_contribution(fitted, row: dict) -> list[dict]:
    """Per-feature (raw_value, z_score, contribution_to_combined_score)
    for one player's field row, using the ACTUALLY-FITTED shrinkage
    params — equal weight (klpga.neo_win.model's v0.1 design), so
    contribution == z_score for every feature."""
    from klpga.models.candidates import apply_shrinkage_and_standardize

    out = []
    for f in fitted.feature_columns:
        raw = row.get(f)
        n = row.get(f"{f}_n")
        z = apply_shrinkage_and_standardize(raw, n, fitted.shrinkage[f])
        out.append({"feature": f, "raw_value": raw, "n": n, "z_score": round(z, 4), "contribution": round(z, 4)})
    return out


def largest_differences(contrib_a: list[dict], contrib_b: list[dict], top_n: int = 3) -> list[dict]:
    by_feature_b = {c["feature"]: c["contribution"] for c in contrib_b}
    diffs = [
        {"feature": c["feature"], "a_contribution": c["contribution"], "b_contribution": by_feature_b.get(c["feature"]),
         "difference": round(c["contribution"] - by_feature_b.get(c["feature"], 0.0), 4)}
        for c in contrib_a
    ]
    diffs.sort(key=lambda d: abs(d["difference"]), reverse=True)
    return diffs[:top_n]


# ---------------------------------------------------------------
# Step 6 — official metric exclusion for a specific player
# ---------------------------------------------------------------


def audit_official_metrics_for_player(conn: sqlite3.Connection, player_code: str, prior_season: int) -> dict:
    total, usable = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN validation_status = 'CLEAN' THEN 1 ELSE 0 END) "
        "FROM official_metric_value WHERE player_code = ? AND season = ?",
        (player_code, prior_season),
    ).fetchone()
    return {
        "player_code": player_code,
        "prior_season": prior_season,
        "rows_available": total or 0,
        "rows_usable_clean": usable or 0,
        "rows_flagged": (total or 0) - (usable or 0),
    }


# ---------------------------------------------------------------
# Step 7 — recent-form audit
# ---------------------------------------------------------------


def audit_recent_form(conn: sqlite3.Connection, player_id: str, cutoff_date_obj: date, limit: int = 10) -> list[dict]:
    """Last `limit` player_event rows strictly before cutoff_date_obj,
    newest first — the exact prior_events window prior_recent_form_N
    draws from (klpga.backtest.point_in_time_features)."""
    rows = conn.execute(
        "SELECT pe.event_id, tm.event_name, tm.start_date, tm.end_date, pe.finish_position, pe.score_to_par "
        "FROM player_event pe JOIN tournament_master tm ON tm.event_id = pe.event_id "
        "WHERE pe.player_id = ? AND (tm.start_date < ? OR (tm.start_date IS NULL AND tm.end_date < ?)) "
        "ORDER BY COALESCE(tm.start_date, tm.end_date) DESC LIMIT ?",
        (player_id, cutoff_date_obj.isoformat(), cutoff_date_obj.isoformat(), limit),
    ).fetchall()
    return [
        {
            "event_id": r[0], "event_name": r[1], "date": r[2] or r[3],
            "finish_position": r[4], "score_to_par": r[5],
        }
        for r in rows
    ]


# ---------------------------------------------------------------
# Step 8 — TOP10 sanity audit
# ---------------------------------------------------------------


def audit_top10(conn: sqlite3.Connection, snapshot: NeoWinPredictionSnapshot) -> list[dict]:
    codes = [e.player_code for e in snapshot.predictions[:10]]
    duplicate_codes = {c for c in codes if codes.count(c) > 1}

    flags = []
    for e in snapshot.predictions[:10]:
        warnings = []
        if e.player_code in duplicate_codes:
            warnings.append("duplicate_player_code")
        if not e.player_master_matched:
            warnings.append("identity_unmatched")
        if e.prior_events_n == 0 and e.win_probability > (1.0 / max(len(snapshot.predictions), 1)):
            warnings.append("zero_history_but_above_uniform_probability")
        if e.prior_recent_form_10_n and e.prior_recent_form_10_n < 3:
            warnings.append("abnormally_low_recent_form_sample_size")

        if any(w in ("duplicate_player_code", "identity_unmatched") for w in warnings):
            flag = "IDENTITY_WARNING"
        elif "zero_history_but_above_uniform_probability" in warnings:
            flag = "MODEL_WARNING"
        elif warnings:
            flag = "DATA_WARNING"
        else:
            flag = "CLEAN"

        flags.append(
            {
                "rank": e.rank, "player_code": e.player_code, "player_name": e.player_name,
                "win_probability": e.win_probability, "warnings": warnings, "flag": flag,
            }
        )
    return flags


# ---------------------------------------------------------------
# Step 9 — verdict
# ---------------------------------------------------------------


VERDICTS = (
    "LEGITIMATE_MODEL_RESULT",
    "DATA_INCOMPLETENESS",
    "IDENTITY_MAPPING_ERROR",
    "FEATURE_ENGINEERING_PROBLEM",
    "WEIGHTING_PROBLEM",
    "NORMALIZATION_PROBLEM",
    "OFFICIAL_METRIC_EXCLUSION_EFFECT",
    "OTHER_CONFIRMED_CAUSE",
)


def classify_verdict(
    *,
    identity_a: dict,
    identity_b: dict,
    verify: dict,
    top_diffs: list[dict],
    official_a: dict,
    official_b: dict,
) -> dict:
    """Rule-based, evidence-first — checked in priority order, never a
    guess. Returns {"verdict": ..., "evidence": [...]}."""
    if identity_a["status"] == "BROKEN" or identity_b["status"] == "BROKEN":
        return {"verdict": "IDENTITY_MAPPING_ERROR", "evidence": [
            f"identity status: a={identity_a['status']} b={identity_b['status']}"
        ]}
    if identity_a["status"] == "PARTIAL" or identity_b["status"] == "PARTIAL":
        return {"verdict": "IDENTITY_MAPPING_ERROR", "evidence": [
            f"non-deterministic identity resolution: a={identity_a}, b={identity_b}"
        ]}
    if not verify["matches_frozen_exactly"]:
        return {"verdict": "OTHER_CONFIRMED_CAUSE", "evidence": [
            "recomputed probabilities do not match the frozen snapshot — the historical corpus or "
            "identity resolution changed since the freeze", *verify["mismatches"][:10]
        ]}

    top_feature = top_diffs[0]["feature"] if top_diffs else None
    if top_feature and top_feature.startswith("neo_official_metric_"):
        official_gap = (official_a["rows_usable_clean"] == 0) != (official_b["rows_usable_clean"] == 0)
        if official_gap:
            return {"verdict": "OFFICIAL_METRIC_EXCLUSION_EFFECT", "evidence": [
                f"largest contribution gap is {top_feature}", f"official_a={official_a}", f"official_b={official_b}"
            ]}
        return {"verdict": "FEATURE_ENGINEERING_PROBLEM", "evidence": [
            f"largest contribution gap is {top_feature}, but coverage is symmetric between both players"
        ]}
    if top_feature == "neo_consistency_stddev":
        return {"verdict": "FEATURE_ENGINEERING_PROBLEM", "evidence": [
            "largest contribution gap is the new consistency feature — not present in the frozen M4 "
            "ladder this project also maintains, so this divergence is structural to NEO WIN v0.1's "
            "feature set, not a bug in it"
        ]}
    return {"verdict": "LEGITIMATE_MODEL_RESULT", "evidence": [
        f"largest contribution gap is {top_feature} (an existing, already-validated point-in-time feature)",
        "recomputation exactly matches the frozen snapshot", "identity resolution clean for both players",
    ]}
