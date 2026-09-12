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
     reconciliation. ANY failure -> BLOCKED, no FINAL candidate written.
  4. Re-snapshots R2's frozen artifacts AFTER collection and asserts
     byte-for-byte equality with step 1 -- if R2 changed in any way,
     HARD STOP (klpga.neo_win.r3_result_input.R2FreezeProtectionError).
  5. On full success: writes the FINAL validation candidate artifact
     (2026090003_FINAL_VALIDATION_CANDIDATE.json) -- a real, reviewable
     file under content/website_v2/, NEVER published to docs/, NEVER
     wired into HOME, NEVER auto-deployed.
  6. Renders that candidate into a real FINAL web page (klpga.neo_win.
     final_real_page.render_final_candidate_page) under
     candidate/<game_code>_final_web_candidate/index.html -- NEVER
     under docs/. Reads the rendered HTML back (klpga.neo_win.
     final_real_page.parse_final_candidate_page) and cross-checks every
     player's rendered rank/identity against the candidate JSON --
     ANY mismatch is a HARD STOP, never a silently-shipped divergence
     (R3 FINAL WEB DRY-RUN task, section 6/16: "JSON은 맞는데 HTML이
     틀릴 수 있는가?" must never pass unnoticed).
  7. STOPS. Never writes klpga.neo_win.final_publication_gate's
     `final_published_evidence` artifact, never touches root HOME,
     never deploys to production -- a human reviews the generated FINAL
     web candidate and decides production promotion as an entirely
     separate, later step.

NEVER builds a POST-R3 win forecast (KB's final_round_number is 3 --
there is nothing left to forecast; see klpga.neo_win.post_r3_forecast's
own remaining_rounds<1 refusal for the parallel, already-established
precedent). NEVER touches PRE/R1/R2's own published pages, root HOME,
or any preserved failed-live audit directory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.final_real_page import parse_final_candidate_page, render_final_candidate_page  # noqa: E402
from klpga.neo_win.r2_freeze import load_r2_freeze, verify_r2_freeze_hash  # noqa: E402
from klpga.neo_win.r3_result_input import (  # noqa: E402
    R2FreezeProtectionError,
    R3ResultInputError,
    build_final_validation_dataset,
    extract_r3_official_result,
    snapshot_r2_state,
    validate_r3_result,
    verify_r2_state_unchanged,
)
from klpga.tournament_context import candidate_dir, load_tournament_context  # noqa: E402

DEFAULT_GAME_CODE = "2026090003"
CONTENT = ROOT / "content" / "website_v2"


def _final_candidate_path(context) -> Path:
    return context.artifact_path("final_validation_candidate")


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
    # publication.
    sponsor_by_id = _load_sponsor_by_id(game_code)
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
        "reason": "R3 official result validated and joined against the frozen R2 forecast",
        "candidate_path": str(candidate_path),
        "records_written": len(dataset),
        "final_web_candidate_path": str(final_web_path),
        "final_web_qa_passed": True,
        "home_still_r2": True,
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
