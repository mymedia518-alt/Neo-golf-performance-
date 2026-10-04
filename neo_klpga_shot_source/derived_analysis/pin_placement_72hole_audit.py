"""PIN PLACEMENT 72-hole completeness audit (R1-4 x H1-18 = 72).

Question asked: has official KLPGA pin-position data already been
collected for every (round, hole)? Answer: yes, implicitly, inside the
already-collected Shot Tracker RAW -- every real player's HOLED
(state_code "10") shot for a given (round, hole) carries the exact same
(green_x, green_y). Since the ball being in the hole IS the pin, this
needs no transform or assumption, unlike baseHoleInfo's bi_gx/bi_gy
(which requires the site's own *2/*1.815 JS transform to interpret and
is used only as an independent cross-check, not the primary source).

VERIFIED = at least one real player HOLED that (round,hole) AND every
real player's (green_x,green_y) at HOLED agrees exactly (pstdev == 0).
SOURCE_GAP = no real player HOLED that (round,hole) in the RAW at all.
INCONSISTENT = real players disagree on the HOLED position (would mean
a data/collection bug -- never silently accepted).
"""
from __future__ import annotations
import json, sqlite3, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
ROUNDS = [1, 2, 3, 4]
HOLES = list(range(1, 19))


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT round, hole, green_x, green_y FROM klpga_player_shot "
        "WHERE game_code=? AND state_code='10'", (GAME,),
    ).fetchall()
    by_rh = defaultdict(list)
    for rnd, hole, gx, gy in rows:
        if gx is not None and gy is not None:
            by_rh[(rnd, hole)].append((gx, gy))

    table = []
    per_round_counts = defaultdict(lambda: {"EXPECTED": 0, "COLLECTED": 0, "VERIFIED": 0, "SOURCE_GAP": 0, "INCONSISTENT": 0})
    pins = {}
    for rnd in ROUNDS:
        for hole in HOLES:
            pts = by_rh.get((rnd, hole), [])
            per_round_counts[rnd]["EXPECTED"] += 1
            entry = {"round": rnd, "hole": hole, "n": len(pts)}
            if not pts:
                entry["status"] = "SOURCE_GAP"
                per_round_counts[rnd]["SOURCE_GAP"] += 1
            else:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                sx, sy = statistics.pstdev(xs), statistics.pstdev(ys)
                per_round_counts[rnd]["COLLECTED"] += 1
                if sx == 0.0 and sy == 0.0:
                    entry["status"] = "VERIFIED"
                    entry["pin_x"], entry["pin_y"] = xs[0], ys[0]
                    pins[(rnd, hole)] = (xs[0], ys[0])
                    per_round_counts[rnd]["VERIFIED"] += 1
                else:
                    entry["status"] = "INCONSISTENT"
                    entry["stdev_x"], entry["stdev_y"] = sx, sy
                    per_round_counts[rnd]["INCONSISTENT"] += 1
            table.append(entry)

    total = {
        "EXPECTED": sum(v["EXPECTED"] for v in per_round_counts.values()),
        "COLLECTED": sum(v["COLLECTED"] for v in per_round_counts.values()),
        "VERIFIED": sum(v["VERIFIED"] for v in per_round_counts.values()),
        "SOURCE_GAP": sum(v["SOURCE_GAP"] for v in per_round_counts.values()),
        "INCONSISTENT": sum(v["INCONSISTENT"] for v in per_round_counts.values()),
    }
    verdict = "PASS" if total["VERIFIED"] == 72 and total["SOURCE_GAP"] == 0 and total["INCONSISTENT"] == 0 else (
        "PASS WITH SOURCE GAPS" if total["INCONSISTENT"] == 0 and total["VERIFIED"] + total["SOURCE_GAP"] == 72 and total["SOURCE_GAP"] > 0 else "FAIL")

    out = {
        "game_code": GAME,
        "method": "every real HOLED shot's (green_x,green_y) for a given (round,hole) must agree exactly (pstdev==0); the shared value is the real pin",
        "per_round": {str(r): v for r, v in per_round_counts.items()},
        "total": total,
        "verdict_PIN_DATA_STATUS": verdict,
        "pins": {f"R{r}H{h}": {"pin_x": p[0], "pin_y": p[1]} for (r, h), p in sorted(pins.items())},
        "per_round_hole_table": table,
    }
    (HERE / "pin_placement_72hole_audit.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'ROUND':<8}{'EXPECTED':<10}{'COLLECTED':<11}{'VERIFIED':<10}{'SOURCE_GAP':<12}{'INCONSISTENT':<13}")
    for r in ROUNDS:
        v = per_round_counts[r]
        print(f"R{r:<7}{v['EXPECTED']:<10}{v['COLLECTED']:<11}{v['VERIFIED']:<10}{v['SOURCE_GAP']:<12}{v['INCONSISTENT']:<13}")
    print(f"{'TOTAL':<8}{total['EXPECTED']:<10}{total['COLLECTED']:<11}{total['VERIFIED']:<10}{total['SOURCE_GAP']:<12}{total['INCONSISTENT']:<13}")
    print(f"\nPIN DATA STATUS: {verdict}")


if __name__ == "__main__":
    main()
