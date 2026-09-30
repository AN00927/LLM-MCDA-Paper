#!/usr/bin/env python3
"""
build_numbers_of_record.py -- regenerate every row of
paper/pass5/NUMBERS_OF_RECORD.csv that still exists in the study design, from
the outputs the pipeline and the experiment scripts write, so a fresh rerun's
numbers can be diffed against the ones on record without hand-checking each cell.

Inputs (each overridable; defaults are where the scripts write):
  per-run metrics    paper/per_run_metrics/per_run_metrics_all.csv
                     (paper_pipeline/calculate_per_run_metrics.py)
  hybrid summary     Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx,
                     sheets `summary` and `per_scenario`
                     (Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py)
  pairwise tests     Analysis/Hybrid_Ablation/hybrid_ablation_pairwise_tests.xlsx
                     (Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py)
  baseline metrics   Output Files/Baselines/baseline_metrics.csv
                     (Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py)
  fixed default      Output Files/Baselines/baseline_fixeddefault.xlsx
                     (run_baseline_models.py; scored here per scenario for the
                     like-for-like A_H - FD gaps)
  numbers master     paper/numbers_master.csv, category GPTOSS_recovery
                     (paper_pipeline/generate_paper_results_numbers.py)

The arithmetic is the one Analysis/rerun_prep/pipeline/pipeline_gate.py used to
reproduce these rows on the shipped data (arm_aggregate, the dataset-median and
fixed-default like-for-like blocks, per_scenario_rank_metrics), ported here.
Every metric is per model; nothing is pooled across models. Failure rule (S4,
2026-09-29): a failed scenario-run stays in every denominator at chance-level
values (Top-1 wrong, tau 0, MAE the uniform-guess error). per_run_metrics and
the hybrid workbook already carry it, so the "inclusive" rows now equal the
headline rows; their old basis (Top-1 counted at 1/3) is retired.

SCOPE. The record covers A_H, parameter provenance, the dataset-median and
fixed-default rows and the provenance SIG rows only. Every other number the
paper prints (A_D / A_E results, the prompt, RAG, position-bias and listwise
ablations, the NN copy baseline, costs, sensitivity) is NOT in this diff; the
runbook (step 7, "Where every other number comes from") lists their sources.

The hybrid workbook's per-run A_H arm is `extracted` in the current harness. A
workbook written by the older harness (the shipped one) has the per-run arm as
`extracted_per_run` and a five-run consensus arm as `extracted`; the per-run arm
is used in both cases.

Retired rows (no longer part of the design; reported as status "retired" with
the reason, never regenerated):
  PROV_extracted_*        Set B: the five-run consensus-parameter arm, removed
                          from the harness. The provenance table's extracted
                          row is now the per-run A_H value (the AH_* rows).
  PROV_gptoss_194of195    Set B count (a scenario counted if any run succeeded).

Gate (--strict): every regenerated row must equal the value on record at the
precision the record prints, else exit 1. Without --strict the comparison is
reported and the exit code is 0, since after the rerun most rows are expected
to move (run_paper_pipeline.py calls this without --strict). Two rows carry a value the record
itself marks "mismatch" (the paper's printed number disagrees with the
documented computation); for those the regenerated value is checked against the
reproduction written in the record's basis_notes instead (KNOWN_RECORD_ERRORS).

READ-ONLY on paper/pass5/: writes numbers_of_record_regenerated.csv (the
record's columns plus regen_value / regen_status / regen_note /
regen_matches_value / expected_value) to --output-dir.

Usage:
    python paper_pipeline/build_numbers_of_record.py --output-dir <scratch dir> [--strict]
"""
import argparse
import contextlib
import importlib.util
import io
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SOURCE_CSV = PROJECT_ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD.csv"
PER_RUN_METRICS_CSV = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
HYBRID_SUMMARY_XLSX = PROJECT_ROOT / "Analysis" / "Hybrid_Ablation" / "hybrid_ablation_summary.xlsx"
PAIRWISE_XLSX = PROJECT_ROOT / "Analysis" / "Hybrid_Ablation" / "hybrid_ablation_pairwise_tests.xlsx"
BASELINE_METRICS_CSV = PROJECT_ROOT / "Output Files" / "Baselines" / "baseline_metrics.csv"
BASELINE_FD_XLSX = PROJECT_ROOT / "Output Files" / "Baselines" / "baseline_fixeddefault.xlsx"
NUMBERS_MASTER_CSV = PROJECT_ROOT / "paper" / "numbers_master.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "Analysis"

