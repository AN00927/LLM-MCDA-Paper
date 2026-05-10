import sys
import pandas as pd
import math
import logging
import numpy as np
import re
from typing import Dict, List, Tuple
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from model_config import CRITERION_WEIGHTS


class HVACGroundTruthCalculator:
    # PJM marginal emissions factors (lbs CO2/kWh). Source: PJM 2022 CO2/SO2/NOx Emissions Report (April 2023).
    # Marginal, not average, is what we want here because it tracks what actually gets shifted at the edge.
    # Peak is 7am-11pm (16h) and off-peak is 11pm-7am (8h) per PJM.
    EMISSIONS_FACTOR_PEAK = 1.041     # PJM peak (1041 lbs/MWh)
    EMISSIONS_FACTOR_OFFPEAK = 0.976  # PJM off-peak (976 lbs/MWh)
    EMISSIONS_PEAK_HOURS_PER_DAY = 16
    EMISSIONS_OFFPEAK_HOURS_PER_DAY = 8

    # PA residential electricity price from EIA (2024)
    ELECTRICITY_RATE_PA = 0.19  # $/kWh; flat-rate default (see modeling choice above)
    SUMMER_COMFORT_RANGE = (73, 79)
    SUMMER_OPTIMAL = 76
    WINTER_COMFORT_RANGE = (68, 75)
    WINTER_OPTIMAL = 70

    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Management Science 26(8):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact - physical units have linear marginal value
    # Note: This represents a MODELING ASSUMPTION rather than an empirically validated preference.
    # While some environmental psychology literature supports linear preferences for physical
    # impact metrics (e.g., CO2 levels), the specific claim in Kotchen & Moore (2007) does not
    # explicitly endorse this for utility function specification.
    # For MAVT framework justification, see:
    # - Keeney, R. L., & Raiffa, H. (1976). Decisions with Multiple Objectives: Preferences 
    #   and Value Trade-offs. Wiley. (Foundation for Multi-Attribute Value Theory axioms)
    # Linear VF justification in this context: When environmental impacts are framed in 
    # absolute physical units (lbs CO₂), a linear preference is a conservative modeling choice
    # that treats equal changes in emissions as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"
    def calculate_cooling_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int, household_size: int = 3,
                               ceiling_height: float = 8.0, ach: float = 0.35,
                               housing_type: str = "Single-family") -> float:
        """Calculate cooling load."""
        delta_t = outdoor_temp - indoor_temp

        # Adjust by housing type. Typical multipliers from ACCA Manual J:
        # - Single-family (2-story typical): 1.7 (includes roof, walls, floor exposures)
        # - Apartment (mid-unit typical): 1.2 (shared walls reduce exposure)
        # - Townhouse (end-unit typical): 1.5 (one or two shared walls)
         # Twin semi-detached (PA regional term). One shared party wall reduces exposed envelope vs. Single-family (1.7).
        housing_multipliers = {
            "Single-family": 1.7,
            "Apartment": 1.2,
            "Condo": 1.2,      # Shared walls/floor/ceiling; same exposure profile as Apartment
            "Townhouse": 1.5,
            "Rowhouse": 1.5,
            "Twin": 1.6,  
        }
        envelope_multiplier = housing_multipliers.get(housing_type, 1.7)
        envelope_area = square_footage * envelope_multiplier

        u_factor = 1.0 / r_value

        conductive_load = u_factor * envelope_area * delta_t

        # Formula: occupants (400 BTU/hr each) + lighting & equipment (1.0 BTU/hr/sqft) + baseline (800)
        # For 3-person, 1500 sqft home: (3 × 400) + (1500 × 1.0) + 800 = 3,500 BTU/hr (more realistic)
        # Source: ASHRAE Handbook of Fundamentals, Chapter 18, Table 1
        internal_gains = (household_size * 400) + (square_footage * 1.0) + 800

        window_area = square_footage * 0.15
        solar_gains = window_area * 20

        # Use the ASHRAE-style ventilation formula instead of a rough multiplier
        # ventilation_load = 1.08 × (square_footage × ceiling_height × ACH / 60) × ΔT
        # ACH is about 0.35 for modern construction, and 1.08 is the air factor
        ventilation_cfm = (square_footage * ceiling_height * ach) / 60.0
        ventilation_load = 1.08 * ventilation_cfm * delta_t

        total_load = conductive_load + internal_gains + solar_gains + ventilation_load
        print(f"  to Load calculated: {total_load:,.0f} BTU/hr (internal_gains={internal_gains:,.0f}, "
              f"ventilation={ventilation_load:,.0f}, envelope_mult={envelope_multiplier})")
        return max(0, total_load)

    def calculate_heating_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int, household_size: int = 3,
                               ceiling_height: float = 8.0, ach: float = 0.35,
                               housing_type: str = "Single-family") -> float:
        """Calculate heating load."""
        delta_t = indoor_temp - outdoor_temp

        # Adjust by housing type. Typical multipliers from ACCA Manual J:
        # - Single-family (2-story typical): 1.7
        # - Apartment (mid-unit typical): 1.2 (shared walls reduce exposure)
        # - Townhouse (end-unit typical): 1.5 (one or two shared walls)
        # TODO(D4): "Twin" appears in TestScenarios but the ACCA Manual J
        # multiplier is unconfirmed. Currently falls through to the 1.7 default
        # via the .get() below — research and add an explicit entry.
        housing_multipliers = {
            "Single-family": 1.7,
            "Apartment": 1.2,
            "Condo": 1.2,      # Shared walls/floor/ceiling; same exposure profile as Apartment
            "Townhouse": 1.5,
            "Rowhouse": 1.5,
            # "Twin": <TODO_VALUE>,
        }
        envelope_multiplier = housing_multipliers.get(housing_type, 1.7)
        envelope_area = square_footage * envelope_multiplier

        u_factor = 1.0 / r_value

        conductive_loss = u_factor * envelope_area * delta_t

        # Same formula as cooling load: occupants + lighting/equipment + baseline
        # Source: ASHRAE Handbook of Fundamentals, Chapter 18, Table 1
        internal_gains = (household_size * 400) + (square_footage * 1.0) + 800

        # Use the same ASHRAE-style ventilation formula here too
        # infiltration_loss = 1.08 × (square_footage × ceiling_height × ACH / 60) × ΔT
        infiltration_cfm = (square_footage * ceiling_height * ach) / 60.0
        infiltration_loss = 1.08 * infiltration_cfm * delta_t

        total_load = conductive_loss + infiltration_loss - internal_gains
        print(f"  to Load calculated: {total_load:,.0f} BTU/hr (internal_gains={internal_gains:,.0f}, "
              f"infiltration={infiltration_loss:,.0f}, envelope_mult={envelope_multiplier})")
        return max(0, total_load)

    def calculate_energy_consumption(self, load_btu_hr: float, seer: int,
                                     hvac_age: int, occupancy_context: str, hours: float = 8,
                                     maintenance_level: str = 'moderate') -> float:
        """Calculate energy consumption."""
        maintenance_rates = {
            'good': 0.005,  # 0.5%/year with annual/biannual maintenance
            'moderate': 0.010,  # 1.0%/year with occasional maintenance
            'poor': 0.015  # 1.5%/year with little/no maintenance
        }

        base_rate = maintenance_rates.get(maintenance_level, 0.010)

        # Front-loaded degradation: accelerated first 10 years, slower thereafter
        if hvac_age <= 10:
            # Accelerated early loss (1.5× base rate)
            effective_rate = base_rate * 1.5
            total_degradation = hvac_age * effective_rate
        else:
            # First 10 years at accelerated rate
            early_degradation = 10 * (base_rate * 1.5)
            # Remaining years at slower tail rate (0.5× base rate)
            later_years = hvac_age - 10
            later_degradation = later_years * (base_rate * 0.5)
            total_degradation = early_degradation + later_degradation

        # Cap maximum degradation at 30% (realistic upper bound)
        total_degradation = min(total_degradation, 0.30)

        # Calculate effective SEER after degradation
        effective_seer = seer * (1 - total_degradation)

        print(f"  to SEER degradation: {seer} to {effective_seer:.1f} "
              f"(age={hvac_age}yr, {maintenance_level}, {total_degradation * 100:.1f}% loss)")

          # Formula: EER = -0.02 × SEER² + 1.12 × SEER
       # Source: AHRI Standard 210/240 (Air Conditioning, Heating, and Refrigeration Institute)
        eer_estimated = (-0.02 * effective_seer ** 2) + (1.12 * effective_seer)

        # Calculate power draw
        kw = (load_btu_hr / eer_estimated) / 1000
        occupancy_context = self.normalize_occupancy_context(occupancy_context)

        if occupancy_context == "occupied_all_day":
            runtime_multiplier = 1.0
        elif occupancy_context.startswith("unoccupied_"):
            hours_match = re.search(r"(\d+)", occupancy_context)
            if hours_match:
                hours_away = max(0, min(int(hours_match.group(1)), 24))
            else:
                hours_away = 8
            runtime_multiplier = 1.0 - (hours_away / 24) * 0.5
        elif occupancy_context == "occupied_sleep":
            runtime_multiplier = 0.75
        else:
            runtime_multiplier = 1.0
        total_kwh = kw * hours * runtime_multiplier

        print(f"  to Energy consumption: {total_kwh:.2f} kWh over {hours} hours")
        return total_kwh

    def calculate_comfort_score(self, indoor_temp: float, outdoor_temp: float,
                                household_size: int) -> float:
        """Calculate comfort score."""
        # Tent comfort function around PMV-aligned indoor setpoints for mechanical
        # HVAC. Optimal indoor 76F in cooling mode (outdoor > 75F) and 70F in
        # heating mode, consistent with ASHRAE 55-2020 Section 5.2 (PMV/PPD method)
        # operative-temperature recommendations for sedentary metabolic activity
        # and typical clothing insulation (1.0 clo winter, 0.5 clo summer).
        # Score = 10 - |indoor - optimal|, clipped to [0, 10]. The -1.0/F slope
        # follows the PPD response in Fanger (1970, Thermal Comfort, Danish
        # Technical Press): roughly 5-10 percentage-point increase in PPD per F
        # outside the comfort band, which on a 0-10 scale maps to a comparable
        # score decrement. A prior -2.0/F out-of-band slope was over-aggressive
        # (producing 0/10 at indoor 83F when outdoor 88F, which is not consistent
        # with the PPD literature on hot-weather indoor tolerance).
        # An earlier revision used the ASHRAE 55 adaptive method (T_comf = 0.31 *
        # T_rm + 17.8) to slide the optimal with outdoor temperature, but the
        # adaptive method is formally applicable only to occupant-controlled,
        # naturally conditioned (non-mechanically-cooled) spaces (de Dear & Brager
        # 2002; Nicol & Humphreys 2002), which is not the regime our scenarios
        # describe. The fixed-setpoint tent is therefore the standards-compliant
        # choice for mechanical HVAC; the adaptive citations are retained as
        # context for why a sliding-target alternative was considered and rejected.
        # Sources: ashrae55-2020 Sec 5.2; fanger1970; dedear2002; nicol2002.
        optimal = 76 if outdoor_temp > 75 else 70
        deviation = abs(indoor_temp - optimal)
        comfort_score = 10.0 - deviation

        if household_size > 3:
            size_penalty = (household_size - 3) * 0.3
            comfort_score -= size_penalty * (deviation / 3.0)

        return max(0.0, min(10.0, comfort_score))

    def calculate_practicality_score(self, outdoor_temp: float, indoor_temp: float,) -> float:
        """Calculate practicality score."""
        if outdoor_temp > 75:  # Cooling mode
            if indoor_temp >= 82:
                extremity_penalty = (indoor_temp - 82) * 1.5
            elif indoor_temp <= 71:
                extremity_penalty = (71 - indoor_temp) * 1.0
            else:
                extremity_penalty = 0
        else:  # Heating mode
            if indoor_temp <= 63:
                extremity_penalty = (63 - indoor_temp) * 1.8
            elif indoor_temp >= 76:
                extremity_penalty = (indoor_temp - 76) * 0.8
            else:
                extremity_penalty = 0

        base_score = 10 - extremity_penalty

        base_score = max(0.5, base_score)

        # Component 2: change in T operational feasibility
        # Large ΔT indicates system operating at limits; lower reliability/higher failure risk
        delta_t = abs(outdoor_temp - indoor_temp)
        if delta_t < 10:
            delta_t_multiplier = 1.0
        elif delta_t < 20:
            delta_t_multiplier = 0.95
        elif delta_t < 35:
            delta_t_multiplier = 0.85
        else:
            delta_t_multiplier = 0.70

        base_score *= delta_t_multiplier

        return max(1.5, min(10.0, base_score))

    def calculate_monthly_cost(self, per_period_cost: float, periods_per_month: int = 90) -> float:
        """Calculate monthly cost."""
        return per_period_cost * periods_per_month

    def calculate_budget_penalty(self, monthly_cost: float, monthly_budget: float) -> float:
        """Calculate budget penalty."""
        if monthly_budget <= 0:
            return 1.0  # No budget constraint

        utilization = monthly_cost / monthly_budget

        if utilization < 0.80:
            # Mental budget safety margin (Thaler 1999)
            return 1.0

        elif utilization < 1.0:
            # Linear decline as budget limit approached (Heath & Soll 1996)
            return 1.0 - 2.5 * (utilization - 0.80)

        elif utilization < 1.5:
            # Exponential loss aversion under budget violation (Prelec & Loewenstein 1998; Heutel 2017)
            import math
            return 0.5 * math.exp(-3.0 * (utilization - 1.0))

        else:
            # Infeasible option eliminated (Gathergood 2012)
            return 0.0

    @staticmethod
    def parse_utility_budget(budget_value) -> float:
        """Parse utility budget values that may include currency symbols or spacing."""
        if budget_value is None or pd.isna(budget_value):
            return 0.0

        if isinstance(budget_value, (int, float, np.integer, np.floating)):
            return max(0.0, float(budget_value))

        cleaned = re.sub(r"[^0-9.\-]", "", str(budget_value))
        if not cleaned:
            return 0.0

        try:
            return max(0.0, float(cleaned))
        except ValueError:
            return 0.0

    @classmethod
    def emissions_factor_for_occupancy(cls, occupancy_context: str) -> float:
        """Return the PJM marginal CO2 factor (lbs/kWh) implied by an HVAC occupancy
        context. HVAC alternatives have no explicit start_time, so we infer when the
        system is running from the occupancy pattern:
          - occupied_all_day: runs across the full 24h, weighted by peak/off-peak hours
          - occupied_sleep:   runs during the 8h off-peak window (11pm-7am)
          - unoccupied_<H>:   runs while the household is away. If H <= 16, all of those
                              hours fit within the daytime peak window so use the peak
                              factor. If H > 16, hours overflow into off-peak and we
                              weight accordingly.
        """
        ctx = cls.normalize_occupancy_context(occupancy_context)
        peak = cls.EMISSIONS_FACTOR_PEAK
        off = cls.EMISSIONS_FACTOR_OFFPEAK
        peak_h = cls.EMISSIONS_PEAK_HOURS_PER_DAY
        off_h = cls.EMISSIONS_OFFPEAK_HOURS_PER_DAY

        if ctx == "occupied_sleep":
            return off

        if ctx == "occupied_all_day":
            return (peak_h * peak + off_h * off) / (peak_h + off_h)

        if ctx.startswith("unoccupied_"):
            hours_match = re.search(r"(\d+)", ctx)
            hours_away = int(hours_match.group(1)) if hours_match else 8
            hours_away = max(0, min(hours_away, 24))
            if hours_away <= peak_h:
                return peak
            offpeak_hours = hours_away - peak_h
            return (peak_h * peak + offpeak_hours * off) / hours_away

        return (peak_h * peak + off_h * off) / (peak_h + off_h)

    @staticmethod
    def normalize_occupancy_context(occupancy_value) -> str:
        """Normalize occupancy context values to expected internal tokens."""
        if occupancy_value is None or pd.isna(occupancy_value):
            return "occupied_all_day"

        value = str(occupancy_value).strip().lower()

        if value in {"occupied_all_day", "standard", "occupied", "home_all_day"}:
            return "occupied_all_day"

        if value in {"occupied_sleep", "sleep", "night", "overnight_sleep", "overnight"}:
            return "occupied_sleep"

        if value.startswith("unoccupied"):
            hours_match = re.search(r"(\d+)", value)
            if hours_match:
                hours_away = max(0, min(int(hours_match.group(1)), 24))
                return f"unoccupied_{hours_away}"
            return "unoccupied_8"

        return "occupied_all_day"

    def apply_value_function(self, raw_value: float, vf_spec: str, value_type: str) -> float:
        """Apply value function."""
        reference_ranges = {
                'energy_cost': {
        # 5th-95th percentile of the actual scenario-set cost distribution (8h
        # window at $0.19/kWh). Dataset-percentile bounds are chosen over a wider
        # physics envelope so that scores spread meaningfully across the [0,10]
        # scale for typical PA residential alternatives; this is a deliberate
        # entropy-driven normalization choice (Roszkowska 2026) and is documented
        # as a paper limitation. Cost endpoints are still anchored in real
        # residential studies:
        #   Min (efficient): Huyen & Cetin (2019), Energies 12(1):188;
        #     Kim et al. (2024), Building Simulation; Cetin & Novoselac (2015),
        #     EB 96:210.
        #   Max (degraded):  Alves et al. (2016), EB 130:408;
        #     Krarti & Howarth (2020), JBE 31:101457.
        'min': 0.47,
        'max': 3.31,
        'decreasing': True
    },
    'environmental': {
        # Bounds derived from the same 5th-95th percentile cost envelope as
        # energy_cost ($0.47-$3.31 at $0.19/kWh flat = 2.474-17.421 kWh) but
        # applied against PJM marginal emissions factors (0.976 off-peak, 1.041
        # peak):
        #   min = 2.474 kWh x 0.976 lbs/kWh = 2.42 lbs CO2  (best case: fully off-peak)
        #   max = 17.421 kWh x 1.041 lbs/kWh = 18.14 lbs CO2 (worst case: fully peak)
        # Source: PJM 2022 Emissions Report (April 2023).
        # Note for HVAC: alternatives within one scenario share the same emission
        # factor (collinearity documented as paper limitation - all alternatives
        # evaluated at same moment, differing only in load magnitude).
        'min': 2.42,
        'max': 18.14,
        'decreasing': True
    },
            'comfort': {
                'min': 0.0,
                'max': 10.0,
                'decreasing': False
            },
            'practicality': {
                # Match calculation floor (0.5) so VF mapping doesn't collapse
                # the raw floor to a utility of exactly zero.
                'min': 0.5,
                'max': 10.0,
                'decreasing': False
            }
        }

        ref = reference_ranges[value_type]
        x_min = ref['min']
        x_max = ref['max']

        x = raw_value

        vf_type = vf_spec.split(',')[0].strip().lower()

        # Normalize (now can go outside [0,1] range)
        if ref['decreasing']:
            x_normalized = (x_max - x) / (x_max - x_min)
        else:
            x_normalized = (x - x_min) / (x_max - x_min)

        # Apply transformation
        if vf_type == 'linear':
            u_x = x_normalized

        elif vf_type == 'polynomial':
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0
            u_x = x_normalized ** a

        elif vf_type == 'exponential':
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0
            if a == 0:
                u_x = x_normalized
            else:
                u_x = (1 - math.exp(a * x_normalized)) / (1 - math.exp(a))

        elif vf_type == 'logarithmic':
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0
            if a == -1:
                u_x = x_normalized
            else:
                # Handle negative x_normalized (better than best case)
                if a * x_normalized + 1 <= 0:
                    u_x = 0.0
                else:
                    u_x = math.log(a * x_normalized + 1) / math.log(a + 1)

        else:
            u_x = x_normalized

        # NOW clamp the final score to [0, 10]
        return max(0.0, min(10.0, u_x * 10.0))

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        """Calculate scenario scores."""
        is_cooling = scenario['outdoor_temp'] > 75

        raw_results = {}

        for alt in scenario['alternatives']:
            if isinstance(alt, str):
                import re

                # Enhanced parsing for "Off" alternatives
                # Handles: "Off", "Off (55)", "Off (let drift to 85)", etc.
                if 'off' in alt.lower():
                    paren_match = re.search(r'\(.*?(\d+).*?\)', alt)
                    if paren_match:
                        effective_temp = float(paren_match.group(1))
                    elif 'to' in alt.lower():
                        to_match = re.search(r'to\s+(\d+)', alt, re.IGNORECASE)
                        if to_match:
                            effective_temp = float(to_match.group(1))
                        else:
                            # Fallback to drift calculation
                            if is_cooling:
                                effective_temp = scenario['outdoor_temp'] - 5
                            else:
                                effective_temp = scenario['outdoor_temp'] + 5
                    else:
                        if is_cooling:
                            effective_temp = scenario['outdoor_temp'] - 5
                        else:
                            effective_temp = scenario['outdoor_temp'] + 5
                else:
                    # Not an "off" alternative - extract first number found
                    numbers = re.findall(r'\d+', alt)
                    if numbers:
                        effective_temp = float(numbers[0])
                    else:
                        print(f"   Could not parse alternative: {alt}")
                        continue
            else:
                effective_temp = float(alt)

            if is_cooling:
                load = self.calculate_cooling_load(
                    scenario['outdoor_temp'],
                    effective_temp,
                    scenario['square_footage'],
                    scenario['r_value'],
                    scenario['household_size'],
                    scenario.get('ceiling_height', 8.0),
                    scenario.get('ach', 0.35),
                    scenario.get('Housing Type', 'Single-family')
                )
            else:
                load = self.calculate_heating_load(
                    scenario['outdoor_temp'],
                    effective_temp,
                    scenario['square_footage'],
                    scenario['r_value'],
                    scenario['household_size'],
                    scenario.get('ceiling_height', 8.0),
                    scenario.get('ach', 0.35),
                    scenario.get('Housing Type', 'Single-family')
                )

            kwh = self.calculate_energy_consumption(
                load,
                scenario['seer'],
                scenario['hvac_age'],
                occupancy_context=self.normalize_occupancy_context(
                    scenario.get('occupancy_context', 'occupied_all_day')
                ),
                maintenance_level=scenario.get('maintenance_level', 'moderate')
            )

            energy_cost = kwh * scenario.get('electricity_rate', self.ELECTRICITY_RATE_PA)
            emission_factor = self.emissions_factor_for_occupancy(
                scenario.get('occupancy_context', 'occupied_all_day')
            )
            emissions = kwh * emission_factor

            # When alternative is "off", set energy-related values to 0 (physically correct).
            # Still use drift temp for comfort/practicality scoring.
            if 'off' in alt.lower():
                kwh = 0.0
                energy_cost = 0.0
                emissions = 0.0
                print(f"  OFF alternative detected: Setting kwh=0, cost=0, emissions=0 "
                      f"(system inactive). Using drift temp ({effective_temp}F) for comfort/practicality.")

            comfort = self.calculate_comfort_score(
                effective_temp,
                scenario['outdoor_temp'],
                scenario['household_size']
            )

            practicality = self.calculate_practicality_score(
                scenario['outdoor_temp'],
                effective_temp,
            )
            raw_results[alt] = {
                'kwh': kwh,
                'energy_cost_dollars': energy_cost,
                'emissions_lbs': emissions,
                'comfort_raw': comfort,
                'practicality_raw': practicality
            }

        final_scores = {}
        utility_budget = self.parse_utility_budget(scenario.get('utility_budget', 0.0))

        for alt, raw in raw_results.items():


            energy_vf = self.apply_value_function(
                raw['energy_cost_dollars'],
                self.VF_ENERGY_COST,
                'energy_cost'
            )

            env_vf = self.apply_value_function(
                raw['emissions_lbs'],
                self.VF_ENVIRONMENTAL,
                'environmental'
            )

            comfort_vf = self.apply_value_function(
                raw['comfort_raw'],
                self.VF_COMFORT,
                'comfort'
            )

            practicality_vf = self.apply_value_function(
                raw['practicality_raw'],
                self.VF_PRACTICALITY,
                'practicality'
            )

            # Apply budget penalty if budget constraint exists
            if utility_budget > 0:
                # Convert 8-hour cost to monthly estimate (30 days)
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost_dollars'],
                    periods_per_month=90 # 24 hours per day divided by 8 hour decision period
                )

                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    utility_budget
                )

                # Apply penalty to energy cost score
                energy_vf_penalized = energy_vf * budget_penalty

                print(f"  Budget check: ${monthly_cost:.2f}/month vs ${utility_budget:.2f} budget")
                print(
                    f"  Utilization: {monthly_cost / utility_budget * 100:.1f}% to penalty: {budget_penalty:.3f}")
                print(f"  Energy score: {energy_vf:.2f} to {energy_vf_penalized:.2f} (after penalty)")

                energy_vf = energy_vf_penalized

            final_scores[alt] = {
                'energy_cost_score': round(energy_vf, 2),
                'environmental_score': round(env_vf, 2),
                'comfort_score': round(comfort_vf, 2),
                'practicality_score': round(practicality_vf, 2),
                'raw_kwh': round(raw['kwh'], 2),
                'raw_cost': round(raw['energy_cost_dollars'], 2),
                'raw_emissions': round(raw['emissions_lbs'], 2)
            }

            print(f"  to FINAL SCORES:")
            print(
                f"     Energy: {energy_vf:.2f}, Environmental: {env_vf:.2f}, Comfort: {comfort_vf:.2f}, Practicality: {practicality_vf:.2f}\n")

        return final_scores


