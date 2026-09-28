# Provenance: Shower reference calculator (new)

File: `Analysis/rerun_prep/calc_new/ShowerGroundTruthCalculator.py` (line numbers below refer to it).
Only comments changed from the shipped file, plus the continuous budget penalty (author's decision, 2026-09-25), which no Shower alternative reaches; every scored value is the shipped value. Written 2026-09-25
from sources already read in the P1-HVAC session and the quotes recorded in `paper/CALCULATOR_AUDIT.md`
(Shower section) and Part B of `paper/pass5/PASS5_PROPOSAL.md`. No source was re-fetched for this file.
"Quote not recorded" means no verbatim line was kept in an earlier pass.

Source keys:
- **REU2016**: DeOreo et al. (2016), *Residential End Uses of Water, Version 2*, Water Research Foundation.
- **CFR 430.32**: 10 CFR 430.32(d). https://www.law.cornell.edu/cfr/text/10/430.32
- **CDC**: CDC (2026), Monitoring building water / Legionella control guidance.
  https://www.cdc.gov/control-legionella/php/guidance/monitor-water-guidance.html
- **Burch & Christensen 2007**: mains water temperature algorithm, OSTI 981988 (audit read it via the
  energystar.gov "AlgorithmForMainsWaterTemperature.pdf").
- **Zhang 2023**: Zhang et al. (2023), *Buildings* 13(5), 1300.
- **Ibanez-Rueda 2023**: https://link.springer.com/article/10.1007/s40899-023-00905-3 (abstract only).
- **Harris 2024**: The Harris Poll (2024), shower-duration tabulations (Q4).
- **Rheem 2025**: Rheem residential electric tank water heater specifications (code comment only).

| Item | Value | Code location | Source | Verbatim quote supporting the value | Status | Previous source |
|---|---|---|---|---|---|---|
| `ELECTRICITY_RATE_PA` | $0.19/kWh flat | ShowerGroundTruthCalculator.py:29 | Paper: bundled default-service rate from PA PUC (2025); EIA Table 5A for context | EIA: "Pennsylvania ... 17.77" (c/kWh, 2024) | derived (from PA PUC 2025 default-service components, per the paper; derivation not re-checked here) | EIA Electric Power Annual (2025), "0.19 is a defensible flat-rate proxy" |
| `INLET_TEMP_WINTER` | 45 F (outdoor <= 32 F) | :36 | our linear approximation to Burch & Christensen 2007 | Quote not recorded. Audit summary: Burch = annual sinusoid (annual mean ambient + ~6 F offset, amplitude 0.4 x ambient swing, phase lag), giving Pittsburgh ~47-69 F, Philadelphia ~50-74 F | our assumption (approximation of a sourced model; runs ~2-5 F low for PA) | Burch & Christensen (2007) and Maguire et al. (2013) as direct sources |
| `INLET_TEMP_SUMMER` | 65 F (outdoor >= 75 F) | :37 | as above | as above | our assumption (as above) | as above |
| `determine_inlet_temp` | linear from 45 F at 32 F outdoor to 65 F at 75 F outdoor (20 F over 43 F) | :102-112 | as above | as above | our assumption | Burch & Christensen (2007); Backman & Hoeschele (2013) |
| `ELECTRIC_HEATER_EFFICIENCY` | 0.92 | :43 | CFR 430.32(d), electric storage 20-55 gal, medium draw (manufactured before May 6, 2029) | "0.9307 − (0.0002 × Vr)" (= 0.9207 at 50 gal) | sourced (0.92 matches the federal minimum at 50 gal; Rheem's 0.90-0.93 range kept as context) | Rheem 2025, "UEF 0.90-0.93 ... Midpoint: 0.92" (0.915) |
| `TARGET_SHOWER_TEMP` | 105 F delivered | :44 | none; Zhang 2023 for context | Zhang 2023: "assumed to be 32-40 C" (89.6-104 F) | our assumption (delivery convention) | Zhang et al. (2023), "~98-105F" comfortable band |
| `WATER_DENSITY` | 8.33 lb/gal | :45 | physical constant | none | derived (standard property of water) | |
| `BTU_PER_KWH` | 3412 | :46 | unit conversion | none | derived (1 kWh = 3412 Btu) | |
| `calculate_hot_water_fraction` | f = (105 - T_in)/(T_heater - T_in), clamped [0, 1] | :134-141 | mixing energy balance (code cites Hendron & Burch 2008; Backman & Hoeschele 2013; Zhang 2023) | none | derived (energy balance of two streams) | |
| `calculate_shower_energy` | kWh = gpm x f x 8.33 x (T_heater - T_in) x minutes / (3412 x 0.92) | :114-132 | derived from the constants above | none | derived | |
| `calculate_environmental_impact` | gallons = gpm x minutes | :147-149 | project convention (CLAUDE.md: Shower environmental = water volume) | none | our assumption (metric choice) | |
| `COMFORT_DURATION_OPTIMAL` | 7.8 min | :52 | REU2016, p. 9 | "average duration held steady at 7.8 minutes" | sourced | |
| `COMFORT_TEMP_REFERENCE_F` | 77 F (no shift at or above) | :64 | none (comment: 25 C, the upper ASHRAE 55-2020 cooling comfort reference; not accessed) | none | our assumption | |
| `COMFORT_TEMP_ELASTICITY_PER_F` | +10% optimum per 10.8 F (6 C) below 77 F | :65 | none (Wong et al. 2022 cited in the comment for direction only) | none | our assumption | paper cited REU2016 for the season-dependent optimum (REU2016 has no seasonal data) |
| `COMFORT_TEMP_MAX_MULTIPLIER` | 11.6 / 8.8 = 1.318 | :66 | Ibanez-Rueda 2023 (945 Granada students, self-reported, summer/winter) | "average duration is 8.8 and 11.6 min" | sourced (cross-population extrapolation) | |
| `COMFORT_DURATION_MAX` | 15 min (ceiling of the comfort plateau) | :53 | Harris 2024, Q4 tabulation (supports the 33% share, not the ceiling) | "15 Minutes Or Less (Net) 66%", "More Than 15 (Net) 33%" | our assumption (ceiling), prevalence sourced | |
| `COMFORT_DURATION_MIN` | 5 min (practicality breakpoint) | :51 | none | none | our assumption | |
| `calculate_comfort_score`: duration curve | cubic 0 -> 4.0 up to 3 min; linear 4.0 -> 10.0 to the optimum; linear 10.0 -> 8.0 to 15 min; then -0.5/min, floor 1.0 | :169-185 | none (3 min called a "dermatologist minimum" in the comment; unsourced) | none | our assumption | |
| `calculate_comfort_score`: heater band | no penalty in [120, 140] F; -2.0 below 120 F; -1.0 above 140 F | :86-87, :187-191 | CDC (120 F is the circulation floor, 140 F the storage recommendation); penalty above 140 F is ours | "Store hot water at temperatures above 140°F (60°C)."; "Ensure hot water in circulation doesn't fall below 120°F (49°C)" | sourced (120 F and 140 F anchors); our assumption (penalty sizes and the >140 F penalty) | comment called 120 F a "standard delivery setpoint (CDC)" |
| `HEATER_TEMP_OPTIMAL` | 120 F | :72 | CDC | "Ensure hot water in circulation doesn't fall below 120°F (49°C)" | sourced (circulation floor, used as the band's lower edge) | "standard delivery setpoint (CDC (2026))" |
| `HEATER_TEMP_LEGIONELLA_SAFE` | 140 F | :74 | CDC | "Store hot water at temperatures above 140°F (60°C)." | sourced | |
| `HEATER_TEMP_MINIMUM` | 110 F (not used in scoring) | :71 | CDC growth range, for context | "Legionella grows best between 77°F–113°F (25°C–45°C)." | our assumption (unused constant) | |
| `HEATER_TEMP_SCALD_RISK` | 130 F (not used in scoring) | :73 | code cites Moritz & Henriques (1947); not checked by the audit | none | our assumption (unused constant; citation not verified) | |
| `calculate_comfort_score`: contention | 0.5 points per minute above the optimum, for >= 4 occupants | :195-197 | none | none | our assumption | |
| `calculate_practicality_score`: duration curve | 2.0 + 0.5(d - 3) to 5 min; 3.0 + (4/3)(d - 5) to 8; 7.0 + 0.5(d - 8) to 12; 9.0 - 0.5(d - 12) to 15; then 7.5 - 0.35(d - 15), floor 1.5 | :205-222 | none (hand-set; comments reference REU2016 and Harris 2024 for context only) | none | our assumption | |
| `calculate_practicality_score`: tank availability | usable hot water = 0.80 x tank size | :232 | none | none | our assumption | |
| `calculate_practicality_score`: capacity penalty | -3.0 if household hot-water need > available; clamp [0.15, 1.0] | :234-240 | none | none | our assumption | |
| `calculate_monthly_cost`: showers per person per day | 0.9 | :243, :450 | none | none | our assumption | "Q21: REU2016 average"; docstring credited DeOreo et al. (2016) |
| `calculate_monthly_cost`: days | 30 | :244 | none | none | derived (month length) | |
| `calculate_budget_penalty` | 1.0 below u = 0.80 (or no budget); 1 - 2.5(u - 0.8) for 0.80 <= u < 1.0; 0.5 e^(-3(u-1)) for every u >= 1.0 (continuous; no drop to 0) | :247-261 | Paper: "The values 0.80, 2.5 and 1.5 and the exponential form are our own choices." | "The values 0.80, 2.5 and 1.5 and the exponential form are our own choices." | our assumption (continuity above u = 1.5 is the author's decision of 2026-09-25; no Shower alternative exceeds u = 0.905, so no score changes) | shipped: 0 at u >= 1.5 |
| `apply_value_function`: energy_cost bounds | min $0.14, max $1.14 | :276-277 | 5th/95th percentile (numpy linear) of per-shower cost, 80 test + RAG scenarios pooled: p5 0.1449, p95 1.1354, rounded to cents | none (computed; recomputed unchanged in `Analysis/rerun_prep/hvac/reproduce.py`) | derived (scenario-set percentiles) | comment also credited DeOreo 2016, Burch & Christensen 2007, EIA 2025 |
| `apply_value_function`: environmental bounds | min 6.0, max 45.0 gal | :286-287 | 5th/95th percentile of gallons over the same pool: p5 6.00, p95 45.00 | none (computed) | derived (scenario-set percentiles) | |
| `apply_value_function`: practicality floor | min 0.05, max 1.0 | :301-302 | none (Keeney & Raiffa 1976 cited for convention only) | none | our assumption | |
| `apply_value_function`: comfort range | min 0.0, max 1.0 | :291-292 | none | none | derived (raw comfort is already on [0, 1]) | |
| `calculate_scenario_scores`: defaults | household 2, tank 40 gal, 2.5 gpm, outdoor 50 F, heater 120 F (only when a field is missing; the master sheet supplies all of them) | :366-370 | none | none | our assumption (fallbacks) | |
| Value function, energy cost (`VF_ENERGY_COST`) | linear, decreasing: u = (x_max - x)/(x_max - x_min), clamped [0, 1] | :91, :316-324 | code cites Dyer & Sarin (1979), *Oper. Res.* 27(4):810-822 | code comment (not re-verified): "For monetary attributes with small stakes relative to wealth, linear utility is appropriate" | sourced (quote not re-verified) | |
| Value function, environmental (`VF_ENVIRONMENTAL`) | linear, decreasing, as above (gallons) | :98, :316-324 | code cites Keeney & Raiffa (1976) for MAVT; linearity is a modelling choice | none | our assumption | |
| Value function, comfort (`VF_COMFORT`) | logarithmic, u = ln(1.5 x + 1)/ln(2.5), increasing, clamped | :99, :345-358 | none | none | our assumption (a = 1.5) | |
| Value function, practicality (`VF_PRACTICALITY`) | logarithmic, u = ln(1.2 x + 1)/ln(2.2), increasing, clamped | :100, :345-358 | none | none | our assumption (a = 1.2) | |
