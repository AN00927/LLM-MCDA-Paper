"""Tests for the HVAC reference calculator (P1-HVAC changes, revision 2).

The calculator is imported from HVAC_CALC_PATH (env var, absolute or relative to the repo
root) or, by default, from Analysis/rerun_prep/calc_new/HVACGroundTruthCalculator.py.
After installation run:

    set HVAC_CALC_PATH=Ground Truth Calculators\\HVACGroundTruthCalculator.py
    python -m pytest Analysis/rerun_prep/tests/test_hvac_reference.py
"""
import importlib.util
import math
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CALC_PATH = PROJECT_ROOT / "Analysis" / "rerun_prep" / "calc_new" / "HVACGroundTruthCalculator.py"
CALC_PATH = Path(os.environ.get("HVAC_CALC_PATH", DEFAULT_CALC_PATH))
if not CALC_PATH.is_absolute():
    CALC_PATH = PROJECT_ROOT / CALC_PATH
MASTER_XLSX = PROJECT_ROOT / "Scenario Files" / "HVACScenarios.xlsx"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_spec = importlib.util.spec_from_file_location("hvac_calc_under_test", str(CALC_PATH))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
HVAC = _mod.HVACGroundTruthCalculator
SENTINEL = _mod.SENTINEL_VALUE

HEAT_Q = "With 3 people home, what heat temperature should I set?"
AC_Q = "With 3 people home, what AC temperature should I set?"


def _eer(seer):
    return -0.02 * seer ** 2 + 1.12 * seer


def _scenario(outdoor, alts, question=AC_Q, **kw):
    s = {"question": question, "location": "X, PA", "square_footage": 1500, "r_value": 13,
         "household_size": 3, "utility_budget": 0.0, "outdoor_temp": float(outdoor),
         "seer": 13, "hvac_age": 10, "housing_type": "Single-family",
         "occupancy_context": "occupied_all_day", "electricity_rate": 0.19,
         "alternatives": [str(a) for a in alts]}
    s.update(kw)
    return s


def _net(calc, outdoor, setpoint, mode, **kw):
    a = dict(square_footage=1500, r_value=13, household_size=3, housing_type="Single-family")
    a.update(kw)
    return calc.calculate_net_heat_gain(float(outdoor), float(setpoint), a["square_footage"],
                                        a["r_value"], a["household_size"], 8.0, a["housing_type"],
                                        include_solar=(mode == "cool"))


@pytest.fixture
def calc():
    return HVAC()


# --- (a) heating efficiency ---------------------------------------------------------

def test_hspf_anchors_and_interpolation(calc):
    assert calc.heating_hspf(13) == pytest.approx(7.7)
    assert calc.heating_hspf(8) == pytest.approx(6.6)
    assert calc.heating_hspf(22) == pytest.approx(10.0)
    assert calc.heating_hspf(12) == pytest.approx(7.1 + 2 * (7.7 - 7.1) / 3)
    vals = [calc.heating_hspf(s) for s in range(6, 31)]
    assert all(b > a for a, b in zip(vals, vals[1:])), "HSPF must rise with SEER"


def test_heating_energy_uses_hspf_not_eer(calc):
    load = 10000.0
    for seer in (8, 13, 16, 22):
        kwh = calc.calculate_energy_consumption(load, seer, "occupied_all_day", mode="heat")
        assert kwh == pytest.approx(load / (calc.heating_hspf(seer) * 1000) * 8)
        assert kwh != pytest.approx(load / (_eer(seer) * 1000) * 8)
        cool = calc.calculate_energy_consumption(load, seer, "occupied_all_day", mode="cool")
        assert cool == pytest.approx(load / (_eer(seer) * 1000) * 8)