def process_hvac_scenarios(
    csv_filename: str = str(SCENARIO_DIR / "HVACScenarios.csv"),
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_hvac.csv")):
    """Process hvac scenarios."""
    csv_path = Path(csv_filename)
    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

    print(f"Found {len(df)} scenarios")

    calculator = HVACGroundTruthCalculator()

    results = []

    for idx, row in df.iterrows():
        print(f"Processing scenario {idx + 1}/{len(df)}: {row['Location']}")
        electricity_rate = 0.19

        alternatives = []
        for alt_col in ['Alternative 1', 'Alternative 2', 'Alternative 3']:
            alt_val = str(row[alt_col]).strip()

            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)

        scenario = {
            'question': row['Question'],
            'location': row['Location'],
            'square_footage': int(row['Square Footage']),
            'r_value': int(row['R-Value']),
            'household_size': int(row['Household Size']),
            'utility_budget': calculator.parse_utility_budget(row.get('Utility Budget', 0)),
            'outdoor_temp': float(row['Outdoor Temp']),
            'seer': int(row['SEER']),
            'hvac_age': int(row['HVAC Age']),
            'occupancy_context': calculator.normalize_occupancy_context(
                row.get('Occupancy Context', row.get('Occupancy context', 'occupied_all_day'))
            ),
            'electricity_rate': electricity_rate,
            'alternatives': alternatives,
        }
        try:
            scores = calculator.calculate_scenario_scores(scenario)
            alts_for_ranking = [
                {
                    "alternative": alt,
                    "energy_cost": scores[alt]["energy_cost_score"],
                    "environmental": scores[alt]["environmental_score"],
                    "comfort": scores[alt]["comfort_score"],
                    "practicality": scores[alt]["practicality_score"]
                }
                for alt in scores
            ]
            ranking_result = apply_mavt_ranking(alts_for_ranking)
            for alt, alt_scores in scores.items():
                result_row = {
                    'scenario_id': idx,
                    'question': row['Question'],
                    'location': row['Location'],
                    'square_footage': row['Square Footage'],
                    'insulation': row.get('Insulation', ''),
                    'household_size': row['Household Size'],
                    'utility_budget': row.get('Utility Budget', ''),
                    'housing_type': row.get('Housing Type', ''),
                    'outdoor_temp': row['Outdoor Temp'],
                    'house_age': row.get('House Age', ''),
                    'alternative': alt,
                    'energy_cost_score': alt_scores['energy_cost_score'],
                    'environmental_score': alt_scores['environmental_score'],
                    'comfort_score': alt_scores['comfort_score'],
                    'practicality_score': alt_scores['practicality_score'],
                    'mavt_score': ranking_result["weighted_scores"][list(scores.keys()).index(alt)],
                    'rank': ranking_result["ranks"][list(scores.keys()).index(alt)],
                    'raw_kwh': alt_scores['raw_kwh'],
                    'raw_cost': alt_scores['raw_cost'],
                    'raw_emissions': alt_scores['raw_emissions']
                }
                results.append(result_row)

        except Exception as e:
            print(f"ERROR processing scenario {idx}: {e}")
            continue

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_path, index=False)

    print(f"\nGround truth saved to {output_path}")
    print(f"Total alternatives scored: {len(results_df)}")
    return results_df

