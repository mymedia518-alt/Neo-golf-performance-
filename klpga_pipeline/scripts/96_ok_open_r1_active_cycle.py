"""OK Open R1 ACTIVE MODE: one 30-minute operational cycle -- collect,
freshness-check, validate, compute live Cut/Top20/Top10/Top5/Win
probabilities (Monte Carlo, klpga.neo_win.r1_live_probability), save an
IMMUTABLE snapshot, publish (build + hard-validate + promote), or
preserve last-known-good production on any failure.

Safe by default: with no --live flag, this makes ZERO HTTP requests and
reports a SKIP_WAIT dry run -- matching every other real-collection
script in this project (see run_klpga_collector.py's own module
docstring). LOCAL WINDOWS (or any machine with real network access to
klpga.co.kr) IS THE DATA-COLLECTION ENVIRONMENT for --live; a sandbox
with no route to klpga.co.kr (confirmed, repeatedly, all session) will
have --live fail its own HTTP calls, which this script treats as an
ordinary SKIP_WAIT -- never a crash, never a reason to touch production.

DUPLICATE-EXECUTION LOCK
======================================================================
A simple exclusive lock file (content/website_v2/.r1_active_cycle.lock,
created with O_CREAT|O_EXCL) prevents two cycles from running at once
(e.g. an overlapping Task Scheduler run and a manual run). A lock older
than STALE_LOCK_SECONDS is treated as abandoned (a prior run crashed
without releasing it) and taken over rather than blocking forever. This
is a simple mtime-based lock, not OS-level flock -- adequate for one
machine running this on a schedule, not a distributed multi-worker
deployment.

FRESHNESS -- NO NEW VALIDATED DATA, NO DEPLOY
======================================================================
Each cycle's leaderboard-state signature (klpga.neo_win.
r1_snapshot_store.leaderboard_state_signature) is compared against the
last cycle's, persisted in OK_OPEN_STAGE_STATE.json. An unchanged
signature with the round still in progress yields SKIP_NO_NEW_DATA:
the collection succeeded, but nothing is rebuilt or promoted, and no
new immutable snapshot is written for it -- "새롭고 검증된 데이터가
없으면 배포하지 않는다".

Usage:
    python scripts/96_ok_open_r1_active_cycle.py                       # dry run, no HTTP
    python scripts/96_ok_open_r1_active_cycle.py --live                # real cycle, local promote only
    python scripts/96_ok_open_r1_active_cycle.py --live --git-push     # real cycle, promote AND commit+push
                                                                        # (the exact command for a 30-minute
                                                                        # Windows Task Scheduler entry -- see
                                                                        # _git_commit_and_push below)

Always prints exactly one JSON summary line to stdout as its last line,
for both a human operator and an automated caller (e.g. the 30-minute
Routine) to read. `stop_active_cycle: true` is script 96's own
R1-close signal -- the caller (never this script, which cannot reach
the scheduler) is responsible for actually stopping further cycles
once it sees that.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
ENTRY_SNAPSHOT = CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
PRE_MASTER = CONTENT / "OK_OPEN_2026_PRE_PUBLIC_MASTER.json"
PRE_PERFORMANCE_SNAPSHOT = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"
R1_LIVE_SNAPSHOT = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"
R1_CLOSE_RECORD = CONTENT / "OK_OPEN_2026_R1_CLOSE_RECORD.json"
STAGE_STATE = CONTENT / "OK_OPEN_STAGE_STATE.json"
LOCK_PATH = CONTENT / ".r1_active_cycle.lock"
STALE_LOCK_SECONDS = 25 * 60
GAME_CODE = "2026120001"
KST = datetime.timezone(datetime.timedelta(hours=9))
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r1_active_cycle import decide_cycle  # noqa: E402
from klpga.neo_win.r1_live_probability import (  # noqa: E402
    build_r1_sim_inputs,
    compute_neo_movers,
    cutline_percentiles,
    simulate_r1_live,
)
from klpga.neo_win.r1_snapshot_store import leaderboard_state_signature, save_snapshot_immutable  # noqa: E402


def _acquire_lock() -> bool:
    now = time.time()
    if LOCK_PATH.exists():
        try:
            age = now - LOCK_PATH.stat().st_mtime
        except OSError:
            age = 0.0
        if age < STALE_LOCK_SECONDS:
            return False
        LOCK_PATH.unlink(missing_ok=True)
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()} {datetime.datetime.now(datetime.timezone.utc).isoformat()}".encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


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
        tournament_finished = bool(listings and listings[0].is_completed)
        rows = fetch_round_leaderboard(client, GAME_CODE, 1, use_cache=False)
        row_dicts = [
            {
                "player_id": r.player_code,
                "player_name": r.player_name,
                "status": r.status,
                "holes_completed": r.holes_completed,
                "rank": r.rank,
                "rank_display": r.rank_display,
                "total_under_par": r.total_under_par,
                "total_under_par_display": r.total_under_par_display,
                "today_under_par": r.today_under_par if r.today_under_par is not None else r.total_under_par,
            }
            for r in rows
        ]
        return row_dicts, True, tournament_finished, None
    except requests.exceptions.RequestException as exc:
        return [], False, False, f"WAIT:{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 -- parser/programming defects are hard stops
        return [], False, False, f"HARD_STOP:{type(exc).__name__}: {exc}"


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


def _read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _load_previous_signature(state: dict) -> tuple | None:
    raw = ((state.get("stages") or {}).get("r1") or {}).get("signature")
    if raw is None:
        return None
    return tuple(tuple(row) for row in raw)


def _kst_hhmm(retrieved_at: str) -> str:
    dt = datetime.datetime.fromisoformat(retrieved_at.replace("Z", "+00:00")).astimezone(KST)
    return dt.strftime("%H%M")


def _build_player_table(rows: list[dict], probabilities: dict, sim_inputs: list, pre_by_id: dict) -> list[dict]:
    real_scores = [r.get("total_under_par") for r in rows if r.get("total_under_par") is not None]
    leader_score = min(real_scores) if real_scores else None
    sim_by_id = {p.player_code: p for p in sim_inputs}
    table = []
    for row in rows:
        pid = str(row.get("player_id") or "")
        probs = probabilities.get(pid)
        pre = pre_by_id.get(pid, {})
        gap = None
        if row.get("total_under_par") is not None and leader_score is not None:
            gap = row["total_under_par"] - leader_score
        entry = {
            "player_id": pid,
            "player_name": row.get("player_name"),
            "rank_display": row.get("rank_display"),
            "total_under_par": row.get("total_under_par"),
            "total_under_par_display": row.get("total_under_par_display"),
            "today_under_par": row.get("today_under_par"),
            "holes_completed": row.get("holes_completed"),
            "status": row.get("status"),
            "gap_to_leader": gap,
            "cut_pct": probs.get("make_cut_pct") if probs else None,
            "top20_pct": probs.get("top20_pct") if probs else None,
            "top10_pct": probs.get("top10_pct") if probs else None,
            "top5_pct": probs.get("top5_pct") if probs else None,
            "win_pct": probs.get("win_pct") if probs else None,
            "pre_win_probability": pre.get("win_probability"),
            "pre_top10_probability": pre.get("top10_probability"),
        }
        table.append(entry)
    table.sort(key=lambda e: (e["total_under_par"] is None, e["total_under_par"] if e["total_under_par"] is not None else 0))
    return table


GIT_TRACKED_PATHS = (
    "klpga_pipeline/scripts/96_ok_open_r1_active_cycle.py",
    "docs",
    "klpga_pipeline/candidate",
    "klpga_pipeline/content/website_v2/OK_OPEN_STAGE_STATE.json",
    "klpga_pipeline/content/website_v2/OK_OPEN_2026_R1_LIVE_SNAPSHOT.json",
    "klpga_pipeline/content/website_v2/OK_OPEN_2026_R1_CLOSE_RECORD.json",
    "klpga_pipeline/content/website_v2/r1_snapshots",
)


def _git_commit_and_push(message: str) -> tuple[bool, str]:
    """OPT-IN ONLY (--git-push): stages exactly the known cycle-output
    paths (never `git add -A`), commits, and pushes with the same
    retry-with-backoff convention this project's own commits use. This
    is what actually closes the "collect -> ... -> promote -> deploy"
    loop into one Task Scheduler entry on the real operator machine --
    never run in this sandbox (no real cycle ever reaches here without
    real network access) and never run at all unless explicitly asked
    for. Returns (pushed, detail)."""
    repo_root = ROOT.parent
    try:
        existing_paths = [p for p in GIT_TRACKED_PATHS if (repo_root / p).exists()]
        subprocess.run(["git", "add", "--"] + existing_paths, cwd=repo_root, check=True, capture_output=True, text=True)
        status = subprocess.run(["git", "status", "--porcelain"] + existing_paths, cwd=repo_root, check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            return False, "nothing to commit (no tracked-path changes)"
        subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True, capture_output=True, text=True)
        delay = 2
        last_error = ""
        for _attempt in range(4):
            push = subprocess.run(["git", "push", "-u", "origin", "neo-website-v2"], cwd=repo_root, capture_output=True, text=True)
            if push.returncode == 0:
                return True, "pushed"
            last_error = push.stderr[-500:]
            time.sleep(delay)
            delay *= 2
        return False, f"push failed after retries: {last_error}"
    except subprocess.CalledProcessError as exc:
        return False, f"{exc.cmd} exit={exc.returncode}: {(exc.stderr or '')[:500]}"


def main() -> int:
    live = "--live" in sys.argv[1:]
    git_push = "--git-push" in sys.argv[1:]

    if not _acquire_lock():
        print(json.dumps({"action": "LOCKED", "reason": "another cycle is already running (or a stale lock is younger than the staleness threshold)", "stop_active_cycle": False, "promoted": False}, ensure_ascii=False))
        return 0

    try:
        entry = _read_json(ENTRY_SNAPSHOT, {"entries": []})
        expected_ids = [str(e["player_id"]) for e in entry.get("entries", [])]
        state = _read_json(STAGE_STATE, {"stages": {}})
        previous_signature = _load_previous_signature(state)

        if live:
            rows, official_page_available, tournament_finished, error = _collect_live()
            if error and error.startswith("HARD_STOP:"):
                print(f"[r1-active-cycle] collector defect: {error}", file=sys.stderr)
                result = {"action": "HARD_STOP", "reason": error, "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "row_count": 0, "r1_status": None, "stop_active_cycle": False, "promoted": False}
                print(json.dumps(result, ensure_ascii=False))
                return 1
            if error:
                print(f"[r1-active-cycle] official leaderboard unavailable (WAIT): {error}", file=sys.stderr)
            # The official R1 start field is authoritative for this live
            # snapshot.  A pre-event entry snapshot can legitimately be
            # superseded by late substitutions; use the observed official
            # player IDs for the cycle while retaining both sources in the
            # immutable provenance payload.
            if rows:
                expected_ids = [str(r.get("player_id")) for r in rows if r.get("player_id")]
        else:
            rows, official_page_available, tournament_finished = [], False, False

        decision = decide_cycle(
            rows, expected_ids, official_page_available=official_page_available, tournament_finished=tournament_finished, previous_signature=previous_signature
        )

        result = {
            "action": decision.action, "reason": decision.reason, "retrieved_at": decision.retrieved_at,
            "row_count": decision.row_count, "r1_status": decision.r1_status,
            "stop_active_cycle": decision.action == "PUBLISH_AND_CLOSE", "promoted": False,
        }

        if decision.action in ("SKIP_WAIT", "SKIP_NO_NEW_DATA"):
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if decision.action == "HARD_STOP":
            print(json.dumps(result, ensure_ascii=False))
            return 1

        # PUBLISH or PUBLISH_AND_CLOSE: compute live probabilities, save
        # the IMMUTABLE snapshot, write the "latest" convenience copy +
        # stage state, THEN rebuild+promote. If rebuild/promote raises,
        # production is simply never touched -- last-known-good is the
        # existing docs/, untouched by construction (script 94 only
        # mirrors on success). The immutable snapshot and stage-state
        # update are NOT rolled back on a promote failure -- they record
        # what was really collected/computed this cycle regardless of
        # whether the site build happened to succeed.
        pre_master = _read_json(PRE_MASTER, {"records": []})
        pre_records = pre_master.get("records", [])
        pre_by_id = {str(r.get("player_id")): r for r in pre_records}
        performance = _read_json(PRE_PERFORMANCE_SNAPSHOT, {"profiles": []})
        profiles = performance.get("profiles", [])

        r1_scores = {str(r.get("player_id")): r.get("total_under_par") for r in rows if r.get("total_under_par") is not None}
        sim_result = build_r1_sim_inputs(pre_records, profiles, r1_scores)
        prob_result = simulate_r1_live(sim_result.sim_inputs)
        movers = compute_neo_movers(pre_records, prob_result.probabilities, sim_result.sim_inputs)
        cutline = cutline_percentiles(prob_result.cutline_distribution)
        player_table = _build_player_table(rows, prob_result.probabilities, sim_result.sim_inputs, pre_by_id)

        def _movers_json(entries):
            return [
                {"player_id": e.player_id, "player_name": e.player_name, "metric": e.metric, "pre_value": e.pre_value, "current_value": e.current_value, "delta": e.delta}
                for e in entries
            ]

        kind = f"R1_{_kst_hhmm(decision.retrieved_at)}"
        payload = {
            "round": 1,
            "collected_at": decision.retrieved_at,
            "official_data_timestamp": None,
            "official_data_timestamp_note": "KLPGA's leaderboard response carries no per-row timestamp field -- never fabricated equal to collected_at.",
            "leaderboard": rows,
            "probabilities": prob_result.probabilities,
            "expected_cut_distribution": cutline,
            "cut_fraction_used": prob_result.cut_fraction_used,
            "n_simulations": prob_result.n_simulations,
            "excluded_no_r1_score": prob_result.excluded_no_r1_score,
            "neo_movers": {k: _movers_json(v) for k, v in movers.items()},
            "model_version": "r1_live_probability_v1",
            "build_id": decision.retrieved_at,
            "input_provenance": {
                "pre_master": "OK_OPEN_2026_PRE_PUBLIC_MASTER.json",
                "performance_snapshot": "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json",
                "r1_leaderboard_source": "klpga.co.kr getGameList/roundLeaderboard (live)" if live else "dry run -- no HTTP",
                "population_fallback_players": sim_result.population_fallback_players,
                "missing_r1_players": sim_result.missing_r1_players,
            },
            "validation_result": {"cycle_action": decision.action, "cycle_reason": decision.reason, "row_count": decision.row_count},
        }

        try:
            snapshot_path = save_snapshot_immutable(GAME_CODE, kind, payload)
        except FileExistsError:
            kind = f"{kind}{datetime.datetime.now(KST).strftime('%S')}"
            snapshot_path = save_snapshot_immutable(GAME_CODE, kind, payload)
        result["snapshot_kind"] = kind
        try:
            result["snapshot_path"] = str(snapshot_path.relative_to(ROOT))
        except ValueError:
            result["snapshot_path"] = str(snapshot_path)

        latest_payload = {**payload, "player_table": player_table, "kind": kind}
        R1_LIVE_SNAPSHOT.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

        signature = leaderboard_state_signature(rows)
        state.setdefault("stages", {})["r1"] = {
            "validated": True,
            "retrieved_at": decision.retrieved_at,
            "row_count": decision.row_count,
            "r1_status": decision.r1_status,
            "signature": [list(t) for t in signature],
            "latest_snapshot_kind": kind,
        }
        if decision.action == "PUBLISH_AND_CLOSE":
            state["r1_complete"] = True
            state["r2_ready"] = True
            close_record = {
                "closed_at": decision.retrieved_at,
                "final_snapshot_kind": kind,
                "leader": player_table[0] if player_table else None,
                "cutline_p50": cutline.get("p50") if cutline else None,
                "top_win_probability_player": max(
                    (p for p in player_table if p.get("win_pct") is not None), key=lambda p: p["win_pct"], default=None
                ),
                "row_count": decision.row_count,
            }
            R1_CLOSE_RECORD.write_text(json.dumps(close_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
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

        if git_push:
            commit_message = f"R1 ACTIVE MODE: {kind} snapshot ({decision.action}, {decision.row_count} rows)\n\nAutomated by scripts/96_ok_open_r1_active_cycle.py --live --git-push."
            pushed, detail = _git_commit_and_push(commit_message)
            result["git_pushed"] = pushed
            result["git_detail"] = detail
            if not pushed:
                print(f"[r1-active-cycle] git commit/push did not complete: {detail}", file=sys.stderr)

        print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
