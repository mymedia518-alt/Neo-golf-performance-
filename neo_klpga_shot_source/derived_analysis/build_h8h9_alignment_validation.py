"""H8/H9 coordinate alignment validation -- NOT eyeballed. Uses the
course image's own pixel colors as ground truth: a "course mask" (green
turf vs white background) from the overview, and separately the actual
hole_cup/pin pixel from the known real-pin formula, cross-checked
against the green shape. Reuses the EXACT confirmed KLPGA transform
(x=(390-pp_y*2)*1.815, y=(pp_x*2)*1.815, rescaled 708x471->650x433 as
A,B,C below) -- no new transform, no manual nudging.
"""
from __future__ import annotations
import json, sqlite3, statistics
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
IMG_DIR = HERE.parent / "hole_images"
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
PAR_YDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
PIN_AUDIT = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())
PINS = {(e["round"], e["hole"]): e for e in PIN_AUDIT["per_round_hole_table"]}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}

A, B = -3.3326271186440724, 649.8622881355936
C = 3.337133757961783


def px_of(v_y): return A * v_y + B
def py_of(v_x): return C * v_x


def course_mask(img):
    """True where the pixel is course turf/water/sand (non-white,
    non-transparent background), used as ground truth for 'is this
    pixel actually on the hole' -- not an assumption, read from the
    image itself."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    mask = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, bch, a = px[x, y]
            is_white_bg = (r > 245 and g > 245 and bch > 245) or a < 10
            mask[y][x] = not is_white_bg
    return mask, w, h


def sample(mask, w, h, x, y, radius=6):
    """Fraction of a small neighborhood around (x,y) that is on-course."""
    x0, x1 = max(0, int(x) - radius), min(w, int(x) + radius + 1)
    y0, y1 = max(0, int(y) - radius), min(h, int(y) + radius + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    total = 0
    on = 0
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            total += 1
            if mask[yy][xx]:
                on += 1
    return on / total if total else 0.0


def water_mask(img):
    """Blue-ish pixels specifically (hazard water), separate from green turf."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    mask = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, bch, a = px[x, y]
            if a < 10:
                continue
            is_blue = bch > 150 and bch > r + 20 and bch > g - 10 and g > 100
            mask[y][x] = is_blue
    return mask, w, h


