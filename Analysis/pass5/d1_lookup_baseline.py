#!/usr/bin/env python3
"""
d1_lookup_baseline.py -- Pass 5, item D1: a non-LLM "label-lookup / text-parse"
baseline for LLM-parameterized reference scoring (A_H).

READ-ONLY with respect to the repository: imports the reference calculators and
the hybrid-ablation harness without modifying them, makes no API calls, runs no
architecture, and writes only under Analysis/pass5/ (prefix d1_). Every metric
that involves an LLM is computed per model; nothing is pooled across models.
Failed A_H scenario-runs (sentinel 1928, detected by sentinel_utils.is_sentinel
inside the harness) are excluded run by run and never enter an average.

Sections
  0. Harness checks
     0a. True parameters -> reference scores equal Ground Truth/ground_truth_*.xlsx
     0b. Fixed default (FD) through the harness reproduces the published FD
         numbers (Output Files/Baselines/baseline_metrics.csv) scenario by scenario
     0c. Dataset median (DM) through the harness reproduces the published
         default_params arm (hybrid_ablation_summary.xlsx) scenario by scenario
  1. Non-LLM baselines (model-free): FD, DM, FD+time, LU (rule), LU-literal,
     LU-corpus, plus single-component ablations of LU.
  2. A_H (numbers of record: per-run arm, failed rows dropped) vs baselines:
     like-for-like gain per model per decision type, and paired Wilcoxon /
     Cliff's delta / Holm on per-scenario run means (same helpers as the paper).
  3. Where the LLM adds value beyond lookup: parameter swap analysis and
     parameter-level accuracy (LLM vs lookup vs truth).
"""

import contextlib
import importlib.util
import io
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
warnings.filterwarnings("ignore")

from model_config import MODEL_SPECS  # noqa: E402
from sentinel_utils import (  # noqa: E402
    appliance_age_to_band_label, gpm_to_flow_rate_label, house_age_to_band_label,
    is_sentinel, read_table_clean,
)

OUT = PROJECT_ROOT / "Analysis" / "pass5"
OUT.mkdir(parents=True, exist_ok=True)
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DTYPES = ["HVAC", "Appliance", "Shower"]
CRIT = ["energy_cost", "environmental", "comfort", "practicality"]
AH = "LLM-Parameterized_Reference_Scoring"
REFERENCE_YEAR = 2026  # scenario-construction year; used only for the SEER rule


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


hab = _load("run_hybrid_ablation_experiments",
            "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py")
rag = _load("run_rag_ablation_experiments",
            "Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py")


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


test_df = hab.load_test_scenarios()          # scenario_id = 1..195 (Test row order)
gt_cache = {d: hab.load_ground_truth(d) for d in DTYPES}   # master scenario sheets
DM = hab.compute_defaults()

SC = {}  # sid -> dict(row, dt, gt_row, ref_scored)
for _, row in test_df.iterrows():
    sid = int(row["scenario_id"])
    dt = hab._clean_text(row["decision_type"])
    g = hab.match_ground_truth(row, gt_cache[dt], dt)
    assert g is not None, f"unmatched scenario {sid}"
    ref = quiet(hab.score_scenario, dt, hab.build_scenario(dt, row, g, hab.true_params(g, dt)))
    SC[sid] = {"row": row, "dt": dt, "g": g, "ref": ref}
print(f"Loaded {len(SC)} Test scenarios; all matched to their master rows.")


def score(sid, params):
    s = SC[sid]
    scored = quiet(hab.score_scenario, s["dt"], hab.build_scenario(s["dt"], s["row"], s["g"], params))
    return hab.scenario_metrics(scored, s["ref"])


# ---------------------------------------------------------------------------
# Parsers and lookup rules
# ---------------------------------------------------------------------------
def parse_appliance_type(q):
    """Identical rule to the fixed-default baseline (run_baseline_models.py):
    'dishwasher' is tested before 'washer' because it contains it."""
    ql = str(q).lower()
    if "dishwasher" in ql:
        return "dishwasher"
    if "dryer" in ql:
        return "dryer"
    return "washing_machine"


FD_KWH = {"washing_machine": 0.55, "dryer": 2.10, "dishwasher": 1.00}


def parse_clock_time(q):
    """Clock time the question states ('It's around 2 in the afternoon',
    'just past 5 PM', 'just past midnight'). Returns 'H:00 AM/PM' or None."""
    ql = str(q).lower()
    if "midnight" in ql:
        return "12:00 AM"
    if re.search(r"noon", ql):  # word boundary: 'afternoon' contains 'noon'
        return "12:00 PM"
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", ql)
    if m:
        return f"{int(m.group(1))}:00 {m.group(3).upper()}"
    m = re.search(r"\b(\d{1,2})\b", ql)
    if not m:
        return None
    h = int(m.group(1))
    if not 1 <= h <= 12:
        return None
    if "morning" in ql:
        mer = "AM"
    elif "afternoon" in ql or "evening" in ql:
        mer = "PM"
    elif "night" in ql:
        mer = "PM" if 6 <= h <= 11 else "AM"
    else:
        return None
    return f"{h}:00 {mer}"


