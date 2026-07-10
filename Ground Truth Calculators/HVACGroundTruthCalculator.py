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
from sentinel_utils import apply_mavt_ranking, read_table_clean, has_sentinel_scores


class HVACGroundTruthCalculator:
    # PJM marginal emissions factors (lbs CO2/kWh). Source: PJM 2022 CO2/SO2/NOx Emissions Report (April 2023).
    # Marginal, not average, is what we want here because it tracks what actually gets shifted at the edge.
    # Peak is 7am-11pm (16h) and off-peak is 11pm-7am (8h) per PJM.
    EMISSIONS_FACTOR_PEAK = 1.041     # PJM peak (1041 lbs/MWh)
    EMISSIONS_FACTOR_OFFPEAK = 0.976  # PJM off-peak (976 lbs/MWh)
    EMISSIONS_PEAK_HOURS_PER_DAY = 16
    EMISSIONS_OFFPEAK_HOURS_PER_DAY = 8

    # PA residential flat electricity rate, $/kWh. Source: EIA Electric Power Annual (2025)
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024 rising to
    # ~19-21 c/kWh through 2025 -- 0.19 is a defensible flat-rate proxy).
    ELECTRICITY_RATE_PA = 0.19

    # Residential infiltration rate (air changes/hour) for the air-change load method.
    # Source: ACCA Manual J (2016) -- 0.35 ACH is the standard
    # modern/average-construction default (also the ASHRAE 62.1-1989 whole-house baseline).
    AIR_CHANGES_PER_HOUR = 0.35
    SUMMER_COMFORT_RANGE = (73, 79)
    SUMMER_OPTIMAL = 76
    WINTER_COMFORT_RANGE = (68, 75)
    WINTER_OPTIMAL = 70

    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Oper. Res. 27(4):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact:
    # - Keeney & Raiffa (1976): Foundation for Multi-Attribute Value Theory axioms.
    # Linear VF justification in this context: When environmental impacts are framed in
    # absolute physical units (lbs CO2), a linear preference is a conservative modeling choice
    # that treats equal changes in emissions as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"
    def calculate_cooling_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int, household_size: int = 3,
                               ceiling_height: float = 8.0,
                               housing_type: str = "Single-family") -> float:
      
        delta_t = outdoor_temp - indoor_temp

        # Adjust by housing type. Typical multipliers from ACCA Manual J:
        # - Single-family (2-story typical): 1.7 (includes roof, walls, floor exposures)
        # - Apartment (mid-unit typical): 1.2 (shared walls reduce exposure)
        # - Townhouse (end-unit typical): 1.5 (one or two shared walls)
        # twin semi-detached (PA regional term). One shared party wall reduces exposed envelope vs. Single-family (1.7).
        housing_multipliers = {
            "Single-family": 1.7,
            "Apartment": 1.2,
            "Condo": 1.2,
            "Townhouse": 1.5,
            "Rowhouse": 1.5,
            "Twin": 1.6,  
        }
        envelope_multiplier = housing_multipliers.get(housing_type, 1.7)
        envelope_area = square_footage * envelope_multiplier

        u_factor = 1.0 / r_value

        conductive_load = u_factor * envelope_area * delta_t

        # Formula: occupants (400 BTU/hr each) + lighting & equipment (1.0 BTU/hr/sqft) + baseline (800)
        # Example: for 3-person, 1500 sqft home: (3 × 400) + (1500 × 1.0) + 800 = 3,500 BTU/hr 
        # Source: ASHRAE Handbook of Fundamentals, Chapter 18, Table 1
        internal_gains = (household_size * 400) + (square_footage * 1.0) + 800

        window_area = square_footage * 0.15
        solar_gains = window_area * 20

        # Infiltration sensible load via the air-change method (ACCA Manual J (2016)):
        #   cfm = volume_ft3 * ACH / 60;  Q_sensible = 1.08 * cfm * deltaT
        #   1.08 = rho*cp*60 = 0.075 lbm/ft3 * 0.24 BTU/(lbm F) * 60 min/hr
        #   (ASHRAE Handbook of Fundamentals (2017) Ch.16)
        infiltration_cfm = (square_footage * ceiling_height * self.AIR_CHANGES_PER_HOUR) / 60.0
        infiltration_load = 1.08 * infiltration_cfm * delta_t

        total_load = conductive_load + internal_gains + solar_gains + infiltration_load
        return max(0, total_load)

    def calculate_heating_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int, household_size: int = 3,
                               ceiling_height: float = 8.0,
                               housing_type: str = "Single-family") -> float:
        delta_t = indoor_temp - outdoor_temp

        housing_multipliers = {
            "Single-family": 1.7,
            "Apartment": 1.2,
            "Condo": 1.2,     
            "Townhouse": 1.5,
            "Rowhouse": 1.5,
            "Twin": 1.6,
        }
        envelope_multiplier = housing_multipliers.get(housing_type, 1.7)
        envelope_area = square_footage * envelope_multiplier

        u_factor = 1.0 / r_value

        conductive_loss = u_factor * envelope_area * delta_t

        # Same formula as cooling load: occupants + lighting/equipment + baseline
        # Source: ASHRAE Handbook of Fundamentals, Chapter 18, Table 1
        internal_gains = (household_size * 400) + (square_footage * 1.0) + 800

        # Infiltration sensible loss via the air-change method (ACCA Manual J (2016); ASHRAE Handbook of Fundamentals (2017) Ch.16):
        #   cfm = volume_ft3 * ACH / 60;  Q_sensible = 1.08 * cfm * deltaT
        infiltration_cfm = (square_footage * ceiling_height * self.AIR_CHANGES_PER_HOUR) / 60.0
        infiltration_loss = 1.08 * infiltration_cfm * delta_t

        total_load = conductive_loss + infiltration_loss - internal_gains
        return max(0, total_load)

    def calculate_energy_consumption(self, load_btu_hr: float, seer: int,
                                     occupancy_context: str, hours: float = 8) -> float:
        # Energy reflects the unit's rated SEER only. Age/maintenance efficiency
        # degradation is NOT applied here -- it is modeled as a reliability factor in
        # calculate_practicality_score (item 3d). Keeping it out of the energy path means
        # the energy score reflects the setpoint choice, not the system's condition.
        # EER = -0.02 * SEER^2 + 1.12 * SEER  (Source: AHRI Standard 210/240)
        eer_estimated = (-0.02 * seer ** 2) + (1.12 * seer)

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
        return total_kwh

    def calculate_comfort_score(self, indoor_temp: float, outdoor_temp: float,
                                household_size: int) -> float:
        # Tent comfort function around PMV-neutral indoor setpoints for mechanical HVAC.
        # Optimal indoor 76F in cooling (outdoor > 75F) and 70F in heating: 76F is the
        # midpoint of the ASHRAE 55-2020 summer comfort band (73-79F, 0.5 clo); 70F sits
        # within the winter band (68-74F, 1.0 clo), ~1F below its 71F midpoint -- both for
        # sedentary occupants. Score = 10 - |indoor - optimal|, clipped to [0,10]; the
        # -1.0/F slope mirrors the rising PPD per F outside neutral in Fanger's PMV/PPD
        # model. The adaptive method (de Dear & Brager (2002)) applies only to naturally
        # conditioned spaces and is not used here.
        # Sources: ASHRAE 55-2020 (Sec 5.3.1 graphic zone); Fanger (1970); van Hoof (2008).
        optimal = 76 if outdoor_temp > 75 else 70
        comfort_score = 10 - abs(indoor_temp - optimal)

        if household_size > 3:
            size_penalty = (household_size - 3) * 0.3
            comfort_score -= size_penalty * (abs(indoor_temp - optimal) / 3.0)

        return max(0.0, min(1.0, comfort_score / 10.0))

    def _efficiency_degradation(self, hvac_age: int, maintenance_level: str = 'moderate') -> float:
        """Fraction of HVAC efficiency lost to age + maintenance: front-loaded, capped
        at 30%. Base annual loss 0.5/1.0/1.5%/yr for good/moderate/poor upkeep; the first
        10 years degrade at 1.5x base, later years at 0.5x. Raises on a missing age rather
        than defaulting to 0 (which would falsely score the system as pristine)."""
        if hvac_age is None:
            raise ValueError("hvac_age is required to compute efficiency degradation")
        rates = {'good': 0.005, 'moderate': 0.010, 'poor': 0.015}
        base_rate = rates.get(maintenance_level, 0.010)
        if hvac_age <= 10:
            total_degradation = hvac_age * (base_rate * 1.5)
        else:
            total_degradation = 10 * (base_rate * 1.5) + (hvac_age - 10) * (base_rate * 0.5)
        return min(total_degradation, 0.30)

    def calculate_practicality_score(self, outdoor_temp: float, indoor_temp: float,
                                     hvac_age: int, maintenance_level: str = 'moderate') -> float:
        # Mode is decided by outdoor vs the chosen indoor setpoint (cool when hotter
        # outside than the setpoint, else heat) -- the physically correct test, replacing
        # the earlier fixed 75F split. Extremity penalties grow as the setpoint moves past
        # adoption-comfort bounds: in cooling, setpoints >= 82F (too warm to tolerate) or
        # <= 71F (overcooling) are penalized; in heating, <= 63F (too cold) or >= 76F
        # (overheating). Slopes are asymmetric because the too-cold directions draw the
        # sharper real-world adoption penalties.
        if outdoor_temp > indoor_temp:  # Cooling mode
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

        # Component 2: delta-T operational feasibility. Large outdoor-indoor gaps push the
        # system toward its limits (lower reliability / higher failure risk).
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

        # Component 3: system condition (item 3d). Age/maintenance efficiency degradation
        # is a reliability concern -- an older or poorly maintained unit is a less
        # practical choice to rely on -- so it scales the score down by the degraded
        # fraction (0-30%) instead of inflating energy use.
        degradation = self._efficiency_degradation(hvac_age, maintenance_level)
        base_score *= (1 - degradation)

        return max(0.15, min(1.0, base_score / 10.0))

    def calculate_monthly_cost(self, per_period_cost: float, periods_per_month: int = 90) -> float:
        return per_period_cost * periods_per_month

    def calculate_budget_penalty(self, monthly_cost: float, monthly_budget: float) -> float:
  
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

    def emissions_factor_for_occupancy(self, occupancy_context: str) -> float:
        """PJM marginal CO2 factor (lbs/kWh) implied by an HVAC occupancy context.
        HVAC alternatives carry no explicit start_time, so run-time is inferred from the
        occupancy pattern against the PJM peak (7am-11pm) / off-peak (11pm-7am) windows
        (Source: PJM 2022 Emissions Report, April 2023):
          - occupied_all_day: runs the full 24h -> peak/off-peak hour-weighted average.
          - occupied_sleep:   home only at night, so run-time falls entirely in the 8h
                              off-peak window -> off-peak factor (this is intended).
          - unoccupied_<H>:   reduced run-time occurs across the H daytime away-hours,
                              which fill the peak window first. H <= 16 -> all peak;
                              H > 16 -> (16h peak + (H-16)h off) / H, a correct hour-
                              weighted average over the H-hour run window.
        """
        ctx = self.normalize_occupancy_context(occupancy_context)
        peak = self.EMISSIONS_FACTOR_PEAK
        off = self.EMISSIONS_FACTOR_OFFPEAK
        peak_h = self.EMISSIONS_PEAK_HOURS_PER_DAY
        off_h = self.EMISSIONS_OFFPEAK_HOURS_PER_DAY

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

    def normalize_occupancy_context(self, occupancy_value) -> str:
        """Map raw scenario occupancy tokens to canonical internal tokens.

        Required (not a no-op): HVACScenarios.xlsx stores non-canonical values
        ('standard', 'sleep', 'overnight_sleep', 'unoccupied_4hr/8hr/12hr') that
        must be folded to 'occupied_all_day' / 'occupied_sleep' / 'unoccupied_<H>'.
        """
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
        reference_ranges = {
            'energy_cost': {
                # 5th-95th percentile of the actual scenario-set HVAC cost distribution
                # (8h window at $0.19/kWh), computed over the ACTIVE-conditioning
                # alternatives only. Zero-load alternatives (a setpoint at/near the
                # outdoor temp, and the bare "Off" option) collapse to $0 and are
                # excluded from the percentile so the normalization floor is not
                # degenerate; an Off/zero-load alternative still scores at the top of the
                # [0,10] cost scale via the (x_max - x) normalization. p5 over the
                # nonzero active set = $0.38, p95 = $3.29. Endpoints remain consistent
                # with residential HVAC studies (efficient: Huyen & Cetin (2019),
                # Energies 12(1):188; degraded: Alves et al. (2016), EB 130:408).
                'min': 0.38,
                'max': 3.29,
                'decreasing': True
            },
            'environmental': {
                # Derived from the same active-set 5th-95th percentile cost envelope as
                # energy_cost ($0.38-$3.29 at $0.19/kWh flat = 2.011-17.326 kWh), applied
                # against PJM marginal emissions factors (0.976 off-peak, 1.041 peak) to
                # keep cost and emissions physically consistent:
                #   min = 2.011 kWh x 0.976 lbs/kWh = 1.96 lbs CO2  (best case: fully off-peak)
                #   max = 17.326 kWh x 1.041 lbs/kWh = 18.04 lbs CO2 (worst case: fully peak)
                # Source: PJM 2022 Emissions Report (April 2023).
                # For HVAC, alternatives within one scenario share the same emission
                # factor because they are evaluated at the same moment and differ by load.
                'min': 1.96,
                'max': 18.04,
                'decreasing': True
            },
            'comfort': {
                'min': 0.0,
                'max': 1.0,
                'decreasing': False
            },
            'practicality': {
                # VF floor 0.05 sits below the raw practicality floor of 0.15 so the least
                # practical-but-feasible option keeps a small positive utility instead of
                # collapsing to exactly zero. Internal normalization choice (not a literature
                # value): no feasible option is treated as absolutely infeasible
                # (Keeney & Raiffa (1976) value-measurability convention).
                'min': 0.05,
                'max': 1.0,
                'decreasing': False
            }
        }

        ref = reference_ranges[value_type]
        x_min = ref['min']
        x_max = ref['max']

        x = raw_value

        vf_type = vf_spec.split(',')[0].strip().lower()

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

        # Clamp final score to [0, 1]
        return max(0.0, min(1.0, u_x))

    def _free_float_temp(self, outdoor_temp: float, cooling_season: bool) -> float:
        # Indoor air a bare "Off" system drifts to when no explicit target is given. With
        # the system off, solar + internal gains drive indoor ABOVE outdoor in cooling
        # season (a closed, occupied house runs ~5F over outdoor on a daily mean), while in
        # heating season internal gains hold indoor ~10F above outdoor (HDD-65 balance-point
        # floor). Sources: de Dear & Brager (2002) / ASHRAE 55-2020 (free-running adaptive
        # model: indoor >= outdoor under heat); ACCA Manual J (2016) (solar + internal gains
        # are additive); ASHRAE Handbook of Fundamentals (2017) (balance-point /
        # internal-gain offset). Replaces an earlier unsourced +/-5F placeholder whose
        # cooling-season sign was physically backwards.
        return outdoor_temp + 5 if cooling_season else outdoor_temp + 10

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        # Drift direction for bare "Off" alternatives that give no explicit target:
        # warmer than the neutral comfort point -> an off system drifts warm (cooling
        # season); otherwise it drifts cold (heating season). Neutral point is the
        # midpoint of the heating/cooling comfort optima (derived, not a magic 75).
        cooling_season = scenario['outdoor_temp'] > (self.SUMMER_OPTIMAL + self.WINTER_OPTIMAL) / 2.0

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
                            effective_temp = self._free_float_temp(scenario['outdoor_temp'], cooling_season)
                    else:
                        effective_temp = self._free_float_temp(scenario['outdoor_temp'], cooling_season)
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

            # Cooling vs heating decided per-alternative from the actual setpoint: cool
            # when it is hotter outside than the chosen indoor temp, otherwise heat.
            is_cooling = scenario['outdoor_temp'] > effective_temp

            if is_cooling:
                load = self.calculate_cooling_load(
                    scenario['outdoor_temp'],
                    effective_temp,
                    scenario['square_footage'],
                    scenario['r_value'],
                    scenario['household_size'],
                    scenario.get('ceiling_height', 8.0),
                    scenario.get('housing_type', 'Single-family')
                )
            else:
                load = self.calculate_heating_load(
                    scenario['outdoor_temp'],
                    effective_temp,
                    scenario['square_footage'],
                    scenario['r_value'],
                    scenario['household_size'],
                    scenario.get('ceiling_height', 8.0),
                    scenario.get('housing_type', 'Single-family')
                )

            kwh = self.calculate_energy_consumption(
                load,
                scenario['seer'],
                occupancy_context=self.normalize_occupancy_context(
                    scenario.get('occupancy_context', 'occupied_all_day')
                ),
            )

            energy_cost = kwh * scenario.get('electricity_rate', self.ELECTRICITY_RATE_PA)
            emission_factor = self.emissions_factor_for_occupancy(
                scenario.get('occupancy_context', 'occupied_all_day')
            )
            emissions = kwh * emission_factor

      
            if 'off' in alt.lower():
                kwh = 0.0
                energy_cost = 0.0
                emissions = 0.0

              # Still use drift temp for comfort/practicality scoring.

            comfort = self.calculate_comfort_score(
                effective_temp,
                scenario['outdoor_temp'],
                scenario['household_size']
            )

            practicality = self.calculate_practicality_score(
                scenario['outdoor_temp'],
                effective_temp,
                scenario['hvac_age'],
                scenario.get('maintenance_level', 'moderate'),
            )
            raw_results[alt] = {
                'kwh': kwh,
                'energy_cost_dollars': energy_cost,
                'emissions_lbs': emissions,
                'comfort_raw': comfort,
                'practicality_raw': practicality
            }

        final_scores = {}
        utility_budget = float(scenario.get('utility_budget', 0.0))

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
                # Monthly cost proxy: holding this setpoint across all three 8h periods
                # per day, every day -> 3 periods/day * 30 days = 90 periods/month.
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost_dollars'],
                    periods_per_month=90
                )

                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    utility_budget
                )

                # Apply penalty to energy cost score
                energy_vf_penalized = energy_vf * budget_penalty
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

        return final_scores


