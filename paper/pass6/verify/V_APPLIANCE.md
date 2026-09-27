# V_APPLIANCE: independent verification of the new Appliance calculator

Verified 2026-09-26 by a fresh agent. Scope: Appliance only.
Under test: `Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py` (calc_new). Baseline: `Ground Truth Calculators/ApplianceGroundTruthCalculator.py` (shipped), which is byte-identical to the frozen copy `Analysis/rerun_prep/appliance/shipped/` and to commit c6cdf60 (checked with `cmp` and `git show c6cdf60:...`).
Python: `.venv/Scripts/python.exe`. My scripts are in the session scratchpad `v_app/`: `check1_repro.py`, `check_4789.py`, `check_89_probe.py`, `check8_fixeddefault.py`, `scan_scen.py`, `pdfgrep.py`.

**Verdict: conditional.** The tariff, mapping, bounds and budget-penalty work is correct, fully sourced and approved, with nothing unapproved in the diff. Two sentinel-discipline gaps predate this work and were not introduced by it (D1, D2), but the A_H rerun can hit them. The author should decide on them before the A_H Appliance rerun. Neither one changes the reference ground truth.

No edits were made to calc_new or its test. The only file I changed in the repo is `paper/pass6/verify/SCENARIO_FIXES.md` (rows #40-#83 appended), plus this report. My harness and impact reruns rewrote `Analysis/rerun_prep/appliance/out/*.xlsx`. Their content was identical to the previous files, and I restored the original bytes, so the working tree for `Analysis/rerun_prep/appliance/` is clean.

---

## Check 1. Reproduction: PASS

| What | Command | Result |
|---|---|---|
| Frozen shipped copy vs GT (harness) | `python Analysis/rerun_prep/appliance/harness.py Analysis/rerun_prep/appliance/shipped/ApplianceGroundTruthCalculator.py` | IDENTICAL, 300/300 rows |
| Frozen and live shipped vs GT, all 18 columns (independent) | `python v_app/check1_repro.py` | 0 differences in every column. `mavt_score` max abs diff 2.2e-16, from the pipeline agent's 10-dp rounding in `sentinel_utils`, as the handoff says |
| RAG score columns | same script: `Scenario Files/ApplianceRAGScenarios.xlsx` (105 rows) matched to regenerated rows by descriptors + alternative hour | 105/105 matched, 0 differences in all 8 score columns (4 criteria, mavt, rank, raw_cost, raw_emissions) |
| Test/RAG split | same script | 35 RAG + 65 test master rows. The 65 test rows match `TestScenarios.xlsx`'s 65 Appliance rows one-to-one and in order |
| "New logic + shipped data reproduces" | `python Analysis/rerun_prep/appliance/impact.py` | "New logic + shipped data vs GT: IDENTICAL". Every impact-table row reproduces exactly (`impact_summary.txt` byte-identical) |

Note: master rows 98 and 99 store times as `6pm` / `8am`, while the RAG sheet stores `6:00 PM`. A string-keyed match therefore misses them. The harness matches on descriptors only, so it is unaffected. Logged as scenario fixes #74-#81.

## Check 2. Tests: PASS

| Command | Result |
|---|---|
| `python -m pytest Analysis/rerun_prep/tests/test_appliance_tariffs.py` | 101 passed |
| same, with `APPLIANCE_CALC_PATH="Ground Truth Calculators/ApplianceGroundTruthCalculator.py"` | 46 failed, 55 passed, matching the report. The failures come from the super off-peak windows (27), mapping (6), PPL window/rates (5), FE rates (3), Duquesne (3), PECO rates (1) and bounds (1) |

Coverage gap (MINOR): no test pins the budget-penalty continuity or any appliance-type or baseline-time validation.

## Check 3. Hunk-by-hunk diff audit: PASS (all hunks map, nothing missing)

The stored `Analysis/rerun_prep/appliance/calc_new.diff` predates the budget-penalty addendum and lacks that hunk (D7). I audited a fresh `git diff --no-index` of shipped vs calc_new.

| Hunk (calc_new lines) | Change | Section 2 decision |
|---|---|---|
| 21-22 | PJM comment: "Weekday/holiday distinction not modeled" -> non-holiday weekday rule. Factors 1.041/0.976 and window (7, 23) unchanged | Weekdays; CLAUDE.md PJM rule preserved |
| 27-39 | Rate-period and basis comment: one common period Dec 1 2025-May 31 2026, full PTC basis, weekday rule, `[start, end)` wrap convention, FE Supp 20/28 citations | Appliance tariffs; comment corrections |
| 40-65 | `UTILITY_RATES`: PECO 3-period on the (A) basis; PPL 16-20 window at PTC-sheet rates; FE x3 PTCDefault(Dec 2025) x Supp 20 multipliers with 23-6 super off-peak; Duquesne `peak_hours: None`, `flat_rate` 0.1375 | Appliance tariffs (super off-peak PECO 0-6 and FE 23-6; PPL winter 4-8 p.m.; Duquesne flat; common period; PTC basis) |
| 67-92 | Mapping comment rewritten. Six values: Indiana->Penelec, Carlisle->PPL, Reading->MetEd, Lebanon->MetEd, State College->WestPenn, Chambersburg->WestPenn. Stroudsburg and Quakertown stay PPL | Six cities remapped; Stroudsburg/Quakertown stay PPL |
| 94-100 | New class constants `ENERGY_COST_BOUNDS = (0.028, 0.774)`, `ENVIRONMENTAL_BOUNDS = (0.288, 3.643)` | Bounds |
| 147-172 | `_in_window` (wrap-aware); `determine_rate_period` returns peak / super_offpeak / offpeak / flat | Required to implement the tariffs. Behaviour-neutral on old data (Check 1) |
| 186 | `rate = rates[period + "_rate"]` | same |
| 352-375 | `apply_value_function` reads the class constants; comments updated | Bounds |
| 455-464 | Budget penalty: `elif u < 1.5` / `else: return 0.0` replaced by one `else` branch with the exponential | Budget penalty continuous |
| 483 | "strongly" -> "moderately" correlated | Comment corrections |

Unmapped hunks: none. Missing approved changes: none. Remaining unchanged comments carry bibliography-key citations (e.g. "Duquesne Light Company TOU (2026)", "Coolblue (2026)"). None is a stale claim.

## Check 4. TOU correctness: PASS (with NOTEs)

Command: `python v_app/check_4789.py`. Hours 0..23 (P = peak, s = super off-peak, o = off-peak, f = flat):

```
PECO      ssssssooooooooPPPPoooooo
PPL       ooooooooooooooooPPPPoooo
WestPenn  ssssssooooooooPPPPPPPoos
Penelec   ssssssooooooooPPPPPPPoos
MetEd     ssssssooooooooPPPPPPPoos
Duquesne  ffffffffffffffffffffffff
```

- Every hour falls in exactly one period for every utility; the script asserts that windows never overlap. The FE 23-6 window wraps correctly.
- Edges tested through `parse_alternative` with minutes:
  - 10:59 PM -> hour 22, off-peak (FE).
  - 11:00 PM -> hour 23, super off-peak (FE) and off-peak (PECO).
  - 11:59 PM stays super off-peak (FE).
  - 12:00 AM -> hour 0, super off-peak (PECO and FE).
  - 5:59 AM -> super off-peak; 6:00 AM -> off-peak.
  - PPL: 3:59 PM off-peak, 4:00 PM peak, 7:59 PM peak, 8:00 PM off-peak.
  - FE: 8:59 PM peak, 9:00 PM off-peak.
- **Billing of cycles that span a boundary (NOTE):** the whole cycle is billed at the rate of the start hour. Minutes are truncated (11:30 PM -> hour 23), and cycle duration is not modelled, so there is no proration. The shipped file did the same. The paper (main text L726: "prices the energy a cycle draws at the location- and time-specific rate") does not claim proration, so the two are consistent. Consider saying "at the rate in effect at the cycle's start time" when the paragraph is rewritten.
- PJM emissions window: `EMISSIONS_PEAK_HOURS = (7, 23)` and factors 1.041/0.976 are unchanged. The per-hour emissions period is identical to shipped for all 24 hours. It uses its own non-wrapping test, which is correct for 7-23.
- `determine_rate_period(location=None)` keeps a 2-6 p.m. default. No caller in the repo uses it (grep), so the path is dead.

## Check 5. Rate basis and primary sources: PASS, except Duquesne composition (NOTE)

Every value in the code matches the primary document I fetched, except Duquesne's breakdown (see the sources table). All utilities are on a price-to-compare basis (generation + transmission, with the PTC's own tax gross-up; no distribution).
- PECO: column (A) = (B) + 0.787 c.
- PPL: PTC-sheet TOU row = GSC + 3.343 c TSC.
- FE: PTCDefault, whose formula includes PTCNITS (confirmed on p.205 of the Jan 2026 consolidated tariff).
- Duquesne: the PA PUC release confirms 13.75 c as the residential PTC. I could not retrieve Duquesne's own Rider 8 supplement: Supplement No. 96 (DSS update effective 12/1/2025) and the Supplement 101 tariff return 404 to automated fetches, the Wayback Machine has no copy, and the site pages are JS-rendered. Two secondary sources say it includes transmission:
  - pyther.net/dlc-rates: "In the raw tariff, this consists of two separate charges (Supply + Transmission), which are combined here".
  - gridshopper.com: the transmission component "is the second largest component of the price to compare, after the auction price".

  Duquesne is therefore probably on the same basis, but this is not primary-confirmed. Impact is bounded: Duquesne is flat, so its rate cannot change any within-scenario ranking (variant b5 = 0 changes). It only moves the level of Pittsburgh/McKeesport cost scores and could nudge the pooled p5/p95 bounds. For a primary confirmation, download Supplement No. 96 by hand from duquesnelight.com (Tariff Resources) and read the Rider 8 residential table.
