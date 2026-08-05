"""Significance tests for the hybrid (parameter-provenance) ablation.

Tests whether the three parameter-provenance arms differ by more than noise:
    true_params      reference ceiling (true hidden parameters)
    extracted        LLM-extracted hidden parameters
    default_params   corpus-median parameters, no inference

The comparison that carries the paper's claim is extracted vs default_params:
it isolates what the extraction step contributes over a no-inference baseline.
true_params is a ceiling by construction (tau = 1.0, MAE = 0 for every
scenario), so pairs involving it are reported but are not evidence about the
method -- they quantify the remaining headroom.

As in test_prompt_ablation_significance.py, no statistic is implemented here. The
Friedman / Wilcoxon-Holm / Cliff's delta / bootstrap functions come from
run_rag_ablation_experiments.py, so all three ablations in the paper are tested by the
same reviewed code.

Only the three provenance arms above are tested here. `hybrid_ablation_summary.xlsx`
also carries the alternative-ordering arms (`extracted_per_run`, `order_control`,
`order_reversed`), which are a different experiment with its own analysis in
`hybrid_order_reversal.xlsx`. They are excluded for two reasons: including them
would silently redefine this omnibus from "do the three provenance arms differ"
to "do six mixed arms differ", and they carry several runs per scenario, which
`friedman_test_per_metric` would collapse with `aggfunc='first'` -- keeping run 1
and discarding the rest without saying so.

Tests run within each model. Pooling models would confound provenance effects
with model effects.

Significance-testing methodology (two correction layers, identical in kind to
run_rag_ablation_experiments.py and test_prompt_ablation_significance.py):
  1. Friedman omnibus test per (model, metric): the family size is (number of
     models) x (number of metrics) and grows whenever a model is added. With
     the four models currently collected that is 4 x 3 = 12 tests; it was 9
     before the Gemini arm. The script prints the realised count at run time --
     read that, not this comment, when reporting the family size.
     Holm-Bonferroni correction is applied ACROSS this whole family before any
     p-value is used downstream, so the omnibus tests are not each
     independently exposed to nominal alpha=0.05. Adding a model therefore
     makes every existing cell's corrected p-value more conservative; that is
     the correction working, not a regression.
  2. Post-hoc pairwise Wilcoxon+Holm tests (each model x metric's own
     pairwise family separately Holm-corrected) are computed ONLY for
     (model, metric) cells whose Friedman omnibus remains significant after
     step 1 (significant_holm, not raw p_value < 0.05).
  Bootstrap CIs are left ungated, computed for every model x metric
  regardless of the Friedman outcome, since they describe an arm's own
  sampling uncertainty rather than a pairwise comparison.

Outputs (Analysis/Hybrid_Ablation/):
    hybrid_ablation_friedman_tests.xlsx
    hybrid_ablation_posthoc_tests.xlsx
    hybrid_ablation_bootstrap_ci.xlsx
    hybrid_ablation_significance.xlsx     friedman / posthoc / descriptives

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
PROVENANCE_ARMS = ["true_params", "extracted", "default_params"]


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

    friedman_rows = []
    boot_rows = []
    strata = []

    for model, stratum in df.groupby("model"):
        if stratum["arm"].nunique() < 3:
            continue
        strata.append((model, stratum))

        fr = rag.friedman_test_per_metric(
            stratum, METRIC_COLS, config_col="arm", scenario_col="scenario_id")
        for _, r in fr.iterrows():
            friedman_rows.append({"model": model, **r.to_dict()})

        # Bootstrap CIs are left ungated: they describe each arm's own
        # sampling uncertainty, not a pairwise comparison, so they are
        # computed for every model x metric regardless of the Friedman
        # outcome (matching run_rag_ablation_experiments.py and test_prompt_ablation_significance.py).
        for metric in METRIC_COLS:
            bc = rag.bootstrap_ci_per_config(stratum, metric, config_col="arm",
                                             stratum_key=model)
            for _, r in bc.iterrows():
                boot_rows.append({"model": model, **r.to_dict()})

    friedman = pd.DataFrame(friedman_rows)

    # Cross-stratum family correction: (number of models) x len(METRIC_COLS)
    # independent Friedman omnibus tests are run above, one per (model,
    # metric) pair -- 12 with the four models currently collected.
    # Holm-Bonferroni correction is applied ACROSS this whole family before it
    # is used for anything downstream, for the same reason and using the same
    # method as run_rag_ablation_experiments.py and
    # test_prompt_ablation_significance.py: reporting several omnibus tests
    # side by side at nominal alpha=0.05 with no correction inflates the
    # family-wise false-positive rate across the study.
    if not friedman.empty:
        p_holm, significant_holm = rag.holm_correct(friedman["p_value"].values)
        friedman["p_holm"] = p_holm
        friedman["significant_holm"] = significant_holm
    else:
        friedman["p_holm"] = pd.Series(dtype=float)
        friedman["significant_holm"] = pd.Series(dtype=bool)

    # Post-hoc pairwise Wilcoxon+Holm tests (each stratum x metric's own
    # pairwise family separately Holm-corrected) are computed ONLY for
    # (model, metric) cells whose Friedman omnibus remains significant after
    # the family correction above (significant_holm, not raw p_value < 0.05).
    posthoc_rows = []
    for model, stratum in strata:
        sig_metrics = set(
            friedman.loc[
                (friedman["model"] == model) & (friedman["significant_holm"]),
                "metric",
            ]
        )
        for metric in METRIC_COLS:
            if metric not in sig_metrics:
                continue
            ph = rag.posthoc_wilcoxon_holm(
                stratum, metric, config_col="arm", scenario_col="scenario_id")
            for _, r in ph.iterrows():
                posthoc_rows.append({"model": model, "metric": metric, **r.to_dict()})

    posthoc = pd.DataFrame(posthoc_rows)
    bootstrap = pd.DataFrame(boot_rows)
    if len(bootstrap):
        bootstrap = bootstrap.rename(columns={"ablation_id": "arm"}).drop(
            columns=[c for c in ["ablation_label"] if c in bootstrap.columns])

    descriptives = df.groupby(["model", "arm"])[METRIC_COLS].agg(["mean", "std"])
    descriptives.columns = ["_".join(c).strip("_") for c in descriptives.columns.to_flat_index()]
    descriptives = descriptives.reset_index()

    with pd.ExcelWriter(OUT_DIR / "hybrid_ablation_significance.xlsx") as xl:
        friedman.to_excel(xl, sheet_name="friedman", index=False)
        posthoc.to_excel(xl, sheet_name="posthoc", index=False)
        descriptives.to_excel(xl, sheet_name="descriptives", index=False)

    friedman.to_excel(OUT_DIR / "hybrid_ablation_friedman_tests.xlsx", index=False)
    posthoc.to_excel(OUT_DIR / "hybrid_ablation_posthoc_tests.xlsx", index=False)
    bootstrap.to_excel(OUT_DIR / "hybrid_ablation_bootstrap_ci.xlsx", index=False)

    print(f"Models tested: {df['model'].nunique()}  |  scenario rows: {len(df)}")
    print()
    n_friedman = int(friedman["p_value"].notna().sum()) if len(friedman) else 0
    print(f"=== FRIEDMAN (Holm-corrected across all {n_friedman} tests) ===")
    if len(friedman):
        print(friedman[["model", "metric", "chi2", "p_value", "p_holm", "significant_holm",
                        "df", "n_scenarios", "n_configs"]]
              .to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    n_sig_omnibus = int(friedman["significant_holm"].sum()) if len(friedman) else 0
    print()
    print(f"=== SIGNIFICANT OMNIBUS TESTS (Holm-corrected): {n_sig_omnibus} of {n_friedman} ===")
    print("(post-hoc pairwise tests below are only computed for these)")

    key = posthoc[
        posthoc.apply(lambda r: {r["config_i"], r["config_j"]} == {"extracted", "default_params"}, axis=1)
    ] if len(posthoc) else pd.DataFrame()
    print()
    print("=== extracted vs default_params (the contribution of extraction) ===")
    if len(key):
        print(key[["model", "metric", "p_holm", "significant_holm",
                   "cliff_delta", "cliff_delta_interpretation"]]
              .to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    n_sig = int(posthoc["significant_holm"].sum()) if len(posthoc) else 0
    print(f"\nSignificant pairs overall: {n_sig} of {len(posthoc)}")
    print(f"Wrote 4 files to {OUT_DIR}")


if __name__ == "__main__":
    main()
