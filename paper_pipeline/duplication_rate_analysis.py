#!/usr/bin/env python3
"""C6: cost/environmental score-duplication rate analysis.

For each model x architecture x decision type x run, computes the fraction of
scored alternatives (sentinel rows excluded) where the architecture assigned
the identical value to energy_cost and environmental (np.isclose). Reports the
five-run mean and standard deviation per cell, writes per-run values plus
summary to Analysis/duplication_rates_all_runs.xlsx, and renders the paper
table snippet to paper/duplication_table.tex.

The paper table covers A_D and A_E (matching task brief C6). A_H duplication
rates are computed as auxiliary context (its criterion scores are calculator
outputs) and written to the A_H_aux sheet only.
"""
import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from sentinel_utils import is_sentinel  # noqa: E402

N_RUNS = 5
# Column order matches the task brief's run-01 example table.
DECISION_TYPES = ["HVAC", "Shower", "Appliance"]

MODEL_FOLDERS = [
    ("Gemini 3.5 Flash", "Output Files Gemini 3.5 Flash"),
    ("GPT-OSS 20B", "Output Files GPT-OSS 20B"),
    ("Qwen3.5 9B", "Output Files Qwen3.5 9B"),
    ("DeepSeek V4 Flash", "Output Files DeepSeek V4 Flash"),
]

# C6's paper table lists A_D and A_E only.
TABLE_ARCHS = ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring"]
# A_H computed as auxiliary context, not part of the paper table.
ALL_ARCHS = TABLE_ARCHS + ["LLM-Parameterized_Reference_Scoring"]

ARCH_KEYS = {
    "Direct_LLM_Scoring": "A_D",
    "Example-Guided_LLM_Scoring": "A_E",
    "LLM-Parameterized_Reference_Scoring": "A_H",
}

OUT_XLSX = os.path.join(PROJECT_ROOT, "Analysis", "duplication_rates_all_runs.xlsx")
OUT_TEX = os.path.join(PROJECT_ROOT, "paper", "duplication_table.tex")


def duplication_rate(path, decision_type):
    """Return (rate_pct, n_duplicated, n_scored) for one run x decision type.

    A row counts as scored only if neither energy_cost nor environmental is the
    failure sentinel (1928 in int/float/string form). Non-numeric garbage is
    excluded as well: is_sentinel is False for NaN, and np.isclose(NaN, x) is
    False, so a NaN would silently count as non-duplicated.
    """
    df = pd.read_excel(path)
    sub = df[df["decision_type"] == decision_type]
    n_scored = 0
    n_duplicated = 0
    for ec, env in zip(sub["energy_cost"], sub["environmental"]):
        if is_sentinel(ec) or is_sentinel(env):
            continue
        try:
            ec_f, env_f = float(ec), float(env)
        except (TypeError, ValueError):
            continue
        if np.isnan(ec_f) or np.isnan(env_f):
            continue
        n_scored += 1
        if np.isclose(ec_f, env_f):
            n_duplicated += 1
    if n_scored == 0:
        return float("nan"), 0, 0
    return 100.0 * n_duplicated / n_scored, n_duplicated, n_scored


def per_run_frame():
    rows = []
    for model, folder in MODEL_FOLDERS:
        for arch in ALL_ARCHS:
            for run in range(1, N_RUNS + 1):
                path = os.path.join(
                    PROJECT_ROOT, folder, f"{arch}_results_run_{run:02d}.xlsx"
                )
                if not os.path.exists(path):
                    print(f"[WARN] missing {path}")
                    continue
                for dt in DECISION_TYPES:
                    rate, n_dup, n_scored = duplication_rate(path, dt)
                    rows.append({
                        "model": model,
                        "architecture": arch,
                        "run": run,
                        "decision_type": dt,
                        "scored_alternatives": n_scored,
                        "duplicated_alternatives": n_dup,
                        "duplication_rate_pct": round(rate, 4) if not np.isnan(rate) else np.nan,
                    })
    return pd.DataFrame(rows)