AH_ARCH = "LLM-Parameterized_Reference_Scoring"
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DTYPES = ["HVAC", "Appliance", "Shower"]

# number_id patterns, matched in order.
RE_SIMPLE = re.compile(r"^AH_(tau|top1|mae|success)_(deepseek|gemini|gptoss|qwen)$")
RE_INCLUSIVE = re.compile(r"^AH_(tau|top1)_inclusive_(deepseek|gemini|gptoss|qwen)$")
RE_BY_TYPE = re.compile(r"^AH_tau_(deepseek|gemini|gptoss|qwen)_(HVAC|Appliance|Shower)$")
RE_RANGE_TAU = re.compile(r"^AH_tau_range_L\d+$")
RE_RANGE_TOP1 = re.compile(r"^AH_top1_range_L\d+$")
RE_DTAU_FD = re.compile(r"^AH_dtau_vs_FD_(deepseek|gemini|gptoss|qwen)_not_in_paper$")
RE_PROV_SETB = re.compile(r"^PROV_extracted_")
RE_PROV_MEDIAN = re.compile(r"^PROV_median_(deepseek|gemini|gptoss|qwen)$")
RE_MEDIAN_TYPE = re.compile(r"^MEDIAN_tau_(HVAC|Appliance|Shower)$")
RE_FD = re.compile(r"^FD_tau_(overall|HVAC|Appliance|Shower)$")
RE_EFFECT = re.compile(r"^EFFECT_like_for_like_(deepseek|gemini|gptoss|qwen)(?:_(HVAC|Appliance|Shower))?$")
RE_SIG = re.compile(r"^SIG_cliff_(kendall_tau|top1|mae)_(deepseek|gemini|gptoss|qwen)$")

RETIRED = {
    "PROV_gptoss_194of195": "Set B count (consensus arm, a scenario counted if any run "
                            "succeeded); the arm is no longer in the harness",
}
SETB_REASON = ("Set B: five-run consensus-parameter arm, removed from the harness; the "
               "provenance table's extracted row is now the per-run A_H value (AH_* rows)")

# Rows whose value on record is the paper's printed number, which the record
# itself flags as wrong ("mismatch"); the regenerated value is checked against
# the reproduction in the record's basis_notes instead.
KNOWN_RECORD_ERRORS = {
    "AH_gptoss_recovery_tau": ("0.904", "record basis_notes: backfill recomputed tau 0.9045; "
                                        "the paper's 0.897 is the non-recovered value"),
    "EFFECT_range_text": ("0.24-0.30", "record basis_notes: like-for-like range 0.239-0.300; "
                                       "the paper's 0.24-0.28 mixes two scenario bases"),
}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class Sources:
    """Lazy loaders; a missing input leaves its rows not_regenerated with a reason."""

    def __init__(self, args):
        self.args = args
        self._cache = {}

    def _get(self, key, loader):
        if key not in self._cache:
            try:
                self._cache[key] = (loader(), None)
            except Exception as exc:  # recorded per row, never silent
                self._cache[key] = (None, f"{type(exc).__name__}: {exc}")
        return self._cache[key]

    def prm(self):
        return self._get("prm", lambda: pd.read_csv(self.args.per_run_metrics))

    def hybrid(self):
        def load():
            xl = pd.ExcelFile(self.args.hybrid_summary)
            ps = xl.parse("per_scenario")
            ps["source_run"] = ps["source_run"].fillna("").astype(str)
            arms = set(ps["arm"])
            per_run_arm = "extracted_per_run" if "extracted_per_run" in arms else "extracted"
            return {"per_scenario": ps, "per_run_arm": per_run_arm}
        return self._get("hybrid", load)

    def pairwise(self):
        return self._get("pairwise", lambda: pd.read_excel(self.args.pairwise))

    def baseline_metrics(self):
        return self._get("bm", lambda: pd.read_csv(self.args.baseline_metrics))

    def fd_per_scenario(self):
        return self._get("fd_ps", lambda: _fd_per_scenario(Path(self.args.baseline_fd)))

    def numbers_master(self):
        return self._get("nm", lambda: pd.read_csv(self.args.numbers_master))


