import json
import re
import hashlib
import subprocess
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
    for label in ["선수", "KLPGA K-RANKING", "NEO 경기력", "최근 5R SG"]:
        assert label in html
    # PRODUCT RECOVERY V1: the tournament outcome probability
    # distribution (CUT/TOP20/TOP10/TOP5/WIN) is withheld while
    # MODEL_VALIDATED_FOR_PUBLICATION is False -- WIN has no exception.
    for forbidden in ["SCORE", "THRU", "현재 라운드", "TOP20", "TOP10", "TOP5", "player_id", "VERY_HIGH", "INSUFFICIENT_EVIDENCE"]:
        assert forbidden not in html
    if not builder.MODEL_VALIDATED_FOR_PUBLICATION:
        assert "우승확률" not in html
        assert "SG Total" not in html
    assert "참가 120 ·" in html and "· PRE" in html
    assert "★★★★★" not in html and "★★★★☆" not in html and "★★★☆☆" not in html and "★★☆☆☆" not in html and "★☆☆☆☆" not in html
    assert "데이터 부족" in html
    assert "aria-label='NEO 경기력" in html
    assert html.count("NEO 경기력") >= 1
    assert len(re.findall(r"<span class='band'[^>]*>최상위</span>", html)) == 15
    assert len(re.findall(r"<span class='band'[^>]*>데이터 부족</span>", html)) == 3
    assert "NEO 경기력 구간" not in html


