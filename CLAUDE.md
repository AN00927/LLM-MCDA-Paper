# CLAUDE.md — agent operating guide

Operational guide for working in this repo. The research narrative lives in
[README.md](README.md); this file is the "how the machine fits together + don't
break these" reference.

## What this is

Benchmarks **three LLM-MCDA architectures** for household energy decisions against
a physics MAVT ground truth, over **195 Test scenarios** (70 HVAC / 65 Appliance /
60 Shower) with a **disjoint 90-scenario RAG corpus** (35 / 35 / 20). Three
decision types: HVAC setpoint, Appliance schedule time, Shower duration. Four
criteria: `energy_cost`, `environmental`, `comfort`, `practicality`.

## Layout

- `Architectures/` — `Direct_LLM_Prompting.py`, `Example-Guided_LLM_Scoring.py`, `LLM-Parameterized_Reference_Scoring.py`. Each
  runs the benchmark via `run_multi_and_aggregate` and writes to the model's output
  folder.
- `Ground Truth Calculators/` — `{HVAC,Appliance,Shower}GroundTruthCalculator.py`. The
  deterministic physics. LLM-Parameterized_Reference_Scoring imports these at runtime; run a file directly to
  regenerate its `Ground Truth/ground_truth_*.xlsx`.
- `Scenario Files/` — masters live in `ConsolidatedforSimaltaneousediting.xlsx`;
  `rebuild_consolidated.py` derives `TestScenarios.xlsx` + the 3 `*RAGScenarios.xlsx`
  from it (audited, deterministic, backs up first).
- `Miscellaneous Scripts/` — `BuildRAG.py` (Chroma index), `SyncRAGGroundTruth.py`
  (refresh RAG scores from GT), `CalculateMetrics.py`, weight scripts,
  `run_benchmarks.py`.
- `paper_pipeline/` — `run_all.py` (master pipeline), `generate_figures.py`,
  `generate_numbers_master.py`, per-run metrics + LaTeX snippet generators.
- `model_config.py`, `sentinel_utils.py` — shared config + shared utilities.
- `docs/` — `CODEBASE_GUIDE.md`, `PROVENANCE_AUDIT_PROMPT.md`, `REVISION_PLAN.md`.
- `chroma_rag_db/` — built RAG vector index (gitignored).

## Running

- Set `OPENROUTER_API_KEY` in `.env`. Pick the model with `MODEL_KEY` and runs with
  `N_RUNS` in [model_config.py](model_config.py); output routes to that model's folder.
- Run an architecture: `python Architectures/Direct_LLM_Prompting.py` (resp. RAG / LLM-Parameterized_Reference_Scoring).
  Runs are resume-aware (a complete per-run xlsx is skipped).
- RAG requires a current Chroma index — run `BuildRAG.py` first.

## Conventions that MUST hold

- **Sentinel `1928`** marks a failed/invalid score (int/float/`"1928"` all count).
  Use `sentinel_utils.has_sentinel_scores` / `is_sentinel`; never let `1928` enter an
  average or a ranking. A failed sub-calc should surface as the sentinel, never a
  neutral default (e.g. `0.0` cost is a *perfect* score — a silent corruption).
- **Shared config in `model_config.py`:** `CRITERION_WEIGHTS` (35/30/20/15),
  `TEMPERATURE`, `MAX_RETRIES=10`, `REQUEST_TIMEOUT=90`, `RETRY_BASE_DELAY`,
  `MAX_RETRY_BACKOFF`. All three `query_openrouter` implementations share this policy
  and report `latency_ms` measured around the successful POST only.
- **Proxy/true pairs (intentional):** the LLM sees a homeowner-accessible label/estimate;
  the calculator gets the true engineering value. Never leak the true value to the LLM
  prompt, never let the calculator score the label directly.
  - `insulation` (Poor/Medium/Good) ⟷ `r_value` (R-11/13/19)
  - `flow_rate` (low_flow/standard/high_flow) ⟷ `gpm`
  - `appliance_age` band ⟷ raw years (→ `kwh_per_cycle`)
  - LLM-Parameterized_Reference_Scoring's extraction prompt asks ONLY for the true/engineering params it must
    estimate; homeowner facts + alternatives come from the scenario sheet.
- **Banded labels** (`house_age`, `appliance_age`, `flow_rate`) are produced by the
  single-source helpers in `sentinel_utils` (`*_to_band_label`, `gpm_to_flow_rate_label`)
  and used by BOTH the rebuild (Test sheet) and `format_embedding_text` (RAG embedding).
  RAG/GT sheets keep RAW numeric values; banding is applied at embed/display time so
  query↔index strings stay byte-identical. Do not store bands in RAG/GT sheets.
