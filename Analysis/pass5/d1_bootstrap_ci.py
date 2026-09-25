#!/usr/bin/env python3
"""
d1_bootstrap_ci.py -- Pass 5, item D1: 95% paired bootstrap CIs for the
extraction gain over the lookup baselines (A_H minus baseline), per model and
decision type. Reads only d1_baseline_per_scenario.csv (written by
d1_lookup_baseline.py) and the per-run A_H arm of
Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx. No API calls.

Basis: for each scenario, A_H's metric is averaged over the runs in which that
scenario succeeded (failed scenario-runs excluded, sentinel detection done by
the ablation harness), then paired with the deterministic baseline's metric on
the same scenario. Scenarios are resampled with replacement (10,000 draws,
fixed seed). Never pooled across models.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Analysis" / "pass5"
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
B = 10_000

base = pd.read_csv(OUT / "d1_baseline_per_scenario.csv")
ps = pd.read_excel(ROOT / "Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx", sheet_name="per_scenario")
ps["failed"] = ps["failed"].astype(bool)
rows = []
for mk_i, mk in enumerate(MODELS):
    pr = ps[(ps.model == mk) & (ps.arm == "extracted_per_run") & (~ps.failed)]
    rm = pr.groupby(["scenario_id", "decision_type"])[["kendall_tau", "top1", "mae"]].mean().reset_index()
    for b_i, bl in enumerate(["LU", "FD+time", "LU-corpus", "LU-literal"]):
        bb = base[base.baseline == bl].set_index("scenario_id")
        for s_i, scope in enumerate(["Overall", "HVAC", "Appliance", "Shower"]):
            x = rm if scope == "Overall" else rm[rm.decision_type == scope]
            for m_i, metric in enumerate(["kendall_tau", "top1"]):
                d = (x[metric].values - bb.loc[x.scenario_id, metric].values)
                rng = np.random.default_rng(20260925 + 1000 * mk_i + 100 * b_i + 10 * s_i + m_i)
                idx = rng.integers(0, len(d), size=(B, len(d)))
                boots = d[idx].mean(axis=1)
                rows.append({"model": mk, "baseline": bl, "scope": scope, "metric": metric,
                             "n_scenarios": len(d), "mean_gain_ah_minus_baseline": d.mean(),
                             "ci95_lo": np.percentile(boots, 2.5), "ci95_hi": np.percentile(boots, 97.5)})
ci = pd.DataFrame(rows)
ci.to_csv(OUT / "d1_bootstrap_ci_gain.csv", index=False)
print(ci[ci.baseline.isin(["LU", "FD+time"])].round(3).to_string(index=False))
