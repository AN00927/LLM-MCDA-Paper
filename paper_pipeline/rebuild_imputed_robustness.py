#!/usr/bin/env python3
"""C5: rebuild the imputed robustness check at per-run granularity.

Computes, for all 4 models x 3 architectures, three comparison columns:

  (a) Method A           per-run-then-average: failed scenarios excluded from their
                         run's metric computation, metrics averaged across 5 runs.
  (b) Imputed (all-5)    existing variant: runs aggregated first; a scenario that
                         fails in ALL five runs receives the 0.5 scale midpoint at
                         criterion-score level before metric computation.
  (c) Imputed (per-run)  NEW variant: for EACH run independently, any scenario
                         carrying a sentinel in that run receives 0.5 for the
                         affected criterion scores before that run's MAVT
                         aggregation, ranking, and metric computation; metrics are
                         averaged across the 5 runs, each run evaluating the full
                         195-scenario test set.

Imputation happens only at the criterion-score level (energy_cost, environmental,
comfort, practicality). MAVT scores and ranks are never imputed directly; the
existing aggregation and ranking machinery (CalculateMetrics.impute_failed_scores
+ recompute_arch_ranks) runs on the imputed scores. The sentinel 1928 never enters
an average or a ranking.

Zero API calls. Writes only NEW files:
  Analysis/MetricsSummary/metrics_summary_all_models_imputed_perrun.xlsx

Embedded verification: (a) checked against paper/per_run_metrics_all.csv and the
supplementary table tab:imputed_comparison; (b) checked against
Analysis/MetricsSummary/metrics_summary_all_models_imputed.xlsx.
"""

import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS, get_output_folder  # noqa: E402
from sentinel_utils import _is_complete_run_file  # noqa: E402

ARCH_STEMS = {
    "Direct_LLM_Scoring": "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring": "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring": "LLM-Parameterized_Reference_Scoring",
}
MODEL_KEYS = sorted(MODEL_SPECS.keys())  # deepseek, gemini, gptoss, qwen

OUT_XLSX = PROJECT_ROOT / "Analysis" / "MetricsSummary" / "metrics_summary_all_models_imputed_perrun.xlsx"

RANK_METRICS = ["kendall_tau", "spearman_rho", "top1_accuracy", "top2_accuracy"]
CRIT_KEYS = ["energy_cost", "environmental", "comfort", "practicality"]
TABLE_METRICS = ["kendall_tau", "overall_mae", "top1_accuracy"]

# Supplementary table tab:imputed_comparison targets (pooled means across 4 models).
SUPP_METHOD_A = {
    ("Direct_LLM_Scoring", "kendall_tau"): 0.093,
    ("Direct_LLM_Scoring", "overall_mae"): 0.232,
    ("Direct_LLM_Scoring", "top1_accuracy"): 0.341,
    ("Example-Guided_LLM_Scoring", "kendall_tau"): 0.277,
    ("Example-Guided_LLM_Scoring", "overall_mae"): 0.171,
    ("Example-Guided_LLM_Scoring", "top1_accuracy"): 0.492,
    ("LLM-Parameterized_Reference_Scoring", "kendall_tau"): 0.899,
    ("LLM-Parameterized_Reference_Scoring", "overall_mae"): 0.055,
    ("LLM-Parameterized_Reference_Scoring", "top1_accuracy"): 0.913,
}
SUPP_IMPUTED = {
    ("Direct_LLM_Scoring", "kendall_tau"): 0.095,
    ("Direct_LLM_Scoring", "overall_mae"): 0.219,
    ("Direct_LLM_Scoring", "top1_accuracy"): 0.354,
    ("Example-Guided_LLM_Scoring", "kendall_tau"): 0.314,
    ("Example-Guided_LLM_Scoring", "overall_mae"): 0.161,
    ("Example-Guided_LLM_Scoring", "top1_accuracy"): 0.513,
    ("LLM-Parameterized_Reference_Scoring", "kendall_tau"): 0.900,
    ("LLM-Parameterized_Reference_Scoring", "overall_mae"): 0.051,
    ("LLM-Parameterized_Reference_Scoring", "top1_accuracy"): 0.917,
}


