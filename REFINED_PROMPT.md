# Refined Working Prompt — GT Calculator / Architecture / Repo Audit & Refactor

> Paste this whole file into a fresh Claude Code (VSCode) chat. It is written so the
> main agent can dispatch subagents **itself** — every `→ DISPATCH` block is an
> explicit instruction to spawn a subagent with the given type/model/effort.
>
> **Slash commands** are written like `«RUN: /code-review high»`. They will NOT execute
> while this file is being authored or pasted; run them only when a step says to.

---

## 0. Setup — model, effort, and subagent policy

**Main agent**
- Model: **Opus 4.8** (`claude-opus-4-8`). This work is judgment-heavy (physics reasoning,
  deciding whether values are literature-correct, cross-file consistency) — keep it on Opus.
- Effort / thinking: **high** ("think hard") by default; bump to **"ultrathink"** for the
  comfort/practicality value-function audits and the degradation-relocation design.
- The main agent owns: all edits, all design decisions, all cross-calculator consistency,
  and final sign-off. Subagents never edit — they research and report back.

**Subagent roster** (dispatch via the `Agent` tool):
| Job | `subagent_type` | model | effort | runs in |
|-----|-----------------|-------|--------|---------|
| Citation / literature hunting in `cas-refs.bib` + web | `general-purpose` | sonnet | medium–high | parallel, background OK |
| Mapping / data verification (city→utility, rates, xlsx column existence) | `general-purpose` | sonnet | medium | parallel |
| Broad read-only "where is X used / does X still exist" sweeps | `Explore` | sonnet | "medium" or "very thorough" | parallel |
| Planning the big standardization refactor | `Plan` | opus | high | once, up front |

**Rules for every subagent dispatch**
- Subagents are **read-only researchers**. They return findings (file:line, the bib key,
  the proposed number + source). The **main agent applies** every change so consistency
  across the 3 calculators is preserved.
- Subagents may **search online whenever needed** (WebSearch/WebFetch) — explicitly allow this.
- Give each subagent the exact files to read and the exact output format you want back
  (e.g. "return a table: value | current justification | correct value | bib key or URL").
- Batch independent dispatches in **one message** so they run in parallel.

**Global rules (hold for the whole job)**
- **Never** combine system + user messages anywhere. (Leave message structure as-is.)
- Windows console is cp1252 — **no non-ASCII in any `print()`** that runs in the pipeline.
- **Never** `git commit` / `git push` — commits are the user's job.
- Respect the proxy/true pairs, sentinel `1928`, and the refresh order (BuildRAG always last)
  documented in `CLAUDE.md`. Any data/calculator change invalidates affected `*_results.xlsx`.
- When you change a number from what's currently in the code, **state the change explicitly
  in a running "Modifications Made" list** at the end, with the old value, new value, and source.
- After each phase that edits a calculator, run «RUN: /code-review medium» on the diff before moving on.

---

## PHASE 1 — Repo-wide standardization & organization (DO THIS FIRST)

> The user is explicit: this is a big refactor of many small changes, and doing it first
> makes every later edit easier to keep consistent. **No behavior changes in this phase** —
> pure organization. Do the 3 GT calculators as one group, then the architectures as a
> **separate** group.

**1a. Plan the refactor first.**
→ DISPATCH (Agent, `subagent_type="Plan"`, model=opus, effort=high):
"Read the three files in `Ground Truth Calculators/` and the three in `Architectures/`.
Produce a standardization plan covering, for each group separately (calculators vs
architectures): (1) a canonical function order — most shared/common methods live in the
lower half of each calculator, standardize that ordering; (2) canonical function names for
methods that do the same thing across files; (3) which methods should be `@staticmethod`
vs `@classmethod` vs instance methods — pick ONE convention and list every method that
currently violates it; (4) a list of import statements per calculator that differ and
should be unified. Return as a checklist of concrete renames/moves with file:line. Do NOT
edit anything."

**1b. Apply the standardization (main agent, think hard):**
- Standardize function order, names, and method-binding (`@staticmethod`/`@classmethod`/instance)
  across the 3 calculators **only where it does not change behavior of any one calculator**.
