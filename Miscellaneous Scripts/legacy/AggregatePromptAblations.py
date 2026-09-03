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
    python "Miscellaneous Scripts/AggregatePromptAblations.py"
"""

import argparse
import glob
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd


def _load_runner():
    path = PROJECT_ROOT / "Miscellaneous Scripts" / "experiments" / "run_prompt_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("run_prompt_ablations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild the prompt-ablation summary from all cell files.")
    parser.add_argument("--cells-dir",
                        default=str(PROJECT_ROOT / "Analysis" / "Prompt_Ablation"))
    parser.add_argument("--output",
                        default=str(PROJECT_ROOT / "prompt_ablation_results.md"))
    args = parser.parse_args()

    runner = _load_runner()
    cells_dir = Path(args.cells_dir)
    files = sorted(glob.glob(str(cells_dir / "cell_*.xlsx")))
    if not files:
        print(f"No cell files found in {cells_dir}")
        return

    df = pd.concat([pd.read_excel(f) for f in files], ignore_index=True)
    summary, per_run = runner.summarize(df)

    # Report which cells are short of the expected 5 runs, so a partial matrix
    # is never mistaken for a complete one.
    expected_runs = int(per_run["run"].max()) if len(per_run) else 0
    counts = per_run.groupby(["variant", "architecture", "model"]).size()
    incomplete = counts[counts < expected_runs]

    out_dir = cells_dir
    with pd.ExcelWriter(out_dir / "prompt_ablation_summary.xlsx") as xl:
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
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {args.output} and {out_dir / 'prompt_ablation_summary.xlsx'}")


if __name__ == "__main__":
    main()
