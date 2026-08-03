#!/usr/bin/env python3
"""
significance_testing.py - Statistical significance tests for LLM-MCDA architecture comparison.

Computes ICC, mixed-model tests, Wilcoxon signed-rank tests, Stouffer
combination, and effect sizes for three architectures (AD, AE, AH) across
four models on 195 scenarios.

Input:  Raw per-run xlsx files from each model's output folder, plus
        ground truth xlsx files from Ground Truth/.
Output: significance_tests.xlsx (four sheets) + stdout tables.

Aggregation method (Method A):
    Per-scenario metrics are computed independently for each of the 5 runs,
    then averaged across runs. This gives one (scenario, model, architecture)
    metric value. The headline results in the paper use the identical pipeline
    (calculate_per_run_metrics.py -> generate_paper_results_numbers.py), so the point
    estimate being significance-tested IS the number reported in results tables.
    evaluate_architecture_metrics.py's standalone evaluate_all() uses a different aggregation
    (Method C: average raw scores across 5 runs -> recompute rank -> compute
    metric once); generate_method_c_consensus.py tracks this discrepancy.

Wilcoxon notes:
    The normal approximation omits the tie-correction term in std_T. This is
    conservative (wider CIs, fewer false positives) — standard in scipy's
    legacy implementation and a deliberate choice here. Holm-Bonferroni
    correction pools all 56 tests (2 architecture pairs x 7 metrics x 4
    models) into a SINGLE family: one correction step across both pairwise
    comparisons, not two separate 28-test families. run_wilcoxon() computes
    rank/p_holm over the entire non-Stouffer subset of the results table in
    one pass (no groupby on `comparison` before the Holm step), so this is
    already the broadest defensible family scope for this test set: every
    Wilcoxon test run in this script answers a variation of "does this
    metric differ between adjacent architectures for this model," and all of
    them compete for the same alpha budget. (An earlier version of this
    docstring said "40 tests," which undercounted both the metric list
    length, 7 not 5, and the fact that both architecture pairs share one
    family rather than each having their own; the code was already correct,
    only this comment was stale.)

ICC is computed on per-run aggregate metrics (the per_run_metrics_all.csv
file) because it is a variance decomposition, not a pairwise test.
"""

import sys
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.mixed_linear_model import MixedLM

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import read_table_clean, SENTINEL_VALUE, coerce_score, CRITERIA
from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY, MODEL_SPECS
from evaluate_architecture_metrics import filter_failed_scenarios, normalize_alternative, build_gt_lookup

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

ICC_INPUT_CSV = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
OUTPUT_XLSX = PROJECT_ROOT / "paper" / "per_run_metrics" / "significance_tests.xlsx"

METRICS = [
    "kendall_tau",
    "spearman_rho",
    "top1_accuracy",
    "top2_accuracy",
    "overall_mae",
    "overall_rmse",
    "overall_rmse_mae_ratio",
]

ARCH_SHORT = {
    "Direct_LLM_Scoring": "AD",
    "Example-Guided_LLM_Scoring": "AE",
    "LLM-Parameterized_Reference_Scoring": "AH",
}

MODEL_FOLDERS = {k: spec["output_folder"] for k, spec in MODEL_SPECS.items()}

ARCHITECTURES = [
    "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring",
]

PAIRS = [
    ("Direct_LLM_Scoring", "Example-Guided_LLM_Scoring"),
    ("Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"),
]

GT_SCORE_COLS = {
    "energy_cost": "energy_cost_score",
    "environmental": "environmental_score",
    "comfort": "comfort_score",
    "practicality": "practicality_score",
}

ARCH_SCORE_COLS = {
    "energy_cost": "energy_cost",
    "environmental": "environmental",
    "comfort": "comfort",
    "practicality": "practicality",
}

CLIFF_BOUNDS = [(0.0, 0.147, "negligible"), (0.147, 0.33, "small"),
                (0.33, 0.474, "medium")]


# ---------------------------------------------------------------------------
# Ground truth loading
# ---------------------------------------------------------------------------