- Do the same, **separately**, for the 3 architectures.
- Standardize the import block across all 3 GT calculators (see also Phase 5 Appliance note —
  Appliance imports a different set from `sentinel_utils`; bring them in line).
- **Comment cleanup (whole repo):**
  - Delete every docstring that is just the function name restated
    (e.g. `def process_hvac_scenarios(...): """Process hvac scenarios."""`).
  - Remove obvious comments that restate code that's self-evident without them.
- This is the foundation — get consistency locked in before touching logic.

---

## PHASE 2 — Shared structural refactors (foundational; later logic depends on these)

> These change *where things live* and *what the shared helpers look like*. Do them before
> the per-calculator logic audits so the logic audits operate on the final structure.

**2a. `electricity_rate` constant — HIGH PRIORITY BUG.**
- In HVAC it is set to a flat `0.19` at ~line 617 (deep inside the code). That is the wrong
  place and likely the wrong value. Move it to a **named constant at the top of the calculator**.
- → DISPATCH (Agent, `general-purpose`, sonnet, medium): "What is a defensible residential
  electricity rate ($/kWh) for the utility/region these scenarios model? Check `cas-refs.bib`
  and the Appliance calculator's `utility_rates` for what the rest of the repo already uses,
  and confirm against a current public source online. Return the value + source." Then set the
  constant to the verified value (or the existing repo-consistent value) — do not leave a bare 0.19.

**2b. `parse_utility_budget` — move out of `sentinel_utils`, simplify, possibly delete.**
- → DISPATCH (Agent, `Explore`, sonnet, "medium"): "Across all xlsx in `Scenario Files/` and
  `Ground Truth/`, what is the actual stored type/format of the `utility_budget` column? Are
  there ever currency symbols/commas, or is it always a plain number? List every reader of that
  column." Based on the answer:
  - If budgets are always plain numerics, **inline** the parse (often just `float(...)`) and
    delete the standalone function. If a tiny helper is still warranted, put it **in each GT
    calculator** (not `sentinel_utils`) — simplify heavily.
  - Refactor every call site accordingly.

**2c. `normalize_occupancy_context` — keep or kill?**
- → DISPATCH (Agent, `Explore`, sonnet, "medium"): "Check every xlsx that feeds the calculators
  for an occupancy/occupancy_context column: what raw values actually appear? Then find every
  call to `normalize_occupancy_context` and `emissions_factor_for_occupancy` across the repo."
- If the stored values are already canonical (normalization is a no-op), **remove
  `normalize_occupancy_context`** and refactor every use. If it's still needed, keep it but
  document why. **Decide this before Phase 3's occupancy work** so you only touch those sites once.

**2d. `calculate_budget_penalty` ↔ `calculate_monthly_cost` consolidation.**
- → DISPATCH (Agent, `Explore`, sonnet, "medium"): "Find all call sites of
  `calculate_budget_penalty` and `calculate_monthly_cost` in all 3 GT calculators. Is
  `calculate_budget_penalty` actually called anywhere? Does it internally compute monthly cost?"
- Then: explain where `calculate_budget_penalty` is used. **If it is unused, identify where it
  *should* be used** (likely in `calculate_scenario_scores` / practicality) and wire it in or
  remove it. **If it is used and it recomputes monthly cost, consolidate** so `monthly_cost` is
  computed inside the larger function rather than as a separate call. Apply the resulting pattern
  to **all 3 calculators** (rule: structural fixes that generalize get applied to all three).

---

## PHASE 3 — HVAC calculator logic audit (`HVACGroundTruthCalculator.py`)

> Run the citation sweep (Phase 4) in parallel with this — it's read-only and independent.
> Main agent, think hard; use **ultrathink** for the comfort and degradation items.

**3a. Ventilation comment vs. code.** Lines ~86–88: the comment does not line up with
`ventilation_cfm` / `ventilation_load`. → DISPATCH a citation subagent (see Phase 4 format) to
pull the correct ventilation source; then fix the comment AND the code to agree, with the citation.

**3b. `calculate_comfort_score` — full audit (ultrathink).**
- Is the optimal **76 °F for comfort only** (not practicality) actually right? Verify against
  literature (ASHRAE 55 thermal comfort etc.).
  → DISPATCH (Agent, `general-purpose`, sonnet, high): "From `cas-refs.bib` (and online if
  needed) find the cited thermal-comfort optimum / comfortable indoor temp band for cooling.
  Return the number(s) + bib key. Flag if 76 °F is unsupported." Correct the number if wrong.
- Add in-text citations to **every line/value** in this function; analyze the whole function for
  correctness, not just the optimum.

**3c. `calculate_practicality_score` — first `if`.** The user changed it from `> 75` to its
current form. Evaluate whether the new logic is sound; explain and fix if not. Add a justification
comment in the **same style** as Shower line 138 (after that placeholder is filled — see 5c).

**3d. Degradation is in the wrong function (ultrathink design).** Degradation currently lives in
`calculate_energy_consumption`. It belongs in **practicality**. Determine whether to move it; if
yes, design and implement how practicality should incorporate degradation, and remove it from the
energy path. Keep the sentinel discipline (a failed sub-calc surfaces `1928`, never a neutral default).

**3e. `periods_per_month` default = 90.** Analyze `calculate_monthly_cost`'s periods-per-month.
Should it really be 90? Justify against how a scenario period maps to real time, and correct if wrong.

**3f. `calculate_budget_penalty`** — handled structurally in Phase 2d; here just confirm the HVAC
wiring is correct after consolidation.

**3g. `emissions_factor_for_occupancy` — reasoning audit.** Analyze the reasoning at the top of the
function. Validate the PJM marginal peak/off-peak framing (per `CLAUDE.md`) and the occupancy logic.
- **Occupied-sleep context returns "off"** — explain why; confirm that's intended or fix it.
- **Audit this occupancy calculation for accuracy** (the user flagged it specifically):
  ```
  if ctx.startswith("unoccupied_"):
      hours_match = re.search(r"(\d+)", ctx)
      hours_away = int(hours_match.group(1)) if hours_match else 8
      hours_away = max(0, min(hours_away, 24))
      if hours_away <= peak_h:
          return peak
      offpeak_hours = hours_away - peak_h
      return (peak_h * peak + offpeak_hours * off) / hours_away
  ```
  Verify the peak/off-peak weighting is physically correct; fix and cite if not.

**3h. `apply_value_function` JSON nesting.** Comfort and practicality JSON specs are nested *inside*
the environmental JSON. If they don't need to be, restructure (changing whatever other code reads
them) so they are top-level siblings. Apply the resulting cleaner schema consistently.

**3i. `calculate_scenario_scores` — `is_cooling` at the top.** The `is_cooling` calc sits above the
if/else and hardcodes 75 °F. Move the cooling/heating decision **into** the if/else, and use
`indoor_temp` (the actual setpoint) instead of a hardcoded 75.

**3j. `effective_temp` audit.** What is `effective_temp` used for, and is that use accurate? The
user is skeptical, especially of the hardcoded **±5**. Decide per use-site whether `effective_temp`
is justified; replace the hardcoded ±5 with a **derived** value (you propose the derivation, with a
citation) unless you can justify keeping it.

**3k. `ach` parameter removed.** The user removed the `ach` input param from the heating and cooling
load functions — it should just be **0.35**. Make `0.35` a named constant and update every call site
and any place that previously passed `ach`.

---

## PHASE 4 — Citation & source sweep across ALL 3 calculators (parallel, subagent-heavy)

> This is the big read-heavy job. Run it as parallel subagents while you do Phase 3. The main
> agent applies every citation/number change so the three calculators stay consistent.

**Rule:** every important formula step and every hardcoded value in all 3 GT calculators needs an
**in-text citation**. Anywhere a value is "justified" by a vague word like `"standard"`, a season
label (`# Winter minimum`), or no source at all, replace it with a real in-text citation. Where the
literature contradicts the current number, **change the number and log it** in "Modifications Made".

→ DISPATCH THREE subagents in one message (Agent, `general-purpose`, sonnet, medium–high,
`run_in_background: true`), one per calculator:

> "Read `Ground Truth Calculators/<X>GroundTruthCalculator.py` and `paper/cas-refs.bib`. For
> EVERY hardcoded constant and every formula step (loads, energy, emissions factors, comfort and
> practicality value functions, inlet/water temps, cycles, rates, reference ranges), return a row:
> `file:line | value or formula | current justification | matching cas-refs.bib key (or 'none in bib')
> | if none, a citable external source (URL) | is the current number supported? (yes/no + correct value)`.
> Pay special attention to comfort and practicality value functions — confirm there is a bib source
> for each VF shape/threshold; if not, find one or recommend a corrected VF. Search online when the
> bib lacks a source. Do not edit."

Then, main agent applies:
- In-text citations on every value/formula in all 3 calculators (HVAC, Appliance, Shower).
- **Comfort & practicality VF source comments** in all 3 (currently missing) — add the cited source;
  if no justification exists, find one or change the VF.
- Standardize the **citation comment style** repo-wide: as short as reasonably possible while
  conveying the full source, **in-text style only**. → DISPATCH (Agent, `Explore`, sonnet,
  "very thorough"): "List every source/citation comment across the repo and its current style, so
  it can be normalized to one short in-text format." Then normalize.

---

## PHASE 5 — Appliance & Shower calculator-specific logic

**Appliance (`ApplianceGroundTruthCalculator.py`)**

**5a. Imports** — already unified in Phase 1b; confirm Appliance no longer imports a divergent set
from `sentinel_utils`.

**5b. Weekend/holiday handling.**
- Read the header comments; the user distrusts lines ~29–31. → DISPATCH (Agent, `Explore`, sonnet,
  "medium"): "In the Appliance calculator, where (if anywhere) are weekends/holidays actually
  treated in rate-period / emissions-period logic? Quote the lines." Confirm whether the header
  claims match the implementation; fix the comments to match reality.
- Add to `paper/paper_draft_working.tex` a **placeholder** noting that weekend/holiday peak hours
  are **not currently modeled** (format: `[PLACEHOLDER NOTE] ...`), in the right methodology spot.

**5c. Verify `city_to_utility` mapping + `utility_rates`.**
→ DISPATCH (Agent, `general-purpose`, sonnet, medium): "Verify the `_normalize_city` /
`_utility_for_location` city→utility mapping and the `utility_rates` table in the Appliance
calculator against current public utility data online. Return: city | mapped utility | correct
utility? | rate used | correct rate + source." Apply corrections + cite.

**5d. `cycles_per_month` (default 30) realism.** Is `cycles_per_month` appropriate for **every**
appliance tested? → DISPATCH (Agent, `general-purpose`, sonnet, medium): "For each appliance type
in the Appliance scenarios (dishwasher, dryer, washer, etc.), find the cited/realistic average
cycles per month from `cas-refs.bib` or online. Return appliance | current value | realistic value
+ source." Refactor `cycles_per_month` (and any analogous per-appliance constants) to per-appliance
literature values and log the changes.

**Shower (`ShowerGroundTruthCalculator.py`)**

**5e. `reference_ranges` location.** Move the `reference_ranges` defined at the top into
`apply_value_function`, matching how HVAC/Appliance do it (per `CLAUDE.md`: 5th–95th pct, must match
the README table).

**5f. Justification comments that aren't real citations.** Lines like
`if outdoor_temp <= 32: return 45.0  # Winter minimum` / `# Summer maximum` are pseudo-justifications.
Replace with real in-text citations (covered by the Phase 4 Shower subagent output). If the literature
disagrees with the number, change it and log it.

**5g. `self` calls.** Replace `ShowerGroundTruthCalculator.<x>` calls **inside the class** with
`self.<x>`; import/bind `self` as needed within functions. (Reconcile with the Phase 1 static/instance
decision — if a method becomes instance-bound, the `self.` form is correct.)

**5h.** Use the (now-filled) Shower line-138 practicality justification comment as the **template**
for the practicality justification comments added to HVAC (3c) and Appliance.

**Cross-calculator VF propagation (all 3).**

**5i.** If the **HVAC value functions end up different** from what's there now (from Phase 3), apply
the corresponding changes across **all 3** calculators. **Before changing any VF**, first record how
the current VF shapes the score **distribution**, and what would have to change in the distribution /
reference ranges / README table if the VF changes. Document this analysis before editing.

---

## PHASE 6 — Architecture bug fixes