PRESENT = ["not going anywhere", "not going out", "not planning to leave", "staying",
           "stay in", "home all day", "home for the day", "at home", "working from home",
           "around all day", "sticking around", "home and"]
SLEEP = ["overnight", "bed", "turn in", "for the night", "calling it a night"]
SHORT_AWAY = ["a bit", "few hours", "couple hours", "couple of hours", "short while", "quick"]
AWAY = ["gone", " out", "away", "leaving", "not home"]


def parse_occupancy(q):
    """Occupancy context from the question wording. Written by hand from the
    question templates; unstated absences get 8 h, the calculator's own
    default for an 'unoccupied' context with no hours."""
    ql = " " + str(q).lower()
    if any(k in ql for k in SLEEP):
        return "occupied_sleep"
    if any(k in ql for k in PRESENT):
        return "occupied_all_day"
    if any(k in ql for k in SHORT_AWAY):
        return "unoccupied_4hr"
    if any(k in ql for k in AWAY):
        return "unoccupied_8hr"
    return "occupied_all_day"


def band_bounds(label):
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)", str(label))
    return (int(m.group(1)), int(m.group(2))) if m else None


def band_mid(label):
    b = band_bounds(label)
    return (b[0] + b[1]) / 2.0 if b else np.nan


# Insulation tier -> R-value ranges stated in the supplement (Parameter Ranges
# and Band Labels): Poor R-8..R-12, Medium R-13..R-18, Good R-19..R-24.
R_MID = {"Poor": 10.0, "Medium": 15.5, "Good": 21.5}
# flow_rate label -> GPM band. Edges from sentinel_utils.gpm_to_flow_rate_label
# (low <= 2.0 < standard <= 3.0 < high); outer edges from the audited GPM range
# of the scenario data (1.0-5.0, Scenario Files/build_consolidated_scenario_workbooks.py).
GPM_BANDS = {"low_flow": (1.0, 2.0), "standard": (2.0, 3.0), "high_flow": (3.0, 5.0)}
GPM_MID = {k: (a + b) / 2 for k, (a, b) in GPM_BANDS.items()}
# check the edges against the shared helper
for lab, (a, b) in GPM_BANDS.items():
    assert gpm_to_flow_rate_label(b) == lab and gpm_to_flow_rate_label((a + b) / 2) == lab


def seer_from_install_year(year):
    """U.S. federal minimum SEER for a split central AC in the North region
    (Pennsylvania) in force at installation: none before 1992 (the supplement
    places pre-1992 units at SEER 8-10; midpoint 9), 10 from 1992, 13 from
    2006, SEER2 13.4 (~SEER 14) from 2023."""
    if year < 1992:
        return 9.0
    if year < 2006:
        return 10.0
    if year < 2023:
        return 13.0
    return 14.0


def hvac_from_house_band(label):
    """Original-equipment assumption: equipment age = house-age band midpoint,
    capped at A_H's own validation bound (60 yr)."""
    b = band_bounds(label)
    assert b is not None and house_age_to_band_label(b[0]) == str(label).strip(), label
    age = min((b[0] + b[1]) / 2.0, 60.0)
    return age, seer_from_install_year(REFERENCE_YEAR - age)


# ---- RAG-corpus conditional lookups (disjoint from Test) --------------------
def _rag(name):
    df = read_table_clean(PROJECT_ROOT / "Scenario Files" / name)
    return df.drop_duplicates(subset=["scenario_id"])


rag_h, rag_a, rag_s = _rag("HVACRagScenarios.xlsx"), _rag("ApplianceRAGScenarios.xlsx"), _rag("ShowerRAGScenarios.xlsx")
rag_h["band"] = rag_h["house_age"].map(house_age_to_band_label)
rag_a["band"] = rag_a["appliance_age"].map(appliance_age_to_band_label)
CORPUS = {
    "r_by_ins": rag_h.groupby("insulation")["r_value"].median().to_dict(),
    "seer_by_band": rag_h.groupby("band")["seer"].median().to_dict(),
    "hage_by_band": rag_h.groupby("band")["hvac_age"].median().to_dict(),
    "seer_all": rag_h["seer"].median(), "hage_all": rag_h["hvac_age"].median(),
    "kwh_by_type_band": rag_a.groupby(["appliance", "band"])["kwh_per_cycle"].median().to_dict(),
    "kwh_by_type": rag_a.groupby("appliance")["kwh_per_cycle"].median().to_dict(),
    "gpm_by_flow": rag_s.groupby("flow_rate")["gpm"].median().to_dict(),
    "tank_by_hh": rag_s.groupby("household_size")["tank_size"].median().to_dict(),
    "tank_all": rag_s["tank_size"].median(), "wht_all": rag_s["water_heater_temp"].median(),
}
CORPUS_FALLBACKS = []


