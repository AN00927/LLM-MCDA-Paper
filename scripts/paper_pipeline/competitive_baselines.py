#!/usr/bin/env python3
"""
competitive_baselines.py - task P1.5 of the EMS revision plan.

QUESTION. Does A_E beat a fixed default, and does it beat copying the ranking
of the one exemplar it retrieves (the NearestNeighbor copy baseline, k = 1)?
The manuscript recommends A_E as the practical option for domains where a
calculator cannot be built. That recommendation only survives if A_E beats the
trivial non-LLM baselines a practitioner already has.

TESTS (S7). Per model, a paired Wilcoxon signed-rank test on the 195 Test
scenarios: A_E's per-scenario value (the mean over its runs, failure rule
applied: a failed scenario-run is wrong for Top-1 and at tau 0) against the
baseline's value on the same scenario, paired by the matched ground-truth
scenario. Effect size: matched-pairs rank-biserial (positive = A_E higher).
Holm family: every test in this file, (number of models) x 2 baselines
(FixedDefault, NearestNeighbor) x 2 metrics (tau, Top-1) = 16 with four models.

WHAT THIS REPORTS, per model and per decision type:
  * A_E on Kendall's tau and Top-1 (per-run mean, then mean across runs -- the
    paper's estimator, per the estimator decision).
  * FixedDefault on the same two metrics. FixedDefault is deterministic and
    model-independent, so it is one column repeated against four models.
  * The single-criterion-argmax baseline per decision type: rank the three
    alternatives by ONE ground-truth criterion and score that ranking against
    the reference MAVT ranking. Also model-independent.

NULL RESULTS ARE REPORTED STRAIGHT. If A_E loses to a fixed default on a
decision type, that is the finding.

SOURCES
  A_E:            local-only per-run metrics CSV
  FixedDefault:   results/older_runs/unclassified_legacy/Baselines/baseline_metrics.csv
                  (preserved output of scripts/analysis/evaluate_baseline_metrics.py)
  Single-crit:    workbooks/ground_truth/ground_truth_*.xlsx, restricted to the 195 Test
                  scenarios by matching against a shipped run file, so the
                  scenario set is exactly the one the architectures were scored on.

Ties in a single-criterion ranking are not broken by list order: Top-1 and tau
are their expected values under a uniform random tie-break (1/k credit when the
reference winner is among k alternatives tied for the best value; tied pairs
count 0 in tau), from paper_pipeline/single_criterion.py, the implementation
used by the single-criterion recovery table.

Output: local-only workbook (3 sheets) and Markdown report copies

Usage:
    python scripts/paper_pipeline/competitive_baselines.py
"""

import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
sys.path.insert(0, str(PROJECT_ROOT))
IMPORT_ROOT = PROJECT_ROOT
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

from common.paths import repository_path  # noqa: E402
from common.model_config import CRITERIA, MODEL_SPECS  # noqa: E402
from common.sentinel_utils import _is_complete_run_file  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from single_criterion import expected_tau, top1_credit  # noqa: E402

_cm_path = PROJECT_ROOT / "scripts" / "analysis" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("evaluate_architecture_metrics", _cm_path)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

PER_RUN_CSV = repository_path("Combined Metrics", "per_run_metrics_all.csv")
BASELINE_DIR = PROJECT_ROOT / "workbooks" / "older_runs" / "unclassified_legacy" / "Baselines"
BASELINE_CSV = PROJECT_ROOT / "results" / "older_runs" / "unclassified_legacy" / "Baselines" / "baseline_metrics.csv"
BASELINE_FILES = {"FixedDefault": "baseline_fixeddefault.xlsx",
                  "NearestNeighbor": "baseline_nearestneighbor.xlsx"}
TEST_METRICS = {"kendall_tau": "tau", "top1": "Top-1"}
OUT_XLSX = repository_path("Combined Metrics", "competitive_baselines.xlsx")
OUT_MD = repository_path("Combined Metrics", "competitive_baselines.md")

AE = "Example-Guided_LLM_Scoring"
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]


# ---------------------------------------------------------------------------
# A_E
# ---------------------------------------------------------------------------

