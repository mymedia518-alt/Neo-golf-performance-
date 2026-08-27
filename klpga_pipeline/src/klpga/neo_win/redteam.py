"""BETA #001-C Phase 11 — TOP20 red-team audit on an already-frozen
#001-C snapshot. Read-only: takes an already-loaded `NeoWinCPrediction
Snapshot` plus a read-only DB connection for independent cross-checks
(identity crosswalk, field membership, cutoff sanity) — never re-fits
or re-derives the prediction itself, and never writes to the DB.

Per player, checks (each check can only ESCALATE severity, never
downgrade another check's finding):
  1. Duplicate player_code within the TOP20 slice.
  2. Identity integrity — cross-checked against klpga.neo_win.identity_
     resolution.build_full_identity_crosswalk (independent of whatever
     identity resolution the prediction itself already used). Only the
     genuinely concerning statuses (AMBIGUOUS/BROKEN/UNMATCHED/not in
     the crosswalk at all) escalate — PARTIAL (a field player who
     simply has no official-metric coverage this season, a common,
     expected case) does not.
  3. Field membership — player_code must appear in tournament_entry
     for this game_code.
  4. History coverage — zero prior_events_n (cold start).
  5. Metric coverage — zero non-null feature values beyond the always-
     present base features.
  6. Cutoff sanity — the target tournament's own start_date must be on
     or after the prediction's cutoff_date (a live PRE prediction must
     never target an already-started/finished tournament).
  7. Winner-history correctness (internal consistency) — a windowed
     win count can never exceed its own sample size (e.g.
     wins_current_season > wins_current_season_n is a real, impossible
     value, not just an outlier).
  8. Extreme / normalization anomalies — a feature value more than 4
     population standard deviations from the FULL field's own mean for
     that feature (population computed from the snapshot's full
     `predictions`, not just the TOP20 slice), or a win_probability
     outside (0, 1).

Severity order (worst wins): CLEAN < DATA_WARNING < IDENTITY_WARNING <
MODEL_WARNING."""
from __future__ import annotations

import sqlite3
import statistics

STATUS_CLEAN = "CLEAN"
STATUS_DATA_WARNING = "DATA_WARNING"
STATUS_IDENTITY_WARNING = "IDENTITY_WARNING"
STATUS_MODEL_WARNING = "MODEL_WARNING"

_SEVERITY_ORDER = {STATUS_CLEAN: 0, STATUS_DATA_WARNING: 1, STATUS_IDENTITY_WARNING: 2, STATUS_MODEL_WARNING: 3}


def _escalate(current: str, new: str) -> str:
    return new if _SEVERITY_ORDER[new] > _SEVERITY_ORDER[current] else current


def _feature_population_stats(predictions, feature_names: tuple[str, ...]) -> dict[str, tuple[float, float]]:
    stats: dict[str, tuple[float, float]] = {}
    for name in feature_names:
        values = [e.feature_values.get(name) for e in predictions]
        values = [v for v in values if v is not None]
        if len(values) < 2:
            continue
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev > 0:
            stats[name] = (mean, stdev)
    return stats


def red_team_top20(c_snapshot, conn: sqlite3.Connection, *, top_n: int = 20) -> list[dict]:
    from klpga.neo_win.identity_resolution import (
        STATUS_AMBIGUOUS as IDENTITY_STATUS_AMBIGUOUS,
        STATUS_BROKEN as IDENTITY_STATUS_BROKEN,
        STATUS_UNMATCHED as IDENTITY_STATUS_UNMATCHED,
        build_full_identity_crosswalk,
    )

    _CONCERNING_IDENTITY_STATUSES = {IDENTITY_STATUS_AMBIGUOUS, IDENTITY_STATUS_BROKEN, IDENTITY_STATUS_UNMATCHED, "NOT_IN_CROSSWALK"}

    crosswalk_by_code = {row["player_code"]: row for row in build_full_identity_crosswalk(conn)}
    field_codes = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT player_code FROM tournament_entry WHERE game_code = ?", (c_snapshot.game_code,)
        )
    }
    cutoff_row = conn.execute(
        "SELECT start_date FROM tournament_master WHERE game_code = ?", (c_snapshot.game_code,)
    ).fetchone()
    target_start_date = cutoff_row[0] if cutoff_row else None

    pop_stats = _feature_population_stats(c_snapshot.predictions, c_snapshot.model_features)

    top_slice = sorted(c_snapshot.predictions, key=lambda e: e.rank)[:top_n]
    seen_codes: set[str] = set()
    reports: list[dict] = []

    for e in top_slice:
        flags: list[str] = []
        severity = STATUS_CLEAN

        if e.player_code in seen_codes:
            flags.append("duplicate player_code within TOP N slice")
            severity = _escalate(severity, STATUS_DATA_WARNING)
        seen_codes.add(e.player_code)

        crosswalk_row = crosswalk_by_code.get(e.player_code)
        identity_status = crosswalk_row["identity_status"] if crosswalk_row else "NOT_IN_CROSSWALK"
        if identity_status in _CONCERNING_IDENTITY_STATUSES:
            flags.append(f"identity_status={identity_status}")
            severity = _escalate(severity, STATUS_IDENTITY_WARNING)

        if e.player_code not in field_codes:
            flags.append("player_code not found in tournament_entry for this game_code")
            severity = _escalate(severity, STATUS_DATA_WARNING)

        if e.prior_events_n == 0:
            flags.append("zero prior tournament history (cold start, fully shrunk to training-fold mean)")
            severity = _escalate(severity, STATUS_DATA_WARNING)

        non_count_features = [k for k in e.feature_values if not k.endswith("_n")]
        covered = sum(1 for k in non_count_features if e.feature_values.get(k) is not None)
        if non_count_features and covered == 0:
            flags.append("zero feature coverage beyond base features")
            severity = _escalate(severity, STATUS_DATA_WARNING)

        if target_start_date is not None and target_start_date < c_snapshot.cutoff_date:
            flags.append(
                f"target tournament start_date ({target_start_date}) is BEFORE the prediction's own cutoff_date "
                f"({c_snapshot.cutoff_date}) — this is not a valid PRE-tournament prediction"
            )
            severity = _escalate(severity, STATUS_MODEL_WARNING)

        for base, n_key in (("wins_current_season", "wins_current_season_n"),
                            ("wins_last_10_starts", "wins_last_10_starts_n"),
                            ("wins_last_52_weeks", "wins_last_52_weeks_n")):
            v, n = e.feature_values.get(base), e.feature_values.get(n_key)
            if v is not None and n is not None and v > n:
                flags.append(f"{base}={v} exceeds its own sample size {n_key}={n} — impossible value")
                severity = _escalate(severity, STATUS_MODEL_WARNING)

        for name, (mean, stdev) in pop_stats.items():
            v = e.feature_values.get(name)
            if v is None:
                continue
            z = abs(v - mean) / stdev
            if z > 4:
                flags.append(f"extreme value: {name}={v!r} is {z:.1f} population std devs from the field mean")
                severity = _escalate(severity, STATUS_MODEL_WARNING)

        if not (0.0 < e.win_probability < 1.0):
            flags.append(f"win_probability out of (0,1): {e.win_probability!r}")
            severity = _escalate(severity, STATUS_MODEL_WARNING)

        reports.append(
            {"rank": e.rank, "player_code": e.player_code, "player_name": e.player_name, "status": severity, "flags": flags}
        )

    return reports
