"""R2 HOUSE: the official R2 input contract.

Explicit REQUIRED / OPTIONAL / DERIVED / UNAVAILABLE vocabulary for
every field the R2 house's completeness/status/freeze machinery
consumes -- so a caller never has to guess whether a field the real
official source happens not to provide is a real gap (HARD_STOP-
worthy) or an expected absence (fine to publish around).

REQUIRED: without this, R2 cannot be assessed as complete at all.
OPTIONAL: nice to have when the official source provides it; its
    absence never blocks completeness by itself.
DERIVED: never collected directly -- computed from REQUIRED/OPTIONAL
    fields by this pipeline (e.g. completed_holes from inghole +
    starting_tee, see klpga.parsers.round_progress).
UNAVAILABLE: known to not exist in the real official source for this
    tournament/round shape -- documented here so nothing downstream
    ever silently invents it or blocks waiting for it forever.

INDEPENDENT EXPECTED POPULATION (P0-COMPLETENESS): the field a real R2
collection is checked against must NEVER be "however many rows R2
happened to return" -- that collapses to `expected_count ==
observed_count`, the exact anti-pattern this module exists to forbid.
The one real, already-validated, pre-R2 source of the field is KB's
own real R1 evidence artifact (NEO_KB_<game_code>_R1_OFFICIAL_RESULT_
EVIDENCE_V1.json's `players` list -- the players[] who actually played
R1, NOT R1_5PROB_FROZEN_V1.json's `predictions[]`, which excludes
insufficient-PRE-history players from the MODEL while they remain
real, expected R2 entrants). Every one of those real R1 participants
is expected to appear in R2 either with a real result row or with an
explicit official WD/DQ/DNS status -- never silently absent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED = "REQUIRED"
OPTIONAL = "OPTIONAL"
DERIVED = "DERIVED"
UNAVAILABLE = "UNAVAILABLE"

R2_FIELD_CONTRACT: dict[str, str] = {
    # identity -- without these a row cannot be matched to a real entrant
    "player_id": REQUIRED,
    "player_name": REQUIRED,
    # result -- REQUIRED only in the sense that its ABSENCE must be
    # explained by an official status; a player legitimately has no
    # score yet mid-round (see round/tee handling below)
    "round_to_par": OPTIONAL,
    "total_to_par": OPTIONAL,
    # official participation status for this round -- the ONLY field
    # allowed to explain why a player has no result row
    "status": REQUIRED,  # one of ACTIVE / CUT / WD / DQ / DNS
    # round/tee progress -- see klpga.parsers.round_progress; inghole
    # alone is NOT completed-hole count (the known regression)
    "inghole": OPTIONAL,
    "starting_tee": OPTIONAL,
    "completed_holes": DERIVED,  # via round_progress.resolve_completed_holes(inghole, starting_tee)
    # official source identity/provenance -- REQUIRED for the freeze
    "official_source_url": REQUIRED,
    "collected_at": REQUIRED,
    # KLPGA's live leaderboard endpoint carries no per-row official
    # timestamp of when THAT score was posted -- confirmed absent from
    # every already-collected OK Open/KG Ladies Open/KB snapshot this
    # session; never fabricated as equal to collected_at.
    "official_data_timestamp": UNAVAILABLE,
    # live per-round strokes-gained (OTT/APP/ARG/PUTT/TOTAL) -- no live,
    # per-round SG collector exists anywhere in this codebase (confirmed:
    # SG data here is exclusively a prior-season, cross-tournament
    # warehouse, never a per-round live source); a real per-round SG
    # value from KLPGA's own official R2 source is UNAVAILABLE until
    # such a collector is built -- never computed from incomplete/live
    # data as a substitute (see r2_sg_gate.py).
    "sg_ott": UNAVAILABLE,
    "sg_app": UNAVAILABLE,
    "sg_arg": UNAVAILABLE,
    "sg_putt": UNAVAILABLE,
    "sg_total": UNAVAILABLE,
}


def field_classification(field_name: str) -> str:
    """REQUIRED/OPTIONAL/DERIVED/UNAVAILABLE for a named field -- raises
    KeyError for any field not explicitly classified here (never a
    silent default), so a new field must be classified before any
    gate/freeze code depends on it."""
    return R2_FIELD_CONTRACT[field_name]


@dataclass(frozen=True)
class ExpectedR2Field:
    game_code: str
    player_ids: frozenset[str]
    source_artifact: str
    source_sha256: str


def expected_r2_field_from_r1_evidence(r1_evidence: dict, *, source_artifact: str, source_sha256: str) -> ExpectedR2Field:
    """The ONE sanctioned way to derive R2's independent expected
    population: KB's own real R1 official-result-evidence artifact's
    `players` list (who actually played R1), NEVER
    R1_5PROB_FROZEN_V1.json's `predictions` (a MODEL-eligibility
    subset that excludes real, present entrants with insufficient PRE
    history) and NEVER a count of R2's own observed rows."""
    game_code = str(r1_evidence["gameCode"])
    player_ids = frozenset(str(p["playerCode"]) for p in r1_evidence["players"])
    if not player_ids:
        raise ValueError("R1 evidence has no players -- refusing to derive an empty expected R2 field")
    return ExpectedR2Field(
        game_code=game_code, player_ids=player_ids, source_artifact=source_artifact, source_sha256=source_sha256,
    )


def load_expected_r2_field(r1_evidence_path: Path) -> ExpectedR2Field:
    """Convenience loader: reads the real R1 evidence file off disk and
    hashes it, so the returned ExpectedR2Field carries real
    provenance (never a bare in-memory set with no traceable source)."""
    import hashlib

    raw = r1_evidence_path.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    evidence = json.loads(raw.decode("utf-8"))
    return expected_r2_field_from_r1_evidence(evidence, source_artifact=r1_evidence_path.name, source_sha256=sha256)
