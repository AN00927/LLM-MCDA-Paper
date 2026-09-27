# Rerun runbook: the one paid collection, in order

Written 2026-09-26 with the script fixes in `paper/pass6/verify/SCRIPT_FIXES_REPORT.md`.
Every command runs from the repo root in Git Bash, with the project venv. No step here
edits the paper.

```bash
cd "/c/Users/Ahaan/LLM-MCDA Paper"
PY=.venv/Scripts/python.exe
export OPENBLAS_NUM_THREADS=1
```

Placeholders the author must fill before the step that needs them are marked
**[AUTHOR: ...]**. Nothing marked that way has a default.

Call counts are per model unless a line says "all models". Sources: `V_INFRA.md` Section 2
and `V_INFRA_cost_plan.csv`, re-derived below from the script defaults as they now stand.
The costs are V_INFRA's listed-price estimates (Gemini 3.5 and DeepSeek V4 token counts used
as proxies, Gemini at the standard tier), not quotes. With Gemini pinned to the flex tier
(D1), Gemini's share, 70-90% of every arm, is roughly halved.

---

## 0. Blockers and decisions before any paid call

| # | Item | Status |
|---|---|---|
| B1 | Architecture patch (`Analysis/rerun_prep/arch_new/`) installed into `Architectures/` and `sentinel_utils.py`, its tests passing against the installed files | done 2026-09-27: `tests/test_arch_patch.py` 140/140 under each MODEL_KEY; gate unchanged (`paper/pass6/verify/INSTALL_MIGRATE_REPORT.md`) |
| B2 | The two ablation scripts (`run_rag_ablation_experiments.py`, `run_prompt_ablation_experiments.py`) switched to the patch's shared payload and POST (`sentinel_utils.build_openrouter_payload` / `openrouter_chat`), so they send `provider`, `max_tokens` and fail truncated replies like the architectures (ARCH_PATCH_REPORT, "Adaptations" item 1) | done 2026-09-27: both use `openrouter_chat`; prompts byte-identical (hash proof in INSTALL_MIGRATE_REPORT); `tests/test_ablation_migration.py` |
| B3 | Phase I of `PASS6_HANDOFF.md` done: snapshot, scenario fixes, calculators installed, calculators run, `sync_rag_ground_truth_scores.py`, `build_rag_index.py` (always last) | done (second cloud session, 2026-09-27; `CLOUD_AGENT_CONTEXT.md`) |
| D1 | Provider pinning. `model_config.py` (author's edit, seen 2026-09-26) now pins one provider per model with `"only": [...]` and `"allow_fallbacks": false`: gptoss `darkbloom/fp8`, qwen `venice/fp8`, deepseek `baseten/fp8`, gemini `google-ai-studio/flex`. The entry replaces the patch's default `{"require_parameters": true}`, so `require_parameters` is not sent: a pinned provider that does not support `temperature` would ignore it silently. The smoke test must confirm each pinned endpoint lists `temperature` and `reasoning` | done (author, 2026-09-27): `"require_parameters": true` added to all four pins; `build_openrouter_payload` sends the pin dict unchanged (`test_payload_passes_model_specs_provider_pin_unchanged`) |
| D2 | Gemini reasoning effort. `model_config.py` now says `"low"` (a listed effort). Confirm in the smoke test that it is accepted and how many reasoning tokens it returns; main L734 says "minimal" | smoke 2026-09-27: `low` accepted, about 269 reasoning tokens per call; Gemini is about 68% of the estimate. **[AUTHOR: keep `low` (then fix main L737), or switch to `minimal`]** |
| D3 | DeepSeek output folder: now `"Output Files DeepSeek V4 Flash 0731"` (new, must be empty). The old `"Output Files DeepSeek V4 Flash"` keeps the old runs and is not written to | done (author) |
| D4 | Price labels updated by the author (DeepSeek $0.13/$0.26, Gemini flex $0.375/$1.875). Only the Table 8 fallback uses labels; charged cost comes from the diagnostics JSON | done (author) |
| D5 | Prompt-ablation run counts (step 6) | **[AUTHOR: DECISION prompt-ablation runs]** |
| D6 | Copy-only / nearest-neighbour fallback: `--nn-fallback tie` (old rule), `nearest` or `unscored` (numbers per variant in SCRIPT_FIXES_REPORT item 1) | **[AUTHOR: DECISION nn-fallback]** |
| D7 | Rule, fixed in advance, for confirming the benchmark k from the RAG ablation (step 2) | **[AUTHOR: DECISION k rule]** |
| D8 | Optional arms (step 7): A_E at k = 3 on the test set; listwise A_D | **[AUTHOR: DECISION optional arms]** |
| D9 | `MAX_OUTPUT_TOKENS = 8192` (arch patch, now also sent by both ablations), confirmed against the smoke-test token counts. Old logs: only the Qwen CoT prompt-ablation arms come near it (A_D CoT 4.3-39.4% of calls over 8,192, A_E CoT 1.3-8.5%; `paper/pass6/verify/truncation_risk_8192.csv`); those calls now fail as `failed_truncated` | **[AUTHOR: confirm after step 1; decide on Qwen CoT (step 6)]** |

Step 1 ran on 2026-09-27: see `Analysis/rerun_smoke/SMOKE_REPORT.md` (112/112 calls ok, $0.03;
DeepSeek 429s upstream, so use `--workers 1-2` for it; re-costed total about $35; balance was
$2.97). Check the OpenRouter credit balance is at least twice the estimate for the steps you are about
to run (V_INFRA Section 2).

## 0.1 What must be empty (or moved aside) before collecting

Every path below is resumed from, appended to, or overwritten. Move each aside **after** the
Phase I snapshot. Do not delete.

| Path | Why |
|---|---|
| `Output Files GPT-OSS 20B/` including `position_bias/` and `hybrid_order_reversal/` | Same folder name for the rerun; old runs would be skipped as complete (the patched architectures refuse old-format files instead). Order arm and position bias resume from their checkpoint jsonl and completed xlsx |
| `Output Files Qwen3.5 9B/` including `position_bias/` and `hybrid_order_reversal/` | same |
| `Output Files DeepSeek V4 Flash 0731/` (new folder per D3; the old `Output Files DeepSeek V4 Flash/` is not written to) | same |
| `Output Files Gemini 3.8 Flash/` | empty today; confirm it still is |
| `Analysis/Prompt_Ablation/` | 162 old `cell_*` files; resume is by file existence and keyed by model key, not model id |
| `Analysis/RAG_Ablation/` | the raw jsonl is appended to; `checkpoints/` would be resumed; the result workbooks are overwritten |
| `Analysis/Hybrid_Ablation/` | analysis workbooks are overwritten by step 5's analysis (move aside for a clean diff) |
| `Output Files/Baselines/` orphans `baseline_oracle.xlsx`, `baseline_random_aggregated.xlsx`, `baseline_uniform.xlsx` | no current producer (V_BASELINE issue 13) |

Check (prints every file still present; expect nothing):

```bash
for d in "Output Files GPT-OSS 20B" "Output Files Qwen3.5 9B" "Output Files DeepSeek V4 Flash 0731" \
         "Output Files Gemini 3.8 Flash" "Analysis/Prompt_Ablation" "Analysis/RAG_Ablation" "Analysis/Hybrid_Ablation"; do
  [ -d "$d" ] && find "$d" -type f | head -5
done
```

---

## Call budget (re-derived)

| Step | Experiment | Unit | Calls per model | All four models | Listed-price estimate (V_INFRA) |
|---|---|---|---|---|---|
| 1 | Smoke test | 3 scenarios x 3 alternatives, three paths | 27 | 108 | cents |
| 2 | RAG ablation | 7 LLM configs x 90 scenarios x 3 alternatives, 1 run | 1,890 | 7,560 | about $2.0 |
| 3-4 | Main benchmark | A_D 5 x 585 + A_E 5 x 585 + A_H 5 x 195 | 6,825 | 27,300 | about $6.2 |
| 5 | A_H order arms | reversed 5 x 195 + control 3 x 195 | 1,560 | 6,240 | about $1.2 |
| 5 | Position bias | A_D reversed, 1 x 195 x 3 | 585 | 2,340 | about $0.5 |
| 6 | Prompt ablation, paper design | non-Gemini 45 cell-runs x 585; Gemini 21 x 585 | 26,325 (Gemini 12,285) | 91,260 | about $23 |
| 6 | Prompt ablation, script default (5 runs every cell) | 35 cell-runs x 585 | 20,475 | 81,900 | about $33 (Gemini about $26) |
| 7 | Optional: A_E k = 3 on test, 3 runs | 3 x 585 | 1,755 | 7,020 | about $2.3 |
| | **Total, paper-design prompt ablation, no optional arms** | | | **134,700** (+108 smoke) | **about $33** |

---

## 1. Smoke test (about 108 calls)

Goal: every model id resolves; `temperature`, `reasoning`, `provider` and `max_tokens` are
accepted; token and reasoning-token use per call; the new raw-log fields are populated.
Writes to a scratch folder except where noted.

```bash
SMOKE=Analysis/rerun_smoke; mkdir -p "$SMOKE"

# (a) RAG-ablation request path: 3 scenarios x 3 alternatives x 4 models = 36 calls
$PY "Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py" \
    --sample-size 3 --ablations retrieval_k1 --workers 1 --no-checkpoint \
    --output-dir "$SMOKE/rag" --output "$SMOKE/rag/report.md"

# (b) prompt-ablation request path: 36 calls
$PY "Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py" \
    --sample-size 3 --runs 1 --variants control --architectures AD --workers 1 \
    --output-dir "$SMOKE/prompt" --output "$SMOKE/prompt/report.md"

# (c) architecture request path (A_D via the position-bias driver): 3 x 3 x 4 = 36 calls.
#     This writes into each model's Output Files*/position_bias/. DELETE it afterwards,
#     or step 5 skips the reversed run as already complete.
$PY "Miscellaneous Scripts/experiments/run_position_bias_control.py" run --n 3
```

A_H has no small-sample entry point; its first real run (step 3) is the A_H smoke test: stop
it after the first few scenarios if the raw log shows a problem.

Checks:
- No `failure_type` / `parse_error` of `failed_truncated`, `failed_empty_response`,
  `failed_api_bad_request` or `FAILED_API_BAD_REQUEST` in the smoke raw logs.
- No HTTP 400/404/422 in the raw logs (`$SMOKE/rag/rag_ablation_results_raw.jsonl`,
  `$SMOKE/prompt/cell_*_raw.jsonl`, `Output Files*/position_bias/*_raw.jsonl`). Gemini with
  effort `minimal`: a 400 means D2 must change the effort; a success means read
  `usage.completion_tokens_details.reasoning_tokens` to see which tier was applied.
- Every record carries `provider`, `response_id`, `response_model`, `finish_reason`, `usage`
  (with `cost`). Under `:floor` note which providers served each model (D1).
- Output tokens per call, per model, against D9's 8,192 cap; no `finish_reason: length`.
- Then remove the smoke outputs from the real folders:

```bash
for f in "Output Files GPT-OSS 20B" "Output Files Qwen3.5 9B" \
         "Output Files DeepSeek V4 Flash 0731" \
         "Output Files Gemini 3.8 Flash"; do rm -r "$f/position_bias"; done
```

## 2. RAG ablation first (7,560 calls; confirms the benchmark k)

Runs before the main benchmark because the benchmark's k = 1 was chosen from this ablation on
the old models. One process, all four models (two concurrent processes would clobber the
workbook and interleave the raw log).

```bash
$PY "Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py" \
    --nn-fallback [AUTHOR: DECISION nn-fallback: tie|nearest|unscored]
```

Defaults: all 90 RAG scenarios (leave-one-out), all eight configurations (seven LLM + the
offline copy-only control), all four models, 8 worker threads, seed 13.

Writes: `Analysis/RAG_Ablation/` (`rag_ablation_results.xlsx`, `rag_ablation_summary.xlsx`,
`..._by_decision_type.xlsx`, Friedman / post-hoc / bootstrap workbooks,
`rag_ablation_results_raw.jsonl`, `checkpoints/<ablation>__<model>.json`), and
`rag_ablation_results.md` at the repo root.

Restart after a crash: rerun the same command. Finished (ablation, model) units load from
`checkpoints/`; the random arm's draws are replayed so they stay identical. A unit whose calls
all failed is not saved and stops the run.

Checks:
- 29 checkpoint files (7 x 4 + 1): `ls Analysis/RAG_Ablation/checkpoints | wc -l`.
- Per model and configuration, failures and scored scenarios:

```bash
$PY -c "import pandas as pd; s=pd.read_excel('Analysis/RAG_Ablation/rag_ablation_summary.xlsx'); print(s[['model_key','ablation_id','n_scenarios','n_failed_scenarios','api_calls','failed_calls','kendall_tau','top1_accuracy','score_mae']].to_string(index=False))"
```

- Top-1 / Top-2 accuracy (changed 2026-09-27): a scenario with any failed or unscored
  alternative (API failure, truncation, empty reply, parse error, copy-only `unscored`) counts
  as wrong, and the denominator is `n_scenarios`. `n_failed_scenarios` is how many were counted
  wrong that way. Tau and MAE still average only the scored scenarios.
- Checkpoints are now format 2. A checkpoint from an older collection is refused ("different
  configuration"), not resumed: move `Analysis/RAG_Ablation/` aside first (section 0.1).
- An HTTP 401/402/403 (or 5 failed calls in a row) stops the process: queued scenarios are
  cancelled, the unit is not checkpointed, no workbook is written. Fix the cause and rerun the
  same command.

- Raw log has 7,560 success records plus any failure records:
  `wc -l Analysis/RAG_Ablation/rag_ablation_results_raw.jsonl`.
- **k decision**: apply **[AUTHOR: DECISION k rule, e.g. "keep k = 1 unless k = 3 beats
  k = 1 on tau for a model with Holm-significant post-hoc"]** to `retrieval_k1` vs
  `control_k3` vs `retrieval_k5`, per model (never pooled). If k changes, set
  `DEFAULT_RETRIEVE_K` in the installed A_E (or export `RAG_TOP_K`) before step 3 and tell the
  author: the paper's k rationale changes.

## 3. Main benchmark, one model at a time (6,825 calls per model)

`model_config.py` now reads `MODEL_KEY` from the environment (default `gemini`), once at
import. Different models write to different folders and may run in parallel, one process per
model. `N_RUNS` is 5 in `model_config.py`. `RAG_TOP_K` must be unset (unless step 2 changed k).

```bash
unset RAG_TOP_K
for MK in gptoss qwen deepseek gemini; do
  MODEL_KEY=$MK $PY Architectures/Direct_LLM_Scoring.py
  MODEL_KEY=$MK $PY Architectures/Example-Guided_LLM_Scoring.py
  MODEL_KEY=$MK $PY Architectures/LLM-Parameterized_Reference_Scoring.py
done
```

A_E checks the Chroma index at start-up (schema version 4 and the RAG-sheet SHA); if it
refuses, rerun `build_rag_index.py` (B3), never skip the check.

Writes, per model folder: `<arch>_results_run_01..05.xlsx` (now with `collected_utc` and
`model_id` columns), `<arch>_results_diagnostics_run_01..05.json` (with
`collected_utc_start/_end`, `total_cost_usd`, `calls_with_cost`),
`<arch>_results_run_01..05_raw.jsonl`, `<arch>_results_events.log`, and the aggregate
`<arch>_results.xlsx`.

Checks, per model (edit `F`):

```bash
F="Output Files GPT-OSS 20B"
$PY - "$F" <<'EOF'
import glob, json, sys
F = sys.argv[1]
for arch in ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]:
    for p in sorted(glob.glob(f"{F}/{arch}_results_diagnostics_run_*.json")):
        d = json.load(open(p))
        print(p.rsplit("/", 1)[-1], d.get("model_id"), d.get("collected_utc_start"), d.get("collected_utc_end"),
              "calls", d.get("total_api_calls"), "with_cost", d.get("calls_with_cost"),
              "cost", d.get("total_cost_usd"), "failed_scen", d.get("failed_scenarios"))
EOF
grep -h "REFUSED\|ABORT\|FAILED" "$F"/*_events.log
```

Expect 15 run files, 15 diagnostics JSON and 15 raw jsonl per model; A_D and A_E 585 calls per
run and A_H 195; `calls_with_cost` equal to the call count; no REFUSED or ABORT event. Resume is per
run file: rerunning the command skips completed runs and re-collects a run that aborted
(its calls stay in that run's raw jsonl, which is appended to).

## 4. After all four models: collection window so far

```bash
$PY paper_pipeline/emit_collection_window.py --out-dir Analysis/rerun_smoke/window
```

Every main-run artifact should report a `time_source` other than `mtime`.

## 5. A_H order arms (1,560 calls per model) and position bias (585 per model)

Both can start as soon as step 1 passes; their analyses need step 3's runs.

```bash
# order arms: reversed runs 1-5 and same-session control runs 1-3, all four models
$PY "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py" --collect-only
#   one model per process to parallelise: add --models gptoss (etc.)

# position bias: A_D reversed, all 195 scenarios, 1 run, all four models
$PY "Miscellaneous Scripts/experiments/run_position_bias_control.py" run
```

Both defaults now reproduce the paper's design with no flags (order arms: 5 reversed + 3
control; position bias: 4 models, n = 195, 1 run). `--order-runs` is a last run index, not a
count.

Writes: `<model folder>/hybrid_order_reversal/AH_extraction_order_{reversed,control}_run_NN.xlsx`
and `..._raw.jsonl`; `<model folder>/position_bias/Direct_LLM_Scoring_reversed_run_01.xlsx`,
`..._raw.jsonl`, `..._partial_run_01.jsonl` (checkpoint), sample manifest and spec.

Checks:

```bash
for f in "Output Files GPT-OSS 20B" "Output Files Qwen3.5 9B" \
         "Output Files DeepSeek V4 Flash 0731" \
         "Output Files Gemini 3.8 Flash"; do
  echo "$f: order xlsx $(ls "$f/hybrid_order_reversal"/*.xlsx | wc -l) (expect 8)," \
       "position-bias xlsx $(ls "$f/position_bias"/Direct_LLM_Scoring_reversed_run_*.xlsx | wc -l) (expect 1)"
done
```

Then the offline analyses (no API calls):

```bash
$PY "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py"          # all four models
$PY "Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py"
$PY "Miscellaneous Scripts/experiments/run_position_bias_control.py" analyze        # all four models
```

Check `Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx`: per model, `extracted` has 5
runs, `order_reversed` 5, `order_control` 3, `default_params` 1.

## 6. Prompt ablation

**[AUTHOR: DECISION prompt-ablation runs.]** The script applies one `--runs` to every cell it
selects, and it does not change counts by itself.

- Option 1, uniform 5 runs in every cell, all models (script default; 81,900 calls):

```bash
$PY "Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py"
```

- Option 2, the design the supplement describes (10 runs for A_D control and no_anchors on
  DeepSeek / GPT-OSS / Qwen, 5 for their other cells, 3 for every Gemini cell; 91,260 calls):

```bash
$PY "Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py" --models gptoss qwen deepseek --runs 5
$PY "Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py" --models gptoss qwen deepseek \
    --architectures AD --variants control no_anchors --runs 10
$PY "Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py" --models gemini --runs 3
```

Writes: `Analysis/Prompt_Ablation/cell_<variant>_<arch>_<model>_run_NN.xlsx` and
`..._raw.jsonl`, `prompt_ablation_summary.xlsx`, and `prompt_ablation_results.md` at the repo
root. Each invocation rewrites the summary with only the runs it selected; the significance
script reads every `cell_*.xlsx`, so under option 2 the summary workbook is partial and is not
the source for the paper.

`RAG_TOP_K` must be unset (the A_E arms use the installed A_E's `RETRIEVE_K`). An HTTP
401/402/403 (or 5 failed calls in a row) stops the whole process: running workers stop at
their next call, queued scenarios are cancelled, and the cell being collected is not written
(no summary or report either). Completed cells stay; rerun the same command to resume. The
aborted cell's `_raw.jsonl` keeps the aborted pass's records (append-only; each has its own
`collected_utc`).

**Truncation risk (D9):** in the old logs, Qwen's `cot_scaffold` arms averaged 5,732 (A_D) and
2,482 (A_E) completion tokens per call, up to 139,044 per 3-call scenario. Under the 8,192 cap
an estimated 4.3-39.4% (A_D) and 1.3-8.5% (A_E) of those calls will stop at `finish_reason:
length` and fail as `failed_truncated` (scenario then fails). Every other model x arm was far
below the cap. **[AUTHOR: DECISION accept the Qwen CoT failures, or raise the cap for that arm
before collecting]**; check with
`grep -c failed_truncated Analysis/Prompt_Ablation/cell_cot_scaffold_*_qwen_run_01_raw.jsonl`
after the first Qwen CoT cell.

Checks: cell count (option 1: 28 cells x 5 = 140 files; option 2: 3 x 45 + 21 = 156):
`ls Analysis/Prompt_Ablation/cell_*_run_*.xlsx | grep -v _raw | wc -l`, then
`$PY "Miscellaneous Scripts/validation/test_prompt_ablation_significance.py"`.

## 7. Optional arms

**[AUTHOR: DECISION optional arms.]**

- A_E at k = 3 on the 195 test scenarios, 3 runs per model (7,020 calls; V_RERUN_PROOFING
  item C). The patched A_E writes k-tagged files the pipeline globs never pick up:

```bash
# [AUTHOR: N_RUNS = 3 in model_config.py for this arm only, then back to 5]
for MK in gptoss qwen deepseek gemini; do
  MODEL_KEY=$MK RAG_TOP_K=3 $PY Architectures/Example-Guided_LLM_Scoring.py
done
```

- Listwise A_D (V_RERUN_PROOFING item E, about 3,900 calls): no code exists yet.
  **[AUTHOR: DECISION; needs a new arm in an experiment script first]**

## 8. Offline, after collection (no API calls)

Order matters: baselines read the installed calculators and the synced RAG sheets.

```bash
$PY "Miscellaneous Scripts/core-automation/run_baseline_models.py" \
    --nn-fallback [AUTHOR: DECISION nn-fallback, same as step 2]
$PY "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py"
$PY paper_pipeline/run_paper_pipeline.py
$PY paper_pipeline/compute_dispersion_diagnostics.py
$PY paper_pipeline/competitive_baselines.py
$PY paper_pipeline/emit_collection_window.py
$PY paper_pipeline/build_numbers_of_record.py --output-dir Analysis/rerun_numbers
```

Checks:
- `paper/collection_window_summary.csv`: no `mtime` source for any rerun artifact; the whole
  collection inside one window.
- `Table8_cost_per_run` rows in `paper/numbers_master.csv` have `cost_source` = `charged`.
- `Analysis/rerun_numbers/numbers_of_record_regenerated.csv`: every row except the 25 retired
  Set B rows is `regenerated`; the diff against the record is the list of numbers the paper
  must update (Phase S4). Nothing is pooled across models.
