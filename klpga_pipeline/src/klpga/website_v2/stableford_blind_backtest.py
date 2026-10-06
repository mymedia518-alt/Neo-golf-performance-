"""Frozen V1 blind-backtest methodology, GENERALIZED for replication
across target years (HJ 2026100004 gap, continued 2026-10-06).

This is a mechanical parameterization of
klpga.website_v2.stableford_2025_blind_backtest -- that module is left
completely untouched (still importable, still passing its own tests,
still the permanent record of the 2025 run) specifically so it can
never be "altered" by this generalization. Every formula, rate
definition, ranking rule, tie rule, and leakage rule here is copied
verbatim from that module; only the previously-hardcoded 2025 paths
(TARGET_GAME_CODE, PRIOR_DIR, the manifest filename) became function
parameters. test_stableford_blind_backtest_matches_frozen_2025.py
proves this by calling THIS module with the 2025 paths and asserting
the SAME SHA-256 (`232aee3f...`) the original module produces.

PIPELINE (strict order, never reversed) -- unchanged from 2025:
  1. build_preevent_snapshot(target_game_code, manifest_path, prior_dir,
     target_evidence_dir) -- reads ONLY the manifest's prior-tournament
     captures plus the target event's own NAME list (never a score/
     outcome from it). Computes real outcome counts/rates and the
     frozen klpga.website_v2.stableford_player_value formula per
     player.
  2. freeze_and_hash() -- unchanged.
  3. join_actual_results() -- unchanged, ONLY called after step 2.

ALBATROSS: never inferred -- unchanged. Every real capture used so far
(2023/2024/2025 target events and every one of their prior-season
captures) carries zero albatross-classed cells."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_player_value import StablefordValueBreakdown, from_season_rates

EVIDENCE_ROOT = Path(__file__).resolve().parents[3] / "evidence"  # .../klpga_pipeline/evidence
CONTENT_ROOT = Path(__file__).resolve().parents[3] / "content" / "website_v2"


@dataclass(frozen=True)
class PlayerPreEventRecord:
    player_name: str
    holes: int
    albatross: int
    eagle: int
    birdie: int
    par: int
    bogey: int
    double_or_worse: int
    tournaments_used: tuple[str, ...]
    birdie_rate: float
    eagle_rate: float
    par_rate: float
    bogey_rate: float
    double_or_worse_rate: float
    albatross_rate: float
    positive_scoring_contribution: float
    bogey_cost: float
    double_plus_downside: float
    net_expected_value: float
    pre_event_rank: int = 0  # filled in after sorting the whole field
    percentile: float = 0.0


def _aggregate_prior_outcomes(manifest_path: Path, prior_dir: Path) -> dict[str, dict]:
    """Real aggregation, holes-only: a round with 0 holes (WD/no-show)
    contributes nothing. Every count here traces to one of the
    manifest's own captures -- no other file is read. Identical logic
    to stableford_2025_blind_backtest._aggregate_prior_outcomes, just
    parameterized by manifest_path/prior_dir instead of the hardcoded
    2025 ones."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    game_codes = [e["game_code"] for e in manifest["entries"]]

    agg: dict[str, dict] = {}
    for game_code in game_codes:
        html = (prior_dir / f"{game_code}_scoreRecord.html").read_text(encoding="utf-8")
        by_round = extract_hole_outcomes(html)
        for round_label, by_name in by_round.items():
            for name, counts in by_name.items():
                if counts.total_holes == 0:
                    continue  # WD/no-show this round -- never fabricated as "0 outcomes over N holes"
                d = agg.setdefault(name, {
                    "albatross": 0, "eagle": 0, "birdie": 0, "par": 0, "bogey": 0,
                    "double_or_worse": 0, "holes": 0, "tournaments": set(),
                })
                d["albatross"] += counts.albatross
                d["eagle"] += counts.eagle
                d["birdie"] += counts.birdie
                d["par"] += counts.par
                d["bogey"] += counts.bogey
                d["double_or_worse"] += counts.double_or_worse
                d["holes"] += counts.total_holes
                d["tournaments"].add(game_code)
    return agg


