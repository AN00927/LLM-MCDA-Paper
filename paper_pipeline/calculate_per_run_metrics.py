#!/usr/bin/env python3
"""
calculate_per_run_metrics.py

Computes ranking and error metrics for each individual model run
(not averaged across runs). Produces per-run CSV files consumed by
 generate_boxplot_tex.py and generate_violin_plot_tex.py.

Usage:
    python paper_pipeline/calculate_per_run_metrics.py
    python paper_pipeline/calculate_per_run_metrics.py --all-models
    python paper_pipeline/calculate_per_run_metrics.py --model gemini
"""

import argparse
import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

import pandas as pd
import numpy as np
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_KEY, MODEL_SPECS
from sentinel_utils import _is_complete_run_file, read_table_clean

# ---------- dynamic import of CalculateMetrics ----------
_cm_path = PROJECT_ROOT / "Miscellaneous Scripts" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("CalculateMetrics", _cm_path)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

load_ground_truth = _cm.load_ground_truth
load_architecture = _cm.load_architecture
build_gt_lookup = _cm.build_gt_lookup
build_gt_id_lookup = _cm.build_gt_id_lookup
match_scenarios = _cm.match_scenarios
filter_failed_scenarios = _cm.filter_failed_scenarios
compute_criterion_metrics = _cm.compute_criterion_metrics
_build_config = _cm._build_config

OUTPUT_DIR = PROJECT_ROOT / "paper" / "per_run_metrics"

ARCH_STEMS = {
    "Direct_LLM_Scoring": "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring": "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring": "LLM-Parameterized_Reference_Scoring",
}

DECISION_TYPES = ["HVAC", "Appliance", "Shower"]


def compute_ranking_metrics_local(merged_df):
    """Kendall tau, Spearman rho, Top-1, and Top-2 - per-scenario then averaged.

    Scenarios where any rank value is NaN (genuinely missing) are skipped
    entirely so a single bad row does not turn the whole scenario's tau/rho
    into NaN.
    """
    taus = []
    rhos = []
    top1_ok = 0
    top2_ok = 0
    n = 0

    for sid in merged_df["arch_scenario_id"].unique():
        sc = merged_df[merged_df["arch_scenario_id"] == sid].copy()
        if len(sc) < 2:
            continue

        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values

        # Skip scenario if any rank is NaN (not sentinel-filtered, genuinely missing)
        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue

        n += 1

        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            tau, _ = stats.kendalltau(gt_r, ar_r)
            taus.append(tau if not np.isnan(tau) else 0.0)
        else:
            taus.append(1.0 if np.array_equal(gt_r, ar_r) else 0.0)

        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            rho, _ = stats.spearmanr(gt_r, ar_r)
            rhos.append(rho if not np.isnan(rho) else 0.0)
        else:
            rhos.append(1.0 if np.array_equal(gt_r, ar_r) else 0.0)

        gt_top1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        if gt_top1 == ar_top1:
            top1_ok += 1

        ar_top2 = set(sc.sort_values("arch_rank")["norm_alternative"].head(2).values)
        if gt_top1 in ar_top2:
            top2_ok += 1

    return {
        "kendall_tau": round(np.mean(taus), 4) if taus else np.nan,
        "spearman_rho": round(np.mean(rhos), 4) if rhos else np.nan,
        "top1_accuracy": round(top1_ok / n, 4) if n else np.nan,
        "top2_accuracy": round(top2_ok / n, 4) if n else np.nan,
        "n_scenarios_evaluated": n,
    }


def _discover_run_files(output_folder, arch_stem):
    run_files = sorted(output_folder.glob(f"{arch_stem}_results_run_*.xlsx"))
    return [f for f in run_files if _is_complete_run_file(f)]