def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    """Apply mavt ranking."""
    try:
        alternatives = [alt["alternative"] for alt in alternatives_scores]

        # Calculate weighted sum for each alternative
        weighted_scores = []
        for alt_scores in alternatives_scores:
            weighted_sum = (
                    CRITERION_WEIGHTS["energy_cost"] * alt_scores["energy_cost"] +
                    CRITERION_WEIGHTS["environmental"] * alt_scores["environmental"] +
                    CRITERION_WEIGHTS["comfort"] * alt_scores["comfort"] +
                    CRITERION_WEIGHTS["practicality"] * alt_scores["practicality"]
            )
            weighted_scores.append(weighted_sum)

        # Rank alternatives (higher weighted sum = better = lower rank number)
        ranked_indices = np.argsort(weighted_scores)[::-1]  # Descending order
        ranked_alternatives = [alternatives[i] for i in ranked_indices]

        # Create rank numbers (1 = best, 2 = second, 3 = third)
        ranks = [0] * len(alternatives)
        for rank_position, alt_index in enumerate(ranked_indices):
            ranks[alt_index] = rank_position + 1

        return {
            "ranked_alternatives": ranked_alternatives,
            "ranks": ranks,
            "weighted_scores": weighted_scores
        }

    except Exception as e:
        logging.error(f"MAVT ranking failed: {e}")

        # Fallback: rank by average score
        avg_scores = []
        for alt_scores in alternatives_scores:
            avg = np.mean([
                alt_scores["energy_cost"],
                alt_scores["environmental"],
                alt_scores["comfort"],
                alt_scores["practicality"]
            ])
            avg_scores.append(avg)

        ranked_indices = np.argsort(avg_scores)[::-1]
        ranked_alternatives = [alternatives[i] for i in ranked_indices]

        ranks = [0] * len(alternatives)
        for rank_position, alt_index in enumerate(ranked_indices):
            ranks[alt_index] = rank_position + 1

        return {
            "ranked_alternatives": ranked_alternatives,
            "ranks": ranks,
            "weighted_scores": avg_scores,
            "error": str(e)
        }


if __name__ == "__main__":
    process_hvac_scenarios()
