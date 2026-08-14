#!/usr/bin/env python3
"""
run_paper_pipeline.py - Master pipeline for paper data generation.

Runs every DETERMINISTIC analysis step that feeds the paper, in dependency
order. Nothing here calls an LLM API: the architecture runners and the
run_*_experiments.py ablation scripts are deliberately EXCLUDED because they
cost money and must be launched by hand.

The paper does NOT use \\input{} for any table. Every table in
paper_draft_working.tex and supplementary_material.tex is literal LaTeX,
hand-pasted after inspecting the outputs below. That is intentional - this
pipeline refreshes the NUMBERS; a human re-pastes the tables. Consequently no
step here writes into either .tex file, so running the pipeline can never
clobber hand edits.

Usage:
    python paper_pipeline/run_paper_pipeline.py                # everything
    python paper_pipeline/run_paper_pipeline.py --skip-metrics # skip per-run metrics
    python paper_pipeline/run_paper_pipeline.py --only weights # one stage
    python paper_pipeline/run_paper_pipeline.py --list         # show stages
    python paper_pipeline/run_paper_pipeline.py --keep-going   # don't stop on failure
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MISC = "Miscellaneous Scripts"

# (stage, label, argv-after-interpreter)
# Order is load-bearing:
#   weights  -> writes Scoring Logic and Documentation/method/*.xlsx
#   sensitivity reads those, so it MUST follow weights.
#   metrics  -> writes paper/per_run_metrics/, read by the numbers stage.
STEPS = [
    ("weights", "MEREC objective weights",
     [f"{MISC}/merec_weights.py"]),
    ("weights", "Entropy objective weights",
     [f"{MISC}/EntropyWeights.py"]),
    ("weights", "Implied weights (constrained least squares)",
     [f"{MISC}/implied_weights.py"]),
    ("weights", "Weight discrimination / zero-variance diagnostics",
     [f"{MISC}/WeightDiagnostics.py"]),

    ("metrics", "Per-run metrics (all models)",
     ["paper_pipeline/calculate_per_run_metrics.py", "--all-models"]),

    ("sensitivity", "Weight-perturbation sensitivity (all models)",
     [f"{MISC}/SensitivityAnalysis.py", "--all-models"]),
    ("sensitivity", "MEREC/Entropy objective arms (all models)",
     [f"{MISC}/SensitivityAnalysis.py", "--objective-arms", "--all-models"]),
    ("sensitivity", "Alpha sweep (all models)",
     [f"{MISC}/SensitivityAnalysis.py", "--alpha-sweep", "--all-models"]),

    ("numbers", "Paper results numbers (numbers_master.csv)",
     ["paper_pipeline/generate_paper_results_numbers.py"]),
    ("numbers", "Imputed-failure robustness tables",
     ["paper_pipeline/generate_imputed_robustness_tables.py"]),
    ("numbers", "Benchmark failure analysis",
     ["paper_pipeline/analyze_benchmark_failures.py"]),
    ("numbers", "Duplication rate analysis",
     ["paper_pipeline/duplication_rate_analysis.py"]),
    ("numbers", "Significance testing",
     [f"{MISC}/significance_testing.py"]),
    ("numbers", "Cluster bootstrap CIs",
     ["paper_pipeline/cluster_bootstrap_ci.py"]),
    ("numbers", "Failure-inclusive metrics",
     ["paper_pipeline/failure_inclusive_metrics.py"]),
    ("numbers", "Symmetric gate metrics",
     ["paper_pipeline/symmetric_gate_metrics.py"]),
    ("numbers", "Per-model p-values export",
     ["paper_pipeline/emit_per_model_pvalues.py"]),

    ("figures", "Variance plot snippet",
     ["paper_pipeline/generate_variance_plot_tex.py"]),
    ("figures", "Violin plot snippet",
     ["paper_pipeline/generate_violin_plot_tex.py"]),
    ("figures", "Boxplot snippet",
     ["paper_pipeline/generate_boxplot_tex.py"]),
    ("figures", "Paper figures",
     ["paper_pipeline/generate_paper_figures.py"]),
]

STAGES = ["weights", "metrics", "sensitivity", "numbers", "figures"]


def run_step(label, argv, keep_going):
    print("\n" + "=" * 64)
    print(f"  {label}")
    print("=" * 64)
    result = subprocess.run([sys.executable] + argv, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode}): {label}")
        if not keep_going:
            sys.exit(result.returncode)
        return False
    print("  OK")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate every deterministic paper analysis artifact.")
    parser.add_argument("--skip-metrics", action="store_true",
                        help="Skip the per-run metrics stage (slow; skip if unchanged)")
    parser.add_argument("--only", choices=STAGES, action="append", default=None,
                        help="Run only this stage (repeatable)")
    parser.add_argument("--keep-going", action="store_true",
                        help="Continue after a failing step instead of aborting")
    parser.add_argument("--list", action="store_true",
                        help="List the steps that would run, then exit")
    args = parser.parse_args()

    wanted = set(args.only) if args.only else set(STAGES)
    if args.skip_metrics:
        wanted.discard("metrics")

    selected = [(s, lbl, argv) for (s, lbl, argv) in STEPS if s in wanted]

    if args.list:
        print("Steps that would run:")
        for stage, label, argv in selected:
            print(f"  [{stage:<11}] {label}")
        return

    failed = []
    for stage, label, argv in selected:
        if not run_step(label, argv, args.keep_going):
            failed.append(label)

    print("\n" + "=" * 64)
    if failed:
        print(f"  Pipeline finished with {len(failed)} FAILED step(s):")
        for label in failed:
            print(f"    - {label}")
    else:
        print("  Pipeline complete - all steps OK")
    print("")
    print("  No .tex file was modified. Paper tables are literal LaTeX and are")
    print("  hand-pasted; re-paste any table whose source numbers changed:")
    print("    tab:sensitivity_by_model  <- Analysis/Sensitivity_*_<model>.xlsx")
    print("    tab:sensitivity_top1      <- Analysis/Sensitivity_*_<model>.xlsx")
    print("    tab:zero_variance         <- Analysis/.../weight_discrimination.xlsx")
    print("    tab:weight_comparison     <- Scoring Logic and Documentation/method/")
    print("=" * 64)


if __name__ == "__main__":
    main()
