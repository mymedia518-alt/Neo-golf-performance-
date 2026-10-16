"""R1's own dedicated, persisted forecast file for 아이스버그골프·서울신문
오픈 (game_code 2026100003) -- exact same technique as
klpga.neo_win.hitejinro_round_pipeline.write_post_r1_forecast(), whose
own docstring establishes the precedent this script follows verbatim:
no round_update_r1 module exists anywhere in this codebase (confirmed
2026-10-03 for 하이트진로, re-confirmed here for 2026100003 by the same
exhaustive search) -- the relational M4 round-conditioning engine
(klpga.neo_win.round_update_r2/r3) only starts at R2 and REQUIRES real
R1+R2 scores together, so it structurally cannot produce an R1-only
forecast.

R1's real forecast is therefore the frozen PRE M4 model
(ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json) itself, persisted here
UNCHANGED under its own R1-specific filename -- never a new model,
never values recalculated from the real R1 scores NEO Sync just
collected. This is not a shortcut invented for this tournament: it is
the one documented, already-shipped answer this codebase gives for
every tournament's own R1 page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GAME_CODE = "2026100003"
CONTENT = ROOT / "content" / "website_v2"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"
POST_R1_FORECAST_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R1_FORECAST.json"


def main() -> None:
    m4 = json.loads(M4_CANDIDATE_PATH.read_text(encoding="utf-8"))
    if m4.get("gameCode") != GAME_CODE:
        raise SystemExit(f"{M4_CANDIDATE_PATH} gameCode mismatch: {m4.get('gameCode')!r} != {GAME_CODE!r}")

    records = [
        {
            "player_id": str(r["playerCode"]),
            "player_name": r["playerName"],
            "win_probability": r["win_probability"],
            "top5_probability": r["top5_probability"],
            "top10_probability": r["top10_probability"],
            "top20_probability": r["top20_probability"],
            "cut_probability": r["cut_probability"],
        }
        for r in m4.get("records", [])
        if r.get("analysis_status") == "PASS"
    ]

    out = {
        "artifact": "iceberg_2026100003_post_r1_forecast",
        "game_code": GAME_CODE,
        "source_round": 1,
        "source_model": (
            "frozen PRE M4 -- no round_update_r1 module exists in this codebase "
            "(same precedent as klpga.neo_win.hitejinro_round_pipeline.write_post_r1_forecast's "
            "own docstring); values are NOT recalculated from the real R1 scores."
        ),
        "source_file": str(M4_CANDIDATE_PATH.relative_to(ROOT.parent)),
        "source_generated_at": m4.get("generated_at"),
        "simulation_count": m4.get("simulation_count"),
        "random_seed": m4.get("random_seed"),
        "model_version": m4.get("model_version"),
        "records": records,
    }
    POST_R1_FORECAST_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(POST_R1_FORECAST_PATH),
        "records": len(records),
        "pass_count": len(records),
        "total_candidate_rows": len(m4.get("records", [])),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
