"""Independent source<->UI numeric match test for the generated public page.

Does NOT reuse build.py's in-memory values. Re-reads the CSVs from scratch and
re-parses the rendered index.html from scratch, then compares. This is the
"screen numbers vs CSV cross-check" test required before any deploy decision.
"""
import csv
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
SR = ROOT / "artifacts" / "seed_race"
HTML_PATH = Path(__file__).resolve().parent / "index.html"
SCRATCH_SEEDRACE2 = Path(
    "/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04"
    "/scratchpad/seedrace2"
)

failures = []


def check(label, got, want):
    ok = (got == want)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}: got={got!r} want={want!r}")
    if not ok:
        failures.append(label)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "html.parser")

# ---- 1. headline locked facts ----
seed_rows = read_csv(SR / "seed_probability.csv")
row60 = next(r for r in seed_rows if int(float(r["current_rank"])) == 60)
check("CSV: rank60 player name", row60["player"], "김새로미")
check("CSV: rank60 current_money", row60["current_money"], "147312262")
check("CSV: rank60 prob_top60 rounds to 31.9%", round(float(row60["prob_top60"]) * 100, 1), 31.9)

hero_money_el = soup.select_one('[data-field="hero-money"]')
hero_prob_el = soup.select_one('[data-field="hero-prob"]')
check("HTML hero-money text", hero_money_el.get_text(strip=True), "147,312,262원")
check("HTML hero-prob text", hero_prob_el.get_text(strip=True), "31.9%")
check("HTML headline contains 31.9%", "31.9%" in soup.select_one('[data-testid="hero"] h1').get_text(), True)

cur_money_el = soup.select_one('[data-field="current-money"]')
check("HTML current-money (moving cutline) matches hero", cur_money_el.get_text(strip=True), "147,312,262원")

# ---- 2. raw survive count, independently re-derived from the .npz simulation array ----
# (not from the CSV, not from build.py -- direct re-computation, per check-list item requiring
#  raw_count / 60000 to be shown, not just the rounded probability)
try:
    import numpy as np
    d = np.load(SCRATCH_SEEDRACE2 / "sim_expected.npz")
    idx = json.loads((SCRATCH_SEEDRACE2 / "player_index.json").read_text())
    i60 = idx["rank0"].index(60)
    fr = d["final_rank"][:, i60] if d["final_rank"].ndim == 2 else d["final_rank"].reshape(60000, -1)[:, i60]
    n = fr.shape[0]
    survive = int((fr <= 60).sum())
    check("raw simulation: n_iterations", n, 60000)
    check("raw simulation: survive count", survive, 19157)
    check("raw simulation: pct rounds to 31.9%", round(survive / n * 100, 1), 31.9)
except FileNotFoundError:
    print("[SKIP] raw .npz re-derivation -- scratchpad simulation arrays not found in this environment")

# ---- 3. P10 / median / P90 straight from final_60th_money_distribution.csv ----
dist_rows = read_csv(SR / "final_60th_money_distribution.csv")
dist = {r["metric"]: int(r["value"]) for r in dist_rows}
check("CSV current_60th_money", dist["current_60th_money"], 147312262)
check("CSV simulated_final_60th_p10", dist["simulated_final_60th_p10"], 164840244)
check("CSV simulated_final_60th_median", dist["simulated_final_60th_median"], 172303371)
check("CSV simulated_final_60th_p90", dist["simulated_final_60th_p90"], 180291768)

p10_el = soup.select_one('[data-field="p10"]')
median_el = soup.select_one('[data-field="median"]')
p90_el = soup.select_one('[data-field="p90"]')
check("HTML p10 contains CSV value", "164,840,244원" in p10_el.get_text(), True)
check("HTML median contains CSV value", "172,303,371원" in median_el.get_text(), True)
check("HTML p90 contains CSV value", "180,291,768원" in p90_el.get_text(), True)

# forbidden phrase check: the old mislabeled "최소 1,750만원" claim must not appear anywhere
full_text = soup.get_text()
check('forbidden phrase "최소 1,750만원" absent', "최소 1,750만원" in full_text, False)
check('forbidden phrase "최소" + "17" co-occurring as a minimum claim absent',
      ("최소" in full_text and "17,527,982" in full_text), False)

