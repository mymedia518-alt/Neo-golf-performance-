"""Build all Artifact JS data blocks for Hole 1, mirroring the Hole 12
Artifact's data shape exactly (same procedure) but computed entirely
fresh from Hole 1's own real shots -- no numbers copied from Hole 12.
"""
from __future__ import annotations
import json, math, sqlite3, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
HOLE = 1
PAR = 4
HOLE_YARDAGE = 402.0
A, B = -3.3326271186440724, 649.8622881355936
C = 3.337133757961783
PLAYERS_OF_INTEREST = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}


def px_of(v_y): return A * v_y + B
def py_of(v_x): return C * v_x


def main():
    con = sqlite3.connect(DB)
    players_meta = json.loads((HERE / "players_RAW_READONLY.json").read_text())["players"]
    rows = con.execute(
        "SELECT player_code, round, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND hole=? ORDER BY player_code, round, shot",
        (GAME, HOLE)).fetchall()
    by_pr = defaultdict(list)
    for pc, rnd, shot, state, x, y, gx, gy, dist in rows:
        by_pr[(pc, rnd)].append({"shot": shot, "state": state, "x": x, "y": y, "green_x": gx, "green_y": gy, "distance": dist})

    tee_pts, hole_pts = [], []
    for key, shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        if ss and ss[0]["x"] is not None:
            tee_pts.append((ss[0]["x"], ss[0]["y"]))
        for s in ss:
            if s["state"] == "10" and s["x"] is not None:
                hole_pts.append((s["x"], s["y"])); break
    tee = (statistics.mean(p[0] for p in tee_pts), statistics.mean(p[1] for p in tee_pts))
    green = (statistics.mean(p[0] for p in hole_pts), statistics.mean(p[1] for p in hole_pts))

    def project(pt):
        vx, vy = green[0] - tee[0], green[1] - tee[1]
        L2 = vx * vx + vy * vy
        px_, py_ = pt[0] - tee[0], pt[1] - tee[1]
        frac = (px_ * vx + py_ * vy) / L2
        cross = px_ * vy - py_ * vx
        lateral = cross / math.sqrt(L2)
        return frac, lateral

    # round pins (HOLED convergence)
    by_round_pin = defaultdict(list)
    for (pc, rnd), shots in by_pr.items():
        for s in shots:
            if s["state"] == "10" and s["green_x"] is not None:
                by_round_pin[rnd].append((s["green_x"], s["green_y"]))
    pins = {}
    for rnd, pts in sorted(by_round_pin.items()):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        pins[rnd] = {"pin_x": statistics.mean(xs), "pin_y": statistics.mean(ys)}

    field_shots = []
    tmp = []
    for (pc, rnd), shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        if not ss or ss[0]["x"] is None:
            continue
        s1 = ss[0]
        frac, lat = project((s1["x"], s1["y"]))
        field_shots.append({"player_code": pc, "round": rnd, "px": px_of(s1["y"]), "py": py_of(s1["x"]), "state": s1["state"]})
        tmp.append((pc, rnd, ss, frac, lat))

    fracs = sorted(t[3] for t in tmp)
    laterals = sorted(t[4] for t in tmp)
    f1, f2 = fracs[len(fracs) // 3], fracs[(2 * len(fracs)) // 3]
    l1, l2 = laterals[len(laterals) // 3], laterals[(2 * len(laterals)) // 3]

    def lon_bucket(f): return "SHORT" if f <= f1 else ("MID" if f <= f2 else "LONG")
    def lat_bucket(l): return "LAT1" if l <= l1 else ("LAT2" if l <= l2 else "LAT3")

    # zone boundary lines in overview PIXEL space (for the SVG), analogous
    # to Hole 12's zone_lines -- two longitudinal cut-lines + two lateral cut-lines.
    def pt_at(frac, lateral):
        vx, vy = green[0] - tee[0], green[1] - tee[1]
        L = math.hypot(vx, vy)
        ux, uy = vx / L, vy / L
        nx, ny = -uy, ux
        x = tee[0] + frac * vx + lateral * nx
        y = tee[1] + frac * vy + lateral * ny
        return (px_of(y), py_of(x))

    long_lines = [[pt_at(f1, laterals[0] - 20), pt_at(f1, laterals[-1] + 20)],
                  [pt_at(f2, laterals[0] - 20), pt_at(f2, laterals[-1] + 20)]]
    lat_lines = [[pt_at(fracs[0] - 0.05, l1), pt_at(fracs[-1] + 0.05, l1)],
                 [pt_at(fracs[0] - 0.05, l2), pt_at(fracs[-1] + 0.05, l2)]]

    zone_centers = {}
    for lb in ("SHORT", "MID", "LONG"):
        for lt in ("LAT1", "LAT2", "LAT3"):
            f_mid = {"SHORT": (fracs[0] + f1) / 2, "MID": (f1 + f2) / 2, "LONG": (f2 + fracs[-1]) / 2}[lb]
            l_mid = {"LAT1": (laterals[0] + l1) / 2, "LAT2": (l1 + l2) / 2, "LAT3": (l2 + laterals[-1]) / 2}[lt]
            zone_centers[f"{lb}-{lt}"] = list(pt_at(f_mid, l_mid))

    # Real distance-calibrated zone stats, chain detail, pin-centered points
    reliable = sorted(HOLE_YARDAGE - ss[0]["distance"] for _, _, ss, _, _ in tmp if ss[0]["state"] not in ("4", "5", "7", "8"))
    n = len(reliable)
    d1, d2 = reliable[n // 3], reliable[(2 * n) // 3]

    def dist_band(land):
        if land <= d1: return f"{int(round(reliable[0]))}-{int(round(d1))}yd"
        if land <= d2: return f"{int(round(d1))}-{int(round(d2))}yd"
        return f"{int(round(d2))}-{int(round(reliable[-1]))}yd"

    detail_rows = []
    chains_pc = defaultdict(lambda: defaultdict(list))
    pin_centered_pts = []
    approach_map = defaultdict(list)
    for pc, rnd, ss, frac, lat in tmp:
        s1 = ss[0]
        unreliable = s1["state"] in ("4", "5", "7", "8")
        landing = HOLE_YARDAGE - s1["distance"]
        approach_dist = s1["distance"]
        strokes = len(ss)
        stp = strokes - PAR
        gir_shot = None
        for s in ss:
            if s["state"] == "3": gir_shot = s["shot"]; break
        gir = gir_shot is not None and gir_shot <= PAR - 2
        shot2 = ss[1] if len(ss) >= 2 else None
        approach_lie = LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}") if shot2 else None
        zone = f"{dist_band(landing)} x {lat_bucket(lat)}"
        if stp <= -1: bucket = "Birdie+"
        elif stp == 0: bucket = "Par"
        elif stp == 1: bucket = "Bogey"
        else: bucket = "Double+"
        detail_rows.append({
            "pc": pc, "nm": players_meta.get(pc, {}).get("player_name", pc), "rnd": rnd,
            "px": round(px_of(s1["y"]), 1), "py": round(py_of(s1["x"]), 1),
            "land": round(landing, 1), "app": round(approach_dist, 1),
            "tlie": LIE_NAME.get(s1["state"], f"UNKNOWN_{s1['state']}"), "alie": approach_lie,
            "gir": gir, "strokes": strokes, "stp": stp, "zone": zone, "unreliable": unreliable,
        })
        for s in ss:
            chains_pc[pc][rnd].append({
                "shot": s["shot"], "state": s["state"],
                "gpx": px_of(s["green_y"]) if s["green_y"] is not None else None,
                "gpy": py_of(s["green_x"]) if s["green_x"] is not None else None,
                "dist": s["distance"],
            })
        if shot2 is not None and shot2["green_x"] is not None and rnd in pins:
            pin = pins[rnd]
            dx = shot2["green_x"] - pin["pin_x"]; dy = shot2["green_y"] - pin["pin_y"]
            pin_centered_pts.append({"pc": pc, "r": rnd, "dx": round(dx, 1), "dy": round(dy, 1), "b": bucket})
            approach_map[rnd].append({"pc": pc, "nm": players_meta.get(pc, {}).get("player_name", pc),
                                       "sd": round(approach_dist, 1), "ex": round(px_of(shot2["green_y"]), 1),
                                       "ey": round(py_of(shot2["green_x"]), 1), "px": round(px_of(pin["pin_y"]), 1),
                                       "py": round(py_of(pin["pin_x"]), 1), "lie": approach_lie, "b": bucket})

    round_pins_px = {rnd: {"gx": p["pin_x"], "gy": p["pin_y"], "px": px_of(p["pin_y"]), "py": py_of(p["pin_x"])} for rnd, p in pins.items()}

    out_DATA = {
        "tee": {"px": px_of(tee[1]), "py": py_of(tee[0])},
        "green": {"px": px_of(green[1]), "py": py_of(green[0]), "n": len(hole_pts)},
        "image_size": [650, 433], "field_shots": field_shots,
        "zone_lines": {"long_lines": long_lines, "lat_lines": lat_lines, "f1": f1, "f2": f2, "l1": l1, "l2": l2},
        "zone_centers": zone_centers,
    }
    out_DATA2 = {"round_pins_px": round_pins_px, "player_chains": {pc: {"label": PLAYERS_OF_INTEREST[pc], "rounds": chains_pc.get(pc, {})} for pc in PLAYERS_OF_INTEREST}}
    out_DATA3 = detail_rows
    out_DATA5 = {"approach_map": approach_map, "pin_centered_points": pin_centered_pts}

    adir = HERE / "artifact_data"
    (adir / "hole1_DATA.json").write_text(json.dumps(out_DATA, ensure_ascii=False, separators=(",", ":"), default=str))
    (adir / "hole1_DATA2.json").write_text(json.dumps(out_DATA2, ensure_ascii=False, separators=(",", ":"), default=str))
    (adir / "hole1_DATA3.json").write_text(json.dumps(out_DATA3, ensure_ascii=False, separators=(",", ":"), default=str))
    (adir / "hole1_DATA5.json").write_text(json.dumps(out_DATA5, ensure_ascii=False, separators=(",", ":"), default=str))
    print("wrote hole1_DATA{,2,3,5}.json")
    print("tee", out_DATA["tee"], "green", out_DATA["green"])
    print("thresholds f1,f2,l1,l2:", f1, f2, l1, l2)


if __name__ == "__main__":
    main()
