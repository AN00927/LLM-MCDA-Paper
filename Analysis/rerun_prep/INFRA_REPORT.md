# P3 infra report: model_config, ablation-script logging, B60 tie-break, new pipeline scripts

Scope: `paper/pass5/RERUN_PREP_PLAN.md` section P3. No git command was run (no
commit/push/checkout/stash/reset; one existing script this report discusses,
`paper_pipeline/reconcile_recollection_diagnostics.py`, calls `git show` at
runtime to read historical file content -- that call was not executed by me).
No paid API call was made. Only `GET /api/v1/models` and
`GET /api/v1/models/{id}/endpoints` were used, both keyless.

## 1. Gemini 3.8 Flash

### 1.1 Model ID and evidence

`GET https://openrouter.ai/api/v1/models` lists `google/gemini-3.8-flash`
(canonical slug `google/gemini-3.8-flash-20260902`), alongside a `:batch`
variant. Its top-level `supported_parameters` includes both `temperature` and
`reasoning`/`reasoning_effort`:

```
"supported_parameters": ["include_reasoning", "max_tokens", "reasoning",
  "reasoning_effort", "response_format", "seed", "stop", "structured_outputs",
  "temperature", "tool_choice", "tools", "top_p"]
"pricing": {"prompt": "0.00000075", "completion": "0.00000375", ...}
```

$0.75/M prompt, $3.75/M completion -- matches the plan's projected price
exactly, and is the number the plan's $24-30 rerun cost estimate assumes.

`GET https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints`
lists 6 endpoints (Google AI Studio and Google/Vertex, each at standard/flex/
priority pricing tiers). All 6 list `reasoning` and `reasoning_effort`; the 3
Google AI Studio endpoints additionally list `temperature` (the 3 Vertex
endpoints omit `temperature` from their own `supported_parameters` but still
accept `reasoning`). The base (non-flex, non-priority) tier's price
($0.75/$3.75) is the one used in the label below.

### 1.2 `:exacto` -- kept, not dropped

None of the 6 endpoints for `google/gemini-3.8-flash` has `exacto` in its
`tag` (tags seen: `google-ai-studio[/flex|/priority]`,
`google-vertex/global[/flex|/priority]`). This is not evidence against
`:exacto`, though: the same two GET endpoints show **zero** `exacto`-tagged
rows for any of the four *currently shipped* model IDs either --
`google/gemini-3.5-flash`, `openai/gpt-oss-20b`, `qwen/qwen3.5-9b`, and
`deepseek/deepseek-v4-flash` (checked all four) all have provider lists with
ordinary provider tags (Google AI Studio/Vertex, Darkbloom, AkashML, DekaLLM,
CoreWeave, DeepInfra, Parasail, Novita, SiliconFlow, Amazon Bedrock, Groq,
etc.) and none named `exacto`. `:exacto` is evidently a request-time routing
suffix OpenRouter resolves internally (comparable to `:floor`/`:nitro`), not
a provider enumerated by `/endpoints` -- so its absence from the endpoints
list is expected and uninformative for every model in `MODEL_SPECS`, old and
new alike. Per the instruction ("keep `:exacto` unless evidence says it's
unsupported -- then report, don't guess"), I found no such evidence, so
`google/gemini-3.8-flash:exacto` was kept. **Open issue:** this is inference
from absence of evidence, not a positive confirmation that OpenRouter accepts
the suffix on this specific new model; the plan's P5 smoke test (one real
call) is the actual check, and should be watched for an `:exacto`-specific
error.

### 1.3 `model_config.py` change

```python
"gemini": {
    "label": "Input Price: $0.75/M, Output Price: $3.75/M",
    "openrouter_id": "google/gemini-3.8-flash:exacto",
    "output_folder": "Output Files Gemini 3.8 Flash",
    "reasoning_effort": "minimal",
},
```

Only the `gemini` spec changed. `reasoning_effort` stays `"minimal"` --
`google/gemini-3.8-flash` lists `reasoning_effort` among its supported
parameters, same as the outgoing 3.5 model, so nothing here needed to change;
this is not a new confirmation that OpenRouter validates `"minimal"` as a
value against Gemini specifically (that string is generic across `MODEL_SPECS`
and passed straight through by `get_reasoning_payload`), only that the
parameter itself is accepted.

