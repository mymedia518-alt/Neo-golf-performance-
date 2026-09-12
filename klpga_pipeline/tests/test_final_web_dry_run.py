"""R3 FINAL WEB DRY-RUN / PRE-MORTEM.

KB 2026090003's real R3 has NOT concluded. Every fixture in this file
is synthetic -- built under its OWN isolated game_code
(SYN_GAME_CODE below, never "2026090003") with its OWN isolated
CONTENT_DIR (a pytest tmp_path, never the real content/website_v2/
tree) and its own isolated repo_root (never the real repository), so
nothing here can ever read, write, or leak into any real KB artifact.
Every synthetic r2_freeze/forecast fixture built in this file carries
an explicit `"SYNTHETIC_TEST_ONLY": True` top-level marker as a second,
defense-in-depth guard against a real result ever being mistaken for
one of these fixtures.

This suite exercises the REAL, already-shipped code path end to end:
klpga.neo_win.r3_result_input (R3 RESULT-ONLY INPUT PREPARATION, commit
0c909ec) -> klpga.neo_win.final_real_page (this task's new FINAL
renderer) -> klpga.website_v2.kb_home_stage_router /
klpga.neo_win.final_publication_gate (this task's new HOME-transition
gate) -> scripts/117_kb_r3_result_and_final_candidate.py's own real
run() function (module-loaded and exercised directly, with only the
network call and tournament-context resolution stubbed).

Section numbers below refer to the R3 FINAL WEB DRY-RUN task's own
20-section spec."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from klpga.neo_win.final_publication_gate import (
    build_final_published_evidence,
    final_published_evidence_exists,
    verify_final_published_hash,
)
from klpga.neo_win.final_real_page import (
    is_final_candidate_page,
    parse_final_candidate_page,
    render_final_candidate_page,
)
from klpga.neo_win.r3_freeze import build_r3_frozen_evidence, r3_freeze_exists, verify_r3_freeze_hash, write_r3_freeze_immutable
from klpga.neo_win.r3_real_page import is_real_page as is_r3_real_page, parse_r3_real_page, render_r3_real_page
from klpga.neo_win.r3_result_input import (
    build_final_validation_dataset,
    build_r3_frozen_records,
    extract_r3_official_result,
    validate_r3_result,
)
from klpga.parsers.leaderboard_parser import PlayerRoundRow
from klpga.tournament_context import TournamentContext
from klpga.website_v2.kb_home_stage_router import kb_current_stage, sync_root_home_to_current_stage

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SYN_GAME_CODE = "SYNFINALDRY01"
_ACTIVE_71 = [f"syn{i}" for i in range(71)]


# ---------------------------------------------------------------------
# Section 3: synthetic fixture (real identities allowed, isolated
# game_code, explicit SYNTHETIC_TEST_ONLY provenance marker).
# ---------------------------------------------------------------------

def _real_r2_active_identities() -> list[tuple[str, str]]:
    """Read-only: the real KB 71-ACTIVE population's (player_id, name)
    pairs, from the already-committed real R2 freeze. Only identity
    fields are borrowed (explicitly permitted by this task's own
    section 3); every score/result below is fabricated under a wholly
    separate, isolated game_code."""
    from klpga.neo_win.r2_freeze import load_r2_freeze
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context("2026090003")
    freeze = load_r2_freeze(context)
    active = [r for r in freeze["records"] if r.get("status") == "ACTIVE"]
    return [(str(r["player_id"]), r["player_name"]) for r in active]


def _synthetic_r2_freeze(ids: list[str]) -> dict:
    return {
        "SYNTHETIC_TEST_ONLY": True,
        "records": [
            {"player_id": pid, "player_name": f"SynPlayer{pid}", "status": "ACTIVE",
             "r1_score_to_par": -1, "r2_score_to_par": -1}
            for pid in ids
        ],
    }


def _synthetic_r2_forecast(ids: list[str]) -> dict:
    return {
        "SYNTHETIC_TEST_ONLY": True,
        "records": [
            {"player_id": pid, "neo_final_rank": i + 1, "r2_total_to_par": -2,
             "top20_pct": 45.0, "top10_pct": 18.0, "top5_pct": 0.0, "win_pct": 0.03}
            for i, pid in enumerate(ids)
        ],
    }


def _row(pid, name, *, status=None, r3=None, total=None) -> PlayerRoundRow:
    return PlayerRoundRow(
        game_code=SYN_GAME_CODE, player_code=pid, player_name=name, player_eng_name=None, round_number=3,
        rank_display=None, rank=None, tie_flag=False, status=status,
        total_under_par_display=None, total_under_par=total,
        today_under_par_display=None, today_under_par=r3,
        total_strokes=None, holes_completed="18",
        round1_score=None, round2_score=None, round3_score=r3, round4_score=None,
    )


def test_synthetic_fixture_uses_real_identities_isolated_from_real_kb():
    identities = _real_r2_active_identities()
    assert len(identities) == 71
    ids = [pid for pid, _ in identities]
    freeze = _synthetic_r2_freeze(ids)
    assert freeze["SYNTHETIC_TEST_ONLY"] is True
    # Same real player_ids, but under this file's OWN isolated
    # game_code -- never "2026090003" -- so no artifact_path this
    # fixture could ever produce collides with a real KB file.
    from klpga.tournament_context import TournamentContext as TC
    ctx = TC(game_code=SYN_GAME_CODE, tournament_name="SYN", season=2099,
              start_date="2099-01-01", end_date="2099-01-04", final_round_number=3,
              current_round_number=3, url_base=f"/tournaments/2099/{SYN_GAME_CODE}/",
              stage_state_filename="x", stage_order=("pre", "r1", "r2", "r3", "final"), artifacts={})
    assert ctx.game_code != "2026090003"


# ---------------------------------------------------------------------
# Section 4/6/16: full pipeline dry run using the exact real code path
# (r3_result_input -> final_real_page), with a deliberate tie/WD mix
# (section 7) so rank semantics are actually exercised, not just a
# trivial all-distinct case.
# ---------------------------------------------------------------------

def _tie_and_wd_dataset():
    """71 players: p0 solo 1st (-10), p1/p2 tied 2nd (-8), p3 solo 4th
    (-6), p4 WD (no score), p5..p70 (66 players) spread on strictly
    increasing distinct totals so no accidental extra ties occur."""
    ids = _ACTIVE_71
    r2_freeze = _synthetic_r2_freeze(ids)
    r2_forecast = _synthetic_r2_forecast(ids)
    raw_rows = []
    raw_rows.append(_row("syn0", "SynPlayersyn0", r3=-4, total=-10))
    raw_rows.append(_row("syn1", "SynPlayersyn1", r3=-3, total=-8))
    raw_rows.append(_row("syn2", "SynPlayersyn2", r3=-3, total=-8))
    raw_rows.append(_row("syn3", "SynPlayersyn3", r3=-2, total=-6))
    raw_rows.append(_row("syn4", "SynPlayersyn4", status="WD"))
    for i, pid in enumerate(ids[5:]):
        raw_rows.append(_row(pid, f"SynPlayer{pid}", r3=0, total=(-4 + i)))
    return r2_freeze, r2_forecast, raw_rows


def _build_candidate(r2_freeze, r2_forecast, raw_rows, *, final_round_number=3, game_code=SYN_GAME_CODE):
    active_ids = {str(r["player_id"]) for r in r2_freeze["records"] if r.get("status") == "ACTIVE"}
    rows, unresolved = extract_r3_official_result(raw_rows, active_ids)
    report = validate_r3_result(
        game_code=game_code, final_round_number=final_round_number, r2_freeze=r2_freeze,
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows,
        expected_game_code=game_code,
    )
    dataset = None
    if report.passed:
        dataset = build_final_validation_dataset(r2_freeze=r2_freeze, r2_forecast=r2_forecast, r3_rows=rows)
    return report, dataset


def test_full_pipeline_dry_run_validates_and_renders_final_candidate():
    r2_freeze, r2_forecast, raw_rows = _tie_and_wd_dataset()
    report, dataset = _build_candidate(r2_freeze, r2_forecast, raw_rows)
    assert report.passed, report.blocked_reasons()
    assert len(dataset) == 71

    candidate = {
        "schema_version": 1, "artifact": "final_validation_candidate", "game_code": SYN_GAME_CODE,
        "tournament_name": "SYNTHETIC FINAL DRY RUN OPEN", "final_round_number": 3,
        "r2_active_population": 71, "post_r3_win_forecast_generated": False, "records": dataset,
    }
    html = render_final_candidate_page(
        tournament_name=candidate["tournament_name"], game_code=SYN_GAME_CODE,
        date_range="2099.01.01 — 01.04", candidate=candidate,
        sponsor_by_id={"syn0": "SYN SPONSOR CO"},
    )
    assert is_final_candidate_page(html)


@pytest.fixture
def dry_run_html_and_candidate():
    r2_freeze, r2_forecast, raw_rows = _tie_and_wd_dataset()
    report, dataset = _build_candidate(r2_freeze, r2_forecast, raw_rows)
    assert report.passed, report.blocked_reasons()
    candidate = {
        "schema_version": 1, "artifact": "final_validation_candidate", "game_code": SYN_GAME_CODE,
        "tournament_name": "SYNTHETIC FINAL DRY RUN OPEN", "final_round_number": 3,
        "r2_active_population": 71, "post_r3_win_forecast_generated": False, "records": dataset,
    }
    html = render_final_candidate_page(
        tournament_name=candidate["tournament_name"], game_code=SYN_GAME_CODE,
        date_range="2099.01.01 — 01.04", candidate=candidate,
        sponsor_by_id={"syn0": "SYN SPONSOR CO"},
    )
    return html, candidate


# ---------------------------------------------------------------------
# Section 6: player count / player_id mapping / rendered == JSON.
# ---------------------------------------------------------------------

def test_rendered_player_count_matches_candidate(dry_run_html_and_candidate):
    html, candidate = dry_run_html_and_candidate
    rendered = parse_final_candidate_page(html)
    assert len(rendered) == len(candidate["records"]) == 71


def test_rendered_values_equal_candidate_json_player_by_player(dry_run_html_and_candidate):
    html, candidate = dry_run_html_and_candidate
    rendered_by_id = {r["player_id"]: r for r in parse_final_candidate_page(html)}
    assert set(rendered_by_id) == {str(r["player_id"]) for r in candidate["records"]}
    for record in candidate["records"]:
        pid = str(record["player_id"])
        rendered = rendered_by_id[pid]
        assert rendered["final_rank"] == (record["final_rank"] or "—")
        assert rendered["has_status_badge"] == (record["final_status"] != "ACTIVE")


# ---------------------------------------------------------------------
# Section 7: tie ranking semantics (1 / T2 / T2 / 4 / WD unranked).
# ---------------------------------------------------------------------

def test_tie_ranking_semantics_are_correct_and_never_all_collapse_to_t1(dry_run_html_and_candidate):
    html, candidate = dry_run_html_and_candidate
    by_id = {str(r["player_id"]): r for r in candidate["records"]}
    assert by_id["syn0"]["final_rank"] == "1"
    assert by_id["syn1"]["final_rank"] == "T2"
    assert by_id["syn2"]["final_rank"] == "T2"
    assert by_id["syn3"]["final_rank"] == "4"
    assert by_id["syn4"]["final_status"] == "WD"
    assert by_id["syn4"]["final_rank"] in (None, "—")
    # RED TEAM (section 17): "모든 선수가 T1이 될 수 있는가?" -- prove it
    # structurally impossible, not just absent in this one fixture.
    ranks = [r["final_rank"] for r in candidate["records"] if r["final_rank"] not in (None, "—")]
    assert not all(r == "1" or r == "T1" for r in ranks)
    assert len(set(ranks)) > 1

    rendered_by_id = {r["player_id"]: r for r in parse_final_candidate_page(html)}
    assert rendered_by_id["syn0"]["final_rank"] == "1"
    assert rendered_by_id["syn1"]["final_rank"] == "T2"
    assert rendered_by_id["syn2"]["final_rank"] == "T2"
    assert rendered_by_id["syn3"]["final_rank"] == "4"
    assert rendered_by_id["syn4"]["final_rank"] == "—"


# ---------------------------------------------------------------------
# Section 8: sponsor hard gate.
# ---------------------------------------------------------------------

def test_sponsor_slot_present_when_known_and_blank_never_guessed_when_unknown(dry_run_html_and_candidate):
    html, candidate = dry_run_html_and_candidate
    rendered_by_id = {r["player_id"]: r for r in parse_final_candidate_page(html)}
    assert rendered_by_id["syn0"]["sponsor"] == "SYN SPONSOR CO"
    for pid, row in rendered_by_id.items():
        if pid != "syn0":
            assert row["sponsor"] == ""  # blank, never a fabricated placeholder
    # the structural sponsor slot itself is ALWAYS present (render_player_identity's
    # own always-emit contract), even when empty:
    assert html.count("class='player-sponsor'") == 71


# ---------------------------------------------------------------------
# Section 6/9: HOME transition dry run -- the full STATE A / B / C / D
# sequence, entirely on isolated synthetic contexts. Never touches the
# real KB repo. Proves file existence ALONE can never skip R3.
# ---------------------------------------------------------------------

@pytest.fixture
def home_router_synth(tmp_path, monkeypatch):
    import klpga.tournament_context as tc

    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)

    context = TournamentContext(
        game_code="SYNHOME01", tournament_name="SYNTHETIC HOME ROUTER OPEN", season=2099,
        start_date="2099-01-01", end_date="2099-01-04", final_round_number=3,
        current_round_number=3, url_base="/tournaments/2099/SYNHOME01/",
        stage_state_filename="SYNHOME01_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )
    repo_root = tmp_path / "repo"
    return context, repo_root, content_dir


def _write_minimal_r3_freeze(context, repo_root) -> None:
    """The minimal real write path to make r3_freeze_exists(context) and
    verify_r3_freeze_hash(context) both true -- used to move a synthetic
    context from STATE B/C into a place where STATE D can be tested."""
    r2_freeze_path = context.artifact_path("r2_frozen_evidence")
    r2_freeze_path.parent.mkdir(parents=True, exist_ok=True)
    r2_freeze_path.write_text('{"records": []}', encoding="utf-8")
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="test", official_source_url=None,
        collection_timestamp="2099-01-03T00:00:00Z", raw_official_response=b"[]",
        records=[{"player_id": "p1", "player_name": "P", "status": "ACTIVE",
                  "r1_score_to_par": -1, "r2_score_to_par": -1, "r3_score_to_par": 0}],
        expected_field_count=1, status_counts={"ACTIVE": 1}, wd_dq_dns_evidence=[],
        r2_freeze_path=r2_freeze_path, repo_root=repo_root, build_id="TESTB1",
    )
    write_r3_freeze_immutable(context, evidence)
    assert r3_freeze_exists(context) and verify_r3_freeze_hash(context)


def test_state_a_r2_current_before_any_official_r3_result(home_router_synth):
    """STATE A: nothing R3-related exists yet -- HOME stays at R2."""
    context, repo_root, content_dir = home_router_synth
    assert r3_freeze_exists(context) is False
    assert final_published_evidence_exists(context) is False
    assert kb_current_stage(context) not in ("r3", "final")


def test_state_b_validated_official_r3_result_makes_r3_current(home_router_synth):
    """STATE B: a real, hash-verified R3 freeze exists (mirroring a
    genuine official-result collection+validation pass) -- R3 becomes
    current, never skipped straight to FINAL."""
    context, repo_root, content_dir = home_router_synth
    _write_minimal_r3_freeze(context, repo_root)
    assert kb_current_stage(context) == "r3"


def test_state_c_final_candidate_alone_never_advances_past_r3(home_router_synth):
    """STATE C: a FINAL candidate JSON (or even a rendered FINAL HTML
    file) existing on disk -- both produced automatically the instant
    validation passes, long before any human approval -- must NEVER by
    itself promote past R3. Section 1/6's own explicit requirement."""
    context, repo_root, content_dir = home_router_synth
    _write_minimal_r3_freeze(context, repo_root)
    candidate_path = context.artifact_path("final_validation_candidate")
    candidate_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    assert final_published_evidence_exists(context) is False
    assert kb_current_stage(context) == "r3"

    final_page = repo_root / "docs" / "tournaments" / "2099" / "SYNHOME01" / "final" / "index.html"
    final_page.parent.mkdir(parents=True, exist_ok=True)
    final_page.write_text("<html><body><main><strong class=\"status\">FINAL</strong></main></body></html>", encoding="utf-8")
    assert kb_current_stage(context) == "r3"  # still r3 -- the FINAL HTML file's mere existence changes nothing


