#!/usr/bin/env python3
"""4R FINAL PRE-BUILD Phase 12: the single FINAL-result ingestion
command.

Run this ONE script after the official FR/R4 result is confirmed:

    PYTHONPATH=src python scripts/128_ingest_final_result_and_validate.py --game-code 2026090003

Pipeline (fail-closed at every step -- never fabricates a later step's
input from an earlier step's failure):

  1. Ensure the PRE-FINAL freeze manifest exists (final_pre_freeze) --
     this is idempotent and should already be done well before FR/R4
     finishes; running it here too costs nothing and guarantees the
     validator always has something real to compare against.
  2. If FINAL truth does not exist yet, attempt to build+write it from
     the official final-round live snapshot artifact
     (context.artifact_path(f"r{final_round_number}_live_snapshot") --
     the same generic artifact this project's postmortem module
     already reads, klpga.tournament_postmortem._final_round_snapshot).
     BLOCKED (not fabricated) if that artifact is absent or the round
     is not yet officially complete for every player.
  3. Run the validator (final_validator) + report generator
     (final_report) + content export (final_content_export).
  4. Report each step's real status as one machine-readable JSON
     summary line -- reused by the same "act only on the JSON action"
     convention every other NEO operational script in this repo uses
     (see scripts/96_ok_open_r1_active_cycle.py).

Deliberately NOT automated here: building a real public FINAL page
with the actual numbers. No final_real_page.py renderer exists yet
(correctly -- it cannot be built against fabricated data), so this
script reports that step as MANUAL rather than silently skipping it or
inventing one on the spot.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win import final_content_export, final_pre_freeze, final_report, final_truth, final_validator
from klpga.tournament_context import TournamentContext, load_tournament_context


def _try_build_final_truth_from_live_snapshot(context: TournamentContext) -> dict:
    snapshot_path = context.artifact_path(f"r{context.final_round_number}_live_snapshot")
    if not snapshot_path.is_file():
        return {"status": "BLOCKED", "reason": f"no official final-round live snapshot at {snapshot_path}"}

    live = json.loads(snapshot_path.read_text(encoding="utf-8"))
    players = live.get("player_table") or []
    if not players:
        return {"status": "BLOCKED", "reason": "final-round live snapshot has zero players"}

    still_playing = [p for p in players if int(p.get("holes_completed") or 0) != 18 and str(p.get("status") or "").upper() == "ACTIVE"]
    if still_playing:
        return {"status": "BLOCKED", "reason": f"{len(still_playing)} player(s) still in progress -- FR/R4 not officially complete"}

    records = []
    for p in players:
        status = str(p.get("status") or "ACTIVE").upper()
        if status not in ("ACTIVE", "WD", "DQ", "DNS"):
            status = "ACTIVE"
        rank_display = p.get("rank_display")
        final_rank = rank_display if status != "ACTIVE" else int(rank_display) if str(rank_display).isdigit() else rank_display
        records.append({
            "player_id": str(p.get("player_id") or p.get("player_code")),
            "player_name": p.get("player_name", ""),
            "final_rank": final_rank,
            "final_score": p.get("total_to_par_display", p.get("score_to_par")),
            "r4_score": p.get("round_score_to_par"),
            "rounds_completed": p.get("holes_completed", 0) // 18 if status == "ACTIVE" else int(p.get("rounds_completed") or 0),
            "status": status,
            "top5_actual": bool(isinstance(final_rank, int) and final_rank <= 5),
            "top10_actual": bool(isinstance(final_rank, int) and final_rank <= 10),
            "top20_actual": bool(isinstance(final_rank, int) and final_rank <= 20),
        })

    try:
        truth = final_truth.build_final_truth(
            context=context,
            official_source="klpga.co.kr official final-round live snapshot",
            collected_at=live.get("collected_at", "unknown"),
            raw_official_response=snapshot_path.read_bytes(),
            records=records,
            repo_root=Path(__file__).resolve().parents[1],
            build_id=f"{context.game_code}_FINAL_TRUTH_INGEST",
        )
        path = final_truth.write_final_truth_immutable(context, truth)
    except (final_truth.FinalTruthError, FileExistsError) as exc:
        return {"status": "BLOCKED", "reason": str(exc)}
    return {"status": "WRITTEN", "path": str(path)}


def run(game_code: str) -> dict:
    context = load_tournament_context(game_code)
    summary: dict = {"game_code": context.game_code}

    _, freeze_written = final_pre_freeze.write_freeze_manifest_if_absent(context)
    summary["pre_final_freeze"] = "ALREADY_FROZEN" if not freeze_written else "FROZEN_NOW"

    if not final_truth.final_truth_exists(context):
        truth_step = _try_build_final_truth_from_live_snapshot(context)
        summary["final_truth_ingest"] = truth_step
        if truth_step["status"] == "BLOCKED":
            summary["action"] = "BLOCKED"
            summary["reason"] = truth_step["reason"]
            return summary
    else:
        summary["final_truth_ingest"] = {"status": "ALREADY_EXISTS"}

    try:
        report = final_report.build_final_report(context)
    except final_validator.FinalValidationBlocked as exc:
        summary["action"] = "BLOCKED"
        summary["reason"] = str(exc)
        return summary

    summary["report_status"] = report["status"]
    if report["status"] == report.get("status") and report["status"] != "BLOCKED":
        content = final_content_export.export_content_sources(context)
        summary["content_export_channels"] = {k: v["status"] for k, v in content.items()}
    summary["public_final_page_build"] = "MANUAL -- final_real_page.py renderer does not exist yet (by design: it cannot be built before real data exists)"
    summary["action"] = "VALIDATED" if report["status"] != "BLOCKED" else "BLOCKED"
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-code", default=None)
    args = parser.parse_args()
    summary = run(args.game_code)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
