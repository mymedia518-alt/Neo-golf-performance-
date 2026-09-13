#!/usr/bin/env python3
"""NEO TOURNAMENT OPERATOR V2: close out every background task owned
by one tournament (RULE 3), persist the update, and print the
[TOURNAMENT CLOSEOUT] block. Never touches a task belonging to any
other tournament_id, and never touches an unrelated (tournament_id=
None) automation -- see close_tournament()'s own docstring for why
that is structurally guaranteed, not just a convention.

Usage: python3 scripts/134_tournament_closeout.py <game_code>
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_background_tasks import DEFAULT_REGISTRY_PATH, close_tournament, load_registry, save_registry  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: 134_tournament_closeout.py <game_code>")
    game_code = sys.argv[1]
    tasks = load_registry(DEFAULT_REGISTRY_PATH)
    result = close_tournament(tasks, game_code)
    save_registry(result.updated_tasks, DEFAULT_REGISTRY_PATH)

    print("[TOURNAMENT CLOSEOUT]")
    print(f"tournament_id: {result.tournament_id}")
    print(f"lifecycle: {result.lifecycle}")
    print(f"polling_tasks_disabled: {result.polling_tasks_disabled}")
    print(f"wait_processes_terminated: {result.wait_processes_terminated}")
    print(f"scheduled_cycles_disabled: {result.scheduled_cycles_disabled}")
    print(f"remaining_tournament_tasks: {result.remaining_tournament_tasks}")


if __name__ == "__main__":
    main()
