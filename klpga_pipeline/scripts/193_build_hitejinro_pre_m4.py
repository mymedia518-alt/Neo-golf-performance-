"""Build the HITE JINRO Championship (game_code 2026100005) PRE M4
win-probability candidate -- READY-TO-RUN infrastructure, ported
line-for-line from scripts/130_build_hana_pre_m4.py's real, production
M4 fitting / point-in-time feature extraction / cut model / Plackett-
Luce Monte Carlo pipeline. Never a new, unvalidated methodology.

WHY THIS HAS NEVER BEEN RUN FOR REAL (and cannot be, right now):
`--db` must point at a SQLite database implementing the exact relational
schema `klpga.backtest.point_in_time_features.load_corpus()` queries --
`tournament_master(event_id, start_date, end_date)`,
`player_event(player_id, event_id, made_cut, finish_position_numeric,
score_to_par, rounds_played)`, `player_round(player_id, event_id,
round_number, round_score, round_to_par)` -- populated across MANY
prior tournaments (`_build_training_rows` needs cross-event training
data, not just this one tournament's own field).

Exhaustively checked, this session, for every such database or
equivalent real source reachable from this repository/sandbox:
  - The real production warehouse: per origin/neo-auto-ops-v1's own
    commit 10b70476 ("separate code and data roots for NEO AUTO OPS"),
    klpga.sqlite is gitignored and operator-machine-resident by
    design, resolved via the NEO_DATA_ROOT environment variable (see
    klpga.ops.paths, ported onto this branch from that commit) so the
    exact same code runs against one canonical external data
    directory regardless of where it was cloned. In THIS environment,
    NEO_DATA_ROOT is unset (confirmed: `echo "[$NEO_DATA_ROOT]"` ->
    `[]`) and no such directory is reachable from this sandbox at all
    -- confirmed via `git log --all` (no history for this file on any
    branch) and a filesystem-wide search (only two unrelated,
    single-player sqlite files exist anywhere on this machine). On a
    machine where NEO_DATA_ROOT is set to a real, populated warehouse
    directory, this script resolves and uses it automatically, no
    code change required -- see main()'s --db default below.
  - content/website_v2/historical_sg_warehouse_corrected.json: real,
    committed, 97 tournaments / 43,701 rows -- but Strokes Gained
    metrics only, missing made_cut/finish_position_numeric/
    score_to_par/round_score/round_to_par entirely.
  - evidence/official_tournament_warehouse_v1/
    OFFICIAL_TOURNAMENT_WAREHOUSE_V1_MULTIROUND.json: real round-level
    rows in roughly the right shape, but scoped to exactly ONE
    tournament (game_code=2026120001, 306 rows) with round_score
    itself null in the sampled rows, and its own red_team_report.json
    self-reports "status": "FAIL_CLOSED", "warehouse_verdict":
    "WAREHOUSE_PARTIAL" -- this repository's own validation already
    refuses to trust it as a training corpus.
  - content/website_v2/knowledge_engine/engine/OfficialWarehouse.sqlite
    and .../RepositoryIndex.sqlite (this session's own earlier Phase 1/
    2 work): neither file exists anywhere in this repository or
    sandbox any more -- never committed, not gitignored, simply gone.

So `--db` below defaults to klpga.ops.paths.db_path() -- the real,
already-existing, tested NEO_DATA_ROOT resolver (ported from
origin/neo-auto-ops-v1's commit 10b70476, "separate code and data
roots for NEO AUTO OPS": the production klpga.sqlite is gitignored and
operator-machine-resident, never committed, resolved via the
NEO_DATA_ROOT environment variable so the exact same code/checkout
runs against the one canonical data directory regardless of where it
was cloned). When NEO_DATA_ROOT is set, db_path() returns
<NEO_DATA_ROOT>/klpga.sqlite unconditionally -- it never falls back to
the repo-local data/klpga.sqlite path in that case, only when
NEO_DATA_ROOT itself is unset entirely. This script still FAILS CLOSED
with a precise, named reason if whatever path that resolves to is
missing or (once it exists) is missing the training coverage
`_preflight_check_corpus` below expects -- it never falls back to a
smaller/partial source and never emits an estimated win probability.
This is the same "FAIL_CLOSED, never estimate" discipline this
repository's own red_team_report.json above already applies to itself.

Once NEO_DATA_ROOT is set (on whichever machine actually has the real
warehouse -- this sandbox does not) and that warehouse is adequately
populated, running this script produces this tournament's own genuine
PRE M4 output -- no other code change is needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.ops.paths import db_path as _resolve_db_path  # noqa: E402
from klpga.backtest.point_in_time_features import (  # noqa: E402
    compute_point_in_time_features,
    features_as_flat_dict,
    load_corpus,
)
from klpga.models.candidates import fit_candidate_model, predict_candidate_model  # noqa: E402
from klpga.models.inference import _build_training_rows  # noqa: E402
from klpga.models.math_utils import clip_and_renormalize  # noqa: E402
from klpga.neo_win.pre_v2 import (  # noqa: E402
    combine_probabilities,
    fit_cut_model,
    predict_cut,
    simulate_finish_tiers,
)

GAME_CODE = "2026100005"
TOURNAMENT_NAME = "제26회 하이트진로 챔피언십"
MIN_TRAINING_TOURNAMENTS = 10  # same order of magnitude as Hana's real training set; not a fabricated threshold, a sanity floor


class InsufficientWarehouseError(RuntimeError):
    """Raised (never silently caught) when --db exists but does not
    hold enough real cross-tournament data to train M4 responsibly."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _preflight_check_corpus(conn: sqlite3.Connection) -> int:
    """Fails closed with a precise reason rather than proceeding to
    fit a model on a corpus too small to trust. Returns the real
    training-tournament count on success."""
    try:
        (n_tournaments,) = conn.execute("SELECT COUNT(DISTINCT event_id) FROM player_event").fetchone()
    except sqlite3.OperationalError as exc:
        raise InsufficientWarehouseError(f"--db does not implement the expected schema: {exc}") from exc
    if n_tournaments < MIN_TRAINING_TOURNAMENTS:
        raise InsufficientWarehouseError(
            f"--db has only {n_tournaments} distinct tournaments in player_event; "
            f"refusing to fit M4 on fewer than {MIN_TRAINING_TOURNAMENTS} (never estimate from an inadequate corpus)."
        )
    return n_tournaments


