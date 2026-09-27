# INSTALL_MIGRATE_REPORT: architecture patch installed, ablation scripts migrated

Written 2026-09-27.

**Rules kept**
- No API call was made. Every test mocks `requests.post` and blocks `requests.Session.request`, and every Python command ran with `OPENROUTER_API_KEY` unset.
- Git was read-only (commands at the end).
- `model_config.py` and every `.tex` file are untouched.
- Prompts are byte-identical (section 4).
- Printed pipeline output is ASCII.

## 1. What was installed

The four files from `Analysis/rerun_prep/arch_new/` were copied over the live files:
- `Architectures/Direct_LLM_Scoring.py`
- `Architectures/Example-Guided_LLM_Scoring.py`
- `Architectures/LLM-Parameterized_Reference_Scoring.py`
- `sentinel_utils.py`

Each installed file is byte-identical to its `arch_new` copy. The CRLF line endings are kept.

**Drift check (no merge needed).** The live files had not changed since the patch was built:
- Their mtimes are 2026-08-13, 2026-08-17 and 2026-09-25; the patch was built on 2026-09-26 at 22:12.
- The last git commit touching them is `19862aa`, and they matched it.

`git apply --check` was run on a scratch git repo holding LF-normalised copies of the live files, never on the real tree:
- `ARCH_PATCH.diff` applied cleanly forward.
- The result equalled the `arch_new` copies byte for byte, ignoring CR.
- `git apply -R --check` on the `arch_new` copies also passed.

**Names removed or renamed.** None, in `sentinel_utils` or in any of the three architectures, and no function signature changed. An AST scan found every name imported or used as an attribute from `sentinel_utils` across the whole repo: 40 names, including `Analysis/`, `paper_pipeline/`, `tests/`, `Ground Truth Calculators/` and `Scenario Files/`. All 40 exist in the installed file.

**Provider pins.** `build_openrouter_payload` deep-copies `MODEL_SPECS[<entry whose openrouter_id is the model sent>]["provider"]` into the payload unchanged. That includes the author's new `"require_parameters": true`. The new test `test_payload_passes_model_specs_provider_pin_unchanged` checks two things:
- all four pins arrive exactly as written, with no key added or dropped;
- the payload holds a copy, not the `MODEL_SPECS` object itself.

It also checks the pin on the wire through each installed architecture's `query_openrouter`.

**RAG schema version.** `build_rag_index.RAG_SCHEMA_VERSION` = 4 = `EXPECTED_RAG_SCHEMA_VERSION` in the installed A_E.

## 2. Tests

The arch_new tests were ported into `tests/`:
- `tests/arch_patch_harness.py` loads the installed files.
- `tests/test_arch_patch.py` holds the 139 original cases plus the pin test.

The tests that compare against the replaced code (tie rounding, A_H key override, the A_H and A_D/A_E regressions) now read the pre-patch architectures read-only with `git show 19862aa:Architectures/<file>`. They skip if git is unavailable; `ARCH_PREPATCH_DIR` can point at a copy instead. None skipped.

| MODEL_KEY | `test_arch_patch.py` | `test_ablation_migration.py` (new) | existing `test_sentinel_aggregation_matching.py` | `tests/` total |
|---|---|---|---|---|
| gptoss | 140/140 | 28/28 | 46/46 | 214/214 |
| qwen | 140/140 | 28/28 | 46/46 | 214/214 |
| deepseek | 140/140 | 28/28 | 46/46 | 214/214 |
| gemini | 140/140 | 28/28 | 46/46 | 214/214 |

**Before the install:**
- `tests/` passed 46/46;
- `Analysis/rerun_prep/arch_new/tests` passed 139/139.

There are no new failures.

**`Analysis/rerun_prep/infra/test_retry_exhausted_logging.py`** now passes 3/3 after a small edit:
- Why it failed after the migration: its three checks each make 3 exhausted calls in one process, so the shared 5-in-a-row breaker correctly aborted the second check.
- The fix: `__main__` resets `sentinel_utils._consecutive_api_failures` before each check. That is the only change.

**Mutation check of the migration tests.** 11 mutants were built on scratch copies, each reverting one change: truncation parsed, empty content accepted, no abort flag or cancel (in each script), pins dropped, empty retrieval scored, the old Top-1 rule, checkpoint format 1, and no `api_diagnostics`. **All 11 were caught**, and every file was restored byte-identical (checked by sha256).

## 3. Gate and the A_H regression

**Pipeline gate** (`pipeline_gate.py after` → `diff` → `gate_checks.py`). It ran from scratch copies with `PROJECT_ROOT` repointed, so nothing under `Analysis/rerun_prep/pipeline/` was written. It ran three times:

