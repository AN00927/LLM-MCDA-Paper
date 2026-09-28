# HVAC constant value review

Scope: every row of the HVAC section of `docs/CALCULATOR_PROVENANCE.md` (lines 29-106) except the two
solar-gain rows (solar gain per ft2 of glass; solar in both modes). Code checked:
`Ground Truth Calculators/HVACGroundTruthCalculator.py` (831 lines, read in full 2026-09-27). No repo file
was edited. Impact estimates used a subclass of the calculator in the session scratchpad
(`scratchpad/impact/run.py`), run over the 105 scenarios in `Scenario Files/HVACScenarios.xlsx`.

## Summary

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

## Row table

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

## Other observations (not edited)

- `paper/paper_draft_working.tex:614` reports "\$0.38--\$3.29" as the realized cost span. Current code
  bounds are \$0.19/\$3.21. The same line cites the EIA state average as "about \$0.177/kWh" (2024);
  EIA's 2025 figure is 19.30 c/kWh.
- The HVAC code comment at :35 cites ACCA Manual J for 0.35 ACH; the provenance row cites Persily 2015.

## Not opened / blocked

- ASHRAE Standard 55-2020, ASHRAE Handbook of Fundamentals Ch. 18 (residential internal gains) and ACCA
  Manual J (1,200 Btu/h appliance allowance): paywalled, not opened. The IECC R405 equation was used
  instead.
- Dyer & Sarin (1979), Oper. Res. 27(4): pubsonline.informs.org returned 403.
- Newer PJM emissions reports (2023, 2024 data): guessed URLs on pjm.com returned an HTML page, not a
  PDF. The newer vintages were not checked.
- Not needed: codes.iccsafe.org (blocked). up.codes (IECC 2018 Pennsylvania) served the full chapter.
