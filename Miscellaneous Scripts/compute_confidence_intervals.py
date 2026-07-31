#!/usr/bin/env python3
"""
compute_confidence_intervals.py - Bootstrap confidence intervals for LLM-MCDA benchmark metrics.

Computes 95% bias-corrected and accelerated (BCa) bootstrap confidence intervals
for five primary metrics (kendall_tau, top1_accuracy, overall_mae, overall_rmse,
overall_rmse_mae_ratio) across three LLM-MCDA architectures and four models,
plus pooled (all-models) estimates per architecture.

Input:  paper/per_run_metrics/per_run_metrics_all.csv
Output: paper/per_run_metrics/bootstrap_confidence_intervals.xlsx

Methodology:
  For each (metric, architecture, model) triplet and each (metric, architecture)
  pooled combination, the script:
    1. Extracts the per-run metric values (5 runs per model, 20 pooled).
    2. Draws 10,000 bootstrap resamples of those values with replacement.
    3. Computes the mean of each resample.
    4. Uses the BCa method to construct a 95% confidence interval around the
       point estimate (the mean of the original values).

  The BCa interval adjusts for both bias (deviation of the point estimate from
  the bootstrap distribution median) and skewness (asymmetry of the bootstrap
  distribution), providing better coverage than a naive percentile interval,
  especially for small sample sizes (n=5 or n=20).

Interpretation:
  A 95% BCa interval [L, U] means that, under repeated sampling, the true
  population mean of the metric would fall within [L, U] approximately 95%
  of the time.  Non-overlapping intervals between two architectures (or
  models) suggest a statistically meaningful difference at roughly the
  alpha=0.05 level, though formal hypothesis testing (e.g., permutation
  tests) would be needed for rigorous comparison.

Usage:
  python compute_confidence_intervals.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_CSV = (
    PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
)
OUTPUT_XLSX = (
    PROJECT_ROOT
    / "paper"
    / "per_run_metrics"
    / "bootstrap_confidence_intervals.xlsx"
)

N_BOOTSTRAP = 10000
RANDOM_SEED = 42
CONFIDENCE_LEVEL = 0.95
ALPHA = 1.0 - CONFIDENCE_LEVEL  # 0.05

PRIMARY_METRICS = [
    "kendall_tau",
    "top1_accuracy",
    "overall_mae",
    "overall_rmse",
    "overall_rmse_mae_ratio",
]

ARCHITECTURES = [
    "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring",
]

MODELS = ["deepseek", "gemini", "gptoss", "qwen"]

POOLED_MODEL_LABEL = "All Models"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data(csv_path):
    """Load the per-run metrics CSV and return only Overall rows with valid metrics.

    Why: The bootstrap operates on the per-run aggregated metrics.  Each row
    represents one independent run of an architecture on one model, with
    metrics already computed across all ~195 scenarios.  We keep only the
    "Overall" decision type because per-type breakdowns are not the focus of
    this script and would require separate treatment of varying scenario
    counts.

    Returns:
        pd.DataFrame with columns: architecture, model, run, plus all metric
        columns.  Rows where any primary metric is NaN are flagged but not
        dropped globally -- NaN handling is deferred to the bootstrap step so
        that different metrics can have different effective sample sizes.
    """
    df = pd.read_csv(csv_path)
    overall = df[df["decision_type"] == "Overall"].copy()

    n_rows = len(overall)
    n_arch = overall["architecture"].nunique()
    n_models = overall["model"].nunique()
    n_runs = overall.groupby(["architecture", "model"])["run"].nunique()

    print(f"Loaded {n_rows} Overall rows ({n_arch} architectures x "
          f"{n_models} models x {n_runs.iloc[0]} runs each)")

    for m in PRIMARY_METRICS:
        n_nan = overall[m].isna().sum()
        if n_nan > 0:
            print(f"  WARNING: {m} has {n_nan} NaN value(s) out of {n_rows}")

    return overall


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def bootstrap_bca_ci(values, n_resamples=N_BOOTSTRAP, alpha=ALPHA,
                     random_state=RANDOM_SEED):
    """Compute a 95% BCa bootstrap confidence interval for the mean.

    Method:
      Uses scipy.stats.bootstrap with method='BCa' (bias-corrected and
      accelerated).  BCa adjusts the naive percentile interval by two
      correction factors:

        - Bias correction (z0): accounts for the bootstrap distribution
          median differing from the point estimate.
        - Acceleration (a): accounts for skewness in the sampling
          distribution of the statistic.

      The adjusted percentiles are:

        alpha_1 = Phi(z0 + (z0 + z_alpha) / (1 - a * (z0 + z_alpha)))
        alpha_2 = Phi(z0 + (z0 + z_{1-alpha}) / (1 - a * (z0 + z_{1-alpha})))

      where Phi is the standard normal CDF and z_x is the x-th quantile
      of the standard normal.

      For small samples (n=5 per model), BCa is critical because the
      bootstrap distribution of the mean can be noticeably skewed or
      biased, especially for bounded metrics like top1_accuracy [0, 1]
      or metrics with heavy tails.

    Why this approach:
      - Non-parametric: makes no distributional assumptions about the
        underlying metric distribution.
      - BCa method provides second-order accuracy (error O(n^{-1})
        vs O(n^{-1/2}) for percentile intervals).
      - With n_resamples=10000, the Monte Carlo error of the CI bounds
        is approximately +/- 0.003 for a 95% interval, which is small
        relative to the metric scales.

    Args:
        values: 1-D array-like of numeric metric values (one per run).
        n_resamples: Number of bootstrap resamples (default 10000).
        alpha: Significance level for the CI (default 0.05 for 95% CI).
        random_state: Seed or RandomState for reproducibility.

    Returns:
        dict with keys 'point_estimate', 'ci_lower', 'ci_upper'.
        Returns NaN for all three if fewer than 2 non-NaN values exist
        (BCa requires at least 2 observations to estimate acceleration).
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]

    if len(arr) < 2:
        return {"point_estimate": np.nan, "ci_lower": np.nan, "ci_upper": np.nan}

    point_estimate = float(np.mean(arr))

    result = stats.bootstrap(
        (arr,),
        statistic=np.mean,
        n_resamples=n_resamples,
        method="BCa",
        confidence_level=CONFIDENCE_LEVEL,
        random_state=random_state,
    )

    return {
        "point_estimate": round(point_estimate, 4),
        "ci_lower": round(float(result.confidence_interval.low), 4),
        "ci_upper": round(float(result.confidence_interval.high), 4),
    }


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------


