"""2025100001 pre-event acquisition manifest builder (HJ 2026100004
gap, continued 2026-10-06): exactly which prior-season tournaments
need their real scoreRecord HTML captured so
klpga.collectors.score_record.extract_hole_outcomes can compute real
birdie/eagle/par/bogey/double-or-worse counts for 김민솔 (and the rest
of the 2025 field) from BEFORE the 2025 Stableford event.

SOURCES (both real, already in this repo, cross-checked against each
other):
  - klpga_pipeline/content/website_v2/historical_sg_warehouse_corrected_v2.json
    identifies WHICH game_codes/tournaments/players exist for season
    2025 before the target event (the bounded set the previous gate
    analysis already found: 23 tournaments) -- used here only for
    tournament identity/name/player-count/round-count, never for a
    Stableford feature itself (it has no outcome counts).
  - klpga_pipeline/content/website_v2/TOURNAMENT_MASTER_DATES_V1.json
    gives each game_code's REAL exact start_date (from the Windows
    production tournament_master table, generated_at_utc
    2026-09-10) -- used here to confirm the leakage cutoff at DAY
    granularity, replacing the earlier gate analysis's more
    conservative month-only heuristic. All 23 confirmed strictly
    before 2025-10-01 (the real 2025100001 event_start_date, see
    klpga.website_v2.stableford_historical_dates) -- the latest is
    2025-09-25, nowhere close to the cutoff.

end_date is DERIVED, not independently sourced: start_date + (max
observed per-player `rounds` value in the SG warehouse for that
game_code, minus 1) days, on the same consecutive-calendar-day
convention already CONFIRMED real for all 3 Stableford events (see
stableford_historical_dates's own "라운드 마감" timestamps, which are
on 4 consecutive days each). This manifest marks end_date explicitly
as derived, not a page-confirmed fact, so it is never mistaken for a
second independently-sourced field."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

CONTENT_ROOT = Path(__file__).resolve().parents[3] / "content" / "website_v2"
SG_WAREHOUSE_PATH = CONTENT_ROOT / "historical_sg_warehouse_corrected_v2.json"
MASTER_DATES_PATH = CONTENT_ROOT / "TOURNAMENT_MASTER_DATES_V1.json"


@dataclass(frozen=True)
class ManifestEntry:
    game_code: str
    tournament_name: str
    start_date: str  # ISO, real, from TOURNAMENT_MASTER_DATES_V1.json
    end_date: str  # ISO, DERIVED (see module docstring) -- not independently confirmed
    end_date_is_derived: bool
    before_target_event_start: bool
    player_count_sg_warehouse: int
    round_count: int
    acquisition_status: str  # "NOT_YET_ACQUIRED" | "ACQUIRED" | "ACQUISITION_FAILED"
    response_status: int | None = None
    response_bytes: int | None = None
    sha256: str | None = None
    acquired_at_utc: str | None = None
    parser_verdict: str | None = None  # "SOURCE_PASS" | "SOURCE_FAIL" | None


def build_manifest(target_game_code: str, target_event_start_date: date) -> list[ManifestEntry]:
    sg_records = json.loads(SG_WAREHOUSE_PATH.read_text(encoding="utf-8"))["records"]
    master_dates = json.loads(MASTER_DATES_PATH.read_text(encoding="utf-8"))["dates"]

    target_season = target_event_start_date.year
    by_code: dict[str, dict] = {}
    for r in sg_records:
        if r["season"] != target_season or r["scope"] != "tournament_cumulative":
            continue
        if r["game_code"] == target_game_code:
            continue
        entry = by_code.setdefault(
            r["game_code"], {"name": r["tournament"], "rounds": set(), "players": set()}
        )
        entry["rounds"].add(r["rounds"])
        entry["players"].add(r["player"])

    manifest = []
    for game_code in sorted(by_code):
        start_str = master_dates.get(game_code)
        if start_str is None:
            continue  # no real date available for this code -- excluded, never guessed
        y, m, d = map(int, start_str.split("-"))
        start = date(y, m, d)
        before_target = start < target_event_start_date
        if not before_target:
            continue  # never include a same-day-or-later tournament in the manifest at all

        info = by_code[game_code]
        round_count = max(info["rounds"])
        end = start + timedelta(days=round_count - 1)

        manifest.append(
            ManifestEntry(
                game_code=game_code,
                tournament_name=info["name"],
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                end_date_is_derived=True,
                before_target_event_start=True,
                player_count_sg_warehouse=len(info["players"]),
                round_count=round_count,
                acquisition_status="NOT_YET_ACQUIRED",
            )
        )
    return manifest


def manifest_as_json(entries: list[ManifestEntry]) -> list[dict]:
    return [vars(e) for e in entries]
