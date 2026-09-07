"""Shared, read-only R1-provenance evidence helpers used by both
scripts/45_audit_beta001c_r1.py (the full R1 audit) and
scripts/48_investigate_unexplained_r1_player.py (a single-player deep
dive). Extracted so both scripts compute evidence and classify with
the exact same logic — never two independently-maintained copies that
could silently drift apart.

Every function here is read-only (SELECT only) and never writes to the
DB or to any frozen prediction/history artifact. Classification is
always evidence-only: a positive DB fact (a timestamp, a name match,
an identity-crosswalk status) is required before any conclusion is
drawn; absence of evidence maps to UNRESOLVED/OTHER, never a guess.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga.neo_win.player_status import STATUS_WD


def r2_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 2", (game_code,)
    ).fetchone()[0]


def r1_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 1 AND round_to_par IS NOT NULL",
        (game_code,),
    ).fetchone()[0]


def r1_player_codes(conn: sqlite3.Connection, game_code: str) -> set:
    return {
        player_id
        for (player_id,) in conn.execute(
            "SELECT DISTINCT player_id FROM player_round WHERE game_code = ? AND round_number = 1 "
            "AND round_to_par IS NOT NULL",
            (game_code,),
        )
    }


def field_size(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT player_code) FROM tournament_entry WHERE game_code = ?", (game_code,)
    ).fetchone()[0]


def r1_row_detail(conn: sqlite3.Connection, game_code: str, player_code: str) -> Optional[dict]:
    """Full real detail for a player's round_number=1 player_round row
    — used only for provenance reporting, never to alter any already-
    frozen snapshot."""
    row = conn.execute(
        "SELECT player_name, round_score, round_to_par, finish_position_after_round "
        "FROM player_round WHERE game_code = ? AND round_number = 1 AND player_id = ?",
        (game_code, player_code),
    ).fetchone()
    if row is None:
        return None
    player_name, round_score, round_to_par, finish_position_after_round = row
    return {
        "player_name": player_name, "round_score": round_score, "round_to_par": round_to_par,
        "finish_position_after_round": finish_position_after_round,
        "is_completed_score": round_to_par is not None,
    }


def all_round_rows_for_player(conn: sqlite3.Connection, game_code: str, player_code: str) -> list[dict]:
    """Every real player_round row for this player across ALL round
    numbers (not just round_number=1). Read-only, no filter on
    round_to_par being non-null: a bare status row (if one ever
    existed) would show here too, distinct from a real completed
    score."""
    rows = conn.execute(
        "SELECT round_number, round_score, round_to_par, finish_position_after_round "
        "FROM player_round WHERE game_code = ? AND player_id = ? ORDER BY round_number",
        (game_code, player_code),
    ).fetchall()
    return [
        {
            "round_number": round_number, "round_score": round_score, "round_to_par": round_to_par,
            "finish_position_after_round": finish_position_after_round,
            "is_completed_score": round_to_par is not None,
        }
        for round_number, round_score, round_to_par, finish_position_after_round in rows
    ]


# Final-provenance-checkpoint taxonomy (for the snapshot's own disclosed
# missing_r1_data players), mapped from the shared classifier's real-
# evidence-only STATUS_* result.
PROVENANCE_CONFIRMED_WD = "CONFIRMED_WD"
PROVENANCE_CONFIRMED_DQ = "CONFIRMED_DQ"
PROVENANCE_CONFIRMED_DNS = "CONFIRMED_DNS"
PROVENANCE_LATE_R1_DATA = "LATE_R1_DATA"
PROVENANCE_DATA_MISSING = "DATA_MISSING"
PROVENANCE_OTHER = "OTHER"


def final_provenance_classification(status, *, has_late_r1_row: bool) -> str:
    """Maps the shared classifier's STATUS_* result (plus the separate,
    already-computed 'does this player now have a real R1 row in the
    DB that didn't exist at freeze time' fact) onto the R1 provenance
    checkpoint's own six-value taxonomy."""
    if has_late_r1_row:
        return PROVENANCE_LATE_R1_DATA
    if status is None:
        return PROVENANCE_OTHER
    if status.classification == STATUS_WD:
        return PROVENANCE_CONFIRMED_WD
    if status.classification == "DQ":
        return PROVENANCE_CONFIRMED_DQ
    if status.classification == "DNS":
        return PROVENANCE_CONFIRMED_DNS
    if status.classification == "COLLECTION_MISSING":
        return PROVENANCE_DATA_MISSING
    return PROVENANCE_OTHER


