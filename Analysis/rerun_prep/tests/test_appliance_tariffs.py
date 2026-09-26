"""Regression tests for the Appliance reference calculator's tariff model (P1-APP).

Pins the Dec 1 2025 - May 31 2026 TOU windows and rates, the super off-peak periods,
Duquesne's flat rate, the corrected city-to-utility mapping and the recomputed bounds.

The calculator file under test is APPLIANCE_CALC_PATH if set, otherwise CALC_PATH below.
After installation, point it at the shipped file:
    APPLIANCE_CALC_PATH="Ground Truth Calculators/ApplianceGroundTruthCalculator.py" \
        python -m pytest Analysis/rerun_prep/tests/test_appliance_tariffs.py
"""
import importlib.util
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CALC_PATH = PROJECT_ROOT / "Analysis" / "rerun_prep" / "calc_new" / "ApplianceGroundTruthCalculator.py"
MASTER_XLSX = PROJECT_ROOT / "Scenario Files" / "ApplianceScenarios.xlsx"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load():
    path = Path(os.environ.get("APPLIANCE_CALC_PATH", CALC_PATH))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    spec = importlib.util.spec_from_file_location("_appliance_calc_under_test", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()
CALC = MOD.ApplianceGroundTruthCalculator()
SENTINEL = MOD.SENTINEL_VALUE

FE_CITY = {"WestPenn": "Greensburg, PA", "Penelec": "Erie, PA", "MetEd": "York, PA"}
# Dec 2025 PTCDefault (FE PA Supp. No. 28) and Supp. No. 20 multipliers (on, off, super).
FE_PTC = {"WestPenn": 0.10947, "Penelec": 0.11747, "MetEd": 0.12965}
FE_MULT = {"WestPenn": (1.6649, 0.8542, 0.6298),
           "Penelec": (1.6792, 0.8482, 0.6510),
           "MetEd": (1.7060, 0.8397, 0.6215)}


def period(hour, location):
    return CALC.determine_rate_period(hour, location)


# ---- PECO: peak 2-6pm, super off-peak midnight-6am ----

@pytest.mark.parametrize("hour", range(0, 6))
def test_peco_super_offpeak_midnight_to_6am(hour):
    assert period(hour, "Philadelphia, PA") == "super_offpeak"


@pytest.mark.parametrize("hour", [6, 7, 13, 18, 22, 23])
def test_peco_offpeak_outside_windows(hour):
    assert period(hour, "Philadelphia, PA") == "offpeak"


@pytest.mark.parametrize("hour", range(14, 18))
def test_peco_peak_2_to_6pm(hour):
    assert period(hour, "Philadelphia, PA") == "peak"


def test_peco_rates_dec2025_ptc_basis():
    assert CALC.calculate_energy_cost(1.0, 15, "Philadelphia, PA") == pytest.approx(0.32747)
    assert CALC.calculate_energy_cost(1.0, 20, "Philadelphia, PA") == pytest.approx(0.08382)
    assert CALC.calculate_energy_cost(1.0, 1, "Philadelphia, PA") == pytest.approx(0.06061)


# ---- FirstEnergy: peak 2-9pm, super off-peak 11pm-6am ----

@pytest.mark.parametrize("utility", sorted(FE_CITY))
@pytest.mark.parametrize("hour", [23, 0, 1, 2, 3, 4, 5])
def test_fe_super_offpeak_11pm_to_6am(utility, hour):
    assert period(hour, FE_CITY[utility]) == "super_offpeak"


@pytest.mark.parametrize("utility", sorted(FE_CITY))
@pytest.mark.parametrize("hour", [6, 7, 13, 21, 22])
def test_fe_offpeak_outside_windows(utility, hour):
    assert period(hour, FE_CITY[utility]) == "offpeak"


@pytest.mark.parametrize("utility", sorted(FE_CITY))
@pytest.mark.parametrize("hour", range(14, 21))
def test_fe_peak_2_to_9pm(utility, hour):
    assert period(hour, FE_CITY[utility]) == "peak"


@pytest.mark.parametrize("utility", sorted(FE_CITY))
def test_fe_rates_are_ptc_times_supplement20_multipliers(utility):
    on, off, sup = FE_MULT[utility]
    ptc = FE_PTC[utility]
    city = FE_CITY[utility]
    assert CALC.calculate_energy_cost(1.0, 15, city) == pytest.approx(ptc * on)
    assert CALC.calculate_energy_cost(1.0, 10, city) == pytest.approx(ptc * off)
    assert CALC.calculate_energy_cost(1.0, 2, city) == pytest.approx(ptc * sup)


# ---- PPL: winter on-peak 4-8pm, two periods ----

@pytest.mark.parametrize("hour", range(16, 20))
def test_ppl_winter_peak_4_to_8pm(hour):
    assert period(hour, "Allentown, PA") == "peak"


@pytest.mark.parametrize("hour", [0, 3, 6, 14, 15, 20, 23])
def test_ppl_offpeak_outside_window_no_super(hour):
    assert period(hour, "Allentown, PA") == "offpeak"


def test_ppl_rates_dec2025_ptc_basis():
    assert CALC.calculate_energy_cost(1.0, 17, "Allentown, PA") == pytest.approx(0.13986)
    assert CALC.calculate_energy_cost(1.0, 15, "Allentown, PA") == pytest.approx(0.11987)


# ---- Duquesne: flat, no window ----

def test_duquesne_has_no_peak_window():
    assert CALC.UTILITY_RATES["Duquesne"]["peak_hours"] is None


@pytest.mark.parametrize("city", ["Pittsburgh, PA", "McKeesport, PA"])
def test_duquesne_flat_every_hour(city):
    costs = {round(CALC.calculate_energy_cost(1.0, h, city), 10) for h in range(24)}
    assert costs == {0.1375}
    assert {period(h, city) for h in range(24)} == {"flat"}


# ---- City-to-utility mapping ----

@pytest.mark.parametrize("city,utility", [
    ("Indiana", "Penelec"), ("Carlisle", "PPL"), ("Reading", "MetEd"),
    ("Lebanon", "MetEd"), ("State College", "WestPenn"), ("Chambersburg", "WestPenn"),
])
def test_corrected_city_mapping(city, utility):
    assert CALC._utility_for_location(f"{city}, PA") == utility


def test_every_master_location_is_mapped():
    locations = pd.read_excel(MASTER_XLSX)["location"].unique()
    for loc in locations:
        assert CALC._utility_for_location(loc) in CALC.UTILITY_RATES


def test_unmapped_city_emits_sentinel():
    scenario = {"location": "Nowhere, PA", "kwh_per_cycle": 1.0, "housing_type": "Apartment",
                "household_size": 2, "appliance": "dishwasher", "utility_budget": 100,
                "baseline_time": "7:00 PM", "alternative_1": "7:00 PM"}
    scores = CALC.calculate_scenario_scores(scenario)
    assert scores["7:00 PM"]["energy_cost_score"] == SENTINEL


# ---- Value-function bounds ----

def test_recomputed_bounds():
    assert tuple(CALC.ENERGY_COST_BOUNDS) == (0.028, 0.774)
    assert tuple(CALC.ENVIRONMENTAL_BOUNDS) == (0.288, 3.643)
