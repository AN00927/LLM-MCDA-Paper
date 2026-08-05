# Workstream B, P1 pass: change log

Files edited: `paper/paper_draft_working.tex`, `paper/supplementary_material.tex`,
`paper/cas-refs.bib`. No git command that writes was run. Zero API calls to
OpenRouter.

This log covers the P1 pass only. Everything already recorded in
[B_P0_CHANGES.md](B_P0_CHANGES.md) is excluded, so the two documents do not
double-count. Items 1 through 13 were performed by the P1 agent that was killed
by a session limit before it could write this file; they are reconstructed here
from `git diff` against HEAD and verified against source data. Items 14 and 15
were performed in the finishing pass, together with the sweep in the last
section.

Line numbers are post-edit. Sources are abbreviated:
**RN** = `paper/REVISION_NUMBERS.md`,
**CR** = `Analysis/consolidation_report.md`,
**WF** = `Analysis/workstream_f_report.md`,
**code/data** = read directly from the repository.

---

## Item 1. The fifth central-tendency site

The P0 pass cleared four assertions that $\mathcal{A}_{\text{D}}$ compresses
scores toward the middle of the scale. P1 cleared the fifth, in the Comparison
with Prior Work subsection.

**Line 1485** (Discussion, Comparison with Prior Work). Before: "exemplar scores
function as calibration anchors that set the output scale but cannot compensate
for the underlying central-tendency bias." After: "...cannot compensate for the
over-separation documented in Section~\ref{sec:res-ranking}:
$\mathcal{A}_{\text{D}}$'s within-scenario MAVT range runs 1.25 (Qwen) to 2.00
(DeepSeek) times the reference's, and under $\mathcal{A}_{\text{E}}$ it still
runs 1.19 (Qwen), 1.13 (DeepSeek), 1.41 (Gemini) and 1.43 (GPT-OSS) times it."
Source: RN 1.3 (`paper/dispersion_diagnostics.csv`).

**Verification.** `central.tendency|central tendency|centrality bias|regress.*to
the mean|collapse.*toward 0.5|cluster near 0.5|compress.*toward the middle` now
returns exactly one hit across both files, line 985, which is the Results
sentence stating the prediction is falsified. The Literature Review prediction
at line 314 is unchanged by user decision.

## Item 2. Gemini's parameter-provenance row and the four-identical-rows check

Source: `Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx`, WF F1.

**Table `tab:param_provenance`, lines 1146--1149.** Three Gemini rows added after
DeepSeek: True (ceiling) 1.000 / 1.000 / 0.000; LLM-extracted 0.921 / 0.928 /
0.047; Corpus median 0.641 / 0.769 / 0.122.

**Line 1154 (tablenote).** Before: "...so it is identical across models.
Scenarios whose extraction failed are excluded from that arm rather than
defaulted; the extracted arm scored 194 of 195 scenarios for GPT-OSS and 195 for
the other two models." After: "...so it is identical across models, and the four
identical 0.641 / 0.769 / 0.122 rows serve as a second correctness check on the
harness. ... 195 for the other three models."

**Line 1163.** "all three models" $\to$ "all four models", twice in the same
sentence.

## Item 3. The $\mathcal{A}_{\text{H}}$ prompt-perturbation floor argument

The ablation never perturbed $\mathcal{A}_{\text{H}}$'s extraction prompt, which
left the magnitude of its advantage unbounded. P1 bounded it using the
corpus-median arm as a floor.

**Line 1497** (Limitations). Added after "may reflect a fortunate
extraction-prompt draw":

> Its sign does not, and the parameter-provenance ablation is what bounds it. An
> extraction prompt that recovered nothing scenario-specific would leave the
> architecture at the corpus-median arm of Section~\ref{sec:res-paramprov}, which
> performs no per-scenario inference at all and still reaches $\tau = 0.641$.
> That floor sits above every $\mathcal{A}_{\text{E}}$ figure recorded in this
> study: 0.328 for DeepSeek, 0.305 for Gemini, 0.270 for GPT-OSS and 0.207 for
> Qwen on the main benchmark, and a maximum of 0.325 across all four models and
> all prompt variants in Table~\ref{tab:prompt_ablation}. No perturbation of the
> extraction prompt can therefore reverse the architecture ordering, because
> degrading the prompt to the point of carrying no information still leaves
> $\mathcal{A}_{\text{H}}$ ahead.

