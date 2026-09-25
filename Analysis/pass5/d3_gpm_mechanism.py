#!/usr/bin/env python3
"""
d3_gpm_mechanism.py -- Pass 5, item D3 ("the GPM mechanism").

READ-ONLY with respect to the repo: no API calls, no architecture reruns, no
edits to calculators / pipeline / outputs. Writes only Analysis/pass5/d3_*.csv.
Every metric is computed per model (and per run, then averaged over runs);
nothing is pooled across models. Failed scenario-runs (extraction_failed or a
1928 sentinel, detected via sentinel_utils.is_sentinel / has_sentinel_scores)
are excluded and never enter an average.

Sections
  0. Linearity check: within each Shower scenario, cost/alt-duration and
     gallons/alt-duration are constant (premise check, numeric).
  1. Local instrumented copy of the Shower scoring path with switches
     (clip, tank step, budget penalty, 2-dp rounding, comfort curve,
     practicality duration curve). Verified to reproduce the shipped
     calculator exactly with all switches at their shipped setting.
  2. Observed A_H extraction errors, per model x run: for each scenario and
     hidden parameter with an error, re-score with ONLY that parameter at its
     extracted value (all else true) and record whether Top-1 changes.
     P(Top-1 change | error) per run, then mean over runs.
  3. Margin bins: flip probability vs the reference winner's MAVT margin.
  4. Attribution of every observed GPM-only flip to calculator components.
  5. Controlled sweep: true GPM x factor (0.5..2.0), all else true; flip
     rates under the full model and each variant; attribution.
  6. Flip distance: for every scenario and numeric hidden parameter, the
     smallest multiplicative perturbation that changes Top-1 (0.50..2.00 grid,
     step 0.01), compared with the models' observed relative errors.
"""

import contextlib
import importlib.util
import io
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
warnings.filterwarnings("ignore")

from model_config import MODEL_SPECS, CRITERION_WEIGHTS  # noqa: E402
from sentinel_utils import (is_sentinel, has_sentinel_scores, read_table_clean,  # noqa: E402
                            apply_mavt_ranking, CRITERIA)

OUT = PROJECT_ROOT / "Analysis" / "pass5"
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DTYPES = ["HVAC", "Appliance", "Shower"]
AH = "LLM-Parameterized_Reference_Scoring"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


hab = _load("run_hybrid_ablation_experiments",
            "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py")
epe = _load("evaluate_parameter_extraction",
            "Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py")
ShowerCalc = hab.CALCULATORS["Shower"]


# ---------------------------------------------------------------------------
# Ranking helpers (the shipped MAVT rule: weighted sum of the 2-dp criterion
# scores, ties broken by TIE_BREAK_PRIORITY, sentinel alternatives excluded)
# ---------------------------------------------------------------------------
def rank(scored):
    if scored is None or any(has_sentinel_scores(a) for a in scored):
        return None
    r = apply_mavt_ranking(scored)
    if not r["ranked_alternatives"]:
        return None
    ws = sorted([w for w in r["weighted_scores"] if not is_sentinel(w)], reverse=True)
    return {"top1": r["ranked_alternatives"][0], "order": tuple(r["ranked_alternatives"]),
            "margin": ws[0] - ws[1] if len(ws) > 1 else np.nan}


def score_full(dt, scn):
    return hab.score_scenario(dt, scn)


# ---------------------------------------------------------------------------
# 1. Local instrumented copy of the Shower scoring path
# ---------------------------------------------------------------------------
FULL = dict(clip=True, tank=True, budget=True, round2=True, comfort=True, prac_curve=True)


