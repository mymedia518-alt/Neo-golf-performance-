"""NEO Damage Control Save Drilldown 02.

Observed-only experiment:
Par4 -> tee ends rough -> second shot misses green.
Trace the third shot and final result, and print every player case.

No Expected Strokes. No SG. No causal claim.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klpga.collectors.score_record import parse_score_record_hole_par
from klpga.expected_strokes.transitions import build_transition_dataset

ROUGH = "러프"
GREEN = "그린"
HOLED = "홀인"


def load_pars(path: Path):
    html = path.read_text(encoding="utf-8")
    out = {}
    for rnd, tab in enumerate(("round-one", "round-two", "round-three", "round-four"), 1):
        pars = parse_score_record_hole_par(html, round_tab_id=tab)
        if len(pars) != 18:
            raise SystemExit(f"BLOCKED: {tab} par count={len(pars)}")
        for hole, par in pars.items():
            out[(rnd, hole)] = par
    if len(out) != 72:
        raise SystemExit(f"BLOCKED: verified par count={len(out)}")
    return out


def outcome(rows):
    n = len(rows)
    pb = sum(x["to_par"] <= 0 for x in rows)
    bogey = sum(x["to_par"] == 1 for x in rows)
    dp = sum(x["to_par"] >= 2 for x in rows)
    return {
        "n": n,
        "par_or_better": {"count": pb, "rate": pb / n if n else None},
        "bogey": {"count": bogey, "rate": bogey / n if n else None},
        "double_or_worse": {"count": dp, "rate": dp / n if n else None},
    }


def band(d):
    if d is None:
        return "UNKNOWN"
    if d < 5:
        return "<5yd"
    if d < 10:
        return "5-10yd"
    if d < 20:
        return "10-20yd"
    if d < 30:
        return "20-30yd"
    return "30yd+"


def reconstruct(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r.player_code, r.round_number, r.hole)].append(r)

    out = []
    for (pc, rnd, hole), hs in grouped.items():
        hs.sort(key=lambda x: x.shot_no)
        if not hs or hs[0].par != 4 or hs[0].end_lie != ROUGH or hs[-1].end_lie != HOLED:
            continue

        second = next((x for x in hs if x.shot_no == 2), None)
        third = next((x for x in hs if x.shot_no == 3), None)
        if second is None or third is None or second.end_lie == GREEN:
            continue

        strokes = len(hs)
        out.append({
            "player_code": pc,
            "player_name": hs[0].player_name,
            "round": rnd,
            "hole": hole,
            "to_par": strokes - 4,
            "total_strokes": strokes,
            "second_start_distance_yd": second.start_distance_yd,
            "second_end_lie": second.end_lie or "UNKNOWN",
            "second_end_distance_yd": second.end_distance_yd,
            "third_start_lie": third.start_lie or "UNKNOWN",
            "third_start_distance_yd": third.start_distance_yd,
            "third_end_lie": third.end_lie or "UNKNOWN",
            "third_end_distance_yd": third.end_distance_yd,
            "third_reached_green": third.end_lie == GREEN,
            "third_holed": third.end_lie == HOLED,
            "shots_after_third": strokes - 3,
        })
    return out


def summarize(rows):
    by_start = {}
    for b in ("<5yd", "5-10yd", "10-20yd", "20-30yd", "30yd+", "UNKNOWN"):
        xs = [x for x in rows if band(x["third_start_distance_yd"]) == b]
        if not xs:
            continue
        green_or_hole = sum(x["third_reached_green"] or x["third_holed"] for x in xs)
        pb = sum(x["to_par"] <= 0 for x in xs)
        by_start[b] = {
            "n": len(xs),
            "third_shot_green_or_hole": green_or_hole,
            "third_shot_green_or_hole_rate": green_or_hole / len(xs),
            "par_or_better": pb,
            "par_or_better_rate": pb / len(xs),
        }

    by_lie = {}
    for lie in sorted({x["third_start_lie"] for x in rows}):
        xs = [x for x in rows if x["third_start_lie"] == lie]
        by_lie[lie] = outcome(xs)

    starts = [x["third_start_distance_yd"] for x in rows if x["third_start_distance_yd"] is not None]
    ends = [
        x["third_end_distance_yd"] for x in rows
        if x["third_end_distance_yd"] is not None and x["third_reached_green"]
    ]
    reached = [x for x in rows if x["third_reached_green"] or x["third_holed"]]

    return {
        "outcome": outcome(rows),
        "avg_third_shot_start_distance_yd": sum(starts) / len(starts) if starts else None,
        "third_shot_green_or_hole": {
            "count": len(reached),
            "rate": len(reached) / len(rows) if rows else None,
        },
        "avg_remaining_after_third_on_green_yd": sum(ends) / len(ends) if ends else None,
        "by_third_shot_start_distance": by_start,
        "by_third_shot_start_lie": by_lie,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", type=Path, required=True)
    ap.add_argument("--official-score-source", type=Path, required=True)
    ap.add_argument("--game", default="2026090002")
    ap.add_argument("--player", default="김민선7")
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()

    if not a.sqlite.is_file():
        raise SystemExit("BLOCKED: sqlite not found")
    if not a.official_score_source.is_file():
        raise SystemExit("BLOCKED: official score source not found")

    pars = load_pars(a.official_score_source)
    con = sqlite3.connect(f"file:{a.sqlite.resolve()}?mode=ro", uri=True)
    try:
        transitions = build_transition_dataset(con, a.game, par_by_round_hole=pars)
    finally:
        con.close()

    recs = reconstruct(transitions)
    player = [x for x in recs if x["player_name"] == a.player]

    if len(recs) != 905:
        raise SystemExit(f"BLOCKED: expected field sample 905, got {len(recs)}")
    if len(player) != 7:
        raise SystemExit(f"BLOCKED: expected {a.player} sample 7, got {len(player)}")

    result = {
        "experiment": "damage_control_save_drilldown_02",
        "game_code": a.game,
        "player": a.player,
        "methodology": {
            "observed_only": True,
            "expected_strokes": False,
            "strokes_gained": False,
            "population": "Par4 tee rough, second shot missed green",
            "causality_claimed": False,
        },
        "qa": {
            "transition_rows": len(transitions),
            "verified_par_round_holes": len(pars),
            "field_cases": len(recs),
            "player_cases": len(player),
        },
        "field": summarize(recs),
        "player_metrics": summarize(player),
        "player_case_trace": player,
    }

    txt = json.dumps(result, ensure_ascii=False, indent=2)
    print(txt)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