def compute_all_confidence_intervals(df):
    """Compute bootstrap CIs for every (metric, architecture, model) cell
    plus pooled (all models) rows per architecture.

    For each cell:
      1. Extract the per-run metric values for that (arch, model) pair.
      2. Drop NaN values (a run may have a NaN for a particular metric if
         scenario matching failed for that run).
      3. Call bootstrap_bca_ci to get the point estimate and 95% BCa CI.

    Pooled rows combine all 20 runs (5 per model x 4 models) for a given
    architecture.  This gives a more stable estimate of the architecture's
    overall performance, at the cost of averaging across model-specific
    variation.

    Returns:
        list of dicts, each with keys: Metric, Architecture, Model,
        Point Estimate, 95% CI Lower, 95% CI Upper.
    """
    results = []

    for metric in PRIMARY_METRICS:
        for arch in ARCHITECTURES:
            # --- Per-model rows ---
            for model in MODELS:
                mask = (df["architecture"] == arch) & (df["model"] == model)
                values = df.loc[mask, metric].dropna().values
                ci = bootstrap_bca_ci(values)
                results.append({
                    "Metric": metric,
                    "Architecture": arch,
                    "Model": model,
                    "Point Estimate": ci["point_estimate"],
                    "95% CI Lower": ci["ci_lower"],
                    "95% CI Upper": ci["ci_upper"],
                })

            # --- Pooled row (all models) ---
            mask = df["architecture"] == arch
            values = df.loc[mask, metric].dropna().values
            ci = bootstrap_bca_ci(values)
            results.append({
                "Metric": metric,
                "Architecture": arch,
                "Model": POOLED_MODEL_LABEL,
                "Point Estimate": ci["point_estimate"],
                "95% CI Lower": ci["ci_lower"],
                "95% CI Upper": ci["ci_upper"],
            })

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_table(results):
    """Print a formatted ASCII table of bootstrap CI results to stdout.

    Groups rows by Metric, then by Architecture, with pooled rows at the
    end of each architecture block.  Column widths are fixed to fit in a
    standard 120-column terminal without unicode characters (Windows
    cp1252 compatibility).
    """
    col_w = {
        "Metric": 26,
        "Architecture": 42,
        "Model": 20,
        "Point Estimate": 10,
        "95% CI Lower": 10,
        "95% CI Upper": 10,
    }

    hdr = (
        f"{'Metric':<{col_w['Metric']}}"
        f"{'Architecture':<{col_w['Architecture']}}"
        f"{'Model':<{col_w['Model']}}"
        f"{'Estimate':>{col_w['Point Estimate']}}"
        f"{'CI Lower':>{col_w['95% CI Lower']}}"
        f"{'CI Upper':>{col_w['95% CI Upper']}}"
    )

    total_w = sum(col_w.values())
    sep = "-" * total_w

    print()
    print("=" * total_w)
    print(f"  95% BCa BOOTSTRAP CONFIDENCE INTERVALS ({N_BOOTSTRAP} resamples)")
    print(f"  Random seed: {RANDOM_SEED}")
    print("=" * total_w)
    print()
    print(hdr)
    print(sep)

    prev_metric = None
    for r in results:
        if prev_metric is not None and r["Metric"] != prev_metric:
            print()  # blank line between metrics
        prev_metric = r["Metric"]

        est = "N/A" if np.isnan(r["Point Estimate"]) else f"{r['Point Estimate']:.4f}"
        lo = "N/A" if np.isnan(r["95% CI Lower"]) else f"{r['95% CI Lower']:.4f}"
        hi = "N/A" if np.isnan(r["95% CI Upper"]) else f"{r['95% CI Upper']:.4f}"

        print(
            f"{r['Metric']:<{col_w['Metric']}}"
            f"{r['Architecture']:<{col_w['Architecture']}}"
            f"{r['Model']:<{col_w['Model']}}"
            f"{est:>{col_w['Point Estimate']}}"
            f"{lo:>{col_w['95% CI Lower']}}"
            f"{hi:>{col_w['95% CI Upper']}}"
        )

    print(sep)
    print()