def shower_variant(scn, flags=FULL, diag=False):
    """Local re-implementation of ShowerGroundTruthCalculator.calculate_scenario_scores
    with component switches. With flags == FULL it must equal the shipped calculator
    (checked in verify_variant). Physics sub-functions are the shipped ones."""
    c = ShowerCalc()
    occ = int(scn.get("household_size", 2))
    tank = float(scn.get("tank_size", 40))
    gpm = float(scn.get("gpm", 2.5))
    tout = float(scn.get("outdoor_temp", 50))
    wht = float(scn.get("water_heater_temp", 120))
    budget = float(scn.get("utility_budget", 0) or 0)
    out, dg = [], []
    for i in range(1, 4):
        v = scn.get(f"alternative_{i}")
        if v is None or str(v).strip().lower() in ("", "nan", "none"):
            continue
        d = float(v)
        kwh = c.calculate_shower_energy(d, gpm, wht, tout)
        cost = c.calculate_energy_cost(kwh)
        gal = c.calculate_environmental_impact(gpm, d)
        comfort = c.calculate_comfort_score(d, wht, occ, tout) if flags["comfort"] else 0.8
        # practicality: shipped curve + tank step, each switchable
        if flags["prac_curve"]:
            prac_raw_base = _prac_base(d)
        else:
            prac_raw_base = 7.0
        inlet = c.determine_inlet_temp(tout)
        hf = c.calculate_hot_water_fraction(wht, inlet, c.TARGET_SHOWER_TEMP)
        need = d * gpm * hf * occ
        tank_hit = need > tank * 0.80
        pen = 3.0 if (tank_hit and flags["tank"]) else 0.0
        prac = max(0.15, min(1.0, (prac_raw_base - pen) / 10.0))

        e_vf = _vf(c, cost, c.VF_ENERGY_COST, "energy_cost", flags["clip"])
        w_vf = _vf(c, gal, c.VF_ENVIRONMENTAL, "environmental", flags["clip"])
        c_vf = c.apply_value_function(comfort, c.VF_COMFORT, "comfort")
        p_vf = c.apply_value_function(prac, c.VF_PRACTICALITY, "practicality")
        util = np.nan
        bp = 1.0
        if budget > 0:
            monthly = c.calculate_monthly_cost(cost, occ, showers_per_person_per_day=0.9)
            util = monthly / budget
            if flags["budget"]:
                bp = c.calculate_budget_penalty(monthly, budget)
        e_vf = e_vf * bp
        vals = {"energy_cost": e_vf, "environmental": w_vf, "comfort": c_vf, "practicality": p_vf}
        if flags["round2"]:
            vals = {k: round(x, 2) for k, x in vals.items()}
        out.append({"alternative": hab._clean_text(v), **vals})
        dg.append({"duration": d, "cost": cost, "gal": gal, "tank_hit": tank_hit, "util": util,
                   "budget_regime": _regime(util),
                   "cost_clip": (cost < 0.14) or (cost > 1.14),
                   "gal_clip": (gal < 6.0) or (gal > 45.0)})
    return (out, dg) if diag else out


def _lab(v):
    f = float(v)
    return str(int(f)) if f.is_integer() else str(f)


def _prac_base(duration):
    C = ShowerCalc
    if duration <= C.COMFORT_DURATION_MIN:
        return 2.0 + (duration - 3.0) * 0.5
    if duration <= 8:
        return 3.0 + (duration - float(C.COMFORT_DURATION_MIN)) * (4.0 / 3.0)
    if duration <= 12:
        return 7.0 + (duration - 8.0) * 0.5
    if duration <= C.COMFORT_DURATION_MAX:
        return 9.0 - (duration - 12.0) * (1.5 / 3.0)
    return max(1.5, 7.5 - (duration - float(C.COMFORT_DURATION_MAX)) * 0.35)


def _vf(c, x, spec, vt, clip):
    if clip:
        return c.apply_value_function(x, spec, vt)
    ref = {"energy_cost": (0.14, 1.14), "environmental": (6.0, 45.0)}[vt]
    return (ref[1] - x) / (ref[1] - ref[0])  # linear, decreasing, no clip


def _regime(u):
    if u is None or (isinstance(u, float) and np.isnan(u)):
        return "none"
    if u < 0.8:
        return "free"
    if u < 1.0:
        return "linear"
    if u < 1.5:
        return "exp"
    return "zero"


def variant_rank(scn, flags):
    return rank(shower_variant(scn, flags))