Sources: 0.641 from `hybrid_ablation_summary.xlsx` corpus-median arm; the four
$\mathcal{A}_{\text{E}}$ main-benchmark values from `paper/numbers_master.csv`;
0.325 is Gemini's control cell in Table 11
(`Analysis/Prompt_Ablation/prompt_ablation_summary.xlsx`).

## Item 4. Stouffer combination replaced by per-model reporting

Combining four Wilcoxon tests by Stouffer's method assumed independence the four
models do not have: they score the same 195 scenarios against the same ground
truth, so the per-scenario paired differences are positively dependent and the
combined $p$ is anti-conservative by an unknown factor.

**Main paper, line 979.** Before: "Pairwise differences between architectures are
significant under Wilcoxon signed-rank testing (Stouffer-combined $p < 0.001$ for
each adjacent pair on $\tau$, MAE, and Top-1; full results in Supplementary
Material S2)." After: a per-model report of all 24 tests (two adjacent pairs,
three metrics, four models), all surviving Holm correction, with the three
largest adjusted values named (Gemini $\mathcal{A}_{\text{D}}$ vs.
$\mathcal{A}_{\text{E}}$ on $\tau$ and Top-1 at $p_{\mathrm{Holm}} = 0.0092$
each, DeepSeek on $\tau$ at 0.0018), the reason no combination is reported, the
Gemini zero-median reading note with Cliff's $\delta$ ($-0.128$ on $\tau$,
$-0.143$ on Top-1), and the GPT-OSS $n = 194$ note.

**Supplementary, line 773.** Subsection title "Pairwise Wilcoxon Tests with
Stouffer Combination" $\to$ "Pairwise Wilcoxon Tests, Reported Per Model".

**Supplementary, line 775.** The Stouffer paragraph was replaced with the
per-model account, including the statement that all 24 comparisons survive Holm
correction whether corrected across the 24 tests shown or across the full 56-test
family, so nothing is lost by dropping the combination.

Source: `paper/per_model_pvalues.csv`.

## Item 5. Unified provenance readings

The extraction gain was quoted as "roughly 0.26" in one place and left implicit in
another. P1 made both read from the same per-model range.

**Line 1123.** "a gain of roughly 0.26 in $\tau$" $\to$ "a gain of 0.26--0.28 in
$\tau$".

**Line 1167.** "since extraction accounts for most of the gap between the
median-parameter arm and full performance" $\to$ "since extraction accounts for
the 0.26--0.28 gap in $\tau$ between the median-parameter arm and full
performance."

Source: `hybrid_ablation_summary.xlsx`; extracted $\tau$ 0.897--0.921 against the
corpus-median 0.641.

## Item 6. Abstract: per-model ranges, means labelled as four-model means

**Line 255.** Before, three bare point estimates: "$\mathcal{A}_{\text{H}}$
achieved a Kendall's tau of 0.899 and 91.3\% Top-1 accuracy across 195 scenarios;
$\mathcal{A}_{\text{E}}$ scored 0.277 and 49.2\%, and $\mathcal{A}_{\text{D}}$
0.093 and 34.1\%." After: "Over 195 scenarios and four models,
$\mathcal{A}_{\text{H}}$ achieved a Kendall's tau of 0.880--0.923 and
89.7--93.1\% Top-1 accuracy (four-model means 0.899 and 91.3\%);
$\mathcal{A}_{\text{E}}$ scored 0.207--0.328 and 47.0--54.5\% (means 0.277 and
49.2\%), and $\mathcal{A}_{\text{D}}$ 0.010--0.176 and 30.0--36.7\% (means 0.093
and 34.1\%)." Every pooled figure that survives is now labelled a four-model mean.

The same line gained a sensitivity sentence: "Under a seven-vector weight
sensitivity analysis, $\mathcal{A}_{\text{H}}$ leads $\mathcal{A}_{\text{E}}$ in
all 28 model $\times$ vector cells, while $\mathcal{A}_{\text{E}}$'s lead over
$\mathcal{A}_{\text{D}}$ reverses in two MEREC cells; three ablation suites
separate retrieval depth, prompt wording, and parameter provenance."

Source: `paper/numbers_master.csv`; the two MEREC reversals are the Gemini cells
quoted at line 1252.

## Item 7. Latency non-report

**New paragraph, line 1353** (Results, Efficiency and Cost):

