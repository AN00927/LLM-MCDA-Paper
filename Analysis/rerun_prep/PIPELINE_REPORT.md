# P2 report: per-run A_H basis and the two no-LLM baselines

Date: 2026-09-25; follow-ups 2026-09-26 in section 9, which supersedes the numbers below where
they differ. Scope: `paper/pass5/RERUN_PREP_PLAN.md`, phase P2. No API call was made, and
nothing under `Ground Truth/`, `Scenario Files/`, `chroma_rag_db/`, `Output Files*`, the existing
`Analysis/*` outputs, the paper, the supplement, the bib, `README.md` or `CLAUDE.md` was written. The
only git commands run were read-only (`git status --short`, `git diff --stat -- model_config.py`,
`git diff --quiet -- <file>`).

## 1. Result

- **Gate: passed.** After the changes, the per-run `extracted` arm of the hybrid ablation reproduces
  every per-run A_H number the paper reports, exactly at the precision the paper prints: all 36
  per-run A_H rows of `paper/pass5/NUMBERS_OF_RECORD.csv` (tau, Top-1, MAE, success rate, inclusive
  tau and Top-1, per-type tau, for all four models) and all 68 model x type checks against
  `paper/per_run_metrics/`. The largest full-precision gap is 4.5e-5. It comes from
  `calculate_per_run_metrics.py`, which rounds each run's metric to four decimals before the runs
  are averaged; the ablation harness does not round. The Set A reference itself did not move (48/48
  identical before and after), and every `numbers_master.csv` row outside `GPTOSS_recovery` is
  byte-identical (341 rows). After the 2026-09-26 tie-rounding follow-up, five Gemini tau cells in
  the harness differ from the paper for one explained reason: the stored Gemini A_H ranks broke an
  exact MAVT tie by floating-point noise in one HVAC scenario (section 9.1). Everything else still
  matches exactly.
- **Per-run basis everywhere.** The five-run aggregate workbook
  (`LLM-Parameterized_Reference_Scoring_results.xlsx`) is no longer read by any of the five scripts.
  Nothing else needs it: the only other readers are the D2 reproduction scripts in `Analysis/pass5/`,
  which read it on purpose to prove the Set B mechanism.
- **Dataset median (DM)** now takes its medians and modes over the 90 retrieval scenarios only. The
  overall tau is unchanged at 0.641 by coincidence; Top-1 falls from 76.9% to 75.9% and MAE rises
  from 0.122 to 0.133.
- **Fixed default (FD)** no longer reads the question; every Appliance scenario is a dryer at 2.10
  kWh/cycle. Appliance tau rises from 0.097 to 0.138, and overall tau from 0.614 to 0.627.
- The extraction table (`tab:extraction_accuracy`) moves to the per-run basis and reproduces the
  D3 per-run values exactly in every cell but one: under the tie-rounding rule, DeepSeek's R-value
  P(Top-1 change | error) is 0.042, not D3's 0.036 (section 9.1).

## 2. Code changes

Line numbers are for the files after the change. Pre-change copies are in
`Analysis/rerun_prep/pipeline/orig/` for diffing.

### `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`

- **L1-32, L95-97 (docstring).** `extracted` is now described as the per-run arm and `default_params`
  as the retrieval-set median; states the aggregation rule (per-run mean, then mean over runs).
- **L126 (import).** `_is_complete_run_file`.
- **L185-218 (`RAG_SCENARIO_FILES`, `ARM_SPECS`).** New map of the three RAG sheets. The `extracted`
  arm's label is now "LLM-extracted hidden parameters (per run, shipped runs)". The separate
  `extracted_per_run` arm is gone, because it would have been an exact duplicate of `extracted`.
  `default_params` is labelled "Retrieval-set median hidden parameters (no inference)".
- **L595-689 (`RAG_CHECK_KEYS`, `_canon`, `_canonical_clock`, `retrieval_set_rows`,
  `compute_defaults`).** The DM statistics are now computed over the RAG rows of the master sheets.
  `retrieval_set_rows` takes the master rows that no Test scenario matches, which is the rebuild's own
  partition rule (`build_consolidated_scenario_workbooks.py` L11). It checks them against the RAG sheet
  (same scenario count, same location / household size / budget / housing type) and raises on any
  mismatch. The RAG sheets can't be used directly because they omit `occupancy_context` and
  `baseline_time`. Baseline-time spellings (`6pm`, `6:00 PM`) are normalised before the mode is
  taken. A tied mode resolves to the first value in sorted order, as before. Every hidden parameter,
  categorical ones included, stays one constant; nothing is read from the question.
- **L837-900 (`_sentinel_failed_sids`, `run`).** The aggregate workbook is no longer read. The
  `extracted` arm has one entry per shipped per-run file. A scenario-run counts as failed if
  `extraction_failed` is set or any stored criterion score is the 1928 sentinel, the same rule as
  the main pipeline's `filter_failed_scenarios`, and it is dropped from that run only. A model with no
  per-run files is skipped with a message.
