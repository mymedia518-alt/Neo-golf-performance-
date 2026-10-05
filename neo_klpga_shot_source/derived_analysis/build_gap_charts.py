import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
chain = json.loads((HERE / "three_player_master_chain.json").read_text())["records"]
deep = json.loads((HERE / "three_player_gap_deep_analysis.json").read_text())
by_prh = {(r["player_code"], r["round"], r["hole"]): r for r in chain}
PLAYERS = {"9115": "Ryu", "9708": "Lee", "9111": "Park"}
COLORS = {"Ryu": "#1b6e3c", "Lee": "#2563eb", "Park": "#c2410c"}

# sequence of 72 hole-plays in round/hole order
seq = [(rnd, hole) for rnd in (1, 2, 3, 4) for hole in range(1, 19)]

# ---------- Chart 1: cumulative score-to-par, 3 players, 72 holes ----------
fig, ax = plt.subplots(figsize=(13, 5))
for pc, name in PLAYERS.items():
    cum = []
    tot = 0
    for rnd, hole in seq:
        tot += by_prh[(pc, rnd, hole)]["score_to_par"]
        cum.append(tot)
    ax.plot(range(1, 73), cum, label=name, color=COLORS[name], linewidth=1.8)
for r in (1, 2, 3):
    ax.axvline(r * 18 + 0.5, color="#999", linestyle="--", linewidth=0.8)
ax.set_xlabel("Hole-play # (R1 H1-18, R2 H1-18, R3 H1-18, R4 H1-18)")
ax.set_ylabel("Cumulative strokes to par")
ax.set_title("72-hole cumulative score-to-par -- Ryu(1st,-4) / Lee(27th,+9) / Park(61st,+26)")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(HERE / "chart1_cumulative_score_to_par.png", dpi=130)
plt.close(fig)

# ---------- Chart 2: pairwise net-gap concentration (top-N % of net gap) ----------
concentration = {
    "Ryu-Lee": [15.4, 38.5, 53.8, 92.3],
    "Lee-Park": [17.6, 41.2, 64.7, 94.1],
    "Ryu-Park": [10.0, 23.3, 36.7, 60.0],
}
fig, ax = plt.subplots(figsize=(8, 5))
xs = ["Top1", "Top3", "Top5", "Top10"]
label_map = {'Ryu-Lee': '유해란-이재윤', 'Lee-Park': '이재윤-박서현', 'Ryu-Park': '유해란-박서현'}
for k, v in concentration.items():
    net = deep['pair_net_gap'][label_map[k]]
    ax.plot(xs, v, marker="o", label=f"{k} (net={net})")
ax.set_ylabel("% of net pairwise gap explained")
ax.set_title("Score-gap concentration -- how few hole-plays explain the gap")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(HERE / "chart2_gap_concentration.png", dpi=130)
plt.close(fig)

# ---------- Chart 3: GIR-miss -> outcome, 3 players ----------
rates = deep["player_rates"]
PLAYERS_KO = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
fig, ax = plt.subplots(figsize=(8, 5))
names = [PLAYERS[pc] for pc in PLAYERS]
parsave = [rates[pc]["GIRMiss_to_ParSave"] * 100 for pc in PLAYERS]
bogey = [rates[pc]["GIRMiss_to_Bogey"] * 100 for pc in PLAYERS]
dbl = [rates[pc]["GIRMiss_to_DoublePlus"] * 100 for pc in PLAYERS]
x = range(len(names))
ax.bar(x, parsave, label="Par-save (Birdie/Par)", color="#16a34a")
ax.bar(x, bogey, bottom=parsave, label="Bogey", color="#f59e0b")
ax.bar(x, dbl, bottom=[p + b for p, b in zip(parsave, bogey)], label="Double+", color="#dc2626")
ax.set_xticks(list(x), names)
ax.set_ylabel("% of GIR-miss hole-plays")
ax.set_title("GIR-miss -> outcome, all 72 holes (recovery conversion)")
for i, pc in enumerate(PLAYERS):
    ax.text(i, 102, f"n={rates[pc]['GIRMiss_n']}", ha="center", fontsize=9)
ax.set_ylim(0, 110)
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(HERE / "chart3_gir_miss_outcome.png", dpi=130)
plt.close(fig)

