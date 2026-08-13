#!/usr/bin/env python3
"""
test_mechanics.py - task P1.7 of the EMS revision plan.

Three fixes to what `Miscellaneous Scripts/significance_testing.py` reports.
That script is NOT modified; this is a separate artifact that supersedes three
of its outputs.

FIX 1 - STRATIFY THE WILCOXON BY DECISION TYPE.
    A_D's Kendall tau runs from about -0.15 to +0.63 across the three decision
    types. Pooling 195 paired differences into one signed-rank test therefore
    mixes three subpopulations with different central tendencies. The pooled
    test can be significant because the decision types differ from each other
    rather than because the architectures differ, and it can also be diluted
    when two types move in opposite directions. Every test here is run within a
    single (model, decision type) cell, and the pooled test is reported
    alongside for comparison, not instead.

FIX 2 - STATE TIE HANDLING AND EXACT-VS-ASYMPTOTIC MODE.
    Per-scenario Kendall tau over three alternatives takes only four distinct
    values, so run-averaged paired differences are heavily tied and often
    exactly zero. Gemini's median paired difference is exactly 0.0000 on some
    cells while the test still reports significance; that is tie saturation and
    it must be disclosed, not left for a reader to infer. Every row below
    carries: n pairs, n zero differences (dropped by Wilcoxon's zero method),
    n non-zero pairs the statistic is actually computed on, the largest tie
    group among |d|, the share of non-zero pairs sitting in some tie group, the
    median and mean paired difference, and the mode actually used.

    MODE. scipy's `wilcoxon` is called explicitly with
    `zero_method="wilcox"` (zero differences discarded) and
    `mode`/`method` chosen as: exact when n_nonzero <= 25 AND no ties are
    present among |d|, asymptotic with tie and continuity correction
    otherwise. The exact distribution is not valid under ties, so with these
    data the mode is asymptotic essentially everywhere; the column records it
    per row rather than asserting it in prose.

FIX 3 - REPLACE ICC(1,1).
    ICC(1,1) is a one-way random-effects reliability coefficient. Runs nested
    in model is the right design for it, but the number is being read as
    "reliability of the measurement", which it does not support here: the
    "raters" are runs of one stochastic system, not interchangeable judges, and
    the between-group variance it divides by is a variance across four
    deliberately chosen, non-random models. Reported instead, in the metric's
    own units and with no reliability interpretation attached:
      * between-model range = max over models of the cell mean minus the min,
      * within-cell run-to-run SD = SD across the 5 runs inside a cell,
        summarised as the median and max across models,
      * their ratio.
    A between-model range several times the within-cell SD means model choice
    moves the metric more than rerunning does. That is the claim the paper
    actually needs, stated as a comparison of two dispersions.

Inputs:  Analysis/per_scenario_metrics_all.csv   (built by cluster_bootstrap_ci.py)
         paper/per_run_metrics/per_run_metrics_all.csv
Output:  Analysis/test_mechanics.{xlsx,md}

Usage:
    python paper_pipeline/test_mechanics.py
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

PER_SCENARIO_CSV = PROJECT_ROOT / "Analysis" / "per_scenario_metrics_all.csv"
PER_RUN_CSV = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
OUT_XLSX = PROJECT_ROOT / "Analysis" / "test_mechanics.xlsx"
OUT_MD = PROJECT_ROOT / "Analysis" / "test_mechanics.md"

ARCH_SHORT = {
    "Direct_LLM_Scoring": "A_D",
    "Example-Guided_LLM_Scoring": "A_E",
    "LLM-Parameterized_Reference_Scoring": "A_H",
}
PAIRS = [("Example-Guided_LLM_Scoring", "Direct_LLM_Scoring"),
         ("LLM-Parameterized_Reference_Scoring", "Example-Guided_LLM_Scoring"),
         ("LLM-Parameterized_Reference_Scoring", "Direct_LLM_Scoring")]
METRICS = ["kendall_tau", "top1_accuracy"]
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
EXACT_MAX_N = 25


def run_averaged(df):
    """One value per (model, architecture, decision_type, scenario, metric):
    the mean across the runs that scored it. Same aggregation the paper's
    point estimates use."""
    return (df.groupby(["model", "architecture", "decision_type", "scenario_id"],
                       as_index=False)[METRICS].mean())


def tie_profile(d_nonzero):
    """Largest tie group among |d| and the share of pairs inside any tie group."""
    if len(d_nonzero) == 0:
        return 0, 0.0
    _, counts = np.unique(np.abs(d_nonzero), return_counts=True)
    largest = int(counts.max())
    in_ties = int(counts[counts > 1].sum())
    return largest, float(in_ties / len(d_nonzero))


def wilcoxon_cell(a, b):
    """Wilcoxon signed-rank on paired vectors, with full mechanics disclosed."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n_pairs = len(d)
    n_zero = int(np.sum(d == 0))
    nz = d[d != 0]
    n_nonzero = len(nz)
    largest_tie, tie_share = tie_profile(nz)
    has_ties = largest_tie > 1

    out = {
        "n_pairs": n_pairs,
        "n_zero_diff": n_zero,
        "n_nonzero": n_nonzero,
        "zero_method": "wilcox (zeros discarded)",
        "largest_tie_group": largest_tie,
        "tied_share_of_nonzero": round(tie_share, 4),
        "median_diff": round(float(np.median(d)), 6) if n_pairs else np.nan,
        "mean_diff": round(float(np.mean(d)), 6) if n_pairs else np.nan,
    }

    if n_nonzero == 0:
        out.update({"mode": "not run (all differences zero)",
                    "statistic": np.nan, "p_value": np.nan,
                    "rank_biserial": 0.0,
                    "tie_saturated": True})
        return out

    use_exact = (n_nonzero <= EXACT_MAX_N) and not has_ties
    method = "exact" if use_exact else "asymptotic"
    try:
        res = stats.wilcoxon(d, zero_method="wilcox", correction=not use_exact,
                             alternative="two-sided", method=method)
        statistic, pval = float(res.statistic), float(res.pvalue)
    except ValueError as exc:
        out.update({"mode": "failed: %s" % exc, "statistic": np.nan,
                    "p_value": np.nan, "rank_biserial": np.nan,
                    "tie_saturated": bool(n_zero > n_pairs / 2)})
        return out

    ranks = stats.rankdata(np.abs(nz))
    pos = float(ranks[nz > 0].sum())
    neg = float(ranks[nz < 0].sum())
    total = pos + neg
    rb = (pos - neg) / total if total > 0 else 0.0

    out.update({
        "mode": method + (" (tie + continuity corrected)" if method == "asymptotic" else ""),
        "statistic": round(statistic, 4),
        "p_value": pval,
        "rank_biserial": round(rb, 4),
        # A cell is tie-saturated when the median paired difference is exactly
        # zero, or when over half the pairs are exact zeros. Either way the
        # p-value is being driven by a minority of the pairs.
        "tie_saturated": bool(out["median_diff"] == 0.0 or n_zero > n_pairs / 2),
    })
    return out


def holm(pvals):
    """Holm-Bonferroni adjusted p-values over one family."""
    p = np.asarray(pvals, dtype=float)
    ok = ~np.isnan(p)
    adj = np.full_like(p, np.nan)
    idx = np.where(ok)[0]
    m = len(idx)
    if m == 0:
        return adj
    order = idx[np.argsort(p[idx])]
    running = 0.0
    for i, j in enumerate(order):
        val = (m - i) * p[j]
        running = max(running, val)
        adj[j] = min(1.0, running)
    return adj


def run_stratified(avg):
    rows = []
    models = sorted(avg["model"].unique())
    for model in models:
        for a, b in PAIRS:
            for metric in METRICS:
                for scope in DECISION_TYPES + ["Pooled"]:
                    sub = avg if scope == "Pooled" else avg[avg["decision_type"] == scope]
                    sa = sub[(sub["model"] == model) & (sub["architecture"] == a)] \
                        .set_index("scenario_id")[metric].dropna()
                    sb = sub[(sub["model"] == model) & (sub["architecture"] == b)] \
                        .set_index("scenario_id")[metric].dropna()
                    common = sa.index.intersection(sb.index)
                    if len(common) < 5:
                        continue
                    res = wilcoxon_cell(sa.loc[common].values, sb.loc[common].values)
                    rows.append({
                        "model": model,
                        "comparison": "%s vs %s" % (ARCH_SHORT[a], ARCH_SHORT[b]),
                        "metric": metric,
                        "scope": scope,
                        **res,
                    })
    df = pd.DataFrame(rows)
    # Holm over the stratified family only (Pooled rows are reported for
    # comparison and are not part of the corrected family, because they are the
    # same data as the three strata combined).
    strat = df["scope"] != "Pooled"
    df["p_holm"] = np.nan
    df.loc[strat, "p_holm"] = holm(df.loc[strat, "p_value"].values)
    return df


