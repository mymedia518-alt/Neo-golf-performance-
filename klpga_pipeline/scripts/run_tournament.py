"""NEO TOURNAMENT PIPELINE items 2/5 (Phase 5 hardening): single generic
entry point.

    run_tournament.py [--game-code <GAME_CODE>] [--stage STAGE]
                       [--dry-run] [--live] [--git-push]
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

--live (Phase 5 item 7): explicit, generic opt-in for real official-data
collection, mirroring the "safe by default" convention scripts 96/98
already use on their own. Without --live, RUN_R1/CLOSE_R1 never pass
--live down to 96/98 (so THEY stay in their own safe dry mode) and
RUN_R2/CONFIRM_CUT/RUN_NEXT_ROUND/RUN_FINAL are skipped entirely
(WAIT, changed=False) rather than making real network calls. This
closes a real regression: before this flag existed, the registered
scheduled path (NEO-GOLF-R1-ACTIVE-30MIN.ps1 -> this script) never
passed --live to anything, so it could never actually collect live
data through the generic entry point at all.

--dry-run: prints the decision only. NOTHING is written -- not
active_tournament.json, not the site registry, not the entry-list
artifact, not any candidate/docs/database file (Phase 5 item 12,
DRY-RUN IMMUTABILITY). Every lifecycle/registry-bootstrap call below is
threaded with dry_run=True in that mode so it resolves and previews
identity without ever persisting anything, even for a brand-new
game_code that has no prior record at all.

This script's own job is still narrow and does not reimplement any of
the above: it only (a) resolves/bootstraps identity and the entry-list
prerequisite, (b) builds a TournamentActionRegistry whose runners
invoke the existing per-stage scripts -- the PRE-upstream chain
(67/69/72/73/75/79/81/82/83/84, see _PRE_UPSTREAM_CHAIN below) plus
96/98/99/100/101 and build_current_round_page.py -- which Phase
1/2/4/5 already verified are internally generic (TournamentContext
-driven, no game_code/tournament-name/Windows-path literals), and are
therefore eligible generic runners per
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
NEO-GOLF-R1-ACTIVE-30MIN.ps1, which calls this script with --live
--git-push. The final stdout line is a JSON summary carrying a
stop_active_cycle field (true once POSTMORTEM has genuinely run), the
same contract that PS1 wrapper already knows how to parse to
auto-disable its own schedule.

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
from klpga.tournament_context import ensure_site_registry_entry, resolve_context  # noqa: E402
from klpga.tournament_cycle import CycleRequest, run_tournament_cycle  # noqa: E402
from klpga.tournament_engine import Stage  # noqa: E402
from klpga.tournament_entry_bootstrap import EntryListBootstrapBlocked, collect_entry_list_snapshot  # noqa: E402
from klpga.tournament_lifecycle import (  # noqa: E402
    resolve_lifecycle,
    resolve_or_bootstrap_lifecycle,
    write_lifecycle_state,
)
from klpga.tournament_official_ingest import fetch_official_round  # noqa: E402
from klpga.tournament_operator import OperatorAction  # noqa: E402

DEFAULT_DB_PATH = ROOT / "data" / "klpga.sqlite"


def _run_script(*relative_path: str, extra_args: list[str] | None = None) -> tuple[int, str]:
    """Run a scripts/<relative_path> child process, returning (returncode,
    combined stdout). Output is still echoed to this process's own
    stdout (an operator/scheduled-task log must show it), but is also
    captured so callers can read the script's own final JSON summary
    line to determine whether it actually changed anything (Phase 5
    item 7, "action runner changed status must reflect actual
    changes") instead of assuming every successful run changed state."""
    script = ROOT / "scripts" / Path(*relative_path)
    result = subprocess.run(
        [sys.executable, str(script), *(extra_args or [])],
        cwd=str(ROOT), check=True, capture_output=True, text=True,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    return result.returncode, result.stdout


def _last_json_line(stdout: str) -> dict | None:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _load_registry_json() -> dict:
    from klpga.tournament_context import SITE_REGISTRY_PATH
    return json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})


