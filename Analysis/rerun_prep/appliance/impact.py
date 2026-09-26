"""Per-fix and combined impact of the Appliance calculator fixes (P1-APP).

Every variant is the NEW calculator class (Analysis/rerun_prep/calc_new/) with some
class data reverted to the shipped values, so each fix is measured alone against the
shipped reference. Baseline = shipped calculator output (must equal
Ground Truth/ground_truth_appliance.xlsx). Outputs go to Analysis/rerun_prep/appliance/out/.

Usage:  python Analysis/rerun_prep/appliance/impact.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

new_mod = harness.load_calc_module(harness.NEW_CALC)
old_mod = harness.load_calc_module(harness.PREP_DIR / "appliance" / "shipped" / "ApplianceGroundTruthCalculator.py")
New = new_mod.ApplianceGroundTruthCalculator
Old = old_mod.ApplianceGroundTruthCalculator

# Shipped rates re-expressed in the new schema (two periods; Duquesne equal peak/off-peak).
OLD_RATES = {
    "PECO":     {"peak_hours": (14, 18), "peak_rate": 0.320, "offpeak_rate": 0.076},
    "PPL":      {"peak_hours": (14, 18), "peak_rate": 0.160, "offpeak_rate": 0.070},
    "WestPenn": {"peak_hours": (14, 21), "peak_rate": 0.172, "offpeak_rate": 0.088},
    "Penelec":  {"peak_hours": (14, 21), "peak_rate": 0.185, "offpeak_rate": 0.093},
    "MetEd":    {"peak_hours": (14, 21), "peak_rate": 0.203, "offpeak_rate": 0.100},
    "Duquesne": {"peak_hours": (14, 21), "peak_rate": 0.1375, "offpeak_rate": 0.1375},
}
assert {k: {kk: vv for kk, vv in v.items()} for k, v in Old.UTILITY_RATES.items()} == OLD_RATES
OLD_MAP = dict(Old.CITY_TO_UTILITY)
OLD_BOUNDS = ((0.025, 0.71), (0.288, 3.643))
NEW_RATES = {k: dict(v) for k, v in New.UTILITY_RATES.items()}
NEW_MAP = dict(New.CITY_TO_UTILITY)
NEW_BOUNDS = (New.ENERGY_COST_BOUNDS, New.ENVIRONMENTAL_BOUNDS)

# Shipped Jun-2025 FE PTCs (code comments) for the super-off-peak-only variant.
OLD_FE_PTC = {"WestPenn": 0.10317, "Penelec": 0.11003, "MetEd": 0.11903}
FE_SUPER_MULT = {"WestPenn": 0.6298, "Penelec": 0.6510, "MetEd": 0.6215}


def rates_super_only():
    r = {k: dict(v) for k, v in OLD_RATES.items()}
    r["PECO"].update(super_offpeak_hours=(0, 6), super_offpeak_rate=0.05274)
    for u in OLD_FE_PTC:
        r[u].update(super_offpeak_hours=(23, 6), super_offpeak_rate=OLD_FE_PTC[u] * FE_SUPER_MULT[u])
    return r


def rates_period_only():
    r = {k: dict(v) for k, v in NEW_RATES.items()}
    for v in r.values():
        v.pop("super_offpeak_hours", None)
        v.pop("super_offpeak_rate", None)
    return r


def rates_swap(base, **utilities):
    r = {k: dict(v) for k, v in base.items()}
    r.update({k: dict(v) for k, v in utilities.items()})
    return r


def variant(rates, mapping, bounds, recorder=None):
    class V(New):
        UTILITY_RATES = rates
        CITY_TO_UTILITY = mapping
        ENERGY_COST_BOUNDS = bounds[0]
        ENVIRONMENTAL_BOUNDS = bounds[1]
        if recorder is not None:
            def calculate_energy_cost(self, kwh_cycle, run_time_hour, location):
                c = super().calculate_energy_cost(kwh_cycle, run_time_hour, location)
                recorder["cost"].append(c)
                return c

            def calculate_environmental_impact(self, kwh_cycle, run_time_hour):
                e = super().calculate_environmental_impact(kwh_cycle, run_time_hour)
                recorder["env"].append(e)
                return e
    return V


def percentile_bounds(values):
    v = np.asarray(values, dtype=float)
    lo, hi = float(np.percentile(v, 5)), float(np.percentile(v, 95))
    return lo, hi


def convention_bounds(cost, env):
    """Shipped rounding convention: np.round(numpy linear p5/p95, 3)."""
    c, e = percentile_bounds(cost), percentile_bounds(env)
    return (tuple(float(np.round(x, 3)) for x in c), tuple(float(np.round(x, 3)) for x in e))


def bounds_line(label, cost, env):
    (lo, hi), (elo, ehi) = percentile_bounds(cost), percentile_bounds(env)
    cb, eb = convention_bounds(cost, env)
    return (f"bounds [{label}, n={len(cost)}]: cost p5={lo:.6f} p95={hi:.6f} -> {cb}; "
            f"env p5={elo:.6f} p95={ehi:.6f} -> {eb}")


def main():
    rag_ids = harness.rag_scenario_ids()
    gt = pd.read_excel(harness.SHIPPED_GT)
    lines = []

    # 0. Baselines: shipped copy and new logic with shipped data both reproduce GT.
    rec_old = {"cost": [], "env": []}
    base = harness.run_module(old_mod, tag="shipped")
    assert not harness.compare_exact(base, gt), "shipped copy does not reproduce GT"
    newlogic_old = harness.run_module(
        new_mod, variant(OLD_RATES, OLD_MAP, OLD_BOUNDS, rec_old), tag="newlogic_olddata")
    p = harness.compare_exact(newlogic_old, gt)
    lines.append("New logic + shipped data vs GT: " + ("IDENTICAL" if not p else "; ".join(p)))
    lines.append(bounds_line("shipped data, unrounded raw", rec_old["cost"], rec_old["env"]))

    # 1. Combined fixes with shipped bounds -> source of the new bounds.
    rec_new = {"cost": [], "env": []}
    combined_oldb = harness.run_module(
        new_mod, variant(NEW_RATES, NEW_MAP, OLD_BOUNDS, rec_new), tag="combined_oldbounds")
    lines.append(bounds_line("new data, unrounded raw", rec_new["cost"], rec_new["env"]))
    # Shipped convention: numpy linear percentiles of the output xlsx raw_cost (4 dp) and
    # raw_emissions (3 dp) columns, np.round to 3 dp. It reproduces all four shipped
    # constants (Python round() would give 0.711, not 0.71, for p95 cost = 0.7105).
    lines.append(bounds_line("shipped GT xlsx columns", gt["raw_cost"], gt["raw_emissions"]))
    lines.append(bounds_line("new data xlsx columns", combined_oldb["raw_cost"], combined_oldb["raw_emissions"]))
    assert convention_bounds(gt["raw_cost"], gt["raw_emissions"]) == OLD_BOUNDS, "shipped convention not reproduced"
    derived = convention_bounds(combined_oldb["raw_cost"], combined_oldb["raw_emissions"])
    lines.append(f"Bounds in calc_new: cost {NEW_BOUNDS[0]}, env {NEW_BOUNDS[1]}; derived {derived}")
    if tuple(map(tuple, NEW_BOUNDS)) != derived:
        lines.append(f"WARNING: calc_new bounds {NEW_BOUNDS} != derived {derived}")

    peco_rate = {k: v for k, v in NEW_RATES["PECO"].items() if not k.startswith("super")}
    ppl_window_only = dict(OLD_RATES["PPL"], peak_hours=(16, 20))
    fe_new = {u: {k: v for k, v in NEW_RATES[u].items() if not k.startswith("super")}
              for u in ("WestPenn", "Penelec", "MetEd")}
    stroud = dict(NEW_MAP, Stroudsburg="MetEd")

    variants = [
        ("a  super off-peak only (shipped rates)", rates_super_only(), OLD_MAP, OLD_BOUNDS),
        ("b  Dec25-May26 rates+windows, no super", rates_period_only(), OLD_MAP, OLD_BOUNDS),
        ("b1   PPL Dec25 PTC-basis rates+4-8pm", rates_swap(OLD_RATES, PPL=NEW_RATES["PPL"]), OLD_MAP, OLD_BOUNDS),
        ("b2   PPL 4-8pm window only (old rates)", rates_swap(OLD_RATES, PPL=ppl_window_only), OLD_MAP, OLD_BOUNDS),
        ("b3   PECO Dec25 PTC-basis values only", rates_swap(OLD_RATES, PECO=peco_rate), OLD_MAP, OLD_BOUNDS),
        ("b4   FE Dec25 PTCs only (no super)", rates_swap(OLD_RATES, **fe_new), OLD_MAP, OLD_BOUNDS),
        ("b5   Duquesne flat, no window", rates_swap(OLD_RATES, Duquesne=NEW_RATES["Duquesne"]), OLD_MAP, OLD_BOUNDS),
        ("c  city mapping only (6 cities)", OLD_RATES, NEW_MAP, OLD_BOUNDS),
        ("a+b  all tariff fixes, shipped map+bounds", NEW_RATES, OLD_MAP, OLD_BOUNDS),
        ("a+b+c  all, shipped bounds", NEW_RATES, NEW_MAP, OLD_BOUNDS),
        ("f  new bounds only (shipped rates+map)", OLD_RATES, OLD_MAP, NEW_BOUNDS),
        ("ALL  a+b+c+f (calc_new as written)", NEW_RATES, NEW_MAP, NEW_BOUNDS),
        ("sens ALL + Stroudsburg -> MetEd", NEW_RATES, stroud, NEW_BOUNDS),
    ]
    results = {}
    lines.append("")
    lines.append("W = winner changes, R = full-ranking changes, S = scenarios with any criterion score change")
    for label, rates, mapping, bounds in variants:
        tag = "v_" + label.split()[0].replace("+", "_")
        df = harness.run_module(new_mod, variant(rates, mapping, bounds), tag=tag)
        res = harness.impact(base, df, rag_ids)
        results[label] = (df, res)
        lines.append(harness.format_impact(label, res))

    # The installed-form file must equal the ALL variant.
    final = harness.run_module(new_mod, tag="calc_new_final")
    p = harness.compare_exact(final, results["ALL  a+b+c+f (calc_new as written)"][0])
    lines.append("")
    lines.append("calc_new file vs ALL variant: " + ("IDENTICAL" if not p else "; ".join(p)))
    res = harness.impact(base, final, rag_ids)
    lines.append("bounds effect alone on top of a+b+c: " + harness.format_impact(
        "", harness.impact(results["a+b+c  all, shipped bounds"][0], final, rag_ids)).strip())

    # Detail of the final changes.
    master = pd.read_excel(harness.MASTER_XLSX)
    lines.append("")
    lines.append("Scenarios whose winner or ranking changes under ALL (calc_new):")
    for part in ("test", "rag"):
        for sid in sorted(set(res[part]["winner"]) | set(res[part]["ranking"])):
            b = base[base.scenario_id == sid].sort_values("rank")
            n = final[final.scenario_id == sid].sort_values("rank")
            lines.append(f"  [{part}] sid {sid:>2} {master.loc[sid, 'location']:<18} {master.loc[sid, 'appliance']:<15}"
                         f" base {master.loc[sid, 'baseline_time']!s:<9} old {' > '.join(b.alternative)}"
                         f"  |  new {' > '.join(n.alternative)}")

    text = "\n".join(lines)
    print(text)
    (harness.OUT_DIR / "impact_summary.txt").write_text(text + "\n", encoding="ascii")
    final.to_excel(harness.OUT_DIR / "ground_truth_appliance_NEW.xlsx", index=False)
    return results


if __name__ == "__main__":
    main()
