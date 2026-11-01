"""Reshape the real official FR (round 4) Strokes Gained collected for
제20회 S-OIL 챔피언십 (game_code 2026100001) via collect-r3-sg-oneoff.yml
(game_code=2026100001, round=4, against the real KLPGA
strokesGained_detail endpoint) into the same flat schema
SOIL_2026100001_R1/R2/R3_SG_OFFICIAL_V1.json already use.

This SG is collected and stored for the record only -- per the
tournament-end operating procedure, it must never be backdated into the
already-frozen SOIL_2026100001_POST_R3_FORECAST_V1.json (see the R3
archive manifest). It has no bearing on any forecast; it is purely a
post-tournament data asset.

Source: the collector's own published output on
collector-output/2026100001-r4 (__out/sg.json), pulled via `git show`
(the same cross-branch read pattern scripts/278/282/284 already use),
never downloaded or re-fetched by this script itself.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100001"
FR_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_FR_OFFICIAL_V1.json"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_FR_SG_OFFICIAL_V1.json"
SOURCE_BRANCH = f"collector-output/{GAME_CODE}-r4"


def _git_show(ref: str) -> str:
    return subprocess.run(
        ["git", "show", ref], cwd=REPO_ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
    ).stdout


def main() -> None:
    raw = json.loads(_git_show(f"origin/{SOURCE_BRANCH}:__out/sg.json"))
    rows = raw["records"]

    fr_official = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    expected_ids = {r["player_id"] for r in fr_official["records"]}
    assert fr_official["field_count"] == 68

    out_records = []
    for r in rows:
        pid = str(r["player_id"])
        out_records.append({
            "player_id": pid,
            "player_name": r["player"],
            "total": r["total"],
            "tee_to_green": r["tee_to_green"],
            "off_the_tee": r["off_the_tee"],
            "approach": r["approach"],
            "around_green": r["around_green"],
            "putting": r["putting"],
            "rounds": r["rounds"],
        })

    sg_ids = {r["player_id"] for r in out_records}
    assert sg_ids == expected_ids, (
        f"FR SG player set != FR official field. "
        f"SG-only: {sorted(sg_ids - expected_ids)}, official-only: {sorted(expected_ids - sg_ids)}"
    )
    assert len(out_records) == 68, f"expected 68 FR SG rows, found {len(out_records)}"

    tol_fail = [r for r in rows if not r.get("validation", {}).get("total_within_tolerance", False)]

    out = {
        "schema_version": "SOIL_2026100001_FR_SG_OFFICIAL_V1",
        "game_code": GAME_CODE,
        "source_url": "https://klpga.co.kr/load/leaderboard/strokesGained_detail (POST gameCode=2026100001&round=4)",
        "source_branch": SOURCE_BRANCH,
        "scope": "single_round",
        "round": 4,
        "stage_label": "FR",
        "metric": "total",
        "retrieved_at": raw["retrieved_at"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "usage_note": (
            "Record only -- never backdated into SOIL_2026100001_POST_R3_FORECAST_V1.json "
            "(frozen at content/website_v2/archive/2026100001/r3/ before this file existed) "
            "and never displayed as raw numbers on any public page."
        ),
        "records": out_records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "records": len(out_records),
        "matches_fr_official_field": sg_ids == expected_ids,
        "component_sum_tolerance_fail_count": len(tol_fail),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