def run_dispersion(per_run):
    """Between-model range vs within-cell run-to-run SD. Replaces ICC(1,1)."""
    df = per_run[per_run["decision_type"] == "Overall"]
    rows = []
    for arch, g in df.groupby("architecture"):
        for metric in METRICS:
            cells = g.groupby("model")[metric]
            means = cells.mean()
            sds = cells.std(ddof=1)
            rng = float(means.max() - means.min())
            med_sd = float(sds.median())
            max_sd = float(sds.max())
            rows.append({
                "architecture": ARCH_SHORT.get(arch, arch),
                "metric": metric,
                "n_models": int(len(means)),
                "model_min": round(float(means.min()), 4),
                "model_max": round(float(means.max()), 4),
                "between_model_range": round(rng, 4),
                "within_cell_sd_median": round(med_sd, 4),
                "within_cell_sd_max": round(max_sd, 4),
                "range_over_median_sd": round(rng / med_sd, 2) if med_sd > 0 else np.inf,
                "range_over_max_sd": round(rng / max_sd, 2) if max_sd > 0 else np.inf,
            })
    return pd.DataFrame(rows)


def main():
    warnings.filterwarnings("ignore")
    print("P1.7 test mechanics")
    print("=" * 64)

    per_scen = pd.read_csv(PER_SCENARIO_CSV)
    avg = run_averaged(per_scen)
    print("  Run-averaged per-scenario rows: %d" % len(avg))

    wil = run_stratified(avg)
    print("  Wilcoxon rows: %d (%d stratified, %d pooled)"
          % (len(wil), int((wil['scope'] != 'Pooled').sum()),
             int((wil['scope'] == 'Pooled').sum())))

    per_run = pd.read_csv(PER_RUN_CSV)
    disp = run_dispersion(per_run)
    print("  Dispersion rows: %d" % len(disp))

    OUT_XLSX.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        wil.to_excel(xw, sheet_name="Wilcoxon_stratified", index=False)
        disp.to_excel(xw, sheet_name="Dispersion_replaces_ICC", index=False)
    print("  Wrote %s" % OUT_XLSX.relative_to(PROJECT_ROOT))

    L = []
    L.append("# P1.7 - test mechanics\n")
    L.append("Supersedes three outputs of `Miscellaneous Scripts/significance_testing.py`.")
    L.append("That script is unchanged; this is a separate artifact.\n")

    L.append("## Fix 1+2 - Wilcoxon stratified by decision type, with tie handling stated\n")
    L.append("Zero method: `wilcox` (exact-zero differences discarded before ranking).")
    L.append("Mode: exact only when n_nonzero <= %d AND no ties among |d|; asymptotic with"
             % EXACT_MAX_N)
    L.append("tie and continuity correction otherwise. `tie_saturated` marks cells whose")
    L.append("median paired difference is exactly 0 or where over half the pairs are exact zeros.")
    L.append("Holm correction is applied across the stratified family only; `Pooled` rows")
    L.append("are shown for comparison and are excluded from the correction.\n")
    L.append("| Model | Comparison | Metric | Scope | n | n zero | n nonzero | median d | mode | p | p_holm | tie sat. |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in wil.iterrows():
        ph = "" if pd.isna(r["p_holm"]) else "%.3g" % r["p_holm"]
        pv = "" if pd.isna(r["p_value"]) else "%.3g" % r["p_value"]
        L.append("| %s | %s | %s | %s | %d | %d | %d | %+.4f | %s | %s | %s | %s |" % (
            r["model"], r["comparison"], r["metric"], r["scope"],
            r["n_pairs"], r["n_zero_diff"], r["n_nonzero"], r["median_diff"],
            r["mode"], pv, ph, "YES" if r["tie_saturated"] else ""))

    n_sat = int(wil["tie_saturated"].sum())
    L.append("")
    L.append("**%d of %d cells are tie-saturated.**" % (n_sat, len(wil)))
    L.append("")

    L.append("## Fix 3 - between-model range vs within-cell run-to-run SD (replaces ICC(1,1))\n")
    L.append("No reliability interpretation is attached. Both quantities are in the")
    L.append("metric's own units; the ratio says how much larger the spread across models")
    L.append("is than the spread across reruns of one model.\n")
    L.append("| Arch | Metric | model min | model max | between-model range | within-cell SD (median) | within-cell SD (max) | range / median SD |")
    L.append("|---|---|---|---|---|---|---|---|")
    for _, r in disp.iterrows():
        L.append("| %s | %s | %.4f | %.4f | %.4f | %.4f | %.4f | %.2f |" % (
            r["architecture"], r["metric"], r["model_min"], r["model_max"],
            r["between_model_range"], r["within_cell_sd_median"],
            r["within_cell_sd_max"], r["range_over_median_sd"]))

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("  Wrote %s" % OUT_MD.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
