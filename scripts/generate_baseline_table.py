#!/usr/bin/env python3
"""
generate_baseline_table.py - Incremental Contribution DIAGNOSTIC

Prints a single-model comparison of the two non-LLM baselines against the three
LLM architectures. Console and CSV output; a LaTeX rendering is available on
request via --output-latex.

THIS IS NOT THE SOURCE OF THE MANUSCRIPT'S TABLE. The manuscript's incremental
contribution table (tab:incremental-contribution) is built from
paper/numbers_master.csv, which reports the LLM rows per model (best and worst)
rather than for one model at a time -- a breakdown this script has no model
dimension to express. An earlier version of this script wrote
paper/incremental_contribution_table.tex unprompted; that file was never
\\input anywhere, disagreed with the manuscript, and has been removed. Do not
reintroduce an automatic write into paper/.

Sources:
- LLM rows: metrics_summary_{MODEL_KEY}.xlsx (evaluate_architecture_metrics.py)
- Baseline rows: Output Files/Baselines/baseline_metrics.csv
  (run_baseline_models.py -> evaluate_baseline_metrics.py). These used to come
  from `evaluate_architecture_metrics.py --include-baselines`, a flag that is
  accepted but never acted on, which is why both baseline rows previously
  rendered as N/A.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_KEY, get_output_folder

OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
METRICS_FILE = OUTPUT_DIR / f"metrics_summary_{MODEL_KEY}.xlsx"
BASELINE_METRICS_FILE = PROJECT_ROOT / "Output Files" / "Baselines" / "baseline_metrics.csv"

# Aggregation used for the baseline rows. "Overall_pooled" matches what the
# manuscript reports; "Overall_per_type_mean" is also present in the CSV.
BASELINE_AGGREGATE = "Overall_pooled"


def load_metrics(metrics_path):
    """Load metrics summary from Excel file."""
    df = pd.read_excel(metrics_path)
    return df


def extract_key_metrics(metrics_df):
    """Extract key ranking metrics for each architecture."""
    overall = metrics_df[metrics_df['decision_type'] == 'Overall'].copy()
    
    key_metrics = ['top1_accuracy', 'kendall_tau', 'spearman_rho', 'top2_accuracy', 
                   'overall_MAE', 'overall_RMSE', 'n_scenarios_evaluated']
    
    pivot = overall[overall['metric'].isin(key_metrics)].pivot_table(
        index='architecture', columns='metric', values='value', aggfunc='first'
    )
    
    expected_archs = ["FixedDefault", "NearestNeighbor", "Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]
    for arch in expected_archs:
        if arch not in pivot.index:
            pivot.loc[arch] = np.nan

    pivot = pivot.reindex(expected_archs)

    # The metrics summary never contains baseline rows, so fill them from the
    # baseline evaluator's output rather than emitting N/A.
    pivot = _merge_baseline_rows(pivot)
    return pivot


def _merge_baseline_rows(pivot):
    """Fill the FixedDefault / NearestNeighbor rows from baseline_metrics.csv."""
    if not BASELINE_METRICS_FILE.exists():
        print(f"WARNING: {BASELINE_METRICS_FILE} not found -- baseline rows will be N/A.")
        print('  Fix: python "Miscellaneous Scripts/run_baseline_models.py" '
              "--baselines fixed_default nearest_neighbor")
        print('       python "Miscellaneous Scripts/evaluate_baseline_metrics.py"')
        return pivot

    bm = pd.read_csv(BASELINE_METRICS_FILE)
    bm = bm[bm["decision_type"] == BASELINE_AGGREGATE]
    colmap = {
        "top1_accuracy": "top1_accuracy",
        "kendall_tau": "kendall_tau",
        "spearman_rho": "spearman_rho",
        "top2_accuracy": "top2_accuracy",
        "overall_MAE": "overall_MAE",
        "overall_RMSE": "overall_RMSE",
    }
    for name in ("FixedDefault", "NearestNeighbor"):
        sub = bm[bm["baseline"] == name]
        if sub.empty:
            print(f"WARNING: no rows for {name} in {BASELINE_METRICS_FILE.name}")
            continue
        for src, dst in colmap.items():
            vals = sub[sub["metric"] == src]["value"]
            if not vals.empty and dst in pivot.columns:
                pivot.loc[name, dst] = float(vals.iloc[0])
    return pivot


def compute_incremental(pivot, baseline="FixedDefault"):
    """Compute incremental improvements vs baseline (default: FixedDefault)."""
    baseline_row = pivot.loc[baseline]
    
    inc_df = pivot.copy()
    for col in ['top1_accuracy', 'kendall_tau', 'spearman_rho', 'top2_accuracy']:
        if col in pivot.columns:
            inc_df[f'{col}_delta'] = pivot[col] - baseline_row[col]
    
    return inc_df


def format_console_table(pivot, inc_df):
    """Format the incremental contribution table for console output."""
    lines = []
    lines.append("=" * 100)
    lines.append("  INCREMENTAL CONTRIBUTION TABLE -- Top-1 Accuracy & Kendall tau")
    lines.append("=" * 100)
    lines.append("")
    
    # Header
    header = f"{'System':<28} {'Top-1':>8} {'Delta vs FixedDef':>17} {'Kendall tau':>12} {'Delta vs FixedDef':>17}"
    lines.append(header)
    lines.append("-" * len(header))
    
    # Rows
    for arch in pivot.index:
        top1 = pivot.loc[arch, 'top1_accuracy'] if 'top1_accuracy' in pivot.columns else np.nan
        tau = pivot.loc[arch, 'kendall_tau'] if 'kendall_tau' in pivot.columns else np.nan
        
        top1_delta = inc_df.loc[arch, 'top1_accuracy_delta'] if 'top1_accuracy_delta' in inc_df.columns else np.nan
        tau_delta = inc_df.loc[arch, 'kendall_tau_delta'] if 'kendall_tau_delta' in inc_df.columns else np.nan
        
        def fmt(val):
            if pd.isna(val):
                return "   N/A"
            return f"{val:>8.4f}"
        
        def fmt_delta(val):
            if pd.isna(val):
                return "       N/A"
            sign = "+" if val > 0 else ""
            return f"{sign}{val:>12.4f}"
        
        row = f"{arch:<28} {fmt(top1)} {fmt_delta(top1_delta)} {fmt(tau)} {fmt_delta(tau_delta)}"
        lines.append(row)
    
    lines.append("")
    lines.append("=" * 100)
    
    # Additional metrics table
    lines.append("")
    lines.append("  ADDITIONAL METRICS")
    lines.append("=" * 100)
    lines.append(f"{'System':<28} {'Spearman rho':>12} {'Delta':>12} {'Top-2':>8} {'Delta':>12} {'MAE':>8} {'RMSE':>8}")
    lines.append("-" * 80)
    
    for arch in pivot.index:
        rho = pivot.loc[arch, 'spearman_rho'] if 'spearman_rho' in pivot.columns else np.nan
        top2 = pivot.loc[arch, 'top2_accuracy'] if 'top2_accuracy' in pivot.columns else np.nan
        mae = pivot.loc[arch, 'overall_MAE'] if 'overall_MAE' in pivot.columns else np.nan
        rmse = pivot.loc[arch, 'overall_RMSE'] if 'overall_RMSE' in pivot.columns else np.nan
        
        rho_delta = inc_df.loc[arch, 'spearman_rho_delta'] if 'spearman_rho_delta' in inc_df.columns else np.nan
        top2_delta = inc_df.loc[arch, 'top2_accuracy_delta'] if 'top2_accuracy_delta' in inc_df.columns else np.nan
        
        def fmt(val):
            if pd.isna(val):
                return "   N/A"
            return f"{val:>10.4f}"
        
        def fmt_short(val):
            if pd.isna(val):
                return "  N/A"
            return f"{val:>8.4f}"
        
        def fmt_delta(val):
            if pd.isna(val):
                return "     N/A"
            sign = "+" if val > 0 else ""
            return f"{sign}{val:>10.4f}"
        
        row = f"{arch:<28} {fmt(rho)} {fmt_delta(rho_delta)} {fmt_short(top2)} {fmt_delta(top2_delta)} {fmt_short(mae)} {fmt_short(rmse)}"
        lines.append(row)
    
    lines.append("")
    return "\n".join(lines)


def generate_latex_table(pivot, inc_df):
    """Generate LaTeX table for paper inclusion."""
    lines = []
    lines.append("% Diagnostic rendering from generate_baseline_table.py -- single model.")
    lines.append("% NOT the manuscript's table: tab:incremental-contribution is built from")
    lines.append("% paper/numbers_master.csv and reports LLM rows per model.")
    lines.append("")
    lines.append("\\begin{table}[htbp]")
    lines.append("  \\centering")
    lines.append("  \\caption{Incremental contribution of each system over Fixed-Default baseline.}")
    lines.append("  \\label{tab:incremental-contribution}")
    lines.append("  \\begin{tabular}{lcccc}")
    lines.append("    \\toprule")
    lines.append("    System & Top-1 & $\\Delta$ vs FixedDef & Kendall $\\tau$ & $\\Delta$ vs FixedDef \\\\")
    lines.append("    \\midrule")
    
    for arch in pivot.index:
        top1 = pivot.loc[arch, 'top1_accuracy'] if 'top1_accuracy' in pivot.columns else np.nan
        tau = pivot.loc[arch, 'kendall_tau'] if 'kendall_tau' in pivot.columns else np.nan
        
        top1_delta = inc_df.loc[arch, 'top1_accuracy_delta'] if 'top1_accuracy_delta' in inc_df.columns else np.nan
        tau_delta = inc_df.loc[arch, 'kendall_tau_delta'] if 'kendall_tau_delta' in inc_df.columns else np.nan
        
        def fmt_latex(val):
            if pd.isna(val):
                return "N/A"
            return f"{val:.4f}"
        
        def fmt_delta_latex(val):
            if pd.isna(val):
                return "N/A"
            sign = "+" if val > 0 else ""
            return f"${sign}{val:.4f}$"
        
        arch_latex = arch.replace("_", "\\_")
        row = f"    {arch_latex} & {fmt_latex(top1)} & {fmt_delta_latex(top1_delta)} & {fmt_latex(tau)} & {fmt_delta_latex(tau_delta)} \\\\"
        lines.append(row)
    
    lines.append("    \\bottomrule")
    lines.append("  \\end{tabular}")
    lines.append("\\end{table}")
    
    return "\n".join(lines)


def save_csv(pivot, inc_df, output_path):
    """Save combined table as CSV."""
    combined = pivot.copy()
    for col in inc_df.columns:
        if col.endswith('_delta'):
            combined[col] = inc_df[col]
    combined.to_csv(output_path)
    print(f"CSV saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate incremental contribution table from metrics summary")
    parser.add_argument('--metrics-file', type=str, default=str(METRICS_FILE),
                        help=f'Path to metrics_summary_{{MODEL_KEY}}.xlsx (default: {METRICS_FILE})')
    parser.add_argument('--output-latex', type=str, default=None,
                        help='Path to save LaTeX table (default: print to stdout)')
    parser.add_argument('--output-csv', type=str, default=None,
                        help='Path to save CSV table (default: do not save)')
    parser.add_argument('--baseline', type=str, default='FixedDefault',
                        help='Baseline architecture for delta computation (default: FixedDefault)')
    args = parser.parse_args()
    
    metrics_path = Path(args.metrics_file)
    if not metrics_path.exists():
        print(f"ERROR: Metrics file not found: {metrics_path}")
        print("Run: python evaluate_architecture_metrics.py --include-baselines")
        sys.exit(1)
    
    print(f"Loading metrics from: {metrics_path}")
    metrics_df = load_metrics(metrics_path)
    print(f"Loaded {len(metrics_df)} metric rows")
    
    pivot = extract_key_metrics(metrics_df)
    inc_df = compute_incremental(pivot, baseline=args.baseline)
    
    console_output = format_console_table(pivot, inc_df)
    print(console_output)
    
    latex_output = generate_latex_table(pivot, inc_df)
    if args.output_latex:
        with open(args.output_latex, 'w') as f:
            f.write(latex_output)
        print(f"LaTeX table saved to: {args.output_latex}")
    else:
        print("\n--- LaTeX Output ---")
        print(latex_output)
    
    if args.output_csv:
        save_csv(pivot, inc_df, args.output_csv)

    # Deliberately no write into paper/. The manuscript's table comes from
    # numbers_master.csv; an auto-written copy here only ever drifted from it.


if __name__ == "__main__":
    main()
