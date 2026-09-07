"""PHASE B red-team: does the current production feature construction
(``home_ranking.build_features`` -- a naive mean of raw event totals)
bias NEO Ranking against players with fewer rounds/events, and does the
V2 candidate (``neo_ranking_v2_candidate.py``, VALIDATION_MODEL_NOT_
PRODUCTION) fix it?

Each test is a synthetic case from the NEO GOLF DATA handoff's PHASE B.
Where the naive method is provably wrong, the test asserts it fails
(documenting the real bug) AND asserts the candidate passes."""
from __future__ import annotations

import statistics

import pytest

from klpga.website_v2.neo_ranking_v2_candidate import (
    EventObservation,
    ShrinkagePrior,
    estimate_shrinkage_prior_from_warehouse,
    estimate_skill,
    naive_event_total_mean,
    pooled_per_round_rate,
)


# --- Case 1: equal per-round performance, unequal rounds ------------------

def test_case1_equal_per_round_performance_must_rank_equal():
    # A: 4 rounds, stable +1 SG/round -> total +4
    a = [EventObservation(total_sg=4.0, rounds=4)]
    # B: 2 rounds, stable +1 SG/round, missed cut -> total +2
    b = [EventObservation(total_sg=2.0, rounds=2)]

    naive_a, naive_b = naive_event_total_mean(a), naive_event_total_mean(b)
    assert naive_a != naive_b, "documents the bug: naive method treats equal skill as unequal"
    assert naive_a > naive_b

    candidate_a, candidate_b = pooled_per_round_rate(a), pooled_per_round_rate(b)
    assert candidate_a == pytest.approx(candidate_b), "candidate must recognize equal per-round skill"
    assert candidate_a == pytest.approx(1.0)


# --- Case 2: equal totals, unequal rounds -> NOT equal performance --------

def test_case2_equal_totals_unequal_rounds_are_not_equivalent():
    a = [EventObservation(total_sg=4.0, rounds=4)]  # +1 SG/round
    b = [EventObservation(total_sg=4.0, rounds=2)]  # +2 SG/round

    naive_a, naive_b = naive_event_total_mean(a), naive_event_total_mean(b)
    assert naive_a == pytest.approx(naive_b), "documents the bug: naive method calls these equal"

    rate_a, rate_b = pooled_per_round_rate(a), pooled_per_round_rate(b)
    assert rate_b > rate_a, "B produced +2 SG/round vs A's +1 SG/round -- candidate must distinguish them"
    assert rate_a == pytest.approx(1.0)
    assert rate_b == pytest.approx(2.0)


# --- Case 3: same true rate, different sample size -> similar center, A more certain ---

def test_case3_same_rate_different_sample_size_similar_center():
    prior = ShrinkagePrior(population_mean_per_round=0.0, between_player_variance=1.0, within_player_variance=4.0)
    a = [EventObservation(total_sg=4.0, rounds=4) for _ in range(10)]  # 10 tournaments x 4 rounds, +1/round
    b = [EventObservation(total_sg=4.0, rounds=4) for _ in range(5)]  # 5 tournaments x 4 rounds, +1/round

    skill_a = estimate_skill("A", a, prior)
    skill_b = estimate_skill("B", b, prior)

    assert skill_a.observed_rate == pytest.approx(skill_b.observed_rate), "identical true rate must give identical raw rate"
    # A must not be rewarded merely for having more observations: shrunk estimates
    # should be close (both far from 0 toward their shared observed rate), but A's
    # weight (confidence) must be strictly higher since it has double the rounds.
    assert skill_a.shrinkage_weight > skill_b.shrinkage_weight
    assert skill_a.total_rounds == 40 and skill_b.total_rounds == 20


# --- Case 4: many mediocre rounds vs few elite rounds -> shrinkage required ---

