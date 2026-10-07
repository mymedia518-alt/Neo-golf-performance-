"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- build the
canonical homepage identity file (선수명/공식 스폰서/국적/playerCode)
from the real, Windows-acquired entry reconciliation evidence
(evidence/hj_2026100004_entry_acquisition/RECONCILIATION_REPORT.json,
commit 9d40b92). No new network access, no new acquisition -- pure
reshaping of already-verified real data.

Carries forward, per player, exactly what was confirmed real:
  - player_code, player_name (from the official entry list)
  - nationality (from the entry list's own confirmed flag-image field)
  - official_sponsor (never a placeholder -- "" when the sponsor was
    checked and confirmed genuinely absent, same value as the entry
    acquisition's own real result; None is never produced here)
  - qualification_category / qualification_reason (the closest real
    "출전자 유형" field this page exposes -- no official entry_status/
    WD/DNS field has ever been confirmed to exist on this page)
  - identity_reconciliation_status (MATCHED_EXISTING / NEW_PLAYER --
    carried through unchanged, never re-decided here)

Does NOT compute or attach any Stableford rank, K-RANKING, or
"Stableford Fit" value -- this file is identity only."""
from __future__ import annotations

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
RECONCILIATION_PATH = (
    KLPGA_PIPELINE_ROOT / "evidence" / "hj_2026100004_entry_acquisition" / "RECONCILIATION_REPORT.json"
)
OUT_PATH = KLPGA_PIPELINE_ROOT / "content" / "website_v2" / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"

GAME_CODE = "2026100004"


def build() -> dict:
    report = json.loads(RECONCILIATION_PATH.read_text(encoding="utf-8"))
    records = []
    for r in report["records"]:
        records.append({
            "player_code": r["player_code"],
            "player_name": r["player_name"],
            "nationality": r["nationality"],
            "official_sponsor": r["sponsor"] if r["sponsor"] is not None else "",
            "qualification_category": r["qualification_category"],
            "qualification_reason": r["qualification_reason"],
            "identity_reconciliation_status": r["identity_reconciliation_status"],
        })
    return {
        "schema_version": 1,
        "game_code": GAME_CODE,
        "source_evidence": "evidence/hj_2026100004_entry_acquisition/RECONCILIATION_REPORT.json",
        "field_size_confirmed": report["page_reported_total_participants"],
        "entry_count": len(records),
        "new_players_not_in_any_existing_master": [
            r["player_code"] for r in records if r["identity_reconciliation_status"] == "NEW_PLAYER"
        ],
        "overseas_players": [
            r["player_code"] for r in records if r["nationality"] and r["nationality"] != "KOR"
        ],
        "records": records,
    }


def main() -> int:
    data = build()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"field_size_confirmed={data['field_size_confirmed']} entry_count={data['entry_count']}")
    print(f"new_players={data['new_players_not_in_any_existing_master']}")
    print(f"overseas_players={data['overseas_players']}")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
