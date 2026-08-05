# Workstream B, P0 pass: change log

Files edited: `paper/paper_draft_working.tex`, `paper/supplementary_material.tex`.
No other file was written. No git command that writes was run. Zero API calls.

Line numbers below are post-edit. Sources are abbreviated:
**RN** = `paper/REVISION_NUMBERS.md` (workstream A),
**CR** = `Analysis/consolidation_report.md` (workstream E),
**WF** = `Analysis/workstream_f_report.md` (workstream F),
**code** = read directly from the repository.

---

## Item 1 (B1). A_D failure mechanism, four sites plus a Results anchor

Source: RN section 1.2 / 1.3 (`paper/dispersion_diagnostics.csv`).

**New paragraph, line 985** (Results, Overall Ranking Accuracy). Added:

> The mechanism behind A_D's failure is not the compression toward the middle of
> the scale predicted in Section 2: A_D separates the three alternatives within a
> scenario more widely than the physics reference does, not less. Its mean
> within-scenario range of the MAVT aggregate is 0.181 for Qwen, 0.210 for
> GPT-OSS, 0.233 for Gemini, and 0.289 for DeepSeek, against 0.145 for the
> reference, a factor of 1.25 to 2.00 with a run-to-run standard deviation of
> 0.002--0.012; on HVAC energy cost the excess reaches 0.518 against the
> reference's 0.082. A_D orders the alternatives confidently and wrongly rather
> than failing to discriminate between them.

This carries the one sentence that makes the Literature Review prediction read as
falsified. Line 314 (the prediction itself) was left unchanged, per user decision.

**Line 1451** (Discussion, RAG ablation). Before: "counteracting the
central-tendency bias that otherwise collapses scores toward 0.5". After:
"pulling the within-scenario spread back toward the reference's (DeepSeek 0.289
to 0.163, Qwen 0.181 to 0.173)". Source: RN 1.3.

**Line 1453.** Before: "A_D's central-tendency bias (Section 2.2) is most
damaging...". After: "A_D's over-separation of the alternatives (Section 4.1) is
most damaging...". Cross-reference moved from `sec:mavt-design` to
`sec:res-ranking`, which is where the evidence now lives.

**Line 1465.** Before: "needs no custom code, but scores cluster near 0.5".
After: "needs no custom code, but spreads the alternatives further apart than the
physics warrants".

**Line 1473** (see Item 2).

## Item 2 (B2). Prior-work generalization

**Line 1473.** Before: "Internal consistency and ground-truth accuracy diverge
because the central-tendency bias compresses scores into a narrow middle band,
missing the sharp non-linear penalties in the value functions." After: "Internal
consistency and ground-truth accuracy diverge because A_D separates the
alternatives more sharply than the physics warrants rather than less: its
within-scenario MAVT range runs 1.25 (Qwen) to 2.00 (DeepSeek) times the
reference's, so the alternatives are confidently ordered while still missing the
sharp non-linear penalties in the value functions."
Same sentence, later: "This central-tendency pattern generalizes" became "This
miscalibration generalizes". Source: RN 1.2, 1.3.

## Item 3 (B3). Single-criterion recovery scope statement

Source: RN section 2 (`paper/single_criterion_recovery.tex`,
`paper/dispersion_diagnostics.csv`).

**New paragraph, line 1024** (Results, Baseline Comparison), quoting the Test-set
(n = 195) figures: comfort 85.7 / 92.3 / 18.3, energy cost 10.0 / 61.5 / 75.0
(HVAC / Appliance / Shower quoted where used), environmental 10.0 / 46.2 / 75.0,
practicality 27.1 / 90.8 / 20.0, chance 33.3%. Closing sentence notes the full
285-scenario corpus preserves every ordering and moves no cell by more than 6.5
points.

`paper/single_criterion_recovery.tex` (label `tab:single-criterion-recovery`) was
**not** inserted as a float; the prose carries the numbers. It is available if the
user wants the table.

## Item 4 (B4). Abstract: non-LLM baselines

**Line 255.** Added after the three architecture figures:

> Two non-LLM baselines on the same scenarios place those figures: a fixed-default
> parameter substitution into the same calculator reached tau 0.614 and 70.3%
> Top-1, and nearest-neighbour exemplar copying 0.371 and 56.9%, so only A_H beat
> both.

