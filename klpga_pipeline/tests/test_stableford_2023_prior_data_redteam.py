"""Red Team checks for the 19 real 2023 prior-tournament captures
(klpga_pipeline/evidence/stableford_prior_2023/), plus the
cross-year immutability requirement: the 2024 and 2025 frozen results
must remain byte-identical after this 2023 work."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup

from klpga.collectors.score_record import extract_hole_outcomes

EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence" / "stableford_prior_2023"
CONTENT_ROOT = Path(__file__).parent.parent / "content" / "website_v2"

with open(CONTENT_ROOT / "STABLEFORD_2023_PRIOR_TOURNAMENT_MANIFEST_V1.json", encoding="utf-8") as f:
    MANIFEST = json.load(f)
    GAME_CODES = [e["game_code"] for e in MANIFEST["entries"]]


def test_manifest_has_19_distinct_codes_target_excluded():
    assert len(GAME_CODES) == 19
    assert len(set(GAME_CODES)) == 19
    assert "2023100002" not in GAME_CODES


def test_acquisition_report_all_19_source_pass():
    rep = json.loads((EVIDENCE_ROOT / "ACQUISITION_REPORT.json").read_text(encoding="utf-8"))
    results = rep["results"]
    assert len(results) == 19
    assert all(r.get("source_pass_fail") == "SOURCE_PASS" for r in results)
    assert all(r.get("acquisition_status") == "ACQUIRED" for r in results)


def test_every_capture_identity_verified_against_committed_file():
    import re
    for code in GAME_CODES:
        html = (EVIDENCE_ROOT / f"{code}_scoreRecord.html").read_text(encoding="utf-8")
        assert re.search(rf'value="{code}"\s*selected', html) is not None


def test_sha256_chain_of_custody_mismatch_is_explained_by_git_crlf_normalization():
    """FOUND, non-blocking: the 19 sha256/response_bytes values recorded
    in ACQUISITION_REPORT.json at capture time do NOT match the
    committed files as-is (unlike 2024, which matched exactly). Root
    cause here is DIFFERENT from the 2025 run's write_text bug: this
    script already used write_bytes correctly. Instead, the originally
    fetched HTML had real CRLF line endings, and something in the git
    add/commit path (core.autocrlf or equivalent on the acquiring
    machine) normalized them to bare LF before the commit landed --
    changing the committed bytes after the hash was taken. Proven here
    by reinserting a CR before every LF and confirming the
    reconstructed bytes DO match the recorded sha256/response_bytes
    exactly -- i.e. the content is byte-for-byte the same modulo line
    endings, not corrupted or wrong."""
    rep = json.loads((EVIDENCE_ROOT / "ACQUISITION_REPORT.json").read_text(encoding="utf-8"))
    by_code = {r["game_code"]: r for r in rep["results"]}
    for code in GAME_CODES:
        raw = (EVIDENCE_ROOT / f"{code}_scoreRecord.html").read_bytes()
        recorded_sha = by_code[code]["sha256"]
        recorded_bytes = by_code[code]["response_bytes"]
        assert hashlib.sha256(raw).hexdigest() != recorded_sha  # confirms the mismatch is real
        reconstructed = raw.replace(b"\n", b"\r\n")
        assert hashlib.sha256(reconstructed).hexdigest() == recorded_sha
        assert len(reconstructed) == recorded_bytes


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
    assert found == [("2023050004", "성은정", "11")]


def test_2025_frozen_result_unchanged_after_2023_work():
    import klpga.website_v2.stableford_2025_blind_backtest as frozen_2025
    records = frozen_2025.build_preevent_snapshot()
    digest, _ = frozen_2025.freeze_and_hash(records)
    assert digest == "232aee3f8e3ac368d5924ceef8b676b2543da8edcd42ec860cd73e38061a26d4"


def test_2024_frozen_result_unchanged_after_2023_work():
    from klpga.website_v2.stableford_blind_backtest import build_preevent_snapshot as generic_snapshot
    from klpga.website_v2.stableford_blind_backtest import freeze_and_hash as generic_freeze

    manifest_2024 = CONTENT_ROOT / "STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json"
    prior_dir_2024 = EVIDENCE_ROOT.parent / "stableford_prior_2024"
    records = generic_snapshot("2024100009", manifest_2024, prior_dir_2024)
    digest, _ = generic_freeze(records)
    assert digest == "e55a64403d75c4eb634b6632b7f4858ef73a4a8e64718d6f87cf65f88c788eb4"
