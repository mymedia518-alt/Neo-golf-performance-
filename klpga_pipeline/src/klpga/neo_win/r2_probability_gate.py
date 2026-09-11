"""R2 HOUSE: probability hard gate.

Runs immediately before the post-R2 forecast artifact is trusted for
publication (never before -- see post_r2_forecast.run_post_r2_forecast,
which already writes the artifact; this gate is the publication-time
re-check every consumer, especially the publication gate, must run
against that artifact's own content rather than trusting it blindly).

ALL of the following must hold, or `validate_probability_gate` raises
ProbabilityGateError and the caller must treat this as NO ARTIFACT
(refuse to publish):
  - every probability value is finite (no NaN/inf)
  - 0 <= WIN <= 100, 0 <= TOP5 <= 100, 0 <= TOP10 <= 100, 0 <= TOP20 <= 100
  - per player: WIN <= TOP5 <= TOP10 <= TOP20
  - correct player population (matches the R2 freeze's ACTIVE set)
  - correct tournament (game_code matches)
  - source_round == 2
  - simulation count > 0
  - no future-source fields (future_data_excluded is True, no forbidden
    result fields)
"""
from __future__ import annotations

import math

from klpga.neo_win import r2_leakage_gate


class ProbabilityGateError(RuntimeError):
    pass


_PROB_FIELDS = ("win_pct", "top5_pct", "top10_pct", "top20_pct")


def validate_probability_gate(forecast: dict, *, expected_game_code: str, expected_active_player_ids: set[str]) -> None:
    if str(forecast.get("game_code")) != str(expected_game_code):
        raise ProbabilityGateError(
            f"wrong tournament: forecast game_code={forecast.get('game_code')!r}, expected {expected_game_code!r}"
        )
    if int(forecast.get("source_round", -1)) != 2:
        raise ProbabilityGateError(f"wrong source_round: {forecast.get('source_round')!r}, expected 2")
    n_sim = int(forecast.get("n_simulations", 0))
    if n_sim <= 0:
        raise ProbabilityGateError(f"simulation count must be > 0, got {n_sim}")
    if not forecast.get("future_data_excluded"):
        raise ProbabilityGateError("future_data_excluded must be True")
    r2_leakage_gate.assert_no_forbidden_result_fields(forecast, context="probability gate")

    records = forecast.get("records") or []
    observed_ids = {str(r["player_id"]) for r in records}
    if observed_ids != {str(x) for x in expected_active_player_ids}:
        missing = {str(x) for x in expected_active_player_ids} - observed_ids
        extra = observed_ids - {str(x) for x in expected_active_player_ids}
        raise ProbabilityGateError(
            f"population mismatch: {len(missing)} missing ({sorted(missing)[:5]}...), "
            f"{len(extra)} unexpected extra ({sorted(extra)[:5]}...)"
        )

    for row in records:
        pid = row.get("player_id")
        values = {}
        for field in _PROB_FIELDS:
            v = row.get(field)
            if v is None or not math.isfinite(v):
                raise ProbabilityGateError(f"player {pid}: {field} is not finite ({v!r})")
            if not (0.0 <= v <= 100.0):
                raise ProbabilityGateError(f"player {pid}: {field}={v} out of bounds [0,100]")
            values[field] = v
        if not (values["win_pct"] <= values["top5_pct"] <= values["top10_pct"] <= values["top20_pct"]):
            raise ProbabilityGateError(
                f"player {pid}: monotonicity violated "
                f"WIN={values['win_pct']} TOP5={values['top5_pct']} "
                f"TOP10={values['top10_pct']} TOP20={values['top20_pct']}"
            )
