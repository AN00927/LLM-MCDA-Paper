"""Significance tests for the prompt-sensitivity ablation matrix.

Answers the question the summary means cannot: are the differences between
prompt variants larger than run-to-run noise?

No statistic is implemented here. The Friedman / Wilcoxon-Holm / Cliff's delta
functions are imported from `run_rag_ablation_experiments.py`, which already carries the
reviewed implementations used for the retrieval ablation -- so both ablations
in the paper are tested by identical code. Those functions take `config_col`
and `scenario_col` as parameters, which is what makes the reuse direct.

Design:
  - Tests run WITHIN each (architecture, model) stratum, comparing prompt
    variants. Pooling across models would confound prompt effects with model
    effects, and pooling across architectures would compare A_D variants
    against A_E variants, which is not the question.
  - Scenario-level metrics are averaged over the 5 runs first, giving one
    value per (variant, scenario). This matches the "Method A" aggregation
    used by `significance_testing.py` for the headline architecture results,
    so effect estimates are comparable across the paper. `no_anchors` uses
    10 runs instead of 5 (see module-level rerun note); the averaging step is
    identical, just over more runs for that variant.
  - `no_anchors` has no A_E arm (A_E ships without anchors), so A_E strata
    test 3 variants and A_D strata test 4.

Significance-testing methodology (two correction layers, mirroring
run_rag_ablation_experiments.py and test_hybrid_ablation_significance.py exactly):
  1. Friedman omnibus test per (architecture, model, metric) -- up to
     6 strata x 2 metrics = 12 independent tests. Holm-Bonferroni correction
     is applied ACROSS this whole family before anything downstream reads a
     p-value, because reporting 12 omnibus tests side by side at nominal
     alpha=0.05 with no correction inflates the chance of at least one false
     "significant" result across the study.
  2. Post-hoc pairwise Wilcoxon signed-rank tests (Holm-corrected within
     their own per-stratum-per-metric family) are computed ONLY for
     (architecture, model, metric) cells whose Friedman omnibus remains
     significant after step 1's correction (`significant_holm`, not the raw
     `p_value`). A cell whose omnibus does not survive correction has no
     pairwise differences to report -- running the post-hoc test anyway
     would test comparisons the omnibus itself could not support.
  Bootstrap CIs are left ungated: they describe each variant's own sampling
  uncertainty, not a pairwise comparison, so they are computed for every
  stratum x metric regardless of the Friedman outcome.

Outputs (mirroring the RAG ablation's artifact set so both are tracked and
inspected the same way):
    prompt_ablation_significance.xlsx      friedman / posthoc / descriptives
    prompt_ablation_friedman_tests.xlsx
    prompt_ablation_posthoc_tests.xlsx
    prompt_ablation_bootstrap_ci.xlsx      95% percentile CIs per variant
    prompt_ablation_summary_by_decision_type.xlsx

Run:
    python "Miscellaneous Scripts/test_prompt_ablation_significance.py"
"""

import glob
import importlib.util
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CELLS_DIR = PROJECT_ROOT / "Analysis" / "Prompt_Ablation"
OUTPUT_XLSX = CELLS_DIR / "prompt_ablation_significance.xlsx"

# Metrics tested. `top1` is binary per scenario; Friedman on a binary outcome
# is valid but low-powered, so it is reported alongside tau rather than alone.
METRIC_COLS = ["kendall_tau", "top1"]


def _load_rag_module():
    """Import run_rag_ablation_experiments for its reviewed statistical helpers."""
    path = Path(__file__).resolve().parent / "run_rag_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("run_rag_ablations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_matrix() -> pd.DataFrame:
    files = sorted(glob.glob(str(CELLS_DIR / "cell_*.xlsx")))
    if not files:
        raise SystemExit(f"No cell files in {CELLS_DIR}")
    df = pd.concat([pd.read_excel(f) for f in files], ignore_index=True)

    # Failed scenarios carry sentinel-derived metrics; excluding them keeps a
    # parse failure from being scored as if it were a bad-but-valid ranking.
    return df[~df["failed"].astype(bool)].copy()


