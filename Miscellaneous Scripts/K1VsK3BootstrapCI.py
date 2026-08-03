#!/usr/bin/env python3
"""K1VsK3BootstrapCI.py - Percentile bootstrap CI on the k=1 vs k=3 retrieval difference.

Task C4(a): quantify the power actually available behind the paper's claim that
retrieval counts k=1 and k=3 produced "statistically indistinguishable" ranking
accuracy. This script computes a percentile bootstrap 95% CI on the paired
per-scenario difference in Kendall's tau:

    d_i = tau_i(retrieval_k1) - tau_i(control_k3)

for each model and pooled across models, using the same bootstrap conventions
as the prompt-ablation machinery (bootstrap_ci_per_config in
Miscellaneous Scripts/RunRAGAblations.py):

    - n_bootstrap = 10,000 resamples
    - seed = 42 (np.random.default_rng(42))
    - resampling unit = the scenario-level metric value (here: the paired
      per-scenario difference)
    - statistic = mean of the resampled differences
    - CI = percentile method, 2.5 / 97.5 percentiles

A BCa interval (via scipy.stats.bootstrap, the method used by
Miscellaneous Scripts/compute_confidence_intervals.py for the per-run metrics)
is reported as a cross-check. The point estimate is the observed mean
difference, which is the quantity the CI describes.

Input : Analysis/RAG_Ablation/rag_ablation_results.xlsx (scenario-level rows)
Output: Analysis/RAG_Ablation/k1_vs_k3_bootstrap_ci.xlsx (new file)

Zero API calls. Plain ASCII output only.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_XLSX = PROJECT_ROOT / "Analysis" / "RAG_Ablation" / "rag_ablation_results.xlsx"
OUTPUT_XLSX = PROJECT_ROOT / "Analysis" / "RAG_Ablation" / "k1_vs_k3_bootstrap_ci.xlsx"

N_BOOTSTRAP = 10000
RANDOM_SEED = 42
CONFIDENCE_LEVEL = 0.95
ALPHA = 1.0 - CONFIDENCE_LEVEL

CONFIG_K1 = "retrieval_k1"
CONFIG_K3 = "control_k3"
MODELS = ["deepseek", "gptoss", "qwen"]
POOLED_LABEL = "All Models"


def load_paired_differences() -> pd.DataFrame:
    """Return one row per (model, source_scenario_id) with the k1-k3 tau difference.

    Scenario-level rows are the same deduplication the ablation itself uses
    (scenario_level_df in RunRAGAblations.py): one row per
    (model_key, ablation_id, ablation_label, decision_type, source_scenario_id).
    Kendall's tau is NaN for scenarios with no valid/varying predictions; a
    paired difference requires valid tau in BOTH configurations, so rows with
    NaN in either config are dropped.
    """
    df = pd.read_excel(INPUT_XLSX)
    scenario_df = df.drop_duplicates(
        ["model_key", "ablation_id", "ablation_label", "decision_type", "source_scenario_id"]
    ).copy()
    scenario_df["kendall_tau"] = pd.to_numeric(scenario_df["kendall_tau"], errors="coerce")

    rows = []
    for model in MODELS:
        mask = scenario_df["model_key"] == model
        pivot = scenario_df.loc[mask].pivot_table(
            index=["source_scenario_id", "decision_type"],
            columns="ablation_id",
            values="kendall_tau",
            aggfunc="first",
        )
        pivot = pivot.dropna(subset=[CONFIG_K1, CONFIG_K3])
        diffs = pivot[CONFIG_K1] - pivot[CONFIG_K3]
        for (scenario_id, decision_type), d in diffs.items():
            rows.append({
                "model": model,
                "source_scenario_id": scenario_id,
                "decision_type": decision_type,
                "tau_k1": float(pivot.loc[(scenario_id, decision_type), CONFIG_K1]),
                "tau_k3": float(pivot.loc[(scenario_id, decision_type), CONFIG_K3]),
                "diff": float(d),
            })
    return pd.DataFrame(rows)


def percentile_ci(diffs: np.ndarray, n_bootstrap: int = N_BOOTSTRAP, seed: int = RANDOM_SEED):
    """Percentile bootstrap CI for the mean of paired differences.

    Mirrors bootstrap_ci_per_config in RunRAGAblations.py exactly:
    default_rng(seed), rng.choice(values, size=len(values), replace=True),
    mean of each resample, np.percentile(..., 2.5 / 97.5).
    """
    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_bootstrap)
    for b in range(n_bootstrap):
        sample = rng.choice(diffs, size=len(diffs), replace=True)
        boot_means[b] = np.mean(sample)
    lo = float(np.percentile(boot_means, 2.5))
    hi = float(np.percentile(boot_means, 97.5))
    return lo, hi


def bca_ci(diffs: np.ndarray, n_bootstrap: int = N_BOOTSTRAP, seed: int = RANDOM_SEED):
    """BCa CI cross-check, matching compute_confidence_intervals.py."""
    result = stats.bootstrap(
        (diffs,),
        statistic=np.mean,
        n_resamples=n_bootstrap,
        method="BCa",
        confidence_level=CONFIDENCE_LEVEL,
        random_state=seed,
    )
    return float(result.confidence_interval.low), float(result.confidence_interval.high)


def main():
    print("K1 vs K3 retrieval bootstrap CI (task C4a)")
    print(f"  Input : {INPUT_XLSX}")
    print(f"  Output: {OUTPUT_XLSX}")
    print(f"  Resamples: {N_BOOTSTRAP}, seed: {RANDOM_SEED}, "
          f"unit: paired per-scenario diff, method: percentile (BCa cross-check)")
    print()

    diffs_df = load_paired_differences()
    if diffs_df.empty:
        raise SystemExit("No paired k1/k3 differences found")

    rows = []
    groups = [(m, g) for m, g in diffs_df.groupby("model")] + [
        (POOLED_LABEL, diffs_df)
    ]
    for label, group in groups:
        d = group["diff"].values.astype(float)
        mean_k1 = float(group["tau_k1"].mean())
        mean_k3 = float(group["tau_k3"].mean())
        point = float(np.mean(d))
        p_lo, p_hi = percentile_ci(d)
        b_lo, b_hi = bca_ci(d)
        rows.append({
            "Model": label,
            "n_pairs": int(len(d)),
            "mean_tau_k1": round(mean_k1, 6),
            "mean_tau_k3": round(mean_k3, 6),
            "mean_diff_k1_minus_k3": round(point, 6),
            "CI95_lower_percentile": round(p_lo, 6),
            "CI95_upper_percentile": round(p_hi, 6),
            "CI95_lower_bca": round(b_lo, 6),
            "CI95_upper_bca": round(b_hi, 6),
            "CI95_contains_zero": bool(p_lo <= 0.0 <= p_hi),
        })

    out = pd.DataFrame(rows)
    out.to_excel(OUTPUT_XLSX, index=False, sheet_name="k1_vs_k3")

    print("Model      n  mean_tau_k1  mean_tau_k3  mean_diff  CI95 percentile    CI95 bca        contains_zero")
    print("-" * 100)
    for _, r in out.iterrows():
        print(
            f"{r['Model']:<10} {r['n_pairs']:>3}  {r['mean_tau_k1']:>10.4f}  "
            f"{r['mean_tau_k3']:>10.4f}  {r['mean_diff_k1_minus_k3']:>9.4f}  "
            f"[{r['CI95_lower_percentile']:>7.4f}, {r['CI95_upper_percentile']:>7.4f}]  "
            f"[{r['CI95_lower_bca']:>7.4f}, {r['CI95_upper_bca']:>7.4f}]  "
            f"{str(r['CI95_contains_zero'])}"
        )
    print()
    print(f"Wrote {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
