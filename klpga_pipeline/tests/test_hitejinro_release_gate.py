"""2026-10-02 'RELEASE GATE' mission: every bug a human found and fixed
by hand in this tournament (game_code 2026100005) this session,
converted into a permanent automated check. These are the checks NOT
already covered by test_hitejinro_cut_status_model.py / test_hitejinro_
round_pipeline.py -- see scripts/hitejinro_release_gate.py for the full
checklist (this file + those two + a Playwright pass + a mandatory LIVE
confirmation). A future tournament's own equivalent pipeline should
copy this file's pattern, not this file itself (per this project's own
"never share a builder ACROSS tournaments" convention)."""
from __future__ import annotations

import json
import re

import pytest

from klpga.neo_win import hitejinro_round_pipeline as _rp
from klpga.neo_win.hitejinro_round_pipeline import raw_evidence_path

pytestmark = pytest.mark.round_pipeline

_R2_LEADERBOARD_PRESENT = raw_evidence_path(2, "LEADERBOARD").is_file()
requires_r2_leaderboard_evidence = pytest.mark.skipif(
    not _R2_LEADERBOARD_PRESENT, reason="real R2 leaderboard raw evidence not present in this checkout",
)


@requires_r2_leaderboard_evidence
def test_r1_cut_threshold_is_grounded_in_real_course_par():
    """Bug class this guards: a cut rule silently drifting from the
    real course without anyone re-deriving it by hand. The real R1_CUT
    threshold (88 strokes) must equal this course's own real 18-hole
    par (West 36 + East 36, from course_layout.json) + 16 -- the exact
    math that originally proved this tournament's cut is R1-only, never
    a 36-hole cumulative cut."""
    from klpga.tournament_context import CONTENT_DIR

    course = json.loads(
        (CONTENT_DIR / "knowledge_engine" / "course" / "blue_heron" / "course_layout.json").read_text(encoding="utf-8")
    )
    par18 = course["courses"]["West"]["par"] + course["courses"]["East"]["par"]
    assert par18 == 72

    board = json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    cut_r1_scores = {r["r1_score"] for r in board["records"] if r["status"] == "R1_CUT"}
    assert cut_r1_scores, "no real R1_CUT players found -- evidence may have changed, re-verify by hand"
    for score in cut_r1_scores:
        assert score == par18 + 16, f"R1_CUT player's r1_score {score} != course par({par18}) + 16"


@requires_r2_leaderboard_evidence
def test_no_silent_36_hole_cumulative_cut():
    """Bug class this guards: silently introducing a second, 36-hole-
    style cut (like Hana's real, different rule) without new evidence
    ever proving one exists for THIS tournament. While this board's
    final_round is still 2, zero real R2_CUT records must exist --
    R2_CUT can only ever be produced once round-3 evidence is parsed
    (hitejinro_round_pipeline._status_state's own round_number gate)."""
    from klpga.tournament_context import CONTENT_DIR

    board = json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    if board["final_round"] != 2:
        pytest.skip("final_round has advanced past 2 -- this guard is R2-state-specific")
    r2_cut = [r for r in board["records"] if r["status"] == "R2_CUT"]
    assert r2_cut == [], f"unexpected R2_CUT record(s) while final_round==2: {r2_cut}"


def test_set_difference_inference_never_comes_back():
    """Bug class this guards: re-introducing R3-participant-Set-
    Difference as a way to infer CUT status (explicitly rejected,
    2026-10-02 -- real incident: a partial R3 capture, 61 of 102 real
    active players, would have silently mislabeled 41 real competing
    players as cut). This module must never again expose any of these
    names -- their mere existence (not even being called) is the
    regression this guards against."""
    removed_names = (
        "parse_cut_by_set_difference", "validate_round_html_completeness",
        "PartialHTMLError", "_player_ranks_from_leaderboard_html", "_lazy_load_detected",
    )
    for name in removed_names:
        assert not hasattr(_rp, name), f"{name} must stay removed -- Set Difference inference is permanently rejected"


@requires_r2_leaderboard_evidence
def test_home_mirrors_the_current_stage_page_exactly():
    """Bug class this guards: HOME silently drifting out of sync with
    the real current-stage page (confirmed this session via byte-
    identical rebuilds after every mission) -- HOME's own <main>...
    </main> must be byte-identical to the real current stage page's
    (docs/index.html mirrors docs/.../r2/index.html verbatim, per
    scripts/192_promote_hitejinro_home.py's own real mechanism)."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    home_path = repo_root / "docs" / "index.html"
    r2_path = repo_root / "docs" / "tournaments" / "2026" / "2026100005" / "r2" / "index.html"
    if not (home_path.is_file() and r2_path.is_file()):
        pytest.skip("docs/index.html or the real R2 page isn't built in this checkout")

    def _main(html: str) -> str:
        assert "<main>" in html and "</main>" in html
        return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"

    home_html = home_path.read_text(encoding="utf-8")
    r2_html = r2_path.read_text(encoding="utf-8")
    # HOME is only a mirror of R2 while R2 genuinely is the current
    # stage (confirmed via the real nav: R2 marked aria-current).
    if "aria-current='page'>R2</a>" not in home_html:
        pytest.skip("R2 is not the current stage mirrored onto HOME in this checkout")
    assert _main(home_html) == _main(r2_html), "HOME's <main> has drifted from the real current stage page's <main>"


def test_css_wrap_fix_rule_is_present():
    """Bug class this guards: a real screen showed R1/R2/R3/FR scores
    like "70" rendering as "7"/"0" stacked on separate lines (CSS
    specificity bug, .leaderboard-table tbody td's white-space:normal
    outranking .data td's own nowrap). The fix rule must stay present
    in the real stylesheet, and the real table markup must keep
    opting into it."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    css_path = repo_root / "docs" / "assets" / "neo.css"
    if not css_path.is_file():
        pytest.skip("docs/assets/neo.css isn't present in this checkout")
    css = css_path.read_text(encoding="utf-8")
    assert ".leaderboard-table.leaderboard-table--hitejinro tbody td{white-space:nowrap}" in css

    r2_path = repo_root / "docs" / "tournaments" / "2026" / "2026100005" / "r2" / "index.html"
    if r2_path.is_file():
        assert "leaderboard-table leaderboard-table--hitejinro" in r2_path.read_text(encoding="utf-8")


@requires_r2_leaderboard_evidence
def test_r2_컷_통과_label_never_reappears_without_real_evidence():
    """Bug class this guards: labeling the active-player group with any
    claim ("컷 통과"/"본선 진출"/etc.) that no real KLPGA page has ever
    been shown to display (2026-10-02 'EVIDENCE INSUFFICIENT' finding,
    exhaustive DOM/class/style/JS/AJAX/JSON search). status=None must
    render as a plain ranked list with no group label until real R3
    evidence changes this."""
    from klpga.neo_win.hitejinro_round_page import render_round_page
    from klpga.tournament_context import CONTENT_DIR

    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    for forbidden in ("R2 컷 통과", "컷 통과 ", "본선 진출"):
        assert forbidden not in html, f"unsubstantiated label {forbidden!r} must not appear on the R2 page"