**6a. RAG `NameError` bug — `RAGDatabaseOptimized.py` (~lines 535–536).**
```
diagnostics['rag_retrieved_count'] = len(retrieved)
diagnostics['rag_context_length'] = len(rag_context)
```
`retrieved` and `rag_context` are never assigned in `score_alternative_with_rag`; line ~496 calls
`retrieve_similar_scenarios(...)` / `format_rag_context(...)` **inline** and passes the result
straight into `build_user_prompt_with_rag`, so these two lines raise `NameError` at runtime. Fix by
**capturing the retrieval results into locals first**, then using them for both the prompt and the
diagnostics (preferred — keeps the diagnostics meaningful), or remove the two lines if the diagnostics
aren't needed. Pick the capture-into-locals fix unless you find a reason not to.

**6b. Verbatim-alignment block — `RAGDatabaseOptimized.py` (~lines 521–533).** Evaluate whether this
block is removable (you, as the builder, decide — the user is unsure):
```
verbatim_alts = [scenario.get('alternative_1'), scenario.get('alternative_2'), scenario.get('alternative_3')]
...
for idx, alt_data in enumerate(alternatives_scores):
    alt_data['extracted_alternative'] = alt_data.get('alternative', '')
    if idx < len(verbatim_alts) and verbatim_alts[idx] not in (None, ''):
        alt_data['alternative'] = str(verbatim_alts[idx])
```
Trace whether `extracted_alternative` or the overwritten `alternative` is consumed downstream (output
sheet columns, metrics). If nothing depends on the verbatim overwrite, remove the block; otherwise keep
it and add a one-line comment explaining why it's needed.

**6c. Decimal precision (all architectures + anything rendering scores).** Every score rendered to the
user or to the LLM with one decimal (`.1f`) must become **two decimals (`.2f`)**. → DISPATCH (Agent,
`Explore`, sonnet, "very thorough"): "List every `:.1f` / `%.1f` / `round(x, 1)` that formats a SCORE
for display or for an LLM prompt across `Architectures/` and the GT calculators. Exclude latency/ms and
non-score numbers." Apply `.2f` to the score ones.

**6d.** Run «RUN: /code-review high» on the architecture diffs after 6a–6c.

---

## PHASE 7 — Misc Scripts, `sentinel_utils.py`, `model_config.py` (NEW SECTION)

> Same style as above. These are mostly general math/plumbing — lighter on physics judgment,
> heavier on consistency, dead-code, and "does this still match the data" checks. Main agent
> applies; use subagents for the cross-file sweeps.

**`Miscellaneous Scripts/`** — `BuildRAG.py`, `SyncRAGGroundTruth.py`, `CalculateMetrics.py`,
`SensitivityAnalysis.py`, `EntropyWeights.py`, `MERCECWeights.py`, `ImpliedWeights.py`.

**7a. Validation-only firewall.** Confirm the objective-weight scripts (`EntropyWeights`,
`MERCECWeights`, `ImpliedWeights`) and `SensitivityAnalysis` are **validation only** and are never
imported by any architecture or calculator, and never mutate `CRITERION_WEIGHTS` at runtime
(per `CLAUDE.md`). → DISPATCH (Agent, `Explore`, sonnet, "medium"): "Find every import of the four
weight/sensitivity scripts and every assignment to `CRITERION_WEIGHTS` repo-wide." Flag any violation;
do not silently 'fix' by changing weights — report it.

**7b. RAG schema-version lockstep.** Verify `BuildRAG.RAG_SCHEMA_VERSION ==
RAGDatabaseOptimized.EXPECTED_RAG_SCHEMA_VERSION`. If any Phase 2/4/5 change touched the embedding
string (`format_embedding_text`) or Chroma metadata, **bump BOTH** (a code-only embedding change still
needs a version bump — the source SHA only catches sheet edits). State whether a bump is required.

**7c. Citations/comments + comment cleanup.** Apply the same two repo-wide rules here: in-text citation
style for any literature-derived constant (e.g. emissions factors, percentile ranges in metrics),
delete name-restating docstrings, remove obvious comments. (Folds into Phase 1 + Phase 4 sweeps — just
make sure Misc Scripts are in scope for both subagent dispatches.)

