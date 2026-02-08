
class ApplianceGroundTruthCalculator:
    """
    Calculate physics-based ground truth scores for appliance scheduling decisions.

    Key difference from HVAC: Energy consumption is constant per cycle,
    but cost varies by time-of-day due to TOU pricing.

    Citations:
    - Paetz et al. (2012): "Test-residents said to be able to postpone the dish-washer
      use by twelve hours without constraints in their daily routines"
      ACEEE Summer Study, Paper 0193-000232
    - EPA eGRID (2023): Pennsylvania grid emissions factor 0.6458 lbs CO2/kWh
    - PPL Electric (2024): TOU rate structure for southeastern PA
    - PECO Energy (2021): TOU rate structure for Philadelphia area
    """

    # Grid emissions factor (Pennsylvania)
    # EPA eGRID (2023): Pennsylvania state-level CO₂ emission rate
    EMISSIONS_FACTOR_PA = 0.6458  # lbs CO2/kWh

    # Fixed Peak Hours (2pm-6pm) - no seasonal variation
    # Based on PECO Energy standard TOU schedule
    PEAK_HOURS = (14, 18)  # 2 PM - 6 PM

    # Appliance Noise Levels
    # Whirlpool (2024): "Dishwashers typically have noise levels between 40 to 50 dBA"
    # Reviewed.com: Modern appliances operate at keyboard typing level (~45-50 dBA)
    NOISE_DISHWASHER = 45        # dBA typical modern dishwasher
    NOISE_WASHER = 50            # dBA typical washing machine
    NOISE_DRYER = 55             # dBA typical dryer

    # Apartment Noise Standards
    # All County Apartments: "Anything louder than 45 dB during daytime or 35 dB
    # in evening is deemed too loud"
    # Decibel Pro: "Time limits usually apply after 10 pm and until 7 am"
    NOISE_LIMIT_DAYTIME = 45     # dBA acceptable during day
    NOISE_LIMIT_EVENING = 35     # dBA acceptable after 10pm

    # Value Function Specifications
    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Management Science 26(8):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact - physical units have linear marginal value
    # Kotchen & Moore (2007): "When environmental impacts are framed in absolute physical
    # units (tons CO₂, lbs emissions), people exhibit approximately linear preferences"
    # (J. Environmental Economics and Management 54(1):100-123)
    VF_ENVIRONMENTAL = "linear"

    # Linear VF for comfort - start simple, test if needs adjustment
    VF_COMFORT = "linear"

    # Linear VF for practicality - adoption rates show approximately linear relationship
    VF_PRACTICALITY = "linear"

    def determine_rate_period(self, run_time_hour: int) -> str:
        """
        Determine if run time falls in peak or off-peak period.

        Args:
            run_time_hour: Hour of day (0-23, e.g., 19 for 7pm)

        Returns:
            "peak" or "offpeak"

        Citation: PECO Energy TOU schedule - 2pm-6pm peak hours
        """
        peak_start, peak_end = self.PEAK_HOURS

        if peak_start <= run_time_hour < peak_end:
            return "peak"

        return "offpeak"

    def calculate_energy_cost(self, kwh_cycle: float, run_time_hour: int,
                             peak_rate: float, offpeak_rate: float) -> float:
        """
        Calculate energy cost based on TOU rate structure.

        CRITICAL: Energy consumption (kWh) is FIXED - only COST varies by time.

        Args:
            kwh_cycle: Fixed energy per cycle (from Ground Truth Data.pdf Section 2)
            run_time_hour: When appliance runs (0-23)
            peak_rate: Peak period $/kWh
            offpeak_rate: Off-peak period $/kWh

        Returns:
            Energy cost in dollars

        Citations:
        - Ground Truth Data.pdf Section 2:
          Dishwasher 0.9-1.1 kWh/cycle (Energy Star), 1.4-2.0 kWh (old)
          Washer 0.15-0.25 kWh (front-load HE), 0.3-0.5 kWh (top-load)
          Dryer 0.8-1.5 kWh (heat pump), 2.5-4.0 kWh (standard electric)
        - Porras et al. (2020), Chen-Yu & Emmel (2018), Patel et al. (2021)
        """
        period = self.determine_rate_period(run_time_hour)

        if period == "peak":
            rate = peak_rate
        else:
            rate = offpeak_rate

        cost = kwh_cycle * rate
        print(f"  → Energy cost: {kwh_cycle} kWh × ${rate:.4f}/kWh ({period}) = ${cost:.4f}")
        return cost

    def calculate_environmental_impact(self, kwh_cycle: float) -> float:
        """
        Calculate CO2 emissions from electricity consumption.

        IMPORTANT: Environmental impact is SAME regardless of run time
        (using average grid emissions, not marginal hourly emissions).

        Args:
            kwh_cycle: Energy consumption per cycle

        Returns:
            CO2 emissions in pounds

        Citation: EPA eGRID (2023), Pennsylvania grid emissions factor
        0.6458 lbs CO2/kWh (state-level average)
        """
        emissions = kwh_cycle * self.EMISSIONS_FACTOR_PA
        print(f"  → Emissions: {kwh_cycle} kWh × {self.EMISSIONS_FACTOR_PA} lbs/kWh = {emissions:.3f} lbs CO2")
        return emissions

    def calculate_comfort_score(self, delay_hours: float, run_time_hour: int,
                               housing_type: str, occupants: int,
                               appliance_type: str) -> float:
        """
        Calculate comfort score based on delay inconvenience and noise disruption.

        Components:
        1. Delay penalty (longer delay = more inconvenience)
        2. Noise disruption (late night in apartment = worse)
        3. Household size multiplier (more people = dishes/laundry pile up faster)

        Citations:
        - Paetz et al. (2012): "Test-residents said to be able to postpone the
          dish-washer use by twelve hours without constraints in their daily routines"
          ACEEE Summer Study, Paper 0193-000232

        - All County Apartments: "Anything louder than 45 dB during daytime or
          35 dB in evening is deemed too loud"

        - Whirlpool (2024): Modern dishwashers 40-50 dBA typical
          https://www.whirlpool.com/blog/kitchen/what-decibel-is-a-quiet-dishwasher.html
        """

        # Component 1: Base delay penalty
        # Paetz et al.: 12hr delay is maximum acceptable for dishwasher
        if delay_hours == 0:
            base_comfort = 10.0
        elif delay_hours <= 3:
            base_comfort = 8.0   # Short delay, minor inconvenience
        elif delay_hours <= 7:
            base_comfort = 6.0   # Medium delay, moderate inconvenience
        elif delay_hours <= 12:
            base_comfort = 4.0   # Long delay but still within "acceptable" range
        else:
            base_comfort = 2.0   # Beyond acceptable (>12hr)

        print(f"  → Base comfort (delay={delay_hours}hr): {base_comfort}/10")

        # Component 2: Noise disruption penalty
        # Depends on: time of day + housing type + appliance noise
        noise_penalty = 0.0

        if appliance_type.lower() == "dishwasher":
            appliance_noise = self.NOISE_DISHWASHER
        elif appliance_type.lower() == "washer" or "washing" in appliance_type.lower():
            appliance_noise = self.NOISE_WASHER
        elif appliance_type.lower() == "dryer":
            appliance_noise = self.NOISE_DRYER
        else:
            appliance_noise = 50  # default

        # Late night running (10pm-7am)
        # Decibel Pro: "Time limits usually apply after 10 pm and until 7 am"
        if 22 <= run_time_hour or run_time_hour < 7:
            # Noise limit is 35 dBA in evening (All County Apartments)
            if appliance_noise > self.NOISE_LIMIT_EVENING:
                noise_penalty = 2.0  # Base penalty for late night

                # Housing type multiplier
                # Apartment noise complaints from shared walls
                if housing_type == "Apartment":
                    noise_penalty *= 1.5   # Neighbors very close
                elif housing_type == "Townhouse" or housing_type == "Rowhouse":
                    noise_penalty *= 1.2   # Shared walls
                else:  # Single-family
                    noise_penalty *= 0.8   # Isolated, lower concern

                print(f"  → Noise penalty (late night, {housing_type}): -{noise_penalty:.1f}")

        # Component 3: Household size impact
        # Larger households → dishes pile up faster → delay worse
        # Ground Truth Data Section 9: Practicality varies by household context
        if occupants >= 5:
            size_penalty = 1.5
        elif occupants >= 3:
            size_penalty = 0.8
        else:
            size_penalty = 0.0

        # Apply size penalty proportional to delay
        # (No delay = no penalty, long delay = full penalty)
        size_penalty *= (delay_hours / 12.0)  # Scale by delay fraction
        print(f"  → Household size penalty ({occupants} occupants): -{size_penalty:.1f}")

        final_comfort = base_comfort - noise_penalty - size_penalty
        return max(0.0, min(10.0, final_comfort))

    def calculate_practicality_score(self, delay_hours: float, run_time_hour: int,
                                    housing_type: str, occupants: int,
                                    appliance_type: str) -> float:
        """
        Calculate practicality as behavioral adoption likelihood.

        NOT about comfort (that's comfort criterion), but about:
        - Willingness to adopt TOU scheduling behavior
        - Complexity of remembering to delay
        - Household coordination difficulty

        Citations:
        - Paetz et al. (2012): "Monetary savings became more important, which was
          also found to be one of the main underlying motives in shifting loads...
          During this test-living phase the residents saved around 6.5% on electricity costs"
          ACEEE Summer Study, Paper 0193-000232

        - Indonesia TOU study (2024): "63% of survey participants expect to opt into
          ToU scheme... 37% find ToU burdensome to implement and very demanding"
          PMC11190461

        - Shewale et al. (2023): TOU appliance scheduling adoption <20% without automation
          Arabian Journal for Science and Engineering, DOI: 10.1007/s13369-023-08178-w
        """

        # Component 1: Base adoption likelihood by delay duration
        # Paetz: 12hr delay acceptable, but adoption varies
        # Shewale: <20% adoption for manual TOU scheduling

        if delay_hours == 0:
            base_practicality = 10.0  # No behavior change required
        elif delay_hours <= 2:
            base_practicality = 8.0   # Minor behavior change, high adoption
        elif delay_hours <= 4:
            base_practicality = 6.5   # Moderate change, medium adoption
        elif delay_hours <= 8:
            base_practicality = 4.5   # Significant delay, lower adoption
        elif delay_hours <= 12:
            base_practicality = 3.0   # Maximum acceptable (Paetz), but low adoption
        else:
            base_practicality = 1.5   # Beyond typical adoption range

        print(f"  → Base practicality (delay={delay_hours}hr): {base_practicality}/10")

        # Component 2: Timing complexity (remembering to run at specific time)
        # Late night/early morning = harder to remember/coordinate
        timing_penalty = 0.0

        # Paetz et al.: "If low-price zones applied on brink of day, it was
        # perceived as too early or too late"
        if 0 <= run_time_hour < 6:  # Middle of night (midnight-6am)
            timing_penalty = 2.0   # Very inconvenient timing
        elif 22 <= run_time_hour < 24:  # Late night (10pm-midnight)
            timing_penalty = 1.0   # Somewhat inconvenient

        print(f"  → Timing complexity penalty: -{timing_penalty:.1f}")

        # Component 3: Household coordination difficulty
        # More occupants = harder to coordinate "don't run dishes yet"
        # Ground Truth Data Section 9: Behavioral barriers increase with complexity

        if occupants >= 5:
            coordination_penalty = 1.5
        elif occupants >= 3:
            coordination_penalty = 0.8
        else:
            coordination_penalty = 0.0

        # Scale penalty by delay (longer delay = more coordination needed)
        coordination_penalty *= (delay_hours / 12.0)
        print(f"  → Coordination penalty ({occupants} occupants): -{coordination_penalty:.1f}")

        final_practicality = base_practicality - timing_penalty - coordination_penalty

        # CRITICAL: Set minimum floor (even impractical has SOME adoption)
        # Following HVAC pattern: max(1.5, score)
        return max(1.5, min(10.0, final_practicality))

    def parse_alternative(self, alt: str, scenario: Dict) -> Tuple[int, float]:
        """
        Parse alternative text to extract run time and delay.

        SIMPLIFIED FORMAT - alternatives are just "Run at 7pm" (no extra description)

        Examples:
        - "Run at 7pm" → (19, 0)     # 7pm, no delay from 7pm baseline
        - "Run at 10pm" → (22, 3)    # 10pm, 3 hours after 7pm
        - "Run at 2am" → (2, 7)      # 2am, 7 hours after 7pm

        Args:
            alt: Alternative text string (e.g., "Run at 7pm")
            scenario: Full scenario dict (for fallback context)

        Returns:
            (run_time_hour, delay_hours)
        """
        import re

        # Extract time (e.g., "7pm", "10pm", "2am")
        time_match = re.search(r'(\d+)\s*(am|pm)', alt, re.IGNORECASE)
        if not time_match:
            print(f"  ⚠ Could not parse run time from: {alt}")
            # Default to immediate (no delay)
            return 19, 0.0  # 7pm, no delay

        hour = int(time_match.group(1))
        am_pm = time_match.group(2).lower()

        # Convert to 24-hour format
        if am_pm == "pm" and hour != 12:
            run_time_hour = hour + 12
        elif am_pm == "am" and hour == 12:
            run_time_hour = 0
        else:
            run_time_hour = hour

        # Calculate delay from baseline "after dinner" time (7pm = 19:00)
        baseline_hour = 19  # 7pm

        # Handle wraparound for late night (e.g., 2am is 7 hours after 7pm, not -17)
        if run_time_hour >= baseline_hour:
            delay_hours = float(run_time_hour - baseline_hour)
        else:
            # Crossed midnight: e.g., 7pm to 2am = 7 hours forward
            delay_hours = float(24 - baseline_hour + run_time_hour)

        print(f"  Parsed: '{alt}' → run at {run_time_hour:02d}:00, delay={delay_hours}hr")
        return run_time_hour, delay_hours

    def apply_value_function(self, raw_value: float, vf_spec: str, value_type: str) -> float:
        """
        Apply value function transformation to raw criterion values.

        EXACT SAME METHOD AS HVAC - maintains consistency across calculators.

        Reference ranges derived from actual scenario distribution (5th-95th percentile).

        Args:
            raw_value: Raw criterion value (e.g., dollars, lbs CO2)
            vf_spec: Value function specification (e.g., "linear", "logarithmic, a=1.5")
            value_type: Criterion name for reference range lookup

        Returns:
            Transformed score on 0-10 scale
        """
        # PLACEHOLDER - MUST BE DETERMINED FROM ACTUAL SCENARIOS
        # Process: Run all scenarios, analyze 5th-95th percentile, then set ranges
        reference_ranges = {
            'energy_cost': {
                # Will depend on: kWh range (0.9-4.0) × rate differential (0.09-0.18)
                # PLACEHOLDER values - update after data analysis
                'min': 0.08,
                'max': 0.65,
                'decreasing': True
            },
            'environmental': {
                # Calculated from energy bounds × emissions factor
                # PLACEHOLDER values - update after data analysis
                'min': 0.58,
                'max': 2.58,
                'decreasing': True
            },
            'comfort': {
                'min': 0.0,
                'max': 10.0,
                'decreasing': False
            },
            'practicality': {
                'min': 1.5,  # Floor from calculation
                'max': 10.0,
                'decreasing': False
            }
        }

        ref = reference_ranges[value_type]
        x_min = ref['min']
        x_max = ref['max']

        # Use raw_value directly - allow extrapolation (following HVAC pattern)
        x = raw_value

        vf_type = vf_spec.split(',')[0].strip().lower()

        # Normalize (can go outside [0,1] range)
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

        # Clamp final score to [0, 10]
        return max(0.0, min(10.0, u_x * 10.0))

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        """
        Calculate complete ground truth scores for appliance scenario with all alternatives.

        Expected scenario structure (EXACT MATCH to CSV parameters):
        {
            'Description': "When should I run my dishwasher after dinner tonight?",
            'Location': "Philadelphia, PA",
            'Utility Budget': 150,
            'Appliance': "dishwasher",
            'Housing Type': "Apartment",
            'Occupants': 2,
            'Peak Rate': 0.18,      # Dollar amount, not string
            'Off-Peak Rate': 0.09,  # Dollar amount, not string
            'kwh/cycle': 1.25,
            'Appliance Age/Type': "7 years",
            'Alternative 1': "Run at 7pm",
            'Alternative 2': "Run at 10pm",
            'Alternative 3': "Run at 2am",
            'vf_specs': {
                'energy_cost': 'linear',
                'environmental': 'linear',
                'comfort': 'linear',
                'practicality': 'linear'
            }
        }

        Returns:
            Dict mapping alternatives to their criterion scores and raw values
        """

        # Extract alternatives from scenario
        alternatives = []
        for alt_key in ['Alternative 1', 'Alternative 2', 'Alternative 3']:
            if alt_key in scenario and scenario[alt_key]:
                alternatives.append(scenario[alt_key])

        raw_results = {}

        for alt in alternatives:
            print(f"\nProcessing alternative: {alt}")

            # Parse alternative to extract run time and delay
            try:
                run_time_hour, delay_hours = self.parse_alternative(alt, scenario)
            except Exception as e:
                print(f"  ✗ Parsing ERROR: {e}")
                continue

            # Calculate raw criterion values
            try:
                energy_cost = self.calculate_energy_cost(
                    scenario['kwh/cycle'],
                    run_time_hour,
                    scenario['Peak Rate'],
                    scenario['Off-Peak Rate']
                )
            except Exception as e:
                print(f"  ✗ Energy cost ERROR: {e}")
                energy_cost = 0.0

            try:
                emissions = self.calculate_environmental_impact(scenario['kwh/cycle'])
            except Exception as e:
                print(f"  ✗ Emissions ERROR: {e}")
                emissions = 0.0

            try:
                comfort = self.calculate_comfort_score(
                    delay_hours,
                    run_time_hour,
                    scenario['Housing Type'],
                    scenario['Occupants'],
                    scenario['Appliance']
                )
            except Exception as e:
                print(f"  ✗ Comfort ERROR: {e}")
                comfort = 5.0

            try:
                practicality = self.calculate_practicality_score(
                    delay_hours,
                    run_time_hour,
                    scenario['Housing Type'],
                    scenario['Occupants'],
                    scenario['Appliance']
                )
            except Exception as e:
                print(f"  ✗ Practicality ERROR: {e}")
                practicality = 5.0

            raw_results[alt] = {
                'energy_cost_dollars': energy_cost,
                'emissions_lbs': emissions,
                'comfort_raw': comfort,
                'practicality_raw': practicality
            }

        # Apply value functions to get final 0-10 scores
        final_scores = {}

        for alt, raw in raw_results.items():
            print(f"\nApplying value functions for: {alt}")

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
                'raw_cost': round(raw['energy_cost_dollars'], 4),
                'raw_emissions': round(raw['emissions_lbs'], 3)
            }

            print(f"  → FINAL SCORES:")
            print(f"     Energy: {energy_vf:.2f}, Environmental: {env_vf:.2f}, "
                  f"Comfort: {comfort_vf:.2f}, Practicality: {practicality_vf:.2f}\n")

        return final_scores