> Wall-clock latency was recorded for every API call but is not reported here.
> The collection machine's power state was not controlled, so sleep and
> efficiency-mode transitions during long runs enter the recorded intervals, and
> the resulting values do not support comparison across models or architectures.
> The call and token counts above carry no such contamination and are the basis
> for every efficiency claim in this section.

The `latency_ms` field remains in the run diagnostics; no latency figure is quoted
anywhere in either file.

## Item 8. Circularity paragraph  **(PROVISIONAL)**

**Line 1499** (Limitations). Before, the paragraph closed: "Nonetheless, a blind
schema review by an independent engineer would strengthen this claim." After, it
closes:

> Two further facts bound the risk. The second author reviewed the calculator
> specification and the validation bounds before any benchmark results existed,
> so that review was pre-specification and could not have been fitted to the
> outcome; and his CRediT contribution covers Validation, Conceptualization,
> Methodology, Supervision, and Writing (Review \& Editing), with no Software
> role, so he reviewed code he had not written. Neither fact makes the review
> independent. The reviewer is a co-author of this paper and a supervisor of the
> project it reports, so a review by an engineer outside the project remains
> desirable (Section~\ref{sec:futurework}).

**This item is provisional.** The claim "reviewed the calculator specification and
the validation bounds before any benchmark results existed" describes a scope the
user intends to supply precisely and has not yet supplied. The CRediT roles are
verifiable from the author-contribution statement; the review scope and its timing
are not yet sourced. The user should confirm or correct the scope sentence before
submission.

## Item 9. EMS reframing in abstract and conclusions

Target journal is Environmental Modelling & Software, which weights reusable
frameworks and released software over new model architectures.

**Line 255** (abstract). "This study evaluated whether LLMs can bridge that gap by
comparing three architectures" $\to$ "This study contributes an evaluation
framework and an open reference implementation for LLM-fronted MCDA in
residential energy, and uses it to compare three architectures". A closing
sentence was added: "The calculators, scenario corpus, and analysis code are
released."

**New paragraph, line 1548** (Conclusion). States the contribution as a framework
plus reference implementation rather than a new architecture, and itemizes what
ships: three deterministic MAVT calculators, a 285-scenario corpus split 195 test
/ 90 retrieval, a harness reporting $\tau$, Top-1, Top-2, MAE and RMSE per model
and per decision type, seven weight vectors including entropy- and MEREC-derived
arms, a four-value curvature sweep, three ablation suites, and an exact
permutation test on alternative ordering.

## Item 10. Weighted-score tie rates

The tie-breaking rule was disclosed but its firing rate was not, leaving a reader
unable to judge how much of the reported ranking is decided by the rule rather
than by the model.

**Line 707** (Methodology, outside the protected range). Added after the
tie-breaking sentence:

> The rule fires often enough to disclose, because $\mathcal{A}_{\text{D}}$ and
> $\mathcal{A}_{\text{E}}$ scores come from the LLM on a coarse grid. At least two
> alternatives share a weighted score in 3.2\% of Gemini's
> $\mathcal{A}_{\text{D}}$ scenarios, 5.9\% of DeepSeek's, 12.6\% of GPT-OSS's and
> 21.3\% of Qwen's, and in 2.7\%, 19.1\%, 6.4\% and 13.9\% of the same four
> models' $\mathcal{A}_{\text{E}}$ scenarios. All three alternatives carrying
> identical scores on all four criteria is rarer, between 0.0\% and 1.2\% in every
> model--architecture cell, so the rule usually separates alternatives that
> already differ on at least one criterion.

**Source and verification.** Not `Analysis/duplication_rates_all_runs.xlsx`, which
measures a different quantity (identical *energy-cost and environmental* scores
within one alternative, the basis of `paper/duplication_table.tex`). These rates
were recomputed in the finishing pass from the 20 per-run workbooks
`Output Files */{Direct,Example-Guided}_LLM_Scoring_results_run_0*.xlsx`, as the
five-run mean share of scenarios in which at least two alternatives carry the same
`weighted_score` (rounded to 6 dp, sentinel rows dropped). All eight rates
reproduce to the stated precision: $\mathcal{A}_{\text{D}}$ 3.2 / 5.9 / 12.6 /
21.3 and $\mathcal{A}_{\text{E}}$ 2.7 / 19.1 / 6.4 / 13.9. The all-four-criteria-
identical rate spans 0.0--1.2\%, matching the sentence's bound.

## Item 11. The $n = 3$ resolution bound

