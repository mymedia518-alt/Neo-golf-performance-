import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "68_build_website_2_0_candidate.py"
spec = importlib.util.spec_from_file_location("website20", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_stage_tabs_follow_official_format_without_r4():
    assert mod.stage_labels(3) == ["대회", "R1", "R2", "FINAL"]
    assert mod.stage_labels(4) == ["대회", "R1", "R2", "R3", "FINAL"]
    assert "R4" not in mod.stage_labels(3) + mod.stage_labels(4)


def test_dashboard_has_rank_value_modes_and_null_sg():
    html = mod.render_dashboard({"game_code":"x","name":"대회","start_date":"2026-01-01","end_date":"2026-01-03","venue":"코스","holes":54,"rounds":3,"format":"스트로크 플레이"}, [{"player_id":"p1","canonical_name":"선수"}], {"p1":{"windows":{"recent5":{"components":{},"event_count":0}}}})
    assert 'data-player-id="p1"' in html
    assert "RANKS" in html and "VALUES" in html
    assert 'class="pending">—' in html
    assert "FINAL" in html and "R4" not in html


def test_dashboard_has_frozen_checkpoint_contract_and_mobile_css():
    html = mod.render_dashboard({"game_code":"x","name":"대회","start_date":"2026-01-01","end_date":"2026-01-03","venue":"코스","holes":54,"rounds":3,"format":"스트로크 플레이"}, [], {})
    css = (ROOT / "candidate" / "website-v2-0" / "assets" / "dashboard.css").read_text(encoding="utf-8")
    assert 'probability_checkpoints' in html and "예측 체크포인트 없음" in html
    assert "overflow-x:auto" in css and "white-space:nowrap" in css and "44px" in css