def corpus_hvac(band):
    if band in CORPUS["seer_by_band"]:
        return CORPUS["hage_by_band"][band], CORPUS["seer_by_band"][band]
    # nearest populated band by midpoint
    mids = {b: band_mid(b) for b in CORPUS["seer_by_band"]}
    near = min(mids, key=lambda b: abs(mids[b] - band_mid(band)))
    CORPUS_FALLBACKS.append(("HVAC house_age band", band, near))
    return CORPUS["hage_by_band"][near], CORPUS["seer_by_band"][near]


def corpus_kwh(app, band):
    if (app, band) in CORPUS["kwh_by_type_band"]:
        return CORPUS["kwh_by_type_band"][(app, band)]
    CORPUS_FALLBACKS.append(("Appliance type x age band", f"{app} {band}", "type median"))
    return CORPUS["kwh_by_type"][app]


def corpus_tank(hh):
    hh = int(hh)
    if hh in CORPUS["tank_by_hh"]:
        return CORPUS["tank_by_hh"][hh]
    CORPUS_FALLBACKS.append(("Shower household size", hh, "overall median"))
    return CORPUS["tank_all"]


# ---------------------------------------------------------------------------
# Parameter builders. Each returns exactly the hidden-parameter dict A_H's LLM
# must return (hab.HIDDEN_PARAMS); homeowner fields come from the sheet.
# Component switches let us add or remove one rule at a time.
# ---------------------------------------------------------------------------
LU_COMPONENTS = {
    "HVAC": ["r_mid", "house_age_rule", "occupancy_parse"],
    "Appliance": ["time_parse"],
    "Shower": ["gpm_mid"],
}


def params_for(sid, comps, source="rule", gpm_map=None):
    """comps: set of component names switched on; everything else = FD."""
    s = SC[sid]
    row, dt = s["row"], s["dt"]
    q = hab._clean_text(row["question"])
    if dt == "HVAC":
        p = {"r_value": 15.0, "seer": 13.0, "hvac_age": 13.0, "occupancy_context": "occupied_all_day"}
        ins = hab._clean_text(row["insulation"])
        band = hab._clean_text(row["house_age"])
        if "r_mid" in comps:
            p["r_value"] = R_MID[ins] if source == "rule" else float(CORPUS["r_by_ins"][ins])
        if "house_age_rule" in comps:
            a, sr = hvac_from_house_band(band) if source == "rule" else corpus_hvac(band)
            p["hvac_age"], p["seer"] = float(a), float(sr)
        if "occupancy_parse" in comps:
            p["occupancy_context"] = parse_occupancy(q)
        return p
    if dt == "Appliance":
        app = parse_appliance_type(q)
        p = {"appliance": app, "kwh_per_cycle": FD_KWH[app], "baseline_time": "7pm"}
        if "time_parse" in comps:
            t = parse_clock_time(q)
            if t is not None:
                p["baseline_time"] = t
        if source == "corpus" and "kwh_corpus" in comps:
            p["kwh_per_cycle"] = float(corpus_kwh(app, hab._clean_text(row["appliance_age"])))
        return p
    # Shower
    p = {"gpm": 2.5, "tank_size": 50.0, "water_heater_temp": 120.0}
    fl = hab._clean_text(row["flow_rate"])
    if "gpm_mid" in comps:
        p["gpm"] = (gpm_map or GPM_MID)[fl] if source == "rule" else float(CORPUS["gpm_by_flow"][fl])
    if source == "corpus" and "tank_corpus" in comps:
        p["tank_size"] = float(corpus_tank(row["household_size"]))
        p["water_heater_temp"] = float(CORPUS["wht_all"])
    return p


ALL_RULE = {c for v in LU_COMPONENTS.values() for c in v}
ALL_CORPUS = ALL_RULE | {"kwh_corpus", "tank_corpus"}

BASELINES = {
    "FD": lambda sid: params_for(sid, set()),
    "DM": lambda sid: dict(DM[SC[sid]["dt"]]),
    "FD+time": lambda sid: params_for(sid, {"time_parse"}),
    "LU": lambda sid: params_for(sid, ALL_RULE),
    "LU-literal": lambda sid: params_for(sid, {"r_mid", "house_age_rule", "time_parse", "gpm_mid"}),
    "LU-corpus": lambda sid: params_for(sid, ALL_CORPUS, source="corpus"),
}
# GPM-midpoint sensitivity: the supplement describes 'standard' as 2.5-3.0 GPM
# (midpoint 2.75) and the high band has no stated upper edge (3.5 = lower half).
BASELINES["LU[gpm std=2.75]"] = lambda sid: params_for(sid, ALL_RULE, gpm_map={**GPM_MID, "standard": 2.75})
BASELINES["LU[gpm high=3.5]"] = lambda sid: params_for(sid, ALL_RULE, gpm_map={**GPM_MID, "high_flow": 3.5})
for dt, comps in LU_COMPONENTS.items():
    for c in comps:
        BASELINES[f"FD+{c}"] = (lambda cc: (lambda sid: params_for(sid, {cc})))(c)
        BASELINES[f"LU-{c}"] = (lambda cc: (lambda sid: params_for(sid, ALL_RULE - {cc})))(c)