# ---------------------------------------------------------------------------
# Scenario tables
# ---------------------------------------------------------------------------
test_df = hab.load_test_scenarios()
gt_cache = {d: hab.load_ground_truth(d) for d in hab.SCENARIO_FILES}
SC = {}
for _, row in test_df.iterrows():
    sid = int(row["scenario_id"])
    dt = hab._clean_text(row["decision_type"])
    g = hab.match_ground_truth(row, gt_cache[dt], dt)
    tp = hab.true_params(g, dt)
    scn = hab.build_scenario(dt, row, g, tp)
    ref = rank(score_full(dt, scn))
    SC[sid] = {"dt": dt, "row": row, "gt": g, "true": tp, "scn": scn, "ref": ref}
assert len(SC) == 195 and all(v["ref"] is not None for v in SC.values())
print("Loaded 195 test scenarios; reference ranking computed for all.")

SHOWER = [s for s in SC if SC[s]["dt"] == "Shower"]

# ---------------------------------------------------------------------------
# 0. Linearity check + variant verification
# ---------------------------------------------------------------------------
lin_rows = []
for s in SHOWER:
    _, dg = shower_variant(SC[s]["scn"], FULL, diag=True)
    cpd = [x["cost"] / x["duration"] for x in dg]
    gpd = [x["gal"] / x["duration"] for x in dg]
    lin_rows.append({"scenario_id": s, "gpm": SC[s]["true"]["gpm"],
                     "cost_per_min_spread": max(cpd) - min(cpd),
                     "gal_per_min_spread": max(gpd) - min(gpd),
                     "cost_per_min": cpd[0], "gal_per_min": gpd[0]})
lin = pd.DataFrame(lin_rows)
lin.to_csv(OUT / "d3_linearity_check.csv", index=False)
print(f"Linearity: max within-scenario spread of cost/min = {lin.cost_per_min_spread.max():.2e}, "
      f"gal/min = {lin.gal_per_min_spread.max():.2e}")


def _same(a, b):
    if a is None or b is None:
        return False
    ka = {x["alternative"]: x for x in a}
    kb = {x["alternative"]: x for x in b}
    if set(ka) != set(kb):
        return False
    return all(abs(float(ka[k][c]) - float(kb[k][c])) < 1e-12 for k in ka for c in CRITERIA)


n_chk, n_ok = 0, 0
for s in SHOWER:
    for f in [0.5, 0.75, 0.9, 1.0, 1.1, 1.33, 1.5, 2.0]:
        scn = dict(SC[s]["scn"])
        scn["gpm"] = SC[s]["true"]["gpm"] * f
        n_chk += 1
        n_ok += _same(score_full("Shower", scn), shower_variant(scn, FULL))
print(f"Variant check: local copy == shipped calculator in {n_ok}/{n_chk} scored scenarios")
assert n_ok == n_chk

VARIANTS = {
    "full": FULL,
    "no_clip": {**FULL, "clip": False},
    "no_tank": {**FULL, "tank": False},
    "no_budget": {**FULL, "budget": False},
    "no_round": {**FULL, "round2": False},
    "linear_core": {**FULL, "clip": False, "tank": False, "budget": False, "round2": False},
    "comfort_flat": {**FULL, "comfort": False},
    "prac_curve_flat": {**FULL, "prac_curve": False},
    "comfort_and_prac_flat": {**FULL, "comfort": False, "prac_curve": False},
}


def attribute(scn_true, scn_pert):
    """For a (true, perturbed) Shower pair, return per-variant flip flags and
    crossing diagnostics (full model)."""
    res = {}
    for name, fl in VARIANTS.items():
        a, b = variant_rank(scn_true, fl), variant_rank(scn_pert, fl)
        res[f"flip_{name}"] = (a is not None and b is not None and a["top1"] != b["top1"])
    _, d0 = shower_variant(scn_true, FULL, diag=True)
    _, d1 = shower_variant(scn_pert, FULL, diag=True)
    res["cross_tank"] = any(x["tank_hit"] != y["tank_hit"] for x, y in zip(d0, d1))
    res["cross_budget"] = any(x["budget_regime"] != y["budget_regime"] for x, y in zip(d0, d1))
    res["cross_clip"] = any((x["cost_clip"] != y["cost_clip"]) or (x["gal_clip"] != y["gal_clip"])
                            for x, y in zip(d0, d1))
    res["any_clip_active"] = any(y["cost_clip"] or y["gal_clip"] or x["cost_clip"] or x["gal_clip"]
                                 for x, y in zip(d0, d1))
    res["tank_hit_any_true"] = any(x["tank_hit"] for x in d0)
    res["budget_active_any"] = any(x["budget_regime"] not in ("free", "none") for x in d0 + d1)
    return res