| Run | G1 | G2 | G3 | G4 |
|---|---|---|---|---|
| before install | 66/68 | 33/36 | 48/48 | 5/5 |
| after install | 66/68 | 33/36 | 48/48 | 5/5 |
| after install + migrations | 66/68 | 33/36 | 48/48 | 5/5 |

- **The failures:** only the five known Gemini A_H tie cells (HVAC test 5): overall tau 0.923 → 0.920, HVAC 0.977 → 0.968. Each is labelled "explained" by `gate_checks`.
- **Stability:** `after.csv` and `gate.csv` are byte-identical across all three runs.
- **Against the committed `Analysis/rerun_prep/pipeline/after.csv`:**
  - the 18 `RobustnessComparison` rows that SCRIPT_FIXES removed are absent, as expected;
  - 6 `Table8_cost_per_run` values differ, the three DeepSeek and three Gemini `cost_usd` values. They already differ in the **before-install** run, so the install did not cause them. They follow the author's price-label edits in `model_config.py` (runbook D4).

**A_H parser on the 6,240 old responses** (4 models × 8 runs × 195, from `Output Files*/hybrid_order_reversal/*_raw.jsonl`), run through the installed `extract_all_with_ai`:
- **0** differ from the pre-patch code;
- **0** differ from the outcome stored at collection time.

For tie rounding, the pre-patch A_E and A_H mis-rank 40 of 40 noise-tie cases, and the installed code ranks all of them correctly.

## 4. Migration of the experiment scripts

### Prompt ablation and RAG ablation

Both now build the payload with `sentinel_utils.build_openrouter_payload` and post it with `sentinel_utils.openrouter_chat`, so they share the architectures' client.

**What they now send:**
- `max_tokens` 8192;
- the `MODEL_SPECS` provider pin of the model id sent;
- the same temperature and reasoning payload as before.

**Failed calls.** Each fails the call and puts the sentinel on that alternative. The codes stay lower-case, like the rest of each script:

| Condition | Code |
|---|---|
| `finish_reason` length (or a native max-tokens reason) | `failed_truncated`. The partial text is logged and never parsed, and the call is not retried. |
| null, empty or whitespace content | `failed_empty_response` |
| 400/404/422 twice | `failed_api_bad_request` (2 attempts) |
| retries exhausted | `failed_api_exhausted` (10 attempts; 429 is retried with backoff) |

**Fatal errors.** A 401/402/403, or the shared breaker (5 failed calls in a row), raises `OpenRouterFatalError`, which is a `RunAbort`. The script then:
1. archives the failing call in the raw jsonl;
2. sets a module `_ABORT` event, which each worker checks before its next call;
3. shuts the pool down with `cancel_futures=True`;
4. re-raises past every `except Exception`.

Nothing is left to look complete:
- **Prompt ablation:** the cell xlsx, `prompt_ablation_summary.xlsx` and the report are not written.
- **RAG ablation:** the unit is not checkpointed and no workbook is written.

**Tested behaviour with 4 workers and a 402 after 10 successes:**
- at most 14 POSTs (the 10 successes plus at most one in-flight call per worker), against the 72 or 90 the cell or unit would make;
- nothing written;
- rerunning the same command completes the cell.

**Raw jsonl record, per call:**
- `provider`, `response_id` (the generation id), `response_model`;
- `usage` in full, `cost` and `reasoning_tokens`;
- `finish_reason`, `native_finish_reason`, `truncated`, `failure_type`;
- `latency_ms`, `collected_utc` (UTC) and `model` (the id);
- `request_params`, which is the payload minus the messages, including `max_tokens` and `provider`;
- `attempts`, `retries` and `attempt_errors` (per attempt: status, kind, UTC and detail).

**What is unchanged:**
- CLI flags and their defaults, including `--workers 8`;
- checkpoint and resume;
- the prompt builders.

**Extra fixes:**
- **Prompt ablation, A_E arms.** A scenario with no exemplar retrieved now fails as `failed_rag_retrieval` without an API call. It used to be scored silently with no exemplar, which made it A_D. The record also logs `rag_exemplar_distances`, `rag_top_k`, `retrieval_error` and `api_called`.
- **RAG ablation.** The stale "--ablations nearest-neighbor" text in the missing-key error now names `nearest_neighbor_k3`.

**Prompt-hash proof.**
- Method: `requests.post` was mocked, and the exact `messages` of every call were captured with the same sample before and after the change (15 stratified test scenarios, seed 13).
- Prompt ablation: every variant × arch cell (7) × 4 models, 1,260 calls, 315 distinct prompts.
- RAG ablation: all 7 LLM arms × 4 models, 15 RAG scenarios, 1,260 calls, 309 distinct prompts.

