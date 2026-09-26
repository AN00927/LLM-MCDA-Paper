#!/usr/bin/env python3
"""
tie_rounding_check.py -- effect of rounding the weighted MAVT sum before ranking
(sentinel_utils.MAVT_ROUND_DECIMALS) on the reference rankings.

In memory only; writes tie_rounding_check.csv next to this file and nothing
else (Ground Truth/*.xlsx is not touched). No API calls.

  A. Stored reference: for every scenario in Ground Truth/ground_truth_*.xlsx,
     re-rank its stored criterion scores with the old rule (unrounded sum) and
     the new rule (apply_mavt_ranking as it is now), and compare with the stored
     rank.
  B. Shipped calculators: re-score every master scenario (105 HVAC, 100
     Appliance, 80 Shower; test and RAG) from its true parameters with the
     shipped calculators, and rank old vs new.
  C. HVAC Test scenario 58 at its true parameters, and the R = 5 counterfactual
     that exposed the problem.
  D. The shipped per-run files of all three architectures rank with each
     architecture's own weighted sum (Architectures/, not edited here): how many
     stored scenario-runs would rank differently under the rounded rule.
"""

import contextlib
import importlib.util
import io
import math
import sys
import warnings
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY, MODEL_SPECS  # noqa: E402
from sentinel_utils import (apply_mavt_ranking, has_sentinel_scores, CRITERIA,  # noqa: E402
                            read_table_clean)

# model_config.py is being repointed at the rerun's folders (P3: Gemini 3.8
# Flash, DeepSeek V4.1 Flash). The data these checks use is the shipped
# collection, so each in-process spec whose folder holds no A_H run files yet
# is redirected to the shipped folder. model_config.py itself is not touched.
SHIPPED_FOLDERS = {"gptoss": "Output Files GPT-OSS 20B", "qwen": "Output Files Qwen3.5 9B",
                   "deepseek": "Output Files DeepSeek V4 Flash",
                   "gemini": "Output Files Gemini 3.5 Flash"}
for _mk, _shipped in SHIPPED_FOLDERS.items():
    if (not list((ROOT / MODEL_SPECS[_mk]["output_folder"]).glob(
            "LLM-Parameterized_Reference_Scoring_results_run_*.xlsx"))
            and (ROOT / _shipped).exists()):
        MODEL_SPECS[_mk]["output_folder"] = _shipped


def old_rank(alts):
    """apply_mavt_ranking before the change: unrounded weighted sum."""
    valid = []
    for i, a in enumerate(alts):
        if has_sentinel_scores(a):
            continue
        ws = (CRITERION_WEIGHTS["energy_cost"] * float(a["energy_cost"])
              + CRITERION_WEIGHTS["environmental"] * float(a["environmental"])
              + CRITERION_WEIGHTS["comfort"] * float(a["comfort"])
              + CRITERION_WEIGHTS["practicality"] * float(a["practicality"]))
        if math.isnan(ws):
            continue
        valid.append((i, ws))
    valid.sort(key=lambda p: (p[1],) + tuple(float(alts[p[0]].get(c, 0.0))
                                             for c in TIE_BREAK_PRIORITY), reverse=True)
    return [alts[i]["alternative"] for i, _ in valid]


def new_rank(alts):
    return apply_mavt_ranking(alts)["ranked_alternatives"]


def exact_tie(alts):
    ws = [round(sum(CRITERION_WEIGHTS[c] * float(a[c]) for c in CRITERIA), 10) for a in alts]
    return len(set(ws)) < len(ws)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


rows = []

# A. stored reference ------------------------------------------------------
for f in ("hvac", "appliance", "shower"):
    gt = pd.read_excel(ROOT / "Ground Truth" / f"ground_truth_{f}.xlsx")
    n = n_tie = n_old_mismatch = n_new_change = 0
    changed = []
    for sid, g in gt.groupby("scenario_id", sort=True):
        alts = [{"alternative": str(r["alternative"]),
                 **{c: r[f"{c}_score"] for c in CRITERIA}} for _, r in g.iterrows()]
        stored = [str(a) for a in g.sort_values("rank")["alternative"]]
        o, nw = old_rank(alts), new_rank(alts)
        n += 1
        n_tie += exact_tie(alts)
        n_old_mismatch += (o != stored)
        if nw != stored:
            n_new_change += 1
            changed.append(f"sid {sid}: {stored} -> {nw}")
    rows += [{"check": "A_stored_reference", "decision_type": f, "metric": m, "value": v}
             for m, v in [("scenarios", n), ("exact_mavt_ties", n_tie),
                          ("old_rule_differs_from_stored", n_old_mismatch),
                          ("new_rule_changes_stored_ranking", n_new_change)]]
    for c in changed:
        rows.append({"check": "A_stored_reference", "decision_type": f,
                     "metric": "changed_scenario", "value": c})
    print(f"A {f}: {n} scenarios, {n_tie} exact ties, old rule != stored {n_old_mismatch}, "
          f"new rule changes {n_new_change}")