def ae_by_type():
    df = pd.read_csv(PER_RUN_CSV)
    df = df[df["architecture"] == AE]
    rows = []
    for (model, dt), g in df.groupby(["model", "decision_type"]):
        rows.append({
            "model": model,
            "decision_type": dt,
            "n_runs": len(g),
            "AE_tau": float(g["kendall_tau"].mean()),
            "AE_tau_sd": float(g["kendall_tau"].std(ddof=1)),
            "AE_top1": float(g["top1_accuracy"].mean()),
            "AE_top1_sd": float(g["top1_accuracy"].std(ddof=1)),
            "AE_n_scenarios_mean": float(g["n_scenarios"].mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FixedDefault
# ---------------------------------------------------------------------------

def baseline_by_type(name="FixedDefault", prefix="FD"):
    df = pd.read_csv(BASELINE_CSV)
    df = df[df["baseline"] == name]
    piv = df.pivot_table(index="decision_type", columns="metric",
                         values="value", aggfunc="first")
    out = []
    for dt in DECISION_TYPES + ["Overall_pooled"]:
        if dt not in piv.index:
            continue
        out.append({
            "decision_type": "Overall" if dt == "Overall_pooled" else dt,
            f"{prefix}_tau": float(piv.loc[dt, "kendall_tau"]),
            f"{prefix}_top1": float(piv.loc[dt, "top1_accuracy"]),
        })
    return pd.DataFrame(out)


def fixeddefault_by_type():
    return baseline_by_type("FixedDefault", "FD")


# ---------------------------------------------------------------------------
# Paired tests: A_E vs each baseline, per model (S7)
# ---------------------------------------------------------------------------

def _per_scenario(merged):
    """Per-scenario tau / Top-1 under the failure rule, keyed by the matched
    ground-truth scenario (decision_type, gt_scenario_id), which is the same
    for an architecture run and a baseline file."""
    ps = _cm.per_scenario_ranking_metrics(merged)
    key = merged.groupby("arch_scenario_id")["gt_scenario_id"].first()
    ps = ps.join(key, on="arch_scenario_id")
    ps["key"] = list(zip(ps["decision_type"], ps["gt_scenario_id"].astype(str)))
    return ps.set_index("key")[list(TEST_METRICS)]


def _gt_lookups():
    config = _cm._build_config(sorted(MODEL_SPECS)[0])
    gt = _cm.load_ground_truth(config)
    return _cm.build_gt_lookup(gt), _cm.build_gt_id_lookup(gt)


def baseline_per_scenario(name, lookups):
    df = pd.read_excel(BASELINE_DIR / BASELINE_FILES[name])
    df = df.rename(columns={f"{c}_score": c for c in CRITERIA})
    for col in ("question", "location", "alternative"):
        df[col] = df[col].astype(str).str.strip()
    arch = _cm.load_architecture(df, name)
    merged, _ = _cm.match_scenarios(*lookups, arch, name)
    return _per_scenario(merged)


def ae_per_scenario(model_key, lookups):
    """A_E per scenario: each run scored under the failure rule, then the mean
    over runs."""
    folder = PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"]
    runs = [p for p in sorted(folder.glob(f"{AE}_results_run_*.xlsx"))
            if _is_complete_run_file(p)]
    parts = []
    for p in runs:
        merged, _ = _cm.match_scenarios(*lookups, _cm.load_architecture(p, AE), AE)
        parts.append(_per_scenario(merged))
    if not parts:
        return None, 0
    return pd.concat(parts).groupby(level=0).mean(), len(parts)


def _load_rag_stats():
    path = PROJECT_ROOT / "scripts" / "experiments" / "run_rag_ablation_experiments.py"
    spec = spec_from_file_location("competitive_rag_stats", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def paired_tests(models=None):
    """One paired Wilcoxon per (model, baseline, metric), Holm over all of them."""
    rag = _load_rag_stats()
    lookups = _gt_lookups()
    base = {name: baseline_per_scenario(name, lookups) for name in BASELINE_FILES}
    rows = []
    for model_key in (models or list(MODEL_SPECS)):
        ae, n_runs = ae_per_scenario(model_key, lookups)
        if ae is None:
            print(f"  [SKIP] {model_key}: no A_E run files")
            continue
        for name, b in base.items():
            both = ae.join(b, lsuffix="_ae", rsuffix="_base", how="inner")
            for metric, label in TEST_METRICS.items():
                x = both[f"{metric}_ae"].values.astype(float)
                y = both[f"{metric}_base"].values.astype(float)
                if np.allclose(x, y):
                    stat, p = 0.0, 1.0
                else:
                    stat, p = stats.wilcoxon(x, y, alternative="two-sided")
                rb, n_nonzero = rag.matched_pairs_rank_biserial(x, y)
                rows.append({"model": model_key, "baseline": name, "metric": label,
                             "n_runs_AE": n_runs, "n_pairs": len(both),
                             "n_nonzero": n_nonzero,
                             "AE_mean": float(np.mean(x)), "baseline_mean": float(np.mean(y)),
                             "diff": float(np.mean(x - y)),
                             "statistic": float(stat), "p_value": float(p),
                             "rank_biserial": rb})
    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"], out["significant_holm"] = rag.holm_correct(out["p_value"].values)
        out["holm_family_size"] = int(out["p_value"].notna().sum())
    return out


# ---------------------------------------------------------------------------
# Single-criterion argmax baseline, on the 195 Test scenarios
# ---------------------------------------------------------------------------

def _tau(gt_ranks, pred_ranks):
    if len(set(gt_ranks)) > 1 and len(set(pred_ranks)) > 1:
        t, _ = stats.kendalltau(gt_ranks, pred_ranks)
        return 0.0 if np.isnan(t) else float(t)
    return 1.0 if list(gt_ranks) == list(pred_ranks) else 0.0


def test_reference_table():
    """The 195 Test scenarios with their reference criterion scores and ranks.

    Obtained by matching a shipped A_H run file against the ground truth with
    the project's own matcher, then keeping only the gt_* columns. This
    guarantees the scenario set is identical to the one the metrics use, and
    it drops the 90 RAG scenarios that also live in ground_truth_*.xlsx.
    """
    model_key = sorted(MODEL_SPECS)[0]
    config = _cm._build_config(model_key)
    folder = Path(config["output_csv"]).parent
    path = folder / "LLM-Parameterized_Reference_Scoring_results_run_01.xlsx"
    if not path.exists():
        raise SystemExit(f"Missing carrier run file: {path}")
    gt_by_type = _cm.load_ground_truth(config)
    arch_df = _cm.load_architecture(path, "carrier")
    merged, _ = _cm.match_scenarios(_cm.build_gt_lookup(gt_by_type),
                                    _cm.build_gt_id_lookup(gt_by_type),
                                    arch_df, "carrier")
    keep = ["arch_scenario_id", "decision_type", "norm_alternative",
            "gt_rank", "gt_mavt_score"] + [f"gt_{c}" for c in CRITERIA]
    ref = merged[keep].copy()
    n = ref["arch_scenario_id"].nunique()
    if n != 195:
        raise SystemExit(f"Reference table has {n} scenarios, expected 195")
    return ref


def single_criterion_baseline(ref):
    rows = []
    for dt in DECISION_TYPES:
        sub = ref[ref["decision_type"] == dt]
        sids = sorted(sub["arch_scenario_id"].unique())
        for crit in CRITERIA:
            taus, top1s = [], []
            for sid in sids:
                sc = sub[sub["arch_scenario_id"] == sid]
                gt_ranks = list(sc["gt_rank"].astype(float))
                vals = list(sc[f"gt_{crit}"].astype(float))
                # Expected values under a uniform random tie-break (shared
                # with compute_dispersion_diagnostics.py), not first occurrence.
                taus.append(expected_tau(gt_ranks, vals))
                top1s.append(top1_credit(gt_ranks, vals))
            rows.append({
                "decision_type": dt,
                "criterion": crit,
                "n_scenarios": len(sids),
                "SC_tau": float(np.mean(taus)),
                "SC_top1": float(np.mean(top1s)),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------

def main():
    if not PER_RUN_CSV.is_file():
        raise SystemExit(
            f"Required local-only per-run metrics are missing: {PER_RUN_CSV}. "
            "Restore the file under local_manuscripts/ or set "
            "LLM_MCDA_LOCAL_MANUSCRIPTS_DIR."
        )
    warnings.filterwarnings("ignore")
    print("P1.5 competitive baselines")
    print("=" * 64)

    ae = ae_by_type()
    fd = fixeddefault_by_type()
    nn = baseline_by_type("NearestNeighbor", "NN")
    print(f"  A_E cells: {len(ae)}")
    print(f"  FixedDefault rows: {len(fd)}")

    ref = test_reference_table()
    sc = single_criterion_baseline(ref)
    print(f"  Single-criterion rows: {len(sc)}")

    head = ae.merge(fd, on="decision_type", how="left").merge(nn, on="decision_type", how="left")
    head["d_tau"] = head["AE_tau"] - head["FD_tau"]
    head["d_top1"] = head["AE_top1"] - head["FD_top1"]
    head["AE_beats_FD_tau"] = head["d_tau"] > 0
    head["AE_beats_FD_top1"] = head["d_top1"] > 0
    head["d_tau_NN"] = head["AE_tau"] - head["NN_tau"]
    head["d_top1_NN"] = head["AE_top1"] - head["NN_top1"]
    head["AE_beats_NN_tau"] = head["d_tau_NN"] > 0
    head["AE_beats_NN_top1"] = head["d_top1_NN"] > 0

    tests = paired_tests()
    print(f"  Paired tests: {len(tests)} (Holm across all of them)")
    order = {"Overall": 0, "HVAC": 1, "Appliance": 2, "Shower": 3}
    head = head.sort_values(["model", "decision_type"],
                            key=lambda s: s.map(order) if s.name == "decision_type" else s)

    # Best single criterion per decision type, for the summary table.
    best = (sc.sort_values("SC_top1", ascending=False)
              .groupby("decision_type", as_index=False).first()
              .rename(columns={"criterion": "best_criterion",
                               "SC_tau": "best_SC_tau",
                               "SC_top1": "best_SC_top1"}))

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        head.to_excel(xw, sheet_name="AE_vs_FixedDefault", index=False)
        sc.to_excel(xw, sheet_name="SingleCriterionArgmax", index=False)
        best.to_excel(xw, sheet_name="BestSingleCriterion", index=False)
        tests.to_excel(xw, sheet_name="PairedTests_AE_vs_baselines", index=False)
    print(f"  Wrote {OUT_XLSX}")

    lines = []
    lines.append("# P1.5 - competitive baselines\n")
    lines.append("Estimator: per-run mean, then mean across runs (aggregation A).")
    lines.append("FixedDefault and the single-criterion baselines are deterministic and")
    lines.append("model-independent; they are repeated against each model for comparison.\n")

    lines.append("## A_E vs FixedDefault, per model and decision type\n")
    lines.append("| Model | Decision type | A_E tau | FD tau | d tau | A_E Top-1 | FD Top-1 | d Top-1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for _, r in head.iterrows():
        lines.append("| %s | %s | %.4f | %.4f | %+.4f | %.4f | %.4f | %+.4f |" % (
            r["model"], r["decision_type"], r["AE_tau"], r["FD_tau"], r["d_tau"],
            r["AE_top1"], r["FD_top1"], r["d_top1"]))

    n_cells = len(head)
    win_tau = int(head["AE_beats_FD_tau"].sum())
    win_t1 = int(head["AE_beats_FD_top1"].sum())
    lines.append("")
    lines.append("**A_E beats FixedDefault in %d of %d cells on tau and %d of %d on Top-1.**"
                 % (win_tau, n_cells, win_t1, n_cells))
    lines.append("")
    lines.append("## A_E vs the NearestNeighbor copy baseline (k = 1), per model and decision type\n")
    lines.append("| Model | Decision type | A_E tau | NN tau | d tau | A_E Top-1 | NN Top-1 | d Top-1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for _, r in head.iterrows():
        lines.append("| %s | %s | %.4f | %.4f | %+.4f | %.4f | %.4f | %+.4f |" % (
            r["model"], r["decision_type"], r["AE_tau"], r["NN_tau"], r["d_tau_NN"],
            r["AE_top1"], r["NN_top1"], r["d_top1_NN"]))
    lines.append("")
    lines.append("## Paired Wilcoxon, A_E vs each baseline (per model; Holm over all %d tests)\n"
                 % len(tests))
    lines.append("| Model | Baseline | Metric | A_E | Baseline | diff | n pairs | n non-zero | p | p Holm | rank-biserial |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in tests.iterrows():
        lines.append("| %s | %s | %s | %.4f | %.4f | %+.4f | %d | %d | %.3g | %.3g | %+.3f |" % (
            r["model"], r["baseline"], r["metric"], r["AE_mean"], r["baseline_mean"],
            r["diff"], r["n_pairs"], r["n_nonzero"], r["p_value"], r["p_holm"],
            r["rank_biserial"]))
    lines.append("")
    lines.append("## Single-criterion argmax baseline, per decision type\n")
    lines.append("| Decision type | n | Criterion | tau | Top-1 |")
    lines.append("|---|---|---|---|---|")
    for _, r in sc.iterrows():
        lines.append("| %s | %d | %s | %.4f | %.4f |" % (
            r["decision_type"], r["n_scenarios"], r["criterion"],
            r["SC_tau"], r["SC_top1"]))
    lines.append("")
    lines.append("## Strongest single criterion per decision type\n")
    lines.append("| Decision type | Criterion | tau | Top-1 |")
    lines.append("|---|---|---|---|")
    for _, r in best.iterrows():
        lines.append("| %s | %s | %.4f | %.4f |" % (
            r["decision_type"], r["best_criterion"], r["best_SC_tau"], r["best_SC_top1"]))

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")

    print("\n" + "\n".join(lines[6:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