# ---------------------------------------------------------------------------
# 0. Harness checks
# ---------------------------------------------------------------------------
print("\n=== 0a. True parameters reproduce Ground Truth/ground_truth_*.xlsx ===")
GT_FILES = {"HVAC": "ground_truth_hvac.xlsx", "Appliance": "ground_truth_appliance.xlsx",
            "Shower": "ground_truth_shower.xlsx"}


def norm_alt(a, dt):
    a = str(a).strip()
    if dt == "Appliance":
        m = re.search(r"(\d{1,2}):?(\d{2})?\s*([AaPp][Mm])", a)
        return f"{int(m.group(1))}:{m.group(2) or '00'} {m.group(3).upper()}" if m else a.upper()
    try:
        v = float(a)
        return str(int(v)) if v.is_integer() else str(v)
    except ValueError:
        return a.lower()


gtx = {dt: read_table_clean(PROJECT_ROOT / "Ground Truth" / f, keep_str_cols=["alternative", "question", "location"])
       for dt, f in GT_FILES.items()}
chk_rows = []
for sid, s in SC.items():
    dt = s["dt"]
    g = gtx[dt]
    cand = g[(g["question"].map(hab._clean_text) == hab._clean_text(s["g"]["question"]))
             & (g["location"].map(hab._clean_text) == hab._clean_text(s["g"]["location"]))]
    alts = {norm_alt(a, dt) for a in [s["row"][f"alternative_{i}"] for i in (1, 2, 3)]}
    # a (question, location) pair can repeat in the master; keep the gt scenario whose alternatives match
    best = None
    for gid, grp in cand.groupby("scenario_id"):
        same_fields = all(float(grp[k].iloc[0]) == float(s["row"][k])
                          for k in ("household_size", "utility_budget") if k in grp.columns)
        if {norm_alt(a, dt) for a in grp["alternative"]} == alts and same_fields:
            best = grp
            break
    if best is None:
        chk_rows.append({"scenario_id": sid, "decision_type": dt, "matched": False})
        continue
    by = {norm_alt(r["alternative"], dt): r for _, r in best.iterrows()}
    ref = {norm_alt(a["alternative"], dt): a for a in s["ref"]}
    # rank from the harness reference
    rr = hab.apply_mavt_ranking(s["ref"]) if hasattr(hab, "apply_mavt_ranking") else None
    ref_rank = {norm_alt(a["alternative"], dt): rk for a, rk in zip(s["ref"], rr["ranks"])}
    d = max(abs(float(ref[k][c]) - float(by[k][f"{c}_score"])) for k in ref for c in CRIT)
    rk_ok = all(int(ref_rank[k]) == int(by[k]["rank"]) for k in ref)
    chk_rows.append({"scenario_id": sid, "decision_type": dt, "matched": True,
                     "max_abs_score_diff": d, "ranks_identical": rk_ok})
gtchk = pd.DataFrame(chk_rows)
gtchk.to_csv(OUT / "d1_check_true_params_vs_ground_truth.csv", index=False)
print(gtchk.groupby("decision_type").agg(n=("scenario_id", "size"), matched=("matched", "sum"),
                                         max_diff=("max_abs_score_diff", "max"),
                                         ranks_identical=("ranks_identical", "sum")).to_string())


# ---------------------------------------------------------------------------
# 1. Baselines, per scenario
# ---------------------------------------------------------------------------
print("\n=== 1. Non-LLM baselines (model-free) ===")
base_rows = []
param_rows = []
for name, fn in BASELINES.items():
    for sid in SC:
        p = fn(sid)
        m = score(sid, p)
        base_rows.append({"baseline": name, "scenario_id": sid, "decision_type": SC[sid]["dt"],
                          "failed": m is None, **(m or {"kendall_tau": np.nan, "top1": np.nan, "mae": np.nan})})
        if name in ("FD", "FD+time", "LU", "LU-literal", "LU-corpus", "DM"):
            param_rows.append({"baseline": name, "scenario_id": sid, "decision_type": SC[sid]["dt"],
                               **{f"p_{k}": v for k, v in p.items()}})
base = pd.DataFrame(base_rows)
base.to_csv(OUT / "d1_baseline_per_scenario.csv", index=False)
pd.DataFrame(param_rows).to_csv(OUT / "d1_baseline_params.csv", index=False)
assert not base["failed"].any(), "a baseline scenario failed in the calculator"


