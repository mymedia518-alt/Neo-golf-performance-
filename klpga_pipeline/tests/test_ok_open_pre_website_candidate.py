import json
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_candidate_uses_public_master_and_renders_contract(tmp_path):
    out = builder.build()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert html.count("<tr>") - 1 == 120
    for label in ["선수", "KLPGA K-RANKING", "NEO 경기력 ⓘ", "SG Total 순위", "우승확률"]:
        assert label in html
    for forbidden in ["SCORE", "THRU", "현재 라운드", "TOP20", "TOP10", "TOP5", "player_id", "VERY_HIGH", "INSUFFICIENT_EVIDENCE"]:
        assert forbidden not in html
    assert "K-RANKING은 누적 성과, NEO는 최근 경기력을 봅니다." in html
    assert "★★★★★" in html and "평가 보류" in html
    assert "aria-label='NEO 경기력" in html


def test_manifest_points_to_canonical_master():
    out = builder.build()
    manifest = json.loads((out / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_master"].endswith("OK_OPEN_2026_PRE_PUBLIC_MASTER.json")
    assert manifest["entry_count"] == 120


def test_mobile_table_containment_contract():
    out = builder.build()
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert ".grid > *,.panel{min-width:0}" in css
    assert ".table-wrap{width:100%;max-width:100%;overflow-x:auto" in css
