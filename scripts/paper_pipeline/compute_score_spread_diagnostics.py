#!/usr/bin/env python3
"""
compute_score_spread_diagnostics.py -- separates how a scoring architecture
orders the alternatives on each criterion from how far apart it places them,
and converts criterion errors to physical units.

Three analyses, all READ-ONLY on the per-run output files (no API calls):

1. Rescaling (A_D, A_E). For each scenario and criterion, map the model's
   scores affinely onto the reference's within-scenario range, which keeps
   the model's own order (a criterion the model scored flat takes the
   midpoint), re-aggregate with the design weights and recompute Kendall's
   tau and Top-1. Failed scenarios keep tau = 0 / Top-1 = 0 as in the paper.
   The rescaling borrows the reference's ranges, so it is a diagnostic, not a
   deployable correction.
2. Within-criterion order (A_D, A_E). Per scenario and criterion: Kendall
   tau-b between the model's and the reference's scores across the three
   alternatives, and both within-scenario ranges. Failed scores and scenarios
   in which either side scores all three alternatives alike are excluded from
   the tau means.
3. Physical-unit error (A_D, A_E, A_H). Absolute Energy Cost and
   Environmental Impact score errors multiplied by the width of the decision
   type's normalization range; a failed scenario takes the expected error of
   a uniform random guess, as in the headline MAE.

Outputs (Combined Metrics/):
    score_rescaling.csv            model, run, architecture, variant, decision_type, tau, top1
    criterion_order.csv            architecture, model, decision_type, criterion,
                                   tau_b, model_range, reference_range, range_ratio, flat_share
    criterion_order_overall.csv    architecture, model, criterion, tau_b, flat_share
    criterion_error_physical.csv   architecture, model, quantity, unit, mean_error

Main text Results 5.1 and Discussion 6.1, Supplementary Tables
tab:rescaling and tab:mae_physical.

Usage:
    python scripts/paper_pipeline/compute_score_spread_diagnostics.py
    python scripts/paper_pipeline/compute_score_spread_diagnostics.py --output-dir local_manuscripts/Analysis
"""
import argparse
import contextlib
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts" / "analysis") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "analysis"))
from common.paths import repository_path  # noqa: E402
from common.model_config import get_output_folder  # noqa: E402
warnings.filterwarnings("ignore")

with contextlib.redirect_stdout(io.StringIO()):
    import evaluate_architecture_metrics as E  # noqa: E402
warnings.filterwarnings("ignore")  # E resets the filter to "default" on import

MODELS = {"deepseek": "DeepSeek", "gemini": "Gemini", "gptoss": "GPT-OSS", "qwen": "Qwen"}
SCORING_ARCHS = ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring"]
ALL_ARCHS = SCORING_ARCHS + ["LLM-Parameterized_Reference_Scoring"]
N_RUNS = 5
CRITERIA = list(E.CRITERIA)

# Width (x_max - x_min) of each physical criterion's normalization range, as
# set in the calculators and printed in the main text's normalization-bounds
# table: HVAC calculators/HVACGroundTruthCalculator.py ('energy_cost',
# 'environmental' min/max), Appliance ENERGY_COST_BOUNDS / ENVIRONMENTAL_BOUNDS,
# Shower calculators/ShowerGroundTruthCalculator.py.
RANGE_WIDTH = {
    "HVAC": {"energy_cost": 2.81 - 0.40, "environmental": 15.40 - 2.05},
    "Appliance": {"energy_cost": 0.774 - 0.028, "environmental": 3.643 - 0.288},
    "Shower": {"energy_cost": 1.07 - 0.13, "environmental": 45.0 - 6.0},
}

DEFAULT_OUTPUT_DIR = repository_path("Combined Metrics")


def load_run(gt_lookup, gt_id_lookup, model_key, arch, run):
    path = PROJECT_ROOT / get_output_folder(model_key) / f"{arch}_results_run_{run:02d}.xlsx"
    with contextlib.redirect_stdout(io.StringIO()):
        df = E.load_architecture(str(path), arch)
        merged, _ = E.match_scenarios(gt_lookup, gt_id_lookup, df, arch)
    return merged


def is_failed(value):
    return pd.isna(value) or E.is_sentinel(value)


def rescale(merged):
    """Map each criterion's scores onto the reference's within-scenario range."""
    df = merged.copy()
    for _, idx in df.groupby("arch_scenario_id").groups.items():
        for c in CRITERIA:
            a = pd.to_numeric(df.loc[idx, f"arch_{c}"], errors="coerce")
            g = pd.to_numeric(df.loc[idx, f"gt_{c}"], errors="coerce")
            if a.isna().any() or E.is_sentinel(a.iloc[0]):
                continue
            lo, hi = g.min(), g.max()
            if a.max() == a.min():
                df.loc[idx, f"arch_{c}"] = (lo + hi) / 2
            else:
                df.loc[idx, f"arch_{c}"] = lo + (a - a.min()) / (a.max() - a.min()) * (hi - lo)
    return E.recompute_arch_ranks(df)