def load_ground_truth():
    """Load all three ground truth files and return a dict keyed by decision type.

    Each GT DataFrame is renamed so that score columns use gt_* prefix and
    rank column uses gt_rank.  Only the columns needed for per-scenario
    metric computation are retained.
    """
    gt_by_type = {}
    for dtype, fname in [("HVAC", "ground_truth_hvac.xlsx"),
                         ("Appliance", "ground_truth_appliance.xlsx"),
                         ("Shower", "ground_truth_shower.xlsx")]:
        df = read_table_clean(GROUND_TRUTH_DIR / fname)
        rename_map = {}
        for criterion, gt_col in GT_SCORE_COLS.items():
            if gt_col in df.columns:
                rename_map[gt_col] = f"gt_{criterion}"
        if "rank" in df.columns:
            rename_map["rank"] = "gt_rank"
        df = df.rename(columns=rename_map)
        df["question"] = df["question"].str.strip()
        df["location"] = df["location"].str.strip()
        df["alternative"] = df["alternative"].astype(str).str.strip()
        gt_by_type[dtype] = df
    return gt_by_type


# ---------------------------------------------------------------------------
# Architecture run file loading and matching
# ---------------------------------------------------------------------------




def match_arch_to_gt(arch_df, arch_name, gt_lookup):
    """Match architecture scenarios to GT by (question, location) content keys.

    Returns a DataFrame of matched (arch_scenario, GT scenario) rows with
    per-alternative arch and GT scores.  This mirrors the match_scenarios
    logic in evaluate_architecture_metrics.py but is scoped to a single run dataframe.
    """
    matched_rows = []

    for arch_sid in arch_df["scenario_id"].unique():
        arch_sub = arch_df[arch_df["scenario_id"] == arch_sid]
        arch_dtype = arch_sub["decision_type"].iloc[0]
        q = arch_sub["question"].iloc[0]
        loc = arch_sub["location"].iloc[0]

        key = (q, loc)
        if key not in gt_lookup:
            continue

        arch_norm_alts = {}
        for _, row in arch_sub.iterrows():
            norm_alt = normalize_alternative(row["alternative"], arch_dtype)
            arch_norm_alts[norm_alt] = row

        param_pairs = []
        if arch_dtype == "HVAC":
            _pairs = [("outdoor_temp", "outdoor_temp")]
        elif arch_dtype == "Appliance":
            _pairs = [("appliance_age", "appliance_age")]
        else:
            _pairs = [
                ("outdoor_temp", "outdoor_temp"),
                ("flow_rate", "gpm"),
                ("household_size", "household_size"),
                ("utility_budget", "utility_budget"),
                ("housing_type", "housing_type"),
            ]
        for arch_col, gt_key in _pairs:
            v = str(arch_sub[arch_col].iloc[0]).strip() if arch_col in arch_sub.columns else ""
            if v and v.lower() not in ("", "n/a", "nan", "none"):
                param_pairs.append((v, gt_key))

        best_match = None
        best_score = 0

        for gt_entry in gt_lookup[key]:
            if gt_entry["used"]:
                continue
            if gt_entry["decision_type"] != arch_dtype:
                continue
            overlap = len(set(gt_entry["alt_map"].keys()) & set(arch_norm_alts.keys()))
            extra = 0
            for arch_val, gt_key in param_pairs:
                gt_val = str(gt_entry.get(gt_key, "")).strip()
                if gt_val and arch_val == gt_val:
                    extra += 100
            score = overlap + extra
            if score > best_score:
                best_score = score
                best_match = gt_entry

        if best_match is None or best_score == 0:
            continue

        best_match["used"] = True

        matched_alts = 0
        for norm_alt, arch_row in arch_norm_alts.items():
            gt_row = best_match["alt_map"].get(norm_alt)
            if gt_row is None:
                continue
            matched_alts += 1
            merged = {
                "arch_scenario_id": arch_sid,
                "gt_scenario_id": best_match["gt_sid"],
                "decision_type": arch_dtype,
                "alternative": norm_alt,
                "question": q,
                "location": loc,
            }
            for c in CRITERIA:
                gt_val = gt_row.get(f"gt_{c}", np.nan)
                arch_val = arch_row.get(ARCH_SCORE_COLS[c], np.nan)
                merged[f"gt_{c}"] = coerce_score(gt_val) if gt_val is not None else np.nan
                merged[f"arch_{c}"] = coerce_score(arch_val) if arch_val is not None else np.nan
            merged["gt_rank"] = gt_row.get("gt_rank", np.nan)
            merged["arch_rank"] = arch_row.get("rank", np.nan)
            merged["arch_weighted_score"] = arch_row.get("weighted_score", np.nan)
            merged["gt_mavt_score"] = gt_row.get("mavt_score", np.nan)
            matched_rows.append(merged)

        if 0 < matched_alts < 3:
            warnings.warn(
                f"[match_arch_to_gt] only {matched_alts}/3 alternatives matched "
                f"for sid={arch_sid} ({arch_dtype}) "
                f"— ranking metrics may be unreliable",
                stacklevel=2,
            )

    for entries in gt_lookup.values():
        for e in entries:
            e["used"] = False

    return pd.DataFrame(matched_rows)


