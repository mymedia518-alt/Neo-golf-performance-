"""Reconcile an expected finalist roster (e.g.
data/roster/r3_finalists_2026080001.csv) against a real official round
fetch and the real DB state for that round — built for
scripts/final_close_preflight.py's FINAL-close identity check.

Reuses klpga.neo_win.round_reconciliation.reconcile_round verbatim
(the SAME reusable data-quality gate every other round transition in
this project uses) with the roster standing in for its `entry`
argument — the classification semantics are identical, only the
REPORTED LABELS differ (a roster player absent from both official and
DB is "MISSING", not the full-field "EXCLUDED", since for a finalist
roster that is unexpected and needs real WD/DQ evidence, not assumed
CUT status).

WD/DQ status is never inferred from absence — it is read directly from
player_event.withdrawn/disqualified, the same real, evidence-backed
columns klpga.neo_win.player_status already uses.
"""
from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from klpga.neo_win.round_reconciliation import (
    NormalizedPlayer,
    ReconciliationResult,
    reconcile_round,
)


def load_roster_csv(path: Path) -> list[tuple[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [(row["player_code"], row["player_name"]) for row in reader]


def build_roster_normalized(roster_rows: list[tuple[str, str]]) -> dict[str, NormalizedPlayer]:
    return {
        code: NormalizedPlayer(
            player_code=code, player_name=name,
            position_display=None, position=None, round_score=None, score_to_par=None, status=None,
        )
        for code, name in roster_rows
    }


def query_wd_dq_status(conn: sqlite3.Connection, game_code: str, player_codes: list[str]) -> dict[str, dict]:
    """Real, evidence-backed WD/DQ flags from player_event — never
    inferred from a player simply being absent elsewhere."""
    if not player_codes:
        return {}
    placeholders = ",".join("?" for _ in player_codes)
    rows = conn.execute(
        f"SELECT player_id, withdrawn, disqualified, made_cut FROM player_event "
        f"WHERE game_code = ? AND player_id IN ({placeholders})",
        [game_code, *player_codes],
    ).fetchall()
    return {
        player_id: {"withdrawn": bool(withdrawn), "disqualified": bool(disqualified), "made_cut": bool(made_cut)}
        for player_id, withdrawn, disqualified, made_cut in rows
    }


@dataclass(frozen=True)
class FinalistReconciliationReport:
    round_number: int
    expected_finalists: int
    official_round_total: int
    official_round_in_roster: int
    db_round_total: int
    matched: list[str]
    missing: list[str]
    """Roster player_codes absent from BOTH the official round fetch AND
    the DB for this round — needs real WD/DQ evidence, never assumed."""
    extra: list[str]
    """player_codes present in the official round fetch but NOT in the
    expected roster — unexpected; could mean the roster is stale or an
    identity mismatch."""
    unresolved: list[str]
    """Roster player_codes reconcile_round classified as unresolved
    (official-vs-DB disagreement or a one-sided gap) — see `anomalies`
    for the exact classification per code."""
    wd: list[str]
    dq: list[str]
    anomalies: list[dict]
    verdict: str
    reconciliation: ReconciliationResult


def reconcile_finalists(
    conn: sqlite3.Connection,
    game_code: str,
    round_number: int,
    roster_rows: list[tuple[str, str]],
    official_normalized: dict[str, NormalizedPlayer],
    db_normalized: dict[str, NormalizedPlayer],
) -> FinalistReconciliationReport:
    roster_normalized = build_roster_normalized(roster_rows)
    roster_codes = set(roster_normalized)

    result = reconcile_round(roster_normalized, official_normalized, db_normalized, round_number)

    missing = sorted(result.excluded)  # roster codes: CLASS_ENTRY_ABSENT (no official, no db)
    extra = sorted(set(official_normalized) - roster_codes)
    unresolved = sorted(code for code in result.unresolved if code in roster_codes)
    matched = sorted(result.eligible)

    wd_dq_status = query_wd_dq_status(conn, game_code, sorted(roster_codes))
    wd = sorted(code for code, s in wd_dq_status.items() if s["withdrawn"])
    dq = sorted(code for code, s in wd_dq_status.items() if s["disqualified"])

    return FinalistReconciliationReport(
        round_number=round_number,
        expected_finalists=len(roster_rows),
        official_round_total=len(official_normalized),
        official_round_in_roster=len(set(official_normalized) & roster_codes),
        db_round_total=len(db_normalized),
        matched=matched, missing=missing, extra=extra, unresolved=unresolved,
        wd=wd, dq=dq,
        anomalies=[a for a in result.anomalies if a["player_code"] in roster_codes],
        verdict=result.verdict,
        reconciliation=result,
    )
