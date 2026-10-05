import json, csv, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
data = json.loads((HERE / "neo_three_player_spatial_chain.json").read_text())
by_hole_key = {(r["player_code"], r["round"], r["hole"]): r for r in data["hole_summaries"]}
by_shot_key = defaultdict(list)
for r in data["shot_records"]:
    by_shot_key[(r["player_code"], r["round"], r["hole"])].append(r)
for k in by_shot_key:
    by_shot_key[k].sort(key=lambda r: r["shot_number"])
NAME_EN = {"유해란": "Ryu", "이재윤": "Lee", "박서현": "Park"}
COLOR = {"유해란": "#1b6e3c", "이재윤": "#2563eb", "박서현": "#c2410c"}
CODE2NAME = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}


def pin_panel(ax, rnd, hole, player_codes, title):
    ax.scatter([0], [0], marker="+", s=200, color="black", zorder=5, label="PIN")
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
        rec = by_hole_key[(pc, rnd, hole)]
        ax.annotate(f"{rec['strokes']}", (xs[-1], ys[-1]), fontsize=8, color=COLOR[name])
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("pin-relative coordinate-space units (NOT meters)", fontsize=7)
    ax.axhline(0, color="#ddd", linewidth=0.5)
    ax.axvline(0, color="#ddd", linewidth=0.5)
    ax.set_aspect("equal", adjustable="datalim")


