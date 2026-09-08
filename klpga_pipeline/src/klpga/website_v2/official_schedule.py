"""Red Team FAIL B remediation: a generic official-schedule ingestion
layer.

TOURNAMENT_SITE_REGISTRY.json only ever grew per-tournament route/
presentation metadata (url_base, hub_card copy) for whichever
tournaments already had a public page -- it was never meant to be a
calendar, so an officially-scheduled tournament with no public page
yet simply had nowhere to live and disappeared from HOME entirely.

This module reads content/website_v2/OFFICIAL_KLPGA_SCHEDULE.json --
the authoritative calendar -- and is the ONLY thing
klpga.website_v2.tournament_chronology may treat as a source of
tournament identity/dates/venue. It is deliberately generic: a new
tournament needs a new entry in that JSON file (real start_date/
end_date/venue plus real source_identity/retrieved_at/source_hash
provenance), never a source-code change here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

_REQUIRED_FIELDS = ("game_code", "tournament_name", "start_date", "end_date", "source_identity", "retrieved_at", "source_hash")


@dataclass(frozen=True)
class ScheduleEntry:
    game_code: str
    tournament_name: str
    start_date: str
    end_date: str
    source_identity: str
    retrieved_at: str
    source_hash: str
    venue: str | None = None


class OfficialScheduleError(Exception):
    """Raised when the official schedule artifact is missing a
    required field -- a hard stop, never a silent skip, since an
    incomplete entry cannot be trusted for calendar chronology."""


def load_official_schedule(path: Path) -> list[ScheduleEntry]:
    """Load and validate every entry in the official schedule
    artifact. Each entry must carry every field in _REQUIRED_FIELDS --
    an entry missing one (e.g. real venue/course when not yet
    officially available) may still omit `venue` (the one genuinely
    optional field), but never any of the provenance/identity/date
    fields that make it usable as a calendar record at all."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = []
    for raw in data.get("tournaments") or []:
        missing = [f for f in _REQUIRED_FIELDS if not raw.get(f)]
        if missing:
            raise OfficialScheduleError(f"{path}: schedule entry {raw.get('game_code', '?')!r} missing required field(s): {missing}")
        entries.append(ScheduleEntry(
            game_code=str(raw["game_code"]),
            tournament_name=str(raw["tournament_name"]),
            start_date=str(raw["start_date"]),
            end_date=str(raw["end_date"]),
            source_identity=str(raw["source_identity"]),
            retrieved_at=str(raw["retrieved_at"]),
            source_hash=str(raw["source_hash"]),
            venue=raw.get("venue"),
        ))
    return entries
