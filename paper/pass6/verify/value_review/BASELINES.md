# Baselines constant value review

Scope: every row of the Baselines section of `docs/CALCULATOR_PROVENANCE.md` (lines 297-361; 38 table rows
plus the header notes). Code checked: `Miscellaneous Scripts/core-automation/run_baseline_models.py`
(`RBM`, 520 lines, read in full) and `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`
(`HAB`, 1,556 lines; lines 1-200 and 612-975 read, the rest mapped by `def` index). No repo file was
edited. The dataset-median (DM) constants were recomputed by calling `HAB.compute_defaults()` (reads the
scenario workbooks only; no API call). Fixed-default (FD) impact estimates used
`scratchpad/impact/fd_impact.py`, which patches RBM module constants in memory and scores every Test
scenario against the reference built by HAB's own `build_scenario(..., true_params(...))`; top-1 and
Kendall tau are single deterministic runs and may differ slightly from the paper's pipeline numbers.

## Summary

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

## Table

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

## Corrected HAB line numbers

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

## Unused-constant grep results

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

## Not opened / blocked

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
