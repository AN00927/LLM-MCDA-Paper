# HVAC solar gain term: value review

Scope: `Ground Truth Calculators/HVACGroundTruthCalculator.py`, `calculate_net_heat_gain`
(L127-130): `window_area = square_footage * 0.15` and `solar_gains = window_area * 20`
Btu/h, credited in both heat mode and AC mode (author decision 2026-09-27). Review date
2026-09-27. Read-only: no repo code or data was changed. The installed
`Ground Truth/ground_truth_hvac.xlsx` was first reproduced exactly by the installed
calculator (0 mismatching cells), and the scratch variant with q = 20 in both modes and
the installed bounds reproduces it exactly too (the gate in the impact run).

## 1. Summary

- Recommended replacement: q_solar [Btu/h] = A_glass x SHGC x IAC x I_avg, with
  A_glass = 0.15 x floor area (unchanged), SHGC = 0.40 and interior shade fraction
  IAC = 0.92 - 0.21 x 0.40 = 0.836, both from the IECC 2018 R405 standard reference design
  (Table R405.5.2(1), the same table that already supplies the 15% glazing area), and
  I_avg = the 24-hour mean irradiance on the four cardinal vertical orientations, Harrisburg
  Intl AP TMY3, isotropic sky, ground reflectance 0.2.
- Values: heat mode I_avg = 74.0 W/m2 = 23.5 Btu/(h ft2), q = 7.85 Btu/h per ft2 of glass
  (1.18 per ft2 of floor); AC mode I_avg = 105.5 W/m2 = 33.4 Btu/(h ft2), q = 11.19 Btu/h
  per ft2 of glass (1.68 per ft2 of floor). The current 20 per ft2 of glass (3.0 per ft2 of
  floor) is 2.5x (heat) and 1.8x (AC) the recommended values; it matches almost exactly the
  DAYTIME 8-h heating-season value (20.4), so it behaves like a daytime figure applied to
  every hour of the day.
- The 20 Btu/h/ft2 has no source; it is replaced, not confirmed. The 0.15 glazing fraction
  is confirmed verbatim in IECC 2018 R405.5.2(1).
- Impact (recomputed own bounds, vs the installed GT): recommended option changes 7/70 test
  and 2/35 RAG winners (13/70 and 2/35 full rankings); new cost bounds $0.36 / $2.82
  (installed $0.19 / $3.21), Environmental 1.85 / 15.45 lbs (installed 0.97 / 17.59).
  Daytime-8h alternative: 2/70 test and 2/35 RAG winners, bounds $0.22 / $3.44.
- Decision points for the author: (a) 24-h mean (recommended) vs daytime 8-h vs
  occupancy-aware irradiance; (b) IECC 2018 (code, recommended) vs Building America HSP
  (SHGC 0.35 or 0.44 with multiplier 0.7) for SHGC x IAC; (c) season definition by the
  scenario temperature ranges (recommended) vs the HSP monthly-average-temperature rule
  (8% higher heat-mode value, identical AC value); (d) one statewide station (Harrisburg)
  vs per-location stations (Philadelphia and Pittsburgh differ by at most 10%).

## 2. Constants

