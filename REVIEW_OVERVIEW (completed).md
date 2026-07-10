# Repository Overview for Review — LLM-MCDA Household Energy Decision Support

**Prepared for:** Dr. River Huang (Paul Scherrer Institut)
**Prepared by:** Ahaan Nigam
**Purpose:** A guided overview of the experiment so you can review the three
architectures (prompts, parameters, MAVT) and the scenario data
(`TestScenarios.xlsx` and the RAG files) without having to reverse-engineer the
code. Each section points to the exact file/function if you want to verify a
claim against the implementation.

> **River:** In general, I think the paper should present itself as a study aimed at identifying the most effective way to apply LLM to support MCDA. This could mitigate some of the disadvantages of the study, which involves a lot of assumptions, limited criteria, and a rather simple setting.

---

## 1. What the experiment measures

We benchmark **three ways of integrating an LLM into an MCDA workflow** for
household energy decisions, scored against a **deterministic, physics-based MAVT
ground truth**. The model and the MAVT weighting are held constant within each
run, so the *integration strategy* is the only variable under test.

- **Decision types (3):** HVAC thermostat setpoint, Appliance run-time
  scheduling, Shower duration.
- **Criteria (4):** Environmental Impact (35%), Energy Cost (30%), Comfort
  (20%), Practicality (15%). Weights are in
  [`model_config.py`](model_config.py) (`CRITERION_WEIGHTS`) and are the single
  source of truth — every architecture and the ground-truth calculator import
  them; nothing recomputes weights at runtime.
- **Test set:** 195 scenarios (70 HVAC / 65 Appliance / 60 Shower), each with 3
  alternatives. This is the file the architectures actually consume:
  [`Scenario Files/TestScenarios.xlsx`](Scenario%20Files/TestScenarios.xlsx).
- **RAG corpus:** a **disjoint** 90 scenarios (35 / 35 / 20) used only to seed
  the retrieval index, never evaluated.
- **Models (4):** GPT-OSS-20B, Qwen 3.5 9B, DeepSeek V4 Flash, Gemini 3.5 Flash
  (`MODEL_SPECS` in [`model_config.py`](model_config.py)).

**Central hypothesis:** the LLM-Parameterized_Reference_Scoring architecture should beat Pure Prompting *even
with weaker models*, because the physics backbone compensates for model
capability.

> **River:**  For decision types => Maybe call it “Decision problems” or  Scnearios”
>
> Weight is one very weak point of the work as the weights are defined in an arbitrary way

---

## 2. The three architectures

All three live in [`Architectures/`](Architectures/), call the same model via
OpenRouter at temperature 0.3, share one retry/timeout policy
([`model_config.py`](model_config.py)), and rank alternatives with the same MAVT
weighted sum. They differ only in **how each alternative is scored**.

### 2.1 Pure Prompting — [`Direct_LLM_Prompting.py`](Architectures/Direct_LLM_Prompting.py)

- **3 API calls per scenario** (one per alternative).
- The LLM is given the homeowner-facing scenario context and asked to return the
  four criterion scores directly as JSON.
- **Prompt:** system prompt with per-decision-type scoring rubric in
  `score_alternative()`; the context fields are built in `build_user_prompt()`.
- **Parameters the LLM sees** (HVAC example): location, outdoor temp, square
  footage, *insulation label* (Poor/Medium/Good — not the R-value), household
  size, housing type, *house-age band*, utility budget. It never sees R-value,
  SEER, GPM, kWh/cycle, tank size, or occupancy context.

### 2.2 RAG-Enhanced — [`Eample-Guided_LLM_Scoring.py.py`](Architectures/Eample-Guided_LLM_Scoring.py.py)

- **3 API calls per scenario.** Before scoring each alternative, it retrieves the
  top *k* = 3 most similar **RAG** scenarios from a ChromaDB index
  (all-MiniLM-L6-v2 embeddings) and injects them as worked examples.
- Each exemplar shows its full parameters (including the engineering values it is
  fine to reveal for a *different* scenario), every alternative, and the
  ground-truth scores + MAVT rank. The model is told to use them as reference but
  score the target independently.
