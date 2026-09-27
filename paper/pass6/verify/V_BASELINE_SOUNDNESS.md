# V_BASELINE: adversarial soundness review of the non-LLM baselines

Written 2026-09-26 by the baseline-verification agent (Phase V). Scope: every non-LLM condition the
paper or the pipeline computes: fixed default (FD), dataset median (DM), nearest neighbour (NN, test
set), the offline copy-only control of the RAG ablation (the same NN code on the RAG corpus), the
single-criterion recovery table, and the unreported random / uniform baselines. Every number below
was recomputed offline in scratch against the **new** calculators in `Analysis/rerun_prep/calc_new/`
(imported by path, not installed) on the current scenario data. No repo file was edited except this
report and the rows appended to `paper/pass6/verify/SCENARIO_FIXES.md`. No API call was made.

Scratch scripts and outputs (session scratchpad, `v_base/`): `run_checks.py` (new GT workbooks,
DM, FD, reference, single-criterion, per-scenario CSV), `run_nn.py` (NN with RAG scores rescored by
the new calculators, label diagnosis, priority tie rule), `run_match.py` (official evaluation
matcher), `run_appl_decomp.py` (Appliance diagnostic, full-ranking identity check), `scan_text.py`.

Throughout, "Overall" means pooled over the 195 scenarios of the three decision types, as the paper
does for the FD row. Baselines have no model dimension, so nothing here is pooled across models.

---

## Ranked issues

