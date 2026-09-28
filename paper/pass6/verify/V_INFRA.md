# V_INFRA: rerun data-collection infrastructure verification

Written 2026-09-26 (Phase V, item 7 of `paper/pass6/PASS6_HANDOFF.md`). Goal: the paid rerun
must never need repeating, so every field a reviewer or later analysis could need has to be
captured on the first pass.

**Method.** I read every collecting code path. I then ran four kinds of no-network checks:
- mocked `requests.post` probes of every raw-log call site, for a normal 200, a 200 with
  `content: null`, and retry exhaustion;
- the infra agent's `test_retry_exhausted_logging.py`;
- `verify_b60_tiebreak.py`;
- the free keyless GETs `/api/v1/models` and `/api/v1/models/{id}/endpoints`, plus the
  OpenRouter docs pages (provider routing, usage accounting, reasoning tokens, API reference).

No completion or chat endpoint was called and no money was spent. Scratch scripts and raw
outputs are in the session scratchpad `v_infra/`: `probe_success.py`, `ep.py`, `tokens.py`,
`cost.py`, and the endpoint JSON dumps.

**Files written:**
- this report;
- `V_INFRA_experiment_scripts.diff`, the exact diff applied to the experiment scripts;
- `V_INFRA_cost_plan.csv`, per experiment × arm × model: calls, tokens, cost.

**Edits made:** small logging additions to the four experiment scripts only (Section 3.3).
Nothing else was edited: not `model_config.py`, `Architectures/`, the paper, `Output Files*`,
or `sentinel_utils.py`.

**Git:** read-only only. I ran `git status --short` and `git show HEAD:<file>` to check a line
ending. No commit, push, checkout, stash or reset.

---

## 1. Model IDs, `:floor`, prices, providers (check 1 and 2a)

### 1.1 What `:floor` does (OpenRouter provider-routing docs)

- `:floor` is "a shortcut to sort by price". It is a superset of `provider.sort: "price"` and it
  **makes flex service-tier endpoints eligible**.
- Price sorting is load-balanced by inverse-square price weighting: a provider at 1/3 the
  price is 9x more likely to be tried first. Routing therefore varies from call to call; it
  is not pinned to one provider.
- `provider.require_parameters` defaults to **false**. The docs say providers "that don't
  support all the LLM parameters specified in your request can still receive the request,
  but will ignore unknown parameters". **Under the current payload, a provider that doesn't
  support `temperature` silently ignores it.**
- Other `provider` fields: `order`, `allow_fallbacks` (default true), `only`, `ignore`,
  `quantizations`, `sort`, `max_price`, `data_collection`, `zdr`.
- **None of the 7 collecting code paths sends a `provider` object.** Only `model`,
  `messages`, `temperature` and `reasoning` are sent, and never `max_tokens`.
- `:exacto` is not in the current docs. Supplement S1 still describes `:exacto` (B24 at S4).

### 1.2 Per-model table (fetched 2026-09-26)

**`openai/gpt-oss-20b:floor`** (reasoning `low`)
- Exists: yes.
- Listed price per M tokens (in/out): **$0.018 / $0.09**. Label `$0.018/$0.09`: OK.
- Context 131,072; max output 32,768.
- Reasoning: mandatory; efforts high/medium/low. `low` is valid.
- 12 endpoints. The cheapest are Darkbloom fp8 ($0.018/$0.09) and AkashML fp4
  ($0.020/$0.10). Others: CoreWeave fp4, DekaLLM bf16, DeepInfra bf16, Parasail fp4, Novita
  fp4, Bedrock, SiliconFlow fp8 (max output 8,192), Vertex, Groq.
- Every endpoint supports `temperature` and `reasoning`.
- Effect of `:floor`: roughly a 55/45 split between Darkbloom fp8 and AkashML fp4, so
  **quantization varies by call**.

**`qwen/qwen3.5-9b:floor`** (reasoning `none`)
- Exists: yes (canonical `qwen3.5-9b-20260310`).
- Listed price: **$0.10 / $0.15**. Label: OK.
- Context 262,144.
- Reasoning: not mandatory; no effort list. `effort: none` should disable it.
- 6 endpoints. The cheapest is **Darkbloom fp4 ($0.08/$0.13)**, then SiliconFlow fp8,
  DeepInfra bf16, Venice fp8, Parasail bf16 and Together.
- Every endpoint supports `temperature` and `reasoning`.
- Effect of `:floor`: most calls go to fp4 Darkbloom.

**`deepseek/deepseek-v4-flash-0731:floor`** (reasoning `none`)
- Exists: yes (canonical `deepseek-v4-flash-20260731`).
- Listed price: **$0.021 / $0.32**, which is the Relace fp4 endpoint. **Label `$0.14/$0.42`
  is WRONG**; that is V4.1's old label. V4.1 itself now lists $0.30/$1.20.
- Context 1.31M; max output about 944K.
- Reasoning: not mandatory, but **enabled by default at effort `high`**; efforts
  max/high/low. `none` should disable it.
- **31 endpoints**, with quantization fp4, fp8, bf16 or unknown. Price-weighted spread
  across StreamLake fp8 ($0.044/$0.132), Inceptron fp4, Sail fp4, Relace fp4 and
  OpenInference fp8, among others.
