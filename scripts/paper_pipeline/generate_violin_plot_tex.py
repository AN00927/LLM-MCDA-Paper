#!/usr/bin/env python3
"""Generate hardcoded pgfplots violin polygon commands from per-run data."""

import numpy as np
from scipy.stats import gaussian_kde
import pandas as pd
import sys
from pathlib import Path

from llm_mcda.common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from llm_mcda.common.paths import local_manuscript_path

DATA_DIR = local_manuscript_path("paper", "per_run_metrics")
PER_RUN_MODELS = ["deepseek", "gemini", "gptoss", "qwen"]


def _require_local_per_run_csvs():
    paths = {
        model: DATA_DIR / f"per_run_metrics_{model}.csv"
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

ARCH_MAP = {
    "Direct_LLM_Scoring": ("colorPure!60", 1),
    "Example-Guided_LLM_Scoring": ("colorRAG!60", 2),
    "LLM-Parameterized_Reference_Scoring": ("colorLLMParameterizedReferenceScoring!60", 3),
}

N_GRID = 50
MAX_HALF_WIDTH = 0.35


def compute_violin_polygon(values, center_x):
    """Compute mirrored KDE polygon coordinates."""
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
    """Return pgfplots violin \addplot commands for one model x metric."""
    csv_path = _require_local_per_run_csvs()[model_key]
    df = pd.read_csv(csv_path)
    overall = df[df["decision_type"] == "Overall"]
    lines = []
    for arch, (color, x_pos) in ARCH_MAP.items():
        vals = overall[overall["architecture"] == arch][metric].values
        if len(vals) < 2:
            continue
        polygon = compute_violin_polygon(vals, x_pos)
        coords_str = " ".join(f"({x:.4f},{y:.4f})" for x, y in polygon)
        lines.append(
            f"\\addplot[no marks, fill={color}, fill opacity=0.5] coordinates {{ {coords_str} }};"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    _require_local_per_run_csvs()
    for model in ["gemini", "deepseek", "gptoss", "qwen"]:
        for metric in ["kendall_tau", "spearman_rho", "top1_accuracy", "overall_mae", "overall_rmse"]:
            print(f"=== {model} / {metric} ===")
            print(generate_violin_block(model, metric))
            print()
