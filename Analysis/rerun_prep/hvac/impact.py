"""HVAC reference-calculator impact report (P1-HVAC, revision 2: question-based mode).

Computes, against the shipped ground truth:
  - the 5th-95th percentile bounds (current convention: nonzero cent-rounded raw_cost over
    the 105 master scenarios, test + RAG pooled; HVAC Environmental derived from those kWh
    at the PJM off-peak / peak factors), first confirming the shipped $0.38/$3.29 and
    1.96/18.04 reproduce;
  - the operating mode assigned to each of the 105 scenarios, against the question wording;
  - winner and full-ranking changes (test of 70, RAG of 35) for each change alone and
    combined, with old bounds and with recomputed bounds;
  - exemplar-visible RAG score cells that change;
  - heating/cooling branch changes per alternative;
  - the Bradford budget case and the Stroudsburg hvac_age 95 -> 40 data fix.

Writes Analysis/rerun_prep/hvac/out/impact_results.json, out/scenario_modes.csv and a
scratch master copy under Analysis/rerun_prep/hvac/out/. Nothing else is written.

Usage: python Analysis/rerun_prep/hvac/impact.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd  # noqa: E402
import common as C  # noqa: E402
import variants as V  # noqa: E402

STROUDSBURG_ROW = 30
LABELS = {"hspf": "(a) heating at HSPF", "mode": "(b) mode from question, load capped by mode",
          "t71": "(c) heating optimum 71 F", "gain220": "(d) occupant gain 220 Btu/h",
          "budget": "(g) continuous budget penalty"}


def bounds_from(df):
    return C.cost_percentile_bounds(df["raw_cost"].tolist())


def summarize(name, base, df, rag_sids):
    rc = C.ranking_changes(base, df, rag_sids)
    ex = C.exemplar_changes(base, df, rag_sids)
    return {"variant": name,
            "test_winner": rc["test"]["winner"], "test_full": rc["test"]["full"],
            "rag_winner": rc["rag"]["winner"], "rag_full": rc["rag"]["full"],
            "test_winner_ids": rc["test"]["winner_ids"], "test_full_ids": rc["test"]["full_ids"],
            "rag_winner_ids": rc["rag"]["winner_ids"], "rag_full_ids": rc["rag"]["full_ids"],
            "exemplar_cells_changed": ex["changed"], "exemplar_cells": ex["cells"],
            "exemplar_rows_changed": ex["rows_changed"],
            "exemplar_scenarios_changed": ex["scenarios_changed"],
            "exemplar_per_col": ex["per_col"]}


def run_with_own_bounds(label, base, rag_sids, **kw):
    """Run a variant at old bounds, recompute its bounds, rerun at those; return both rows."""
    df_old = C.run_hvac(V.new_mod, V.make_variant(cost_bounds=V.OLD_COST_BOUNDS,
                                                  env_bounds=V.OLD_ENV_BOUNDS, **kw))
    b = bounds_from(df_old)
    nb = ((b["cost_min_r"], b["cost_max_r"]), (b["env_min_r"], b["env_max_r"]))
    df_new = C.run_hvac(V.new_mod, V.make_variant(cost_bounds=nb[0], env_bounds=nb[1], **kw))
    r1 = summarize(label + ", old bounds", base, df_old, rag_sids)
    r2 = summarize(label + ", own recomputed bounds", base, df_new, rag_sids)
    r2["bounds"] = [nb[0][0], nb[0][1], nb[1][0], nb[1][1]]
    return r1, r2, df_new, b


def question_wording(q):
    q = str(q)
    heat = bool(re.search(r"\bheat\b", q, re.I))
    ac = bool(re.search(r"\bAC\b", q))
    return "heat" if heat and not ac else "cool" if ac and not heat else "unclear"


def _effective_temp(alt, outdoor, ac_mode, calc):
    if "off" in alt.lower():
        return calc._free_float_temp(outdoor, ac_mode), True
    return float(re.findall(r"\d+", alt)[0]), False


def branch_counts(master, rag_ids, new_cls):
    """Per alternative: shipped load/practicality branch (outdoor > setpoint) and shipped
    comfort mode (outdoor > 75), vs the new operating mode from the question."""
    calc = new_cls()
    frozen = V.Frozen()
    rows = []
    for idx, r in master.iterrows():
        out = float(r["outdoor_temp"])
        mode = calc.resolve_hvac_mode({"question": r["question"]})
        ac = mode == "cool"
        old_ff = out > (76 + 70) / 2.0
        for col in ("alternative_1", "alternative_2", "alternative_3"):
            alt = str(r[col]).strip()
            t_old, is_off = _effective_temp(alt, out, old_ff, calc)
            t_new, _ = _effective_temp(alt, out, ac, calc)
            old_branch = "cool" if out > t_old else "heat"
            fargs = (out, t_old, int(r["square_footage"]), int(r["r_value"]),
                     int(r["household_size"]), 8.0, str(r["housing_type"]))
            old_load = (frozen.calculate_cooling_load(*fargs) if old_branch == "cool"
                        else frozen.calculate_heating_load(*fargs))
            q = calc.calculate_net_heat_gain(out, t_new, int(r["square_footage"]), int(r["r_value"]),
                                             int(r["household_size"]), 8.0, str(r["housing_type"]),
                                             include_solar=ac)
            new_load = max(0.0, q) if ac else max(0.0, -q)
            rows.append({"scenario_id": idx, "rag": idx in rag_ids, "alt": alt, "outdoor": out,
                         "setpoint": t_new, "off": is_off, "mode": mode,
                         "old_branch": old_branch, "old_zero_load": old_load == 0,
                         "new_zero_load": new_load == 0,
                         "old_comfort_mode": "cool" if out > 75 else "heat"})
    d = pd.DataFrame(rows)

    def cnt(mask):
        return {"test": int((mask & ~d["rag"]).sum()), "rag": int((mask & d["rag"]).sum())}
    changed = d["old_branch"] != d["mode"]
    res = {
        "branch_changed": cnt(changed),
        "branch_changed_excl_off": cnt(changed & ~d["off"]),
        "old_zero_load": cnt(d["old_zero_load"]),
        "new_zero_load": cnt(d["new_zero_load"]),
        "new_zero_load_excl_off": cnt(d["new_zero_load"] & ~d["off"]),
        "zero_load_status_changed": cnt(d["old_zero_load"] != d["new_zero_load"]),
        "comfort_mode_changed": cnt(d["old_comfort_mode"] != d["mode"]),
        "practicality_mode_changed": cnt(changed),
        "detail_changed": d[changed | (d["old_comfort_mode"] != d["mode"])
                            | (d["old_zero_load"] != d["new_zero_load"])].to_dict("records"),
    }
    return res


def main():
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    gt = pd.read_excel(C.HVAC_GT)
    master = pd.read_excel(C.HVAC_MASTER)
    rag_sids, _ = C.rag_signatures(gt, C.HVAC_RAG, "HVAC")
    rag_ids = set(rag_sids)
    results = {"rag_scenario_ids": sorted(rag_sids)}

    # --- Gate: all-reverted variant reproduces the shipped reference exactly -------------
    R = V.make_variant(keep=(), cost_bounds=V.OLD_COST_BOUNDS, env_bounds=V.OLD_ENV_BOUNDS)
    mm = {k: v for k, v in C.compare_frames(gt, C.run_hvac(V.new_mod, R)).items() if v}
    results["gate_all_reverted_mismatches"] = mm
    print(f"[{'PASS' if not mm else 'FAIL'}] all-reverted new class reproduces shipped GT: {mm or 0}")
    if mm:
        return 1

    # --- Mode per scenario ------------------------------------------------------------------
    calc = V.New()
    modes = []
    for idx, r in master.iterrows():
        m = calc.resolve_hvac_mode({"question": r["question"]})
        modes.append({"scenario_id": idx, "set": "RAG" if idx in rag_ids else "test",
                      "location": r["location"], "outdoor_temp": r["outdoor_temp"],
                      "mode": m, "question_wording": question_wording(r["question"]),
                      "question": r["question"]})
    mdf = pd.DataFrame(modes)
    mdf.to_csv(C.OUT_DIR / "scenario_modes.csv", index=False)
    agree = int((mdf["mode"] == mdf["question_wording"]).sum())
    results["modes"] = {
        "agree_with_wording": agree, "n": len(mdf),
        "heat": int((mdf["mode"] == "heat").sum()), "cool": int((mdf["mode"] == "cool").sum()),
        "none": int(mdf["mode"].isna().sum()),
        "heat_outdoor_range": [float(mdf[mdf["mode"] == "heat"]["outdoor_temp"].min()),
                               float(mdf[mdf["mode"] == "heat"]["outdoor_temp"].max())],
        "cool_outdoor_range": [float(mdf[mdf["mode"] == "cool"]["outdoor_temp"].min()),
                               float(mdf[mdf["mode"] == "cool"]["outdoor_temp"].max())],
        "by_set": {f"{k[0]}/{k[1]}": int(v) for k, v in mdf.groupby(["set", "mode"]).size().items()},
    }
    print(f"modes: {results['modes']}")

    # --- Bounds ------------------------------------------------------------------------------
    old_b = bounds_from(gt)
    results["bounds_shipped_recomputed"] = old_b
    print(f"shipped bounds recomputed: cost {old_b['cost_min_r']}/{old_b['cost_max_r']}, "
          f"env {old_b['env_min_r']}/{old_b['env_max_r']} (n_active={old_b['n_active']})")
    full_old = C.run_hvac(V.new_mod, V.make_variant(cost_bounds=V.OLD_COST_BOUNDS,
                                                    env_bounds=V.OLD_ENV_BOUNDS))
    new_b = bounds_from(full_old)   # raw costs do not depend on the bounds
    results["bounds_new"] = new_b
    nb_cost = (new_b["cost_min_r"], new_b["cost_max_r"])
    nb_env = (new_b["env_min_r"], new_b["env_max_r"])
    print(f"new bounds: cost {nb_cost}, env {nb_env} (n_active={new_b['n_active']}; "
          f"p5={new_b['cost_p5']:.3f} p95={new_b['cost_p95']:.3f} "
          f"kWh {new_b['kwh_p5']:.3f}/{new_b['kwh_p95']:.3f})")

    # --- Variants ----------------------------------------------------------------------------
    table = []
    for ch in V.CHANGES:
        r1, r2, _, _ = run_with_own_bounds(LABELS[ch] + " alone", gt, rag_sids, keep=(ch,))
        table += [r1, r2]
    df0 = C.run_hvac(V.new_mod, V.make_variant(keep=(), cost_bounds=V.OLD_COST_BOUNDS,
                                               env_bounds=V.OLD_ENV_BOUNDS))
    table.append(summarize("(0) nothing changed, current sentinel_utils MAVT rounding", gt, df0, rag_sids))
    df = C.run_hvac(V.new_mod, V.make_variant(keep=(), cost_bounds=nb_cost, env_bounds=nb_env))
    table.append(summarize("(f) new bounds alone (shipped model)", gt, df, rag_sids))
    table.append(summarize("all combined, old bounds", gt, full_old, rag_sids))
    full_new = C.run_hvac(V.new_mod, V.make_variant(cost_bounds=nb_cost, env_bounds=nb_env))
    table.append(summarize("ALL COMBINED, new bounds (the new calculator)", gt, full_new, rag_sids))
    for label, kw in (("sensitivity: occupant gain 230 instead of 220", {"occupant_gain": 230}),
                      ("sensitivity: solar credited in heat mode too", {"solar_both": True}),
                      ("sensitivity: budget cliff kept (all other changes)",
                       {"keep": tuple(c for c in V.CHANGES if c != "budget")})):
        _, r2, dfs, b = run_with_own_bounds(label, gt, rag_sids, **kw)
        r2["variant"] = label + ", own bounds, vs shipped"
        table.append(r2)
        r3 = summarize(label + ", own bounds, vs the new calculator", full_new, dfs, rag_sids)
        r3["bounds"] = r2["bounds"]
        table.append(r3)

    inst = C.run_hvac(V.new_mod)
    inst_mm = {k: v for k, v in C.compare_frames(full_new, inst).items() if v}
    results["new_class_matches_new_bounds_variant"] = inst_mm
    print(f"[{'PASS' if not inst_mm else 'NOTE'}] new class as written == all-combined/new-bounds "
          f"variant: {inst_mm or 0}"
          + ("" if not inst_mm else "  (expected until the new bounds are put in the class)"))

    results["impact"] = table
    for row in table:
        print(f"{row['variant']:<78} test W {row['test_winner']:>2}/70 full {row['test_full']:>2}/70 | "
              f"RAG W {row['rag_winner']:>2}/35 full {row['rag_full']:>2}/35 | exemplar cells "
              f"{row['exemplar_cells_changed']:>3}/{row['exemplar_cells']} "
              f"({row['exemplar_scenarios_changed']}/35 scen)"
              + (f" bounds {row['bounds']}" if row.get('bounds') else ""))

    # --- Branch changes --------------------------------------------------------------------
    results["branches"] = branch_counts(master, rag_ids, V.New)
    print("branches", {k: v for k, v in results["branches"].items() if k != "detail_changed"})

    # --- Budget: utilization in the new calculator ------------------------------------------
    u = inst["raw_cost"] * 90 / inst["utility_budget"]
    ub = gt["raw_cost"] * 90 / gt["utility_budget"]
    results["budget"] = {
        "new_u_ge_1_5": int((u >= 1.5).sum()), "new_u_1_to_1_5": int(u.between(1.0, 1.5, "left").sum()),
        "new_u_0_8_to_1": int(u.between(0.8, 1.0, "left").sum()), "new_u_max": float(u.max()),
        "shipped_u_ge_1_5": int((ub >= 1.5).sum()), "shipped_u_max": float(ub.max()),
        "bradford": inst[inst["location"].astype(str).str.startswith("Bradford")][
            ["scenario_id", "alternative", "raw_cost", "utility_budget", "energy_cost_score",
             "mavt_score", "rank"]].to_dict("records"),
        "bradford_shipped": gt[gt["location"].astype(str).str.startswith("Bradford")][
            ["scenario_id", "alternative", "raw_cost", "energy_cost_score", "rank"]].to_dict("records"),
    }
    print("budget", {k: v for k, v in results["budget"].items() if not k.startswith("bradford")})
    for rec in results["budget"]["bradford"]:
        print("  Bradford", rec)

    # --- Stroudsburg data fix on a scratch master -------------------------------------------
    scratch = C.OUT_DIR / "HVACScenarios_stroudsburg_hvac_age40.xlsx"
    m2 = master.copy()
    assert m2.loc[STROUDSBURG_ROW, "location"] == "Stroudsburg, PA"
    assert int(m2.loc[STROUDSBURG_ROW, "hvac_age"]) == 95
    m2.loc[STROUDSBURG_ROW, "hvac_age"] = 40
    m2.to_excel(scratch, index=False)
    s_old = C.run_hvac(V.frozen_mod, master=scratch)
    s_new = C.run_hvac(V.new_mod, master=scratch)
    s_res = {"shipped_calc": {k: v for k, v in C.compare_frames(gt, s_old).items() if v},
             "new_calc": {k: v for k, v in C.compare_frames(inst, s_new).items() if v},
             "is_rag": STROUDSBURG_ROW in rag_ids}
    results["stroudsburg"] = s_res
    print(f"Stroudsburg hvac_age 40: shipped-calc mismatches {s_res['shipped_calc'] or 0}; "
          f"new-calc mismatches {s_res['new_calc'] or 0}; RAG scenario: {s_res['is_rag']}")

    inst.to_excel(C.OUT_DIR / "ground_truth_hvac_NEW_preview.xlsx", index=False)
    with open(C.OUT_DIR / "impact_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, default=str)
    print(f"wrote {C.OUT_DIR / 'impact_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
