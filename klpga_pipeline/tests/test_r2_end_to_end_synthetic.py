"""R2 HOUSE red-team: the FULL END-TO-END SYNTHETIC FIXTURE requirement.

Proves the entire chain works together on one isolated, fabricated
COMPLETE R2 dataset -- never real production data, never written to
any real content/website_v2/docs path (every artifact lands under
pytest's own tmp_path, and TournamentContext.CONTENT_DIR is
monkeypatched to point there):

    expected field (from synthetic R1 evidence)
    -> R2 reconciliation (r2_readiness.assess_r2 via decide_r2_cycle)
    -> immutable freeze (PRE/R1 binding)
    -> leakage gate
    -> SG ingestion (fake HTTP client, real parser/validator)
    -> post-R2 forecast
    -> probability gate
    -> real-data renderer (klpga.neo_win.r2_real_page)
    -> publication gate (ALL PASS)
    -> HOME R2 eligibility (scripts/88's chronology resolver advances)

A companion test in this file separately proves the REAL, CURRENT
state is untouched by any of this -- nothing fake leaks into what a
real operator run against the real repo would see, and (BUGFIX,
fix/kb-r2-official-cut-gate-20260911, discovered via this exact test)
a dry run (live=False) must never regress KB's real, published R2 page
back to the WAIT placeholder once it has genuinely gone live.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from klpga.neo_win import r2_leakage_gate, r2_publication_gate, r2_sg_gate
from klpga.neo_win.post_r2_forecast import run_post_r2_forecast
from klpga.neo_win.r2_active_cycle import decide_r2_cycle
from klpga.neo_win.r2_freeze import build_r2_frozen_evidence, load_r2_freeze, verify_r2_freeze_hash, write_r2_freeze_immutable
from klpga.neo_win.r2_house_contract import expected_r2_field_from_r1_evidence
from klpga.neo_win.r2_probability_gate import validate_probability_gate
from klpga.neo_win.r2_real_page import is_real_page, render_r2_real_page
from klpga.neo_win.r2_sg_pipeline import STATUS_AVAILABLE, ingest_r2_sg
from klpga.tournament_context import TournamentContext

GAME_CODE = "E2ETEST01"

# SYNTHETIC ONLY: a fabricated 5-player field, never real KLPGA data.
SYNTHETIC_R1_EVIDENCE = {
    "gameCode": GAME_CODE,
    "players": [
        {"playerCode": "e1", "name": "가상선수일"},
        {"playerCode": "e2", "name": "가상선수이"},
        {"playerCode": "e3", "name": "가상선수삼"},
        {"playerCode": "e4", "name": "가상선수사"},
        {"playerCode": "e5", "name": "가상선수오"},
    ],
}

SYNTHETIC_R2_RECORDS = [
    {"player_id": "e1", "player_name": "가상선수일", "status": "ACTIVE", "round_to_par": -4, "total_to_par": -6,
     "r1_score_to_par": -2, "r2_score_to_par": -4, "holes_completed": "36"},
    {"player_id": "e2", "player_name": "가상선수이", "status": "ACTIVE", "round_to_par": -1, "total_to_par": -3,
     "r1_score_to_par": -2, "r2_score_to_par": -1, "holes_completed": "36"},
    {"player_id": "e3", "player_name": "가상선수삼", "status": "ACTIVE", "round_to_par": 2, "total_to_par": 1,
     "r1_score_to_par": -1, "r2_score_to_par": 2, "holes_completed": "36"},
    {"player_id": "e4", "player_name": "가상선수사", "status": "CUT", "round_to_par": 6, "total_to_par": 9,
     "r1_score_to_par": 3, "r2_score_to_par": 6, "holes_completed": "36"},
    {"player_id": "e5", "player_name": "가상선수오", "status": "WD", "round_to_par": None, "total_to_par": 3,
     "r1_score_to_par": 3, "r2_score_to_par": None, "holes_completed": None},
]


def _context(tmp_path: Path) -> TournamentContext:
    return TournamentContext(
        game_code=GAME_CODE, tournament_name="SYNTHETIC E2E OPEN", season=2026,
        start_date="2026-09-01", end_date="2026-09-04", final_round_number=3,
        current_round_number=2, url_base=f"/tournaments/2026/{GAME_CODE}/",
        stage_state_filename=f"{GAME_CODE}_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )


@pytest.fixture()
def context(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    monkeypatch.setattr(tc, "CONTENT_DIR", tmp_path / "content")
    (tmp_path / "content").mkdir()
    return _context(tmp_path)


def _sg_fixture_html(rows) -> str:
    """rows: list of (rank, name, [total, t2g, ott, app, arg, putt], rounds).
    Mirrors the real official strokesGained_detail response shape (see
    tests/test_website_v2_official_expansion.py's own fixture)."""
    body = ""
    for rank, name, vals, rounds in rows:
        total, t2g, ott, app, arg, putt = vals
        body += (
            "<tr>"
            f"<td>{rank}</td><td>{name}</td>"
            f"<td>{total}</td><td>{t2g}</td><td>{ott}</td><td>{app}</td><td>{arg}</td><td>{putt}</td>"
            f"<td>{rounds}</td>"
            "</tr>"
        )
    return f'<div id="record-one"><table><tbody>{body}</tbody></table></div>'


class _FakeSgSession:
    def __init__(self, html: str):
        self._html = html

    def post(self, url, data=None, headers=None, timeout=None):
        class _Resp:
            def __init__(self, text):
                self.text = text
                self.encoding = "utf-8"

            def raise_for_status(self):
                return None

        return _Resp(self._html)


class _FakeSgClient:
    def __init__(self, html: str):
        self.session = _FakeSgSession(html)


def test_full_end_to_end_synthetic_complete_r2_chain(context, tmp_path):
    # STEP 1: expected field, derived from synthetic R1 evidence (never
    # from R2's own observed rows -- P0-COMPLETENESS's independent
    # expected population rule).
    r1_evidence_path = tmp_path / "SYNTHETIC_R1_EVIDENCE.json"
    r1_evidence_path.write_text(json.dumps(SYNTHETIC_R1_EVIDENCE, ensure_ascii=False), encoding="utf-8")
    expected = expected_r2_field_from_r1_evidence(
        SYNTHETIC_R1_EVIDENCE, source_artifact=r1_evidence_path.name,
        source_sha256="0" * 64,
    )
    assert expected.player_ids == {"e1", "e2", "e3", "e4", "e5"}

    # STEP 2: R2 reconciliation -- decide_r2_cycle must resolve
    # PUBLISH_AND_CLOSE for a genuinely complete, fully-reconciled field.
    decision = decide_r2_cycle(
        SYNTHETIC_R2_RECORDS, sorted(expected.player_ids),
        official_page_available=True, cut_known=True, freeze_exists=False,
    )
    assert decision.action == "PUBLISH_AND_CLOSE"

    # STEP 3: immutable freeze, PRE+R1 binding.
    pre_freeze_path = tmp_path / "SYNTHETIC_PRE_FREEZE.json"
    pre_freeze_path.write_text(json.dumps({"schema": "pre"}), encoding="utf-8")
    r1_freeze_path = tmp_path / "SYNTHETIC_R1_FREEZE.json"
    r1_freeze_path.write_text(json.dumps({"schema": "r1"}), encoding="utf-8")

    status_counts = {"ACTIVE": 0, "CUT": 0, "WD": 0, "DQ": 0, "DNS": 0}
    for r in SYNTHETIC_R2_RECORDS:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    evidence = build_r2_frozen_evidence(
        context=context, official_source_identity="synthetic-e2e-fixture", official_source_url=None,
        collection_timestamp="2026-09-03T12:00:00Z", raw_official_response=json.dumps(SYNTHETIC_R2_RECORDS).encode("utf-8"),
        records=SYNTHETIC_R2_RECORDS, expected_field_count=len(expected.player_ids), status_counts=status_counts,
        cut_wd_dq_evidence=[{"player_id": "e4", "status": "CUT", "evidence": "synthetic"},
                             {"player_id": "e5", "status": "WD", "evidence": "synthetic"}],
        pre_freeze_path=pre_freeze_path, r1_freeze_path=r1_freeze_path, repo_root=tmp_path, build_id="E2E_BUILD",
    )
    write_r2_freeze_immutable(context, evidence)
    assert verify_r2_freeze_hash(context) is True
    freeze = load_r2_freeze(context)
    assert freeze["observed_player_count"] == 5

    # STEP 4: leakage gate -- R2 stage is allowed, no forbidden fields.
    r2_leakage_gate.assert_stage_allowed("r2", context="e2e test")
    r2_leakage_gate.assert_no_forbidden_result_fields({"records": freeze["records"]}, context="e2e freeze")

    # STEP 5: SG ingestion, precondition-gated on the verified freeze.
    r2_sg_gate.require_verified_frozen_r2_for_sg(context)
    sg_html = _sg_fixture_html([
        (1, "가상선수일", [4.10, 3.00, 1.50, 1.00, 0.50, 1.10], 2),
        (2, "가상선수이", [1.20, 0.80, 0.30, 0.30, 0.20, 0.40], 2),
        (3, "가상선수삼", [-0.90, -0.50, -0.20, -0.10, -0.20, -0.40], 2),
    ])
    sg_result = ingest_r2_sg(_FakeSgClient(sg_html), GAME_CODE, [
        {"player_id": r["player_id"], "player_name": r["player_name"]} for r in SYNTHETIC_R2_RECORDS
    ])
    assert sg_result["status"] == STATUS_AVAILABLE
    assert set(sg_result["sg_by_player_id"]) == {"e1", "e2", "e3"}  # e4/e5 (CUT/WD) never simulated -> no SG row

    # STEP 6: post-R2 forecast (ACTIVE players only, never CUT/WD).
    pre_performance = {"profiles": [
        {"player_id": "e1", "windows": {"recent5": {"components": {"total": {"mean": 0.4}}}}},
        {"player_id": "e2", "windows": {"recent5": {"components": {"total": {"mean": 0.1}}}}},
        {"player_id": "e3", "windows": {"recent5": {"components": {"total": {"mean": -0.2}}}}},
    ]}
    forecast = run_post_r2_forecast(
        context, pre_performance_snapshot=pre_performance, repo_root=tmp_path, build_id="E2E_BUILD",
        seed=42, n_simulations=500,
    )
    assert forecast["source_round"] == 2
    assert {r["player_id"] for r in forecast["records"]} == {"e1", "e2", "e3"}

    # STEP 7: probability hard gate.
    active_ids = {r["player_id"] for r in SYNTHETIC_R2_RECORDS if r["status"] == "ACTIVE"}
    validate_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids=active_ids)

    # STEP 8: real-data renderer -- fed ONLY by the already-gated
    # canonical artifacts above.
    real_html = render_r2_real_page(
        tournament_name=context.tournament_name, game_code=GAME_CODE, date_range="2026.09.01 — 09.04",
        r2_freeze=freeze, forecast=forecast, sg_ingest=sg_result,
        sponsor_by_id={"e1": "SYNTH SPONSOR"},
    )
    assert is_real_page(real_html)
    # R2 CUT SURVIVORS ONLY (fix/kb-r2-official-cut-gate-20260911): the
    # public main table shows ONLY the 3 ACTIVE (advancing) players --
    # CUT/WD are excluded from the table entirely, though they remain
    # fully intact in `freeze` (asserted == 5 in STEP 3 above) and every
    # other canonical artifact this test built.
    assert real_html.count("class='player-name'") == 3
    assert "가상선수사" not in real_html
    assert "가상선수오" not in real_html
    assert "총 3명 (컷 통과 선수만 표시)" in real_html

    # STEP 9: publication gate -- every named gate PASS.
    report = r2_publication_gate.evaluate_r2_publication_gate(GAME_CODE, {
        "official_source_verified": (r2_publication_gate.PASS, "synthetic fixture"),
        "completeness": (r2_publication_gate.PASS, decision.reason),
        "duplicate": (r2_publication_gate.PASS, "no duplicate identity"),
        "status": (r2_publication_gate.PASS, "every entrant accounted for"),
        "freeze": (r2_publication_gate.PASS, "immutable freeze written and hash-verified"),
        "pre_binding": (r2_publication_gate.PASS, "PRE+R1 freeze hashes bound"),
        "future_leakage": (r2_publication_gate.PASS, "no forbidden fields"),
        "sg": (r2_publication_gate.PASS, f"SG ingestion completed safely: status={sg_result['status']}"),
        "forecast": (r2_publication_gate.PASS, "forecast written"),
        "probability": (r2_publication_gate.PASS, "probability gate passed"),
        "website_build": (r2_publication_gate.PASS, "real page rendered"),
    })
    assert report.overall_state == r2_publication_gate.PASS
    assert report.publication_allowed is True
    assert report.real_r2 == "CONFIRMED"

    # STEP 10: HOME R2 eligibility -- scripts/88's chronology resolver
    # advances to r2 once the real page (no WAIT marker) is on disk.
    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("r2_e2e_home_router", ROOT / "scripts" / "88_build_neo_top120_candidate.py")
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)

    output = tmp_path / "docs_output"
    url_base = context.url_base
    for stage, html in (("pre", "<html><body>pre real content</body></html>"),
                         ("r1", "<html><body>r1 real content</body></html>"),
                         ("r2", real_html)):
        page = output / "tournaments" / "2026" / GAME_CODE / stage / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(html, encoding="utf-8")

    import klpga.website_v2.tournament_chronology as chron
    facts = chron.TournamentCardFacts(
        game_code=GAME_CODE, tournament_name=context.tournament_name, date_range_display="",
        url_base=url_base, start_date=context.start_date, end_date=context.end_date,
    )
    chronology = {"current": facts, "last": None, "next": None}
    registry = {GAME_CODE: {"stage_order": ["pre", "r1", "r2", "r3", "final"]}}
    resolved = router.resolve_chronology_stages(chronology, registry, output)
    assert resolved["current"].url_base == f"{url_base}r2/"


