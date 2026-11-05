"""Build + publish the LIVE (mid-round) win/top-N probability for 대보
하우스디 챔피언십 (game_code 2026110001), using klpga.neo_win.sg_live_v1
-- the new, independent engine built to close the four confirmed
defects in the permanently-BLOCKED klpga.neo_win.r1_live_probability
(see that module's own docstring, and sg_live_v1.py's).

======================================================================
TOURNAMENT FORMAT -- WHAT IS AND ISN'T CONFIRMED
======================================================================
CONFIRMED (multiple independent real sources, cross-checked this
session): 3 rounds, 2026-11-06 through 2026-11-08, one round per day,
60-player field (official entry list, collected live).
NOT CONFIRMED: whether a 36-hole cut applies. Per this project's own
established discipline for an unconfirmed cut rule (see
klpga.website_v2.model_publication_gate.assert_cut_probability_not_
published_as_number / CUT_RULE_UNCONFIRMED_LABEL), this script never
simulates or publishes a cut probability: cut_after_round=ROUNDS and
cut_position=FIELD_SIZE are passed to the engine so the "cut" step is
mathematically a no-op (every real-eligible player always survives it)
-- this is a deliberate way to represent "cut status unconfirmed, not
modeled" using the existing engine, not a guess that there IS no cut.
Only Win/Top5/Top10/Top20 are published; no Cut% column exists.

======================================================================
PUBLICATION STATUS
======================================================================
Every output file carries model_status="REFERENCE_ESTIMATE" (never
"VALIDATED" -- see sg_live_v1.LIVE_V2_MODEL_STATUS) and the real RNG
seed used, so any published number can be exactly reproduced later.
Callers rendering this into a page MUST include the disclosure text
klpga.website_v2.model_publication_gate.REFERENCE_ESTIMATE_DISCLOSURE
("참고 예상") on the same page -- enforced by that module's
assert_reference_estimate_disclosed on promotion, not just by this
script's own intent.

======================================================================
OPERATING ASSUMPTION FOR PRIOR ROUNDS
======================================================================
This script reads content/website_v2/2026110001_LIVE_R{k}_SNAPSHOT.json
for every k < current_round as that round's FINAL state -- correct only
if scripts/306 is never re-run against an already-finished round after
collection has moved on to the next one (the orchestration's job, not
this script's). Before trusting any such file as final, this script
re-checks it with klpga.website_v2.freshness_gate.
assert_completed_round_has_no_incomplete_holes (round_complete=True) --
if that check fails, this script refuses to run rather than silently
treating a still-in-progress round as finished.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.sg_live_v1 import (  # noqa: E402
    LIVE_V2_MODEL_STATUS,
    PlayerSGForecast,
    build_live_states,
    simulate_live_tournament_outcomes,
)
from klpga.website_v2.freshness_gate import (  # noqa: E402
    FreshnessGateError,
    assert_completed_round_has_no_incomplete_holes,
    assert_no_silent_staleness,
    is_snapshot_stale,
)

GAME_CODE = "2026110001"
ROUNDS = 3  # confirmed: 3 rounds, one per day, 2026-11-06..11-08
CONTENT = ROOT / "content" / "website_v2"
FORECAST_PATH = CONTENT / f"DAEBO_{GAME_CODE}_PRE_SG_FORECAST_V1.json"
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json"
DEFAULT_N_SIMULATIONS = 60_000


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_forecasts() -> dict[str, PlayerSGForecast]:
    doc = _load(FORECAST_PATH)
    return {
        row["player_id"]: PlayerSGForecast(
            player_id=row["player_id"], mean_sg=row["mean_sg"], round_sd=row["round_sd"],
            rounds=row["rounds"], events=row["events"], effective_rounds=row["effective_rounds"],
            latest_sg_date=row["latest_sg_date"], has_player_sg=row["has_player_sg"],
        )
        for row in doc["forecasts"]
    }


def _load_prior_round_snapshot(round_number: int) -> dict:
    path = CONTENT / f"{GAME_CODE}_LIVE_R{round_number}_SNAPSHOT.json"
    if not path.exists():
        raise RuntimeError(
            f"round {round_number} is before current_round but has no snapshot at {path} -- "
            "cannot build real completed-round scores without it. Run scripts/306 for that round first."
        )
    snapshot = _load(path)
    player_table = [
        {"status": p["status"], "holes_completed": p["holes_completed"], "player_name": p["player_name"]}
        for p in snapshot["players"]
    ]
    try:
        assert_completed_round_has_no_incomplete_holes(player_table, round_complete=True, label=f"round {round_number}")
    except FreshnessGateError as exc:
        raise RuntimeError(
            f"round {round_number}'s snapshot still shows in-progress players -- refusing to treat it as "
            f"a final, real completed round. Original error: {exc}"
        ) from exc
    return snapshot


def build(*, current_round: int, seed: int, n_simulations: int, max_staleness_minutes: int) -> dict:
    forecasts = _load_forecasts()
    entry = _load(ENTRY_PATH)
    player_ids = [str(row["player_code"]) for row in entry["records"]]
    name_by_id = {str(row["player_code"]): row["player_name"] for row in entry["records"]}

    completed_round_scores_by_player: dict[str, list] = {pid: [] for pid in player_ids}
    for k in range(1, current_round):
        snap = _load_prior_round_snapshot(k)
        rows_by_player = {p["player_code"]: p for p in snap["players"]}
        for pid in player_ids:
            row = rows_by_player.get(pid)
            completed_round_scores_by_player[pid].append(
                row["today_under_par"] if row is not None else None
            )

    current_snapshot_path = CONTENT / f"{GAME_CODE}_LIVE_R{current_round}_SNAPSHOT.json"
    current_snapshot = _load(current_snapshot_path)
    now = datetime.now(timezone.utc)
    stale = is_snapshot_stale(current_snapshot["collected_at"], now, max_age_seconds=max_staleness_minutes * 60)
    current_round_rows = {
        p["player_code"]: {
            "today_under_par": p["today_under_par"],
            "holes_completed": p["holes_completed"],
            "status": p["status"],
        }
        for p in current_snapshot["players"]
    }
    status_by_player = {p["player_code"]: p["status"] for p in current_snapshot["players"]}

    try:
        assert_completed_round_has_no_incomplete_holes(current_snapshot["players"], round_complete=True, label="current round")
        round_complete = True
    except FreshnessGateError:
        round_complete = False

    live_states, excluded = build_live_states(
        player_ids, current_round=current_round,
        completed_round_scores_by_player=completed_round_scores_by_player,
        current_round_rows=current_round_rows,
    )

    result = simulate_live_tournament_outcomes(
        forecasts, live_states, rounds=ROUNDS, cut_after_round=ROUNDS, cut_position=len(player_ids),
        current_round=current_round, n_simulations=n_simulations, seed=seed,
    )

    assumed_default_start_players = [
        p["player_code"] for p in current_snapshot["players"] if p.get("assumed_default_start")
    ]

    out = {
        "schema_version": 1,
        "game_code": GAME_CODE,
        "current_round": current_round,
        "rounds_total": ROUNDS,
        "model": "klpga.neo_win.sg_live_v1.simulate_live_tournament_outcomes",
        "model_status": LIVE_V2_MODEL_STATUS,
        "disclosure": "참고 예상 -- 독립 Red Team 검증을 거치지 않은 실험적 실시간 모델입니다. 공식 순위가 아닙니다.",
        "cut_rule_confirmed": False,
        "cut_modeled": False,
        "seed": seed,
        "n_simulations": n_simulations,
        "collected_at": current_snapshot["collected_at"],
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "is_stale": stale,
        "stale_threshold_minutes": max_staleness_minutes,
        "round_complete": round_complete,
        "excluded_players": [
            {"player_id": pid, "player_name": name_by_id.get(pid), "reason": reason} for pid, reason in excluded.items()
        ],
        "eliminated_players": [
            {"player_id": pid, "player_name": name_by_id.get(pid), "status": status_by_player.get(pid)}
            for pid in result.eliminated_players
        ],
        "assumed_default_start_players": [
            {"player_id": pid, "player_name": name_by_id.get(pid)} for pid in assumed_default_start_players
        ],
        "probabilities": [
            {
                "player_id": pid,
                "player_name": name_by_id.get(pid),
                "holes_completed": live_states[pid].holes_completed if pid in live_states else None,
                "today_under_par": live_states[pid].current_round_score_so_far if pid in live_states else None,
                **probs,
            }
            for pid, probs in sorted(result.probabilities.items(), key=lambda kv: -kv[1]["win_probability"])
        ],
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-round", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int, help="Required: persisted in the output for reproducibility.")
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--max-staleness-minutes", type=int, default=45)
    args = parser.parse_args()

    out = build(
        current_round=args.current_round, seed=args.seed,
        n_simulations=args.n_simulations, max_staleness_minutes=args.max_staleness_minutes,
    )
    encoded = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    out_path = CONTENT / f"DAEBO_{GAME_CODE}_LIVE_PROBABILITY_R{args.current_round}_V1.json"
    out_path.write_text(encoded, encoding="utf-8")
    # Stable, round-agnostic fetch target for the live page's client-side
    # JS -- avoids the page needing to know which round is "current" on
    # its own. Byte-identical content to the round-specific file above;
    # this is purely a convenience copy, never a second source of truth.
    latest_path = CONTENT / f"DAEBO_{GAME_CODE}_LIVE_PROBABILITY_LATEST.json"
    latest_path.write_text(encoded, encoding="utf-8")
    print(f"wrote {out_path} and {latest_path}: seed={out['seed']} is_stale={out['is_stale']} "
          f"excluded={len(out['excluded_players'])} eliminated={len(out['eliminated_players'])}")


if __name__ == "__main__":
    main()