### 1.4 gptoss and qwen price labels (follow-up: labels updated, IDs/settings untouched)

Originally left alone (out of scope for the first pass) and flagged as stale
in this section. A follow-up instruction asked for the two stale labels to be
corrected, IDs and `reasoning_effort` untouched. Current listed prices
(2026-09-25):

| Model key | `openrouter_id` (unchanged) | Current price (prompt/completion per M) | Label before | Label now |
|---|---|---|---|---|
| gptoss | `openai/gpt-oss-20b:exacto` | $0.018 / $0.09 | `input Price: $0.029/M, Output Price: $0.14/M` | `input Price: $0.018/M, Output Price: $0.09/M` |
| qwen | `qwen/qwen3.5-9b:exacto` | $0.10 / $0.15 | matched already | unchanged |

Only the `label` string changed for `gptoss`; `qwen`'s already matched
current pricing and was left as-is. Neither model's `openrouter_id` or
`reasoning_effort` was touched. (`deepseek`'s label was also stale at this
point -- see section 1.5, where its whole spec changed for a different
reason before the label fix would have mattered on its own.)

**Observed, not made by me:** between this report's first version and this
update, `gptoss`'s and `gemini`'s `openrouter_id` suffix changed on disk from
`:exacto` to `:floor` (`deepseek`'s stayed `:exacto`, per this task's explicit
instruction below). I did not make that change and was told to treat it as
the current, deliberate state rather than reverting it. Flagging it here
because it affects this report's own "`:exacto`, kept" reasoning in section
1.2 and 1.5 for the two models where it no longer applies -- if `:floor` was
chosen because `:exacto` isn't real routing, that reasoning would also apply
to `deepseek`'s `:exacto`, which this task set independently afterward. Not
resolved by me; flagged for the author/coordinator to reconcile.

### 1.5 DeepSeek V4 Flash -> DeepSeek V4.1 Flash (follow-up lineup change)

Second follow-up: the author replaced DeepSeek V4 Flash with DeepSeek V4.1
Flash, key stays `deepseek`.

**Evidence**, same two keyless GET endpoints as section 1.1, no completion
calls:

- `GET /api/v1/models` lists `deepseek/deepseek-v4.1-flash` (and a `:batch`
  variant; not the same slug as the `deepseek/deepseek-v4-flash-*` family
  already in the list, which are the outgoing model and unrelated variants).
  Pricing: `"prompt": "0.00000014", "completion": "0.00000042"` -- $0.14/M
  input, $0.42/M output, matching the author's stated price exactly.
  `supported_parameters` includes `reasoning` and `reasoning_effort` (also
  `temperature`, `tool_choice`, `tools`, and others), so reasoning control is
  supported -- kept `reasoning_effort: "none"` unchanged, as instructed.
- `GET /api/v1/models/deepseek/deepseek-v4.1-flash/endpoints` lists 28
  provider endpoints (InferenceNet, Morph, DeepInfra, Fireworks, Together,
  DeepSeek itself, and 22 others); none is tagged `exacto`, the same pattern
  as every other model checked in this task (section 1.2) -- consistent with
  `:exacto` being a request-time routing suffix OpenRouter resolves
  internally rather than an enumerable provider, so this is not evidence
  against it either. Kept `:exacto`, per the instruction to apply the same
  reasoning as Gemini's.

**`model_config.py` change:**

```python
"deepseek": {
    "label": "Input Price: $0.14/M, Output Price: $0.42/M",
    "openrouter_id": "deepseek/deepseek-v4.1-flash:exacto",
    "output_folder": "Output Files DeepSeek V4.1 Flash",
    "reasoning_effort": "none",
},
```

**Hardcoded "DeepSeek V4 Flash" strings**, updated the same way as Gemini's
(derived from `MODEL_SPECS["deepseek"]["output_folder"]`, not a new hardcoded
string), in the same four files:

- `paper_pipeline/compute_dispersion_diagnostics.py`: `MODEL_LABELS["deepseek"]`.
- `paper_pipeline/duplication_rate_analysis.py`: the `deepseek` tuple in
  `MODEL_FOLDERS`.
