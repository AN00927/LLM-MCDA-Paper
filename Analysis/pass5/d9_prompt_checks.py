#!/usr/bin/env python3
"""
d9_prompt_checks.py -- Pass 5, item D9 (rescoping "LLMs should not score").

READ-ONLY. No API calls, writes only under Analysis/pass5/. Per model; nothing
pooled across models. Sentinel/failed scenarios never enter a mean: the
prompt-ablation cell files carry a `failed` flag that the ablation harness sets
whenever any alternative returned the 1928 sentinel (scenario_metrics in
run_prompt_ablation_experiments.py uses SENTINEL_FLOAT); those rows are dropped.

Sections
  1. Appliance emissions contrast in the reference: PJM marginal factors
     (1.041 peak / 0.976 off-peak lbs CO2/kWh), and the realized within-scenario
     spread of the reference Environmental Impact score on the 65 Appliance test
     scenarios, next to the other three criteria.
  2. No-anchors prompt ablation by decision type, per model: A_D control,
     A_D no_anchors, A_E control. Per-run mean over non-failed scenarios, then
     mean over runs (the ablation summarize() convention). Stored tau/Top-1 were
     computed at collection time against the reference as it then stood (the
     Shower reference used an earlier comfort function). Top-1 is therefore
     also recomputed against the CURRENT reference from the stored predicted
     winner (`pred_top1`). Main-benchmark per-run means (numbers of record,
     paper/per_run_metrics/per_run_metrics_all.csv) are listed alongside.
  3. Paired Wilcoxon, no_anchors vs control (A_D), per model x decision type,
     on scenario run-means; Holm within each metric across the 12 tests.

Outputs: d9_appliance_env_contrast.csv, d9_prompt_ablation_by_type.csv,
d9_prompt_ablation_tests.csv, d9_prompt_ablation_ref_check.csv
"""

import contextlib
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "paper_pipeline"))
warnings.filterwarnings("ignore")

with contextlib.redirect_stdout(io.StringIO()):
    import calculate_per_run_metrics as cprm  # noqa: E402
from sentinel_utils import CRITERIA  # noqa: E402

OUT = PROJECT_ROOT / "Analysis" / "pass5"
ABL = PROJECT_ROOT / "Analysis" / "Prompt_Ablation"
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DTYPES = ["HVAC", "Appliance", "Shower"]
STEM = {"AD": "Direct_LLM_Scoring", "AE": "Example-Guided_LLM_Scoring"}


