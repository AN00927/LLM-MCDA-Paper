# Handoff to the next cloud session (written 2026-09-27)

Read in this order: this file, `CLAUDE.md`, `paper/pass6/CLOUD_AGENT_CONTEXT.md` (standing
rules; all binding), then `paper/pass6/PASS6_HANDOFF.md` sections 5-6 when you reach the paper
work. Work on branch `cloud-work`. No paid API call without the author's go-ahead in the
conversation. The author let the previous session commit and push to `cloud-work`; confirm that
permission in the new conversation before committing.

Why a new session: the author is widening the environment's network access so primary sources
can be opened (the old sandbox denied nrel.gov, energy.gov, ashrae.org, osti.gov,
codes.iccsafe.org, huggingface.co and openrouter.ai; WebSearch worked but WebFetch/curl could
not open any source).

## 0. Setup (first thing)

1. `python -m venv .venv && .venv/bin/pip install -r requirements.txt` (`.venv` is not in git;
   system Python lacks pandas). Use `.venv/bin/python` everywhere.
2. Check the network: `curl -s -o /dev/null -w "%{http_code}\n" https://docs.nrel.gov/docs/fy11osti/49246.pdf`
   and the same for `https://huggingface.co`. If a source host is still denied, tell the author
   which one and continue with what does not need it.
3. Baseline check: `MODEL_KEY=gemini .venv/bin/python -m pytest -q tests` should give 368 passed,
   1 failed (`test_ae_real_chroma_retrieval_distances`, no Chroma index yet). The
   `attempts=None` crash in `run_rag_ablation_experiments.py` is being fixed by the author
   elsewhere; ignore it.

## 1. State on `cloud-work` (HEAD `4a93468`)

- `846b02e` Phase I done (offline): 148 scenario fixes, rebuild, new calculators + tests
  installed, ground truth regenerated, RAG scores synced, README ranges, `audit_scenarios.py`
  city map, `docs/CALCULATOR_PROVENANCE.md` (`!docs/*.md` in `.gitignore`), Duquesne D9
  resolved, code changes a-c, fixed-default baseline, 301 old outputs archived to
  `archive/2026-09_pre_rerun/`. Details: `paper/pass6/verify/PHASE1_RUN_REPORT.md` and
  `PHASE1_CODE_CHANGES_REPORT.md` (both under an ignored path; use `git add -f`).
- `fedf891` scenario workbook backups (`Scenario Files/Backups/`).
- `4a93468` **author decision: HVAC solar gain now counts in heat mode as well as AC mode**
  (`include_solar=True` in `calculate_heating_load` and `calculate_scenario_scores`). Recomputed:
  HVAC ground truth, HVAC RAG scores (`HVACRagScenarios.xlsx` only; Appliance/Shower unchanged),
  fixed-default baseline, README table, provenance rows, `tests/test_hvac_reference.py` (new
  `test_solar_gain_offsets_heating_load`; 19/19). New HVAC bounds: cost $0.19-$3.21 (p5/p95 of
  280 nonzero active alternatives), environmental 0.97-17.59 lbs CO2. Against the pre-solar
  ground truth: 12/105 winners and 16/105 rankings change (10 of the 12 are heat-mode
  questions). **Pending review**: the 20 Btu/h per ft2 of glass is still an unsourced
  assumption, and it is a cooling-season peak figure.
- New output folders are empty. `model_config.py` already fixed the earlier issues: DeepSeek
  0731 price label, "Output Files DeepSeek V4 Flash 0731" folder, per-call `provider` logged.

Gotcha: `Miscellaneous Scripts/core-automation/sync_rag_ground_truth_scores.py` has no argument
parsing; `--help` runs the full sync and rewrites all three RAG workbooks. Restore unchanged ones
with `git checkout -- <file>` so the Chroma source hash does not move for nothing.

## 2. First task: Opus review of every value (the author asked for this before anything else)

