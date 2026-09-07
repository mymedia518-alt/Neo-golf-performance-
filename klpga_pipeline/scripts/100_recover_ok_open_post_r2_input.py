from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_active_tournament_context  # noqa: E402
# NEO TOURNAMENT PIPELINE: game_code resolved from the shared context
# instead of this script's own hardcoded literal -- see
# src/klpga/tournament_context.py.
GAME_CODE = load_active_tournament_context().game_code

pre_path = SRC / "OK_OPEN_2026_PRE_WIN_FORECAST.json"
master_path = SRC / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json"

pre = json.loads(pre_path.read_text(encoding="utf-8"))
master = json.loads(master_path.read_text(encoding="utf-8"))

records = pre["records"]

if pre.get("game_code") != GAME_CODE:
    raise SystemExit("HARD STOP: wrong game_code")

if pre.get("model_version") != "M4":
    raise SystemExit("HARD STOP: unexpected PRE model")

if pre.get("future_data_excluded") is not True:
    raise SystemExit("HARD STOP: future-data exclusion not confirmed")

if len(records) != 120:
    raise SystemExit(f"HARD STOP: expected 120 PRE players, got {len(records)}")

ids = [str(r["player_id"]) for r in records]

if len(ids) != len(set(ids)):
    raise SystemExit("HARD STOP: duplicate PRE player_id")

if any(r.get("win_probability") is None for r in records):
    raise SystemExit("HARD STOP: null PRE win_probability")

out = {
    "schema_version": 1,
    "artifact": "OK_OPEN_2026_POST_R2_INPUT",
    "game_code": GAME_CODE,
    "stage": "POST_R2_PRE_FINAL",
    "model_version": pre["model_version"],
    "pre_cutoff": pre["cutoff"],
    "future_data_excluded": True,
    "pre_source": str(pre_path.name),
    "master_source": str(master_path.name),
    "pre_field_size": len(records),
    "records": records,
}

out_path = SRC / "OK_OPEN_2026_POST_R2_INPUT.json"
out_path.write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("=== POST-R2 INPUT RECOVERY ===")
print("GAME:", out["game_code"])
print("MODEL:", out["model_version"])
print("PRE CUTOFF:", out["pre_cutoff"])
print("PRE FIELD:", out["pre_field_size"])
print("DUPLICATES:", len(ids) - len(set(ids)))
print("NULL WIN:", sum(r.get("win_probability") is None for r in records))
print("FUTURE DATA EXCLUDED:", out["future_data_excluded"])
print("WROTE:", out_path)