# Unexplained-player investigation taxonomy — for a real round_number=1
# row whose player_code is not present anywhere in the frozen R1
# snapshot at all (neither scored nor missing_r1_data). Distinct from
# FINAL PROVENANCE CLASSIFICATION above, which only ever applies to the
# snapshot's own disclosed missing_r1_data players.
UNEXPLAINED_PLAYER_CODE_CHANGED = "PLAYER_CODE_CHANGED"
UNEXPLAINED_DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
UNEXPLAINED_LATE_ENTRY_FIELD_CHANGE = "LATE_ENTRY_FIELD_CHANGE"
UNEXPLAINED_DB_MAPPING_ERROR = "DB_MAPPING_ERROR"
UNEXPLAINED_OTHER = "OTHER"
UNEXPLAINED_UNRESOLVED = "UNRESOLVED"


def normalize_name(name) -> str:
    return " ".join(str(name or "").split()).casefold()


def scan_raw_cache_for_player(cache_dir: Path, game_code: str, player_code: str) -> list[dict]:
    """Read-only scan of the raw HTTP cache (klpga.http_client's
    PoliteHttpClient, default data/raw_cache/http) for any cached
    response referencing this game_code, checking whether player_code
    also appears in that same cached response. Cache files are keyed
    by sha256(url+params), NOT addressable by game_code directly —
    this is a full scan of every cache file's own stored {url, params,
    body_text/body_json}, never a fabricated direct lookup. Gracefully
    returns [] if the cache directory doesn't exist, never errors."""
    if not cache_dir.exists():
        return []
    hits = []
    for path in sorted(cache_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        raw_text = json.dumps(data, ensure_ascii=False)
        if game_code not in raw_text:
            continue
        hits.append({
            "cache_file": str(path), "url": data.get("url"), "params": data.get("params"),
            "player_code_found_in_body": player_code in raw_text,
        })
    return hits


def entry_field_name_matches(conn: sqlite3.Connection, game_code: str, player_code: str, normalized_target: str) -> list[str]:
    """Real evidence: OTHER tournament_entry.player_code values (today's
    ENTRY_FIELD, not just the frozen PRE field) whose player_name_display
    normalizes to the exact same name as `normalized_target`. Distinct
    from the PRE-field-only and missing-players-only name checks —
    tournament_entry can contain names/codes added after PRE was
    frozen."""
    if not normalized_target:
        return []
    rows = conn.execute(
        "SELECT DISTINCT player_code, player_name_display FROM tournament_entry WHERE game_code = ?",
        (game_code,),
    ).fetchall()
    return sorted(
        code for code, name in rows
        if code != player_code and normalize_name(name) == normalized_target
    )


def find_entry_list_cache_file(cache_dir: Path, entry_list_url: str, game_code: str) -> Optional[dict]:
    """Locate the raw HTTP cache file for the real entry-list endpoint's
    GET request for this game_code (klpga.collectors.entry_list.
    fetch_entry_list / klpga.config.ENTRY_LIST_ENDPOINT with params=
    {"gameCode": game_code}) by reading each cache file's own stored
    {url, params} — never a precomputed hash guess. Returns
    {"path": Path, "mtime_utc": iso-8601 str, "body_text": str} for the
    first match, or None if no such cache file exists (cleared, never
    fetched, or fetched with different params).

    IMPORTANT CAVEAT (real code behavior, confirmed by reading klpga.
    http_client.PoliteHttpClient.get_text and klpga.collectors.
    entry_list.fetch_entry_list / scripts/15_collect_entry_list.py):
    the entry-list fetch always uses the SAME cache key for a given
    game_code (url + {"gameCode": game_code}), and get_text only
    WRITES the cache file on a real (non-cache-hit) fetch — every
    later run with use_cache=True (the default, never overridden by
    scripts/15) just replays the SAME cached bytes without touching
    the file. So this file's mtime is the timestamp of whichever real
    HTTP fetch most recently produced the CURRENTLY cached content —
    it is NOT necessarily the very first-ever fetch, and it does NOT
    tell you whether an EARLIER real fetch (now overwritten) ever
    existed. Report this mtime as what it is: the most recent known
    real-fetch time for the content on disk today, not a definitive
    'first seen' timestamp."""
    if not cache_dir.exists():
        return None
    for path in sorted(cache_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("url") != entry_list_url:
            continue
        if (data.get("params") or {}).get("gameCode") != game_code:
            continue
        mtime_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return {"path": path, "mtime_utc": mtime_utc, "body_text": data.get("body_text")}
    return None


def real_entry_field_codes_from_cached_html(body_text: str) -> set[str]:
    """Parse a cached entry-list HTML body with the SAME parser the real
    production collector uses (klpga.parsers.entry_list_parser.
    parse_entry_list_html) — never a separate/independent re-parse that
    could silently drift from what the collector itself would see."""
    from klpga.parsers.entry_list_parser import parse_entry_list_html

    result = parse_entry_list_html(body_text)
    return {row.player_code for row in result.rows}


def investigate_unexplained_player(
    conn: sqlite3.Connection,
    game_code: str,
    player_code: str,
    *,
    pre_field_names_by_code: dict,
    missing_names_by_code: dict,
    identity_by_code: dict,
    pre_created_at_utc,
    raw_cache_dir: Optional[Path] = None,
) -> dict:
    """Full, read-only evidence gathering + classification for one
    player_code that has a real round_number=1 row but is absent from
    the frozen R1 snapshot entirely. Never guesses: every field here is
    a direct query result, a real timestamp comparison, or a
    normalized-exact-string comparison — never a fuzzy/approximate
    match, never an assumption made without a specific evidence check."""
    master_row = conn.execute(
        "SELECT player_name FROM player_master WHERE player_id = ?", (player_code,)
    ).fetchone()
    player_name = master_row[0] if master_row else None

    event_row = conn.execute(
        "SELECT player_name, finish_position, finish_position_numeric, made_cut, withdrawn, disqualified, "
        "rounds_played, score_to_par FROM player_event WHERE game_code = ? AND player_id = ?",
        (game_code, player_code),
    ).fetchone()
    event_detail = None
    if event_row is not None:
        (ev_name, finish_position, finish_position_numeric, made_cut, withdrawn, disqualified,
         rounds_played, score_to_par) = event_row
        event_detail = {
            "player_name": ev_name, "finish_position": finish_position,
            "finish_position_numeric": finish_position_numeric, "made_cut": bool(made_cut),
            "withdrawn": bool(withdrawn), "disqualified": bool(disqualified),
            "rounds_played": rounds_played, "score_to_par": score_to_par,
        }

    entry_row = conn.execute(
        "SELECT collected_at FROM tournament_entry WHERE game_code = ? AND player_code = ?", (game_code, player_code)
    ).fetchone()
    in_entry_field = entry_row is not None
    entry_collected_at = entry_row[0] if entry_row is not None else None

    all_rounds = all_round_rows_for_player(conn, game_code, player_code)
    raw_cache_hits = scan_raw_cache_for_player(raw_cache_dir, game_code, player_code) if raw_cache_dir is not None else []

    identity_row = identity_by_code.get(player_code)

    display_name = player_name or (event_detail or {}).get("player_name")
    normalized = normalize_name(display_name)
    name_match_in_missing = [
        code for code, name in missing_names_by_code.items() if normalize_name(name) == normalized and normalized
    ]
    name_match_in_pre_field = [
        code for code, name in pre_field_names_by_code.items()
        if code != player_code and normalize_name(name) == normalized and normalized
    ]
    name_match_in_current_entry_field = entry_field_name_matches(conn, game_code, player_code, normalized)

    # --- classification, evidence-only: never assume, only conclude what a specific
    # check above positively supports. ---
    entered_after_pre = (
        in_entry_field and entry_collected_at is not None and pre_created_at_utc is not None
        and entry_collected_at > pre_created_at_utc
    )
    entered_at_or_before_pre = (
        in_entry_field and entry_collected_at is not None and pre_created_at_utc is not None
        and entry_collected_at <= pre_created_at_utc
    )
    if identity_row is not None and identity_row.get("identity_status") == "AMBIGUOUS":
        classification = UNEXPLAINED_DUPLICATE_IDENTITY
    elif identity_row is not None and identity_row.get("identity_status") == "BROKEN":
        classification = UNEXPLAINED_DB_MAPPING_ERROR
    elif name_match_in_missing or name_match_in_pre_field:
        classification = UNEXPLAINED_PLAYER_CODE_CHANGED
    elif entered_after_pre:
        classification = UNEXPLAINED_LATE_ENTRY_FIELD_CHANGE
    elif entered_at_or_before_pre:
        classification = UNEXPLAINED_DB_MAPPING_ERROR
    else:
        classification = UNEXPLAINED_UNRESOLVED

    return {
        "player_code": player_code,
        "player_name": player_name,
        "player_master_row_exists": master_row is not None,
        "player_event": event_detail,
        "in_entry_field": in_entry_field,
        "entry_collected_at": entry_collected_at,
        "all_round_rows": all_rounds,
        "raw_cache_hits": raw_cache_hits,
        "identity_crosswalk": identity_row,
        "name_match_in_missing_players": name_match_in_missing,
        "name_match_in_pre_field": name_match_in_pre_field,
        "name_match_in_current_entry_field": name_match_in_current_entry_field,
        "classification": classification,
    }
