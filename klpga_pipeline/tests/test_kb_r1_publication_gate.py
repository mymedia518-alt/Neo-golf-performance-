"""KB 2026090003 R1 public page -- deployment-critical publication gate.

Covers: official population reconciliation, PRE immutability, R1
freeze integrity, no future leakage, probability bounds/coherence,
118 active / 2 WD, duplicate identity, sponsor invariant, HOME
unchanged, unrelated-route lockdown, R1 page build, production
artifact consistency. This is the gate scripts/109_build_kb_r1_page.py
and the whole KB R1 deployment depend on passing before any push to
production.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
DOCS = REPO_ROOT / "docs"
GAME_CODE = "2026090003"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _freeze() -> dict:
    return _load(f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json")


def test_official_population_reconciles_120():
    freeze = _freeze()
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    entry_ids = {e["player_id"] for e in entry["entries"]}
    predicted_ids = {p["player_id"] for p in freeze["predictions"]}
    excluded_ids = {e["player_id"] for e in freeze["excluded_players"]}
    wd_ids = {w["playerCode"] for w in freeze["official_wd"]}
    assert len(entry_ids) == 120
    assert (predicted_ids | excluded_ids | wd_ids) == entry_ids
    assert len(predicted_ids) + len(excluded_ids) + len(wd_ids) == 120


def test_pre_immutability():
    actual_sha = hashlib.sha256((CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()).hexdigest()
    assert actual_sha == "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"


def test_r1_freeze_integrity_hashes_match_real_files():
    freeze = _freeze()
    assert freeze["model_freeze_sha256"] == hashlib.sha256((CONTENT / "NEO_R1_MODEL_V1_FREEZE.json").read_bytes()).hexdigest()
    assert freeze["tournament_master_dates_sha256"] == hashlib.sha256((CONTENT / "TOURNAMENT_MASTER_DATES_V1.json").read_bytes()).hexdigest()
    recomputed = hashlib.sha256(
        json.dumps(freeze["predictions"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert recomputed == freeze["prediction_values_sha256"]


def test_no_future_leakage_r1_uses_only_r1_and_pre_data():
    """The frozen model's only two features are pre_score (PRE-time)
    and r1_z (R1-observed) -- guard against a future edit smuggling in
    a later-round field name."""
    freeze = _freeze()
    for p in freeze["predictions"]:
        assert set(p.keys()) == {
            "player_id", "player_name", "r1_score", "r1_to_par", "r1_rank_display",
            "pre_score", "r1_z", "cut", "top20", "top10", "top5", "win",
        }


def test_probability_bounds_and_coherence():
    freeze = _freeze()
    for p in freeze["predictions"]:
        vals = [p["win"], p["top5"], p["top10"], p["top20"], p["cut"]]
        assert all(0.0 <= v <= 1.0 for v in vals)
        assert vals == sorted(vals)


def test_118_active_2_wd():
    freeze = _freeze()
    assert freeze["r1_active_count"] == 118
    assert freeze["official_wd_count"] == 2


def test_no_duplicate_identity():
    freeze = _freeze()
    ids = [p["player_id"] for p in freeze["predictions"]] + [e["player_id"] for e in freeze["excluded_players"]]
    assert len(ids) == len(set(ids))


def test_sponsor_invariant_on_r1_page():
    """Every public occurrence of a player name (118 leaderboard rows +
    the top-3 PRE->R1 movers) must carry a sponsor slot immediately
    below it (klpga.website_v2.player_identity.render_player_identity),
    possibly empty, never fabricated -- only real verified sponsors
    from KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json."""
    from html import escape as html_escape

    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    audit = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    verified_sponsors = {html_escape(r["sponsor"]) for r in audit["newly_recovered_sponsors"]}

    sponsors = re.findall(r"<span class='player-sponsor'>(.*?)</span>", r1_html)
    names = re.findall(r"<span class='player-name'>(.*?)</span>", r1_html)
    assert len(sponsors) == 118 + 3  # 118 leaderboard rows + 3 PRE->R1 movers
    assert len(names) == len(sponsors)
    for sponsor in sponsors:
        if sponsor:
            assert sponsor in verified_sponsors, f"unverified sponsor text on page: {sponsor!r}"


def test_root_home_ownership_is_recognized_and_kb_r1_page_is_unaffected_either_way():
    """ROOT HOME RECOVERY (scripts/111_promote_top120_root_home_only.py),
    retargeted by PRODUCTION HOME PRODUCT POLICY CORRECTION (20260911):
    "root HOME is permanently reverted to TOP120_OWNER" was itself a
    misinterpretation -- the HOME STATE ROUTER makes root HOME's owner
    state-dependent (top120-v1 with no active tournament,
    current-tournament-v1 while one -- possibly KB itself -- is active;
    see tests/test_home_state_router.py for that contract's own
    coverage). What THIS gate still protects, unconditionally, is that
    KB's own dedicated R1 route is never affected by whichever owner
    root HOME currently has -- it is a real, separately-addressable
    page either way (see test_r1_page_exists_and_stage_nav_links_to_pre_and_r1
    and test_unrelated_routes_still_locked's sibling coverage)."""
    home_html = (DOCS / "index.html").read_text(encoding="utf-8")
    owner_match = re.search(r'neo-home-owner" content="([^"]*)"', home_html)
    assert owner_match is not None
    assert owner_match.group(1) in ("top120-v1", "current-tournament-v1")

    nav = re.search(r'<nav class="neo-global-nav".*?</nav>', home_html, re.S).group(0)
    assert '<a href="/" class="is-active" aria-current="page">홈</a>' in nav

    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    assert "KB금융 골든라이프 챔피언십" in r1_html
    assert r1_html.count("class='player-name'") > 0
    assert '<a href="/tournaments/">대회</a>' in nav


def test_previous_home_content_preserved_in_archive():
    """The prior real HOME (K-Ranking x NEO Ranking) is preserved,
    never deleted, when root is superseded by the current tournament --
    its own build/data implementation is untouched by this patch."""
    archive_path = REPO_ROOT / "docs_internal_archive" / "index.html"
    assert archive_path.is_file()
    archived = archive_path.read_text(encoding="utf-8")
    assert "K-Ranking TOP120" in archived or "player-row" in archived or "data-player-row" in archived
    assert "공사중" not in archived


def test_unrelated_routes_still_locked():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lockdown", ROOT / "scripts" / "apply_public_site_lockdown.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    problems = mod.verify_lockdown()
    assert problems == []


def test_r1_page_exists_and_stage_nav_links_to_pre_and_r1():
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    assert 'href="/tournaments/2026/2026090003/pre/"' in r1_html
    assert '<strong class="status">R1</strong>' in r1_html

    pre_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html").read_text(encoding="utf-8")
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in pre_html


def test_production_artifact_consistency_r1_score_matches_official_evidence():
    freeze = _freeze()
    r1ev = _load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    official_by_id = {p["playerCode"]: p for p in r1ev["players"]}
    for p in freeze["predictions"] + [
        {**e, "r1_score": None} for e in freeze["excluded_players"]
    ]:
        official = official_by_id.get(p["player_id"])
        if official is None or p.get("r1_score") is None:
            continue
        assert p["r1_score"] == official["r1Score"]


def test_r1_table_columns_exact_order():
    """NEO PUBLIC UI immutable column order (applies to PRE/R1/R2/R3/FR
    and every future public page): 순위 | 선수 | 합계 | 1R | 컷 통과 |
    Top20 | Top10 | Top5 | 우승 -- sponsor is not a separate column, it
    lives immediately below the player name inside the 선수 cell (see
    test_sponsor_invariant_on_r1_page)."""
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    thead = re.search(r"<thead>(.*?)</thead>", r1_html, re.S).group(1)
    headers = re.findall(r"<th>(.*?)</th>", thead)
    assert headers == ["순위", "선수", "합계", "1R", "컷 통과", "Top20", "Top10", "Top5", "우승"]


def test_r1_table_is_official_rank_ordered_with_ties_preserved_and_all_118_shown():
    """DEPLOYMENT-CRITICAL RECONCILIATION (navigation + R1 leaderboard
    patch): the public table's primary order is OFFICIAL R1 RANKING,
    never NEO probability order; genuine official ties (repeated rank
    values in the frozen evidence) render as 'T<rank>'; all 118
    R1-active players appear unconditionally, including the 7 with no
    NEO_V1_score, which render '--' for every prediction column
    instead of being dropped from the leaderboard."""
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    r1ev = _load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    freeze = _freeze()

    tbody = re.search(r"<tbody>(.*?)</tbody>", r1_html, re.S).group(1)
    rows = re.findall(r"<tr>(.*?)</tr>", tbody, re.S)
    assert len(rows) == 118 == r1ev["r1_competitive_count"]

    from collections import Counter
    rank_counts = Counter(p["rank"] for p in r1ev["players"])

    excluded_ids = {e["player_id"] for e in freeze["excluded_players"]}
    unavailable_seen = 0
    for row, official in zip(rows, r1ev["players"]):
        expected_rank = f"T{official['rank']}" if rank_counts[official["rank"]] > 1 else official["rank"]
        assert re.search(rf"data-label='순위'>{re.escape(expected_rank)}<", row), row
        assert official["name"] in row
        assert f"data-label='1R'>{official['r1Score']}<" in row
        if official["playerCode"] in excluded_ids:
            unavailable_seen += 1
            for label in ("컷 통과", "Top20", "Top10", "Top5", "우승"):
                assert f"data-label='{label}'>—<" in row, f"{official['name']} should show '—' for {label}"
    assert unavailable_seen == 7 == freeze["excluded_count"]


def test_r1_page_has_no_internal_developer_terminology():
    """NEO PUBLIC UI CORRECTION: internal evidence (model name, freeze/
    gate/validation status, provenance identifiers) stays in repository/
    audit artifacts -- it must never leak into visible public copy. This
    checks the page's VISIBLE body text only (not <meta>/<script> tags,
    which legitimately carry build-provenance identifiers for internal
    QA and are never rendered to a visitor)."""
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    body = re.search(r"<body[^>]*>(.*)</body>", r1_html, re.S).group(1)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    forbidden = (
        "NEO_R1_MODEL_V1", "freeze", "gate", "PASS", "FAIL", "holdout", "bootstrap",
        "coherence", "provenance", "SHA", "commit", "pipeline", "artifact",
        "simulation seed", "reconciliation", "검증된 고정 모델",
    )
    for term in forbidden:
        assert term not in body, f"forbidden internal term leaked into public R1 body: {term!r}"


def test_r1_heading_is_minimal_public_copy():
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    assert '<div class="leaderboard-head"><h2>1R 결과</h2></div>' in r1_html
    assert f'※ {7}명은 데이터 부족으로 예측 제외' in r1_html


def test_pre_r1_movement_section_is_short_no_model_explanation():
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    section = re.search(r'<section class="panel" id="pre-r1-movement">(.*?)</section>', r1_html, re.S).group(1)
    assert "PRE" in section and "R1" in section
    for term in ("NEO_R1_MODEL_V1", "검증된 고정 모델", "산출"):
        assert term not in section


def test_round_update_status_copy_on_pre_and_r1():
    """NEO PUBLIC UI immutable stage-copy rule."""
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    pre_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html").read_text(encoding="utf-8")
    assert '<p class="round-update-note">2R 종료 후 업데이트</p>' in r1_html
    assert '<p class="round-update-note">1R 종료 후 업데이트</p>' in pre_html


def test_footer_copyright_on_home_pre_and_r1():
    """PERMANENT PUBLIC INVARIANT (section 9): every currently-released
    public page carries the copyright line, via the one shared
    global_navigation.ensure_footer_copyright() mechanism."""
    from klpga.website_v2.global_navigation import FOOTER_COPYRIGHT_TEXT

    for path in (
        DOCS / "index.html",
        DOCS / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html",
        DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",
    ):
        html = path.read_text(encoding="utf-8")
        assert FOOTER_COPYRIGHT_TEXT in html, f"{path} is missing the copyright footer invariant"


def test_deployment_reconciliation_counts():
    """The exact reconciliation the navigation + R1 leaderboard patch
    is required to satisfy."""
    r1ev = _load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    freeze = _freeze()
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    tbody = re.search(r"<tbody>(.*?)</tbody>", r1_html, re.S).group(1)
    public_rows = len(re.findall(r"<tr>", tbody))

    official_active = r1ev["r1_competitive_count"]
    assert official_active == 118
    assert public_rows == 118

    official_by_id = {p["playerCode"]: p for p in r1ev["players"]}
    rank_mismatches = sum(
        1 for p in freeze["predictions"]
        if official_by_id.get(p["player_id"], {}).get("r1Score") != p["r1_score"]
    )
    assert rank_mismatches == 0

    assert freeze["predicted_count"] == 111
    assert freeze["excluded_count"] == 7

    coherence_violations = sum(
        1 for p in freeze["predictions"]
        if not (0.0 <= p["win"] <= p["top5"] <= p["top10"] <= p["top20"] <= p["cut"] <= 1.0)
    )
    assert coherence_violations == 0


def test_top_nav_routes_to_current_kb_r1_on_pre_and_r1():
    """The top-nav "대회" link (and its screen-reader compatibility
    copy) must route straight to KB's current published stage (R1),
    never to the locked /tournaments/ hub placeholder, on both the
    PRE and R1 pages."""
    kb_r1_url = "/tournaments/2026/2026090003/r1/"
    for route in ("pre", "r1"):
        html = (DOCS / "tournaments" / "2026" / GAME_CODE / route / "index.html").read_text(encoding="utf-8")
        nav = re.search(r'<nav class="neo-global-nav".*?</nav>', html, re.S).group(0)
        assert f'href="{kb_r1_url}"' in nav and ">대회</a>" in nav
        sr_nav = re.search(r'<nav class="sr-data".*?</nav>', html, re.S).group(0)
        assert f'href="{kb_r1_url}">대회</a>' in sr_nav


def test_ranking_deep_dive_neo_lab_about_still_locked():
    """OWNER UI/ROUTING FINAL PATCH (section C/P): with root HOME now
    the current tournament, every other unapproved product page (랭킹,
    딥다이브, NEO LAB, 소개) must still show the standard construction
    state -- already enforced by apply_public_site_lockdown.py's
    LOCKED_HTML_PATHS; this locks in that the new root-HOME patch
    didn't loosen it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("lockdown", ROOT / "scripts" / "apply_public_site_lockdown.py")
    lockdown = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lockdown)  # type: ignore[union-attr]

    for rel in ("ranking/index.html", "deep-dive/index.html", "neo-lab/index.html", "about/index.html"):
        assert rel in lockdown.LOCKED_HTML_PATHS
        content = (DOCS / rel).read_text(encoding="utf-8")
        assert content == lockdown.PLACEHOLDER_HTML, f"{rel} is not the exact placeholder"


def test_pre_r1_movement_section_has_no_bullets_and_aligned_rows():
    """Section I alignment-bug fix: PRE -> R1 uses the site's existing
    .mover-list flex-row pattern (identity left, movement right, same
    row, no <ul> default bullet -- list-style:none) instead of a bare
    <ul>/<li> list, on the R1 route. ROOT HOME RECOVERY
    (scripts/111_promote_top120_root_home_only.py) reverted root HOME
    away from the KB R1 mirror, so this is no longer also checked
    against docs/index.html -- see test_root_home_ownership_reverted_
    to_top120_owner for root HOME's own current content."""
    for path in (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",):
        html = path.read_text(encoding="utf-8")
        section = re.search(r'<section class="panel" id="pre-r1-movement">(.*?)</section>', html, re.S).group(1)
        assert section.startswith("<h2>PRE → R1</h2>")
        assert "주요 변동" not in section
        assert "<ul class='mover-list'>" in section
        rows = re.findall(r"<li>(.*?)</li>", section, re.S)
        assert len(rows) == 3
        for row in rows:
            assert "<span class='player-name'>" in row and "<span class='player-sponsor'>" in row
            assert "<span class='delta'>PRE " in row and "→ R1 " in row