| Script | Calls | sha256 mismatches of `messages` | Aggregate hash, before = after |
|---|---|---|---|
| prompt ablation | 1,260 | **0** | `6929a8fc09e5dbcf` |
| RAG ablation | 1,260 | **0** | `26f3cc503f0959af` |

The only payload difference is the added `max_tokens: 8192` and `provider` block. For example, qwen: `{"only": ["venice/fp8"], "allow_fallbacks": false, "require_parameters": true}`. The capture scripts are `capture_prompts.py` and `compare_prompts.py` in the session scratchpad.

### Hybrid order arm

Each jsonl record gains `api_diagnostics`:
- **Failed call:** A_H's `diag["api_diagnostics"]`, which carries `attempt_errors` and `request_params`. `api_diag` is empty in that case.
- **Successful call:** the captured call's fields (provider, generation id, `usage.cost`, finish_reason, reasoning tokens).

A 402 aborts the arm, and the checkpoint jsonl keeps only the completed scenarios. Both are tested.

### Position bias

No code change. It drives the installed A_D, so it inherits the pins, `max_tokens`, response metadata, truncation failure, the 5-in-a-row breaker and the fatal abort. Tested:
- pins on the wire and metadata in its raw jsonl;
- a truncated scenario gives sentinel ranks;
- 5 truncated calls in a row abort;
- a 402 aborts with no run xlsx, and only the completed scenario stays in its checkpoint.

## 5. Metric definition changes (RAG ablation)

**The author's rule.** A scenario whose run failed or is unscored counts as **wrong**, and the denominator is every scenario in the arm. "Failed or unscored" means any of:
- any alternative failed (API failure, truncation, empty reply, parse error);
- the copy-only `unscored` fallback fired;
- any alternative has no valid rank.

**Changed:**

| Metric | Before | Now |
|---|---|---|
| `top1_correct` / `top1_accuracy` | A partial failure could still score a hit from the surviving alternatives | Failed scenario = 0; mean over `n_scenarios` |
| `top2_correct` / `top2_accuracy` | Same | Same rule |

These feed:
- `rag_ablation_summary.xlsx` and `rag_ablation_summary_by_decision_type.xlsx`;
- the Friedman, post-hoc and bootstrap tests on `top1_accuracy`;
- the report.

**Added:**
- a per-row `scenario_failed` column;
- `n_failed_scenarios` in both summaries.

**Unchanged:**
- `kendall_tau`, `spearman_rho`, `score_mae` and `score_rmse`, which are not accuracy metrics and average the scored scenarios;
- the nearest-neighbour fallback default, still `tie`.

**Old checkpoints refused.** `CHECKPOINT_FORMAT` went from 1 to 2, so an old checkpoint is refused ("different configuration") rather than resumed under the new rules.

**Test and end-to-end run:**
- `test_ra_top1_counts_failed_scenarios_as_wrong` has 3 scenarios: one correct, one with a single truncated non-top alternative (a hit under the old rule), and one fully truncated. Top-1 = 1/3.
- A mocked end-to-end `run()` wrote the summaries, significance workbooks and report with the new columns.

**Not changed (author decision needed).** The prompt ablation still computes Top-1 over non-failed scenarios only (`summarize`: `ok["top1"].mean()`), which is the old rule. The brief limited the rule to the RAG script.

## 6. Truncation risk at max_tokens 8,192 (old logs)

**What the old logs hold.** Old per-call token counts exist only for A_H (the order-arm jsonl). The prompt-ablation cells and the RAG results hold each scenario's sum over its 3 calls. So the share of calls over 8,192 is reported as bounds:
- **Lower bound:** a sum above 3 × 8,192 forces at least one call over the cap.
- **Upper bound:** min(3, ⌊sum / 8,193⌋) calls.
- **Equal-split estimate:** all 3 calls count as over when sum / 3 > 8,192.

The denominator is scored calls. Full table: `paper/pass6/verify/truncation_risk_8192.csv`; script: `truncation_risk_8192.py`.

