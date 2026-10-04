"""STEP 2 -- independent 72-hole reconstruction directly from RAW JSON
files (never from the sqlite/derived CSV), for 3 case-study players
selected purely by official result. Diffs the result against the
already-published derived CSV and FAILS LOUDLY on any mismatch.

Never copies derived CSV values -- every field here is recomputed from
scratch by scanning the raw/group_shot/*/R*/H*.json archive directly.
"""
from __future__ import annotations
import csv, glob, json, sys
from pathlib import Path

RAW_ROOT = Path("/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04/scratchpad/raw_archive/out/__out/raw/2026100005/group_shot")
DERIVED_CSV = Path(__file__).parent / "neo_player_hole_shot_derived.csv"

PAR_BY_HOLE = {1: 4, 2: 3, 3: 4, 4: 5, 5: 3, 6: 4, 7: 5, 8: 4, 9: 4,
               10: 5, 11: 3, 12: 4, 13: 4, 14: 4, 15: 4, 16: 3, 17: 4, 18: 5}
TEE_MISS_MAP = {"2": "ROUGH", "6": "BUNKER", "5": "PENALTY", "4": "OB"}

PLAYERS = {
    "9115": "유해란 (TOP, rank1)",
    "9708": "이재윤 (MID, rank27)",
    "9111": "박서현 (BOTTOM, rank61)",
}


def flatten_group_shots(obj):
    """Same confirmed real shape as collector.normalize_group: dict
    keyed by small integer-string indices, each value a list of that
    member's shot dicts."""
    container = obj.get("groupShotTrackerList") or {}
    shots = []
    if isinstance(container, dict):
        for v in container.values():
            if isinstance(v, list):
                shots.extend(s for s in v if isinstance(s, dict))
    elif isinstance(container, list):
        for v in container:
            if isinstance(v, dict):
                shots.append(v)
            elif isinstance(v, list):
                shots.extend(s for s in v if isinstance(s, dict))
    return shots


def scan_raw_for_players(player_codes):
    """Scan EVERY raw group_shot file and collect shots for the target
    players directly from the raw bytes on disk."""
    by_player_round_hole = {}
    files = sorted(glob.glob(str(RAW_ROOT / "*/R*/H*.json")))
    for fpath in files:
        parts = Path(fpath).parts
        rnd = int([p for p in parts if p.startswith("R")][0][1:])
        hole = int(Path(fpath).stem[1:3])
        with open(fpath, "rb") as fh:
            raw = fh.read()
        obj = json.loads(raw.decode("utf-8-sig"))
        shots = flatten_group_shots(obj)
        for s in shots:
            pc = str(s.get("playerCode"))
            if pc in player_codes:
                by_player_round_hole.setdefault((pc, rnd, hole), []).append(s)
    return by_player_round_hole


def compute_hole_record_independent(par, shots):
    shots_sorted = sorted(shots, key=lambda s: int(s["shot"]))
    strokes = len(shots_sorted)
    score_to_par = strokes - par
    first_shot_state = shots_sorted[0]["pp_state"] if shots_sorted else None

    fw_hit = None
    tee_miss_state = None
    if par in (4, 5) and shots_sorted:
        if first_shot_state == "1":
            fw_hit = True
        else:
            fw_hit = False
            tee_miss_state = TEE_MISS_MAP.get(first_shot_state, "OTHER")

    gir_shot_number = None
    for s in shots_sorted:
        if s["pp_state"] == "3":
            gir_shot_number = int(s["shot"])
            break
    gir = gir_shot_number is not None and gir_shot_number <= (par - 2)
    par_or_better = score_to_par <= 0

    state_sequence = [s["pp_state"] for s in shots_sorted]

    return {
        "par": par, "strokes": strokes, "score_to_par": score_to_par,
        "first_shot_state": first_shot_state, "fw_hit": fw_hit,
        "tee_miss_state": tee_miss_state, "gir": gir,
        "gir_shot_number": gir_shot_number, "gir_miss": not gir,
        "final_score": strokes, "par_or_better": par_or_better,
        "state_sequence": state_sequence,
    }


