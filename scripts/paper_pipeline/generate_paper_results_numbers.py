#!/usr/bin/env python3
"""Generate numbers_master.csv from raw data sources."""
import argparse
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

from common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
IMPORT_ROOT = PROJECT_ROOT
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

from common.paths import repository_path  # noqa: E402
from common.model_config import get_model_artifact_subdir  # noqa: E402

_ap = argparse.ArgumentParser(description="Generate numbers_master.csv from raw data sources.")
_ap.add_argument("--output", default=str(repository_path("Combined Metrics", "numbers_master.csv")),
                 help="CSV to write (default: local_manuscripts/paper/numbers_master.csv)")
# Averaging basis of the IncrementalContribution table (S6). Every row, the two
# baselines and the LLM rows alike, uses the same one:
#   per_type_mean  unweighted mean of the HVAC / Appliance / Shower means
#                  (baselines: baseline_metrics.csv "Overall_per_type_mean";
#                  LLM rows: per run, mean of the three per-type values, then
#                  the mean over runs)
#   pooled         every scenario weighted equally (baselines: "Overall_pooled";
#                  LLM rows: the per-run "Overall" value, then the mean over runs)
TABLE7_BASES = ("per_type_mean", "pooled")
_ap.add_argument("--table7-basis", choices=TABLE7_BASES, default="pooled",
                 help="Averaging basis of the IncrementalContribution rows (default "
                      "pooled, the author's choice)")
_args = _ap.parse_args()
OUT = Path(_args.output).expanduser()
if not OUT.is_absolute():
    OUT = PROJECT_ROOT / OUT
TABLE7_BASIS = _args.table7_basis

REQUIRED_PER_RUN_CSVS = [
    repository_path(get_model_artifact_subdir(model, "metrics"), f"per_run_metrics_{model}.csv")
    for model in ("deepseek", "gemini", "gptoss", "qwen")
]
MISSING_PER_RUN_CSVS = [str(path) for path in REQUIRED_PER_RUN_CSVS if not path.is_file()]
if MISSING_PER_RUN_CSVS:
    _ap.error(
        "Required local-only per-run metric inputs are missing: "
        + ", ".join(MISSING_PER_RUN_CSVS)
        + "; restore them under local_manuscripts/ or set "
        "LLM_MCDA_LOCAL_MANUSCRIPTS_DIR."
    )

rows = []

def add(category, architecture, model_or_pooled, decision_type, metric, value, sd=None,
        cost_source=None):
    rows.append({
        "category": category,
        "architecture": architecture,
        "model_or_pooled": model_or_pooled,
        "decision_type": decision_type,
        "metric": metric,
        "value": round(value, 6) if pd.notna(value) else np.nan,
        "sd": round(sd, 6) if sd is not None and pd.notna(sd) else np.nan,
        # Table 8 only: which price source the row's cost came from.
        "cost_source": cost_source if cost_source is not None else np.nan,
    })

ARCH_SHORT = {
    "Direct_LLM_Scoring": "AD",
    "Example-Guided_LLM_Scoring": "AE",
    "LLM-Parameterized_Reference_Scoring": "AH",
}
LLM_ARCHS = list(ARCH_SHORT.keys())
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]

per_run_frames = []
for f, path in zip(MODELS, REQUIRED_PER_RUN_CSVS):
    df = pd.read_csv(path)
    per_run_frames.append(df)
per_run = pd.concat(per_run_frames, ignore_index=True)

rag = pd.read_excel(repository_path("Combined Metrics","rag_ablation_summary.xlsx"))

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
# TABLE 8: Cost per run, COMPUTED from the run diagnostics.
#
# Previously these values were transcribed from the LaTeX by hand, which let the
# table drift from the run data (three cells disagreed materially). They are now
# derived from each run's architecture diagnostics JSON, averaged over the runs:
#   * cost: the charged cost `total_cost_usd` (OpenRouter usage.cost summed over
#     the run's calls) when the JSON has it. Under :floor routing the provider,
#     and so the price, varies call to call, so this is the only exact figure.
#   * fallback, for a run whose JSON predates that field: its token totals
#     (total_tokens_input / total_tokens_output) priced at the list rates in the
#     model_config.MODEL_SPECS label, which are hand-typed and can drift.
# The cost row's `cost_source` column says which: "charged" (every run had
# total_cost_usd), "label_price" (none had) or "mixed:<k>/<n>_charged", with
# ";cost_covers_<a>/<b>_calls" appended when a charged run's calls_with_cost
# shows that some calls reported no cost (their cost is then missing, not zero).
# Token counts and calls/scenario are emitted alongside the cost so the prose
# figures are also traceable.
# ────────────────────────────────────────────────────────────────
import json
import glob
import re
sys.path.insert(0, str(PROJECT_ROOT))
from common.model_config import MODEL_SPECS

