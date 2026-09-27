"""Validation and sentinel-discipline tests for the Appliance reference calculator (P1-APP,
git commit `daafa48`, "Refactor ApplianceGroundTruthCalculator: strict appliance and time
parsing, validate utility_budget and baseline_time").

Pins the fixes described in `paper/pass6/verify/V_APPLIANCE.md` discrepancies D1, D2, D3, D4
and D6 (all now raise inside `calculate_scenario_scores`'s try/except and emit the sentinel
instead of silently defaulting or crashing), plus the Appliance and Shower budget-penalty
continuity (D13's test-coverage gap; HVAC's own continuity test is
`tests/test_hvac_reference.py::test_budget_penalty_continuous_above_1_5`).

The Appliance calculator file under test is APPLIANCE_CALC_PATH if set, otherwise the
installed file at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py`. The Shower
calculator file is SHOWER_CALC_PATH if set, otherwise `Ground Truth Calculators/
ShowerGroundTruthCalculator.py`. Import style follows tests/test_appliance_tariffs.py and
tests/test_shower_reference.py.
"""
import importlib.util
import math
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLIANCE_DEFAULT_PATH = PROJECT_ROOT / "Ground Truth Calculators" / "ApplianceGroundTruthCalculator.py"
SHOWER_DEFAULT_PATH = PROJECT_ROOT / "Ground Truth Calculators" / "ShowerGroundTruthCalculator.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import is_sentinel, has_sentinel_scores, SENTINEL_VALUE, CRITERIA


def _load(env_var: str, default_path: Path, module_name: str):
    path = Path(os.environ.get(env_var, default_path))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


APPLIANCE_MOD = _load("APPLIANCE_CALC_PATH", APPLIANCE_DEFAULT_PATH, "_appliance_validation_calc")
SHOWER_MOD = _load("SHOWER_CALC_PATH", SHOWER_DEFAULT_PATH, "_shower_validation_calc")


@pytest.fixture
def calc():
    return APPLIANCE_MOD.ApplianceGroundTruthCalculator()


@pytest.fixture
def shower_calc():
    return SHOWER_MOD.ShowerGroundTruthCalculator()


ALT_SCORE_KEYS = ("energy_cost_score", "environmental_score", "comfort_score", "practicality_score")


def _scenario(appliance="dishwasher", location="Philadelphia, PA", utility_budget=200,
              housing_type="Single-family", household_size=3, kwh_per_cycle=1.0,
              baseline_time="7:00 PM", alt1="7:00 PM", alt2="9:00 PM", alt3="10:00 AM",
              drop_baseline_time=False, drop_utility_budget=False):
    """Build a minimal valid Appliance scenario dict of the shape
    calculate_scenario_scores expects (matches a master ApplianceScenarios.xlsx row)."""
    s = {
        "question": "When should I run the appliance?",
        "location": location,
        "appliance": appliance,
        "housing_type": housing_type,
        "household_size": household_size,
        "kwh_per_cycle": kwh_per_cycle,
        "alternative_1": alt1,
        "alternative_2": alt2,
        "alternative_3": alt3,
    }
    if not drop_baseline_time:
        s["baseline_time"] = baseline_time
    if not drop_utility_budget:
        s["utility_budget"] = utility_budget
    return s


def _criteria_dict(alt_scores):
    """Map the calculator's `*_score`-suffixed keys onto sentinel_utils.CRITERIA's
    plain names so has_sentinel_scores can be used directly."""
    return {
        "energy_cost": alt_scores["energy_cost_score"],
        "environmental": alt_scores["environmental_score"],
        "comfort": alt_scores["comfort_score"],
        "practicality": alt_scores["practicality_score"],
    }


def _assert_all_alts_sentinel(scores, alt_values):
    for alt in alt_values:
        alt_scores = scores[alt]
        for key in ALT_SCORE_KEYS:
            assert is_sentinel(alt_scores[key]), f"{alt}: {key} = {alt_scores[key]!r}, expected sentinel"
        assert has_sentinel_scores(_criteria_dict(alt_scores), criteria=CRITERIA)


def _assert_no_sentinel(scores, alt_values):
    for alt in alt_values:
        alt_scores = scores[alt]
        for key in ALT_SCORE_KEYS:
            assert not is_sentinel(alt_scores[key]), f"{alt}: {key} unexpectedly sentinel"
        assert not has_sentinel_scores(_criteria_dict(alt_scores), criteria=CRITERIA)


# --- positive control ---------------------------------------------------------------

def test_valid_scenario_has_no_sentinel(calc):
    sc = _scenario()
    scores = calc.calculate_scenario_scores(sc)
    _assert_no_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


# --- D1: misspelled / unknown appliance type -----------------------------------------

@pytest.mark.parametrize("appliance", ["Waser", "toaster"])
def test_unknown_or_misspelled_appliance_is_sentinel(calc, appliance):
    sc = _scenario(appliance=appliance)
    scores = calc.calculate_scenario_scores(sc)
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


def test_canonical_appliance_rejects_unknown_directly(calc):
    with pytest.raises(ValueError):
        calc._canonical_appliance("Waser")
    with pytest.raises(ValueError):
        calc._canonical_appliance("toaster")


# --- D2: missing / unparseable baseline_time -----------------------------------------

