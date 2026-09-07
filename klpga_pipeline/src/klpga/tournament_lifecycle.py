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
            return refresh_active_config(db_path=db_path, config_path=config_path, as_of=as_of)
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


def infer_cut_validated(context: TournamentContext) -> bool:
    """A cut is treated as validated once the post-cut finalist-field
    recovery artifact exists -- script 100's real chain only writes
    post_r2_input after asserting the confirmed field size, so its
    presence is the real cut-confirmation fact, not a guess. Generic:
    the artifact_type name is not tied to any one tournament, and a
    tournament with no registry mapping still resolves it via
    TournamentContext.artifact_path()'s generic fallback."""
    return context.artifact_path("post_r2_input").exists()


def infer_post_evaluated(context: TournamentContext) -> bool:
    """True once a postmortem artifact exists for this game_code -- see
    klpga.tournament_postmortem, the generic Phase 2 item 4 connection
    point. Never inferred from dates or round completion alone."""
    return context.artifact_path("postmortem_report").exists()


def infer_tournament_facts(context: TournamentContext) -> TournamentFacts:
    entry_validated = context.artifact_path("entry_snapshot").exists()
    pre_validated = context.artifact_path("pre_win_forecast").exists()
    rounds = [
        facts
        for n in range(1, context.final_round_number + 1)
        if (facts := infer_round_facts(context, n)) is not None
    ]
    return TournamentFacts(
        entry_validated=entry_validated,
        pre_validated=pre_validated,
        rounds=tuple(rounds),
        cut_validated=infer_cut_validated(context),
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
    facts = infer_tournament_facts(context)
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
