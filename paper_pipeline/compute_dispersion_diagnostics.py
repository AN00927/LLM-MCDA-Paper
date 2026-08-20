#!/usr/bin/env python3
"""
compute_dispersion_diagnostics.py -- score-dispersion evidence for the EMS revision.

Motivation
----------
The manuscript attributes A_D's ranking failure to "central-tendency bias" --
scores clustering near 0.5. The shipped run data does not support that: A_D
*over*-separates relative to the physics reference. This script produces the
measurements that settle the mechanism, all from files already on disk (no API
calls, no re-running of any architecture).

What it computes (195 Test scenarios only; sentinel-carrying scenarios excluded
via the shared filter in evaluate_architecture_metrics)

  1. Marginal score distribution per (model, architecture) and for the ground
     truth: mean, sd, and the fraction of scores falling in [0.3, 0.7], pooling
     the four criteria.
  2. Within-scenario range and sd of the MAVT aggregate (the CRITERION_WEIGHTS
     weighted sum), averaged over scenarios, per (model, architecture) and for
     the ground truth.
  3. Within-scenario range and sd of each individual criterion, per decision
     type, per (model, architecture) and for the ground truth.
  4. (A2) Single-criterion top-1 recovery: the share of scenarios in which the
     ground-truth top-ranked alternative is also the argmax of one criterion
     considered alone. Reported for the 195 Test scenarios and for the full
     285-scenario ground-truth corpus.

Architecture figures are computed per run and then averaged over the five runs;
the spread across runs is carried in the `sd_across_runs` column. The ground
truth is deterministic, so its rows have no run spread.

Outputs
-------
  paper/dispersion_diagnostics.csv    long format, all statistics
  paper/dispersion_table.tex          compact main-text table (NOT auto-inserted)
  paper/single_criterion_recovery.tex single-criterion recovery table

Usage
-----
  python paper_pipeline/compute_dispersion_diagnostics.py
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

from model_config import CRITERION_WEIGHTS, MODEL_SPECS, get_output_folder
from sentinel_utils import CRITERIA, _is_complete_run_file, read_table_clean

# ---------------------------------------------------------------------------
# Reuse the shipped matching / filtering machinery rather than re-implementing.
# ---------------------------------------------------------------------------
_CM_PATH = PROJECT_ROOT / "Miscellaneous Scripts" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("evaluate_architecture_metrics", _CM_PATH)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
MODEL_LABELS = {
    "deepseek": "DeepSeek V4 Flash",
    "gemini": "Gemini 3.5 Flash",
    "gptoss": "GPT-OSS 20B",
    "qwen": "Qwen3.5 9B",
}
ARCHITECTURES = [
    "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring",
]
ARCH_TEX = {
    "Direct_LLM_Scoring": r"$\mathcal{A}_{\text{D}}$",
    "Example-Guided_LLM_Scoring": r"$\mathcal{A}_{\text{E}}$",
    "LLM-Parameterized_Reference_Scoring": r"$\mathcal{A}_{\text{H}}$",
}
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
CENTRAL_BAND = (0.3, 0.7)

PAPER_DIR = PROJECT_ROOT / "paper"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"
GT_FILES = {
    "HVAC": GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx",
    "Appliance": GROUND_TRUTH_DIR / "ground_truth_appliance.xlsx",
    "Shower": GROUND_TRUTH_DIR / "ground_truth_shower.xlsx",
}

_rows = []


def add(source, model, architecture, decision_type, criterion, statistic,
        value, sd_across_runs=np.nan):
    _rows.append({
        "source": source,
        "model": model,
        "architecture": architecture,
        "decision_type": decision_type,
        "criterion": criterion,
        "statistic": statistic,
        "value": np.nan if value is None or pd.isna(value) else round(float(value), 6),
        "sd_across_runs": (np.nan if sd_across_runs is None or pd.isna(sd_across_runs)
                           else round(float(sd_across_runs), 6)),
    })


# ---------------------------------------------------------------------------
# Core statistics
# ---------------------------------------------------------------------------
def weighted_aggregate(df, prefix):
    """MAVT weighted sum of the four criterion columns carrying *prefix*."""
    total = None
    for c in CRITERIA:
        term = df[f"{prefix}{c}"].astype(float) * CRITERION_WEIGHTS[c]
        total = term if total is None else total + term
    return total


def marginal_stats(df, prefix):
    """Pooled-criteria mean, sd, and fraction inside the central band."""
    vals = pd.concat([df[f"{prefix}{c}"].astype(float) for c in CRITERIA],
                     ignore_index=True).dropna()
    if len(vals) == 0:
        return {}
    lo, hi = CENTRAL_BAND
    return {
        "marginal_mean": vals.mean(),
        "marginal_sd": vals.std(ddof=1),
        "marginal_frac_in_central_band": float(((vals >= lo) & (vals <= hi)).mean()),
        "marginal_n_scores": float(len(vals)),
    }


def within_scenario_aggregate_stats(df, prefix):
    """Mean over scenarios of the within-scenario MAVT range and sd."""
    work = df.copy()
    work["_agg"] = weighted_aggregate(work, prefix)
    grp = work.groupby("arch_scenario_id")["_agg"]
    rng = grp.apply(lambda s: s.max() - s.min())
    sd = grp.apply(lambda s: s.std(ddof=1))
    return {
        "within_scenario_aggregate_range": rng.mean(),
        "within_scenario_aggregate_sd": sd.mean(),
        "n_scenarios": float(rng.notna().sum()),
    }


def within_scenario_criterion_stats(df, prefix, criterion):
    """Mean over scenarios of the within-scenario range and sd of one criterion."""
    grp = df.groupby("arch_scenario_id")[f"{prefix}{criterion}"]
    rng = grp.apply(lambda s: s.astype(float).max() - s.astype(float).min())
    sd = grp.apply(lambda s: s.astype(float).std(ddof=1))
    return {
        "within_scenario_range": rng.mean(),
        "within_scenario_sd": sd.mean(),
    }


def all_stats_for_frame(df, prefix):
    """Every dispersion statistic for one merged frame, keyed for aggregation."""
    out = {}
    for k, v in marginal_stats(df, prefix).items():
        out[("Overall", "all", k)] = v
    for k, v in within_scenario_aggregate_stats(df, prefix).items():
        out[("Overall", "mavt_aggregate", k)] = v
    for dt in DECISION_TYPES:
        sub = df[df["decision_type"] == dt]
        if sub.empty:
            continue
        for k, v in within_scenario_aggregate_stats(sub, prefix).items():
            out[(dt, "mavt_aggregate", k)] = v
        for c in CRITERIA:
            for k, v in within_scenario_criterion_stats(sub, prefix, c).items():
                out[(dt, c, k)] = v
    return out


# ---------------------------------------------------------------------------
# A2: single-criterion top-1 recovery
# ---------------------------------------------------------------------------
def single_criterion_recovery(df, rank_col, score_prefix, group_col):
    """Share of scenarios whose GT top-1 alternative is the argmax of one criterion.

    Ties are resolved by first-occurrence in the frame's existing row order
    (`idxmax` on a stably ordered frame), so the result is deterministic.
    """
    out = {}
    work = df.sort_index(kind="mergesort")
    for c in CRITERIA:
        hits = 0
        n = 0
        for _, g in work.groupby(group_col, sort=True):
            ranks = g[rank_col].astype(float)
            if ranks.isna().any():
                continue
            top = g.loc[ranks.idxmin(), "_alt_key"]
            crit = g[f"{score_prefix}{c}"].astype(float)
            if crit.isna().any():
                continue
            argmax = g.loc[crit.idxmax(), "_alt_key"]
            n += 1
            if top == argmax:
                hits += 1
        out[c] = (100.0 * hits / n if n else np.nan, n)
    return out


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------
def build_merged_runs():
    """Match every per-run architecture output to ground truth.

    Returns (per_run, gt_test) where
      per_run  -- {(model, architecture, run): clean merged frame}
      gt_test  -- deduplicated ground-truth rows for the matched Test scenarios
    """
    config = _cm._build_config(MODELS[0])
    gt_by_type = _cm.load_ground_truth(config)
    gt_lookup = _cm.build_gt_lookup(gt_by_type)
    gt_id_lookup = _cm.build_gt_id_lookup(gt_by_type)

    per_run = {}
    gt_frames = []

    for model in MODELS:
        folder = PROJECT_ROOT / get_output_folder(model)
        for arch in ARCHITECTURES:
            run_paths = [p for p in sorted(folder.glob(f"{arch}_results_run_*.xlsx"))
                         if _is_complete_run_file(p)]
            if not run_paths:
                print(f"  [SKIP] {model}/{arch}: no complete run files")
                continue
            for path in run_paths:
                run = int(path.stem.split("_run_")[-1])
                arch_df = _cm.load_architecture(path, arch)
                merged, _ = _cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch)
                if merged.empty:
                    continue
                gt_cols = ["arch_scenario_id", "decision_type", "norm_alternative",
                           "gt_rank"] + [f"gt_{c}" for c in CRITERIA]
                gt_frames.append(merged[gt_cols].copy())
                clean, _, _ = _cm.filter_failed_scenarios(merged)
                if clean.empty:
                    continue
                per_run[(model, arch, run)] = clean

    gt_test = pd.concat(gt_frames, ignore_index=True).drop_duplicates(
        subset=["decision_type", "arch_scenario_id", "norm_alternative"]
    ).reset_index(drop=True)
    return per_run, gt_test


def load_full_corpus_gt():
    """Ground-truth long frame for the full 285-scenario corpus."""
    frames = []
    for dt, path in GT_FILES.items():
        df = read_table_clean(path, keep_str_cols=["question", "location", "alternative"])
        df["decision_type"] = dt
        rename = {f"{c}_score": f"gt_{c}" for c in CRITERIA}
        rename["rank"] = "gt_rank"
        df = df.rename(columns=rename)
        df["_alt_key"] = df["alternative"].astype(str)
        df["_sid"] = df["decision_type"] + "_" + df["scenario_id"].astype(str)
        frames.append(df[["decision_type", "_sid", "_alt_key", "gt_rank"]
                        + [f"gt_{c}" for c in CRITERIA]])
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# LaTeX emitters
# ---------------------------------------------------------------------------
def _fmt(v, nd=3):
    return "--" if v is None or pd.isna(v) else f"{v:.{nd}f}"


def pick_best_worst_models():
    """Best/worst model by mean Kendall tau over all architectures and runs."""
    path = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
    if not path.exists():
        return "gemini", "qwen"
    pr = pd.read_csv(path)
    pr = pr[pr["decision_type"] == "Overall"]
    means = pr.groupby("model")["kendall_tau"].mean()
    return means.idxmax(), means.idxmin()


def emit_dispersion_table(diag, best_model, worst_model, out_path):
    def get(source, model, arch, dt, crit, stat):
        m = diag[(diag["source"] == source) & (diag["model"] == model)
                 & (diag["architecture"] == arch) & (diag["decision_type"] == dt)
                 & (diag["criterion"] == crit) & (diag["statistic"] == stat)]
        if m.empty:
            return np.nan, np.nan
        return m["value"].iloc[0], m["sd_across_runs"].iloc[0]

    def cell(source, model, arch, dt, crit, stat):
        v, s = get(source, model, arch, dt, crit, stat)
        if pd.isna(v):
            return "--"
        if pd.isna(s):
            return _fmt(v)
        return f"{_fmt(v)} $\\pm$ {_fmt(s)}"

    lines = []
    lines.append("% Generated by paper_pipeline/compute_dispersion_diagnostics.py")
    lines.append("% Numbers are reproducible from paper/dispersion_diagnostics.csv.")
    lines.append(r"\begin{table*}[htbp]")
    lines.append(r"\begin{threeparttable}")
    lines.append(r"  \footnotesize")
    lines.append(r"  \centering")
    lines.append(r"  \textbf{Within-scenario score dispersion}")
    lines.append(r"  \begin{tabular}{llccc}")
    lines.append(r"    \toprule")
    lines.append(r"    & & MAVT aggregate & \multicolumn{2}{c}{HVAC criterion range} \\")
    lines.append(r"    \cmidrule(lr){4-5}")
    lines.append(r"    Model & Architecture & range & Energy cost & Comfort \\")
    lines.append(r"    \midrule")
    lines.append("    Physics reference & --- & "
                 + cell("ground_truth", "ground_truth", "GroundTruth", "Overall",
                        "mavt_aggregate", "within_scenario_aggregate_range")
                 + " & "
                 + cell("ground_truth", "ground_truth", "GroundTruth", "HVAC",
                        "energy_cost", "within_scenario_range")
                 + " & "
                 + cell("ground_truth", "ground_truth", "GroundTruth", "HVAC",
                        "comfort", "within_scenario_range")
                 + r" \\")
    lines.append(r"    \midrule")

    for label, model in [("best", best_model), ("worst", worst_model)]:
        for arch in ARCHITECTURES:
            name = f"{MODEL_LABELS[model]} ({label})" if arch == ARCHITECTURES[0] else ""
            lines.append(
                f"    {name} & {ARCH_TEX[arch]} & "
                + cell("architecture", model, arch, "Overall", "mavt_aggregate",
                       "within_scenario_aggregate_range")
                + " & "
                + cell("architecture", model, arch, "HVAC", "energy_cost",
                       "within_scenario_range")
                + " & "
                + cell("architecture", model, arch, "HVAC", "comfort",
                       "within_scenario_range")
                + r" \\")
        if label == "best":
            lines.append(r"    \addlinespace")

    lines.append(r"    \bottomrule")
    lines.append(r"  \end{tabular}")
    lines.append(r"  \begin{tablenotes}")
    lines.append(r"    \item Mean over the 195 Test scenarios of the within-scenario"
                 r" range (maximum minus minimum across the three alternatives), on"
                 r" the 0--1 score scale. Architecture entries are the five-run mean"
                 r" $\pm$ standard deviation across runs; the physics reference is"
                 r" deterministic and has no run spread. Scenarios carrying a failed"
                 r" score are excluded. Best and worst model are those with the"
                 r" highest and lowest mean Kendall's $\tau$ across all three"
                 r" architectures. A wider range than the reference means the"
                 r" architecture separates alternatives \emph{more} than the physics"
                 r" warrants, not less.")
    lines.append(r"  \end{tablenotes}")
    lines.append(r"\end{threeparttable}")
    lines.append(r"\caption{Within-scenario dispersion of the MAVT aggregate and of"
                 r" two HVAC criteria, for the physics reference and for each"
                 r" architecture under the strongest and weakest model.}")
    lines.append(r"\label{tab:dispersion}")
    lines.append(r"\end{table*}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [OK] wrote {out_path}")


def emit_recovery_table(test_rec, full_rec, out_path):
    crit_labels = {"energy_cost": "Energy cost", "environmental": "Environmental",
                   "comfort": "Comfort", "practicality": "Practicality"}
    lines = []
    lines.append("% Generated by paper_pipeline/compute_dispersion_diagnostics.py")
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\begin{threeparttable}")
    lines.append(r"  \footnotesize")
    lines.append(r"  \centering")
    lines.append(r"  \textbf{Single-criterion top-1 recovery}")
    lines.append(r"  \begin{tabular}{lcccc}")
    lines.append(r"    \toprule")
    lines.append(r"    Decision type & Energy cost & Environmental & Comfort & Practicality \\")
    lines.append(r"    \midrule")
    for dt in DECISION_TYPES:
        n = test_rec[dt]["energy_cost"][1]
        cells = " & ".join(_fmt(test_rec[dt][c][0], 1) for c in CRITERIA)
        lines.append(f"    {dt} ($n={n}$) & {cells} " + r"\\")
    lines.append(r"    \bottomrule")
    lines.append(r"  \end{tabular}")
    lines.append(r"  \begin{tablenotes}")
    lines.append(r"    \item Percentage of scenarios in which the physics reference's"
                 r" top-ranked alternative is also the argmax of the named criterion"
                 r" taken alone, over the 195 Test scenarios. With three alternatives"
                 r" per scenario, chance agreement is 33.3\%. Ties are broken by first"
                 r" occurrence, so the statistic is deterministic. Values on the full"
                 r" 285-scenario dataset, reported in"
                 r" \texttt{paper/dispersion\_diagnostics.csv}, are: "
                 + "; ".join(
                     f"{dt} " + ", ".join(f"{crit_labels[c].lower()} {_fmt(full_rec[dt][c][0], 1)}\\%"
                                          for c in CRITERIA)
                     for dt in DECISION_TYPES)
                 + ".")
    lines.append(r"  \end{tablenotes}")
    lines.append(r"\end{threeparttable}")
    lines.append(r"\caption{Share of scenarios whose ground-truth winner is recoverable"
                 r" from a single criterion.}")
    lines.append(r"\label{tab:single-criterion-recovery}")
    lines.append(r"\end{table}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [OK] wrote {out_path}")


# ---------------------------------------------------------------------------
def main():
    warnings.filterwarnings("ignore")
    print("[1] Matching per-run architecture outputs to ground truth ...")
    per_run, gt_test = build_merged_runs()
    print(f"    {len(per_run)} (model, architecture, run) frames matched")
    print(f"    ground-truth Test reference: {gt_test['arch_scenario_id'].nunique()} "
          f"scenarios, {len(gt_test)} alternative rows")

    print("[2] Ground-truth dispersion ...")
    gt_stats = all_stats_for_frame(gt_test, "gt_")
    for (dt, crit, stat), val in gt_stats.items():
        add("ground_truth", "ground_truth", "GroundTruth", dt, crit, stat, val)

    print("[3] Architecture dispersion (5-run mean, sd across runs) ...")
    for model in MODELS:
        for arch in ARCHITECTURES:
            runs = {r: f for (m, a, r), f in per_run.items()
                    if m == model and a == arch}
            if not runs:
                continue
            per_run_stats = {r: all_stats_for_frame(f, "arch_") for r, f in runs.items()}
            keys = sorted({k for s in per_run_stats.values() for k in s},
                          key=lambda t: (t[0], t[1], t[2]))
            for key in keys:
                vals = [s[key] for s in per_run_stats.values() if key in s]
                vals = [v for v in vals if pd.notna(v)]
                if not vals:
                    continue
                dt, crit, stat = key
                add("architecture", model, arch, dt, crit, stat,
                    float(np.mean(vals)),
                    float(np.std(vals, ddof=1)) if len(vals) > 1 else np.nan)
            print(f"    {model:9s} {arch:38s} {len(runs)} runs")

    print("[4] Single-criterion top-1 recovery ...")
    gt_test = gt_test.copy()
    gt_test["_alt_key"] = gt_test["norm_alternative"].astype(str)
    gt_test["_sid"] = gt_test["decision_type"] + "_" + gt_test["arch_scenario_id"].astype(str)
    test_rec = {}
    for dt in DECISION_TYPES:
        sub = gt_test[gt_test["decision_type"] == dt]
        test_rec[dt] = single_criterion_recovery(sub, "gt_rank", "gt_", "_sid")

    gt_full = load_full_corpus_gt()
    full_rec = {}
    for dt in DECISION_TYPES:
        sub = gt_full[gt_full["decision_type"] == dt]
        full_rec[dt] = single_criterion_recovery(sub, "gt_rank", "gt_", "_sid")

    for corpus, rec in [("test_195", test_rec), ("full_285", full_rec)]:
        for dt in DECISION_TYPES:
            for c in CRITERIA:
                pct, n = rec[dt][c]
                add(f"single_criterion_recovery_{corpus}", "ground_truth",
                    "GroundTruth", dt, c, "gt_top1_recovery_pct", pct)
                add(f"single_criterion_recovery_{corpus}", "ground_truth",
                    "GroundTruth", dt, c, "n_scenarios", float(n))
            print(f"    {corpus:9s} {dt:10s} n={rec[dt]['energy_cost'][1]:4d}  "
                  + "  ".join(f"{c}={rec[dt][c][0]:.1f}" for c in CRITERIA))

    diag = pd.DataFrame(_rows)
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = PAPER_DIR / "dispersion_diagnostics.csv"
    diag.to_csv(csv_path, index=False)
    print(f"\n  [OK] wrote {csv_path} ({len(diag)} rows)")

    best_model, worst_model = pick_best_worst_models()
    print(f"  best model = {best_model}, worst model = {worst_model}")
    emit_dispersion_table(diag, best_model, worst_model, PAPER_DIR / "dispersion_table.tex")
    emit_recovery_table(test_rec, full_rec, PAPER_DIR / "single_criterion_recovery.tex")

    print("\n=== HEADLINE: within-scenario MAVT aggregate range (mean over scenarios) ===")
    hl = diag[(diag["decision_type"] == "Overall")
              & (diag["criterion"] == "mavt_aggregate")
              & (diag["statistic"] == "within_scenario_aggregate_range")]
    for _, r in hl.iterrows():
        sd = "" if pd.isna(r["sd_across_runs"]) else f" +/- {r['sd_across_runs']:.4f}"
        print(f"  {r['model']:13s} {r['architecture']:38s} {r['value']:.4f}{sd}")

    print("\n=== HEADLINE: marginal score distribution (pooled criteria) ===")
    for stat in ["marginal_mean", "marginal_sd", "marginal_frac_in_central_band"]:
        print(f"  -- {stat}")
        sub = diag[(diag["decision_type"] == "Overall") & (diag["criterion"] == "all")
                   & (diag["statistic"] == stat)]
        for _, r in sub.iterrows():
            print(f"     {r['model']:13s} {r['architecture']:38s} {r['value']:.4f}")


if __name__ == "__main__":
    main()
