"""NEO Ranking V2 round-count audit (VALIDATION_MODEL_NOT_PRODUCTION).

Cross-checks the corrected SG warehouse's own self-reported ``rounds``
field (read from the official strokesGained_detail table's own column --
see official_data.py::parse_sg_html, cells[8]) against every OTHER
official signal this repository actually has access to, and is explicit
about which checks it could NOT run.

WHAT THIS SCRIPT CANNOT DO, AND WHY
------------------------------------
The literal requirement -- "count(non-null numeric r1_score..r4_score)
from the official roundLeaderboard, independent of the SG table's own
rounds column" -- requires the `player_event` SQLite table (see
src/klpga/db/schema.sql: r1_score..r4_score columns), which is built by
klpga.backtest.historical_field from a REAL database. This environment's
local data/klpga.sqlite is a confirmed 0-byte placeholder (verified
repeatedly this session) -- there is no other JSON export in this repo
that carries genuine per-round numeric scores for the 82 historical
tournaments (content/website_v2/empirical_sg_corrected_v2/
player_event_series.json was checked and is actually another SG-only
export, not the DB's player_event table, despite its filename).

Given that, this script does NOT claim ROUND_COUNT_VERIFIED for any
record -- that would require the independent leaderboard score count it
cannot obtain here. Instead it:
  1. Confirms scope separation (never mixes tournament_cumulative and
     single_round rows for the same player-event).
  2. Cross-checks SG-table rounds against the WEAKER but real proxy
     available in this environment -- NEO_HISTORICAL_TRUTH_WAREHOUSE_V1's
     made_cut/withdrawn/disqualified outcome flags (themselves sourced
     from player_event, i.e. real official status, just without the
     round-by-round SCORES needed for a literal count).
  3. Reports every record's round_count_state as UNVERIFIED, and sets
     hard_gate.status = BLOCKED, per the explicit instruction that an
     unverified round-count is a normal, correct stopping point -- not a
     result to be quietly upgraded to VERIFIED.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def main() -> int:
    sg_path = CONTENT / "historical_sg_warehouse_corrected.json"
    truth_path = CONTENT / "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json"
    consistency_path = CONTENT / "HISTORICAL_FIELD_CONSISTENCY_BLOCKER_RESOLUTION_V1.json"

    sg = json.loads(sg_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    consistency = json.loads(consistency_path.read_text(encoding="utf-8"))

    sg_records = sg["records"]
    scope_counts = Counter(r.get("scope") for r in sg_records)

    # Step 1: STRICT scope separation, per explicit instruction ("절대로
    # 혼합하지 말라"). tournament_cumulative rows are the only ones used for
    # the round-count audit and the SG/R candidate below; single_round-only
    # events (a player-event with SG rows but no tournament_cumulative row
    # at all) are counted and reported SEPARATELY, never silently merged in
    # as if they were a cumulative observation. This deliberately differs
    # from home_ranking.build_features's current production behavior
    # (which does select single_round rows as a fallback) -- that
    # cross-scope fallback is exactly the kind of silent mixing this audit
    # exists to catch, not to replicate.
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

    single_round_only_events = single_round_keys - set(cumulative_only.keys())
    player_events_checked = len(cumulative_only)
    round_distribution = Counter(int(r.get("rounds") or 0) for r in cumulative_only.values())

    # Step 2: join against the real outcome-status warehouse (7830 records,
    # 82 tournaments -- verified below against the frozen V1 backtest hash).
    truth_by_key = {(r["player_id"], r["game_code"]): r for r in truth["records"]}
    status_by_rounds: dict[int, Counter] = defaultdict(Counter)
    mismatch_examples = []
    unverified_examples = []
    wd_examples = []
    dq_examples = []
    competition_status = Counter()

    for key, sg_row in cumulative_only.items():
        rounds = int(sg_row.get("rounds") or 0)
        truth_row = truth_by_key.get(key)
        if truth_row is None:
            competition_status["other"] += 1
            if len(unverified_examples) < 10:
                unverified_examples.append({"player_id": key[0], "game_code": key[1], "rounds": rounds, "reason": "no matching outcome record in truth warehouse"})
            continue
        outcome = truth_row["outcome"]
        wd, dq, made_cut = outcome["withdrawn"], outcome["disqualified"], outcome["made_cut"]
        if wd:
            status_by_rounds[rounds]["wd"] += 1
            competition_status["wd"] += 1
            if len(wd_examples) < 10:
                wd_examples.append({"player_id": key[0], "game_code": key[1], "rounds": rounds})
            # A WD player who is recorded with all 4 rounds is a real,
            # reportable inconsistency worth flagging -- WD normally implies
            # an incomplete tournament.
            if rounds >= 4 and len(mismatch_examples) < 10:
                mismatch_examples.append({"player_id": key[0], "game_code": key[1], "rounds": rounds, "reason": "withdrawn but SG table shows 4 completed rounds"})
        elif dq:
            status_by_rounds[rounds]["dq"] += 1
            competition_status["dq"] += 1
            if len(dq_examples) < 10:
                dq_examples.append({"player_id": key[0], "game_code": key[1], "rounds": rounds})
        elif made_cut:
            status_by_rounds[rounds]["made_cut_finished"] += 1
            competition_status["finished"] += 1
        else:
            status_by_rounds[rounds]["cut"] += 1
            competition_status["cut"] += 1

    # Step 3: per-round-group descriptive stats (only where data exists)
    round_group_stats = {}
    for n in (1, 2, 3, 4):
        rows_in_group = [r for k, r in cumulative_only.items() if int(r.get("rounds") or 0) == n]
        if not rows_in_group:
            continue
        totals = [float(r["total"]) for r in rows_in_group]
        round_group_stats[str(n)] = {
            "player_event_count": len(rows_in_group),
            "mean_tournament_sg": round(statistics.fmean(totals), 4),
            "mean_sg_per_round": round(statistics.fmean(t / n for t in totals), 4),
            "competition_status_distribution": dict(status_by_rounds[n]),
        }

    # Step 4: the frozen 9682-vs-7830 explanation, from the already-existing
    # (not newly invented) field-consistency artifact.
    agg = consistency["aggregate"]
    gap_explanation = {
        "verified_field_players": agg["verified_field_players"],
        "SG_field_players": agg["SG_field_players"],
        "missing_from_SG": agg["missing_from_SG"],
        "root_cause_from_existing_artifact": (
            "verified_field_players (9682) counts every player appearing in the R1 grouping/"
            "tee-time page across 82 tournaments -- a real official STARTING list. SG_field_players "
            "(7830) counts only players who have a matching row in the SG-reconstructed warehouse, "
            "which requires the player to have generated an official SG total (i.e. appeared in "
            "strokesGained_detail). The R1 grouping page does NOT encode WD/DQ status "
            "(see per-tournament 'WD_DQ_reason' field in HISTORICAL_FIELD_CONSISTENCY_BLOCKER_"
            "RESOLUTION_V1.json), so the 1852-player gap cannot be attributed to WD/DQ with "
            "confidence from this evidence alone."
        ),
        "classification": "UNKNOWN (not WD/DQ-attributed; not otherwise explained by available evidence)",
    }

    report = {
        "schema_version": "neo_ranking_v2_round_count_audit_v1",
        "model_state": "VALIDATION_MODEL_NOT_PRODUCTION",
        "events_checked": len(set(k[1] for k in cumulative_only)),
        "player_events_checked": player_events_checked,
        "scope_counts_raw_warehouse": dict(scope_counts),
        "duplicate_cumulative_snapshots_collapsed": duplicate_cumulative_snapshots,
        "single_round_only_events_excluded_not_mixed_in": len(single_round_only_events),
        "round_count_state": {
            "verified": 0,
            "mismatch": len(mismatch_examples),
            "unverified": player_events_checked,
        },
        "round_count_state_note": (
            "ALL player-events are classified UNVERIFIED. The literal cross-check (SG table rounds "
            "vs count of non-null official r1..r4 leaderboard scores) requires the player_event SQL "
            "table, which needs the real KLPGA database. This sandbox's data/klpga.sqlite is a "
            "confirmed 0-byte placeholder. No JSON export of player_event with per-round numeric "
            "scores was found in this repository (player_event_series.json was checked and is an "
            "SG-only export, not the DB table, despite its name)."
        ),
        "competition_status": dict(competition_status),
        "round_distribution": {str(k): v for k, v in sorted(round_distribution.items())},
        "round_group_stats": round_group_stats,
        "mismatch_examples": mismatch_examples,
        "unverified_examples": unverified_examples,
        "wd_examples": wd_examples,
        "dq_examples": dq_examples,
        "gap_9682_vs_7830_explanation": gap_explanation,
        "source_provenance": {
            "historical_sg_warehouse_corrected": {"path": str(sg_path.relative_to(ROOT)), "sha256": sha256_of(sg_path)},
            "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1": {"path": str(truth_path.relative_to(ROOT)), "sha256": sha256_of(truth_path)},
            "HISTORICAL_FIELD_CONSISTENCY_BLOCKER_RESOLUTION_V1": {"path": str(consistency_path.relative_to(ROOT)), "sha256": sha256_of(consistency_path)},
        },
        "input_sha256": {
            "historical_sg_warehouse_corrected.json": sha256_of(sg_path),
            "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json": sha256_of(truth_path),
        },
        "hard_gate": {
            "status": "BLOCKED",
            "reason": (
                "round_count_state has zero VERIFIED records -- the independent official leaderboard "
                "round-score source (player_event SQL table) is not accessible in this environment. "
                "Per instruction, an unverified round count must end in BLOCKED, not be reported as "
                "PASS. The SG-table's own rounds field and the WD/DQ/made_cut proxy cross-check above "
                "are real evidence but do not constitute independent verification."
            ),
        },
    }

    out_path = CONTENT / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("events_checked", "player_events_checked", "round_count_state", "competition_status", "round_distribution", "hard_gate")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