- FE rounding (NOTE): the rider says rates are "determined to the nearest one-thousandth of a cent per kWh". The code uses the unrounded products (e.g. 0.10947 x 1.6649 = 0.182257), a difference below $0.00001/kWh. No effect.

## Check 6. City remap: PASS (all six confirmed; Stroudsburg and Quakertown findings as reported)

Checked in the PPL Dec-2025 master tariff (pp. 7-8 of the PDF, "Territory Covered by this Tariff") and the FE PA consolidated tariff of Jan 1, 2026 ("Description of Territory").

| City | New | Evidence (verbatim) |
|---|---|---|
| Indiana | Penelec | FE p.14: "INDIANA COUNTY - Penelec and West Penn Rate Districts / Penelec Rate District / Boroughs of Armagh, Blairsville, ... Homer City, Indiana, Marion Center, ..."; West Penn's Indiana County list is only "Borough of Saltsburg." |
| Carlisle | PPL | PPL p.7: "CUMBERLAND COUNTY Boroughs of Camp Hill, Carlisle, Lemoyne, ..."; FE p.12 Met-Ed Cumberland list: "Borough of Mt. Holly Springs. Townships of Cooke, Dickinson, Monroe, South Middleton, Upper Allen." |
| Reading | Met-Ed | FE p.8: "BERKS COUNTY - Met-Ed Rate District / City of Reading."; PPL's Berks list names boroughs only (Morgantown, New Morgan, Robesonia, ...) and no city |
| Lebanon | Met-Ed | FE p.15: "LEBANON COUNTY - Met-Ed Rate District / City of Lebanon."; PPL: "LEBANON COUNTY Borough of Richland. Townships of Heidelberg and Millcreek." |
| State College | West Penn | FE p.10: "West Penn Rate District / Boroughs of Bellefonte, Centre Hall, Howard, Milesburg, Millheim, Port Matilda, State College, Unionville."; PPL has no Centre County entry |
| Chambersburg | West Penn | FE p.13: "West Penn Rate District / Boroughs of Chambersburg, Greencastle, Mercersburg, Mont Alto, Waynesboro." (the borough itself runs a municipal system, as the report says) |
| Stroudsburg | PPL (kept) | PPL p.8: "MONROE COUNTY Boroughs of East Stroudsburg (part), Mount Pocono, and Stroudsburg (part)."; FE p.16: "MONROE COUNTY - Met-Ed Rate District / Boroughs of Delaware Water Gap, East Stroudsburg, Stroudsburg." The FE tariff contains no "(part)" anywhere (grep over all 248 pages), so neither list settles it. The report's flag stands (moving it to Met-Ed flips 1 more test winner) |
| Quakertown | PPL (kept) | In neither PPL's Bucks list ("Boroughs of Richlandtown, Sellersville, Silverdale, Telford, and Turmbauersville") nor FE's ("Borough of Riegelsville"). The borough runs its own electric department (quakertown.org/government/electric-department; its rates in ecode360 §14354891). The report's flag stands |

