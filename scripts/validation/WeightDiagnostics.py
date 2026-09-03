#!/usr/bin/env python3
"""
WeightDiagnostics.py

Measures what the criterion weights actually do inside the choice sets the
benchmark evaluates, as opposed to what they are nominally set to.

The three objective weight scripts (EntropyWeights, merec_weights,
implied_weights) each return a weight vector, and comparing four vectors
column by column produces a table that is consistent and uninformative. The
quantities below are the ones that carry a finding:

  discrimination      Fraction of scenarios where a criterion takes the same
                      value for all three alternatives. A criterion that never
                      varies within a choice set cannot affect the ranking no
                      matter what weight it carries.

  within-scenario     Mean (max - min) of a criterion across the alternatives
  range               of one scenario. This is the swing the weight actually
                      multiplies.

  realized swing      weight x mean within-scenario range. The contribution a
                      criterion can make to separating alternatives. Reported
                      as a share so it is directly comparable to the nominal
                      weight vector.

  cost/env            Within-scenario Spearman rho between the energy_cost and
  collinearity        environmental value scores. Where this is 1.0 the two
                      criteria are one criterion carrying their combined
                      weight.

Everything here reads the ground-truth workbooks. No API calls.

Usage:
    python "Miscellaneous Scripts/WeightDiagnostics.py"
    python "Miscellaneous Scripts/WeightDiagnostics.py" --scope test
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import CRITERIA, CRITERION_WEIGHTS
from sentinel_utils import _atomic_write_xlsx, read_table_clean

GT_DIR = PROJECT_ROOT / "Ground Truth"
OUT_DIR = PROJECT_ROOT / "Scoring Logic and Documentation" / "method"
TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"

DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
SCORE_COLS = {c: f"{c}_score" for c in CRITERIA}

# A criterion counts as non-discriminating in a scenario when its spread
# across the three alternatives is below this. The GT scores are rounded to
# two decimals, so anything under half a rounding step is an exact tie.
TIE_TOL = 0.005


def load_gt(scope):
    """Load the ground-truth workbooks, optionally restricted to the Test
    scenarios that the benchmark actually evaluates."""
    frames = []
    for dtype in DECISION_TYPES:
        df = read_table_clean(GT_DIR / f"ground_truth_{dtype.lower()}.xlsx")
        df["decision_type"] = dtype
        frames.append(df)
    gt = pd.concat(frames, ignore_index=True)

    for c in CRITERIA:
        gt[c] = pd.to_numeric(gt[SCORE_COLS[c]], errors="coerce")

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
    for c in CRITERIA:
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


def main():
    parser = argparse.ArgumentParser(description="Weight discrimination diagnostics")
    parser.add_argument("--scope", choices=["full", "test"], default="full",
                        help="full = 285-scenario corpus the value functions are "
                             "calibrated on (default); test = 195 evaluated scenarios")
    args = parser.parse_args()

    gt = load_gt(args.scope)
    print(f"Scope: {args.scope} | {gt['_sid'].nunique()} scenarios, {len(gt)} rows")

    diag_rows = []
    for scope_label, sub in [("Overall", gt)] + [
        (dt, gt[gt["decision_type"] == dt]) for dt in DECISION_TYPES
    ]:
        if sub.empty:
            continue
        for r in diagnostics_for(sub):
            r["scope"] = scope_label
            r["corpus"] = args.scope
            diag_rows.append(r)

    col_rows = []
    for scope_label, sub in [("Overall", gt)] + [
        (dt, gt[gt["decision_type"] == dt]) for dt in DECISION_TYPES
    ]:
        if sub.empty:
            continue
        r = collinearity_for(sub)
        r["scope"] = scope_label
        r["corpus"] = args.scope
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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.scope == "full" else "_test"
    d_path = OUT_DIR / f"weight_discrimination{suffix}.xlsx"
    c_path = OUT_DIR / f"cost_env_collinearity{suffix}.xlsx"
    _atomic_write_xlsx(diag, d_path)
    _atomic_write_xlsx(coll, c_path)
    diag.to_csv(d_path.with_suffix(".csv"), index=False)
    coll.to_csv(c_path.with_suffix(".csv"), index=False)

    print("\nDISCRIMINATION AND REALIZED SWING")
    print("=" * 100)
    for scope_label in ["Overall"] + DECISION_TYPES:
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

    print(f"\n[OK] Wrote {d_path.name}, {c_path.name} (+ .csv)")


if __name__ == "__main__":
    main()
