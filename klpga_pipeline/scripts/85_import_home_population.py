"""Create the checked-in HOME population contract from the validated DB export."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-master-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "content" / "website_v2" / "HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    args = parser.parse_args()
    with args.player_master_csv.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    seen = set(); records = []
    for row in source:
        player_id = str(row["player_id"]).strip()
        name = str(row["player_name"]).strip()
        if not player_id or not name or player_id in seen:
            raise SystemExit(f"invalid canonical player row: {player_id!r} {name!r}")
        seen.add(player_id)
        records.append({"player_id": player_id, "player_name": name, "provenance": {"source_table": "player_master", "source_export": "player_master.csv", "identity_key": "player_id"}})
    document = {
        "schema_version": "neo_home_population_v1",
        "population_kind": "regular_tour_historical_player_master",
        "population_definition": "players observed in the validated 100 most-recent completed KLPGA regular-tour event warehouse",
        "population_validation_state": "BLOCKED_CURRENT_REGISTRY_EQUIVALENCE_NOT_PROVEN",
        "source_database_provenance": "validated official-source KLPGA historical database checkpoint; README full-100 collection",
        "player_count": len(records),
        "records": sorted(records, key=lambda item: (item["player_name"], item["player_id"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {len(records)} canonical HOME players to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
