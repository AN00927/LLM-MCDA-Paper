import pandas as pd
import math
from typing import Dict, List, Tuple
class ShowerGroundTruthCalculator:
    """
    Calculate physics-based ground truth scores for shower duration decisions.

    Energy consumption based on water heating physics, comfort based on duration
    and temperature adequacy, practicality based on behavioral adoption and
    hot water capacity constraints.

    Key Citations:
    - REU2016 (Residential End Uses of Water): Average shower 7.8 min at 2.1 GPM
    - Rinnai/Chronomite groundwater temperature maps: PA inlet temps 52-57°F annual
    - DOE/Rheem water heater specs: Electric tank UEF 0.92 typical for 40-50 gal
    - CDC/OSHA Legionella control: 140°F storage, 120°F delivery optimal
    - Healthline/dermatology: 5-10 min recommended shower duration
    """

    # EPA eGRID2022: Pennsylvania grid emissions 0.85 lb CO2/kWh
    # Citations: EPA eGRID2022 [Ref 77,81], PA DEP 2021 [Ref 29,32]
    EMISSIONS_FACTOR_PA = 0.6458  # lbs CO2/kWh

    # EIA 2024-2025: Pennsylvania residential average
    # Citations: EIA state data [Ref 29], PA suppliers [Ref 28]
    ELECTRICITY_RATE_PA = 0.19  # $/kWh

    # Rinnai/Chronomite groundwater maps: PA in 52-57°F band annual average
    # Seasonal variation: winter dips to high 40s, summer rises to mid 60s
    INLET_TEMP_WINTER = 45  # °F, outdoor <40°F (Rinnai/Chronomite)
    INLET_TEMP_SPRING_FALL = 55  # °F, outdoor 40-70°F (PA 52-57°F band)
    INLET_TEMP_SUMMER = 65  # °F, outdoor >70°F (seasonal rise)

    # DOE standards and manufacturer specs
    ELECTRIC_HEATER_EFFICIENCY = 0.92  # UEF 0.90-0.93 for 40-50 gal electric (DOE/Rheem)
    HOT_WATER_FRACTION = 0.65  # Fraction of shower water from hot side (mixing physics)
    WATER_DENSITY = 8.33  # lbs/gallon (standard)
    BTU_PER_KWH = 3412  # Conversion factor (standard)

    # REU2016: Average US shower 7.8 minutes
    # Healthline/dermatology: 5-10 min recommended
    COMFORT_DURATION_MIN = 5  # Rushed but viable (bottom of recommended range)
    COMFORT_DURATION_OPTIMAL = 8  # US average from REU2016 (7.8 min)
    COMFORT_DURATION_MAX = 12  # Comfortable upper bound (typical 5-15 min range)

    # CDC/OSHA/ASHRAE temperature standards
    HEATER_TEMP_MINIMUM = 110  # °F, below this feels lukewarm
    HEATER_TEMP_OPTIMAL = 120  # °F, standard residential setpoint
    HEATER_TEMP_SCALD_RISK = 130  # °F, scald risk increases above this
    HEATER_TEMP_LEGIONELLA_SAFE = 140  # °F, CDC/OSHA storage recommendation

    # Behavioral adoption estimates (modeled from REU2016 distribution)
    PRACTICALITY_SHORT_ADOPTION = 0.30  # ~30% maintain <7 min without intervention
    PRACTICALITY_MEDIUM_ADOPTION = 0.65  # ~65% maintain 8-10 min (Harris Poll)

    # Tank capacity standards
    TANK_RECOVERY_ELECTRIC = 21  # GPH @ 90°F rise (plumbing guides)
    FIRST_HOUR_RATING_40GAL = 50  # Gallons available in first hour
    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Management Science 26(8):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact - physical units have linear marginal value
    # Kotchen & Moore (2007): "When environmental impacts are framed in absolute physical
    # units (tons CO₂, lbs emissions), people exhibit approximately linear preferences"
    # (J. Environmental Economics and Management 54(1):100-123)
    VF_ENVIRONMENTAL = "linear"

    # test if needs adjustment
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"

    REFERENCE_RANGES = {
        'energy_cost': {
            # Q23: Shower energy cost ranges in PA (electric, 0.9-0.95 efficiency)
            # Min: 5 min, 2.0 GPM, ΔT≈50°F (summer 55→105°F)
            #      1.3 kWh × $0.19 = $0.25 (use 0.20 for 5th percentile)
            # Max: 15 min, 2.5 GPM, ΔT≈70°F (winter 50→120°F)
            #      6.9 kWh × $0.19 = $1.31 (use 1.40 for 95th percentile)
            # Citations: Q23, Q17-Q19 [Ref 57,58,33,31,28]
            'min': 0.20,
            'max': 1.40,
            'decreasing': True
        },
        'environmental': {
            # Derived from energy bounds × emissions factor
            # Min: 1.3 kWh × 0.85 = 1.11 lbs CO2 (round to 1.10)
            # Max: 6.9 kWh × 0.85 = 5.87 lbs CO2 (round to 5.90)
            # Citations: EPA eGRID2022 [Ref 77,29], Q18-Q19 [Ref 57,58,33]
            'min': 1.10,
            'max': 5.90,
            'decreasing': True
        },
        'comfort': {
            'min': 0.0,
            'max': 10.0,
            'decreasing': False
        },
        'practicality': {
            'min': 1.5,  # Floor prevents zero practicality
            'max': 10.0,
            'decreasing': False
        }
    }

    @staticmethod
    def determine_inlet_temp(outdoor_temp: float) -> float:
        """
        Determine inlet (cold) water temperature based on outdoor temperature.

        Q17 Research: Linear interpolation for PA inlet water temperature
        Based on NREL mains temp models [Ref 53,54] and Philadelphia data [Ref 52,56]

        Formula: inlet = 45 + (outdoor - 32) × (20/43)
        - outdoor ≤32°F → inlet = 45°F (winter minimum)
        - outdoor = 75°F → inlet = 65°F (summer maximum)
        - Linear between these points

        Examples:
        - 28°F outdoor → 45°F inlet (winter, capped)
        - 55°F outdoor → 55.7°F inlet
        - 85°F outdoor → 65°F inlet (summer, capped)

        ΔT Impact:
        - Winter: 120°F - 45°F = 75°F rise (36% more energy than summer)
        - Summer: 120°F - 65°F = 55°F rise

        Args:
            outdoor_temp: Outdoor temperature in °F

        Returns:
            Inlet water temperature in °F
        """
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
        """
        Calculate energy consumption for shower in kWh.

        Physics-based formula:
        Energy (kWh) = (GPM × 8.33 lbs/gal × ΔT°F × duration_min) / (3412 BTU/kWh × efficiency)

        Args:
            duration_min: Shower duration in minutes
            gpm: Flow rate in gallons per minute
            water_heater_temp: Water heater setpoint temperature in °F
            outdoor_temp: Outdoor temperature (for inlet temp determination)

        Returns:
            Energy consumption in kWh
        """
        inlet_temp = ShowerGroundTruthCalculator.determine_inlet_temp(outdoor_temp)
        delta_t = water_heater_temp - inlet_temp

        # Only heat the hot water fraction (rest is cold water mixed in)
        effective_gpm = gpm * ShowerGroundTruthCalculator.HOT_WATER_FRACTION

        # Energy = (flow × density × temp_rise × time) / (conversion × efficiency)
        energy_kwh = (effective_gpm * ShowerGroundTruthCalculator.WATER_DENSITY *
                      delta_t * duration_min) / (ShowerGroundTruthCalculator.BTU_PER_KWH *
                                                 ShowerGroundTruthCalculator.ELECTRIC_HEATER_EFFICIENCY)

        return energy_kwh

    @staticmethod
    def calculate_energy_cost(kwh: float, electricity_rate: float = None) -> float:
        """
        Calculate energy cost in dollars.

        Args:
            kwh: Energy consumption in kWh
            electricity_rate: Custom rate in $/kWh (optional, defaults to PA rate)

        Returns:
            Energy cost in dollars
        """
        rate = electricity_rate if electricity_rate is not None else ShowerGroundTruthCalculator.ELECTRICITY_RATE_PA
        return kwh * rate

    @staticmethod
    def calculate_environmental_impact(kwh: float) -> float:
        """
        Calculate CO2 emissions in pounds.

        Args:
            kwh: Energy consumption in kWh

        Returns:
            CO2 emissions in pounds
        """
        return kwh * ShowerGroundTruthCalculator.EMISSIONS_FACTOR_PA

    @staticmethod
    def calculate_comfort_score(duration: float, water_heater_temp: float,
                                occupants: int) -> float:
        """
        Calculate comfort score (0-10) based on shower duration, temperature adequacy,
        and household contention.

        Components:
        1. Duration comfort (REU2016 average 7.8 min)
        2. Temperature adequacy (CDC/OSHA standards)
        3. Household contention for hot water

        Args:
            duration: Shower duration in minutes
            water_heater_temp: Water heater setpoint in °F
            occupants: Number of household occupants

        Returns:
            Comfort score (0-10)
        """
        # Component 1: Duration comfort
        if duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_MIN:
            base_comfort = 4.0  # Very rushed - below dermatologist recommendation
        elif duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_OPTIMAL:
            base_comfort = 7.0  # Adequate - near empirical average
        elif duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_MAX:
            base_comfort = 10.0  # Comfortable - extended but still typical
        else:
            base_comfort = 8.0  # Diminishing returns - feels luxurious but wasteful

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
            # Penalty increases with duration above optimal
            excess_duration = max(0, duration - ShowerGroundTruthCalculator.COMFORT_DURATION_OPTIMAL)
            contention_penalty = excess_duration * 0.5

        total_comfort = base_comfort - temp_penalty - contention_penalty
        return max(0.0, min(10.0, total_comfort))

    @staticmethod
    def calculate_practicality_score(duration: float, occupants: int,
                                     tank_size: float, gpm: float) -> float:
        """
        Calculate practicality score (0-10) based on behavioral adoption likelihood
        and hot water capacity constraints.

        Components:
        1. Behavioral adoption (likelihood of maintaining duration)
        2. Hot water capacity (can tank support multiple showers?)

        Args:
            duration: Shower duration in minutes
            occupants: Number of household occupants
            tank_size: Water heater tank size in gallons
            gpm: Flow rate in gallons per minute

        Returns:
            Practicality score (0-10)
        """
        # Component 1: Behavioral adoption likelihood
        if duration <= 5:
            base_practicality = 2.0 + (duration - 3.0) * 0.5
        elif duration <= 8:
            base_practicality = 3.0 + (duration - 5.0) * (4.0 / 3.0)
        elif duration <= 12:
            base_practicality = 7.0 + (duration - 8.0) * 0.5
        elif duration <= 15:
            base_practicality = 9.0 - (duration - 12.0) * (0.5 / 3.0)
        else:
            base_practicality = max(7.0, 8.5 - (duration - 15.0) * 0.1)

        # Component 2: Hot water capacity constraint
        hot_water_per_shower = duration * gpm * ShowerGroundTruthCalculator.HOT_WATER_FRACTION
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
        """
        Convert per-shower cost to estimated monthly cost.

        Q21: Average 0.9 showers per person per day [REU2016]

        Args:
            per_shower_cost: Cost per shower ($)
            occupants: Number of household occupants
            showers_per_person_per_day: Frequency (default 0.9 from REU2016)

        Returns:
            Estimated monthly cost in dollars
        """
        showers_per_month = occupants * showers_per_person_per_day * 30
        return per_shower_cost * showers_per_month

    @staticmethod
    def calculate_budget_penalty(monthly_cost: float, monthly_budget: float) -> float:
        """
        Calculate budget constraint penalty multiplier.
        """
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
        """
        Apply Multi-Attribute Value Theory (MAVT) value function transformation.
        MAVT Framework:
        1. Normalize raw value using reference range [min, max]
        2. Apply transformation per value function spec
        3. Scale to [0, 10] and clamp final result

        Args:
            raw_value: Raw criterion value (e.g., dollars, lbs CO2, 0-10 score)
            vf_spec: Value function specification (e.g., "linear", "logarithmic, a=1.5")
            value_type: Criterion name for reference range lookup

        Returns:
            Transformed score on 0-10 scale
        """
        # Get reference range for this criterion
        reference_ranges = self.REFERENCE_RANGES

        ref = reference_ranges[value_type]
        x_min = ref['min']
        x_max = ref['max']

        # Use raw_value directly - allow extrapolation (following HVAC pattern)
        # Don't clamp to [min, max] before transformation
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
            # Linear: u(x) = x
            # Dyer & Sarin (1979): Appropriate for monetary attributes
            u_x = x_normalized

        elif vf_type == 'polynomial':
            # Polynomial: u(x) = x^a
            # a > 1: risk averse (concave), a < 1: risk seeking (convex)
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0  # Default to linear if parameter not found
            u_x = x_normalized ** a

        elif vf_type == 'exponential':
            # Exponential: u(x) = (1 - e^(ax)) / (1 - e^a)
            # a > 0: risk averse, a < 0: risk seeking
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0  # Default parameter

            if a == 0:
                u_x = x_normalized  # Degenerate to linear
            else:
                import math
                u_x = (1 - math.exp(a * x_normalized)) / (1 - math.exp(a))

        elif vf_type == 'logarithmic':
            # Logarithmic: u(x) = ln(ax + 1) / ln(a + 1)
            # a > 0: risk averse (concave)
            try:
                a = float([p for p in vf_spec.split(',') if 'a=' in p][0].split('=')[1].strip())
            except:
                a = 1.0  # Default parameter

            if a == -1:
                u_x = x_normalized  # Degenerate to linear
            else:
                import math
                # Handle negative x_normalized (better than best case)
                if a * x_normalized + 1 <= 0:
                    u_x = 1.0  # Cap at perfect score
                else:
                    u_x = math.log(a * x_normalized + 1) / math.log(a + 1)

        else:
            u_x = x_normalized

        # This is the only point where we prevent extrapolation
        return max(0.0, min(10.0, u_x * 10.0))
    def calculate_scenario_scores(self, scenario: dict) -> dict:
        """
        Calculate ground truth scores for all alternatives in a shower scenario.

        Args:
            scenario: Dictionary containing scenario parameters and alternatives

        Returns:
            Dictionary with calculated scores for each criterion and alternative
        """
        # Extract scenario parameters
        location = scenario.get('Location', 'Unknown')
        occupants = int(scenario.get('Occupants', 2))
        tank_size = float(scenario.get('Tank Size', 40))
        gpm = float(scenario.get('GPM', 2.5))
        outdoor_temp = float(scenario.get('Outdoor Temp', 50))
        water_heater_temp = float(scenario.get('Water Heater Temp', 120))

        print(f"\n{'=' * 60}")
        print(f"SHOWER SCENARIO: {scenario.get('Description', 'N/A')}")
        print(f"Location: {location}")
        print(f"Occupants: {occupants} | Tank: {tank_size} gal | Flow: {gpm} GPM")
        print(f"Outdoor: {outdoor_temp}°F | Heater: {water_heater_temp}°F")
        print(f"{'=' * 60}")

        # Parse alternatives
        alternatives = []
        for i in range(1, 4):
            alt_key = f'Alternative {i}'
            if alt_key in scenario:
                duration = float(scenario[alt_key])
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
            emissions = ShowerGroundTruthCalculator.calculate_environmental_impact(kwh)
            comfort = ShowerGroundTruthCalculator.calculate_comfort_score(
                duration, water_heater_temp, occupants
            )
            practicality = ShowerGroundTruthCalculator.calculate_practicality_score(
                duration, occupants, tank_size, gpm
            )

            print(f"\n{alt['name']} ({duration} min):")
            print(f"  Energy: {kwh:.4f} kWh → ${cost:.3f}")
            print(f"  Emissions: {emissions:.3f} lbs CO2")
            print(f"  Comfort: {comfort:.2f}/10")
            print(f"  Practicality: {practicality:.2f}/10")

            results.append({
                'alternative': alt['name'],
                'duration': duration,
                'raw_values': {
                    'energy_kwh': kwh,
                    'energy_cost': cost,
                    'environmental': emissions,
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

            try:
                energy_vf = self.apply_value_function(
                    raw['energy_cost'],
                    self.VF_ENERGY_COST,
                    'energy_cost'
                )
                print(f"  After VF ({vf_specs['energy_cost']}): Energy = {energy_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Energy VF ERROR: {e}")
                energy_vf = 5.0

            try:
                env_vf = self.apply_value_function(
                    raw['environmental'],
                    self.VF_ENVIRONMENTAL,
                    'environmental'
                )
                print(f"  After VF ({vf_specs['environmental']}): Environmental = {env_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Environmental VF ERROR: {e}")
                env_vf = 5.0

            try:
                comfort_vf = self.apply_value_function(
                    raw['comfort'],
                    self.VF_COMFORT,
                    'comfort'
                )
                print(f"  After VF ({vf_specs['comfort']}): Comfort = {comfort_vf:.2f}/10")
            except Exception as e:
                print(f"  ✗ Comfort VF ERROR: {e}")
                comfort_vf = raw['comfort']  # Already 0-10

            try:
                practicality_vf = self.apply_value_function(
                    raw['practicality'],
                    self.VF_PRACTICALITY,
                    'practicality'
                )

            except Exception as e:
                print(f"  ✗ Practicality VF ERROR: {e}")
                practicality_vf = raw['practicality']  # Already 0-10

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
                    f"  Utilization: {monthly_cost / scenario['Utility Budget'] * 100:.1f}% → penalty: {budget_penalty:.3f}")
                print(f"  Energy score: {energy_vf:.2f} → {energy_vf_penalized:.2f} (after penalty)")

                energy_vf = energy_vf_penalized

            # Store final scores
            result['transformed_values'] = {
                'energy_cost': round(energy_vf, 2),
                'environmental': round(env_vf, 2),
                'comfort': round(comfort_vf, 2),
                'practicality': round(practicality_vf, 2)
            }

            print(f"  → FINAL SCORES:")
            print(f"     Energy: {energy_vf:.2f}, Environmental: {env_vf:.2f}, "
                  f"Comfort: {comfort_vf:.2f}, Practicality: {practicality_vf:.2f}\n")

        print(f"\n{'=' * 60}\n")

        return {
            'scenario': scenario.get('Description', 'N/A'),
            'alternatives': results
        }


def process_shower_scenarios(csv_filename: str = "ShowerScenarios.csv",
                             output_filename: str = "ground_truth_shower.csv"):
    """
    Read Shower scenarios from CSV and calculate ground truth scores for all alternatives.

    Args:
        csv_filename: Path to CSV file with scenarios
        output_filename: Where to save ground truth results

    Expected CSV columns:
        Description, Location, Occupants, Water Heater, Tank Size, GPM,
        Utility Budget, Housing Type, Outdoor Temp, Water Heater Temp,
        Alternative 1, Alternative 2, Alternative 3
    """
    import pandas as pd

    df = pd.read_csv(csv_filename)
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

            # Extract scores from result and flatten to CSV rows
            for alt_data in result['alternatives']:
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
                    'raw_kwh': alt_data['raw_values']['energy_kwh'],
                    'raw_cost': alt_data['raw_values']['energy_cost'],
                    'raw_emissions': alt_data['raw_values']['environmental']
                }
                results.append(result_row)

        except Exception as e:
            print(f"ERROR processing scenario {idx}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Save results to CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_filename, index=False)

    print(f"\nGround truth saved to {output_filename}")
    print(f"Total alternatives scored: {len(results_df)}")
    return results_df


# Main execution block
if __name__ == "__main__":
    process_shower_scenarios(
        csv_filename="ShowerScenarios.csv",
        output_filename="ground_truth_shower.csv"
    )