"""R2 HOUSE red-team P1: scripts/112_kb_r2_active_cycle.py stays KB's
own, deliberately separate canonical R2 operator.

Regression test for a real defect found and reverted during this same
session: pointing script 112 at load_tournament_context() with no
argument (the generic "active tournament" resolver scripts 96/99 use,
which resolves config/active_tournament.json -- OK Open's own R1/R2
live-polling lineage, a completely separate identity system from KB's)
silently made the script evaluate whatever tournament active_tournament
.json happens to name instead of KB, while still presenting itself
(module docstring, filename) as KB's operator. This test locks in the
correct, deliberate choice: GAME_CODE is hardcoded, never derived from
the active-tournament resolver.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_operator_game_code_is_hardcoded_to_kb_not_derived_from_active_tournament():
    module = _load_operator_module()
    assert module.GAME_CODE == "2026090003"
    assert module._CONTEXT.game_code == "2026090003"


def test_operator_dry_run_reports_wait_state_never_fabricated_ready():
    module = _load_operator_module()
    result = module.run_cycle(live=False, build_id="TEST_OPERATOR_BUILD")
    assert result["REAL_R2"] == "WAIT"
    assert result["R2_PUBLICATION_READY"] is False
    assert result["action"] in ("SKIP_WAIT", "HARD_STOP")


def test_active_tournament_json_is_a_different_tournament_than_kb():
    """Documents WHY genericizing would have been wrong -- confirms the
    real config file this repo ships names a different game_code than
    KB's, so a generic resolver really would silently redirect."""
    active_path = SCRIPTS_DIR.parent / "config" / "active_tournament.json"
    if not active_path.is_file():
        return  # nothing to compare against in this environment -- not this test's concern
    active = json.loads(active_path.read_text(encoding="utf-8"))
    assert str(active.get("game_code")) != "2026090003"


def test_module_docstring_documents_kb_scope_and_hardcoding_rationale():
    module = _load_operator_module()
    doc = module.__doc__
    assert "KB" in doc
    assert "canonical" in doc.lower()