def _load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


def per_scenario_rank_metrics(clean):
    """tau and Top-1 per scenario through the pipeline matcher, same rules as
    calculate_per_run_metrics.compute_ranking_metrics_local (pipeline_gate.py)."""
    import scipy.stats as stats
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


def _fd_per_scenario(path):
    """Fixed-default tau / Top-1 per Test scenario, keyed by the 1-based Test
    row the hybrid harness uses (baseline_fixeddefault's scenario_id is the
    0-based row; verified row by row in Analysis/pass5/d2)."""
    if not path.exists():
        raise FileNotFoundError(path)
    ebm = _load_module("evaluate_baseline_metrics",
                       "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py")
    cm = ebm._cm
    with contextlib.redirect_stdout(io.StringIO()):
        gt = cm.load_ground_truth(cm._build_config("gemini"))  # only the GT paths are used
        arch = ebm.load_baseline(path, "FixedDefault")
        merged, _ = cm.match_scenarios(cm.build_gt_lookup(gt), cm.build_gt_id_lookup(gt),
                                       arch, "FixedDefault")
    clean, _, _ = cm.filter_failed_scenarios(merged)
    return {int(k) + 1: v for k, v in per_scenario_rank_metrics(clean).items()}


# ---------------------------------------------------------------------------
# Arithmetic (ported from pipeline_gate.py)
# ---------------------------------------------------------------------------
def _per_run_agg(prm, model, decision_type):
    sub = prm[(prm.model == model) & (prm.architecture == AH_ARCH) &
              (prm.decision_type == decision_type)]
    if sub.empty:
        return None
    return dict(
        tau=round(float(sub.kendall_tau.mean()), 3),
        top1=round(float(sub.top1_accuracy.mean()) * 100, 1),
        mae=round(float(sub.overall_mae.mean()), 3),
        success=round(float((sub.n_scenarios / sub.n_total).mean()) * 100, 1),
        n_failed_total=int(sub.n_failed.sum()),
        # Failure rule (S4): per_run_metrics already keeps every failed
        # scenario-run in the denominator (tau 0, Top-1 wrong), so the
        # inclusive value IS the headline value.
        tau_inclusive=round(float(sub.kendall_tau.mean()), 3),
        top1_inclusive=round(float(sub.top1_accuracy.mean()) * 100, 1),
    )


def _run_slices(ps, model, arm, decision_type):
    g = ps[(ps["model"] == model) & (ps["arm"] == arm)]
    if decision_type != "Overall":
        g = g[g["decision_type"] == decision_type]
    return g


def arm_mean(ps, model, arm, decision_type, col):
    """Paper estimator: per source_run, mean over ALL scenarios (a failed one
    carries the failure rule's chance-level value, S4); then mean over runs. A
    single-run arm reduces to a plain mean."""
    g = _run_slices(ps, model, arm, decision_type)
    if g.empty:
        return np.nan
    vals = [r[col].mean() for _, r in g.groupby("source_run")]
    return float(np.mean(vals))


def like_for_like_gain(ps, per_run_arm, model, decision_type, other):
    """A_H minus `other` on the same scenarios, run by run, then the mean over
    runs. Every scenario is in (failure rule S4). `other` is 'dm'
    (dataset-median arm of the same workbook) or a {scenario_id: {"tau": ...}}
    map (fixed default)."""
    ext = _run_slices(ps, model, per_run_arm, decision_type)
    if ext.empty:
        return np.nan, np.nan
    if isinstance(other, str):
        dm = ps[(ps["model"] == model) & (ps["arm"] == "default_params")].set_index("scenario_id")
        ref = lambda sids: dm.loc[sids, "kendall_tau"].mean()  # noqa: E731
    else:
        ref = lambda sids: np.mean([other[int(s)]["tau"] for s in sids])  # noqa: E731
    gains, refs = [], []
    for _, r in ext.groupby("source_run"):
        base = ref(r["scenario_id"].values)
        refs.append(base)
        gains.append(r["kendall_tau"].mean() - base)
    return float(np.mean(gains)), float(np.mean(refs))


def _signed(v, nd=3):
    return f"{v:+.{nd}f}"


