"""Pre-tournament SG forecast for 제6회 대보 하우스디 챔피언십 (game_code
2026110001, 2026-11-06~11-08, KLPGA 2026 season finale), built on the
exact same engine as the S-OIL (2026100001) and prior 2026 tournaments'
PRE forecasts (klpga.neo_win.sg_pre_v1 -- unmodified).

load_2026_sg_round_history() only covers real SG rows up to and
including 2026-10-18 (see that function's own docstring/filter). Every
tournament played after that date must be appended by hand, same
discipline scripts/279/283 (S-OIL's own post-R2/post-R3 forecasts)
already use for S-OIL's own rounds. Between 2026-10-18 and this
tournament's 2026-11-06 start, exactly one real tournament occurred:
제20회 S-OIL 챔피언십 (2026100001, R1=10-29, R2=10-30, R3=10-31,
FR/R4=11-01) -- all four rounds' official SG are already collected and
committed (SOIL_2026100001_{R1,R2,R3,FR}_SG_OFFICIAL_V1.json). This
script appends all four, unmodified, before estimating forecasts for
Daebo's own 60-player field.

Output (SG-space forecast only -- cut_after_round/rounds/cut_position
for Daebo's actual 3-round, no 36-hole-cut format are applied later by
whichever script runs the live/pre simulation, not baked in here):
DAEBO_2026110001_PRE_SG_FORECAST_V1.json
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
OUT_PATH = CONTENT / f"DAEBO_{GAME_CODE}_PRE_SG_FORECAST_V1.json"

CUTOFF_DATE = "2026-11-06"  # Daebo's own start_date -- estimate_player_sg_forecasts
                            # only uses rows strictly before this.

# S-OIL (2026100001) rounds played after load_2026_sg_round_history's own
# 2026-10-18 cutoff -- real, already-collected, committed files.
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


def _load_soil_round_sg(path: Path, round_number: int, round_date: str) -> list[dict]:
    doc = _load(path)
    rows = []
    for r in doc["records"]:
        if r.get("total") is None or not r.get("player_id"):
            continue
        rows.append({
            "player_id": str(r["player_id"]),
            "total": float(r["total"]),
            "game_code": "2026100001",
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
        history.extend(_load_soil_round_sg(path, round_number, round_date))
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
        "tournament_name": info["event_name"],
        "model": "klpga.neo_win.sg_pre_v1.estimate_player_sg_forecasts",
        "cutoff_date": cutoff_date,
        "half_life_days": SG_HALF_LIFE_DAYS,
        "prior_rounds": SG_PRIOR_ROUNDS,
        "volatility_prior_df": SG_VOLATILITY_PRIOR_DF,
        "history_source_summary": source_summary,
        "history_rows_used": len(history),
        "field_size": len(player_ids),
        "players_with_real_sg_history": has_forecast,
        "players_on_population_fallback": population_fallback,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            "entry_snapshot": _sha256(ENTRY_PATH),
            "tournament_info": _sha256(INFO_PATH),
            **{
                f"soil_r{rn}_sg": _sha256(path)
                for rn, path, _ in _SOIL_ROUNDS
            },
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
