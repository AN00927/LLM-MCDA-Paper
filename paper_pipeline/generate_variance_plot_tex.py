#!/usr/bin/env python3
"""Assemble the complete Run-to-Run Variance subsection as a self-contained .tex file."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_boxplot_tex import generate_boxplot_block
from generate_violin_tex import generate_violin_block

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "paper" / "per_run_metrics"
OUTPUT_FILE = OUTPUT_DIR / "variance_plots.tex"

METRICS = [
    {
        "key": "kendall_tau",
        "ylabel": "Kendall's $\\tau$",
        "ymin": -0.15,
        "ymax": 1.05,
        "box_caption": "Distribution of Kendall's $\\tau$ across five independent runs per model. Box plots show median, quartiles, and whiskers.",
        "box_label": "fig:box_tau",
        "violin_caption": "Violin plots of Kendall's $\\tau$ across five runs.",
        "violin_label": "fig:violin_tau",
    },
    {
        "key": "overall_mae",
        "ylabel": "Overall MAE",
        "ymin": 0,
        "ymax": 0.35,
        "box_caption": "Distribution of Overall MAE across five independent runs per model.",
        "box_label": "fig:box_mae",
        "violin_caption": "Violin plots of Overall MAE across five runs.",
        "violin_label": "fig:violin_mae",
    },
    {
        "key": "top1_accuracy",
        "ylabel": "Top-1 Accuracy (\\%)",
        "ymin": 20,
        "ymax": 100,
        "box_caption": "Distribution of Top-1 Accuracy across five independent runs per model.",
        "box_label": "fig:box_top1",
        "violin_caption": "Violin plots of Top-1 Accuracy across five runs.",
        "violin_label": "fig:violin_top1",
    },
    {
        "key": "spearman_rho",
        "ylabel": "Spearman's $\\rho$",
        "ymin": -0.15,
        "ymax": 1.05,
        "box_caption": "Distribution of Spearman's $\\rho$ across five independent runs per model.",
        "box_label": "fig:box_rho",
        "violin_caption": "Violin plots of Spearman's $\\rho$ across five runs.",
        "violin_label": "fig:violin_rho",
    },
    {
        "key": "overall_rmse",
        "ylabel": "Overall RMSE",
        "ymin": 0,
        "ymax": 0.35,
        "box_caption": "Distribution of Overall RMSE across five independent runs per model.",
        "box_label": "fig:box_rmse",
        "violin_caption": "Violin plots of Overall RMSE across five runs.",
        "violin_label": "fig:violin_rmse",
    },
]

MODELS = [
    ("gemini", "Gemini"),
    ("deepseek", "DeepSeek"),
    ("gptoss", "GPT-OSS"),
    ("qwen", "Qwen"),
]

# Use __PLACEHOLDER__ markers to avoid .format() / LaTeX brace collision
BOX_MINIPAGE_TPL = r"""\begin{minipage}{0.24\textwidth}
\centering
\begin{tikzpicture}
\begin{axis}[boxplot/draw direction=y, width=\textwidth, height=5cm,
  ylabel={__YLABEL__}, ymin=__YMIN__, ymax=__YMAX__,
  xtick={1,2,3}, xticklabels={$\mathcal{A}_{\text{D}}$,$\mathcal{A}_{\text{E}}$,$\mathcal{A}_{\text{H}}$},
  title={\small __MODEL_TITLE__}, title style={font=\small}]
__COORDS__
\end{axis}
\end{tikzpicture}
\end{minipage}"""

VIOLIN_MINIPAGE_TPL = r"""\begin{minipage}{0.24\textwidth}
\centering
\begin{tikzpicture}
\begin{axis}[width=\textwidth, height=5cm, ymin=__YMIN__, ymax=__YMAX__,
  xtick={1,2,3}, xticklabels={$\mathcal{A}_{\text{D}}$,$\mathcal{A}_{\text{E}}$,$\mathcal{A}_{\text{H}}$},
  title={\small __MODEL_TITLE__}, title style={font=\small}]
__COORDS__
\end{axis}
\end{tikzpicture}
\end{minipage}"""


def _fill_box_minipage(ylabel, ymin, ymax, model_title, coords):
    return (
        BOX_MINIPAGE_TPL
        .replace("__YLABEL__", ylabel)
        .replace("__YMIN__", str(ymin))
        .replace("__YMAX__", str(ymax))
        .replace("__MODEL_TITLE__", model_title)
        .replace("__COORDS__", coords)
    )


def _fill_violin_minipage(ymin, ymax, model_title, coords):
    return (
        VIOLIN_MINIPAGE_TPL
        .replace("__YMIN__", str(ymin))
        .replace("__YMAX__", str(ymax))
        .replace("__MODEL_TITLE__", model_title)
        .replace("__COORDS__", coords)
    )


def _join_minipages(minipages):
    out = []
    for i, mp in enumerate(minipages):
        out.append(mp)
        if i < len(minipages) - 1:
            out.append("\\hfill")
    return "\n".join(out)


def build_box_figure(metric):
    minipages = []
    for model_key, model_title in MODELS:
        coords = generate_boxplot_block(model_key, metric["key"])
        minipages.append(
            _fill_box_minipage(
                ylabel=metric["ylabel"],
                ymin=metric["ymin"],
                ymax=metric["ymax"],
                model_title=model_title,
                coords=coords,
            )
        )
    body = _join_minipages(minipages)
    return (
        "\\begin{figure*}[t]\n"
        "\\centering\n"
        f"{body}\n"
        f"\\caption{{{metric['box_caption']}}}\n"
        f"\\label{{{metric['box_label']}}}\n"
        "\\end{figure*}"
    )


def build_violin_figure(metric):
    minipages = []
    for model_key, model_title in MODELS:
        coords = generate_violin_block(model_key, metric["key"])
        minipages.append(
            _fill_violin_minipage(
                ymin=metric["ymin"],
                ymax=metric["ymax"],
                model_title=model_title,
                coords=coords,
            )
        )
    body = _join_minipages(minipages)
    return (
        "\\begin{figure*}[t]\n"
        "\\centering\n"
        f"{body}\n"
        f"\\caption{{{metric['violin_caption']}}}\n"
        f"\\label{{{metric['violin_label']}}}\n"
        "\\end{figure*}"
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = []
    for metric in METRICS:
        blocks.append(build_box_figure(metric))
        blocks.append("")
        blocks.append(build_violin_figure(metric))
        blocks.append("")
    OUTPUT_FILE.write_text("\n".join(blocks).strip() + "\n")
    print(f"[OK] Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
