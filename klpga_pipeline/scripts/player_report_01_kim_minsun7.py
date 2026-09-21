"""PLAYER INTELLIGENCE REPORT PROTOTYPE 01 -- 김민선7, 2026090002
(read-only, no network, no DB writes, no model, no SG, no ranking).

Answers "how did 김민선7 shoot -12 (276) and win by four strokes?"
purely from real official score data + real cmpro shot_event data.
This is NOT Expected Strokes, NOT SG, NOT a player-quality ranking --
every metric here is a directly observed count/rate/average, and every
average is reported with its denominator so a reader can see exactly
how many real observations back it.

Independent re-implementation of the qualifying-shot/green-reach/
avg-remaining/avg-strokes-after methodology from
scripts/experiment_01a_top10_150_175_lie_analysis.py (same RULES, own
code -- see Section J, which cross-checks this extractor's own
150-175yd numbers against Experiment 01A's prior verified output and
STOPS rather than silently reconciling if they differ).

Inputs (both READ ONLY):
    --sqlite <path to cmpro_<game>_full.sqlite>, or
    --transitions-csv <path to the already-generated transitions CSV>
    --official-score-source <a real captured scoreRecord HTML page for
        this game, ideally covering every round's tab-pane>
    --final-round-tab <the real tab id for the FINAL round, e.g.
        "round-four" -- REQUIRED, never defaulted or guessed>
    --player-name <default "김민선7">

Usage (from klpga_pipeline/):
    py scripts/player_report_01_kim_minsun7.py \
        --game 2026090002 \
        --sqlite data/cmpro_2026090002_full.sqlite \
        --official-score-source <real scoreRecord HTML> \
        --final-round-tab round-four

Writes (never overwrites source data):
    reports/player_intelligence/2026090002_kim_minsun7_prototype01.json
    reports/player_intelligence/2026090002_kim_minsun7_prototype01.csv

NOT committed/pushed by this script -- per explicit instruction, the
operator commits this separately after reviewing real output.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klpga.collectors.score_record import (
    parse_score_record_final_ranking,
    parse_score_record_hole_by_hole,
    parse_score_record_hole_par,
)
from klpga.expected_strokes.transitions import TransitionRow, build_transition_dataset

QUALIFYING_LIES = ("페어웨이", "러프", "벙커")
_ROUND_TAB_TO_NUMBER = {"round-one": 1, "round-two": 2, "round-three": 3, "round-four": 4}

# Experiment 01A's own verified reference numbers for 김민선7's
# 150-175yd shots (Section J cross-check target -- literal comparison
# values supplied by the operator from a prior real run, NOT this
# script's own guess). Only used for comparison; never used to compute
# anything.
EXPERIMENT_01A_REFERENCE = {
    "페어웨이": {"n": 4, "green_reach": 4, "green_reach_rate": 1.0, "avg_remaining_yd": 12.03, "avg_strokes_after": 2.00},
    "러프": {"n": 2, "green_reach": 0, "green_reach_rate": 0.0, "avg_remaining_yd": None, "avg_strokes_after": 2.00},
    "벙커": {"n": 0, "green_reach": None, "green_reach_rate": None, "avg_remaining_yd": None, "avg_strokes_after": None},
}


# ---------------------------------------------------------------
# Loading (read-only).
# ---------------------------------------------------------------

def load_rows_from_sqlite(sqlite_path: Path, game_code: str) -> list[TransitionRow]:
    conn = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)
    try:
        return build_transition_dataset(conn, game_code)
    finally:
        conn.close()


def _to_bool(text: str) -> bool:
    return text.strip().lower() == "true"


def load_rows_from_csv(csv_path: Path) -> list[TransitionRow]:
    rows: list[TransitionRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(TransitionRow(
                game_code=r["game_code"], player_code=r["player_code"], player_name=r["player_name"],
                round_number=int(r["round"]), hole=int(r["hole"]), shot_no=int(r["shot_no"]),
                par=int(r["par"]) if r["par"] else None,
                start_distance_yd=float(r["start_distance_yd"]) if r["start_distance_yd"] else None,
                start_lie=r["start_lie"] or "",
                end_distance_yd=float(r["end_distance_yd"]),
                end_lie=r["end_lie"] or "",
                holed=_to_bool(r["holed"]),
                zero_distance_ambiguous=_to_bool(r["zero_distance_ambiguous"]),
                official_hole_score=int(r["official_hole_score"]) if r["official_hole_score"] else None,
            ))
    return rows


def load_official_evidence(html: str) -> tuple[dict, dict, dict]:
    """Returns (par_by_round_hole, official_score_by_round_hole,
    final_ranking_rows_by_round). Best-effort per round -- a round
    whose tab-pane isn't in the supplied HTML is simply absent from the
    result (never guessed), and is reported in DATA QA."""
    par_by_round_hole: dict[tuple[int, int], int] = {}
    official_score_by_round_hole: dict[tuple[int, int], int] = {}
    blocked_rounds: list[str] = []
    for tab_id, rnd in _ROUND_TAB_TO_NUMBER.items():
        try:
            par = parse_score_record_hole_par(html, round_tab_id=tab_id)
            for h, p in par.items():
                par_by_round_hole[(rnd, h)] = p
        except ValueError:
            blocked_rounds.append(f"{tab_id}:par")
        try:
            rows = parse_score_record_hole_by_hole(html, round_tab_id=tab_id)
        except ValueError:
            blocked_rounds.append(f"{tab_id}:holes")
            continue
        for row in rows:
            if row["player_name"] != PLAYER_NAME_CONTEXT[0]:
                continue
            for h, score in row["holes"].items():
                if score is not None:
                    official_score_by_round_hole[(rnd, h)] = score
    return par_by_round_hole, official_score_by_round_hole, {"blocked": blocked_rounds}


# A module-level mutable single-item list used only to pass the target
# player_name into load_official_evidence without threading it through
# every call site -- set once in main() before load_official_evidence runs.
PLAYER_NAME_CONTEXT: list[str] = ["김민선7"]


# ---------------------------------------------------------------
# Pure helpers (unit-tested).
# ---------------------------------------------------------------

def classify_score_to_par(to_par: Optional[int]) -> Optional[str]:
    if to_par is None:
        return None
    if to_par <= -1:
        return "birdie_or_better"
    if to_par == 0:
        return "par"
    if to_par == 1:
        return "bogey"
    return "double_or_worse"


DISTANCE_BANDS = ("<100", "100-125", "125-150", "150-175", "175-200", "200+")


def distance_band(d: float) -> str:
    """Non-overlapping bands covering the real number line. The
    150-175 band is deliberately BOTH-ENDS INCLUSIVE (150.0<=d<=175.0)
    to exactly match Experiment 01A's own filter (needed for Section
    J's reproduction to be meaningful); the neighboring bands are
    defined around that fixed point so nothing is double-counted or
    skipped: <100 is d<100 (open), 100-125/125-150 are half-open up to
    (not including) their upper bound, 175-200 starts just AFTER 175
    (since 175 itself already belongs to 150-175), and 200+ is
    d>200 (200.0 itself belongs to 175-200)."""
    if d < 100.0:
        return "<100"
    if d < 125.0:
        return "100-125"
    if d < 150.0:
        return "125-150"
    if 150.0 <= d <= 175.0:
        return "150-175"
    if d <= 200.0:
        return "175-200"
    return "200+"


def group_by_hole(rows: list[TransitionRow]) -> dict[tuple[int, int], list[TransitionRow]]:
    groups: dict[tuple[int, int], list[TransitionRow]] = defaultdict(list)
    for r in rows:
        groups[(r.round_number, r.hole)].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r.shot_no)
    return groups


@dataclass(frozen=True)
class LieMetrics:
    n: int
    green_reach: int
    green_reach_rate: Optional[float]
    avg_remaining_yd: Optional[float]
    avg_remaining_denominator: int
    avg_remaining_excluded_unknown_end: int
    avg_strokes_after: Optional[float]
    avg_strokes_after_denominator: int
    terminal_integrity_failures: int


def compute_lie_metrics(shots: list[TransitionRow], hole_groups: dict) -> LieMetrics:
    """Independent re-implementation of Experiment 01A's own metric
    rules (see that script's compute_lie_metrics) -- same rules, own
    code, so Section J's cross-check is a genuine second derivation,
    not a re-run of the same function."""
    n = len(shots)
    green_reach = sum(1 for s in shots if s.end_lie == "그린")
    green_reach_rate = (green_reach / n) if n > 0 else None

    valid_end = [s for s in shots if s.end_lie != ""]
    excluded_unknown_end = n - len(valid_end)
    avg_remaining_yd = (sum(s.end_distance_yd for s in valid_end) / len(valid_end)) if valid_end else None

    strokes_after_values: list[int] = []
    terminal_failures = 0
    seen_terminal_check: set[tuple[int, int]] = set()
    for s in shots:
        key = (s.round_number, s.hole)
        hole_rows = hole_groups[key]
        terminal = hole_rows[-1]
        if terminal.end_lie != "홀인":
            if key not in seen_terminal_check:
                terminal_failures += 1
                seen_terminal_check.add(key)
            continue
        after = sum(1 for r in hole_rows if r.shot_no > s.shot_no)
        strokes_after_values.append(after)
    avg_strokes_after = (sum(strokes_after_values) / len(strokes_after_values)) if strokes_after_values else None

    return LieMetrics(
        n=n, green_reach=green_reach, green_reach_rate=green_reach_rate,
        avg_remaining_yd=avg_remaining_yd, avg_remaining_denominator=len(valid_end),
        avg_remaining_excluded_unknown_end=excluded_unknown_end,
        avg_strokes_after=avg_strokes_after, avg_strokes_after_denominator=len(strokes_after_values),
        terminal_integrity_failures=terminal_failures,
    )


def qualifying_shots_150_175(rows: list[TransitionRow], lie: str) -> list[TransitionRow]:
    out = []
    for r in rows:
        if r.start_lie != lie or r.start_distance_yd is None:
            continue
        if 150.0 <= r.start_distance_yd <= 175.0:
            out.append(r)
    return out


def sample_size_flag(n: int) -> str:
    if n < 5:
        return "VERY_SMALL_SAMPLE"
    if n < 10:
        return "SMALL_SAMPLE"
    return ""


def green_entry_shot(hole_rows: list[TransitionRow]) -> Optional[TransitionRow]:
    """First (lowest shot_no) shot in a hole whose end_lie=='그린' --
    never inferred from distance or shot position, only real end_lie."""
    for r in hole_rows:
        if r.end_lie == "그린":
            return r
    return None


def green_finish_shot_count(hole_rows: list[TransitionRow], entry_shot_no: int) -> Optional[int]:
    """Real count of shots after the green-entry shot through the
    terminal shot. Returns None (never a guessed number) if the
    terminal shot's end_lie != '홀인' (terminal integrity failure) --
    caller must check/report that separately."""
    terminal = hole_rows[-1]
    if terminal.end_lie != "홀인":
        return None
    return sum(1 for r in hole_rows if r.shot_no > entry_shot_no)


def shot_no_continuity_ok(hole_rows: list[TransitionRow]) -> bool:
    return [r.shot_no for r in hole_rows] == list(range(1, len(hole_rows) + 1))


# ---------------------------------------------------------------
# Section builders.
# ---------------------------------------------------------------

def section_a_identity(rows: list[TransitionRow], final_rank_rows: list[dict], player_name: str) -> dict:
    distinct_codes = {r.player_code for r in rows}
    ambiguous = len(distinct_codes) > 1
    player_code = next(iter(distinct_codes)) if len(distinct_codes) == 1 else None

    official_match = next((r for r in final_rank_rows if r["player_name"] == player_name), None)

    return {
        "player_name": player_name,
        "player_code": player_code,
        "identity_ambiguous_multiple_player_codes": sorted(distinct_codes) if ambiguous else None,
        "official_final_rank_display": official_match["rank_display"] if official_match else None,
        "official_final_score_to_par": official_match["total_to_par"] if official_match else None,
        "official_total_strokes": official_match["total_raw_strokes"] if official_match else None,
        "official_match_found": official_match is not None,
        "rounds_played": sorted({r.round_number for r in rows}),
        "holes_played": len({(r.round_number, r.hole) for r in rows}),
        "total_shots": len(rows),
    }


def section_b_round_by_round(rows: list[TransitionRow], par_by_round_hole: dict, official_score_by_round_hole: dict) -> dict:
    hole_groups = group_by_hole(rows)
    rounds_out = []
    mismatches = []
    for rnd in sorted({r.round_number for r in rows}):
        round_holes = sorted({h for (rr, h) in hole_groups if rr == rnd})
        reconstructed_by_hole = {h: len(hole_groups[(rnd, h)]) for h in round_holes}
        round_score = sum(reconstructed_by_hole.values())
        known_pars = {h: par_by_round_hole.get((rnd, h)) for h in round_holes}
        par_sum = sum(p for p in known_pars.values() if p is not None)
        par_known_all = all(p is not None for p in known_pars.values()) and round_holes
        to_par = (round_score - par_sum) if par_known_all else None

        counts = {"birdie_or_better": 0, "par": 0, "bogey": 0, "double_or_worse": 0, "unclassified_no_par": 0}
        front9 = sum(reconstructed_by_hole.get(h, 0) for h in round_holes if h <= 9)
        back9 = sum(reconstructed_by_hole.get(h, 0) for h in round_holes if h >= 10)
        for h in round_holes:
            par = known_pars[h]
            strokes = reconstructed_by_hole[h]
            cat = classify_score_to_par(strokes - par) if par is not None else None
            counts[cat or "unclassified_no_par"] += 1

            official = official_score_by_round_hole.get((rnd, h))
            if official is not None and official != strokes:
                mismatches.append({
                    "round": rnd, "hole": h, "reconstructed_shot_count": strokes, "official_hole_score": official,
                })

        rounds_out.append({
            "round": rnd, "round_raw_strokes": round_score, "to_par": to_par,
            "birdies_or_better": counts["birdie_or_better"], "pars": counts["par"],
            "bogeys": counts["bogey"], "double_or_worse": counts["double_or_worse"],
            "unclassified_no_par_source": counts["unclassified_no_par"],
            "front9_raw_strokes": front9, "back9_raw_strokes": back9,
            "holes_reconstructed": len(round_holes),
        })

    tournament_raw_total = sum(r["round_raw_strokes"] for r in rounds_out)
    tournament_to_par = sum(r["to_par"] for r in rounds_out if r["to_par"] is not None)
    tournament_to_par_complete = all(r["to_par"] is not None for r in rounds_out) and bool(rounds_out)

    return {
        "rounds": rounds_out,
        "tournament_raw_total_strokes": tournament_raw_total,
        "tournament_to_par": tournament_to_par if tournament_to_par_complete else None,
        "tournament_to_par_incomplete_par_source": not tournament_to_par_complete,
        "official_hole_score_mismatches": mismatches,
    }


def section_c_par_scoring(rows: list[TransitionRow], par_by_round_hole: dict) -> dict:
    hole_groups = group_by_hole(rows)
    by_par: dict[int, dict] = {3: defaultdict(int), 4: defaultdict(int), 5: defaultdict(int)}
    excluded_no_par = 0
    for (rnd, hole), hole_rows in hole_groups.items():
        par = par_by_round_hole.get((rnd, hole))
        if par not in (3, 4, 5):
            excluded_no_par += 1
            continue
        strokes = len(hole_rows)
        by_par[par]["holes"] += 1
        by_par[par]["total_strokes"] += strokes
        cat = classify_score_to_par(strokes - par)
        by_par[par][cat] += 1
    out = {}
    for par in (3, 4, 5):
        d = by_par[par]
        holes = d.get("holes", 0)
        out[f"par_{par}"] = {
            "holes": holes,
            "total_strokes": d.get("total_strokes", 0),
            "score_to_par": (d.get("total_strokes", 0) - holes * par) if holes else None,
            "birdie_or_better": d.get("birdie_or_better", 0),
            "par": d.get("par", 0),
            "bogey": d.get("bogey", 0),
            "double_or_worse": d.get("double_or_worse", 0),
        }
    out["excluded_no_verified_par_source"] = excluded_no_par
    return out


def section_d_tee_shot_profile(rows: list[TransitionRow], par_by_round_hole: dict) -> dict:
    first_shots = [r for r in rows if r.shot_no == 1]
    groups: dict[str, list[TransitionRow]] = defaultdict(list)
    for r in first_shots:
        par = par_by_round_hole.get((r.round_number, r.hole))
        key = f"par_{par}" if par in (3, 4, 5) else "par_unknown"
        groups[key].append(r)
        groups["all"].append(r)

    end_state_labels = {"페어웨이": "FAIRWAY", "러프": "ROUGH", "벙커": "SAND", "그린": "GREEN"}
    out = {}
    for key, shots in groups.items():
        n_total = len(shots)
        state_counts: dict[str, int] = defaultdict(int)
        for r in shots:
            label = end_state_labels.get(r.end_lie, "UNKNOWN_OTHER")
            state_counts[label] += 1
        distances = [r.end_distance_yd for r in shots if r.end_lie != "" and r.end_lie != "홀인"]
        out[key] = {
            "n_tee_shots": n_total,
            "end_state_counts": dict(state_counts),
            "end_state_percentages": {k: round(v / n_total * 100, 1) for k, v in state_counts.items()} if n_total else {},
            "avg_first_shot_end_distance_yd": (sum(distances) / len(distances)) if distances else None,
            "avg_first_shot_end_distance_denominator": len(distances),
        }
    return out


def section_e_approach_distance_profile(rows: list[TransitionRow]) -> dict:
    hole_groups = group_by_hole(rows)
    out = {}
    for band in DISTANCE_BANDS:
        band_out = {}
        for lie in QUALIFYING_LIES:
            shots = [r for r in rows if r.start_lie == lie and r.start_distance_yd is not None
                     and distance_band(r.start_distance_yd) == band]
            m = compute_lie_metrics(shots, hole_groups)
            band_out[lie] = {**asdict(m), "sample_flag": sample_size_flag(m.n)}
        out[band] = band_out
    return out


def section_f_green_entry(rows: list[TransitionRow], par_by_round_hole: dict) -> dict:
    hole_groups = group_by_hole(rows)
    entries = []
    no_entry_holes = []
    for (rnd, hole), hole_rows in hole_groups.items():
        entry = green_entry_shot(hole_rows)
        par = par_by_round_hole.get((rnd, hole))
        if entry is None:
            no_entry_holes.append({"round": rnd, "hole": hole, "par": par, "terminal_end_lie": hole_rows[-1].end_lie})
            continue
        entries.append({"round": rnd, "hole": hole, "par": par, "shot_no": entry.shot_no, "remaining_yd": entry.end_distance_yd})

    def _summarize(subset):
        n = len(subset)
        if n == 0:
            return {"holes_with_valid_green_entry": 0, "average_green_entry_shot_number": None,
                    "green_entry_by_shot_number": {"shot_1": 0, "shot_2": 0, "shot_3": 0, "shot_4_plus": 0},
                    "average_remaining_distance_at_green_entry": None}
        by_shot_no = {"shot_1": 0, "shot_2": 0, "shot_3": 0, "shot_4_plus": 0}
        for e in subset:
            key = f"shot_{e['shot_no']}" if e["shot_no"] <= 3 else "shot_4_plus"
            by_shot_no[key] += 1
        return {
            "holes_with_valid_green_entry": n,
            "average_green_entry_shot_number": sum(e["shot_no"] for e in subset) / n,
            "green_entry_by_shot_number": by_shot_no,
            "average_remaining_distance_at_green_entry": sum(e["remaining_yd"] for e in subset) / n,
        }

    out = {"overall": _summarize(entries), "no_valid_green_entry_holes": no_entry_holes}
    for par in (3, 4, 5):
        out[f"par_{par}"] = _summarize([e for e in entries if e["par"] == par])
    out["par_unknown"] = _summarize([e for e in entries if e["par"] not in (3, 4, 5)])
    return out


def section_g_green_finish(rows: list[TransitionRow]) -> dict:
    hole_groups = group_by_hole(rows)
    finishes = []
    terminal_failures = 0
    for (rnd, hole), hole_rows in hole_groups.items():
        entry = green_entry_shot(hole_rows)
        if entry is None:
            continue
        count = green_finish_shot_count(hole_rows, entry.shot_no)
        if count is None:
            terminal_failures += 1
            continue
        finishes.append(count)

    n = len(finishes)
    buckets = {"finish_1": 0, "finish_2": 0, "finish_3": 0, "finish_4_plus": 0}
    for c in finishes:
        key = f"finish_{c}" if c <= 3 else "finish_4_plus"
        buckets[key] += 1
    pct = {k: round(v / n * 100, 1) for k, v in buckets.items()} if n else {k: None for k in buckets}
    return {
        "n_holes_with_valid_green_entry_and_terminal_integrity": n,
        "observed_green_finish_shot_counts": buckets,
        "observed_green_finish_shot_percentages": pct,
        "average_observed_green_finish_shots": (sum(finishes) / n) if n else None,
        "terminal_integrity_failures_excluded": terminal_failures,
    }


def section_h_scoring_outcome_structure(rows: list[TransitionRow], par_by_round_hole: dict, official_score_by_round_hole: dict) -> dict:
    hole_groups = group_by_hole(rows)
    outcome_holes: dict[str, list] = defaultdict(list)
    excluded_no_official_or_par = 0
    for (rnd, hole), hole_rows in hole_groups.items():
        par = par_by_round_hole.get((rnd, hole))
        official = official_score_by_round_hole.get((rnd, hole))
        if par is None or official is None:
            excluded_no_official_or_par += 1
            continue
        cat = classify_score_to_par(official - par)
        entry = green_entry_shot(hole_rows)
        finish = green_finish_shot_count(hole_rows, entry.shot_no) if entry else None
        outcome_holes[cat].append({
            "round": rnd, "hole": hole, "green_entry_shot_no": entry.shot_no if entry else None,
            "green_entry_remaining_yd": entry.end_distance_yd if entry else None,
            "green_finish_shots": finish,
            "approach_start_lie": entry_approach_lie(hole_rows, entry) if entry else None,
            "approach_distance_band": (distance_band(entry_approach_distance(hole_rows, entry))
                                        if entry and entry_approach_distance(hole_rows, entry) is not None else None),
        })

    def _agg(cat):
        holes = outcome_holes.get(cat, [])
        n = len(holes)
        entry_shots = [h["green_entry_shot_no"] for h in holes if h["green_entry_shot_no"] is not None]
        entry_dists = [h["green_entry_remaining_yd"] for h in holes if h["green_entry_remaining_yd"] is not None]
        finishes = [h["green_finish_shots"] for h in holes if h["green_finish_shots"] is not None]
        lie_dist: dict[str, int] = defaultdict(int)
        band_dist: dict[str, int] = defaultdict(int)
        for h in holes:
            if h["approach_start_lie"]:
                lie_dist[h["approach_start_lie"]] += 1
            if h["approach_distance_band"]:
                band_dist[h["approach_distance_band"]] += 1
        return {
            "hole_count": n,
            "average_green_entry_shot_number": (sum(entry_shots) / len(entry_shots)) if entry_shots else None,
            "average_green_entry_remaining_distance_yd": (sum(entry_dists) / len(entry_dists)) if entry_dists else None,
            "average_observed_green_finish_shots": (sum(finishes) / len(finishes)) if finishes else None,
            "approach_start_lie_distribution_of_green_entry_shot": dict(lie_dist),
            "approach_distance_band_distribution_of_green_entry_shot": dict(band_dist),
        }

    return {
        "birdie_or_better": _agg("birdie_or_better"),
        "par": _agg("par"),
        "bogey": _agg("bogey"),
        "double_or_worse": _agg("double_or_worse"),
        "excluded_holes_missing_official_score_or_par": excluded_no_official_or_par,
        "note": "approach_start_lie/distance_band above describe the GREEN-ENTRY SHOT's own start state -- "
                "the shot that reached the green -- not every approach attempt on the hole. No causality is asserted.",
    }


def entry_approach_lie(hole_rows: list[TransitionRow], entry: TransitionRow) -> Optional[str]:
    return entry.start_lie or None


def entry_approach_distance(hole_rows: list[TransitionRow], entry: TransitionRow) -> Optional[float]:
    return entry.start_distance_yd


def section_i_best_worst_holes(rows: list[TransitionRow], par_by_round_hole: dict, official_score_by_round_hole: dict) -> dict:
    hole_groups = group_by_hole(rows)
    best, worst = [], []
    for (rnd, hole), hole_rows in sorted(hole_groups.items()):
        par = par_by_round_hole.get((rnd, hole))
        official = official_score_by_round_hole.get((rnd, hole))
        if par is None or official is None:
            continue
        to_par = official - par
        cat = classify_score_to_par(to_par)
        record = {
            "round": rnd, "hole": hole, "par": par, "official_hole_score": official, "score_to_par": to_par,
            "shot_count": len(hole_rows),
            "shot_sequence": [
                {"shot_no": r.shot_no, "start_lie": r.start_lie, "start_distance_yd": r.start_distance_yd,
                 "end_lie": r.end_lie, "end_distance_yd": r.end_distance_yd, "holed": r.holed}
                for r in hole_rows
            ],
        }
        if cat == "birdie_or_better":
            best.append(record)
        elif cat in ("bogey", "double_or_worse"):
            worst.append(record)
    return {"birdie_or_better_holes": best, "bogey_or_worse_holes": worst}


def section_j_cross_check(rows: list[TransitionRow]) -> dict:
    hole_groups = group_by_hole(rows)
    out = {}
    all_match = True
    for lie in QUALIFYING_LIES:
        shots = qualifying_shots_150_175(rows, lie)
        m = compute_lie_metrics(shots, hole_groups)
        ref = EXPERIMENT_01A_REFERENCE[lie]
        mismatches = []
        if m.n != ref["n"]:
            mismatches.append(f"n: got {m.n}, expected {ref['n']}")
        if ref["green_reach"] is not None and m.green_reach != ref["green_reach"]:
            mismatches.append(f"green_reach: got {m.green_reach}, expected {ref['green_reach']}")
        if ref["avg_remaining_yd"] is not None:
            got = round(m.avg_remaining_yd, 2) if m.avg_remaining_yd is not None else None
            if got != ref["avg_remaining_yd"]:
                mismatches.append(f"avg_remaining_yd: got {got}, expected {ref['avg_remaining_yd']}")
        if ref["avg_strokes_after"] is not None:
            got_after = round(m.avg_strokes_after, 2) if m.avg_strokes_after is not None else None
            if got_after != ref["avg_strokes_after"]:
                mismatches.append(f"avg_strokes_after: got {got_after}, expected {ref['avg_strokes_after']}")
        if mismatches:
            all_match = False
        out[lie] = {"computed": asdict(m), "reference": ref, "matches": not mismatches, "mismatches": mismatches}
    out["ALL_LIES_MATCH"] = all_match
    return out


def section_k_data_qa(rows: list[TransitionRow], par_by_round_hole: dict, official_score_by_round_hole: dict, section_b: dict) -> dict:
    hole_groups = group_by_hole(rows)
    dup_check: dict[tuple, int] = defaultdict(int)
    for r in rows:
        dup_check[(r.player_code, r.round_number, r.hole, r.shot_no)] += 1
    duplicate_shot_keys = sum(1 for c in dup_check.values() if c > 1)

    continuity_failures = sum(1 for hole_rows in hole_groups.values() if not shot_no_continuity_ok(hole_rows))
    terminal_failures = sum(1 for hole_rows in hole_groups.values() if hole_rows[-1].end_lie != "홀인")

    matches = 0
    mismatches = 0
    for (rnd, hole), hole_rows in hole_groups.items():
        official = official_score_by_round_hole.get((rnd, hole))
        if official is None:
            continue
        if official == len(hole_rows):
            matches += 1
        else:
            mismatches += 1

    return {
        "player_rows_loaded": len(rows),
        "holes_reconstructed": len(hole_groups),
        "duplicate_shot_keys": duplicate_shot_keys,
        "shot_no_continuity_failures": continuity_failures,
        "terminal_integrity_failures": terminal_failures,
        "official_hole_score_matches": matches,
        "official_hole_score_mismatches": mismatches,
        "unknown_start_lie_count": sum(1 for r in rows if r.start_lie == ""),
        "unknown_end_lie_count": sum(1 for r in rows if r.end_lie == ""),
        "zero_distance_unknown_count": sum(1 for r in rows if r.zero_distance_ambiguous),
    }


# ---------------------------------------------------------------
# Output writers.
# ---------------------------------------------------------------

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_csv(path: Path, flat_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "denominator", "sample_warning"])
        for r in flat_rows:
            w.writerow([r.get("metric"), r.get("value"), r.get("denominator", ""), r.get("sample_warning", "")])


def flatten_for_csv(sections: dict) -> list[dict]:
    flat = []
    a = sections["A_identity"]
    for k in ("player_code", "official_final_rank_display", "official_final_score_to_par",
              "official_total_strokes", "rounds_played", "holes_played", "total_shots"):
        flat.append({"metric": f"A.{k}", "value": a.get(k)})
    for rr in sections["B_round_by_round"]["rounds"]:
        flat.append({"metric": f"B.round_{rr['round']}.round_raw_strokes", "value": rr["round_raw_strokes"]})
        flat.append({"metric": f"B.round_{rr['round']}.to_par", "value": rr["to_par"]})
    for par in (3, 4, 5):
        c = sections["C_par_scoring"][f"par_{par}"]
        flat.append({"metric": f"C.par_{par}.holes", "value": c["holes"]})
        flat.append({"metric": f"C.par_{par}.score_to_par", "value": c["score_to_par"]})
    for band, lies in sections["E_approach_distance_profile"].items():
        for lie, m in lies.items():
            flat.append({"metric": f"E.{band}.{lie}.N", "value": m["n"], "sample_warning": m["sample_flag"]})
            flat.append({"metric": f"E.{band}.{lie}.green_reach_pct",
                          "value": round(m["green_reach_rate"] * 100, 1) if m["green_reach_rate"] is not None else None})
            flat.append({"metric": f"E.{band}.{lie}.avg_remaining_yd", "value": m["avg_remaining_yd"],
                          "denominator": m["avg_remaining_denominator"]})
            flat.append({"metric": f"E.{band}.{lie}.avg_strokes_after", "value": m["avg_strokes_after"],
                          "denominator": m["avg_strokes_after_denominator"]})
    g = sections["G_green_finish"]
    flat.append({"metric": "G.average_observed_green_finish_shots", "value": g["average_observed_green_finish_shots"],
                  "denominator": g["n_holes_with_valid_green_entry_and_terminal_integrity"]})
    for lie, j in sections["J_cross_check"].items():
        if lie == "ALL_LIES_MATCH":
            continue
        flat.append({"metric": f"J.{lie}.matches", "value": j["matches"]})
    k = sections["K_data_qa"]
    for key, val in k.items():
        flat.append({"metric": f"K.{key}", "value": val})
    return flat


# ---------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="2026090002")
    ap.add_argument("--sqlite", type=Path, default=None)
    ap.add_argument("--transitions-csv", type=Path, default=None)
    ap.add_argument("--official-score-source", type=Path, required=True)
    ap.add_argument("--final-round-tab", required=True)
    ap.add_argument("--player-name", default="김민선7")
    a = ap.parse_args()

    if bool(a.sqlite) == bool(a.transitions_csv):
        print("BLOCKED: supply exactly one of --sqlite or --transitions-csv.")
        raise SystemExit(1)

    print("[FILE LOCATIONS]")
    if a.sqlite:
        print("sqlite =", a.sqlite, "exists=", a.sqlite.is_file())
        if not a.sqlite.is_file():
            print("BLOCKED: sqlite file not found.")
            raise SystemExit(1)
        all_rows = load_rows_from_sqlite(a.sqlite, a.game)
    else:
        print("transitions_csv =", a.transitions_csv, "exists=", a.transitions_csv.is_file())
        if not a.transitions_csv.is_file():
            print("BLOCKED: transitions CSV not found.")
            raise SystemExit(1)
        all_rows = load_rows_from_csv(a.transitions_csv)
    print("official_score_source =", a.official_score_source, "exists=", a.official_score_source.is_file())
    if not a.official_score_source.is_file():
        print("BLOCKED: official score source HTML not found.")
        raise SystemExit(1)

    PLAYER_NAME_CONTEXT[0] = a.player_name
    html = a.official_score_source.read_text(encoding="utf-8")
    par_by_round_hole, official_score_by_round_hole, official_meta = load_official_evidence(html)
    final_rank_rows = parse_score_record_final_ranking(html, round_tab_id=a.final_round_tab)

    rows = [r for r in all_rows if r.player_name == a.player_name]
    print("total_transition_rows_loaded_all_players =", len(all_rows))
    print("player_rows_loaded =", len(rows))
    if not rows:
        print(f"BLOCKED: no shot_event rows found for player_name={a.player_name!r}.")
        raise SystemExit(1)

    sections = {}
    sections["A_identity"] = section_a_identity(rows, final_rank_rows, a.player_name)
    sections["B_round_by_round"] = section_b_round_by_round(rows, par_by_round_hole, official_score_by_round_hole)
    sections["C_par_scoring"] = section_c_par_scoring(rows, par_by_round_hole)
    sections["D_tee_shot_profile"] = section_d_tee_shot_profile(rows, par_by_round_hole)
    sections["E_approach_distance_profile"] = section_e_approach_distance_profile(rows)
    sections["F_green_entry"] = section_f_green_entry(rows, par_by_round_hole)
    sections["G_green_finish"] = section_g_green_finish(rows)
    sections["H_scoring_outcome_structure"] = section_h_scoring_outcome_structure(rows, par_by_round_hole, official_score_by_round_hole)
    sections["I_best_worst_holes"] = section_i_best_worst_holes(rows, par_by_round_hole, official_score_by_round_hole)
    sections["J_cross_check"] = section_j_cross_check(rows)
    sections["K_data_qa"] = section_k_data_qa(rows, par_by_round_hole, official_score_by_round_hole, sections["B_round_by_round"])
    sections["_meta"] = {"official_evidence_blocked_rounds": official_meta["blocked"]}

    print("\n[SECTION A -- IDENTITY]")
    for k, v in sections["A_identity"].items():
        print(f"{k} =", v)

    print("\n[SECTION B -- ROUND BY ROUND]")
    for rr in sections["B_round_by_round"]["rounds"]:
        print(rr)
    print("tournament_raw_total_strokes =", sections["B_round_by_round"]["tournament_raw_total_strokes"])
    print("tournament_to_par =", sections["B_round_by_round"]["tournament_to_par"])
    print("official_hole_score_mismatches =", sections["B_round_by_round"]["official_hole_score_mismatches"])

    print("\n[SECTION C -- PAR SCORING]")
    for k, v in sections["C_par_scoring"].items():
        print(f"{k} =", v)

    print("\n[SECTION D -- TEE SHOT PROFILE] (Observed Tee-Shot End State, NOT 'driving accuracy')")
    for k, v in sections["D_tee_shot_profile"].items():
        print(f"{k} =", v)

    print("\n[SECTION E -- APPROACH DISTANCE PROFILE]")
    for band, lies in sections["E_approach_distance_profile"].items():
        for lie, m in lies.items():
            print(f"{band} | {lie} | {m}")

    print("\n[SECTION F -- GREEN ENTRY]")
    for k, v in sections["F_green_entry"].items():
        print(f"{k} =", v)

    print("\n[SECTION G -- OBSERVED GREEN-FINISH SHOTS] (NOT 'Putts')")
    for k, v in sections["G_green_finish"].items():
        print(f"{k} =", v)

    print("\n[SECTION H -- SCORING OUTCOME STRUCTURE] (no causality asserted)")
    for k, v in sections["H_scoring_outcome_structure"].items():
        print(f"{k} =", v)

    print("\n[SECTION I -- BEST/WORST OBSERVED HOLES]")
    print("birdie_or_better_holes:")
    for h in sections["I_best_worst_holes"]["birdie_or_better_holes"]:
        print("  ", {k: v for k, v in h.items() if k != "shot_sequence"})
        for s in h["shot_sequence"]:
            print("     ", s)
    print("bogey_or_worse_holes:")
    for h in sections["I_best_worst_holes"]["bogey_or_worse_holes"]:
        print("  ", {k: v for k, v in h.items() if k != "shot_sequence"})
        for s in h["shot_sequence"]:
            print("     ", s)

    print("\n[SECTION J -- 150-175yd EXPERIMENT 01A CROSS-CHECK]")
    for lie in QUALIFYING_LIES:
        j = sections["J_cross_check"][lie]
        print(f"{lie}: matches={j['matches']}", j["mismatches"] if j["mismatches"] else "")
    if not sections["J_cross_check"]["ALL_LIES_MATCH"]:
        print("STOP: 150-175yd cross-check DISCREPANCY DETECTED -- see mismatches above. NOT silently reconciled.")

    print("\n[SECTION K -- DATA QA]")
    for k, v in sections["K_data_qa"].items():
        print(f"{k} =", v)
    if official_meta["blocked"]:
        print("official_evidence_blocked_rounds =", official_meta["blocked"])

    out_dir = Path(__file__).resolve().parents[1] / "reports" / "player_intelligence"
    json_path = out_dir / f"{a.game}_kim_minsun7_prototype01.json"
    csv_path = out_dir / f"{a.game}_kim_minsun7_prototype01.csv"
    write_json(json_path, sections)
    write_csv(csv_path, flatten_for_csv(sections))
    print("\n[SECTION L -- MACHINE-READABLE OUTPUT]")
    print("json =", json_path)
    print("csv =", csv_path)
    print("\nNOTE: descriptive observed data only. NOT Expected Strokes. NOT SG. NOT a player-quality ranking.")


if __name__ == "__main__":
    main()
