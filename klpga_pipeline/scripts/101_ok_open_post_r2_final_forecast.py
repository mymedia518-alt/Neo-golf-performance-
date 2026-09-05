from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.round_update_r2 import PlayerR2SimInput, simulate_post_round2

GAME_CODE = "2026120001"
N_SIMULATIONS = 100000
SEED = 20260906

CONTENT = ROOT / "content" / "website_v2"
GT = ROOT / "outputs" / "ground_truth_diagnostic" / "comparison_table.csv"
OUTDIR = ROOT / "outputs" / "ok_open_post_r2"
OUT_JSON = CONTENT / "OK_OPEN_2026_POST_R2_FINAL_FORECAST.json"
OUT_CSV = OUTDIR / "OK_OPEN_2026_POST_R2_FINAL_FORECAST.csv"

R1_PATH = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"
R2_PATH = CONTENT / "OK_OPEN_2026_R2_LIVE_SNAPSHOT.json"
PRE_PATH = CONTENT / "OK_OPEN_2026_POST_R2_INPUT.json"
PROFILE_PATH = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().upper().replace("+", "")
    if s in ("", "-", "E", "EVEN"):
        return 0.0 if s in ("E", "EVEN") else None
    try:
        return float(s)
    except ValueError:
        return None

r1 = load_json(R1_PATH)
r2 = load_json(R2_PATH)
pre = load_json(PRE_PATH)
perf = load_json(PROFILE_PATH)

r1_by = {str(x["player_id"]): x for x in r1["player_table"]}
r2_by = {str(x["player_id"]): x for x in r2["player_table"]}
pre_by = {str(x["player_id"]): x for x in pre["records"]}
profile_by = {str(x["player_id"]): x for x in perf["profiles"]}

with GT.open(encoding="utf-8-sig", newline="") as f:
    gt_rows = list(csv.DictReader(f))

finalists = [
    r for r in gt_rows
    if r.get("final_ground_truth_status") == "MADE_CUT_CONFIRMED"
]

if len(finalists) != 68:
    raise SystemExit(f"HARD_STOP: expected 68 official finalists, got {len(finalists)}")

def expected_round(profile):
    """
    PRE-only performance expectation.
    Prefer recent5 SG total, then recent10, then multi-season.
    SG > 0 means better than field, therefore expected score-to-par
    adjustment is negative.
    """
    windows = profile.get("windows") or {}
    for key in ("recent5", "recent10", "multi_season"):
        w = windows.get(key) or {}
        total = ((w.get("components") or {}).get("total") or {})
        mean = num(total.get("mean"))
        if mean is not None:
            return -mean, key
    return 0.0, "population_fallback"

def spread_for(profile):
    c = profile.get("consistency") or {}
    for key in ("legacy_sample_sd", "population_sd_research"):
        v = num(c.get(key))
        if v is not None and v > 0:
            return max(v, 0.5), key
    windows = profile.get("windows") or {}
    for key in ("multi_season", "recent10", "recent5"):
        total = (((windows.get(key) or {}).get("components") or {}).get("total") or {})
        for sk in ("sample_sd", "population_sd"):
            v = num(total.get(sk))
            if v is not None and v > 0:
                return max(v, 0.5), f"{key}.{sk}"
    return 3.0, "population_fallback"

sim_inputs = []
audit = []
missing = []

for g in finalists:
    pid = str(g["player_code"])
    rr1 = r1_by.get(pid)
    rr2 = r2_by.get(pid)
    pp = profile_by.get(pid)

    if rr1 is None or rr2 is None or pp is None:
        missing.append({
            "player_id": pid,
            "name": g.get("official_name"),
            "r1": rr1 is not None,
            "r2": rr2 is not None,
            "profile": pp is not None,
        })
        continue

    r1_score = num(rr1.get("today_under_par"))
    if r1_score is None:
        r1_score = num(rr1.get("total_under_par"))

    r2_score = num(rr2.get("today_under_par_display"))
    r2_total = num(rr2.get("total_under_par_display"))

    if r2_score is None and r2_total is not None and r1_score is not None:
        r2_score = r2_total - r1_score

    if r1_score is None or r2_score is None:
        missing.append({
            "player_id": pid,
            "name": g.get("official_name"),
            "reason": "score missing",
        })
        continue

    expected, expected_source = expected_round(pp)
    spread, spread_source = spread_for(pp)

    sim_inputs.append(
        PlayerR2SimInput(
            player_code=pid,
            player_name=g["official_name"],
            expected_round_score_to_par=expected,
            spread=spread,
            r1_score_to_par=r1_score,
            r2_score_to_par=r2_score,
            made_cut=True,
        )
    )

    audit.append({
        "player_id": pid,
        "player_name": g["official_name"],
        "r1_score_to_par": r1_score,
        "r2_score_to_par": r2_score,
        "r2_total_to_par": r1_score + r2_score,
        "expected_final_round_to_par": expected,
        "expected_source": expected_source,
        "spread": spread,
        "spread_source": spread_source,
        "pre_win_probability": pre_by.get(pid, {}).get("win_probability"),
    })

