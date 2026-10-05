import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

HERE = Path(__file__).parent
res = json.loads((HERE / "three_player_attribution_audit_results.json").read_text())
ko2en_pair = {"유해란-이재윤": "Ryu-Lee", "이재윤-박서현": "Lee-Park", "유해란-박서현": "Ryu-Park"}


def stacked(data_ko, title, fname, palette):
    data = {ko2en_pair[k]: v for k, v in data_ko.items()}
    cats = sorted(set(c for v in data.values() for c in v))
    pairs = list(data.keys())
    fig, ax = plt.subplots(figsize=(10, 6))
    bottom_pos = [0] * len(pairs)
    bottom_neg = [0] * len(pairs)
    for cat in cats:
        vals = [data[p].get(cat, 0) for p in pairs]
        bottoms = [bottom_pos[i] if v >= 0 else bottom_neg[i] for i, v in enumerate(vals)]
        ax.bar(pairs, vals, bottom=bottoms, label=cat, color=palette.get(cat, "#999"))
        for i, v in enumerate(vals):
            if v >= 0:
                bottom_pos[i] += v
            else:
                bottom_neg[i] += v
    ax.axhline(0, color="black", linewidth=1)
    ax.set_ylabel("Net strokes (signed; sums exactly to the pair's net gap)")
    ax.set_title(title)
    ax.legend(fontsize=8, loc="lower left", ncol=2)
    fig.tight_layout()
    fig.savefig(HERE / fname, dpi=130)
    plt.close(fig)


palette_a = {"TEE": "#f59e0b", "APPROACH": "#2563eb", "RECOVERY": "#0891b2",
             "PUTTING": "#db2777", "PENALTY": "#b91c1c", "UNRESOLVED": "#6b7280"}
stacked(res["layer_a"], "LAYER A -- unique causal/shot-stage attribution (BIG NUMBER removed as a cause)",
        "chartA_layer_causal_stage.png", palette_a)

palette_b = {"Birdie+": "#16a34a", "Par": "#9ca3af", "Bogey": "#f59e0b", "Double": "#dc2626",
             "TriplePlus": "#7f1d1d", "Birdie+(A)": "#16a34a", "Birdie+(B)": "#15803d",
             "Bogey(A)": "#f59e0b", "Bogey(B)": "#d97706", "Double(A)": "#dc2626", "Double(B)": "#991b1b"}
stacked(res["layer_b"], "LAYER B -- event-severity decomposition (independent axis, not summed with Layer A)",
        "chartB_layer_severity.png", palette_b)

print("Wrote chartA_layer_causal_stage.png, chartB_layer_severity.png")
