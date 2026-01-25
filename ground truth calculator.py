import pandas as pd
import math
from typing import Dict, List, Tuple


class HVACGroundTruthCalculator:
    """
    Calculate physics-based ground truth scores for HVAC decision scenarios.
    Uses research from Ground Truth Data.pdf and ASHRAE standards.
    """

    EMISSIONS_FACTOR_PA = 0.6574
    ELECTRICITY_RATE_PA = 0.14
    SUMMER_COMFORT_RANGE = (73, 79)
    SUMMER_OPTIMAL = 76
    WINTER_COMFORT_RANGE = (68, 75)
    WINTER_OPTIMAL = 70

    VF_ENERGY_COST = "polynomial, a=0.5"
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "linear"

    def calculate_cooling_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int) -> float:
        """
        Calculate cooling load using ASHRAE cooling load temperature difference method.

        Citation: ASHRAE Handbook—Fundamentals (2021), Chapter 18
        """
        delta_t = outdoor_temp - indoor_temp

        envelope_area = square_footage * 1.4

        u_factor = 1.0 / r_value

        conductive_load = u_factor * envelope_area * delta_t

        internal_gains = 1000

        window_area = square_footage * 0.15
        solar_gains = window_area * 20

        ventilation_load = conductive_load * 0.20

        total_load = conductive_load + internal_gains + solar_gains + ventilation_load
        print(f"  → Load calculated: {total_load:,.0f} BTU/hr")
        return max(0, total_load)

    def calculate_heating_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int) -> float:
        """
        Calculate heating load using ASHRAE heat loss method.

        Citation: ASHRAE Handbook—Fundamentals (2021), Chapter 18
        """
        delta_t = indoor_temp - outdoor_temp

        envelope_area = square_footage * 1.4

        u_factor = 1.0 / r_value

        conductive_loss = u_factor * envelope_area * delta_t

        internal_gains = 1000

        infiltration_loss = conductive_loss * 0.25

        total_load = conductive_loss + infiltration_loss - internal_gains
        print(f"  → Load calculated: {total_load:,.0f} BTU/hr")
        return max(0, total_load)

    def calculate_energy_consumption(self, load_btu_hr: float, seer: int,
                                     hvac_age: int, hours: float = 8) -> float:
        """
        Calculate energy consumption in kWh.

        Citations:
        - Huyen & Cetin (2019). Energies, 12(1):188
        - Age degradation: Alves et al. (2016). Energy and Buildings, 130:408-419

        Args:
            load_btu_hr: Cooling/heating load (BTU/hr)
            seer: SEER rating
            hvac_age: System age (years)
            hours: Operating hours

        Returns:
            Energy consumption in kWh
        """
        eer_estimated = seer * 0.875

        age_degradation_factor = 1 + (hvac_age * 0.01)

        adjusted_load = load_btu_hr * age_degradation_factor

        kw = (adjusted_load / eer_estimated) / 1000

        total_kwh = kw * hours
        print(f"  → Energy consumption: {total_kwh:.2f} kWh over {hours} hours")
        return total_kwh

    def calculate_comfort_score(self, indoor_temp: float, outdoor_temp: float,
                                household_size: int) -> float:
        """
        Calculate comfort score using ASHRAE 55 with adaptive comfort considerations.

        Citations:
        - Dear & Brager (2002). Energy and Buildings, 34:549-561 (adaptive comfort)
        - Wang & Hong (2020). Renewable & Sustainable Energy Reviews (occupant preferences)
        - Wu et al. (2018). Applied Energy, 212:577-591 (comfort ranges)
        """
        if outdoor_temp > 75:
            optimal = 76
            comfort_min, comfort_max = 73, 79
        else:
            optimal = 70
            comfort_min, comfort_max = 68, 75

        if 60 < outdoor_temp < 85:
            comfort_min -= 2
            comfort_max += 2

        deviation = abs(indoor_temp - optimal)

        if comfort_min <= indoor_temp <= comfort_max:
            comfort_score = 10 - (deviation * 1.0)
        else:
            if indoor_temp < comfort_min:
                range_violation = comfort_min - indoor_temp
            else:
                range_violation = indoor_temp - comfort_max
            comfort_score = 7 - (range_violation * 2.5)

        if household_size > 3:
            size_penalty = (household_size - 3) * 0.3
            comfort_score -= size_penalty * (deviation / 3)

        return max(0, min(10, comfort_score))

    def calculate_practicality_score(self, outdoor_temp: float, indoor_temp: float,
                                     question_type: str = "simple") -> float:
        """
        Calculate practicality based on behavioral research.

        Citations:
        - Xu et al. (2017). Energy Research & Social Science, 32:13-22
          "Thermostat Override Behavior: A Multi-year Field Study"
          Finding: Households exhibit "rebound behavior" when ΔT becomes uncomfortable,
          overriding setpoint schedules. Discomfort threshold varies by household but
          typically emerges at ΔT > 20-25°F.

        - Stopps & Touchie (2021). Energy and Buildings, 238:110834
          "Evaluating Smart Thermostat Schedules in Canadian Homes"
          Finding: Only 40-45% of households successfully adopt thermostat setback schedules.
          Behavioral resistance increases significantly when ΔT exceeds comfort tolerance.
          Complex schedules reduce adoption rates by ~15% (0.85 multiplier for habit disruption).

        - Karjalainen (2007). Indoor Air, 17(1):60-67
          "Gender differences in thermal comfort and use of thermostats"
          Finding: Thermal comfort tolerance range typically spans 15-20°F before occupant
          intervention. Beyond this, occupants frequently override automated controls.
        """
        delta_t = abs(outdoor_temp - indoor_temp)
        if delta_t < 15:
            base_score = 10
        elif delta_t < 25:
            base_score = 10 - (delta_t - 15) * 0.25
        elif delta_t < 40:
            base_score = 7.5 - (delta_t - 25) * 0.233
        else:
            base_score = 4 - (delta_t - 40) * 0.25

        if question_type == "complex":
            base_score *= 0.85

        return max(1.5, min(10, base_score))

    def apply_value_function(self, raw_value: float, vf_spec: str, value_type: str) -> float:
        reference_ranges = {
            'energy_cost': {
                'min': 1.73,
                'max': 9.36,
                'decreasing': True
            },
            'environmental': {
                'min': 6.2,
                'max': 33.58,
                'decreasing': True
            },
            'comfort': {
                'min': 0.0,
                'max': 10.0,
                'decreasing': False
            },
            'practicality': {
                'min': 1.5,
                'max': 10.0,
                'decreasing': False
            }
        }

        ref = reference_ranges[value_type]
        x_min = ref['min']
        x_max = ref['max']

        # REMOVED: x = max(x_min, min(x_max, raw_value))
        # Now use raw_value directly - allow extrapolation
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
                    u_x = 1.0  # Cap at perfect score
                else:
                    u_x = math.log(a * x_normalized + 1) / math.log(a + 1)

        else:
            u_x = x_normalized

        # NOW clamp the final score to [0, 10]
        return max(0.0, min(10.0, u_x * 10.0))

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        """
        Calculate complete ground truth scores for a scenario with all alternatives.
        Feeds raw criterion values directly to value functions per MAVT principles.
        """
        print(f"\n{'=' * 60}")
        print(f"DEBUGGING SCENARIO")
        print(f"{'=' * 60}")
        print(f"Question: {scenario.get('question', 'N/A')}")
        print(
            f"Outdoor: {scenario.get('outdoor_temp')}°F, SEER: {scenario.get('seer')}, R-value: {scenario.get('r_value')}")
        print(f"HVAC Age: {scenario.get('hvac_age')} years")
        print(f"Square Footage: {scenario.get('square_footage')} ft²")
        print(f"Household Size: {scenario.get('household_size')}")
        print(f"Alternatives (raw): {scenario.get('alternatives')}")
        print(f"VF Specs: {scenario.get('vf_specs')}")
        print(f"")

        is_cooling = scenario['outdoor_temp'] > 75

        question_lower = scenario['question'].lower()
        is_complex = any(word in question_lower for word in
                         ['turn off', 'away', 'vacation', 'overnight', 'schedule',
                          'days', 'week', 'setback', 'program'])
        question_type = "complex" if is_complex else "simple"
        print(f"Mode: {'COOLING' if is_cooling else 'HEATING'}, Complexity: {question_type.upper()}\n")

        raw_results = {}

        for alt in scenario['alternatives']:
            print(f"--- Processing Alternative: {alt} ---")

            if isinstance(alt, str):
                if 'off' in alt.lower():
                    if is_cooling:
                        effective_temp = scenario['outdoor_temp'] - 5
                    else:
                        effective_temp = scenario['outdoor_temp'] + 5
                    print(f"  'Off' alternative → effective temp: {effective_temp}°F")
                else:
                    import re
                    numbers = re.findall(r'\d+', alt)
                    if numbers:
                        effective_temp = float(numbers[0])
                    else:
                        print(f"  ⚠ Could not parse alternative: {alt}")
                        continue
            else:
                effective_temp = float(alt)

            print(f"  Effective indoor temp: {effective_temp}°F")

            if is_cooling:
                load = self.calculate_cooling_load(
                    scenario['outdoor_temp'],
                    effective_temp,
                    scenario['square_footage'],
                    scenario['r_value']
                )
            else:
                load = self.calculate_heating_load(
                    scenario['outdoor_temp'],
                    effective_temp,
                    scenario['square_footage'],
                    scenario['r_value']
                )

            kwh = self.calculate_energy_consumption(
                load,
                scenario['seer'],
                scenario['hvac_age']
            )

            energy_cost = kwh * scenario.get('electricity_rate', self.ELECTRICITY_RATE_PA)
            print(f"  → Cost: ${energy_cost:.2f}")
            emissions = kwh * self.EMISSIONS_FACTOR_PA
            print(f"  → Emissions: {emissions:.2f} lbs CO2")

            comfort = self.calculate_comfort_score(
                effective_temp,
                scenario['outdoor_temp'],
                scenario['household_size']
            )
            print(f"  → Comfort (raw): {comfort:.2f}/10")

            practicality = self.calculate_practicality_score(
                scenario['outdoor_temp'],
                effective_temp,
                question_type
            )
            print(f"  → Practicality (raw): {practicality:.2f}/10\n")

            raw_results[alt] = {
                'kwh': kwh,
                'energy_cost_dollars': energy_cost,
                'emissions_lbs': emissions,
                'comfort_raw': comfort,
                'practicality_raw': practicality
            }

        final_scores = {}

        for alt, raw in raw_results.items():
            print(f"--- Scoring Alternative: {alt} ---")
            print(f"  Raw values:")
            print(f"     Energy Cost:   ${raw['energy_cost_dollars']:.2f}")
            print(f"     Emissions:     {raw['emissions_lbs']:.2f} lbs CO2")
            print(f"     Comfort:       {raw['comfort_raw']:.2f}/10")
            print(f"     Practicality:  {raw['practicality_raw']:.2f}/10")

            try:
                energy_vf = self.apply_value_function(
                    raw['energy_cost_dollars'],
                    scenario['vf_specs']['energy_cost'],
                    'energy_cost'
                )
                print(f"  After VF ({scenario['vf_specs']['energy_cost']}): Energy = {energy_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Energy VF ERROR: {e}")
                energy_vf = 5.0

            try:
                env_vf = self.apply_value_function(
                    raw['emissions_lbs'],
                    scenario['vf_specs']['environmental'],
                    'environmental'
                )
                print(f"  After VF ({scenario['vf_specs']['environmental']}): Environmental = {env_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Environmental VF ERROR: {e}")
                env_vf = 5.0

            try:
                comfort_vf = self.apply_value_function(
                    raw['comfort_raw'],
                    scenario['vf_specs']['comfort'],
                    'comfort'
                )
                print(f"  After VF ({scenario['vf_specs']['comfort']}): Comfort = {comfort_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Comfort VF ERROR: {e}")
                comfort_vf = raw['comfort_raw']

            try:
                practicality_vf = self.apply_value_function(
                    raw['practicality_raw'],
                    scenario['vf_specs']['practicality'],
                    'practicality'
                )
                print(f"  After VF ({scenario['vf_specs']['practicality']}): Practicality = {practicality_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Practicality VF ERROR: {e}")
                practicality_vf = raw['practicality_raw']

            final_scores[alt] = {
                'energy_cost_score': round(energy_vf, 2),
                'environmental_score': round(env_vf, 2),
                'comfort_score': round(comfort_vf, 2),
                'practicality_score': round(practicality_vf, 2),
                'raw_kwh': round(raw['kwh'], 2),
                'raw_cost': round(raw['energy_cost_dollars'], 2),
                'raw_emissions': round(raw['emissions_lbs'], 2)
            }

            print(f"  → FINAL SCORES:")
            print(
                f"     Energy: {energy_vf:.2f}, Environmental: {env_vf:.2f}, Comfort: {comfort_vf:.2f}, Practicality: {practicality_vf:.2f}\n")

        return final_scores


