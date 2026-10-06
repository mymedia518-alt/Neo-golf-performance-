"""2025100001 (2025's "동부건설·한국토지신탁 챔피언십", this tournament's
own 2025 identity) Modified Stableford SOURCE PASS verification, run
against the real local Windows probe capture committed at
klpga_pipeline/evidence/stableford_source_probe_2025100001/
scoreRecord_2025100001.html (1,362,254 bytes, status 200, captured
2026-10-06).

Before trusting extract_hole_outcomes() on an unseen Modified Stableford
page, two class-semantics questions were checked empirically against
this real file's own raw relative-to-par values (never assumed):

  - Does "Dbogeys" mean exactly double bogey, or double-bogey-or-worse?
    Two real cells classed Dbogeys are +3 relative to par (a TRIPLE
    bogey): 2R, 이정민2 hole#3 (stroke 7 vs hole par 4) and 송은아 hole#1
    (stroke 7 vs hole par 4). So Dbogeys = double bogey OR WORSE,
    matching the official Stableford double_or_worse=-3 single bucket
    exactly -- not "exactly double bogey".
  - How is albatross represented? It is NOT -- the full closed set of
    hole-outcome CSS classes anywhere in this file is only
    {par, birdies, bogeys, Dbogeys, eagles}; every real "eagles" cell
    (21 of them, across all 4 rounds) is exactly -2 relative to par,
    never -3. No albatross occurred for any player in this capture, so
    this file cannot show how one would be rendered -- that remains
    genuinely unconfirmed, not guessed as "same as eagle".

Only after both were confirmed did the Stableford point computation
run -- the official +7/+14/+14/+16/+51 result below fell out of an
already-verified classification, not the other way around."""
from __future__ import annotations

from pathlib import Path

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_scoring import HoleOutcomeCounts

FIXTURE = (
    Path(__file__).parent.parent
    / "evidence" / "stableford_source_probe_2025100001" / "scoreRecord_2025100001.html"
)
ROUNDS = ["1R", "2R", "3R", "4R"]


def _load():
    return extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))


def test_four_rounds_present_with_real_field_sizes():
    """108 in R1/R2 (matches the independently-confirmed 108-player
    field size), 61 in R3/R4 (cut after R2 -- top 60 and ties, so 61 is
    consistent with a tie at the cut line, matching the already-recorded
    cut_rule in 2026100004_TOURNAMENT_INFO.json's historical note)."""
    by_round = _load()
    assert set(by_round.keys()) == set(ROUNDS)
    assert len(by_round["1R"]) == 108
    assert len(by_round["2R"]) == 108
    assert len(by_round["3R"]) == 61
    assert len(by_round["4R"]) == 61


def test_dbogeys_class_is_double_bogey_or_worse_not_exactly_double():
    """Empirical check, not an assumption: find hole_par for every
    Dbogeys-classed cell and confirm at least one is +3 (triple bogey)
    relative to par, across the real file -- proving the class is a
    double-or-worse bucket, exactly matching official Stableford
    scoring's single double_or_worse=-3 bucket."""
    from bs4 import BeautifulSoup
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.table-scorecard, .table-scorecard table")
    found_triple_or_worse = False
    for table in tables:
        thead = table.find("thead")
        header_rows = thead.find_all("tr")
        hole_pars = [
            int(th.get_text(strip=True))
            for th in header_rows[1].find_all("th")
            if not any(c in ("today", "out", "in") for c in (th.get("class") or []))
            and th.get_text(strip=True).isdigit()
        ]
        tbody = table.find("tbody")
        for tr in tbody.find_all("tr", recursive=False):
            if tr.select_one("td.name") is None:
                continue
            outcome_cells = [
                td for td in tr.find_all("td")
                if any(c in ("par", "birdies", "bogeys", "Dbogeys", "eagles") for c in (td.get("class") or []))
            ]
            if len(outcome_cells) != 18:
                continue
            for i, td in enumerate(outcome_cells):
                classes = td.get("class") or []
                if "Dbogeys" not in classes:
                    continue
                text = td.get_text(strip=True)
                if not text.isdigit():
                    continue
                relative = int(text) - hole_pars[i]
                assert relative >= 2, f"Dbogeys cell with relative-to-par {relative} < 2"
                if relative >= 3:
                    found_triple_or_worse = True
    assert found_triple_or_worse, "expected at least one real +3-or-worse cell classed Dbogeys"


def test_no_albatross_class_exists_anywhere_in_this_real_file():
    html = FIXTURE.read_text(encoding="utf-8")
    assert "albatross" not in html.lower()


def test_eagles_class_is_always_exactly_two_under_par_never_albatross_level():
    from bs4 import BeautifulSoup
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.table-scorecard, .table-scorecard table")
    seen_any = False
    for table in tables:
        thead = table.find("thead")
        header_rows = thead.find_all("tr")
        hole_pars = [
            int(th.get_text(strip=True))
            for th in header_rows[1].find_all("th")
            if not any(c in ("today", "out", "in") for c in (th.get("class") or []))
            and th.get_text(strip=True).isdigit()
        ]
        tbody = table.find("tbody")
        for tr in tbody.find_all("tr", recursive=False):
            if tr.select_one("td.name") is None:
                continue
            outcome_cells = [
                td for td in tr.find_all("td")
                if any(c in ("par", "birdies", "bogeys", "Dbogeys", "eagles") for c in (td.get("class") or []))
            ]
            if len(outcome_cells) != 18:
                continue
            for i, td in enumerate(outcome_cells):
                if "eagles" not in (td.get("class") or []):
                    continue
                text = td.get_text(strip=True)
                if not text.isdigit():
                    continue
                seen_any = True
                assert int(text) - hole_pars[i] == -2
    assert seen_any


def test_kim_min_sol_identified_in_every_round():
    by_round = _load()
    for r in ROUNDS:
        assert "김민솔" in by_round[r]


def test_kim_min_sol_round_points_match_official_relay_exactly():
    by_round = _load()
    computed = [by_round[r]["김민솔"].total_points() for r in ROUNDS]
    assert computed == [7, 14, 14, 16]


def test_kim_min_sol_four_round_total_matches_official_plus_51():
    by_round = _load()
    total = sum(by_round[r]["김민솔"].total_points() for r in ROUNDS)
    assert total == 51


def test_kim_min_sol_hole_outcome_breakdown_by_round():
    by_round = _load()
    assert by_round["1R"]["김민솔"] == HoleOutcomeCounts(birdie=5, par=10, bogey=3)
    assert by_round["2R"]["김민솔"] == HoleOutcomeCounts(birdie=7, par=11)
    assert by_round["3R"]["김민솔"] == HoleOutcomeCounts(birdie=7, par=11)
    assert by_round["4R"]["김민솔"] == HoleOutcomeCounts(birdie=8, par=10)


def test_kim_min_sol_independent_cross_check_against_pages_own_displayed_strokes_to_par():
    """The page displays strokes-to-par (not Stableford points) in its
    own td.today/td.total columns. This is a SEPARATE check from the
    points reconstruction above: it confirms the extracted hole data,
    converted to ordinary signed stroke-vs-par, matches what the real
    page itself displays -- independent evidence the extraction is
    reading the real cells correctly (double_or_worse=0 for her in every
    round, so no double-bogey-magnitude ambiguity affects this check)."""
    from bs4 import BeautifulSoup
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.table-scorecard, .table-scorecard table")
    displayed_today = {}
    displayed_cum_total = {}
    for table in tables:
        thead = table.find("thead")
        round_label = thead.find_all("tr")[1].find("th").get_text(strip=True)
        tbody = table.find("tbody")
        for tr in tbody.find_all("tr", recursive=False):
            name_cell = tr.select_one("td.name")
            if name_cell and "김민솔" in name_cell.get_text():
                displayed_today[round_label] = tr.select_one("td.today").get_text(strip=True)
                displayed_cum_total[round_label] = tr.select_one("td.total").get_text(strip=True)

    by_round = _load()
    cumulative = 0
    for r in ROUNDS:
        c = by_round[r]["김민솔"]
        assert c.double_or_worse == 0, f"{r}: double_or_worse != 0 would make this cross-check ambiguous"
        score_to_par_today = c.birdie * -1 + c.eagle * -2 + c.bogey * 1 + c.albatross * -3
        cumulative += score_to_par_today
        assert str(score_to_par_today) == displayed_today[r]
        assert str(cumulative) == displayed_cum_total[r]


def test_full_field_reconstruction_covers_every_made_cut_player_not_just_kim_min_sol():
    """SOURCE PASS condition 5 (extensible to the full field, not just
    one example player): every one of the 61 players present in the 4R
    table gets a real 4-round total computed from the same extractor,
    and 김민솔's reconstructed total ranks her #1 -- consistent with her
    being the real 2025 winner and with her own displayed rank="1" in
    the real 4R table (checked directly, not assumed)."""
    from bs4 import BeautifulSoup
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.table-scorecard, .table-scorecard table")
    fourth_round_table = tables[3]
    km_rank_cell = None
    for tr in fourth_round_table.find("tbody").find_all("tr", recursive=False):
        name_cell = tr.select_one("td.name")
        if name_cell and "김민솔" in name_cell.get_text():
            km_rank_cell = tr.select_one("td.rank")
            break
    assert km_rank_cell is not None
    assert " ".join(km_rank_cell.get_text(" ", strip=True).split()) == "1"

    by_round = _load()
    finalists = set(by_round["4R"].keys())
    assert len(finalists) == 61
    totals = {
        name: sum(by_round[r][name].total_points() for r in ROUNDS if name in by_round[r])
        for name in finalists
    }
    assert totals["김민솔"] == 51
    assert totals["김민솔"] == max(totals.values())
