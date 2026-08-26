"""Round 7 regression tests — real B2-gate audit evidence (Windows
PowerShell extraction of the actual saved Sg::Around response body,
2026-08-26) proved `response_parser.py` was missing a THIRD
column-semantics pattern: KLPGA's Sg-family responses set
`var menu = "<identity>";` then branch on that value
(`if(menu == "X") { ... } else if(menu == "Y") { ... }`), each branch
assigning `menuName`/`recordNote`/`order` and up to five `data1`..
`data5` value-column labels — never a JSON-object metadata block, and
never the `var record<N> = "...";` pattern the existing
`dynamic_header_vars` layer recognizes. This is the confirmed root
cause of `Sg::Around`/`Sg::Approach` classifying AMBIGUOUS/
EMPTY_SCHEMA despite 223 real rows in the real bounded B1 rerun.

Against tests/fixtures/loadLocationRecord_sg_menu_switch_sample.html,
whose <script> block is VERBATIM from the real saved response — not a
hypothesis."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.response_parser import (
    _extract_menu_switch_metadata,
    parse_record_response,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _sg_html() -> str:
    return _read("loadLocationRecord_sg_menu_switch_sample.html")


# ---------------------------------------------------------------
# A. _extract_menu_switch_metadata in isolation, against the exact
#    real script content for each confirmed branch.
# ---------------------------------------------------------------


def test_around_branch_extracts_menu_name_and_record_note():
    metadata, data_labels = _extract_menu_switch_metadata(_sg_html())
    assert metadata.menu == "Around"
    assert metadata.menu_name == "SG : 그린주변"
    assert metadata.record_note == "* 그린주변(핀 위치로부터 60야드 미만)에서의 샷으로 획득한 타수"
    assert metadata.order == "desc"
    assert data_labels == {1: "총 SG : 그린주변", 2: "측정 라운드 수"}


def test_menu_switch_metadata_never_claims_layer_1_confidence():
    """Deliberately stays found=False — the per-column mapping is a
    positional heuristic, not confirmed by real row-level markup for
    the Sg family (see the function's own docstring)."""
    metadata, _ = _extract_menu_switch_metadata(_sg_html())
    assert metadata.found is False


def test_only_the_matching_branch_is_read_never_a_different_ones_labels():
    """The fixture's script defines Total/TeeToGreen/Tee/Approach
    branches too — none of THEIR labels must leak into the Around
    response's own data_labels."""
    _, data_labels = _extract_menu_switch_metadata(_sg_html())
    assert "SG : 티샷" not in data_labels.values()  # would be Tee's data1, wrong branch
    assert "SG : 어프로치" not in data_labels.values()  # would be Approach's data1, wrong branch


def test_total_branch_extracts_all_five_data_columns():
    """A different fixture instance targeting the Total branch (5
    columns) — proves the extractor isn't hardcoded to a 1-2 column
    shape."""
    html = _sg_html().replace('var menu = "Around";', 'var menu = "Total";')
    metadata, data_labels = _extract_menu_switch_metadata(html)
    assert metadata.menu == "Total"
    assert metadata.menu_name == "SG : 전체"
    assert metadata.record_note == "* SG : 티샷 to 그린 + SG : 퍼팅"
    assert data_labels == {
        1: "SG : 티샷",
        2: "SG : 어프로치",
        3: "SG : 그린주변",
        4: "SG : 퍼팅",
        5: "측정 라운드 수",
    }


# ---------------------------------------------------------------
# B. The real confirmed no-match case: var menu = "All"; with no
#    matching branch anywhere in the switch (the real Sg::All
#    response, which returned zero rows) — must never fabricate.
# ---------------------------------------------------------------


def test_no_matching_branch_returns_not_found_never_fabricated():
    html = _sg_html().replace('var menu = "Around";', 'var menu = "All";')
    metadata, data_labels = _extract_menu_switch_metadata(html)
    assert metadata.found is False
    assert metadata.menu_name is None
    assert data_labels == {}


def test_no_menu_var_at_all_returns_not_found():
    metadata, data_labels = _extract_menu_switch_metadata("<html><body>no script here</body></html>")
    assert metadata.found is False
    assert data_labels == {}


# ---------------------------------------------------------------
# C. End-to-end via parse_record_response — column semantics + status.
# ---------------------------------------------------------------


def test_end_to_end_sg_around_resolves_record_and_record1_labels():
    result = parse_record_response(_sg_html())
    labels = {c.field_name: c.label for c in result.column_semantics}
    assert labels["record"] == "총 SG : 그린주변"
    assert labels["record1"] == "측정 라운드 수"
    assert all(c.source == "menu_switch_vars" for c in result.column_semantics if c.label)


def test_end_to_end_sg_around_is_no_longer_ambiguous_empty_schema():
    """The exact real regression: before this fix, this shape
    classified AMBIGUOUS/EMPTY_SCHEMA despite real rows. It must now
    reach DISCOVERED_NOT_VALIDATED (real labels resolved, but not from
    a layer-1 metadata block or row-confirmed evidence — see
    _extract_menu_switch_metadata's docstring for why layer-1
    confidence is deliberately withheld)."""
    result = parse_record_response(_sg_html())
    assert result.parse_status == "DISCOVERED_NOT_VALIDATED"
    assert result.metadata.found is False
    assert result.metadata.menu_name == "SG : 그린주변"
    assert any("menu-switch" in note for note in result.notes)


def test_end_to_end_sg_around_rows_still_parse():
    result = parse_record_response(_sg_html())
    assert len(result.rows) == 2
    assert result.rows[0].player_name == "김새로미"
    assert result.rows[0].values["record"] == "1.42"


def test_end_to_end_sg_all_with_zero_rows_stays_empty_not_fabricated():
    """The real Sg::All case: var menu="All", no matching branch, AND
    (per the real response) zero player rows — must classify EMPTY,
    never invent a schema from an unmatched branch."""
    html = _sg_html().replace('var menu = "Around";', 'var menu = "All";')
    html = html.replace(
        '<tbody>\n<tr data-playercode="9807" data-name="김새로미" data-rank="1" data-record="1.42" data-record1="61"></tr>\n'
        '<tr data-playercode="9812" data-name="전예성" data-rank="2" data-record="0.98" data-record1="58"></tr>\n</tbody>',
        "<tbody></tbody>",
    )
    result = parse_record_response(html)
    assert result.parse_status == "EMPTY"
    assert result.rows == []


# ---------------------------------------------------------------
# D. Non-Sg fixtures are completely unaffected — this layer only ever
#    activates when metadata layer 1 found nothing AND a `var menu =`
#    declaration is present.
# ---------------------------------------------------------------


def test_approach_020104_fixture_unaffected_still_confirmed_via_metadata():
    result = parse_record_response(_read("loadLocationRecord_approach_020104_sample.html"))
    assert result.parse_status == "CONFIRMED"
    assert result.metadata.found is True


def test_dynamic_header_fixture_unaffected_still_discovered_not_validated():
    result = parse_record_response(_read("loadLocationRecord_dynamic_header_sample.html"))
    assert result.parse_status == "DISCOVERED_NOT_VALIDATED"
    assert all(c.source in ("dynamic_header_vars",) for c in result.column_semantics if c.label)