# List price per 1M tokens, parsed from the MODEL_SPECS label strings so that a
# price edit in model_config propagates here instead of being duplicated.
def _parse_prices(label):
    nums = re.findall(r"\$([0-9.]+)\s*/\s*M", label)
    if len(nums) != 2:
        raise ValueError(f"Cannot parse input/output price from label: {label!r}")
    return float(nums[0]), float(nums[1])

N_SCENARIOS = 195

for model_key, spec in MODEL_SPECS.items():
    folder = spec["output_folder"]
    # Table 8 identifies models by the same raw key every other category uses.
    label = model_key
    for arch in LLM_ARCHS:
        paths = sorted(glob.glob(
            str(PROJECT_ROOT / folder / f"{arch}_results_diagnostics_run_*.json")))
        if not paths:
            continue
        tok_in = tok_out = calls = 0
        cost = 0.0
        n_charged = 0
        calls_charged = calls_covered = 0
        for p in paths:
            with open(p) as fh:
                diag = json.load(fh)
            run_in = diag.get("total_tokens_input", 0)
            run_out = diag.get("total_tokens_output", 0)
            tok_in += run_in
            tok_out += run_out
            calls += diag.get("total_api_calls", 0)
            charged = diag.get("total_cost_usd")
            if charged is not None and pd.notna(charged):
                cost += float(charged)
                n_charged += 1
                # calls_with_cost: how many of the run's calls reported a cost
                run_calls = diag.get("total_api_calls", 0)
                calls_charged += run_calls
                calls_covered += diag.get("calls_with_cost", run_calls)
            else:
                price_in, price_out = _parse_prices(spec["label"])
                cost += run_in / 1e6 * price_in + run_out / 1e6 * price_out
        n = len(paths)
        tok_in, tok_out, calls, cost = tok_in / n, tok_out / n, calls / n, cost / n
        source = ("charged" if n_charged == n else
                  "label_price" if n_charged == 0 else f"mixed:{n_charged}/{n}_charged")
        if n_charged and calls_covered < calls_charged:
            source += f";cost_covers_{calls_covered}/{calls_charged}_calls"
        add("Table8_cost_per_run", arch, label, "Overall", "cost_usd", cost,
            cost_source=source)
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
# The dataset-median condition and the NearestNeighbor copy baseline are
# deterministic. The median numbers come from hybrid_ablation_summary.xlsx
# (arm "default_params"); NearestNeighbor comes from the preserved baseline
# metrics CSV. Every delta is relative to the dataset median.
# LLM rows computed from per-run CSVs as per-type arithmetic means.
# ────────────────────────────────────────────────────────────────

# NearestNeighbor is deterministic. Its metric snapshot is preserved at results/older_runs/unclassified_legacy/Baselines/baseline_metrics.csv.
# Baseline regeneration is a separate operation and is not part of the safe
# paper pipeline.
#
# The pooled aggregate is used here, matching what the manuscript's baseline
# rows have always reported; per-decision-type arithmetic means are also
# available in that CSV under decision_type == "Overall_per_type_mean".
_BASELINE_METRICS = PROJECT_ROOT / "results" / "older_runs" / "unclassified_legacy" / "Baselines" / "baseline_metrics.csv"
if not os.path.exists(_BASELINE_METRICS):
    raise FileNotFoundError(
        f"{_BASELINE_METRICS} not found. Restore the preserved baseline metrics "
        "file under results/older_runs/unclassified_legacy/Baselines/."
    )
_bm = pd.read_csv(_BASELINE_METRICS)
_bm = _bm[_bm["decision_type"] == {"per_type_mean": "Overall_per_type_mean",
                                   "pooled": "Overall_pooled"}[TABLE7_BASIS]]


