"""Red Team checks for the 23 real 2024 prior-tournament captures
(klpga_pipeline/evidence/stableford_prior_2024/) -- mirrors
test_stableford_2025_prior_data_redteam.py."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from klpga.collectors.score_record import extract_hole_outcomes

EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence" / "stableford_prior_2024"
CONTENT_ROOT = Path(__file__).parent.parent / "content" / "website_v2"

with open(CONTENT_ROOT / "STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json", encoding="utf-8") as f:
    MANIFEST = json.load(f)
    GAME_CODES = [e["game_code"] for e in MANIFEST["entries"]]


def test_manifest_has_23_distinct_codes_target_excluded():
    assert len(GAME_CODES) == 23
    assert len(set(GAME_CODES)) == 23
    assert "2024100009" not in GAME_CODES


def test_acquisition_report_all_23_source_pass():
    rep = json.loads((EVIDENCE_ROOT / "ACQUISITION_REPORT.json").read_text(encoding="utf-8"))
    results = rep["results"]
    assert len(results) == 23
    assert all(r.get("source_pass_fail") == "SOURCE_PASS" for r in results)
    assert all(r.get("acquisition_status") == "ACQUIRED" for r in results)


def test_every_capture_identity_verified_and_sha256_matches_committed_file():
    """Chain-of-custody re-verified for real -- unlike the 2025 run,
    this script already had the write_bytes fix from the start, so
    every recorded sha256 should match the actual committed bytes."""
    rep = json.loads((EVIDENCE_ROOT / "ACQUISITION_REPORT.json").read_text(encoding="utf-8"))
    by_code = {r["game_code"]: r for r in rep["results"]}
    for code in GAME_CODES:
        path = EVIDENCE_ROOT / f"{code}_scoreRecord.html"
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == by_code[code]["sha256"]
        assert len(data) == by_code[code]["response_bytes"]
        text = data.decode("utf-8")
        assert re.search(rf'value="{code}"\s*selected', text) is not None


def test_every_prior_capture_parses_and_every_row_has_zero_or_eighteen_holes():
    for code in GAME_CODES:
        html = (EVIDENCE_ROOT / f"{code}_scoreRecord.html").read_text(encoding="utf-8")
        by_round = extract_hole_outcomes(html)
        assert by_round
        for round_label, by_name in by_round.items():
            for name, counts in by_name.items():
                assert counts.total_holes in (0, 18)


def test_known_malformed_cell_is_the_one_already_investigated():
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
    assert found == [("2024050018", "박설휘", "12")]


def test_all_23_start_dates_strictly_before_target_and_latest_is_20241003():
    from klpga.website_v2.stableford_historical_dates import HISTORICAL_EVENT_DATES
    from datetime import date

    target = HISTORICAL_EVENT_DATES["2024100009"].event_start_date
    assert target == date(2024, 10, 10)
    dates = [date(*map(int, e["start_date"].split("-"))) for e in MANIFEST["entries"]]
    assert all(d < target for d in dates)
    assert max(dates) == date(2024, 10, 3)
