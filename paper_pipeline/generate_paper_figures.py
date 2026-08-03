import numpy as np
import pandas as pd

per_run_frames = []
for f in ["deepseek", "gemini", "gptoss", "qwen"]:
    df = pd.read_csv(f"paper/per_run_metrics/per_run_metrics_{f}.csv")
    per_run_frames.append(df)
per_run = pd.concat(per_run_frames, ignore_index=True)


def agg_per_run(arch, model, dt, metric):
    vals = per_run[(per_run["architecture"] == arch) &
                   (per_run["model"] == model) &
                   (per_run["decision_type"] == dt)][metric].dropna().values
    return np.mean(vals) if len(vals) > 0 else np.nan

# === Mappings ===
ARCH_MAP = {
    "Direct_LLM_Scoring": "Pure",
    "Example-Guided_LLM_Scoring": "RAG",
    "LLM-Parameterized_Reference_Scoring": "Hybrid",
}
CRITERION_MAP = {
    "energy_cost_mae": "Energy Cost",
    "environmental_mae": "Environmental",
    "comfort_mae": "Comfort",
    "practicality_mae": "Practicality",
}
MODEL_ORDER = ["gemini", "deepseek", "gptoss", "qwen"]
MODEL_LABELS = {
    "gemini": "Gemini 3.5 Flash",
    "deepseek": "DeepSeek V4 Flash",
    "gptoss": "GPT-OSS 20B",
    "qwen": "Qwen 3.5 9B",
}
COLORS = {
    "gemini": "colorGemini",
    "deepseek": "colorDeepSeek",
    "gptoss": "colorGPTOSS",
    "qwen": "colorQwen",
}
MARKS = {
    "gemini": "*",
    "deepseek": "square*",
    "gptoss": "triangle*",
    "qwen": "diamond*",
}
ARCH_ORDER = ["Pure", "RAG", "Hybrid"]

criterion_mae = {}
for metric_key, crit_label in CRITERION_MAP.items():
    criterion_mae[crit_label] = {}
    for arch_full, arch_short in ARCH_MAP.items():
        for model in MODEL_ORDER:
            val = agg_per_run(arch_full, model, "Overall", metric_key)
            criterion_mae[crit_label].setdefault(arch_short, {})[model] = val

decision_tau = {}
for dt in ["HVAC", "Appliance", "Shower"]:
    decision_tau[dt] = {}
    for arch_full, arch_short in ARCH_MAP.items():
        for model in MODEL_ORDER:
            val = agg_per_run(arch_full, model, dt, "kendall_tau")
            decision_tau[dt].setdefault(arch_short, {})[model] = val

print("=" * 80)
print("CRITERION-LEVEL MAE (Overall)")
print("=" * 80)
for crit in CRITERION_MAP.values():
    print(f"\n{crit}:")
    print(f"  {'Architecture':<10} {'Gemini':>10} {'DeepSeek':>10} {'GPT-OSS':>10} {'Qwen':>10}")
    for arch in ARCH_ORDER:
        vals = [criterion_mae[crit][arch][m] for m in MODEL_ORDER]
        print(f"  {arch:<10} {vals[0]:>10.4f} {vals[1]:>10.4f} {vals[2]:>10.4f} {vals[3]:>10.4f}")

print("\n" + "=" * 80)
print("DECISION-TYPE-LEVEL Kendall's Tau")
print("=" * 80)
for dt in ["HVAC", "Appliance", "Shower"]:
    print(f"\n{dt}:")
    print(f"  {'Architecture':<10} {'Gemini':>10} {'DeepSeek':>10} {'GPT-OSS':>10} {'Qwen':>10}")
    for arch in ARCH_ORDER:
        vals = [decision_tau[dt][arch][m] for m in MODEL_ORDER]
        print(f"  {arch:<10} {vals[0]:>10.4f} {vals[1]:>10.4f} {vals[2]:>10.4f} {vals[3]:>10.4f}")

def coords_str(arch_data, model):
    parts = []
    for arch in ARCH_ORDER:
        parts.append(f"({arch},{arch_data[arch][model]:.4f})")
    return " ".join(parts)

def find_ymax(data, key_type="criterion"):
    all_vals = []
    if key_type == "criterion":
        for crit in data:
            for arch in ARCH_ORDER:
                for model in MODEL_ORDER:
                    all_vals.append(data[crit][arch][model])
    else:
        for dt in data:
            for arch in ARCH_ORDER:
                for model in MODEL_ORDER:
                    all_vals.append(data[dt][arch][model])
    return max(all_vals)

criterion_titles = {
    "Energy Cost": "(a) Energy Cost",
    "Environmental": "(b) Environmental",
    "Comfort": "(c) Comfort",
    "Practicality": "(d) Practicality",
}
decision_titles = {
    "HVAC": "(a) HVAC",
    "Appliance": "(b) Appliance",
    "Shower": "(c) Shower",
}

latex_lines = []

# --- Figure 1: Criterion MAE ---
ymax_mae = find_ymax(criterion_mae, "criterion")
import math
ymax_mae_ceil = math.ceil(ymax_mae * 10) / 10

