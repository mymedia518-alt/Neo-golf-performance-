import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
chain = json.loads((HERE / "three_player_attribution_chain.json").read_text())["records"]
mech_by_hole = {m["hole"]: m for m in json.loads((HERE / "blue_heron_hole_mechanism.json").read_text())}
by_hole_key = {(r["player_code"], r["round"], r["hole"]): r for r in chain}
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
NAME_EN = {"유해란": "Ryu", "이재윤": "Lee", "박서현": "Park"}
COLOR = {"유해란": "#1b6e3c", "이재윤": "#2563eb", "박서현": "#c2410c"}

seq = [(rnd, hole) for rnd in (1, 2, 3, 4) for hole in range(1, 19)]

fig, ax = plt.subplots(figsize=(15, 6))
cum_data = {}
for pc, name in PLAYERS.items():
    cum = []
    tot = 0
    for rnd, hole in seq:
        tot += by_hole_key[(pc, rnd, hole)]["score_to_par"]
        cum.append(tot)
    cum_data[name] = cum
    ax.plot(range(1, 73), cum, label=NAME_EN[name], color=COLOR[name], linewidth=2)

for r in (1, 2, 3):
    ax.axvline(r * 18 + 0.5, color="#999", linestyle="--", linewidth=0.8)

# Annotate the biggest Ryu-Park step moments with their real hole number + mechanism
annotate_idx = {(3, 8): "H8\nMIXED", (4, 9): "H9\nTEE", (4, 10): "H10\nTEE", (1, 3): "H3\nAPPROACH",
                (1, 16): "H16\nPENALTY\n(Park better)", (4, 4): "H4\nMIXED"}
for (rnd, hole), label in annotate_idx.items():
    idx = seq.index((rnd, hole))
    y = cum_data["박서현"][idx]
    ax.annotate(label, (idx + 1, y), fontsize=7, color="#c2410c", ha="center",
                xytext=(0, 10), textcoords="offset points",
                arrowprops=dict(arrowstyle="-", color="#c2410c", lw=0.6))

ax.set_xlabel("Hole-play # (R1 H1-18, R2 H1-18, R3 H1-18, R4 H1-18)")
ax.set_ylabel("Cumulative strokes to par")
ax.set_title("Blue Heron 72-hole score story -- where the gap actually opened (real holes annotated)")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(HERE / "NEO_BLUE_HERON_SCORE_STORY.png", dpi=140)
plt.close(fig)
print("Wrote NEO_BLUE_HERON_SCORE_STORY.png")
