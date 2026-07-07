import sys
import pandas as pd
import math
import logging
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from sentinel_utils import apply_mavt_ranking, read_table_clean, SENTINEL_VALUE, has_sentinel_scores

class ApplianceGroundTruthCalculator:
    # PJM marginal emissions factors (lbs CO2/kWh). Source: PJM 2022 CO2/SO2/NOx
    # Emissions Report (April 2023). Marginal rates reflect emissions of the last
    # generator dispatched
    # Peak window: 7am-11pm. Weekday/holiday distinction not modeled.
    EMISSIONS_FACTOR_PEAK = 1.041      # lbs CO2/kWh; PJM peak (1041 lbs/MWh)
    EMISSIONS_FACTOR_OFFPEAK = 0.976   # lbs CO2/kWh; PJM off-peak (976 lbs/MWh)
    EMISSIONS_PEAK_HOURS = (7, 23)     # 7am-11pm system-wide PJM

    # Utility-to-city mapping with TOU rate windows and rates ($/kWh); per-utility sources
    # cited inline below. MODELING SCOPE: scenarios carry no day-of-week or date, so ALL
    # days are treated as weekdays and the single (summer) weekday peak window applies to
    # every scenario -- weekend off-peak pricing and seasonal summer/winter peak-window
    # shifts are NOT modeled (see methodology placeholder note).
    # FirstEnergy (WestPenn/Penelec/MetEd) TOU rate = PTC x multiplier; values below use
    # Jun-2025 PTCs (FirstEnergy Corp. (2025)) x fixed multipliers (FirstEnergy Corp. (2026))
    # and must be recomputed at each PTC reset (Jun 1 / Dec 1).
    UTILITY_RATES = {
        "PECO":      {"peak_hours": (14, 18), "peak_rate": 0.320,  "offpeak_rate": 0.076},   # Rate R-TOU, 2-6pm wkdy (PECO Energy Company (2026))
        # PPL Rate RTS: summer peak 2-6pm modeled; winter peak 4-8pm NOT modeled (no
        # season/date field) -- summer window used year-round (PPL Electric Utilities (2025)).
        "PPL":       {"peak_hours": (14, 18), "peak_rate": 0.160,  "offpeak_rate": 0.070},
        "WestPenn":  {"peak_hours": (14, 21), "peak_rate": 0.172,  "offpeak_rate": 0.088},   # PTC 0.10317 x 1.6649/0.8542
        "Penelec":   {"peak_hours": (14, 21), "peak_rate": 0.185,  "offpeak_rate": 0.093},   # PTC 0.11003 x 1.6792/0.8482
        "MetEd":     {"peak_hours": (14, 21), "peak_rate": 0.203,  "offpeak_rate": 0.100},   # PTC 0.11903 x 1.7060/0.8397
        # Duquesne Rate RS flat default (Duquesne Light Company (2026)); optional non-default
        # TOU (peak 3-9pm, PUC-approved 2025-04-10, Duquesne Light Company TOU (2026)) exists but is not used.
        "Duquesne":  {"peak_hours": (14, 21), "peak_rate": 0.1375, "offpeak_rate": 0.1375},
    }

    # City-to-utility mapping (PA only; city name as it appears in scenario Location field).
    # Coverage verified against PA PUC service-territory maps and FirstEnergy/PPL/PECO
    # public service-area documentation. Cities not in outline-provided mapping
    # (Harrisburg, Williamsport, McKeesport, Chester, Easton, Johnstown) researched
    # against utility service-territory pages and PA PUC sources.
    CITY_TO_UTILITY = {
        "Philadelphia": "PECO", "Norristown": "PECO", "Pottstown": "PECO",
        "Phoenixville": "PECO", "West Chester": "PECO", "Exton": "PECO",
        "King of Prussia": "PECO", "Blue Bell": "PECO", "Lower Merion": "PECO",
        "Media": "PECO", "Coatesville": "PECO", "Newtown": "PECO",
        "Doylestown": "PECO", "Chester": "PECO", "Levittown": "PECO",
        "Allentown": "PPL", "Bethlehem": "PPL", "Hazleton": "PPL",
        "Reading": "PPL", "Scranton": "PPL", "Wilkes-Barre": "PPL",
        "Stroudsburg": "PPL", "Lebanon": "PPL", "Lancaster": "PPL",
        "State College": "PPL", "Harrisburg": "PPL", "Williamsport": "PPL",
        "Quakertown": "PPL",
        "Greensburg": "WestPenn", "Monroeville": "WestPenn",
        "Indiana": "WestPenn", "Uniontown": "WestPenn", "Butler": "WestPenn",
        "DuBois": "Penelec", "Oil City": "Penelec", "Meadville": "Penelec",
        "Erie": "Penelec", "Altoona": "Penelec", "Johnstown": "Penelec",
        "York": "MetEd", "Chambersburg": "MetEd", "Gettysburg": "MetEd",
        "Carlisle": "MetEd", "Easton": "MetEd",
        "Pittsburgh": "Duquesne", "McKeesport": "Duquesne",
    }

    NOISE_LIMIT_EVENING = 45     # dBA threshold after 10pm (EPA/WHO indoor night limit is 35 dBA;
                                  # 45 dBA chosen so dishwashers (~45 dBA, Bellingham Electric (2026))
                                  # are at-threshold and washers/dryers (74/65 dBA,
                                  # Precision Appliance Leasing (2024) / Coolblue (2026))
                                  # exceed it and receive the noise penalty)
    # Dyer & Sarin (1979) (Oper. Res. 27(4):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact - physical units have linear marginal value.
    # For MAVT framework justification, see Keeney & Raiffa (1976): Foundation for
    # Multi-Attribute Value Theory axioms.
    # Linear VF justification in this context: When environmental impacts are framed in
    # absolute physical units (lbs CO2), a linear preference is a conservative modeling choice
    # that treats equal changes in emissions as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"
    def _max_acceptable_delay(self, appliance_type: str) -> float:
        delays = {
            'dishwasher': 12.0,
            'washer': 8.0,
            'washing_machine': 8.0,
            'dryer': 6.0,
        }
        return delays.get(appliance_type.lower().strip(), 12.0)

    def _cycles_per_month(self, appliance_type: str) -> int:
        cycles = {
            'dishwasher': 18,         # 215 cycles/yr (U.S. EPA (2023) ENERGY STAR Dishwashers criteria)
            'washer': 25,             # ~300 loads/yr (U.S. EPA (2026) ENERGY STAR Clothes Washers)
            'washing_machine': 25,
            'dryer': 24,              # 283 cycles/yr (U.S. DOE (2011) dryer test procedure)
        }
        return cycles.get(appliance_type.lower().strip(), 24)

    def _normalize_city(self, location: str) -> str:
        """Strip ', PA' / state suffix and whitespace from a Location string."""
        return location.split(",")[0].strip()

    def _utility_for_location(self, location: str) -> str:
        city = self._normalize_city(location)
        if city not in self.CITY_TO_UTILITY:
            raise ValueError(f"Unmapped city for utility lookup: {city!r}")
        return self.CITY_TO_UTILITY[city]

    def determine_rate_period(self, run_time_hour: int, location: str = None) -> str:
        """Determine rate period using the utility's TOU window for `location`."""
        if location is None:
            peak_start, peak_end = (14, 18)
        else:
            utility = self._utility_for_location(location)
            peak_start, peak_end = self.UTILITY_RATES[utility]["peak_hours"]

        if peak_start <= run_time_hour < peak_end:
            return "peak"
        return "offpeak"

    def determine_emissions_period(self, run_time_hour: int) -> str:
        """Determine PJM marginal-emissions period (system-wide 7am-11pm peak)."""
        peak_start, peak_end = self.EMISSIONS_PEAK_HOURS
        if peak_start <= run_time_hour < peak_end:
            return "peak"
        return "offpeak"

    def calculate_energy_cost(self, kwh_cycle: float, run_time_hour: int,
                              location: str) -> float:
        """Calculate energy cost using the utility's TOU rates for the given location."""
        utility = self._utility_for_location(location)
        rates = self.UTILITY_RATES[utility]
        period = self.determine_rate_period(run_time_hour, location)
        rate = rates["peak_rate"] if period == "peak" else rates["offpeak_rate"]
        cost = kwh_cycle * rate
        return cost

    def calculate_environmental_impact(self, kwh_cycle: float, run_time_hour: int) -> float:
        """Calculate environmental impact using PJM marginal emissions factors."""
        period = self.determine_emissions_period(run_time_hour)
        emissions_factor = self.EMISSIONS_FACTOR_PEAK if period == "peak" else self.EMISSIONS_FACTOR_OFFPEAK
        emissions = kwh_cycle * emissions_factor
        return emissions

    def calculate_comfort_score(self, delay_hours: float, run_time_hour: int,
                               housing_type: str, occupants: int,
                               appliance_type: str) -> float:
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

        # Component 2: Noise disruption penalty
        # Depends on: time of day + housing type + appliance noise level. Representative dBA:
        # dishwasher ~45 (Bellingham Electric (2026)), washer ~74 (spin-cycle peak,
        # Precision Appliance Leasing (2024)), dryer ~65 (Coolblue (2026)). Only the >45 threshold test
        # below reads these, so washer/dryer trigger the penalty regardless of the exact value.
        if appliance_type.lower() == "dishwasher":
            appliance_noise = 45
        elif appliance_type.lower() == "washer" or "washing" in appliance_type.lower():
            appliance_noise = 74
        elif appliance_type.lower() == "dryer":
            appliance_noise = 65
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

        final_comfort = base_comfort - noise_penalty - size_penalty
        return max(0.0, min(1.0, final_comfort / 10.0))

    def calculate_practicality_score(self, delay_hours: float, run_time_hour: int,
                                    housing_type: str, occupants: int,
                                    appliance_type: str) -> float:
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

        # Component 2: Timing complexity (remembering to run at specific hour)
        # Paetz et al.: "If low-price zones applied on brink of day, perceived as too early or too late"
        timing_penalty = 0.0
        if 0 <= run_time_hour < 6:    # Middle of night (midnight–6am)
            timing_penalty = 2.0
        elif 22 <= run_time_hour < 24: # Late night (10pm–midnight)
            timing_penalty = 1.0

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

        final_practicality = base_practicality - timing_penalty - coordination_penalty

        # Daytime floor: running appliances during business hours carries a minimum practicality
        # of 0.4 (always a socially acceptable option). Only applies when delay is within the
        # appliance-specific acceptable window — prevents large-delay wrap-bug rescues.
        DAYTIME_START = 7
        DAYTIME_END = 22
        if DAYTIME_START <= run_time_hour < DAYTIME_END and delay_hours <= max_delay:
            final_practicality = max(final_practicality, 0.4)

        return max(0.15, min(1.0, final_practicality / 10.0))


    def parse_alternative(self, alt: str, scenario: Dict) -> Tuple[int, float]:
        import re

        # Extract run time from alternative (e.g., "7pm", "10pm", "2am")
        time_match = re.search(r'(\d{1,2})(?::\d{2})?\s*(am|pm)', alt, re.IGNORECASE)
        if not time_match:
            # Don't silently fall back to baseline+0 delay — that fabricates a
            # zero-delay (perfect-comfort) result. Raise so the caller emits the
            # sentinel for this alternative.
            raise ValueError(f"Could not parse run time from alternative: {alt!r}")

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
        baseline_str = scenario.get('baseline_time', '7pm')
        baseline_hour = self._parse_time_to_hour(baseline_str)

        # Calculate delay from baseline as circular clock distance.
        # This treats near wrap-around differences as short delays (e.g., 2 hours),
        # rather than inflated 22-23 hour delays.
        delay_forward = float((run_time_hour - baseline_hour) % 24)
        delay_backward = float((baseline_hour - run_time_hour) % 24)
        delay_hours = min(delay_forward, delay_backward)

        return run_time_hour, delay_hours
    def _parse_time_to_hour(self, time_str: str) -> int:
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
        reference_ranges = {
            'energy_cost': {
                # 5th-95th percentile of the actual scenario-set per-cycle cost
                # distribution (kWh/cycle x the resolved TOU rate across the 6 PA
                # utilities): p5 = $0.025, p95 = $0.71. Dataset-percentile bounds
                # concentrate score sensitivity in the range households actually
                # encounter. Underlying kWh/cycle endpoints remain consistent with the
                # ENERGY STAR certified-products distribution (efficient HE washer
                # ~0.25 kWh) through older non-certified resistance dryers.
                'min': 0.025,
                'max': 0.71,
                'decreasing': True
            },
            'environmental': {
                # 5th-95th percentile of the actual scenario-set per-cycle emissions
                # distribution (kWh/cycle x PJM marginal factor at run time): p5 = 0.288,
                # p95 = 3.643 lbs CO2. Source: PJM 2022 CO2/SO2/NOx Emissions Report
                # (April 2023). Marginal (not average) factors are the correct measure
                # for behavioral time-shifting decisions because they reflect the
                # generator actually displaced or added at the margin.
                'min': 0.288,
                'max': 3.643,
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

        # Clamp final score to [0, 1]
        return max(0.0, min(1.0, u_x))

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

    def calculate_monthly_cost(self, per_cycle_cost: float, cycles_per_month: int = 30) -> float:
        return per_cycle_cost * cycles_per_month

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        alternatives = []
        for alt_key in ['alternative_1', 'alternative_2', 'alternative_3']:
            if alt_key in scenario and scenario[alt_key]:
                alternatives.append(scenario[alt_key])

        raw_results = {}

        for alt in alternatives:
            print(f"\nProcessing alternative: {alt}")

            try:
                run_time_hour, delay_hours = self.parse_alternative(alt, scenario)
                # kwh_per_cycle already reflects the appliance's age: within each
                # appliance type the dataset's per-cycle energy is strongly
                # correlated with appliance_age (older units assigned higher
                # kWh), so age's efficiency effect flows through here directly.
                energy_cost = self.calculate_energy_cost(
                    scenario['kwh_per_cycle'], run_time_hour, scenario['location']
                )
                emissions = self.calculate_environmental_impact(
                    scenario['kwh_per_cycle'], run_time_hour
                )
                comfort = self.calculate_comfort_score(
                    delay_hours, run_time_hour, scenario['housing_type'],
                    scenario['household_size'], scenario['appliance']
                )
                practicality = self.calculate_practicality_score(
                    delay_hours, run_time_hour, scenario['housing_type'],
                    scenario['household_size'], scenario['appliance']
                )
            except Exception as e:
                print(f"  scoring failed for {alt}: {e}; emitting sentinel {SENTINEL_VALUE}")
                raw_results[alt] = None
                continue

            raw_results[alt] = {
                'energy_cost_dollars': energy_cost,
                'emissions_lbs': emissions,
                'comfort_raw': comfort,
                'practicality_raw': practicality
            }

        # Apply value functions to get final 0-10 scores
        final_scores = {}

        for alt, raw in raw_results.items():
            if raw is None:
                final_scores[alt] = {
                    'energy_cost_score': SENTINEL_VALUE,
                    'environmental_score': SENTINEL_VALUE,
                    'comfort_score': SENTINEL_VALUE,
                    'practicality_score': SENTINEL_VALUE,
                    'raw_cost': SENTINEL_VALUE,
                    'raw_emissions': SENTINEL_VALUE,
                }
                continue

            energy_vf = self.apply_value_function(
                raw['energy_cost_dollars'],
                self.VF_ENERGY_COST,
                'energy_cost'
            )

            if 'utility_budget' in scenario and scenario['utility_budget'] > 0:
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost_dollars'],
                    cycles_per_month=self._cycles_per_month(scenario['appliance'])
                )

                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    scenario['utility_budget']
                )

                # Apply penalty to energy cost score
                energy_vf_penalized = energy_vf * budget_penalty
                energy_vf = energy_vf_penalized

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

            final_scores[alt] = {
                'energy_cost_score': round(energy_vf, 2),
                'environmental_score': round(env_vf, 2),
                'comfort_score': round(comfort_vf, 2),
                'practicality_score': round(practicality_vf, 2),
                'raw_cost': round(raw['energy_cost_dollars'], 4),
                'raw_emissions': round(raw['emissions_lbs'], 3)
            }

        return final_scores


