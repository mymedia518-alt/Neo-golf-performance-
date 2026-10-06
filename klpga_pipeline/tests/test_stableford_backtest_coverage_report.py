"""The committed coverage report JSON must match what the real snapshot
builder computes right now -- re-derived, not just asserted statically,
so the report can't silently drift from the code that produced it."""
from __future__ import annotations

import json
from pathlib import Path

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_backtest_snapshot import build_event_snapshot

REPORT_PATH = (
    Path(__file__).parent.parent / "content" / "website_v2" / "STABLEFORD_BACKTEST_DATA_COVERAGE_V1.json"
)
EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"


def test_coverage_report_matches_live_computation_for_all_three_events():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    for code in ["2023100002", "2024100009", "2025100001"]:
        html = (EVIDENCE_ROOT / f"stableford_source_probe_{code}" / f"scoreRecord_{code}.html").read_text(encoding="utf-8")
        field = set(extract_hole_outcomes(html)["1R"].keys())
        snap = build_event_snapshot(code, field)
        covered = sum(1 for p in snap.players.values() if p.prior_tournament_count > 0)

        event_report = report["events"][code]
        assert event_report["field_size"] == snap.field_size
        assert event_report["event_start_date"] == snap.event_start_date
        assert event_report["features"]["prior_sg_total_and_components"]["players_covered"] == covered


def test_every_birdie_eagle_bogey_feature_honestly_reports_zero_coverage():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    for code, event_report in report["events"].items():
        for key in ["birdie_rate", "eagle_rate", "par_rate", "bogey_rate", "double_or_worse_rate"]:
            assert event_report["features"][key]["players_covered"] == 0
            assert event_report["features"][key]["coverage_pct"] == 0.0
