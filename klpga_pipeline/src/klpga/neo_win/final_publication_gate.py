"""R3 FINAL WEB DRY-RUN task, section 9 -- FINAL is never promoted onto
HOME merely because a FINAL candidate JSON or a rendered FINAL HTML file
exists. Those are both produced by scripts/117 the moment R3's official
result passes validation (see klpga.neo_win.r3_result_input), long
before any human has reviewed or approved a production deploy -- exactly
the kind of "file exists" signal klpga.website_v2.kb_home_stage_router
already refuses for R3's own WAIT page (see that module's own
`test_r3_wait_page_existing_does_not_promote_home_to_r3` precedent).

This module defines the ONE piece of evidence that is allowed to mean
"FINAL is really published": a separate, explicit
`final_published_evidence` artifact that binds itself, by real sha256,
to one specific candidate JSON. Nothing in this task's own pipeline
(scripts/117, this branch) ever writes this artifact -- it is
deliberately left for a SEPARATE, future, human-invoked production-
promotion step (out of scope here, per this task's own "DO NOT DEPLOY"
requirement). As a direct consequence, KB's real current stage can
never advance to "final" from anything this task adds; it only stops
being permanently unreachable once that future promotion tooling
actually exists and a human actually runs it."""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from klpga.tournament_context import TournamentContext

FINAL_PUBLISHED_ARTIFACT_TYPE = "final_published_evidence"
FINAL_CANDIDATE_ARTIFACT_TYPE = "final_validation_candidate"


def final_published_evidence_exists(context: TournamentContext) -> bool:
    return context.artifact_path(FINAL_PUBLISHED_ARTIFACT_TYPE).is_file()


def verify_final_published_hash(context: TournamentContext) -> bool:
    """True only if a `final_published_evidence` artifact exists, is
    marked `published: true`, and its own recorded `candidate_sha256`
    still matches a fresh hash of the CURRENT `final_validation_candidate`
    artifact's bytes -- a stale/edited/orphaned evidence file (or one
    left behind after the candidate was regenerated) never counts."""
    evidence_path = context.artifact_path(FINAL_PUBLISHED_ARTIFACT_TYPE)
    if not evidence_path.is_file():
        return False
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    if evidence.get("published") is not True:
        return False
    candidate_path = context.artifact_path(FINAL_CANDIDATE_ARTIFACT_TYPE)
    if not candidate_path.is_file():
        return False
    candidate_sha256 = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    return evidence.get("candidate_sha256") == candidate_sha256


def build_final_published_evidence(context: TournamentContext, *, approved_by: str) -> dict:
    """Pure construction of the ONE evidence shape
    verify_final_published_hash() accepts. NOT called anywhere in this
    branch's real pipeline -- provided only so a future, separate,
    human-invoked promotion script (and this task's own tests, which
    must prove the gate CAN pass on real evidence, not just refuse
    everything) has one real, shared definition to use rather than each
    inventing its own JSON shape."""
    candidate_path = context.artifact_path(FINAL_CANDIDATE_ARTIFACT_TYPE)
    if not candidate_path.is_file():
        raise FileNotFoundError(f"no final_validation_candidate exists at {candidate_path} -- nothing to publish")
    return {
        "schema_version": 1,
        "artifact": FINAL_PUBLISHED_ARTIFACT_TYPE,
        "game_code": context.game_code,
        "published": True,
        "approved_by": approved_by,
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    }
