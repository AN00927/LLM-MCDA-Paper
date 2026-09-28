# Rerun runbook: the one paid collection, in order

Rewritten 2026-09-27 (end of the second cloud session) after the author's design decisions.
The previous version is in git history (commit 617b07c). No step here edits the paper.

**No paid call without the author's explicit go-ahead in the conversation.** The author has
approved the design below and said they will top up the OpenRouter credit when they choose.
Only start collecting after the author says go. Before any step, check that the balance is at
least twice that step's estimate.

```bash
# Windows (author's machine, Git Bash):
cd "/c/Users/Ahaan/LLM-MCDA Paper"; PY=.venv/Scripts/python.exe
# Linux (cloud container):
cd /home/user/LLM-MCDA-Paper; PY=.venv/bin/python
export OPENBLAS_NUM_THREADS=1
unset RAG_TOP_K                     # k = 1 everywhere; never set this for the rerun
```

Call counts are for all four models together. Costs are listed-price estimates re-costed
with the 2026-09-27 smoke measurements (`Analysis/rerun_smoke/SMOKE_REPORT.md`), not quotes.

---

## 0. Decisions (all settled; author, 2026-09-27)

| # | Decision |
|---|---|
| Order | Collect every ablation first and the **main suite last**. Keep this order in any plan. |
| k | **k = 1** in the main suite, no matter what the RAG ablation shows. Still rerun the RAG ablation and report how far its results moved from the old ones. |
| Prompt ablation | **3 runs per cell, fixed in advance, with no top-ups.** The cells are A_D `no_anchors`, A_D `cot_scaffold` and A_E `cot_scaffold`. The 0-10 scale variant is **cut**. The control cell is **not collected**: the significance script uses main-suite runs 1-3, whose messages are byte-identical (checked at startup). |
| A_H order arms | Collect the **reversed arm only** (5 runs). The same-session control arm is **cut**, because every run now carries a timestamp and is collected in one window. The permutation test uses the 5 main-suite A_H runs plus the 5 reversed runs: C(10,5) = 252 relabelings, floor p = 0.004. |
| Optional arm: A_E k = 3 on the test set | **Cut** (k = 1 is fixed). |
| Added arm: listwise A_D | **Added**. One call per scenario asking the model to rank the three alternatives. It uses A_D's anchors and scenario context plus the 35/30/20/15 weights. 5 runs. Script: `run_listwise_direct_ranking.py`. |
| Nearest-neighbour fallback (D6) | **`tie`**, the script default and the original rule. The copy-only baseline on the test set now defaults to **k = 1**, matching A_E. |
| DeepSeek provider | **`relace/fp4`**, set in `model_config.py` on `main` on 2026-09-28. A 15-call smoke at 4 workers had 0 failures and 0 retries (BaseTen had 429s on 12 of 27). |
| Gemini effort | **`minimal`**, set in `model_config.py` on 2026-09-28 (author decision). It matches main L737. It is accepted and costs the same as `low` (smoke of 9 identical calls), so the estimates stand. |
| Qwen CoT cap | The prompt ablation raises `max_tokens` for `cot_scaffold` from each pinned endpoint's own limit, capped at 32,768 (`resolve_cot_max_tokens`). Nothing to decide. |

## 0.1 What must be empty before collecting

Resume logic skips completed files, so old files would be silently reused. Move aside, never
delete.

```bash
for d in "Output Files GPT-OSS 20B" "Output Files Qwen3.5 9B" "Output Files DeepSeek V4 Flash 0731" \
         "Output Files Gemini 3.8 Flash" "Analysis/Prompt_Ablation" "Analysis/RAG_Ablation" \
         "Analysis/Hybrid_Ablation" "Analysis/Listwise_Direct"; do
  [ -d "$d" ] && find "$d" -type f | head -5
done
```

Expect no output. The smoke outputs live in `Analysis/rerun_smoke/`, which nothing reads.

## Call budget

| Step | Experiment | Calls (4 models) | Estimate |
|---|---|---|---|
| 1 | RAG ablation (7 LLM configs x 90 x 3, 1 run) | 7,560 | $2.1 |
| 2 | A_H order arm, reversed (5 x 195) | 3,900 | $0.9 |
| 3 | Position bias, A_D reversed (1 x 195 x 3) | 2,340 | $0.5 |
| 4 | Prompt ablation (3 cells x 3 runs x 585) | 21,060 | $11.4 |
| 5 | Listwise A_D (5 x 195) | 3,900 | $1.7 |
| 6 | **Main suite, last** (A_D 5x585 + A_E 5x585 + A_H 5x195) | 27,300 | $6.6 |
| | **Total** | **66,060** | **about $23** |

Gemini is about 85% of the cost. The balance was $2.93 on 2026-09-27.

Steps 1-5 are independent and may run in parallel **only as separate model processes where a
script allows it**. The RAG ablation must be one process for all models (two processes would
clobber its workbook). Step 6 starts only after 1-5 have finished.

---

## 1. RAG ablation (7,560 calls)

```bash
$PY "Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py" --nn-fallback tie
```

Defaults: all 90 RAG scenarios (leave-one-out), eight configurations (seven LLM + offline
copy-only at k = 3), all four models, 8 workers, seed 13. If DeepSeek logs 429s under
`relace/fp4`, rerun the same command with `--workers 2`; it resumes from `checkpoints/`.