- **Important and deliberate:** the exemplars reveal engineering values of
  *neighbor* scenarios, but the **target scenario's** withheld values are never
  put in the prompt — no leakage of the thing being predicted.
- **Prompt:** `build_system_prompt()` (intentionally a short rubric, because the
  retrieved examples supply the calibration) + `build_user_prompt_with_rag()`.
- The index is built by [`Miscellaneous Scripts/BuildRAG.py`](Miscellaneous%20Scripts/BuildRAG.py)
  and is guarded by a schema-version + source-hash check, so a stale index makes
  the run abort rather than silently use old data.

### 2.3 LLM-Parameterized_Reference_Scoring — [`LLM-Parameterized_Reference_Scoring.py`](Architectures/LLM-Parameterized_Reference_Scoring.py)

This is the architecture worth the closest read.

- **1 API call per scenario.** The LLM does **not** score anything. It only
  *estimates the withheld engineering parameters* the calculator needs:
  - HVAC: R-value, SEER, HVAC age, occupancy context
  - Appliance: appliance type, kWh/cycle, baseline (current) time
  - Shower: GPM (from the flow-rate label), tank size, water-heater setpoint
- The **alternatives are taken verbatim from the sheet**; the deterministic
  calculator parses the numeric content (setpoint / run time / duration), not the
  LLM. All homeowner facts are passed through unchanged.
- The extracted JSON is **validated** before use (`extract_all_with_ai()`):
  every numeric parameter must parse as a finite number inside a physically
  admissible range, and the extracted decision type must match the scenario's
  known type — otherwise the scenario is recorded as a failure (sentinel `1928`),
  never silently defaulted. *(This validation was tightened during my latest
  review — see the change list in §5.)*
- The merged parameters are fed to the matching ground-truth calculator
  (`score_with_ground_truth()`), which runs the identical physics used to produce
  the ground truth.
- **Why this should help weak models:** the LLM is asked only for a handful of
  estimates, and the physics does the scoring. One caveat I want you to be aware
  of: the extracted parameters are *scenario-level* (the same for all three
  alternatives), so extraction error largely cancels in the *ranking* — meaning
  LLM-Parameterized_Reference_Scoring's ranking robustness is partly structural. The score-level error
  (MAE/RMSE) and the Appliance result are the measures that truly test extraction
  quality. This is now stated explicitly in the paper's Limitations.

### 2.4 MAVT scoring (shared)

- Additive weighted sum `s_j = Σ wᵢ · vᵢ(xᵢⱼ)`.
- Value functions: Environmental and Energy Cost are **linear, decreasing**
  (lower raw = better); Comfort and Practicality are **logarithmic, increasing**
  (α = 1.5 and 1.2). Defined in each calculator's `apply_value_function()` and in
  the paper's Table (MAVT criterion specification).
- **Reference ranges** for normalization are the **5th–95th percentiles of the
  realized ground-truth distributions** over the corpus. *(These were recomputed
  to the true dataset percentiles during my latest review — see §5.)*
- A four-tier **budget penalty** multiplies the energy-cost score when monthly
  cost approaches/exceeds the household budget.

> **River:** Regarding MAVT calculation, I don't think you need to rescale the score to [0,10]. A score ranges in [0,1] is more natural.

---

## 3. The ground-truth calculators

In [`Ground Truth Calculators/`](Ground%20Truth%20Calculators/) — one per
decision type. These are pure physics (no LLM). They are deterministic: I
regenerated all three from scratch during review and they reproduce the committed
`Ground Truth/ground_truth_*.xlsx` **byte-for-byte**.

- **HVAC:** ASHRAE-style thermal load (conductive + internal + solar +
  infiltration) → energy via SEER→EER quadratic → cost and PJM-marginal
  emissions; tent comfort around ASHRAE 55 setpoints; practicality includes an
  age/maintenance reliability factor.
