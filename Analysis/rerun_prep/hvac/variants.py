"""Variant calculator classes for per-change impact analysis (harness only).

Every variant subclasses the NEW calculator (calc_new/HVACGroundTruthCalculator.py) and
reverts the changes it should not carry, so "change X alone" = new class with every other
change reverted. The all-reverted variant must reproduce the shipped ground truth exactly;
impact.py checks that before it reports anything.

Changes: hspf (heating at HSPF), mode (operating mode from the question, load capped by
mode), t71 (heating optimum 71 F), gain220 (occupant gain 220 Btu/h), budget (continuous
budget penalty above u = 1.5).

The module path of the new calculator can be overridden with HVAC_CALC_PATH so the same
harness runs against the installed file after P4.
"""
from __future__ import annotations

import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

NEW_PATH = Path(os.environ.get("HVAC_CALC_PATH", C.NEW_DIR / "HVACGroundTruthCalculator.py"))
if not NEW_PATH.is_absolute():
    NEW_PATH = C.PROJECT_ROOT / NEW_PATH
new_mod = C.load_module(NEW_PATH, "hvac_new")
frozen_mod = C.load_module(C.FROZEN_DIR / "HVACGroundTruthCalculator.py", "hvac_frozen_v")
New = new_mod.HVACGroundTruthCalculator
Frozen = frozen_mod.HVACGroundTruthCalculator

OLD_COST_BOUNDS = (0.38, 3.29)
OLD_ENV_BOUNDS = (1.96, 18.04)
CHANGES = ("hspf", "mode", "t71", "gain220", "budget")


class _Capture:
    """Records the unrounded per-alternative cost passed to the energy_cost VF."""
    captured = None

    def apply_value_function(self, raw_value, vf_spec, value_type):
        if value_type == "energy_cost" and type(self).captured is not None:
            type(self).captured.append(raw_value)
        return super().apply_value_function(raw_value, vf_spec, value_type)


def _bounds_vf(cost_bounds, env_bounds):
    """apply_value_function override that swaps the linear cost / env bounds."""
    def apply_value_function(self, raw_value, vf_spec, value_type):
        if value_type in ("energy_cost", "environmental"):
            x_min, x_max = cost_bounds if value_type == "energy_cost" else env_bounds
            u_x = (x_max - raw_value) / (x_max - x_min)
            return max(0.0, min(1.0, u_x))
        return New.apply_value_function(self, raw_value, vf_spec, value_type)
    return apply_value_function


def _old_budget_penalty(self, monthly_cost, monthly_budget):
    """Shipped budget penalty, with the drop to 0 at u >= 1.5."""
    u = monthly_cost / monthly_budget
    if u < 0.80:
        return 1.0
    elif u < 1.0:
        return 1.0 - 2.5 * (u - 0.80)
    elif u < 1.5:
        return 0.5 * math.exp(-3.0 * (u - 1.0))
    return 0.0


