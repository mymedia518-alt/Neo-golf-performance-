import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "klpga_pipeline/content/website_v2/HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json"
OUTPUT = ROOT / "klpga_pipeline/content/website_v2/HANA_2026090002_SEASON_SG_SORTED_V1.json"

source = json.loads(INPUT.read_text(encoding="utf-8"))
records = []
for record in source["records"]:
    sg = record.get("current_official_sg") or {}
    total = sg.get("total")
    item = dict(record)
    if total is None:
        item["season_sg_status"] = "데이터 부족"
        item["season_sg_rank"] = None
    else:
        item["season_sg_status"] = "확인"
        item["season_sg_rank"] = None
    records.append(item)

records.sort(key=lambda r: (
    r["season_sg_status"] != "확인",
    -(r.get("current_official_sg") or {}).get("total", 0),
    r.get("k_rank") if r.get("k_rank") is not None else 999,
    r["official_display_name"],
))

rank = 0
for record in records:
    if record["season_sg_status"] == "확인":
        rank += 1
        record["season_sg_rank"] = rank

output = {
    "schema_version": "HANA_2026090002_SEASON_SG_SORTED_V1",
    "game_code": source["game_code"],
    "tournament_name": source["tournament_name"],
    "as_of": source["as_of"],
    "sort_rule": "season cumulative SG total descending; missing KLPGA SG last as 데이터 부족",
    "source_input": "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json",
    "coverage": {
        "total_players": len(records),
        "sg_confirmed": sum(r["season_sg_status"] == "확인" for r in records),
        "data_insufficient": sum(r["season_sg_status"] == "데이터 부족" for r in records),
        "foreign_or_amateur_not_converted": True,
    },
    "records": records,
}
OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(OUTPUT)
print(json.dumps(output["coverage"], ensure_ascii=False))
for record in records[:20]:
    sg = record.get("current_official_sg") or {}
    print(record["season_sg_rank"], record["official_display_name"], sg.get("total"), record["season_sg_status"])
print("DATA_INSUFFICIENT")
for record in records:
    if record["season_sg_status"] == "데이터 부족":
        print(record["official_display_name"])
