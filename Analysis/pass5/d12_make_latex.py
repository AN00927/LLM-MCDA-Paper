#!/usr/bin/env python3
"""
d12_make_latex.py -- renders the proposed D9/D12 supplement tables from the
Analysis/pass5 CSVs into Analysis/pass5/d9_d12_latex_tables.tex (proposal text
only; nothing is inserted into the paper or supplement). READ-ONLY otherwise.
"""

from pathlib import Path

import pandas as pd

A = Path(__file__).resolve().parent
MODELS = [("gemini", "Gemini"), ("deepseek", "DeepSeek"), ("gptoss", "GPT-OSS"), ("qwen", "Qwen")]
AR = {"A_D": r"$\mathcal{A}_{\text{D}}$", "A_E": r"$\mathcal{A}_{\text{E}}$", "A_H": r"$\mathcal{A}_{\text{H}}$"}
DT = ["HVAC", "Appliance", "Shower"]


def f(x, d=3):
    s = f"{x:.{d}f}"
    return s.replace("-", "$-$") if x < 0 else s


out = []

# ---- ablation by type ----
bt = pd.read_csv(A / "d9_prompt_ablation_by_type.csv")
out.append(r"""% ---- D9: no-anchors prompt ablation by decision type ----
\begin{table*}[htbp]
\centering
\footnotesize
\caption{Prompt ablation by decision type: Kendall's $\tau$ and Top-1 accuracy (\%) for the $\mathcal{A}_{\text{D}}$ control, $\mathcal{A}_{\text{D}}$ without anchors, and the $\mathcal{A}_{\text{E}}$ control}
\label{tab:prompt_ablation_bytype}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{ll ccc ccc}
\toprule
& & \multicolumn{3}{c}{Kendall's $\tau$} & \multicolumn{3}{c}{Top-1 (\%)} \\
\cmidrule(lr){3-5}\cmidrule(lr){6-8}
Model & Cell & HVAC & Appliance & Shower & HVAC & Appliance & Shower \\
\midrule""")
for mk, ml in MODELS:
    for arch, var, lab in (("A_D", "control", AR["A_D"] + " control"), ("A_D", "no_anchors", AR["A_D"] + r" no\_anchors"),
                           ("A_E", "control", AR["A_E"] + " control")):
        s = bt[(bt.model == mk) & (bt.arch == arch) & (bt.variant == var)].set_index("decision_type")
        taus = " & ".join(f(s.loc[d, "stored_tau"]) for d in DT)
        tops = " & ".join(f"{100 * s.loc[d, 'top1_vs_current_ref']:.1f}" for d in DT)
        out.append(f"{ml if var == 'control' and arch == 'A_D' else ''} & {lab} & {taus} & {tops} \\\\")
    out.append(r"\addlinespace" if mk != "qwen" else "")
out.append(r"""\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table*}
""")

# ---- ensemble ----
en = pd.read_csv(A / "d12_ensemble.csv")
out.append(r"""% ---- D12a: five-run score ensemble ----
\begin{table}[htbp]
\centering
\footnotesize
\caption{Five-run score ensemble against the per-run mean: Kendall's $\tau$ by model, architecture and decision type}
\label{tab:score_ensemble}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{ll cc cc cc cc}
\toprule
& & \multicolumn{2}{c}{Overall} & \multicolumn{2}{c}{HVAC} & \multicolumn{2}{c}{Appliance} & \multicolumn{2}{c}{Shower} \\
\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}
Model & Arch. & Per-run & Ens. & Per-run & Ens. & Per-run & Ens. & Per-run & Ens. \\
\midrule""")
for mk, ml in MODELS:
    for arch in ("A_D", "A_E"):
        s = en[(en.model == mk) & (en.arch == arch)].set_index("decision_type")
        cells = " & ".join(f"{f(s.loc[d, 'perrun_tau'])} & {f(s.loc[d, 'ens_tau'])}" for d in ["Overall"] + DT)
        out.append(f"{ml if arch == 'A_D' else ''} & {AR[arch]} & {cells} \\\\")