def classify(r):
    """Mechanism label for a full-model flip."""
    if not r["flip_full"]:
        return "no_flip"
    if r["flip_linear_core"]:
        return "tradeoff_rate (survives with clip, tank, budget, rounding all off)"
    nec = [k for k in ("clip", "tank", "budget", "round") if not r[f"flip_no_{k}"]]
    if nec:
        return "needs_" + "+".join(nec)
    return "joint_nonlinear (no single component necessary; linear core does not flip)"


# ---------------------------------------------------------------------------
# 2. Observed A_H extraction errors, per model x run
# ---------------------------------------------------------------------------
PARAMS = {dt: hab.HIDDEN_PARAMS[dt]["numeric"] + hab.HIDDEN_PARAMS[dt]["categorical"] for dt in DTYPES}
CAT = {p for dt in DTYPES for p in hab.HIDDEN_PARAMS[dt]["categorical"]}

case_rows, run_rows, gpm_flip_rows = [], [], []
for mk in MODELS:
    folder = PROJECT_ROOT / MODEL_SPECS[mk]["output_folder"]
    for rp in sorted(folder.glob(f"{AH}_results_run_*.xlsx")):
        run = int(rp.stem.split("_run_")[-1])
        df = read_table_clean(rp)
        n_failed = 0
        for sid, grp in df.groupby("scenario_id"):
            sid = int(sid)
            if sid not in SC:
                continue
            first = grp.iloc[0]
            S = SC[sid]
            dt = S["dt"]
            # id sanity: question/location must agree with the Test sheet
            assert hab._clean_text(first["question"]) == hab._clean_text(S["row"]["question"])
            failed = (str(first.get("extraction_failed", "")).strip().lower() in {"true", "1", "yes"}
                      or any(has_sentinel_scores(r) for r in grp[CRITERIA].to_dict("records")))
            ext = None if failed else hab.extracted_params(first, dt)
            if ext is None:
                n_failed += 1
                continue
            # the full-extraction A_H result, rescored (equals the stored scores)
            ah = rank(score_full(dt, hab.build_scenario(dt, S["row"], S["gt"], ext)))
            ah_miss = ah is not None and ah["top1"] != S["ref"]["top1"]
            run_rows.append({"model": mk, "run": run, "scenario_id": sid, "decision_type": dt,
                             "ah_top1_miss": ah_miss, "ref_margin": S["ref"]["margin"]})
            for p in PARAMS[dt]:
                tv, ev = S["true"][p], ext[p]
                if p in CAT:
                    err = epe._normalize_categorical(ev, p) != epe._normalize_categorical(tv, p)
                    rel = np.nan
                else:
                    err = float(ev) != float(tv)
                    rel = (float(ev) - float(tv)) / float(tv) if float(tv) != 0 else np.nan
                flip = False
                pr = None
                if err:
                    scn = dict(S["scn"])
                    scn[p] = ev
                    pr = rank(score_full(dt, scn))
                    flip = pr is not None and pr["top1"] != S["ref"]["top1"]
                case_rows.append({"model": mk, "run": run, "scenario_id": sid, "decision_type": dt,
                                  "parameter": p, "true": tv, "extracted": ev, "rel_error": rel,
                                  "error": err, "cf_top1_change": flip,
                                  "ref_margin": S["ref"]["margin"], "ah_top1_miss": ah_miss})
                if p == "gpm" and err:
                    scn = dict(S["scn"])
                    scn["gpm"] = float(ev)
                    a = attribute(S["scn"], scn)
                    a.update({"model": mk, "run": run, "scenario_id": sid,
                              "true_gpm": tv, "extracted_gpm": ev, "rel_error": rel,
                              "ref_margin": S["ref"]["margin"], "ah_top1_miss": ah_miss,
                              "ref_top1": S["ref"]["top1"], "cf_top1": pr["top1"] if pr else ""})
                    a["mechanism"] = classify(a)
                    gpm_flip_rows.append(a)
        print(f"  {mk} run {run:02d}: {n_failed} failed scenario-runs excluded")