**Line 1520** (Limitations, Threats to External Validity). Added mid-paragraph:

> Three alternatives also bound the resolution of the correlation measure itself:
> per-scenario Kendall's $\tau$ can take only the four values $-1$, $-1/3$,
> $+1/3$ and $+1$, so every per-scenario $\tau$ reported in this paper is a mean
> over a four-level variable, and differences smaller than the spacing between
> adjacent levels are resolved only in aggregate.

This makes explicit what Section 3.9 (line 840) already states about the discrete
support of $\tau$ at $n = 3$, and it is the reason small per-model $\tau$
differences are not read as separable.

## Item 12. Collection window

**New paragraph, line 1518** (Limitations, Threats to External Validity):

> The benchmark runs were collected between 2026-06-28 and 2026-07-21. Those dates
> are reconstructed after the fact from version-control commit metadata rather
> than recorded inside the run artifacts, so they bound collection from above
> rather than dating it exactly; the shipped runs carry no internal timestamp, and
> the architectures now stamp a UTC \texttt{collected\_utc} field on every run.
> Within each architecture the four models were collected together, which makes
> cross-model comparisons at fixed architecture contemporaneous, while
> cross-architecture comparisons span up to three weeks and cannot rule out a
> provider-side model update inside that window.

Source: `paper/collection_window.csv`, `paper/collection_window_summary.csv`.

The same paragraph's neighbour at line 1516 had "Lower temperatures reduce
variance but may increase central-tendency bias" changed to "may narrow the
model's output range", which is the sixth and last site of Item 1.

## Item 13. Baseline aggregation disclosure

The LLM rows of `tab:incremental-contribution` are per-type arithmetic means; the
two non-LLM rows are pooled over all 195 scenarios. That mismatch was undisclosed.

**Line 990.** Added: "The two non-LLM rows of
Table~\ref{tab:incremental-contribution} are pooled over all 195 scenarios
instead, because that is the form in which both baselines are reported elsewhere
in the paper", with the size of the resulting discrepancy given.

**Line 1015 (caption).** "The LLM rows are per-type arithmetic means; the two
non-LLM baseline rows are pooled over all 195 scenarios, which moves them by less
than 0.004 relative to their per-type means."

**Line 1020.** The FixedDefault per-type average (0.610) and the pooled figure the
table reports (0.614) are now both stated, so the two aggregations are visible
side by side. Source: RN 3.1--3.2.

---

# Items performed in the finishing pass

## Item 14. Inference energy and carbon footprint

The paper is about residential energy and never stated what running the benchmark
itself cost. A draft paragraph existed at line 1355 that reported pooled totals
and declined to estimate energy. It was replaced for two reasons: it pooled the
token and call counts across models, and one of its three figures was a
triple-count (see the Flags section).

**Line 1355**, new text (call and token counts, per model):

> The benchmark's own inference footprint was recorded per call. Summed over the
> main benchmark, the RAG ablation and the prompt ablation, the four models
> consumed 26.5 million tokens across 35,028 calls (DeepSeek), 17.2 million across
> 21,000 (Gemini), 29.0 million across 35,040 (GPT-OSS) and 47.7 million across
> 35,040 (Qwen), for 120.4 million tokens across 126,108 calls. The main benchmark
> accounts for 27,288 of those calls (17.5 million input and 3.3 million output
> tokens), the RAG ablation for 7,560, and the prompt ablation for 91,260 across
> its 156 runs. The hybrid ablation and the alternative-ordering arm are excluded
> because their per-call token counts were not retained.

Derivation, all from repository data:

| Stage | Source | Calls | Tokens |
|---|---|---|---|
| Main benchmark | 60 files `Output Files*/**/*diagnostics_run_*.json`, fields `total_api_calls`, `total_tokens_input`, `total_tokens_output` | 27,288 | 20,801,731 |
| RAG ablation | `Analysis/RAG_Ablation/rag_ablation_results.xlsx`, deduplicated on (`model_key`, `ablation_id`, `sample_seed`, `source_scenario_id`) | 7,560 | 8,131,810 |
| Prompt ablation | 156 files `Analysis/Prompt_Ablation/cell_*_run_*.xlsx`, columns `api_calls`, `prompt_tokens`, `completion_tokens` | 91,260 | 91,486,559 |
| **Total** | | **126,108** | **120,420,100** |

