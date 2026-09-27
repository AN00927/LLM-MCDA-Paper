# ARCH_PATCH_REPORT: pre-rerun patch for the three architectures

Written 2026-09-26. Scope: items 1-14 of the pre-rerun brief, drawn from `V_INFRA.md` sections 1.1-1.3, 3, 4 and 5 and from `V_PIPELINE.md` sections 2, 4 and 7 and its Discrepancies table.

**Nothing live was edited.** `Architectures/`, `sentinel_utils.py` and `model_config.py` are unchanged; `git status` confirms it. All work is in `Analysis/rerun_prep/arch_new/`:

| File | What it is |
|---|---|
| `Direct_LLM_Scoring.py`, `Example-Guided_LLM_Scoring.py`, `LLM-Parameterized_Reference_Scoring.py` | Patched copies, CRLF like the live files. They are drop-in: `PROJECT_ROOT = parents[1]` is unchanged, so they work once copied into `Architectures/`. |
| `sentinel_utils.py` | Patched copy (LF, like the live file). |
| `ARCH_PATCH.diff` | Unified diff, live to copy, all four files (line endings ignored). |
| `tests/harness.py`, `tests/test_arch_patch.py` | Mocked tests, 139 cases. |
| `tests/test_run_output.txt` | Output of the last test run: 139 passed. |
| `token_evidence.py`, `token_evidence.csv` | The evidence behind `MAX_OUTPUT_TOKENS`. |

**Install (author).** Copy the four `.py` files over `Architectures/*.py` and `sentinel_utils.py`. `model_config.py` is not touched.

**Rules kept.**
- No LLM or API call was made. The only network use was WebFetch of OpenRouter docs.
- Git was read-only: `git status --short` and `git log --oneline -1 -- sentinel_utils.py`.
- Prompt text and scoring logic are unchanged except where an item below required a change. For A_H this is proven on 6,240 historical responses. For A_D and A_E it is proven on a synthetic response corpus (section T).

---

## Design in one paragraph

The retry loop that all three `query_openrouter` functions used to duplicate now lives once, as `sentinel_utils.openrouter_chat` (L505). Each architecture's `query_openrouter` keeps its signature and return contract and calls it:
- A_D returns `(None, diag)` on failure.
- A_E and A_H raise on failure, now as `OpenRouterCallFailed`. It subclasses `Exception`, and its message still starts with the failure code, so the old string checks still work.

Because the loop exists once, the new policy is implemented once and tested once: fatal statuses, a single retry for bad requests, retry of a 200 that carries an error, truncation, `attempt_errors` and `request_params`.

Every scoring or extraction call writes exactly one raw record. The record is written after validation, so it carries the outcome (`failure_types`, `scores_valid` / `extraction_success`). If validation itself raises, or the process aborts, the call is still archived before the exception propagates.

---

## Items

Line numbers refer to the copies in `arch_new/`. SU = `sentinel_utils.py`, AD = Direct, AE = Example-Guided, AH = LLM-Parameterized.

### 1. Tie rounding
**Change:**
- Per-run ranking: the local `apply_mavt_ranking` rounds with `round(weighted_sum, MAVT_ROUND_DECIMALS)` at AE L732 and AH L743.
- Averaged-results ranking: `.round(MAVT_ROUND_DECIMALS)` at AD L853, AE L1200 and AH L1363.
- A_D's per-run path already used the shared, rounded function.

**Evidence:**
- `test_tie_rounding_per_run_ae_ah` builds 20 pairs of 2-dp score vectors whose weighted sums are exactly equal in decimal but differ as floats, in the direction opposite to `TIE_BREAK_PRIORITY`.
  - Patched AE and AH match `sentinel_utils.apply_mavt_ranking` on all 20.
  - The live AE and AH mis-rank all 40 of 40.
- `test_tie_rounding_aggregate[AD|AE|AH]` plants such a tie in a per-run file. The aggregate workbook then ranks it by the tie-break.

### 2. A_H key restriction
**Change:**
- `EXTRACTION_REQUIRED_PARAMS` (AH L218) is now the only list of extraction keys. The completeness check uses it (L610).
- The merge over the scenario keeps only those keys (L656-659).

**Evidence:** `test_ah_key_override_blocked`.
- The historical HVAC reply was sent with extra keys injected: `question`, `hvac_mode`, `location`, `outdoor_temp`, `utility_budget`, `household_size`, `square_footage`.
- The patched A_H scores it identically to the clean reply.
- The live A_H scores it differently, which confirms the override was possible.

