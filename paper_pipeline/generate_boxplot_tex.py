#!/usr/bin/env python3
"""Generate hardcoded pgfplots boxplot commands from per-run CSV data."""

import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "paper" / "per_run_metrics"

ARCH_MAP = {
    "Direct_LLM_Scoring": ("colorPure!30", 1),
    "Example-Guided_LLM_Scoring": ("colorRAG!30", 2),
    "LLM-Parameterized_Reference_Scoring": ("colorLLMParameterizedReferenceScoring!30", 3),
}


def generate_boxplot_block(model_key, metric):
    """Return pgfplots boxplot \addplot commands for one model x metric."""
    csv_path = DATA_DIR / f"per_run_metrics_{model_key}.csv"
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
    for model in ["gemini", "deepseek", "gptoss", "qwen"]:
        for metric in ["kendall_tau", "spearman_rho", "top1_accuracy", "overall_mae", "overall_rmse"]:
            print(f"=== {model} / {metric} ===")
            print(generate_boxplot_block(model, metric))
            print()
