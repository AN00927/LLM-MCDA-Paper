# Pass 6 handoff: verify the rerun prep, install it, rerun, then update the paper

Written 2026-09-26 by the session that ran Pass 5 and dispatched the pre-rerun code work. You
are a **fresh agent**. The author asked for a new agent at this point because the session that
built the changes is too close to them to verify them. Your first job is to check that work
independently. Everything after that is in Section 6.

**Authority order.** Where two documents disagree, the one higher in this list wins:
1. this file;
2. `paper/pass5/RERUN_PREP_PLAN.md` (the pre-rerun plan and the author's decisions);
3. `paper/pass6/PASS6_PROPOSAL.md` (a working copy of the Pass 5 proposal; Section 5 of this
   file gives the status of every item in it);
4. everything else.

`paper/pass5/PASS5_PROPOSAL.md` is the frozen original. Don't edit it.

**The paper files are `paper/paper_draft_v2.tex` and `paper/supplementary.tex`**, with
`paper/cas-refs.bib`. `CLAUDE.md` still names `paper_draft_working.tex`, which is stale. The
manuscript is gitignored and has no history, so snapshots are the only backup.

---

## 1. Where things stand (2026-09-26, about 00:30 ET)

- **Nothing in the paper, supplement, bib or README has been edited since the Pass 5
  snapshot** (`C:\Users\Ahaan\LLM-MCDA-Paper-snapshots\2026-09-25_pass5\`).
- **Nothing has been reinstalled or regenerated.** The shipped calculators in
  `Ground Truth Calculators/`, `Ground Truth/*.xlsx`, `Scenario Files/*` and `chroma_rag_db/`
  are still the ones behind the published numbers.
- **The new calculators exist only as copies** in `Analysis/rerun_prep/calc_new/`.
- **Pipeline, baseline and infrastructure code has been edited in place** (Section 3). The
  author has not committed any of it. Never commit.
- **No paid API call has been made.** The rerun hasn't started.

**Four agents did the pre-rerun work.** Their reports are in `Analysis/rerun_prep/`:
`APPLIANCE_REPORT.md`, `HVAC_SHOWER_REPORT.md`, `PIPELINE_REPORT.md` and `INFRA_REPORT.md`,
plus `PROVENANCE_*.md` for each calculator and the baselines.

**All four pre-rerun agents and their follow-ups have finished (2026-09-26, about 01:30 ET).**
What each one did is below. Phase V still verifies all of it.

1. **HVAC agent: finished (revision 2).** Everything below landed; details are in the revised
   `HVAC_SHOWER_REPORT.md`.
   - **Tests and gate:** 121 tests pass (HVAC 18, Shower 2, Appliance 101).
   - **Mode assignment:** all 105 scenarios match their question wording. Heat: 51 scenarios,
     5–62 °F. AC: 54 scenarios, 68–102 °F. See `hvac/out/scenario_modes.csv`.
   - **New HVAC bounds:** cost $0.59/$3.27, Environmental 3.03/17.90 lbs. Shower and Appliance
     bounds are unchanged.
   - **Combined impact:** 13/70 test winners and 17/70 rankings change; RAG 10/35.
   - **Budget penalty:** the continuous version changes no score anywhere.
   - **Question passing:** every calculator call path passes `question`.

   Its gate now compares `mavt_score` within 1e-9, because the pipeline agent's 10-dp rounding
   in `sentinel_utils` adds float noise of about 1e-16. The rounding changes no rank, but it
   changes the 2-dp score in 3 RAG exemplar cells.

   **Two items for Phase V:**
   - **Open author question: solar gain in heat mode.** The calculator keeps solar out of the
     heat-mode balance, as the shipped heating load did. Crediting it would change 8/70 test
     winners (the cost floor would drop to $0.19). The lead's recommendation is to keep it
     out: 20 Btu/h per ft² of glass is a cooling-season peak value with no source, and the
     scenarios have no time of day for HVAC. Ask the author.
   - **A_H key-override risk.** `Architectures/LLM-Parameterized_Reference_Scoring.py` merges
     the model's extracted parameters over the scenario without restricting keys, so an
     extraction that returned `question` or `hvac_mode` would override the scenario's value.
     Propose restricting the merge to the requested extraction keys: a small fix, needed
     before the rerun. Show the author the diff first, because it touches an architecture
     file.

   What the agent was asked to do:
   - The mode rule is redone. The operating mode is the system the question asks about, "heat"
     or "AC". A strict matcher reads it from `scenario['question']`, and an explicit
     `scenario['hvac_mode']` overrides it. A question that matches neither or both returns the
     sentinel.
   - The load comes from the setpoint against the free-float indoor temperature (net heat
     balance) and is capped by the mode: heat mode gives heating or 0, never cooling, and AC
     mode the reverse.
   - Comfort, Practicality and the "Off" free-float follow the mode. No outdoor-temperature
     season threshold remains.
   - Occupant gain 230 → 220 Btu/h (Building America HSP Table 44, single-zone value).
   - Continuous budget penalty in **all three** calculators: above u = 1.5 the exponential
     continues instead of dropping to 0. Bradford (HVAC test id 96) had all three alternatives
     past the old cliff.
   - Then bounds, impact, tests, reports and provenance.
   - The agent was also asked to list every code path that builds an HVAC scenario dict, and
     whether it passes `question`.
2. **Pipeline agent: finished.** Section 9 of `PIPELINE_REPORT.md` has the details.
   - **Tie rounding.** `sentinel_utils.apply_mavt_ranking` rounds each weighted sum to 10
     decimals (`MAVT_ROUND_DECIMALS`). The same rule is in `evaluate_architecture_metrics.py`
     (this is the pipeline agent's change, not the author's) and in `run_baseline_models.py`.
     0 of 285 reference rankings change.
   - **Nearest-neighbour baseline.** The parser is gone, and the query is A_E's
     `format_embedding_text` on the test row. All 195 queries are identical to A_E's. No
     ranking changed.
   - **Pooled rows.** The rows pooled across models were removed; the paper printed none of
     them. The `RobustnessComparison` rows in the same file also average across all four
     models. Nobody has checked whether anything prints them: **check in Phase V**.
   - **Gate note.** Five Gemini A_H HVAC scenario-runs (test scenario 5, an exact tie at
     0.7775) now rank by the tie rule, not by float noise. On the old data, Gemini A_H tau goes
     from 0.923 to 0.920, and those are the only gate cells that differ. The rerun makes this
     moot.

   **Required before the rerun (Phase V):** the architectures still rank on their own
   unrounded sums:
   - `Direct_LLM_Scoring.py` L828;
   - `Example-Guided_LLM_Scoring.py` L686 and L1105;
   - `LLM-Parameterized_Reference_Scoring.py` L747 and L1323.

   Apply the same 10-dp rounding there, preferably by calling the shared
   `sentinel_utils` rule. Otherwise new runs break ties by noise while the reference follows
   the rule. Bundle it with the A_H key-restriction fix, and show the author both diffs.
   Also check how `Table8_cost_per_run` gets its prices: the paper's cost table must use the
   prices charged at collection time (the raw logs or the OpenRouter usage fields), not the
   label strings in `model_config.py`.

   What the agent was asked to do:
   - Round the weighted MAVT sum before ranking in `sentinel_utils.apply_mavt_ranking`, so an
     exact tie always reaches `TIE_BREAK_PRIORITY` and float noise never decides it; report how
     many reference rankings that changes.
   - Remove the nearest-neighbour baseline's question parser and build its query with A_E's
     embedding-text function from the test-sheet fields.
   - Remove the rows `generate_paper_results_numbers.py` pools across models, unless the paper
     prints them.
3. **Infrastructure agent: finished.**
   - It logs calls that fail after every retry: the RAG-ablation fix and the prompt-ablation
     enrichment. Position bias already logged them. Verified with a mocked failure; see
     `Analysis/rerun_prep/infra/test_retry_exhausted_logging.py`.
   - It updated the `gptoss` price label.
   - It set DeepSeek to V4.1 Flash, but the author has since overridden that; see Section 2,
     "Model lineup".
   - Details are in sections 1.4, 1.5 and 3.1 of `INFRA_REPORT.md`.

The author said they are handling the "cost" lineup identifier in `model_config.py`
themselves. Leave it alone.

---

## 2. Everything the author has decided (all approved)

| Topic | Decision |
|---|---|
| Rerun scope | **Full fresh rerun** of every experiment, collected in one window, with a UTC `collected_utc` per run and a `*_raw.jsonl` per-call log. |
| Model lineup | **`model_config.py` belongs to the author, and the file is the source of truth.** The author edited it after the infrastructure agent. As of 2026-09-26 about 01:00 ET it reads: `gptoss` = `openai/gpt-oss-20b:floor` (reasoning low); `qwen` = `qwen/qwen3.5-9b:floor` (none); `deepseek` = `deepseek/deepseek-v4-flash-0731:floor` (none); `gemini` = `google/gemini-3.8-flash:floor` (minimal). So the author chose **DeepSeek V4 Flash 0731**, not the V4.1 Flash discussed earlier, and switched every model from `:exacto` to `:floor` routing (the cheapest provider). This is the "cost" identifier the author said they would handle. Don't change these IDs. **Take three inconsistencies to the author in Phase V** (list them; don't edit the file): (1) the `deepseek` label still carries V4.1's price ($0.14/$0.42), while 0731 lists $0.021/$0.32; (2) the `deepseek` output folder is back to "Output Files DeepSeek V4 Flash", the folder that holds the **old** V4 Flash runs, so a resume-aware run would skip them all as complete. Suggest "Output Files DeepSeek V4 Flash 0731", or move the old folder aside after the snapshot; (3) `:floor` lets the provider (and its quantization) vary from call to call. Check that the raw log records the serving provider for each call; if it doesn't, propose adding it, because a reviewer can ask which provider served each run. The paper-pipeline strings the infrastructure agent derived from `MODEL_SPECS` follow the file automatically; check that they don't still say "V4.1". GPT-6 Luna was rejected because it has no temperature parameter. |
| Dataset-median baseline | **Pure median.** Nothing is read from the question. Every hidden parameter, including appliance type, baseline time and occupancy, is the median or mode over the **90 retrieval scenarios only**. |
| Fixed-default baseline | The keyword parser is removed. Appliance type = the retrieval-set mode (dryer); all other fixed constants stay. |
| A_H numbers | Per-run everywhere (Set A). The five-run aggregate (Set B) is removed from every script. |
| Appliance tariffs | Faithful to the tariffs, for **one common period, Dec 1, 2025 – May 31, 2026**, all on the **full price-to-compare basis including transmission**. Super off-peak periods: PECO midnight–6 a.m., FirstEnergy 11 p.m.–6 a.m. PPL uses its winter 4–8 p.m. window. Duquesne is truly flat. Six cities remapped. Stroudsburg and Quakertown stay on PPL (flagged: no primary source settles them). |
| Weekdays | Every scenario is a non-holiday weekday, so the weekday TOU and PJM windows apply as coded. The paper states this once. |
| HVAC heating | An electric heat pump, heating at an **HSPF paired with each SEER** (Building America HSP Tables 32 and 4; NREL ResStock for SEER 18 and 22), COP = HSPF / 3.412. Cooling keeps the SEER-derived EER. |
| HVAC mode | See Section 1, follow-up 1. The author's rule: no cooling in heating season, and the gap between the desired and the actual temperature decides the load, not a season threshold. |
| HVAC constants | Heating comfort optimum **71 °F** (HSP, citing ASHRAE 55-2004), range (68, 74). Occupant gain **220 Btu/h** sensible. The equipment gain and the 800 Btu/h base stay, labelled as our assumptions. |
| Budget penalty | Continuous in all three calculators. |
| Data | Stroudsburg HVAC (`Scenario Files/HVACScenarios.xlsx`, row index 30): `hvac_age` 95 → 40. Degradation is capped at 40 years, so the reference score doesn't change. |
| Shower | Comment corrections plus the budget-penalty change. No other value changes. |
| Prompts | Unchanged. |
| Bounds | 5th–95th percentiles over all 285 test + RAG scenarios, the same convention as before, recomputed after the fixes. HVAC Environmental bounds are derived from the HVAC cost percentiles. |
| Provenance | Every constant and function in every calculator and baseline is documented with its source, verbatim quote and status. Merge the four `PROVENANCE_*.md` files into `docs/CALCULATOR_PROVENANCE.md`. Where a new source differs from the old one, the new one is the source and the old one is listed as the previous source. A redundancy pass comes later. Don't re-read sources already used just to re-derive a value. |
| Paper-level decisions | See Section 5: A1-a; A2 rejected; A3-a; A4 dropped; A5 version 1; A6.1 only; A7.1 and A7.3; A8 all; A11-a; A12 rewrite last; Part B all, adjusted. |
| Standing preferences | Fix, don't disclose. The LLMs deliberately don't get the value model. Baselines stay simple medians. Token and cost detail beyond the existing cost table goes in the repo, not the paper. Dataset features, such as the winner's list position, are not mentioned. |

---

## 3. File map: what to run, what to install, what never to run

**A. Live code already edited in place (review it; it is what the rerun will use).** `git diff`
shows every change.
- `model_config.py`: the Gemini and DeepSeek specs and price labels.
- `sentinel_utils.py`: the ranking rounding fix, if follow-up 2 landed.
- `Miscellaneous Scripts/experiments/`: `run_hybrid_ablation_experiments.py`,
  `run_prompt_ablation_experiments.py`, `run_rag_ablation_experiments.py`,
  `run_position_bias_control.py`.
- `Miscellaneous Scripts/core-automation/`: `run_baseline_models.py`,
  `evaluate_parameter_extraction.py`, `evaluate_architecture_metrics.py`.
  - The pipeline agent changed `evaluate_architecture_metrics.py` (its tie-break helper now
    uses 10-dp rounding).
- `Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py`.
- `paper_pipeline/`: `generate_paper_results_numbers.py`, `run_paper_pipeline.py`,
  `compute_dispersion_diagnostics.py`, `duplication_rate_analysis.py`,
  `generate_paper_figures.py`, `reconcile_recollection_diagnostics.py`, and the new files
  `compute_tie_rates.py`, `compute_regret.py`, `build_numbers_of_record.py`.

**B. To install after verification** (copy over the shipped files):
- `Analysis/rerun_prep/calc_new/{HVAC,Appliance,Shower}GroundTruthCalculator.py` →
  `Ground Truth Calculators/`
- `Analysis/rerun_prep/tests/test_*.py` → `tests/`. Point their calculator-path environment
  variable or constant at the installed files.

**C. Run during the refresh chain, in this order** (`CLAUDE.md` "Refresh workflows"):
1. (Superseded 2026-09-27: use `paper/pass6/verify/apply_scenario_fixes.py --apply`, then
   `Scenario Files/build_scenario_workbooks.py --in-place`, per Phase I step 3. The old script
   below cannot run: its source workbook is gone.)
   `Scenario Files/build_consolidated_scenario_workbooks.py`, after the Stroudsburg edit to the
   master.
2. Each installed calculator, which regenerates `Ground Truth/ground_truth_*.xlsx`.
3. `Miscellaneous Scripts/core-automation/sync_rag_ground_truth_scores.py`.
4. `Miscellaneous Scripts/core-automation/build_rag_index.py`, always last. Bump
   `RAG_SCHEMA_VERSION` in both `build_rag_index.py` and `Architectures/Example-Guided_LLM_Scoring.py`
   only if the embedding text changed. Scores aren't embedded, so no bump is expected.

**D. Verification-only tools. Run them to check the work; never use them to produce shipped
outputs:**
- `Analysis/rerun_prep/appliance/` (`harness.py`, `impact.py`)
- `Analysis/rerun_prep/hvac/` (`common.py`, `reproduce.py`, `variants.py`, `impact.py`)
- `Analysis/rerun_prep/pipeline/` (`pipeline_gate.py`, `gate_checks.py`)
- `Analysis/rerun_prep/infra/verify_b60_tiebreak.py`

The `shipped/` and `orig/` subfolders are frozen "before" copies, for diffs only.

**E. Never run for new outputs; historical reference only:**
- everything in `Analysis/pass5/`. Its D1 label-lookup baseline was rejected by the author. Its
  D1/D2 scripts expect an arm named `extracted_per_run`, which no longer exists.
- `paper/pass5/proposal_part_A.md` and `proposal_part_B.md`, which are superseded.
- `Miscellaneous Scripts/legacy/`.

**F. The rerun itself** (Section 6, Phase R; paid; only after the author says go):
- `Architectures/Direct_LLM_Scoring.py`, `Architectures/Example-Guided_LLM_Scoring.py` and
  `Architectures/LLM-Parameterized_Reference_Scoring.py`, once per model. Set `MODEL_KEY` in
  `model_config.py` for each; `N_RUNS` = 5.
- the collect paths of the four experiment scripts;
- then `paper_pipeline/run_paper_pipeline.py`.

---

## 4. Phase V: verify the pre-rerun work independently (do this first)

The author asked for this explicitly. The changes must be rigorous and correct, they must make
physical sense, and they must include **every approved change and nothing unapproved**. Don't
take the reports' claims on trust: re-run the checks. Where the evidence rests on a recorded
quote, spot-check the high-impact values against the primary source:
- the tariff rates and multipliers;
- the HSPF/SEER anchor pairs;
- 71 °F;
- 220 Btu/h.

Don't re-audit every low-impact constant.

1. **Reproduction.** Run the harnesses:
   - Each frozen shipped copy must reproduce its `Ground Truth/*.xlsx` exactly, including the
     RAG score columns.
   - Where a report says "new code with old parameters reproduces", confirm it.
2. **Tests.** Run `Analysis/rerun_prep/tests/` against `calc_new`, and against the shipped
   files, where they must fail as the reports say. Run `tests/test_sentinel_aggregation_matching.py`.
3. **Diff audit, hunk by hunk.** For each calculator, compare `calc_new` with the shipped file
   and map every hunk to a line in Section 2.
   - List any hunk that maps to nothing, such as an unrequested refactor or a changed constant
     nobody approved.
   - List any approved change that is missing.
   - The Shower file should differ only in comments and the budget penalty.
4. **Physical sanity checks:**
   - HSPF rises with SEER, and the COPs are plausible (about 1.8–3).
   - The mode matcher assigns all 105 HVAC scenarios exactly as their question words them.
   - Heat mode never produces cooling energy, and AC mode never produces heating.
   - A setpoint the house already sits past gives 0 load.
   - The budget penalty is continuous and monotone at u = 1.5; evaluate it on both sides.
   - Every hour maps to exactly one TOU period, including windows that wrap past midnight.
     Check the edges: 11 p.m., midnight, 6 a.m.
   - Every utility is on the same rate basis. Duquesne's PTC composition was never inspected;
     check it.
   - New bounds are computed by the stated convention and actually used by `apply_value_function`.
   - Failures surface as the sentinel `1928`, never as a neutral default.
5. **Consistency across code paths.** Confirm that the same installed calculators, called with
   the same scenario fields, score the reference, A_H (`Architectures/LLM-Parameterized_Reference_Scoring.py`),
   both baselines, the hybrid ablation and `sync_rag_ground_truth_scores.py`.
   - Confirm every path passes `question`, which the mode matcher needs. Fix any path that
     doesn't.
   - The baselines may pass the question to the calculator; the calculator reading its own mode
     is not a baseline reading facts.
6. **Pipeline.** Re-run `Analysis/rerun_prep/pipeline/pipeline_gate.py` on the current (old)
   data before installing anything: the main text's per-run A_H numbers must reproduce exactly.
   Check that the dataset-median constants come from the 90 retrieval rows. Check that
   `run_baseline_models.py` reads nothing from the question.
7. **Infrastructure.** Check:
   - the `model_config.py` IDs and labels against OpenRouter's free `/api/v1/models`;
   - that every collecting script writes `collected_utc` and a raw log (read the code paths);
   - that the ablations' tau uses the benchmark tie-break.
8. **Write `paper/pass6/VERIFICATION_REPORT.md`:**
   - what you checked, how, and the result;
   - every discrepancy, each with a proposed fix.

   Fix small, clear errors directly and record them. **Stop and ask the author** before
   installing if anything material is wrong or a hunk changes the model beyond Section 2.

---

## 5. Status of every item in `PASS6_PROPOSAL.md`

Key:
- **S1**: apply now. No number from model outputs, and no calculator behaviour.
- **S-CALC**: after the new calculators are installed. The text describes calculator behaviour
  or ground-truth-derived numbers (bounds, swings, winner counts), which are final once
  installed, so this can happen before or during the rerun.
- **S4**: after the rerun (numbers from model outputs).
- **S5**: claims, after S4.
- **S6**: Discussion 6.1, last.
- **DROP**: don't apply.
- **Adapted**: the item's text must be rewritten for the new calculators or decisions before
  it is applied. Several Pass 5 items were written as disclosures of errors that are now fixed.
  Per the author's rule, they become plain method descriptions, or are dropped.

### Part A

| Item | Status |
|---|---|
| A1 | Scripts are done (per-run everywhere). The paper edits (A1.1–A1.7) are **S4**, with every value from the rerun. |
| A2 | **DROP**, except two corrections at S4: L945 "exactly" becomes the measured rate (A2.10), and L1083 "the one parameter" (the run time is also read from the question). No lookup baseline anywhere. |
| A3 | A3.1 and A3.3 (the GPM mechanism sentences) are **S1**. A3.4 and A3.5 are **S4**. A3.2 is DROP. |
| A4 | **DROP** all edits. The only remaining work is making the abstract and the Conclusion (L1112) consistent, at S5, with no value-function wording. |
| A5 | Abstract **version 1** at **S5**, adapted: last sentence = the new dataset-median result; delete "without the reference's value functions"; model names as in `model_config.py`; 150 words or fewer. Scope swaps (main L328, L330, L415, optionally L873; README L18) also at S5. The title is the author's call (G3), still open. |
| A6 | A6.1 (tie rates, from `paper_pipeline/compute_tie_rates.py` on the new runs) is **S4**. A6.2–A6.4 are DROP. |
| A7 | A7.1 (delete the L404 clause) is **S1**. A7.3 (the regret sentence, from `compute_regret.py`; place it where it reads best, L837 proposed) is **S4**. A7.2 and A7.4–A7.6 are DROP. The DeepSeek A_D output-token anomaly, if it recurs, is documented in the repo only. |
| A8 | **S1**: all of it (the L320 replacement, the Jakeman/Bennett sentence, BibTeX). |
| A9 | **DROP.** The fresh runs carry timestamps and raw logs, so README L73 becomes true as written, and the old Gemini A_E Shower re-collection question no longer arises. State the new collection window in S1 at S4. |
| A10 | **DROP the disclosure.** The calculator now bills super off-peak. Describe the three-period tariffs in the S-CALC batch (see B38–B40). |
| A11 | A11.1 and A11.3 are **S1**. A11.2 and A11.4 (swing numbers, caption) are **S-CALC**, recomputed on the new ground truth. |
| A12 | **S6**: rewrite Discussion 6.1 from the final numbers and whatever limitations remain. |

### Part B

| Items | Status |
|---|---|
| B1–B10 | **S4**. They concern ablation numbers, which the rerun replaces. Keep the logic of each correction (for example "for tau only", "which difference"), but take the values from the new outputs and re-check whether each flawed claim is still flawed. |
| B11 | **S1**. The author must say whether the 19.2 quadrillion BTU is delivered or total energy. |
| B12, B13, B14 | **S1** (table labels and the withheld-parameter list), unless the new calculators change the fields; check. |
| B15, B16, B18–B23, B25 | **S1**. B16 applies on its own. |
| B17 | **S4** (depends on A_E results). |
| B24 | **S4**: sampling settings, reasoning modes and the `:floor` provider routing for the **new** lineup. |
| B26 | **S-CALC**: the EER attribution to HSP Eq. 3 still holds for cooling. Merge it with the new heating sentence. |
| B27 | **Adapted, S-CALC**: describe heating as a heat pump at an HSPF paired with each SEER (cite the HSP tables and ResStock), instead of "at its cooling EER". |
| B28 | **Adapted, S-CALC**: no limitation list. Heating goes into the method description (B27). The flat HVAC and Shower rate becomes a method sentence tied to the shared-time reason (main L614). State the wall-R-value-on-the-whole-envelope choice as a method choice. Weekday: "every scenario is a non-holiday weekday". Keep the `pjm2022emissions` URL fix. |
| B29 | **Adapted, S-CALC**: the penalty is now continuous. State its form, and drop the "never reaches 1.5" claim. |
| B30 | **Adapted, S-CALC**: 220 Btu/h sensible per occupant (HSP Table 44). Glazing 15% (IECC R405). The 20 Btu/h per ft² of glass, the 1.0 Btu/h per ft² and the 800 Btu/h are our assumptions. Fix Eq. 9's 400. |
| B31, B34, B41, B43, B45–B49, B51, B53 | **S-CALC**, as written, after checking each against the installed code. |
| B32 | **Adapted, S-CALC**: the heating optimum is now 71 °F, the HSP value; the text states 71 °F with the citation. |
| B33 | **Adapted, S-CALC**: describe the new mode rule (heat or AC as asked; the load from the setpoint against the free-float temperature; no cooling in heat mode). No disclosure of the old inconsistency. |
| B35, B36, B37 | **S-CALC** with the **new** bound values. |
| B38 | **Adapted, S-CALC**. Take the citations and URLs from `Analysis/rerun_prep/APPLIANCE_REPORT.md` and `PROVENANCE_APPLIANCE.md`: the PECO price-to-compare sheet, the PPL price-to-compare sheet and Supplement 402, FirstEnergy Supplement No. 20 (multipliers) and No. 28 (PTCDefault), the PA PUC release of 11/24/2025 (Duquesne). Update the bib. |
| B39, B40, B44 | **Adapted, S-CALC**. Rewrite supplement Table S1.6 (three periods, new rates, Duquesne flat), the "Rate RTS" label, and the savings sentence: peak to off-peak **14–74%**, to super off-peak **61–81.5%** (recompute from the installed code). "Weekday summer rates" becomes "one common rate period (December 2025 – May 2026), weekday windows". No PPL-mismatch disclosure. |
| B42 | **S1** (paetz2012 authors). |
| B50 | **S1** (dangling S1 pointer). |
| B52 | **DROP**: the data is fixed. |
| B54 | **S-CALC**, or replaced by the A12 rewrite. |
| B55 | **S-CALC**: the swing values are recomputed on the new ground truth. |
| B56 | **S4** (success rates on the new runs). |
| B57, B58, B59, B61 | **S1**. |
| B60 | **DROP the disclosure**: the code now uses the benchmark tie-break, and the rerun makes it true. |
| B62, B64–B67 | **S1**. |
| B63 | Citation style: the **author chooses** first. |
| B68, B69, B73, B74, B75, B78 | **S1**. |
| B70, B71, B72 | **S-CALC** (README ranges, R-value table, mains, heater): take the values from the installed code. |
| B76 | Done by the calculator agents in `calc_new`. Verify in Phase V. |
| B77 | Edits `CLAUDE.md`, so it needs the **author's explicit approval**. |

**Also new at S-CALC or S4, not in the proposal:**
- Model names everywhere: as `model_config.py` names them at rerun time. Right now that is Gemini 3.8 Flash and DeepSeek V4 Flash 0731.
- The cost table `tab:item8` and the S1 price date, regenerated from the new diagnostics.
- The collection window.
- The S1 fixed-default description: no longer per-appliance-type; every Appliance scenario is a
  dryer at 2.10 kWh/cycle.
- The retrieval-set medians and modes.
- Every other paper line that `PIPELINE_REPORT.md` lists as moved.

---

## 6. Execution order

**Phase V: verify.** Section 4. Stop and ask the author if anything material is wrong.

**Phase I: install and refresh** (sequential, only after Phase V passes):
1. Re-run the pipeline gate on the old data and confirm it passes.
2. Snapshot to `C:\Users\Ahaan\LLM-MCDA-Paper-snapshots\2026-09-26_pre_rerun\`:
   - all four `Output Files*` folders;
   - `Analysis/` result files;
   - `Ground Truth/`, `Scenario Files/`, `chroma_rag_db/`;
   - `paper/paper_draft_v2.tex`, `paper/supplementary.tex`, `paper/cas-refs.bib`, `README.md`.
3. Apply all staged scenario fixes (`paper/pass6/verify/scenario_fixes.json`, 148 fixes,
   including Stroudsburg `hvac_age` 95 → 40 as #84 and #82/#83) with
   `paper/pass6/verify/apply_scenario_fixes.py --apply`, then rebuild with
   `Scenario Files/build_scenario_workbooks.py --in-place` (partition fixed by
   `Scenario Files/rag_membership.json`; the old `build_consolidated_scenario_workbooks.py`
   cannot run). Read its audit output; expect 65 changed derived cells
   (`paper/pass6/verify/REBUILD_REPORT.md` section 8).
4. Install the calculators and tests (Section 3B). Run the tests against the installed files.
5. Run the calculators, then sync, then build the index (Section 3C). Check that the
   regenerated xlsx match the agents' preview outputs (`Analysis/rerun_prep/*/out/`).
6. Update the city map in `tests/audit_scenarios.py` (it has the six old assignments) and the
   README reference-range table.
7. Merge the provenance files into `docs/CALCULATOR_PROVENANCE.md`.
8. Rerun the offline parts: both baselines, the dataset-median condition, and the
   single-criterion floors, on the new ground truth.
9. Check that the new output folders are empty, so resume-aware runs skip nothing. Don't delete
   the old folders; they are snapshotted, and the new lineup writes to new folder names for
   Gemini and DeepSeek. Move GPT-OSS's and Qwen's old outputs aside **after** the snapshot,
   because their folder names don't change.
   Archive rule: move the CONTENTS of `Output Files GPT-OSS 20B/` and `Output Files Qwen3.5 9B/`
   (including `position_bias/` and `hybrid_order_reversal/`), and of `Analysis/Prompt_Ablation/`,
   to `archive/2026-09_pre_rerun/<same path>/`, verify every file arrived (sha256), and keep the
   emptied folders as the new output folders. `Analysis/RAG_Ablation/checkpoints/` must be empty.
10. Code changes approved 2026-09-27 (mocked-HTTP tests; prompts byte-identical; then `tests/`
    under all four MODEL_KEYs and the pipeline gate):
    a. prompt-ablation `cot_scaffold` arms (A_D and A_E, every model) send
       max_tokens = min(32768, pinned endpoint `max_completion_tokens`), looked up by a free
       GET of `https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints` at run start
       (abort if it fails; `--cot-max-tokens N` overrides); other arms and the architectures
       keep 8192; the cap is recorded in the raw log;
    b. prompt-ablation Top-1/Top-2: a failed or unscored scenario counts as wrong, denominator
       = all scenarios in the cell (the RAG-ablation rule); tau/MAE unchanged;
       `n_failed_scenarios` reported;
    c. the five-consecutive-failures breaker in `sentinel_utils` is lock-protected;
    d. Duquesne (V_APPLIANCE D9): composition primary-confirmed from Duquesne Light Supplement
       No. 108 to Electric Pa. P.U.C. No. 25,
       `temppapers/currenttariff_108_256018e393-caba-4589-8360-f64513d80451.pdf` (168 pages;
       read only the TOC and the needed pages). 13.75 c/kWh unchanged.

**Phase P1: Step 1 paper edits (subagent, can run in parallel with Phase I or R).**
- First, per `CLAUDE.md`'s paper reading protocol, map the section structure with an explore
  agent.
- Then dispatch one well-scoped subagent (Sonnet, with a precise prompt) to apply every **S1**
  item from Section 5 with the Edit tool.
- Before each edit, re-check its quoted old string. The file hasn't changed since Pass 5, but
  verify anyway: `Analysis/pass5/audit_old_strings.py`.
- Minimal-diff rule: touch only the quoted span.
- Run the stop-slop skill before writing any prose.
- Snapshot first.

**Phase S-CALC: calculator-description edits** (after Phase I; before or during the rerun).
Apply every S-CALC item, with values from the installed code and the regenerated ground truth.

**Phase R: rerun (paid; only when the author says go).**
1. **Smoke test.** One call per model, a few cents. Check that the ID and `:exacto` resolve,
   that `temperature` and `reasoning` are accepted, and the token use. Report it to the author.
2. **Collection plan.** Take the run counts of every experiment from the paper's Methods and S2
   and from each script's defaults: main benchmark 5 runs; prompt ablation; RAG ablation; A_H
   ordering arms; position-bias control. Show the author the call count and cost estimate
   before collecting. The earlier estimate for everything is about $24–30.
3. **Collect** in one window. Every run writes `collected_utc` and a raw log.

**Phase S4: numbers.**
1. Run `paper_pipeline/run_paper_pipeline.py`.
2. Regenerate the numbers of record with `paper_pipeline/build_numbers_of_record.py`, and diff
   them against `paper/pass5/NUMBERS_OF_RECORD.csv`.
3. Apply every S4 item and every other moved number.
4. Re-check every claim whose direction could flip:
   - per-model best/worst labels;
   - "for every model";
   - significance calls;
   - fixed-default and dataset-median comparisons;
   - the reversal cell under the MEREC HVAC weight vector.
5. Never pool across models.

**Phase S5: claims.** The L808 effect size (dataset median), abstract version 1 adapted,
abstract and Conclusion consistency, the scope swaps, and the title once the author picks it.

**Phase S6: Discussion 6.1 rewrite (A12).** About 800 words, written from the final numbers.

**Phase VER: verification.**
1. The old-string check on any prepared edit.
2. Diff the paper's numbers against the regenerated CSV.
3. A diagnostic compile: pdflatex, bibtex, pdflatex ×2.
4. Re-run the simulated EMS review (`paper/MOCK_EMS_REVIEW.md` has the 20-row consistency
   table).
5. The author compiles in Overleaf.

---

## 7. What only the author can supply or decide

- **G3 title.** Candidates are in A5 of `PASS6_PROPOSAL.md`.
- ~~**B63** citation style; **B77** `CLAUDE.md` edit; **B11** delivered or total energy; **B10**
  the real reason for the α values.~~ Decided 2026-09-27: option (a) for B10, B11 and B63 and
  B77 approved; all four applied.
- **Stroudsburg and Quakertown utility assignment.** Both stay on PPL for now.
- **Solar gain in HVAC heat mode**, and the three `model_config.py` inconsistencies (Section 2,
  "Model lineup").
- **Bib fields no one could confirm:** the Ibáñez-Rueda authors and title, the HSP report
  number, the IECC table number, the NeurIPS page ranges, the paywalled page numbers.
  `APPLIANCE_REPORT.md` now has the PECO and FirstEnergy URLs.
- **Go-ahead** for the smoke test and for the rerun.
- **Before submission:** Zenodo DOI, EMS hardware and program-size fields, highlights,
  graphical abstract, strip the co-author TODOs and `todonotes` (B62).

---

## 8. Rules

- Never run `git commit` or `push`, and no `checkout`, `stash` or `reset` of the author's work.
- Unexpected git changes are the author's or a subagent's; don't revert them.
- Paper edits are minimal-diff (the absolute rule in `CLAUDE.md`), with the Edit tool.
- Run the stop-slop skill before writing any paper or supplement prose, subagents included.
- Never pool metrics across models.
- Appendix references are bare `\ref{...}`.
- Sentinel `1928`, and ASCII-only `print()` in pipeline code.
- Fix, don't disclose.
- No limitation sentences for things the rerun fixed.
- Token and cost detail goes in the repo docs.
- `CLAUDE.md` edits need the author's approval.
- Every paid API call needs the author's go-ahead.
- Subagents: Sonnet with a precise prompt for mechanical work, Opus for judgment. Tell each
  subagent to say whether it ran any git command.
- The author compiles in Overleaf; a local compile is diagnostic only.
- Dr. Huang's Overleaf comments are already accounted for. Don't re-account for them, and
  don't resolve them; replies go in-thread.
- Leave `paper_draft_working.tex` alone; it is the frozen rollback point.

---

## 9. Where the evidence lives

| File | Contents |
|---|---|
| `paper/pass5/RERUN_PREP_PLAN.md` | The pre-rerun plan and decisions (phases P1–P5). |
| `paper/pass6/PASS6_PROPOSAL.md` | Working copy of the Pass 5 proposal: every item with its old and new text, evidence, and line numbers. |
| `Analysis/rerun_prep/*_REPORT.md` | What each pre-rerun agent changed and measured. |
| `Analysis/rerun_prep/PROVENANCE_*.md` | Constant-to-source tables. |
| `Analysis/rerun_prep/pipeline/*.csv` | Gate results; old and new baseline numbers. |
| `paper/pass5/NUMBERS_OF_RECORD.csv` | The pre-rerun numbers of record (122 rows). |
| `paper/pass5/D1–D13_REPORT.md` | Pass 5 analyses. D1's lookup baseline is rejected. |
| `paper/CALCULATOR_AUDIT.md` | The original calculator audits, with source quotes. |
| `paper/MOCK_EMS_REVIEW.md` | The simulated panel. |
