"""Regression for the 2026-10-02 data-model mission: R1_CUT and R2_CUT
must be separate real states, never collapsed into one undifferentiated
"CUT"/missed_cut boolean. Exercises real R1+R2 evidence already
committed under content/website_v2/incoming_evidence/2026100005/ --
never a synthetic fixture (this project's established convention).

Also covers the same-day follow-up "실제 운영 적용" mission: hitejinro_
round_page.py's display logic (_advancement_summary/_status_family)
must key off the real status enum, never the legacy withdrawn/
disqualified/missed_cut booleans directly -- proven with synthetic
records whose legacy fields are deliberately wrong, since the real
production data's legacy fields are always consistent with status and
so can't itself catch a silent reversion to reading them.

Kept as its own file rather than appended to test_hitejinro_round_
pipeline.py, which currently carries separate, paused, not-yet-approved
isolation-refactor edits (2026-10-02 "운영 데이터 보호 규칙" mission) --
this file's own commit must not bundle in unrelated, unapproved work."""
from __future__ import annotations

import json
import re

import pytest

from klpga.neo_win import hitejinro_round_pipeline as _rp
from klpga.neo_win.hitejinro_round_pipeline import cross_validate_against_round, parse_leaderboard, raw_evidence_path
from klpga.neo_win.hitejinro_round_page import _advancement_summary, _status_family, render_round_page

pytestmark = pytest.mark.round_pipeline

_R2_LEADERBOARD_PRESENT = raw_evidence_path(2, "LEADERBOARD").is_file()

requires_r2_leaderboard_evidence = pytest.mark.skipif(
    not _R2_LEADERBOARD_PRESENT,
    reason="real R2 leaderboard raw evidence not present in this checkout",
)


@requires_r2_leaderboard_evidence
def test_r1_cut_and_r2_cut_are_separate_states_not_one_missed_cut_boolean(tmp_path, monkeypatch):
    """status must be a real STATE (R1_CUT/R2_CUT/WD/DQ), never a
    single undifferentiated "CUT" string. Exercises real R1+R2
    evidence: 조하리/이수민/이소영 never played R2 at all (real
    r2_score is None for all three) -- their real cut was decided on
    R1's score alone, so status must read R1_CUT, never R2_CUT
    (R2_CUT is reserved for a player who actually completed round 2
    and is cut before round 3 -- zero such real cases exist in this
    tournament yet, but the states must stay distinct regardless)."""
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    out_path = parse_leaderboard(2)
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    by_id = {r["player_id"]: r for r in doc["records"]}

    for pid, name in [("11076", "조하리"), ("11978", "이수민"), ("8246", "이소영")]:
        r = by_id[pid]
        assert r["status"] == "R1_CUT", f"{name} ({pid}): expected R1_CUT, got {r['status']}"
        assert r["status_round"] == 1
        assert r["r1_score"] is not None and r["r2_score"] is None
        # legacy fields still real and consistent (backward compat --
        # every existing consumer reading missed_cut keeps working).
        assert r["missed_cut"] is True
        assert r["withdrawn"] is False
        assert r["disqualified"] is False

    for pid, name in [("10112", "고지우"), ("8240", "황정미")]:
        r = by_id[pid]
        assert r["status"] == "WD", f"{name} ({pid}): expected WD, got {r['status']}"
        assert r["status_round"] == 1
        assert r["withdrawn"] is True

    # 마다솜: withdrew before the tournament itself -- no real completed
    # round to attribute the status to, so status_round must be None,
    # never a fabricated round number.
    mds = by_id["9401"]
    assert mds["status"] == "WD"
    assert mds["status_round"] is None
    assert mds["r1_score"] is None and mds["r2_score"] is None

    # No real R2_CUT case exists yet in this tournament -- confirm the
    # state is at least representable (never collapsed into R1_CUT)
    # rather than asserting a count of zero forever.
    statuses = {r["status"] for r in doc["records"]}
    assert "R1_CUT" in statuses
    assert statuses <= {None, "ACTIVE", "R1_CUT", "R2_CUT", "WD", "DQ"}