| Constant | Code value | Source value | Verbatim quote | Page / URL | Verdict | Proposed change |
|---|---|---|---|---|---|---|
| Glazing area | 0.15 x floor area (L129) | 15% of conditioned floor area | "Total area h = The proposed glazing area, where the proposed glazing area is less than 15 percent of the conditioned floor area 15 percent of the conditioned floor area , where the proposed glazing area is 15 percent or more of the conditioned floor area ." | IECC 2018 (Pennsylvania edition on UpCodes), Table R405.5.2(1), "Vertical fenestration other than opaque doors", standard reference design column. https://up.codes/viewer/pennsylvania/iecc-2018/chapter/RE_4/re-residential-energy-efficiency | confirmed | none; record table number R405.5.2(1) and URL in CALCULATOR_PROVENANCE row 41 |
| Glazing area (HSP, for contrast) | n/a | 15% of exterior wall area, not floor area | "AF, Liv = 0.15 × AExWa, Liv (1)" ... "AExWa,Liv = total exterior wall area of above-grade living space on a specific floor (ft2)" | Hendron & Engebrecht (2010) HSP, NREL/TP-550-49426, p. 4 (PDF p. 12), Eq. 1. https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/house_simulation_revised.pdf | note only | do not cite HSP for the 0.15 floor-area rule; IECC is the right source |
| Window orientation | implicit (none) | equal on N, E, S, W | "Orientation: equally distributed to four cardinal compass orientations (N, E, S & W)." | IECC 2018 Table R405.5.2(1), same URL | confirmed as the averaging rule | average I over N, E, S, W |
| Window orientation (HSP) | n/a | equal on four walls (Option 2) | "Option 2: The window area is distributed equally on each of the four walls (including attached walls), and the orientation of the Benchmark is the same as the NCTH." | HSP 2010 p. 5 (PDF p. 13). The 2012 Addendum keeps Option 2 with a fixed north-facing front door: "The latest version of BEopt will use option 2 with a fixed orientation" (Engebrecht Metzger, Wilson & Horowitz 2012, DOE/GO-102012-3855, p. 4, Modification 1.1.4, https://www.osti.gov/servlets/purl/1060599) | confirmed (agrees with IECC) | same |
| SHGC | none (folded into 20) | 0.40 (IECC 2018 reference design, PA climate zones 4A and 5A) | "SHGC: as specified in Table R402.1.2 except for climate zones without an SHGC requirement, the SHGC shall be equal to 0.40." Table R402.1.2 row "4 except Marine 0.32 0.55 0.40 ..." and row "5 and Marine 4 0.30 0.55 NR ..." | IECC 2018 Tables R405.5.2(1) and R402.1.2, same URL | replacement proposed | SHGC = 0.40 |
| SHGC (HSP 2010) | n/a | 0.35 (zones 4 and 5) | "Table 3. Fenestration Assembly Characteristics ... 4 except Marine 0.35 0.35 / 5 and Marine 4 0.35 0.35" (U, SHGC) | HSP 2010 p. 7 (PDF p. 15), Table 3 | alternative (sensitivity S2) | not recommended; superseded |
| SHGC (HSP Addendum 2012 and HSP 2014) | n/a | 0.44 (zones 4 to 8) | Addendum: "Table 3. Fenestration Assembly Characteristics ... 4 to 8 0.35 0.44" (p. 6, Modification 1.9). HSP 2014: "Table 4. Fenestration Assembly Characteristics ... 4 to 8 0.35 0.44" | Addendum DOE/GO-102012-3855 p. 6; Wilson, Engebrecht Metzger, Horowitz & Hendron (2014), 2014 Building America House Simulation Protocols, NREL/TP-5500-60988, p. 10 (PDF p. 19), https://www.osti.gov/servlets/purl/1126820 | alternative (sensitivity S3) | not recommended |
| Interior shading, IECC | none | 0.92 - 0.21 x SHGC = 0.836, no seasonal split | "Interior shade fraction: 0.92-(0.21 × SHGC for the standard reference design )." | IECC 2018 Table R405.5.2(1), same URL | replacement proposed | IAC = 0.836 in both modes |
| Interior shading, HSP 2010 | none | 0.7, single value | "Interior shading multiplier = 0.7" | HSP 2010 p. 50 (PDF p. 58), Operating Conditions | confirms a year-round multiplier (heating = cooling = 0.7) | cross-check only |
| Interior shading, HSP 2014 | none | 0.7 year-round | Table 1: "Int. shading All 0.7 multiplier on SHGC[a], year-round p. 49" ([a] is a footnote marker); Sec. 4.2.2: "Solar gains through windows shall be modified by a constant interior shading multiplier of 0.7, meaning that all solar gains are reduced by 30% through use of blinds, shades, or curtains." | HSP 2014 p. 5 (PDF p. 14) and p. 49 (PDF p. 58) | confirms 0.7 heating and 0.7 cooling | cross-check only |
| Interior shading, RESNET 301 via ResStock | none | summer 0.7, winter 0.85 | "Summer = 0.7, Winter = 0.85 0.85 0.7" (Table 75, window_interior_shading_winter / _summer); data source "ANSI/RESNET/ICC 301 Standard." | NREL ResStock Technical Reference Documentation v3.3.0, NREL/TP-5500-91621, p. 93 (PDF p. 102), Table 75. https://www.osti.gov/servlets/purl/2583488 | seasonal alternative, noted | not used (IECC is the code source and has no split). With it, heat q would be 0.40 x 0.85 x 23.5 = 7.98 and AC q = 0.40 x 0.70 x 33.4 = 9.36 |
| Solar gain per ft2 glass | 20 Btu/(h ft2) both modes (L130) | heat 7.85, AC 11.19 (recommended); see Section 4 for alternatives | computed: SHGC x IAC x I_avg with I_avg from TMY3 (Section 3) | TMY3 EPW, https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/PA_Pennsylvania/USA_PA_Harrisburg.Intl.AP.723990_TMY3.zip | mismatch (20 unsourced) / replacement proposed | `solar_gains = window_area * (7.85 if heat else 11.19)`, or better, store SHGC, IAC and the two irradiances as named constants |
| Solar in both modes (method) | include_solar=True in heat and AC | energy-estimating methods credit solar and internal gains; design-load (Manual J) heating sizing does not | see Section 3.5 | see Section 3.5 | author decision supported by a primary source | keep; cite SERI (1983) for the balance-point method and DOE (2024) for the Manual J contrast |

Unit conversion used throughout: 1 Btu/(h ft2) = 3.15459 W/m2.

## 3. Irradiance computation method

### 3.1 Data

- TMY3 EPW files from climate.onebuilding.org (header: "NREL TMY Data Set (2008) updated
  2015 to include better precipitation; Period of Record 1973-2005 (Generally)"):
  - `USA_PA_Harrisburg.Intl.AP.723990_TMY3.epw` (primary; lat 40.20, lon -76.767, TZ -5),
    sha256 a6e633a5ef4adb3a16fd92c45f5f0944c6109e502ac83cfba9bc7f66788fddff
  - `USA_PA_Philadelphia.Intl.AP.724080_TMY3.epw`, sha256 70a634cb...fc44bfc6b3d
  - `USA_PA_Pittsburgh.Intl.AP.725200_TMY3.epw`, sha256 9299e648...4912ba7a57
- Cross-check: NASA POWER climatology API (2001-2020), parameters ALLSKY_SFC_SW_DWN and
  SI_EF_TILTED_SURFACE (vertical equator-facing surface),
  `https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,SI_EF_TILTED_SURFACE&community=RE&longitude=-76.767&latitude=40.2&format=JSON`
  (and the Philadelphia and Pittsburgh airport coordinates).
- Script: `paper/pass6/verify/value_review/solar_irradiance.py` (copy of the scratchpad
  script; standard library + numpy; downloads the EPW files if missing). Run:
  `.venv/bin/python paper/pass6/verify/value_review/solar_irradiance.py --epw-dir <dir> --json out.json`.

### 3.2 Formulas

- EPW columns: month, day, hour (1-24, hour ending, local standard time), dry bulb (C),
  GHI, DNI, DHI (Wh/m2 over the hour, i.e. mean W/m2).
- Sun position at mid-hour (hour - 0.5 LST). Declination and equation of time by the Spencer
  (1971) Fourier series; solar time = LST + [4 min/deg x (lon - 15 x TZ) + EoT]/60;
  hour angle 15 deg/h from solar noon; altitude and azimuth by the standard spherical
  relations (azimuth clockwise from north).
- Vertical surface of azimuth psi (N 0, E 90, S 180, W 270), isotropic sky:
  I = DNI x max(0, cos(alt) x cos(az - psi)) [beam, 0 with the sun below the horizon]
  + DHI x (1 + cos 90)/2 = DHI/2 [sky diffuse] + GHI x 0.2 x (1 - cos 90)/2 = 0.1 x GHI
  [ground reflected, rho = 0.2].
- Window irradiance = mean of N, E, S and W (IECC equal distribution, Section 2).
- SHGC is applied to total incident irradiance at its normal-incidence value. Angular
  dependence of SHGC and frame effects are not modelled; both would lower q somewhat, so
  the proposed values lean high rather than low.

### 3.3 Season definitions (both computed)

- BIN (recommended, tied to the scenarios): each TMY3 hour whose dry bulb lies in the
  mode's scenario outdoor range (heat-mode questions 5-62 F, AC-mode questions 68-102 F, the
  full ranges in `Scenario Files/HVACScenarios.xlsx`) adds one unit of weight to its month.
  The season value is the weighted mean of the monthly window means, so the averaging
  window (24 h or daytime) keeps its own definition. Harrisburg weights, Jan..Dec:
  heat 660, 672, 725, 527, 472, 90, 0, 40, 284, 578, 687, 744; AC 0, 0, 4, 110, 154, 509,
  693, 560, 311, 70, 10, 0.
- HSP (primary-sourced alternative): Building America HSP 2010 p. 49: "The heating system
  shall be enabled for a month in which the MAT is less than 66°F. The cooling system shall
  be enabled for a month in which the MAT is greater than 66°F.", plus Step 2 (heating in
  December and January when the winter design temperature <= 59 F; cooling in July and
  August), Step 3 (swing-month adjustment) and "One month shall be added to the start of
  the cooling season" (p. 50). Harrisburg TMY3 gives heating months Jan-Jun and Sep-Dec,
  cooling May-Sep (May, June and September are in both after Steps 3 and the added month).
  The overlap is why BIN is preferred: it assigns months by how often the scenario
  temperatures actually occur.

