#!/usr/bin/env python3
"""
single_criterion.py -- the one implementation of the single-criterion
diagnostic, shared by compute_dispersion_diagnostics.py (the paper's
single-criterion recovery table) and competitive_baselines.py.

The diagnostic ranks a scenario's alternatives by ONE of the reference's own
criterion scores and compares that with the reference MAVT ranking. Single
criteria tie often (Appliance energy cost, HVAC practicality), and any fixed
tie rule makes the statistic depend on the order the alternatives are listed.
Both statistics here are instead the expectation under a uniform random
tie-break, which does not depend on list order:

  top1_credit     1/k when the reference winner is one of the k alternatives
                  tied for the best value of the criterion, else 0 (so an
                  untied correct argmax scores 1 and a three-way tie 1/3).
  expected_tau    Kendall's tau with every pair tied on the criterion counted
                  as neither concordant nor discordant: (C - D) / n_pairs. The
                  reference ranks are strict, so this equals the mean tau over
                  all tie-break orders.

Values are compared after rounding to MAVT_ROUND_DECIMALS, the same rule the
MAVT ranking uses, so floating-point noise cannot split a tie.
"""

import math
from typing import Sequence

from llm_mcda.common.sentinel_utils import MAVT_ROUND_DECIMALS


def _clean(values: Sequence) -> list:
    return [round(float(v), MAVT_ROUND_DECIMALS) for v in values]


def top1_credit(ref_ranks: Sequence, crit_values: Sequence) -> float:
    """Expected Top-1 of 'pick the argmax of this criterion' under a uniform
    random tie-break: 1/k if the reference rank-1 alternative is among the k
    alternatives tied for the maximum, else 0."""
    ranks = [float(r) for r in ref_ranks]
    vals = _clean(crit_values)
    if not ranks or len(ranks) != len(vals):
        raise ValueError("ref_ranks and crit_values must be non-empty and the same length")
    winner = min(range(len(ranks)), key=lambda i: ranks[i])
    best = max(vals)
    tied = [i for i, v in enumerate(vals) if v == best]
    return 1.0 / len(tied) if winner in tied else 0.0


def expected_tau(ref_ranks: Sequence, crit_values: Sequence) -> float:
    """Mean Kendall tau over all tie-break orders of the criterion ranking.
    A reference pair that is itself tied contributes 0 as well."""
    ranks = [float(r) for r in ref_ranks]
    vals = _clean(crit_values)
    n = len(ranks)
    if n < 2 or n != len(vals):
        return math.nan
    score = 0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            pairs += 1
            ref_dir = (ranks[j] > ranks[i]) - (ranks[j] < ranks[i])   # +1: i better
            crit_dir = (vals[i] > vals[j]) - (vals[i] < vals[j])      # +1: i better
            score += ref_dir * crit_dir
    return score / pairs
