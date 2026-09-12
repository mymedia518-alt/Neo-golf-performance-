"""R3 RESULT-ONLY INPUT PREPARATION -- the ONE command a user runs
after KB 2026090003's R3 has genuinely concluded.

    python scripts/117_kb_r3_result_and_final_candidate.py --game-code 2026090003

Does ALL of the following, and nothing else:
  1. Snapshots R2's frozen artifacts (freeze + forecast) BEFORE touching
     anything.
  2. Collects the real, official R3 result (klpga.co.kr roundLeaderboard,
     round=3) -- the ONLY required input. No player list, no CSV, no
     manually-entered probability, no CUT/WD judgment, no R1/R2
     re-entry.
  3. Runs the full validation checklist (klpga.neo_win.r3_result_input.
     validate_r3_result) -- tournament identity, final_round_number,
     71-player R2 ACTIVE population, player_id JOIN completeness,
     duplicate id/name, unmatched players, r3_score/final_total
     presence, derived final_rank, evidenced WD/DQ status, population
     reconciliation. ANY failure -> BLOCKED, no R3 freeze / FINAL
     candidate written.
  4. Re-snapshots R2's frozen artifacts AFTER collection and asserts
     byte-for-byte equality with step 1 -- if R2 changed in any way,
     HARD STOP (klpga.neo_win.r3_result_input.R2FreezeProtectionError).
  5. R3 IS A REAL PUBLIC STAGE (R3 FINAL WEB DRY-RUN task, section 1) --
     FINAL is never reachable by collapsing R2 straight into FINAL.
     Builds and writes the immutable R3 freeze (klpga.neo_win.r3_freeze,
     write-once -- a re-run against an already-frozen R3 loads and
     re-verifies it instead of erroring), then renders R3's own real
     public page (klpga.neo_win.r3_real_page.render_r3_real_page) under
     candidate/<game_code>_r3_web_candidate/index.html -- NEVER under
     docs/. The frozen R2 forecast is shown on this page ONLY under its
     fixed "R2 종료 후 예측" label; no new R3-based forecast is ever
     computed (KB's final_round_number is 3 -- see
     klpga.neo_win.post_r3_forecast's own remaining_rounds<1 refusal).
  6. Re-verifies the R3 freeze's own hash immediately after writing it
     -- only once R3 genuinely, verifiably exists does step 7 proceed.
  7. Builds the FINAL validation dataset (JOIN of the R3 freeze's result
     against the frozen R2 forecast) and writes the FINAL validation
     candidate artifact (2026090003_FINAL_VALIDATION_CANDIDATE.json) --
     a real, reviewable file under content/website_v2/, NEVER published
     to docs/, NEVER wired into HOME, NEVER auto-deployed.
  8. Renders that candidate into a real FINAL web page (klpga.neo_win.
     final_real_page.render_final_candidate_page) under
     candidate/<game_code>_final_web_candidate/index.html -- NEVER
     under docs/. Reads both the R3 and FINAL rendered HTML back and
     cross-checks every player's rendered rank/identity against their
     source JSON -- ANY mismatch is a HARD STOP, never a silently-shipped
     divergence (R3 FINAL WEB DRY-RUN task, section 6/16: "JSON은 맞는데
     HTML이 틀릴 수 있는가?" must never pass unnoticed).
  9. STOPS. Never writes klpga.neo_win.final_publication_gate's
     `final_published_evidence` artifact, never touches root HOME,
     never deploys to production -- a human reviews the generated R3
     and FINAL web candidates and decides production promotion as an
     entirely separate, later step.

NEVER builds a POST-R3 win forecast. NEVER touches PRE/R1/R2's own
published pages, root HOME, or any preserved failed-live audit
directory."""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.final_real_page import parse_final_candidate_page, render_final_candidate_page  # noqa: E402
from klpga.neo_win.r2_freeze import load_r2_freeze, verify_r2_freeze_hash  # noqa: E402
from klpga.neo_win.r3_freeze import (  # noqa: E402
    build_r3_frozen_evidence,
    load_r3_freeze,
    r3_freeze_exists,
    verify_r3_freeze_hash,
    write_r3_freeze_immutable,
)
from klpga.neo_win.r3_real_page import parse_r3_real_page, render_r3_real_page  # noqa: E402
from klpga.neo_win.r3_result_input import (  # noqa: E402
    R2FreezeProtectionError,
    R3ResultInputError,
    build_final_validation_dataset,
    build_r3_frozen_records,
    extract_r3_official_result,
    snapshot_r2_state,
    validate_r3_result,
    verify_r2_state_unchanged,
)
from klpga.parsers.leaderboard_parser import PlayerRoundRow  # noqa: E402
from klpga.tournament_context import candidate_dir, load_tournament_context  # noqa: E402
from klpga.website_v2.kb_home_stage_router import kb_current_stage  # noqa: E402

