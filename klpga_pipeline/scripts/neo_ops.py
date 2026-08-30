"""NEO ZERO-TOUCH OPS — unified operator CLI.

Subcommands:
  final-close   Run the real FINAL CLOSE preflight
                (scripts/final_close_preflight.py) for one tournament as
                a subprocess, streaming its complete stdout/stderr live
                to this console AND saving it verbatim to
                outputs/neo_ops/<game_code>/latest.txt, plus a
                machine-readable summary at
                outputs/neo_ops/<game_code>/latest.json (the SAME
                --json-out final_close_preflight.py itself already
                writes — this script never re-derives that summary).

                Exits with a distinct code per verdict so external
                automation (Task Scheduler, a future exception-agent)
                can branch on it without parsing text:
                    GO = 0, WARN = 1, HARD_STOP = 2, UNKNOWN = 3

======================================================================
WHAT THIS SCRIPT NEVER DOES
======================================================================
It only ever invokes scripts/final_close_preflight.py as a subprocess
(no other klpga.neo_win/site module is imported here) — so, exactly
like that script, it never freezes FINAL, never freezes an evaluation,
never deploys, never commits/pushes, and never touches docs/index.html
or any docs/tournaments/.../index.html. It never deletes any cache
file — the cache directory is only ever passed through to the
preflight, never written to directly here.

======================================================================
DISCORD NOTIFICATION (optional)
======================================================================
Set NEO_DISCORD_WEBHOOK_URL to also post the verdict there
(klpga.ops.discord_notify). Unset/empty is a normal, silent no-op —
never fails this pipeline; a Discord-side failure is caught and
reported, never raised.

======================================================================
NOT YET ENABLED (prepared interfaces only)
======================================================================
  - Windows Task Scheduler automation: scripts/ops/register_task_scheduler.bat
    (a template — registers nothing until a human deliberately runs it)
  - Claude Code exception-agent invocation: klpga.ops.exception_agent
    (gated behind NEO_ENABLE_EXCEPTION_AGENT; even enabled, it currently
    only reports NOT_IMPLEMENTED — no real invocation exists yet)

Usage:
    python scripts/neo_ops.py final-close
    python scripts/neo_ops.py final-close --game-code 2026080002 --season 2026
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.ops import paths  # noqa: E402
from klpga.ops.discord_notify import send_discord_notification  # noqa: E402
from klpga.ops.exception_agent import trigger_exception_agent  # noqa: E402

# ROOT is this SCRIPT's own worktree (code location) -- used only for
# locating final_close_preflight.py and for where AUTO OPS's own
# outputs/ go. It is NEVER used to resolve klpga.sqlite/the HTTP
# cache/roster files -- those go through klpga.ops.paths, which
# resolves from $NEO_DATA_ROOT when set (see paths.py's module
# docstring for why outputs and operational data are kept separate).
ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_SCRIPT = ROOT / "scripts" / "final_close_preflight.py"

EXIT_GO, EXIT_WARN, EXIT_HARD_STOP, EXIT_UNKNOWN = 0, 1, 2, 3
_EXIT_CODE_BY_VERDICT = {"GO": EXIT_GO, "WARN": EXIT_WARN, "HARD_STOP": EXIT_HARD_STOP}
_LABEL_BY_VERDICT = {"GO": "GO", "WARN": "WARN", "HARD_STOP": "HARD STOP"}


def run_final_close(
    db: str, season: str, game_code: str, expected_final_round: str, finalists: str,
    cache_dir: Optional[str] = None, out_dir: Optional[Path] = None,
) -> int:
    """Real subprocess invocation of scripts/final_close_preflight.py.
    Streams its output live and returns this process's own exit code
    (EXIT_GO / EXIT_WARN / EXIT_HARD_STOP / EXIT_UNKNOWN)."""
    out_dir = out_dir if out_dir is not None else ROOT / "outputs" / "neo_ops" / game_code
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / "latest.txt"
    json_path = out_dir / "latest.json"

    cmd = [
        sys.executable, str(PREFLIGHT_SCRIPT),
        "--db", db, "--season", str(season), "--game-code", game_code,
        "--expected-final-round", str(expected_final_round), "--finalists", finalists,
        "--json-out", str(json_path),
    ]
    if cache_dir:
        cmd += ["--cache-dir", cache_dir]

    print("=== NEO ZERO-TOUCH OPS: final-close ===")
    print(f"game_code={game_code} season={season} expected_final_round={expected_final_round}")
    print(f"log:  {txt_path}")
    print(f"json: {json_path}")
    print()

    lines: list[str] = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        print(line, end="")
        lines.append(line)
    proc.wait()

    txt_path.write_text("".join(lines), encoding="utf-8")

    verdict = "UNKNOWN"
    summary: dict = {}
    if json_path.exists():
        try:
            summary = json.loads(json_path.read_text(encoding="utf-8"))
            verdict = summary.get("verdict") or "UNKNOWN"
        except (json.JSONDecodeError, OSError):
            pass

    exit_code = _EXIT_CODE_BY_VERDICT.get(verdict, EXIT_UNKNOWN)
    label = _LABEL_BY_VERDICT.get(verdict, f"UNKNOWN ({verdict})")

    print()
    print("============================================================")
    print(f"NEO FINAL CLOSE: {label}")
    print(f"Full log:  {txt_path}")
    print(f"JSON:      {json_path}")
    print("============================================================")

    discord_content = (
        f"**NEO FINAL CLOSE** — game_code={game_code}\n"
        f"VERDICT: **{label}**\n"
        f"hard_stop_reasons: {summary.get('hard_stop_reasons', [])}\n"
        f"warn_reasons: {summary.get('warn_reasons', [])}"
    )
    posted = send_discord_notification(discord_content)
    print(f"Discord notification: {'sent' if posted else 'skipped (no webhook configured, or post failed)'}")

    if verdict in ("WARN", "HARD_STOP"):
        agent_status = trigger_exception_agent(verdict, summary)
        print(f"Exception-agent: {agent_status}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fc = subparsers.add_parser("final-close", help="Run the real FINAL CLOSE preflight for one tournament.")
    fc.add_argument(
        "--db", default=str(paths.db_path()),
        help="Defaults to $NEO_DATA_ROOT/klpga.sqlite if NEO_DATA_ROOT is set, else data/klpga.sqlite "
             "under this repo checkout.",
    )
    fc.add_argument("--season", default="2026")
    fc.add_argument("--game-code", default="2026080001", dest="game_code")
    fc.add_argument("--expected-final-round", default="4", dest="expected_final_round")
    fc.add_argument(
        "--finalists", default=str(paths.roster_dir() / "r3_finalists_2026080001.csv"),
        help="Defaults to $NEO_DATA_ROOT/roster/r3_finalists_2026080001.csv if NEO_DATA_ROOT is set, "
             "else data/roster/r3_finalists_2026080001.csv under this repo checkout.",
    )
    fc.add_argument(
        "--cache-dir", default=None,
        help="If omitted, final_close_preflight.py resolves its own default from NEO_DATA_ROOT/data.",
    )

    args = parser.parse_args()

    if args.command == "final-close":
        return run_final_close(
            db=args.db, season=args.season, game_code=args.game_code,
            expected_final_round=args.expected_final_round, finalists=args.finalists,
            cache_dir=args.cache_dir,
        )

    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover -- parser.error already exits


if __name__ == "__main__":
    raise SystemExit(main())