### 3.4 Averaging window (scenarios carry no time of day)

- 24-h mean (recommended). The calculator treats the 8-h energy window as a generic period:
  `calculate_monthly_cost` multiplies the per-period cost by 90 periods per month, "holding
  this setpoint across all three 8h periods per day, every day" (L694-695). For the monthly
  budget proxy to be a month of energy, the per-period solar gain must be the average over
  all 24 hours of the day; a daytime value would be credited three times a day. The
  balance-point method (Section 3.5) is also written in "average hourly utilizable solar
  gains". The same reasoning is behind the scenario's single outdoor temperature entering
  every period unchanged.
- Daytime 8-h mean (08:00-16:00 LST, EPW hours ending 9-16, roughly centred on solar noon,
  which is about 12:10 LST at Harrisburg): appropriate only if each scenario is read as one
  daytime block. It conflicts with the x90 monthly cost and with occupied_sleep.
- Occupancy-aware (design choice for the author, not recommended as the default):
  occupied_all_day 24-h mean; occupied_sleep night window 23:00-07:00 LST (the PJM
  off-peak window the calculator already assigns to occupied_sleep in
  `emissions_factor_for_occupancy`); unoccupied_H daytime 08:00-16:00 (the calculator
  already puts the away hours in the PJM peak window). This is consistent with the emission
  factor logic, but it gives the 13 sleep scenarios (10 heat, 3 AC) almost no solar gain
  while their monthly cost is still multiplied by 90 periods.
