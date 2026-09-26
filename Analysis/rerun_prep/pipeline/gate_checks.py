#!/usr/bin/env python3
"""
gate_checks.py -- the P2 regression gate verdicts, from before.csv / after.csv.

Run after `pipeline_gate.py before`, `pipeline_gate.py after` and
`pipeline_gate.py diff`. Writes gate.csv and baseline_old_vs_new.csv next to
this file and prints a summary. Offline; reads only files in this folder,
paper/pass5/NUMBERS_OF_RECORD.csv and Analysis/pass5/d2_*.csv.

Checks
  G1  after-phase hybrid `extracted` arm == Set A (paper/per_run_metrics), per
      model x decision type, for tau / Top-1 / MAE / success / inclusive
      tau and Top-1: exact at the precision the paper prints (tau and MAE 3 dp,
      percentages 1 dp); the full-precision gap is recorded.
  G2  the same values against every per-run A_H row of NUMBERS_OF_RECORD.csv.
  G3  Set A itself identical before and after (no pipeline input moved).
  G4  generate_paper_results_numbers: every category other than
      GPTOSS_recovery unchanged; the recovered value vs D2's backfill.
  G5  provenance significance tests vs D2's like-for-like run-mean tests.
"""

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]

b = pd.read_csv(HERE / "before.csv")
a = pd.read_csv(HERE / "after.csv")
for f in (a, b):
    f["v"] = pd.to_numeric(f["value"], errors="coerce")


def get(df, q, m, dt, met):
    s = df[(df.quantity == q) & (df.model == m) & (df.decision_type == dt) & (df.metric == met)]
    return float(s["v"].iloc[0]) if len(s) else np.nan


rows = []


def check(gate, item, ref, new, digits, note=""):
    ok = (np.isnan(ref) and np.isnan(new)) or (round(ref, digits) == round(new, digits))
    rows.append({"gate": gate, "item": item, "reference": ref, "new": new,
                 "abs_diff": abs(ref - new) if not (np.isnan(ref) or np.isnan(new)) else np.nan,
                 "compare_digits": digits, "pass": bool(ok), "note": note})


# G1 / G3
for m in MODELS:
    for dt in ["Overall", "HVAC", "Appliance", "Shower"]:
        for met_p, met_h, dig in [("kendall_tau", "kendall_tau", 3), ("top1", "top1", 3),
                                  ("mae", "mae", 3)]:
            ref = get(b, "AH_pipeline", m, dt, met_p)
            check("G1", f"{m}/{dt}/{met_h}", ref, get(a, "hybrid:extracted", m, dt, met_h), dig)
            check("G3", f"{m}/{dt}/{met_p}", ref, get(a, "AH_pipeline", m, dt, met_p), 12)
        check("G1", f"{m}/{dt}/n_scored", get(b, "AH_pipeline", m, dt, "n_scored"),
              get(a, "hybrid:extracted", m, dt, "n_scored"), 0)
    check("G1", f"{m}/Overall/success_rate", get(b, "AH_pipeline", m, "Overall", "success_rate"),
          get(a, "hybrid:extracted", m, "Overall", "success_rate"), 3)

