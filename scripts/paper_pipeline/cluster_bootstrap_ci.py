#!/usr/bin/env python3
"""
cluster_bootstrap_ci.py - task P1.1 of the EMS revision plan.

Replaces the run-mean BCa intervals in
`Miscellaneous Scripts/compute_confidence_intervals.py`.

WHY THE OLD INTERVALS ARE WRONG. That script resamples the FIVE per-run mean
values for a cell and calls the result a 95% CI on the metric. Two problems:
n=5 is far too small for BCa's bias/acceleration corrections to mean anything,
and -- more importantly -- resampling runs captures only seed/sampling variance
of the LLM. It treats the 195 scenarios as fixed and known, so the interval
answers "how much would this number move if I reran the same 195 scenarios?"
The question the paper actually asks is "how much would it move on another draw
of scenarios from this population?", and that variance is invisible to a
run-level resample.

WHAT THIS DOES INSTEAD. A scenario-level cluster bootstrap. The resampling unit
is the scenario, not the run; all runs of a resampled scenario travel together,
which is what makes it a *cluster* bootstrap and what preserves the
within-scenario correlation across runs.

The bootstrap statistic is computed exactly the way the paper computes its point
estimate -- per-run mean over the resampled scenarios, then averaged across runs
-- so this changes the resampling unit and nothing else. Comparing the two
interval widths is therefore a clean measurement of how much uncertainty the old
method was hiding.

Intervals are PERCENTILE intervals. BCa's acceleration constant is estimated
from a jackknife, and the natural jackknife unit here is the scenario cluster;
with 195 clusters that is computable, but percentile intervals on 10,000
clustered resamples are the standard, defensible choice and do not invite a
second methodological argument. The method is stated in the output so the paper
can state it too.

Stage 1 writes a per-scenario long table, which P1.3 (S_int), P1.6 (S_disc) and
P1.7 (stratified tests) all need and none of which currently exists.

Usage:
    python paper_pipeline/cluster_bootstrap_ci.py
    python paper_pipeline/cluster_bootstrap_ci.py --reuse   (skip stage 1)
"""

import argparse
import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS  # noqa: E402
from sentinel_utils import _is_complete_run_file  # noqa: E402

_cm_path = PROJECT_ROOT / "Miscellaneous Scripts" / "core-automation" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("CalculateMetrics", _cm_path)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

OUT_DIR = PROJECT_ROOT / "Analysis"
PER_SCENARIO_CSV = OUT_DIR / "per_scenario_metrics_all.csv"
OUT_XLSX = OUT_DIR / "cluster_bootstrap_ci.xlsx"
OUT_MD = OUT_DIR / "cluster_bootstrap_ci.md"

ARCH_STEMS = {
    "Direct_LLM_Scoring": "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring": "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring": "LLM-Parameterized_Reference_Scoring",
}
ARCH_SHORT = {
    "Direct_LLM_Scoring": "A_D",
    "Example-Guided_LLM_Scoring": "A_E",
    "LLM-Parameterized_Reference_Scoring": "A_H",
}
METRICS = ["kendall_tau", "overall_mae", "top1_accuracy", "top2_accuracy"]

N_BOOT = 10000
SEED = 42


# ---------------------------------------------------------------------------
# Stage 1 - per-scenario metrics
# ---------------------------------------------------------------------------

