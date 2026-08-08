# Ablation Experiments

Supplementary experiments run alongside the main benchmark. Each has a runner script
in `Miscellaneous Scripts/` and writes its outputs under `Analysis/`. The main
benchmark itself is described in [README.md](../README.md); the metrics definitions
are in [metrics_calculation_pipeline.md](metrics_calculation_pipeline.md).

All ablation runners default `--models` to all four keys, which is the set the paper
reports, so a default invocation reproduces the shipped ablation. Gemini costs roughly
50x the output price of the other three; pass the other three keys explicitly to skip
it, at the cost of no longer matching the paper.

Narrowing `--models` on an **analysis** pass overwrites that suite's workbooks with only
the models named. The omitted models are not merged back in, so a partial analysis run
silently drops them from the shipped results.

---

## 1. Parameter-provenance ablation (LLM-Parameterized Reference Scoring)

**Script:** `Miscellaneous Scripts/run_hybrid_ablation_experiments.py`
**Outputs:** `Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx`
**Cost:** zero API calls (reads existing run outputs and scenario sheets)

Isolates how much of the LLM-Parameterized architecture's accuracy comes from LLM
parameter extraction versus from merely having access to the reference calculator.
Three arms, all scored by the same reference calculators over the same 195 test
scenarios:

| Arm | Hidden parameters sourced from | Interpretation |
| --- | --- | --- |
| `true_params` | scenario source sheets (these *are* the reference) | ceiling |
| `extracted` | `extracted_*` columns of `LLM-Parameterized_Reference_Scoring_results.xlsx` | actual |
| `default_params` | corpus median (numeric) / mode (categorical), one constant per parameter | floor |

### Results

| model | arm | n_scored | success_rate | kendall_tau | top1_accuracy | mae |
| --- | --- | --- | --- | --- | --- | --- |
| gptoss | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| gptoss | extracted | 194 | 0.9949 | 0.9210 | 0.9433 | 0.0463 |
| gptoss | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |
| qwen | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| qwen | extracted | 195 | 1.0000 | 0.8974 | 0.9128 | 0.0659 |
| qwen | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |
| deepseek | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| deepseek | extracted | 195 | 1.0000 | 0.9043 | 0.9128 | 0.0411 |
| deepseek | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |

**Finding.** With no per-scenario inference at all, calculator access alone reaches
tau = 0.641 / Top-1 = 76.9%. LLM extraction lifts that to tau ~= 0.90 / Top-1 ~= 92%.
Extraction therefore contributes roughly 0.26 tau *beyond* having the calculator; the
architecture's accuracy is not an artifact of errors cancelling inside a deterministic
scorer. `default_params` is identical across models because it consumes no model output.

**Validity checks.** `true_params` returns exactly tau = 1.0 / MAE = 0.0, which is
correct by construction. `extracted` tau (0.897-0.921) tracks the published
LLM-Parameterized tau (0.880-0.897), validating the harness against known numbers.

### Implementation notes

- The three calculators return three different result shapes. HVAC and Appliance
  return `{alt_label: {"<criterion>_score": v}}`; Shower returns
  `{"alternatives": [{"alternative": label, "transformed_values": {criterion: v}}]}`.
  `score_scenario` normalizes both.
- Calculators print per-alternative progress; this is suppressed via
  `contextlib.redirect_stdout` across roughly 1,700 scoring calls.
- `pandas.to_markdown` requires `tabulate`, which is not a repo dependency. The script
  uses a hand-rolled `_md()` helper instead.
- Sentinel-safe: a failed extraction is excluded from its arm rather than replaced by a
  neutral default. Per-arm `n_scored` makes exclusions visible (gptoss `extracted` = 194).

---

## 2. Alternative-ordering ablation (LLM-Parameterized Reference Scoring)

**Script:** `Miscellaneous Scripts/run_hybrid_ablation_experiments.py` (`--collect-only` for collection,
default mode for analysis)
**Outputs:** `Analysis/Hybrid_Ablation/hybrid_order_reversal.xlsx` (`summary` and `pairwise`
sheets)
**Cost:** collection only, 20 reversed runs across 4 models (2,340 API calls); analysis is free

