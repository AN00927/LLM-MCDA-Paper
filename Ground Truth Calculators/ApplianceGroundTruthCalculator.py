import pandas as pd
import math
import logging
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

class ApplianceGroundTruthCalculator:
    # his average factor is defined for reference only. Actual emissions
    # calculations use EMISSIONS_FACTOR_PEAK / EMISSIONS_FACTOR_OFFPEAK below
    # because time-of-use differentiation is integral to appliance scheduling.
    EMISSIONS_FACTOR_PA = 0.6458  # lbs CO2/kWh (2024 update); NOT used in calculations

    # Peak window 2 PM–6 PM from PECO Energy TOU documentation (PECO, 2021).
    PEAK_HOURS = (14, 18)
    # Time-varying marginal emissions factors by TOU period.
    # PJM-region defaults inspired by EPA AVERT / NREL Cambium framework.
    # Replace with hourly PJM marginal factors when available.
    EMISSIONS_FACTOR_PEAK = 0.7427      # lbs CO2/kWh (approx. marginal peak-period)
    EMISSIONS_FACTOR_OFFPEAK = 0.5489   # lbs CO2/kWh (approx. marginal off-peak period)
    NOISE_LIMIT_EVENING = 45     # dBA threshold after 10pm (EPA/WHO indoor night limit is 35 dBA;
                                  # 45 dBA chosen so dishwashers (~45 dBA) are at-threshold and
                                  # washers/dryers (50-55 dBA) exceed it and receive the noise penalty)
    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Management Science 26(8):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact - physical units have linear marginal value
    # Note: This represents a MODELING ASSUMPTION rather than an empirically validated preference.
    # For MAVT framework justification, see:
    # - Keeney, R. L., & Raiffa, H. (1976). Decisions with Multiple Objectives: Preferences 
    #   and Value Trade-offs. Wiley. (Foundation for Multi-Attribute Value Theory axioms)
    # Linear VF justification in this context: When environmental impacts are framed in 
    # absolute physical units (lbs CO₂), a linear preference is a conservative modeling choice
    # that treats equal changes in emissions as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"
    def _max_acceptable_delay(self, appliance_type: str) -> float:
        """ max acceptable delay."""
        delays = {
            'dishwasher': 12.0,
            'washer': 8.0,
            'washing_machine': 8.0,
            'dryer': 6.0,
        }
        return delays.get(appliance_type.lower().strip(), 12.0)

    def determine_rate_period(self, run_time_hour: int) -> str:
        """Determine rate period."""
        peak_start, peak_end = self.PEAK_HOURS

        if peak_start <= run_time_hour < peak_end:
            return "peak"

        return "offpeak"

    def calculate_energy_cost(self, kwh_cycle: float, run_time_hour: int,
                             peak_rate: float, offpeak_rate: float) -> float:
        """Calculate energy cost."""
        period = self.determine_rate_period(run_time_hour)

        if period == "peak":
            rate = peak_rate
        else:
            rate = offpeak_rate

        cost = kwh_cycle * rate
        print(f" Energy cost: {kwh_cycle} kWh × ${rate:.4f}/kWh ({period}) = ${cost:.4f}")
        return cost

    def calculate_environmental_impact(self, kwh_cycle: float, run_time_hour: int) -> float:
        """Calculate environmental impact."""
        period = self.determine_rate_period(run_time_hour)
        if period == "peak":
            emissions_factor = self.EMISSIONS_FACTOR_PEAK
        else:
            emissions_factor = self.EMISSIONS_FACTOR_OFFPEAK

        emissions = kwh_cycle * emissions_factor
        print(f"  : Emissions: {kwh_cycle} kWh × {emissions_factor:.4f} lbs/kWh ({period} marginal) = "
              f"{emissions:.3f} lbs CO2")
        return emissions

    def calculate_comfort_score(self, delay_hours: float, run_time_hour: int,
                               housing_type: str, occupants: int,
                               appliance_type: str) -> float:
        """Calculate comfort score."""
        if delay_hours == 0:
            base_comfort = 10.0
        elif delay_hours <= 3:
            base_comfort = 10.0 - (delay_hours / 3.0) * 2.0         # 10→8 over 3hr
        elif delay_hours <= 7:
            base_comfort = 8.0 - ((delay_hours - 3.0) / 4.0) * 2.0  # 8→6 over 4hr
        elif delay_hours <= 12:
            base_comfort = 6.0 - ((delay_hours - 7.0) / 5.0) * 2.0  # 6→4 over 5hr
        else:
            base_comfort = 2.0   # Beyond acceptable (>12hr)

        print(f"  : Base comfort (delay={delay_hours:.1f}hr): {base_comfort:.2f}/10")

        # Component 2: Noise disruption penalty
        # Depends on: time of day + housing type + appliance noise level
        if appliance_type.lower() == "dishwasher":
            appliance_noise = 45
        elif appliance_type.lower() == "washer" or "washing" in appliance_type.lower():
            appliance_noise = 50
        elif appliance_type.lower() == "dryer":
            appliance_noise = 55
        else:
            appliance_noise = 50

        noise_penalty = 0.0
        # Late night running (10pm–7am)
        if 22 <= run_time_hour or run_time_hour < 7:
            if appliance_noise > self.NOISE_LIMIT_EVENING:
                noise_penalty = 2.0  # Base penalty for late-night noise above threshold

                # Housing type multiplier — shared walls increase noise impact
                if housing_type in ("Apartment", "Condo"):
                    noise_penalty *= 1.5   # Neighbors immediately adjacent
                elif housing_type in ("Townhouse", "Rowhouse"):
                    noise_penalty *= 1.2   # Shared walls, some buffering
                else:  # Single-family
                    noise_penalty *= 0.8   # Isolated structure, lower concern

                print(f"  : Noise penalty (late night, {housing_type}): -{noise_penalty:.1f}")

        # Component 3: Household size impact — larger households feel delay more acutely
        # (dishes/laundry pile up faster; scale penalty by appliance-specific max delay)
        max_delay = self._max_acceptable_delay(appliance_type)
        if occupants >= 5:
            size_penalty = 1.5
        elif occupants >= 3:
            size_penalty = 0.8
        else:
            size_penalty = 0.0

        size_penalty *= min(delay_hours / max_delay, 1.0)  # Cap scaling at 1.0
        print(f"  : Household size penalty ({occupants} occupants, max_delay={max_delay:.0f}hr): -{size_penalty:.2f}")

        final_comfort = base_comfort - noise_penalty - size_penalty
        return max(0.0, min(10.0, final_comfort))

    def calculate_practicality_score(self, delay_hours: float, run_time_hour: int,
                                    housing_type: str, occupants: int,
                                    appliance_type: str) -> float:
        """Calculate practicality score."""
        if delay_hours == 0:
            base_practicality = 10.0
        elif delay_hours <= 2:
            base_practicality = 10.0 - (delay_hours / 2.0) * 2.0          # 10→8 over 2hr
        elif delay_hours <= 4:
            base_practicality = 8.0 - ((delay_hours - 2.0) / 2.0) * 1.5   # 8→6.5 over 2hr
        elif delay_hours <= 8:
            base_practicality = 6.5 - ((delay_hours - 4.0) / 4.0) * 2.0   # 6.5→4.5 over 4hr
        elif delay_hours <= 12:
            base_practicality = 4.5 - ((delay_hours - 8.0) / 4.0) * 1.5   # 4.5→3.0 over 4hr
        else:
            base_practicality = 1.5   # Beyond typical adoption range

        print(f"  : Base practicality (delay={delay_hours:.1f}hr): {base_practicality:.2f}/10")

        # Component 2: Timing complexity (remembering to run at specific hour)
        # Paetz et al.: "If low-price zones applied on brink of day, perceived as too early or too late"
        timing_penalty = 0.0
        if 0 <= run_time_hour < 6:    # Middle of night (midnight–6am)
            timing_penalty = 2.0
        elif 22 <= run_time_hour < 24: # Late night (10pm–midnight)
            timing_penalty = 1.0

        print(f"  : Timing complexity penalty: -{timing_penalty:.1f}")

        # Component 3: Household coordination difficulty
        # Appliance-specific max delay used for proportional scaling
        max_delay = self._max_acceptable_delay(appliance_type)
        if occupants >= 5:
            coordination_penalty = 1.5
        elif occupants >= 3:
            coordination_penalty = 0.8
        else:
            coordination_penalty = 0.0

        coordination_penalty *= min(delay_hours / max_delay, 1.0)
        print(f"  : Coordination penalty ({occupants} occupants, max_delay={max_delay:.0f}hr): -{coordination_penalty:.2f}")

        final_practicality = base_practicality - timing_penalty - coordination_penalty

        # Daytime floor: running appliances during business hours carries a minimum practicality
        # of 4 (always a socially acceptable option). Only applies when delay is within the
        # appliance-specific acceptable window — prevents large-delay wrap-bug rescues.
        DAYTIME_START = 7
        DAYTIME_END = 22
        if DAYTIME_START <= run_time_hour < DAYTIME_END and delay_hours <= max_delay:
            final_practicality = max(final_practicality, 4)

        return max(1.5, min(10.0, final_practicality))


    def parse_alternative(self, alt: str, scenario: Dict) -> Tuple[int, float]:
        """Parse alternative."""
        import re

        # Extract run time from alternative (e.g., "7pm", "10pm", "2am")
        time_match = re.search(r'(\d{1,2})(?::\d{2})?\s*(am|pm)', alt, re.IGNORECASE)
        if not time_match:
            print(f"  : Could not parse run time from: {alt}")
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

        # Calculate delay from baseline as circular clock distance.
        # This treats near wrap-around differences as short delays (e.g., 2 hours),
        # rather than inflated 22-23 hour delays.
        delay_forward = float((run_time_hour - baseline_hour) % 24)
        delay_backward = float((baseline_hour - run_time_hour) % 24)
        delay_hours = min(delay_forward, delay_backward)

        print(f"  Parsed: '{alt}' -> run at {run_time_hour:02d}:00, "
              f"delay={delay_hours:.1f}hr from baseline {baseline_str} "
              f"(fwd={delay_forward:.0f}hr, bwd={delay_backward:.0f}hr)")

        return run_time_hour, delay_hours
    def _parse_time_to_hour(self, time_str: str) -> int:
        """ parse time to hour."""
        import re

        match =re.search(r'(\d{1,2})(?::\d{2})?\s*(am|pm)', time_str, re.IGNORECASE)
        if not match:
            # Default to 7pm if unparseable
            print(f"  : Could not parse baseline time '{time_str}', defaulting to 7pm")
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
        """Apply value function."""
        reference_ranges = {
            'energy_cost': {
                # Reference range derived from representative appliance usage:
                # Min: Efficient HE washer off-peak≈0.1 kWh × $0.09/kWh ≈ $0.01 (rounded to $0.02 for 5th percentile)
                # Max: Standard electric resistance dryer at peak≈4.5 kWh × $0.20/kWh ≈ $0.90
                # Sources: Winfield et al. (2016); NEEP (2015); Porras et al. (2020); Chen-Yu & Emmel (2018); EIA (2022) for PA electricity price.

                'min': 0.02,
                'max': 0.90,
                'decreasing': True
            },
            'environmental': {
                # Derived from energy bounds × peak marginal emissions factor.
                # Min: 0.1 kWh (HE washer off-peak) × 0.5489 lbs/kWh ≈ 0.055 → 0.09 (5th pctile)
                # Max: 4.5 kWh (resistance dryer at peak) × 0.7427 lbs/kWh ≈ 3.34 lbs CO2
                # Previous value of 3.83 was computed with an older emissions factor (~0.85 lbs/kWh);
                # updated to reflect current EMISSIONS_FACTOR_PEAK = 0.7427 (EPA eGRID2024).
                # Source: EPA eGRID2024 Detailed Data.

                'min': 0.09,
                'max': 3.34,
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

        # Use raw_value directly and allow extrapolation.
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
                    u_x = 0.0  # absolutely horrible score
                else:
                    u_x = math.log(a * x_normalized + 1) / math.log(a + 1)

        else:
            u_x = x_normalized

        # Clamp final score to [0, 10]
        return max(0.0, min(10.0, u_x * 10.0))

    def calculate_budget_penalty(self, monthly_cost: float, monthly_budget: float) -> float:
        """Calculate budget penalty."""
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

    def calculate_monthly_cost(self, per_cycle_cost: float, cycles_per_month: int = 30) -> float:
        """Calculate monthly cost."""
        return per_cycle_cost * cycles_per_month

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        """Calculate scenario scores."""
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
                emissions = self.calculate_environmental_impact(
                    scenario['kwh/cycle'],
                    run_time_hour
                )
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

            energy_vf = self.apply_value_function(
                raw['energy_cost_dollars'],
                self.VF_ENERGY_COST,
                'energy_cost'
            )
            print(f"  After VF linear: Energy = {energy_vf:.2f}/10")

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
                    f"  Utilization: {monthly_cost / scenario['Utility Budget'] * 100:.1f}% : penalty: {budget_penalty:.3f}")
                print(f"  Energy score: {energy_vf:.2f} : {energy_vf_penalized:.2f} (after penalty)")

                energy_vf = energy_vf_penalized

            env_vf = self.apply_value_function(
                raw['emissions_lbs'],
                self.VF_ENVIRONMENTAL,
                'environmental'
            )
            print(f"  After VF Linear: Environmental = {env_vf:.2f}/10")

            comfort_vf = self.apply_value_function(
                raw['comfort_raw'],
                self.VF_COMFORT,
                'comfort'
            )
            print(f"  After VF logarithmic (a=1.5): Comfort = {comfort_vf:.2f}/10")

            practicality_vf = self.apply_value_function(
                raw['practicality_raw'],
                self.VF_PRACTICALITY,
                'practicality'
            )
            print(f"  After VF logarithmic (a=1.2): Practicality = {practicality_vf:.2f}/10")

            final_scores[alt] = {
                'energy_cost_score': round(energy_vf, 2),
                'environmental_score': round(env_vf, 2),
                'comfort_score': round(comfort_vf, 2),
                'practicality_score': round(practicality_vf, 2),
                'raw_cost': round(raw['energy_cost_dollars'], 4),
                'raw_emissions': round(raw['emissions_lbs'], 3)
            }

            print(f"  : FINAL SCORES:")
            print(f"     Energy: {energy_vf:.2f}, Environmental: {env_vf:.2f}, "
                  f"Comfort: {comfort_vf:.2f}, Practicality: {practicality_vf:.2f}\n")

        return final_scores


def process_appliance_scenarios(
    csv_filename: str = str(SCENARIO_DIR / "ApplianceScenarios.csv"),
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_appliance.csv")):
    """Process appliance scenarios."""
    csv_path = Path(csv_filename)
    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

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
            'Baseline Time': row['Baseline Time'],
            'Alternative 1': row['Alternative 1'],
            'Alternative 2': row['Alternative 2'],
            'Alternative 3': row['Alternative 3'],
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
                    'description': row['Description'],
                    'location': row['Location'],
                    'utility_budget': row['Utility Budget'],
                    'appliance': row['Appliance'],
                    'appliance_age_type': row['Appliance Age/Type'],
                    'housing_type': row['Housing Type'],
                    'occupants': row['Occupants'],
                    'kwh_per_cycle': row['kwh/cycle'],
                    'peak_rate': row['Peak Rate'],
                    'offpeak_rate': row['Off-Peak Rate'],
                    'alternative': alt,
                    'energy_cost_score': alt_scores['energy_cost_score'],
                    'environmental_score': alt_scores['environmental_score'],
                    'comfort_score': alt_scores['comfort_score'],
                    'practicality_score': alt_scores['practicality_score'],
                    'mavt_score': ranking_result["weighted_scores"][list(scores.keys()).index(alt)],
                    'rank': ranking_result["ranks"][list(scores.keys()).index(alt)],
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
    results_df.to_csv(output_path, index=False)

    print(f"\nGround truth saved to {output_path}")
    print(f"Total alternatives scored: {len(results_df)}")
    return results_df

CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15
}
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
    process_appliance_scenarios()
