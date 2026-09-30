"""Tests for 190_build_hitejinro_pre_page.py's M4 publication wiring
(added 2026-09-30): _load_m4_by_id() reads scripts/193's own output
(HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1.json) and the row loop
renders real cut/top20/top10/top5/win percentages only for a
playerCode whose record has analysis_status=='PASS' -- otherwise it
must reproduce the pre-2026-09-30 behavior exactly (데이터 부족 for
every player), never crash on a missing file."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "190_build_hitejinro_pre_page.py"


def _load_module():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location("hitejinro_pre_page_190", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def test_pct_formats_as_one_decimal_percentage(module):
    assert module._pct(0.9998930114477839) == "100.0%"
    assert module._pct(0.031) == "3.1%"
    assert module._pct(0.0) == "0.0%"


def test_load_m4_by_id_returns_empty_when_file_absent(module, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "M4_CANDIDATE_PATH", tmp_path / "does_not_exist.json")
    assert module._load_m4_by_id() == {}


def test_load_m4_by_id_returns_only_pass_records_keyed_by_player_code(module, tmp_path, monkeypatch):
    doc = {
        "gameCode": module.GAME_CODE,
        "records": [
            {"playerCode": "9174", "analysis_status": "PASS", "win_probability": 0.05, "cut_probability": 0.9,
             "top5_probability": 0.1, "top10_probability": 0.2, "top20_probability": 0.3},
            {"playerCode": "10112", "analysis_status": "DATA_INSUFFICIENT", "win_probability": 0.0},
        ],
    }
    m4_path = tmp_path / "m4.json"
    m4_path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(module, "M4_CANDIDATE_PATH", m4_path)

    result = module._load_m4_by_id()
    assert set(result.keys()) == {"9174"}
    assert result["9174"]["win_probability"] == 0.05


def test_load_m4_by_id_rejects_a_file_for_a_different_game_code(module, tmp_path, monkeypatch):
    """Defensive: never accept a stale/mismatched M4 file just because
    it happens to exist at the expected path."""
    doc = {
        "gameCode": "2026090002",  # Hana, not this tournament
        "records": [{"playerCode": "9174", "analysis_status": "PASS", "win_probability": 0.5}],
    }
    m4_path = tmp_path / "m4.json"
    m4_path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(module, "M4_CANDIDATE_PATH", m4_path)

    assert module._load_m4_by_id() == {}


def test_load_m4_by_id_matches_the_real_193_output_schema(module, tmp_path, monkeypatch):
    """Real shape scripts/193_build_hitejinro_pre_m4.py's own build()
    actually emits (field names, nesting) -- not a simplified guess."""
    doc = {
        "schema_version": "HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1",
        "gameCode": "2026100005",
        "stage": "PRE",
        "records": [
            {
                "playerCode": "9174", "playerName": "강가율", "analysis_status": "PASS",
                "data_status": "검증 가능", "cut_probability": 0.9999999999699356,
                "top5_probability": 1.0, "top10_probability": 1.0, "top20_probability": 1.0,
                "win_probability": 0.9998930114477839,
            },
        ],
    }
    m4_path = tmp_path / "m4.json"
    m4_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "M4_CANDIDATE_PATH", m4_path)

    result = module._load_m4_by_id()
    row = result["9174"]
    assert module._pct(row["win_probability"]) == "100.0%"
    assert module._pct(row["cut_probability"]) == "100.0%"
