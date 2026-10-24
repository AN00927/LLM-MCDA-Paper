#!/usr/bin/env python3
"""
evaluate_baseline_metrics.py -- score the non-LLM baselines against ground truth.

Why this exists
---------------
`run_baseline_models.py` produces the baseline predictions but never scores
them, and `evaluate_architecture_metrics.py --include-baselines` accepts the
flag without acting on it, so no code path in the repository turned the
baseline workbooks into Top-1 / Kendall tau. New runs use
`workbooks/current_runs/baselines/`; preserved inputs remain under
`workbooks/older_runs/unclassified_legacy/Baselines/`. The baseline figures
in the manuscript were consequently carried as literals inside
`generate_paper_results_numbers.py`, where they could not be checked and could
not follow a change to the baseline code. This script closes that gap.

It reuses the matching and sentinel-filtering machinery from
`evaluate_architecture_metrics.py` so the baselines are scored by exactly the
same rules as the LLM architectures.

Both pooled and per-decision-type-arithmetic-mean aggregates are emitted,
because the manuscript's baseline rows and its LLM rows have historically used
different ones (see paper/REVISION_NUMBERS.md).

Output: results/current/baselines/baseline_metrics.csv
        columns: baseline, decision_type, metric, value, n_scenarios

Usage:
    python "scripts/analysis/evaluate_baseline_metrics.py"
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Make the checkout root importable when this script is run directly.
for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "common").is_dir():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise RuntimeError("Cannot locate the repository root (common/ package)")

from common.paths import (
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_path,
)
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.sentinel_utils import CRITERIA
from scripts.analysis import evaluate_architecture_metrics as _cm

CURRENT_BASELINE_DIR = PROJECT_ROOT / "workbooks/current_runs/baselines"
LEGACY_BASELINE_DIR = PROJECT_ROOT / "workbooks/older_runs/unclassified_legacy/Baselines"
DEFAULT_OUT_CSV = PROJECT_ROOT / "results/current/baselines/baseline_metrics.csv"

BASELINES = {
    "NearestNeighbor": "baseline_nearestneighbor.xlsx",
}
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]


def load_baseline(path, name):
    """Read a baseline xlsx and rename its columns to the architecture schema."""
    df = pd.read_excel(path)
    df = df.rename(columns={f"{c}_score": c for c in CRITERIA})
    for col in ("question", "location", "alternative"):
        df[col] = df[col].astype(str).str.strip()
    return _cm.load_architecture(df, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--input-dir",
        default=str(CURRENT_BASELINE_DIR),
        help=("directory containing baseline workbook inputs; use "
              f"{LEGACY_BASELINE_DIR} to re-evaluate preserved legacy outputs"),
    )
    parser.add_argument("--output", default=str(DEFAULT_OUT_CSV),
                        help="CSV output path (defaults to results/current/baselines/)")
    args = parser.parse_args(argv)
    baseline_dir = Path(args.input_dir)
    try:
        out_csv = require_safe_output_path(
            args.output, option="--output", root=PROJECT_ROOT
        )
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))
    output_key = os.path.normcase(str(out_csv.resolve()))
    for name, filename in BASELINES.items():
        input_path = (baseline_dir / filename).resolve()
        if output_key == os.path.normcase(str(input_path)):
            parser.error(f"--output would overwrite the {name} input workbook: {input_path}")

    warnings.filterwarnings("ignore")
    config = _cm._build_config("gemini")   # only the GT paths are used
    gt_by_type = _cm.load_ground_truth(config)
    gt_lookup = _cm.build_gt_lookup(gt_by_type)
    gt_id_lookup = _cm.build_gt_id_lookup(gt_by_type)

    rows = []
    for name, fname in BASELINES.items():
        path = baseline_dir / fname
        if not path.exists():
            print(f"  [SKIP] {name}: {path} not found -- run run_baseline_models.py first")
            continue

        arch_df = load_baseline(path, name)
        merged, _ = _cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, name)
        clean, n_failed, n_total = _cm.filter_failed_scenarios(merged)

        # Failure rule, the same as the LLM architectures: metrics are
        # computed on the unfiltered frame, every matched scenario counted.
        per_type = {}
        for dt in DECISION_TYPES:
            sub = merged[merged["decision_type"] == dt]
            if sub.empty:
                continue
            r = _cm.compute_ranking_metrics_inclusive(sub)
            c = _cm.compute_criterion_metrics_inclusive(sub)
            per_type[dt] = r
            for metric, value in [
                ("top1_accuracy", r["top1_accuracy"]),
                ("kendall_tau", r["kendall_tau"]),
                ("spearman_rho", r["spearman_rho"]),
                ("top2_accuracy", r["top2_accuracy"]),
                ("overall_MAE", c["overall_MAE"]),
                ("overall_RMSE", c["overall_RMSE"]),
            ]:
                rows.append({"baseline": name, "decision_type": dt,
                             "metric": metric, "value": value,
                             "n_scenarios": r["n_scenarios_evaluated"]})

        pooled_r = _cm.compute_ranking_metrics_inclusive(merged)
        pooled_c = _cm.compute_criterion_metrics_inclusive(merged)
        for metric, value in [
            ("top1_accuracy", pooled_r["top1_accuracy"]),
            ("kendall_tau", pooled_r["kendall_tau"]),
            ("spearman_rho", pooled_r["spearman_rho"]),
            ("top2_accuracy", pooled_r["top2_accuracy"]),
            ("overall_MAE", pooled_c["overall_MAE"]),
            ("overall_RMSE", pooled_c["overall_RMSE"]),
        ]:
            rows.append({"baseline": name, "decision_type": "Overall_pooled",
                         "metric": metric, "value": value,
                         "n_scenarios": pooled_r["n_scenarios_evaluated"]})

        for metric in ("top1_accuracy", "kendall_tau", "spearman_rho", "top2_accuracy"):
            vals = [per_type[dt][metric] for dt in DECISION_TYPES if dt in per_type]
            rows.append({"baseline": name, "decision_type": "Overall_per_type_mean",
                         "metric": metric, "value": float(np.mean(vals)) if vals else np.nan,
                         "n_scenarios": pooled_r["n_scenarios_evaluated"]})

        print(f"\n  {name}: {clean['arch_scenario_id'].nunique()} scenarios "
              f"({n_failed} sentinel-failed of {n_total} matched)")
        for dt in DECISION_TYPES:
            if dt in per_type:
                print(f"    {dt:10s} n={per_type[dt]['n_scenarios_evaluated']:4d} "
                      f"tau={per_type[dt]['kendall_tau']:.4f} "
                      f"top1={per_type[dt]['top1_accuracy']:.4f}")
        print(f"    {'POOLED':10s} n={pooled_r['n_scenarios_evaluated']:4d} "
              f"tau={pooled_r['kendall_tau']:.4f} top1={pooled_r['top1_accuracy']:.4f}")
        pt_tau = np.mean([per_type[dt]["kendall_tau"] for dt in per_type])
        pt_t1 = np.mean([per_type[dt]["top1_accuracy"] for dt in per_type])
        print(f"    {'PER-TYPE':10s}      tau={pt_tau:.4f} top1={pt_t1:.4f}")

    if not rows:
        print("ERROR: no baselines evaluated")
        return

    df = pd.DataFrame(rows)
    df["value"] = df["value"].astype(float).round(6)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"\n[OK] wrote {out_csv} ({len(df)} rows)")


if __name__ == "__main__":
    main()
