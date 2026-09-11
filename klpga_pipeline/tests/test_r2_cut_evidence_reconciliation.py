"""FINAL R2 EVIDENCE-GATE TASK: scripts/112's wiring of the real
scoreRecord cut-boundary evidence into the primary R2 rows and into
cut_known -- requirement H ("wire this evidence into
112_kb_r2_active_cycle.py so the R2 HOUSE can move from SKIP_WAIT to
R2 COMPLETE when official cut publication evidence exists").

Every test here calls PURE functions directly with synthetic data
(_reconcile_cut_evidence, _derive_cut_known, decide_r2_cycle) -- it
NEVER calls run_cycle(live=True) or _publish_and_close, because those
write real files under this repo's real content/website_v2/ tree for
the real KB game code. Proving the wiring is correct at the function
level is both sufficient and the ONLY safe way to test it without
risking a real production artifact write from synthetic test data.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_evidence_reconciliation_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


def _evidence(rows, *, cut_boundary_published):
    return {"rows": rows, "cut_boundary_published": cut_boundary_published}


# ---------------------------------------------------------------------
# _reconcile_cut_evidence: fills in real status from the second source,
# never overwrites an already-explicit disagreeing status.
# ---------------------------------------------------------------------

def test_reconcile_fills_in_cut_status_for_a_default_active_row(module):
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE"}]
    evidence = _evidence([{"player_name": "선수A", "official_status": "CUT", "rank_display": "T72"}], cut_boundary_published=True)
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "CUT"


def test_reconcile_fills_in_wd_for_a_row_with_no_status_at_all(module):
    rows = [{"player_id": "p1", "player_name": "양서후", "status": None}]
    evidence = _evidence([{"player_name": "양서후", "official_status": "WD", "rank_display": "WD"}], cut_boundary_published=True)
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "WD"


def test_reconcile_leaves_matching_explicit_status_untouched(module):
    rows = [{"player_id": "p1", "player_name": "양서후", "status": "WD"}]
    evidence = _evidence([{"player_name": "양서후", "official_status": "WD", "rank_display": "WD"}], cut_boundary_published=True)
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "WD"


def test_reconcile_never_silently_overrides_a_disagreeing_explicit_status(module):
    """The real P0-DUPLICATE-style safety net: if the primary source
    already says WD for a player but the evidence page says CUT (or
    vice versa), that is a genuine conflict between two real official
    sources -- never silently resolved either way."""
    rows = [{"player_id": "p1", "player_name": "선수B", "status": "WD"}]
    evidence = _evidence([{"player_name": "선수B", "official_status": "CUT", "rank_display": "T72"}], cut_boundary_published=True)
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == ["선수B"]
    assert reconciled[0]["status"] == "WD"  # untouched, not silently overwritten


def test_reconcile_leaves_row_untouched_when_no_matching_evidence_name(module):
    rows = [{"player_id": "p1", "player_name": "선수C", "status": "ACTIVE"}]
    evidence = _evidence([{"player_name": "다른선수", "official_status": "CUT", "rank_display": "T72"}], cut_boundary_published=True)
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "ACTIVE"


def test_reconcile_leaves_row_untouched_when_evidence_row_has_no_explicit_status(module):
    """An ACTIVE (made-the-cut) row in the evidence has official_status
    is None -- never overlaid as if it were a real "ACTIVE" claim, just
    left alone (the primary source's own default already covers it)."""
    rows = [{"player_id": "p1", "player_name": "선수D", "status": "ACTIVE"}]
    evidence = _evidence([{"player_name": "선수D", "official_status": None, "rank_display": "T5"}], cut_boundary_published=True)
    reconciled, conflicts = module._reconcile_cut_evidence(rows, evidence)
    assert conflicts == []
    assert reconciled[0]["status"] == "ACTIVE"


# ---------------------------------------------------------------------
# _derive_cut_known: cut_boundary_published is independently sufficient
# ---------------------------------------------------------------------

def test_derive_cut_known_true_from_boundary_alone_even_with_zero_literal_cut_rows(module):
    rows = [{"status": "ACTIVE"}, {"status": "WD"}]
    assert module._derive_cut_known(rows, cut_boundary_published=True) is True


def test_derive_cut_known_false_when_neither_signal_present(module):
    rows = [{"status": "ACTIVE"}, {"status": "WD"}]
    assert module._derive_cut_known(rows, cut_boundary_published=False) is False


def test_derive_cut_known_default_parameter_preserves_a7a2a24_behavior(module):
    """Backward compatibility: calling with the old single-argument
    signature (no cut_boundary_published) must behave exactly as
    commit a7a2a24 already tested and committed."""
    rows = [{"status": "ACTIVE"}]
    assert module._derive_cut_known(rows) is False
    rows_with_literal_cut = [{"status": "CUT"}]
    assert module._derive_cut_known(rows_with_literal_cut) is True


# ---------------------------------------------------------------------
# End-to-end WIRING proof (requirement H): reconciled rows + the
# derived cut_known correctly carry decide_r2_cycle from what would
# otherwise be SKIP_WAIT all the way to PUBLISH_AND_CLOSE -- using
# ONLY pure functions, never run_cycle/_publish_and_close (see module
# docstring for why real file writes must never happen in this test).
# ---------------------------------------------------------------------

def test_full_wiring_moves_decide_r2_cycle_from_skip_wait_to_publish_and_close(module):
    from klpga.neo_win.r2_active_cycle import decide_r2_cycle

    primary_rows = [
        {"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "player_name": "선수B", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p3", "player_name": "양서후", "status": "ACTIVE", "holes_completed": "36"},
    ]
    expected_ids = ["p1", "p2", "p3"]

    # BEFORE evidence: no explicit CUT/WD anywhere, no boundary -- the
    # real, honest a7a2a24-era outcome is WAIT (cut_known can't be
    # established yet).
    before_decision = decide_r2_cycle(
        primary_rows, expected_ids, official_page_available=True,
        cut_known=module._derive_cut_known(primary_rows), freeze_exists=False,
    )
    assert before_decision.action == "SKIP_WAIT"

    # AFTER evidence: the real scoreRecord cut-boundary page reports
    # 선수B missed the cut and 양서후 withdrew -- reconciled in, exactly
    # matching this task's real captured evidence shape.
    evidence = _evidence(
        [
            {"player_name": "선수B", "official_status": "CUT", "rank_display": "T72"},
            {"player_name": "양서후", "official_status": "WD", "rank_display": "WD"},
        ],
        cut_boundary_published=True,
    )
    reconciled_rows, conflicts = module._reconcile_cut_evidence(primary_rows, evidence)
    assert conflicts == []

    after_decision = decide_r2_cycle(
        reconciled_rows, expected_ids, official_page_available=True,
        cut_known=module._derive_cut_known(reconciled_rows, cut_boundary_published=evidence["cut_boundary_published"]),
        freeze_exists=False,
    )
    assert after_decision.action == "PUBLISH_AND_CLOSE"
