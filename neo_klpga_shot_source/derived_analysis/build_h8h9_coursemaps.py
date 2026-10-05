"""H8/H9 real course-map visualizations. Background = actual KLPGA
Shot Tracker images (hole_8.png / hole_8_G.png / hole_9.png / hole_9_G.png),
not decoration -- every marker is placed with the confirmed transform
(build_h8h9_alignment_validation.py, both holes PASS). Field = low-alpha
context layer (real tee-landing / green-arrival points, colored by real
eventual score). Player = foreground story (connected real shot-to-shot
traces, R1-R4, per player). Lines are literal start->recorded-endpoint
traces, not actual-aim indicators.
"""
from __future__ import annotations
import json, sqlite3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
IMG_DIR = HERE.parent / "hole_images"
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"

A, B = -3.3326271186440724, 649.8622881355936
C = 3.337133757961783
def px_of(v_y): return A * v_y + B
def py_of(v_x): return C * v_x

PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
NAME_EN = {"유해란": "Ryu", "이재윤": "Lee", "박서현": "Park"}
COLOR = {"유해란": "#1b6e3c", "이재윤": "#2563eb", "박서현": "#c2410c"}
ROUND_MARK = {1: "o", 2: "s", 3: "^", 4: "D"}
ROUND_LABEL_OFFSET = {1: (8, 10), 2: (8, -14), 3: (-30, 10), 4: (-30, -14)}  # (dx, dy) points, avoids collisions
PIN_AUDIT = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())
PINS = {(e["round"], e["hole"]): e for e in PIN_AUDIT["per_round_hole_table"]}
BUCKET_SHORT = {"Birdie+": "BIRDIE", "Par": "PAR", "Bogey": "BOGEY", "Double": "DOUBLE+", "TriplePlus": "DOUBLE+"}
chain = json.loads((HERE / "three_player_attribution_chain.json").read_text())["records"]
chain_by = {(r["player_code"], r["round"], r["hole"]): r for r in chain}


def load_field(hole):
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT player_code, round, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND hole=? ORDER BY player_code, round, shot",
        (GAME, hole)).fetchall()
    by_pr = defaultdict(list)
    for pc, rnd, shot, st, x, y, gx, gy, d in rows:
        by_pr[(pc, rnd)].append({"shot": shot, "state": st, "x": x, "y": y, "gx": gx, "gy": gy, "d": d})
    return by_pr


def score_color(bucket):
    return "#dc2626" if bucket in ("Bogey", "Double", "TriplePlus") else "#9ca3af"


def draw_whole_hole(ax, hole, by_pr, show_text=True):
    img = plt.imread(IMG_DIR / f"hole_{hole}.png")
    ax.imshow(img, extent=[0, 650, 433, 0])  # origin top-left, matches px/py convention
    # FIELD context: tee-landing points (shot=1), colored by eventual score, low alpha
    for (pc, rnd), shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        s1 = ss[0]
        if s1["y"] is None:
            continue
        final = chain_by.get((pc, rnd, hole))
        bucket = final["score_bucket"] if final else None
        col = score_color(bucket) if bucket else "#9ca3af"
        ax.scatter([px_of(s1["y"])], [py_of(s1["x"])], s=22, color=col, alpha=0.22, linewidths=0, zorder=2)
    # PLAYER foreground: TEE -> first GREEN-arrival only (short game detail lives in the
    # green panel; drawing full putt sequences here at whole-hole scale is pure clutter)
    for pc, pname in PLAYERS.items():
        for rnd in (1, 2, 3, 4):
            shots = by_pr.get((pc, rnd))
            if not shots:
                continue
            ss = sorted(shots, key=lambda s: s["shot"])
            green_idx = next((i for i, s in enumerate(ss) if s["state"] in ("3", "10")), len(ss) - 1)
            pre_green = ss[: green_idx + 1]
            xs = [px_of(s["y"]) for s in pre_green if s["y"] is not None]
            ys = [py_of(s["x"]) for s in pre_green if s["x"] is not None]
            if not xs:
                continue
            ax.plot(xs, ys, "-", color=COLOR[pname], linewidth=1.8, alpha=0.95, zorder=5,
                     marker=ROUND_MARK[rnd], markersize=6, markeredgecolor="white", markeredgewidth=0.7)
            if show_text:
                dx, dy = ROUND_LABEL_OFFSET[rnd]
                ax.annotate(f"{NAME_EN[pname][0]}{rnd}", (xs[0], ys[0]), fontsize=6.5, color=COLOR[pname],
                            fontweight="bold", xytext=(dx * 0.6, dy * 0.6), textcoords="offset points",
                            ha="left" if dx > 0 else "right",
                            path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])
    ax.set_xlim(0, 650)
    ax.set_ylim(433, 0)
    ax.axis("off")


