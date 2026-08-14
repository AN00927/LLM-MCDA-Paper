#!/usr/bin/env python3
"""
failure_inclusive_metrics.py - task P1.2 of the EMS revision plan.

WHY THIS IS NOT THE EXISTING SCRIPT (M4 was optimistic).
`generate_imputed_robustness_tables.py` imputes **0.5 at the criterion-score
level** and then re-runs MAVT aggregation and ranking. That is a different
operation from what D2 specifies, not a different parameter of the same
operation:

  - 0.5-score imputation produces a CONCRETE ranking for the failed scenario.
    That ranking can be right by luck, and 0.5 across all four criteria is a
    highly structured guess, not a random one. It therefore understates what a
    failure costs.
  - D2 imputes at the METRIC level, giving each failed scenario the chance value
    of the metric in question: tau -> 0, Top-1 -> 1/3, Top-2 -> 2/3. That is the
    expected score of a system that produced nothing usable, which is what an
    availability-inclusive number is supposed to mean.

Changing `impute_value=0.5` to anything else does not turn one into the other.

DENOMINATOR (plan D1): this PAIRS with the conditional number, it does not
replace it. Every row reports both:
    S_ok   conditional on successful extraction  (what the paper prints today)
    S_all  all 195 scenarios, failures at chance (availability-inclusive)

Input:  Analysis/per_scenario_metrics_all.csv   (written by cluster_bootstrap_ci.py)
Output: Analysis/failure_inclusive_metrics.{xlsx,md}

Usage:
    python paper_pipeline/failure_inclusive_metrics.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

IN_CSV = PROJECT_ROOT / "Analysis" / "per_scenario_metrics_all.csv"
OUT_XLSX = PROJECT_ROOT / "Analysis" / "failure_inclusive_metrics.xlsx"
OUT_MD = PROJECT_ROOT / "Analysis" / "failure_inclusive_metrics.md"

ARCH_SHORT = {
    "Direct_LLM_Scoring": "A_D",
    "Example-Guided_LLM_Scoring": "A_E",
    "LLM-Parameterized_Reference_Scoring": "A_H",
}

# D2: each failure receives the chance value of its own metric.
CHANCE = {
    "kendall_tau": 0.0,        # expected tau of a random permutation of 3 items
    "top1_accuracy": 1.0 / 3,  # 1 correct of 3 alternatives
    "top2_accuracy": 2.0 / 3,  # correct item in a random pair of 3
}
METRICS = list(CHANCE)

TYPE_TOTALS = {"HVAC": 70, "Appliance": 65, "Shower": 60}
N_ALL = sum(TYPE_TOTALS.values())  # 195


def scenario_universe(df):
    """scenario_id -> decision_type, over the union of everything ever scored."""
    uni = (df[["scenario_id", "decision_type"]]
           .drop_duplicates(subset=["scenario_id"])
           .set_index("scenario_id")["decision_type"])
    return uni


def compute(df, universe):
    rows = []
    all_ids = set(universe.index)

    for (model, arch), cell in df.groupby(["model", "architecture"]):
        for scope in ["Overall"] + list(TYPE_TOTALS):
            if scope == "Overall":
                scope_ids = all_ids
                n_scope = N_ALL
            else:
                scope_ids = {s for s in all_ids if universe[s] == scope}
                n_scope = TYPE_TOTALS[scope]

            per_run_cond = {m: [] for m in METRICS}
            per_run_incl = {m: [] for m in METRICS}
            failed_counts = []

            for run, rdf in cell.groupby("run"):
                sub = rdf[rdf["scenario_id"].isin(scope_ids)]
                n_ok = len(sub)
                n_failed = n_scope - n_ok
                failed_counts.append(n_failed)
                for m in METRICS:
                    vals = sub[m].to_numpy(dtype=float)
                    cond = float(np.mean(vals)) if n_ok else np.nan
                    # Inclusive: the n_failed missing scenarios enter at chance.
                    incl = ((vals.sum() + n_failed * CHANCE[m]) / n_scope
                            if n_scope else np.nan)
                    per_run_cond[m].append(cond)
                    per_run_incl[m].append(incl)

            row = {
                "model": model,
                "architecture": ARCH_SHORT[arch],
                "scope": scope,
                "n_scope": n_scope,
                "mean_failed_per_run": round(float(np.mean(failed_counts)), 2),
                "max_failed_per_run": int(np.max(failed_counts)),
            }
            for m in METRICS:
                c = float(np.nanmean(per_run_cond[m]))
                i = float(np.nanmean(per_run_incl[m]))
                row[f"{m}_conditional"] = round(c, 4)
                row[f"{m}_inclusive"] = round(i, 4)
                row[f"{m}_delta"] = round(i - c, 4)
            rows.append(row)

    return pd.DataFrame(rows)


def main():
    if not IN_CSV.exists():
        print(f"ERROR: {IN_CSV} missing. Run cluster_bootstrap_ci.py first.")
        return 1

    df = pd.read_csv(IN_CSV)
    universe = scenario_universe(df)
    print(f"Scenario universe: {len(universe)} distinct scenarios")
    counts = universe.value_counts().to_dict()
    print(f"  by type: {counts}")
    if len(universe) != N_ALL:
        print(f"  WARNING: expected {N_ALL}. Inclusive denominators use the")
        print(f"           declared totals {TYPE_TOTALS}, not the observed union.")
    print("")

    res = compute(df, universe)
    res = res.sort_values(["architecture", "model", "scope"]).reset_index(drop=True)

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xl:
        res.to_excel(xl, sheet_name="failure_inclusive", index=False)

    overall = res[res["scope"] == "Overall"]
    print("OVERALL (S_ok conditional vs S_all inclusive, D2 chance imputation)")
    print(overall[["model", "architecture", "mean_failed_per_run",
                   "kendall_tau_conditional", "kendall_tau_inclusive", "kendall_tau_delta",
                   "top1_accuracy_conditional", "top1_accuracy_inclusive",
                   "top1_accuracy_delta"]].to_string(index=False))

    moved = overall[overall["kendall_tau_delta"].abs() >= 0.005]
    print("")
    print("Cells whose Overall tau moves by >= 0.005 when failures are included:")
    print(moved[["model", "architecture", "mean_failed_per_run",
                 "kendall_tau_conditional", "kendall_tau_inclusive",
                 "kendall_tau_delta"]].to_string(index=False)
          if len(moved) else "  none")

    # Plan P1.2 explicitly asks for GPT-OSS A_H broken out by decision type.
    gpt = res[(res["model"] == "gptoss") & (res["architecture"] == "A_H")]
    print("")
    print("GPT-OSS A_H by decision type (the concentrated-failure cell):")
    print(gpt[["scope", "n_scope", "mean_failed_per_run", "max_failed_per_run",
               "kendall_tau_conditional", "kendall_tau_inclusive", "kendall_tau_delta",
               "top1_accuracy_conditional", "top1_accuracy_inclusive",
               "top1_accuracy_delta"]].to_string(index=False))

    # Does the headline ordering survive availability-inclusive scoring?
    print("")
    print("Architecture ordering under each denominator:")
    for model in sorted(overall["model"].unique()):
        sub = overall[overall["model"] == model].set_index("architecture")
        for metric in ["kendall_tau", "top1_accuracy"]:
            c = sub[f"{metric}_conditional"]
            i = sub[f"{metric}_inclusive"]
            oc = " > ".join(c.sort_values(ascending=False).index)
            oi = " > ".join(i.sort_values(ascending=False).index)
            flag = "" if oc == oi else "   <-- ORDER CHANGES"
            print(f"  {model:9s} {metric:14s} cond: {oc}   incl: {oi}{flag}")

    md = ["# Failure-inclusive metrics (P1.2)", "",
          "D2 convention: each failed scenario receives the **chance value of its own",
          "metric** -- tau 0, Top-1 1/3, Top-2 2/3. This is imputation at the metric",
          "level, not the 0.5-at-criterion-score level used by",
          "`generate_imputed_robustness_tables.py`; the two are different operations,",
          "not two settings of one operation.", "",
          "D1: the inclusive number **pairs with** the conditional number. Neither",
          "replaces the other.", "",
          "## Overall", "",
          "| Model | Arch | Failed/run | tau S_ok | tau S_all | delta | Top-1 S_ok | Top-1 S_all | delta |",
          "|---|---|---|---|---|---|---|---|---|"]
    for _, r in overall.iterrows():
        md.append(f"| {r['model']} | {r['architecture']} | {r['mean_failed_per_run']} "
                  f"| {r['kendall_tau_conditional']:.4f} | {r['kendall_tau_inclusive']:.4f} "
                  f"| {r['kendall_tau_delta']:+.4f} "
                  f"| {r['top1_accuracy_conditional']:.4f} | {r['top1_accuracy_inclusive']:.4f} "
                  f"| {r['top1_accuracy_delta']:+.4f} |")

    md += ["", "## GPT-OSS A_H by decision type", "",
           "| Scope | n | Failed/run | tau S_ok | tau S_all | delta | Top-1 S_ok | Top-1 S_all | delta |",
           "|---|---|---|---|---|---|---|---|---|"]
    for _, r in gpt.iterrows():
        md.append(f"| {r['scope']} | {r['n_scope']} | {r['mean_failed_per_run']} "
                  f"| {r['kendall_tau_conditional']:.4f} | {r['kendall_tau_inclusive']:.4f} "
                  f"| {r['kendall_tau_delta']:+.4f} "
                  f"| {r['top1_accuracy_conditional']:.4f} | {r['top1_accuracy_inclusive']:.4f} "
                  f"| {r['top1_accuracy_delta']:+.4f} |")
    md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print("")
    print(f"  Wrote {OUT_XLSX.relative_to(PROJECT_ROOT)}")
    print(f"  Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