def test_missing_baseline_time_is_sentinel(calc):
    sc = _scenario(drop_baseline_time=True)
    scores = calc.calculate_scenario_scores(sc)
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


def test_unparseable_baseline_time_is_sentinel(calc):
    sc = _scenario(baseline_time="sometime this evening")
    scores = calc.calculate_scenario_scores(sc)
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


def test_parse_time_to_hour_rejects_unparseable_directly(calc):
    with pytest.raises(ValueError):
        calc._parse_time_to_hour("sometime this evening")


# --- D3: utility_budget None / non-numeric --------------------------------------------

def test_utility_budget_none_is_sentinel_no_exception(calc):
    sc = _scenario(utility_budget=None)
    scores = calc.calculate_scenario_scores(sc)  # must not raise
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


def test_utility_budget_non_numeric_is_sentinel_no_exception(calc):
    sc = _scenario(utility_budget="abc")
    scores = calc.calculate_scenario_scores(sc)  # must not raise
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


# --- D4: utility_budget missing / 0 -----------------------------------------------------

def test_missing_utility_budget_is_sentinel(calc):
    sc = _scenario(drop_utility_budget=True)
    scores = calc.calculate_scenario_scores(sc)
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


def test_zero_utility_budget_is_sentinel(calc):
    sc = _scenario(utility_budget=0)
    scores = calc.calculate_scenario_scores(sc)
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


# --- D6: "13:00 PM"-style (hour > 12 with am/pm) -----------------------------------------

def test_hour_over_12_with_ampm_alternative_is_sentinel(calc):
    sc = _scenario(alt1="13:00 PM", alt2="9:00 PM", alt3="10:00 AM")
    scores = calc.calculate_scenario_scores(sc)
    for key in ALT_SCORE_KEYS:
        assert is_sentinel(scores["13:00 PM"][key])
    # the other, valid alternatives are unaffected
    _assert_no_sentinel(scores, ["9:00 PM", "10:00 AM"])


def test_hour_over_12_with_ampm_baseline_is_sentinel(calc):
    # An invalid baseline affects every alternative (delay can't be computed for any of them).
    sc = _scenario(baseline_time="13:00 PM")
    scores = calc.calculate_scenario_scores(sc)
    _assert_all_alts_sentinel(scores, [sc["alternative_1"], sc["alternative_2"], sc["alternative_3"]])


def test_parse_alternative_rejects_hour_over_12_directly(calc):
    with pytest.raises(ValueError):
        calc.parse_alternative("13:00 PM", {"baseline_time": "7:00 PM"})
    with pytest.raises(ValueError):
        calc._parse_time_to_hour("13:00 PM")


# --- budget-penalty continuity: Appliance ------------------------------------------------

def test_appliance_budget_penalty_continuity(calc):
    bp = calc.calculate_budget_penalty
    budget = 100.0

    # Left/right limits at the two threshold points (0.80, 1.0) and at the former cliff
    # point (1.5) agree within 1e-6: no discontinuity remains anywhere.
    for u in (0.80, 1.0, 1.5):
        left = bp(budget * (u - 1e-7), budget)
        right = bp(budget * (u + 1e-7), budget)
        assert abs(left - right) < 1e-6, f"discontinuity at u={u}: left={left}, right={right}"

    # Exact values at the anchor points.
    assert bp(0.5 * budget, budget) == pytest.approx(1.0)
    assert bp(0.80 * budget, budget) == pytest.approx(1.0)
    assert bp(1.0 * budget, budget) == pytest.approx(0.5)
    assert bp(1.5 * budget, budget) == pytest.approx(0.5 * math.exp(-1.5))

    # Monotone non-increasing on a fine grid over u in [0, 3].
    us = [i / 100.0 for i in range(0, 301)]
    vals = [bp(u * budget, budget) for u in us]
    assert all(b <= a + 1e-12 for a, b in zip(vals, vals[1:])), "budget penalty must be non-increasing"

    # Positive at u = 2.0 (no drop to 0; the former u >= 1.5 cliff was removed).
    assert bp(2.0 * budget, budget) > 0.0
    assert bp(2.0 * budget, budget) == pytest.approx(0.5 * math.exp(-3.0))


# --- budget-penalty continuity: Shower --------------------------------------------------

def test_shower_budget_penalty_continuity(shower_calc):
    bp = shower_calc.calculate_budget_penalty
    budget = 100.0

    for u in (0.80, 1.0, 1.5):
        left = bp(budget * (u - 1e-7), budget)
        right = bp(budget * (u + 1e-7), budget)
        assert abs(left - right) < 1e-6, f"discontinuity at u={u}: left={left}, right={right}"

    assert bp(0.5 * budget, budget) == pytest.approx(1.0)
    assert bp(0.80 * budget, budget) == pytest.approx(1.0)
    assert bp(1.0 * budget, budget) == pytest.approx(0.5)
    assert bp(1.5 * budget, budget) == pytest.approx(0.5 * math.exp(-1.5))

    us = [i / 100.0 for i in range(0, 301)]
    vals = [bp(u * budget, budget) for u in us]
    assert all(b <= a + 1e-12 for a, b in zip(vals, vals[1:])), "budget penalty must be non-increasing"

    assert bp(2.0 * budget, budget) > 0.0
    assert bp(2.0 * budget, budget) == pytest.approx(0.5 * math.exp(-3.0))
