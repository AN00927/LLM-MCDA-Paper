# Value review of every calculator and baseline constant (2026-09-27)

Scope: every row of `docs/CALCULATOR_PROVENANCE.md` (HVAC, Appliance, Shower, Baselines), checked
against the installed code and the primary source, per `paper/pass6/NEXT_SESSION_HANDOFF.md`
section 2. Five Opus reviews; their full tables follow this summary unchanged (sections 1-5). No
calculator, data or ground-truth file was changed. Every impact figure below comes from patched
copies of the calculators in the session scratchpad.

Network: all `*.nrel.gov` hosts (docs, www, NSRDB, PVWatts), web.archive.org, sciencedirect.com,
github.com (HTML), eta-publications.lbl.gov and codes.iccsafe.org were unreachable. NREL reports
were read from eere.energy.gov and osti.gov mirrors, IECC from up.codes (Pennsylvania edition),
TMY3 weather from climate.onebuilding.org.

## Verdict counts

| Review | Rows | Confirmed | Mismatch | Assumption kept | Replacement proposed |
|---|---|---|---|---|---|
| HVAC solar gain | 2 + inputs | see section 1 | | | 1 |
| HVAC (other rows) | 49 | 24 | 4 | 16 | 5 |
| Appliance | 90 | 51 | 4 | 29 | 6 |
| Shower | 39 | 17 | 1 | 19 | 2 |
| Baselines | 38 | 7 | 21 (14 are line numbers only) | 8 | 2 |

Every tariff, PJM, cycle-count and bound value in the Appliance code matches its source. No
mismatch found is a wrong number in a calculator; the mismatches are in the provenance record
(line numbers, a swapped weights row, stale quotes, a stale paper sentence).

## Decisions for the author

### A. Changes that move the ground truth (need approval; each triggers the CLAUDE.md refresh order)

| # | Change | Source | Impact (vs installed ground truth) |
|---|---|---|---|
| A1 | **HVAC solar gain**: replace `window_area * 20` with A_glass x SHGC x IAC x I_avg. SHGC 0.40 and interior shading 0.92 - 0.21 x SHGC = 0.836 (IECC 2018 PA, Table R405.5.2(1), the same table as the 15% glazing); I_avg = 24-h mean incident irradiance on the four cardinal vertical faces, Harrisburg Intl TMY3, weighted by the hours in each mode's scenario temperature range. Heat mode 7.85, AC mode 11.19 Btu/h per ft2 of glass (now 20 in both). | IECC R405; TMY3; SERI/NREL 1983 balance-point definition (solar credited in heat mode); DOE 2024 on Manual J omitting solar for sizing | Test 7/70 winners, 13/70 rankings; RAG 2/35 winners; cost bounds $0.36-$2.82, env 1.85-15.45 lbs |
| A1-alt | Same formula with a daytime 8-h mean (20.4 / 25.9 per ft2 glass) | as A1 | Test 2/70 winners; RAG 2/35; bounds $0.22-$3.44, 1.10-18.83 |
| A1-alt2 | Occupancy-aware (no solar for `occupied_sleep`) | as A1 | Test 5/70 winners, 11 rankings; RAG 1/35; bounds $0.28-$2.82 |
| A2 | **HVAC internal gains**: `BASE_INTERNAL_GAIN_BTUH` 800 -> 746, `EQUIPMENT_GAIN_BTUH_PER_SQFT` 1.0 -> 0.99 (IECC 2018 R405 IGain = 17,900 + 23.8 x CFA + 4,104 x Nbr Btu/day, / 24; occupant term stays 220 Btu/h per person) | IECC 2018 Table R405.5.2(1) | 2/105 winners; cost floor $0.19 -> $0.20 |
| A3 | **HVAC efficiency degradation**: replace the 0.5/1.0/1.5 %/yr schedule and 30% cap with HSP Eq. 20, 1 - (1 - M)^min(age, 20); M = 0.01 / 0.03 from HSP Table 32, 0.02 for "moderate" is our midpoint | HSP 2010 Eq. 20, Table 32 | No ranking changes (all alternatives share one unit age); practicality of old units moves |
| A4 | **HVAC glazing for attached units**: IECC reduces the 15% glazing by a factor F (>= 0.56) for townhouses and apartment units; the code applies 15% to all 58 attached-type scenarios | IECC 2018 Table R405.5.2(1) | Not estimated; interacts with A1 |
| A5 | **Shower inlet temperature**: anchors 45/65 F -> 48.5/68.2 F (same linear form and 32/75 F breakpoints; least-squares fit to the Burch & Christensen / HSP Eq. 26 mains model on 6 PA TMY3 stations; RMS error 3.6 F vs 4.8 F now) | HSP 2010 Eq. 26; TMY3 | 1/80 winners, 2/80 rankings; cost bounds $0.14-$1.14 -> $0.13-$1.07 |
| A6 | **Shower showers/person/day** 0.9 -> 0.69 (L243 and L450) | REU2016 via Gauley & Koeller 2017; HSP 2014 event table implies 0.64 | No score changes on current data |
| A7 | **Fixed-default tank** 50 -> 40 gal | RECS 2020 PA median band 31-49 gal; master-sheet mode | Shower FD Top-1 0.850 -> 0.833 |
| A8 | **Fixed-default dryer** 2.10 -> 2.27 kWh/cycle (DOE test load 8.45 lb / 2015 minimum CEF 3.73) | 10 CFR 430.32 | Appliance FD Top-1 unchanged |

Options reviewed and not proposed (the numbers stay as they are): the envelope multipliers
(Apartment/Condo 1.2 is a top-floor value; 0.5 for a mid-floor unit would change 2/105), the
PJM seasonal Dec-May factors (992.8 / 985.7; 3/100 Appliance winners; CLAUDE.md fixes the annual
factors), Monroeville to Duquesne (split territory; 0/100 winners), the WHO 23:00-07:00 night
(1/100 winners).

### B. Other questions for the author

1. For A1, which irradiance average (24-h recommended; daytime; occupancy-aware), which SHGC
   source (IECC recommended; HSP 0.35/0.44 with IAC 0.7), which season rule (scenario
   temperature ranges; HSP monthly rule moves heat 7.85 -> 8.50), one station (Harrisburg) or
   one per scenario location.
2. For A3, is M = 0.02 for "moderate" maintenance acceptable as our midpoint.

### C. Record-only fixes (no ground-truth change; to apply together with the approved changes)

- `docs/CALCULATOR_PROVENANCE.md`: Appliance weights row has energy/environmental swapped
  (code: energy 0.30, environmental 0.35); line-number drift in HVAC (mode resolution :540-551,
  load cap :603-606, seven rows off by one), Appliance (`calculate_environmental_impact`
  :201-205) and every HAB citation in Baselines (corrected list in section 5); Random and
  Uniform are reachable from the CLI (`--baseline random|uniform`); the NN prediction has an
  undocumented fallback option; the quoted HVAC rate comment no longer exists.
- New or corrected quotes: PJM 2022 p. 3 (1,041 / 976; peak window); IECC glazing 15%; HSP
  rows; Persily 0.35 ACH (a ventilation minimum, not an infiltration rate; the code comment at
  :35 still credits ACCA Manual J).