def ranking_rows(merged, model, run, arch, variant):
    with contextlib.redirect_stdout(io.StringIO()):
        per_scenario = E.per_scenario_ranking_metrics(merged)
    rows = []
    for dtype, sub in [("Overall", per_scenario)] + list(per_scenario.groupby("decision_type")):
        rows.append({"model": model, "run": run, "architecture": arch, "variant": variant,
                     "decision_type": dtype, "tau": sub["kendall_tau"].mean(),
                     "top1": sub["top1"].mean()})
    return rows


def order_rows(merged, model, run, arch):
    rows = []
    for _, g in merged.groupby("arch_scenario_id"):
        dtype = g["decision_type"].iloc[0]
        for c in CRITERIA:
            x = pd.to_numeric(g[f"arch_{c}"], errors="coerce")
            y = pd.to_numeric(g[f"gt_{c}"], errors="coerce")
            if x.isna().any() or E.is_sentinel(x.iloc[0]):
                continue
            tau = kendalltau(x, y).statistic if (x.nunique() > 1 and y.nunique() > 1) else np.nan
            rows.append({"architecture": arch, "model": model, "run": run, "decision_type": dtype,
                         "criterion": c, "tau_b": tau, "model_range": x.max() - x.min(),
                         "reference_range": y.max() - y.min(), "flat": float(x.nunique() == 1)})
    return rows


def physical_rows(merged, model, run, arch):
    rows = []
    for _, r in merged.iterrows():
        dtype = r["decision_type"]
        for c in ("energy_cost", "environmental"):
            x = pd.to_numeric(r[f"arch_{c}"], errors="coerce")
            y = pd.to_numeric(r[f"gt_{c}"], errors="coerce")
            err = (y ** 2 + (1 - y) ** 2) / 2 if is_failed(x) else abs(x - y)
            rows.append({"architecture": arch, "model": model, "run": run, "decision_type": dtype,
                         "criterion": c, "physical_error": err * RANGE_WIDTH[dtype][c]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    with contextlib.redirect_stdout(io.StringIO()):
        gt = E.load_ground_truth(E._build_config("gemini"))
    gt_lookup, gt_id_lookup = E.build_gt_lookup(gt), E.build_gt_id_lookup(gt)

    ranking, order, physical = [], [], []
    for arch in ALL_ARCHS:
        for key, model in MODELS.items():
            for run in range(1, N_RUNS + 1):
                merged = load_run(gt_lookup, gt_id_lookup, key, arch, run)
                physical += physical_rows(merged, model, run, arch)
                if arch in SCORING_ARCHS:
                    ranking += ranking_rows(merged, model, run, arch, "as_scored")
                    ranking += ranking_rows(rescale(merged), model, run, arch, "rescaled")
                    order += order_rows(merged, model, run, arch)

    ranking = pd.DataFrame(ranking)
    ranking.to_csv(out / "score_rescaling.csv", index=False)

    order = pd.DataFrame(order)
    by_type = (order.groupby(["architecture", "model", "decision_type", "criterion"])
               .agg(tau_b=("tau_b", "mean"), model_range=("model_range", "mean"),
                    reference_range=("reference_range", "mean"), flat_share=("flat", "mean"))
               .reset_index())
    by_type["range_ratio"] = by_type["model_range"] / by_type["reference_range"]
    by_type.to_csv(out / "criterion_order.csv", index=False)
    overall = (order.groupby(["architecture", "model", "criterion"])
               .agg(tau_b=("tau_b", "mean"), flat_share=("flat", "mean")).reset_index())
    overall.to_csv(out / "criterion_order_overall.csv", index=False)

    physical = pd.DataFrame(physical)
    groups = [
        ("Energy Cost", "USD per alternative", physical["criterion"] == "energy_cost"),
        ("Environmental Impact (Thermostat, Appliance)", "lb CO2 per alternative",
         (physical["criterion"] == "environmental") & (physical["decision_type"] != "Shower")),
        ("Environmental Impact (Shower)", "gallons per alternative",
         (physical["criterion"] == "environmental") & (physical["decision_type"] == "Shower")),
    ]
    phys_rows = []
    for quantity, unit, mask in groups:
        means = physical[mask].groupby(["architecture", "model"])["physical_error"].mean()
        for (arch, model), value in means.items():
            phys_rows.append({"architecture": arch, "model": model, "quantity": quantity,
                              "unit": unit, "mean_error": value})
    pd.DataFrame(phys_rows).to_csv(out / "criterion_error_physical.csv", index=False)

    pd.set_option("display.width", 200)
    print(ranking[ranking["decision_type"] == "Overall"]
          .groupby(["architecture", "model", "variant"])["tau"].mean().unstack().round(3))
    print(overall.pivot_table(index=["architecture", "model"], columns="criterion", values="tau_b").round(3))
    print(pd.DataFrame(phys_rows).pivot_table(index=["quantity", "model"], columns="architecture",
                                              values="mean_error").round(3))
    print(f"\nWrote score_rescaling.csv, criterion_order.csv, criterion_order_overall.csv, "
          f"criterion_error_physical.csv to {out}")


if __name__ == "__main__":
    main()
