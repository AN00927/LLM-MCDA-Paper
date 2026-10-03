# CLAUDE.md — agent operating guide

Operational guide for working in this repo. The research narrative lives in
[README.md](README.md); this file is the "how the machine fits together + don't
break these" reference.

## ABSOLUTE RULE: minimal-diff editing on the paper

When resolving a TODO, fixing a flagged sentence, or making any other targeted
edit to `paper/paper_draft_v2.tex` or `paper/supplementary.tex`,
touch ONLY the exact span identified — the marked sentence/clause, or the
specific fact being corrected. Do NOT rewrite, rephrase, tighten, or "improve"
neighboring sentences in the same paragraph, even if they read awkwardly, even
if a rewrite would clearly read better, and even if you are already editing
that paragraph for an unrelated reason. If you believe a nearby sentence has a
problem, say so to the user and stop — do not fix it silently in the same
pass. This applies to every edit, not only ones explicitly marked with the
word-level-swap rules already in this file's "Paper editing conventions"
section — this is the umbrella rule those rules are examples of. Violating
this is the single most important thing to avoid in this repo.

## What this is

Benchmarks **three LLM-MCDA architectures** for household energy decisions against
a physics MAVT ground truth, over **195 Test scenarios** (70 HVAC / 65 Appliance /
60 Shower) with a **disjoint 90-scenario RAG corpus** (35 / 35 / 20). Three
decision types: HVAC setpoint, Appliance schedule time, Shower duration. Four
criteria: `energy_cost`, `environmental`, `comfort`, `practicality`.

## Running

- **Compilation happens in Overleaf, by the user** — not in this repo/sandbox. The
  agent should edit `.tex` source and let the user compile in Overleaf. A local
  `pdflatex` build may be used purely as a diagnostic step (e.g. Phase 0 audits)
  but its output is never the source of truth; the Overleaf-compiled PDF is.
- Set `OPENROUTER_API_KEY` in `.env`. Pick the model with `MODEL_KEY` and runs with
  `N_RUNS` in [src/llm_mcda/common/model_config.py](src/llm_mcda/common/model_config.py).
- Run an architecture with an explicit safe output directory, for example:
  `python src/llm_mcda/architectures/Direct_LLM_Scoring.py --output-dir results/scratch/direct-run`.
  The architecture CLIs also accept `LLM_MCDA_RUN_OUTPUT_DIR`. Runs are resume-aware
  (a complete per-run xlsx is skipped), so an existing safe destination may be reused.
- Migration-updated run, analysis, validation, and legacy writers require `--output-dir`
  or `LLM_MCDA_RUN_OUTPUT_DIR`; single-file writers use their documented `--output`
  option. Relative destinations resolve from the repository root. Missing or unsafe
  destinations stop with an error. Do not write into frozen `Analysis/`, `archive/`,
  `paper/`, `Output Files*/`, or frozen `workbooks/scenarios/`, `workbooks/ground_truth/`,
  and `workbooks/older_runs/` paths. Existing non-frozen destinations are allowed and
  are not automatically cleared.
- **Tracked outputs are a second, softer tier.** `workbooks/methodology/` and
  `results/methodology/` hold committed artifacts that the `weights` stage
  legitimately regenerates, so they are writable but only on explicit opt-in:
  either run through `run_paper_pipeline.py --allow-tracked-output-writes` (which
  propagates the opt-in to its subprocesses) or set
  `LLM_MCDA_ALLOW_TRACKED_OUTPUT_WRITES=1`. Invoking a weighting or diagnostics
  script directly with one of those paths stops with an error. Do not add these
  to the frozen list — freezing them would make the `weights` stage impossible
  to run. Prefer a scratch `--output-dir` unless you intend to refresh the
  committed copies.
- Calculator CLIs require `--output FILE`. For example:
  `python src/llm_mcda/calculators/HVACGroundTruthCalculator.py --output results/scratch/ground_truth_hvac.xlsx`.
  Keep the generated workbook separate from the frozen canonical ground-truth workbook.
- RAG requires a current Chroma index — run `python scripts/collection/build_rag_index.py` first.
- The paper pipeline skips its guarded `weights` and `sensitivity` stages by default because they can overwrite tracked or frozen outputs. Preview with `python scripts/paper_pipeline/run_paper_pipeline.py --list`. Run a guarded stage only after reviewing its destinations and opting in with `--allow-tracked-output-writes`; prefer a clean or disposable checkout. For example, CI runs only `weights` in its clean checkout. The `numbers` stage needs local-only manuscript inputs.

## Conventions that MUST hold

