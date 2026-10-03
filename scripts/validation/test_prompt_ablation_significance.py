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
  - Scenario-level metrics are averaged over the runs first (3 per cell,
    fixed in advance, author decision 2026-09-27), giving one value per
    (variant, scenario). This matches the "Method A" aggregation used by
    `significance_testing.py` for the headline architecture results, so
    effect estimates are comparable across the paper.
  - The control cell is NOT a collected cell by default: it is main-suite runs
    1..R (R = the stratum's run count), rebuilt and scored by
    run_prompt_ablation_experiments.main_suite_control_rows. The ablation
    script checks at startup that its control messages equal the main suite's
    byte for byte. A control collected explicitly (cell_control_*) is used
    instead when present, never mixed with main-suite rows.
  - Variants since 2026-09-27: control, no_anchors, cot_scaffold (scale_0_10
    cut). `no_anchors` has no A_E arm (A_E ships without anchors), so A_D
    strata test 3 variants (Friedman omnibus, then post-hoc Wilcoxon) and A_E
    strata test 2 (one paired Wilcoxon signed-rank test, control vs
    cot_scaffold, which is that stratum's omnibus test and joins the same
    Holm family as the Friedman tests).

Significance-testing methodology (two correction layers, mirroring
run_rag_ablation_experiments.py and test_hybrid_ablation_significance.py exactly):
  1. Friedman omnibus test per (architecture, model, metric): one test per
     stratum per metric, so the family size is (number of strata) x
     (number of metrics) and grows whenever a model or metric is added. With
     the four models currently collected and top2 added alongside kendall_tau
     and top1 (2026-09-27), that is 8 strata x 3 metrics = 24 tests; it was
     16 with two metrics, and 12 before the Gemini arm. The script prints the
     realised count at run time -- read that, not this comment, when
     reporting the family size.
     Holm-Bonferroni correction is applied ACROSS this whole family before
     anything downstream reads a p-value, because reporting every omnibus
     test side by side at nominal alpha=0.05 with no correction inflates the
     chance of at least one false "significant" result across the study.
     Adding a model therefore makes every existing cell's corrected p-value
     more conservative; that is the correction working, not a regression.
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
inspected the same way) in a required safe destination supplied with
--output-dir or LLM_MCDA_RUN_OUTPUT_DIR:
    prompt_ablation_significance.xlsx      friedman / posthoc / descriptives
    prompt_ablation_friedman_tests.xlsx
    prompt_ablation_posthoc_tests.xlsx
    prompt_ablation_bootstrap_ci.xlsx      95% percentile CIs per variant
    prompt_ablation_summary_by_decision_type.xlsx

Run:
    python "scripts/validation/test_prompt_ablation_significance.py" --output-dir results/scratch/prompt-significance
