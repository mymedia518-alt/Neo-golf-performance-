"""2026-10-07 UI cleanup (operator instruction: "HOME/PRE Stableford
설명 통일"). HOME (build_tournament_archive_and_hj_scaffold.py) and PRE
(scripts/225) each keep their own literal markup (different quote
convention per file, same as the rest of this codebase), but the
READER-FACING TEXT of the fixture-notice explanation must be identical,
word for word, on both pages."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HOME_SCRIPT = Path(__file__).parent.parent / "scripts" / "build_tournament_archive_and_hj_scaffold.py"
PRE_SCRIPT = Path(__file__).parent.parent / "scripts" / "225_build_hj_2026100004_pre_page.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_notice_text(html: str) -> str:
    m = re.search(r'<div class=.fixture-notice.>(.*?)</div>', html, re.DOTALL)
    assert m, "fixture-notice block not found"
    inner = m.group(1)
    text = re.sub(r"<[^>]+>", " ", inner)
    return re.sub(r"\s+", " ", text).strip()


def test_home_and_pre_stableford_explanation_text_is_identical():
    home = _load(HOME_SCRIPT, "archive_hj_home_consistency")
    pre = _load(PRE_SCRIPT, "pre_225_consistency")
    home_text = _fixture_notice_text(home.build_home())
    pre_text = _fixture_notice_text(pre.build()["html"])
    assert home_text == pre_text


def test_explanation_text_has_the_three_required_sentences_in_order():
    home = _load(HOME_SCRIPT, "archive_hj_home_consistency2")
    text = _fixture_notice_text(home.build_home())
    i1 = text.find("이번 대회는 변형 스테이블포드 방식으로 진행됩니다.")
    i2 = text.find("알바트로스 +8")
    i3 = text.find("NEO는 선수들의 대회 전 기록을")
    assert i1 != -1 and i2 != -1 and i3 != -1
    assert i1 < i2 < i3
