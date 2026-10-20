"""Unified objective-weight validation suite (MEREC, entropy, implied, diagnostics).

VALIDATION ONLY. These analyses triangulate the 35/30/20/15 criterion weights.
No architecture or calculator may import this module or change weights at runtime.

This module consolidates four formerly separate scripts:
    EntropyWeights.py, merec_weights.py, implied_weights.py, WeightDiagnostics.py

Each method keeps its own numerical code path exactly as in the original script
(including its own ground-truth loading and rounding). Only genuinely identical
plumbing is shared (constants with identical values).

CLI:
    python -m common.weighting.weight_analysis \
        --method merec|entropy|implied|diagnostics|all --output-dir DIR [--scope full|test]

Output files (all written flat into --output-dir):
    entropy      -> entropy_weights.xlsx
    merec        -> merec_weights_summary.xlsx
    implied      -> implied_weights_summary.xlsx
    diagnostics  -> weight_discrimination[_test].xlsx, cost_env_collinearity[_test].xlsx
                    and the matching .csv files
"""

from __future__ import annotations

import argparse
import sys
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from common.paths import (
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
    require_safe_output_path,
)

PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.sentinel_utils import (  # noqa: E402
    _atomic_write_xlsx,
    find_file_in_paths,
    read_table_clean,
)

# Console output of the implied-weights report contains math symbols; make sure
# stdout can encode them on Windows (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# ---------------------------------------------------------------------------
# Shared constants (values identical across the original scripts)
# ---------------------------------------------------------------------------

SUBJECTIVE_WEIGHTS = {
    "energy_cost":   0.30,
    "environmental": 0.35,
    "comfort":       0.20,
    "practicality":  0.15,
}

DECISION_TYPES = ("HVAC", "Appliance", "Shower")

# merec / implied (identical in both originals)
GT_FILES = {
    "HVAC":      "ground_truth_hvac.xlsx",
    "Appliance": "ground_truth_appliance.xlsx",
    "Shower":    "ground_truth_shower.xlsx",
}
SCORE_COLS = {
    "energy_cost":   "energy_cost_score",
    "environmental": "environmental_score",
    "comfort":       "comfort_score",
    "practicality":  "practicality_score",
}
CRITERIA = list(SCORE_COLS.keys())
RANK_COL = "rank"
GROUND_TRUTH_DIR = PROJECT_ROOT / "workbooks" / "ground_truth"
SEARCH_DIRS = [str(GROUND_TRUTH_DIR)]

ENTROPY_OUTPUT_NAME = "entropy_weights.xlsx"
MEREC_OUTPUT_NAME = "merec_weights_summary.xlsx"
IMPLIED_OUTPUT_NAME = "implied_weights_summary.xlsx"

# Legacy default destinations (used only by the deprecated per-script shims so
# that the existing pipeline invocation keeps writing where it always wrote).
LEGACY_METHODOLOGY_DIR = PROJECT_ROOT / "workbooks" / "methodology"
# Implied weights used to land in a scoring_logic/ subfolder, with a second stale
# copy under misc_scripts/. Both tracked copies were scrapped on 2026-10-03; the
# workbook now regenerates flat beside the other methodology workbooks.
LEGACY_IMPLIED_DIR = LEGACY_METHODOLOGY_DIR
LEGACY_DIAG_CSV_DIR = PROJECT_ROOT / "results" / "methodology"


# ===========================================================================
# ENTROPY  (from EntropyWeights.py)
# ===========================================================================

# Entropy has its own criterion order (environmental first) and its own
# column-name candidates; kept separate from the merec/implied definitions.
ENTROPY_SUBJECTIVE_WEIGHTS = {
    "environmental": 0.35,
    "energy_cost": 0.30,
    "comfort": 0.20,
    "practicality": 0.15,
}

CRITERION_COLUMN_MAP = {
    "energy_cost": ("gt_energy_cost", "energy_cost_score", "energy_cost"),
    "environmental": ("gt_environmental", "environmental_score", "environmental"),
    "comfort": ("gt_comfort", "comfort_score", "comfort"),
    "practicality": ("gt_practicality", "practicality_score", "practicality"),
}


def get_project_root() -> Path:
    """Return the repository root directory."""
    return PROJECT_ROOT


def resolve_existing_path(project_root: Path, relative_candidates: tuple[str, ...]) -> Path:
    """Return the first existing path from a list of relative candidates."""
    for relative_candidate in relative_candidates:
        candidate_path = project_root / relative_candidate
        if candidate_path.exists():
            return candidate_path
    raise FileNotFoundError(
        "Could not find any of the expected files: "
        + ", ".join(relative_candidates)
    )


