"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- apply the FROZEN
Stableford V1 pipeline to the real 2026 field, unchanged.

This is NOT a new model. Every formula/coefficient/ranking rule below
is imported directly from the already-frozen, already-blind-backtest-
verified modules (klpga.website_v2.stableford_player_value.
from_season_rates, klpga.website_v2.stableford_blind_backtest.
_aggregate_prior_outcomes) -- see content/website_v2/STABLEFORD_V1_
REPRODUCTION_VERIFICATION.md for the reproduction proof against the
2023/2024/2025 blind backtests.

THE ONE STRUCTURAL DIFFERENCE from the 2023/2024/2025 backtests: those
read the target field's names from the target event's OWN scoreRecord
page (post-hoc, since the event had already happened). 2026100004 has
not happened yet, so the field here comes from the real official
entry-list acquisition instead (content/website_v2/2026100004_
CANONICAL_PLAYER_IDENTITY_V1.json, 108 real entrants, playerCode-
reconciled). klpga.website_v2.stableford_backtest_snapshot's own
module docstring already establishes this is not a leakage violation
-- "entry lists are genuinely knowable before day 1" -- it is in fact
MORE honest than reading names off a finished event's page, since here
the event genuinely has not started.

Per explicit instruction:
  - no new 0-100 score invented
  - no new weights invented
  - a player with zero matched prior-tournament data is never
    assigned an imputed value -- reported as DATA_LIMITED (no rank)
  - a player whose matched prior sample is thin (< MIN_ROUNDS_
    QUALIFIED real rounds, the same pre-declared, non-arbitrary floor
    already used and justified in scripts/214_finalize_reconstruction
    _verdict.py for the official-stat reconstruction) is still ranked
    (matching the 2023/2024/2025 precedent, which never excluded thin-
    sample players either) but flagged DATA_LIMITED for disclosure
  - name matching against the prior-tournament aggregation is EXACT
    string match only -- a name that doesn't match contributes
    nothing, is never fuzzy-matched, and is never treated as "0
    prior-event rate" (that would be fabricating a real value, not
    reporting an absence)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from klpga.website_v2.stableford_blind_backtest import _aggregate_prior_outcomes
from klpga.website_v2.stableford_player_value import StablefordValueBreakdown, from_season_rates

MIN_ROUNDS_QUALIFIED = 10


@dataclass(frozen=True)
class PlayerV1Record:
    player_code: str
    player_name: str
    nationality: str | None
    official_sponsor: str
    identity_reconciliation_status: str
    data_status: str  # "OK" | "DATA_LIMITED_THIN_SAMPLE" | "DATA_LIMITED_NO_PRIOR_DATA"
    rounds: int | None
    holes: int | None
    albatross: int | None
    eagle: int | None
    birdie: int | None
    par: int | None
    bogey: int | None
    double_or_worse: int | None
    albatross_rate: float | None
    eagle_rate: float | None
    birdie_rate: float | None
    par_rate: float | None
    bogey_rate: float | None
    double_or_worse_rate: float | None
    net_expected_value: float | None  # == klpga.website_v2.stableford_player_value's net_expectation, unchanged
    pre_event_rank: int | None = None  # filled in only for data_status != DATA_LIMITED_NO_PRIOR_DATA
    percentile: float | None = None


def build_2026_field_snapshot(
    canonical_identity_path: Path, manifest_path: Path, prior_dir: Path,
    min_rounds_qualified: int = MIN_ROUNDS_QUALIFIED,
) -> list[PlayerV1Record]:
    identity = json.loads(canonical_identity_path.read_text(encoding="utf-8"))
    agg = _aggregate_prior_outcomes(manifest_path, prior_dir)

    unranked: list[PlayerV1Record] = []
    rankable: list[tuple[PlayerV1Record, float]] = []

    for r in identity["records"]:
        name = r["player_name"]
        d = agg.get(name)
        base = {
            "player_code": r["player_code"], "player_name": name, "nationality": r["nationality"],
            "official_sponsor": r["official_sponsor"],
            "identity_reconciliation_status": r["identity_reconciliation_status"],
        }
        if d is None or d["holes"] == 0:
            unranked.append(PlayerV1Record(
                **base, data_status="DATA_LIMITED_NO_PRIOR_DATA",
                rounds=None, holes=None, albatross=None, eagle=None, birdie=None, par=None, bogey=None,
                double_or_worse=None, albatross_rate=None, eagle_rate=None, birdie_rate=None, par_rate=None,
                bogey_rate=None, double_or_worse_rate=None, net_expected_value=None,
            ))
            continue

        holes = d["holes"]
        rounds = holes // 18
        rates = {
            "albatross_rate": d["albatross"] / holes, "eagle_rate": d["eagle"] / holes,
            "birdie_rate": d["birdie"] / holes, "par_rate": d["par"] / holes,
            "bogey_rate": d["bogey"] / holes, "double_or_worse_rate": d["double_or_worse"] / holes,
        }
        breakdown: StablefordValueBreakdown = from_season_rates(
            eagle_rate=rates["eagle_rate"], birdie_rate=rates["birdie_rate"], par_rate=rates["par_rate"],
            bogey_rate=rates["bogey_rate"], double_or_worse_rate=rates["double_or_worse_rate"],
            albatross_rate=rates["albatross_rate"],
        )
        data_status = "DATA_LIMITED_THIN_SAMPLE" if rounds < min_rounds_qualified else "OK"
        record = PlayerV1Record(
            **base, data_status=data_status, rounds=rounds, holes=holes,
            albatross=d["albatross"], eagle=d["eagle"], birdie=d["birdie"], par=d["par"], bogey=d["bogey"],
            double_or_worse=d["double_or_worse"],
            albatross_rate=round(rates["albatross_rate"], 5), eagle_rate=round(rates["eagle_rate"], 5),
            birdie_rate=round(rates["birdie_rate"], 5), par_rate=round(rates["par_rate"], 5),
            bogey_rate=round(rates["bogey_rate"], 5), double_or_worse_rate=round(rates["double_or_worse_rate"], 5),
            net_expected_value=breakdown.net_expectation,
        )
        rankable.append((record, breakdown.net_expectation))

    rankable.sort(key=lambda item: -item[1])
    n = len(rankable)
    ranked: list[PlayerV1Record] = []
    for i, (record, _) in enumerate(rankable):
        rank = i + 1
        percentile = round(100 * (n - rank) / (n - 1), 2) if n > 1 else 100.0
        ranked.append(_with_rank(record, rank, percentile))

    return ranked + unranked


def _with_rank(record: PlayerV1Record, rank: int, percentile: float) -> PlayerV1Record:
    from dataclasses import asdict
    return PlayerV1Record(**{**asdict(record), "pre_event_rank": rank, "percentile": percentile})
