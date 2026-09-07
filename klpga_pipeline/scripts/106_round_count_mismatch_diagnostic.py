"""NEO Ranking V2 round-count MISMATCH root-cause diagnostic
(VALIDATION_MODEL_NOT_PRODUCTION).

RED TEAM CONTEXT: a real Windows-side retrieval run (97/97 events, 6294/6294
player-events matched to official leaderboard evidence) found that
retrieval coverage is NOT the blocker -- 2973/6294 (47.2%) of matched
player-events show the SG warehouse's own `rounds` field DISAGREEING with
the official leaderboard's non-null round-score count. This script does
NOT retrieve anything from the network -- it reads the already-persisted
content/website_v2/NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json (built
by scripts/104_official_archive_reconstruction.py) and cross-references it
against the SG warehouse to characterize the mismatch, not to fix or hide
it.

Per instruction, this script never:
  - modifies historical_sg_warehouse_corrected.json or the frozen V1
    baseline
  - discards mismatched rows or trains/backtests on the verified-only
    subset (that would introduce verification-selection bias)
  - infers WD/CUT from the round-count number alone
  - "repairs" the SG warehouse's `rounds` field to match official evidence

SECTION MAP (matches the task's numbered requirements):
  1. confusion_matrix          -- SG rounds -> official round count
  2. delta_distribution        -- official_round_count - sg_rounds
  3. event_diagnostics         -- per-game_code population/verified/
                                   mismatch/mismatch_rate + worst events
  4. year_diagnostics          -- per-year population/verified/mismatch
  5. sg_rounds_semantics       -- code-path citation, NOT inference
  6. official_snapshot_audit   -- best_snapshot() legitimacy audit
  7. cut_classifier_redteam    -- "phantom later-round appearance" signal
  8. mismatch_direction        -- SG<official / SG>official / SG==official
  9. clustering_patterns       -- by sg_rounds bucket, competition_status,
                                   year, worst players
  10. (enforced structurally: no warehouse/baseline writes anywhere here)
  11. (hard_gate wording fixed in scripts/105_round_count_audit_v2.py)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
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

_audit_v2_spec = importlib.util.spec_from_file_location(
    "round_count_audit_v2_for_diagnostic", ROOT / "scripts" / "105_round_count_audit_v2.py"
)
_audit_v2 = importlib.util.module_from_spec(_audit_v2_spec)
sys.modules[_audit_v2_spec.name] = _audit_v2
_audit_v2_spec.loader.exec_module(_audit_v2)  # type: ignore[union-attr]
classify_competition_status = _audit_v2.classify_competition_status


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def year_of_game_code(game_code) -> str:
    """Every observed game_code (e.g. '2023040001') begins with a 4-digit
    year. Never guessed for a code that doesn't match this shape."""
    s = str(game_code)
    return s[:4] if len(s) >= 4 and s[:4].isdigit() else "UNKNOWN"


def player_present_in_later_round_than_best(rows: list[dict], best_row: dict | None) -> bool:
    """CUT-CLASSIFIER RED TEAM SIGNAL (section 7). The current CUT rule in
    scripts/105_round_count_audit_v2.py::classify_competition_status infers
    CUT from "this player's best (fullest) snapshot came from a round
    earlier than the latest round this event's archive actually
    retrieved" -- treating ABSENCE from a later round's official response
    as evidence of a cut. That inference is only valid if a cut player
    truly stops appearing in later-round leaderboard responses at all.

    IMPORTANT: best_snapshot()'s own tie-break (prefer the HIGHEST
    requested_round among rows sharing the same max non-null count) means
    a phantom re-appearance can itself BECOME best_row -- so comparing
    against best_row's round alone would miss exactly the case this
    signal exists to catch. Instead: find every round that achieves this
    player's maximum non-null count; if more than one round does, the
    player reappeared later with no new information -- a real, tie-break-
    independent red flag, not a guess."""
    if not rows:
        return False
    max_count = max(count_nonnull_rounds(r.get("rounds")) for r in rows)
    rounds_at_max = sorted({(r.get("requested_round") or 0) for r in rows if count_nonnull_rounds(r.get("rounds")) == max_count})
    return len(rounds_at_max) > 1