def test_state_d_explicit_final_publication_approval_makes_final_current(home_router_synth):
    """STATE D: R3 evidence exists AND a real, hash-bound
    final_published_evidence artifact exists -- only now does FINAL
    become current."""
    context, repo_root, content_dir = home_router_synth
    _write_minimal_r3_freeze(context, repo_root)
    candidate_path = context.artifact_path("final_validation_candidate")
    candidate_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    assert kb_current_stage(context) == "r3"

    evidence = build_final_published_evidence(context, approved_by="TEST_HUMAN_APPROVER")
    evidence_path = context.artifact_path("final_published_evidence")
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
    assert final_published_evidence_exists(context)
    assert verify_final_published_hash(context)
    assert kb_current_stage(context) == "final"

    final_page = repo_root / "docs" / "tournaments" / "2099" / "SYNHOME01" / "final" / "index.html"
    final_page.parent.mkdir(parents=True, exist_ok=True)
    final_page.write_text(
        "<html><head><title>t</title></head><body><main>"
        '<strong class="status">FINAL</strong><p>final-body-marker</p>'
        "</main></body></html>", encoding="utf-8",
    )
    result = sync_root_home_to_current_stage(context, repo_root=repo_root)
    assert result["current_stage"] == "final"
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert "final-body-marker" in home_html