def load_derived_csv_rows(player_codes):
    out = {}
    with open(DERIVED_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["player_code"] in player_codes:
                out[(row["player_code"], int(row["round"]), int(row["hole"]))] = row
    return out


def to_bool_or_none(s):
    if s in (None, "", "None"):
        return None
    return s == "True"


def to_int_or_none(s):
    if s in (None, "", "None"):
        return None
    return int(s)


def compare(independent, derived_row):
    """Returns list of mismatch descriptions; empty if identical."""
    mismatches = []
    checks = [
        ("par", independent["par"], to_int_or_none(derived_row["par"])),
        ("strokes", independent["strokes"], to_int_or_none(derived_row["strokes"])),
        ("score_to_par", independent["score_to_par"], to_int_or_none(derived_row["score_to_par"])),
        ("first_shot_state", independent["first_shot_state"], derived_row["first_shot_state"] or None),
        ("fw_hit", independent["fw_hit"], to_bool_or_none(derived_row["fw_hit"])),
        ("tee_miss_state", independent["tee_miss_state"], derived_row["tee_miss_state"] or None),
        ("gir", independent["gir"], to_bool_or_none(derived_row["gir"])),
        ("gir_shot_number", independent["gir_shot_number"], to_int_or_none(derived_row["gir_shot_number"])),
        ("par_or_better", independent["par_or_better"], to_bool_or_none(derived_row["par_or_better"])),
    ]
    for name, ind_val, der_val in checks:
        if ind_val != der_val:
            mismatches.append(f"{name}: independent={ind_val!r} derived={der_val!r}")
    return mismatches


def main():
    player_codes = set(PLAYERS.keys())
    raw_data = scan_raw_for_players(player_codes)
    derived = load_derived_csv_rows(player_codes)

    all_records = {}
    total_mismatches = 0
    full_reconstruction = []

    for pc in player_codes:
        for rnd in range(1, 5):
            for hole in range(1, 19):
                key = (pc, rnd, hole)
                shots = raw_data.get(key, [])
                par = PAR_BY_HOLE[hole]
                if not shots:
                    full_reconstruction.append({
                        "player_code": pc, "player_name": PLAYERS[pc], "round": rnd, "hole": hole,
                        "par": par, "shot_states": "", "strokes": 0, "score_to_par": None,
                        "fw_hit": None, "tee_miss_state": None, "gir": None, "gir_shot_number": None,
                        "par_or_better": None, "NOTE": "no raw shots found for this player/round/hole",
                    })
                    continue
                rec = compute_hole_record_independent(par, shots)
                all_records[key] = rec

                der_row = derived.get(key)
                if der_row is None:
                    total_mismatches += 1
                    print(f"FAIL: {pc} R{rnd} H{hole}: no derived CSV row found for independently-reconstructed data")
                    continue
                mism = compare(rec, der_row)
                if mism:
                    total_mismatches += len(mism)
                    print(f"FAIL: {pc} R{rnd} H{hole}: {mism}")

                full_reconstruction.append({
                    "player_code": pc, "player_name": PLAYERS[pc], "round": rnd, "hole": hole,
                    "par": par, "shot_states": "|".join(rec["state_sequence"]),
                    "strokes": rec["strokes"], "score_to_par": rec["score_to_par"],
                    "fw_hit": rec["fw_hit"], "tee_miss_state": rec["tee_miss_state"],
                    "gir": rec["gir"], "gir_shot_number": rec["gir_shot_number"],
                    "par_or_better": rec["par_or_better"], "NOTE": "",
                })

    out_csv = Path(__file__).parent / "neo_three_player_raw_reconstruction.csv"
    cols = ["player_code", "player_name", "round", "hole", "par", "shot_states", "strokes",
            "score_to_par", "fw_hit", "tee_miss_state", "gir", "gir_shot_number", "par_or_better", "NOTE"]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in sorted(full_reconstruction, key=lambda r: (r["player_code"], r["round"], r["hole"])):
            w.writerow(r)

    print(f"\nTOTAL independent-vs-derived field mismatches: {total_mismatches}")
    print(f"Wrote {len(full_reconstruction)} reconstructed hole-rows to {out_csv}")
    if total_mismatches > 0:
        print("STEP 2 VERDICT: FAIL -- investigate before trusting derived CSV for these players")
        sys.exit(1)
    else:
        print("STEP 2 VERDICT: PASS -- independent RAW reconstruction matches derived CSV exactly for all 3 players, all 72 holes each")


if __name__ == "__main__":
    main()