cases = pd.DataFrame(case_rows)
cases.to_csv(OUT / "d3_error_cases.csv", index=False)
runs_df = pd.DataFrame(run_rows)
gpmA = pd.DataFrame(gpm_flip_rows)
gpmA.to_csv(OUT / "d3_gpm_error_attribution_cases.csv", index=False)

# P(Top-1 change | error): per run, then mean over runs; also run-summed counts
pr_rows = []
for (mk, run, dt, p), g in cases.groupby(["model", "run", "decision_type", "parameter"]):
    e = g[g.error]
    pr_rows.append({"model": mk, "run": run, "decision_type": dt, "parameter": p,
                    "n_scored": len(g), "n_error": len(e), "n_flip": int(e.cf_top1_change.sum()),
                    "p_change_given_error": e.cf_top1_change.mean() if len(e) else np.nan,
                    "error_rate": len(e) / len(g) if len(g) else np.nan,
                    "median_abs_rel_error": e.rel_error.abs().median() if len(e) else np.nan,
                    "mae": (g.extracted.astype(float) - g.true.astype(float)).abs().mean()
                    if p not in CAT else np.nan})
prr = pd.DataFrame(pr_rows)
prr.to_csv(OUT / "d3_p_top1_change_per_run.csv", index=False)
psum = (prr.groupby(["model", "decision_type", "parameter"])
        .agg(p_change_mean=("p_change_given_error", "mean"),
             p_change_sd=("p_change_given_error", "std"),
             p_change_min=("p_change_given_error", "min"),
             p_change_max=("p_change_given_error", "max"),
             n_error_total=("n_error", "sum"), n_flip_total=("n_flip", "sum"),
             n_scored_total=("n_scored", "sum"),
             error_rate_mean=("error_rate", "mean"),
             median_abs_rel_error_mean=("median_abs_rel_error", "mean"),
             mae_per_run_mean=("mae", "mean"))
        .reset_index())
psum["p_change_run_summed"] = psum.n_flip_total / psum.n_error_total
PUBLISHED = {  # tab:extraction_accuracy, computed on the 5-run aggregate workbook
    ("r_value", "gptoss"): 0.015, ("r_value", "qwen"): 0.086, ("r_value", "deepseek"): 0.015, ("r_value", "gemini"): 0.000,
    ("seer", "gptoss"): 0.049, ("seer", "qwen"): 0.033, ("seer", "deepseek"): 0.032, ("seer", "gemini"): 0.075,
    ("hvac_age", "gptoss"): 0.0, ("hvac_age", "qwen"): 0.0, ("hvac_age", "deepseek"): 0.0, ("hvac_age", "gemini"): 0.0,
    ("kwh_per_cycle", "gptoss"): 0.016, ("kwh_per_cycle", "qwen"): 0.066, ("kwh_per_cycle", "deepseek"): 0.016, ("kwh_per_cycle", "gemini"): 0.031,
    ("gpm", "gptoss"): 0.174, ("gpm", "qwen"): 0.167, ("gpm", "deepseek"): 0.185, ("gpm", "gemini"): 0.233,
    ("tank_size", "gptoss"): 0.0, ("tank_size", "qwen"): 0.026, ("tank_size", "deepseek"): 0.025, ("tank_size", "gemini"): 0.0,
    ("water_heater_temp", "gptoss"): 0.042, ("water_heater_temp", "qwen"): 0.050, ("water_heater_temp", "deepseek"): 0.042, ("water_heater_temp", "gemini"): 0.050,
}
psum["published_aggregate_basis"] = [PUBLISHED.get((p, m), np.nan) for p, m in zip(psum.parameter, psum.model)]
psum.to_csv(OUT / "d3_p_top1_change_summary.csv", index=False)
print("\nP(Top-1 change | error), mean over runs (per model):")
print(psum[["model", "decision_type", "parameter", "p_change_mean", "p_change_sd",
            "n_flip_total", "n_error_total", "published_aggregate_basis"]].round(3).to_string(index=False))

