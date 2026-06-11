import sys
import logging
import numpy as np
from typing import Dict, List, Tuple
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
from sentinel_utils import read_table_clean

class ShowerGroundTruthCalculator:
    """Key sources:
- DeOreo et al. (2016). Average shower 7.8 min; 0.9 showers/person/day.
- Hendron & Burch (2008). Mains temp model.
- Backman & Hoeschele (2013). Hot water distribution validation.
- Rheem Manufacturing Company (2025). Electric Tank Water Heaters product specs.
- CDC (2026). Monitoring Building Water: Legionella control guidance.
- Zhang et al. (2023). Buildings, 13(5), 1300.
"""

    # PA residential flat electricity rate, $/kWh. Source: EIA Electric Power Annual (2025)
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024 rising to
    # ~19-21 c/kWh through 2025 -- 0.19 is a defensible flat-rate proxy).
    ELECTRICITY_RATE_PA = 0.19

    # PA seasonal mains water temperatures.
    # Sources: Hendron & Burch (2008), NREL/TP-550-40874; Maguire et al. (2013), NREL/TP-5500-58756.
    INLET_TEMP_WINTER = 45  # F, outdoor <=32F
    INLET_TEMP_SPRING_FALL = 55  # F, outdoor 32-75F
    INLET_TEMP_SUMMER = 65  # F, outdoor >=75F

    # UEF 0.90-0.93 for 40-55 gal electric tank.
    # Source: Rheem Manufacturing Company. (2025). Residential Tank Water Heaters
    #         Product Specifications (electric models 40-55 gal). Midpoint: 0.92.
    ELECTRIC_HEATER_EFFICIENCY = 0.92
    TARGET_SHOWER_TEMP = 105.0  # F, upper end of the comfortable shower delivery band (~98-105F); Zhang et al. (2023)
    WATER_DENSITY = 8.33  # lbs/gallon (standard)
    BTU_PER_KWH = 3412  # Conversion factor (standard)

    # Duration comfort thresholds.
    # Average 7.8 min from REU2016 (Water Research Foundation).
    # Long-duration prevalence (33% >15 min) from The Harris Poll (2024).
    COMFORT_DURATION_MIN = 5  # Rushed but viable
    COMFORT_DURATION_OPTIMAL = 7.8  # REU2016 average of 7.8 min (moderate-weather anchor)
    COMFORT_DURATION_MAX = 15  # Comfortable upper bound

    # Cold-weather comfort shift: comfortable shower duration lengthens as outdoor
    # temperature falls, so the comfort-optimal duration is shifted upward below a
    # moderate reference outdoor temperature. The +10% per 6 C (10.8 F) elasticity is a
    # MODELING ASSUMPTION, not a directly reported coefficient -- Wong et al. (2022) supports
    # only the qualitative direction that colder conditions raise showering thermal demand.
    # The shift is capped at the empirically observed winter/summer field-mean envelope
    # of 11.6 vs 8.8 min (ratio ~1.318) from Ibanez-Rueda et al. (2023) (a southern-Spain
    # sample, so a cross-population extrapolation). No shift applies at/above 77 F (= 25 C),
    # the upper ASHRAE 55-2020 cooling comfort reference (ASHRAE 55-2020).
    COMFORT_TEMP_REFERENCE_F = 77.0
    COMFORT_TEMP_ELASTICITY_PER_F = 0.10 / 10.8  # +10% per 10.8 F (6 C) drop (modeling assumption)
    COMFORT_TEMP_MAX_MULTIPLIER = 11.6 / 8.8     # ~1.318x winter/summer envelope (Ibanez-Rueda et al. (2023))

    # Water-heater temp thresholds. CDC Legionella guidance (CDC (2026)): store >=140F,
    # deliver/recirculate >=120F. 110F and 130F are code-defined comfort/scald
    # boundaries, NOT CDC setpoints.
    HEATER_TEMP_MINIMUM = 110  # F, lukewarm boundary (within CDC Legionella growth range 77-113F, CDC (2026))
    HEATER_TEMP_OPTIMAL = 120  # F, standard delivery setpoint (CDC (2026))
    HEATER_TEMP_SCALD_RISK = 130  # F, scald-risk threshold (~30s to a deep burn; Moritz & Henriques (1947))
    HEATER_TEMP_LEGIONELLA_SAFE = 140  # F, CDC minimum storage temp (CDC (2026))
     # Behavioral adoption estimates (modeled from REU2016 distribution)
    PRACTICALITY_SHORT_ADOPTION = 0.30  # ~30% maintain <7 min without intervention
    PRACTICALITY_MEDIUM_ADOPTION = 0.65  # ~65% maintain 8-10 min (Harris Poll)

    # Tank capacity standards
    TANK_RECOVERY_ELECTRIC = 21  # GPH at 90F rise (plumbing guides)
    FIRST_HOUR_RATING_40GAL = 50  # Gallons available in first hour
    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Oper. Res. 27(4):810-822)
    VF_ENERGY_COST = "linear"

    # For MAVT framework justification, see Keeney & Raiffa (1976): Foundation for
    # Multi-Attribute Value Theory axioms.
    # Linear VF justification in this context: When environmental impacts are framed in
    # absolute physical units (gallons), a linear preference is a conservative modeling choice
    # that treats equal changes in water use as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"

    def determine_inlet_temp(self, outdoor_temp: float) -> float:
        # PA seasonal mains temps, linearly interpolated across the 32-75F outdoor band
        # between the winter and summer anchors (Hendron & Burch (2008); Backman & Hoeschele (2013)).
        if outdoor_temp <= 32:
            return float(self.INLET_TEMP_WINTER)
        elif outdoor_temp >= 75:
            return float(self.INLET_TEMP_SUMMER)
        else:
            span = self.INLET_TEMP_SUMMER - self.INLET_TEMP_WINTER  # 20F over a 43F outdoor range
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
        """Calculate hot-water mixing fraction for a target delivery temperature."""
        # Mixing-energy balance for hot/cold streams.
        # Sources: Hendron & Burch (2008); Backman & Hoeschele (2013); Zhang et al. (2023).
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
        """Calculate comfort score.

        The comfort-optimal duration (the peak of the curve) is shifted upward in
        cold weather per the cold-weather elasticity documented on the class
        constants: warmer outdoor temps keep the REU2016 7.8-min optimum, colder
        temps raise it (capped at the observed winter envelope). Warm-weather
        scoring is unchanged (multiplier == 1.0 at/above the reference temp).
        """
        cls = ShowerGroundTruthCalculator
        drop_f = max(0.0, cls.COMFORT_TEMP_REFERENCE_F - outdoor_temp)
        temp_multiplier = min(
            1.0 + cls.COMFORT_TEMP_ELASTICITY_PER_F * drop_f,
            cls.COMFORT_TEMP_MAX_MULTIPLIER,
        )
        optimal_duration = cls.COMFORT_DURATION_OPTIMAL * temp_multiplier  # <= ~10.3 min

        if duration <= 3.0:
            # Below dermatologist minimum — severely rushed.
            # Cubic ramp: 0.0 at 0 min → 4.0 at 3 min, with exponential penalization for
            # very short durations. At 2min: ~1.2 (vs ~3.0 with prior linear ramp).
            # Boundary at 3min = 4.0 is unchanged — no discontinuity with next segment.
            base_comfort = 4.0 * (duration / 3.0) ** 3
        elif duration <= optimal_duration:
            # Ramp to the (temperature-adjusted) optimum: 4.0 at 3 min → 10.0 at optimal.
            base_comfort = 4.0 + ((duration - 3.0) / (optimal_duration - 3.0)) * 6.0
        elif duration <= 15.0:
            # Above optimal - diminishing returns, slight waste concern.
            # Linear decline: 10.0 at optimal → 8.0 at 15 min.
            base_comfort = 10.0 + ((duration - optimal_duration) / (15.0 - optimal_duration)) * (8.0 - 10.0)
        else:
            # Extreme duration - very wasteful
            # Continue linear decline: 0.5 per minute beyond 15 min
            base_comfort = max(1.0, 8.0 - (duration - 15.0) * 0.5)

        temp_penalty = 0.0
        if water_heater_temp < ShowerGroundTruthCalculator.HEATER_TEMP_MINIMUM:
            temp_penalty = 2.0  # Lukewarm, within Legionella growth range
        elif water_heater_temp > ShowerGroundTruthCalculator.HEATER_TEMP_SCALD_RISK:
            temp_penalty = 1.0  # Scald risk, no extra comfort benefit

        # Larger households experience pressure to keep showers short
        contention_penalty = 0.0
        if occupants >= 4:
            excess_duration = max(0, duration - ShowerGroundTruthCalculator.COMFORT_DURATION_OPTIMAL)
            contention_penalty = excess_duration * 0.5

        total_comfort = base_comfort - temp_penalty - contention_penalty
        return max(0.0, min(10.0, total_comfort))

    def calculate_practicality_score(self, duration: float, occupants: int,
                                     tank_size: float, gpm: float,
                                     water_heater_temp: float, outdoor_temp: float) -> float:
        if duration <= 5:
            # Below dermatologist minimum - very low adoption
            # REUS 2016: well below average, requires significant behavior change
            base_practicality = 2.0 + (duration - 3.0) * 0.5
        elif duration <= 8:
            # Near REUS 2016 average (7.8 min) - high adoption zone
            base_practicality = 3.0 + (duration - 5.0) * (4.0 / 3.0)
        elif duration <= 12:
            # Above average but within typical range - moderate adoption
            base_practicality = 7.0 + (duration - 8.0) * 0.5
        elif duration <= 15:
            # Declining-adoption tail approaching the 15-min upper bound (Harris Poll (2024)
            # reports 33% of adults exceed 15 min; this band is just below that).
            base_practicality = 9.0 - (duration - 12.0) * (1.5 / 3.0)
        else:
            # Harris Poll (2024): 33% self-report >15 min, but DeOreo et al. (2016) metered data implies a
            # much lower true rate, so this tail is modeled conservatively.
            base_practicality = max(1.5, 7.5 - (duration - 15.0) * 0.35)

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

        return max(1.5, min(10.0, total_practicality))

    def calculate_monthly_cost(self, per_shower_cost: float, occupants: int,
                               showers_per_person_per_day: float = 0.9) -> float:
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
        elif utilization < 1.5:
            import math
            return 0.5 * math.exp(-3.0 * (utilization - 1.0))
        else:
            return 0.0


    def apply_value_function(self, raw_value: float, vf_spec: str, value_type: str) -> float:
        reference_ranges = {
            'energy_cost': {
                # 5th-95th percentile of the actual scenario-set per-shower cost
                # distribution: p5 = $0.14, p95 = $1.14. Shower energy follows the
                # dynamic mixing-fraction physics (target=105F),
                #   kWh = gpm * 8.33 lb/gal * (TARGET_SHOWER_TEMP - inlet) * duration
                #         / (3412 BTU/kWh * 0.92 UEF),
                # priced at the PA residential rate ($0.19/kWh). Dataset-percentile
                # bounds (vs. a theoretical physics envelope) concentrate score
                # sensitivity over the durations/flows households actually encounter.
                # Sources: DeOreo et al. (2016); Hendron & Burch (2008) (PA seasonal
                # inlet temps); EIA Electric Power Annual (2025) (PA residential rate).
                'min': 0.14,
                'max': 1.14,
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
                'max': 10.0,
                'decreasing': False
            },
            'practicality': {
                # VF floor 0.5 sits below the raw practicality floor of 1.5 so the least
                # practical-but-feasible option keeps a small positive utility instead of
                # collapsing to exactly zero. Internal normalization choice (not a literature
                # value): no feasible option is treated as absolutely infeasible
                # (Keeney & Raiffa (1976) value-measurability convention).
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

        # Normalize to create x_normalized (can go outside [0,1] range for extrapolation)
        if ref['decreasing']:
            # Lower raw value = higher score (e.g., cost, emissions)
            x_normalized = (x_max - x) / (x_max - x_min)
        else:
            # Higher raw value = higher score (e.g., comfort, practicality)
            x_normalized = (x - x_min) / (x_max - x_min)

        # Apply transformation based on value function type
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

        return max(0.0, min(10.0, u_x * 10.0))
    
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

            # Calculate raw values
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

            # Apply budget penalty to energy cost score if budget constraint exists
            if 'utility_budget' in scenario and scenario['utility_budget'] > 0:
                occupants = scenario.get('household_size', 2)

                # Calculate monthly cost
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost'],
                    occupants,
                    showers_per_person_per_day=0.9  # Q21: REU2016 average
                )

                # Calculate and apply penalty
                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    scenario['utility_budget']
                )

                # Apply penalty to energy cost score
                energy_vf_penalized = energy_vf * budget_penalty
                energy_vf = energy_vf_penalized

            # Store final scores
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
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_shower.xlsx")):
    csv_path = Path(xlsx_filename)
    output_path = Path(output_filename)
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

def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
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

        # Rank alternatives: higher weighted sum = better (rank 1). Ties are
        # broken deterministically by TIE_BREAK_PRIORITY criteria (each desc)
        order = sorted(
            range(len(alternatives)),
            key=lambda i: (weighted_scores[i],
                           *[alternatives_scores[i][c] for c in TIE_BREAK_PRIORITY]),
            reverse=True,
        )
        ranked_alternatives = [alternatives[i] for i in order]

        ranks = [0] * len(alternatives)
        for rank_position, alt_index in enumerate(order):
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
    process_shower_scenarios()