def build_preevent_snapshot(
    target_game_code: str, manifest_path: Path, prior_dir: Path, target_evidence_dir: Path | None = None,
) -> list[PlayerPreEventRecord]:
    """Returns the FULL target field, ranked by net Stableford expected
    value computed EXCLUSIVELY from the manifest's prior-event
    captures. A player absent from those captures is simply not
    returned (never assigned a fabricated rate). Identical logic to
    stableford_2025_blind_backtest.build_preevent_snapshot."""
    if target_evidence_dir is None:
        target_evidence_dir = EVIDENCE_ROOT / f"stableford_source_probe_{target_game_code}"
    target_html = (target_evidence_dir / f"scoreRecord_{target_game_code}.html").read_text(encoding="utf-8")
    target_field = set(extract_hole_outcomes(target_html)["1R"].keys())

    agg = _aggregate_prior_outcomes(manifest_path, prior_dir)

    records = []
    for name in sorted(target_field):
        d = agg.get(name)
        if d is None or d["holes"] == 0:
            continue
        holes = d["holes"]
        rates = {
            "albatross_rate": d["albatross"] / holes,
            "eagle_rate": d["eagle"] / holes,
            "birdie_rate": d["birdie"] / holes,
            "par_rate": d["par"] / holes,
            "bogey_rate": d["bogey"] / holes,
            "double_or_worse_rate": d["double_or_worse"] / holes,
        }
        breakdown: StablefordValueBreakdown = from_season_rates(
            eagle_rate=rates["eagle_rate"], birdie_rate=rates["birdie_rate"],
            par_rate=rates["par_rate"], bogey_rate=rates["bogey_rate"],
            double_or_worse_rate=rates["double_or_worse_rate"],
            albatross_rate=rates["albatross_rate"],  # always 0.0 for every real player observed so far
        )
        records.append(PlayerPreEventRecord(
            player_name=name, holes=holes,
            albatross=d["albatross"], eagle=d["eagle"], birdie=d["birdie"],
            par=d["par"], bogey=d["bogey"], double_or_worse=d["double_or_worse"],
            tournaments_used=tuple(sorted(d["tournaments"])),
            birdie_rate=round(rates["birdie_rate"], 5),
            eagle_rate=round(rates["eagle_rate"], 5),
            par_rate=round(rates["par_rate"], 5),
            bogey_rate=round(rates["bogey_rate"], 5),
            double_or_worse_rate=round(rates["double_or_worse_rate"], 5),
            albatross_rate=round(rates["albatross_rate"], 5),
            positive_scoring_contribution=breakdown.positive_scoring_contribution,
            bogey_cost=breakdown.bogey_cost,
            double_plus_downside=breakdown.double_plus_downside,
            net_expected_value=breakdown.net_expectation,
        ))

    records.sort(key=lambda r: -r.net_expected_value)
    n = len(records)
    ranked = []
    for i, r in enumerate(records):
        rank = i + 1
        percentile = round(100 * (n - rank) / (n - 1), 2) if n > 1 else 100.0
        ranked.append(
            PlayerPreEventRecord(**{**asdict(r), "pre_event_rank": rank, "percentile": percentile})
        )
    return ranked


