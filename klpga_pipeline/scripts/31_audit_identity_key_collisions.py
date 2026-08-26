"""Round 10 continued — offline audit of every canonical-plan
`identity_key` collision group (docs/KLPGA_OFFICIAL_DATA_MAP.md's
Round 10 section). NEVER fires a live HTTP request: classifies each
colliding group using ONLY an already-saved raw response, if one
exists under `--raw-samples-dir` (the same directory scripts/27 and
scripts/29 already save to, using the identical naming convention).
A group with no saved evidence is reported as insufficient-evidence,
never guessed, and excluded from the B2_REQUEST_COUNT gate.

Usage (fully offline — reads only local files already on disk):
    python scripts\\31_audit_identity_key_collisions.py \\
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json \\
        --season 2025

Gate rule: if every colliding group classifies as
C_MULTI_METRIC_ONE_REQUEST_CONFIRMED, B_CONTAINER_CHILD, or
EMPTY_SHARED_RESPONSE (i.e. zero D_UNRESOLVED /
PARTIAL_MATCH_NEEDS_REVIEW / INSUFFICIENT_EVIDENCE groups remain),
this script declares B2_REQUEST_COUNT = the canonical plan's own
unique_identity_key_count and exits 0. Otherwise it lists exactly
which groups are still unresolved and exits non-zero — this script
does NOT authorize or execute Phase B2 either way.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.canonical_plan import build_canonical_plan  # noqa: E402
from klpga.discovery.identity_key_audit import (  # noqa: E402
    CATEGORY_CONTAINER_CHILD,
    CATEGORY_EMPTY_SHARED_RESPONSE,
    CATEGORY_EXACT_DUPLICATE,
    CATEGORY_INSUFFICIENT_EVIDENCE,
    CATEGORY_MULTI_METRIC_CONFIRMED,
    CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW,
    CATEGORY_UNRESOLVED,
    audit_identity_key_collisions,
)

ROOT = Path(__file__).resolve().parents[1]

EXIT_GATE_CLEAN = 0
EXIT_GATE_NOT_CLEAN = 1
EXIT_TAXONOMY_LOAD_FAILED = 5

_CATEGORY_PRINT_ORDER = [
    CATEGORY_MULTI_METRIC_CONFIRMED,
    CATEGORY_CONTAINER_CHILD,
    CATEGORY_EMPTY_SHARED_RESPONSE,
    CATEGORY_EXACT_DUPLICATE,
    CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW,
    CATEGORY_UNRESOLVED,
    CATEGORY_INSUFFICIENT_EVIDENCE,
]

_UNRESOLVED_CATEGORIES = {
    CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW,
    CATEGORY_UNRESOLVED,
    CATEGORY_INSUFFICIENT_EVIDENCE,
}


def run(taxonomy: dict, season: str, raw_samples_dir: Path) -> int:
    counts, _plan = build_canonical_plan(taxonomy)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)

    print(f"canonical taxonomy entry count:  {counts.canonical_requestable_metric_count}")
    print(f"unique request_identity_key count: {counts.unique_identity_key_count}")
    print(f"duplicate identity_key groups:    {counts.duplicate_identity_key_group_count}")
    print(f"colliding groups audited:        {len(audits)}")
    print()

    category_counts = {c: 0 for c in _CATEGORY_PRINT_ORDER}
    for a in audits:
        category_counts[a.category] = category_counts.get(a.category, 0) + 1

    print("Collision-group classification counts:")
    for category in _CATEGORY_PRINT_ORDER:
        print(f"  {category}: {category_counts[category]}")
    print()

    print("Per-group detail (request_identity_key -> mapped canonical labels):")
    for a in audits:
        print(f"=== {a.request_identity_key} [{a.category}] ===")
        print(f"  labels ({len(a.labels)}): {a.labels}")
        if a.response_column_labels:
            print(f"  response column labels: {a.response_column_labels}")
        if a.matched_labels:
            print(f"  matched: {a.matched_labels}")
        if a.unmatched_labels:
            print(f"  UNMATCHED: {a.unmatched_labels}")
        if a.notes:
            print(f"  note: {a.notes}")
        print()

    unresolved = [a for a in audits if a.category in _UNRESOLVED_CATEGORIES]

    print("=== GATE RULE ===")
    if not unresolved:
        print(
            f"D=0, zero unresolved/partial/insufficient-evidence groups across all "
            f"{len(audits)} colliding groups."
        )
        print(f"B2_REQUEST_COUNT = {counts.unique_identity_key_count}")
        print(
            "This script does NOT authorize or execute Phase B2 — it only clears the "
            "canonical-plan-layer request-identity gate."
        )
        return EXIT_GATE_CLEAN

    print(f"NOT CLEAN — {len(unresolved)} group(s) still unresolved:")
    for a in unresolved:
        print(f"  {a.request_identity_key} [{a.category}]: {a.notes}")
    print("B2_REQUEST_COUNT not declared. Phase B2 not authorized.")
    return EXIT_GATE_NOT_CLEAN


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--season", required=True, help="Season value the raw samples were fetched for")
    parser.add_argument(
        "--raw-samples-dir",
        default=str(ROOT / "docs" / "discovery" / "raw_samples"),
        help="Directory of already-saved raw responses (scripts/27's/29's raw_samples/ convention).",
    )
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    return run(taxonomy, args.season, Path(args.raw_samples_dir))


if __name__ == "__main__":
    raise SystemExit(main())