# ---------------------------------------------------------------------------
# Per-scenario metric computation
# ---------------------------------------------------------------------------

def _compute_weighted_score(row):
    """Compute weighted MAVT score from four criterion scores and standard weights."""
    try:
        ws = (
            CRITERION_WEIGHTS["energy_cost"] * float(row["arch_energy_cost"]) +
            CRITERION_WEIGHTS["environmental"] * float(row["arch_environmental"]) +
            CRITERION_WEIGHTS["comfort"] * float(row["arch_comfort"]) +
            CRITERION_WEIGHTS["practicality"] * float(row["arch_practicality"])
        )
        return ws
    except (ValueError, TypeError):
        return np.nan


def compute_scenario_metrics(matched_df):
    """Compute per-scenario metrics from matched arch-GT data.

    For each scenario (arch_scenario_id), computes:
    - kendall_tau: Kendall's tau between arch rank and GT rank (3 alternatives)
    - spearman_rho: Spearman rank correlation between arch rank and GT rank
    - top1_accuracy: 1 if arch best alternative matches GT best, else 0
    - top2_accuracy: 1 if GT best alternative is in arch's top 2, else 0
    - overall_mae: mean absolute error across 4 criteria, 3 alternatives
    - overall_rmse: root mean squared error across 4 criteria, 3 alternatives
    - overall_rmse_mae_ratio: RMSE / MAE for this scenario

    Returns a DataFrame with one row per scenario.
    """
    scenario_rows = []
    for sid, group in matched_df.groupby("arch_scenario_id"):
        if len(group) < 2:
            continue

        gt_r = pd.to_numeric(group["gt_rank"], errors="coerce").values
        ar_r = pd.to_numeric(group["arch_rank"], errors="coerce").values

        has_sentinel = np.isnan(gt_r).any() or np.isnan(ar_r).any() or (gt_r == SENTINEL_VALUE).any() or (ar_r == SENTINEL_VALUE).any()
        if has_sentinel:
            kendall_tau = np.nan
            spearman_rho = np.nan
        else:
            if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
                tau, _ = stats.kendalltau(gt_r, ar_r)
                kendall_tau = tau if not np.isnan(tau) else 0.0
            else:
                kendall_tau = 1.0 if np.array_equal(gt_r, ar_r) else 0.0
            if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
                rho, _ = stats.spearmanr(gt_r, ar_r)
                spearman_rho = rho if not np.isnan(rho) else 0.0
            else:
                spearman_rho = 1.0 if np.array_equal(gt_r, ar_r) else 0.0

        if has_sentinel:
            top1 = np.nan
            top2 = np.nan
        else:
            gt_best_idx = np.nanargmin(gt_r)
            ar_best_idx = np.nanargmin(ar_r)
            gt_best_alt = group.iloc[gt_best_idx]["alternative"]
            ar_best_alt = group.iloc[ar_best_idx]["alternative"]
            top1 = 1.0 if gt_best_alt == ar_best_alt else 0.0
            ar_top2 = set(group.nsmallest(2, "arch_rank")["alternative"].values)
            top2 = 1.0 if gt_best_alt in ar_top2 else 0.0

        abs_errors = []
        sq_errors = []
        for c in CRITERIA:
            gt_col = f"gt_{c}"
            ar_col = f"arch_{c}"
            gt_vals = pd.to_numeric(group[gt_col], errors="coerce").values
            ar_vals = pd.to_numeric(group[ar_col], errors="coerce").values
            valid = np.isfinite(gt_vals) & np.isfinite(ar_vals)
            if valid.any():
                abs_errors.extend(np.abs(ar_vals[valid] - gt_vals[valid]).tolist())
                sq_errors.extend(((ar_vals[valid] - gt_vals[valid]) ** 2).tolist())

        if abs_errors:
            overall_mae = np.mean(abs_errors)
            overall_rmse = np.sqrt(np.mean(sq_errors))
            rmse_mae_ratio = overall_rmse / overall_mae if overall_mae > 0 else np.nan
        else:
            overall_mae = np.nan
            overall_rmse = np.nan
            rmse_mae_ratio = np.nan

        scenario_rows.append({
            "scenario_id": sid,
            "decision_type": group["decision_type"].iloc[0],
            "kendall_tau": kendall_tau,
            "spearman_rho": spearman_rho,
            "top1_accuracy": top1,
            "top2_accuracy": top2,
            "overall_mae": overall_mae,
            "overall_rmse": overall_rmse,
            "overall_rmse_mae_ratio": rmse_mae_ratio,
        })

    return pd.DataFrame(scenario_rows)


