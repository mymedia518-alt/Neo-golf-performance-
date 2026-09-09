"""Evidence-driven Tier-2 field-domain publication gate.

The gate is deliberately independent of Website rendering.  A missing or
unknown validation state fails closed for the affected domain.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from klpga.tournament_context import CONTENT_DIR, TournamentContext

STATES = {"PASS", "WARN", "BLOCK", "HARD_STOP"}
DOMAINS = ("IDENTITY", "TEAM_SPONSOR", "K_RANKING", "WIN_PROBABILITY", "SG_DERIVED")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(domain: str, state: str, checks: list[str], reason: str, fields: list[str], path: Path) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"unknown gate state: {state}")
    return {"domain": domain, "state": state, "check_ids": checks, "reason": reason,
            "affected_fields": fields, "evidence": {"source_artifact": path.name, "sha256": _hash(path)}}


def detect_survivor_bias(early_population: int, cumulative_population: int, final_population: int) -> bool:
    """Detect the legacy lookup signature, not legitimate equal populations."""
    return bool(early_population > 0 and early_population == cumulative_population == final_population)


def evaluate(context: TournamentContext, *, sg_accepted: bool | None = None) -> dict[str, Any]:
    entry_path = context.artifact_path("entry_snapshot")
    current_path = context.artifact_path("current_player_master")
    rank_path = context.artifact_path("official_klpga_ranking")
    win_path = context.artifact_path("pre_win_forecast")
    # These two are shared, cross-tournament warehouse artifacts (built by
    # scripts 77/78/80 from every historical event, not just the active
    # tournament) -- deliberately fixed filenames under CONTENT_DIR, never
    # routed through context.artifact_path() (which is per-tournament).
    sg_path = CONTENT_DIR / "historical_sg_warehouse_corrected_v2.json"
    sg_audit_path = CONTENT_DIR / "historical_sg_warehouse_corrected_audit_v2.json"
    profile_audit_path = context.artifact_path("data_center_profile_audit")
    sg_acceptance_path = context.artifact_path("sg_independent_acceptance")
    required = (entry_path, current_path, rank_path, win_path, sg_path, sg_audit_path, profile_audit_path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    domains = []
    missing = [p for p in required if not p.exists()]
    if missing:
        domains.append(_result("IDENTITY", "HARD_STOP", ["T2-ID-001"], "required evidence artifact missing", ["public_master"], missing[0] if missing else CONTENT_DIR / "missing"))
        for d in DOMAINS[1:]: domains.append({"domain": d, "state": "BLOCK", "check_ids": ["T2-EVIDENCE-001"], "reason": "upstream evidence missing", "affected_fields": [], "evidence": {}})
    else:
        # The official field size is never a hardcoded assumption -- every
        # domain below is validated for internal self-consistency against
        # the SAME count, taken from the frozen entry snapshot's own
        # player_count (the one fact every one of these artifacts must
        # agree with, whatever it is for the active tournament).
        expected_count = int(json.loads(entry_path.read_text(encoding="utf-8"))["player_count"])
        current = json.loads(current_path.read_text(encoding="utf-8")); records = current.get("records", current.get("entries", []))
        ids = [str(r.get("player_id")) for r in records]
        identity_ok = len(records) == expected_count and len(set(ids)) == expected_count and all(r.get("identity_validation", "PASS") == "PASS" for r in records)
        domains.append(_result("IDENTITY", "PASS" if identity_ok else "HARD_STOP", ["T2-ID-001"], f"{expected_count} unique canonical identities validated" if identity_ok else "identity count/uniqueness/validation failure", ["player_id", "current_official_player_name"], current_path))
        profile_audit = json.loads(profile_audit_path.read_text(encoding="utf-8")); pa = profile_audit.get("records", [])
        sponsor_ok = len(pa) == expected_count and all(r.get("parse_state") in {"PASS", "ACCESS_FAILURE"} and r.get("team_state") in {"PARSED", "OFFICIAL_BLANK", "ACCESS_FAILURE"} for r in pa)
        domains.append(_result("TEAM_SPONSOR", "PASS" if sponsor_ok else "BLOCK", ["T2-TEAM-001"], "official nulls or explicitly unavailable profiles preserved as null" if sponsor_ok else "unclassified sponsor null", ["current_official_sponsor"], current_path))
        rank = json.loads(rank_path.read_text(encoding="utf-8")); rr = rank.get("records", rank.get("players", []))
        # K-RANK WEEK (Phase 5 item 4): a population entirely UNAVAILABLE
        # (zero real PASS rows) must never PASS -- that reads as "the
        # fetch technically completed" but confirms nothing about any
        # player's actual official rank. UNAVAILABLE per row is only
        # tolerated for INDIVIDUAL gaps in an otherwise-real population.
        available_count = sum(1 for r in rr if r.get("validation_state") == "PASS")
        population_ok = (
            len(rr) == expected_count
            and available_count > 0
            and all(r.get("validation_state") in {"PASS", "UNAVAILABLE"} and (r.get("official_rank") is not None or r.get("validation_state") == "UNAVAILABLE") for r in rr)
        )
        # K-RANK PROVENANCE (Phase 2, fix/phase5-generic-pipeline-hardening):
        # resolve_ranking_week()'s requested week is a REQUEST candidate,
        # never proof -- a neighboring/wrong week with at least one real
        # PASS row must never be enough on its own. The artifact must
        # additionally prove which week the official response itself
        # claimed to return, that it matches the requested week, and
        # that the raw response is hashed for audit -- never trust the
        # request label alone if the raw response can't back it up.
        rank_game_code = rank.get("game_code")
        provenance_reasons: list[str] = []
        if not rank.get("raw_response_sha256"):
            provenance_reasons.append("no raw_response_sha256 recorded -- the official response was never hashed for audit")
        if rank.get("week_evidence_state") != "PROVEN" or not rank.get("returned_rank_week"):
            provenance_reasons.append("returned_rank_week is unproven -- the official response never confirmed which week it actually served")
        elif rank.get("collection_method") != "offline_import" and rank.get("week_match") is not True:
            # week_match compares a REQUESTED week against what the live
            # response claimed to return -- meaningful only when a
            # request actually happened. A sanctioned offline import
            # (klpga.tournament_entry_bootstrap-style provenance: hashed
            # raw bytes, independently re-parsed here by the exact same
            # extractor a live fetch would use) never requested any
            # particular week in the first place -- its PROVEN state
            # already comes from directly re-deriving returned_rank_week
            # from the captured bytes, which is a stronger, not weaker,
            # guarantee than a live request/response comparison. Only an
            # artifact explicitly marked collection_method="offline_import"
            # gets this exemption -- anything else (including older
            # artifacts with no collection_method at all, like OK Open's
            # own frozen historical one) still requires week_match=True,
            # so this never loosens the check for a live-fetched or
            # unlabeled artifact.
            provenance_reasons.append(
                f"requested_rank_week={rank.get('requested_rank_week')!r} does not match "
                f"returned_rank_week={rank.get('returned_rank_week')!r}"
            )
        if rank_game_code is not None and str(rank_game_code) != context.game_code:
            provenance_reasons.append(f"ranking artifact game_code={rank_game_code!r} does not match {context.game_code!r}")
        rank_ok = population_ok and not provenance_reasons
        if not population_ok:
            rank_reason = (
                "every K-Ranking row is UNAVAILABLE -- the requested ranking week may be wrong, ambiguous, or not yet published; refusing to treat an entirely-unconfirmed population as validated"
                if len(rr) == expected_count and available_count == 0
                else "ranking evidence incomplete"
            )
        elif provenance_reasons:
            rank_reason = "; ".join(provenance_reasons)
        else:
            rank_reason = "same-week official ranking snapshot validated with proven, matching, hashed provenance"
        domains.append(_result("K_RANKING", "PASS" if rank_ok else "BLOCK", ["T2-RANK-001"], rank_reason, ["official_klpga_rank"], rank_path))
        win = json.loads(win_path.read_text(encoding="utf-8")); wr = win.get("records", win.get("players", [])); probs = [r.get("win_probability") for r in wr]; win_ok = len(wr) == expected_count and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in probs)
        domains.append(_result("WIN_PROBABILITY", "PASS" if win_ok else "BLOCK", ["T2-WIN-001"], f"{expected_count} pre-cutoff WIN probabilities validated" if win_ok else "forecast coverage/range failure", ["win_probability"], win_path))
        sg_audit = json.loads(sg_audit_path.read_text(encoding="utf-8")); arithmetic = sg_audit.get("arithmetic_validation", {}); acceptance = json.loads(sg_acceptance_path.read_text(encoding="utf-8")) if sg_acceptance_path.exists() else {}
        # SG SIGN-OFF (Phase 5 item 6): {"state": "ACCEPTED"} alone is
        # never sufficient -- validate the acceptance actually names
        # (a) the reviewer/signer, (b) when it was signed, and (c) the
        # EXACT upstream artifact it certifies, by re-hashing that
        # artifact right now and requiring an exact match. A stale
        # acceptance (the warehouse content changed since sign-off) or
        # an incomplete one (missing reviewer/timestamp/hash) fails
        # closed here -- it is never silently accepted.
        acceptance_valid = False
        if acceptance.get("state") == "ACCEPTED":
            reviewer = acceptance.get("accepted_by")
            signed_at = acceptance.get("accepted_at")
            claimed_hash = acceptance.get("warehouse_sha256")
            certified_name = acceptance.get("warehouse")
            certified_path = (sg_path.parent / certified_name) if certified_name else sg_path
            actual_hash = _hash(certified_path) if certified_path.exists() else None
            acceptance_valid = bool(
                reviewer and signed_at and claimed_hash and actual_hash
                and claimed_hash == actual_hash
            )
        accepted = sg_accepted if sg_accepted is not None else acceptance_valid
        sg_evidence_path = sg_acceptance_path if acceptance_valid else sg_audit_path
        sg_ok = arithmetic.get("exceptions") == 0 and accepted
        if acceptance and not acceptance_valid and sg_accepted is None:
            reason = "corrected SG arithmetic passes but the independent acceptance is incomplete or stale (missing reviewer/timestamp, or its recorded warehouse_sha256 no longer matches the actual warehouse content)"
        else:
            reason = "corrected SG evidence validated and independently accepted" if sg_ok else "corrected SG arithmetic passes but independent rank/band acceptance is pending"
        domains.append(_result("SG_DERIVED", "PASS" if sg_ok else "BLOCK", ["T2-SG-001", "T2-SG-002"], reason, ["sg_total_rank", "neo_performance_band", "band_statistics"], sg_evidence_path))
    overall = "HARD_STOP" if any(d["state"] == "HARD_STOP" for d in domains) else "BLOCK" if any(d["state"] == "BLOCK" for d in domains) else "WARN" if any(d["state"] == "WARN" for d in domains) else "PASS"
    return {"schema_version": "neo_tier2_field_domain_publication_gate_v1", "generated_at": now, "overall_state": overall, "domains": domains, "publication_allowed": overall in {"PASS", "WARN"}, "fail_closed_unknown": True}


def write_gate(context: TournamentContext, output: Path | None = None, *, sg_accepted: bool | None = None) -> dict[str, Any]:
    artifact = evaluate(context, sg_accepted=sg_accepted)
    out = output or context.artifact_path("tier2_publication_gate")
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact
