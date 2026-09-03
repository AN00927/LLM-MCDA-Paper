#!/usr/bin/env python3
"""Generate the fig:grouped_bars figure (Overall performance by model) as a
matplotlib-rendered vector PDF, replacing the original tikz/pgfplots groupplot.

This is a one-off figure script (not wired into run_paper_pipeline.py). Data is
hardcoded from the confirmed source values in paper/paper_draft_working.tex
(architecture comparison across four metrics: Kendall's tau, Top-1 %, MAE, RMSE).

Colors reuse the document's existing, previously-unused per-architecture color
definitions (paper/paper_draft_working.tex ~line 277-279):
    colorPure    = RGB(180,180,180)  -> A_D (Direct scoring)
    colorRAG     = RGB(100,149,200)  -> A_E (Example-Guided / RAG scoring)
    colorLLMParameterizedReferenceScoring = RGB(31,73,125) -> A_H (Hybrid reference scoring)
so this figure's palette is consistent with the rest of the document's color
system rather than introducing a new ad hoc scheme.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "paper" / "Images" / "OverallPerformanceByModel.pdf"

MODELS = ["Gemini", "DeepSeek", "GPT-OSS", "Qwen"]

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
        "A_D": ([0.176, 0.144, 0.041, 0.010], [0.014, 0.041, 0.045, 0.039]),
        "A_E": ([0.310, 0.307, 0.272, 0.208], [0.019, 0.036, 0.040, 0.037]),
        "A_H": ([0.923, 0.897, 0.897, 0.880], [0.002, 0.006, 0.007, 0.013]),
    },
    "top1": {
        "title": "Top-1 (%)",
        "ymin": 0, "ymax": 110,
        "A_D": ([36.2, 36.7, 33.3, 30.0], [1.5, 3.1, 2.4, 3.0]),
        "A_E": ([48.7, 53.5, 47.4, 46.6], [2.0, 3.3, 2.1, 1.6]),
        "A_H": ([93.1, 90.8, 91.7, 89.7], [0.3, 1.0, 0.7, 1.2]),
    },
    "mae": {
        "title": "MAE",
        "ymin": 0, "ymax": 1.0,
        "A_D": ([0.219, 0.231, 0.241, 0.235], [0.002, 0.003, 0.002, 0.002]),
        "A_E": ([0.158, 0.168, 0.169, 0.194], [0.001, 0.001, 0.002, 0.003]),
        "A_H": ([0.048, 0.045, 0.052, 0.072], [0.001, 0.004, 0.001, 0.002]),
    },
    "rmse": {
        "title": "RMSE",
        "ymin": 0, "ymax": 1.0,
        "A_D": ([0.295, 0.302, 0.306, 0.295], [0.002, 0.003, 0.002, 0.002]),
        "A_E": ([0.231, 0.237, 0.242, 0.261], [0.002, 0.001, 0.003, 0.004]),
        "A_H": ([0.101, 0.092, 0.101, 0.162], [0.001, 0.011, 0.004, 0.005]),
    },
}

PANEL_ORDER = ["kendall_tau", "top1", "mae", "rmse"]


def main():
    fig, axes = plt.subplots(2, 2, figsize=(9, 7))
    axes = axes.flatten()

    n_models = len(MODELS)
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
        ax.set_xticklabels(MODELS, rotation=25, ha="right", fontsize=9)
        ax.grid(axis="y", linestyle="--", color="gray", alpha=0.4)
        ax.set_axisbelow(True)

    fig.legend(
        bars_for_legend, LEGEND_LABELS,
        loc="upper center", ncol=3, frameon=False,
        bbox_to_anchor=(0.5, 1.02), fontsize=12,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, format="pdf", bbox_inches="tight")
    print(f"Saved figure to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
