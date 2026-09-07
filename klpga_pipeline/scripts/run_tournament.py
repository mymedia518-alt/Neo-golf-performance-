"""NEO TOURNAMENT PIPELINE items 2/5 (Phase 3 hardening): single generic
entry point.

    run_tournament.py [--game-code <GAME_CODE>] [--stage STAGE]
                       [--dry-run] [--git-push]
                       [--db PATH] [--final-round-number N] [--cut-after-round N]

Drives DISCOVERY -> METADATA -> ENTRY LIST -> IDENTITY -> PRE
PREREQUISITES -> PRE FREEZE -> PRE -> R1 -> R2 -> R3/R4 -> FINAL ->
POSTMORTEM through the SAME already-existing, already-tested generic
engine every tournament shares:

    klpga.tournament_lifecycle   -- DISCOVERY/bootstrap + real artifacts
                                     -> RoundFacts/TournamentFacts
    klpga.tournament_entry_bootstrap -- ENTRY LIST / IDENTITY prerequisite
    klpga.tournament_runtime     -- RoundFacts/TournamentFacts -> Stage
    klpga.tournament_operator    -- Stage -> OperatorAction
    klpga.tournament_action_registry / tournament_cycle
                                  -- OperatorAction -> dispatch + official
                                     preflight fetch

Phase 3 fixes two real architecture gaps a QA pass found in the Phase 2
version of this script:

1. --game-code is now OPTIONAL and this script performs DISCOVERY
   itself (klpga.tournament_lifecycle.resolve_or_bootstrap_lifecycle):
   a brand-new game_code with no prior config/active_tournament.json
   record bootstraps a fresh lifecycle from real tournament_master
   identity, instead of requiring an operator to hand-edit that file
   first. Never fabricates final_round_number -- fails closed if
   tournament_master doesn't confirm it and --final-round-number isn't
   given.
2. The DISCOVERED -> ENTRY_READY prerequisite (official entry list +
   identity) is now attempted automatically
   (klpga.tournament_entry_bootstrap), not silently skipped -- so a
   brand-new tournament actually progresses instead of parking at WAIT
   forever once its entry list is genuinely published.

This script's own job is still narrow and does not reimplement any of
the above: it only (a) resolves/bootstraps identity and the entry-list
prerequisite, (b) builds a TournamentActionRegistry whose runners
invoke the existing per-stage scripts -- 83/84/96/98/99/100/101 and
build_current_round_page.py -- which Phase 1/2 already verified are
internally generic (TournamentContext-driven, no game_code/tournament-
name literals), and are therefore eligible generic runners per
docs/NEO_TOURNAMENT_LEGACY_ACTION_BLOCKERS.md's own stated condition
("eligible ... only after their tournament-specific assumptions are
removed"). No numbered/named script is ever selected implicitly for an
action with no registered runner -- TournamentActionRegistry.execute()
already hard-blocks that case, per the same policy document, and (c)
persists the freshly-inferred stage back to config/active_tournament.json
so the next invocation resumes from real state instead of a stale
hand-maintained field.

--git-push (Phase 3): after a changed action, commits and pushes
whatever files the action actually touched (discovered generically via
`git status --porcelain`, never a hardcoded path list) so this one
script can be the entire body of a scheduled task -- see
NEO-GOLF-R1-ACTIVE-30MIN.ps1, which now calls this script instead of
directly invoking 96_ok_open_r1_active_cycle.py. The final stdout line
is a JSON summary carrying a stop_active_cycle field (true once
POSTMORTEM has genuinely run), the same contract that PS1 wrapper
already knows how to parse to auto-disable its own schedule.

Resumable and non-destructive: every runner below invokes a script that
is itself safe to re-run (96/98/99/100/101/83/84/94 already assert
their own preconditions and hard-stop rather than silently redo
already-validated work; build_current_round_page.py's --promote gate
only writes docs/ once a byte-for-byte-verified candidate exists).

Sandbox note: any LIVE-stage action requires a real klpga.co.kr fetch
(the tournament_cycle official-data preflight, and/or the dispatched
script's own ingest) -- there is no offline stand-in, by design ("fail
loudly rather than silently" per klpga.tournament_cycle). Use --dry-run
to see the decision only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402

from klpga.tournament_action_registry import (  # noqa: E402
    ActionContext,
    ActionResult,
    ActionAvailability,
    TournamentActionRegistry,
    no_change_runner,
)
from klpga.tournament_context import resolve_context, SITE_REGISTRY_PATH  # noqa: E402
from klpga.tournament_cycle import CycleRequest, run_tournament_cycle  # noqa: E402
from klpga.tournament_entry_bootstrap import EntryListBootstrapBlocked, collect_entry_list_snapshot  # noqa: E402
from klpga.tournament_lifecycle import (  # noqa: E402
    resolve_lifecycle,
    resolve_or_bootstrap_lifecycle,
    write_lifecycle_state,
)
from klpga.tournament_official_ingest import fetch_official_round  # noqa: E402
from klpga.tournament_operator import OperatorAction  # noqa: E402

DEFAULT_DB_PATH = ROOT / "data" / "klpga.sqlite"


def _run_script(*relative_path: str) -> None:
    script = ROOT / "scripts" / Path(*relative_path)
    subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True)


def _load_registry_json() -> dict:
    return json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})


def _script_runner(action: OperatorAction, *relative_path: str, message: str):
    def _run(context: ActionContext, decision) -> ActionResult:
        del context
        _run_script(*relative_path)
        return ActionResult(action=action, availability=ActionAvailability.READY, changed=True, message=message)
    return _run


def _promote_current_round():
    """RUN_FINAL / RUN_NEXT_ROUND: collect official evidence for the
    live round, then run it through the candidate->validate->promote
    gate (build_current_round_page.py --promote) instead of the old
    direct docs/ write. The round to collect is the tournament's own
    current_round_number, resolved fresh each call -- never hardcoded."""
    def _run(context: ActionContext, decision) -> ActionResult:
        lifecycle = resolve_or_bootstrap_lifecycle(game_code=context.game_code, db_path=DEFAULT_DB_PATH)
        tctx = resolve_context(lifecycle, _load_registry_json())
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
             "--template", str(REPO_ROOT / "docs" / tctx.url_base.strip("/") / f"r{round_number}" / "index.html"),
             "--output", str(candidate),
             "--tournament-name", tctx.tournament_name,
             "--promote"],
            cwd=str(ROOT), check=True,
        )
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message=f"round {round_number} evidence collected and promoted")
    return _run


def _prepare_pre_runner():
    """PREPARE_PRE: 83/84 are already verified generic (TournamentContext
    -driven), but they themselves depend on upstream PRE-freeze artifacts
    (tier2_publication_gate, current_player_master, SG-band computation)
    that are NOT yet generalized -- see the module docstring. Their own
    HARD_STOP assertions already fail closed on a missing prerequisite;
    this runner just re-raises that as an honest, actionable message
    instead of a bare traceback."""
    def _run(context: ActionContext, decision) -> ActionResult:
        del context
        try:
            _run_script("83_build_ok_open_pre_public_master.py")
            _run_script("84_build_ok_open_pre_website_candidate.py")
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "PRE prerequisites incomplete: the PRE-freeze input chain "
                "(tier2_publication_gate / current_player_master / SG-band artifacts) "
                "is not yet generalized and must be produced first -- see "
                "src/klpga/tournament_entry_bootstrap.py's module docstring for what IS "
                "automated (entry list) versus what still requires manual data prep."
            ) from exc
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message="PRE public master + candidate built")
    return _run


def _postmortem_runner():
    def _run(context: ActionContext, decision) -> ActionResult:
        from klpga.tournament_postmortem import run_postmortem
        lifecycle = resolve_or_bootstrap_lifecycle(game_code=context.game_code, db_path=DEFAULT_DB_PATH)
        tctx = resolve_context(lifecycle, _load_registry_json())
        result = run_postmortem(tctx)
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message=f"postmortem written: {result.output_path}")
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


def _attempt_entry_list_prerequisite(context, lifecycle) -> None:
    """The generic ENTRY LIST / IDENTITY prerequisite. Attempted
    whenever it hasn't succeeded yet; a genuine "not published yet"
    outcome is swallowed here so the normal decide_operator_action()
    WAIT stands -- this is a best-effort prerequisite attempt, not
    itself a lifecycle stage with its own OperatorAction."""
    if context.artifact_path("entry_snapshot").exists():
        return
    try:
        collect_entry_list_snapshot(context, cache_dir=ROOT / "evidence" / "official_cache" / context.game_code)
        print(f"ENTRY LIST collected for {context.game_code}")
    except EntryListBootstrapBlocked as exc:
        print(f"ENTRY LIST not ready yet: {exc}")
    except requests.exceptions.RequestException as exc:
        # A real network failure (offline sandbox, klpga.co.kr
        # unreachable, proxy block) is exactly the same kind of "can't
        # confirm this fact right now" outcome as "not published yet" --
        # never fabricate a snapshot, just leave entry_validated False
        # so decide_operator_action's own WAIT stands, instead of
        # crashing the whole cycle over one best-effort prerequisite.
        print(f"ENTRY LIST fetch failed (network): {exc}")


def _git_push_changes(game_code: str, action: str) -> bool:
    """Generic post-action commit+push: stage and commit whatever files
    this run actually changed (discovered via `git status --porcelain`,
    never a hardcoded per-tournament path list), so this one script can
    be a scheduled task's entire body regardless of which stage it just
    advanced."""
    status = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    changed_paths = [line[3:] for line in status.stdout.splitlines() if line.strip()]
    if not changed_paths:
        print("git-push requested but nothing changed; skipping commit")
        return False
    subprocess.run(["git", "add", *changed_paths], cwd=str(REPO_ROOT), check=True)
    message = f"run_tournament: {game_code} {action}\n\nAutomated by scripts/run_tournament.py --git-push."
    subprocess.run(["git", "commit", "-m", message], cwd=str(REPO_ROOT), check=True)
    subprocess.run(["git", "push"], cwd=str(REPO_ROOT), check=True)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-code", default=None,
                     help="omit to resolve the currently active tournament, or bootstrap the one "
                          "named here if it has no prior lifecycle record")
    ap.add_argument("--stage", help="override the inferred stage (manual resume/testing only)")
    ap.add_argument("--dry-run", action="store_true", help="print the decision only, run nothing")
    ap.add_argument("--git-push", action="store_true",
                     help="after a changed action, commit+push whatever files it touched")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="tournament_master DB for discovery")
    ap.add_argument("--final-round-number", type=int, default=None,
                     help="required only to bootstrap a brand-new game_code whose official round "
                          "count isn't yet confirmed in tournament_master")
    ap.add_argument("--cut-after-round", type=int, default=2,
                     help="only used when bootstrapping a brand-new game_code (default: 2)")
    args = ap.parse_args()

    lifecycle = resolve_or_bootstrap_lifecycle(
        game_code=args.game_code, db_path=args.db,
        final_round_number=args.final_round_number, cut_after_round=args.cut_after_round,
    )

    registry_json = _load_registry_json()
    context = resolve_context(lifecycle, registry_json)

    _attempt_entry_list_prerequisite(context, lifecycle)

    snapshot = resolve_lifecycle(context, lifecycle)
    stage = args.stage or snapshot.stage

    print(f"=== run_tournament --game-code {context.game_code} ===")
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

    try:
        result = run_tournament_cycle(request, official_fetcher=official_fetcher, registry=build_registry())
        action = result.decision.action.value
        availability = result.action_result.availability.value
        changed = result.action_result.changed
        message = result.action_result.message
        error = None
    except Exception as exc:  # noqa: BLE001 -- summarized honestly below, never swallowed
        action = "ERROR"
        availability = "BLOCKED"
        changed = False
        message = str(exc)
        error = exc

    print(f"action: {action}")
    print(f"availability: {availability}")
    print(f"changed: {changed}")
    print(f"message: {message}")

    stage_after = stage
    if changed:
        refreshed = resolve_lifecycle(context, lifecycle)
        lifecycle["validated_stage"] = refreshed.stage
        lifecycle["current_round_number"] = refreshed.current_round_number
        write_lifecycle_state(lifecycle)
        stage_after = refreshed.stage
        print(f"lifecycle advanced: validated_stage={refreshed.stage} current_round_number={refreshed.current_round_number}")

    committed = False
    if changed and args.git_push:
        committed = _git_push_changes(context.game_code, action)

    print(json.dumps({
        "game_code": context.game_code,
        "action": action,
        "stage": stage_after,
        "changed": changed,
        "committed": committed,
        "stop_active_cycle": stage_after == "POST_EVALUATED" and changed,
    }, ensure_ascii=False))

    if error is not None:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