def main():
    rag = _load_rag_module()
    df = load_matrix()

    # Average over runs -> one row per (variant, architecture, model, scenario).
    per_scenario = (
        df.groupby(["variant", "architecture", "model", "scenario_id"], as_index=False)[METRIC_COLS]
        .mean()
    )

    friedman_rows = []
    strata = []

    for (arch, model), stratum in per_scenario.groupby(["architecture", "model"]):
        n_variants = stratum["variant"].nunique()
        if n_variants < 3:
            continue
        strata.append((arch, model, stratum))

        fr = rag.friedman_test_per_metric(
            stratum, METRIC_COLS,
            config_col="variant", scenario_col="scenario_id",
        )
        for _, r in fr.iterrows():
            friedman_rows.append({"architecture": arch, "model": model, **r.to_dict()})

    friedman = pd.DataFrame(friedman_rows)

    # Cross-stratum family correction: up to (architecture x model) strata x
    # 2 metrics = up to 12 independent Friedman omnibus tests are run above,
    # one per (architecture, model, metric) triple. Reporting all of them at
    # nominal alpha=0.05 with no correction across the family inflates the
    # chance of at least one false "significant" omnibus across the study,
    # the same failure mode multiple pairwise tests have without Holm
    # correction. Holm is applied here across the whole Friedman table for
    # consistency with the correction used for post-hoc pairwise tests below
    # and with the equivalent family correction in run_rag_ablation_experiments.py and
    # test_hybrid_ablation_significance.py. Post-hoc pairwise tests for a given
    # stratum x metric are only computed if that cell's Friedman result
    # remains significant AFTER this correction (significant_holm), not on
    # the raw p_value.
    if not friedman.empty:
        p_holm, significant_holm = rag.holm_correct(friedman["p_value"].values)
        friedman["p_holm"] = p_holm
        friedman["significant_holm"] = significant_holm
    else:
        friedman["p_holm"] = pd.Series(dtype=float)
        friedman["significant_holm"] = pd.Series(dtype=bool)

    posthoc_rows = []
    for arch, model, stratum in strata:
        sig_metrics = set(
            friedman.loc[
                (friedman["architecture"] == arch) & (friedman["model"] == model) & (friedman["significant_holm"]),
                "metric",
            ]
        )
        for metric in METRIC_COLS:
            if metric not in sig_metrics:
                continue
            ph = rag.posthoc_wilcoxon_holm(
                stratum, metric,
                config_col="variant", scenario_col="scenario_id",
            )
            for _, r in ph.iterrows():
                posthoc_rows.append({
                    "architecture": arch, "model": model, "metric": metric, **r.to_dict()
                })

    posthoc = pd.DataFrame(posthoc_rows)

    descriptives = (
        per_scenario.groupby(["architecture", "model", "variant"])[METRIC_COLS]
        .agg(["mean", "std"])
    )
    descriptives.columns = ["_".join(c).strip("_") for c in descriptives.columns.to_flat_index()]
    descriptives = descriptives.reset_index()

    # Bootstrap CIs per variant, within stratum. bootstrap_ci_per_config expects
    # a single config column, so each stratum is bootstrapped separately and the
    # architecture/model labels are re-attached afterwards.
    boot_rows = []
    for (arch, model), stratum in per_scenario.groupby(["architecture", "model"]):
        for metric in METRIC_COLS:
            bc = rag.bootstrap_ci_per_config(stratum, metric, config_col="variant")
            for _, r in bc.iterrows():
                boot_rows.append({"architecture": arch, "model": model, **r.to_dict()})
    bootstrap = pd.DataFrame(boot_rows)
    if len(bootstrap):
        bootstrap = bootstrap.rename(columns={"ablation_id": "variant"}).drop(
            columns=[c for c in ["ablation_label"] if c in bootstrap.columns])

    # Per-decision-type breakdown: decision_type lives on the raw rows, so this
    # is computed from df rather than the run-averaged frame.
    by_dtype = (
        df.groupby(["variant", "architecture", "model", "decision_type"], as_index=False)[METRIC_COLS]
        .mean()
        .sort_values(["architecture", "model", "variant", "decision_type"])
    )

    with pd.ExcelWriter(OUTPUT_XLSX) as xl:
        friedman.to_excel(xl, sheet_name="friedman", index=False)
        posthoc.to_excel(xl, sheet_name="posthoc", index=False)
        descriptives.to_excel(xl, sheet_name="descriptives", index=False)

    # Standalone files mirroring the RAG ablation's layout.
    friedman.to_excel(CELLS_DIR / "prompt_ablation_friedman_tests.xlsx", index=False)
    posthoc.to_excel(CELLS_DIR / "prompt_ablation_posthoc_tests.xlsx", index=False)
    bootstrap.to_excel(CELLS_DIR / "prompt_ablation_bootstrap_ci.xlsx", index=False)
    by_dtype.to_excel(CELLS_DIR / "prompt_ablation_summary_by_decision_type.xlsx", index=False)

    print(f"Strata tested: {friedman[['architecture','model']].drop_duplicates().shape[0]}")
    print(f"Scenario rows (run-averaged): {len(per_scenario)}")
    print()
    n_friedman = int(friedman["p_value"].notna().sum()) if len(friedman) else 0
    print(f"=== FRIEDMAN (per architecture x model; Holm-corrected across all {n_friedman} tests) ===")
    if len(friedman):
        show = friedman[["architecture", "model", "metric", "chi2", "p_value",
                         "p_holm", "significant_holm", "df", "n_scenarios", "n_configs"]]
        print(show.to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    n_sig_omnibus = int(friedman["significant_holm"].sum()) if len(friedman) else 0
    print()
    print(f"=== SIGNIFICANT OMNIBUS TESTS (Holm-corrected): {n_sig_omnibus} of {n_friedman} ===")
    print("(post-hoc pairwise tests below are only computed for these)")

    sig = posthoc[posthoc["significant_holm"]] if len(posthoc) else pd.DataFrame()
    print()
    print(f"=== SIGNIFICANT PAIRS (Holm-corrected within each stratum x metric posthoc family): {len(sig)} of {len(posthoc)} ===")
    if len(sig):
        show = sig[["architecture", "model", "metric", "config_i", "config_j",
                    "p_holm", "cliff_delta", "cliff_delta_interpretation"]]
        print(show.to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    print(f"\nWrote {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