- **Sentinel `1928`** marks a failed/invalid score (int/float/`"1928"` all count).
  Use `src/llm_mcda/common/sentinel_utils.py` (`has_sentinel_scores` / `is_sentinel`); never let `1928` enter an
  average or a ranking. A failed sub-calc should surface as the sentinel, never a
  neutral default (e.g. `0.0` cost is a *perfect* score — a silent corruption).
- **Shared config in `src/llm_mcda/common/model_config.py`:** `CRITERION_WEIGHTS` (35/30/20/15),
  `TEMPERATURE`, `MAX_RETRIES=10`, `REQUEST_TIMEOUT=90`, `RETRY_BASE_DELAY`,
  `MAX_RETRY_BACKOFF`. All three `query_openrouter` implementations share this policy
  and report `latency_ms` measured around the successful POST only.
- **Every run must record a UTC collection timestamp.** Any new run output (per-run
  xlsx and `*_raw.jsonl`) needs a wall-clock timestamp per run. The shipped benchmark
  runs lack one, which is why the 2026-08-03 A_H alternative-ordering experiment
  needed a 3-run contemporaneous control arm (2,340 extra API calls) purely to rule
  out provider drift. With timestamps that control is optional, not mandatory.
- **Proxy/true pairs (intentional):** the LLM sees a homeowner-accessible label/estimate;
  the calculator gets the true engineering value. Never leak the true value to the LLM
  prompt, never let the calculator score the label directly.
  - `insulation` (Poor/Medium/Good) ⟷ `r_value` (tiers R-8–12 / R-13–18 / R-19–24)
  - `flow_rate` (low_flow/standard/high_flow) ⟷ `gpm`
  - `appliance_age` band ⟷ raw years (→ `kwh_per_cycle`)
  - LLM-Parameterized_Reference_Scoring's extraction prompt asks ONLY for the true/engineering params it must
    estimate; homeowner facts + alternatives come from the scenario sheet.
- **Banded labels** (`house_age`, `appliance_age`, `flow_rate`) are produced by the
  single-source helpers in `src/llm_mcda/common/sentinel_utils.py` (`*_to_band_label`, `gpm_to_flow_rate_label`)
  and used by BOTH the rebuild (Test sheet) and `format_embedding_text` (RAG embedding).
  RAG/GT sheets keep RAW numeric values; banding is applied at embed/display time so
  query↔index strings stay byte-identical. Do not store bands in RAG/GT sheets.
- **Environmental impact:** Shower = water volume (gallons = GPM × duration); HVAC &
  Appliance = lbs CO₂ via **PJM marginal** factors (peak 1.041 / off-peak 0.976), not
  eGRID average. These definitions prevent collinearity with energy cost — do not revert.
- **Reference ranges** in each calculator's `apply_value_function` are 5th–95th
  percentiles of the actual scenario distributions (must match the README table), not
  theoretical extremes.
- **Objective weight scripts** (`EntropyWeights`, `merec_weights`, `implied_weights`) are
  VALIDATION only — they triangulate the 35/30/20/15 weights. No architecture or
  calculator may import them or change weights at runtime.
- **RAG schema version** is in lockstep: `scripts/collection/build_rag_index.py:RAG_SCHEMA_VERSION` ==
  `src/llm_mcda/architectures/Example-Guided_LLM_Scoring.py:EXPECTED_RAG_SCHEMA_VERSION` (currently **4**). Bump BOTH on any
  change to the embedding string or Chroma metadata; the source-file SHA only catches
  sheet edits, not embedding-code changes — so a code-only change needs a version bump.

## Refresh workflows (order matters — build_rag_index is always LAST)

Rebuilding the Chroma index (`scripts/collection/build_rag_index.py`) is always the
final step of any refresh chain below.

- **Changed a ground-truth calculator** → run that calculator (regenerates
  a workbook at an explicit safe `--output` path) → run
  `scripts/collection/sync_rag_ground_truth_scores.py --dry-run` to validate the frozen
  RAG and ground-truth inputs. A write pass requires a separate safe `--output-dir` for
  refreshed workbook copies; it never overwrites frozen RAG inputs. These scratch outputs
  are not promoted into the frozen canonical input tree by this workflow.
- **Scenario refresh is currently frozen.** The repository masters in `workbooks/scenarios/`
  are historical inputs and must not be edited in place. For a scratch-only audit, copy the
  standalone masters (`HVACScenarios.xlsx`, `ApplianceScenarios.xlsx`, and
  `ShowerScenarios.xlsx`) and the RAG sheets needed to carry scores to a separate working
  directory and run
  `python scripts/collection/scenarios/build_scenario_workbooks.py --masters-dir path/to/safe-input-copy --rag-scores-dir path/to/safe-input-copy --output-dir results/scratch/scenarios`.
  Without `--output-dir`, the builder creates a fresh temporary output directory. It audits
  the derived workbooks and never modifies the standalone masters. `--in-place` is refused
  for the frozen repository scenario workbooks; do not bypass that guard. The current
  freeze has no promotion step from scratch outputs into the canonical workbooks, so a
  canonical data refresh must wait until the freeze is explicitly changed and the
  input/output workflow is reviewed.