- Temperature-coincident hours (diagnostic): the mean over exactly the TMY3 hours in the
  scenario temperature range, with no clock window. For AC this picks the hot, sunny
  afternoon hours (138 W/m2 vs 105.5 for the 24-h mean). It pairs solar with the scenario's
  temperature more literally, and it is reported as variant C in Section 4.

### 3.5 Why solar counts in heat mode: primary statements

- Balance-point (variable-base degree-day) energy method: "Td is defined as the outdoor
  temperature above which heating is not required on the average, because heat losses are
  balanced by internal and solar gains. Td can be calculated as: Tb = Tset - (I + S)/UA
  [5] ... I = average hourly utilizable internal gains S = average hourly utilizable solar
  gains." (The minus sign in Eq. 5 is garbled in the scanned text layer.) Christensen, C. and Wortman, D. (1983). Solar and Internal Gain Adjustments in
  Calculation of Energy Conservation Savings. SERI/TP-254-2019 (Solar Energy Research
  Institute, now NREL), Section 3, PDF p. 4, citing ASHRAE Handbook 1981 Fundamentals
  pp. 28.2-28.4. https://www.osti.gov/servlets/purl/5344868
- Manual J design heating load: "The Manual J methodology relies on the bulk heat transfer
  calculation U x Area x Delta T to determine annual heating needs, disregarding heat gains
  from internal sources or solar radiance." (The formula is garbled in the PDF text layer;
  the words are verbatim.) U.S. DOE Building Technologies Office (2024). Design Heating
  and Cooling Load Calculation Versus Building Load Simulation for Cold Climate Heat
  Pumps: Understanding the "Gap". Prepared by Grimes-Casey, Thomas and Masi-Perkins
  (Performance Systems Development), NREL technical monitor; DOE/GO-102024-6351,
  NREL/TP-5500-90544 (OSTI), p. 1, Section 1.1. https://www.osti.gov/servlets/purl/2479124
  The same report (p. 10): "solar and internal gains offset other heating losses ... during
  a January peak heating day (10 a.m. to 4 p.m. local time) to reduce the net heating load".
