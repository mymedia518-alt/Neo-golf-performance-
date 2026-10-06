"""2025 TRUE BLIND BACKTEST (HJ 2026100004 gap, continued 2026-10-06).

Question: "2025 HJ중공업·동부건설 챔피언십 결과를 전혀 모르는 상태에서, 대회
시작 전 실제 기록만으로 김민솔을 Stableford에 강한 선수로 식별할 수 있었는가?"

PIPELINE (strict order, never reversed):
  1. build_preevent_snapshot() -- reads ONLY the 23 real captures under
     evidence/stableford_prior_2025/ (all independently confirmed
     strictly before 2025100001's own 2025-10-01 start, see
     klpga.website_v2.stableford_prior_tournament_manifest) plus the
     2025100001 field's own NAME list (not scores) to know who to
     report on. Computes real outcome counts/rates and the frozen
     klpga.website_v2.stableford_player_value formula per player.
     Returns a ranking with a content-hash for provenance.
  2. freeze_and_hash() -- serializes that ranking deterministically and
     SHA-256's it, so the hash can be checked/quoted BEFORE step 3 ever
     touches an actual result.
  3. join_actual_results() -- ONLY called after step 2 -- reads the
     ALREADY-RECONSTRUCTED real 2025100001 Stableford totals (see
     tests/test_stableford_2025100001_reconstruction.py) and computes
     evaluation metrics. This module's own tests call these in that
     exact order and assert the frozen hash from step 2 is identical
     whether or not step 3 has run yet -- proving the ranking really
     was frozen before evaluation, not just claimed to be.

ALBATROSS: never inferred. Every real pre-event capture (same 5-class
vocabulary confirmed for the 3 target events: par/birdies/bogeys/
Dbogeys/eagles, no albatross class anywhere) carries zero albatross
occurrences, so albatross_rate is always exactly 0.0, passed through
stableford_player_value.from_season_rates without a source string
(matching that function's own "default 0.0, no source needed" path).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_player_value import StablefordValueBreakdown, from_season_rates
from klpga.website_v2.stableford_prior_tournament_manifest import build_manifest
from klpga.website_v2.stableford_historical_dates import HISTORICAL_EVENT_DATES

EVIDENCE_ROOT = Path(__file__).resolve().parents[3] / "evidence"  # .../klpga_pipeline/evidence
PRIOR_DIR = EVIDENCE_ROOT / "stableford_prior_2025"
TARGET_GAME_CODE = "2025100001"


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


def _aggregate_prior_outcomes() -> dict[str, dict]:
    """Real aggregation, holes-only: a round with 0 holes (WD/no-show)
    contributes nothing. Every count here traces to one of the 23
    manifest captures -- no other file is read."""
    manifest = json.loads(
        (Path(__file__).resolve().parents[3] / "content" / "website_v2"
         / "STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json").read_text(encoding="utf-8")
    )
    game_codes = [e["game_code"] for e in manifest["entries"]]

    agg: dict[str, dict] = {}
    for game_code in game_codes:
        html = (PRIOR_DIR / f"{game_code}_scoreRecord.html").read_text(encoding="utf-8")
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


def build_preevent_snapshot() -> list[PlayerPreEventRecord]:
    """Returns the FULL 2025 target field, ranked by net Stableford
    expected value computed EXCLUSIVELY from the 23 pre-event captures.
    A player absent from those captures is simply not returned (never
    assigned a fabricated rate) -- see this snapshot's own
    `players_covered` vs the target field size for the coverage gap."""
    target_html = (EVIDENCE_ROOT / f"stableford_source_probe_{TARGET_GAME_CODE}"
                   / f"scoreRecord_{TARGET_GAME_CODE}.html").read_text(encoding="utf-8")
    target_field = set(extract_hole_outcomes(target_html)["1R"].keys())

    agg = _aggregate_prior_outcomes()

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
            albatross_rate=rates["albatross_rate"],  # always 0.0 for every real player this turn
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
    """Deterministic serialization + SHA-256 -- the integrity mechanism
    proving this ranking was computed before any actual-result data was
    touched. Field order and dict key order are fixed by
    PlayerPreEventRecord's own declaration order (dataclasses preserve
    it), never re-sorted by the JSON encoder."""
    payload = [asdict(r) for r in records]
    # tournaments_used is a tuple -> JSON list; everything else is already JSON-native.
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=False, default=list)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest, payload


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Plain rank-based Pearson correlation -- no scipy in this
    environment. Average (fractional) ranks for ties, the standard
    Spearman tie convention."""
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
    """Standard "T-rank" (ties share a rank, next distinct value skips
    ahead by the tie count) -- the SAME convention a real golf
    leaderboard uses (T9, T9, then 11), explicitly handled rather than
    left ambiguous. items: [(name, value)], higher value = better rank."""
    ordered = sorted(items, key=lambda x: -x[1])
    ranks: dict[str, int] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        for k in range(i, j + 1):
            ranks[ordered[k][0]] = i + 1  # all tied players get the rank of the first position in the tie block
        i = j + 1
    return ranks


@dataclass(frozen=True)
class BlindEvaluationResult:
    n_joined: int
    spearman_correlation: float
    predicted_top10_names: tuple[str, ...]
    actual_top10_names: tuple[str, ...]  # competition-rank <= 10, ties included (may be >10 names)
    top10_precision: float  # |predicted ∩ actual| / |predicted|
    top10_recall: float  # |predicted ∩ actual| / |actual|
    predicted_top20_names: tuple[str, ...]
    actual_top20_names: tuple[str, ...]
    top20_precision: float
    top20_recall: float
    actual_top10_pre_event_ranks: tuple[int, ...]  # the pre-event rank of each real actual-Top10 player
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
    """ONLY call this after freeze_and_hash has already been computed
    and recorded -- see this module's own docstring and
    tests/test_stableford_2025_blind_backtest.py's ordering proof.
    Evaluates over the JOIN of (pre-event-covered player) AND (has a
    real actual Stableford total) -- never a feature-engineering join,
    purely for scoring the already-frozen ranking."""
    pre_by_name = {r.player_name: r for r in pre_event_records}
    joined_names = sorted(set(pre_by_name) & set(actual_points_by_name))
    n = len(joined_names)

    pre_values = [pre_by_name[n_].net_expected_value for n_ in joined_names]
    actual_values = [actual_points_by_name[n_] for n_ in joined_names]
    spearman = round(_spearman(pre_values, actual_values), 4)

    # predicted TopN: by the FROZEN pre-event rank, restricted to names that are part of this join
    # (a frozen-Top10 player absent from the join has no actual result to score against at all).
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
