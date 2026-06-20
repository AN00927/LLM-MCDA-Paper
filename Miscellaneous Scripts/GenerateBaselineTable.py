#!/usr/bin/env python3
"""
GenerateBaselineTable.py - Incremental Contribution Table Generator

Reads metrics_summary_{MODEL_KEY}.xlsx (produced by CalculateMetrics.py with --include-baselines)
and prints/saves the incremental contribution table comparing all 8 systems:
- 5 baselines (Random, Uniform, FixedDefault, NearestNeighbor, Oracle)
- 3 LLM architectures (Pure, RAG, LLM-Parameterized_Reference_Scoringrameterized_Reference_Scoring)

Output formats: Console (formatted), LaTeX (paper-ready), CSV (for further analysis)
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


def load_metrics(metrics_path):
    """Load metrics summary from Excel file."""
    df = pd.read_excel(metrics_path)
    return df


def extract_key_metrics(metrics_df):
    """Extract key ranking metrics for each architecture."""
    # Filter for Overall decision type and key metrics
    overall = metrics_df[metrics_df['decision_type'] == 'Overall'].copy()
    
    key_metrics = ['top1_accuracy', 'kendall_tau', 'spearman_rho', 'top2_accuracy', 
                   'overall_MAE', 'overall_RMSE', 'n_scenarios_evaluated']
    
    pivot = overall[overall['metric'].isin(key_metrics)].pivot_table(
        index='architecture', columns='metric', values='value', aggfunc='first'
    )
    
    # Ensure all architectures are present
    expected_archs = ["Random", "Uniform", "FixedDefault", "NearestNeighbor", "Oracle", "Pure", "RAG", "LLM-Parameterized_Reference_Scoringrameterized_Reference_Scoring"]
    for arch in expected_archs:
        if arch not in pivot.index:
            pivot.loc[arch] = np.nan
    
    pivot = pivot.reindex(expected_archs)
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
    lines.append("  INCREMENTAL CONTRIBUTION TABLE — Top-1 Accuracy & Kendall τ")
    lines.append("=" * 100)
    lines.append("")
    
    # Header
    header = f"{'System':<28} {'Top-1':>8} {'Δ vs FixedDef':>14} {'Kendall τ':>10} {'Δ vs FixedDef':>14}"
    lines.append(header)
    lines.append("─" * len(header))
    
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
    lines.append(f"{'System':<28} {'Spearman ρ':>10} {'Δ':>12} {'Top-2':>8} {'Δ':>12} {'MAE':>8} {'RMSE':>8}")
    lines.append("─" * 78)
    
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
    lines.append("% Incremental Contribution Table - Auto-generated by GenerateBaselineTable.py")
    lines.append("% DO NOT EDIT MANUALLY - Regenerate after running CalculateMetrics.py --include-baselines")
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
        
        # Escape underscores for LaTeX
        arch_latex = arch.replace("_", "\\_")
        row = f"    {arch_latex} & {fmt_latex(top1)} & {fmt_delta_latex(top1_delta)} & {fmt_latex(tau)} & {fmt_delta_latex(tau_delta)} \\\\"
        lines.append(row)
    
    lines.append("    \\bottomrule")
    lines.append("  \\end{tabular}")
    lines.append("\\end{table}")
    
    return "\n".join(lines)


def save_csv(pivot, inc_df, output_path):
    """Save combined table as CSV."""
    # Merge pivot and incremental columns
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
        print("Run: python CalculateMetrics.py --include-baselines")
        sys.exit(1)
    
    print(f"Loading metrics from: {metrics_path}")
    metrics_df = load_metrics(metrics_path)
    print(f"Loaded {len(metrics_df)} metric rows")
    
    pivot = extract_key_metrics(metrics_df)
    inc_df = compute_incremental(pivot, baseline=args.baseline)
    
    # Print console table
    console_output = format_console_table(pivot, inc_df)
    print(console_output)
    
    # Generate LaTeX
    latex_output = generate_latex_table(pivot, inc_df)
    if args.output_latex:
        with open(args.output_latex, 'w') as f:
            f.write(latex_output)
        print(f"LaTeX table saved to: {args.output_latex}")
    else:
        print("\n--- LaTeX Output ---")
        print(latex_output)
    
    # Save CSV if requested
    if args.output_csv:
        save_csv(pivot, inc_df, args.output_csv)
    
    # Also save LaTeX to default location in paper directory
    paper_dir = PROJECT_ROOT / "paper"
    if paper_dir.exists():
        default_latex = paper_dir / "incremental_contribution_table.tex"
        with open(default_latex, 'w') as f:
            f.write(latex_output)
        print(f"LaTeX table also saved to: {default_latex}")


if __name__ == "__main__":
    main()