- Simulation protocol: both HSP editions apply the 0.7 shading multiplier to solar gains all
  year ("year-round"), i.e. the Building America energy benchmark credits window solar
  gain in the heating season.
- Not opened: ASHRAE Handbook of Fundamentals, Ch. 19 (Energy Estimating and Modeling
  Methods), and ACCA Manual J itself (both paywalled; no attempt to fetch). The SERI paper
  is the citable primary statement of the balance-point method and points to the ASHRAE
  handbook pages it came from.

### 3.6 Results (W/m2, mean of N, E, S, W)

| Station | Window | HSP heat | HSP cool | BIN heat | BIN cool | Annual |
|---|---|---|---|---|---|---|
| Harrisburg | 24 h | 80.2 | 105.6 | **74.0** | **105.5** | 84.7 |
| Harrisburg | day 08-16 | 202.6 | 244.0 | 192.8 | 244.2 | 210.4 |
| Harrisburg | night 23-07 | 5.5 | 14.2 | 3.3 | 13.9 | 6.9 |
| Philadelphia | 24 h | 87.2 | 108.2 | 81.3 | 111.9 | 92.8 |
| Philadelphia | day 08-16 | 220.0 | 254.1 | 212.2 | 258.2 | 229.6 |
| Pittsburgh | 24 h | 80.7 | 110.7 | 75.7 | 112.4 | 87.1 |
| Pittsburgh | day 08-16 | 202.7 | 252.0 | 194.8 | 255.6 | 214.0 |

Temperature-coincident hours (Harrisburg): heat 62.1, AC 138.1 W/m2.

Cross-check against NASA POWER (south-facing vertical, annual mean kWh/m2/day): Harrisburg
TMY3 model 2.60 vs POWER 2.76; Philadelphia 2.96 vs 2.88; Pittsburgh 2.58 vs 2.56. GHI:
Harrisburg 3.64 vs 3.86, Philadelphia 4.02 vs 4.07, Pittsburgh 3.81 vs 3.76. Agreement is
within 6% annually; monthly differences are larger in winter (Harrisburg January 2.14 vs
2.70), which reflects the TMY3 month selection and POWER's own tilted-surface model.