def summary_frame(per_run):
    rows = []
    for model, folder in MODEL_FOLDERS:
        for arch in ALL_ARCHS:
            for dt in DECISION_TYPES:
                sub = per_run[
                    (per_run["model"] == model)
                    & (per_run["architecture"] == arch)
                    & (per_run["decision_type"] == dt)
                ]
                vals = sub["duplication_rate_pct"].dropna().values
                if len(vals) == 0:
                    continue
                rows.append({
                    "model": model,
                    "architecture": arch,
                    "decision_type": dt,
                    "n_runs": len(vals),
                    "mean_pct": round(float(np.mean(vals)), 4),
                    "std_pct": round(float(np.std(vals, ddof=1)), 4)
                    if len(vals) > 1 else 0.0,
                    "min_pct": round(float(np.min(vals)), 4),
                    "max_pct": round(float(np.max(vals)), 4),
                })
    return pd.DataFrame(rows)


def _fmt_pct(mean, std):
    return f"{mean:.1f} $\\pm$ {std:.1f}"


def tex_snippet(summary):
    lines = [
        "\\begin{table*}[htbp]",
        "\\begin{threeparttable}",
        "  \\footnotesize",
        "  \\centering",
        "  \\textbf{Cost--environmental score duplication rate}",
        "  \\begin{tabular}{llccc}",
        "    \\toprule",
        "    Model & Architecture & HVAC (\\%) & Shower (\\%) & Appliance (\\%) \\\\",
        "    \\midrule",
    ]
    for model, _ in MODEL_FOLDERS:
        for arch in TABLE_ARCHS:
            cells = []
            for dt in DECISION_TYPES:
                sub = summary[
                    (summary["model"] == model)
                    & (summary["architecture"] == arch)
                    & (summary["decision_type"] == dt)
                ]
                if len(sub) == 0:
                    cells.append("--")
                else:
                    cells.append(_fmt_pct(sub.iloc[0]["mean_pct"], sub.iloc[0]["std_pct"]))
            arch_key = ARCH_KEYS[arch]
            lines.append(f"    {model} & $\\mathcal{{A}}_{{\\text{{{arch_key[2:]}}}}}$ & "
                         + " & ".join(cells) + " \\\\")
            if arch == TABLE_ARCHS[0]:
                lines.append("    \\addlinespace")
    lines += [
        "    \\bottomrule",
        "  \\end{tabular}",
        "  \\begin{tablenotes}",
        "    \\item Five-run mean $\\pm$ standard deviation of the percentage of scored",
        "    alternatives in which the architecture returned the identical value for",
        "    energy cost and environmental impact (equal within floating-point tolerance).",
        "    Alternatives carrying a failed score are excluded before computing the rate.",
        "  \\end{tablenotes}",
        "\\end{threeparttable}",
        "\\caption{Share of scored alternatives in which the architecture assigned",
        "identical energy-cost and environmental scores, by decision type.}",
        "\\label{tab:score_duplication}",
        "\\end{table*}",
        "",
    ]
    return "\n".join(lines)


def main():
    per_run = per_run_frame()
    summary = summary_frame(per_run)

    os.makedirs(os.path.dirname(OUT_XLSX), exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        per_run.to_excel(writer, sheet_name="per_run", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        a_h = summary[summary["architecture"] == "LLM-Parameterized_Reference_Scoring"]
        a_h.to_excel(writer, sheet_name="A_H_aux", index=False)

    with open(OUT_TEX, "w") as fh:
        fh.write(tex_snippet(summary))

    print("Wrote " + OUT_XLSX)
    print("Wrote " + OUT_TEX)

    print("\nMean +/- std duplication rate (percent) per model/arch/decision type:")
    print(f"{'Model':16s} {'Arch':4s} {'HVAC':>14s} {'Shower':>14s} {'Appliance':>14s}")
    for model, _ in MODEL_FOLDERS:
        for arch in TABLE_ARCHS:
            cells = []
            for dt in DECISION_TYPES:
                sub = summary[
                    (summary["model"] == model)
                    & (summary["architecture"] == arch)
                    & (summary["decision_type"] == dt)
                ]
                cells.append(f"{sub.iloc[0]['mean_pct']:.1f}+/-{sub.iloc[0]['std_pct']:.1f}"
                             if len(sub) else "--")
            print(f"{model:16s} {ARCH_KEYS[arch]:4s} {cells[0]:>14s} {cells[1]:>14s} {cells[2]:>14s}")


if __name__ == "__main__":
    main()
