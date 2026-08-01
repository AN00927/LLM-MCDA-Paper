#!/usr/bin/env python3
"""
run_all.py - Master pipeline for paper data generation.

Usage:
    python3 paper_pipeline/run_all.py              # full pipeline
    python3 paper_pipeline/run_all.py --skip-metrics  # skip per-run metrics (if already computed)
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_step(name, cmd):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=False)
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        sys.exit(result.returncode)
    print(f"  OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-metrics", action="store_true",
                        help="Skip per-run metrics computation")
    args = parser.parse_args()

    if not args.skip_metrics:
        run_step(
            "Step 1: Compute per-run metrics",
            [sys.executable, "paper_pipeline/calculate_per_run_metrics.py", "--all-models"],
        )

    run_step(
        "Step 2: Generate hardcoded plot snippet",
        [sys.executable, "paper_pipeline/generate_variance_snippet.py"],
    )

    print(f"\n{'='*60}")
    print("  Pipeline complete!")
    print("  Output: paper/per_run_metrics/variance_plots.tex")
    print("  Copy to Overleaf and ensure Draft.tex uses:")
    print("    \\input{per_run_metrics/variance_plots.tex}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
