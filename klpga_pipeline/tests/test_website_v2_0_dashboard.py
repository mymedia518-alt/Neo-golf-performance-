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


def test_stage_routes_are_functional_and_graph_renders_real_points():
    html = mod.render_dashboard({"game_code":"x","name":"대회","start_date":"2026-01-01","end_date":"2026-01-03","venue":"코스","holes":54,"rounds":3,"format":"스트로크 플레이"}, [], {}, current_stage="R1")
    assert 'href="/r1/index.html"' in html
    assert 'href="/r2/index.html"' in html
    assert 'href="/final/index.html"' in html
    assert 'aria-current="page"' in html
    graph = mod.probability_graph([{"checkpoint":"PRE","probability":1.9},{"checkpoint":"R1","probability":3.2}])
    assert "probability-chart" in graph and "1.90%" in graph and "3.20%" in graph


def test_72_hole_routes_include_r3_but_never_r4():
    html = mod.render_dashboard({"game_code":"x","name":"대회","start_date":"2026-01-01","end_date":"2026-01-04","venue":"코스","holes":72,"rounds":4,"format":"스트로크 플레이"}, [], {})
    assert 'href="/r3/index.html"' in html
    assert "R4" not in html
