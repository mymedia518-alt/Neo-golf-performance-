"""KLPGA OFFICIAL TECHNICAL STATS -- playerCode=10097 (김민선7), season 2025 ONLY.

This closes a real completeness gap found during verification: Driving
Distance and Fairway (Driving) Accuracy were previously disclosed as
"not measured anywhere in this repository." That was true of every
warehouse this player's report reads from, but false of the repository
as a whole -- real, already-fetched KLPGA official response HTML for
these exact metrics (and GIR/Around-the-Green/Putting breakdowns) has
existed since 2026-08-26 at docs/discovery/raw_samples/, produced by a
prior live capture against the confirmed official endpoint

    POST https://klpga.co.kr/web/record/locationRecord
    (client-side AJAX: POST /load/record/loadLocationRecord)

for season=2025. It was never ingested into this player's report
because it predates the reconciliation/Player History work entirely
and lives outside the warehouse pipeline. This script closes that gap
for playerCode=10097 specifically, using the already-existing, already
line-tested parser (src/klpga/discovery/response_parser.py) -- no new
parsing logic, no guessed HTML structure.

Scope discipline:
- season=2025 ONLY. This is a single-season capture, exactly like the
  existing 2026 current_snapshot -- never extrapolated to any other
  season, never averaged with the 2026 snapshot (different season,
  different sample).
- Only files with a real, parsed player_code=="10097" row are used.
  Files where the parser could not resolve a header label (metadata
  not found) are skipped entirely rather than guessed.
- Every value keeps its real KLPGA-embedded label (extracted from the
  response's own `var record = "..."` client-side label assignments,
  the same mechanism response_parser.py's own docstring documents as
  the confirmed source of truth for this endpoint), its real
  numerator/denominator pair where the response provides one, and its
  measured-rounds sample size. Nothing here is a percentile, a
  z-score, or a derived statistic -- these are the raw official values
  as published.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.discovery.response_parser import parse_record_response  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402

PLAYER_ID = "10097"
PLAYER_NAME = "김민선7"
SEASON = 2025
RAW_SAMPLES_DIR = ROOT / "docs" / "discovery" / "raw_samples"
OUTPUT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "TECHNICAL_STATS_2025.json"

# filename stem -> (group label, real KLPGA menu path as captured in the filename)
# Real, observed group meaning (not guessed): Tee01/02 = Par4,5 combined tee
# shots, Tee03/04 = Par5, Tee05/06 = Par4 -- confirmed by the values
# themselves being internally consistent (Par5 avg distance > combined >
# Par4 avg distance; a real physical relationship, not an artifact).
_FILES = {
    "Tee__Tee01__010101__2025.html": "평균 티샷 거리 (Par4,5)",
    "Tee__Tee02__010109__2025.html": "페어웨이 안착률 (Par4,5)",
    "Tee__Tee03__010201__2025.html": "평균 티샷 거리 (Par5)",
    "Tee__Tee04__010209__2025.html": "페어웨이 안착률 (Par5)",
    "Tee__Tee05__010301__2025.html": "평균 티샷 거리 (Par4)",
    "Tee__Tee06__010309__2025.html": "페어웨이 안착률 (Par4)",
    "Approach__Approach01__020101__2025.html": "그린 적중률 (GIR)",
    "Approach__Approach07__020701__2025.html": "버디 이하 확률",
    "Approach__Approach11__020901__2025.html": "페어웨이 안착률 (세컨샷)",
    "Around__Around01__030101__2025.html": "샌드 세이브율",
    "Around__Around03__030301__2025.html": "스크램블링률",
    "Putt__Putt01__040101__2025.html": "1퍼트 성공률",
    "Putt__Putt02__040201__2025.html": "라운드당 평균 퍼트 수",
    "Putt__Putt07__040601__2025.html": "퍼팅 성공률",
}


def _real_labels(html: str) -> dict:
    return {m.group(1): m.group(2) for m in re.finditer(r'var\s+(record\d*)\s*=\s*"([^"]*)"', html) if m.group(2)}


def build() -> dict:
    metrics = []
    for filename, group_label in _FILES.items():
        path = RAW_SAMPLES_DIR / filename
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_record_response(html)
        row = next((r for r in parsed.rows if r.player_code == PLAYER_ID), None)
        if not row:
            continue
        labels = _real_labels(html)
        if "record" not in labels:
            continue
        rank = int(row.rank) if row.rank and row.rank.isdigit() else None
        value = row.values.get("record")
        rounds_label = next((v for k, v in labels.items() if v in ("측정 라운드", "측정 대회")), None)
        rounds_field = next((k for k, v in labels.items() if v in ("측정 라운드", "측정 대회")), None)
        metrics.append({
            "label": group_label,
            "value_label": labels.get("record"),
            "value": value,
            "rank": rank,
            "numerator_label": labels.get("record1"),
            "numerator": row.values.get("record1"),
            "denominator_label": labels.get("record2"),
            "denominator": row.values.get("record2"),
            "measured_rounds_label": rounds_label,
            "measured_rounds": row.values.get(rounds_field) if rounds_field else None,
            "source_file": f"docs/discovery/raw_samples/{filename}",
        })

    return {
        "schema_version": "technical_stats_2025_v1",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "season": SEASON,
        "source_endpoint": "POST https://klpga.co.kr/web/record/locationRecord (client AJAX: /load/record/loadLocationRecord)",
        "as_of_note": (
            f"KLPGA 공식 {SEASON}시즌 스냅샷 1건입니다 (2026-08-26 캡처). 다른 시즌으로 확장하지 않습니다. "
            "2026시즌 공식 스냅샷(현재 시즌 공식 스냅샷 섹션)과는 서로 다른 시즌의 서로 다른 실측치이며 합산하지 않습니다."
        ),
        "metrics": metrics,
    }


if __name__ == "__main__":
    result = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT_PATH}")
    print(f"metrics recovered: {len(result['metrics'])}")
    for m in result["metrics"]:
        print(f"  {m['label']}: {m['value']} {m['value_label']} (rank {m['rank']})")
