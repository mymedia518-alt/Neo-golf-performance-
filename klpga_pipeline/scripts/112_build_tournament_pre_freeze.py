"""Build TOURNAMENT_PRE_FREEZE.json -- NEO SITE V5 Mission 3.

Assembles the canonical lifecycle's pre-tournament freeze point:
    OFFICIAL ENTRY LIST -> FIELD IDENTITY MATCH -> PRE SNAPSHOT -> PRE MODEL
from artifacts that ALREADY exist for OK Open 2026 (this script does not
collect anything new -- it composes and hashes what scripts/72 and its
predecessors already collected against live klpga.co.kr, each with its
own real retrieved_at timestamp):
  - OK_OPEN_2026_ENTRY_SNAPSHOT.json      -- the official entry list
  - HOME_REGULAR_TOUR_PLAYER_MASTER.json  -- canonical player_id space
  - OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json -- the contemporaneous K-Rank
    snapshot (already scoped to this tournament's exact retrieval time)
  - OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json -- the contemporaneous
    NEO skill/performance input snapshot (already carries its own
    cutoff/future_data_excluded/data_version/warehouse_generated_at)
  - OK_OPEN_2026_PRE_WIN_FORECAST.json    -- the PRE model's predictions,
    generated only from the above (future_data_excluded: true)

FIELD IDENTITY MATCH here means: every entrant's player_id must resolve
to a name in HOME_REGULAR_TOUR_PLAYER_MASTER.json. Anyone who does not
is reported under unmatched_field, never silently dropped or silently
included as if matched.

Freezing/hashing: once written, this artifact's own artifact_hash covers
every field this script controls (game_code, tournament_name, field,
player_ids, snapshots, model_version, freeze_timestamp) EXCLUDING
generated_at (which legitimately differs on every regeneration even of
byte-identical inputs) -- so re-running this script against the exact
same source artifacts reproduces the exact same hash, while any change
to the underlying evidence changes it. There is no in-place-edit path:
to change a PRE freeze after publication, a NEW artifact_hash must be
produced and the change must be visible in git history -- this script
itself never edits an existing frozen file in place, only overwrites
wholesale (git preserves the prior version).

RETROSPECTIVE-RESEARCH GUARD: this script only ever reads pre-tournament
-scoped source files (entry snapshot, K-Rank snapshot, PRE performance
snapshot, PRE win forecast) -- it has no code path that reads any R1/R2/
R3/FINAL result artifact. Do not add one without also adding an explicit
is_retrospective_research: true marker to the output (see module
docstring in the mission brief: "Never use post-R1 information to
rebuild a historical PRE prediction without explicitly marking it as
retrospective research").
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONTENT = ROOT / "content" / "website_v2"

GAME_CODE = "2026120001"
TOURNAMENT_NAME = "OK저축은행 읏맨 오픈"
MODEL_VERSION = "M4"

ENTRY_SNAPSHOT_PATH = CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
HOME_MASTER_PATH = CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"
K_RANK_PATH = CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
NEO_INPUT_PATH = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"
FORECAST_PATH = CONTENT / "OK_OPEN_2026_PRE_WIN_FORECAST.json"
OUT_PATH = CONTENT / "TOURNAMENT_PRE_FREEZE.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    entry_doc = json.loads(ENTRY_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    home_master = json.loads(HOME_MASTER_PATH.read_text(encoding="utf-8"))
    k_rank_doc = json.loads(K_RANK_PATH.read_text(encoding="utf-8"))
    neo_input_doc = json.loads(NEO_INPUT_PATH.read_text(encoding="utf-8"))
    forecast_doc = json.loads(FORECAST_PATH.read_text(encoding="utf-8")) if FORECAST_PATH.is_file() else None

    canonical_ids = {str(r["player_id"]) for r in home_master["records"]}
    canonical_names = {str(r["player_id"]): r["player_name"] for r in home_master["records"]}

    field: list[dict] = []
    unmatched_field: list[dict] = []
    for entrant in entry_doc["entries"]:
        pid = str(entrant["player_id"])
        matched = pid in canonical_ids
        record = {
            "player_id": pid,
            "entry_name": entrant.get("player_name"),
            "canonical_player_id_match": matched,
            "canonical_name": canonical_names.get(pid),
            "qualification_category": entrant.get("qualification_category"),
            "qualification_reason": entrant.get("qualification_reason"),
        }
        (field if matched else unmatched_field).append(record)

    player_ids = sorted((r["player_id"] for r in field), key=int)

    doc = {
        "schema_version": "neo_tournament_pre_freeze_v1",
        "game_code": GAME_CODE,
        "tournament_name": TOURNAMENT_NAME,
        "field": field,
        "player_ids": player_ids,
        "unmatched_field": unmatched_field,
        "identity_match_summary": {
            "entrants_total": len(entry_doc["entries"]),
            "matched": len(field),
            "unmatched": len(unmatched_field),
        },
        "entry_source": {
            "source_url": entry_doc.get("source_url"),
            "artifact": "OK_OPEN_2026_ENTRY_SNAPSHOT.json",
            "artifact_sha256": _sha256_file(ENTRY_SNAPSHOT_PATH),
        },
        "entry_source_timestamp": entry_doc.get("retrieved_at"),
        "k_rank_snapshot": {
            "artifact": "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json",
            "artifact_sha256": _sha256_file(K_RANK_PATH),
            "official_source": k_rank_doc.get("official_source"),
            "ranking_date": k_rank_doc.get("ranking_date"),
            "retrieved_at": k_rank_doc.get("retrieved_at"),
            "records": [
                {"player_id": str(r["player_id"]), "official_rank": r.get("official_rank")}
                for r in k_rank_doc.get("records", ())
                if str(r["player_id"]) in canonical_ids
            ],
        },
        "neo_input_snapshot": {
            "artifact": "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json",
            "artifact_sha256": _sha256_file(NEO_INPUT_PATH),
            "cutoff": neo_input_doc.get("cutoff"),
            "future_data_excluded": neo_input_doc.get("future_data_excluded"),
            "data_version": neo_input_doc.get("data_version"),
            "warehouse_generated_at": neo_input_doc.get("warehouse_generated_at"),
            "calculation_version": neo_input_doc.get("calculation_version"),
            "entry_snapshot_sha256": neo_input_doc.get("entry_snapshot_sha256"),
        },
        "pre_predictions": {
            "artifact": "OK_OPEN_2026_PRE_WIN_FORECAST.json" if forecast_doc else None,
            "artifact_sha256": _sha256_file(FORECAST_PATH) if forecast_doc else None,
            "model_version": forecast_doc.get("model_version") if forecast_doc else MODEL_VERSION,
            "cutoff": forecast_doc.get("cutoff") if forecast_doc else neo_input_doc.get("cutoff"),
            "future_data_excluded": forecast_doc.get("future_data_excluded") if forecast_doc else None,
            "status": "AVAILABLE" if forecast_doc else "NOT_YET_GENERATED",
        },
        "model_version": MODEL_VERSION,
        "is_retrospective_research": False,
        "generated_at": now(),
        "freeze_timestamp": neo_input_doc.get("cutoff"),
        "source_provenance": {
            "entry_source": entry_doc.get("source_url"),
            "k_rank_source": k_rank_doc.get("official_source"),
            "neo_input_source": "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json (see neo_input_snapshot for its own chained provenance)",
        },
        "validation_status": (
            "FIELD_IDENTITY_CLEAN" if not unmatched_field else "UNMATCHED_IDENTITIES_PRESENT"
        ),
    }

    hash_payload = {k: v for k, v in doc.items() if k not in ("generated_at", "artifact_hash")}
    doc["artifact_hash"] = hashlib.sha256(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(doc["identity_match_summary"] | {
        "validation_status": doc["validation_status"], "artifact_hash": doc["artifact_hash"][:12] + "...",
    }, ensure_ascii=False))
    return doc


if __name__ == "__main__":
    build()
