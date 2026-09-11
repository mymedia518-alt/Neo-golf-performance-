"""R2 HOUSE: the immutable R2 freeze artifact.

Write-once, content-addressed evidence for a tournament's real,
official R2 result -- the one artifact every downstream stage (SG gate,
post-R2 forecast, probability gate, R2 website, HOME transition,
publication gate) must verify against rather than re-deriving its own
notion of "is R2 real/complete/frozen".

Mirrors the R1 freeze shape already used in production for KB
(2026090003_R1_5PROB_FROZEN_V1.json / NEO_KB_..._R1_OFFICIAL_RESULT_
EVIDENCE_V1.json) but as ONE generic, tournament-neutral schema rather
than a second bespoke, hand-rolled JSON shape per tournament -- reached
via TournamentContext.artifact_path("r2_frozen_evidence"), which
resolves to <game_code>_R2_FROZEN_EVIDENCE.json with zero registry
changes for any tournament, KB included.

Immutability: `write_r2_freeze_immutable` raises FileExistsError if a
freeze for this game_code already exists -- a mutable "latest" artifact
must never silently replace the frozen source a downstream forecast
already consumed (the user's own explicit requirement). There is no
"overwrite" parameter; a genuine correction requires a new, explicitly
versioned artifact_type, never an in-place rewrite of this one.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from klpga.tournament_context import TournamentContext

R2_FREEZE_SCHEMA_VERSION = "neo_r2_frozen_evidence_v1"
FEATURE_CUTOFF = "END_OF_R2"


@dataclass(frozen=True)
class R2FrozenEvidence:
    schema_version: str
    game_code: str
    round: int  # always 2
    official_source_identity: str
    official_source_url: Optional[str]
    collection_timestamp: str
    raw_official_response_sha256: str
    parsed_canonical_sha256: str
    expected_field_count: int
    observed_player_count: int
    status_counts: dict  # {"ACTIVE": n, "CUT": n, "WD": n, "DQ": n, "DNS": n}
    cut_wd_dq_evidence: list  # [{"player_id", "status", "evidence"}]
    feature_cutoff: str  # always FEATURE_CUTOFF
    pre_freeze_artifact: str
    pre_freeze_sha256: str
    r1_freeze_artifact: str
    r1_freeze_sha256: str
    code_commit: str
    build_id: str
    records: list = field(default_factory=list)  # the real per-player R2 rows this freeze is built from

    def __post_init__(self):
        if self.round != 2:
            raise ValueError(f"R2FrozenEvidence.round must be 2, got {self.round!r}")
        if self.feature_cutoff != FEATURE_CUTOFF:
            raise ValueError(f"feature_cutoff must be {FEATURE_CUTOFF!r}, got {self.feature_cutoff!r}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def build_r2_frozen_evidence(
    *,
    context: TournamentContext,
    official_source_identity: str,
    official_source_url: Optional[str],
    collection_timestamp: str,
    raw_official_response: bytes,
    records: list,
    expected_field_count: int,
    status_counts: dict,
    cut_wd_dq_evidence: list,
    pre_freeze_path: Path,
    r1_freeze_path: Path,
    repo_root: Path,
    build_id: str,
) -> R2FrozenEvidence:
    """Pure construction (no file I/O beyond reading the two binding
    artifacts + hashing) -- the caller decides when/whether to write it
    via write_r2_freeze_immutable. Binds PRE and R1 freeze by their real
    sha256 at construction time, not a filename alone, so a later
    accidental edit of either upstream artifact is detectable."""
    if not pre_freeze_path.is_file():
        raise FileNotFoundError(f"PRE freeze artifact not found: {pre_freeze_path}")
    if not r1_freeze_path.is_file():
        raise FileNotFoundError(f"R1 freeze artifact not found: {r1_freeze_path}")

    canonical = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return R2FrozenEvidence(
        schema_version=R2_FREEZE_SCHEMA_VERSION,
        game_code=context.game_code,
        round=2,
        official_source_identity=official_source_identity,
        official_source_url=official_source_url,
        collection_timestamp=collection_timestamp,
        raw_official_response_sha256=_sha256_bytes(raw_official_response),
        parsed_canonical_sha256=_sha256_bytes(canonical),
        expected_field_count=expected_field_count,
        observed_player_count=len(records),
        status_counts=dict(status_counts),
        cut_wd_dq_evidence=list(cut_wd_dq_evidence),
        feature_cutoff=FEATURE_CUTOFF,
        pre_freeze_artifact=pre_freeze_path.name,
        pre_freeze_sha256=_sha256_bytes(pre_freeze_path.read_bytes()),
        r1_freeze_artifact=r1_freeze_path.name,
        r1_freeze_sha256=_sha256_bytes(r1_freeze_path.read_bytes()),
        code_commit=_source_git_sha(repo_root),
        build_id=build_id,
        records=list(records),
    )


def r2_freeze_path(context: TournamentContext) -> Path:
    return context.artifact_path("r2_frozen_evidence")


def r2_freeze_exists(context: TournamentContext) -> bool:
    return r2_freeze_path(context).is_file()


def write_r2_freeze_immutable(context: TournamentContext, evidence: R2FrozenEvidence) -> Path:
    """Raises FileExistsError if this game_code's R2 freeze already
    exists -- write-once, never silently replaced."""
    path = r2_freeze_path(context)
    if path.is_file():
        raise FileExistsError(f"R2 freeze already exists and is immutable: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(evidence), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def load_r2_freeze(context: TournamentContext) -> Optional[dict]:
    path = r2_freeze_path(context)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify_r2_freeze_hash(context: TournamentContext) -> bool:
    """True only if the on-disk freeze's own recorded
    parsed_canonical_sha256 still matches a fresh hash of its own
    `records` -- detects any post-write tampering/corruption."""
    freeze = load_r2_freeze(context)
    if freeze is None:
        return False
    canonical = json.dumps(freeze["records"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(canonical) == freeze["parsed_canonical_sha256"]
