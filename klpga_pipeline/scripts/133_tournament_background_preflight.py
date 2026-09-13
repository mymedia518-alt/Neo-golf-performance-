#!/usr/bin/env python3
"""NEO TOURNAMENT OPERATOR V2: print the [BACKGROUND PREFLIGHT] block
required before starting any NEO tournament work. Scans the persisted
task registry for stale previous-tournament background tasks (RULE 4)
and reports any locally-detected orphan wait processes (a real OS scan
via psutil-free pgrep/ps -- this is the one place in the whole feature
allowed to touch the real process table, kept strictly out of the pure
klpga.tournament_background_tasks module so that module stays unit-
testable without mocking the OS).

Usage: python3 scripts/133_tournament_background_preflight.py <game_code>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_background_tasks import DEFAULT_REGISTRY_PATH, load_registry, preflight  # noqa: E402


def _count_orphan_wait_processes() -> int:
    """A wait process is "orphan" here if it matches the exact banned
    self-matching-pgrep shape (see tournament_background_tasks.
    find_self_matching_wait_loops) among currently running processes.
    Best-effort, read-only -- never modifies process state."""
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return 0
    from klpga.tournament_background_tasks import find_self_matching_wait_loops
    count = 0
    for line in out.splitlines()[1:]:
        if find_self_matching_wait_loops(line):
            count += 1
    return count


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: 133_tournament_background_preflight.py <game_code>")
    game_code = sys.argv[1]
    tasks = load_registry(DEFAULT_REGISTRY_PATH)
    orphan_count = _count_orphan_wait_processes()
    result = preflight(tasks, game_code, orphan_wait_process_count=orphan_count)

    print("[BACKGROUND PREFLIGHT]")
    print(f"current_tournament: {result.current_tournament}")
    print(f"active_tournament_tasks: {result.active_tournament_tasks}")
    print(f"stale_tournament_tasks: {len(result.stale_tournament_tasks)}")
    print(f"orphan_wait_processes: {result.orphan_wait_processes}")
    print(f"previous_tournament_tasks: {len(result.previous_tournament_tasks)}")
    print(f"status: {result.status}")
    if result.status == "BLOCKED":
        for t in result.stale_tournament_tasks:
            print(f"  STALE_BACKGROUND_TASK: task_id={t.task_id} tournament_id={t.tournament_id} "
                  f"stage={t.stage} schedule={t.schedule} reason='still enabled/ACTIVE for a different tournament'")


if __name__ == "__main__":
    main()
