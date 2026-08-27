"""Safe identity resolution between `official_metric_value.player_code`
(loadLocationRecord's own identity space) and `player_master.player_id`
— the join `klpga.discovery.season_metric_collector.verify_player_code_
identity_space` exists specifically because this was NEVER assumed
identical. A real production run reported 440/446 = 98.65% matched —
high, but not 100%, so this module makes the remaining 6 explicit
rather than silently joining on a possibly-wrong shared string.

======================================================================
RESOLUTION STRATEGY — deterministic, evidence-only, never fuzzy
======================================================================
For every `official_metric_value.player_code` NOT directly present in
`player_master.player_id`:
  1. Read one already-saved raw response for that code
     (`official_metric_value.raw_sample_path`).
  2. Re-parse it with the same, unmodified `response_parser.
     parse_record_response` to recover the player_name KLPGA itself
     displayed for that code.
  3. Look for an EXACT `player_master.player_name` match (case-
     sensitive, no normalization, no fuzzy/edit-distance matching —
     a near-miss is left unresolved, never guessed).
  4. Resolve ONLY if exactly one player_master row has that exact
     name — an ambiguous (0 or 2+) match is left unresolved.

This never invents a mapping — every resolution is traceable to a real
raw HTML file's real displayed name matching a real player_master row
byte-for-byte.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from klpga.discovery.response_parser import parse_record_response


def find_unmatched_official_metric_player_codes(conn: sqlite3.Connection) -> set[str]:
    """Real `official_metric_value.player_code` values with NO matching
    `player_master.player_id` — a plain set difference, no evidence
    invented."""
    metric_codes = {row[0] for row in conn.execute("SELECT DISTINCT player_code FROM official_metric_value")}
    player_master_ids = {row[0] for row in conn.execute("SELECT player_id FROM player_master")}
    return metric_codes - player_master_ids


def resolve_unmatched_player_codes(conn: sqlite3.Connection, unmatched_codes: set[str]) -> dict[str, Optional[str]]:
    """Returns {official_metric_value.player_code: resolved_player_master_id or None}.
    None means "attempted, evidence insufficient to resolve deterministically" —
    never removed from the report, never silently dropped."""
    if not unmatched_codes:
        return {}

    player_master_by_name: dict[str, list[str]] = {}
    for player_id, player_name in conn.execute("SELECT player_id, player_name FROM player_master"):
        player_master_by_name.setdefault(player_name, []).append(player_id)

    resolved: dict[str, Optional[str]] = {}
    for code in unmatched_codes:
        row = conn.execute(
            "SELECT raw_sample_path FROM official_metric_value "
            "WHERE player_code = ? AND raw_sample_path IS NOT NULL LIMIT 1",
            (code,),
        ).fetchone()
        if row is None:
            resolved[code] = None
            continue
        raw_path = Path(row[0])
        if not raw_path.exists():
            resolved[code] = None
            continue
        parsed = parse_record_response(raw_path.read_text(encoding="utf-8"))
        player_name = next((r.player_name for r in parsed.rows if r.player_code == code), None)
        if player_name is None:
            resolved[code] = None
            continue
        candidates = player_master_by_name.get(player_name, [])
        resolved[code] = candidates[0] if len(candidates) == 1 else None
    return resolved


def build_identity_alias_map(conn: sqlite3.Connection) -> dict:
    """The full, real resolution report this round's release requires:
    which official_metric_value.player_code values are directly usable
    as-is, which were resolved to a DIFFERENT player_master.player_id
    by exact name match, and which remain genuinely unresolved (SKIP +
    LOG, never removed from the model — a player with tournament-result
    history keeps that history regardless of this join's outcome).

    Returns {"alias_map": {metric_code: player_master_id}  (direct
    matches map to themselves), "unresolved_codes": [...],
    "resolved_by_name_count": int, "direct_match_count": int}."""
    unmatched = find_unmatched_official_metric_player_codes(conn)
    resolution = resolve_unmatched_player_codes(conn, unmatched)

    metric_codes = {row[0] for row in conn.execute("SELECT DISTINCT player_code FROM official_metric_value")}
    player_master_ids = {row[0] for row in conn.execute("SELECT player_id FROM player_master")}
    direct = metric_codes & player_master_ids

    alias_map: dict[str, str] = {code: code for code in direct}
    unresolved_codes: list[str] = []
    resolved_by_name_count = 0
    for code, resolved_id in resolution.items():
        if resolved_id is not None:
            alias_map[code] = resolved_id
            resolved_by_name_count += 1
        else:
            unresolved_codes.append(code)

    return {
        "alias_map": alias_map,
        "unresolved_codes": sorted(unresolved_codes),
        "resolved_by_name_count": resolved_by_name_count,
        "direct_match_count": len(direct),
    }
