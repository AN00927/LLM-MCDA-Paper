"""
MerecWeights.py
---------------
Computes objective criteria weights using the MEREC method
(MEthod based on the Removal Effects of Criteria), applied
PER-SCENARIO then averaged across all 100 scenarios.

Reference:
    Keshavarz-Ghorabaee, M., Amiri, M., Zavadskas, E.K., Turskis, Z.,
    & Antucheviciene, J. (2021).
    "Determination of objective weights using a new method based on
    the removal effects of criteria (MEREC)."
    Symmetry, 13(4), 525. https://doi.org/10.3390/sym13040525

Why per-scenario rather than pooled:
    MEREC is designed for a single decision matrix where rows are
    alternatives in the SAME decision problem. Pooling 300 alternatives
    across 100 unrelated scenarios violates this structure. Running MEREC
    on each 3-alternative decision matrix and averaging preserves the
    correct unit of analysis (Keshavarz-Ghorabaee et al., 2021).

Why MEREC over CRITIC here:
    CRITIC relies on Pearson correlation, which only captures linear
    relationships. Because comfort and practicality use logarithmic value
    functions (α=1.5 and α=1.2 respectively), the true criterion
    relationships in this dataset are nonlinear. MEREC bypasses
    correlation entirely: it assigns weight based on how much a criterion's
    removal changes the ranking of alternatives, making it robust to
    nonlinearity (Keshavarz-Ghorabaee et al., 2021).

MEREC formula (all criteria are beneficial, higher score = better):
    Step 1: Normalize  n_ij = (min_j + ε) / (x_ij + ε)
    Step 2: Overall performance  S_i = ln(1 + (1/m) * Σ_j |ln(n_ij)|)
    Step 3: Performance without j  S_i^(-j) = ln(1 + (1/m) * Σ_{k≠j} |ln(n_ik)|)
    Step 4: Removal effect  E_j = Σ_i |S_i^(-j) - S_i|
    Step 5: Weight  w_j = E_j / Σ_k E_k

Inputs:  ground_truth_hvac.xlsx, ground_truth_appliance.xlsx, ground_truth_shower.xlsx
Outputs: merec_weights_summary.xlsx
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import find_file_in_paths, read_table_clean

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

CRITERIA = list(SCORE_COLS.keys())
N_CRITERIA = len(CRITERIA)

SUBJECTIVE_WEIGHTS = {
    "energy_cost":   0.30,
    "environmental": 0.35,
    "comfort":       0.20,
    "practicality":  0.15,
}

OUTPUT_CSV  = "merec_weights_summary.xlsx"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

# Small constant added before log to avoid ln(0).
# Scores are on [0, 1]; epsilon = 0.01 has negligible effect on scores > 0.01
# but prevents undefined log for zero-score alternatives.
EPSILON = 0.001


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MEREC Core
# ---------------------------------------------------------------------------

def merec_scenario(matrix: np.ndarray) -> np.ndarray:
    """
    Run MEREC on a single (n_alternatives × m_criteria) matrix.
    All criteria are treated as beneficial (higher = better).

    Returns: array of E_j (unnormalized removal effects), shape (m_criteria,)
    """
    n_alt, m_crit = matrix.shape

    # Step 1: Normalize — n_ij = (min_j + ε) / (x_ij + ε)
    # Best alternative gets smallest n_ij; worst gets n_ij = 1.
    col_mins = matrix.min(axis=0) + EPSILON
    norm = col_mins / (matrix + EPSILON)         # shape (n_alt, m_crit)

    # Step 2: log-based performance scores
    abs_log_norm = np.abs(np.log(norm))          # shape (n_alt, m_crit)

    S = np.log(1.0 + (1.0 / m_crit) * abs_log_norm.sum(axis=1))  # shape (n_alt,)

    # Steps 3–4: remove each criterion in turn and measure effect
    E = np.zeros(m_crit)
    for j in range(m_crit):
        mask = np.ones(m_crit, dtype=bool)
        mask[j] = False
        remaining = abs_log_norm[:, mask]        # shape (n_alt, m_crit-1)
        # Canonical MEREC (Keshavarz-Ghorabaee et al. 2021, Eq. 5) keeps the SAME
        # 1/m normalization as the overall score S_i (Eq. 3); the removal effect
        # comes from dropping the j-th term, not from rescaling by (m-1).
        S_minus_j = np.log(1.0 + (1.0 / m_crit) * remaining.sum(axis=1))
        E[j] = np.abs(S_minus_j - S).sum()

    return E


def run_merec_all_scenarios(gt: pd.DataFrame) -> dict:
    """
    Run MEREC per (scenario_id, decision_type), collect per-scenario weights,
    and aggregate by averaging.

    Returns dict: scope → {'weights': pd.Series, 'n_scenarios': int,
                            'per_scenario_weights': list of pd.Series,
                            'zero_variance_count': dict}
    """
    # Determine scenario grouping column — scenario_id exists in all GT files
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

            # Check for zero-variance criteria within this scenario
            for ci, c in enumerate(CRITERIA):
                if matrix[:, ci].std() < 1e-9:
                    zero_variance_counts[c] += 1

            E = merec_scenario(matrix)
            E_sum = E.sum()

            if E_sum < 1e-12:
                # All criteria perfectly tied across alternatives — skip
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


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\nMEREC PER-SCENARIO OBJECTIVE WEIGHT ANALYSIS")
    print("=" * 65)
    print("Reference: Keshavarz-Ghorabaee et al. (2021)")
    print("           Symmetry, 13(4), 525.")
    print("           https://doi.org/10.3390/sym13040525")
    print("=" * 65)
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

    pd.DataFrame(rows).to_excel(OUTPUT_CSV, index=False, engine="openpyxl")
    print(f"\n  Saved: {OUTPUT_CSV}")
    print("\nDone.\n")


if __name__ == "__main__":
    main()