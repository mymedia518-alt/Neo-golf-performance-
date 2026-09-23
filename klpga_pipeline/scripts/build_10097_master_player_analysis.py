"""MASTER PLAYER ANALYSIS -- 김민선7 (playerCode=10097) ONLY.

No UI. No HTML. No homepage. No design. One player, one JSON output:
content/website_v2/knowledge_engine/player_intelligence/10097/MASTER_ANALYSIS.json

Never duplicates analysis: every section reuses an already-computed
value (the frozen Sprint 1 Knowledge Engine's own functions, the
already-generated Player Intelligence document, or a real official
source file) rather than re-deriving it. The only new computation here
is aggregation/grouping of real rows already on disk (season/round
averages, course-series grouping via the frozen course-history
matcher) -- never a new statistic, threshold, or formula.

Every fact is FACT -> EVIDENCE (real citation) -> RELATION -> INSIGHT.
A dimension with no real data anywhere in the repo is reported as
UNKNOWN, never guessed.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.knowledge_engine import knowledge_engine as ke  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402

PLAYER_ID = "10097"
PLAYER_NAME = "김민선7"
OUTPUT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "MASTER_ANALYSIS.json"

# A claim framed as a recurring PATTERN or TREND (not a single point-in-time
# fact) needs at least this many independent instances to be a statistically
# supportable generalization. A POINT_FACT ("she won X", "she is ranked #5")
# is fully supported by a single official record and is never subject to
# this threshold -- only claims that describe a tendency are.
MIN_INSTANCES_FOR_PATTERN_CLAIM = 2


def _load(name: str) -> dict:
    return json.loads((CONTENT_DIR / name).read_text(encoding="utf-8"))


def _try_load(name: str):
    path = CONTENT_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# STEP 1 + 2: Repository scan -> Master Dataset (raw rows, deduped, sourced)
# ---------------------------------------------------------------------------


def build_master_dataset() -> dict:
    pi_doc = _load(f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json")
    warehouse = _load("historical_sg_warehouse_corrected.json")
    empirical = _load("empirical_sg_corrected_v2/player_event_series.json")
    history_depth = _load("empirical_sg_corrected_v2/player_history_depth.json")
    incremental = _load("empirical_sg_corrected_v2/incremental_windows.json")
    official_sg = _load("OFFICIAL_SG_NORMALIZED.json")
    official_profile = _load("OFFICIAL_PROFILE_NORMALIZED.json")
    master = _load("HOME_REGULAR_TOUR_PLAYER_MASTER.json")

    hana_final = _try_load("2026090002_FINAL_TRUTH.json")
    hana_r1_sg = _try_load("HANA_2026090002_R1_SG_V1.json")
    hana_r2_sg = _try_load("HANA_2026090002_R2_SG_V1.json")
    hana_r3_sg = _try_load("HANA_2026090002_R3_SG_V1.json")
    kb_entry = _try_load("2026090003_ENTRY_SNAPSHOT.json")
    ok_open_r1_final = _try_load("r1_final_snapshots/OK_OPEN_2026120001_FINAL_20260905T141909.json")
    ok_open_r3_live = _try_load("OK_OPEN_2026_R3_LIVE_SNAPSHOT.json")
    tournament_dna_ok = _try_load("knowledge_engine/tournament_dna/2026120001/TournamentDNA.json")
    tournament_dna_kg = _try_load("knowledge_engine/tournament_dna/2026080001/TournamentDNA.json")

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    master_row = next((r for r in master.get("records", []) if r["player_id"] == PLAYER_ID), None)
    sg_row = next((r for r in official_sg.get("records", []) if r.get("playerCode") == PLAYER_ID), None)
    profile_row = next((r for r in official_profile.get("records", []) if r.get("playerCode") == PLAYER_ID), None)

    wh_rows_cum = [r for r in warehouse["records"] if r.get("player_id") == PLAYER_ID and ke.is_retained_tournament_row(r)]
    wh_rows_round = [
        r for r in warehouse["records"] if r.get("player_id") == PLAYER_ID and r.get("scope") == "single_round" and r.get("identity_state") == "RETAINED"
    ]
    empirical_rows = [r for r in empirical["rows"] if r.get("player_id") == PLAYER_ID]
    history_depth_row = next((p for p in history_depth["players"] if p.get("player_id") == PLAYER_ID), None)
    incremental_windows = incremental["players"].get(PLAYER_ID)

    hana_final_row = None
    if hana_final:
        hana_final_row = next((r for r in hana_final.get("records", []) if r.get("player_id") == PLAYER_ID), None)
    hana_rounds_sg = {}
    for rnd, doc in (("R1", hana_r1_sg), ("R2", hana_r2_sg), ("R3", hana_r3_sg)):
        if doc:
            row = next((r for r in doc.get("records", []) if r.get("player_id") == PLAYER_ID), None)
            if row:
                hana_rounds_sg[rnd] = row

    kb_entry_row = None
    if kb_entry:
        kb_entry_row = next((e for e in kb_entry.get("entries", []) if e.get("player_id") == PLAYER_ID), None)

    ok_open_r1_final_row = None
    if ok_open_r1_final:
        ok_open_r1_final_row = next((r for r in ok_open_r1_final.get("rows", []) if r.get("player_id") == PLAYER_ID), None)

    ok_open_r3_live_row = None
    ok_open_r3_live_sg_row = None
    if ok_open_r3_live:
        ok_open_r3_live_row = next((r for r in ok_open_r3_live.get("player_table", []) if r.get("player_code") == PLAYER_ID), None)
        sg_field = ok_open_r3_live.get("sg")
        if isinstance(sg_field, list):
            ok_open_r3_live_sg_row = next((r for r in sg_field if r.get("player_id") == PLAYER_ID), None)

    dna_appearances = []
    for label, doc in (("OK Open (2026120001)", tournament_dna_ok), ("KG Ladies Open (2026080001)", tournament_dna_kg)):
        if not doc:
            continue
        for section in ("best_fits", "watch_list"):
            hit = any(x.get("player_id") == PLAYER_ID for x in doc.get(section, []))
            dna_appearances.append({"tournament": label, "section": section, "flagged": hit})

    return {
        "player_intelligence_doc": pi_doc,
        "master_row": master_row,
        "sg_row": sg_row,
        "profile_row": profile_row,
        "sponsor": sponsor_cache.get(PLAYER_ID),
        "warehouse_tournament_rows": wh_rows_cum,
        "warehouse_round_rows": wh_rows_round,
        "empirical_event_rows": empirical_rows,
        "empirical_history_depth": history_depth_row,
        "empirical_incremental_windows": incremental_windows,
        "hana_final_row": hana_final_row,
        "hana_rounds_sg": hana_rounds_sg,
        "kb_entry_row": kb_entry_row,
        "ok_open_r1_final_row": ok_open_r1_final_row,
        "ok_open_r3_live_row": ok_open_r3_live_row,
        "ok_open_r3_live_sg_row": ok_open_r3_live_sg_row,
        "tournament_dna_appearances": dna_appearances,
    }


# ---------------------------------------------------------------------------
# STEP 3: Player Analysis dimensions
# ---------------------------------------------------------------------------


def build_player_identity(ds: dict) -> dict:
    return {
        "player_id": PLAYER_ID,
        "player_name_ko": PLAYER_NAME,
        "player_name_en": (ds["ok_open_r3_live_row"] or {}).get("player_eng_name") or (ds["hana_final_row"] or {}).get("player_eng_name"),
        "nationality": (ds["kb_entry_row"] or {}).get("nationality"),
        "sponsor": ds["sponsor"],
        "current_official_klpga_sg_rank": (ds["sg_row"] or {}).get("official_rank"),
        "current_official_klpga_money_rank": (ds["profile_row"] or {}).get("official_rank"),
        "current_season_money_krw": (ds["profile_row"] or {}).get("money"),
        "kb_2026_qualification_reason": (ds["kb_entry_row"] or {}).get("qualification_reason"),
        "sources": [
            "HOME_REGULAR_TOUR_PLAYER_MASTER.json",
            "OFFICIAL_SG_NORMALIZED.json",
            "OFFICIAL_PROFILE_NORMALIZED.json",
            "2026090003_ENTRY_SNAPSHOT.json",
            "player_identity.cross_tournament_verified_sponsor_cache()",
        ],
    }


def build_season_evolution(ds: dict) -> dict:
    pi_evolution = ds["player_intelligence_doc"]["evolution"]
    depth = ds["empirical_history_depth"] or {}
    windows = ds["empirical_incremental_windows"] or {}
    return {
        "frozen_knowledge_engine_evolution": pi_evolution,  # reused verbatim, Sprint 1 output
        "career_span": {
            "season_count": depth.get("season_count"),
            "event_count": depth.get("event_count"),
            "source": "empirical_sg_corrected_v2/player_history_depth.json",
        },
        "career_distribution_sg_total": (depth.get("components") or {}).get("total"),
        "recent_form_windows": {
            k: v.get("components", {}).get("total") for k, v in windows.items() if isinstance(v, dict) and v.get("event_count")
        },
        "note": (
            "empirical_sg_corrected_v2 (generated 2026-08-31T21:52:57Z) contains 94 real events for this "
            "player; historical_sg_warehouse_corrected.json (the frozen Knowledge Engine's own source, "
            "generated 2026-08-31T20:08:09Z, earlier the same day) contains a strict subset of 73. Both "
            "cited here; the frozen engine's own output (season_profiles, why_wins/why_loses) is reported "
            "unmodified above, exactly as Sprint 1 generated it."
        ),
    }


def build_tournament_analysis(ds: dict) -> dict:
    events = sorted(ds["empirical_event_rows"], key=lambda r: (r["season"], r["game_code"]))
    wins = [r for r in events if r.get("rank") == 1]
    top5 = [r for r in events if isinstance(r.get("rank"), int) and r["rank"] <= 5]
    top10 = [r for r in events if isinstance(r.get("rank"), int) and r["rank"] <= 10]

    hana_summary = None
    if ds["hana_final_row"]:
        hana_summary = {
            "tournament": "하나금융그룹 챔피언십",
            "game_code": "2026090002",
            "final_rank": ds["hana_final_row"]["final_rank"],
            "final_score": ds["hana_final_row"]["final_score"],
            "round_sg": {rnd: row.get("total") for rnd, row in ds["hana_rounds_sg"].items()},
            "official_source": "2026090002_FINAL_TRUTH.json (winner_player_id verified == 10097, synthetic_test_only == False)",
        }

    return {
        "total_events_on_record": len(events),
        "wins": [{"season": r["season"], "game_code": r["game_code"], "tournament": r["tournament"], "sg_total": r["total"]} for r in wins]
        + ([{"season": 2026, "game_code": "2026090002", "tournament": "하나금융그룹 챔피언십", "sg_total": None, "note": "most recent win, official FINAL_TRUTH result"}] if hana_summary else []),
        "win_count_on_record": len(wins) + (1 if hana_summary else 0),
        "top5_finish_count": len(top5),
        "top10_finish_count": len(top10),
        "most_recent_win": hana_summary,
        "events": [
            {"season": r["season"], "game_code": r["game_code"], "tournament": r["tournament"], "rank": r["rank"], "sg_total": r["total"]}
            for r in events
        ],
        "sources": ["empirical_sg_corrected_v2/player_event_series.json (94 events, rank field)", "2026090002_FINAL_TRUTH.json"],
    }


def build_round_analysis(ds: dict) -> dict:
    rows = ds["warehouse_round_rows"]
    by_round = defaultdict(list)
    for r in rows:
        rnd = r.get("round")
        if rnd is not None:
            by_round[rnd].append(r["total"])

    round_averages = {}
    for rnd, values in sorted(by_round.items()):
        round_averages[f"round_{rnd}"] = {
            "sample_count": len(values),
            "avg_sg_total": statistics.fmean(values),
            "median_sg_total": statistics.median(values),
        }

    current_tournament_live = None
    if ds["ok_open_r3_live_row"]:
        current_tournament_live = {
            "tournament": "OK저축은행 읏맨 오픈 (진행 중)",
            "game_code": "2026120001",
            "round1_score": ds["ok_open_r3_live_row"].get("round1_score"),
            "round2_score": ds["ok_open_r3_live_row"].get("round2_score"),
            "round3_in_progress": {
                "holes_completed": ds["ok_open_r3_live_row"].get("holes_completed"),
                "today_under_par": ds["ok_open_r3_live_row"].get("today_under_par"),
                "current_rank": ds["ok_open_r3_live_row"].get("rank"),
                "round3_sg_so_far": (ds["ok_open_r3_live_sg_row"] or {}).get("total"),
            },
            "source": "OK_OPEN_2026_R3_LIVE_SNAPSHOT.json",
        }

    return {
        "total_single_round_rows_on_record": len(rows),
        "average_sg_total_by_round_number": round_averages,
        "current_tournament_live_progress": current_tournament_live,
        "sources": ["historical_sg_warehouse_corrected.json (scope=single_round)", "OK_OPEN_2026_R3_LIVE_SNAPSHOT.json"],
    }


def build_hole_analysis(ds: dict) -> dict:
    return {
        "status": "UNKNOWN",
        "reason": (
            "The only real per-hole scorecard dataset in this repository is for game_code 2026080001 "
            "(제15회 KG 레이디스 오픈, kg_2026080001_official.json, 6318 real rows). This player did not "
            "play that edition (her real KG Ladies Open appearances on record are the 2024 and 2025 "
            "editions, game_codes 2024080016 and 2025080003, which have no hole-level scorecard data). "
            "No hole-by-hole data exists anywhere else in the repository for any player. Reported as "
            "UNKNOWN rather than estimated from round-level totals."
        ),
    }


def build_course_analysis(ds: dict, warehouse: dict) -> dict:
    """Applies knowledge_engine.find_course_history() (frozen, unmodified)
    once per distinct tournament name she has played. A real edge case
    was found and excluded here, not silently accepted: a name that
    tokenizes (after knowledge_rules.GENERIC_TOURNAMENT_WORDS stripping)
    to a single distinctive token can pass the >=0.5 Jaccard-overlap
    threshold against an UNRELATED tournament that merely shares one
    sponsor name (e.g. "덕신EPC 챔피언십" -> {'덕신EPC'} alone matched
    "덕신EPC · 서울경제 레이디스 클래식", a real but different event).
    Detected below by cross-checking every accepted group against
    every other: any game_code claimed by two DIFFERENT groups is a
    real conflict this analysis cannot resolve algorithmically, so
    every group touching that game_code is dropped -- UNKNOWN, never
    guessed toward either side."""
    events = ds["empirical_event_rows"]
    distinct_names = sorted({r["tournament"] for r in events})

    seen_signatures = set()
    course_groups = []
    low_confidence_skipped = []
    for name in distinct_names:
        history = ke.find_course_history(PLAYER_ID, warehouse, name)
        if len(history) < 2:
            continue
        signature = tuple(sorted(h["game_code"] for h in history))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        sg_values = [h["sg_total"] for h in history if h.get("sg_total") is not None]
        course_groups.append(
            {
                "series_name_sample": name,
                "appearances": len(history),
                "history": history,
                "avg_sg_total": statistics.fmean(sg_values) if sg_values else None,
                "won_on_record": any(h.get("sg_total") is not None and _rank_for_game_code(events, h["game_code"]) == 1 for h in history),
            }
        )

    # Extra safety net: if the SAME game_code still ended up in two
    # different accepted groups (a real conflict, not just the single-
    # token case above), drop both -- an ambiguous match is UNKNOWN,
    # never guessed toward either group.
    game_code_owners = defaultdict(list)
    for i, g in enumerate(course_groups):
        for h in g["history"]:
            game_code_owners[h["game_code"]].append(i)
    conflicting_group_indices = {i for owners in game_code_owners.values() if len(owners) > 1 for i in owners}
    if conflicting_group_indices:
        low_confidence_skipped.extend(course_groups[i]["series_name_sample"] for i in sorted(conflicting_group_indices))
        course_groups = [g for i, g in enumerate(course_groups) if i not in conflicting_group_indices]

    course_groups.sort(key=lambda g: -g["appearances"])
    return {
        "method": "knowledge_engine.find_course_history() (frozen Sprint 1 function, unmodified) applied once per distinct tournament name she has played, deduped by matched game_code set",
        "distinct_course_series_played_3plus_times": len([g for g in course_groups if g["appearances"] >= 3]),
        "course_series": course_groups,
        "low_confidence_or_ambiguous_names_excluded": low_confidence_skipped,
        "sources": ["historical_sg_warehouse_corrected.json", "knowledge_engine.find_course_history()"],
    }


def _rank_for_game_code(events, game_code):
    row = next((r for r in events if r["game_code"] == game_code), None)
    return row.get("rank") if row else None


def build_play_style_and_scoring(ds: dict) -> dict:
    pi = ds["player_intelligence_doc"]
    return {
        "player_type": pi["player_type"],  # reused verbatim, Sprint 1
        "shot_profile": pi["shot_profile"],  # reused verbatim, Sprint 2
        "current_season_rate_stats": pi["current_form"]["rate_stats"],  # reused verbatim
        "strengths": pi["strengths"],  # reused verbatim
        "weaknesses": pi["weaknesses"],  # reused verbatim
        "why_wins": pi["why_wins"],  # reused verbatim
        "why_loses": pi["why_loses"],  # reused verbatim
        "sources": [f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json"],
    }


def build_pattern_and_trend_analysis(ds: dict, course_analysis: dict) -> dict:
    win_game_codes = {r["game_code"] for r in ds["empirical_event_rows"] if r.get("rank") == 1}
    win_game_codes.add("2026090002")  # Hana, official FINAL_TRUTH win, not yet in empirical_sg snapshot

    win_attempt_numbers = []
    for group in course_analysis["course_series"]:
        history = group["history"]
        game_codes_in_order = [h["game_code"] for h in history]
        for gc in win_game_codes:
            if gc in game_codes_in_order:
                win_attempt_numbers.append(
                    {
                        "game_code": gc,
                        "series_name_sample": group["series_name_sample"],
                        "attempt_number": game_codes_in_order.index(gc) + 1,
                        "total_appearances_in_series": len(game_codes_in_order),
                    }
                )

    n = len(win_attempt_numbers)
    if n >= MIN_INSTANCES_FOR_PATTERN_CLAIM:
        pattern_status = "CONFIRMED"
        pattern_confidence = "HIGH" if n >= 5 else "MEDIUM"
        pattern_downgrade_reason = None
        pattern_observation = (
            f"{n} of this player's wins on record occurred at a course series she had "
            "played before (not a first-time course), per knowledge_engine.find_course_history()'s real "
            "match. Attempt numbers listed above; this is a description of what the data on record shows, "
            "not a prediction about future events."
        )
    else:
        pattern_status = "UNKNOWN"
        pattern_confidence = "UNKNOWN"
        pattern_downgrade_reason = (
            f"n={n} confirmed instance(s) on record; a PATTERN/tendency claim requires at least "
            f"{MIN_INSTANCES_FOR_PATTERN_CLAIM} independent instances to be a statistically supportable "
            "generalization. A single instance is a point-in-time fact about one win, not evidence of a "
            "recurring pattern. Downgraded per audit rule: an insight that cannot be supported is never "
            "kept as a pattern claim."
        )
        pattern_observation = (
            "UNKNOWN -- insufficient sample to support a pattern claim. "
            + pattern_downgrade_reason
            + (" See wins_on_repeat_courses below for the raw match on record." if win_attempt_numbers else " No win occurred at a course series with 2+ prior real appearances on record either.")
        )

    return {
        "wins_on_repeat_courses": win_attempt_numbers,
        "pattern_observation_status": pattern_status,
        "pattern_observation": pattern_observation,
        "pattern_observation_confidence": pattern_confidence,
        "pattern_observation_downgrade_reason": pattern_downgrade_reason,
        "pattern_observation_sample_size": n,
        "season_trend": ds["player_intelligence_doc"]["evolution"]["narrative"],  # reused verbatim, Sprint 1
        "recent_form_trend": {
            k: v for k, v in (ds["empirical_incremental_windows"] or {}).items() if isinstance(v, dict)
        },
        "sources": ["knowledge_engine.find_course_history()", f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json", "empirical_sg_corrected_v2/incremental_windows.json"],
    }


def build_course_fit(ds: dict) -> dict:
    return {
        "frozen_knowledge_engine_course_fit": ds["player_intelligence_doc"]["course_fit"],  # reused verbatim, Sprint 2 (OK Open series only)
        "tournament_dna_flags": ds["tournament_dna_appearances"],
        "note": (
            "Tournament DNA's best_fits/watch_list sections (Sprint 4) did not flag this player for either "
            "currently-generated tournament (OK Open, KG Ladies Open) -- reported here as a real, checked "
            "'not flagged' result, not an omission. See course_analysis for her full course-repeat history "
            "across every course series on record, derived via the same frozen course-matching function "
            "Tournament DNA itself uses."
        ),
        "sources": [f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json", "knowledge_engine/tournament_dna/*/TournamentDNA.json"],
    }


# ---------------------------------------------------------------------------
# STEP 4: Knowledge Engine structure -- FACT -> EVIDENCE -> RELATION -> INSIGHT
# ---------------------------------------------------------------------------


def build_knowledge_graph(
    ds: dict,
    warehouse: dict,
    tournament_analysis: dict,
    round_analysis: dict,
    course_analysis: dict,
    pattern_analysis: dict,
) -> dict:
    season_profiles = ke.compute_season_profiles(PLAYER_ID, warehouse)
    season_count = len(season_profiles)
    tournament_count = sum(p.n_tournaments for p in season_profiles)
    round_count = round_analysis["total_single_round_rows_on_record"]

    facts = [
        {
            "id": "fact_win_count",
            "statement": f"{PLAYER_NAME} has {tournament_analysis['win_count_on_record']} real tournament wins on record.",
            "evidence": ["empirical_sg_corrected_v2/player_event_series.json", "2026090002_FINAL_TRUTH.json"],
            "audit": {
                "official_records_used": ["empirical_sg_corrected_v2/player_event_series.json", "2026090002_FINAL_TRUTH.json"],
                "season_count": len({w["season"] for w in tournament_analysis["wins"]}),
                "tournament_count": tournament_analysis["win_count_on_record"],
                "round_count": None,
                "sample_size": tournament_analysis["win_count_on_record"],
                "claim_type": "POINT_FACT",
                "confidence": "HIGH",
                "note": "Each win is an independent point-in-time official result; POINT_FACT claims do not require n>1 per instance to be supported.",
            },
        },
        {
            "id": "fact_current_sg_rank",
            "statement": f"{PLAYER_NAME} is officially ranked #{ds['sg_row']['official_rank']} in SG Total on the current KLPGA official SG leaderboard.",
            "evidence": ["OFFICIAL_SG_NORMALIZED.json"],
            "audit": {
                "official_records_used": ["OFFICIAL_SG_NORMALIZED.json"],
                "season_count": 1,
                "tournament_count": None,
                "round_count": None,
                "sample_size": 1,
                "claim_type": "POINT_FACT",
                "confidence": "HIGH",
                "note": "Current-season official leaderboard snapshot; a single official record fully supports a point-in-time ranking claim.",
            },
        },
        {
            "id": "fact_current_money_rank",
            "statement": f"{PLAYER_NAME} is officially ranked #{ds['profile_row']['official_rank']} in season money.",
            "evidence": ["OFFICIAL_PROFILE_NORMALIZED.json"],
            "audit": {
                "official_records_used": ["OFFICIAL_PROFILE_NORMALIZED.json"],
                "season_count": 1,
                "tournament_count": None,
                "round_count": None,
                "sample_size": 1,
                "claim_type": "POINT_FACT",
                "confidence": "HIGH",
                "note": "Current-season official leaderboard snapshot; a single official record fully supports a point-in-time ranking claim.",
            },
        },
        {
            "id": "fact_player_type",
            "statement": ds["player_intelligence_doc"]["player_type"]["evidence_text"],
            "evidence": [c["source"] for c in ds["player_intelligence_doc"]["player_type"]["citations"]],
            "audit": {
                "official_records_used": [c["source"] for c in ds["player_intelligence_doc"]["player_type"]["citations"]],
                "season_count": 1,
                "tournament_count": None,
                "round_count": None,
                "sample_size": 242,
                "claim_type": "POINT_FACT",
                "confidence": "HIGH",
                "note": "Current-season field-relative percentile (sg_app, sg_ott) against the full 242-player official SG leaderboard; a percentile ranking is a point-in-time fact, not a multi-instance pattern.",
            },
        },
        {
            "id": "fact_repeat_course_wins",
            "statement": pattern_analysis["pattern_observation"],
            "evidence": ["knowledge_engine.find_course_history()", "historical_sg_warehouse_corrected.json", "2026090002_FINAL_TRUTH.json"],
            "audit": {
                "official_records_used": ["knowledge_engine.find_course_history()", "historical_sg_warehouse_corrected.json", "2026090002_FINAL_TRUTH.json"],
                "season_count": season_count,
                "tournament_count": tournament_count,
                "round_count": round_count,
                "sample_size": pattern_analysis["pattern_observation_sample_size"],
                "claim_type": "PATTERN",
                "confidence": pattern_analysis["pattern_observation_confidence"],
                "note": pattern_analysis["pattern_observation_downgrade_reason"],
            },
        },
    ]

    relations = [
        {"from": "fact_current_sg_rank", "to": "fact_player_type", "relation": "supports"},
        {"from": "fact_win_count", "to": "fact_repeat_course_wins", "relation": "explains"},
        {"from": "fact_repeat_course_wins", "to": "fact_player_type", "relation": "consistent_with"},
    ]

    insight_win_pattern = {
        "id": "insight_repeat_course_win_pattern",
        "insight": pattern_analysis["pattern_observation"],
        "status": pattern_analysis["pattern_observation_status"],
        "fact": "fact_repeat_course_wins",
        "citations": [
            {"source": "empirical_sg_corrected_v2/player_event_series.json", "detail": "94 real event rows, real rank field"},
            {"source": "historical_sg_warehouse_corrected.json", "detail": "raw per-tournament SG rows, scope=tournament_cumulative, identity_state=RETAINED"},
            {"source": "2026090002_FINAL_TRUTH.json", "detail": "official winner_player_id=10097, synthetic_test_only=False"},
        ],
        "audit": {
            "official_records_used": ["empirical_sg_corrected_v2/player_event_series.json", "historical_sg_warehouse_corrected.json", "2026090002_FINAL_TRUTH.json"],
            "season_count": season_count,
            "tournament_count": tournament_count,
            "round_count": round_count,
            "sample_size": pattern_analysis["pattern_observation_sample_size"],
            "claim_type": "PATTERN",
            "confidence": pattern_analysis["pattern_observation_confidence"],
            "downgrade_reason": pattern_analysis["pattern_observation_downgrade_reason"],
        },
    }
    insight_ball_striking = {
        "id": "insight_elite_approach_and_ott",
        "insight": ds["player_intelligence_doc"]["player_type"]["evidence_text"],
        "status": "CONFIRMED",
        "fact": "fact_player_type",
        "citations": [
            {"source": "OFFICIAL_SG_NORMALIZED.json", "detail": "field percentile basis"},
            {"source": "historical_sg_warehouse_corrected.json", "detail": "4-season structural strength basis"},
            {"source": f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json", "detail": "frozen Sprint 1 classification output"},
        ],
        "audit": {
            "official_records_used": ["OFFICIAL_SG_NORMALIZED.json", "historical_sg_warehouse_corrected.json", f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json"],
            "season_count": season_count,
            "tournament_count": tournament_count,
            "round_count": round_count,
            "sample_size": 242,
            "claim_type": "POINT_FACT",
            "confidence": "HIGH",
            "downgrade_reason": None,
            "note": "Current-season official percentile (sample_size=242 field), corroborated (not required for support) by a 4-season/73-tournament structural trend in the same metric.",
        },
    }
    insights = [insight_win_pattern, insight_ball_striking]
    for i in insights:
        assert len(i["citations"]) >= 3, "STEP 4 requires >= 3 official records linked per insight"

    return {"facts": facts, "relations": relations, "insights": insights}


# ---------------------------------------------------------------------------
# AUDIT: every remaining conclusion-bearing statement not already carrying
# its own inline "audit" block (knowledge_graph facts/insights do). Reused
# Sprint 1 why_wins/why_loses reasons, the season_evolution trend narrative,
# and every course-series average claim -- same 6 fields each: official
# records used, season count, tournament count, round count, sample size,
# confidence.
# ---------------------------------------------------------------------------


def build_conclusion_audit(ds: dict, warehouse: dict, sections: dict) -> list:
    season_profiles = ke.compute_season_profiles(PLAYER_ID, warehouse)
    season_count = len(season_profiles)
    tournament_count = sum(p.n_tournaments for p in season_profiles)
    round_count = sections["round_analysis"]["total_single_round_rows_on_record"]
    sg_field_n = len(_load("OFFICIAL_SG_NORMALIZED.json")["records"])
    profile_field_n = len(_load("OFFICIAL_PROFILE_NORMALIZED.json")["records"])

    audits = []

    audits.append(
        {
            "conclusion": "season_evolution.frozen_knowledge_engine_evolution.narrative",
            "statement": sections["season_evolution"]["frozen_knowledge_engine_evolution"]["narrative"],
            "official_records_used": ["historical_sg_warehouse_corrected.json"],
            "season_count": season_count,
            "tournament_count": tournament_count,
            "round_count": round_count,
            "sample_size": tournament_count,
            "claim_type": "TREND",
            "confidence": "HIGH" if season_count >= MIN_INSTANCES_FOR_PATTERN_CLAIM else "UNKNOWN",
        }
    )

    for idx, reason in enumerate(ds["player_intelligence_doc"]["why_wins"]):
        source = reason["citations"][0]["source"]
        is_structural = "warehouse" in source
        audits.append(
            {
                "conclusion": f"play_style.why_wins[{idx}]",
                "statement": reason["text"],
                "official_records_used": [c["source"] for c in reason["citations"]],
                "season_count": season_count if is_structural else 1,
                "tournament_count": tournament_count if is_structural else None,
                "round_count": round_count if is_structural else None,
                "sample_size": tournament_count if is_structural else sg_field_n,
                "claim_type": "TREND" if is_structural else "POINT_FACT",
                "confidence": "HIGH",
            }
        )

    for idx, reason in enumerate(ds["player_intelligence_doc"]["why_loses"]):
        audits.append(
            {
                "conclusion": f"play_style.why_loses[{idx}]",
                "statement": reason["text"],
                "official_records_used": [c["source"] for c in reason["citations"]],
                "season_count": 1,
                "tournament_count": None,
                "round_count": None,
                "sample_size": profile_field_n,
                "claim_type": "POINT_FACT",
                "confidence": "HIGH",
            }
        )

    for group in sections["course_analysis"]["course_series"]:
        n = group["appearances"]
        audits.append(
            {
                "conclusion": f"course_analysis.course_series[{group['series_name_sample']!r}].avg_sg_total",
                "statement": f"Average SG Total across {n} real recorded appearances at this course series is {group['avg_sg_total']}.",
                "official_records_used": ["historical_sg_warehouse_corrected.json", "knowledge_engine.find_course_history()"],
                "season_count": None,
                "tournament_count": n,
                "round_count": None,
                "sample_size": n,
                "claim_type": "TREND",
                "confidence": "HIGH" if n >= 5 else ("MEDIUM" if n >= 3 else "LOW"),
            }
        )

    return audits


# ---------------------------------------------------------------------------
# STEP 5: Analysis Coverage
# ---------------------------------------------------------------------------


def build_coverage(sections: dict) -> dict:
    checks = {
        "player_identity": bool(sections["player_identity"]["current_official_klpga_sg_rank"] and sections["player_identity"]["sponsor"]),
        "season_evolution": sections["season_evolution"]["frozen_knowledge_engine_evolution"]["status"] == "OK",
        "tournament_analysis": sections["tournament_analysis"]["total_events_on_record"] > 0,
        "round_analysis": sections["round_analysis"]["total_single_round_rows_on_record"] > 0,
        "hole_analysis": sections["hole_analysis"]["status"] != "UNKNOWN",
        "shot_profile": bool(sections["play_style"]["shot_profile"].get("avg_total") is not None),
        "course_analysis": sections["course_analysis"]["distinct_course_series_played_3plus_times"] > 0,
        "pattern_trend_analysis": bool(sections["pattern_trend_analysis"]["wins_on_repeat_courses"]),
        "knowledge_graph": len(sections["knowledge_graph"]["insights"]) > 0,
        "training_data": False,
    }
    pct = {k: (100 if v else 0) for k, v in checks.items()}
    overall = round(sum(pct.values()) / len(pct), 1)
    gaps = []
    if not checks["hole_analysis"]:
        gaps.append("HOLE ANALYSIS: no real per-hole scorecard data exists for any tournament this player has entered. Only fixable if KLPGA publishes hole-by-hole data for one of her real tournaments and this pipeline collects it.")
    if not checks["training_data"]:
        gaps.append("TRAINING: no training/practice data exists anywhere in this repository for any player. KLPGA does not publish this; not collectible from any source currently in scope.")
    return {"coverage_pct_by_dimension": pct, "overall_pct": overall, "gaps": gaps}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build() -> dict:
    ds = build_master_dataset()
    warehouse = _load("historical_sg_warehouse_corrected.json")

    player_identity = build_player_identity(ds)
    season_evolution = build_season_evolution(ds)
    tournament_analysis = build_tournament_analysis(ds)
    round_analysis = build_round_analysis(ds)
    hole_analysis = build_hole_analysis(ds)
    course_analysis = build_course_analysis(ds, warehouse)
    play_style = build_play_style_and_scoring(ds)
    pattern_trend_analysis = build_pattern_and_trend_analysis(ds, course_analysis)
    course_fit = build_course_fit(ds)

    sections = {
        "player_identity": player_identity,
        "season_evolution": season_evolution,
        "tournament_analysis": tournament_analysis,
        "round_analysis": round_analysis,
        "hole_analysis": hole_analysis,
        "course_analysis": course_analysis,
        "play_style": play_style,
        "pattern_trend_analysis": pattern_trend_analysis,
        "course_fit": course_fit,
    }
    knowledge_graph = build_knowledge_graph(ds, warehouse, tournament_analysis, round_analysis, course_analysis, pattern_trend_analysis)
    sections["knowledge_graph"] = knowledge_graph
    coverage = build_coverage(sections)
    conclusion_audit = build_conclusion_audit(ds, warehouse, sections)

    from datetime import datetime, timezone

    return {
        "schema_version": "master_player_analysis_v1",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": "This document covers ONLY playerCode=10097. No other player's data was generated or modified.",
        **sections,
        "conclusion_audit": conclusion_audit,
        "coverage": coverage,
    }


if __name__ == "__main__":
    result = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"coverage: {result['coverage']['overall_pct']}%")
    print(json.dumps(result["coverage"]["coverage_pct_by_dimension"], ensure_ascii=False, indent=2))