**7d. Shared-helper consistency.** After Phase 2 moves `parse_utility_budget` out of `sentinel_utils`
and possibly drops `normalize_occupancy_context`, update **every** Misc-script importer of
`sentinel_utils` so nothing imports a now-moved/-deleted symbol. → covered by the Phase 2 Explore
sweeps — confirm Misc Scripts were included.

**`sentinel_utils.py`**

**7e.** This file should be **shared, low-logic plumbing only** (sentinel handling, atomic IO, band
labels, embedding text). After Phase 2:
- `parse_utility_budget` removed (moved/inlined). Confirm no caller still imports it from here.
- Confirm the band-label helpers (`house_age_to_band_label`, `appliance_age_to_band_label`,
  `gpm_to_flow_rate_label`) remain the **single source of truth** used by both rebuild and embedding —
  do not duplicate banding logic into the calculators.
- Remove any name-restating docstrings / obvious comments per Phase 1.

**`model_config.py`**

**7f. Audit the shared config for correctness/consistency** (no behavior change unless flagged):
- Confirm `CRITERION_WEIGHTS` here (env 0.35 / cost 0.30 / comfort 0.20 / practicality 0.15) matches
  what `CLAUDE.md` and the README state, and that `TIE_BREAK_PRIORITY` is consistent with the
  environmental-first framing. If `CLAUDE.md`'s "35/30/20/15" ordering and the dict disagree in
  labeling, **flag it for the user** rather than silently editing weights.
- Verify every `MODEL_SPECS` entry: `openrouter_id`, pricing label, `output_folder`, and
  `reasoning_effort` value are valid (e.g. `reasoning_effort` ∈ the set the architectures actually
  honor via `get_reasoning_payload`). → DISPATCH (Agent, `general-purpose`, sonnet, medium): "Confirm
  these OpenRouter model IDs and their reasoning-effort options exist as written; flag any that look
  stale." Report, don't auto-swap models.
- Add concise in-text comments only where a constant's value is non-obvious; remove redundant ones.

---

## PHASE 8 — Paper integration (LAST — depends on all final formulas/values)

> Do this only after Phases 1–7 land, so the formulas you write are final.

**8a. Add formulas to the paper.** Review the formulas in `paper/paper_draft_working.tex`. For **every
important/semi-important formula** finalized in the calculators that is **not already present**, add it
in the appropriate location and organization, with an appropriate subparagraph, **matching the existing
draft's style/format**. This includes any HVAC/Appliance/Shower load, energy, emissions, comfort,
practicality, and value-function formulas, plus the occupancy emissions weighting (3g).
→ DISPATCH (Agent, `Explore`, sonnet, "very thorough"): "List which calculator formulas already appear
in `paper/paper_draft_working.tex` and which do not, with the section each belongs in." Main agent writes
the LaTeX.

**8b. Placeholder notes (format `[PLACEHOLDER NOTE] ...`):**
- In methodology, a note reminding the user to **justify the scenario counts and splits**
  (195 Test = 70/65/60; 90 RAG = 35/35/20).
- The weekend/holiday-not-modeled note from 5b.

**8c. Modifications log.** Append the running **"Modifications Made"** list (every number you changed
from the original code, with old → new + source) to your final summary so the user can review all
literature-driven value changes in one place.

---

## Suggested execution order (dependency-aware, condensed)

1. **Phase 1** standardization (Plan subagent → apply) — unblocks consistent edits everywhere.
2. **Phase 2** structural shared refactors (electricity_rate, parse_utility_budget,
   normalize_occupancy_context decision, budget/monthly_cost consolidation) — fix structure before logic.
3. **Phase 4 citation subagents** launch **in parallel** (background) with **Phase 3** HVAC logic.
4. **Phase 5** Appliance + Shower logic (consumes Phase 4 citation output; applies VF propagation).
5. **Phase 6** architecture bug fixes (independent — can overlap with 3–5).
6. **Phase 7** Misc/sentinel/config (consumes Phase 2 moves; confirm schema-version bump).
7. **Phase 8** paper integration + placeholders + modifications log (last).

Run «RUN: /code-review high» on the full diff before declaring done.
