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
    python scripts/paper_pipeline/run_paper_pipeline.py                # safe stages
    python scripts/paper_pipeline/run_paper_pipeline.py --skip-metrics # skip per-run metrics
    python scripts/paper_pipeline/run_paper_pipeline.py --only weights # list guarded stage
    python scripts/paper_pipeline/run_paper_pipeline.py --list         # show stages
    python scripts/paper_pipeline/run_paper_pipeline.py --allow-tracked-output-writes --only weights
"""

import argparse
import subprocess
import sys
from pathlib import Path

from llm_mcda.common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from llm_mcda.common.paths import local_manuscript_path
SCRIPTS = "scripts"
PIPELINE = f"{SCRIPTS}/paper_pipeline"
VALIDATION = f"{SCRIPTS}/validation"
WEIGHTING = "src/llm_mcda/common/weighting"
GUARDED_STAGES = {"weights", "sensitivity"}

# (stage, label, argv-after-interpreter)
# Order is load-bearing:
#   weights  -> writes the tracked methodology workbooks under workbooks/methodology
#   sensitivity reads those, so it MUST follow weights.
#   metrics  -> writes local-only per-run metrics, read by the numbers stage.
STEPS = [
    ("weights", "MEREC objective weights",
     [f"{WEIGHTING}/merec_weights.py"]),
    ("weights", "Entropy objective weights",
     [f"{WEIGHTING}/EntropyWeights.py"]),
    ("weights", "Implied weights (constrained least squares)",
     [f"{WEIGHTING}/implied_weights.py"]),
    ("weights", "Weight discrimination / zero-variance diagnostics",
     [f"{VALIDATION}/WeightDiagnostics.py"]),

    ("metrics", "Per-run metrics (all models)",
     [f"{PIPELINE}/calculate_per_run_metrics.py", "--all-models"]),

    ("sensitivity", "Weight-perturbation sensitivity (all models)",
     [f"{VALIDATION}/SensitivityAnalysis.py", "--all-models"]),
    ("sensitivity", "MEREC/Entropy objective arms (all models)",
     [f"{VALIDATION}/SensitivityAnalysis.py", "--objective-arms", "--all-models"]),
    ("sensitivity", "Alpha sweep (all models)",
     [f"{VALIDATION}/SensitivityAnalysis.py", "--alpha-sweep", "--all-models"]),

    ("numbers", "Paper results numbers (numbers_master.csv)",
     [f"{PIPELINE}/generate_paper_results_numbers.py"]),
    ("numbers", "Imputed-failure robustness tables",
     [f"{PIPELINE}/generate_imputed_robustness_tables.py"]),
    ("numbers", "Benchmark failure analysis",
     [f"{PIPELINE}/analyze_benchmark_failures.py"]),
    ("numbers", "Duplication rate analysis",
     [f"{PIPELINE}/duplication_rate_analysis.py"]),
    ("numbers", "Significance testing",
     [f"{VALIDATION}/significance_testing.py"]),
    ("numbers", "Cluster bootstrap CIs",
     [f"{PIPELINE}/cluster_bootstrap_ci.py"]),
    ("numbers", "Failure-inclusive metrics",
     [f"{PIPELINE}/failure_inclusive_metrics.py"]),
    ("numbers", "Symmetric gate metrics",
     [f"{PIPELINE}/symmetric_gate_metrics.py"]),
    ("numbers", "Per-model p-values export",
     [f"{PIPELINE}/emit_per_model_pvalues.py"]),
    ("numbers", "Tie rates (share of scenario-runs tied before the tie-break)",
     [f"{PIPELINE}/compute_tie_rates.py"]),
    ("numbers", "Decision regret (A_D/A_E/A_H vs reference MAVT)",
     [f"{PIPELINE}/compute_regret.py"]),
    ("numbers", "Numbers-of-record regeneration check",
     [f"{PIPELINE}/build_numbers_of_record.py"]),

    ("figures", "Variance plot snippet",
     [f"{PIPELINE}/generate_variance_plot_tex.py"]),
    ("figures", "Violin plot snippet",
     [f"{PIPELINE}/generate_violin_plot_tex.py"]),
    ("figures", "Boxplot snippet",
     [f"{PIPELINE}/generate_boxplot_tex.py"]),
    ("figures", "Paper figures",
     [f"{PIPELINE}/generate_paper_figures.py"]),
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
    parser.add_argument("--allow-tracked-output-writes", action="store_true",
                        help="Run weights and sensitivity stages, which can overwrite tracked or frozen artifacts")
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
            guard = (" (guarded; requires --allow-tracked-output-writes)"
                     if stage in GUARDED_STAGES and not args.allow_tracked_output_writes else "")
            print(f"  [{stage:<11}] {label}{guard}")
        return

    guarded = [(stage, label) for stage, label, _ in selected if stage in GUARDED_STAGES]
    if guarded and not args.allow_tracked_output_writes:
        selected = [(stage, label, argv) for stage, label, argv in selected
                    if stage not in GUARDED_STAGES]
        print("Skipping stages that may overwrite tracked or frozen outputs by default:")
        for stage, label in guarded:
            print(f"  [{stage:<11}] {label}")
        print("Pass --allow-tracked-output-writes to run them after reviewing the destinations.\n")

    required_local = []
    if "numbers" in wanted:
        required_local.append(local_manuscript_path("paper", "pass5", "NUMBERS_OF_RECORD.csv"))
    if ("numbers" in wanted or "figures" in wanted) and "metrics" not in wanted:
        required_local.extend(
            local_manuscript_path("paper", "per_run_metrics", f"per_run_metrics_{model}.csv")
            for model in ("deepseek", "gemini", "gptoss", "qwen")
        )
        if "numbers" in wanted:
            required_local.append(
                local_manuscript_path("paper", "per_run_metrics", "per_run_metrics_all.csv")
            )
    if required_local:
        missing_local = [str(path) for path in required_local if not path.is_file()]
        if missing_local:
            parser.error("The selected paper pipeline stages require local-only inputs: "+", ".join(missing_local)+"; restore them under local_manuscripts/ or set LLM_MCDA_LOCAL_MANUSCRIPTS_DIR.")

    failed = []
    for stage, label, argv in selected:
        if not run_step(label, argv, args.keep_going):
            failed.append(label)

    print("\n" + "=" * 64)
    if failed:
        print(f"  Pipeline finished with {len(failed)} FAILED step(s):")
        for label in failed:
            print(f"    - {label}")
    elif guarded and not args.allow_tracked_output_writes:
        print("  Safe stages complete; guarded weights and sensitivity stages were skipped.")
    else:
        print("  Pipeline complete - all steps OK")
    print("")
    print("  The pipeline does not write to the manuscript copies. Generated snippets")
    print("  and reports use local-only destinations under local_manuscripts/.")
    print("    tab:sensitivity_by_model  <- frozen Analysis/Sensitivity_*_<model>.xlsx")
    print("    tab:sensitivity_top1      <- frozen Analysis/Sensitivity_*_<model>.xlsx")
    print("    tab:zero_variance         <- workbooks/methodology/")
    print("    tab:weight_comparison     <- workbooks/methodology/")
    print("=" * 64)


if __name__ == "__main__":
    main()
