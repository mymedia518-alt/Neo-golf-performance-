"""EXPERIMENT 01A -- HANA TOP10 / 150-175 YARD LIE ANALYSIS
(read-only, no network, no DB writes, no model, no SG, no ranking).

Analyzes the OFFICIAL FINAL TOP 10 players (by real official rank, ties
preserved) of a real cmpro shot-level collection, restricted to shots
with 150.0 <= start_distance_yd <= 175.0, split by real raw start_lie
in {"페어웨이","러프","벙커"}. Purely descriptive counts/rates/averages
-- explicitly NOT Expected Strokes, NOT Strokes Gained, and never used
to rank player quality.

Inputs (exactly one of --sqlite / --transitions-csv; both are
READ ONLY -- this script never writes to either):
    --sqlite <path to cmpro_<game>_full.sqlite>
    --transitions-csv <path to the already-generated
        expected_strokes_<game>_transitions.csv from
        scripts/build_expected_strokes_dataset.py>
    --official-score-source <a real captured scoreRecord HTML page for
        this game, containing the FINAL round's own tab-pane>
    --final-round-tab <the real tab id for that final round, e.g.
        "round-four" for a 4-round event -- REQUIRED, never defaulted
        or guessed, per explicit instruction to use FINAL official
        ranking, never R3 or any predicted ranking>

Usage (from klpga_pipeline/):
    py scripts/experiment_01a_top10_150_175_lie_analysis.py \
        --game 2026090002 \
        --sqlite data/cmpro_2026090002_full.sqlite \
        --official-score-source <path to real scoreRecord HTML> \
        --final-round-tab round-four

This script is intentionally NOT committed to git (per explicit
instruction: no commit, no push, no merge for this experiment) -- save
it locally and run it against your real files.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klpga.collectors.score_record import parse_score_record_final_ranking
from klpga.expected_strokes.transitions import TransitionRow, build_transition_dataset

QUALIFYING_LIES = ("페어웨이", "러프", "벙커")
DIST_MIN, DIST_MAX = 150.0, 175.0


# ---------------------------------------------------------------
# Loading transition rows: from a real SQLite DB (read-only) or from
# the already-generated transitions CSV (also read-only, no
# re-derivation of any field).
# ---------------------------------------------------------------

def load_rows_from_sqlite(sqlite_path: Path, game_code: str) -> list[TransitionRow]:
    conn = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)
    try:
        return build_transition_dataset(conn, game_code)
    finally:
        conn.close()


def _to_bool(text: str) -> bool:
    return text.strip().lower() == "true"


def load_rows_from_csv(csv_path: Path) -> list[TransitionRow]:
    rows: list[TransitionRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(TransitionRow(
                game_code=r["game_code"], player_code=r["player_code"], player_name=r["player_name"],
                round_number=int(r["round"]), hole=int(r["hole"]), shot_no=int(r["shot_no"]),
                par=int(r["par"]) if r["par"] else None,
                start_distance_yd=float(r["start_distance_yd"]) if r["start_distance_yd"] else None,
                start_lie=r["start_lie"] or "",
                end_distance_yd=float(r["end_distance_yd"]),
                end_lie=r["end_lie"] or "",
                holed=_to_bool(r["holed"]),
                zero_distance_ambiguous=_to_bool(r["zero_distance_ambiguous"]),
                official_hole_score=int(r["official_hole_score"]) if r["official_hole_score"] else None,
            ))
    return rows


# ---------------------------------------------------------------
# OUTPUT 1: official Top10 from real final-round ranking.
# ---------------------------------------------------------------

@dataclass(frozen=True)
class Top10Entry:
    rank: int
    rank_display: str
    player_name: str
    total_to_par: Optional[int]
    total_raw_strokes: Optional[int]


def _numeric_rank(rank_display: str) -> Optional[int]:
    text = rank_display.strip().upper()
    if text.startswith("T"):
        text = text[1:]
    if text.isdigit():
        return int(text)
    return None


def official_top10(final_rows: list[dict]) -> tuple[list[Top10Entry], list[dict]]:
    """Returns (top10_entries, excluded_non_numeric_rows). A row is
    excluded from Top10 consideration (never silently dropped -- the
    excluded list is reported in OUTPUT 5) when its real rank_display
    has no parseable numeric rank (e.g. WD/DQ/DNS/CUT, or any other
    real text this page might show that isn't a plain or T-prefixed
    integer)."""
    entries: list[Top10Entry] = []
    excluded: list[dict] = []
    for row in final_rows:
        rank = _numeric_rank(row["rank_display"])
        if rank is None:
            excluded.append(row)
            continue
        entries.append(Top10Entry(
            rank=rank, rank_display=row["rank_display"], player_name=row["player_name"],
            total_to_par=row["total_to_par"], total_raw_strokes=row["total_raw_strokes"],
        ))
    entries.sort(key=lambda e: (e.rank, e.player_name))
    top10 = [e for e in entries if e.rank <= 10]
    return top10, excluded


# ---------------------------------------------------------------
# Name -> player_code join (same disclosed limitation as the SCORE
# CROSS CHECK work: the official page carries no player_code, only a
# real player_name -- joined against the real DB/CSV's own
# player_code<->player_name pairs).
# ---------------------------------------------------------------

def name_to_codes(rows: list[TransitionRow]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        out[r.player_name].add(r.player_code)
    return dict(out)


# ---------------------------------------------------------------
# Shot filter + per-hole grouping (for AVG_STROKES_TO_HOLE_AFTER_SHOT
# and terminal-integrity checking).
# ---------------------------------------------------------------

def group_by_hole(rows: list[TransitionRow]) -> dict[tuple[str, int, int], list[TransitionRow]]:
    groups: dict[tuple[str, int, int], list[TransitionRow]] = defaultdict(list)
    for r in rows:
        groups[(r.player_code, r.round_number, r.hole)].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r.shot_no)
    return groups


def qualifying_shots(rows: list[TransitionRow], lie: str) -> list[TransitionRow]:
    out = []
    for r in rows:
        if r.start_lie != lie:
            continue
        if r.start_distance_yd is None:
            continue  # missing start distance -- excluded, never guessed
        if not (DIST_MIN <= r.start_distance_yd <= DIST_MAX):
            continue
        out.append(r)
    return out


@dataclass(frozen=True)
class LieMetrics:
    n: int
    green_reach: int
    green_reach_rate: Optional[float]
    avg_remaining_yd: Optional[float]
    avg_remaining_denominator: int
    avg_remaining_excluded_unknown_end: int
    avg_strokes_after: Optional[float]
    avg_strokes_after_denominator: int
    terminal_integrity_failures: int


def compute_lie_metrics(shots: list[TransitionRow], hole_groups: dict) -> LieMetrics:
    n = len(shots)
    green_reach = sum(1 for s in shots if s.end_lie == "그린")
    green_reach_rate = (green_reach / n) if n > 0 else None

    valid_end = [s for s in shots if s.end_lie != ""]
    excluded_unknown_end = n - len(valid_end)
    avg_remaining_yd = (sum(s.end_distance_yd for s in valid_end) / len(valid_end)) if valid_end else None

    strokes_after_values: list[int] = []
    terminal_failures = 0
    seen_terminal_check: set[tuple[str, int, int]] = set()
    for s in shots:
        key = (s.player_code, s.round_number, s.hole)
        hole_rows = hole_groups[key]
        terminal = hole_rows[-1]
        if terminal.end_lie != "홀인":
            if key not in seen_terminal_check:
                terminal_failures += 1
                seen_terminal_check.add(key)
            continue  # exclude this qualifying shot from THIS metric only
        after = sum(1 for r in hole_rows if r.shot_no > s.shot_no)
        strokes_after_values.append(after)
    avg_strokes_after = (sum(strokes_after_values) / len(strokes_after_values)) if strokes_after_values else None

    return LieMetrics(
        n=n, green_reach=green_reach, green_reach_rate=green_reach_rate,
        avg_remaining_yd=avg_remaining_yd, avg_remaining_denominator=len(valid_end),
        avg_remaining_excluded_unknown_end=excluded_unknown_end,
        avg_strokes_after=avg_strokes_after, avg_strokes_after_denominator=len(strokes_after_values),
        terminal_integrity_failures=terminal_failures,
    )


def sample_size_flag(n: int) -> str:
    if n < 5:
        return "VERY SMALL SAMPLE"
    if n < 10:
        return "SMALL SAMPLE"
    return ""


def fmt_metrics(m: LieMetrics) -> str:
    if m.n == 0:
        return "N=0, metrics=N/A"
    rate = f"{m.green_reach_rate*100:.1f}%" if m.green_reach_rate is not None else "N/A"
    avg_rem = f"{m.avg_remaining_yd:.2f}yd (den={m.avg_remaining_denominator})" if m.avg_remaining_yd is not None else "N/A"
    avg_after = f"{m.avg_strokes_after:.2f} (den={m.avg_strokes_after_denominator})" if m.avg_strokes_after is not None else "N/A"
    flag = sample_size_flag(m.n)
    flag_txt = f" [{flag}]" if flag else ""
    return f"N={m.n}{flag_txt} | GreenReach={m.green_reach} ({rate}) | AvgRemaining={avg_rem} | AvgStrokesAfter={avg_after}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="2026090002")
    ap.add_argument("--sqlite", type=Path, default=None)
    ap.add_argument("--transitions-csv", type=Path, default=None)
    ap.add_argument("--official-score-source", type=Path, required=True)
    ap.add_argument("--final-round-tab", required=True,
                     help='e.g. "round-four" -- the REAL final round tab id, never guessed')
    a = ap.parse_args()

    if bool(a.sqlite) == bool(a.transitions_csv):
        print("BLOCKED: supply exactly one of --sqlite or --transitions-csv.")
        raise SystemExit(1)

    print("[FILE LOCATIONS]")
    if a.sqlite:
        print("sqlite =", a.sqlite, "exists=", a.sqlite.is_file())
        if not a.sqlite.is_file():
            print("BLOCKED: sqlite file not found.")
            raise SystemExit(1)
        rows = load_rows_from_sqlite(a.sqlite, a.game)
    else:
        print("transitions_csv =", a.transitions_csv, "exists=", a.transitions_csv.is_file())
        if not a.transitions_csv.is_file():
            print("BLOCKED: transitions CSV not found.")
            raise SystemExit(1)
        rows = load_rows_from_csv(a.transitions_csv)
    print("official_score_source =", a.official_score_source, "exists=", a.official_score_source.is_file())
    if not a.official_score_source.is_file():
        print("BLOCKED: official score source HTML not found.")
        raise SystemExit(1)
    print("total_transition_rows_loaded =", len(rows))

    html = a.official_score_source.read_text(encoding="utf-8")
    final_rows = parse_score_record_final_ranking(html, round_tab_id=a.final_round_tab)
    top10, excluded_non_numeric = official_top10(final_rows)

    print("\n[OUTPUT 1 -- OFFICIAL TOP10]")
    print(f"(final_round_tab={a.final_round_tab!r} -- REAL official ranking, never R3, never predicted)")
    if len(top10) > 10:
        print(f"NOTE: {len(top10)} players have official final rank <= 10 due to ties -- all included.")
    print("Rank | Player | Final Score (to-par / raw strokes)")
    for e in top10:
        to_par = "E" if e.total_to_par == 0 else (f"+{e.total_to_par}" if e.total_to_par and e.total_to_par > 0 else e.total_to_par)
        print(f"{e.rank_display} | {e.player_name} | {to_par} ({e.total_raw_strokes})")

    name_map = name_to_codes(rows)
    unmatched_names = [e.player_name for e in top10 if e.player_name not in name_map]
    multi_code_names = {e.player_name: name_map[e.player_name] for e in top10
                         if e.player_name in name_map and len(name_map[e.player_name]) > 1}

    top10_player_codes: set[str] = set()
    for e in top10:
        top10_player_codes |= name_map.get(e.player_name, set())

    top10_rows = [r for r in rows if r.player_code in top10_player_codes]
    hole_groups = group_by_hole(top10_rows)

    per_player_lie: dict[tuple[str, str], LieMetrics] = {}
    qual_counts = {"페어웨이": 0, "러프": 0, "벙커": 0}
    all_qual_keys: list[tuple] = []
    for e in top10:
        codes = name_map.get(e.player_name, set())
        player_rows = [r for r in top10_rows if r.player_code in codes]
        for lie in QUALIFYING_LIES:
            shots = qualifying_shots(player_rows, lie)
            qual_counts[lie] += len(shots)
            for s in shots:
                all_qual_keys.append((s.player_code, s.round_number, s.hole, s.shot_no))
            per_player_lie[(e.player_name, lie)] = compute_lie_metrics(shots, hole_groups)

    print("\n[OUTPUT 2 -- PLAYER DETAIL]")
    print("Player | Lie | N | Green Reached | Green Reach % | Avg Remaining yd | Avg Strokes to Hole After Shot")
    for e in top10:
        for lie in QUALIFYING_LIES:
            m = per_player_lie[(e.player_name, lie)]
            print(f"{e.player_name} | {lie} | {fmt_metrics(m)}")

    print("\n[OUTPUT 3 -- TOP10 AGGREGATE]")
    print("(directly from all qualifying shot observations -- NOT an average of player averages)")
    print("Lie | N | Green Reach % | Avg Remaining yd | Avg Strokes to Hole After Shot")
    for lie in QUALIFYING_LIES:
        shots = qualifying_shots(top10_rows, lie)
        m = compute_lie_metrics(shots, hole_groups)
        print(f"{lie} | {fmt_metrics(m)}")

    print("\n[OUTPUT 4 -- SAMPLE SIZE WARNING]")
    print("N < 5 = VERY SMALL SAMPLE, 5 <= N < 10 = SMALL SAMPLE. No player-quality conclusions from tiny samples.")
    print("(N=0 is not flagged here -- it is N/A, a distinct case, not a 'sample'; see OUTPUT 2.)")
    for e in top10:
        for lie in QUALIFYING_LIES:
            m = per_player_lie[(e.player_name, lie)]
            if m.n == 0:
                continue
            flag = sample_size_flag(m.n)
            if flag:
                print(f"{e.player_name} | {lie} | N={m.n} | {flag}")

    dup_check: dict[tuple, int] = defaultdict(int)
    for k in all_qual_keys:
        dup_check[k] += 1
    duplicate_qualifying_keys = sum(1 for c in dup_check.values() if c > 1)

    unknown_excluded_start = 0
    for r in top10_rows:
        if r.start_lie == "" and r.start_distance_yd is not None and DIST_MIN <= r.start_distance_yd <= DIST_MAX:
            unknown_excluded_start += 1
    invalid_end_excluded_total = sum(
        per_player_lie[(e.player_name, lie)].avg_remaining_excluded_unknown_end
        for e in top10 for lie in QUALIFYING_LIES
    )
    terminal_failures_total = sum(
        per_player_lie[(e.player_name, lie)].terminal_integrity_failures
        for e in top10 for lie in QUALIFYING_LIES
    )

    print("\n[OUTPUT 5 -- DATA QA]")
    print("total_top10_players_included =", len(top10))
    if len(top10) > 10:
        print("  (>10 due to ties -- see OUTPUT 1 note)")
    print("total_qualifying_150_175yd_shots =", sum(qual_counts.values()))
    print("qualifying_fairway_shots =", qual_counts["페어웨이"])
    print("qualifying_rough_shots =", qual_counts["러프"])
    print("qualifying_sand_shots =", qual_counts["벙커"])
    print("unknown_lie_shots_excluded_from_filter (start_lie==\"\" within 150-175yd) =", unknown_excluded_start)
    print("invalid_end_state_exclusions_from_avg_remaining (end_lie==\"\") =", invalid_end_excluded_total)
    print("terminal_integrity_failures (last shot's end_lie != \"홀인\", excluded from AVG_STROKES_TO_HOLE_AFTER_SHOT only) =", terminal_failures_total)
    print("duplicate_qualifying_shot_keys =", duplicate_qualifying_keys)
    print("official_top10_rows_excluded_non_numeric_rank (WD/DQ/DNS/CUT/other) =", len(excluded_non_numeric))
    for row in excluded_non_numeric:
        print("   excluded:", row["player_name"], "rank_display=", row["rank_display"], "status=", row["official_status"])
    if unmatched_names:
        print("WARNING: official Top10 player_name(s) with NO matching player_code in the shot data:", unmatched_names)
    if multi_code_names:
        print("WARNING: official Top10 player_name(s) matching MULTIPLE player_codes (ambiguous join):", multi_code_names)
    print("exact_filter_used = start_lie in {'페어웨이','러프','벙커'} AND 150.0 <= start_distance_yd <= 175.0")
    print("NOTE: this is descriptive observed data only. NOT Expected Strokes. NOT SG. NOT a player-quality ranking.")


if __name__ == "__main__":
    main()