Per model: DeepSeek 35,028 calls / 26,493,547 tokens; Gemini 21,000 /
17,196,639; GPT-OSS 35,040 / 29,042,358; Qwen 35,040 / 47,687,556. The prompt
ablation token total cross-checks against the `tokens_per_run` $\times$ `n_runs`
product in `prompt_ablation_summary.xlsx` (91,486,559, exact match), and the call
count against $156 \times 195 \times 3 = 91{,}260$.

**Line 1357**, new paragraph (energy and carbon). An order-of-magnitude estimate
was judged supportable and is given with its assumptions in the same sentences.
It applies the 0.16--0.60 Wh interquartile range for production hosted inference
to 126,108 calls, giving 20--76 kWh, and converts at the IEA 2024 global average
of 445 g CO$_2$/kWh to 9.0--34 kg CO$_2$e, with the two published medians (0.24
and 0.31 Wh) landing at 13 and 17 kg. The paragraph names the two errors of
opposite sign inside that bracket (three of the four models are smaller than the
200-billion-parameter systems the measurements cover; the calls here average 955
tokens, longer than the consumer chat queries the measurements assume), states
that the grid factor is a generic global average **rather than** the paper's PJM
marginal factors and why (OpenRouter does not disclose the serving datacenter),
and closes by naming the token and call counts as the measured quantity.

**Three bibliography entries added** to `paper/cas-refs.bib`:

- `elsworth2025googlescale` --- Elsworth, Huang, Patterson, Schneider, Sedivy,
  Goodman, Townsend, Ranganathan, Dean, Vahdat, Gomes, Manyika, "Measuring the
  Environmental Impact of Delivering AI at Google Scale", arXiv:2508.15734, 2025.
  Median 0.24 Wh per Gemini Apps text prompt, boundary includes accelerator power,
  host system, idle capacity and datacenter overhead at PUE 1.09.
- `oviedo2026energy` --- Oviedo, Kazhamiaka, Choukse, Kim, Luers, Nakagawa,
  Bianchini, Lavista Ferres, "Energy use of AI inference, efficiency pathways, and
  test-time scaling", *Joule*, 2026 (arXiv:2509.20241). Median 0.31 Wh/query, IQR
  0.16--0.60 Wh, frontier-scale models above 200B parameters on H100 nodes.
- `iea2025electricity` --- International Energy Agency, "Electricity 2025:
  Analysis and Forecast to 2027", 2025. Global average generation intensity 445 g
  CO$_2$/kWh in 2024.

No DOI is asserted for the Joule entry because the DOI was not verified; the
arXiv identifier is given in a `note` field instead.

## Item 15. Automation bias and distributional fairness

Both topics were absent from the manuscript. Two paragraphs now sit at the end of
the Scope Boundaries subsection, after the implementation-cost paragraph.

**Line 1526, automation bias.** Grounded in this paper's own measurements rather
than in generalities: $\mathcal{A}_{\text{D}}$ places the reference-best
alternative first in 30.0--36.7\% of scenarios against a 33.3\% chance level and
falls below chance on Top-1 in 8 of 12 model--decision-type cells;
$\mathcal{A}_{\text{E}}$ reaches 47.0--54.5\%; a household following an
$\mathcal{A}_{\text{D}}$ recommendation on HVAC does about as well as choosing at
random while receiving an answer that reads as analysed. The finishing pass added
the calibration sentence:

> None of the three architectures emits a calibrated confidence estimate, so a
> scenario the model has ranked correctly and one it has inverted arrive in the
> same form, and the household has no signal telling the two apart.

The paragraph names the mitigation: expose the estimated parameters and the
per-criterion scores alongside the ranking.

**Sources and verification.** The Top-1 ranges verify exactly against
`paper/numbers_master.csv` (Method A, per-run-then-average):
$\mathcal{A}_{\text{D}}$ 0.3001 (Qwen) to 0.3668 (DeepSeek),
$\mathcal{A}_{\text{E}}$ 0.4698 to 0.5446, $\mathcal{A}_{\text{H}}$ 0.8972 to
0.9313. The same file confirms every range in the abstract (Item 6). The 8-of-12
count was recomputed from `paper/per_run_metrics/per_run_metrics_all.csv`,
five-run mean Top-1 by model and decision type: DeepSeek 31.71 / 19.79 / 61.94,
Gemini 24.92 / 25.43 / 61.00, GPT-OSS 26.77 / 39.71 / 33.00, Qwen 23.15 / 32.66 /
34.33 (Appliance / HVAC / Shower). Exactly 8 of the 12 fall strictly below 33.33.

