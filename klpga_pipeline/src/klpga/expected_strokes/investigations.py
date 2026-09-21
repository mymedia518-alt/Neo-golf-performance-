"""NEO Expected Strokes -- Phase 1 red-team investigations (2026-09-21).

Deep-dive diagnostics for three real findings flagged against the real
2026090002 transition dataset: blank ("") lie shots, BUNKER ("벙커")
lie shots, and the 17 zero-distance/non-홀인 cases. Also produces the
MODEL-ELIGIBILITY classification (non-overlapping, no double counting).

Pure functions over an already-built list[TransitionRow] (see
klpga.expected_strokes.transitions.build_transition_dataset) -- no
database access, no network calls, no writes. Never asserts a single
meaning for an ambiguous case; reports structured evidence only, per
explicit instruction not to infer without evidence.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from klpga.expected_strokes.transitions import TransitionRow, distance_stats

DISTANCE_BUCKETS = [
    ("0-5", 0.0, 5.0),
    (">5-20", 5.0, 20.0),
    (">20-50", 20.0, 50.0),
    (">50-100", 50.0, 100.0),
    (">100-200", 100.0, 200.0),
    (">200", 200.0, None),
]


def _bucket_label(distance: Optional[float]) -> str:
    if distance is None:
        return "unknown"
    for label, lo, hi in DISTANCE_BUCKETS:
        if hi is None:
            if distance > lo:
                return label
        elif lo == 0.0:
            if lo <= distance <= hi:
                return label
        elif lo < distance <= hi:
            return label
    return "unknown"


def _group_by_hole(rows: list[TransitionRow]) -> dict[tuple[str, int, int], list[TransitionRow]]:
    """Requires rows already ordered by (player_code,round_number,hole,shot_no)
    -- build_transition_dataset's own query guarantees this."""
    groups: dict[tuple[str, int, int], list[TransitionRow]] = defaultdict(list)
    for row in rows:
        groups[(row.player_code, row.round_number, row.hole)].append(row)
    return groups


def _prev_next_lie_map(rows: list[TransitionRow]) -> dict[int, dict]:
    """Maps id(row) -> {"previous_end_lie": ..., "next_start_lie": ...,
    "is_final_shot": bool} using real hole-grouping, never assumed
    from row order alone across hole boundaries."""
    context: dict[int, dict] = {}
    for hole_rows in _group_by_hole(rows).values():
        for i, row in enumerate(hole_rows):
            prev_lie = hole_rows[i - 1].end_lie if i > 0 else None
            is_final = i == len(hole_rows) - 1
            next_lie = hole_rows[i + 1].start_lie if not is_final else None
            context[id(row)] = {
                "previous_end_lie": prev_lie,
                "next_start_lie": next_lie,
                "is_final_shot": is_final,
            }
    return context


# ---------------------------------------------------------------
# Blank-lie ("") investigation.
# ---------------------------------------------------------------

def blank_lie_investigation(rows: list[TransitionRow]) -> dict:
    ctx = _prev_next_lie_map(rows)
    start_blank = [r for r in rows if (r.start_lie or "") == ""]
    end_blank = [r for r in rows if (r.end_lie or "") == ""]

    def _by_shot_no(subset):
        d: dict[int, int] = defaultdict(int)
        for r in subset:
            d[r.shot_no] += 1
        return dict(sorted(d.items()))

    def _by_par(subset):
        d: dict[str, int] = defaultdict(int)
        for r in subset:
            d["unknown" if r.par is None else f"par_{r.par}"] += 1
        return dict(sorted(d.items()))

    def _by_prev_lie(subset):
        d: dict[str, int] = defaultdict(int)
        for r in subset:
            prev = ctx[id(r)]["previous_end_lie"]
            d["NONE_first_shot" if prev is None else (prev or "BLANK")] += 1
        return dict(sorted(d.items()))

    def _by_next_lie(subset):
        d: dict[str, int] = defaultdict(int)
        for r in subset:
            info = ctx[id(r)]
            if info["is_final_shot"]:
                d["NONE_final_shot"] += 1
            else:
                d[(info["next_start_lie"] or "BLANK")] += 1
        return dict(sorted(d.items()))

    def _by_distance_bucket(subset, distance_attr):
        d: dict[str, int] = defaultdict(int)
        for r in subset:
            d[_bucket_label(getattr(r, distance_attr))] += 1
        return dict(sorted(d.items()))

    def _top_examples(subset, distance_attr, limit=30):
        with_dist = [r for r in subset if getattr(r, distance_attr) is not None]
        with_dist.sort(key=lambda r: getattr(r, distance_attr), reverse=True)
        out = []
        for r in with_dist[:limit]:
            info = ctx[id(r)]
            out.append({
                "player_code": r.player_code, "player_name": r.player_name,
                "round": r.round_number, "hole": r.hole, "shot_no": r.shot_no,
                "start_distance_yd": r.start_distance_yd, "start_lie": r.start_lie,
                "shot_distance_yd": None, "end_distance_yd": r.end_distance_yd, "end_lie": r.end_lie,
                "previous_end_lie": info["previous_end_lie"], "next_start_lie": info["next_start_lie"],
                "is_final_shot": info["is_final_shot"],
            })
        return out

    return {
        "start_blank_count": len(start_blank),
        "end_blank_count": len(end_blank),
        "start_blank_by_shot_no": _by_shot_no(start_blank),
        "end_blank_by_shot_no": _by_shot_no(end_blank),
        "start_blank_by_par": _by_par(start_blank),
        "end_blank_by_par": _by_par(end_blank),
        "start_blank_by_previous_lie": _by_prev_lie(start_blank),
        "end_blank_by_previous_lie": _by_prev_lie(end_blank),
        "start_blank_by_next_lie": _by_next_lie(start_blank),
        "end_blank_by_next_lie": _by_next_lie(end_blank),
        "start_blank_distance_buckets": _by_distance_bucket(start_blank, "start_distance_yd"),
        "end_blank_distance_buckets": _by_distance_bucket(end_blank, "end_distance_yd"),
        "start_blank_top30_longest": _top_examples(start_blank, "start_distance_yd"),
        "end_blank_top30_longest": _top_examples(end_blank, "end_distance_yd"),
    }