latex_lines.append(r"\newcommand{\plotCriterionMAEByModel}{%")
latex_lines.append(r"\begin{tikzpicture}")
latex_lines.append(r"\begin{groupplot}[")
latex_lines.append(r"    group style={group size=2 by 2, horizontal sep=1.9cm, vertical sep=1.6cm},")
latex_lines.append(r"    width=0.46\textwidth, height=4.3cm,")
latex_lines.append(r"    symbolic x coords={Pure,RAG,Hybrid},")
latex_lines.append(r"    xtick=data,")
latex_lines.append(r"    xticklabel style={font=\small},")
latex_lines.append(r"    enlarge x limits=0.25,")
latex_lines.append(r"    grid=major, grid style={gray!30}, ymajorgrids=true,")
latex_lines.append(r"    legend style={font=\scriptsize, at={(1.05,1.4)}, anchor=south, legend columns=4},")
latex_lines.append(r"    legend cell align={left},")
latex_lines.append(r"    mark size=2pt,")
latex_lines.append(r"    every axis plot/.append style={thick},")
latex_lines.append(r"]")

for i, crit in enumerate(CRITERION_MAP.values()):
    title = criterion_titles[crit]
    ylabel = "MAE" if i % 2 == 0 else ""
    extra_ylabel = "ylabel={MAE}," if i % 2 == 0 else "ylabel={},"
    latex_lines.append(rf"\nextgroupplot[ylabel={{{ylabel}}}, ymin=0, ymax={ymax_mae_ceil:.1f},")
    latex_lines.append(rf"    title={{\small {title}}}, title style={{font=\small}}]")
    for model in MODEL_ORDER:
        c = coords_str(criterion_mae[crit], model)
        latex_lines.append(rf"\addplot[mark={MARKS[model]}, {COLORS[model]}] coordinates {{{c}}};")
    if i == 0:
        legend_entries = " & ".join([f"{{{MODEL_LABELS[m]}}}" for m in MODEL_ORDER])
        latex_lines.append(rf"\legend{{{legend_entries}}}")

latex_lines.append(r"\end{groupplot}")
latex_lines.append(r"\end{tikzpicture}%")
latex_lines.append(r"}")

latex_lines.append("")

# --- Figure 2: Decision Type tau ---
ymax_tau = find_ymax(decision_tau, "tau")
ymax_tau_ceil = min(math.ceil(ymax_tau * 100) / 100, 1.0)  # tau max is 1.0
all_tau = []
for dt in decision_tau:
    for arch in ARCH_ORDER:
        for model in MODEL_ORDER:
            all_tau.append(decision_tau[dt][arch][model])
ymin_tau = math.floor(min(all_tau) * 10) / 10

latex_lines.append(r"\newcommand{\plotDecisionTypeByModel}{%")
latex_lines.append(r"\begin{tikzpicture}")
latex_lines.append(r"\begin{groupplot}[")
latex_lines.append(r"    group style={group size=3 by 1, vertical sep=1.6cm},")
latex_lines.append(r"    width=0.31\textwidth, height=4.3cm,")
latex_lines.append(r"    symbolic x coords={Pure,RAG,Hybrid},")
latex_lines.append(r"    xtick=data,")
latex_lines.append(r"    xticklabel style={font=\small},")
latex_lines.append(r"    enlarge x limits=0.25,")
latex_lines.append(r"    grid=major, grid style={gray!30}, ymajorgrids=true,")
latex_lines.append(r"    legend style={font=\scriptsize, at={(0.5,1.25)}, anchor=south, legend columns=4},")
latex_lines.append(r"    legend cell align={left},")
latex_lines.append(r"    mark size=2pt,")
latex_lines.append(r"    every axis plot/.append style={thick},")
latex_lines.append(r"]")

for i, dt in enumerate(["HVAC", "Appliance", "Shower"]):
    title = decision_titles[dt]
    ylabel = "Kendall's tau" if i == 0 else ""
    ymin_val = ymin_tau
    latex_lines.append(rf"\nextgroupplot[ylabel={{{ylabel}}}, ymin={ymin_val:.1f}, ymax={ymax_tau_ceil:.2f},")
    latex_lines.append(rf"    title={{\small {title}}}, title style={{font=\small}}]")
    for model in MODEL_ORDER:
        c = coords_str(decision_tau[dt], model)
        latex_lines.append(rf"\addplot[mark={MARKS[model]}, {COLORS[model]}] coordinates {{{c}}};")
    if i == 0:
        legend_entries = " & ".join([f"{{{MODEL_LABELS[m]}}}" for m in MODEL_ORDER])
        latex_lines.append(rf"\legend{{{legend_entries}}}")

latex_lines.append(r"\end{groupplot}")
latex_lines.append(r"\end{tikzpicture}%")
latex_lines.append(r"}")

latex_output = "\n".join(latex_lines) + "\n"

with open("paper/step5_figures.tex", "w") as f:
    f.write(latex_output)

print("\n" + "=" * 80)
print("LaTeX written to paper/step5_figures.tex")
print("=" * 80)