def _load_modules():
    """Dynamically import CalculateMetrics and calculate_per_run_metrics
    (same pattern as the pipeline; paths contain spaces / hyphens)."""
    cm_path = PROJECT_ROOT / "Miscellaneous Scripts" / "CalculateMetrics.py"
    cm_spec = spec_from_file_location("CalculateMetrics", cm_path)
    cm = module_from_spec(cm_spec)
    cm_spec.loader.exec_module(cm)

    prm_path = PROJECT_ROOT / "paper_pipeline" / "calculate_per_run_metrics.py"
    prm_spec = spec_from_file_location("calculate_per_run_metrics", prm_path)
    prm = module_from_spec(prm_spec)
    prm_spec.loader.exec_module(prm)
    return cm, prm


def _run_files(output_folder, stem):
    """Discover per-run result files (same completion filter as the pipeline)."""
    return [
        f for f in sorted(output_folder.glob(f"{stem}_results_run_*.xlsx"))
        if _is_complete_run_file(f)
    ]


def _crit_metrics_dict(crit_res):
    out = {
        "overall_mae": crit_res.get("overall_MAE", np.nan),
        "overall_rmse": crit_res.get("overall_RMSE", np.nan),
        "overall_rmse_mae_ratio": crit_res.get("overall_rmse_mae_ratio", np.nan),
    }
    for c in CRIT_KEYS:
        out[f"{c}_mae"] = crit_res.get(f"{c}_MAE", np.nan)
        out[f"{c}_rmse"] = crit_res.get(f"{c}_RMSE", np.nan)
    return out


def _rank_metrics_dict(rank_res):
    out = {m: rank_res.get(m, np.nan) for m in RANK_METRICS}
    out["n_scenarios"] = rank_res.get("n_scenarios_evaluated", np.nan)
    return out


def compute_variant_a_per_run(cm, prm, gt_lookup, gt_id_lookup, run_paths, arch_name):
    """Method A: per-run filtered metrics."""
    rows = []
    for run_path in run_paths:
        arch_df = cm.load_architecture(run_path, arch_name)
        merged, _ = cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name)
        clean, n_failed, n_total = cm.filter_failed_scenarios(merged)
        crit = _crit_metrics_dict(cm.compute_criterion_metrics(clean))
        rank = _rank_metrics_dict(prm.compute_ranking_metrics_local(clean))
        row = {
            "variant": "MethodA",
            "architecture": arch_name,
            "run": int(run_path.stem.split("_run_")[-1]),
            "n_failed": n_failed,
            "n_total": n_total,
        }
        row.update(crit)
        row.update(rank)
        rows.append(row)
    return rows


def compute_variant_b(cm, gt_lookup, gt_id_lookup, run_paths, arch_name):
    """Existing all-five-runs imputed variant: aggregate, then impute, then evaluate."""
    aggregated = cm.aggregate_run_files(run_paths)
    arch_df = cm.load_architecture(aggregated, arch_name)
    merged, _ = cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name)
    merged_imp, n_rows, n_sids = cm.impute_failed_scores(merged.copy(), impute_value=0.5)
    merged_imp = cm.recompute_arch_ranks(merged_imp)
    crit = _crit_metrics_dict(cm.compute_criterion_metrics(merged_imp))
    rank = _rank_metrics_dict(cm.compute_ranking_metrics(merged_imp))
    row = {
        "variant": "ImputedAll5",
        "architecture": arch_name,
        "n_imputed_scenarios": n_sids,
        "n_imputed_cells": n_rows,
    }
    row.update(crit)
    row.update(rank)
    return row


