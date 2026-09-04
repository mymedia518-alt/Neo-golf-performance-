"""P0 MODEL SAFETY PATCH -- integration tests proving
scripts/94_promote_top120_to_production.py's promotion gate actually
calls into the model-publication checks and hard-stops a promotion,
exercising the REAL `_validate_model_publication_gate` function (never
a re-implementation). Fully isolated via monkeypatch on the module's
own function attributes -- never touches the real candidate/docs
trees."""
from pathlib import Path

import importlib.util

import pytest

SPEC = importlib.util.spec_from_file_location(
    "promoter_under_test", Path(__file__).parents[1] / "scripts" / "94_promote_top120_to_production.py"
)
promoter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(promoter)


def _r1_page(tmp_path: Path, text: str) -> None:
    page = tmp_path / "tournaments" / "2026" / "ok-savings-bank-open" / "r1" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"<html><body>{text}</body></html>", encoding="utf-8")


def _root_page(tmp_path: Path, text: str) -> None:
    (tmp_path / "index.html").write_text(f"<html><body>{text}</body></html>", encoding="utf-8")


def test_model_is_currently_not_validated_for_publication():
    assert promoter.MODEL_VALIDATED_FOR_PUBLICATION is False


def test_clean_r1_page_passes_while_model_blocked(tmp_path, monkeypatch):
    _r1_page(tmp_path, "순위/선수/현재스코어만 있는 정상 페이지")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("pre", "/x/"))
    promoter._validate_model_publication_gate(tmp_path, "t")


def test_r1_page_with_blocked_win_pct_header_hard_stops_promotion(tmp_path, monkeypatch):
    _r1_page(tmp_path, "<th>Win%</th>")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("pre", "/x/"))
    with pytest.raises(promoter.PromotionError, match="Win%"):
        promoter._validate_model_publication_gate(tmp_path, "t")


def test_r1_page_with_neo_movers_section_hard_stops_promotion(tmp_path, monkeypatch):
    _r1_page(tmp_path, "<h2>NEO Movers · PRE 대비 변화</h2>")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("pre", "/x/"))
    with pytest.raises(promoter.PromotionError):
        promoter._validate_model_publication_gate(tmp_path, "t")


def test_root_page_is_also_checked_when_it_is_the_r1_stage_page(tmp_path, monkeypatch):
    _r1_page(tmp_path, "clean")
    _root_page(tmp_path, "<th>Cut%</th>")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("r1", "/x/"))
    with pytest.raises(promoter.PromotionError, match="Cut%"):
        promoter._validate_model_publication_gate(tmp_path, "t")


def test_root_page_is_not_checked_when_root_is_not_the_r1_stage_page(tmp_path, monkeypatch):
    # Root is some other page (e.g. the ranking page) -- a blocked
    # marker there is irrelevant to this gate's concern and must not
    # trip it.
    _r1_page(tmp_path, "clean")
    _root_page(tmp_path, "<th>Cut%</th>")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("pre", "/x/"))
    promoter._validate_model_publication_gate(tmp_path, "t")


def test_missing_r1_page_is_a_noop():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        promoter._validate_model_publication_gate(Path(d), "t")
