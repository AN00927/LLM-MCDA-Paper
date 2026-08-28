"""
implied_weights.py
-----------------
Recovers "implied weights" from the ground truth ranking structure using
pairwise constrained linear regression.

Motivation:
    MEREC and Entropy measure how much each criterion *varies* across
    alternatives. This script asks a different question: which weighting
    of criteria best reproduces the observed preference rankings? The
    answer — "implied weights" — can diverge from subjective weights
    when some criteria have near-zero within-scenario variance (i.e.,
    they do not discriminate between alternatives in practice).

Method — Pairwise Ranking Regression:
    For each scenario with 3 alternatives, form all 3 pairwise comparisons
    (i, k). For each pair:
        y_ik    = rank_i − rank_k          (rank 1 = best)
        x_ik_j  = score_j(i) − score_j(k)
    Since a higher criterion score produces a lower (better) rank:
        y_ik ≈ −Σ_j  w_j * x_ik_j
    Rearranging: −y_ik ≈ Σ_j  w_j * x_ik_j

    Find w that minimizes Σ(−y_ik − Σ_j w_j * x_ik_j)² subject to:
        w_j ≥ 0  for all j
        Σ_j w_j = 1

    This formulation avoids pooling across unrelated scenarios because
    within-scenario means cancel in the pairwise differences. It also
    avoids circularity: the outcome is the RANK (an ordinal ordering),
    not the mavt_score (which is by construction a linear function of
    criterion scores). Criteria with zero within-scenario variance
    (x_ik_j = 0 for all pairs) contribute nothing to the regression
    signal and receive near-zero implied weights — a genuine finding
    rather than an artefact.

Methodological grounding:
    Pairwise comparison aggregation is a well-established technique in
    preference learning and MCDA weight elicitation (Jacquet-Lagrèze &
    Siskos, 1982; Dyer & Sarin, 1979). The constrained least-squares
    formulation follows standard MAVT weight recovery approaches.

    References:
    - Jacquet-Lagreze & Siskos (1982). EJOR 10(2):151-164.
    - Dyer & Sarin (1979). Oper. Res. 27(4):810-822.

Inputs:  ground_truth_hvac.xlsx, ground_truth_appliance.xlsx, ground_truth_shower.xlsx
Outputs: implied_weights_summary.xlsx
"""

import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from itertools import combinations
from scipy.optimize import minimize

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import find_file_in_paths, read_table_clean

# Console output contains math symbols (σ, ≥, Σ, −); ensure stdout can encode them
# on Windows where the default codec (cp1252) cannot.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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
RANK_COL = "rank"

CRITERIA = list(SCORE_COLS.keys())

SUBJECTIVE_WEIGHTS = {
    "energy_cost":   0.30,
    "environmental": 0.35,
    "comfort":       0.20,
    "practicality":  0.15,
}

OUTPUT_CSV  = "implied_weights_summary.xlsx"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Prefer repository-level Ground Truth and deterministic script-relative locations
SEARCH_DIRS = [
    os.path.join(BASE_DIR, "..", "Ground Truth"),
    os.path.join(BASE_DIR, ".."),
    os.path.join(BASE_DIR, "Ground Truth"),
    BASE_DIR,
    os.path.join(os.getcwd(), "Ground Truth"),
    os.getcwd(),
]

# Default output inside Scoring Logic and Documentation/method
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "Scoring Logic and Documentation", "method")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, OUTPUT_CSV)


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


def load_ground_truth() -> pd.DataFrame:
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


# ---------------------------------------------------------------------------
# Pairwise Dataset Builder
# ---------------------------------------------------------------------------

def build_pairwise(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Build pairwise comparison arrays from a ground truth DataFrame.

    For each scenario, enumerate all C(n_alt, 2) pairs.
    For each pair (i, k):
        X_row = score_j(i) - score_j(k)   for each criterion j
        y_row = -(rank_i - rank_k)         (positive when i is better)

    The regression target is y = Σ w_j * X_j, i.e., a positive y means
    alternative i is preferred and has higher criterion scores on average.

    Returns: X (n_pairs × 4), y (n_pairs,)
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

            # We want: y = Σ w_j * score_diff_j
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


# ---------------------------------------------------------------------------
# Constrained Regression
# ---------------------------------------------------------------------------

def constrained_ols(X: np.ndarray, y: np.ndarray,
                    label: str = "") -> dict:
    """
    Minimize Σ(y - X @ w)² subject to w ≥ 0, Σw = 1 (no intercept).

    Uses SLSQP via scipy.optimize.minimize.
    Returns dict with weights, residual stats, and diagnostics.
    """
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

    # Diagnostic: R² analogue on pairwise outcomes
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


# ---------------------------------------------------------------------------
# Per-Criterion Variance Summary
# ---------------------------------------------------------------------------

def criterion_variance_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute within-scenario std dev for each criterion.
    A near-zero within-scenario std dev means a criterion does not
    differentiate alternatives → its implied weight will be near zero
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


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\nIMPLIED WEIGHT ANALYSIS — PAIRWISE RANKING REGRESSION")
    print("=" * 65)
    print("References:")
    print("  Jacquet-Lagrèze & Siskos (1982). EJOR, 10(2), 151–164.")
    print("  Dyer & Sarin (1979). Operations Research, 27(4), 810–822.")
    print("=" * 65)
    print("\nLoading ground truth data...")

    gt = load_ground_truth()

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

    # Save
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

    pd.DataFrame(rows).to_excel(OUTPUT_CSV, index=False, engine="openpyxl")
    print(f"\n  Saved: {OUTPUT_CSV}")
    print("\nDone.\n")


if __name__ == "__main__":
    main()
