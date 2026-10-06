"""Red Team checks specific to the 23 real 2025 prior-tournament
captures (klpga_pipeline/evidence/stableford_prior_2025/) -- malformed
cells, WD/missing-round handling, and the committed comparison/
evaluation JSON artifacts staying consistent with live computation."""
from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from klpga.collectors.score_record import extract_hole_outcomes

EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence" / "stableford_prior_2025"
CONTENT_ROOT = Path(__file__).parent.parent / "content" / "website_v2"

with open(CONTENT_ROOT / "STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json", encoding="utf-8") as f:
    GAME_CODES = [e["game_code"] for e in json.load(f)["entries"]]


def test_every_prior_capture_parses_and_every_row_has_zero_or_eighteen_holes():
    for code in GAME_CODES:
        html = (EVIDENCE_ROOT / f"{code}_scoreRecord.html").read_text(encoding="utf-8")
        by_round = extract_hole_outcomes(html)
        assert by_round, f"{code}: no round tables parsed"
        for round_label, by_name in by_round.items():
            for name, counts in by_name.items():
                assert counts.total_holes in (0, 18), (
                    f"{code}/{round_label}/{name}: {counts.total_holes} holes (expected 0 or 18)"
                )


def test_known_malformed_cells_are_exactly_the_two_already_investigated():
    """Any stroke value >10 in an outcome-classed cell across all 23
    files -- re-derived here, not just asserted, so a NEW anomaly in a
    future re-capture would be caught rather than silently matching a
    stale expectation."""
    found = []
    for code in GAME_CODES:
        html = (EVIDENCE_ROOT / f"{code}_scoreRecord.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.select("table.table-scorecard, .table-scorecard table"):
            tbody = table.find("tbody")
            if tbody is None:
                continue
            for tr in tbody.find_all("tr", recursive=False):
                if tr.select_one("td.name") is None:
                    continue
                cells = [
                    td for td in tr.find_all("td")
                    if any(c in ("par", "birdies", "bogeys", "Dbogeys", "eagles") for c in (td.get("class") or []))
                ]
                if len(cells) != 18:
                    continue
                for td in cells:
                    text = td.get_text(strip=True)
                    if text.isdigit() and int(text) > 10:
                        found.append((code, tr.select_one("td.name").get_text(strip=True), text))
    assert sorted(found) == sorted([
        ("2025050001", "황민정", "11"),
        ("2025060003", "장하나", "12"),
    ])


def test_ordinary_vs_stableford_report_matches_live_computation():
    from klpga.website_v2.stableford_2025_blind_backtest import build_preevent_snapshot

    report = json.loads((CONTENT_ROOT / "STABLEFORD_2025_ORDINARY_VS_STABLEFORD_V1.json").read_text(encoding="utf-8"))
    records = build_preevent_snapshot()
    ordinary = {
        r.player_name: r.birdie_rate - r.bogey_rate + 2 * r.eagle_rate - 2 * r.double_or_worse_rate
        for r in records
    }
    ord_sorted = sorted(records, key=lambda r: -ordinary[r.player_name])
    ord_rank = {r.player_name: i + 1 for i, r in enumerate(ord_sorted)}
    sf_rank = {r.player_name: r.pre_event_rank for r in records}

    km = report["kim_min_sol"]
    assert km["ordinary_rank"] == ord_rank["김민솔"]
    assert km["stableford_rank"] == sf_rank["김민솔"]
    assert km["rank_shift"] == ord_rank["김민솔"] - sf_rank["김민솔"]
    assert km["rank_shift"] > 0  # confirmed real riser


def test_frozen_snapshot_artifact_hash_matches_its_own_committed_records():
    from klpga.website_v2.stableford_2025_blind_backtest import freeze_and_hash, build_preevent_snapshot

    artifact = json.loads((CONTENT_ROOT / "STABLEFORD_2025_FROZEN_PREEVENT_SNAPSHOT_V1.json").read_text(encoding="utf-8"))
    assert artifact["frozen_before_actual_results_joined"] is True

    live_records = build_preevent_snapshot()
    live_digest, live_payload = freeze_and_hash(live_records)
    assert artifact["sha256"] == live_digest
    # round-trip through JSON so tuple-vs-list typing (tournaments_used)
    # doesn't cause a false mismatch -- the hash comparison above is
    # already the real byte-for-byte integrity check.
    assert artifact["records"] == json.loads(json.dumps(live_payload, ensure_ascii=False))
