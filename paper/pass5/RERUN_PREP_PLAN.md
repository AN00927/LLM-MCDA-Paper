# Pre-rerun plan: calculators, baselines, pipeline, rerun infrastructure

Written 2026-09-25. This plan implements gate G1(c), a full fresh rerun, in
`PASS5_PROPOSAL.md` → "Execution order". It covers the code and data work that has to be
finished before any API call. The author's decisions of 2026-09-25 are recorded below. Where
they conflict with an older recommendation, they win.

## Decisions

| Topic | Decision |
|---|---|
| Rerun scope | G1(c): every experiment re-collected in one window, with UTC timestamps and raw per-call logs. |
| Gemini | Replace Gemini 3.5 Flash (`google/gemini-3.5-flash:exacto`) with Gemini 3.8 Flash. Keep the model key `gemini`. Output folder `Output Files Gemini 3.8 Flash`. |
| Baselines (G2) | **Pure median, nothing read from the question.** The dataset-median condition sets every hidden parameter, including appliance type, baseline time and occupancy, to its median or mode over the 90 retrieval scenarios only; the 195 test scenarios are excluded. The fixed-default baseline keeps its fixed engineering constants and loses its keyword parser: its appliance type becomes the retrieval-set mode. |
| Appliance tariffs | Tariff-faithful. Add PECO's and FirstEnergy's super off-peak periods, correct the PPL rates, fix the six misassigned cities (and the two ambiguous ones, if a primary source settles them), and give Duquesne a flat rate with no placeholder window. Every utility uses the rates and windows published for **one common period, December 1, 2025 to May 31, 2026**. |
| Weekday rule | Every scenario is a non-holiday weekday, so the weekday TOU and PJM peak windows apply as coded. No code change; the paper states it once. |
| HVAC heating | Keep the electric heat pump, but heat with a sourced heating efficiency: the HSPF paired with each SEER, COP = HSPF / 3.412. The cooling EER stays for cooling only. |
| HVAC constants | Heating comfort optimum 70 → 71 °F (Building America HSP, citing ASHRAE 55). Occupant gain 400 → 230 Btu/h sensible (HSP Table 44). The equipment gain and the 800 Btu/h base stay, unless the HSP gives sourced sensible values in usable units. |
| HVAC mode logic | One consistent rule replaces the three current tests: 75 °F in Comfort, 73 °F in free-float, and outdoor > setpoint in load and Practicality. See P1-HVAC. |
| Data | Stroudsburg (`Scenario Files/HVACScenarios.xlsx`, row index 30): `hvac_age` 95 → 40. Degradation is capped at 40 years, so the reference score doesn't change. |
| Shower | No value changes. Only the code comments are corrected (B76 items). |
| Prompts | Unchanged. The A_D rubric's "dirtiest at peak" is directionally correct (PJM 1.041 against 0.976). |
| Bounds | After the fixes, recompute every 5th–95th percentile bound over the 285 test and RAG scenarios, the same convention as now. The HVAC Environmental bounds stay derived from the HVAC cost percentiles. |

## Phases and order

The phases are ordered so that nothing is done twice and no old number is lost before it has
been checked.

**P1–P3 run in parallel.** Each agent has its own set of files. The calculator agents write
their new calculators to `Analysis/rerun_prep/`, not over the shipped files. That keeps the
shipped calculators and `Ground Truth/*.xlsx` intact until the pipeline agent's regression
gate has run on the old data.

### P1-APP: Appliance calculator (agent)
- Write the new calculator to `Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py`,
  starting from the shipped file.
- Add three-period TOU (peak / off-peak / super off-peak) for PECO (midnight–6 a.m. daily) and for
  the FirstEnergy utilities (11 p.m.–6 a.m. daily). Use the multiplier for each utility.
- Use Dec 2025–May 2026 rates and windows for every utility:
  - PECO TOU generation, excluding transmission, the same basis as the current values;
  - PPL GSC-1 winter rates, with the 4–8 p.m. on-peak window;
  - FirstEnergy PTCs for that period × Supplement No. 20 multipliers;
  - Duquesne's PTC for that period, flat.

  Verify each figure against a primary source (PDF or tariff page) and record the URL and the
  quoted line in the report. If a figure can't be verified, keep the current value and flag it;
  never invent one.
