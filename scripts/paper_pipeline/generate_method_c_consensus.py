#!/usr/bin/env python3
"""
generate_method_c_consensus.py

Computes Method C (mean-aggregate-then-evaluate) metrics for comparison to Method A.
Reads per-run xlsx files (5 runs), computes consensus scores per scenario,
evaluates metrics once on the consensus, and compares to per-run CSVs.

Usage: python paper_pipeline/generate_method_c_consensus.py
"""
import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

import pandas as pd
import numpy as np
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS, CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
from sentinel_utils import SENTINEL_VALUE, CRITERIA as SCORE_COLS

_cm_path = PROJECT_ROOT / "Miscellaneous Scripts" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("CalculateMetrics", _cm_path)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

load_ground_truth = _cm.load_ground_truth
load_architecture = _cm.load_architecture
build_gt_lookup = _cm.build_gt_lookup
build_gt_id_lookup = _cm.build_gt_id_lookup
match_scenarios = _cm.match_scenarios
compute_criterion_metrics = _cm.compute_criterion_metrics
_build_config = _cm._build_config
_rank_with_deterministic_tiebreak = _cm._rank_with_deterministic_tiebreak

OUTPUT = PROJECT_ROOT / "paper" / "method_c_comparison.csv"

MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
ARCHS = ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]
META_COLS_PRESERVE = ["decision_type", "question", "location",
                      "outdoor_temp", "appliance_age", "flow_rate",
                      "household_size", "utility_budget", "housing_type"]


def safe_mean(series):
    """Mean of non-NaN values, requiring >= 3 valid entries."""
    vals = series.dropna()
    return np.mean(vals) if len(vals) >= 3 else np.nan


def compute_ranking_metrics_local(merged_df):
    """Kendall tau, Top-1 - per-scenario then averaged.
    Mirrors calculate_per_run_metrics.py compute_ranking_metrics_local.
    """
    taus = []
    top1_ok = 0
    n = 0

    for sid in merged_df["arch_scenario_id"].unique():
        sc = merged_df[merged_df["arch_scenario_id"] == sid]
        if len(sc) < 2:
            continue

        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values

        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue

        n += 1

        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            tau, _ = stats.kendalltau(gt_r, ar_r)
            taus.append(tau if not np.isnan(tau) else 0.0)
        else:
            taus.append(1.0 if np.array_equal(gt_r, ar_r) else 0.0)

        gt_top1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        if gt_top1 == ar_top1:
            top1_ok += 1

    return {
        "kendall_tau": round(np.mean(taus), 4) if taus else np.nan,
        "top1_accuracy": round(top1_ok / n, 4) if n else np.nan,
        "n_scenarios_evaluated": n,
    }


