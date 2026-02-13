import pandas as pd
import math
from typing import Dict, List, Tuple
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
    # EPA eGRID2022: Pennsylvania grid emissions 0.85 lb CO2/kWh
    # Citations: EPA eGRID2022 [Ref 77,81], PA DEP 2021 [Ref 29,32]
    EMISSIONS_FACTOR_PA = 0.85  # lbs CO2/kWh

    # ADD AFTER (new constant):
    # EIA 2024-2025: Pennsylvania residential average
    # Citations: EIA state data [Ref 29], PA suppliers [Ref 28]
    ELECTRICITY_RATE_PA = 0.19  # $/kWh (informational, scenarios provide own rates)

    # Fixed Peak Hours (2pm-6pm) - no seasonal variation
    # Based on PECO Energy standard TOU schedule
    PEAK_HOURS = (14, 18)  # 2 PM - 6 PM

    # Dishwasher: Modern 38-50 dBA, typical 44-48 dBA [Ref 35,36]
    # Washer: 50-70 dBA average wash+spin [Ref 37,38]
    # Dryer: 50-65 dBA during operation [Ref 39]
    # Citations: Manufacturer specs [Ref 35,36], acoustic studies [Ref 40,38]
    APPLIANCE_NOISE_LEVELS = {
        'dishwasher': 45,
        'washer': 50,
        'dryer': 55
    }

    # Apartment Noise Standards
    # All County Apartments: "Anything louder than 45 dB during daytime or 35 dB
    # in evening is deemed too loud"
    # Decibel Pro: "Time limits usually apply after 10 pm and until 7 am"
    NOISE_LIMIT_DAYTIME = 45     # dBA acceptable during day
    NOISE_LIMIT_EVENING = 35     # dBA acceptable after 10pm
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
            appliance_noise = 50

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

        Now uses scenario-provided baseline time instead of hardcoded defaults.
        This allows user flexibility and makes the baseline visible to AI.

        Args:
            alt: Alternative text string (e.g., "Run at 7pm")
            scenario: Full scenario dict (must contain 'Baseline Time' key)

        Returns:
            (run_time_hour, delay_hours)
        """
        import re

        # Extract run time from alternative (e.g., "7pm", "10pm", "2am")
        time_match = re.search(r'(\d+)\s*(am|pm)', alt, re.IGNORECASE)
        if not time_match:
            print(f"  ⚠ Could not parse run time from: {alt}")
            # Return baseline with no delay
            baseline_hour = self._parse_time_to_hour(scenario.get('Baseline Time', '7pm'))
            return baseline_hour, 0.0

        hour = int(time_match.group(1))
        am_pm = time_match.group(2).lower()

        # Convert to 24-hour format
        if am_pm == "pm" and hour != 12:
            run_time_hour = hour + 12
        elif am_pm == "am" and hour == 12:
            run_time_hour = 0
        else:
            run_time_hour = hour

        # Parse baseline time from scenario
        baseline_str = scenario.get('Baseline Time', '7pm')
        baseline_hour = self._parse_time_to_hour(baseline_str)

        # Calculate delay from baseline
        if run_time_hour >= baseline_hour:
            delay_hours = float(run_time_hour - baseline_hour)
        else:
            # Crossed midnight
            delay_hours = float(24 - baseline_hour + run_time_hour)

        print(f"  Parsed: '{alt}' → run at {run_time_hour:02d}:00, "
              f"delay={delay_hours}hr from baseline {baseline_str}")

        return run_time_hour, delay_hours
#AHAAN CHECK LOGIC FOR TS
    def _parse_time_to_hour(self, time_str: str) -> int:
        """
        Helper function to convert time string to 24-hour format.

        Examples:
        - "7pm" → 19
        - "8am" → 8
        - "12pm" → 12
        - "12am" → 0

        Args:
            time_str: Time string (e.g., "7pm", "8am")

        Returns:
            Hour in 24-hour format (0-23)
        """
        import re

        match = re.search(r'(\d+)\s*(am|pm)', time_str, re.IGNORECASE)
        if not match:
            # Default to 7pm if unparseable
            print(f"  ⚠ Could not parse baseline time '{time_str}', defaulting to 7pm")
            return 19

        hour = int(match.group(1))
        am_pm = match.group(2).lower()

        if am_pm == "pm" and hour != 12:
            return hour + 12
        elif am_pm == "am" and hour == 12:
            return 0
        else:
            return hour

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
        reference_ranges = {
            'energy_cost': {
                # Q16: Appliance energy cost per cycle in PA
                # Min: Front-load HE washer off-peak
                #      0.1 kWh × $0.09/kWh = $0.009 (use 0.02 for 5th percentile)
                # Max: Electric resistance dryer peak
                #      4.5 kWh × $0.20/kWh = $0.90
                # Citations: Q16, Q8-Q10 [Ref 29,28,33,34]
                'min': 0.02,
                'max': 0.90,
                'decreasing': True
            },
            'environmental': {
                # Derived from energy bounds × emissions factor
                # Min: 0.1 kWh × 0.85 = 0.085 lbs CO2 (round to 0.09)
                # Max: 4.5 kWh × 0.85 = 3.83 lbs CO2
                # Citations: EPA eGRID2022 [Ref 77,29], Q8-Q10 [Ref 33,34]
                'min': 0.09,
                'max': 3.83,
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

    def calculate_budget_penalty(self, monthly_cost: float, monthly_budget: float) -> float:
        """
        1. 80% Threshold (Comfortable Headroom):
           - Thaler (1999): "Mental accounting creates hedonic framing of expenses
             against budget envelopes; consumers maintain safety margins"
             Mental Accounting Matters, J. Behavioral Decision Making 12:183-206

           - Financial planning literature: 80% rule-of-thumb for sustainable spending
             vs income/budget (20% safety margin)
             Statman (2017), Finance for Normal People, Oxford University Press

        2. 100% Threshold (Budget Limit):
           - Prelec & Loewenstein (1998): "Pain of paying" increases sharply at
             budget violation point; consumers exhibit loss aversion
             The Red and the Black, Marketing Science 17(1):4-28

           - Heath & Soll (1996): Mental budget violations trigger self-control costs
             and justify abandonment of consumption goals
             Mental Budgeting and Consumer Decisions, J. Consumer Research 23(1):40-52

        3. 100-150% Range (Exponential Decline):
           - Kahneman & Tversky (1979): Prospect theory - losses loom larger than gains;
             value function is steeper for losses (λ ≈ 2-2.5)
             Prospect Theory, Econometrica 47(2):263-291

           - Budget overruns treated as losses; penalty accelerates nonlinearly
           - Exponential decay models increasing psychological cost of deficit

        4. 150% Cutoff (Infeasibility):
           - Simon (1955): Bounded rationality - options exceeding feasibility
             constraints are eliminated from consideration set
             A Behavioral Model of Rational Choice, Quarterly J. Economics 69(1):99-118

           - Financial stress research: 150% debt-to-income triggers default risk,
             alternatives become "unaffordable" not just "expensive"
             Gathergood (2012), Self-control, financial literacy and consumer
             over-indebtedness, J. Economic Psychology 33(3):590-602

        VALIDATION:
        - Consistent with mental accounting theory (Thaler)
        - Matches prospect theory loss aversion (Kahneman & Tversky)
        - Reflects bounded rationality screening (Simon)
        - Aligns with financial stress cutoffs (consumer finance research)

        Args:
            monthly_cost: Estimated monthly energy cost for this alternative ($)
            monthly_budget: User's stated monthly utility budget ($)

        Returns:
            Penalty multiplier ∈ [0.0, 1.0] to apply to energy cost score

        Examples:
            Budget = $175/month
            - $140 cost (80%):  penalty = 1.0   (no reduction)
            - $158 cost (90%):  penalty = 0.75  (mild reduction)
            - $175 cost (100%): penalty = 0.5   (moderate reduction)
            - $193 cost (110%): penalty = 0.37  (significant reduction)
            - $219 cost (125%): penalty = 0.14  (severe reduction)
            - $263 cost (150%): penalty = 0.01  (near elimination)
            - $267 cost (153%): penalty = 0.0   (complete elimination)
        """

        utilization = monthly_cost / monthly_budget

        if utilization < 0.80:
            # Below 80%: Comfortable headroom, no penalty
            # Thaler (1999): Mental budget safety margin
            return 1.0

        elif utilization < 1.0:
            # 80-100%: Linear decline (approaching budget limit)
            # Heath & Soll (1996): Increasing cost-consciousness near boundary
            # Formula: penalty = 1.0 at 80%, penalty = 0.5 at 100%
            # Slope: Δpenalty/Δutil = -0.5/0.2 = -2.5
            return 1.0 - 2.5 * (utilization - 0.80)

        elif utilization < 1.5:
            # 100-150%: Exponential decline (budget violation)
            # Kahneman & Tversky (1979): Loss aversion, steeper value function
            # Prelec & Loewenstein (1998): "Pain of paying" accelerates with deficit
            # Formula: penalty = 0.5 at 100%, penalty ≈ 0.01 at 150%
            # exp(-3×(1.5-1.0)) ≈ 0.011, so 0.5 × 0.011 ≈ 0.006
            import math
            return 0.5 * math.exp(-3.0 * (utilization - 1.0))

        else:
            # >150%: Complete elimination (infeasibility threshold)
            # Simon (1955): Bounded rationality - infeasible options eliminated
            # Gathergood (2012): 150% debt threshold for consumer stress
            return 0.0

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

            if 'Utility Budget' in scenario and scenario['Utility Budget'] > 0:
                # Convert per-cycle cost to monthly estimate (assume 30 cycles/month)
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost_dollars'],
                    cycles_per_month=30
                )

                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    scenario['Utility Budget']
                )

                # Apply penalty to energy cost score
                energy_vf_penalized = energy_vf * budget_penalty

                print(f"  Budget check: ${monthly_cost:.2f}/month vs ${scenario['Utility Budget']:.2f} budget")
                print(
                    f"  Utilization: {monthly_cost / scenario['Utility Budget'] * 100:.1f}% → penalty: {budget_penalty:.3f}")
                print(f"  Energy score: {energy_vf:.2f} → {energy_vf_penalized:.2f} (after penalty)")

                energy_vf = energy_vf_penalized

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


def process_appliance_scenarios(csv_filename: str = "ApplianceScenarios.csv",
                                output_filename: str = "ground_truth_appliance.csv"):
    """
    Read Appliance scenarios from CSV and calculate ground truth scores for all alternatives.

    Args:
        csv_filename: Path to CSV file with scenarios
        output_filename: Where to save ground truth results

    Expected CSV columns:
        Description, Location, Utility Budget, Appliance, Housing Type,
        Occupants, Peak Rate, Off-Peak Rate, kwh/cycle, Appliance Age/Type,
        Alternative 1, Alternative 2, Alternative 3
    """

    df = pd.read_csv(csv_filename)

    print(f"Found {len(df)} appliance scenarios")

    calculator = ApplianceGroundTruthCalculator()

    results = []

    for idx, row in df.iterrows():
        print(f"\nProcessing scenario {idx + 1}/{len(df)}: {row['Appliance']} in {row['Location']}")

        # Collect alternatives
        alternatives = []
        for alt_col in ['Alternative 1', 'Alternative 2', 'Alternative 3']:
            alt_val = str(row[alt_col]).strip()

            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        scenario = {
            'Description': row['Description'],
            'Location': row['Location'],
            'Utility Budget': float(row['Utility Budget']),
            'Appliance': row['Appliance'],
            'Housing Type': row['Housing Type'],
            'Occupants': int(row['Occupants']),
            'Peak Rate': float(row['Peak Rate']),
            'Off-Peak Rate': float(row['Off-Peak Rate']),
            'kwh/cycle': float(row['kwh/cycle']),
            'Appliance Age/Type': row['Appliance Age/Type'],
            'Baseline Time': row['Baseline Time'],  # ADD THIS LINE
            'Alternative 1': row['Alternative 1'],
            'Alternative 2': row['Alternative 2'],
            'Alternative 3': row['Alternative 3'],
            'vf_specs': {
                'energy_cost': ApplianceGroundTruthCalculator.VF_ENERGY_COST,
                'environmental': ApplianceGroundTruthCalculator.VF_ENVIRONMENTAL,
                'comfort': ApplianceGroundTruthCalculator.VF_COMFORT,
                'practicality': ApplianceGroundTruthCalculator.VF_PRACTICALITY
            }
        }

        try:
            scores = calculator.calculate_scenario_scores(scenario)

            for alt, alt_scores in scores.items():
                result_row = {
                    'scenario_id': idx,
                    'description': row['Description'],
                    'location': row['Location'],
                    'appliance': row['Appliance'],
                    'housing_type': row['Housing Type'],
                    'occupants': row['Occupants'],
                    'peak_rate': row['Peak Rate'],
                    'offpeak_rate': row['Off-Peak Rate'],
                    'kwh_per_cycle': row['kwh/cycle'],
                    'alternative': alt,
                    'energy_cost_score': alt_scores['energy_cost_score'],
                    'environmental_score': alt_scores['environmental_score'],
                    'comfort_score': alt_scores['comfort_score'],
                    'practicality_score': alt_scores['practicality_score'],
                    'raw_cost': alt_scores['raw_cost'],
                    'raw_emissions': alt_scores['raw_emissions']
                }
                results.append(result_row)

        except Exception as e:
            print(f"ERROR processing scenario {idx}: {e}")
            import traceback
            traceback.print_exc()
            continue

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_filename, index=False)

    print(f"\nGround truth saved to {output_filename}")
    print(f"Total alternatives scored: {len(results_df)}")
    return results_df


if __name__ == "__main__":
    process_appliance_scenarios(
        csv_filename="ApplianceScenarios.csv",
        output_filename="ground_truth_appliance.csv"
    )