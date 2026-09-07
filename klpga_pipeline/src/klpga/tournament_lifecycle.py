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
import json
from pathlib import Path
from typing import Any

from klpga.tournament_context import ACTIVE_TOURNAMENT_PATH, TournamentContext
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