Dispatch an **Opus** subagent (or several, one per calculator, all Opus) to check every row of
`docs/CALCULATOR_PROVENANCE.md` (HVAC, Appliance, Shower, Baselines; about 214 rows, 113 marked
"our assumption") against the installed code and the primary source. Per row:

1. The value in the code matches the value in the row (file and line).
2. The source is opened (PDF or page), and the row gets the verbatim quote, the page or table,
   and the URL. Report a mismatch between the quote and the value.
3. For each "our assumption" row that is a physical or economic number (not a design choice such
   as a value-function shape or the criterion weights), look for a primary source that gives a
   defensible value. Propose the replacement with its quote, or state that none was found and
   why the assumption stands.
4. Source hierarchy: tariffs and codes, then government labs (NREL, LBNL, DOE, EIA, EPA), then
   ASHRAE/ACCA handbooks, then peer-reviewed papers. No retailer pages or blogs as a final source.
   PDFs over about 30 pages: read the table of contents first, then only the pages needed
   (`pypdf` page ranges).
5. Output: `paper/pass6/verify/VALUE_REVIEW.md`, a table per calculator with columns: constant,
   code value, source value, quote, page/URL, verdict (confirmed / mismatch / assumption kept /
   replacement proposed), and the proposed change.

**Solar gain comes first.** The current term is `window_area * 20` Btu/h, with glazing = 15% of
floor area (IECC R405 reference design, sourced). Candidate cited replacement:
q_solar = A_glass x SHGC x (interior shading multiplier) x I, with SHGC and the shading
multipliers from the Building America House Simulation Protocols (2010 revised,
NREL/TP-5500-49246; search snippets show SHGC 0.30-0.44 in the FY13 addendum, NREL/TP-5500-57450)
and I = mean incident solar on vertical surfaces for Pennsylvania, split by heating and cooling
season, from NREL TMY3 / NSRDB data (Harrisburg or Philadelphia) or an ASHRAE Fundamentals table.
The HVAC scenarios have no time of day, and the energy window is 8 h; the agent must state how
it averages irradiance over that window and why. Note that ACCA Manual J's heating design load
omits solar (a sizing worst case), while ASHRAE's energy-estimating (balance-point) method
counts solar and internal gains; the calculator estimates energy, so crediting solar is
consistent with the second. Cite whichever is used.

**Stop after the review and show the author the proposed changes** (each one changes ground
truth). Apply only what the author approves. Any calculator change then follows the CLAUDE.md
refresh order: run the calculator -> recompute bounds with
`Analysis/rerun_prep/hvac/common.py:cost_percentile_bounds` (HVAC) or the calculator's own
convention -> update the bounds, the README table and the bound tests -> rerun the calculator ->
`sync_rag_ground_truth_scores.py` -> fixed-default baseline
(`run_baseline_models.py --baselines fixed_default`) -> provenance rows -> tests -> pipeline gate
(`Analysis/rerun_prep/pipeline/pipeline_gate.py after` then `diff`; the only allowed differences
are score changes you caused) -> `build_rag_index.py` last.

## 3. Remaining fixes (author said: fix everything)