### 3. Response metadata (M3)
**Changes in SU:**
- `response_meta(data)` (L401). It has the same fields as the ablation helper: `response_id`, `response_model`, `provider`, `system_fingerprint`, `finish_reason`, `native_finish_reason`, the full `usage`, `reasoning` and `body_error`.
- `openrouter_chat` also returns:
  - `request_params`: the payload minus the messages;
  - `attempt_errors`: one entry per failed attempt, with `attempt`, `utc`, `status`, `kind` and a 500-character `detail` excerpt;
  - `attempts`, `retries`, `truncated`, `reasoning_tokens` and `cost`.
- `call_log_fields()` (L660) spreads all of these into each raw record.

**Each raw record also carries:**
- `architecture`;
- `system_prompt_sha256` (`None` for A_H, which sends no system prompt);
- `run` and `scenario_id`, both as before, from `RawCallLog`;
- `failure_types`;
- the parse outcome: `scores` and `scores_valid` for A_D and A_E; `parsed`, `extraction_success` and `extraction_error` for A_H.

A_E also logs `rag_top_k`, `rag_exemplar_ids` and `rag_exemplar_distances`.

**Record sites:**
- AD: `_record_call`, L338.
- AE: the `_record` closure in `score_alternative_with_rag`, L511 onward.
- AH: the `_record` closure in `extract_all_with_ai`, L438 onward.

**Diagnostics JSON sums:**
- New: `total_cost_usd`, `total_tokens_reasoning` and `calls_with_cost`, which says how many calls the cost total covers. They use `init_usage_totals`, `add_call_usage` and `merge_usage_totals` (SU L679 onward).
- Prompt and completion token totals were already summed.

**Usage accounting:** the payload does not carry `usage: {include: true}`. OpenRouter's usage-accounting page (fetched today) says that parameter and `stream_options.include_usage` "are deprecated and have no effect", and that "Full usage details are now always included automatically in every response." I left it out rather than send a no-op field alongside `require_parameters: true`. The tests assert that `usage.cost` is read from the response. **Author: say if you want the field sent anyway; it is one line in `build_openrouter_payload`.**

**Evidence:** `test_response_kinds` checks every one of these fields on every record, for all 11 response kinds × 3 architectures × 3 decision types (99 cases). It also checks the cost and reasoning-token sums in the result diagnostics. `test_run_test_set_outputs` checks the JSON totals: 9 calls × cost for A_D and A_E, 3 for A_H.

### 4. Null content, empty choices, error body (M4, S2)
**Change:**
- `message_content()` (SU L430) never returns `None`: `content: null` becomes `""`, and a list of content parts is joined.
- `_body_problem()` (SU L481) flags an `error` body, missing or empty `choices`, or a choice with `error` / `finish_reason: "error"`. Such a 200 is retried like a transient error and logged in `attempt_errors` with `kind: "error_in_200_body"`.
- The debug f-strings no longer slice `None`: A_H and A_E now use `(response_text or '')`.
- The `DEBUG_API` block that printed message keys was removed along with the old loops. That block is where A_D crashed. The raw record now holds the same information.

**Evidence:**
- `null_content`: no exception, one POST, sentinel scores. The record keeps `response: ""` and the reasoning text. The failure codes are the existing ones for an empty reply: A_D `FAILED_UNKNOWN`, A_E `EXTRACTION_INVALID_JSON`, A_H `FAILED_EXTRACTION_NON_JSON_WRAPPER`.
- `empty_choices_then_ok` and `error_body_then_ok`: 2 POSTs, success, and one `attempt_errors` entry with status 200.
- `empty_choices_always`: 10 POSTs, then `FAILED_API_EXHAUSTED`.

### 5. A_E `api_success` (M5)
**Change:** A_E now logs `api_success = response_text is not None`, which is true whenever the API returned a body (AE L564). The same rule applies in A_D and A_H.

**Evidence:**
- `test_ae_success_logs_distances_and_true_api_success`.
- The mutation "AE api_success False" is caught.

### 6. Per-run xlsx columns (M6)
**Change:**
- Every per-run row gets `collected_utc`, the UTC ISO time at which that scenario's calls finished, and `model_id` (`API_CONFIG["model"]`). The fieldnames are at AD L526, AE L843 and AH L159; the per-scenario stamp at AD L625, AE L954 and AH L1054.
- The diagnostics JSON keeps `collected_utc` (the start, for existing readers) and adds `collected_utc_start`, `collected_utc_end`, `architecture`, `model_id` and `max_output_tokens`. A_E also records `rag_top_k`.

