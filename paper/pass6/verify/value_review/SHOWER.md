# Shower constant value review

Scope: every row of the Shower section of `docs/CALCULATOR_PROVENANCE.md` (lines 233-295; 39 rows).
Code checked: `Ground Truth Calculators/ShowerGroundTruthCalculator.py` (read in full 2026-09-27). No repo
file was edited. Impact estimates used patched copies of the calculator in the session scratchpad
(`scratchpad/impact/shower_impact.py`, `scratchpad/impact/bounds.py`), run over the 80 master scenarios in
`Scenario Files/ShowerScenarios.xlsx` (60 Test + 20 RAG), ranked with `sentinel_utils.apply_mavt_ranking`.
Mains-temperature numbers come from `scratchpad/mains.py` on six PA TMY3 EPW files from
climate.onebuilding.org.

## Summary

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

## Source keys used below

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

## Table

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

### PA mains temperature detail (HSP Eq. 26 on TMY3)

| Station (TMY3) | T_amb annual (F) | max monthly difference (F) | T_mains min / max (F) | mean (current line - Eq. 26) over 12 months (F) |
|---|---|---|---|---|
| Allentown 725170 | 51.7 | 48.9 | 46.1 / 69.4 | -3.2 |
| Erie 725260 | 49.1 | 47.2 | 44.4 / 65.7 | -1.6 |
| Harrisburg 723990 | 51.5 | 57.3 | 43.9 / 71.1 | -2.9 |
| Philadelphia 724080 | 54.9 | 48.5 | 48.6 / 73.3 | -5.3 |
| Pittsburgh 725200 | 51.0 | 45.2 | 46.4 / 67.7 | -2.9 |
| Wilkes-Barre/Scranton 725130 | 49.8 | 45.7 | 45.4 / 66.3 | -2.1 |

## Not opened / blocked

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
