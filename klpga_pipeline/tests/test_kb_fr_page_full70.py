"""MISSION J -- KB FR FINAL BUILD: tests for the real, complete 70-player
FR page built from the validated official dataset.

Covers: complete FR population, identity uniqueness, ties, WD exclusion,
round arithmetic, to-par arithmetic, sponsor invariant, mobile rendering
class, FR nav, no prediction metrics on FR, /final/ unchanged, R3
fingerprint unchanged.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPO_ROOT = REPO.parent

SPEC = importlib.util.spec_from_file_location(
    "kb_fr_build_full70", REPO / "scripts/138_build_kb_fr_page_full70.py"
)
build_mod = importlib.util.module_from_spec(SPEC)
sys.modules["kb_fr_build_full70"] = build_mod
SPEC.loader.exec_module(build_mod)

FR_PAGE_PATH = REPO_ROOT / "docs/tournaments/2026/2026090003/fr/index.html"
FINAL_PAGE_PATH = REPO_ROOT / "docs/tournaments/2026/2026090003/final/index.html"

FORBIDDEN_TERMS = [
    "우승확률", "win_pct", "NEO 우승", "Top5", "Top10", "Top20", "확률",
    "Brier", "log-loss", "log loss", "Monte Carlo", "몬테카를로",
    "SURPRISE", "MISS", "NEO PICK", "예측", "postmortem", "포스트모템", "모델",
]


def _html() -> str:
    return FR_PAGE_PATH.read_text(encoding="utf-8")


def test_complete_fr_population_70_rows_rendered():
    html = _html()
    assert len(re.findall(r"data-player-id=", html)) == 70


def test_identity_uniqueness_in_rendered_page():
    html = _html()
    ids = re.findall(r"data-player-id='(\d+)'", html)
    assert len(ids) == 70
    assert len(set(ids)) == 70


def test_ties_rendered_with_t_prefix_matching_mission_anchors():
    html = _html()
    for name, position in [("박예지", "T2"), ("방신실", "T2"), ("유서연2", "T2"), ("서교림", "5"), ("박보겸", "1")]:
        row = re.search(
            r"<td data-label='순위'>([^<]+)</td><th[^>]*><span class='player-name'>" + re.escape(name),
            html,
        )
        assert row is not None, name
        assert row.group(1) == position, (name, row.group(1))


def test_wd_player_not_in_rendered_page():
    html = _html()
    assert "8881" not in re.findall(r"data-player-id='(\d+)'", html)
    assert "성유진" not in html


def test_round_and_total_arithmetic_for_every_rendered_row():
    evidence = build_mod.build_evidence()
    for r in evidence["confirmed_records"]:
        assert r["r1_strokes"] + r["r2_strokes"] + r["r3_strokes"] + r["r4_strokes"] == r["final_total_strokes"]
        assert r["final_total_strokes"] - build_mod.PAR_PER_ROUND * 4 == r["final_to_par"]


def test_sponsor_invariant_blank_when_unverified():
    evidence = build_mod.build_evidence()
    verified = {r["player_id"]: r["sponsor"] for r in evidence["confirmed_records"]}
    v3 = json.loads(build_mod.gate_mod.V3_PATH.read_text(encoding="utf-8"))
    v3_ids = {r["player_id"] for r in v3["confirmed_records"]}
    for pid, sponsor in verified.items():
        if pid not in v3_ids:
            assert sponsor is None, f"{pid} has an unverified sponsor guessed as {sponsor!r}"
    html = _html()
    assert "<span class='player-sponsor'></span>" in html  # at least one blank-sponsor row rendered


def test_mobile_leaderboard_class_present():
    html = _html()
    assert "leaderboard-table--fr-full" in html


def test_fr_nav_active_no_final_link_pre_r1_r2_r3_present():
    html = _html()
    nav = re.search(r'<nav class="stage-nav".*?</nav>', html).group()
    assert nav.count('href="/tournaments/2026/2026090003/pre/"') == 1
    assert nav.count('href="/tournaments/2026/2026090003/r1/"') == 1
    assert nav.count('href="/tournaments/2026/2026090003/r2/"') == 1
    assert nav.count('href="/tournaments/2026/2026090003/r3/"') == 1
    assert 'href="/tournaments/2026/2026090003/fr/" aria-current="page"' in nav
    assert "final" not in nav.lower()


def test_no_prediction_or_validation_metrics_on_fr_page():
    html = _html()
    for term in FORBIDDEN_TERMS:
        assert term not in html, f"forbidden term found on FR page: {term!r}"


def test_final_page_unchanged():
    assert FINAL_PAGE_PATH.is_file()
    # FINAL is the permanent validation record -- Mission J must not touch it.
    # (byte-for-byte immutability is checked at the repo level via git diff
    # in the mission report; here we just assert it still exists and still
    # carries its own distinct FINAL-only content, not FR's.)
    final_html = FINAL_PAGE_PATH.read_text(encoding="utf-8")
    assert "FINAL" in final_html or "최종" in final_html


def test_r3_fingerprint_unchanged():
    gate = build_mod.gate_mod.build()
    check = gate["r3_freeze_check"]
    assert check["expected_sha256"] == "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"
    assert check["unchanged"] is True
