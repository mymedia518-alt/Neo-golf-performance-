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
  docs/discovery/KLPGA_MALFORMED_LEAF_REPORT.csv

Then STOPS. This does NOT authorize firing any of the listed requests
— that remains Phase B2, separately gated and NOT started by this
script. Nothing here fabricates a menu3 value or silently resolves a
menu3 collision; both are preserved and reported (see
`canonical_plan.py`'s own docstring).

SAFETY GUARD: a live Windows run against the real 283-leaf taxonomy
found 272 leaves (~96%) classified malformed — far too many to accept
silently. This script now runs `check_sanity_invariants()` after
computing counts and, if either guard trips (malformed ratio > 10%, or
the canonical count is >80% smaller than the valid-identity leaf
count), prints the violation(s), STILL writes both output files (the
data is real and worth having on disk for inspection), but returns a
non-zero, distinct exit code (`EXIT_SANITY_CHECK_FAILED`) so this is
never mistaken for a clean, trustworthy canonical plan. These
thresholds are diagnostic guards, not claims about the true correct
count.

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

from klpga.discovery.canonical_plan import (  # noqa: E402
    build_canonical_plan,
    build_canonical_plan_json,
    build_identity_key_collision_report,
    build_malformed_leaf_report,
    check_sanity_invariants,
    group_counts_by_family,
    to_identity_key_collision_report_csv,
    to_malformed_leaf_report_csv,
)

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_SANITY_CHECK_FAILED = 6
EXIT_TAXONOMY_LOAD_FAILED = 5

_FAMILY_PRINT_ORDER = ["Sg", "Tee", "Approach", "Around", "Putt", "other"]


def run(taxonomy: dict, source_taxonomy_path: str, out_dir: Path) -> int:
    counts, plan = build_canonical_plan(taxonomy)
    malformed_rows = build_malformed_leaf_report(taxonomy)
    families = group_counts_by_family(taxonomy)

    valid_leaf_count = counts.total_dom_discovered_nodes - counts.malformed_leaf_count

    print("Canonical metric request plan counts:")
    print(f"  total DOM-discovered nodes:              {counts.total_dom_discovered_nodes}")
    print(f"  valid identity nodes:                     {valid_leaf_count}")
    print(f"  malformed leaves (blank identity):        {counts.malformed_leaf_count}")
    print(f"  requestable menu2-level metrics:          {counts.requestable_menu2_leaf_count}")
    print(f"  requestable menu3-level metrics:          {counts.requestable_menu3_leaf_count}")
    print(f"  navigation/container nodes:                {counts.navigation_container_count}")
    print(f"  exact duplicate DOM entries:               {counts.exact_duplicate_count}")
    print(f"  CANONICAL requestable metric count:        {counts.canonical_requestable_metric_count}")
    print(f"  menu3 collisions (canonical set):          {counts.menu3_collision_count}")
    print(f"  unique identity_key count:                 {counts.unique_identity_key_count}")
    print(f"  duplicate identity_key groups:              {counts.duplicate_identity_key_group_count}")
    print()

    print("Counts by menu1 family:")
    print(f"  {'family':<10} {'total':>6} {'malformed':>10} {'req_menu2':>10} {'req_menu3':>10} {'navigation':>11}")
    for family in _FAMILY_PRINT_ORDER:
        b = families[family]
        print(
            f"  {family:<10} {b['total']:>6} {b['malformed']:>10} {b['requestable_menu2']:>10} "
            f"{b['requestable_menu3']:>10} {b['navigation_container']:>11}"
        )
    print()

    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    plan_path = out_dir / "KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json"
    plan_path.write_text(
        build_canonical_plan_json(taxonomy, generated_at=generated_at, source_taxonomy=source_taxonomy_path),
        encoding="utf-8",
    )
    print(f"Wrote {plan_path}")

    malformed_path = out_dir / "KLPGA_MALFORMED_LEAF_REPORT.csv"
    # newline="" — the returned string already carries csv.writer's own
    # \r\n row terminators; without this, Path.write_text's default
    # universal-newline translation on Windows (os.linesep="\r\n")
    # doubles every \n it finds, turning \r\n into \r\r\n on disk — the
    # confirmed root cause of a real Windows pytest run reporting extra
    # blank lines in this exact file (docs/KLPGA_OFFICIAL_DATA_MAP.md's
    # Round 8 section).
    malformed_path.write_text(to_malformed_leaf_report_csv(malformed_rows), encoding="utf-8", newline="")
    print(f"Wrote {malformed_path} ({len(malformed_rows)} rows)")

    if counts.duplicate_identity_key_group_count:
        collision_rows = build_identity_key_collision_report(taxonomy)
        collision_path = out_dir / "KLPGA_IDENTITY_KEY_COLLISION_REPORT.csv"
        # newline="" — same Windows CSV-corruption fix as the other
        # CSV writes above (docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 8
        # section).
        collision_path.write_text(to_identity_key_collision_report_csv(collision_rows), encoding="utf-8", newline="")
        print(
            f"Wrote {collision_path} ({len(collision_rows)} rows across "
            f"{counts.duplicate_identity_key_group_count} duplicate identity_key groups) — "
            "review before treating unique_identity_key_count as the real B2 request count."
        )
    print()

    print(
        "This is a request PLAN only — no requests were made. Phase B2 "
        "(firing all canonical requests) remains a separate, not-yet-"
        "authorized step."
    )

    violations = check_sanity_invariants(counts)
    if violations:
        print()
        print("SANITY CHECK FAILED — this canonical plan is NOT presented as trustworthy:")
        for v in violations:
            print(f"  - {v}")
        print()
        print(
            f"See {malformed_path.name} for the {len(malformed_rows)} rejected leaves, grouped by "
            "rejection_reason, to investigate before trusting this plan's counts."
        )
        return EXIT_SANITY_CHECK_FAILED

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