# ---------------------------------------------------------------------------
# Main per-scenario data pipeline
# ---------------------------------------------------------------------------

def compute_per_scenario_metrics_from_raw():
    """Load raw run files and compute per-scenario metrics for all model x arch x run (Method A).

    For each of the 4 models and 3 architectures, loads 5 run xlsx files,
    matches each run to ground truth by (question, location) content keys,
    and computes per-scenario metrics (Kendall tau, Spearman rho, Top-1,
    Top-2, MAE, RMSE, RMSE/MAE ratio).

    The 5 runs are averaged to produce a single per-scenario-per-model
    metric vector (195 scenarios per model). This is Method A (per-run
    metrics averaged). The same method feeds generate_paper_results_numbers.py,
    so significance tests here test the same point estimate as the paper's
    results tables.

    Returns
    -------
    per_scenario_df : DataFrame
        Long-form DataFrame with columns: model, scenario_id, decision_type,
        and the 5 averaged metric columns.  Shape approximately
        4 models x 195 scenarios = 780 rows.
    """
    gt_by_type = load_ground_truth()
    gt_lookup = build_gt_lookup(gt_by_type)

    all_rows = []

    for model_key, folder_name in MODEL_FOLDERS.items():
        output_dir = PROJECT_ROOT / folder_name
        print(f"  Processing model: {model_key} ({folder_name})")

        for arch_name in ARCHITECTURES:
            run_pattern = f"{arch_name}_results_run_*.xlsx"
            run_files = sorted(output_dir.glob(run_pattern))
            if not run_files:
                print(f"    [{arch_name}] No run files found, skipping")
                continue

            run_scenario_dfs = []
            for rf in run_files:
                arch_df = read_table_clean(rf)
                for c in CRITERIA:
                    col = ARCH_SCORE_COLS[c]
                    if col in arch_df.columns:
                        arch_df[col] = pd.to_numeric(arch_df[col], errors="coerce")
                if "rank" in arch_df.columns:
                    arch_df["rank"] = pd.to_numeric(arch_df["rank"], errors="coerce")

                matched = match_arch_to_gt(arch_df, arch_name, gt_lookup)
                if len(matched) == 0:
                    continue
                matched, n_failed, n_total = filter_failed_scenarios(matched)
                if len(matched) == 0:
                    continue
                scen_metrics = compute_scenario_metrics(matched)
                run_scenario_dfs.append(scen_metrics)

            if not run_scenario_dfs:
                print(f"    [{arch_name}] No matched scenarios across all runs")
                continue

            all_runs = pd.concat(run_scenario_dfs, ignore_index=True)
            metric_cols = [m for m in METRICS if m in all_runs.columns]
            averaged = all_runs.groupby(["scenario_id", "decision_type"], as_index=False)[metric_cols].mean()
            averaged["model"] = model_key
            averaged["architecture"] = arch_name
            all_rows.append(averaged)

            n_scenarios = len(averaged)
            n_runs_used = len(run_scenario_dfs)
            print(f"    [{arch_name}] {n_scenarios} scenarios from {n_runs_used} runs")

    if not all_rows:
        print("  WARNING: No per-scenario metrics computed")
        return pd.DataFrame()

    per_scenario_df = pd.concat(all_rows, ignore_index=True)
    print(f"\n  Total per-scenario rows: {len(per_scenario_df)} "
          f"({per_scenario_df['model'].nunique()} models x "
          f"~{per_scenario_df.groupby(['model','architecture'])['scenario_id'].nunique().median():.0f} scenarios)")
    return per_scenario_df


# ---------------------------------------------------------------------------
# ICC (kept on per-run aggregates)
# ---------------------------------------------------------------------------

def load_icc_data():
    """Load per_run_metrics_all.csv filtered to Overall rows for ICC computation.

    ICC is a variance decomposition, not a pairwise test, so it remains
    on the per-run aggregate data.
    """
    df = pd.read_csv(ICC_INPUT_CSV)
    return df[df["decision_type"] == "Overall"].copy()


