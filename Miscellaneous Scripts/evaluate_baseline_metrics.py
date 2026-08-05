#!/usr/bin/env python3
"""
evaluate_baseline_metrics.py -- score the non-LLM baselines against ground truth.

Why this exists
---------------
`run_baseline_models.py` produces the baseline predictions but never scores
them, and `evaluate_architecture_metrics.py --include-baselines` accepts the
flag without acting on it, so no code path in the repository turned
`Output Files/Baselines/*.xlsx` into Top-1 / Kendall tau. The baseline figures
in the manuscript were consequently carried as literals inside
`generate_paper_results_numbers.py`, where they could not be checked and could
not follow a change to the baseline code. This script closes that gap.

It reuses the matching and sentinel-filtering machinery from
`evaluate_architecture_metrics.py` so the baselines are scored by exactly the
same rules as the LLM architectures.

Both pooled and per-decision-type-arithmetic-mean aggregates are emitted,
because the manuscript's baseline rows and its LLM rows have historically used
different ones (see paper/REVISION_NUMBERS.md).

Output: Output Files/Baselines/baseline_metrics.csv
        columns: baseline, decision_type, metric, value, n_scenarios

Usage:
    python "Miscellaneous Scripts/evaluate_baseline_metrics.py"
"""

import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import CRITERIA

_CM_PATH = Path(__file__).resolve().parent / "evaluate_architecture_metrics.py"
_spec = spec_from_file_location("evaluate_architecture_metrics", _CM_PATH)
_cm = module_from_spec(_spec)
_spec.loader.exec_module(_cm)

BASELINE_DIR = PROJECT_ROOT / "Output Files" / "Baselines"
OUT_CSV = BASELINE_DIR / "baseline_metrics.csv"

BASELINES = {
    "FixedDefault": "baseline_fixeddefault.xlsx",
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


def main():
    warnings.filterwarnings("ignore")
    config = _cm._build_config("gemini")   # only the GT paths are used
    gt_by_type = _cm.load_ground_truth(config)
    gt_lookup = _cm.build_gt_lookup(gt_by_type)
    gt_id_lookup = _cm.build_gt_id_lookup(gt_by_type)

    rows = []
    for name, fname in BASELINES.items():
        path = BASELINE_DIR / fname
        if not path.exists():
            print(f"  [SKIP] {name}: {path} not found -- run run_baseline_models.py first")
            continue

        arch_df = load_baseline(path, name)
        merged, _ = _cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, name)
        clean, n_failed, n_total = _cm.filter_failed_scenarios(merged)

        per_type = {}
        for dt in DECISION_TYPES:
            sub = clean[clean["decision_type"] == dt]
            if sub.empty:
                continue
            r = _cm.compute_ranking_metrics(sub)
            c = _cm.compute_criterion_metrics(sub)
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

        pooled_r = _cm.compute_ranking_metrics(clean)
        pooled_c = _cm.compute_criterion_metrics(clean)
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
    df.to_csv(OUT_CSV, index=False)
    print(f"\n[OK] wrote {OUT_CSV} ({len(df)} rows)")


if __name__ == "__main__":
    main()