Source: RN 3.1 (Fixed-Default pooled Top-1 0.7026, tau 0.6137; Nearest-Neighbour
0.5692 / 0.3709). **Discrepancy with the brief:** the brief said "at tau
~0.61-0.64". The reports give Fixed-Default 0.6137 and Nearest-Neighbor 0.3709.
The reports win; 0.64 is most likely the corpus-median hybrid arm (tau 0.641),
which is a different baseline. Flagged, not silently reconciled.

## Item 5 (B5). Fixed-Default description and numbers

Source: `Miscellaneous Scripts/run_baseline_models.py` lines 46-73 and 127-205
(code), RN 3.1-3.2.

**Line 990.** Before: "substitutes fixed engineering defaults (68F setpoint for
HVAC, 7PM schedule for appliances, 8-minute shower duration) into the same
physics calculators". After: "ranks the same three alternatives as every other
system, but substitutes one fixed value for each withheld engineering parameter
before calling the same physics calculators used by the ground truth: R-value 15,
SEER 13, and HVAC age 13 years for HVAC; a per-appliance-type kWh/cycle (0.55
washer, 2.10 dryer, 1.00 dishwasher) and a 7 p.m. baseline run time for Appliance;
and 2.5 GPM, a 50-gallon tank, and a 120F heater setpoint for Shower. It performs
no per-scenario inference, so it isolates what calculator access buys with no
estimation at all."

**Line 1020.** Before: "(the 68F setpoint is near-optimal...)" and "(because the
8-minute/2.5-GPM default is near-optimal...)". After: "(the R-15/SEER-13 defaults
are close to the corpus centre...)" and "(the 2.5-GPM, 50-gallon, 120F defaults
are near-optimal...)".

**Table `tab:incremental-contribution`.** FixedDefault Top-1 0.7282 -> **0.7026**.
NearestNeighbor Top-1 delta -0.1590 -> **-0.1334**. Kendall tau 0.6137 unchanged,
per RN 3.2. The six LLM Top-1 delta cells were recomputed against the new
reference point (they are hand-computed in the .tex, not in `numbers_master.csv`):
-0.357 -> -0.332, -0.428 -> -0.402, -0.176 -> -0.150, -0.257 -> -0.231,
+0.200 -> +0.226, +0.169 -> +0.195. All tau deltas unchanged.

## Item 6 (B6). Denominators (PROTECTED SECTION)

Source: brief; consistent with the 105 / 100 / 80 corpus sizes.

**Line 414** (Methodology 2.2). Before: "The mean within-scenario Spearman
correlation between raw cost and raw emissions is 0.61, and the two are exactly
collinear in only 22% of Appliance scenarios." After: "The within-scenario
Spearman correlation between raw cost and raw emissions is defined in 50 of the
100 Appliance scenarios (in the other 50 at least one of the two quantities is
constant across the three alternatives, so rho is undefined); over those 50 it
averages 0.610, and 11 of them exceed 0.999."

**Line 416** (Methodology 2.2). Before: "The within-scenario Spearman correlation
is 1.000 for all 101 HVAC and all 80 Shower scenarios". After: "The
within-scenario Spearman correlation is 1.000 for 101 of the 105 HVAC scenarios
(the four exceptions have a constant raw cost across the three alternatives, so
rho is undefined) and for all 80 Shower scenarios".

Nothing else in that paragraph or section was touched.

## Item 7 (B7). AI disclosure

**Line 1551.** `[TODO: NAME OF TOOL/SERVICE]` / `[TODO: REASON]` replaced with a
factual disclosure naming Anthropic's Claude via the Claude Code CLI and its three
roles (drafting/copy-editing, writing and debugging the analysis and
figure-generation scripts, cross-checking reported values against result files),
plus one sentence stating nothing was accepted without verification against
primary data. The Elsevier boilerplate sentence that follows is unchanged.

## Item 8 (B8). Author TODO comments (PROTECTED SECTION)

**Deleted** the `% TODO:` comment that sat between the swing-weights table and the
weight-configuration paragraph (was line 433), and the `%todo:` comment between
the Energy Cost and Comfort weight paragraphs (was line 463). Both were LaTeX
comments, so neither appeared in the compiled PDF.

The substantive point in the first TODO was folded into the A_D architecture
description (**line 725**, outside the protected range), which already contrasts
what A_D and A_E receive:

> Neither prompt states any Pennsylvania-specific quantity: A_D is given the
> location and must supply the PECO time-of-use tiers and the PJM marginal
> emissions factors from its own knowledge, whereas A_E's retrieved exemplar is a
> worked Pennsylvania case with reference scores attached. Part of the A_D--A_E
> gap is therefore access to locale-specific values rather than scoring ability
> alone.

