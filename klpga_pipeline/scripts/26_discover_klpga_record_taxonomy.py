"""Phase A — KLPGA official record taxonomy discovery. Read-only,
zero-to-one HTTP request, no DB writes, no Prediction/model/archive
access.

Fetches ONE page (the landing page whose DOM is expected to carry
data-menu1/data-menu2/data-menu3 attributes — see
klpga.config.RECORD_TAXONOMY_SOURCE_URL's docstring for why this
script requires --source-url explicitly rather than guessing it),
inspects it for the full three-level menu taxonomy, and writes:

  docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.json
  docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.csv
  docs/discovery/KLPGA_METRIC_COLLISION_REPORT.md

Then STOPS. This script deliberately does NOT proceed to fetch
`/load/record/loadLocationRecord` for any discovered menu3 — that is
Phase B (schema validation), a separately authorized, separately
invoked step (see docs/KLPGA_OFFICIAL_DATA_MAP.md).

If the discovered DOM is only partially static (some menu1 categories
have zero resolved menu3 leaves), this script reports exactly which
categories are incomplete and STOPS without attempting any further
request — per instruction, no second/lazy-load endpoint is invented.

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts/26_discover_klpga_record_taxonomy.py \\
        --source-url "https://klpga.co.kr/<the real record/거리기록 page URL, copied from your own browser>"
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.collision_report import build_collision_report, render_collision_report_markdown  # noqa: E402
from klpga.discovery.menu_taxonomy import DomInspectionResult, inspect_menu_dom  # noqa: E402
from klpga.discovery.taxonomy_report import compute_counts, to_taxonomy_csv, to_taxonomy_json  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_INCOMPLETE_NEEDS_INVESTIGATION = 3
EXIT_FETCH_FAILED = 4


def discover_taxonomy(client: PoliteHttpClient, source_url: str) -> DomInspectionResult:
    """Fetches source_url once and inspects it. Factored out of
    main() so it can be exercised in tests against a FakeClient,
    matching this project's existing script-testing pattern (see
    scripts/13_discover_entry_list.py / scripts/14_inspect_entry_list.py)."""
    html = client.get_text(source_url)
    return inspect_menu_dom(html)


def run(client: PoliteHttpClient, source_url: str, out_dir: Path) -> int:
    print(f"Fetching menu-taxonomy source page:\n  {source_url}\n")
    try:
        dom_result = discover_taxonomy(client, source_url)
    except RateLimitBlockedError as exc:
        print(f"BLOCKED: {exc}")
        print("Not retrying — this is a site-side access restriction, not a transient failure.")
        return EXIT_FETCH_FAILED
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED to fetch/parse the source page: {exc}")
        return EXIT_FETCH_FAILED

    counts = compute_counts(dom_result)
    print("Taxonomy discovery counts:")
    print(f"  menu1 categories found:             {counts.menu1_count}")
    print(f"  menu2 nodes found:                  {counts.menu2_node_count}")
    print(f"  menu2-level metric leaves found:    {counts.menu2_level_leaf_count}")
    print(f"  menu3-level metric leaves found:    {counts.menu3_level_leaf_count}  (OLD-style 'menu3 combinations')")
    print(f"  total metric leaves found:          {counts.total_leaf_count}  (NEW — menu2-level + menu3-level)")
    print(f"  unique menu3 codes:                 {counts.unique_menu3_count}")
    print(f"  menu3 collisions:                   {counts.collision_count}")
    print(f"  unresolved menu1 categories:        {counts.incomplete_menu1_count}")
    print()

    out_dir.mkdir(parents=True, exist_ok=True)
    discovered_at = datetime.now(timezone.utc).isoformat()

    json_path = out_dir / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
    csv_path = out_dir / "KLPGA_RECORD_TAXONOMY_DISCOVERED.csv"
    collision_path = out_dir / "KLPGA_METRIC_COLLISION_REPORT.md"

    json_path.write_text(
        to_taxonomy_json(dom_result, source_url=source_url, discovered_at=discovered_at),
        encoding="utf-8",
    )
    # newline="" — the returned string already carries csv.writer's own
    # \r\n row terminators; without this, Path.write_text's default
    # universal-newline translation on Windows (os.linesep="\r\n")
    # doubles every \n it finds, turning \r\n into \r\r\n on disk (see
    # docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 8 section — this is the
    # exact confirmed root cause of a real Windows pytest run reporting
    # extra blank lines in a written CSV).
    csv_path.write_text(to_taxonomy_csv(dom_result), encoding="utf-8", newline="")

    collision_report = build_collision_report(dom_result)
    collision_path.write_text(render_collision_report_markdown(collision_report), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {collision_path}")

    if dom_result.incomplete_menu1_categories:
        print()
        print("INCOMPLETE — the following menu1 categories were found in the DOM")
        print("but had ZERO resolved leaves at EITHER level (menu2 or menu3).")
        print("A category is NOT flagged here merely for lacking menu3 leaves —")
        print("a menu2-level leaf (e.g. the confirmed Sg/Total case) counts as")
        print("fully resolved. This means the categories below need either a")
        print("lazily-loaded request this project has not confirmed, or this")
        print("parser's DOM-shape assumptions don't match their markup. NOT")
        print("attempting any further request — per instruction, no second")
        print("endpoint is guessed:")
        for c in dom_result.incomplete_menu1_categories:
            print(f"  - menu1={c.menu1!r} ({c.menu1_label!r})")
        print()
        print("Next step: inspect one of these categories directly in DevTools")
        print("and report back what request (if any) fires when you click it.")
        return EXIT_INCOMPLETE_NEEDS_INVESTIGATION

    print()
    print("COMPLETE — every discovered menu1 category has at least one resolved")
    print("leaf, at menu2 or menu3 level. Phase A taxonomy discovery finished")
    print("with zero requests beyond the single source-page fetch above.")
    return EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--source-url",
        required=True,
        help=(
            "The exact KLPGA record/거리기록 page URL — copy this from your own "
            "browser's address bar, the page where you clicked the menu tabs "
            "that fired getRecord(menu1, menu2, menu3). This script does not "
            "guess this URL."
        ),
    )
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "discovery"))
    args = parser.parse_args()

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    return run(client, args.source_url, Path(args.out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
