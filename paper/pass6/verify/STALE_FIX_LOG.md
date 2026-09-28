# Stale-value fix log (2026-09-27)

Follow-up to `SCALC_APPLY_LOG.md` ("Stale text found outside these items"). Targets:
`paper/paper_draft_v2.tex` (main), `paper/supplementary.tex` (S), `README.md`. Every value
comes from the installed calculators (HEAD 95d7fce) or the current `Ground Truth/*.xlsx`; no
LLM output was used. No git write, no paid API call; no `.py`, `.xlsx` or
`docs/CALCULATOR_PROVENANCE.md` edited. Scripts, outputs and pre-edit copies are in the session
scratchpad `stale/` (`hvac_example.py`, `shower_example.py`, `weights.py`, `spearman3.py`,
`*_out.txt`, `gt_*` historical GT copies, `pre/`). Stop-slop skill loaded before editing.
Line numbers are after the edits.

Checks after editing (`stale/check.py`, same as `scalc/check.py`): braces balance in both .tex
files and the bib; every `\cite*` key (81 main, 24 S) is in `cas-refs.bib`; every
`\ref`/`\eqref` label exists; environments balance; no duplicate bib key.

## Edits

| Item | File:line | Old -> new | How computed |
|---|---|---|---|
| 1 HVAC worked example | S:698-700 | rows (sorted by $s_j$) `76F 0.11/0.30/1.00/0.85 **0.466**; 80F 0.17/0.37/0.67/0.85 0.442; 72F 0.06/0.24/0.67/0.78 0.353` -> `80F 0.44/0.45/0.67/0.83 **0.548**; 76F 0.29/0.37/1.00/0.83 0.541; 72F 0.16/0.29/0.67/0.76 0.398`. Rows reordered so the table stays sorted by $s_j$ with the bold winner on top (winner 76 F -> 80 F). Prose unchanged (it names no winner). | `stale/hvac_example.py`: installed `HVACGroundTruthCalculator.calculate_scenario_scores` on the S:677-689 scenario (95 F, 2,200 sq ft single-family, R-15, SEER 13, age 10, occupied_all_day, household 4, \$200 budget, \$0.19/kWh, cool mode, 72/76/80), $s_j$ = 0.30/0.35/0.20/0.15 x rounded scores: 0.3975 / 0.5410 / 0.5480. Raw: 11.29/10.26/9.23 kWh, \$2.15/1.95/1.75. (The pre-95d7fce calculator gives 0.4685/0.4475/0.3525, close to the old table.) |
| 2 cost vs emissions differential | S:779 | "the cost differential is an order of magnitude larger than the emissions differential" -> "the cost differential is 2.3 to 12 times the emissions differential" | `ApplianceGroundTruthCalculator` constants: emissions 1 - 0.976/1.041 = 6.24%. Peak to off-peak cost cut / 6.24%: PPL 14.29% (2.29x), West Penn 48.69% (7.80x), Penelec 49.49% (7.93x), MetEd 50.78% (8.13x), PECO 74.40% (11.92x). (Super off-peak 61.2-81.5% = 9.8-13.1x; the sentence refers to the peak/off-peak split.) |
| 3 Table S2.2 | S:823-826, 828-831 | Entropy overall 0.269/0.371/0.161/0.199 -> 0.272/0.370/0.171/0.186; HVAC 0.336/0.320/0.269/0.074 -> 0.337/0.315/0.278/0.070; Appliance 0.193/0.465/0.124/0.218 -> 0.190/0.467/0.124/0.219; Shower 0.335/0.316/0.122/0.227 -> 0.333/0.318/0.123/0.226; MEREC overall 0.194/0.131/0.404/0.271 -> 0.196/0.134/0.403/0.267; HVAC 0.138/0.128/0.663/0.071 -> 0.158/0.135/0.656/0.051; Appliance 0.208/0.044/0.292/0.456 -> 0.194/0.043/0.298/0.466; Shower 0.251/0.245/0.203/0.300 -> 0.250/0.246/0.203/0.302 | see "Objective weights" below |
| 3 S text | S:837 | "0.371 ... 0.161 ... 0.199" -> "0.370 ... 0.171 ... 0.186"; "0.663 ... 0.128" -> "0.656 ... 0.135"; "0.044 ... 0.456" -> "0.043 ... 0.466". "MEREC weights diverge for HVAC and Appliance and remain close to the design vector for Shower" still holds, unchanged. | same |
| 3 main | main:768 | "puts $0.663$ on Comfort" -> "$0.656$" | same |
| 3 README | README:442 | "Comfort (0.663 for HVAC" -> "0.656". The result numbers in the same bullet (0.676 vs 0.600) left for S4. | same |
| 3 checked, no change | main:1072 | "Every entropy vector puts a combined 0.64--0.66 on Energy Cost and Environmental Impact": new sums 0.643 (overall), 0.652 (HVAC), 0.657 (Appliance), 0.651 (Shower); still 0.64--0.66 | same |
| 4 Spearman | main:613 | "0.92" unchanged: current value 0.923 | see "Spearman" below |
| 5 hot water | main:609 | "about 155 gallons" -> "about 153 gallons" | `stale/shower_example.py`: 20 min x 2.5 GPM x 4 x f_hot, heater 120 F, target 105 F. Old anchors (45/65 F) give 155.0 gal at 50 F outdoor (inlet 53.37 F), the implied temperature of the old text; new anchors (48.5/68.2 F) at 50 F give inlet 56.75 F, f_hot 0.763, 152.6 gal. Tank 50 gal / 40 gal usable (0.80 factor) is the example's scenario input and matches the calculator; left. |
| 6 README budget | README:359, 365, 367 | "A four-tier" -> "A three-tier"; rows `1.00 <= u < 1.50 | Exponential ...` and `u >= 1.50 | 0 (eliminated)` -> one row `u >= 1.00 | Exponential: 0.5 * e^{-3(u - 1.0)} (continuous, never 0)`; anchors: dropped "; infeasibility elimination (Gathergood 2012)" | `calculate_budget_penalty` in all three calculators (HVAC :357-374, Shower :250-263, Appliance :472-488) |
| 6 README heating | README:394 | "(76 F cooling, 70 F heating)" -> "71 F heating" | HVAC calc `WINTER_OPTIMAL = 71` (HSP set point) |
| 7 base gain wording | main:672 | "an always-on standby baseline" -> "a constant base internal gain" | HVAC calc `BASE_INTERNAL_GAIN_BTUH = 17900/24` (IECC R405.5.2(1) IGain constant) |
| 7 base gain wording | main:699 | "The 746\,BTU/hr standby term keeps" -> "The 746\,BTU/hr base internal gain keeps" | same |

## Objective weights (item 3)

`stale/weights.py` imports `EntropyWeights.load_ground_truth_data`, `resolve_criterion_columns`,
`build_comparison_table` and `merec_weights.run_merec_all_scenarios` (the scripts under
`Miscellaneous Scripts/core-automation/`), points them at a scratch copy of a GT folder, and
prints only (merec_weights' import-time `os.makedirs` suppressed; nothing written to the repo).
Scope as the table states: all 285 scenarios (HVAC 105, Appliance 100, Shower 80), no
sentinel rows.

Gate: the current Table S2.2 is NOT reproduced by the GT at 95d7fce~1 (it gives MEREC HVAC
Comfort 0.709) or at 4a93468~1 (0.663 but Practicality 0.051). It is reproduced to all 32
printed digits by the GT before Phase I (`846b02e~1`): entropy overall 0.269/0.371/0.161/0.199,
MEREC HVAC 0.138/0.128/0.663/0.071, etc. So the table dated from before 846b02e, and the
Appliance rows changed too (Appliance GT changed at 846b02e).

Current GT (4 decimals; Ene / Env / Com / Pra):

| Vector | Ene | Env | Com | Pra |
|---|---|---|---|---|
| Entropy overall | 0.2724 | 0.3701 | 0.1715 | 0.1860 |
| Entropy HVAC | 0.3374 | 0.3148 | 0.2776 | 0.0702 |
| Entropy Appliance | 0.1905 | 0.4667 | 0.1240 | 0.2188 |
| Entropy Shower | 0.3332 | 0.3182 | 0.1230 | 0.2256 |
| MEREC overall (n=285) | 0.1963 | 0.1338 | 0.4030 | 0.2669 |
| MEREC HVAC (n=105) | 0.1581 | 0.1349 | 0.6561 | 0.0509 |
| MEREC Appliance (n=100) | 0.1937 | 0.0428 | 0.2976 | 0.4658 |
| MEREC Shower (n=80) | 0.2495 | 0.2460 | 0.2026 | 0.3019 |

`implied_weights.py` is not quoted in the paper, so it was not rerun.

## Spearman (item 4)

Source: `compute_cross_criterion_correlation` in
`Miscellaneous Scripts/core-automation/evaluate_architecture_metrics.py` (pooled Spearman of
GT `energy_cost_score` vs `environmental_score` over all matched test alternatives), stored as
`cross_criterion_rho_overall` = 0.9202 in every `metrics_summary_*.xlsx`. `stale/spearman3.py`
runs that function on the script's own `load_ground_truth` + `match_scenarios`, with the
architecture side replaced by the TestScenarios sheet (one row per alternative) so all 195
scenarios match. (Matching the old architecture outputs to the current GT drops 20 Appliance
scenarios because Phase I changed their text; hence the sheet.) Gate: old GT + old
TestScenarios (`846b02e~1`) gives 0.9202 (HVAC 0.9992, Appliance 0.8988, Shower 0.9662),
matching the stored value. Current GT + current TestScenarios: overall 0.9230 (HVAC 0.9992,
Appliance 0.9020, Shower 0.9637), 585 alternatives. "0.92" stands. No other GT correlation
near main:613 (main:615 swing values were updated by S-CALC).

## Item 8 grep (both .tex files)

| Pattern | Hits | Decision |
|---|---|---|
| `0.38` | main:209, S:864, S:962 (tau/ablation values), S:578 ($\rho=0.38$ dryers, S-CALC recomputed), S:1019/1032 (plot coords) | not calculator bounds; left |
| `3.29`, `1.96`, `2.10` | S:1005-1109 plot coordinates only | left |
| `18.04`, `0.71`, `0.14--1.14`, `\$1.14`, `20\,Btu`, `400\,n`, `45/65\,\textdegree`, `0.9 shower`, `50\,gal`, `70\,^\circ` / `70\,\textdegree` | none | - |
| `0.025` | main:939 (parameter-error table), S:1031 plot | not calculator; left |
| `20\,BTU` | main:699 "220\,BTU/hr ... per occupant" | current value; left |
| `800` | main:778, main:1074 ($\tau=0.800$), S:1020 plot | not calculator; left (fixed-default taus are an S4 item) |
| `50-gal` | main:609 (worked example tank) | scenario input, consistent with calc; left |
| `30\%` | main:351 (end-use share), main:583 (Energy Cost weight) | not a degradation cap; left |
| `1.5` | main:248-273 ($\alpha$ sweep ticks/coords) | not the budget cutoff; main:665 already `u \ge 1.0` |
| `R-11/13/19` | S:576 tier bands R-8-12/13-18/19-24 | current; left |
| `standby` | main:672, 699 (fixed, item 7); S:938 "tank adds standby loss" | S:938 is water-heater standby loss, correct; left |
| `four-tier`, `Gathergood`, `eliminat` | none left in .tex; `gathergood2012` still cited at main:670 for the curve shape | left |

## Needs the S4 rerun (not changed here; they use the weight vectors on model outputs)

- `Miscellaneous Scripts/validation/SensitivityAnalysis.py` reads
  `Scoring Logic and Documentation/method/{merec_weights_summary,entropy_weights}.xlsx`, which
  still hold the pre-Phase-I vectors, and hard-codes the old Table S2.2 values in `merec_tab` /
  `entropy_tab` (lines ~148-166; docstring line 97 "0.663"). Before S4: rerun
  `EntropyWeights.py` and `merec_weights.py` to refresh the xlsx and update the hard-coded tabs.
- S Tables S2.3/S2.4 (S:846-904): tau / Top-1 under entropy per-type, MEREC per-type, MEREC
  HVAC vector; bold Gemini reversal cell (0.676 / 80.4) and S:904 text.
- main:1015: "all 20 model--weight-vector cells, by at least $0.304$", the Gemini reversal
  "$0.676$ vs.\ $0.600$".
- main:613: "leaves LLM-parameterized reference scoring ahead ... in all 20 model--weight-vector
  cells".
- main:768 (framing only) and main:1072: "$\mathcal{A}_{\text{E}}$ loses most of its margin over
  $\mathcal{A}_{\text{D}}$" under the MEREC vectors.
- README:110 and README:442-443 (reversal for Gemini, 0.676 vs 0.600).

## Noticed, not fixed (outside this task's spans)

- main:699 "The 746\,BTU/hr base internal gain keeps a zero-$\Delta T$ setpoint from producing
  exactly zero load" holds in cooling mode only: in heating mode the internal gain offsets the
  loss, so a zero-$\Delta T$ heat setpoint gives zero load.
- README:149/151 dataset-median tau 0.641 and fixed-default tau 0.614 (and the matching paper
  numbers listed as S-CALC stale item 4) are calculator-only baselines; S-CALC assigned them to
  S4 via `Output Files/Baselines/baseline_metrics.csv`.
