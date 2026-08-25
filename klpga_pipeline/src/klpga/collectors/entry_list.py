"""Entry-list collector — real /web/tourInfo/entry adapter.

Confirmed via manual browser Network capture, then cross-checked against
the full raw HTML the user pasted verbatim (see
klpga.parsers.entry_list_parser and tests/fixtures/entry_list_sample.html):

  GET https://klpga.co.kr/web/tourInfo/entry?gameCode=<code>
  response: text/html; charset=UTF-8

This module is read-only with respect to tournament_master, player_master,
player_event, player_round and the production 100-tournament dataset — it
never writes to any of them. Matching functions below only SELECT against
player_master to report matched/unmatched counts.

`build_tournament_entry_rows` below is a pure function (no DB access) that
shapes parsed EntryRows into tournament_entry row dicts — the actual write
(via klpga.db.upsert.upsert_tournament_entry) happens in
scripts/15_collect_entry_list.py, matching this project's convention of
keeping DB writes in the orchestration script rather than the collector.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from klpga import config
from klpga.http_client import PoliteHttpClient
from klpga.parsers.entry_list_parser import EntryRow, EntryListParseResult, parse_entry_list_html


def fetch_entry_list(client: PoliteHttpClient, game_code: str) -> str:
    """Fetch the raw entry-list HTML for one gameCode. Returns the page
    text as-is — parsing is a separate step (see
    klpga.parsers.entry_list_parser.parse_entry_list_html)."""
    return client.get_text(config.ENTRY_LIST_ENDPOINT, params={"gameCode": game_code})


@dataclass
class MatchResult:
    matched: list[EntryRow] = field(default_factory=list)
    unmatched: list[EntryRow] = field(default_factory=list)
    duplicate_player_codes: list[str] = field(default_factory=list)

    @property
    def matched_count(self) -> int:
        return len(self.matched)

    @property
    def unmatched_count(self) -> int:
        return len(self.unmatched)


def match_entries_to_player_master(conn: sqlite3.Connection, entry_rows: list[EntryRow]) -> MatchResult:
    """Match entry-list rows against player_master by player_code (i.e.
    player_master.player_id — confirmed to be the same identity space,
    see klpga.collectors.aggregate where player_id is populated directly
    from the confirmed playerCode). Never fuzzy-matches by name. Every
    entrant is reported as matched or unmatched — none are silently
    discarded."""
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for row in entry_rows:
        seen[row.player_code] = seen.get(row.player_code, 0) + 1
    for code, count in seen.items():
        if count > 1:
            duplicates.append(code)

    codes = list(seen.keys())
    known_ids: set[str] = set()
    if codes:
        placeholders = ", ".join("?" for _ in codes)
        cursor = conn.execute(
            f"SELECT player_id FROM player_master WHERE player_id IN ({placeholders})",
            codes,
        )
        known_ids = {r[0] for r in cursor.fetchall()}

    result = MatchResult(duplicate_player_codes=sorted(duplicates))
    for row in entry_rows:
        if row.player_code in known_ids:
            result.matched.append(row)
        else:
            result.unmatched.append(row)
    return result


@dataclass
class EntryVsResultCrossCheck:
    game_code: str
    entry_count: int
    player_event_count: int
    intersection_count: int
    entry_only: list[str] = field(default_factory=list)   # player_codes in entry list but not in player_event
    result_only: list[str] = field(default_factory=list)  # player_codes in player_event but not in entry list


def cross_check_against_player_event(
    conn: sqlite3.Connection, game_code: str, entry_rows: list[EntryRow]
) -> EntryVsResultCrossCheck:
    """Compare an entry list's player_code set against a COMPLETED
    tournament's already-collected player_event.player_id set for the
    same game_code. Per the investigation brief, the two lists are NOT
    assumed to be identical: withdrawals, late changes, and DNS players
    may legitimately differ — this only reports the sets and their
    differences, it never treats a mismatch as an error."""
    entry_codes = {row.player_code for row in entry_rows}
    cursor = conn.execute(
        "SELECT DISTINCT player_id FROM player_event WHERE game_code = ?",
        (game_code,),
    )
    result_codes = {r[0] for r in cursor.fetchall()}

    return EntryVsResultCrossCheck(
        game_code=game_code,
        entry_count=len(entry_codes),
        player_event_count=len(result_codes),
        intersection_count=len(entry_codes & result_codes),
        entry_only=sorted(entry_codes - result_codes),
        result_only=sorted(result_codes - entry_codes),
    )


def build_tournament_entry_rows(
    game_code: str,
    entry_rows: list[EntryRow],
    source: str,
    collected_at: str,
) -> list[dict]:
    """Shape parsed EntryRows into tournament_entry row dicts, ready for
    klpga.db.upsert.upsert_tournament_entry. Only the fields genuinely
    confirmed on the live entry-list page are included — no
    entry_status/WD/DNS or any other unconfirmed field is added here.
    Pure function: no DB access, no fabrication of any field not already
    present on `entry_rows`."""
    return [
        {
            "game_code": game_code,
            "player_code": row.player_code,
            "player_name_display": row.player_name,
            "nationality": row.nationality,
            "qualification_category": row.qualification_category,
            "qualification_reason": row.qualification_reason,
            "source": source,
            "collected_at": collected_at,
        }
        for row in entry_rows
    ]
