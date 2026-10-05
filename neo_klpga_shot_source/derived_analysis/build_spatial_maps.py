"""Coordinate-space hole visualizations. NOT aligned to satellite/GPS
course imagery -- explicitly labeled as coordinate-space on every figure.
Two sub-spaces used, both real RAW fields:
  - whole-hole (x, y): tee-to-green, for tee-shot/overall trajectory.
  - pin-relative (green_x, green_y minus the real per-round pin): for
    near-green detail. Pin is always (0, 0) in this space by construction.
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
data = json.loads((HERE / "neo_three_player_spatial_chain.json").read_text())
inter = json.loads((HERE / "spatial_analysis_intermediate.json").read_text())
hole_summaries = data["hole_summaries"]
shot_records = data["shot_records"]
axes = data["tee_green_axes"]
by_hole_key = {(r["player_code"], r["round"], r["hole"]): r for r in hole_summaries}
by_shot_key = defaultdict(list)
for r in shot_records:
    by_shot_key[(r["player_code"], r["round"], r["hole"])].append(r)
for k in by_shot_key:
    by_shot_key[k].sort(key=lambda r: r["shot_number"])

NAME_EN = {"유해란": "Ryu", "이재윤": "Lee", "박서현": "Park"}
COLOR = {"유해란": "#1b6e3c", "이재윤": "#2563eb", "박서현": "#c2410c"}
CODE2NAME = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}


def pin_panel(ax, rnd, hole, player_codes, title):
    ax.scatter([0], [0], marker="+", s=200, color="black", zorder=5, label="PIN (real, this round)")
    for pc in player_codes:
        name = CODE2NAME[pc]
        sh = by_shot_key.get((pc, rnd, hole))
        if not sh:
            continue
        xs = [s["pin_dx_mapunits"] for s in sh if s["pin_dx_mapunits"] is not None]
        ys = [s["pin_dy_mapunits"] for s in sh if s["pin_dy_mapunits"] is not None]
        if not xs:
            continue
        ax.plot(xs, ys, "-o", color=COLOR[name], markersize=5, linewidth=1.3, alpha=0.85, label=NAME_EN[name])
        ax.scatter([xs[0]], [ys[0]], s=70, facecolors="none", edgecolors=COLOR[name], linewidths=2, zorder=4)
        rec = by_hole_key[(pc, rnd, hole)]
        ax.annotate(f"{rec['strokes']}", (xs[-1], ys[-1]), fontsize=8, color=COLOR[name])
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("pin-relative, coordinate-space units (NOT meters)", fontsize=7)
    ax.axhline(0, color="#ddd", linewidth=0.5)
    ax.axvline(0, color="#ddd", linewidth=0.5)
    ax.set_aspect("equal", adjustable="datalim")


def wholehole_panel(ax, rnd, hole, player_codes, title):
    g = axes[str(hole)]["green"]
    ax.scatter([g[0]], [g[1]], marker="*", s=180, color="black", zorder=5,
               label="field mean holed-out pt (NOT the real per-round pin)")
    for pc in player_codes:
        name = CODE2NAME[pc]
        sh = by_shot_key.get((pc, rnd, hole))
        if not sh:
            continue
        xs = [s["end_x"] for s in sh if s["end_x"] is not None]
        ys = [s["end_y"] for s in sh if s["end_y"] is not None]
        if not xs:
            continue
        ax.plot(xs, ys, "-o", color=COLOR[name], markersize=5, linewidth=1.3, alpha=0.85, label=NAME_EN[name])
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("whole-hole coordinate-space units (NOT meters, NOT GPS)", fontsize=7)
    ax.set_aspect("equal", adjustable="datalim")


def finish(fig, suptitle, fname, ncol=3):
    fig.suptitle(suptitle, fontsize=12)
    # shared legend: union of unique labels across ALL axes (a mixed-pair
    # map, e.g. Ryu-Lee in one panel and Ryu-Park in another, must show
    # every color actually used, not just the first panel's)
    seen = {}
    for ax in fig.axes:
        h, l = ax.get_legend_handles_labels()
        for hi, li in zip(h, l):
            if li not in seen:
                seen[li] = hi
    if seen:
        fig.legend(list(seen.values()), list(seen.keys()), loc="lower center",
                    ncol=min(ncol, len(seen)), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    fig.savefig(HERE / fname, dpi=130)
    plt.close(fig)


# ---- map01: score-gap casebook, top-3 Ryu-Park events, pin-relative ----
top3 = inter["pair_tops"]["유해란-박서현"][:3]
fig, axs = plt.subplots(1, 3, figsize=(15, 5))
for ax, r in zip(axs, top3):
    pin_panel(ax, r["round"], r["hole"], ["9115", "9111"], f"R{r['round']}H{r['hole']} par{r['par']} (Ryu {r['a']} vs Park {r['b']})")
finish(fig, "Score-gap casebook -- Ryu vs Park, top-3 widest hole-plays (pin-relative coordinate space)", "map01_score_gap_casebook.png")

# ---- map02: Ryu score preservation, pin-relative, up to 6 panels ----
pres = json.loads((HERE / "spatial_analysis_intermediate.json").read_text())
import csv as _csv
pres_rows = list(_csv.DictReader(open(HERE / "three_player_score_preservation_cases.csv", encoding="utf-8")))
fig, axs = plt.subplots(2, 3, figsize=(15, 9))
for ax, r in zip(axs.flat, pres_rows[:6]):
    pin_panel(ax, int(r["round"]), int(r["hole"]), ["9115"], f"R{r['round']}H{r['hole']} par{r['par']} Ryu={r['score']} (Bogey)")
for ax in axs.flat[len(pres_rows):]:
    ax.axis("off")
finish(fig, "Ryu's score-preservation chains -- her own Bogeys, where damage stopped at 1-over (pin-relative)", "map02_ryu_score_preservation.png", ncol=2)

# ---- map03: Lee safe-vs-scoring -- representative Ryu-birdied/Lee-par holes ----
rlp = inter["ryu_lee_positive_cases"][:4]
fig, axs = plt.subplots(1, 4, figsize=(18, 5))
for ax, c in zip(axs, rlp):
    pin_panel(ax, c["round"], c["hole"], ["9115", "9708"], f"R{c['round']}H{c['hole']} par{c['par']} (Ryu {c['a_score']} vs Lee {c['b_score']})")
finish(fig, "Lee: safe-but-not-scoring -- Ryu birdied, Lee parred from a comparable hole (pin-relative)", "map03_lee_safe_vs_scoring.png")

# ---- map04: Park failure escalation, her 5 Double+/TriplePlus events ----
park_big = [c for c in inter["lee_park_big_cases"]]
if len(park_big) < 5:
    # fall back to reconstructing all 5 directly from hole_summaries
    pass
fig, axs = plt.subplots(2, 3, figsize=(15, 9))
big_events = [(r["round"], r["hole"]) for r in hole_summaries if r["player_code"] == "9111" and r["score_bucket"] in ("Double", "TriplePlus")]
for ax, (rnd, hole) in zip(axs.flat, big_events):
    rec = by_hole_key[("9111", rnd, hole)]
    pin_panel(ax, rnd, hole, ["9111"], f"R{rnd}H{hole} par{rec['par']} Park={rec['strokes']} ({rec['score_bucket']})")
for ax in axs.flat[len(big_events):]:
    ax.axis("off")
finish(fig, "Park's failure-escalation chains -- all 5 Double+/TriplePlus events (pin-relative)", "map04_park_failure_escalation.png", ncol=1)

# ---- map05: same-start different-end, whole-hole panels ----
ssde = inter["same_start_diff_end"]
fig, axs = plt.subplots(1, len(ssde), figsize=(6 * len(ssde), 5))
if len(ssde) == 1:
    axs = [axs]
name2code = {"유해란": "9115", "이재윤": "9708", "박서현": "9111"}
for ax, r in zip(axs, ssde):
    codes = [name2code[r["player_a"]], name2code[r["player_b"]]]
    wholehole_panel(ax, r["round"], r["hole"], codes,
                     f"R{r['round']}H{r['hole']} par{r['par']} tol={r['tolerance_yd']}yd\n"
                     f"{NAME_EN[r['player_a']]}={r['a_score']}({r['a_bucket']}) vs {NAME_EN[r['player_b']]}={r['b_score']}({r['b_bucket']})")
finish(fig, "SAME-START, DIFFERENT-END -- comparable fairway landing, divergent final score (whole-hole coordinate space)", "map05_same_start_different_end.png")

# ---- map06: same-miss different-recovery, pin-relative ----
smdr = inter["same_miss_diff_recovery"]
fig, axs = plt.subplots(1, len(smdr), figsize=(6 * len(smdr), 5))
if len(smdr) == 1:
    axs = [axs]
for ax, r in zip(axs, smdr):
    codes = [name2code[r["player_a"]], name2code[r["player_b"]]]
    pin_panel(ax, r["round"], r["hole"], codes,
              f"R{r['round']}H{r['hole']} par{r['par']} miss={r['miss_lie']}\n"
              f"{NAME_EN[r['player_a']]}={r['a_score']}({r['a_bucket']}) vs {NAME_EN[r['player_b']]}={r['b_score']}({r['b_bucket']})")
finish(fig, "SAME MISS LIE, comparable distance-to-pin -- divergent recovery outcome (pin-relative)", "map06_same_miss_different_recovery.png")

print("Wrote map01..map06")