@requires_r2_leaderboard_evidence
def test_legacy_fields_stay_byte_identical_to_the_real_production_file(tmp_path, monkeypatch):
    """The new status/status_round fields must be purely additive --
    every existing consumer reading finish_position/scores/withdrawn/
    disqualified/missed_cut must see exactly what it saw before this
    mission, for all 108 real entrants, not just a handful of spot
    checks."""
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    out_path = parse_leaderboard(2)
    new_doc = json.loads(out_path.read_text(encoding="utf-8"))

    from klpga.tournament_context import CONTENT_DIR
    current_doc = json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))

    new_by_id = {r["player_id"]: r for r in new_doc["records"]}
    cur_by_id = {r["player_id"]: r for r in current_doc["records"]}
    assert set(new_by_id) == set(cur_by_id)

    fields = [
        "finish_position", "finish_position_numeric", "score_to_par",
        "r1_score", "r2_score", "r3_score", "r4_score",
        "withdrawn", "disqualified", "missed_cut",
    ]
    mismatches = [
        (pid, f, cur_by_id[pid].get(f), new_by_id[pid].get(f))
        for pid in cur_by_id for f in fields
        if cur_by_id[pid].get(f) != new_by_id[pid].get(f)
    ]
    assert mismatches == [], f"{len(mismatches)} legacy-field mismatches: {mismatches[:10]}"


def test_status_family_reads_the_enum_not_legacy_booleans():
    """2026-10-02 '실제 운영 적용' mission: hitejinro_round_page.py's
    display logic must key off the real status enum (R1_CUT/R2_CUT/
    WD/DQ/None), never the legacy withdrawn/disqualified/missed_cut
    booleans directly. Proven here with a record whose legacy fields
    deliberately DISAGREE with status -- if the renderer still read the
    legacy fields, this would silently pass; reading status is the only
    way this assertion holds."""
    contradictory_record = {
        "status": "R2_CUT",
        "status_round": 2,
        # Legacy fields deliberately wrong/stale, as if an older writer
        # had set them -- _status_family must ignore these entirely.
        "withdrawn": True,
        "disqualified": True,
        "missed_cut": False,
    }
    assert _status_family(contradictory_record["status"]) == "CUT"
    assert _status_family("WD") == "WD"
    assert _status_family("DQ") == "DQ"
    assert _status_family(None) is None


def test_advancement_summary_classifies_by_status_not_legacy_flags():
    """Same proof at the _advancement_summary level: a four-record
    synthetic set whose legacy booleans are all wrong on purpose. The
    real counts must come out matching the real `status` values, which
    only happens if the summary reads status, never missed_cut/
    withdrawn/disqualified."""
    records = [
        {"player_id": "1", "status": None, "r1_score": 70,
         "withdrawn": True, "disqualified": True, "missed_cut": True},
        {"player_id": "2", "status": "R1_CUT", "r1_score": 90,
         "withdrawn": False, "disqualified": False, "missed_cut": False},
        {"player_id": "3", "status": "WD", "r1_score": None,
         "withdrawn": False, "disqualified": False, "missed_cut": False},
        {"player_id": "4", "status": "DQ", "r1_score": None,
         "withdrawn": False, "disqualified": False, "missed_cut": False},
    ]
    summary = _advancement_summary(records)
    assert summary["advanced_count"] == 1
    assert summary["cut_count"] == 1
    assert summary["withdrawn_count"] == 1
    assert summary["disqualified_count"] == 1
    assert summary["cut_line_score"] == 70


@requires_r2_leaderboard_evidence
def test_r2_banner_never_shows_advanced_count_and_uses_real_evidence_only():
    """2026-10-02 'advanced_count 표시 금지' mission: R2's top banner
    and in-table cut-divider must never render "컷 통과 {n}명" -- that
    phrase claims a later, unconfirmed fact (who actually tees off in
    R3) that _advancement_summary was never computed from. _advancement_
    summary() itself is untouched (advanced_count is still a real,
    correct field on its returned dict -- see the test above) -- only
    the HTML these two displays render was changed to stop using it.

    Real R3 data doesn't exist in this checkout yet, so the banner must
    fall to the no-estimate branch: real R2 종료/R1 컷 확정/CUT+WD counts
    only, no CUT LINE score, no guessed R3 headcount. "R1 컷 확정" (not
    bare "CUT 확정") per the 2026-10-02 "배너 문구 재검토" mission: this
    tournament's real cut rule is R1-only, and a bare "CUT" on an R2
    RESULTS page could otherwise read as a cumulative R1+R2 cut -- the
    far more common real rule in stroke play."""
    from klpga.tournament_context import CONTENT_DIR
    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    # "컷 통과확률" (the M4 cut-PROBABILITY column header) is a separate,
    # unrelated real metric this mission never touched -- only the
    # count phrase "컷 통과 {n}명" (advanced_count) must be gone. A
    # same-day "Renderer만 수정" mission briefly added a "R2 컷 통과"
    # SECTION header too, but a later "EVIDENCE INSUFFICIENT" mission
    # removed it again (no real evidence backs labeling status=None
    # as any kind of "컷 통과" group) -- so "컷 통과 " should not
    # appear anywhere on this page any more, in any form.
    assert "컷 통과 " not in html, "no form of '컷 통과' may be displayed on the R2 page (no real evidence backs it)"
    assert "<p class='cut-line-banner'><strong>R2 종료</strong>" in html
    assert "R1 컷 확정" in html
    assert "CUT 3명" in html
    assert "WD 3명" in html
    # 2026-10-02 "R2 Renderer 재설계" mission: the in-table cut-line
    # score now lives on the "R2 미출전" SECTION's own header (see
    # test_r2_sections_are_rendered_for_r1_cut_and_wd_only below for
    # the full grouping behavior), not a standalone "CUT LINE —" line.
    assert "R2 미출전 — 87타 이하 통과 · 3명" in html


