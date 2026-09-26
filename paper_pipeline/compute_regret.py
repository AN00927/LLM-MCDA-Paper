#!/usr/bin/env python3
"""
compute_regret.py -- per-run decision regret for A_D / A_E / A_H, averaged over
runs, per model x architecture (x decision type).

Regret per scenario = reference MAVT value of the reference's top-ranked
alternative minus reference MAVT value of the alternative the architecture
ranks first (0 when the architecture's Top-1 matches the reference's). This is
the D12(b) analysis in paper/pass5/D9_D12_REPORT.md, section 7; that report's
Analysis/pass5/d12_analyses.py is the reference implementation this was
checked against (see the verification note in Analysis/rerun_prep/INFRA_REPORT.md
for the reproduction check against that report's section 7.2 table).

READ-ONLY on existing per-run output files. No API calls. Reuses the same
harness paper_pipeline/calculate_per_run_metrics.py uses (load_architecture,
match_scenarios, filter_failed_scenarios) rather than re-parsing run files.

Usage:
    python paper_pipeline/compute_regret.py
    python paper_pipeline/compute_regret.py --output-dir Analysis/rerun_prep/infra
"""
import argparse
import contextlib
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "paper_pipeline") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "paper_pipeline"))
warnings.filterwarnings("ignore")

with contextlib.redirect_stdout(io.StringIO()):
    import calculate_per_run_metrics as cprm  # noqa: E402

MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
ARCHS = {
    "A_D": "Direct_LLM_Scoring",
    "A_E": "Example-Guided_LLM_Scoring",
    "A_H": "LLM-Parameterized_Reference_Scoring",
}
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
EPS = 1e-9

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "Analysis"


def load_runs(model_key, arch_stem):
    """(run_num, clean merged df) per run file, matching d12_analyses.load_runs."""
    config = cprm._build_config(model_key)
    folder = Path(config["output_csv"]).parent
    gt_by_type = cprm.load_ground_truth(config)
    gt_lookup = cprm.build_gt_lookup(gt_by_type)
    gt_id_lookup = cprm.build_gt_id_lookup(gt_by_type)
    out = []
    for p in cprm._discover_run_files(folder, arch_stem):
        run = int(p.stem.split("_run_")[-1])
        with contextlib.redirect_stdout(io.StringIO()):
            arch_df = cprm.load_architecture(p, arch_stem)
            merged, _ = cprm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_stem)
        clean, n_failed, n_total = cprm.filter_failed_scenarios(merged)
        clean = clean.copy()
        clean["gt_mavt_score"] = clean["gt_mavt_score"].astype(float)
        out.append((run, clean))
    return out


def per_scenario_regret(clean_df):
    """One row per scenario: regret, whether the architecture's Top-1 hit the
    reference's, and the regret a uniformly-random pick would take on average
    (same definition as Analysis/pass5/d12_analyses.py)."""
    rows = []
    for sid, sc in clean_df.groupby("arch_scenario_id", sort=False):
        dt = sc["decision_type"].iloc[0]
        gm = sc["gt_mavt_score"].values
        gt_top_idx = sc["gt_rank"].astype(float).values.argmin()
        ar_top_idx = sc["arch_rank"].astype(float).values.argmin()
        best = gm[gt_top_idx]
        regret = best - gm[ar_top_idx]
        rand_regret = float(np.mean(best - gm))
        hit = float(sc["norm_alternative"].values[gt_top_idx] ==
                    sc["norm_alternative"].values[ar_top_idx])
        rows.append(dict(sid=sid, dt=dt, regret=regret, rand_regret=rand_regret, hit=hit))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                    help="Where to write regret CSVs (default: Analysis/).")
    args = ap.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_run_rows = []
    for model in MODELS:
        for arch, stem in ARCHS.items():
            print(f"[{model}] {arch} ...")
            try:
                runs = load_runs(model, stem)
            except Exception as exc:
                print(f"  [SKIP] {model}/{arch}: {exc}")
                continue
            for run, clean in runs:
                if clean.empty:
                    continue
                ps = per_scenario_regret(clean)
                for dt in ["Overall"] + DECISION_TYPES:
                    s = ps if dt == "Overall" else ps[ps.dt == dt]
                    if not len(s):
                        continue
                    miss = s[s.hit == 0]
                    per_run_rows.append(dict(
                        model=model, arch=arch, run=run, decision_type=dt, n=len(s),
                        mean_regret=s.regret.mean(),
                        zero_regret_share=(s.regret.abs() < EPS).mean(),
                        top1=s.hit.mean(), n_miss=len(miss),
                        mean_regret_given_miss=miss.regret.mean() if len(miss) else np.nan,
                        random_pick_regret=s.rand_regret.mean(),
                    ))

    per_run = pd.DataFrame(per_run_rows)
    per_run_path = out_dir / "decision_regret_per_run.csv"
    per_run.to_csv(per_run_path, index=False)
    print(f"[OK] Wrote {per_run_path} ({len(per_run)} rows)")

    agg = {c: "mean" for c in ["n", "mean_regret", "zero_regret_share", "top1", "n_miss",
                               "mean_regret_given_miss", "random_pick_regret"]}
    summary = per_run.groupby(["model", "arch", "decision_type"], sort=False).agg(agg).reset_index()
    summary["n_runs"] = per_run.groupby(["model", "arch", "decision_type"], sort=False).size().values
    summary_path = out_dir / "decision_regret_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"[OK] Wrote {summary_path} ({len(summary)} rows)")

    check = summary[summary.decision_type == "Overall"].pivot(index="model", columns="arch", values="mean_regret")
    print("\nMean regret, Overall (compare to D9_D12_REPORT.md sec. 7.2):")
    print(check.to_string())


if __name__ == "__main__":
    main()
