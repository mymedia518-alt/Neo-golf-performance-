"""Post-R1 SG forecast for 제6회 대보 하우스디 챔피언십 (game_code
2026110001), built the same way S-OIL's own post-round forecasts
(scripts/279, scripts/283) already were: feed the SAME engine
(klpga.neo_win.sg_pre_v1.estimate_player_sg_forecasts, unmodified)
the field's full prior SG history PLUS this tournament's own just-
completed round(s)' real official SG, so the forecast used to simulate
the rounds that remain is informed by how each player has actually hit
the ball at this course/week, not just their season-long prior.

Unlike S-OIL's post-R2 stage, Daebo has no confirmed 36-hole cut (see
scripts/307's own docstring) -- every one of the 60 real Round 1
finishers is still eligible for Round 2 onward, so this script does no
cut gating at all; it only produces an updated per-player
PlayerSGForecast, in the exact same schema scripts/305's own PRE
forecast already uses, so scripts/307 can load either file
interchangeably.

Inputs:
  - The same 2026-season single-round SG corpus scripts/305's own PRE
    forecast already loads (load_2026_sg_round_history) plus S-OIL's
    four 2026100001 rounds appended by hand (same post-Oct-18 gap
    scripts/305 documents) -- i.e. scripts/305's own build() history,
    reused rather than re-derived.
  - DAEBO_2026110001_R1_SG_OFFICIAL_V1.json (scripts/311): this
    tournament's own real, official Round 1 SG for all 60 entrants.

Output: DAEBO_2026110001_POST_R1_FORECAST_V1.json (same PlayerSGForecast
field shape as the PRE forecast).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.sg_pre_v1 import (  # noqa: E402
    SG_HALF_LIFE_DAYS,
    SG_PRIOR_ROUNDS,
    SG_VOLATILITY_PRIOR_DF,
    estimate_player_sg_forecasts,
    load_2026_sg_round_history,
)

GAME_CODE = "2026110001"
CONTENT = ROOT / "content" / "website_v2"
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json"
INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
R1_SG_PATH = CONTENT / f"DAEBO_{GAME_CODE}_R1_SG_OFFICIAL_V1.json"
OUT_PATH = CONTENT / f"DAEBO_{GAME_CODE}_POST_R1_FORECAST_V1.json"

CUTOFF_DATE = "2026-11-07"  # Round 2's own start date -- only rows strictly before this are used.
R1_DATE = "2026-11-06"

_SOIL_ROUNDS = (
    (1, CONTENT / "SOIL_2026100001_R1_SG_OFFICIAL_V1.json", "2026-10-29"),
    (2, CONTENT / "SOIL_2026100001_R2_SG_OFFICIAL_V1.json", "2026-10-30"),
    (3, CONTENT / "SOIL_2026100001_R3_SG_OFFICIAL_V1.json", "2026-10-31"),
    (4, CONTENT / "SOIL_2026100001_FR_SG_OFFICIAL_V1.json", "2026-11-01"),
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_round_sg(path: Path, *, game_code: str, round_number: int, round_date: str) -> list[dict]:
    doc = _load(path)
    rows = []
    for r in doc["records"]:
        if r.get("total") is None or not r.get("player_id"):
            continue
        rows.append({
            "player_id": str(r["player_id"]),
            "total": float(r["total"]),
            "game_code": game_code,
            "round": round_number,
            "scope": "single_round",
            "date": round_date,
            "season": 2026,
        })
    return rows


def build(*, cutoff_date: str) -> dict:
    info = _load(INFO_PATH)
    entry = _load(ENTRY_PATH)
    entries = entry["records"]
    game_code = str(info["game_code"])
    if game_code != GAME_CODE or len(entries) != 60:
        raise RuntimeError(f"Unexpected Daebo identity/field: {game_code}, {len(entries)}")
    player_ids = [str(row["player_code"]) for row in entries]
    if len(set(player_ids)) != len(player_ids):
        raise RuntimeError("Duplicate player IDs in the official Daebo entry list")

    history, source_summary = load_2026_sg_round_history(CONTENT)
    for round_number, path, round_date in _SOIL_ROUNDS:
        history.extend(_load_round_sg(path, game_code="2026100001", round_number=round_number, round_date=round_date))
    own_r1 = _load_round_sg(R1_SG_PATH, game_code=GAME_CODE, round_number=1, round_date=R1_DATE)
    if len(own_r1) != 60:
        raise RuntimeError(f"expected 60 own-R1 SG rows, found {len(own_r1)}")
    history.extend(own_r1)
    history.sort(key=lambda row: (row["date"], row["game_code"], int(row["round"]), str(row["player_id"])))

    forecasts = estimate_player_sg_forecasts(
        player_ids,
        history,
        cutoff_date=cutoff_date,
        half_life_days=SG_HALF_LIFE_DAYS,
        prior_rounds=SG_PRIOR_ROUNDS,
        volatility_prior_df=SG_VOLATILITY_PRIOR_DF,
    )

    has_forecast = sum(1 for f in forecasts.values() if f.has_player_sg)
    population_fallback = [pid for pid, f in forecasts.items() if not f.has_player_sg]

    out = {
        "schema_version": 1,
        "game_code": GAME_CODE,
        "stage": "POST_R1",
        "tournament_name": info["event_name"],
        "model": "klpga.neo_win.sg_pre_v1.estimate_player_sg_forecasts",
        "cutoff_date": cutoff_date,
        "half_life_days": SG_HALF_LIFE_DAYS,
        "prior_rounds": SG_PRIOR_ROUNDS,
        "volatility_prior_df": SG_VOLATILITY_PRIOR_DF,
        "history_source_summary": source_summary,
        "own_r1_sg_rows": len(own_r1),
        "history_rows_used": len(history),
        "field_size": len(player_ids),
        "players_with_real_sg_history": has_forecast,
        "players_on_population_fallback": population_fallback,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            "entry_snapshot": _sha256(ENTRY_PATH),
            "tournament_info": _sha256(INFO_PATH),
            "own_r1_sg_official": _sha256(R1_SG_PATH),
            **{f"soil_r{rn}_sg": _sha256(path) for rn, path, _ in _SOIL_ROUNDS},
        },
        "forecasts": [
            {
                "player_id": pid,
                "player_name": next((e["player_name"] for e in entries if str(e["player_code"]) == pid), None),
                "mean_sg": f.mean_sg,
                "round_sd": f.round_sd,
                "rounds": f.rounds,
                "events": f.events,
                "effective_rounds": f.effective_rounds,
                "latest_sg_date": f.latest_sg_date,
                "has_player_sg": f.has_player_sg,
            }
            for pid, f in sorted(forecasts.items())
        ],
    }
    return out


def main() -> None:
    out = build(cutoff_date=CUTOFF_DATE)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"field_size={out['field_size']} with_real_sg={out['players_with_real_sg_history']} "
          f"population_fallback={len(out['players_on_population_fallback'])}")


if __name__ == "__main__":
    main()
