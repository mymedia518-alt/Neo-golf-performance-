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
def test_r2_cut_is_always_traceable_to_a_score_boundary_verified_field_list():
    """Bug class this guards: a real R2_CUT population appearing with
    no real, checkable provenance behind it -- silently hand-edited,
    or derived by some other (e.g. Set Difference against R3 RESULTS,
    explicitly rejected 2026-10-02) method. 2026-10-03: this
    tournament's real 41 R2_CUT records ARE legitimate (derived from a
    real confirmed R3 field list via hitejinro_round_pipeline.
    derive_r2_cut_from_confirmed_r3_field, which refuses to run at all
    if the field's own score boundary isn't clean -- see
    test_derive_r2_cut_refuses_a_split_tie_group below for that
    safety check's own regression guard) -- so this test only requires
    that whenever a real R2_CUT record exists, the board's own
    r2_cut_derivation metadata names that real method, never silence
    or a different one."""
    from klpga.tournament_context import CONTENT_DIR

    board = json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    r2_cut = [r for r in board["records"] if r["status"] == "R2_CUT"]
    if not r2_cut:
        pytest.skip("no real R2_CUT records in this checkout yet")
    derivation = board.get("r2_cut_derivation")
    assert derivation is not None, "real R2_CUT records exist but board carries no r2_cut_derivation provenance"
    assert derivation["method"].startswith("confirmed_r3_field_list"), (
        f"R2_CUT must be derived from a confirmed field list, never Set Difference against results: {derivation['method']!r}"
    )
    assert derivation["r2_cut_count"] == len(r2_cut)


