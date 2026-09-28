# PHASE1_CODE_CHANGES_REPORT: cot_scaffold max_tokens, failure-as-wrong Top-1/Top-2, thread-safe breaker

Written 2026-09-27.

Rules kept: no paid API call was made (OPENROUTER_API_KEY was unset in every shell; every test
mocks requests.post and requests.get; network to openrouter.ai and huggingface.co is blocked in
this sandbox anyway). No git commit, push, checkout, stash or reset was run. Git was read-only:
`git status --short`, `git diff --stat`, and `git show HEAD:<path>` to pull original copies of
the three files I edited into /tmp for comparison and the prompt-hash proof. model_config.py, all
.tex files, and CLAUDE.md were not touched. I own and edited only sentinel_utils.py,
Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py, Miscellaneous
Scripts/validation/test_prompt_ablation_significance.py, and new test files under tests/. I did
not touch Ground Truth Calculators/, Scenario Files/, docs/, or run_rag_ablation_experiments.py.

## Task a: cot_scaffold max_tokens

Added to run_prompt_ablation_experiments.py:

- `COT_MAX_TOKENS_CAP = 32768` and a module-level `COT_MAX_TOKENS` dict.
- `_pinned_provider_tag(model_key)`: reads the single provider string from
  `MODEL_SPECS[model_key]["provider"]["only"]`.
- `_endpoint_matches_pin(endpoint, tag)`: matches an /endpoints entry by its own `tag` field
  first, falling back to `<provider_name>/<quantization>` lower-cased if `tag` is blank. This
  covers both plausible response shapes since the exact field OpenRouter uses was not directly
  observable from this sandbox.
- `_fetch_endpoint_max_completion_tokens(model_key)`: GETs
  `https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints` (author/slug parsed from the
  model id with the `:floor` suffix stripped), finds the pinned endpoint, and returns its
  `max_completion_tokens`. Raises RuntimeError with a clear ASCII message on any failure: network
  error, non-200 status, unparseable body, no endpoints, no match for the pinned tag, or a null
  max_completion_tokens. Never falls back silently.
