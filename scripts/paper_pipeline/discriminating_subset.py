#!/usr/bin/env python3
"""
discriminating_subset.py - task P1.6 of the EMS revision plan.

S_disc = the Test scenarios where the comfort-criterion argmax DIFFERS from the
reference MAVT winner. These are the scenarios you cannot get right by simply
maximising comfort.

WHY IT MATTERS. paper/single_criterion_recovery.tex shows that comfort alone
recovers the reference winner in 85.7% of HVAC and 92.3% of Appliance
scenarios. An architecture that has merely learned "pick the most comfortable
option" therefore scores well on most of the corpus without doing any
multi-criteria reasoning. S_disc removes that shortcut and asks how the three
architectures do when comfort-following is actively wrong.

DEFINITION. Ranking by gt_comfort alone, ties broken by first occurrence (same
convention as single_criterion_recovery.tex), a scenario is in S_disc iff the
argmax alternative is not the alternative with gt_rank == 1.

METRICS. tau and Top-1 recomputed on S_disc with the paper's estimator: per-run
mean over the S_disc scenarios that run actually scored, then mean across runs.
Failed scenarios are already absent from per_scenario_metrics_all.csv, so the
denominator is the scored subset of S_disc and is reported per cell.

Inputs:  Analysis/per_scenario_metrics_all.csv  (built by cluster_bootstrap_ci.py)
         Ground Truth/ground_truth_*.xlsx       (via the project matcher)
Output:  Analysis/discriminating_subset.{xlsx,md}

Usage:
    python paper_pipeline/discriminating_subset.py
"""

import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS  # noqa: E402

_cm_path = PROJECT_ROOT / "Miscellaneous Scripts" / "core-automation" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("evaluate_architecture_metrics", _cm_path)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

PER_SCENARIO_CSV = PROJECT_ROOT / "Analysis" / "per_scenario_metrics_all.csv"
OUT_XLSX = PROJECT_ROOT / "Analysis" / "discriminating_subset.xlsx"
OUT_MD = PROJECT_ROOT / "Analysis" / "discriminating_subset.md"

ARCH_SHORT = {
    "Direct_LLM_Scoring": "A_D",
    "Example-Guided_LLM_Scoring": "A_E",
    "LLM-Parameterized_Reference_Scoring": "A_H",
}
ARCH_ORDER = ["A_D", "A_E", "A_H"]
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]


def build_sdisc():
    """Return (DataFrame of per-scenario flags, set of S_disc scenario ids)."""
    model_key = sorted(MODEL_SPECS)[0]
    config = _cm._build_config(model_key)
    folder = Path(config["output_csv"]).parent
    path = folder / "LLM-Parameterized_Reference_Scoring_results_run_01.xlsx"
    if not path.exists():
        raise SystemExit(f"Missing carrier run file: {path}")

    gt_by_type = _cm.load_ground_truth(config)
    arch_df = _cm.load_architecture(path, "carrier")
    merged, _ = _cm.match_scenarios(_cm.build_gt_lookup(gt_by_type),
                                    _cm.build_gt_id_lookup(gt_by_type),
                                    arch_df, "carrier")
    rows = []
    for sid, sc in merged.groupby("arch_scenario_id"):
        sc = sc.reset_index(drop=True)
        comfort = sc["gt_comfort"].astype(float).values
        gt_rank = sc["gt_rank"].astype(float).values
        # argmax with first-occurrence tie-break
        comfort_win = int(np.argmax(comfort))
        gt_win = int(np.argmin(gt_rank))
        rows.append({
            "scenario_id": int(sid),
            "decision_type": sc["decision_type"].iloc[0],
            "comfort_argmax_alt": sc.loc[comfort_win, "norm_alternative"],
            "reference_winner_alt": sc.loc[gt_win, "norm_alternative"],
            "comfort_tied": bool(np.sum(comfort == comfort.max()) > 1),
            "in_S_disc": sc.loc[comfort_win, "norm_alternative"] != sc.loc[gt_win, "norm_alternative"],
        })
    flags = pd.DataFrame(rows).sort_values("scenario_id")
    if len(flags) != 195:
        raise SystemExit(f"Expected 195 scenarios, got {len(flags)}")
    return flags


def metrics_on(df, sids):
    """Per-run mean over `sids`, then mean across runs, per model x arch x scope."""
    sub = df[df["scenario_id"].isin(sids)]
    rows = []
    for (model, arch), cell in sub.groupby(["model", "architecture"]):
        per_run = cell.groupby("run").agg(
            tau=("kendall_tau", "mean"),
            top1=("top1_accuracy", "mean"),
            n=("scenario_id", "nunique"))
        rows.append({
            "model": model,
            "architecture": ARCH_SHORT.get(arch, arch),
            "tau": float(per_run["tau"].mean()),
            "top1": float(per_run["top1"].mean()),
            "n_scored_mean": float(per_run["n"].mean()),
            "n_runs": int(len(per_run)),
        })
    return pd.DataFrame(rows)