DEFAULT_GAME_CODE = "2026090003"
CONTENT = ROOT / "content" / "website_v2"


def _final_candidate_path(context) -> Path:
    return context.artifact_path("final_validation_candidate")


def _count_by_status(records: list) -> dict:
    counts: dict = {}
    for r in records:
        status = r.get("status", "ACTIVE")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _load_sponsor_by_id(game_code: str) -> dict:
    """Same verified-official sponsor source scripts/109 and 112 already
    use for R1/R2 -- never a second, independently-sourced sponsor
    mapping. Missing file -> empty dict (every row's sponsor slot
    renders empty, never guessed)."""
    path = CONTENT / f"KB_{game_code}_SPONSOR_INTEGRITY_AUDIT_V2.json"
    if not path.is_file():
        return {}
    audit = json.loads(path.read_text(encoding="utf-8"))
    return {r["player_id"]: r["sponsor"] for r in audit.get("newly_recovered_sponsors", [])}


def run(*, game_code: str) -> dict:
    """Always performs the real, official R3 collection -- this is a
    manual, one-time command a human runs deliberately after R3 has
    concluded, never an automated polling cycle, so there is no
    separate --live gate to remember. (The synthetic test suite never
    calls this function at all -- it exercises the pure functions in
    klpga.neo_win.r3_result_input directly, with injected fixture rows,
    so a real network call is never reachable from a test.)"""
    context = load_tournament_context(game_code)

    r2_freeze = load_r2_freeze(context)
    if r2_freeze is None:
        raise R3ResultInputError(f"no verified R2 freeze exists for game_code={game_code!r} -- nothing to build a FINAL candidate from")
    if not verify_r2_freeze_hash(context):
        raise R3ResultInputError(f"R2 freeze for game_code={game_code!r} failed hash verification -- refusing to proceed")

    forecast_path = context.artifact_path("post_r2_final_forecast")
    if not forecast_path.is_file():
        raise R3ResultInputError("no post_r2_final_forecast artifact exists -- nothing to JOIN R3 result against")
    r2_forecast = json.loads(forecast_path.read_text(encoding="utf-8"))

    active_ids = {str(r["player_id"]) for r in r2_freeze["records"] if r.get("status") == "ACTIVE"}

    before_snapshot = snapshot_r2_state(context)

    from klpga.collectors.leaderboard import fetch_round_leaderboard
    from klpga.http_client import PoliteHttpClient

    client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r3_result")
    try:
        raw_rows = fetch_round_leaderboard(client, game_code, 3, use_cache=False)
    except Exception as exc:  # noqa: BLE001 -- a real network failure is WAIT, never a crash
        return {"action": "WAIT", "reason": f"{type(exc).__name__}: {exc}"}

    r3_rows, unresolved = extract_r3_official_result(raw_rows, active_ids)

    report = validate_r3_result(
        game_code=context.game_code,
        final_round_number=context.final_round_number,
        r2_freeze=r2_freeze,
        r3_rows=r3_rows,
        unresolved_player_ids=unresolved,
        raw_rows=raw_rows,
        expected_game_code=game_code,
    )

    try:
        verify_r2_state_unchanged(context, before_snapshot)
    except R2FreezeProtectionError as exc:
        return {"action": "HARD_STOP", "reason": str(exc)}

    if not report.passed:
        return {
            "action": "BLOCKED",
            "reason": "R3 result validation failed -- see blocked_reasons",
            "blocked_reasons": report.blocked_reasons(),
            "unresolved_players": report.unresolved_players,
            "duplicate_player_ids": report.duplicate_player_ids,
            "duplicate_player_names": report.duplicate_player_names,
        }

    sponsor_by_id = _load_sponsor_by_id(game_code)

    # R3 IS A REAL PUBLIC STAGE (section 5 above / R3 FINAL WEB DRY-RUN
    # task section 1): write the immutable R3 freeze and render R3's own
    # page BEFORE ever building a FINAL candidate. A re-run against an
    # already-frozen R3 loads and re-verifies it rather than erroring
    # (write_r3_freeze_immutable's own write-once contract), so this
    # command stays safely re-runnable.
    if r3_freeze_exists(context):
        r3_freeze = load_r3_freeze(context)
        if r3_freeze is None or not verify_r3_freeze_hash(context):
            return {"action": "HARD_STOP", "reason": f"existing R3 freeze for game_code={game_code!r} failed hash verification"}
    else:
        r3_records = build_r3_frozen_records(r2_freeze=r2_freeze, r3_rows=r3_rows)
        status_counts: dict = {}
        for rec in r3_records:
            status_counts[rec["status"]] = status_counts.get(rec["status"], 0) + 1
        wd_dq_dns_evidence = [
            {"player_id": r.player_id, "status": r.official_status, "evidence": r.status_evidence}
            for r in r3_rows if r.official_status != "ACTIVE"
        ]
        raw_serializable = [dataclasses.asdict(r) if dataclasses.is_dataclass(r) else repr(r) for r in raw_rows]
        evidence = build_r3_frozen_evidence(
            context=context,
            official_source_identity="klpga.co.kr roundLeaderboard round=3",
            official_source_url=None,
            collection_timestamp=datetime.now(timezone.utc).isoformat(),
            raw_official_response=json.dumps(raw_serializable, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"),
            records=r3_records,
            expected_field_count=len(dataclasses.fields(PlayerRoundRow)),
            status_counts=status_counts,
            wd_dq_dns_evidence=wd_dq_dns_evidence,
            r2_freeze_path=context.artifact_path("r2_frozen_evidence"),
            repo_root=REPO_ROOT,
            build_id=f"r3_result_{game_code}",
        )
        write_r3_freeze_immutable(context, evidence)
        if not verify_r3_freeze_hash(context):
            return {"action": "HARD_STOP", "reason": "newly-written R3 freeze failed its own hash verification immediately after writing"}
        r3_freeze = load_r3_freeze(context)

    r3_html = render_r3_real_page(
        tournament_name=context.tournament_name, game_code=context.game_code,
        date_range=context.display_date_range, r3_freeze=r3_freeze, forecast=r2_forecast,
        sponsor_by_id=sponsor_by_id,
    )
    r3_web_dir = candidate_dir(f"{game_code}_r3_web_candidate")
    r3_web_dir.mkdir(parents=True, exist_ok=True)
    r3_web_path = r3_web_dir / "index.html"
    r3_web_path.write_text(r3_html, encoding="utf-8", newline="\n")

    r3_active_ids = {str(r["player_id"]) for r in r3_freeze["records"] if r.get("status") == "ACTIVE"}
    r3_rendered = parse_r3_real_page(r3_html)
    r3_qa_errors = []
    if len(r3_rendered) != len(r3_active_ids):
        r3_qa_errors.append(f"rendered R3 row count {len(r3_rendered)} != R3 ACTIVE population {len(r3_active_ids)}")
    rendered_r3_ids = {r["player_id"] for r in r3_rendered}
    if rendered_r3_ids != r3_active_ids:
        r3_qa_errors.append(f"rendered R3 player_ids differ from R3 ACTIVE population: missing={r3_active_ids - rendered_r3_ids}, extra={rendered_r3_ids - r3_active_ids}")
    if r3_qa_errors:
        return {"action": "HARD_STOP", "reason": "R3 web candidate rendered-output QA failed", "qa_errors": r3_qa_errors}

    dataset = build_final_validation_dataset(r2_freeze=r2_freeze, r2_forecast=r2_forecast, r3_rows=r3_rows)
    candidate = {
        "schema_version": 1,
        "artifact": "final_validation_candidate",
        "game_code": context.game_code,
        "tournament_name": context.tournament_name,
        "final_round_number": context.final_round_number,
        "r2_active_population": len(active_ids),
        "post_r3_win_forecast_generated": False,
        "records": dataset,
    }
    candidate_path = _final_candidate_path(context)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # FINAL WEB CANDIDATE + GENERATED HTML QA (R3 FINAL WEB DRY-RUN task,
    # sections 4/6/16): render the exact same candidate into real HTML,
    # then read it straight back and cross-check every player, player by
    # player, against the JSON that produced it. Written ONLY under
    # candidate/ (never docs/) -- this is a reviewable artifact, not a
    # publication. Reuses the SAME sponsor_by_id loaded once above for
    # R3's page -- never a second, independently-fabricated mapping.
    final_html = render_final_candidate_page(
        tournament_name=context.tournament_name,
        game_code=context.game_code,
        date_range=context.display_date_range,
        candidate=candidate,
        sponsor_by_id=sponsor_by_id,
    )
    final_web_dir = candidate_dir(f"{game_code}_final_web_candidate")
    final_web_dir.mkdir(parents=True, exist_ok=True)
    final_web_path = final_web_dir / "index.html"
    final_web_path.write_text(final_html, encoding="utf-8", newline="\n")

    rendered_rows = parse_final_candidate_page(final_html)
    qa_errors = []
    if len(rendered_rows) != len(dataset):
        qa_errors.append(f"rendered row count {len(rendered_rows)} != candidate record count {len(dataset)}")
    rendered_by_id = {r["player_id"]: r for r in rendered_rows}
    for record in dataset:
        pid = str(record["player_id"])
        rendered = rendered_by_id.get(pid)
        if rendered is None:
            qa_errors.append(f"player_id={pid} missing from rendered FINAL web candidate HTML")
            continue
        expected_rank = record["final_rank"] or "—"
        if rendered["final_rank"] != expected_rank:
            qa_errors.append(f"player_id={pid} rendered final_rank={rendered['final_rank']!r} != candidate final_rank={expected_rank!r}")
    if qa_errors:
        # Never ship a candidate whose own rendered HTML disagrees with
        # the JSON that produced it -- HARD STOP, not a degraded PASS.
        return {"action": "HARD_STOP", "reason": "FINAL web candidate rendered-output QA failed", "qa_errors": qa_errors}

    return {
        "action": "FINAL_CANDIDATE_READY",
        "reason": "R3 official result frozen/published as its own stage, then joined against the frozen R2 forecast for FINAL",
        "r3_freeze_path": str(context.artifact_path("r3_frozen_evidence")),
        "r3_web_candidate_path": str(r3_web_path),
        "r3_status_counts": _count_by_status(r3_freeze["records"]),
        "candidate_path": str(candidate_path),
        "records_written": len(dataset),
        "final_web_candidate_path": str(final_web_path),
        "final_web_qa_passed": True,
        # This script itself NEVER calls sync_root_home_to_current_stage
        # -- it only reports what klpga.website_v2.kb_home_stage_router
        # would now resolve, for operator visibility. HOME only ever
        # advances to "final" once a separate, human-invoked promotion
        # step writes final_published_evidence -- never from this run.
        "kb_current_stage_after_this_run": kb_current_stage(context),
        "home_synced_by_this_script": False,
        "production_deployed": False,
        "final_published_evidence_written": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-code", default=DEFAULT_GAME_CODE)
    args = parser.parse_args()

    result = run(game_code=args.game_code)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["action"] not in ("BLOCKED", "HARD_STOP") else 1


if __name__ == "__main__":
    raise SystemExit(main())