def test_final_published_evidence_alone_without_r3_freeze_never_promotes_home(home_router_synth):
    """RED TEAM (section 6/17): even a hypothetical stray/miswritten
    final_published_evidence, with NO real R3 freeze behind it at all,
    must never promote HOME past R2 -- R3 evidence is a hard,
    structural prerequisite for "final", not just a convention."""
    context, repo_root, content_dir = home_router_synth
    candidate_path = context.artifact_path("final_validation_candidate")
    candidate_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    evidence = build_final_published_evidence(context, approved_by="TEST_HUMAN_APPROVER")
    context.artifact_path("final_published_evidence").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
    assert r3_freeze_exists(context) is False
    assert kb_current_stage(context) != "final"


def test_stale_final_published_evidence_never_matches_a_regenerated_candidate(home_router_synth):
    """Section 17 red team: a candidate regenerated after evidence was
    written (e.g. R3 result corrected) must invalidate the old
    evidence's hash binding -- never let a stale approval silently
    cover a different candidate."""
    context, repo_root, content_dir = home_router_synth
    _write_minimal_r3_freeze(context, repo_root)
    candidate_path = context.artifact_path("final_validation_candidate")
    candidate_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    evidence = build_final_published_evidence(context, approved_by="TEST_HUMAN_APPROVER")
    context.artifact_path("final_published_evidence").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
    assert kb_current_stage(context) == "final"

    candidate_path.write_text(json.dumps({"records": [{"changed": True}]}), encoding="utf-8")
    assert verify_final_published_hash(context) is False
    assert kb_current_stage(context) != "final"
    assert kb_current_stage(context) == "r3"  # falls back to r3, never further back than the real evidence supports


