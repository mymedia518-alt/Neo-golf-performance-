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


REASON_RESOLVED = "RESOLVED_BY_EXACT_NAME"
REASON_NO_RAW_SAMPLE = "NO_RAW_SAMPLE_TO_CHECK"
REASON_NAME_NOT_FOUND = "NAME_NOT_IN_PLAYER_MASTER"
REASON_AMBIGUOUS_NAME = "AMBIGUOUS_NAME_MULTIPLE_PLAYER_MASTER_MATCHES"


def resolve_unmatched_player_codes(conn: sqlite3.Connection, unmatched_codes: set[str]) -> dict[str, dict]:
    """Returns {official_metric_value.player_code: {"resolved_id": str
    or None, "reason": str, "candidate_ids": [...]}}. `reason` is one
    of REASON_RESOLVED / REASON_NO_RAW_SAMPLE / REASON_NAME_NOT_FOUND /
    REASON_AMBIGUOUS_NAME — the LAST one is deliberately distinct from
    "not found at all": 2+ player_master rows sharing the exact same
    name is a genuine ambiguity (never silently resolved to either),
    not the same failure mode as no match existing."""
    if not unmatched_codes:
        return {}

    player_master_by_name: dict[str, list[str]] = {}
    for player_id, player_name in conn.execute("SELECT player_id, player_name FROM player_master"):
        player_master_by_name.setdefault(player_name, []).append(player_id)

    resolved: dict[str, dict] = {}
    for code in unmatched_codes:
        row = conn.execute(
            "SELECT raw_sample_path FROM official_metric_value "
            "WHERE player_code = ? AND raw_sample_path IS NOT NULL LIMIT 1",
            (code,),
        ).fetchone()
        if row is None:
            resolved[code] = {"resolved_id": None, "reason": REASON_NO_RAW_SAMPLE, "candidate_ids": []}
            continue
        raw_path = Path(row[0])
        if not raw_path.exists():
            resolved[code] = {"resolved_id": None, "reason": REASON_NO_RAW_SAMPLE, "candidate_ids": []}
            continue
        parsed = parse_record_response(raw_path.read_text(encoding="utf-8"))
        player_name = next((r.player_name for r in parsed.rows if r.player_code == code), None)
        if player_name is None:
            resolved[code] = {"resolved_id": None, "reason": REASON_NO_RAW_SAMPLE, "candidate_ids": []}
            continue
        candidates = player_master_by_name.get(player_name, [])
        if len(candidates) == 1:
            resolved[code] = {"resolved_id": candidates[0], "reason": REASON_RESOLVED, "candidate_ids": candidates}
        elif len(candidates) == 0:
            resolved[code] = {"resolved_id": None, "reason": REASON_NAME_NOT_FOUND, "candidate_ids": []}
        else:
            resolved[code] = {"resolved_id": None, "reason": REASON_AMBIGUOUS_NAME, "candidate_ids": candidates}
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
    "unresolved_detail": {code: {"reason", "candidate_ids"}},
    "resolved_by_name_count": int, "direct_match_count": int}."""
    unmatched = find_unmatched_official_metric_player_codes(conn)
    resolution = resolve_unmatched_player_codes(conn, unmatched)

    metric_codes = {row[0] for row in conn.execute("SELECT DISTINCT player_code FROM official_metric_value")}
    player_master_ids = {row[0] for row in conn.execute("SELECT player_id FROM player_master")}
    direct = metric_codes & player_master_ids

    alias_map: dict[str, str] = {code: code for code in direct}
    unresolved_codes: list[str] = []
    unresolved_detail: dict[str, dict] = {}
    resolved_by_name_count = 0
    for code, info in resolution.items():
        if info["resolved_id"] is not None:
            alias_map[code] = info["resolved_id"]
            resolved_by_name_count += 1
        else:
            unresolved_codes.append(code)
            unresolved_detail[code] = {"reason": info["reason"], "candidate_ids": info["candidate_ids"]}

    return {
        "alias_map": alias_map,
        "unresolved_codes": sorted(unresolved_codes),
        "unresolved_detail": unresolved_detail,
        "resolved_by_name_count": resolved_by_name_count,
        "direct_match_count": len(direct),
    }


# ---------------------------------------------------------------
# Phase 1/2 — full, DB-wide identity crosswalk (not just official_
# metric_value vs player_master): one row per canonical identity seen
# ANYWHERE (player_master, player_event, player_round, tournament_
# entry, official_metric_value), classified CLEAN / PARTIAL /
# AMBIGUOUS / BROKEN / UNMATCHED. player_event/player_round already
# share player_master's identity space by a real schema FK
# (player_event.player_id REFERENCES player_master.player_id) — the
# only genuinely uncertain relationship is official_metric_value.
# player_code, which is why build_identity_alias_map (above) exists.
# ---------------------------------------------------------------

STATUS_CLEAN = "CLEAN"
STATUS_PARTIAL = "PARTIAL"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_BROKEN = "BROKEN"
STATUS_UNMATCHED = "UNMATCHED"


def build_full_identity_crosswalk(conn: sqlite3.Connection) -> list[dict]:
    """One row per canonical player_master.player_id PLUS one row per
    orphan code (a code appearing in tournament_entry or official_
    metric_value with no player_master row at all — tournament_entry
    has no FK to player_master by design, so this is a real, expected
    case, not a defect). Never merges two player_master rows just
    because their names match (STATUS_AMBIGUOUS exists precisely to
    flag that case instead)."""
    player_master = {row[0]: row[1] for row in conn.execute("SELECT player_id, player_name FROM player_master")}
    name_counts: dict[str, int] = {}
    for name in player_master.values():
        name_counts[name] = name_counts.get(name, 0) + 1

    player_event_ids = {row[0] for row in conn.execute("SELECT DISTINCT player_id FROM player_event")}
    player_round_ids = {row[0] for row in conn.execute("SELECT DISTINCT player_id FROM player_round")}
    tournament_entry_codes = {row[0] for row in conn.execute("SELECT DISTINCT player_code FROM tournament_entry")}
    official_metric_codes = {row[0] for row in conn.execute("SELECT DISTINCT player_code FROM official_metric_value")}

    alias_report = build_identity_alias_map(conn)
    alias_map = alias_report["alias_map"]
    unresolved_detail = alias_report["unresolved_detail"]
    resolved_to_by_id: dict[str, list[str]] = {}
    for code, resolved_id in alias_map.items():
        if code != resolved_id:
            resolved_to_by_id.setdefault(resolved_id, []).append(code)

    rows: list[dict] = []
    seen_official_codes_covered: set[str] = set()

    for player_id, player_name in sorted(player_master.items()):
        om_direct = player_id in official_metric_codes
        om_resolved_aliases = resolved_to_by_id.get(player_id, [])
        for c in ([player_id] if om_direct else []) + om_resolved_aliases:
            seen_official_codes_covered.add(c)
        official_metric_match = om_direct or bool(om_resolved_aliases)

        evidence = []
        resolution_method = "direct_id"
        if name_counts.get(player_name, 0) > 1:
            status = STATUS_AMBIGUOUS
            evidence.append(f"{name_counts[player_name]} player_master rows share the name {player_name!r}")
        elif not official_metric_match and player_id in tournament_entry_codes:
            status = STATUS_PARTIAL
            evidence.append("in current tournament field but no official_metric_value coverage")
        elif om_resolved_aliases:
            status = STATUS_PARTIAL
            resolution_method = "resolved_by_exact_name"
            evidence.append(f"official_metric_value code(s) {om_resolved_aliases} resolved to this player by exact name match")
        else:
            status = STATUS_CLEAN
            evidence.append("player_master id used consistently everywhere it appears")

        rows.append(
            {
                "canonical_player_id": player_id,
                "player_code": player_id,
                "player_name": player_name,
                "player_master_match": True,
                "player_event_match": player_id in player_event_ids,
                "player_round_match": player_id in player_round_ids,
                "official_metric_match": official_metric_match,
                "tournament_entry_match": player_id in tournament_entry_codes,
                "identity_status": status,
                "evidence": "; ".join(evidence),
                "resolution_method": resolution_method,
            }
        )

    # Orphan tournament_entry codes with no player_master row at all.
    for code in sorted(tournament_entry_codes - set(player_master)):
        rows.append(
            {
                "canonical_player_id": None,
                "player_code": code,
                "player_name": None,
                "player_master_match": False,
                "player_event_match": code in player_event_ids,
                "player_round_match": code in player_round_ids,
                "official_metric_match": code in official_metric_codes,
                "tournament_entry_match": True,
                "identity_status": STATUS_BROKEN,
                "evidence": "in tournament_entry with no player_master row at all",
                "resolution_method": "none",
            }
        )

    # Genuinely unmatched official_metric_value codes (not already covered above).
    for code in sorted(official_metric_codes - seen_official_codes_covered - tournament_entry_codes):
        detail = unresolved_detail.get(code, {"reason": "NOT_ATTEMPTED", "candidate_ids": []})
        status = STATUS_AMBIGUOUS if detail["reason"] == REASON_AMBIGUOUS_NAME else STATUS_UNMATCHED
        rows.append(
            {
                "canonical_player_id": None,
                "player_code": code,
                "player_name": None,
                "player_master_match": False,
                "player_event_match": code in player_event_ids,
                "player_round_match": code in player_round_ids,
                "official_metric_match": True,
                "tournament_entry_match": False,
                "identity_status": status,
                "evidence": f"resolution attempt: {detail['reason']} (candidates={detail['candidate_ids']})",
                "resolution_method": "attempted_unresolved",
            }
        )

    return rows
