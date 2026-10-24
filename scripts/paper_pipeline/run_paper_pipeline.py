#!/usr/bin/env python3
"""Run the deterministic analysis pipeline that generates paper numbers and tables."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from common.paths import ALLOW_TRACKED_OUTPUT_WRITES_ENV, repository_root
PROJECT_ROOT = repository_root(start=__file__)
IMPORT_ROOT = PROJECT_ROOT
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))
from common.paths import repository_path
from common.model_config import get_model_artifact_subdir
SCRIPTS = "scripts"
PIPELINE = f"{SCRIPTS}/paper_pipeline"
VALIDATION = f"{SCRIPTS}/validation"
ANALYSIS = f"{SCRIPTS}/analysis"
WEIGHTING = "common/weighting"
GUARDED_STAGES = {"weights", "sensitivity"}

# Cross-model destination for every artifact this pipeline generates. Not
# guarded, unlike the per-model "Output Files <model>/" trees.
COMBINED = "Combined Metrics"
PIPELINE_MODELS = ("deepseek", "gemini", "gptoss", "qwen")

# Weights runs before sensitivity (methodology workbook dependency).
# Metrics runs before numbers (per-run metrics dependency).
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
    # Reconciliation runs before failure analysis (diagnostics JSON dependency).
    ("numbers", "Re-collection diagnostics reconciliation (read-only check)",
     [f"{PIPELINE}/reconcile_recollection_diagnostics.py", "--dry-run"]),
    ("numbers", "Benchmark failure analysis",
     [f"{PIPELINE}/analyze_benchmark_failures.py"]),
    ("numbers", "Duplication rate analysis",
     [f"{PIPELINE}/duplication_rate_analysis.py"]),
    ("numbers", "Significance testing",
     [f"{VALIDATION}/significance_testing.py", "--output-dir", COMBINED]),
    # Significance testing runs before failure-inclusive metrics (per-scenario metrics dependency).
    ("numbers", "Run-level bootstrap confidence intervals",
     [f"{VALIDATION}/compute_confidence_intervals.py"]),
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

    ("numbers", "Competitive baselines (A_E vs nearest-neighbour copy)",
     [f"{PIPELINE}/competitive_baselines.py"]),
    ("numbers", "Score-dispersion and single-criterion recovery",
     [f"{PIPELINE}/compute_dispersion_diagnostics.py"]),

    ("numbers", "Hybrid ablation significance (order reversal)",
     [f"{VALIDATION}/test_hybrid_ablation_significance.py", "--output-dir", COMBINED]),
    ("numbers", "Prompt ablation significance",
     [f"{VALIDATION}/test_prompt_ablation_significance.py", "--output-dir", COMBINED]),
    ("numbers", "Retrieval depth k=1 vs k=3 bootstrap CIs",
     [f"{VALIDATION}/compare_retrieval_k_bootstrap_ci.py",
      "--output", f"{COMBINED}/k1_vs_k3_bootstrap_ci.xlsx"]),

    *[("numbers", f"Parameter-extraction accuracy ({model})",
       [f"{ANALYSIS}/evaluate_parameter_extraction.py", "--model", model,
        "--output", f"{get_model_artifact_subdir(model, 'metrics')}"
                    "/LLM-Parameterized_Reference_Scoring_parameter_evaluation.md"])
      for model in PIPELINE_MODELS],

    ("numbers", "Collection window provenance",
     [f"{PIPELINE}/emit_collection_window.py"]),

    ("figures", "pgfplots snippets and vector figures (all four)",
     [f"{PIPELINE}/generate_pgfplots.py", "--figure", "all"]),
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
    elif guarded:
        # Guarded stages write the tracked methodology artifacts. Propagate the
        # opt-in to the step subprocesses so the path guard permits those writes.
        os.environ[ALLOW_TRACKED_OUTPUT_WRITES_ENV] = "1"

    required_local = []
    if ("numbers" in wanted or "figures" in wanted) and "metrics" not in wanted:
        required_local.extend(
            repository_path(get_model_artifact_subdir(model, "metrics"), f"per_run_metrics_{model}.csv")
            for model in ("deepseek", "gemini", "gptoss", "qwen")
        )
        if "numbers" in wanted:
            required_local.append(
                repository_path("Combined Metrics", "per_run_metrics_all.csv")
            )
    if required_local:
        missing_local = [str(path) for path in required_local if not path.is_file()]
        if missing_local:
            parser.error("The selected paper pipeline stages require inputs that are not present: "+", ".join(missing_local)+"; restore them at those paths before rerunning.")

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
    print(f"  Generated data artifacts go to {COMBINED}/; LaTeX snippets and figures go to paper/.")
    print("    tab:sensitivity_by_model  <- per-model sensitivity workbooks in Output Files <model>/sensitivity/")
    print("    tab:sensitivity_top1      <- per-model sensitivity workbooks in Output Files <model>/sensitivity/")
    print("    tab:zero_variance         <- workbooks/methodology/")
    print("    tab:weight_comparison     <- workbooks/methodology/")
    print("=" * 64)


if __name__ == "__main__":
    main()
