#!/usr/bin/env python3
"""
pipeline_gate.py -- P2 regression gate for the per-run / baseline changes.

Usage:
    python Analysis/rerun_prep/pipeline/pipeline_gate.py before
    python Analysis/rerun_prep/pipeline/pipeline_gate.py after
    python Analysis/rerun_prep/pipeline/pipeline_gate.py diff

`before` and `after` compute the same quantities from whichever version of the
five P2 scripts is live on disk and write before.csv / after.csv (long format)
next to this file. `diff` joins the two and writes diff.csv plus gate.csv.

Nothing here makes an API call, and nothing is written outside
Analysis/rerun_prep/pipeline/: every script whose default output is a shipped
path is either called as a function with its output redirected, or run with an
explicit output argument. Every metric is computed per model; nothing is pooled
across the four models. Failed scenario-runs (1928 sentinel / extraction_failed)
never enter an average.

Quantities (column `quantity`):
  AH_pipeline            Set A from the shipped paper/per_run_metrics CSVs
                         (calculate_per_run_metrics.py output), mean over runs.
                         This is the reference the main text quotes.
  hybrid:<arm>           run_hybrid_ablation_experiments.run() re-executed now.
                         Multi-run arms: per-run mean over scored scenarios,
                         then mean over runs (the paper's estimator).
  DM_like_for_like       dataset-median arm on the scenarios each run of the
                         per-run extracted arm scored, mean over runs.
  DM_param               the constants compute_defaults() returns.
  FD                     run_baseline_models.run_fixed_default_baseline()
                         re-executed now, scored by evaluate_baseline_metrics'
                         machinery (the path behind baseline_metrics.csv).
  FD_like_for_like       FD on the scenarios each A_H run scored.
  FD_appliance_type      appliance type the FD assigns, counted.
  SIG                    test_hybrid_ablation_significance.main() re-executed.
  NUMBERS:<category>     generate_paper_results_numbers.py re-executed.
  EXTRACTION             evaluate_parameter_extraction.evaluate() re-executed.
"""

