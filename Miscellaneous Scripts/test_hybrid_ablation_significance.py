"""Significance tests for the hybrid (parameter-provenance) ablation.

Tests whether the two parameter-provenance arms differ by more than noise:
    extracted        LLM-extracted hidden parameters
    default_params   corpus-median parameters, no inference

That single contrast is the paper's claim: it isolates what the extraction step
contributes over a no-inference baseline. Both arms are scored against the
ranking the reference calculator produces from the scenario's true engineering
values. That reference is the scoring target, not an arm. It was previously
reported as a third `true_params` arm, which was dropped: it reproduces the
reference by construction (tau = 1.0, MAE = 0 for every scenario), so every
statistic involving it was a tautology rather than evidence about the method.

As in test_prompt_ablation_significance.py, no statistic is implemented here. The
Wilcoxon-Holm / Cliff's delta / bootstrap functions come from
run_rag_ablation_experiments.py, so all three ablations in the paper are tested by the
same reviewed code.

Only the two provenance arms above are tested here. `hybrid_ablation_summary.xlsx`
also carries the alternative-ordering arms (`extracted_per_run`, `order_control`,
`order_reversed`), which are a different experiment with its own analysis in
`hybrid_order_reversal.xlsx`. They are excluded because they carry several runs
per scenario, which the pivot inside `posthoc_wilcoxon_holm` would collapse with
`aggfunc='first'` -- keeping run 1 and discarding the rest without saying so.

Tests run within each model. Pooling models would confound provenance effects
with model effects.

Significance-testing methodology (one correction layer):
  With two arms there is exactly one comparison per (model, metric) cell, so a
  Friedman omnibus does not apply -- it needs three or more related samples --
  and there is no within-cell pairwise family to correct. Each cell is therefore
  tested directly with a paired Wilcoxon signed-rank test on the 195 scenarios,
  via `posthoc_wilcoxon_holm` restricted to the two arms (its own Holm step is a
  no-op over a family of one, so the RAW p_value is taken from it).

  The family is (number of models) x (number of metrics) and grows whenever a
  model is added. With the four models currently collected that is 4 x 3 = 12
  tests. The script prints the realised count at run time -- read that, not this
  comment, when reporting the family size. Holm-Bonferroni correction is applied
  ACROSS that whole family, for the same reason and using the same method as
  run_rag_ablation_experiments.py and test_prompt_ablation_significance.py:
  reporting twelve tests side by side at nominal alpha=0.05 with no correction
  inflates the family-wise false-positive rate across the study. Adding a model
  therefore makes every existing cell's corrected p-value more conservative;
  that is the correction working, not a regression.

  Cliff's delta is descriptive and is not corrected. Bootstrap CIs are computed
  for every model x arm x metric; they describe an arm's own sampling
  uncertainty rather than a pairwise comparison.

Outputs (Analysis/Hybrid_Ablation/):
    hybrid_ablation_pairwise_tests.xlsx
    hybrid_ablation_bootstrap_ci.xlsx
    hybrid_ablation_significance.xlsx     pairwise / descriptives

Run:
    python "Miscellaneous Scripts/test_hybrid_ablation_significance.py"
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUT_DIR = PROJECT_ROOT / "Analysis" / "Hybrid_Ablation"
SUMMARY_XLSX = OUT_DIR / "hybrid_ablation_summary.xlsx"

METRIC_COLS = ["kendall_tau", "top1", "mae"]

# The parameter-provenance arms, and only those. See the module docstring: the
# summary workbook also carries the alternative-ordering arms, which belong to a
# separate experiment and have several rows per scenario.
PROVENANCE_ARMS = ["extracted", "default_params"]


def _load_rag_module():
    path = Path(__file__).resolve().parent / "run_rag_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("run_rag_ablations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if not SUMMARY_XLSX.exists():
        raise SystemExit(f"Missing {SUMMARY_XLSX}. Run run_hybrid_ablation_experiments.py first.")

    rag = _load_rag_module()
    df = pd.read_excel(SUMMARY_XLSX, sheet_name="per_scenario")
    df = df[~df["failed"].astype(bool)].copy()

    missing = [a for a in PROVENANCE_ARMS if a not in set(df["arm"])]
    if missing:
        raise SystemExit(f"Missing provenance arm(s) in {SUMMARY_XLSX}: {missing}")
    dropped = sorted(set(df["arm"]) - set(PROVENANCE_ARMS))
    df = df[df["arm"].isin(PROVENANCE_ARMS)].copy()
    if dropped:
        print(f"Arms excluded (separate experiment, see hybrid_order_reversal.xlsx): "
              f"{', '.join(dropped)}")

    pairwise_rows = []
    boot_rows = []

    for model, stratum in df.groupby("model"):
        if stratum["arm"].nunique() < len(PROVENANCE_ARMS):
            continue

        # One paired Wilcoxon signed-rank test per (model, metric). With only
        # the two provenance arms present, posthoc_wilcoxon_holm returns exactly
        # one row and its internal Holm step is a no-op over a family of one, so
        # its p_holm/significant_holm columns are dropped here: the correction
        # that matters is applied across the whole (model x metric) family below.
        for metric in METRIC_COLS:
            ph = rag.posthoc_wilcoxon_holm(
                stratum, metric, config_col="arm", scenario_col="scenario_id")
            ph = ph.drop(columns=[c for c in ["p_holm", "significant_holm"]
                                  if c in ph.columns])
            for _, r in ph.iterrows():
                pairwise_rows.append({"model": model, "metric": metric, **r.to_dict()})

        # Bootstrap CIs describe each arm's own sampling uncertainty, not a
        # pairwise comparison, so they are computed for every model x metric
        # (matching run_rag_ablation_experiments.py and test_prompt_ablation_significance.py).
        for metric in METRIC_COLS:
            bc = rag.bootstrap_ci_per_config(stratum, metric, config_col="arm",
                                             stratum_key=model)
            for _, r in bc.iterrows():
                boot_rows.append({"model": model, **r.to_dict()})

    pairwise = pd.DataFrame(pairwise_rows)

    # Cross-stratum family correction: (number of models) x len(METRIC_COLS)
    # independent Wilcoxon tests are run above, one per (model, metric) pair --
    # 12 with the four models currently collected. Holm-Bonferroni correction is
    # applied ACROSS this whole family, for the same reason and using the same
    # method as run_rag_ablation_experiments.py and
    # test_prompt_ablation_significance.py: reporting several tests side by side
    # at nominal alpha=0.05 with no correction inflates the family-wise
    # false-positive rate across the study.
    if not pairwise.empty:
        p_holm, significant_holm = rag.holm_correct(pairwise["p_value"].values)
        pairwise["p_holm"] = p_holm
        pairwise["significant_holm"] = significant_holm
    else:
        pairwise["p_holm"] = pd.Series(dtype=float)
        pairwise["significant_holm"] = pd.Series(dtype=bool)

    bootstrap = pd.DataFrame(boot_rows)
    if len(bootstrap):
        bootstrap = bootstrap.rename(columns={"ablation_id": "arm"}).drop(
            columns=[c for c in ["ablation_label"] if c in bootstrap.columns])

    descriptives = df.groupby(["model", "arm"])[METRIC_COLS].agg(["mean", "std"])
    descriptives.columns = ["_".join(c).strip("_") for c in descriptives.columns.to_flat_index()]
    descriptives = descriptives.reset_index()

    with pd.ExcelWriter(OUT_DIR / "hybrid_ablation_significance.xlsx") as xl:
        pairwise.to_excel(xl, sheet_name="pairwise", index=False)
        descriptives.to_excel(xl, sheet_name="descriptives", index=False)

    pairwise.to_excel(OUT_DIR / "hybrid_ablation_pairwise_tests.xlsx", index=False)
    bootstrap.to_excel(OUT_DIR / "hybrid_ablation_bootstrap_ci.xlsx", index=False)

    print(f"Models tested: {df['model'].nunique()}  |  scenario rows: {len(df)}")
    print()
    n_tests = int(pairwise["p_value"].notna().sum()) if len(pairwise) else 0
    print(f"=== extracted vs default_params: paired Wilcoxon signed-rank ===")
    print(f"(one test per model x metric, Holm-corrected across all {n_tests})")
    if len(pairwise):
        print(pairwise[["model", "metric", "config_i", "config_j", "statistic",
                        "p_value", "p_holm", "significant_holm", "cliff_delta",
                        "cliff_delta_interpretation", "n_pairs"]]
              .to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    n_sig = int(pairwise["significant_holm"].sum()) if len(pairwise) else 0
    print(f"\nSignificant cells: {n_sig} of {n_tests}")
    print(f"Wrote 3 files to {OUT_DIR}")


if __name__ == "__main__":
    main()