- **Appliance:** per-cycle cost at the location's time-of-use rate (6 PA
  utilities) and PJM-marginal emissions; comfort/practicality decay with delay
  from the baseline time (circular clock distance), plus late-night noise and
  household-coordination penalties.
- **Shower:** mixing-fraction physics to a 105 °F delivery target → energy/cost;
  **environmental impact is water volume in gallons** (deliberately *not* CO₂, to
  avoid collinearity with energy cost); comfort peaks near the 7.8-min REU2016
  mean; practicality includes a hot-water tank-capacity constraint.

**Proxy/true design (intentional):** the LLM sees homeowner-accessible labels
(insulation tier, flow-rate label, appliance-age band); the calculator gets the
true engineering value. The LLM never sees the true value, and the calculator
never scores the label directly.

> **River:**  The term "physics" should be reconsidered. You also have indicators like confort, which is not "physics".
>
> And here you need to set different assumptions -> Why the indicator values will lead to the scores.
>
> For Shower case , you should explicitly explain why you use water volumn for enviromental indicator in the paper.

---

## 4. The data files to review

- **[`TestScenarios.xlsx`](Scenario%20Files/TestScenarios.xlsx)** — the 195
  scenarios given to the architectures. Columns are homeowner-facing only
  (no R-value/SEER/GPM/kWh-per-cycle/tank-size/occupancy columns). Banded labels
  (`house_age`, `appliance_age`, `flow_rate`) are produced by the single-source
  helpers in `sentinel_utils.py`.
- **RAG files** — [`HVACRagScenarios.xlsx`](Scenario%20Files/HVACRagScenarios.xlsx),
  [`ApplianceRAGScenarios.xlsx`](Scenario%20Files/ApplianceRAGScenarios.xlsx),
  [`ShowerRAGScenarios.xlsx`](Scenario%20Files/ShowerRAGScenarios.xlsx). These
  carry the raw engineering values and the ground-truth scores (banding is applied
  only at embed/display time). They are **disjoint** from the test set: zero
  shared scenarios for HVAC and Appliance. (Shower shares some question/location
  text but the underlying parameters differ — they are distinct scenarios, not
  duplicates.)
- All Test/RAG files are derived deterministically from the master workbook
  `ConsolidatedforSimaltaneousediting.xlsx` by
  [`rebuild_consolidated.py`](Scenario%20Files/rebuild_consolidated.py), which
  audits provenance on every rebuild.

**Suggested review path:** open `TestScenarios.xlsx`, pick one scenario of each
type, and trace it through (a) the prompt each architecture would build for it
and (b) the calculator that produces its ground truth. Then spot-check a couple
of RAG rows to confirm the engineering values and scores look sane.

---

## 5. Changes made in the latest review pass (please sanity-check these)

A code audit before this review surfaced a few issues I have now fixed. Flagging
them explicitly so you know what changed since you last looked:

1. **Reference ranges → true dataset percentiles.** The normalization bounds in
   all three calculators were literature-anchored envelopes; the paper described
   them as dataset 5th–95th percentiles, which was not exactly true. I recomputed
   them to the actual percentiles of the realized ground-truth distributions
   (HVAC computed over active-conditioning alternatives so the zero-load "Off"
   option doesn't make the floor degenerate). **This changed every ground-truth
   score**, so I re-ran the calculators → `SyncRAGGroundTruth.py` → `BuildRAG.py`;
   all derived state is consistent and the staleness guard passes. New bounds are
   in the paper's reference-range table and the README.
2. **LLM-Parameterized_Reference_Scoring extraction now validates numbers.** Previously a non-numeric
   extraction (e.g. `gpm: "low_flow"`) was silently coerced to 0.0, which could
   produce a fake perfect score. It is now rejected as a failure.
3. **LLM-Parameterized_Reference_Scoring rejects decision-type mismatches.** If the model mislabels a
   scenario's decision type, it is now failed rather than scored by the wrong
   calculator.
4. **Paper corrections:** the LLM-Parameterized_Reference_Scoring description and the parameter tables now
   match the implementation (the LLM does *not* parse alternatives, and does
   *not* receive the parameters some tables claimed); the model list is now
   consistent (the four models above) everywhere; stale leaked metric numbers
   were replaced with placeholders; the Results and Conclusion sections now have
   final scaffolding with placeholders to fill once the runs complete.
5. **Minor:** test files renamed so the 54-test suite is actually collected by
   pytest; the sensitivity analysis now uses the same per-run aggregation and
   deterministic tie-breaking as the headline metrics; README EER text corrected;
   cold-weather shower-comfort shift and shower-practicality shape now documented
   in the paper.

If any of these concern you, the relevant code is cited inline above and in the
paper, and I'm happy to walk through the reasoning.

> **River:** Perhaps you could also report the accuracy of parameter extraction in the LLM-Parameterized_Reference_Scoring parameter, as well as the final score/rank agreement. This could be interesting. As mentioned, the work involves identifying the most effective use of LLMs, so if parameter extraction is highly accurate, it's not surprising that the final accuracy is high.
>
> Maybe the names for the three types of approaches can be improved for better recognization and easier understanding.

> **River:** I also asked AI to give some suggestions for improvement. Maybe they can also be useful:


## AI: Final critical improvement checklist

The following items should be treated as the minimum critical improvements
before presenting the study as a rigorous comparison of LLM-assisted MCDA
architectures.

### A. Correctly define and compare MAVT use

- **Problem:** The architectures do not use MAVT in the same way. Ground Truth
  and LLM-Parameterized_Reference_Scoring explicitly calculate raw physical outcomes and transform them
  through the reference value functions. Pure and RAG directly ask the LLM to
  estimate criterion-level `0–10` value scores and only apply the final additive
  weighting step.
- **Required improvement:** Clearly separate:
  1. raw criterion outcome calculation;
  2. single-criterion value-function transformation; and
  3. additive MAVT aggregation.
- **Completion criterion:** The manuscript explicitly states that Pure and RAG
  do not execute the reference value functions for target scenarios, while
  LLM-Parameterized_Reference_Scoring and Ground Truth do. Claims that all architectures use the “same MAVT
  procedure” are removed or qualified.

### B. Make the architecture comparison experimentally fair

- **Problem:** LLM-Parameterized_Reference_Scoring has direct access to the same calculators and value
  functions used to generate the reference answers. Pure and RAG do not. LLM-Parameterized_Reference_Scoring
  also evaluates all three alternatives jointly through one calculator call,
  whereas Pure and RAG score alternatives independently.
- **Required improvement:** Run controlled ablations that independently vary:
  calculator access, value-function access, retrieval access, visible
  information, joint versus isolated alternative scoring, and LLM call budget.
- **Completion criterion:** Any claimed LLM-Parameterized_Reference_Scoring advantage remains significant
  after comparison against architectures with equivalent information and
  computational access.

### C. Establish whether an LLM is needed

- **Problem:** A simple no-LLM fixed-default-parameter calculator already
  achieves approximately `90.3%` overall Top-1 accuracy and `0.863` mean
  Kendall's tau. This suggests much of the ranking may be recoverable without
  LLM reasoning or accurate hidden-parameter extraction.
- **Required improvement:** Add, at minimum:
  - random-choice baseline;
  - always-first-alternative baseline;
  - simple rule-based baseline;
  - fixed-default-parameter calculator baseline;
  - nearest-neighbor baseline;
  - oracle-parameter calculator upper bound.
- **Completion criterion:** The paper quantifies the incremental contribution of
  the LLM over each non-LLM baseline.

### D. Remove alternative-order leakage

- **Problem:** The first listed alternative is the reference winner in
  approximately `90.8%` of Appliance scenarios and `73.3%` of Shower scenarios.
  An always-first rule reaches approximately `61.5%` overall Top-1 accuracy.
- **Required improvement:** Randomize alternative order independently for every
  run and map predictions back to canonical alternative IDs before evaluation.
- **Completion criterion:** All headline results are reproduced using randomized
  alternative order, and position-wise performance is reported.

### E. Validate the reference model instead of calling it objective truth

- **Problem:** The “Ground Truth” combines engineering calculations with
  author-selected behavioral assumptions, thresholds, budget penalties, comfort
  functions, and practicality rules.
- **Required improvement:** Rename it a `formula-based reference model` unless
  it is independently validated. Separate physical, literature-calibrated,
  expert-selected, and synthetic-benchmark assumptions.
- **Completion criterion:** The reference scores and rankings are validated
  against independent simulations, experts, behavioral observations, or a
  second independently specified model.

### F. Evaluate LLM-Parameterized_Reference_Scoring parameter extraction directly

- **Problem:** Correct final ranking does not demonstrate correct extraction.
  Parameter errors may affect all alternatives similarly and therefore leave the
  ranking unchanged.
- **Required improvement:** Report parameter-level MAE, categorical accuracy,
  error distributions, and the probability that each parameter error changes
  the selected alternative.
- **Completion criterion:** LLM-Parameterized_Reference_Scoring's contribution is demonstrated beyond simply
  reproducing the output of the shared calculator.

### G. Demonstrate that RAG retrieval adds value

- **Problem:** RAG exemplars are Ground-Truth-scored historical scenarios
  containing engineering parameters, criterion scores, MAVT totals, and ranks.
  Current results cannot distinguish useful retrieval from answer-pattern
  imitation or extra-information access.
- **Required improvement:** Run RAG ablations using:
  - random exemplars;
  - no exemplars;
  - descriptions without scores or ranks;
  - exemplars without hidden engineering parameters;
  - different retrieval values of `k`;
  - different embedding models;
  - nearest-neighbor prediction without an LLM.
- **Completion criterion:** Retrieval quality, retrieval distance, and downstream
  accuracy are linked empirically, and RAG significantly outperforms the
  relevant controls.

### H. Prevent data leakage and test generalization

- **Problem:** Test and RAG scenarios are disjoint by scenario, but they come
  from the same synthetic source and may share templates, parameter patterns,
  and alternative structures.
- **Required improvement:** Audit near-duplicates and template overlap. Add an
  external or out-of-distribution test set with unseen wording, locations,
  parameter combinations, and decision structures.
- **Completion criterion:** Performance remains credible on data not generated
  by the same scenario-construction process.

### I. Strengthen uncertainty and statistical analysis

- **Problem:** `N_RUNS = 1` does not measure LLM stochasticity. A small set of
  hand-selected weight perturbations does not adequately characterize MCDA
  preference uncertainty.
- **Required improvement:** Use repeated model runs, paired bootstrap confidence
  intervals, paired significance tests, and full weight-space sampling or SMAA.
  Report score uncertainty, rank stability, failure rates, and decision regret.
- **Completion criterion:** Architecture differences remain robust across model
  randomness, preference weights, domains, and reasonable reference-model
  uncertainty.

### J. Address criterion dependence and cross-domain comparability

- **Problem:** Cost and environmental scores are highly correlated
  (`0.999` HVAC, `0.883` Appliance, `0.968` Shower), creating possible double
  weighting. In addition, Shower environmental impact is water use, whereas the
  other domains use emissions.
- **Required improvement:** Test alternative criterion definitions, remove or
  combine correlated criteria in sensitivity analyses, and avoid interpreting
  pooled cross-domain metrics as measuring identical constructs.
- **Completion criterion:** Conclusions remain stable under defensible
  alternative criterion structures.

### K. Freeze and publish a reproducible experiment

- **Problem:** Changes to value-function ranges, prompts, calculators, data
  derivation, or RAG contents invalidate previous results. The master workbook
  is absent, some tests are skipped, and an audit script contains an absolute
  machine-specific path.
- **Required improvement:** Publish a frozen experiment version containing:
  commit hash, source-data checksums, stable scenario UUIDs, model IDs, provider
  settings, prompts, random seeds, complete outputs, environment lockfile, and a
  one-command reproduction workflow.
- **Completion criterion:** An independent researcher can rebuild the scenarios,
  Ground Truth/reference scores, RAG database, architecture outputs, and all
  tables without manual intervention.