**Evidence:** `test_run_test_set_outputs[AD|AE|AH]` parses each timestamp and checks it is UTC.

### 7. Provider routing (M2)
**Change:**
- `build_openrouter_payload` (SU L457) adds `"provider": provider_prefs_for_model(model)` (L444).
- That function returns `MODEL_SPECS[<entry whose openrouter_id is the model sent>].get("provider", DEFAULT_PROVIDER_PREFS)`, and `DEFAULT_PROVIDER_PREFS = {"require_parameters": True}` (SU L49).
- The lookup is by the id actually sent, not by `MODEL_KEY`. Position bias and the order arm repoint `API_CONFIG["model"]` per `--model`, so they get that model's routing.
- `model_config.py` is untouched.

**Evidence:**
- `test_provider_prefs_follow_model_id`.
- Every POST in `test_response_kinds` carries `provider`.

### 8. Truncation (S1)
**Change:**
- `max_tokens = MAX_OUTPUT_TOKENS` on every payload (SU L44, value **8,192**).
- A reply with `finish_reason == "length"`, or with `native_finish_reason` in {length, max_tokens, max_output_tokens}, is `truncated`. It is not retried.
- It fails as `FAILED_TRUNCATED` (SU L29) with sentinel scores. The partial text is kept in the raw record and is never parsed. The checks are at AD L387, in AE `_validate_scores` L641 onward, and in AH `_parse_extraction` L526 onward.
- `FAILED_TRUNCATED` is added to all three failure-counter lists.

**Evidence:**
- `truncated` and `truncated_valid_json`. The second is the V_INFRA §4.1 case: parseable JSON with `finish_reason: length`, which the live code accepts as a success. Now it gives sentinels, `FAILED_TRUNCATED`, one POST, and a record with `truncated: true`.

#### Token evidence behind 8,192 (`token_evidence.csv`)
No architecture ever logged per-call tokens for A_D or A_E. I used:
- per-run means from the shipped diagnostics JSON;
- exact per-call counts for A_H, from the order-arm raw jsonl;
- per-scenario sums of 3 calls from the prompt-ablation cells. A sum is an upper bound on the largest single call in it.

Completion tokens include reasoning tokens.

| Model (historical) | A_D | A_E | A_H (per call, exact) |
|---|---|---|---|
| DeepSeek V4 Flash | run-mean 507 (max run 601); control: 3-call sum p99 111, max 115 | run-mean 36; 3-call sum max 111 | mean 64, p99 68, **max 69** |
| Gemini 3.5 Flash | run-mean 41; 3-call sum p99 154, max 158 | run-mean 87 (max run 154); 3-call sum max 156 | mean 75, p99 86, **max 87** |
| GPT-OSS 20B | run-mean 140; 3-call sum p99 621, max 828; no-anchors sum **max 2,501** | run-mean 146; 3-call sum max 713; RAG ablation row max 699 | mean 123, p99 197, **max 247** |
| Qwen3.5 9B | run-mean 38; 3-call sum p99 127, max 214 | run-mean 38; 3-call sum max 123 | mean 73, p99 80, **max 82** |

Reading the table:
- The largest shipped-prompt bound anywhere is 2,501 tokens. That is a sum of three calls, so it overstates any single call. 8,192 is more than 3× that bound and more than 13× the largest run mean (DeepSeek A_D, 601, the reasoning leak noted in V_INFRA).
- 8,192 is within every model's max output: gpt-oss 32,768, Gemini 65,536. It also equals SiliconFlow's gpt-oss cap, the smallest endpoint listed.
- A runaway call at Gemini's standard price costs at most about $0.03.
- The CoT prompt-ablation arm reaches 139,044 tokens per Qwen scenario. That arm is outside this cap: the ablation scripts have their own `query_openrouter`.

**Caveat (author):** there is no history for Gemini 3.8 (mandatory reasoning) or DeepSeek 0731. The smoke test should report the maximum `completion_tokens` and `reasoning_tokens` per model. If either comes within 2× of 8,192, raise the cap before collecting.

### 9. Non-retryable errors (S3)
**Change in SU:**
- **401, 402 and 403** raise `OpenRouterFatalError` on the first response, with a clear message and no retry.
- It subclasses `RunAbort(BaseException)` (L362). It is deliberately not an `Exception`: the run loops, position bias and the order arm all wrap scenarios in `except Exception`, and an abort must pass through all of them.
- Before re-raising, the architectures archive the failing call. `run_multi_and_aggregate` logs `ABORT` to the events log and re-raises. No per-run xlsx or diagnostics JSON is written for that run, so a resume re-collects it.