def compute_icc(df, metric):
    """Compute ICC(2,1) for a single metric within one architecture.

    What:  One-way random-effects ICC measuring the proportion of total
           variance attributable to differences between models.
    Why:   High ICC means model choice dominates run-to-run noise, so
           architecture rankings are model-dependent rather than stochastic.
    How:   Uses one-way ANOVA decomposition:
             MS_model  = variance of the 4 model means
             MS_error  = mean of the 4 within-model variances (each from 5 runs)
             ICC(2,1)  = (MS_model - MS_error) /
                          (MS_model + (k - 1) * MS_error)
           where k = 5 runs per model.
    Interp: ICC > 0.5 suggests model identity explains more variance than
            residual noise; ICC < 0.15 suggests runs are nearly exchangeable
            across models.
    """
    groups = df.groupby("model")[metric]
    model_means = groups.mean()
    model_vars = groups.var(ddof=1)
    k = groups.count().iloc[0]
    assert (groups.count() == k).all(), f"Unbalanced groups in ICC: counts={dict(groups.count())}"

    n_models = len(model_means)
    grand_mean = df[metric].mean()

    ms_model = np.sum((model_means - grand_mean) ** 2) / (n_models - 1)
    ms_error = model_vars.mean()

    denom = ms_model + (k - 1) * ms_error
    if abs(denom) < 1e-15:
        return 0.0, 0.0, 0.0

    icc = (ms_model - ms_error) / denom
    sigma2_model = max(ms_model - ms_error, 0.0) / denom
    sigma2_residual = 1.0 - sigma2_model

    return icc, sigma2_model, sigma2_residual


def run_icc(df):
    """Compute ICC(2,1) for every architecture x metric combination.

    Returns a DataFrame with columns:
        architecture, metric, ICC, sigma2_model_frac, sigma2_residual_frac
    """
    rows = []
    for arch in df["architecture"].unique():
        sub = df[df["architecture"] == arch]
        for m in METRICS:
            vals = sub[m].dropna()
            if len(vals) < 2 or vals.nunique() == 0:
                rows.append((ARCH_SHORT[arch], m, np.nan, np.nan, np.nan))
                continue
            icc, s2m, s2r = compute_icc(sub, m)
            rows.append((ARCH_SHORT[arch], m, round(icc, 4),
                         round(s2m, 4), round(s2r, 4)))
    return pd.DataFrame(rows, columns=[
        "architecture", "metric", "ICC", "sigma2_model_frac",
        "sigma2_residual_frac"
    ])


# ---------------------------------------------------------------------------
# Mixed-Model tests (per-scenario)
# ---------------------------------------------------------------------------

def mixed_model_pair(per_scenario_df, arch_a, arch_b, metric):
    """Mixed-effects model for two architectures on per-scenario metric differences.

    What:  Mixed-effects model on per-scenario metric differences between
           two architectures, with a random intercept for model.
    Why:   The random intercept accounts for systematic between-model
           offsets so the fixed intercept tests the average architectural
           difference across all models.
    How:   For each model m and scenario s compute diff(s) = metric_A(m,s) -
           metric_B(m,s).  Fit diff ~ 1 + (1|model) via statsmodels MixedLM.
           The t-test on the intercept tests H0: no average difference.
    Interp: |t| > 2 or p < 0.05 indicates one architecture systematically
            outperforms the other after accounting for model effects.
    """
    sub_a = per_scenario_df[per_scenario_df["architecture"] == arch_a].set_index(
        ["model", "scenario_id"])[metric]
    sub_b = per_scenario_df[per_scenario_df["architecture"] == arch_b].set_index(
        ["model", "scenario_id"])[metric]
    common = sub_a.index.intersection(sub_b.index)
    if len(common) < 10:
        return np.nan, np.nan, np.nan, np.nan

    diff = sub_a.loc[common].values - sub_b.loc[common].values
    model_labels = [idx[0] for idx in common]

    try:
        mod = MixedLM(diff, np.ones(len(diff)), groups=model_labels)
        res = mod.fit(reml=True, disp=False)
        intercept = res.fe_params[0]
        se = res.bse[0]
        tval = res.tvalues[0]
        pval = res.pvalues[0]
    except Exception:
        intercept = np.nanmean(diff)
        se = np.nanstd(diff, ddof=1) / np.sqrt(len(diff))
        tval = intercept / se if se > 0 else 0.0
        pval = 2 * (1 - stats.norm.cdf(abs(tval)))

    return intercept, se, tval, pval


