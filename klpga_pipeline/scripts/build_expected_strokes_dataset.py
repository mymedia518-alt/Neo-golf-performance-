"""NEO Expected Strokes -- Phase 1 dataset builder (read-only, no network).

Builds the shot-level transition dataset (Task A), runs the state-
continuity check (Task B), reports the real lie taxonomy gaps (Task C),
and prints lie/par distributions (Task E) directly from the collected
cmpro shot_event/hole_audit warehouse. Opens the SQLite strictly
read-only (`file:<path>?mode=ro`) and never writes to it, never
re-collects, never makes a network call.

Task D (first-shot start state) is intentionally NOT estimated here --
see [FIRST-SHOT START STATE] in this script's own printed output: no
official course/hole yardage source exists anywhere in this repo for
any tournament (confirmed by klpga.neo_win.final_course_deep_dive's own
BLOCKED contract), so every first shot's start_distance_yd/start_lie
stays exactly what the DB already has (None/"티") -- never back-derived
from shot_distance+remaining_distance, per explicit instruction.

Usage (from klpga_pipeline/):
    py scripts/build_expected_strokes_dataset.py --game 2026090002
Optional real per-hole par/official-score evidence (never fetched by
this script -- point it at a file you already have):
    --official-score-source <scoreRecord HTML> --official-score-rounds round-one,round-two,...
Output:
    --out <csv path>   (default: data/expected_strokes_<game>_transitions.csv)
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klpga.collectors.score_record import parse_score_record_hole_by_hole, parse_score_record_hole_par
from klpga.expected_strokes.investigations import (
    blank_lie_investigation,
    bunker_investigation,
    model_eligibility_summary,
    zero_distance_ambiguous_detail,
)
from klpga.expected_strokes.transitions import (
    LIE_TAXONOMY,
    build_transition_dataset,
    check_state_continuity,
    lie_distribution,
    par_distribution,
    taxonomy_gaps,
)

_ROUND_TAB_TO_NUMBER = {"round-one": 1, "round-two": 2, "round-three": 3, "round-four": 4}


def find_by_name(filename: str, search_root: Path):
    for dirpath, dirnames, filenames in os.walk(search_root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv")]
        if filename in filenames:
            return Path(dirpath) / filename
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="2026090002")
    ap.add_argument("--sqlite", type=Path, default=None)
    ap.add_argument("--search-root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--official-score-source", type=Path, default=None)
    ap.add_argument("--official-score-rounds", default="round-one,round-two,round-three,round-four")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    pipeline_root = Path(__file__).resolve().parents[1]
    default_sqlite = pipeline_root / "data" / f"cmpro_{a.game}_full.sqlite"
    sqlite_path = a.sqlite or default_sqlite
    if not sqlite_path.is_file():
        found = find_by_name(f"cmpro_{a.game}_full.sqlite", a.search_root)
        sqlite_path = found if found else sqlite_path

    print("[FILE LOCATIONS]")
    print("sqlite =", sqlite_path, "exists=", sqlite_path.is_file())
    if not sqlite_path.is_file():
        print("BLOCKED: sqlite file not found.")
        raise SystemExit(1)

    conn = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)

    par_by_round_hole: dict = {}
    official_score_by_player_round_hole: dict = {}
    if a.official_score_source and a.official_score_source.is_file():
        html = a.official_score_source.read_text(encoding="utf-8")
        for tab_id in [r.strip() for r in a.official_score_rounds.split(",") if r.strip()]:
            rnd = _ROUND_TAB_TO_NUMBER.get(tab_id)
            if rnd is None:
                continue
            try:
                par = parse_score_record_hole_par(html, round_tab_id=tab_id)
                for h, p in par.items():
                    par_by_round_hole[(rnd, h)] = p
            except ValueError as exc:
                print(f"  par {tab_id} -> BLOCKED: {exc}")
            try:
                rows = parse_score_record_hole_by_hole(html, round_tab_id=tab_id)
                for row in rows:
                    for h, score in row["holes"].items():
                        if score is not None:
                            official_score_by_player_round_hole[(row["player_name"], rnd, h)] = score
            except ValueError as exc:
                print(f"  official scores {tab_id} -> BLOCKED: {exc}")

    rows = build_transition_dataset(
        conn, a.game,
        par_by_round_hole=par_by_round_hole or None,
        official_score_by_player_round_hole=official_score_by_player_round_hole or None,
    )

    print("\n[TRANSITION DATASET]")
    print("total_shot_rows =", len(rows))
    print("distinct_holes =", len({(r.player_code, r.round_number, r.hole) for r in rows}))
    rows_with_par = sum(1 for r in rows if r.par is not None)
    rows_with_official_score = sum(1 for r in rows if r.official_hole_score is not None)
    print("rows_with_par =", rows_with_par, "/ rows_with_official_hole_score =", rows_with_official_score)

    out_path = a.out or (pipeline_root / "data" / f"expected_strokes_{a.game}_transitions.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["game_code", "player_code", "player_name", "round", "hole", "shot_no", "par",
                    "start_distance_yd", "start_lie", "end_distance_yd", "end_lie", "holed",
                    "zero_distance_ambiguous", "official_hole_score"])
        for r in rows:
            w.writerow([r.game_code, r.player_code, r.player_name, r.round_number, r.hole, r.shot_no,
                        "" if r.par is None else r.par, "" if r.start_distance_yd is None else r.start_distance_yd,
                        r.start_lie, r.end_distance_yd, r.end_lie, r.holed, r.zero_distance_ambiguous,
                        "" if r.official_hole_score is None else r.official_hole_score])
    print("transition_dataset_csv =", out_path)

    print("\n[ZERO-DISTANCE / NON-HOLED CASES]")
    ambiguous = [r for r in rows if r.zero_distance_ambiguous]
    print("zero_distance_but_not_holed_lie_count =", len(ambiguous))
    print("player_code,player_name,round,hole,shot_no,end_lie")
    for r in ambiguous:
        print(f"{r.player_code},{r.player_name},{r.round_number},{r.hole},{r.shot_no},{r.end_lie}")
    print("NOT reinterpreted as HOLED -- holed is strict end_lie==\"홀인\" only, per operator instruction.")
    print("These rows keep holed=False in the CSV above; review manually before any modeling use.")

    print("\n[LIE TAXONOMY]")
    gaps = taxonomy_gaps(conn, a.game)
    print("distinct_start_lie (real DB values) =", gaps["distinct_start_lie"])
    print("distinct_end_lie (real DB values) =", gaps["distinct_end_lie"])
    print("unmapped_values (not covered by LIE_TAXONOMY) =", gaps["unmapped_values"])
    print("proposed_mapping =", LIE_TAXONOMY)

    print("\n[STATE CONTINUITY]")
    mismatches = check_state_continuity(rows)
    print("mismatch_count =", len(mismatches))
    for m in mismatches[:30]:
        print("   ", m)

    print("\n[FIRST-SHOT START STATE]")
    first_shots = [r for r in rows if r.shot_no == 1]
    print("first_shot_rows =", len(first_shots))
    print("first_shot_start_distance_all_none =", all(r.start_distance_yd is None for r in first_shots))
    print("first_shot_start_lie_all_tee =", all(r.start_lie == "티" for r in first_shots))
    print("No official course/hole yardage source exists anywhere in this repo (confirmed by")
    print("klpga.neo_win.final_course_deep_dive's own BLOCKED contract, checked for every game_code).")
    print("start_distance_yd for shot_no==1 is left exactly as the DB has it (None) -- never")
    print("back-derived from shot_distance_yd+end_distance_yd.")

    print("\n[DISTRIBUTION]")
    print("by_lie (raw lie value -> shots/min/p25/median/p75/max of start_distance_yd):")
    for lie, stats in lie_distribution(rows).items():
        print("  ", repr(lie), "->", stats)
    print("by_par:", par_distribution(rows))

    print("\n[BLANK-LIE INVESTIGATION]")
    print("(no single meaning inferred -- structured evidence only, per operator instruction)")
    blank = blank_lie_investigation(rows)
    print("start_blank_count =", blank["start_blank_count"], "/ end_blank_count =", blank["end_blank_count"])
    print("start_blank_by_shot_no =", blank["start_blank_by_shot_no"])
    print("end_blank_by_shot_no =", blank["end_blank_by_shot_no"])
    print("start_blank_by_par =", blank["start_blank_by_par"])
    print("end_blank_by_par =", blank["end_blank_by_par"])
    print("start_blank_by_previous_lie =", blank["start_blank_by_previous_lie"])
    print("end_blank_by_previous_lie =", blank["end_blank_by_previous_lie"])
    print("start_blank_by_next_lie =", blank["start_blank_by_next_lie"])
    print("end_blank_by_next_lie =", blank["end_blank_by_next_lie"])
    print("start_blank_distance_buckets =", blank["start_blank_distance_buckets"])
    print("end_blank_distance_buckets =", blank["end_blank_distance_buckets"])
    print("start_blank_top30_longest:")
    for ex in blank["start_blank_top30_longest"]:
        print("   ", ex)
    print("end_blank_top30_longest:")
    for ex in blank["end_blank_top30_longest"]:
        print("   ", ex)

    print("\n[BUNKER INVESTIGATION]")
    print("(hypothesis only, not a conclusion: start_lie for shot n is copied from shot n-1's")
    print("own end_lie by the collector -- klpga.collectors.cmpro_shots -- so a '벙커' START")
    print("reflects real state propagation from the previous shot's recorded end state, not")
    print("necessarily a parsing artifact. This does NOT by itself explain unexpectedly long")
    print("bunker-start distances; review the structured evidence below before concluding.)")
    bunker = bunker_investigation(rows)
    print("start_bunker_shots =", bunker["start_bunker_shots"])
    print("distance_stats =", bunker["distance_stats"])
    print("by_distance_bucket =", bunker["by_distance_bucket"])
    print("by_par =", bunker["by_par"])
    print("by_shot_no =", bunker["by_shot_no"])
    print("end_lie_distribution =", bunker["end_lie_distribution"])
    print("examples (sorted by start_distance_yd desc):")
    for ex in bunker["examples"]:
        print("   ", ex)

    print("\n[ZERO-DISTANCE AMBIGUOUS -- FULL DETAIL]")
    print("(the 17 real end_distance_yd==0.0 AND end_lie!='홀인' cases -- full context)")
    for d in zero_distance_ambiguous_detail(rows):
        print("   ", d)

    print("\n[MODEL-ELIGIBILITY SUMMARY]")
    print("(non-overlapping A-F classification -- no double counting; 2+ flags -> F with combination recorded)")
    elig = model_eligibility_summary(rows)
    for key, value in elig.items():
        print(f"{key} =", value)

    conn.close()


if __name__ == "__main__":
    main()