- `paper_pipeline/generate_paper_figures.py`: `MODEL_LABELS["deepseek"]`.
- `paper_pipeline/reconcile_recollection_diagnostics.py`: the `deepseek`
  entry in `FOLDERS`. Same caveat as Gemini's in section 2: this one-time
  historical script will no-op for DeepSeek until something is collected
  under the new folder name.

`grep -rl "DeepSeek V4 Flash\|deepseek-v4-flash" --include=*.py .` (excluding
`archive/` and `Analysis/pass5/`) found the same single out-of-scope file as
the Gemini search: `Miscellaneous Scripts/legacy/aggregate_position_bias_results.py`
(legacy, not in my file list, not registered in the pipeline). Left untouched.

**Consequence for the two new pipeline scripts**: `compute_tie_rates.py` and
`compute_regret.py` resolve `deepseek`'s output folder through `model_config`,
so as soon as `model_config.py` points `deepseek` at
`Output Files DeepSeek V4.1 Flash`, they can no longer find the *existing*
`Output Files DeepSeek V4 Flash` run files under the `deepseek` key (that
folder is untouched on disk; only the config pointer moved). Verified this is
a silent, non-crashing no-result for `deepseek` (an empty run list, not an
exception) by rerunning both scripts after the config change: `gptoss` and
`qwen` still reproduce correctly, `deepseek` contributes zero rows. This is
the expected, correct state until the actual DeepSeek V4.1 Flash rerun is
collected -- the same situation Gemini was already in from section 1's change.

## 2. Gemini label/folder strings in `paper_pipeline/*`

Edited only the `gemini` entry in each of the four named files, pulling from
`MODEL_SPECS["gemini"]["output_folder"]` rather than hardcoding a new
"Gemini 3.8 Flash" string, per the file list's "(Gemini label/folder strings
only)" note:

- `paper_pipeline/compute_dispersion_diagnostics.py`: `MODEL_LABELS["gemini"]`
  now `MODEL_SPECS["gemini"]["output_folder"].replace("Output Files ", "")`.
- `paper_pipeline/duplication_rate_analysis.py`: added
  `from model_config import MODEL_SPECS`; the Gemini tuple in `MODEL_FOLDERS`
  now derives both the label and the folder path from `MODEL_SPECS["gemini"]`.
- `paper_pipeline/generate_paper_figures.py`: added the `model_config` import
  (this file previously imported nothing project-local); `MODEL_LABELS["gemini"]`
  now derived the same way.