def test_cold_heat_scenario_prices_heating_at_hspf(calc):
    sc = _scenario(20, [68, 71, 74], question=HEAT_Q)
    res = calc.calculate_scenario_scores(sc)
    for alt in sc["alternatives"]:
        q = _net(calc, 20, alt, "heat")
        assert q < 0
        expected = (-q) / (calc.heating_hspf(13) * 1000) * 8
        assert res[alt]["raw_kwh"] == pytest.approx(round(expected, 2), abs=1e-9)


# --- (b) mode from the question; load capped by mode --------------------------------

def test_mode_from_question_wording(calc):
    assert calc.hvac_mode_from_question(HEAT_Q) == "heat"
    assert calc.hvac_mode_from_question(AC_Q) == "cool"
    assert calc.hvac_mode_from_question("What temperature should I set?") is None
    assert calc.hvac_mode_from_question("Heat or AC, what should I set?") is None
    assert calc.hvac_mode_from_question(None) is None


def test_unmatched_or_ambiguous_question_is_sentinel(calc):
    for q in ("What temperature should I set?", "Heat or AC, what should I set?"):
        res = calc.calculate_scenario_scores(_scenario(60, [68, 70, 72], question=q))
        for alt in ("68", "70", "72"):
            assert res[alt]["energy_cost_score"] == SENTINEL
            assert res[alt]["comfort_score"] == SENTINEL


def test_explicit_hvac_mode_overrides_question(calc):
    assert calc.resolve_hvac_mode({"question": AC_Q, "hvac_mode": "heat"}) == "heat"
    assert calc.resolve_hvac_mode({"question": HEAT_Q, "hvac_mode": "cool"}) == "cool"
    assert calc.resolve_hvac_mode({"question": HEAT_Q, "hvac_mode": "auto"}) is None
    assert calc.resolve_hvac_mode({"question": HEAT_Q}) == "heat"


def test_every_master_scenario_gets_the_mode_its_question_names(calc):
    m = pd.read_excel(MASTER_XLSX)
    for q in m["question"]:
        heat = bool(re.search(r"\bheat\b", q, re.I))
        ac = bool(re.search(r"\bAC\b", q))
        assert heat != ac
        assert calc.resolve_hvac_mode({"question": q}) == ("heat" if heat else "cool")


def test_no_outdoor_temperature_season_test(calc):
    assert not hasattr(calc, "COMFORT_SEASON_THRESHOLD_F")
    assert not hasattr(calc, "is_cooling_season")
    # The optimum follows the mode whatever the weather.
    for outdoor in (10.0, 66.0, 75.0, 95.0):
        assert calc.calculate_comfort_score(71, outdoor, 2, mode="heat") == 1.0
        assert calc.calculate_comfort_score(76, outdoor, 2, mode="cool") == 1.0


def test_setpoint_just_above_outdoor_in_ac_mode_is_a_cooling_load(calc):
    # 79 F at 78 F outdoors, AC question: internal + solar gains exceed the 1 F loss.
    q = _net(calc, 78, 79, "cool")
    assert q > 0
    res = calc.calculate_scenario_scores(_scenario(78, [75, 77, 79], question=AC_Q))
    assert res["79"]["raw_kwh"] == pytest.approx(round(q / (_eer(13) * 1000) * 8, 2), abs=1e-9)
    assert res["79"]["raw_kwh"] > 0


def test_never_cooling_in_heat_mode(calc):
    # Heat question, internal gains exceed the losses at these setpoints: no load at all.
    kw = dict(r_value=30, household_size=5, housing_type="Apartment")
    sc = _scenario(62, [64, 68, 72], question=HEAT_Q, **kw)
    res = calc.calculate_scenario_scores(sc)
    for alt in ("64", "68", "72"):
        assert _net(calc, 62, alt, "heat", **kw) > 0
        assert res[alt]["raw_kwh"] == 0.0


def test_never_heating_in_ac_mode(calc):
    # AC question with a setpoint far above a cool outdoor temperature: the balance calls
    # for heat, which AC mode does not supply.
    kw = dict(r_value=8, household_size=1)
    q = _net(calc, 40, 85, "cool", **kw)
    assert q < 0
    res = calc.calculate_scenario_scores(_scenario(40, [80, 85, 90], question=AC_Q, **kw))
    assert res["85"]["raw_kwh"] == 0.0