def scenario_rows(clean, model, arch, run):
    """Per-scenario tau / MAE / top-1 / top-2, using the SAME rules as
    calculate_per_run_metrics.compute_ranking_metrics_local so the per-run means
    of this table reproduce the shipped per-run metrics exactly.

    overall_mae follows significance_testing.compute_per_scenario_metrics_from_raw:
    the mean absolute gap between arch and ground-truth criterion scores over the
    4 criteria x 3 alternatives, so the two files agree on what MAE means."""
    rows = []
    for sid in clean["arch_scenario_id"].unique():
        sc = clean[clean["arch_scenario_id"] == sid]
        if len(sc) < 2:
            continue
        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values
        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue

        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            tau, _ = stats.kendalltau(gt_r, ar_r)
            tau = 0.0 if np.isnan(tau) else float(tau)
        else:
            tau = 1.0 if np.array_equal(gt_r, ar_r) else 0.0

        # spearman_rho: same per-scenario rule as kendall_tau above, and the
        # same rule calculate_per_run_metrics.compute_ranking_metrics_local uses,
        # so this column's per-run mean reproduces the shipped per-run spearman_rho.
        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            rho, _ = stats.spearmanr(gt_r, ar_r)
            rho = 0.0 if np.isnan(rho) else float(rho)
        else:
            rho = 1.0 if np.array_equal(gt_r, ar_r) else 0.0

        gt_top1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top2 = set(sc.sort_values("arch_rank")["norm_alternative"].head(2).values)

        abs_errors = []
        for c in _cm.CRITERIA:
            gt_col, ar_col = f"gt_{c}", f"arch_{c}"
            if gt_col not in sc.columns or ar_col not in sc.columns:
                continue
            gt_v = pd.to_numeric(sc[gt_col], errors="coerce").values
            ar_v = pd.to_numeric(sc[ar_col], errors="coerce").values
            valid = np.isfinite(gt_v) & np.isfinite(ar_v)
            if valid.any():
                abs_errors.extend(np.abs(ar_v[valid] - gt_v[valid]).tolist())
        overall_mae = float(np.mean(abs_errors)) if abs_errors else np.nan

        dt = sc["decision_type"].iloc[0] if "decision_type" in sc.columns else ""
        rows.append({
            "model": model,
            "architecture": arch,
            "run": run,
            "decision_type": dt,
            "scenario_id": sid,
            "kendall_tau": tau,
            "spearman_rho": rho,
            "overall_mae": overall_mae,
            "top1_accuracy": 1.0 if gt_top1 == ar_top1 else 0.0,
            "top2_accuracy": 1.0 if gt_top1 in ar_top2 else 0.0,
        })
    return rows


def build_per_scenario_table():
    all_rows = []
    for model_key in MODEL_SPECS:
        config = _cm._build_config(model_key)
        output_folder = Path(config["output_csv"]).parent
        if not output_folder.exists():
            print(f"  [SKIP] {model_key}: {output_folder} missing")
            continue

        gt_by_type = _cm.load_ground_truth(config)
        gt_lookup = _cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = _cm.build_gt_id_lookup(gt_by_type)

        for arch_name, stem in ARCH_STEMS.items():
            files = [f for f in sorted(output_folder.glob(f"{stem}_results_run_*.xlsx"))
                     if _is_complete_run_file(f)]
            if not files:
                print(f"  [SKIP] {model_key} / {ARCH_SHORT[arch_name]}: no run files")
                continue
            for path in files:
                run = int(path.stem.split("_run_")[-1]) if "_run_" in path.stem else 0
                arch_df = _cm.load_architecture(path, arch_name)
                merged, _ = _cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name)
                if merged.empty:
                    continue
                clean, _, _ = _cm.filter_failed_scenarios(merged)
                if clean.empty:
                    continue
                all_rows.extend(scenario_rows(clean, model_key, arch_name, run))
            print(f"  [OK] {model_key} / {ARCH_SHORT[arch_name]}: {len(files)} runs")

    df = pd.DataFrame(all_rows)
    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(PER_SCENARIO_CSV, index=False, encoding="utf-8")
    print(f"\n  Wrote {PER_SCENARIO_CSV.relative_to(PROJECT_ROOT)}  ({len(df)} rows)")
    return df


# ---------------------------------------------------------------------------
# Stage 2 - cluster bootstrap
# ---------------------------------------------------------------------------

def cell_matrix(cell, metric):
    """scenarios x runs value matrix, NaN where a run did not score a scenario."""
    piv = cell.pivot_table(index="scenario_id", columns="run",
                           values=metric, aggfunc="mean")
    return piv.to_numpy(dtype=float), list(piv.index), list(piv.columns)


def point_estimate(mat):
    """Per-run mean over scenarios, then mean across runs -- the paper's estimator."""
    with np.errstate(invalid="ignore"):
        run_means = np.nanmean(mat, axis=0)
    return float(np.nanmean(run_means))


def cluster_bootstrap(mat, n_boot=N_BOOT, seed=SEED):
    """Resample scenario rows (clusters) with replacement; all runs of a drawn
    scenario travel together. Statistic recomputed as the paper computes it."""
    rng = np.random.default_rng(seed)
    n_scen = mat.shape[0]
    idx = rng.integers(0, n_scen, size=(n_boot, n_scen))
    stats_out = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        sample = mat[idx[b]]
        with np.errstate(invalid="ignore"):
            run_means = np.nanmean(sample, axis=0)
            stats_out[b] = np.nanmean(run_means)
    return stats_out