def test_case4_small_sample_elite_performance_is_shrunk_toward_mean_but_not_always_below_large_sample():
    prior = ShrinkagePrior(population_mean_per_round=0.0, between_player_variance=1.0, within_player_variance=4.0)
    # A: many rounds, mediocre (+0.2/round)
    a = [EventObservation(total_sg=0.8, rounds=4) for _ in range(15)]
    # B: few rounds, elite observed performance (+3.0/round) but tiny sample
    b = [EventObservation(total_sg=3.0, rounds=1)]

    skill_a = estimate_skill("A", a, prior)
    skill_b = estimate_skill("B", b, prior)

    assert skill_b.observed_rate > skill_a.observed_rate, "B's raw observed rate is genuinely higher"
    # The whole point of shrinkage: B's tiny sample must be pulled hard toward the
    # population mean, while A's large sample stays close to its own observed rate.
    assert skill_b.shrunk_rate < skill_b.observed_rate
    assert abs(skill_a.shrunk_rate - skill_a.observed_rate) < abs(skill_b.shrunk_rate - skill_b.observed_rate)
    assert skill_b.shrinkage_weight < 0.25

    # DOCUMENTED, GENUINE FINDING (not a bug in the test -- a real property of
    # simple homoscedastic empirical-Bayes shrinkage): the shrunk estimate is a
    # LINEAR function of the raw observed value at a weight that depends only on
    # n, not on how extreme the observation is. So proportional shrinkage alone
    # narrows the gap a great deal (15x -> ~3.2x here) but does NOT guarantee a
    # single extreme small-sample observation can never still outrank a large,
    # mediocre sample -- that requires an additional minimum-rounds ELIGIBILITY
    # floor (distinct from shrinkage), matching the production concept already
    # present in home_ranking.py (`eligibility: FEATURES_READY` at a minimum
    # sample size) but currently keyed on event count, not round count.
    naive_gap = skill_b.observed_rate / skill_a.observed_rate
    shrunk_gap = skill_b.shrunk_rate / skill_a.shrunk_rate
    assert shrunk_gap < naive_gap, "shrinkage must narrow the gap even if it cannot always close it"
    assert skill_b.shrunk_rate > skill_a.shrunk_rate, (
        "with only n=1 round of evidence for B, this prior's shrinkage narrows but does not "
        "close the gap -- shrinkage is not a substitute for a minimum-rounds eligibility floor"
    )


# --- Case 5: missed-cut vs completed, identical first two rounds ---------

def test_case5_missed_cut_with_identical_early_rate_is_not_penalized_per_round():
    # Both played R1+R2 at the same rate. The completed player continued at the
    # SAME rate for R3+R4 (a fair "identical performance, different survival" setup).
    missed_cut = [EventObservation(total_sg=2.0, rounds=2)]  # +1/round, WD/cut after R2
    completed = [EventObservation(total_sg=4.0, rounds=4)]  # +1/round for all 4

    rate_cut, rate_completed = pooled_per_round_rate(missed_cut), pooled_per_round_rate(completed)
    assert rate_cut == pytest.approx(rate_completed), (
        "identical per-round performance must not be penalized just because one player "
        "did not survive into later rounds"
    )
    naive_cut, naive_completed = naive_event_total_mean(missed_cut), naive_event_total_mean(completed)
    assert naive_cut < naive_completed, "documents the bug: naive method punishes the missed-cut player"


# --- Case 6: WD/DQ 1-round event must not count as equivalent evidence ---

def test_case6_single_round_event_carries_less_weight_than_full_event():
    prior = ShrinkagePrior(population_mean_per_round=0.0, between_player_variance=1.0, within_player_variance=4.0)
    one_round = [EventObservation(total_sg=2.0, rounds=1)]  # WD/DQ after 1 round, +2/round
    four_round = [EventObservation(total_sg=2.0, rounds=4)]  # completed, +0.5/round -- different signal entirely

    skill_1r = estimate_skill("WD", one_round, prior)
    skill_4r = estimate_skill("FULL", four_round, prior)

    # The 1-round sample must be trusted far less (lower shrinkage weight) than a
    # normal 4-round event, precisely because rounds (not events) drive confidence.
    assert skill_1r.shrinkage_weight < skill_4r.shrinkage_weight
    # Known, documented limitation (not fixed by this candidate): round-count
    # weighting alone treats "1 round of noisy data" as just "1/4 the evidence" of
    # a full event, not as a categorically noisier data point. A single round's
    # per-round variance is not directly estimable from one observation, so this
    # candidate cannot yet distinguish "1 noisy round" from "1 representative
    # round" -- flagged here rather than silently assumed fixed.
    assert skill_1r.event_count == 1


# --- Case 7: extreme small sample vs large sample -> regression to mean ---

def test_case7_extreme_small_sample_regresses_toward_population_mean():
    prior = ShrinkagePrior(population_mean_per_round=0.0, between_player_variance=1.0, within_player_variance=4.0)
    small = [EventObservation(total_sg=12.0, rounds=4) for _ in range(2)]  # 2 events, +3/round (very high)
    large = [EventObservation(total_sg=8.0, rounds=4) for _ in range(20)]  # 20 events, +2/round (lower but stable)

    skill_small = estimate_skill("SMALL", small, prior)
    skill_large = estimate_skill("LARGE", large, prior)

    assert skill_small.observed_rate > skill_large.observed_rate
    # regression toward the mean: the small-sample player's shrunk estimate must
    # move substantially closer to the population mean than the large-sample
    # player's does, in relative terms.
    small_shrink_fraction = abs(skill_small.shrunk_rate - skill_small.observed_rate) / abs(skill_small.observed_rate)
    large_shrink_fraction = abs(skill_large.shrunk_rate - skill_large.observed_rate) / abs(skill_large.observed_rate)
    assert small_shrink_fraction > large_shrink_fraction


