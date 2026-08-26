"""Round 10 continued — bounded, missing-evidence-ONLY request plan
for the identity_key collision audit's `UNRESOLVED_INSUFFICIENT_
EVIDENCE` groups (docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 10 section).

**DRY RUN ONLY this round** — makes ZERO HTTP requests, no matter
what. The live-fire step (reusing `PoliteHttpClient`, its disk cache,
`klpga.discovery.record_fetch.fetch_and_analyze`, the `raw_samples/`
naming convention, and the 401/403/429 hard-stop / consecutive-
failure circuit breaker already proven in `scripts/29`) is a
SEPARATE, NOT-YET-IMPLEMENTED step, deliberately deferred until this
dry-run plan itself has been reviewed. `--dry-run` is required;
omitting it does nothing but print an explanation and exit non-zero.

Scope: ONLY the identity_key groups
`klpga.discovery.identity_key_audit.audit_identity_key_collisions`
classifies as `UNRESOLVED_INSUFFICIENT_EVIDENCE` right now — derived
fresh from the audit every run, never hardcoded, never assumed.
Excludes every `PARTIAL_MATCH_NEEDS_REVIEW`/`D_UNRESOLVED`/already-
resolved (`C_MULTI_METRIC_ONE_REQUEST_CONFIRMED`/`B_CONTAINER_CHILD`/
`EMPTY_SHARED_RESPONSE`) group by construction — this script never
even looks at their evidence. One row per distinct `request_identity_
key`, exactly matching Phase B2's own definition of "one live
request" (see `identity_key_audit.derive_request_identity_key` and
`record_fetch.request_form` — both derive strictly from `menu1`/
`menu2`/`menu3`, nothing else).

Usage (fully offline — reads only local files already on disk):
    python scripts\\32_bounded_missing_evidence_request_plan.py \\
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json \\
        --season 2025 \\
        --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.canonical_plan import build_canonical_plan  # noqa: E402
from klpga.discovery.identity_key_audit import (  # noqa: E402
    CATEGORY_INSUFFICIENT_EVIDENCE,
    audit_identity_key_collisions,
)
from klpga.discovery.record_fetch import request_form, sanitize_identity_key_for_filename  # noqa: E402
from klpga.discovery.sampler import _canonical_entry_to_leaf_dict, _leaf_from_dict  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_TAXONOMY_LOAD_FAILED = 5
EXIT_DRY_RUN_REQUIRED = 2


def build_missing_evidence_request_plan(
    taxonomy: dict, *, season: str, raw_samples_dir: Path
) -> list[dict]:
    """Returns one row per `UNRESOLVED_INSUFFICIENT_EVIDENCE`
    `request_identity_key`, sorted for determinism. Every field is
    derived from evidence/logic that already exists elsewhere in this
    project (`build_canonical_plan`, `audit_identity_key_collisions`,
    `request_form`, `sanitize_identity_key_for_filename`) — nothing
    new is invented here."""
    counts, plan = build_canonical_plan(taxonomy)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    missing = [a for a in audits if a.category == CATEGORY_INSUFFICIENT_EVIDENCE]
    missing_keys = sorted(a.request_identity_key for a in missing)

    by_key: dict[str, dict] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], entry)

    rows: list[dict] = []
    for key in missing_keys:
        entry = by_key.get(key)
        if entry is None:
            # Should not happen — every audited identity_key comes
            # directly from this same canonical plan — but never
            # silently skip a real inconsistency.
            rows.append(
                {
                    "identity_key": key,
                    "menu1": None,
                    "menu2": None,
                    "menu3": None,
                    "season": season,
                    "expected_raw_sample_path": None,
                    "raw_sample_exists": None,
                    "warning": "No matching canonical plan entry found for this identity_key.",
                }
            )
            continue
        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        form = request_form(leaf, season)
        raw_path = raw_samples_dir / f"{sanitize_identity_key_for_filename(key)}__{season}.html"
        rows.append(
            {
                "identity_key": key,
                "menu1": form.get("menu1"),
                "menu2": form.get("menu2"),
                "menu3": form.get("menu3"),
                "season": form.get("season"),
                "expected_raw_sample_path": str(raw_path),
                "raw_sample_exists": raw_path.exists(),
                "warning": None,
            }
        )
    return rows


def run(taxonomy: dict, season: str, raw_samples_dir: Path, *, dry_run: bool) -> int:
    if not dry_run:
        print(
            "STOP: live-fire mode is not implemented in this script yet — this round is "
            "DRY RUN ONLY, by explicit instruction. Re-run with --dry-run."
        )
        return EXIT_DRY_RUN_REQUIRED

    counts, plan = build_canonical_plan(taxonomy)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    rows = build_missing_evidence_request_plan(taxonomy, season=season, raw_samples_dir=raw_samples_dir)
    excluded = [a for a in audits if a.category != CATEGORY_INSUFFICIENT_EVIDENCE]

    print("Bounded missing-evidence-only request plan (DRY RUN — zero HTTP requests)")
    print(f"season: {season}")
    print(f"total canonical entries: {counts.canonical_requestable_metric_count}")
    print(f"total colliding identity_key groups audited: {len(audits)}")
    print(
        f"excluded (existing-evidence / already-classified) groups NOT in this plan: "
        f"{len(excluded)}"
    )
    print()
    print(f"exact request count: {len(rows)}")
    print()

    for row in rows:
        print(f"identity_key: {row['identity_key']}")
        print(f"  menu1: {row['menu1']}")
        print(f"  menu2: {row['menu2']}")
        print(f"  menu3: {row['menu3']}")
        print(f"  season: {row['season']}")
        print(f"  expected_raw_sample_path: {row['expected_raw_sample_path']}")
        print(f"  raw_sample_exists: {row['raw_sample_exists']}")
        if row["raw_sample_exists"]:
            print(
                "  WARNING: a raw sample now exists at this path but the audit still classified "
                "this identity as INSUFFICIENT_EVIDENCE — investigate before treating this plan "
                "as accurate (possible timing/consistency issue between the audit and this script)."
            )
        if row["warning"]:
            print(f"  WARNING: {row['warning']}")
        print()

    print(
        "Zero HTTP requests made. Phase B2 not authorized. Live-fire mode is not implemented "
        "in this script this round. This plan excludes every existing-evidence group "
        "(PARTIAL_MATCH_NEEDS_REVIEW / D_UNRESOLVED / already-resolved)."
    )
    return EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--season", required=True, help="Season value the raw samples were/would be fetched for")
    parser.add_argument(
        "--raw-samples-dir",
        default=str(ROOT / "docs" / "discovery" / "raw_samples"),
        help="Directory of already-saved raw responses (scripts/27's/29's raw_samples/ convention).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required this round — prints the plan, makes zero HTTP requests.",
    )
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    return run(taxonomy, args.season, Path(args.raw_samples_dir), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
