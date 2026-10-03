#!/usr/bin/env python3
"""Generate hardcoded pgfplots boxplot commands from per-run CSV data."""

import sys
from pathlib import Path

import pandas as pd

from llm_mcda.common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from llm_mcda.common.paths import local_manuscript_path

DATA_DIR = local_manuscript_path("paper", "per_run_metrics")
PER_RUN_MODELS = ["deepseek", "gemini", "gptoss", "qwen"]


def require_local_per_run_csvs():
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
    "Direct_LLM_Scoring": ("colorPure!30", 1),
    "Example-Guided_LLM_Scoring": ("colorRAG!30", 2),
    "LLM-Parameterized_Reference_Scoring": ("colorLLMParameterizedReferenceScoring!30", 3),
}


def generate_boxplot_block(model_key, metric):
    """Return pgfplots boxplot \addplot commands for one model x metric."""
    csv_path = require_local_per_run_csvs()[model_key]
    df = pd.read_csv(csv_path)
    overall = df[df["decision_type"] == "Overall"]
    lines = []
    for arch, (color, x_pos) in ARCH_MAP.items():
        vals = sorted(overall[overall["architecture"] == arch][metric].values)
        if len(vals) != 5:
            raise ValueError(f"Expected 5 runs for {model_key}/{arch}/{metric}, got {len(vals)}")
        coords = " ".join(f"({x_pos}, {v})" for v in vals)
        lines.append(f"\\addplot+[boxplot, fill={color}] coordinates {{ {coords} }};")
    return "\n".join(lines)


if __name__ == "__main__":
    require_local_per_run_csvs()
    for model in ["gemini", "deepseek", "gptoss", "qwen"]:
        for metric in ["kendall_tau", "spearman_rho", "top1_accuracy", "overall_mae", "overall_rmse"]:
            print(f"=== {model} / {metric} ===")
            print(generate_boxplot_block(model, metric))
            print()
