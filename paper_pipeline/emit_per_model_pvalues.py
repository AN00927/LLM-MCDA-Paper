#!/usr/bin/env python3
"""
emit_per_model_pvalues.py -- per-model Wilcoxon p-values for the adjacent
architecture comparisons, so the manuscript can report four model-specific
results instead of one Stouffer-combined omnibus p.

Why this exists
---------------
`significance_testing.stouffer_combine` treats the four models as independent
tests. They are not: all four score the same 195 Test scenarios against the
same physics ground truth, so their per-scenario differences are positively
dependent and the combined p-value is anti-conservative. Rather than change
the combination rule (which would require a dependence estimate the data does
not directly supply), this script emits the underlying per-model tests at full
precision, Holm-corrected, so the claim can be made per model.

Two Holm corrections are reported for every test:
  p_holm_subset  -- Holm over the 24 tests in THIS file
                    (2 adjacent pairs x 3 headline metrics x 4 models)
  p_holm_family  -- Holm over the full 56-test family that
                    significance_testing.run_wilcoxon corrects across
                    (2 pairs x 7 metrics x 4 models)

`p_value` is written unrounded, unlike the 6-decimal rounding in
significance_tests.xlsx, so genuinely tiny p-values are not displayed as 0.

No API calls; reads only per-run xlsx already on disk.

Usage:
    python paper_pipeline/emit_per_model_pvalues.py
"""

import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_MISC = PROJECT_ROOT / "Miscellaneous Scripts"
if str(_MISC) not in sys.path:
    sys.path.insert(0, str(_MISC))

_SIG_PATH = _MISC / "validation" / "significance_testing.py"
_spec = spec_from_file_location("significance_testing", _SIG_PATH)
_sig = module_from_spec(_spec)
_spec.loader.exec_module(_sig)

OUT = PROJECT_ROOT / "paper" / "per_model_pvalues.csv"

HEADLINE_METRICS = ["kendall_tau", "overall_mae", "top1_accuracy"]
METRIC_LABEL = {"kendall_tau": "tau", "overall_mae": "MAE", "top1_accuracy": "Top-1"}


def holm(pvals):
    """Holm-Bonferroni adjusted p-values, order preserved, NaNs passed through."""
    p = np.asarray(pvals, dtype=float)
    out = np.full(p.shape, np.nan)
    idx = np.where(np.isfinite(p))[0]
    if len(idx) == 0:
        return out
    order = idx[np.argsort(p[idx], kind="mergesort")]
    k = len(order)
    running = 0.0
    for i, j in enumerate(order):
        adj = min(p[j] * (k - i), 1.0)
        running = max(running, adj)   # enforce monotonicity
        out[j] = running
    return out


def main():
    warnings.filterwarnings("ignore")
    print("[1] Computing per-scenario metrics from raw run files ...")
    per_scenario = _sig.compute_per_scenario_metrics_from_raw()
    if per_scenario.empty:
        print("ERROR: no per-scenario metrics computed")
        return

    models = sorted(per_scenario["model"].unique())
    print(f"    models: {models}")

    # Full 56-test family, matching significance_testing.run_wilcoxon's scope.
    family = []
    for arch_a, arch_b in _sig.PAIRS:
        for metric in _sig.METRICS:
            for model in models:
                # wilcoxon_pair_model now returns a fourth value, n_nonzero: the
                # number of pairs the signed-rank statistic was actually computed
                # on, i.e. n_scenarios minus the exact-zero (tied) pairs. Carrying
                # it makes tie saturation visible instead of silent -- several
                # comparisons here report significance on a median paired
                # difference of exactly 0.0000.
                z, p, n, n_nonzero = _sig.wilcoxon_pair_model(
                    per_scenario, arch_a, arch_b, metric, model)
                family.append({
                    "comparison": f"{_sig.ARCH_SHORT[arch_a]} vs {_sig.ARCH_SHORT[arch_b]}",
                    "metric": metric,
                    "model": model,
                    "Z": z,
                    "p_value": p,
                    "n_scenarios": n,
                    "n_nonzero_pairs": n_nonzero,
                    "n_tied_pairs": (n - n_nonzero) if n else 0,
                })
    fam = pd.DataFrame(family)
    fam["p_holm_family"] = holm(fam["p_value"].values)

    sub = fam[fam["metric"].isin(HEADLINE_METRICS)].copy().reset_index(drop=True)
    sub["p_holm_subset"] = holm(sub["p_value"].values)

    # Direction: sign of the median paired difference (arch_a - arch_b).
    directions = []
    for _, r in sub.iterrows():
        arch_a, arch_b = next(
            (a, b) for a, b in _sig.PAIRS
            if f"{_sig.ARCH_SHORT[a]} vs {_sig.ARCH_SHORT[b]}" == r["comparison"])
        a = per_scenario[(per_scenario["architecture"] == arch_a)
                         & (per_scenario["model"] == r["model"])
                         ].set_index("scenario_id")[r["metric"]].dropna()
        b = per_scenario[(per_scenario["architecture"] == arch_b)
                         & (per_scenario["model"] == r["model"])
                         ].set_index("scenario_id")[r["metric"]].dropna()
        common = a.index.intersection(b.index)
        directions.append(np.median(a.loc[common].values - b.loc[common].values))
    sub["median_paired_diff"] = directions

    sub["metric_label"] = sub["metric"].map(METRIC_LABEL)
    sub["significant_holm_subset"] = sub["p_holm_subset"] < 0.05
    sub["significant_holm_family"] = sub["p_holm_family"] < 0.05

    cols = ["comparison", "metric", "metric_label", "model", "n_scenarios",
            "n_nonzero_pairs", "n_tied_pairs",
            "Z", "median_paired_diff", "p_value", "p_holm_subset",
            "p_holm_family", "significant_holm_subset", "significant_holm_family"]
    sub = sub[cols].sort_values(["comparison", "metric", "model"],
                                kind="mergesort").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(OUT, index=False)
    print(f"\n[2] Wrote {OUT} ({len(sub)} rows)")

    show = sub.copy()
    for c in ["p_value", "p_holm_subset", "p_holm_family"]:
        show[c] = show[c].apply(lambda v: f"{v:.3e}" if pd.notna(v) else "")
    show["Z"] = show["Z"].round(3)
    show["median_paired_diff"] = show["median_paired_diff"].round(4)
    print(show[["comparison", "metric_label", "model", "n_scenarios", "Z",
                "median_paired_diff", "p_value", "p_holm_subset",
                "p_holm_family", "significant_holm_subset"]].to_string(index=False))

    n_sig = int(sub["significant_holm_subset"].sum())
    print(f"\nSignificant at Holm-corrected alpha=0.05 (subset family of "
          f"{len(sub)}): {n_sig}/{len(sub)}")


if __name__ == "__main__":
    main()