# ---------------------------------------------------------------
# BUNKER ("벙커") investigation.
# ---------------------------------------------------------------

def bunker_investigation(rows: list[TransitionRow]) -> dict:
    ctx = _prev_next_lie_map(rows)
    start_bunker = [r for r in rows if r.start_lie == "벙커"]

    by_bucket: dict[str, int] = defaultdict(int)
    by_par: dict[str, int] = defaultdict(int)
    by_shot_no: dict[int, int] = defaultdict(int)
    end_lie_dist: dict[str, int] = defaultdict(int)
    for r in start_bunker:
        by_bucket[_bucket_label(r.start_distance_yd)] += 1
        by_par["unknown" if r.par is None else f"par_{r.par}"] += 1
        by_shot_no[r.shot_no] += 1
        end_lie_dist[r.end_lie or "BLANK"] += 1

    examples = []
    for r in sorted(start_bunker, key=lambda r: r.start_distance_yd or 0.0, reverse=True):
        info = ctx[id(r)]
        examples.append({
            "player_code": r.player_code, "player_name": r.player_name,
            "round": r.round_number, "hole": r.hole, "shot_no": r.shot_no, "par": r.par,
            "start_distance_yd": r.start_distance_yd, "end_distance_yd": r.end_distance_yd,
            "end_lie": r.end_lie, "previous_end_lie": info["previous_end_lie"],
        })

    return {
        "start_bunker_shots": len(start_bunker),
        "distance_stats": distance_stats([r.start_distance_yd for r in start_bunker if r.start_distance_yd is not None]),
        "by_distance_bucket": dict(sorted(by_bucket.items())),
        "by_par": dict(sorted(by_par.items())),
        "by_shot_no": dict(sorted(by_shot_no.items())),
        "end_lie_distribution": dict(sorted(end_lie_dist.items())),
        "examples": examples,
    }


# ---------------------------------------------------------------
# Zero-distance / non-홀인 (the 17) full detail.
# ---------------------------------------------------------------

def zero_distance_ambiguous_detail(rows: list[TransitionRow]) -> list[dict]:
    ctx = _prev_next_lie_map(rows)
    out = []
    for r in rows:
        if not r.zero_distance_ambiguous:
            continue
        info = ctx[id(r)]
        out.append({
            "player_code": r.player_code, "player_name": r.player_name,
            "round": r.round_number, "hole": r.hole, "shot_no": r.shot_no,
            "start_lie": r.start_lie, "start_distance_yd": r.start_distance_yd,
            "end_lie": r.end_lie, "end_distance_yd": r.end_distance_yd,
            "next_start_lie": info["next_start_lie"], "is_final_shot": info["is_final_shot"],
        })
    return out


# ---------------------------------------------------------------
# MODEL-ELIGIBILITY classification -- no double counting.
# ---------------------------------------------------------------

def model_eligibility_summary(rows: list[TransitionRow]) -> dict:
    """Each row gets flags in {B,C,D,E} as applicable:
      B: first-shot start-distance unresolved (shot_no==1)
      C: blank-lie unresolved (start_lie=="" or end_lie=="")
      D: zero-distance ambiguous (row.zero_distance_ambiguous)
      E: bunker semantic review (start_lie=="벙커" or end_lie=="벙커")
    A row with zero flags -> A (fully usable). Exactly one flag -> that
    letter. 2+ flags -> F (overlap), with the exact combination
    recorded rather than lost. Sums to TOTAL_SHOTS exactly once each."""
    counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    overlap_combinations: dict[str, int] = defaultdict(int)
    for r in rows:
        flags = []
        if r.shot_no == 1:
            flags.append("B")
        if (r.start_lie or "") == "" or (r.end_lie or "") == "":
            flags.append("C")
        if r.zero_distance_ambiguous:
            flags.append("D")
        if r.start_lie == "벙커" or r.end_lie == "벙커":
            flags.append("E")
        if not flags:
            counts["A"] += 1
        elif len(flags) == 1:
            counts[flags[0]] += 1
        else:
            counts["F"] += 1
            overlap_combinations["+".join(flags)] += 1
    return {
        "total_shots": len(rows),
        "A_fully_usable_transition": counts["A"],
        "B_first_shot_start_distance_unresolved": counts["B"],
        "C_blank_lie_unresolved": counts["C"],
        "D_zero_distance_ambiguous": counts["D"],
        "E_bunker_semantic_review": counts["E"],
        "F_overlap": counts["F"],
        "F_overlap_combinations": dict(sorted(overlap_combinations.items())),
        "sum_check": sum(counts.values()),
    }