### 3.7 Proposed q values (Btu/h per ft2 of glass; per ft2 of floor = x 0.15)

| Option | SHGC x IAC | Heat mode | AC mode | Heat per ft2 floor | AC per ft2 floor |
|---|---|---|---|---|---|
| Current code | n/a | 20.00 | 20.00 | 3.00 | 3.00 |
| R: IECC, BIN, 24 h (recommended) | 0.3344 | 7.85 | 11.19 | 1.18 | 1.68 |
| D: IECC, BIN, daytime 8 h | 0.3344 | 20.43 | 25.89 | 3.07 | 3.88 |
| O: occupancy-aware, sleep (night) | 0.3344 | 0.35 | 1.47 | 0.05 | 0.22 |
| C: IECC, coincident hours | 0.3344 | 6.58 | 14.64 | 0.99 | 2.20 |
| S1: IECC, HSP season, 24 h | 0.3344 | 8.50 | 11.19 | 1.28 | 1.68 |
| S2: HSP 2010 (0.35 x 0.7), 24 h | 0.245 | 5.75 | 8.20 | 0.86 | 1.23 |
| S3: HSP 2014 (0.44 x 0.7), 24 h | 0.308 | 7.23 | 10.30 | 1.08 | 1.55 |
| S4: IECC, Philadelphia, 24 h | 0.3344 | 8.61 | 11.86 | 1.29 | 1.78 |
| S5: IECC, Pittsburgh, 24 h | 0.3344 | 8.02 | 11.91 | 1.20 | 1.79 |

For scale, a 1,760 ft2 house (the scenario mean) now gets 5,280 Btu/h of solar gain in both
modes; option R gives 2,072 Btu/h (heat) and 2,954 Btu/h (AC), against 3,220 Btu/h of
internal gains for a 3-person household.

## 4. Impact on the 105 master scenarios (70 test / 35 RAG)

Method: scratch copy of the installed calculator
(`HVACGroundTruthCalculator_scratch.py`, byte-identical, sha256 4199ac1e...0f985d) with a
subclass that replaces only the solar term by mode (and, for option O, by occupancy) and
swaps the linear cost and Environmental bounds; run through
`Analysis/rerun_prep/hvac/common.py:run_hvac` into a temp file. Bounds are recomputed with
`common.cost_percentile_bounds` (p5 / p95 of the nonzero cent-rounded raw_cost, pooled over
the 105 scenarios; Environmental = kWh at p5 x 0.976 and kWh at p95 x 1.041). Rankings are
compared with the installed `Ground Truth/ground_truth_hvac.xlsx` via
`common.ranking_changes` (RAG split by `common.rag_signatures`). "Old bounds" = installed
$0.19 / $3.21 and 0.97 / 17.59; "own bounds" = recomputed for the variant.

| Option | Own bounds cost ($) | Own bounds env (lbs) | Active alts (of 315) | Test winners (old / own bounds) | Test full rankings (old / own) | RAG winners (old / own) | RAG full (old / own) |
|---|---|---|---|---|---|---|---|
| Installed | 0.19 / 3.21 | 0.97 / 17.59 | 280 | n/a | n/a | n/a | n/a |
| R (recommended) | 0.36 / 2.82 | 1.85 / 15.45 | 301 | 6 / 7 | 9 / 13 | 0 / 2 | 1 / 2 |
| D daytime 8 h | 0.22 / 3.44 | 1.10 / 18.83 | 279 | 2 / 2 | 2 / 2 | 0 / 2 | 0 / 2 |
| O occupancy-aware | 0.28 / 2.82 | 1.44 / 15.46 | 299 | 5 / 5 | 7 / 11 | 0 / 1 | 1 / 1 |
| C coincident hours | 0.42 / 2.97 | 2.16 / 16.27 | 301 | 4 / 5 | 7 / 11 | 1 / 2 | 1 / 2 |
| S1 HSP season | 0.36 / 2.81 | 1.85 / 15.40 | 300 | 6 / 7 | 9 / 13 | 1 / 3 | 2 / 3 |
| S2 HSP 2010 | 0.39 / 2.70 | 2.00 / 14.78 | 302 | 5 / 8 | 8 / 15 | 2 / 3 | 2 / 4 |
| S3 HSP 2014 | 0.39 / 2.77 | 2.00 / 15.18 | 301 | 6 / 8 | 9 / 14 | 0 / 3 | 1 / 3 |
| S4 Philadelphia | 0.35 / 2.84 | 1.80 / 15.57 | 300 | 6 / 7 | 9 / 13 | 0 / 3 | 1 / 3 |
| S5 Pittsburgh | 0.37 / 2.84 | 1.90 / 15.56 | 301 | 7 / 8 | 10 / 14 | 0 / 3 | 1 / 3 |
| S6 no solar (bound) | 0.32 / 2.77 | 1.66 / 15.19 | 306 | 9 / 10 | 13 / 17 | 2 / 5 | 2 / 5 |

