"""Rebuild the prompt-ablation summary from every completed cell file.

`run_prompt_ablation_experiments.py` writes its summary workbook and markdown report from
whatever cells that invocation covered, so running the matrix as several
partial jobs (per variant, per model, or resumed after an interruption) leaves
those aggregates describing only the last slice. The per-cell xlsx files under
Analysis/Prompt_Ablation/ are the complete record; this script re-derives the
full summary from all of them.

Reuses `run_prompt_ablation_experiments.summarize` and `_md` so the output is identical in
shape to a single-shot run -- no metric is recomputed here.

Run after the matrix finishes (or any time a partial view is wanted):
    python "scripts/archive/legacy/AggregatePromptAblations.py"
"""

import argparse
import glob
import importlib.util
import os
import sys
from pathlib import Path

# Bootstrap the checkout's src/ package before importing llm_mcda.
_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[3]
for _import_root in (_BOOTSTRAP_ROOT / "src", _BOOTSTRAP_ROOT):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from llm_mcda.common.paths import (
    RUN_OUTPUT_DIR_ENV,
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
    require_safe_output_path,
)
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd


def _load_runner():
    path = PROJECT_ROOT / "scripts" / "experiments" / "run_prompt_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("run_prompt_ablations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild the prompt-ablation summary from all cell files.")
    parser.add_argument("--cells-dir",
                        default=str(PROJECT_ROOT / "Analysis" / "Prompt_Ablation"))
    parser.add_argument(
        "--output-dir",
        default=os.environ.get(RUN_OUTPUT_DIR_ENV),
        help=f"Required safe output directory (or set {RUN_OUTPUT_DIR_ENV}); "
             "the source cell directory remains read-only.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional markdown report path (defaults to prompt_ablation_results.md "
             "inside --output-dir).",
    )
    args = parser.parse_args()

    try:
        out_dir = require_safe_output_directory(
            args.output_dir,
            option=f"--output-dir (or {RUN_OUTPUT_DIR_ENV})",
            root=PROJECT_ROOT,
        )
        workbook_path = require_safe_output_path(
            out_dir / "prompt_ablation_summary.xlsx",
            option="prompt-ablation workbook output",
            root=PROJECT_ROOT,
        )
        report_path = require_safe_output_path(
            args.output or out_dir / "prompt_ablation_results.md",
            option="--output",
            root=PROJECT_ROOT,
        )
        require_safe_output_directory(
            report_path.parent,
            option="--output parent",
            root=PROJECT_ROOT,
        )
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))
    if report_path == workbook_path:
        parser.error("--output must not overwrite the prompt-ablation workbook.")

    runner = _load_runner()
    cells_dir = Path(args.cells_dir)
    files = sorted(glob.glob(str(cells_dir / "cell_*.xlsx")))
    if not files:
        print(f"No cell files found in {cells_dir}")
        return
    input_paths = {Path(file).resolve() for file in files}
    if report_path in input_paths:
        parser.error("--output must not overwrite a source cell workbook.")

    df = pd.concat([pd.read_excel(f) for f in files], ignore_index=True)
    summary, per_run = runner.summarize(df)

    # Report which cells are short of the expected 5 runs, so a partial matrix
    # is never mistaken for a complete one.
    expected_runs = int(per_run["run"].max()) if len(per_run) else 0
    counts = per_run.groupby(["variant", "architecture", "model"]).size()
    incomplete = counts[counts < expected_runs]

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(workbook_path) as xl:
        summary.to_excel(xl, sheet_name="summary", index=False)
        per_run.to_excel(xl, sheet_name="per_run", index=False)
        df.to_excel(xl, sheet_name="per_scenario", index=False)

    cols = ["variant", "architecture", "model", "n_runs", "kendall_tau",
            "kendall_tau_sd", "top1_accuracy", "top1_accuracy_sd",
            "mean_criterion_sd", "success_rate"]
    print(f"Cells aggregated: {len(files)}")
    print(f"Scenario rows: {len(df)}")
    print(f"Combos: {summary.shape[0]}")
    if len(incomplete):
        print(f"\nWARNING: {len(incomplete)} combo(s) have fewer than {expected_runs} runs:")
        for k, v in incomplete.items():
            print(f"  {'/'.join(map(str, k))}: {v} run(s)")
    print()
    print(summary[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    lines = [
        "# Prompt-Sensitivity Ablation (A_D / A_E)", "",
        f"- Cells aggregated: {len(files)}",
        f"- Scenario rows: {len(df)}",
        f"- Models: {', '.join(sorted(df['model'].unique()))}", "",
        f"Note: {runner.NO_ANCHORS_AE_NOTE}", "",
        "## Summary (mean over runs; SD is run-to-run)", "",
        runner._md(summary[cols]), "",
        "## Per-run detail", "",
        runner._md(per_run),
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {report_path} and {workbook_path}")


if __name__ == "__main__":
    main()
