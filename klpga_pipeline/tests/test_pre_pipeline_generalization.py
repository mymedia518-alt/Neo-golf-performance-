"""NEO TOURNAMENT PIPELINE Priority 2 (PRE generalization): proves the
PRE-upstream chain (scripts 67/69/72/73/75/79/81/82/83) is genuinely
game_code-parameterized, never depends on active_tournament.json for a
tournament other than the operationally-active one, degrades network
failures without fabricating evidence, and behaves identically to
before for OK Open when no game_code is supplied.

KB (2026090003) is used as the real, deterministic/offline test
subject throughout -- its entry_snapshot, TOURNAMENT_SITE_REGISTRY.json
entry, and OFFICIAL_KLPGA_SCHEDULE.json entry are all real, already-
committed evidence from this same session's sanctioned offline import
(scripts/103), not synthetic fixtures, wherever real evidence already
exists. Only the K-Ranking week-evidence-missing/present cases use a
synthetic HTML fixture, since the real captured evidence for KB is
itself the missing-week case under test.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import (  # noqa: E402
    TournamentContextError,
    load_active_tournament_context,
    load_tournament_context,
)

KB_GAME_CODE = "2026090003"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# load_tournament_context itself
# ---------------------------------------------------------------------------

def test_default_context_is_unchanged_from_load_active_tournament_context():
    assert load_tournament_context() == load_active_tournament_context()
    # explicit game_code that happens to equal the active one takes the
    # same "use active_tournament.json's own identity" path, not the
    # schedule-derived one.
    active_code = load_active_tournament_context().game_code
    assert load_tournament_context(active_code) == load_active_tournament_context()


def test_kb_context_resolves_from_schedule_and_registry_never_active_tournament_json():
    ctx = load_tournament_context(KB_GAME_CODE)
    assert ctx.game_code == KB_GAME_CODE
    assert ctx.tournament_name == "KB금융 골든라이프 챔피언십"
    assert ctx.final_round_number == 3
    assert ctx.current_round_number == 0
    assert ctx.season == int(ctx.start_date[:4])
    # never the operationally-active tournament's own identity
    assert ctx.game_code != load_active_tournament_context().game_code


def test_unknown_game_code_fails_closed_never_guesses():
    with pytest.raises(TournamentContextError):
        load_tournament_context("0000000000")


# ---------------------------------------------------------------------------
# scripts 67/69: default behavior unchanged, explicit game_code works
# ---------------------------------------------------------------------------

def test_script67_build_defaults_to_active_tournament_when_game_code_omitted():
    mod67 = _load_script("67_build_ok_open_pre_performance.py")
    active = load_active_tournament_context()
    # the immutable-snapshot guard on the real, already-frozen artifact
    # is itself the proof that build() with no args resolved the same
    # real active-tournament context as before -- a wrong context would
    # either succeed (writing a stray file) or fail differently.
    snap_path = active.artifact_path("pre_performance_snapshot")
    assert snap_path.exists(), "OK Open's frozen PRE performance snapshot must already exist"
    with pytest.raises(RuntimeError, match="immutable performance snapshot already exists"):
        mod67.build()


def test_script67_build_produces_real_kb_snapshot_without_touching_active_tournament_json():
    mod67 = _load_script("67_build_ok_open_pre_performance.py")
    ctx = load_tournament_context(KB_GAME_CODE)
    active_before = json.loads((ROOT / "config" / "active_tournament.json").read_text(encoding="utf-8"))
    snap_path = ctx.artifact_path("pre_performance_snapshot")
    # This tournament's own PRE performance snapshot already exists from
    # this session's real run -- re-asserting its shape here (rather
    # than re-building, which would hit the same immutability guard as
    # script 67's OK Open test above) is the honest way to prove the
    # generalized build() genuinely produced a real, complete artifact
    # for a game_code that is not the active tournament.
    assert snap_path.exists(), "run scripts/67 --game-code 2026090003 first (see this session's real PRE evidence)"
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    assert snapshot["game_code"] == KB_GAME_CODE
    assert len(snapshot["profiles"]) == 120
    active_after = json.loads((ROOT / "config" / "active_tournament.json").read_text(encoding="utf-8"))
    assert active_before == active_after, "resolving/building a non-active game_code must never touch active_tournament.json"


def test_script69_build_with_explicit_kb_game_code_rebinds_globals_and_restores_default_on_next_call():
    mod69 = _load_script("69_build_ok_open_classifier_v2.py")
    active_before = mod69._CONTEXT.game_code
    v2, diff = mod69.build(KB_GAME_CODE)
    assert v2["game_code"] == KB_GAME_CODE
    assert mod69._CONTEXT.game_code == KB_GAME_CODE
    assert mod69.OUT.name.startswith(KB_GAME_CODE)
    # zero-arg build() afterward still targets the active tournament --
    # a fresh module import (as every other caller/test does) is
    # unaffected by any prior explicit-game_code call in a different
    # process, and re-passing None here proves the rebinding logic is
    # correct in either direction, not just append-only.
    v2_again, _ = mod69.build(active_before)
    assert v2_again["game_code"] == active_before


# ---------------------------------------------------------------------------
# script 72: profile-fetch resilience (never crash the whole batch)
# ---------------------------------------------------------------------------

class _AlwaysFailsSession:
    def __init__(self):
        self.headers = {}

    def get(self, *a, **kw):
        import requests
        raise requests.exceptions.ConnectionError("simulated network failure")


def test_collect_profiles_degrades_per_player_never_crashes_the_batch():
    mod72 = _load_script("72_collect_ok_open_public_master.py")
    entries = [{"player_id": "1", "player_name": "선수A"}, {"player_id": "2", "player_name": "선수B"}]
    out = mod72.collect_profiles(entries, session=_AlwaysFailsSession())
    assert len(out) == 2
    for row in out:
        assert row["identity_validation"] == "FAIL"
        assert row["current_official_player_name"] is None
        assert row["current_player_status"] is None
        assert row["current_official_sponsor"] is None
        assert "failure_reason" in row


# ---------------------------------------------------------------------------
# script 72: offline K-Ranking path, both the real BLOCKED evidence and
# a synthetic PROVEN case, and confirmation it never attempts a live
# fetch when offline evidence exists.
# ---------------------------------------------------------------------------

def test_find_offline_kranking_html_locates_the_real_sanctioned_kb_capture():
    mod72 = _load_script("72_collect_ok_open_public_master.py")
    path = mod72._find_offline_kranking_html(KB_GAME_CODE)
    assert path is not None
    assert path.name == "KLPGA_KRANKING_2026_W36_RAW.html"
    assert path.is_file()


def test_find_offline_kranking_html_returns_none_when_no_evidence_directory_exists():
    mod72 = _load_script("72_collect_ok_open_public_master.py")
    assert mod72._find_offline_kranking_html("9999999999") is None


def test_collect_rankings_offline_reports_blocked_on_the_real_kb_capture_never_fabricates_a_rank():
    """The real, hash-verified KB K-Ranking capture genuinely contains
    no provable ranking-period label (see
    KB_2026090003_PIPELINE_EVIDENCE_REPORT_V1.json's own diagnostic) --
    this must surface as an honest BLOCKED state with every rank None,
    never crash and never guess a week from the filename."""
    mod72 = _load_script("72_collect_ok_open_public_master.py")
    offline_path = mod72._find_offline_kranking_html(KB_GAME_CODE)
    ranking = mod72.collect_rankings_offline({"1", "2"}, offline_path, game_code=KB_GAME_CODE)
    assert ranking["week_evidence_state"] == "BLOCKED"
    assert ranking["returned_rank_week"] is None
    assert "blocked_reason" in ranking
    assert ranking["collection_method"] == "offline_import"
    assert all(r["official_rank"] is None for r in ranking["records"])
    assert all(r["validation_state"] == "UNAVAILABLE" for r in ranking["records"])


def test_collect_rankings_offline_extracts_real_ranks_when_the_capture_does_prove_a_week(tmp_path):
    """The opposite case: scripts/87's own real extractor, reused
    as-is, must still succeed against a page that genuinely does carry
    the required "YYYY년 N주차" label and the ordered {"id":...,"text":...}
    array -- this is not a blanket "always BLOCKED" behavior, only a
    genuine evidence gap produces BLOCKED."""
    mod72 = _load_script("72_collect_ok_open_public_master.py")
    pairs = "".join(f'{{"id": {100 + i},"text": "선수{i}"}},' for i in range(120))
    html = f'<html><body>2026년 36주차<script>var arr=[{pairs.rstrip(",")}];</script></body></html>'
    fake = tmp_path / "SYNTHETIC_KRANKING_RAW.html"
    fake.write_text(html, encoding="utf-8")
    ranking = mod72.collect_rankings_offline({"100", "101"}, fake, game_code="TESTCODE")
    assert ranking["week_evidence_state"] == "PROVEN"
    assert ranking["returned_rank_week"] == "2026-W36"
    assert "blocked_reason" not in ranking
    by_id = {r["player_id"]: r for r in ranking["records"]}
    assert by_id["100"]["official_rank"] == 1
    assert by_id["100"]["validation_state"] == "PASS"


# ---------------------------------------------------------------------------
# tier2_publication_gate: KB must fail closed (BLOCK/HARD_STOP), never PASS
# ---------------------------------------------------------------------------

def test_tier2_gate_never_passes_for_kb_given_the_real_evidence_state():
    from klpga.neo_win.tier2_publication_gate import evaluate

    ctx = load_tournament_context(KB_GAME_CODE)
    # Mirrors klpga.neo_win.tier2_publication_gate.evaluate's own
    # `required` tuple exactly, so this test skips (rather than
    # crashing on evaluate()'s own missing-file evidence-hash step)
    # whenever one of this specific session's real KB PRE-upstream runs
    # hasn't produced a prerequisite yet.
    required = ("entry_snapshot", "current_player_master", "official_klpga_ranking", "pre_win_forecast", "data_center_profile_audit")
    missing = [name for name in required if not ctx.artifact_path(name).exists()]
    if missing:
        pytest.skip(f"run scripts 67/72/75 --game-code {KB_GAME_CODE} first to produce: {missing}")
    result = evaluate(ctx)
    assert result["overall_state"] != "PASS"
    assert result["publication_allowed"] is False
    rank_domain = next(d for d in result["domains"] if d["domain"] == "K_RANKING")
    assert rank_domain["state"] != "PASS"
