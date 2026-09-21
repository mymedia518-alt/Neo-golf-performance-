"""NEO CMPRO FULL COLLECTION -- POST COLLECTION QA (read-only, no network).

Runs entirely against files already on disk:
  - the collected SQLite warehouse (opened strictly read-only, via
    `file:<path>?mode=ro`; this process never writes to it)
  - the manifest CSV produced by plan_cmpro_collection.py
  - PoliteHttpClient's on-disk playerScore cache (re-parsed, never
    re-fetched -- no network call is made anywhere in this script)

Never modifies the database, never re-collects, never requests
anything over the network. Intended to be run on the machine that
actually holds the collected data (this repo's own git history does
not and must not carry cmpro_<game>_full.sqlite -- it is a large,
per-machine, gitignored-by-convention artifact).

Usage (from klpga_pipeline/):
    py scripts/qa_cmpro_full_collection.py --game 2026090002
Optional overrides if the files aren't at the default data/ path:
    --sqlite <path> --manifest <path> --cache-dir <path>
    --search-root <path>   (default: this repo's root; used only if
                             the default/--sqlite/--manifest path
                             does not exist, to search by filename)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klpga.collectors.cmpro_shots import PLAYER_SCORE_ENDPOINT, parse_cmpro_played_holes

NAMED_NO_PLAYED_HOLES = {
    "9702": "김리안",
    "9136": "조혜림",
    "12706": "권은 0906(A)",
}
EXPECTED_STRUCTURE_BUCKETS = {0: 3, 18: 3, 36: 38, 54: 1, 72: 63}


def cache_key(url: str, params: dict) -> str:
    raw = url + "|" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def find_by_name(filename: str, search_root: Path) -> "Path | None":
    for dirpath, dirnames, filenames in os.walk(search_root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv")]
        if filename in filenames:
            return Path(dirpath) / filename
    return None


def locate(preferred: "Path | None", filename: str, search_root: Path) -> "Path | None":
    if preferred is not None and preferred.is_file():
        return preferred
    return find_by_name(filename, search_root)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="2026090002")
    ap.add_argument("--sqlite", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--search-root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--official-score-source", type=Path, default=None,
                     help="Optional: a JSON/CSV file with official per-hole scores, if you have one. "
                          "Without it, [SCORE CROSS CHECK] reports structure-only.")
    a = ap.parse_args()

    pipeline_root = Path(__file__).resolve().parents[1]
    default_sqlite = pipeline_root / "data" / f"cmpro_{a.game}_full.sqlite"
    default_manifest = pipeline_root / "data" / f"cmpro_{a.game}_manifest.csv"
    default_cache = pipeline_root / "cache" / "cmpro"

    sqlite_path = locate(a.sqlite or default_sqlite, f"cmpro_{a.game}_full.sqlite", a.search_root)
    manifest_path = locate(a.manifest or default_manifest, f"cmpro_{a.game}_manifest.csv", a.search_root)
    cache_dir = a.cache_dir or default_cache

    print("[FILE LOCATIONS]")
    print("sqlite   =", sqlite_path)
    print("manifest =", manifest_path)
    print("cache_dir=", cache_dir, "exists=", cache_dir.is_dir())

    if sqlite_path is None or not Path(sqlite_path).is_file():
        print("\nBLOCKED: sqlite file not found (checked default path and searched", a.search_root, "for the filename).")
        raise SystemExit(1)
    if manifest_path is None or not Path(manifest_path).is_file():
        print("\nBLOCKED: manifest CSV not found (checked default path and searched", a.search_root, "for the filename).")
        raise SystemExit(1)

    conn = sqlite3.connect(f"file:{Path(sqlite_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    game = a.game

    def q(sql, params=()):
        return conn.execute(sql, params).fetchall()

    def q1(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return row[0] if row is not None else None

    # ---------------------------------------------------------------
    print("\n[DATABASE]")
    print("shot_event_total_rows =", q1("SELECT COUNT(*) FROM shot_event"))
    print("hole_audit_total_rows =", q1("SELECT COUNT(*) FROM hole_audit"))
    print("shot_event_rows_for_game =", q1("SELECT COUNT(*) FROM shot_event WHERE game_code=?", (game,)))
    print("hole_audit_rows_for_game =", q1("SELECT COUNT(*) FROM hole_audit WHERE game_code=?", (game,)))

    print("hole_audit_qa_status_counts:")
    for row in q("SELECT qa_status, COUNT(*) c FROM hole_audit WHERE game_code=? GROUP BY qa_status ORDER BY c DESC", (game,)):
        print("  ", row["qa_status"], "=", row["c"])

    pass_holes = q1("SELECT COUNT(*) FROM hole_audit WHERE game_code=? AND qa_status='PASS'", (game,))
    print("PASS_hole_audit_rows =", pass_holes)

    zero_shot_pass = q("""
        SELECT ha.player_code, ha.round_number, ha.hole FROM hole_audit ha
        WHERE ha.game_code=? AND ha.qa_status='PASS'
        AND NOT EXISTS (SELECT 1 FROM shot_event se WHERE se.game_code=ha.game_code
            AND se.player_code=ha.player_code AND se.round_number=ha.round_number AND se.hole=ha.hole)
    """, (game,))
    print("zero_shot_PASS_holes =", len(zero_shot_pass))
    for r in zero_shot_pass[:20]:
        print("   ", dict(r))

    dup_shot_event = q("""
        SELECT game_code,player_code,round_number,hole,shot_no,COUNT(*) c FROM shot_event
        WHERE game_code=? GROUP BY game_code,player_code,round_number,hole,shot_no HAVING c>1
    """, (game,))
    dup_hole_audit = q("""
        SELECT game_code,player_code,round_number,hole,COUNT(*) c FROM hole_audit
        WHERE game_code=? GROUP BY game_code,player_code,round_number,hole HAVING c>1
    """, (game,))
    print("duplicate_shot_event_pk_violations =", len(dup_shot_event), "(should always be 0 -- shot_event's own PRIMARY KEY forbids this; checked anyway)")
    print("duplicate_hole_audit_pk_violations =", len(dup_hole_audit), "(should always be 0 -- hole_audit's own PRIMARY KEY forbids this; checked anyway)")

    print("round_number_range =", (q1("SELECT MIN(round_number) FROM hole_audit WHERE game_code=?", (game,)),
                                    q1("SELECT MAX(round_number) FROM hole_audit WHERE game_code=?", (game,))))
    print("hole_out_of_1_18_range_count =", q1("SELECT COUNT(*) FROM hole_audit WHERE game_code=? AND (hole<1 OR hole>18)", (game,)))

    neg_start = q1("SELECT COUNT(*) FROM shot_event WHERE game_code=? AND start_distance_yd<0", (game,))
    neg_end = q1("SELECT COUNT(*) FROM shot_event WHERE game_code=? AND end_distance_yd<0", (game,))
    print("negative_start_distance_count =", neg_start)
    print("negative_end_distance_count =", neg_end)

    continuity_gaps = []
    for row in q("SELECT player_code,round_number,hole FROM hole_audit WHERE game_code=?", (game,)):
        nums = [r["shot_no"] for r in q(
            "SELECT shot_no FROM shot_event WHERE game_code=? AND player_code=? AND round_number=? AND hole=? ORDER BY shot_no",
            (game, row["player_code"], row["round_number"], row["hole"]))]
        if nums != list(range(1, len(nums) + 1)):
            continuity_gaps.append((row["player_code"], row["round_number"], row["hole"], nums))
    print("shot_no_continuity_gap_holes =", len(continuity_gaps))
    for g in continuity_gaps[:20]:
        print("   ", g)

    non_holed = []
    for row in q("SELECT player_code,round_number,hole FROM hole_audit WHERE game_code=? AND qa_status='PASS'", (game,)):
        last = conn.execute(
            "SELECT end_distance_yd,end_lie FROM shot_event WHERE game_code=? AND player_code=? AND round_number=? AND hole=? ORDER BY shot_no DESC LIMIT 1",
            (game, row["player_code"], row["round_number"], row["hole"])).fetchone()
        if last is None:
            continue
        holed = (last["end_lie"] == "홀인") or (last["end_distance_yd"] == 0.0)
        if not holed:
            non_holed.append((row["player_code"], row["round_number"], row["hole"], last["end_distance_yd"], last["end_lie"]))
    print("PASS_holes_with_non_holed_last_shot =", len(non_holed))
    for r in non_holed[:20]:
        print("   ", r)

    mismatch_a = q1("SELECT COUNT(*) FROM shot_event WHERE game_code=? AND end_lie='홀인' AND end_distance_yd<>0.0", (game,))
    mismatch_b = q1("SELECT COUNT(*) FROM shot_event WHERE game_code=? AND end_distance_yd=0.0 AND end_lie<>'홀인'", (game,))
    print("holed_lie_but_nonzero_distance_count =", mismatch_a)
    print("zero_distance_but_not_holed_lie_count =", mismatch_b)

    # ---------------------------------------------------------------
    print("\n[MANIFEST COVERAGE]")
    with open(manifest_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        manifest_rows = list(reader)
        manifest_header = reader.fieldnames
    print("manifest_header =", manifest_header)
    print("manifest_player_count =", len(manifest_rows))

    per_player_planned = {}
    planned_total = 0
    for row in manifest_rows:
        code = row.get("player_code")
        try:
            ph = int(row.get("planned_holes", "") or 0)
        except ValueError:
            ph = None
        per_player_planned[code] = (ph, row.get("player_name"), row.get("rounds"))
        if ph:
            planned_total += ph
    print("manifest_planned_holes_sum =", planned_total)

    pass_by_player = defaultdict(int)
    for row in q("SELECT player_code, COUNT(*) c FROM hole_audit WHERE game_code=? AND qa_status='PASS' GROUP BY player_code", (game,)):
        pass_by_player[row["player_code"]] = row["c"]

    missing_players = [p for p in per_player_planned if per_player_planned[p][0] and pass_by_player.get(p, 0) == 0]
    extra_players_in_db = [p for p in pass_by_player if p not in per_player_planned]
    print("manifest_players_with_zero_PASS_in_db =", len(missing_players), missing_players[:20])
    print("db_players_not_in_manifest =", len(extra_players_in_db), extra_players_in_db[:20])

    under_planned, over_planned = [], []
    for p, (planned, name, rounds) in per_player_planned.items():
        if planned is None:
            continue
        actual = pass_by_player.get(p, 0)
        if actual < planned:
            under_planned.append((p, name, planned, actual, planned - actual))
        elif actual > planned:
            over_planned.append((p, name, planned, actual, actual - planned))
    print("total_missing_planned_holes (sum of shortfalls) =", sum(x[4] for x in under_planned))
    print("total_extra_holes_beyond_plan (sum of overages) =", sum(x[4] for x in over_planned))
    print("players_under_planned_holes =", len(under_planned))
    for x in under_planned[:30]:
        print("   ", x)
    print("players_over_planned_holes =", len(over_planned))
    for x in over_planned[:30]:
        print("   ", x)

    code_counts = defaultdict(int)
    for row in manifest_rows:
        code_counts[row.get("player_code")] += 1
    dup_manifest_rows = {k: v for k, v in code_counts.items() if v > 1}
    print("duplicate_player_codes_in_manifest =", dup_manifest_rows)

    # ---------------------------------------------------------------
    print("\n[PLAYER COVERAGE]")
    structure_buckets = defaultdict(int)
    per_player_report = []
    for p, (planned, name, rounds) in sorted(per_player_planned.items()):
        actual_pass = pass_by_player.get(p, 0)
        audit_holes = q1("SELECT COUNT(*) FROM hole_audit WHERE game_code=? AND player_code=?", (game, p))
        shot_count = q1("SELECT COUNT(*) FROM shot_event WHERE game_code=? AND player_code=?", (game, p))
        per_player_report.append((p, name, rounds, planned, audit_holes, actual_pass, shot_count))
        structure_buckets[planned] += 1
    print("distinct_players_in_db =", q1("SELECT COUNT(DISTINCT player_code) FROM hole_audit WHERE game_code=?", (game,)))
    print("planned_holes_bucket_counts (planned_holes -> #players) =", dict(sorted((k, v) for k, v in structure_buckets.items() if k is not None)))
    print("expected_bucket_counts_from_task_description =", EXPECTED_STRUCTURE_BUCKETS)
    print("\nplayer_code,player_name,rounds,planned_holes,audit_holes,PASS_holes,shot_count")
    for row in per_player_report:
        print(",".join("" if x is None else str(x) for x in row))

    # ---------------------------------------------------------------
    print("\n[NO PLAYED HOLES]")
    zero_planned_players = [p for p, (planned, name, rounds) in per_player_planned.items() if planned == 0]
    print("manifest_players_with_planned_holes_0 =", zero_planned_players)
    print("task_named_NO_PLAYED_HOLES_players =", NAMED_NO_PLAYED_HOLES)
    mismatch = set(zero_planned_players) ^ set(NAMED_NO_PLAYED_HOLES)
    if mismatch:
        print("WARNING: manifest's 0-planned-hole set differs from the task's named 3 players:", mismatch)

    for code in sorted(set(zero_planned_players) | set(NAMED_NO_PLAYED_HOLES)):
        name = per_player_planned.get(code, (None, NAMED_NO_PLAYED_HOLES.get(code), None))[1]
        params = {"gameCode": game, "playerCode": code, "lang": "kr"}
        key = cache_key(PLAYER_SCORE_ENDPOINT, params)
        cache_file = Path(cache_dir) / f"{key}.json"
        print(f"\n-- player {code} ({name}) --")
        print("expected_cache_file =", cache_file, "exists=", cache_file.is_file())
        if not cache_file.is_file():
            print("classification = UNVERIFIABLE (no cached playerScore response found for this exact URL+params -- cannot confirm the 0-hole claim from real evidence)")
            continue
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        html = raw.get("body_text", "")
        print("cached_url =", raw.get("url"))
        print("cached_params =", raw.get("params"))
        print("cached_html_length =", len(html))
        print("cached_html_head_200chars =", html[:200].replace("\n", " "))
        scope = parse_cmpro_played_holes(html)
        print("parsed_scope =", scope)
        stripped = html.strip()
        looks_empty_or_nonhtml = len(stripped) == 0 or ("<" not in stripped)
        has_any_score_markup = bool(re.search(r"_round\s*=|_hole\s*=", html))
        if scope:
            print("classification = MISMATCH (manifest says planned_holes=0 but the cached HTML actually parses to a non-empty scope -- re-run plan_cmpro_collection.py or investigate)")
        elif looks_empty_or_nonhtml:
            print("classification = FETCH_FAILED (cached body_text is empty or does not look like HTML at all)")
        elif not has_any_score_markup:
            print("classification = PARSE_FAILED_OR_STRUCTURE_CHANGED (real HTML body present, but it contains zero _round/_hole attributes anywhere -- cannot distinguish a genuine 0-hole player from a fragment whose shape parse_cmpro_played_holes doesn't recognize; inspect cached_html manually)")
        else:
            print("classification = NOT_APPLICABLE (real HTML with score-page markup present; genuinely zero round/hole entries found in it)")

    # ---------------------------------------------------------------
    print("\n[SHOT SANITY]")
    for row in q("SELECT shot_count, COUNT(*) c FROM hole_audit WHERE game_code=? GROUP BY shot_count ORDER BY shot_count", (game,)):
        label = f"{row['shot_count']} shot" + ("s" if row["shot_count"] != 1 else "")
        print(f"  {label}: {row['c']} holes")
    print("zero_shot_PASS (see [DATABASE]) =", len(zero_shot_pass))
    print("duplicate_shot_event_pk_violations (see [DATABASE]) =", len(dup_shot_event))
    print("shot_no_continuity_gap_holes (see [DATABASE]) =", len(continuity_gaps))
    print("negative_distance_total =", (neg_start or 0) + (neg_end or 0))
    print("non_holed_last_shot_on_PASS (see [DATABASE]) =", len(non_holed))
    excessive = q("SELECT player_code,round_number,hole,shot_count FROM hole_audit WHERE game_code=? AND shot_count>=8 ORDER BY shot_count DESC", (game,))
    print("holes_with_8_or_more_shots =", len(excessive))
    for r in excessive[:20]:
        print("   ", dict(r))
    repeated_shot = q("""
        SELECT player_code,round_number,hole,shot_no,COUNT(*) c FROM shot_event
        WHERE game_code=?
        GROUP BY player_code,round_number,hole,shot_no,end_distance_yd,end_lie,shot_distance_yd,start_distance_yd,start_lie
        HAVING c>1
    """, (game,))
    print("exact_duplicate_shot_rows =", len(repeated_shot))

    # ---------------------------------------------------------------
    print("\n[SCORE CROSS CHECK]")
    if a.official_score_source and a.official_score_source.is_file():
        print("official_score_source =", a.official_score_source, "(present -- extend this script's logic to parse it; not auto-implemented since its schema is unknown)")
    else:
        print("official_score_source = NOT PROVIDED")
        print("This branch (feat/cmpro-shot-data-v0) is rooted at an early scaffold commit and does not")
        print("contain any of the later official per-round/per-hole score artifacts for 2026090002 (those")
        print("live only on neo-website-v2 and its descendants). No official per-hole stroke source is")
        print("reachable from here, so a real matched/+1/+2/negative/PENALTY_REVIEW breakdown cannot be")
        print("computed by this script as-is.")
        print("cmpro's own per-hole shot_count is available above ([PLAYER COVERAGE] / [SHOT SANITY]) and")
        print("can be diffed against an official per-hole score file once you point --official-score-source")
        print("at one (or tell me its exact path/schema and I will extend this script).")

    conn.close()


if __name__ == "__main__":
    main()