- Every endpoint lists `temperature` and `reasoning`.
- Effect of `:floor`: provider and quantization **vary widely call to call**. If any
  provider ignores `effort: none`, reasoning runs at `high` by default, the likely cause of
  the old DeepSeek A_D output anomaly (507 output tokens per call).

**`google/gemini-3.8-flash:floor`** (reasoning `minimal`)
- Exists: yes (canonical `gemini-3.8-flash-20260902`).
- Listed price: **$0.75 / $3.75** standard tier. Label: OK for the standard tier.
- Context 1,048,576; max output 65,536.
- Reasoning: **mandatory; efforts high/medium/low only.** **`minimal` is not a listed
  effort for this model.**
- 6 endpoints: AI Studio and Vertex, each at flex ($0.375/$1.875), standard ($0.75/$3.75)
  and priority ($1.35/$6.75).
- **The 3 Vertex endpoints do not list `temperature`.** All 6 list `reasoning`.
- Effect of `:floor`: routes mainly to the **flex tier** (4x weight over standard). About
  half of the flex calls would go to **Vertex flex, which does not list `temperature`**, and
  with `require_parameters` false, temperature 0.3 would be silently dropped on those calls.

**Current recommendations (for the author; `model_config.py` is theirs):**
1. Add `"provider": {"require_parameters": true}` to every payload, at minimum. For Gemini
   this removes the Vertex endpoints.
2. For reproducibility, pin one provider per model for the whole collection, with
   `"order": [<slug>], "allow_fallbacks": false, "require_parameters": true`, and optionally
   `"quantizations": [...]`. Example choices: gptoss `darkbloom/fp8` or `deepinfra/bf16`;
   qwen `deepinfra/bf16`; deepseek `deepinfra/fp8`; gemini `google-ai-studio` (standard) or
   `google-ai-studio/flex`.
3. If the author prefers `:floor` for cost, keep it and at least add
   `require_parameters: true` plus a quantization allowlist. **Log the serving provider on
   every call either way** (Section 3).
4. The natural place is a `"provider"` key in each `MODEL_SPECS` entry, read by a shared
   payload builder. That is the author's file, so this is proposed only.

**Gemini effort.** `"effort": "minimal"` is not among 3.8 Flash's `supported_efforts`
(high/medium/low), and reasoning is mandatory. The smoke test must show whether OpenRouter
rejects it (400) or maps it to `low`, and how many reasoning tokens come back. If it maps to
`low`, the paper's "minimal for Gemini" (main L734) must say `low`, or the spec should say
`low` explicitly.

### 1.3 The three `model_config.py` inconsistencies (check 2)

**(a) DeepSeek price label.** Listed $0.021/$0.32; the label says $0.14/$0.42. The label also
drives the paper's cost table: `generate_paper_results_numbers.py` L127–161 parses
`MODEL_SPECS[...]["label"]` for `Table8_cost_per_run`. Under `:floor` the charged price varies
per call, so **the cost table must be built from `usage.cost` summed from the raw logs, not
from labels**. That needs the architecture logging diff (Section 5, item M3).

**(b) Output folders and resume.** All three architectures skip any run whose
`<arch>_results_run_NN.xlsx` passes `sentinel_utils._is_complete_run_file`: exists, non-empty,
no `.tmp` sibling, readable with at least one row. See
`Direct_LLM_Scoring.py` L719–726, `Example-Guided_LLM_Scoring.py` L1000–1007 and
`LLM-Parameterized_Reference_Scoring.py` L1170–1177. The skip is logged to the console only.

- **"Output Files DeepSeek V4 Flash"** holds complete old V4 Flash data:
  - 5 per-run xlsx for each of A_D, A_E and A_H;
  - `position_bias/Direct_LLM_Scoring_reversed_run_01.xlsx`;
  - `hybrid_order_reversal/` with all 8 order-arm runs, complete jsonl.

  A rerun with the current config would **skip every DeepSeek architecture run, the
  position-bias arm and every order-arm run**, then re-aggregate and re-analyse the old V4
  Flash data under the 0731 name. Pipeline labels are derived from the folder name
  (`compute_dispersion_diagnostics.py` L69, `duplication_rate_analysis.py` L35), so they would
  also read "DeepSeek V4 Flash".
- **"Output Files GPT-OSS 20B" and "Output Files Qwen3.5 9B"** keep their names and hold the
  same complete set, 63 files each. Everything would be skipped.
- **"Output Files Gemini 3.8 Flash"** exists and is **empty**, so it is safe.
  "Output Files Gemini 3.5 Flash" is no longer referenced.
- **`Analysis/Prompt_Ablation/`** holds 162 old `cell_<variant>_<arch>_<model_key>_run_NN.xlsx`
  files. The prompt ablation resumes on file existence
  (`run_prompt_ablation_experiments.py`, the `cell_path.exists()` check in `main()`), keyed
  by `model_key`, **not by model id**. Old `gemini` (3.5) and `deepseek` (V4) cells would be
  reused as if they were 3.8 and 0731. **This folder must be moved aside too.** The handoff's
  Phase I step 9 names only the Output folders.

**(c) Serving provider.** No raw log recorded it before this check.
- The ablation scripts now do (Section 3.3).
- The architectures still don't: position bias and the hybrid order arm inherit A_D's and
  A_H's call paths, so they don't either.
