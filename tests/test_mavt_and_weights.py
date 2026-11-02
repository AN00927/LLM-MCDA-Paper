"""Unit tests for the fixed criterion weights, MAVT aggregation and rank metrics."""
import math

import numpy as np
import pandas as pd
import pytest

from common.model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
from common.sentinel_utils import apply_mavt_ranking
from scripts.analysis.evaluate_architecture_metrics import _scenario_ranking_values


def test_weights_are_the_published_35_30_20_15():
    assert CRITERION_WEIGHTS == {
        "environmental": 0.35,
        "energy_cost": 0.30,
        "comfort": 0.20,
        "practicality": 0.15,
    }
    assert math.isclose(sum(CRITERION_WEIGHTS.values()), 1.0, abs_tol=1e-12)


def test_tie_break_priority_covers_every_criterion_once():
    assert sorted(TIE_BREAK_PRIORITY) == sorted(CRITERION_WEIGHTS)


def _alt(name, env, cost, comfort, practicality):
    return {
        "alternative": name,
        "environmental": env,
        "energy_cost": cost,
        "comfort": comfort,
        "practicality": practicality,
    }


def test_apply_mavt_ranking_matches_weighted_sum_and_orders_best_first():
    alts = [
        _alt("a", 0.2, 0.2, 0.2, 0.2),
        _alt("b", 1.0, 1.0, 1.0, 1.0),
        _alt("c", 0.5, 0.5, 0.5, 0.5),
    ]
    out = apply_mavt_ranking(alts)
    assert out["ranks"] == [3, 1, 2]
    assert out["ranked_alternatives"] == ["b", "c", "a"]
    assert out["weighted_scores"] == pytest.approx([0.2, 1.0, 0.5])


def test_apply_mavt_ranking_uses_exact_weights():
    # Environmental only: 0.35. Practicality only: 0.15.
    out = apply_mavt_ranking([_alt("env", 1, 0, 0, 0), _alt("prac", 0, 0, 0, 1)])
    assert out["weighted_scores"] == pytest.approx([0.35, 0.15])
    assert out["ranks"] == [1, 2]


def test_apply_mavt_ranking_assigns_distinct_ranks_to_tied_aggregates():
    out = apply_mavt_ranking([_alt("x", 0.5, 0.5, 0.5, 0.5), _alt("y", 0.5, 0.5, 0.5, 0.5)])
    assert sorted(out["ranks"]) == [1, 2]


def _scenario(gt_ranks, arch_ranks):
    names = list("abc")[: len(gt_ranks)]
    return pd.DataFrame(
        {"gt_rank": gt_ranks, "arch_rank": arch_ranks, "norm_alternative": names}
    )


def test_kendall_tau_identical_rankings_is_one():
    vals = _scenario_ranking_values(_scenario([1, 2, 3], [1, 2, 3]))
    assert vals["kendall_tau"] == pytest.approx(1.0)
    assert vals["top1"] == 1.0 and vals["top2"] == 1.0


def test_kendall_tau_reversed_rankings_is_minus_one():
    vals = _scenario_ranking_values(_scenario([1, 2, 3], [3, 2, 1]))
    assert vals["kendall_tau"] == pytest.approx(-1.0)
    assert vals["top1"] == 0.0


def test_top2_credit_when_reference_winner_is_architecture_runner_up():
    vals = _scenario_ranking_values(_scenario([1, 2, 3], [2, 1, 3]))
    assert vals["top1"] == 0.0
    assert vals["top2"] == 1.0
    assert 0.0 < vals["kendall_tau"] < 1.0


def test_single_alternative_has_no_ranking():
    assert _scenario_ranking_values(_scenario([1], [1])) is None


def test_chance_level_tau_is_zero_in_expectation():
    from itertools import permutations

    taus = [
        _scenario_ranking_values(_scenario([1, 2, 3], list(p)))["kendall_tau"]
        for p in permutations([1, 2, 3])
    ]
    assert np.mean(taus) == pytest.approx(0.0, abs=1e-12)