def resolve_criterion_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map canonical criterion names to the actual columns present in a DataFrame."""
    resolved_columns: dict[str, str] = {}
    for canonical_name, candidate_names in CRITERION_COLUMN_MAP.items():
        for candidate_name in candidate_names:
            if candidate_name in df.columns:
                resolved_columns[canonical_name] = candidate_name
                break
        else:
            raise KeyError(
                f"Missing criterion column for {canonical_name}. "
                f"Looked for: {candidate_names}"
            )
    return resolved_columns


def load_ground_truth_data(project_root: Path) -> pd.DataFrame:
    """Load and concatenate all ground-truth tables into one DataFrame."""
    file_specs = (
        ("HVAC", ("workbooks/ground_truth/ground_truth_hvac.xlsx",)),
        (
            "Appliance",
            ("workbooks/ground_truth/ground_truth_appliance.xlsx",),
        ),
        (
            "Shower",
            ("workbooks/ground_truth/ground_truth_shower.xlsx",),
        ),
    )

    data_frames: list[pd.DataFrame] = []
    for decision_type, relative_candidates in file_specs:
        csv_path = resolve_existing_path(project_root, relative_candidates)
        df = read_table_clean(csv_path)
        df = df.copy()
        df["decision_type"] = decision_type
        df["source_file"] = csv_path.name
        data_frames.append(df)

    return pd.concat(data_frames, ignore_index=True)


def entropy_weights(data: pd.DataFrame, column_map: dict[str, str], epsilon: float = 1e-10) -> pd.Series:
    """Compute Shannon entropy weights for the provided criterion columns.

    The calculation follows:
    1. Normalize each criterion column to a probability distribution.
    2. Replace zero probabilities with a small epsilon before computing logs.
    3. Compute entropy: E_j = -k * sum(p_ij * ln(p_ij)), where k = 1 / ln(n).
    4. Compute divergence: d_j = 1 - E_j.
    5. Compute objective weight: w_j = d_j / sum(d_j).
    """
    criterion_names = list(column_map.keys())
    if len(data) <= 1:
        return pd.Series(
            data=np.full(len(criterion_names), 1.0 / len(criterion_names)),
            index=criterion_names,
            dtype=float,
        )

    criteria_matrix = data[[column_map[name] for name in criterion_names]].apply(pd.to_numeric, errors="coerce")
    criteria_matrix = criteria_matrix.fillna(0.0)

    entropy_values = {}
    for canonical_name in criterion_names:
        column = criteria_matrix[column_map[canonical_name]].to_numpy(dtype=float)
        total = column.sum()
        if total == 0:
            probabilities = np.full(column.shape, 1.0 / len(column), dtype=float)
        else:
            probabilities = column / total
            probabilities = np.where(probabilities <= 0, epsilon, probabilities)

        n = probabilities.size
        if n <= 1:
            entropy_values[canonical_name] = 0.0
            continue

        k = 1.0 / np.log(n)
        entropy = -k * np.sum(probabilities * np.log(probabilities))
        entropy_values[canonical_name] = float(entropy)

    entropy_series = pd.Series(entropy_values, dtype=float)
    divergence_series = 1.0 - entropy_series
    divergence_sum = divergence_series.sum()

    if divergence_sum == 0:
        return pd.Series(
            data=np.full(len(criterion_names), 1.0 / len(criterion_names)),
            index=criterion_names,
            dtype=float,
        )

    return divergence_series / divergence_sum


def build_comparison_table(data: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    """Build a wide comparison table for subjective and entropy-based weights."""
    rows = []

    overall_entropy = entropy_weights(data, column_map)
    per_type_entropy = {
        decision_type: entropy_weights(data[data["decision_type"] == decision_type], column_map)
        for decision_type in DECISION_TYPES
    }

    for criterion in column_map.keys():
        subjective_weight = ENTROPY_SUBJECTIVE_WEIGHTS[criterion]
        overall_weight = float(overall_entropy[criterion])
        hvac_weight = float(per_type_entropy["HVAC"][criterion])
        appliance_weight = float(per_type_entropy["Appliance"][criterion])
        shower_weight = float(per_type_entropy["Shower"][criterion])

        rows.append(
            {
                "criterion": criterion,
                "subjective_weight": subjective_weight,
                "entropy_weight_overall": overall_weight,
                "entropy_weight_hvac": hvac_weight,
                "entropy_weight_appliance": appliance_weight,
                "entropy_weight_shower": shower_weight,
                "abs_diff_overall": abs(subjective_weight - overall_weight),
                "abs_diff_hvac": abs(subjective_weight - hvac_weight),
                "abs_diff_appliance": abs(subjective_weight - appliance_weight),
                "abs_diff_shower": abs(subjective_weight - shower_weight),
            }
        )

    comparison_table = pd.DataFrame(rows).set_index("criterion")
    return comparison_table


def run_entropy(output_dir: Path) -> Path:
    """Run the entropy-weight comparison workflow, writing into output_dir."""
    from tabulate import tabulate

    ground_truth = load_ground_truth_data(get_project_root())
    column_map = resolve_criterion_columns(ground_truth)

    comparison_table = build_comparison_table(ground_truth, column_map)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ENTROPY_OUTPUT_NAME
    comparison_table.reset_index().to_excel(output_path, index=False, engine="openpyxl")

    print("\n" + "=" * 140)
    print("ENTROPY WEIGHTS COMPARISON".center(140))
    print("=" * 140 + "\n")

    display_table = comparison_table.round(6).reset_index()
    headers = [col.replace("_", " ").title() for col in display_table.columns]
    print(tabulate(display_table, headers=headers, tablefmt="grid", floatfmt=".6f", stralign="left", numalign="center"))
    print("\n" + "=" * 140)
    print(f"Results saved to: {output_path}")
    print("=" * 140 + "\n")
    return output_path


# ===========================================================================
# MEREC  (from merec_weights.py)
# ===========================================================================

# Small constant added before log to avoid ln(0).
EPSILON = 0.001


def load_ground_truth() -> pd.DataFrame:
    frames = []
    for dtype, fname in GT_FILES.items():
        df = read_table_clean(find_file_in_paths(fname, SEARCH_DIRS))
        missing = [c for c in SCORE_COLS.values() if c not in df.columns]
        if missing:
            raise ValueError(f"[{dtype}] Missing columns: {missing}")
        df["decision_type"] = dtype
        frames.append(df)
        print(f"  {dtype:10s}: {len(df):>4d} rows")
    combined = pd.concat(frames, ignore_index=True)
    print(f"  {'Total':10s}: {len(combined):>4d} rows\n")
    return combined


def merec_scenario(matrix: np.ndarray) -> np.ndarray:
    """
    Run MEREC on a single (n_alternatives x m_criteria) matrix.
    All criteria are treated as beneficial (higher = better).

    Returns: array of E_j (unnormalized removal effects), shape (m_criteria,)
    """
    n_alt, m_crit = matrix.shape

    # Step 1: Normalize - n_ij = (min_j + eps) / (x_ij + eps)
    col_mins = matrix.min(axis=0) + EPSILON
    norm = col_mins / (matrix + EPSILON)         # shape (n_alt, m_crit)

    # Step 2: log-based performance scores
    abs_log_norm = np.abs(np.log(norm))          # shape (n_alt, m_crit)

    S = np.log(1.0 + (1.0 / m_crit) * abs_log_norm.sum(axis=1))  # shape (n_alt,)

    # Steps 3-4: remove each criterion in turn and measure effect
    E = np.zeros(m_crit)
    for j in range(m_crit):
        mask = np.ones(m_crit, dtype=bool)
        mask[j] = False
        remaining = abs_log_norm[:, mask]        # shape (n_alt, m_crit-1)
        S_minus_j = np.log(1.0 + (1.0 / m_crit) * remaining.sum(axis=1))
        E[j] = np.abs(S_minus_j - S).sum()

    return E


def run_merec_all_scenarios(gt: pd.DataFrame) -> dict:
    """
    Run MEREC per (scenario_id, decision_type), collect per-scenario weights,
    and aggregate by averaging.
    """
    results = {}
    scopes  = [("Overall", gt)] + [
        (dtype, gt[gt["decision_type"] == dtype]) for dtype in ["HVAC", "Appliance", "Shower"]
    ]

    for label, df in scopes:
        if len(df) == 0:
            continue

        per_scenario_weights = []
        zero_variance_counts = {c: 0 for c in CRITERIA}
        skipped = 0

        for (sid, dtype), grp in df.groupby(["scenario_id", "decision_type"]):
            if len(grp) < 2:
                skipped += 1
                continue

            matrix = grp[[SCORE_COLS[c] for c in CRITERIA]].values.astype(float)

            for ci, c in enumerate(CRITERIA):
                if matrix[:, ci].std() < 1e-9:
                    zero_variance_counts[c] += 1

            E = merec_scenario(matrix)
            E_sum = E.sum()

            if E_sum < 1e-12:
                # All criteria perfectly tied across alternatives - skip
                skipped += 1
                continue

            w = E / E_sum
            per_scenario_weights.append(pd.Series(dict(zip(CRITERIA, w))))

        n_scenarios = len(per_scenario_weights)
        if n_scenarios == 0:
            print(f"  WARNING: No valid scenarios for '{label}'")
            continue

        avg_weights = pd.concat(per_scenario_weights, axis=1).mean(axis=1)
        avg_weights = avg_weights / avg_weights.sum()   # renormalize rounding

        results[label] = {
            "weights":              avg_weights,
            "n_scenarios":          n_scenarios,
            "per_scenario_weights": per_scenario_weights,
            "zero_variance_counts": zero_variance_counts,
            "skipped":              skipped,
        }

    return results


def print_merec_result(label: str, res: dict) -> None:
    weights = res["weights"]
    n       = res["n_scenarios"]
    zvc     = res["zero_variance_counts"]

    print(f"\n{'='*65}")
    print(f"  MEREC WEIGHTS — {label}  (n = {n} scenarios)")
    print(f"{'='*65}")

    # Per-scenario weight std dev (stability measure)
    all_w = pd.concat(res["per_scenario_weights"], axis=1)
    w_std = all_w.std(axis=1)

    print(f"\n  {'Criterion':20s} {'MEREC w':>10s} {'±StdDev':>10s} "
          f"{'Subj w':>8s} {'Diff':>8s} {'Zero-var scen':>14s}")
    print(f"  {'-'*70}")

    for c in CRITERIA:
        diff = weights[c] - SUBJECTIVE_WEIGHTS[c]
        sign = "+" if diff >= 0 else ""
        zv_pct = 100.0 * zvc[c] / n if n > 0 else 0
        print(f"  {c:20s} {weights[c]:>10.4f} {w_std[c]:>10.4f} "
              f"{SUBJECTIVE_WEIGHTS[c]:>8.4f} {sign}{diff:>7.4f} "
              f"{zvc[c]:>6d} ({zv_pct:.0f}%)")

    if res["skipped"] > 0:
        print(f"\n  Note: {res['skipped']} scenario(s) skipped "
              f"(fewer than 2 alternatives or zero total effect).")


def run_merec(output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / MEREC_OUTPUT_NAME
    print("\nRunning MEREC objective weight analysis...")
    print("\nLoading ground truth data...")

    gt = load_ground_truth()
    results = run_merec_all_scenarios(gt)

    for label in ["Overall", "HVAC", "Appliance", "Shower"]:
        if label in results:
            print_merec_result(label, results[label])

    print(f"\n{'='*65}")
    print("  INTERPRETATION NOTE — Zero-Variance Scenarios")
    print(f"{'='*65}")
    print(
        "  A 'zero-variance scenario' for a criterion means all three\n"
        "  alternatives in that scenario received identical scores.\n"
        "  MEREC correctly assigns zero removal effect (E_j = 0) to\n"
        "  criteria that do not discriminate between alternatives.\n"
        "  HVAC comfort/practicality are expected to show high zero-\n"
        "  variance counts because those scores are deterministic in\n"
        "  the calculator (occupant-comfort-based fixed score)."
    )

    rows = []
    for label, res in results.items():
        all_w = pd.concat(res["per_scenario_weights"], axis=1)
        w_std = all_w.std(axis=1)
        for c in CRITERIA:
            rows.append({
                "scope":             label,
                "n_scenarios":       res["n_scenarios"],
                "criterion":         c,
                "merec_weight":      round(res["weights"][c], 6),
                "weight_std_dev":    round(w_std[c], 6),
                "subjective_weight": SUBJECTIVE_WEIGHTS[c],
                "diff":              round(res["weights"][c] - SUBJECTIVE_WEIGHTS[c], 6),
                "zero_var_scenarios": res["zero_variance_counts"][c],
            })

    pd.DataFrame(rows).to_excel(output_path, index=False, engine="openpyxl")
    print(f"\n  Saved: {output_path}")
    print("\nDone.\n")
    return output_path


# ===========================================================================
# IMPLIED  (from implied_weights.py)
# ===========================================================================

def load_ground_truth_with_rank() -> pd.DataFrame:
    """implied_weights loader: same as load_ground_truth but also requires rank."""
    frames = []
    for dtype, fname in GT_FILES.items():
        df = read_table_clean(find_file_in_paths(fname, SEARCH_DIRS))
        missing = [c for c in list(SCORE_COLS.values()) + [RANK_COL]
                   if c not in df.columns]
        if missing:
            raise ValueError(f"[{dtype}] Missing columns: {missing}")
        df["decision_type"] = dtype
        frames.append(df)
        print(f"  {dtype:10s}: {len(df):>4d} rows")
    combined = pd.concat(frames, ignore_index=True)
    print(f"  {'Total':10s}: {len(combined):>4d} rows\n")
    return combined


def build_pairwise(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Build pairwise comparison arrays from a ground truth DataFrame.

    For each scenario, enumerate all C(n_alt, 2) pairs.
    For each pair (i, k):
        X_row = score_j(i) - score_j(k)   for each criterion j
        y_row = -(rank_i - rank_k)         (positive when i is better)

    Returns: X (n_pairs x 4), y (n_pairs,)
    """
    X_rows, y_rows = [], []
    skipped = 0

    for (sid, dtype), grp in df.groupby(["scenario_id", "decision_type"]):
        if len(grp) < 2:
            skipped += 1
            continue

        alts = grp.reset_index(drop=True)
        scores = alts[[SCORE_COLS[c] for c in CRITERIA]].values.astype(float)
        ranks  = alts[RANK_COL].values.astype(float)

        for i, k in combinations(range(len(alts)), 2):
            score_diff = scores[i] - scores[k]    # positive when i has higher scores
            rank_diff  = ranks[i] - ranks[k]       # negative when i has better (lower) rank

            # y should be positive when i is preferred (i.e., rank_i < rank_k, rank_diff < 0)
            y = -rank_diff                         # positive when i is preferred

            # Skip ties (should be extremely rare with physics-based GT)
            if abs(y) < 0.5:
                continue

            X_rows.append(score_diff)
            y_rows.append(y)

    if skipped > 0:
        print(f"  Note: {skipped} scenario group(s) skipped (< 2 alternatives).")

    return np.array(X_rows), np.array(y_rows)


