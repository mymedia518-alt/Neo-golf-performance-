"""Targeted KLPGA 2026 player baseline pull for NEO A/B validation.

Uses the already-confirmed public loadLocationRecord endpoint and existing
parser. Pulls only the decision-relevant metric families and writes one
JSON artifact containing the exact returned values for requested players.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga import config
from klpga.discovery.response_parser import parse_record_response
from klpga.http_client import PoliteHttpClient

FAMILIES = {
    "Tee05",      # Par4 tee distance distribution
    "Tee06",      # Par4 fairway accuracy
    "Approach01", # GIR by approach distance
    "Approach03", # fairway GIR by distance
    "Approach05", # rough GIR by distance
    "Approach07", # birdie-or-better by state/distance
    "Approach08", # post-approach remaining distance
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026")
    ap.add_argument("--players", default="10097,9784")
    ap.add_argument("--taxonomy", default=str(ROOT / "docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.json"))
    ap.add_argument("--out", default=str(ROOT / "data/player_baseline/ab_10097_9784_2026.json"))
    ap.add_argument("--cache-dir", default=str(ROOT / "data/raw_cache/http"))
    args = ap.parse_args()

    wanted = {x.strip() for x in args.players.split(",") if x.strip()}
    taxonomy = json.loads(Path(args.taxonomy).read_text(encoding="utf-8"))

    leaves = []
    seen = set()
    for leaf in taxonomy["leaves"]:
        if leaf.get("menu2") not in FAMILIES or leaf.get("leaf_level") != "menu3":
            continue
        key = (leaf.get("menu1"), leaf.get("menu2"), leaf.get("menu3"))
        if key in seen:
            continue
        seen.add(key)
        leaves.append(leaf)

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir), min_interval_sec=1.5)
    result = {
        "season": args.season,
        "players": sorted(wanted),
        "source_endpoint": config.RECORD_TAXONOMY_ENDPOINT,
        "families": sorted(FAMILIES),
        "requests": [],
    }

    for i, leaf in enumerate(leaves, 1):
        form = {
            "season": args.season,
            "menu1": leaf["menu1"],
            "menu2": leaf["menu2"],
            "menu3": leaf["menu3"],
        }
        html = client.post_text(config.RECORD_TAXONOMY_ENDPOINT, data=form)
        parsed = parse_record_response(html)
        selected = []
        for row in parsed.rows:
            if row.player_code in wanted:
                selected.append({
                    "player_code": row.player_code,
                    "player_name": row.player_name,
                    "rank": row.rank,
                    "values": row.values,
                })
        result["requests"].append({
            "menu1": leaf["menu1"],
            "menu2": leaf["menu2"],
            "menu3": leaf["menu3"],
            "label": leaf.get("menu3_label"),
            "source_metric_key": leaf.get("source_metric_key"),
            "parse_status": parsed.parse_status,
            "row_count": len(parsed.rows),
            "selected": selected,
        })
        print(f"[{i}/{len(leaves)}] {leaf['menu2']} {leaf['menu3']} rows={len(parsed.rows)} selected={len(selected)}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    found = {p: 0 for p in wanted}
    for req in result["requests"]:
        for row in req["selected"]:
            found[row["player_code"]] += 1
    print("FOUND", json.dumps(found, ensure_ascii=False), flush=True)
    print("OUTPUT", out, flush=True)
    return 0 if all(v > 0 for v in found.values()) else 2

if __name__ == "__main__":
    raise SystemExit(main())
