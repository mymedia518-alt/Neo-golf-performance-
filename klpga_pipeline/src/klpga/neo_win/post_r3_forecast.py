"""R3 HOUSE: the canonical post-R3 forecast.

Generalizes the proven post_r2_forecast.py pattern one round later:
same engine family (klpga.neo_win.round_update_r3.simulate_post_round3,
the real, verified R3 Monte Carlo engine already used by BETA #001's
own R3/R4 pipeline), same TournamentContext-based generic input
sourcing -- consumes ONLY the verified, hash-intact R3 freeze
(klpga.neo_win.r3_freeze) plus the verified PRE performance snapshot,
never a tournament-specific model.

NO "ADVANCES TO FINAL" PROBABILITY -- by R3 every real advancing player
has already made the cut (settled at R2); there is no new elimination
event between R3 and FINAL (see round_update_r3.py's own module
docstring). This module therefore forecasts ONLY the single remaining
round (FINAL/R4) -- remaining_rounds is COMPUTED from
context.final_round_number - 3, never assumed to be 1.

N_SIMULATIONS is the module's own discovered constant
(klpga.neo_win.round_update.DEFAULT_N_SIMULATIONS) -- the current NEO
Monte Carlo production contract (10,000 as of fix/kb-r2-official-cut-
gate-20260911's explicit production-contract change), shared by every
round_update-family engine. A caller publishing this forecast for real
must additionally pass it through
klpga.neo_win.production_simulation_gate.assert_production_simulation_count
before trusting it for publication -- this module itself only refuses
n_simulations <= 0, matching post_r2_forecast.py's own precondition
scope (mathematical validity, not the separate production-contract
policy check).

CANONICAL ARTIFACT CONTRACT: exactly one artifact_type,
"post_r3_final_forecast", resolved via TournamentContext.artifact_path
-- until a real R3 freeze exists, `post_r3_forecast_status()` reports
NOT_CREATED and `run_post_r3_forecast()` refuses to write anything.

A player in the R3 freeze's ACTIVE set who withdrew/was disqualified/
did not start DURING R3 itself (status WD/DQ/DNS at R3, distinct from
CUT which is settled before R3 even starts) is excluded from
simulation and reported in `missing_players` -- never simulated on a
fabricated score. Likewise a player missing a PRE performance profile.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import Optional

from klpga.neo_win import r3_leakage_gate
from klpga.neo_win.r3_freeze import load_r3_freeze, verify_r3_freeze_hash
from klpga.neo_win.round_update import DEFAULT_N_SIMULATIONS
from klpga.neo_win.round_update_r3 import PlayerR3SimInput, simulate_post_round3
from klpga.tournament_context import TournamentContext

STAGE_NOT_CREATED = "NOT_CREATED"
STAGE_CREATED = "CREATED"


class PostR3ForecastError(RuntimeError):
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
    """Same PRE-only performance expectation as post_r2_forecast.py's
    equivalent (see that module for the full window-key trace) -- SG >
    0 means better than field, so the score-to-par adjustment is
    negated."""
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


def post_r3_forecast_path(context: TournamentContext) -> Path:
    return context.artifact_path("post_r3_final_forecast")


def post_r3_forecast_status(context: TournamentContext) -> str:
    return STAGE_CREATED if post_r3_forecast_path(context).is_file() else STAGE_NOT_CREATED


def run_post_r3_forecast(
    context: TournamentContext,
    *,
    pre_performance_snapshot: dict,
    repo_root: Path,
    build_id: str,
    seed: int,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
) -> dict:
    """Builds and writes the ONE canonical post_r3_final_forecast
    artifact. Raises PostR3ForecastError (writes nothing) unless:
      - a verified, hash-intact R3 freeze exists for this game_code
      - every simulated player's inputs are leakage-safe (pre/r1/r2/r3 only)
      - n_simulations > 0
    A player present in the freeze's ACTIVE set but missing a PRE
    performance profile, or WD/DQ/DNS at R3 itself, is excluded from
    simulation and reported in `missing_players` -- never simulated on
    a guessed profile."""
    r3_leakage_gate.assert_stage_allowed("r3", context="post_r3_forecast input")

    freeze = load_r3_freeze(context)
    if freeze is None:
        raise PostR3ForecastError(f"no verified R3 freeze exists for game_code={context.game_code!r}")
    if not verify_r3_freeze_hash(context):
        raise PostR3ForecastError(f"R3 freeze for game_code={context.game_code!r} failed hash verification")
    if n_simulations <= 0:
        raise PostR3ForecastError(f"n_simulations must be > 0, got {n_simulations}")

    remaining_rounds = context.final_round_number - 3
    if remaining_rounds < 1:
        raise PostR3ForecastError(
            f"final_round_number={context.final_round_number} leaves {remaining_rounds} round(s) "
            "after R3 -- nothing to forecast"
        )

    profile_by = {str(p["player_id"]): p for p in pre_performance_snapshot.get("profiles", [])}

    active_records = [r for r in freeze["records"] if r.get("status", "ACTIVE") == "ACTIVE"]
    sim_inputs: list[PlayerR3SimInput] = []
    missing_players: list[dict] = []
    audit_by: dict[str, dict] = {}

    for row in active_records:
        pid = str(row["player_id"])
        profile = profile_by.get(pid)
        r1_score = _num(row.get("r1_score_to_par"))
        r2_score = _num(row.get("r2_score_to_par"))
        r3_score = _num(row.get("r3_score_to_par"))
        if profile is None or r1_score is None or r2_score is None or r3_score is None:
            missing_players.append({
                "player_id": pid, "player_name": row.get("player_name"),
                "profile": profile is not None, "r1_score": r1_score is not None,
                "r2_score": r2_score is not None, "r3_score": r3_score is not None,
            })
            continue
        expected, expected_source = _expected_round(profile)
        spread, spread_source = _spread_for(profile)
        sim_inputs.append(PlayerR3SimInput(
            player_code=pid, player_name=row.get("player_name", pid),
            expected_round_score_to_par=expected, spread=spread,
            r1_score_to_par=r1_score, r2_score_to_par=r2_score, r3_score_to_par=r3_score, made_cut=True,
        ))
        audit_by[pid] = {
            "player_id": pid, "player_name": row.get("player_name", pid),
            "r1_score_to_par": r1_score, "r2_score_to_par": r2_score, "r3_score_to_par": r3_score,
            "r3_total_to_par": r1_score + r2_score + r3_score,
            "expected_final_round_to_par": expected, "expected_source": expected_source,
            "spread": spread, "spread_source": spread_source,
        }

    rng = random.Random(seed)
    result = simulate_post_round3(sim_inputs, n_simulations=n_simulations, rng=rng)

    rows = []
    for inp in sim_inputs:
        s = result[inp.player_code]
        rows.append({**audit_by[inp.player_code], "win_pct": float(s["win_pct"]), "top5_pct": float(s["top5_pct"]),
                     "top10_pct": float(s["top10_pct"]), "top20_pct": float(s["top20_pct"])})
    rows.sort(key=lambda x: (-x["win_pct"], -x["top5_pct"], x["r3_total_to_par"], x["player_name"]))
    for i, row in enumerate(rows, 1):
        row["neo_final_rank"] = i

    payload = {
        "schema_version": 1,
        "artifact": "post_r3_final_forecast",
        "game_code": context.game_code,
        "tournament_name": context.tournament_name,
        "stage": "POST_R3",
        "source_round": 3,
        "final_round_number": context.final_round_number,
        "remaining_rounds": remaining_rounds,
        "official_advancing_field_size": len(active_records),
        "simulated_field_size": len(rows),
        "missing_players": missing_players,
        "r3_freeze_artifact": freeze["schema_version"],
        "r3_freeze_sha256": freeze["parsed_canonical_sha256"],
        "future_data_excluded": True,
        "feature_cutoff": freeze["feature_cutoff"],
        "simulation_engine": "klpga.neo_win.round_update_r3.simulate_post_round3",
        "n_simulations": n_simulations,
        "seed": seed,
        "win_probability_sum_pct": sum(r["win_pct"] for r in rows),
        "code_commit": _source_git_sha(repo_root),
        "build_id": build_id,
        "records": rows,
    }
    r3_leakage_gate.assert_no_forbidden_result_fields(payload, context="post_r3_final_forecast payload")

    path = post_r3_forecast_path(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload
