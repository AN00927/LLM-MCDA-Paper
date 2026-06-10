# GT Calculator / Architecture / Repo Audit & Refactor

Work through the phases below in the
dependency order given in the final section. Every `→ DISPATCH` block is an explicit
instruction to spawn a subagent yourself using the Agent tool — do not skip them.
Slash commands are written as `«RUN: /command»`; invoke them via the Skill tool at
the point each one appears.

---

## Subagent roster

Use this table whenever you dispatch an agent. Subagents are **read-only researchers**
and never edit. You apply every change so consistency across the 3 calculators is preserved.
Give each subagent the exact files to read and the exact return format you want.
Subagents may search online (WebSearch/WebFetch) whenever needed.
Batch all independent dispatches in one message so they run in parallel.

| Job | `subagent_type` | model | effort |
| --- | --- | --- | --- |
| Pure mechanical: grep, list call sites, read column types, quote lines | `Explore` | haiku | low |
| Bib + web lookup: find a source, verify a mapping, check a rate | `general-purpose` | sonnet | medium |
| Deep physics/literature evaluation: assess formula correctness, recommend VF corrections | `general-purpose` | sonnet | high |
| Standardization plan (Phase 1 only) | `Plan` | sonnet | high |

---

## Global rules

- Never combine system + user messages anywhere. Leave message structure as-is.
- Windows console is cp1252 — no non-ASCII in any `print()` that runs in the pipeline.
- Never `git commit` / `git push`.
- Respect proxy/true pairs, sentinel `1928`, and the refresh order (BuildRAG always last)
  in `CLAUDE.md`. Any calculator change invalidates affected `*_results.xlsx`.
- Every time you change a number from what is currently in the code, append an entry to
  a running **"Modifications Made"** list: old value → new value + source. Deliver this
  list at the end.
- After each phase that edits a calculator, run «RUN: /code-review medium» on the diff
  before moving on.

---

## PHASE 1 — Repo-wide standardization & organization (DO THIS FIRST)

No behavior changes in this phase — pure organization. Do the 3 GT calculators as one
group, then the 3 architectures as a **separate** group.

**1a. Plan the refactor first.**

*ANYWHERE THAT THERE IS A HIGH LEVEL PLANNING, USE YOUR OWN REASONING, NOT SONNET HIGH UNLESS IT IS NOT A SUPER HIGH LEVEL PLANNING. HOWEVER THIS IS VERY HIGH LEVEL.*
"Read every file in `Ground Truth Calculators/` and `Architectures/`. Produce a
standardization plan covering, for each group separately (calculators vs architectures):
(1) canonical function order — most shared/common methods live in the lower half of each
calculator, standardize that ordering; (2) canonical function names for methods that do the
same thing across files; (3) which methods should be `@staticmethod` vs `@classmethod` vs
plain instance methods — pick ONE convention and list every method that currently violates
it; (4) import statements per calculator that differ and should be unified.
Return as a checklist of concrete renames/moves with file:line. Do NOT edit anything."

**1b. Apply the plan:**

- Standardize function order, names, and method-binding across all 3 calculators
  **only where it does not change behavior of any one calculator**; do the same separately
  for the 3 architectures.
- Standardize the import block across all 3 GT calculators (Appliance currently imports a
  divergent set from `sentinel_utils` — bring them in line).
- **Comment cleanup (whole repo):** delete every docstring that just restates the function
  name (e.g. `"""Process hvac scenarios."""`); remove obvious comments that restate
  self-evident code.

---

## PHASE 2 — Shared structural refactors

Do these before the per-calculator logic audits so the logic audits work on the final structure.

**2a. `electricity_rate` constant — HIGH PRIORITY.**
In HVAC it is set to a flat `0.19` at ~line 617 deep inside the code. Wrong place, possibly
wrong value. Move it to a named constant at the top of the file.
→ DISPATCH (`general-purpose`, sonnet, medium): "What is a defensible residential electricity
rate ($/kWh) for the utility/region these scenarios model? Check `cas-refs.bib` and the
Appliance calculator's `utility_rates` dict for what the repo already uses; confirm against a
current public source online. Return the value + source."
Set the constant to the verified value; never leave a bare `0.19`.

**2b. `parse_utility_budget` — move out of `sentinel_utils`, simplify, possibly delete.**
→ DISPATCH (`Explore`, haiku): "Across all xlsx in `Scenario Files/` and
`Ground Truth/`, what is the actual stored type/format of the `utility_budget` column?
Are there ever currency symbols or commas, or is it always a plain number? List every
file and function that reads that column."
Decision rules based on findings:

- If budgets are always plain numerics, inline the parse (usually just `float(...)`) and
  delete the standalone function.
- If a small helper is still warranted, put it in each GT calculator, not `sentinel_utils`.

Refactor every call site accordingly.

**2c. `normalize_occupancy_context` — keep or kill?**
→ DISPATCH (`Explore`, haiku): "In every xlsx that feeds the calculators,
what raw values actually appear in the occupancy / occupancy_context column? Then find
every call to `normalize_occupancy_context` and `emissions_factor_for_occupancy`
across the repo with file:line."
If stored values are already canonical (normalization is a no-op), remove
`normalize_occupancy_context` and refactor every use. If still needed, document why.
**Decide this before Phase 3's occupancy work** so those call sites are only touched once.

**2d. `calculate_budget_penalty` ↔ `calculate_monthly_cost` consolidation.**
→ DISPATCH (`Explore`, haiku): "Find all call sites of `calculate_budget_penalty`
and `calculate_monthly_cost` in all 3 GT calculators. Is `calculate_budget_penalty` actually
called anywhere? Does it internally recompute monthly cost?"
Based on findings: if the penalty function is unused, identify where it *should* be used
(likely `calculate_scenario_scores` / practicality) and wire it in, or remove it.
If it recomputes monthly cost, consolidate so `monthly_cost` is computed inside the larger
function, not as a separate call. Apply the resulting pattern to **all 3 calculators**.

---

## PHASE 3 — HVAC calculator logic audit (`HVACGroundTruthCalculator.py`)

Launch the Phase 4 citation subagents in parallel with this phase — they are read-only and
independent. Items 3b, 3d, and the occupancy weighting in 3g require your own deep reasoning
(ultrathink); do not delegate those decisions to a subagent.

**3a. Ventilation comment vs. code.**
Lines ~86–88: the comment does not match `ventilation_cfm` / `ventilation_load`.
→ DISPATCH (`general-purpose`, sonnet, medium): "Find the correct ASHRAE or ACCA source
for residential ventilation CFM and ventilation load calculation. Check `cas-refs.bib`
first; search online if not found. Return the correct formula + source."
Fix both the comment and the code to agree, with the citation.

**3b. `calculate_comfort_score` — full audit. (ultrathink)**
Is the optimal **76 °F** (for comfort only, not practicality) actually right per ASHRAE 55
or other thermal-comfort literature?
→ DISPATCH (`general-purpose`, sonnet, medium): "From `cas-refs.bib` (and online if needed)
find the cited thermal-comfort optimum / comfortable indoor temperature band for residential
cooling. Return the number(s) + bib key or URL. Flag if 76 °F is unsupported."
Correct the number if wrong. Add in-text citations to every line and value in this function
and analyze the whole function for correctness, not just the optimum.

**3c. `calculate_practicality_score` — first `if` condition.**
The threshold was changed from `> 75` to its current form. Evaluate whether the new logic
is sound; explain your reasoning and fix if not. Add a justification comment in the same
style as the one you add for Shower practicality in Phase 5h.

**3d. Degradation belongs in practicality, not energy consumption. (ultrathink)**
Degradation currently lives in `calculate_energy_consumption`. Design and implement how
`calculate_practicality_score` should incorporate degradation, then remove it from the
energy path. Sentinel discipline must hold: a failed sub-calc surfaces `1928`, never `0.0`.

**3e. `periods_per_month` default = 90.**
Should `calculate_monthly_cost` use 90 periods per month? Justify how a scenario period
maps to real time and correct the default if wrong.

**3f. `calculate_budget_penalty` wiring.**
Covered structurally in Phase 2d. Once that consolidation is done, confirm the HVAC
wiring in `calculate_scenario_scores` is correct.

**3g. `emissions_factor_for_occupancy` — full reasoning audit.**
Validate the PJM marginal peak/off-peak framing (required by `CLAUDE.md`) and the
occupancy weighting logic.

- Why does occupied-sleep return off-peak? Confirm that is intended or fix it.
- Audit this specific calculation for physical correctness:

  ```python
  if ctx.startswith("unoccupied_"):
      hours_match = re.search(r"(\d+)", ctx)
      hours_away = int(hours_match.group(1)) if hours_match else 8
      hours_away = max(0, min(hours_away, 24))
      if hours_away <= peak_h:
          return peak
      offpeak_hours = hours_away - peak_h
      return (peak_h * peak + offpeak_hours * off) / hours_away
  ```

  Is this weighted average physically correct? Fix and cite if not.

**3h. `apply_value_function` JSON nesting.**
Comfort and practicality JSON specs are nested inside the environmental JSON. Restructure
so they are top-level siblings (changing whatever downstream code reads them). Apply the
cleaner schema consistently across all 3 calculators.

**3i. `is_cooling` in `calculate_scenario_scores`.**
`is_cooling` is computed above the if/else using a hardcoded 75 °F. Move the
cooling/heating decision into the if/else and use `indoor_temp` (the actual setpoint) instead.

**3j. `effective_temp` audit.**
What is `effective_temp` used for and is that use physically accurate? The hardcoded **±5**
is suspect. For each use site, decide whether `effective_temp` is justified; if kept, replace
the hardcoded ±5 with a derived value (propose the derivation with a citation).

**3k. `ach` removed.**
`ach` was removed as an input param from the heating/cooling load functions; use `0.35`
as a named constant. Update every call site and any place that previously passed `ach`.

---

## PHASE 4 — Citation & source sweep across ALL 3 calculators

Launch these as background subagents in parallel while you work on Phase 3.

Every important formula step and every hardcoded value in all 3 GT calculators needs an
in-text citation. Anywhere a value is justified only by a vague word like `"standard"`,
a season label (`# Winter minimum`), or nothing at all, replace it with a real citation.
Where the literature contradicts the current number, change the number and log it.

→ DISPATCH THREE subagents in one message (`general-purpose`, sonnet, high,
`run_in_background: true`), one per calculator, with this instruction template:

> "Read `Ground Truth Calculators/<X>GroundTruthCalculator.py` and `paper/cas-refs.bib`.
> For EVERY hardcoded constant and every formula step — loads, energy, emissions factors,
> comfort and practicality value functions, inlet/water temps, cycles, rates, reference ranges
> — return one row per item:
> `file:line | value or formula | current justification | matching bib key (or 'none') |
> if none: a citable external source (URL) | is the number supported? (yes/no + correct value if no)`
> Pay special attention to comfort and practicality VF shapes and thresholds: if no bib source
> exists, find one online or recommend a corrected VF. Do NOT edit anything."

Once all three report back, you apply:

- In-text citations on every value/formula in all 3 calculators.
- Comfort & practicality VF source comments in all 3 (currently missing).
- If the literature disagrees with a number, change it and log it.

Standardize citation comment style repo-wide: as short as reasonably possible while
conveying the full source, in-text style only.
→ DISPATCH (`Explore`, haiku): "List every source/citation comment
across the repo with its current format so it can be normalized to one short in-text style."
Then normalize all of them.

---

## PHASE 5 — Appliance & Shower calculator-specific logic

**Appliance (`ApplianceGroundTruthCalculator.py`)**

**5a. Imports.** Confirmed unified in Phase 1b. Verify Appliance no longer has a divergent
import set from `sentinel_utils`.

**5b. Weekend/holiday handling.**
→ DISPATCH (`Explore`, haiku): "In the Appliance calculator, where (if anywhere)
are weekends/holidays actually treated in the rate-period or emissions-period logic? Quote the
relevant lines verbatim."
Confirm whether the header comments (~lines 29–31) match the implementation; fix comments to
match reality. Add to `paper/paper_draft_working.tex` a placeholder in the methodology noting
that weekend/holiday peak hours are not currently modeled, in this format:
`[PLACEHOLDER NOTE] Weekend and holiday peak-hour pricing not currently modeled; all days
treated as weekdays for TOU rate assignment.`

**5c. Verify `city_to_utility` mapping + `utility_rates`.**
→ DISPATCH (`general-purpose`, sonnet, medium): "Verify the `_normalize_city` /
`_utility_for_location` city-to-utility mapping and the `utility_rates` dict in the Appliance
calculator against current public utility data online. Return:
city | mapped utility | correct? | rate used | correct rate + source."
Apply corrections and add citations.

**5d. `cycles_per_month` realism.**
→ DISPATCH (`general-purpose`, sonnet, medium): "For each appliance type in the Appliance
scenarios (check the xlsx for the full list), find the cited/realistic average cycles per month
from `cas-refs.bib` or online. Return: appliance | current value | realistic value + source."
Refactor `cycles_per_month` (and any analogous per-appliance default constants) to
per-appliance literature values. Log every change.

**Shower (`ShowerGroundTruthCalculator.py`)**

**5e. `reference_ranges` location.** Move the `reference_ranges` from the top of the file into
`apply_value_function`, matching how HVAC and Appliance do it. Confirm the ranges are the
5th–95th percentiles of the actual scenario distribution and match the README table.

**5f. Pseudo-justification comments.** Lines like
`if outdoor_temp <= 32: return 45.0  # Winter minimum` are not real citations. Replace with
in-text citations from the Phase 4 Shower subagent output. If literature disagrees with the
number, change it and log it.

**5g. `self` calls.** Replace `ShowerGroundTruthCalculator.<method>` calls inside the class
with `self.<method>`. Reconcile with the Phase 1 static/instance decision — if a method is
made instance-bound, `self.` is the correct form.

**5h. Practicality justification template.** Fill in the placeholder comment at Shower line 138.
Once filled, use that comment as the template for the practicality justification comments you
add to the HVAC (Phase 3c) and Appliance calculators.

**Cross-calculator VF propagation.**

**5i.** If any HVAC value functions change from Phase 3, propagate the corresponding changes
to Appliance and Shower where they apply. **Before changing any VF**: record how the current
VF shapes the score distribution and what would need to change in the reference ranges or
README table if the VF changes. Document this analysis before editing.

---

## PHASE 6 — Architecture bug fixes

**6a. RAG `NameError` bug in `RAGDatabaseOptimized.py` (~lines 535–536).**

```python
diagnostics['rag_retrieved_count'] = len(retrieved)
diagnostics['rag_context_length'] = len(rag_context)
```

`retrieved` and `rag_context` are never assigned in `score_alternative_with_rag`. The
retrieval call at ~line 496 is inlined directly into `build_user_prompt_with_rag`, so these
two lines raise `NameError` at runtime. Fix by capturing the retrieval results into local
variables first, then using them for both the prompt and the diagnostics. That is the
preferred fix; only remove the diagnostics lines if you find a specific reason not to capture.

**6b. Verbatim-alignment block in `RAGDatabaseOptimized.py` (~lines 521–533).**

```python
verbatim_alts = [scenario.get('alternative_1'), scenario.get('alternative_2'), scenario.get('alternative_3')]
...
for idx, alt_data in enumerate(alternatives_scores):
    alt_data['extracted_alternative'] = alt_data.get('alternative', '')
    if idx < len(verbatim_alts) and verbatim_alts[idx] not in (None, ''):
        alt_data['alternative'] = str(verbatim_alts[idx])
```

Trace whether `extracted_alternative` or the overwritten `alternative` is consumed downstream
in output sheet columns or metrics. If nothing depends on the verbatim overwrite, remove the
block. If it is needed, keep it and add a one-line comment explaining why.

**6c. Decimal precision.**
Every score rendered to the user or passed to an LLM with one decimal (`.1f`) must become
two decimals (`.2f`).
→ DISPATCH (`Explore`, haiku): "List every `:.1f`, `%.1f`, and `round(x, 1)`
that formats a score for display or for an LLM prompt across `Architectures/` and the GT
calculators. Exclude latency/ms and non-score numbers."
Apply `.2f` to every score-formatting instance found.

«RUN: /code-review high» on all architecture diffs after 6a–6c.

---

## PHASE 7 — Miscellaneous Scripts, `sentinel_utils.py`, `model_config.py`

**`Miscellaneous Scripts/`** covers `BuildRAG.py`, `SyncRAGGroundTruth.py`,
`CalculateMetrics.py`, `SensitivityAnalysis.py`, `EntropyWeights.py`, `MERCECWeights.py`,
`ImpliedWeights.py`.

**7a. Validation-only firewall.**
The weight scripts (`EntropyWeights`, `MERCECWeights`, `ImpliedWeights`) and
`SensitivityAnalysis` must be validation-only and must never be imported by any architecture
or calculator, and must never mutate `CRITERION_WEIGHTS` at runtime (required by `CLAUDE.md`).
→ DISPATCH (`Explore`, haiku): "Find every import of those four scripts and every
assignment to `CRITERION_WEIGHTS` anywhere in the repo."
Flag any violation to the user — do not silently fix by changing weights.

**7b. RAG schema-version lockstep.**
Verify `BuildRAG.RAG_SCHEMA_VERSION == RAGDatabaseOptimized.EXPECTED_RAG_SCHEMA_VERSION`.
If any change in Phases 2, 4, or 5 touched `format_embedding_text` or Chroma metadata, bump
**both** constants. A code-only embedding change still needs a version bump — the source SHA
only catches sheet edits.

**7c. Citations/comments + comment cleanup.**
Apply the same two repo-wide rules to all Misc Scripts: in-text citations for any
literature-derived constant (e.g. emissions factors, percentile thresholds in metrics);
delete name-restating docstrings; remove obvious comments. These scripts should be in scope
for the Phase 4 citation subagents and the Phase 1 comment-cleanup pass — confirm they are.

**7d. Shared-helper import consistency.**
After Phase 2 moves `parse_utility_budget` out of `sentinel_utils` and possibly removes
`normalize_occupancy_context`, update every Misc-script importer of `sentinel_utils` so
nothing imports a now-moved or deleted symbol. The Phase 2 Explore sweeps should include
Misc Scripts — confirm they did.

**`sentinel_utils.py`**

**7e.** This file should be shared, low-logic plumbing only. After Phase 2:

- Confirm `parse_utility_budget` is gone and no caller still imports it from here.
- Confirm the band-label helpers (`house_age_to_band_label`, `appliance_age_to_band_label`,
  `gpm_to_flow_rate_label`) remain the single source of truth for both the rebuild and embedding
  — do not let banding logic be duplicated into the calculators.
- Remove any name-restating docstrings and obvious comments per Phase 1 rules.

**`model_config.py`**

**7f. Config correctness audit.**

- Confirm `CRITERION_WEIGHTS` (environmental 0.35 / energy_cost 0.30 / comfort 0.20 /
  practicality 0.15) matches `CLAUDE.md` and the README. If `CLAUDE.md`'s "35/30/20/15"
  label ordering and the dict's key order disagree in a potentially confusing way, **flag it
  for the user** rather than touching the weights.
- Confirm `TIE_BREAK_PRIORITY` is consistent with the environmental-first framing.
- Verify every `MODEL_SPECS` entry: `openrouter_id`, pricing label, `output_folder`, and
  `reasoning_effort` are internally consistent and the `reasoning_effort` values are ones the
  architectures actually honor via `get_reasoning_payload`.
  → DISPATCH (`general-purpose`, sonnet, medium): "Check whether these OpenRouter model IDs
  still exist and whether their reasoning-effort options are valid as written in `model_config.py`.
  Flag any that look stale. Do not suggest replacement models — just flag."
- Add in-text comments only where a constant's value is non-obvious; remove redundant ones.

---

## PHASE 8 — Paper integration (do this last)

Do not start this phase until Phases 1–7 are complete and all formulas/values are final.

**8a. Add missing formulas to the paper.**
Review `paper/paper_draft_working.tex`. For every important or semi-important formula
finalized in the calculators that is not already present, add it in the appropriate location
and subparagraph, matching the draft's existing style and formatting exactly. Scope includes:
HVAC/Appliance/Shower load, energy, emissions, comfort, and practicality formulas; value
functions; and the occupancy emissions weighting from Phase 3g.
→ DISPATCH (`Explore`, sonnet): "List which formulas from the three GT calculators already
appear in `paper/paper_draft_working.tex`, which do not, and which section each missing one
belongs in."
You write the LaTeX based on that map.

**8b. Placeholder notes** — add both in the methodology section, in the format
`[PLACEHOLDER NOTE] ...`:

- Remind the user to justify the scenario counts and splits
  (195 Test = 70 HVAC / 65 Appliance / 60 Shower; 90 RAG = 35 / 35 / 20).
- The weekend/holiday-not-modeled note (from Phase 5b).

**8c. Modifications log.**
Output the complete "Modifications Made" list accumulated throughout all phases as the final
section of your response, so the user can review every literature-driven value change in one place.

«RUN: /code-review high» on the full diff before declaring done.

---

## Execution order (dependency-aware)

1. **Phase 1** — standardization plan then apply. Unblocks consistent edits everywhere.
2. **Phase 2** — structural refactors (electricity_rate, parse_utility_budget,
   normalize_occupancy_context, budget/monthly_cost consolidation). Fixes structure before logic.
3. **Phase 4 citation subagents** — launch in parallel background while you work on Phase 3.
4. **Phase 3** — HVAC logic audit. Consumes Phase 4 output when the subagents return.
5. **Phase 5** — Appliance + Shower. Consumes Phase 4 citation output; applies VF propagation.
6. **Phase 6** — architecture bug fixes. Independent; can overlap with Phases 3–5.
7. **Phase 7** — Misc Scripts / sentinel / config. Consumes Phase 2 structural moves.
8. **Phase 8** — paper integration and modifications log. Always last.