1. **Delete `tests/audit_scenarios.py`** (author's call; it flagged every scenario as an orphan).
   Update the places that name it: `docs/CODEBASE_GUIDE.md`, `docs/CALCULATOR_PROVENANCE.md`,
   `paper/pass6/verify/PHASE1_RUN_REPORT.md` (item 4). Leave historical reports as they are.
2. **Appliance tests and docs** (a Sonnet agent was started and stopped before changing anything;
   redo it). New `tests/test_appliance_validation.py` pinning, against the installed calculator:
   D1 misspelled/unknown appliance -> sentinel; D2 missing/unparseable `baseline_time` ->
   sentinel; D3 `utility_budget` None/non-numeric -> sentinel, no crash; D4 missing/0 budget ->
   what the code does; D6 "13:00 PM" -> sentinel; budget-penalty continuity at u = 0.8, 1.0, 1.5,
   monotone, positive at 2.0, for Appliance and Shower (HVAC already has it). Verify each fix is
   really in the code first. Docs: `V_APPLIANCE.md` D1-D4/D6/D13 "Applied?" column -> applied
   (daafa48) or tested; `PROVENANCE_APPLIANCE.md` rows still describing the old behaviour; D5
   "about 0.29" -> "0.23" (recompute max utilization first) in `PROVENANCE_APPLIANCE.md`,
   `APPLIANCE_REPORT.md` ~L399, `HVAC_SHOWER_REPORT.md` ~L234; D7 regenerate
   `Analysis/rerun_prep/appliance/calc_new.diff` (shipped vs installed; name the base commit);
   D8 regenerate `Analysis/rerun_prep/appliance/out/check_calc_new.xlsx` from the installed
   calculator; close open items 2-6 in `docs/CALCULATOR_PROVENANCE.md`.
3. **Baselines** (provenance open items 8-9): re-verify the line citations for
   `run_hybrid_ablation_experiments.py`; remove the constants no code reads
   (`HVAC_DEFAULT_HOUSEHOLD_SIZE`, `HVAC_DEFAULT_OUTDOOR_TEMP`, `HVAC_DEFAULT_UTILITY_BUDGET`,
   `SHOWER_DEFAULT_OUTDOOR_TEMP`, and others the item lists) after grepping the whole repo, then
   the tests and the gate.
4. **HVAC rows marked "Quote not recorded"**: fill them during the Section 2 review.
5. **Now possible with the network:** `build_rag_index.py` (after every data change), then
   `pytest tests` under all four MODEL_KEYs (expect all pass), then the nearest-neighbour
   baseline (`run_baseline_models.py --baselines nearest_neighbor`).

## 4. Paper edits (after Sections 2-3)

The author asked for every edit that does not depend on the rerun's numbers: the **S1** items
and the **S-CALC** items in `PASS6_HANDOFF.md` section 5 (Phase P1 and Phase S-CALC in section 6).
Manuscript: `paper/paper_draft_v2.tex` and `paper/supplementary.tex`. Map the structure with an
explore agent first (CLAUDE.md paper reading protocol), then dispatch Sonnet agents with precise
prompts; minimal-diff rule; run the `stop-slop` skill before writing prose; re-check each quoted
old string before editing.

Changes since `PASS6_HANDOFF.md` was written that S-CALC must reflect:
- **B30**: solar gain now enters the heat balance in both modes. Its value and citation follow
  whatever the author approves in Section 2 (if the 20 Btu/h per ft2 stays, it stays labelled as
  our assumption).
- **B35-B37**: HVAC bounds are now $0.19-$3.21 and 0.97-17.59 lbs CO2 (or whatever Section 2
  produces); take them from the installed code, not from this file.
- **B38-B40, B44**: Duquesne composition is primary-confirmed (Supplement No. 108, see
  `docs/CALCULATOR_PROVENANCE.md`); 13.75 c/kWh unchanged.
- **D12** stale text: main text "per-cycle cost spans \$0.025--\$0.71" -> \$0.028--\$0.774 and
  the "weekday summer rates" wording; supplement "PPL (Rate RTS)", "2--6pm", "Jun-2025 PTC",
  "49--76\%" and Table S1.6. Savings: 14-74% off-peak, 61-81.5% super off-peak (recompute).
- A11.2/A11.4 and B55 swing values: recompute on the current ground truth.

Skip anything tagged S4, S5 or S6 (they need rerun numbers) and every item in
`PASS6_HANDOFF.md` section 7 that only the author can decide (B11 delivered vs total energy,
B10, B63, B77, the title). Collect those in the report as open questions.

## 5. After that

Phase R (smoke test, then full collection, about $28-32) only on the author's go-ahead with the
cost shown first. Update `paper/pass6/CLOUD_AGENT_CONTEXT.md` "State" and `PASS6_HANDOFF.md`
as each phase finishes.
