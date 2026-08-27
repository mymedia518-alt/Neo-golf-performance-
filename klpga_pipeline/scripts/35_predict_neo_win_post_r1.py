"""NEO GOLF BETA #001-R1 — post-Round-1 probability update. Combines
the FROZEN PRE prediction (prediction_id=001, read-only, never
modified) with the real, already-collected Round-1 leaderboard
(`player_round`, round_number=1) via a Monte Carlo tournament
simulation over the REMAINING rounds (see src/klpga/neo_win/
round_update.py for the full method and the real-evidence-verified
36-hole-cut-only format this relies on).

Does NOT write to tournament_master/player_master/player_event/
player_round/tournament_entry/official_metric_value/player_stats_
snapshot/predictions/neo_win_predictions' PRE files (DB opened
`mode=ro`; the PRE snapshot is only ever read). Writes:
  - outputs/beta001_r1/{BETA001_R1_FULL.csv, BETA001_R1_TOP20.csv,
    BETA001_R1_MODEL_REPORT.md, BETA001_R1_THREADS.txt} every run
    (regenerated, gitignored).
  - Only with --freeze: an IMMUTABLE neo_win_predictions/<year>/
    neo_win_001-R1_<game_code>.{json,csv} snapshot (append-only, never
    overwritten) plus a convenience copy at
    outputs/beta001_r1/BETA001_R1_FREEZE.json.

PREREQUISITE: Round 1's leaderboard must already be collected into
`player_round` for this game_code — this script never fires an HTTP
request itself. Use the existing single-tournament collector:
    python scripts/04_collect_single_tournament.py --season 2026 --game-code <code>

======================================================================
HARD STOP ON ANY ROUND-2 DATA (LEAKAGE GUARD)
======================================================================
Before doing anything else, this script queries `player_round` for
round_number=2 rows for this game_code. If even ONE such row exists,
it HARD STOPS and writes nothing — this script must never use Round-2
(or later) data. Once Round 2 has genuinely concluded, use
scripts/44_predict_neo_win_post_r2.py instead (which correctly reads
the cut as a real, known fact rather than simulating it).

======================================================================
NEO R3 % / NEO FINAL % ARE ALIASES OF POST_R1_MAKE_CUT %
======================================================================
Verified real evidence (docs/SITE_STRUCTURE_TODO.md): this tournament
format has exactly ONE cut, after Round 2, and no subsequent cut — a
cutmaker automatically plays both remaining rounds. There is no
independent "advances to R3" vs "advances to FINAL" event to model, so
`neo_r3_pct`/`neo_final_pct` are reported as the literal same simulated
value as `post_r1_make_cut_pct` (still a Monte Carlo estimate at this
stage, since Round 2 has not happened yet) — never a second,
independently-derived number. Same convention as round_update_r2.py.

======================================================================
--pre-family {beta001, beta001c} — READING THE #001-C PRE BASELINE
======================================================================
Default `beta001` preserves every existing behavior byte-for-byte
(reads `neo_win_predictions/`, same as always). Pass `--pre-family
beta001c --c-predictions-dir neo_win_c_predictions --pre-prediction-id
<id>` to source PRE from the current BETA #001-C production baseline
instead (e.g. `neo_win_c_001-C-FINAL_<game_code>.json`) — '001' is
rejected as `--pre-prediction-id` in this mode (that id is BETA #001's
own, never to be reused for a #001-C snapshot).

`_adapt_beta001c_snapshot` below is a PURE FIELD-MAPPING adapter, not a
model change: `klpga.neo_win.model.BASE_FEATURES` (reused unmodified by
every BETA #001-C model A/B/C) always stores the RAW
`prior_avg_round_score_to_par` / `neo_consistency_stddev` values in a
#001-C entrant's `feature_values` dict (verified: scripts/38 populates
`feature_values` straight from the live-field row, before any
standardization) — the exact same real quantities BETA #001's own
snapshot already exposes as dedicated fields. The adapter only renames
where these live so the UNCHANGED `klpga.neo_win.round_update.
build_sim_inputs_from_frozen_snapshot` / `simulate_post_round1` can
consume a #001-C PRE exactly as they already consume a #001 one — no
simulation math is touched.

With `--pre-family beta001c --freeze`, this script ALSO attempts to
record the result as tournament_history's STAGE_R1 (same append-only
`klpga.neo_win.tournament_history.write_history_stage_atomic` used by
scripts/42 and scripts/44) — a SKIP + LOG, never a crash, if that
(game_code, R1) slot is already occupied (e.g. by an earlier
HISTORICAL_SNAPSHOT_MISSING marker). The `--prediction-id`-identified
round-update snapshot itself is written either way. The `beta001`
(legacy) path is unchanged: still recorded via the separate
scripts/42_record_tournament_history.py, exactly as before.

Usage (legacy BETA #001, unchanged default):
    python scripts/35_predict_neo_win_post_r1.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-prediction-id 001 --freeze --prediction-id 001-R1

Usage (current BETA #001-C production baseline):
    python scripts/35_predict_neo_win_post_r1.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-family beta001c --pre-prediction-id 001-C-FINAL --pre-cutoff-date 2026-08-27 \\
        --freeze --prediction-id 001-C-R1
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import NeoWinAlreadyArchivedError, archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import (  # noqa: E402
    archive_paths as c_archive_paths,
    read_neo_win_c_snapshot,
)
from klpga.neo_win.round_update import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_sim_inputs_from_frozen_snapshot,
    estimate_cut_fraction,
    simulate_post_round1,
)
from klpga.neo_win.round_update_archive import (  # noqa: E402
    RECORD_KIND, MODEL_VERSION, RoundUpdateEntrantSnapshot, RoundUpdateSnapshot,
    snapshot_to_dict, write_round_update_snapshot_atomic,
)
from klpga.neo_win.tournament_history import (  # noqa: E402
    RECORD_KIND as HISTORY_RECORD_KIND,
    STAGE_R1,
    HistoryEntrant,
    HistoryStageAlreadyRecordedError,
    HistoryStageSnapshot,
    write_history_stage_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001_r1"

_KNOWN_LIMITATIONS: tuple[str, ...] = (
    "Monte Carlo tournament simulation over Normal(expected_round_score_to_par, spread) i.i.d. "
    "per remaining round — no course-difficulty-by-round correlation, no playoff modeling (a "
    "tied win splits credit fractionally rather than simulating a playoff).",
    "Cut line is the REAL, empirically-observed made-cut rate from every historical player_event "
    "row (rounds_played==4), applied to today's field size — KLPGA's exact cutline rule "
    "(e.g. top-N-and-ties) is not independently confirmed anywhere in this project.",
    "Verified real evidence (docs/SITE_STRUCTURE_TODO.md, 100-tournament collection): the "
    "real rounds_played distribution is exactly {1,2,4} — zero 3-round players — confirming a "
    "single 36-hole cut with no subsequent cut. This simulation never models an R3/R4 cut.",
)


def _read_r1_scores(conn: sqlite3.Connection, game_code: str) -> dict:
    rows = conn.execute(
        "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = 1 "
        "AND round_to_par IS NOT NULL",
        (game_code,),
    ).fetchall()
    return {player_id: round_to_par for player_id, round_to_par in rows}


def _r1_positions(r1_scores: dict) -> dict:
    ordered = sorted(r1_scores.items(), key=lambda kv: kv[1])
    positions = {}
    for rank, (code, _score) in enumerate(ordered, start=1):
        positions[code] = rank
    return positions


def _r2_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 2",
        (game_code,),
    ).fetchone()[0]


@dataclass(frozen=True)
class _AdaptedPreEntrant:
    player_code: str
    player_name: str
    win_probability: Optional[float]
    prior_avg_round_score_to_par: Optional[float]
    neo_consistency_stddev: Optional[float]


@dataclass(frozen=True)
class _AdaptedPreSnapshot:
    prediction_id: str
    tournament_name: Optional[str]
    cutoff_date: str
    predictions: tuple


def _adapt_beta001c_snapshot(c_snapshot) -> _AdaptedPreSnapshot:
    """Pure field-mapping adapter — see module docstring. Reads the RAW
    prior_avg_round_score_to_par / neo_consistency_stddev values out of
    a NeoWinCEntrantSnapshot's feature_values dict (present because
    klpga.neo_win.model.BASE_FEATURES is always the first 3 columns of
    every BETA #001-C model) so the untouched round_update.py Monte
    Carlo simulation can consume it exactly like a BETA #001 snapshot.
    Never computes, guesses, or renormalizes a value — a feature absent
    from feature_values stays None (round_update.py's own existing
    population-mean shrink handles that, unchanged)."""
    entrants = tuple(
        _AdaptedPreEntrant(
            player_code=e.player_code,
            player_name=e.player_name,
            win_probability=e.win_probability,
            prior_avg_round_score_to_par=e.feature_values.get("prior_avg_round_score_to_par"),
            neo_consistency_stddev=e.feature_values.get("neo_consistency_stddev"),
        )
        for e in c_snapshot.predictions
    )
    return _AdaptedPreSnapshot(
        prediction_id=c_snapshot.prediction_id,
        tournament_name=c_snapshot.tournament_name,
        cutoff_date=c_snapshot.cutoff_date,
        predictions=entrants,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--predictions-dir", default=str(ROOT / "neo_win_predictions"))
    parser.add_argument("--pre-family", choices=["beta001", "beta001c"], default="beta001",
                         help="Which frozen PRE archive family to read. Default 'beta001' preserves existing "
                              "behavior; 'beta001c' reads the current BETA #001-C production baseline instead.")
    parser.add_argument("--c-predictions-dir", default=str(ROOT / "neo_win_c_predictions"))
    parser.add_argument("--history-dir", default=str(ROOT / "neo_tournament_history"))
    parser.add_argument("--pre-prediction-id", default="001")
    parser.add_argument("--pre-cutoff-date", required=True, help="cutoff_date of the PRE snapshot, to locate its archive path")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--prediction-id", default="001-R1")
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed for the simulation.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    if args.pre_family == "beta001c" and args.pre_prediction_id == "001":
        print("ERROR: --pre-family beta001c requires an explicit --pre-prediction-id (e.g. '001-C-FINAL') — "
              "'001' is BETA #001's own legacy id and must never be reused for a #001-C snapshot.")
        return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    if args.pre_family == "beta001c":
        pre_json_path, _c = c_archive_paths(
            Path(args.c_predictions_dir), args.pre_prediction_id, args.game_code, args.pre_cutoff_date
        )
        if not pre_json_path.exists():
            print(f"ERROR: frozen BETA #001-C PRE snapshot not found at {pre_json_path}. "
                  "Run scripts/38_predict_beta001c.py --freeze first.")
            return 5
        pre_snapshot = _adapt_beta001c_snapshot(read_neo_win_c_snapshot(pre_json_path))
    else:
        pre_json_path, _c = archive_paths(Path(args.predictions_dir), args.pre_prediction_id, args.game_code, args.pre_cutoff_date)
        if not pre_json_path.exists():
            print(f"ERROR: frozen PRE snapshot not found at {pre_json_path}. Run scripts/33_predict_neo_win.py --freeze first.")
            return 5
        pre_snapshot = read_neo_win_snapshot(pre_json_path)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r2_row_count = _r2_row_count(conn, args.game_code)
        r2_check_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if r2_row_count > 0:
            print(f"HARD STOP: {r2_row_count} round_number=2 player_round row(s) already exist for "
                  f"game_code={args.game_code!r} (checked at {r2_check_utc}). This script only ever "
                  "uses R1-confirmed data — generating a POST-R1 snapshot now would leak Round-2 "
                  "information. Use scripts/44_predict_neo_win_post_r2.py instead. Nothing written.")
            return 7

        r1_scores = _read_r1_scores(conn, args.game_code)
        if not r1_scores:
            print(f"ERROR: no round_number=1 player_round rows found for game_code={args.game_code!r}. "
                  "Collect Round 1 first: python scripts/04_collect_single_tournament.py --season <season> "
                  f"--game-code {args.game_code}")
            return 6
        cut_fraction = estimate_cut_fraction(conn)
    finally:
        conn.close()

    sim_inputs, missing_r1 = build_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores)
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    sim_result = simulate_post_round1(sim_inputs, cut_fraction=cut_fraction, n_simulations=args.n_simulations, rng=rng)

    positions = _r1_positions(r1_scores)
    leader_score = min(r1_scores.values()) if r1_scores else None

    pre_by_code = {e.player_code: e for e in pre_snapshot.predictions}
    entrants = []
    for p in sim_inputs:
        pre_entrant = pre_by_code.get(p.player_code)
        pre_prob = pre_entrant.win_probability if pre_entrant else None
        sim = sim_result.get(p.player_code)
        entrants.append(
            RoundUpdateEntrantSnapshot(
                player_code=p.player_code,
                player_name=p.player_name,
                pre_win_probability=pre_prob,
                r1_score_to_par=p.r1_score_to_par,
                r1_position=positions.get(p.player_code),
                strokes_behind_leader=(p.r1_score_to_par - leader_score) if (p.r1_score_to_par is not None and leader_score is not None) else None,
                post_r1_win_pct=sim["win_pct"] if sim else None,
                post_r1_top5_pct=sim["top5_pct"] if sim else None,
                post_r1_top10_pct=sim["top10_pct"] if sim else None,
                post_r1_top20_pct=sim["top20_pct"] if sim else None,
                post_r1_make_cut_pct=sim["make_cut_pct"] if sim else None,
                probability_change_from_pre=(sim["win_pct"] - pre_prob * 100) if (sim and pre_prob is not None) else None,
                missing_r1_data=(p.r1_score_to_par is None),
            )
        )
    entrants.sort(key=lambda e: (e.post_r1_win_pct is None, -(e.post_r1_win_pct or 0)))

    win_sum = sum(e.post_r1_win_pct for e in entrants if e.post_r1_win_pct is not None)
    codes = [e.player_code for e in entrants]
    duplicates = len(codes) - len(set(codes))
    pre_field_codes = {e.player_code for e in pre_snapshot.predictions}
    non_field = len([c for c in codes if c not in pre_field_codes])
    null_probs = sum(1 for e in entrants if e.post_r1_win_pct is None)

    leakage_check = {
        "rounds_used": [1],
        "cut_rounds_simulated_only": [2, 3, 4],
        "post_r1_real_data_used": False,
        "round_number_2_rows_found_at_generation_time": r2_row_count,
        "round_2_absence_checked_at_utc": r2_check_utc,
        "status": "PASS",
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    full_fieldnames = [
        "rank", "player_code", "player_name", "pre_win_probability_pct", "r1_score_to_par", "r1_position",
        "strokes_behind_leader", "post_r1_win_pct", "post_r1_top5_pct", "post_r1_top10_pct", "post_r1_top20_pct",
        "post_r1_make_cut_pct", "neo_r3_pct", "neo_final_pct", "probability_change_from_pre", "missing_r1_data",
    ]

    def _row(rank, e):
        return {
            "rank": rank, "player_code": e.player_code, "player_name": e.player_name,
            "pre_win_probability_pct": "" if e.pre_win_probability is None else round(e.pre_win_probability * 100, 4),
            "r1_score_to_par": "" if e.r1_score_to_par is None else e.r1_score_to_par,
            "r1_position": "" if e.r1_position is None else e.r1_position,
            "strokes_behind_leader": "" if e.strokes_behind_leader is None else e.strokes_behind_leader,
            "post_r1_win_pct": "" if e.post_r1_win_pct is None else e.post_r1_win_pct,
            "post_r1_top5_pct": "" if e.post_r1_top5_pct is None else e.post_r1_top5_pct,
            "post_r1_top10_pct": "" if e.post_r1_top10_pct is None else e.post_r1_top10_pct,
            "post_r1_top20_pct": "" if e.post_r1_top20_pct is None else e.post_r1_top20_pct,
            "post_r1_make_cut_pct": "" if e.post_r1_make_cut_pct is None else e.post_r1_make_cut_pct,
            # Single-cut format (see module docstring): R3/FINAL advancement IS the make-cut event —
            # a documented alias, never a second, independently-simulated probability.
            "neo_r3_pct": "" if e.post_r1_make_cut_pct is None else e.post_r1_make_cut_pct,
            "neo_final_pct": "" if e.post_r1_make_cut_pct is None else e.post_r1_make_cut_pct,
            "probability_change_from_pre": "" if e.probability_change_from_pre is None else round(e.probability_change_from_pre, 4),
            "missing_r1_data": e.missing_r1_data,
        }

    full_path = output_dir / "BETA001_R1_FULL.csv"
    top20_path = output_dir / "BETA001_R1_TOP20.csv"
    for path, subset in ((full_path, entrants), (top20_path, entrants[:20])):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=full_fieldnames)
            writer.writeheader()
            for rank, e in enumerate(subset, start=1):
                writer.writerow(_row(rank, e))

    threads_lines = [f"[INFO] cut format verified from real evidence: single 36-hole cut, no subsequent cut "
                      f"(docs/SITE_STRUCTURE_TODO.md, rounds_played distribution {{1,2,4}} across 100 real tournaments)"]
    threads_lines.append(f"[INFO] empirical cut_fraction={cut_fraction:.4f} (from real player_event rounds_played=4 rate)")
    threads_lines.append(f"[INFO] n_simulations={args.n_simulations}")
    for code in missing_r1:
        threads_lines.append(f"[SKIP] player_code={code!r}: no Round-1 score found — excluded from the simulation "
                              "field, reported with null post-R1 probabilities, not silently dropped from output.")
    (output_dir / "BETA001_R1_THREADS.txt").write_text("\n".join(threads_lines) + "\n", encoding="utf-8")

    report_lines = [
        "# NEO GOLF BETA #001-R1 — Model Report",
        "",
        f"- Tournament: {pre_snapshot.tournament_name} (`{args.game_code}`)",
        f"- PRE family: {args.pre_family}  prediction_id: {args.pre_prediction_id}  cutoff: {pre_snapshot.cutoff_date}",
        f"- Cut format: single 36-hole cut, no subsequent cut (verified, see threads log)",
        f"- Empirical cut_fraction: {cut_fraction:.4f}",
        f"- n_simulations: {args.n_simulations}",
        f"- Field size (PRE): {len(pre_field_codes)}  Entrants scored: {len(entrants) - len(missing_r1)}  "
        f"Missing R1 data: {len(missing_r1)}",
        "",
        "## Validation",
        "",
        f"- Duplicate players: {duplicates}",
        f"- Non-field players: {non_field}",
        f"- Null probabilities: {null_probs}",
        f"- WIN probability sum: {win_sum:.4f}%",
        f"- Leakage check: {leakage_check}",
        "",
        "## Known BETA limitations",
        "",
    ] + [f"- {l}" for l in _KNOWN_LIMITATIONS]
    (output_dir / "BETA001_R1_MODEL_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("=== NEO GOLF BETA #001 — AFTER R1 ===")
    print()
    print(f"R1 DATA: {len(r1_scores)} player_round round_number=1 rows found for game_code={args.game_code!r}")
    print(f"R2 DATA: 0 round_number=2 rows found (actively checked at {r2_check_utc}, before this snapshot "
          "was generated) — safe to proceed, no future-round leakage.")
    print()
    leader_code = min(r1_scores, key=r1_scores.get) if r1_scores else None
    leader_name = next((e.player_name for e in entrants if e.player_code == leader_code), leader_code)
    print(f"R1 leader: {leader_name}")
    print(f"R1 leader score: {leader_score}")
    print()
    print("=== WIN % TOP 20 ===")
    print()
    for i, e in enumerate(entrants[:20], start=1):
        print(f"{i}. {e.player_name} — {e.post_r1_win_pct}% (PRE {round((e.pre_win_probability or 0) * 100, 3)}%)")
    print()
    risers = sorted([e for e in entrants if e.probability_change_from_pre is not None], key=lambda e: -e.probability_change_from_pre)[:5]
    fallers = sorted([e for e in entrants if e.probability_change_from_pre is not None], key=lambda e: e.probability_change_from_pre)[:5]
    print("=== BIGGEST WIN % RISERS ===")
    print()
    for e in risers:
        print(f"{e.player_name}: {e.probability_change_from_pre:+.4f}%")
    print()
    print("=== BIGGEST WIN % FALLERS ===")
    print()
    for e in fallers:
        print(f"{e.player_name}: {e.probability_change_from_pre:+.4f}%")
    print()
    danger = sorted([e for e in entrants if e.post_r1_make_cut_pct is not None and 20 <= e.post_r1_make_cut_pct <= 80],
                     key=lambda e: e.post_r1_make_cut_pct)
    print("=== MAKE CUT — DANGER ZONE ===")
    print()
    for e in danger[:15]:
        print(f"{e.player_name}: {e.post_r1_make_cut_pct}%")
    print()

    special = {"서교림": "Seo Gyo-rim", "이서윤4": "Lee Seo-yoon4", "박현경": "Park Hyun-kyung",
               "최예림": "Choi Ye-rim", "성유진": "Sung Yu-jin"}
    print("=== SEO GYO-RIM TRACK ===")
    print()
    seo = next((e for e in entrants if e.player_name == "서교림"), None)
    if seo:
        print(f"PRE: {round((seo.pre_win_probability or 0) * 100, 3)}%")
        print(f"After R1: {seo.post_r1_win_pct}%")
        print(f"Change: {seo.probability_change_from_pre}")
    else:
        print("PRE: — (not found in field)")
        print("After R1: —")
        print("Change: —")
    print()
    print("=== SPECIAL DIAGNOSTIC (5 named players) ===")
    print()
    for name, label in special.items():
        e = next((x for x in entrants if x.player_name == name), None)
        if not e:
            print(f"{label} ({name}): SKIP — not found in field")
            continue
        print(f"{label} ({name}): PRE={round((e.pre_win_probability or 0) * 100, 3)}% R1_score={e.r1_score_to_par} "
              f"R1_pos={e.r1_position} behind_leader={e.strokes_behind_leader} POST_R1_WIN={e.post_r1_win_pct}% "
              f"POST_R1_TOP10={e.post_r1_top10_pct}% MAKE_CUT={e.post_r1_make_cut_pct}% "
              f"change={e.probability_change_from_pre}")
    print()
    print("=== MODEL CHECK ===")
    print()
    print(f"Players: {len(entrants)}")
    print(f"WIN probability sum: {win_sum:.4f}%")
    print(f"Missing: {len(missing_r1)} {missing_r1}")
    print(f"Skipped: {len(missing_r1)}")
    print(f"Leakage: {leakage_check['status']}")

    freeze_status = "NOT FROZEN (pass --freeze to freeze 001-R1 permanently)"
    history_status = "NOT ATTEMPTED (tournament history is only recorded here for --pre-family beta001c; " \
                      "the legacy beta001 path is recorded separately by scripts/42_record_tournament_history.py)"
    if args.freeze:
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = RoundUpdateSnapshot(
            prediction_id=args.prediction_id, created_at_utc=created_at_utc, record_kind=RECORD_KIND,
            game_code=args.game_code, tournament_name=pre_snapshot.tournament_name,
            pre_prediction_id=args.pre_prediction_id, pre_cutoff_date=pre_snapshot.cutoff_date,
            round_number=1, cut_fraction_used=cut_fraction, cut_format="single_36_hole_cut_no_subsequent_cut",
            n_simulations=args.n_simulations, field_size=len(pre_field_codes),
            entrants_scored=len(entrants) - len(missing_r1), missing_r1_players=tuple(missing_r1),
            win_probability_sum_pct=win_sum, leakage_check=leakage_check, known_limitations=_KNOWN_LIMITATIONS,
            predictions=tuple(entrants),
        )
        try:
            json_path, csv_path = write_round_update_snapshot_atomic(snapshot, Path(args.predictions_dir))
        except NeoWinAlreadyArchivedError as exc:
            print(f"\nERROR: {exc}")
            return 4
        freeze_copy = output_dir / "BETA001_R1_FREEZE.json"
        freeze_copy.write_text(json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        freeze_status = f"FROZEN at {json_path} / {csv_path} (+ convenience copy {freeze_copy})"

        if args.pre_family == "beta001c":
            history_entrants = tuple(
                HistoryEntrant(
                    player_code=e.player_code, player_name=e.player_name,
                    win_pct=e.post_r1_win_pct, make_cut_pct=e.post_r1_make_cut_pct,
                    top5_pct=e.post_r1_top5_pct, top10_pct=e.post_r1_top10_pct, top20_pct=e.post_r1_top20_pct,
                    position=e.r1_position, score_to_par=e.r1_score_to_par,
                )
                for e in entrants
            )
            history_snapshot = HistoryStageSnapshot(
                game_code=args.game_code, stage=STAGE_R1, record_kind=HISTORY_RECORD_KIND,
                recorded_at_utc=created_at_utc, source_prediction_id=args.prediction_id,
                source_model_version=pre_snapshot.prediction_id, source_generated_at_utc=created_at_utc,
                tournament_name=pre_snapshot.tournament_name, field_size=len(entrants),
                entrants=history_entrants,
            )
            try:
                history_path = write_history_stage_atomic(history_snapshot, Path(args.history_dir))
                history_status = f"RECORDED at {history_path}"
            except HistoryStageAlreadyRecordedError as exc:
                history_status = f"SKIP + LOG — already recorded: {exc}"

    print(f"Freeze status: {freeze_status}")
    print(f"Tournament history (PRE->R1): {history_status}")
    print()
    print(f"Wrote: {full_path}")
    print(f"Wrote: {top20_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
