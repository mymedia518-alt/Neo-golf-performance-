"""2024100009 and 2023100002 Modified Stableford SOURCE PASS
verification -- same method as test_stableford_2025100001_reconstruction
.py, run against the real local Windows probe captures committed at
klpga_pipeline/evidence/stableford_source_probe_<code>/
scoreRecord_<code>.html (captured 2026-10-06, via
scripts/206_fetch_scoreRecord_2024_2023.py).

Also documents one real, isolated site-data anomaly found while
investigating a class-semantics mismatch in the 2023100002 file (see
test_known_data_anomaly_is_isolated_and_does_not_affect_scoring below):
a single cell's raw stroke digit ("88") is implausible, but it does not
affect Stableford scoring, which depends only on the cell's CSS class,
never the stroke digit -- the affected player (a real finalist who
played all 4 rounds) finishes with 2 points, far below the winner."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.collectors.score_record import extract_hole_outcomes

EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"
ROUNDS = ["1R", "2R", "3R", "4R"]

CASES = [
    {"game_code": "2024100009", "winner": "김민별", "known_rounds": [13, 8, 10, 18], "known_total": 49, "field_1r": 108, "field_3r": 60},
    {"game_code": "2023100002", "winner": "방신실", "known_rounds": [10, 5, 15, 13], "known_total": 43, "field_1r": 108, "field_3r": 61},
]


def _load(game_code):
    path = EVIDENCE_ROOT / f"stableford_source_probe_{game_code}" / f"scoreRecord_{game_code}.html"
    return extract_hole_outcomes(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["game_code"] for c in CASES])
def test_field_sizes_and_winner_present(case):
    by_round = _load(case["game_code"])
    assert set(by_round.keys()) == set(ROUNDS)
    assert len(by_round["1R"]) == case["field_1r"]
    assert len(by_round["2R"]) == case["field_1r"]
    assert len(by_round["3R"]) == case["field_3r"]
    assert len(by_round["4R"]) == case["field_3r"]
    for r in ROUNDS:
        assert case["winner"] in by_round[r]


@pytest.mark.parametrize("case", CASES, ids=[c["game_code"] for c in CASES])
def test_winner_round_points_match_official_relay_exactly(case):
    by_round = _load(case["game_code"])
    computed = [by_round[r][case["winner"]].total_points() for r in ROUNDS]
    assert computed == case["known_rounds"]


@pytest.mark.parametrize("case", CASES, ids=[c["game_code"] for c in CASES])
def test_winner_four_round_total_matches_official(case):
    by_round = _load(case["game_code"])
    total = sum(by_round[r][case["winner"]].total_points() for r in ROUNDS)
    assert total == case["known_total"]


@pytest.mark.parametrize("case", CASES, ids=[c["game_code"] for c in CASES])
def test_every_extracted_row_has_zero_or_eighteen_holes(case):
    by_round = _load(case["game_code"])
    for r, by_name in by_round.items():
        for name, counts in by_name.items():
            assert counts.total_holes in (0, 18), f"{case['game_code']}/{r}/{name}: {counts.total_holes} holes"


@pytest.mark.parametrize("case", CASES, ids=[c["game_code"] for c in CASES])
def test_full_field_reconstruction_ranks_winner_first(case):
    by_round = _load(case["game_code"])
    finalists = set(by_round["4R"].keys())
    totals = {
        name: sum(by_round[r][name].total_points() for r in ROUNDS if name in by_round[r])
        for name in finalists
    }
    assert totals[case["winner"]] == case["known_total"]
    assert totals[case["winner"]] == max(totals.values())


def test_known_data_anomaly_is_isolated_and_does_not_affect_scoring():
    """2023100002, 3R table, player 유서연2, hole#7 (par 4): the real raw
    td.Dbogeys cell text is literally "88" -- confirmed by direct
    re-inspection of the row's raw markup, not a BeautifulSoup
    concatenation artifact. This is a genuine site-side data anomaly
    (no real golfer shoots 88-over on one hole), found while checking
    Dbogeys/eagles semantics the same way 2025100001 was checked. (She
    is a real finalist who played all 4 rounds -- an earlier version of
    this test wrongly assumed her empty "4R" recap cell inside the 3R
    table's own row meant she hadn't played round 4 yet; that cell is
    just that round-table's own snapshot-so-far display. Her actual 4R
    table row shows a normal round. Corrected after being caught by
    this exact assertion failing against the real data.)

    The anomaly does not corrupt this reconstruction: Stableford scoring
    here depends only on the cell's CSS class (Dbogeys -> double_or_worse,
    -3 points), never the stroke digit itself, so "88" vs any other
    double-or-worse digit changes nothing. Her real total across all 4
    rounds is 2 points (2+4-8+4) -- nowhere near 방신실's winning 43,
    so this isolated anomaly does not threaten the winner verification
    either way."""
    path = EVIDENCE_ROOT / "stableford_source_probe_2023100002" / "scoreRecord_2023100002.html"
    html = path.read_text(encoding="utf-8")
    assert 'class="Dbogeys">88<' in html

    by_round = _load("2023100002")
    assert "유서연2" in by_round["3R"]
    assert "유서연2" in by_round["4R"]
    for r in ROUNDS:
        assert by_round[r]["유서연2"].total_holes == 18
    total = sum(by_round[r]["유서연2"].total_points() for r in ROUNDS)
    assert total == 2