def draw_green_detail(ax, hole, by_pr, show_text=True):
    img = plt.imread(IMG_DIR / f"hole_{hole}_G.png")
    ax.imshow(img, extent=[0, 650, 433, 0])
    # FIELD context: green-arrival points, colored by eventual score
    for (pc, rnd), shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        g = next((s for s in ss if s["state"] == "3"), None)
        if g is None or g["gy"] is None:
            continue
        final = chain_by.get((pc, rnd, hole))
        bucket = final["score_bucket"] if final else None
        col = score_color(bucket) if bucket else "#9ca3af"
        ax.scatter([px_of(g["gy"])], [py_of(g["gx"])], s=22, color=col, alpha=0.22, linewidths=0, zorder=2)
    # Real pins, one marker style per round
    pin_colors = {1: "#111827", 2: "#111827", 3: "#111827", 4: "#111827"}
    for rnd in (1, 2, 3, 4):
        pin = PINS.get((rnd, hole))
        if pin is None:
            continue
        ppx, ppy = px_of(pin["pin_y"]), py_of(pin["pin_x"])
        ax.scatter([ppx], [ppy], marker=ROUND_MARK[rnd], s=90, facecolor="#fde047", edgecolor="#111827",
                   linewidths=1.3, zorder=8)
        if show_text:
            dx, dy = ROUND_LABEL_OFFSET[rnd]
            ax.annotate(f"PIN R{rnd}", (ppx, ppy), fontsize=6, color="#111827", fontweight="bold",
                        xytext=(dx, dy + 9), textcoords="offset points", ha="left" if dx > 0 else "right",
                        path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
    # Player foreground: from the approach-arrival shot onward (miss/on -> recovery -> finish)
    for pc, pname in PLAYERS.items():
        for rnd in (1, 2, 3, 4):
            shots = by_pr.get((pc, rnd))
            if not shots:
                continue
            ss = sorted(shots, key=lambda s: s["shot"])
            # start the green-detail trace from the first shot whose green_x/y puts it near this
            # panel's frame (i.e. all shots with usable gx/gy -- the full short-game sequence)
            pts = [(px_of(s["gy"]), py_of(s["gx"])) for s in ss if s["gy"] is not None]
            if not pts:
                continue
            xs, ys = zip(*pts)
            ax.plot(xs, ys, "-", color=COLOR[pname], linewidth=1.6, alpha=0.95, zorder=6,
                     marker=ROUND_MARK[rnd], markersize=5, markeredgecolor="white", markeredgewidth=0.6)
            final = chain_by.get((pc, rnd, hole))
            if show_text and final:
                lbl = f"{NAME_EN[pname][0]}{rnd}:{BUCKET_SHORT.get(final['score_bucket'],'')}"
                dx, dy = ROUND_LABEL_OFFSET[rnd]
                ax.annotate(lbl, (xs[-1], ys[-1]), fontsize=6, color=COLOR[pname], fontweight="bold",
                            xytext=(dx, dy - 9), textcoords="offset points", ha="left" if dx > 0 else "right",
                            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
    ax.set_xlim(0, 650)
    ax.set_ylim(433, 0)
    ax.axis("off")


def build_prototype(hole, title, subtitle, out_name, show_text=True):
    by_pr = load_field(hole)
    FIG_W, FIG_H = 7.2, 9.6
    if show_text:
        top, bottom, gap = 0.85, 0.08, 0.015
        panel_h_frac = (top - bottom - gap) / 2
        panel_h_in = panel_h_frac * FIG_H
        panel_w_in = panel_h_in * (650 / 433)
        panel_w_frac = panel_w_in / FIG_W
        left = (1 - panel_w_frac) / 2
        fig = plt.figure(figsize=(FIG_W, FIG_H))
        ax0 = fig.add_axes([left, top - panel_h_frac, panel_w_frac, panel_h_frac])
        ax1 = fig.add_axes([left, bottom, panel_w_frac, panel_h_frac])
    else:
        panel_w_in = FIG_W
        panel_h_in = panel_w_in * (433 / 650)
        panel_h_frac = panel_h_in / FIG_H
        fig = plt.figure(figsize=(FIG_W, FIG_H))
        ax0 = fig.add_axes([0.0, 1 - panel_h_frac, 1.0, panel_h_frac])
        ax1 = fig.add_axes([0.0, 1 - 2 * panel_h_frac - 0.01, 1.0, panel_h_frac])
    draw_whole_hole(ax0, hole, by_pr, show_text=show_text)
    draw_green_detail(ax1, hole, by_pr, show_text=show_text)
    if show_text:
        ax0.set_title("WHOLE HOLE -- tee-to-green trace (field=light dots, player=solid line)", fontsize=9, pad=4)
        ax1.set_title("GREEN DETAIL -- real R1-R4 pins + approach/miss/recovery/finish", fontsize=9, pad=4)
        fig.text(0.5, 0.975, f"{title}", ha="center", fontsize=13, fontweight="bold")
        fig.text(0.5, 0.945, f"{subtitle}", ha="center", fontsize=10)
        fig.text(0.5, 0.918, "coordinate-space overlay on real KLPGA Shot Tracker course image -- lines are recorded shot traces, not actual aim",
                 ha="center", fontsize=6.3, color="#555")
        handles = [plt.Line2D([0], [0], color=COLOR[p], lw=2, marker=ROUND_MARK[1], label=NAME_EN[p]) for p in PLAYERS.values()]
        handles += [plt.Line2D([0], [0], marker=ROUND_MARK[r], color="w", markerfacecolor="#6b7280",
                                markeredgecolor="#111827", markersize=7, label=f"R{r}") for r in (1, 2, 3, 4)]
        handles += [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markersize=6, label="field: bogey+"),
                    plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#9ca3af", markersize=6, label="field: par or better")]
        fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=7.5, bbox_to_anchor=(0.5, 0.012))
    fig.savefig(HERE / out_name, dpi=150)
    plt.close(fig)
    print("Wrote", out_name)


# ---- H8 / H9 prototypes (with text; Korean titles given in the report
# prose -- no CJK-capable font is installed in this sandbox, same
# constraint already documented for every earlier chart this session) ----
build_prototype(8, "HOLE 8 -- Difficult for everyone", "field avg +0.387 (par4 field avg +0.258) | Double+ 10.3% (n=331)", "NEO_H8_COURSEMAP_PROTOTYPE.png")
build_prototype(9, "HOLE 9 -- Costlier for Park than for the course", "field avg +0.127 (easier than par4 field avg, n=331) | Park repeat loss R3/R4 only", "NEO_H9_COURSEMAP_PROTOTYPE.png")

# ---- No-text QA versions (minimal labels only) ----
build_prototype(8, "", "", "NEO_H8_COURSEMAP_NO_TEXT_QA.png", show_text=False)
build_prototype(9, "", "", "NEO_H9_COURSEMAP_NO_TEXT_QA.png", show_text=False)


# ---- Side-by-side comparison ----
fig, axs = plt.subplots(2, 2, figsize=(15, 11))
by_pr8 = load_field(8)
by_pr9 = load_field(9)
draw_whole_hole(axs[0, 0], 8, by_pr8, show_text=True)
draw_green_detail(axs[1, 0], 8, by_pr8, show_text=True)
draw_whole_hole(axs[0, 1], 9, by_pr9, show_text=True)
draw_green_detail(axs[1, 1], 9, by_pr9, show_text=True)
axs[0, 0].set_title("HOLE 8 -- whole hole (shared course risk)", fontsize=10, fontweight="bold")
axs[1, 0].set_title("HOLE 8 -- green detail", fontsize=9)
axs[0, 1].set_title("HOLE 9 -- whole hole (Park-specific repeat risk)", fontsize=10, fontweight="bold")
axs[1, 1].set_title("HOLE 9 -- green detail", fontsize=9)
handles = [plt.Line2D([0], [0], color=COLOR[p], lw=2, marker=ROUND_MARK[1], label=NAME_EN[p]) for p in PLAYERS.values()]
handles += [plt.Line2D([0], [0], marker=ROUND_MARK[r], color="w", markerfacecolor="#6b7280",
                        markeredgecolor="#111827", markersize=7, label=f"R{r}") for r in (1, 2, 3, 4)]
handles += [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markersize=6, label="field: bogey+"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#9ca3af", markersize=6, label="field: par or better")]
fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("H8 vs H9 -- field avg +0.387 (H8) vs +0.127 (H9); Park repeat loss (R3/R4) only on H9", fontsize=12, fontweight="bold")
fig.tight_layout(rect=[0, 0.04, 1, 0.95])
fig.savefig(HERE / "NEO_H8_H9_VISUAL_COMPARISON.png", dpi=140)
plt.close(fig)
print("Wrote NEO_H8_H9_VISUAL_COMPARISON.png")
