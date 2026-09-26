#!/usr/bin/env python3
"""Generate numbers_master.csv from raw data sources."""
import argparse
import pandas as pd
import numpy as np
import os

_ap = argparse.ArgumentParser(description="Generate numbers_master.csv from raw data sources.")
_ap.add_argument("--output", default="paper/numbers_master.csv",
                 help="CSV to write (default paper/numbers_master.csv)")
OUT = _ap.parse_args().output
rows = []

def add(category, architecture, model_or_pooled, decision_type, metric, value, sd=None):
    rows.append({
        "category": category,
        "architecture": architecture,
        "model_or_pooled": model_or_pooled,
        "decision_type": decision_type,
        "metric": metric,
        "value": round(value, 6) if pd.notna(value) else np.nan,
        "sd": round(sd, 6) if sd is not None and pd.notna(sd) else np.nan,
    })

ARCH_SHORT = {
    "Direct_LLM_Scoring": "AD",
    "Example-Guided_LLM_Scoring": "AE",
    "LLM-Parameterized_Reference_Scoring": "AH",
}
LLM_ARCHS = list(ARCH_SHORT.keys())
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
MODEL_LABELS = {"deepseek": "DeepSeek", "gemini": "Gemini", "gptoss": "GPT-OSS", "qwen": "Qwen"}

per_run_frames = []
for f in MODELS:
    df = pd.read_csv(f"paper/per_run_metrics/per_run_metrics_{f}.csv")
    per_run_frames.append(df)
per_run = pd.concat(per_run_frames, ignore_index=True)

imputed = pd.read_excel("Analysis/MetricsSummary/metrics_summary_all_models_imputed_perrun.xlsx")

rag = pd.read_excel("Analysis/RAG_Ablation/rag_ablation_summary.xlsx")

# ────────────────────────────────────────────────────────────────
# TABLES 5-7: no rows pooled across models
#
# This file used to write Table5_pooled_overall, the pooled half of
# Table6_per_criterion_mae and Table7_per_decision_type_pooled: means over the
# 20 per-run values of all four models. Neither the paper nor the supplement
# prints any of them (checked 2026-09-25; both state that no value is pooled
# across models), and a four-model mean can hide a per-model reversal, so they
# were removed. The per-model best/worst rows below are kept.
# ────────────────────────────────────────────────────────────────
criterion_mae_keys = ["energy_cost_mae", "environmental_mae", "comfort_mae", "practicality_mae"]
criterion_mae_labels = ["EnergyCost", "Environmental", "Comfort", "Practicality"]

# TABLE 6: Per-criterion MAE (per-run CSVs, Overall, best/worst model)
for arch in LLM_ARCHS:
    arch_data = per_run[per_run["architecture"] == arch]
    model_means = {}
    for model in MODELS:
        m_data = arch_data[(arch_data["model"] == model) & (arch_data["decision_type"] == "Overall")]
        overall_vals = m_data["overall_mae"].dropna().values
        if len(overall_vals) > 0:
            model_means[model] = np.mean(overall_vals)
    if len(model_means) >= 2:
        best_m = min(model_means, key=model_means.get)
        worst_m = max(model_means, key=model_means.get)
        for label, mod in [("best", best_m), ("worst", worst_m)]:
            for raw_key, nice_label in zip(criterion_mae_keys, criterion_mae_labels):
                sub = arch_data[(arch_data["model"] == mod) & (arch_data["decision_type"] == "Overall")]
                vals = sub[raw_key].dropna().values
                if len(vals) > 0:
                    add("Table6_best_worst", arch, label, mod, nice_label,
                        np.mean(vals), np.std(vals, ddof=1))
            sub_mae = arch_data[(arch_data["model"] == mod) & (arch_data["decision_type"] == "Overall")]
            vals_mae = sub_mae["overall_mae"].dropna().values
            if len(vals_mae) > 0:
                add("Table6_best_worst", arch, label, mod, "Overall",
                    np.mean(vals_mae), np.std(vals_mae, ddof=1))

