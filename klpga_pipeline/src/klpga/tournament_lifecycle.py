"""NEO TOURNAMENT PIPELINE items 2/5: bridge between real on-disk artifacts
(written by the existing per-stage scripts) and the already-existing,
already-tested generic engine (klpga.tournament_engine /
tournament_runtime / tournament_operator / tournament_cycle).

This module adds no new state-machine rules. It only answers one
question generically for any game_code: "given what has actually been
written to content/website_v2/ so far, which RoundFacts/TournamentFacts
does the real generic engine see?" -- so run_tournament.py can call the
existing determine_stage()/decide_operator_action()/run_tournament_cycle()
unchanged, instead of a tournament-specific reimplementation.

Known, documented simplification: expected_players for a round is taken
to be that round's own official_players count (the number of rows the
producing script actually wrote), not an independently re-verified
field size. This is safe rather than a silent gap because every script
that writes an r{N}_live_snapshot artifact (96, 99,
collect_current_round_evidence.py) already hard-stops internally if its
own official row count disagrees with what it expected -- so a written
snapshot is, by construction, one the upstream script already validated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

from klpga.tournament_context import ACTIVE_TOURNAMENT_PATH, TournamentContext
from klpga.tournament_discovery import (
    DiscoveredTournament,
    TournamentDiscoveryBlocked,
    discover_tournament,
    discover_tournament_by_game_code,
    refresh_active_config,
)
from klpga.tournament_engine import RoundFacts, TournamentFacts
from klpga.tournament_pre_state import build_pre_state_contract
from klpga.tournament_runtime import CutValidation, NON_CUT_STATUSES, resolve_runtime_stage, TournamentConfig


class TournamentLifecycleError(RuntimeError):
    pass


def load_lifecycle_state(path: Path = ACTIVE_TOURNAMENT_PATH) -> dict[str, Any]:
    """The validation-owned lifecycle fields active_tournament.json
    already carries (validated_stage, cut_after_round, model_ready) --
    read raw, never guessed, exactly like tournament_context._load_json."""
    if not path.is_file():
        raise TournamentLifecycleError(f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise TournamentLifecycleError(f"invalid JSON in {path}: {exc}") from exc


def write_lifecycle_state(payload: dict[str, Any], path: Path = ACTIVE_TOURNAMENT_PATH) -> None:
    """Atomic write-back, same tmp+replace pattern as
    klpga.tournament_discovery.refresh_active_config."""
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(path)


def bootstrap_lifecycle_state(
    discovered: DiscoveredTournament,
    *,
    final_round_number: int | None = None,
    cut_after_round: int | None = 2,
) -> dict[str, Any]:
    """NEO TOURNAMENT PIPELINE Phase 3 item 2: the real DISCOVERY step --
    first-time lifecycle bootstrap for a game_code with no prior
    validated lifecycle record (config/active_tournament.json missing,
    or naming a different tournament entirely). Uses ONLY real official
    identity (from DiscoveredTournament, itself sourced from
    tournament_master's official getGameList capture) plus universal
    state-machine starting values (round 1, stage DISCOVERED, model not
    ready) -- never a fabricated tournament FACT.

    final_round_number is the one field with no reliable
    always-present official source today (scripts/01's own docstring:
    "rounds_scheduled ... left NULL" when unconfirmed) -- resolved from
    tournament_master's rounds_scheduled if present, else from an
    explicit caller-supplied override (an operator who has confirmed it
    from the official site), else this fails closed rather than
    guessing 3 or 4.
    """
    resolved_final_round = (
        final_round_number if final_round_number is not None else discovered.rounds_scheduled
    )
    if resolved_final_round is None:
        raise TournamentLifecycleError(
            f"cannot bootstrap game_code={discovered.game_code!r}: final_round_number is not "
            "confirmed in tournament_master (rounds_scheduled is NULL) and was not supplied "
            "explicitly -- never fabricated. Pass an explicit final_round_number once confirmed "
            "from the official site."
        )
    if resolved_final_round < 2:
        raise TournamentLifecycleError(f"invalid final_round_number={resolved_final_round}")

    return {
        "schema_version": 2,
        "game_code": discovered.game_code,
        "tournament_name": discovered.tournament_name,
        "season": discovered.season,
        "start_date": discovered.start_date,
        "end_date": discovered.end_date,
        "final_round_number": resolved_final_round,
        "current_round_number": 1,
        "validated_stage": "DISCOVERED",
        "cut_after_round": cut_after_round,
        "model_ready": False,
        "identity_source": "tournament_master",
        "lifecycle_source": "bootstrap",
    }


def resolve_or_bootstrap_lifecycle(
    *,
    game_code: str | None,
    db_path: Path,
    final_round_number: int | None = None,
    cut_after_round: int = 2,
    as_of: date | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """The generic DISCOVERY entry point run_tournament.py calls before
    anything else, fixing the exact gap QA found ("does not perform/
    resolve tournament discovery" / "fails when active config differs").

    - game_code omitted, active_tournament.json already on file: keep
      using that tournament, refreshed via the existing generic
      refresh_active_config() (identity re-derived, lifecycle fields
      stay validation-owned).
    - game_code omitted, no file yet: discover "what's active today"
      from tournament_master and bootstrap it.
    - game_code given and it matches the file already on disk: same as
      the first case (an explicit confirmation, not a new tournament).
    - game_code given and it differs from (or there is no) existing
      file: a genuinely new tournament -- look it up directly in
      tournament_master (independent of today's date, so PRE work can
      start before the tournament's window opens) and bootstrap a fresh
      lifecycle record. NEVER requires a human to hand-edit
      active_tournament.json first.

    dry_run=True (Phase 5 item 12, DRY-RUN IMMUTABILITY): resolves and
    returns the SAME payload a real run would, but never writes
    active_tournament.json -- neither the refresh path nor the
    first-bootstrap path persists anything. A caller previewing a
    brand-new game_code with --dry-run gets back the in-memory
    bootstrapped payload to build a TournamentContext from, without
    ever touching disk.
    """
    as_of = as_of or date.today()

    # ACTIVE_TOURNAMENT_PATH resolved fresh here (never via another
    # function's default argument, which is bound once at import time
    # and would silently ignore a test's/caller's monkeypatched path).
    config_path = ACTIVE_TOURNAMENT_PATH
    existing = load_lifecycle_state(config_path) if config_path.is_file() else None
    existing_game_code = str(existing.get("game_code")) if existing else None

    if existing is not None and (game_code is None or str(game_code) == existing_game_code):
        try:
            return refresh_active_config(db_path=db_path, config_path=config_path, as_of=as_of, persist=not dry_run)
        except TournamentDiscoveryBlocked:
            # tournament_master doesn't (or can't, e.g. no DB in this
            # environment) confirm this tournament as active today --
            # the already-validated lifecycle state on disk is still
            # real and trustworthy; an unrelated discovery miss must
            # never destroy it.
            return existing

    target = game_code or existing_game_code
    if target is not None:
        discovered = discover_tournament_by_game_code(db_path, target)
    else:
        discovered = discover_tournament(db_path, as_of=as_of)

    payload = bootstrap_lifecycle_state(
        discovered, final_round_number=final_round_number, cut_after_round=cut_after_round
    )
    if not dry_run:
        write_lifecycle_state(payload, config_path)
    return payload


def _round_snapshot(context: TournamentContext, round_number: int) -> dict | None:
    path = context.artifact_path(f"r{round_number}_live_snapshot")
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _holes_completed(player: dict) -> int:
    """r{N}_live_snapshot player rows are not written by one single
    script (96, 99, collect_current_round_evidence.py each write their
    own), so holes_completed shows up as either a str or an int across
    real artifacts -- normalize rather than assume one shape."""
    value = player.get("holes_completed")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def infer_round_facts(context: TournamentContext, round_number: int) -> RoundFacts | None:
    """RoundFacts for one round from its real r{N}_live_snapshot artifact,
    or None if that round has not produced one yet (never fabricated)."""
    snapshot = _round_snapshot(context, round_number)
    if snapshot is None:
        return None
    players = snapshot.get("player_table") or []
    if not players:
        return None
    official = len(players)
    # WD/DQ/DNS players are exempt from "incomplete", matching the
    # engine's own klpga.tournament_runtime.NON_CUT_STATUSES -- a
    # withdrawn player's round is not "still in progress".
    incomplete = sum(
        1 for p in players
        if str(p.get("status") or "").strip().upper() not in NON_CUT_STATUSES
        and _holes_completed(p) != 18
    )
    return RoundFacts(
        round_number=round_number,
        expected_players=official,
        official_players=official,
        incomplete_players=incomplete,
        unresolved_players=0,
    )


def infer_cut_validated(context: TournamentContext, *, cut_after_round: int | None = 2) -> bool:
    """CUT CONTRACT (Phase 4 hardening, fix/phase5-generic-pipeline-
    hardening): a cut is treated as validated only once the post-cut
    finalist-field recovery artifact carries real, internally-
    consistent, non-stale cut-evidence provenance -- existence, or a
    bare advancing/pre count pair, is never sufficient on its own.

    cut_after_round=None means this tournament format has no cut at
    all (never assume every event cuts after round 2) -- validated is
    vacuously True so the generic engine's round progression is never
    blocked waiting on a cut confirmation that will never come.

    Required, all independently checked:
      - game_code on the artifact matches this context's own game_code
      - cut_round on the artifact matches the tournament's actual
        cut_after_round (never assumed to be round 2)
      - cut_evidence_sha256 matches a fresh hash of the CURRENT
        r2_live_snapshot file -- this is what catches a stale artifact
        (the real R2 snapshot has since been replaced/corrected) as
        well as a tampered/fabricated hash, not just "the field exists"
      - advancing_player_ids is a real, non-empty identity list (never
        count-only evidence) whose length matches advancing_field_size
      - advancing_field_size is STRICTLY smaller than pre_field_size --
        equal sizes are always rejected here (a copied, unfiltered PRE
        roster relabeled as the cut result must never pass)
    """
    if cut_after_round is None:
        return True
    path = context.artifact_path("post_r2_input")
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if str(payload.get("game_code")) != context.game_code:
        return False
    if payload.get("cut_round") != cut_after_round:
        return False
    if not payload.get("cut_evidence_source"):
        return False
    claimed_hash = payload.get("cut_evidence_sha256")
    if not claimed_hash:
        return False
    r2_snapshot_path = context.artifact_path("r2_live_snapshot")
    if not r2_snapshot_path.is_file():
        return False
    actual_hash = hashlib.sha256(r2_snapshot_path.read_bytes()).hexdigest()
    if claimed_hash != actual_hash:
        return False
    advancing_ids = payload.get("advancing_player_ids")
    advancing = payload.get("advancing_field_size")
    pre_size = payload.get("pre_field_size")
    if not isinstance(advancing_ids, list) or not advancing_ids:
        return False
    if advancing is None or pre_size is None:
        return False
    if len(advancing_ids) != int(advancing):
        return False
    return 0 < int(advancing) < int(pre_size)


def infer_post_evaluated(context: TournamentContext) -> bool:
    """True once a postmortem artifact exists for this game_code -- see
    klpga.tournament_postmortem, the generic Phase 2 item 4 connection
    point. Never inferred from dates or round completion alone."""
    return context.artifact_path("postmortem_report").exists()


def infer_tournament_facts(context: TournamentContext, *, cut_after_round: int | None = 2) -> TournamentFacts:
    """PRE STATE CONTRACT (Phase 5 item 3): entry_validated/pre_validated
    are never raw artifact existence -- see klpga.tournament_pre_state
    for the explicit ENTRY_VALIDATED/PRE_INPUTS_VALIDATED/
    PRE_FEATURES_FROZEN/PRE_MODEL_VALIDATED checks each of these
    booleans is actually built from. Read-only (freeze_if_ready=False):
    this function is called from dry-run previews too and must never
    have the side effect of freezing a new immutable feature archive --
    that only happens explicitly during a real PREPARE_PRE run (see
    run_tournament.py).

    cut_after_round (CUT CONTRACT, Phase 4 hardening) is threaded
    through to infer_cut_validated() -- never assumed to be round 2;
    None means this tournament format has no cut at all."""
    contract = build_pre_state_contract(context, freeze_if_ready=False)
    entry_validated = contract.entry_validated.valid
    pre_validated = contract.pre_ready
    rounds = [
        facts
        for n in range(1, context.final_round_number + 1)
        if (facts := infer_round_facts(context, n)) is not None
    ]
    return TournamentFacts(
        entry_validated=entry_validated,
        pre_validated=pre_validated,
        rounds=tuple(rounds),
        cut_validated=infer_cut_validated(context, cut_after_round=cut_after_round),
        final_round_number=context.final_round_number,
        post_evaluated=infer_post_evaluated(context),
    )


@dataclass(frozen=True)
class LifecycleSnapshot:
    context: TournamentContext
    facts: TournamentFacts
    stage: str
    current_round_number: int
    model_ready: bool
    cut_after_round: int | None


def resolve_lifecycle(context: TournamentContext, lifecycle: dict[str, Any]) -> LifecycleSnapshot:
    """The single place run_tournament.py calls to get 'what stage is
    this tournament really at, from real artifacts' -- built entirely
    from the existing generic engine (RoundFacts/TournamentFacts/
    resolve_runtime_stage), never a parallel state machine."""
    facts = infer_tournament_facts(context, cut_after_round=lifecycle.get("cut_after_round", 2))
    config = TournamentConfig(
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        final_round_number=context.final_round_number,
        cut_after_round=lifecycle.get("cut_after_round", 2),
    )
    stage = resolve_runtime_stage(
        config,
        entry_validated=facts.entry_validated,
        pre_validated=facts.pre_validated,
        rounds=facts.rounds,
        cut_validation=(
            CutValidation(validated=True, advancing=(), eliminated=(), exempt_status=(), unresolved=())
            if facts.cut_validated
            else None
        ),
        post_evaluated=facts.post_evaluated,
    )
    latest_round = max((r.round_number for r in facts.rounds), default=lifecycle.get("current_round_number", 1))
    return LifecycleSnapshot(
        context=context,
        facts=facts,
        stage=stage.value,
        current_round_number=latest_round,
        model_ready=bool(lifecycle.get("model_ready", False)),
        cut_after_round=lifecycle.get("cut_after_round", 2),
    )
