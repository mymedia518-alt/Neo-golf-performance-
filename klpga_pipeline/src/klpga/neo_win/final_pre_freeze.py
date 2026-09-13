"""4R FINAL PRE-BUILD Phase 1-2: the PRE-FINAL forecast freeze + its
machine-readable manifest.

Does NOT create a new forecast snapshot. The already-frozen POST-R3
forecast (content.website_v2.<game_code>_POST_R3_FINAL_FORECAST.json,
built by scripts/126_build_r3_freeze_and_post_r3_forecast.py, itself
binding r3_frozen_evidence's own sha256 -- see r3_freeze.py) already IS
the PRE-FINAL snapshot the mission asks for: it is the last forecast
computed before the final competitive round (FR/R4), built exclusively
from R1-R3 official data (future_data_excluded=true, feature_cutoff=
END_OF_R3 fields already on the artifact itself). Per the mission's own
rule ("기존 snapshot이 이미 존재한다면 무조건 새로 만들지 말고 먼저
provenance와 생성시각을 검증한다"), this module verifies and freezes
THAT artifact rather than duplicating it.

This module adds exactly what did not already exist:
  1. An explicit, re-verifiable future-leakage scan over the frozen
     forecast's own JSON keys/values (FR/R4/FINAL-shaped fields would
     never legitimately appear in a POST_R3 artifact; this is a
     structural check, not a guess).
  2. A content hash of the frozen forecast's exact bytes
     (PRE_FINAL_FREEZE_SHA256) and a drift-detector against it.
  3. A separate, machine-readable FREEZE_MANIFEST artifact recording
     that hash + the surprise-classification thresholds (Phase 5),
     pre-registered now, before any FINAL result exists.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga.tournament_context import TournamentContext

PRE_FINAL_SNAPSHOT_ARTIFACT_TYPE = "post_r3_final_forecast"
FREEZE_MANIFEST_ARTIFACT_TYPE = "pre_final_freeze_manifest"

# Any key or string value in the frozen forecast containing one of
# these substrings would mean round-4 (or later) evidence leaked into
# a forecast that is supposed to be built exclusively from R1-R3 data.
# Deliberately generic (not tied to this one game_code) so the same
# check is reusable for the next tournament's PRE-FINAL freeze.
#
# NOT included: "final_rank"/"final_score" -- those collide with this
# forecast's own legitimate "neo_final_rank" (NEO's PREDICTED rank,
# computed entirely from R1-R3 data); the FINAL TRUTH schema's actual
# "final_rank" field lives in a completely separate artifact
# (final_truth.py) and is never expected inside a POST_R3 forecast at
# all, so a same-named key never legitimately co-occurs here anyway.
_FUTURE_LEAKAGE_MARKERS = ("r4_", "_r4", "fr_score", "fr_result", "top5_actual", "top10_actual", "top20_actual")

# Pre-registered NOW (Phase 5), before any FINAL result exists --
# never adjusted after results are seen. NEO's own top10_pct-based
# forecast already treats "top 10" as the operative threshold
# elsewhere in this codebase (klpga.models.metrics.top_k_hit(..., 10)
# is the SECONDARY headline metric); reused here rather than inventing
# a second, ad hoc cutoff.
SURPRISE_CLASSIFICATION_RULE = {
    "neo_high_if": "neo_final_rank <= 10",
    "actual_high_if": "final_rank <= 10",
    "rationale": "matches the existing top10_pct / top_k_hit(10) threshold "
                  "already used as this project's secondary headline metric "
                  "-- not invented for this classification",
}


class FutureLeakageDetected(RuntimeError):
    pass


@dataclass(frozen=True)
class PreFinalFreezeManifest:
    schema_version: str
    status: str  # "FROZEN"
    game_code: str
    tournament_name: str
    forecast_source_round: str  # "R3"
    snapshot_type: str  # "PRE_FINAL_R3"
    snapshot_artifact: str
    created_at: str
    verified_at: str
    model_version: str  # the frozen forecast's own build_id
    code_commit: str  # the frozen forecast's own code_commit
    seed: int
    input_fingerprint: str  # the frozen forecast's own r3_freeze_sha256
    snapshot_sha256: str  # PRE_FINAL_FREEZE_SHA256
    player_count: int
    future_data_excluded: bool
    future_leakage_check: str  # "PASS" (this module raises rather than ever recording FAIL)
    surprise_classification_rule: dict


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pre_final_snapshot_path(context: TournamentContext) -> Path:
    return context.artifact_path(PRE_FINAL_SNAPSHOT_ARTIFACT_TYPE)


def _freeze_manifest_path(context: TournamentContext) -> Path:
    return context.artifact_path(FREEZE_MANIFEST_ARTIFACT_TYPE)


def load_pre_final_snapshot(context: TournamentContext) -> dict:
    path = _pre_final_snapshot_path(context)
    if not path.is_file():
        raise FileNotFoundError(
            f"no PRE-FINAL (POST_R3) forecast snapshot at {path} -- nothing to freeze yet"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_strings(value) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out.append(str(k))
            out.extend(_walk_strings(v))
    elif isinstance(value, list):
        for item in value:
            out.extend(_walk_strings(item))
    else:
        out.append(str(value))
    return out


def check_future_leakage(snapshot: dict) -> None:
    """Raises FutureLeakageDetected if any key/value anywhere in the
    snapshot looks like it carries round-4/FINAL evidence. Never
    "fixes" a leak silently -- a leaking snapshot must never be frozen."""
    haystack = _walk_strings(snapshot)
    lowered = [s.lower() for s in haystack]
    hits = sorted({
        marker for marker in _FUTURE_LEAKAGE_MARKERS
        if any(marker in s for s in lowered)
    })
    if hits:
        raise FutureLeakageDetected(
            f"PRE-FINAL snapshot contains future-round-shaped marker(s) {hits} -- "
            "refusing to freeze a snapshot that may carry round-4/FINAL data"
        )
    if snapshot.get("final_round_number") is not None and snapshot.get("source_round") is not None:
        if int(snapshot["final_round_number"]) == int(snapshot["source_round"]):
            raise FutureLeakageDetected(
                "snapshot's source_round equals final_round_number -- this would be "
                "the FINAL round's own forecast, not a PRE-FINAL one"
            )


def verify_and_build_manifest(context: TournamentContext) -> PreFinalFreezeManifest:
    """Verifies provenance + absence of future leakage on the ALREADY
    frozen POST_R3 forecast, then builds (but does not write) the
    freeze manifest. Raises FutureLeakageDetected / ValueError rather
    than ever producing a manifest for bad input."""
    snapshot_path = _pre_final_snapshot_path(context)
    snapshot = load_pre_final_snapshot(context)
    check_future_leakage(snapshot)

    if snapshot.get("stage") != "POST_R3":
        raise ValueError(f"expected stage=POST_R3, got {snapshot.get('stage')!r}")
    if snapshot.get("future_data_excluded") is not True:
        raise ValueError("frozen forecast does not assert future_data_excluded=true")

    records = snapshot.get("records") or []
    if not records:
        raise ValueError("frozen forecast has zero player records")

    raw_bytes = snapshot_path.read_bytes()
    snapshot_sha256 = _sha256_bytes(raw_bytes)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return PreFinalFreezeManifest(
        schema_version="neo_pre_final_freeze_manifest_v1",
        status="FROZEN",
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        forecast_source_round="R3",
        snapshot_type="PRE_FINAL_R3",
        snapshot_artifact=snapshot_path.name,
        created_at=str(snapshot.get("build_id") or "unknown"),
        verified_at=now,
        model_version=str(snapshot.get("build_id") or "unknown"),
        code_commit=str(snapshot.get("code_commit") or "unknown"),
        seed=int(snapshot.get("seed") or 0),
        input_fingerprint=str(snapshot.get("r3_freeze_sha256") or "unknown"),
        snapshot_sha256=snapshot_sha256,
        player_count=len(records),
        future_data_excluded=True,
        future_leakage_check="PASS",
        surprise_classification_rule=dict(SURPRISE_CLASSIFICATION_RULE),
    )


def write_freeze_manifest_if_absent(context: TournamentContext) -> tuple[Path, bool]:
    """Write-once: never overwrites an existing manifest (mirrors
    r3_freeze.py's write-once discipline). Returns (path, written)."""
    path = _freeze_manifest_path(context)
    if path.is_file():
        return path, False
    manifest = verify_and_build_manifest(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path, True


def load_freeze_manifest(context: TournamentContext) -> Optional[dict]:
    path = _freeze_manifest_path(context)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def detect_snapshot_drift(context: TournamentContext) -> bool:
    """True if the underlying PRE-FINAL snapshot's bytes no longer
    match the hash the manifest recorded at freeze time -- i.e. the
    supposedly-immutable forecast changed after being frozen."""
    manifest = load_freeze_manifest(context)
    if manifest is None:
        raise FileNotFoundError("no freeze manifest exists yet -- nothing to check drift against")
    current_bytes = _pre_final_snapshot_path(context).read_bytes()
    return _sha256_bytes(current_bytes) != manifest["snapshot_sha256"]