def compute_variant_c_per_run(cm, prm, gt_lookup, gt_id_lookup, run_paths, arch_name):
    """Per-run imputed variant. Returns (per-run rows, rank-consistency diagnostics)."""
    rows = []
    rank_mismatch_total = 0
    rank_checked_total = 0
    for run_path in run_paths:
        arch_df = cm.load_architecture(run_path, arch_name)
        merged, _ = cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name)
        if merged.empty:
            continue
        run_num = int(run_path.stem.split("_run_")[-1])

        # Sentinel detection at criterion-score level (pre-imputation).
        sentinel_mask = pd.Series(False, index=merged.index)
        for c in CRIT_KEYS:
            col = f"arch_{c}"
            sentinel_mask |= (pd.to_numeric(merged[col], errors="coerce") == 1928)
        imputed_sids = set(merged.loc[sentinel_mask, "arch_scenario_id"].unique())

        merged_imp, n_rows, n_sids = cm.impute_failed_scores(merged.copy(), impute_value=0.5)
        merged_imp = cm.recompute_arch_ranks(merged_imp)

        # Rank-consistency guard: for scenarios with no imputed cells, the recomputed
        # rank must equal the rank stored in the run file (same weights/tie-break).
        guard = merged_imp[~merged_imp["arch_scenario_id"].isin(imputed_sids)]
        if len(guard) > 0:
            orig = pd.to_numeric(merged.loc[guard.index, "arch_rank"], errors="coerce")
            new = pd.to_numeric(merged_imp.loc[guard.index, "arch_rank"], errors="coerce")
            cmp_df = pd.DataFrame({"o": orig.values, "n": new.values}).dropna()
            rank_mismatch_total += int((cmp_df["o"] != cmp_df["n"]).sum())
            rank_checked_total += len(cmp_df)

        crit = _crit_metrics_dict(cm.compute_criterion_metrics(merged_imp))
        rank = _rank_metrics_dict(prm.compute_ranking_metrics_local(merged_imp))
        row = {
            "variant": "ImputedPerRun",
            "architecture": arch_name,
            "run": run_num,
            "n_imputed_scenarios": n_sids,
            "n_imputed_cells": n_rows,
            "n_total": len(merged["arch_scenario_id"].unique()),
        }
        row.update(crit)
        row.update(rank)
        rows.append(row)
    return rows, {"mismatches": rank_mismatch_total, "checked": rank_checked_total}


def _mean_over_runs(run_rows):
    """Mean of per-run metric values (per column)."""
    df = pd.DataFrame(run_rows)
    out = {}
    for col in RANK_METRICS + ["overall_mae", "overall_rmse", "overall_rmse_mae_ratio",
                               "n_scenarios"] + [f"{c}_mae" for c in CRIT_KEYS]:
        out[col] = float(df[col].mean())
    return out


def _long_rows(model_key, arch_name, agg):
    return [
        {"model": model_key, "architecture": arch_name, "decision_type": "Overall",
         "metric": m, "value": agg.get(m, np.nan)}
        for m in RANK_METRICS + ["overall_mae", "overall_rmse", "overall_rmse_mae_ratio",
                                 "n_scenarios"] + [f"{c}_mae" for c in CRIT_KEYS]
    ]