def save_xlsx(results, output_path):
    """Write the results list to an Excel file.

    Uses openpyxl via pandas.  A single sheet named 'Bootstrap CI' contains
    all rows: per-model cells first, then pooled rows, organized by metric.
    """
    out_df = pd.DataFrame(results)

    out_df = out_df[[
        "Metric", "Architecture", "Model",
        "Point Estimate", "95% CI Lower", "95% CI Upper",
    ]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_excel(str(output_path), index=False, sheet_name="Bootstrap CI")
    print(f"Results written to: {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Load data, compute bootstrap CIs, print table, write xlsx."""
    print("Bootstrap Confidence Interval Computation")
    print(f"  Input:  {INPUT_CSV}")
    print(f"  Output: {OUTPUT_XLSX}")
    print(f"  Resamples: {N_BOOTSTRAP}")
    print(f"  Seed: {RANDOM_SEED}")
    print()

    df = load_data(INPUT_CSV)

    print(f"\nComputing BCa bootstrap CIs for {len(PRIMARY_METRICS)} metrics "
          f"x {len(ARCHITECTURES)} architectures "
          f"x ({len(MODELS)} models + pooled)...")
    print(f"  Total cells: "
          f"{len(PRIMARY_METRICS) * len(ARCHITECTURES) * (len(MODELS) + 1)}")
    print()

    results = compute_all_confidence_intervals(df)

    print_table(results)
    save_xlsx(results, OUTPUT_XLSX)

    print("Done.")


if __name__ == "__main__":
    main()