- `paper_pipeline/reconcile_recollection_diagnostics.py`: the `FOLDERS` list's
  Gemini entry now reads `MODEL_SPECS["gemini"]["output_folder"]`. **Caveat**:
  this script's job is a one-time historical reconciliation tied to a specific
  already-collected, already-spliced Gemini 3.5 Shower re-collection (it reads
  both the live xlsx *and* the pre-splice git-history copy from the same
  folder path). It is not registered in `run_paper_pipeline.py` and was
  presumably already run to completion against the 3.5 data. Repointing its
  Gemini folder to `Output Files Gemini 3.8 Flash` means it will find no
  matching diagnostics files there yet (nothing has been collected under that
  folder) and silently no-op for Gemini on its next invocation, which is
  correct once the old 3.5 folder is archived (P4 step 8: "clear the live
  output folders"). If anyone needs to re-run this specific reconciliation
  against the *old* 3.5 data after that archive step, they need the snapshot
  copy under `LLM-MCDA-Paper-snapshots\2026-09-25_pre_rerun\`, not the live
  tree.

### 2.1 Other "3.5 Flash" / "gemini-3.5" references found, not edited (outside my file list)

`grep -rl "3\.5 Flash\|gemini-3\.5" --include=*.py .` (excluding `archive/`
and `Analysis/pass5/`) found one file outside my scope:

- `Miscellaneous Scripts/legacy/aggregate_position_bias_results.py`

Left untouched -- it is in `legacy/`, not in my file list, and not registered
in the pipeline.

## 3. Logging (`collected_utc` + `*_raw.jsonl` per-call archive)

`sentinel_utils.RawCallLog`'s own docstring already flags the exact gap this
task asked about: "Importing an architecture module and driving run_scenario
yourself -- which the ablation and position-bias scripts do -- archives
nothing and behaves exactly as it did before." Checked each of the three
scripts against that:

| Script | Before | After |
|---|---|---|
| `run_prompt_ablation_experiments.py` | Own `query_openrouter`; no `RawCallLog` import; no `collected_utc` anywhere. | Added a module-level `RAW_LOG = RawCallLog()` + `_raw_log_lock` (workers run under a `ThreadPoolExecutor`, so `.record()` calls are serialised by a lock and `scenario_id` is passed explicitly per call rather than via `.set_scenario()`, which is not thread-safe). `RAW_LOG.start()`/`.stop()` wrap each cell in `run_cell()`, keyed to `<cell>_raw.jsonl` next to that cell's xlsx. `collected_utc` (one timestamp per cell, captured at the top of `run_cell()`) added to every per-scenario record and to `_failed_record()`. |
| `run_rag_ablation_experiments.py` | Own `query_openrouter`; no `RawCallLog` import; no `collected_utc`. | Same `RAW_LOG`/lock pattern; `.record()` added in `llm_prediction()` (the only function that calls the API) right after each successful `query_openrouter()` call. `RAW_LOG.start()`/`.stop()` wrap the single `build_result_rows()` call in `run()`, writing `rag_ablation_results_raw.jsonl` next to `rag_ablation_results.xlsx`. `collected_utc` (one timestamp for the whole collection -- this script has no per-run/`--runs` concept) added as a column on `rows_df`. |
| `run_position_bias_control.py` | Drives the real `Direct_LLM_Scoring.py` module's `run_scenario()` directly, never calling that module's own `RAW_LOG.start()`. Serial loop (no threading), so no lock is needed. | Reuses the loaded module's own `RAW_LOG` object (`mod.RAW_LOG.start(...)`/`.set_scenario(...)`/`.stop()`) rather than a re-implementation -- this is the case the plan's "reusing the architectures' RAW_LOG" instruction describes most literally. Writes `<arch>_<suffix>_run_NN_raw.jsonl` next to that run's xlsx. `collected_utc` added to `RESULT_COLUMNS` and stamped onto every row from `normalize_result()`'s output before it is checkpointed. |

Resume behavior: `RawCallLog.start()` does not truncate; a resumed/partially-
complete run appends further records to whatever jsonl already exists, exactly
as the shipped architectures already do (per its own docstring).

### 3.1 Follow-up: retry-exhausted calls, fixed in all three scripts

Original open issue: `run_rag_ablation_experiments.py`'s own `query_openrouter()`
*raises* `RuntimeError` on full retry exhaustion rather than returning
`(None, diag)`, so the `RAW_LOG.record()` call after it (inside the `try`
block in `llm_prediction()`) was never reached for that call -- a fully
exhausted call left only a `failed_calls` counter increment, no raw-log trace.

Fixed at the call site in each of the three scripts, without touching
`Architectures/*.py` or `query_openrouter` itself in any file:

- **`run_rag_ablation_experiments.py`** (the actual gap): the
  `query_openrouter(messages, model_id)` call inside `llm_prediction()` is now
  wrapped in its own inner `try/except`. On the raised `RuntimeError`, it logs
  one `RAW_LOG.record()` (`response=""`, `error=str(call_exc)`,
  `attempts=MAX_RETRIES`, `api_success=False`) and then re-raises, so the
  existing outer `except` still appends the sentinel-scored prediction and
  increments `failed_calls` exactly as before -- only the missing raw-log
  record was added, no scoring/control-flow change.
- **`run_prompt_ablation_experiments.py`**: its own `query_openrouter` already
  returns `(None, diagnostics)` on exhaustion rather than raising, so the
  existing `RAW_LOG.record()` call already fired for this case (this script
  never had the gap). Enriched the same record with two fields the follow-up
  asked for that it didn't already carry: `error=call_diag.get("error", "")`
  and `attempts=call_diag.get("retries", 0) + 1`.
- **`run_position_bias_control.py`**: no change needed or possible without
  touching `Architectures/*.py`. It drives the real, unmodified
  `Direct_LLM_Scoring.py`, whose own `query_openrouter` also returns
  `(None, diagnostics)` on exhaustion (never raises) and whose `score_alternative`
  already calls `RAW_LOG.record()` unconditionally, before checking success --
  so the exhausted case was already logged, automatically, the moment section
  3's `mod.RAW_LOG.start()` wiring turned that logging on. That architecture
  file has no free-text `error` field in its `RAW_LOG.record()` call (it logs
  `retries` and `api_success` instead, via `diagnostics["failure_types"]`
  internally) -- adding one would mean editing `Architectures/Direct_LLM_Scoring.py`,
  which this task and the follow-up both rule out.

`collected_utc` needed no extra work in any of the three: `RawCallLog.record()`
stamps it itself, per call, unconditionally (see `sentinel_utils.py`), so
every record -- success or failure -- already carries it.

**Verification** (`Analysis/rerun_prep/infra/test_retry_exhausted_logging.py`,
no network, no API key): monkeypatches `requests.post` to always raise
`requests.exceptions.ConnectionError` and patches `time.sleep`/`MAX_RETRIES`
so the retry loop exhausts in about 2 seconds, then calls each script's real
call-site function (`score_scenario()`, `llm_prediction()`, and, for
position-bias, `Direct_LLM_Scoring.run_scenario()` directly) against a
temporary `RAW_LOG` path and reads back the jsonl. Result: all three scripts
write one record per failed alternative (3 for a 3-alternative scenario) with
`api_success is False` and `collected_utc` present; the two scripts I changed
also carry a non-empty `error` string and `attempts >= 1`; position-bias's
records lack `error` for the reason above but do carry `retries`/`api_success`.
Note on `MAX_RETRIES` monkeypatching: `Direct_LLM_Scoring.query_openrouter`
takes `max_retries` as a default-parameter value bound at function-definition
time, so reassigning the module attribute after import does not shrink its
retry count (it still ran the full 10 attempts, just with `time.sleep`
patched to a no-op so this cost no wall-clock time) -- noted here since it's a
minor surprise, not a defect in the fix being tested.

## 4. B60: deterministic tie-break for per-scenario tau

### 4.1 What was actually wrong, per script

- **`run_prompt_ablation_experiments.py`**: `scenario_metrics()` computed tau
  via `kendalltau(pred_vec, ref_vec)` on the raw weighted-sum scores (`pred`)
  and raw `mavt_score` values (`ref`), i.e. tau_b with ties kept, even though
  the script already imports and calls `apply_mavt_ranking` elsewhere
  (`score_scenario()`, for `result["ranking"]`) and never used its ranks for
  tau. Fixed: `load_reference()` now also carries `rank_by_alt` (the ground
  truth's own tie-broken `rank` column, already produced by
  `apply_mavt_ranking` inside the GT calculators -- reused, not re-derived);
  `scenario_metrics()` now computes tau on `result["ranking"]["ranks"]` vs
  `ref["rank_by_alt"]`.
- **`run_rag_ablation_experiments.py`**: two separate bugs.
  1. `rank_from_scores()` (used for the *predicted* ranks in both
     `llm_prediction()` and `nearest_neighbor_prediction()`) broke
     weighted-score ties by **list position** (`sorted(..., reverse=True)` is
     stable, so a tie falls through to whatever order the alternatives came
     in), not by `TIE_BREAK_PRIORITY`. Fixed: both call sites now build a
     flat per-criterion dict list and call `apply_mavt_ranking(...)["ranks"]`
     instead. `rank_from_scores` is left in the file, marked superseded in a
     comment, rather than deleted (not the change B60 asked for).
  2. `scenario_metrics()`'s tau, independently of the rank columns being
     right or wrong, was computed on raw `pred_weighted_score`/`gt_mavt_score`
     values (tau_b, ties kept) rather than on the `pred_rank`/`gt_rank`
     columns the row-building code already stores. Fixed: tau now uses
     `pred_by_alt[alt]["rank"]` vs `gt_by_alt[alt]["rank"]` (the latter is
     already the ground truth's own tie-broken rank, read from the GT xlsx's
     `rank` column at scenario-metadata build time -- that part was already
     correct). `spearman_rho` was left computed on raw scores; the plan item
     names Kendall's tau specifically, and `rho` is not part of any number
     this task pointed at.
- **`run_position_bias_control.py`**: **no bug found.** This script drives
  the real `Direct_LLM_Scoring.py` module's `run_scenario()` (which calls the
  real `apply_mavt_ranking`) and then reuses the real
  `paper_pipeline/calculate_per_run_metrics.py`'s `compute_ranking_metrics_local`
  for tau, which already computes tau on `gt_rank`/`arch_rank` -- both
  already tie-broken by `TIE_BREAK_PRIORITY`. Nothing to fix here; recorded
  below under verification.

### 4.2 Verification (`Analysis/rerun_prep/infra/verify_b60_tiebreak.py`)

Read-only, no API calls. Output: `Analysis/rerun_prep/infra/b60_tiebreak_verification.md`.

- **RAG ablation** (real historical data, `Analysis/RAG_Ablation/rag_ablation_results.xlsx`,
  7,830 per-alternative rows / 2,610 scenario-cells): recomputing tau the old
  way (raw scores) reproduces 3 distinct off-canon values in the stored
  `kendall_tau` column (-0.816497, 0.0, 0.816497), confirming the bug was
  real. Recomputing with the fixed method (ranks re-derived via
  `apply_mavt_ranking`, ground-truth ranks from the stored `gt_rank` column)
  gives **0 off-canon values across all 2,610 scenario-cells**. 57 of the
  7,830 predicted ranks change under the `TIE_BREAK_PRIORITY` fix (i.e. 57
  rows where the old positional tie-break and the correct criterion-priority
  tie-break disagreed on a genuine weighted-score tie).
- **Position-bias control** (real historical data, all four models'
  `Output Files */position_bias/Direct_LLM_Scoring_reversed_run_01.xlsx`, 533
  scenarios): tau recomputed directly from the stored `rank` column (already
  `apply_mavt_ranking`'s output) is within {-1,-1/3,1/3,1} for all 533 --
  confirms no bug, independent of the "no bug found" code-reading conclusion
  above.
- **Prompt ablation**: the shipped `Analysis/Prompt_Ablation/*.xlsx` cell
  files store only the aggregate `kendall_tau`/`top1` per scenario, never the
  per-alternative scores or ranks that produced them (checked: no such
  columns exist), so the *fixed* code cannot be re-run against *historical*
  data -- there is nothing to feed it. The historical bug is still
  demonstrable from what is stored: `cell_control_AD_deepseek_run_01.xlsx`'s
  194 stored tau values include 4 distinct off-canon values (-0.816497, -0.5,
  0.0, 0.816497). The fix itself was verified by exercising the actual
  patched `scenario_metrics()` function (dynamically imported, not
  re-implemented) against two constructed cases, one of which has a genuine
  float-exact predicted weighted-score tie between two alternatives with
  different `environmental` scores (`TIE_BREAK_PRIORITY`'s first key): both
  cases return tau = 1/3, and the tie is broken toward the alternative with
  higher `environmental`, as `TIE_BREAK_PRIORITY` specifies.

All three scripts' post-fix tau values are confirmed restricted to
{-1, -1/3, 1/3, 1} wherever they could be checked (RAG ablation and
position-bias from real data; prompt ablation from the patched function
directly).

## 5. New `paper_pipeline/` scripts

All three are read-only on existing per-run output files (no API calls),
default their output to `Analysis/` (the convention `duplication_rate_analysis.py`
and similar existing scripts use), and take `--output-dir` so they can be
pointed elsewhere -- used here to redirect every verification run to
`Analysis/rerun_prep/infra/` rather than touching the real `Analysis/` files.
Registered in `paper_pipeline/run_paper_pipeline.py` under the `numbers` stage
(after "Per-run metrics", which `build_numbers_of_record.py` depends on).

### 5.1 `compute_tie_rates.py`

Reuses `paper_pipeline/calculate_per_run_metrics.py`'s own harness
(`_build_config`, `load_ground_truth`, `build_gt_lookup`, `build_gt_id_lookup`,
`_discover_run_files`, `load_architecture`, `match_scenarios`,
`filter_failed_scenarios`) rather than re-parsing run files, matching
`Analysis/pass5/d12_analyses.py`'s `load_runs()` pattern. Computes, per
scenario, `any_tie` (>=2 alternatives share a weighted score *anywhere* in the
ranking -- the S L203 supplement figure) separately from `top_tie` (a tie at
the *top* score, the one that can move Top-1) and `top_tie_input_order_share`
(within a top tie, whether `TIE_BREAK_PRIORITY` still leaves a tie that falls
through to input order).

**Reproduction check** against `Analysis/pass5/d12_ties_summary.csv` (the
D9_D12_REPORT.md reference): exact match (max abs diff 0.0) across all 36
model x architecture x decision_type cells, including the three named cells
(A_E Overall `any_tie_share`: DeepSeek 17.3%, GPT-OSS 5.8%, Qwen 12.7%,
matching D9_D12_REPORT.md section 8.2's table exactly). My first draft
conflated `any_tie` with `top_tie` (both computed as "does the *top* score
tie") and got 11.0/3.3/7.1% -- caught by this same reproduction check, fixed
by adding the separate "any two alternatives share *any* score" computation
via `len(np.unique(np.round(ws, 9))) < len(ws)`.

### 5.2 `compute_regret.py`

Same harness reuse. Per scenario: reference MAVT value of the reference's
top-ranked alternative minus reference MAVT value of the alternative the
architecture ranks first (0 on a Top-1 hit), plus the regret a uniformly
random pick would take on the same scenario (matches
`Analysis/pass5/d12_analyses.py`'s definition exactly).

**Reproduction check** against `Analysis/pass5/d12_regret_summary.csv`: exact
match (max abs diff 0.0) across all 36 cells for `mean_regret`,
`zero_regret_share`, `top1`, `mean_regret_given_miss`, `random_pick_regret`.
Overall-row values match D9_D12_REPORT.md section 7.2's table to the last
published digit (e.g. DeepSeek A_D 0.0511, A_E 0.0346, A_H 0.0021; GPT-OSS
A_D 0.0616; Qwen A_H 0.0033).

### 5.3 `build_numbers_of_record.py`

`paper/pass5/NUMBERS_OF_RECORD.csv` has 122 rows; 37 are tagged with
`computing_script` = `paper_pipeline/calculate_per_run_metrics.py` (all the
`AH_*` per-model, per-decision-type, range and best/worst-model rows) and are
mechanically recomputable from `paper/per_run_metrics/per_run_metrics_all.csv`,
which that script already produces. The other 85 rows are tagged with scripts
this task's file list explicitly excludes (`run_hybrid_ablation_experiments.py`,
`test_hybrid_ablation_significance.py`, `evaluate_baseline_metrics.py`,
`Analysis/pass5/d2_reproduce_ah_numbers.py` sections B-E) -- P1/P2 territory,
and mostly Set-B-ensemble / significance-testing numbers that are not
recomputable from a single per-run CSV. Never writes
`paper/pass5/NUMBERS_OF_RECORD.csv` itself; writes a sibling CSV with the
original schema plus `regen_value`/`regen_status`/`regen_note`/
`regen_matches_value` columns, diffable against the original by `number_id`.

**Result on current data**: 37/122 rows regenerated, all 37 matching the
recorded `value` (0 mismatches). The other 85 are marked `not_regenerated`
with the owning script named in `regen_note`, grouped in the script's printed
summary. (First draft had 6 false mismatches on the Top-1 rows -- an
off-by-a-factor-of-100 bug, `top1_accuracy` in `per_run_metrics_all.csv` is a
0-1 fraction and needs `* 100` to match the CSV's percentage convention;
fixed and reverified.)

## 6. Files touched

- `model_config.py` -- `gemini` spec (section 1.3); `gptoss` label only
  (section 1.4); `deepseek` full spec, id/label/output_folder (section 1.5).
  `qwen` untouched throughout.
- `Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py` --
  imports (`hashlib`'s new use, `datetime`, `RawCallLog`), `RAW_LOG`/lock,
  `score_scenario()` logging call (now also `error`/`attempts`, section 3.1),
  `load_reference()`/`scenario_metrics()` tie-break fix, `run_cell()`/
  `_failed_record()`/`main()` for `collected_utc` + raw-log start/stop,
  removed the now-unused `CRITERION_WEIGHTS` import.
- `Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py` --
  imports (`threading`, `datetime`, `RawCallLog`, `apply_mavt_ranking`),
  `RAW_LOG`/lock, `llm_prediction()` logging call plus the inner try/except
  added in section 3.1 for the retry-exhausted case, both
  `rank_from_scores(...)` call sites replaced with `apply_mavt_ranking`,
  `scenario_metrics()` tau fix, `run()` for `collected_utc` + raw-log
  start/stop.
- `Miscellaneous Scripts/experiments/run_position_bias_control.py` --
  `datetime` import, `RESULT_COLUMNS` gained `collected_utc`,
  `run_reversed_arm()` reuses the loaded module's own `RAW_LOG`. No tie-break
  change (none needed); no change needed for section 3.1 either (see there).
- `paper_pipeline/compute_dispersion_diagnostics.py`,
  `paper_pipeline/duplication_rate_analysis.py`,
  `paper_pipeline/generate_paper_figures.py`,
  `paper_pipeline/reconcile_recollection_diagnostics.py` -- Gemini and
  DeepSeek label/folder strings only, derived from `MODEL_SPECS["gemini"]`
  and `MODEL_SPECS["deepseek"]`.
- `paper_pipeline/run_paper_pipeline.py` -- registered the three new scripts
  under the `numbers` stage.
- New: `paper_pipeline/compute_tie_rates.py`, `paper_pipeline/compute_regret.py`,
  `paper_pipeline/build_numbers_of_record.py`.
- New (this task's own scratch/verification, not part of the pipeline):
  `Analysis/rerun_prep/infra/verify_b60_tiebreak.py` and its output
  `b60_tiebreak_verification.md`; `Analysis/rerun_prep/infra/test_retry_exhausted_logging.py`
  (section 3.1); the three new scripts' verification CSVs written under
  `--output-dir Analysis/rerun_prep/infra/`.

Not touched: the calculators, `run_hybrid_ablation_experiments.py`,
`run_baseline_models.py`, `test_hybrid_ablation_significance.py`,
`generate_paper_results_numbers.py`, `evaluate_parameter_extraction.py`, the
`Architectures/*.py` files, `sentinel_utils.py`, any `Ground Truth/*`,
`Scenario Files/*`, `chroma_rag_db/`, existing `Output Files*` or `Analysis/*`
result files, the paper, supplement, bib, README, or `CLAUDE.md`.

## 7. Open issues

1. `:exacto` on `google/gemini-3.8-flash` and `deepseek/deepseek-v4.1-flash`
   is kept on the "no evidence against it" standard described in sections 1.2
   and 1.5, not a positive confirmation; the P5 smoke test is the actual
   check. Note the `:floor` observation in section 1.4 -- if `gptoss` and
   `gemini` moved off `:exacto` for a real reason, `deepseek`'s new `:exacto`
   (set per this task's explicit instruction) may want the same reconciliation.
2. ~~`run_rag_ablation_experiments.py`'s raw log misses fully-exhausted calls~~
   -- **fixed**, section 3.1; verified with a mocked, no-network test.
3. `reconcile_recollection_diagnostics.py`'s Gemini and DeepSeek folders now
   point at `Output Files Gemini 3.8 Flash` / `Output Files DeepSeek V4.1
   Flash`; both will no-op until something is collected there, and neither
   can be pointed back at the old data without using the pre-rerun snapshot
   (sections 2 and 1.5).
4. `gptoss`'s label is now current (section 1.4); `qwen`'s already was.
   `deepseek`'s label reflects the new V4.1 Flash model (section 1.5), not a
   fix to the old V4 Flash price.
5. `paper/pass5/NUMBERS_OF_RECORD.csv`'s 85 non-`calculate_per_run_metrics.py`
   rows are not covered by `build_numbers_of_record.py`; a full rebuild of
   those needs the P1/P2-owned significance/ensemble scripts, out of this
   task's file scope.
6. `compute_tie_rates.py`/`compute_regret.py` will report zero rows for
   `deepseek` (and `gemini`) against *live* output folders until the actual
   reruns under the new folder names are collected -- expected, not a defect
   (section 1.5).

No git command (commit, push, checkout, stash, reset, or otherwise) was run
during this task or its follow-ups.