def main():
    results = []

    for model_key in MODELS:
        config = _build_config(model_key)
        output_folder = Path(config["output_csv"]).parent

        gt_by_type = load_ground_truth(config)
        gt_lookup = build_gt_lookup(gt_by_type)
        gt_id_lookup = build_gt_id_lookup(gt_by_type)

        for arch_name in ARCHS:
            run_dfs = []
            for run_num in range(1, 6):
                xlsx_path = output_folder / f"{arch_name}_results_run_{run_num:02d}.xlsx"
                if xlsx_path.exists():
                    run_dfs.append(pd.read_excel(xlsx_path))

            if len(run_dfs) < 3:
                print(f"  [SKIP] {arch_name} {model_key}: {len(run_dfs)} runs")
                continue

            combined = pd.concat(run_dfs, ignore_index=True)

            for col in SCORE_COLS:
                combined[col] = pd.to_numeric(combined[col], errors="coerce")
                combined.loc[combined[col] == SENTINEL_VALUE, col] = np.nan

            agg_dict = {col: safe_mean for col in SCORE_COLS}
            for mc in META_COLS_PRESERVE:
                if mc in combined.columns:
                    agg_dict[mc] = "first"

            grouped = combined.groupby(["scenario_id", "alternative"]).agg(agg_dict).reset_index()

            grouped["weighted_score"] = (
                grouped["energy_cost"] * CRITERION_WEIGHTS["energy_cost"] +
                grouped["environmental"] * CRITERION_WEIGHTS["environmental"] +
                grouped["comfort"] * CRITERION_WEIGHTS["comfort"] +
                grouped["practicality"] * CRITERION_WEIGHTS["practicality"]
            )

            grouped["rank"] = np.nan
            for sid in grouped["scenario_id"].unique():
                sc_mask = grouped["scenario_id"] == sid
                idx = grouped.index[sc_mask]
                sc = grouped.loc[idx]
                valid = idx[sc[SCORE_COLS].notna().all(axis=1)]
                if len(valid) > 0:
                    sub = grouped.loc[valid, SCORE_COLS + ["weighted_score"]].copy()
                    ranks = _rank_with_deterministic_tiebreak(
                        sub, "weighted_score", TIE_BREAK_PRIORITY,
                        log_prefix=f"[method_c sid={sid}] "
                    )
                    grouped.loc[valid, "rank"] = ranks.values

            arch_df = load_architecture(grouped, arch_name)
            merged, _ = match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name)

            if merged.empty:
                print(f"  [SKIP] {arch_name} {model_key}: no matched scenarios")
                continue

            criterion_metrics = compute_criterion_metrics(merged)
            ranking_metrics = compute_ranking_metrics_local(merged)

            results.append({
                "architecture": arch_name,
                "model": model_key,
                "method_c_tau": ranking_metrics.get("kendall_tau", np.nan),
                "method_c_mae": criterion_metrics.get("overall_MAE", np.nan),
                "method_c_top1": ranking_metrics.get("top1_accuracy", np.nan),
            })
            print(f"  [OK] {arch_name} {model_key}: "
                  f"tau={results[-1]['method_c_tau']:.4f}, "
                  f"mae={results[-1]['method_c_mae']:.4f}, "
                  f"top1={results[-1]['method_c_top1']:.4f}")

    per_run_frames = []
    for mk in MODELS:
        csv_path = PROJECT_ROOT / "paper" / "per_run_metrics" / f"per_run_metrics_{mk}.csv"
        if csv_path.exists():
            per_run_frames.append(pd.read_csv(csv_path))
    if per_run_frames:
        per_run = pd.concat(per_run_frames, ignore_index=True)
        per_run = per_run[per_run["decision_type"] == "Overall"].copy()
    else:
        per_run = pd.DataFrame()

    result_df = pd.DataFrame(results)
    method_a_rows = []
    for _, r in result_df.iterrows():
        arch = r["architecture"]
        model = r["model"]
        sub = per_run[(per_run["architecture"] == arch) & (per_run["model"] == model)]
        ks = sub["kendall_tau"].dropna()
        ms = sub["overall_mae"].dropna()
        ts = sub["top1_accuracy"].dropna()
        method_a_rows.append({
            "architecture": arch,
            "model": model,
            "method_a_tau": ks.mean() if len(ks) else np.nan,
            "method_a_mae": ms.mean() if len(ms) else np.nan,
            "method_a_top1": ts.mean() if len(ts) else np.nan,
        })

    method_a_df = pd.DataFrame(method_a_rows)
    merged_results = result_df.merge(method_a_df, on=["architecture", "model"], how="left")

    merged_results["tau_diff"] = (merged_results["method_c_tau"] - merged_results["method_a_tau"]).abs()
    merged_results["mae_diff"] = (merged_results["method_c_mae"] - merged_results["method_a_mae"]).abs()

    merged_results.to_csv(OUTPUT, index=False)
    print(f"\nWrote {OUTPUT} ({len(merged_results)} rows)")
    print(merged_results.to_string(index=False))


if __name__ == "__main__":
    main()