- OpenRouter bodies carry an `id` (generation id). `GET /api/v1/generation?id=` returns
  provider and cost afterwards, so logging `id` is the minimum. The top-level `provider`
  field is observed in practice but isn't in the documented schema, so log both.

**Stale strings.** A grep of `paper_pipeline/`, `Miscellaneous Scripts/` (legacy excluded),
`Architectures/`, `model_config.py` and `sentinel_utils.py` found:
- no "V4.1", "3.5 Flash", "Gemini 3.5", `gemini-3.5` or `exacto`;
- no hard-coded OpenRouter model ids outside `model_config.py`;
- "DeepSeek V4 Flash" only in `model_config.py` itself, via the folder name. Renaming the
  folder to "Output Files DeepSeek V4 Flash 0731" fixes the derived labels automatically.

Supplement L201 (old IDs, `:exacto`, prices "as of August 1, 2026") and main L734 ("DeepSeek
V4 Flash", "Gemini 3.5 Flash", "minimal") are S4 items.

---

## 2. Collection plan and cost (check 6)

Call counts follow the paper's Methods and S2 design:
- main L753 and L757–761;
- supplement L1237–1242, the prompt-ablation run counts (10/5/3);
- supplement L1339–1342, 5 reversed + 3 control order runs.

Tokens per call are the **historical** means per model and arm, from:
- the shipped diagnostics JSON;
- the `Analysis/Prompt_Ablation` cells;
- `Analysis/RAG_Ablation/rag_ablation_results.xlsx`;
- the order-arm jsonl.

The Gemini figures are **Gemini 3.5** tokens and the DeepSeek figures are **V4 Flash**
tokens, used as proxies. Prices are current listed prices. Models are never pooled.

| Experiment | Arms × runs | Calls/model | GPT-OSS | Qwen | DeepSeek 0731 | Gemini 3.8 |
|---|---|---|---|---|---|---|
| Main benchmark | A_D, A_E 5×585; A_H 5×195 | 6,825 | $0.17 | $0.49 | $0.62 | $4.93 |
| Prompt ablation | A_D control, no_anchors 10×585; A_D cot, scale 5×585; A_E control, cot, scale 5×585. Gemini 3 runs per cell | 26,325 (Gemini 12,285) | $0.72 | $5.33 | $1.47 | $15.71 |
| RAG ablation | 7 LLM configs × 90 × 3, 1 run (NN arm offline) | 1,890 | $0.06 | $0.21 | $0.06 | $1.70 |
| Position bias | A_D reversed, 1 × 195 × 3 | 585 | $0.02 | $0.04 | $0.10 | $0.38 |
| A_H order arms | reversed 5 + control 3, × 195 | 1,560 | $0.03 | $0.10 | $0.05 | $1.03 |
| **Total per model** | | **37,185** (Gemini 23,145) | **$1.00** | **$6.16** | **$2.29** | **$23.76** |

**Total: 134,700 calls, about $33 at listed standard prices.**

- If Gemini is served at the flex tier (what `:floor` favours), and DeepSeek at the
  mid-market $0.14/$0.42, the total is about **$25**.
- This is consistent with the earlier $24–30 estimate **only if Gemini 3.8 produces about
  as many output tokens as Gemini 3.5 did** (41–87 per scoring call).
- Gemini 3.8 has mandatory reasoning, and `minimal` is not a listed effort. **Each extra 100
  reasoning tokens per call adds about $8.7** across Gemini's 23,145 calls, at the standard
  output price.
- Qwen's CoT arm averaged **5,703 output tokens per call** on A_D; it is 24.7M of Qwen's 25M
  prompt-ablation output tokens. No `max_tokens` is set anywhere.
- At the script default (`--runs 5` for every cell, Gemini included), the prompt ablation
  alone becomes 81,900 calls and about $33 (Gemini $26.2), for a total of about $43.

**Commands implied by the paper design** (the prompt-ablation script applies one `--runs` to
every selected cell):
- Main: for each model, set `MODEL_KEY`, then run the 3 architectures with `N_RUNS=5`.
- Prompt ablation, 3 invocations:
  1. `--models gptoss qwen deepseek --runs 5`
  2. `--models gptoss qwen deepseek --architectures AD --variants control no_anchors --runs 10`
     (resumes runs 1–5 and adds 6–10)
  3. `--models gemini --runs 3`

  Then run one final invocation with all 4 models, which resumes every cell and rewrites the
  combined summary.
- RAG ablation: **one** process with all models (see check 7).
- Position bias: `run --model <k> --runs 1` for each of the 4 models.
- A_H order arms: `--collect-only --order-arms reversed control --order-runs 3`, then
  `--collect-only --order-arms reversed --order-run-start 4 --order-runs 5`.

**The A_H order experiment is part of `run_hybrid_ablation_experiments.py`.** It costs
1,560 calls per model: reversed 975 plus control 585. With a timestamped same-window rerun of
the main A_H runs, the control arm is no longer needed to rule out drift, which is the point
of CLAUDE.md's timestamp rule. The 13-run permutation design (C(13,5) = 1,287) in S2 still
assumes 8 original-order runs, so dropping the control arm changes the test to C(10,5). That
is the author's call; keeping it costs about $1.3 in total.

**Before collecting:** check the OpenRouter credit balance is at least 2x the estimate. See
item S7 in Section 5: an out-of-credit 402 is retried 10 times and then written as sentinel
"failures", and resume logic treats that run as complete.

---

## 3. Per-call raw log and per-run file completeness (check 3)

### 3.1 How each field was verified

`probe_success.py` mocks a 200 response with `id`, `provider`, `model`,
`finish_reason: "length"` (valid JSON content), `usage.cost`, `reasoning_tokens` and a
`message.reasoning`. It then reads back the jsonl each call site writes. A second probe sends
`content: null`. The infra agent's retry-exhaustion test passes both before and after my
edits (3/3 scripts).

### 3.2 Field-by-field table

Key:
- **Y** = present; **N** = absent; **Y\*** = added by my edit today (Section 3.3).
- **fn** = implied by the filename only.

| Field | A_D (`Direct`) | A_E (`Example-Guided`) | A_H (`LLM-Param`) | Prompt abl. | RAG abl. | Position bias (via A_D) | A_H order arm (hybrid) |
|---|---|---|---|---|---|---|---|
| UTC timestamp per call | Y | Y | Y | Y | Y | Y | **N → Y\*** |
| Run index | Y (from filename) | Y | Y | Y | N (1 run; `null`) | Y | Y |
| Scenario id | Y | Y | Y | Y | Y (source id) | Y | Y |
| Decision type | Y | Y | Y | Y | Y | Y | Y |
| Architecture / condition | fn | fn | fn | Y\* (architecture, variant) | Y\* (ablation label, k, retrieval mode) | fn | Y (arm) |
| Model id requested | Y | Y | Y | Y (+ `model_key`\*) | Y | Y | Y\* (`model_id`) |
| Model id returned | N | N | N | Y\* | Y\* | N | N (Y once A_H logs it; captured via `api_diag`\*) |
| Serving provider | N | N | N | Y\* | Y\* | N | N (same) |
| Generation `id` | N | N | N | Y\* | Y\* | N | N (same) |
| User prompt text + sha256 | Y | Y | Y (single message) | Y | Y | Y | Y |
| System prompt | N (constant in code) | N | n/a | Y\* (sha256) | Y\* (sha256) | N | n/a |
| temperature / reasoning params | N | N | N | Y\* (`request_params`) | Y\* | N | N |
| max_tokens | not sent | not sent | not sent | not sent | not sent | not sent | not sent |
| Raw response text | Y (content only) | Y | Y | Y | Y | Y | Y |
| Reasoning text | N | N | N | Y\* | Y\* | N | N |
| finish_reason | N | N | N | Y\* (logged, not acted on) | Y\* | N | N |
| usage: prompt/completion tokens | Y | Y | Y | Y | Y | Y | Y |
| usage: reasoning tokens, cost | N | N | N | Y\* (full `usage`) | Y\* | N | N |
| Latency | Y | Y | Y | Y | Y | Y | Y |
| Retry count | Y | N | N | Y | Y\* | Y | N |
| Each failed attempt's error | N | last error only, on exhaustion | exception text only | Y\* (`attempt_errors`) | Y\* | N | N |
| Parse outcome / failure code | N | N | N | Y\* (`parse_error`) | Y\* | N | Y (`failure_types`, `parsed`) |
| `api_success` correct | Y | **N (always False on success)** | Y | Y | Y | Y | n/a |
| Retrieval ids / distances | n/a | ids Y, distances N | n/a | Y\* (A_E arms, ids) | Y\* (ids + distances, jsonl and xlsx) | n/a | n/a |
| Per-run file `collected_utc` | **N** (diagnostics json only, start time) | **N** (same) | **N** (same) | Y (per cell) | Y (one for whole collection) | Y | **N → Y\*** |
| Per-run file `model_id` | N (folder only) | N | N | Y\* | Y\* | Y\* | Y\* |
| Per-alternative scores in the per-run file | Y | Y | Y | **N → Y\*** (`alt_scores_json` with tie-broken ranks) | Y | Y | params Y |

**Bug found by probe.** In `Example-Guided_LLM_Scoring.py` L562, every A_E raw record
written after a *successful* call says `api_success: false`, because the `diagnostics` dict
returned by its `query_openrouter` has no `success` key.

### 3.3 Edits applied (experiment scripts only; full diff in `V_INFRA_experiment_scripts.diff`)

All scripts compile. The mocked probes show the new fields populated, and
`test_retry_exhausted_logging.py` still passes 3/3.

- **`run_prompt_ablation_experiments.py`**
  - New `_response_meta(data)` helper. It returns `response_id`, `response_model`,
    `provider`, `system_fingerprint`, `finish_reason`, `native_finish_reason`, `usage` (in
    full), `reasoning` and `body_error`.
  - `query_openrouter` now also returns `request_params` (the payload minus messages) and
    `attempt_errors`.
  - `build_messages(..., retrieved_out=None)` now reports A_E exemplar ids.
  - The raw record gains:
    - `architecture`, `variant`, `model_key`;
    - `system_prompt_sha256`, `rag_exemplar_ids`;
    - `attempt_errors`, `request_params`;
    - all the `_response_meta` fields;
    - `parse_error`. The parse now runs before the record, with an unchanged result.
  - Cell rows gain `model_id` and `alt_scores_json`: per-alternative scores plus tie-broken
    ranks, so tau and Top-1 can be recomputed from the sheet.
  - The original was LF. My first Python rewrite produced CRLF, which I reverted to LF, so the
    diff is content only.
- **`run_rag_ablation_experiments.py`**
  - Same `_response_meta` helper, plus `retries`, `attempt_errors` and `request_params` on
    success.
  - The retry-exhausted `RuntimeError` now carries `.attempt_errors`.
  - Both raw records gain:
    - `ablation` (label), `k`, `retrieval_mode`;
    - `retrieved_ids`, `retrieved_distances`, `system_prompt_sha256`;
    - the metadata fields and `parse_error`.
  - Result rows gain `model_id`, `retrieved_ids` and `retrieved_distances`, as JSON strings.
  - **Also fixed:** `_is_transient_http_status` was used at L568 but never imported. Every
    non-200 response raised a `NameError` that was caught and **overwrote the real HTTP
    error text** in `last_error`. I added it to the `model_config` import. Retry behaviour is
    unchanged; only the logged error text is now correct.
- **`run_hybrid_ablation_experiments.py`**
  - Order-arm jsonl records gain `collected_utc` (per call, UTC) and `model_id`. Before this
    the order arm **recorded no timestamp at all**, against the CLAUDE.md rule.
  - The order-arm xlsx gains the same two columns.
  - `instrument_capture` now keeps A_H's full per-call diagnostics as `api_diag`, so provider,
    id and usage flow through automatically once A_H's `query_openrouter` returns them.
- **`run_position_bias_control.py`**: `model_id` column added to `RESULT_COLUMNS` and to each
  row. Its raw log is A_D's, so the provider and usage fields depend on the A_D fix.

**Not applied** (behaviour changes, not logging): the `finish_reason == "length"` failure
rule, `max_tokens`, the `provider` block, and RAG-ablation checkpointing. See Section 5.

---

## 4. Silent-failure risks (check 4), tie-break (check 5), concurrency and determinism (check 7)

### 4.1 Silent failures

1. **Truncation.** No script sets `max_tokens`, and none checks `finish_reason`.
   - A truncated JSON usually fails `json.loads`. It then shows up as
     `EXTRACTION_INVALID_JSON` or `failed_malformed_json`, a failure with the wrong cause.
   - The probe shows a `finish_reason: "length"` response with parseable content is
     **accepted as a success** by all 7 paths.
   - In the prompt-ablation CoT arm, `parse_scores` falls back to the *last* `{...}` holding
     any criterion key. A response truncated mid-reasoning can therefore parse an early
     partial block.
   - Reasoning tokens count against `max_tokens` on most providers (docs). A provider default
     cap, such as SiliconFlow gpt-oss at 8,192, could end in `length` with empty content.
2. **`content: null` with reasoning in a separate field.** Verified by mock:
   - **A_D:** `query_openrouter` L207
     (`logger.debug(f"...{msg.get('content', '')[:500]}")`) is evaluated even with debug
     off, and raises `TypeError` on `None`. The exception escapes `query_openrouter`, which
     catches only `RequestException` and `ValueError`. `run_scenario` aborts: the remaining
     alternatives are not scored, the scenario is marked "crashed" with `api_calls=0`, and
     **no raw record is written for a paid call**. Position bias inherits this.
   - **A_E:** L233 fails the same way. It lands in the `except` at L570, so it is recorded
     as an API failure with error "'NoneType' object is not subscriptable"; the reasoning is
     lost and the code is `FAILED_UNKNOWN`. L568 has the same f-string problem.
   - **A_H:** L352 and L505 fail the same way and yield `FAILED_EXTRACTION_EXCEPTION`.
   - Prompt and RAG ablations now log `finish_reason` and `reasoning`. The prompt ablation
     marks such a call `api_success=False` or `failed_api_exhausted`, which is a mislabel; the
     RAG ablation shows it as a `parse_error`.
3. **200 with an error body, or no `choices`.** Content becomes `""` and the call is failed
   without retry. `"choices": []` raises an `IndexError` that escapes A_D's
   `query_openrouter` the same way as item 2.
4. **Non-retryable HTTP errors (400/401/402/403) are retried 10 times** with backoff up to
   60 s. Running out of credit mid-run therefore produces a "complete" run xlsx full of
   sentinels, which `_is_complete_run_file` then accepts as done.
5. **Retrieval.**
   - A_E logs exemplar ids per call, but no distances: `retrieve_similar_scenarios` L353–366
     drops `results['distances']`.
   - If a Chroma query raises, A_E silently scores **without exemplars** as a success. It
     returns `[]` at L348–350, and an empty context is not a failure. That is detectable
     afterwards only through `rag_exemplar_ids: []`.
   - Prompt-ablation A_E arms had no retrieval logging (now Y\*). The RAG ablation had
     only mean distance and count in the xlsx (now ids and distances in both jsonl and xlsx).
   - The RAG ablation's random arm draws from one `rng` across models in sequence, so each
     model sees different random exemplars. That is now auditable through `retrieved_ids`.
6. **RAG index check** is enforced at A_E startup (`init_rag_resources` L150–178). It raises
   on schema-version mismatch (expects 4) or a source-sheet SHA mismatch. The prompt
   ablation's A_E arms call it too.
   - The hash covers the three RAG xlsx only, so a code-only change to the embedding still
     needs a manual version bump, as CLAUDE.md says.
   - The RAG ablation builds a fresh temporary collection from the xlsx on every run, so it
     can't be stale. Its `.rag_ablation_temp/` dirs are never cleaned up.
7. **Resume skips** are logged to the console only.
   - The architectures skip any readable per-run xlsx, with no check that it came from this
     collection window.
   - Old runs have no `collected_utc`, so a mix is detectable after the fact, but nothing
     prevents it.
   - Position bias and the order arm resume from checkpoint jsonl. The prompt ablation
     resumes from cell existence.
   - The RAG ablation has **no checkpoint**: 7,560 calls in one process, with the xlsx
     written only at the end. A crash loses everything except the raw jsonl, which now
     carries the ablation and retrieval fields.
8. **A_H diagnostics miscount.** At L808, an API-exhausted extraction returns
   `scenario_failed: False`, so `successful_scenarios` and `success_rate` in the diagnostics
   JSON count it as a success. The xlsx still carries sentinels, so the metrics are right; the
   JSON success rate is wrong.

### 4.2 Ablation tau (check 5)

- **Prompt ablation** (`scenario_metrics`): tau on `apply_mavt_ranking` ranks (10-dp rounding
  plus `TIE_BREAK_PRIORITY`) against the GT `rank` column. Top-1 comes from ranks. OK.
- **RAG ablation**: tau on the ranks OK. Predicted ranks use `apply_mavt_ranking`.
  **Top-1 and Top-2 are not.** At L927–929 they sort raw `pred_weighted_score` and
  `gt_mavt_score` with no tie-break, so an exact predicted tie falls to input order and can
  disagree with `pred_rank`. This is SHOULD-FIX, not blocking: it is recomputable offline from
  the stored `pred_rank` and `gt_rank`.
- **Position bias**: uses `calculate_per_run_metrics.compute_ranking_metrics_local`, with tau
  and Top-1 on `gt_rank` and `arch_rank`. OK.
- **`verify_b60_tiebreak.py` re-run:**
  - RAG: 0 of 2,610 new tau values off-canon.
  - Position bias: 0 of 533.
  - Prompt ablation: patched function OK.
  - One difference from INFRA_REPORT §4.2: **47** predicted ranks change under the fix, not
    57. The likely reason is the pipeline agent's later 10-dp rounding in `apply_mavt_ranking`,
    which removes float-noise ties.
  - The script rewrote `Analysis/rerun_prep/infra/b60_tiebreak_verification.md`.
- **Note:** fully identical scores still fall through `TIE_BREAK_PRIORITY` to input order,
  which is the documented benchmark rule. In the prompt-ablation probe, three identical score
  sets gave tau = 1 because the reference happened to be in list order.
  `compute_tie_rates.py` measures this.

### 4.3 Concurrency and determinism (check 7)

- **Parallelism.** The architectures, position bias and the order arm are serial. The prompt
  and RAG ablations use `ThreadPoolExecutor` (default `--workers 8`). Raw-log writes are
  serialised by a lock, and the RAG ablation's retrieval is serial, so random draws stay
  reproducible. 429s are retried with backoff.
- **Shared files.**
  - Architecture outputs are per model folder and per architecture, so they don't collide.
  - Prompt-ablation cells are per model_key, but each process **overwrites**
    `prompt_ablation_summary.xlsx` and `prompt_ablation_results.md` with only its own
    `--models`. Finish with one all-model invocation.
  - **The RAG ablation writes one `rag_ablation_results.xlsx` and appends to one raw jsonl for
    all models.** Two concurrent RAG processes would clobber the xlsx and interleave the
    jsonl. Run it as one process, or give each its own `--output-dir`.
- **`MODEL_KEY`** is read once, when `model_config` is imported at process start, and the
  architectures bind `MODEL_ID` and `API_CONFIG` at import. Editing `model_config.py`
  between launches is therefore safe, even while an earlier process is still running.
  - Position bias and the order arm override `API_CONFIG["model"]` and `["reasoning"]` per
    `--model`, and the architectures read `API_CONFIG` at call time. OK.
  - The ablations take the model from `--models`. The RAG ablation's
    `OUTPUT_DIR = get_output_folder()` only creates a directory.
- Proposed for the author: `MODEL_KEY = os.getenv("MODEL_KEY", "gemini")`, so the 12
  architecture runs don't need 4 file edits.
- **No hard-coded model id** exists outside `model_config.py`.
- **Prompt-ablation control is not byte-identical to the main runs**, although the docstring
  says "shipped prompt, unmodified".
  - Its user prompt says "Provide scores for all 4 criteria." where A_D and A_E say "(0-1)".
  - Its A_E arms append the RAG context to the *A_D* user prompt with "\n", rather than
    using A_E's `build_user_prompt_with_rag`, which has different blank lines.
  - The RAG ablation's system prompt also lacks A_E's "You must distinguish between the
    criteria" sentence.
  - These are pre-existing design choices. Since everything is re-collected anyway, the
    author may want the control arms to call the architectures' own prompt builders (NOTE).

---

## 5. Discrepancies / must-fix before rerun

"Applied?": **Y** = done today, recorded in `V_INFRA_experiment_scripts.diff`;
**N-prop** = proposed diff, needs the author because it touches `Architectures/` or
`model_config.py`; **N-op** = an operational step.

### MUST-FIX

**M1. Old outputs would be resumed as new.** Applied: N-op.
- Where: `model_config.py` L50 (deepseek folder); the resume logic at `Direct` L722,
  `Example-Guided` L1003, `LLM-Param` L1173, position bias L280, hybrid L468–492, prompt
  ablation `main()`.
- Fix:
  - After the Phase I snapshot, rename deepseek's `output_folder` to
    `"Output Files DeepSeek V4 Flash 0731"` (the author's edit).
  - Move aside "Output Files GPT-OSS 20B" and "Output Files Qwen3.5 9B", **including their
    `position_bias/` and `hybrid_order_reversal/` subfolders**.
  - **Move aside `Analysis/Prompt_Ablation/`**, because its cells are keyed by model_key.
  - Confirm every target folder is empty before collecting.

**M2. No `provider` routing control.** Applied: N-prop.
- Where: the payload in all 5 `query_openrouter` functions: `Direct` L161–169,
  `Example-Guided` L198–205, `LLM-Param` L319–326, prompt ablation `query_openrouter`,
  RAG ablation `query_openrouter`.
- The risk: under `:floor`, Gemini routes about half its flex calls to Vertex, which doesn't
  list `temperature`, and `require_parameters` defaults to false. DeepSeek's quantization
  varies across 31 endpoints.
- Fix: add `MODEL_SPECS[k]["provider"]` and `payload["provider"] = spec["provider"]`, at
  minimum `{"require_parameters": True}`. Recommended:
  `{"order": [slug], "allow_fallbacks": False, "require_parameters": True}` per model.

**M3. The architectures log neither provider, generation id, returned model, finish_reason,
usage (reasoning tokens, cost), reasoning text, request params nor parse outcome.** They make
27,300 of 134,700 calls, and position bias (2,340) and the order arm (6,240) inherit them. The
cost table can't use collection-time prices without `usage.cost`. Applied: N-prop.
- In each `query_openrouter` success branch (`Direct` L230–239, `Example-Guided` L256–267,
  `LLM-Param` L375–386), add `diagnostics.update(_response_meta(data))`. Preferably move the
  helper into `sentinel_utils` as `response_meta()`; it is identical to the one added to the
  ablation scripts.
- Also add `diagnostics["request_params"] = {k: v for k, v in payload.items() if k != "messages"}`
  and an `attempt_errors` list appended in each failure branch.
- In each `RAW_LOG.record` (`Direct` L369–381, `Example-Guided` L552–564,
  `LLM-Param` L490–501), add:
  - `architecture=`, `system_prompt_sha256=`;
  - `request_params`, `response_id`, `response_model`, `provider`, `finish_reason`,
    `native_finish_reason`, `usage`, `reasoning` and `attempt_errors`, each from the
    diagnostics dict;
  - the parse or failure code. For A_D and A_E this means moving the record after
    validation, or adding a second "outcome" field.

**M4. Null content crashes A_D and loses the raw record.** A_E and A_H record it with the
wrong error. Applied: N-prop.
- Where: `Direct` L207; `Example-Guided` L233 and L568; `LLM-Param` L352 and L505.
- Fix: replace `msg.get('content', '')[:500]` with `(msg.get('content') or '')[:500]`, and
  `response_text[:1000]` with `(response_text or '')[:1000]`. At the content line
  (`Direct` L212, `Example-Guided` L238, `LLM-Param` L357), use
  `content = (...).get("content") or ""`.

**M5. A_E `api_success` is always False on success.** Applied: N-prop.
- Where: `Example-Guided` L562.
- Fix: `api_success=True`. That branch runs only when `query_openrouter` returned.

**M6. No `collected_utc` in the per-run xlsx** (CLAUDE.md rule; the diagnostics JSON has the
start time only). Applied: N-prop.
- Where: `Direct` L529–534 and L680–695; `Example-Guided` L778–783 and L944–959;
  `LLM-Param` its FIELDNAMES and L1113–1135.
- Fix: add a `collected_utc` column filled from `cumulative_diagnostics['collected_utc']`,
  plus `model_id` from `API_CONFIG['model']`. Add `collected_utc_end` to the diagnostics JSON.

**M7. The hybrid order arm had no timestamp.** Applied: **Y**.
- Where: `run_hybrid_ablation_experiments.py` `collect_order_arm`.
- Change: `collected_utc` and `model_id` added to the jsonl and xlsx.

**M8. Gemini 3.8 does not list effort `minimal`.** It lists high/medium/low, and reasoning is
mandatory. Applied: N (smoke test).
- Where: `model_config.py` L57.
- At the smoke test, check for a 400 response, the returned reasoning tokens, and whether the
  `usage` shows reasoning. If it is mapped to `low`, set `"low"` explicitly (author) and
  update main L734. **Each 100 reasoning tokens per call adds about $8.7.**

**M9. DeepSeek label and cost table.** Applied: N-prop.
- Where: `model_config.py` L48; `generate_paper_results_numbers.py` L127–161.
- Fix: the label should read $0.021/$0.32 listed; the author edits it. Build `Table8` from the
  summed `usage.cost` in the raw logs, which depends on M3; labels are fallback only.

**M10. Carried over from the handoff (not re-derived here): unrounded architecture ranking and
the A_H key override.** Applied: N-prop (other V agents).
- Where: `Direct` L828; `Example-Guided` L686 and L1105; `LLM-Param` L747 and L1323; the A_H
  merge at `LLM-Param` L652.
- Note: the A_E and A_H per-run ranks come from **local** `apply_mavt_ranking` copies
  (`Example-Guided` L658, `LLM-Param` L721) that don't round. Replace them with a call to
  `sentinel_utils.apply_mavt_ranking` on flattened scores. Restrict the merge to the requested
  extraction keys.

### SHOULD-FIX

**S1. `finish_reason == "length"` is accepted as a success; no `max_tokens` is set.**
Applied: N-prop, ablations N.
- Where: all `query_openrouter` functions and score paths.
- Fix:
  - Set `diagnostics["truncated"] = finish_reason == "length"`, and fail the call with a new
    code such as `FAILED_TRUNCATED` (add it to `model_config`; author).
  - Set `max_tokens` (for example 4,096, or 16,384 for the CoT arm) so a runaway output (Qwen
    CoT averages 5.7K tokens) is bounded and then flagged.

**S2. A 200 response with an `error` body or empty `choices` is not retried.**
Applied: N-prop.
- Where: the same success branches.
- Fix: if `data.get("error")` or `not data.get("choices")`, append to `attempt_errors`, sleep
  and continue.

**S3. Non-retryable 400/401/402/403 are retried, then written as sentinel failures that count
as a complete run.** Applied: N-prop.
- Where: every retry loop.
- Fix: raise immediately on 401, 402 and 403 (and 400 after logging) so the run aborts instead
  of being saved.

**S4. A_E: empty retrieval is scored as a success, and distances are not logged.**
Applied: N-prop.
- Where: `Example-Guided` L342–366 and L531–547.
- Fix: keep `results['distances']` and log `rag_exemplar_distances`. Treat `retrieved == []`
  as a failure (sentinel) rather than scoring without context.

**S5. A_H counts an API-exhausted extraction as a successful scenario in the diagnostics
JSON.** Applied: N-prop.
- Where: `LLM-Param` L808.
- Fix: `'scenario_failed': True`.

**S6. RAG-ablation Top-1 and Top-2 ignore the tie-break.** Applied: N (metric change).
- Where: `run_rag_ablation_experiments.py` `scenario_metrics`, L927–929.
- Fix: take `pred_top1` and `gt_top1` from `rank == 1`, and top-2 from `rank <= 2`. This is
  recomputable offline from `pred_rank` and `gt_rank`.

**S7. The RAG ablation has no checkpoint; 7,560 calls run in one process.** Applied: N.
- Where: `run_rag_ablation_experiments.py` `run()` and `build_result_rows`.
- Fix: write a per-(ablation, model) xlsx and skip completed ones on restart. Until then, run
  it in a stable session and keep the raw jsonl.

**S8. Resume has no collection-window guard.** Applied: N-prop.
- Where: `sentinel_utils._is_complete_run_file` callers.
- Fix: refuse to resume a run whose diagnostics JSON lacks `collected_utc` or predates a
  configured `RERUN_START_UTC`.

**S9. Prompt-ablation control arms are not byte-identical to the main-run prompts** ("(0-1)"
and the A_E layout). Applied: N.
- Where: `run_prompt_ablation_experiments.py` `build_user_prompt` and `build_messages`.
- Fix: for `control`, call the architectures' own `build_user_prompt` and
  `build_user_prompt_with_rag`. It's the author's call, since it changes the arm definition.

**S10. `emit_collection_window.py` still uses file mtimes and git dates.** Applied: N.
- Where: `paper_pipeline/emit_collection_window.py`.
- Fix: read `collected_utc` from the diagnostics JSON and raw jsonl for the new runs.

### NOTE

**N1. RAG ablation: `_is_transient_http_status` was not imported,** so the logged HTTP error
was masked by a `NameError`. Applied: **Y**.

**N2. Raw-log additions to all four experiment scripts** (Section 3.3). Applied: **Y**.

**N3. The A_H order-arm control may be redundant with a timestamped rerun.** Applied: N.
It is kept in the plan because the S2 permutation design uses 13 runs.

**N4. Raw-log size.** Applied: N. The prompt ablation will write about 91K records; Qwen CoT
reasoning text alone could reach about 130 MB. The system prompt is logged as a sha256, not
in full; the text is in the code.

**N5. `order_runs` is an end index, not a count.** Applied: N.
- Where: hybrid `main()`, L1408.
- `--order-run-start 4 --order-runs 5` collects runs 4 and 5. The help text says "repeat
  runs".

**N6. The stored B60 rank-change count is now 47, not 57.** Applied: N. The likely cause is
the later 10-dp rounding.

**N7. Paper strings to update at S4.** Applied: N (S4).
- Where: supplement L201; main L734.
- Change: new IDs, `:floor` instead of `:exacto`, the price date, Gemini 3.8 and DeepSeek V4
  Flash 0731, and the reasoning tier actually used.
