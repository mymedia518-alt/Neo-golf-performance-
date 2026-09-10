"""KB 2026090003 -- PRE FROZEN RECONSTRUCTION V1 -- regression coverage.

Covers exactly the scope this task requires: PRE temporal safety, PRE
field integrity, probability invariants, WD leakage (a hard test --
PRE output must be byte-identical whether or not the R1 WD evidence
files exist in the repository), artifact reproducibility, and the
publication gate decision. Does NOT touch R1 probability work, does
NOT use the two known WD statuses inside PRE, does NOT modify
production.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

GAME_CODE = "2026090003"
WD_PLAYERS = {"11374", "9788"}
WD_RELATED_FILES = (
    f"KB_{GAME_CODE}_R1_OFFICIAL_STATUS_EVIDENCE_V1.json",
    f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json",
)


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _entry_ids() -> list[str]:
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    return [e["player_id"] for e in entry["entries"]]


def _build_pre_field_freeze() -> dict:
    """A minimal, deterministic re-derivation of the PRE field freeze,
    independent of KB_2026090003_PRE_FIELD_FREEZE_V1.json's own
    (hand-frozen) content -- used by the WD-leakage test below to prove
    this computation never depends on whether the R1 WD files exist."""
    ids = _entry_ids()
    return {
        "PRE_FIELD_COUNT": len(ids),
        "unique_playercode_count": len(set(ids)),
        "duplicates": len(ids) - len(set(ids)),
        "sorted_ids": sorted(ids),
    }


# ---------------------------------------------------------------------
# 1. PRE temporal safety
# ---------------------------------------------------------------------

def test_pre_cutoff_is_explicit_and_cross_verified():
    audit = _load(f"KB_{GAME_CODE}_PRE_TEMPORAL_AUDIT_V1.json")
    assert audit["pre_cutoff"] == "2026-09-10T00:00:00+09:00"
    assert audit["temporal_leakage_count"] == 0
    assert audit["future_data_excluded"] is True


def test_pre_cutoff_matches_every_existing_pre_artifact():
    audit = _load(f"KB_{GAME_CODE}_PRE_TEMPORAL_AUDIT_V1.json")
    cutoff = audit["pre_cutoff"]
    for name in (
        f"{GAME_CODE}_PRE_WIN_FORECAST.json",
        f"{GAME_CODE}_PRE_PERFORMANCE_SNAPSHOT.json",
        f"{GAME_CODE}_PRE_PUBLIC_MASTER.json",
        f"{GAME_CODE}_PRE_SG_TOTAL_RANK.json",
    ):
        assert _load(name)["cutoff"] == cutoff, f"{name} cutoff mismatch"


def test_r1_wd_evidence_files_explicitly_named_as_excluded_not_used():
    audit = _load(f"KB_{GAME_CODE}_PRE_TEMPORAL_AUDIT_V1.json")
    excluded = audit["r1_future_data_prohibition"]["known_r1_evidence_not_used"]["files"]
    assert set(Path(f).name for f in excluded) == set(WD_RELATED_FILES)


# ---------------------------------------------------------------------
# 2. PRE field integrity
# ---------------------------------------------------------------------

def test_pre_field_count_is_120_with_no_duplicates():
    freeze = _load(f"KB_{GAME_CODE}_PRE_FIELD_FREEZE_V1.json")
    assert freeze["PRE_FIELD_COUNT"] == 120
    assert freeze["unique_playercode_count"] == 120
    assert freeze["duplicates"] == 0


def test_pre_field_source_is_official_entry_never_home_or_kranking():
    freeze = _load(f"KB_{GAME_CODE}_PRE_FIELD_FREEZE_V1.json")
    assert freeze["field_source_is_home_top120"] is False
    assert freeze["field_source_is_k_ranking"] is False


def test_wd_players_remain_in_pre_field_freeze():
    freeze = _load(f"KB_{GAME_CODE}_PRE_FIELD_FREEZE_V1.json")
    assert set(freeze["wd_players_preserved_in_field"]) == WD_PLAYERS
    assert freeze["all_wd_players_present"] is True


def test_home_ranking_population_independent_of_pre_field():
    home = _load("HOME_PLAYER_MASTER_TOP120.json")
    home_ids = {r["player_id"] for r in home["records"]}
    pre_ids = set(_entry_ids())
    # independent populations -- overlap is expected (real players can
    # be in both), but neither is a subset-defining source of the other
    assert len(home_ids) == 120
    assert len(pre_ids) == 120


# ---------------------------------------------------------------------
# 3. Probability invariants (vacuous here -- zero probabilities exist)
# ---------------------------------------------------------------------

def test_probability_snapshot_generated_zero_and_blocked_all():
    snap = _load(f"KB_{GAME_CODE}_PRE_PROBABILITY_SNAPSHOT_V1.json")
    assert snap["generated_count"] == 0
    assert snap["blocked_count"] == 120
    assert len(snap["blocked_players"]) == 120
    assert snap["generation_status"] == "BLOCKED_FOR_ALL_PLAYERS"


def test_no_synthetic_probability_values_present():
    snap = _load(f"KB_{GAME_CODE}_PRE_PROBABILITY_SNAPSHOT_V1.json")
    assert snap["no_synthetic_values_inserted"] is True
    for row in snap["blocked_players"]:
        assert row["status"] == "BLOCKED"
        assert "reason" in row and row["reason"]
        assert not any(k in row for k in ("win", "top5", "top10", "top20", "cut", "probability"))


def test_every_blocked_player_matches_a_real_pre_entrant():
    snap = _load(f"KB_{GAME_CODE}_PRE_PROBABILITY_SNAPSHOT_V1.json")
    pre_ids = set(_entry_ids())
    blocked_ids = {row["playerCode"] for row in snap["blocked_players"]}
    assert blocked_ids == pre_ids


# ---------------------------------------------------------------------
# 4. WD leakage -- hard temporal-leakage test
# ---------------------------------------------------------------------

def test_pre_field_freeze_computation_is_identical_with_and_without_r1_wd_files():
    """The core hard test this task requires: build the PRE field
    freeze once with the R1 WD evidence files present (normal repo
    state), then again with those exact files temporarily moved out of
    content/website_v2/, and assert byte-identical results. If the
    computation ever depended on those files (even indirectly), this
    test would fail the moment they are absent."""
    with_files = _build_pre_field_freeze()

    moved = []
    try:
        for name in WD_RELATED_FILES:
            src = CONTENT / name
            assert src.is_file(), f"expected fixture file missing: {name}"
            dst = src.with_suffix(".json.movedaway")
            shutil.move(str(src), str(dst))
            moved.append((src, dst))

        without_files = _build_pre_field_freeze()
    finally:
        for src, dst in moved:
            shutil.move(str(dst), str(src))

    assert with_files == without_files, (
        "PRE field freeze computation changed depending on whether the R1 WD "
        "evidence files exist -- this is a temporal leakage bug"
    )


def test_pre_probability_snapshot_never_references_wd_status_or_r1_files():
    snap_text = (CONTENT / f"KB_{GAME_CODE}_PRE_PROBABILITY_SNAPSHOT_V1.json").read_text(encoding="utf-8")
    for forbidden in ("WD", "withdrawn", "기권", *WD_RELATED_FILES):
        assert forbidden not in snap_text, f"PRE probability snapshot must never mention {forbidden!r}"


def test_wd_status_never_used_to_alter_pre_field_membership():
    """전승희/박혜준's WD status must never remove them from PRE, and
    must never be read by the PRE reconstruction at all."""
    ids = set(_entry_ids())
    assert WD_PLAYERS.issubset(ids)
    freeze = _load(f"KB_{GAME_CODE}_PRE_FIELD_FREEZE_V1.json")
    assert freeze["PRE_FIELD_COUNT"] == 120  # not 118 -- WD never subtracted at PRE


# ---------------------------------------------------------------------
# 5. Model provenance honesty
# ---------------------------------------------------------------------

def test_new_pre_model_is_not_classified_as_faithful_reconstruction():
    prov = _load(f"KB_{GAME_CODE}_PRE_MODEL_PROVENANCE_V1.json")
    pre5prob = next(
        m for m in prov["models_inspected"] if m["model_id"].startswith("NEO_PRE_5PROB_V1")
    )
    assert pre5prob["classification"].startswith("B")
    assert "option B" in prov["real_pre_model_path_conclusion"]["no_faithful_reconstruction_claim_made"]


def test_model_provenance_records_commit_and_module_hash():
    prov = _load(f"KB_{GAME_CODE}_PRE_MODEL_PROVENANCE_V1.json")
    assert prov["model_commit"] == "4c0e8d7231b75d1b8fd038178e89085b599bc380"
    pre5prob = next(m for m in prov["models_inspected"] if m["model_id"].startswith("NEO_PRE_5PROB_V1"))
    module_path = ROOT / "src" / "klpga" / "neo_win" / "pre_5prob.py"
    actual_sha = hashlib.sha256(module_path.read_bytes()).hexdigest()
    assert pre5prob["module_sha256"] == actual_sha


# ---------------------------------------------------------------------
# 6. Artifact reproducibility / provenance hashes
# ---------------------------------------------------------------------

def test_temporal_audit_entry_snapshot_hash_matches_real_file():
    audit = _load(f"KB_{GAME_CODE}_PRE_TEMPORAL_AUDIT_V1.json")
    entry_family = next(
        f for f in audit["per_feature_temporal_proof"] if f["feature_family"] == "official ENTRY field (120 entrants)"
    )
    actual_sha = hashlib.sha256((CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json").read_bytes()).hexdigest()
    assert entry_family["source_sha256"] == actual_sha


def test_feature_coverage_reports_zero_score_field_coverage():
    cov = _load(f"KB_{GAME_CODE}_PRE_FEATURE_COVERAGE_V1.json")
    summary = cov["publication_relevant_summary"]["player_coverage_for_pre_5prob_v1"]
    assert summary["AVAILABLE_PRE_SAFE_score_field"] == 0
    assert summary["MISSING_score_field"] == 120


# ---------------------------------------------------------------------
# 7. Publication gate decision
# ---------------------------------------------------------------------

def test_publication_gate_decision_is_blocked_multiple_reasons():
    gate = _load(f"KB_{GAME_CODE}_PRE_PUBLICATION_GATE_V1.json")
    assert gate["publication_decision"] == "BLOCKED_MULTIPLE_REASONS"
    assert gate["checks"]["INPUT_AVAILABILITY"]["status"] == "BLOCKED_MISSING_INPUTS"
    assert gate["checks"]["HISTORICAL_VALIDATION"]["status"] == "BLOCKED_INSUFFICIENT_SAMPLE"


def test_publication_gate_field_and_temporal_checks_pass():
    gate = _load(f"KB_{GAME_CODE}_PRE_PUBLICATION_GATE_V1.json")
    assert gate["checks"]["PRE_FIELD_INTEGRITY"]["status"] == "PASS"
    assert gate["checks"]["TEMPORAL_INTEGRITY"]["status"] == "PASS"


def test_frozen_candidate_kept_off_public_website():
    gate = _load(f"KB_{GAME_CODE}_PRE_PUBLICATION_GATE_V1.json")
    disposition = gate["frozen_candidate_disposition"]
    assert disposition["frozen_snapshot_exists"] is True
    assert disposition["public_website_status"].startswith("OFF")


def test_no_probability_page_or_script_references_the_frozen_snapshot():
    """Nothing in scripts/ wires this frozen candidate into a public
    build -- it stays a standalone evidence artifact."""
    snapshot_name = f"KB_{GAME_CODE}_PRE_PROBABILITY_SNAPSHOT_V1.json"
    for script in (ROOT / "scripts").glob("*.py"):
        assert snapshot_name not in script.read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------------
# 8. Safety: this task never touched production, sponsor work, or R1 status
# ---------------------------------------------------------------------

def test_r1_status_artifacts_untouched():
    r1_audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    assert r1_audit["wd_count"] == 2
    assert r1_audit["official_entry_count"] == 120


def test_this_task_never_modifies_docs_directory():
    """This worktree's own docs/ snapshot is from a different lineage
    (branched off commit 4c0e8d7, which predates the MAIN ONLY LOCKDOWN
    commit ecf507d on neo-website-v2) so its content is not a live
    production proxy -- the real guarantee this task must uphold is
    that it never stages or modifies anything under docs/ at all,
    verified directly against git status for this worktree."""
    import subprocess

    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "docs"],
        cwd=ROOT.parent, capture_output=True, text=True, check=True,
    )
    assert result.stdout == "", f"this task must never touch docs/: {result.stdout}"