Note for anyone re-checking this: `Analysis/MetricsSummary/metrics_summary_all_models.xlsx`
gives a different set of figures (for example $\mathcal{A}_{\text{D}}$ Qwen Shower
at 33.33 rather than 34.33), because it is computed under aggregate-then-evaluate
rather than the per-run-then-average aggregation the main results use. Under that
file the count would read 7, not 8. The main text is correct as written; the
mismatch is an aggregation difference, not an error.

**Line 1528, distributional fairness.** States that every scenario is set in one of
48 Pennsylvania municipalities on one of six utility tariffs inside the PJM
footprint and assumes the occupant controls the setpoint, run time and
water-heater configuration; that apartments and condominiums are represented but a
renter who cannot change the setpoint or replace the heater is out of scope, as is
any household outside PJM; and that the comfort criterion's ASHRAE 55 setpoint
optima and its occupancy penalty above three people encode one account of what a
comfortable home is. The finishing pass added the practicality sentence, which the
paragraph was missing:

> The practicality criterion assumes the same about time: it charges every scenario
> the same penalty per hour of delay and a further penalty for run times between
> 22:00 and 07:00, which presumes an occupant free to move a wash or a dry. A
> shift worker, a carer, or a household sharing one machine faces a delay cost the
> criterion does not represent.

Source for the practicality behaviour:
`Ground Truth Calculators/ApplianceGroundTruthCalculator.py`,
`calculate_practicality_score` lines 210--256 (monotone decreasing base score in
`delay_hours`; `timing_penalty` of 2.0 for 00:00--06:00 and 1.0 for 22:00--24:00;
`coordination_penalty` scaling with occupant count).

## Item 16. RAG ablation call count corrected

**Supplementary, line 604.** Before (set by the P0 pass): "Across all LLM
configurations 22,680 scoring calls were made with 6 failures (0.03\%)." After:
"Across all LLM configurations 7,560 scoring calls were made (4 models $\times$ 7
configurations $\times$ 90 scenarios $\times$ 3 alternatives) with 2 failures
(0.03\%), both on DeepSeek."

**Why.** `run_rag_ablation_experiments.py` accumulates `api_calls`,
`successful_calls` and `failed_calls` per *scenario* (line 740, inside
`for alt in scenario["alternatives"]`), then writes that same scenario-level
diagnostic into each of the three per-alternative output rows (line 1298,
under the comment "flatten to per-alternative rows"). Summing the raw column
therefore triples every count. Deduplicating on (`model_key`, `ablation_id`,
`sample_seed`, `source_scenario_id`) gives 2,520 scenario-evaluations
(= 4 models $\times$ 7 configurations $\times$ 90 scenarios), 7,560 calls, 7,558
successes and 2 failures, both on DeepSeek. The failure *rate* is unaffected
(0.026\% either way) because numerator and denominator were tripled together,
which is why the error survived.

The pre-P0 manuscript carried the same error at three models (17,010 = 5,670
$\times$ 3); P0 rescaled it to four. The value was therefore last set by these two
passes, which is why it was corrected rather than only flagged. **The correction
is flagged for user review** in case the intended unit was something other than
one API call.

---

# Task 4: final consistency sweep

## 1. Surviving three-model claims about the ablations

None. Every remaining "three models" phrase is correct in context:

- Line 269 (Introduction, protected): "three architectures across three household
  energy decision types". Not about models.
- Line 762: "the five or ten the other three models use". Correct; Gemini is the
  fourth.
- Line 1154: "195 for the other three models". Correct.
- Line 1497: "across three controlled perturbations, four models". Correct.
- Supplementary line 979: "$\mathcal{A}_{\text{E}}$ differences are small for
  three models but reach 0.104 for GPT-OSS". Correct; three of four.

No "Gemini is excluded" text survives in either file.

## 2. Family sizes

| Family | Stated where | Value | Arithmetic |
|---|---|---|---|
| RAG Friedman | line 760 ("sixteen-test family of four models by four metrics"), line 1270 ("16-test Friedman family") | 16 | 4 models $\times$ 4 metrics |
| Prompt ablation Holm | line 770 ("sixteen Holm-corrected Friedman omnibus tests"), supplementary lines 855 and 872 ("16-test family") | 16 | 8 strata $\times$ 2 metrics |
| Hybrid ablation | line 778 ("twelve Holm-corrected Friedman omnibus tests"), line 1161 ("twelve-test family") | 12 | 4 models $\times$ 3 metrics |
| Main pairwise Wilcoxon | line 842, supplementary line 775 | 56 | 2 pairs $\times$ 7 metrics $\times$ 4 models |
| Per-model subset shown in supplementary | line 775, main line 979 | 24 | 2 pairs $\times$ 3 metrics $\times$ 4 models |

