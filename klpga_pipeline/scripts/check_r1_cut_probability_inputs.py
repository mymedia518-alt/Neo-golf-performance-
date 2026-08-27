"""TEMPORARY, READ-ONLY verification script — inspects the real, already-
stored input feature values behind post_r1_make_cut_pct for a fixed set
of player_codes, so a large probability spread among same-1R-score
players can be explained from actual stored data (never guessed).

Reads only two already-existing files, writes nothing, modifies no
model/prediction/frozen artifact, collects no new data:
  - neo_win_c_predictions/2026/neo_win_c_001-C-FINAL_2026080001.json
  - outputs/beta001_r1/BETA001_R1_FULL.csv

Usage:
    python scripts/check_r1_cut_probability_inputs.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE_PATH = ROOT / "neo_win_c_predictions" / "2026" / "neo_win_c_001-C-FINAL_2026080001.json"
R1_CSV_PATH = ROOT / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv"

CODES = ["11770", "8840", "11134", "11485", "8284", "10563"]


def main() -> int:
    pre = json.loads(PRE_PATH.read_text(encoding="utf-8"))
    pre_by_code = {p["player_code"]: p for p in pre["predictions"]}

    r1_by_code: dict[str, dict] = {}
    with open(R1_CSV_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            r1_by_code[row["player_code"]] = row

    for code in CODES:
        p = pre_by_code.get(code)
        r = r1_by_code.get(code)
        print(f"=== player_code={code} ===")
        if p is None:
            print("  NOT FOUND in frozen PRE snapshot")
            print()
            continue
        print(f"  player_name (PRE): {p['player_name']!r}")
        print(f"  player_name (R1 CSV): {(r['player_name'] if r else 'N/A')!r}")
        print(f"  r1_score_to_par: {r['r1_score_to_par'] if r else 'N/A'}")
        fv = p.get("feature_values", {})
        print("  feature_values (ALL keys actually stored, real values only):")
        for k, v in fv.items():
            print(f"    {k}: {v!r}")
        print(f"  post_r1_make_cut_pct: {r['post_r1_make_cut_pct'] if r else 'N/A'}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