if missing:
    print(json.dumps(missing, ensure_ascii=False, indent=2))
    raise SystemExit(f"HARD_STOP: {len(missing)} finalist input(s) missing")

if len(sim_inputs) != 68:
    raise SystemExit(f"HARD_STOP: simulation field != 68 ({len(sim_inputs)})")

rng = random.Random(SEED)

result = simulate_post_round2(
    sim_inputs,
    remaining_rounds=1,
    n_simulations=N_SIMULATIONS,
    rng=rng,
)

rows = []
audit_by = {x["player_id"]: x for x in audit}

for inp in sim_inputs:
    pid = inp.player_code
    s = result[pid]
    a = audit_by[pid]

    rows.append({
        **a,
        "win_pct": float(s["win_pct"]),
        "top5_pct": float(s["top5_pct"]),
        "top10_pct": float(s["top10_pct"]),
        "top20_pct": float(s["top20_pct"]),
    })

rows.sort(
    key=lambda x: (
        -x["win_pct"],
        -x["top5_pct"],
        x["r2_total_to_par"],
        x["player_name"],
    )
)

for i, row in enumerate(rows, 1):
    row["neo_final_rank"] = i

win_sum = sum(x["win_pct"] for x in rows)

payload = {
    "schema_version": 1,
    "artifact": "OK_OPEN_2026_POST_R2_FINAL_FORECAST",
    "game_code": GAME_CODE,
    "tournament_name": "OK저축은행 읏맨 오픈",
    "stage": "POST_R2_PRE_FINAL",
    "final_round_number": 3,
    "remaining_rounds": 1,
    "official_final_field_size": 68,
    "field_source": str(GT.relative_to(ROOT)).replace("\\", "/"),
    "pre_model_version": pre.get("model_version"),
    "pre_cutoff": pre.get("pre_cutoff"),
    "future_data_excluded": True,
    "simulation_engine": "klpga.neo_win.round_update_r2.simulate_post_round2",
    "n_simulations": N_SIMULATIONS,
    "seed": SEED,
    "win_probability_sum_pct": win_sum,
    "records": rows,
}

OUTDIR.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

fields = [
    "neo_final_rank",
    "player_id",
    "player_name",
    "r1_score_to_par",
    "r2_score_to_par",
    "r2_total_to_par",
    "expected_final_round_to_par",
    "spread",
    "pre_win_probability",
    "win_pct",
    "top5_pct",
    "top10_pct",
    "top20_pct",
]

with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for row in rows:
        w.writerow({k: row.get(k) for k in fields})

print()
print("=== OK OPEN POST-R2 -> FINAL FORECAST ===")
print("GAME:", GAME_CODE)
print("FINAL FIELD:", len(rows))
print("REMAINING ROUNDS: 1")
print("SIMULATIONS:", N_SIMULATIONS)
print("WIN SUM:", round(win_sum, 6))
print("FUTURE DATA EXCLUDED:", payload["future_data_excluded"])
print()

print("TOP 20")
print("-" * 105)
print(f"{'#':>2} {'PLAYER':<12} {'R2':>5} {'WIN':>8} {'TOP5':>8} {'TOP10':>8} {'TOP20':>8}")
print("-" * 105)

for row in rows[:20]:
    print(
        f"{row['neo_final_rank']:>2} "
        f"{row['player_name']:<12} "
        f"{row['r2_total_to_par']:>+5.0f} "
        f"{row['win_pct']:>7.2f}% "
        f"{row['top5_pct']:>7.2f}% "
        f"{row['top10_pct']:>7.2f}% "
        f"{row['top20_pct']:>7.2f}%"
    )

print()
print("JSON:", OUT_JSON)
print("CSV :", OUT_CSV)