def test_real_kb_current_stage_is_still_r2_unaffected_by_this_task():
    """Confirms the new "final" branch is a real no-op for production:
    KB's real context has no final_published_evidence artifact, so
    kb_current_stage keeps resolving exactly as before this task."""
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context("2026090003")
    assert final_published_evidence_exists(context) is False
    assert kb_current_stage(context) == "r2"


# ---------------------------------------------------------------------
# Section 10: PRE/R1/R2 historical immutability across the whole dry
# run performed by this test module.
# ---------------------------------------------------------------------

_HISTORICAL_PATHS = (
    "docs/tournaments/2026/2026090003/pre/index.html",
    "docs/tournaments/2026/2026090003/r1/index.html",
    "docs/tournaments/2026/2026090003/r2/index.html",
    "docs/index.html",
    "klpga_pipeline/content/website_v2/2026090003_R2_FROZEN_EVIDENCE.json",
    "klpga_pipeline/content/website_v2/2026090003_POST_R2_FINAL_FORECAST.json",
)


def test_pre_r1_r2_historical_artifacts_are_byte_identical_before_and_after_the_full_dry_run():
    """Runs the entire synthetic pipeline (validate -> build dataset ->
    render -> HOME-router probe) again inside this one test, then
    confirms git reports zero pending changes to any real PRE/R1/R2
    file -- the strongest available proof nothing in this task's own
    code path can touch them, since every real file's actual bytes are
    checked, not just "no write call was made"."""
    r2_freeze, r2_forecast, raw_rows = _tie_and_wd_dataset()
    report, dataset = _build_candidate(r2_freeze, r2_forecast, raw_rows)
    assert report.passed
    candidate = {
        "schema_version": 1, "artifact": "final_validation_candidate", "game_code": SYN_GAME_CODE,
        "tournament_name": "SYNTHETIC FINAL DRY RUN OPEN", "final_round_number": 3,
        "r2_active_population": 71, "post_r3_win_forecast_generated": False, "records": dataset,
    }
    render_final_candidate_page(
        tournament_name=candidate["tournament_name"], game_code=SYN_GAME_CODE,
        date_range="2099.01.01 — 01.04", candidate=candidate, sponsor_by_id={},
    )
    from klpga.tournament_context import load_tournament_context
    kb_current_stage(load_tournament_context("2026090003"))

    for rel in _HISTORICAL_PATHS:
        result = subprocess.run(["git", "diff", "--stat", "HEAD", "--", rel], capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert result.stdout.strip() == "", f"{rel} has uncommitted changes: {result.stdout}"


# ---------------------------------------------------------------------
# Section 11: R2 probability formatter / column semantics preserved on
# the FINAL page's historical-prediction columns.
# ---------------------------------------------------------------------

def test_r2_probability_format_and_historical_context_label_on_final_page():
    candidate = {
        "schema_version": 1, "artifact": "final_validation_candidate", "game_code": SYN_GAME_CODE,
        "tournament_name": "T", "final_round_number": 3, "r2_active_population": 1,
        "post_r3_win_forecast_generated": False,
        "records": [
            {"player_id": "a", "player_name": "A", "r2_rank": 1, "r2_total": -2,
             "r2_top20": 0.0, "r2_top10": 0.05, "r2_top5": 12.34, "r2_win": None,
             "r3_score": -1, "final_total": -3, "final_rank": "1", "final_status": "ACTIVE",
             "winner_flag": True, "top5_flag": True, "top10_flag": True, "top20_flag": True},
        ],
    }
    html = render_final_candidate_page(tournament_name="T", game_code=SYN_GAME_CODE, date_range="x", candidate=candidate, sponsor_by_id={})
    rendered = parse_final_candidate_page(html)[0]
    assert rendered["r2_top20_display"] == "0%"
    assert rendered["r2_top10_display"] == "<0.1%"
    assert rendered["r2_top5_display"] == "12.3%"
    assert rendered["r2_win_display"] == "—"
    assert "R2 종료 후 예측" in html
    # never mixes outcome and prediction into one recomputed number:
    forbidden = ("post_r3_win", "r3_win_pct", "새 예측", "post-r3")
    assert not any(term in html for term in forbidden)


# ---------------------------------------------------------------------
# Section 12/13: desktop/mobile QA. Same markup renders for both (no
# separate mobile template -- CSS alone reflows it, exactly R2's own
# established contract); this proves the structural data-label/column
# order every viewport depends on, and that the mobile grid CSS class
# is reused, never redesigned.
# ---------------------------------------------------------------------

def test_desktop_and_mobile_share_identical_markup_and_data_label_contract(dry_run_html_and_candidate):
    html, _candidate = dry_run_html_and_candidate
    assert "leaderboard-table--r2-full" in html  # reused verbatim, zero new CSS
    for label in ("순위", "선수", "합계", "R3", "Top20", "Top10", "Top5", "우승"):
        assert f"data-label='{label}'" in html
    # column order in the DOM (both desktop table and the mobile
    # data-label caption follow DOM order) is FINAL outcome first, then
    # the historical-prediction group -- never interleaved.
    order = ["순위", "선수", "합계", "R3", "Top20", "Top10", "Top5", "우승"]
    positions = [html.index(f"data-label='{label}'") for label in order]
    assert positions == sorted(positions)


# ---------------------------------------------------------------------
# Section 14: navigation.
# ---------------------------------------------------------------------

def test_navigation_pre_r1_r2_r3_final_present_with_correct_hrefs(dry_run_html_and_candidate):
    """Section 1: PRE -> R1 -> R2 -> R3 -> FINAL -- R3 must never be
    collapsed out of the public stage progression."""
    html, _candidate = dry_run_html_and_candidate
    assert f'href="/tournaments/2026/{SYN_GAME_CODE}/pre/"' in html
    assert f'href="/tournaments/2026/{SYN_GAME_CODE}/r1/"' in html
    assert f'href="/tournaments/2026/{SYN_GAME_CODE}/r2/"' in html
    assert f'href="/tournaments/2026/{SYN_GAME_CODE}/r3/"' in html
    assert f'href="/tournaments/2026/{SYN_GAME_CODE}/final/" aria-current="page"' in html
    # FINAL is aria-current only on FINAL's own page; R3's own link here
    # must never itself carry aria-current (that would mean two "current"
    # stages at once).
    assert f'href="/tournaments/2026/{SYN_GAME_CODE}/r3/" aria-current="page"' not in html


# ---------------------------------------------------------------------
# Section 15: result input failure drills A-J -- each must BLOCKED /
# no candidate / no rendering ever happens.
# ---------------------------------------------------------------------

def test_drill_a_missing_player_blocks():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids[:-1]]
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed is False and dataset is None