- City-to-utility mapping:
  - Indiana → Penelec; Carlisle → PPL; Reading → Met-Ed; Lebanon → Met-Ed;
    State College → West Penn; Chambersburg → West Penn.
  - Stroudsburg and Quakertown: settle each from a primary source, or leave it and flag it.
- Correct the code comments (Part B B76 items for this file).
- Regression and impact checks:
  - The unmodified copy must reproduce `Ground Truth/ground_truth_appliance.xlsx` exactly.
  - Report winner and full-ranking changes (test out of 65, RAG out of 35), both for each fix and
    for all fixes combined.
  - Report the new 5th–95th percentile cost and emissions bounds, and put them in the new file.
- Put the tests in `Analysis/rerun_prep/tests/`.

### P1-HVAC: HVAC calculator, plus the Shower comments (agent)
- Write the new calculators to `Analysis/rerun_prep/calc_new/HVACGroundTruthCalculator.py` and
  `ShowerGroundTruthCalculator.py`.
- **Heating efficiency.** HSPF paired with SEER from a primary source: the DOE federal minimum
  pairing (SEER 13 / HSPF 7.7, SEER 14 / HSPF 8.2 and so on), ENERGY STAR, or the Building
  America HSP / BEopt defaults. Interpolate between tabulated pairs, then take COP = HSPF / 3.412.
  Cite the source in a comment.
- **Mode logic.** Two rules:
  - The comfort season is set per scenario by one outdoor-temperature threshold. Free-float uses
    the same threshold.
  - The load's heating or cooling direction per alternative comes from the sign of the net heat
    balance (conduction + infiltration + internal gains, plus solar in the cooling season), so a
    setpoint just above the outdoor temperature can't take the heating branch with zero load
    while internal gains are heating the house.

  Practicality follows the same mode as the load. Report how many alternatives change branch.
- **Constants.** Heating optimum 71 °F, and align `WINTER_COMFORT_RANGE` with its comment.
  Occupant gain 230 Btu/h sensible.
- **Comments.** Fix the ACH source comment (ASHRAE 62-1989) and the other B76 items for the HVAC
  and Shower files.
- **Checks.** The same exact-reproduction check as P1-APP. Report per-fix and combined changes
  (test out of 70, RAG out of 35), with the Stroudsburg `hvac_age` fix applied in a scratch copy
  of the scenario data. Compute the new bounds. The Shower bounds should come out unchanged;
  confirm it.

### P2: Baselines and the per-run pipeline (agent)
Files:
- `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`
- `Miscellaneous Scripts/core-automation/run_baseline_models.py`
- `Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py`
- `paper_pipeline/generate_paper_results_numbers.py`
- `Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py`

Steps:
1. **Regression gate first:** record, on the current data and code, every per-run A_H number the
   main text reports, from `paper/pass5/NUMBERS_OF_RECORD.csv`.
2. **Per-run basis everywhere.** Each run is scored separately, failed scenario-runs are dropped,
   and the metrics are averaged over runs. `Analysis/pass5/d2_reproduce_ah_numbers.py` is the
   reference implementation. Gate: the main-text per-run numbers reproduce exactly.
3. **Dataset-median.** `compute_defaults()` takes medians and modes over the 90 RAG scenarios
   only (RAG rows of the master sheets). Every hidden parameter, including the categorical ones,
   stays a constant.
4. **Fixed-default.** Remove the keyword parser. The appliance type becomes the RAG-set mode, and
   the kWh default is the value for that type. All other constants stay.
5. Report the old and new DM and fixed-default numbers per model and decision type, on the old
   data. They are expected to move; the gate is only the main-text A_H numbers.

### P3: Rerun infrastructure, ablation scripts and new analysis scripts (agent)
Files:
- `model_config.py`
- `Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py`
- `Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py`
- `Miscellaneous Scripts/experiments/run_position_bias_control.py`
- the `paper_pipeline/` files that hard-code "Gemini 3.5":
  - `compute_dispersion_diagnostics.py`
  - `duplication_rate_analysis.py`
  - `generate_paper_figures.py`
  - `reconcile_recollection_diagnostics.py`
