"""
SensitivityAnalysis.py - Sensitivity analysis for MCDA architecture comparison

Tests whether the architecture performance ordering (Hybrid > RAG > Pure on
Kendall tau) holds when MAVT criterion weights are perturbed. For each weight
scenario, GT and architecture rankings are recomputed from raw criterion scores
using the perturbed weights, so the "correct" answer shifts with the weights.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MISC_DIR = PROJECT_ROOT / "Miscellaneous Files"

for p in (str(PROJECT_ROOT), str(MISC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from model_config import CRITERION_WEIGHTS, MODEL_KEY, get_output_folder
from CalculateMetrics import (
    CONFIG,
    CRITERIA,
    build_gt_lookup,
    filter_failed_scenarios,
    load_architecture,
    load_ground_truth,
    match_scenarios,
    compute_ranking_metrics,
)

OUTPUT_DIR = PROJECT_ROOT / get_output_folder(MODEL_KEY)

def generate_weight_scenarios(baseline: dict[str, float]) -> list[tuple[str, dict[str, float]]]:
    """Generate 10 weight perturbation scenarios from a baseline weight dict.

    Scenarios:
      - Baseline (no change)
      - For each of the 4 criteria: +0.05 and -0.05 (8 scenarios)
        Difference is redistributed equally across the other 3 criteria.
        Any weight clipped below 0.0 is set to 0.0 and the remainder is
        renormalised so weights always sum exactly to 1.0.
      - Equal weights: all criteria at 0.25
    """
    criteria = list(baseline.keys())
    scenarios: list[tuple[str, dict[str, float]]] = []

    # Baseline
    scenarios.append(("baseline", dict(baseline)))

    # ±0.05 perturbations
    for target in criteria:
        for sign, label in [(+0.05, "+0.05"), (-0.05, "-0.05")]:
            w = dict(baseline)
            w[target] = baseline[target] + sign
            others = [c for c in criteria if c != target]
            redistrib = -sign / len(others)
            for c in others:
                w[c] = baseline[c] + redistrib

            # Clip and renormalise
            for c in criteria:
                w[c] = max(0.0, w[c])
            total = sum(w.values())
            for c in criteria:
                w[c] = w[c] / total

            short = target[:3]          # e.g. "ene", "env", "com", "pra"
            name = f"{short} {label}"
            scenarios.append((name, w))

    # Equal weights
    scenarios.append(("equal", {c: 0.25 for c in criteria}))

    return scenarios


def rerank_with_weights(merged_df: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Recompute GT and architecture ranks within each scenario using perturbed weights.

    For each scenario (grouped by arch_scenario_id):
      - gt_weighted  = Σ weights[c] * gt_{c}   → ranked descending (rank 1 = highest)
      - arch_weighted = Σ weights[c] * arch_{c} → ranked descending (rank 1 = highest)

    The recomputed rank columns replace the loaded rank values; criterion score
    columns are never modified.
    """
    df = merged_df.copy()

    df["_gt_weighted"] = sum(
        weights[c] * df[f"gt_{c}"].astype(float) for c in CRITERIA
    )
    df["_arch_weighted"] = sum(
        weights[c] * df[f"arch_{c}"].astype(float) for c in CRITERIA
    )

    df["gt_rank"] = (
        df.groupby("arch_scenario_id")["_gt_weighted"]
        .rank(method="average", ascending=False)
    )
    df["arch_rank"] = (
        df.groupby("arch_scenario_id")["_arch_weighted"]
        .rank(method="average", ascending=False)
    )

    df = df.drop(columns=["_gt_weighted", "_arch_weighted"])
    return df


