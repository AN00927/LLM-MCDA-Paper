"""Regression tests: arch->GT scenario matching resolves descriptor ties by the
true GT scenario id (master-row index), in both matchers.

Arch Shower sid 136 (Pittsburgh, 28F, 2 people, low_flow) ties between GT shower
sid 0 (gpm 1.5) and sid 63 (gpm 2.0); the correct partner is GT sid 0.
"""
import sys
import json
import warnings
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _p in (PROJECT_ROOT, PROJECT_ROOT / "Miscellaneous Scripts" / "core-automation"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import evaluate_architecture_metrics as cm  # noqa: E402
from model_config import MODEL_SPECS  # noqa: E402

SDIR = PROJECT_ROOT / "Scenario Files"


@pytest.fixture(scope="module")
def sig():
    path = PROJECT_ROOT / "Miscellaneous Scripts" / "validation" / "significance_testing.py"
    spec = spec_from_file_location("significance_testing_for_tiebreak", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def arch_df():
    """Test sheet as a long-format architecture frame (sid = row index + 1)."""
    test = pd.read_excel(SDIR / "TestScenarios.xlsx")
    rows = []
    for i, r in test.iterrows():
        for j in (1, 2, 3):
            alt = str(r.get(f"alternative_{j}") or "").strip()
            if alt and alt.lower() != "nan":
                rows.append({
                    "scenario_id": i + 1, "decision_type": r["decision_type"],
                    "question": r["question"], "location": r["location"],
                    "outdoor_temp": r["outdoor_temp"],
                    "appliance_age": r["appliance_age"],
                    "flow_rate": r["flow_rate"], "household_size": r["household_size"],
                    "utility_budget": r["utility_budget"],
                    "housing_type": r["housing_type"], "alternative": alt,
                    "energy_cost": 50, "environmental": 50, "comfort": 50,
                    "practicality": 50, "weighted_score": 50, "rank": j,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def gt_by_type():
    return cm.load_ground_truth(cm._build_config(next(iter(MODEL_SPECS))))


def _truth_map():
    test = pd.read_excel(SDIR / "TestScenarios.xlsx")
    with open(SDIR / "rag_membership.json", encoding="utf-8") as fh:
        types = json.load(fh)["types"]
    out = {}
    for t in ("HVAC", "Appliance", "Shower"):
        ids = [i for i in test.index if test.loc[i, "decision_type"] == t]
        rag = {e["master_row"] for e in types[t]}
        mrows = [m for m in range(len(ids) + len(rag)) if m not in rag]
        for i, m in zip(ids, mrows):
            out[i + 1] = m
    return out


def test_resolve_true_gt_sid_shower_136():
    assert cm.resolve_true_gt_sid("Shower", 136) == 0
    assert cm.resolve_true_gt_sid("HVAC", 136) is None  # wrong type -> no id


def test_match_scenarios_sid136_maps_to_gt0_and_no_ties(gt_by_type, arch_df, capsys):
    gl, gi = cm.build_gt_lookup(gt_by_type), cm.build_gt_id_lookup(gt_by_type)
    merged, _ = cm.match_scenarios(gl, gi, arch_df, "Direct_LLM_Scoring")
    out = capsys.readouterr()
    assert "UNRESOLVED" not in out.err and "UNRESOLVED" not in out.out
    mp = merged.drop_duplicates("arch_scenario_id").set_index("arch_scenario_id")["gt_scenario_id"]
    assert len(mp) == 195
    assert int(mp[136]) == 0
    sh = gt_by_type["Shower"]
    assert float(sh[sh.scenario_id == 0]["gpm"].iloc[0]) == 1.5
    truth = _truth_map()
    assert {int(k): int(v) for k, v in mp.items()} == truth


def test_match_arch_to_gt_sid136_maps_to_gt0_and_no_ties(sig, arch_df, capsys):
    gl = sig.build_gt_lookup(sig.load_ground_truth())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        merged = sig.match_arch_to_gt(arch_df, "Direct_LLM_Scoring", gl)
    out = capsys.readouterr()
    assert "UNRESOLVED" not in out.err and "UNRESOLVED" not in out.out
    mp = merged.drop_duplicates("arch_scenario_id").set_index("arch_scenario_id")["gt_scenario_id"]
    assert len(mp) == 195
    assert int(mp[136]) == 0
    assert {int(k): int(v) for k, v in mp.items()} == _truth_map()