- new scripts in `paper_pipeline/`

Steps:
1. **Gemini 3.8 Flash in `model_config.py`.**
   - Verify the exact OpenRouter ID, that `:exacto` is served, and support for `temperature` and
     `reasoning` (effort "minimal"). Use only the free, keyless GET endpoints
     `/api/v1/models` and `/api/v1/models/{id}/endpoints`; make no completion call.
   - Record the price in the label.
   - Update the Gemini label and folder strings in the pipeline files.
2. **Logging.** Every experiment script that makes API calls must write, for each run, a
   `collected_utc` and a `*_raw.jsonl` per-call log, as the three architectures already do.
   Check each script, and add the logging where it is missing, reusing the architectures'
   `RAW_LOG`.
3. **B60 tie-break.** The prompt, RAG and position-bias ablations compute each scenario's tau
   with the main benchmark's deterministic tie-break (`TIE_BREAK_PRIORITY` in `model_config.py`),
   not tau_b on tied scores.
4. **New scripts:**
   - tie rates per model × architecture, the table behind S L203;
   - per-run regret (the `Analysis/pass5/d12_*` reference);
   - a numbers-of-record generator that rebuilds `paper/pass5/NUMBERS_OF_RECORD.csv` from outputs.

   Register all three in `paper_pipeline/run_paper_pipeline.py`.

### P4: Install and refresh chain (lead, sequential, after P1–P3)
1. Confirm the P2 regression gate passed on the old data.
2. Archive the current state to `C:\Users\Ahaan\LLM-MCDA-Paper-snapshots\2026-09-25_pre_rerun\`:
   all four `Output Files*` folders, `Analysis/` ablation outputs, `Ground Truth/`,
   `Scenario Files/` and `chroma_rag_db/`.
3. Apply the Stroudsburg data fix in `Scenario Files/HVACScenarios.xlsx`, then run
   `Scenario Files/build_consolidated_scenario_workbooks.py`.
4. Install the new calculators and tests from `Analysis/rerun_prep/`.
5. Run each calculator to regenerate `Ground Truth/*.xlsx`. The regenerated file must match the
   agent's scratch results.
6. Run `sync_rag_ground_truth_scores.py`, then `build_rag_index.py`. Bump `RAG_SCHEMA_VERSION`
   in both files only if the embedding text changed.
7. Update the README reference-range table to the new bounds.
7a. Merge the agents' `Analysis/rerun_prep/PROVENANCE_*.md` files (Appliance, HVAC, Shower,
    baselines) into one repository document, `docs/CALCULATOR_PROVENANCE.md`. It maps every
    constant and function to its source, verbatim quote and status. A later pass removes
    duplicate or redundant sources. Where a new implementation's source differs from the old
    one, the new source is recorded as the source and the old one is kept only as the
    previous source.
8. Clear the live output folders for the new runs; resume-aware runs would otherwise skip
   existing files.

### P5: Rerun (lead, after the author says go)
1. One smoke-test call per model (a few cents), to check the Gemini 3.8 ID, reasoning and
   token use.
2. Collect, in one window:
   - main benchmark, 5 runs × 3 architectures × 4 models;
   - prompt ablation;
   - RAG ablation;
   - A_H ordering arms;
   - position-bias control.
3. Run `paper_pipeline/run_paper_pipeline.py`, then continue with Step 4 of
   `PASS5_PROPOSAL.md` → "Execution order".

**Estimated cost:** about $24, up to $30 with retries, down from $44–60 with Gemini 3.5. Gemini
3.8 Flash is $0.75/$3.75 per million tokens, about 47% of Gemini 3.5 on this token mix. Real
usage is confirmed at the smoke test.

## Rules for every agent
- Never run `git commit`, `push`, `checkout`, `stash` or `reset`.
- Don't edit the paper, the supplement, the bib, `README.md` or `CLAUDE.md`.
- Don't write `Ground Truth/*.xlsx`, `Scenario Files/*` or `chroma_rag_db/`.
- Make no paid API calls.
- `print()` ASCII only.
- The sentinel `1928` never enters an average.
- Never pool metrics across models.
- Keep each file's existing style and comment density.