def test_manifest_points_to_canonical_master():
    out = builder.build()
    manifest = json.loads((out / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["entry_count"] == 120
    assert "source_master" not in manifest and "source_master_sha256" not in manifest
    evidence = json.loads(builder._CONTEXT.artifact_path("pre_website_build_evidence").read_text(encoding="utf-8"))
    assert evidence["source_master"] == "OK_OPEN_2026_PRE_PUBLIC_MASTER.json"
    assert len(evidence["source_master_sha256"]) == 64


def test_mobile_table_containment_contract():
    out = builder.build()
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert ".grid > *,.panel{min-width:0}" in css
    assert ".table-wrap{width:100%;max-width:100%;overflow-x:auto" in css


def test_about_and_center_alignment_contract():
    out = builder.build()
    about = (out / "about" / "index.html").read_text(encoding="utf-8")
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert "결과만으로는 보이지 않는 경기력을 데이터에서 봅니다." in about
    # PRODUCT RECOVERY V1 (design-system consolidation, phase 1): the
    # player identity cell now uses the shared player-name/player-sponsor
    # classes neo-site.css already styles -- this page's own separate
    # .player/.sponsor rule was removed, not just renamed.
    assert ".player-name,.player-sponsor{text-align:center}" in css
    assert ".player{display:block" not in css and ".sponsor{display:block" not in css


def test_info_control_is_interactive_in_generated_html():
    out = builder.build()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "class='info-control'" in html
    assert "aria-expanded='false'" in html
    assert "aria-controls='neo-info'" in html
    assert "role='tooltip'" in html
    assert "최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다." in html
    assert "addEventListener('click'" in html
    assert "지금의 경기력" not in html
    assert "지금 경기력" not in html


def test_mobile_popover_is_viewport_safe():
    out = builder.build()
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    # OWNER UI FIX (tooltip overflow): .info-popover is position:fixed
    # everywhere now (not absolute), with JS computing its left/top from
    # the trigger button on desktop; the mobile media query only needs
    # to pin it to a fixed on-screen banner with !important so it can
    # never be overridden by the JS-set inline left/top.
    assert ".info-popover{display:none;position:fixed" in css
    assert "@media(max-width:760px){.info-popover{left:16px!important;right:16px!important;top:112px!important" in css
    assert "max-width:none" in css


def test_neo_info_tooltip_never_participates_in_table_width():
    """OWNER QA: KB PRE screenshot showed the NEO 경기력 info tooltip
    breaking the table layout (extending across adjacent columns,
    overlapping SG Total, clipped/overlaid content). Regression coverage
    for the fix: the popover must be position:fixed (out of the table's
    box model and immune to .table-wrap's overflow-x/overflow-y
    clipping -- position:absolute was the root cause, since it needed a
    positioned ancestor this markup never reliably provided), have a
    viewport-clamped max-width, and wrap Korean text safely instead of
    overflowing its box."""
    out = builder.build()
    html = (out / "index.html").read_text(encoding="utf-8")
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")

    # structure: trigger button + popover, correctly associated for a11y
    assert "<th class='band-head'>NEO 경기력 <button type='button' class='info-control'" in html
    assert "aria-controls='neo-info'" in html
    assert "<span id='neo-info' class='info-popover' role='tooltip' tabindex='-1'>" in html

    # position:fixed, never absolute -- absolute was the overflow root cause
    assert ".info-popover{display:none;position:fixed" in css
    assert "position:absolute" not in css.split(".info-popover", 1)[1][:120]

    # viewport-clamped width + safe Korean wrapping, not a bare fixed max-width
    assert "max-width:min(260px,calc(100vw - 2rem))" in css
    assert "white-space:normal" in css and "overflow-wrap:break-word" in css and "word-break:keep-all" in css

    # ESC / outside-click close behavior preserved, plus new scroll/resize
    # close (fixed coordinates would otherwise drift from the button)
    script = html.rsplit("<script>", 1)[1]
    assert "e.key==='Escape'" in script
    assert "!b.contains(e.target)&&!p.contains(e.target)" in script
    assert "addEventListener('scroll',close,true)" in script
    assert "addEventListener('resize',close)" in script


def test_canonical_pre_route_and_stage_navigation_are_generated():
    out = builder.build()
    route = out / "tournaments" / "2026" / "ok-savings-bank-open" / "pre" / "index.html"
    assert route.exists()
    html = route.read_text(encoding="utf-8")
    for stage in ["PRE", "R1", "R2", "FINAL"]:
        assert stage in html
    assert "tournaments/2026/ok-savings-bank-open/pre/" in html
    assert "tournaments/2026/ok-savings-bank-open/r3/" not in html


def test_public_ui_contract_generated_route():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/pre/index.html").read_text(encoding="utf-8")
    assert html.count("<tr>") - 1 == 120
    assert "<th>선수</th>" in html
    assert "KLPGA K-RANKING" in html and "최근 5R SG" in html
    # PRODUCT RECOVERY V1: SG LABEL DECISION -- the NEO recent-5-round SG
    # metric must never render under an official-looking label, and the
    # probability distribution (WIN included) is withheld while blocked.
    assert "SG Total" not in html and "SG 전체" not in html and "KLPGA SG" not in html
    if not builder.MODEL_VALIDATED_FOR_PUBLICATION:
        assert "우승확률" not in html
    assert all(x not in html for x in ["VERY_HIGH", "HIGH", "TYPICAL", "LOW", "VERY_LOW", "INSUFFICIENT_EVIDENCE", "TOP20", "TOP10", "TOP5", "player_id"])
    assert sum(html.count(c) for c in "★☆") == 0
    assert len(re.findall(r"<span class='band'[^>]*>데이터 부족</span>", html)) == 3
    assert "평가 보류" not in html
    assert "지금의 경기력" not in html and "지금 경기력" not in html
    assert "최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다." in html
    assert ".player-name,.player-sponsor{text-align:center}" not in html  # style contract is in linked CSS
    assert "aria-label='NEO 경기력" in html


def test_all_54_hole_stage_routes_are_truthful_and_provenance_is_private():
    out = builder.build()
    root = out / "tournaments/2026/ok-savings-bank-open"
    for stage in ["pre", "r1", "r2", "final"]:
        page = root / stage / "index.html"
        assert page.exists()
        html = page.read_text(encoding="utf-8")
        assert "neo-public-master-sha256" not in html
        # FINAL has no real pipeline yet and must show the honest
        # "공식 데이터가 아직 없습니다" placeholder. PRE and R1 both have
        # real data (R1's page previously matched "아직" only by
        # coincidence, via now-removed probability-model help text --
        # P0 MODEL SAFETY PATCH -- so it is exempted explicitly here,
        # not by an accidental substring match).
        #
        # QA REMEDIATION (post-fbb69de): R2 is exempted too -- commits
        # db13746 ("R2 LIVE: publish OK Open factual stage") and
        # 1885e2c ("fix: publish verified R2 completed-hole progress")
        # gave stage=="r2" a real live pipeline
        # (_r2_live_leaderboard_section), same as R1's. Only FINAL still
        # has no live pipeline wired into build()'s route loop (its
        # stage body is always None there), so it alone still gets the
        # placeholder.
        assert "아직" in html or stage in ("pre", "r1", "r2")
    assert not (root / "r3").exists()
    manifest = json.loads((out / "data/manifest.json").read_text(encoding="utf-8"))
    assert "source_master_sha256" not in manifest
    evidence = json.loads(builder._CONTEXT.artifact_path("pre_website_build_evidence").read_text(encoding="utf-8"))
    expected = hashlib.sha256(builder.MASTER.read_bytes()).hexdigest()
    assert evidence["source_master_sha256"] == expected
    for stage in ["pre", "r1", "r2", "final"]:
        page = (root / stage / "index.html").read_text(encoding="utf-8")
        assert "neo-public-master-sha256" not in page


def test_stage_links_resolve_from_every_generated_stage_page():
    # v3 UI/UX rebuild (spec 9/10): a stage that has no real data yet must
    # never be a clickable link. Which stages currently qualify is read
    # from the same single source of truth every other page uses
    # (tournament_state.ok_open_available_stages()) -- PRE always
    # qualifies, and R1 now also qualifies because a real R1 active-cycle
    # has actually run and validated it (see OK_OPEN_STAGE_STATE.json).
    # R2/FINAL have no real data yet, so they still render disabled
    # (present as text, no href) on every stage page.
    from urllib.parse import urljoin

    from klpga.website_v2.tournament_state import ok_open_available_stages

    out = builder.build()
    root = out / "tournaments/2026/ok-savings-bank-open"
    real_stages = ok_open_available_stages()
    fake_stages = [s for s in ("pre", "r1", "r2", "final") if s not in real_stages]
    for stage in ["pre", "r1", "r2", "final"]:
        page_url = f"http://localhost/tournaments/2026/ok-savings-bank-open/{stage}/"
        html = (root / stage / "index.html").read_text(encoding="utf-8")
        for real in real_stages:
            href = f"/tournaments/2026/ok-savings-bank-open/{real}/"
            assert href in html
            assert urljoin(page_url, href).endswith(f"/{real}/")
        for target in fake_stages:
            href = f"/tournaments/2026/ok-savings-bank-open/{target}/"
            assert href not in html, f"{target} has no real data yet and must not be a clickable link on the {stage} page"
            assert 'class="stage-nav__disabled"' in html and target.upper() in html
        assert "/r3/" not in html