Unrounded p5 / p95 for R: $0.3600 / $2.8200; for D: $0.2150 / $3.4360.

Winner changes, own bounds (scenario_id, mode, installed winner -> new winner):

- R: 11 heat 72 -> 69; 21 heat 71 -> 68; 25 heat 68 -> 65 (RAG); 39 AC 78 -> 80;
  49 heat 72 -> 68; 55 heat 70 -> 65; 56 AC Off -> 78; 59 heat 72 -> 68; 64 heat 71 -> 68
  (RAG). Seven of nine are heat mode: less solar credit raises the heating cost of the
  warmer setpoints, so the winner moves down 3-5 F. Zero-load alternatives fall from 35 to
  14, because less solar gain means fewer setpoints where the heat balance already needs no
  heating.
- D: 25 heat 68 -> 71 (RAG); 27 heat 66 -> 69 (RAG); 67 AC 82 -> 78; 69 heat 69 -> 72.
  D is close to the installed model because the installed 20 is close to the daytime
  heating-season value.
- O: 21 heat 71 -> 68; 25 heat 68 -> 65 (RAG); 39 AC 78 -> 82; 49 heat 72 -> 68;
  57 AC 78 -> Off; 59 heat 72 -> 68.

With recomputed bounds, RAG winners change in 1-5 scenarios under every option, so the
refresh workflow in CLAUDE.md applies (calculator, `sync_rag_ground_truth_scores.py`, then
`build_rag_index.py`) and the `apply_value_function` bound comments and
CALCULATOR_PROVENANCE row 70 need the new percentiles. The Environmental bounds move with
the cost bounds by construction.

## 5. Hosts

- Worked: www1.eere.energy.gov (HSP 2010 PDF), www.osti.gov (API and purl PDFs: HSP 2014,
  2012 Addendum, ResStock v3.3.0 documentation, DOE 2024 "Gap" report, SERI 1983),
  up.codes (Pennsylvania IECC 2018 chapter RE 4), climate.onebuilding.org (TMY3 EPW),
  power.larc.nasa.gov (POWER climatology API).
- Not found (HTTP 404, not a block): up.codes `/viewer/general/iecc-2018/...` and
  `/viewer/general/iecc-2021/...`; the Pennsylvania path worked.
- Not attempted because stated blocked: nrel.gov (all subdomains), codes.iccsafe.org,
  web.archive.org, sciencedirect, github.com. No host returned a proxy block during this
  review.
- Not opened (paywalled, not attempted): ASHRAE Handbook of Fundamentals Ch. 19; ACCA
  Manual J.
- The FY13 addendum number given in the brief (NREL/TP-5500-57450) did not come up in the
  OSTI search for "House Simulation Protocols"; the addenda found were the December 2012
  Addendum (DOE/GO-102012-3855) and the 2014 HSP (NREL/TP-5500-60988), both read above.