| Source | Model | Arm | Scored calls | Mean completion / call | Max 3-call sum | % calls > 8,192 (lower / equal split / upper) |
|---|---|---|---|---|---|---|
| prompt ablation | qwen | A_D cot_scaffold | 2,910 | 5,732 | 139,044 | **4.3 / 12.7 / 39.4** |
| prompt ablation | qwen | A_E cot_scaffold | 2,919 | 2,482 | 82,400 | **1.3 / 3.7 / 8.5** |
| prompt ablation | gemini (3.5) | A_D / A_E cot_scaffold | 1,754 / 1,753 | 649 / 643 | 2,415 / 2,539 | 0 / 0 / 0 |
| prompt ablation | deepseek (V4) | A_D / A_E cot_scaffold | 2,925 / 2,924 | 470 / 499 | 1,789 / 3,161 | 0 / 0 / 0 |
| prompt ablation | gptoss | A_D / A_E cot_scaffold | 2,920 / 2,886 | 261 / 325 | 1,728 / 2,021 | 0 / 0 / 0 |
| prompt ablation | all four | control, no_anchors, scale_0_10 (A_D and A_E) | — | 36–161 | ≤ 2,501 | 0 / 0 / 0 |
| RAG ablation | all four | all 7 LLM arms | 269–270 per arm | 35–156 | ≤ 699 | 0 / 0 / 0 |
| A_H order arm (exact per call) | all four | extraction | 1,560 each | 64–123 | max single call 247 | 0 |

**Reading the table:**
- Only Qwen's CoT arms are at risk. Under the new client those calls will fail as `failed_truncated`, so their scenarios fail.
- The Gemini and DeepSeek rows come from the old model versions (3.5, V4). Gemini 3.8 and DeepSeek 0731 have no history.
- The cap was not changed. The decision is flagged in the runbook (D9, step 6).

## 7. Backups

Every file overwritten was backed up first, with its path preserved, to:

`C:\Users\Ahaan\AppData\Local\Temp\claude\c--Users-Ahaan-LLM-MCDA-Paper\68915bc4-ce9d-42b7-bc8b-bc1fac60115c\scratchpad\pre_install_backup\`

The backed-up files:
- the three architectures and `sentinel_utils.py`;
- the four experiment scripts;
- `paper/pass6/RERUN_RUNBOOK.md`;
- `Analysis/rerun_prep/infra/test_retry_exhausted_logging.py`.

## 8. Files for the author to commit

**Changed:**
- `Architectures/Direct_LLM_Scoring.py`
- `Architectures/Example-Guided_LLM_Scoring.py`
- `Architectures/LLM-Parameterized_Reference_Scoring.py`
- `sentinel_utils.py`
- `Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py`
- `Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py`
- `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`
- `Analysis/rerun_prep/infra/test_retry_exhausted_logging.py`
- `paper/pass6/RERUN_RUNBOOK.md` (gitignored)

**New:**
- `tests/arch_patch_harness.py`
- `tests/test_arch_patch.py`
- `tests/test_ablation_migration.py`
- `paper/pass6/verify/INSTALL_MIGRATE_REPORT.md` (this file)
- `paper/pass6/verify/truncation_risk_8192.csv`
- `paper/pass6/verify/truncation_risk_8192.py`

**Not mine (already modified or untracked before this work):**
- `model_config.py`
- `paper/pass6/verify/apply_scenario_fixes.py`
- `paper/pass6/verify/scenario_fixes.json`
- `paper/pass6/verify/compare_scenario_workbooks.py`
- `Scenario Files/build_scenario_workbooks.py`
- `Scenario Files/rag_membership.json`

**Not modified:** `run_position_bias_control.py`.

## 9. Notes for the author

1. **Qwen CoT truncation (D9).** Accept the estimated 4–39% (A_D) and 1–9% (A_E) failed calls, or raise the cap for that arm before collecting.
2. **Prompt ablation Top-1** still excludes failed scenarios (section 5). Decide whether it should follow the RAG rule.
3. **The breaker counter** `_consecutive_api_failures` is a process-wide global incremented without a lock. With 8 workers the count is approximate but still trips. It also spans cells and units within one process, which is intended.
4. **After a fatal abort** the aborted cell's or unit's raw jsonl keeps the aborted pass's records. The files are append-only, and each record carries its own `collected_utc`.
5. **Pinned commit.** The tests pin the pre-patch reference to commit `19862aa`. After the install is committed that commit still exists, so the comparisons keep working.
6. **Old workbooks.** The old `Analysis/RAG_Ablation/` workbooks were computed under the old Top-1 rule. They were not recomputed, and they are moved aside before the rerun anyway (runbook section 0.1).

## Git commands run (all read-only on the repo)

On the repo:
- `git status --short` (several times)
- `git diff model_config.py`
- `git diff --stat` (with paths and with `--ignore-cr-at-eol`)
- `git log -3 --format=... -- Architectures/ sentinel_utils.py`
- `git log -3`
- `git config core.autocrlf`
- `git ls-files --eol ...`
- `git ls-files <file>`
- `git check-ignore ...`
- `git show 19862aa:<path>`, run by me and by the test harness

On a separate scratch repo in the scratchpad (not this repository): `git init`, `git apply --check`, `git apply`, `git apply -R --check`.

No commit, add, checkout, stash, reset or restore was run.