def freeze_and_hash(records: list[PlayerPreEventRecord]) -> tuple[str, list[dict]]:
    """Unchanged from stableford_2025_blind_backtest.freeze_and_hash."""
    payload = [asdict(r) for r in records]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=False, default=list)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest, payload


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Unchanged from stableford_2025_blind_backtest._spearman."""
    def fractional_ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks

    rx, ry = fractional_ranks(xs), fractional_ranks(ys)
    n = len(xs)
    mean_rx, mean_ry = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x ** 0.5 * var_y ** 0.5)


def _competition_rank(items: list[tuple[str, float]]) -> dict[str, int]:
    """Unchanged from stableford_2025_blind_backtest._competition_rank
    (T-rank: ties share a rank, next distinct value skips ahead)."""
    ordered = sorted(items, key=lambda x: -x[1])
    ranks: dict[str, int] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        for k in range(i, j + 1):
            ranks[ordered[k][0]] = i + 1
        i = j + 1
    return ranks


@dataclass(frozen=True)
class BlindEvaluationResult:
    n_joined: int
    spearman_correlation: float
    predicted_top10_names: tuple[str, ...]
    actual_top10_names: tuple[str, ...]
    top10_precision: float
    top10_recall: float
    predicted_top20_names: tuple[str, ...]
    actual_top20_names: tuple[str, ...]
    top20_precision: float
    top20_recall: float
    actual_top10_pre_event_ranks: tuple[int, ...]
    winner_name: str
    winner_actual_points: int
    winner_pre_event_rank: int
    winner_pre_event_percentile: float
    tie_rule: str = (
        "competition ranking (T-rank): players tied on actual Stableford points share the same "
        "rank number; the next distinct point total's rank skips ahead by the tie-block size -- "
        "the same convention a real golf leaderboard uses. 'actual TopN' therefore means "
        "rank<=N and may include MORE than N names when a tie straddles the boundary."
    )


def join_actual_results(
    pre_event_records: list[PlayerPreEventRecord],
    actual_points_by_name: dict[str, int],
    winner_name: str,
) -> BlindEvaluationResult:
    """Unchanged from stableford_2025_blind_backtest.join_actual_results
    -- ONLY call this after freeze_and_hash has already been computed
    and recorded."""
    pre_by_name = {r.player_name: r for r in pre_event_records}
    joined_names = sorted(set(pre_by_name) & set(actual_points_by_name))
    n = len(joined_names)

    pre_values = [pre_by_name[n_].net_expected_value for n_ in joined_names]
    actual_values = [actual_points_by_name[n_] for n_ in joined_names]
    spearman = round(_spearman(pre_values, actual_values), 4)

    predicted_sorted = sorted(joined_names, key=lambda n_: pre_by_name[n_].pre_event_rank)
    predicted_top10 = tuple(predicted_sorted[:10])
    predicted_top20 = tuple(predicted_sorted[:20])

    actual_rank = _competition_rank([(n_, actual_points_by_name[n_]) for n_ in joined_names])
    actual_top10 = tuple(sorted(n_ for n_ in joined_names if actual_rank[n_] <= 10))
    actual_top20 = tuple(sorted(n_ for n_ in joined_names if actual_rank[n_] <= 20))

    def _prec_recall(predicted: tuple[str, ...], actual: tuple[str, ...]) -> tuple[float, float]:
        inter = len(set(predicted) & set(actual))
        precision = round(inter / len(predicted), 4) if predicted else 0.0
        recall = round(inter / len(actual), 4) if actual else 0.0
        return precision, recall

    p10_prec, p10_rec = _prec_recall(predicted_top10, actual_top10)
    p20_prec, p20_rec = _prec_recall(predicted_top20, actual_top20)

    winner_record = pre_by_name[winner_name]

    return BlindEvaluationResult(
        n_joined=n,
        spearman_correlation=spearman,
        predicted_top10_names=predicted_top10,
        actual_top10_names=actual_top10,
        top10_precision=p10_prec,
        top10_recall=p10_rec,
        predicted_top20_names=predicted_top20,
        actual_top20_names=actual_top20,
        top20_precision=p20_prec,
        top20_recall=p20_rec,
        actual_top10_pre_event_ranks=tuple(sorted(pre_by_name[n_].pre_event_rank for n_ in actual_top10)),
        winner_name=winner_name,
        winner_actual_points=actual_points_by_name[winner_name],
        winner_pre_event_rank=winner_record.pre_event_rank,
        winner_pre_event_percentile=winner_record.percentile,
    )