# ---------------------------------------------------------------------------
# Row regeneration
# ---------------------------------------------------------------------------
def regenerate(row, src):
    """(regen_value, regen_status, regen_note) for one record row."""
    nid = row["number_id"]

    # ---- retired rows
    if RE_PROV_SETB.match(nid):
        return None, "retired", SETB_REASON
    if nid in RETIRED:
        return None, "retired", RETIRED[nid]

    # ---- per-run metrics (A_H, Set A)
    needs_prm = (RE_SIMPLE.match(nid) or RE_INCLUSIVE.match(nid) or RE_BY_TYPE.match(nid)
                 or RE_RANGE_TAU.match(nid) or RE_RANGE_TOP1.match(nid)
                 or nid in ("AH_table_best_tau", "AH_table_worst_tau", "AH_failures_total",
                            "AH_gptoss_success_weighted_tau_text",
                            "AH_gptoss_success_weighted_top1_text"))
    if needs_prm:
        prm, err = src.prm()
        if prm is None:
            return None, "not_regenerated", f"per-run metrics unavailable ({err})"
        overall = {mk: _per_run_agg(prm, mk, "Overall") for mk in MODELS}
        overall = {mk: v for mk, v in overall.items() if v is not None}

        m = RE_SIMPLE.match(nid)
        if m:
            metric, model = m.groups()
            if model not in overall:
                return None, "not_regenerated", "no per_run_metrics_all.csv rows for this model"
            return overall[model][metric], "regenerated", "mean over runs, per_run_metrics_all.csv"
        m = RE_INCLUSIVE.match(nid)
        if m:
            metric, model = m.groups()
            if model not in overall:
                return None, "not_regenerated", "no per_run_metrics_all.csv rows for this model"
            return (overall[model][f"{metric}_inclusive"], "regenerated",
                    "failure rule S4: failed scenario-runs at tau 0 / Top-1 wrong over all "
                    "n_total (equals the headline value); mean over runs")
        if nid in ("AH_gptoss_success_weighted_tau_text", "AH_gptoss_success_weighted_top1_text"):
            if "gptoss" not in overall:
                return None, "not_regenerated", "no gptoss rows"
            key = "tau_inclusive" if "tau" in nid else "top1_inclusive"
            return (overall["gptoss"][key], "regenerated",
                    "the inclusive value (failed scenario-runs at chance), which is what the text quotes")
        m = RE_BY_TYPE.match(nid)
        if m:
            model, dtype = m.groups()
            agg = _per_run_agg(prm, model, dtype)
            if agg is None:
                return None, "not_regenerated", "no per_run_metrics_all.csv rows for this model/type"
            return agg["tau"], "regenerated", f"mean over runs, per_run_metrics_all.csv, {dtype}"
        if RE_RANGE_TAU.match(nid) or nid in ("AH_table_best_tau", "AH_table_worst_tau"):
            taus = {mk: v["tau"] for mk, v in overall.items()}
            if not taus:
                return None, "not_regenerated", "no per-model tau available"
            lo_model, lo = min(taus.items(), key=lambda kv: kv[1])
            hi_model, hi = max(taus.items(), key=lambda kv: kv[1])
            if nid == "AH_table_best_tau":
                return hi, "regenerated", f"max over models ({hi_model})"
            if nid == "AH_table_worst_tau":
                return lo, "regenerated", f"min over models ({lo_model})"
            return f"{lo:.3f}-{hi:.3f}", "regenerated", f"min({lo_model})-max({hi_model}) over models"
        if RE_RANGE_TOP1.match(nid):
            vals = {mk: v["top1"] for mk, v in overall.items()}
            lo_model, lo = min(vals.items(), key=lambda kv: kv[1])
            hi_model, hi = max(vals.items(), key=lambda kv: kv[1])
            return f"{lo:.1f}-{hi:.1f}", "regenerated", f"min({lo_model})-max({hi_model}) over models"
        if nid == "AH_failures_total":
            parts = {mk: v["n_failed_total"] for mk, v in overall.items()}
            detail = "/".join(f"{mk}={parts[mk]}" for mk in MODELS if mk in parts)
            return sum(parts.values()), "regenerated", f"sum of n_failed over runs per model ({detail})"

    # ---- A_H minus fixed default, as the paper's table prints it: the model's
    # A_H tau (mean over runs) minus the FD row's tau over all 195 scenarios
    if nid in ("AH_table_best_dtau_vs_FD", "AH_table_worst_dtau_vs_FD"):
        prm, err = src.prm()
        if prm is None:
            return None, "not_regenerated", f"per-run metrics unavailable ({err})"
        bm, err = src.baseline_metrics()
        if bm is None:
            return None, "not_regenerated", f"baseline_metrics.csv unavailable ({err})"
        sub = prm[(prm.architecture == AH_ARCH) & (prm.decision_type == "Overall")]
        taus = sub.groupby("model")["kendall_tau"].mean().to_dict()
        pick = max if nid == "AH_table_best_dtau_vs_FD" else min
        model = pick(taus, key=taus.get)
        fd = bm[(bm["baseline"] == "FixedDefault") & (bm["decision_type"] == "Overall_pooled")
                & (bm["metric"] == "kendall_tau")]["value"]
        if fd.empty:
            return None, "not_regenerated", "no FixedDefault Overall_pooled kendall_tau"
        fd_tau = float(fd.iloc[0])
        return (_signed(taus[model] - fd_tau), "regenerated",
                f"{'best' if pick is max else 'worst'} A_H model by tau ({model}): A_H tau "
                f"{taus[model]:.4f} minus FD tau over all 195 ({fd_tau:.4f}), the table's basis")

    # ---- A_H minus fixed default, like-for-like (FD on the scenarios each A_H run scored)
    if RE_DTAU_FD.match(nid):
        hyb, err = src.hybrid()
        if hyb is None:
            return None, "not_regenerated", f"hybrid summary unavailable ({err})"
        fd, err = src.fd_per_scenario()
        if fd is None:
            return None, "not_regenerated", f"fixed-default baseline unavailable ({err})"
        model = RE_DTAU_FD.match(nid).group(1)
        gain, fd_tau = like_for_like_gain(hyb["per_scenario"], hyb["per_run_arm"], model,
                                          "Overall", fd)
        return (_signed(gain), "regenerated",
                f"{model}: A_H tau minus FD tau on the scenarios each A_H run scored "
                f"(FD {fd_tau:.4f}), mean over runs; arm={hyb['per_run_arm']}")

    # ---- failure detail from the per-scenario frame
    if nid in ("AH_gptoss_failures_HVAC", "AH_gptoss_failed_all_runs"):
        hyb, err = src.hybrid()
        if hyb is None:
            return None, "not_regenerated", f"hybrid summary unavailable ({err})"
        g = _run_slices(hyb["per_scenario"], "gptoss", hyb["per_run_arm"], "Overall")
        failed = g[g["failed"].astype(bool)]
        if nid == "AH_gptoss_failures_HVAC":
            n_hvac = int((failed["decision_type"] == "HVAC").sum())
            text = f"{n_hvac} (all HVAC)" if n_hvac == len(failed) else f"{n_hvac} (of {len(failed)})"
            return text, "regenerated", f"failed scenario-runs by type, arm={hyb['per_run_arm']}"
        n_runs = g["source_run"].nunique()
        per_sid = failed.groupby("scenario_id")["source_run"].nunique()
        return (int((per_sid == n_runs).sum()), "regenerated",
                f"scenarios failed in all {n_runs} runs, arm={hyb['per_run_arm']}")

    # ---- GPT-OSS recovery (numbers_master)
    if nid == "AH_gptoss_recovery_tau":
        nm, err = src.numbers_master()
        if nm is None:
            return None, "not_regenerated", f"numbers_master unavailable ({err})"
        s = nm[(nm["category"] == "GPTOSS_recovery") & (nm["model_or_pooled"] == "recovered_5run")
               & (nm["metric"] == "tau")]
        if s.empty:
            return (None, "not_regenerated",
                    "numbers_master.csv has no GPTOSS_recovery/recovered_5run row (written by the "
                    "current generate_paper_results_numbers.py; the file predates it)")
        return (round(float(s["value"].iloc[0]), 3), "regenerated",
                "numbers_master GPTOSS_recovery recovered_5run tau")

    # ---- dataset-median arm (hybrid workbook)
    if (nid in ("MEDIAN_tau_text", "MEDIAN_top1_text", "MEDIAN_tau_gptoss_same_scenarios",
                "EFFECT_range_text")
            or RE_MEDIAN_TYPE.match(nid) or RE_PROV_MEDIAN.match(nid) or RE_EFFECT.match(nid)):
        hyb, err = src.hybrid()
        if hyb is None:
            return None, "not_regenerated", f"hybrid summary unavailable ({err})"
        ps, arm = hyb["per_scenario"], hyb["per_run_arm"]
        dm_model = "deepseek"  # the dataset-median arm is model-independent
        if nid == "MEDIAN_tau_text":
            return round(arm_mean(ps, dm_model, "default_params", "Overall", "kendall_tau"), 3), \
                "regenerated", "default_params arm, all 195"
        if nid == "MEDIAN_top1_text":
            return round(arm_mean(ps, dm_model, "default_params", "Overall", "top1") * 100, 1), \
                "regenerated", "default_params arm, all 195"
        m = RE_MEDIAN_TYPE.match(nid)
        if m:
            dt = m.group(1)
            return round(arm_mean(ps, dm_model, "default_params", dt, "kendall_tau"), 3), \
                "regenerated", f"default_params arm, {dt}"
        m = RE_PROV_MEDIAN.match(nid)
        if m:
            model = m.group(1)
            vals = [arm_mean(ps, model, "default_params", "Overall", c)
                    for c in ("kendall_tau", "top1", "mae")]
            return " / ".join(f"{v:.3f}" for v in vals), "regenerated", \
                "default_params arm tau / Top-1 / MAE"
        if nid == "MEDIAN_tau_gptoss_same_scenarios":
            _, dm_tau = like_for_like_gain(ps, arm, "gptoss", "Overall", "dm")
            return round(dm_tau, 3), "regenerated", \
                f"default_params on the scenarios each gptoss run scored, mean over runs; arm={arm}"
        m = RE_EFFECT.match(nid)
        if m:
            model, dt = m.group(1), m.group(2) or "Overall"
            gain, _ = like_for_like_gain(ps, arm, model, dt, "dm")
            val = round(gain, 3) if dt == "Overall" else _signed(gain)
            return val, "regenerated", f"like-for-like A_H minus dataset median, {dt}; arm={arm}"
        if nid == "EFFECT_range_text":
            gains = [like_for_like_gain(ps, arm, mk, "Overall", "dm")[0] for mk in MODELS
                     if not _run_slices(ps, mk, arm, "Overall").empty]
            return f"{min(gains):.2f}-{max(gains):.2f}", "regenerated", \
                "min-max over models of the like-for-like gain"

    # ---- fixed default (baseline_metrics.csv)
    m = RE_FD.match(nid)
    if m:
        bm, err = src.baseline_metrics()
        if bm is None:
            return None, "not_regenerated", f"baseline_metrics.csv unavailable ({err})"
        dt = "Overall_pooled" if m.group(1) == "overall" else m.group(1)
        s = bm[(bm["baseline"] == "FixedDefault") & (bm["decision_type"] == dt)
               & (bm["metric"] == "kendall_tau")]
        if s.empty:
            return None, "not_regenerated", f"no FixedDefault kendall_tau row for {dt}"
        return round(float(s["value"].iloc[0]), 3), "regenerated", f"baseline_metrics.csv, {dt}"

    # ---- provenance significance (pairwise tests)
    m = RE_SIG.match(nid)
    if m:
        metric, model = m.groups()
        pw, err = src.pairwise()
        if pw is None:
            return None, "not_regenerated", f"pairwise tests unavailable ({err})"
        s = pw[(pw["model"] == model) & (pw["metric"] == metric)
               & (pw[["config_i", "config_j"]].isin(["default_params", "extracted"]).all(axis=1))]
        if s.empty:
            return None, "not_regenerated", "no extracted vs default_params row"
        return round(float(s["cliff_delta"].iloc[0]), 3), "regenerated", \
            f"Cliff's delta, {s['config_i'].iloc[0]} vs {s['config_j'].iloc[0]}"

    return None, "not_regenerated", f"no rule for this row (owner: {row['computing_script']})"