def main():
    warnings.filterwarnings("ignore")
    print("P1.6 discriminating subset S_disc")
    print("=" * 64)

    flags = build_sdisc()
    counts = []
    for dt in DECISION_TYPES:
        s = flags[flags["decision_type"] == dt]
        counts.append({
            "decision_type": dt,
            "n_total": int(len(s)),
            "n_S_disc": int(s["in_S_disc"].sum()),
            "share_S_disc": float(s["in_S_disc"].mean()),
            "n_comfort_ties": int(s["comfort_tied"].sum()),
        })
    counts.append({
        "decision_type": "Overall",
        "n_total": int(len(flags)),
        "n_S_disc": int(flags["in_S_disc"].sum()),
        "share_S_disc": float(flags["in_S_disc"].mean()),
        "n_comfort_ties": int(flags["comfort_tied"].sum()),
    })
    counts = pd.DataFrame(counts)
    print(counts.to_string(index=False))

    per_scen = pd.read_csv(PER_SCENARIO_CSV)
    sdisc_ids = set(flags.loc[flags["in_S_disc"], "scenario_id"])
    all_ids = set(flags["scenario_id"])

    full = metrics_on(per_scen, all_ids).rename(
        columns={"tau": "tau_full", "top1": "top1_full",
                 "n_scored_mean": "n_full"})
    disc = metrics_on(per_scen, sdisc_ids).rename(
        columns={"tau": "tau_Sdisc", "top1": "top1_Sdisc",
                 "n_scored_mean": "n_Sdisc"})
    comb = full.merge(disc, on=["model", "architecture"], suffixes=("", "_d"))
    comb["d_tau"] = comb["tau_Sdisc"] - comb["tau_full"]
    comb["d_top1"] = comb["top1_Sdisc"] - comb["top1_full"]
    comb["arch_order"] = comb["architecture"].map({a: i for i, a in enumerate(ARCH_ORDER)})
    comb = comb.sort_values(["model", "arch_order"]).drop(columns=["arch_order", "n_runs_d"])

    # Per decision type on S_disc
    bytype_rows = []
    for dt in DECISION_TYPES:
        ids = set(flags.loc[flags["in_S_disc"] & (flags["decision_type"] == dt), "scenario_id"])
        if not ids:
            continue
        m = metrics_on(per_scen[per_scen["decision_type"] == dt], ids)
        m["decision_type"] = dt
        bytype_rows.append(m)
    bytype = pd.concat(bytype_rows, ignore_index=True) if bytype_rows else pd.DataFrame()
    if not bytype.empty:
        bytype["arch_order"] = bytype["architecture"].map({a: i for i, a in enumerate(ARCH_ORDER)})
        bytype = bytype.sort_values(["decision_type", "model", "arch_order"]).drop(columns="arch_order")

    OUT_XLSX.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        counts.to_excel(xw, sheet_name="S_disc_counts", index=False)
        comb.to_excel(xw, sheet_name="Overall_full_vs_Sdisc", index=False)
        if not bytype.empty:
            bytype.to_excel(xw, sheet_name="Sdisc_by_type", index=False)
        flags.to_excel(xw, sheet_name="scenario_flags", index=False)
    print(f"\n  Wrote {OUT_XLSX.relative_to(PROJECT_ROOT)}")

    L = []
    L.append("# P1.6 - discriminating subset S_disc\n")
    L.append("S_disc = scenarios where the comfort-criterion argmax differs from the")
    L.append("reference MAVT winner. Ties in comfort broken by first occurrence.\n")
    L.append("## Size of S_disc\n")
    L.append("| Decision type | n total | n in S_disc | share | comfort ties |")
    L.append("|---|---|---|---|---|")
    for _, r in counts.iterrows():
        L.append("| %s | %d | %d | %.1f%% | %d |" % (
            r["decision_type"], r["n_total"], r["n_S_disc"],
            100 * r["share_S_disc"], r["n_comfort_ties"]))
    L.append("")
    L.append("## Full corpus vs S_disc, per model and architecture\n")
    L.append("| Model | Arch | tau full | tau S_disc | d tau | Top-1 full | Top-1 S_disc | d Top-1 | n S_disc scored |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in comb.iterrows():
        L.append("| %s | %s | %.4f | %.4f | %+.4f | %.4f | %.4f | %+.4f | %.1f |" % (
            r["model"], r["architecture"], r["tau_full"], r["tau_Sdisc"], r["d_tau"],
            r["top1_full"], r["top1_Sdisc"], r["d_top1"], r["n_Sdisc"]))
    if not bytype.empty:
        L.append("")
        L.append("## S_disc by decision type\n")
        L.append("| Decision type | Model | Arch | tau | Top-1 | n scored |")
        L.append("|---|---|---|---|---|---|")
        for _, r in bytype.iterrows():
            L.append("| %s | %s | %s | %.4f | %.4f | %.1f |" % (
                r["decision_type"], r["model"], r["architecture"],
                r["tau"], r["top1"], r["n_scored_mean"]))

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")
    print("\n" + "\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