- **L902-913.** The arm list builds `extracted` / `order_control` / `order_reversed` the same way,
  one entry per run.
- **L941-948 (`_shipped_run_paths`).** Skips incomplete run files with the same
  `_is_complete_run_file` rule as `calculate_per_run_metrics.py`, so the two harnesses always see the
  same runs.
- **L1277-1367 (`_run_means`, `summarize`, `like_for_like`).** `summarize` now uses the paper's
  estimator: each run's mean over the scenarios it scored, then the mean over runs (it used to pool
  scenario-runs). It adds a per-run tau SD and, with `by_type=True`, a per-decision-type breakdown.
  `like_for_like` computes the extraction gain over the DM on the same scenarios, run by run.
- **L1419-1455 (`main`).** The workbook gains the sheets `summary_by_type` and `like_for_like`; the
  Markdown summary states the arms and the basis.

### `Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py`

- **Docstring (L1-72).** States the pairing basis and the new CLI.
- **L95 and L111-128 (`RUN_MEAN_DECIMALS`, `per_scenario_run_means`).** Before testing, each
  scenario's metric is averaged over the runs in which it succeeded; a scenario that failed in every
  run drops out (GPT-OSS: n = 194). The test pairs that run mean with the scenario's DM value. This is
  the Methods protocol (main L482: "For each scenario, we average the metric over the runs in which
  that scenario succeeded") and the basis D2 recommended. The run means are rounded to 10 decimals,
  for the reason in section 4.4.
- **L131-161 (`parse_args`, `main`).** New `--summary` and `--output-dir` arguments. The defaults are
  the old paths.

### `Miscellaneous Scripts/core-automation/run_baseline_models.py`

- **L61, L68.** New explicit constants `HVAC_DEFAULT_OCCUPANCY_CONTEXT = "occupied_all_day"` and
  `APPLIANCE_DEFAULT_BASELINE_TIME = "7pm"`.
- **L133-156 (`retrieval_set_appliance_mode`, docstring).** The FD appliance type is the
  retrieval-set mode, taken from the same `compute_defaults()` as the DM and cached.
- **L170, L178-201.** The question-text keyword parser is removed. `appliance` is the retrieval-set
  mode, and `kwh_per_cycle` is the fixed default for that type (2.10 for `dryer`).
- **L170, L201, L208-210.** Occupancy, baseline time, GPM, tank size and heater setpoint used to be
  read as `row.get(<column>, <constant>)`. The Test sheet has none of these columns, so the constant
  always applied and no number changes. They are now plain constants, so a column added to the Test
  sheet later can't leak a hidden parameter into the baseline.
- **L488-489, L500.** New `--output-dir` argument; the default is still `Output Files/Baselines`.

### `paper_pipeline/generate_paper_results_numbers.py`

- **L2-11.** New `--output` argument; the default is still `paper/numbers_master.csv`.
- **L301-321 (`GPTOSS_recovery` rows).** The block used to sweep in the three per-type rows of each
  GPT-OSS run and label them "Overall", so its `run_k` rows were mixed and `pooled_5run` held the
  mean of 20 mixed rows (tau 0.8985, not 0.8974). It now filters to `decision_type == "Overall"`.
  `pooled_5run` is the unrecovered per-run mean (0.8974 / 91.73%, the main-text value).
- **L345-409 (`_recovered_per_run`, `recovered_5run` rows).** The recovery that main L909 describes
  is now actually computed; before, no code did it. In each run, a failed scenario takes its rows
  from the first other run in which it succeeded, and the run is then scored by the same functions as
  `calculate_per_run_metrics.py`. Without backfill this reproduces the per-run CSVs exactly. Result:
  tau 0.9045, Top-1 91.96%, MAE 0.0520, 194 scenarios per run, 22.4 recovered per run. This matches
  D2's backfill (0.9045 / 91.96%).

### `Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py`

- **L16-18 (imports).** `MODEL_KEY`, `is_sentinel`, `apply_mavt_ranking`, `SENTINEL_VALUE`,
  `_is_complete_run_file`; the no-longer-used `CRITERION_WEIGHTS` and `TIE_BREAK_PRIORITY` are gone.
- **L142-159 (`_rank_alternatives`).** Now calls `sentinel_utils.apply_mavt_ranking`, the one
  implementation that also produces the reference rankings. The private re-implementation summed
  the weighted scores in a different order, so on an exact MAVT tie the two could disagree about
  which alternative floating-point noise put first (section 4.4). That was the only difference from
  D3: DeepSeek's R-value P(Top-1 change | error) was 0.0425 against D3's 0.0364, from scenario 58
  (runs 2 and 3), where alternatives 77 and 81 tie at 0.5175.
- **L248-266 (`_load_..._results`).** Flags a failed scenario-run (`extraction_failed`, or a sentinel
  in any stored score) before the one-row-per-scenario reduction.
- **L467-721 (`_discover_run_files`, `_check_per_run_file`, `_evaluate_one_run`,
  `_summaries_for_run`, `_mean_over_runs`, `evaluate`).** Evaluates each per-run file on its own,
  drops failed scenario-runs, and averages every MAE, match accuracy and P(Top-1 change | error) over
  runs; counts are summed over runs. The unconditional change rate now divides by the scenarios the
  run scored for that decision type (before, the Test count). The aggregate workbook is refused with
  an explanation. Counterfactual rows now carry `scenario_id` and `run`. The master sheet is loaded
  once per type instead of once per row.
- **L724-758 (`parse_args`).** `--model` (default `MODEL_KEY`) picks the output folder; `--results`
  optionally names explicit per-run files; `--output` defaults to the model folder.

### New files (all under `Analysis/rerun_prep/`)

- `pipeline/pipeline_gate.py`: runs the live code for `before` / `after` and writes `before.csv`,
  `after.csv` (long format) and, with `diff`, `diff.csv`.
- `pipeline/gate_checks.py`: gate verdicts in `gate.csv`, baseline table in
  `baseline_old_vs_new.csv`.
- `pipeline/orig/`: pre-change copies of the five scripts.
- `pipeline/work_before/`, `pipeline/work_after/`: regenerated outputs (hybrid per-scenario frame
  and workbook, significance workbooks, FD predictions, `numbers_master.csv`, extraction reports).
- `pipeline/cli_outputs/`: each edited script run end-to-end through its own CLI with redirected
  outputs. `_run_with_gemini35.py` is the wrapper that does this (section 4.1).
- `pipeline/work_sigcheck_oldDM/`: the new significance code run on the old DM, used to separate the
  two changes (section 3.3).
- `PROVENANCE_BASELINES.md`: every constant and rule of the DM and the four baselines, with source
  and status.

## 3. Gate detail

### 3.1 Main-text per-run A_H numbers (after the change)

`extracted` arm of the hybrid ablation, per-run mean then mean over runs:

| Model | tau | Top-1 | MAE | Scored / 975 | Inclusive tau / Top-1 | HVAC / Appliance / Shower tau |
|---|---|---|---|---|---|---|
| DeepSeek | 0.897 | 90.8 | 0.045 | 974 (99.9%) | 0.896 / 90.7 | 0.920 / 0.975 / 0.787 |
| Gemini | 0.923 | 93.1 | 0.048 | 975 (100%) | 0.923 / 93.1 | 0.977 / 0.959 / 0.822 |
| GPT-OSS | 0.897 | 91.7 | 0.052 | 858 (88.0%) | 0.790 / 84.7 | 0.943 / 0.967 / 0.787 |
| Qwen | 0.880 | 89.7 | 0.072 | 973 (99.8%) | 0.878 / 89.6 | 0.881 / 0.906 / 0.851 |

Every cell equals the paper's printed value.

### 3.2 GPT-OSS recovery

Unrecovered: tau 0.897, Top-1 91.7% (main-text value). Recovered (first other successful run):
tau 0.904, Top-1 92.0%. That confirms D2's proposed L909 correction (A1.8).

### 3.3 The significance code, separated from the DM change

On the old DM, the new significance code reproduces D2's like-for-like tests up to the float-tie
effect described in 4.4. Top-1 matches exactly. With the run means rounded (the new code), tau
Cliff's delta is -0.179 / -0.240 / -0.189 / -0.168 (DeepSeek / Gemini / GPT-OSS / Qwen); D2 printed
-0.179 / -0.240 / -0.187 / -0.166 from unrounded run means. MAE delta is 0.450 / 0.444 / 0.383 /
0.298. The ranges D2 proposed (tau -0.17 to -0.24, MAE 0.30 to 0.45) still hold at two decimals.

## 4. Things I found that are not fixed here

1. **`model_config.py` now points `gemini` at `Output Files Gemini 3.8 Flash` and `deepseek` at
   `Output Files DeepSeek V4.1 Flash`** (P3's changes). The first folder is empty and the second
   doesn't exist. Any script run as-is on the shipped data skips those models or fails on them;
   `run_hybrid_ablation_experiments.py` printed no Gemini rows until I redirected it. All my checks
   redirect each model whose configured folder has no A_H run files to its shipped folder, in-process
   only (`pipeline_gate.py`, `tie_rounding_check.py`, `cli_outputs/_run_with_gemini35.py`). Until
   the rerun lands, anyone regenerating old-data outputs has to do the same. The same price edits
   change the `Table8_cost_per_run` rows for DeepSeek and GPT-OSS (old tokens priced at the new
   labels); that is P3's change, not P2's.
2. **The shipped outputs are still the old ones.** `Analysis/Hybrid_Ablation/*.xlsx` (with the Set B
   arm), `Output Files/Baselines/baseline_fixeddefault.xlsx` and `baseline_metrics.csv` (old FD),
   `paper/numbers_master.csv` and each model's `*_parameter_evaluation.md` were not overwritten. They
   refresh when P5 runs `run_baseline_models.py`, then `evaluate_baseline_metrics.py`, then the
   ablation, then the significance script, then the pipeline.
3. **The D1 and D2 reproduction scripts read `arm == "extracted_per_run"`**
   (`Analysis/pass5/d1_bootstrap_ci.py` L30, `d1_lookup_baseline.py` L500,
   `d2_reproduce_ah_numbers.py`, `d2_build_numbers_of_record.py`). A regenerated workbook has only
   `extracted`, which is the same data. P3's new `paper_pipeline/build_numbers_of_record.py` reads
   only `per_run_metrics_all.csv` and marks the ablation rows "not_regenerated", so it is not
   affected. Anything that later regenerates those rows should read `arm == "extracted"`.
4. **(Fixed 2026-09-26, section 9.1.)** **`sentinel_utils.apply_mavt_ranking` let floating-point noise break exact MAVT ties.** It
   compares unrounded weighted sums, so `TIE_BREAK_PRIORITY` only applies when two sums are equal to
   the last bit. Example: HVAC Test scenario 58 at R = 5 gives 77 and 81 an exact MAVT of 0.5175
   (weights 0.30 / 0.35 / 0.20 / 0.15). The function computes 0.5175000000000001 for 77 and 0.5175
   for 81, so 77 ranks first. The stated rule (environmental first) would pick 81. The same function
   builds the reference rankings, so the reference itself can depend on summation order. Fixing it
   (round the sum to about 10 decimals before sorting) belongs to whoever owns `sentinel_utils.py`
   and would need a reference and results rerun. I only made epe use the same function, so it stays
   consistent with the reference. The same effect in the Wilcoxon and Cliff's delta inputs is handled
   by rounding the run means (L95, L111-128 of the significance script). There, a simple xlsx
   round trip moved GPT-OSS's tau delta from -0.187 to -0.190.
5. **(Fixed 2026-09-26, section 9.2.)** **The nearest-neighbour baseline** (`run_baseline_models.py` L346-388; not in P2 scope):
   - its question keyword parser (L365-366) has no effect, because `format_embedding_text` ignores
     the appliance field; it also mislabels dishwashers ("washer" is in "dishwasher");
   - its Shower query hard-codes the flow-rate label `standard` (L369) instead of using the Test
     row's label, so every Shower query embeds "standard showerhead".

   The second point changes which RAG scenarios it retrieves. Not fixed.
6. **Order-arm summaries moved slightly** because `summarize` now averages run means instead of
   pooling scenario-runs. Only GPT-OSS changes, the one model with failures in those arms: control
   tau 0.8988 -> 0.8985, reversed 0.8977 -> 0.8977. The permutation test is untouched, and the paper
   quotes neither value.
7. **(Fixed 2026-09-26, section 9.3.)** **`generate_paper_results_numbers.py` wrote pooled-across-model rows**
   (`Table5_pooled_overall`, `Table6_per_criterion_mae`, `Table7_per_decision_type_pooled`), which
   conflicted with the never-pool rule. The `IncrementalContribution` rows
   still use per-type means for the LLM rows (the known "best label" issue); unchanged.
8. **Dead FD constants.** 2.54 persons, 51.8 F, $430, the square-footage map and the
   housing-type defaults are defined in `run_baseline_models.py` but never read (details in
   `PROVENANCE_BASELINES.md`).

## 5. Dataset-median constants, old -> new

The old values come from all master rows (105 / 100 / 80, test scenarios included). The new values
come from the 35 / 35 / 20 retrieval rows only.

| Type | Parameter | Old | New |
|---|---|---|---|
| HVAC | R-value | 16.0 | 16.0 |
| HVAC | SEER | 13.0 | 13.0 |
| HVAC | HVAC age (yr) | 18.0 | **16.0** |
| HVAC | Occupancy | occupied_all_day (33/105) | **standard** (14/35); the calculator maps it to occupied_all_day, so it behaves the same |
| Appliance | kWh/cycle | 1.15 | **1.2** |
| Appliance | Appliance type | dryer (37/100) | dryer (13/35) |
| Appliance | Baseline time | 2:00 PM (11/100) | **9:00 AM** (6/35) |
| Shower | GPM | 2.5 | **2.25** |
| Shower | Tank size (gal) | 50.0 | **45.0** |
| Shower | Heater setpoint (F) | 120.0 | 120.0 |

## 6. Baselines, old -> new (current data)

Both conditions are model-independent over all 195 scenarios (`baseline_old_vs_new.csv`).

| Baseline | Type | tau old -> new | Top-1 old -> new | MAE old -> new |
|---|---|---|---|---|
| Dataset median | Overall | 0.641 -> 0.641 | 76.9 -> **75.9** | 0.122 -> **0.133** |
| Dataset median | HVAC | 0.933 -> 0.933 | 95.7 -> 95.7 | 0.070 -> 0.070 |
| Dataset median | Appliance | 0.179 -> **0.190** | 49.2 -> 49.2 | 0.237 -> **0.261** |
| Dataset median | Shower | 0.800 -> **0.789** | 85.0 -> **81.7** | 0.059 -> **0.067** |
| Fixed default | Overall (pooled) | 0.614 -> **0.627** | 70.3 -> **70.8** | 0.097 -> **0.129** |
| Fixed default | HVAC | 0.933 -> 0.933 | 95.7 -> 95.7 | 0.071 -> 0.071 |
| Fixed default | Appliance | 0.097 -> **0.138** | 29.2 -> **30.8** | 0.161 -> **0.257** |
| Fixed default | Shower | 0.800 -> 0.800 | 85.0 -> 85.0 | 0.059 -> 0.059 |

The DM overall tau is unchanged only because one Appliance scenario gains 2/3 and one Shower scenario
loses 2/3 (65 x 0.0103 = 60 x 0.0111). The FD Appliance MAE rises because every appliance is now
scored as a dryer; its ranking gets slightly better.

Per model, same scenarios as each A_H run (tau gain of A_H over the baseline, mean over runs):

| Model | Gain over DM, overall | Appliance | HVAC | Shower | Gain over FD, overall | Appliance |
|---|---|---|---|---|---|---|
| DeepSeek | 0.257 -> 0.257 | 0.796 -> 0.786 | -0.013 -> -0.013 | -0.013 -> -0.002 | 0.284 -> 0.270 | 0.878 -> 0.837 |
| Gemini | 0.282 -> 0.282 | 0.779 -> 0.769 | 0.044 -> 0.044 | 0.022 -> 0.033 | 0.310 -> 0.296 | 0.862 -> 0.821 |
| GPT-OSS | 0.300 -> 0.300 | 0.788 -> 0.777 | 0.023 -> 0.023 | -0.013 -> -0.002 | 0.329 -> 0.313 | 0.870 -> 0.829 |
| Qwen | 0.239 -> 0.239 | 0.726 -> 0.716 | -0.054 -> -0.054 | 0.051 -> 0.062 | 0.266 -> 0.253 | 0.808 -> 0.767 |

DM on the scenarios GPT-OSS's runs scored: tau 0.597 -> 0.597, Top-1 74.1 -> 73.0.

Provenance significance (per-run basis, run means paired with the new DM, 12 tests Holm-corrected;
all 12 significant):

| Model | tau: p_Holm, delta | Top-1: p_Holm, delta | MAE: p_Holm, delta | n |
|---|---|---|---|---|
| DeepSeek | 6.5e-8, -0.207 small | 8.0e-6, -0.124 negligible | 2.8e-17, 0.483 large | 195 |
| Gemini | 1.5e-8, -0.266 small | 1.1e-5, -0.170 small | 1.1e-21, 0.497 large | 195 |
| GPT-OSS | 4.0e-9, -0.218 small | 5.3e-7, -0.132 negligible | 1.6e-17, 0.406 medium | 194 |
| Qwen | 4.0e-8, -0.195 small | 7.8e-6, -0.106 negligible | 2.5e-13, 0.337 medium | 195 |

## 7. What the paper states that these changes move

Line numbers are for `paper/paper_draft_v2.tex` (main) and `paper/supplementary.tex` (S) as they
stand now. None was edited.

**Fixed default** (the keyword parser is gone):

- **Main L775:** "collapses on Appliance ($\tau = 0.097$), for an overall $\tau$ of 0.614" becomes
  0.138 and 0.627. HVAC 0.933 and Shower 0.800 are unchanged.
- **Main L788-797, `tab:incremental-contribution`.** The FD row becomes Top-1 70.8 and tau 0.627, and
  every delta changes. The new deltas below are computed from the printed row values against the
  exact FD (70.769%, 0.62735); where a printed row value is rounded, the delta can differ by 0.1 pp.
  - A_D Gemini: -34.6 / -0.451
  - A_D Qwen: -40.8 / -0.617
  - A_E Gemini: -22.1 / -0.317
  - A_E Qwen: -24.2 / -0.419
  - A_H Gemini: +22.4 / +0.296
  - A_H Qwen: +19.0 / +0.253 (+18.9 if computed from the printed 89.7 and 70.8)

  NUMBERS_OF_RECORD rows `AH_table_best_dtau_vs_FD` (+0.310) and `AH_table_worst_dtau_vs_FD`
  (+0.266) become +0.296 and +0.253.
- **Main L1071:** "collapses on Appliance ($\tau = 0.097$)" becomes 0.138. The per-type statements
  still hold. A_H clears the FD on Appliance for every model, and on HVAC / Shower for the same two
  models each, since the FD's HVAC and Shower values didn't change. A_E still beats the FD on
  Appliance for every model except GPT-OSS: A_E Appliance tau is 0.417 / 0.344 / -0.048 / 0.231
  against 0.138.
- **Main L1112:** "outranks A_E on overall tau for all four models" still holds (0.627 against at
  most 0.310).
- **S L622-629 and `tab:fixed_default_constants` (S L633-652).** The text calls kWh/cycle "a
  per-appliance-type constant" and lists washer 0.55 / dryer 2.10 / dishwasher 1.00. The FD now
  assigns the retrieval-set mode (dryer, 2.10) to every Appliance scenario, so the washer and
  dishwasher rows no longer apply, and the table needs an "Appliance type: dryer (retrieval-set
  mode)" row.

**Dataset median** (retrieval-set statistics):

- **Main L749:** "(the dataset median, or the mode for a categorical parameter)". The statistics
  are now over the 90 retrieval scenarios, with the test scenarios excluded; the wording may want
  to say so.
- **Main L808:** "$\tau = 0.641$ and Top-1 of 76.9\%". The tau is unchanged; Top-1 becomes 75.9%.
  The extraction gain on the scenarios each run scored stays 0.24-0.30 (0.239 / 0.257 / 0.282 /
  0.300): on the scenarios each run scored, the Appliance gain falls and the Shower gain rises by
  the same total, as in the all-scenario tau.
- **Main L808, parenthetical, and S L1332** (significance, new DM and per-run basis):
  - tau Cliff's delta: -0.195 to -0.266, p_Holm < 1e-7 for all four models;
  - Top-1: -0.106 to -0.170, p_Holm <= 1.1e-5; small for Gemini (-0.170), negligible for DeepSeek
    (-0.124), GPT-OSS (-0.132) and Qwen (-0.106);
  - MAE: 0.337 to 0.497, p_Holm <= 2.5e-13; large for DeepSeek (0.483) and Gemini (0.497), medium
    for GPT-OSS (0.406) and Qwen (0.337). The published "medium to large" wording fits; D2's
    proposed "small to medium" no longer does;
  - "$p_{\text{Holm}} < 10^{-3}$ throughout" stays true.

  D2's proposed replacements (A1.5, A1.7), which were computed with the old DM, no longer match.
  Take these numbers from `pipeline/work_after/hybrid_ablation_significance.xlsx`, or from the rerun.
- **S L1313-1322, `tab:param_provenance`, dataset-median rows:** 0.641 / 0.769 / 0.122 becomes
  0.641 / 0.759 / 0.133. S L1328 quotes the same triple.
- **Proposal A1.3** ("the dataset-median condition reaches $\tau = 0.597$" on GPT-OSS's scenarios):
  unchanged at 0.597.
- **By-type gains quoted in the proposal** (A1.6 "almost all of it on Appliance", D2 section 6.3):
  Appliance DM tau is 0.190 (was 0.179), and the Appliance gain is 0.716-0.786 (was 0.726-0.796).
  HVAC gains are unchanged. Shower gains shift up by 0.011 (DM Shower 0.789).

**Per-run extraction table** (`tab:extraction_accuracy`, main L931-L937, L945). With the aggregate
default gone, `evaluate_parameter_extraction.py` now produces the per-run values in proposal A3.5
"new" exactly (R-value MAE 4.411 / 4.463 / 3.216 / 1.806; GPM P 0.271 / 0.256 / 0.249 / 0.233; and so
on), plus the A3.4 occupancy accuracies 73.8 / 78.7 / 80.0 / 82.2 and occupancy P 0.017 / 0.054 /
0.081 / 0.072. Also on this basis, Qwen's baseline-time match rate is 99.7%, not 100% (one miss in
325), which bears on the "recovered exactly" wording that A2.10 already flags.

**GPT-OSS recovery, main L909:** "the reported figures do not change ($\tau$ 0.897, Top-1 91.7\%)"
becomes tau 0.904 and Top-1 92.0% (`recovered_5run`), as D2 proposed.

## 8. Reproduce

```
python Analysis/rerun_prep/pipeline/pipeline_gate.py after   # 'before' needs the orig/ scripts in place
python Analysis/rerun_prep/pipeline/pipeline_gate.py diff
python Analysis/rerun_prep/pipeline/gate_checks.py
```

Each step runs offline in under a minute. For a regenerated ablation workbook on the current data
(Gemini redirected to the 3.5 folder):

```
python Analysis/rerun_prep/pipeline/cli_outputs/_run_with_gemini35.py "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py" --output-dir <dir> --output <dir>/hybrid_ablation_results.md
python "Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py" --summary <dir>/hybrid_ablation_summary.xlsx --output-dir <dir>
```

## 9. Follow-ups of 2026-09-26

Three items from section 4, done at the coordinator's request. Same rules as before: no API call,
no write to the paper, supplement, `Ground Truth/`, `Scenario Files/`, `chroma_rag_db/`,
`Output Files*`, `Architectures/*`, the calculators or `sync_rag_ground_truth_scores.py`.
`sentinel_utils.py` and `evaluate_architecture_metrics.py` were outside the original P2 file list;
the coordinator authorised both for this item.

### 9.1 Floating-point ties in the MAVT ranking

**Code:**

- `sentinel_utils.py` L17-23: new constant `MAVT_ROUND_DECIMALS = 10`, with the reason in a comment.
- `sentinel_utils.py` L376-377: `apply_mavt_ranking` rounds each weighted sum to 10 decimals
  before sorting, so an exact tie always reaches `TIE_BREAK_PRIORITY`. The returned
  `weighted_scores` are the rounded values. Scores and weights are 2 dp, so an exact sum never
  needs more than 4 decimals; the rounding only strips noise.
- `Miscellaneous Scripts/core-automation/evaluate_architecture_metrics.py` L47, L116-121:
  `_rank_with_deterministic_tiebreak` applies the same rounding. That covers the imputed-metric
  re-ranking (`recompute_arch_ranks`) and `SensitivityAnalysis.py`, which imports this helper for
  its weight-vector re-ranking.
- `Miscellaneous Scripts/core-automation/run_baseline_models.py` L34, L93-98, L391-402: the same
  rounding in the file's own `_rank_with_deterministic_tiebreak` and in
  `_rank_with_weights_and_tiebreak` (random and uniform baselines). The stored `mavt_score` keeps
  its full value there.
- `evaluate_parameter_extraction.py` already ranks through `apply_mavt_ranking` (section 2), so it
  follows automatically.
- `tests/test_sentinel_aggregation_matching.py`: 46 passed.

**Reference rankings** (`pipeline/tie_rounding_check.py`, in memory; `tie_rounding_check.csv`):

| Check | HVAC | Appliance | Shower |
|---|---|---|---|
| Scenarios in `Ground Truth/ground_truth_*.xlsx` | 105 | 100 | 80 |
| Exact MAVT ties among them | 1 | 0 | 0 |
| Stored ranking changed by the rounded rule | **0** | **0** | **0** |
| Re-scored with the shipped calculators from true parameters: ranking changed | **0** | **0** | **0** |

No reference ranking changes, in the test or the RAG scenarios. The one exact tie (HVAC) already
falls the way `TIE_BREAK_PRIORITY` says. HVAC Test scenario 58 at its true parameters has no tie
and keeps its ranking (77, 81, 73). The case that exposed the problem was the R-value = 5
counterfactual on that scenario; there the rule now ranks 81 first (old: 77).

**The architectures break ties with their own weighted sums.** `Architectures/Direct_LLM_Scoring.py`
L828, `Example-Guided_LLM_Scoring.py` L686 and L1105, and `LLM-Parameterized_Reference_Scoring.py`
L747 and L1323 sort on an unrounded sum. I couldn't edit them. Stored scenario-runs whose ranking
differs under the rounded rule:

| Architecture | DeepSeek | Gemini | GPT-OSS | Qwen |
|---|---|---|---|---|
| A_H | 0 / 974 | **5 / 975** | 0 / 858 | 0 / 973 |
| A_E | 5 / 975 | 12 / 965 | 4 / 975 | 0 / 975 |
| A_D | 3 / 968 | 4 / 975 | 3 / 975 | 2 / 973 |

The main-text metrics use these stored ranks. Before the rerun, the three files need the same
rounding. Otherwise the new runs will break exact ties by noise while the reference breaks them by
the rule, which is the inconsistency this item removes.

**The five Gemini A_H cases are all HVAC Test scenario 5, in every run.** Alternatives 74 and 80
tie exactly at 0.7775. The architecture's stored order is 77, 74, 80, which matches the reference
(77, 74, 80) by noise. The rule puts 80 before 74 (environmental 0.78 > 0.74). So ranked by the
stated rule, the shipped Gemini A_H runs give:

- tau 0.920 instead of 0.923 (HVAC 0.968 instead of 0.977);
- Top-1 unchanged at 93.1%;
- the scenario's tau drops from 1 to 1/3: -(2/3)/70 on HVAC, -(2/3)/195 overall.

Because the hybrid harness ranks with `apply_mavt_ranking`, the gate now shows exactly these five
cells as differences (`gate.csv`, G1 and G2, annotated "explained"): Gemini overall tau, inclusive
tau, HVAC tau. Every other cell matches as before. The paper's Gemini numbers come from the stored
ranks and don't change unless the architecture is fixed and rerun; after the rerun, they'll come
from new data anyway.

Knock-on values in the harness, rule-based ranking (all Gemini unless stated):

- extraction gain over the DM, same scenarios: 0.282 -> 0.279 overall, HVAC 0.044 -> 0.034;
- gain over the FD: 0.296 -> 0.293;
- provenance test, tau: Cliff's delta -0.266 -> -0.262, p_Holm 2.2e-8. Still small and significant;
  the range across models is -0.195 to -0.262;
- order arms: control 0.929 -> 0.926, reversed 0.926 -> 0.925;
- extraction table, DeepSeek R-value P(Top-1 change | error): 0.036 -> 0.042. The R = 5
  counterfactual on HVAC Test scenario 58 (runs 2 and 3) now counts as a flip. This cell no longer
  matches D3, which used the old tie-breaking; A3.5's "new" value 0.036 would become 0.042.

### 9.2 Nearest-neighbour baseline

**Code:** `run_baseline_models.py` L355-373. The hand-built query dict is gone, along with its
question keyword parser and the constants `gpm` 2.5, `flow_rate` "standard", `tank_size` 50,
`water_heater_temp` 120 and `kwh_per_cycle` 0. The query is now the Test row's own fields passed
to `sentinel_utils.format_embedding_text` (inside `retrieve_similar`), which is what A_E does
(`Architectures/Example-Guided_LLM_Scoring.py` L317-326). For Shower, that means the row's
`flow_rate` label. `source_scenario_id` is now `test_<row>`, so it can never equal a RAG id. The
old integer couldn't match either, since the index ids are strings, so nothing changes there.

**Checks** (`pipeline/nn_check.py`): all 195 query strings equal the string A_E builds for the same
Test row. The old code reproduces the shipped `baseline_metrics.csv` exactly.

**Old -> new, current data** (`pipeline/nn_old_vs_new.csv`):

| Type | tau | Top-1 (%) | MAE |
|---|---|---|---|
| HVAC | 0.133 -> 0.133 | 42.9 -> 42.9 | 0.158 -> 0.158 |
| Appliance | 0.292 -> 0.292 | 55.4 -> 55.4 | 0.157 -> 0.157 |
| Shower | 0.733 -> 0.733 | 75.0 -> 75.0 | 0.2122 -> 0.2126 |
| Overall | 0.371 -> 0.371 | 56.9 -> 56.9 | 0.1743 -> 0.1744 |

The predicted scores changed in 34 of the 60 Shower scenarios, the 24 low-flow and 10 high-flow
ones that used to be queried as "standard". No ranking changed, so tau and Top-1 are identical. HVAC
and Appliance predictions are unchanged, because the removed fields never reached their
embeddings. `PROVENANCE_BASELINES.md` is updated (NN rows, rounding rule, line numbers).

### 9.3 Pooled rows

**Check:** I took all 54 pooled values `generate_paper_results_numbers.py` wrote (`Table5_pooled_overall`,
the pooled rows of `Table6_per_criterion_mae`, `Table7_per_decision_type_pooled`) at the
precision the paper uses (3 or 4 dp; Top-1 as a 1-dp percentage) and searched
`paper/paper_draft_v2.tex` and `paper/supplementary.tex` for them, skipping plot coordinates.

**Result: nothing prints them.** There were 32 numeric matches, and each is a coincidence with a
different quantity:

- per-model cells, e.g. S L1528 and L1546 (`tab:overall_by_model`), S L1486 (per-criterion MAE),
  main L861 and L865 (`tab:dispersion`);
- bootstrap intervals, e.g. S L1171-1183;
- weight-vector cells, e.g. S L854-856;
- RAG-ablation cells, e.g. S L959-962;
- a Δ in `tab:incremental-contribution` (main L789);
- prose values, e.g. S L1288, L1337, main L810.

The supplement also states "No value is pooled across models" (S L835, L841, L1372, L1457).

**Code:** `paper_pipeline/generate_paper_results_numbers.py` L44-58. The three pooled blocks are
removed and replaced by a comment saying what was there and why it went. The per-model best/worst
rows of Tables 6 and 7 stay. Output check: the three categories are gone (54 rows), and the
remaining 314 rows are identical.

**Also pooled, not in scope:** the `RobustnessComparison` rows in the same file are means over all
four models' runs (Method A vs imputed). I didn't touch them. They are a robustness diagnostic;
whether anything prints them wasn't checked.

### 9.4 Files

- Changed: `sentinel_utils.py`, `Miscellaneous Scripts/core-automation/evaluate_architecture_metrics.py`,
  `Miscellaneous Scripts/core-automation/run_baseline_models.py`,
  `paper_pipeline/generate_paper_results_numbers.py`.
- New or updated under `Analysis/rerun_prep/`: `pipeline/tie_rounding_check.py` and
  `tie_rounding_check.csv`, `pipeline/nn_check.py`, `nn_before/`, `nn_after/`, `nn_old_vs_new.csv`,
  `pipeline/gate_checks.py`, `pipeline/pipeline_gate.py`, `cli_outputs/_run_with_gemini35.py` (all
  three now redirect every model with an empty configured folder), `gate.csv`, `after.csv`,
  `diff.csv`, `PROVENANCE_BASELINES.md`, this report.
- Git: only the read-only `git diff --quiet -- sentinel_utils.py`, run before the edit to confirm
  the file was unmodified.