def run_bootstrap(df):
    rows = []
    for (model, arch), cell in df.groupby(["model", "architecture"]):
        for metric in METRICS:
            mat, scen_ids, runs = cell_matrix(cell, metric)
            est = point_estimate(mat)
            boot = cluster_bootstrap(mat)
            lo, hi = np.nanpercentile(boot, [2.5, 97.5])

            # Run-level interval, for the side-by-side comparison the paper needs.
            with np.errstate(invalid="ignore"):
                run_means = np.nanmean(mat, axis=0)
            run_means = run_means[~np.isnan(run_means)]
            rng = np.random.default_rng(SEED)
            rboot = rng.choice(run_means, size=(N_BOOT, len(run_means)),
                               replace=True).mean(axis=1)
            rlo, rhi = np.nanpercentile(rboot, [2.5, 97.5])

            rows.append({
                "model": model,
                "architecture": ARCH_SHORT[arch],
                "metric": metric,
                "n_scenarios": len(scen_ids),
                "n_runs": len(runs),
                "estimate": round(est, 4),
                "cluster_lo": round(float(lo), 4),
                "cluster_hi": round(float(hi), 4),
                "cluster_width": round(float(hi - lo), 4),
                "runlevel_lo": round(float(rlo), 4),
                "runlevel_hi": round(float(rhi), 4),
                "runlevel_width": round(float(rhi - rlo), 4),
                "width_ratio": round(float((hi - lo) / (rhi - rlo)), 2)
                if (rhi - rlo) > 0 else np.nan,
                "run_sd": round(float(np.std(run_means, ddof=1)), 4)
                if len(run_means) > 1 else np.nan,
            })
    return pd.DataFrame(rows)