out.append(r"""\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
""")

# ---- regret ----
rg = pd.read_csv(A / "d12_regret_summary.csv")
out.append(r"""% ---- D12b: decision regret ----
\begin{table}[htbp]
\centering
\footnotesize
\caption{Decision regret: reference MAVT value lost by the alternative each architecture ranks first, mean per scenario}
\label{tab:decision_regret}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{ll cccc c}
\toprule
Model & Arch. & Overall & HVAC & Appliance & Shower & Given a miss \\
\midrule""")
for mk, ml in MODELS:
    for arch in ("A_D", "A_E", "A_H"):
        s = rg[(rg.model == mk) & (rg.arch == arch)].set_index("decision_type")
        cells = " & ".join(f"{s.loc[d, 'mean_regret']:.4f}" for d in ["Overall"] + DT)
        out.append(f"{ml if arch == 'A_D' else ''} & {AR[arch]} & {cells} & {s.loc['Overall', 'mean_regret_given_miss']:.4f} \\\\")
    out.append(r"\addlinespace" if mk != "qwen" else "")
rp = rg[(rg.model == "gemini") & (rg.arch == "A_D")].set_index("decision_type")
cells = " & ".join(f"{rp.loc[d, 'random_pick_regret']:.4f}" for d in ["Overall"] + DT)
out.append(r"\midrule")
out.append(f"\\multicolumn{{2}}{{l}}{{Random pick}} & {cells} & -- \\\\")
out.append(r"""\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
""")

# ---- ties ----
ti = pd.read_csv(A / "d12_ties_summary.csv")
out.append(r"""% ---- D12c: ties at the top weighted score ----
\begin{table}[htbp]
\centering
\footnotesize
\caption{Ties at the top weighted score and their effect on Top-1 accuracy (\%)}
\label{tab:top_ties}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{ll ccccc}
\toprule
Model & Arch. & Top tie & By input order & Top-1 reported & Top-1 random break & Ties as misses \\
\midrule""")
for mk, ml in MODELS:
    for arch in ("A_D", "A_E"):
        s = ti[(ti.model == mk) & (ti.arch == arch) & (ti.decision_type == "Overall")].iloc[0]
        out.append(f"{ml if arch == 'A_D' else ''} & {AR[arch]} & {100 * s.top_tie_share:.1f} & "
                   f"{100 * s.top_tie_input_order_share:.1f} & {100 * s.top1_shipped:.1f} & "
                   f"{100 * s.top1_random_tiebreak:.1f} & {100 * s.top1_ties_as_miss:.1f} \\\\")
out.append(r"""\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
""")

# ---- tokens ----
tk = pd.read_csv(A / "d12_tokens.csv")
out.append(r"""% ---- D12d: input and output tokens ----
\begin{table}[htbp]
\centering
\footnotesize
\caption{Input and output tokens per run (thousands), mean of five runs}
\label{tab:tokens_in_out}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{l cc cc cc cc}
\toprule
 & \multicolumn{2}{c}{Gemini} & \multicolumn{2}{c}{DeepSeek} & \multicolumn{2}{c}{GPT-OSS} & \multicolumn{2}{c}{Qwen} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}
Architecture & In & Out & In & Out & In & Out & In & Out \\
\midrule""")
for arch in ("A_D", "A_E", "A_H"):
    cells = []
    for mk, _ in MODELS:
        s = tk[(tk.model == mk) & (tk.arch == arch)].iloc[0]
        cells.append(f"{s.input_tokens_per_run / 1000:.1f} & {s.output_tokens_per_run / 1000:.1f}")
    out.append(f"{AR[arch]} & " + " & ".join(cells) + r" \\")
out.append(r"""\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
""")

(A / "d9_d12_latex_tables.tex").write_text("\n".join(out), encoding="utf-8")
print("wrote d9_d12_latex_tables.tex")
