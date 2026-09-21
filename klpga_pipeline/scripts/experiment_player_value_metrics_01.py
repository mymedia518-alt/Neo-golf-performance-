"""NEO Player Value Metrics Experiment 01.
Read-only descriptive experiment. No Expected Strokes, no SG, no ranking model.
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

FAIRWAY = "페어웨이"
ROUGH = "러프"
GREEN = "그린"
HOLED = "홀인"


def groups(rows):
    out = defaultdict(list)
    for r in rows:
        out[(r.player_code, r.round_number, r.hole)].append(r)
    for v in out.values():
        v.sort(key=lambda x: x.shot_no)
    return out


def hole_records(rows):
    rec = []
    for (pc, rnd, hole), hs in groups(rows).items():
        first = hs[0]
        par = first.par
        if par is None or hs[-1].end_lie != HOLED:
            continue
        strokes = len(hs)
        entry = next((s for s in hs if s.end_lie == GREEN), None)
        rec.append({
            "player_code": pc,
            "player_name": first.player_name,
            "round": rnd,
            "hole": hole,
            "par": par,
            "strokes": strokes,
            "to_par": strokes - par,
            "tee_end_lie": first.end_lie if first.shot_no == 1 else "",
            "green_entry_remaining_yd": entry.end_distance_yd if entry else None,
            "green_entry_shot_no": entry.shot_no if entry else None,
        })
    return rec


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def miss_cost(recs):
    p45 = [x for x in recs if x["par"] in (4, 5) and x["tee_end_lie"] in (FAIRWAY, ROUGH)]

    def one(lie):
        xs = [x["to_par"] for x in p45 if x["tee_end_lie"] == lie]
        return {"n": len(xs), "avg_hole_to_par": mean(xs)}

    fw, rg = one(FAIRWAY), one(ROUGH)
    delta = None
    if fw["avg_hole_to_par"] is not None and rg["avg_hole_to_par"] is not None:
        delta = rg["avg_hole_to_par"] - fw["avg_hole_to_par"]
    return {"fairway": fw, "rough": rg, "rough_minus_fairway_to_par": delta}


def _damage_bucket(xs):
    n = len(xs)

    def cnt(fn):
        return sum(1 for x in xs if fn(x["to_par"]))

    par_or_better = cnt(lambda z: z <= 0)
    bogey = cnt(lambda z: z == 1)
    double_plus = cnt(lambda z: z >= 2)
    return {
        "n": n,
        "par_or_better": {"count": par_or_better, "rate": par_or_better / n if n else None},
        "bogey": {"count": bogey, "rate": bogey / n if n else None},
        "double_or_worse": {"count": double_plus, "rate": double_plus / n if n else None},
    }


def damage_control(recs):
    xs = [x for x in recs if x["par"] in (4, 5) and x["tee_end_lie"] == ROUGH]
    return {
        "combined": _damage_bucket(xs),
        "par4": _damage_bucket([x for x in xs if x["par"] == 4]),
        "par5": _damage_bucket([x for x in xs if x["par"] == 5]),
    }


def band(d):
    if d is None:
        return None
    if d < 3:
        return "<3yd"
    if d < 6:
        return "3-6yd"
    if d < 10:
        return "6-10yd"
    if d < 15:
        return "10-15yd"
    return "15yd+"


def opportunity(recs):
    buckets = defaultdict(list)
    for x in recs:
        b = band(x["green_entry_remaining_yd"])
        if b:
            buckets[b].append(x)
    out = {}
    for b in ["<3yd", "3-6yd", "6-10yd", "10-15yd", "15yd+"]:
        xs = buckets.get(b, [])
        bird = sum(1 for x in xs if x["to_par"] <= -1)
        out[b] = {
            "n": len(xs),
            "birdie_or_better": bird,
            "conversion_rate": bird / len(xs) if xs else None,
        }
    return out


def opportunity_by_par_and_entry(recs):
    out = {}
    for par in (3, 4, 5):
        par_rows = [x for x in recs if x["par"] == par]
        par_out = {}
        for entry_no in sorted({x["green_entry_shot_no"] for x in par_rows if x["green_entry_shot_no"] is not None}):
            rows = [x for x in par_rows if x["green_entry_shot_no"] == entry_no]
            par_out[f"entry_shot_{entry_no}"] = opportunity(rows)
        out[f"par{par}"] = par_out
    return out


def metrics(recs):
    return {
        "miss_cost": miss_cost(recs),
        "damage_control": damage_control(recs),
        "opportunity_conversion": opportunity(recs),
        "opportunity_controlled": opportunity_by_par_and_entry(recs),
    }


def load_verified_pars(score_path, round_tabs):
    html = score_path.read_text(encoding="utf-8")
    par_by_round_hole = {}
    tabs = [x.strip() for x in round_tabs.split(",") if x.strip()]
    if len(tabs) != 4:
        raise SystemExit(f"BLOCKED: expected 4 round tabs, got {len(tabs)}")
    for rnd, tab in enumerate(tabs, start=1):
        try:
            pars = parse_score_record_hole_par(html, round_tab_id=tab)
        except ValueError as exc:
            raise SystemExit(f"BLOCKED: cannot parse par for {tab}: {exc}")
        if len(pars) != 18:
            raise SystemExit(f"BLOCKED: {tab} expected 18 pars, got {len(pars)}")
        for hole, par in pars.items():
            par_by_round_hole[(rnd, hole)] = par
    if len(par_by_round_hole) != 72:
        raise SystemExit(f"BLOCKED: expected 72 round-hole par values, got {len(par_by_round_hole)}")
    return par_by_round_hole


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", type=Path, required=True)
    ap.add_argument("--official-score-source", type=Path, required=True)
    ap.add_argument("--game", default="2026090002")
    ap.add_argument("--player", default="김민선7")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--round-tabs", default="round-one,round-two,round-three,round-four")
    a = ap.parse_args()

    if not a.sqlite.is_file():
        raise SystemExit("BLOCKED: sqlite not found")
    if not a.official_score_source.is_file():
        raise SystemExit("BLOCKED: official score source not found")

    par_by_round_hole = load_verified_pars(a.official_score_source, a.round_tabs)

    con = sqlite3.connect(f"file:{a.sqlite.resolve()}?mode=ro", uri=True)
    try:
        rows = build_transition_dataset(con, a.game, par_by_round_hole=par_by_round_hole)
    finally:
        con.close()

    recs = hole_records(rows)
    player = [x for x in recs if x["player_name"] == a.player]
    if not player:
        names = sorted({x["player_name"] for x in recs})
        raise SystemExit(f"BLOCKED: player not found after reconstruction; valid_holes={len(recs)}, players={len(names)}")

    result = {
        "experiment": "player_value_metrics_01",
        "game_code": a.game,
        "player": a.player,
        "methodology": {
            "observed_only": True,
            "expected_strokes": False,
            "strokes_gained": False,
            "miss_cost_definition": "Par4/5 rough tee-end avg hole-to-par minus fairway tee-end avg hole-to-par",
            "damage_control_definition": "Par4/5 holes whose tee shot ended rough; final hole outcome distribution",
            "opportunity_definition": "birdie-or-better rate by first-green-entry remaining-distance bucket",
            "controlled_checks": "damage split by Par4/Par5; opportunity split by par and green-entry shot number",
            "causality_claimed": False,
        },
        "qa": {
            "transition_rows": len(rows),
            "verified_par_round_holes": len(par_by_round_hole),
            "valid_terminal_holes": len(recs),
            "player_valid_holes": len(player),
        },
        "field": metrics(recs),
        "player_metrics": metrics(player),
    }

    txt = json.dumps(result, ensure_ascii=False, indent=2)
    print(txt)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