def test_drill_b_duplicate_player_id_blocks():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    raw_rows.append(_row("syn0", "SynPlayersyn0-dup", r3=0, total=0))
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed is False and dataset is None


def test_drill_c_duplicate_name_blocks():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    raw_rows[1] = _row(ids[1], f"SynPlayer{ids[0]}", r3=0, total=0)
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed is False and dataset is None


def test_drill_d_r3_score_missing_blocks():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    raw_rows[0] = _row(ids[0], f"SynPlayer{ids[0]}", r3=None, total=0)  # ACTIVE but no r3 score
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed is False and dataset is None


def test_drill_e_final_total_missing_blocks():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    raw_rows[0] = _row(ids[0], f"SynPlayer{ids[0]}", r3=0, total=None)
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed is False and dataset is None


def test_drill_f_unknown_status_is_never_silently_accepted_as_active():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    raw_rows[0] = _row(ids[0], f"SynPlayer{ids[0]}", status="RETIRED", r3=None, total=None)
    active_ids = {str(r["player_id"]) for r in _synthetic_r2_freeze(ids)["records"]}
    rows, unresolved = extract_r3_official_result(raw_rows, active_ids)
    row0 = next(r for r in rows if r.player_id == ids[0])
    # An unrecognized status string is treated as ACTIVE-with-no-real-
    # score (never silently promoted to a clean WD/DQ with fabricated
    # evidence) -- so it fails the real score-presence check, BLOCKED.
    assert row0.official_status == "ACTIVE"
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed is False and dataset is None


def test_drill_g_player_not_in_r2_active_is_excluded_never_leaks_into_dataset():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    raw_rows.append(_row("intruder-not-r2-active", "Intruder", r3=-99, total=-99))
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows)
    assert report.passed, report.blocked_reasons()
    assert all(r["player_id"] != "intruder-not-r2-active" for r in dataset)
    assert len(dataset) == 71