All consistent. No stale 9-test or 12-test RAG/prompt figure remains.

## 3. Pooled-across-models figures

Every surviving instance is labelled or accompanied by per-model values:

- Line 1270: the pooled $k{=}1$ minus $k{=}3$ interval $[-0.120, 0.052]$ is
  explicitly a pooled diagnostic, cited to show that pooling conceals DeepSeek's
  reversal, with all four per-model intervals given alongside.
- Line 255 (abstract): three pooled means, each labelled "four-model mean" and
  each preceded by its per-model range.
- Lines 990, 1015, 1020: "pooled" refers to pooling over the 195 scenarios rather
  than over models, disclosed in prose and in the caption.
- Lines 1215, 1252: "pooled" refers to weight vectors applied across decision types
  rather than per type. Not a cross-model pool.
- Supplementary line 604: the previous cross-model RAG estimates are stated as
  withdrawn, with the reason.
- Supplementary line 948 and `tab:imputed_comparison`: the pooled $\mathcal{A}_{\text{H}}$
  fall from 0.899 to 0.871 is labelled a four-model average that no individual
  model exhibits, and the table breaks $\mathcal{A}_{\text{H}}$ out per model.

The new footprint paragraph reports calls and tokens per model; its stage
subtotals are resource sums, not performance metrics.

## 4. References, labels, floats

- Unresolved `\ref` targets: **none**, across both files.
- `\ref` targets present in HEAD and missing now: **none**, in either file.
- `\label`s present in HEAD and missing now: **none**, in either file. No table or
  figure lost its referencing text during the two passes.
- `\FloatBarrier` precedes every `\section` and `\subsection` from
  `\section{Results}` through the end of the Discussion: **verified, no gaps**.
- One duplicate label, `eq:hvac_degradation`, appears in both files
  (`supplementary_material.tex:461` and `paper_draft_working.tex:587`). The two are
  compiled as separate documents, so this is not an error. Informational.

## 5. Brace, environment and math-delimiter balance

| Check | `paper_draft_working.tex` | `supplementary_material.tex` |
|---|---|---|
| Brace balance (comments stripped) | 0 | 0 |
| `\begin`/`\end` pairing | balanced | balanced |
| Inline `$` parity | 1586, even | 818, even |

Two apparent delimiter mismatches were inspected and are regex artifacts, not
document defects: the `\left`/`\right` counts differ because four occurrences of
`\rightarrow` match a `\right` pattern, and the `\[`/`\]` counts differ because
nine occurrences of the table row-break `\\[2pt]`-style spacing match a `\[`
pattern. Neither file contains an unmatched display-math or `\left` delimiter.

---

# Flags for the user (not fixed, or fixed and worth reviewing)

1. **Item 16 was fixed, not just flagged.** The RAG ablation call count in the
   supplementary was a triple-count that both the pre-P0 manuscript and the P0
   pass carried. It was corrected because the P0 pass last set that value and the
   arithmetic is unambiguous, but the failure count moved from 6 to 2 as part of
   the same correction, which goes one token beyond what P0 touched. Revert both
   together if the intended unit was not one API call.

2. **Item 8 is provisional.** The sentence describing what the second author
   reviewed and when has no source in the repository. The user intends to supply
   the precise scope.

3. **The hybrid ablation and alternative-ordering arms have no retained token
   counts.** The footprint paragraph says so, but if those arms' API cost matters
   for the EMS disclosure, the diagnostics would need to be regenerated. No new
   API calls were made to fill the gap.

4. **`paper/single_criterion_recovery.tex`** (label
   `tab:single-criterion-recovery`) still exists and is still not inserted as a
   float. The P0 pass carried its numbers in prose instead. Unchanged by P1.

5. **The flipped `A_D / DeepSeek / kendall_tau` omnibus** (0.0448 $\to$ 0.0627
   under the 16-test family) remains unstated in the manuscript, as P0 recorded.
   Both omnibus claims the manuscript does make survive the larger family. No
   change was needed and none was made.