class ApplianceGroundTruthCalculator:
    """
    PLACEHOLDER: Calculate ground truth for appliance scheduling decisions.

    Will need:
    - calculate_appliance_energy(kwh_per_cycle, time_of_day, tou_rates)
    - calculate_delay_discomfort(delay_hours, appliance_type)
    - apply_value_functions() (inherited or shared method)
    """
    pass


class WaterGroundTruthCalculator:
    """
    PLACEHOLDER: Calculate ground truth for water heating decisions.

    Will need:
    - calculate_shower_energy(duration, water_heater_type, flow_rate)
    - calculate_comfort_score(duration, temperature)
    - apply_value_functions() (inherited or shared method)
    """
    pass


def process_hvac_scenarios(csv_filename: str = "Scenarios - HVAC Scenarios; GT (add complexity).csv",  output_filename: str = "ground_truth_hvac.csv"):
    """
    Read HVAC scenarios from CSV and calculate ground truth scores for all alternatives.

    Args:
        csv_filename: Path to CSV file with scenarios
        output_filename: Where to save ground truth results

    Expected CSV columns:
        Question, Location, Square Footage, Insulation, Household Size,
        Utility Budget, Housing Type, Outdoor Temp, House Age, R-Value,
        HVAC Age, SEER, Alternative 1, Alternative 2, Alternative 3,
        Energy Cost VF, Environmental VF, Comfort VF, Practicality VF
    """

    print(f"Reading scenarios from {csv_filename}...")
    df = pd.read_csv(csv_filename)

    print(f"Found {len(df)} scenarios")

    calculator = HVACGroundTruthCalculator()

    results = []

    for idx, row in df.iterrows():
        print(f"Processing scenario {idx + 1}/{len(df)}: {row['Location']}")
        electricity_rate = 0.14

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
            'outdoor_temp': float(row['Outdoor Temp']),
            'seer': int(row['SEER']),
            'hvac_age': int(row['HVAC Age']),
            'electricity_rate': electricity_rate,
            'alternatives': alternatives,
            'vf_specs': {
                'energy_cost': HVACGroundTruthCalculator.VF_ENERGY_COST,
                'environmental': HVACGroundTruthCalculator.VF_ENVIRONMENTAL,
                'comfort': HVACGroundTruthCalculator.VF_COMFORT,
                'practicality': HVACGroundTruthCalculator.VF_PRACTICALITY
            }
        }
        try:
            scores = calculator.calculate_scenario_scores(scenario)

            for alt, alt_scores in scores.items():
                result_row = {
                    'scenario_id': idx,
                    'question': row['Question'],
                    'location': row['Location'],
                    'electricity_rate': electricity_rate,
                    'alternative': alt,
                    'energy_cost_score': alt_scores['energy_cost_score'],
                    'environmental_score': alt_scores['environmental_score'],
                    'comfort_score': alt_scores['comfort_score'],
                    'practicality_score': alt_scores['practicality_score'],
                    'raw_kwh': alt_scores['raw_kwh'],
                    'raw_cost': alt_scores['raw_cost'],
                    'raw_emissions': alt_scores['raw_emissions']
                }
                results.append(result_row)

        except Exception as e:
            print(f"ERROR processing scenario {idx}: {e}")
            continue

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_filename, index=False)

    print(f"\nGround truth saved to {output_filename}")
    print(f"Total alternatives scored: {len(results_df)}")
    return results_df


if __name__ == "__main__":
    process_hvac_scenarios(
        csv_filename="Scenarios - HVAC Scenarios; GT (add complexity).csv",
        output_filename="ground_truth_hvac.csv"
    )

    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)