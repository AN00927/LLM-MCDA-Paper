#!/usr/bin/env python3
"""
aggregate_position_bias_results.py

Combines the per-model position-bias control arms into the tables the paper
reports. Reads only files already written by run_position_bias_control.py, so it can
be re-run at any time without touching the API.

The reversed arm is a single run compared against five shipped runs, so every
test here is paired within a shipped run and then summarised across the five.
Reporting the median and the maximum p-value together makes the claim explicit:
the maximum is the weakest of the five comparisons, so "max p < 0.05" means the
effect held against every shipped run, not just a favourable one.

Per-decision-type p-values are Holm-corrected across the three types within each
(model, architecture) pair. Without that correction, four models times three
types is twelve tests and a single borderline cell means nothing.

Usage:
    python "Miscellaneous Scripts/aggregate_position_bias_results.py"
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS, get_output_folder
from sentinel_utils import _atomic_write_xlsx

OUT_DIR = PROJECT_ROOT / "Analysis" / "PositionBias"
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]

# Weakest to strongest on the paper's headline Kendall tau, so the table reads
# as a susceptibility ladder.
MODEL_ORDER = ["qwen", "gptoss", "deepseek", "gemini"]
MODEL_LABELS = {
    "qwen": "Qwen3.5 9B",
    "gptoss": "GPT-OSS 20B",
    "deepseek": "DeepSeek V4 Flash",
    "gemini": "Gemini 3.5 Flash",
}
# A_D only. The A_H order arm lives in run_hybrid_ablation_experiments.py, where it is
# compared against A_H's own five shipped runs rather than against a sample.
ARCH_LABELS = {
    "Direct_LLM_Scoring": "A_D",
}


def holm(pvals):
    """Holm-Bonferroni step-down adjusted p-values, order preserved."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    adj = np.empty(n, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (n - rank) * p[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return adj


def load_paired(model_key):
    folder = PROJECT_ROOT / get_output_folder(model_key) / "position_bias"
    path = folder / f"position_bias_paired_top1_{model_key}.xlsx"
    if not path.exists():
        return None
    df = pd.read_excel(path)
    df["model"] = model_key
    return df


def main():
    frames = [f for f in (load_paired(m) for m in MODEL_ORDER) if f is not None]
    if not frames:
        print("[ERROR] No paired-test workbooks found. Run the control arms first.")
        return
    paired = pd.concat(frames, ignore_index=True)
    paired = paired[paired["comparison"].str.startswith("reversed")]

    rows = []
    for (model, arch), g in paired.groupby(["model", "architecture"]):
        for comparison, gg in g.groupby("comparison"):
            scope = "Overall"
            if "[" in comparison:
                scope = comparison.split("[", 1)[1].rstrip("]")
            b = gg["shipped_right_reversed_wrong"].mean()
            c = gg["shipped_wrong_reversed_right"].mean()
            rows.append({
                "model": model,
                "model_label": MODEL_LABELS.get(model, model),
                "architecture": arch,
                "arch_label": ARCH_LABELS.get(arch, arch),
                "scope": scope,
                "n_scenarios": int(gg["n_paired_scenarios"].iloc[0]),
                "n_shipped_runs": len(gg),
                "shipped_right_reversed_wrong": round(b, 1),
                "shipped_wrong_reversed_right": round(c, 1),
                "net_reversed_gain": round(c - b, 1),
                "mcnemar_p_median": round(gg["mcnemar_exact_p"].median(), 4),
                "mcnemar_p_max": round(gg["mcnemar_exact_p"].max(), 4),
                "top1_choice_agreement": round(gg["top1_choice_agreement"].mean(), 4),
            })

    summary = pd.DataFrame(rows)

    # Holm across the three decision types within each model/architecture pair.
    summary["mcnemar_p_median_holm"] = np.nan
    summary["mcnemar_p_max_holm"] = np.nan
    for (model, arch), idx in summary[summary["scope"] != "Overall"].groupby(
        ["model", "architecture"]
    ).groups.items():
        block = summary.loc[idx]
        summary.loc[idx, "mcnemar_p_median_holm"] = holm(block["mcnemar_p_median"]).round(4)
        summary.loc[idx, "mcnemar_p_max_holm"] = holm(block["mcnemar_p_max"]).round(4)

    summary["_m"] = summary["model"].map({m: i for i, m in enumerate(MODEL_ORDER)})
    summary["_s"] = summary["scope"].map(
        {"Overall": 0, **{d: i + 1 for i, d in enumerate(DECISION_TYPES)}}
    )
    summary = summary.sort_values(["architecture", "_m", "_s"]).drop(columns=["_m", "_s"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "position_bias_summary_all_models.xlsx"
    _atomic_write_xlsx(summary, out_path)
    summary.to_csv(out_path.with_suffix(".csv"), index=False)

    print("POSITION-BIAS CONTROL: REVERSED ALTERNATIVE ORDER vs SHIPPED ORDER")
    print("=" * 104)
    print("Paired McNemar on top-1 correctness, reversed arm against each of five "
          "shipped runs.")
    print("p_max is the weakest of the five comparisons. Per-type p is "
          "Holm-corrected across the three types.\n")

    for arch in ARCH_LABELS:
        sub = summary[summary["architecture"] == arch]
        if sub.empty:
            continue
        print(f"\n{ARCH_LABELS.get(arch, arch)}  ({arch})")
        print(f"  {'model':<20}{'scope':<11}{'n':>5}{'net':>7}"
              f"{'p_med':>9}{'p_max':>9}{'p_holm':>9}{'agree':>8}")
        print("  " + "-" * 78)
        for _, r in sub.iterrows():
            holm_p = r["mcnemar_p_max_holm"]
            holm_s = "     -" if pd.isna(holm_p) else f"{holm_p:>9.4f}"
            print(f"  {r['model_label']:<20}{r['scope']:<11}{r['n_scenarios']:>5}"
                  f"{r['net_reversed_gain']:>+7.1f}"
                  f"{r['mcnemar_p_median']:>9.4f}{r['mcnemar_p_max']:>9.4f}"
                  f"{holm_s}{r['top1_choice_agreement']:>8.3f}")

    print("\n\nDIRECTION OF EFFECT, OVERALL, BY ARCHITECTURE")
    print("=" * 104)
    ov = summary[summary["scope"] == "Overall"]
    for arch in ARCH_LABELS:
        s = ov[ov["architecture"] == arch]
        if s.empty:
            continue
        neg = int((s["net_reversed_gain"] < 0).sum())
        sig = int((s["mcnemar_p_max"] < 0.05).sum())
        print(f"  {ARCH_LABELS.get(arch, arch):<5} reversed arm worse in "
              f"{neg}/{len(s)} models; significant against every shipped run in "
              f"{sig}/{len(s)}")

    print(f"\n[OK] Wrote {out_path.name} (+ .csv) to {OUT_DIR}")


if __name__ == "__main__":
    main()
