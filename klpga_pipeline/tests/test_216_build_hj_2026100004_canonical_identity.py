"""Tests for scripts/216_build_hj_2026100004_canonical_identity.py --
reshapes the real RECONCILIATION_REPORT.json (commit 9d40b92) into the
homepage-ready canonical identity file. Pure reshaping, no new
acquisition -- these tests run against the real committed evidence."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "216_build_hj_2026100004_canonical_identity.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("canonical_216", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["canonical_216"] = module
    spec.loader.exec_module(module)
    return module


def test_build_covers_every_real_entrant_with_no_drops():
    mod = _load_module()
    data = mod.build()
    assert data["field_size_confirmed"] == 108
    assert data["entry_count"] == 108
    assert len(data["records"]) == 108


def test_new_players_and_overseas_players_match_known_real_values():
    mod = _load_module()
    data = mod.build()
    assert set(data["new_players_not_in_any_existing_master"]) == {"11426", "10821", "12472"}
    assert set(data["overseas_players"]) == {"10789", "1485", "11770"}


def test_sponsor_never_none_empty_string_means_confirmed_no_sponsor():
    mod = _load_module()
    data = mod.build()
    for r in data["records"]:
        assert r["official_sponsor"] is not None
    sponsored = [r for r in data["records"] if r["official_sponsor"]]
    unsponsored = [r for r in data["records"] if r["official_sponsor"] == ""]
    assert len(sponsored) == 90
    assert len(unsponsored) == 18


def test_every_record_has_a_real_nationality_or_explicit_none():
    mod = _load_module()
    data = mod.build()
    for r in data["records"]:
        assert "nationality" in r
    overseas = [r for r in data["records"] if r["nationality"] and r["nationality"] != "KOR"]
    assert len(overseas) == 3
