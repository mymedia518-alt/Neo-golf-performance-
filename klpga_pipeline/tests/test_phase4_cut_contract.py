"""Phase 4 (fix/phase5-generic-pipeline-hardening): CUT CONTRACT
hardening.

Reproduced bug: infer_cut_validated() compared
`0 < advancing_field_size <= pre_field_size` -- the `<=` meant a
copied, unfiltered PRE roster relabeled as the cut result (same size
as the pre-cut field) still passed as CUT_CONFIRMED=True. This module
adds real, checkable provenance requirements (game_code binding, cut
round binding, a hash of the actual R2 snapshot the evidence claims to
be derived from, and real advancing-player identities rather than a
bare count) and fixes the comparison to strictly reject an unfiltered
field.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_lifecycle import infer_cut_validated  # noqa: E402

IDENTITY = {
    "game_code": "FIXTURECUT01",
    "tournament_name": "Fixture Cut Contract Open",
    "season": 2027,
    "start_date": "2027-07-01",
    "end_date": "2027-07-03",
    "final_round_number": 3,
    "current_round_number": 2,
}
REGISTRY = {
    "FIXTURECUT01": {
        "url_base": "/tournaments/2027/fixture-cut-open/",
        "stage_state_filename": "FIXTURE_CUT_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
}
FIELD = [f"P{i}" for i in range(1, 21)]  # 20-player synthetic field
ADVANCING = FIELD[:12]
EXCLUDED = FIELD[12:]


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def _write_r2_snapshot(tmp_path, *, round_number=2):
    payload = {
        "schema_version": "fixture_r2_v1",
        "game_code": "FIXTURECUT01",
        "round": round_number,
        "player_table": [
            {"player_id": p, "status": "ACTIVE"} for p in ADVANCING
        ] + [
            {"player_id": p, "status": "CUT"} for p in EXCLUDED
        ],
    }
    _write(tmp_path, "FIXTURECUT01_R2_LIVE_SNAPSHOT.json", payload)
    return hashlib.sha256((tmp_path / "FIXTURECUT01_R2_LIVE_SNAPSHOT.json").read_bytes()).hexdigest()


def _valid_post_r2_input(tmp_path, *, cut_evidence_sha256, cut_round=2, game_code="FIXTURECUT01",
                          advancing_ids=None, advancing_field_size=None, pre_field_size=None):
    advancing_ids = ADVANCING if advancing_ids is None else advancing_ids
    payload = {
        "schema_version": 1,
        "game_code": game_code,
        "cut_evidence_source": "FIXTURECUT01_R2_LIVE_SNAPSHOT.json",
        "cut_evidence_sha256": cut_evidence_sha256,
        "cut_round": cut_round,
        "pre_field_size": len(FIELD) if pre_field_size is None else pre_field_size,
        "advancing_field_size": len(advancing_ids) if advancing_field_size is None else advancing_field_size,
        "advancing_player_ids": advancing_ids,
        "records": [{"player_id": p} for p in advancing_ids],
    }
    _write(tmp_path, "FIXTURECUT01_POST_R2_INPUT.json", payload)
    return payload


def test_valid_cut_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    h = _write_r2_snapshot(tmp_path)
    _valid_post_r2_input(tmp_path, cut_evidence_sha256=h)
    assert infer_cut_validated(context, cut_after_round=2) is True


def test_copied_pre_field_rejected_when_advancing_equals_pre_size(tmp_path, monkeypatch):
    """The exact reproduced bug: advancing_field_size == pre_field_size
    (a copied, unfiltered PRE roster relabeled as the cut result) must
    never pass, even with an otherwise-valid hash/game_code/round."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    h = _write_r2_snapshot(tmp_path)
    _valid_post_r2_input(
        tmp_path, cut_evidence_sha256=h,
        advancing_ids=FIELD, advancing_field_size=len(FIELD), pre_field_size=len(FIELD),
    )
    assert infer_cut_validated(context, cut_after_round=2) is False


def test_count_only_evidence_without_identities_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    h = _write_r2_snapshot(tmp_path)
    payload = _valid_post_r2_input(tmp_path, cut_evidence_sha256=h)
    payload["advancing_player_ids"] = []  # count-only: no real identities
    _write(tmp_path, "FIXTURECUT01_POST_R2_INPUT.json", payload)
    assert infer_cut_validated(context, cut_after_round=2) is False


def test_wrong_game_code_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    h = _write_r2_snapshot(tmp_path)
    _valid_post_r2_input(tmp_path, cut_evidence_sha256=h, game_code="OTHERGAME0001")
    assert infer_cut_validated(context, cut_after_round=2) is False


def test_wrong_round_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    h = _write_r2_snapshot(tmp_path)
    _valid_post_r2_input(tmp_path, cut_evidence_sha256=h, cut_round=3)
    assert infer_cut_validated(context, cut_after_round=2) is False


def test_missing_snapshot_hash_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write_r2_snapshot(tmp_path)
    _valid_post_r2_input(tmp_path, cut_evidence_sha256="")
    assert infer_cut_validated(context, cut_after_round=2) is False


def test_stale_snapshot_hash_rejected(tmp_path, monkeypatch):
    """The recorded hash no longer matches the current R2 snapshot file
    (it was replaced/corrected since the cut evidence was recovered) --
    this must fail closed as stale, never silently trusted."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write_r2_snapshot(tmp_path)
    _valid_post_r2_input(tmp_path, cut_evidence_sha256="0" * 64)
    assert infer_cut_validated(context, cut_after_round=2) is False


def test_legitimate_no_cut_configuration_handled_explicitly(tmp_path, monkeypatch):
    """A tournament format with no cut at all (cut_after_round=None)
    must never be blocked waiting on cut evidence that will never
    exist -- this is a real, valid configuration, not an accident."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    # No post_r2_input artifact at all -- deliberately.
    assert infer_cut_validated(context, cut_after_round=None) is True


def test_missing_player_id_set_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    h = _write_r2_snapshot(tmp_path)
    payload = _valid_post_r2_input(tmp_path, cut_evidence_sha256=h)
    del payload["advancing_player_ids"]
    _write(tmp_path, "FIXTURECUT01_POST_R2_INPUT.json", payload)
    assert infer_cut_validated(context, cut_after_round=2) is False