@requires_r2_leaderboard_evidence
def test_r2_round_columns_never_wrap_a_two_digit_score():
    """2026-10-02 'CSS 줄바꿈 버그' mission: a real screen showed R1/R2/
    R3/FR scores like "70" rendering as "7" over "0" -- traced to
    .leaderboard-table tbody td's white-space:normal (docs/assets/
    neo.css) outranking .data td's own nowrap by CSS specificity, the
    exact same bug class KB's own --r2-full fix (further up the same
    file) already documents. HITE JINRO's table never carried that
    modifier, so it was never covered. Fixed with a new, HITE-JINRO-
    scoped modifier (--hitejinro) that fixes nowrap only, without
    inheriting --r2-full's OTHER rules (which hard-code KB's own mobile
    grid column count/order). This test only proves the table opts
    into the fix; docs/assets/neo.css itself (where the real behavior
    lives) isn't Python-importable, so it can't assert the computed
    style here -- that was verified with a real Playwright render
    (box height ~39px / 1 line, vs ~58px / 2 lines before the fix)."""
    from klpga.tournament_context import CONTENT_DIR
    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    assert "leaderboard-table leaderboard-table--hitejinro" in html


@requires_r2_leaderboard_evidence
def test_r1_cut_shows_as_2r_미출전_not_as_an_r1_vs_r2_code():
    """2026-10-02 'CUT UI 재설계' mission: R1_CUT must render as plain-
    language "2R 미출전" inside the R2 column, not "R1 CUT" -- the old
    text named the round the player LAST COMPLETED while sitting
    inside the NEXT column, a second, independent source of confusion
    on top of "CUT" itself being ambiguous between the R1 and R2 cut
    rounds. Real evidence: 조하리/이수민/이소영 (all R1_CUT). The
    section they're grouped under is separately named "R2 미출전"
    (2026-10-02 "R2 Renderer 재설계"/"Renderer만 수정" missions) --
    "R1 CUT" as a string does not appear anywhere on the page any
    more, per-cell or as a section title."""
    from klpga.tournament_context import CONTENT_DIR
    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    assert "R1 CUT" not in html
    assert html.count("data-label='R2'>2R 미출전</td>") == 3


@requires_r2_leaderboard_evidence
def test_r2_sections_are_rendered_for_r1_cut_and_wd_only_not_active():
    """2026-10-02 'R2 Renderer 재설계' mission (operator's own words:
    "문제는 status enum이 아니다. 문제는 Renderer다"): on the R2 page,
    R1_CUT and WD/DQ/DNS each get their own separate, rank-less section
    (never played the round that would have produced a real rank) --
    never one flat tail mixing them. A same-day "Renderer만 수정"
    mission briefly gave status=None its own "R2 컷 통과" header too,
    but the following "EVIDENCE INSUFFICIENT" mission removed it again
    -- no real evidence (no KLPGA page anywhere in this tournament's
    raw evidence displays a "본선 진출자"/cut-pass counter for this
    population) backs that label, so status=None renders as a PLAIN
    ranked list with NO header/group name, pending real R3 evidence.
    R2_CUT never gets a section at all (real evidence: none exist in
    this tournament yet -- see
    test_r2_cut_merges_inline_with_a_real_rank_and_a_badge below for
    its own, different, no-section treatment via a synthetic record).
    Real evidence: 102 active (unlabeled), R1_CUT (조하리/이수민/이소영,
    3), WD (고지우/황정미/마다솜, 3)."""
    from klpga.tournament_context import CONTENT_DIR
    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    dividers = re.findall(r"<tr class='cut-divider'><td colspan='\d+'>([^<]*)</td></tr>", html)
    # Exactly 2 sections (R2 미출전, WD) -- no header for the active
    # group, no R2 CUT section/placeholder, no DQ/DNS section (0 real
    # cases of either).
    assert dividers == ["R2 미출전 — 87타 이하 통과 · 3명", "WD · 3명"]
    assert "R2 컷 통과" not in html
    assert html.index("R2 미출전") < html.index("WD · 3명")
    # The first real row (활성 선수, rank 1) must come before any
    # section divider -- confirms it renders plainly with no header
    # above it.
    assert html.index("<td data-label='순위'>1</td>") < html.index("R2 미출전")