# ---------------------------------------------------------------------------
# Comparison at the record's printed precision
# ---------------------------------------------------------------------------
_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _decimals(tok):
    return len(tok.split(".")[1]) if "." in tok else 0


def values_match(record_value, regen_value):
    """True if every number in the record string equals the regenerated one
    rounded to the record's decimals, and the non-numeric text agrees."""
    rec, new = str(record_value).strip(), str(regen_value).strip()
    rec_nums, new_nums = _NUM.findall(rec), _NUM.findall(new)
    if not rec_nums:
        return rec == new
    if len(rec_nums) != len(new_nums):
        return False
    if _NUM.sub("#", rec).replace("+", "") != _NUM.sub("#", new).replace("+", ""):
        return False
    for r, n in zip(rec_nums, new_nums):
        d = _decimals(r)
        if round(float(n), d) != round(float(r), d):
            return False
    return True


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                    help="Where to write numbers_of_record_regenerated.csv (default: Analysis/).")
    ap.add_argument("--record", default=str(SOURCE_CSV))
    ap.add_argument("--per-run-metrics", default=str(PER_RUN_METRICS_CSV))
    ap.add_argument("--hybrid-summary", default=str(HYBRID_SUMMARY_XLSX))
    ap.add_argument("--pairwise", default=str(PAIRWISE_XLSX))
    ap.add_argument("--baseline-metrics", default=str(BASELINE_METRICS_CSV))
    ap.add_argument("--baseline-fd", default=str(BASELINE_FD_XLSX))
    ap.add_argument("--numbers-master", default=str(NUMBERS_MASTER_CSV))
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if any regenerated row differs from the record "
                         "(the pre-rerun gate on the shipped data).")
    ap.add_argument("--allow-deviation", nargs="*", default=[],
                    help="number_ids allowed to differ from the record (e.g. the known "
                         "Gemini A_H tie cells), reported but not counted as failures.")
    args = ap.parse_args()
    out_dir = Path(args.output_dir)
    record_path = Path(args.record)
    if out_dir.resolve() == record_path.parent.resolve():
        raise SystemExit("Refusing to write next to the record; pass a different --output-dir.")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not record_path.exists():
        print(f"[ERROR] {record_path} not found; nothing to regenerate against.")
        return 1

    records = pd.read_csv(record_path)
    src = Sources(args)

    cols = {"regen_value": [], "regen_status": [], "regen_note": [],
            "expected_value": [], "regen_matches_value": []}
    for _, row in records.iterrows():
        value, status, note = regenerate(row, src)
        expected, exp_note = row["value"], ""
        if row["number_id"] in KNOWN_RECORD_ERRORS:
            expected, exp_note = KNOWN_RECORD_ERRORS[row["number_id"]]
            note = f"{note}; checked against {exp_note}"
        cols["regen_value"].append(value)
        cols["regen_status"].append(status)
        cols["regen_note"].append(note)
        cols["expected_value"].append(expected)
        cols["regen_matches_value"].append(values_match(expected, value)
                                           if status == "regenerated" else np.nan)

    out = records.copy()
    for k, v in cols.items():
        out[k] = v
    out_path = out_dir / "numbers_of_record_regenerated.csv"
    out.to_csv(out_path, index=False)

    n = len(out)
    regen = out[out.regen_status == "regenerated"]
    retired = out[out.regen_status == "retired"]
    missing = out[out.regen_status == "not_regenerated"]
    bad = regen[regen.regen_matches_value == False]  # noqa: E712
    allowed = bad[bad.number_id.isin(args.allow_deviation)]
    failing = bad[~bad.number_id.isin(args.allow_deviation)]
    print(f"[OK] Wrote {out_path} ({n} rows)")
    print(f"Regenerated: {len(regen)}/{n}; retired: {len(retired)}; not regenerated: {len(missing)}")
    print(f"Match the record: {int(regen.regen_matches_value.eq(True).sum())}/{len(regen)}; "
          f"allowed deviations: {len(allowed)}; failures: {len(failing)}")
    show = ["number_id", "value", "expected_value", "regen_value", "regen_note"]
    if len(allowed):
        print("\nAllowed deviations:")
        print(allowed[show].to_string(index=False))
    if len(failing):
        print("\nFAILURES:")
        print(failing[show].to_string(index=False))
    if len(missing):
        print("\nNot regenerated (input missing):")
        print(missing[["number_id", "regen_note"]].to_string(index=False))
    if len(retired):
        print("\nRetired rows:")
        print(retired[["number_id", "regen_note"]].to_string(index=False))
    return 1 if (args.strict and len(failing)) else 0


if __name__ == "__main__":
    sys.exit(main())