def bucket_delta(delta: int) -> str:
    if -3 <= delta <= 3:
        return str(delta)
    return "<=-4" if delta < -3 else ">=+4"


def build_diagnostic(sg: dict, archive: dict | None) -> dict:
    cumulative_only, duplicate_cumulative_snapshots, single_round_only_events = build_cumulative_only(sg["records"])
    events = (archive or {}).get("events", {})
    total_population = len(cumulative_only)

    confusion_matrix: Counter = Counter()
    delta_distribution: Counter = Counter()
    direction: Counter = Counter()
    competition_status_totals: Counter = Counter()
    mismatch_rate_by_sg_rounds: dict[int, Counter] = defaultdict(Counter)
    mismatch_rate_by_status: dict[str, Counter] = defaultdict(Counter)
    player_mismatch_counter: Counter = Counter()
    event_stats: dict[str, dict] = defaultdict(lambda: {
        "population": 0, "verified": 0, "mismatch": 0, "unverified": 0,
        "sg_round_distribution": Counter(), "official_round_distribution": Counter(),
    })
    year_stats: dict[str, dict] = defaultdict(lambda: {"population": 0, "verified": 0, "mismatch": 0, "unverified": 0})

    mismatch_examples: list[dict] = []
    unverified_examples: list[dict] = []
    cut_redteam_examples: list[dict] = []
    cut_redteam_phantom_count = 0

    player_index_cache: dict[str, dict] = {}
    max_round_cache: dict[str, int] = {}

    for (player_id, game_code), sg_row in cumulative_only.items():
        sg_rounds = int(sg_row.get("rounds") or 0)
        game_code_key = str(game_code)
        year = year_of_game_code(game_code_key)

        if game_code_key not in player_index_cache:
            event = events.get(game_code_key, {})
            player_index_cache[game_code_key] = build_player_index(event)
            max_round_cache[game_code_key] = max_retrieved_round(events, game_code_key)

        rows = player_index_cache[game_code_key].get(str(player_id), [])
        best_row = best_snapshot(rows)
        archive_max_round = max_round_cache[game_code_key]

        ev = event_stats[game_code_key]
        ev["population"] += 1
        ev["sg_round_distribution"][sg_rounds] += 1
        yr = year_stats[year]
        yr["population"] += 1

        if best_row is None:
            direction["unverified_no_official_row"] += 1
            ev["unverified"] += 1
            yr["unverified"] += 1
            if len(unverified_examples) < 10:
                unverified_examples.append({"player_id": player_id, "game_code": game_code, "sg_rounds": sg_rounds})
            continue

        official_rounds = count_nonnull_rounds(best_row.get("rounds"))
        ev["official_round_distribution"][official_rounds] += 1
        confusion_matrix[(sg_rounds, official_rounds)] += 1

        delta = official_rounds - sg_rounds
        delta_distribution[bucket_delta(delta)] += 1

        status = classify_competition_status(best_row, official_rounds, archive_max_round)
        competition_status_totals[status] += 1

        phantom = player_present_in_later_round_than_best(rows, best_row)
        if phantom:
            cut_redteam_phantom_count += 1
            if len(cut_redteam_examples) < 15:
                cut_redteam_examples.append({
                    "player_id": player_id, "game_code": game_code,
                    "best_snapshot_round": best_row.get("requested_round"),
                    "classified_status": status,
                    "rounds_this_player_appears_in": sorted({r.get("requested_round") for r in rows}),
                })

        is_verified = official_rounds == sg_rounds
        mismatch_rate_by_sg_rounds[sg_rounds]["population"] += 1
        mismatch_rate_by_status[status]["population"] += 1
        if is_verified:
            ev["verified"] += 1
            yr["verified"] += 1
            direction["sg_equal_official"] += 1
            mismatch_rate_by_sg_rounds[sg_rounds]["verified"] += 1
            mismatch_rate_by_status[status]["verified"] += 1
        else:
            ev["mismatch"] += 1
            yr["mismatch"] += 1
            mismatch_rate_by_sg_rounds[sg_rounds]["mismatch"] += 1
            mismatch_rate_by_status[status]["mismatch"] += 1
            player_mismatch_counter[str(player_id)] += 1
            if sg_rounds < official_rounds:
                direction["sg_less_than_official"] += 1
            else:
                direction["sg_greater_than_official"] += 1
            if len(mismatch_examples) < 30:
                mismatch_examples.append({
                    "player_id": player_id, "game_code": game_code,
                    "sg_rounds": sg_rounds, "official_rounds": official_rounds,
                    "delta": delta, "official_rounds_array": best_row.get("rounds"),
                    "official_status": best_row.get("status"),
                    "classified_competition_status": status,
                })

    # ---- finalize confusion matrix ----
    evidence_count = sum(v for k, v in direction.items() if k != "unverified_no_official_row")
    confusion_matrix_out = []
    for (sg_r, off_r), count in sorted(confusion_matrix.items()):
        confusion_matrix_out.append({
            "sg_rounds": sg_r, "official_rounds": off_r, "count": count,
            "pct_of_evidence_matched": round(100.0 * count / evidence_count, 3) if evidence_count else 0.0,
            "pct_of_total_population": round(100.0 * count / total_population, 3) if total_population else 0.0,
        })

    # ---- finalize event diagnostics ----
    event_list = []
    for game_code, stats in event_stats.items():
        pop = stats["population"]
        evidence = stats["verified"] + stats["mismatch"]
        mismatch_rate = round(stats["mismatch"] / evidence, 4) if evidence else None
        event_list.append({
            "game_code": game_code,
            "year": year_of_game_code(game_code),
            "population": pop,
            "verified": stats["verified"],
            "mismatch": stats["mismatch"],
            "unverified": stats["unverified"],
            "mismatch_rate": mismatch_rate,
            "sg_round_distribution": {str(k): v for k, v in sorted(stats["sg_round_distribution"].items())},
            "official_round_distribution": {str(k): v for k, v in sorted(stats["official_round_distribution"].items())},
        })
    worst_events = sorted(
        (e for e in event_list if e["mismatch_rate"] is not None),
        key=lambda e: (e["mismatch_rate"], e["population"]), reverse=True,
    )[:20]

    # ---- finalize year diagnostics ----
    year_list = []
    for year, stats in sorted(year_stats.items()):
        evidence = stats["verified"] + stats["mismatch"]
        year_list.append({
            "year": year, "population": stats["population"], "verified": stats["verified"],
            "mismatch": stats["mismatch"], "unverified": stats["unverified"],
            "mismatch_rate": round(stats["mismatch"] / evidence, 4) if evidence else None,
        })

    # ---- clustering summaries ----
    def _rate_table(counter_by_key: dict) -> dict:
        out = {}
        for key, c in counter_by_key.items():
            evidence = c.get("verified", 0) + c.get("mismatch", 0)
            out[str(key)] = {
                "population": c.get("population", 0), "verified": c.get("verified", 0),
                "mismatch": c.get("mismatch", 0),
                "mismatch_rate": round(c["mismatch"] / evidence, 4) if evidence else None,
            }
        return out

    worst_players = [
        {"player_id": pid, "mismatch_count": n}
        for pid, n in player_mismatch_counter.most_common(20)
    ]

    return {
        "schema_version": "neo_ranking_v2_round_count_mismatch_diagnostic_v1",
        "model_state": "VALIDATION_MODEL_NOT_PRODUCTION",
        "population_checked": total_population,
        "evidence_matched_count": evidence_count,
        "unverified_no_official_row_count": direction.get("unverified_no_official_row", 0),

        # Section 1
        "confusion_matrix": confusion_matrix_out,

        # Section 2
        "delta_distribution": dict(delta_distribution),

        # Section 3
        "event_diagnostics": {
            "events_checked": len(event_list),
            "worst_mismatch_events_top20": worst_events,
        },

        # Section 4
        "year_diagnostics": year_list,

        # Section 5 -- code-path citation, not inference (see report / docstring above)
        "sg_rounds_semantics_provenance": {
            "producer_script": "scripts/77_repair_sg_row_retention.py (only script that writes "
                                "historical_sg_warehouse_corrected.json -- confirmed via repo-wide search; "
                                "scripts/78_parallel_repair_sg.py writes a DIFFERENT file, "
                                "historical_sg_warehouse_corrected_v2.json)",
            "cumulative_request_params": "scripts/77_repair_sg_row_retention.py line ~24-26: "
                                          "for rnd in (None,*range(1,latest+1)): html=post(s,SG,{'gameCode':code,"
                                          "'round':'' if rnd is None else str(rnd)}); "
                                          "parse_sg_html(html, scope='tournament_cumulative' if rnd is None else "
                                          "'single_round', round_number=rnd) -- i.e. scope='tournament_cumulative' "
                                          "is ALWAYS the round='' (empty) request to strokesGained_detail, never "
                                          "a specific round number.",
            "rounds_field_source": "src/klpga/website_v2/official_data.py::parse_sg_html, line ~39: "
                                    "\"rounds\": int(_number(cells[8].get_text(strip=True)) or 0) -- read "
                                    "LITERALLY from the 9th <td> of the strokesGained_detail HTML table row "
                                    "(cells[0]=rank, [1]=player, [2:8]=the 6 SG stat columns, [8]=this field). "
                                    "There is NO local counting/summation logic anywhere in parse_sg_html -- "
                                    "it is whatever numeric value the KLPGA site itself renders in that column.",
            "known_fact": "The 'rounds' value on a tournament_cumulative row is copied verbatim from a column "
                          "the KLPGA site displays on its CUMULATIVE (round='') strokesGained_detail view.",
            "unresolved_hypothesis_not_asserted_as_fact": "Because this is the CUMULATIVE SG endpoint (not a "
                          "per-round request), this column plausibly represents 'how many rounds' worth of "
                          "SG data went into this cumulative total' -- which is a measure of SG-STAT COVERAGE, "
                          "not necessarily 'how many rounds this player officially competed in' (the official "
                          "leaderboard's round-score count). These are conceptually different quantities and "
                          "would explain a real, systematic mismatch if KLPGA's SG-tracking coverage does not "
                          "always equal tournament participation. This is a HYPOTHESIS grounded in the code "
                          "path above, not a proven fact -- no docstring, schema comment, or docs/*.md file "
                          "anywhere in the repo defines this column's meaning (confirmed by repo-wide search); "
                          "docs/KLPGA_OFFICIAL_DATA_MAP.md's only 'measured rounds' reference (lines ~133,213) "
                          "explicitly documents a DIFFERENT, season-level endpoint (loadLocationRecord), not "
                          "strokesGained_detail. Only the real confusion-matrix DIRECTION split above (section "
                          "8) can adjudicate this hypothesis -- see mismatch_direction.",
        },

        # Section 6
        "official_snapshot_audit": {
            "function_audited": "src/klpga/website_v2/round_count_audit_lib.py::best_snapshot",
            "current_rule": "selects the row (across all retrieved rounds for this player) with the most "
                             "non-null R1-R4 values, tie-broken by the highest requested_round.",
            "known_risk_not_yet_confirmed_against_real_data": "IF a player who has already exited the "
                          "tournament (CUT/WD/DQ) still appears in a LATER round's official leaderboard "
                          "response with the SAME (non-improving) score array -- rather than being excluded "
                          "from that response entirely -- then best_snapshot's tie-break (prefer highest "
                          "requested_round on a non-null-count tie) would select that later, stale row. This "
                          "does not change official_rounds (still counts real non-null values only, never "
                          "fabricated), but it DOES change best_row['requested_round'], which is the signal "
                          "the CUT classifier (section 7 below) depends on.",
            "verification_status": "UNCONFIRMED in this environment -- requires inspecting real archived rows "
                          "for a player known to have missed the cut, comparing their round-2 row against their "
                          "round-3/round-4 rows (if present) for identical vs. absent data. The "
                          "cut_classifier_redteam.phantom_later_round_appearance signal below is the "
                          "instrumentation added to answer this from real data once available.",
        },

        # Section 7
        "cut_classifier_redteam": {
            "current_105_rule": "classify_competition_status: best_row.requested_round < archive_max_round "
                                 "(the highest round this EVENT's archive actually retrieved) => CUT.",
            "reported_cut_count_context": "User-reported real run: CUT=12 across 97 events / 6294 player-events "
                                           "-- suspiciously low if a ~50% cut rate is typical for stroke-play "
                                           "fields, UNLESS most of these 97 events are 3-round (54-hole) "
                                           "tournaments without a traditional 36-hole cut, which the existing "
                                           "round_distribution ({\"3\": majority bucket}) makes plausible.",
            "phantom_later_round_appearance_signal": {
                "definition": "count of player-events where the player has an archived row in a round STRICTLY "
                               "AFTER their best (fullest) snapshot's round -- i.e. they are NOT actually "
                               "absent from later official responses, only their score array never grew. If "
                               "this count is non-trivial, the current CUT rule's 'absence = cut' assumption "
                               "is invalidated for those specific player-events and the CUT classifier is "
                               "WRONG for them, not just imprecise.",
                "phantom_count": cut_redteam_phantom_count,
                "examples": cut_redteam_examples,
            },
            "verdict": (
                "UNRESOLVED pending real archive data in this environment -- phantom_count is computed against "
                "whatever leaderboard archive is actually on disk when this script runs. If phantom_count > 0 "
                "when run against the real Windows-retrieved archive, the current CUT classifier must be "
                "marked WRONG for those cases (not silently trusted), and scripts/105's CUT logic needs a "
                "stronger signal (e.g. explicit rank/status text for 'CUT' if KLPGA's HTML renders one, which "
                "parse_leaderboard_html does not currently extract beyond WD/DQ) before any V2 backtest can "
                "treat competition_status as ground truth. This diagnostic does NOT auto-repair the classifier "
                "-- it only instruments and reports the evidence."
            ),
        },

        # Section 8
        "mismatch_direction": dict(direction),

        # Section 9
        "clustering_patterns": {
            "by_sg_rounds": _rate_table(mismatch_rate_by_sg_rounds),
            "by_competition_status": _rate_table(mismatch_rate_by_status),
            "worst_players_by_mismatch_count": worst_players,
        },

        "competition_status_totals": dict(competition_status_totals),
        "duplicate_cumulative_snapshots_collapsed": duplicate_cumulative_snapshots,
        "single_round_only_events_excluded_not_mixed_in": len(single_round_only_events),
        "mismatch_examples": mismatch_examples,
        "unverified_examples": unverified_examples,
    }


def main() -> int:
    sg_path = CONTENT / "historical_sg_warehouse_corrected.json"
    archive_path = CONTENT / "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json"

    sg = json.loads(sg_path.read_text(encoding="utf-8"))
    archive = None
    archive_sha = None
    if archive_path.exists():
        archive = json.loads(archive_path.read_text(encoding="utf-8"))
        archive_sha = sha256_of(archive_path)

    report = build_diagnostic(sg, archive)
    report["input_sha256"] = {
        "historical_sg_warehouse_corrected.json": sha256_of(sg_path),
        "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json": archive_sha,
    }

    out_path = CONTENT / "NEO_RANKING_V2_ROUND_COUNT_MISMATCH_DIAGNOSTIC.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "population_checked": report["population_checked"],
        "evidence_matched_count": report["evidence_matched_count"],
        "mismatch_direction": report["mismatch_direction"],
        "cut_redteam_phantom_count": report["cut_classifier_redteam"]["phantom_later_round_appearance_signal"]["phantom_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