def compute_per_run_metrics_for_model(model_key):
    config = _build_config(model_key)
    output_folder = Path(config["output_csv"]).parent

    gt_by_type = load_ground_truth(config)
    gt_lookup = build_gt_lookup(gt_by_type)
    gt_id_lookup = build_gt_id_lookup(gt_by_type)

    all_rows = []

    for arch_name, arch_stem in ARCH_STEMS.items():
        run_files = _discover_run_files(output_folder, arch_stem)
        if not run_files:
            print(f"  [SKIP] {arch_name}: no per-run files in {output_folder}")
            continue

        print(f"  [INFO] {arch_name}: {len(run_files)} run files")

        for run_path in run_files:
            run_name = run_path.stem
            run_num = int(run_name.split("_run_")[-1]) if "_run_" in run_name else 0

            arch_df = load_architecture(run_path, arch_name)
            merged, _ = match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name)

            if merged.empty:
                print(f"    [WARN] {arch_name} run {run_num:02d}: no matched scenarios")
                continue

            clean, n_failed, n_total = filter_failed_scenarios(merged)
            if clean.empty:
                print(f"    [WARN] {arch_name} run {run_num:02d}: all scenarios failed")
                continue

            criterion_metrics = compute_criterion_metrics(clean)
            ranking_metrics = compute_ranking_metrics_local(clean)

            all_rows.append({
                "architecture": arch_name,
                "run": run_num,
                "decision_type": "Overall",
                "kendall_tau": ranking_metrics.get("kendall_tau", float("nan")),
                "spearman_rho": ranking_metrics.get("spearman_rho", float("nan")),
                "top1_accuracy": ranking_metrics.get("top1_accuracy", float("nan")),
                "top2_accuracy": ranking_metrics.get("top2_accuracy", float("nan")),
                "overall_mae": criterion_metrics.get("overall_MAE", float("nan")),
                "overall_rmse": criterion_metrics.get("overall_RMSE", float("nan")),
                "overall_rmse_mae_ratio": criterion_metrics.get("overall_rmse_mae_ratio", float("nan")),
                "energy_cost_mae": criterion_metrics.get("energy_cost_MAE", float("nan")),
                "environmental_mae": criterion_metrics.get("environmental_MAE", float("nan")),
                "comfort_mae": criterion_metrics.get("comfort_MAE", float("nan")),
                "practicality_mae": criterion_metrics.get("practicality_MAE", float("nan")),
                "energy_cost_rmse": criterion_metrics.get("energy_cost_RMSE", float("nan")),
                "environmental_rmse": criterion_metrics.get("environmental_RMSE", float("nan")),
                "comfort_rmse": criterion_metrics.get("comfort_RMSE", float("nan")),
                "practicality_rmse": criterion_metrics.get("practicality_RMSE", float("nan")),
                "n_scenarios": ranking_metrics.get("n_scenarios_evaluated", 0),
                "n_failed": n_failed,
                "n_total": n_total,
                "model": model_key,
            })

            for dt in DECISION_TYPES:
                dt_clean = clean[clean["decision_type"] == dt]
                if dt_clean.empty:
                    continue
                dt_crit = compute_criterion_metrics(dt_clean)
                dt_rank = compute_ranking_metrics_local(dt_clean)
                all_rows.append({
                    "architecture": arch_name,
                    "run": run_num,
                    "decision_type": dt,
                    "kendall_tau": dt_rank.get("kendall_tau", float("nan")),
                    "spearman_rho": dt_rank.get("spearman_rho", float("nan")),
                    "top1_accuracy": dt_rank.get("top1_accuracy", float("nan")),
                    "top2_accuracy": dt_rank.get("top2_accuracy", float("nan")),
                    "overall_mae": dt_crit.get("overall_MAE", float("nan")),
                    "overall_rmse": dt_crit.get("overall_RMSE", float("nan")),
                    "overall_rmse_mae_ratio": dt_crit.get("overall_rmse_mae_ratio", float("nan")),
                    "energy_cost_mae": dt_crit.get("energy_cost_MAE", float("nan")),
                    "environmental_mae": dt_crit.get("environmental_MAE", float("nan")),
                    "comfort_mae": dt_crit.get("comfort_MAE", float("nan")),
                    "practicality_mae": dt_crit.get("practicality_MAE", float("nan")),
                    "energy_cost_rmse": dt_crit.get("energy_cost_RMSE", float("nan")),
                    "environmental_rmse": dt_crit.get("environmental_RMSE", float("nan")),
                    "comfort_rmse": dt_crit.get("comfort_RMSE", float("nan")),
                    "practicality_rmse": dt_crit.get("practicality_RMSE", float("nan")),
                    "n_scenarios": dt_rank.get("n_scenarios_evaluated", 0),
                    "n_failed": 0,
                    "n_total": 0,
                    "model": model_key,
                })

    if not all_rows:
        print(f"  [ERROR] No metrics computed for {model_key}")
        return None

    df = pd.DataFrame(all_rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    xlsx_path = OUTPUT_DIR / f"per_run_metrics_{model_key}.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"  [OK] Wrote {xlsx_path} ({len(df)} rows)")

    csv_path = OUTPUT_DIR / f"per_run_metrics_{model_key}.csv"
    df.to_csv(csv_path, index=False)
    print(f"  [OK] Wrote {csv_path} ({len(df)} rows)")

    return df


def write_aggregate_all_models():
    """Concatenate per-model CSVs (alphabetical by model key) into
    per_run_metrics_all.csv (+.xlsx), matching each model's own row order."""
    dfs = []
    for mk in sorted(MODEL_SPECS.keys()):
        csv_path = OUTPUT_DIR / f"per_run_metrics_{mk}.csv"
        if not csv_path.exists():
            print(f"  [SKIP] {mk}: {csv_path} not found, cannot include in aggregate")
            continue
        dfs.append(pd.read_csv(csv_path))

    if not dfs:
        print("  [ERROR] No per-model CSVs found; skipping aggregate")
        return

    all_df = pd.concat(dfs, ignore_index=True)

    all_csv_path = OUTPUT_DIR / "per_run_metrics_all.csv"
    all_df.to_csv(all_csv_path, index=False)
    print(f"  [OK] Wrote {all_csv_path} ({len(all_df)} rows)")

    all_xlsx_path = OUTPUT_DIR / "per_run_metrics_all.xlsx"
    all_df.to_excel(all_xlsx_path, index=False, engine="openpyxl")
    print(f"  [OK] Wrote {all_xlsx_path} ({len(all_df)} rows)")


def main():
    parser = argparse.ArgumentParser(description="Compute per-run metrics")
    parser.add_argument("--model", choices=list(MODEL_SPECS.keys()), default=None)
    parser.add_argument("--all-models", action="store_true")
    args = parser.parse_args()

    if args.all_models:
        models = list(MODEL_SPECS.keys())
    elif args.model:
        models = [args.model]
    else:
        models = [MODEL_KEY]

    for mk in models:
        print(f"\n{'=' * 60}")
        print(f"Per-run metrics: {mk}")
        print(f"{'=' * 60}")
        compute_per_run_metrics_for_model(mk)

    if args.all_models:
        print(f"\n{'=' * 60}")
        print("Aggregating per-model CSVs -> per_run_metrics_all")
        print(f"{'=' * 60}")
        write_aggregate_all_models()

    print("\nDone.")


if __name__ == "__main__":
    main()
