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
from model_config import CRITERION_WEIGHTS

class ShowerGroundTruthCalculator:
    """"Key sources:
- Residential End Uses of Water, Version 2 (REU2016). Water Research Foundation.
  Average shower 7.8 min; 0.9 showers/person/day.
- Hendron, R., & Burch, J. (2008). NREL/TP-550-40874. Mains temp model.
- Maguire, J., et al. (2013). NREL/TP-5500-58756. Hot water distribution validation.
- Rheem Manufacturing Company. (2025). Electric Tank Water Heaters — Product Specs.
- Centers for Disease Control and Prevention (CDC). (2026).
  Monitoring Building Water: A Vital Step for Control of Legionella.
- Zhang, D., Mui, K.-W., & Wong, L.-T. (2023). Buildings, 13(5), 1300.
"""

    # PA residential electricity price from EIA (2024)
    ELECTRICITY_RATE_PA = 0.19  # $/kWh; flat-rate default (see modeling choice above)

    # PA seasonal mains water temperatures.
    # Sources: Hendron & Burch (2008), NREL/TP-550-40874; Maguire et al. (2013), NREL/TP-5500-58756.
    INLET_TEMP_WINTER = 45  # F, outdoor <=32F
    INLET_TEMP_SPRING_FALL = 55  # F, outdoor 32-75F
    INLET_TEMP_SUMMER = 65  # F, outdoor >=75F

    # UEF 0.90-0.93 for 40-55 gal electric tank.
    # Source: Rheem Manufacturing Company. (2025). Residential Tank Water Heaters
    #         Product Specifications (electric models 40-55 gal). Midpoint: 0.92.
    ELECTRIC_HEATER_EFFICIENCY = 0.92
    TARGET_SHOWER_TEMP = 105.0  # F, typical comfortable shower delivery temp (zhang2023)
    WATER_DENSITY = 8.33  # lbs/gallon (standard)
    BTU_PER_KWH = 3412  # Conversion factor (standard)

    # Duration comfort thresholds.
    # Average 7.8 min from REU2016 (Water Research Foundation).
    # Long-duration prevalence (33% >15 min) from The Harris Poll (2024).
    COMFORT_DURATION_MIN = 5  # Rushed but viable
    COMFORT_DURATION_OPTIMAL = 7.8  # REU2016 average of 7.8 min
    COMFORT_DURATION_MAX = 15  # Comfortable upper bound

    # Temperature thresholds from CDC Legionella guidance (CDC, 2026):store at >=140F; deliver/recirculate at >=120F.
    HEATER_TEMP_MINIMUM = 110  # F, lukewarm boundary
    HEATER_TEMP_OPTIMAL = 120  # F, standard delivery setpoint (CDC, 2026)
    HEATER_TEMP_SCALD_RISK = 130  # F, scald risk threshold
    HEATER_TEMP_LEGIONELLA_SAFE = 140  # F, CDC minimum storage temp (CDC, 2026)
     # Behavioral adoption estimates (modeled from REU2016 distribution)
    PRACTICALITY_SHORT_ADOPTION = 0.30  # ~30% maintain <7 min without intervention
    PRACTICALITY_MEDIUM_ADOPTION = 0.65  # ~65% maintain 8-10 min (Harris Poll)

    # Tank capacity standards
    TANK_RECOVERY_ELECTRIC = 21  # GPH at 90F rise (plumbing guides)
    FIRST_HOUR_RATING_40GAL = 50  # Gallons available in first hour
    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Management Science 26(8):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact - physical units have linear marginal value
    # For MAVT framework justification, see:
    # - Keeney, R. L., & Raiffa, H. (1976). Decisions with Multiple Objectives: Preferences 
    #   and Value Trade-offs. Wiley. (Foundation for Multi-Attribute Value Theory axioms)
    # Linear VF justification in this context: When environmental impacts are framed in 
    # absolute physical units (lbs CO₂), a linear preference is a conservative modeling choice
    # that treats equal changes in emissions as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"

    REFERENCE_RANGES = {
        'energy_cost': {
            # Re-derived under the dynamic mixing-fraction physics (calculate_shower_energy
            # uses target=105F so total shower energy reduces to
            #   kWh = gpm * 8.33 lb/gal * (TARGET_SHOWER_TEMP - inlet) * duration
            #         / (3412 BTU/kWh * 0.92 UEF)
            # which is independent of heater setpoint and depends only on target-vs-inlet
            # and flow-time).
            #
            # Min (short, summer, efficient):
            #   1.5 GPM (WaterSense low-flow) x 5 min x summer inlet 65F
            #   -> 1.5 * 8.33 * 40 * 5 / (3412 * 0.92) = 0.80 kWh -> $0.15 at $0.19/kWh
            # Max (long, winter, higher flow incl. dataset extension to 3.5 GPM):
            #   3.5 GPM (older / non-WaterSense multi-jet) x 15 min x winter inlet 45F
            #   -> 3.5 * 8.33 * 60 * 15 / (3412 * 0.92) = 8.36 kWh -> $1.59 at $0.19/kWh
            #
            # Sources for endpoints: REU2016 (Water Research Foundation, short-duration
            # benchmark); Harris Poll (2024, long-duration prevalence); Hendron & Burch
            # (2008) NREL/TP-550-40874 (PA seasonal inlet temps); EPA WaterSense
            # Appendix B (GPM benchmarks); EIA (2024) PA residential rate.
            'min': 0.15,
            'max': 1.50,
            'decreasing': True
        },
        'environmental': {
            # Environmental criterion = water volume consumed (gallons) per shower.
            # Bounds derived from EPA conservation-planning Appendix B 5th-95th percentile
            # GPM (1.5-5.0) and duration (5-15 min):
            #   5th x 5th = 1.5 GPM x 5 min = 7.5 gal
            #   95th x 95th = 5.0 GPM x 15 min = 75 gal (EPA reference upper bound)
        
            # Source: EPA WaterSense conservation benchmarks (Appendix B).
            'min': 7.5,
            'max': 75,
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

    @staticmethod
    def determine_inlet_temp(outdoor_temp: float) -> float:
        """Determine inlet temp."""
        if outdoor_temp <= 32:
            return 45.0  # Winter minimum
        elif outdoor_temp >= 75:
            return 65.0  # Summer maximum
        else:
            # Linear interpolation: slope = 20/43 ≈ 0.465
            return 45.0 + (outdoor_temp - 32.0) * (20.0 / 43.0)

    @staticmethod
    def calculate_shower_energy(duration_min: float, gpm: float,
                                water_heater_temp: float, outdoor_temp: float) -> float:
        """Calculate shower energy."""
        inlet_temp = ShowerGroundTruthCalculator.determine_inlet_temp(outdoor_temp)
        delta_t = water_heater_temp - inlet_temp

        # Only heat the hot water fraction (rest is cold water mixed in)
        hot_fraction = ShowerGroundTruthCalculator.calculate_hot_water_fraction(
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

    @staticmethod
    def calculate_hot_water_fraction(water_heater_temp: float, inlet_temp: float,
                                     target_temp: float) -> float:
        """Calculate hot-water mixing fraction for a target delivery temperature."""
        # Mixing-energy balance for hot/cold streams.
        # Sources: hendron2008; maguire2013; zhang2023.
        if water_heater_temp <= inlet_temp:
            return 0.0
        fraction = (target_temp - inlet_temp) / (water_heater_temp - inlet_temp)
        return max(0.0, min(1.0, fraction))

    @staticmethod
    def calculate_energy_cost(kwh: float) -> float:
        """Calculate energy cost."""
        rate =ShowerGroundTruthCalculator.ELECTRICITY_RATE_PA
        return kwh * rate

    @staticmethod
    def calculate_environmental_impact(gpm: float, duration_min: float) -> float:
        """Calculate environmental impact as water volume consumed (gallons)."""
        return gpm * duration_min

    @staticmethod
    def calculate_comfort_score(duration: float, water_heater_temp: float,
                                occupants: int) -> float:
        """Calculate comfort score."""
        if duration <= 3.0:
            # Below dermatologist minimum — severely rushed.
            # Cubic ramp: 0.0 at 0 min → 4.0 at 3 min, with exponential penalization for
            # very short durations. At 2min: ~1.2 (vs ~3.0 with prior linear ramp).
            # Boundary at 3min = 4.0 is unchanged — no discontinuity with next segment.
            base_comfort = 4.0 * (duration / 3.0) ** 3
        elif duration <= 7.8:
            # Optimal range - REU2016 average at 7.8 min
            # Linear interpolation: 4.0 at 3 min → 10.0 at 7.8 min
            # Slope: (10.0 - 4.0) / (7.8 - 3.0) = 1.167
            base_comfort = 4.0 + ((duration - 3.0) / (7.8 - 3.0)) * 6.0
        elif duration <= 15.0:
            # Above optimal - diminishing returns, slight waste concern
            # Linear decline: 10.0 at 7.8 min → 8.0 at 15 min
            # Slope: (8.0 - 10.0) / (15.0 - 7.8) = -0.260
            base_comfort = 10.0 + ((duration - 7.8) / (15.0 - 7.8)) * (8.0 - 10.0)
        else:
            # Extreme duration - very wasteful
            # Continue linear decline: 0.5 per minute beyond 15 min
            base_comfort = max(1.0, 8.0 - (duration - 15.0) * 0.5)

        # Component 2: Temperature adequacy
        temp_penalty = 0.0
        if water_heater_temp < ShowerGroundTruthCalculator.HEATER_TEMP_MINIMUM:
            temp_penalty = 2.0  # Lukewarm, within Legionella growth range
        elif water_heater_temp > ShowerGroundTruthCalculator.HEATER_TEMP_SCALD_RISK:
            temp_penalty = 1.0  # Scald risk, no extra comfort benefit

        # Component 3: Household contention
        # Larger households experience pressure to keep showers short
        contention_penalty = 0.0
        if occupants >= 4:
            excess_duration = max(0, duration - ShowerGroundTruthCalculator.COMFORT_DURATION_OPTIMAL)
            contention_penalty = excess_duration * 0.5

        total_comfort = base_comfort - temp_penalty - contention_penalty
        return max(0.0, min(10.0, total_comfort))

    @staticmethod
    def calculate_practicality_score(duration: float, occupants: int,
                                     tank_size: float, gpm: float,
                                     water_heater_temp: float, outdoor_temp: float) -> float:
        """Calculate practicality score."""
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
            # Harris Poll (2024): ~33% of adults here - declining adoption
            base_practicality = 9.0 - (duration - 12.0) * (1.5 / 3.0)
        else:
            # Harris Poll (2024): 33% report >15 min but REUS metered data suggests
            # actual rate much lower, so conservative modeling
            base_practicality = max(1.5, 7.5 - (duration - 15.0) * 0.35)

        # Component 2: Hot water capacity constraint
        inlet_temp = ShowerGroundTruthCalculator.determine_inlet_temp(outdoor_temp)
        hot_fraction = ShowerGroundTruthCalculator.calculate_hot_water_fraction(
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

    @staticmethod
    def calculate_monthly_cost(per_shower_cost: float, occupants: int,
                               showers_per_person_per_day: float = 0.9) -> float:
        """Calculate monthly cost."""
        showers_per_month = occupants * showers_per_person_per_day * 30
        return per_shower_cost * showers_per_month

    @staticmethod
    def calculate_budget_penalty(monthly_cost: float, monthly_budget: float) -> float:
        """Calculate budget penalty."""
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
        """Apply value function."""
        reference_ranges = self.REFERENCE_RANGES

        ref = reference_ranges[value_type]
        x_min = ref['min']
        x_max = ref['max']

        # Use raw_value directly; don't clamp to [min, max] before transformation.
        x = raw_value

        # Parse value function type and parameters
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

        # This is the only point where we prevent extrapolation
        return max(0.0, min(10.0, u_x * 10.0))
    def calculate_scenario_scores(self, scenario: dict) -> dict:
        """Calculate scenario scores."""
        location = scenario.get('Location', 'Unknown')
        occupants = int(scenario.get('Occupants', 2))
        tank_size = float(scenario.get('Tank Size', 40))
        gpm = float(scenario.get('GPM', 2.5))
        outdoor_temp = float(scenario.get('outdoor_temp', scenario.get('Outdoor Temp', 50)))
        water_heater_temp = float(scenario.get('Water Heater Temp', 120))

        print(f"SHOWER SCENARIO: {scenario.get('Description', 'N/A')}")
        print(f"Location: {location}")
        print(f"Occupants: {occupants} | Tank: {tank_size} gal | Flow: {gpm} GPM")
        print(f"Outdoor: {outdoor_temp} degrees F | Heater: {water_heater_temp} degrees F")
        alternatives = []
        for i in range(1, 4):
            alt_key = f'Alternative {i}'
            if alt_key in scenario:
                val = scenario[alt_key]
                if pd.isna(val) if hasattr(pd, 'isna') else str(val).lower() in ('nan', '', 'none'):
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
            kwh = ShowerGroundTruthCalculator.calculate_shower_energy(
                duration, gpm, water_heater_temp, outdoor_temp
            )
            cost = ShowerGroundTruthCalculator.calculate_energy_cost(kwh)
            water_gallons = ShowerGroundTruthCalculator.calculate_environmental_impact(gpm, duration)
            comfort = ShowerGroundTruthCalculator.calculate_comfort_score(
                duration, water_heater_temp, occupants
            )
            practicality = ShowerGroundTruthCalculator.calculate_practicality_score(
                duration, occupants, tank_size, gpm, water_heater_temp, outdoor_temp
            )

            print(f"\n{alt['name']} ({duration} min):")
            print(f"  Energy: {kwh:.4f} kWh -> ${cost:.3f}")
            print(f"  Water: {water_gallons:.2f} gal ({gpm} GPM x {duration} min)")
            print(f"  Comfort: {comfort:.2f}/10")
            print(f"  Practicality: {practicality:.2f}/10")

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

            print(f"\nApplying value functions for: {alt}")

            vf_specs = scenario.get('vf_specs', {
                'energy_cost': self.VF_ENERGY_COST,
                'environmental': self.VF_ENVIRONMENTAL,
                'comfort': self.VF_COMFORT,
                'practicality': self.VF_PRACTICALITY
            })

            energy_vf = self.apply_value_function(
                raw['energy_cost'],
                self.VF_ENERGY_COST,
                'energy_cost'
            )
            print(f"  After VF ({vf_specs['energy_cost']}): Energy = {energy_vf:.2f}/10")

            env_vf = self.apply_value_function(
                raw['environmental'],
                self.VF_ENVIRONMENTAL,
                'environmental'
            )
            print(f"  After VF ({vf_specs['environmental']}): Environmental = {env_vf:.2f}/10")

            comfort_vf = self.apply_value_function(
                raw['comfort'],
                self.VF_COMFORT,
                'comfort'
            )
            print(f"  After VF ({vf_specs['comfort']}): Comfort = {comfort_vf:.2f}/10")

            practicality_vf = self.apply_value_function(
                raw['practicality'],
                self.VF_PRACTICALITY,
                'practicality'
            )

            # Apply budget penalty to energy cost score if budget constraint exists
            if 'Utility Budget' in scenario and scenario['Utility Budget'] > 0:
                occupants = scenario.get('Occupants', 2)

                # Calculate monthly cost
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost'],
                    occupants,
                    showers_per_person_per_day=0.9  # Q21: REU2016 average
                )

                # Calculate and apply penalty
                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    scenario['Utility Budget']
                )

                # Apply penalty to energy cost score
                energy_vf_penalized = energy_vf * budget_penalty

                print(f"  Budget check: ${monthly_cost:.2f}/month vs ${scenario['Utility Budget']:.2f} budget")
                print(f"  ({occupants} people × 0.9 showers/day × 30 days = {occupants * 0.9 * 30:.0f} showers/month)")
                print(
                    f"  Utilization: {monthly_cost / scenario['Utility Budget'] * 100:.1f}% -> penalty: {budget_penalty:.3f}")
                print(f"  Energy score: {energy_vf:.2f} -> {energy_vf_penalized:.2f} (after penalty)")

                energy_vf = energy_vf_penalized

            # Store final scores
            result['transformed_values'] = {
                'energy_cost': round(energy_vf, 2),
                'environmental': round(env_vf, 2),
                'comfort': round(comfort_vf, 2),
                'practicality': round(practicality_vf, 2)
            }

            print(f" fINAL SCORES:")
            print(f"     Energy: {energy_vf:.2f}, Environmental: {env_vf:.2f}, "
                  f"Comfort: {comfort_vf:.2f}, Practicality: {practicality_vf:.2f}\n")


        return {
            'scenario': scenario.get('Description', 'N/A'),
            'alternatives': results
        }


def process_shower_scenarios(
    csv_filename: str = str(SCENARIO_DIR / "ShowerScenarios.csv"),
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_shower.csv")):
    """Process shower scenarios."""
    import pandas as pd

    csv_path = Path(csv_filename)
    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} shower scenarios")

    calculator = ShowerGroundTruthCalculator()
    results = []

    for idx, row in df.iterrows():
        print(f"\nProcessing scenario {idx + 1}/{len(df)}: {row['Location']}")

        # Build scenario dict matching expected format
        scenario = {
            'Description': row['Description'],
            'Location': row['Location'],
            'Occupants': int(row['Occupants']),
            'Tank Size': float(row['Tank Size']),
            'GPM': float(row['GPM']),
            'Utility Budget': float(row['Utility Budget']),
            'Housing Type': row['Housing Type'],
            'Outdoor Temp': float(row['Outdoor Temp']),
            'Water Heater Temp': float(row['Water Heater Temp']),
            'Alternative 1': row['Alternative 1'],
            'Alternative 2': row['Alternative 2'],
            'Alternative 3': row['Alternative 3'],
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
            # Extract scores from result and flatten to CSV rows
            for alt_data in result['alternatives']:
                alt_idx = result['alternatives'].index(alt_data)
                result_row = {
                    'scenario_id': idx,
                    'description': row['Description'],
                    'location': row['Location'],
                    'occupants': row['Occupants'],
                    'gpm': row['GPM'],
                    'utility_budget': row['Utility Budget'],
                    'housing_type': row['Housing Type'],
                    'outdoor_temp': row['Outdoor Temp'],
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

    # Save results to CSV
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


# Main execution block
if __name__ == "__main__":
    process_shower_scenarios()