def constrained_ols(X: np.ndarray, y: np.ndarray,
                    label: str = "") -> dict:
    """
    Minimize sum (y - X @ w)^2 subject to w >= 0, sum w = 1 (no intercept).

    Uses SLSQP via scipy.optimize.minimize.
    Returns dict with weights, residual stats, and diagnostics.
    """
    from scipy.optimize import minimize

    n_crit = X.shape[1]
    w0 = np.array([1.0 / n_crit] * n_crit)    # equal-weight initialisation

    def objective(w):
        residuals = y - X @ w
        return (residuals ** 2).sum()

    def grad(w):
        residuals = y - X @ w
        return -2.0 * X.T @ residuals

    constraints = {"type": "eq",  "fun": lambda w: w.sum() - 1.0}
    bounds      = [(0.0, 1.0)] * n_crit

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = minimize(
            objective, w0, jac=grad,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-12, "maxiter": 2000},
        )

    if not result.success:
        print(f"  WARNING [{label}]: Optimiser did not converge — {result.message}")

    w_opt = result.x
    w_opt = np.clip(w_opt, 0, 1)
    w_opt /= w_opt.sum()

    # Diagnostic: R^2 analogue on pairwise outcomes
    y_pred    = X @ w_opt
    ss_res    = ((y - y_pred) ** 2).sum()
    ss_tot    = ((y - y.mean()) ** 2).sum()
    r2        = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    # Sign accuracy: how often does the implied ranking agree with GT ranking?
    agree = np.sign(y_pred) == np.sign(y)
    sign_acc = agree.mean()

    return {
        "weights":   pd.Series(dict(zip(CRITERIA, w_opt))),
        "r2":        r2,
        "sign_acc":  sign_acc,
        "n_pairs":   len(y),
        "converged": result.success,
    }