# ────────────────────────────────────────────────────────────────
# TABLE 7: Per-decision-type (per-run CSVs, best/worst model)
# ────────────────────────────────────────────────────────────────
for arch in LLM_ARCHS:
    for dt in ["HVAC", "Appliance", "Shower"]:
        model_means = {}
        for model in MODELS:
            sub = per_run[(per_run["architecture"] == arch) &
                          (per_run["model"] == model) &
                          (per_run["decision_type"] == dt)]
            tau_vals = sub["kendall_tau"].dropna().values
            if len(tau_vals) > 0:
                model_means[model] = np.mean(tau_vals)
        if len(model_means) >= 2:
            best_m = max(model_means, key=model_means.get)
            worst_m = min(model_means, key=model_means.get)
            for label, mod in [("best", best_m), ("worst", worst_m)]:
                for raw_m, nice_m in [("kendall_tau", "tau"), ("top1_accuracy", "Top-1")]:
                    sub = per_run[(per_run["architecture"] == arch) &
                                  (per_run["model"] == mod) &
                                  (per_run["decision_type"] == dt)]
                    vals = sub[raw_m].dropna().values
                    if len(vals) > 0:
                        add("Table7_best_worst", arch, label, mod, dt + "_" + nice_m,
                            np.mean(vals), np.std(vals, ddof=1))

# ────────────────────────────────────────────────────────────────
# TABLE 8: Cost per run, COMPUTED from measured token usage.
#
# Previously these values were transcribed from the LaTeX by hand, which let the
# table drift from the run data (three cells disagreed materially). They are now
# derived: per-run token totals come from the architecture diagnostics JSON
# (total_tokens_input / total_tokens_output, averaged over the 5 runs) and are
# priced with the list rates in model_config.MODEL_SPECS. Token counts and
# calls/scenario are emitted alongside the cost so the prose figures are also
# traceable.
# ────────────────────────────────────────────────────────────────
import json
import glob
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model_config import MODEL_SPECS

# List price per 1M tokens, parsed from the MODEL_SPECS label strings so that a
# price edit in model_config propagates here instead of being duplicated.
def _parse_prices(label):
    nums = re.findall(r"\$([0-9.]+)\s*/\s*M", label)
    if len(nums) != 2:
        raise ValueError(f"Cannot parse input/output price from label: {label!r}")
    return float(nums[0]), float(nums[1])

MODEL_KEY_TO_LABEL = {"gptoss": "GPT-OSS", "qwen": "Qwen",
                      "deepseek": "DeepSeek", "gemini": "Gemini"}
N_SCENARIOS = 195

for model_key, spec in MODEL_SPECS.items():
    price_in, price_out = _parse_prices(spec["label"])
    folder = spec["output_folder"]
    label = MODEL_KEY_TO_LABEL[model_key]
    for arch in LLM_ARCHS:
        paths = sorted(glob.glob(
            os.path.join(folder, f"{arch}_results_diagnostics_run_*.json")))
        if not paths:
            continue
        tok_in = tok_out = calls = 0
        for p in paths:
            with open(p) as fh:
                diag = json.load(fh)
            tok_in += diag.get("total_tokens_input", 0)
            tok_out += diag.get("total_tokens_output", 0)
            calls += diag.get("total_api_calls", 0)
        n = len(paths)
        tok_in, tok_out, calls = tok_in / n, tok_out / n, calls / n
        cost = tok_in / 1e6 * price_in + tok_out / 1e6 * price_out
        add("Table8_cost_per_run", arch, label, "Overall", "cost_usd", cost)
        add("Table8_cost_per_run", arch, label, "Overall", "tokens_in_per_run", tok_in)
        add("Table8_cost_per_run", arch, label, "Overall", "tokens_out_per_run", tok_out)
        add("Table8_cost_per_run", arch, label, "Overall", "tokens_per_scenario",
            (tok_in + tok_out) / N_SCENARIOS)
        add("Table8_cost_per_run", arch, label, "Overall", "calls_per_scenario",
            calls / N_SCENARIOS)

# ────────────────────────────────────────────────────────────────
# TABLE 9: RAG ablation (from xlsx)
# ────────────────────────────────────────────────────────────────
n_distinct_models = rag["model_key"].nunique()
for _, r in rag.iterrows():
    add("Table9_rag_ablation", r["ablation_id"], r["model_key"], "Overall", "kendall_tau", r["kendall_tau"])
    if pd.notna(r["score_mae"]):
        add("Table9_rag_ablation", r["ablation_id"], r["model_key"], "Overall", "score_mae", r["score_mae"])
    if pd.notna(r["score_rmse"]):
        add("Table9_rag_ablation", r["ablation_id"], r["model_key"], "Overall", "score_rmse", r["score_rmse"])