def finish(fig, suptitle, fname, ncol=3):
    fig.suptitle(suptitle, fontsize=12)
    seen = {}
    for ax in fig.axes:
        h, l = ax.get_legend_handles_labels()
        for hi, li in zip(h, l):
            if li not in seen:
                seen[li] = hi
    if seen:
        fig.legend(list(seen.values()), list(seen.keys()), loc="lower center",
                   ncol=min(ncol, len(seen)), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    fig.savefig(HERE / fname, dpi=130)
    plt.close(fig)


# ---- map07: same-location different-execution, top divergent cases ----
sle = list(csv.DictReader(open(HERE / "same_location_player_execution.csv", encoding="utf-8")))
sle_div = [r for r in sle if r["strokes_to_finish_diff"] != "0"]
sle_div.sort(key=lambda r: -abs(int(r["strokes_to_finish_diff"])))
top6 = sle_div[:6]
name2code = {"유해란": "9115", "이재윤": "9708", "박서현": "9111"}
fig, axs = plt.subplots(2, 3, figsize=(15, 9))
for ax, r in zip(axs.flat, top6):
    codes = [name2code[r["player_a"]], name2code[r["player_b"]]]
    title = (f"{r['lie']} ~{r['remaining_a_yd']}/{r['remaining_b_yd']}yd\n"
             f"{NAME_EN[r['player_a']]} R{r['round_a']}H{r['hole_a']} finish={r['strokes_to_finish_a']} vs "
             f"{NAME_EN[r['player_b']]} R{r['round_b']}H{r['hole_b']} finish={r['strokes_to_finish_b']}")
    # plot each player's OWN hole separately (different holes -> can't share one pin-relative frame meaningfully
    # unless same hole; handle generically by showing each player's own hole chain in its own pin-relative frame,
    # overlaid since pin is always (0,0) by construction regardless of which hole)
    ax.scatter([0], [0], marker="+", s=200, color="black", zorder=5, label="PIN (each own round/hole)")
    for role, pname, rnd, hole in [("a", r["player_a"], r["round_a"], r["hole_a"]), ("b", r["player_b"], r["round_b"], r["hole_b"])]:
        pc = name2code[pname]
        sh = by_shot_key.get((pc, int(rnd), int(hole)))
        if not sh:
            continue
        xs = [s["pin_dx_mapunits"] for s in sh if s["pin_dx_mapunits"] is not None]
        ys = [s["pin_dy_mapunits"] for s in sh if s["pin_dy_mapunits"] is not None]
        ax.plot(xs, ys, "-o", color=COLOR[pname], markersize=5, linewidth=1.3, alpha=0.85, label=NAME_EN[pname])
    ax.set_title(title, fontsize=8)
    ax.axhline(0, color="#ddd", linewidth=0.5)
    ax.axvline(0, color="#ddd", linewidth=0.5)
    ax.set_aspect("equal", adjustable="datalim")
finish(fig, "map07: same lie + comparable real-yard distance (different holes), different strokes-to-finish\n"
            "(pin-relative, each player's OWN round/hole overlaid at a shared (0,0) pin)", "map07_same_location_different_execution.png")

# ---- map08: fairway paradox, 4 example cases (FW_HIT_BAD vs FW_MISS_GOOD) ----
fwp = list(csv.DictReader(open(HERE / "neo_fairway_paradox_cases.csv", encoding="utf-8")))
hit_bad = [r for r in fwp if r["category"] == "FW_HIT_BAD"][:2]
miss_good = [r for r in fwp if r["category"] == "FW_MISS_GOOD" and r["final_bucket"] == "Birdie+"][:2]
cases8 = hit_bad + miss_good
fig, axs = plt.subplots(1, 4, figsize=(18, 5))
for ax, r in zip(axs, cases8):
    pc = name2code[r["player"]]
    pin_panel(ax, int(r["round"]), int(r["hole"]), [pc],
              f"{r['category']}\n{NAME_EN[r['player']]} R{r['round']}H{r['hole']} tee={r['tee_lie']} -> {r['final_bucket']}")
finish(fig, "map08: fairway paradox -- FW HIT that still went bad, FW MISS that still scored", "map08_fairway_paradox.png", ncol=1)

# ---- map09: GIR paradox, 4 example cases ----
girp = list(csv.DictReader(open(HERE / "neo_gir_paradox_cases.csv", encoding="utf-8")))
gir_bogey = [r for r in girp if r["category"] == "GIR_TO_Bogey"][:2]
girmiss_par = [r for r in girp if r["category"] == "GIRMISS_TO_Par"][:2]
cases9 = gir_bogey + girmiss_par
fig, axs = plt.subplots(1, 4, figsize=(18, 5))
for ax, r in zip(axs, cases9):
    pc = name2code[r["player"]]
    pin_panel(ax, int(r["round"]), int(r["hole"]), [pc],
              f"{r['category']}\n{NAME_EN[r['player']]} R{r['round']}H{r['hole']}")
finish(fig, "map09: GIR paradox -- GIR that still bogeyed, GIR-miss that still parred", "map09_gir_paradox.png", ncol=1)

# ---- map10: field vs player location value (bar chart, not a hole map) ----
fvp = list(csv.DictReader(open(HERE / "field_vs_player_location_value.csv", encoding="utf-8")))
fvp_valid = [r for r in fvp if r["player_avg_score_to_par"] not in (None, "")]
fig, ax = plt.subplots(figsize=(12, 6))
labels = sorted(set(f"{r['lie']}\n{r['distance_band']}" for r in fvp_valid), key=lambda s: s)[:8]
x = range(len(labels))
width = 0.2
for i, pname in enumerate(["유해란", "이재윤", "박서현"]):
    vals = []
    for lab in labels:
        lie, band = lab.split("\n")
        match = next((r for r in fvp_valid if r["lie"] == lie and r["distance_band"] == band and r["player"] == pname), None)
        vals.append(float(match["player_avg_score_to_par"]) if match else None)
    xs = [xi + (i - 1) * width for xi in x if vals[xi] is not None]
    ys = [v for v in vals if v is not None]
    ax.bar(xs, ys, width=width, label=NAME_EN[pname], color=COLOR[pname])
field_vals = []
for lab in labels:
    lie, band = lab.split("\n")
    match = next((r for r in fvp_valid if r["lie"] == lie and r["distance_band"] == band), None)
    field_vals.append(float(match["field_avg_score_to_par"]) if match else None)
ax.plot(list(x), field_vals, "k--o", label="FIELD avg", markersize=6)
ax.set_xticks(list(x), labels, fontsize=7)
ax.set_ylabel("avg final score-to-par from this condition")
ax.legend()
finish(fig, "map10: field vs player location value -- avg eventual score-to-par by (lie, distance band)",
       "map10_field_vs_player_location_value.png", ncol=4)

# ---- map11: course x player risk matrix (scatter) ----
crm = list(csv.DictReader(open(HERE / "course_player_risk_matrix.csv", encoding="utf-8")))
fig, ax = plt.subplots(figsize=(9, 7))
label_set = set()
for r in crm:
    if r["player_avg_score_to_par"] in (None, ""):
        continue
    x = float(r["field_avg_score_to_par"])
    y = float(r["player_avg_score_to_par"])
    pname = r["player"]
    marker = {"유해란": "o", "이재윤": "s", "박서현": "^"}[pname]
    ax.scatter([x], [y], color=COLOR[pname], marker=marker, s=60, alpha=0.85,
               label=NAME_EN[pname] if pname not in label_set else None)
    label_set.add(pname)
    if pname == "박서현" and int(r["hole"]) in (8, 9):
        ax.annotate(f"H{r['hole']}", (x, y), fontsize=9, fontweight="bold")
ax.axline((0, 0), slope=1, color="#999", linestyle="--", linewidth=0.8, label="field == player (y=x)")
ax.set_xlabel("field avg score-to-par on this hole (course risk)")
ax.set_ylabel("player avg score-to-par on this hole (player risk)")
ax.legend()
finish(fig, "map11: course risk (x) vs player risk (y), all 18 holes -- Hole 8/9 labeled for Park",
       "map11_course_player_risk_matrix.png")

# ---- map12: next-shot quality chain, one illustrative hole-play (R3H8 Park) ----
fig, ax = plt.subplots(figsize=(7, 7))
sh = by_shot_key[("9111", 3, 8)]
xs = [s["pin_dx_mapunits"] for s in sh if s["pin_dx_mapunits"] is not None]
ys = [s["pin_dy_mapunits"] for s in sh if s["pin_dy_mapunits"] is not None]
ax.scatter([0], [0], marker="+", s=200, color="black", zorder=5, label="PIN")
ax.plot(xs, ys, "-o", color=COLOR["박서현"], markersize=7, linewidth=1.5)
for i, s in enumerate(sh):
    ax.annotate(f"shot{s['shot_number']}:{s['lie_after']}\nrem={s['remaining_distance_after_yd']}yd",
                (s["pin_dx_mapunits"], s["pin_dy_mapunits"]), fontsize=6)
ax.set_title("map12: next-shot quality chain -- R3H8 Park, TriplePlus\n"
             "each point = state1 (shot result); annotation = state2 hint (lie + remaining)", fontsize=9)
ax.axhline(0, color="#ddd", linewidth=0.5)
ax.axvline(0, color="#ddd", linewidth=0.5)
ax.set_aspect("equal", adjustable="datalim")
finish(fig, "", "map12_next_shot_quality_chain.png", ncol=1)

print("Wrote map07..map12")
