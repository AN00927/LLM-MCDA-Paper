
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

    EMISSIONS_FACTOR_PA = 0.6458  # lbs CO2/kWh, EPA eGRID 2023 Pennsylvania
    ELECTRICITY_RATE_PA = 0.17  # $/kWh, PA residential blended 2025-26

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

    # Placeholder - will be updated after analyzing scenario distribution
    REFERENCE_RANGES = {
        'energy_cost': {
            'min': 0.05,  # 5th percentile placeholder
            'max': 0.50,  # 95th percentile placeholder
            'decreasing': True
        },
        'environmental': {
            'min': 0.03,  # Derived from energy bounds
            'max': 0.32,  # Derived from energy bounds
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
        Uses range-based transitions to avoid hard cutoffs.

        Args:
            outdoor_temp: Outdoor temperature in °F

        Returns:
            Inlet water temperature in °F
        """
        if outdoor_temp < 35:
            return ShowerGroundTruthCalculator.INLET_TEMP_WINTER
        elif outdoor_temp < 45:
            # Transition zone: blend winter and spring/fall
            blend = (outdoor_temp - 35) / 10.0
            return (ShowerGroundTruthCalculator.INLET_TEMP_WINTER * (1 - blend) +
                    ShowerGroundTruthCalculator.INLET_TEMP_SPRING_FALL * blend)
        elif outdoor_temp < 65:
            return ShowerGroundTruthCalculator.INLET_TEMP_SPRING_FALL
        elif outdoor_temp < 75:
            # Transition zone: blend spring/fall and summer
            blend = (outdoor_temp - 65) / 10.0
            return (ShowerGroundTruthCalculator.INLET_TEMP_SPRING_FALL * (1 - blend) +
                    ShowerGroundTruthCalculator.INLET_TEMP_SUMMER * blend)
        else:
            return ShowerGroundTruthCalculator.INLET_TEMP_SUMMER

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
        if duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_MIN:
            base_practicality = 3.0  # Very difficult to maintain consistently
        elif duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_OPTIMAL:
            base_practicality = 6.0  # Moderately difficult - at or below average
        elif duration <= ShowerGroundTruthCalculator.COMFORT_DURATION_MAX:
            base_practicality = 9.0  # Easy to maintain - typical range
        else:
            base_practicality = 8.0  # Still easy, but wasteful from conservation standpoint

        # Component 2: Hot water capacity constraint (HARD CUTOFF)
        # Calculate total hot water needed if all occupants shower back-to-back
        hot_water_per_shower = duration * gpm * ShowerGroundTruthCalculator.HOT_WATER_FRACTION
        total_hot_water_needed = hot_water_per_shower * occupants

        # Available hot water is ~80% of tank (usable fraction)
        available_capacity = tank_size * 0.80

        capacity_penalty = 0.0
        if total_hot_water_needed > available_capacity:
            # Hard cutoff: will run out of hot water
            capacity_penalty = 3.0

        total_practicality = base_practicality - capacity_penalty

        # Floor at 1.5 (same as HVAC/Appliance pattern)
        return max(1.5, min(10.0, total_practicality))

    @staticmethod
    def parse_alternative(alt: str) -> float:
        """
        Parse shower duration from alternative string.

        Expected formats:
        - "5" → 5 minutes
        - "8" → 8 minutes
        - "12" → 12 minutes

        Args:
            alt: Alternative string

        Returns:
            Duration in minutes
        """
        # Simple numeric extraction
        alt_clean = alt.strip().lower()

        # Handle numeric-only strings
        try:
            duration = float(alt_clean)
            return duration
        except ValueError:
            pass

        # Extract first number found
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', alt_clean)
        if match:
            return float(match.group(1))

        raise ValueError(f"Could not parse duration from alternative: {alt}")

    @staticmethod
    def apply_value_function(raw_value: float, vf_spec: str, value_type: str) -> float:
        """
        Apply Multi-Attribute Value Theory (MAVT) value function transformation.

        EXACT COPY from HVAC/Appliance calculators for consistency.

        Steps:
        1. Normalize to [0,1] using reference range
        2. Apply transformation (linear, polynomial, exponential, etc.)
        3. Scale to [0,10]

        Args:
            raw_value: Raw criterion value
            vf_spec: Value function specification (e.g., "linear", "concave, alpha=0.5")
            value_type: Criterion name for reference range lookup

        Returns:
            Transformed value score (0-10)
        """
        # Get reference range
        ref = ShowerGroundTruthCalculator.REFERENCE_RANGES.get(value_type)
        if ref is None:
            raise ValueError(f"No reference range defined for {value_type}")

        min_val = ref['min']
        max_val = ref['max']
        decreasing = ref['decreasing']

        # Step 1: Normalize to [0,1]
        if max_val == min_val:
            u_x = 0.5  # Avoid division by zero
        else:
            if decreasing:
                # Lower is better: normalize as (max - x) / (max - min)
                u_x = (max_val - raw_value) / (max_val - min_val)
            else:
                # Higher is better: normalize as (x - min) / (max - min)
                u_x = (raw_value - min_val) / (max_val - min_val)

        # Clamp to [0,1]
        u_x = max(0.0, min(1.0, u_x))

        # Step 2: Apply transformation
        vf_lower = vf_spec.strip().lower()

        if vf_lower == "linear":
            transformed = u_x

        elif vf_lower.startswith("concave"):
            # Polynomial with exponent < 1
            # Extract alpha (default 0.5)
            alpha = 0.5
            if "alpha=" in vf_lower:
                try:
                    alpha = float(vf_lower.split("alpha=")[1].split(",")[0].split(")")[0])
                except:
                    pass
            transformed = u_x ** alpha

        elif vf_lower.startswith("convex"):
            # Polynomial with exponent > 1
            # Extract beta (default 2.0)
            beta = 2.0
            if "beta=" in vf_lower:
                try:
                    beta = float(vf_lower.split("beta=")[1].split(",")[0].split(")")[0])
                except:
                    pass
            transformed = u_x ** beta

        elif vf_lower.startswith("piecewise"):
            # Piecewise with threshold and post-threshold exponent
            threshold = 0.5
            beta = 2.0
            if "threshold=" in vf_lower:
                try:
                    threshold = float(vf_lower.split("threshold=")[1].split(",")[0])
                except:
                    pass
            if "beta=" in vf_lower:
                try:
                    beta = float(vf_lower.split("beta=")[1].split(",")[0].split(")")[0])
                except:
                    pass

            if u_x <= threshold:
                transformed = (u_x / threshold) ** 0.5  # Concave below threshold
            else:
                # Convex above threshold
                excess = (u_x - threshold) / (1.0 - threshold)
                transformed = (threshold ** 0.5) + (1.0 - threshold ** 0.5) * (excess ** beta)

        elif vf_lower.startswith("exponential"):
            # Exponential: (1 - exp(-a*u_x)) / (1 - exp(-a))
            a = 2.0
            if "a=" in vf_lower:
                try:
                    a = float(vf_lower.split("a=")[1].split(",")[0].split(")")[0])
                except:
                    pass
            import math
            if abs(a) < 0.001:
                transformed = u_x  # Avoid division issues
            else:
                transformed = (1.0 - math.exp(-a * u_x)) / (1.0 - math.exp(-a))

        elif vf_lower.startswith("logarithmic"):
            # Logarithmic: log(a*u_x + 1) / log(a + 1)
            a = 9.0
            if "a=" in vf_lower:
                try:
                    a = float(vf_lower.split("a=")[1].split(",")[0].split(")")[0])
                except:
                    pass
            import math
            if a < 0.001:
                transformed = u_x
            else:
                transformed = math.log(a * u_x + 1.0) / math.log(a + 1.0)

        else:
            # Default to linear if unknown
            transformed = u_x

        # Step 3: Scale to [0,10]
        final_score = transformed * 10.0

        return max(0.0, min(10.0, final_score))

    @staticmethod
    def calculate_scenario_scores(scenario: dict) -> dict:
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
        water_heater = scenario.get('Water Heater', 'Electric')
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
                try:
                    duration = ShowerGroundTruthCalculator.parse_alternative(scenario[alt_key])
                    alternatives.append({
                        'name': scenario[alt_key],
                        'duration': duration
                    })
                except Exception as e:
                    print(f"Warning: Could not parse {alt_key}: {scenario[alt_key]} - {e}")

        if not alternatives:
            raise ValueError("No valid alternatives found in scenario")

        # Calculate scores for each alternative
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

        # Apply value functions if specified
        vf_specs = scenario.get('vf_specs', {})

        for result in results:
            transformed = {}
            for criterion in ['energy_cost', 'environmental', 'comfort', 'practicality']:
                raw_val = result['raw_values'][criterion]
                vf_spec = vf_specs.get(criterion, 'linear')

                transformed[criterion] = ShowerGroundTruthCalculator.apply_value_function(
                    raw_val, vf_spec, criterion
                )

            result['transformed_values'] = transformed

        print(f"\n{'=' * 60}\n")

        return {
            'scenario': scenario.get('Description', 'N/A'),
            'alternatives': results
        }


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
        iscomplex
    """

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
            'is_complex': row['iscomplex'] == "TRUE",
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
                    'outdoor_temp': row['Outdoor Temp'],
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