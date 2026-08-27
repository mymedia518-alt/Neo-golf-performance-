"""Official-vs-DB round reconciliation — ONE reusable data-quality gate
for every NEO round transition (PRE->R1, R1->R2, R2->R3, R3->FINAL).

Reuses existing, already-validated collector/parser infrastructure —
never a second scraper:
  - klpga.collectors.entry_list.fetch_entry_list /
    klpga.parsers.entry_list_parser.parse_entry_list_html (real entry list)
  - klpga.collectors.leaderboard.fetch_round_leaderboard /
    klpga.parsers.leaderboard_parser.parse_round_leaderboard_html (real
    official round leaderboard)
  - klpga.collectors.aggregate.merge_player_rows (the SAME round-scoped
    score/to-par/rank extraction scripts 02/04/05 already use — reused
    here verbatim, not reimplemented)
  - klpga.parsers.leaderboard_parser.parse_rank (the SAME tie-rank/
    status text parser, reused for DB's finish_position_after_round so
    "T27" parses identically on both sides of the comparison)

======================================================================
IDENTITY DISCIPLINE
======================================================================
player_code is the ONLY primary join key across ENTRY / OFFICIAL /
DB. Names are read and compared only as SECONDARY diagnostic
evidence — two records are never merged just because their names look
alike, and a name difference for the SAME player_code is never
silently ignored either (see NAME_MISMATCH below).

======================================================================
PRODUCT RULE — field size is not a target
======================================================================
ENTRY count, OFFICIAL count, and DB count are never forced to agree.
Golf is an individual sport; a player can legitimately not have a
result for a round (WD/DQ/DNS/unknown). This module NEVER fabricates
a score, position, or probability to preserve a headcount — an
unresolved/absent player is reported, never filled in.

======================================================================
CLASSIFICATION
======================================================================
Per player_code, one of:
  MATCHED                        — consistent across the sources compared
  ENTRY_ABSENT_FROM_OFFICIAL_AND_DB  (WARN) — in ENTRY only; no real
                                    round data anywhere; possible DNS/
                                    WD/DQ/unknown, never fabricated
  OFFICIAL_COMPLETE_MISSING_IN_DB (FAIL) — official shows a real,
                                    completed round result but the DB
                                    has no row for that round at all —
                                    a real collection gap
  SCORE_MISMATCH                 (FAIL) — official round_score/
                                    score_to_par disagrees with DB's
  NAME_MISMATCH                  (FAIL) — same player_code, but
                                    OFFICIAL and DB disagree on the
                                    player's name — identity cannot be
                                    safely reconciled without a human
  POSITION_MISMATCH              (WARN, reported not gate-blocking) —
                                    rank disagreement only, everything
                                    else consistent (tie-numbering
                                    noise is common and not itself
                                    proof of a real data defect)
  DB_NOT_IN_OFFICIAL             (WARN) — DB has a round row the
                                    official leaderboard doesn't show
                                    for this fetch
  POSSIBLE_IDENTITY_MISMATCH     (WARN) — a code in OFFICIAL_NOT_IN_DB
                                    and a DIFFERENT code in
                                    DB_NOT_IN_OFFICIAL share the exact
                                    same normalized name — flagged for
                                    human review, NEVER auto-merged
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from klpga.collectors.aggregate import merge_player_rows
from klpga.parsers.leaderboard_parser import PlayerRoundRow, parse_rank

VERDICT_PASS = "PASS"
VERDICT_WARN = "WARN"
VERDICT_FAIL = "FAIL"

CLASS_MATCHED = "MATCHED"
CLASS_ENTRY_ABSENT = "ENTRY_ABSENT_FROM_OFFICIAL_AND_DB"
CLASS_OFFICIAL_MISSING_IN_DB = "OFFICIAL_COMPLETE_MISSING_IN_DB"
CLASS_SCORE_MISMATCH = "SCORE_MISMATCH"
CLASS_NAME_MISMATCH = "NAME_MISMATCH"
CLASS_POSITION_MISMATCH = "POSITION_MISMATCH"
CLASS_DB_NOT_IN_OFFICIAL = "DB_NOT_IN_OFFICIAL"
CLASS_POSSIBLE_IDENTITY_MISMATCH = "POSSIBLE_IDENTITY_MISMATCH"

_FAIL_CLASSES = {CLASS_OFFICIAL_MISSING_IN_DB, CLASS_SCORE_MISMATCH, CLASS_NAME_MISMATCH}
_WARN_CLASSES = {CLASS_ENTRY_ABSENT, CLASS_POSITION_MISMATCH, CLASS_DB_NOT_IN_OFFICIAL, CLASS_POSSIBLE_IDENTITY_MISMATCH}


def _normalize_name(name) -> str:
    return " ".join(str(name or "").split()).casefold()


@dataclass(frozen=True)
class NormalizedPlayer:
    player_code: str
    player_name: Optional[str]
    position_display: Optional[str]
    position: Optional[int]
    round_score: Optional[int]
    score_to_par: Optional[int]
    status: Optional[str]


def normalize_entry_rows(entry_rows) -> dict[str, NormalizedPlayer]:
    """entry_rows: list[klpga.parsers.entry_list_parser.EntryRow]."""
    return {
        row.player_code: NormalizedPlayer(
            player_code=row.player_code, player_name=row.player_name,
            position_display=None, position=None, round_score=None, score_to_par=None, status=None,
        )
        for row in entry_rows
    }


def normalize_official_round(rows: list[PlayerRoundRow], round_number: int) -> dict[str, NormalizedPlayer]:
    """rows: the result of klpga.collectors.leaderboard.fetch_round_leaderboard
    (or parse_round_leaderboard_html) for exactly this round_number. Reuses
    klpga.collectors.aggregate.merge_player_rows — the SAME round-scoped
    score/to-par/rank extraction the real collector already uses — rather
    than re-deriving it."""
    merged = merge_player_rows({round_number: rows})
    out: dict[str, NormalizedPlayer] = {}
    for code, entry in merged.items():
        out[code] = NormalizedPlayer(
            player_code=code, player_name=entry["player_name"],
            position_display=entry["rank_display"], position=entry["rank"],
            round_score=entry["round_scores"].get(round_number),
            score_to_par=entry["round_to_par"].get(round_number),
            status=entry["status"],
        )
    return out


def normalize_db_round(conn: sqlite3.Connection, game_code: str, round_number: int) -> dict[str, NormalizedPlayer]:
    rows = conn.execute(
        "SELECT player_id, player_name, round_score, round_to_par, finish_position_after_round "
        "FROM player_round WHERE game_code = ? AND round_number = ?",
        (game_code, round_number),
    ).fetchall()
    out: dict[str, NormalizedPlayer] = {}
    for player_id, player_name, round_score, round_to_par, finish_position_after_round in rows:
        _display, position, _tie, _status = parse_rank(finish_position_after_round)
        out[player_id] = NormalizedPlayer(
            player_code=player_id, player_name=player_name,
            position_display=finish_position_after_round, position=position,
            round_score=round_score, score_to_par=round_to_par, status=None,
        )
    return out


@dataclass(frozen=True)
class ReconciliationResult:
    round_number: int
    entry: dict[str, NormalizedPlayer]
    official: dict[str, NormalizedPlayer]
    db: dict[str, NormalizedPlayer]

    entry_and_official_and_db: set
    entry_only: set
    official_only: set
    db_only: set
    official_not_in_db: set
    db_not_in_official: set

    anomalies: list[dict]
    """[{"player_code", "classification", "detail"}, ...] — every
    player_code with a non-MATCHED classification, evidence-only."""

    verdict: str
    eligible: list[str]
    excluded: list[str]
    unresolved: list[str]


def reconcile_round(
    entry: dict[str, NormalizedPlayer],
    official: dict[str, NormalizedPlayer],
    db: dict[str, NormalizedPlayer],
    round_number: int,
) -> ReconciliationResult:
    """Pure function — no I/O, no DB writes, no fabrication. Every
    output field is derived strictly from the three already-normalized
    inputs."""
    entry_codes = set(entry)
    official_codes = set(official)
    db_codes = set(db)

    entry_and_official_and_db = entry_codes & official_codes & db_codes
    entry_only = entry_codes - official_codes - db_codes
    official_only = official_codes - entry_codes - db_codes
    db_only = db_codes - entry_codes - official_codes
    official_not_in_db = official_codes - db_codes
    db_not_in_official = db_codes - official_codes

    anomalies: list[dict] = []
    eligible: list[str] = []
    excluded: list[str] = []
    unresolved: list[str] = []

    all_codes = entry_codes | official_codes | db_codes
    for code in sorted(all_codes):
        e, o, d = entry.get(code), official.get(code), db.get(code)

        if o is not None and d is not None:
            name_mismatch = (
                o.player_name is not None and d.player_name is not None
                and _normalize_name(o.player_name) != _normalize_name(d.player_name)
            )
            score_mismatch = o.round_score != d.round_score or o.score_to_par != d.score_to_par
            position_mismatch = o.position != d.position
            if name_mismatch:
                anomalies.append({
                    "player_code": code, "classification": CLASS_NAME_MISMATCH,
                    "detail": f"official player_name={o.player_name!r} vs DB player_name={d.player_name!r}",
                })
                unresolved.append(code)
                continue
            if score_mismatch:
                anomalies.append({
                    "player_code": code, "classification": CLASS_SCORE_MISMATCH,
                    "detail": f"official round_score={o.round_score!r}/score_to_par={o.score_to_par!r} vs "
                              f"DB round_score={d.round_score!r}/score_to_par={d.score_to_par!r}",
                })
                unresolved.append(code)
                continue
            if position_mismatch:
                anomalies.append({
                    "player_code": code, "classification": CLASS_POSITION_MISMATCH,
                    "detail": f"official position={o.position_display!r} vs DB position={d.position_display!r}",
                })
            eligible.append(code)
            continue

        if o is not None and d is None:
            # Official shows this player with a real round result but DB has no row at all.
            anomalies.append({
                "player_code": code, "classification": CLASS_OFFICIAL_MISSING_IN_DB,
                "detail": f"official round_score={o.round_score!r} score_to_par={o.score_to_par!r} "
                          f"position={o.position_display!r} status={o.status!r} — no DB row for round {round_number}",
            })
            unresolved.append(code)
            continue

        if o is None and d is not None:
            anomalies.append({
                "player_code": code, "classification": CLASS_DB_NOT_IN_OFFICIAL,
                "detail": f"DB round_score={d.round_score!r} score_to_par={d.score_to_par!r} "
                          f"position={d.position_display!r} — not present in this official round fetch",
            })
            unresolved.append(code)
            continue

        # o is None and d is None -> in ENTRY only (or nowhere useful).
        if code in entry_only:
            anomalies.append({
                "player_code": code, "classification": CLASS_ENTRY_ABSENT,
                "detail": "in ENTRY field, no official round result and no DB round row — possible DNS/WD/DQ/"
                          "unknown; not fabricated, not assumed",
            })
            excluded.append(code)

    # POSSIBLE_IDENTITY_MISMATCH — a code official-has-but-db-doesn't paired with a DIFFERENT
    # code db-has-but-official-doesn't, sharing the exact same normalized name. Name used only
    # as SECONDARY evidence tied to the primary player_code-based set difference — never a merge.
    official_missing_names = {
        code: _normalize_name(official[code].player_name) for code in official_not_in_db if official[code].player_name
    }
    db_missing_names = {
        code: _normalize_name(db[code].player_name) for code in db_not_in_official if db[code].player_name
    }
    for o_code, o_name in official_missing_names.items():
        for d_code, d_name in db_missing_names.items():
            if o_code != d_code and o_name and o_name == d_name:
                anomalies.append({
                    "player_code": f"{o_code}/{d_code}", "classification": CLASS_POSSIBLE_IDENTITY_MISMATCH,
                    "detail": f"official player_code={o_code!r} and DB player_code={d_code!r} share the same "
                              f"normalized name {o_name!r} — flagged for human review, NOT auto-merged",
                })

    fail_hit = any(a["classification"] in _FAIL_CLASSES for a in anomalies)
    warn_hit = any(a["classification"] in _WARN_CLASSES for a in anomalies)
    verdict = VERDICT_FAIL if fail_hit else (VERDICT_WARN if warn_hit else VERDICT_PASS)

    return ReconciliationResult(
        round_number=round_number, entry=entry, official=official, db=db,
        entry_and_official_and_db=entry_and_official_and_db, entry_only=entry_only,
        official_only=official_only, db_only=db_only,
        official_not_in_db=official_not_in_db, db_not_in_official=db_not_in_official,
        anomalies=anomalies, verdict=verdict,
        eligible=sorted(eligible), excluded=sorted(excluded), unresolved=sorted(unresolved),
    )