import argparse
import contextlib
import importlib.util
import io
import os
import runpy
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
for sub in ("Miscellaneous Scripts/core-automation", "Miscellaneous Scripts/experiments",
            "Ground Truth Calculators"):
    p = str(PROJECT_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
warnings.filterwarnings("ignore")

from model_config import MODEL_SPECS  # noqa: E402
from sentinel_utils import read_table_clean, CRITERIA  # noqa: E402

# model_config.py is being repointed at the rerun's folders (P3: Gemini 3.8
# Flash, DeepSeek V4.1 Flash). The data these checks use is the shipped
# collection, so each in-process spec whose folder holds no A_H run files yet
# is redirected to the shipped folder. model_config.py itself is not touched.
SHIPPED_FOLDERS = {"gptoss": "Output Files GPT-OSS 20B", "qwen": "Output Files Qwen3.5 9B",
                   "deepseek": "Output Files DeepSeek V4 Flash",
                   "gemini": "Output Files Gemini 3.5 Flash"}
for _mk, _shipped in SHIPPED_FOLDERS.items():
    if (not list((PROJECT_ROOT / MODEL_SPECS[_mk]["output_folder"]).glob(
            "LLM-Parameterized_Reference_Scoring_results_run_*.xlsx"))
            and (PROJECT_ROOT / _shipped).exists()):
        MODEL_SPECS[_mk]["output_folder"] = _shipped

MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DTYPES = ["HVAC", "Appliance", "Shower"]
AH = "LLM-Parameterized_Reference_Scoring"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


ROWS = []


def add(quantity, model, decision_type, metric, value, note=""):
    ROWS.append({"quantity": quantity, "model": model, "decision_type": decision_type,
                 "metric": metric, "value": value, "note": note})


# ---------------------------------------------------------------------------
# Per-scenario ranking metrics through the pipeline matcher (same rules as
# calculate_per_run_metrics.compute_ranking_metrics_local).
# ---------------------------------------------------------------------------
def per_scenario_rank_metrics(clean):
    out = {}
    for sid in clean["arch_scenario_id"].unique():
        sc = clean[clean["arch_scenario_id"] == sid]
        if len(sc) < 2:
            continue
        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values
        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue
        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            t, _ = stats.kendalltau(gt_r, ar_r)
            t = 0.0 if np.isnan(t) else t
        else:
            t = 1.0 if np.array_equal(gt_r, ar_r) else 0.0
        g1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        a1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        out[sid] = {"tau": t, "top1": float(g1 == a1),
                    "decision_type": sc["decision_type"].iloc[0]}
    return out


def arm_aggregate(g):
    """Paper estimator for one (model, arm) slice of the ablation per_scenario
    frame: per source_run, mean over non-failed scenarios; then mean over runs.
    A single-run arm (source_run == "") reduces to a plain mean."""
    rows = {}
    for dt in ["Overall"] + DTYPES:
        sub = g if dt == "Overall" else g[g["decision_type"] == dt]
        per_run = []
        for tag, r in sub.groupby("source_run"):
            ok = r[~r["failed"].astype(bool)]
            n_fail = len(r) - len(ok)
            per_run.append({
                "tau": ok["kendall_tau"].mean(), "top1": ok["top1"].mean(),
                "mae": ok["mae"].mean(), "n_scored": len(ok), "n_total": len(r),
                # inclusive: a failed scenario counts tau = 0, Top-1 = 1/3
                "tau_incl": ok["kendall_tau"].sum() / len(r) if len(r) else np.nan,
                "top1_incl": (ok["top1"].sum() + n_fail / 3.0) / len(r) if len(r) else np.nan,
            })
        R = pd.DataFrame(per_run)
        rows[dt] = {"kendall_tau": R["tau"].mean(), "top1": R["top1"].mean(),
                    "mae": R["mae"].mean(), "n_runs": len(R),
                    "n_scored": int(R["n_scored"].sum()), "n_total": int(R["n_total"].sum()),
                    "success_rate": R["n_scored"].sum() / R["n_total"].sum(),
                    "tau_inclusive": R["tau_incl"].mean(), "top1_inclusive": R["top1_incl"].mean()}
    return rows


# ---------------------------------------------------------------------------
# A. Set A reference from the shipped per-run metric CSVs
# ---------------------------------------------------------------------------
def section_setA():
    print("[A] Set A from paper/per_run_metrics")
    for mk in MODELS:
        pr = pd.read_csv(PROJECT_ROOT / "paper" / "per_run_metrics" / f"per_run_metrics_{mk}.csv")
        pr = pr[pr["architecture"] == AH]
        for dt in ["Overall"] + DTYPES:
            s = pr[pr["decision_type"] == dt]
            add("AH_pipeline", mk, dt, "kendall_tau", s["kendall_tau"].mean())
            add("AH_pipeline", mk, dt, "top1", s["top1_accuracy"].mean())
            add("AH_pipeline", mk, dt, "mae", s["overall_mae"].mean())
            add("AH_pipeline", mk, dt, "n_scored", s["n_scenarios"].sum())
        ov = pr[pr["decision_type"] == "Overall"]
        add("AH_pipeline", mk, "Overall", "success_rate",
            ov["n_scenarios"].sum() / ov["n_total"].sum())


# ---------------------------------------------------------------------------
# B-C. Hybrid ablation arms, dataset-median condition
# ---------------------------------------------------------------------------
def section_hybrid(work):
    print("[B] hybrid ablation run() (scores every arm; takes a few minutes)")
    hab = _load("run_hybrid_ablation_experiments",
                "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py")
    defaults = quiet(hab.compute_defaults)
    for dt, params in defaults.items():
        for k, v in params.items():
            add("DM_param", "all", dt, k, v)
    args = argparse.Namespace(models=MODELS)
    df = quiet(hab.run, args)
    df.to_csv(work / "hybrid_per_scenario.csv", index=False)
    summary = hab.summarize(df)
    # the significance script reads the same workbook layout run() writes
    with pd.ExcelWriter(work / "hybrid_ablation_summary.xlsx") as xl:
        summary.to_excel(xl, sheet_name="summary", index=False)
        df.to_excel(xl, sheet_name="per_scenario", index=False)
    df["source_run"] = df["source_run"].fillna("").astype(str)
    for (mk, arm), g in df.groupby(["model", "arm"]):
        for dt, m in arm_aggregate(g).items():
            for k, v in m.items():
                add(f"hybrid:{arm}", mk, dt, k, v)

    # dataset-median like-for-like: same scenarios each per-run extracted run scored
    ext_arm = "extracted_per_run" if "extracted_per_run" in set(df["arm"]) else "extracted"
    for mk in MODELS:
        pr = df[(df["model"] == mk) & (df["arm"] == ext_arm)]
        de = df[(df["model"] == mk) & (df["arm"] == "default_params")].set_index("scenario_id")
        for dt in ["Overall"] + DTYPES:
            per_run = []
            for tag, g in pr.groupby("source_run"):
                g = g if dt == "Overall" else g[g["decision_type"] == dt]
                ok = g[~g["failed"].astype(bool)]
                sids = ok["scenario_id"].values
                per_run.append({"ext_tau": ok["kendall_tau"].mean(), "ext_top1": ok["top1"].mean(),
                                "dm_tau": de.loc[sids, "kendall_tau"].mean(),
                                "dm_top1": de.loc[sids, "top1"].mean(),
                                "dm_mae": de.loc[sids, "mae"].mean()})
            R = pd.DataFrame(per_run)
            add("DM_like_for_like", mk, dt, "kendall_tau", R["dm_tau"].mean(), f"arm={ext_arm}")
            add("DM_like_for_like", mk, dt, "top1", R["dm_top1"].mean(), f"arm={ext_arm}")
            add("DM_like_for_like", mk, dt, "mae", R["dm_mae"].mean(), f"arm={ext_arm}")
            add("DM_like_for_like", mk, dt, "tau_gain_AH_minus_DM",
                (R["ext_tau"] - R["dm_tau"]).mean(), f"arm={ext_arm}")
            add("DM_like_for_like", mk, dt, "top1_gain_AH_minus_DM",
                (R["ext_top1"] - R["dm_top1"]).mean(), f"arm={ext_arm}")
    return df, ext_arm


# ---------------------------------------------------------------------------
# D. Fixed-default baseline
# ---------------------------------------------------------------------------
def section_fd(work, hyb_df, ext_arm):
    print("[D] fixed-default baseline")
    rbm = _load("run_baseline_models", "Miscellaneous Scripts/core-automation/run_baseline_models.py")
    ebm = _load("evaluate_baseline_metrics",
                "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py")
    test_df = read_table_clean(PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx")
    fd = quiet(rbm.run_fixed_default_baseline, test_df)
    fd_path = work / "baseline_fixeddefault.xlsx"
    fd.to_excel(fd_path, index=False, engine="openpyxl")
    app = fd[fd["decision_type"] == "Appliance"].drop_duplicates("scenario_id")
    for t, n in app["appliance"].value_counts().items():
        add("FD_appliance_type", "all", "Appliance", str(t), int(n))
    for t, n in app["kwh_per_cycle"].value_counts().items():
        add("FD_kwh_per_cycle", "all", "Appliance", str(t), int(n))

    cm = ebm._cm
    config = cm._build_config("gemini")  # only the GT paths are used
    gt = quiet(cm.load_ground_truth, config)
    arch = quiet(ebm.load_baseline, fd_path, "FixedDefault")
    merged, _ = quiet(cm.match_scenarios, cm.build_gt_lookup(gt), cm.build_gt_id_lookup(gt),
                      arch, "FixedDefault")
    clean, n_failed, n_total = cm.filter_failed_scenarios(merged)
    for dt in DTYPES + ["Overall"]:
        sub = clean if dt == "Overall" else clean[clean["decision_type"] == dt]
        r = cm.compute_ranking_metrics(sub)
        c = cm.compute_criterion_metrics(sub)
        add("FD", "all", dt, "kendall_tau", r["kendall_tau"], "pooled" if dt == "Overall" else "")
        add("FD", "all", dt, "top1", r["top1_accuracy"], "pooled" if dt == "Overall" else "")
        add("FD", "all", dt, "mae", c["overall_MAE"], "pooled" if dt == "Overall" else "")
        add("FD", "all", dt, "n_scored", r["n_scenarios_evaluated"])

    # like-for-like per model: FD on the scenarios each A_H run scored.
    # baseline_fixeddefault scenario_id is the 0-based Test row; the ablation's
    # scenario_id is 1-based (verified row by row in Analysis/pass5/d2).
    fd_ps = {int(k) + 1: v for k, v in per_scenario_rank_metrics(clean).items()}
    for mk in MODELS:
        pr = hyb_df[(hyb_df["model"] == mk) & (hyb_df["arm"] == ext_arm)]
        for dt in ["Overall"] + DTYPES:
            per_run = []
            for tag, g in pr.groupby("source_run"):
                g = g if dt == "Overall" else g[g["decision_type"] == dt]
                ok = g[~g["failed"].astype(bool)]
                sids = [int(s) for s in ok["scenario_id"]]
                per_run.append({"fd_tau": np.mean([fd_ps[s]["tau"] for s in sids]),
                                "fd_top1": np.mean([fd_ps[s]["top1"] for s in sids]),
                                "gain_tau": ok["kendall_tau"].mean()
                                - np.mean([fd_ps[s]["tau"] for s in sids])})
            R = pd.DataFrame(per_run)
            add("FD_like_for_like", mk, dt, "kendall_tau", R["fd_tau"].mean())
            add("FD_like_for_like", mk, dt, "top1", R["fd_top1"].mean())
            add("FD_like_for_like", mk, dt, "tau_gain_AH_minus_FD", R["gain_tau"].mean())


# ---------------------------------------------------------------------------
# E. Significance tests
# ---------------------------------------------------------------------------
def section_sig(work):
    print("[E] provenance significance tests")
    sig = _load("test_hybrid_ablation_significance",
                "Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py")
    sig.SUMMARY_XLSX = work / "hybrid_ablation_summary.xlsx"
    sig.OUT_DIR = work
    old_argv = sys.argv
    sys.argv = ["test_hybrid_ablation_significance.py",
                "--summary", str(work / "hybrid_ablation_summary.xlsx"),
                "--output-dir", str(work)]
    try:
        try:
            quiet(sig.main)
        except SystemExit:
            # pre-change script takes no CLI arguments; its paths are patched above
            sys.argv = ["test_hybrid_ablation_significance.py"]
            quiet(sig.main)
    finally:
        sys.argv = old_argv
    pw = pd.read_excel(work / "hybrid_ablation_pairwise_tests.xlsx")
    for _, r in pw.iterrows():
        note = f"{r['config_i']} vs {r['config_j']}"
        for k in ("p_value", "p_holm", "cliff_delta", "n_pairs"):
            add("SIG", r["model"], "Overall", f"{r['metric']}:{k}", r[k], note)


# ---------------------------------------------------------------------------
# F. generate_paper_results_numbers.py
# ---------------------------------------------------------------------------
def section_numbers(work):
    print("[F] generate_paper_results_numbers.py")
    src_path = PROJECT_ROOT / "paper_pipeline" / "generate_paper_results_numbers.py"
    out = work / "numbers_master.csv"
    src = src_path.read_text(encoding="utf-8")
    # Run in-process (not as a subprocess) so the Gemini folder redirect above
    # applies in both phases.
    old_argv = sys.argv
    if "--output" in src:
        sys.argv = [str(src_path), "--output", str(out)]
        code = src
    else:
        # pre-change script hard-codes its output path; run a patched copy of
        # its source so paper/numbers_master.csv is not overwritten
        sys.argv = [str(src_path)]
        code = src.replace('OUT = "paper/numbers_master.csv"', f'OUT = r"{out}"')
        assert code != src
    cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        quiet(exec, compile(code, str(src_path), "exec"),
              {"__name__": "__main__", "__file__": str(src_path)})
    finally:
        os.chdir(cwd)
        sys.argv = old_argv
    nm = pd.read_csv(out)
    for _, r in nm.iterrows():
        add(f"NUMBERS:{r['category']}", r["model_or_pooled"], r["decision_type"],
            f"{r['architecture']}|{r['metric']}", r["value"])


# ---------------------------------------------------------------------------
# G. Parameter-extraction evaluation (Table tab:extraction_accuracy)
# ---------------------------------------------------------------------------
def section_extraction(work, phase):
    print("[G] evaluate_parameter_extraction")
    epe = _load("evaluate_parameter_extraction",
                "Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py")
    for mk in MODELS:
        folder = PROJECT_ROOT / MODEL_SPECS[mk]["output_folder"]
        md = work / f"parameter_evaluation_{mk}.md"
        if phase == "before":
            args = argparse.Namespace(results=str(folder / f"{AH}_results.xlsx"), output=str(md),
                                      scenario_dir=str(PROJECT_ROOT / "Scenario Files"))
        else:
            old = sys.argv
            sys.argv = ["evaluate_parameter_extraction.py", "--model", mk, "--output", str(md)]
            try:
                args = epe.parse_args()
            finally:
                sys.argv = old
        res = quiet(epe.evaluate, args)
        for _, r in res["numeric_summary"].iterrows():
            add("EXTRACTION", mk, r["decision_type"], f"{r['parameter']}:MAE", r["MAE"])
        for _, r in res["categorical_summary"].iterrows():
            add("EXTRACTION", mk, r["decision_type"], f"{r['parameter']}:accuracy", r["accuracy"])
        for _, r in res["sensitivity_summary"].iterrows():
            add("EXTRACTION", mk, r["decision_type"], f"{r['parameter']}:P_change_given_error",
                r["conditional_change_probability"])


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "before"
    if phase == "diff":
        return diff()
    work = HERE / f"work_{phase}"
    work.mkdir(parents=True, exist_ok=True)
    section_setA()
    hyb_df, ext_arm = section_hybrid(work)
    section_fd(work, hyb_df, ext_arm)
    section_sig(work)
    section_numbers(work)
    section_extraction(work, phase)
    out = pd.DataFrame(ROWS)
    out.insert(0, "phase", phase)
    out.to_csv(HERE / f"{phase}.csv", index=False)
    print(f"Wrote {HERE / (phase + '.csv')} ({len(out)} rows)")


def diff():
    b = pd.read_csv(HERE / "before.csv")
    a = pd.read_csv(HERE / "after.csv")
    key = ["quantity", "model", "decision_type", "metric", "occurrence"]
    for f in (b, a):
        f["occurrence"] = f.groupby(key[:-1]).cumcount()
    m = b.drop(columns=["phase"]).merge(a.drop(columns=["phase"]), on=key, how="outer",
                                        suffixes=("_before", "_after"))

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return np.nan
    vb, va = m["value_before"].map(_num), m["value_after"].map(_num)
    m["delta"] = va - vb
    m["changed"] = ~((m["value_before"].astype(str) == m["value_after"].astype(str))
                     | ((vb - va).abs() < 1e-12))
    m.to_csv(HERE / "diff.csv", index=False)
    print(f"Wrote {HERE / 'diff.csv'} ({len(m)} rows, {int(m['changed'].sum())} changed)")


if __name__ == "__main__":
    main()