def summarize(df, keys):
    out = []
    for k, g in df.groupby(keys):
        for dt in ["Overall"] + DTYPES:
            x = g if dt == "Overall" else g[g.decision_type == dt]
            out.append({**dict(zip(keys if isinstance(keys, list) else [keys], k if isinstance(k, tuple) else (k,))),
                        "decision_type": dt, "tau": x.kendall_tau.mean(), "top1": x.top1.mean(),
                        "mae": x.mae.mean(), "n": len(x)})
    return pd.DataFrame(out)


bsum = summarize(base, ["baseline"])
bsum.to_csv(OUT / "d1_baseline_summary.csv", index=False)
wide = bsum.pivot_table(index="baseline", columns="decision_type", values=["tau", "top1", "mae"])
print(wide.round(3).to_string())

# 0b / 0c scenario-by-scenario reproduction of published FD and DM
print("\n=== 0b. FD through harness vs published FD (baseline_fixeddefault.xlsx pipeline) ===")
bm = pd.read_csv(PROJECT_ROOT / "Output Files/Baselines/baseline_metrics.csv")
fdpub = bm[bm.baseline == "FixedDefault"]
for dt, key in [("HVAC", "HVAC"), ("Appliance", "Appliance"), ("Shower", "Shower"), ("Overall", "Overall_pooled")]:
    b = bsum[(bsum.baseline == "FD") & (bsum.decision_type == dt)].iloc[0]
    pt = fdpub[(fdpub.decision_type == key) & (fdpub.metric == "kendall_tau")].value.iloc[0]
    p1 = fdpub[(fdpub.decision_type == key) & (fdpub.metric == "top1_accuracy")].value.iloc[0]
    pm = fdpub[(fdpub.decision_type == key) & (fdpub.metric == "overall_MAE")].value.iloc[0]
    print(f"  {dt:9s} harness tau {b.tau:.4f} top1 {b.top1:.4f} mae {b.mae:.4f} | published tau {pt:.4f} top1 {p1:.4f} mae {pm:.4f}")

print("\n=== 0c. DM through harness vs published default_params arm ===")
ps = pd.read_excel(PROJECT_ROOT / "Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx", sheet_name="per_scenario")
ps["failed"] = ps["failed"].astype(bool)
dmp = ps[(ps.model == "gemini") & (ps.arm == "default_params")].set_index("scenario_id")
dmh = base[base.baseline == "DM"].set_index("scenario_id")
dd = {m: float((dmh[m] - dmp.loc[dmh.index, m]).abs().max()) for m in ["kendall_tau", "top1", "mae"]}
print("  max |harness - published| per scenario:", {k: f"{v:.2e}" for k, v in dd.items()})

# FD scenario-by-scenario vs the pipeline-computed FD (same as D2's fd_by_q)
cm = _load("evaluate_architecture_metrics", "Miscellaneous Scripts/core-automation/evaluate_architecture_metrics.py")
fd_df = pd.read_excel(PROJECT_ROOT / "Output Files/Baselines/baseline_fixeddefault.xlsx")
fd_df = fd_df.rename(columns={f"{c}_score": c for c in CRIT})
for col in ("question", "location", "alternative"):
    fd_df[col] = fd_df[col].astype(str).str.strip()
cfg = cm._build_config("gemini")
gt = quiet(cm.load_ground_truth, cfg)
fd_arch = quiet(cm.load_architecture, fd_df, "FixedDefault")
fd_m, _ = quiet(cm.match_scenarios, cm.build_gt_lookup(gt), cm.build_gt_id_lookup(gt), fd_arch, "FixedDefault")
fd_clean, _, _ = cm.filter_failed_scenarios(fd_m)
import scipy.stats as stats  # noqa: E402
fd_pipe = {}
for asid in fd_clean["arch_scenario_id"].unique():
    sc = fd_clean[fd_clean["arch_scenario_id"] == asid]
    gt_r, ar_r = sc["gt_rank"].astype(float).values, sc["arch_rank"].astype(float).values
    t = stats.kendalltau(gt_r, ar_r)[0] if len(set(gt_r)) > 1 and len(set(ar_r)) > 1 else float(np.array_equal(gt_r, ar_r))
    g1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
    a1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
    fd_pipe[int(asid) + 1] = (t, float(g1 == a1))
fdh = base[base.baseline == "FD"].set_index("scenario_id")
dtau = max(abs(fdh.loc[s, "kendall_tau"] - v[0]) for s, v in fd_pipe.items())
dtop = max(abs(fdh.loc[s, "top1"] - v[1]) for s, v in fd_pipe.items())
print(f"  FD per-scenario vs pipeline: n={len(fd_pipe)}, max |d tau|={dtau:.2e}, max |d top1|={dtop:.2e}")
pd.DataFrame([{"check": "FD_vs_pipeline_per_scenario", "n": len(fd_pipe), "max_abs_dtau": dtau, "max_abs_dtop1": dtop},
              {"check": "DM_vs_published_per_scenario", "n": len(dmh), "max_abs_dtau": dd["kendall_tau"],
               "max_abs_dtop1": dd["top1"], "max_abs_dmae": dd["mae"]}]).to_csv(OUT / "d1_check_fd_dm_repro.csv", index=False)