def process_appliance_scenarios(
    xlsx_filename: str = str(SCENARIO_DIR / "ApplianceScenarios.xlsx"),
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_appliance.xlsx")):
    csv_path = Path(xlsx_filename)
    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = read_table_clean(
        csv_path,
        time_columns=['baseline_time'],
        keep_str_cols=[
            'baseline_time', 'question', 'location', 'appliance',
            'appliance_age', 'housing_type',
            'alternative_1', 'alternative_2', 'alternative_3',
        ],
    )

    required_cols = ['question', 'location', 'utility_budget', 'appliance', 'housing_type',
                     'household_size', 'kwh_per_cycle', 'appliance_age', 'baseline_time']

    def is_missing(value) -> bool:
        if value is None or pd.isna(value):
            return True
        return str(value).strip().lower() in {'', 'nan', 'none'}

    invalid_rows = []
    for row_index, row in df.iterrows():
        missing_cols = [col for col in required_cols if is_missing(row.get(col))]
        if missing_cols:
            invalid_rows.append((row_index, missing_cols))

    if invalid_rows:
        preview = ", ".join(
            f"row {row_index + 2} missing {missing_cols}" for row_index, missing_cols in invalid_rows[:5]
        )
        raise ValueError(
            f"ApplianceScenarios.xlsx contains {len(invalid_rows)} malformed row(s). "
            f"Fix or remove them before processing. Examples: {preview}"
        )

    print(f"Found {len(df)} valid appliance scenarios")

    calculator = ApplianceGroundTruthCalculator()

    results = []

    for idx, row in df.reset_index(drop=True).iterrows():
        print(f"\nProcessing scenario {idx + 1}/{len(df)}: {row['appliance']} in {row['location']}")

        # Collect alternatives
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()

            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        scenario = {
            'question': row['question'],
            'location': row['location'],
            'utility_budget': float(row.get('utility_budget', 0)),
            'appliance': row['appliance'],
            'housing_type': row['housing_type'],
            'household_size': int(row['household_size']),
            'kwh_per_cycle': float(row['kwh_per_cycle']),
            'appliance_age': row['appliance_age'],
            'baseline_time': row.get('baseline_time', ''),
            'alternative_1': row['alternative_1'],
            'alternative_2': row['alternative_2'],
            'alternative_3': row['alternative_3'],
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
                    'utility_budget': float(row.get('utility_budget', 0)),
                    'appliance': row['appliance'],
                    'appliance_age': row['appliance_age'],
                    'housing_type': row['housing_type'],
                    'household_size': row['household_size'],
                    'kwh_per_cycle': row['kwh_per_cycle'],
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
    _STR_COLS = ['question', 'location', 'appliance', 'appliance_age', 'housing_type', 'alternative']
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



if __name__ == "__main__":
    process_appliance_scenarios()