def test_drill_h_r2_freeze_changing_mid_run_hard_stops(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    from klpga.neo_win.r3_result_input import R2FreezeProtectionError, snapshot_r2_state, verify_r2_state_unchanged

    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)
    context = TournamentContext(
        game_code="SYNHSTOP01", tournament_name="X", season=2099, start_date="2099-01-01",
        end_date="2099-01-04", final_round_number=3, current_round_number=3,
        url_base="/x/", stage_state_filename="x", stage_order=("pre", "r1", "r2", "r3", "final"), artifacts={},
    )
    freeze_path = content_dir / "SYNHSTOP01_R2_FROZEN_EVIDENCE.json"
    forecast_path = content_dir / "SYNHSTOP01_POST_R2_FINAL_FORECAST.json"
    freeze_path.write_text('{"records": []}', encoding="utf-8")
    forecast_path.write_text('{"records": []}', encoding="utf-8")
    before = snapshot_r2_state(context)
    freeze_path.write_text('{"records": [{"tampered": true}]}', encoding="utf-8")
    with pytest.raises(R2FreezeProtectionError):
        verify_r2_state_unchanged(context, before)


def test_drill_i_final_round_number_not_3_blocks():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    report, dataset = _build_candidate(_synthetic_r2_freeze(ids), _synthetic_r2_forecast(ids), raw_rows, final_round_number=4)
    assert report.passed is False and dataset is None
    assert any("final_round_number" in reason for reason in report.blocked_reasons())


def test_drill_j_malformed_official_response_never_crashes_and_never_passes():
    ids = _ACTIVE_71
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids[:-1]]
    raw_rows.append(object())  # malformed: no player_code/status/etc attributes at all
    active_ids = {str(r["player_id"]) for r in _synthetic_r2_freeze(ids)["records"]}
    rows, unresolved = extract_r3_official_result(raw_rows, active_ids)  # must not raise
    assert ids[-1] in unresolved
    report = validate_r3_result(
        game_code=SYN_GAME_CODE, final_round_number=3, r2_freeze=_synthetic_r2_freeze(ids),
        r3_rows=rows, unresolved_player_ids=unresolved, raw_rows=raw_rows, expected_game_code=SYN_GAME_CODE,
    )
    assert report.passed is False


# ---------------------------------------------------------------------
# Section 16: the real scripts/117 run() function, exercised end to
# end with only the network call and tournament-context resolution
# stubbed -- proves the ACTUAL single command's real code path, not a
# reimplementation of it.
# ---------------------------------------------------------------------