# ────────────────────────────────────────────────────────────────
# INCREMENTAL CONTRIBUTION TABLE
# Baselines (FixedDefault, NearestNeighbor) are deterministic;
# computed by run_baseline_models.py + evaluate_architecture_metrics.py --include-baselines.
# LLM rows computed from per-run CSVs as per-type arithmetic means.
# ────────────────────────────────────────────────────────────────

# FixedDefault and NearestNeighbor are deterministic. These used to be literals
# transcribed into this file, which meant they could not be checked and did not
# follow a change to the baseline code -- and they silently went stale when the
# Fixed-Default appliance defaults were corrected. They are now read from
# Output Files/Baselines/baseline_metrics.csv, produced by
# "Miscellaneous Scripts/evaluate_baseline_metrics.py" (which itself consumes
# run_baseline_models.py's output). Regenerate in that order after any baseline
# change.
#
# The pooled aggregate is used here, matching what the manuscript's baseline
# rows have always reported; per-decision-type arithmetic means are also
# available in that CSV under decision_type == "Overall_per_type_mean".
_BASELINE_METRICS = "Output Files/Baselines/baseline_metrics.csv"
if not os.path.exists(_BASELINE_METRICS):
    raise FileNotFoundError(
        f"{_BASELINE_METRICS} not found. Run:\n"
        '  python "Miscellaneous Scripts/run_baseline_models.py" '
        "--baselines fixed_default nearest_neighbor\n"
        '  python "Miscellaneous Scripts/evaluate_baseline_metrics.py"'
    )
_bm = pd.read_csv(_BASELINE_METRICS)
_bm = _bm[_bm["decision_type"] == "Overall_pooled"]


def _baseline_metric(name, metric):
    sel = _bm[(_bm["baseline"] == name) & (_bm["metric"] == metric)]["value"]
    if sel.empty:
        raise KeyError(f"No {metric} for baseline {name} in {_BASELINE_METRICS}")
    return float(sel.iloc[0])


baseline_data = {
    name: {
        "Top-1": _baseline_metric(name, "top1_accuracy"),
        "kendall_tau": _baseline_metric(name, "kendall_tau"),
    }
    for name in ("FixedDefault", "NearestNeighbor")
}
for name, vals in baseline_data.items():
    for met, val in vals.items():
        delta = val - baseline_data["FixedDefault"][met]
        if met == "kendall_tau":
            add("IncrementalContribution", name, "pooled", "Overall", "kendall_tau", val)
            add("IncrementalContribution", name, "pooled", "Overall", "tau_delta", delta)
        else:
            add("IncrementalContribution", name, "pooled", "Overall", "Top-1", val)
            add("IncrementalContribution", name, "pooled", "Overall", "Top-1_delta", delta)

for arch in LLM_ARCHS:
    model_means = {}
    for model in MODELS:
        sub = per_run[(per_run["architecture"] == arch) &
                      (per_run["model"] == model) &
                      (per_run["decision_type"].isin(["HVAC", "Appliance", "Shower"]))]
        if len(sub) == 0:
            continue
        run_means = sub.groupby("run")[["kendall_tau", "top1_accuracy"]].mean()
        model_means[model] = {
            "tau": run_means["kendall_tau"].mean(),
            "top1": run_means["top1_accuracy"].mean(),
        }

    if len(model_means) == 0:
        continue

    best_tau_model = max(model_means, key=lambda m: model_means[m]["tau"])
    worst_tau_model = min(model_means, key=lambda m: model_means[m]["tau"])
    best_top1_model = max(model_means, key=lambda m: model_means[m]["top1"])
    worst_top1_model = min(model_means, key=lambda m: model_means[m]["top1"])

    for label, model, metric_key in [
        ("best", best_tau_model, "tau"),
        ("worst", worst_tau_model, "tau"),
        ("best", best_top1_model, "top1"),
        ("worst", worst_top1_model, "top1"),
    ]:
        val = model_means[model][metric_key]
        metric_label = {"tau": "kendall_tau", "top1": "Top-1"}[metric_key]
        add("IncrementalContribution", f"{arch}_{label}", model, "Overall", metric_label, val)