| # | Severity | Issue | Evidence | Proposed fix (within the author's decisions) |
|---|---|---|---|---|
| 1 | **MUST-FIX-BEFORE-RERUN** (code only, no API dependency, but the RAG-ablation run writes the copy-only rows in the same pass) | **NN never matches a Shower alternative.** `nearest_neighbor_prediction` (`Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py` L687-735) compares `md["alt{j}"] == alt_name`. The index metadata stores Shower labels as `"8 min"` (`build_scenario_metadata` L269-270), the test-set NN passes `8.0` (float, `run_baseline_models.py` L368) and the RAG ablation passes `"8"`. No label ever matches, so every Shower scenario falls to the "mean over all retrieved alternatives" branch, the three alternatives get **identical** scores, and the ranking is the listed order. | Test-set NN: 60/60 Shower scenarios have identical scores for all three alternatives, winner is alternative_1 in 60/60 (shipped `Output Files/Baselines/baseline_nearestneighbor.xlsx` and `pipeline/nn_after/`, same result). RAG-ablation copy-only: 20/20 Shower scenarios identical (`Analysis/RAG_Ablation/rag_ablation_results.xlsx`). The published NN Shower tau 0.733 / Top-1 75.0% is therefore list order, not retrieval. With normalised labels the new-calculator NN Shower result is tau 0.278 / Top-1 43.3% (was 0.733 / 75.0). | Normalise both sides before comparing (e.g. `RBM.normalize_alternative(str(x).replace(" min", ""), dtype)` on the metadata label and the target label). One shared helper fixes the test-set NN and the copy-only control. Re-run `nn_check.py`-style parity afterwards. |
| 2 | **FIX-OFFLINE-LATER** (decide before the copy-only number is regenerated) | **NN fallback produces all-tied scores, so the ranking is list order.** When none of the k = 3 exemplars shares an alternative label, the prediction is the mean over every retrieved alternative, identical for all three targets. | Test set, new calculators, after fix 1: 8/70 HVAC, 10/65 Appliance, 10/60 Shower scenarios have zero label hits (all three alternatives tied). RAG-ablation copy-only: 7/35 HVAC, 3/35 Appliance (plus all Shower, issue 1). | Keep the baseline simple but stop list order deciding: either match each target to the exemplar alternative nearest in value (setpoint degrees, clock hours on a circle, minutes), or treat a zero-hit scenario as unscored/inclusive (tau 0, Top-1 1/3), and say which in the supplement. |
| 3 | **PAPER-TEXT** (numbers regenerate automatically) | **The printed copy-only tau (0.001) excluded every tied scenario.** The shipped results were produced (2026-08-05) by an older `scenario_metrics` that took tau from the raw scores; all-tied predictions gave NaN, so 30 of the 90 scenarios (all 20 Shower + 10 fallback) were dropped silently. Main L810 and S L966-973 say it is evaluated on the full 90-scenario set. The current code (rank-based tau, commit 19862aa) scores those scenarios, so the regenerated number will differ even without fixes 1-2 (Shower alone would read tau 0.50 from list order). | `rag_ablation_results.xlsx`: 60 non-NaN scenario taus of 90; mean 0.00112 equals the printed 0.001. | After fixes 1-2 and the rerun, update main L810 and S L966-973 and the CI; state n. |
| 4 | **FIX-OFFLINE-LATER + PAPER-TEXT** | **Single-criterion table breaks criterion ties by first occurrence, not by the reference's rule.** Ties on a single criterion are common (Appliance energy cost: 52/65 scenarios have a tie, 20/65 all three equal; HVAC practicality: 63/70 tie, 34/70 all equal). First occurrence hands every such tie to alternative_1, so the statistic partly measures list position (which the author does not want discussed). | New calculators, Top-1 (%), first occurrence vs `TIE_BREAK_PRIORITY`: Appliance energy 64.6 vs 47.7, Appliance environmental 53.8 vs 47.7, HVAC energy 10.0 vs 17.1, HVAC practicality 30.0 vs 20.0. The same with a last-occurrence rule gives Appliance energy 26.2, so the printed cell swings by 38 pp on the tie rule alone. | Break single-criterion ties with the reference rule (criterion, then Environmental, Energy Cost, Comfort, Practicality, then input order) in `paper_pipeline/compute_dispersion_diagnostics.py::single_criterion_recovery` (`idxmax`) and `paper_pipeline/competitive_baselines.py::_rank_desc_first_occurrence`; update the table note at main L829. |
| 5 | **PAPER-TEXT** | **The single-criterion "floor" is not a no-inference floor.** It ranks by the test scenario's own *reference* criterion scores, i.e. it uses the true hidden parameters. Main L775 lists it as one of "three floors ... without per-scenario inference". A reviewer will call this an oracle diagnostic. | `compute_dispersion_diagnostics.py` L187-209 and `competitive_baselines.py` L159-190 read `gt_*` scores. | Describe it as a diagnostic on the reference (how often one criterion decides), not as a floor. Main L745 also says "two non-LLM baselines" while L775 says "three floors"; the Methods (L747-749) never describe the single-criterion analysis. |
| 6 | **PAPER-TEXT** | **DM/FD Appliance collapse is entirely the baseline run time, and that time is written in the question.** Every Appliance question states the current time and names the appliance ("It's around 2 in the afternoon and I need to run the washing machine"). DM/FD deliberately don't read it (author decision, respected). Consequence: swapping in the true baseline time alone lifts DM Appliance from tau 0.179 to 0.815 and FD from 0.190 to 0.908 (A_H's Appliance tau was 0.906-0.975). Swapping in the true appliance type or kWh changes tau by at most 0.05, and lowers FD's. | `run_appl_decomp.py` output (table in Q3). | Say in Methods (L749) and S1 that neither condition reads the question, including the stated time and appliance, and in L1071 that A_H's Appliance margin is reading that time. No code change. |
| 7 | **PAPER-TEXT** | **The DM description never says which dataset.** L749 "(the dataset median, or the mode for a categorical parameter)" reads like test-set statistics. The code uses the 90 retrieval scenarios only (verified: 35/35/20 rows, identity-checked against the RAG sheets). | Q4 below. | "... the median (mode for a categorical parameter) over the 90 retrieval scenarios, excluding every test scenario; nothing is read from the question." Same in S L1299 and S L1328. |
| 8 | **PAPER-TEXT** | **S1 FD description is out of date.** S L622-629 say Appliance kWh/cycle is per appliance type with a 1.00 fallback; `tab:fixed_default_constants` (S L641-643) lists washer / dryer / dishwasher. The FD now assigns the retrieval-set mode, dryer at 2.10 kWh, to every Appliance scenario. | `run_baseline_models.py` L140-150, L184-203. | Replace the three kWh rows with "Appliance type: dryer (retrieval-set mode)" and "kWh/cycle: 2.10"; rewrite the per-type sentence and drop the fallback clause. |
| 9 | **PAPER-TEXT** | **Every printed baseline number moves under the new calculators** (HVAC most). See Q2 table. FD HVAC 0.933 -> 0.838, DM HVAC 0.933 -> 0.848; heat-mode HVAC scenarios drop to about 0.74-0.76 because the heat-pump HSPF path now makes the ranking depend on the hidden SEER / R-value. L1071's "A_H clears the FD on HVAC for only two of the four models" and "R-15, SEER-13 sits near typical values" need re-checking after the rerun. | Q2. | Take all numbers from the regenerated pipeline after the rerun; list of sentences in Q6. |
| 10 | FIX-OFFLINE-LATER | **NN output rows carry no disambiguating columns.** The evaluation matcher (`evaluate_architecture_metrics.match_scenarios`) keys on (question, location) and then on outdoor_temp / flow_rate / household_size / utility_budget / housing_type for Shower, whose question is constant. NN rows carry none of these, so Shower matching falls back to alternative overlap and "first unused candidate". | Checked: all 195 NN (and FD) scenarios currently pair with the correct new-GT row (`run_match.py`). Correct today by the order of the GT rows, not by design. | Copy the Test row's homeowner fields into each NN output row, as FD already does. |
| 11 | NONE (report only) | FD and DM are near-duplicates outside Appliance: identical full orderings in 69/70 HVAC and 57/60 Shower scenarios (2/65 Appliance). | Q2. | Optional one clause: "the two differ materially only on Appliance". |
| 12 | NONE | Dead code: FD parses `appliance_age` (lower band edge) but no Appliance calculator reads it; FD constants 2.54 / 51.8 / 430 / sqft map unused; DM takes the occupancy mode on raw labels (`standard`), which the calculator maps to `occupied_all_day` (same behaviour). | calc_new Appliance never reads `appliance_age`. | Redundancy pass. PROVENANCE_BASELINES lists appliance age as a used input; mark it unused. |
| 13 | NONE (unreported baselines) | Random baseline seeds collide across scenarios (`42 + seed + 7*idx`: scenario 0 seed 7 = scenario 1 seed 0), so its draws are correlated across scenarios; Uniform is pure list order. Neither is reachable from the CLI or printed. `Output Files/Baselines/` also holds orphan `baseline_oracle.xlsx`, `baseline_random_aggregated.xlsx`, `baseline_uniform.xlsx` with no current producer. | `run_baseline_models.py` L403-470. | Move the orphans aside when the baselines are regenerated so no script picks up a stale file. Fix the seed formula only if Random is ever reported. |
| 14 | NONE (ordering note for Phase P5) | `run_baseline_models.py` (FD and NN) and the copy-only control read calculators from `Ground Truth Calculators/` and exemplar scores from the RAG sheets. They must run after the calculators are installed and after `sync_rag_ground_truth_scores.py`, or NN/copy-only will average old-calculator scores against a new-calculator reference. | Imports at `run_baseline_models.py` L20-39; `load_source_df` reads the RAG sheets. | Put them after step C3 of the handoff's refresh chain. |

