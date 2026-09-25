#!/usr/bin/env python3
"""
d3_other_params_tradeoff.py -- Pass 5, D3 follow-up.

For every OBSERVED single-parameter counterfactual flip on HVAC and Appliance
(rows of d3_error_cases.csv with cf_top1_change == True), re-score true vs
perturbed with (a) the budget penalty switched off, (b) Comfort and
Practicality held constant across alternatives, and report whether the flip
survives. Uses subclasses of the shipped calculators (local, in-memory only);
no repo file is modified. Per model, runs summed within model; never pooled
across models. Writes Analysis/pass5/d3_other_params_tradeoff.csv.
"""
import contextlib
import importlib.util
import io
import sys
import warnings
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
warnings.filterwarnings("ignore")
from sentinel_utils import apply_mavt_ranking, has_sentinel_scores  # noqa: E402

OUT = PROJECT_ROOT / "Analysis" / "pass5"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


hab = _load("run_hybrid_ablation_experiments",
            "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py")
ORIG = dict(hab.CALCULATORS)


def make(dt, flat=False, no_budget=False):
    base = ORIG[dt]

    class V(base):
        pass
    if flat:
        V.calculate_comfort_score = lambda self, *a, **k: 0.8
        V.calculate_practicality_score = lambda self, *a, **k: 0.8
    if no_budget:
        V.calculate_budget_penalty = lambda self, *a, **k: 1.0
    return V


def top1(dt, scn, cls):
    hab.CALCULATORS[dt] = cls
    try:
        s = hab.score_scenario(dt, scn)
    finally:
        hab.CALCULATORS[dt] = ORIG[dt]
    if s is None or any(has_sentinel_scores(a) for a in s):
        return None
    r = apply_mavt_ranking(s)
    return r["ranked_alternatives"][0] if r["ranked_alternatives"] else None


test_df = hab.load_test_scenarios()
gt_cache = {d: hab.load_ground_truth(d) for d in hab.SCENARIO_FILES}
cases = pd.read_csv(OUT / "d3_error_cases.csv", keep_default_na=False)
cases["cf_top1_change"] = cases["cf_top1_change"].astype(str) == "True"
flips = cases[cases.cf_top1_change & cases.decision_type.isin(["HVAC", "Appliance"])]

rows = []
for _, c in flips.iterrows():
    row = test_df[test_df.scenario_id == int(c.scenario_id)].iloc[0]
    dt = c.decision_type
    g = hab.match_ground_truth(row, gt_cache[dt], dt)
    tp = hab.true_params(g, dt)
    s0 = hab.build_scenario(dt, row, g, tp)
    s1 = dict(s0)
    v = c.extracted
    try:
        v = float(v)
    except ValueError:
        pass
    s1[c.parameter] = v
    out = {"model": c.model, "run": c.run, "scenario_id": c.scenario_id, "decision_type": dt,
           "parameter": c.parameter, "true": c["true"], "extracted": c.extracted,
           "ref_margin": float(c.ref_margin)}
    for name, cls in [("full", ORIG[dt]), ("no_budget", make(dt, no_budget=True)),
                      ("comfort_prac_flat", make(dt, flat=True))]:
        a, b = top1(dt, s0, cls), top1(dt, s1, cls)
        out[f"flip_{name}"] = (a is not None and b is not None and a != b)
    rows.append(out)
d = pd.DataFrame(rows)
d.to_csv(OUT / "d3_other_params_tradeoff.csv", index=False)
assert d.flip_full.all(), "full-model re-run must reproduce every recorded flip"
summ = (d.groupby(["model", "decision_type", "parameter"])
        .agg(n_flips=("flip_full", "size"),
             share_survive_no_budget=("flip_no_budget", "mean"),
             share_survive_comfort_prac_flat=("flip_comfort_prac_flat", "mean"),
             median_margin=("ref_margin", "median"))
        .reset_index())
summ.to_csv(OUT / "d3_other_params_tradeoff_summary.csv", index=False)
print(summ.round(3).to_string(index=False))