def criterion_variance_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute within-scenario std dev for each criterion.
    A near-zero within-scenario std dev means a criterion does not
    differentiate alternatives -> its implied weight will be near zero
    regardless of its theoretical importance.
    """
    records = []
    for (sid, dtype), grp in df.groupby(["scenario_id", "decision_type"]):
        for c in CRITERIA:
            col = SCORE_COLS[c]
            records.append({
                "decision_type": dtype,
                "criterion": c,
                "within_std": grp[col].std(ddof=0),
            })
    summ = pd.DataFrame(records).groupby(["decision_type", "criterion"])["within_std"].agg(
        mean_within_std="mean",
        pct_zero=lambda x: (x < 1e-9).mean() * 100,
    ).reset_index()
    return summ


def print_implied_result(label: str, res: dict, var_df: pd.DataFrame) -> None:
    weights  = res["weights"]
    r2       = res["r2"]
    sign_acc = res["sign_acc"]
    n_pairs  = res["n_pairs"]

    print(f"\n{'='*65}")
    print(f"  IMPLIED WEIGHTS — {label}  ({n_pairs} pairwise comparisons)")
    print(f"{'='*65}")
    print(f"  Pairwise sign accuracy: {sign_acc:.1%}   "
          f"R² (pairwise): {r2:.4f}   "
          f"Converged: {res['converged']}")

    if label == "Overall":
        scope_var = var_df.groupby("criterion")[["mean_within_std", "pct_zero"]].mean()
    else:
        scope_var = var_df[var_df["decision_type"] == label].set_index("criterion")

    print(f"\n  {'Criterion':20s} {'Implied w':>10s} {'Subj w':>8s} "
          f"{'Diff':>8s} {'Mean within-std':>15s} {'% zero-var':>10s}")
    print(f"  {'-'*72}")

    for c in CRITERIA:
        diff = weights[c] - SUBJECTIVE_WEIGHTS[c]
        sign = "+" if diff >= 0 else ""
        try:
            ws   = scope_var.loc[c, "mean_within_std"]
            pz   = scope_var.loc[c, "pct_zero"]
        except KeyError:
            ws, pz = float("nan"), float("nan")
        print(f"  {c:20s} {weights[c]:>10.4f} {SUBJECTIVE_WEIGHTS[c]:>8.4f} "
              f"{sign}{diff:>7.4f} {ws:>14.4f} {pz:>9.1f}%")


def run_implied(output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / IMPLIED_OUTPUT_NAME
    print("\nIMPLIED WEIGHT ANALYSIS — PAIRWISE RANKING REGRESSION")
    print("=" * 65)
    print("References:")
    print("  Jacquet-Lagrèze & Siskos (1982). EJOR, 10(2), 151–164.")
    print("  Dyer & Sarin (1979). Operations Research, 27(4), 810–822.")
    print("=" * 65)
    print("\nLoading ground truth data...")

    gt = load_ground_truth_with_rank()

    print("Computing within-scenario criterion variance...")
    var_df = criterion_variance_summary(gt)

    print("\nWithin-scenario std dev by decision type:")
    print(f"  {'Decision Type':12s} {'Criterion':20s} "
          f"{'Mean within-std':>15s} {'% zero-var scen':>16s}")
    print(f"  {'-'*64}")
    for _, row in var_df.iterrows():
        print(f"  {row['decision_type']:12s} {row['criterion']:20s} "
              f"{row['mean_within_std']:>14.4f} {row['pct_zero']:>15.1f}%")

    results = {}
    scopes  = [("Overall", gt)] + [
        (dtype, gt[gt["decision_type"] == dtype]) for dtype in ["HVAC", "Appliance", "Shower"]
    ]

    for label, df in scopes:
        if len(df) == 0:
            continue
        print(f"\nBuilding pairwise dataset for: {label}...")
        X, y = build_pairwise(df)
        print(f"  {len(y)} pairwise comparisons from "
              f"{df['scenario_id'].nunique()} scenarios.")
        print(f"  Running constrained OLS (w ≥ 0, Σw = 1, no intercept)...")
        res = constrained_ols(X, y, label=label)
        results[label] = res
        print_implied_result(label, res, var_df)

    print(f"\n{'='*65}")
    print("  INTERPRETATION NOTE")
    print(f"{'='*65}")
    print(
        "  Implied weights reflect which criteria actually differentiate\n"
        "  alternatives in the ground truth data, not which criteria are\n"
        "  theoretically important. A criterion with near-zero implied\n"
        "  weight means it does not discriminate between alternatives in\n"
        "  practice — its subjective weight has no effect on rankings.\n"
        "  HVAC comfort and practicality are expected to show near-zero\n"
        "  implied weights because those scores are deterministic and\n"
        "  identical across alternatives in the HVAC calculator.\n"
        "  Appliance and Shower should show implied weights closer to\n"
        "  the subjective weights since all four criteria vary."
    )

    rows = []
    for label, res in results.items():
        for c in CRITERIA:
            rows.append({
                "scope":             label,
                "n_pairs":           res["n_pairs"],
                "criterion":         c,
                "implied_weight":    round(res["weights"][c], 6),
                "subjective_weight": SUBJECTIVE_WEIGHTS[c],
                "diff":              round(res["weights"][c] - SUBJECTIVE_WEIGHTS[c], 6),
                "pairwise_sign_acc": round(res["sign_acc"], 4),
                "r2_pairwise":       round(res["r2"], 4),
            })

    pd.DataFrame(rows).to_excel(output_path, index=False, engine="openpyxl")
    print(f"\n  Saved: {output_path}")
    print("\nDone.\n")
    return output_path


# ===========================================================================
# DIAGNOSTICS  (from scripts/validation/WeightDiagnostics.py)
# ===========================================================================

from common.model_config import CRITERIA as DIAG_CRITERIA  # noqa: E402
from common.model_config import CRITERION_WEIGHTS  # noqa: E402

GT_DIR = PROJECT_ROOT / "workbooks/ground_truth"
TEST_SCENARIOS = PROJECT_ROOT / "workbooks/scenarios" / "TestScenarios.xlsx"

DIAG_DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
DIAG_SCORE_COLS = {c: f"{c}_score" for c in DIAG_CRITERIA}

# A criterion counts as non-discriminating in a scenario when its spread
# across the three alternatives is below this. The GT scores are rounded to
# two decimals, so anything under half a rounding step is an exact tie.
TIE_TOL = 0.005


def load_gt(scope):
    """Load the ground-truth workbooks, optionally restricted to the Test
    scenarios that the benchmark actually evaluates."""
    frames = []
    for dtype in DIAG_DECISION_TYPES:
        df = read_table_clean(GT_DIR / f"ground_truth_{dtype.lower()}.xlsx")
        df["decision_type"] = dtype
        frames.append(df)
    gt = pd.concat(frames, ignore_index=True)

    for c in DIAG_CRITERIA:
        gt[c] = pd.to_numeric(gt[DIAG_SCORE_COLS[c]], errors="coerce")

    if scope == "test":
        test = read_table_clean(
            TEST_SCENARIOS,
            keep_str_cols=["alternative_1", "alternative_2", "alternative_3"],
        )
        keys = set(
            test["question"].str.strip() + "||" + test["location"].str.strip()
        )
        mask = (gt["question"].str.strip() + "||" + gt["location"].str.strip()).isin(keys)
        gt = gt[mask].copy()

    gt["_sid"] = gt["decision_type"] + "#" + gt["scenario_id"].astype(str)
    return gt


def diagnostics_for(sub):
    """Per-criterion discrimination, range, and realized swing for one slice."""
    rows = []
    ranges = {}
    for c in DIAG_CRITERIA:
        spread = sub.groupby("_sid")[c].agg(lambda s: s.max() - s.min())
        spread = spread.dropna()
        if spread.empty:
            continue
        zero_var = float((spread <= TIE_TOL).mean())
        mean_range = float(spread.mean())
        ranges[c] = mean_range
        rows.append({
            "criterion": c,
            "nominal_weight": CRITERION_WEIGHTS[c],
            "n_scenarios": int(spread.size),
            "pct_no_discrimination": round(100 * zero_var, 1),
            "mean_within_scenario_range": round(mean_range, 4),
            "max_within_scenario_range": round(float(spread.max()), 4),
            "realized_swing": round(CRITERION_WEIGHTS[c] * mean_range, 4),
        })

    total = sum(CRITERION_WEIGHTS[r["criterion"]] * ranges[r["criterion"]] for r in rows)
    for r in rows:
        r["realized_swing_share"] = (
            round(r["realized_swing"] / total, 4) if total > 0 else np.nan
        )
        r["nominal_minus_realized"] = round(r["nominal_weight"] - r["realized_swing_share"], 4)
    return rows


def collinearity_for(sub):
    """Within-scenario Spearman rho between the cost and environmental value
    scores, plus the rate at which the two are numerically identical."""
    import scipy.stats as stats

    rhos = []
    identical = 0
    n = 0
    for _, g in sub.groupby("_sid"):
        a = g["energy_cost"].values
        b = g["environmental"].values
        if len(a) < 2 or np.isnan(a).any() or np.isnan(b).any():
            continue
        n += 1
        if np.allclose(a, b, atol=TIE_TOL):
            identical += 1
        if len(set(a)) < 2 or len(set(b)) < 2:
            rhos.append(1.0 if np.allclose(a, b, atol=TIE_TOL) else np.nan)
            continue
        rho, _ = stats.spearmanr(a, b)
        rhos.append(rho)
    valid = [r for r in rhos if not np.isnan(r)]
    return {
        "n_scenarios": n,
        "mean_spearman_cost_env": round(float(np.mean(valid)), 4) if valid else np.nan,
        "pct_rho_equals_1": round(100 * float(np.mean([r >= 0.999 for r in valid])), 1) if valid else np.nan,
        "pct_scores_identical": round(100 * identical / n, 1) if n else np.nan,
        "combined_cost_env_weight": round(
            CRITERION_WEIGHTS["energy_cost"] + CRITERION_WEIGHTS["environmental"], 3
        ),
    }


def run_diagnostics(xlsx_out_dir: Path, csv_out_dir: Path | None = None, scope: str = "full"):
    """Run the weight-discrimination / collinearity diagnostics.

    Destinations are validated with the repository output guards; raises
    UnsafeOutputPathError for an unsafe destination.
    """
    if csv_out_dir is None:
        csv_out_dir = xlsx_out_dir
    suffix = "" if scope == "full" else "_test"
    xlsx_out_dir = require_safe_output_directory(
        xlsx_out_dir, option="workbooks/methodology output", root=PROJECT_ROOT
    )
    csv_out_dir = require_safe_output_directory(
        csv_out_dir, option="results/methodology output", root=PROJECT_ROOT
    )
    d_path = require_safe_output_path(
        xlsx_out_dir / f"weight_discrimination{suffix}.xlsx",
        option="weight_discrimination XLSX output", root=PROJECT_ROOT
    )
    c_path = require_safe_output_path(
        xlsx_out_dir / f"cost_env_collinearity{suffix}.xlsx",
        option="cost_env_collinearity XLSX output", root=PROJECT_ROOT
    )
    d_csv_path = require_safe_output_path(
        csv_out_dir / f"weight_discrimination{suffix}.csv",
        option="weight_discrimination CSV output", root=PROJECT_ROOT
    )
    c_csv_path = require_safe_output_path(
        csv_out_dir / f"cost_env_collinearity{suffix}.csv",
        option="cost_env_collinearity CSV output", root=PROJECT_ROOT
    )

    gt = load_gt(scope)
    print(f"Scope: {scope} | {gt['_sid'].nunique()} scenarios, {len(gt)} rows")

    diag_rows = []
    for scope_label, sub in [("Overall", gt)] + [
        (dt, gt[gt["decision_type"] == dt]) for dt in DIAG_DECISION_TYPES
    ]:
        if sub.empty:
            continue
        for r in diagnostics_for(sub):
            r["scope"] = scope_label
            r["corpus"] = scope
            diag_rows.append(r)

    col_rows = []
    for scope_label, sub in [("Overall", gt)] + [
        (dt, gt[gt["decision_type"] == dt]) for dt in DIAG_DECISION_TYPES
    ]:
        if sub.empty:
            continue
        r = collinearity_for(sub)
        r["scope"] = scope_label
        r["corpus"] = scope
        col_rows.append(r)

    diag = pd.DataFrame(diag_rows)[
        ["corpus", "scope", "criterion", "nominal_weight", "n_scenarios",
         "pct_no_discrimination", "mean_within_scenario_range",
         "max_within_scenario_range", "realized_swing", "realized_swing_share",
         "nominal_minus_realized"]
    ]
    coll = pd.DataFrame(col_rows)[
        ["corpus", "scope", "n_scenarios", "mean_spearman_cost_env",
         "pct_rho_equals_1", "pct_scores_identical", "combined_cost_env_weight"]
    ]

    xlsx_out_dir.mkdir(parents=True, exist_ok=True)
    csv_out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_xlsx(diag, d_path)
    _atomic_write_xlsx(coll, c_path)
    diag.to_csv(d_csv_path, index=False)
    coll.to_csv(c_csv_path, index=False)

    print("\nDISCRIMINATION AND REALIZED SWING")
    print("=" * 100)
    for scope_label in ["Overall"] + DIAG_DECISION_TYPES:
        s = diag[diag["scope"] == scope_label]
        if s.empty:
            continue
        print(f"\n{scope_label}")
        print(f"  {'criterion':<16}{'nominal':>9}{'no-discrim%':>13}"
              f"{'mean range':>12}{'realized':>10}{'share':>8}{'gap':>8}")
        for _, r in s.iterrows():
            print(f"  {r['criterion']:<16}{r['nominal_weight']:>9.3f}"
                  f"{r['pct_no_discrimination']:>13.1f}"
                  f"{r['mean_within_scenario_range']:>12.4f}"
                  f"{r['realized_swing']:>10.4f}"
                  f"{r['realized_swing_share']:>8.3f}"
                  f"{r['nominal_minus_realized']:>+8.3f}")

    print("\n\nCOST / ENVIRONMENTAL COLLINEARITY")
    print("=" * 100)
    print(f"  {'scope':<12}{'n':>6}{'mean rho':>11}{'rho=1 %':>10}"
          f"{'identical %':>14}{'combined w':>12}")
    for _, r in coll.iterrows():
        print(f"  {r['scope']:<12}{r['n_scenarios']:>6}"
              f"{r['mean_spearman_cost_env']:>11.4f}{r['pct_rho_equals_1']:>10.1f}"
              f"{r['pct_scores_identical']:>14.1f}{r['combined_cost_env_weight']:>12.3f}")

    print(f"\n[OK] Wrote {d_path}, {c_path}, {d_csv_path}, and {c_csv_path}")
    return d_path, c_path, d_csv_path, c_csv_path


# ===========================================================================
# Unified CLI
# ===========================================================================

METHODS = ("merec", "entropy", "implied", "diagnostics")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Objective-weight validation suite (VALIDATION ONLY).")
    parser.add_argument("--method", choices=[*METHODS, "all"], required=True,
                        help="Which analysis to run ('all' runs every method).")
    parser.add_argument("--output-dir", required=True,
                        help="Explicit output directory (must not be a frozen path).")
    parser.add_argument("--scope", choices=["full", "test"], default="full",
                        help="Diagnostics only. full = 285-scenario corpus the value "
                             "functions are calibrated on (default); test = 195 "
                             "evaluated scenarios.")
    args = parser.parse_args(argv)

    try:
        out_dir = require_safe_output_directory(
            args.output_dir, option="--output-dir", root=PROJECT_ROOT)
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))

    selected = METHODS if args.method == "all" else (args.method,)
    for method in selected:
        if method == "merec":
            run_merec(out_dir)
        elif method == "entropy":
            run_entropy(out_dir)
        elif method == "implied":
            run_implied(out_dir)
        else:
            try:
                run_diagnostics(out_dir, out_dir, args.scope)
            except UnsafeOutputPathError as exc:
                parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