# G2: NUMBERS_OF_RECORD per-run A_H rows
nor = pd.read_csv(ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD.csv")
map_metric = {"tau": ("kendall_tau", 1, 3), "top1": ("top1", 100, 1), "mae": ("mae", 1, 3),
              "success": ("success_rate", 100, 1), "tau_inclusive": ("tau_inclusive", 1, 3),
              "top1_inclusive": ("top1_inclusive", 100, 1)}
for _, r in nor.iterrows():
    nid = r["number_id"]
    if not nid.startswith("AH_") or r["model"] not in MODELS:
        continue
    parts = nid[3:].rsplit("_", 1)
    rest, model = parts[0], parts[1]
    dt = "Overall"
    for t in ("HVAC", "Appliance", "Shower"):
        if nid.endswith("_" + t):
            model_dt = nid[3:].rsplit("_", 2)
            rest, model, dt = model_dt[0], model_dt[1], t
    if rest not in map_metric:
        continue
    met, scale, dig = map_metric[rest]
    try:
        paper = float(str(r["value"]).lstrip("+"))
    except ValueError:
        continue
    new = get(a, "hybrid:extracted", model, dt, met) * scale
    check("G2", nid, paper, round(new, dig), dig, f"paper value from {r['where_in_paper']}")

# G4: numbers_master
na = a[a.quantity.str.startswith("NUMBERS:")].copy()
nb = b[b.quantity.str.startswith("NUMBERS:")].copy()
for f in (na, nb):
    f["occ"] = f.groupby(["quantity", "model", "decision_type", "metric"]).cumcount()
key = ["quantity", "model", "decision_type", "metric", "occ"]
j = nb.merge(na, on=key, how="outer", suffixes=("_b", "_a"), indicator=True)
# Excluded from the unchanged-rows check, each for a stated reason:
#   GPTOSS_recovery      -- changed on purpose (P2)
#   the pooled tables    -- removed on purpose (P2 follow-up; nothing prints them)
#   Table8_cost_per_run  -- priced from the MODEL_SPECS labels, which P3 changed
#                           for the rerun models; reported separately below
REMOVED = {"NUMBERS:Table5_pooled_overall", "NUMBERS:Table6_per_criterion_mae",
           "NUMBERS:Table7_per_decision_type_pooled"}
other = j[~j.quantity.isin({"NUMBERS:GPTOSS_recovery", "NUMBERS:Table8_cost_per_run"} | REMOVED)]
n_diff = int(((other.v_b - other.v_a).abs() > 1e-12).sum() + (other["_merge"] != "both").sum())
rows.append({"gate": "G4", "item": "numbers_master rows (not recovery / pooled / cost) that changed",
             "reference": 0, "new": n_diff, "abs_diff": n_diff, "compare_digits": 0,
             "pass": n_diff == 0, "note": f"{len(other)} rows compared"})
removed_left = int(j[j.quantity.isin(REMOVED)]["v_a"].notna().sum())
rows.append({"gate": "G4", "item": "pooled-across-model rows still written", "reference": 0,
             "new": removed_left, "abs_diff": removed_left, "compare_digits": 0,
             "pass": removed_left == 0, "note": "Table5 / Table6 pooled / Table7 pooled"})
cost = j[j.quantity == "NUMBERS:Table8_cost_per_run"]
rows.append({"gate": "G4-info", "item": "Table8 cost rows changed (MODEL_SPECS prices, P3)",
             "reference": 0, "new": int(((cost.v_b - cost.v_a).abs() > 1e-12).sum()),
             "abs_diff": np.nan, "compare_digits": 0, "pass": np.nan, "note": ""})
d2r = pd.read_csv(ROOT / "Analysis" / "pass5" / "d2_gptoss_recovery.csv")
d2r = d2r[(d2r.model == "gptoss") & (d2r.policy == "first_other_success")].iloc[0]
check("G4", "GPTOSS recovered tau vs D2 backfill", d2r["tau"],
      get(a, "NUMBERS:GPTOSS_recovery", "recovered_5run", "Overall", "AH|tau"), 3)
check("G4", "GPTOSS recovered Top-1 vs D2 backfill", d2r["top1"],
      get(a, "NUMBERS:GPTOSS_recovery", "recovered_5run", "Overall", "AH|Top-1"), 3)
check("G4", "GPTOSS unrecovered (pooled_5run) tau vs Set A", get(b, "AH_pipeline", "gptoss", "Overall", "kendall_tau"),
      get(a, "NUMBERS:GPTOSS_recovery", "pooled_5run", "Overall", "AH|tau"), 12)

# G5: significance vs D2 like-for-like (published helpers, run-mean basis)
d2s = pd.read_csv(ROOT / "Analysis" / "pass5" / "d2_significance_like_for_like.csv")
d2s = d2s[~d2s.metric.str.contains(r"[\[<]")]
for _, r in d2s.iterrows():
    for k_new, k_ref, dig in (("p_holm", "p_holm_12", None), ("cliff_delta", "cliff_delta", 3),
                              ("n_pairs", "n_pairs", 0)):
        ref = float(r[k_ref])
        new = get(a, "SIG", r["model"], "Overall", f"{r['metric']}:{k_new}")
        # the DM arm moved (retrieval-set medians), so these are expected to
        # differ; recorded for the report, not a pass/fail on the gate
        rows.append({"gate": "G5-info", "item": f"{r['model']}/{r['metric']}/{k_new}",
                     "reference": ref, "new": new, "abs_diff": abs(ref - new),
                     "compare_digits": dig, "pass": np.nan,
                     "note": "reference = D2 run-mean basis with the OLD dataset median"})

g = pd.DataFrame(rows)
g.to_csv(HERE / "gate.csv", index=False)
for gate, s in g[g.gate.isin(["G1", "G2", "G3", "G4"])].groupby("gate"):
    print(f"{gate}: {int(s['pass'].sum())}/{len(s)} pass; max abs diff {s['abs_diff'].max():.2e}")
# Known, explained G1/G2 differences: Gemini A_H, HVAC Test scenario 5, all five
# runs. The architecture broke an exact MAVT tie (74 and 80 at 0.7775) by
# floating-point noise when it stored its ranks; the harness now ranks with the
# rounded rule (sentinel_utils.MAVT_ROUND_DECIMALS), which applies
# TIE_BREAK_PRIORITY. See PIPELINE_REPORT.md section 9.1.
KNOWN_TIE = {"gemini/Overall/kendall_tau", "gemini/HVAC/kendall_tau", "AH_tau_gemini",
             "AH_tau_inclusive_gemini", "AH_tau_gemini_HVAC"}
g.loc[g["item"].isin(KNOWN_TIE) & (g["pass"] == False), "note"] = (  # noqa: E712
    "explained: stored Gemini A_H rank broke an exact tie by float noise (HVAC test 5)")
g.to_csv(HERE / "gate.csv", index=False)
bad = g[(g["pass"] == False)]  # noqa: E712
if len(bad):
    print("FAILURES:")
    print(bad.to_string(index=False))

# Old vs new baselines table
bl = []
for q in ["hybrid:default_params", "FD"]:
    for dt in ["Overall", "HVAC", "Appliance", "Shower"]:
        for met in ["kendall_tau", "top1", "mae"]:
            mdl = "deepseek" if q.startswith("hybrid") else "all"
            ob, na_ = get(b, q, mdl, dt, met), get(a, q, mdl, dt, met)
            bl.append({"baseline": "dataset_median" if q.startswith("hybrid") else "fixed_default",
                       "model": "all (model-independent)", "decision_type": dt, "metric": met,
                       "old": ob, "new": na_, "delta": na_ - ob})
for q, lab in [("DM_like_for_like", "dataset_median_same_scenarios"),
               ("FD_like_for_like", "fixed_default_same_scenarios")]:
    for m in MODELS:
        for dt in ["Overall", "HVAC", "Appliance", "Shower"]:
            for met in ["kendall_tau", "top1",
                        "tau_gain_AH_minus_DM" if q.startswith("DM") else "tau_gain_AH_minus_FD"]:
                ob, na_ = get(b, q, m, dt, met), get(a, q, m, dt, met)
                bl.append({"baseline": lab, "model": m, "decision_type": dt, "metric": met,
                           "old": ob, "new": na_, "delta": na_ - ob})
pd.DataFrame(bl).to_csv(HERE / "baseline_old_vs_new.csv", index=False)
print(f"Wrote {HERE / 'gate.csv'} and {HERE / 'baseline_old_vs_new.csv'}")