Tests whether LLM-Parameterized_Reference_Scoring's ranking depends on the order in which the
three alternatives are listed in the extraction prompt. This is the only architecture whose
prompt shows all three alternatives as a numbered sequence in one call (Direct and
Example-Guided score one alternative per stateless call). The manipulation reverses
`alternative_1`/`alternative_3` in the extraction prompt and nothing else; scoring is always
performed in canonical alternative order in every arm, so the calculator's stable-sort
tie-break cannot manufacture a difference between arms.

Three arms per model:

| Arm | Runs | What it is |
| --- | --- | --- |
| `shipped` | 5 | the benchmark runs, collected 2026-07-29 |
| `control` | 3 | shipped order, re-sent 2026-08-03, identical code path |
| `reversed` | 5 | reversed order, collected 2026-08-03 |

The control arm exists because the shipped runs record no collection timestamp (see the
CLAUDE.md convention added this session requiring one going forward): a gap between reversed
and shipped is equally consistent with an ordering effect or with provider drift, so
control-vs-shipped measures drift directly and reversed-vs-control holds the session fixed.

The primary test is an exact label-permutation test (`_exchangeability_test`): under the null a
reversed run is just another run, so the test relabels which runs carry the reversed label
across all `pooled` (shipped+control treated as one shipped-order group, the primary basis;
conservative because pooling inflates the reference group's internal spread) assignments and
asks how often the observed within-minus-between separation is matched. At 5 reversed + 3
control runs there are C(13,5) = 1287 relabelings.

### Results (5 reversed runs, final)

| Model | choice-level p (pooled) | param-level separation | param-level p (pooled) | Holm (8 tests) |
| --- | --- | --- | --- | --- |
| Gemini | 0.235 | **+0.047** | 0.00078 | **0.0062** |
| Qwen | 0.679 | **+0.054** | 0.00078 | **0.0062** |
| GPT-OSS | 0.838 | +0.004 | 0.302 | 1.000 |
| DeepSeek | 0.953 | -0.016 | 0.450 | 1.000 |

**0/4 models show decision-level (top-1 choice) order sensitivity. 2/4 (Gemini, Qwen) show
parameter-level order sensitivity**, surviving Holm correction across all eight tests (4
models x 2 instruments). Both significant p-values sit exactly at the permutation floor
(1/1287 = 0.00078): the observed labelling was the most extreme of all 1287 assignments, so
the test is saturated and the true p is bounded above by that figure rather than estimated at
it.

Accuracy against the ground-truth ranking does not move consistently with the ordering
manipulation, and the sign of the (small) shift is inconsistent across models — Kendall's tau,
order_control vs. order_reversed: DeepSeek 0.8974/0.9009, Gemini 0.9293/0.9262, GPT-OSS
0.8988/0.8970, Qwen 0.8895/0.8913 (max gap 0.0035). A low permutation p means the two arms are
*distinguishable*, not that one ordering is more accurate — reversing the alternative order
shifts which parameter values the model returns, not how good the resulting ranking is.

**Do not use McNemar as the headline test here.** It is included in the workbook for
completeness but is structurally underpowered: shipped runs disagree on top-1 for only a
handful of the 195 scenarios, and an exact binomial on that few discordant pairs cannot reach
p < 0.05 at any plausible split. A McNemar null in this workbook is an artefact of the test,
not evidence about ordering.

**Conclusion (unchanged from the 3-run interim result, now at full power):** the calculator
absorbs the ordering perturbation before it reaches the ranking. The perturbation demonstrably
moved extracted parameters upstream (2/4 models, at the permutation floor) and demonstrably did
not move the top-1 decision downstream (0/4 models) — this is the architecture's core claim
(errors in scenario-level parameters cancel across alternatives at the ranking stage) measured
directly rather than assumed. See `paper/paper_draft_working.tex`
`\subsection{Alternative ordering}` (Methods, `sec:alternative-order`) and
`\subsection{Alternative Ordering}` (Results, `sec:res-order`) for the full writeup.

**Incidental finding, also in the paper's Results section:** DeepSeek's run-to-run parameter
agreement was 0.4230 among the shipped runs (collected 2026-07-29) versus 0.6393 (control) and
0.6703 (reversed), both collected 2026-08-03. Both of the same-day arms show the elevated
agreement equally, so this is a session/provider effect, not an ordering effect — without the
contemporaneous control arm this would have been misread as a finding about reversal.

### Reproduction

```bash
# Collection (spends API calls; resume-aware, never re-run a completed run index)
python "Miscellaneous Scripts/run_hybrid_ablation_experiments.py" --collect-only \
    --models <key> --order-arms reversed --order-run-start 1 --order-runs 5
python "Miscellaneous Scripts/run_hybrid_ablation_experiments.py" --collect-only \
    --models <key> --order-arms control --order-run-start 1 --order-runs 3

# Analysis (free, reads existing run outputs). Do NOT narrow --models here: the
# analysis pass overwrites the workbooks with whatever set it was given.
python "Miscellaneous Scripts/run_hybrid_ablation_experiments.py"
```

---

## 3. RAG ablation (Example-Guided Scoring)

**Script:** `Miscellaneous Scripts/run_rag_ablation_experiments.py`
**Outputs:** `Analysis/RAG_Ablation/rag_ablation_{results,summary,summary_by_decision_type,friedman_tests,posthoc_tests,bootstrap_ci}.xlsx`

Evaluated on the **90-scenario RAG corpus**, not the 195 test scenarios. `load_source_df`
reads `RAG_FILES`, and each target is excluded from its own retrieval, making this a
leave-one-out design: the RAG scenarios are simultaneously the queries and the index.
This is a different experiment from the main benchmark, where Example-Guided Scoring
retrieves from the RAG corpus to score the disjoint test set. Do not repoint this script
at the test set without treating it as a new experiment.

### Configurations

| ablation_id | k | retrieval | embedding model | hidden params | scores | ranks | LLM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `control_k3` | 3 | similarity | all-MiniLM-L6-v2 | yes | yes | yes | yes |
| `random_exemplars_k3` | 3 | random | all-MiniLM-L6-v2 | yes | yes | yes | yes |
| `descriptions_no_scores_ranks` | 3 | similarity | all-MiniLM-L6-v2 | yes | no | no | yes |
| `exemplars_no_hidden_params` | 3 | similarity | all-MiniLM-L6-v2 | no | yes | yes | yes |
| `retrieval_k1` | 1 | similarity | all-MiniLM-L6-v2 | yes | yes | yes | yes |
| `retrieval_k5` | 5 | similarity | all-MiniLM-L6-v2 | yes | yes | yes | yes |
| `alternate_embedding_k3` | 3 | similarity | paraphrase-MiniLM-L3-v2 | yes | yes | yes | yes |
| `nearest_neighbor_k3` | 3 | similarity | all-MiniLM-L6-v2 | yes | yes | yes | no (offline) |

### Overall results (90 scenarios, seed 13)

| model | ablation | MAE | RMSE | tau | rho | Top-1 | Top-2 | mean retr. dist. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | control_k3 | 0.0884 | 0.0984 | 0.4887 | 0.5187 | 0.6333 | 0.8889 | 0.0723 |
| deepseek | exemplars_no_hidden_params | 0.0874 | 0.0965 | 0.3911 | 0.4128 | 0.5889 | 0.8444 | 0.0723 |
| deepseek | alternate_embedding_k3 | 0.0876 | 0.0984 | 0.3463 | 0.3749 | 0.4889 | 0.8333 | 1.2152 |
| deepseek | retrieval_k5 | 0.0842 | 0.0941 | 0.3421 | 0.3663 | 0.5222 | 0.8111 | 0.0847 |
| deepseek | retrieval_k1 | 0.0981 | 0.1114 | 0.1822 | 0.1782 | 0.4778 | 0.7778 | 0.0561 |
| deepseek | descriptions_no_scores_ranks | 0.1312 | 0.1465 | 0.0733 | 0.0841 | 0.4111 | 0.7000 | 0.0723 |
| deepseek | random_exemplars_k3 | 0.1267 | 0.1432 | 0.0632 | 0.0675 | 0.3889 | 0.7444 | 0.4477 |
| gptoss | retrieval_k1 | 0.1182 | 0.1377 | 0.2367 | 0.2304 | 0.4667 | 0.7556 | 0.0561 |
| gptoss | alternate_embedding_k3 | 0.1127 | 0.1247 | 0.2268 | 0.2426 | 0.4444 | 0.7778 | 1.2152 |
| gptoss | control_k3 | 0.1045 | 0.1209 | 0.1872 | 0.1682 | 0.4444 | 0.6667 | 0.0723 |
| gptoss | exemplars_no_hidden_params | 0.1058 | 0.1212 | 0.1754 | 0.1844 | 0.4444 | 0.7111 | 0.0723 |
| gptoss | retrieval_k5 | 0.1016 | 0.1162 | 0.1124 | 0.1180 | 0.3889 | 0.7000 | 0.0847 |
| gptoss | descriptions_no_scores_ranks | 0.1577 | 0.1770 | 0.0609 | 0.0652 | 0.3333 | 0.7111 | 0.0723 |
| gptoss | random_exemplars_k3 | 0.1634 | 0.1841 | 0.0222 | 0.0222 | 0.3444 | 0.6889 | 0.4469 |
| qwen | retrieval_k1 | 0.0968 | 0.1128 | 0.3056 | 0.2969 | 0.5222 | 0.8222 | 0.0561 |
| qwen | random_exemplars_k3 | 0.1407 | 0.1568 | 0.2756 | 0.2969 | 0.5778 | 0.8444 | 0.4558 |
| qwen | exemplars_no_hidden_params | 0.0988 | 0.1136 | 0.2730 | 0.2779 | 0.4667 | 0.7444 | 0.0723 |
| qwen | retrieval_k5 | 0.0880 | 0.1002 | 0.2343 | 0.2708 | 0.4889 | 0.7667 | 0.0847 |
| qwen | alternate_embedding_k3 | 0.1039 | 0.1163 | 0.1651 | 0.1640 | 0.4778 | 0.7333 | 1.2152 |
| qwen | control_k3 | 0.1019 | 0.1200 | 0.1535 | 0.1541 | 0.4333 | 0.7444 | 0.0723 |
| qwen | descriptions_no_scores_ranks | 0.1511 | 0.1683 | 0.0711 | 0.0763 | 0.4222 | 0.7556 | 0.0723 |
| offline | nearest_neighbor_k3 | 0.1009 | 0.1159 | 0.0011 | 0.0173 | 0.4444 | 0.7222 | 0.0723 |

Per-decision-type breakdowns and the Friedman / Holm-corrected post-hoc Wilcoxon tests
are in the `Analysis/RAG_Ablation/` workbooks.

**Findings.** Stripping numeric scores and ranks from the retrieved exemplars
(`descriptions_no_scores_ranks`) is the single most damaging change for every model
(tau collapses to 0.06-0.07), so the exemplars carry their value through their scores
rather than through their prose. Random rather than similarity-based retrieval is
comparably damaging for deepseek and gptoss. Retrieval quality dominates retrieval
quantity: k=5 does not consistently beat k=3, and the weaker alternate embedding
(mean retrieval distance 1.2152 vs 0.0723) still performs near control. The offline
nearest-neighbor arm sits near tau = 0 overall, so the LLM is doing more than copying
its nearest exemplar.

---

## 4. Prompt ablation (Direct and Example-Guided Scoring)

**Script:** `Miscellaneous Scripts/run_prompt_ablation_experiments.py`
**Outputs:** `Analysis/Prompt_Ablation/`

Four prompt variants across Direct and Example-Guided Scoring, over the full 195-scenario
test set:

| Variant | Change vs shipped prompt |
| --- | --- |
| `control` | unmodified; must reproduce main-text tau within run-to-run SD |
| `no_anchors` | per-criterion good/moderate/poor anchors stripped, leaving criterion names and the scale |
| `cot_scaffold` | explicit reasoning scaffold before the JSON response |
| `scale_0_10` | response scale 0-1 changed to 0-10, rescaled post hoc |

The harness overrides the system prompt at call time; it does not edit the architecture
modules, so the committed architectures keep producing the main-text results unchanged.
The Direct system prompt is inline in `score_alternative()`
(`Architectures/Direct_LLM_Scoring.py`); the Example-Guided equivalent is in
`score_alternative_with_rag()` (`Architectures/Example-Guided_LLM_Scoring.py`).

Note for interpreting the `scale_0_10` and anchor results: the shipped Direct system
prompt already ends with an explicit anti-clustering instruction ("do not assign the
same score to all 4 criteria... unless performance is actually identical"). Any
central-tendency behavior observed therefore occurs despite active mitigation.

### Results (complete matrix, 2026-07-31)

105 cells, 20,475 scenario rows, 5 runs per combo, overall success rate 0.9955.
Example-Guided has no `no_anchors` arm (its shipped prompt has no anchors), so the
matrix is 105 cells rather than 120.

Headline: **no variant beats the shipped prompt for Example-Guided.** Every
Holm-significant pair involving the control favours the control. The shipped
configuration is not a lucky draw, so no re-run of the main results is warranted.

| Finding | Evidence |
| --- | --- |
| Architecture ordering holds within each model | Every Example-Guided variant > every Direct variant on tau, per model |
| Ordering is robust, calibration is not | Friedman on tau n.s. for all Example-Guided strata (p = 0.470 / 0.184 / 0.057); on Top-1 significant for DeepSeek (p = 1.8e-08) and Qwen (p = 0.007) |
| Effects are mostly small | 11 of 54 pairs significant; 3 reach "small" by Cliff's delta, rest negligible |
| Groups overlap across models | Example-Guided/Qwen `scale_0_10` (tau = 0.102) < Direct/DeepSeek `scale_0_10` (tau = 0.167) |

Two caveats carried into the paper: `cot_scaffold` confounds reasoning with parsing
(it has the lowest success rate in the matrix, 0.961, because the JSON moves behind
free-form text and the parser falls back to the last balanced object), and the
perturbations are one-at-a-time rather than factorial, so interactions are out of scope.

### Significance testing

`Miscellaneous Scripts/test_prompt_ablation_significance.py` and
`Miscellaneous Scripts/test_hybrid_ablation_significance.py` implement no statistics of their
own -- they import `friedman_test_per_metric`, `posthoc_wilcoxon_holm`, `cliff_delta`,
and `bootstrap_ci_per_config` from `run_rag_ablation_experiments.py`, so all three ablations are
tested by the same reviewed code. Tests run within strata (architecture x model for the
prompt ablation, model for the parameter-provenance ablation); pooling would confound
the manipulation with model identity.

Parameter-provenance result: `extracted` beats `default_params` on all three models and
all three metrics, 27 of 27 pairs significant, with medium-to-large Cliff's delta on MAE
(0.35 to 0.48). Extraction contributes real signal over a corpus-median baseline.

---

## Reproduction

```bash
# Parameter-provenance ablation (free, zero API calls)
python "Miscellaneous Scripts/run_hybrid_ablation_experiments.py"

# RAG ablation, full 90-scenario corpus, all four models
python "Miscellaneous Scripts/run_rag_ablation_experiments.py"

# Prompt ablation. Resume-aware: a completed cell xlsx is skipped, so
# re-invoking after an interruption costs nothing for work already done.
# Run ONE process at a time for Example-Guided arms -- concurrent Chroma access
# across processes corrupts the collection handle and yields zero-API failed cells.
python "Miscellaneous Scripts/run_prompt_ablation_experiments.py"

# Rebuild the prompt-ablation summary from every cell file. Needed whenever the
# matrix ran as several partial jobs, since each job's summary covers only its
# own slice.
python "Miscellaneous Scripts/AggregatePromptAblations.py"

# Significance tests (free, read existing outputs)
python "Miscellaneous Scripts/test_prompt_ablation_significance.py"
python "Miscellaneous Scripts/test_hybrid_ablation_significance.py"

# Extraction accuracy per model (free, reads existing outputs).
# --output must be an ABSOLUTE path; a relative path resolves against the
# shell cwd and can raise PermissionError. Expect "Matched scenarios: 195/195".
python "Miscellaneous Scripts/evaluate_parameter_extraction.py" \
  --results "Output Files GPT-OSS 20B/LLM-Parameterized_Reference_Scoring_results.xlsx" \
  --output "/absolute/path/extraction_gptoss.md"

# Regenerate paper/numbers_master.csv, including token-derived cost table
python paper_pipeline/generate_paper_results_numbers.py
```

None of the ablation runners has any parallelism. Wall clock, not cost, is the binding
constraint: a full 195-scenario Direct run against DeepSeek averages 7,412 ms/call and
takes about 72 minutes. Any parallelism added later must preserve `MAX_RETRIES = 10`
with backoff, per-run resume-awareness, and `latency_ms` measured around the successful
POST only.

---

## Cost derivation

`paper_pipeline/generate_paper_results_numbers.py` computes per-run API costs from measured
token totals in each architecture's `*_results_diagnostics_run_*.json`, priced with
rates parsed from `model_config.MODEL_SPECS[...]["label"]`, so a price edit propagates
rather than being duplicated. It is the source of record for the paper's cost table and
is deliberately tracked in git while the rest of `paper_pipeline/` is not.

Measured per-run cost in USD (5-run mean tokens x list price):

| Architecture | Gemini | DeepSeek | GPT-OSS | Qwen |
| --- | --- | --- | --- | --- |
| Direct | 0.8017 | 0.0867 | 0.0234 | 0.0435 |
| Example-Guided | 1.0243 | 0.0365 | 0.0235 | 0.0419 |
| LLM-Parameterized | 0.2798 | 0.0110 | 0.0062 | 0.0119 |

The cost table must be reported to **three decimal places**. Rounded to cents, the
LLM-Parameterized row collapses to 0.28 / 0.01 / 0.01 / 0.01, and the capability-
compression ratio a reader can derive from it changes from 45x to 28x.

DeepSeek is the cost outlier: it emits roughly 295,000 output tokens per Direct run but
only about 21,000 per Example-Guided run, consistently across all five runs. It is a
hybrid-reasoning model that spontaneously reasons on the scoring task, so variants that
encourage reasoning (such as `cot_scaffold`) can exceed a naive token projection.

---

## Known issues

- `Ground Truth/ground_truth_shower.xlsx` can drift out of date relative to
  `Ground Truth Calculators/ShowerGroundTruthCalculator.py`. After changing any
  calculator, run it to regenerate its `Ground Truth/ground_truth_*.xlsx`, then
  `Miscellaneous Scripts/sync_rag_ground_truth_scores.py`, then `Miscellaneous Scripts/build_rag_index.py`
  — in that order. `build_rag_index.py` must always run last, or the Chroma source hash will
  not match the re-exported RAG sheets.
- `Scenario Files/ConsolidatedforSimaltaneousediting.xlsx`, referenced in `CLAUDE.md` and
  in the README repository tree as the master workbook that
  `Scenario Files/build_consolidated_scenario_workbooks.py` derives the Test and RAG sheets from, is not
  present in this repository. The derived standalone sheets (`TestScenarios.xlsx`, the
  three `*RAGScenarios.xlsx`, and the three `*Scenarios.xlsx` masters) are present and
  are what every script actually reads.
- `Miscellaneous Scripts/evaluate_parameter_extraction.py` matches results to ground truth by
  progressive narrowing on the descriptor columns in `MATCH_KEYS`. An earlier
  positional tie-break compared indices from two different coordinate systems (position
  within the Test sheet vs position within the combined Test+RAG master) and silently
  dropped 14 of 195 Shower scenarios, a contiguous tail block containing the only Condo
  and Rowhouse housing types. Any change to the matching logic should be verified to
  resolve all 195 scenarios uniquely for every decision type.