def test_real_current_state_is_untouched_and_a_dry_run_never_regresses_a_real_page():
    """The mandatory companion run: against the REAL repo (not tmp_path,
    no monkeypatching), nothing from the synthetic fixture above leaks
    into it, AND (the bug this test actually caught while verifying
    fix/kb-r2-official-cut-gate-20260911's rendered-output fix) a dry
    run must never regress an already-real, published R2 page back to
    the WAIT placeholder. This test now works correctly whether KB's
    real R2 has gone live yet or not -- it reads the real, current
    on-disk state FIRST and asserts the dry run preserves it exactly,
    rather than hardcoding a stale "always WAIT/empty" assumption.
    Reuses the real operator script exactly as an operator would run
    it."""
    import importlib.util

    from klpga.neo_win.r2_real_page import is_real_page
    from klpga.neo_win.r2_wait_page import is_wait_page

    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("op112_real_state_check", ROOT / "scripts" / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    real_r2_page = ROOT.parent / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html"
    was_real_before = real_r2_page.is_file() and is_real_page(real_r2_page.read_text(encoding="utf-8"))

    real_home = ROOT.parent / "docs" / "index.html"
    # PRODUCTION HOME -> KB CURRENT STAGE ROUTING HOTFIX
    # (fix/kb-r2-official-cut-gate-20260911): root HOME now legitimately
    # mirrors whichever stage klpga.website_v2.kb_home_stage_router
    # resolves as real-evidence-current -- once R2 genuinely publishes,
    # HOME correctly DOES carry the r2-full leaderboard. What a dry run
    # must never do is CHANGE that -- so capture the real, current
    # before-state and assert it is unchanged after, rather than
    # hardcoding a stale "HOME can never show R2 content" assumption.
    home_had_r2_full_before = real_home.is_file() and "leaderboard-table--r2-full" in real_home.read_text(encoding="utf-8")

    result = module.run_cycle(live=False, build_id="REAL_STATE_CHECK")
    # REAL_R2/R2_PUBLICATION_READY are generic dry-run-convention values
    # scripts/112's own _summary() always reports for live=False,
    # regardless of prior published state -- not a claim about the real
    # site's actual current content.
    assert result["REAL_R2"] == "WAIT"
    assert result["R2_PUBLICATION_READY"] is False
    if was_real_before:
        assert result["R2_SNAPSHOT"] == "CREATED"
        assert result["POST_R2_FORECAST"] == "CREATED"
    else:
        assert result["R2_SNAPSHOT"] == "NOT_CREATED"
        assert result["POST_R2_FORECAST"] == "NOT_CREATED"

    if real_r2_page.is_file():
        after = real_r2_page.read_text(encoding="utf-8")
        if was_real_before:
            assert is_real_page(after) is True  # never regressed to WAIT by a dry run
        else:
            assert is_wait_page(after) is True

    if real_home.is_file():
        home_html = real_home.read_text(encoding="utf-8")
        # A dry run must never advance OR regress HOME's mirrored
        # stage -- whatever it showed before this dry run, it must
        # show identically after.
        assert ("leaderboard-table--r2-full" in home_html) == home_had_r2_full_before
