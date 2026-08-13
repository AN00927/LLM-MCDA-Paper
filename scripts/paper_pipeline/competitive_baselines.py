#!/usr/bin/env python3
"""
competitive_baselines.py - task P1.5 of the EMS revision plan.

QUESTION. Does A_E beat a fixed default? The manuscript recommends A_E as the
practical option for domains where a calculator cannot be built. That
recommendation only survives if A_E beats the trivial non-LLM baselines a
practitioner already has.

WHAT THIS REPORTS, per model and per decision type:
  * A_E on Kendall's tau and Top-1 (per-run mean, then mean across runs -- the
    paper's estimator, per decision D6).
  * FixedDefault on the same two metrics. FixedDefault is deterministic and
    model-independent, so it is one column repeated against four models.
  * The single-criterion-argmax baseline per decision type: rank the three
    alternatives by ONE ground-truth criterion and score that ranking against
    the reference MAVT ranking. Also model-independent.

NULL RESULTS ARE REPORTED STRAIGHT. If A_E loses to a fixed default on a
decision type, that is the finding.

SOURCES
  A_E:            paper/per_run_metrics/per_run_metrics_all.csv
  FixedDefault:   Output Files/Baselines/baseline_metrics.csv
                  (produced by Miscellaneous Scripts/evaluate_baseline_metrics.py)
  Single-crit:    Ground Truth/ground_truth_*.xlsx, restricted to the 195 Test
                  scenarios by matching against a shipped run file, so the
                  scenario set is exactly the one the architectures were scored on.

Ties in a single-criterion ranking are broken by first occurrence, matching
paper/single_criterion_recovery.tex, so the statistic is deterministic.

Output: Analysis/competitive_baselines.xlsx (3 sheets) + .md

Usage:
    python paper_pipeline/competitive_baselines.py
"""

import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS  # noqa: E402

_cm_path = PROJECT_ROOT / "Miscellaneous Scripts" / "evaluate_architecture_metrics.py"
_cm_spec = spec_from_file_location("evaluate_architecture_metrics", _cm_path)
_cm = module_from_spec(_cm_spec)
_cm_spec.loader.exec_module(_cm)

PER_RUN_CSV = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
BASELINE_CSV = PROJECT_ROOT / "Output Files" / "Baselines" / "baseline_metrics.csv"
OUT_XLSX = PROJECT_ROOT / "Analysis" / "competitive_baselines.xlsx"
OUT_MD = PROJECT_ROOT / "Analysis" / "competitive_baselines.md"

AE = "Example-Guided_LLM_Scoring"
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]


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

def fixeddefault_by_type():
    df = pd.read_csv(BASELINE_CSV)
    df = df[df["baseline"] == "FixedDefault"]
    piv = df.pivot_table(index="decision_type", columns="metric",
                         values="value", aggfunc="first")
    out = []
    for dt in DECISION_TYPES + ["Overall_pooled"]:
        if dt not in piv.index:
            continue
        out.append({
            "decision_type": "Overall" if dt == "Overall_pooled" else dt,
            "FD_tau": float(piv.loc[dt, "kendall_tau"]),
            "FD_top1": float(piv.loc[dt, "top1_accuracy"]),
        })
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Single-criterion argmax baseline, on the 195 Test scenarios
# ---------------------------------------------------------------------------

def _rank_desc_first_occurrence(values):
    """Rank 1 = largest. Ties broken by first occurrence (stable), so the
    ranking is deterministic and matches single_criterion_recovery.tex."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    ranks = [0] * len(values)
    for pos, i in enumerate(order):
        ranks[i] = pos + 1
    return ranks


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
                pred = _rank_desc_first_occurrence(vals)
                taus.append(_tau(gt_ranks, pred))
                gt_win = sc.iloc[int(np.argmin(gt_ranks))]["norm_alternative"]
                pred_win = sc.iloc[int(np.argmin(pred))]["norm_alternative"]
                top1s.append(1.0 if gt_win == pred_win else 0.0)
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
    warnings.filterwarnings("ignore")
    print("P1.5 competitive baselines")
    print("=" * 64)

    ae = ae_by_type()
    fd = fixeddefault_by_type()
    print(f"  A_E cells: {len(ae)}")
    print(f"  FixedDefault rows: {len(fd)}")

    ref = test_reference_table()
    sc = single_criterion_baseline(ref)
    print(f"  Single-criterion rows: {len(sc)}")

    head = ae.merge(fd, on="decision_type", how="left")
    head["d_tau"] = head["AE_tau"] - head["FD_tau"]
    head["d_top1"] = head["AE_top1"] - head["FD_top1"]
    head["AE_beats_FD_tau"] = head["d_tau"] > 0
    head["AE_beats_FD_top1"] = head["d_top1"] > 0
    order = {"Overall": 0, "HVAC": 1, "Appliance": 2, "Shower": 3}
    head = head.sort_values(["model", "decision_type"],
                            key=lambda s: s.map(order) if s.name == "decision_type" else s)

    # Best single criterion per decision type, for the summary table.
    best = (sc.sort_values("SC_top1", ascending=False)
              .groupby("decision_type", as_index=False).first()
              .rename(columns={"criterion": "best_criterion",
                               "SC_tau": "best_SC_tau",
                               "SC_top1": "best_SC_top1"}))

    OUT_XLSX.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        head.to_excel(xw, sheet_name="AE_vs_FixedDefault", index=False)
        sc.to_excel(xw, sheet_name="SingleCriterionArgmax", index=False)
        best.to_excel(xw, sheet_name="BestSingleCriterion", index=False)
    print(f"  Wrote {OUT_XLSX.relative_to(PROJECT_ROOT)}")

    lines = []
    lines.append("# P1.5 - competitive baselines\n")
    lines.append("Estimator: per-run mean, then mean across runs (aggregation A, decision D6).")
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

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")

    print("\n" + "\n".join(lines[6:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
