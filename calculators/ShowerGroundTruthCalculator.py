import argparse
import sys
import logging
import numpy as np
from typing import Dict, List, Tuple
import pandas as pd
from pathlib import Path

from llm_mcda.common.paths import (
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_path,
)
PROJECT_ROOT = repository_root(start=__file__)
SCENARIO_DIR = PROJECT_ROOT / "workbooks/scenarios"
GROUND_TRUTH_DIR = PROJECT_ROOT / "workbooks/ground_truth"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from llm_mcda.common.sentinel_utils import apply_mavt_ranking, read_table_clean, has_sentinel_scores

class ShowerGroundTruthCalculator:
    """Calculate shower ground-truth criterion scores."""

    # PA residential electricity rate (EIA Electric Power Monthly, $/kWh).
    ELECTRICITY_RATE_PA = 0.19

    # PA seasonal mains water temperatures: linear fit evaluated against monthly
    # mean outdoor temperature at six PA TMY3 stations (RMSE 3.6 F).
    INLET_TEMP_WINTER = 48.5  # F, outdoor <=32F
    INLET_TEMP_SUMMER = 68.2  # F, outdoor >=75F

    # Heater efficiency and temperature thresholds.
    ELECTRIC_HEATER_EFFICIENCY = 0.92
    TARGET_SHOWER_TEMP = 105.0  # F delivery temperature
    WATER_DENSITY = 8.33  # lbs/gallon (standard)
    BTU_PER_KWH = 3412  # Conversion factor (standard)

    # Duration comfort thresholds (7.8 min average; ~33% of showers exceed 15 min).
    COMFORT_DURATION_MIN = 5  # Rushed but viable
    COMFORT_DURATION_OPTIMAL = 7.8  # field-average shower length (moderate-weather anchor)
    COMFORT_DURATION_MAX = 15  # Comfortable upper bound

    # Lengthen shower target in cold weather (capped).
    COMFORT_TEMP_REFERENCE_F = 77.0
    COMFORT_TEMP_ELASTICITY_PER_F = 0.10 / 10.8  # +10% per 10.8 F (6 C) drop (modeling assumption)
    COMFORT_TEMP_MAX_MULTIPLIER = 11.6 / 8.8     # ~1.318x winter/summer field-mean envelope

    HEATER_TEMP_MINIMUM = 110
    HEATER_TEMP_OPTIMAL = 120
    HEATER_TEMP_SCALD_RISK = 130
    HEATER_TEMP_LEGIONELLA_SAFE = 140

    # Comfort no-penalty band for the water-heater setpoint: [OPTIMAL, LEGIONELLA_SAFE]
    # = 120-140F. Below 120F the tank cannot deliver 105F with any mixing margin;
    # above 140F adds standby loss and scald exposure with no comfort benefit.
    COMFORT_HEATER_TEMP_MIN = HEATER_TEMP_OPTIMAL        # 120F
    COMFORT_HEATER_TEMP_MAX = HEATER_TEMP_LEGIONELLA_SAFE  # 140F
    # Linear VF for energy cost.
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"

    def determine_inlet_temp(self, outdoor_temp: float) -> float:
        # PA seasonal mains temps, interpolated across the 32-75F outdoor band.
        if outdoor_temp <= 32:
            return float(self.INLET_TEMP_WINTER)
        elif outdoor_temp >= 75:
            return float(self.INLET_TEMP_SUMMER)
        else:
            span = self.INLET_TEMP_SUMMER - self.INLET_TEMP_WINTER  # 19.7F over a 43F outdoor range
            return self.INLET_TEMP_WINTER + (outdoor_temp - 32.0) * (span / 43.0)

    def calculate_shower_energy(self, duration_min: float, gpm: float,
                                water_heater_temp: float, outdoor_temp: float) -> float:
        inlet_temp = self.determine_inlet_temp(outdoor_temp)
        delta_t = water_heater_temp - inlet_temp

        # Only heat the hot water fraction (rest is cold water mixed in)
        hot_fraction = self.calculate_hot_water_fraction(
            water_heater_temp,
            inlet_temp,
            ShowerGroundTruthCalculator.TARGET_SHOWER_TEMP
        )
        effective_gpm = gpm * hot_fraction

        # Energy = (flow × density × temp_rise × time) / (conversion × efficiency)
        energy_kwh = (effective_gpm * ShowerGroundTruthCalculator.WATER_DENSITY *
                      delta_t * duration_min) / (ShowerGroundTruthCalculator.BTU_PER_KWH *
                                                 ShowerGroundTruthCalculator.ELECTRIC_HEATER_EFFICIENCY)

        return energy_kwh

    def calculate_hot_water_fraction(self, water_heater_temp: float, inlet_temp: float,
                                     target_temp: float) -> float:
        # Mixing-energy balance for hot/cold streams.
        if water_heater_temp <= inlet_temp:
            return 0.0
        fraction = (target_temp - inlet_temp) / (water_heater_temp - inlet_temp)
        return max(0.0, min(1.0, fraction))

    def calculate_energy_cost(self, kwh: float) -> float:
        rate = ShowerGroundTruthCalculator.ELECTRICITY_RATE_PA
        return kwh * rate

    def calculate_environmental_impact(self, gpm: float, duration_min: float) -> float:
        """Calculate environmental impact as water volume consumed (gallons)."""
        return gpm * duration_min

    def calculate_comfort_score(self, duration: float, water_heater_temp: float,
                                occupants: int, outdoor_temp: float = COMFORT_TEMP_REFERENCE_F) -> float:
        """Calculate comfort score (optimum shifts upward in cold weather)."""
        cls = ShowerGroundTruthCalculator
        drop_f = max(0.0, cls.COMFORT_TEMP_REFERENCE_F - outdoor_temp)
        temp_multiplier = min(
            1.0 + cls.COMFORT_TEMP_ELASTICITY_PER_F * drop_f,
            cls.COMFORT_TEMP_MAX_MULTIPLIER,
        )
        optimal_duration = cls.COMFORT_DURATION_OPTIMAL * temp_multiplier  # <= ~10.3 min

        if duration <= 3.0:
            # Below dermatologist minimum: severely rushed.
            base_comfort = 4.0 * (duration / 3.0) ** 3
        elif duration <= optimal_duration:
            # Ramp to the (temperature-adjusted) optimum: 4.0 at 3 min → 10.0 at optimal.
            base_comfort = 4.0 + ((duration - 3.0) / (optimal_duration - 3.0)) * 6.0
        elif duration <= float(ShowerGroundTruthCalculator.COMFORT_DURATION_MAX):
            # Above optimal - diminishing returns, slight waste concern.
            # Linear decline: 10.0 at optimal → 8.0 at COMFORT_DURATION_MAX.
            base_comfort = 10.0 + ((duration - optimal_duration) / (float(ShowerGroundTruthCalculator.COMFORT_DURATION_MAX) - optimal_duration)) * (8.0 - 10.0)
        else:
            # Extreme duration - very wasteful
            # Continue linear decline: 0.5 per minute beyond COMFORT_DURATION_MAX
            base_comfort = max(1.0, 8.0 - (duration - float(ShowerGroundTruthCalculator.COMFORT_DURATION_MAX)) * 0.5)

        temp_penalty = 0.0
        if water_heater_temp < ShowerGroundTruthCalculator.COMFORT_HEATER_TEMP_MIN:
            temp_penalty = 2.0  # No mixing margin above the 105F target; within Legionella growth range
        elif water_heater_temp > ShowerGroundTruthCalculator.COMFORT_HEATER_TEMP_MAX:
            temp_penalty = 1.0  # Standby loss and scald exposure, no extra comfort benefit (our assumption)

        # Larger households experience pressure to keep showers short
        contention_penalty = 0.0
        if occupants >= 4:
            excess_duration = max(0, duration - optimal_duration)
            contention_penalty = excess_duration * 0.5

        total_comfort = base_comfort - temp_penalty - contention_penalty
        return max(0.0, min(1.0, total_comfort / 10.0))

    def calculate_practicality_score(self, duration: float, occupants: int,
                                     tank_size: float, gpm: float,
                                     water_heater_temp: float, outdoor_temp: float) -> float:
        if duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_MIN:
            # Below minimum: very low adoption.
            base_practicality = 2.0 + (duration - 3.0) * 0.5
        elif duration <= 8:
            # Near average (7.8 min): high adoption zone.
            base_practicality = 3.0 + (duration - float(ShowerGroundTruthCalculator.COMFORT_DURATION_MIN)) * (4.0 / 3.0)
        elif duration <= 12:
            # Above average but within typical range - moderate adoption
            base_practicality = 7.0 + (duration - 8.0) * 0.5
        elif duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_MAX:
            # Declining-adoption tail approaching the upper bound.
            base_practicality = 9.0 - (duration - 12.0) * (1.5 / 3.0)
        else:
            # Long tail modeled conservatively (metered data implies lower true rates).
            base_practicality = max(1.5, 7.5 - (duration - float(ShowerGroundTruthCalculator.COMFORT_DURATION_MAX)) * 0.35)

        inlet_temp = self.determine_inlet_temp(outdoor_temp)
        hot_fraction = self.calculate_hot_water_fraction(
            water_heater_temp,
            inlet_temp,
            ShowerGroundTruthCalculator.TARGET_SHOWER_TEMP
        )
        hot_water_per_shower = duration * gpm * hot_fraction
        total_hot_water_needed = hot_water_per_shower * occupants
        available_capacity = tank_size * 0.80

        capacity_penalty = 0.0
        if total_hot_water_needed > available_capacity:
            capacity_penalty = 3.0

        total_practicality = base_practicality - capacity_penalty

        return max(0.15, min(1.0, total_practicality / 10.0))

    def calculate_monthly_cost(self, per_shower_cost: float, occupants: int,
                               showers_per_person_per_day: float = 0.69) -> float:
        showers_per_month = occupants * showers_per_person_per_day * 30
        return per_shower_cost * showers_per_month

    def calculate_budget_penalty(self, monthly_cost: float, monthly_budget: float) -> float:
        if monthly_budget <= 0:
            return 1.0

        utilization = monthly_cost / monthly_budget

        if utilization < 0.80:
            return 1.0
        elif utilization < 1.0:
            return 1.0 - 2.5 * (utilization - 0.80)
        else:
            # u >= 1.0: exponential decline, continuous for every u (no drop to 0 at u = 1.5).
            import math
            return 0.5 * math.exp(-3.0 * (utilization - 1.0))


    def apply_value_function(self, raw_value: float, vf_spec: str, value_type: str) -> float:
        reference_ranges = {
            'energy_cost': {
                # 5th-95th percentile of the actual scenario-set per-shower cost
                # distribution: p5 = $0.13, p95 = $1.07. Shower energy follows the
                # dynamic mixing-fraction physics (target=105F),
                #   kWh = gpm * 8.33 lb/gal * (TARGET_SHOWER_TEMP - inlet) * duration
                #         / (3412 BTU/kWh * 0.92 UEF),
                # priced at the PA residential rate ($0.19/kWh). Dataset-percentile
                # bounds (vs. a theoretical physics envelope) concentrate score
                # sensitivity over the durations/flows households actually encounter.
                'min': 0.13,
                'max': 1.07,
                'decreasing': True
            },
            'environmental': {
                # Environmental criterion = water volume consumed (gallons) per shower.
                # 5th-95th percentile of the actual scenario-set water-volume
                # distribution (gpm x duration): p5 = 6.0 gal, p95 = 45.0 gal. Dataset
                # percentiles rather than the theoretical WaterSense extremes, so the
                # score spreads across the volumes households actually use.
                'min': 6.0,
                'max': 45.0,
                'decreasing': True
            },
            'comfort': {
                'min': 0.0,
                'max': 1.0,
                'decreasing': False
            },
            'practicality': {
                # VF floor below the raw practicality floor keeps feasible options positive.
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

        # Normalize to create x_normalized (can go outside [0,1] range for extrapolation)
        if ref['decreasing']:
            # Lower raw value = higher score (e.g., cost, emissions)
            x_normalized = (x_max - x) / (x_max - x_min)
        else:
            # Higher raw value = higher score (e.g., comfort, practicality)
            x_normalized = (x - x_min) / (x_max - x_min)

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
                import math
                u_x = (1 - math.exp(a * x_normalized)) / (1 - math.exp(a))

        elif vf_type == 'logarithmic':
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0

            if a == -1:
                u_x = x_normalized
            else:
                import math
                if a * x_normalized + 1 <= 0:
                    u_x = 0.0
                else:
                    u_x = math.log(a * x_normalized + 1) / math.log(a + 1)

        else:
            u_x = x_normalized

        return max(0.0, min(1.0, u_x))
    
    def calculate_scenario_scores(self, scenario: dict) -> dict:
        occupants = int(scenario.get('household_size', 2))
        tank_size = float(scenario.get('tank_size', 40))
        gpm = float(scenario.get('gpm', 2.5))
        outdoor_temp = float(scenario.get('outdoor_temp', 50))
        water_heater_temp = float(scenario.get('water_heater_temp', 120))

        alternatives = []
        for i in range(1, 4):
            alt_key = f'alternative_{i}'
            if alt_key in scenario:
                val = scenario[alt_key]
                if pd.isna(val) or str(val).strip().lower() in ('nan', '', 'none'):
                    continue
                duration = float(val)
                alternatives.append({
                    'name': scenario[alt_key],
                    'duration': duration
                })
        if not alternatives:
            raise ValueError("No valid alternatives found in scenario")

        results = []

        for alt in alternatives:
            duration = alt['duration']

            kwh = self.calculate_shower_energy(
                duration, gpm, water_heater_temp, outdoor_temp
            )
            cost = self.calculate_energy_cost(kwh)
            water_gallons = self.calculate_environmental_impact(gpm, duration)
            comfort = self.calculate_comfort_score(
                duration, water_heater_temp, occupants, outdoor_temp
            )
            practicality = self.calculate_practicality_score(
                duration, occupants, tank_size, gpm, water_heater_temp, outdoor_temp
            )

            results.append({
                'alternative': alt['name'],
                'duration': duration,
                'raw_values': {
                    'energy_kwh': kwh,
                    'energy_cost': cost,
                    'environmental': water_gallons,
                    'comfort': comfort,
                    'practicality': practicality
                }
            })

        for result in results:
            alt = result['alternative']
            raw = result['raw_values']

            energy_vf = self.apply_value_function(
                raw['energy_cost'],
                self.VF_ENERGY_COST,
                'energy_cost'
            )

            env_vf = self.apply_value_function(
                raw['environmental'],
                self.VF_ENVIRONMENTAL,
                'environmental'
            )

            comfort_vf = self.apply_value_function(
                raw['comfort'],
                self.VF_COMFORT,
                'comfort'
            )

            practicality_vf = self.apply_value_function(
                raw['practicality'],
                self.VF_PRACTICALITY,
                'practicality'
            )

            if 'utility_budget' in scenario and scenario['utility_budget'] > 0:
                occupants = scenario.get('household_size', 2)

                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost'],
                    occupants,
                    showers_per_person_per_day=0.69
                )

                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    scenario['utility_budget']
                )

                energy_vf_penalized = energy_vf * budget_penalty
                energy_vf = energy_vf_penalized

            result['transformed_values'] = {
                'energy_cost': round(energy_vf, 2),
                'environmental': round(env_vf, 2),
                'comfort': round(comfort_vf, 2),
                'practicality': round(practicality_vf, 2)
            }

        return {
            'scenario': scenario.get('question', 'N/A'),
            'alternatives': results
        }