**400**, and also 404 and 422 (see decisions):
- logged, retried once (`BAD_REQUEST_MAX_ATTEMPTS = 2`);
- then the call fails as the new code `FAILED_API_BAD_REQUEST`.

Transient errors keep the shared `MAX_RETRIES` and backoff policy.

**Evidence:**
- `test_fatal_status_aborts[AD|AE|AH × 401|402|403]`: exactly 1 POST. The abort passes through a surrounding `except Exception`, and the raw record carries `failure_types: ["FATAL_HTTP_402"]`.
- `test_run_multi_fatal_aborts_without_saving`: a 402 inside `run_multi_and_aggregate`, with `N_RUNS=2`, leaves no run file and no aggregate, and the events log shows START then ABORT.
- `400`: 2 POSTs per call.
- `429_then_ok`: 2 POSTs, `retries: 1`, one sleep.
- `timeout_always`: 10 POSTs.

### 10. A_E retrieval (S4)
**Change:**
- `retrieve_similar_scenarios` keeps each Chroma `distance` (AE L352). It takes an optional `error_out` list. Its return type is unchanged, so the prompt ablation still works.
- If no exemplar is retrieved (Chroma raised, the index is not initialised, or there are zero results), the call fails as `FAILED_RAG_RETRIEVAL` (SU L32) with sentinels. **No API call is made.** The raw record carries `api_called: false` and `retrieval_error` (AE L573).
- Five such calls in a row raise `RunAbort` (`MAX_CONSECUTIVE_RETRIEVAL_FAILURES`, SU L66).

**Evidence:**
- `test_ae_retrieval_failure[raise|empty|uninitialised]`: 0 POSTs, 3 records, and the counter reads 3.
- `test_ae_consecutive_retrieval_failures_abort`.
- `test_ae_real_chroma_retrieval_distances`: against a copy of the real `chroma_rag_db` and the cached MiniLM model, offline. Each decision type returns 1 exemplar of its own type, with a float distance.

### 11. A_H diagnostics (S5)
**Change:** an API-exhausted or bad-request extraction now returns `scenario_failed: True` (AH L789, L816). It keeps the real alternative names and the decision type.

**Evidence:**
- `test_ah_api_exhausted_marks_scenario_failed`.
- The mutation "AH S5 reverted" is caught.

### 12. Resume guard (S8)
**Change:**
- `run_file_state()` (SU L246) returns `missing`, `complete` or `old_format`. `old_format` means readable rows but no `collected_utc` column.
- `run_multi_and_aggregate` **refuses to start** (`RuntimeError`, before any call) if any run slot holds an old-format file. It neither resumes nor overwrites it.
- Every START, SKIP, DONE, FAILED, ABORT and REFUSED event is appended with a UTC stamp to `<base>_events.log` beside the outputs, for example `Direct_LLM_Scoring_results_events.log`. I checked the name: it matches none of the pipeline's `*_results_run_*` globs.
- The shared `_is_complete_run_file` is unchanged. Position bias still uses it, and its files already carry `collected_utc`.

**Evidence:**
- `test_resume_guard[AD|AE|AH]`: a complete new-format run is skipped and logged, with 0 POSTs. An old-format run is refused, with 0 POSTs, the file byte-identical and REFUSED logged.
- `test_run_file_state_missing_and_tmp`.

### 13. A_E retrieval count
**Change:**
- The benchmark value in code was `RETRIEVE_K = 1`, now `DEFAULT_RETRIEVE_K = 1`.
- `RETRIEVE_K = int(os.getenv("RAG_TOP_K", "1"))`, which must be ≥ 1 (AE L117-118).
- `main()` adds `_k<k>` to the output file names only when k ≠ 1 (L1237), for example `Example-Guided_LLM_Scoring_k3_results_run_01.xlsx`. The pipeline globs `Example-Guided_LLM_Scoring_results_run_*.xlsx` never match those files.
- k is logged in each raw record and in the diagnostics JSON.

**Evidence:** `test_ae_rag_top_k_env`. With k = 3, Chroma is queried with `n_results=3`, and the records hold 3 ids and 3 distances. The file names are k-tagged, and the default names are unchanged.

