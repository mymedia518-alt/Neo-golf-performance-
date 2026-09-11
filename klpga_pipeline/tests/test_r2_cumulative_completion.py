"""Task F (fix/kb-r2-official-cut-gate-20260911): R2 CUMULATIVE
COMPLETION regression tests.

ROOT CAUSE: scripts/112's _collect_live_r2() fed R2's own CURRENT-
ROUND-ONLY holes_completed (klpga.parsers.round_progress.
resolve_completed_holes -- correctly generic, 0-18, unchanged by this
fix) straight into r2_readiness.assess_r2's own separate, deliberate,
already-tested CUMULATIVE R1+R2 completion contract (its "36"/"F"/
"FINAL" check on holes_completed, also unchanged by this fix). Real R2
data could never satisfy that check via the old wiring.

FIX (reconciliation, not collection or assessment): scripts/112's new
_apply_r2_cumulative_completion(rows, expected_player_ids) adds the
GUARANTEED R1=18 fact -- taken directly from KB's own real, committed
R1 evidence artifact's own contract (r1_forward_population, which that
artifact's own `contract` dict documents as EXCLUDING every official
R1 WD) -- to R2's own real current-round value, for every row whose
player_id is a confirmed member of that expected population. Neither
round_progress.resolve_completed_holes nor assess_r2's own "36" check
is modified.

Every test here calls PURE functions directly with synthetic (or, for
the real-evidence E2E test, the real committed R1 artifact's own)
data -- NEVER run_cycle(live=True) or _publish_and_close, matching
test_r2_cut_evidence_reconciliation.py's own established, binding
safety convention (see that module's docstring): those would write
real files into this repo's real content/website_v2/ tree.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from klpga.neo_win.r2_active_cycle import decide_r2_cycle
from klpga.neo_win.r2_house_contract import load_expected_r2_field
from klpga.neo_win.r2_readiness import assess_r2
from klpga.parsers.round_progress import resolve_completed_holes

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
REAL_R1_EVIDENCE_PATH = ROOT / "content" / "website_v2" / "NEO_KB_2026090003_R1_OFFICIAL_RESULT_EVIDENCE_V1.json"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_cumulative_completion_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


# ---------------------------------------------------------------------
# 1. R1 complete + R2 complete => cumulative completion evidence
#    satisfies R2 (18 R2-own holes + guaranteed R1 18 = 36).
# ---------------------------------------------------------------------

def test_1_full_r2_round_plus_guaranteed_r1_satisfies_cumulative_completion(module):
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "18"}]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1"])
    assert reconciled[0]["holes_completed"] == "36"
    readiness = assess_r2(reconciled, ["p1"], cut_known=True)
    assert readiness.decision == "R2_COMPLETE"


# ---------------------------------------------------------------------
# 2. R2 only 17 holes => NOT complete (cumulative 35, not 36).
# ---------------------------------------------------------------------

def test_2_r2_only_17_holes_is_not_cumulative_complete(module):
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "17"}]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1"])
    assert reconciled[0]["holes_completed"] == "35"
    readiness = assess_r2(reconciled, ["p1"], cut_known=True)
    assert readiness.decision == "WAIT"
    assert readiness.reason == "R2 player/hole completion unresolved"


# ---------------------------------------------------------------------
# 3. 10th-tee starter completing 18 holes => correctly complete.
#    round_progress.resolve_completed_holes is already proven 10th-tee
#    aware (tests/test_round_progress.py); this proves the NEW
#    reconciliation layer correctly builds cumulative 36 on top of a
#    real, correctly-tee-adjusted current-round value -- the exact
#    combination a real 10th-tee finisher needs.
# ---------------------------------------------------------------------

def test_3_10th_tee_starter_completing_18_holes_is_cumulative_complete(module):
    # Real 10-tee starter finishes on hole 9 (10,11,...,18,1,...,9) --
    # resolve_completed_holes correctly reports 18, never the naive raw "9".
    per_round = resolve_completed_holes(raw_inghole="9", starting_tee="10")
    assert per_round.completed == 18
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": str(per_round.completed)}]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1"])
    assert reconciled[0]["holes_completed"] == "36"
    readiness = assess_r2(reconciled, ["p1"], cut_known=True)
    assert readiness.decision == "R2_COMPLETE"


# ---------------------------------------------------------------------
# 4. data-inghole=18 does not automatically mean 18 completed if
#    start/progress evidence disagrees -- an out-of-range raw hole
#    number is never guessed into a real count (round_progress's own
#    existing defensive contract), so it must never be silently
#    fabricated into cumulative completeness either.
# ---------------------------------------------------------------------

def test_4_disagreeing_start_progress_evidence_is_never_fabricated_complete(module):
    # raw_inghole "19" is out-of-range for an 18-hole round -- never
    # guessed, resolve_completed_holes returns 0, not 18.
    per_round = resolve_completed_holes(raw_inghole="19", starting_tee="1")
    assert per_round.completed == 0
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": str(per_round.completed)}]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1"])
    assert reconciled[0]["holes_completed"] == "18"  # guaranteed R1 18 + real R2 0, never fabricated 36
    readiness = assess_r2(reconciled, ["p1"], cut_known=True)
    assert readiness.decision == "WAIT"


# ---------------------------------------------------------------------
# 5. WD remains WD and is not required to reach 36.
# ---------------------------------------------------------------------

def test_5_wd_row_never_required_to_reach_cumulative_36(module):
    rows = [
        {"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "18"},
        {"player_id": "p2", "player_name": "선수B", "status": "WD", "holes_completed": "9"},
    ]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1", "p2"])
    wd_row = next(r for r in reconciled if r["player_id"] == "p2")
    assert wd_row["status"] == "WD"
    readiness = assess_r2(reconciled, ["p1", "p2"], cut_known=True)
    assert readiness.decision == "R2_COMPLETE"  # WD row's holes_completed never checked
    assert readiness.wd == 1


# ---------------------------------------------------------------------
# 6. DQ remains DQ and is not required to reach 36.
# ---------------------------------------------------------------------

def test_6_dq_row_never_required_to_reach_cumulative_36(module):
    rows = [
        {"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "18"},
        {"player_id": "p2", "player_name": "선수B", "status": "DQ", "holes_completed": "4"},
    ]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1", "p2"])
    dq_row = next(r for r in reconciled if r["player_id"] == "p2")
    assert dq_row["status"] == "DQ"
    readiness = assess_r2(reconciled, ["p1", "p2"], cut_known=True)
    assert readiness.decision == "R2_COMPLETE"  # DQ row's holes_completed never checked
    assert readiness.dq == 1


# ---------------------------------------------------------------------
# 7. missing player does not become WD/CUT -- it stays a real,
#    explicit HARD_STOP ("entrant absent without official WD/DQ/DNS
#    status"), assess_r2's own pre-existing, unmodified contract --
#    this fix's reconciliation never touches rows that aren't present.
# ---------------------------------------------------------------------

def test_7_missing_player_never_becomes_wd_or_cut(module):
    rows = [{"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "18"}]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=["p1", "p2"])
    ids_present = {r["player_id"] for r in reconciled}
    assert "p2" not in ids_present  # never fabricated into existence
    readiness = assess_r2(reconciled, ["p1", "p2"], cut_known=True)
    assert readiness.decision == "HARD_STOP"
    assert readiness.reason == "entrant absent without official WD/DQ/DNS status"


# ---------------------------------------------------------------------
# 8. existing CUT-boundary tests still pass -- proven by running
#    test_r2_cut_evidence_reconciliation.py / test_score_record_round_
#    table*.py / test_r2_cut_gate.py in the same pytest session as this
#    file (see this task's [FULL TEST RESULTS] report); this file adds
#    one direct proof that reconciling cumulative completion and
#    reconciling cut evidence compose correctly together, order-
#    independent, exactly as scripts/112's run_cycle wires them.
# ---------------------------------------------------------------------

def test_8_cumulative_completion_composes_with_cut_evidence_reconciliation(module):
    primary_rows = [
        {"player_id": "p1", "player_name": "선수A", "status": "ACTIVE", "holes_completed": "18"},
        {"player_id": "p2", "player_name": "선수B", "status": "ACTIVE", "holes_completed": "18"},
    ]
    evidence = {
        "rows": [{"player_name": "선수B", "official_status": "CUT", "rank_display": "T72"}],
        "cut_boundary_published": True,
    }
    reconciled_status, conflicts = module._reconcile_cut_evidence(primary_rows, evidence)
    assert conflicts == []
    reconciled = module._apply_r2_cumulative_completion(reconciled_status, expected_player_ids=["p1", "p2"])
    assert reconciled[1]["status"] == "CUT"
    assert reconciled[1]["holes_completed"] == "36"
    readiness = assess_r2(
        reconciled, ["p1", "p2"],
        cut_known=module._derive_cut_known(reconciled, cut_boundary_published=True),
    )
    assert readiness.decision == "R2_COMPLETE"
    assert readiness.cut_players == 1


# ---------------------------------------------------------------------
# 9. R2 HOUSE reaches PUBLISH_AND_CLOSE using the REAL, committed R1
#    evidence artifact's own real population -- no hardcoded
#    player/count/score values. Every player_id/name/count below is
#    read live from NEO_KB_2026090003_R1_OFFICIAL_RESULT_EVIDENCE_V1.
#    json itself, never typed in as a literal.
# ---------------------------------------------------------------------

def test_9_r2_house_reaches_publish_and_close_from_real_r1_evidence_population(module):
    assert REAL_R1_EVIDENCE_PATH.is_file(), "real committed R1 evidence artifact must exist for this E2E proof"
    expected = load_expected_r2_field(REAL_R1_EVIDENCE_PATH)
    real_r1 = json.loads(REAL_R1_EVIDENCE_PATH.read_text(encoding="utf-8"))
    name_by_id = {str(p["playerCode"]): p["name"] for p in real_r1["players"]}
    assert set(name_by_id) == expected.player_ids  # sanity: same real population both ways

    # Synthetic-but-population-real R2 rows: every real expected
    # player_id, real name, each with a real full R2 round (18 own
    # holes) and ACTIVE status -- the only fabricated field is the
    # per-round holes_completed value itself (this test's job is to
    # prove the READINESS WIRING, not to claim real live R2 scores).
    rows = [
        {"player_id": pid, "player_name": name, "status": "ACTIVE", "holes_completed": "18"}
        for pid, name in name_by_id.items()
    ]
    reconciled = module._apply_r2_cumulative_completion(rows, expected_player_ids=expected.player_ids)
    assert len(reconciled) == len(expected.player_ids)
    assert all(r["holes_completed"] == "36" for r in reconciled)

    decision = decide_r2_cycle(
        reconciled, sorted(expected.player_ids),
        official_page_available=True,
        cut_known=True,
        freeze_exists=False,
    )
    assert decision.action == "PUBLISH_AND_CLOSE"
    assert decision.readiness.decision == "R2_COMPLETE"
    assert decision.readiness.cutmakers == len(expected.player_ids)