def _live_gated_script_runner(action: OperatorAction, script_name: str, *, changed_actions: frozenset[str], message: str):
    """RUN_R1 (96) / CLOSE_R1 (98): both already support their own
    --live opt-in (safe dry mode without it). --live is forwarded only
    when context.live is True -- never inferred, never defaulted on.
    `changed` is read back from the script's own final JSON summary
    line rather than assumed True, so a SKIP_WAIT/DRY_RUN/no-op cycle
    correctly reports changed=False (Phase 5 item 7)."""
    def _run(context: ActionContext, decision) -> ActionResult:
        extra = ["--live"] if context.live else []
        _, stdout = _run_script(script_name, extra_args=extra)
        summary = _last_json_line(stdout) or {}
        script_action = str(summary.get("action") or "")
        changed = script_action in changed_actions
        availability = ActionAvailability.READY if changed else ActionAvailability.WAIT
        reason = summary.get("reason")
        detail = f"{message}: {script_action}" + (f" ({reason})" if reason else "")
        return ActionResult(action=action, availability=availability, changed=changed, message=detail)
    return _run


def _live_gated_network_runner(action: OperatorAction, runner):
    """RUN_R2 / CONFIRM_CUT / RUN_NEXT_ROUND / RUN_FINAL: these dispatch
    to scripts (99, 100, collect_current_round_evidence.py) that make
    real official-data HTTP calls unconditionally, with no --live flag
    of their own to gate on. Rather than editing each of those scripts'
    own CLI contract, run_tournament.py itself refuses to invoke them
    at all unless --live was passed -- so a plain (non---live) run of
    this script never makes an official network call for these stages,
    matching every other stage's "safe by default" contract."""
    def _run(context: ActionContext, decision) -> ActionResult:
        if not context.live:
            return ActionResult(
                action=action, availability=ActionAvailability.WAIT, changed=False,
                message="--live not set; this stage requires a real official-data fetch and was skipped",
            )
        return runner(context, decision)
    return _run


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
    direct docs/ write.

    ROUND ORCHESTRATION (Phase 5 item 7): the round to collect is NOT
    always the tournament's own last-known current_round_number --
    that number tracks the highest round with ANY snapshot written,
    which stays the SAME round while it's still live. Only once
    decide_operator_action's decision.stage says that round is fully
    COMPLETE (CUT_CONFIRMED just after R2, or NEXT_ROUND_COMPLETE) does
    the NEXT round actually need a first snapshot -- i.e. the round to
    collect is current_round_number + 1. Getting this wrong re-collects
    the round that already finished instead of advancing (the exact
    bug QA found: "next collector must collect N+1")."""
    def _run(context: ActionContext, decision) -> ActionResult:
        lifecycle = resolve_or_bootstrap_lifecycle(game_code=context.game_code, db_path=DEFAULT_DB_PATH)
        tctx = resolve_context(lifecycle, _load_registry_json())
        base_round = context.current_round_number or tctx.current_round_number
        if decision.stage in (Stage.CUT_CONFIRMED, Stage.NEXT_ROUND_COMPLETE):
            round_number = base_round + 1
        else:
            round_number = base_round
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


# PRE UPSTREAM CHAIN (NEO TOURNAMENT PIPELINE Phase 4): every script that
# produces a PRE-freeze prerequisite, all TournamentContext-driven (no
# game_code/date/Windows-path/tournament-name literals -- see each
# script's own module docstring), in dependency order:
#   67 entry_snapshot (if not already collected) + pre_performance_snapshot
#   69 pre_performance_corrected_v2 (classifier v2, feeds 73)
#   72 current_player_master / official_klpga_ranking / pre_win_forecast /
#      neo_pre_ranking_evidence / pre_sg_total_rank
#   73 pre_public_master (draft -- see its own docstring on the 83 overwrite)
#   75 data_center_profile_audit
#   79 pre_performance_row_retention_corrected_v2 (needs 73's draft + the
#      shared historical_sg_warehouse_corrected_v2.json -- see NOTE below)
#   81 tier2_publication_gate (BLOCKs/HARD_STOPs on a still-pending
#      prerequisite, including the one genuinely manual step: the
#      independent human sign-off at OK_OPEN_2026_SG_INDEPENDENT_ACCEPTANCE.json
#      -- never auto-generated, per klpga.neo_win.tier2_publication_gate)
#   82 pre_sg_total_rank_corrected_v2
#   83 canonical pre_public_master (raises SystemExit if Tier-2 isn't PASS
#      -- this IS the fail-closed contract, not a bug to route around)
#   84 PRE website candidate
#
# NOTE: 79/82/81's SG_DERIVED check read historical_sg_warehouse_corrected_v2.json
# and its audit -- a SHARED, cross-tournament artifact built by scripts
# 77/78/80 from every historical event, not this tournament's own data.
# It is not rebuilt per-tournament here; if it doesn't exist yet in a
# fresh environment, run 77 (or 78) then 80 once first.
_PRE_UPSTREAM_CHAIN = (
    "67_build_ok_open_pre_performance.py",
    "69_build_ok_open_classifier_v2.py",
    "72_collect_ok_open_public_master.py",
    "73_build_ok_open_performance_bands.py",
    "75_audit_klpga_datacenter_profiles.py",
    "79_rebuild_corrected_sg_downstream.py",
    "81_build_tier2_publication_gate.py",
    "82_build_corrected_sg_total_rank.py",
    "83_build_ok_open_pre_public_master.py",
    "84_build_ok_open_pre_website_candidate.py",
)


def _prepare_pre_runner():
    """PREPARE_PRE: run the full PRE-upstream chain (see _PRE_UPSTREAM_CHAIN),
    every step TournamentContext-driven so a brand-new game_code needs no
    source edits. Each step's own HARD_STOP/SystemExit (missing official
    data, network unreachable, or the still-pending manual SG acceptance
    sign-off) is fail-closed by design -- never fabricated -- so this
    runner re-raises it as an honest, actionable "which step, why" message
    instead of a bare traceback, rather than trying to work around it.

    Not gated behind --live: PRE preparation is a one-time-per-tournament
    setup phase (unlike R1's repeated 30-minute live polling), and every
    step already fails closed on its own missing prerequisite -- there is
    no meaningful "dry" variant of building the PRE artifacts.

    After the chain runs, builds and persists the explicit PRE state
    contract (klpga.tournament_pre_state, Phase 5 item 3) -- this is
    also the one place freeze_active_pre_features() is actually
    triggered (freeze_if_ready=True), wiring the previously-orphaned
    freeze_pre_model_features() into the real lifecycle. Never done
    during --dry-run (this runner is only ever reached from a real,
    non-dry-run cycle)."""
    def _run(context: ActionContext, decision) -> ActionResult:
        for script_name in _PRE_UPSTREAM_CHAIN:
            try:
                _run_script(script_name)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"PRE prerequisites incomplete at scripts/{script_name}: this step's "
                    "own required input isn't available yet -- official data not yet "
                    "published, network unreachable from this environment, the shared "
                    "historical_sg_warehouse_corrected_v2.json/audit not built yet (run "
                    "77/78 then 80 once), or the independent human SG acceptance "
                    "sign-off (OK_OPEN_2026_SG_INDEPENDENT_ACCEPTANCE.json / its "
                    "per-tournament equivalent) is still pending. Never fabricated -- "
                    "resolve the underlying prerequisite and rerun."
                ) from exc
        from klpga.tournament_pre_state import build_pre_state_contract
        lifecycle = resolve_or_bootstrap_lifecycle(game_code=context.game_code, db_path=DEFAULT_DB_PATH)
        tctx = resolve_context(lifecycle, _load_registry_json())
        contract = build_pre_state_contract(tctx, freeze_if_ready=True)
        tctx.artifact_path("pre_state_contract").write_text(
            json.dumps(contract.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message="PRE upstream chain built through PRE public master + website candidate")
    return _run


def _close_final_runner():
    """CLOSE_FINAL (Phase 5 item 9): reached only when Stage.FINAL_COMPLETE
    -- the official final round is validated complete but POSTMORTEM has
    not run yet. THIS is the action that must actually produce the
    terminal postmortem_report artifact (previously this was wired to a
    no-op, which meant FINAL_COMPLETE/CLOSE_FINAL never advanced at all:
    an infinite stuck loop, since nothing ever created the artifact that
    would let determine_stage() move on to POST_EVALUATED). Idempotent:
    if postmortem_report already exists (e.g. a retry after a partial
    git-push failure), this is a no-op rather than recomputing and
    rewriting an already-final artifact."""
    def _run(context: ActionContext, decision) -> ActionResult:
        from klpga.tournament_postmortem import run_postmortem
        lifecycle = resolve_or_bootstrap_lifecycle(game_code=context.game_code, db_path=DEFAULT_DB_PATH)
        tctx = resolve_context(lifecycle, _load_registry_json())
        report_path = tctx.artifact_path("postmortem_report")
        if report_path.exists():
            return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=False,
                                 message=f"final already closed; postmortem already exists at {report_path}")
        result = run_postmortem(tctx)
        return ActionResult(action=decision.action, availability=ActionAvailability.READY, changed=True,
                             message=f"final closed; postmortem written: {result.output_path}")
    return _run


def build_registry() -> TournamentActionRegistry:
    registry = TournamentActionRegistry()
    registry.register(OperatorAction.PREPARE_PRE, _prepare_pre_runner())
    registry.register(OperatorAction.RUN_R1, _live_gated_script_runner(
        OperatorAction.RUN_R1, "96_ok_open_r1_active_cycle.py",
        changed_actions=frozenset({"PUBLISH", "PUBLISH_AND_CLOSE"}), message="R1 active cycle"))
    registry.register(OperatorAction.CLOSE_R1, _live_gated_script_runner(
        OperatorAction.CLOSE_R1, "98_ok_open_r1_final_reconciliation.py",
        changed_actions=frozenset({"FINAL_RECONCILED"}), message="R1 final reconciliation"))
    registry.register(OperatorAction.RUN_R2, _live_gated_network_runner(OperatorAction.RUN_R2, _script_runner(
        OperatorAction.RUN_R2, "99_ok_open_r2_live_recovery.py", message="R2 live recovery run")))
    registry.register(OperatorAction.CONFIRM_CUT, _live_gated_network_runner(OperatorAction.CONFIRM_CUT, _script_runner(
        OperatorAction.CONFIRM_CUT, "100_recover_ok_open_post_r2_input.py", message="post-cut finalist field recovered")))
    registry.register(OperatorAction.RUN_FINAL, _live_gated_network_runner(OperatorAction.RUN_FINAL, _promote_current_round()))
    registry.register(OperatorAction.RUN_NEXT_ROUND, _live_gated_network_runner(OperatorAction.RUN_NEXT_ROUND, _promote_current_round()))
    registry.register(OperatorAction.CLOSE_FINAL, _close_final_runner())
    # POST_EVALUATE is reached only once Stage.POST_EVALUATED already
    # holds -- i.e. postmortem_report already exists (see
    # tournament_lifecycle.infer_post_evaluated / tournament_engine
    # .determine_stage). There is nothing left to do; CLOSE_FINAL above
    # is what actually produces that artifact. Registering this as
    # anything other than a no-op would re-run postmortem forever.
    registry.register(OperatorAction.POST_EVALUATE, no_change_runner(
        OperatorAction.POST_EVALUATE, message="post-event evaluation already complete"))
    return registry


def _attempt_entry_list_prerequisite(context, lifecycle) -> None:
    """The generic ENTRY LIST / IDENTITY prerequisite. Attempted
    whenever it hasn't succeeded yet; a genuine "not published yet"
    outcome is swallowed here so the normal decide_operator_action()
    WAIT stands -- this is a best-effort prerequisite attempt, not
    itself a lifecycle stage with its own OperatorAction. Never called
    in --dry-run mode (see main()) -- Phase 5 item 12."""
    if context.artifact_path("entry_snapshot").exists():
        return
    try:
        collect_entry_list_snapshot(
            context,
            cache_dir=ROOT / "evidence" / "official_cache" / context.game_code,
            db_path=DEFAULT_DB_PATH,
        )
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
    ap.add_argument("--dry-run", action="store_true",
                     help="print the decision only; NEVER writes active_tournament.json, the site "
                          "registry, the entry snapshot, or any other artifact (Phase 5 item 12)")
    ap.add_argument("--live", action="store_true",
                     help="opt in to real official-data collection (HTTP fetches); without this, "
                          "every live-collection stage stays in its own safe/no-op default (Phase 5 item 7)")
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
        dry_run=args.dry_run,
    )

    registry_json = ensure_site_registry_entry(lifecycle, dry_run=args.dry_run)
    context = resolve_context(lifecycle, registry_json)

    if not args.dry_run:
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
        live=args.live,
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