No sentinel ever enters a baseline average (0 sentinels anywhere; `scenario_metrics` and
`filter_failed_scenarios` both drop sentinel scenarios). No baseline reads a true engineering value.

---

## Q1. What each baseline sees and does

| Baseline | Code | Read from the scenario | Constants | Scoring and ranking | Tie rule | Leak? |
|---|---|---|---|---|---|---|
| Fixed default (FD) | `run_baseline_models.py` `build_scenario_from_test` L154-221, `run_calculator_on_scenarios` L224-328 | Test row: `question` (only the HVAC calculator reads it, for the heat/AC mode), `location` (Appliance tariff), `household_size`, `utility_budget`, `housing_type`, `square_footage` + `outdoor_temp` (HVAC), `outdoor_temp` (Shower), `appliance_age` band (parsed, never used), alternatives | HVAC R-15, SEER 13, age 13, `occupied_all_day`, $0.19/kWh; Appliance `dryer` (retrieval-set mode, via `compute_defaults`), 2.10 kWh, baseline `7pm`; Shower 2.5 GPM, 50 gal, 120 F | Reference calculators; `apply_mavt_ranking` | 10-dp rounding, then `TIE_BREAK_PRIORITY`, then input order (same as reference) | No. The Test sheet holds only homeowner fields and banded labels; every hidden parameter is a constant. |
| Dataset median (DM) | `run_hybrid_ablation_experiments.py` `compute_defaults` L667-689, `build_scenario` L694-719, `score_scenario` L722-765 | Master row (same values the Test sheet shows): `question`, `location`, `household_size`, `housing_type`, `utility_budget`, `square_footage` + `outdoor_temp` (HVAC), `outdoor_temp` (Shower); alternatives from the Test row | Retrieval-set statistics: R 16, SEER 13, age 16, `standard`; kWh 1.2, `dryer`, `9:00 AM`; 2.25 GPM, 45 gal, 120 F | Reference calculators; `apply_mavt_ranking`; `scenario_metrics` | Same as reference | No. `build_scenario` copies only homeowner fields; hidden parameters are the constants. |
| Nearest neighbour (NN, test set) | `run_baseline_models.py` L335-381 + `run_rag_ablation_experiments.py` `retrieve_similar` L574-614, `nearest_neighbor_prediction` L687-735 | Query = `format_embedding_text` on the Test row (identical to A_E's query); scores of the k = 3 retrieved RAG scenarios | k = 3, all-MiniLM-L6-v2, 90-scenario index built fresh | Mean of the exemplars' criterion scores for the same alternative label, else mean over all retrieved alternatives; `apply_mavt_ranking` | Same as reference, so a fully tied prediction falls to input order (issues 1-2) | No. It reads other scenarios' reference scores, exactly the corpus A_E sees. |
| Copy-only control (RAG ablation) | same NN code, leave-one-out over the 90 RAG scenarios | as NN | as NN | as NN | as NN | No |
| Single-criterion recovery | `compute_dispersion_diagnostics.py` L187-209 (paper table), `competitive_baselines.py` L111-190 | The test scenario's own **reference** criterion scores | none | argmax of one criterion vs the reference winner (and tau of that ordering in `competitive_baselines`) | First occurrence (issue 4) | Uses the reference by design: a diagnostic, not a floor (issue 5) |
| Random / Uniform | `run_baseline_models.py` L403-470 | alternatives only | U(0,100) / 50 | weighted sum, `_rank_with_weights_and_tiebreak` | Uniform = input order | No; not reported |

The LLMs get every field FD/DM/NN read (the Test sheet row), so no baseline has information the LLMs
lack. The oracle-parameter ceiling is the reference itself (tau = 1 by construction); the hybrid
harness deliberately omits it (docstring L30-35).

## Q2. Results against the new calculators, per decision type

New = `calc_new`, current scenario data. Old = `Analysis/rerun_prep/pipeline/baseline_old_vs_new.csv`
column `new` (current baseline code, shipped calculators) and `nn_old_vs_new.csv`.

| Baseline | Type | tau old -> new | Top-1 % old -> new | Sentinel scenarios | Any MAVT tie | All 3 scores identical | Distinct full orderings | Most common winner (share) |
|---|---|---|---|---|---|---|---|---|
| DM | HVAC (70) | 0.933 -> **0.848** | 95.7 -> **84.3** | 0 | 1 | 0 | 40 | 78 (18.6%) |
| DM | Appliance (65) | 0.190 -> **0.179** | 49.2 -> **47.7** | 0 | 0 | 0 | 58 | 2:00 PM (16.9%) |
| DM | Shower (60) | 0.789 -> 0.789 | 81.7 -> 81.7 | 0 | 1 | 0 | 27 | 5 min (30.0%) |
| DM | Overall (195) | 0.641 -> **0.607** | 75.9 -> **71.3** | | | | | MAE 0.133 -> 0.135 |
| FD | HVAC | 0.933 -> **0.838** | 95.7 -> **82.9** | 0 | 1 | 0 | 40 | 78 (18.6%) |
| FD | Appliance | 0.138 -> **0.190** | 30.8 -> **32.3** | 0 | 0 | 0 | 60 | 7:00 PM (18.5%) |
| FD | Shower | 0.800 -> 0.800 | 85.0 -> 85.0 | 0 | 0 | 0 | 27 | 5 min (30.0%) |
| FD | Overall | 0.627 -> **0.610** | 70.8 -> **66.7** | | | | | MAE 0.129 -> 0.132 |
| NN as coded | HVAC | 0.133 -> **0.076** | 42.9 -> **37.1** | 0 | | **8** | | |
| NN as coded | Appliance | 0.292 -> **0.303** | 55.4 -> **56.9** | 0 | | **10** | | |
| NN as coded | Shower | 0.733 -> 0.733 | 75.0 -> 75.0 | 0 | | **60** (list order) | 1 | alternative_1 (100%) |
| NN as coded | Overall | 0.371 -> **0.354** | 56.9 -> **55.4** | | | | | |
| NN, labels normalised (diagnostic) | Shower | 0.278 | 43.3 | 0 | | 10 | | |
| NN, labels normalised | Overall | 0.214 | 45.6 | | | | | |

No baseline always picks the same alternative, and none produces all-tie rankings except NN. DM and
FD are not constant across scenarios (40 / 58-60 / 27 distinct orderings). The reference ranking
recomputed through the ablation harness equals the ranking in freshly generated
`ground_truth_*.xlsx` (new calculators) for all 195 test scenarios.

HVAC by mode (the new mode rule reads the question; 37 AC, 33 heat, all resolved, 0 sentinels):
DM tau 0.928 AC / 0.758 heat; FD 0.928 AC / 0.737 heat. Heat mode is where the hidden parameters
now matter (HSPF from SEER, R-value), which is the intended physics, not a degeneracy.

## Q3. Degeneracy checks

- **Dryer for every Appliance scenario.** In calc_new the appliance type enters three places:
  late-night (22:00-07:00) noise penalty (dishwasher 45 dBA is at the threshold and gets none,
  dryer 65 and washer 74 get it), the max acceptable delay (dryer 6 h, washer 8 h, dishwasher 12 h)
  that scales the household-size penalties and gates the daytime practicality floor, and cycles per
  month (dryer 24, washer 25, dishwasher 18) in the budget penalty. So a dishwasher scored as a dryer
  is pushed away from night runs. It is not what drives the result: substituting the true type moves
  DM Appliance tau 0.179 -> 0.179 and FD 0.190 -> 0.138. Per true type: DM tau dishwasher 0.333,
  dryer 0.194, washer 0.016; FD 0.233 / 0.222 / 0.111.

  | Appliance, diagnostic swap (true value of one parameter) | DM tau / Top-1 | FD tau / Top-1 |
  |---|---|---|
  | none (as run) | 0.179 / 47.7 | 0.190 / 32.3 |
  | appliance type | 0.179 / 46.2 | 0.138 / 29.2 |
  | kWh per cycle | 0.200 / 47.7 | 0.149 / 35.4 |
  | appliance type + kWh | 0.200 / 47.7 | 0.108 / 32.3 |
  | **baseline run time** | **0.815 / 86.2** | **0.908 / 92.3** |

  The collapse comes from the constant baseline time (9 AM / 7 PM), which the question states for
  every scenario (issue 6). The "dryer at median 1.2 kWh" combination in the DM is incoherent
  physically but inconsequential (row 2-4).
- **HVAC.** Outdoor temperature is a homeowner field given to every condition, not hidden. Under DM
  parameters no non-Off alternative has zero load in any of the 70 scenarios (0/70 scenarios with a
  zero-load setpoint), so there are no all-tie scenarios; 1/70 has an exact MAVT tie (the reference
  also has 1). Practicality is identical across the three alternatives in 34/70 scenarios, in the
  reference as well: a property of the calculator, not of the baseline.
- **Shower.** DM (2.25 GPM, 45 gal, 120 F): 1/60 MAVT tie, 0 all-tie; winner is alternative_1 in
  52/60. FD: 0 ties; alternative_1 in 54/60. Not degenerate; both mostly pick the shortest duration,
  which is also what Energy Cost alone picks.
- **NN**: see issues 1-2.
- Sentinels: 0 for every baseline and type.

## Q4. Is anything computed from the test set?

- DM statistics: 35 HVAC / 35 Appliance / 20 Shower master rows, the complement of the 195 Test
  matches; `retrieval_set_rows` raises unless the set equals the RAG sheets on (location, household
  size, budget, housing type). Confirmed by running it: 35/35/20, no exception.
- FD appliance type: the same `compute_defaults()` (retrieval set). All other FD constants are fixed
  literals.
- NN / copy-only index: built from the three RAG sheets only (35 + 35 + 20 = 90 scenarios); the
  test-set NN excludes nothing it shouldn't (`test_<i>` ids can't collide).
