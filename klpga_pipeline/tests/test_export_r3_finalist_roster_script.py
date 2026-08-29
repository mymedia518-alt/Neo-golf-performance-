"""Tests for scripts/55_export_r3_finalist_roster.py's extract_roster
function against synthetic Player-Journey-trigger-row HTML fragments
(the real docs/index.html markup this project already produced and
validated 62/62 for the Player Journey feature)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "55_export_r3_finalist_roster.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("export_r3_finalist_roster", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_r3_finalist_roster"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def script():
    return _load_script()


def _trigger_row(code: str, name: str) -> str:
    return f'<tr data-player-journey-trigger data-player-code="{code}" data-player-name="{name}"></tr>'


def test_extract_roster_basic(script):
    html = f"<table><tbody>{_trigger_row('1001', '가')}{_trigger_row('1002', '나')}</tbody></table>"
    roster = script.extract_roster(html)
    assert roster == [("1001", "가"), ("1002", "나")]


def test_extract_roster_rejects_duplicate_player_code(script):
    html = f"<table><tbody>{_trigger_row('1001', '가')}{_trigger_row('1001', '나')}</tbody></table>"
    with pytest.raises(ValueError):
        script.extract_roster(html)


def test_extract_roster_rejects_duplicate_player_name(script):
    html = f"<table><tbody>{_trigger_row('1001', '가')}{_trigger_row('1002', '가')}</tbody></table>"
    with pytest.raises(ValueError):
        script.extract_roster(html)


def test_extract_roster_rejects_missing_attributes(script):
    html = "<table><tbody><tr data-player-journey-trigger data-player-code=\"1001\"></tr></tbody></table>"
    with pytest.raises(ValueError):
        script.extract_roster(html)


def test_real_committed_homepage_yields_exactly_62_unique_finalists(script):
    """Guards against a silent regression in the real production page
    this collector's roster depends on."""
    site_html = script.SITE_HTML_PATH.read_text(encoding="utf-8")
    roster = script.extract_roster(site_html)
    assert len(roster) == 62
    assert len({code for code, _ in roster}) == 62
    assert len({name for _, name in roster}) == 62
