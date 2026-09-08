"""Phase 5 (Codex blocker remediation) regression tests.

Each test here reproduces one specific real Codex-rejection scenario
against 855ffa7 and pins the fixed behavior. These are deliberately
independent of test_sg_publication_blockers.py / test_tier2_publication_gate.py
/ test_4round_tournament_replay.py, which already cover several other
Phase 5 items (SG sign-off hash validation, K-Ranking all-PASS gate,
4-round next-round/FINAL->POSTMORTEM) against the real committed
artifacts -- this file focuses on the items those files do not reach:
PRE state contract partial-PRE behavior, K-Ranking all-UNAVAILABLE,
missing-DB fail-closed, dry-run immutability, promotion-route
derivation, leakage date resolution, and remaining scheduler literals.
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

from klpga import tournament_context as tc_module  # noqa: E402
from klpga import tournament_discovery  # noqa: E402
from klpga import tournament_pre_state as pre_state  # noqa: E402
from klpga.neo_win import tier2_publication_gate  # noqa: E402


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeContext:
    """Duck-typed TournamentContext: only game_code/tournament_name/
    start_date and a working artifact_path() are exercised by the
    functions under test here."""

    def __init__(self, tmp_path: Path, game_code: str = "9999990001"):
        self.game_code = game_code
        self.tournament_name = "Fixture Open"
        self.season = 9999
        self.start_date = "2099-01-01"
        self._root = tmp_path

    def artifact_path(self, artifact_type: str, *, ext: str = "json") -> Path:
        return self._root / f"{artifact_type}.{ext}"


# ---------------------------------------------------------------------------
# Item 3: PRE STATE CONTRACT -- artifact existence must never equal validated
# ---------------------------------------------------------------------------

def _write(ctx: _FakeContext, artifact_type: str, payload: dict) -> None:
    ctx.artifact_path(artifact_type).write_text(json.dumps(payload), encoding="utf-8")


def test_entry_validated_rejects_duplicate_player_ids(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {
        "entries": [{"player_id": "1"}, {"player_id": "1"}],
        "player_count": 2,
        "duplicate_player_ids": ["1"],
    })
    check = pre_state.validate_entry(ctx)
    assert check.valid is False
    assert any("duplicate" in r for r in check.reasons)


def test_entry_validated_rejects_unresolved_identity(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {
        "entries": [{"player_id": "1"}, {"player_id": "2"}],
        "player_count": 2,
        "identity_matched": True,
        "unresolved_player_ids": ["2"],
    })
    check = pre_state.validate_entry(ctx)
    assert check.valid is False
    assert any("unresolved identity" in r for r in check.reasons)


def test_entry_validated_passes_a_clean_snapshot(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {
        "entries": [{"player_id": "1", "identity_match": True}, {"player_id": "2", "identity_match": True}],
        "player_count": 2,
        "identity_matched": "player_master identity match attempted",
    })
    assert pre_state.validate_entry(ctx).valid is True


def test_partial_pre_run_never_reads_as_pre_inputs_validated(tmp_path):
    """A PRE run that crashed after writing entry_snapshot but before
    every upstream PRE artifact was produced must fail
    PRE_INPUTS_VALIDATED on the artifact that never got written --
    resuming from the incomplete stage, never silently PRE_READY."""
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    # Only one of the required PRE-upstream artifacts is present.
    _write(ctx, "pre_performance_snapshot", {"profiles": [{"player_id": "1"}]})
    check = pre_state.validate_pre_inputs(ctx)
    assert check.valid is False
    assert any("current_player_master" in r for r in check.reasons)


def test_pre_state_contract_pre_ready_is_false_when_any_check_fails(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    contract = pre_state.build_pre_state_contract(ctx, freeze_if_ready=False)
    assert contract.pre_ready is False
    assert contract.pre_inputs_validated.valid is False


# ---------------------------------------------------------------------------
# PRE contract fail-closed hardening (fix/phase5-pre-contract-gates-20260908)
# ---------------------------------------------------------------------------

def test_entry_validated_fails_when_identity_matching_was_not_performed(tmp_path):
    """The explicit "not attempted" sentinel, and/or every entry's own
    identity_match evidence being None, must FAIL -- never read as
    VALIDATED merely because unresolved_player_ids happens to be empty
    (klpga.tournament_entry_bootstrap leaves it empty in exactly this
    case, since it never even checked)."""
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {
        "entries": [
            {"player_id": "1", "identity_match": None},
            {"player_id": "2", "identity_match": None},
        ],
        "player_count": 2,
        "identity_matched": "not attempted (no player_master DB in this run)",
        "unresolved_player_ids": [],
    })
    check = pre_state.validate_entry(ctx)
    assert check.valid is False
    assert any("not attempted" in r or "not actually performed" in r for r in check.reasons)


def test_entry_validated_fails_on_partial_missing_identity_evidence(tmp_path):
    """Even when the top-level summary claims matching was attempted,
    any individual entry with no real identity_match evidence must
    still fail -- missing identity evidence is never accepted."""
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {
        "entries": [
            {"player_id": "1", "identity_match": True},
            {"player_id": "2", "identity_match": None},
        ],
        "player_count": 2,
        "identity_matched": "player_master identity match attempted",
        "unresolved_player_ids": [],
    })
    check = pre_state.validate_entry(ctx)
    assert check.valid is False
    assert any("no identity-match evidence" in r for r in check.reasons)


def _write_frozen_archive(root: Path, game_code: str, cutoff_date: str, payload: dict | str) -> Path:
    from klpga.neo_win.archive import archive_paths
    json_path, _ = archive_paths(root, "PRE", game_code, cutoff_date)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        json_path.write_text(payload, encoding="utf-8")
    else:
        json_path.write_text(json.dumps(payload), encoding="utf-8")
    return json_path


def _valid_frozen_payload(ctx: _FakeContext) -> dict:
    return {
        "game_code": ctx.game_code,
        "cutoff_date": ctx.start_date,
        "model_id": "M4",
        "model_version": "M4",
        "leakage_validation": {"future_data_excluded": True},
    }


def test_pre_features_frozen_fails_on_corrupted_non_json_archive(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    root = tmp_path / "predictions"
    _write_frozen_archive(root, ctx.game_code, ctx.start_date, "{not valid json")
    check = pre_state.validate_pre_features_frozen(ctx, predictions_root=root)
    assert check.valid is False
    assert any("not valid JSON" in r for r in check.reasons)


def test_pre_features_frozen_fails_on_wrong_game_code(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    root = tmp_path / "predictions"
    payload = _valid_frozen_payload(ctx)
    payload["game_code"] = "0000000000"
    _write_frozen_archive(root, ctx.game_code, ctx.start_date, payload)
    check = pre_state.validate_pre_features_frozen(ctx, predictions_root=root)
    assert check.valid is False
    assert any("game_code" in r for r in check.reasons)


def test_pre_features_frozen_fails_on_wrong_cutoff(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    root = tmp_path / "predictions"
    payload = _valid_frozen_payload(ctx)
    payload["cutoff_date"] = "1999-01-01"
    _write_frozen_archive(root, ctx.game_code, ctx.start_date, payload)
    check = pre_state.validate_pre_features_frozen(ctx, predictions_root=root)
    assert check.valid is False
    assert any("cutoff_date" in r for r in check.reasons)


def test_pre_features_frozen_fails_when_future_data_excluded_missing_or_false(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    root = tmp_path / "predictions"
    payload = _valid_frozen_payload(ctx)
    payload["leakage_validation"] = {"future_data_excluded": False}
    _write_frozen_archive(root, ctx.game_code, ctx.start_date, payload)
    check = pre_state.validate_pre_features_frozen(ctx, predictions_root=root)
    assert check.valid is False
    assert any("future_data_excluded" in r for r in check.reasons)

    root2 = tmp_path / "predictions2"
    payload2 = _valid_frozen_payload(ctx)
    del payload2["leakage_validation"]
    _write_frozen_archive(root2, ctx.game_code, ctx.start_date, payload2)
    check2 = pre_state.validate_pre_features_frozen(ctx, predictions_root=root2)
    assert check2.valid is False
    assert any("future_data_excluded" in r for r in check2.reasons)


def test_pre_features_frozen_passes_on_a_genuinely_matching_archive(tmp_path):
    ctx = _FakeContext(tmp_path)
    _write(ctx, "entry_snapshot", {"entries": [{"player_id": "1"}], "player_count": 1})
    root = tmp_path / "predictions"
    _write_frozen_archive(root, ctx.game_code, ctx.start_date, _valid_frozen_payload(ctx))
    check = pre_state.validate_pre_features_frozen(ctx, predictions_root=root)
    assert check.valid is True


def test_pre_ready_is_false_when_publication_fails_even_if_first_four_pass():
    """Data/model readiness alone must never be sufficient: with
    entry/inputs/features/model all PASS but publication FAIL,
    pre_ready must be False."""
    ok = pre_state.StateCheck.ok
    fail = pre_state.StateCheck.fail
    contract = pre_state.PreStateContract(
        entry_validated=ok("ENTRY_VALIDATED"),
        pre_inputs_validated=ok("PRE_INPUTS_VALIDATED"),
        pre_features_frozen=ok("PRE_FEATURES_FROZEN"),
        pre_model_validated=ok("PRE_MODEL_VALIDATED"),
        pre_publication_approved=fail("PRE_PUBLICATION_APPROVED", "no built PRE candidate"),
    )
    assert contract.pre_ready is False
    # And the inverse sanity check: all five PASS -> pre_ready True.
    contract_all_pass = pre_state.PreStateContract(
        entry_validated=ok("ENTRY_VALIDATED"),
        pre_inputs_validated=ok("PRE_INPUTS_VALIDATED"),
        pre_features_frozen=ok("PRE_FEATURES_FROZEN"),
        pre_model_validated=ok("PRE_MODEL_VALIDATED"),
        pre_publication_approved=ok("PRE_PUBLICATION_APPROVED"),
    )
    assert contract_all_pass.pre_ready is True


# ---------------------------------------------------------------------------
# Item 4: K-RANK WEEK -- an all-UNAVAILABLE K-Ranking population must never
# pass the publication gate.
# ---------------------------------------------------------------------------

_VALID_RANK_PROVENANCE = {
    "requested_rank_week": "2099-W01",
    "returned_rank_week": "2099-W01",
    "week_evidence_state": "PROVEN",
    "week_match": True,
    "raw_response_sha256": "a" * 64,
}


def _write_minimal_gate_fixtures(ctx: _FakeContext, monkeypatch, *, rank_records, sg_acceptance=None, rank_extra=None):
    monkeypatch.setattr(tier2_publication_gate, "CONTENT_DIR", ctx._root)
    _write(ctx, "entry_snapshot", {"player_count": 2})
    _write(ctx, "current_player_master", {"records": [
        {"player_id": "1", "identity_validation": "PASS"},
        {"player_id": "2", "identity_validation": "PASS"},
    ]})
    rank_payload = {**_VALID_RANK_PROVENANCE, **(rank_extra or {}), "records": rank_records}
    _write(ctx, "official_klpga_ranking", rank_payload)
    _write(ctx, "pre_win_forecast", {"records": [
        {"player_id": "1", "win_probability": 0.5},
        {"player_id": "2", "win_probability": 0.5},
    ]})
    (ctx._root / "historical_sg_warehouse_corrected_v2.json").write_text("{}", encoding="utf-8")
    (ctx._root / "historical_sg_warehouse_corrected_audit_v2.json").write_text(
        json.dumps({"arithmetic_validation": {"exceptions": 0}}), encoding="utf-8")
    _write(ctx, "data_center_profile_audit", {"records": [
        {"parse_state": "PASS", "team_state": "PARSED"},
        {"parse_state": "PASS", "team_state": "PARSED"},
    ]})
    if sg_acceptance is not None:
        _write(ctx, "sg_independent_acceptance", sg_acceptance)


def test_all_k_ranking_unavailable_never_passes_the_publication_gate(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch,
        rank_records=[
            {"player_id": "1", "validation_state": "UNAVAILABLE"},
            {"player_id": "2", "validation_state": "UNAVAILABLE"},
        ],
        sg_acceptance={"state": "ACCEPTED", "accepted_by": "x", "accepted_at": "2099-01-01T00:00:00Z",
                       "warehouse": "historical_sg_warehouse_corrected_v2.json",
                       "warehouse_sha256": __import__("hashlib").sha256(b"{}").hexdigest()},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"
    assert "UNAVAILABLE" in rank["reason"]


def test_k_ranking_with_at_least_one_real_pass_row_still_passes(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch,
        rank_records=[
            {"player_id": "1", "validation_state": "PASS", "official_rank": 5},
            {"player_id": "2", "validation_state": "UNAVAILABLE"},
        ],
        sg_acceptance={"state": "ACCEPTED", "accepted_by": "x", "accepted_at": "2099-01-01T00:00:00Z",
                       "warehouse": "historical_sg_warehouse_corrected_v2.json",
                       "warehouse_sha256": __import__("hashlib").sha256(b"{}").hexdigest()},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "PASS"


_DEFAULT_RANK_RECORDS = [
    {"player_id": "1", "validation_state": "PASS", "official_rank": 5},
    {"player_id": "2", "validation_state": "PASS", "official_rank": 12},
]


def test_k_ranking_passes_with_correct_requested_returned_week_and_hash(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch, rank_records=_DEFAULT_RANK_RECORDS,
        rank_extra={"requested_rank_week": "2099-W01", "returned_rank_week": "2099-W01",
                    "week_evidence_state": "PROVEN", "week_match": True, "raw_response_sha256": "a" * 64},
        sg_acceptance={"state": "ACCEPTED", "accepted_by": "x", "accepted_at": "2099-01-01T00:00:00Z",
                       "warehouse": "historical_sg_warehouse_corrected_v2.json",
                       "warehouse_sha256": __import__("hashlib").sha256(b"{}").hexdigest()},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "PASS"


def test_k_ranking_blocks_on_requested_returned_week_mismatch(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch, rank_records=_DEFAULT_RANK_RECORDS,
        rank_extra={"requested_rank_week": "2099-W01", "returned_rank_week": "2099-W02",
                    "week_evidence_state": "PROVEN", "week_match": False, "raw_response_sha256": "a" * 64},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"
    assert "does not match" in rank["reason"]


def test_k_ranking_blocks_when_returned_week_missing(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch, rank_records=_DEFAULT_RANK_RECORDS,
        rank_extra={"requested_rank_week": "2099-W01", "returned_rank_week": None,
                    "week_evidence_state": "UNPROVEN", "week_match": None, "raw_response_sha256": "a" * 64},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"
    assert "unproven" in rank["reason"]


def test_k_ranking_blocks_when_raw_hash_missing(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch, rank_records=_DEFAULT_RANK_RECORDS,
        rank_extra={"requested_rank_week": "2099-W01", "returned_rank_week": "2099-W01",
                    "week_evidence_state": "PROVEN", "week_match": True, "raw_response_sha256": None},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"
    assert "raw_response_sha256" in rank["reason"]


def test_k_ranking_blocks_on_wrong_adjacent_week_even_with_one_pass_row(tmp_path, monkeypatch):
    """A neighboring/wrong week that still happens to return one real
    PASS row must never be enough by itself -- population availability
    and week provenance are independent requirements."""
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch,
        rank_records=[
            {"player_id": "1", "validation_state": "PASS", "official_rank": 5},
            {"player_id": "2", "validation_state": "UNAVAILABLE"},
        ],
        rank_extra={"requested_rank_week": "2099-W01", "returned_rank_week": "2099-W52",
                    "week_evidence_state": "PROVEN", "week_match": False, "raw_response_sha256": "a" * 64},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"


def test_k_ranking_blocks_on_wrong_game_code(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch, rank_records=_DEFAULT_RANK_RECORDS,
        rank_extra={"game_code": "0000000000", "requested_rank_week": "2099-W01",
                    "returned_rank_week": "2099-W01", "week_evidence_state": "PROVEN",
                    "week_match": True, "raw_response_sha256": "a" * 64},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"
    assert "game_code" in rank["reason"]


def test_extract_returned_week_finds_selected_option_and_fallback_label():
    from klpga.kranking_week import extract_returned_week
    assert extract_returned_week('<select><option selected>2099년 3주</option></select>') == "2099-W03"
    assert extract_returned_week('<div>현재 랭킹 기준: 2099년 12주</div>') == "2099-W12"
    assert extract_returned_week('<html><body>no week here</body></html>') is None


# ---------------------------------------------------------------------------
# Item 6: SG SIGN-OFF -- {"state": "ACCEPTED"} alone must never be enough.
# ---------------------------------------------------------------------------

def test_sg_acceptance_missing_reviewer_fields_fails_closed(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch,
        rank_records=[{"player_id": "1", "validation_state": "PASS", "official_rank": 1},
                      {"player_id": "2", "validation_state": "PASS", "official_rank": 2}],
        sg_acceptance={"state": "ACCEPTED"},  # no reviewer/timestamp/hash
    )
    gate = tier2_publication_gate.evaluate(ctx)
    sg = next(d for d in gate["domains"] if d["domain"] == "SG_DERIVED")
    assert sg["state"] == "BLOCK"
    assert "stale" in sg["reason"] or "incomplete" in sg["reason"]


def test_sg_acceptance_with_stale_hash_fails_closed(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    _write_minimal_gate_fixtures(
        ctx, monkeypatch,
        rank_records=[{"player_id": "1", "validation_state": "PASS", "official_rank": 1},
                      {"player_id": "2", "validation_state": "PASS", "official_rank": 2}],
        sg_acceptance={"state": "ACCEPTED", "accepted_by": "x", "accepted_at": "2099-01-01T00:00:00Z",
                       "warehouse": "historical_sg_warehouse_corrected_v2.json",
                       "warehouse_sha256": "0" * 64},  # does not match the real file's hash
    )
    gate = tier2_publication_gate.evaluate(ctx)
    sg = next(d for d in gate["domains"] if d["domain"] == "SG_DERIVED")
    assert sg["state"] == "BLOCK"


def test_sg_acceptance_fully_signed_and_matching_hash_passes(tmp_path, monkeypatch):
    ctx = _FakeContext(tmp_path)
    import hashlib
    real_hash = hashlib.sha256(b"{}").hexdigest()
    _write_minimal_gate_fixtures(
        ctx, monkeypatch,
        rank_records=[{"player_id": "1", "validation_state": "PASS", "official_rank": 1},
                      {"player_id": "2", "validation_state": "PASS", "official_rank": 2}],
        sg_acceptance={"state": "ACCEPTED", "accepted_by": "reviewer-x", "accepted_at": "2099-01-01T00:00:00Z",
                       "warehouse": "historical_sg_warehouse_corrected_v2.json",
                       "warehouse_sha256": real_hash},
    )
    gate = tier2_publication_gate.evaluate(ctx)
    sg = next(d for d in gate["domains"] if d["domain"] == "SG_DERIVED")
    assert sg["state"] == "PASS"


# ---------------------------------------------------------------------------
# Item 5: PRE LEAKAGE -- event dates must be resolved from real,
# evidence-based per-game_code provenance; unmapped/future dates excluded.
# ---------------------------------------------------------------------------

def test_verified_event_dates_excludes_unmapped_and_is_keyed_by_game_code(tmp_path, monkeypatch):
    mod79 = _load_script("79_rebuild_corrected_sg_downstream.py")
    fake_mapping = tmp_path / "TOURNAMENT_K_WEEK_MAPPING_V1.json"
    fake_mapping.write_text(json.dumps({"records": [
        {"game_code": "2020010001", "start_date": "2020-01-05"},
        {"game_code": "2020020002", "start_date": None},  # no verified date
    ]}), encoding="utf-8")
    monkeypatch.setattr(mod79, "K_WEEK_MAPPING", fake_mapping)
    dates = mod79._verified_event_dates()
    assert dates == {"2020010001": "2020-01-05"}
    assert "2020020002" not in dates
    assert "2099990099" not in dates  # unmapped game_code has no verified date at all


def test_leakage_filter_excludes_rows_with_no_verified_date_or_on_after_cutoff(tmp_path, monkeypatch):
    mod82 = _load_script("82_build_corrected_sg_total_rank.py")
    fake_mapping = tmp_path / "TOURNAMENT_K_WEEK_MAPPING_V1.json"
    fake_mapping.write_text(json.dumps({"records": [
        {"game_code": "2020010001", "start_date": "2020-01-05"},  # before cutoff: included
        {"game_code": "2020120001", "start_date": "2020-12-31"},  # after cutoff: excluded
    ]}), encoding="utf-8")
    monkeypatch.setattr(mod82, "K_WEEK_MAPPING", fake_mapping)
    event_dates = mod82._verified_event_dates()
    cutoff = "2020-06-01"
    rows = [
        {"game_code": "2020010001", "player_id": "1", "scope": "tournament_cumulative"},
        {"game_code": "2020120001", "player_id": "1", "scope": "tournament_cumulative"},
        {"game_code": "2020999999", "player_id": "1", "scope": "tournament_cumulative"},  # unmapped
    ]
    kept = [
        r for r in rows
        if event_dates.get(str(r.get("game_code"))) is not None
        and event_dates[str(r.get("game_code"))] < cutoff
    ]
    assert [r["game_code"] for r in kept] == ["2020010001"]


# ---------------------------------------------------------------------------
# Item 2: NEW TOURNAMENT SOURCE EDITS = ZERO -- script 69's
# correction_timestamp must not special-case a hardcoded game_code.
# ---------------------------------------------------------------------------

def test_correction_timestamp_is_not_keyed_to_a_hardcoded_game_code():
    import ast
    import inspect
    mod69 = _load_script("69_build_ok_open_classifier_v2.py")
    tree = ast.parse(inspect.getsource(mod69._correction_timestamp))
    body_src = "\n".join(
        ast.unparse(node) for node in tree.body[0].body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    )
    assert "2026120001" not in body_src
    assert "2026-08-31" not in body_src


def test_correction_timestamp_is_preserved_across_rebuilds(tmp_path, monkeypatch):
    mod69 = _load_script("69_build_ok_open_classifier_v2.py")
    fake_out = tmp_path / "out.json"
    fake_out.write_text(json.dumps({"correction_timestamp": "2020-01-01T00:00:00Z"}), encoding="utf-8")
    monkeypatch.setattr(mod69, "OUT", fake_out)
    assert mod69._correction_timestamp() == "2020-01-01T00:00:00Z"


def test_correction_timestamp_is_fresh_for_a_tournament_with_no_prior_build(tmp_path, monkeypatch):
    mod69 = _load_script("69_build_ok_open_classifier_v2.py")
    monkeypatch.setattr(mod69, "OUT", tmp_path / "does_not_exist.json")
    ts = mod69._correction_timestamp()
    assert ts.endswith("Z")
    assert ts != "2020-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Item 11: DATABASE PROVISIONING -- missing canonical DB must fail closed,
# never silently create/use an empty one.
# ---------------------------------------------------------------------------

def test_discover_tournament_fails_closed_on_table_less_db_file(tmp_path):
    """A DB *file* existing (e.g. an empty file left behind by an earlier
    sqlite3.connect() against a not-yet-provisioned path -- exactly how
    data/klpga.sqlite ends up as 0 bytes in a fresh checkout) must never
    surface as a raw sqlite3.OperationalError; it must fail closed with
    TournamentDiscoveryBlocked so callers like
    resolve_or_bootstrap_lifecycle can fall back to the last validated
    lifecycle state instead of crashing the whole run."""
    from datetime import date

    from klpga.tournament_discovery import TournamentDiscoveryBlocked, discover_tournament

    empty_db = tmp_path / "empty.sqlite"
    empty_db.touch()  # a real, connectable, zero-table sqlite file
    with pytest.raises(TournamentDiscoveryBlocked, match="tournament_master table missing"):
        discover_tournament(empty_db, as_of=date(2099, 1, 1))


def test_missing_canonical_db_fails_closed_not_silently_created(tmp_path, monkeypatch):
    from dataclasses import dataclass, field

    mod = _load_script("70_ok_open_operational_readiness.py")

    @dataclass
    class _Listing:
        game_code: str
        game_title: str = "Fixture Open"
        start_date_raw: str = "20990101"
        end_date_raw: str = "20990103"
        course_text: str = "Fixture GC"
        out_course_text: str = ""
        in_course_text: str = ""
        prize_money: int = 0
        game_method: str = "0"
        game_finish: str = "N"
        raw: dict = field(default_factory=lambda: {"totalPar": 72, "totalRound": "3", "gameMethodName": "stroke-play"})

    monkeypatch.setattr(mod, "fetch_game_list", lambda client, season: [_Listing(game_code=mod.GAME)])
    monkeypatch.setattr(mod, "fetch_entry_list", lambda client, game_code: "<html></html>")

    from klpga.parsers.entry_list_parser import EntryListParseResult, EntryRow
    frozen = json.loads(mod.FROZEN_ENTRY.read_text(encoding="utf-8"))
    fixture_rows = [
        EntryRow(player_code=e["player_id"], player_name=e["player_name"],
                 nationality=None, qualification_category=None, qualification_reason=None)
        for e in frozen["entries"]
    ]
    monkeypatch.setattr(mod, "parse_entry_list_html",
                         lambda html: EntryListParseResult(rows=fixture_rows, unparsed_row_count=0, unparsed_samples=[]))

    missing_db = tmp_path / "does_not_exist.sqlite"
    monkeypatch.setattr(mod, "DB", missing_db)

    with pytest.raises(RuntimeError, match="canonical player_master database missing"):
        mod.main()
    assert not missing_db.exists()  # the guard must never create the file it just refused to use


# ---------------------------------------------------------------------------
# Item 12: DRY RUN -- must be side-effect free.
# ---------------------------------------------------------------------------

def test_refresh_active_config_dry_run_never_writes(tmp_path):
    import sqlite3
    from datetime import date

    db_path = tmp_path / "fixture.sqlite"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE tournament_master (game_code TEXT, event_name TEXT, season INTEGER, "
        "start_date TEXT, end_date TEXT, rounds_scheduled INTEGER)"
    )
    con.execute(
        "INSERT INTO tournament_master VALUES ('1', 'Fixture Open', 2099, '2099-01-01', '2099-01-05', 3)"
    )
    con.commit()
    con.close()

    active_path = tmp_path / "active_tournament.json"
    previous = {"schema_version": 2, "game_code": "1", "tournament_name": "x", "season": 2099,
                "start_date": "2099-01-01", "end_date": "2099-01-05", "final_round_number": 3,
                "current_round_number": 1, "validated_stage": "PRE_READY",
                "cut_after_round": None, "model_ready": False}
    active_path.write_text(json.dumps(previous), encoding="utf-8")
    before = active_path.read_bytes()

    result = tournament_discovery.refresh_active_config(
        db_path=db_path, config_path=active_path, as_of=date(2099, 1, 2), persist=False,
    )

    after = active_path.read_bytes()
    assert before == after, "dry-run must never modify active_tournament.json on disk"
    assert result["game_code"] == "1"  # the resolved payload is still returned for preview


def test_ensure_site_registry_entry_dry_run_never_writes(tmp_path, monkeypatch):
    registry_path = tmp_path / "TOURNAMENT_SITE_REGISTRY.json"
    original = {"schema_version": 1, "tournaments": {}}
    registry_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(tc_module, "SITE_REGISTRY_PATH", registry_path)
    before = registry_path.read_bytes()
    tc_module.ensure_site_registry_entry(
        {"game_code": "9999990001", "tournament_name": "Fixture Open", "season": 2099, "final_round_number": 3},
        dry_run=True,
    )
    after = registry_path.read_bytes()
    assert before == after, "dry-run must never modify the site registry on disk"


# ---------------------------------------------------------------------------
# Item 10: PUBLIC PROMOTION -- required routes must be derived from
# TournamentContext / the site registry, never a hardcoded OK/KG list.
# ---------------------------------------------------------------------------

def test_required_tournament_routes_are_derived_from_the_registry_not_hardcoded(tmp_path, monkeypatch):
    mod94 = _load_script("94_promote_top120_to_production.py")
    fake_registry = tmp_path / "TOURNAMENT_SITE_REGISTRY.json"
    fake_registry.write_text(json.dumps({"tournaments": {
        "1234560001": {
            "url_base": "/tournaments/2099/fixture-open/",
            "has_hub_index": True,
            "hub_card": {"nav_stages": ["pre", "r1", "final"]},
        }
    }}), encoding="utf-8-sig")
    monkeypatch.setattr(mod94, "SITE_REGISTRY_PATH", fake_registry)
    routes = mod94._required_tournament_routes()
    assert any(r.endswith("tournaments/2099/fixture-open/index.html") for r in routes)
    assert any("pre" in r for r in routes)
    assert any("r1" in r for r in routes)
    assert any("final" in r for r in routes)
    # A game_code that never existed at fixture-authoring time must not
    # need any source edit to be picked up -- the function BODY (not its
    # explanatory docstring, which legitimately references real
    # tournaments) must not hardcode a specific game_code or URL slug.
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(mod94._required_tournament_routes))
    body_src = "\n".join(ast.unparse(node) for node in tree.body[0].body if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant))
    assert "kg-ladies-open" not in body_src.lower()
    assert "ok-savings-bank-open" not in body_src.lower()
    assert "2026080001" not in body_src
    assert "2026120001" not in body_src


# ---------------------------------------------------------------------------
# Item 1: ACTIVE SCHEDULER -- no remaining C:\Users literals; the retired
# competing operator path must actually refuse to run.
# ---------------------------------------------------------------------------

REPO_ROOT = ROOT.parent


def test_no_scheduler_wrapper_hardcodes_a_windows_user_path():
    """Scans every .ps1/.bat operational script in the repo (not a fixed
    named list) so a newly-added Windows helper script can never silently
    reintroduce a machine-specific C:\\Users\\... path the way
    NEO_HISTORICAL_TRUTH_VALIDATE.bat and
    NEO_HISTORICAL_TRUTH_BLOCKER_RESOLUTION.bat once did."""
    checked = 0
    for path in list(REPO_ROOT.glob("*.ps1")) + list(REPO_ROOT.glob("*.bat")) + \
            list(REPO_ROOT.glob("klpga_pipeline/*.ps1")) + list(REPO_ROOT.glob("klpga_pipeline/*.bat")):
        checked += 1
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        assert "C:\\Users" not in text, f"{path.name} still hardcodes a Windows user path"
    assert checked > 0, "no .ps1/.bat operational scripts found to check"


def test_retired_competing_operator_script_refuses_to_run():
    path = REPO_ROOT / "NEO-GOLF-TOURNAMENT-OPERATOR.ps1"
    if not path.is_file():
        pytest.skip("operator script not present in this checkout")
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    assert "RETIRED" in text.upper()
    assert "exit 2" in text.lower() or "exit(2)" in text.lower()


def test_active_cycle_script_only_goes_live_on_explicit_opt_in():
    path = REPO_ROOT / "NEO-GOLF-R1-ACTIVE-30MIN.ps1"
    if not path.is_file():
        pytest.skip("active-cycle wrapper not present in this checkout")
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    assert "--live" in text


def test_installer_registers_the_canonical_wrapper_via_dynamic_repo_path():
    """Phase 6 (scheduler path): the installer's Task Scheduler action
    must be built from this script's own on-disk folder ($PSScriptRoot,
    never a machine-specific literal) and must point at the canonical
    NEO-GOLF-R1-ACTIVE-30MIN.ps1 -- never the retired
    NEO-GOLF-TOURNAMENT-OPERATOR.ps1 path. Inspects the source text only
    (command construction) -- never mutates a real Windows Task
    Scheduler, which does not exist in this Linux test environment."""
    path = REPO_ROOT / "NEO-GOLF-R1-INSTALL-SCHEDULE.ps1"
    if not path.is_file():
        pytest.skip("installer script not present in this checkout")
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    assert "$Repo = $PSScriptRoot" in text, "repo location must be derived dynamically, not hardcoded"
    assert "NEO-GOLF-R1-ACTIVE-30MIN.ps1" in text
    assert "NEO-GOLF-TOURNAMENT-OPERATOR.ps1" not in text, (
        "installer must never register the retired competing operator script"
    )
    assert "New-ScheduledTaskAction" in text and "$ScriptPath" in text
    assert "TaskName = 'NEO-GOLF-R1-ACTIVE-30MIN'" in text


def test_active_cycle_wrapper_dispatches_through_generic_run_tournament_entry_point():
    """The scheduled 30-minute wrapper must dispatch through the single
    generic entry point (run_tournament.py --live --git-push), never a
    hardcoded per-stage script (e.g. a direct call to
    96_ok_open_r1_active_cycle.py) -- that generic dispatch is what lets
    the same registered task keep running unattended across R1 -> R2 ->
    FINAL -> POSTMORTEM without ever needing re-registration."""
    path = REPO_ROOT / "NEO-GOLF-R1-ACTIVE-30MIN.ps1"
    if not path.is_file():
        pytest.skip("active-cycle wrapper not present in this checkout")
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    invocation_lines = [line for line in text.splitlines() if "= & $Python" in line or "&$Python" in line]
    assert invocation_lines, "no PowerShell python-invocation line found"
    assert any("run_tournament.py" in line for line in invocation_lines)
    assert any("--live" in line and "--git-push" in line for line in invocation_lines)
    assert not any("96_ok_open_r1_active_cycle.py" in line for line in invocation_lines), (
        "the actual dispatched command must be run_tournament.py, not a direct per-stage script call"
    )
