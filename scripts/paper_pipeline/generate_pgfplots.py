#!/usr/bin/env python3
r"""Consolidated pgfplots/LaTeX snippet generators for the paper.

Figures (select with --figure {boxplot,violin,variance,grouped_bars,all}):
  boxplot       hardcoded pgfplots boxplot \addplot commands, printed to stdout
  violin        hardcoded pgfplots violin polygon commands, printed to stdout
  variance      full Run-to-Run Variance subsection written to
                <local manuscripts>/paper/per_run_metrics/variance_plots.tex
  grouped_bars  matplotlib vector PDF written to
                <local manuscripts>/paper/Images/OverallPerformanceByModel.pdf
                (one-off figure with hardcoded data; not a pgfplots snippet)
"""

import argparse
import sys

import numpy as np
import pandas as pd

from llm_mcda.common.paths import repository_root

PROJECT_ROOT = repository_root(start=__file__)
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from llm_mcda.common.paths import repository_path
from llm_mcda.common.model_config import get_model_artifact_subdir

PER_RUN_MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
OUTPUT_DIR = repository_path("paper")
OUTPUT_FILE = OUTPUT_DIR / "variance_plots.tex"
OUTPUT_PATH = repository_path("paper", "Images", "OverallPerformanceByModel.pdf")

FIGURES = ["boxplot", "violin", "variance", "grouped_bars"]


