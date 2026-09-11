"""R2 HOUSE: the canonical post-R2 forecast.

Generalizes scripts/101_ok_open_post_r2_final_forecast.py's Monte Carlo
call (same engine, klpga.neo_win.round_update_r2.simulate_post_round2)
away from that script's OK-Open-specific input sourcing (a
ground_truth_diagnostic/comparison_table.csv that only exists for OK
Open) onto this tournament's own verified R2 freeze
(klpga.neo_win.r2_freeze) -- the one real, already-validated source of
who made the cut and what they shot, for any tournament.

Consumes ONLY:
  - the verified PRE freeze (never re-read live data)
  - the verified, hash-intact R2 freeze (klpga.neo_win.r2_freeze)
  - leakage-safe features (klpga.neo_win.r2_leakage_gate)

remaining_rounds is COMPUTED from context.final_round_number -- 2
(round 2 is complete), never assumed to be 1 the way script 101's own
HARD_STOP did for OK Open's 3-round shape. simulate_post_round2 itself
is round-structure-generic (only requires remaining_rounds >= 1), so
this module works unmodified for a tournament with 1 or more rounds
remaining after R2.

N_SIMULATIONS is the module's own discovered constant
(klpga.neo_win.round_update.DEFAULT_N_SIMULATIONS = 5000) -- never an
assumed 10,000/100,000.

CANONICAL ARTIFACT CONTRACT: exactly one artifact_type,
"post_r2_final_forecast", resolved via TournamentContext.artifact_path
-- until a real R2 freeze exists, `post_r2_forecast_status()` reports
NOT_CREATED and `run_post_r2_forecast()` refuses to write anything.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import Optional

from klpga.neo_win import r2_leakage_gate
from klpga.neo_win.r2_freeze import load_r2_freeze, verify_r2_freeze_hash
from klpga.neo_win.round_update import DEFAULT_N_SIMULATIONS
from klpga.neo_win.round_update_r2 import PlayerR2SimInput, simulate_post_round2
from klpga.tournament_context import TournamentContext

STAGE_NOT_CREATED = "NOT_CREATED"
STAGE_CREATED = "CREATED"


class PostR2ForecastError(RuntimeError):
    """Hard-stop precondition failure -- no artifact is ever written
    when this is raised."""


def _num(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().upper().replace("+", "")
    if s in ("E", "EVEN"):
        return 0.0
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _expected_round(profile: dict) -> tuple[float, str]:
    """PRE-only performance expectation -- tries every known window key
    this codebase's PRE performance snapshots have used (KB's and OK
    Open's window-key vocabularies differ slightly), falls back to 0.0
    (population-neutral) rather than guessing. SG > 0 means better than
    field, so the score-to-par adjustment is negated."""
    windows = profile.get("windows") or {}
    for key in ("recent5", "recent3", "current", "recent10", "multi_season"):
        w = windows.get(key) or {}
        total = (w.get("components") or {}).get("total") or {}
        mean = _num(total.get("mean"))
        if mean is not None:
            return -mean, key
    return 0.0, "population_fallback"


def _spread_for(profile: dict) -> tuple[float, str]:
    c = profile.get("consistency") or {}
    for key in ("legacy_sample_sd", "population_sd_research"):
        v = _num(c.get(key))
        if v is not None and v > 0:
            return max(v, 0.5), key
    windows = profile.get("windows") or {}
    for key in ("multi_season", "recent10", "recent5", "recent3", "current"):
        total = ((windows.get(key) or {}).get("components") or {}).get("total") or {}
        for sk in ("sample_sd", "population_sd"):
            v = _num(total.get(sk))
            if v is not None and v > 0:
                return max(v, 0.5), f"{key}.{sk}"
    return 3.0, "population_fallback"


def _source_git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def post_r2_forecast_path(context: TournamentContext) -> Path:
    return context.artifact_path("post_r2_final_forecast")


def post_r2_forecast_status(context: TournamentContext) -> str:
    return STAGE_CREATED if post_r2_forecast_path(context).is_file() else STAGE_NOT_CREATED


def run_post_r2_forecast(
    context: TournamentContext,
    *,
    pre_performance_snapshot: dict,
    repo_root: Path,
    build_id: str,
    seed: int,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
) -> dict:
    """Builds and writes the ONE canonical post_r2_final_forecast
    artifact. Raises PostR2ForecastError (writes nothing) unless:
      - a verified, hash-intact R2 freeze exists for this game_code
      - every simulated player's inputs are leakage-safe (pre/r1/r2 only)
      - n_simulations > 0
    A player present in the freeze's ACTIVE (made-cut) set but missing
    a PRE performance profile is excluded from simulation and reported
    in `missing_players` -- never simulated on a guessed profile."""
    r2_leakage_gate.assert_stage_allowed("r2", context="post_r2_forecast input")

    freeze = load_r2_freeze(context)
    if freeze is None:
        raise PostR2ForecastError(f"no verified R2 freeze exists for game_code={context.game_code!r}")
    if not verify_r2_freeze_hash(context):
        raise PostR2ForecastError(f"R2 freeze for game_code={context.game_code!r} failed hash verification")
    if n_simulations <= 0:
        raise PostR2ForecastError(f"n_simulations must be > 0, got {n_simulations}")

    remaining_rounds = context.final_round_number - 2
    if remaining_rounds < 1:
        raise PostR2ForecastError(
            f"final_round_number={context.final_round_number} leaves {remaining_rounds} round(s) "
            "after R2 -- nothing to forecast"
        )

    profile_by = {str(p["player_id"]): p for p in pre_performance_snapshot.get("profiles", [])}

    active_records = [r for r in freeze["records"] if r.get("status") == "ACTIVE"]
    sim_inputs: list[PlayerR2SimInput] = []
    missing_players: list[dict] = []
    audit_by: dict[str, dict] = {}

    for row in active_records:
        pid = str(row["player_id"])
        profile = profile_by.get(pid)
        r1_score = _num(row.get("r1_score_to_par"))
        r2_score = _num(row.get("r2_score_to_par"))
        if profile is None or r1_score is None or r2_score is None:
            missing_players.append({
                "player_id": pid, "player_name": row.get("player_name"),
                "profile": profile is not None, "r1_score": r1_score is not None, "r2_score": r2_score is not None,
            })
            continue
        expected, expected_source = _expected_round(profile)
        spread, spread_source = _spread_for(profile)
        sim_inputs.append(PlayerR2SimInput(
            player_code=pid, player_name=row.get("player_name", pid),
            expected_round_score_to_par=expected, spread=spread,
            r1_score_to_par=r1_score, r2_score_to_par=r2_score, made_cut=True,
        ))
        audit_by[pid] = {
            "player_id": pid, "player_name": row.get("player_name", pid),
            "r1_score_to_par": r1_score, "r2_score_to_par": r2_score,
            "r2_total_to_par": r1_score + r2_score,
            "expected_final_round_to_par": expected, "expected_source": expected_source,
            "spread": spread, "spread_source": spread_source,
        }

    rng = random.Random(seed)
    result = simulate_post_round2(sim_inputs, remaining_rounds=remaining_rounds, n_simulations=n_simulations, rng=rng)

    rows = []
    for inp in sim_inputs:
        s = result[inp.player_code]
        rows.append({**audit_by[inp.player_code], "win_pct": float(s["win_pct"]), "top5_pct": float(s["top5_pct"]),
                     "top10_pct": float(s["top10_pct"]), "top20_pct": float(s["top20_pct"])})
    rows.sort(key=lambda x: (-x["win_pct"], -x["top5_pct"], x["r2_total_to_par"], x["player_name"]))
    for i, row in enumerate(rows, 1):
        row["neo_final_rank"] = i

    payload = {
        "schema_version": 1,
        "artifact": "post_r2_final_forecast",
        "game_code": context.game_code,
        "tournament_name": context.tournament_name,
        "stage": "POST_R2",
        "source_round": 2,
        "final_round_number": context.final_round_number,
        "remaining_rounds": remaining_rounds,
        "official_advancing_field_size": len(active_records),
        "simulated_field_size": len(rows),
        "missing_players": missing_players,
        "r2_freeze_artifact": freeze["schema_version"],
        "r2_freeze_sha256": freeze["parsed_canonical_sha256"],
        "future_data_excluded": True,
        "feature_cutoff": freeze["feature_cutoff"],
        "simulation_engine": "klpga.neo_win.round_update_r2.simulate_post_round2",
        "n_simulations": n_simulations,
        "seed": seed,
        "win_probability_sum_pct": sum(r["win_pct"] for r in rows),
        "code_commit": _source_git_sha(repo_root),
        "build_id": build_id,
        "records": rows,
    }
    r2_leakage_gate.assert_no_forbidden_result_fields(payload, context="post_r2_final_forecast payload")

    path = post_r2_forecast_path(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload
