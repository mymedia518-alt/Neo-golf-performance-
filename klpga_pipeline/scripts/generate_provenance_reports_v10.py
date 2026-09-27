"""MISSION V10 (2026-09-25), playerCode=10097 only: generates the three
markdown reports this mission requires (data provenance report,
missing-data report, derived-value dependency graph) directly from the
live provenance maps in build_10097_player_history.py and
build_10097_player_intelligence_report.py -- never hand-written, so
they can never silently drift out of sync with the code they describe.
Re-run this script after any change to either builder's _provenance_map().
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DOCS_DIR = ROOT / "docs"

REPORTS = [
    ("Player History", "build_10097_player_history.py", "player_history_10097"),
    ("Player Intelligence Report", "build_10097_player_intelligence_report.py", "player_intelligence_10097"),
]


def _load_build(script_name: str):
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), ROOT / "scripts" / script_name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build()


def _group_by_top_level(provenance: dict) -> dict:
    groups: dict = {}
    for path, entry in provenance.items():
        top = path.split(".")[0].split("[")[0]
        groups.setdefault(top, []).append((path, entry))
    return groups


def _provenance_report() -> str:
    lines = [
        "# NEO Data Provenance Report V1",
        "",
        "**Mission V10 (2026-09-25), playerCode=10097 only.** \"Every "
        "number shown on NEO can always answer: 'Where did this come "
        "from?'\" Generated directly from the live `_provenance_map()` "
        "in each builder (`scripts/generate_provenance_reports_v10.py`)"
        " -- never hand-maintained, so this table cannot drift out of "
        "sync with the code. Re-run that script after any provenance "
        "map change.",
        "",
        "## The five labels",
        "",
        "| Label | Meaning |",
        "|---|---|",
        "| **MEASURED** | A real, directly-collected raw data point. No arithmetic was applied to produce this exact value. |",
        "| **DERIVED** | Computed via a deterministic formula/aggregation from one or more MEASURED (or other DERIVED) values. |",
        "| **IMPUTED** | Estimated, interpolated, or defaulted to stand in for missing data. |",
        "| **NOT_COLLECTED** | The pipeline is capable of having this data, but NEO has not ingested it for this case. |",
        "| **NOT_AVAILABLE** | Not obtainable at all in this pipeline's current design/environment. |",
        "",
        "## Methodology",
        "",
        "- Classification is at the **JSON-path-schema level** (e.g. "
        "`tournament_history[].sg_total` covers all ~96 rows with one "
        "entry), not per literal value instance -- the one documented "
        "exception is `questions[].monitoring_protocol.current_reading` "
        "in the Player Intelligence report, where a real IMPUTED "
        "instance (id=q_win_blueprint) is disclosed in that entry's own "
        "reason text rather than given a separate schema path (see the "
        "Player Intelligence section below).",
        "- Pure build/pipeline metadata (`schema_version`, `generated_at`, "
        "`scope_note`, `source_document`, and Player Intelligence's own "
        "methodology-description strings) is excluded: none of the 5 "
        "labels honestly describes a build timestamp or a schema tag.",
        "- Two real governance gaps this audit surfaced -- kept "
        "**MEASURED** (a factual assertion, not a formula or a data "
        "gap) rather than invented as an unlisted 6th label, but named "
        "explicitly here and in every affected entry's own reason text:",
        "  - `status.data_completeness` / `status.derived_metrics` "
        "(Player History) are fixed literal strings (`\"PARTIAL\"`/`\"PASS\"`) "
        "with no per-run check behind them -- they never vary "
        "regardless of the actual data state.",
        "  - `coverage_matrix.rows` (Player History) is an entirely "
        "hand-authored table; its MEASURED/DERIVED/NOT_COLLECTED/BLOCKED "
        "cell values are asserted by whoever last edited the source "
        "file, never verified against a live presence-check of what "
        "this specific build run actually has.",
        "",
    ]

    for title, script, _ in REPORTS:
        doc = _load_build(script)
        provenance = doc["provenance"]
        lines.append(f"## {title} ({script})")
        lines.append("")
        lines.append(f"{len(provenance)} classified fields.")
        lines.append("")
        counts = {}
        for e in provenance.values():
            counts[e["label"]] = counts.get(e["label"], 0) + 1
        lines.append("| Label | Count |")
        lines.append("|---|---|")
        for label in ("MEASURED", "DERIVED", "IMPUTED", "NOT_COLLECTED", "NOT_AVAILABLE"):
            lines.append(f"| {label} | {counts.get(label, 0)} |")
        lines.append("")
        groups = _group_by_top_level(provenance)
        for top in sorted(groups):
            lines.append(f"### `{top}`")
            lines.append("")
            lines.append("| Path | Label | Reason |")
            lines.append("|---|---|---|")
            for path, entry in sorted(groups[top]):
                reason = entry["reason"].replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{path}` | {entry['label']} | {reason} |")
            lines.append("")

    return "\n".join(lines) + "\n"


def _missing_data_report() -> str:
    lines = [
        "# NEO Missing Data Report V1",
        "",
        "**Mission V10 (2026-09-25), playerCode=10097 only.** Every "
        "field currently classified NOT_COLLECTED or NOT_AVAILABLE "
        "across Player History and Player Intelligence, generated "
        "directly from the live provenance maps -- and the pre-existing "
        "free-text `not_available` disclosure list Player History has "
        "carried since the original RED TEAM mission, for cross-reference.",
        "",
    ]

    for title, script, _ in REPORTS:
        doc = _load_build(script)
        provenance = doc["provenance"]
        gaps = {p: e for p, e in provenance.items() if e["label"] in ("NOT_COLLECTED", "NOT_AVAILABLE")}
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"{len(gaps)} of {len(provenance)} classified fields ({len(gaps) / len(provenance):.1%}) are a disclosed gap, not a real value.")
        lines.append("")
        lines.append("| Path | Label | Reason |")
        lines.append("|---|---|---|")
        for path, entry in sorted(gaps.items()):
            reason = entry["reason"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{path}` | {entry['label']} | {reason} |")
        lines.append("")

    doc = _load_build("build_10097_player_history.py")
    unverified = {p: e for p, e in doc["provenance"].items() if "not computed from a live" in e["reason"]}
    lines.append("## Known governance gaps (not missing data -- unverified assertions)")
    lines.append("")
    lines.append(
        "These fields are classified MEASURED (a real factual assertion "
        "exists), but nothing in the pipeline currently re-verifies "
        "them against this specific run's actual data -- they are "
        "hand-authored constants that could silently drift from "
        "reality. Not a data gap, but a real governance gap this audit "
        "surfaced and did not fix (fixing it would mean writing a live "
        "presence-check, out of scope for an audit mission)."
    )
    lines.append("")
    lines.append(f"{len(unverified)} fields, {len({p.split('.')[0] for p in unverified}) } distinct top-level groups (dominated by `coverage_matrix.rows`'s 76 hand-authored cells).")
    lines.append("")
    sample_paths = sorted(p for p in unverified if not p.startswith("coverage_matrix.rows."))
    lines.append("Non-`coverage_matrix.rows` examples:")
    lines.append("")
    for p in sample_paths:
        lines.append(f"- `{p}`")
    lines.append("")
    lines.append("Plus all 76 `coverage_matrix.rows.<metric>.<season>` cells (19 metrics x 4 seasons) -- see the full provenance report for the complete list.")
    lines.append("")

    lines.append("## Player History's existing free-text disclosure list (`not_available`)")
    lines.append("")
    lines.append("Carried since the original RED TEAM tournament-ordering mission, predating this audit -- listed here for cross-reference since it names the same real gaps in prose rather than as JSON paths.")
    lines.append("")
    for item in doc["not_available"]:
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines) + "\n"


def _dependency_graph_report() -> str:
    from klpga.data_provenance import dependency_graph

    lines = [
        "# NEO Derived-Value Dependency Graph V1",
        "",
        "**Mission V10 (2026-09-25), playerCode=10097 only.** For every "
        "DERIVED field whose provenance entry declares real `depends_on` "
        "paths, this is the adjacency list of what it was computed "
        "from -- a plain data structure (a graph), not a rendered "
        "chart/diagram (this mission explicitly forbids building UI or "
        "charts). Only DERIVED entries that named their real inputs are "
        "listed; most DERIVED entries in this codebase are simple "
        "aggregations (a mean, a count, an argmax) over raw rows rather "
        "than over another already-classified JSON field, so they have "
        "no `depends_on` edge to show here -- their reason text still "
        "states the formula in prose (see the provenance report).",
        "",
    ]

    for title, script, _ in REPORTS:
        doc = _load_build(script)
        graph = dependency_graph(doc["provenance"])
        lines.append(f"## {title}")
        lines.append("")
        if not graph:
            lines.append("No DERIVED entry in this report declares a `depends_on` edge onto another classified field.")
            lines.append("")
            continue
        for path in sorted(graph):
            deps = graph[path]
            lines.append(f"- `{path}`")
            for d in deps:
                lines.append(f"  - depends on `{d}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "NEO_DATA_PROVENANCE_REPORT_10097_V1.md").write_text(_provenance_report(), encoding="utf-8")
    (DOCS_DIR / "NEO_MISSING_DATA_REPORT_10097_V1.md").write_text(_missing_data_report(), encoding="utf-8")
    (DOCS_DIR / "NEO_DERIVED_VALUE_DEPENDENCY_GRAPH_10097_V1.md").write_text(_dependency_graph_report(), encoding="utf-8")
    print(f"wrote {DOCS_DIR / 'NEO_DATA_PROVENANCE_REPORT_10097_V1.md'}")
    print(f"wrote {DOCS_DIR / 'NEO_MISSING_DATA_REPORT_10097_V1.md'}")
    print(f"wrote {DOCS_DIR / 'NEO_DERIVED_VALUE_DEPENDENCY_GRAPH_10097_V1.md'}")


if __name__ == "__main__":
    main()