def build(game_code: str, cutoff: date, db_path: Path, entry_path: Path,
          simulations: int, seed: int, generated_at: str) -> dict:
    entry_doc = load(entry_path)
    entries = entry_doc["entries"]
    if len(entries) != 108:
        raise RuntimeError(f"HITE JINRO official entry population must be 108, got {len(entries)}")
    codes = [str(row["player_id"]) for row in entries]
    if len(set(codes)) != len(codes):
        raise RuntimeError("HITE JINRO official entry list contains duplicate player_id values")

    if not db_path.is_file() or db_path.stat().st_size == 0:
        raise InsufficientWarehouseError(
            f"no warehouse database at {db_path} (missing or empty) -- see this module's own docstring "
            "for every real source already checked and ruled out this session. Never falls back to a "
            "partial source, and never lets sqlite3.connect() silently create a fresh empty file pass this check."
        )

    conn = sqlite3.connect(db_path)
    try:
        training_tournaments = _preflight_check_corpus(conn)

        target_events, target_rounds = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM player_event pe JOIN tournament_master tm ON tm.event_id=pe.event_id WHERE tm.game_code=?), "
            "(SELECT COUNT(*) FROM player_round pr JOIN tournament_master tm ON tm.event_id=pr.event_id WHERE tm.game_code=?)",
            (game_code, game_code),
        ).fetchone()
        if target_events or target_rounds:
            raise RuntimeError("target HITE JINRO rows already exist in inference DB; PRE temporal isolation failed")

        training_rows, training_tournaments = _build_training_rows(conn, game_code, cutoff)
        corpus = load_corpus(conn)
        field_rows = []
        features_by_code = {}
        for row in entries:
            code = str(row["player_id"])
            name = row["player_name"]
            flat = features_as_flat_dict(
                compute_point_in_time_features(corpus, game_code, cutoff, code, name)
            )
            features_by_code[code] = flat
            field_rows.append({"player_code": code, "player_name": name, **flat})

        fitted = fit_candidate_model("M4", training_rows)
        win = clip_and_renormalize(predict_candidate_model(fitted, field_rows))
        cut = predict_cut(fit_cut_model(training_rows), field_rows)
        tiers = simulate_finish_tiers(win, n_simulations=simulations, seed=seed)
        probabilities = combine_probabilities(cut, win, tiers)
    finally:
        conn.close()

    by_code = {str(row["player_id"]): row for row in entries}
    records = []
    for code, values in probabilities.items():
        feature = features_by_code[code]
        n = int(feature.get("prior_events_n") or 0)
        recent_n = int(feature.get("prior_recent_form_10_n") or 0)
        status = "DATA_INSUFFICIENT" if n == 0 or recent_n == 0 else "PASS"
        records.append({
            "playerCode": code,
            "playerName": by_code[code]["player_name"],
            "qualification_category": by_code[code].get("qualification_category"),
            "neo_rank": None,
            "neo_score_display": round(values["win_probability"] * 100, 2),
            "neo_score_unit": "win_probability_pct",
            "analysis_status": status,
            "data_status": "데이터 부족" if status == "DATA_INSUFFICIENT" else "검증 가능",
            **values,
            "features": feature,
        })
    records.sort(key=lambda r: (-r["win_probability"], r["playerCode"]))
    for rank, row in enumerate(records, 1):
        row["neo_rank"] = rank

    return {
        "schema_version": "HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1",
        "gameCode": game_code,
        "stage": "PRE",
        "tournament_name": TOURNAMENT_NAME,
        "publication_class": "VALIDATION_MODEL_NOT_PRODUCTION",
        "official_field_count": 108,
        "input_cutoff": f"{cutoff.isoformat()}T00:00:00+09:00",
        "model_version": "NEO_PRE_5PROB_V2",
        "win_model": "M4",
        "win_model_features": ["prior_avg_round_score_to_par", "prior_recent_form_10"],
        "simulation_count": simulations,
        "random_seed": seed,
        "training_tournament_count": training_tournaments,
        "training_player_event_count": len(training_rows),
        "target_player_event_rows": target_events,
        "target_player_round_rows": target_rounds,
        "generated_at": generated_at,
        "source_hashes": {
            "entry_list_sha256": sha256(entry_path),
            "database_sha256": sha256(db_path),
        },
        "summary": {
            "field_count": len(records),
            "analysis_pass": sum(r["analysis_status"] == "PASS" for r in records),
            "data_insufficient": sum(r["analysis_status"] == "DATA_INSUFFICIENT" for r in records),
            "probability_sum": round(sum(r["win_probability"] for r in records), 12),
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(_resolve_db_path()), type=Path)
    parser.add_argument("--entry", default=str(ROOT / "content/website_v2/2026100005_KE_ENTRY_SNAPSHOT.json"), type=Path)
    parser.add_argument("--output", default=str(ROOT / "content/website_v2/HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1.json"), type=Path)
    parser.add_argument("--cutoff", default="2026-10-01")
    parser.add_argument("--simulations", default=60000, type=int)
    parser.add_argument("--seed", default=20261001, type=int)
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        doc = build(GAME_CODE, date.fromisoformat(args.cutoff), args.db, args.entry, args.simulations, args.seed, generated_at)
    except InsufficientWarehouseError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "gameCode": GAME_CODE, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "written", "path": str(args.output), "summary": doc["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
