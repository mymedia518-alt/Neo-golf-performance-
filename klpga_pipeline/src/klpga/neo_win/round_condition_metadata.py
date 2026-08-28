"""BETA #001 R1 -> R2 evaluation pipeline, Section F: round-condition /
weather metadata for Round 2.

This is a FIELD/USER OBSERVATION, explicitly kept separate from the
official CUT/WD/DQ/MADE_CUT status Section B derives from the real
official leaderboard. Nothing in this module feeds any probability,
classification, or model input — it is descriptive context only,
attached alongside the R2 evaluation output for human readers. The
`official_*` fields (delay/suspension/suspension_time/restart_time/
round_completed_time) are prepared here as real, named fields but left
None until an official, site-sourced value for them exists — never
inferred or filled in from the field observation alone.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

SOURCE_TYPE_FIELD_OBSERVATION = "field/user observation"
SOURCE_TYPE_OFFICIAL = "official"


@dataclass(frozen=True)
class RoundConditionMetadata:
    game_code: str
    round_number: int
    date: str
    weather: str
    green_condition: str
    play_status_at_observation: str
    source_type: str
    official_delay: Optional[str] = None
    official_suspension: Optional[str] = None
    suspension_time: Optional[str] = None
    restart_time: Optional[str] = None
    round_completed_time: Optional[str] = None


def build_r2_round_condition_metadata(game_code: str) -> RoundConditionMetadata:
    """The real, user-supplied field observation for this R2 round.
    `official_*` fields are left None — genuinely unknown at the time
    this pipeline was prepared, never guessed or backfilled from the
    field observation."""
    return RoundConditionMetadata(
        game_code=game_code,
        round_number=2,
        date="2026-08-28",
        weather="rain",
        green_condition="standing water beginning to appear",
        play_status_at_observation="play continued",
        source_type=SOURCE_TYPE_FIELD_OBSERVATION,
    )


def round_condition_metadata_to_dict(metadata: RoundConditionMetadata) -> dict:
    return asdict(metadata)


def write_round_condition_metadata_json(metadata: RoundConditionMetadata, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(round_condition_metadata_to_dict(metadata), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def read_round_condition_metadata_json(path: Path) -> RoundConditionMetadata:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RoundConditionMetadata(**data)