def _old_mode_scores(self, scenario):
    """Shipped mode logic on the new class: Comfort switches at outdoor > 75 F, the Off
    drift at the midpoint of the optima, and load / Practicality by outdoor > setpoint.
    Copied from the shipped calculate_scenario_scores, with the new efficiency hook."""
    SENT = new_mod.SENTINEL_VALUE
    ff_cool = scenario['outdoor_temp'] > (self.SUMMER_OPTIMAL + self.WINTER_OPTIMAL) / 2.0
    comfort_mode = 'cool' if scenario['outdoor_temp'] > 75 else 'heat'
    raw_results = {}
    for alt in scenario['alternatives']:
        if 'off' in alt.lower():
            paren_match = re.search(r'\(.*?(\d+).*?\)', alt)
            if paren_match:
                effective_temp = float(paren_match.group(1))
            else:
                effective_temp = self._free_float_temp(scenario['outdoor_temp'], ff_cool)
        else:
            numbers = re.findall(r'\d+', alt)
            if not numbers:
                raw_results[alt] = None
                continue
            effective_temp = float(numbers[0])
        is_cooling = scenario['outdoor_temp'] > effective_temp
        args = (scenario['outdoor_temp'], effective_temp, scenario['square_footage'],
                scenario['r_value'], scenario['household_size'],
                scenario.get('ceiling_height', 8.0), scenario.get('housing_type', 'Single-family'))
        load = self.calculate_cooling_load(*args) if is_cooling else self.calculate_heating_load(*args)
        mode = 'cool' if is_cooling else 'heat'
        kwh = self.calculate_energy_consumption(
            load, scenario['seer'],
            occupancy_context=self.normalize_occupancy_context(
                scenario.get('occupancy_context', 'occupied_all_day')), mode=mode)
        energy_cost = kwh * scenario.get('electricity_rate', self.ELECTRICITY_RATE_PA)
        emissions = kwh * self.emissions_factor_for_occupancy(
            scenario.get('occupancy_context', 'occupied_all_day'))
        if 'off' in alt.lower():
            kwh = energy_cost = emissions = 0.0
        comfort = self.calculate_comfort_score(effective_temp, scenario['outdoor_temp'],
                                               scenario['household_size'], mode=comfort_mode)
        practicality = self.calculate_practicality_score(
            scenario['outdoor_temp'], effective_temp, scenario['hvac_age'],
            scenario.get('maintenance_level', 'moderate'), mode=mode)
        raw_results[alt] = {'kwh': kwh, 'energy_cost_dollars': energy_cost,
                            'emissions_lbs': emissions, 'comfort_raw': comfort,
                            'practicality_raw': practicality}
    final_scores = {}
    utility_budget = float(scenario.get('utility_budget', 0.0))
    for alt, raw in raw_results.items():
        if raw is None:
            final_scores[alt] = {k: SENT for k in (
                'energy_cost_score', 'environmental_score', 'comfort_score',
                'practicality_score', 'raw_kwh', 'raw_cost', 'raw_emissions')}
            continue
        energy_vf = self.apply_value_function(raw['energy_cost_dollars'], self.VF_ENERGY_COST, 'energy_cost')
        env_vf = self.apply_value_function(raw['emissions_lbs'], self.VF_ENVIRONMENTAL, 'environmental')
        comfort_vf = self.apply_value_function(raw['comfort_raw'], self.VF_COMFORT, 'comfort')
        practicality_vf = self.apply_value_function(raw['practicality_raw'], self.VF_PRACTICALITY, 'practicality')
        if utility_budget > 0:
            monthly_cost = self.calculate_monthly_cost(raw['energy_cost_dollars'], periods_per_month=90)
            energy_vf = energy_vf * self.calculate_budget_penalty(monthly_cost, utility_budget)
        final_scores[alt] = {
            'energy_cost_score': round(energy_vf, 2), 'environmental_score': round(env_vf, 2),
            'comfort_score': round(comfort_vf, 2), 'practicality_score': round(practicality_vf, 2),
            'raw_kwh': round(raw['kwh'], 2), 'raw_cost': round(raw['energy_cost_dollars'], 2),
            'raw_emissions': round(raw['emissions_lbs'], 2)}
    return final_scores


def _solar_both_net_gain(self, *args, include_solar=True, **kw):
    """Sensitivity only: solar credited in heat mode too."""
    return New.calculate_net_heat_gain(self, *args, include_solar=True, **kw)


def make_variant(keep=CHANGES, cost_bounds=None, env_bounds=None, occupant_gain=None,
                 capture=False, name=None, solar_both=False):
    """Build a calculator class carrying only the changes in `keep`.
    cost_bounds/env_bounds: None = whatever the new class has; otherwise (min, max)."""
    attrs = {}
    if "hspf" not in keep:
        attrs["heating_hspf"] = lambda self, seer: (-0.02 * seer ** 2) + (1.12 * seer)
    if "t71" not in keep:
        attrs["WINTER_OPTIMAL"] = 70
    if "gain220" not in keep:
        attrs["OCCUPANT_SENSIBLE_GAIN_BTUH"] = 400
    if occupant_gain is not None:
        attrs["OCCUPANT_SENSIBLE_GAIN_BTUH"] = occupant_gain
    if "budget" not in keep:
        attrs["calculate_budget_penalty"] = _old_budget_penalty
    if "mode" not in keep:
        attrs["calculate_scenario_scores"] = _old_mode_scores
    if solar_both:
        attrs["calculate_net_heat_gain"] = _solar_both_net_gain
    if cost_bounds is not None or env_bounds is not None:
        attrs["apply_value_function"] = _bounds_vf(cost_bounds or OLD_COST_BOUNDS,
                                                   env_bounds or OLD_ENV_BOUNDS)
    bases = (_Capture, New) if capture else (New,)
    if capture:
        attrs["captured"] = []
    return type(name or ("V_" + "_".join(keep) if keep else "V_none"), bases, attrs)


def frozen_capture_class():
    return type("FrozenCapture", (_Capture, Frozen), {"captured": []})