- Re-citations: `ELECTRICITY_RATE_PA` 0.19 to EIA 2025 PA residential 19.30 c/kWh (Electric
  Power Monthly, Feb 2026, Table 5.6.B), because the PA PUC default-service derivation gives
  0.179, not 0.19; ceiling height 8 ft to ResStock v3.2.0 (status sourced); 27 unchecked
  cities to the utilities' territory lists (status sourced, Monroeville stays split); 45 dBA
  threshold to WHO 1999 (45 dB LAmax single events, bedrooms; the code's "WHO night limit
  35 dBA" comment is wrong); appliance noise to EU label regulations 2019/2017, 2019/2014,
  2023/2534 (sound power, not pressure: caveat); 10 p.m.-7 a.m. window to 24 CFR 51.103 /
  14 CFR 150.7 and Pittsburgh Code 601.04; washer cycles to DOE Appendix J2 (295); 105 F
  delivered shower temperature to ANSI 301-2019 via LBNL (Chen et al. 2020); SEER 13 to the
  2015-2022 federal minimum; 2.5 gpm to the federal showerhead maximum.
- Paper (S-CALC, B29): the budget-penalty sentence still names the removed 1.5 cutoff and omits
  the 0.5 scale and exponent 3.
- Baselines: the 11 unused constants are confirmed unread anywhere (removal is handoff
  section 3 item 3).

### D. Not opened

ASHRAE Fundamentals (Ch. 18, 19) and ASHRAE 55, ACCA Manual J (paywalled); Dyer & Sarin 1979
(403); the Harris Poll page (403); Ibanez-Rueda full text; Moritz & Henriques 1947; LINEAR /
Smart-A reports; Pittsburgh's ecode360 (403; a 2015 print was used); quakertown.org (403). The
only REU2016 copy found is hosted by Circle of Blue (a news nonprofit).


---

## 1. HVAC solar gain term: value review (`value_review/HVAC_SOLAR.md`)

Scope: `Ground Truth Calculators/HVACGroundTruthCalculator.py`, `calculate_net_heat_gain`
(L127-130): `window_area = square_footage * 0.15` and `solar_gains = window_area * 20`
Btu/h, credited in both heat mode and AC mode (author decision 2026-09-27). Review date
2026-09-27. Read-only: no repo code or data was changed. The installed
`Ground Truth/ground_truth_hvac.xlsx` was first reproduced exactly by the installed
calculator (0 mismatching cells), and the scratch variant with q = 20 in both modes and
the installed bounds reproduces it exactly too (the gate in the impact run).

### 1. Summary

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

### 2. Constants

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

### 3. Irradiance computation method

#### 3.1 Data

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

#### 3.2 Formulas

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

#### 3.3 Season definitions (both computed)

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

#### 3.4 Averaging window (scenarios carry no time of day)

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

#### 3.5 Why solar counts in heat mode: primary statements

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

#### 3.6 Results (W/m2, mean of N, E, S, W)

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

#### 3.7 Proposed q values (Btu/h per ft2 of glass; per ft2 of floor = x 0.15)

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

### 4. Impact on the 105 master scenarios (70 test / 35 RAG)

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

### 5. Hosts

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

---

## 2. HVAC constant value review (`value_review/HVAC.md`)

Scope: every row of the HVAC section of `docs/CALCULATOR_PROVENANCE.md` (lines 29-106) except the two
solar-gain rows (solar gain per ft2 of glass; solar in both modes). Code checked:
`Ground Truth Calculators/HVACGroundTruthCalculator.py` (831 lines, read in full 2026-09-27). No repo file
was edited. Impact estimates used a subclass of the calculator in the session scratchpad
(`scratchpad/impact/run.py`), run over the 105 scenarios in `Scenario Files/HVACScenarios.xlsx`.

### Summary

49 rows reviewed.

| Verdict | Count |
|---|---|
| confirmed (value and source agree, or code/design row matches its description) | 24 |
| mismatch | 4 |
| assumption kept | 16 |
| replacement proposed | 5 |

Mismatches: (a) `ELECTRICITY_RATE_PA`: the PA PUC derivation cited for $0.19 does not reproduce 0.19. The
volumetric default-service rate from the PUC 2025 Rate Comparison Report averages 17.9 c/kWh; EIA's 2025
PA residential average (19.30 c/kWh) supports 0.19 directly. (b) Budget penalty: the paper sentence quoted
as the source still names the 1.5 cutoff ("infeasibility beyond 150%"), which revision 2 removed, and
does not name the exponent 3.0 that the code uses. (c, d) Two rows cite the wrong line numbers (load cap;
mode resolution in `calculate_scenario_scores`). Smaller line drift (1 line) affects seven more rows; see
the code column.

Proposed changes, ranked by likely impact:

1. `_efficiency_degradation` (rates, schedule, cap): replace with HSP Eq. 20,
   `1 - (1 - M)^min(age, 20)`, where M = 0.01 (annual professional maintenance) and M = 0.03 (seldom or
   never maintained) come from HSP Table 32. M = 0.02 for 'moderate' is our midpoint. At age 10, 20 and
   40+ this gives 18.3%, 33.2% and 33.2%. The current code gives 15%, 20% and 30%. Rankings: 0 of 105
   scenarios change, because degradation scales every alternative in a scenario equally. Absolute
   practicality scores do change for old units (hvac_age runs 1-40, median 18).
2. `BASE_INTERNAL_GAIN_BTUH` 800 -> 746 and `EQUIPMENT_GAIN_BTUH_PER_SQFT` 1.0 -> 0.99. Both come from
   the IECC 2018 (PA-adopted) Table R405.5.2(1) internal-gain equation, IGain = 17,900 + 23.8 x CFA
   + 4,104 x Nbr Btu/day, divided by 24. The current values already sit within 7% of this code equation,
   so the main gain is a sourced status. Impact: 2 of 105 scenarios change ranking (both change top-1).
   The cost p5 moves from 0.1895 to 0.20, which would shift the energy_cost VF floor from $0.19 to $0.20.
3. `ELECTRICITY_RATE_PA` 0.19: keep the value and re-cite it to EIA Electric Power Monthly (Feb 2026),
   Table 5.6.B: PA residential, year to date through December 2025, 19.30 c/kWh.
4. `ceiling_height` 8 ft: keep the value, with its status changing from our assumption to sourced. The
   source is ResStock v3.2.0 options_lookup.tsv, which sets `geometry_average_ceiling_height=8` for every
   RECS building type.
5. Envelope multipliers: no primary source found, so the assumption is kept. However, a ResStock-geometry
   cross-check puts Apartment/Condo 1.2 well above a mid-floor unit (about 0.2-0.5), which is flagged, not
   proposed. Cutting it to 0.5 changes ranks in 2 of 105 scenarios.

### Row table

| constant | code value (file:line) | source value | verbatim quote | page/URL | verdict | proposed change |
|---|---|---|---|---|---|---|
| `EMISSIONS_FACTOR_PEAK` | 1.041 lbs/kWh (HVACGroundTruthCalculator.py:24) | 2022 marginal On-Peak, Annual column: 1,041 lbs/MWh | "2022 MARGINAL On-Peak 1,124 973 1,017 893 938 1,071 1,232 1,192 1,044 946 944 1,012 1,041" (row of "Marginal CO2 Emission Rates Table", columns Jan..Dec, Annual) | PJM, 2018-2022 CO2, SO2 and NOX Emission Rates (Apr 27, 2023), p. 3 (PDF p. 6), https://www.pjm.com/-/media/DotCom/library/reports-notices/special-reports/2023/2022-emissions-report.ashx | confirmed | Add the quote to the provenance row. |
| `EMISSIONS_FACTOR_OFFPEAK` | 0.976 lbs/kWh (:25) | 2022 marginal Off-Peak, Annual: 976 lbs/MWh | "Off-Peak 1,196 1,078 954 839 830 888 1,041 1,033 958 924 947 1,017 976" (2022 block) | same, p. 3 | confirmed | Add quote. |
| `EMISSIONS_PEAK_HOURS_PER_DAY` / `OFFPEAK` | 16 / 8 (:26-27) | 7 a.m.-11 p.m. on non-holiday weekdays | "Peak periods are all non-holiday weekdays from 7 a.m. to 11 p.m., and off-peak periods are all other hours." | same, p. 3 | confirmed | None. Note: in PJM's definition, off-peak also includes all weekend and holiday hours, so the annual off-peak rate is not a pure 11 p.m.-7 a.m. rate. The code's every-day split is already disclosed. |
| `emissions_factor_for_occupancy` | mapping (:344-378) | PJM windows | (window quote above) | same, p. 3 | confirmed (derived) + assumption kept (occupancy-to-hours mapping) | None. |
| `ELECTRICITY_RATE_PA` | 0.19 $/kWh (:32) | EIA 2025 PA residential average 19.30 c/kWh; EIA 2024 17.77 c/kWh; PUC 2025 default-service volumetric rate (500 kWh bill minus customer charge, /500) averages 0.179 for Duquesne, Met-Ed, Penelec, West Penn, PECO, PPL (range 0.151-0.208) | EIA: "Table 5.6.B. Average Price of Electricity to Ultimate Customers by End-Use Sector, by State, Year-to-Date through December 2025 and 2024 (Cents per Kilowatthour) ... Pennsylvania 19.30 17.77". PUC: "the rates used would be as of Jan. 31, 2025, and would be based on the default service price"; Residential "using 500 kWh" totals: Duquesne $117.15 (customer charge $13.00), Met-Ed $97.67 ($11.25), Penelec $108.28 ($11.25), West Penn $84.39 ($9.00), PECO $106.01 ($11.25), PPL $93.67 ($14.09) | EIA EPM Feb 2026, Table 5.6.B (PDF p. 138), https://www.eia.gov/electricity/monthly/archive/february2026.pdf; EIA EPA Table 2.10, https://www.eia.gov/electricity/annual/html/epa_02_10.html; PA PUC Rate Comparison Report Apr 15 2025, pp. 4, 8, 12-19, https://www.puc.pa.gov/media/3429/2025_rate_comparison_report.pdf | mismatch (derivation) | Keep 0.19 and cite EIA 2025 (19.30 c/kWh). The PUC default-service derivation yields about 0.18 volumetric (about 0.20 with the customer charge spread over 500 kWh), not 0.19. The provenance row and code comment (:29-31) should say 0.19 = EIA 2025 average. |
| `AIR_CHANGES_PER_HOUR` | 0.35 (:37) | 0.35 h^-1 | "In 1989, the standard required an air change rate of 0.35 h−1 in living areas, but no less than 7.5 L/s per person, which remained in the standard through the 2004 version." | Persily 2015, Sec. 2.3, https://pmc.ncbi.nlm.nih.gov/articles/PMC6605073/ | confirmed | None to the value. Flag: this is a ventilation requirement, not a measured infiltration rate. The code comment (:35) still names ACCA Manual J as the source. |
| infiltration coefficient 1.08 | 1.08; cfm = V x ACH / 60 (:132-137) | 0.075 x 0.24 x 60 = 1.08 | arithmetic | n/a | confirmed (derived) | None. |
| `ceiling_height` | 8.0 ft (:94; also :143, :152, :599) | 8 ft for all RECS building types | `Geometry Building Type RECS	Single-Family Detached	ResStockArguments	geometry_unit_type=single-family detached	geometry_average_ceiling_height=8	geometry_unit_aspect_ratio=1.8`; same `geometry_average_ceiling_height=8` for Mobile Home, Multi-Family 2-4, Multi-Family 5+, Single-Family Attached | ResStock v3.2.0 options_lookup.tsv lines 9361-9365, https://raw.githubusercontent.com/NREL/resstock/v3.2.0/resources/options_lookup.tsv | replacement proposed (status only) | Status: our assumption -> sourced (ResStock). Value unchanged. |
| `u_factor` = 1/R on whole envelope | 1/r_value (:116) | IECC 2018 climate zone 5 (most of PA) minimums: ceiling R-49, wood wall R-20 or 13+5, floor R-30, fenestration U-0.30 | "5 and Marine 4 0.30 0.55 NR 49 20 or 13+5 h 13/17 30 g 15/19 10, 2 ft 15/19" (Table R402.1.2 columns: fenestration U, skylight U, SHGC, ceiling R, wood frame wall R, mass wall R, floor R, basement wall R, slab, crawl space wall) | IECC 2018 (Pennsylvania), Table R402.1.2, https://up.codes/viewer/pennsylvania/iecc-2018/chapter/RE_4/re-residential-energy-efficiency | assumption kept | None. Wall R understates ceiling R (49 vs 20) but overstates window R (U 0.30 = R 3.3), so the errors partly offset. Scenario r_value spans 8-24. No source gives a single whole-envelope R. |
| envelope multipliers | SF 1.7, Apt/Condo 1.2, Town/Row 1.5, default 1.7 (:106-113) | no primary source gives a surface-to-floor ratio. Our cross-check from ResStock geometry (8 ft ceilings, aspect ratio 1.8 SFD / 0.5556 SFA and MF): SFD walls+ceiling 1.6 (2-story, 1,800 ft2) to 1.9 (1-story, 1,500 ft2), 2.1-2.9 with floor; interior townhouse 0.9 (1.4 with floor); end townhouse 1.3 (1.8 with floor); mid-floor apartment 0.2-0.5; top-floor apartment about 1.2 | ResStock aspect-ratio and ceiling-height rows quoted above (lines 9361-9365) | same ResStock URL | assumption kept | None proposed. Flag: Apartment/Condo 1.2 matches only a top-floor unit; the code comment calls it "mid-unit typical". Scratch test with 0.5: 2/105 scenarios change rank; cost p5/p95 0.192/3.22. |
| `OCCUPANT_SENSIBLE_GAIN_BTUH` | 220 (:44) | 220 Btu/person/h | "Single Zone Internal Load (Btu/person/h) Sensible load 220 Latent load 164" | HSP Table 44, p. 64, https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/house_simulation_revised.pdf | confirmed | None. |
| `EQUIPMENT_GAIN_BTUH_PER_SQFT` | 1.0 (:45) | 23.8 Btu/day per ft2 CFA = 0.99 Btu/h per ft2 | "Internal gains IGain, in units of Btu/day per dwelling unit , shall equal: 17,900 + 23.8 × CFA + 4,104 × N br where: CFA = conditioned floor area , ft 2 . N br = number of bedrooms." | IECC 2018 (PA) Table R405.5.2(1), Internal gains row, up.codes URL above | replacement proposed | 1.0 -> 0.99 (23.8/24), status derived from IECC R405. Cross-check: HSP Table 21 plus lighting Eqs. 7-8 give about 1,830 Btu/h sensible for an all-electric 1,800 ft2, 3-bedroom house; the code gives 2,600 Btu/h and IECC 2,540 Btu/h (without the bedroom term). |
| `BASE_INTERNAL_GAIN_BTUH` | 800 (:46) | 17,900 Btu/day = 746 Btu/h | (same IGain quote) | same | replacement proposed | 800 -> 746 (17,900/24). Keep 220 Btu/h per person in place of IECC's 4,104 x Nbr term (scenarios carry household size, not bedrooms). Combined with the row above, 2/105 scenarios change ranking and the energy_cost p5 becomes $0.20. |
| glazing fraction | 0.15 x floor area (:129) | 15% of CFA | "Vertical fenestration other than opaque doors Total area h = The proposed glazing area, where the proposed glazing area is less than 15 percent of the conditioned floor area 15 percent of the conditioned floor area , where the proposed glazing area is 15 percent or more of the conditioned floor area ." | IECC 2018 (PA) Table R405.5.2(1), up.codes URL above | confirmed | Record the table number (R405.5.2(1)). Caveat: footnote h reduces the glazing for "townhouses" and R-2 units ("F = (above-grade thermal boundary wall area)/(above-grade thermal boundary wall area + common wall area) or 0.56, whichever is greater"), and the code applies 15% to all 58 attached-type scenarios. HSP Eq. 1 uses 0.15 x exterior wall area instead. |
| `HVAC_MODES`, `hvac_mode_from_question`, `resolve_hvac_mode` | :66-68, :208-227; mode resolution is at :545-551 (row says 528-541, which is `_inputs_valid`) | design | none | n/a | mismatch (line numbers) | Fix code location to :540-551. |
| Load, capped by mode | :603-606 (row says 567-586, which is the "Off" parsing) | design | none | n/a | mismatch (line numbers) | Fix code location to :603-606. |
| cooling EER | -0.02 SEER^2 + 1.12 SEER (:187) | same | "Equation 3 may also be used to make an approximate conversion from SEER to EER (Wassmer 2003): EER = –0.02 × SEER2 + 1.12 × SEER (3)" | HSP p. 7 | confirmed | None. |
| `HSPF_BY_SEER` (SEER <= 14) | 6.5/6.0, 8/6.6, 10/7.1, 14/8.0 (:59-60) | same | "Split heat pump, single-speed scroll compressor, BPM air handler motor, thermostatic expansion valve 14 10.5 8.0"; "(after 1991) 10 9.3 7.1"; "(1981–1991) 8 7.7 6.6"; "(before 1981) 6.5 6.4 6.0" | HSP Table 32, p. 40 | confirmed | None. |
| `HSPF_BY_SEER` (13) | 13/7.7 (:59) | same | "Air source heat pump (split) Heating/Cooling 7.7 HSPF/13 SEER air source heat pump" | HSP Table 4, p. 8 | confirmed | None. |
| `HSPF_BY_SEER` (SEER > 14) | 18/9.3, 22/10.0 (:59-60) | same | `"ASHP, SEER 18, 9.3 HSPF" ... heat_pump_heating_efficiency=9.3 ... heat_pump_cooling_efficiency=18`; `"ASHP, SEER 22, 10 HSPF" ... heat_pump_heating_efficiency=10 ... heat_pump_cooling_efficiency=22` | options_lookup.tsv lines 9698-9699 | confirmed | None. |
| `heating_hspf` interpolation | :160-172 | interpolation allowed | "Default efficiencies for equipment not listed in the table may either be interpolated or estimated by referring to the original references." | HSP p. 40 | confirmed (extrapolation remains ours) | None. |
| heating conversion | Btu/h / (HSPF x 1000) (:184-189) | unit identity | none | n/a | confirmed (derived) | None. |
| `hours` | 8 (:175) | none | none | n/a | assumption kept (decision-period design) | None. |
| runtime multipliers | 1.0; 1 - (H/24) x 0.5; 0.75 (:192-204) | none found | HSP gives occupant presence only ("16.5 h/day/person total", Figure 25, p. 64), not HVAC runtime | HSP p. 64 | assumption kept | None; no primary source ties occupancy pattern to HVAC runtime fraction. |
| `SUMMER_OPTIMAL` | 76 (:75, :244) | 76 F | "Set point for cooling: 76°F with no setup period" | HSP p. 49 | confirmed | None. (IECC R405 reference uses 75 F cooling / 72 F heating; context only.) |
| `WINTER_OPTIMAL` | 71 (:77, :244) | 71 F | "Set point for heating: 71°F with no setback period" | HSP p. 49 | confirmed | None. |
| `SUMMER_COMFORT_RANGE` | (73, 79) (:74) | not verified | none (ASHRAE 55-2020 paywalled, not opened) | n/a | assumption kept (unused by code; grep finds only the definition) | None. |
| `WINTER_COMFORT_RANGE` | (68, 74) (:76) | not verified | none | n/a | assumption kept (unused) | None. |
| comfort: mode | :229-244 | design | none | n/a | confirmed (design) | None. |
| comfort: slope | 1.0 per F (:245) | none | none | n/a | assumption kept (design) | None. |
| comfort: household size penalty | (n-3) x 0.3 x abs(dT)/3 (:247-249) | none | none | n/a | assumption kept (design) | None. |
| `_efficiency_degradation`: rates | 0.005/0.010/0.015 per yr (:261-262) | HSP: M = 0.01 (annual professional maintenance) or 0.03 (seldom or never maintained) for split heat pumps and ACs | "EFF = (Base EFF) × (1-M)age (20) ... M = Maintenance factor Age = Age of equipment in years, up to a maximum of 20 years."; Table 32 rows end "0.01 0.03" under "Maintenance Factor (M) Annual Professional Maintenance / Seldom or Never Maintained" | HSP Eq. 20 and Table 32, pp. 40-41 | replacement proposed | good M = 0.01, poor M = 0.03, moderate M = 0.02 (midpoint, ours). |
| `_efficiency_degradation`: schedule and cap | 1.5x base yrs 1-10, 0.5x after; cap 30% (:263-267) | HSP: compound (1-M)^age with age capped at 20 | (Eq. 20 quote above) | HSP p. 41 | replacement proposed | degradation = 1 - (1 - M)^min(age, 20). Max 33.2% at M = 0.02. Scratch run: 0/105 ranking changes (1/105 at M = 0.03). |
| practicality: mode | :279-281 | design | none | n/a | confirmed (design) | None. |
| practicality: extremity thresholds | :281-297 | none | none | n/a | assumption kept (design) | None. |
| practicality: delta-T factors | :299-311 | none | none | n/a | assumption kept | None; no source found. |
| practicality: degradation factor and clamp | :317-320 | none | none | n/a | assumption kept (design) | None. |
| `_free_float_temp` | +5 F cool, +10 F heat (:511-522; row says 510-521) | none found | none | n/a | assumption kept | None; no primary source gives free-running indoor-outdoor offsets for these conditions. |
| `calculate_monthly_cost` | 90 (:322-323; call at :696-699, row says L678) | 3 x 30 | arithmetic | n/a | confirmed (derived) | Fix line ref to :696-699. |
| `calculate_budget_penalty` | 0.80 / 2.5 / 0.5 e^(-3(u-1)) (:325-342) | paper sentence | paper_draft_v2.tex:671: "The values 0.80, 2.5 and 1.5 and the exponential form are our own choices."; paper_draft_working.tex:648 still says "infeasibility beyond 150\%" and "the values 0.80, 2.5 and 1.5" | repo | mismatch (quote vs code) | The quoted text names 1.5, which revision 2 removed, and omits the exponent 3.0 and the 0.5 scale. Update the provenance quote. The paper sentence is flagged for the author, not edited. |
| energy_cost bounds | 0.19 / 3.21 (:423-424; row says 422-423) | recomputed: n = 280 active, p5 0.1895, p95 3.2105 | computed | scratch run | confirmed | Fix line ref. |
| environmental bounds | 0.97 / 17.59 (:438-439) | 0.997 x 0.976 = 0.973; 16.897 x 1.041 = 17.59 | computed | n/a | confirmed | Fix line ref. |
| practicality floor | 0.05 / 1.0 (:453-454) | none | none | n/a | assumption kept (design) | Fix line ref. |
| comfort range | 0 / 1 (:443-444) | derived | none | n/a | confirmed | Fix line ref. |
| `VF_ENERGY_COST` linear | :82, :467-473 | not verified | code quote attributed to Dyer & Sarin (1979); the phrasing reads like a paraphrase | https://doi.org/10.1287/opre.27.4.810 (403 at pubsonline.informs.org) | confirmed (code) / source not opened | Treat the quote as unverified until someone reads the paper. |
| `VF_ENVIRONMENTAL` linear | :89 | none | none | n/a | assumption kept (design) | None. |
| `VF_COMFORT` log a = 1.5 | :90, :492-504 | none | none | n/a | assumption kept (design) | None. |
| `VF_PRACTICALITY` log a = 1.2 | :91, :492-504 | none | none | n/a | assumption kept (design) | None. |
| MAVT weights | model_config.py:20-25 (0.30/0.35/0.20/0.15); sentinel_utils.py:25 `MAVT_ROUND_DECIMALS = 10` | matches row | none | n/a | confirmed | None. |

Verdict tally notes: "confirmed" includes design rows whose code matches their description, plus the
Dyer & Sarin row (code matches, but the source could not be opened). Line drift of one line, with no
value change, affects `_free_float_temp`, the four `apply_value_function` bound rows and both VF-formula
line ranges.

### Other observations (not edited)

- `paper/paper_draft_working.tex:614` reports "\$0.38--\$3.29" as the realized cost span. Current code
  bounds are \$0.19/\$3.21. The same line cites the EIA state average as "about \$0.177/kWh" (2024);
  EIA's 2025 figure is 19.30 c/kWh.
- The HVAC code comment at :35 cites ACCA Manual J for 0.35 ACH; the provenance row cites Persily 2015.

### Not opened / blocked

- ASHRAE Standard 55-2020, ASHRAE Handbook of Fundamentals Ch. 18 (residential internal gains) and ACCA
  Manual J (1,200 Btu/h appliance allowance): paywalled, not opened. The IECC R405 equation was used
  instead.
- Dyer & Sarin (1979), Oper. Res. 27(4): pubsonline.informs.org returned 403.
- Newer PJM emissions reports (2023, 2024 data): guessed URLs on pjm.com returned an HTML page, not a
  PDF. The newer vintages were not checked.
- Not needed: codes.iccsafe.org (blocked). up.codes (IECC 2018 Pennsylvania) served the full chapter.

---

## 3. Value review: Appliance calculator constants (`value_review/APPLIANCE.md`)

Scope: every row of the Appliance section of `docs/CALCULATOR_PROVENANCE.md` (lines 142-231, 90 rows), checked against `Ground Truth Calculators/ApplianceGroundTruthCalculator.py` (read in full, current working tree including commit `daafa48`) and against the cited primary sources, which were re-opened in this session. Reviewed 2026-09-27. Read-only: no `.py`, `.xlsx`, `.tex` or existing `.md` file was edited, and no paid API call was made. Source copies and the impact script are in the session scratchpad (`src/`, `app_impact/impact.py`), not in the repo.

### Summary

Verdict counts (90 provenance rows):

| Verdict | Rows |
|---|---|
| confirmed | 51 |
| mismatch | 4 |
| replacement proposed | 6 |
| assumption kept | 29 |

Every tariff number, tariff window, PJM factor, cycle count and value-function bound in the code matches its primary source. The four mismatches are all documentation errors. None of them is a wrong number in the code:

1. **Criterion weights row (line 230) has energy and environmental swapped.** The row says energy 0.35, environmental 0.30. `model_config.py:20-25` has `energy_cost` 0.30 and `environmental` 0.35, which is also what the HVAC section's row (line 106) says.
2. **Monroeville is a split territory, not a single sourced mapping.** It appears in both the FE West Penn list and Duquesne's "List of Communities Served". Its status should be "our assumption (split territory)", as for Stroudsburg. Moving it to Duquesne changes 0 of 100 master winners.
3. **Budget-penalty row (line 206) says the maximum utilization is "about 0.29".** Recomputed on the current code it is 0.2292. This is the same finding as D5 in `V_APPLIANCE.md`.
4. **`calculate_environmental_impact` code location has drifted.** The row gives lines 190-194; the function is now at lines 201-205.

Proposed changes, ranked by likely ground-truth impact. None of them changes a value in the code, so the ground-truth impact of adopting any of them is zero. The sensitivity figures show what would move if the underlying choice were changed instead:

1. **Noise window 10 p.m.-7 a.m.** Replace "none" with 24 CFR 51.103 and 14 CFR 150.7, the federal DNL definitions whose night is 10 p.m. to 7 a.m., plus Pittsburgh Code 601.04 (nighttime 10:00 p.m. to 7:00 a.m.). The Philadelphia Code has no general night window. Sensitivity: WHO's 23:00-07:00 night would change 1 of 100 winners (2 of 100 full rankings).
2. **`NOISE_LIMIT_EVENING` = 45 dBA.** Source it to WHO (1999) *Guidelines for Community Noise*: bedrooms, 45 dB LAmax for single sound events at night. Also fix the code comment's "EPA/WHO indoor night limit is 35 dBA": in WHO (1999), 35 dB LAeq is the daytime and evening dwelling value, and the bedroom night value is 30 dB LAeq,8h. Sensitivity: if the dishwasher counted as above the threshold, 1 of 100 winners and 6 of 100 full rankings would change.
3. **Appliance noise levels 45 / 74 / 65 dB(A).** Replace the retailer credits with the EU energy-label regulations:
   - Delegated Regulation (EU) 2019/2017, dishwashers: 45 dB(A) is the lower bound of class C.
   - Delegated Regulation (EU) 2019/2014, washing machines, spinning phase: 74 dB falls in class B, 73-77.
   - Delegated Regulation (EU) 2023/2534, tumble dryers: 65 dB(A) falls in class C, 64-68.
   - For the dryer, Čurović et al. (2022, *Applied Acoustics*) measured 64.8 dB(A) sound power on a heat-pump dryer.

   Caveat: all of these are A-weighted sound power levels (re 1 pW). The 45 dB threshold is an indoor sound pressure level at the sleeper, so comparing the two is a modelling simplification the paper should state.
4. **City map row "not checked this session" (line 183).** All 27 cities in it are now confirmed against the utilities' own tariff territory lists (quotes below). The status can move to "sourced", except Monroeville (item 2 in the mismatch list above).
5. **Washer cycles.** Cite 10 CFR 430 Subpart B Appendix J2 ("295 = Representative average number of clothes washer cycles in a year"; 295/12 = 24.6, which rounds to 25) next to or instead of ENERGY STAR's "about 300". The value 25 is unchanged.

**Observation (not a proposal, since CLAUDE.md fixes the PJM annual factors).** The rate period is December to May, but the PJM factors are 2022 annual means. The same PJM table's 2022 December-May monthly means are 992.8 on-peak and 985.7 off-peak, which nearly erases the peak/off-peak difference. Using them (with recomputed bounds) would change 3 of 100 winners and 5 of 100 full rankings.

**DOE figures that affect nothing today.** DOE's newer test procedures use fewer cycles per year:
- Appendix C2 (dishwashers): no substitution for AHAM DW-1-2020's N = 184 was found in the fetched text, so C2 appears to use 184.
- Appendix J (clothes washers): 234.
- Appendix D2 (clothes dryers): 236 from March 1, 2028.

The cycle counts only feed the budget penalty, and that penalty is inert (maximum utilization 0.2292, or 0.1910 with those counts). Switching to these counts therefore changes 0 of 100 rankings.

Impact method: `app_impact/impact.py` (scratchpad) imports the calculator read-only, scores all 100 master scenarios in `Scenario Files/ApplianceScenarios.xlsx` (65 test + 35 RAG, 300 alternatives) with `apply_mavt_ranking`, and compares each variant against the unmodified calculator. The baseline reproduces `ENERGY_COST_BOUNDS` (0.028, 0.774) and `ENVIRONMENTAL_BOUNDS` (0.288, 3.643) exactly.

### Row-by-row table

Line numbers refer to `Ground Truth Calculators/ApplianceGroundTruthCalculator.py` unless another file is named. "PDF idx" is the 0-based pypdf page index.

Source URLs used below:
- PECO-PTC: https://azure-na-assets.contentstack.com/v3/assets/blt1b5616c79bacadb4/bltf7c1eb06cdfe6ab9/6a0e7050df378b4731251e82/2026_RESIDENTIAL_Final_Electric_PTC_Effective_06-01-2026.pdf
- PECO tariff: https://www.peco.com/cdn/assets/v3/assets/blt1b5616c79bacadb4/blt9448ea371fcf175a/69cbdc20a21ea55b33ba7d35/Current_Electric_tariff_effective_April_1_2026.pdf (Supplement No. 24 to Electric Pa. P.U.C. No. 8, eff. April 1, 2026)
- PPL-402 / PPL-201-terr: https://www.pplelectric.com/site/-/media/PPLElectric/At-Your-Service/Docs/Current-Electric-Tariff/2025/Dec/master402-403-posted-2025-12-1.pdf
- PPL-PTC: https://www.pplelectric.com/site/-/media/PPLElectric/At-Your-Service/Docs/Current-Electric-Tariff/2025/Nov/PTC-December-1-2025--May-31-2026.ashx
- FE-20: https://www.puc.pa.gov/pcdocs/1875621.pdf
- FE-28: https://www.firstenergycorp.com/content/dam/customer/Customer%20Choice/Files/PA/tariffs/FEPA-Supp-No-28-PTC-HPS-Rider-Changs-12-1-2025.pdf
- FE-tariff: https://www.firstenergycorp.com/content/dam/customer/Customer%20Choice/Files/PA/tariffs/fe-pa-retail-tariff-1-1-26.pdf
- PUC-1124: https://www.puc.pa.gov/press-release/2025/puc-alerts-consumers-of-december-1-electric-price-changes-11242025
- DUQ-108: `temppapers/currenttariff_108_256018e393-caba-4589-8360-f64513d80451.pdf` (local)
- PJM-2022: https://www.pjm.com/-/media/DotCom/library/reports-notices/special-reports/2023/2022-emissions-report.ashx
- eCFR 10 CFR 430 Subpart B appendices C1, C2, D1, D2, J, J2 (eCFR versioner API, date 2026-09-01): https://www.ecfr.gov/current/title-10/chapter-II/subchapter-D/part-430/subpart-B
- 76 FR 972: https://www.govinfo.gov/content/pkg/FR-2011-01-06/pdf/2010-32118.pdf
- ENERGY STAR: https://www.energystar.gov/products/dishwashers/key_product_criteria ; https://www.energystar.gov/products/clothes_washers
- Paetz et al. (2012): https://www.aceee.org/files/proceedings/2012/data/papers/0193-000232.pdf
- WHO (1999) *Guidelines for Community Noise*, Berglund, Lindvall and Schwela (eds.). The WHO copy (https://iris.who.int/handle/10665/66217) is an image-only scan with no text layer, and no OCR tool was available here. Quotes were taken from a text-layer copy of the same document (https://docs.wind-watch.org/WHO-Communitynoise.pdf, a third-party mirror); the page numbers are the document's own printed ones.
- EU regulations: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32019R2017 , ...CELEX:32019R2014 , ...CELEX:32023R2534
- eCFR 24 CFR 51 and 14 CFR 150 (versioner API, 2026-09-01)
- Pittsburgh Code 601.04: https://www.nonoise.org/regulation/ordinance/Pittsburgh,%20Pennsylvania.pdf (2015 print of the municipal code; the official ecode360 page returned 403)
- Philadelphia Code ch. 10-400: https://www.phila.gov/media/20211008145350/Noise-Code-20211008.pdf

| # | Constant | Code value (file:line) | Source value | Verbatim quote | Page / URL | Verdict | Proposed change |
|---|---|---|---|---|---|---|---|
| 1 | Common rate period | Dec 1 2025 - May 31 2026 (comment :27-29) | Same period in every tariff document | PECO-PTC: "PECO Time-of-Use (TOU) Pricing Option Effective December 1, 2025 through May 31, 2026"; FE-28: "For service rendered December 1, 2025 through May 30, 2026" | PECO-PTC PDF idx 2; FE-28 PDF idx 2 | assumption kept | none (author decision) |
| 2 | Rate basis (PTC, no distribution) | comment :30-33 | FE PTC includes transmission | "PTCNITS = When the Company purchases Network Integration Transmission Service from PJM on behalf of customers, a Network Integration Transmission Service Charge for Default Service" | FE-tariff Original Page 205, PDF idx 204 | assumption kept | none |
| 3 | Weekday rule | comment :21-22, :34 | PLAN decision (not re-opened) | n/a | `paper/pass5/RERUN_PREP_PLAN.md` | assumption kept | none |
| 4 | `_in_window` | :158-164 | FE super off-peak wraps midnight | "Super Off-Peak 11 PM - 6 AM Every day" | FE-20 First Revised Page 221, PDF idx 5 | confirmed | none |
| 5 | `determine_rate_period` | :166-183 (None location -> 14-18) | Tariff period definitions | PECO-PTC note (5): "Off-Peak period refers to all other hours that are not Peak and Super Off-Peak periods." FE-20: "Off-Peak All Other Hours" | PECO-PTC PDF idx 2; FE-20 PDF idx 5 | confirmed | none. The `location=None` branch is dead code (no caller). |
| 6 | `calculate_energy_cost` | :192-199 | arithmetic | n/a | n/a | confirmed | none |
| 7 | PECO peak window | (14, 18) :44 | 2-6 p.m. weekdays | "Peak period refers to 2:00 p.m. through 6:00 p.m., Monday through Friday, excluding PJM holidays" | PECO-PTC note (5), PDF idx 2 | confirmed | none |
| 8 | PECO super off-peak window | (0, 6) :44 | midnight-6 a.m. | "Super Off-Peak period refers to midnight (12 a.m.) through 6 a.m., every day" | PECO-PTC PDF idx 2 | confirmed | none |
| 9 | PECO peak rate | 0.32747 :45 | 32.747 c | "Peak kWhs 32.747 31.960 0.787" (Residential (R), columns (A) = (B) + (C)) | PECO-PTC PDF idx 2 | confirmed | none |
| 10 | PECO off-peak rate | 0.08382 :45 | 8.382 c | "Residential (R) Off-Peak kWhs 8.382 7.595 0.787" | PECO-PTC PDF idx 2 | confirmed | none |
| 11 | PECO super off-peak rate | 0.06061 :45 | 6.061 c | "Super Off-Peak kWhs 6.061 5.274 0.787" | PECO-PTC PDF idx 2 | confirmed | none |
| 12 | PPL on-peak window | (16, 20) :50 | 4-8 p.m. Dec-May | "Rate Schedule RS and RTS (R) Winter On-Peak Hours (4:00 PM to 8:00 PM) December 1 to May 31"; "On-Peak hours will be set based on schedule below Monday through Friday, excluding weekends and holidays." | PPL-402, Twenty-Third Revised Page No. 19Z.5B, PDF idx 65 | confirmed | none |
| 13 | PPL on-peak rate | 0.13986 :51 | 13.986 c | "Residential (TOU On peak - Non-Summer) 10.643 3.343 0.000 13.986"; PPL-402: "On-Peak Hours 10.643 cts per kWh (I)" | PPL-PTC p. 1; PPL-402 PDF idx 65 | confirmed | none |
| 14 | PPL off-peak rate | 0.11987 :51 | 11.987 c | "Residential (TOU Off peak - Non-Summer) 8.644 3.343 0.000 11.987"; PPL-402: "Off Peak Hours 8.644 cts per kWh (I)" | PPL-PTC p. 1; PPL-402 PDF idx 65 | confirmed | none |
| 15 | FE on-peak window | (14, 21) :52, :55, :58 | 2-9 p.m. | "On-Peak 2 PM - 9 PM Monday - Friday" | FE-20 PDF idx 5 | confirmed | none |
| 16 | FE super off-peak window | (23, 6) :52, :55, :58 | 11 p.m.-6 a.m. | "Super Off-Peak 11 PM - 6 AM Every day" | FE-20 PDF idx 5 | confirmed | none |
| 17 | West Penn PTCDefault | 0.10947 :53-54 | $0.10947 | "West Penn ... Rate Schedule RS, GS-V ... Charge $0.10947 (I) per kWh"; PUC-1124: "West Penn Power: 10.318 to 10.947 ¢/kWh ( +6.1% )" | FE-28 Sixth Revised Page 203, PDF idx 2; PUC-1124 | confirmed | none |
| 18 | West Penn multipliers | 1.6649 / 0.8542 / 0.6298 :53-54 | same | "On-Peak Rate PTCDefault Rate x 1.6649"; "Off-Peak Rate PTCDefault Rate x 0.8542"; "Super Off-Peak Rate PTCDefault Rate x 0.6298" (West Penn, Residential) | FE-20 PDF idx 5 | confirmed | none |
| 19 | Penelec PTCDefault | 0.11747 :56-57 | $0.11747 | "Penelec ... Charge $0.11747 (I) per kWh"; PUC-1124: "Penelec: 11.004 to 11.747 ¢/kWh ( +6.75% )" | FE-28 PDF idx 2; PUC-1124 | confirmed | none |
| 20 | Penelec multipliers | 1.6792 / 0.8482 / 0.6510 :56-57 | same | "PTCDefault Rate x 1.6792", "PTCDefault Rate x 0.8482", "PTCDefault Rate x 0.6510" | FE-20 PDF idx 5 | confirmed | none |
| 21 | Met-Ed PTCDefault | 0.12965 :59-60 | $0.12965 | "Met-Ed ... Charge $ 0.12965 (I) per kWh"; PUC-1124: "Met-Ed: 11.905 to 12.965 ¢/kWh ( +8.9% )" | FE-28 PDF idx 2; PUC-1124 | confirmed | none |
| 22 | Met-Ed multipliers | 1.7060 / 0.8397 / 0.6215 :59-60 | same | "PTCDefault Rate x 1.7060", "PTCDefault Rate x 0.8397", "PTCDefault Rate x 0.6215" | FE-20 PDF idx 5 | confirmed | none |
| 23 | FE multipliers in force | Supp. 20 (comment :36-38) | Supp. 20 page still in the Jan 2026 tariff | "Issued: April 22, 2025 Effective: June 1, 2025 ... Supplement No. 20 to Electric Pa P.U.C. No. 1 First Revised Page 221" | FE-tariff PDF idx 221 | confirmed | none |
| 24 | Duquesne rate | 0.1375 flat :64 | 13.75 c | "Duquesne Light: 12.43 to 13.75 ¢/kWh ( +10.6% )" | PUC-1124 | confirmed | none |
| 25 | Duquesne window | `peak_hours: None` :64 | flat default rate | Rate RS: "the Company will supply electricity at the above Distribution Charges, the Supply Charges in Rider No. 8 and the Transmission Service Charges in Appendix A" | DUQ-108 PDF idx 42 (Fourth Revised Page No. 38, Supp. No. 85) | confirmed | none |
| 26 | Duquesne PTC composition | comment :61-63 | supply + transmission | as row 25, plus "The Transmission Service Charges are included, for informational purposes, in Appendix A of this Tariff." | DUQ-108 PDF idx 42 | confirmed | none |
| 27 | Duquesne Rider 8 supply | 11.0275 c (not in code) | 11.0275 | "December 1, 2025, through May 31, 2026 11.0275 31.7565 5.8450 4.3015" | DUQ-108 PDF idx 107, Thirteenth Revised Page No. 98A (Supp. No. 102) | confirmed | none (implied Dec-May TSC = 13.75 - 11.0275 = 2.7225 c) |
| 28 | Duquesne Appendix A TSC | $0.031841 (not in code) | same, eff. June 1 2026 | "RS $0.031841 ⎯ (I)" under "MONTHLY RATES ... Energy Charge $/kWh" | DUQ-108 PDF idx 163, Ninth Revised Page No. 142 (Supp. No. 105) | confirmed | none |
| 29 | Duquesne Rider 10 | not modeled | Part 2 = 0% | "Part 1 of the surcharge, at a rate of (0.0964%) ... will be applied to the distribution charges of customer bills. Part 2 of the surcharge, at a rate of 0.0000% will include Gross Receipts Tax and will be applied to all portions of customer bills." | DUQ-108 PDF idx 125, Twelfth Revised Page No. 112 (Supp. No. 98) | confirmed | none |
| 30 | "13.75" absent from DUQ-108 | n/a | absent | text search of all 168 pages: no match | DUQ-108 | confirmed | none |
| 31 | City: Indiana | Penelec :86 | Penelec | "INDIANA COUNTY – Penelec and West Penn Rate Districts ... Penelec Rate District ... Homer City, Indiana, Marion Center" | FE-tariff PDF idx 13 (Original Page 14) | confirmed | none |
| 32 | City: Carlisle | PPL :90 | PPL | "CUMBERLAND COUNTY Boroughs of Camp Hill, Carlisle, Lemoyne," | PPL-201-terr Fourth Revised Page No. 4, PDF idx 6 | confirmed | none |
| 33 | City: Reading | MetEd :81 | Met-Ed | "BERKS COUNTY – Met-Ed Rate District City of Reading." | FE-tariff Original Page 8, PDF idx 7 | confirmed | none |
| 34 | City: Lebanon | MetEd :82 | Met-Ed | "LEBANON COUNTY – Met-Ed Rate District City of Lebanon." | FE-tariff Original Page 15, PDF idx 14 | confirmed | none |
| 35 | City: State College | WestPenn :83 | West Penn | "West Penn Rate District Boroughs of Bellefonte, Centre Hall, Howard, Milesburg, Millheim, Port Matilda, State College, Unionville." | FE-tariff Original Page 10, PDF idx 9 | confirmed | none |
| 36 | City: Chambersburg | WestPenn :89 | West Penn host utility | FE: "West Penn Rate District Boroughs of Chambersburg, Greencastle, Mercersburg, Mont Alto, Waynesboro."; borough: "In our case this was West Penn Power, now a First Energy Company." | FE-tariff Original Page 13, PDF idx 12; https://www.chambersburgpa.gov/government/electric.html | confirmed | none |
| 37 | City: Stroudsburg | PPL :82 | split (PPL "part", FE lists it) | PPL: "Boroughs of East Stroudsburg (part), Mount Pocono, and Stroudsburg (part)."; FE: "MONROE COUNTY – Met-Ed Rate District Boroughs of Delaware Water Gap, East Stroudsburg, Stroudsburg." | PPL Page No. 4A, PDF idx 7; FE-tariff Original Page 16, PDF idx 15 | assumption kept | none. Moving it to Met-Ed changes 1 of 100 master winners. |
| 38 | City: Quakertown | PPL :84 | absent from PPL, FE and PECO lists | PPL Bucks: "Boroughs of Richlandtown, Sellersville, Silverdale, Telford, and Turmbauersville."; FE Bucks: "Borough of Riegelsville."; PECO Bucks boroughs do not include Quakertown | PPL PDF idx 6; FE PDF idx 7; PECO tariff Original Page No. 4 | assumption kept | none. Municipal page quakertown.org returned 403 and was not re-read. |
| 39 | City: Harrisburg, Lancaster, Scranton, Wilkes-Barre, Hazleton, Allentown, Bethlehem, Williamsport | PPL :80-83 | PPL | "DAUPHIN COUNTY City of Harrisburg."; "LANCASTER COUNTY City of Lancaster."; "LACKAWANNA COUNTY Cities of Carbondale and Scranton."; "LUZERNE COUNTY Cities of Hazleton, Pittston, and Wilkes-Barre."; "LEHIGH COUNTY Cities of Allentown and Bethlehem."; "LYCOMING COUNTY City of Williamsport." | PPL Page No. 4 and 4A, PDF idx 6-7 | confirmed | none |
| 40 | City: Easton, Gettysburg | MetEd :89-90 | Met-Ed | "NORTHAMPTON COUNTY – Met-Ed Rate District City of Easton."; Adams, Met-Ed Rate District: "Fairfield, Gettysburg, Littlestown, McSherrystown, New Oxford, York Springs." | FE-tariff Original Pages 17 and 6, PDF idx 16 and 5 | confirmed | none |
| 41 | City: Monroeville | WestPenn :85 | **split: West Penn and Duquesne** | FE: "West Penn Rate District Boroughs of Bethel Park, Brackenridge, Bridgeville, Cheswick, Elizabeth, Jefferson Hills, Lincoln, McDonald, Monroeville, ..."; Duquesne: "The Company renders service in portions of Allegheny and Beaver Counties ... including all or a portion of the following cities, boroughs and townships." (Allegheny list includes "Monroeville") | FE-tariff Original Page 6, PDF idx 5; DUQ-108 Original Page No. 4, PDF idx 4 | mismatch (status) | Change status from "sourced" to "our assumption (split territory; West Penn kept)". Moving it to Duquesne changes 0 of 100 master winners and rankings. |
| 42 | City: "all other" (27 cities, "not checked this session") | :75-79, :85-91 | all confirmed, see rows 42a-42e | see 42a-42e | see 42a-42e | replacement proposed | Replace "Not checked this session / our assumption" with the quotes in 42a-42e; status "sourced". |
| 42a | PECO: Philadelphia, Chester, Media, Doylestown, Newtown, Levittown, Norristown, Pottstown, Lower Merion, King of Prussia, Blue Bell, Coatesville, Phoenixville, West Chester, Exton | PECO :75-79 | PECO | "PHILADELPHIA: CITY AND COUNTY OF Philadelphia."; "DELAWARE COUNTY: CITY: Chester. BOROUGHS: ... Media ..."; "BUCKS COUNTY: BOROUGHS: Bristol, Chalfont, Doylestown, ... Newtown, Penndel, Telford, Tullytown, Yardley. FIRST-CLASS TOWNSHIPS: Bristol. SECOND-CLASS TOWNSHIPS: ... Falls, ... Middletown, ..."; "MONTGOMERY COUNTY: BOROUGHS: ... Norristown, North Wales, Pennsburg, Pottstown, ... FIRST-CLASS TOWNSHIPS: ... Lower Merion ... SECOND-CLASS TOWNSHIPS: ... Upper Merion, ... Whitpain, ..."; "CHESTER COUNTY: CITY: Coatesville. BOROUGHS: ... Phoenixville, ... West Chester, West Grove. ... SECOND-CLASS TOWNSHIPS: ... Uwchland, ... West Whiteland, ..." | PECO tariff "LIST OF COMMUNITIES SERVED", Original Page No. 4, PDF idx 4 | (part of 42) | Status "sourced". The unincorporated places are Census-designated places inside listed townships: King of Prussia in Upper Merion, Blue Bell in Whitpain, Exton in West Whiteland/Uwchland, Levittown in Bristol Twp, Falls, Middletown and Tullytown. That geography is general knowledge, not quoted from a source. None of the 15 appears in the PPL or FE lists. |
| 42b | West Penn: Greensburg, Uniontown, Butler | WestPenn :85-86 | West Penn | "WESTMORELAND COUNTY ... West Penn Rate District Cities of Arnold, Greensburg, Jeannette, ..."; "FAYETTE COUNTY – West Penn Rate District Cities of Connellsville, Uniontown."; "BUTLER COUNTY ... West Penn Rate District City of Butler." | FE-tariff Original Pages 20, 13, 9 (PDF idx 19, 12, 8) | (part of 42) | status "sourced" |
| 42c | Penelec: DuBois, Oil City, Meadville, Erie, Altoona, Johnstown | Penelec :87-88 | Penelec | "CLEARFIELD COUNTY – Penelec Rate District City of DuBois."; "VENANGO COUNTY – Penelec Rate District Cities of Franklin, Oil City."; "CRAWFORD COUNTY ... Penelec Rate District Cities of Meadville, Titusville."; "ERIE COUNTY – Penelec Rate District Cities of Corry, Erie."; "BLAIR COUNTY ... Penelec Rate District City of Altoona."; "CAMBRIA COUNTY – Penelec Rate District City of Johnstown." | FE-tariff Original Pages 11, 19, 11, First Revised Page 12, Original Pages 8, 9 (PDF idx 10, 18, 10, 11, 7, 8) | (part of 42) | status "sourced" |
| 42d | Met-Ed: York | MetEd :89 | Met-Ed | "YORK COUNTY- Met-Ed Rate District City of York." (PPL's York list: "Boroughs of East Prospect and Wrightsville. Townships of Fairview, Hellam and Lower Windsor.") | FE-tariff Original Page 20, PDF idx 19; PPL Page No. 4B, PDF idx 8 | (part of 42) | status "sourced" |
| 42e | Duquesne: Pittsburgh, McKeesport | Duquesne :91 | Duquesne | Allegheny County list: "Bellevue East Pittsburgh McKeesport Sharpsburg" and "Chalfant Green Tree Pittsburgh West View" (columns of the table; neither city appears in FE's Allegheny West Penn or Penn Power lists) | DUQ-108 Original Page No. 4, PDF idx 4 | (part of 42) | status "sourced" |
| 43 | `EMISSIONS_FACTOR_PEAK` | 1.041 :23 | 1,041 lbs/MWh | "Peak periods are all non-holiday weekdays from 7 a.m. to 11 p.m., and off-peak periods are all other hours." Table "Marginal CO2 Emission Rates Table", row "2022 MARGINAL On-Peak 1,124 973 1,017 893 938 1,071 1,232 1,192 1,044 946 944 1,012 1,041" (last column = Annual) | PJM-2022 p. 3 (PDF idx 5), Carbon Dioxide (CO2) section | confirmed | Record this quote in the provenance row (it currently says "Verbatim text not recorded"). |
| 44 | `EMISSIONS_FACTOR_OFFPEAK` | 0.976 :24 | 976 lbs/MWh | "Off-Peak 1,196 1,078 954 839 830 888 1,041 1,033 958 924 947 1,017 976" (2022, Annual = 976) | PJM-2022 p. 3, PDF idx 5 | confirmed | Record the quote. See the seasonal observation in the Summary. |
| 45 | `EMISSIONS_PEAK_HOURS` | (7, 23) :25; test at :185-190 | 7 a.m.-11 p.m. | "Peak periods are all non-holiday weekdays from 7 a.m. to 11 p.m." | PJM-2022 p. 3 | confirmed | none |
| 46 | `calculate_environmental_impact` | :201-205 | n/a | n/a | n/a | mismatch (line numbers) | Provenance says :190-194; correct it to :201-205 (and `determine_emissions_period` :185-190). |
| 47 | `ENERGY_COST_BOUNDS` | (0.028, 0.774) :99 | recomputed p5/p95 = 0.028 / 0.774 | computed (`app_impact/impact.py`) | n/a | confirmed | none |
| 48 | `ENVIRONMENTAL_BOUNDS` | (0.288, 3.643) :100 | recomputed 0.288 / 3.643 | computed | n/a | confirmed | none |
| 49 | Comfort VF range | 0-1 :401-405 | design | n/a | n/a | assumption kept | none |
| 50 | Practicality VF range | 0.05-1.0 :406-415 | design | code: "Internal normalization choice (not a literature value)" | :409-410 | assumption kept | none |
| 51 | `apply_value_function` normalization | :376-470 | design | n/a | n/a | assumption kept | none |
| 52 | VF energy cost | linear :108, :433-434 | Dyer & Sarin (1979) (not opened) | n/a | n/a | assumption kept | Minor: the "386-388" cited are the reference-range dict, not the linear branch (:433-434). |
| 53 | VF environmental | linear :116, :433-434 | design | n/a | n/a | assumption kept | none |
| 54 | VF comfort | log a = 1.5 :117, :453-465 | design | n/a | n/a | assumption kept | none |
| 55 | VF practicality | log a = 1.2 :118, :453-465 | design | n/a | n/a | assumption kept | none |
| 56 | Max delay dishwasher | 12 h :132 | 12 h | "As an example the test-residents said to be able to postpone the dish-washer use by twelve hours without constraints" | Paetz, Kaschub, Jochem and Fichtner (2012), ACEEE Summer Study, p. 7-230 (PDF idx 6) | confirmed | Author list for the bib entry: Paetz, Kaschub, Jochem, Fichtner. The sample is two residents in one smart home, so the source is thin. |
| 57 | Max delay washer | 8 h :133-134 | no numeric source opened | Paetz p. 7-234 (qualitative): "Results show that the dish-washer, the washing machine and the e-scooters were the devices mainly subjected to load-shifting." | Paetz (2012) | assumption kept | No primary numeric source could be opened. Candidates with appliance-level flexibility windows are D'hulst et al. (2015, *Applied Energy* 155:79, LINEAR pilot) and Klaassen et al. (2016, IEEE ENERGYCON; 2016, *Applied Energy*). All are on sciencedirect/IEEE (blocked or paywalled); the LINEAR final report URL (emis.vito.be) returned HTML, and the Smart-A consumer-acceptance report (smart-a.org) is offline. |
| 58 | Max delay dryer | 6 h :135 | qualitative support only | "Even though, the tumble dryer had the smart functionalities, too, it was not used much, as the test-residents feared to leave the wet clothes in there for too long, before the program would start." | Paetz (2012) p. 7-232 | assumption kept | Cite Paetz p. 7-232 as qualitative support for the dryer having the shortest ceiling. The number 6 h stays ours. |
| 59 | Max delay default | 12 h :137 | n/a | n/a | n/a | assumption kept | Note: unreachable since `daafa48` (`_canonical_appliance` rejects anything outside `APPLIANCE_TYPES`). |
| 60 | Cycles/month dishwasher | 18 :141 | 215/yr | ENERGY STAR: "The average cycles per year is 215 cycles per year."; "Standard ≥ 8 place settings + 6 serving pieces ≤ 240 kWh/year"; 10 CFR 430 App. C1: "use N = 215 cycles/year in place of N = 184 cycles/year." | energystar.gov dishwashers key product criteria; eCFR App. C1 | confirmed | Optionally add the App. C1 citation. Note: App. C2 (amended standards) keeps AHAM's 184 (my reading of the fetched text). Inert (budget penalty never binds). |
| 61 | Cycles/month washer | 25 :142-143 | ~300/yr (ENERGY STAR); 295/yr (DOE J2); 234/yr (DOE J) | ENERGY STAR: "The average American family washes about 300 loads of laundry each year."; App. J2: "295 = Representative average number of clothes washer cycles in a year."; App. J: "234 = Representative average number of clothes washer cycles in a year." | energystar.gov/products/clothes_washers; eCFR App. J2 section 4.6, App. J section 4.6 | confirmed | Cite App. J2 (295, which gives 24.6 and rounds to 25) as the regulatory figure. Value unchanged. |
| 62 | Cycles/month dryer | 24 :144 | 283/yr | "DOE revises the number of annual use cycles from the 416 cycles per year currently specified by the DOE test procedure to 283 cycles per year for all types (that is, product classes) of clothes dryers."; App. D1: "283 = Representative average number of clothes dryer cycles in a year." | 76 FR 972 (Jan 6, 2011), quote on p. 977 (govinfo PDF idx 5); eCFR App. D1 | confirmed | Optional note: App. D2 section 4.5.1: "(1) C annual = 283 (2) C annual = 236", with 236 applying from March 1, 2028. Inert. |
| 63 | Cycles/month default | 24 :146 | n/a | n/a | n/a | assumption kept | unreachable since `daafa48` |
| 64 | `calculate_monthly_cost` | :490-491, :562-565 | arithmetic | n/a | n/a | confirmed | none |
| 65 | `calculate_budget_penalty` | :472-488 | design | code continuous at u = 1.0; max utilization recomputed 0.2292 | `app_impact/impact.py` | mismatch (doc figure) | Change "max utilization in calc_new about 0.29" to 0.23 (V_APPLIANCE D5). |
| 66 | Budget penalty application | :567-573 | n/a | Current code: `utility_budget` validated > 0 at :506-508, so the penalty always applies to a scored row | n/a | confirmed | Optional: drop "when `utility_budget` > 0" (now always true for scored rows). |
| 67 | Comfort base curve | :210-219 | design | n/a | n/a | assumption kept | none |
| 68 | `NOISE_LIMIT_EVENING` | 45 :102 | 45 dB LAmax (single events, bedroom, night) | "Indoor guideline values for bedrooms are 30 dB LAeq for continuous noise and 45 dB LAmax for single sound events." Table 4.1, "Inside bedrooms ... Sleep disturbance, night-time 30 [LAeq] 8 [h] 45 [LAmax, fast]". Also: "For a good sleep, it is believed that indoor sound pressure levels should not exceed approximately 45 dB LAmax more than 10–15 times per night (Vallet & Vernet 1991)" | WHO (1999) p. xiii (Executive summary), p. 61 (Section 4.3.1), p. 65 (Table 4.1), p. 46 | replacement proposed | Source the 45 to WHO (1999) 45 dB LAmax. Fix the code comment: WHO's 35 dB LAeq is the daytime/evening dwelling value, and the bedroom night value is 30 dB LAeq,8h. No value change. |
| 69 | Noise: dishwasher | 45 :226-227 | EU class C lower bound 45 dB(A) re 1 pW | "Table 2 Acoustic airborne noise emission classes ... A n < 39 B 39 ≤ n < 45 C 45 ≤ n < 51 D 51 ≤ n"; label value expressed in "(dB(A) re 1 pW)" | Commission Delegated Regulation (EU) 2019/2017, Annex II Table 2 (EUR-Lex CELEX 32019R2017) | replacement proposed | Replace the "Bellingham Electric (2026)" retailer credit with EU 2019/2017 (regulatory class scale; 45 dB(A) sound power). Keep the value. Sensitivity: if the dishwasher were above the threshold, 1 of 100 winners and 6 of 100 rankings would change. |
| 70 | Noise: washer | 74 (spin) :228-229 | EU spin class B 73-77 dB re 1 pW | "Table 4 Acoustic airborne noise emission classes Phase ... Noise (dB) Spinning A n < 73 B 73 ≤ n < 77 C 77 ≤ n < 81 D n ≥ 81"; label: "airborne acoustic noise emissions of the spinning phase, expressed in dB(A) re 1 pW" | Commission Delegated Regulation (EU) 2019/2014, Annex II Table 4 (CELEX 32019R2014) | replacement proposed | Replace the "Precision Appliance Leasing (2024)" credit with EU 2019/2014. Value unchanged. Only the > 45 test reads it, so there is no GT effect. |
| 71 | Noise: dryer | 65 :230-231 | EU class C 64-68 dB(A) sound power; measured 64.8 dB(A) | EU: "Table 2 Acoustic airborne noise emission class ... A L WA ≤ 60 B 60 < L WA ≤ 64 C 64 < L WA ≤ 68 D L WA > 68" ("weighted average value (L WA) of the sound power in the eco programme"); Čurović et al. (2022) abstract: "the A-weighted sound power level was reduced from 64.8 to 60.4 dB" | Commission Delegated Regulation (EU) 2023/2534, Annex II section 2 (CELEX 32023R2534); Čurović et al. (2022) *Applied Acoustics*, abstract via Consensus (https://consensus.app/papers/details/b6b5542fa7135f1d9347041ea7f98a77/) | replacement proposed | Replace the "Coolblue (2026)" credit with EU 2023/2534 and/or Čurović et al. (2022). Value unchanged. The Čurović full text was not opened (sciencedirect blocked); the quote is from the abstract. |
| 72 | Noise: other | 50 :232-233 | n/a | n/a | n/a | assumption kept | unreachable since `daafa48` |
| 73 | Noise window | 22 <= h or h < 7 :237 | night = 10 p.m.-7 a.m. | 24 CFR 51.103: "Day-night average sound level, abbreviated as DNL and symbolized as L dn, is the 24-hour average sound level, in decibels, obtained after addition of 10 decibels to sound levels in the night from 10 p.m. to 7 a.m."; 14 CFR 150.7: "... obtained after the addition of ten decibels to sound levels for the periods between midnight and 7 a.m., and between 10 p.m., and midnight, local time."; Pittsburgh Code 601.04 Table A: "Nighttime: 10:00 p.m.- 7:00 a.m. ... Residential 65 dB(A) 60 dB(A)" [dash rendered as a hyphen] | eCFR 24 CFR 51.103(a); 14 CFR 150.7; Pittsburgh Code 601.04 (nonoise.org 2015 print) | replacement proposed | Cite 24 CFR 51.103 (and Pittsburgh 601.04, which covers the Pittsburgh/McKeesport scenarios) for 10 p.m.-7 a.m. Note: the Philadelphia Code ch. 10-400 has no general night window (its limits apply around the clock; only source-specific hours such as "Construction between the hours of 7 a.m. and 8 p.m."). WHO 1999 uses an 8 h night; WHO Night Noise Guidelines use 23:00-07:00, which would change 1 of 100 winners. |
| 74 | Noise penalty base | 2.0 :239 | design | n/a | n/a | assumption kept | none |
| 75 | Noise housing multipliers | 1.5 / 1.2 / 0.8 :242-247 | design | n/a | n/a | assumption kept | none (scenario housing types are exactly Apartment, Condo, Townhouse, Rowhouse, Single-family, so the string matches work) |
| 76 | Comfort household-size penalty | :251-259 | design | n/a | n/a | assumption kept | none |
| 77 | Comfort final | :261-262 | design | n/a | n/a | assumption kept | none |
| 78 | Practicality base curve | :267-278 | design | n/a | n/a | assumption kept | none |
| 79 | Practicality timing penalty | 2.0 / 1.0 :282-286 | design; Paetz paraphrase checked | Paetz: "If low-price or mid-price zones applied on the brink of a day, it was perceived as too early or too late as to comply with them." | Paetz (2012) p. 7-231 | assumption kept | The code comment paraphrase at :281 is faithful. Numbers remain ours. |
| 80 | Practicality coordination penalty | :290-298 | design | n/a | n/a | assumption kept | none |
| 81 | Practicality daytime floor | 0.4 :302-308 | design | 0.4/10 = 0.04 < clamp 0.15, so it is never active | :305-310 | assumption kept | none |
| 82 | Practicality final clamp | [0.15, 1.0] :310 | design | n/a | n/a | assumption kept | none |
| 83 | `parse_alternative` delay | circular min distance :339-344 | design | n/a | n/a | assumption kept | none |
| 84 | DISAGREEMENT: baseline-time fallback | raises `ValueError` :336-337, :347-374 | current behavior | "Anything else raises so the caller emits the sentinel; a baseline is never guessed." | :350-351 | confirmed (current behavior; doc fix pending by another agent) | none here |
| 85 | DISAGREEMENT: unknown appliance | `_canonical_appliance` :121-128, called :505 | current behavior | "Anything outside APPLIANCE_TYPES raises, so the caller emits the sentinel" | :122-124 | confirmed (current behavior) | none here. Knock-on: rows 59, 63 and 72 are now unreachable defaults. |
| 86 | DISAGREEMENT: `utility_budget` | :506-508 inside the try | current behavior | `if not utility_budget > 0: raise ValueError(f"utility_budget must be positive: {utility_budget!r}")` | :507-508 | confirmed (current behavior) | none here |
| 87 | Sentinel emission | try/except :504-531, fill :544-553 | CLAUDE.md convention | "Sentinel `1928` marks a failed/invalid score" | CLAUDE.md | confirmed | none |
| 88 | Output rounding | :594-599 | 2 / 4 / 3 dp | n/a | n/a | confirmed | none |
| 89 | Criterion weights | `model_config.py:20-25`: energy_cost 0.30, environmental 0.35, comfort 0.20, practicality 0.15 | n/a | code: `"energy_cost": 0.30, "environmental": 0.35` | `model_config.py:20-25` | mismatch | Provenance line 230 says "energy 0.35, environmental 0.30". Correct it to energy 0.30, environmental 0.35 (as in the HVAC row, line 106). |
| 90 | kWh/cycle | scenario input :514-516 | scenario data | not re-checked | n/a | assumption kept | none |

### Not opened / blocked

- **WHO (1999) at iris.who.int.** The PDF opened, but it is an image-only scan (CCITT fax pages, no text layer), and neither OCR nor PIL is available. Quotes come from the text-layer mirror at docs.wind-watch.org, a third-party copy of the same document.
- **Pittsburgh Code 601.04 on ecode360.com**: 403 to both curl and WebFetch. apps.pittsburghpa.gov (noise amendments PDF): connection reset. Used the nonoise.org 2015 print instead, so the current official text is not verified.
- **quakertown.org electric department page**: 403. The Quakertown municipal-utility claim was not re-verified this session; its absence from all three tariff lists was verified.
- **Numeric sources for the washer 8 h and dryer 6 h ceilings:**
  - D'hulst et al. (2015) and Klaassen et al. (2016, *Applied Energy*): sciencedirect, blocked.
  - Klaassen et al. (2016, IEEE ENERGYCON): not opened.
  - LINEAR final report (emis.vito.be): the URL returned an HTML page, not the PDF.
  - Smart-A D5.5 consumer-acceptance report (smart-a.org): site offline (HTTP returns a generic page, HTTPS certificate error).
  - Semantic Scholar API: 429 rate limit.
- **Čurović et al. (2022) full text** (sciencedirect, blocked). Only the abstract was read, via Consensus.
- **Dyer & Sarin (1979)**: not opened; outside this review's physical/economic scope.
- **Newer PJM emissions report (2023-2025 data)**: guessed pjm.com URLs returned an HTML page, not a PDF, so the 2022 report remains the one verified.
- **ENERGY STAR clothes dryers page**: opened, but it states no cycles per year, so DOE 76 FR 972 and App. D1/D2 were used.

---

## 4. Shower constant value review (`value_review/SHOWER.md`)

Scope: every row of the Shower section of `docs/CALCULATOR_PROVENANCE.md` (lines 233-295; 39 rows).
Code checked: `Ground Truth Calculators/ShowerGroundTruthCalculator.py` (read in full 2026-09-27). No repo
file was edited. Impact estimates used patched copies of the calculator in the session scratchpad
(`scratchpad/impact/shower_impact.py`, `scratchpad/impact/bounds.py`), run over the 80 master scenarios in
`Scenario Files/ShowerScenarios.xlsx` (60 Test + 20 RAG), ranked with `sentinel_utils.apply_mavt_ranking`.
Mains-temperature numbers come from `scratchpad/mains.py` on six PA TMY3 EPW files from
climate.onebuilding.org.

### Summary

39 rows reviewed. Every code line citation in the section matches the current file (no drift).

| Verdict | Count |
|---|---|
| confirmed (value and source agree, or code/design row matches its description) | 17 |
| mismatch (this row also carries a replacement) | 1 |
| assumption kept | 19 |
| replacement proposed | 2 |

Mismatch: the audit summary quoted for the inlet rows gives Burch & Christensen ranges of "Pittsburgh ~47-69 F,
Philadelphia ~50-74 F". Recomputed from TMY3 with HSP Eq. 26 (the published form of the Burch & Christensen
correlation) the ranges are Pittsburgh 46.4-67.7 F and Philadelphia 48.6-73.3 F. The description "runs ~2-5 F
low" holds on average (pooled mean bias -3.0 F) but the monthly error spans -10.7 to +3.8 F, because the
mains lag ambient by about a month and a function of outdoor temperature alone cannot represent that.
This is a mismatch in the recorded summary, not in the code; it is counted on the `INLET_TEMP_WINTER` row
only.

Proposed changes, ranked by likely ground-truth impact:

1. `INLET_TEMP_WINTER` 45 F to 48.5 F and `INLET_TEMP_SUMMER` 65 F to 68.2 F (one change; counted as two
   rows). A least-squares line through the Burch & Christensen / HSP Eq. 26 mid-month mains temperature
   against monthly mean outdoor temperature, pooled over six PA TMY3 stations (Allentown, Erie, Harrisburg,
   Philadelphia, Pittsburgh, Wilkes-Barre/Scranton; 72 station-months), is T_mains = 33.87 + 0.457 x T_out,
   i.e. 48.5 F at 32 F and 68.2 F at 75 F (RMSE 3.6 F vs 4.8 F for the current line). Keep the linear form and
   the 32/75 F breakpoints. The energy-cost value-function bounds must then be recomputed with the same
   rule (p5/p95 become $0.1349/$1.0691, i.e. 0.13/1.07). Impact: raw per-shower cost falls 6.8% on average;
   with bounds recomputed, 1 of 80 scenarios changes its top-1 and 2 of 80 change their full ranking (2 and 3
   of 80 if the bounds are left at 0.14/1.14).
2. `showers_per_person_per_day` 0.9 to 0.69 (REU2016 as reported by Gauley and Koeller 2017; the 2014 HSP
   event table implies 0.64). Impact: none on current data. Only one Shower alternative reaches the 0.80
   budget-utilization threshold (u = 0.905); its energy value is already clamped at 0, so no score changes.
   The change makes the budget penalty less likely to fire in future scenario sets.

Sensitivity checks on "assumption kept" rows (no change proposed, reported so the author can judge):
`TARGET_SHOWER_TEMP` 110 F (the HSP value) changes 1/80 top-1 and 5/80 full rankings; usable tank fraction
0.70 or 1.00 changes 3/80 top-1 each; `COMFORT_TEMP_REFERENCE_F` 65 F changes 3/80 top-1.

Source-only upgrades (value unchanged, a primary source now exists): `TARGET_SHOWER_TEMP` 105 F is the
ANSI/RESNET/ICC 301-2019 mixed-water temperature (as reported by LBNL, Chen et al. 2020);
`COMFORT_DURATION_OPTIMAL` 7.8 min is also the HSP 2014 Table 12 average shower duration.

### Source keys used below

- **CFR 430.32**: 10 CFR 430.32, eCFR current text, https://www.ecfr.gov/current/title-10/chapter-II/subchapter-D/part-430/subpart-C/section-430.32
  (fetched through the eCFR renderer API).
- **CDC**: https://www.cdc.gov/control-legionella/php/guidance/monitor-water-guidance.html (no page date found in the HTML).
- **B&C 2007**: Burch, J. and Christensen, C., "Towards Development of an Algorithm for Mains Water
  Temperature", 6 pp., https://www.energystar.gov/ia/partners/prod_development/new_specs/downloads/water_heaters/AlgorithmForMainsWaterTemperature.pdf
- **HSP 2010**: Hendron, R. and Engebrecht, C. (2010), Building America House Simulation Protocols (Revised),
  NREL/TP-550-49246, https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/house_simulation_revised.pdf
  (same file as https://www.osti.gov/servlets/purl/989422). Printed page = PDF page - 8.
- **HSP 2014**: Wilson, E. et al. (2014), 2014 Building America House Simulation Protocols, NREL/TP-5500-60988,
  https://www.osti.gov/servlets/purl/1126820. Printed page = PDF page - 9.
- **LBNL 2020**: Chen, Y., Fuchs, H., Schein, J., Franco, V., Stratton, H., Dunham, C. (2020), Calculating
  Average Hot Water Mixes of Residential Plumbing Fittings, LBNL, https://www.osti.gov/servlets/purl/1619186
- **REU2016 ER**: DeOreo et al. (2016), Residential End Uses of Water, Version 2: Executive Report, WRF,
  copy at https://www.circleofblue.org/wp-content/uploads/2016/04/WRF_REU2016.pdf (Circle of Blue, a
  nonprofit news site; no government or utility copy was found).
- **MaP 2017**: Gauley, B. and Koeller, J. (2017), Residential Showering Time-of-Day Analysis (MaP report
  analysing REU2016 shower data), https://map-testing.com/wp-content/uploads/2022/10/Time-of-Day_shower_report-Jan_20-2017.pdf
- **Zhang 2023**: Zhang, D., Mui, K.-W., Wong, L.-T. (2023), Establishing the Relationship between Occupants'
  Thermal Behavior and Energy Consumption during Showering, Buildings 13(5) 1300,
  https://mdpi-res.com/d_attachment/buildings/buildings-13-01300/article_deploy/buildings-13-01300.pdf
- **Ibanez-Rueda 2023**: Ibanez-Rueda, Guardiola, Lopez-Ruiz, Gonzalez-Gomez (2023), Towards a sustainable
  use of shower water, Sustainable Water Resources Management 9:121, doi 10.1007/s40899-023-00905-3;
  abstract read via https://api.crossref.org/works/10.1007/s40899-023-00905-3 (Springer page returned a
  JavaScript challenge).
- **EIA EPA T2.10**: https://www.eia.gov/electricity/annual/html/epa_02_10.html
- **App E**: 10 CFR 430 Subpart B Appendix E (water heater test procedure), eCFR current text.
- **TMY3**: climate.onebuilding.org PA_Pennsylvania TMY3 EPW files (stations 723990, 724080, 725200,
  725260, 725170, 725130).

### Table

All code locations are in `Ground Truth Calculators/ShowerGroundTruthCalculator.py` (abbreviated `SGTC`).

| constant | code value (file:line) | source value | verbatim quote | page/URL | verdict | proposed change |
|---|---|---|---|---|---|---|
| `ELECTRICITY_RATE_PA` | 0.19 $/kWh (SGTC:29) | EIA PA residential 17.77 c/kWh (2024), 18.10 (2023) | "Pennsylvania 17.77 18.10" (Residential, Year 2024, Year 2023 columns) | EIA EPA T2.10 | confirmed (EIA context figure matches the row; the PA PUC derivation of 0.19 was not re-checked here; `HVAC.md` in this folder reports it does not reproduce 0.19 while EIA 2025 at 19.30 c/kWh supports it) | none here; follow `HVAC.md` for the shared constant |
| `INLET_TEMP_WINTER` | 45 F at outdoor <= 32 F (SGTC:36) | B&C / HSP Eq. 26 on PA TMY3: annual minimum 43.9 (Harrisburg) to 48.6 F (Philadelphia); pooled linear fit gives 48.5 F at 32 F outdoor | B&C: "The average value of Tmains is Tamb,ann plus an offset ∆Toffset ≈ 6 oF. The amplitude is given as R∆Tamb, with R ≈ 0.4". HSP 2010: "ratio = 0.4 + 0.01 (Tamb,avg – 44)", "lag = 35 – 1.0 (Tamb,avg – 44)", "offset = 6°F" | B&C p. 5 (Conclusions), Table 2 p. 5; HSP 2010 Eq. 26, printed p. 56 (PDF p. 64) | mismatch (recorded audit ranges differ; see Summary) and replacement proposed | 45 F to 48.5 F |
| `INLET_TEMP_SUMMER` | 65 F at outdoor >= 75 F (SGTC:37) | B&C / HSP Eq. 26 annual maximum 65.7 (Erie) to 73.3 F (Philadelphia); pooled fit 68.2 F at 75 F | as above | as above | replacement proposed | 65 F to 68.2 F |
| `determine_inlet_temp` | linear 45 to 65 F over outdoor 32-75 F, span/43 (SGTC:102-112) | Monthly PA error of the current line vs Eq. 26: mean -3.0 F, RMSE 4.8 F, range -10.7 F (Oct, Philadelphia) to +3.8 F (Apr, Harrisburg) | HSP 2010: "Equation 26, based on TMY3 data for the location of the Test House, shall be used to determine the daily mains water temperature for all models" | HSP 2010 printed p. 55-56 (PDF p. 63-64) | assumption kept (linear-in-outdoor form is a simplification the scenarios force: they carry an outdoor temperature but no date) | keep form; only the two anchors change. Note: B&C Table 2 prints K4 = "-0.01 Deg/ oF" while HSP Eq. 26 uses 1.0; the fit above uses the HSP form (annual min/max are unaffected by the lag) |
| `ELECTRIC_HEATER_EFFICIENCY` | 0.92 (SGTC:43) | 0.9307 - 0.0002 x 50 = 0.9207 | "( d ) Water Heaters. ( 1 ) The uniform energy factor of water heaters manufactured before May 6, 2029, shall not be less than the following: ... Electric Storage Water Heaters ≥20 gal and ≤55 gal ... Medium 0.9307 − (0.0002 × V r )" | CFR 430.32(d)(1) | confirmed | none |
| `TARGET_SHOWER_TEMP` | 105 F (SGTC:44) | ANSI 301-2019 Tmix 105 F (via LBNL 2020); HSP uses 110 F; Zhang 2023 32-40 C | LBNL 2020: "Warm water temperatures (Tmix) for showers are assumed to be 105 °F based on ANSI 301-2019." Zhang 2023: "The water temperature was assumed to be 32–40 °C, and the air temperature was assumed to be 20–40 °C." HSP 2014: "the mixed temperature for showers, sinks, and baths shall be 110°F" | LBNL 2020 printed p. 8 (PDF p. 12), sec. 4.3; Zhang 2023 p. 5; HSP 2014 printed p. 49 (PDF p. 58) | confirmed (Zhang quote verified; the value now has a standards source) | cite ANSI 301-2019 via LBNL 2020 instead of "our delivery convention"; 110 F sensitivity: 1/80 top-1, 5/80 rankings |
| `WATER_DENSITY` | 8.33 lb/gal (SGTC:45) | physical property | none | n/a | confirmed | none |
| `BTU_PER_KWH` | 3412 (SGTC:46) | unit conversion | none | n/a | confirmed | none |
| `calculate_hot_water_fraction` | (105 - T_in)/(T_heater - T_in), clamped [0, 1] (SGTC:134-141) | two-stream energy balance | none | n/a | confirmed | none |
| `calculate_shower_energy` | gpm x f x 8.33 x (T_heater - T_in) x min / (3412 x 0.92) (SGTC:114-132) | derived | none | n/a | confirmed (the comment at SGTC:269 writes the equivalent form with (105 - inlet); identical whenever f is not clamped) | none |
| `calculate_environmental_impact` | gallons = gpm x minutes (SGTC:147-149) | project convention (CLAUDE.md) | none | n/a | assumption kept (metric choice) | none |
| `COMFORT_DURATION_OPTIMAL` | 7.8 min (SGTC:52) | 7.8 min | REU2016 ER: "REU2016 shows minimal change in showering patterns. The average duration held steady at 7.8 minutes per shower." HSP 2014 Table 12: "Average duration (min) 0.62 7.8 5.65 0.96 1.38" (Sink, Shower, Bath, CW, DW) | REU2016 ER p. 9; HSP 2014 printed p. 15 (PDF p. 24) | confirmed | optionally add HSP 2014 Table 12 as a government-lab source |
| `COMFORT_TEMP_REFERENCE_F` | 77 F (SGTC:64) | none opened; ASHRAE 55-2020 not accessible. Nearest sourced anchor: HSP cooling set point 76 F from ASHRAE 55-2004 (an indoor thermostat value, not an outdoor reference) | HSP 2010: "Thermostat set points based on the optimum seasonal temperature for human comfort as defined in ASHRAE Standard 55-2004 (ASHRAE 2004b). Set point for cooling: 76°F with no setup period" | HSP 2010 printed p. 49 (PDF p. 57) | assumption kept (curve breakpoint, a design choice) | none; 65 F sensitivity: 3/80 top-1 |
| `COMFORT_TEMP_ELASTICITY_PER_F` | 0.10/10.8 (SGTC:65) | none | none | n/a | assumption kept (design) | none |
| `COMFORT_TEMP_MAX_MULTIPLIER` | 11.6/8.8 = 1.318 (SGTC:66) | 8.8 min summer, 11.6 min winter | "The study is carried out with data from 945 students of the University of Granada, Spain. Significant differences are observed in shower use during the summer and winter months: the average duration is 8.8 and 11.6 min, respectively" | Ibanez-Rueda 2023 abstract (Crossref) | confirmed | none |
| `COMFORT_DURATION_MAX` | 15 min (SGTC:53) | Harris 2024 Q4 shares (not re-opened) | not re-verified (theharrispoll.com returned HTTP 403) | https://theharrispoll.com/articles/shower-habits/ (blocked) | assumption kept (ceiling is ours; prevalence quote not re-verified) | none |
| `COMFORT_DURATION_MIN` | 5 min (SGTC:51) | none | none | n/a | assumption kept (design breakpoint) | none |
| comfort duration curve | cubic to 3 min; linear to optimum; linear to 15 min; -0.5/min, floor 1.0 (SGTC:169-185) | none | none | n/a | assumption kept (design) | none |
| comfort heater band | no penalty 120-140 F; -2.0 below; -1.0 above (SGTC:86-87, 187-191) | CDC 120 F circulation floor, 140 F storage | "Store hot water at temperatures above 140°F (60°C). Ensure hot water in circulation doesn't fall below 120°F (49°C) and recirculate hot water continuously, if possible." | CDC, "Hot water guidance" | confirmed (anchors); penalty sizes remain our assumption | none |
| `HEATER_TEMP_OPTIMAL` | 120 F (SGTC:72) | 120 F | as above | CDC | confirmed | none |
| `HEATER_TEMP_LEGIONELLA_SAFE` | 140 F (SGTC:74) | 140 F | "Store hot water at temperatures above 140°F (60°C)." | CDC | confirmed | none |
| `HEATER_TEMP_MINIMUM` | 110 F, unused (SGTC:71) | CDC growth range 77-113 F | "Legionella grows best between 77°F–113°F (25°C–45°C)." | CDC, "Measure water temperature" | confirmed (quote); value itself is ours and unused | none |
| `HEATER_TEMP_SCALD_RISK` | 130 F, unused (SGTC:73) | Moritz & Henriques 1947, Am J Pathol 23(5):695-720 (PMID 19970955, PMC1934304); full text is a page scan, 130 F / 30 s claim not located | not verified | https://pubmed.ncbi.nlm.nih.gov/19970955/ | assumption kept (unused constant) | none |
| comfort contention | 0.5 per min above optimum, >= 4 occupants (SGTC:195-197) | none | none | n/a | assumption kept (design) | none |
| practicality duration curve | piecewise, floor 1.5 (SGTC:205-222) | none | none | n/a | assumption kept (design) | none |
| tank availability | usable = 0.80 x tank (SGTC:232) | No primary gives a fixed usable fraction. The DOE first-hour-rating test ends each draw on a 15 F outlet drop, so usable volume is a test outcome, not a constant | App E 5.3.3.3: "Terminate the hot water draw when the outlet temperature decreases to T* max,1 −15 °F (T* max,1 −8.3 °C)." | App E sec. 5.3.3.3 | assumption kept | none; 0.70 and 1.00 each change 3/80 top-1 |
| capacity penalty | -3.0 if need > available; clamp [0.15, 1.0] (SGTC:234-240) | none | none | n/a | assumption kept (design) | none |
| showers per person per day | 0.9 (SGTC:243 default, SGTC:450 call) | 0.69 (REU2016, per MaP 2017); HSP 2014 implies 1.7 events/day / 2.64 occupants = 0.64; REU2016 ER arithmetic 11.1 gpcd shower / (7.8 min x 2.1 gpm) = 0.68 | MaP 2017: "REUS2016 determined that showering currently accounts for about 19% of indoor residential water demands; that people take an average of 0.69 showers per day; and that the average shower duration is about 7.8 minutes long." HSP 2014 Table 12: "Average daily events (events/day) 32.9 1.7 0.3 2.2 2.4" (NCTH with three bedrooms); HSP 2014: "Number of occupants = 0.59 × Nbr + 0.87 (23)" | MaP 2017 p. 3; HSP 2014 printed p. 15 and p. 62 (PDF p. 24, 71) | replacement proposed | 0.9 to 0.69 (both SGTC:243 and SGTC:450); no score change on current data |
| days per month | 30 (SGTC:244) | month length | none | n/a | confirmed | none |
| `calculate_budget_penalty` | 1.0 below u = 0.80; 1 - 2.5(u - 0.8) to 1.0; 0.5 e^(-3(u-1)) (SGTC:247-261) | paper states these are our choices | none (design) | n/a | assumption kept (design) | none |
| energy_cost bounds | 0.14 / 1.14 (SGTC:276-277) | recomputed p5 0.1449, p95 1.1354 over 240 alternatives of 80 master rows | none (computed) | `scratchpad/impact/bounds.py` | confirmed | if the inlet change is adopted, recompute: 0.13 / 1.07 |
| environmental bounds | 6.0 / 45.0 gal (SGTC:286-287) | recomputed p5 6.00, p95 45.00 | none (computed) | same | confirmed | none (unchanged by the inlet change) |
| practicality VF floor | 0.05 / 1.0 (SGTC:301-302) | none | none | n/a | assumption kept (design) | none |
| comfort VF range | 0.0 / 1.0 (SGTC:291-292) | raw comfort already on [0, 1] | none | n/a | confirmed | none |
| `calculate_scenario_scores` defaults | household 2, tank 40, 2.5 gpm, 50 F, 120 F (SGTC:366-370) | fallbacks; master sheet supplies every field | none | n/a | assumption kept | none; note the tank fallback (40) differs from the Fixed-Default baseline's 50 gal (see BASELINES.md) |
| `VF_ENERGY_COST` linear | SGTC:91, 316-324 | Dyer & Sarin 1979 (Oper. Res. 27(4)) not opened (paywalled) | not verified | n/a | assumption kept (quote in code comment still unverified) | none |
| `VF_ENVIRONMENTAL` linear | SGTC:98, 316-324 | modelling choice | none | n/a | assumption kept | none |
| `VF_COMFORT` log a = 1.5 | SGTC:99, 345-358 | none | none | n/a | assumption kept | none |
| `VF_PRACTICALITY` log a = 1.2 | SGTC:100, 345-358 | none | none | n/a | assumption kept | none |

#### PA mains temperature detail (HSP Eq. 26 on TMY3)

| Station (TMY3) | T_amb annual (F) | max monthly difference (F) | T_mains min / max (F) | mean (current line - Eq. 26) over 12 months (F) |
|---|---|---|---|---|
| Allentown 725170 | 51.7 | 48.9 | 46.1 / 69.4 | -3.2 |
| Erie 725260 | 49.1 | 47.2 | 44.4 / 65.7 | -1.6 |
| Harrisburg 723990 | 51.5 | 57.3 | 43.9 / 71.1 | -2.9 |
| Philadelphia 724080 | 54.9 | 48.5 | 48.6 / 73.3 | -5.3 |
| Pittsburgh 725200 | 51.0 | 45.2 | 46.4 / 67.7 | -2.9 |
| Wilkes-Barre/Scranton 725130 | 49.8 | 45.7 | 45.4 / 66.3 | -2.1 |

### Not opened / blocked

- Harris Poll 2024 shower-habits article and Q4 tabulation: theharrispoll.com returned HTTP 403 (curl and
  WebFetch). The "15 Minutes Or Less (Net) 66%" / "More Than 15 (Net) 33%" quote is not re-verified.
- Ibanez-Rueda 2023 full text: link.springer.com served a JavaScript challenge; only the Crossref abstract
  was read (it contains the quoted figures).
- Zhang 2023 HTML on www.mdpi.com: HTTP 403; the PDF on mdpi-res.com was read instead.
- REU2016 full report (WRF #4309): not openly available; only the Executive Report was read. No government
  or utility copy was found; the one read is hosted by Circle of Blue.
- OSTI 981988 landing page for Burch & Christensen was not fetched; the energystar.gov copy of the same
  paper was read.
- ASHRAE 55-2020 (for the 77 F reference): not accessible.
- Moritz & Henriques 1947: PubMed metadata only; the scanned full text was not searched.
- Dyer & Sarin 1979; Keeney & Raiffa 1976: not opened (paywalled / book).
- PA PUC 2025 default-service derivation of $0.19: not re-checked here (see `HVAC.md`).
- *.nrel.gov was not used (blocked); HSP documents were read from osti.gov and www1.eere.energy.gov.

---

## 5. Baselines constant value review (`value_review/BASELINES.md`)

Scope: every row of the Baselines section of `docs/CALCULATOR_PROVENANCE.md` (lines 297-361; 38 table rows
plus the header notes). Code checked: `Miscellaneous Scripts/core-automation/run_baseline_models.py`
(`RBM`, 520 lines, read in full) and `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`
(`HAB`, 1,556 lines; lines 1-200 and 612-975 read, the rest mapped by `def` index). No repo file was
edited. The dataset-median (DM) constants were recomputed by calling `HAB.compute_defaults()` (reads the
scenario workbooks only; no API call). Fixed-default (FD) impact estimates used
`scratchpad/impact/fd_impact.py`, which patches RBM module constants in memory and scores every Test
scenario against the reference built by HAB's own `build_scenario(..., true_params(...))`; top-1 and
Kendall tau are single deterministic runs and may differ slightly from the paper's pipeline numbers.

### Summary

38 rows reviewed.

| Verdict | Count |
|---|---|
| confirmed (value and source agree, or code/design row matches its description) | 7 |
| mismatch | 21 |
| assumption kept | 8 |
| replacement proposed | 2 |

Of the 21 mismatches, 14 are the dataset-median rows: every value is confirmed by recomputation, but every
`HAB` line citation has drifted (corrected list below). The other 7:

- FD HVAC electricity rate: the calculator comment quoted in the row ("rising to ~19-21 c/kWh through
  2025") no longer exists; `HVACGroundTruthCalculator.py:29-31` now reads "(Table 2.10; PA residential avg
  17.77 c/kWh in 2024). 0.19 is the bundled default-service rate ... not an EIA figure." Value unchanged.
- NN index and encoder, NN query text, NN prediction: the `run_rag_ablation_experiments.py`,
  `sentinel_utils.py` and `Architectures/Example-Guided_LLM_Scoring.py` line numbers are stale (corrected
  in the table). NN prediction also gained a `fallback` option (`tie` / `nearest` / `unscored`,
  `NN_FALLBACKS` at L730); the default `tie` is the rule the row describes.
- NN excluded self-match id: the line is `RBM` L370, not L371.
- Random and Uniform: the row says they are "Not reachable from the CLI". They are: `--baseline` (`RBM`
  L496, `type=str`, no `choices`) is copied into the run list at L509 (`if args.baseline: baselines =
  [args.baseline]`), so `--baseline random` or `--baseline uniform` runs them.

Proposed changes, ranked by likely ground-truth impact (FD baseline metrics; the reference ground truth is
not affected by any baseline constant):

1. FD shower tank size 50 gal to 40 gal. RECS 2020 puts the Pennsylvania median household water heater in
   the "Medium (31 to 49 gallons)" band (cumulative 60.5% of PA households through that band; 60.3% for
   electric water heaters); 50 gal sits in the "Large (50 gallons or more)" band, which holds 33.8%.
   40 gal is not a RECS number: it is a representative size inside the median band, and it equals the
   master-sheet mode (31 of 80) and the Shower calculator's own fallback (`SGTC:367`). Impact: Shower FD
   top-1 0.850 to 0.833 (1 of 60 scenarios), mean tau 0.800 to 0.789.
2. FD dryer kWh/cycle 2.10 to 2.27. 8.45 lb DOE test load / 3.73 lb/kWh (2015 federal minimum CEF, vented
   electric standard) = 2.27 kWh per test cycle. This is the energy of a minimum-compliant new dryer on the
   DOE test cycle; the installed stock is older and the master sheet's dryer median is 3.0, so 2.27 is a
   sourced lower-end figure, not a stock average. Impact: Appliance FD top-1 unchanged (0.323), mean tau
   0.190 to 0.179.

Source-only upgrades (value unchanged, a primary source now exists): FD SEER 13 (10 CFR 430.32(c)(1)
minimum for split-system ACs, 2015-2022, and ResStock's modal central-AC option "AC, SEER2 12.4"); FD
shower 2.5 gpm (10 CFR 430.32(p) maximum). Values checked and kept with a documented bracket: FD HVAC age 13
(RECS 2020 PA median main heating equipment age is in the 10-14 year band; the central-AC median is in the
5-9 year band; FD age 7 changes no HVAC top-1), FD setpoint 120 F (DOE test procedure, ANSI 301-2019 and HSP
2014 use 125 F; field averages 123-127 F; 125 F changes Shower FD top-1 0.850 to 0.833).

### Table

| constant | code value (file:line) | source value | verbatim quote | page/URL | verdict | proposed change |
|---|---|---|---|---|---|---|
| DM statistic set | 35 HVAC / 35 Appliance / 20 Shower retrieval rows (`HAB` L647-686 `retrieval_set_rows`, L689-709 `compute_defaults`) | recomputed: 35 / 35 / 20 rows, identity check against the RAG sheets passes | none (computed) | `HAB.compute_defaults()` | mismatch (line citation only; doc says L625-664, L667-689) | fix lines |
| DM R-value | 16.0 (`HAB` L703) | recomputed 16.0 | none (computed) | same | mismatch (line citation; doc says L681) | fix line |
| DM SEER | 13.0 (`HAB` L703) | recomputed 13.0 | none | same | mismatch (line citation) | fix line |
| DM HVAC age | 16.0 (`HAB` L703) | recomputed 16.0 | none | same | mismatch (line citation) | fix line |
| DM occupancy | `standard`, 14 of 35 (`HAB` L704-707); calculator maps `standard` to `occupied_all_day` at `HVACGroundTruthCalculator.py:392-393` | recomputed: standard 14, unoccupied_8hr 6, overnight_sleep 4, occupied_all_day 4 (14 + 4 = 18 as stated) | none | same | mismatch (line citation; doc says L682-685; the HVAC-calculator lines L392-393 are correct) | fix line |
| DM kWh/cycle | 1.2 (`HAB` L703) | recomputed 1.2 | none | same | mismatch (line citation) | fix line |
| DM appliance type | `dryer`, 13 of 35 (`HAB` L704-707) | recomputed dryer 13, washing_machine 11, dishwasher 11 | none | same | mismatch (line citation) | fix line |
| DM baseline time | `9:00 AM`, 6 of 35 (`HAB` L704-707; `_canonical_clock` L636-644) | recomputed 9:00 AM 6, 10:00 AM 4, 2:00 PM 4 | none | same | mismatch (line citations; doc says L682-685 and L614) | fix lines |
| DM shower GPM | 2.25 (`HAB` L703) | recomputed 2.25 | none | same | mismatch (line citation) | fix line |
| DM tank size | 45.0 (`HAB` L703) | recomputed 45.0 | none | same | mismatch (line citation) | fix line |
| DM setpoint | 120.0 (`HAB` L703) | recomputed 120.0 | none | same | mismatch (line citation) | fix line |
| DM tie in a mode | first in sorted order, `mode().iloc[0]` (`HAB` L707) | no current mode is tied (14 vs 6; 13 vs 11; 6 vs 4) | none | same | mismatch (line citation; doc says L685) | fix line |
| DM what is read | homeowner fields + alternatives from the master row; hidden params from the arm (`HAB` L716-749 `build_scenario`; key whitelist L744-747) | code matches the description | none | n/a | mismatch (line citation; doc says L694-719) | fix lines |
| DM scoring and failures | calculator exception returns None (`HAB` L759-798 `score_scenario`); ranking by `apply_mavt_ranking` in `scenario_metrics` L805-839 (calls at L819-820); failure recorded in `run()` L955-967 | code matches the description | none | n/a | mismatch (line citation; doc says L722-760, L768-800) | fix lines |
| FD R-value | 15 (`RBM` L52, used L173) | No primary source gives a single whole-envelope R for PA homes (the calculator uses U = 1/R for the whole envelope). Context only: ResStock wall-cavity distribution for PA's region CR07 is 61.6% uninsulated, R-7 11.3%, R-11 15.8%, R-15 0.8%, R-19 10.5%; RECS 2020 PA self-reported insulation: well 27.3%, adequately 48.6%, poorly 21.2%, not 2.8% | ResStock `Location Region.tsv`: "PA 0 0 0 0 0 1 ..." (Option=CR07 column = 1); RECS codebook ADQINSUL: "1 Well insulated 2 Adequately insulated 3 Poorly insulated 4 Not insulated" | https://raw.githubusercontent.com/NREL/resstock/develop/project_national/housing_characteristics/Insulation%20Wall.tsv ; https://www.eia.gov/consumption/residential/data/2020/csv/recs2020_public_v7.csv | assumption kept (wall-cavity R and the calculator's envelope R are different quantities; the scenario median is 16) | none |
| FD SEER | 13 (`RBM` L53, used L174) | 10 CFR 430.32(c)(1): split-system AC minimum 13 SEER (2015 to 2022, PA is outside the SEER-14 regions); ResStock central-AC efficiency, weighted over all vintages: SEER2 12.4 56.5%, SEER2 14.3 23.2%, SEER2 9.5 11.4%, SEER2 7.6 1.7% (12.4 / 13 = 0.95, the SEER2/SEER ratio) | "( 1 ) Central air conditioners and central air conditioning heat pumps manufactured on or after January 1, 2015, and before January 1, 2023, must have Seasonal Energy Efficiency Ratio and Heating Seasonal Performance Factor not less than: " (table row (i), split-system air conditioners: 13 SEER; the row label is quoted in the eCFR with an em-dash and is omitted here) | CFR 430.32(c)(1), https://www.ecfr.gov/current/title-10/chapter-II/subchapter-D/part-430/subpart-C/section-430.32 ; https://raw.githubusercontent.com/NREL/resstock/develop/project_national/housing_characteristics/HVAC%20Cooling%20Efficiency.tsv | confirmed (source found; value unchanged) | cite 10 CFR 430.32(c)(1) and ResStock |
| FD HVAC age | 13 yr (`RBM` L54, used L172) | RECS 2020 PA, weighted: main space-heating equipment age cumulative 5.8% (<2), 20.0% (2-4), 38.9% (5-9), 57.7% (10-14), so the median is in the 10-14 band; central AC age cumulative 12.2%, 26.1%, 52.6% (5-9), so the AC median is in the 5-9 band | RECS codebook EQUIPAGE / ACEQUIPAGE: "1 Less than 2 years old 2 2 to 4 years old 3 5 to 9 years old 4 10 to 14 years old 5 15 to 19 years old 6 20 or more years old" | RECS 2020 microdata v7 and codebook, https://www.eia.gov/consumption/residential/data/2020/xls/RECS%202020%20Codebook%20for%20Public%20File%20-%20v7.xlsx | assumption kept (13 lies in the heating-equipment median band; one number cannot match both bands) | none; age 7 changes no HVAC FD top-1 (0.914), tau 0.886 to 0.876 |
| FD occupancy | `occupied_all_day` (`RBM` L63, used L175) | none | none | n/a | assumption kept | none |
| FD HVAC electricity rate | 0.19 via `HVACGroundTruthCalculator.ELECTRICITY_RATE_PA` (`RBM` L176; constant at `HVACGroundTruthCalculator.py:32`, comment L29-31) | EIA PA residential 17.77 c/kWh (2024) | EIA: "Pennsylvania 17.77 18.10" (Residential 2024, 2023). Current code comment: "(Table 2.10; PA residential avg 17.77 c/kWh in 2024). 0.19 is the bundled default-service rate (supply + delivery + riders) the paper derives from PA PUC (2025), not an EIA figure." | https://www.eia.gov/electricity/annual/html/epa_02_10.html | mismatch (the row's quoted comment "rising to ~19-21 c/kWh through 2025" is stale; value unchanged) | update the quote; see `HVAC.md` for the rate itself |
| FD appliance type | retrieval-set mode `dryer` (`RBM` L141-151, used L186) | recomputed dryer (13 of 35) | none | n/a | confirmed | none |
| FD kWh/cycle dryer | 2.10 (`RBM` L65-68, used L203-204) | 8.45 lb / 3.73 lb/kWh = 2.27 kWh per DOE test cycle at the 2015 federal minimum (vented electric, standard) | CFR 430.32(h)(3): "Clothes dryers manufactured on or after January 1, 2015, shall have a combined energy factor no less than: ... (i) Vented Electric, Standard (4.4 ft 3 or greater capacity) 3.73". App D1 sec. 2.7.1: "Standard size clothes dryer 8.45 pounds ± .085 pounds." | CFR 430.32(h)(3); 10 CFR 430 Subpart B Appendix D1 sec. 2.7.1 (eCFR) | replacement proposed | 2.10 to 2.27 (label it "federal-minimum test-cycle energy"); Appliance FD top-1 unchanged, tau -0.011 |
| FD kWh/cycle washer / dishwasher / fallback | 0.55 / 1.00 / 1.00 (`RBM` L65-69) | Dishwasher: 307 kWh/yr / 215 cycles/yr = 1.43 kWh/cycle ceiling (2013 standard). Washer: no clean per-cycle figure; the federal IMEF metric includes drying energy for remaining moisture, so it does not convert to machine + water-heating kWh | CFR 430.32(f)(1)(i): "Standard size dishwashers shall not exceed 307 kwh/year and 5.0 gallons per cycle." App C1 sec. 5: "use N = 215 cycles/year in place of N = 184 cycles/year." | CFR 430.32(f)(1); Appendix C1 to Subpart B (eCFR) | assumption kept (all three are unused while the retrieval-set mode is `dryer`) | none now; if the mode ever changes, dishwasher 1.43 is the sourced ceiling |
| FD baseline run time | `7pm` (`RBM` L70, used L206) | none | none | n/a | assumption kept | none |
| FD appliance age | first number of the band; fallback 11 (`RBM` L189-198; fallback L71) | parsing rule | none | n/a | assumption kept | none |
| FD shower GPM | 2.5 (`RBM` L76, used L213) | federal maximum 2.5 gpm; HSP 2014 average shower flow 2.25 gpm | CFR 430.32(p): "The maximum water use allowed for any showerheads manufactured after January 1, 1994, shall be 2.5 gallons per minute (9.5 liters per minute) when measured at a flowing pressure of 80 pounds per square inch gage (552 kilopascals)." HSP 2014 Table 12: "Average flow rate (gpm)* 1.14 2.25 4.40 2.20 1.39" | CFR 430.32(p); HSP 2014 printed p. 15 (PDF p. 24), https://www.osti.gov/servlets/purl/1126820 | confirmed (source found: the federal maximum; value unchanged) | cite 10 CFR 430.32(p); 2.25 gpm would lower Shower FD top-1 0.850 to 0.767 |
| FD tank size | 50 gal (`RBM` L77, used L214) | RECS 2020 PA weighted: Small (<= 30 gal) 8.2%, Medium (31-49) 52.3%, Large (>= 50) 33.8%, tankless 5.7%; electric-WH households: 10.8 / 49.5 / 36.5 / 3.2% | RECS codebook WHEATSIZ: "1 Small (30 gallons or less) 2 Medium (31 to 49 gallons) 3 Large (50 gallons or more) 4 Tankless or on-demand" | RECS 2020 microdata v7 and codebook (URLs above) | replacement proposed | 50 to 40 gal (median band 31-49; also master mode and `SGTC:367` fallback); Shower FD top-1 0.850 to 0.833 |
| FD setpoint | 120 F (`RBM` L78, used L215) | DOE test procedure and ANSI 301-2019 / HSP 2014 use 125 F; field averages 123 F (Lutz 2012) and 127 F (Parker 2002); CDC circulation floor 120 F; master-sheet mode 120 (53 of 80) | App E sec. 2.4: "The temperature controllers of a non-flow activated water heater shall be set so that water is delivered at a temperature of 125 °F ± 5 °F (51.7 °C ± 2.8 °C)." HSP 2014: "The hot water set point shall be 125°F, and the mixed temperature for showers, sinks, and baths shall be 110°F. This set point is based on field data (Lutz and Melody 2012) and the 2010 federal rulemaking for residential water heaters (DOE 2010)." LBNL 2020 fn. 5: "audited set point temperature averaged 127 °F, and field measurement studies in California by Lutz (2012) showed the average set point temperature to be 123 °F." | 10 CFR 430 Subpart B Appendix E sec. 2.4; HSP 2014 printed p. 49 (PDF p. 58); https://www.osti.gov/servlets/purl/1619186 printed p. 8 | assumption kept (120 F is the dataset mode and the CDC floor; 125 F is the rating convention, not a measured stock value) | none; 125 F lowers Shower FD top-1 0.850 to 0.833 |
| FD homeowner fields | from the Test row; fallbacks never fire (`RBM` L164-166, L170-171, L216) | code matches | none | n/a | confirmed | none |
| FD unused constants | 11 constants (`RBM` L55-62, L72-74, L80-82) | whole-repo grep: 11 have no reader (list below) | none | grep results below | confirmed | none (removal is another agent's task) |
| FD ranking | `apply_mavt_ranking` (`RBM` L266); sentinel rows on exception (L307-327); function L232-329 | code matches | none | n/a | confirmed | none |
| NN k | 3 (`RBM` L351; CLI `--k` L490) | none | none | n/a | assumption kept (signature is now `run_nearest_neighbor_baseline(test_df, k=3, fallback="tie")`; CLI adds `--nn-fallback` L491-494) | update the quoted signature |
| NN index and encoder | 90 RAG scenarios, all-MiniLM-L6-v2 (`RBM` L352-355) | `DEFAULT_EMBEDDING_MODEL` is at `run_rag_ablation_experiments.py:66` (doc: L58); `load_source_groups` L324-377 and `build_collection` L378-421 (doc: L345-370) | none | n/a | mismatch (line citations) | fix lines |
| NN query text | `format_embedding_text` via `retrieve_similar` (`RBM` L358-379) | `sentinel_utils.format_embedding_text` is at L873-922 (doc: L425-479); A_E builds its query in `format_scenario_text_for_retrieval` at `Architectures/Example-Guided_LLM_Scoring.py:293-302` (doc: L317-326); `retrieve_similar` is at `run_rag_ablation_experiments.py:617` | none | n/a | mismatch (line citations; the "all 195 query strings equal A_E's" check was not re-run) | fix lines |
| NN excluded self-match id | `"test_<row>"` (`RBM` L370) | code matches | none | n/a | mismatch (doc says L371) | fix line |
| NN appliance keyword parser | removed | no parser in `RBM` | none | n/a | confirmed | none |
| NN prediction | copy-and-average, `tie` fallback (`run_rag_ablation_experiments.py:785-879`, `nearest_neighbor_prediction`) | doc cites L687-725; function now also offers `nearest` and `unscored` fallbacks (`NN_FALLBACKS` L730) | none | n/a | mismatch (line citation; description is the `tie` default only) | fix lines; mention the fallback option |
| Random scores | U(0, 100), 20 seeds, seed 42 + seed + 7 x row (`RBM` L404-438; ranking L392-402) | code matches (L418) | none | n/a | mismatch ("Not reachable from the CLI" is wrong: `--baseline random`, L496 and L509) | correct the reachability sentence |
| Uniform scores | 50.0 everywhere, stable mergesort (`RBM` L440-471) | code matches | none | n/a | mismatch (same CLI statement; `--baseline uniform` works) | correct the reachability sentence |

### Corrected HAB line numbers

Checked against the current `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py` (1,556
lines). Drift is +3 at the top of the file and +22 to +38 in the defaults and scoring region.

| Doc citation | Item | Correct line(s) |
|---|---|---|
| L167 | `HIDDEN_PARAMS` (header note) | L170-183 (comment L167-169) |
| L625-664 | `retrieval_set_rows` | L647-686 |
| L667-689 | `compute_defaults` | L689-709 |
| L681 | numeric median | L703 |
| L682-685 | categorical mode | L704-707 |
| L614 | `_canonical_clock` | L636-644 |
| L685 | `mode().iloc[0]` | L707 |
| L694-719 | `build_scenario` | L716-749 (parameter whitelist L744-747) |
| L722-760 | scoring, failure -> None | `score_scenario` L759-798 |
| L768-800 | ranking and metrics | `scenario_metrics` L805-839 (`apply_mavt_ranking` at L819-820); failure record in `run()` L955-967 |

Other stale citations in the same section: `run_rag_ablation_experiments.py` L58 -> L66, L345-370 ->
L324-421, L687-725 -> L785-879; `sentinel_utils.py` L425-479 -> L873-922;
`Architectures/Example-Guided_LLM_Scoring.py` L317-326 -> L293-302; `RBM` L371 -> L370;
`HVACGroundTruthCalculator.py` L28-31 -> L29-32 (and the quoted comment text has changed). All other `RBM`
citations in the section (L52-82, L141-151, L164-216, L232-329, L351-379, L392-471) match.

### Unused-constant grep results

Command: `grep -rn --include=*.py -w <NAME> .` excluding `.venv` and `.git`, discarding the definition
lines; non-.py files and `import run_baseline_models` / `getattr` patterns were also checked (none found
outside documentation). Two copies define the constants: `RBM` and
`Analysis/rerun_prep/pipeline/orig/run_baseline_models.py` (a pre-change snapshot).

Truly unread anywhere (defined only, 11):
`HVAC_DEFAULT_SQFT_BY_HOUSING_TYPE`, `HVAC_DEFAULT_SQFT_FALLBACK`, `HVAC_DEFAULT_HOUSEHOLD_SIZE`,
`HVAC_DEFAULT_OUTDOOR_TEMP`, `HVAC_DEFAULT_UTILITY_BUDGET`, `APPLIANCE_DEFAULT_HOUSEHOLD_SIZE`,
`APPLIANCE_DEFAULT_UTILITY_BUDGET`, `APPLIANCE_DEFAULT_HOUSING_TYPE`, `SHOWER_DEFAULT_HOUSEHOLD_SIZE`,
`SHOWER_DEFAULT_HOUSING_TYPE`, `SHOWER_DEFAULT_UTILITY_BUDGET`. This matches the provenance row exactly.
(Context only: RECS 2020 PA mean household size is 2.37 vs the unused 2.54.)

Read, but only as a fallback that never fires on current data: `SHOWER_DEFAULT_OUTDOOR_TEMP` (`RBM` L216),
`APPLIANCE_DEFAULT_AGE_YEARS` (L198), `APPLIANCE_DEFAULT_KWH_FALLBACK` (L204). Read but ineffective while
the mode is `dryer`: the washer and dishwasher entries of `APPLIANCE_DEFAULT_KWH_PER_CYCLE`.

Read and live: `HVAC_DEFAULT_R_VALUE` (L173), `HVAC_DEFAULT_SEER` (L174), `HVAC_DEFAULT_HVAC_AGE` (L172),
`HVAC_DEFAULT_OCCUPANCY_CONTEXT` (L175), `APPLIANCE_DEFAULT_KWH_PER_CYCLE` (L203), `APPLIANCE_DEFAULT_BASELINE_TIME`
(L206), `SHOWER_DEFAULT_GPM` (L213), `SHOWER_DEFAULT_TANK_SIZE` (L214), `SHOWER_DEFAULT_WATER_HEATER_TEMP`
(L215). No test file reads any of these constants.

### Not opened / blocked

- DOE Energy Saver water-heater temperature page (the "set at 120ºF" recommendation): every energy.gov URL
  tried returned 404 through the proxy, so that quote is not used.
- ResStock option-to-SEER conversion documentation: github.com HTML is blocked; only the TSV files on
  raw.githubusercontent.com were read.
- ENERGY STAR product-specification pages for dryers and dishwashers were not opened; the federal standards
  and test procedures were used instead.
- DOE rulemaking TSDs (dryers, dishwashers, washers, water heaters) were not opened.
- *.nrel.gov (ResStock docs, HSP) was not used; HSP 2014 was read from osti.gov.
- The NN "all 195 query strings equal A_E's" check and the `run_rag_ablation_experiments.py` embedding
  path were not re-run (would load the sentence-transformers model); only line numbers were checked.