# ────────────────────────────────────────────────────────────────
# GPT-OSS RECOVERY: with and without multi-run recovery
#
# Both variants are on the per-run basis: every run is scored on its own and
# the metrics are averaged over runs.
#   run_k / pooled_5run / best / worst  -- WITHOUT recovery: the main-text
#       values, a failed scenario-run dropped from its run.
#   recovered_5run -- WITH recovery: in each run, a scenario that failed takes
#       its rows from the first other run (in run order) in which it succeeded,
#       then the run is scored by the same functions as the main text. A
#       scenario that failed in every run stays out.
# "pooled_5run" is the mean over GPT-OSS's five runs, not a pool across models.
# The rows are filtered to decision_type == "Overall": before, the block also
# swept in the three per-type rows of each run and labelled them "Overall",
# which put the mean of 20 mixed rows (0.8985) into pooled_5run.
# ────────────────────────────────────────────────────────────────
gptoss_runs = per_run[(per_run["model"] == "gptoss") &
                      (per_run["architecture"] == "LLM-Parameterized_Reference_Scoring") &
                      (per_run["decision_type"] == "Overall")]

for _, r in gptoss_runs.iterrows():
    run_id = int(r["run"])
    add("GPTOSS_recovery", "AH", f"run_{run_id}", "Overall", "tau", r["kendall_tau"])
    add("GPTOSS_recovery", "AH", f"run_{run_id}", "Overall", "MAE", r["overall_mae"])
    add("GPTOSS_recovery", "AH", f"run_{run_id}", "Overall", "Top-1", r["top1_accuracy"])

pooled_tau = gptoss_runs["kendall_tau"].mean()
pooled_mae = gptoss_runs["overall_mae"].mean()
pooled_top1 = gptoss_runs["top1_accuracy"].mean()
add("GPTOSS_recovery", "AH", "pooled_5run", "Overall", "tau", pooled_tau, gptoss_runs["kendall_tau"].std(ddof=1))
add("GPTOSS_recovery", "AH", "pooled_5run", "Overall", "MAE", pooled_mae, gptoss_runs["overall_mae"].std(ddof=1))
add("GPTOSS_recovery", "AH", "pooled_5run", "Overall", "Top-1", pooled_top1, gptoss_runs["top1_accuracy"].std(ddof=1))

worst_tau = gptoss_runs["kendall_tau"].min()
best_tau = gptoss_runs["kendall_tau"].max()
worst_mae = gptoss_runs["overall_mae"].max()
best_mae = gptoss_runs["overall_mae"].min()
add("GPTOSS_recovery", "AH", "worst_single_run", "Overall", "tau", worst_tau)
add("GPTOSS_recovery", "AH", "best_single_run", "Overall", "tau", best_tau)
add("GPTOSS_recovery", "AH", "worst_single_run", "Overall", "MAE", worst_mae)
add("GPTOSS_recovery", "AH", "best_single_run", "Overall", "MAE", best_mae)


def _recovered_per_run(model_key, arch="LLM-Parameterized_Reference_Scoring"):
    """Per-run metrics with each failed scenario-run backfilled from the first
    other run in which that scenario succeeded. Uses the same loading,
    matching, sentinel filtering and metric functions as
    calculate_per_run_metrics.py, so without backfill it reproduces the
    per-run CSVs exactly."""
    import importlib.util as _ilu
    import contextlib as _cl
    import io as _io
    _spec = _ilu.spec_from_file_location(
        "calculate_per_run_metrics",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "calculate_per_run_metrics.py"))
    _prm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_prm)
    config = _prm._build_config(model_key)
    folder = os.path.dirname(config["output_csv"])
    with _cl.redirect_stdout(_io.StringIO()):
        gt = _prm.load_ground_truth(config)
    gt_lookup, gt_id_lookup = _prm.build_gt_lookup(gt), _prm.build_gt_id_lookup(gt)
    from pathlib import Path as _P
    clean_by_run = {}
    for rp in _prm._discover_run_files(_P(folder), arch):
        run_num = int(rp.stem.split("_run_")[-1])
        with _cl.redirect_stdout(_io.StringIO()):
            arch_df = _prm.load_architecture(rp, arch)
            merged, _ = _prm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch)
        clean, _, _ = _prm.filter_failed_scenarios(merged)
        clean_by_run[run_num] = (clean, set(merged["arch_scenario_id"].unique()))
    out = []
    runs = sorted(clean_by_run)
    for r in runs:
        clean, all_sids = clean_by_run[r]
        parts = [clean]
        n_recovered = 0
        for sid in sorted(all_sids - set(clean["arch_scenario_id"].unique())):
            for o in runs:
                donor = clean_by_run[o][0]
                if o != r and sid in set(donor["arch_scenario_id"]):
                    parts.append(donor[donor["arch_scenario_id"] == sid])
                    n_recovered += 1
                    break
        rec = pd.concat(parts, ignore_index=True)
        rk = _prm.compute_ranking_metrics_local(rec)
        cr = _prm.compute_criterion_metrics(rec)
        out.append({"run": r, "kendall_tau": rk["kendall_tau"],
                    "top1_accuracy": rk["top1_accuracy"], "overall_mae": cr["overall_MAE"],
                    "n_scenarios": rk["n_scenarios_evaluated"], "n_recovered": n_recovered})
    return pd.DataFrame(out)