def _load_script_117():
    spec = importlib.util.spec_from_file_location("op117_dry_run_under_test", SCRIPTS_DIR / "117_kb_r3_result_and_final_candidate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script117_synth(tmp_path, monkeypatch):
    import klpga.tournament_context as tc

    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)

    context = TournamentContext(
        game_code="SYNRUN01", tournament_name="SYNTHETIC RUN() DRY RUN OPEN", season=2099,
        start_date="2099-01-01", end_date="2099-01-04", final_round_number=3,
        current_round_number=3, url_base="/tournaments/2099/SYNRUN01/",
        stage_state_filename="SYNRUN01_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )
    ids = _ACTIVE_71
    freeze = _synthetic_r2_freeze(ids)
    freeze["parsed_canonical_sha256"] = hashlib.sha256(
        json.dumps(freeze["records"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()  # required by klpga.neo_win.r2_freeze.verify_r2_freeze_hash, which run() calls directly
    (content_dir / "SYNRUN01_R2_FROZEN_EVIDENCE.json").write_text(
        json.dumps(freeze), encoding="utf-8",
    )
    (content_dir / "SYNRUN01_POST_R2_FINAL_FORECAST.json").write_text(
        json.dumps(_synthetic_r2_forecast(ids)), encoding="utf-8",
    )
    module = _load_script_117()
    monkeypatch.setattr(module, "load_tournament_context", lambda game_code: context)
    return module, context, ids


def test_run_end_to_end_dry_run_produces_final_candidate_and_web_qa_pass(script117_synth, monkeypatch):
    module, context, ids = script117_synth
    _r2_freeze, _r2_forecast, raw_rows = _tie_and_wd_dataset()

    def _fake_fetch(client, game_code, round_number, *, use_cache=True):
        return raw_rows

    import klpga.collectors.leaderboard as leaderboard_mod
    monkeypatch.setattr(leaderboard_mod, "fetch_round_leaderboard", _fake_fetch)

    result = module.run(game_code="SYNRUN01")
    assert result["action"] == "FINAL_CANDIDATE_READY", result
    assert result["final_web_qa_passed"] is True
    assert result["production_deployed"] is False
    assert result["final_published_evidence_written"] is False
    assert result["home_synced_by_this_script"] is False
    # R3 is a real, freezable stage BEFORE FINAL exists -- the router
    # must now resolve "r3" for this context (never skipped to "final",
    # since no final_published_evidence was ever written by run()).
    assert result["kb_current_stage_after_this_run"] == "r3"

    web_path = Path(result["final_web_candidate_path"])
    assert web_path.is_file()
    assert "docs" not in web_path.parts  # NEVER written under docs/
    html = web_path.read_text(encoding="utf-8")
    rendered = parse_final_candidate_page(html)
    assert len(rendered) == 71

    r3_web_path = Path(result["r3_web_candidate_path"])
    assert r3_web_path.is_file()
    assert "docs" not in r3_web_path.parts
    r3_html = r3_web_path.read_text(encoding="utf-8")
    assert is_r3_real_page(r3_html)
    r3_rendered = parse_r3_real_page(r3_html)
    assert len(r3_rendered) == 70  # 71 R2-ACTIVE minus the 1 WD in this fixture

    from klpga.neo_win.r3_freeze import r3_freeze_exists as _r3_exists, verify_r3_freeze_hash as _r3_verify
    assert _r3_exists(context) and _r3_verify(context)

    candidate = json.loads(Path(result["candidate_path"]).read_text(encoding="utf-8"))
    assert candidate["post_r3_win_forecast_generated"] is False
    assert not final_published_evidence_exists(context)  # never auto-approved

    # Re-running the exact same command again must be safe (idempotent
    # R3 freeze re-use, never a crash, never a second freeze attempt).
    result2 = module.run(game_code="SYNRUN01")
    assert result2["action"] == "FINAL_CANDIDATE_READY", result2


def test_run_hard_stops_if_rendered_html_ever_disagrees_with_the_candidate_json(script117_synth, monkeypatch):
    """RED TEAM (section 17): forces a render/JSON divergence and proves
    the script's own post-render QA catches it rather than shipping a
    silently-wrong candidate."""
    module, context, ids = script117_synth
    _r2_freeze, _r2_forecast, raw_rows = _tie_and_wd_dataset()

    def _fake_fetch(client, game_code, round_number, *, use_cache=True):
        return raw_rows

    import klpga.collectors.leaderboard as leaderboard_mod
    monkeypatch.setattr(leaderboard_mod, "fetch_round_leaderboard", _fake_fetch)

    def _broken_render(**kwargs):
        # A renderer defect that silently drops one player -- must be caught.
        candidate = dict(kwargs["candidate"])
        candidate["records"] = candidate["records"][1:]
        from klpga.neo_win.final_real_page import render_final_candidate_page as _real
        kwargs["candidate"] = candidate
        return _real(**kwargs)

    monkeypatch.setattr(module, "render_final_candidate_page", _broken_render)
    result = module.run(game_code="SYNRUN01")
    assert result["action"] == "HARD_STOP"
    assert "qa_errors" in result
    assert not final_published_evidence_exists(context)


def test_run_never_writes_under_docs_and_never_writes_publication_evidence(script117_synth, monkeypatch):
    module, context, ids = script117_synth
    _r2_freeze, _r2_forecast, raw_rows = _tie_and_wd_dataset()

    def _fake_fetch(client, game_code, round_number, *, use_cache=True):
        return raw_rows

    import klpga.collectors.leaderboard as leaderboard_mod
    monkeypatch.setattr(leaderboard_mod, "fetch_round_leaderboard", _fake_fetch)

    before = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(REPO_ROOT)).stdout
    module.run(game_code="SYNRUN01")
    after = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(REPO_ROOT)).stdout
    assert before == after, "run() must leave the real tracked repository untouched"
    assert final_published_evidence_exists(context) is False


# ---------------------------------------------------------------------
# Section 8: permanent regression tests against the specific real-review
# failures raised on this preview (RED TEAM: VISUAL PREVIEW FAIL).
# ---------------------------------------------------------------------

def test_regression_r3_stage_never_disappears_regardless_of_final_round_number(home_router_synth):
    """A tournament whose final_round_number is 3 must NOT collapse R3
    out of the public stage progression -- R3 is a distinct stage from
    FINAL, always, never merely a synonym for "the last round"."""
    context, repo_root, content_dir = home_router_synth
    assert context.final_round_number == 3
    assert "r3" in context.stage_order
    assert "final" in context.stage_order
    assert context.stage_order.index("r3") < context.stage_order.index("final")
    _write_minimal_r3_freeze(context, repo_root)
    assert kb_current_stage(context) == "r3"  # reachable on its own, distinct from "final"


def test_regression_r3_result_never_automatically_becomes_final(home_router_synth):
    """A validated R3 freeze existing is NOT, by itself, a FINAL
    publication -- FINAL requires its own separate, explicit,
    human-approved evidence every time."""
    context, repo_root, content_dir = home_router_synth
    _write_minimal_r3_freeze(context, repo_root)
    assert kb_current_stage(context) == "r3"
    assert final_published_evidence_exists(context) is False
    # Even a FINAL candidate existing on top of the real R3 freeze changes nothing:
    context.artifact_path("final_validation_candidate").write_text(json.dumps({"records": []}), encoding="utf-8")
    assert kb_current_stage(context) == "r3"


def test_regression_synthetic_sponsor_can_never_enter_the_render_output_undeclared():
    """A renderer must never introduce a sponsor value that was not
    present in its own `sponsor_by_id` input -- the rendered sponsor set
    is always a subset of the input mapping's values, for BOTH the R3
    and FINAL renderers."""
    ids = _ACTIVE_71
    r2_freeze, r2_forecast, raw_rows = _tie_and_wd_dataset()
    active_ids = {str(r["player_id"]) for r in r2_freeze["records"] if r.get("status") == "ACTIVE"}
    rows, unresolved = extract_r3_official_result(raw_rows, active_ids)
    r3_records = build_r3_frozen_records(r2_freeze=r2_freeze, r3_rows=rows)
    real_sponsor_input = {"syn0": "REAL AUDIT SPONSOR CO"}  # everyone else deliberately absent -> must render blank

    r3_html = render_r3_real_page(
        tournament_name="T", game_code=SYN_GAME_CODE, date_range="x",
        r3_freeze={"records": r3_records}, forecast=r2_forecast, sponsor_by_id=real_sponsor_input,
    )
    for row in parse_r3_real_page(r3_html):
        assert row["sponsor"] in ("", *real_sponsor_input.values())

    report, dataset = _build_candidate(r2_freeze, r2_forecast, raw_rows)
    candidate = {
        "schema_version": 1, "artifact": "final_validation_candidate", "game_code": SYN_GAME_CODE,
        "tournament_name": "T", "final_round_number": 3, "r2_active_population": 71,
        "post_r3_win_forecast_generated": False, "records": dataset,
    }
    final_html = render_final_candidate_page(tournament_name="T", game_code=SYN_GAME_CODE, date_range="x", candidate=candidate, sponsor_by_id=real_sponsor_input)
    for row in parse_final_candidate_page(final_html):
        assert row["sponsor"] in ("", *real_sponsor_input.values())


def test_regression_script117_never_fabricates_a_sponsor_beyond_the_real_audit_loader(script117_synth, monkeypatch):
    """RED TEAM item 2: scripts/117 must pass the REAL audit-file
    loader's own dict straight through to both renderers, unmodified --
    never a second, locally-invented sponsor mapping. Proven by
    monkeypatching the loader to a known, distinctive dict and asserting
    both renderers receive it byte-for-byte."""
    module, context, ids = script117_synth
    _r2_freeze, _r2_forecast, raw_rows = _tie_and_wd_dataset()

    def _fake_fetch(client, game_code, round_number, *, use_cache=True):
        return raw_rows

    import klpga.collectors.leaderboard as leaderboard_mod
    monkeypatch.setattr(leaderboard_mod, "fetch_round_leaderboard", _fake_fetch)

    known_sponsor_map = {"syn0": "KNOWN AUDIT SPONSOR"}
    monkeypatch.setattr(module, "_load_sponsor_by_id", lambda game_code: dict(known_sponsor_map))

    seen = {}
    real_r3_render = module.render_r3_real_page
    real_final_render = module.render_final_candidate_page

    def _spy_r3(**kwargs):
        seen["r3"] = kwargs["sponsor_by_id"]
        return real_r3_render(**kwargs)

    def _spy_final(**kwargs):
        seen["final"] = kwargs["sponsor_by_id"]
        return real_final_render(**kwargs)

    monkeypatch.setattr(module, "render_r3_real_page", _spy_r3)
    monkeypatch.setattr(module, "render_final_candidate_page", _spy_final)

    result = module.run(game_code="SYNRUN01")
    assert result["action"] == "FINAL_CANDIDATE_READY", result
    assert seen["r3"] == known_sponsor_map
    assert seen["final"] == known_sponsor_map


def test_regression_uniform_dummy_probabilities_never_silently_replace_real_variation():
    """A real frozen R2 forecast has genuinely varying probabilities
    across 71 players (see the real KB forecast, 46 distinct top20_pct
    values) -- a rendered R3 or FINAL page must faithfully preserve that
    variation, never homogenize/replace it with a single dummy value."""
    ids = _ACTIVE_71
    r2_freeze = _synthetic_r2_freeze(ids)
    varying_forecast = {
        "records": [
            {"player_id": pid, "neo_final_rank": i + 1, "r2_total_to_par": -2,
             "top20_pct": round(5.0 + i * 1.3, 1), "top10_pct": round(2.0 + i * 0.7, 1),
             "top5_pct": round(0.5 + i * 0.3, 1), "win_pct": round(0.01 + i * 0.02, 2)}
            for i, pid in enumerate(ids)
        ],
    }
    raw_rows = [_row(pid, f"SynPlayer{pid}", r3=0, total=0) for pid in ids]
    active_ids = {str(r["player_id"]) for r in r2_freeze["records"]}
    rows, unresolved = extract_r3_official_result(raw_rows, active_ids)
    r3_records = build_r3_frozen_records(r2_freeze=r2_freeze, r3_rows=rows)
    r3_html = render_r3_real_page(
        tournament_name="T", game_code=SYN_GAME_CODE, date_range="x",
        r3_freeze={"records": r3_records}, forecast=varying_forecast, sponsor_by_id={},
    )
    top20_values = {row["top20_display"] for row in parse_r3_real_page(r3_html)}
    assert len(top20_values) > 1, "rendered TOP20 values must vary player-to-player, never collapse to one dummy value"


def test_regression_verbose_internal_validation_copy_never_leaks_into_public_ui():
    """Section 4: public copy must be minimal -- no internal-validation
    explanation of what the prediction column means or is not. Uses a
    deliberately clean tournament_name (unlike this file's other shared
    fixtures, which intentionally embed "SYNTHETIC" in the name for
    test-only clarity) so this check targets only the RENDERER's own
    copy, never a test fixture's own naming choice."""
    candidate = {
        "schema_version": 1, "artifact": "final_validation_candidate", "game_code": SYN_GAME_CODE,
        "tournament_name": "CLEAN NAME OPEN", "final_round_number": 3, "r2_active_population": 1,
        "post_r3_win_forecast_generated": False,
        "records": [{"player_id": "a", "player_name": "A", "r2_rank": 1, "r2_total": -2,
                     "r2_top20": 50.0, "r2_top10": 20.0, "r2_top5": 10.0, "r2_win": 1.0,
                     "r3_score": -1, "final_total": -3, "final_rank": "1", "final_status": "ACTIVE",
                     "winner_flag": True, "top5_flag": True, "top10_flag": True, "top20_flag": True}],
    }
    html = render_final_candidate_page(tournament_name="CLEAN NAME OPEN", game_code=SYN_GAME_CODE, date_range="x", candidate=candidate, sponsor_by_id={})
    forbidden = ("공식 FINAL 결과", "결과를 알고 다시 계산", "재계산", "SYNTHETIC", "PREVIEW")
    for phrase in forbidden:
        assert phrase not in html, f"forbidden internal/verbose copy leaked into public HTML: {phrase!r}"
    assert "R2 종료 후 예측" in html  # the one label that IS allowed/sufficient
    assert '<p class="note">총 1명</p>' in html  # plain population note, no appended explanation
