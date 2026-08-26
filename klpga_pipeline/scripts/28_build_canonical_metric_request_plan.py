"""Phase B1 CLASS 2 fix — build the REAL canonical metric request plan
from an already-produced Phase A taxonomy. Read-only, ZERO network
access (this script never fetches anything — it only reads a local
JSON file already produced by scripts/26), no DB writes, no
Prediction/model/archive access.

Real evidence (docs/discovery/raw_samples/All__Sg__2025.html — a live
menu1="All" request returned HTTP 200, 0 rows, and a body containing
the ENTIRE navigation menu tree itself) proved that every menu1="All"
leaf discovered by Phase A is a navigation/container node, never a
requestable metric. This script filters those out, alongside
malformed leaves (blank menu1/menu2) and exact-duplicate DOM entries,
to answer: "how many REAL KLPGA metric requests exist?" It writes:

  docs/discovery/KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json

Then STOPS. This does NOT authorize firing any of the listed requests
— that remains Phase B2, separately gated and NOT started by this
script. Nothing here fabricates a menu3 value or silently resolves a
menu3 collision; both are preserved and reported (see
`canonical_plan.py`'s own docstring).

Usage (fully offline — no live site access needed):
    python scripts\\28_build_canonical_metric_request_plan.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.canonical_plan import build_canonical_plan, build_canonical_plan_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_TAXONOMY_LOAD_FAILED = 5


def run(taxonomy: dict, source_taxonomy_path: str, out_dir: Path) -> int:
    counts, plan = build_canonical_plan(taxonomy)

    print("Canonical metric request plan counts:")
    print(f"  total DOM-discovered nodes:              {counts.total_dom_discovered_nodes}")
    print(f"  malformed leaves (blank identity):        {counts.malformed_leaf_count}")
    print(f"  requestable menu2-level metrics:          {counts.requestable_menu2_leaf_count}")
    print(f"  requestable menu3-level metrics:          {counts.requestable_menu3_leaf_count}")
    print(f"  navigation/container nodes:                {counts.navigation_container_count}")
    print(f"  exact duplicate DOM entries:               {counts.exact_duplicate_count}")
    print(f"  CANONICAL requestable metric count:        {counts.canonical_requestable_metric_count}")
    print(f"  menu3 collisions (canonical set):          {counts.menu3_collision_count}")
    print()

    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    out_path = out_dir / "KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json"
    out_path.write_text(
        build_canonical_plan_json(taxonomy, generated_at=generated_at, source_taxonomy=source_taxonomy_path),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")
    print()
    print(
        "This is a request PLAN only — no requests were made. Phase B2 "
        "(firing all canonical requests) remains a separate, not-yet-"
        "authorized step."
    )
    return EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to a Phase A KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "discovery"))
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        print("Run scripts/26_discover_klpga_record_taxonomy.py first.")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    return run(taxonomy, str(taxonomy_path), Path(args.out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
