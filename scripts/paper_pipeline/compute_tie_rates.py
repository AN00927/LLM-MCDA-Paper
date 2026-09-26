#!/usr/bin/env python3
"""
compute_tie_rates.py -- per model x architecture (x decision type), the share
of scenario-runs whose aggregate (weighted-sum) score ties across two or more
alternatives before TIE_BREAK_PRIORITY is applied.

This is the statistic behind the supplement's tie-rate table (S L203) and the
D12(c) analysis in paper/pass5/D9_D12_REPORT.md. On current data, A_E should
reproduce 17.3 / 5.8 / 12.7% for DeepSeek / GPT-OSS / Qwen (see that report,
section 8.2, "Any tie (S1 figure)" column) -- this script's own docstring does
not restate the numbers so it cannot drift from them silently; check the report
itself when validating a rerun.

READ-ONLY on existing per-run output files. No API calls. Reuses the same
harness paper_pipeline/calculate_per_run_metrics.py uses (load_architecture,
match_scenarios, filter_failed_scenarios) rather than re-parsing run files, and
the same tie/tie-break definitions as Analysis/pass5/d12_analyses.py (the
reference implementation this was checked against): a weighted-score tie is
two or more alternatives within 1e-9 of the scenario's maximum weighted score,
computed from model_config.CRITERION_WEIGHTS on the architecture's own
criterion scores -- i.e. before sentinel_utils.apply_mavt_ranking's
TIE_BREAK_PRIORITY tie-break is applied.

Usage:
    python paper_pipeline/compute_tie_rates.py
    python paper_pipeline/compute_tie_rates.py --output-dir Analysis/rerun_prep/infra
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

from model_config import MODEL_SPECS, CRITERION_WEIGHTS, TIE_BREAK_PRIORITY  # noqa: E402
from sentinel_utils import CRITERIA  # noqa: E402

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


def wsum(row, prefix="arch_"):
    return sum(CRITERION_WEIGHTS[c] * float(row[f"{prefix}{c}"]) for c in CRITERIA)


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
        out.append((run, clean.copy()))
    return out


def per_scenario_tie_flags(clean_df):
    """One row per scenario:
      any_tie  -- at least two alternatives share a weighted score ANYWHERE in
                  the ranking (the S L203 / D9_D12_REPORT.md 8.2 "Any tie"
                  figure). Two alternatives tying for 2nd/3rd place counts here
                  even though it cannot move Top-1.
      top_tie  -- the stricter, Top-1-relevant condition: two or more
                  alternatives share the TOP weighted score.
      input_order_decided -- within a top_tie, the tied alternatives also match
                  on every TIE_BREAK_PRIORITY criterion, so input order (not
                  criterion priority) decides Top-1.
    """
    rows = []
    for sid, sc in clean_df.groupby("arch_scenario_id", sort=False):
        dt = sc["decision_type"].iloc[0]
        ws = np.array([wsum(r) for _, r in sc.iterrows()])
        any_tie = int(len(np.unique(np.round(ws, 9))) < len(ws))
        top_set = np.where(np.abs(ws - ws.max()) < EPS)[0]
        top_tie = int(len(top_set) > 1)
        input_order_decided = 0
        if top_tie:
            keys = [tuple(round(float(sc.iloc[i][f"arch_{c}"]), 9) for c in TIE_BREAK_PRIORITY)
                    for i in top_set]
            best_key = max(keys)
            if sum(k == best_key for k in keys) > 1:
                input_order_decided = 1
        rows.append(dict(sid=sid, dt=dt, any_tie=any_tie, top_tie=top_tie,
                         input_order_decided=input_order_decided))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                    help="Where to write tie_rates.csv (default: Analysis/).")
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
                flags = per_scenario_tie_flags(clean)
                for dt in ["Overall"] + DECISION_TYPES:
                    s = flags if dt == "Overall" else flags[flags.dt == dt]
                    if not len(s):
                        continue
                    per_run_rows.append(dict(
                        model=model, arch=arch, run=run, decision_type=dt, n=len(s),
                        any_tie_share=s.any_tie.mean(),
                        top_tie_share=s.top_tie.mean(),
                        top_tie_input_order_share=(
                            s.loc[s.top_tie == 1, "input_order_decided"].mean()
                            if s.top_tie.sum() else np.nan),
                    ))

    per_run = pd.DataFrame(per_run_rows)
    per_run_path = out_dir / "tie_rates_per_run.csv"
    per_run.to_csv(per_run_path, index=False)
    print(f"[OK] Wrote {per_run_path} ({len(per_run)} rows)")

    agg = per_run.groupby(["model", "arch", "decision_type"], sort=False).agg(
        n_runs=("run", "nunique"),
        any_tie_share=("any_tie_share", "mean"),
        top_tie_share=("top_tie_share", "mean"),
        top_tie_input_order_share=("top_tie_input_order_share", "mean"),
    ).reset_index()
    summary_path = out_dir / "tie_rates_summary.csv"
    agg.to_csv(summary_path, index=False)
    print(f"[OK] Wrote {summary_path} ({len(agg)} rows)")

    # Quick sanity print for the S L203 cells named in D9_D12_REPORT.md.
    check = agg[(agg.arch == "A_E") & (agg.decision_type == "Overall") &
               (agg.model.isin(["deepseek", "gptoss", "qwen"]))]
    if len(check):
        print("\nA_E any_tie_share, Overall (expect ~17.3/5.8/12.7 for deepseek/gptoss/qwen):")
        print(check[["model", "any_tie_share"]].to_string(index=False))


if __name__ == "__main__":
    main()