- `resolve_cot_max_tokens(model_keys, override=None)`: called once per run, before any
  cot_scaffold cell is collected (main() calls it right after the shipped-prompt drift check, and
  only when "cot_scaffold" is in the requested variants). With `override` set (the new
  `--cot-max-tokens N` CLI flag) it skips the GET entirely and uses `min(32768, N)` for every
  requested model. Without it, each model's cap is `min(32768, the pinned endpoint's
  max_completion_tokens)`, fetched fresh (not cached) so a rerun in the same process reflects the
  endpoint's current state. A failed lookup for any one model aborts before anything is collected.
- `_max_tokens_for(variant, model_key)`: returns `COT_MAX_TOKENS[model_key]` for the cot_scaffold
  variant, `sentinel_utils.MAX_OUTPUT_TOKENS` (8192) for every other variant. If a cot_scaffold
  cell is scored without the cap having been resolved first, this raises rather than defaulting to
  8192.
- `score_scenario` computes this cap once per scenario and threads it into `query_openrouter(...,
  max_tokens=cap)` on every alternative's call, and into the raw log record as a top-level
  `max_tokens` field (recorded on every record, including the no-API-call RAG-retrieval-failure
  path, since the cap is fixed by variant and model and known regardless of whether a call
  happened).
- `query_openrouter` and `sentinel_utils.build_openrouter_payload` both gained an optional
  `max_tokens=None` parameter. `build_openrouter_payload` sends `MAX_OUTPUT_TOKENS` when it is
  None (every other caller: the three architectures, the RAG ablation, the hybrid ablation, all
  still call it with two or three positional/keyword args and are unaffected) and the given value
  otherwise.

Judgement call: the exact JSON shape of an OpenRouter /endpoints response could not be verified
against a live call from this sandbox (network is blocked). I built the matcher from the field
names given in the task (`tag`, `provider_name`, `quantization`, `max_completion_tokens`,
`supported_parameters`) and made it tolerant of either a populated `tag` field or a blank one
needing the provider_name/quantization fallback. If the real response shape differs from both of
these, the lookup will raise its RuntimeError (an abort, per the hard rule of never falling back
silently) rather than silently sending a wrong cap; the author can then use `--cot-max-tokens` to
proceed while the matcher is fixed.

## Task b: failure-as-wrong Top-1/Top-2

`scenario_metrics` in run_prompt_ablation_experiments.py was rewritten to mirror
run_rag_ablation_experiments.scenario_metrics: a scenario with no reference ranking, any
alternative that scored the sentinel, or no alternative overlapping the reference at all, is
WRONG for top1 and top2 (0.0, never NaN) and marked failed. kendall_tau is unchanged: NaN
whenever it is undefined (fewer than two overlapping alternatives or tied ranks on either side),
which pandas mean() skips, so it still averages over scored scenarios only. `_failed_record` (a
scenario that raised inside run_cell) was updated the same way: top1 and top2 are now 0.0, not
NaN. Top-2 is a new metric; it did not exist in the prompt ablation before this change.

`summarize()` now reports `top1_accuracy` and `top2_accuracy` as the mean of the per-scenario
top1/top2 columns over every scenario in the cell (`g`, not the scored-only subset `ok`), which
falls out automatically from failed scenarios already carrying 0.0. `n_failed_scenarios` was added
next to every place `n_scenarios` is reported (the per-run rows and the aggregated summary rows).
The printed table, the xlsx summary sheet, and the markdown report all carry the new columns.

test_prompt_ablation_significance.py: `METRIC_COLS` gained "top2". `load_matrix()` no longer drops
failed rows (it used to exclude them entirely before computing per-scenario, run-averaged values
for the paired Friedman/Wilcoxon tests, which silently shrank the top1 comparison to the scored
subset, the same bug already fixed on the RAG side). Failed rows now stay in; their kendall_tau is
NaN and is skipped by mean(), while their top1/top2 (0.0) correctly pull down a scenario's
run-averaged accuracy when one of its 5 runs failed. The family-size comment was updated from "2
metrics" to "3 metrics" (16 to 24 Friedman tests with the four models currently collected).

Judgement call: a scenario with no ground truth reference at all (the `ref is None` branch, which
arises from a question+location match failure between the Test sheet and the Ground Truth
workbooks) is also counted as an accuracy failure (wrong, 0.0) under this rule, the same as an API
failure. I checked this against the current data: all 195 Test scenarios currently have a
reference (0 missing), so this choice has no effect on any real number today; I flag it because it
is a genuine judgement call, not because it changes anything at present.

## Task c: thread-safe consecutive-failure breaker

sentinel_utils.py: added `import threading` at module scope and `_consecutive_api_failures_lock =
threading.Lock()` next to `_consecutive_api_failures`. The increment-and-check critical section in
`_count_failure_and_maybe_abort` now increments and reads the counter under the lock before
releasing it and checking the threshold outside the lock (so the RuntimeError message reports the
exact count that thread observed). The success-path reset (`_consecutive_api_failures = 0`) is
also now taken under the same lock. Public names and behaviour are unchanged: the counter is still
a plain module-level int, still reset the same way by existing tests
(`SU._consecutive_api_failures = 0`), and the breaker still trips at
`MAX_CONSECUTIVE_API_FAILURES`.

## Tests added

- tests/test_phase1_cot_max_tokens.py (17 cases): endpoint cap under the ceiling, capped at
  32768, provider_name/quantization fallback match, six ways the lookup can fail (network error,
  bad status, no endpoints, no match, null cap, bad JSON) each aborting, a partial multi-model
  failure never leaking a resolved cap for the model that failed, the --cot-max-tokens override
  skipping the GET and being capped, the control arm sending 8192 on the wire, cot_scaffold
  sending the resolved cap on the wire, cot_scaffold capped at 32768 on the wire, cot_scaffold
  raising rather than defaulting when the cap was never resolved, non-cot arms staying at 8192
  after a cap was resolved for the same model, and the raw log recording the cap even on the
  no-call RAG-retrieval-failure path.
- tests/test_phase1_accuracy_metrics.py (11 cases): scenario_metrics for all-scored-correct, a
  sentinel alternative counting wrong (not NaN), no reference counting wrong (not NaN), Top-2
  crediting the second-ranked alternative, _failed_record counting wrong, a cell with failures
  scoring a lower Top-1 than the old scored-only denominator would, all-failed giving 0.0 not NaN,
  a failure-free cell matching the old denominator exactly, load_matrix keeping failed rows,
  per-scenario run-averaging treating a failed run as a miss, and METRIC_COLS including top2.
- tests/test_phase1_thread_safety.py (4 cases): an exact count under N < threshold concurrent
  failures, an exact gap-free trip at the threshold under N > threshold concurrent failures (every
  abort's embedded count is checked against the full expected set 5..N), concurrent successes
  landing the counter at exactly 0, and a direct hammer test of the lock itself (200 threads, one
  increment each, exact final count). Run 15 times in a row with no flakes.

## Test results

Full suite, all four MODEL_KEYs, OPENROUTER_API_KEY unset:

| MODEL_KEY | passed | failed | total |
|---|---|---|---|
| gptoss | 360 | 7 | 367 |
| qwen | 360 | 7 | 367 |
| deepseek | 360 | 7 | 367 |
| gemini | 360 | 7 | 367 |

367 = the original 214 (test_ablation_migration.py 28, test_arch_patch.py 140,
test_sentinel_aggregation_matching.py 46) plus 121 new tests from the concurrent agent's work
(test_appliance_tariffs.py 101, test_hvac_reference.py 18, test_shower_reference.py 2) plus my 32
new tests (17 plus 11 plus 4).

The 7 failures are pre-existing and unrelated to this work: test_response_kinds[*-AH-Appliance]
(5 cases, an "Unknown appliance type: 'Waser'" error), test_ae_real_chroma_retrieval_distances,
and test_regression_ah_historical_raw_jsonl. I confirmed this by copying the original (git HEAD)
versions of sentinel_utils.py, run_prompt_ablation_experiments.py, and
test_prompt_ablation_significance.py back over my edits and re-running: the same 7 tests fail with
the same errors. They trace to the concurrent agent's in-progress edits to Ground Truth
Calculators/ApplianceGroundTruthCalculator.py and the Scenario Files/Ground Truth workbooks (all
shown as modified in git status), not to anything in this change.

Analysis/rerun_prep/infra/test_retry_exhausted_logging.py: the prompt-ablation check
(check_prompt_ablation) passes: "[OK] run_prompt_ablation_experiments.py: retry-exhausted calls
logged (3 records, error/attempts/collected_utc all present)". The script then fails inside
check_rag_ablation with `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`
on `r.get("attempts", 0) >= 1`. I confirmed this is also pre-existing and unrelated: it reproduces
identically with the original, fully unmodified sentinel_utils.py and
run_prompt_ablation_experiments.py restored. It is inside run_rag_ablation_experiments.py, a file
outside my ownership for this task, so I did not fix it; check_position_bias (the third check)
never runs because check_rag_ablation raises before it. I am flagging this as a separate,
pre-existing bug for the author's attention rather than fixing it here.

## Prompt-hash proof

Method: mocked requests.post, ran score_scenario for every (variant, architecture) cell that is
not skipped (7 cells: control/no_anchors/cot_scaffold/scale_0_10 times AD/AE, minus
no_anchors x AE), across all four models and a stratified sample of 6 scenarios (2 per decision
type), capturing the exact `messages` list sent on every call, once against the original (git
HEAD) run_prompt_ablation_experiments.py and once against the modified one. A_E used a fake Chroma
collection and embedder (deterministic, no network) so both runs retrieve the same exemplar.
cot_scaffold's max_tokens was resolved via the --cot-max-tokens override path (set to 8192) in
both runs so the two capture sessions differ only in code, not in the cap actually sent (the cap
itself is not part of `messages` and would not affect this proof either way).

Result: 504 calls captured on each side (7 cells times 4 models times 6 scenarios times 3
alternatives), 126 distinct prompts per side. Zero sha256 mismatches of `messages` across all 504
calls. Aggregate hash before and after: `2cef7536928989f1` (identical). The only source diff
between the two files that touches anything related to prompts is comments and log/error strings
that use the word "cot_scaffold"; AD_SYSTEM_PROMPT, AE_SYSTEM_PROMPT, COT_SCAFFOLD, VARIANT_SPECS,
build_user_prompt, and build_messages are untouched.

## Files changed

- sentinel_utils.py: threading import and lock for _consecutive_api_failures; build_openrouter_payload
  gained an optional max_tokens parameter (default preserves the old behaviour for every other
  caller).
- Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py: cot_scaffold max_tokens
  lookup/override/threading (task a); failure-as-wrong Top-1/Top-2 plus n_failed_scenarios (task
  b).
- Miscellaneous Scripts/validation/test_prompt_ablation_significance.py: top2 added to
  METRIC_COLS; load_matrix no longer drops failed rows; a documentation comment updated for the
  new test-family size.

New: tests/test_phase1_cot_max_tokens.py, tests/test_phase1_accuracy_metrics.py,
tests/test_phase1_thread_safety.py, this report.

Not touched by me, seen modified in the working tree (the concurrent agent's work): Ground Truth
Calculators/ApplianceGroundTruthCalculator.py, HVACGroundTruthCalculator.py,
ShowerGroundTruthCalculator.py; Ground Truth/ground_truth_*.xlsx; Scenario Files/*.xlsx; README.md;
Analysis/rerun_prep/PROVENANCE_APPLIANCE.md; paper/pass6/verify/V_APPLIANCE.md;
Output Files/Baselines/baseline_fixeddefault.xlsx; tests/audit_scenarios.py; tests/test_appliance_tariffs.py;
tests/test_hvac_reference.py; tests/test_shower_reference.py; plus a large set of deleted files
under Analysis/Prompt_Ablation/, Analysis/Hybrid_Ablation/, and archive/2026-09_pre_rerun/ (the
runbook's archiving step).

## Git

Commands run, all read-only: `git status --short` (repeatedly), `git diff --stat`,
`git show HEAD:sentinel_utils.py`, `git show HEAD:"Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py"`,
`git show HEAD:"Miscellaneous Scripts/validation/test_prompt_ablation_significance.py"` (each
piped to a scratch copy for the before/after comparisons and the prompt-hash proof). No commit,
add, push, checkout, stash, or reset.
