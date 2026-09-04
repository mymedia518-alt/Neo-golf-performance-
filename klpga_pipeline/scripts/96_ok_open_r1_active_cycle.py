"""OK Open R1 ACTIVE MODE: one 30-minute operational cycle -- collect,
validate, publish (build + hard-validate + promote), or preserve
last-known-good production on any failure.

Safe by default: with no --live flag, this makes ZERO HTTP requests and
reports a SKIP_WAIT dry run -- matching every other real-collection
script in this project (see run_klpga_collector.py's own module
docstring). LOCAL WINDOWS (or any machine with real network access to
klpga.co.kr) IS THE DATA-COLLECTION ENVIRONMENT for --live; a sandbox
with no route to klpga.co.kr (confirmed, repeatedly, all session) will
have --live fail its own HTTP calls, which this script treats as an
ordinary SKIP_WAIT -- never a crash, never a reason to touch production.

Usage:
    python scripts/96_ok_open_r1_active_cycle.py           # dry run, no HTTP
    python scripts/96_ok_open_r1_active_cycle.py --live    # real cycle

Always prints exactly one JSON summary line to stdout as its last line,
for both a human operator and an automated caller (e.g. the 30-minute
Routine) to read: {"action", "reason", "retrieved_at", "row_count",
"r1_status", "stop_active_cycle", "promoted"}. `stop_active_cycle: true`
is script 96's own R1-close signal -- the caller (never this script,
which cannot reach the scheduler) is responsible for actually stopping
further cycles once it sees that.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
ENTRY_SNAPSHOT = CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
R1_LIVE_SNAPSHOT = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"
STAGE_STATE = CONTENT / "OK_OPEN_STAGE_STATE.json"
GAME_CODE = "2026120001"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r1_active_cycle import decide_cycle  # noqa: E402


def _collect_live() -> tuple[list[dict], bool, bool, str | None]:
    """Real HTTP collection. Returns (rows, official_page_available,
    tournament_finished, error). Any network/parse failure is reported
    via `error` (treated by the caller as official_page_available=False,
    i.e. an ordinary WAIT) -- never raised past this function, since a
    transient network problem must never look like a data-corruption
    HARD_STOP."""
    try:
        from klpga.collectors.leaderboard import fetch_round_leaderboard
        from klpga.collectors.tournaments import fetch_game_list
        from klpga.http_client import PoliteHttpClient

        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "r1_active")
        listings = [x for x in fetch_game_list(client, season=2026) if x.game_code == GAME_CODE]
        tournament_finished = bool(listings and listings[0].is_finished)
        rows = fetch_round_leaderboard(client, GAME_CODE, 1, use_cache=False)
        row_dicts = [
            {
                "player_id": r.player_code,
                "player_name": r.player_name,
                "status": r.status,
                "holes_completed": r.holes_completed,
                "rank": r.rank,
                "rank_display": r.rank_display,
                "total_under_par_display": r.total_under_par_display,
            }
            for r in rows
        ]
        return row_dicts, True, tournament_finished, None
    except Exception as exc:  # noqa: BLE001 -- any collection failure is a WAIT, not a crash
        return [], False, False, f"{type(exc).__name__}: {exc}"


def _rebuild_and_promote() -> None:
    """Rebuild the full public site (OK Open pages included) and
    promote to docs/ -- the exact same pipeline every prior hotfix this
    session used, run here unchanged. Raises on any failure; the
    caller's job is to never call this after a bad decision and to
    never treat a raise here as anything but "did not promote"."""
    python = sys.executable
    for script in ("84_build_ok_open_pre_website_candidate.py", "86_build_neo_data_home_candidate.py", "88_build_neo_top120_candidate.py"):
        subprocess.run([python, str(ROOT / "scripts" / script)], cwd=ROOT, check=True, capture_output=True, text=True)
    subprocess.run([python, str(ROOT / "scripts" / "94_promote_top120_to_production.py")], cwd=ROOT, check=True, capture_output=True, text=True)


def main() -> int:
    live = "--live" in sys.argv[1:]
    entry = json.loads(ENTRY_SNAPSHOT.read_text(encoding="utf-8"))
    expected_ids = [str(e["player_id"]) for e in entry.get("entries", [])]

    if live:
        rows, official_page_available, tournament_finished, error = _collect_live()
        if error:
            print(f"[r1-active-cycle] collection failed this cycle (treated as WAIT): {error}", file=sys.stderr)
    else:
        rows, official_page_available, tournament_finished = [], False, False

    decision = decide_cycle(rows, expected_ids, official_page_available=official_page_available, tournament_finished=tournament_finished)

    result = {
        "action": decision.action, "reason": decision.reason, "retrieved_at": decision.retrieved_at,
        "row_count": decision.row_count, "r1_status": decision.r1_status,
        "stop_active_cycle": decision.action == "PUBLISH_AND_CLOSE", "promoted": False,
    }

    if decision.action in ("SKIP_WAIT",):
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if decision.action == "HARD_STOP":
        print(json.dumps(result, ensure_ascii=False))
        return 1

    # PUBLISH or PUBLISH_AND_CLOSE: write the snapshot + stage state,
    # THEN rebuild+promote. If rebuild/promote raises, production is
    # simply never touched -- last-known-good is the existing docs/,
    # untouched by construction (script 94 only mirrors on success).
    R1_LIVE_SNAPSHOT.write_text(json.dumps({
        "schema_version": "neo_ok_open_r1_live_snapshot_v1", "game_code": GAME_CODE,
        "retrieved_at": decision.retrieved_at, "row_count": decision.row_count, "rows": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    state = json.loads(STAGE_STATE.read_text(encoding="utf-8")) if STAGE_STATE.is_file() else {"stages": {}}
    state.setdefault("stages", {})["r1"] = {
        "validated": True, "retrieved_at": decision.retrieved_at, "row_count": decision.row_count,
        "r1_status": decision.r1_status,
    }
    if decision.action == "PUBLISH_AND_CLOSE":
        state["r1_complete"] = True
    STAGE_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    try:
        _rebuild_and_promote()
        result["promoted"] = True
    except subprocess.CalledProcessError as exc:
        result["promoted"] = False
        result["build_error"] = f"{exc.cmd} exit={exc.returncode}: {(exc.stderr or '')[:2000]}"
        print(json.dumps(result, ensure_ascii=False))
        print("[r1-active-cycle] build/promote FAILED -- production left untouched (last-known-good preserved)", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
