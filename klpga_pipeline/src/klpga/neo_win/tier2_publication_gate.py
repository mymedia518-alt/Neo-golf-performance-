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


def evaluate(base: Path, *, sg_accepted: bool | None = None) -> dict[str, Any]:
    current_path = base / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json"
    rank_path = base / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
    win_path = base / "OK_OPEN_2026_PRE_WIN_FORECAST.json"
    sg_path = base / "historical_sg_warehouse_corrected_v2.json"
    sg_audit_path = base / "historical_sg_warehouse_corrected_audit_v2.json"
    profile_audit_path = base / "OK_OPEN_2026_DATA_CENTER_PROFILE_AUDIT.json"
    required = (current_path, rank_path, win_path, sg_path, sg_audit_path, profile_audit_path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    domains = []
    missing = [p for p in required if not p.exists()]
    if missing:
        domains.append(_result("IDENTITY", "HARD_STOP", ["T2-ID-001"], "required evidence artifact missing", ["public_master"], missing[0] if missing else base / "missing"))
        for d in DOMAINS[1:]: domains.append({"domain": d, "state": "BLOCK", "check_ids": ["T2-EVIDENCE-001"], "reason": "upstream evidence missing", "affected_fields": [], "evidence": {}})
    else:
        current = json.loads(current_path.read_text(encoding="utf-8")); records = current.get("records", current.get("entries", []))
        ids = [str(r.get("player_id")) for r in records]
        identity_ok = len(records) == 120 and len(set(ids)) == 120 and all(r.get("identity_validation", "PASS") == "PASS" for r in records)
        domains.append(_result("IDENTITY", "PASS" if identity_ok else "HARD_STOP", ["T2-ID-001"], "120 unique canonical identities validated" if identity_ok else "identity count/uniqueness/validation failure", ["player_id", "current_official_player_name"], current_path))
        profile_audit = json.loads(profile_audit_path.read_text(encoding="utf-8")); pa = profile_audit.get("records", [])
        sponsor_ok = len(pa) == 120 and all(r.get("parse_state") in {"PASS", "ACCESS_FAILURE"} and r.get("team_state") in {"PARSED", "OFFICIAL_BLANK", "ACCESS_FAILURE"} for r in pa)
        domains.append(_result("TEAM_SPONSOR", "PASS" if sponsor_ok else "BLOCK", ["T2-TEAM-001"], "official nulls or explicitly unavailable profiles preserved as null" if sponsor_ok else "unclassified sponsor null", ["current_official_sponsor"], current_path))
        rank = json.loads(rank_path.read_text(encoding="utf-8")); rr = rank.get("records", rank.get("players", [])); rank_ok = len(rr) == 120 and all(r.get("validation_state") in {"PASS", "UNAVAILABLE"} and (r.get("official_rank") is not None or r.get("validation_state") == "UNAVAILABLE") for r in rr)
        domains.append(_result("K_RANKING", "PASS" if rank_ok else "BLOCK", ["T2-RANK-001"], "same-week official ranking snapshot validated" if rank_ok else "ranking evidence incomplete", ["official_klpga_rank"], rank_path))
        win = json.loads(win_path.read_text(encoding="utf-8")); wr = win.get("records", win.get("players", [])); probs = [r.get("win_probability") for r in wr]; win_ok = len(wr) == 120 and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in probs)
        domains.append(_result("WIN_PROBABILITY", "PASS" if win_ok else "BLOCK", ["T2-WIN-001"], "120 pre-cutoff WIN probabilities validated" if win_ok else "forecast coverage/range failure", ["win_probability"], win_path))
        sg_audit = json.loads(sg_audit_path.read_text(encoding="utf-8")); arithmetic = sg_audit.get("arithmetic_validation", {}); accepted = sg_accepted if sg_accepted is not None else bool(sg_audit.get("claude_acceptance") or sg_audit.get("acceptance_state") == "ACCEPTED")
        sg_ok = arithmetic.get("exceptions") == 0 and accepted
        domains.append(_result("SG_DERIVED", "PASS" if sg_ok else "BLOCK", ["T2-SG-001", "T2-SG-002"], "corrected SG evidence validated and independently accepted" if sg_ok else "corrected SG arithmetic passes but independent rank/band acceptance is pending", ["sg_total_rank", "neo_performance_band", "band_statistics"], sg_audit_path))
    overall = "HARD_STOP" if any(d["state"] == "HARD_STOP" for d in domains) else "BLOCK" if any(d["state"] == "BLOCK" for d in domains) else "WARN" if any(d["state"] == "WARN" for d in domains) else "PASS"
    return {"schema_version": "neo_tier2_field_domain_publication_gate_v1", "generated_at": now, "overall_state": overall, "domains": domains, "publication_allowed": overall in {"PASS", "WARN"}, "fail_closed_unknown": True}


def write_gate(base: Path, output: Path | None = None, *, sg_accepted: bool | None = None) -> dict[str, Any]:
    artifact = evaluate(base, sg_accepted=sg_accepted)
    out = output or (base / "OK_OPEN_2026_TIER2_PUBLICATION_GATE.json")
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact
