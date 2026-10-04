"""Build per-round real pin pixel positions + 3-player full shot chains
(in the green-closeup pixel frame) for the Hole 12 Artifact's ROUND
selector panel.

Pixel transform: empirically fit by least squares against the ALREADY
PUBLISHED overview-frame pixel data (hole12_full.json's field_shots,
whose px/py were generated from the real site JS transform
"x=(390-pp_y*2)*1.815, y=(pp_x*2)*1.815" scaled to the real 650x433
fetched image). Fit here (max residual ~2e-13, i.e. an exact match):
  px = A*v_y + B   (A=-3.3326271186440724, B=649.8622881355936)
  py = C*v_x       (C=3.337133757961783)

This SAME transform is re-applied to the green-closeup frame's
pp_greenx/pp_greeny (DB columns green_x/green_y), under the documented
assumption that both the overview and green-closeup panels share the
same site-code constants (390/2/1.815) and the same 650x433 image
dimensions (confirmed for both hole_12.png and hole_12_G.png) -- this
reuse is flagged explicitly in the Artifact UI as NOT independently
reverified for the green-closeup panel specifically (no separate
green-panel viewBox has been confirmed from the site's own JS).

Shots far from the green (chiefly the tee shot) map far outside the
650x433 crop under this transform -- expected, since the green-closeup
view only has a field of view near the pin. The Artifact only plots
shots that land inside the crop; all shots (in or out of range) are
still shown as text in the chain table.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
HOLE = 12

A, B = -3.3326271186440724, 649.8622881355936
C = 3.337133757961783


def px_of(v_y): return A * v_y + B
def py_of(v_x): return C * v_x


def main():
    con = sqlite3.connect(DB)
    pins = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())["pins"]
    round_pins_px = {}
    for rnd in (1, 2, 3, 4):
        p = pins[f"R{rnd}H{HOLE}"]
        round_pins_px[rnd] = {"gx": p["pin_x"], "gy": p["pin_y"], "px": px_of(p["pin_y"]), "py": py_of(p["pin_x"])}

    players = {"9115": "유해란(TOP,#1,-4)", "9708": "이재윤(MID,#27,+9)", "9111": "박서현(BOTTOM,#61,+26)"}
    chains = {}
    for pc, label in players.items():
        rows = con.execute(
            "SELECT round,shot,state_code,x,y,green_x,green_y,distance FROM klpga_player_shot "
            "WHERE game_code=? AND hole=? AND player_code=? ORDER BY round,shot",
            (GAME, HOLE, pc),
        ).fetchall()
        by_round = {}
        for rnd, shot, state, x, y, gx, gy, dist in rows:
            by_round.setdefault(rnd, []).append({
                "shot": shot, "state": state, "x": x, "y": y, "green_x": gx, "green_y": gy, "distance": dist,
                "overview_px": px_of(y) if y is not None else None,
                "overview_py": py_of(x) if x is not None else None,
                "green_px": px_of(gy) if gy is not None else None,
                "green_py": py_of(gx) if gx is not None else None,
            })
        chains[pc] = {"label": label, "rounds": by_round}

    out = {
        "round_pins_px": round_pins_px, "player_chains": chains,
        "transform_note": (
            "px=A*v_y+B, py=C*v_x (A=-3.3326271186440724,B=649.8622881355936,C=3.337133757961783); "
            "empirically fit from the already-published overview frame, re-applied to green_x/green_y "
            "under the same documented (390-v*2)*1.815-family formula shape used by the site's own JS "
            "for both panels -- NOT independently reverified for the green-closeup panel specifically."
        ),
    }
    (HERE / "artifact_data" / "hole12_round_pin_chains.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("wrote artifact_data/hole12_round_pin_chains.json")
    for rnd, p in round_pins_px.items():
        print(f"R{rnd} pin px,py = ({p['px']:.1f},{p['py']:.1f})")


if __name__ == "__main__":
    main()