# ---------------------------------------------------------------------------
# 3. Margin bins
# ---------------------------------------------------------------------------
BINS = [-1e-9, 0.005, 0.01, 0.02, 0.05, 10]
LABELS = ["[0,0.005)", "[0.005,0.01)", "[0.01,0.02)", "[0.02,0.05)", ">=0.05"]
ref_m = pd.DataFrame([{"scenario_id": s, "decision_type": SC[s]["dt"], "ref_margin": SC[s]["ref"]["margin"]}
                      for s in SC])
ref_m["margin_bin"] = pd.cut(ref_m.ref_margin, BINS, labels=LABELS, right=False)
ref_m.to_csv(OUT / "d3_reference_margins.csv", index=False)
mdist = ref_m.groupby(["decision_type", "margin_bin"]).size().unstack(fill_value=0)
print("\nReference winner margin distribution (scenarios):")
print(mdist.to_string())
print(ref_m.groupby("decision_type").ref_margin.describe().round(4).to_string())

e = cases[cases.error].copy()
e["margin_bin"] = pd.cut(e.ref_margin, BINS, labels=LABELS, right=False)
mb = (e.groupby(["model", "decision_type", "parameter", "margin_bin"])
      .agg(n_error=("cf_top1_change", "size"), n_flip=("cf_top1_change", "sum")).reset_index())
mb = mb[mb.n_error > 0]
mb["p_flip"] = mb.n_flip / mb.n_error
# any-parameter view per decision type (a scenario-run counts once: flip if any single-param cf flips)
anyp = (e.groupby(["model", "run", "scenario_id", "decision_type"])
        .agg(ref_margin=("ref_margin", "first"), any_flip=("cf_top1_change", "max")).reset_index())
anyp["margin_bin"] = pd.cut(anyp.ref_margin, BINS, labels=LABELS, right=False)
mb_any = (anyp.groupby(["model", "decision_type", "margin_bin"])
          .agg(n=("any_flip", "size"), n_flip=("any_flip", "sum")).reset_index())
mb_any = mb_any[mb_any.n > 0]
mb_any["p_flip"] = mb_any.n_flip / mb_any.n
mb.to_csv(OUT / "d3_margin_bins_by_parameter.csv", index=False)
mb_any.to_csv(OUT / "d3_margin_bins_any_parameter.csv", index=False)
# the actual A_H miss rate vs margin
runs_df["margin_bin"] = pd.cut(runs_df.ref_margin, BINS, labels=LABELS, right=False)
mb_ah = (runs_df.groupby(["model", "decision_type", "margin_bin"])
         .agg(n=("ah_top1_miss", "size"), n_miss=("ah_top1_miss", "sum")).reset_index())