"""

import argparse
import glob
import importlib.util
import os
import sys
from pathlib import Path

# Direct script execution does not add src/ when the package is uninstalled.
_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if _SRC_ROOT.is_dir() and str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import pandas as pd

from llm_mcda.common.paths import (
    RUN_OUTPUT_DIR_ENV,
    repository_path,
    repository_root,
    require_safe_output_directory,
)
from llm_mcda.common.model_config import get_model_artifact_subdir
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CELLS_DIRS = [
    repository_path(get_model_artifact_subdir(mk, "prompt_ablation"))
    for mk in ("deepseek", "gemini", "gptoss", "qwen")
]
OUTPUT_XLSX = repository_path("Combined Metrics", "prompt_ablation_significance.xlsx")

# Metrics tested. `top1` and `top2` are binary per scenario; Friedman on a
# binary outcome is valid but low-powered, so they are reported alongside tau
# rather than alone. Both follow the failure-as-wrong accuracy rule (author
# decision, 2026-09-27, mirroring the RAG ablation): a failed or unscored
# scenario's top1/top2 is 0.0 (never NaN), so it counts as wrong rather than
# being dropped from the comparison. kendall_tau follows the same failure rule
# (S4, 2026-09-29): a failed scenario is at chance, tau 0 (FAILED_SCENARIO_TAU),
# and stays in the comparison.
METRIC_COLS = ["kendall_tau", "top1", "top2"]
FAILED_SCENARIO_TAU = 0.0


def _load_rag_module():
    """Import run_rag_ablation_experiments for its reviewed statistical helpers."""
    path = PROJECT_ROOT / "scripts" / "experiments" / "run_rag_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("run_rag_ablations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_prompt_ablation_module():
    """Import run_prompt_ablation_experiments for the main-suite control loader
    and the reference ranking, so control rows are scored by the same code as
    the collected cells."""
    path = PROJECT_ROOT / "scripts" / "experiments" / "run_prompt_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("run_prompt_ablation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_main_suite_control(df: pd.DataFrame, pa=None) -> pd.DataFrame:
    """Append the control cell for every (architecture, model) stratum that has
    no collected control, from main-suite runs 1..R, where R is the stratum's
    largest run index. Restricted to the scenarios the stratum's cells cover."""
    pa = pa or _load_prompt_ablation_module()
    reference = None
    parts = [df]
    for (arch, model), g in df.groupby(["architecture", "model"]):
        if (g["variant"] == "control").any():
            continue
        if reference is None:
            reference = pa.load_reference()
        runs = int(g["run"].max())
        control = pa.main_suite_control_rows(model, arch, runs, reference,
                                             scenario_ids=set(int(x) for x in g["scenario_id"]))
        print(f"Control for {arch}/{model}: main-suite runs 1-{runs} ({len(control)} scenario rows)")
        parts.append(control)
    return pd.concat(parts, ignore_index=True)


def load_matrix() -> pd.DataFrame:
    """All per-scenario cell rows, failed scenarios included.

    A failed scenario (`failed` True) is kept under the failure rule (S4):
    top1/top2 0.0 (wrong) and kendall_tau FAILED_SCENARIO_TAU = 0 (chance).
    Cells collected before 2026-09-29 stored NaN for a failed scenario's tau;
    it is set to the rule's value here, so no failed scenario drops out of a
    paired test.
    """
    files = sorted(
        f for d in CELLS_DIRS for f in glob.glob(str(d / "cell_*.xlsx"))
    )
    if not files:
        raise SystemExit(
            "No cell files in " + ", ".join(str(d) for d in CELLS_DIRS)
        )
    df = pd.concat([pd.read_excel(f) for f in files], ignore_index=True)
    # Rescore from the stored per-alternative scores against the corrected
    # reference (see run_prompt_ablation_experiments.load_reference): cells
    # collected before that fix stored metrics against a wrong reference
    # ranking for 16 Shower scenarios. Raw scores are untouched.
    pa = _load_prompt_ablation_module()
    df = pa.rescore_cell_rows(df, pa.load_reference())
    df.loc[df["failed"].astype(bool), "kendall_tau"] = FAILED_SCENARIO_TAU
    return df


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output-dir",
        help=f"Safe output directory (required unless {RUN_OUTPUT_DIR_ENV} is set).",
    )
    return parser.parse_args(argv)


def two_variant_test(stratum: pd.DataFrame, metric_cols, rag) -> list:
    """Omnibus rows for a 2-variant stratum: one paired Wilcoxon signed-rank
    test per metric (Friedman needs 3 groups). The rows carry the same columns
    as the Friedman rows plus `test`, so both join one Holm family."""
    rows = []
    for metric in metric_cols:
        ph = rag.posthoc_wilcoxon_holm(stratum, metric, config_col="variant",
                                       scenario_col="scenario_id")
        if ph.empty:
            continue
        r = ph.iloc[0]
        rows.append({"metric": metric, "test": "wilcoxon_signed_rank", "chi2": float("nan"),
                     "statistic": r["statistic"], "p_value": r["p_value"], "df": 1,
                     "n_scenarios": r["n_pairs"], "n_configs": 2,
                     "config_i": r["config_i"], "config_j": r["config_j"],
                     "rank_biserial": r["rank_biserial"],
                     "rank_biserial_interpretation": r["rank_biserial_interpretation"],
                     "n_nonzero": r["n_nonzero"],
                     "cliff_delta": r["cliff_delta"],
                     "cliff_delta_interpretation": r["cliff_delta_interpretation"]})
    return rows