def run_sensitivity_analysis() -> pd.DataFrame:
    """Run the full sensitivity analysis and return a results DataFrame.

    Steps:
      1. Load ground truth and all three architecture results files.
      2. Match architecture scenarios to GT using the existing match_scenarios()
         pipeline (no pre-computed ranks are used after this point).
      3. Filter failed scenarios (1928 sentinel) once per architecture.
      4. For each of the 10 weight scenarios, rerank alternatives within each
         matched scenario and compute Kendall tau / Spearman rho / Top-k accuracy
         via compute_ranking_metrics().
      5. Print a summary table and robustness check, then export results CSV.
    """
    print("=" * 72)
    print("  SENSITIVITY ANALYSIS — MCDA ARCHITECTURE COMPARISON")
    print(f"  Model: {MODEL_KEY}")
    print("=" * 72)

    # 1. Load data
    print("\n[1] Loading ground truth and architectures...")
    gt_by_type = load_ground_truth(CONFIG)
    gt_lookup = build_gt_lookup(gt_by_type)

    arch_names = ["Pure", "RAG", "Hybrid"]
    clean_merged: dict[str, pd.DataFrame] = {}
    for name, path in CONFIG["architectures"].items():
        arch_df = load_architecture(path, name)
        merged = match_scenarios(gt_lookup, arch_df, name)
        if len(merged) == 0:
            print(f"  WARNING: No matched data for {name} — skipping.")
            continue
        filtered, n_failed, n_total = filter_failed_scenarios(merged)
        if n_failed:
            print(f"  [{name}] Filtered {n_failed}/{n_total} failed scenarios.")
        clean_merged[name] = filtered

    # 2. Weight scenarios
    weight_scenarios = generate_weight_scenarios(CRITERION_WEIGHTS)
    print(f"\n[2] Running {len(weight_scenarios)} weight scenarios...")

    # 3. Compute metrics for every (scenario, architecture) combination
    results: list[dict] = []

    for scen_name, weights in weight_scenarios:
        for arch_name in arch_names:
            if arch_name not in clean_merged:
                continue
            df_reranked = rerank_with_weights(clean_merged[arch_name], weights)
            metrics = compute_ranking_metrics(df_reranked)
            results.append({
                "scenario_name": scen_name,
                "weights_json": json.dumps({c: round(v, 6) for c, v in weights.items()}),
                "architecture": arch_name,
                "kendall_tau": metrics["kendall_tau"],
                "spearman_rho": metrics["spearman_rho"],
                "top1_accuracy": metrics["top1_accuracy"],
                "top2_accuracy": metrics["top2_accuracy"],
            })

    results_df = pd.DataFrame(results)

    # 4. Print Kendall tau summary table
    print("\n" + "=" * 72)
    print("  KENDALL TAU SUMMARY TABLE")
    print("=" * 72)

    tau_pivot = results_df.pivot_table(
        index="scenario_name",
        columns="architecture",
        values="kendall_tau",
        aggfunc="first",
    )
    # Preserve scenario order
    scen_order = [s for s, _ in weight_scenarios]
    tau_pivot = tau_pivot.reindex(scen_order)
    # Column order
    col_order = [c for c in ["Pure", "RAG", "Hybrid"] if c in tau_pivot.columns]
    tau_pivot = tau_pivot[col_order]

    header = f"  {'Scenario':<22}" + "".join(f"{c:>10}" for c in col_order)
    print(header)
    print("  " + "-" * (22 + 10 * len(col_order)))
    for scen in scen_order:
        row = f"  {scen:<22}"
        for c in col_order:
            val = tau_pivot.loc[scen, c] if scen in tau_pivot.index else float("nan")
            row += f"{val:>10.4f}" if not (isinstance(val, float) and np.isnan(val)) else f"{'N/A':>10}"
        print(row)

    # 5. Robustness chec
    print("  ROBUSTNESS CHECK  (Hybrid tau > RAG tau > Pure tau)")


    preserved = 0
    for scen in scen_order:
        sub = results_df[results_df["scenario_name"] == scen]
        tau = {row["architecture"]: row["kendall_tau"] for _, row in sub.iterrows()}
        h = tau.get("Hybrid", float("nan"))
        r = tau.get("RAG", float("nan"))
        p = tau.get("Pure", float("nan"))
        ok = (not np.isnan(h)) and (not np.isnan(r)) and (not np.isnan(p)) and (h > r > p)
        preserved += int(ok)
        status = "PRESERVED" if ok else "VIOLATED "
        print(f"  {scen:<22}  {status}   Hybrid={h:.4f}  RAG={r:.4f}  Pure={p:.4f}")

    n_total_scen = len(weight_scenarios)
    print(f"\n  Architecture order (Hybrid > RAG > Pure) preserved in "
          f"{preserved}/{n_total_scen} scenarios")

    # 6. Export
    output_path = OUTPUT_DIR / f"sensitivity_analysis_{MODEL_KEY}.csv"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False)
    print(f"\n  Results saved to: {output_path}")

    return results_df


if __name__ == "__main__":
    run_sensitivity_analysis()