_rec = _recovered_per_run("gptoss")
if len(_rec):
    add("GPTOSS_recovery", "AH", "recovered_5run", "Overall", "tau",
        _rec["kendall_tau"].mean(), _rec["kendall_tau"].std(ddof=1))
    add("GPTOSS_recovery", "AH", "recovered_5run", "Overall", "MAE",
        _rec["overall_mae"].mean(), _rec["overall_mae"].std(ddof=1))
    add("GPTOSS_recovery", "AH", "recovered_5run", "Overall", "Top-1",
        _rec["top1_accuracy"].mean(), _rec["top1_accuracy"].std(ddof=1))
    add("GPTOSS_recovery", "AH", "recovered_5run", "Overall", "n_scenarios_per_run",
        _rec["n_scenarios"].mean())
    add("GPTOSS_recovery", "AH", "recovered_5run", "Overall", "n_recovered_per_run",
        _rec["n_recovered"].mean())

for arch in LLM_ARCHS:
    for model in MODELS:
        sub = per_run[(per_run["architecture"] == arch) &
                      (per_run["model"] == model) &
                      (per_run["decision_type"] == "Overall")]
        if len(sub) == 0:
            continue
        for metric in ["kendall_tau", "overall_mae", "top1_accuracy"]:
            nice = {"kendall_tau": "tau", "overall_mae": "MAE", "top1_accuracy": "Top-1"}[metric]
            vals = sub[metric].dropna().values
            if len(vals) > 0:
                add("PerModel", arch, model, "Overall", nice,
                    np.mean(vals), np.std(vals, ddof=1))

# ────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────
# ROBUSTNESS: Method A (per-run) vs Imputed (per-run) comparison
# ────────────────────────────────────────────────────────────────
print("\n=== ROBUSTNESS: Method A vs Imputed (per-run) ===")
print(f"{'Arch':4s} {'Metric':6s} {'MethodA':>8s} {'Imputed':>8s} {'diff':>8s}")
for arch in LLM_ARCHS:
    for metric in ["kendall_tau", "overall_mae", "top1_accuracy"]:
        nice = {"kendall_tau": "tau", "overall_mae": "MAE", "top1_accuracy": "Top-1"}[metric]
        # Method A: per-run CSVs, mean across all runs
        pr_vals = per_run[(per_run["architecture"] == arch) &
                          (per_run["decision_type"] == "Overall")][metric].dropna().values
        pr_mean = np.mean(pr_vals) if len(pr_vals) > 0 else np.nan
        # Imputed: from imputed per-run xlsx (comparison sheet has variant ImputedPerRun and lowercase metric names)
        imp_sub = imputed[(imputed["variant"] == "ImputedPerRun") &
                          (imputed["architecture"] == arch) &
                          (imputed["decision_type"] == "Overall") &
                          (imputed["metric"] == metric)]
        imp_vals = imp_sub["value"].dropna().values
        imp_mean = np.mean(imp_vals) if len(imp_vals) > 0 else np.nan
        if pd.notna(pr_mean) and pd.notna(imp_mean):
            diff = abs(pr_mean - imp_mean)
            flag = " ***" if diff > 0.005 else ""
            add("RobustnessComparison", arch, "MethodA", "Overall", nice, pr_mean)
            add("RobustnessComparison", arch, "Imputed", "Overall", nice, imp_mean)
            print(f"{ARCH_SHORT[arch]:4s} {nice:6s} {pr_mean:8.4f} {imp_mean:8.4f} {diff:8.4f}{flag}")

df_out = pd.DataFrame(rows)
df_out.to_csv(OUT, index=False)
print(f"Wrote {len(df_out)} rows to {OUT}")

print(f"\nDistinct models in RAG ablation: {n_distinct_models}")
print(f"Models: {sorted(rag['model_key'].unique())}")