def test_derive_r2_cut_refuses_a_split_tie_group():
    """Regression guard for derive_r2_cut_from_confirmed_r3_field's own
    safety check: a confirmed-field capture that splits a tied
    score_to_par group across present/absent is the signature of an
    arbitrary technical truncation (e.g. a partial AJAX load cutting a
    tie group in half), not a real score-based cut -- the function
    must refuse (raise), never silently derive R2_CUT from it. Proven
    with a synthetic board + synthetic field HTML, not real data (this
    exact failure mode has never occurred in this tournament's real
    evidence -- see the test above for the real, clean case)."""
    import tempfile
    from pathlib import Path as _Path
    from klpga.neo_win import hitejinro_round_pipeline as rp

    synthetic_board = {
        "schema_version": "hitejinro_round_leaderboard_v2", "game_code": "2026100005", "final_round": 2,
        "records": [
            {"player_id": "1", "player_name": "A", "status": None, "score_to_par": 5, "finish_position": "1", "finish_position_numeric": 1},
            {"player_id": "2", "player_name": "B", "status": None, "score_to_par": 5, "finish_position": "1", "finish_position_numeric": 1},
            {"player_id": "3", "player_name": "C", "status": None, "score_to_par": 6, "finish_position": "3", "finish_position_numeric": 3},
        ],
    }
    # Synthetic R3 field HTML: player 1 present, player 2 (same tied
    # score_to_par==5 as player 1) absent -- a split tie group.
    synthetic_field_html = (
        '<li id="favoritItem_1" data-rank="1" data-name="A" data-totunderpar="5" data-inghole="1" '
        'data-todayunderpar="0" data-score="" data-round1score="70" data-round2score="75" '
        'data-round3score="0" data-round4score="" data-updown="0">'
    )
    with tempfile.TemporaryDirectory() as td:
        tmp = _Path(td)
        board_path = tmp / "LEADERBOARD.json"
        board_path.write_text(json.dumps(synthetic_board), encoding="utf-8")
        field_path = tmp / "field.html"
        field_path.write_text(synthetic_field_html, encoding="utf-8")

        original_path = rp.LEADERBOARD_PATH
        rp.LEADERBOARD_PATH = board_path
        try:
            with pytest.raises(AssertionError, match="splits a tied score_to_par group"):
                rp.derive_r2_cut_from_confirmed_r3_field(raw_path=field_path)
        finally:
            rp.LEADERBOARD_PATH = original_path


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
    </main> must be byte-identical to whichever stage page is actually
    current (docs/index.html mirrors docs/.../{stage}/index.html
    verbatim, per scripts/192_promote_hitejinro_home.py's own real
    mechanism). 2026-10-03: generalized off a hardcoded "R2" check --
    the current stage advanced to R3 the same day, and this guard must
    keep working for whichever stage is real next, never silently
    skip forever once R2 stops being current."""
    import re as _re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    home_path = repo_root / "docs" / "index.html"
    if not home_path.is_file():
        pytest.skip("docs/index.html isn't built in this checkout")
    home_html = home_path.read_text(encoding="utf-8")

    def _main(html: str) -> str:
        assert "<main>" in html and "</main>" in html
        return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"

    # The real current stage is whichever stage-nav tab HOME's mirrored
    # <main> itself marks aria-current (PRE/R1/R2/R3/FR) -- read from
    # HOME's own content, never assumed.
    m = _re.search(r"aria-current='page'>([A-Z0-9]+)</a>", home_html)
    if m is None:
        pytest.skip("HOME's mirrored <main> carries no stage-nav aria-current marker in this checkout")
    stage_key = {"PRE": "pre", "R1": "r1", "R2": "r2", "R3": "r3", "FR": "fr"}.get(m.group(1))
    assert stage_key is not None, f"unrecognized stage-nav label {m.group(1)!r}"
    stage_path = repo_root / "docs" / "tournaments" / "2026" / "2026100005" / stage_key / "index.html"
    if not stage_path.is_file():
        pytest.skip(f"the real {stage_key} page isn't built in this checkout")
    stage_html = stage_path.read_text(encoding="utf-8")
    assert _main(home_html) == _main(stage_html), f"HOME's <main> has drifted from the real current stage ({stage_key}) page's <main>"


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


_R3_LEADERBOARD_PRESENT = raw_evidence_path(3, "LEADERBOARD").is_file()
requires_r3_leaderboard_evidence = pytest.mark.skipif(
    not _R3_LEADERBOARD_PRESENT, reason="real completed R3 leaderboard raw evidence not present in this checkout",
)


@requires_r3_leaderboard_evidence
def test_r3_neo_verification_numbers_are_internally_consistent():
    """Bug class this guards: the NEO 검증 section (2026-10-03 mission
    -- "예측을 공개하고 실제 결과로 검증한다") silently drifting out of
    arithmetic self-consistency (e.g. accuracy_pct not matching
    correct/total, a topN hit count exceeding N) -- every number here
    must be real and internally coherent, not just present."""
    from klpga.neo_win.hitejinro_round_pipeline import build_r3_neo_verification

    v = build_r3_neo_verification()
    cp = v["cut_prediction"]
    assert 0 <= cp["correct"] <= cp["total"]
    assert cp["accuracy_pct"] == round(100 * cp["correct"] / cp["total"], 1)

    for n, d in v["topn_hitrates"].items():
        assert d["total"] == n
        assert 0 <= d["hit"] <= n
        assert len(d["real"]) == n
        assert d["hit"] == len(set(d["real"]) & set(d["predicted"]))

    assert len(v["risers"]) <= 5
    assert len(v["fallers"]) <= 5
    # risers sorted descending by change, fallers ascending (most negative first)
    assert [c["change"] for c in v["risers"]] == sorted((c["change"] for c in v["risers"]), reverse=True)
    assert [c["change"] for c in v["fallers"]] == sorted((c["change"] for c in v["fallers"]))


@requires_r3_leaderboard_evidence
def test_r2_cut_players_never_appear_on_the_r3_page():
    """Bug class this guards: explicit operator instruction (2026-10-03)
    "R2_CUT 선수는 R3 페이지에 표시하지 않는다" -- unlike R1_CUT/WD,
    which still fall back into R3's flat list with a status cell,
    R2_CUT players must be entirely absent from the R3 page's player
    list. Checked by real name, not just a count, since a count alone
    could hide the wrong players being excluded."""
    import json as _json
    from klpga.neo_win.hitejinro_round_page import render_round_page
    from klpga.tournament_context import CONTENT_DIR

    board = _json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    r2_cut_names = [r["player_name"] for r in board["records"] if r["status"] == "R2_CUT"]
    assert r2_cut_names, "no real R2_CUT players found -- evidence may have changed, re-verify by hand"

    html = render_round_page(
        3, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    for name in r2_cut_names:
        assert name not in html, f"R2_CUT player {name!r} must not appear on the R3 page"