# ---------- Chart 4: big-number (Double+) event count & total damage ----------
big = deep["big_events"]
KO2EN = {"유해란": "Ryu", "이재윤": "Lee", "박서현": "Park"}
by_p = defaultdict(list)
for e in big:
    by_p[KO2EN.get(e["player"], e["player"])].append(e)
fig, ax = plt.subplots(figsize=(7, 5))
names2 = list(PLAYERS.values())
counts = [len(by_p.get(n, [])) for n in names2]
damage = [sum(e["score_to_par"] for e in by_p.get(n, [])) for n in names2]
x = range(len(names2))
ax2 = ax.twinx()
ax.bar([i - 0.15 for i in x], counts, width=0.3, color="#2563eb", label="# Double+ events")
ax2.bar([i + 0.15 for i in x], damage, width=0.3, color="#dc2626", label="Total strokes-over-par from Double+")
ax.set_xticks(list(x), names2)
ax.set_ylabel("# Double+ events (72 holes)", color="#2563eb")
ax2.set_ylabel("Total strokes over par from Double+", color="#dc2626")
ax.set_title("Big-number (Double-bogey-or-worse) events, all 72 holes")
fig.tight_layout()
fig.savefig(HERE / "chart4_big_number_events.png", dpi=130)
plt.close(fig)

# ---------- Chart 5: field-relative round performance (from Step 4, already locked) ----------
field_rel = {
    "Ryu": [-3.73, -7.03, -1.31, -4.69],
    "Lee": [-0.73, -1.03, -0.31, -1.69],
    "Park": [-1.73, 1.97, 6.69, 6.31],
}
fig, ax = plt.subplots(figsize=(8, 5))
rounds = ["R1", "R2", "R3", "R4"]
for name, vals in field_rel.items():
    ax.plot(rounds, vals, marker="o", label=name, color=COLORS[name], linewidth=2)
ax.axhline(0, color="#999", linewidth=0.8)
ax.set_ylabel("Player round score - field round average (strokes)")
ax.set_title("Field-relative round performance (negative = better than field)")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(HERE / "chart5_field_relative_rounds.png", dpi=130)
plt.close(fig)

# ---------- Chart 6: gap decomposition (net, signed) per pair, stacked ----------
net_decomp_ko = deep["gap_decomposition_net_by_pair"]
ko2en_pair = {'유해란-이재윤': 'Ryu-Lee', '이재윤-박서현': 'Lee-Park', '유해란-박서현': 'Ryu-Park'}
net_decomp = {ko2en_pair[k]: v for k, v in net_decomp_ko.items()}
cats = sorted(set(c for v in net_decomp.values() for c in v))
fig, ax = plt.subplots(figsize=(10, 6))
pairs = list(net_decomp.keys())
bottom_pos = [0] * len(pairs)
bottom_neg = [0] * len(pairs)
palette = {"BETTER_PLAYER_BIRDIE": "#16a34a", "TEE_MISS": "#f59e0b", "TEE_PENALTY": "#b91c1c",
           "APPROACH_MISS": "#2563eb", "APPROACH_PENALTY": "#7c3aed", "GREEN_MISS_RECOVERY_FAIL": "#0891b2",
           "THREE_PUTT_PLUS": "#db2777", "BIG_NUMBER_COMPOUND": "#dc2626"}
for cat in cats:
    vals = [net_decomp[p].get(cat, 0) for p in pairs]
    bottoms = [bottom_pos[i] if v >= 0 else bottom_neg[i] for i, v in enumerate(vals)]
    ax.bar(pairs, vals, bottom=bottoms, label=cat, color=palette.get(cat, "#999"))
    for i, v in enumerate(vals):
        if v >= 0:
            bottom_pos[i] += v
        else:
            bottom_neg[i] += v
ax.axhline(0, color="black", linewidth=1)
ax.set_ylabel("Net strokes (signed; sums to the pair's net gap)")
ax.set_title("Score-gap decomposition by failure category (no double-counting)")
ax.legend(fontsize=8, loc="lower left")
fig.tight_layout()
fig.savefig(HERE / "chart6_gap_decomposition.png", dpi=130)
plt.close(fig)

print("Wrote chart1..chart6 PNGs")
