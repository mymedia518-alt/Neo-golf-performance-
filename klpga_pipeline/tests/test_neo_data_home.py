from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from klpga.website_v2.home_ranking import FORMULA_STATE, build_features, join_home_rows, validate_population

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home"


def _load_builder():
    path = ROOT / "scripts" / "86_build_neo_data_home_candidate.py"
    spec = importlib.util.spec_from_file_location("home_candidate_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built():
    return _load_builder().build()


def _json(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def test_home_population_is_canonical_and_not_a_tournament_population():
    population = _json("HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    records = validate_population(population)
    ids = [row["player_id"] for row in records]
    assert len(records) == population["player_count"] == 546
    assert len(ids) == len(set(ids))
    assert len(records) not in {62, 120}
    assert population["population_kind"] != "tournament_entry"
    assert "current" not in population["population_definition"].lower()


def test_player_identity_join_is_player_id_only_and_k_ranking_has_provenance():
    population = _json("HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    ranking = _json("OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json")
    rows, summary = join_home_rows(population, ranking, {"records": []})
    assert summary["k_ranking_join_success"] == 119
    assert summary["k_ranking_join_failure"] == 427
    assert ranking["official_source"].startswith("https://k-rankings.klpga.co.kr/")
    assert all(row["k_ranking_source"] == ranking["official_source"] for row in rows)


def test_neo_ranking_is_blocked_and_cannot_expose_tournament_probability():
    source = (ROOT / "src" / "klpga" / "website_v2" / "home_ranking.py").read_text(encoding="utf-8")
    rows, summary = join_home_rows(_json("HOME_REGULAR_TOUR_PLAYER_MASTER.json"), _json("OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"), {"records": []})
    assert "win_probability" not in source
    assert FORMULA_STATE == "BLOCKED_FORMULA_NOT_APPROVED"
    assert summary["neo_ranking_published"] == 0
    assert all(row["neo_rank"] is None and row["neo_ranking_state"] == FORMULA_STATE for row in rows)


def test_corrected_sg_features_use_event_samples_and_have_provenance():
    warehouse = {"records": [
        {"player_id": "1", "game_code": "E1", "season": 2026, "rounds": 1, "total": 1.0, "identity_state": "RETAINED"},
        {"player_id": "1", "game_code": "E1", "season": 2026, "rounds": 4, "total": 2.0, "identity_state": "RETAINED"},
        {"player_id": "1", "game_code": "E2", "season": 2026, "rounds": 4, "total": -1.0, "identity_state": "RETAINED"},
    ]}
    feature = build_features(warehouse)["1"]
    assert feature["sample_count"] == 2
    assert feature["recent_5_sg"] == 0.5
    assert feature["source_artifact"] == "historical_sg_warehouse_corrected.json"
    assert feature["validation_state"].startswith("PASS")


def test_generated_home_contract_and_navigation(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert all(f'>{label}<' in html for label in ("HOME", "TOURNAMENTS", "DEEP DIVE", "ABOUT"))
    assert "검증 선수 046" not in html
    assert "win_probability" not in html
    assert html.count("data-player-row") == 546
    assert 'data-public-number data-validation-state="PASS"' in html
    assert built["neo_ranking_published"] == 0


def test_public_numbers_have_validation_state(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    public_number_tags = [part.split(">", 1)[0] for part in html.split("data-public-number")[1:]]
    assert public_number_tags
    assert all("data-validation-state=" in tag for tag in public_number_tags)


def test_candidate_preserves_major_routes(built):
    required = (
        "tournaments/2026/kg-ladies-open/r1/index.html",
        "tournaments/2026/kg-ladies-open/r2/index.html",
        "tournaments/2026/ok-savings-bank-open/pre/index.html",
        "tournaments/2026/ok-savings-bank-open/r1/index.html",
        "tournaments/2026/ok-savings-bank-open/r2/index.html",
        "tournaments/2026/ok-savings-bank-open/final/index.html",
        "deep-dive/index.html",
        "about/index.html",
        "assets/neo-site.css",
        "assets/neo-site.js",
        "assets/neo.css",
        "assets/home.js",
    )
    assert all((OUTPUT / path).is_file() for path in required)


def test_deep_dive_preserves_existing_real_content_and_is_not_stub(built):
    html = (OUTPUT / "deep-dive" / "index.html").read_text(encoding="utf-8")
    source = (ROOT / "candidate" / "website-v2" / "deep-dive" / "index.html").read_text(encoding="utf-8")
    assert html == source
    assert len(html) > 1000
    assert "data-chart-series" in html and "/assets/neo-site.js" in html
