"""4R FINAL PRE-BUILD Phase 3: the FINAL Truth schema.

Write-once, content-addressed official result -- mirrors
klpga.neo_win.r3_freeze byte-for-byte in structure and invariants
(immutability, provenance, content-addressing), generalized to the
tournament's FINAL result rather than reinvented. This module defines
the schema and write/verify machinery ONLY; it does not, and must not,
ever be called with fabricated data. Building this now (before the
official FR/R4 result exists) is exactly the mission's point: nothing
about this module's shape may change once real results start arriving.

Status vocabulary matches the project's existing, permanent rule
(klpga.tournament_runtime.NON_CUT_STATUSES): {"ACTIVE", "WD", "DQ",
"DNS"}. No new status vocabulary is invented here.

Tied ranks: `final_rank` is the official displayed rank exactly as the
source publishes it (e.g. two players both showing "2" for a tie) --
this module does not deduplicate or renumber ties; every metric that
consumes final_rank (final_validator.py) must treat equal values as a
legitimate tie, never an error.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from klpga.tournament_context import TournamentContext
from klpga.tournament_runtime import NON_CUT_STATUSES

FINAL_TRUTH_SCHEMA_VERSION = "neo_final_truth_v1"
FINAL_TRUTH_ARTIFACT_TYPE = "final_truth"
FINAL_ALLOWED_STATUSES = frozenset({"ACTIVE"} | NON_CUT_STATUSES)  # {"ACTIVE","WD","DQ","DNS"}

REQUIRED_RECORD_FIELDS = (
    "player_id",
    "player_name",
    "final_rank",
    "final_score",
    "r4_score",
    "rounds_completed",
    "status",
    "top5_actual",
    "top10_actual",
    "top20_actual",
)


class FinalTruthError(ValueError):
    pass


@dataclass(frozen=True)
class FinalTruth:
    schema_version: str
    game_code: str
    tournament_name: str
    winner_player_id: str
    official_source: str
    collected_at: str
    raw_official_response_sha256: str
    parsed_canonical_sha256: str
    observed_player_count: int
    status_counts: dict
    synthetic_test_only: bool  # must be False for any real production write
    code_commit: str
    build_id: str
    records: list = field(default_factory=list)

    def __post_init__(self):
        bad_status = sorted({str(r.get("status", "ACTIVE")) for r in self.records} - FINAL_ALLOWED_STATUSES)
        if bad_status:
            raise FinalTruthError(f"FinalTruth.records contains never-valid status(es): {bad_status}")
        for r in self.records:
            missing = [f for f in REQUIRED_RECORD_FIELDS if f not in r]
            if missing:
                raise FinalTruthError(f"record for player_id={r.get('player_id')!r} missing required field(s): {missing}")
        winners = [r for r in self.records if str(r.get("player_id")) == str(self.winner_player_id)]
        if len(winners) != 1:
            raise FinalTruthError(f"winner_player_id={self.winner_player_id!r} must appear exactly once in records")
        ids = [str(r["player_id"]) for r in self.records]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise FinalTruthError(f"duplicate player_id(s) in FinalTruth.records: {dupes}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def build_final_truth(
    *,
    context: TournamentContext,
    official_source: str,
    collected_at: str,
    raw_official_response: bytes,
    records: list,
    repo_root: Path,
    build_id: str,
    synthetic_test_only: bool = False,
) -> FinalTruth:
    ids = [str(r.get("player_id")) for r in records]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise FinalTruthError(f"duplicate player_id(s) in FinalTruth.records: {dupes}")

    canonical = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    status_counts: dict = {}
    for r in records:
        status = str(r.get("status", "ACTIVE"))
        status_counts[status] = status_counts.get(status, 0) + 1

    rank_one = [r for r in records if str(r.get("final_rank")) == "1"]
    if len(rank_one) != 1:
        raise FinalTruthError(f"expected exactly one player at final_rank=1, found {len(rank_one)}")
    winner_player_id = str(rank_one[0]["player_id"])

    return FinalTruth(
        schema_version=FINAL_TRUTH_SCHEMA_VERSION,
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        winner_player_id=winner_player_id,
        official_source=official_source,
        collected_at=collected_at,
        raw_official_response_sha256=_sha256_bytes(raw_official_response),
        parsed_canonical_sha256=_sha256_bytes(canonical),
        observed_player_count=len(records),
        status_counts=status_counts,
        synthetic_test_only=synthetic_test_only,
        code_commit=_source_git_sha(repo_root),
        build_id=build_id,
        records=list(records),
    )


def final_truth_path(context: TournamentContext) -> Path:
    return context.artifact_path(FINAL_TRUTH_ARTIFACT_TYPE)


def final_truth_exists(context: TournamentContext) -> bool:
    return final_truth_path(context).is_file()


def write_final_truth_immutable(context: TournamentContext, truth: FinalTruth) -> Path:
    """Raises FileExistsError if a FINAL truth for this game_code
    already exists. A synthetic_test_only=True truth must NEVER be
    written to the real content/website_v2 tree -- callers building a
    test fixture must point context at a temp directory instead (see
    tests/test_final_truth.py)."""
    if truth.synthetic_test_only:
        raise FinalTruthError(
            "refusing to write a synthetic_test_only FinalTruth via the real write path -- "
            "synthetic fixtures must never be persisted as production truth"
        )
    path = final_truth_path(context)
    if path.is_file():
        raise FileExistsError(f"FINAL truth already exists and is immutable: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(truth), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def load_final_truth(context: TournamentContext) -> Optional[dict]:
    path = final_truth_path(context)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify_final_truth_hash(context: TournamentContext) -> bool:
    truth = load_final_truth(context)
    if truth is None:
        return False
    canonical = json.dumps(truth["records"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(canonical) == truth["parsed_canonical_sha256"]
