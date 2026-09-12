"""Build the first real, immutable KLPGA Record Report Warehouse snapshot
from the official "총보기" (View All) capture, and report identity
coverage against the current W36 K-Ranking TOP120 / NEO-ranked / pending
cohorts. Read-only against the raw captures; writes only the new
content-addressed snapshot file. Never touches NEO Ranking, HOME, or
production docs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
RAW = CONTENT / "raw_sources"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.record_report_warehouse import (  # noqa: E402
    RecordReportSnapshotConflict,
    build_snapshot,
    join_identity_by_player_code,
    sha256_file,
    snapshot_to_dict,
    write_snapshot_immutable,
)
from klpga.website_v2.top120_validation import evaluate  # noqa: E402

CAPTURE_A = RAW / "KLPGA_RECORD_REPORT_2026_CAPTURE_A_10ROW.html"
CAPTURE_B = RAW / "KLPGA_RECORD_REPORT_2026_CAPTURE_B_EXPANDED.html"
EXPECTED_SHA_A = "198df55cf31b05a141deb83c5269fe40c46a5d20ad623093dc86ab647e0a9538"
EXPECTED_SHA_B = "31ee0f1096f7e552bb4fd235dc4c8533f694f265c4aaa445d44a327fbac05ae0"

SNAPSHOT_PATH = CONTENT / "KLPGA_RECORD_REPORT_WAREHOUSE_V1.json"


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def build() -> dict:
    sha_a = sha256_file(CAPTURE_A)
    sha_b = sha256_file(CAPTURE_B)
    if sha_a != EXPECTED_SHA_A:
        return {"action": "HARD_STOP", "reason": f"Capture A sha256 mismatch: {sha_a} != expected {EXPECTED_SHA_A}"}
    if sha_b != EXPECTED_SHA_B:
        return {"action": "HARD_STOP", "reason": f"Capture B sha256 mismatch: {sha_b} != expected {EXPECTED_SHA_B}"}

    html_b = CAPTURE_B.read_text(encoding="utf-8")
    snapshot = build_snapshot(
        html=html_b,
        source_sha256=sha_b,
        source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="UNKNOWN_BROWSER_CAPTURE_TIME",  # neither raw HTML embeds an actual capture
        effective_season=2026,                              # timestamp; upload mtime is a processing artifact,
        menu_mode="All",                                     # not source provenance -- never fabricated as if known.
        expanded_view=True,  # evidenced: #totalView carries style="display:none" in Capture B, matching the
                              # getRecord(menu1, "ALL") JS branch that hides it -- never inferred from row count alone.
    )

    wrote_new = write_snapshot_immutable(snapshot, SNAPSHOT_PATH)

    # Reconciliation against Capture A (the original 10-row evidence, immutable, untouched).
    html_a = CAPTURE_A.read_text(encoding="utf-8")
    from klpga.website_v2.record_report_warehouse import parse_record_report_html
    records_a = parse_record_report_html(html_a)
    by_code_b = {r["playerCode"]: r for r in snapshot.records}
    original_10_matched, original_10_missing, original_10_mismatched = [], [], []
    for ra in records_a:
        rb = by_code_b.get(ra["playerCode"])
        if rb is None:
            original_10_missing.append(ra["playerCode"])
            continue
        original_10_matched.append(ra["playerCode"])
        compare_keys = ("money", "average_score", "average_putts", "birdie_rate", "gir_rate", "par_save_rate", "par_break_rate", "recovery_rate")
        if any(ra[k] != rb[k] for k in compare_keys):
            original_10_mismatched.append(ra["playerCode"])

    # Identity join against the current W36 TOP120 cohort / NEO-ranked / pending.
    cohort_top120 = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    top120_out, summary = evaluate(cohort_top120, warehouse, config)

    top120_rows = [{"player_id": r["player_id"], "player_name": r["player_name"]} for r in top120_out]
    neo108_rows = [{"player_id": r["player_id"], "player_name": r["player_name"]} for r in top120_out if r["neo_validation_rank"]]
    pending12_rows = [{"player_id": r["player_id"], "player_name": r["player_name"]} for r in top120_out if not r["neo_validation_rank"]]

    join_top120 = join_identity_by_player_code(snapshot.records, top120_rows)
    join_neo108 = join_identity_by_player_code(snapshot.records, neo108_rows)
    join_pending12 = join_identity_by_player_code(snapshot.records, pending12_rows)

    top120_ids = {r["player_id"] for r in top120_rows}
    record_report_not_top120 = [
        {"playerCode": r["playerCode"], "player_name": r["player_name"]}
        for r in snapshot.records if r["playerCode"] not in top120_ids
    ]

    return {
        "action": "WAREHOUSE_BUILT",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_path": str(SNAPSHOT_PATH),
        "wrote_new_file": wrote_new,
        "source_sha256_A": sha_a,
        "source_sha256_B": sha_b,
        "normalized_sha256": snapshot.normalized_sha256,
        "source_rows": snapshot.source_rows,
        "unique_players": snapshot.unique_players,
        "population_completeness": snapshot.population_completeness,
        "original_10_matched": len(original_10_matched),
        "original_10_missing": original_10_missing,
        "original_10_mismatched": original_10_mismatched,
        "top120_summary": {"TOTAL": summary["cohort_count"], "NEO_RANKED": summary["neo_ranked"], "VALIDATION_PENDING": summary["validation_pending"]},
        "join_top120": {"matched": len(join_top120["matched"]), "unmatched": join_top120["unmatched"], "name_conflicts": join_top120["name_conflicts"]},
        "join_neo108": {"matched": len(join_neo108["matched"]), "unmatched": join_neo108["unmatched"], "name_conflicts": join_neo108["name_conflicts"]},
        "join_pending12": {"matched": len(join_pending12["matched"]), "unmatched": join_pending12["unmatched"], "name_conflicts": join_pending12["name_conflicts"]},
        "record_report_not_top120_count": len(record_report_not_top120),
        "record_report_not_top120": record_report_not_top120,
    }


if __name__ == "__main__":
    try:
        result = build()
    except RecordReportSnapshotConflict as exc:
        result = {"action": "HARD_STOP", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
