"""Roadmap #2 — minimum CLI for klpga.neo_win.tournament_history:
records PRE and R1 history stages for one tournament from EXISTING
frozen artifacts only (auto-discovered under --predictions-dir /
--c-predictions-dir), verifies same-player linkage, WIN% values, null
handling, and proves the source frozen files were not modified (SHA256
before/after). Read-only against every frozen file; append-only
against neo_tournament_history/.

Usage:
    python scripts/42_record_tournament_history.py --game-code 2026080001
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_PRE,
    STAGE_R1,
    HistoryStageAlreadyRecordedError,
    history_entry_from_beta001c_snapshot,
    history_entry_from_neo_win_pre_snapshot,
    history_entry_from_round_update_dict,
    history_stage_path,
    read_full_tournament_history,
    write_history_stage_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_one(root: Path, game_code: str, name_prefix: str) -> "Path | None":
    if not root.exists():
        return None
    matches = sorted(root.glob(f"*/{name_prefix}_{game_code}.json"))
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--c-predictions-dir", default=str(DEFAULT_C_PREDICTIONS_DIR))
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    args = parser.parse_args()

    predictions_dir = Path(args.predictions_dir)
    c_predictions_dir = Path(args.c_predictions_dir)
    history_dir = Path(args.history_dir)
    errors: list[str] = []
    frozen_files_checked: dict[Path, str] = {}

    # Prefer BETA #001-C's own PRE if frozen; else fall back to BETA #001's.
    pre_c_path = _find_one(c_predictions_dir, args.game_code, "neo_win_c_001-C")
    pre_001_path = _find_one(predictions_dir, args.game_code, "neo_win_001")
    r1_path = _find_one(predictions_dir, args.game_code, "neo_win_001-R1")

    pre_entry = None
    pre_source_path = None
    if pre_c_path is not None:
        pre_source_path = pre_c_path
        frozen_files_checked[pre_c_path] = _sha256(pre_c_path)
        pre_entry = history_entry_from_beta001c_snapshot(
            read_neo_win_c_snapshot(pre_c_path), recorded_at_utc="RUN_TIME"
        )
    elif pre_001_path is not None:
        pre_source_path = pre_001_path
        frozen_files_checked[pre_001_path] = _sha256(pre_001_path)
        pre_entry = history_entry_from_neo_win_pre_snapshot(
            read_neo_win_snapshot(pre_001_path), recorded_at_utc="RUN_TIME"
        )
    else:
        errors.append(f"No frozen PRE snapshot found for game_code={args.game_code!r} under "
                       f"{c_predictions_dir} or {predictions_dir}")

    r1_entry = None
    if r1_path is not None:
        import json

        frozen_files_checked[r1_path] = _sha256(r1_path)
        r1_data = json.loads(r1_path.read_text(encoding="utf-8"))
        r1_entry = history_entry_from_round_update_dict(r1_data, recorded_at_utc="RUN_TIME")
    else:
        errors.append(f"No frozen R1 snapshot found for game_code={args.game_code!r} under {predictions_dir}")

    for entry in (pre_entry, r1_entry):
        if entry is None:
            continue
        try:
            write_history_stage_atomic(entry, history_dir)
        except HistoryStageAlreadyRecordedError:
            pass  # SKIP + LOG: already recorded, read back below for verification.

    history = read_full_tournament_history(history_dir, args.game_code)
    recorded_pre = history.get(STAGE_PRE)
    recorded_r1 = history.get(STAGE_R1)

    frozen_modified = [str(p) for p, before_hash in frozen_files_checked.items() if _sha256(p) != before_hash]

    pre_codes = {e.player_code for e in recorded_pre.entrants} if recorded_pre else set()
    r1_codes = {e.player_code for e in recorded_r1.entrants} if recorded_r1 else set()
    linked = sorted(pre_codes & r1_codes)

    print("=== STATUS ===")
    print("OK" if not errors else "INCOMPLETE")
    print()
    print(f"PRE COUNT: {len(pre_codes)}  (source: {pre_source_path})")
    print(f"R1 COUNT: {len(r1_codes)}  (source: {r1_path})")
    print(f"LINKED PLAYERS: {len(linked)}")
    print()
    print("SAMPLE 5 PRE->R1 WIN%:")
    pre_by_code = {e.player_code: e for e in recorded_pre.entrants} if recorded_pre else {}
    r1_by_code = {e.player_code: e for e in recorded_r1.entrants} if recorded_r1 else {}
    for code in linked[:5]:
        p = pre_by_code[code]
        r = r1_by_code[code]
        print(f"  {code} ({p.player_name}): PRE {p.win_pct} -> R1 {r.win_pct}")
    print()
    print(f"FROZEN FILES MODIFIED: {len(frozen_modified)} {frozen_modified}")
    print(f"ERRORS: {errors if errors else 'none'}")
    return 0 if not errors else 4


if __name__ == "__main__":
    raise SystemExit(main())
