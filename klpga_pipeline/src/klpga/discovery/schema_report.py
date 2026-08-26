"""Phase B1 output artifacts: KLPGA_RESPONSE_SCHEMA_SAMPLES.json/.csv,
KLPGA_RESPONSE_SCHEMA_REPORT.md, KLPGA_RAW_FIELD_INVENTORY.md,
NEO_RAW_INPUT_CANDIDATES.md. Pure formatting over already-computed
sample records — no network access.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Optional

from klpga.discovery.response_parser import ParsedRecordResponse
from klpga.discovery.response_schema import MetricSchemaAnalysis
from klpga.discovery.sampler import SampledLeaf


def _summarize_player_code_extraction(parsed: ParsedRecordResponse) -> str:
    methods = {row.player_code_source for row in parsed.rows if row.player_code_source}
    if not methods:
        return "none"
    if len(methods) > 1:
        return "mixed"
    return next(iter(methods))


def build_sample_record(
    leaf: SampledLeaf,
    *,
    season: str,
    http_status: Optional[int],
    parsed: ParsedRecordResponse,
    analysis: MetricSchemaAnalysis,
    historical_availability: str = "NOT_TESTED",
) -> dict:
    """Assembles one flat, JSON/CSV-ready record. Status fields use
    the CONFIRMED/OBSERVED-IN-SAMPLE/INFERRED/UNKNOWN vocabulary
    wherever the underlying value is a judgment call rather than a
    directly-read fact."""
    metric_label = leaf.menu3_label if leaf.leaf_level == "menu3" else leaf.menu2_label

    return {
        "identity_key": leaf.source_metric_key,
        "canonical_identity": list(leaf.identity),
        "menu1": leaf.menu1,
        "menu2": leaf.menu2,
        "menu3": leaf.menu3,
        "leaf_level": leaf.leaf_level,
        "metric_label": metric_label,
        "season": season,
        "http_status": http_status,
        "parse_status": parsed.parse_status,
        "player_row_count": len(parsed.rows),
        "column_labels": [c.label for c in parsed.column_semantics if c.label],
        "column_label_source": "CONFIRMED" if parsed.metadata.found else "OBSERVED-IN-SAMPLE (table header)",
        "schema_fingerprint": analysis.schema_fingerprint,
        "raw_pair_status": analysis.raw_pair.status,
        "raw_pair_numerator_field": analysis.raw_pair.numerator_field,
        "raw_pair_denominator_field": analysis.raw_pair.denominator_field,
        "rate_validation": asdict(analysis.raw_pair.validation) if analysis.raw_pair.validation else None,
        "sample_size_fields": [asdict(f) for f in analysis.sample_size_fields],
        "rtp_status": analysis.rtp_status,
        "rtp_example_value": analysis.rtp_example_value,
        "player_code_extraction": _summarize_player_code_extraction(parsed),
        "data_quality_flags": asdict(analysis.data_quality),
        "data_quality_any_flagged": analysis.data_quality.any_flagged,
        "historical_availability": historical_availability,
        "pit_status": analysis.pit_status,
    }


def write_samples_json(records: list[dict], *, discovered_at: str, source_taxonomy: str) -> str:
    payload = {
        "discovered_at": discovered_at,
        "source_taxonomy": source_taxonomy,
        "phase": "B1 — representative response-schema discovery",
        "sample_count": len(records),
        "samples": records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


_CSV_FIELDS = [
    "identity_key",
    "menu1",
    "menu2",
    "menu3",
    "leaf_level",
    "metric_label",
    "season",
    "http_status",
    "parse_status",
    "player_row_count",
    "schema_fingerprint",
    "raw_pair_status",
    "rtp_status",
    "player_code_extraction",
    "data_quality_any_flagged",
    "historical_availability",
    "pit_status",
]


def write_samples_csv(records: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for r in records:
        writer.writerow({k: r.get(k, "") for k in _CSV_FIELDS})
    return buf.getvalue()


def cluster_by_schema_family(records: list[dict]) -> dict[str, list[dict]]:
    families: dict[str, list[dict]] = {}
    for r in records:
        families.setdefault(r["schema_fingerprint"], []).append(r)
    return families


def render_schema_report_markdown(
    records: list[dict], *, request_count: int, historical_probe_records: Optional[list[dict]] = None
) -> str:
    lines = ["# KLPGA Response Schema Report — Phase B1", ""]
    lines.append(
        f"{len(records)} metrics sampled, {request_count} live requests made this run. "
        "Sample-based evidence only — nothing here is generalized to the "
        "full discovered taxonomy without saying so explicitly."
    )
    lines.append("")

    families = cluster_by_schema_family(records)
    lines.append(f"## Schema families discovered: {len(families)}")
    lines.append("")
    lines.append("| Schema family | # sampled metrics | Example metrics | Raw counts? | Sample size? | RTP? |")
    lines.append("|---|---|---|---|---|---|")
    for fingerprint, members in sorted(families.items(), key=lambda kv: -len(kv[1])):
        examples = ", ".join(m["metric_label"] or m["identity_key"] for m in members[:3])
        has_raw_pair = any(m["raw_pair_status"] == "CONFIRMED_RAW_PAIR" for m in members)
        has_rtp = any(m["rtp_status"] == "RTP_PRESENT" for m in members)
        lines.append(
            f"| `{fingerprint}` | {len(members)} | {examples} | "
            f"{'yes' if has_raw_pair else 'no'} | see samples file | {'yes' if has_rtp else 'no'} |"
        )
    lines.append("")

    failed = [r for r in records if r["parse_status"] in ("FAILED", "AMBIGUOUS", "EMPTY")]
    if failed:
        lines.append("## Failed / ambiguous / empty metrics (classified UNKNOWN, not discarded)")
        lines.append("")
        for r in failed:
            lines.append(f"- `{r['identity_key']}` ({r['metric_label']}) — {r['parse_status']}")
        lines.append("")

    flagged = [r for r in records if r["data_quality_any_flagged"]]
    lines.append("## Data-quality anomalies")
    lines.append("")
    if not flagged:
        lines.append("None found in this sample.")
    else:
        for r in flagged:
            lines.append(f"- `{r['identity_key']}`: {r['data_quality_flags']}")
    lines.append("")

    lines.append("## Historical-season probe")
    lines.append("")
    if not historical_probe_records:
        lines.append("Not run this session — no live access.")
    else:
        for r in historical_probe_records:
            lines.append(f"- `{r['identity_key']}`: {r['historical_availability']} (PIT status: {r['pit_status']})")
    lines.append("")
    lines.append(
        "**PIT status is `PIT_UNVERIFIED` for every metric in this report, "
        "unconditionally** — historical season availability, even if "
        "confirmed above, does not by itself establish point-in-time "
        "safety. See docs/KLPGA_OFFICIAL_DATA_MAP.md's PIT analysis."
    )
    lines.append("")

    return "\n".join(lines)


def render_raw_field_inventory_markdown(records: list[dict]) -> str:
    lines = ["# KLPGA Raw Field Inventory — Phase B1", ""]
    lines.append(
        "Every field observed in the sample, classified "
        "CONFIRMED / OBSERVED-IN-SAMPLE / INFERRED / UNKNOWN. Column "
        "*labels* come from the response itself (CONFIRMED if an "
        "embedded metadata block backed them, OBSERVED-IN-SAMPLE if "
        "only the table header did); column *kind* classification "
        "(RATE/COUNT/ROUNDS/...) is always INFERRED from that label "
        "text, never promoted to CONFIRMED fact."
    )
    lines.append("")
    lines.append("| Metric | Fields observed | Label source | Raw pair | Sample-size fields | RTP |")
    lines.append("|---|---|---|---|---|---|")
    for r in records:
        fields = ", ".join(r["column_labels"]) or "—"
        sizes = ", ".join(f["sample_size_type"] for f in r["sample_size_fields"]) or "—"
        lines.append(
            f"| `{r['identity_key']}` | {fields} | {r['column_label_source']} | "
            f"{r['raw_pair_status']} | {sizes} | {r['rtp_status']} |"
        )
    lines.append("")
    return "\n".join(lines)


_DIMENSION_BY_MENU1 = {
    "Sg": "SCORING",
    "Tee": "POWER",
    "Approach": "APPROACH",
    "Putting": "PUTTING",
}
"""INFERRED default mapping only — a starting suggestion per family,
never a final Player DNA formula. Any menu1 not listed here (e.g. an
unconfirmed "Around Green"/"All" family) gets "UNKNOWN", not a guess."""


def render_neo_raw_input_candidates_markdown(records: list[dict]) -> str:
    lines = ["# NEO Raw Input Candidates — Phase B1 sample", ""]
    lines.append(
        "Raw inputs only — no Player DNA formula is defined here, per "
        "explicit instruction. `potential_neo_dimension` is a naming "
        "suggestion, not a computed feature."
    )
    lines.append("")
    lines.append(
        "| Identity | Label | Family | Raw value | Numerator | Denominator | "
        "Measured rounds | RTP | playerCode | Potential NEO dimension |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in records:
        has_numerator = "yes" if r["raw_pair_numerator_field"] else "no"
        has_denominator = "yes" if r["raw_pair_denominator_field"] else "no"
        has_rounds = "yes" if any(
            "라운드" in f["sample_size_type"] for f in r["sample_size_fields"]
        ) else "no"
        has_rtp = "yes" if r["rtp_status"] == "RTP_PRESENT" else "no"
        has_code = "yes" if r["player_code_extraction"] != "none" else "no"
        dimension = _DIMENSION_BY_MENU1.get(r["menu1"], "UNKNOWN")
        lines.append(
            f"| `{r['identity_key']}` | {r['metric_label']} | {r['menu1']} | "
            f"{'yes' if r['parse_status'] not in ('EMPTY', 'FAILED') else 'no'} | "
            f"{has_numerator} | {has_denominator} | {has_rounds} | {has_rtp} | {has_code} | {dimension} |"
        )
    lines.append("")
    return "\n".join(lines)