def process_hvac_scenarios(
    csv_filename: str = str(SCENARIO_DIR / "HVACScenarios.xlsx"),
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx")):
    csv_path = Path(csv_filename)
    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = read_table_clean(
        csv_path,
        keep_str_cols=[
            'question', 'location', 'insulation', 'housing_type',
            'house_age', 'alternative_1', 'alternative_2', 'alternative_3',
        ],
    )

    print(f"Found {len(df)} scenarios")

    calculator = HVACGroundTruthCalculator()

    results = []

    for idx, row in df.iterrows():
        print(f"Processing scenario {idx + 1}/{len(df)}: {row['location']}")
        electricity_rate = HVACGroundTruthCalculator.ELECTRICITY_RATE_PA

        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()

            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)

        scenario = {
            'question': row['question'],
            'location': row['location'],
            'square_footage': int(row['square_footage']),
            'r_value': int(row['r_value']),
            'household_size': int(row['household_size']),
            'utility_budget': float(row.get('utility_budget', 0)),
            'outdoor_temp': float(row['outdoor_temp']),
            'seer': int(row['seer']),
            'hvac_age': int(row['hvac_age']),
            'housing_type': str(row.get('housing_type', 'Single-family')),
            'occupancy_context': calculator.normalize_occupancy_context(
                row.get('occupancy_context', 'occupied_all_day')
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
                    'question': row['question'],
                    'location': row['location'],
                    'square_footage': row['square_footage'],
                    'insulation': row.get('insulation', ''),
                    'household_size': row['household_size'],
                    'utility_budget': row.get('utility_budget', ''),
                    'housing_type': row.get('housing_type', ''),
                    'outdoor_temp': row['outdoor_temp'],
                    'house_age': row.get('house_age', ''),
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
    _STR_COLS = ['question', 'location', 'insulation', 'housing_type', 'house_age', 'alternative']
    _INT_COLS = ['scenario_id', 'household_size', 'square_footage', 'rank']
    for c in _STR_COLS:
        if c in results_df.columns:
            results_df[c] = results_df[c].fillna("").astype(str)
    for c in _INT_COLS:
        if c in results_df.columns:
            results_df[c] = results_df[c].astype("Int64")
    results_df.to_excel(output_path, index=False, engine="openpyxl")

    print(f"\nGround truth saved to {output_path}")
    print(f"Total alternatives scored: {len(results_df)}")
    return results_df


if __name__ == "__main__":
    process_hvac_scenarios()
