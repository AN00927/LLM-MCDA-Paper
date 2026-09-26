"""Before/after harness for the Appliance reference calculator.

Runs any copy of ApplianceGroundTruthCalculator.py over the 100 master scenarios
(Scenario Files/ApplianceScenarios.xlsx) through that module's own
process_appliance_scenarios(), with the output redirected under
Analysis/rerun_prep/appliance/out/. Nothing under Ground Truth/ or Scenario Files/
is written.

Usage:
    python Analysis/rerun_prep/appliance/harness.py [path/to/ApplianceGroundTruthCalculator.py]

With no argument it checks Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py
against Ground Truth/ground_truth_appliance.xlsx and prints the comparison.
"""
import contextlib
import importlib.util
import io
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PREP_DIR = PROJECT_ROOT / "Analysis" / "rerun_prep"
OUT_DIR = PREP_DIR / "appliance" / "out"
MASTER_XLSX = PROJECT_ROOT / "Scenario Files" / "ApplianceScenarios.xlsx"
RAG_XLSX = PROJECT_ROOT / "Scenario Files" / "ApplianceRAGScenarios.xlsx"
SHIPPED_GT = PROJECT_ROOT / "Ground Truth" / "ground_truth_appliance.xlsx"
NEW_CALC = PREP_DIR / "calc_new" / "ApplianceGroundTruthCalculator.py"
SHIPPED_CALC = PROJECT_ROOT / "Ground Truth Calculators" / "ApplianceGroundTruthCalculator.py"

SCORE_COLS = ["energy_cost_score", "environmental_score", "comfort_score", "practicality_score"]
COMPARE_COLS = SCORE_COLS + ["mavt_score", "rank", "raw_cost", "raw_emissions"]
RAG_KEYS = ["location", "utility_budget", "appliance", "housing_type",
            "household_size", "kwh_per_cycle", "appliance_age"]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_module_counter = [0]


def load_calc_module(path):
    """Import a calculator file under a unique module name."""
    _module_counter[0] += 1
    name = f"_appliance_calc_{_module_counter[0]}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_module(mod, calculator_class=None, tag="run"):
    """Run mod.process_appliance_scenarios over the master sheet, output under OUT_DIR.

    calculator_class, if given, temporarily replaces the module's
    ApplianceGroundTruthCalculator (used for per-fix variants).
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{tag}.xlsx"
    original = mod.ApplianceGroundTruthCalculator
    if calculator_class is not None:
        mod.ApplianceGroundTruthCalculator = calculator_class
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            df = mod.process_appliance_scenarios(
                xlsx_filename=str(MASTER_XLSX), output_filename=str(out_path))
    finally:
        mod.ApplianceGroundTruthCalculator = original
    return df


def rag_scenario_ids():
    """Master row indices (= scenario_id) that belong to the 35-scenario RAG corpus.

    Matched on the scenario descriptors, since question text is shared between
    some test and RAG rows.
    """
    master = pd.read_excel(MASTER_XLSX)
    rag = pd.read_excel(RAG_XLSX)
    keys = {tuple(r) for r in rag[RAG_KEYS].drop_duplicates().itertuples(index=False)}
    ids = [i for i, r in enumerate(master[RAG_KEYS].itertuples(index=False)) if tuple(r) in keys]
    assert len(ids) == 35, f"expected 35 RAG scenarios, matched {len(ids)}"
    return set(ids)


def compare_exact(df_a, df_b):
    """Row-by-row comparison. Returns a list of mismatch strings (empty = identical)."""
    problems = []
    if len(df_a) != len(df_b):
        return [f"row count {len(df_a)} vs {len(df_b)}"]
    a = df_a.reset_index(drop=True)
    b = df_b.reset_index(drop=True)
    for col in ["scenario_id", "alternative"]:
        diff = (a[col].astype(str) != b[col].astype(str))
        if diff.any():
            problems.append(f"{col}: {int(diff.sum())} rows differ")
    for col in COMPARE_COLS:
        diff = (a[col].astype(float) - b[col].astype(float)).abs() > 1e-9
        if diff.any():
            problems.append(f"{col}: {int(diff.sum())} rows differ")
    return problems


def _orderings(df):
    """scenario_id -> (winner tuple, full ordering tuple, score tuple)."""
    out = {}
    for sid, g in df.groupby("scenario_id", sort=True):
        g = g.reset_index(drop=True)
        ranks = tuple(int(r) for r in g["rank"])
        winners = tuple(sorted(g.loc[g["rank"] == g["rank"].min(), "alternative"].astype(str)))
        scores = tuple(tuple(float(x) for x in g[c]) for c in SCORE_COLS)
        out[int(sid)] = (winners, ranks, scores)
    return out


def impact(df_base, df_new, rag_ids):
    """Winner / full-ranking / criterion-score changes, split test (65) and RAG (35)."""
    base = _orderings(df_base)
    new = _orderings(df_new)
    res = {"test": {"n": 0, "winner": [], "ranking": [], "scores": []},
           "rag": {"n": 0, "winner": [], "ranking": [], "scores": []}}
    for sid in sorted(base):
        part = "rag" if sid in rag_ids else "test"
        res[part]["n"] += 1
        if base[sid][0] != new[sid][0]:
            res[part]["winner"].append(sid)
        if base[sid][1] != new[sid][1]:
            res[part]["ranking"].append(sid)
        if base[sid][2] != new[sid][2]:
            res[part]["scores"].append(sid)
    return res


def format_impact(label, res):
    t, r = res["test"], res["rag"]
    return (f"{label:<46} test W {len(t['winner']):>2}/{t['n']}  R {len(t['ranking']):>2}/{t['n']}"
            f"  S {len(t['scores']):>2}/{t['n']} | RAG W {len(r['winner']):>2}/{r['n']}"
            f"  R {len(r['ranking']):>2}/{r['n']}  S {len(r['scores']):>2}/{r['n']}")


def main(argv):
    calc_path = Path(argv[1]) if len(argv) > 1 else NEW_CALC
    mod = load_calc_module(calc_path)
    df = run_module(mod, tag="check_" + calc_path.parent.name)
    gt = pd.read_excel(SHIPPED_GT)
    problems = compare_exact(df, gt)
    print(f"calculator: {calc_path}")
    print(f"rows: {len(df)} (shipped ground truth: {len(gt)})")
    if problems:
        print("DIFFERS from Ground Truth/ground_truth_appliance.xlsx:")
        for p in problems:
            print("  " + p)
    else:
        print("IDENTICAL to Ground Truth/ground_truth_appliance.xlsx (scores, mavt, ranks, raw values)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