Placed there rather than at line 433 because the surrounding protected text is
about criterion weights, not prompt content.

The second TODO was a note-to-self asking for an external critique of the
Methodology justifications. It carries no factual content, so it was deleted
outright.

## Item 9 (B9). Model IDs

Source: `model_config.py` lines 26-48 (code).

**Line 707.** Four `\texttt{}` identifiers gained the `:exacto` suffix. Added one
sentence: "The `:exacto` suffix is an OpenRouter provider-routing variant that
restricts serving to providers meeting a fixed accuracy standard; it is part of
the model identifier and is required to reproduce these runs."

## Item 10 (B21). Gemini no longer excluded from ablations

Source: CR sections 1, 3, 5; `Analysis/Prompt_Ablation/prompt_ablation_summary.xlsx`.

**Line 758.** "Each configuration is evaluated across three models" -> "four models".

**Line 762.** Before: "All ablations run DeepSeek, GPT-OSS, and Qwen; Gemini is
excluded from the ablation matrix because its output pricing is roughly fifty
times that of the other models." After: "All ablations run all four models.
Gemini's prompt-ablation cells use three runs against the five or ten the other
three models use, because its output pricing is roughly fifty times theirs; the
significance tests are over n = 195 scenarios rather than over runs, and Gemini's
run-to-run standard deviation of 0.008--0.021 is the lowest of the four models, so
three runs resolve its cell means at the precision reported."

**Line 764.** "across three models with five runs per cell" -> "across four
models"; "the resulting matrix has 105 cells rather than 120" -> "28
architecture--model--variant cells rather than 32".

**Line 772.** "ten repetitions instead of five for every model" -> "for DeepSeek,
GPT-OSS, and Qwen ... ; Gemini runs three repetitions on every variant."

**Line 1272** (Results). "across three models and five runs each" -> "across four
models"; "The full matrix comprises 105 cells and 20,475 scenario-level
observations" -> "28 architecture--model--variant cells, 156 runs, and 30,420
scenario-level observations". The old 105 / 20,475 pair assumed five runs in every
cell and was already inconsistent with the ten-run no_anchors arms; the new figures
are the sum of `n_runs` in `prompt_ablation_summary.xlsx` (156) times 195.

**Table 11 (`tab:prompt_ablation`).** Four Gemini rows added (two tau, two Top-1),
inserted after DeepSeek in each block. Values from
`prompt_ablation_summary.xlsx`: A_D tau 0.188 / 0.126 / 0.212 / 0.178, A_E tau
0.325 / --- / 0.245 / 0.250, A_D Top-1 0.352 / 0.361 / 0.368 / 0.350, A_E Top-1
0.477 / --- / 0.410 / 0.416. Bold follows the existing convention (A_E rows only).
The caption claim that every A_E configuration stays above every A_D configuration
within a model holds for Gemini (0.245 against 0.212), per CR section 5.

**Table 11 tablenote.** Added: "Gemini cells use three runs; the significance
tests below are over n = 195 scenarios rather than over runs, and Gemini's
run-to-run standard deviation is 0.008--0.021, the lowest of the four models, so
three runs resolve its cell means to the precision reported here."

**Line 1487** (Limitations). "across three controlled perturbations, three models,
and five runs each" -> "four models, and three to ten runs each"; "The ablation
excluded Gemini for cost reasons, and it never perturbed..." -> "The ablation
never perturbed...".
Same paragraph: "Extending the prompt-variant robustness check to A_H and to
Gemini" -> "to A_H".

**Line 1521** (Future Work). "to A_H's extraction prompt and to Gemini" -> "to
A_H's extraction prompt".

**RAG figure (`\plotRagAblation`, preamble).** A fourth pgfplots series was added
for Gemini (0.437 / 0.387 / 0.517 / 0.377 / 0.431 / 0.177 / 0.204), legend updated
to four entries and `legend columns` from 3 to 4. Values from
`rag_ablation_bootstrap_ci.xlsx`, matching CR 2.3.

**Supplementary, RAG table note.** "with 3 models; Gemini is excluded on cost
grounds" -> "with all four models".

## Item 11 (B23). Every RAG number moves to per-model

Source: CR sections 2.1-2.4; `Analysis/RAG_Ablation/rag_ablation_bootstrap_ci.xlsx`.

