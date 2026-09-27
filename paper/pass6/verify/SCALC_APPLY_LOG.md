# S-CALC apply log (2026-09-27)

Applied to `paper/paper_draft_v2.tex` (main), `paper/supplementary.tex` (S), `paper/cas-refs.bib`
and `README.md`. Every value comes from the installed code (HEAD 95d7fce) or the regenerated
`Ground Truth/*.xlsx`, not from `PASS6_PROPOSAL.md`. Pre-edit copies and every script and output
are in the session scratchpad `scalc/` (`pre/`, `swing.py`, `tou.py`, `bounds.py`, `check.py`,
`*_out.txt`, `swing_*.csv`). No git write was run (read-only `git show`/`git log` only). No paid
API call. `docs/CALCULATOR_PROVENANCE.md`, `.py` and `.xlsx` files were not edited. The stop-slop
skill was loaded before any prose was written. Line numbers are after all edits.

Checks after editing (`scalc/check.py`): braces balance in both .tex files and the bib; every
`\cite*` key (81 main, 24 S) exists in the bib; every `\ref`/`\eqref` label exists; no duplicate
bib key (100 entries). No pdflatex in this sandbox, so no diagnostic compile.

## Items

| Item | Status | File:line | Old -> new (short) | Value source |
|---|---|---|---|---|
| A11.2 | applied | main:615 | appended swing finding: Env 0.008 (Appliance), 0.035 (HVAC) vs Comfort 0.098 / 0.092; Shower Env 0.128 (Table S2.1) | `scalc/swing.py` on current GT (below) |
| A11.4 / B55 | applied once | S:791 | swing caption + ", over the 285 test and RAG scenarios" | same scope as the recomputation |
| A11.4 / B55 values | applied | S:797-800 | HVAC 0.027/0.032/0.086/0.015 -> 0.031/0.035/0.092/0.012; Shower 0.108/.../0.053 -> 0.107/0.128/0.070/0.054; Appliance unchanged | `scalc/swing_current_full.csv` |
| B26 | applied (merged with B27) | main:672 | "effective EER derived from SEER (both ... \cite{ahri2008})" -> efficiency derived from SEER: EER by the HSP conversion \cite{hendron2010hsp} in cooling, heat-pump HSPF in heating; "all three rating quantities as AHRI defines them" | HVAC calc:215-221 |
| B26 README | applied (adapted) | README:393 | AHRI quadratic "applied identically ... heating or cooling" -> HSP Eq. 3 in cooling; HSPF paired with SEER in heating | HVAC calc:76-88, 215-221 |
| B27 | applied (adapted) | main:699, eq. at main:691-696 | new sentence: heating = electric air-source heat pump, HSPF paired with SEER (HSP defaults up to SEER 14, ResStock SEER 18/22), seasonal rating; Eq. hvac_energy now divides by $\eta$ = EER (cooling) / HSPF(S) (heating) | HVAC calc:76-88, 194-221 |
| B28 | applied (adapted, no limitation list) | main:646, 659, 699; bib pjm2022emissions | flat rate: "We price electricity at a bundled ... \$0.19/kWh." -> HVAC and Shower at the flat rate because their alternatives share one time of use; Appliance on TOU tariffs. Weekday: "PJM defines the peak for non-holiday weekdays, and every scenario is a non-holiday weekday." Wall R-value: "$R$ is the envelope R-value" -> "the scenario's wall R-value, which we apply to the whole conductive envelope". Heating: via B27. PJM URL added. | HVAC calc:20-32, 145-147; Appliance calc:21-34 |
| B29 | applied (adapted) | main:660, 661-666, 670 | "four-tier" -> "three-tier"; eq. drops the $1.0\le u<1.5$ / $u\ge1.5 \to 0$ rows for one $u \ge 1.0$ row; "and infeasibility beyond 150\%" dropped; "0.80, 2.5 and 1.5" -> "0.80, 2.5, 0.5 and 3 ... with them $P$ is continuous and stays positive at any utilization" | HVAC calc:357-374; Appliance :472-488; Shower :250-263 |
| B30 | applied (adapted) | main:677-678 (Eq. hvac_load), 686, 699 | $Q_{int}=400n+A_f+800$ -> $220n + (23.8A_f+17{,}900)/24$; $Q_{sol}=20(0.15A_f)$ -> $0.15F_hA_f\,\mathrm{SHGC}\,\mathrm{IAC}\,\bar I_m$; heating case now subtracts $Q_{sol}$; "Solar gain enters only in cooling season ..." -> sourced description (balance-point method \cite{christensen1983seri}; IECC IGain \cite{iecc2018}; 220 Btu/h per occupant \cite{hendron2010hsp}; 15% glazing, $F_h$ 0.75/0.56/1, SHGC 0.40, IAC 0.836 \cite{iecc2018}; $\bar I$ 74.0 / 105.5 W/m2 = 7.85 / 11.19 Btu/h per ft2 glass, Harrisburg TMY3 \cite{onebuilding_tmy3}); "800 BTU/hr standby term" -> "746" | HVAC calc:39-74, 149-164, 184-192; VALUE_REVIEW.md s.1 (3.3, 3.6, 3.7) |
| B31 | applied | main:699; S:582 | m_h list + "; our values"; S "following ACCA Manual~J exposure conventions \citep{accamanualj}:" -> "with values we set by exposure (they are not taken from a Manual~J table):" | HVAC calc:131-141 |
| B32 | applied (adapted) | main:701 | "70 F in heating mode" -> "71 F in heating mode, the set points of the House Simulation Protocols \cite{hendron2010hsp}" | HVAC calc:98-105 |
| B33 | applied (adapted) | main:706, 727 | new sentences after the Comfort eq.: mode = the system the question asks about; sets $T^*$, the load case, $\eta$, Practicality; load from setpoint against the heat balance; never cools in heat mode or heats in AC mode. Off free-float "cooling/heating season" -> "mode" | HVAC calc:90-96, 572-639 |
| B34 | applied (adapted) | main:722, 725 | Eq. hvac_degradation $\min(0.30, \delta_{maint}[...])$ -> $1-(1-M)^{\min(a,20)}$; text: HSP Eq. 20, $M$ = 0.02 (moderate, our midpoint of 0.01/0.03) for every scenario | HVAC calc:287-299 |
| B35 | applied | main:625, 638-639, 646 | percentile sentence -> "over all 285 test and RAG scenarios ...; HVAC Environmental Impact endpoints convert the HVAC cost percentiles"; Table bounds HVAC 0.38--3.29 -> 0.40--2.81, 1.96--18.04 -> 2.05--15.40; Appliance 0.025--0.71 -> 0.028--0.774; Shower 0.14--1.14 -> 0.13--1.07; text \$0.38/\$3.29 -> \$0.40/\$2.81; 1.96--18.04 -> 2.05--15.40 | HVAC calc:455-472; Appliance calc:99-100; Shower calc:279-290; `scalc/bounds_out.txt` (HVAC p5/p95 of 301 nonzero active = 0.4000/2.8100; Appliance 0.0276/0.7741, 0.2884/3.6430; Shower 0.1349/1.0691, 6.0/45.0) |
| B36 | applied (scope corrected) | main:729 | "realized per-cycle cost spans \$0.025--\$0.71 ... \cite{energystar_products}" -> "5th and 95th percentiles ... over the 100 test and RAG Appliance scenarios are \$0.028 and \$0.774, and of emissions 0.288 and 3.643" (proposal said "285"; the Appliance bounds are over 100 scenarios) | Appliance calc:94-100 |
| B37 | applied | main:731 | "\$0.14--\$1.14 ... \cite{...}" -> 5th/95th over the 80 Shower scenarios \$0.13 / \$1.07, 6.0 / 45.0 gal, citations kept on flows/durations | Shower calc:279-290 |
| B38 | applied (adapted) | main:729; S:777; bib | main cite list `peco2021,ppl2025,firstenergy2025,firstenergy2026,duquesne2026` -> `peco2021,peco2025tou,ppl2025supp402,ppl2025ptc,fepa_supp28,fepa_supp20,duquesne2026,paupc2025dec`; S citations likewise. `ppl2025`, `firstenergy2025`, `firstenergy2026`, `energystar_products` now uncited | APPLIANCE_REPORT.md (PECO/PPL/FE/Duquesne sources) |
| B39 | applied (adapted, no mismatch disclosure) | S:777 | "PPL (Rate RTS) \citep{ppl2025}" -> "PPL (GSC-1 time-of-use program for Rate Schedules RS and RTS) \citep{ppl2025supp402,ppl2025ptc}", 4--8pm winter window, no super off-peak | Appliance calc:46-51 |
| B40 / D12 main | applied (adapted) | main:729 | "applies weekday summer rates year-round" -> "applies the rates of one common rate period (December 2025 to May 2026) with their weekday windows year-round" | Appliance calc:27-34 |
| D12 / B44 Table S1.6 | applied | S:748-771 | new columns (super off-peak window and rate); PECO 0.3275/0.0838/0.0606, PPL 4--8pm 0.1399/0.1199, West Penn 0.1823/0.0935/0.0689, Penelec 0.1973/0.0996/0.0765, MetEd 0.2212/0.1089/0.0806, Duquesne "flat" 0.1375; intro states the one rate period and full price-to-compare basis | `scalc/tou_out.txt` from Appliance calc:40-65 |
| D12 S text | applied | S:777 | "Jun-2025 PTC" -> "December 2025"; "49--76\%" -> "14--74\%"; added super off-peak "61--81\%" | `scalc/tou.py` (below) |
| B41 | applied | main:729 | "against appliance-specific tolerance ceilings \cite{paetz2012,waseem2020}" -> "on curves we set, with a household-size penalty scaled by an appliance-specific delay ceiling (12 h dishwashers following \citet{paetz2012}; 8 h washers and 6 h dryers, our values)" | Appliance calc:130-137, 249-259, 288-298 |
| B43 | applied (scope corrected) | S:578 | "drawn from the ENERGY STAR certified-products database" -> "that we set per scenario (most dryer values and some dishwasher values exceed current ENERGY STAR limits, as older units do)"; Spearman + "over the 100 test and RAG Appliance scenarios" (proposal said 285) | recomputed on current `ApplianceScenarios.xlsx`: rho 0.36 / 0.38 / 0.69 (all 100), dryer 7-9 yr 2.40-3.50; test dryers >2.15 kWh: 23/24, dishwashers >1.12: 8/20 |
| B45 | applied | main:609; S:938 (two spans) | "below the CDC's Legionella threshold" -> "below the 120 F floor that the CDC sets for circulating hot water"; S "The original function ... CDC storage guidance" -> "The current function ... CDC's 120 F floor for circulating hot water"; 140 F cap labelled our assumption | Shower calc:71-90; max scenario setpoint 140 F (none above) |
| B46 | applied | main:731; bib `ibanezrueda2023` | "season-dependent optimum \cite{reu2016}" -> 7.8-min REU2016 start, +10% per 10.8 F below 77 F (our assumption), capped at 11.6/8.8 \citet{ibanezrueda2023} | Shower calc:51-69; bib fields from Crossref API (authors N. Ibáñez-Rueda, J. Guardiola, S. López-Ruiz, F. González-Gómez; vol 9, no 4, art. 121) |
| B47 | applied (adapted) | main:731, 1091 | "\cite{burch2007,zhang2023}" -> linear interpolation 48.5 F (<=32 F) to 68.2 F (>=75 F), least-squares fit to \citet{burch2007} in the form of \citet{hendron2010hsp} over six PA TMY3 stations; Limitations: "(our linear fit to the annual sinusoid of \citet{burch2007})". `zhang2023` now uncited in main | Shower calc:31-40, 105-115 |
| B48 | applied | main:731 | "delivery target." -> "delivery target, our convention."; "calibrated to adoption likelihood" -> "that we set by hand" | Shower calc:47, 205-225 |
| B49 | applied | main:609 | "the tank can usefully supply" -> "we assume the tank can usefully supply" | Shower calc:235 |
| B51 | applied | S:580 | standard "2.5--3.0 GPM" -> "$>$2.0 to 3.0 GPM; every standard scenario lies at 2.5--3.0"; high_flow + "11 of the 80 Shower scenarios sit at 3.5--4.0 GPM, above the federal maximum ..." | `sentinel_utils.gpm_to_flow_rate_label`; current ShowerScenarios.xlsx: GPM counts 1.5:9, 2.0:25, 2.5:31, 3.0:4, 3.5:7, 4.0:4 |
| B53 | applied | S:576 | "ENERGY STAR Most Efficient threshold" -> "ENERGY STAR threshold of 15.2~SEER2"; "R-values drawn from" -> "wall R-values that we set around" | test SEER 8-22; tiers R-8-12/13-17(max)/20-24 on current data, text bands unchanged |
| B54 | applied | main:1074 | "sits near the typical values of the Pennsylvania housing stock these scenarios draw on." -> "sits near the median R-value and SEER of the test scenarios." | test-set medians (70 HVAC test rows): R-15.5, SEER 13 |
| B70 | applied | README:328 | R-11/R-13/R-19 -> scenario R-value (tiers R-8-12 / R-13-18 / R-19-24) | scenario data |
| B71 | applied | README:330 | "true age in years -> kWh/cycle | ENERGY STAR certified datasets" -> "scenario kWh/cycle (the calculator does not read age) | ENERGY STAR and DOE test procedures (cycles/year)" | Appliance calc:510-516 |
| B72 heading | applied | README:346 | range heading -> "5th-95th percentiles over the 285 test + RAG scenarios; HVAC environmental bounds convert the HVAC cost percentiles" | calc bound comments |
| B72 mains | skipped: old string gone | README:405 | already updated by 95d7fce to "48.5 F winter to 68.2 F summer, a linear fit to the NREL (Burch & Christensen) mains model on PA TMY3 weather" | matches Shower calc:31-40 |
| B72 heater | applied | README:417 | eta line + "federal minimum in 10 CFR 430.32(d) is 0.9307 - 0.0002 x V_r = 0.9207 for a 50-gal tank" | Shower calc:42-46 |
| S1 fixed-default description | applied | S:631-641, table S:646-663 | per-appliance-type kWh text and washer/dryer/dishwasher rows -> every Appliance scenario gets the retrieval-set mode (dryer) at 2.27 kWh/cycle (8.45 lb / 3.73 lb/kWh, \citep{cfr430_32h}); tank 50 -> 40 gal (RECS 2020 PA median band 31-49, \citep{eia_recs2020micro}); caption "Fixed-default and dataset-median constant values" | run_baseline_models.py:52-71, 128-141, 171-196 |
| Retrieval-set medians/modes | applied | S:638-641, table "Dataset median" column; main:752 | main "(the dataset median, or the mode ...)" -> "(the median over the 90 retrieval scenarios, or the mode for a categorical parameter; Table S1.4)"; table column R 16, SEER 13, age 16, occupancy standard (scored as occupied_all_day), dryer, 1.2 kWh, 9:00 a.m., 2.25 GPM, 45 gal, 120 F | `compute_defaults()` run live (output identical to the task list) |
| Shower 0.69 showers/person/day | applied | S:619-621 | "assumed 0.9 ... above the 0.75 ... \citet{mayer1999reuw}" -> "0.69 ..., the rate REU2016 measured \citep{reu2016,gauley2017showering}"; eq. 27n -> 20.7n. `mayer1999reuw` now uncited in S | Shower calc:245-248 |
| Nomenclature (knock-on of B27/B30/B34) | applied | S:238-240, 250-251, 259 | added $F_h$, SHGC/IAC, $\bar I_m$, HSPF, $\eta$; $\delta_{maint}$ row -> $M$ | follows the new equations |