### 14. Callers
- `test_position_bias_normalize_result_compat` and `test_hybrid_order_arm_capture_compat` import the real scripts and drive them with the patched modules.
- `tests/test_sentinel_aggregation_matching.py` passes 46/46 with the patched `sentinel_utils`.
- `Analysis/rerun_prep/infra/test_retry_exhausted_logging.py::check_position_bias` passes against the patched A_D.

For what each script needs, see the next section.

---

## Adaptations needed in other scripts (not edited; read-only)

1. **`run_prompt_ablation_experiments.py` and `run_rag_ablation_experiments.py` (important).** Each has its own `query_openrouter`, and together they make about 100K of the 135K rerun calls. Neither sends `max_tokens` or `provider`. Both retry 401/402/403 ten times and save the result, and neither fails a `finish_reason: length` reply.
   - Recommended: build the payload with `sentinel_utils.build_openrouter_payload` and post it with `sentinel_utils.openrouter_chat`.
   - Both scripts run `ThreadPoolExecutor` workers. `OpenRouterFatalError` raised inside a worker surfaces at `future.result()`, so the main loop must let it propagate.
   - The consecutive-failure counter is a plain module global. That is safe for the serial architectures. With 8 workers it is only approximate: the increment is not locked. It still trips; the count can be off by a few.
2. **Prompt ablation, A_E arms.**
   - They still score **with no exemplar** when retrieval is empty. S4 is not applied there: check `retrieved` and fail as `FAILED_RAG_RETRIEVAL`.
   - `retrieved` dicts now carry `distance`, which could be logged.
   - **`RAG_TOP_K` must be unset** when this script runs, because it uses `ae.RETRIEVE_K`.
3. **`run_hybrid_ablation_experiments.py` (order arm).**
   - Works unchanged. On success, `instrument_capture`'s `api_diag` now carries provider, id, usage, `request_params` and `attempt_errors`.
   - On an API failure the wrapper's `original(...)` raises, so `api_diag` stays empty. `extract_all_with_ai` now returns those fields under `diag["api_diagnostics"]`. Add `"api_diagnostics": diag.get("api_diagnostics")` to the jsonl record in `collect_order_arm` to keep the attempt log of failed calls.
   - A fatal status now aborts the arm. Its checkpoint jsonl keeps the completed scenarios.
   - Truncated extractions count as `extraction_failed` and are retried on resume.
4. **`run_position_bias_control.py`.** No change needed. It gains every new raw-log field through A_D. Its per-row `collected_utc` is the arm start time, not the per-scenario time (optional).
5. **`generate_paper_results_numbers.py`, Table 8 (M9, D3).** Price the table from the new `total_cost_usd`, using `calls_with_cost` as a coverage check. Keep label prices only as a fallback.
6. **`emit_collection_window.py` (S10).** Read `collected_utc_start` / `collected_utc_end` from the diagnostics JSON, and the per-row `collected_utc`.
7. The per-run xlsx gains two trailing columns, `collected_utc` and `model_id`. All the readers I checked select columns by name: `calculate_per_run_metrics`, `cluster_bootstrap_ci`, `compute_dispersion_diagnostics`, `evaluate_parameter_extraction`, and the aggregators inside the architectures.

---

## Decisions for the author

1. **`MAX_OUTPUT_TOKENS = 8192`.** Confirm it against the Gemini 3.8 and DeepSeek 0731 smoke-test token counts.
2. **Per-model `provider` entries in `MODEL_SPECS`.** Without them every call sends `{"require_parameters": true}` only, so `:floor` still varies the provider and the quantization. V_INFRA §1.2 recommends a pinned `order` with `allow_fallbacks: false`. The code reads the entry if you add one.
3. **`usage: {include: true}`** is not sent: it is deprecated and has no effect (item 3).
4. **Behaviour beyond the literal brief.** Each item can be reverted with one constant:
   - **Consecutive-failure breaker.** Five calls in a row without a usable completion (exhausted, bad request or truncated) raise `OpenRouterFatalError` (`MAX_CONSECUTIVE_API_FAILURES = 5`; 0 disables). It exists because an unsupported parameter, such as Gemini's `minimal` effort (M8), would otherwise fail every call and save a complete sentinel run.
   - **404 and 422** get the same one-retry treatment as 400, because OpenRouter returns 404 "no endpoints" when `require_parameters` or a pinned provider matches nothing.
   - **New code `FAILED_API_BAD_REQUEST`**, so that a rejected request is not counted as an outage.
   - **Old-format run files are refused rather than overwritten**, to protect un-snapshotted data. Move them aside, per M1.
   - **Retrieval streak abort** (item 10).