def run_mixed_model(per_scenario_df):
    """Run mixed-model tests for both architecture pairs and all metrics."""
    rows = []
    for arch_a, arch_b in PAIRS:
        for m in METRICS:
            coef, se, tval, pval = mixed_model_pair(
                per_scenario_df, arch_a, arch_b, m)
            rows.append((
                f"{ARCH_SHORT[arch_a]} vs {ARCH_SHORT[arch_b]}", m,
                round(coef, 6) if not np.isnan(coef) else np.nan,
                round(se, 6) if not np.isnan(se) else np.nan,
                round(tval, 4) if not np.isnan(tval) else np.nan,
                round(pval, 6) if not np.isnan(pval) else np.nan,
            ))
    return pd.DataFrame(rows, columns=[
        "comparison", "metric", "coefficient", "SE", "t_statistic", "p_value"
    ])


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank tests (per-scenario, n=195)
# ---------------------------------------------------------------------------

def wilcoxon_pair_model(per_scenario_df, arch_a, arch_b, metric, model):
    """Wilcoxon signed-rank test for one model and one architecture pair.

    What:  Non-parametric paired test of whether the metric differs
           between two architectures for a specific model, using the
           195 per-scenario metric values as paired observations.
    Why:   Wilcoxon makes no normality assumption and is appropriate for
           scenario-level metrics which may not be normally distributed.
           With n=195 there is substantial statistical power.
    How:   Computes the Wilcoxon T statistic manually, then derives Z
           via the normal approximation (mean=n(n+1)/4,
           std=sqrt(n(n+1)(2n+1)/24) with tie correction).  This avoids
           scipy's p->Z overflow for extreme p-values.
    Interp: p < 0.05 suggests the two architectures produce different
            metric values for this model across scenarios.
    """
    sub_a = per_scenario_df[
        (per_scenario_df["architecture"] == arch_a) &
        (per_scenario_df["model"] == model)
    ].set_index("scenario_id")[metric].dropna()

    sub_b = per_scenario_df[
        (per_scenario_df["architecture"] == arch_b) &
        (per_scenario_df["model"] == model)
    ].set_index("scenario_id")[metric].dropna()

    common = sub_a.index.intersection(sub_b.index)
    if len(common) < 10:
        return np.nan, np.nan, 0

    a_vals = sub_a.loc[common].values.astype(float)
    b_vals = sub_b.loc[common].values.astype(float)

    if np.allclose(a_vals, b_vals):
        return 0.0, 1.0, len(common)

    diffs = a_vals - b_vals
    nonzero_mask = diffs != 0
    nonzero_diffs = diffs[nonzero_mask]
    n = len(nonzero_diffs)

    if n == 0:
        return 0.0, 1.0, len(common)

    abs_diffs = np.abs(nonzero_diffs)
    ranks = stats.rankdata(abs_diffs)
    signed_ranks = ranks * np.sign(nonzero_diffs)

    # T statistic = min(sum of positive ranks, sum of negative ranks)
    pos_sum = signed_ranks[signed_ranks > 0].sum()
    neg_sum = -signed_ranks[signed_ranks < 0].sum()
    T = min(pos_sum, neg_sum)

    # Normal approximation for Z
    mean_T = n * (n + 1) / 4.0
    std_T = np.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)

    # Continuity correction: shift T toward the mean by 0.5
    z = (T - mean_T - 0.5 * np.sign(mean_T - T)) / std_T if std_T > 0 else 0.0

    # Two-sided p-value from Z
    pval = 2 * (1 - stats.norm.cdf(abs(z)))

    if a_vals.sum() < b_vals.sum():
        z = -z

    return z, pval, len(common)


def stouffer_combine(z_scores, ns):
    """Combine independent p-values via Stouffer's Z method.

    What:  Meta-analytic combination of k independent test results into
           a single omnibus p-value.
    Why:   Each model provides an independent test; Stouffer's method
           weights by sqrt(n_i) for optimal combination.
    How:   Z_combined = sum(w_i * z_i) / sqrt(sum(w_i^2)) where w_i = sqrt(n_i).
           p_combined  = 2 * (1 - Phi(|Z_combined|)).
           Non-finite Z values (inf from extreme tests) are excluded;
           the combined Z is then the sum of finite Zs / sqrt(k_finite).
    Interp: Significant combined p indicates at least one model shows a
            consistent architectural difference.
    """
    z_arr = np.array(z_scores, dtype=float)
    mask = np.isfinite(z_arr)
    if mask.sum() == 0:
        return np.nan, np.nan
    z_valid = z_arr[mask]
    ns_arr = np.array(ns, dtype=float)
    w = np.sqrt(ns_arr[mask])
    z_combined = np.sum(w * z_valid) / np.sqrt(np.sum(w ** 2))
    p_combined = 2 * (1 - stats.norm.cdf(abs(z_combined)))
    return z_combined, p_combined