def _baseline_metric(name, metric):
    sel = _bm[(_bm["baseline"] == name) & (_bm["metric"] == metric)]["value"]
    if sel.empty:
        raise KeyError(f"No {metric} for baseline {name} in {_BASELINE_METRICS}")
    return float(sel.iloc[0])


def _dataset_median_metrics():
    """Dataset-median condition (retrieval-set median hidden parameters, no
    inference) from hybrid_ablation_summary.xlsx. The condition does not depend
    on the model, so the four per-model rows must agree."""
    path = repository_path("Combined Metrics", "hybrid_ablation_summary.xlsx")
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run the hybrid ablation summary first.")
    if TABLE7_BASIS == "pooled":
        df = pd.read_excel(path, sheet_name="summary")
    else:
        df = pd.read_excel(path, sheet_name="summary_by_type")
    df = df[df["arm"] == "default_params"]
    vals = {}
    for col, key in (("top1_accuracy", "Top-1"), ("kendall_tau", "kendall_tau")):
        per_model = df.groupby("model")[col].apply(
            (lambda g: g.mean()) if TABLE7_BASIS == "per_type_mean" else (lambda g: g.iloc[0]))
        if per_model.nunique() != 1 and (per_model.max() - per_model.min()) > 1e-9:
            raise ValueError(f"dataset-median {col} differs across models: {per_model.to_dict()}")
        vals[key] = float(per_model.iloc[0])
    return vals


baseline_data = {
    "DatasetMedian": _dataset_median_metrics(),
    "NearestNeighbor": {
        "Top-1": _baseline_metric("NearestNeighbor", "top1_accuracy"),
        "kendall_tau": _baseline_metric("NearestNeighbor", "kendall_tau"),
    },
}
for name, vals in baseline_data.items():
    for met, val in vals.items():
        delta = val - baseline_data["DatasetMedian"][met]
        # model_or_pooled carries the basis label, not a model pool: the
        # baselines are model-independent.
        if met == "kendall_tau":
            add("IncrementalContribution", name, TABLE7_BASIS, "Overall", "kendall_tau", val)
            add("IncrementalContribution", name, TABLE7_BASIS, "Overall", "tau_delta", delta)
        else:
            add("IncrementalContribution", name, TABLE7_BASIS, "Overall", "Top-1", val)
            add("IncrementalContribution", name, TABLE7_BASIS, "Overall", "Top-1_delta", delta)

for arch in LLM_ARCHS:
    model_means = {}
    for model in MODELS:
        types = (["HVAC", "Appliance", "Shower"] if TABLE7_BASIS == "per_type_mean"
                 else ["Overall"])
        sub = per_run[(per_run["architecture"] == arch) &
                      (per_run["model"] == model) &
                      (per_run["decision_type"].isin(types))]
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
    # One model per label (F1): the table is standardised on Kendall's tau, so
    # the Top-1 cell of the "best" row is the tau-best model's Top-1. Choosing
    # the Top-1 model separately put two models under one label.
    best_top1_model, worst_top1_model = best_tau_model, worst_tau_model

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
        clean_by_run[run_num] = (clean, set(merged["arch_scenario_id"].unique()), merged)
    out = []
    runs = sorted(clean_by_run)
    for r in runs:
        clean, all_sids, merged_r = clean_by_run[r]
        parts = [clean]
        n_recovered = 0
        for sid in sorted(all_sids - set(clean["arch_scenario_id"].unique())):
            for o in runs:
                donor = clean_by_run[o][0]
                if o != r and sid in set(donor["arch_scenario_id"]):
                    parts.append(donor[donor["arch_scenario_id"] == sid])
                    n_recovered += 1
                    break
            else:
                # Failed in every run: stays in, under the failure rule.
                parts.append(merged_r[merged_r["arch_scenario_id"] == sid])
        rec = pd.concat(parts, ignore_index=True)
        rk = _prm.compute_ranking_metrics_inclusive(rec)
        cr = _prm.compute_criterion_metrics_inclusive(rec)
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

df_out = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df_out.to_csv(OUT, index=False)
print(f"Wrote {len(df_out)} rows to {OUT}")

print(f"\nDistinct models in RAG ablation: {n_distinct_models}")
print(f"Models: {sorted(rag['model_key'].unique())}")