## Bib entries added (`paper/cas-refs.bib`, keys checked absent first)

`hendron2010hsp` (report number NREL/TP-550-49246 and DOI 10.2172/989422 confirmed on the OSTI
API; the proposal's "49426" was a typo), `iecc2018` (up.codes PA edition URL, Table R405.5.2(1)),
`christensen1983seri` (SERI/TP-254-2019, OSTI purl 5344868), `onebuilding_tmy3` (no year, no
file URL: one entry for the six PA stations, howpublished climate.onebuilding.org),
`resstock_v320` (no year), `gauley2017showering` (@misc; institution not recorded in the value
review, so left out), `ibanezrueda2023`, `cfr430_32h`, `eia_recs2020micro` (no year field),
`peco2025tou`, `ppl2025supp402`, `ppl2025ptc`, `fepa_supp20`, `fepa_supp28`, `paupc2025dec`.
`pjm2022emissions` gained its URL. The `fepa_supp28` URL contains `%20`; it sits in a `url` field,
which natbib/hyperref read verbatim, but check it in the Overleaf compile.

## Recomputed numbers and how

**Swing table (A11.2, A11.4, B55).** The original was produced by `diagnostics_for()` in
`Miscellaneous Scripts/validation/WeightDiagnostics.py` (default `--scope full`, 285 scenarios):
realized swing = nominal weight x mean over scenarios of (max - min) of the criterion score across
the three alternatives. `scalc/swing.py` imports that function, points `GT_DIR` at a chosen folder
and writes CSV to the scratchpad only. Gate: on the pre-Phase-I ground truth (`git show
846b02e^:Ground Truth/...`) it reproduces the published table (HVAC 0.027/0.032/0.086/0.015,
Appliance 0.066/0.008/0.098/0.095, Shower 0.108/0.128/0.070/0.0535). On the current GT (per
decision type; ground-truth quantities, no model data):

| Criterion | Weight | HVAC | Appliance | Shower |
|---|---|---|---|---|
| Energy Cost | 0.30 | 0.031 (range 0.1042) | 0.066 (0.2206) | 0.107 (0.3579) |
| Environmental Impact | 0.35 | 0.035 (0.1005) | 0.008 (0.0221) | 0.128 (0.3659) |
| Comfort | 0.20 | 0.092 (0.4589) | 0.098 (0.4895) | 0.070 (0.3481) |
| Practicality | 0.15 | 0.012 (0.0782) | 0.095 (0.6318) | 0.054 (0.3593) |

**TOU savings (D12).** `scalc/tou.py` reads `ApplianceGroundTruthCalculator.UTILITY_RATES`;
saving = 1 - rate/peak rate. Peak to off-peak: PECO 74.40%, PPL 14.29%, West Penn 48.69%, Penelec
49.49%, MetEd 50.78% -> "14--74%". Peak to super off-peak: PECO 81.49%, West Penn 62.17%,
Penelec 61.23%, MetEd 63.57% (PPL has no super off-peak; Duquesne flat) -> "61--81%".

## Values not recomputed

None of the items' values was left uncomputed.

## Stale text found outside these items (reported, not fixed)

1. S:666-700 HVAC worked example (Philadelphia 95 F, R-15, SEER 13, age 10): the installed
   calculator gives 72 F 0.16/0.29/0.67/0.76 = 0.398; 76 F 0.29/0.37/1.00/0.83 = 0.541;
   80 F 0.44/0.45/0.67/0.83 = 0.548. The winner moves from 76 F to 80 F (paper: 76 F 0.466).
2. S:779 (TOU emissions paragraph): "the cost differential is an order of magnitude larger than
   the emissions differential" no longer holds for PPL (14.3% against 6.2%).
3. S Table S2.2 entropy/MEREC weights (and main text quoting 0.663, 0.371, etc.) were computed on
   the old ground truth; HVAC and Shower GT changed. Main:613 "Spearman's rho ... 0.92" is also
   GT-derived. Not recomputed here.
4. Baseline numbers from the old GT/baselines: main:776-835 and main:1074 (fixed default tau
   0.097 / 0.933 / 0.800, 0.614), `tab:incremental-contribution`, `tab:single-criterion-recovery`,
   main:811 and S tab:param_provenance dataset-median rows (0.641 / 0.769 / 0.122). The
   fixed-default constants changed again (tank 40, dryer 2.27) after PIPELINE_REPORT.md; take
   these from `Output Files/Baselines/baseline_metrics.csv` at S4.
5. main:609 example "needs about 155 gallons of hot water" was computed with the old inlet
   anchors; at the same implied outdoor temperature the new anchors give about 153.
6. README:359-368 budget-penalty table still says four tiers, "u >= 1.50 -> 0 (eliminated)" and
   "infeasibility elimination (Gathergood 2012)"; README:395 "(76 F cooling, 70 F heating)".
7. S:935-942 "Ablation Data Provenance" describes the old ablation collection; it becomes moot
   after the rerun (S4).
8. main:672 still calls the base internal gain an "always-on standby baseline" and main:699 the
   "746 BTU/hr standby term"; IECC calls it a base internal gain. Wording left as is.
