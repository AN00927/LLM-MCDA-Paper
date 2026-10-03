#!/usr/bin/env python3
"""
run_paper_pipeline.py - Master pipeline for paper data generation.

Runs every DETERMINISTIC analysis step that feeds the paper, in dependency
order. Nothing here calls an LLM API: the architecture runners and the
run_*_experiments.py ablation scripts are deliberately EXCLUDED because they
cost money and must be launched by hand.

COMPLETENESS IS THE POINT. The manuscript's availability statement claims every
table, figure and statistical test can be regenerated from this repository, so
any script producing a number the paper prints belongs in STEPS below. If you
add such a script, add it here too, and keep it out of the guarded stages unless
it writes a tracked or frozen path.

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
import os
import subprocess
import sys
from pathlib import Path

from llm_mcda.common.paths import ALLOW_TRACKED_OUTPUT_WRITES_ENV, repository_root
PROJECT_ROOT = repository_root(start=__file__)
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from llm_mcda.common.paths import repository_path
from llm_mcda.common.model_config import get_model_artifact_subdir
SCRIPTS = "scripts"
PIPELINE = f"{SCRIPTS}/paper_pipeline"
VALIDATION = f"{SCRIPTS}/validation"
ANALYSIS = f"{SCRIPTS}/analysis"
WEIGHTING = "src/llm_mcda/common/weighting"
GUARDED_STAGES = {"weights", "sensitivity"}

# Cross-model destination for every artifact this pipeline generates. Not
# guarded, unlike the per-model "Output Files <model>/" trees.
COMBINED = "Combined Metrics"
PIPELINE_MODELS = ("deepseek", "gemini", "gptoss", "qwen")

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
    # Must precede the failure analysis. analyze_benchmark_failures.py reads
    # sentinel COUNTS from each run xlsx but failure-MODE attribution from that
    # run's diagnostics JSON, and the A_E Shower re-collection left the two
    # disagreeing. Read-only here: it reports drift without touching the source
    # JSON, so a nonzero report means the failure-mode table needs attention.
    ("numbers", "Re-collection diagnostics reconciliation (read-only check)",
     [f"{PIPELINE}/reconcile_recollection_diagnostics.py", "--dry-run"]),
    ("numbers", "Benchmark failure analysis",
     [f"{PIPELINE}/analyze_benchmark_failures.py"]),
    ("numbers", "Duplication rate analysis",
     [f"{PIPELINE}/duplication_rate_analysis.py"]),
    # significance_testing.py requires an explicit destination (it is one of the
    # migration-updated validation writers). Its artifacts span all four models,
    # so they belong in Combined Metrics/ like the rest of this stage's outputs.
    ("numbers", "Significance testing",
     [f"{VALIDATION}/significance_testing.py", "--output-dir", COMBINED]),
    # Order is load-bearing from here: significance_testing.py writes
    # per_scenario_metrics_all.csv, which failure_inclusive_metrics.py and
    # symmetric_gate_metrics.py both read.
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

    # Baselines and dispersion. Both feed floats the paper prints but neither
    # was reachable from this pipeline before: competitive_baselines.py carries
    # the fixed-default and nearest-neighbour-copy comparisons, and
    # compute_dispersion_diagnostics.py writes paper/dispersion_table.tex and
    # paper/single_criterion_recovery.tex.
    ("numbers", "Competitive baselines (fixed default, nearest-neighbour copy)",
     [f"{PIPELINE}/competitive_baselines.py"]),
    ("numbers", "Score-dispersion and single-criterion recovery",
     [f"{PIPELINE}/compute_dispersion_diagnostics.py"]),

    # Ablation significance. The main significance family above covers the
    # A_D/A_E/A_H comparison only; these three cover the hybrid order-reversal,
    # prompt and retrieval-depth arms, each of which the paper reports as
    # surviving (or not surviving) Holm correction.
    ("numbers", "Hybrid ablation significance (order reversal)",
     [f"{VALIDATION}/test_hybrid_ablation_significance.py", "--output-dir", COMBINED]),
    ("numbers", "Prompt ablation significance",
     [f"{VALIDATION}/test_prompt_ablation_significance.py", "--output-dir", COMBINED]),
    ("numbers", "Retrieval depth k=1 vs k=3 bootstrap CIs",
     [f"{VALIDATION}/compare_retrieval_k_bootstrap_ci.py",
      "--output", f"{COMBINED}/k1_vs_k3_bootstrap_ci.xlsx"]),

    # Parameter-extraction accuracy, per model: the source of the extraction
    # accuracy table and of the "probability an extraction error changes the
    # top-ranked alternative" column. One model's report, so it belongs beside
    # that model's other artifacts.
    *[("numbers", f"Parameter-extraction accuracy ({model})",
       [f"{ANALYSIS}/evaluate_parameter_extraction.py", "--model", model,
        "--output", f"{get_model_artifact_subdir(model, 'metrics')}"
                    "/LLM-Parameterized_Reference_Scoring_parameter_evaluation.md"])
      for model in PIPELINE_MODELS],

    # Collection provenance. Nothing in the paper cites it today, but it is the
    # only artifact that recovers each run's UTC collection window, which is
    # what answers a provider-drift question without a fresh control arm.
    ("numbers", "Collection window provenance",
     [f"{PIPELINE}/emit_collection_window.py"]),

    # One invocation covers boxplot, violin, variance AND grouped_bars. The
    # three single-figure shims omitted grouped_bars, so the paper's overall
    # performance-by-model figure (paper/Images/OverallPerformanceByModel.pdf)
    # was never regenerated by this pipeline.
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
