"""Generate a read-only, format-aware R2 readiness artifact."""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.neo_win.r2_readiness import assess_r2
from klpga.neo_win.stage_freeze_gate import stage_sequence_for_holes

ENTRY = ROOT / "content" / "website_v2" / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
OUT = ROOT / "content" / "website_v2" / "OK_OPEN_2026_R2_READINESS.json"

def main() -> int:
    entry = json.loads(ENTRY.read_text(encoding="utf-8"))
    ids = [str(row["player_id"]) for row in entry.get("entries", [])]
    decision = assess_r2([], ids, official_page_available=False)
    result = {
        "schema_version": "neo_ok_open_r2_readiness_v1",
        "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tournament": {"game_code": "2026120001", "total_holes": 54},
        "decision": decision.decision,
        "reason": decision.reason,
        "official_r2_available": False,
        "cut_inferred": False,
        "future_checkpoint_rows": 0,
        "expected_player_count": len(ids),
        "stage_sequence": list(stage_sequence_for_holes(54)),
        "operator_action_count": 0,
        "fast_lane": ["official R2 leaderboard", "completion/status/rank validation", "immutable R2 scoring freeze", "R2 prediction checkpoint"],
        "deep_lane_optional": ["official SG enrichment", "hole analytics"],
        "failure_recovery": {"page_unavailable": "WAIT", "partial_or_suspended": "WAIT", "identity_conflict": "HARD_STOP", "duplicate_player": "HARD_STOP", "freeze_exists": "HARD_STOP", "SG_unavailable": "SAFE_CONTINUE"},
        "provenance": {"entry_snapshot_sha256": hashlib.sha256(ENTRY.read_bytes()).hexdigest(), "source_state": "pre-event; no official R2 evidence exists"},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "reason": result["reason"], "stage_sequence": result["stage_sequence"]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