def require_local_per_run_csvs():
    paths = {
        model: repository_path(get_model_artifact_subdir(model, "metrics"), f"per_run_metrics_{model}.csv")
        for model in PER_RUN_MODELS
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise SystemExit(
            "Required local-only per-run metric inputs are missing: "
            + ", ".join(missing)
            + "; restore them under local_manuscripts/ or set "
            "LLM_MCDA_LOCAL_MANUSCRIPTS_DIR."
        )
    return paths


# ---------------------------------------------------------------- boxplot

BOX_ARCH_MAP = {
    "Direct_LLM_Scoring": ("colorPure!30", 1),
    "Example-Guided_LLM_Scoring": ("colorRAG!30", 2),
    "LLM-Parameterized_Reference_Scoring": ("colorLLMParameterizedReferenceScoring!30", 3),
}


def generate_boxplot_block(model_key, metric):
    r"""Return pgfplots boxplot \addplot commands for one model x metric."""
    csv_path = require_local_per_run_csvs()[model_key]
    df = pd.read_csv(csv_path)
    overall = df[df["decision_type"] == "Overall"]
    lines = []
    for arch, (color, x_pos) in BOX_ARCH_MAP.items():
        vals = sorted(overall[overall["architecture"] == arch][metric].values)
        if len(vals) != 5:
            raise ValueError(f"Expected 5 runs for {model_key}/{arch}/{metric}, got {len(vals)}")
        coords = " ".join(f"({x_pos}, {v})" for v in vals)
        lines.append(f"\\addplot+[boxplot, fill={color}] coordinates {{ {coords} }};")
    return "\n".join(lines)


def _print_blocks(generate_block):
    require_local_per_run_csvs()
    for model in ["gemini", "deepseek", "gptoss", "qwen"]:
        for metric in ["kendall_tau", "spearman_rho", "top1_accuracy", "overall_mae", "overall_rmse"]:
            print(f"=== {model} / {metric} ===")
            print(generate_block(model, metric))
            print()


def build_boxplot():
    _print_blocks(generate_boxplot_block)


# ----------------------------------------------------------------- violin

VIOLIN_ARCH_MAP = {
    "Direct_LLM_Scoring": ("colorPure!60", 1),
    "Example-Guided_LLM_Scoring": ("colorRAG!60", 2),
    "LLM-Parameterized_Reference_Scoring": ("colorLLMParameterizedReferenceScoring!60", 3),
}

N_GRID = 50
MAX_HALF_WIDTH = 0.35


def compute_violin_polygon(values, center_x):
    """Compute mirrored KDE polygon coordinates."""
    from scipy.stats import gaussian_kde

    vals = np.array(values, dtype=float)
    n = len(vals)
    std = np.std(vals, ddof=1) if n > 1 else 0.01
    bandwidth = 1.06 * std * (n ** -0.2)
    bandwidth = max(bandwidth, 1e-6)

    kde = gaussian_kde(vals, bw_method=bandwidth / np.std(vals))
    y_min = vals.min() - 3 * bandwidth
    y_max = vals.max() + 3 * bandwidth
    y_grid = np.linspace(y_min, y_max, N_GRID)
    density = kde(y_grid)

    max_d = density.max()
    if max_d > 0:
        density = density / max_d * MAX_HALF_WIDTH

    right = [(center_x + d, y) for d, y in zip(density, y_grid)]
    left = [(center_x - d, y) for d, y in zip(reversed(density), reversed(y_grid))]
    coords = right + left
    return coords


def generate_violin_block(model_key, metric):
    r"""Return pgfplots violin \addplot commands for one model x metric."""
    csv_path = require_local_per_run_csvs()[model_key]
    df = pd.read_csv(csv_path)
    overall = df[df["decision_type"] == "Overall"]
    lines = []
    for arch, (color, x_pos) in VIOLIN_ARCH_MAP.items():
        vals = overall[overall["architecture"] == arch][metric].values
        if len(vals) < 2:
            continue
        polygon = compute_violin_polygon(vals, x_pos)
        coords_str = " ".join(f"({x:.4f},{y:.4f})" for x, y in polygon)
        lines.append(
            f"\\addplot[no marks, fill={color}, fill opacity=0.5] coordinates {{ {coords_str} }};"
        )
    return "\n".join(lines)


def build_violin():
    _print_blocks(generate_violin_block)


# --------------------------------------------------------------- variance

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


def build_variance():
    require_local_per_run_csvs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = []
    for metric in METRICS:
        blocks.append(build_box_figure(metric))
        blocks.append("")
        blocks.append(build_violin_figure(metric))
        blocks.append("")
    OUTPUT_FILE.write_text("\n".join(blocks).strip() + "\n")
    print(f"[OK] Wrote {OUTPUT_FILE}")


# ----------------------------------------------------------- grouped bars
# matplotlib-rendered fig:grouped_bars (Overall performance by model). Data is
# hardcoded from the five-run means and SDs in supplementary Table overall_by_model. Colors reuse
# the document's per-architecture definitions:
#   colorPure    = RGB(180,180,180)  -> A_D (Direct scoring)
#   colorRAG     = RGB(100,149,200)  -> A_E (Example-Guided / RAG scoring)
#   colorLLMParameterizedReferenceScoring = RGB(31,73,125) -> A_H

GROUPED_BAR_MODELS = ["Gemini", "DeepSeek", "GPT-OSS", "Qwen"]

# color_A_D, color_A_E, color_A_H (RGB 0-255 -> matplotlib 0-1 tuples)
COLOR_A_D = tuple(c / 255 for c in (180, 180, 180))   # colorPure
COLOR_A_E = tuple(c / 255 for c in (100, 149, 200))   # colorRAG
COLOR_A_H = tuple(c / 255 for c in (31, 73, 125))     # colorLLMParameterizedReferenceScoring

LEGEND_LABELS = [r"$\mathcal{A}_{D}$", r"$\mathcal{A}_{E}$", r"$\mathcal{A}_{H}$"]

# metric_key -> (title, ymin, ymax, {arch: (means[4], stds[4])})
DATA = {
    "kendall_tau": {
        "title": r"Kendall's $\tau$",
        "ymin": 0, "ymax": 1.1,
        "A_D": ([0.179, 0.125, 0.032, 0.005], [0.020, 0.031, 0.026, 0.037]),
        "A_E": ([0.298, 0.253, 0.234, 0.147], [0.008, 0.037, 0.040, 0.028]),
        "A_H": ([0.891, 0.856, 0.805, 0.836], [0.005, 0.011, 0.012, 0.012]),
    },
    "top1": {
        "title": "Top-1 (%)",
        "ymin": 0, "ymax": 110,
        "A_D": ([39.8, 39.1, 34.1, 30.8], [0.8, 2.8, 2.2, 2.5]),
        "A_E": ([47.5, 48.3, 46.5, 43.9], [1.1, 1.8, 4.3, 2.4]),
        "A_H": ([90.2, 88.6, 82.5, 86.5], [0.4, 0.9, 0.9, 1.1]),
    },
    "mae": {
        "title": "MAE",
        "ymin": 0, "ymax": 1.0,
        "A_D": ([0.207, 0.223, 0.246, 0.239], [0.001, 0.003, 0.003, 0.002]),
        "A_E": ([0.147, 0.170, 0.179, 0.198], [0.001, 0.002, 0.001, 0.004]),
        "A_H": ([0.048, 0.055, 0.079, 0.074], [0.001, 0.001, 0.002, 0.002]),
    },
}

PANEL_ORDER = ["kendall_tau", "top1", "mae"]


def build_grouped_bars():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes = axes.flatten()

    n_models = len(GROUPED_BAR_MODELS)
    n_arch = 3
    bar_width = 0.25
    x = np.arange(n_models)

    bars_for_legend = None

    for ax, key in zip(axes, PANEL_ORDER):
        d = DATA[key]
        means_ad, stds_ad = d["A_D"]
        means_ae, stds_ae = d["A_E"]
        means_ah, stds_ah = d["A_H"]

        b1 = ax.bar(
            x - bar_width, means_ad, bar_width, yerr=stds_ad,
            color=COLOR_A_D, edgecolor="black", linewidth=0.5,
            capsize=3, error_kw={"elinewidth": 0.8, "capthick": 0.8},
        )
        b2 = ax.bar(
            x, means_ae, bar_width, yerr=stds_ae,
            color=COLOR_A_E, edgecolor="black", linewidth=0.5,
            capsize=3, error_kw={"elinewidth": 0.8, "capthick": 0.8},
        )
        b3 = ax.bar(
            x + bar_width, means_ah, bar_width, yerr=stds_ah,
            color=COLOR_A_H, edgecolor="black", linewidth=0.5,
            capsize=3, error_kw={"elinewidth": 0.8, "capthick": 0.8},
        )

        if bars_for_legend is None:
            bars_for_legend = (b1, b2, b3)

        ax.set_title(d["title"], fontsize=12)
        ax.set_ylim(d["ymin"], d["ymax"])
        ax.set_xticks(x)
        ax.set_xticklabels(GROUPED_BAR_MODELS, rotation=25, ha="right", fontsize=9)
        ax.grid(axis="y", linestyle="--", color="gray", alpha=0.4)
        ax.set_axisbelow(True)

    fig.legend(
        bars_for_legend, LEGEND_LABELS,
        loc="upper center", ncol=3, frameon=False,
        bbox_to_anchor=(0.5, 1.02), fontsize=12,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.92])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, format="pdf", bbox_inches="tight")
    print(f"Saved figure to {OUTPUT_PATH}")


# -------------------------------------------------------------------- CLI

BUILDERS = {
    "boxplot": build_boxplot,
    "violin": build_violin,
    "variance": build_variance,
    "grouped_bars": build_grouped_bars,
}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate the paper pgfplots snippets and the grouped-bars figure."
    )
    parser.add_argument(
        "--figure",
        choices=FIGURES + ["all"],
        default="all",
        help="which generator to run (default: all)",
    )
    args = parser.parse_args(argv)
    for name in (FIGURES if args.figure == "all" else [args.figure]):
        BUILDERS[name]()


if __name__ == "__main__":
    main()