- Any data change invalidates prior `*_results.xlsx` for the affected type — those
  need fresh architecture runs.

## Gotchas

- **Windows console is cp1252** — never `print()` non-ASCII (`✓`/`✗`/em-dash) from code
  that runs in the pipeline; it raises `UnicodeEncodeError`. Use plain ASCII.
- **xlsx provenance:** derived Test/RAG scenario data should retain auditable source lineage;
  column types are documented in [XLSX_Schema_Map.md](XLSX_Schema_Map.md).
- **NEVER commit or push without explicit user permission** — `git commit`/`git push` are strictly forbidden unless the user directly instructs it.
- **Unexpected git state (a commit, branch, or file change you don't recall making) is not automatically a problem.** The user works in this repo concurrently (IDE source control, other sessions, autosave-triggered commits). If you find something you didn't expect: check whether a subagent you dispatched did it (subagent reports state explicitly whether they ran git commands); if a subagent didn't do it, assume it was the user and move on — don't investigate further, don't revert it, don't treat it as an anomaly to flag repeatedly. A one-line mention that you noticed it is enough if it's directly relevant to the task at hand.
- The standalone HVAC, Appliance, and Shower master workbooks in `workbooks/scenarios/`
  are the current source inputs for Test/RAG derivation. `data/scenarios/rag_membership.json`
  fixes the Test/RAG split; the scratch-safe builder audits that membership against the
  master rows before writing derived workbooks.

## Paper editing conventions (`paper/paper_draft_v2.tex`)

The manuscript sources and selected figure assets are local-only; they are preserved under the ignored local manuscript/documentation directories and are not part of a public clone.


### Float placement (tables and figures)

LaTeX's default float algorithm pushes `[htbp]` tables/figures to the top of
the page or even past the text that references them. This document already has
`\FloatBarrier` (from `placeins`) before every `\subsection` and `\section`
boundary in Results and Discussion. Rules:

- **Every `\subsection` and `\section` in Results/Discussion must be preceded by
  `\FloatBarrier`.** This corals floats within their subsection so they cannot
  jump ahead of the next subsection's introducing text.
- **Preamble float fraction tuning is load-bearing.** Do not remove:
  ```latex
  \renewcommand{\floatpagefraction}{0.7}
  \renewcommand{\textfraction}{0.15}
  \renewcommand{\topfraction}{0.85}
  \renewcommand{\bottomfraction}{0.65}
  ```
- **If you add a new table or figure**, place it after the text that references
  it and before the next `\FloatBarrier`. If it must appear before its
  reference, use `[H]` (hard placement) — but prefer `\FloatBarrier` spacing.
- **If you add a new `\subsection`** in Results or Discussion, add
  `\FloatBarrier` immediately before it.
- **No fully pooled tables without user approval.** When presenting metrics
  across multiple models, do not pool all data into a single aggregate table
  without asking the user first. Show per-model breakdowns or at minimum
  strongest+weakest model.

### Reading the user's inline TODOs

A `%TODO`/`[TODO: ...]` marker placed **in the middle of a paragraph refers to the
text immediately before it**, not to what follows. A marker on its own line
between paragraphs refers to the section or paragraph that came right before it.
Resolve the TODO against that antecedent, not against the whole subsection.

Edits here follow the ABSOLUTE RULE at the top of this file: prefer word-level
swaps, touch no sentence but the target, and when in doubt do less.

### Appendix references

When referring to an appendix in the text, use **only** `\ref{APPENDIXNAME}` — do not
prepend "appendix" before it. LaTeX will automatically resolve the reference to the
appendix label; the reader's context already makes clear it's an appendix.

## Subagent usage

- **For resource/context-heavy tasks** (large multi-file edits, long document
  audits, mechanical relocation work), delegate to well-scoped subagents rather
  than doing it inline — use a lighter model (sonnet, thinking off) with a
  precise, self-contained prompt rather than a large reasoning-heavy model with a
  vague one. A well-defined prompt on a cheaper model outperforms a vague prompt
  on an expensive one for mechanical/well-specified work.
  Haiku is also acceptable for extremely boilerplate/boring tasks when it has a strong prompt.
