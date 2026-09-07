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
_CONTEXT = load_active_tournament_context()
GAME_CODE = _CONTEXT.game_code

pre_path = _CONTEXT.artifact_path("pre_win_forecast")
master_path = _CONTEXT.artifact_path("current_player_master")
entry_path = _CONTEXT.artifact_path("entry_snapshot")
r2_snapshot_path = _CONTEXT.artifact_path("r2_live_snapshot")

pre = json.loads(pre_path.read_text(encoding="utf-8"))
master = json.loads(master_path.read_text(encoding="utf-8"))
entry = json.loads(entry_path.read_text(encoding="utf-8"))

records = pre["records"]
# The expected PRE field size is the tournament's own frozen entry
# count, never a hardcoded literal -- a different tournament has a
# different official field size (Phase 5 item 2).
expected_field_size = int(entry["player_count"])

if pre.get("game_code") != GAME_CODE:
    raise SystemExit("HARD STOP: wrong game_code")

if pre.get("model_version") != "M4":
    raise SystemExit("HARD STOP: unexpected PRE model")

if pre.get("future_data_excluded") is not True:
    raise SystemExit("HARD STOP: future-data exclusion not confirmed")

if len(records) != expected_field_size:
    raise SystemExit(f"HARD STOP: expected {expected_field_size} PRE players (per entry_snapshot), got {len(records)}")

ids = [str(r["player_id"]) for r in records]

if len(ids) != len(set(ids)):
    raise SystemExit("HARD STOP: duplicate PRE player_id")

if any(r.get("win_probability") is None for r in records):
    raise SystemExit("HARD STOP: null PRE win_probability")

# CUT CONTRACT (Phase 5 item 8): the recovered "post-R2 input" field
# must be the ACTUAL advancing field per real official R2 evidence --
# never the unfiltered PRE forecast copied wholesale and relabeled.
# r2_live_snapshot (script 99's own output) already carries each
# player's real official status for this round; a player with no row
# there, or an explicit CUT/WD/DQ/DNS status, did not advance.
if not r2_snapshot_path.is_file():
    raise SystemExit(f"HARD STOP: no official R2 snapshot at {r2_snapshot_path} -- cannot validate the real cut/advancing field")
r2_snapshot = json.loads(r2_snapshot_path.read_text(encoding="utf-8"))
if r2_snapshot.get("game_code") != GAME_CODE:
    raise SystemExit("HARD STOP: R2 snapshot game_code mismatch")
_NON_ADVANCING_STATUSES = {"CUT", "WD", "DQ", "DNS"}
r2_status_by_id = {str(r.get("player_id")): str(r.get("status") or "").upper() for r in (r2_snapshot.get("player_table") or [])}
if not r2_status_by_id:
    raise SystemExit("HARD STOP: official R2 snapshot has zero player rows")
if not any(status in _NON_ADVANCING_STATUSES for status in r2_status_by_id.values()):
    raise SystemExit(
        "HARD STOP: official R2 snapshot reports no CUT/WD/DQ/DNS status for any player yet -- "
        "the cut has not actually been published/confirmed; refusing to guess the advancing field"
    )
advancing_ids = {pid for pid, status in r2_status_by_id.items() if status not in _NON_ADVANCING_STATUSES}
records = [r for r in records if str(r["player_id"]) in advancing_ids]
if not records:
    raise SystemExit("HARD STOP: zero PRE players match the official advancing field -- identity mismatch between PRE and R2 evidence")

out_path = _CONTEXT.artifact_path("post_r2_input")
out = {
    "schema_version": 1,
    "artifact": out_path.stem,
    "game_code": GAME_CODE,
    "stage": "POST_R2_PRE_FINAL",
    "model_version": pre["model_version"],
    "pre_cutoff": pre["cutoff"],
    "future_data_excluded": True,
    "pre_source": str(pre_path.name),
    "master_source": str(master_path.name),
    "cut_evidence_source": str(r2_snapshot_path.name),
    "pre_field_size": expected_field_size,
    "advancing_field_size": len(records),
    "records": records,
}

out_path.write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("=== POST-R2 INPUT RECOVERY ===")
print("GAME:", out["game_code"])
print("MODEL:", out["model_version"])
print("PRE CUTOFF:", out["pre_cutoff"])
print("PRE FIELD:", out["pre_field_size"])
print("ADVANCING FIELD:", out["advancing_field_size"])
print("DUPLICATES:", len(ids) - len(set(ids)))
print("NULL WIN:", sum(r.get("win_probability") is None for r in records))
print("FUTURE DATA EXCLUDED:", out["future_data_excluded"])
print("WROTE:", out_path)
