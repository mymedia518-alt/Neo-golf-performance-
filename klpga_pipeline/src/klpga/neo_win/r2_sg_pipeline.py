"""R2 HOUSE — SG ARCHAEOLOGY RESULT (P0-2).

CLASSIFICATION: B — an official, per-round SG component source exists
and already has an authoritative production parser in this codebase
(this is NOT a new calculator): `klpga.website_v2.official_data.
parse_sg_html`/`validate_sg_record`, reading KLPGA's own
`/load/leaderboard/strokesGained_detail` endpoint. This IS how NEO
historically derived OTT/APP/ARG/PUTT/TOTAL for every prior validated
tournament — confirmed by reading scripts/63_collect_historical_sg_
warehouse.py (the historical_sg_warehouse.json builder every PRE-stage
SG feature ultimately traces back to): it POSTs to that exact endpoint
per round (`round=1`, `2`, `3`, `4`, and blank for tournament-
cumulative) for every already-completed tournament, and already has a
named, non-fatal outcome for a round with nothing published yet
(`"OFFICIAL_SG_NOT_AVAILABLE"`, set when the endpoint returns zero
rows) -- i.e. "this round's SG isn't published yet" is an anticipated,
handled real-world case in the existing production collector, not a
new discovery.

RESIDUAL, DISCLOSED UNCERTAINTY: every prior real collection through
this endpoint (script 63) was run ONLY against tournaments already
filtered `is_completed` -- there is no evidence anywhere in this
repository of round=2 SG being fetched successfully WHILE round 3/4
had not yet happened. Whether KLPGA actually populates a round's SG
detail same-day (real-time, as the round finishes) or only backfills
it once the whole event concludes cannot be determined from this
sandbox (no live network access, confirmed structurally blocked all
session). This module does NOT assume either answer -- it fetches,
and reacts honestly to whatever the live response actually is:

  AVAILABLE    -- the endpoint returned real round=2 rows that pass
                  validate_sg_record's own tolerance check. Used.
  NOT_AVAILABLE -- the endpoint returned zero rows for round=2 (same
                  "OFFICIAL_SG_NOT_AVAILABLE" reason script 63 already
                  uses) -- WAIT, never fabricated.
  CORRUPT      -- rows were returned but fail validate_sg_record's
                  arithmetic tolerance check -- HARD_STOP (real data
                  corruption is not a WAIT condition; official
                  components must reconcile to the official total).

If AVAILABLE never actually happens in production, this degrades
exactly to the honest NOT_AVAILABLE/WAIT state documented in this
module's own history -- the R2 house never fabricates SG regardless of
which of these three the real endpoint turns out to produce.
"""
from __future__ import annotations

from klpga.website_v2.official_data import SG_KEYS, parse_sg_html, validate_sg_record

SG_ENDPOINT_PATH = "/load/leaderboard/strokesGained_detail"
"""Byte-identical to scripts/63_collect_historical_sg_warehouse.py's
own SG_PATH -- the one authoritative official SG endpoint, not a new
one invented for R2."""

STATUS_AVAILABLE = "AVAILABLE"
STATUS_NOT_AVAILABLE = "NOT_AVAILABLE"
STATUS_CORRUPT = "CORRUPT"


class SgIngestError(RuntimeError):
    """Raised only for STATUS_CORRUPT -- real official data that fails
    its own internal arithmetic reconciliation."""


def fetch_r2_sg_html(client, game_code: str) -> str:
    """Real HTTP POST to the official endpoint for round 2 specifically
    -- mirrors scripts/63's own `_post(SG_PATH, {"gameCode":..., "round":
    str(rnd)})` call exactly, generalized to any client/game_code."""
    import requests

    response = client.session.post(
        f"https://klpga.co.kr{SG_ENDPOINT_PATH}",
        data={"gameCode": game_code, "round": "2"},
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://klpga.co.kr"},
        timeout=60,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_and_validate_r2_sg(html: str) -> tuple[str, list[dict]]:
    """Pure (no I/O): parses the raw HTML and returns (status, rows).
    `rows` is empty for NOT_AVAILABLE/CORRUPT (never a partial guess);
    for AVAILABLE it is the real parsed+validated per-player rows,
    each carrying SG_KEYS (total/tee_to_green/off_the_tee/approach/
    around_green/putting) plus the raw `player` name and `validation`
    result."""
    try:
        parsed = parse_sg_html(html, scope="single_round", round_number=2)
    except ValueError:
        # "official SG table missing" -- same shape as script 63's own
        # `sg_response_rows == 0` -> OFFICIAL_SG_NOT_AVAILABLE outcome.
        return STATUS_NOT_AVAILABLE, []
    if not parsed:
        return STATUS_NOT_AVAILABLE, []

    validated = []
    for row in parsed:
        validation = validate_sg_record(row)
        if not (validation["total_within_tolerance"] and validation["t2g_within_tolerance"]):
            return STATUS_CORRUPT, []
        validated.append({**row, "validation": validation})
    return STATUS_AVAILABLE, validated


def join_r2_sg_to_frozen_players(sg_rows: list[dict], frozen_players: list[dict]) -> tuple[dict, list[str]]:
    """Joins the official SG rows (keyed only by the raw player NAME the
    endpoint itself returns -- it carries no player_id) to the R2
    freeze's own player_id-keyed records by exact name match, the same
    identity-join convention scripts/63's own `ids` lookup already
    uses. Returns (sg_by_player_id, unresolved_names) -- an unresolved
    name is reported, never silently dropped or guessed."""
    name_to_id = {p["player_name"]: p["player_id"] for p in frozen_players}
    sg_by_player_id: dict[str, dict] = {}
    unresolved: list[str] = []
    for row in sg_rows:
        player_id = name_to_id.get(row["player"])
        if player_id is None:
            unresolved.append(row["player"])
            continue
        sg_by_player_id[player_id] = {key: row[key] for key in SG_KEYS}
    return sg_by_player_id, unresolved


def ingest_r2_sg(client, game_code: str, frozen_players: list[dict]) -> dict:
    """The one entry point the R2 operator calls. Returns a dict:
    {"status": AVAILABLE|NOT_AVAILABLE, "sg_by_player_id": {...},
    "unresolved_names": [...]}. Raises SgIngestError only for CORRUPT
    (a real data-integrity hard stop, never silently swallowed)."""
    html = fetch_r2_sg_html(client, game_code)
    status, rows = parse_and_validate_r2_sg(html)
    if status == STATUS_CORRUPT:
        raise SgIngestError(
            f"official R2 SG components for game_code={game_code!r} failed arithmetic "
            "reconciliation (total/tee_to_green vs component sum) -- refusing to trust corrupted official data"
        )
    if status == STATUS_NOT_AVAILABLE:
        return {"status": STATUS_NOT_AVAILABLE, "sg_by_player_id": {}, "unresolved_names": []}
    sg_by_player_id, unresolved = join_r2_sg_to_frozen_players(rows, frozen_players)
    return {"status": STATUS_AVAILABLE, "sg_by_player_id": sg_by_player_id, "unresolved_names": unresolved}
