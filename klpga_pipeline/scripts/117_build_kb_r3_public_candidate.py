"""Furnish the existing KB R3 page from frozen official evidence only."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r3_real_page import render_r3_real_page  # noqa: E402
from klpga.neo_win.r3_rendered_output_gate import validate_r3_rendered_output  # noqa: E402

GAME = "2026090003"
FINAL = ROOT / "evidence" / "KB_2026090003_R3" / "KB_2026090003_R3_OFFICIAL_FINAL.json"
R2 = ROOT / "content" / "website_v2" / f"{GAME}_R2_FROZEN_EVIDENCE.json"
# ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-v1-
# 20260912): the R3 page must show the genuine POST-R3 -> FR forecast,
# never the frozen POST-R2 forecast (which was itself built with a
# now-corrected round-count defect -- see
# 2026090003_POST_R2_FORECAST_AUDIT_CLASSIFICATION.json). The frozen
# POST-R2 artifact is preserved byte-for-byte and never read here.
FORECAST = ROOT / "content" / "website_v2" / f"{GAME}_POST_R3_FINAL_FORECAST.json"
SPONSORS = ROOT / "content" / "website_v2" / f"KB_{GAME}_SPONSOR_INTEGRITY_AUDIT_V2.json"
OUT = REPO / "docs" / "tournaments" / "2026" / GAME / "r3" / "index.html"
JOINED = ROOT / "evidence" / "KB_2026090003_R3" / "KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json"


def main() -> None:
    final = json.loads(FINAL.read_text(encoding="utf-8"))
    r2 = {str(r.get("playerCode", r.get("player_id"))): r for r in json.loads(R2.read_text(encoding="utf-8"))["records"]}
    forecast = json.loads(FORECAST.read_text(encoding="utf-8"))
    sponsor_by_id = {}
    if SPONSORS.is_file():
        audit = json.loads(SPONSORS.read_text(encoding="utf-8"))
        sponsor_by_id = {str(r["player_id"]): r["sponsor"] for r in audit.get("newly_recovered_sponsors", [])}
    records = []
    for row in final["rows"]:
        pid = str(row["playerCode"])
        status = row.get("raw_status") or "ACTIVE"
        prior = r2.get(pid, {})
        # r3_score_to_par: real strokes minus 72 -- par 72 independently
        # confirmed (not assumed) by cross-checking every sampled
        # player's raw-evidence data-totunderpar against
        # r1_score_to_par + r2_score_to_par + (r3_strokes-72); see
        # scripts/126's own module docstring for the full check.
        r3_score_to_par = (float(row["r3_score"]) - 72.0) if status == "ACTIVE" and row.get("r3_score") is not None else None
        records.append({
            "player_id": pid,
            "player_name": row["playerName"],
            "status": status,
            "r1_score_to_par": prior.get("r1_score_to_par"),
            "r2_score_to_par": prior.get("r2_score_to_par"),
            "r3_score_to_par": r3_score_to_par,
            "r3_strokes": row.get("r3_score"),
            "total_strokes": row.get("cumulative_score"),
        })
    if len(records) != 71 or sum(r["status"] == "WD" for r in records) != 1:
        raise SystemExit("frozen R3 truth contract failed")
    JOINED.write_text(json.dumps({
        "gameCode": GAME, "round": 3, "r3_status": final.get("r3_status"),
        "source_artifact": FINAL.name, "r2_source_artifact": R2.name,
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    html = render_r3_real_page(
        tournament_name="KB금융 골든라이프 챔피언십",
        game_code=GAME,
        date_range="2026.09.10–2026.09.13",
        r3_freeze={"records": records},
        forecast=forecast,
        sponsor_by_id=sponsor_by_id,
    )
    validate_r3_rendered_output(html, {"records": records}, forecast)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(OUT), "players": len(records), "wd": [r["player_id"] for r in records if r["status"] == "WD"], "forecast_build_id": forecast.get("build_id"), "simulations": forecast.get("n_simulations")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