# parser accuracy against the true (master) values
acc = []
hcal = hab.CALCULATORS["HVAC"]()
for sid, s in SC.items():
    q = hab._clean_text(s["row"]["question"])
    if s["dt"] == "Appliance":
        t = parse_clock_time(q)
        tr = hab._clean_text(s["g"]["baseline_time"])
        acc.append({"param": "baseline_time", "scenario_id": sid, "parsed": t, "true": tr,
                    "match": (t is not None) and hab.CALCULATORS["Appliance"]()._parse_time_to_hour(t)
                    == quiet(hab.CALCULATORS["Appliance"]()._parse_time_to_hour, tr)})
    if s["dt"] == "HVAC":
        o = parse_occupancy(q)
        tr = hab._clean_text(s["g"]["occupancy_context"])
        acc.append({"param": "occupancy_context", "scenario_id": sid, "parsed": o, "true": tr,
                    "match": hcal.normalize_occupancy_context(o) == hcal.normalize_occupancy_context(tr)})
acc = pd.DataFrame(acc)
acc.to_csv(OUT / "d1_parser_accuracy.csv", index=False)
print("\nParser accuracy vs truth:")
print(acc.groupby("param")["match"].agg(["sum", "size", "mean"]).to_string())
print("Corpus lookup fallbacks:", sorted(set(map(str, CORPUS_FALLBACKS))))


# ---------------------------------------------------------------------------
# 2. A_H vs baselines
# ---------------------------------------------------------------------------
print("\n=== 2. A_H (per-run, numbers of record) vs baselines ===")
pr_all = ps[(ps.arm == "extracted_per_run")].copy()
bidx = {b: base[base.baseline == b].set_index("scenario_id") for b in base.baseline.unique()}
COMPARE = ["FD", "DM", "FD+time", "LU", "LU-literal", "LU-corpus"]

gain_rows = []
for mk in MODELS:
    pr = pr_all[pr_all.model == mk]
    for dt in ["Overall"] + DTYPES:
        per_run = []
        for run, g in pr.groupby("source_run"):
            g = g if dt == "Overall" else g[g.decision_type == dt]
            ok = g[~g.failed]
            sids = ok.scenario_id.values
            rec = {"run": run, "n_scored": len(ok), "n": len(g),
                   "ah_tau": ok.kendall_tau.mean(), "ah_top1": ok.top1.mean(), "ah_mae": ok.mae.mean()}
            for b in COMPARE:
                rec[f"{b}_tau"] = bidx[b].loc[sids, "kendall_tau"].mean()
                rec[f"{b}_top1"] = bidx[b].loc[sids, "top1"].mean()
                rec[f"{b}_mae"] = bidx[b].loc[sids, "mae"].mean()
            per_run.append(rec)
        R = pd.DataFrame(per_run)
        row = {"model": mk, "decision_type": dt, "n_runs": len(R), "n": int(R.n.iloc[0]),
               "n_scored_mean": R.n_scored.mean(), "ah_tau": R.ah_tau.mean(), "ah_top1": R.ah_top1.mean(),
               "ah_mae": R.ah_mae.mean()}
        for b in COMPARE:
            row[f"{b}_tau_same"] = R[f"{b}_tau"].mean()
            row[f"gain_tau_vs_{b}"] = (R.ah_tau - R[f"{b}_tau"]).mean()
            row[f"gain_tau_vs_{b}_runmin"] = (R.ah_tau - R[f"{b}_tau"]).min()
            row[f"gain_tau_vs_{b}_runmax"] = (R.ah_tau - R[f"{b}_tau"]).max()
            row[f"gain_top1_vs_{b}"] = (R.ah_top1 - R[f"{b}_top1"]).mean()
            row[f"gain_mae_vs_{b}"] = (R.ah_mae - R[f"{b}_mae"]).mean()
        gain_rows.append(row)
gain = pd.DataFrame(gain_rows)
gain.to_csv(OUT / "d1_ah_gain_like_for_like.csv", index=False)
print(gain[["model", "decision_type", "ah_tau", "LU_tau_same", "gain_tau_vs_LU", "gain_tau_vs_LU-corpus",
            "gain_tau_vs_FD+time", "gain_tau_vs_FD", "gain_tau_vs_DM", "gain_top1_vs_LU"]]
      .round(3).to_string(index=False))

# Share of A_H's gain over FD / DM that LU reproduces, per model per decision type
share_rows = []
for _, r in gain.iterrows():
    for ref in ["FD", "DM"]:
        tot = r[f"gain_tau_vs_{ref}"]
        lu_part = r["LU_tau_same"] - r[f"{ref}_tau_same"]
        share_rows.append({"model": r.model, "decision_type": r.decision_type, "reference": ref,
                           "ah_gain_over_ref": tot, "lu_gain_over_ref": lu_part,
                           "share_reproduced_by_LU": lu_part / tot if abs(tot) > 0.02 else np.nan,
                           "corpus_gain_over_ref": r["LU-corpus_tau_same"] - r[f"{ref}_tau_same"]})