def run_wilcoxon(per_scenario_df):
    """Run Wilcoxon tests per model + Stouffer combination.

    Uses per-scenario metrics (n=195 paired observations per model) instead
    of per-run aggregates (n=5), giving meaningful p-values.
    """
    models = sorted(per_scenario_df["model"].unique())
    rows = []
    for arch_a, arch_b in PAIRS:
        for m in METRICS:
            z_list, p_list, n_list = [], [], []
            for model in models:
                z, p, n = wilcoxon_pair_model(
                    per_scenario_df, arch_a, arch_b, m, model)
                z_list.append(z)
                p_list.append(p)
                n_list.append(n)
                rows.append((
                    f"{ARCH_SHORT[arch_a]} vs {ARCH_SHORT[arch_b]}", m,
                    model,
                    round(z, 4) if not np.isnan(z) else np.nan,
                    round(p, 6) if not np.isnan(p) else np.nan,
                    n, np.nan, np.nan
                ))
            z_comb, p_comb = stouffer_combine(z_list, n_list)
            rows.append((
                f"{ARCH_SHORT[arch_a]} vs {ARCH_SHORT[arch_b]}", m,
                "Stouffer", np.nan, np.nan, np.nan,
                round(z_comb, 4) if not np.isnan(z_comb) else np.nan,
                round(p_comb, 6) if not np.isnan(p_comb) else np.nan,
            ))
    df = pd.DataFrame(rows, columns=[
        "comparison", "metric", "model", "Z_statistic", "p_value",
        "n_scenarios", "Stouffer_Z", "Stouffer_p"
    ])

    alpha = 0.05
    model_mask = df["model"] != "Stouffer"
    holm_df = df[model_mask].copy()
    holm_df = holm_df.reset_index(drop=True)
    holm_df["rank"] = holm_df["p_value"].rank(method="min", ascending=True, na_option="keep")
    k = holm_df["p_value"].notna().sum()
    holm_df["p_holm"] = holm_df.apply(
        lambda r: min(r["p_value"] * (k - r["rank"] + 1), 1.0) if pd.notna(r["p_value"]) else np.nan,
        axis=1
    )
    holm_df["significant_holm"] = holm_df["p_holm"].apply(
        lambda p: p < alpha if pd.notna(p) else False
    )
    df["p_holm"] = np.nan
    df["significant_holm"] = False
    df.loc[model_mask, "p_holm"] = holm_df["p_holm"].values
    df.loc[model_mask, "significant_holm"] = holm_df["significant_holm"].values
    return df


# ---------------------------------------------------------------------------
# Effect sizes (per-scenario)
# ---------------------------------------------------------------------------

def cohens_d(a, b):
    """Compute Cohen's d for two paired samples.

    What:  Standardised mean difference adjusting for correlation.
    Why:   Expresses the magnitude of an architectural difference in
           units of standard deviation, making it comparable across metrics.
    How:   d = mean(a - b) / sd(a - b), using the paired difference
           standard deviation.
    Interp: |d| < 0.2 negligible, < 0.5 small, < 0.8 medium, else large
            (Cohen 1988).
    """
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[np.isfinite(d)]
    if len(d) < 2:
        return np.nan
    m = d.mean()
    s = d.std(ddof=1)
    return m / s if s > 1e-15 else 0.0


def rank_biserial(z_stat, n):
    """Rank-biserial correlation from Wilcoxon Z.

    What:  Effect size for the Wilcoxon signed-rank test.
    Why:   Converts the test statistic into a bounded [-1, 1] measure
           of how consistently one architecture ranks higher.
    How:   r = Z / sqrt(N) where N is the number of paired observations.
    Interp: |r| < 0.1 negligible, < 0.3 small, < 0.5 medium, else large.
    """
    if np.isnan(z_stat) or n is None or n < 1:
        return np.nan
    return z_stat / np.sqrt(n)


def cliffs_delta(a, b):
    """Cliff's delta non-parametric effect size.

    What:  Probability that a random observation from A exceeds one from B
           minus the reverse, normalised by sample size.
    Why:   Robust to non-normality and outliers; directly interpretable
           as a dominance measure.
    How:   delta = (# pairs where A > B - # pairs where A < B) / (n_A * n_B).
    Interp: |delta| < 0.147 negligible, < 0.33 small, < 0.474 medium,
            else large (Vargha & Delaney 2000).
    """
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return np.nan
    greater = sum(1 for ai in a for bi in b if ai > bi)
    less = sum(1 for ai in a for bi in b if ai < bi)
    return (greater - less) / (n_a * n_b)


