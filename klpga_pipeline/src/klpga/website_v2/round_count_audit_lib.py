"""Shared helpers for the NEO Ranking V2 round-count audit scripts
(scripts/103_round_count_audit.py, scripts/105_round_count_audit_v2.py).

Kept as a normal importable module -- not a numbered script -- so the
scope-separation rule and the official-leaderboard-archive lookup logic are
defined once and cannot silently drift between audit versions.
"""
from __future__ import annotations


def build_cumulative_only(sg_records: list[dict]) -> tuple[dict[tuple, dict], int, set[tuple]]:
    """Strict scope separation, per explicit instruction ("never mix
    tournament_cumulative and single_round"). Only RETAINED
    tournament_cumulative rows are used for round-count auditing;
    single_round-only events (no matching cumulative row at all) are
    reported separately, never silently substituted in.

    Returns (cumulative_only keyed by (player_id, game_code),
    duplicate_cumulative_snapshot_count, single_round_only_keys).
    """
    cumulative_only: dict[tuple, dict] = {}
    duplicate_cumulative_snapshots = 0
    single_round_keys: set[tuple] = set()
    for r in sg_records:
        if r.get("identity_state") != "RETAINED":
            continue
        key = (r.get("player_id"), r.get("game_code"))
        if r.get("scope") == "tournament_cumulative":
            if key in cumulative_only:
                duplicate_cumulative_snapshots += 1
            cumulative_only[key] = r
        elif r.get("scope") == "single_round":
            single_round_keys.add(key)
    return cumulative_only, duplicate_cumulative_snapshots, single_round_keys - set(cumulative_only.keys())


def count_nonnull_rounds(rounds_array) -> int:
    if not rounds_array:
        return 0
    return sum(1 for v in rounds_array if v is not None)


def build_player_index(event: dict) -> dict[str, list[dict]]:
    """Every row of every successfully-persisted round for one event,
    indexed by player_id -- built once per event and reused across all of
    that event's players, instead of rescanning every round per player."""
    index: dict[str, list[dict]] = {}
    for round_data in (event.get("rounds") or {}).values():
        for row in round_data.get("players") or []:
            pid = str(row.get("player_id"))
            index.setdefault(pid, []).append(row)
    return index


def best_snapshot(rows: list[dict]) -> dict | None:
    """The fullest legitimate official snapshot for one player: the row
    with the most non-null round scores, tie-broken by the highest
    requested_round (the most recent/authoritative retrieval). Never
    fabricates a round the official source did not actually return --
    only chooses among rows that were genuinely retrieved and parsed."""
    if not rows:
        return None
    return max(rows, key=lambda row: (count_nonnull_rounds(row.get("rounds")), row.get("requested_round") or 0))


def max_retrieved_round(events: dict, game_code: str) -> int:
    event = events.get(str(game_code)) or events.get(game_code) or {}
    retrieved = [
        int(rnd) for rnd, data in (event.get("rounds") or {}).items()
        if data.get("round_retrieval_state") == "RETRIEVED"
    ]
    return max(retrieved) if retrieved else 0
