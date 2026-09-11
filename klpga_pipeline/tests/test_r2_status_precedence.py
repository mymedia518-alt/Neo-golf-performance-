"""Task H (fix/kb-r2-official-cut-gate-20260911): REAL LIVE EXECUTION
CORRECTION -- generic terminal-status precedence for
_reconcile_cut_evidence.

A real `python scripts/112_kb_r2_active_cycle.py --live` run against
gameCode=2026090003 HARD_STOPped: "cut-evidence conflict between
roundLeaderboard and scoreRecord for: ['양서후']" -- even though the
real scoreRecord evidence explicitly shows 양서후 = WD, physically
after the Missed Cut boundary. The primary roundLeaderboard source's
real status for that player was never a genuine competing terminal
determination (ACTIVE/unset/the confirmed 999-sentinel INCOMPLETE
placeholder) -- the previous reconciliation only recognized `None` and
`"ACTIVE"` as safe-to-enrich, so every OTHER real non-terminal
placeholder value fell through to the conflict branch by omission.

Fixed generically in _reconcile_cut_evidence (never by player_id or
name -- see its own updated docstring for the full precedence
contract): a named _TERMINAL_STATUSES set (WD/DQ/DNS/CUT) replaces the
two-value enumeration, and scoreRecord's own official_status="CUT" (a
signal that cannot itself distinguish literal-CUT-text from
section-derived CUT) is always treated as subordinate to the primary
source's own real, explicit terminal status.

Every test here calls the PURE _reconcile_cut_evidence function
directly with synthetic data -- never run_cycle(live=True)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
REAL_CUT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "klpga_r2_2026090003_official_round_two_trimmed.html"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_status_precedence_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


def _reconcile(module, current_status, official_status):
    rows = [{"player_id": "p1", "player_name": "선수A", "status": current_status}]
    evidence = {"rows": [{"player_name": "선수A", "official_status": official_status, "rank_display": None}], "cut_boundary_published": True}
    return module._reconcile_cut_evidence(rows, evidence)


# A. ACTIVE + WD -> WD, no conflict
def test_a_active_plus_wd_is_wd_no_conflict(module):
    reconciled, conflicts = _reconcile(module, "ACTIVE", "WD")
    assert conflicts == []
    assert reconciled[0]["status"] == "WD"


# B. unset + WD -> WD
def test_b_unset_plus_wd_is_wd(module):
    reconciled, conflicts = _reconcile(module, None, "WD")
    assert conflicts == []
    assert reconciled[0]["status"] == "WD"


# C. ACTIVE + section CUT -> CUT
def test_c_active_plus_section_cut_is_cut(module):
    reconciled, conflicts = _reconcile(module, "ACTIVE", "CUT")
    assert conflicts == []
    assert reconciled[0]["status"] == "CUT"


# D. WD + section CUT -> WD
def test_d_explicit_wd_plus_section_cut_stays_wd(module):
    reconciled, conflicts = _reconcile(module, "WD", "CUT")
    assert conflicts == []
    assert reconciled[0]["status"] == "WD"


# E. DQ + section CUT -> DQ
def test_e_explicit_dq_plus_section_cut_stays_dq(module):
    reconciled, conflicts = _reconcile(module, "DQ", "CUT")
    assert conflicts == []
    assert reconciled[0]["status"] == "DQ"


# F. DNS + section CUT -> DNS
def test_f_explicit_dns_plus_section_cut_stays_dns(module):
    reconciled, conflicts = _reconcile(module, "DNS", "CUT")
    assert conflicts == []
    assert reconciled[0]["status"] == "DNS"


# G. explicit CUT + explicit WD -> HARD_STOP
def test_g_explicit_cut_plus_explicit_wd_conflicts(module):
    reconciled, conflicts = _reconcile(module, "CUT", "WD")
    assert conflicts == ["선수A"]
    assert reconciled[0]["status"] == "CUT"  # untouched


# H. explicit DQ + explicit WD -> HARD_STOP
def test_h_explicit_dq_plus_explicit_wd_conflicts(module):
    reconciled, conflicts = _reconcile(module, "DQ", "WD")
    assert conflicts == ["선수A"]
    assert reconciled[0]["status"] == "DQ"  # untouched


# I. missing player does not acquire a terminal status
def test_i_missing_player_never_acquires_a_terminal_status(module):
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE"}]
    evidence = {"rows": [{"player_name": "다른선수", "official_status": "WD", "rank_display": "WD"}], "cut_boundary_published": True}
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "ACTIVE"  # untouched -- no matching evidence row


# J. real 양서후 evidence reconciles to WD without name-specific logic
def test_j_real_yang_seohu_evidence_reconciles_to_wd(module):
    assert REAL_CUT_FIXTURE.is_file()
    from klpga.collectors.score_record import parse_score_record_round_table

    html = REAL_CUT_FIXTURE.read_text(encoding="utf-8")
    cut_evidence = parse_score_record_round_table(html, round_tab_id="round-two")

    # Simulates the real roundLeaderboard value that produced the real
    # HARD_STOP: a non-terminal placeholder (the confirmed 999-sentinel
    # INCOMPLETE contract), never a genuine competing determination --
    # proven generically (_TERMINAL_STATUSES), not by matching this name.
    rows = [{"player_id": "real", "player_name": "양서후", "status": "INCOMPLETE"}]
    reconciled, conflicts = module._reconcile_cut_evidence(rows, cut_evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "WD"