def test_off_free_float_follows_mode(calc):
    for q_text, drift in ((AC_Q, 5), (HEAT_Q, 10)):
        mode = calc.resolve_hvac_mode({"question": q_text})
        res = calc.calculate_scenario_scores(_scenario(60, ["Off", 70, 74], question=q_text,
                                                       household_size=2))
        expected = calc.calculate_comfort_score(60 + drift, 60, 2, mode=mode)
        assert res["Off"]["comfort_score"] == round(
            calc.apply_value_function(expected, calc.VF_COMFORT, "comfort"), 2)
        assert res["Off"]["raw_kwh"] == 0.0


def test_practicality_follows_mode(calc):
    # 77 F setpoint: heat mode penalizes >= 76 F, AC mode does not.
    p_cool = calc.calculate_practicality_score(70.0, 77.0, 5, mode="cool")
    p_heat = calc.calculate_practicality_score(70.0, 77.0, 5, mode="heat")
    assert p_cool > p_heat
    res = calc.calculate_scenario_scores(_scenario(70, [73, 75, 77], question=HEAT_Q, hvac_age=5))
    assert res["77"]["practicality_score"] == round(
        calc.apply_value_function(p_heat, calc.VF_PRACTICALITY, "practicality"), 2)


# --- (c), (d) constants -------------------------------------------------------------

def test_heating_optimum_71(calc):
    assert calc.WINTER_OPTIMAL == 71
    lo, hi = calc.WINTER_COMFORT_RANGE
    assert (lo, hi) == (68, 74) and (lo + hi) / 2 == 71
    assert calc.SUMMER_OPTIMAL == 76
    assert calc.calculate_comfort_score(70, 20, 2, mode="heat") < 1.0


def test_occupant_gain_220_sensible(calc):
    assert calc.OCCUPANT_SENSIBLE_GAIN_BTUH == 220
    q3 = _net(calc, 20, 70, "heat", household_size=3)
    q4 = _net(calc, 20, 70, "heat", household_size=4)
    assert q4 - q3 == pytest.approx(220.0)


# --- budget penalty -------------------------------------------------------------------

def test_budget_penalty_continuous_above_1_5(calc):
    bp = calc.calculate_budget_penalty
    assert bp(70, 100) == 1.0
    assert bp(100, 100) == pytest.approx(0.5)
    assert bp(99.999999, 100) == pytest.approx(0.5, abs=1e-6)
    assert bp(149.999, 100) == pytest.approx(bp(150.0, 100), abs=1e-4)
    assert bp(150, 100) == pytest.approx(0.5 * math.exp(-1.5))
    assert bp(200, 100) == pytest.approx(0.5 * math.exp(-3.0))
    vals = [bp(u, 100) for u in range(80, 300, 5)]
    assert all(v > 0 for v in vals)
    assert all(b < a for a, b in zip(vals, vals[1:]))


# --- conventions ------------------------------------------------------------------

def test_unparseable_alternative_is_sentinel(calc):
    res = calc.calculate_scenario_scores(_scenario(80, ["abc", 74, 77]))
    assert res["abc"]["energy_cost_score"] == SENTINEL


def test_new_bounds_in_value_function(calc):
    assert calc.apply_value_function(0.59, calc.VF_ENERGY_COST, "energy_cost") == pytest.approx(1.0)
    assert calc.apply_value_function(3.27, calc.VF_ENERGY_COST, "energy_cost") == pytest.approx(0.0)
    assert calc.apply_value_function(3.03, calc.VF_ENVIRONMENTAL, "environmental") == pytest.approx(1.0)
    assert calc.apply_value_function(17.90, calc.VF_ENVIRONMENTAL, "environmental") == pytest.approx(0.0)