- **Environmental impact:** Shower = water volume (gallons = GPM × duration); HVAC &
  Appliance = lbs CO₂ via **PJM marginal** factors (peak 1.041 / off-peak 0.976), not
  eGRID average. These definitions prevent collinearity with energy cost — do not revert.
- **Reference ranges** in each calculator's `apply_value_function` are 5th–95th
  percentiles of the actual scenario distributions (must match the README table), not
  theoretical extremes.
- **Objective weight scripts** (`EntropyWeights`, `MERCECWeights`, `ImpliedWeights`) are
  VALIDATION only — they triangulate the 35/30/20/15 weights. No architecture or
  calculator may import them or change weights at runtime.
- **RAG schema version** is in lockstep: `BuildRAG.RAG_SCHEMA_VERSION` ==
  `Example-Guided_LLM_Scoring.py.EXPECTED_RAG_SCHEMA_VERSION` (currently **4**). Bump BOTH on any
  change to the embedding string or Chroma metadata; the source-file SHA only catches
  sheet edits, not embedding-code changes — so a code-only change needs a version bump.

## Refresh workflows (order matters — BuildRAG is always LAST)

- **Changed a ground-truth calculator** → run that calculator (regenerates
  `ground_truth_*.xlsx`) → `SyncRAGGroundTruth.py` (refreshes RAG score columns;
  matches RAG↔GT by descriptor signature, not scenario_id; time-aware on appliance
  alternatives) → `BuildRAG.py`.
- **Changed scenario data / banding** → `Scenario Files/rebuild_consolidated.py`
  (re-derives Test + RAG, audits, exports standalone files) → `BuildRAG.py`.
  Because the rebuild re-exports the RAG sheets, the Chroma source-hash only matches
  if BuildRAG runs after it.
- Any data change invalidates prior `*_results.xlsx` for the affected type — those
  need fresh architecture runs.

## Gotchas

- **Windows console is cp1252** — never `print()` non-ASCII (`✓`/`✗`/em-dash) from code
  that runs in the pipeline; it raises `UnicodeEncodeError`. Use plain ASCII.
- **xlsx provenance:** every Test/RAG row must trace to a master under the transform
  rules in [PROVENANCE_AUDIT_PROMPT.md](PROVENANCE_AUDIT_PROMPT.md); column types are
  documented in [XLSX_Schema_Map.md](XLSX_Schema_Map.md).
- **NEVER commit or push without explicit user permission** — `git commit`/`git push` are strictly forbidden unless the user directly instructs it.
- **Superpowers planning artifacts are ephemeral.** Any planning, tracking, or spec documents created by superpowers skills (brainstorming specs, implementation plans, design docs under `docs/superpowers/`) must be added to `.gitignore` after creation. They are working artifacts, not deliverables.
- Standalone master files (`*Scenarios.xlsx`) can drift from the consolidated workbook;
  the consolidated workbook is the source of truth for Test/RAG derivation.
- **Never edit the Introduction, Literature Review, or initial Methodology sections (up to and including the MAVT framework design, §2.2) without explicit user consultation.** These sections carry the paper's research narrative and have been carefully reviewed; changes risk breaking argumentative flow.

## Paper editing conventions (`paper/paper_draft_working.tex`)

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
- After any float layout change, **recompile twice** (pdflatex → bibtex →
  pdflatex × 2) and visually verify tables sit after their references.
- **No fully pooled tables without user approval.** When presenting metrics
  across multiple models, do not pool all data into a single aggregate table
  without asking the user first. Show per-model breakdowns or at minimum
  strongest+weakest model.

When editing text in this file, change the absolute minimum required to
satisfy the request:

1. **Prefer word-level swaps over sentence rewrites.** If a single word,
   number, or phrase needs changing, change only that token — do not
   rephrase the surrounding sentence.
2. **Do not reword for clarity.** Even if nearby prose could be improved,
   leave it as-is unless the task explicitly requires it.
3. **Do not reorder or restructure.** Keep sentences, paragraphs, and
   sections in their original form. Move content only when the edit
   specifically demands it.
4. **Scope edits to the target.** If fixing one sentence, touch no other
   sentence — not for flow, not for consistency, not for style.
5. **When in doubt, do less.** Every character changed beyond what the
   task requires is excess.

## Communication conventions

- **"Explain X to me" means explain in conversation.** When the user asks you to
  explain something, they want a direct answer in the chat — not a plan item, not
  a file edit, not a todo. Do NOT add explanatory requests to task lists or plan
  documents. Just answer.
