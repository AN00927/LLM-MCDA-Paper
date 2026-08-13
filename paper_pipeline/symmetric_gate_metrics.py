#!/usr/bin/env python3
"""
symmetric_gate_metrics.py - task P1.3 of the EMS revision plan.

S_int: the scenarios every architecture actually completed. The paper currently
compares architectures on denominators that differ between them -- if A_H skips
23 HVAC scenarios per run and A_D skips none, the two numbers are not measured
over the same population, and the comparison inherits whatever makes those 23
scenarios hard. Restricting all three arms to their common scenarios removes
that confound.

Two gates, because strictness is a real choice and the difference is worth
seeing:

  strict  scored by all three architectures in EVERY run (5/5 each)
  loose   scored by all three architectures in at least ONE run each
          (this is the S_ok_union gate; it is what cross-run recovery buys you)

Per plan D4 this is a ROBUSTNESS CHECK for the supplement, not a headline
replacement. Report N alongside every number.

Input:  Analysis/per_scenario_metrics_all.csv
Output: Analysis/symmetric_gate_metrics.{xlsx,md}

Usage:
    python paper_pipeline/symmetric_gate_metrics.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IN_CSV = PROJECT_ROOT / "Analysis" / "per_scenario_metrics_all.csv"
OUT_XLSX = PROJECT_ROOT / "Analysis" / "symmetric_gate_metrics.xlsx"
OUT_MD = PROJECT_ROOT / "Analysis" / "symmetric_gate_metrics.md"

ARCH_SHORT = {
    "Direct_LLM_Scoring": "A_D",
    "Example-Guided_LLM_Scoring": "A_E",
    "LLM-Parameterized_Reference_Scoring": "A_H",
}
METRICS = ["kendall_tau", "top1_accuracy", "top2_accuracy"]
TYPES = ["HVAC", "Appliance", "Shower"]


def gates_for_model(mdf):
    """Return (strict_ids, loose_ids) for one model."""
    n_runs = mdf["run"].nunique()
    strict, loose = None, None
    for arch, adf in mdf.groupby("architecture"):
        per_arch_runs = adf.groupby("scenario_id")["run"].nunique()
        s = set(per_arch_runs[per_arch_runs == n_runs].index)
        l = set(per_arch_runs.index)
        strict = s if strict is None else (strict & s)
        loose = l if loose is None else (loose & l)
    return strict, loose, n_runs


def metrics_on(mdf, ids, scope):
    """Per-run mean over `ids`, then mean across runs (the D6 estimator)."""
    sub = mdf[mdf["scenario_id"].isin(ids)]
    if scope != "Overall":
        sub = sub[sub["decision_type"] == scope]
    if sub.empty:
        return None
    out = {"n": sub["scenario_id"].nunique()}
    for m in METRICS:
        per_run = sub.groupby("run")[m].mean()
        out[m] = round(float(per_run.mean()), 4)
    return out


def main():
    if not IN_CSV.exists():
        print(f"ERROR: {IN_CSV} missing. Run cluster_bootstrap_ci.py first.")
        return 1
    df = pd.read_csv(IN_CSV)

    rows = []
    print("Gate sizes per model (of 195):")
    for model, mdf in df.groupby("model"):
        strict, loose, n_runs = gates_for_model(mdf)
        print(f"  {model:9s} runs={n_runs}  strict={len(strict):3d}  loose={len(loose):3d}")

        for gate_name, ids in [("all_scenarios", set(mdf["scenario_id"].unique())),
                               ("S_int_loose", loose),
                               ("S_int_strict", strict)]:
            for arch, adf in mdf.groupby("architecture"):
                for scope in ["Overall"] + TYPES:
                    r = metrics_on(adf, ids, scope)
                    if r is None:
                        continue
                    rows.append({
                        "model": model, "architecture": ARCH_SHORT[arch],
                        "gate": gate_name, "scope": scope, **r,
                    })

    res = pd.DataFrame(rows)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xl:
        res.to_excel(xl, sheet_name="symmetric_gate", index=False)

    # The comparison that matters: does anything move when the gate closes?
    piv = res[res["scope"] == "Overall"].pivot_table(
        index=["model", "architecture"], columns="gate",
        values=["kendall_tau", "top1_accuracy", "n"])

    print("")
    print("OVERALL, by gate:")
    print(piv.round(4).to_string())

    print("")
    print("Shift from all-scenarios to S_int_strict (Overall tau):")
    a = res[(res["gate"] == "all_scenarios") & (res["scope"] == "Overall")]
    s = res[(res["gate"] == "S_int_strict") & (res["scope"] == "Overall")]
    merged = a.merge(s, on=["model", "architecture"], suffixes=("_all", "_strict"))
    merged["tau_delta"] = (merged["kendall_tau_strict"]
                           - merged["kendall_tau_all"]).round(4)
    merged["top1_delta"] = (merged["top1_accuracy_strict"]
                            - merged["top1_accuracy_all"]).round(4)
    print(merged[["model", "architecture", "n_all", "n_strict",
                  "kendall_tau_all", "kendall_tau_strict", "tau_delta",
                  "top1_accuracy_all", "top1_accuracy_strict",
                  "top1_delta"]].to_string(index=False))

    print("")
    print("Architecture ordering under the strict gate:")
    for model in sorted(merged["model"].unique()):
        sub = merged[merged["model"] == model].set_index("architecture")
        for metric in ["kendall_tau", "top1_accuracy"]:
            oa = " > ".join(sub[f"{metric}_all"].sort_values(ascending=False).index)
            os_ = " > ".join(sub[f"{metric}_strict"].sort_values(ascending=False).index)
            flag = "" if oa == os_ else "   <-- ORDER CHANGES"
            print(f"  {model:9s} {metric:14s} all: {oa}   strict: {os_}{flag}")

    md = ["# Symmetric-gate metrics, S_int (P1.3)", "",
          "Every architecture restricted to the scenarios all three completed, so the",
          "arms are compared over one population rather than three.", "",
          "- `S_int_strict` -- scored by all three architectures in **every** run",
          "- `S_int_loose` -- scored by all three in **at least one** run each",
          "",
          "Per plan D4 this is a supplement robustness check, not a headline",
          "replacement. N is reported with every number.", "",
          "## Gate sizes", "",
          "| Model | Strict | Loose | of |", "|---|---|---|---|"]
    for model, mdf in df.groupby("model"):
        strict, loose, _ = gates_for_model(mdf)
        md.append(f"| {model} | {len(strict)} | {len(loose)} | 195 |")

    md += ["", "## Overall metrics under the strict gate", "",
           "| Model | Arch | n all | n strict | tau all | tau strict | delta | Top-1 all | Top-1 strict | delta |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in merged.iterrows():
        md.append(f"| {r['model']} | {r['architecture']} | {r['n_all']} | {r['n_strict']} "
                  f"| {r['kendall_tau_all']:.4f} | {r['kendall_tau_strict']:.4f} "
                  f"| {r['tau_delta']:+.4f} "
                  f"| {r['top1_accuracy_all']:.4f} | {r['top1_accuracy_strict']:.4f} "
                  f"| {r['top1_delta']:+.4f} |")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("")
    print(f"  Wrote {OUT_XLSX.relative_to(PROJECT_ROOT)}")
    print(f"  Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