**Line 760** (Methods). Before: "A Friedman test is run per metric ... across all
seven configurations pooled over models, giving a four-test family". After: "A
Friedman test is run per metric ... across the seven LLM configurations within
each model, giving a sixteen-test family of four models by four metrics; the
offline nearest-neighbor baseline has no per-model arm and so enters the
descriptive bootstrap rather than any omnibus." Also "in two of the three models
tested" -> "in three of the four models tested".

**Line 1266** (Results, RAG Ablation). Rewritten. Pooled taus 0.277 / 0.068 /
0.279 / 0.121 removed. Replaced with per-model values (control 0.489 / 0.387 /
0.187 / 0.154; descriptions-without-scores 0.073 / 0.204 / 0.061 / 0.071;
exemplars-without-hidden-params 0.391 / 0.437 / 0.175 / 0.273), per-model MAE
ranges (top cluster 0.069--0.118; descriptions 0.131--0.158; random 0.127--0.163),
and per-model k1-vs-k3 CIs. See also Items 13, 14, 16.

**Line 1451** (Discussion). Pooled "random exemplars yield tau = 0.121" replaced
with per-model values. See Items 13, 14.

**Supplementary `app:rag_ablation_full` table.** The whole table was rebuilt. The
"Overall tau / 95% CI / Model tau range / Overall MAE" columns (the withdrawn
pooled estimates, exactly 0.279 / 0.277 / 0.246 / 0.242 / 0.230 / 0.121 / 0.068)
were replaced by two stacked per-model panels, one for Kendall's tau and one for
MAE, with four model columns and a separate offline nearest-neighbor row. The note
now says the pooled estimates are withdrawn and why, points to
`rag_ablation_bootstrap_ci.xlsx` for the per-model intervals, and updates the call
count from "17,010 scoring calls with 6 failures (0.04%)" to "22,680 scoring calls
with 6 failures (0.03%)" (recomputed from `rag_ablation_results.xlsx`: 4 models x
5,670 calls, 6 failures all on DeepSeek).

## Item 12 (B24). Prompt-ablation family size and the flipped omnibus

Source: CR section 3; `Analysis/Prompt_Ablation/prompt_ablation_friedman_tests.xlsx`.

**Line 770.** Before: "Up to six strata (three models x two architectures, minus
the A_E/no_anchors cells that do not exist) are each tested on two metrics, giving
up to twelve Holm-corrected Friedman omnibus tests". After: "Eight strata (four
models x two architectures, with the A_E strata comparing three variants because
the A_E/no_anchors cells do not exist) are each tested on two metrics, giving
sixteen Holm-corrected Friedman omnibus tests".

**Supplementary `tab:prompt_friedman`.** Caption "full 12-test family (both
architectures, all three models, both metrics)" -> "full 16-test family (both
architectures, all four models, both metrics)". Two Gemini rows added (tau 3.31,
p 0.192, p_Holm 0.766; Top-1 9.08, p 0.011, p_Holm 0.117). Every existing
p_Holm updated for the larger family: DeepSeek tau 0.922 -> 0.939, GPT-OSS tau
0.922 -> 1.000, Qwen tau 0.460 -> 0.575, DeepSeek Top-1 2.1e-7 -> 2.8e-7, Qwen
Top-1 0.065 -> 0.086. The note's worked example ("DeepSeek and GPT-OSS Kendall's
tau therefore share the adjusted value 0.922") was dropped, since they no longer
share a value; the monotonicity explanation itself was kept. "12-test family" ->
"16-test family" in the note.

**On the flipped omnibus (`A_D / DeepSeek / kendall_tau`, 0.0448 -> 0.0627):** the
manuscript never states this omnibus. The supplementary Friedman table reports A_E
strata only, and the main-text prose at line 1314 refers to post-hoc pairwise
comparisons, not to that omnibus. The two omnibus claims the manuscript does make at line 1318
("the Friedman omnibus on Kendall's tau is not significant for any A_E model" and
"the Top-1 omnibus is significant for DeepSeek") both survive the 16-test family.
No sentence needed changing. Flagged for the user in case a statement is wanted.

## Item 13 (B26). The top-cluster claim

Source: CR section 2.4.

