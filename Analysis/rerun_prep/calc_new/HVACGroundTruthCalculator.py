import sys
import pandas as pd
import math
import logging
import numpy as np
import re
from typing import Dict, List, Tuple
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from sentinel_utils import apply_mavt_ranking, read_table_clean, has_sentinel_scores, SENTINEL_VALUE


class HVACGroundTruthCalculator:
    # PJM marginal emissions factors (lbs CO2/kWh). Source: PJM 2022 CO2/SO2/NOx Emissions Report (April 2023).
    # Marginal, not average, is what we want here because it tracks what actually gets shifted at the edge.
    # Peak is 7am-11pm (16h) and off-peak is 11pm-7am (8h) per PJM, which defines the peak for
    # non-holiday weekdays; every scenario is a non-holiday weekday, so the split applies as coded.
    EMISSIONS_FACTOR_PEAK = 1.041     # PJM peak (1041 lbs/MWh)
    EMISSIONS_FACTOR_OFFPEAK = 0.976  # PJM off-peak (976 lbs/MWh)
    EMISSIONS_PEAK_HOURS_PER_DAY = 16
    EMISSIONS_OFFPEAK_HOURS_PER_DAY = 8

    # PA residential flat electricity rate, $/kWh. Source: EIA Electric Power Annual (2025)
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024). 0.19 is the bundled default-service
    # rate (supply + delivery + riders) the paper derives from PA PUC (2025), not an EIA figure.
    ELECTRICITY_RATE_PA = 0.19

    # Residential infiltration rate (air changes/hour) for the air-change load method.
    # Source: ACCA Manual J (2016) -- 0.35 ACH is the standard
    # modern/average-construction default (also the ASHRAE Standard 62-1989 minimum of 0.35 ACH in living areas).
    AIR_CHANGES_PER_HOUR = 0.35

    # Internal gains, sensible only (the load balance is sensible). Occupants: 220 Btu/h per
    # person, the single-zone sensible gain in Building America House Simulation Protocols
    # (Hendron & Engebrecht 2010) Table 44, citing ASHRAE (2009); the 164 Btu/h latent part is
    # left out. Equipment 1.0 Btu/h per sqft and the 800 Btu/h base are our assumptions (the HSP
    # gives appliance/MEL gains as annual kWh by bedroom count, not in these units).
    OCCUPANT_SENSIBLE_GAIN_BTUH = 220
    EQUIPMENT_GAIN_BTUH_PER_SQFT = 1.0
    BASE_INTERNAL_GAIN_BTUH = 800

    # Heat-pump heating efficiency paired with rated SEER, as (SEER, HSPF) anchors. HSPF is
    # seasonal Btu of heat delivered per Wh of electricity (seasonal COP = HSPF / 3.412), so
    # heating kWh = Btu / (HSPF x 1000), the same form as cooling kWh = Btu / (EER x 1000).
    # SEER <= 14: Building America HSP (Hendron & Engebrecht 2010) Table 32 split heat pump
    #   defaults (6.5/6.0, 8/6.6, 10/7.1, 14/8.0) and the Table 4 benchmark (13 SEER/7.7 HSPF).
    #   Table 32: "Default efficiencies for equipment not listed
    #   in the table may either be interpolated or estimated by referring to the original references."
    # SEER > 14: NREL ResStock/BEopt ASHP options "ASHP, SEER 18, 9.3 HSPF" and
    #   "ASHP, SEER 22, 10 HSPF" (resstock v3.2.0 resources/options_lookup.tsv).
    # Piecewise-linear between anchors; linear along the end segments outside 6.5-22.
    # HSPF is a seasonal rating, so it does not vary with the scenario's outdoor temperature.
    HSPF_BY_SEER = ((6.5, 6.0), (8.0, 6.6), (10.0, 7.1), (13.0, 7.7), (14.0, 8.0),
                    (18.0, 9.3), (22.0, 10.0))

    # Operating mode = the system the household asked about ('heat' or 'cool'), read from the
    # question with a strict matcher (hvac_mode_from_question) unless the scenario carries an
    # explicit hvac_mode. No outdoor-temperature season test is used anywhere. The mode sets
    # the Comfort optimum, the load direction, Practicality and the "Off" free-float.
    HVAC_MODES = ('heat', 'cool')
    _HEAT_WORDS = re.compile(r"\bheat(?:ing)?\b", re.IGNORECASE)
    _COOL_WORDS = re.compile(r"\bAC\b|\bA/C\b|\bair[- ]condition(?:ing|er)\b")

    # Thermostat optima by mode: Building America HSP, "Thermostat set points based on the
    # optimum seasonal temperature for human comfort as defined in ASHRAE Standard 55-2004 ...
    # Set point for cooling: 76F ... Set point for heating: 71F". Each optimum is the
    # midpoint of its comfort range (AC mode: SUMMER_*, heat mode: WINTER_*).
    SUMMER_COMFORT_RANGE = (73, 79)
    SUMMER_OPTIMAL = 76
    WINTER_COMFORT_RANGE = (68, 74)
    WINTER_OPTIMAL = 71

    # Linear VF for energy cost - equal marginal utility across range
    # Dyer & Sarin (1979): "For monetary attributes with small stakes relative to wealth,
    # linear utility is appropriate" (Oper. Res. 27(4):810-822)
    VF_ENERGY_COST = "linear"

    # Linear VF for environmental impact:
    # - Keeney & Raiffa (1976): Foundation for Multi-Attribute Value Theory axioms.
    # Linear VF justification in this context: When environmental impacts are framed in
    # absolute physical units (lbs CO2), a linear preference is a conservative modeling choice
    # that treats equal changes in emissions as equally valuable reductions.
    VF_ENVIRONMENTAL = "linear"
    VF_COMFORT = "logarithmic, a=1.5"
    VF_PRACTICALITY = "logarithmic, a=1.2"
    def calculate_net_heat_gain(self, outdoor_temp: float, indoor_temp: float,
                                square_footage: int, r_value: int, household_size: int = 3,
                                ceiling_height: float = 8.0,
                                housing_type: str = "Single-family",
                                include_solar: bool = True) -> float:
        """Sensible heat balance of the house held at indoor_temp, in BTU/hr: conduction +
        infiltration + internal gains (+ solar when include_solar). Positive means the house
        gains heat and needs cooling; negative means it loses heat and needs heating."""
        delta_t = outdoor_temp - indoor_temp

        # Adjust by housing type. Our multipliers, set by exposure (not a Manual J table):
        # - Single-family (2-story typical): 1.7 (includes roof, walls, floor exposures)
        # - Apartment (mid-unit typical): 1.2 (shared walls reduce exposure)
        # - Townhouse (end-unit typical): 1.5 (one or two shared walls)
        housing_multipliers = {
            "Single-family": 1.7,
            "Apartment": 1.2,
            "Condo": 1.2,
            "Townhouse": 1.5,
            "Rowhouse": 1.5,
        }
        envelope_multiplier = housing_multipliers.get(housing_type, 1.7)
        envelope_area = square_footage * envelope_multiplier

        u_factor = 1.0 / r_value

        conductive_load = u_factor * envelope_area * delta_t

        # Formula: occupants (230 BTU/hr sensible each) + lighting & equipment (1.0 BTU/hr/sqft) + baseline (800)
        # Example: for 3-person, 1500 sqft home: (3 x 230) + (1500 x 1.0) + 800 = 2,990 BTU/hr
        # Occupant gain per Building America HSP Table 44 (sensible); 1.0/sqft and 800 are our assumptions
        internal_gains = ((household_size * self.OCCUPANT_SENSIBLE_GAIN_BTUH)
                          + (square_footage * self.EQUIPMENT_GAIN_BTUH_PER_SQFT)
                          + self.BASE_INTERNAL_GAIN_BTUH)

        # Glazing = 15% of floor area, the IECC R405 standard reference design; 20 BTU/hr per
        # sqft of glass is our assumption. Solar counts only in AC mode.
        window_area = square_footage * 0.15
        solar_gains = window_area * 20 if include_solar else 0.0

        # Infiltration sensible load via the air-change method (ACCA Manual J (2016)):
        #   cfm = volume_ft3 * ACH / 60;  Q_sensible = 1.08 * cfm * deltaT
        #   1.08 = rho*cp*60 = 0.075 lbm/ft3 * 0.24 BTU/(lbm F) * 60 min/hr
        #   (ASHRAE Handbook of Fundamentals (2017) Ch.16)
        infiltration_cfm = (square_footage * ceiling_height * self.AIR_CHANGES_PER_HOUR) / 60.0
        infiltration_load = 1.08 * infiltration_cfm * delta_t

        return conductive_load + internal_gains + solar_gains + infiltration_load

    def calculate_cooling_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int, household_size: int = 3,
                               ceiling_height: float = 8.0,
                               housing_type: str = "Single-family") -> float:
        # Cooling load = the positive part of the net heat gain, solar included.
        return max(0, self.calculate_net_heat_gain(
            outdoor_temp, indoor_temp, square_footage, r_value, household_size,
            ceiling_height, housing_type, include_solar=True))

    def calculate_heating_load(self, outdoor_temp: float, indoor_temp: float,
                               square_footage: int, r_value: int, household_size: int = 3,
                               ceiling_height: float = 8.0,
                               housing_type: str = "Single-family") -> float:
        # Heating load = the negative part of the net heat gain (no solar credit): conductive
        # and infiltration loss minus the same internal gains as the cooling load.
        return max(0, -self.calculate_net_heat_gain(
            outdoor_temp, indoor_temp, square_footage, r_value, household_size,
            ceiling_height, housing_type, include_solar=False))

    def heating_hspf(self, seer: float) -> float:
        """HSPF paired with a rated SEER, piecewise-linear over HSPF_BY_SEER (linear along
        the end segments outside the anchor range)."""
        pts = self.HSPF_BY_SEER
        s = float(seer)
        if s <= pts[0][0]:
            (x0, y0), (x1, y1) = pts[0], pts[1]
        elif s >= pts[-1][0]:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
        else:
            i = next(k for k in range(1, len(pts)) if s <= pts[k][0])
            (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        return y0 + (s - x0) * (y1 - y0) / (x1 - x0)

    def calculate_energy_consumption(self, load_btu_hr: float, seer: int,
                                     occupancy_context: str, hours: float = 8,
                                     mode: str = 'cool') -> float:
        # Energy reflects the unit's rated efficiency only. Age/maintenance efficiency
        # degradation is NOT applied here -- it is modeled as a reliability factor in
        # calculate_practicality_score (item 3d). Keeping it out of the energy path means
        # the energy score reflects the setpoint choice, not the system's condition.
        # Cooling: EER = -0.02 * SEER^2 + 1.12 * SEER  (Source: Building America House Simulation
        # Protocols, Hendron & Engebrecht 2010, Eq. 3, citing Wassmer 2003).
        # Heating: the HSPF paired with the SEER (heating_hspf), a seasonal Btu/Wh rating.
        if mode == 'heat':
            efficiency_btu_per_wh = self.heating_hspf(seer)
        else:
            efficiency_btu_per_wh = (-0.02 * seer ** 2) + (1.12 * seer)

        kw = (load_btu_hr / efficiency_btu_per_wh) / 1000
        occupancy_context = self.normalize_occupancy_context(occupancy_context)

        if occupancy_context == "occupied_all_day":
            runtime_multiplier = 1.0
        elif occupancy_context.startswith("unoccupied_"):
            hours_match = re.search(r"(\d+)", occupancy_context)
            if hours_match:
                hours_away = max(0, min(int(hours_match.group(1)), 24))
            else:
                hours_away = 8
            runtime_multiplier = 1.0 - (hours_away / 24) * 0.5
        elif occupancy_context == "occupied_sleep":
            runtime_multiplier = 0.75
        else:
            runtime_multiplier = 1.0
        total_kwh = kw * hours * runtime_multiplier
        return total_kwh

    def hvac_mode_from_question(self, question) -> str:
        """'heat' or 'cool' from the question wording ("what heat temperature ..." /
        "what AC temperature ..."). Returns None when the question names neither system or
        both, so the caller emits the sentinel instead of guessing."""
        text = "" if question is None else str(question)
        heat = bool(self._HEAT_WORDS.search(text))
        cool = bool(self._COOL_WORDS.search(text))
        if heat == cool:
            return None
        return 'heat' if heat else 'cool'

    def resolve_hvac_mode(self, scenario: Dict) -> str:
        """Explicit scenario['hvac_mode'] ('heat'/'cool') wins; otherwise the question
        matcher. Any other explicit value, or an unmatched question, returns None."""
        explicit = scenario.get('hvac_mode')
        if explicit is not None and not (isinstance(explicit, float) and pd.isna(explicit)) \
                and str(explicit).strip() != '':
            value = str(explicit).strip().lower()
            return value if value in self.HVAC_MODES else None
        return self.hvac_mode_from_question(scenario.get('question'))

    def calculate_comfort_score(self, indoor_temp: float, outdoor_temp: float,
                                household_size: int, mode: str = None) -> float:
        # outdoor_temp is not used (the mode, not the weather, sets the optimum); it is kept
        # for signature compatibility. mode must be 'heat' or 'cool'.
        # Tent comfort function around PMV-neutral indoor setpoints for mechanical HVAC.
        # Optimal indoor 76F in AC mode and 71F in heat mode: the Building
        # America HSP set points (optimum seasonal temperature per ASHRAE 55-2004), and the
        # midpoints of the summer (73-79F, 0.5 clo) and winter (68-74F, 1.0 clo) comfort
        # bands -- both for sedentary occupants. Score = 10 - |indoor - optimal|, clipped to
        # [0,10]; the -1.0/F slope mirrors the rising PPD per F outside neutral in Fanger's
        # PMV/PPD model. The adaptive method (de Dear & Brager (2002)) applies only to
        # naturally conditioned spaces and is not used here.
        # Sources: Hendron & Engebrecht (2010); ASHRAE 55-2020 (Sec 5.3.1 graphic zone); Fanger (1970); van Hoof (2008).
        if mode not in self.HVAC_MODES:
            raise ValueError(f"HVAC mode must be 'heat' or 'cool', got {mode!r}")
        optimal = self.SUMMER_OPTIMAL if mode == 'cool' else self.WINTER_OPTIMAL
        comfort_score = 10 - abs(indoor_temp - optimal)

        if household_size > 3:
            size_penalty = (household_size - 3) * 0.3
            comfort_score -= size_penalty * (abs(indoor_temp - optimal) / 3.0)

        return max(0.0, min(1.0, comfort_score / 10.0))

    def _efficiency_degradation(self, hvac_age: int, maintenance_level: str = 'moderate') -> float:
        """Fraction of HVAC efficiency lost to age + maintenance: front-loaded, capped
        at 30%. Base annual loss 0.5/1.0/1.5%/yr for good/moderate/poor upkeep; the first
        10 years degrade at 1.5x base, later years at 0.5x. These rates and the cap are our
        assumptions; every scenario uses 'moderate'. Raises on a missing age rather
        than defaulting to 0 (which would falsely score the system as pristine)."""
        if hvac_age is None:
            raise ValueError("hvac_age is required to compute efficiency degradation")
        rates = {'good': 0.005, 'moderate': 0.010, 'poor': 0.015}
        base_rate = rates.get(maintenance_level, 0.010)
        if hvac_age <= 10:
            total_degradation = hvac_age * (base_rate * 1.5)
        else:
            total_degradation = 10 * (base_rate * 1.5) + (hvac_age - 10) * (base_rate * 0.5)
        return min(total_degradation, 0.30)

    def calculate_practicality_score(self, outdoor_temp: float, indoor_temp: float,
                                     hvac_age: int, maintenance_level: str = 'moderate',
                                     mode: str = None) -> float:
        # mode ('heat' or 'cool') is the scenario's operating mode, the same one that sets
        # the load and the Comfort optimum. Extremity penalties grow as the setpoint moves past
        # adoption-comfort bounds: in cooling, setpoints >= 82F (too warm to tolerate) or
        # <= 71F (overcooling) are penalized; in heating, <= 63F (too cold) or >= 76F
        # (overheating). Slopes are asymmetric because the too-cold directions draw the
        # sharper real-world adoption penalties. The thresholds, slopes and the delta-T
        # factors below are our values.
        if mode not in self.HVAC_MODES:
            raise ValueError(f"HVAC mode must be 'heat' or 'cool', got {mode!r}")
        if mode == 'cool':  # Cooling mode
            if indoor_temp >= 82:
                extremity_penalty = (indoor_temp - 82) * 1.5
            elif indoor_temp <= 71:
                extremity_penalty = (71 - indoor_temp) * 1.0
            else:
                extremity_penalty = 0
        else:  # Heating mode
            if indoor_temp <= 63:
                extremity_penalty = (63 - indoor_temp) * 1.8
            elif indoor_temp >= 76:
                extremity_penalty = (indoor_temp - 76) * 0.8
            else:
                extremity_penalty = 0

        base_score = 10 - extremity_penalty
        base_score = max(0.5, base_score)

        # Component 2: delta-T operational feasibility. Large outdoor-indoor gaps push the
        # system toward its limits (lower reliability / higher failure risk).
        delta_t = abs(outdoor_temp - indoor_temp)
        if delta_t < 10:
            delta_t_multiplier = 1.0
        elif delta_t < 20:
            delta_t_multiplier = 0.95
        elif delta_t < 35:
            delta_t_multiplier = 0.85
        else:
            delta_t_multiplier = 0.70

        base_score *= delta_t_multiplier

        # Component 3: system condition (item 3d). Age/maintenance efficiency degradation
        # is a reliability concern -- an older or poorly maintained unit is a less
        # practical choice to rely on -- so it scales the score down by the degraded
        # fraction (0-30%) instead of inflating energy use.
        degradation = self._efficiency_degradation(hvac_age, maintenance_level)
        base_score *= (1 - degradation)

        return max(0.15, min(1.0, base_score / 10.0))

    def calculate_monthly_cost(self, per_period_cost: float, periods_per_month: int = 90) -> float:
        return per_period_cost * periods_per_month

    def calculate_budget_penalty(self, monthly_cost: float, monthly_budget: float) -> float:
  
        utilization = monthly_cost / monthly_budget

        if utilization < 0.80:
            # Mental budget safety margin (Thaler 1999)
            return 1.0

        elif utilization < 1.0:
            # Linear decline as budget limit approached (Heath & Soll 1996)
            return 1.0 - 2.5 * (utilization - 0.80)

        else:
            # Exponential loss aversion under budget violation (Prelec & Loewenstein 1998; Heutel 2017).
            # Continuous for every u >= 1.0: the former drop to 0 at u = 1.5 is removed, so an
            # over-budget option keeps a small, still-decreasing credit instead of a cliff.
            import math
            return 0.5 * math.exp(-3.0 * (utilization - 1.0))

    def emissions_factor_for_occupancy(self, occupancy_context: str) -> float:
        """PJM marginal CO2 factor (lbs/kWh) implied by an HVAC occupancy context.
        HVAC alternatives carry no explicit start_time, so run-time is inferred from the
        occupancy pattern against the PJM peak (7am-11pm) / off-peak (11pm-7am) windows
        (Source: PJM 2022 Emissions Report, April 2023):
          - occupied_all_day: runs the full 24h -> peak/off-peak hour-weighted average.
          - occupied_sleep:   home only at night, so run-time falls entirely in the 8h
                              off-peak window -> off-peak factor (this is intended).
          - unoccupied_<H>:   reduced run-time occurs across the H daytime away-hours,
                              which fill the peak window first. H <= 16 -> all peak;
                              H > 16 -> (16h peak + (H-16)h off) / H, a correct hour-
                              weighted average over the H-hour run window.
        """
        ctx = self.normalize_occupancy_context(occupancy_context)
        peak = self.EMISSIONS_FACTOR_PEAK
        off = self.EMISSIONS_FACTOR_OFFPEAK
        peak_h = self.EMISSIONS_PEAK_HOURS_PER_DAY
        off_h = self.EMISSIONS_OFFPEAK_HOURS_PER_DAY

        if ctx == "occupied_sleep":
            return off

        if ctx == "occupied_all_day":
            return (peak_h * peak + off_h * off) / (peak_h + off_h)

        if ctx.startswith("unoccupied_"):
            hours_match = re.search(r"(\d+)", ctx)
            hours_away = int(hours_match.group(1)) if hours_match else 8
            hours_away = max(0, min(hours_away, 24))
            if hours_away <= peak_h:
                return peak
            offpeak_hours = hours_away - peak_h
            return (peak_h * peak + offpeak_hours * off) / hours_away

        return (peak_h * peak + off_h * off) / (peak_h + off_h)

    def normalize_occupancy_context(self, occupancy_value) -> str:
        """Map raw scenario occupancy tokens to canonical internal tokens.

        Required (not a no-op): HVACScenarios.xlsx stores non-canonical values
        ('standard', 'sleep', 'overnight_sleep', 'unoccupied_4hr/8hr/12hr') that
        must be folded to 'occupied_all_day' / 'occupied_sleep' / 'unoccupied_<H>'.
        """
        if occupancy_value is None or pd.isna(occupancy_value):
            return "occupied_all_day"

        value = str(occupancy_value).strip().lower()

        if value in {"occupied_all_day", "standard", "occupied", "home_all_day"}:
            return "occupied_all_day"

        if value in {"occupied_sleep", "sleep", "night", "overnight_sleep", "overnight"}:
            return "occupied_sleep"

        if value.startswith("unoccupied"):
            hours_match = re.search(r"(\d+)", value)
            if hours_match:
                hours_away = max(0, min(int(hours_match.group(1)), 24))
                return f"unoccupied_{hours_away}"
            return "unoccupied_8"

        return "occupied_all_day"

    def apply_value_function(self, raw_value: float, vf_spec: str, value_type: str) -> float:
        reference_ranges = {
            'energy_cost': {
                # 5th-95th percentile of the actual scenario-set HVAC cost distribution
                # (8h window at $0.19/kWh; per-alternative cost rounded to cents, the
                # raw_cost column), pooled over the 105 test + RAG scenarios and computed
                # over the ACTIVE-conditioning alternatives only. Zero-load alternatives
                # (the bare "Off" option, or a setpoint where the heat balance is exactly
                # zero, or a setpoint the mode caps at zero load) collapse to $0 and are
                # excluded from the percentile so the normalization floor is not degenerate;
                # an Off/zero-load alternative still scores at the top of the [0,10] cost
                # scale via the (x_max - x) normalization. p5 over the nonzero active set
                # (306 of 315) = $0.590, p95 = $3.268. Endpoints remain consistent
                # with residential HVAC studies (efficient: Huyen & Cetin (2019),
                # Energies 12(1):188; degraded: Alves et al. (2016), EB 130:408).
                'min': 0.59,
                'max': 3.27,
                'decreasing': True
            },
            'environmental': {
                # Derived from the same active-set 5th-95th percentile cost envelope as
                # energy_cost ($0.590-$3.268 at $0.19/kWh flat = 3.105-17.197 kWh), applied
                # against PJM marginal emissions factors (0.976 off-peak, 1.041 peak) to
                # keep cost and emissions physically consistent (these are not percentiles
                # of the emissions distribution):
                #   min = 3.105 kWh x 0.976 lbs/kWh = 3.03 lbs CO2  (best case: fully off-peak)
                #   max = 17.197 kWh x 1.041 lbs/kWh = 17.90 lbs CO2 (worst case: fully peak)
                # Source: PJM 2022 Emissions Report (April 2023).
                # For HVAC, alternatives within one scenario share the same emission
                # factor because they are evaluated at the same moment and differ by load.
                'min': 3.03,
                'max': 17.90,
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

        x = raw_value

        vf_type = vf_spec.split(',')[0].strip().lower()

        if ref['decreasing']:
            x_normalized = (x_max - x) / (x_max - x_min)
        else:
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
                    u_x = 0.0
                else:
                    u_x = math.log(a * x_normalized + 1) / math.log(a + 1)

        else:
            u_x = x_normalized

        return max(0.0, min(1.0, u_x))

    def _free_float_temp(self, outdoor_temp: float, ac_mode: bool) -> float:
        # Indoor air a bare "Off" system drifts to when no explicit target is given. With
        # the system off, solar + internal gains drive indoor ABOVE outdoor in AC
        # mode (a closed, occupied house runs ~5F over outdoor on a daily mean), while in
        # heat mode internal gains hold indoor ~10F above outdoor (HDD-65 balance-point
        # floor). The +5F/+10F offsets are our modeling assumption, not tabulated by these
        # sources: de Dear & Brager (2002) / ASHRAE 55-2020 (free-running adaptive
        # model: indoor >= outdoor under heat); ACCA Manual J (2016) (solar + internal gains
        # are additive); ASHRAE Handbook of Fundamentals (2017) (balance-point /
        # internal-gain offset). Replaces an earlier unsourced +/-5F placeholder whose
        # cooling-season sign was physically backwards.
        return outdoor_temp + 5 if ac_mode else outdoor_temp + 10

    def calculate_scenario_scores(self, scenario: Dict) -> Dict:
        # Operating mode from the question (or an explicit hvac_mode). It sets the "Off"
        # drift, the Comfort optimum, the load direction, Practicality and whether solar gain
        # enters the heat balance (AC mode only, as the heating load never took a solar credit).
        # No mode -> every alternative is the sentinel; the mode is never guessed.
        mode = self.resolve_hvac_mode(scenario)
        if mode is None:
            print(f"   Could not determine heat/AC mode from the question; emitting sentinel {SENTINEL_VALUE}")
        ac_mode = (mode == 'cool')

        raw_results = {}

        for alt in scenario['alternatives']:
            if mode is None:
                raw_results[alt] = None
                continue
            if isinstance(alt, str):
                import re

                # Enhanced parsing for "Off" alternatives
                # Handles: "Off", "Off (55)", "Off (let drift to 85)", etc.
                if 'off' in alt.lower():
                    paren_match = re.search(r'\(.*?(\d+).*?\)', alt)
                    if paren_match:
                        effective_temp = float(paren_match.group(1))
                    elif 'to' in alt.lower():
                        to_match = re.search(r'to\s+(\d+)', alt, re.IGNORECASE)
                        if to_match:
                            effective_temp = float(to_match.group(1))
                        else:
                            effective_temp = self._free_float_temp(scenario['outdoor_temp'], ac_mode)
                    else:
                        effective_temp = self._free_float_temp(scenario['outdoor_temp'], ac_mode)
                else:
                    # Not an "off" alternative - extract first number found
                    numbers = re.findall(r'\d+', alt)
                    if numbers:
                        effective_temp = float(numbers[0])
                    else:
                        print(f"   Could not parse alternative: {alt}; emitting sentinel {SENTINEL_VALUE}")
                        raw_results[alt] = None
                        continue
            else:
                effective_temp = float(alt)

            # Load from the setpoint against the house's free-float balance (conduction +
            # infiltration + internal gains, + solar in AC mode), capped by the mode: heat mode
            # supplies heat only when the balance calls for heat, AC mode removes heat only when
            # it calls for cooling, otherwise the load is 0. Never cooling in heat mode or
            # heating in AC mode.
            net_gain = self.calculate_net_heat_gain(
                scenario['outdoor_temp'],
                effective_temp,
                scenario['square_footage'],
                scenario['r_value'],
                scenario['household_size'],
                scenario.get('ceiling_height', 8.0),
                scenario.get('housing_type', 'Single-family'),
                include_solar=ac_mode,
            )
            if mode == 'cool':
                load = max(0.0, net_gain)
            else:
                load = max(0.0, -net_gain)

            kwh = self.calculate_energy_consumption(
                load,
                scenario['seer'],
                occupancy_context=self.normalize_occupancy_context(
                    scenario.get('occupancy_context', 'occupied_all_day')
                ),
                mode=mode,
            )

            energy_cost = kwh * scenario.get('electricity_rate', self.ELECTRICITY_RATE_PA)
            emission_factor = self.emissions_factor_for_occupancy(
                scenario.get('occupancy_context', 'occupied_all_day')
            )
            emissions = kwh * emission_factor

      
            if 'off' in alt.lower():
                kwh = 0.0
                energy_cost = 0.0
                emissions = 0.0

              # Still use drift temp for comfort/practicality scoring.

            comfort = self.calculate_comfort_score(
                effective_temp,
                scenario['outdoor_temp'],
                scenario['household_size'],
                mode=mode,
            )

            practicality = self.calculate_practicality_score(
                scenario['outdoor_temp'],
                effective_temp,
                scenario['hvac_age'],
                scenario.get('maintenance_level', 'moderate'),
                mode=mode,
            )
            raw_results[alt] = {
                'kwh': kwh,
                'energy_cost_dollars': energy_cost,
                'emissions_lbs': emissions,
                'comfort_raw': comfort,
                'practicality_raw': practicality
            }

        final_scores = {}
        utility_budget = float(scenario.get('utility_budget', 0.0))

        for alt, raw in raw_results.items():
            if raw is None:
                final_scores[alt] = {
                    'energy_cost_score': SENTINEL_VALUE,
                    'environmental_score': SENTINEL_VALUE,
                    'comfort_score': SENTINEL_VALUE,
                    'practicality_score': SENTINEL_VALUE,
                    'raw_kwh': SENTINEL_VALUE,
                    'raw_cost': SENTINEL_VALUE,
                    'raw_emissions': SENTINEL_VALUE,
                }
                continue

            energy_vf = self.apply_value_function(
                raw['energy_cost_dollars'],
                self.VF_ENERGY_COST,
                'energy_cost'
            )

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

            if utility_budget > 0:
                # Monthly cost proxy: holding this setpoint across all three 8h periods
                # per day, every day -> 3 periods/day * 30 days = 90 periods/month.
                monthly_cost = self.calculate_monthly_cost(
                    raw['energy_cost_dollars'],
                    periods_per_month=90
                )

                budget_penalty = self.calculate_budget_penalty(
                    monthly_cost,
                    utility_budget
                )

                energy_vf_penalized = energy_vf * budget_penalty
                energy_vf = energy_vf_penalized

            final_scores[alt] = {
                'energy_cost_score': round(energy_vf, 2),
                'environmental_score': round(env_vf, 2),
                'comfort_score': round(comfort_vf, 2),
                'practicality_score': round(practicality_vf, 2),
                'raw_kwh': round(raw['kwh'], 2),
                'raw_cost': round(raw['energy_cost_dollars'], 2),
                'raw_emissions': round(raw['emissions_lbs'], 2)
            }

        return final_scores


def process_hvac_scenarios(
    csv_filename: str = str(SCENARIO_DIR / "HVACScenarios.xlsx"),
    output_filename: str = str(GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx")):
    csv_path = Path(csv_filename)
    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = read_table_clean(
        csv_path,
        keep_str_cols=[
            'question', 'location', 'insulation', 'housing_type',
            'house_age', 'alternative_1', 'alternative_2', 'alternative_3',
        ],
    )

    print(f"Found {len(df)} scenarios")

    calculator = HVACGroundTruthCalculator()

    results = []

    for idx, row in df.iterrows():
        print(f"Processing scenario {idx + 1}/{len(df)}: {row['location']}")
        electricity_rate = HVACGroundTruthCalculator.ELECTRICITY_RATE_PA

        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()

            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)

        scenario = {
            'question': row['question'],
            'location': row['location'],
            'square_footage': int(row['square_footage']),
            'r_value': int(row['r_value']),
            'household_size': int(row['household_size']),
            'utility_budget': float(row.get('utility_budget', 0)),
            'outdoor_temp': float(row['outdoor_temp']),
            'seer': int(row['seer']),
            'hvac_age': int(row['hvac_age']),
            'housing_type': str(row.get('housing_type', 'Single-family')),
            'occupancy_context': calculator.normalize_occupancy_context(
                row.get('occupancy_context', 'occupied_all_day')
            ),
            'electricity_rate': electricity_rate,
            'alternatives': alternatives,
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
                    'square_footage': row['square_footage'],
                    'insulation': row.get('insulation', ''),
                    'household_size': row['household_size'],
                    'utility_budget': row.get('utility_budget', ''),
                    'housing_type': row.get('housing_type', ''),
                    'outdoor_temp': row['outdoor_temp'],
                    'house_age': row.get('house_age', ''),
                    'alternative': alt,
                    'energy_cost_score': alt_scores['energy_cost_score'],
                    'environmental_score': alt_scores['environmental_score'],
                    'comfort_score': alt_scores['comfort_score'],
                    'practicality_score': alt_scores['practicality_score'],
                    'mavt_score': ranking_result["weighted_scores"][list(scores.keys()).index(alt)],
                    'rank': ranking_result["ranks"][list(scores.keys()).index(alt)],
                    'raw_kwh': alt_scores['raw_kwh'],
                    'raw_cost': alt_scores['raw_cost'],
                    'raw_emissions': alt_scores['raw_emissions']
                }
                results.append(result_row)

        except Exception as e:
            print(f"ERROR processing scenario {idx}: {e}")
            continue

    results_df = pd.DataFrame(results)
    _STR_COLS = ['question', 'location', 'insulation', 'housing_type', 'house_age', 'alternative']
    _INT_COLS = ['scenario_id', 'household_size', 'square_footage', 'rank']
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
    process_hvac_scenarios()
