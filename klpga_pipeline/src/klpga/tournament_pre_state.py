"""NEO TOURNAMENT PIPELINE Phase 5 item 3: explicit PRE state/provenance
contract.

Artifact existence must NEVER equal validated stage. Before this module,
`tournament_lifecycle.infer_tournament_facts()` set `entry_validated` and
`pre_validated` purely from `Path.exists()` checks -- a truncated entry
snapshot, an unresolved-identity field, or a draft (never-tier2-approved)
`pre_public_master` would all have counted as "validated" merely by
being present on disk. This module defines five explicit, independently
inspectable checks:

    ENTRY_VALIDATED          -- validate_entry()
    PRE_INPUTS_VALIDATED     -- validate_pre_inputs()
    PRE_FEATURES_FROZEN      -- validate_pre_features_frozen() / freeze_active_pre_features()
    PRE_MODEL_VALIDATED      -- validate_pre_model()
    PRE_PUBLICATION_APPROVED -- validate_pre_publication()

Each returns a StateCheck(valid, reasons) -- reasons is always populated
when valid is False, so a partial/incomplete PRE never silently reads as
done; an operator or test can see exactly which check failed and why.
`PreStateContract.pre_ready` (used to gate Stage.PRE_READY) is the AND
of ALL FIVE checks, including PRE_PUBLICATION_APPROVED -- data/model
readiness alone must never advance a tournament into PRE_READY while
the public website candidate has not actually been built/approved.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from pathlib import Path

from datetime import datetime, timezone

from klpga.neo_win.archive import (
    NeoWinAlreadyArchivedError,
    NeoWinEntrantSnapshot,
    NeoWinPredictionSnapshot,
    RECORD_KIND,
    archive_paths,
)
from klpga.tournament_context import CONTENT_DIR, TournamentContext
from klpga.tournament_feature_freeze import FrozenFeatureRef, freeze_pre_model_features


@dataclass(frozen=True)
class StateCheck:
    name: str
    valid: bool
    reasons: tuple[str, ...] = ()

    @staticmethod
    def ok(name: str) -> "StateCheck":
        return StateCheck(name=name, valid=True, reasons=())

    @staticmethod
    def fail(name: str, *reasons: str) -> "StateCheck":
        return StateCheck(name=name, valid=False, reasons=tuple(reasons))


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def validate_entry(context: TournamentContext) -> StateCheck:
    """ENTRY_VALIDATED: the frozen entry_snapshot must exist AND be
    internally consistent -- never just "the file is there". Rejects
    duplicate player_ids, unresolved identity, unparsed rows, a
    player_count that disagrees with the number of entry rows actually
    present, AND (PRE contract hardening, fix/phase5-pre-contract-gates)
    a snapshot where canonical player_master identity matching was
    never actually performed.

    "identity matching actually performed" is judged from real
    per-entry evidence, not merely the top-level identity_matched
    summary string: klpga.tournament_entry_bootstrap's explicit
    "not attempted (no player_master DB in this run)" sentinel is one
    real signal, but that same producer also leaves every entry's own
    identity_match field as None in that exact case -- so an entry_snapshot
    where identity_match is None/missing for some or all rows fails
    here regardless of what the summary string happens to say (older
    schemas have been observed with an ambiguous/absent summary field
    despite carrying real per-entry evidence, and the reverse must
    never be trusted either)."""
    name = "ENTRY_VALIDATED"
    path = context.artifact_path("entry_snapshot")
    payload = _read_json(path)
    if payload is None:
        return StateCheck.fail(name, f"entry_snapshot missing or unreadable at {path}")
    reasons: list[str] = []
    entries = payload.get("entries") or []
    if not entries:
        reasons.append("entry_snapshot has zero entries")
    player_count = payload.get("player_count")
    if player_count is None or int(player_count) != len(entries):
        reasons.append(f"player_count={player_count!r} disagrees with {len(entries)} entry rows")
    duplicates = payload.get("duplicate_player_ids") or []
    if duplicates:
        reasons.append(f"{len(duplicates)} duplicate player_id(s): {duplicates}")
    unparsed = payload.get("parser_unparsed_rows")
    if unparsed:
        reasons.append(f"{unparsed} unparsed row(s) on the official entry page")
    if payload.get("identity_matched") == "not attempted (no player_master DB in this run)":
        reasons.append("canonical player_master identity matching was explicitly not attempted for this snapshot")
    missing_evidence = [str(e.get("player_id")) for e in entries if e.get("identity_match") is None]
    if missing_evidence:
        if len(missing_evidence) == len(entries):
            reasons.append(
                "no entry carries real player_master identity-match evidence -- "
                "identity matching was not actually performed for this snapshot"
            )
        else:
            reasons.append(f"{len(missing_evidence)} entry row(s) have no identity-match evidence: {missing_evidence}")
    unresolved = payload.get("unresolved_player_ids") or []
    if unresolved:
        reasons.append(f"{len(unresolved)} unresolved identity match(es): {unresolved}")
    ids = [str(e.get("player_id")) for e in entries]
    if len(ids) != len(set(ids)):
        reasons.append("entries themselves contain duplicate player_id values")
    if reasons:
        return StateCheck.fail(name, *reasons)
    return StateCheck.ok(name)


# Every PRE-upstream artifact_type that must exist, with self-consistency
# expressed as "how many player rows does it carry" -- each must agree
# with the entry snapshot's own player_count. None means "no per-player
# row count to check" (the artifact's mere presence + game_code match is
# enough).
_PRE_INPUT_ROW_COUNTERS: dict[str, callable] = {
    "pre_performance_snapshot": lambda d: len(d.get("profiles") or []),
    "current_player_master": lambda d: len(d.get("records") or []),
    "official_klpga_ranking": lambda d: len(d.get("records") or []),
    "neo_pre_ranking_evidence": lambda d: len(d.get("records") or []),
    "pre_win_forecast": lambda d: len(d.get("records") or []),
    "data_center_profile_audit": lambda d: len(d.get("records") or []),
    "pre_performance_row_retention_corrected_v2": lambda d: len(d.get("profiles") or []),
    "pre_sg_total_rank_corrected_v2": lambda d: len(d.get("records") or []),
}


def validate_pre_inputs(context: TournamentContext) -> StateCheck:
    """PRE_INPUTS_VALIDATED: every PRE-upstream artifact (67/69/72/73/75/
    79/82's outputs) exists, belongs to THIS game_code, and carries the
    same entrant count as the frozen entry snapshot -- never merely "the
    file exists". A partial PRE run (crashed midway through
    _PRE_UPSTREAM_CHAIN) fails this check on whichever artifact never
    got produced, so Stage.PRE_READY can never be reached from an
    incomplete chain."""
    name = "PRE_INPUTS_VALIDATED"
    entry = _read_json(context.artifact_path("entry_snapshot"))
    if entry is None:
        return StateCheck.fail(name, "entry_snapshot missing -- cannot cross-check PRE input field sizes")
    expected = len(entry.get("entries") or [])
    reasons: list[str] = []
    for artifact_type, counter in _PRE_INPUT_ROW_COUNTERS.items():
        path = context.artifact_path(artifact_type)
        payload = _read_json(path)
        if payload is None:
            reasons.append(f"{artifact_type} missing or unreadable at {path}")
            continue
        game_code = payload.get("game_code")
        if game_code is not None and str(game_code) != context.game_code:
            reasons.append(f"{artifact_type} game_code={game_code!r} does not match {context.game_code!r}")
        count = counter(payload)
        if count != expected:
            reasons.append(f"{artifact_type} has {count} rows, expected {expected} (entry_snapshot player_count)")
    if reasons:
        return StateCheck.fail(name, *reasons)
    return StateCheck.ok(name)


def validate_pre_model(context: TournamentContext) -> StateCheck:
    """PRE_MODEL_VALIDATED: the Tier-2 field-domain publication gate
    (klpga.neo_win.tier2_publication_gate) must have actually reached
    overall_state == PASS, AND the canonical pre_public_master (script
    83's version -- the one built AFTER Tier-2 passed, distinguished
    from script 73's earlier draft by carrying a "tier2_gate"
    provenance field) must exist. A draft pre_public_master that only
    73 ever wrote is explicitly rejected here, not silently accepted."""
    name = "PRE_MODEL_VALIDATED"
    gate = _read_json(context.artifact_path("tier2_publication_gate"))
    if gate is None:
        return StateCheck.fail(name, "tier2_publication_gate missing or unreadable")
    reasons: list[str] = []
    if gate.get("overall_state") != "PASS":
        reasons.append(f"tier2_publication_gate overall_state={gate.get('overall_state')!r}, not PASS")
    master = _read_json(context.artifact_path("pre_public_master"))
    if master is None:
        reasons.append("pre_public_master missing or unreadable")
    elif "tier2_gate" not in master:
        reasons.append(
            "pre_public_master has no tier2_gate provenance field -- this is script 73's draft "
            "version, not the canonical Tier-2-gated version script 83 produces"
        )
    if reasons:
        return StateCheck.fail(name, *reasons)
    return StateCheck.ok(name)


def validate_pre_publication(context: TournamentContext) -> StateCheck:
    """PRE_PUBLICATION_APPROVED: the PRE website candidate has actually
    been built (script 84's candidate output). Reported as its own
    named StateCheck alongside the other four -- a stale/missing
    candidate must never be read as "model validated" -- but (PRE
    contract hardening, fix/phase5-pre-contract-gates) it is now ALSO
    required for PreStateContract.pre_ready: model/data readiness alone
    is no longer sufficient to reach PRE_READY while this is False."""
    name = "PRE_PUBLICATION_APPROVED"
    # Generic signal: any candidate directory whose manifest cites this
    # tournament's canonical pre_public_master as its source. We do not
    # hardcode script 84's OK-Open-specific candidate directory name
    # here -- any candidate/*/data/manifest.json naming this game_code's
    # master file counts.
    candidate_root = context.artifact_path("pre_public_master").parents[2] / "candidate"
    master_name = context.artifact_path("pre_public_master").name
    if not candidate_root.is_dir():
        return StateCheck.fail(name, f"no candidate/ directory at {candidate_root}")
    for manifest_path in candidate_root.glob("*/data/manifest.json"):
        manifest = _read_json(manifest_path)
        if manifest and master_name in str(manifest.get("source_master", "")):
            return StateCheck.ok(name)
    return StateCheck.fail(name, f"no built PRE candidate references {master_name}")


_PRE_FEATURES_PREDICTION_ID = "PRE"


def _pre_feature_snapshot(context: TournamentContext) -> NeoWinPredictionSnapshot:
    """Build the NeoWinPredictionSnapshot freeze_pre_model_features()
    expects from the real, already-produced PRE artifacts -- never
    invents a value: a player with no computable metric gets None for
    that field, exactly as the source artifacts already record it."""
    entry = _read_json(context.artifact_path("entry_snapshot"))
    performance = _read_json(context.artifact_path("pre_performance_snapshot"))
    forecast = _read_json(context.artifact_path("pre_win_forecast"))
    master = _read_json(context.artifact_path("current_player_master"))
    if entry is None or performance is None or forecast is None or master is None:
        raise ValueError("cannot build PRE feature snapshot: one or more source PRE artifacts is missing")

    profiles_by_id = {str(p["player_id"]): p for p in (performance.get("profiles") or [])}
    prob_by_id = {str(r["player_id"]): r.get("win_probability") for r in (forecast.get("records") or [])}
    matched_by_id = {
        str(r.get("player_id")): (r.get("identity_validation") == "PASS")
        for r in (master.get("records") or [])
    }

    entrants = []
    for e in entry.get("entries") or []:
        pid = str(e["player_id"])
        profile = profiles_by_id.get(pid) or {}
        windows = profile.get("windows") or {}
        multi = (windows.get("multi_season") or {}).get("components", {}).get("total", {}) or {}
        recent10 = (windows.get("recent10") or {}).get("components", {}).get("total", {}) or {}
        consistency = profile.get("consistency") or {}
        entrants.append(NeoWinEntrantSnapshot(
            rank=0,  # assigned below once probabilities are known
            player_code=pid,
            player_name=str(profile.get("player_name") or e.get("player_name") or pid),
            win_probability=prob_by_id.get(pid) if prob_by_id.get(pid) is not None else 0.0,
            prior_events_n=int((windows.get("multi_season") or {}).get("event_count") or 0),
            prior_avg_round_score_to_par=multi.get("mean"),
            prior_recent_form_10=recent10.get("mean"),
            prior_recent_form_10_n=int((windows.get("recent10") or {}).get("event_count") or 0),
            neo_consistency_stddev=consistency.get("legacy_sample_sd") or consistency.get("population_sd_research"),
            neo_consistency_stddev_n=int((windows.get("multi_season") or {}).get("event_count") or 0),
            official_metrics={},
            player_master_matched=bool(matched_by_id.get(pid, False)),
        ))
    # Rank by real win_probability descending (ties broken by player_code
    # for a deterministic, reproducible ordering) -- never by array order.
    entrants.sort(key=lambda x: (-(prob_by_id.get(x.player_code) or 0.0), x.player_code))
    entrants = tuple(replace(e, rank=i + 1) for i, e in enumerate(entrants))

    entrants_predicted = sum(1 for pid in prob_by_id if prob_by_id.get(pid) is not None)
    probabilities = [v for v in prob_by_id.values() if v is not None]
    warehouse = _read_json(CONTENT_DIR / "historical_sg_warehouse.json") or {}
    training_tournament_count = len({str(r.get("game_code")) for r in (warehouse.get("records") or []) if r.get("game_code")})

    return NeoWinPredictionSnapshot(
        prediction_id=_PRE_FEATURES_PREDICTION_ID,
        created_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        record_kind=RECORD_KIND,
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        cutoff_date=context.start_date,
        cutoff_source="PRE freeze at tournament start (klpga.tournament_pre_state)",
        model_id=str(forecast.get("model_version") or "unknown"),
        model_version=str(forecast.get("model_version") or "unknown"),
        model_features=("prior_avg_round_score_to_par", "prior_recent_form_10"),
        training_tournament_count=training_tournament_count,
        field_size=len(entry.get("entries") or []),
        entrants_predicted=entrants_predicted,
        dropped_entrants=len(entrants) - entrants_predicted,
        probability_sum=sum(probabilities),
        minimum_probability=min(probabilities) if probabilities else 0.0,
        maximum_probability=max(probabilities) if probabilities else 0.0,
        zero_history_count=sum(1 for e in entrants if e.prior_events_n == 0),
        unmatched_count=sum(1 for e in entrants if not e.player_master_matched),
        official_metric_context={},
        leakage_validation={"future_data_excluded": bool(performance.get("future_data_excluded"))},
        missing_data_report={"dropped_entrants": len(entrants) - entrants_predicted},
        known_limitations=(),
        predictions=entrants,
    )


def freeze_active_pre_features(context: TournamentContext, *, predictions_root: Path | None = None) -> FrozenFeatureRef:
    """Wire freeze_pre_model_features() into the real PRE lifecycle
    (Phase 5 item 3/5): build the feature snapshot from the real,
    already-produced PRE artifacts and freeze it immutably. Idempotent
    -- if this tournament's PRE features are already frozen,
    NeoWinAlreadyArchivedError is caught and the existing frozen ref's
    identity is returned rather than treated as a failure (frozen
    inputs are immutable after freeze; re-freezing the same tournament
    is a no-op, never an overwrite)."""
    root = predictions_root or (CONTENT_DIR.parent.parent / "neo_win_predictions")
    snapshot = _pre_feature_snapshot(context)
    try:
        return freeze_pre_model_features(snapshot, predictions_root=root)
    except NeoWinAlreadyArchivedError:
        json_path, _ = archive_paths(root, snapshot.prediction_id, snapshot.game_code, snapshot.cutoff_date)
        return FrozenFeatureRef(
            snapshot_id=f"PRE:{snapshot.game_code}:{snapshot.prediction_id}",
            sha256=hashlib.sha256(json_path.read_bytes()).hexdigest(),
            path=str(json_path), game_code=snapshot.game_code, stage="PRE",
            model_id=snapshot.model_id, model_version=snapshot.model_version,
        )


def validate_pre_features_frozen(context: TournamentContext, *, predictions_root: Path | None = None) -> StateCheck:
    """PRE_FEATURES_FROZEN: an immutable frozen feature archive already
    exists for this tournament's PRE cutoff -- never inferred from the
    mutable PRE artifacts alone, and (PRE contract hardening,
    fix/phase5-pre-contract-gates) never accepted merely because a file
    happens to sit at the expected path. The archive itself must:
    parse as real JSON; carry a game_code that actually matches this
    context; carry a cutoff_date that actually matches this
    tournament's own start_date (never a stale freeze for a different
    tournament reusing the same path, and never a freeze taken at the
    wrong moment); carry real model_id/model_version provenance
    (missing or the "unknown" placeholder both fail -- that placeholder
    is klpga.tournament_pre_state._pre_feature_snapshot's own admission
    that no real model identity was available, not a real value); and
    explicitly assert leakage_validation.future_data_excluded is True."""
    name = "PRE_FEATURES_FROZEN"
    root = predictions_root or (CONTENT_DIR.parent.parent / "neo_win_predictions")
    entry = _read_json(context.artifact_path("entry_snapshot"))
    if entry is None:
        return StateCheck.fail(name, "entry_snapshot missing -- cannot resolve cutoff_date for the freeze lookup")
    json_path, _ = archive_paths(root, _PRE_FEATURES_PREDICTION_ID, context.game_code, context.start_date)
    if not json_path.is_file():
        return StateCheck.fail(name, f"no frozen PRE feature archive at {json_path}")
    frozen = _read_json(json_path)
    if frozen is None:
        return StateCheck.fail(name, f"frozen PRE feature archive at {json_path} is not valid JSON")
    reasons: list[str] = []
    frozen_game_code = frozen.get("game_code")
    if str(frozen_game_code) != context.game_code:
        reasons.append(f"frozen archive game_code={frozen_game_code!r} does not match {context.game_code!r}")
    frozen_cutoff = frozen.get("cutoff_date")
    if frozen_cutoff != context.start_date:
        reasons.append(
            f"frozen archive cutoff_date={frozen_cutoff!r} does not match tournament start_date={context.start_date!r}"
        )
    model_id = frozen.get("model_id")
    if not model_id or model_id == "unknown":
        reasons.append(f"frozen archive has no real model_id provenance (model_id={model_id!r})")
    model_version = frozen.get("model_version")
    if not model_version or model_version == "unknown":
        reasons.append(f"frozen archive has no real model_version provenance (model_version={model_version!r})")
    leakage = frozen.get("leakage_validation") or {}
    if leakage.get("future_data_excluded") is not True:
        reasons.append(
            f"frozen archive leakage_validation.future_data_excluded={leakage.get('future_data_excluded')!r}, expected True"
        )
    if reasons:
        return StateCheck.fail(name, *reasons)
    return StateCheck.ok(name)


@dataclass(frozen=True)
class PreStateContract:
    entry_validated: StateCheck
    pre_inputs_validated: StateCheck
    pre_features_frozen: StateCheck
    pre_model_validated: StateCheck
    pre_publication_approved: StateCheck

    @property
    def pre_ready(self) -> bool:
        """Feeds TournamentFacts.pre_validated / Stage.PRE_READY.

        PRE contract hardening (fix/phase5-pre-contract-gates):
        PRE_PUBLICATION_APPROVED is now REQUIRED too. Data/model
        readiness alone must never advance a tournament into
        PRE_READY while the public website candidate has not actually
        been built/approved -- a still-pending publication step is a
        real incompleteness, not a detail to track "separately" while
        letting the lifecycle move on regardless."""
        return (
            self.entry_validated.valid
            and self.pre_inputs_validated.valid
            and self.pre_features_frozen.valid
            and self.pre_model_validated.valid
            and self.pre_publication_approved.valid
        )

    def to_dict(self) -> dict:
        def _c(check: StateCheck) -> dict:
            return {"valid": check.valid, "reasons": list(check.reasons)}
        return {
            "entry_validated": _c(self.entry_validated),
            "pre_inputs_validated": _c(self.pre_inputs_validated),
            "pre_features_frozen": _c(self.pre_features_frozen),
            "pre_model_validated": _c(self.pre_model_validated),
            "pre_publication_approved": _c(self.pre_publication_approved),
            "pre_ready": self.pre_ready,
        }


def build_pre_state_contract(context: TournamentContext, *, freeze_if_ready: bool = False) -> PreStateContract:
    """Assemble the full explicit PRE state contract for a tournament.

    freeze_if_ready=True (used by run_tournament.py's PREPARE_PRE
    runner, after the PRE-upstream chain has run): if entry/inputs/model
    are all already valid but features haven't been frozen yet, freeze
    them now via freeze_active_pre_features() before re-checking --
    this is what actually connects freeze_pre_model_features() to the
    real PRE lifecycle instead of leaving it permanently unreachable.
    Freezing is attempted at most once per call and never on a
    still-incomplete PRE (entry/inputs/model must already be valid)."""
    entry_check = validate_entry(context)
    inputs_check = validate_pre_inputs(context)
    model_check = validate_pre_model(context)
    features_check = validate_pre_features_frozen(context)
    if freeze_if_ready and not features_check.valid and entry_check.valid and inputs_check.valid and model_check.valid:
        try:
            freeze_active_pre_features(context)
        except (ValueError, OSError):
            pass  # leave features_check as its already-computed failing state
        else:
            features_check = validate_pre_features_frozen(context)
    publication_check = validate_pre_publication(context)
    return PreStateContract(
        entry_validated=entry_check,
        pre_inputs_validated=inputs_check,
        pre_features_frozen=features_check,
        pre_model_validated=model_check,
        pre_publication_approved=publication_check,
    )