def main(args=None):
    library_call = args is None
    output_value = args.output_dir if args is not None else None
    output_option = "--output-dir"
    if output_value is None:
        output_value = os.environ.get(RUN_OUTPUT_DIR_ENV)
        if output_value is not None:
            output_option = RUN_OUTPUT_DIR_ENV
    if output_value is None and library_call:
        # Keep the in-process path override used by existing callers while
        # rejecting the frozen repository default before any writes.
        output_value = OUTPUT_XLSX.parent
    out_dir = require_safe_output_directory(output_value, option=output_option)
    output_xlsx = out_dir / OUTPUT_XLSX.name

    rag = _load_rag_module()
    df = add_main_suite_control(load_matrix())

    # Average over runs -> one row per (variant, architecture, model, scenario).
    per_scenario = (
        df.groupby(["variant", "architecture", "model", "scenario_id"], as_index=False)[METRIC_COLS]
        .mean()
    )

    friedman_rows = []
    strata = []

    for (arch, model), stratum in per_scenario.groupby(["architecture", "model"]):
        n_variants = stratum["variant"].nunique()
        if n_variants == 2:
            for r in two_variant_test(stratum, METRIC_COLS, rag):
                friedman_rows.append({"architecture": arch, "model": model, **r})
            continue
        if n_variants < 3:
            continue
        strata.append((arch, model, stratum))

        fr = rag.friedman_test_per_metric(
            stratum, METRIC_COLS,
            config_col="variant", scenario_col="scenario_id",
        )
        for _, r in fr.iterrows():
            friedman_rows.append({"architecture": arch, "model": model, "test": "friedman",
                                  **r.to_dict()})

    friedman = pd.DataFrame(friedman_rows)

    # Cross-stratum family correction: (architecture x model) strata x
    # len(METRIC_COLS) metrics independent Friedman omnibus tests are run
    # above, one per (architecture, model, metric) triple -- 16 with the four
    # models currently collected. Reporting all of them at
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
    # architecture/model labels are re-attached afterwards. `stratum_key` is
    # passed so each (architecture, model, variant, metric) bootstrap seeds off
    # its own key: without it, the same variant in two strata would resample on
    # identical indices, and the draw would depend on loop position.
    boot_rows = []
    for (arch, model), stratum in per_scenario.groupby(["architecture", "model"]):
        for metric in METRIC_COLS:
            bc = rag.bootstrap_ci_per_config(stratum, metric, config_col="variant",
                                             stratum_key=f"{arch}|{model}")
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

    out_dir.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_xlsx) as xl:
        friedman.to_excel(xl, sheet_name="friedman", index=False)
        posthoc.to_excel(xl, sheet_name="posthoc", index=False)
        descriptives.to_excel(xl, sheet_name="descriptives", index=False)

    # Standalone files mirroring the RAG ablation's layout.
    friedman.to_excel(out_dir / "prompt_ablation_friedman_tests.xlsx", index=False)
    posthoc.to_excel(out_dir / "prompt_ablation_posthoc_tests.xlsx", index=False)
    bootstrap.to_excel(out_dir / "prompt_ablation_bootstrap_ci.xlsx", index=False)
    by_dtype.to_excel(out_dir / "prompt_ablation_summary_by_decision_type.xlsx", index=False)

    print(f"Strata tested: {friedman[['architecture','model']].drop_duplicates().shape[0]}")
    print(f"Scenario rows (run-averaged): {len(per_scenario)}")
    print()
    n_friedman = int(friedman["p_value"].notna().sum()) if len(friedman) else 0
    print(f"=== FRIEDMAN (per architecture x model; Holm-corrected across all {n_friedman} tests) ===")
    if len(friedman):
        show = friedman[["architecture", "model", "metric", "test", "chi2", "p_value",
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
                    "p_holm", "rank_biserial", "rank_biserial_interpretation", "n_nonzero"]]
        print(show.to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    print(f"\nWrote {output_xlsx}")


if __name__ == "__main__":
    main(parse_args())