# B. shipped calculators on true parameters --------------------------------
hab = _load("hab", "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py")
for dt in ("HVAC", "Appliance", "Shower"):
    master = hab.load_ground_truth(dt)
    n = n_tie = n_change = n_fail = 0
    changed = []
    for idx, r in master.iterrows():
        scored = hab.score_scenario(dt, hab.build_scenario(dt, r, r, hab.true_params(r, dt)))
        if scored is None:
            n_fail += 1
            continue
        n += 1
        n_tie += exact_tie(scored)
        o, nw = old_rank(scored), new_rank(scored)
        if o != nw:
            n_change += 1
            changed.append(f"master row {idx}: {o} -> {nw}")
    rows += [{"check": "B_calculator_rescore", "decision_type": dt, "metric": m, "value": v}
             for m, v in [("scenarios", n), ("calculator_failures", n_fail),
                          ("exact_mavt_ties", n_tie), ("ranking_changes_old_to_new", n_change)]]
    for c in changed:
        rows.append({"check": "B_calculator_rescore", "decision_type": dt,
                     "metric": "changed_scenario", "value": c})
    print(f"B {dt}: {n} scenarios, {n_tie} exact ties, ranking changes {n_change}")

# C. HVAC Test scenario 58 -------------------------------------------------
test = hab.load_test_scenarios()
t58 = test[test["scenario_id"] == 58].iloc[0]
g58 = hab.match_ground_truth(t58, hab.load_ground_truth("HVAC"), "HVAC")
for label, r_value in (("true parameters", None), ("R-value = 5 counterfactual", 5.0)):
    p = hab.true_params(g58, "HVAC")
    if r_value is not None:
        p["r_value"] = r_value
    sc = hab.score_scenario("HVAC", hab.build_scenario("HVAC", t58, g58, p))
    o, nw = old_rank(sc), new_rank(sc)
    rows.append({"check": "C_hvac_test_58", "decision_type": "HVAC", "metric": label,
                 "value": f"old {o} / new {nw} / exact tie {exact_tie(sc)}"})
    print(f"C HVAC test 58, {label}: old {o}, new {nw}, exact tie {exact_tie(sc)}")

# D. stored architecture rankings (architecture code, not edited) ----------
for arch in ("LLM-Parameterized_Reference_Scoring", "Example-Guided_LLM_Scoring",
             "Direct_LLM_Scoring"):
  for mk in ("deepseek", "gemini", "gptoss", "qwen"):
    folder = ROOT / MODEL_SPECS[mk]["output_folder"]
    n = n_change = 0
    for rp in sorted(folder.glob(f"{arch}_results_run_*.xlsx")):
        df = read_table_clean(rp)
        for sid, g in df.groupby("scenario_id"):
            alts = [{"alternative": str(r["alternative"]), **{c: r[c] for c in CRITERIA}}
                    for _, r in g.iterrows()]
            if any(has_sentinel_scores(a) for a in alts):
                continue
            n += 1
            stored = [str(a) for a in g.sort_values("rank")["alternative"]]
            n_change += (new_rank(alts) != stored)
    rows.append({"check": "D_stored_arch_ranks", "decision_type": arch, "metric": f"{mk}:scenario_runs",
                 "value": n})
    rows.append({"check": "D_stored_arch_ranks", "decision_type": arch,
                 "metric": f"{mk}:rank_differs_under_rounded_rule", "value": n_change})
    print(f"D {arch} {mk}: {n} scored scenario-runs, {n_change} rank differently under the rounded rule")

pd.DataFrame(rows).to_csv(HERE / "tie_rounding_check.csv", index=False)
print(f"Wrote {HERE / 'tie_rounding_check.csv'}")