share = pd.DataFrame(share_rows)
share.to_csv(OUT / "d1_share_reproduced.csv", index=False)
print(share[share.decision_type.isin(["Overall", "Appliance"])].round(3).to_string(index=False))

# Paired tests on per-scenario run means (Methods protocol), same helpers
sig_rows = []
for mk in MODELS:
    pr = pr_all[(pr_all.model == mk) & (~pr_all.failed)]
    rm = pr.groupby("scenario_id")[["kendall_tau", "top1", "mae"]].mean().reset_index().assign(arm="AH_runmean")
    for b in ["LU", "LU-corpus", "FD+time"]:
        bb = bidx[b].reset_index()[["scenario_id", "kendall_tau", "top1", "mae"]].assign(arm=b)
        stratum = pd.concat([rm, bb], ignore_index=True)
        for scope in ["Overall"] + DTYPES:
            st = stratum if scope == "Overall" else stratum[stratum.scenario_id.isin(
                [s for s in SC if SC[s]["dt"] == scope])]
            for metric in ["kendall_tau", "top1", "mae"]:
                piv = st.pivot_table(index="scenario_id", columns="arm", values=metric).dropna()
                diff = piv["AH_runmean"] - piv[b]
                ph = rag.posthoc_wilcoxon_holm(st, metric, config_col="arm", scenario_col="scenario_id")
                base_rec = {"model": mk, "comparison": f"AH vs {b}", "scope": scope, "metric": metric,
                            "mean_ah": piv["AH_runmean"].mean(), "mean_base": piv[b].mean(),
                            "mean_diff": diff.mean(), "n_pairs": len(piv),
                            "n_nonzero_diff": int((diff.abs() > 1e-12).sum()),
                            "n_ah_better": int((diff > 1e-12).sum() if metric != "mae" else (diff < -1e-12).sum()),
                            "n_base_better": int((diff < -1e-12).sum() if metric != "mae" else (diff > 1e-12).sum())}
                if ph.empty:
                    sig_rows.append({**base_rec, "p_value": np.nan, "cliff_delta": np.nan,
                                     "note": "Wilcoxon undefined (all differences zero)"})
                    continue
                r = ph.iloc[0]
                # orient Cliff's delta as AH minus baseline regardless of column order
                sign = 1.0 if r.config_i == "AH_runmean" else -1.0
                sig_rows.append({**base_rec, "p_value": r.p_value, "cliff_delta_ah_minus_base": sign * r.cliff_delta,
                                 "cliff_interp": r.cliff_delta_interpretation, "statistic": r.statistic})
sig = pd.DataFrame(sig_rows)
for comp in sig.comparison.unique():
    for fam, mask in [("overall12", sig.scope == "Overall"), ("bytype36", sig.scope != "Overall")]:
        sel = (sig.comparison == comp) & mask & sig.p_value.notna()
        ph_, sh_ = rag.holm_correct(sig.loc[sel, "p_value"].values)
        sig.loc[sel, "p_holm"] = ph_
        sig.loc[sel, "family"] = fam
        sig.loc[sel, "significant_holm"] = sh_
sig.to_csv(OUT / "d1_significance_ah_vs_lookup.csv", index=False)
show = sig[sig.comparison == "AH vs LU"][["model", "scope", "metric", "mean_ah", "mean_base", "mean_diff",
                                         "n_ah_better", "n_base_better", "p_value", "p_holm",
                                         "cliff_delta_ah_minus_base", "cliff_interp"]]
print(show.to_string(index=False, float_format=lambda v: f"{v:.4g}"))


# ---------------------------------------------------------------------------
# 3. Where does the LLM add value beyond lookup?
# ---------------------------------------------------------------------------
print("\n=== 3. Parameter swap analysis and parameter accuracy ===")
runs = {}
for mk in MODELS:
    folder = PROJECT_ROOT / MODEL_SPECS[mk]["output_folder"]
    runs[mk] = {}
    for p in sorted(folder.glob(f"{AH}_results_run_*.xlsx")):
        d = read_table_clean(p).drop_duplicates(subset=["scenario_id"])
        runs[mk][p.stem[-2:]] = {int(r["scenario_id"]): r for _, r in d.iterrows()}