def holm(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for i, idx in enumerate(o):
        run = max(run, (m - i) * p[idx])
        adj[idx] = min(1.0, run)
    return adj


def reference_map():
    """scenario_id -> (decision_type, current reference winner, merged rows)."""
    config = cprm._build_config("gemini")
    folder = Path(config["output_csv"]).parent
    gt_by_type = cprm.load_ground_truth(config)
    gl, gil = cprm.build_gt_lookup(gt_by_type), cprm.build_gt_id_lookup(gt_by_type)
    p = cprm._discover_run_files(folder, "Direct_LLM_Scoring")[0]
    with contextlib.redirect_stdout(io.StringIO()):
        a = cprm.load_architecture(p, "Direct_LLM_Scoring")
        merged, _ = cprm.match_scenarios(gl, gil, a, "Direct_LLM_Scoring")
    ref = {}
    for sid, sc in merged.groupby("arch_scenario_id"):
        w = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ref[int(sid)] = (sc["decision_type"].iloc[0], w)
    return ref, merged


def section1(merged):
    rows = [dict(item="peak_over_offpeak_ratio", value=1.041 / 0.976),
            dict(item="peak_minus_offpeak_as_share_of_peak", value=(1.041 - 0.976) / 1.041),
            dict(item="peak_minus_offpeak_as_share_of_offpeak", value=(1.041 - 0.976) / 0.976)]
    app = merged[merged.decision_type == "Appliance"].copy()
    for c in CRITERIA:
        app[f"gt_{c}"] = app[f"gt_{c}"].astype(float)
    g = app.groupby("arch_scenario_id")
    for c in CRITERIA:
        rng = g[f"gt_{c}"].agg(lambda s: s.max() - s.min())
        rows.append(dict(item=f"appliance_test_mean_within_scenario_range_{c}", value=rng.mean()))
        rows.append(dict(item=f"appliance_test_share_scenarios_zero_range_{c}", value=(rng < 1e-9).mean()))
    # raw-emission view: GT sheet has raw_emissions; derive period from the ratio
    gt = pd.read_excel(PROJECT_ROOT / "Ground Truth" / "ground_truth_appliance.xlsx")
    gt["alt_norm"] = gt["alternative"].astype(str)
    raw = gt.groupby("scenario_id")["raw_emissions"].agg(lambda s: s.max() / s.min() - 1)
    rows.append(dict(item="appliance_all_gt_max_raw_emissions_contrast_within_scenario", value=raw.max()))
    rows.append(dict(item="appliance_all_gt_share_scenarios_with_any_raw_emissions_contrast",
                     value=(raw > 1e-6).mean()))
    rows.append(dict(item="appliance_env_score_gap_per_kwh_peak_vs_offpeak",
                     value=(1.041 - 0.976) / (3.643 - 0.288)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "d9_appliance_env_contrast.csv", index=False)
    return df


def load_cells(variant, arch, model):
    fs = sorted(ABL.glob(f"cell_{variant}_{arch}_{model}_run_*.xlsx"))
    if not fs:
        return None
    return pd.concat([pd.read_excel(f) for f in fs], ignore_index=True)


def main():
    ref, merged = reference_map()
    s1 = section1(merged)
    print(s1.round(4).to_string())

    prm = pd.read_csv(PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv")
    rows, chk, per_scen = [], [], {}
    for model in MODELS:
        for variant, arch in (("control", "AD"), ("no_anchors", "AD"), ("control", "AE")):
            d = load_cells(variant, arch, model)
            if d is None:
                continue
            d = d[~d["failed"].astype(bool)].copy()
            d["ref_dt"] = d["scenario_id"].map(lambda s: ref[int(s)][0])
            d["ref_win"] = d["scenario_id"].map(lambda s: ref[int(s)][1])
            d["pred_norm"] = [cprm._cm.normalize_alternative(str(p), dt) for p, dt in zip(d["pred_top1"], d["ref_dt"])]
            d["top1_current"] = (d["pred_norm"] == d["ref_win"]).astype(float)
            assert (d["ref_dt"] == d["decision_type"]).all()
            per_scen[(model, variant, arch)] = d
            for dt in ["Overall"] + DTYPES:
                s = d if dt == "Overall" else d[d.decision_type == dt]
                pr = s.groupby("run").agg(tau=("kendall_tau", "mean"), top1=("top1", "mean"),
                                          top1_cur=("top1_current", "mean"), n=("scenario_id", "size"),
                                          n_tau_nan=("kendall_tau", lambda x: x.isna().sum()))
                main_ = prm[(prm.model == model) & (prm.architecture == STEM[arch]) & (prm.decision_type == dt)]
                rows.append(dict(model=model, arch="A_D" if arch == "AD" else "A_E", variant=variant,
                                 decision_type=dt, n_runs=len(pr), mean_n_scored=pr.n.mean(),
                                 stored_tau=pr.tau.mean(), stored_tau_sd=pr.tau.std(),
                                 stored_top1=pr.top1.mean(), top1_vs_current_ref=pr.top1_cur.mean(),
                                 mean_tau_nan_scenarios=pr.n_tau_nan.mean(),
                                 main_benchmark_tau=main_.kendall_tau.mean() if variant == "control" else np.nan,
                                 main_benchmark_top1=main_.top1_accuracy.mean() if variant == "control" else np.nan))
                if dt != "Overall":
                    chk.append(dict(model=model, variant=variant, arch=arch, decision_type=dt,
                                    share_scenario_runs_stored_top1_equals_current=(s.top1 == s.top1_current).mean()))
    bt = pd.DataFrame(rows)
    bt.to_csv(OUT / "d9_prompt_ablation_by_type.csv", index=False)
    pd.DataFrame(chk).to_csv(OUT / "d9_prompt_ablation_ref_check.csv", index=False)

    tests = []
    for model in MODELS:
        c = per_scen.get((model, "control", "AD"))
        n = per_scen.get((model, "no_anchors", "AD"))
        if c is None or n is None:
            continue
        for dt in DTYPES:
            for metric, col in (("kendall_tau_stored", "kendall_tau"), ("top1_current_ref", "top1_current")):
                a = c[c.decision_type == dt].groupby("scenario_id")[col].mean()
                b = n[n.decision_type == dt].groupby("scenario_id")[col].mean()
                idx = a.dropna().index.intersection(b.dropna().index)
                x, y = b.loc[idx].values, a.loc[idx].values
                try:
                    p = stats.wilcoxon(x, y, zero_method="wilcox", correction=True, mode="approx").pvalue
                except ValueError:
                    p = np.nan
                tests.append(dict(model=model, decision_type=dt, metric=metric, n=len(idx),
                                  control=y.mean(), no_anchors=x.mean(), diff=x.mean() - y.mean(), p=p))
    te = pd.DataFrame(tests)
    for m in te.metric.unique():
        k = te.metric == m
        te.loc[k, "p_holm"] = holm(te.loc[k, "p"].fillna(1.0).values)
    te.to_csv(OUT / "d9_prompt_ablation_tests.csv", index=False)
    print("done")


if __name__ == "__main__":
    main()
