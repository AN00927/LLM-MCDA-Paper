# Handoff to the next session: the paid rerun and the paper numbers

Written 2026-09-27 at the end of the second cloud session. It replaces the previous handoff,
which is in git history at commit 89ac45c. That handoff's sections 0-4 are all done.

## 0. Read first, and the rules

Read in this order:
1. This file.
2. `CLAUDE.md`.
3. `paper/pass6/CLOUD_AGENT_CONTEXT.md` (standing rules, all binding).
4. `paper/pass6/RERUN_RUNBOOK.md`, which is the procedure for the collection.
5. `paper/pass6/PASS6_HANDOFF.md` sections 5-6, when you reach the paper work.

Rules:
- **Branch:** work on **`main`** (author, 2026-09-28: `cloud-work` was merged into `main` by
  PR #19). The author let the last two sessions commit and push; confirm that permission in
  the new conversation.
- **Paid calls:** none without the author's explicit go-ahead in the conversation. The author
  approved the design in the runbook but has **not** said "collect". They will top up the
  OpenRouter credit when they choose; the balance was $2.93 on 2026-09-27, and the collection
  needs about $23. Show the cost before each paid step.
- **Paper edits:** minimal diffs (CLAUDE.md ABSOLUTE RULE); touch only the quoted span.
  Appendix references use `\ref{}` only. The author compiles in Overleaf.
- **Tables:** never pool across models.
- **Problems:** fix them rather than disclose them.
- **`model_config.py`** is the author's file. Don't edit it; ask.

## 1. Setup

1. `python -m venv .venv && .venv/bin/pip install -r requirements.txt`, then use
   `.venv/bin/python` everywhere.
2. `chroma_rag_db/` is git-ignored, so build it first: `.venv/bin/python build_rag_index.py`.
3. Baseline check: run `MODEL_KEY=<k> .venv/bin/python -m pytest -q tests` for each of `gptoss`,
   `qwen`, `deepseek` and `gemini`. Expect **429 passed** under every key.
4. `git pull origin main`. `model_config.py` pins DeepSeek to `relace/fp4` and sets Gemini's
   effort to `minimal` (both 2026-09-28).

## 2. State at the end of the second session

Done and pushed. Details are in `CLOUD_AGENT_CONTEXT.md`, "State at the end of the second
cloud session".

**Earlier in the session:**
- Opus value review; the author's A1-A8 applied.
- HVAC solar with the 24-h mean irradiance and IECC SHGC/IAC.
- Scenario-temperature season rule; the HSP Eq. 20 degradation cap.
- Shower mains 48.5/68.2 °F and 0.69 showers per person per day.
- Appliance validation tests; `audit_scenarios.py` deleted.
- Paper S1 and S-CALC edits; ground-truth-derived stale text fixed.
- Entropy and MEREC weights regenerated.

**Author decisions B10, B11, B63 and B77** are applied:
- B10: the α clause is deleted.
- B11: "total energy, including electrical system losses". EIA MER Table 2.1 could not be
  opened to confirm that 19.2 quads is the total column; check it once, before submission.
- B63: the supplement uses numeric citations.
- B77: the `CLAUDE.md` R-value tiers are corrected.

**Main L737** now says "Gemini 3.8 Flash". The author asked only for that line.

**Phase R smoke** (`Analysis/rerun_smoke/SMOKE_REPORT.md`):
- 112 of 112 calls succeeded through all three request paths.
- DeepSeek on `relace/fp4`: 15 of 15 calls at 4 workers with no 429s. BaseTen had 429s on 12
  of 27.
- Gemini `minimal` is accepted but reasons as much as `low` and costs the same.
- Listwise arm: 24 of 24 calls parsed.

**Design changes** (all author-approved; code, tests and runbook done):
- **Prompt ablation:**
  - The 0-10 scale variant is cut.
  - 3 runs per cell, fixed in advance, with no top-ups.
  - The control is not collected. `test_prompt_ablation_significance.py` rebuilds it from
    main-suite runs 1-3.
  - The ablation's control messages are now byte-identical to the installed A_D/A_E; this is
    checked at startup and the script refuses to run otherwise. A user-prompt difference was
    fixed: "(0-1)" and A_E's own prompt builder.
  - A_E strata have two variants and get one paired Wilcoxon in the same Holm family as the
    Friedman tests.
- **Reply parsing:** A_D and A_E now use the ablation's lenient reply parser
  (`sentinel_utils.extract_json_object` and `is_numeric_score`). A reply with prose around the
  JSON now parses, and a boolean score is now rejected. All three scoring paths accept and
  reject the same replies, which is tested.
- **A_H order arm:** the same-session control arm is cut. The design is 5 main-suite A_H runs
  plus 5 reversed runs, a permutation test over C(10,5) = 252 labelings.
- **Optional A_E k = 3 arm on the test set:** cut.
- **New listwise A_D arm:** `Miscellaneous Scripts/experiments/run_listwise_direct_ranking.py`.
  - One call per scenario, 5 runs.
  - System prompt: A_D's anchors plus the config weights, and nothing else from the value
    model. Scenario context: A_D's own.
  - Metrics and reference are shared with the prompt ablation. `analyze` compares with
    pointwise A_D per model (Wilcoxon, Holm).
  - Included in `emit_collection_window.py`.
- **k = 1** in the main suite, whatever the RAG ablation shows. Rerun the RAG ablation anyway
  and report how far it moved.
- **Order:** every ablation first, **main suite last**.
- **Nearest-neighbour copy baseline:** fallback `tie`. The default is now **k = 1**, matching
  A_E, and `Output Files/Baselines/` was regenerated.
  - At k = 1 it reaches **τ 0.374 and Top-1 64.6%** with no LLM.
  - That is above every old A_E result (τ 0.208-0.310, Top-1 46.6-53.5%).
  - If this holds after the rerun, A_E's LLM step makes the ranking worse than copying the
    exemplar it retrieves.
  - The paper does not report this baseline in the main text yet (section 5 below).

## 3. Before collecting (blocking)

1. The author says go and has topped up. The balance must be at least 2x the step's estimate.
2. The output folders are empty (runbook section 0.1).

## 4. Collection

Follow `paper/pass6/RERUN_RUNBOOK.md` steps 1-7 exactly:

| Step | What | Calls |
|---|---|---|
| 1 | RAG ablation | 7,560 |
| 2 | A_H reversed arm | 3,900 |
| 3 | Position bias | 2,340 |
| 4 | Prompt ablation | 21,060 |
| 5 | Listwise A_D | 3,900 |
| 6 | Main suite, **last** | 27,300 |
| 7 | Offline analyses | none |

That is 66,060 calls and about $23 in total. After each step, run the step's checks and update
`CLOUD_AGENT_CONTEXT.md` "State". If DeepSeek logs 429s, drop to 2 workers.

After step 1, write the old-vs-new RAG ablation comparison the author asked for:
- per model and configuration: τ, Top-1 and MAE;
- the old values are under `archive/2026-09_pre_rerun/Analysis/RAG_Ablation/`.

## 5. After collection: paper work

### 5.1 Numbers (Phase S4)

- `paper_pipeline/build_numbers_of_record.py` produces the regenerated numbers; diff them
  against `paper/pass5/NUMBERS_OF_RECORD.csv`. Every moved number is an edit.
- Also apply the rerun items of `paper/pass6/verify/STALE_FIX_LOG.md`:
  - Tables S2.3 and S2.4;
  - main:1015;
  - main:613, "all 20 cells";
  - main:1072;
  - README:110 and README:443;
  - the fixed-default and dataset-median numbers.
- Then re-check every claim whose direction could flip:
  - per-model best and worst labels;
  - "for every model";
  - significance calls;
  - the fixed-default and dataset-median comparisons;
  - the MEREC HVAC reversal cell (main ~1006);
  - main:912, which says A_D and A_E fail "mostly on unparseable output". The lenient parser
    changes the failure counts.

### 5.2 Text the design changes require

Line numbers are as of commit f07ddd5. Re-find each span before editing.

- **main:748**
  - "two non-LLM baselines and then run five robustness checks": recount after adding the
    nearest-neighbour copy baseline and the listwise arm.
  - "Run counts differ between cells": check it still holds.
- **main:750-752 (baselines):** add the nearest-neighbour copy baseline. It copies the
  reference ranking of the single nearest RAG scenario, k = 1 like A_E, with the `tie`
  fallback, so it tests what A_E's LLM adds over its own retrieval.
- **main:756 (alternative ordering):**
  - Remove "and collected three more original-order runs at the same time to rule out
    provider drift". State instead that all runs were collected in one timestamped window.
  - Change "all 1,287 ways of labeling five of the thirteen runs" to 252 ways and ten runs.
  - The same applies in S2: supp:1351 "thirteen runs" and `tab:mcnemar_order`.
- **main:760 (prompt ablation):**
  - "three variants" becomes two; delete the rescaled-response clause.
  - Add that each cell runs 3 times and that the control is the main suite's first three
    runs.
  - S2 `tab:prompt_ablation` notes at supp:1249 and supp:1254 describe 10/5/3 runs; replace
    them.
  - `tab:prompt_friedman` now mixes Friedman (A_D) and Wilcoxon (A_E) rows; say so in its
    note.
- **main:1001 (Results):** the "rescaled-response variant" sentence goes; rewrite from the new
  numbers.
- **Listwise arm (new):**
  - One methods paragraph, as a new `\subsubsection` after "Prompt ablation".
  - Its result in Section 4.2 or 4.5 (`\FloatBarrier` rules apply to any new subsection).
  - Its prompt in S1 "Full Prompt Texts" (supp:263 onward).
  - A per-model table in S2.
  - It adds to the proposition's framing but is not a fourth architecture. It is an A_D
    format check.
- **Main Table `tab:incremental-contribution` (main ~790) and Section 4.1:**
  - Add the nearest-neighbour copy row.
  - Say what it means for A_E; this is the finding flagged in section 2.
  - The Discussion's A_E paragraphs (main ~1062-1066) must be rewritten from the result.
- **Models:**
  - supp:202 lists `:exacto` IDs. Replace them with the `model_config.py` IDs and provider
    pins: `:floor`, darkbloom, venice, relace and google-ai-studio flex, plus DeepSeek V4
    Flash 0731.
  - Figure legends at main:64, 115 and 268 and supp:74 and 165, and table rows at main:866 and
    supp:1376, 1441 and 1443, still say "Gemini 3.5 Flash". The author asked only for L737, so
    **ask before changing these**, and recommend changing all of them.
  - README:21, 122, 184 and 258 say the same.
  - Main L737 "minimal for Gemini" matches the config (`minimal`); keep it.

### 5.3 Claims, Discussion, verification

- S5 and S6 as in `PASS6_HANDOFF.md` section 6.
- The Discussion 6.1 rewrite is last, written from the final numbers.
- Phase VER:
  1. the old-string check;
  2. the numbers diff;
  3. a diagnostic compile;
  4. the simulated EMS review.
- The author compiles in Overleaf.

## 6. Still open for the author

- **Before collecting:** the go-ahead and the credit top-up.
- **Title:** candidates are in A5 of `PASS6_PROPOSAL.md`.
- **Flag, not fixed:** main ~699 says the base internal gain prevents zero load at zero ΔT.
  That holds only in cooling mode.
- **Stroudsburg and Quakertown** utility assignment: both stay on PPL.
- **Before submission:** Zenodo DOI, EMS fields, highlights, graphical abstract, and strip
  the co-author TODOs and `todonotes`.
- **Network:** `*.nrel.gov` and `codes.iccsafe.org` were blocked in the cloud container.
  Add them to the environment's allowed domains if a source must be re-opened.

## 7. Gotchas

- **`sync_rag_ground_truth_scores.py`** has no argument parsing and rewrites all three RAG
  workbooks. Restore any unchanged one with `git checkout -- <file>`, or the Chroma source hash
  moves for nothing.
- **`.md` files are git-ignored** except README, CLAUDE and `docs/`. Force-add reports with
  `git add -f`.
- **`merec_weights.py`** now writes to `Scoring Logic and Documentation/method/`.
- **The prompt ablation's summary** has no control rows until the main suite exists. The
  significance script is the source for the paper.
- **`run_hybrid_ablation_experiments.py`** still accepts `--order-arms control`, and
  `run_prompt_ablation_experiments.py` still accepts `--variants control`. Don't pass either
  for the rerun.
- **`Analysis/rerun_smoke/`** holds the smoke outputs, and no pipeline reads it.