def cliffs_delta_interpretation(d):
    """Return a plain-ASCII interpretation label for Cliff's delta."""
    ad = abs(d)
    for lo, hi, label in CLIFF_BOUNDS:
        if ad < hi:
            return label
    return "large"


def run_effect_sizes(per_scenario_df):
    """Compute all effect sizes for each pairwise comparison and metric.

    Uses per-scenario metrics (n=195) for Cohen's d, rank-biserial, and
    Cliff's delta, giving stable and meaningful effect size estimates.
    """
    models = sorted(per_scenario_df["model"].unique())
    rows = []
    for arch_a, arch_b in PAIRS:
        for m in METRICS:
            for model in models:
                ma_df = per_scenario_df[
                    (per_scenario_df["architecture"] == arch_a) &
                    (per_scenario_df["model"] == model)
                ].set_index("scenario_id")[m].dropna()
                mb_df = per_scenario_df[
                    (per_scenario_df["architecture"] == arch_b) &
                    (per_scenario_df["model"] == model)
                ].set_index("scenario_id")[m].dropna()
                common_m = ma_df.index.intersection(mb_df.index)
                ma = ma_df.loc[common_m].values
                mb = mb_df.loc[common_m].values

                d_val = cohens_d(ma, mb)
                z_w, p_w, n_w = wilcoxon_pair_model(
                    per_scenario_df, arch_a, arch_b, m, model)
                rb = rank_biserial(z_w, n_w)
                cd = cliffs_delta(ma, mb)
                cd_label = cliffs_delta_interpretation(cd) if not np.isnan(cd) else ""

                rows.append((
                    f"{ARCH_SHORT[arch_a]} vs {ARCH_SHORT[arch_b]}", m, model,
                    round(d_val, 4) if not np.isnan(d_val) else np.nan,
                    round(rb, 4) if not np.isnan(rb) else np.nan,
                    round(cd, 4) if not np.isnan(cd) else np.nan,
                    cd_label,
                ))
    return pd.DataFrame(rows, columns=[
        "comparison", "metric", "model", "Cohens_d",
        "rank_biserial_r", "Cliffs_delta", "Cliffs_delta_interp"
    ])


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def print_table(title, df):
    """Print a formatted table to stdout using plain ASCII."""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)
    print(df.to_string(index=False))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("  STATISTICAL SIGNIFICANCE TESTING")
    print("  Per-scenario Wilcoxon (n=195) + ICC + MixedLM + Effect Sizes")
    print("=" * 72)

    # --- Per-scenario metrics from raw run files ---
    print("\n[1] Computing per-scenario metrics from raw run files ...")
    per_scenario_df = compute_per_scenario_metrics_from_raw()

    if per_scenario_df.empty:
        print("ERROR: No per-scenario metrics computed. Cannot proceed.")
        return

    # --- ICC on per-run aggregates ---
    print("\n[2] Intraclass Correlation Coefficient (ICC) ...")
    icc_df_raw = load_icc_data()
    print(f"    Loaded {len(icc_df_raw)} Overall rows from per_run_metrics_all.csv")
    icc_df = run_icc(icc_df_raw)
    print_table("ICC(2,1) Variance Decomposition", icc_df)

    # --- Mixed-Model tests ---
    print("\n[3] Mixed-Model Significance Tests (per-scenario) ...")
    mm_df = run_mixed_model(per_scenario_df)
    print_table("MixedLM: diff ~ 1 + (1|model) [per-scenario]", mm_df)

    # --- Wilcoxon + Stouffer ---
    print("\n[4] Per-Model Wilcoxon + Stouffer Combination (per-scenario, n=195) ...")
    wil_df = run_wilcoxon(per_scenario_df)
    print_table("Wilcoxon Signed-Rank + Stouffer [per-scenario]", wil_df)

    # --- Effect Sizes ---
    print("\n[5] Effect Sizes (per-scenario, n=195) ...")
    es_df = run_effect_sizes(per_scenario_df)
    print_table("Effect Sizes [per-scenario]", es_df)

    # --- Write Excel ---
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        icc_df.to_excel(writer, sheet_name="ICC", index=False)
        mm_df.to_excel(writer, sheet_name="MixedModel", index=False)
        wil_df.to_excel(writer, sheet_name="Wilcoxon", index=False)
        es_df.to_excel(writer, sheet_name="EffectSizes", index=False)

    print(f"\nResults written to {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
