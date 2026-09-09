"""One-time repair: recompute NEO Movers (probabilities/neo_movers/
player_table) for the OK Open R1 snapshot against the now-final,
officially-reconciled leaderboard.

Root cause: whatever process wrote commit 49f8a9b ("publish: official
OK Open R1 final reconciliation") updated
OK_OPEN_2026_R1_LIVE_SNAPSHOT.json's leaderboard to the truly-final
18-hole rows but replaced the payload with a minimal shape that never
called klpga.neo_win.r1_live_probability's simulate_r1_live/
compute_neo_movers -- so probabilities/neo_movers/player_table (present
in every prior R1 cycle snapshot, e.g. r1_snapshots/
OK_OPEN_2026120001_SNAPSHOT_R1_1652.json) were silently dropped from
the "latest" convenience copy the site builder and tests read, even
though scripts/96's own contract (and
tests/test_ok_open_r1_movers_visibility.py's documented invariant)
requires that underlying data to always exist -- only the HTML omits
it.

This script re-runs the exact same real computation scripts/96 uses
(build_r1_sim_inputs -> simulate_r1_live -> compute_neo_movers ->
_build_player_table), fed with the ALREADY-COMMITTED, ALREADY-OFFICIAL
final leaderboard rows and the same real PRE inputs -- no network, no
fabricated data. It never changes the official leaderboard rows
themselves.

It deliberately does NOT write a new entry into content/website_v2/
r1_snapshots/ -- tests/test_phase7_generic_naming.py::
test_historical_r1_snapshots_directory_still_uses_legacy_naming_untouched
requires that real, already-collected directory to stay byte-for-byte
frozen (only its original OK_OPEN_-prefixed files, nothing added). Only
the mutable "latest" convenience copy (OK_OPEN_2026_R1_LIVE_SNAPSHOT.json)
is rewritten; the repair is traceable via this script + its "repair_note"
field + git history, not a new immutable snapshot file.

Usage: python scripts/102_ok_open_r1_recompute_final_movers.py
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_active_tournament_context  # noqa: E402
from klpga.neo_win.r1_live_probability import (  # noqa: E402
    build_r1_sim_inputs,
    compute_neo_movers,
    cutline_percentiles,
    simulate_r1_live,
)
_SPEC = importlib.util.spec_from_file_location(
    "ok_open_r1_active_cycle", ROOT / "scripts" / "96_ok_open_r1_active_cycle.py"
)
_cycle_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_cycle_mod)


def _read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def main() -> int:
    ctx = load_active_tournament_context()
    r1_live_snapshot = ctx.artifact_path("r1_live_snapshot")
    pre_master_path = ctx.artifact_path("pre_public_master")
    performance_path = ctx.artifact_path("pre_performance_snapshot")

    live = _read_json(r1_live_snapshot, None)
    if live is None:
        print(json.dumps({"action": "SKIP", "reason": "no r1_live_snapshot on disk"}))
        return 0
    if live.get("neo_movers"):
        print(json.dumps({"action": "SKIP", "reason": "neo_movers already present -- nothing to repair"}))
        return 0

    rows = live["leaderboard"]
    pre_master = _read_json(pre_master_path, {"records": []})
    pre_records = pre_master.get("records", [])
    pre_by_id = {str(r.get("player_id")): r for r in pre_records}
    performance = _read_json(performance_path, {"profiles": []})
    profiles = performance.get("profiles", [])

    r1_scores = {str(r.get("player_id")): r.get("total_under_par") for r in rows if r.get("total_under_par") is not None}
    sim_result = build_r1_sim_inputs(pre_records, profiles, r1_scores)
    prob_result = simulate_r1_live(sim_result.sim_inputs)
    movers = compute_neo_movers(pre_records, prob_result.probabilities, sim_result.sim_inputs)
    cutline = cutline_percentiles(prob_result.cutline_distribution)
    player_table = _cycle_mod._build_player_table(rows, prob_result.probabilities, sim_result.sim_inputs, pre_by_id)

    def _movers_json(entries):
        return [
            {"player_id": e.player_id, "player_name": e.player_name, "metric": e.metric,
             "pre_value": e.pre_value, "current_value": e.current_value, "delta": e.delta}
            for e in entries
        ]

    repair_stamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    recomputed = {
        "round": 1,
        "collected_at": live.get("collected_at"),
        "official_data_timestamp": live.get("official_data_timestamp"),
        "official_data_timestamp_note": live.get("official_data_timestamp_note"),
        "leaderboard": rows,
        "probabilities": prob_result.probabilities,
        "expected_cut_distribution": cutline,
        "cut_fraction_used": prob_result.cut_fraction_used,
        "n_simulations": prob_result.n_simulations,
        "excluded_no_r1_score": prob_result.excluded_no_r1_score,
        "neo_movers": {k: _movers_json(v) for k, v in movers.items()},
        "model_version": "r1_live_probability_v1",
        "build_id": repair_stamp,
        "input_provenance": {
            "pre_master": pre_master_path.name,
            "performance_snapshot": performance_path.name,
            "r1_leaderboard_source": "already-official, already-committed final R1 leaderboard (repair recompute, no network)",
            "population_fallback_players": sim_result.population_fallback_players,
            "missing_r1_players": sim_result.missing_r1_players,
        },
        "validation_result": live.get("validation_result"),
        "repair_note": (
            "neo_movers/probabilities/player_table recomputed by "
            "scripts/102_ok_open_r1_recompute_final_movers.py against the "
            "already-official final leaderboard after commit 49f8a9b "
            "dropped them from the live snapshot's minimal payload."
        ),
    }

    kind = f"R1_FINAL_RECOMPUTED_{repair_stamp.replace(':', '').replace('-', '')}"

    latest_payload = {**recomputed, "player_table": player_table, "kind": kind}
    r1_live_snapshot.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    result = {
        "action": "REPAIRED",
        "snapshot_path": str(r1_live_snapshot.relative_to(ROOT)),
        "beat_expectation_count": len(recomputed["neo_movers"].get("beat_expectation", [])),
        "missed_expectation_count": len(recomputed["neo_movers"].get("missed_expectation", [])),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