- Calculator bounds use all 285 scenarios, which is part of the reference definition (accepted).
- Nothing else in the baseline paths reads Test statistics.

## Q5. Determinism and tie rule

- FD, DM, NN, copy-only: deterministic, all ranked by `apply_mavt_ranking` (10-dp rounding, then
  `TIE_BREAK_PRIORITY`, then input order), the reference's own rule. The pipeline agent reproduced
  the shipped NN file exactly, so the fresh Chroma/HNSW build is reproducible in practice.
- Single-criterion recovery: deterministic, but ties go to the first listed alternative, not the
  reference rule (issue 4).
- Random: seeded (collisions, issue 13). Uniform: list order.

## Q6. Paper sentences that no longer match the code or the new numbers

Main = `paper/paper_draft_v2.tex`, S = `paper/supplementary.tex`. Numbers marked "new" are the
calc_new values from Q2; the post-rerun pipeline is authoritative.

| Location | What is wrong |
|---|---|
| Main L745 | "two non-LLM baselines", but L775 names three floors, and the NN baseline is computed but never reported. |
| Main L749 | DM: doesn't say the statistics are over the 90 retrieval scenarios only, nor that nothing is read from the question (the appliance and the current time are stated there). FD: "one fixed engineering value for each withheld parameter" is no longer true for appliance type (a retrieval-set mode, not an engineering value). |
| Main L775 | "three floors ... without per-scenario inference": the single-criterion floor uses the reference's own criterion scores (issue 5). FD values 0.933 / 0.800 / 0.097 / 0.614 -> new 0.838 / 0.800 / 0.190 / 0.610. |
| Main L788 (`tab:incremental-contribution`) | FD row 70.3 / 0.614 -> new 66.7 / 0.610; every delta changes. |
| Main L808 | DM 0.641 / 76.9% -> new 0.607 / 71.3%; the "0.24-0.28" gain and the Wilcoxon / Cliff's delta ranges need the rerun. |
| Main L810 | Single-criterion percentages (Comfort 85.7 HVAC / 92.3 Appliance, Energy 10.0 / 75.0) change (new, first occurrence: 80.0 / 87.7, 10.0 / 75.0; with the reference tie rule: 81.4 / 87.7, 17.1 / 75.0); "8.8 pp" on the 285-scenario set must be recomputed. Copy-only tau 0.001 was over 60 of 90 scenarios and carries the Shower label bug (issues 1-3). |
| Main L813-829 (`tab:single-criterion-recovery`) | Every cell; table note "We break ties by first occurrence" (issue 4). |
| Main L1071 | FD Appliance 0.097 -> new 0.190; "Practicality alone recovers the reference winner in 90.8%" -> new 86.2%; FD HVAC 0.933 -> 0.838; the two-models-each claim for HVAC/Shower and the "R-15, SEER-13 ... typical" rationale need re-checking after the rerun. |
| Main L1112 | "fixed default ... outranks A_E on overall tau for all four models": still likely (FD 0.610), re-check after the rerun. |
| S L622-629 | "kWh/cycle is a per-appliance-type constant ... falls back to 1.00": false now (issue 8). |
| S L641-643 (`tab:fixed_default_constants`) | Washer / dryer / dishwasher rows obsolete; add the appliance-type row. |
| S L966-973 | Copy-only 0.001 / 0.101 and "Evaluated on the full 90-scenario RAG dataset" (issue 3). |
| S L1299, L1305, L1313-1322, L1328 | "a single dataset-median constant": say retrieval set; DM row 0.641 / 0.769 / 0.122 -> new 0.607 / 0.713 / 0.135. |
| S L1332 | DM significance statistics: regenerate after the rerun. |

