"""BETA #001 R2 -> R3 evaluation pipeline — the importable orchestration
core `scripts/run_beta001_r3_update.py` (a thin CLI wrapper) builds on.
Mirrors `klpga.neo_win.r2_pipeline_orchestrator`'s own discipline:

======================================================================
INPUTS THIS FUNCTION NEVER COLLECTS ITSELF
======================================================================
`entry_r3` / `official_r3` / `db_r3` (already normalized via klpga.
neo_win.round_reconciliation.normalize_*) and `r3_model_entrants`
(already produced via klpga.neo_win.round_update_r3.
simulate_post_round3 against the real DB) are all supplied by the
caller. This keeps collection/DB/model-simulation concerns OUT of this
module entirely — exactly the same "pure function, no I/O of its own
inputs" discipline round_reconciliation.reconcile_round and
r2_pipeline_orchestrator.run_r2_evaluation_pipeline already established.
Only the frozen STAGE_R2 history read (needed for the R2->R3 delta) and
the STEP7/STEP8 file writes happen here — both are filesystem-only
(`history_dir` / `output_root`, both caller-chosen paths), never a live
DB connection or network call.

======================================================================
RECONCILIATION IS A HARD GATE
======================================================================
klpga.neo_win.round_reconciliation.reconcile_round is reused verbatim
(the SAME reusable data-quality gate scripts/50_validate_official_round.py
already uses for every round transition). A FAIL verdict HARD STOPS this
function before any prediction/CSV/freeze step runs — never a partial or
best-effort R3 snapshot built on top of unresolved official-vs-DB
disagreement.

======================================================================
OUTPUT ISOLATION — never the real production files
======================================================================
Every file this function writes lives under `output_root` (a directory
the CALLER chooses) — the BETA_R3_FULL.csv copy. The only OTHER
filesystem write is the optional STAGE_R3 freeze under `history_dir`
(also caller-chosen), gated by `freeze=True` AND a non-FAIL
reconciliation verdict. This function never writes to docs/index.html
or any docs/tournaments/.../index.html, and never touches the PRE/R1/R2
frozen artifacts — R2 is only ever READ (via read_effective_history_stage)
for the movement-baseline delta, never rewritten.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga.neo_win.round_reconciliation import (
    VERDICT_FAIL,
    NormalizedPlayer,
    ReconciliationResult,
    reconcile_round,
)
from klpga.neo_win.tournament_history import (
    STAGE_R2,
    STAGE_R3,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    read_effective_history_stage,
    write_or_supersede_history_stage,
)

_R3_MODEL_CSV_FIELDNAMES: tuple[str, ...] = (
    "player_code", "player_name", "player_status", "position", "score_to_par",
    "neo_win_pct", "neo_top5_pct", "neo_top10_pct", "neo_top20_pct",
    "r2_win_pct", "r2_to_r3_win_change_pct",
)
"""Verbatim the same schema scripts/46_predict_neo_win_post_r3.py already
writes — kept identical here on purpose (never reordered/renamed) so
both the standalone script and this one-command pipeline produce a
byte-for-byte comparable BETA_R3_FULL.csv."""


def reconciliation_report(result: ReconciliationResult) -> dict:
    """The same counts scripts/50_validate_official_round.py already
    prints, as a plain dict — reused by both the CLI's printed report
    and steps["STEP3_RECONCILIATION"]."""
    score_mismatches = [a for a in result.anomalies if a["classification"] == "SCORE_MISMATCH"]
    position_mismatches = [a for a in result.anomalies if a["classification"] == "POSITION_MISMATCH"]
    identity_mismatches = [
        a for a in result.anomalies if a["classification"] in ("NAME_MISMATCH", "POSSIBLE_IDENTITY_MISMATCH")
    ]
    entry_absent = [a for a in result.anomalies if a["classification"] == "ENTRY_ABSENT_FROM_OFFICIAL_AND_DB"]
    incomplete_official = [a for a in result.anomalies if a["classification"] == "OFFICIAL_INCOMPLETE_NO_DB"]
    official_missing_in_db = [a for a in result.anomalies if a["classification"] == "OFFICIAL_COMPLETE_MISSING_IN_DB"]
    return {
        "verdict": result.verdict,
        "entry_count": len(result.entry),
        "official_count": len(result.official),
        "db_count": len(result.db),
        "matched": len(result.entry_and_official_and_db),
        "official_not_in_db": sorted(result.official_not_in_db),
        "db_not_in_official": sorted(result.db_not_in_official),
        "score_mismatch": [a["player_code"] for a in score_mismatches],
        "position_mismatch": [a["player_code"] for a in position_mismatches],
        "identity_mismatch": [a["player_code"] for a in identity_mismatches],
        "entry_absent": [a["player_code"] for a in entry_absent],
        "incomplete_official": [a["player_code"] for a in incomplete_official],
        "official_missing_in_db": [a["player_code"] for a in official_missing_in_db],
        "eligible": result.eligible,
        "excluded": result.excluded,
        "unresolved": result.unresolved,
    }


def write_r3_model_csv(
    entrants: list[dict],
    r2_win_by_code: dict,
    status_labels_by_code: dict,
    out_path: Path,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_R3_MODEL_CSV_FIELDNAMES)
        writer.writeheader()
        for e in entrants:
            code = e["player_code"]
            win_pct = e.get("win_pct")
            r2_pct = r2_win_by_code.get(code)
            change = (win_pct - r2_pct) if (win_pct is not None and r2_pct is not None) else None
            writer.writerow({
                "player_code": code,
                "player_name": e.get("player_name"),
                "player_status": status_labels_by_code.get(code, "unavailable"),
                "position": e.get("position") if e.get("position") is not None else "unavailable",
                "score_to_par": e.get("score_to_par") if e.get("score_to_par") is not None else "unavailable",
                "neo_win_pct": win_pct if win_pct is not None else "unavailable",
                "neo_top5_pct": e.get("top5_pct") if e.get("top5_pct") is not None else "unavailable",
                "neo_top10_pct": e.get("top10_pct") if e.get("top10_pct") is not None else "unavailable",
                "neo_top20_pct": e.get("top20_pct") if e.get("top20_pct") is not None else "unavailable",
                "r2_win_pct": r2_pct if r2_pct is not None else "unavailable",
                "r2_to_r3_win_change_pct": change if change is not None else "unavailable",
            })
    return out_path


def run_r3_evaluation_pipeline(
    *,
    game_code: str,
    tournament_name: str,
    history_dir: Path,
    entry_r3: dict[str, NormalizedPlayer],
    official_r3: dict[str, NormalizedPlayer],
    db_r3: dict[str, NormalizedPlayer],
    r3_model_entrants: list[dict],
    output_root: Path,
    status_labels_by_code: Optional[dict] = None,
    freeze: bool = False,
    source_prediction_id: str = "",
    source_model_version: str = "",
    source_generated_at_utc: str = "",
) -> dict:
    """Runs STEP3 (reconciliation, hard gate) + STEP6 (R2->R3 delta) +
    STEP7 (CSV) + STEP8 (optional freeze). Returns
    {"status": "OK"/"HARD_STOP", "steps": {...}, ...}. STEP1/STEP2
    (live collection+upsert), STEP4 (future-leakage guard — a live-DB
    check with no meaning against these already-normalized inputs), and
    STEP5 (the actual simulate_post_round3 call) all happen in the
    CALLER, exactly like klpga.neo_win.round_update_r2.
    simulate_post_round2 happens in run_beta001_r2_update.py's own
    run_real(), never inside r2_pipeline_orchestrator."""
    output_root = Path(output_root)
    history_dir = Path(history_dir)
    status_labels_by_code = status_labels_by_code or {}
    steps: dict = {}

    reconciliation = reconcile_round(entry_r3, official_r3, db_r3, round_number=3)
    steps["STEP3_RECONCILIATION"] = reconciliation_report(reconciliation)
    if reconciliation.verdict == VERDICT_FAIL:
        return {
            "status": "HARD_STOP",
            "reason": "STEP3 official-vs-DB reconciliation returned FAIL — see steps.STEP3_RECONCILIATION for "
                      "the exact anomalies. No prediction, CSV, or freeze was produced.",
            "steps": steps,
        }

    r2_history = read_effective_history_stage(history_dir, game_code, STAGE_R2)
    r2_win_by_code = {e.player_code: e.win_pct for e in r2_history.entrants} if r2_history is not None else {}
    steps["STEP6_R2_TO_R3_DELTA_BASELINE"] = {
        "found": r2_history is not None,
        "n_r2_players_with_win_pct": len(r2_win_by_code),
    }

    csv_path = output_root / "BETA_R3_FULL.csv"
    write_r3_model_csv(r3_model_entrants, r2_win_by_code, status_labels_by_code, csv_path)
    win_values = [e.get("win_pct") for e in r3_model_entrants if e.get("win_pct") is not None]
    steps["STEP7_R3_MODEL_CSV"] = {
        "path": str(csv_path),
        "n_entrants": len(r3_model_entrants),
        "win_sum_pct": round(sum(win_values), 4),
        "n_with_real_win_pct": len(win_values),
    }

    freeze_status = "NOT FROZEN (pass freeze=True to freeze + record history)"
    if freeze:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entrants = tuple(
            HistoryEntrant(
                player_code=e["player_code"], player_name=e.get("player_name"),
                win_pct=e.get("win_pct"), top5_pct=e.get("top5_pct"),
                top10_pct=e.get("top10_pct"), top20_pct=e.get("top20_pct"),
                position=e.get("position"), score_to_par=e.get("score_to_par"),
            )
            for e in r3_model_entrants
        )
        snapshot = HistoryStageSnapshot(
            game_code=game_code, stage=STAGE_R3, record_kind=RECORD_KIND, recorded_at_utc=now,
            source_prediction_id=source_prediction_id, source_model_version=source_model_version,
            source_generated_at_utc=source_generated_at_utc or now,
            tournament_name=tournament_name, field_size=len(entrants), entrants=entrants,
        )
        path, action = write_or_supersede_history_stage(snapshot, history_dir)
        if action == "RECORDED":
            freeze_status = f"RECORDED at {path}"
        elif action == "SUPERSEDED_MISSING_MARKER":
            freeze_status = f"SUPERSEDED_MISSING_MARKER — corrective event written at {path}"
        else:
            freeze_status = f"ALREADY_RECORDED — SKIP + LOG, nothing written (existing record at {path})"
    steps["STEP8_R3_FREEZE"] = {"freeze_requested": freeze, "result": freeze_status}

    return {
        "status": "OK",
        "steps": steps,
        "csv_path": str(csv_path),
        "win_sum_pct": round(sum(win_values), 4),
        "freeze_status": freeze_status,
    }