mb_ah = mb_ah[mb_ah.n > 0]
mb_ah["p_miss"] = mb_ah.n_miss / mb_ah.n
mb_ah.to_csv(OUT / "d3_margin_bins_ah_top1_miss.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Observed GPM-flip attribution summary (per model; runs summed within model)
# ---------------------------------------------------------------------------
att_rows = []
for mk, g in gpmA.groupby("model"):
    f = g[g.flip_full]
    row = {"model": mk, "n_gpm_errors": len(g), "n_gpm_flips": len(f),
           "p_flip_run_summed": len(f) / len(g) if len(g) else np.nan}
    for k in ["linear_core", "no_clip", "no_tank", "no_budget", "no_round",
              "comfort_flat", "prac_curve_flat", "comfort_and_prac_flat"]:
        row[f"share_flips_surviving_{k}"] = f[f"flip_{k}"].mean() if len(f) else np.nan
    for k in ["cross_tank", "cross_budget", "cross_clip", "any_clip_active"]:
        row[f"share_flips_{k}"] = f[k].mean() if len(f) else np.nan
    row["share_flips_margin_lt_0.01"] = (f.ref_margin < 0.01).mean() if len(f) else np.nan
    row["share_flips_margin_lt_0.02"] = (f.ref_margin < 0.02).mean() if len(f) else np.nan
    row["median_margin_flips"] = f.ref_margin.median() if len(f) else np.nan
    row["median_margin_nonflips"] = g[~g.flip_full].ref_margin.median()
    row["median_abs_rel_err_flips"] = f.rel_error.abs().median() if len(f) else np.nan
    row["median_abs_rel_err_nonflips"] = g[~g.flip_full].rel_error.abs().median()
    for lab, n in f.mechanism.value_counts().items():
        row[f"mech::{lab}"] = n
    att_rows.append(row)
att = pd.DataFrame(att_rows)
att.to_csv(OUT / "d3_gpm_attribution_summary.csv", index=False)
print("\nObserved GPM-only flips, attribution (per model, 5 runs summed):")
print(att.T.to_string())

# Per-run version of the headline GPM shares (then mean over runs)
pr_att = []
for (mk, run), g in gpmA.groupby(["model", "run"]):
    f = g[g.flip_full]
    pr_att.append({"model": mk, "run": run, "n_err": len(g), "n_flip": len(f),
                   "p_flip": len(f) / len(g) if len(g) else np.nan,
                   "share_linear_core": f.flip_linear_core.mean() if len(f) else np.nan,
                   "share_cross_tank": f.cross_tank.mean() if len(f) else np.nan,
                   "share_cross_clip": f.cross_clip.mean() if len(f) else np.nan,
                   "share_cross_budget": f.cross_budget.mean() if len(f) else np.nan,
                   "share_needs_tank": (~f.flip_no_tank).mean() if len(f) else np.nan,
                   "share_needs_clip": (~f.flip_no_clip).mean() if len(f) else np.nan,
                   "share_needs_round": (~f.flip_no_round).mean() if len(f) else np.nan,
                   "share_margin_lt_0.02": (f.ref_margin < 0.02).mean() if len(f) else np.nan})
pr_att = pd.DataFrame(pr_att)
pr_att.to_csv(OUT / "d3_gpm_attribution_per_run.csv", index=False)
pr_att_mean = pr_att.groupby("model").mean(numeric_only=True).drop(columns="run").reset_index()
pr_att_mean.to_csv(OUT / "d3_gpm_attribution_per_run_mean.csv", index=False)
print("\nGPM attribution, per run then mean over runs:")
print(pr_att_mean.round(3).to_string(index=False))

# Share of the actual A_H Shower Top-1 misses that the GPM-only counterfactual reproduces
sh = cases[(cases.decision_type == "Shower")]
miss_rows = []
for (mk, run), g in sh.groupby(["model", "run"]):
    by = g.pivot_table(index="scenario_id", columns="parameter", values="cf_top1_change", aggfunc="first")
    miss = g.groupby("scenario_id").ah_top1_miss.first()
    m = miss[miss]
    miss_rows.append({"model": mk, "run": run, "n_scored": len(miss), "n_ah_miss": len(m),
                      "n_miss_gpm_only_also_flips": int(by.loc[m.index, "gpm"].fillna(False).astype(bool).sum()) if len(m) else 0,
                      "n_miss_any_single_param_flips": int(by.loc[m.index].fillna(False).astype(bool).any(axis=1).sum()) if len(m) else 0})
miss_df = pd.DataFrame(miss_rows)
miss_df.to_csv(OUT / "d3_shower_ah_miss_explained.csv", index=False)
print("\nShower A_H Top-1 misses explained by single-parameter counterfactuals (per run):")
print(miss_df.groupby("model").sum(numeric_only=True).drop(columns="run").to_string())

# ---------------------------------------------------------------------------
# 5. Controlled GPM sweep (model-free)
# ---------------------------------------------------------------------------
FACTORS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.1, 1.2, 1.25, 1.33, 1.5, 1.75, 2.0]
sw_rows = []
for s in SHOWER:
    S = SC[s]
    for f in FACTORS:
        scn = dict(S["scn"])
        scn["gpm"] = S["true"]["gpm"] * f
        a = attribute(S["scn"], scn)
        a.update({"scenario_id": s, "factor": f, "true_gpm": S["true"]["gpm"], "ref_margin": S["ref"]["margin"]})
        a["mechanism"] = classify(a)
        sw_rows.append(a)