Checks:
- `ls Analysis/RAG_Ablation/checkpoints | wc -l` gives 29 (7 x 4 + 1).
- Per model and configuration, `n_failed_scenarios` and `failed_calls` in
  `rag_ablation_summary.xlsx` are near zero.
- Report the old vs new values of tau, Top-1 and MAE per model and configuration. The author
  asked to see whether they are "way different". The old values are in `archive/2026-09_pre_rerun/Analysis/`.
- This does **not** change k (decision above).

## 2. A_H order arm, reversed only (3,900 calls)

```bash
$PY "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py" --collect-only
#   one model per process to parallelise: add --models gptoss (etc.)
```

Writes `<model folder>/hybrid_order_reversal/AH_extraction_order_reversed_run_01..05.xlsx` and
`_raw.jsonl`. Check: 5 xlsx per model and no control files. The analysis (step 7) needs the
main suite's A_H runs.

## 3. Position bias (2,340 calls)

```bash
$PY "Miscellaneous Scripts/experiments/run_position_bias_control.py" run
```

Writes `<model folder>/position_bias/Direct_LLM_Scoring_reversed_run_01.xlsx` and `_raw.jsonl`.
Check: 1 xlsx per model.

## 4. Prompt ablation (21,060 calls)

```bash
$PY "Miscellaneous Scripts/experiments/run_prompt_ablation_experiments.py"
```

Defaults are the design:
- variants `no_anchors` and `cot_scaffold`;
- A_D and A_E (no `no_anchors` x A_E, by construction);
- all four models, 3 runs, 195 scenarios, 8 workers.

At startup it checks that its control messages equal the installed architectures' byte for
byte, and refuses to run otherwise. If DeepSeek 429s, run DeepSeek alone with `--models deepseek
--workers 2`.

Checks:
- `ls Analysis/Prompt_Ablation/cell_*_run_*.xlsx | wc -l` gives 36 (3 cells x 4 models x 3
  runs).
- `grep -c failed_truncated Analysis/Prompt_Ablation/cell_cot_scaffold_*_raw.jsonl` is near 0.
- The summary written here has no control rows until step 6 exists. That is expected.

## 5. Listwise A_D (3,900 calls)

```bash
$PY "Miscellaneous Scripts/experiments/run_listwise_direct_ranking.py" run
#   one model per process: add --models gptoss (etc.); DeepSeek with --workers 2 if it 429s
```

Writes `<model folder>/listwise_direct/AD_listwise_run_01..05.xlsx` and `_raw.jsonl`. Check: 5
xlsx per model, and `failed` near 0 in each run. The smoke on 2026-09-27 parsed 24 of 24.

## 6. Main suite, LAST (27,300 calls)

```bash
for MK in gptoss qwen deepseek gemini; do
  MODEL_KEY=$MK $PY Architectures/Direct_LLM_Scoring.py
  MODEL_KEY=$MK $PY Architectures/Example-Guided_LLM_Scoring.py
  MODEL_KEY=$MK $PY Architectures/LLM-Parameterized_Reference_Scoring.py
done
```

Different models write to different folders and may run as parallel processes, one per model.
A_E checks the Chroma index at start-up (schema 4 and the RAG-sheet SHA). If it refuses, rerun
`build_rag_index.py`, never skip the check.

Checks, per model: 15 run xlsx, 15 diagnostics JSON and 15 raw jsonl. A_D and A_E make 585
calls per run and A_H 195. `calls_with_cost` equals the call count, and there are no REFUSED or
ABORT events:

```bash
grep -h "REFUSED\|ABORT" "Output Files"*/*_events.log
```

## 7. Offline analyses (no API calls), in this order

```bash
$PY "Miscellaneous Scripts/core-automation/run_baseline_models.py"        # fixed default + NN copy (k=1, tie)
$PY "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py"
$PY "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py"          # provenance + order arm
$PY "Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py"
$PY "Miscellaneous Scripts/experiments/run_position_bias_control.py" analyze
$PY "Miscellaneous Scripts/validation/test_prompt_ablation_significance.py"        # adds control from main runs 1-3
$PY "Miscellaneous Scripts/experiments/run_listwise_direct_ranking.py" analyze     # vs pointwise A_D
$PY paper_pipeline/run_paper_pipeline.py
$PY paper_pipeline/compute_dispersion_diagnostics.py
$PY paper_pipeline/competitive_baselines.py
$PY paper_pipeline/emit_collection_window.py
$PY paper_pipeline/build_numbers_of_record.py --output-dir Analysis/rerun_numbers
```

Checks:
- `paper/collection_window_summary.csv`: no `mtime` source for any rerun artifact, and the whole
  collection sits inside one window.
- Rows of `Table8_cost_per_run` in `paper/numbers_master.csv` have `cost_source` = `charged`.
- `Analysis/rerun_numbers/numbers_of_record_regenerated.csv` compared with
  `paper/pass5/NUMBERS_OF_RECORD.csv` gives the list of numbers the paper must update (Phase S4).
  Numbers for the cut arms (scale_0_10, the order control arm) have no regenerated value. That
  is expected, and their paper text is removed, not updated.
- Hybrid summary per model: `extracted` 5 runs, `order_reversed` 5 runs, `order_control` 0.
- Prompt significance prints "Control for <arch>/<model>: main-suite runs 1-3" for all eight
  strata. A_E strata show `test = wilcoxon_signed_rank`.
- Never pool across models in any table.