## Check 7. Budget penalty, bounds, savings: PASS

**Budget penalty** (`check_4789.py`):

| u | 0.79999 | 0.8 | 0.9 | 0.99999 | 1.0 | 1.2 | 1.49999 | 1.5 | 1.50001 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| new | 1.0 | 1.0 | 0.75 | 0.500025 | 0.5 | 0.2744 | 0.111568 | 0.111565 | 0.111562 | 0.0249 | 0.00124 |
| shipped | 1.0 | 1.0 | 0.75 | 0.500025 | 0.5 | 0.2744 | 0.111568 | **0.0** | **0.0** | 0.0 | 0.0 |

The new penalty is continuous at 0.8, 1.0 and 1.5; the left/right limits agree to 1e-12. It is monotone non-increasing on a 6,001-point grid over [0, 6], and the largest step is 0.0025, from the 2.5 slope. Max utilization in the master data under the new rates is **0.2292**, so the penalty is 1.0 for every alternative and the change is inert for Appliance.

**Bounds.** Population, before and now: the output `raw_cost` (4 dp) and `raw_emissions` (3 dp) columns of all 300 alternatives of the 100 Appliance master scenarios (65 test + 35 RAG pooled; the Appliance share of the handoff's "285 test + RAG"). Method: numpy linear p5/p95, then `np.round(., 3)`.
- This convention reproduces the shipped (0.025, 0.71) / (0.288, 3.643) exactly from `Ground Truth/ground_truth_appliance.xlsx`.
- On the calc_new output it gives (0.028, 0.774) / (0.288, 3.643); unrounded 0.0276 / 0.7741 / 0.2884 / 3.643. These equal the constants in calc_new.
- `apply_value_function` reads the class constants: overriding `ENERGY_COST_BOUNDS = (0, 1)` makes x = 0.25 return 0.75, and the defaults map 0.028 -> 1.0 and 0.774 -> 0.0.

**Savings** (rate ratios from calc_new, independent of kWh):

| Utility | peak -> off-peak | peak -> super off-peak |
|---|---|---|
| PECO | 74.40% | 81.49% |
| PPL | 14.29% | n/a |
| West Penn | 48.69% | 62.17% |
| Penelec | 49.49% | 61.23% |
| Met-Ed | 50.78% | 63.57% |

The claimed "14-74%" and "61-81.5%" are both confirmed.

## Check 8. Sentinel discipline and the fixed-default case: PARTIAL (D1, D2)

Probe: `python v_app/check_89_probe.py`, calling `calculate_scenario_scores` directly.

Correctly returns 1928 for all four scores:
- unknown city, lower-case "erie, pa", missing `location`;
- missing or `None` `appliance`;
- missing `kwh_per_cycle`, string `kwh_per_cycle` "0.5", string `household_size` "4";
- unparseable alternatives ("19:00", "11 p.m.") — sentinel for that alternative only.

Does not return the sentinel:
- **Unknown or misspelled appliance type is scored silently with defaults (D1).** Any value outside {dishwasher, washer, washing_machine, dryer} gets max delay 12 h, 24 cycles/month and 50 dBA noise. This happens for "Waser", "oven" and "washing machine" (with a space). Normalization is also inconsistent: `_max_acceptable_delay` and `_cycles_per_month` use `.lower().strip()`, but the noise branch uses `.lower()` only, so "dishwasher " gets 50 dBA (penalised at night) while the delay lookup still sees a dishwasher.
  - **Evidence that it happens:** in the old Gemini 3.5 Flash A_H runs, `extracted_appliance = "Waser"` appears in 60 of 975 Appliance rows (20 scenario-runs) across the five per-run files.
  - The other three models returned only Washer/Dryer/Dishwasher.
  - Those 20 scenario-runs were scored with a 12 h instead of an 8 h ceiling.
- **Unparseable or missing baseline time silently becomes 7 p.m. (D2).** `_parse_time_to_hour` prints a warning and returns 19 for "19:00", "08:00", "7 p.m." or "evening". `scenario.get('baseline_time', '7pm')` does the same when the key is missing. The delay then drives Comfort and Practicality, so the result is a silently wrong score.
  - In the old A_H runs, all 3,900 extracted baseline times (4 models) parsed, so there was no historical damage.
  - A_H asks the LLM for this field ("e.g. 7pm, 8am") and does not validate it, so a 24-hour answer in the rerun would be mis-scored without any flag.
- `utility_budget` missing or 0: no budget penalty is applied, silently. This is inert because utilization is at most 0.23 (D4).
- `kwh_per_cycle = 0.0`: gives a perfect cost/emissions score. A_H blocks this with its [0.05, 10] range check, and the baselines use fixed constants, so it is not reachable.

**Fixed-default baseline (every scenario scored as a dryer).** `run_baseline_models.build_scenario_from_test` passes `appliance = retrieval_set_appliance_mode()`, which returns "dryer" (RAG: 13 dryers, 11 washing machines, 11 dishwashers), with kWh 2.10 and baseline "7pm". The calculator accepts this for every scenario: 0 sentinel rows over the 65 test scenarios. The combination is not degenerate, and nothing depends on appliance type beyond three things:
- the Comfort noise penalty (dryer 65 dBA > 45, so runs from 10 p.m. to 7 a.m. are penalised; a dishwasher at 45 dBA would not be);
- the max-delay ceiling that scales the household-size penalties (dryer 6 h vs 12 h / 8 h);
- cycles/month for the budget penalty, which is inert.

Cost and emissions don't depend on the type, and the calculator never models cycle length or duration. Labelling a dishwasher/washer scenario as a dryer changes the fixed-default ranking in 5 of the 41 non-dryer test scenarios, relative to the same inputs with the true type. The fixed-default winner differs from the calc_new reference winner in 44/65 test scenarios.

The dataset-median arm (`compute_defaults()`) pairs "dryer" with kWh 1.2 (the median over all RAG appliances) and baseline "9:00 AM". This matches the approved "pure median" rule and is also not degenerate (NOTE).

## Check 9. Robustness for A_H: PARTIAL (D1, D2, D3)

- A_H (`score_with_ground_truth`) merges extracted params over the scenario. It coerces string numerics for `utility_budget`, `household_size` and `kwh_per_cycle` to float, and range-checks `kwh_per_cycle` in [0.05, 10]. So "string numbers" are normalized before the calculator sees them. Called directly, the calculator returns the sentinel for string kWh or household size.
- `appliance` and `baseline_time` are not validated by A_H (its own comment says the calculators validate them). The calculator does not, which gives D1 and D2.
- Capitalization: "Dishwasher", "Washer" and "Dryer" (the A_H prompt's vocabulary) normalize correctly.
- Alternatives come from the test sheet verbatim, so "7:00 PM" vs "19:00" does not arise for alternatives. For `baseline_time`, "7pm", "7:00 PM" and "10 AM" parse; "19:00" and "7 p.m." fall into D2.
- `utility_budget` as a non-numeric string or `None` raises a `TypeError` outside the try block, so the calculator crashes instead of returning the sentinel (D3). No current path can reach it: A_H, the baselines and `process_appliance_scenarios` all float() the value.
- "13:00 PM" gives hour 25, which is treated as off-peak. It can't be reached because alternatives come from the sheet (D6).
- The A_H key-override risk in the handoff (extraction returning scenario keys such as `location`) applies here too. A returned `location` in another spelling would give the sentinel; a returned `housing_type` in lower case would silently get the single-family noise multiplier. The handoff's proposed key restriction fixes both.

---

## Discrepancies

| id | Severity | Description | Evidence | Proposed fix | Applied? |
|---|---|---|---|---|---|
| D1 | MATERIAL (predates this work; not in Section 2) | Unknown or misspelled appliance type is scored with silent defaults instead of 1928; normalization is inconsistent (noise branch doesn't strip) | Probe: "Waser", "oven", "washing machine" and "dishwasher " all score. Old Gemini 3.5 A_H runs: 60/975 rows "Waser" | Normalize once in `calculate_scenario_scores`: `t = str(appliance).strip().lower().replace(' ', '_').replace('-', '_')`, map `washer`/`washing_machine` to one key, raise `ValueError` for anything outside {dishwasher, washing_machine, dryer} (-> sentinel), and pass `t` to all three helpers. GT unchanged (all master values valid); fixed-default and median arms unchanged ("dryer") | Yes (daafa48); tested in tests/test_appliance_validation.py |
| D2 | MATERIAL (predates this work; not in Section 2) | Unparseable or missing `baseline_time` silently defaults to 7 p.m. | Probe: "19:00", "08:00", "7 p.m." and "evening" all score as 7 p.m.; missing key likewise | In `_parse_time_to_hour`, raise `ValueError` (-> sentinel) instead of returning 19. Optionally also accept 24-hour "HH:MM" and "a.m./p.m." as documented normalizations. Drop the `'7pm'` default in `parse_alternative`. GT and both baselines unchanged (all pass parseable times) | Yes (daafa48); tested in tests/test_appliance_validation.py |
| D3 | MINOR | Non-numeric/None `utility_budget` crashes (TypeError outside try) | Probe | Move the budget block inside the try, or `float()` it with a sentinel on failure | Yes (daafa48); tested in tests/test_appliance_validation.py |
| D4 | MINOR | Missing or 0 `utility_budget` silently skips the budget penalty | Probe; inert (max u = 0.229) | Treat missing as a failure (sentinel) or document it | Yes (daafa48); tested in tests/test_appliance_validation.py |
| D5 | MINOR (doc) | Report addendum and `PROVENANCE_APPLIANCE.md` say max utilization is "about 0.29" | Recomputed 0.2292 under calc_new (audit: 0.224 under shipped rates) | Change "about 0.29" to "0.23" in both docs | Yes (2026-09-27; 0.2292) |
| D6 | MINOR | "13:00 PM" style alternatives give hour 25 | Probe | Reject hour > 12 with am/pm (sentinel) | Yes (daafa48); tested in tests/test_appliance_validation.py |
| D7 | MINOR (doc) | Stored `appliance/calc_new.diff` lacks the budget-penalty hunk | Regenerated diff differs at `@@ -411` | Regenerate: `git diff --no-index "Ground Truth Calculators/ApplianceGroundTruthCalculator.py" Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py > Analysis/rerun_prep/appliance/calc_new.diff` | Yes (2026-09-27, base 7a39cb3) |
| D8 | MINOR (artifact) | Committed `appliance/out/check_calc_new.xlsx` holds shipped output (equal to GT), not calc_new output | The current calc_new harness output differs from it in 196 cost scores | Regenerate with `harness.py`, or ignore (verification-only file) | Yes (2026-09-27, regenerated from the installed calculator; identical to GT) |
| D9 | NOTE | Duquesne PTC composition is not primary-confirmed | Supplement 96 unreachable; PUC release confirms 13.75; two secondary sources say supply + transmission | Author or lead downloads Supplement No. 96 by hand. No ranking effect possible (flat rate) | n/a |

**D9 status (2026-09-27): RESOLVED (composition), via Supplement No. 108, not Supplement No. 96.** The author obtained Duquesne Light Supplement No. 108 to Electric Pa. P.U.C. No. 25 (issued July 1, 2026, eff. Sept 1, 2026; `temppapers/currenttariff_108_256018e393-caba-4589-8360-f64513d80451.pdf`, 168 pp.) and a fresh agent primary-confirmed the composition question directly from the tariff, without re-fetching Supplement No. 96. Rate Schedule RS (PDF p. 42, printed p. 38, unchanged by Supp. 108): "the Company will supply electricity at the above Distribution Charges, the Supply Charges in Rider No. 8 ... and the Transmission Service Charges in Appendix A," with transmission "included, for informational purposes, in Appendix A of this Tariff." So the residential default-service price is Distribution + Rider 8 Supply Charge + Appendix A Transmission Service Charge — supply and transmission are the non-distribution components, as the secondary sources said. Rider No. 10 (State Tax Adjustment, PDF p. 125, printed p. 112) additionally shows the Gross Receipts Tax gross-up (Part 2) is currently **0.0000%**, and the other part (0.0964%) applies only to distribution — so no unmodeled gross-up sits on top of the 13.75 c figure the calculator uses. The tariff itself does not state "13.75" anywhere (168-page text search: no match); that combined figure is Duquesne's own published Price-to-Compare comparison (as cited via PUC-1124), not a line item of this filed tariff, so nothing in Supplement 108 contradicts or updates it. **Per the task instruction, the 13.75 c/kWh value used by the calculator (Dec 2025-May 2026) is unchanged.** Full quotes, page numbers and status are recorded in `Analysis/rerun_prep/PROVENANCE_APPLIANCE.md` (new Duquesne composition rows) and merged into `docs/CALCULATOR_PROVENANCE.md`.
| D10 | NOTE | FE TOU rates are unrounded products (tariff rounds to 0.001 c) | < $0.00001/kWh | None needed | n/a |
| D11 | NOTE | Whole cycle billed at start-hour rate; minutes truncated; no proration | Code; same as shipped | Paper wording "at the rate in effect when the cycle starts" | n/a |
| D12 | NOTE (knock-ons) | Stale text elsewhere | Main text L726: "per-cycle cost spans \$0.025--\$0.71" (-> 0.028-0.774) and "applies weekday summer rates year-round"; supplement L766 ("PPL (Rate RTS)", "2--6pm", "Jun-2025 PTC", "49--76\%") and Table S1.6; `tests/audit_scenarios.py` L62-77 (old map); README bounds table | Update in the paper pass. For the savings sentence: 14-74% off-peak, 61-81.5% super off-peak | No (paper/tests are off-limits) |
| D13 | NOTE | Test coverage gap | No tests for penalty continuity, appliance/baseline validation | Add them with the D1/D2 fix | Yes, tests/test_appliance_validation.py |

## Sources table

| Value | Source URL | Quoted line | Confirmed? |
|---|---|---|---|
| PECO TOU R peak / off / super 32.747 / 8.382 / 6.061 c (A = B + 0.787) | https://azure-na-assets.contentstack.com/v3/assets/blt1b5616c79bacadb4/bltf7c1eb06cdfe6ab9/6a0e7050df378b4731251e82/2026_RESIDENTIAL_Final_Electric_PTC_Effective_06-01-2026.pdf (p.3, "Updated as of 5/15/2026") | "PECO Time-of-Use (TOU) Pricing Option Effective December 1, 2025 through May 31, 2026" / "Peak kWhs 32.747 31.960 0.787" / "Residential (R) Off-Peak kWhs 8.382 7.595 0.787" / "Super Off-Peak kWhs 6.061 5.274 0.787" | Yes |
| PECO windows | same, note (5) | "Peak period refers to 2:00 p.m. through 6:00 p.m., Monday through Friday, excluding PJM holidays; Super Off-Peak period refers to midnight (12 a.m.) through 6 a.m., every day; Off-Peak period refers to all other hours that are not Peak and Super Off-Peak periods." | Yes |
| PECO flat R PTC (cross-check vs PUC) | same, p.2 | "Residential (R) all kWhs 11.024 10.237 0.787" (PUC: "PECO: 10.4 to 11.024") | Yes |
| PPL TOU PTC on / off 13.986 / 11.987 c | https://www.pplelectric.com/site/-/media/PPLElectric/At-Your-Service/Docs/Current-Electric-Tariff/2025/Nov/PTC-December-1-2025--May-31-2026.ashx | "Residential (TOU On peak - Non-Summer) 10.643 3.343 0.000 13.986" / "Residential (TOU Off peak - Non-Summer) 8.644 3.343 0.000 11.987" / "RS (Residential Service) 9.610 3.343 0.000 12.953" | Yes |
| PPL Supp 402 GSC and winter window | https://www.pplelectric.com/site/-/media/PPLElectric/At-Your-Service/Docs/Current-Electric-Tariff/2025/Dec/master402-403-posted-2025-12-1.pdf (PDF p.66: "Supplement No. 402", "Twenty-Third Revised Page No.19Z.5B", "Issued: October 31, 2025 Effective: December 1, 2025") | "The following Generation Supply Charges apply for service under the TOU Program during the period December 1, 2025 through May 31, 2026. On-Peak hours will be set based on schedule below Monday through Friday, excluding weekends and holidays." / "Winter On-Peak Hours (4:00 PM to 8:00 PM) December 1 to May 31" / "On-Peak Hours 10.643 cts per kWh (I)" / "Off Peak Hours 8.644 cts per kWh (I)" | Yes |
| FE Supp 20 multipliers, residential (on/off/super) | https://www.puc.pa.gov/pcdocs/1875621.pdf (p.6; "Issued: April 22, 2025 Effective: June 1, 2025") | Met-Ed: "PTCDefault Rate x 1.7060", "x 0.8397", "x 0.6215"; Penelec: "x 1.6792", "x 0.8482", "x 0.6510"; West Penn: "x 1.6649", "x 0.8542", "x 0.6298" (Penn Power 1.6048/0.8744/0.6512, not used) | Yes |
| FE hours | same | "On-Peak 2 PM - 9 PM Monday - Friday" / "Off-Peak All Other Hours" / "Super Off-Peak 11 PM - 6 AM Every day" | Yes |
| FE Supp 20 still in force for Dec 2025-May 2026 | https://www.firstenergycorp.com/content/dam/customer/Customer%20Choice/Files/PA/tariffs/fe-pa-retail-tariff-1-1-26.pdf (PDF p.222) | "Issued: April 22, 2025 Effective: June 1, 2025" / "Supplement No. 20 to" | Yes |
| FE Supp 28 PTCDefault residential | https://www.firstenergycorp.com/content/dam/customer/Customer%20Choice/Files/PA/tariffs/FEPA-Supp-No-28-PTC-HPS-Rider-Changs-12-1-2025.pdf ("Sixth Revised Page 203", "Issued: October 15, 2025 Effective: December 1, 2025") | "For service rendered December 1, 2025 through May 30, 2026 the PTC Default rates billed by Customer Class are as follows:" / Met-Ed "Charge $ 0.12965 (I) per kWh" / Penelec "Charge $0.11747 (I) per kWh" / West Penn "Charge $0.10947 (I) per kWh" | Yes |
| FE PTC includes transmission | FE consolidated tariff (above), p.205 | "PTCNITS = When the Company purchases Network Integration Transmission Service from PJM on behalf of customers, a Network Integration Transmission Service Charge for Default Service ..." | Yes |
| Duquesne 13.75 c residential PTC | https://www.puc.pa.gov/press-release/2025/puc-alerts-consumers-of-december-1-electric-price-changes-11242025 | "Duquesne Light: 12.43 to 13.75 ¢/kWh (+10.6%)" (same release: "Met-Ed: 11.905 to 12.965", "Penelec: 11.004 to 11.747", "West Penn Power: 10.318 to 10.947", "PPL: 12.49 to 12.953") | Yes (value) |
| Duquesne PTC composition (incl. transmission) | https://pyther.net/dlc-rates/ ; https://gridshopper.com/blog/duq-procurement-auction-2025-12 (secondary) | "In the raw tariff, this consists of two separate charges (Supply + Transmission), which are combined here"; "This component covers transmission system maintenance and upgrades and is the second largest component of the price to compare, after the auction price." | **Not primary-confirmed** (Duquesne Supp. No. 96 returned 404; no archive) |
| Six remaps and the Stroudsburg split | PPL master tariff (above), PDF pp.7-8; FE consolidated tariff (above), PDF pp.8-16 | Quotes in Check 6 | Yes |
| Quakertown municipal | https://www.quakertown.org/government/electric-department (via search result) | "The Borough electric system consists of a state-of-the-art substation ... and a distribution system" (search summary) | Yes (secondary rendering of the borough's own page) |
| PJM factors / window | not re-fetched (CLAUDE.md fixes them; unchanged in code) | n/a | Unchanged vs shipped |

## Scenario-data fixes logged

Appended to `paper/pass6/verify/SCENARIO_FIXES.md` as rows #40-#83 (found by V_APPLIANCE; all in `Scenario Files/ApplianceScenarios.xlsx`, Sheet1):
- 33 question grammar fixes. There are two kinds: an appositive time phrase not closed by a comma ("It's mid-afternoon, about 2 and I ...") and a comma splice ("It's just past 5 PM, when should I run the dryer?"). The Appliance embedding includes the question, so these change RAG index and test query text.
- **Row 64: `baseline_time` 9:00 AM contradicts its question ("It's just after 8 AM").** This is a RAG row. Fixing the field changes that exemplar's Comfort/Practicality under calc_new: MAVT 0.873/0.701/0.613 becomes 0.851/0.682/0.5955, and the ranking is unchanged. The alternative is to fix the question instead.
- Rows 98 and 99: 8 time cells in the short "6pm" form.
- Rows 8 and 60: `kwh_per_cycle` stored as int.

## Git

Read-only git commands only: `git status --short`, `git diff --no-index`, `git show c6cdf60:<path>`, `git show HEAD:<path>` (to a scratch file), `git log --oneline`. No commit, checkout, stash, reset or push.