def paired_bootstrap(df):
    """Cluster bootstrap of PAIRED architecture differences, within model.

    Marginal intervals cannot answer "do A_D and A_E differ?" -- the two
    architectures score the SAME scenarios, so their errors are positively
    dependent and the paired interval is much narrower than the overlap of two
    marginal intervals suggests. Reading non-significance off overlapping
    marginal CIs is a standard error and this table exists to prevent it.

    The same scenario index is used for both architectures in every resample,
    which is what makes it paired.
    """
    rows = []
    pairs = [("Example-Guided_LLM_Scoring", "Direct_LLM_Scoring"),
             ("LLM-Parameterized_Reference_Scoring", "Example-Guided_LLM_Scoring"),
             ("LLM-Parameterized_Reference_Scoring", "Direct_LLM_Scoring")]

    for model, mdf in df.groupby("model"):
        for arch_a, arch_b in pairs:
            for metric in METRICS:
                a = mdf[mdf["architecture"] == arch_a]
                b = mdf[mdf["architecture"] == arch_b]
                if a.empty or b.empty:
                    continue
                ma, ids_a, _ = cell_matrix(a, metric)
                mb, ids_b, _ = cell_matrix(b, metric)

                # Restrict to scenarios present for both, so the pairing is real.
                common = sorted(set(ids_a) & set(ids_b))
                ia = [ids_a.index(s) for s in common]
                ib = [ids_b.index(s) for s in common]
                ma, mb = ma[ia], mb[ib]

                diff = point_estimate(ma) - point_estimate(mb)

                rng = np.random.default_rng(SEED)
                n_scen = ma.shape[0]
                idx = rng.integers(0, n_scen, size=(N_BOOT, n_scen))
                boot = np.empty(N_BOOT, dtype=float)
                for k in range(N_BOOT):
                    sel = idx[k]  # same scenarios for both arms -> paired
                    with np.errstate(invalid="ignore"):
                        boot[k] = (np.nanmean(np.nanmean(ma[sel], axis=0))
                                   - np.nanmean(np.nanmean(mb[sel], axis=0)))
                lo, hi = np.nanpercentile(boot, [2.5, 97.5])
                rows.append({
                    "model": model,
                    "comparison": f"{ARCH_SHORT[arch_a]} - {ARCH_SHORT[arch_b]}",
                    "metric": metric,
                    "n_common": n_scen,
                    "difference": round(diff, 4),
                    "ci_lo": round(float(lo), 4),
                    "ci_hi": round(float(hi), 4),
                    "excludes_zero": bool(lo > 0 or hi < 0),
                })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true",
                    help="reuse an existing per-scenario table")
    args = ap.parse_args()

    if args.reuse and PER_SCENARIO_CSV.exists():
        df = pd.read_csv(PER_SCENARIO_CSV)
        print(f"Reusing {PER_SCENARIO_CSV.name} ({len(df)} rows)")
    else:
        print("Stage 1 - per-scenario metrics")
        df = build_per_scenario_table()

    print("\nStage 2 - scenario-level cluster bootstrap "
          f"({N_BOOT} resamples, seed {SEED}, percentile intervals)")
    res = run_bootstrap(df)
    res = res.sort_values(["metric", "architecture", "model"]).reset_index(drop=True)

    print("\nStage 3 - paired architecture differences (same scenarios both arms)")
    paired = paired_bootstrap(df)

    OUT_DIR.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xl:
        res.to_excel(xl, sheet_name="cluster_ci", index=False)
        paired.to_excel(xl, sheet_name="paired_differences", index=False)

    md = ["# Scenario-level cluster bootstrap (P1.1)", "",
          "Replaces the run-mean BCa intervals in",
          "`Miscellaneous Scripts/compute_confidence_intervals.py`, which resampled",
          "five per-run means and therefore measured seed variance only.", "",
          f"- Resampling unit: **scenario** (cluster); all runs of a drawn scenario travel together",
          f"- Resamples: **{N_BOOT}**, seed {SEED}, **percentile** intervals",
          "- Statistic: per-run mean over resampled scenarios, then mean across runs",
          "  (identical to the paper's point estimator -- only the resampling unit changed)",
          ""]

    for metric in METRICS:
        sub = res[res["metric"] == metric]
        md += [f"## {metric}", "",
               "| Model | Arch | n | Estimate | Cluster 95% CI | Width | Run-level 95% CI | Width | Ratio |",
               "|---|---|---|---|---|---|---|---|---|"]
        for _, r in sub.iterrows():
            md.append(
                f"| {r['model']} | {r['architecture']} | {r['n_scenarios']} | {r['estimate']:.4f} "
                f"| [{r['cluster_lo']:.4f}, {r['cluster_hi']:.4f}] | {r['cluster_width']:.4f} "
                f"| [{r['runlevel_lo']:.4f}, {r['runlevel_hi']:.4f}] | {r['runlevel_width']:.4f} "
                f"| {r['width_ratio']}x |")
        md.append("")

    ratios = res["width_ratio"].dropna()
    md += ["## How much was the old method hiding?", "",
           f"- Median width ratio (cluster / run-level): **{ratios.median():.1f}x**",
           f"- Range: {ratios.min():.1f}x to {ratios.max():.1f}x",
           "",
           "A ratio above 1 means the published interval was narrower than the",
           "scenario-level uncertainty justifies.", ""]

    md += ["## Paired architecture differences", "",
           "Both arms score the same scenarios, so the paired interval -- not the",
           "overlap of two marginal intervals -- is what decides whether two",
           "architectures differ. Same resampled scenario index used for both arms.", ""]
    for metric in METRICS:
        sub = paired[paired["metric"] == metric]
        if sub.empty:
            continue
        md += [f"### {metric}", "",
               "| Model | Comparison | n | Difference | 95% CI | Excludes 0 |",
               "|---|---|---|---|---|---|"]
        for _, r in sub.iterrows():
            md.append(f"| {r['model']} | {r['comparison']} | {r['n_common']} "
                      f"| {r['difference']:+.4f} | [{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}] "
                      f"| {'yes' if r['excludes_zero'] else '**NO**'} |")
        md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("")
    print(res.to_string(index=False))
    print("")
    print("PAIRED DIFFERENCES (kendall_tau, top1_accuracy):")
    print(paired[paired["metric"] != "top2_accuracy"].to_string(index=False))
    nonsig = paired[~paired["excludes_zero"]]
    if len(nonsig):
        print("")
        print("  Comparisons whose paired 95% CI includes zero:")
        print(nonsig.to_string(index=False))
    else:
        print("\n  Every paired comparison excludes zero.")
    print("")
    print(f"  Median cluster/run-level width ratio: {ratios.median():.1f}x "
          f"(range {ratios.min():.1f}-{ratios.max():.1f})")
    print(f"  Wrote {OUT_XLSX.relative_to(PROJECT_ROOT)}")
    print(f"  Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