def test_r2_cut_merges_inline_with_a_real_rank_and_a_badge(tmp_path, monkeypatch):
    """2026-10-02 'R2 Renderer 재설계' mission, operator's own words:
    "R2 CUT와 R1 CUT는 같은 UI가 아니다." R2_CUT players DID complete
    R2 -- 하나금융's own already-published R2 page (real reference the
    operator supplied) keeps a cut player's REAL rank/total and only
    adds a small "CUT" badge next to the name, never replacing
    rank/total with the word CUT and never pulling them into a
    separate section. No real R2_CUT exists in this tournament yet
    (status enum unchanged by this mission), so this is exercised with
    one synthetic record layered onto the real board -- the only way
    to test a real-shaped state this tournament hasn't produced yet."""
    from klpga.tournament_context import CONTENT_DIR
    import json as _json

    real_board = _json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    synthetic = dict(real_board["records"][0])
    synthetic.update(
        player_id="99999", player_name="테스트선수", finish_position="55", finish_position_numeric=55,
        score_to_par=5, status="R2_CUT", status_round=2, withdrawn=False, disqualified=False, missed_cut=True,
        r1_score=75, r2_score=80, r3_score=None, r4_score=None,
    )
    real_board["records"].append(synthetic)
    tmp_content = tmp_path
    for name in ("2026100005_ENTRY_KRANKING_JOIN.json", "HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1.json"):
        src = CONTENT_DIR / name
        if src.is_file():
            (tmp_content / name).write_bytes(src.read_bytes())
    (tmp_content / "2026100005_LEADERBOARD.json").write_text(
        _json.dumps(real_board, ensure_ascii=False), encoding="utf-8",
    )
    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=tmp_content,
    )
    # Real rank (55), real total (+5) -- never replaced by "CUT" text.
    assert "<td data-label='순위'>55</td>" in html
    assert "<td data-label='합계'>+5</td>" in html
    assert "<span class='status-badge'>CUT</span>" in html
    # No "R2 CUT" section header anywhere -- it merges straight into
    # the ranked list, not its own divider-separated group.
    assert "R2 CUT (" not in html
    assert "R2 CUT ·" not in html


@requires_r2_leaderboard_evidence
def test_r3_and_fr_pages_never_section_cut_or_wd_players():
    """2026-10-02 'R2 Renderer 재설계' mission, operator's own words:
    "R3·FR 페이지에서는 CUT 섹션을 생성하지 않는다." Sectioning is a
    round_number == 2 -only behavior. Real evidence: render_round_page
    (3, ...) against this tournament's real current data (zero real
    r3_score values, but 6 real status-having players) renders those 6
    players with zero 'cut-divider' rows -- they fall back to their
    existing status-replaces-rank/total cell, just with no
    divider/header around them, exactly as a round 3 page with no real
    R3 field of its own should."""
    from klpga.tournament_context import CONTENT_DIR
    html = render_round_page(
        3, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=CONTENT_DIR,
    )
    assert "cut-divider" not in html
    assert "R2 미출전" not in html
    assert "R2 컷 통과" not in html