# --- Case 8: field strength normalization ---------------------------------

def test_case8_field_strength_data_is_not_available_and_not_fabricated():
    """PHASE B Case 8 requires comparing two players with the same per-round
    SG/round but different field strengths. This candidate and the real
    warehouse (historical_sg_warehouse_corrected.json) carry NO field-average
    or field-strength column at all -- SG total/rounds is the only signal
    present. Fabricating a field-strength adjustment here would violate the
    "no invented data" rule, so this test documents the gap rather than
    faking a fix: EventObservation intentionally has no field-strength field."""
    assert not hasattr(EventObservation(total_sg=1.0, rounds=1), "field_strength")
    assert not hasattr(EventObservation(total_sg=1.0, rounds=1), "field_average_sg")


# --- Case 9: volatility must be a separate concept from the point estimate ---

def test_case9_volatility_does_not_move_the_point_estimate():
    prior = ShrinkagePrior(population_mean_per_round=0.0, between_player_variance=1.0, within_player_variance=4.0)
    # Same mean SG/round (+1.0), very different volatility.
    steady = [EventObservation(total_sg=4.0, rounds=4), EventObservation(total_sg=4.0, rounds=4)]
    volatile = [EventObservation(total_sg=12.0, rounds=4), EventObservation(total_sg=-4.0, rounds=4)]

    skill_steady = estimate_skill("STEADY", steady, prior)
    skill_volatile = estimate_skill("VOLATILE", volatile, prior)

    assert skill_steady.observed_rate == pytest.approx(skill_volatile.observed_rate)
    assert skill_steady.shrunk_rate == pytest.approx(skill_volatile.shrunk_rate), (
        "identical mean SG/round must produce an identical skill point estimate "
        "regardless of volatility -- volatility is reported separately, never "
        "subtracted from or added to the point estimate (this was V1's defect #4)"
    )
    assert skill_volatile.volatility > skill_steady.volatility, "volatility must still be measured and exposed"


# --- Shrinkage prior calibration must come from real data, not be invented ---

def test_shrinkage_prior_is_estimated_from_data_not_hardcoded():
    # A tiny synthetic warehouse: enough players/events to exercise the
    # estimator's method-of-moments math end-to-end.
    events_by_player = {
        "p1": [EventObservation(total_sg=4.0, rounds=4), EventObservation(total_sg=3.6, rounds=4), EventObservation(total_sg=4.4, rounds=4)],
        "p2": [EventObservation(total_sg=-2.0, rounds=4), EventObservation(total_sg=-1.6, rounds=4), EventObservation(total_sg=-2.4, rounds=4)],
        "p3": [EventObservation(total_sg=0.0, rounds=4), EventObservation(total_sg=0.4, rounds=4), EventObservation(total_sg=-0.4, rounds=4)],
    }
    prior = estimate_shrinkage_prior_from_warehouse(events_by_player)
    assert prior.between_player_variance > 0
    assert prior.within_player_variance >= 0
    # population mean should sit between the three player means (~1, ~-0.5, ~0)
    assert -0.5 <= prior.population_mean_per_round <= 1.0


def test_shrinkage_prior_requires_at_least_two_eligible_players():
    with pytest.raises(ValueError):
        estimate_shrinkage_prior_from_warehouse({"solo": [EventObservation(total_sg=1.0, rounds=4)] * 3})


# --- Sanity: pooled rate matches simple per-round math for one event -----

def test_pooled_rate_matches_manual_calculation_for_single_event():
    events = [EventObservation(total_sg=6.0, rounds=3)]
    assert pooled_per_round_rate(events) == pytest.approx(2.0)


def test_pooled_rate_is_the_correct_weighted_average_across_unequal_round_events():
    # 1 event of 4 rounds at +1/round (+4 total), 1 event of 1 round at +5/round (+5 total)
    # Weighted pooled rate must be (4+5)/(4+1) = 1.8, NOT the unweighted mean of
    # rates ((1+5)/2 = 3.0) -- the short, noisy event must not dominate equally.
    events = [EventObservation(total_sg=4.0, rounds=4), EventObservation(total_sg=5.0, rounds=1)]
    assert pooled_per_round_rate(events) == pytest.approx(1.8)
    unweighted_mean_of_rates = statistics.fmean(ev.per_round_rate for ev in events)
    assert unweighted_mean_of_rates == pytest.approx(3.0)
    assert pooled_per_round_rate(events) != pytest.approx(unweighted_mean_of_rates)
