# V_RERUN_PROOFING: what must be collected in the rerun so it is the last one

Written 2026-09-26 by a read-only methods-review agent. The only file written is this one. No
API calls were made and no git commands were run.

Sources read: `paper/pass6/PASS6_HANDOFF.md` (all), `paper/MOCK_EMS_REVIEW.md` (all),
`paper/pass6/PASS6_PROPOSAL.md` (summary tables, A4–A7), `paper/pass5/RERUN_PREP_PLAN.md`,
`paper/paper_draft_v2.tex` (abstract, Intro, §2.3, §3, §4.4–4.5, Results, Discussion,
Conclusion, availability), `paper/supplementary.tex` (S1 L198–203; S2 L923–980 and
L1193–1411), the four scripts in `Miscellaneous Scripts/experiments/`, the three
`Architectures/*.py` (logging and `query_openrouter`), `sentinel_utils.RawCallLog`, `model_config.py`,
and the diagnostics JSONs in `Output Files*`.

Line numbers: "L" = `paper_draft_v2.tex`, "S-L" = `supplementary.tex`, as of today.

---

## 0. Cost scale used in this report

I computed per-run token use from the shipped diagnostics (`*_diagnostics_run_*.json`, five runs
per cell). I priced it at the lineup's current prices: GPT-OSS $0.018/$0.09, Qwen $0.10/$0.15,
DeepSeek V4 Flash 0731 $0.021/$0.32 (the handoff's listed price, not the stale label), and
Gemini 3.8 Flash $0.75/$3.75. Gemini 3.5's token counts stand in for 3.8's. The script is in the
scratchpad at `v_proof/tokens.py`.

| One run, 195 test scenarios | Gemini | DeepSeek | GPT-OSS | Qwen | All four |
|---|---|---|---|---|---|
| A_D (585 calls) | $0.383 | $0.102 (the 507-token output anomaly; about $0.014 without it) | $0.015 | $0.044 | **about $0.46–0.54** |
| A_E, k=1 (585 calls) | $0.474 | $0.014 | $0.015 | $0.042 | **about $0.55** |
| A_H (195 calls) | $0.129 | $0.006 | $0.004 | $0.012 | **about $0.15** |

- The main benchmark (5 runs × 3 architectures × 4 models, 27,300 calls) comes to about
  **$6.2**. The rest of the handoff's $24–30 figure is the ablations, mostly Gemini's prompt
  ablation.
- Gemini is 70–90% of the cost of every arm below. A GPT-OSS/Qwen/DeepSeek-only arm costs
  cents, but running only three models would look like cherry-picking, so every estimate below
  covers all four models.

---

## 1. Inventory: what the rerun collects

The collect paths come from each script's code. The run counts are the ones the paper reports.
**Script defaults differ from the paper in two places (flagged ⚠)**: whoever runs the collection
must pass the arguments explicitly.

| Experiment | Script / entry point | Arms | Models | Runs | Scenarios | Calls (all models) |
|---|---|---|---|---|---|---|
| Main benchmark | `Architectures/Direct_LLM_Scoring.py`, `Example-Guided_LLM_Scoring.py` (k = `RETRIEVE_K` = 1), `LLM-Parameterized_Reference_Scoring.py` | A_D, A_E, A_H | 4 | 5 (`N_RUNS`) | 195 test | 27,300 |
| Prompt ablation | `run_prompt_ablation_experiments.py` | A_D: control, no_anchors, cot_scaffold, scale_0_10; A_E (k=1): control, cot_scaffold, scale_0_10 (28 cells) | 4 | ⚠ paper: 5 per cell, 10 for A_D control and no_anchors (DeepSeek/GPT-OSS/Qwen), 3 for all Gemini cells (S-L1237, S-L1242). Script default: `--runs N_RUNS` = 5 everywhere. | 195 test | about 80k (paper counts) |
| RAG ablation | `run_rag_ablation_experiments.py` | control_k3, random_k3 (within type), no scores/ranks, no hidden params, k1, k5, alternate encoder, plus copy-only (offline) | 4 | **1** (no `--runs` option) | 90 RAG, leave-one-out | 7,560 |
| A_D position bias | `run_position_bias_control.py run` | A_D reversed order (A_E removed from the script, L37–45) | ⚠ `--model` defaults to qwen, one per invocation; `--n` is 195 and must be passed | 1 per model; compared against the 5 main runs | 195 test | 2,340 |
| A_H order arms | `run_hybrid_ablation_experiments.py --collect-only` | ⚠ paper (L753, S-L1339–1344): **reversed 5 runs + same-session control 3 runs**. Script default: `--order-arms reversed --order-runs 3`, which collects 3 reversed runs and **no control** | 4 | 5 + 3 | 195 test | 6,240 |
| Offline, no API | hybrid `default_params` (dataset median), fixed default, single-criterion floors, α sweep, weight vectors, imputed check, dispersion, duplication, extraction P(flip \| error), tie rates, regret, ensembling | — | — | — | — | 0 |

**Consequences for the collection plan (no extra cost):**

1. **⚠ A_H order arms.** Run `--order-arms reversed control`. The reversed arm needs 5 runs
   (`--order-runs 5`, or 3 then `--order-run-start 4 --order-runs 2`) and the control arm 3. With
   the defaults, the permutation test has C(8,5) = 56 labelings instead of 1,287. Its floor then
   rises from 1/1287 to 1/56 ≈ 0.018, which cannot survive Holm across 8 tests, and both of the
   paper's significant parameter-level separations would vanish by construction. CLAUDE.md
   notes that timestamps make the control optional. Keep it anyway: it costs about $0.45 and
   keeps the 13-run design the paper describes.
2. **⚠ Prompt ablation run counts: decide them before collecting.** See 2.D below. Don't repeat
   the S-L1242 pattern of extending a cell after seeing a borderline p. That is optional
   stopping, and a statistics reviewer will call it that.
3. **Collect the RAG ablation first**, before the main A_E runs. The benchmark's k = 1 was
   "chosen from the ablation" (L740, S-L935) on the *old* models. DeepSeek 0731 and Gemini 3.8
   are different models. If the new RAG ablation favours k = 3 for one of them, the stated
   rationale for k = 1 breaks, and the main A_E would have to be re-collected: that is the
   second rerun. The RAG ablation costs about $2.5 and finishes quickly. Collecting it first
   costs nothing extra (see also 2.C).
4. **Position bias.** Four invocations, one per model, each `--n 195`.

---

## 2. Reviewer asks that would need new API calls

Each item is classified as one of:
- **ADD**: add it to the rerun.
- **COVERED**: current collection or offline analysis already answers it.
- **OUT**: out of scope by an author ruling.
- **DEFER**: answer it in the response letter.

### Tier 1: recommend adding (small cost, plausible insistence)

| # | Ask | Who raises it | Current coverage | Extra calls | Extra cost | Verdict |
|---|---|---|---|---|---|---|
| A | **The ordering of the collection** (RAG ablation before the main A_E) | Implied by R2 maj. 4 | None | 0 | $0 | **ADD** (sequencing only) |
| B | **A_H order arms at their full size** (5 reversed + 3 control) | Already in the paper | Script defaults fall short | 0 beyond plan | about $1.2 in total (already in the $24–30) | **ADD** (explicit arguments) |
| C | **A_E at k = 3 on the 195 test scenarios.** R2 maj. 4: "Benchmark k = 1 … DeepSeek loses ≈0.31 τ at k = 1." The Conclusion (L1112) and L1071 claim that the fixed default outranks A_E "for all four models". That conclusion-level claim rests on a k that handicaps one model, chosen from one run on a different population. | R2, R4 | The RAG ablation covers k = 1/3/5, but only on the 90 RAG scenarios, 1 run, against a different population (A_E MAE 0.070–0.105 there against 0.158–0.194 on test) | 3 runs × 4 models × 585 = 7,020 | about **$2.3** (k=3 input ≈ 1.8× k=1; Gemini ≈ $0.70/run) | **ADD.** It also insures against item A going the wrong way: if the new RAG ablation favours k = 3, the paper can switch without a second rerun. It needs a way to set `RETRIEVE_K` from the command line or environment (a one-line change in the architecture). Show the author the diff, since it touches an architecture file. |
| D | **Pre-registered, uniform prompt-ablation run counts.** Mock review row 6 and S-L1237/S-L1242: Gemini gets 3 runs, the 10-run extension was triggered by a borderline p, and the control differs from the benchmark | R2, statistics reviewer | The script default (5 everywhere) already gives parity | Option 1, the script default (5 runs every cell, Gemini included): Gemini +2 runs × 7 cells; others −5 runs × 2 A_D cells | about **+$8** over paper-matching counts (Gemini is about $4/run across its 7 cells, CoT the priciest) | **ADD (option 1)** if the author accepts about +$8. Then S-L1242 (Gemini rationale) and the post-hoc 10-run sentence in S-L1237/S-L1242 are deleted. The cheaper option 2 keeps Gemini at 3 but states the counts as fixed in advance and drops the post-hoc extension. Because the collection is in one window, the ablation control is now a same-window replicate of the benchmark prompt, so row 6 becomes a sentence of method, not a discrepancy. |
| E | **A listwise A_D arm**: one call scores all three alternatives. R2 maj. 2: pointwise one-call-per-alternative is a design choice that drives the 3-to-1 cost result; listwise judging ranks better in the LLM-as-judge literature. R4 rates the "should not score" scope CRITICAL. | R2, R4, editor ("encouraged, not required") | None. The author dropped A4 (scope sentences), so the broad claim at L1112 ("where a calculator exists we see no reason to use it") stays **unscoped**. The rule "fix, don't disclose" favours the arm over a scope sentence. | 5 runs × 4 models × 195 = 3,900 | about **$1.1** (the A_H call count, about 750 input and 120 output tokens per call) | **ADD, author decision.** Of all the items here, it answers a CRITICAL reviewer point for the least cost. It also removes the cost confound, because listwise makes the same number of calls as A_H. It needs a new prompt (A_D's system prompt and anchors, with the three alternatives in one user message returning 12 scores) and a parser, written as a new arm in an experiment script; the architecture files are not touched. It does not give the model the value model, so it respects that ruling. Risk: a reviewer then asks about the new prompt's wording. Keep the prompt identical to A_D apart from the alternatives block. |

**Tier 1 total: about $3.4 + $8 (D option 1) ≈ $11**, on top of the $24–30 plan. Without D
option 1 it is about $3.4.

### Tier 2: optional (cheap, but a reviewer is unlikely to insist)

| # | Ask | Coverage | Calls | Cost | Verdict |
|---|---|---|---|---|---|
| F | A_E alternative-order reversal (the position-bias control is A_D only; L745 says "every check covers all four models" but the ordering check covers A_D and A_H) | The script comment and S-L1346 argue that A_E changes the same two-element list | 1 run × 4 × 585 = 2,340 | about $0.55 | **DEFER** (S-L1346 is a sound answer). ADD only if the A_E path in `run_position_bias_control.py` is restored *and* its Chroma initialisation is verified in the smoke test: an earlier A_E arm was invalidated because retrieval silently returned nothing. |
| G | More RAG-ablation runs (currently 1 run, n = 90; the k decision and "DeepSeek loses 0.31" rest on one draw) | 1 run | +2 runs = 15,120 | about $5 | **DEFER**, unless item C is skipped. With C, the k question is answered on the test set. |
| H | A paraphrase of A_H's extraction prompt (A_H is the headline, and its prompt was never perturbed; L757 says the three variants have no A_H counterpart) | The order-reversal arm is a partial perturbation of A_H's prompt, with a null on Top-1 | 3 runs × 4 × 195 = 2,340 | about $0.45 | **DEFER.** The order arm answers "is A_H prompt-fragile" at the ranking level. |
| I | Non-templated question text for A_H. R4 CRITICAL: "a regex could do it" on templated questions. The author rejected the parser baseline, so the benchmark can't show the LLM beats a rule reader. | None | 3 runs × 4 × 195 = 2,340 | about $0.45 in API, but it needs a frozen, fact-checked paraphrased question set: real authoring work and a new data artefact | **DEFER, author decision.** It is the only arm that answers R4 under the no-parser ruling. If it is skipped, cover it as a limitation (§4, item U1). |

### Defer (answer in the response letter) or already covered

| Ask | Status | Rationale and cost if the author wants it anyway |
|---|---|---|
| More runs, for variance or CI width | **COVERED** | Tests are over 195 scenarios. Run SD is reported (S2 run-to-run). 10 runs would add about $6.2. |
| Temperature sensitivity (0.3 only) | **DEFER** | 0.3 is deliberate, so that repeated runs sample variation. The ordering gaps are about 10× the run SD. The five-run ensembling null (A7 analysis, offline) shows that noise-averaging doesn't rescue A_D. If wanted: T = 0, A_D + A_H, 2 runs ≈ $1.3. |
| Reasoning on vs off | **DEFER** (partly COVERED) | The `cot_scaffold` variant tests explicit reasoning for A_D/A_E and hurt or didn't help. Abstract version 1 scopes to "low reasoning effort". If wanted: A_D + A_H at higher effort, 3 runs ≈ $12 (≈ $1.5 without Gemini). |
| A stronger frontier model as an upper reference | **DEFER** (author-owned lineup) | The most common LLM-benchmark ask. Version 1's scope wording ("four models at low reasoning effort") is the answer. If wanted: one frontier model, A_D + A_H, 3 runs ≈ $8–20 depending on price and reasoning. |
| A model-size or scale trend | **DEFER** | The four models are not a scale ladder, and the paper claims no trend. L1065's "Qwen is the smallest model … may use exemplar scores as a template" is speculation. Keep it hedged. |
| Exemplar count k | **COVERED** (RAG ablation k = 1/3/5), plus C | — |
| Wrong-type exemplars | **DEFER** | The random arm is within type (`retrieve_random` filters `decision_type`). One more config ≈ 1,890 calls ≈ $0.35. Low value. |
| A second prompt paraphrase for A_D/A_E | **COVERED** | The prompt ablation has 3 perturbations. |
| Extraction-only accuracy for A_H | **COVERED** (offline) | From the `extracted_*` columns and raw responses. Also the "clip rather than fail" counterfactual for GPT-OSS's out-of-bounds failures, which is offline only if raw responses are logged (they are). |
| Self-consistency or ensembling | **COVERED** (offline) | From the 5 runs. The A7 analysis showed a null. |
| Logprobs and calibration | **DEFER** / future work (L1103) | Under `:floor` routing, logprob support varies by provider (Gemini doesn't expose them via OpenRouter), and adding the parameter can change routing. An offline proxy exists: agreement of A_H's extracted parameters across the 5 runs, as a confidence score against Top-1 correctness. |
| A specification-informed A_D (value functions, bounds, penalty in the prompt) | **OUT** | Author ruling: the LLMs are deliberately not given the value model. |
| A label-lookup or text-parse baseline | **OUT** | Author ruling: baselines stay simple medians and modes, no question parser (A2 dropped). |
| A gas or oil heating branch | **OUT** | No calculator changes beyond handoff §2. |
| EnergyPlus or observational validation | **OUT** | Author ruling. |

---

## 3. Logging needed to answer questions later without new calls

What the raw log records now (`sentinel_utils.RawCallLog` plus the three architectures, L369 /
L552 / L490): collected_utc, run, scenario_id, decision_type, alternative(s), requested `model`,
the user prompt with its SHA-256, response content, prompt/completion tokens, latency, retries
(A_D only), api_success, and `rag_exemplar_ids` (A_E).

`query_openrouter` (for example `Direct_LLM_Scoring.py` L212–231) reads `usage`,
`reasoning_tokens` and `finish_reason`, but **only writes them to the log line, never to the
JSONL**, and it never reads `provider` or `id`. Another agent is auditing field by field. The
critical gaps are:

1. **`id` (the OpenRouter generation id)**, per call. The single most valuable field: from it,
   OpenRouter's generation endpoint returns the serving provider, the native token counts and
   the charged cost after the fact.
2. **`provider`** (the serving provider), per call. `:floor` lets the provider and its
   quantization change between calls. Without this field, "run-to-run variance", "Gemini is the
   most stable" (L1059) and every cross-run comparison can't be separated from provider
   switching. The handoff already asks for it (§2, "Model lineup", item 3).
3. **The whole `usage` object**: `reasoning_tokens` and the charged `cost`. It is needed for the
   cost table at charged prices (handoff §1, pipeline item) and to diagnose a recurrence of the
   DeepSeek A_D 507-token anomaly without a re-collection.
4. **`finish_reason`**. It separates truncation from unparseable output. This matters for the
   CoT variant, whose failures S-L1246 attributes to parsing, and no `max_tokens` is set.
5. **`message.reasoning` / `reasoning_details`** when the model returns them (the same anomaly;
   a "reasoning was not disabled" check).
6. **The returned `model` string** (the resolved version) and a **system-prompt SHA-256** plus
   the request parameters (temperature, reasoning payload). They can go once per run in a header
   record, since the user-prompt hash alone doesn't pin the system prompt.
7. A_E: the **retrieval distance** next to `rag_exemplar_ids` (useful for "does A_E fail when the
   nearest exemplar is far?", offline).
8. Check that the ablation scripts' own `query_openrouter` copies (prompt and RAG ablation) and
   the hybrid order arm's JSONL carry the same fields: they build their own requests.

Items 1–4 are cheap to add and are what stands between the rerun and a second collection for any
provider or cost question. Add them before the smoke test and confirm them in it.

---

## 4. Limitations: the ones in the paper, and the ones a reviewer will raise

Classes:
- **FIXED-BY-PREP**: the rerun or the pre-rerun work removes the cause; delete or rewrite the
  sentence.
- **FIXABLE-NOW**: a code, data or extra-arm fix exists now; the entry gives how and the cost.
- **STRUCTURAL**: a genuine scope limit; keep it.
- **AUTHOR-RULED**: an author ruling settles it.

### 4.1 In the paper now

| Loc. | Text (abridged) | Class | Action |
|---|---|---|---|
| L1088 (1st half) | "We grade A_H against the same calculators it uses … A misspecified formula would inflate A_H's accuracy … An independent audit with a separately built calculator would resolve this." | STRUCTURAL | Keep. It is the circularity point, which the panel accepts. |
| L1088 | "…if a criterion the calculator cannot represent becomes important, such as indoor humidity…" | STRUCTURAL | Keep. |
| L1088 (last two sentences) | "Several calculator relationships are unpublished … mains water temperature … monthly appliance cycle rates, a fixed shower tank-availability factor of 0.8, and a run-time-fraction approximation … **These affect all architectures equally**…" | STRUCTURAL, but S-CALC | Re-check the list against `docs/CALCULATOR_PROVENANCE.md` once it is merged: drop any item the provenance work sourced, keep the rest as assumptions. **Flag for the author:** "affect all architectures equally" is doubtful. A_H shares the calculator's imputations with the reference, so they cancel for A_H but not for A_D/A_E. This is a wording issue, not a rerun issue. |
| L1090 | "We calibrated each criterion's 0–1 scoring curve against published standards … normative household … fixed importance weights … single decision-maker … monotonicity…" | STRUCTURAL | Keep. |
| L1092 | "synthetic dataset decouples [house age, insulation, SEER] … Accuracy in real-world use may therefore be lower." | STRUCTURAL | Keep. |
| L1094 (1st sentence) | "Results are specific to Pennsylvania's grid and utility rate structure…" | STRUCTURAL | Keep. |
| L1094 (2nd sentence) | "because PJM's marginal emissions intensity does not vary independently of retail price, the four-criterion specification collapses to an effective three on HVAC and Shower" | Text fix (A11, S1) | Shower's Environmental Impact is water volume, not PJM. Apply A11.1 as planned. |
| L1094 (last sentence) | "We also assume electric resistance water heating in every Shower scenario." | STRUCTURAL | Keep. |
| L947 | "With only three alternatives … τ … likely overstates A_H's ranking accuracy for larger choice sets." | STRUCTURAL | Keep. |
| L1071 (last sentence) | "These results describe how closely the defaults match this dataset's housing stock…" | STRUCTURAL | Keep. The defaults are now retrieval-set medians and modes; update the S4 numbers only. |
| L1103 | "None of the three architectures produces a calibrated confidence estimate…" | STRUCTURAL / future work | Keep. Optional offline proxy (§2, logprobs row). |
| L1108 | "Our metrics measure fidelity to the specified reference model, not real-world decision accuracy." | STRUCTURAL | Keep. |
| L745 | "Run counts differ between cells, which changes the precision of each scenario's estimate but not the power of our tests" | FIXABLE-NOW (item D) | The claim is also doubtful: fewer runs mean noisier scenario means, which lowers the power of a scenario-level test. With uniform pre-registered counts, delete the sentence. $0–8. |
| S-L926–930 | The ablations "were collected against an earlier shower comfort function…", the "0.13 margin", "799 of 14,400…" | **FIXED-BY-PREP** | Delete the whole "Ablation Data Provenance" subsection after the rerun. Every arm is now scored on one reference. |
| S-L1237, S-L1242 | "no_anchors was extended from five to ten runs to give a borderline … comparison enough power"; "Gemini cells use three runs…" | FIXABLE-NOW (item D) | With pre-registered uniform counts, delete both rationales. |
| S-L1339–1344, L753 | "three further original-order runs collected in the same session … to rule out provider drift … per the main text's timestamp convention" | FIXED-BY-PREP (rewrite) | Every arm now carries `collected_utc` in one window. Keep the 3-run control for the 1,287-labeling design (item B), but describe it as a design choice, not a drift fix, and drop the dangling "timestamp convention" (B50/row 20). |
| S-L201 | `:exacto` identifiers, prices "as of August 1, 2026" | FIXED-BY-PREP | S4 (B24): the `:floor` IDs, the collection window, and the charged prices from the `usage.cost` logs. |
| L1136 | "every table … can be regenerated without an API key" | FIXED-BY-PREP | True once the raw logs and `collected_utc` ship with the new outputs (A9 dropped as planned). |
| L404 (last clause) | "so averaging several scoring runs might likewise improve MCDA scores" | Text fix (A7.1, S1) | Already planned for deletion. |
| L1112 | "Direct LLM scoring … so where a calculator exists we see no reason to use it." | AUTHOR-RULED (A4 dropped), FIXABLE-NOW via item E | The claim goes past a pointwise, low-effort design. The listwise arm (about $1.1) either supports it across both designs or shows where it fails. Otherwise R2/R4 will return it. |

### 4.2 Not in the paper, and a reviewer will raise them (nothing can fix them within the rulings; cover them)

These are the ones that "make sense to cover", one sentence each in the A12 rewrite of §6.1:

- **U1. Templated question text.** Every scenario's question and fields come from templates, so
  reading the stated facts is easier than for free-form household descriptions, and the
  benchmark can't separate LLM extraction from any reader of the template. This is R4's CRITICAL
  point, made without mentioning a lookup baseline (ruled out) or dataset features like winner
  position (ruled). It is fixable only by item I.
- **U2. The model set and the scoring design.** Four low-cost models at their lowest reasoning
  tier, one call per alternative. Abstract version 1 states the scope; the body currently
  doesn't. If item E is collected, the one-call-per-alternative half becomes a result instead.
- **U3. Heating fuel.** Every HVAC heating scenario is an electric heat pump (the handoff's
  HSPF-paired method), while most Pennsylvania homes heat with gas or oil (R1 maj. 2, R4's
  "missing stakeholders"). Under B28 this goes into the method description, but the consequence
  for gas-heated households (costs and emissions not modelled) is a scope limit. Keep it as one
  clause. Adding a gas branch is ruled out.
- **U4. Provider and version dependence.** OpenRouter's `:floor` routing and hosted model
  versions that may be retired mean exact re-collection may not be possible. With the provider
  logged per call (§3), this becomes a factual S1 sentence instead of a vulnerability (R3 minor:
  "state that `:exacto` models may be retired").
- **U5. The fixed weights are importance weights**, and the reference is a single normative
  household. Already covered at L1090; no new sentence is needed.

---

## 5. Prioritized action list

1. **Before the smoke test (code, no cost):** add `id`, `provider`, the full `usage` (cost and
   reasoning tokens), `finish_reason`, the reasoning text, the returned model and a
   system-prompt hash to the raw log in all three architectures *and* the experiment scripts'
   own request functions. Confirm them in the smoke-test output.
2. **Write the collection plan with explicit arguments:**
   - hybrid: `--order-arms reversed control`, 5 reversed and 3 control runs;
   - position bias: `--model <each> --n 195`, four times;
   - prompt ablation: `--runs`, decided before collection (item D).
3. **Order of collection:** the RAG ablation first. Confirm k = 1 with the author against a
   decision rule fixed in advance, then collect the main benchmark.
4. **Author decisions, before collection:**
   - (a) item C, A_E k = 3 on test, 3 runs, about $2.3: recommended;
   - (b) item E, listwise A_D, 5 runs, about $1.1 plus new prompt and parser code: recommended;
     the only cheap answer to the CRITICAL scope point, since A4 was dropped;
   - (c) item D, option 1 (uniform 5 runs) at about +$8, or option 2 (keep Gemini at 3, fixed in
     advance);
   - (d) item I, non-templated A_H questions: defer unless the author wants to answer R4 with
     data.
5. **After the rerun:**
   - delete S-L926–930 and the run-count rationales at S-L1237/S-L1242;
   - rewrite S-L1339–1344 and S-L201;
   - in the A12 rewrite, cover U1–U4 and re-check the L1088 "affect all architectures equally"
     sentence.
6. **Response-letter answers, no calls:** temperature, reasoning effort, a frontier model,
   scale, logprobs, wrong-type exemplars and more runs (§2 table).

Git: none run. API: none called. Files written: this report only.
