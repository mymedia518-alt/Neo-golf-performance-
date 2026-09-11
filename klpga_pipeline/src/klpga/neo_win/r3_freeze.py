"""R3 HOUSE: the immutable R3 freeze artifact.

Write-once, content-addressed evidence for a tournament's real,
official R3 result -- the one artifact every downstream stage (post-R3
forecast, probability gate, R3 website, publication gate) must verify
against rather than re-deriving its own notion of "is R3 real/complete/
frozen". Mirrors klpga.neo_win.r2_freeze byte-for-byte in structure and
invariants (immutability, provenance, content-addressing) -- generalized
to R3 rather than reinvented.

NO NEW CUT EVENT AT R3: unlike R2 (which determines who advances),
R3 has no elimination -- the R3-eligible population IS the R2 freeze's
own ACTIVE (advancing) set. `records` therefore carries only that
population (never the R2 freeze's CUT rows, which have zero R3
relevance -- they did not play). Status within the R3 population is
{"ACTIVE", "WD", "DQ", "DNS"} only -- never "CUT" (see
klpga.neo_win.round_update_r3's own module docstring for why: the cut
is a settled, historical fact by R3, not a new R3-stage event). A
player who withdraws/is disqualified/does-not-start DURING R3 itself is
still recorded here (never silently dropped) -- the public R3 page is
responsible for excluding them from its own MAIN table (see
r3_real_page.py), never this freeze.

Reached via TournamentContext.artifact_path("r3_frozen_evidence"),
which resolves to <game_code>_R3_FROZEN_EVIDENCE.json with zero
registry changes for any tournament.

Immutability: `write_r3_freeze_immutable` raises FileExistsError if a
freeze for this game_code already exists -- a mutable "latest" artifact
must never silently replace the frozen source a downstream forecast
already consumed. There is no "overwrite" parameter; a genuine
correction requires a new, explicitly versioned artifact_type, never an
in-place rewrite of this one.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from klpga.tournament_context import TournamentContext

R3_FREEZE_SCHEMA_VERSION = "neo_r3_frozen_evidence_v1"
FEATURE_CUTOFF = "END_OF_R3"
R3_ALLOWED_STATUSES = frozenset({"ACTIVE", "WD", "DQ", "DNS"})


@dataclass(frozen=True)
class R3FrozenEvidence:
    schema_version: str
    game_code: str
    round: int  # always 3
    official_source_identity: str
    official_source_url: Optional[str]
    collection_timestamp: str
    raw_official_response_sha256: str
    parsed_canonical_sha256: str
    expected_field_count: int
    observed_player_count: int
    status_counts: dict  # {"ACTIVE": n, "WD": n, "DQ": n, "DNS": n}
    wd_dq_dns_evidence: list  # [{"player_id", "status", "evidence"}]
    feature_cutoff: str  # always FEATURE_CUTOFF
    r2_freeze_artifact: str
    r2_freeze_sha256: str
    code_commit: str
    build_id: str
    records: list = field(default_factory=list)  # the real per-player R3 rows this freeze is built from

    def __post_init__(self):
        if self.round != 3:
            raise ValueError(f"R3FrozenEvidence.round must be 3, got {self.round!r}")
        if self.feature_cutoff != FEATURE_CUTOFF:
            raise ValueError(f"feature_cutoff must be {FEATURE_CUTOFF!r}, got {self.feature_cutoff!r}")
        bad = sorted({str(r.get("status", "ACTIVE")) for r in self.records} - R3_ALLOWED_STATUSES)
        if bad:
            raise ValueError(f"R3FrozenEvidence.records contains status(es) never valid at R3: {bad} (CUT is settled by R2, never an R3 status)")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def build_r3_frozen_evidence(
    *,
    context: TournamentContext,
    official_source_identity: str,
    official_source_url: Optional[str],
    collection_timestamp: str,
    raw_official_response: bytes,
    records: list,
    expected_field_count: int,
    status_counts: dict,
    wd_dq_dns_evidence: list,
    r2_freeze_path: Path,
    repo_root: Path,
    build_id: str,
) -> R3FrozenEvidence:
    """Pure construction (no file I/O beyond reading the binding
    artifact + hashing) -- the caller decides when/whether to write it
    via write_r3_freeze_immutable. Binds the R2 freeze by its real
    sha256 at construction time, not a filename alone, so a later
    accidental edit of R2's own frozen evidence is detectable (R2's own
    freeze already transitively binds PRE+R1, so binding R3 to R2 alone
    is sufficient chain-of-custody)."""
    if not r2_freeze_path.is_file():
        raise FileNotFoundError(f"R2 freeze artifact not found: {r2_freeze_path}")

    canonical = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return R3FrozenEvidence(
        schema_version=R3_FREEZE_SCHEMA_VERSION,
        game_code=context.game_code,
        round=3,
        official_source_identity=official_source_identity,
        official_source_url=official_source_url,
        collection_timestamp=collection_timestamp,
        raw_official_response_sha256=_sha256_bytes(raw_official_response),
        parsed_canonical_sha256=_sha256_bytes(canonical),
        expected_field_count=expected_field_count,
        observed_player_count=len(records),
        status_counts=dict(status_counts),
        wd_dq_dns_evidence=list(wd_dq_dns_evidence),
        feature_cutoff=FEATURE_CUTOFF,
        r2_freeze_artifact=r2_freeze_path.name,
        r2_freeze_sha256=_sha256_bytes(r2_freeze_path.read_bytes()),
        code_commit=_source_git_sha(repo_root),
        build_id=build_id,
        records=list(records),
    )


def r3_freeze_path(context: TournamentContext) -> Path:
    return context.artifact_path("r3_frozen_evidence")


def r3_freeze_exists(context: TournamentContext) -> bool:
    return r3_freeze_path(context).is_file()


def write_r3_freeze_immutable(context: TournamentContext, evidence: R3FrozenEvidence) -> Path:
    """Raises FileExistsError if this game_code's R3 freeze already
    exists -- write-once, never silently replaced."""
    path = r3_freeze_path(context)
    if path.is_file():
        raise FileExistsError(f"R3 freeze already exists and is immutable: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(evidence), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def load_r3_freeze(context: TournamentContext) -> Optional[dict]:
    path = r3_freeze_path(context)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify_r3_freeze_hash(context: TournamentContext) -> bool:
    """True only if the on-disk freeze's own recorded
    parsed_canonical_sha256 still matches a fresh hash of its own
    `records` -- detects any post-write tampering/corruption."""
    freeze = load_r3_freeze(context)
    if freeze is None:
        return False
    canonical = json.dumps(freeze["records"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(canonical) == freeze["parsed_canonical_sha256"]
