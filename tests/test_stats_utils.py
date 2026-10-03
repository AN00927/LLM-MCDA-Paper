"""holm_adjust must reproduce the two pre-refactor Holm implementations exactly."""
import numpy as np
import pandas as pd

from llm_mcda.common.stats_utils import holm_adjust


def _reference_emit(pvals):
    p = np.asarray(pvals, dtype=float)
    out = np.full(p.shape, np.nan)
    idx = np.where(np.isfinite(p))[0]
    if len(idx) == 0:
        return out
    order = idx[np.argsort(p[idx], kind="mergesort")]
    k = len(order)
    running = 0.0
    for i, j in enumerate(order):
        running = max(running, min(p[j] * (k - i), 1.0))
        out[j] = running
    return out


def _reference_significance_testing(pvals):
    holm_df = pd.DataFrame({"p_value": np.asarray(pvals, dtype=float)})
    k = int(holm_df["p_value"].notna().sum())
    holm_df["p_holm"] = np.nan
    ordered = holm_df.loc[holm_df["p_value"].notna(), "p_value"].sort_values(
        kind="mergesort")
    running_max = 0.0
    for i, (idx, p_raw) in enumerate(ordered.items()):
        running_max = max(running_max, min(p_raw * (k - i), 1.0))
        holm_df.at[idx, "p_holm"] = running_max
    return holm_df["p_holm"].values


def test_holm_adjust_matches_both_former_implementations():
    rng = np.random.default_rng(0)
    for _ in range(300):
        n = int(rng.integers(0, 60))
        p = rng.random(n) ** rng.integers(1, 12)
        if n:
            p[rng.random(n) < 0.15] = np.nan
            tie = rng.random(n) < 0.2
            p[tie] = np.round(p[tie], 2)
        got = holm_adjust(p)
        np.testing.assert_array_equal(got, _reference_emit(p))
        np.testing.assert_array_equal(got, _reference_significance_testing(p))


def test_holm_adjust_known_values_and_monotone():
    got = holm_adjust([0.01, 0.04, 0.03, np.nan])
    np.testing.assert_allclose(got[:3], [0.03, 0.06, 0.06])
    assert np.isnan(got[3])