def process_shower_scenarios(
    xlsx_filename: str = str(SCENARIO_DIR / "ShowerScenarios.xlsx"),
    output_filename: str | None = None):
    csv_path = Path(xlsx_filename)
    output_path = require_safe_output_path(
        output_filename,
        option="--output",
        root=PROJECT_ROOT,
    )
    if output_path == csv_path.resolve():
        raise UnsafeOutputPathError("--output must be separate from the scenario input workbook")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = read_table_clean(
        csv_path,
        keep_str_cols=[
            'question', 'location', 'housing_type',
            'alternative_1', 'alternative_2', 'alternative_3',
        ],
    )
    print(f"Found {len(df)} shower scenarios")

    calculator = ShowerGroundTruthCalculator()
    results = []

    for idx, row in df.iterrows():
        print(f"\nProcessing scenario {idx + 1}/{len(df)}: {row['location']}")
        scenario = {
            'question': row['question'],
            'location': row['location'],
            'household_size': int(row['household_size']),
            'tank_size': float(row['tank_size']),
            'gpm': float(row['gpm']),
            'utility_budget': float(row.get('utility_budget', 0)),
            'housing_type': row['housing_type'],
            'outdoor_temp': float(row['outdoor_temp']),
            'water_heater_temp': float(row['water_heater_temp']),
            'alternative_1': row['alternative_1'],
            'alternative_2': row['alternative_2'],
            'alternative_3': row['alternative_3'],
        }

        try:
            result = calculator.calculate_scenario_scores(scenario)
            alts_for_ranking = [
                {
                    "alternative": alt_data['alternative'],
                    "energy_cost": alt_data['transformed_values']['energy_cost'],
                    "environmental": alt_data['transformed_values']['environmental'],
                    "comfort": alt_data['transformed_values']['comfort'],
                    "practicality": alt_data['transformed_values']['practicality']
                }
                for alt_data in result['alternatives']
            ]
            ranking_result = apply_mavt_ranking(alts_for_ranking)
            for alt_data in result['alternatives']:
                alt_idx = result['alternatives'].index(alt_data)
                result_row = {
                    'scenario_id': idx,
                    'question': row['question'],
                    'location': row['location'],
                    'household_size': row['household_size'],
                    'gpm': row['gpm'],
                    'utility_budget': row['utility_budget'],
                    'housing_type': row['housing_type'],
                    'outdoor_temp': row['outdoor_temp'],
                    'alternative': alt_data['alternative'],
                    'duration_min': alt_data['duration'],
                    'energy_cost_score': alt_data['transformed_values']['energy_cost'],
                    'environmental_score': alt_data['transformed_values']['environmental'],
                    'comfort_score': alt_data['transformed_values']['comfort'],
                    'practicality_score': alt_data['transformed_values']['practicality'],
                    'mavt_score': ranking_result["weighted_scores"][alt_idx],
                    'rank': ranking_result["ranks"][alt_idx],
                    'raw_kwh': alt_data['raw_values']['energy_kwh'],
                    'raw_cost': alt_data['raw_values']['energy_cost'],
                    'raw_water_gallons': alt_data['raw_values']['environmental']
                }
                results.append(result_row)

        except Exception as e:
            print(f"ERROR processing scenario {idx}: {e}")
            import traceback
            traceback.print_exc()
            continue

    results_df = pd.DataFrame(results)
    _STR_COLS = ['question', 'location', 'housing_type', 'alternative']
    _INT_COLS = ['scenario_id', 'household_size', 'rank']
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calculate shower ground-truth scores.")
    parser.add_argument(
        "--input",
        default=str(SCENARIO_DIR / "ShowerScenarios.xlsx"),
        help="scenario workbook to read (default: workbooks/scenarios/ShowerScenarios.xlsx)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="explicit safe output workbook path outside frozen repository data",
    )
    args = parser.parse_args(argv)
    try:
        process_shower_scenarios(args.input, args.output)
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