## Q7. Anything a reviewer could ask for that would need API calls

Nothing on the baseline side. All of these are offline once the rerun lands:
- Oracle-parameter ceiling: the reference itself (tau = 1); not an arm, by design.
- Per-parameter oracle swaps (true value for one hidden parameter, extracted or median for the
  rest): computable from the stored `extracted_*` columns (A_H writes all ten, `LLM-Parameterized_Reference_Scoring.py`
  L133-151) and the master rows; `run_appl_decomp.py` shows the pattern.
- "Is A_H's Appliance advantage just reading the clock time from the question?": answered offline
  (FD with the true time: tau 0.908).
- Single-criterion floors, FD, DM, NN, copy-only: all offline.

The only reviewer requests that would need calls are architecture variants the author has already
ruled out (LLMs given the value functions) or new arms (e.g. A_H with the time removed from the
question); none is a baseline.

## Q8. Bugs

Issues 1, 2, 3, 4 and 10 above. Also checked and found clean: FD and NN scenarios pair with the
correct GT row in the official matcher (195/195 each); the ablation harness reference equals the
regenerated GT workbooks (195/195 full rankings); no sentinel reaches an average; the FD
`scenario_id` offsets line up with Test order because the Test sheet is sorted by type (HVAC 0-69,
Appliance 70-134, Shower 135-194), and evaluation matches on content anyway.

## Scenario-data fixes logged

38 rows appended to `paper/pass6/verify/SCENARIO_FIXES.md`: 32 Appliance question grammar fixes
(16 comma-splices "It's X, when should I ..." and 16 missing commas closing "about 2 and" style
appositives; all change the Appliance embedding text, so the RAG index must be rebuilt after them),
2 HVAC "for the single-family?" -> "single-family home?" (mode matcher unaffected), 2 Appliance
`baseline_time` short spellings (`6pm`, `8am` -> `6:00 PM`, `8:00 AM`), 2 HVAC `alternative_3`
integer cells in rows 103-104 that every other row stores as text.

## Git

Read-only only: `git log -S ... -- run_rag_ablation_experiments.py` and `git log -1 -- rag_ablation_results.xlsx`
(to date the tau code against the stored results). No state-changing git command was run.
