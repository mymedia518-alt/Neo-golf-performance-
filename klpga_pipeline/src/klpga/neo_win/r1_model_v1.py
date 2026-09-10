"""NEO_R1_MODEL_V1 -- frozen R1-update model (PRE prior + observed R1
performance -> POST-R1 CUT/TOP20/TOP10/TOP5/WIN).

Provenance: content/website_v2/NEO_R1_MODEL_V1_FREEZE.json (dataset
SHAs, training cutoff, walk-forward validation metrics, selection
rule). This module holds ONLY the frozen numeric artifact of that
research -- the coefficients below are copied byte-for-byte from the
freeze JSON's chain_coefficients / feature_standardization and must
never be refit or hand-edited here; a real refit produces a new
version, never a silent edit of these constants.

MODEL FORM -- nested/conditional chain, never a single flat model:

  P(made_cut)              = sigmoid(a0 + b0*z_pre + c0*z_r1)
  P(top20 | made_cut)      = sigmoid(a1 + b1*z_pre + c1*z_r1)   [fit on made_cut rows only]
  P(top10 | top20)         = sigmoid(a2 + b2*z_pre + c2*z_r1)   [fit on top20 rows only]
  P(top5  | top10)         = sigmoid(a3 + b3*z_pre + c3*z_r1)   [fit on top10 rows only]
  P(win   | top5)          = sigmoid(a4 + b4*z_pre + c4*z_r1)   [fit on top5 rows only]

  P(top20) = P(made_cut) * P(top20|made_cut)
  P(top10) = P(top20) * P(top10|top20)
  P(top5)  = P(top10) * P(top5|top10)
  P(win)   = P(top5)  * P(win|top5)

Each stage's output is itself a probability in [0, 1], so every
product above is also in [0, 1] AND no less than the next stage's
product -- 0 <= win <= top5 <= top10 <= top20 <= cut <= 1 holds by
construction, for every input, with no post-hoc clipping or
renormalization anywhere in this module. This is the "structural
change" the frozen research's coherence requirement asked for, not a
repair applied after the fact.

FEATURES (both z-scored using the FROZEN training-corpus mean/std
below -- never re-standardized per-tournament, which would make the
frozen coefficients meaningless):
  pre_score -- PRE-time prior strength (NEO Ranking V1 composite score,
    frozen_model.NEO_V1_score in NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json).
  r1_z      -- field-relative R1 performance: -(r1_to_par - field_mean)
    / field_stddev, computed ONLY from that tournament's own round-1
    field (historical: NEO_HISTORICAL_R1_FULL_FIELD_V1.json; higher is
    better, since lower to-par is a better score).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

FEATURE_STANDARDIZATION = {
    "pre_score": {"mean": 0.0469895136744602, "std": 0.8694476250189915},
    "r1_z": {"mean": 0.08811534179410624, "std": 0.9544810344206671},
}

CHAIN_ORDER: tuple[str, ...] = ("made_cut", "top20", "top10", "top5", "win")

CHAIN_COEFFICIENTS: dict[str, dict[str, float]] = {
    "made_cut": {"intercept": 0.5774392981724348, "coef_pre_score": 0.48250054273950177, "coef_r1_z": 1.7860838065233837},
    "top20": {"intercept": -1.4274163106098317, "coef_pre_score": 0.7665780609703265, "coef_r1_z": 1.028359438790535},
    "top10": {"intercept": -0.8313328152934988, "coef_pre_score": 0.3839540081075844, "coef_r1_z": 0.7827555492257763},
    "top5": {"intercept": -0.8615642963900275, "coef_pre_score": 0.3569500327967934, "coef_r1_z": 0.6166529428188612},
    "win": {"intercept": -2.3624814258584754, "coef_pre_score": 0.17852802556084985, "coef_r1_z": 0.4897379112975217},
}


def _standardize(feature: str, raw_value: float) -> float:
    params = FEATURE_STANDARDIZATION[feature]
    return (raw_value - params["mean"]) / params["std"]


def _sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _stage_probability(label: str, pre_score: float, r1_z: float) -> float:
    coef = CHAIN_COEFFICIENTS[label]
    z_pre = _standardize("pre_score", pre_score)
    z_r1 = _standardize("r1_z", r1_z)
    z = coef["intercept"] + coef["coef_pre_score"] * z_pre + coef["coef_r1_z"] * z_r1
    return _sigmoid(z)


@dataclass(frozen=True)
class R1TierProbabilities:
    cut: float
    top20: float
    top10: float
    top5: float
    win: float

    def is_coherent(self) -> bool:
        vals = (self.win, self.top5, self.top10, self.top20, self.cut)
        return all(0.0 <= v <= 1.0 for v in vals) and list(vals) == sorted(vals)


def predict_r1_tiers(pre_score: float, r1_z: float) -> R1TierProbabilities:
    """Apply the frozen NEO_R1_MODEL_V1 chain to one player's PRE-time
    prior strength and observed R1 performance. Structurally coherent
    for any real-valued input -- see module docstring."""
    p_cut = _stage_probability("made_cut", pre_score, r1_z)
    p_top20 = p_cut * _stage_probability("top20", pre_score, r1_z)
    p_top10 = p_top20 * _stage_probability("top10", pre_score, r1_z)
    p_top5 = p_top10 * _stage_probability("top5", pre_score, r1_z)
    p_win = p_top5 * _stage_probability("win", pre_score, r1_z)
    return R1TierProbabilities(cut=p_cut, top20=p_top20, top10=p_top10, top5=p_top5, win=p_win)


def field_relative_r1_z(r1_to_par: float, field_mean: float, field_stddev: float) -> float:
    """Leakage-safe R1 normalization -- uses only that round's own
    field values, never a later round's. Higher = better (negated
    because a lower to-par score is the better outcome)."""
    std = field_stddev if field_stddev else 1.0
    return -(r1_to_par - field_mean) / std