lu_params = {sid: BASELINES["LU"](sid) for sid in SC}
lu_metrics = bidx["LU"]
swap_rows, pacc_rows = [], []
for mk in MODELS:
    for run, by_sid in runs[mk].items():
        for sid, s in SC.items():
            dt = s["dt"]
            r = by_sid.get(sid)
            llm = hab.extracted_params(r, dt) if r is not None else None
            if llm is None:
                continue
            m_llm = score(sid, llm)
            if m_llm is None:
                continue
            true = hab.true_params(s["g"], dt)
            for p in list(hab.HIDDEN_PARAMS[dt]["numeric"]) + list(hab.HIDDEN_PARAMS[dt]["categorical"]):
                # (a) LU with this one parameter taken from the LLM
                m_a = score(sid, {**lu_params[sid], p: llm[p]})
                # (b) LLM with this one parameter taken from LU
                m_b = score(sid, {**llm, p: lu_params[sid][p]})
                swap_rows.append({"model": mk, "run": run, "scenario_id": sid, "decision_type": dt, "param": p,
                                  "tau_lu": lu_metrics.loc[sid, "kendall_tau"], "tau_llm": m_llm["kendall_tau"],
                                  "tau_lu_plus_llm_param": m_a["kendall_tau"] if m_a else np.nan,
                                  "tau_llm_plus_lu_param": m_b["kendall_tau"] if m_b else np.nan,
                                  "top1_lu": lu_metrics.loc[sid, "top1"], "top1_llm": m_llm["top1"],
                                  "top1_lu_plus_llm_param": m_a["top1"] if m_a else np.nan,
                                  "top1_llm_plus_lu_param": m_b["top1"] if m_b else np.nan})
                if p in hab.HIDDEN_PARAMS[dt]["numeric"]:
                    pacc_rows.append({"model": mk, "run": run, "scenario_id": sid, "decision_type": dt, "param": p,
                                      "true": float(true[p]), "llm": float(llm[p]), "lu": float(lu_params[sid][p]),
                                      "fd": float(BASELINES["FD"](sid)[p]),
                                      "corpus": float(BASELINES["LU-corpus"](sid)[p])})
                else:
                    if p == "occupancy_context":
                        eq = lambda a, b: hcal.normalize_occupancy_context(a) == hcal.normalize_occupancy_context(b)
                    elif p == "baseline_time":
                        ac = hab.CALCULATORS["Appliance"]()
                        eq = lambda a, b: quiet(ac._parse_time_to_hour, str(a)) == quiet(ac._parse_time_to_hour, str(b))
                    else:
                        norm = lambda a: {"washer": "washing_machine", "washing machine": "washing_machine"}.get(
                            str(a).strip().lower(), str(a).strip().lower())
                        eq = lambda a, b: norm(a) == norm(b)
                    pacc_rows.append({"model": mk, "run": run, "scenario_id": sid, "decision_type": dt, "param": p,
                                      "llm_match": bool(eq(llm[p], true[p])), "lu_match": bool(eq(lu_params[sid][p], true[p])),
                                      "fd_match": bool(eq(BASELINES["FD"](sid)[p], true[p]))})
swap = pd.DataFrame(swap_rows)
swap.to_csv(OUT / "d1_param_swap_per_scenario.csv", index=False)
pacc = pd.DataFrame(pacc_rows)
pacc.to_csv(OUT / "d1_param_accuracy_per_scenario.csv", index=False)

# Summaries: per model, decision type, parameter; run mean of scenario means
sw = swap.assign(gain_llm_param_into_lu=swap.tau_lu_plus_llm_param - swap.tau_lu,
                 loss_lu_param_into_llm=swap.tau_llm - swap.tau_llm_plus_lu_param,
                 top1_gain_llm_param_into_lu=swap.top1_lu_plus_llm_param - swap.top1_lu)
swsum = (sw.groupby(["model", "decision_type", "param", "run"])
         [["gain_llm_param_into_lu", "loss_lu_param_into_llm", "top1_gain_llm_param_into_lu"]].mean()
         .groupby(["model", "decision_type", "param"]).mean().reset_index())
swsum.to_csv(OUT / "d1_param_swap_summary.csv", index=False)
print(swsum.round(3).to_string(index=False))

num = pacc[pacc["true"].notna()] if "true" in pacc else pacc
num = pacc.dropna(subset=["llm"])
nsum = (num.assign(err_llm=(num.llm - num.true).abs(), err_lu=(num.lu - num.true).abs(),
                   err_fd=(num.fd - num.true).abs(), err_corpus=(num.corpus - num.true).abs())
        .groupby(["model", "decision_type", "param", "run"])[["err_llm", "err_lu", "err_fd", "err_corpus"]].mean()
        .groupby(["model", "decision_type", "param"]).mean().reset_index())
cat = pacc[pacc["llm_match"].notna()] if "llm_match" in pacc else pd.DataFrame()
csum = (cat.groupby(["model", "decision_type", "param", "run"])[["llm_match", "lu_match", "fd_match"]].mean()
        .groupby(["model", "decision_type", "param"]).mean().reset_index())
nsum.to_csv(OUT / "d1_param_accuracy_numeric.csv", index=False)
csum.to_csv(OUT / "d1_param_accuracy_categorical.csv", index=False)
print(nsum.round(3).to_string(index=False))
print(csum.round(3).to_string(index=False))
print("\nDone. Outputs in Analysis/pass5/ (d1_*).")