sw = pd.DataFrame(sw_rows)
sw.to_csv(OUT / "d3_sweep_gpm_cases.csv", index=False)
sws = sw.groupby("factor").agg(
    n=("flip_full", "size"),
    flip_rate_full=("flip_full", "mean"),
    flip_rate_linear_core=("flip_linear_core", "mean"),
    flip_rate_no_clip=("flip_no_clip", "mean"),
    flip_rate_no_tank=("flip_no_tank", "mean"),
    flip_rate_no_budget=("flip_no_budget", "mean"),
    flip_rate_no_round=("flip_no_round", "mean"),
    flip_rate_comfort_flat=("flip_comfort_flat", "mean"),
    flip_rate_prac_curve_flat=("flip_prac_curve_flat", "mean"),
    flip_rate_comfort_and_prac_flat=("flip_comfort_and_prac_flat", "mean"),
).reset_index()
fl = sw[sw.flip_full]
shares = fl.groupby("factor").agg(
    n_flips=("flip_full", "size"),
    share_survive_linear_core=("flip_linear_core", "mean"),
    share_needs_tank=("flip_no_tank", lambda x: (~x).mean()),
    share_needs_clip=("flip_no_clip", lambda x: (~x).mean()),
    share_needs_budget=("flip_no_budget", lambda x: (~x).mean()),
    share_needs_round=("flip_no_round", lambda x: (~x).mean()),
    share_cross_tank=("cross_tank", "mean"),
    share_cross_clip=("cross_clip", "mean"),
    share_cross_budget=("cross_budget", "mean"),
).reset_index()
sws = sws.merge(shares, on="factor", how="left")
sws.to_csv(OUT / "d3_sweep_gpm_summary.csv", index=False)
print("\nControlled GPM sweep (60 Shower scenarios, all else true):")
print(sws.round(3).to_string(index=False))
print("\nSweep flips by mechanism (all factors):")
print(fl.mechanism.value_counts().to_string())


# ---------------------------------------------------------------------------
# 6. Flip distance for every numeric hidden parameter (model-free)
# ---------------------------------------------------------------------------
GRID = np.round(np.arange(0.50, 2.0001, 0.01), 2)
fd_rows = []
for s, S in SC.items():
    dt = S["dt"]
    for p in hab.HIDDEN_PARAMS[dt]["numeric"]:
        tv = float(S["true"][p])
        flips_dn, flips_up = [], []
        for f in GRID:
            if f == 1.0:
                continue
            scn = dict(S["scn"])
            scn[p] = tv * f
            r = rank(score_full(dt, scn))
            if r is not None and r["top1"] != S["ref"]["top1"]:
                (flips_dn if f < 1 else flips_up).append(f)
        dn = max(flips_dn) if flips_dn else np.nan
        up = min(flips_up) if flips_up else np.nan
        # distance in log units to the nearest flipping factor
        cand = [abs(math.log(x)) for x in (dn, up) if not np.isnan(x)]
        fd_rows.append({"scenario_id": s, "decision_type": dt, "parameter": p, "true": tv,
                        "nearest_flip_factor_down": dn, "nearest_flip_factor_up": up,
                        "log_flip_distance": min(cand) if cand else np.nan,
                        "ref_margin": S["ref"]["margin"]})
fdist = pd.DataFrame(fd_rows)
fdist.to_csv(OUT / "d3_flip_distance.csv", index=False)
fds = fdist.groupby(["decision_type", "parameter"]).agg(
    n=("scenario_id", "size"),
    share_flippable_within_0p5_2x=("log_flip_distance", lambda x: x.notna().mean()),
    share_flip_within_10pct=("log_flip_distance", lambda x: (x <= math.log(1.10) + 1e-9).mean()),
    share_flip_within_20pct=("log_flip_distance", lambda x: (x <= math.log(1.20) + 1e-9).mean()),
    share_flip_within_33pct=("log_flip_distance", lambda x: (x <= math.log(1.3333) + 1e-9).mean()),
    median_log_flip_distance=("log_flip_distance", "median"),
).reset_index()
fds.to_csv(OUT / "d3_flip_distance_summary.csv", index=False)
print("\nFlip distance (share of scenarios whose Top-1 flips within a +/- x% perturbation):")
print(fds.round(3).to_string(index=False))

# Relative error magnitude vs flip distance: expected P(flip | error) if error size
# were the only driver = share of observed errors whose |log(ext/true)| exceeds the
# scenario's flip distance in the error's direction (checked against observed).
print("\nDone. Outputs written to Analysis/pass5/d3_*.csv")
