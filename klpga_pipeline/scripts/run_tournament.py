"""NEO TOURNAMENT PIPELINE items 2/5: single generic entry point.

    run_tournament.py --game-code <GAME_CODE> [--stage STAGE] [--dry-run]

Drives DISCOVERY -> ENTRY -> PRE FREEZE -> PRE -> R1 -> R2 -> R3/R4 ->
FINAL -> POSTMORTEM through the SAME already-existing, already-tested
generic engine every tournament shares:

    klpga.tournament_lifecycle   -- real artifacts -> RoundFacts/TournamentFacts
    klpga.tournament_runtime     -- RoundFacts/TournamentFacts -> Stage
    klpga.tournament_operator    -- Stage -> OperatorAction
    klpga.tournament_action_registry / tournament_cycle
                                  -- OperatorAction -> dispatch + official
                                     preflight fetch

This script's own job is narrow and does not reimplement any of the
above: it only (a) builds a TournamentActionRegistry whose runners
invoke the existing per-stage scripts as subprocesses -- never
duplicating their logic -- and (b) persists the freshly-inferred stage
back to config/active_tournament.json so the next invocation resumes
from real state instead of a stale hand-maintained field.

Resumable and non-destructive: every runner below invokes a script that
is itself safe to re-run (96/98/99/100/101/83/84/94 already assert
their own preconditions and hard-stop rather than silently redo
already-validated work; build_current_round_page.py's --promote gate
only writes docs/ once a byte-for-byte-verified candidate exists).
run_tournament.py adds no additional state beyond what those scripts
already track.

Sandbox note: any LIVE-stage action requires a real klpga.co.kr fetch
(the tournament_cycle official-data preflight, and/or the dispatched
script's own ingest) -- there is no offline stand-in, by design ("fail
loudly rather than silently" per klpga.tournament_cycle). Use --dry-run
to see the decision only.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_action_registry import (  # noqa: E402
    ActionContext,
    ActionResult,
    ActionAvailability,
    TournamentActionRegistry,
    no_change_runner,
)
from klpga.tournament_context import resolve_context, SITE_REGISTRY_PATH  # noqa: E402
from klpga.tournament_cycle import CycleRequest, run_tournament_cycle  # noqa: E402
from klpga.tournament_lifecycle import (  # noqa: E402
    load_lifecycle_state,
    resolve_lifecycle,
    write_lifecycle_state,
)
from klpga.tournament_official_ingest import fetch_official_round  # noqa: E402
from klpga.tournament_operator import OperatorAction  # noqa: E402
import json  # noqa: E402


def _run_script(*relative_path: str) -> None:
    script = ROOT / "scripts" / Path(*relative_path)
    subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True)


def _script_runner(action: OperatorAction, *relative_path: str, message: str):
    def _run(context: ActionContext, decision) -> ActionResult:
        del context
        _run_script(*relative_path)
        return ActionResult(action=action, availability=ActionAvailability.READY, changed=True, message=message)
    return _run


def _promote_current_round(round_number_hint: int | None = None):
    """RUN_FINAL / RUN_NEXT_ROUND: collect official evidence for the
    live round, then run it through the candidate->validate->promote
    gate (build_current_round_page.py --promote) instead of the old
    direct docs/ write. The round to collect is the tournament's own
    current_round_number, resolved fresh each call -- never hardcoded."""
    def _run(context: ActionContext, decision) -> ActionResult:
        lifecycle = load_lifecycle_state()
        registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})
        tctx = resolve_context(lifecycle, registry)
        round_number = context.current_round_number or tctx.current_round_number
        evidence_dir = ROOT / "evidence" / f"current_round_{context.game_code}_r{round_number}"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "collect_current_round_evidence.py"),
             "--game-code", context.game_code, "--round", str(round_number), "--output", str(evidence_dir)],
            cwd=str(ROOT), check=True,
        )
        candidate = ROOT / "candidate" / f"current-round-{context.game_code}-r{round_number}.html"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_current_round_page.py"),
             "--snapshot", str(evidence_dir / "validated-current.json"),
             "--template", str(ROOT.parent / "docs" / tctx.url_base.strip("/") / f"r{round_number}" / "index.html"),
             "--output", str(candidate),
             "--tournament-name", tctx.tournament_name,
             "--promote"],
            cwd=str(ROOT), check=True,
        )
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message=f"round {round_number} evidence collected and promoted")
    return _run


def build_registry() -> TournamentActionRegistry:
    registry = TournamentActionRegistry()
    registry.register(OperatorAction.PREPARE_PRE, _prepare_pre_runner())
    registry.register(OperatorAction.RUN_R1, _script_runner(
        OperatorAction.RUN_R1, "96_ok_open_r1_active_cycle.py", message="R1 active cycle run"))
    registry.register(OperatorAction.CLOSE_R1, _script_runner(
        OperatorAction.CLOSE_R1, "98_ok_open_r1_final_reconciliation.py", message="R1 final reconciliation run"))
    registry.register(OperatorAction.RUN_R2, _script_runner(
        OperatorAction.RUN_R2, "99_ok_open_r2_live_recovery.py", message="R2 live recovery run"))
    registry.register(OperatorAction.CONFIRM_CUT, _script_runner(
        OperatorAction.CONFIRM_CUT, "100_recover_ok_open_post_r2_input.py", message="post-cut finalist field recovered"))
    registry.register(OperatorAction.RUN_FINAL, _promote_current_round())
    registry.register(OperatorAction.RUN_NEXT_ROUND, _promote_current_round())
    # No dedicated FINAL-reconciliation script exists yet in the real
    # operational chain (unlike CLOSE_R1's script 98) -- advance state
    # without inventing one, per "don't build new tournament-specific
    # scripts" and "fail closed rather than fabricate".
    registry.register(OperatorAction.CLOSE_FINAL, no_change_runner(
        OperatorAction.CLOSE_FINAL, message="final round validated complete; no dedicated close-final script yet"))
    registry.register(OperatorAction.POST_EVALUATE, _postmortem_runner())
    return registry


def _prepare_pre_runner():
    def _run(context: ActionContext, decision) -> ActionResult:
        del context
        _run_script("83_build_ok_open_pre_public_master.py")
        _run_script("84_build_ok_open_pre_website_candidate.py")
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message="PRE public master + candidate built")
    return _run


def _postmortem_runner():
    def _run(context: ActionContext, decision) -> ActionResult:
        from klpga.tournament_postmortem import run_postmortem
        lifecycle = load_lifecycle_state()
        registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})
        tctx = resolve_context(lifecycle, registry)
        result = run_postmortem(tctx)
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message=f"postmortem written: {result.output_path}")
    return _run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-code", required=True)
    ap.add_argument("--stage", help="override the inferred stage (manual resume/testing only)")
    ap.add_argument("--dry-run", action="store_true", help="print the decision only, run nothing")
    args = ap.parse_args()

    lifecycle = load_lifecycle_state()
    if str(lifecycle.get("game_code")) != args.game_code:
        raise SystemExit(
            f"HARD STOP: --game-code {args.game_code!r} does not match config/active_tournament.json's "
            f"active game_code {lifecycle.get('game_code')!r}. Run tournament discovery "
            "(klpga.tournament_discovery.refresh_active_config) to switch tournaments first."
        )

    registry_json = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})
    context = resolve_context(lifecycle, registry_json)
    snapshot = resolve_lifecycle(context, lifecycle)
    stage = args.stage or snapshot.stage

    print(f"=== run_tournament --game-code {args.game_code} ===")
    print(f"tournament: {context.tournament_name}")
    print(f"inferred stage: {snapshot.stage}" + (f" (overridden to {stage})" if args.stage else ""))
    print(f"current_round_number: {snapshot.current_round_number}")

    request = CycleRequest(
        game_code=context.game_code,
        final_round_number=context.final_round_number,
        current_round_number=snapshot.current_round_number,
        validated_stage=stage,
        model_ready=snapshot.model_ready,
    )

    if args.dry_run:
        from klpga.tournament_operator import decide_operator_action
        decision = decide_operator_action(
            stage=request.validated_stage,
            final_round_number=request.final_round_number,
            current_round_number=request.current_round_number,
            model_ready=request.model_ready,
        )
        print(f"DRY RUN decision: action={decision.action.value} reason={decision.reason!r}")
        return 0

    def official_fetcher(game_code: str, round_number: int):
        return fetch_official_round(
            game_code=game_code, round_number=round_number,
            cache_dir=ROOT / "evidence" / "official_cache" / game_code,
        )

    result = run_tournament_cycle(request, official_fetcher=official_fetcher, registry=build_registry())
    print(f"action: {result.decision.action.value}")
    print(f"availability: {result.action_result.availability.value}")
    print(f"changed: {result.action_result.changed}")
    print(f"message: {result.action_result.message}")

    if result.action_result.changed:
        refreshed = resolve_lifecycle(context, lifecycle)
        lifecycle["validated_stage"] = refreshed.stage
        lifecycle["current_round_number"] = refreshed.current_round_number
        write_lifecycle_state(lifecycle)
        print(f"lifecycle advanced: validated_stage={refreshed.stage} current_round_number={refreshed.current_round_number}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