**Line 1266.** "pairwise p_Holm > 0.62" removed. Replaced with: "Only DeepSeek and
Gemini carry a Kendall's tau omnibus that survives the 16-test Friedman family, and
within those two the top cluster separates for DeepSeek alone: its k=1 arm scores
below the k=3 control at p_Holm = 0.003 (Cliff's delta = 0.247, small), whereas
Gemini's six top-cluster pairs all sit at p_Holm >= 0.35."

**Line 1451.** "while retrieval architecture and exemplar content contribute
negligibly (top-cluster pairwise p_Holm > 0.62)" removed. Replaced with: "Retrieval
depth is undetectable for Gemini and untestable for GPT-OSS and Qwen, whose tau
omnibus does not survive correction, while for DeepSeek k=1 scores significantly
below k=3 (p_Holm = 0.003, Cliff's delta = 0.247, small)."

## Item 14 (B28). The Qwen reversal

Source: CR section 2.3.

**Line 1451.** Before: "Semantic selection of exemplars drives the RAG contribution
(random exemplars yield tau = 0.121)". After: "Semantic selection of exemplars
drives the RAG contribution for three of the four models (random exemplars yield
tau = 0.063 for DeepSeek, 0.177 for Gemini, and 0.022 for GPT-OSS, against control
values of 0.489, 0.387, and 0.187) and reverses for Qwen, whose random-exemplar
tau of 0.276 sits above its own control at 0.154." The claim is qualified per
model, not deleted.

## Item 15 (B32). Hybrid ablation family size

Source: WF section F1.

**Line 1157** (Results). "across the nine-test family" -> "across the twelve-test
family". The quoted chi2 range 52.5 to 305.3 and the p_Holm < 1e-11 bound both
still hold with Gemini's three rows included (WF F1 table).

**Line 778** (Methods). "Three models times three metrics ... gives nine
Holm-corrected Friedman omnibus tests" -> "Four models times three metrics ...
gives twelve".

## Item 16 (B31). Bootstrap bounds

Source: WF section F2.

**Line 1264.** `nearest_neighbor_k3` tau CI [-0.175, 0.172] -> **[-0.173, 0.175]**
(exact: [-0.1725, 0.1753]); point estimate 0.001 unchanged. Same interval used in
the rebuilt supplementary RAG table.

**Line 730** (A_E methods). Before: "no retrieval count differed detectably at the
power available, with a percentile bootstrap 95% CI on the pooled k=1 minus k=3
Kendall's tau difference of [-0.144, 0.063] containing zero, although DeepSeek's
... CI [-0.471, -0.159]". After: "no retrieval count differed detectably at the
power available in three of the four models, whose percentile bootstrap 95% CIs on
the k=1 minus k=3 Kendall's tau difference all contain zero (Gemini [-0.163,
0.142], GPT-OSS [-0.128, 0.228], Qwen [-0.047, 0.326]), although DeepSeek's k=1
mean tau sits 0.316 below its k=3 mean with CI [-0.471, -0.161]".

**Line 1266.** Same four per-model intervals plus the pooled diagnostic
[-0.120, 0.052] (was [-0.144, 0.063]). The pooled interval is still cited, and
still labelled as pooled, because the sentence's argument is that pooling conceals
the DeepSeek reversal.

## Item 17 (F4). Supplementary imputed-robustness table

Source: WF section F4.

**`tab:imputed_comparison` caption.** "Values are means across all four models."
-> "A_D and A_E values are means across all four models; A_H is broken out per
model, because imputation moves one model there and leaves the other three
unchanged."

**Table body.** The three pooled A_H rows (tau 0.899 -> 0.871, MAE 0.055 -> 0.061,
Top-1 91.3 -> 89.2) were replaced by four per-model blocks: DeepSeek
0.897/0.897, 0.047/0.047, 90.8/90.7; Gemini 0.923/0.923, 0.048/0.048, 93.1/93.1;
GPT-OSS 0.897/**0.786**, 0.052/**0.078**, 91.6/**83.6**; Qwen 0.880/0.877,
0.072/0.073, 89.7/89.5. The A_D and A_E rows stay pooled and are relabelled
"(4-model mean)". A tablenote explains the bolding and why A_D and A_E stay pooled.

**Prose (line 948).** Rewritten along WF F4's suggested wording: imputation lowers
A_H on GPT-OSS alone; DeepSeek, Gemini and Qwen move by 0.0006, 0.0000 and 0.0032
on tau; the pooled fall from 0.899 to 0.871 is stated as an average no individual
model exhibits and explicitly not A_H's failure-inclusive accuracy. The claim that
the A_H > A_E > A_D ordering holds for all four models under imputation was kept,
as instructed.

---

## Verification

Both files compile cleanly under a local `pdflatex -halt-on-error -draftmode` run
(exit 0, no errors). This was a syntax check only; the Overleaf build remains the
source of truth.
