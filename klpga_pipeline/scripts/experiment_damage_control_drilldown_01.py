"""NEO Damage Control Drilldown 01.

Read-only descriptive experiment.
Question: after a Par4 tee shot ends in rough, where does the field-vs-player
difference in final scoring emerge?

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
        if second is None:
            continue
        strokes = len(hs)
        to_par = strokes - 4
        out.append({
            "player_code": pc,
            "player_name": hs[0].player_name,
            "round": rnd,
            "hole": hole,
            "to_par": to_par,
            "second_start_distance_yd": second.start_distance_yd,
            "second_end_lie": second.end_lie or "UNKNOWN",
            "second_end_distance_yd": second.end_distance_yd,
            "second_reached_green": second.end_lie == GREEN,
        })
    return out


def dist_band(d):
    if d is None:
        return "UNKNOWN"
    if d < 125:
        return "<125"
    if d < 150:
        return "125-150"
    if d < 175:
        return "150-175"
    if d < 200:
        return "175-200"
    return "200+"


def outcome(rows):
    n = len(rows)
    parbetter = sum(x["to_par"] <= 0 for x in rows)
    bogey = sum(x["to_par"] == 1 for x in rows)
    doubleplus = sum(x["to_par"] >= 2 for x in rows)
    return {
        "n": n,
        "par_or_better": {"count": parbetter, "rate": parbetter / n if n else None},
        "bogey": {"count": bogey, "rate": bogey / n if n else None},
        "double_or_worse": {"count": doubleplus, "rate": doubleplus / n if n else None},
    }


def summarize(rows):
    reached = [x for x in rows if x["second_reached_green"]]
    missed = [x for x in rows if not x["second_reached_green"]]

    by_start_distance = {}
    for b in ("<125", "125-150", "150-175", "175-200", "200+", "UNKNOWN"):
        xs = [x for x in rows if dist_band(x["second_start_distance_yd"]) == b]
        if xs:
            green = sum(x["second_reached_green"] for x in xs)
            by_start_distance[b] = {
                "n": len(xs),
                "second_shot_green_reach": green,
                "green_reach_rate": green / len(xs),
                "outcome": outcome(xs),
            }

    by_miss_lie = {}
    for lie in sorted({x["second_end_lie"] for x in missed}):
        xs = [x for x in missed if x["second_end_lie"] == lie]
        by_miss_lie[lie] = outcome(xs)

    miss_remaining = [x["second_end_distance_yd"] for x in missed if x["second_end_distance_yd"] is not None]

    return {
        "all_par4_rough_tee": outcome(rows),
        "second_shot_green_reach": {
            "count": len(reached),
            "rate": len(reached) / len(rows) if rows else None,
            "outcome": outcome(reached),
        },
        "second_shot_missed_green": {
            "count": len(missed),
            "rate": len(missed) / len(rows) if rows else None,
            "avg_remaining_yd": sum(miss_remaining) / len(miss_remaining) if miss_remaining else None,
            "outcome": outcome(missed),
            "end_lie_breakdown": by_miss_lie,
        },
        "by_second_shot_start_distance": by_start_distance,
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
    if len(recs) != 1972:
        raise SystemExit(f"BLOCKED: expected field Par4 rough sample 1972, got {len(recs)}")
    if len(player) != 20:
        raise SystemExit(f"BLOCKED: expected {a.player} Par4 rough sample 20, got {len(player)}")

    result = {
        "experiment": "damage_control_drilldown_01",
        "game_code": a.game,
        "player": a.player,
        "methodology": {
            "observed_only": True,
            "expected_strokes": False,
            "strokes_gained": False,
            "population": "Par4 holes where tee shot ended rough",
            "question": "Where does the field-vs-player scoring difference emerge after the miss?",
            "causality_claimed": False,
        },
        "qa": {
            "transition_rows": len(transitions),
            "verified_par_round_holes": len(pars),
            "field_par4_rough_holes": len(recs),
            "player_par4_rough_holes": len(player),
        },
        "field": summarize(recs),
        "player_metrics": summarize(player),
    }

    txt = json.dumps(result, ensure_ascii=False, indent=2)
    print(txt)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