def validate_hole(hole):
    con = sqlite3.connect(DB)
    ov_img = Image.open(IMG_DIR / f"hole_{hole}.png")
    gr_img = Image.open(IMG_DIR / f"hole_{hole}_G.png")
    assert ov_img.size == (650, 433) and gr_img.size == (650, 433)
    ov_mask, ow, oh = course_mask(ov_img)
    ov_water, _, _ = water_mask(ov_img)
    gr_mask, gw, gh = course_mask(gr_img)

    rows = con.execute(
        "SELECT player_code, round, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND hole=? ORDER BY player_code, round, shot",
        (GAME, hole)).fetchall()

    checks = {}
    by_lie_overview = {}
    for state in ("1", "2", "6", "5", "7", "8"):
        pts = [(px_of(y), py_of(x)) for pc, rnd, s, st, x, y, gx, gy, d in rows if st == state and x is not None and y is not None]
        if not pts:
            continue
        in_bounds = [0 <= px < ow and 0 <= py < oh for px, py in pts]
        on_course = [sample(ov_mask, ow, oh, px, py) > 0.3 for px, py in pts if 0 <= px < ow and 0 <= py < oh]
        by_lie_overview[LIE_NAME[state]] = {
            "n": len(pts), "pct_in_image_bounds": round(sum(in_bounds) / len(pts), 3),
            "pct_on_course_pixels": round(sum(on_course) / len(on_course), 3) if on_course else None,
        }

    # PENALTY_AREA (state 5) should disproportionately land on water pixels specifically
    pen_pts = [(px_of(y), py_of(x)) for pc, rnd, s, st, x, y, gx, gy, d in rows if st == "5" and x is not None and y is not None]
    pen_on_water = [sample(ov_water, ow, oh, px, py) > 0.15 for px, py in pen_pts if 0 <= px < ow and 0 <= py < oh]
    checks["penalty_area_on_water_pct"] = round(sum(pen_on_water) / len(pen_on_water), 3) if pen_on_water else None
    checks["penalty_area_n"] = len(pen_pts)

    # GREEN-state shots should cluster inside the green-mask region of the GREEN DETAIL image
    green_pts_g = [(px_of(gy), py_of(gx)) for pc, rnd, s, st, x, y, gx, gy, d in rows if st == "3" and gx is not None and gy is not None]
    green_in_bounds = [0 <= px < gw and 0 <= py < gh for px, py in green_pts_g]
    green_on_course = [sample(gr_mask, gw, gh, px, py) > 0.3 for px, py in green_pts_g if 0 <= px < gw and 0 <= py < gh]
    checks["green_shots_n"] = len(green_pts_g)
    checks["green_shots_pct_in_image_bounds"] = round(sum(green_in_bounds) / len(green_pts_g), 3) if green_pts_g else None
    checks["green_shots_pct_on_course_pixels"] = round(sum(green_on_course) / len(green_on_course), 3) if green_on_course else None

    # real per-round pins (green-detail space) should fall near the green centroid of GREEN shots
    pin_checks = {}
    for rnd in (1, 2, 3, 4):
        pin = PINS.get((rnd, hole))
        if pin is None:
            pin_checks[rnd] = "NO PIN DATA"
            continue
        ppx, ppy = px_of(pin["pin_y"]), py_of(pin["pin_x"])
        in_b = 0 <= ppx < gw and 0 <= ppy < gh
        on_c = sample(gr_mask, gw, gh, ppx, ppy) > 0.3 if in_b else False
        pin_checks[rnd] = {"pin_px": round(ppx, 1), "pin_py": round(ppy, 1), "in_image_bounds": in_b, "on_course_pixels": bool(on_c)}
    checks["round_pins"] = pin_checks

    # monotonic approach: mean distance from tee-shot pixel to green-centroid pixel should
    # DECREASE shot-by-shot for genuine chains (structural sanity, not a hard requirement
    # since recoveries/penalties can move backward -- reported, not enforced as pass/fail)
    green_centroid = (statistics.mean(p[0] for p in green_pts_g), statistics.mean(p[1] for p in green_pts_g)) if green_pts_g else None

    # LOST_BALL / OB are EXPECTED to often land outside the drawn course
    # polygon (that is structurally what "lost ball"/"out of bounds"
    # means -- the illustration only draws the playing corridor). They
    # are reported but NOT required to pass the on-course check.
    EXPECTED_OFF_COURSE = {"LOST_BALL", "OB"}
    core_lie_checks = {k: v for k, v in by_lie_overview.items() if k not in EXPECTED_OFF_COURSE}
    overall_pass = (
        all(v["pct_on_course_pixels"] is None or v["pct_on_course_pixels"] >= 0.5 for v in core_lie_checks.values()) and
        (checks["green_shots_pct_on_course_pixels"] or 0) >= 0.5 and
        all(isinstance(v, dict) and v["on_course_pixels"] for v in pin_checks.values() if isinstance(v, dict))
    )
    for name in EXPECTED_OFF_COURSE:
        if name in by_lie_overview:
            by_lie_overview[name]["note"] = "expected to often land outside the drawn course polygon (lost ball / OB) -- not counted against overall_alignment"

    return {
        "hole": hole, "image_overview": f"hole_{hole}.png", "image_green": f"hole_{hole}_G.png",
        "image_size_confirmed": [650, 433], "transform": {"A": A, "B": B, "C": C,
            "formula": "px=A*raw_y+B, py=C*raw_x (overview); same applied to green_x/green_y for green-detail panel"},
        "by_lie_overview_checks": by_lie_overview,
        "penalty_area_water_check": {"n": checks["penalty_area_n"], "pct_landing_on_water_pixels": checks["penalty_area_on_water_pct"]},
        "green_shot_checks": {"n": checks["green_shots_n"], "pct_in_bounds": checks["green_shots_pct_in_image_bounds"],
                               "pct_on_course_pixels": checks["green_shots_pct_on_course_pixels"],
                               "green_centroid_px_py": green_centroid},
        "round_pin_checks": pin_checks,
        "overall_alignment": "PASS" if overall_pass else "FAIL",
    }


def main():
    for hole in (8, 9):
        result = validate_hole(hole)
        (HERE / f"H{hole}_coordinate_alignment_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
        print(f"=== Hole {hole}: {result['overall_alignment']} ===")
        print(" by_lie:", result["by_lie_overview_checks"])
        print(" penalty/water:", result["penalty_area_water_check"])
        print(" green shots:", result["green_shot_checks"])
        print(" pins:", result["round_pin_checks"])
        print()


if __name__ == "__main__":
    main()
