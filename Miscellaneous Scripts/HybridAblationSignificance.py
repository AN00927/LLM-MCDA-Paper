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

As in PromptAblationSignificance.py, no statistic is implemented here. The
Friedman / Wilcoxon-Holm / Cliff's delta / bootstrap functions come from
RunRAGAblations.py, so all three ablations in the paper are tested by the
same reviewed code.

Tests run within each model. Pooling models would confound provenance effects
with model effects.

Outputs (Analysis/Hybrid_Ablation/):
    hybrid_ablation_friedman_tests.xlsx
    hybrid_ablation_posthoc_tests.xlsx
    hybrid_ablation_bootstrap_ci.xlsx
    hybrid_ablation_significance.xlsx     friedman / posthoc / descriptives

Run:
    python "Miscellaneous Scripts/HybridAblationSignificance.py"
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


def _load_rag_module():
    path = Path(__file__).resolve().parent / "RunRAGAblations.py"
    spec = importlib.util.spec_from_file_location("run_rag_ablations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if not SUMMARY_XLSX.exists():
        raise SystemExit(f"Missing {SUMMARY_XLSX}. Run RunHybridAblations.py first.")

    rag = _load_rag_module()
    df = pd.read_excel(SUMMARY_XLSX, sheet_name="per_scenario")
    df = df[~df["failed"].astype(bool)].copy()

    friedman_rows = []
    posthoc_rows = []
    boot_rows = []

    for model, stratum in df.groupby("model"):
        if stratum["arm"].nunique() < 3:
            continue

        fr = rag.friedman_test_per_metric(
            stratum, METRIC_COLS, config_col="arm", scenario_col="scenario_id")
        for _, r in fr.iterrows():
            friedman_rows.append({"model": model, **r.to_dict()})

        for metric in METRIC_COLS:
            ph = rag.posthoc_wilcoxon_holm(
                stratum, metric, config_col="arm", scenario_col="scenario_id")
            for _, r in ph.iterrows():
                posthoc_rows.append({"model": model, "metric": metric, **r.to_dict()})

            bc = rag.bootstrap_ci_per_config(stratum, metric, config_col="arm")
            for _, r in bc.iterrows():
                boot_rows.append({"model": model, **r.to_dict()})

    friedman = pd.DataFrame(friedman_rows)
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
    print("=== FRIEDMAN ===")
    if len(friedman):
        print(friedman[["model", "metric", "chi2", "p_value", "df", "n_scenarios", "n_configs"]]
              .to_string(index=False, float_format=lambda v: f"{v:.4g}"))

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