5. **Not added (possible follow-ups):**
   - `Retry-After` is not honoured; 429 and 503 use the fixed backoff.
   - There is no scenario-level failure-streak abort. The historical maximum streak of failed scenarios in any run is 4 (GPT-OSS A_H). But the Test sheet is ordered by decision type, so a model that legitimately fails one type would trip such a breaker.
   - An empty `content` with `finish_reason: stop` is not retried. It keeps each architecture's existing failure code, which differs between architectures (item 4). A shared `FAILED_EMPTY_RESPONSE` would make the three comparable.
6. **Pre-existing quirks, left as they were:**
   - In A_D and A_E, a reply that parses as JSON but not as an object (for example `0.5`) raises in validation and crashes the whole scenario. The raw record is now written before the crash.
   - A_E counts a retrieval failure in `api_calls` even though no call was made.
   - The per-call `[WARN] reasoning_tokens > 0` line will fire on every gpt-oss and Gemini call.
   - Reasoning text is now logged in full. V_INFRA N4 flags this for size; it matters most for the ablations, not the architectures.

---

## Test evidence summary (T)

`OPENBLAS_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest Analysis/rerun_prep/arch_new/tests -q`: **139 passed** (29 s). Output is in `tests/test_run_output.txt`.

**How the tests run.**
- No network: `requests.Session.request` is replaced with a function that raises, the API key is a dummy, and `requests.post` is mocked in every test.
- Each copy is executed with `__file__` set to its future `Architectures/` path, so it runs the real `run_scenario`, `run_test_set` and `run_multi_and_aggregate` against the real scenario sheet and calculators.

**Coverage.**
- **Response kinds (99 cases).** Normal success with usage, cost, provider and id; `content: null` with reasoning; `choices: []` then success; `choices: []` always; a 200 error body then success; `finish_reason: length` with partial text; `finish_reason: length` with valid JSON; 429 then success; timeout then success; timeout always; 400.
  - Each runs on 3 architectures × 3 decision types.
  - Asserted: failure code, sentinel on failure, POST count, `attempt_errors` content, the full raw-record schema, and payload `max_tokens` / `provider` with no `usage` field. The diagnostics sums (cost, reasoning tokens, `calls_with_cost`, failure counters) are asserted for A_D and A_E; for A_H the per-call cost and reasoning tokens are asserted on success.
- **Fatal statuses (9 cases).** 401, 402 and 403 × 3 architectures abort through `except Exception`. Also tested: the consecutive-400 breaker, the success reset, and a fatal status inside `run_multi_and_aggregate`.
- **Per-run outputs.** Columns, UTC timestamps, JSON sums, raw jsonl, the resume guard (skip, refuse, byte-identical file), and the `.tmp` / missing file states.
- **A_E.** Retrieval failure in 3 modes, the retrieval streak abort, `RAG_TOP_K=3` (query k, logged ids and distances, file names), and real Chroma distances.
- **Ties, per run and aggregate.** Live A_E and A_H mis-rank 40/40 of the noise ties; the patched copies rank all correctly.
- **A_H key override.** The patched output is invariant to injected keys; the live output is not.
- **Regression.**
  - **A_H.** All 6,240 stored order-arm responses: 4 models × 8 runs × 195, from `Output Files*/hybrid_order_reversal/*_raw.jsonl`. Each went through the patched and the live `extract_all_with_ai`. **0 differ from the live code; 0 differ from the outcome stored at collection time.**
  - **A_D and A_E.** No raw responses exist for these architectures. An 11-shape synthetic corpus gives identical scores, failure codes and success flags from the live and patched scorers:
    - fenced and unfenced JSON;
    - out of range, negative, string score, bool score, missing key;
    - prose wrapper, non-JSON, and surrounding whitespace.
- **Callers.** Position bias `normalize_result` works on patched A_D results. The hybrid `instrument_capture` works on success, exhausted, truncated and fatal replies, and its captured record is JSON-serialisable.

**Mutation check** (scratch script, not shipped). Each mutant reverts one change in a scratch copy, and the suite must then fail. **14/14 failed**:
- truncation ignored;
- no fatal abort;
- 400 retried 10×;
- a 200 error body accepted;
- no provider;
- A_E `api_success` forced False;
- A_E rounding removed;
- A_H rounding removed;
- A_H key restriction removed;
- S5 reverted;
- no `collected_utc` column;
- empty retrieval scored;
- A_D aggregate rounding removed;
- old-format files resumed.