def main():
    print("=" * 72)
    print("C5 per-run imputed robustness rebuild")
    print("=" * 72)

    cm, prm = _load_modules()

    variant_a_long = []   # long rows: model x arch x metric (Method A)
    variant_c_long = []   # long rows: model x arch x metric (ImputedPerRun)
    variant_b_rows = []   # wide rows: model x arch (ImputedAll5)
    detail_rows = []      # per-run rows (Method A + ImputedPerRun)
    impute_count_rows = []
    rank_diag_all = []

    for mk in MODEL_KEYS:
        config = cm._build_config(mk)
        output_folder = PROJECT_ROOT / get_output_folder(mk)
        print(f"\n[{mk}] {output_folder.name}")
        gt_by_type = cm.load_ground_truth(config)
        gt_lookup = cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = cm.build_gt_id_lookup(gt_by_type)

        for arch_name, stem in ARCH_STEMS.items():
            run_paths = _run_files(output_folder, stem)
            if not run_paths:
                print(f"  [SKIP] {arch_name}: no run files")
                continue

            a_rows = compute_variant_a_per_run(cm, prm, gt_lookup, gt_id_lookup, run_paths, arch_name)
            b_row = compute_variant_b(cm, gt_lookup, gt_id_lookup, run_paths, arch_name)
            c_rows, rank_diag = compute_variant_c_per_run(cm, prm, gt_lookup, gt_id_lookup, run_paths, arch_name)
            rank_diag_all.append((mk, arch_name, rank_diag))

            a_agg = _mean_over_runs(a_rows)
            c_agg = _mean_over_runs(c_rows)

            variant_a_long.extend(_long_rows(mk, arch_name, a_agg))
            variant_c_long.extend(_long_rows(mk, arch_name, c_agg))

            b_row["model"] = mk
            variant_b_rows.append(b_row)

            for r in a_rows + c_rows:
                r["model"] = mk
            detail_rows.extend(a_rows + c_rows)

            n_imp = [r["n_imputed_scenarios"] for r in c_rows]
            n_cells = [r["n_imputed_cells"] for r in c_rows]
            impute_count_rows.append({
                "model": mk, "architecture": arch_name,
                "scenarios_imputed_mean_per_run": float(np.mean(n_imp)),
                "cells_imputed_mean_per_run": float(np.mean(n_cells)),
                "scenarios_imputed_min": int(min(n_imp)),
                "scenarios_imputed_max": int(max(n_imp)),
                "cells_imputed_min": int(min(n_cells)),
                "cells_imputed_max": int(max(n_cells)),
                "n_scenarios_per_run_min": int(min(r["n_scenarios"] for r in c_rows)),
                "n_scenarios_per_run_max": int(max(r["n_scenarios"] for r in c_rows)),
            })

            print(f"  {arch_name}: A tau={a_agg['kendall_tau']:.4f} top1={a_agg['top1_accuracy']:.4f} "
                  f"mae={a_agg['overall_mae']:.4f} | C tau={c_agg['kendall_tau']:.4f} "
                  f"top1={c_agg['top1_accuracy']:.4f} mae={c_agg['overall_mae']:.4f} | "
                  f"imputed scen/run={float(np.mean(n_imp)):.2f}")

    # ---------------- verification ----------------
    print("\n" + "=" * 72)
    print("VERIFICATION")
    print("=" * 72)

    # (a) per-run vs pipeline per-run CSVs
    pipeline_csv = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
    max_diff_a = 0.0
    n_cmp_a = 0
    if pipeline_csv.exists():
        pipe = pd.read_csv(pipeline_csv)
        pipe = pipe[pipe["decision_type"] == "Overall"]
        for r in [x for x in detail_rows if x["variant"] == "MethodA"]:
            prow = pipe[(pipe["model"] == r["model"]) & (pipe["architecture"] == r["architecture"])
                        & (pipe["run"] == r["run"])]
            if len(prow) == 0:
                continue
            for m in ["kendall_tau", "spearman_rho", "top1_accuracy", "top2_accuracy", "overall_mae"]:
                if pd.notna(r.get(m)) and pd.notna(prow[m].iloc[0]):
                    max_diff_a = max(max_diff_a, abs(r[m] - prow[m].iloc[0]))
                    n_cmp_a += 1
        print(f"  (a) max |per-run diff| vs paper/per_run_metrics_all.csv: {max_diff_a:.6f} "
              f"({n_cmp_a} values compared)")

    # (a) pooled vs supplementary table Method A
    print("  (a) pooled vs supplementary tab:imputed_comparison 'Method A':")
    ok_a = True
    for (arch, m), target in SUPP_METHOD_A.items():
        vals = [r["value"] for r in variant_a_long if r["architecture"] == arch and r["metric"] == m]
        got = float(np.mean(vals)) if vals else np.nan
        flag = "OK" if abs(got - target) <= 0.0006 else "MISMATCH"
        ok_a = ok_a and flag == "OK"
        print(f"      {arch} {m:16s} got={got:.4f} target={target:.4f} {flag}")

    # (b) per-model vs existing imputed aggregate xlsx
    existing_imp = PROJECT_ROOT / "Analysis" / "MetricsSummary" / "metrics_summary_all_models_imputed.xlsx"
    max_diff_b = 0.0
    n_cmp_b = 0
    metric_name_map = {"overall_mae": "overall_MAE", "overall_rmse": "overall_RMSE",
                       "overall_rmse_mae_ratio": "overall_rmse_mae_ratio"}
    if existing_imp.exists():
        ex = pd.read_excel(existing_imp)
        ex = ex[ex["decision_type"] == "Overall"]
        for r in variant_b_rows:
            for m in RANK_METRICS + ["overall_mae", "overall_rmse", "overall_rmse_mae_ratio"]:
                erow = ex[(ex["model"] == r["model"]) & (ex["architecture"] == r["architecture"])
                          & (ex["metric"] == metric_name_map.get(m, m))]
                if len(erow) == 0 or pd.isna(r.get(m)):
                    continue
                max_diff_b = max(max_diff_b, abs(r[m] - erow["value"].iloc[0]))
                n_cmp_b += 1
        print(f"  (b) max |value diff| vs metrics_summary_all_models_imputed.xlsx: "
              f"{max_diff_b:.6f} ({n_cmp_b} values compared)")

    # (b) pooled vs supplementary table Imputed column
    print("  (b) pooled vs supplementary tab:imputed_comparison 'Imputed (0.5)':")
    ok_b = True
    for (arch, m), target in SUPP_IMPUTED.items():
        vals = [r.get(m) for r in variant_b_rows if r["architecture"] == arch]
        vals = [v for v in vals if pd.notna(v)]
        got = float(np.mean(vals)) if vals else np.nan
        flag = "OK" if abs(got - target) <= 0.0006 else "MISMATCH"
        ok_b = ok_b and flag == "OK"
        print(f"      {arch} {m:16s} got={got:.4f} target={target:.4f} {flag}")

    # (c) full-set coverage
    cov_ok = True
    for r in [x for x in detail_rows if x["variant"] == "ImputedPerRun"]:
        if r["n_scenarios"] != 195:
            cov_ok = False
            print(f"      WARN {r['model']} {r['architecture']} run {r['run']}: "
                  f"{r['n_scenarios']} scenarios")
    print(f"  (c) every run evaluated 195 scenarios: {cov_ok}")

    # rank-consistency guard
    print("  rank-consistency guard (recomputed rank == file rank, non-imputed scenarios):")
    for mk, arch, diag in rank_diag_all:
        print(f"      {mk} {arch}: {diag['mismatches']}/{diag['checked']} mismatches")

    # ---------------- outputs ----------------
    print("\n" + "=" * 72)
    print("WRITING OUTPUTS")
    print("=" * 72)

    comp_rows = []
    for r in variant_a_long:
        comp_rows.append({"variant": "MethodA", **r})
    for r in variant_b_rows:
        for m in RANK_METRICS + ["overall_mae", "overall_rmse", "overall_rmse_mae_ratio",
                                 "n_scenarios"] + [f"{c}_mae" for c in CRIT_KEYS]:
            comp_rows.append({"variant": "ImputedAll5", "model": r["model"],
                              "architecture": r["architecture"], "decision_type": "Overall",
                              "metric": m, "value": r.get(m, np.nan)})
    for r in variant_c_long:
        comp_rows.append({"variant": "ImputedPerRun", **r})
    comp_df = pd.DataFrame(comp_rows)

    pooled_rows = []
    for arch in ARCH_STEMS:
        for m in TABLE_METRICS:
            row = {"architecture": arch, "metric": m}
            for variant in ["MethodA", "ImputedAll5", "ImputedPerRun"]:
                vals = comp_df[(comp_df["variant"] == variant) & (comp_df["architecture"] == arch)
                               & (comp_df["metric"] == m)]["value"]
                row[variant] = float(np.mean(vals.dropna())) if len(vals.dropna()) else np.nan
            row["perrun_minus_A"] = row["ImputedPerRun"] - row["MethodA"]
            row["all5_minus_A"] = row["ImputedAll5"] - row["MethodA"]
            pooled_rows.append(row)
    pooled_df = pd.DataFrame(pooled_rows)

    detail_cols = ["variant", "model", "architecture", "run", "n_scenarios",
                   "n_imputed_scenarios", "n_imputed_cells", "n_failed", "n_total"] \
        + RANK_METRICS + ["overall_mae", "overall_rmse"]
    detail_df = pd.DataFrame([{k: r.get(k) for k in detail_cols} for r in detail_rows])
    detail_df = detail_df.sort_values(["variant", "model", "architecture", "run"]).reset_index(drop=True)

    impute_df = pd.DataFrame(impute_count_rows)

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        comp_df.to_excel(writer, sheet_name="comparison", index=False)
        pooled_df.to_excel(writer, sheet_name="pooled", index=False)
        impute_df.to_excel(writer, sheet_name="imputation_counts", index=False)
        detail_df.to_excel(writer, sheet_name="per_run_detail", index=False)
    print(f"  Wrote {OUT_XLSX}")

    # ---------------- verdict ----------------
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)
    for variant in ["MethodA", "ImputedAll5", "ImputedPerRun"]:
        tau = {}
        for short, long in [("AD", "Direct_LLM_Scoring"), ("AE", "Example-Guided_LLM_Scoring"),
                            ("AH", "LLM-Parameterized_Reference_Scoring")]:
            vals = comp_df[(comp_df["variant"] == variant) & (comp_df["architecture"] == long)
                           & (comp_df["metric"] == "kendall_tau")]["value"]
            tau[short] = float(np.mean(vals.dropna()))
        order = "AH > AE > AD" if tau["AH"] > tau["AE"] > tau["AD"] else "NOT HELD"
        print(f"  {variant:14s} pooled tau: AD={tau['AD']:.4f} AE={tau['AE']:.4f} "
              f"AH={tau['AH']:.4f} -> {order}")

    idx = pooled_df["perrun_minus_A"].abs().idxmax()
    largest = pooled_df.loc[idx]
    print(f"  largest |per-run - MethodA| movement (pooled): {largest['architecture']} "
          f"{largest['metric']} {largest['MethodA']:.4f} -> {largest['ImputedPerRun']:.4f} "
          f"({largest['perrun_minus_A']:+.4f})")

    print("  per-model tau ordering under per-run imputation:")
    for mk in MODEL_KEYS:
        vals = {}
        for short, long in [("AD", "Direct_LLM_Scoring"), ("AE", "Example-Guided_LLM_Scoring"),
                            ("AH", "LLM-Parameterized_Reference_Scoring")]:
            v = comp_df[(comp_df["variant"] == "ImputedPerRun") & (comp_df["model"] == mk)
                        & (comp_df["architecture"] == long) & (comp_df["metric"] == "kendall_tau")]
            vals[short] = v["value"].iloc[0] if len(v) else np.nan
        ok = vals["AH"] > vals["AE"] > vals["AD"]
        print(f"      {mk}: AD={vals['AD']:.4f} AE={vals['AE']:.4f} AH={vals['AH']:.4f} "
              f"{'holds' if ok else 'BREAKS'}")

    print("\nVerification summary: (a) matches pipeline CSV + supp table:",
          ok_a and max_diff_a < 0.0015, "| (b) matches existing imputed xlsx + supp table:", ok_b)
    print("Done.")


if __name__ == "__main__":
    main()
