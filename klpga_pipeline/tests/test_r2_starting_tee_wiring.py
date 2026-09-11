"""Task G (fix/kb-r2-official-cut-gate-20260911): REAL R2 STARTING-TEE
WIRING regression tests -- the final P0 blocker before real R2
execution.

ROOT CAUSE (identified while completing e902bd5): scripts/112's
_collect_live_r2() called klpga.parsers.round_progress.
resolve_completed_holes(raw_inghole, starting_tee=None) -- always
None. KLPGA's real data-inghole is the LAST ACTUAL COURSE HOLE played
(klpga.parsers.leaderboard_parser's own confirmed contract), not a
completed-hole count; it is correct arithmetic input only when combined
with the player's REAL starting tee. Silently assuming tee=1 for every
player can fabricate a false-complete 18 from a genuinely partial round
for any real 10-tee starter (see test C below) -- unsafe for a field
(holes_completed) that directly gates R2_COMPLETE / PUBLISH_AND_CLOSE.

FIX: scripts/112 now fetches Round 2's own real grouping from the
official group/tee-time page (klpga.collectors.group_page +
klpga.parsers.group_page_parser.parse_round_grouping(round_number=2) --
the SAME real, confirmed source scripts/96's own
_fetch_round1_starting_tees already uses for R1), joined by the one
stable official identity that page carries directly: player_code.
_collect_live_r2() now carries the RAW course-hole value through under
a private `_raw_inghole` key; only the new
_resolve_r2_starting_tee_and_holes (called from run_cycle with the
separately-collected starting-tee evidence) is allowed to turn it into
the real `holes_completed` field via round_progress.
resolve_completed_holes, unmodified.

Missing evidence (group page unavailable / Round 2 grouping not yet
published) NEVER silently assumes tee 1 -- affected rows get the
explicit _UNRESOLVED_STARTING_TEE sentinel, which naturally routes
through r2_readiness.assess_r2's own existing, unmodified "36"/"F"/
"FINAL" check to WAIT (mirrors this script's existing cut-boundary
evidence pattern: missing secondary evidence degrades to the primary
gate's own WAIT, never blocks the cycle by itself). A genuine identity
conflict (the group page disagreeing with itself about one player's
starting tee) is a HARD_STOP, never silently resolved -- mirrors
_reconcile_cut_evidence's own conflict discipline exactly.

Every test here calls PURE functions directly with synthetic (or, for
the real-evidence tests, real committed artifact/fixture) data --
NEVER run_cycle(live=True) or _publish_and_close (see
test_r2_cut_evidence_reconciliation.py's own module docstring for why:
those would write real files into this repo's real content/website_v2/
tree)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from klpga.neo_win.r2_active_cycle import decide_r2_cycle
from klpga.neo_win.r2_house_contract import load_expected_r2_field
from klpga.neo_win.r2_readiness import assess_r2
from klpga.parsers.group_page_parser import GroupingRow, parse_round_grouping
from klpga.parsers.round_progress import resolve_completed_holes

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
REAL_R1_EVIDENCE_PATH = ROOT / "content" / "website_v2" / "NEO_KB_2026090003_R1_OFFICIAL_RESULT_EVIDENCE_V1.json"
REAL_CUT_FIXTURE = ROOT / "tests" / "fixtures" / "klpga_r2_2026090003_official_round_two_trimmed.html"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_starting_tee_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


def _row(player_id: str, name: str, *, raw_inghole, status: str = "ACTIVE") -> dict:
    return {"player_id": player_id, "player_name": name, "status": status, "_raw_inghole": raw_inghole,
            "r1_score_to_par": None, "r2_score_to_par": None}


def _group_page_html(entries: list[tuple[str, str, str]], *, round_id: str = "round-two") -> str:
    """Fabricated HTML built structurally from group_page_parser.py's
    own confirmed real markup (td.fixed-start / td.text-start /
    a[href*="playerCode="] / span.name) -- the same real fixture-derived
    edge-case-coverage convention already used by
    test_score_record_round_table_precedence.py, for a Round 2 grouping
    shape the one real committed group_page_sample.html fixture does not
    happen to cover (that capture's Round 2 was not yet published)."""
    rows_html = "".join(
        f'<tr><td class="fixed-start">{tee}</td><td>09:10</td>'
        f'<td class="text-start"><a href="/web/player?playerCode={pid}"></a><span class="name">{name}</span></td></tr>'
        for tee, pid, name in entries
    )
    return f'<html><body><div id="{round_id}"><table class="table-teetimes"><tbody>{rows_html}</tbody></table></div></body></html>'


# ---------------------------------------------------------------------
# A. tee 1: last actual hole 18 -> 18 completed.
# ---------------------------------------------------------------------

def test_a_tee_1_last_actual_hole_18_is_18_completed(module):
    rows = [_row("p1", "선수A", raw_inghole="18")]
    tee_evidence = {"tee_by_player": {"p1": "1"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    assert resolved[0]["holes_completed"] == "18"
    assert "_raw_inghole" not in resolved[0]


# ---------------------------------------------------------------------
# B. tee 10: sequence 10...18,1...9 -> 18 completed.
# ---------------------------------------------------------------------

def test_b_tee_10_full_sequence_is_18_completed(module):
    rows = [_row("p1", "선수A", raw_inghole="9")]  # last real hole played is course-hole 9
    tee_evidence = {"tee_by_player": {"p1": "10"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    assert resolved[0]["holes_completed"] == "18"


# ---------------------------------------------------------------------
# C. tee 10 partial: last actual hole 18 -> 9 completed, NOT 18.
#    This IS the exact fabrication the old starting_tee=None wiring
#    would have produced (raw "18" treated as if tee were 1).
# ---------------------------------------------------------------------

def test_c_tee_10_partial_last_actual_hole_18_is_9_completed_not_18(module):
    rows = [_row("p1", "선수A", raw_inghole="18")]
    tee_evidence = {"tee_by_player": {"p1": "10"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    assert resolved[0]["holes_completed"] == "9"
    assert resolved[0]["holes_completed"] != "18"


# ---------------------------------------------------------------------
# D. tee 10 partial: last actual hole 1 -> 10 completed.
# ---------------------------------------------------------------------

def test_d_tee_10_partial_last_actual_hole_1_is_10_completed(module):
    rows = [_row("p1", "선수A", raw_inghole="1")]
    tee_evidence = {"tee_by_player": {"p1": "10"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    assert resolved[0]["holes_completed"] == "10"


# ---------------------------------------------------------------------
# E. same data-inghole produces different completed-hole values where
#    starting tee differs.
# ---------------------------------------------------------------------

def test_e_same_raw_inghole_different_tee_gives_different_completed(module):
    rows = [_row("p1", "선수A", raw_inghole="9"), _row("p2", "선수B", raw_inghole="9")]
    tee_evidence = {"tee_by_player": {"p1": "1", "p2": "10"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    by_id = {r["player_id"]: r["holes_completed"] for r in resolved}
    assert by_id["p1"] == "9"    # tee 1: raw "9" really is 9 holes played
    assert by_id["p2"] == "18"   # tee 10: raw "9" is the full 18-hole sequence
    assert by_id["p1"] != by_id["p2"]


# ---------------------------------------------------------------------
# F. missing starting tee does not silently produce false R2_COMPLETE.
# ---------------------------------------------------------------------

def test_f_missing_starting_tee_never_silently_completes(module):
    # No tee evidence at all for p1 (group page unavailable / Round 2
    # grouping not yet published -- tee_evidence itself is None).
    rows = [_row("p1", "선수A", raw_inghole="18", status="ACTIVE")]
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, None)
    assert conflicts == []
    assert resolved[0]["holes_completed"] == module._UNRESOLVED_STARTING_TEE
    assert resolved[0]["holes_completed"] not in {"18", "36"}

    # Never fabricated into a false cumulative-complete either.
    cumulative = module._apply_r2_cumulative_completion(resolved, expected_player_ids=["p1"])
    assert cumulative[0]["holes_completed"] == module._UNRESOLVED_STARTING_TEE  # int() failed, left untouched

    readiness = assess_r2(cumulative, ["p1"], cut_known=True)
    assert readiness.decision == "WAIT"
    assert readiness.reason == "R2 player/hole completion unresolved"


def test_f2_starting_tee_evidence_present_but_this_player_absent_from_it(module):
    # The group page IS available this cycle, but this specific player
    # simply isn't in the returned grouping (e.g. late add / a mismatch
    # between the leaderboard and grouping snapshots) -- same
    # unresolved-not-fabricated outcome, never a silent tee-1 default.
    rows = [_row("p1", "선수A", raw_inghole="18")]
    tee_evidence = {"tee_by_player": {"p2": "1"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    assert resolved[0]["holes_completed"] == module._UNRESOLVED_STARTING_TEE


# ---------------------------------------------------------------------
# G. player identity mismatch/ambiguity cannot silently select a tee.
# ---------------------------------------------------------------------

def test_g_ambiguous_starting_tee_evidence_is_never_silently_resolved(module):
    # The real group page itself disagreeing about one player's tee
    # (two grouping rows for the same player_code, different tees) --
    # via the pure _build_starting_tee_map helper, no HTTP involved.
    groupings = [
        GroupingRow(player_code="p1", player_name="선수A", starting_tee="1", tee_time="09:10"),
        GroupingRow(player_code="p1", player_name="선수A", starting_tee="10", tee_time="13:20"),
    ]
    evidence = module._build_starting_tee_map(groupings)
    assert evidence["ambiguous_player_ids"] == frozenset({"p1"})
    assert "p1" not in evidence["tee_by_player"]  # never picks either value

    rows = [_row("p1", "선수A", raw_inghole="18")]
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, evidence)
    assert conflicts == ["p1"]  # caller MUST HARD_STOP on this
    assert resolved[0]["holes_completed"] == module._UNRESOLVED_STARTING_TEE


def test_g2_same_tee_repeated_is_not_ambiguous(module):
    groupings = [
        GroupingRow(player_code="p1", player_name="선수A", starting_tee="1", tee_time="09:10"),
        GroupingRow(player_code="p1", player_name="선수A", starting_tee="1", tee_time="09:10"),
    ]
    evidence = module._build_starting_tee_map(groupings)
    assert evidence["ambiguous_player_ids"] == frozenset()
    assert evidence["tee_by_player"]["p1"] == "1"


def test_g3_real_group_page_markup_parses_into_the_pure_tee_map_correctly(module):
    """Proves the fabricated-but-structurally-real HTML (see
    _group_page_html's own docstring) really does flow through the
    real, unmodified parse_round_grouping the same way a real captured
    Round 2 page would."""
    html = _group_page_html([("1", "10001", "선수A"), ("10", "10002", "선수B")])
    groupings = parse_round_grouping(html, round_number=2)
    evidence = module._build_starting_tee_map(groupings)
    assert evidence["tee_by_player"] == {"10001": "1", "10002": "10"}
    assert evidence["ambiguous_player_ids"] == frozenset()


# ---------------------------------------------------------------------
# H. WD remains WD (unaffected by starting-tee resolution either way).
# ---------------------------------------------------------------------

def test_h_wd_remains_wd_regardless_of_starting_tee_resolution(module):
    rows = [
        _row("p1", "선수A", raw_inghole="18", status="ACTIVE"),
        _row("p2", "선수B", raw_inghole="9", status="WD"),  # no tee evidence for the WD player
    ]
    tee_evidence = {"tee_by_player": {"p1": "1"}, "ambiguous_player_ids": frozenset()}
    resolved, conflicts = module._resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    assert conflicts == []
    wd_row = next(r for r in resolved if r["player_id"] == "p2")
    assert wd_row["status"] == "WD"
    assert wd_row["holes_completed"] == module._UNRESOLVED_STARTING_TEE  # real, but never checked

    cumulative = module._apply_r2_cumulative_completion(resolved, expected_player_ids=["p1", "p2"])
    readiness = assess_r2(cumulative, ["p1", "p2"], cut_known=True)
    assert readiness.decision == "R2_COMPLETE"  # WD row's unresolved holes_completed never blocks it
    assert readiness.wd == 1


# ---------------------------------------------------------------------
# I. Compose the COMPLETE chain: official grouping evidence -> starting
#    tee -> current-round completed holes -> official table-cut
#    evidence -> R2 cumulative completion -> decide_r2_cycle ->
#    PUBLISH_AND_CLOSE. Uses REAL evidence/fixtures wherever available:
#    the real, committed R1 evidence artifact (118 real player_ids/
#    names, zero hardcoded literals) AND the real, committed cut-
#    boundary fixture (klpga_r2_2026090003_official_round_two_trimmed.
#    html -- same real 118-player population, confirmed by direct
#    comparison of both real sources' player_name sets). The one piece
#    with no real captured equivalent available (this game_code's
#    actual Round 2 tee-time grouping was never captured) is a
#    fabricated-but-real-identity grouping page, built only from those
#    real player_ids/names -- never a fictional/synthetic tournament.
# ---------------------------------------------------------------------

def test_i_full_chain_grouping_to_starting_tee_to_holes_to_cut_to_cumulative_to_publish_and_close(module):
    assert REAL_R1_EVIDENCE_PATH.is_file()
    assert REAL_CUT_FIXTURE.is_file()

    expected = load_expected_r2_field(REAL_R1_EVIDENCE_PATH)
    real_r1 = json.loads(REAL_R1_EVIDENCE_PATH.read_text(encoding="utf-8"))
    name_by_id = {str(p["playerCode"]): p["name"] for p in real_r1["players"]}
    assert set(name_by_id) == expected.player_ids

    # Real cut-boundary evidence: real official CUT/WD determinations
    # for this exact real 118-player population.
    cut_html = REAL_CUT_FIXTURE.read_text(encoding="utf-8")
    from klpga.collectors.score_record import parse_score_record_round_table
    cut_evidence = parse_score_record_round_table(cut_html, round_tab_id="round-two")
    assert cut_evidence["cut_boundary_published"] is True

    # Deterministic (not fabricated-random) real-identity tee assignment
    # -- alternate tee 1 / tee 10 by player_id parity -- covering both
    # branches of resolve_completed_holes' real arithmetic across the
    # entire real population, with every real player entered on the
    # official grouping page (as the real page always lists everyone).
    group_entries = [
        ("10" if int(pid) % 2 == 0 else "1", pid, name)
        for pid, name in name_by_id.items()
    ]
    group_html = _group_page_html(group_entries)
    groupings = parse_round_grouping(group_html, round_number=2)
    tee_evidence = module._build_starting_tee_map(groupings)
    assert tee_evidence["ambiguous_player_ids"] == frozenset()
    assert set(tee_evidence["tee_by_player"]) == expected.player_ids

    # Real course-hole values that correspond to a genuine, real full
    # 18-hole round FOR THE ASSIGNED REAL TEE (never fabricated as a
    # flat "18" bypassing tee arithmetic) -- tee 1 finishes on
    # course-hole 18, tee 10 finishes on course-hole 9.
    raw_rows = [
        {
            "player_id": pid, "player_name": name, "status": "ACTIVE",
            "_raw_inghole": "18" if tee_evidence["tee_by_player"][pid] == "1" else "9",
            "r1_score_to_par": None, "r2_score_to_par": None,
        }
        for pid, name in name_by_id.items()
    ]

    # Sanity: prove tee arithmetic is real, not a shortcut -- every raw
    # value, run through the real unmodified round_progress function
    # with its real assigned tee, really does resolve to 18.
    for row in raw_rows:
        tee = tee_evidence["tee_by_player"][row["player_id"]]
        assert resolve_completed_holes(row["_raw_inghole"], tee).completed == 18

    resolved_rows, tee_conflicts = module._resolve_r2_starting_tee_and_holes(raw_rows, tee_evidence)
    assert tee_conflicts == []
    assert all(r["holes_completed"] == "18" for r in resolved_rows)

    status_rows, status_conflicts = module._reconcile_cut_evidence(resolved_rows, cut_evidence)
    assert status_conflicts == []
    assert any(r["status"] == "CUT" for r in status_rows)
    assert any(r["status"] == "WD" for r in status_rows)  # real 양서후

    cumulative_rows = module._apply_r2_cumulative_completion(status_rows, expected.player_ids)
    for r in cumulative_rows:
        if r["status"] in ("ACTIVE", "CUT"):
            assert r["holes_completed"] == "36"

    cut_known = module._derive_cut_known(cumulative_rows, cut_boundary_published=cut_evidence["cut_boundary_published"])
    assert cut_known is True

    decision = decide_r2_cycle(
        cumulative_rows, sorted(expected.player_ids),
        official_page_available=True, cut_known=cut_known, freeze_exists=False,
    )
    assert decision.action == "PUBLISH_AND_CLOSE"
    assert decision.readiness.decision == "R2_COMPLETE"