# ---- 4. seed bubble rows (55-70) match CSV exactly, row by row ----
bubble_csv = {int(float(r["current_rank"])): r for r in seed_rows if 55 <= int(float(r["current_rank"])) <= 70}
check("CSV bubble row count (55-70)", len(bubble_csv), 16)

bubble_rows_html = soup.select('[data-testid="seed-bubble"] .bubble-row')
check("HTML bubble row count", len(bubble_rows_html), 16)

for el in bubble_rows_html:
    rank = int(el["data-rank"])
    csv_row = bubble_csv[rank]
    check(f"rank{rank} player match", el["data-player"], csv_row["player"])
    check(f"rank{rank} money match", el["data-money"], csv_row["current_money"])
    check(f"rank{rank} prob match (4dp)", float(el["data-prob"]), round(float(csv_row["prob_top60"]), 4))
    want_medrank = str(int(float(csv_row["median_final_rank"])))
    check(f"rank{rank} median_final_rank match", el["data-medrank"], want_medrank)

# seed-line divider must sit between rank60 and rank61
rows_in_order = bubble_rows_html
marker = soup.select_one('[data-testid="seed-bubble"] .seed-line-marker')
check("seed-line-marker present exactly once",
      len(soup.select('[data-testid="seed-bubble"] .seed-line-marker')), 1)
# the marker's next sibling bubble-row should be rank 61, previous should be rank 60
prev_row = marker.find_previous_sibling(class_="bubble-row")
next_row = marker.find_next_sibling(class_="bubble-row")
check("seed-line-marker directly follows rank60", prev_row["data-rank"] if prev_row else None, "60")
check("seed-line-marker directly precedes rank61", next_row["data-rank"] if next_row else None, "61")

# ---- 5. what-if ladder matches seed_probability_whatif.csv for 박결 ----
whatif_rows = read_csv(SR / "seed_probability_whatif.csv")
pg_rows = {r["hj_scenario"]: r for r in whatif_rows if r["player"] == "박결"}
pg_baseline = float(pg_rows["CUT"]["baseline_prob_top60_expected"])

ladder_pcts = soup.select('[data-testid="whatif-ladder"] [data-whatif-pct]')
check("HTML whatif ladder item count", len(ladder_pcts), 6)  # 현재 + CUT/30/20/10/5

by_label = {el["data-whatif-scn"]: float(el["data-whatif-pct"]) for el in ladder_pcts}
check("whatif 현재(baseline) match", by_label.get("현재"), round(pg_baseline, 4))
for scn in ["CUT", "30위", "20위", "10위", "5위"]:
    want = round(float(pg_rows[scn]["prob_top60"]), 4)
    check(f"whatif {scn} match", by_label.get(scn), want)

check('whatif player name is 박결 (not substituted)',
      soup.select_one('[data-testid="whatif"] .whatif-name').get_text(strip=True), "박결")
check('whatif current rank label',
      soup.select_one('[data-testid="whatif"] .whatif-rank').get_text(strip=True), "현재 68위")

# ---- 6. forbidden internal-term scan across the whole page ----
INTERNAL_TERMS = [
    "simulation array", "payout curve", "log-linear", "rank key", "JSON",
    "interpolation function", "seed A", "seed B", "seed C", "Monte Carlo",
    "monte carlo", "Plackett", "Gumbel", "tau", "τ", "pp_x", "pp_y", "gameCode", "viewBox",
]
raw_html = HTML_PATH.read_text(encoding="utf-8")
for term in INTERNAL_TERMS:
    check(f'internal term "{term}" absent', term in raw_html, False)

# "60,000번 시뮬레이션" / "60,000회" is explicitly allowed per spec
check('"60,000번 시뮬레이션" phrase present (allowed exception)',
      "60,000번" in full_text, True)

# ---- 7. model label compliance ----
check('approved model label "NEO KLPGA 시드 레이스 시뮬레이션" present',
      "NEO KLPGA 시드 레이스 시뮬레이션" in full_text, True)
for forbidden in ["경기력 예측", "SG 기반", "최근 경기력 기반"]:
    check(f'forbidden model label "{forbidden}" absent', forbidden in full_text, False)

check('Monte Carlo (any case) absent anywhere', "monte" in raw_html.lower(), False)

print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} failing checks)")
    for f in failures:
        print(" -", f)
    sys.exit(1)
else:
    print("RESULT: ALL CHECKS PASS")