def test_dns_text_produces_a_real_dns_status_not_silently_none():
    """2026-10-02 '공식 DOM 그대로 파싱' mission: re-analyzing the
    operator-re-uploaded official R2 evidence (byte-identical to the
    already-ingested file) confirmed _EXCLUSION_TEXT_RE already
    matches DNS/불참 text, but _status_state had no case for it --
    falling through to (None, None), silently indistinguishable from a
    genuinely active player. Zero real DNS cases exist in this
    tournament's evidence (re-confirmed this session), so this is
    exercised with the literal text directly, the same way WD/DQ/CUT
    already are."""
    round_scores = {1: 75, 2: None, 3: None, 4: None}
    assert _rp._status_state("DNS", round_scores, round_number=2) == ("DNS", 1)
    assert _rp._status_state("불참", round_scores, round_number=2) == ("DNS", 1)
    # Never flagged as withdrawn/disqualified/missed_cut (the legacy
    # booleans) -- DNS is its own real outcome, not equivalent to any
    # of those three.
    status, _ = _rp._status_state("DNS", round_scores, round_number=2)
    assert status not in ("WD", "DQ", "R1_CUT", "R2_CUT")


@requires_r2_leaderboard_evidence
def test_dns_section_renders_on_r2_page_when_a_real_dns_record_exists(tmp_path, monkeypatch):
    """No real DNS record exists in this tournament yet, so this is
    exercised with one synthetic record layered onto the real board --
    the same pattern already established for the R2_CUT inline-badge
    test above. Proves the Renderer (2026-10-02 mission item ②) gives
    DNS its own sectioned, rank-less group on the R2 page, same as
    R1_CUT/WD/DQ."""
    from klpga.tournament_context import CONTENT_DIR
    import json as _json

    real_board = _json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    synthetic = dict(real_board["records"][0])
    synthetic.update(
        player_id="88888", player_name="테스트DNS선수", finish_position=None, finish_position_numeric=None,
        score_to_par=None, status="DNS", status_round=None, withdrawn=False, disqualified=False, missed_cut=False,
        r1_score=None, r2_score=None, r3_score=None, r4_score=None,
    )
    real_board["records"].append(synthetic)
    for name in ("2026100005_ENTRY_KRANKING_JOIN.json", "HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1.json"):
        src = CONTENT_DIR / name
        if src.is_file():
            (tmp_path / name).write_bytes(src.read_bytes())
    (tmp_path / "2026100005_LEADERBOARD.json").write_text(_json.dumps(real_board, ensure_ascii=False), encoding="utf-8")

    html = render_round_page(
        2, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04", content_root=tmp_path,
    )
    dividers = re.findall(r"<tr class='cut-divider'><td colspan='\d+'>([^<]*)</td></tr>", html)
    assert dividers[-1] == "DNS · 1명"
    assert "테스트DNS선수" in html


@requires_r2_leaderboard_evidence
def test_cross_validate_against_round_flags_contradictions_and_verification_worklist(tmp_path, monkeypatch):
    """cross_validate_against_round is VALIDATION ONLY -- it must never
    assign or change any status (2026-10-02 mission item ③). Exercised
    against the real R2 LEADERBOARD.json with a synthetic "round 3"
    raw HTML built to contain: (a) 조하리 (a real R1_CUT player) --
    a genuine contradiction, since a cut player cannot be in a later
    round's field, and (b) a real active player simply absent --
    must land in needs_verification, never be concluded as WD."""
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    out_path = parse_leaderboard(2)
    assert out_path == tmp_path / "LEADERBOARD.json"

    import json as _json
    board = _json.loads(out_path.read_text(encoding="utf-8"))
    active_ids = [r["player_id"] for r in board["records"] if r.get("status") is None]
    first_active = active_ids[0]

    # Synthetic round-3 raw HTML: 조하리 (11076, real R1_CUT) wrongly
    # present, one real active player genuinely absent.
    raw_html = (
        f'<li id="favoritItem_11076" data-rank="50" data-name="조하리" '
        f'data-totunderpar="0" data-inghole="" data-todayunderpar="" data-score="0" '
        f'data-round1score="88" data-round2score="75" data-round3score="70" data-round4score="" '
        f'data-updown="0">'
    )
    raw_path = tmp_path / "r3_raw.html"
    raw_path.write_text(raw_html, encoding="utf-8")

    result = cross_validate_against_round(3, raw_path=raw_path)
    contradiction_ids = {c["player_id"] for c in result["contradictions"]}
    assert "11076" in contradiction_ids
    verify_ids = {v["player_id"] for v in result["needs_verification"]}
    assert first_active in verify_ids
    # Never a status field anywhere in the result -- confirms this
    # function only reports, never decides.
    assert "status" not in result["needs_verification"][0]
