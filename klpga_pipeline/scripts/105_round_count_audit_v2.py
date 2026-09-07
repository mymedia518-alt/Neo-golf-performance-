"""NEO Ranking V2 round-count audit v2 -- connected to the official
leaderboard archive (VALIDATION_MODEL_NOT_PRODUCTION).

Supersedes scripts/103_round_count_audit.py's UNVERIFIED-only output now
that a real evidence source exists: scripts/104_official_archive_
reconstruction.py's persisted NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json
(the ACTUAL parsed official leaderboard rows, not just retrieval counts).

For every tournament_cumulative SG player-event, this script:

  1. Joins STRICTLY on (game_code, player_id) against the leaderboard
     archive -- never on name, never fuzzy.
  2. Selects the fullest legitimate official snapshot available for that
     player: the retrieved round with the most non-null R1-R4 scores.
     Never fabricates a round the archive did not actually retrieve.
  3. Computes leaderboard_round_count = count(non-null values in that
     snapshot's rounds array) and compares it against the SG table's own
     `rounds` field, classifying:
         ROUND_COUNT_VERIFIED   -- the two counts agree
         ROUND_COUNT_MISMATCH   -- they disagree
         ROUND_COUNT_UNVERIFIED -- no matching official row exists (no
                                    archive data yet, or this player/event
                                    was never retrieved)
  4. Separately classifies competition_status (an independent axis):
         WD / DQ                 -- from the official rank-text flag
         UNVERIFIED_EARLY_EXIT   -- 1-ROUND RULE: a single official round
                                     with no WD/DQ flag is never guessed
                                     as CUT or WD
         CUT                     -- REAL evidence: the player's best
                                     snapshot comes from a round earlier
                                     than the latest round this event's
                                     archive actually retrieved, i.e. they
                                     are officially absent from a later
                                     round leaderboard that exists -- not
                                     inferred from the round-count number
                                     alone
         FINISHED                -- present through the event's latest
                                     retrieved round
         OTHER                   -- no official row to classify from

If the leaderboard archive does not exist yet, or holds no real player
rows (this environment's network egress is blocked and every event is
NETWORK_EGRESS_DENIED), every player-event is honestly UNVERIFIED and the
hard gate stays BLOCKED -- this script never claims verification it does
not have real evidence for.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.website_v2.round_count_audit_lib import (  # noqa: E402
    build_cumulative_only,
    build_player_index,
    best_snapshot,
    count_nonnull_rounds,
    max_retrieved_round,
)

CONTENT = ROOT / "content" / "website_v2"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def classify_competition_status(best_row: dict, leaderboard_round_count: int, archive_max_round: int) -> str:
    status = best_row.get("status")
    if status == "WD":
        return "WD"
    if status == "DQ":
        return "DQ"
    # Not officially flagged WD/DQ -- decide FINISHED vs CUT vs
    # UNVERIFIED_EARLY_EXIT from REAL evidence, never the round-count
    # number alone.
    if leaderboard_round_count <= 1:
        return "UNVERIFIED_EARLY_EXIT"  # 1 ROUND RULE
    best_round = best_row.get("requested_round") or 0
    if archive_max_round and best_round < archive_max_round:
        # Real evidence: officially absent from a LATER round leaderboard
        # this archive actually retrieved for this event.
        return "CUT"
    if archive_max_round and best_round >= archive_max_round:
        return "FINISHED"
    return "OTHER"


def build_report(sg: dict, consistency: dict, archive: dict | None, archive_sha: str | None) -> dict:
    cumulative_only, duplicate_cumulative_snapshots, single_round_only_events = build_cumulative_only(sg["records"])
    scope_counts = Counter(r.get("scope") for r in sg["records"])
    events = (archive or {}).get("events", {})

    round_count_state = Counter()
    competition_status = Counter()
    mismatch_examples = []
    verified_examples = []
    unverified_examples = []
    round_distribution = Counter()

    player_index_cache: dict[str, dict] = {}
    max_round_cache: dict[str, int] = {}

    for (player_id, game_code), sg_row in cumulative_only.items():
        sg_rounds = int(sg_row.get("rounds") or 0)
        round_distribution[sg_rounds] += 1
        game_code_key = str(game_code)

        if game_code_key not in player_index_cache:
            event = events.get(game_code_key, {})
            player_index_cache[game_code_key] = build_player_index(event)
            max_round_cache[game_code_key] = max_retrieved_round(events, game_code_key)

        rows = player_index_cache[game_code_key].get(str(player_id), [])
        best_row = best_snapshot(rows)
        archive_max_round = max_round_cache[game_code_key]

        if best_row is None:
            round_count_state["unverified"] += 1
            competition_status["OTHER"] += 1
            if len(unverified_examples) < 10:
                unverified_examples.append({
                    "player_id": player_id, "game_code": game_code, "sg_rounds": sg_rounds,
                    "reason": ("no matching official leaderboard row for this (game_code, player_id)"
                               if events else "no official leaderboard archive data available"),
                })
            continue

        leaderboard_round_count = count_nonnull_rounds(best_row.get("rounds"))
        status = classify_competition_status(best_row, leaderboard_round_count, archive_max_round)
        competition_status[status] += 1

        if leaderboard_round_count == sg_rounds:
            round_count_state["verified"] += 1
            if len(verified_examples) < 5:
                verified_examples.append({
                    "player_id": player_id, "game_code": game_code,
                    "sg_rounds": sg_rounds, "leaderboard_round_count": leaderboard_round_count,
                    "competition_status": status,
                })
        else:
            round_count_state["mismatch"] += 1
            if len(mismatch_examples) < 10:
                mismatch_examples.append({
                    "player_id": player_id, "game_code": game_code,
                    "sg_rounds": sg_rounds, "leaderboard_round_count": leaderboard_round_count,
                    "official_rounds_array": best_row.get("rounds"),
                    "official_status": best_row.get("status"),
                    "competition_status": status,
                })

    agg = consistency["aggregate"]
    gap_explanation = {
        "verified_field_players": agg["verified_field_players"],
        "SG_field_players": agg["SG_field_players"],
        "missing_from_SG": agg["missing_from_SG"],
        "classification": "UNKNOWN (not WD/DQ-attributed; not otherwise explained by available evidence)",
    }

    total_checked = len(cumulative_only)
    verified_count = round_count_state.get("verified", 0)

    if verified_count == 0:
        gate_status = "BLOCKED"
        gate_reason = (
            "round_count_state has zero VERIFIED records -- no official leaderboard archive evidence is "
            "available in this environment (network egress blocked, or the archive has not been generated "
            "yet). Round-count verification requires a real retrieval run (e.g. on a machine with genuine "
            "KLPGA network access) to populate NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json with real "
            "parsed player rows first."
        )
    else:
        gate_status = "PARTIAL_EVIDENCE"
        gate_reason = (
            f"{verified_count}/{total_checked} player-events achieved ROUND_COUNT_VERIFIED using real "
            "official leaderboard evidence. This is real progress but not yet a full-population "
            "verification -- V2 backtest eligibility should be scoped to the verified subset, not assumed "
            "for the full population, until every population-defining tournament has been retrieved."
        )

    return {
        "schema_version": "neo_ranking_v2_round_count_audit_v2_archive_connected",
        "model_state": "VALIDATION_MODEL_NOT_PRODUCTION",
        "supersedes": "neo_ranking_v2_round_count_audit_v1 (scripts/103_round_count_audit.py)",
        "events_checked": len({k[1] for k in cumulative_only}),
        "player_events_checked": total_checked,
        "scope_counts_raw_warehouse": dict(scope_counts),
        "duplicate_cumulative_snapshots_collapsed": duplicate_cumulative_snapshots,
        "single_round_only_events_excluded_not_mixed_in": len(single_round_only_events),
        "leaderboard_archive_available": archive is not None,
        "leaderboard_archive_sha256": archive_sha,
        "round_count_state": {
            "verified": round_count_state.get("verified", 0),
            "mismatch": round_count_state.get("mismatch", 0),
            "unverified": round_count_state.get("unverified", 0),
        },
        "competition_status": dict(competition_status),
        "round_distribution": {str(k): v for k, v in sorted(round_distribution.items())},
        "verified_examples": verified_examples,
        "mismatch_examples": mismatch_examples,
        "unverified_examples": unverified_examples,
        "gap_9682_vs_7830_explanation": gap_explanation,
        "hard_gate": {"status": gate_status, "reason": gate_reason},
    }


def main() -> int:
    sg_path = CONTENT / "historical_sg_warehouse_corrected.json"
    consistency_path = CONTENT / "HISTORICAL_FIELD_CONSISTENCY_BLOCKER_RESOLUTION_V1.json"
    archive_path = CONTENT / "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json"

    sg = json.loads(sg_path.read_text(encoding="utf-8"))
    consistency = json.loads(consistency_path.read_text(encoding="utf-8"))

    archive = None
    archive_sha = None
    if archive_path.exists():
        archive = json.loads(archive_path.read_text(encoding="utf-8"))
        archive_sha = sha256_of(archive_path)

    report = build_report(sg, consistency, archive, archive_sha)
    report["input_sha256"] = {
        "historical_sg_warehouse_corrected.json": sha256_of(sg_path),
        "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json": archive_sha,
    }

    out_path = CONTENT / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "player_events_checked": report["player_events_checked"],
        "round_count_state": report["round_count_state"],
        "competition_status": report["competition_status"],
        "hard_gate": report["hard_gate"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
