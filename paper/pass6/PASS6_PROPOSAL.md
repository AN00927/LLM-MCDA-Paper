> **READ FIRST (added 2026-09-26).** This is the working copy of `paper/pass5/PASS5_PROPOSAL.md`,
> which stays frozen as the original. The entry point is **`paper/pass6/PASS6_HANDOFF.md`**. Its
> item status table (Section 5) decides what happens to every item below: apply as written,
> apply adapted, rewrite as a description of the new calculator, move after the rerun, or drop.
> **Where this file and the handoff disagree, the handoff wins.** Line numbers below refer to
> the paper as of 2026-09-25. Re-check every quoted old string before editing
> (`Analysis/pass5/audit_old_strings.py`).

# Pass 5 proposal

Assembled 2026-09-25 from an overnight run of offline analyses. **Nothing in the manuscript
(`paper/paper_draft_v2.tex`), supplement (`paper/supplementary.tex`), bibliography
(`paper/cas-refs.bib`), README, `CLAUDE.md`, `requirements.txt` or any code was edited.** Every
change below is a proposal written as old -> new. Each "old" string is copied from the current
file so a text search finds it, and line numbers are current as of today. A snapshot of the
four files as they stood before this pass is in
`C:\Users\Ahaan\LLM-MCDA-Paper-snapshots\2026-09-25_pass5\`. No API calls were made and nothing
was rerun.

The file has four parts:
- **Part A** (items A1–A12): the big items. They change what the paper claims, and each needs
  your decision.
- **Part B** (items B1–B78): the cheap-fix batch. Most are one-token or one-clause fixes you can
  approve or strike item by item.
- **Not proposed, and why:** the things this pass deliberately left alone.
- **Your actions:** what only you can do.

Part A and Part B each begin with their own orientation, glossary and summary table.

Short names used in this header: A_D is direct LLM scoring, A_E is example-guided LLM scoring
and A_H is LLM-parameterized reference scoring. Kendall's tau is the rank correlation between an
architecture's ranking of a scenario's three alternatives and the reference ranking. The
dataset-median baseline feeds the reference calculators each withheld parameter's median over
the scenario sheet, with no LLM. Part A's "Terms used throughout" gives the full definitions.

## What changed overnight, in four sentences

1. The supplement reports LLM-parameterized reference scoring (A_H: the LLM extracts engineering
   parameters and the reference calculators score) with a different estimator from the main
   text. Its provenance table, its "194 of 195" and its significance tests describe a five-run
   parameter ensemble, not the benchmarked system. The main-text A_H numbers are correct
   (item A1).
2. A rule-based reader with no LLM fills the calculators' inputs from the scenario labels and
   the question text. It ranks as well as A_H on every decision type: overall Kendall's tau
   0.925 against A_H's 0.880–0.923. For every model, A_H's gain over it lies between −0.045
   and −0.001 and is never significantly positive. The paper can therefore not credit the LLM
   with A_H's accuracy (item A2).
3. The paper explains shower flow-rate (GPM) errors wrongly: a GPM error scales every duration's
   cost and water by the same factor. What it changes is how those two criteria weigh against
   comfort, and the winner flips when its lead is narrow (item A3).
4. "LLMs should not score" is broader than the one design tested: one call per alternative,
   low reasoning effort, no value functions in the prompt (item A4).

## Summary table

| Item | Problem | Recommendation | Needs your judgment? |
|---|---|---|---|
| A1 | Supplement's A_H provenance numbers, "194 of 195" and tests use a five-run ensemble. The main text's "0.24–0.28" was measured against the dataset-median baseline over mixed scenario sets. | Switch to per-run numbers; the tau gain becomes 0.24–0.30. | Low: token swaps |
| A2 | A no-LLM label-lookup baseline matches A_H on every decision type. | Add the baseline to the paper and rescope every "extraction adds" claim. | **Yes**: central claim |
| A3 | The GPM mechanism clause contradicts the calculator code. | Replace the clause (main text and README); report the extraction-accuracy table per run. | Yes: thesis wording |
| A4 | "Should not score" exceeds the tested design; three prompt facts are undisclosed. | Scope the claim, add the disclosures, and give the no-anchors ablation by decision type. | **Yes** |
| A5 | The abstract says "physics-based" and "any domain", and omits the scope and the boundary result. | Choose one of two drafted abstracts (147 and 145 words; limit 150); choose a title. | **Yes**: choice |
| A6 | Ranking alternatives in their listed order, with no model, beats every A_D and A_E cell. | Disclose it in the supplement plus one main-text sentence. | Yes |
| A7 | The self-consistency clause is unsupported; regret and tokens are unreported. | Delete the clause; add the optional tables. | Low |
| A8 | "Single correct value" is falsified by the LLM-to-solver literature. | Replace the clause; add Jakeman 2006 and Bennett 2013; eight verified BibTeX entries. | Low |
| A9 | README and the availability statement promise raw logs and UTC timestamps the runs lack. | Correct both; state collection windows in the supplement. | Low |
| A10 | The Appliance calculator omits the super off-peak period (4 of 65 winners). | Disclose it; no rerun. | Low |
| A11 | Text blames PJM factors for the cost/emissions collapse; the small Environmental Impact swing is unreported. | Fix the wording; state the swing once as a finding. | Yes: framing |
| A12 | Discussion 6.1 restates Results and holds sentences A1–A4 change. | Defer the rewrite until A1–A4 are decided. | — |
| B1–B14 | Number mismatches from the simulated panel's consistency audit. | Fix each. | B2, B10, B11 |
| B15–B25 | The panel's cheap-fix list. | Fix each. | B16, B17, B18, B20 |
| B26–B55 | Calculator-audit text fixes: wrong attributions, undisclosed assumptions, pooled ranges. | Fix in text; no calculator changes. | B32, B39 |
| B56–B61 | Supplement: wrong rate, dangling pointer, tau without tie-break, warnings. | Fix each. | B60 |
| B62–B67 | Submission hygiene: TODOs, citation style, caption source, bib warnings. | Fix each. | B63 |
| B68–B78 | Repository: README, `requirements.txt`, code comments, `CLAUDE.md`, `PAPER_STATUS.md`. | Fix each. | B74, B77 |

**Suggested order:**
1. Decide A1–A4.
2. Choose the abstract and title (A5).
3. Approve or strike A6–A11 and the Part B items.
4. The approved edits then go in as one minimal-diff pass.
5. Discussion 6.1 (A12) comes last.

## Cross-part notes

- **B60 extends A4.** Both ablation suites (prompt and retrieval) compute Kendall's tau on the
  raw scores without the tie-break the main benchmark uses. This affects 4–12% of scenario-runs
  per prompt-ablation cell. It is a third way the ablation control differs from the main
  benchmark, alongside the 10 runs (3 for Gemini) and the older Shower reference. A4's
  supplement note (A4.8) already names all three reasons for the prompt-ablation control; B60
  adds one sentence at S L930 that extends the tie-break point to the retrieval (RAG) ablation.
  The two sentences sit in different paragraphs and do not conflict; take both or neither.
  A4.6's main-text clause points to the supplement and needs no change.
- **A2 has a caveat you must weigh.** The lookup baseline's parsers were written after reading
  the question templates, and its insulation R-values are the midpoints of the tier ranges that
  generated the data. The result shows that this benchmark cannot separate the LLM from a rule
  reader, not that LLMs add nothing on free text. Two versions don't depend on the hand-written
  occupancy parser:
  - the time-only version: tau 0.901;
  - the lookup without the occupancy parser: tau 0.921.

  Without the tier-midpoint rule, lookup HVAC tau falls to 0.933, still within A_H's range.
- **Sentences edited by several items** are listed in Part A's table "Sentences edited by more
  than one item". Apply the combined edit given there, never two edits one after the other.
- **Supporting reports** are in `paper/pass5/`: `D2_REPORT.md`, `D1_REPORT.md`, `D3_REPORT.md`,
  `D9_D12_REPORT.md` and `D13_REPORT.md`. The scripts and CSVs behind every number are in
  `Analysis/pass5/`. You don't need any of them to decide an item: each item below states its
  evidence.
- **Numbers of record.** `paper/pass5/NUMBERS_OF_RECORD.csv` maps each A_H, baseline and
  provenance number in the paper to the output file, column and script it comes from, and gives
  its status (verified or mismatch). Four more files beside it hold the rows each analysis
  added. Every number is computed per model and per run, then averaged over runs; none is
  pooled across models.

---

# Pass 5 proposal, Part A: the big items

Date: 2026-09-25. Nothing in the paper, supplement, bib, README or code was edited. Every change below is a proposal written as old -> new, with the old string copied from the current file so you can find it by search. Line numbers are current as of today: "main" is `paper/paper_draft_v2.tex`, "S" is `paper/supplementary.tex`, "README" is `README.md`. Part B (later in this file) covers the cheap review fixes, calculator-audit wording, README/requirements/code comments and supplement cosmetics; where one of my edits touches a sentence Part B may also edit, I say so.

## Orientation

The analyses of existing data run for this pass, all offline with no API calls, changed four things the manuscript claims. (1) The supplement reports LLM-parameterized reference scoring on a different estimator from the main text, so its table, its "194 of 195" and its significance tests describe a five-call ensemble, not the benchmarked system. (2) A rule-based reader that fills the calculator's inputs from the scenario labels and question text, with no LLM, ranks as well as that architecture on every decision type, so the paper cannot say the LLM supplies the accuracy. (3) The paper's explanation of why shower flow-rate errors flip the recommendation contradicts the calculator's code. (4) The "LLMs should not score" conclusion is broader than the one scoring design tested. The items below turn those findings into edits. Decide A1-A4 first: A5 (abstract and title) and A12 (Discussion rewrite) depend on them.

### Terms used throughout

- **A_D, direct LLM scoring** (`Architectures/Direct_LLM_Scoring.py`): the LLM scores each alternative on the four criteria (Energy Cost, Environmental Impact, Comfort, Practicality, weights 0.30/0.35/0.20/0.15), one API call per alternative, three per scenario; the weighted sum ranks them.
- **A_E, example-guided LLM scoring** (`Architectures/Example-Guided_LLM_Scoring.py`): as A_D, plus a retrieved, reference-scored exemplar scenario in the prompt.
- **A_H, LLM-parameterized reference scoring** (`Architectures/LLM-Parameterized_Reference_Scoring.py`): one LLM call per scenario returns the withheld engineering parameters (HVAC: R-value, SEER, HVAC age, occupancy context; Appliance: appliance type, kWh per cycle, baseline run time; Shower: GPM, tank size, heater setpoint); the deterministic reference calculators score the three alternatives from them.
- **Reference**: the MAVT (multi-attribute value theory: per-criterion value functions combined by the weighted sum) ranking the three calculators produce from each scenario's true engineering values.
- **Kendall's tau**: per-scenario rank correlation between an architecture's ranking of the three alternatives and the reference ranking, averaged over scenarios. **Top-1**: share of scenarios whose top-ranked alternative is the reference winner.
- **Numbers of record**: each metric computed per run over the scenarios that run scored, then averaged over the five runs per model (`paper/per_run_metrics/per_run_metrics_all.csv`). This is the main text's basis. Nothing below is pooled across models.
- **Sentinel 1928**: the value the pipeline writes for a failed scenario; failed scenario-runs are excluded run by run.
- **Fixed default (FD)**: a non-LLM baseline that feeds the calculators one fixed engineering value per withheld parameter (R-15, SEER 13, HVAC age 13, occupied all day; kWh/cycle 0.55 washer, 2.10 dryer, 1.00 dishwasher; baseline time 7 p.m.; 2.5 GPM, 50 gal, 120 F). Tau 0.933 HVAC / 0.097 Appliance / 0.800 Shower / 0.614 overall.
- **Dataset median (DM)**: a non-LLM condition that feeds the calculators the median (numeric) or mode (categorical) of each withheld parameter over the decision type's scenario master sheet. Tau 0.641, Top-1 76.9%, identical for every model.
- **Label-lookup baseline (LU)**: a new non-LLM baseline, built for this pass, that reads only what A_H's LLM reads and fills each withheld parameter by fixed rules: insulation tier -> R-value tier midpoint (Poor 10, Medium 15.5, Good 21.5); house-age band midpoint -> HVAC age, and SEER = the federal minimum at that installation year; flow-rate band midpoint -> GPM (1.5 / 2.5 / 4.0); a keyword parser for occupancy; a clock-time parser for the Appliance baseline time; every other parameter keeps its FD value. **FD+time** is FD with only the parsed baseline time added.
- **Like-for-like**: both conditions measured on the same scenarios, run by run, then averaged over runs. It matters only for GPT-OSS, whose A_H lost 117 of 975 scenario-runs, all HVAC.
- **GPM**: shower flow rate in gallons per minute. The LLMs see only a three-tier flow-rate label; the Shower calculator uses the true GPM.
- **Test set and RAG set**: the 195 benchmark scenarios (70 HVAC, 65 Appliance, 60 Shower) and the disjoint 90-scenario retrieval corpus (35 / 35 / 20) from which A_E draws its exemplar; 285 scenarios together. "Retrieval scenarios" means the RAG set.
- **main / S / README with a line number**: `paper/paper_draft_v2.tex`, `paper/supplementary.tex` and `README.md`. **S1 and S2** are the supplement's two sections (S1 "Extended Methods", from S L198: prompts, scenario fields, rates; S2 "Extended Results and Robustness", from S L768: ablations and statistics).
- **Simulated panel, "the editor", "Reviewer 1-4"**: the simulated EMS peer review of the current draft, run on 2026-09-24 (`paper/MOCK_EMS_REVIEW.md`). It had a handling editor and four reviewers: Reviewer 1 (environmental modelling and MCDA), Reviewer 2 (LLM and ML evaluation), Reviewer 3 (reproducibility and software) and Reviewer 4 (devil's advocate). All five returned Major Revision. Each item below states the point it raised; the file is further reading only.

### Summary

| Item | Problem in one line | Recommendation | Effort | Depends on |
|---|---|---|---|---|
| A1 | The supplement's A_H provenance table, "194 of 195", its tests and the main text's "0.24-0.28" rest on a five-run parameter ensemble or mixed scenario sets | Replace with per-run numbers (tau gain 0.24-0.30); fix L889, L909 | Small (token swaps) | none |
| A2 | A no-LLM label-lookup baseline matches A_H on every decision type | Add two table rows, one Methods sentence, one Results paragraph, one S2 subsection; rescope L808, L1048, L1071, L1112; fix L1083, L945 | Medium | A1 (shares L808) |
| A3 | "GPM multiplies against each alternative's own duration" is wrong; the GPM flip probabilities are on the ensemble basis | Replace the mechanism clause (L1057, README L144/L149); move Table 6 to per-run values | Small-medium | none |
| A4 | "LLMs should not score" exceeds the tested design; three prompt facts undisclosed; no-anchors effect hidden by averaging | Scope L1112 and the abstract; add three disclosures; add a by-type sentence and S2 table; label the ablation control | Medium | A5 (abstract) |
| A5 | Abstract says "physics-based", "in any domain with a validated modeling calculator", omits scope and the fixed-default/lookup boundary | Choose one of two drafted abstracts (147 and 145 words); four word-level scope swaps in the body; title choice | Medium (decision) | A1-A4 |
| A6 | Listing the alternatives in sheet order, with no model, beats every A_D and A_E cell; ties break by that order | Disclose in S1 with a top-tie table; one sentence in main Section 5.1 | Small | none |
| A7 | L404 motivates ensembling that the data do not support; regret and token split unreported | Delete the L404 clause; add a regret sentence; S2/S1 tables; flag the DeepSeek A_D token anomaly | Small | none |
| A8 | L320's "single correct value" is falsified by LLM+P and NL4Opt; no EMS evaluation references | Replace the L320 clause; add Jakeman 2006 / Bennett 2013 at L476; six BibTeX entries plus two | Small | none |
| A9 | README and availability statement promise raw logs and UTC timestamps the benchmark runs lack | Correct README L73 and main L1136; state commit-dated collection windows in S1 | Small | A1 (regeneration caveat) |
| A10 | The Appliance calculator omits the super off-peak period of PECO and FirstEnergy | Option A: disclose with the 4-of-65 sensitivity; no rerun | Small | B40 (rewords the L726 sentence A10.1 follows) |
| A11 | Text blames PJM for the Shower (and HVAC) cost/emissions collapse; the small Environmental Impact swing is unreported | Fix L614 and L1094; state the swing once; caption the swing table as test + retrieval pooled | Small | none |
| A12 | Discussion 6.1 restates Results and holds sentences A1-A4 change | Defer the rewrite until A1-A4 are decided | none now | A1-A4 |

### Sentences edited by more than one item

| Location | Items | Where the combined edit lives |
|---|---|---|
| main L304 (abstract) | A2, A4, A5 | A5 (the two abstract drafts include A2's and A4's content) |
| main L808, effect-size sentence | A1, A2 | A1 edit A1.6 gives the A1-only and the combined text |
| main L775, last sentence | A2, A6 | A2 edit A2.3 (the A6 sentence is an optional addition after it) |
| main L945 paragraph | A2, A3 | Separate sentences; both edits listed in A3 edit A3.4 and A2 edit A2.10 |
| main L1083, occupancy percentages and "the one parameter" | A2, A3 | A2 edit A2.9 gives the combined sentence |
| main L1112 (Conclusion paragraph) | A2, A4 | Separate sentences in one paragraph; both shown together in A2 edit A2.8 |
| main L1048 third point | A2 and Part B's B16 ("comes close" -> "matches or beats") | A2 edit A2.7 includes B16's swap; if you accept A2, apply A2.7 and skip B16 |
| README L148 | A1, A2 | A2 edit A2.12 |
| S L779, swing-table caption | A11.4 and Part B's B55 | Both give the same new caption ("... over the 285 test and RAG scenarios"); apply it once |

Items that edit different sentences of the same paragraph (checked: their old strings do not overlap, and applying one leaves the other's old string intact): main L328 (A5 scope swap, B18); L726 (A10.1 insertion after the "weekday summer rates" sentence, which B40 rewords; B36, B38, B41); L740 (A4.9, B15); L837 (A6.4, A7.3 insertion, B18); L998 (A4.6, B3); L1083 (A2.9, B19); S L201 (B24 prepends a sampling sentence before "We report API costs ...", B61 changes the model identifiers, and A9.3 inserts after that sentence; A7.6 may go there too or near the failure-mode table, and if both go there, put A9.3's sentences first); S L765 (B38, B39, then A10.2's new paragraph after the paragraph); S L930 (B2, B60).

---

## A1. The two sets of A_H numbers

### Problem

The manuscript reports two sets of A_H results that come from different estimators.

- **Set A (main text, correct)**: each of the five runs is scored separately, failed scenarios are dropped from that run, and the five run metrics are averaged. Tau 0.923 / 0.897 / 0.897 / 0.880 (Gemini / DeepSeek / GPT-OSS / Qwen); GPT-OSS success rate 88.0%.
- **Set B (supplement parameter-provenance table)**: for each scenario, the extracted parameters are averaged over the runs in which it succeeded (numeric by mean, categorical by mode) and the consensus is scored once. Tau 0.921 / 0.904 / 0.921 / 0.897. Any scenario with one successful run counts as scored, which produces GPT-OSS's "194 of 195". A_H as benchmarked makes one extraction call per scenario, so Set B describes a five-call ensemble.

Set B enters the text in four places:

1. The provenance table, S L1305-L1322. Caption: `\caption{Ranking accuracy of $\mathcal{A}_{\text{H}}$ with LLM-extracted and dataset-median hidden parameters. Significance testing on these conditions follows.}` Rows, for example L1312: `GPT-OSS & LLM-extracted & 0.921 & 0.943 & 0.046 \\`.
2. S L1328: "the extracted condition scored 194 of 195 scenarios for GPT-OSS and 195 for the other three models."
3. The provenance significance tests, S L1330-L1332 and the parenthetical at main L808 ("Cliff's $\delta$ from $-0.14$ to $-0.24$ on Kendall's $\tau$ and Top-1 and from 0.35 to 0.49 on MAE"). They were run on Set B.
4. Main L808: "Extraction therefore adds 0.24--0.28 in $\tau$ beyond what the calculator provides." No script computes this. It is Set A's range minus DM's tau over all 195 scenarios (0.880 - 0.641, 0.923 - 0.641). For GPT-OSS that subtracts a 195-scenario DM value from an A_H value that excludes 117 HVAC scenario-runs, where DM scores high. Like-for-like, GPT-OSS's gain is 0.300, so the range is 0.24-0.30. On Set B it would be 0.26-0.28. The published range matches neither.

Three related sentences are also wrong:

- Main L909: "GPT-OSS accounts for 117 of the 120 $\mathcal{A}_{\text{H}}$ failures, most of them on HVAC scenarios". All 117 are HVAC (S L704 already says "All of its $\mathcal{A}_{\text{H}}$ failures were HVAC scenarios").
- Main L909: "When we recover each failed scenario from a run in which it succeeded, the reported figures do not change ($\tau$ 0.897, Top-1 91.7\%)." No code performs the recovery; 0.897 / 91.7% are the unrecovered values. Backfilling each failed scenario-run from another run where it succeeded gives tau 0.904 and Top-1 92.0%.
- Main L889: "lowers its success-weighted $\tau$ from 0.897 to 0.790 and its Top-1 from 91.7\% to 84.7\%." The tau is success-weighted (0.88 x 0.897). The 84.7% scores each failed scenario at the chance value 1/3 (the "inclusive" row of S Table `tab:overall_by_model`); strictly success-weighted Top-1 would be 80.7%.

### Why an EMS reviewer cares

The simulated panel listed this as a consistency failure that needed resolving "before anything else is interpreted": the tests at L808 use one estimator and the effect size another. A reviewer who recomputes any cell finds the mismatch.

### Evidence

Source: `paper/pass5/D2_REPORT.md`; script `Analysis/pass5/d2_reproduce_ah_numbers.py`; outputs `Analysis/pass5/d2_*.csv`. Both sets reproduce exactly from the stored per-run files. Set B's consensus parameters match the aggregate workbook to 7e-15.

Like-for-like tau gain of A_H over DM (`d2_effect_like_for_like.csv`):

| Model | Overall | HVAC | Appliance | Shower | Top-1 gain (pp) |
|---|---|---|---|---|---|
| DeepSeek | +0.257 | -0.013 | +0.796 | -0.013 | +13.9 |
| Gemini | +0.282 | +0.044 | +0.779 | +0.022 | +16.2 |
| GPT-OSS | +0.300 | +0.023 | +0.788 | -0.013 | +17.6 |
| Qwen | +0.239 | -0.054 | +0.726 | +0.051 | +12.7 |

Per-run significance, A_H vs DM (paired Wilcoxon on each scenario's metric averaged over the runs in which it succeeded, the Methods protocol at main L480; 12 tests Holm-corrected; `d2_significance_like_for_like.csv`):

| Model | tau: p_Holm, Cliff's delta | Top-1: p_Holm, delta | MAE: p_Holm, delta |
|---|---|---|---|
| DeepSeek | 1.1e-6, -0.179 small | 1.8e-5, -0.112 negligible | 2.9e-15, 0.450 medium |
| Gemini | 2.6e-7, -0.240 small | 2.8e-5, -0.160 small | 4.5e-18, 0.444 medium |
| GPT-OSS | 3.4e-8, -0.187 small | 2.0e-6, -0.120 negligible | 1.5e-16, 0.383 medium |
| Qwen | 2.2e-6, -0.166 small | 2.2e-5, -0.094 negligible | 4.1e-8, 0.298 small |

All 12 stay significant. By decision type, only Appliance differs (every HVAC and Shower p_Holm >= 0.61).

### Options

- **A1-a (recommended)**: replace every Set B number with its Set A counterpart and fix L889 and L909. Token swaps only.
- **A1-b**: keep Set B as a labelled ensemble result. Averaging five extractions changes tau by +0.007 (DeepSeek), +0.017 (Qwen), +0.024 (GPT-OSS, including recovery of failed runs) and -0.002 (Gemini), at five times the extraction cost. If you want it, add it as one S2 sentence (A1.10 below), never in the provenance table.

### Edits (A1-a)

**A1.1, S L1305 (caption).**
- old: `\caption{Ranking accuracy of $\mathcal{A}_{\text{H}}$ with LLM-extracted and dataset-median hidden parameters. Significance testing on these conditions follows.}`
- new: `\caption{Ranking accuracy of $\mathcal{A}_{\text{H}}$ with LLM-extracted (five-run mean, as in Table~\ref{tab:overall_by_model}) and dataset-median hidden parameters. Significance testing on these conditions follows.}`

**A1.2, S L1312, L1315, L1318, L1321 (LLM-extracted rows).** The dataset-median rows stay.
- `GPT-OSS & LLM-extracted & 0.921 & 0.943 & 0.046 \\` -> `GPT-OSS & LLM-extracted & 0.897 & 0.917 & 0.052 \\`
- `Qwen & LLM-extracted & 0.897 & 0.913 & 0.066 \\` -> `Qwen & LLM-extracted & 0.880 & 0.897 & 0.072 \\`
- `DeepSeek & LLM-extracted & 0.904 & 0.913 & 0.040 \\` -> `DeepSeek & LLM-extracted & 0.897 & 0.908 & 0.045 \\`
- `Gemini & LLM-extracted & 0.921 & 0.928 & 0.047 \\` -> `Gemini & LLM-extracted & 0.923 & 0.931 & 0.048 \\`

**A1.3, S L1328, last sentence.**
- old: `Scenarios whose extraction failed are excluded from that condition rather than defaulted; the extracted condition scored 194 of 195 scenarios for GPT-OSS and 195 for the other three models.`
- new: `Scenarios whose extraction failed are excluded from that condition rather than defaulted, run by run; GPT-OSS scored 858 of its 975 scenario-runs (88.0\%) and each other model at least 973. On the scenarios GPT-OSS's runs scored, the dataset-median condition reaches $\tau = 0.597$ rather than 0.641.`

**A1.4, S L1330, one clause.**
- old: `so each cell is tested directly with a paired Wilcoxon signed-rank test over the 195 scenarios.`
- new: `so each cell is tested directly with a paired Wilcoxon signed-rank test over the 195 scenarios (194 for GPT-OSS), with each scenario's extracted value averaged over the runs in which it succeeded.`

**A1.5, S L1332, second sentence (token swaps inside one span).**
- old: `($p_{\text{Holm}} < 10^{-5}$, Cliff's $\delta$ between $-0.22$ and $-0.24$, small) and on MAE ($p_{\text{Holm}} < 10^{-9}$, $\delta$ between 0.35 and 0.49, medium to large); the Top-1 comparison is significant for all four models ($p_{\text{Holm}} < 10^{-3}$) but the effect size is small for GPT-OSS ($\delta=-0.175$) and Gemini ($\delta=-0.159$) and negligible for DeepSeek and Qwen ($\delta=-0.144$),`
- new: `($p_{\text{Holm}} < 10^{-5}$, Cliff's $\delta$ between $-0.17$ and $-0.24$, small) and on MAE ($p_{\text{Holm}} < 10^{-7}$, $\delta$ between 0.30 and 0.45, small to medium); the Top-1 comparison is significant for all four models ($p_{\text{Holm}} < 10^{-4}$) but the effect size is small for Gemini ($\delta=-0.160$) and negligible for GPT-OSS ($\delta=-0.120$), DeepSeek ($\delta=-0.112$) and Qwen ($\delta=-0.094$),`

**A1.6, main L808, effect-size sentence. Merged with A2.** Pick one version.
- old: `Extraction therefore adds 0.24--0.28 in $\tau$ beyond what the calculator provides.`
- new, A1 only (if you reject A2): `Measured on the scenarios each run scored, extraction therefore adds 0.24--0.30 in $\tau$ beyond what the calculator provides, almost all of it on Appliance.`
- new, combined A1+A2 (recommended): `Measured on the scenarios each run scored, per-scenario inputs therefore add 0.24--0.30 in $\tau$ beyond what the calculator provides, almost all of it on Appliance.`

"Almost all of it on Appliance" is the by-type result above: Appliance gains 0.73-0.80 in tau for every model, while HVAC and Shower show no significant difference for any model (p_Holm >= 0.61). Drop the clause if you prefer the token swap alone.

**A1.7, main L808, parenthetical.** `$p_{\text{Holm}} < 10^{-3}$ throughout` stays true (largest 2.8e-5).
- old: `Cliff's $\delta$ from $-0.14$ to $-0.24$ on Kendall's $\tau$ and Top-1 and from 0.35 to 0.49 on MAE`
- new: `Cliff's $\delta$ from $-0.09$ to $-0.24$ on Kendall's $\tau$ and Top-1 and from 0.30 to 0.45 on MAE`

**A1.8, main L909, two spans.**
- old: `GPT-OSS accounts for 117 of the 120 $\mathcal{A}_{\text{H}}$ failures, most of them on HVAC scenarios`
- new: `GPT-OSS accounts for 117 of the 120 $\mathcal{A}_{\text{H}}$ failures, all of them on HVAC scenarios`
- old: `When we recover each failed scenario from a run in which it succeeded, the reported figures do not change ($\tau$ 0.897, Top-1 91.7\%).`
- new: `When we recover each failed scenario from a run in which it succeeded, $\tau$ rises from 0.897 to 0.904 and Top-1 from 91.7\% to 92.0\%.`

**A1.9, main L889, Top-1 definition.**
- old: `lowers its success-weighted $\tau$ from 0.897 to 0.790 and its Top-1 from 91.7\% to 84.7\%.`
- new: `lowers its success-weighted $\tau$ from 0.897 to 0.790 and, with each failed scenario counted at the chance rate of 1/3, its Top-1 from 91.7\% to 84.7\%.`

**A1.10 (only if you choose A1-b), S, new sentence at the end of the L1332 paragraph.**
```latex
Averaging each scenario's extracted parameters over the runs in which it succeeded, a five-call ensemble rather than the benchmarked single call, changes $\tau$ by $+0.007$ for DeepSeek, $+0.017$ for Qwen, $+0.024$ for GPT-OSS, whose failed runs it also recovers, and $-0.002$ for Gemini.
```

### Knock-on effects

- No change needed, verified on Set A: abstract tau range (L304), L837, L947, Table `tab:item7`, Table `tab:incremental-contribution` rows for A_H (+0.310 Gemini, +0.266 Qwen are like-for-like correct), L775, L1071, S `tab:overall_by_model`, the S weight-vector and imputed tables.
- README L148 carries "0.24--0.28": edited in A2.12 (combined with A2's rescoping). README L154 ("Failure rates" bullet): old `concentrated in HVAC scenarios` -> new `all in HVAC scenarios`. No Part B item carries this swap.
- **Regeneration (links to A9):** the repository's significance script (`Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py`) still builds the extracted arm from the aggregate workbook, and `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py` still reports the five-run consensus arm as "extracted", so rerunning the pipeline regenerates the old Set B table and statistics. Before the release tag, either change that script to use the per-run arm (`extracted_per_run`, failed rows dropped, averaged per scenario) or ship `Analysis/pass5/d2_reproduce_ah_numbers.py` and say which script produces the S2 numbers. Code changes are outside this pass; this is a decision for you.

---

## A2. The label-lookup baseline: what the LLM contributes in A_H

### Problem

The paper argues that A_H's accuracy comes from the LLM's extraction. Main L808: "Extraction therefore adds 0.24--0.28 in $\tau$ beyond what the calculator provides." The abstract (L304) ends "an LLM can translate a plain-language description into that calculator's inputs," and the Conclusion (L1112) says "The language model adds value only where a single average input would be badly wrong for the household in front of it."

The dataset-median comparison shows that per-scenario inputs matter. It does not show that an LLM is needed to supply them. On Appliance the fixed default collapses (tau 0.097) because it assumes 7 p.m. while every Appliance question states the current time. All five members of the simulated panel raised this; the editor called a label-lookup / text-parse baseline the one required item.

### Evidence

Source: `paper/pass5/D1_REPORT.md`; script `Analysis/pass5/d1_lookup_baseline.py` (offline, 50 s) plus `d1_bootstrap_ci.py`; outputs `Analysis/pass5/d1_*.csv`. The harness reuses the paper's own ablation functions and reproduces the reference, FD and DM exactly, scenario by scenario.

Model-free baselines (`d1_baseline_summary.csv`):

| Baseline | tau HVAC | tau Appliance | tau Shower | tau overall | Top-1 overall (%) | MAE |
|---|---|---|---|---|---|---|
| Fixed default | 0.933 | 0.097 | 0.800 | 0.614 | 70.3 | 0.097 |
| Dataset median | 0.933 | 0.179 | 0.800 | 0.641 | 76.9 | 0.122 |
| FD + stated time | 0.933 | 0.959 | 0.800 | 0.901 | 93.8 | 0.062 |
| Label lookup | 0.971 | 0.959 | 0.833 | 0.925 | 94.4 | 0.040 |

A_H minus label lookup, like-for-like tau (`d1_ah_gain_like_for_like.csv`, `d1_bootstrap_ci_gain.csv`):

| Model | A_H tau | Overall gain | 95% CI | HVAC | Appliance | Shower | Top-1 gain (pp) |
|---|---|---|---|---|---|---|---|
| DeepSeek | 0.897 | -0.027 | [-0.057, 0.000] | -0.052 | +0.016 | -0.047 | -3.6 |
| Gemini | 0.923 | -0.001 | [-0.025, 0.023] | +0.006 | 0.000 | -0.011 | -1.2 |
| GPT-OSS | 0.897 | -0.020 | [-0.050, 0.008] | -0.026 | +0.008 | -0.047 | -2.0 |
| Qwen | 0.880 | -0.045 | [-0.100, 0.009] | -0.090 | -0.053 | +0.018 | -4.6 |

- No paired Wilcoxon test on tau or Top-1, overall (12 tests) or by decision type (35 defined tests), favours A_H for any model. One favours lookup: DeepSeek Top-1 overall, p_Holm 0.040, negligible effect. Lookup has significantly lower MAE than A_H for GPT-OSS (p_Holm 0.003) and Qwen (p_Holm < 0.001).
- FD + stated time alone reproduces 101% (DeepSeek), 93% (Gemini), 99% (GPT-OSS) and 108% (Qwen) of A_H's overall tau gain over FD (`d1_share_reproduced.csv`).
- Parser accuracy: baseline time 64/65, occupancy 66/70. The LLMs match occupancy in 73.8-82.2% of extractions (per run).
- Parameter swaps: the LLM's own values help only for kWh per cycle (DeepSeek +0.016, GPT-OSS +0.008 Appliance tau) and SEER within an LLM's own HVAC set; its R-values and GPM values do worse than the tier midpoints (mean R-value error 1.8-4.5 for the models against 1.0; GPM 0.31-0.45 against 0.22).

Validity limits you should state and weigh:
1. The parsers were written after reading the Test question templates. The result shows the benchmark cannot separate the LLM's reading from a rule's; it does not show LLMs add nothing on real homeowner text. The robust parts need no occupancy parser: FD+time uses only a clock-time parser (0.901), and lookup without the occupancy parser reaches 0.921.
2. The R-value midpoints come from the tier ranges the supplement publishes (S L570). Without them, lookup HVAC tau is 0.933, which still matches or beats three of four models on HVAC.
3. Non-significance is not equivalence; the CIs cap any LLM advantage over lookup at about +0.02 tau.

### Options

- **A2-a (recommended)**: report the lookup and FD+time in the main text next to the dataset-median result, rescope every sentence that credits the LLM with the accuracy, and add an S2 subsection. The contribution becomes: a calculator plus correctly read inputs reproduces the reference; an LLM is one way to read them; on templated text it shows no measurable edge over rules.
- **A2-b**: report only in S2 and rescope L808 and L1112. A reviewer who asked for the baseline will look for it in the main text, so I do not recommend this.
- **A2-c**: add the stronger "LU-corpus" variant (label -> median true value among the 90 disjoint retrieval scenarios; tau 0.938, significantly better than Qwen's A_H) as a further row. I left it out of the primary rows because it uses fitted values.

### Edits (A2-a)

**A2.1, main L745, one token.**
- old: `We compare the architectures with two non-LLM baselines`
- new: `We compare the architectures with three non-LLM baselines`

**A2.2, main L749 (Methods, `sec:hybrid-ablation-methods`), one token and an appended pair of sentences.**
- old: `We run two non-LLM conditions through the calculators that $\mathcal{A}_{\text{H}}$ uses.`
- new: `We run three non-LLM conditions through the calculators that $\mathcal{A}_{\text{H}}$ uses.`
- old: `so it tests whether a household needs an LLM at all.`
- new: `so it tests whether a household needs an LLM at all. The label-lookup baseline reads the same fields and question text as $\mathcal{A}_{\text{H}}$'s LLM and fills each withheld parameter by a fixed rule: each band label becomes its band midpoint, a keyword parser reads the current time and the occupancy pattern from the question, and every other parameter keeps its fixed default (rules in Supplementary Material S2). It tests whether the LLM reads the scenario better than fixed rules do.`

**A2.3, main L775, last sentence. Merged with A6 (optional sentence after it).**
- old: `With no LLM at all, it outranks direct and example-guided LLM scoring for every model, and only LLM-parameterized reference scoring clears it.`
- new: `With no LLM at all, it outranks direct and example-guided LLM scoring for every model, and among the LLM architectures only LLM-parameterized reference scoring clears it.`
- If you accept A6's main-text option, append A6.3's sentence directly after this one.

**A2.4, Table `tab:incremental-contribution`, insert two rows after L788** (`    Fixed default & 70.3 & $0.0$ & 0.614 & $0.000$ \\`). Differences computed before rounding.
```latex
    Fixed default + stated time & 93.8 & $+23.6$ & 0.901 & $+0.287$ \\
    Label lookup (no LLM) & 94.4 & $+24.1$ & 0.925 & $+0.311$ \\
```

**A2.5, main L808, effect-size sentence.** Combined with A1; the text is A1.6 "combined A1+A2".

**A2.6, main, new paragraph after L808** (between the dataset-median paragraph and the paragraph starting "The fixed default succeeds where one criterion decides"):
```latex
Reading those inputs does not require an LLM. The label-lookup baseline fills the same withheld parameters by fixed rules and reaches $\tau = 0.925$ and Top-1 of 94.4\% (Table~\ref{tab:incremental-contribution}). On the scenarios each run scored, $\mathcal{A}_{\text{H}}$'s $\tau$ differs from the lookup's by $-0.001$ for Gemini, $-0.020$ for GPT-OSS, $-0.027$ for DeepSeek and $-0.045$ for Qwen, and no paired test on $\tau$ or Top-1, overall or by decision type, favours extraction for any model (Supplementary Material S2). One input explains most of the gain over the dataset median: every Appliance question states the current time, and a fixed default that reads only that time reaches $\tau = 0.959$ on Appliance, against 0.097 for the unmodified default and 0.906--0.975 for $\mathcal{A}_{\text{H}}$. Our scenarios state what the calculator needs in fixed phrasings, so this benchmark cannot separate the LLM's reading of a scenario from a parser's; free-form household descriptions would be needed to show what the model adds.
```

**A2.7, main L1048, third point. Merged with Part B's "comes close" -> "matches or exceeds" fix.**
- old: `Third, a calculator driven by fixed constants, with no LLM at all, already comes close on two of the three decision types, which limits how much the language model can contribute.`
- new: `Third, a calculator driven by fixed constants, with no LLM at all, matches or exceeds $\mathcal{A}_{\text{H}}$ for two of the four models on HVAC and on Shower, and one driven by fixed rules that read the scenario text matches $\mathcal{A}_{\text{H}}$ on all three decision types, which limits how much the language model can contribute.`
- Check: FD HVAC 0.933 beats DeepSeek 0.920 and Qwen 0.881; FD Shower 0.800 beats DeepSeek and GPT-OSS (0.787). Part B's B16 proposes the "comes close" swap on its own ("already matches or beats LLM-parameterized reference scoring for two of the four models on two of the three decision types"); if you accept A2, apply this version and skip B16.

**A2.8, main L1112 (Conclusion paragraph). Two sentences in one paragraph; the A4 sentence is shown for context.**
- A4 edit (second sentence), see A4.2: `so where a calculator exists we see no reason to use it.` -> `so where a calculator exists we see no reason to use it in the form we tested: one call per alternative, at the lowest reasoning tier, with no access to the reference's value functions.`
- A2 edit (last sentence):
  - old: `The language model adds value only where a single average input would be badly wrong for the household in front of it.`
  - new: `The language model adds value only where a single average input would be badly wrong for the household in front of it and no fixed rule can read the right input from the description. On our scenarios, a rule-based parser reading the same fields ranked as well as $\mathcal{A}_{\text{H}}$ did.`
- Optional, first sentence of the same paragraph (it claims the LLM "is worth using", which the lookup does not show):
  - old: `An LLM is worth using as an interpreter once a deterministic calculator exists,`
  - new: `An LLM can serve as the interpreter once a deterministic calculator exists,`

**A2.9, main L1083. Merged with A3 (per-run occupancy percentages).**
- old: `at 75.4\% for GPT-OSS, 78.6\% for Qwen, 80.0\% for Gemini and 81.4\% for DeepSeek (Section~\ref{sec:res-extraction}). Occupancy context is the one parameter a model must read from the phrasing of the question rather than look up in a scenario field, which is the error class their taxonomy predicts a calculator cannot remove.`
- new: `at 73.8\% for GPT-OSS, 78.7\% for Qwen, 80.0\% for Gemini and 82.2\% for DeepSeek (Section~\ref{sec:res-extraction}). Occupancy context and appliance run time are the two parameters a model must read from the phrasing of the question rather than look up in a scenario field, and occupancy is the one the models often miss, which is the error class their taxonomy predicts a calculator cannot remove.`
- Why: every Appliance question also states the run time, so "the one parameter" is false. The percentages move to the per-run basis (A3). Optional extra sentence, if you want the parser comparison here: `A keyword parser written for our question templates reads occupancy correctly in 66 of 70 scenarios (Supplementary Material S2), so on these templates the misses come from the models' reading rather than from ambiguous questions.`

**A2.10, main L945, one word-level change** (same paragraph as A3.4, different sentence).
- old: `All four models recover appliance baseline run time exactly, and three`
- new: `All four models recover appliance baseline run time in at least 99.7\% of extractions, and three`
- Why: Qwen missed the time once across five runs (99.7%); the other three are 100%.

**A2.11, S, new subsection inserted before S L1334** (`\subsection{Alternative-Ordering Ablation: Full Statistics}`), after the parameter-source significance subsection.
```latex
\subsection{Label-Lookup Baseline}
\label{app:label-lookup}

The label-lookup baseline reads only the fields and question text that $\mathcal{A}_{\text{H}}$'s extraction prompt receives and fills each withheld parameter by a fixed rule, with no LLM call. The reference calculators then score it through the harness of the parameter-source ablation (Section~\ref{app:paramprov-significance}). With the true parameters, that harness reproduces the reference scores for all 195 test scenarios; with the fixed-default constants, it reproduces the fixed-default baseline scenario by scenario. Table~\ref{tab:lookup_rules} lists the rules.

\begin{table}[htbp]
\centering
\footnotesize
\caption{Rules of the label-lookup baseline. Parameters not listed keep their fixed-default value (Table~\ref{tab:fixed_default_constants}).}
\label{tab:lookup_rules}
\begin{tabular}{@{}lll@{}}
\toprule
Parameter & Input read & Rule \\
\midrule
R-value & Insulation tier & Tier midpoint: Poor 10, Medium 15.5, Good 21.5 \\
HVAC age & House-age band & Band midpoint (original equipment), capped at 60\,yr \\
SEER & HVAC age & Federal minimum at installation: 9 before 1992, 10 from 1992, 13 from 2006, 14 from 2023 \\
Occupancy context & Question text & Keyword rules; unstated absences set to 8\,h \\
Baseline run time & Question text & Stated clock time \\
Appliance type & Question text & Keyword (as in the fixed default) \\
GPM & Flow-rate band & Band midpoint: low 1.5, standard 2.5, high 4.0 \\
\bottomrule
\end{tabular}
\end{table}

The time parser recovers the true baseline run time in 64 of 65 Appliance scenarios, and the occupancy parser recovers the true occupancy context in 66 of 70 HVAC scenarios; its four misses read a 12-hour absence as 8 hours. We wrote both parsers after reading the question templates, so their accuracy reflects the templated phrasing of our scenarios.

\begin{table}[htbp]
\centering
\footnotesize
\caption{Kendall's $\tau$ of the non-LLM baselines by decision type (195 test scenarios).}
\label{tab:lookup_by_type}
\begin{tabular}{@{}lcccccc@{}}
\toprule
Baseline & HVAC & Appliance & Shower & Overall & Top-1 (\%) & MAE \\
\midrule
Fixed default & 0.933 & 0.097 & 0.800 & 0.614 & 70.3 & 0.097 \\
Dataset median & 0.933 & 0.179 & 0.800 & 0.641 & 76.9 & 0.122 \\
Fixed default + stated time & 0.933 & 0.959 & 0.800 & 0.901 & 93.8 & 0.062 \\
Label lookup & 0.971 & 0.959 & 0.833 & 0.925 & 94.4 & 0.040 \\
\bottomrule
\end{tabular}
\end{table}

\begin{table}[htbp]
\centering
\footnotesize
\caption{Gain in Kendall's $\tau$ of $\mathcal{A}_{\text{H}}$ over the label-lookup baseline, on the scenarios each run scored, averaged over five runs. The CI is a 95\% paired bootstrap interval over scenarios.}
\label{tab:lookup_gain}
\begin{tabular}{@{}lcccccc@{}}
\toprule
Model & $\mathcal{A}_{\text{H}}$ $\tau$ & Overall gain & 95\% CI & HVAC & Appliance & Shower \\
\midrule
DeepSeek & 0.897 & $-0.027$ & $[-0.057,\,0.000]$ & $-0.052$ & $+0.016$ & $-0.047$ \\
Gemini   & 0.923 & $-0.001$ & $[-0.025,\,0.023]$ & $+0.006$ & $0.000$ & $-0.011$ \\
GPT-OSS  & 0.897 & $-0.020$ & $[-0.050,\,0.008]$ & $-0.026$ & $+0.008$ & $-0.047$ \\
Qwen     & 0.880 & $-0.045$ & $[-0.100,\,0.009]$ & $-0.090$ & $-0.053$ & $+0.018$ \\
\bottomrule
\end{tabular}
\end{table}

We test $\mathcal{A}_{\text{H}}$ against the label-lookup baseline within each model with paired Wilcoxon signed-rank tests on each scenario's metric averaged over the runs in which it succeeded, Holm-corrected over the twelve overall tests (four models, three metrics) and separately over the 35 defined tests by decision type. No test on Kendall's $\tau$ or Top-1 favours $\mathcal{A}_{\text{H}}$. The label-lookup baseline has the higher Top-1 for DeepSeek ($p_{\text{Holm}} = 0.040$, Cliff's $\delta = -0.08$, negligible) and the lower MAE for GPT-OSS ($p_{\text{Holm}} = 0.003$, $\delta = 0.22$, small) and Qwen ($p_{\text{Holm}} < 10^{-3}$, $\delta = 0.22$, small); no other overall test is significant.

Swapping one parameter at a time between an LLM's extraction and the lookup shows where the model helps. Per-scenario kWh per cycle raises Appliance $\tau$ by 0.016 for DeepSeek and 0.008 for GPT-OSS, and extracted SEER helps within the HVAC parameter sets of DeepSeek, Gemini and Qwen. The models' R-values and GPM values lose more than they gain against the tier and band midpoints: the mean R-value error is 1.8--4.5 for the models and 1.0 for the midpoint, and the mean GPM error is 0.31--0.45 against 0.22.
```

**A2.12, README L148 (Key Findings, first bullet). Merged with A1.**
- old: `LLM extraction itself accounts for 0.24--0.28 of the architecture's tau advantage; the calculator alone is not sufficient.`
- new: `Per-scenario inputs account for 0.24--0.30 of the architecture's tau advantage (measured on the scenarios each run scored, almost all of it on Appliance), and the calculator alone is not sufficient. The LLM is not needed to supply those inputs on these scenarios: a rule-based label-lookup baseline that fills them with no LLM reaches tau = 0.925, matching the architecture for every model.`
- README L150, same bullet as "only LLM-parameterized reference scoring clears it": `only LLM-parameterized reference scoring clears it.` -> `among the LLM architectures only LLM-parameterized reference scoring clears it; the label-lookup baseline clears it too.` (No Part B item edits README L148 or L150; B4 edits the separate L152 bullet.)

### Knock-on effects

- Abstract: A5 (both drafts carry the lookup or FD+time result).
- Main L1071: optional one sentence after `which is what Practicality measures.` (L1071, second sentence): `Each Appliance question states the current time, and when the fixed default reads that time instead of assuming 7\,p.m., its Appliance $\tau$ rises to 0.959, inside $\mathcal{A}_{\text{H}}$'s range across the four models (0.906--0.975).` It repeats A2.6's number, so add it only if A2.6 is not placed nearby.
- Main L330 and L1110 ("division of labor") still read correctly: the model translates, the calculator computes. A5 swaps "validated" there.
- Main L316 (intro: "A practitioner should choose by how much accuracy each piece of infrastructure adds") becomes more pointed; no change needed.
- Limitations (L1088-L1094): A2.6's last sentence already states the free-text limit. Add nothing unless you want it in Limitations too.
- Future Work L1099: a natural place for "test extraction on free-form household descriptions"; optional.
- Discussion 6.1 (A12).

---

## A3. The GPM mechanism

### Problem

Main L1057 explains why shower flow-rate (GPM) extraction errors change the recommendation more often than any other parameter: "Shower GPM is that parameter (Section~\ref{sec:res-extraction}): GPM multiplies against each alternative's own duration rather than scaling all three by a common amount, so a GPM error shifts the three duration alternatives by different absolute amounts and breaks the cancellation."

The code says the opposite. In `Ground Truth Calculators/ShowerGroundTruthCalculator.py`, energy cost is kWh x rate with kWh proportional to `gpm * hot_fraction * delta_t * duration_min` (L121-L126, L141) and water is `gpm * duration_min` (L145). Within a scenario, `hot_fraction`, `delta_t` and the rate are the same for all three alternatives. So a GPM error multiplies every alternative's cost and water by one common factor, extracted/true, and cannot reorder the durations on either criterion. The shortest shower stays cheapest and uses the least water at any GPM. The insulation example at L1055 has the same structure, and so do SEER, occupancy context and kWh per cycle.

README repeats the error at L144 ("because a flow-rate (GPM) error multiplies each alternative's own duration and so does not cancel across alternatives") and L149 ("The one consistent exception is shower flow rate (GPM), which multiplies against each alternative's own duration rather than scaling all three by a common amount -- it carries the highest top-1 flip probability of any extracted parameter for every model.").

Separately, the `P(Top-1 change | error)` column of Table `tab:extraction_accuracy` (main L931-L937) and the MAE columns were computed on the five-run consensus parameters (the Set B basis of A1): `evaluate_parameter_extraction.py` reads the aggregate workbook by default. On the per-run basis the GPM values are 0.233-0.271, not 0.167-0.233.

### What the data support

A GPM error stretches or shrinks the gaps between the three durations on Energy Cost and Environmental Impact (65% of the weight) by the ratio extracted/true. Comfort, and Practicality's duration curve, favour mid-length showers and do not depend on GPM, so their gaps stay fixed. The winner is the duration where the cost and water saving balances the comfort loss, so each scenario has a break-even flow rate, and the winner flips when true and extracted GPM fall on opposite sides of it. That happens mostly when the reference winner leads narrowly.

### Why an EMS reviewer cares

This is the paper's mechanism claim, and Reviewer 2 called it internally inconsistent. Any reader who looks at the shower equations sees GPM as a common multiplier.

### Evidence

Source: `paper/pass5/D3_REPORT.md`; scripts `Analysis/pass5/d3_gpm_mechanism.py`, `d3_other_params_tradeoff.py`; outputs `Analysis/pass5/d3_*.csv`. Per run, averaged over five runs; failed scenario-runs excluded.

- Linearity check: within each of the 60 Shower test scenarios, cost per minute varies by at most 2.8e-17 and gallons per minute by 0 (`d3_linearity_check.csv`).
- Nonlinear parts matter little: 57% (Gemini), 60% (DeepSeek), 74% (GPT-OSS) and 94% (Qwen) of observed GPM-induced flips persist with value-function clipping, the tank-capacity step, the budget penalty and 2-dp rounding all switched off. The tank step is necessary for 0-19% of flips, clipping 0-3%, rounding 3-14%, budget penalty 0%.
- Every observed GPM flip disappears once Comfort and Practicality no longer vary with duration.
- Margin decides: a GPM error flips nearly every scenario whose winner leads by less than 0.01 MAVT and almost none leading by 0.05 or more (0 of 94, 80, 84 for DeepSeek, Gemini, GPT-OSS; 1 of 70 for Qwen; five runs summed within model).
- Leverage: multiplying the true GPM by some factor in [0.5, 2] changes the winner in 83% of Shower scenarios, against 33% for R-value, 36% for SEER and 11% for kWh per cycle. The models map each flow-rate tier to one number, so their median GPM error is 22-30%.
- Per-run P(Top-1 change | error), from `d3_p_top1_change_summary.csv`:

| Type | Parameter | GPT-OSS | Qwen | DeepSeek | Gemini |
|---|---|---|---|---|---|
| HVAC | R-value | 0.026 | 0.093 | 0.036 | 0.000 |
| HVAC | SEER | 0.052 | 0.037 | 0.048 | 0.051 |
| HVAC | HVAC age | 0.000 | 0.000 | 0.000 | 0.000 |
| HVAC | Occupancy context | 0.017 | 0.054 | 0.081 | 0.072 |
| Appliance | kWh/cycle | 0.014 | 0.080 | 0.017 | 0.031 |
| Shower | GPM | 0.271 | 0.256 | 0.249 | 0.233 |
| Shower | Tank size | 0.005 | 0.028 | 0.017 | 0.000 |
| Shower | Heater setpoint | 0.049 | 0.050 | 0.044 | 0.050 |

GPM is 2.8-5.2 times the next-largest numeric parameter (5.2x SEER for DeepSeek and GPT-OSS, 4.6x SEER for Gemini, 2.8x R-value for Qwen).

### Options

- **A3-a (recommended)**: replace the mechanism clause (A3.1) and the README sentences (A3.3); move Table 6 and L945 to the per-run basis (A3.4, A3.5); add the occupancy flip probability Reviewer 2 asked for.
- **A3-b**: A3.1 and A3.3 only; leave Table 6 on the ensemble basis with a caption saying so. Not recommended: it leaves a second Set B table in the main text after A1 removes the first.
- Optional A3.2: one sentence putting the attribution on record.

### Edits

**A3.1 (P1, required), main L1057, mechanism clause.**
- old: `Shower GPM is that parameter (Section~\ref{sec:res-extraction}): GPM multiplies against each alternative's own duration rather than scaling all three by a common amount, so a GPM error shifts the three duration alternatives by different absolute amounts and breaks the cancellation.`
- new: `Shower GPM is that parameter (Section~\ref{sec:res-extraction}): cost and water use are both proportional to GPM times duration, so a GPM error rescales the gaps between the three durations on those two criteria without reordering them, while the Comfort gaps, which do not depend on GPM, stay fixed; when the reference winner leads narrowly, the rescaled gaps are enough to change it.`
- The paragraph's first two sentences and its last one ("We would expect a multiplier of the same kind in another domain...") still hold: GPM "scales the outcome directly" and the three-tier flow-rate label is a "coarse proxy".

**A3.2 (P2, optional), main L1057, one sentence after A3.1.** The old string below is the end of A3.1's new text, so it exists only after A3.1 is applied.
- old: `when the reference winner leads narrowly, the rescaled gaps are enough to change it. We would expect`
- new: `when the reference winner leads narrowly, the rescaled gaps are enough to change it. Holding every other input at its true value, 57--94\% of the models' GPM-induced changes persist with the tank-capacity penalty, value-function clipping, budget penalty and score rounding all removed, and none persists once Comfort and Practicality no longer vary with duration (Supplementary Material S2). We would expect`
- Needs a short S2 paragraph with the attribution table above if you add it.

**A3.3, README L144 and L149 (Markdown).**
- L144 old: `because a flow-rate (GPM) error multiplies each alternative's own duration and so does not cancel across alternatives.`
- L144 new: `because a flow-rate (GPM) error rescales every duration's cost and water use by the same factor, which changes how they trade off against comfort, and many shower scenarios sit close to that trade-off's break-even point.`
- L149 old: `The one consistent exception is shower flow rate (GPM), which multiplies against each alternative's own duration rather than scaling all three by a common amount -- it carries the highest top-1 flip probability of any extracted parameter for every model.`
- L149 new: `The one consistent exception is shower flow rate (GPM). A GPM error scales every duration's cost and water use by one factor without reordering them, but it changes their weight against comfort, which GPM does not affect; shower winners often lead narrowly, so GPM carries the highest top-1 flip probability of any extracted parameter for every model (0.23-0.27 per run).`

**A3.4 (P4), main L945, per-run numbers** (same paragraph as A2.10 and the occupancy percentages).
- old: `The models misestimate HVAC equipment age by 6.1--8.5 years on average`
- new: `The models misestimate HVAC equipment age by 6.4--9.3 years on average`
- old: `at 75.4\% for GPT-OSS, 78.6\% for Qwen, 80.0\% for Gemini and 81.4\% for DeepSeek, because`
- new: `at 73.8\% for GPT-OSS, 78.7\% for Qwen, 80.0\% for Gemini and 82.2\% for DeepSeek, because`
- old: `For most parameters, the probability that an extraction error changes the top-ranked alternative is below 0.09, and for HVAC equipment age it is zero for every model. Shower GPM is the consistent exception, with the highest probability for every model (0.167--0.233), roughly two to four and a half times that of the next-largest parameter;`
- new: `For most parameters, the probability that an extraction error changes the top-ranked alternative is below 0.10, and for HVAC equipment age it is zero for every model; for occupancy context it is 0.017--0.081. Shower GPM is the consistent exception, with the highest probability for every model (0.233--0.271), roughly three to five times that of the next-largest parameter;`
- The occupancy percentages also appear at L1083; the combined L1083 edit is A2.9. The occupancy clause answers the review's request for P(Top-1 change | error) on occupancy.

**A3.5 (P5), Table `tab:extraction_accuracy`, main L931-L937.** Columns as printed: MAE GPT-OSS, Qwen, DeepSeek, Gemini, then P for the same order.
- old:
```latex
HVAC & R-value & 3.594 & 3.699 & 2.312 & 1.766 & 0.015 & 0.086 & 0.015 & 0.000 \\
HVAC & SEER & 2.135 & 1.585 & 1.602 & 1.313 & 0.049 & 0.033 & 0.032 & 0.075 \\
HVAC & HVAC age (yr) & 8.5 & 6.1 & 8.5 & 7.6 & 0.000 & 0.000 & 0.000 & 0.000 \\
Appliance & kWh/cycle & 0.425 & 0.975 & 0.341 & 0.541 & 0.016 & 0.066 & 0.016 & 0.031 \\
Shower & GPM & 0.256 & 0.271 & 0.368 & 0.367 & \textbf{0.174} & \textbf{0.167} & \textbf{0.185} & \textbf{0.233} \\
Shower & Tank size (gal) & 8.1 & 8.9 & 6.9 & 6.7 & 0.000 & 0.026 & 0.025 & 0.000 \\
Shower & Heater setpoint (\textdegree{}F) & 4.7 & 4.6 & 8.3 & 4.6 & 0.042 & 0.050 & 0.042 & 0.050 \\
```
- new:
```latex
HVAC & R-value & 4.411 & 4.463 & 3.216 & 1.806 & 0.026 & 0.093 & 0.036 & 0.000 \\
HVAC & SEER & 2.208 & 1.626 & 1.651 & 1.376 & 0.052 & 0.037 & 0.048 & 0.051 \\
HVAC & HVAC age (yr) & 9.3 & 6.4 & 8.4 & 7.8 & 0.000 & 0.000 & 0.000 & 0.000 \\
Appliance & kWh/cycle & 0.453 & 0.998 & 0.363 & 0.548 & 0.014 & 0.080 & 0.017 & 0.031 \\
Shower & GPM & 0.449 & 0.305 & 0.370 & 0.367 & \textbf{0.271} & \textbf{0.256} & \textbf{0.249} & \textbf{0.233} \\
Shower & Tank size (gal) & 8.6 & 8.9 & 7.2 & 6.7 & 0.005 & 0.028 & 0.017 & 0.000 \\
Shower & Heater setpoint (\textdegree{}F) & 4.8 & 4.6 & 8.9 & 4.6 & 0.049 & 0.050 & 0.044 & 0.050 \\
```
- Caption, main L917:
  - old: `\caption{Extraction error and its effect on the top-ranked alternative, by numeric hidden parameter.}`
  - new: `\caption{Extraction error and its effect on the top-ranked alternative, by numeric hidden parameter (computed within each run, mean of five runs).}`

### Knock-on effects

- L945 "roughly two to four and a half times" and "below 0.09" change with the table (A3.4).
- L914 describes the counterfactual; the caption now carries the per-run basis, so L914 can stay.
- L952 ("Even on Shower, where GPM errors change the recommendation most often") and L996 ("The calculator's error cancellation absorbs the perturbation") remain consistent.
- L1055 (insulation example, "The cancellation fails only when another alternative is close to winning on Comfort or Practicality") is correct; it states the general mechanism.
- Abstract, end of Introduction and Conclusion do not state the mechanism; no change.
- Recommended one-line thesis for any summary (response letter, highlights): "A GPM error scales every shower duration's cost and water use by the same factor, so it never reorders the durations on those criteria; it changes how heavily they weigh against comfort, which GPM does not affect, and flips the recommendation when the reference winner leads narrowly."
- Regeneration (A9): the table's generator reads the aggregate workbook by default; same code decision as A1.

---

## A4. Rescoping "LLMs should not score", three prompt disclosures, the no-anchors ablation by decision type

### Problem

Two sentences generalize past the design.

- Main L304 (abstract, last sentence): "LLMs should not score MCDA-based environmental recommendations themselves, but in any domain with a validated modeling calculator, an LLM can translate a plain-language description into that calculator's inputs."
- Main L1112 (Conclusion): "Direct LLM scoring is the least accurate of the three architectures for every model and costs more than extracting parameters for a calculator, so where a calculator exists we see no reason to use it."

What was tested: one API call per alternative (pointwise scoring), the lowest reasoning tier each model offers (`model_config.py`: GPT-OSS `low`, Gemini `minimal`, DeepSeek and Qwen `none`), and prompts that give the 0-1 scale and verbal anchors but not the reference's value functions, its 5th-95th percentile normalization bounds or its budget penalty. Pairwise or listwise judging, higher reasoning effort and a prompt stating the value model were not tested.

Three facts about the prompts are undisclosed in the main text, all verified in code:

1. **A_E's system prompt drops A_D's per-decision-type anchors.** A_D (`Direct_LLM_Scoring.py` L320-L357) gives good/moderate/poor descriptions per criterion and decision type; A_E's `build_system_prompt()` (`Example-Guided_LLM_Scoring.py` L299-L315) omits them ("Calibration anchors are intentionally omitted because RAG already supplies scored in-context examples"). So A_D and A_E differ in two things, the exemplar and the anchors. The supplement says so (S L1237, "its original prompt contains no anchors"); the main text does not.
2. **The Appliance emissions anchor promises a contrast the reference barely has.** A_D's anchor (S L289-L290): "environmental: good when grid emissions are low (typically overnight); moderate during shoulder hours; poor when peak-period generation is dirtiest." The reference uses PJM marginal factors 1.041 (peak) and 0.976 (off-peak) lbs CO2/kWh, a 6.2% difference. Across the 65 Appliance test scenarios the reference Environmental Impact score spans 0.026 within a scenario on average and is identical for all three alternatives in 32% of them; Energy Cost spans 0.230, Comfort 0.466, Practicality 0.609 (`Analysis/pass5/d9_appliance_env_contrast.csv`). Environmental Impact carries the largest weight (0.35).
3. **No prompt states the value functions, the percentile bounds or the budget penalty.** A search of both prompt builders finds only the scenario field "Utility Budget: $.../month".

The prompt ablation removed A_D's anchors ("no_anchors" arm). Its overall effect hides large offsetting effects by decision type, and the ablation's control runs are not the benchmark runs: 10 runs for DeepSeek, GPT-OSS and Qwen (3 for Gemini) against the benchmark's 5, a separate collection session, scored against the reference before the shower comfort function was revised, and tau computed on continuous scores with ties retained. Main L998 quotes the control's Qwen value (tau = -0.052) without saying so; the benchmark's Qwen A_D tau is 0.010.

### Why an EMS reviewer cares

Reviewers 2 and 4 rated the scope of "LLMs should not score" critical: A_D is graded against a value model it never sees. The editor made rescoping and disclosure a condition.

### Evidence

Source: `paper/pass5/D9_D12_REPORT.md` sections 3-5; script `Analysis/pass5/d9_prompt_checks.py`; outputs `d9_prompt_ablation_by_type.csv`, `d9_prompt_ablation_tests.csv`.

No-anchors minus control, by decision type (tau as collected, Shower on the earlier reference; Top-1 recomputed against the current reference; Wilcoxon on scenario run-means, Holm across the 12 model x type tests per metric):

| Model | HVAC tau diff (p_Holm) | Appliance tau diff | Shower tau diff | Appliance Top-1 diff (pp) |
|---|---|---|---|---|
| DeepSeek | -0.052 (0.90) | +0.335 (0.012) | -0.244 (0.0004) | +30.5 (0.0002) |
| Gemini | -0.279 (0.0004) | +0.003 (1.0) | +0.121 (0.50) | +2.1 (1.0) |
| GPT-OSS | -0.111 (0.18) | +0.003 (1.0) | +0.279 (0.0008) | -4.5 (0.54) |
| Qwen | -0.016 (1.0) | +0.306 (0.025) | -0.064 (0.63) | +29.2 (0.003) |

Removing the anchors raises Appliance tau by about 0.3 for DeepSeek and Qwen, lowers HVAC tau for Gemini, and moves Shower in opposite directions for DeepSeek and GPT-OSS. DeepSeek's Shower loss rests on the earlier Shower reference and does not show in Top-1 against the current one. All four Appliance anchors were removed together, so the emissions anchor's share cannot be isolated.

### Options

- **A4-a (recommended)**: scope L1112 and the abstract to the tested design; add the three disclosures (one sentence in Section 3.2, one Limitations paragraph, one S1 paragraph); add the by-type sentence and S2 table; label the control where L998 quotes it; fix the L757 description of what the ablation removed.
- **A4-b**: scope sentences only. Leaves two of Reviewer 2's major points unanswered: that the main text should say A_E's prompt drops A_D's anchors, and that A_D is graded against a value model it never sees, under an Appliance emissions anchor that promises a contrast the reference barely has, which the no-anchors ablation by decision type should test.
- A listwise or specification-informed A_D arm would need new API data; the panel said scoping is enough.

### Edits (A4-a)

**A4.1, abstract.** Handled in A5; both abstract drafts drop the sentence and scope A_D to "one alternative per call without the reference's value functions".

**A4.2, main L1112.**
- old: `so where a calculator exists we see no reason to use it.`
- new: `so where a calculator exists we see no reason to use it in the form we tested: one call per alternative, at the lowest reasoning tier, with no access to the reference's value functions.`
- The factual half holds: A_D is least accurate for every model on the numbers of record, under the five-run ensemble (A7) and on regret (A7).

**A4.3, main L461 (A_E paragraph), one inserted sentence.**
- old: `score the current situation on its own merits rather than copy the example's scores. On top of everything`
- new: `score the current situation on its own merits rather than copy the example's scores. Its system prompt names the four criteria and the 0--1 scale but omits the per-decision-type anchors in $\mathcal{A}_{\text{D}}$'s prompt (Supplementary Material S1), so the two architectures differ in their instructions as well as in the exemplar; the prompt ablation removes the anchors from $\mathcal{A}_{\text{D}}$ (Section~\ref{sec:prompt-ablation-methods}). On top of everything`

**A4.4, main, new Limitations paragraph** after the paragraph ending `We also assume electric resistance water heating in every Shower scenario.` (L1094) and before `\FloatBarrier` (L1096). A11 edits a different sentence of the L1094 paragraph; this insertion is unaffected.
```latex
We tested one way of asking a model to score: one call per alternative, at the lowest reasoning tier each model offers, with a prompt that gives the 0--1 scale and, for $\mathcal{A}_{\text{D}}$, verbal anchors, but not the reference's value functions, its 5th--95th percentile normalization bounds or its budget penalty. $\mathcal{A}_{\text{D}}$ and $\mathcal{A}_{\text{E}}$ therefore had to reproduce a value model they never saw. One of $\mathcal{A}_{\text{D}}$'s anchors also overstates a contrast the reference barely contains: it rates Appliance runs during peak-period generation as poor on Environmental Impact, but the PJM marginal factors differ by only 6.2\% between peak and off-peak, so the reference's Appliance Environmental Impact scores span 0.026 within a scenario on average (Supplementary Material S1). Pairwise or listwise judging, higher reasoning effort, or a prompt that states the value model could score better, and we did not test them; our conclusions about direct LLM scoring apply to the design we tested.
```

**A4.5, S1, new paragraph after S L329** (`\noindent The user prompt includes the other alternatives as reference so that the model doesn't assign the same scores to all alternatives.`):
```latex
The Appliance Environmental Impact anchor describes a larger contrast than the reference contains. The reference uses PJM marginal emissions factors of 1.041\,lbs CO\textsubscript{2}/kWh from 7\,a.m.\ to 11\,p.m.\ and 0.976 otherwise, a 6.2\% difference, so moving a cycle from peak to off-peak changes its Environmental Impact score by at most 0.019 per kWh of cycle energy. Across the 65 Appliance test scenarios, the reference Environmental Impact score spans 0.026 within a scenario on average and is identical for all three alternatives in 32\% of them; Energy Cost spans 0.23, Comfort 0.47 and Practicality 0.61. The $\mathcal{A}_{\text{E}}$ system prompt below has none of these anchors. Neither prompt gives the model the reference's value functions, the 5th--95th percentile normalization bounds of the main text's reference-range table, or the budget penalty.
```

**A4.6, main L998, control label plus by-type sentence.**
- old: `Under $\mathcal{A}_{\text{D}}$, the two significant comparisons, both for Qwen and both favoring the perturbation, fall between $\tau = -0.052$ and $\tau = 0.092$,`
- new: `Under $\mathcal{A}_{\text{D}}$, the two significant comparisons, both for Qwen and both favoring the perturbation, fall between $\tau = -0.052$ and $\tau = 0.092$ in the ablation's own runs, which we collected separately from the main benchmark (Supplementary Material S2),`
- Append at the end of the L998 paragraph, after `falls below $\mathcal{A}_{\text{D}}$ with DeepSeek ($\tau = 0.167$).`:
```latex
Removing $\mathcal{A}_{\text{D}}$'s anchors does not act the same way on every decision type: it raises Appliance $\tau$ by about 0.3 for DeepSeek and Qwen, lowers HVAC $\tau$ for Gemini by 0.28, and moves Shower $\tau$ in opposite directions for DeepSeek and GPT-OSS, with no detectable change in the other cells (Holm-corrected; Supplementary Material S2).
```
- Part B's B3 carries the separate L998 fix "no perturbation improved" (true for tau only); it touches a different sentence.

**A4.7, main L757, what the ablation removed.**
- old: `one removes the anchors that define the ends of the scoring scale,`
- new: `one removes the per-decision-type anchors that describe good, moderate and poor performance on each criterion,`

**A4.8, S2, append to the note at S L1237** (after `so no prompt perturbation reverses the architecture ordering for a fixed model.`):
```latex
The control cells are a separate collection, not the main benchmark runs: they use ten runs for DeepSeek, GPT-OSS and Qwen (three for Gemini) against the benchmark's five, were scored against the reference before the shower comfort function was revised, and compute Kendall's $\tau$ on the continuous weighted scores with ties retained, where the benchmark ranks with the tie-break of Supplementary Material S1. Their values therefore differ from the main results; for Qwen $\mathcal{A}_{\text{D}}$, $\tau$ is $-0.052$ in the control against 0.010 in the benchmark. We give the unanchored variant by decision type in Table~\ref{tab:prompt_ablation_bytype}, with Top-1 recomputed against the current reference from each run's predicted winner.
```
Then the table (from `Analysis/pass5/d9_d12_latex_tables.tex`, first block), with the note below it:
```latex
\begin{table*}[htbp]
\centering
\footnotesize
\caption{Prompt ablation by decision type: Kendall's $\tau$ and Top-1 accuracy (\%) for the $\mathcal{A}_{\text{D}}$ control, $\mathcal{A}_{\text{D}}$ without anchors, and the $\mathcal{A}_{\text{E}}$ control}
\label{tab:prompt_ablation_bytype}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{ll ccc ccc}
\toprule
& & \multicolumn{3}{c}{Kendall's $\tau$} & \multicolumn{3}{c}{Top-1 (\%)} \\
\cmidrule(lr){3-5}\cmidrule(lr){6-8}
Model & Cell & HVAC & Appliance & Shower & HVAC & Appliance & Shower \\
\midrule
Gemini & $\mathcal{A}_{\text{D}}$ control & 0.049 & $-$0.001 & 0.555 & 29.0 & 25.6 & 52.8 \\
 & $\mathcal{A}_{\text{D}}$ no\_anchors & $-$0.230 & 0.002 & 0.676 & 12.9 & 27.7 & 75.6 \\
 & $\mathcal{A}_{\text{E}}$ control & $-$0.052 & 0.340 & 0.750 & 20.5 & 55.4 & 73.3 \\
\addlinespace
DeepSeek & $\mathcal{A}_{\text{D}}$ control & $-$0.064 & 0.011 & 0.484 & 30.1 & 33.4 & 59.7 \\
 & $\mathcal{A}_{\text{D}}$ no\_anchors & $-$0.118 & 0.350 & 0.240 & 23.0 & 63.9 & 56.8 \\
 & $\mathcal{A}_{\text{E}}$ control & 0.040 & 0.360 & 0.552 & 37.7 & 68.0 & 59.0 \\
\addlinespace
GPT-OSS & $\mathcal{A}_{\text{D}}$ control & 0.140 & $-$0.149 & 0.168 & 37.9 & 27.7 & 36.7 \\
 & $\mathcal{A}_{\text{D}}$ no\_anchors & 0.029 & $-$0.146 & 0.446 & 31.6 & 23.2 & 56.3 \\
 & $\mathcal{A}_{\text{E}}$ control & 0.235 & $-$0.002 & 0.579 & 42.9 & 31.7 & 66.0 \\
\addlinespace
Qwen & $\mathcal{A}_{\text{D}}$ control & $-$0.007 & $-$0.147 & $-$0.001 & 31.6 & 18.2 & 38.2 \\
 & $\mathcal{A}_{\text{D}}$ no\_anchors & $-$0.021 & 0.158 & $-$0.069 & 30.4 & 47.4 & 34.7 \\
 & $\mathcal{A}_{\text{E}}$ control & 0.111 & 0.179 & 0.347 & 36.3 & 52.6 & 55.0 \\
\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table*}
```
Note text to place under the table: `$\tau$ as collected (Shower against the earlier comfort function); Top-1 recomputed against the current reference. Means over runs: ten for $\mathcal{A}_{\text{D}}$ (three for Gemini), five for $\mathcal{A}_{\text{E}}$ (three for Gemini).`

**A4.9, optional, main L740 (Methods).** Only if you want the value-model disclosure in Methods as well as Limitations.
- old: `from its own knowledge. The embedding model`
- new: `from its own knowledge. Neither prompt states the reference's value functions, normalization bounds or budget penalty. The embedding model`

### Knock-on effects

- L1061 ("generally the worst option on both counts") is conditioned on a calculator and says "generally"; leave it once L1112 and the abstract are scoped.
- L1067 ("$\mathcal{A}_{\text{D}}$ fails in a way the LLM-as-judge literature does not predict... Shower's single dominant duration trade-off being easier") is qualified by the no-anchors result (the Appliance anchors hurt two models): A12.
- L1109 ("A language model belongs in a pipeline that already has, or could have, a deterministic way to check its answer.") stays.
- A7's ensemble result supports the scoped claim (A_D stays last under averaging).

---

## A5. Abstract, title and scope

### Problem

The current abstract (main L304, 148 words counting each math expression as one word):

> Everyday decisions such as setting a thermostat or scheduling an appliance can lower a household's carbon footprint, but households make them by rules of thumb. Multi-criteria decision analysis (MCDA) could optimize these decisions, but an expert must first specify how the household trades off cost, emissions, comfort and convenience. We benchmark three ways to place a large language model (LLM) inside an MCDA workflow (direct LLM scoring, example-guided LLM scoring and LLM-parameterized reference scoring) on 195 household energy scenarios with four models. In LLM-parameterized reference scoring, the LLM only extracts the engineering parameters a deterministic calculator needs. This architecture reproduces a physics-based reference ranking at Kendall's $\tau=0.880$--$0.923$ and costs the least to run, while direct LLM scoring stays near chance. LLMs should not score MCDA-based environmental recommendations themselves, but in any domain with a validated modeling calculator, an LLM can translate a plain-language description into that calculator's inputs.

Four problems:
1. "physics-based": the reference's Comfort curves, Practicality curves, budget penalty and percentile normalization are normative choices, not physics (Reviewer 1).
2. "in any domain with a validated modeling calculator": one synthetic domain, calculators not validated against observations (editor, Reviewer 4).
3. No scope: four models at their lowest reasoning tier, three alternatives per scenario, synthetic Pennsylvania scenarios.
4. The boundary result is missing: a calculator with fixed defaults gets tau 0.614, reading the stated run time lifts it to 0.901, and a rule-based parser matches A_H (A2). The abstract's last clause also implies the LLM is needed for the translation, which A2 does not support, and the "should not score" clause exceeds the tested design (A4).

**Length limit.** Elsevier's Environmental Modelling & Software guide for authors limits the abstract to 150 words (search result for the EMS guide; the guide page returned HTTP 403 to direct fetch, so confirm on submission). `paper/PAPER_STATUS.md` section 6 item 2 records the same limit.

### Two abstracts (both within 150 words; A1-A4 consistent)

Both drop the opening "rules of thumb" sentence to make room and fold its examples into the MCDA sentence. Word counts treat each `$...$` as one word; Elsevier's counter may count differently, so keep the margin.

**Version 1: lookup-forward (147 words). Recommended.** It states the strongest finding directly and survives a reviewer who reads only the abstract.

- old: the entire content of L304 between `\begin{abstract}` and `\end{abstract}` (quoted above).
- new:
```latex
Multi-criteria decision analysis (MCDA) could guide household energy choices, such as a thermostat setpoint or an appliance run time, but an expert must first specify how a household trades off cost, emissions, comfort and convenience. We benchmark three ways to place a large language model (LLM) in an MCDA workflow (direct LLM scoring, example-guided LLM scoring and LLM-parameterized reference scoring) with four models at low reasoning effort, on 195 synthetic Pennsylvania scenarios with three alternatives each. In LLM-parameterized reference scoring, the LLM only extracts the engineering parameters a deterministic calculator needs; this architecture reproduces an engineering-and-preference reference ranking at Kendall's $\tau=0.880$--$0.923$ at the lowest cost. Direct LLM scoring, one alternative per call without the reference's value functions, stays near chance. A rule-based parser filling the same inputs without an LLM does as well ($\tau=0.925$), so on these scenarios the calculator and the stated details supply the accuracy.
```

**Version 2: fixed-default-forward (145 words).** It keeps the lookup for the body and gives the reader the calculator's own numbers.
```latex
Multi-criteria decision analysis (MCDA) could guide household energy choices, such as a thermostat setpoint or an appliance run time, but an expert must first specify how a household trades off cost, emissions, comfort and convenience. We benchmark three ways to place a large language model (LLM) in an MCDA workflow (direct LLM scoring, example-guided LLM scoring and LLM-parameterized reference scoring) with four models at low reasoning effort, on 195 synthetic Pennsylvania scenarios with three alternatives each. When the LLM only extracts the engineering parameters a deterministic calculator needs, it reproduces an engineering-and-preference reference ranking at Kendall's $\tau=0.880$--$0.923$ for the least cost; direct LLM scoring, one alternative per call without the reference's value functions, stays near chance. The calculator does most of the work. Fed fixed defaults, it reaches $\tau=0.614$ without an LLM, and reading the run time each appliance question states lifts it to $\tau=0.901$.
```

Both remove the "LLMs should not score" sentence, "in any domain" and "physics-based". If you want to keep the "rules of thumb" opener, you have about three words of room, not enough for a full sentence; cut elsewhere first.

### Scope swaps in the body (word-level)

- **main L328.** old: `against a physics-based multi-attribute value theory (MAVT) reference` -> new: `against a multi-attribute value theory (MAVT) reference built from engineering calculations and stated preferences`
- **main L330.** old: `into the inputs of a validated calculator,` -> new: `into the inputs of a deterministic calculator,`
- **main L415.** old: `so that it applies to any decision for which a validated calculator exists.` -> new: `so that it applies to any decision for which a deterministic calculator exists.`
- **main L873 (Table `tab:dispersion` note), optional.** old: `separates the alternatives more than the physics warrants.` -> new: `separates the alternatives more than the reference does.`
- **README L18.** old: `against a physics-based Multi-Attribute Value Theory (MAVT) reference calculator` -> new: `against a Multi-Attribute Value Theory (MAVT) reference calculator built from engineering calculations and stated preferences` (same swap as main L328; added in the self-containment audit because no item covered it).
- L496 ("the reference calculator uses what the physics requires") refers to the engineering inputs and can stay.

### Title

The current title (main L290 and S L193): *Benchmarking LLM Integration Strategies for MCDA-Assisted Household Energy Decision Support*.

The three candidates in `paper/PAPER_STATUS.md` section 6.1, quoted in full:
1. *Read, don't judge: where a language model adds value in multi-criteria household energy decisions*
2. *Is a language model worth adding to multi-criteria household energy decision support?*
3. *Language models as parameter extractors, not scorers: three integration architectures against a physics-based MAVT reference*

Two new candidates:
4. *What does a language model add to multi-criteria household energy decisions? A benchmark against a deterministic reference and rule-based baselines*
5. *Calculators carry the accuracy: benchmarking LLM integration strategies for multi-criteria household energy decisions*

After A2, candidate 1 promises value the benchmark cannot show over rules, and candidate 3 uses "physics-based" and implies extraction is where the LLM earns its place. **Recommendation: candidate 2.** It asks the question the paper answers, and the answer (only as a reader of inputs, and on templated scenarios a rule reads them as well) fits under it. Candidate 4 is the safer, more descriptive alternative. Keeping the current title is also defensible: it is neutral and claims nothing A2 contradicts. The supplement title (S L193) must match whichever you choose.

### Knock-on effects

- Keywords (L306) stay.
- Conclusion L1108 could carry the scope ("195 synthetic Pennsylvania household energy scenarios"); optional token insertion: old `across 195 household energy scenarios.` -> new `across 195 synthetic Pennsylvania household energy scenarios.`
- Highlights and graphical abstract (not in the source) must match the chosen abstract.

---

## A6. The listed-order baseline and ties

### Problem

The architectures rank with `sentinel_utils.apply_mavt_ranking`, which breaks ties by criterion priority and then by input order, the order the scenario sheet lists the alternatives. The sheet lists the reference winner first in 62.1% of test scenarios: 90.8% of Appliance, 75.0% of Shower, 24.3% of HVAC (`Analysis/pass5/d12_gt_winner_position.csv`). Two consequences:

1. **A no-model rule beats every A_D and A_E cell.** Ranking the alternatives in their listed order, with no model and no calculator, scores tau 0.463 and Top-1 62.1% (HVAC 0.010 / 24.3%, Appliance 0.703 / 90.8%, Shower 0.733 / 75.0%; `d12_position_baseline.csv`). The best A_E cell is tau 0.310 and Top-1 53.5%. Main L837 compares A_D with "33.3\% for a random choice"; a reviewer who computes the listed-order rule will ask why that is the comparison.
2. **Input-order tie-breaks inflate A_D and A_E Top-1** by 0.05 to 1.8 points overall, most for DeepSeek A_E (53.5% reported against 51.8% under a random tie-break). Counting every top tie as a miss lowers Top-1 by at most 5.8 points. A_H has top ties in at most 0.1% of scenarios.

S L203 also reports three wrong A_E tie rates: "in 2.7\%, 19.1\%, 6.4\% and 13.9\% of the same four models' $\mathcal{A}_{\text{E}}$ scenarios". Recomputing from the current run files gives 2.7 / 17.3 / 5.8 / 12.7% (Gemini / DeepSeek / GPT-OSS / Qwen); the published values were probably computed on an earlier A_E collection, and I could not find the script that produced them. The four A_D values reproduce exactly. S L203's closing clause ("the tie-break rule usually separates alternatives that already differ on at least one criterion") holds for ties anywhere in the ranking but not for ties at the top, where 71-95% of ties fall through to input order for every model except Gemini.

### Why an EMS reviewer cares

Reviewer 2 asked for the winner-position distribution or a random-tie-break Top-1. The listed-order result does not change any ordering claim (the alternative-reversal check at L996 shows A_D does not exploit list position: net Top-1 change under 9 of 195 for every model), but it changes what "near chance" means and it would inflate any LLM's score that had a first-position bias.

### Evidence

Source: `paper/pass5/D9_D12_REPORT.md` section 8; scripts `Analysis/pass5/d12_analyses.py`, `d12_position_baseline.py`; outputs `d12_ties_summary.csv`, `d12_position_baseline.csv`, `d12_gt_winner_position.csv`. The harness reproduces all 240 pipeline cells exactly (`d12_harness_gate.csv`).

### Options

- **A6-a (minimum)**: S1 disclosure only (corrected tie rates, top-tie paragraph and table, one listed-order sentence).
- **A6-b (recommended)**: A6-a plus one sentence in main Section 5.1, where the paper already lists its floors.
- **A6-c**: A6-b plus a row in Table `tab:incremental-contribution` (`Listed order (no model) & 62.1 & $-8.2$ & 0.463 & $-0.151$ \\`) and a qualification at L837. Makes the table busier after A2's two rows.

### Edits

**A6.1, S L203, three numbers** (confirm against whatever produced the originals before applying).
- old: `and in 2.7\%, 19.1\%, 6.4\% and 13.9\% of the same four models' $\mathcal{A}_{\text{E}}$ scenarios.`
- new: `and in 2.7\%, 17.3\%, 5.8\% and 12.7\% of the same four models' $\mathcal{A}_{\text{E}}$ scenarios.`

**A6.2, S, new paragraph and table after the L203 paragraph** (before `\subsection{Notation}` at L204):
```latex
Only a tie at the top weighted score can change Top-1. Such ties occur in 1.5--8.8\% of $\mathcal{A}_{\text{D}}$ scenarios and 2.0--11.0\% of $\mathcal{A}_{\text{E}}$ scenarios, depending on the model, and in at most 0.1\% of $\mathcal{A}_{\text{H}}$'s (Table~\ref{tab:top_ties}). For every model except Gemini, most top ties fall through the criterion priority to input order, because the tied alternatives carry identical criterion scores. The scenario sheet lists the reference winner first in 62\% of test scenarios (91\% of Appliance, 75\% of Shower, 24\% of HVAC), so input order favors the reference winner: reported Top-1 exceeds the Top-1 expected under a random tie-break by 0.05 to 1.8 percentage points, most for DeepSeek under $\mathcal{A}_{\text{E}}$ (53.5\% against 51.8\%). Counting every top tie as a miss lowers Top-1 by at most 5.8 points. The ordering $\mathcal{A}_{\text{H}} > \mathcal{A}_{\text{E}} > \mathcal{A}_{\text{D}}$ holds for every model under all three rules. Ranking the alternatives in their listed order, with no model, reaches $\tau = 0.463$ and Top-1 of 62.1\% (Appliance 0.703 and 90.8\%, Shower 0.733 and 75.0\%, HVAC 0.010 and 24.3\%).

\begin{table}[htbp]
\centering
\footnotesize
\caption{Ties at the top weighted score and their effect on Top-1 accuracy (\%)}
\label{tab:top_ties}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{ll ccccc}
\toprule
Model & Arch. & Top tie & By input order & Top-1 reported & Top-1 random break & Ties as misses \\
\midrule
Gemini & $\mathcal{A}_{\text{D}}$ & 1.5 & 0.2 & 36.2 & 36.1 & 35.6 \\
 & $\mathcal{A}_{\text{E}}$ & 2.0 & 0.3 & 48.7 & 48.3 & 47.4 \\
DeepSeek & $\mathcal{A}_{\text{D}}$ & 4.2 & 3.0 & 36.7 & 36.6 & 35.1 \\
 & $\mathcal{A}_{\text{E}}$ & 11.0 & 8.8 & 53.5 & 51.8 & 47.7 \\
GPT-OSS & $\mathcal{A}_{\text{D}}$ & 7.1 & 6.3 & 33.3 & 33.1 & 30.5 \\
 & $\mathcal{A}_{\text{E}}$ & 3.3 & 2.4 & 47.4 & 47.1 & 46.2 \\
Qwen & $\mathcal{A}_{\text{D}}$ & 8.8 & 8.4 & 30.0 & 28.7 & 26.0 \\
 & $\mathcal{A}_{\text{E}}$ & 7.1 & 6.6 & 46.6 & 45.0 & 42.7 \\
\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
```

**A6.3 (A6-b), main L775, one sentence appended after A2.3's sentence.**
```latex
The order in which the scenario sheet lists the alternatives is a floor of its own: ranking them in that order, with no model, gives $\tau = 0.463$ and Top-1 of 62.1\%, above every direct and example-guided cell, because the sheet lists the reference winner first in 91\% of Appliance and 75\% of Shower scenarios (Supplementary Material S1).
```

**A6.4 (A6-c only), main L837.**
- old: `Top-1 30.0--36.7\%, against 33.3\% for a random choice)`
- new: `Top-1 30.0--36.7\%, against 33.3\% for a random choice and 62.1\% for taking the alternatives in listed order)`

### Knock-on effects

- Main L738 already says ties break by criterion priority, then input order, and points to S1; no change.
- L996 (alternative reversal) supports the claim that A_D does not ride on list position; no change.
- A7's regret sentence uses the random-pick benchmark; the listed-order regret is 0.022 overall, lower than A_E's 0.032-0.047. If you take A6-c, mention it there too.

---

## A7. Optional analyses on existing data: ensembling, regret, tokens

### Problem

- **Ensembling.** Main L404 ends: "On arithmetic, LLMs often return wrong answers unless they check themselves against several generated solution paths \cite{imani2023mathprompter}, so averaging several scoring runs might likewise improve MCDA scores." The paper never tests this; Reviewer 2 asked for the test or the deletion.
- **Regret.** Top-1 does not say how much value a wrong pick loses. An EMS reader interprets "reference MAVT value lost" more easily.
- **Tokens.** Table `tab:item8` (L1019-L1042) sums input and output tokens. DeepSeek's A_D runs return 507 output tokens per call against 36 under A_E and 37 in the prompt-ablation A_D control with the identical prompt; that anomaly sets the upper end of "2.9--7.9 times" at L1017 (DeepSeek: 0.0867 / 0.0110). Without raw logs (A9) the extra tokens cannot be identified, although `model_config.py` sets DeepSeek's reasoning effort to "none".

### Evidence

Source: `paper/pass5/D9_D12_REPORT.md` sections 6, 7, 9; `Analysis/pass5/d12_ensemble.csv`, `d12_ensemble_wilcoxon.csv`, `d12_regret_summary.csv`, `d12_tokens.csv`.

- Ensemble (average each alternative's criterion scores over the runs in which the scenario succeeded, then rank): overall tau change -0.008 to +0.015 for A_D and -0.024 to +0.068 for A_E; no change survives Holm across 8 tests (smallest p_Holm 0.074, GPT-OSS A_E). MAE falls in every cell by 0.003-0.024, as it must (the error of an average cannot exceed the mean error). A_H > A_E > A_D holds for every model.
- Regret per scenario (reference MAVT, 0-1 scale): A_D 0.050 (Gemini), 0.051 (DeepSeek), 0.062 (GPT-OSS), 0.069 (Qwen); random pick 0.070. A_E 0.032-0.047. A_H 0.0015-0.0033; given a miss, A_H loses 0.019-0.032 against 0.078-0.099 for A_D.
- Tokens: input dominates every cell except DeepSeek A_D (372.4k in / 295.3k out per run). At 37 output tokens per call, DeepSeek's A_D would cost $0.037 rather than $0.087 per run, 3.4 rather than 7.9 times its A_H cost.

### Options and recommendations

- **Ensembling: delete the L404 clause (recommended)**, and add the null to S2. Alternative: keep the clause and add "in our data it does not (Supplementary Material S2)".
- **Regret: one main-text sentence plus an S2 table (recommended).**
- **Tokens: S1 table and paragraph, a caption pointer in `tab:item8`, and a pointer at L1017 (recommended).** Also check with OpenRouter's activity log whether DeepSeek A_D returned reasoning text.

### Edits

**A7.1, main L404.**
- old: `several generated solution paths \cite{imani2023mathprompter}, so averaging several scoring runs might likewise improve MCDA scores.`
- new (recommended): `several generated solution paths \cite{imani2023mathprompter}.`
- new (alternative): `several generated solution paths \cite{imani2023mathprompter}, so averaging several scoring runs might likewise improve MCDA scores; in our data it does not (Supplementary Material S2).`

**A7.2, S2, new paragraph with table** (a short subsection near "Run-to-Run Variance", S L980, e.g. `\subsection{Five-Run Score Ensemble}`):
```latex
Averaging each alternative's criterion scores over the five runs before ranking does not improve ranking accuracy. Overall Kendall's $\tau$ changes by $-0.008$ to $+0.015$ for $\mathcal{A}_{\text{D}}$ and by $-0.024$ to $+0.068$ for $\mathcal{A}_{\text{E}}$ across the four models, and no change survives Holm correction across the eight model--architecture tests (smallest $p_{\text{Holm}} = 0.074$, GPT-OSS $\mathcal{A}_{\text{E}}$). MAE falls in every cell, by 0.003--0.024, as it must, since the error of an averaged score cannot exceed the mean error of the runs averaged. The ordering $\mathcal{A}_{\text{H}} > \mathcal{A}_{\text{E}} > \mathcal{A}_{\text{D}}$ holds for every model.

\begin{table}[htbp]
\centering
\footnotesize
\caption{Five-run score ensemble against the per-run mean: Kendall's $\tau$ by model, architecture and decision type}
\label{tab:score_ensemble}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{ll cc cc cc cc}
\toprule
& & \multicolumn{2}{c}{Overall} & \multicolumn{2}{c}{HVAC} & \multicolumn{2}{c}{Appliance} & \multicolumn{2}{c}{Shower} \\
\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}
Model & Arch. & Per-run & Ens. & Per-run & Ens. & Per-run & Ens. & Per-run & Ens. \\
\midrule
Gemini & $\mathcal{A}_{\text{D}}$ & 0.176 & 0.169 & $-$0.032 & $-$0.048 & $-$0.022 & $-$0.026 & 0.633 & 0.633 \\
 & $\mathcal{A}_{\text{E}}$ & 0.310 & 0.285 & $-$0.116 & $-$0.181 & 0.344 & 0.354 & 0.767 & 0.756 \\
DeepSeek & $\mathcal{A}_{\text{D}}$ & 0.144 & 0.159 & $-$0.102 & $-$0.124 & 0.029 & $-$0.056 & 0.558 & 0.722 \\
 & $\mathcal{A}_{\text{E}}$ & 0.307 & 0.337 & 0.042 & 0.048 & 0.417 & 0.405 & 0.496 & 0.600 \\
GPT-OSS & $\mathcal{A}_{\text{D}}$ & 0.041 & 0.053 & 0.135 & 0.238 & $-$0.147 & $-$0.190 & 0.133 & 0.100 \\
 & $\mathcal{A}_{\text{E}}$ & 0.272 & 0.340 & 0.265 & 0.362 & $-$0.048 & 0.015 & 0.629 & 0.667 \\
Qwen & $\mathcal{A}_{\text{D}}$ & 0.010 & 0.002 & $-$0.003 & 0.057 & $-$0.031 & $-$0.128 & 0.069 & 0.078 \\
 & $\mathcal{A}_{\text{E}}$ & 0.208 & 0.214 & 0.160 & 0.133 & 0.231 & 0.282 & 0.240 & 0.233 \\
\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
```
(Gemini A_E ensemble tau prints 0.285 here and 0.286 in the report's text table: rounding of 0.2855. Use 0.285 in both places if you quote it.)

**A7.3, main L837, one sentence appended after** `exclude zero for every architecture difference.`
```latex
Measured as decision regret, the reference MAVT value lost by the alternative an architecture ranks first, $\mathcal{A}_{\text{D}}$ gives up 0.050--0.069 per scenario, close to the 0.070 a random pick gives up, $\mathcal{A}_{\text{E}}$ 0.032--0.047 and $\mathcal{A}_{\text{H}}$ 0.002--0.003; when $\mathcal{A}_{\text{H}}$ misses the reference winner, it loses 0.019--0.032 (Supplementary Material S2).
```
S2 table:
```latex
\begin{table}[htbp]
\centering
\footnotesize
\caption{Decision regret: reference MAVT value lost by the alternative each architecture ranks first, mean per scenario}
\label{tab:decision_regret}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{ll cccc c}
\toprule
Model & Arch. & Overall & HVAC & Appliance & Shower & Given a miss \\
\midrule
Gemini & $\mathcal{A}_{\text{D}}$ & 0.0499 & 0.0408 & 0.0900 & 0.0171 & 0.0783 \\
 & $\mathcal{A}_{\text{E}}$ & 0.0324 & 0.0451 & 0.0431 & 0.0063 & 0.0632 \\
 & $\mathcal{A}_{\text{H}}$ & 0.0015 & 0.0003 & 0.0014 & 0.0029 & 0.0218 \\
\addlinespace
DeepSeek & $\mathcal{A}_{\text{D}}$ & 0.0511 & 0.0445 & 0.0830 & 0.0241 & 0.0806 \\
 & $\mathcal{A}_{\text{E}}$ & 0.0346 & 0.0364 & 0.0302 & 0.0372 & 0.0743 \\
 & $\mathcal{A}_{\text{H}}$ & 0.0021 & 0.0024 & 0.0002 & 0.0037 & 0.0222 \\
\addlinespace
GPT-OSS & $\mathcal{A}_{\text{D}}$ & 0.0616 & 0.0306 & 0.1002 & 0.0557 & 0.0923 \\
 & $\mathcal{A}_{\text{E}}$ & 0.0427 & 0.0227 & 0.0865 & 0.0188 & 0.0812 \\
 & $\mathcal{A}_{\text{H}}$ & 0.0015 & 0.0006 & 0.0002 & 0.0037 & 0.0187 \\
\addlinespace
Qwen & $\mathcal{A}_{\text{D}}$ & 0.0691 & 0.0360 & 0.0965 & 0.0781 & 0.0987 \\
 & $\mathcal{A}_{\text{E}}$ & 0.0468 & 0.0298 & 0.0596 & 0.0528 & 0.0875 \\
 & $\mathcal{A}_{\text{H}}$ & 0.0033 & 0.0027 & 0.0041 & 0.0030 & 0.0322 \\
\midrule
\multicolumn{2}{l}{Random pick} & 0.0695 & 0.0372 & 0.0898 & 0.0852 & -- \\
\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
```
Note under it: `Mean per scenario over the scenarios each run scored, then over five runs. MAVT values lie on the reference's 0--1 scale. The reference has no tie at the top in any test scenario, so a Top-1 miss always carries positive regret.`

**A7.4, main L1020 (caption of `tab:item8`).**
- old: `\caption{Cost per run (USD) and total tokens per run (thousands, input+output).}`
- new: `\caption{Cost per run (USD) and total tokens per run (thousands, input+output; the split is in Supplementary Material S1).}`

**A7.5, main L1017.**
- old: `$\mathcal{A}_{\text{D}}$ costs 2.9--7.9 times as much as $\mathcal{A}_{\text{H}}$ on the same model,`
- new: `$\mathcal{A}_{\text{D}}$ costs 2.9--7.9 times as much as $\mathcal{A}_{\text{H}}$ on the same model (the 7.9 reflects unusually long DeepSeek outputs; Supplementary Material S1),`

**A7.6, S1, new paragraph with table** (after the prices sentence at S L201 or near the failure-mode table):
```latex
Input tokens dominate the cost of every architecture--model cell except DeepSeek under $\mathcal{A}_{\text{D}}$ (Table~\ref{tab:tokens_in_out}). $\mathcal{A}_{\text{D}}$ and $\mathcal{A}_{\text{E}}$ send about the same input per call, since $\mathcal{A}_{\text{E}}$'s exemplar replaces $\mathcal{A}_{\text{D}}$'s anchor text, and $\mathcal{A}_{\text{H}}$ is cheaper because it makes one call per scenario rather than three. DeepSeek's $\mathcal{A}_{\text{D}}$ runs returned 507 output tokens per call, against 36 under $\mathcal{A}_{\text{E}}$ and 37 in the prompt-ablation control with the same prompt; the stored diagnostics record only token totals, so we cannot tell whether the extra tokens were reasoning. At 37 output tokens per call, DeepSeek's $\mathcal{A}_{\text{D}}$ run would cost \$0.037 rather than \$0.087, 3.4 rather than 7.9 times its $\mathcal{A}_{\text{H}}$ cost.

\begin{table}[htbp]
\centering
\footnotesize
\caption{Input and output tokens per run (thousands), mean of five runs}
\label{tab:tokens_in_out}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{l cc cc cc cc}
\toprule
 & \multicolumn{2}{c}{Gemini} & \multicolumn{2}{c}{DeepSeek} & \multicolumn{2}{c}{GPT-OSS} & \multicolumn{2}{c}{Qwen} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}
Architecture & In & Out & In & Out & In & Out & In & Out \\
\midrule
$\mathcal{A}_{\text{D}}$ & 390.2 & 24.0 & 372.4 & 295.3 & 411.2 & 81.9 & 401.5 & 22.1 \\
$\mathcal{A}_{\text{E}}$ & 377.8 & 50.8 & 363.4 & 21.1 & 397.2 & 85.3 & 385.4 & 22.2 \\
$\mathcal{A}_{\text{H}}$ & 98.6 & 14.7 & 97.9 & 12.3 & 98.6 & 24.1 & 98.2 & 14.2 \\
\bottomrule
\end{tabular}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.0}
\end{table}
```

### Knock-on effects

- L1061 "by roughly three to eight times" carries the same DeepSeek anomaly; leave it, or add "(Section~\ref{sec:res-efficiency})" context once A7.5 is in.
- L1079 ("instead of trying to improve the model's arithmetic through chain-of-thought prompting \cite{wei2022cot} or self-verification") stays; A7.1 removes the only ensembling claim.
- The A_H parameter ensemble (A1-b) is the one place averaging helps a little; if you report it, say so next to A7.2.

---

## A8. Literature additions

### Problem

Main L320: "MCDA studies have begun to use LLMs to construct decision models or to score alternatives \cite{svoboda2024,icaart26}, but researchers have tested tool augmentation only on calculations with a single correct value." Two of the six standard LLM-to-solver papers falsify the clause: LLM+P scores plans, and NL4Opt scores formulations against a reference formulation. What survives is narrower: in all six, the correct answer is fixed by the problem, and none depends on preferences such as criterion weights. The editor also asked for EMS's own model-evaluation references (Jakeman et al. 2006; Bennett et al. 2013); none is in `paper/cas-refs.bib`.

### Evidence

Source: `paper/pass5/D13_REPORT.md`. Each reference was checked against the venue page (PMLR, NeurIPS, ACL Anthology) and Crossref:
- PAL (Gao et al., ICML 2023, PMLR 202:10764-10799): LLM writes a program, the interpreter runs it; scored against one gold answer.
- Toolformer (Schick et al., NeurIPS 2023, 36:68539-68551, DOI 10.52202/075280-2997; nine authors in the NeurIPS version): calls to calculator, QA, search, translator, calendar; gold answers.
- LLM+P (Liu et al., arXiv:2304.11477, preprint only): LLM writes PDDL, a planner solves it; scored on optimal plans.
- Logic-LM (Pan et al., Findings of EMNLP 2023, 3806-3824, DOI 10.18653/v1/2023.findings-emnlp.248): symbolic solvers; true/false/unknown labels.
- NL4Opt (Ramamonjison et al., NeurIPS 2022 Competitions Track, PMLR 220:189-203, published 2023): formulation scored against a canonical formulation.
- OptiMUS (AhmadiTeshnizi et al., ICML 2024, PMLR 235:577-596): (MI)LP formulation scored on the correct optimal objective value.
- Jakeman, Letcher, Norton (2006), EMS 21(5):602-614, DOI 10.1016/j.envsoft.2006.01.004.
- Bennett et al. (2013), EMS 40:1-20, DOI 10.1016/j.envsoft.2012.09.011.

### Recommendation

Apply A8.1 and A8.3; A8.2 is optional but keeps the literature review from citing six papers only in the introduction.

### Edits

**A8.1, main L320 (recommended).**
- old: `but researchers have tested tool augmentation only on calculations with a single correct value.`
- new: `but researchers have tested tool augmentation only on tasks whose correct answer does not depend on anyone's preferences, such as a numerical or factual answer \cite{gao2023pal,schick2023toolformer}, a logical conclusion \cite{pan2023logiclm}, a plan \cite{liu2023llmp} or an optimization model \cite{ramamonjison2023nl4opt,ahmaditeshnizi2024optimus}.`
- Hedged alternative: replace `researchers have tested tool augmentation only on tasks whose correct answer` with `the tool-augmentation studies we know of test the model on tasks whose correct answer`, rest unchanged.
- The next sentence (Goodell) and L410 ("Every task in that comparison has one correct number") still read correctly.

**A8.2, main L408 (optional).**
- old: `the model translates natural language into the inputs of an external tool, and the tool does the calculation. In building energy modeling,`
- new: `the model translates natural language into the inputs of an external tool, and the tool does the calculation. The model can write a program for an interpreter to run \cite{gao2023pal}, call a calculator or search engine it has learned to use \cite{schick2023toolformer}, or state a problem formally for a logic solver \cite{pan2023logiclm}, a classical planner \cite{liu2023llmp} or an optimization solver \cite{ramamonjison2023nl4opt,ahmaditeshnizi2024optimus}. In building energy modeling,`

**A8.3, main L476 (recommended).**
- old: `We evaluate accuracy on both scores and rankings. For score error,`
- new: `We evaluate accuracy on both scores and rankings. Environmental modelling guidance recommends choosing performance criteria to fit the model's purpose and combining several of them rather than relying on one \cite{jakeman2006tensteps,bennett2013characterising}. For score error,`

**A8.4, BibTeX to append to `paper/cas-refs.bib`** (house style: initials, braced acronyms, bare DOIs; none duplicates an existing key).
```bibtex
@inproceedings{gao2023pal,
  author = {L. Gao and A. Madaan and S. Zhou and U. Alon and P. Liu and Y. Yang and J. Callan and G. Neubig},
  title = {{PAL}: Program-aided Language Models},
  booktitle = {Proceedings of the 40th International Conference on Machine Learning (ICML)},
  series = {Proceedings of Machine Learning Research},
  volume = {202},
  pages = {10764--10799},
  publisher = {PMLR},
  year = {2023},
  url = {https://proceedings.mlr.press/v202/gao23f.html},
  note = {arXiv:2211.10435},
}

@inproceedings{schick2023toolformer,
  author = {T. Schick and J. Dwivedi-Yu and R. Dess{\`\i} and R. Raileanu and M. Lomeli and E. Hambro and L. Zettlemoyer and N. Cancedda and T. Scialom},
  title = {Toolformer: Language Models Can Teach Themselves to Use Tools},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS) 36},
  pages = {68539--68551},
  publisher = {Curran Associates, Inc.},
  year = {2023},
  doi = {10.52202/075280-2997},
}

@article{liu2023llmp,
  author = {B. Liu and Y. Jiang and X. Zhang and Q. Liu and S. Zhang and J. Biswas and P. Stone},
  title = {{LLM+P}: Empowering Large Language Models with Optimal Planning Proficiency},
  journal = {arXiv preprint arXiv:2304.11477},
  year = {2023},
  doi = {10.48550/arXiv.2304.11477},
}

@inproceedings{pan2023logiclm,
  author = {L. Pan and A. Albalak and X. Wang and W. Y. Wang},
  title = {{Logic-LM}: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2023},
  pages = {3806--3824},
  year = {2023},
  address = {Singapore},
  publisher = {Association for Computational Linguistics},
  doi = {10.18653/v1/2023.findings-emnlp.248},
}

@inproceedings{ramamonjison2023nl4opt,
  author = {R. Ramamonjison and T. T. Yu and R. Li and H. Li and G. Carenini and B. Ghaddar and S. He and M. Mostajabdaveh and A. Banitalebi-Dehkordi and Z. Zhou and Y. Zhang},
  title = {{NL4Opt} Competition: Formulating Optimization Problems Based on Their Natural Language Descriptions},
  booktitle = {Proceedings of the NeurIPS 2022 Competitions Track},
  series = {Proceedings of Machine Learning Research},
  volume = {220},
  pages = {189--203},
  publisher = {PMLR},
  year = {2023},
  url = {https://proceedings.mlr.press/v220/ramamonjison23a.html},
  note = {arXiv:2303.08233},
}

@inproceedings{ahmaditeshnizi2024optimus,
  author = {A. {AhmadiTeshnizi} and W. Gao and M. Udell},
  title = {{OptiMUS}: Scalable Optimization Modeling with ({MI}){LP} Solvers and Large Language Models},
  booktitle = {Proceedings of the 41st International Conference on Machine Learning (ICML)},
  series = {Proceedings of Machine Learning Research},
  volume = {235},
  pages = {577--596},
  publisher = {PMLR},
  year = {2024},
  url = {https://proceedings.mlr.press/v235/ahmaditeshnizi24a.html},
  note = {arXiv:2402.10172},
}

@article{jakeman2006tensteps,
  author = {A. J. Jakeman and R. A. Letcher and J. P. Norton},
  title = {Ten iterative steps in development and evaluation of environmental models},
  journal = {Environmental Modelling \& Software},
  volume = {21},
  number = {5},
  pages = {602--614},
  year = {2006},
  doi = {10.1016/j.envsoft.2006.01.004},
}

@article{bennett2013characterising,
  author = {N. D. Bennett and B. F. W. Croke and G. Guariso and J. H. A. Guillaume and S. H. Hamilton and A. J. Jakeman and S. Marsili-Libelli and L. T. H. Newham and J. P. Norton and C. Perrin and S. A. Pierce and B. Robson and R. Seppelt and A. A. Voinov and B. D. Fath and V. Andreassian},
  title = {Characterising performance of environmental models},
  journal = {Environmental Modelling \& Software},
  volume = {40},
  pages = {1--20},
  year = {2013},
  doi = {10.1016/j.envsoft.2012.09.011},
}
```
Style notes: PMLR issues no DOIs, so those entries carry `url` and the arXiv ID in `note`; if you prefer the bib's existing convention (`lewis2020`, `wei2022cot` put the arXiv DOI in `doi`), swap in `10.48550/arXiv.2211.10435`, `10.48550/arXiv.2303.08233`, `10.48550/arXiv.2402.10172`. The venue of record prints "William Wang" (Logic-LM) and "Timothy Yu" (NL4Opt); change the initials if you want an exact match.

Optional, from the same verification: Refsgaard and Henriksen (2004), *Advances in Water Resources* 27(1):71-82, DOI 10.1016/j.advwatres.2003.08.006, separates verification from validation and fits the Limitations sentence "We grade $\mathcal{A}_{\text{H}}$ against the same calculators it uses" (L1088); only the abstract was checked, so read it before writing a sentence around it.

### Knock-on effects

- The three PMLR/arXiv entries will cite with URLs; the compile will not warn.
- Part B's citation fixes (B19, Goodell attribution at L1083; B20, "compressed scores" at L1077) touch other sentences.

---

## A9. Raw logs, timestamps and collection dates

### Problem

Two public statements promise records the benchmark runs do not have.

- README L73: "Each run also writes `*_results_diagnostics_run_NN.json` (token counts, latency, failure-type counters, UTC collection timestamp) and `*_results_run_NN_raw.jsonl` (one record per API call with the prompt, the raw model response, and per-call latency and token counts)."
- Main L1136 (Software and data availability): "The repository includes the per-run outputs of every model, so every table, figure and statistical test in this paper can be regenerated without an API key."

What the repository holds (checked read-only today):
- **Raw logs**: 32 `*_raw.jsonl` files exist, all under `Output Files <model>/hybrid_order_reversal/` (the A_H alternative-ordering experiment: 3 control and 5 reversed runs per model). None exists for any of the 60 benchmark runs (4 models x 3 architectures x 5 runs). The ordering-experiment logs carry prompt, response, token and latency fields but no timestamp field.
- **Timestamps**: no benchmark diagnostics file has a `collected_utc` field. The current code writes one (`Architectures/Direct_LLM_Scoring.py` L559) and starts a raw log (L572), so the logging was added after the benchmark was collected.
- **File modification times cannot date the runs.** Every A_D per-run xlsx and every diagnostics JSON for all four models shows the same modification minute, 2026-07-29 16:41 local time; the A_E and A_H per-run xlsx files show 2026-08-12 18:54-18:55 (A_H) and 2026-08-13 00:31 (A_E). Those times come from bulk rewrites, not collection. Only the ordering-experiment raw logs have spread-out times (2026-08-03, 10:32 to 14:35), consistent with genuine collection that day.
- **Git commit history gives upper bounds.** Commit dates (U.S. Eastern) of the last change to the per-run xlsx files before the August re-scoring commit:
  - A_D: July 5, 2026 for all four models (commits "ran all qwen", "GPT OSS model benchmarks reran.", "ran all deepseek trials.", "ran all gemini benchmarks.").
  - A_H: July 3, 2026 (DeepSeek, GPT-OSS, Qwen) and July 4 (Gemini, "ran gemini (COST: 8.13)"); all A_H xlsx files changed again on August 13 while their diagnostics files did not, which suggests offline re-scoring of stored parameters, not new API calls.
  - A_E: July 21, 2026 for all four models ("reran all rag and recomputed all metrics"). On August 13 (commit "...Reran A_E subset to account for updated examplar..."), Gemini's A_E diagnostics for runs 1, 3, 4 and 5 gained the note "Shower scenarios were re-collected after a ground-truth comfort-band correction... Token, latency and cost fields describe the original 195-scenario collection." No other model's A_E diagnostics carry that note.

**Unresolved for you:** the Gemini A_E Shower re-collection is not disclosed anywhere in the paper or supplement I could find. It means those rows come from a later session than the rest of Gemini's A_E runs. The project's operating guide (`CLAUDE.md`) warns against exactly this: without timestamps, a difference between rows from two sessions looks the same whether the change under study caused it or the provider changed its model in between. Confirm which models and runs were re-collected on or before August 13 (the commit message says "subset"; only Gemini's diagnostics say so) before writing the S1 sentence.

### Why an EMS reviewer cares

Reviewer 3 verified the missing logs locally and asked either to ship them or correct the README and L1136, and to state collection dates in S1. EMS's software-availability section is a formal requirement, and `:exacto` routing can change over time, so dates matter for anyone re-collecting.

### Options

- **A9-a (recommended)**: correct README L73 and main L1136; add an S1 sentence giving commit-dated windows as upper bounds; disclose the Gemini A_E Shower re-collection. Before writing the dates, check OpenRouter's activity log for the account: it records per-request times and could give exact collection dates, which would replace the commit bounds.
- **A9-b**: state in S1 that collection dates are unavailable. Honest but weaker, and the commit history is public in the repository anyway.
- **A9-c**: re-collect with timestamps. Costs about $44 for every API experiment (about $12 for the main benchmark alone) and creates a new result set; not justified by this item.

### Edits (A9-a)

**A9.1, README L73 (Markdown).**
- old: `Each run also writes `*_results_diagnostics_run_NN.json` (token counts, latency, failure-type counters, UTC collection timestamp) and `*_results_run_NN_raw.jsonl` (one record per API call with the prompt, the raw model response, and per-call latency and token counts).`
- new: `Each run also writes `*_results_diagnostics_run_NN.json` (token counts, latency, failure-type counters). The current code also records a UTC collection timestamp in that file and writes `*_results_run_NN_raw.jsonl` (one record per API call with the prompt, the raw model response, and per-call latency and token counts). The shipped benchmark runs predate both: their diagnostics carry no timestamp and they have no raw logs. Raw logs ship only for the alternative-ordering experiment of LLM-parameterized reference scoring (`Output Files */hybrid_order_reversal/`), and those carry no timestamp either.`

**A9.2, main L1136.**
- old: `The repository includes the per-run outputs of every model, so every table, figure and statistical test in this paper can be regenerated without an API key.`
- new: `The repository includes the per-run outputs of every model, the scores or, for $\mathcal{A}_{\text{H}}$, the extracted parameters of every scenario and run, so every table, figure and statistical test in this paper can be regenerated from them without an API key. The benchmark runs predate our logging of raw model responses and collection timestamps, so the repository does not hold the prompts and responses behind those outputs; it holds them only for the alternative-ordering experiment (Supplementary Material S1).`
- Condition: "every ... statistical test ... can be regenerated" is only true of the corrected numbers if the pipeline scripts are updated or this pass's analysis scripts (`Analysis/pass5/`) ship with the release (A1 and A3 knock-ons). Otherwise the pipeline regenerates the superseded Set B statistics.

**A9.3, S1, new sentences after S L201** (after `We report API costs at OpenRouter's published prices as of August 1, 2026.`). Fill the bracketed part after you confirm the re-collection scope.
```latex
The benchmark runs carry no collection timestamps; we added timestamped logging after collecting them, and file modification times reflect later rewrites rather than collection. The repository's commit history bounds when each set of runs was committed (U.S. Eastern time): the $\mathcal{A}_{\text{H}}$ runs on July 3--4, 2026, the $\mathcal{A}_{\text{D}}$ runs on July 5 and the $\mathcal{A}_{\text{E}}$ runs on July 21. [After the shower comfort-band correction, we re-collected the Shower scenarios of Gemini's $\mathcal{A}_{\text{E}}$ runs 1, 3, 4 and 5; that re-collection was committed on August 13, 2026.] We re-scored the stored $\mathcal{A}_{\text{H}}$ parameters against the corrected reference without new API calls. The alternative-ordering runs were collected on August 3, 2026. A commit date bounds a collection from above; it does not date the runs within that window.
```
- If the OpenRouter log gives exact dates, replace the commit-date sentence with them.
- If you choose A9-b instead: `The benchmark runs carry no collection timestamps, and file modification times reflect later rewrites rather than collection, so we cannot state the collection dates.`

### Knock-on effects

- S L1342 ("per the main text's timestamp convention") refers to a convention that does not exist; Part B's B57 deletes the phrase.
- README L92 ("every metric, table, figure, significance test ... can be regenerated from a fresh clone") has the same condition as A9.2. No item in this file edits L92; it becomes true once the pipeline scripts are updated (see "Your actions"), so no text change is proposed.
- CLAUDE.md already records that the benchmark runs are undated; no change there.

---

## A10. Appliance super off-peak omission

### Problem

The Appliance calculator bills every time-of-use utility in two periods (peak and off-peak; S Table `tab:tou_rates`, S L743-L765). PECO bills a third, super off-peak period from midnight to 6 a.m. every day, and the three FirstEnergy utilities (West Penn, Penelec, Met-Ed) bill one from 11 p.m. to 6 a.m. every day, both at rates below off-peak (evidence: PECO's December 2025 - May 2026 TOU generation rate sheet, super off-peak 5.274 cents excluding transmission; FirstEnergy Pennsylvania Supplement No. 20, PUC document 1875621, super off-peak multipliers near 0.63). Neither the main text (L726) nor S1 mentions the omission.

### Why an EMS reviewer cares

Appliance scheduling is the decision where the paper argues cost and emissions separate because of time-of-use tariffs. A reviewer who knows the PECO or FirstEnergy tariff will see a missing rate period in the one calculator where rate periods decide the ranking.

### Evidence

Source: `paper/CALCULATOR_AUDIT.md`, Appliance section, items 3, 4 and "Combined". A scratchpad copy of the calculator reproduced `Ground Truth/ground_truth_appliance.xlsx` exactly (300 rows, 0 rank mismatches) before any change.
- Adding the super off-peak period: 1 PECO and 3 FirstEnergy reference winners change, 4 of 65 Appliance test scenarios, all dryers for which an 11 p.m. or midnight run overtakes the baseline time (Indiana, Greensburg, Gettysburg, Chester).
- With the super off-peak rates plus the corrected PPL rates: 4 of 65 winners, 4 of 65 full orderings; criterion scores change in 32 test and 18 of 35 retrieval (RAG) scenarios, but no RAG ranking changes.
- Adding PPL's winter window and the corrected city-to-utility mapping as well: at most 6 of 65 winners and 7 of 65 orderings.
- The architecture metrics were not recomputed against an adjusted reference.

### Options

- **Option A (recommended): disclose, no rerun.** One main-text sentence and one S1 paragraph.
- **Option A' (adds strength, $0):** before disclosing, re-score the stored A_D, A_E and A_H outputs and the baselines against an adjusted reference offline, so the S1 paragraph can say whether the architecture ordering and the per-model Appliance numbers hold. A_E's exemplars would still show the old scores (18 of 35 retrieval scenarios), so its re-score is approximate. This needs a scratchpad calculator copy; no shipped file changes.
- **Option B:** fix the calculator, regenerate the ground truth, sync the RAG scores, rebuild the index, re-score A_H, A_D and the baselines offline, and rerun A_E. To avoid mixing dated and undated A_E runs, rerun A_E on all 195 scenarios with timestamps: about $5.6. Every Appliance number in the paper moves. Not recommended for this pass.

### Edits (Option A)

**A10.1, main L726, one sentence inserted after** `The calculator applies weekday summer rates year-round and models no weekend, holiday, or seasonal shift in the peak window.` Part B's B40 rewords that sentence to "The calculator applies one weekday rate pair per utility year-round ..." (PECO's rates are December-May rates, so "summer" is wrong); insert this one after it in either case.
```latex
It also bills every utility in two periods, although PECO (midnight to 6\,a.m.) and the three FirstEnergy utilities (11\,p.m.\ to 6\,a.m.) offer a third, cheaper super off-peak period; adding that period changes the reference winner in 4 of the 65 Appliance test scenarios, all of them dryers (Supplementary Material S1).
```

**A10.2, S1, new paragraph after S L765** (the paragraph ending `...cuts its per-cycle cost by 49--76\% across these five time-of-use utilities.`):
```latex
The calculator omits the super off-peak period that PECO (midnight to 6\,a.m.) and the three FirstEnergy utilities (11\,p.m.\ to 6\,a.m.) bill below their off-peak rate. With those rates added, the reference winner changes in 4 of the 65 Appliance test scenarios: one PECO and three FirstEnergy households, all running a dryer, for which an 11\,p.m.\ or midnight run overtakes the baseline time. Correcting the PPL rates, PPL's winter peak window and the city-to-utility mapping as well changes at most 6 winners and 7 full rankings. No change moves a retrieval-set ranking, but the corrected rates change the criterion scores of 18 of the 35 Appliance retrieval scenarios, which $\mathcal{A}_{\text{E}}$ shows to the model as exemplars. We kept the reference and the collected runs unchanged.
```
If you take Option A', append one sentence with the re-scored result.

### Knock-on effects

- Part B covers the related text-only Appliance fixes: B38 (PECO and FirstEnergy citations), B39 ("PPL (Rate RTS)" and the 49-76% saving range), B36 (pooled percentile wording), B40 ("weekday summer rates"). A10.2 names "PPL rates" and "city-to-utility mapping" as corrections without citing sources; if you accept B38 and B39, reuse their keys here (`peco2025tou`, `fepa_supp20`, `ppl2025`).
- The Limitations paragraph (L1094) mentions Pennsylvania rate tiers; no change needed.

---

## A11. Shower (and HVAC) environmental metric wording, and the small Environmental Impact swing

### Problem

**Keep gallons.** Within a Shower scenario the three alternatives differ only in duration, so energy, cost, water and any CO2 figure are each duration x a per-scenario constant. Switching Environmental Impact to CO2 would make it an exact copy of Energy Cost for 100% of alternatives, putting 0.65 of the weight on one number; gallons at least vary 1.5x in cost per gallon across scenarios (CALCULATOR_AUDIT.md, "Environmental metric"). No text change is needed for the metric itself.

**The wording blames the wrong cause.**
- Main L614: "We evaluate all three alternatives of an HVAC or Shower scenario at a single time, so their cost and emissions move together. On a grid whose marginal emissions intensity varied independently of retail price, the two criteria would separate on every decision type; the PJM footprint studied here is not such a grid (Section~\ref{sec:limitations})."
- Main L1094: "because PJM's marginal emissions intensity does not vary independently of retail price, the four-criterion specification collapses to an effective three on HVAC and Shower, with 0.65 of the weight resting on a single cost/emissions dimension".

For Shower, Environmental Impact is water volume, which has nothing to do with PJM; cost and water co-move because both scale with duration. I also checked HVAC today (read-only, `Ground Truth/ground_truth_hvac.xlsx`): within every one of the 105 HVAC scenarios (test and RAG), raw cost and raw emissions order the three alternatives identically, because both equal the same kWh times a scenario-level constant (flat $0.19/kWh; one PJM factor for the scenario's time and occupancy). A grid whose emissions varied independently of price would not separate them either, since all three setpoints draw at the same time. Only alternatives that run at different times (Appliance) can separate cost from emissions. So "the two criteria would separate on every decision type" is false for HVAC as well as Shower.

**The small Environmental Impact swing.** S Table `tab:swing_weights` (S L775-L793) gives the mean of weight x within-scenario score range. Environmental Impact contributes 0.032 on HVAC and 0.008 on Appliance, against 0.086 and 0.098 for Comfort, despite the largest weight (0.35). In a paper motivated by emissions, emissions barely move the recommendation on two of three decision types. Reviewer 1 and the editor asked to see this discussed. The table is computed on the 285 test + RAG scenarios pooled, and its caption does not say so. Test-only values: HVAC 0.025 / 0.028 / 0.083 / 0.013 (Energy Cost / Environmental / Comfort / Practicality; CALCULATOR_AUDIT.md); Appliance 0.069 / 0.009 / 0.093 / 0.091 (weights times the test-set mean ranges 0.230 / 0.026 / 0.466 / 0.609 in `Analysis/pass5/d9_appliance_env_contrast.csv`); Shower 0.115 / 0.136 / 0.067 / 0.052 (CALCULATOR_AUDIT.md).

### Options

- **A11-a (recommended)**: fix L614 and L1094 to name the real cause; state the swing once as a finding at the end of the L614 paragraph; add "285 test and RAG scenarios" to the swing-table caption.
- **A11-b**: also switch the swing table to the 195 test scenarios (all twelve test-only values above), so it matches the rest of the paper's basis. Changes 12 numbers; the finding reads the same.

### Edits (A11-a)

**A11.1, main L614, two sentences.**
- old: `We evaluate all three alternatives of an HVAC or Shower scenario at a single time, so their cost and emissions move together. On a grid whose marginal emissions intensity varied independently of retail price, the two criteria would separate on every decision type; the PJM footprint studied here is not such a grid (Section~\ref{sec:limitations}).`
- new: `We evaluate all three alternatives of an HVAC scenario at a single time, so their cost and emissions both scale with the same energy use and move together on any grid. The three alternatives of a Shower scenario differ only in duration, and cost and water volume both scale with duration, so those two criteria move together as well. Only alternatives that draw energy at different times can separate the two criteria, which is why they separate on Appliance alone (Section~\ref{sec:limitations}).`

**A11.2, main L614, one sentence appended at the end of the same paragraph (the swing finding).**
```latex
Separating the two criteria does not make Environmental Impact decisive. Over the 285 test and RAG scenarios, its weight times its within-scenario score range averages 0.008 on Appliance and 0.032 on HVAC, against 0.098 and 0.086 for Comfort, so despite the largest weight the emissions criterion barely moves the recommendation on these two decision types; it carries the largest swing only on Shower, where it measures water (0.128; Supplementary Material S2).
```

**A11.3, main L1094.**
- old: `because PJM's marginal emissions intensity does not vary independently of retail price, the four-criterion specification collapses to an effective three on HVAC and Shower,`
- new: `because the three alternatives of an HVAC or Shower scenario share one time of use, and Shower cost and water volume both scale with duration, the four-criterion specification collapses to an effective three on HVAC and Shower,`
- The paragraph's first sentence (PJM factors and PA tariffs do not generalize to high-renewables grids) stays: it concerns absolute scores, not the collapse.

**A11.4, S L779 (swing-table caption).**
- old: `\caption{Mean within-scenario swing (nominal weight $\times$ within-scenario score range) by criterion and decision type}`
- new: `\caption{Mean within-scenario swing (nominal weight $\times$ within-scenario score range) by criterion and decision type, over the 285 test and RAG scenarios}` (identical to B55; apply once)

### Knock-on effects

- L612 ("How far the two criteria separate depends on the decision type.") leads into A11.1 and stays.
- L1101 (Future Work: "Cross-grid replication under different emissions--cost correlation structures ... would address the PJM specificity") now overstates what a different grid would show for HVAC and Shower. Optional swap: old `would address the PJM specificity noted in Section~\ref{sec:limitations}.` -> new `would address the PJM specificity noted in Section~\ref{sec:limitations} for Appliance scheduling; separating the criteria on HVAC and Shower would need alternatives that differ in when or how they draw energy.`
- Main L728 reads "Energy, cost and water volume all follow from that mixing fraction, the flow rate and the duration". Water volume depends only on flow rate and duration, but the sentence names all three inputs together, so it is loose rather than wrong. No item in Part A or Part B edits it; leave it unless you want to split the clause.
- The A4.5 S1 paragraph gives the Appliance Environmental Impact range (0.026 unweighted, test only); A11.2 gives the weighted, pooled swing (0.008). Both are correct; the bases differ, and each sentence names its own.

---

## A12. Discussion 6.1 rewrite: defer

### Problem

Section 6.1 (main L1053-L1071, 10 paragraphs, about 1,230 words) restates Results numbers; the simulated panel's editor mentioned the repetition without making it a condition. A four-claim rewrite would come to about 800 words and save about half a page.

### Recommendation

Defer until you have decided A1-A4, because they change what 6.1 must say. Sentences in 6.1 that A1-A4 already touch or qualify:

| Line | Sentence (start) | Changed by | Status |
|---|---|---|---|
| L1053 | "$\mathcal{A}_{\text{H}}$ was the strongest architecture overall and the only one whose within-scenario score spread matched..." | none | Holds |
| L1055 | "Extraction error rarely reaches the ranking, and the reason is the structure of the decision..." | A3 | Holds; states the general mechanism correctly |
| L1057 | "The cancellation depends on the alternatives sharing the same uncertain state..." | A3.1, A3.2 | Mechanism clause replaced |
| L1059 | "GPT-OSS carries 117 of the 120 $\mathcal{A}_{\text{H}}$ extraction failures..." | A1 | Holds (all HVAC, all out-of-bounds) |
| L1061 | "The architecture that ranks best is also the cheapest to run, by roughly three to eight times..." | A4, A7 | "Generally the worst option" holds once L1112 is scoped; "eight" carries the DeepSeek token anomaly |
| L1063 | "Example-guided LLM scoring corrects the level of the model's scores..." | A4 | A_D and A_E also differ in anchors (A4.3); the causal reading "exemplars narrow the numeracy gap" confounds the two |
| L1067 | "$\mathcal{A}_{\text{D}}$ fails in a way the LLM-as-judge literature does not predict..." | A4 | The no-anchors ablation shows Appliance anchors hurt DeepSeek and Qwen; the "multi-parameter interactions" explanation needs that caveat |
| L1069 | "The entropy weights come close to the assumed 35/30/20/15 weights..." | A11 (swing), B23 ("single forward pass", same paragraph) | Revisit with the swing finding. Reviewer 1 also noted that "come close" holds only for the overall entropy vector; no item edits that clause |
| L1071 | "The fixed-default baseline performs well only where its defaults happen to suit the decision..." | A2 | Needs the stated-time and lookup result (A2 knock-on sentence); "R-15, SEER-13 ... typical of the Pennsylvania housing stock" is Part B's B54 (-> "sits near the median R-value and SEER of the test scenarios") |

Once A1-A4 are applied, a rewrite should carry four claims: (1) ranking survives extraction error because errors rescale shared gaps and flip only near-ties (A3); (2) accuracy comes from the calculator plus correctly read inputs, and rules read these templated inputs as well as the LLMs (A2); (3) pointwise scoring without the value model fails, and prompt anchors can hurt (A4); (4) the cheapest architecture is the most accurate (A7 caveat on DeepSeek A_D).

---

## Files

- Evidence reports: `paper/pass5/D1_REPORT.md` (lookup), `D2_REPORT.md` (two sets of A_H numbers), `D3_REPORT.md` (GPM), `D9_D12_REPORT.md` (scope, disclosures, ensemble, regret, ties, tokens), `D13_REPORT.md` (literature); `paper/CALCULATOR_AUDIT.md` (super off-peak, Shower metric); `paper/MOCK_EMS_REVIEW.md` (review).
- Scripts and CSVs: `Analysis/pass5/` (`d1_*`, `d2_*`, `d3_*`, `d9_*`, `d12_*`); ready LaTeX tables in `Analysis/pass5/d9_d12_latex_tables.tex`.
- Number ledgers: `paper/pass5/NUMBERS_OF_RECORD.csv` and the `NUMBERS_OF_RECORD_D1_rows.csv`, `_D3_rows.csv`, `_D9_D12_rows.csv` files beside it.


---

# Pass 5 proposal, Part B: the cheap-fix batch

Written 2026-09-25. Nothing below has been applied. Every edit is a proposal in the form
old -> new, with the old string copied from the current file so a text search finds it once.
Line numbers are current as of this writing (`paper_draft_v2.tex` = main text, 1,148 lines;
`supplementary.tex` = supplement, 1,559 lines). A script checked every quoted old string
against those files; the check is described at the end.

This batch covers four sources: (1) the numeric mismatches in the simulated EMS panel's
consistency audit (`paper/MOCK_EMS_REVIEW.md`, the 20-row table), (2) the panel's list of
cheap fixes, (3) the text-only fixes from the three calculator audits
(`paper/CALCULATOR_AUDIT.md`), and (4)-(6) supplement, submission-hygiene and repository
fixes. The abstract, title, the parameter-provenance numbers, the lookup baseline, the GPM
mechanism, the scoring-scope claims, the prompt disclosures, the raw-log and availability
claims, the Appliance super off-peak omission, the Shower emissions wording, the
environmental-swing finding and the Section 6.1 rewrite belong to Part A; the table
"Handled in Part A" lists every review or audit item routed there and why.

Conventions. "Risk" means: **none** (typo, pointer or label; no claim changes), **low**
(a fact or citation corrected to match its source; wording otherwise kept), **author** (the
edit touches a claim, a rationale only the author knows, or Discussion/Conclusion wording;
the author must read it before it goes in). Numbers come from the numbers-of-record files in
`paper/pass5/` or from a read-only recomputation described in the item. Nothing here needs an
API call or a calculator change. Where an item adds a bibliography entry, the entry is given in
full; entries marked "verify" contain a field I could not confirm from files in the repository.

Terms. A_D is direct LLM scoring, A_E example-guided LLM scoring (one retrieved, reference-scored
exemplar in the prompt; k is the number of exemplars retrieved) and A_H LLM-parameterized
reference scoring (the LLM extracts engineering parameters and the reference calculators score).
The reference is the MAVT (multi-attribute value theory) ranking the three calculators produce
from each scenario's true values. Kendall's tau (tau) and Top-1 (share of scenarios whose
top-ranked alternative is the reference winner) measure agreement with it. The fixed default is
the no-LLM baseline that feeds the calculators one constant per withheld parameter. The test set
is the 195 benchmark scenarios; the RAG set is the disjoint 90-scenario retrieval corpus; 285
counts both. GPM is shower flow rate in gallons per minute; TOU means time-of-use; PTC is a
utility's price to compare; HSP is the Building America House Simulation Protocols; PJM is the
regional grid whose marginal emissions factors the calculators use. "main:N", "supp:N",
"README:N", "bib:N" and "calc:N" are line numbers in `paper/paper_draft_v2.tex`,
`paper/supplementary.tex`, `README.md`, `paper/cas-refs.bib` and the named calculator file.
"Table S2.8" and similar labels are the supplement's current compiled numbering, listed in full
in B25. The "numbers of record" are each metric computed per model and per run, then averaged
over runs (`paper/pass5/NUMBERS_OF_RECORD.csv`).

Provenance tags. The parenthesis after each item's risk records where the item came from; it
never replaces the item's evidence. "Review audit row N" is row N of the simulated panel's
20-row numerical consistency table and "cheap-fix N" is item N of its cheap-fix list (both in
`paper/MOCK_EMS_REVIEW.md`, 2026-09-24). "Handling editor", "R1" to "R4" and "major"/"minor"
name the panel member and the point: R1 environmental modelling and MCDA, R2 LLM and ML
evaluation, R3 reproducibility and software, R4 devil's advocate. "HVAC/Appliance/Shower audit
item N" is item N of that calculator's section in `paper/CALCULATOR_AUDIT.md`.

---

## Summary table

| Item | File:line | One-line fix | Risk |
|---|---|---|---|
| **Group 1: number mismatches** | | | |
| B1 | main:1000; supp:935 | State that DeepSeek's 0.32 loss at k=1 is the paired difference (unpaired figure means differ by 0.307) | low |
| B2 | supp:930 | "narrowest ordering margin ... 0.13" is false (0.010); restate the argument | author |
| B3 | main:998 | "no perturbation improved on the original prompt" holds for tau only | low |
| B4 | main:996; README:152 | "changed no model's top-ranked alternative" -> "did not detectably change" | low |
| B5 | main:1077 | "low-variance scores" -> stable aggregate metrics (scenario choices are not stable) | low |
| B6 | supp:903 | Say the alpha sweep uses one alpha for both criteria and a linear function at alpha=1.0 | none |
| B7 | main:1012; README:442 | "The MEREC vectors load onto Comfort" holds for the HVAC vector only | low |
| B8 | main:612, 1012; README:441-442 | "all 20 cells" under "alternative" vectors: 16 alternative cells | none |
| B9 | main:761, 1000 | "seven configurations" means two different sets | none |
| B10 | main:610 | alpha "adjusted only to keep values inside the 0--1 range" cannot be the reason | author |
| B11 | main:341 | 19.2 quads is residential *total* energy, not delivered (verify against MER) | author |
| B12 | main:523 | Table 2 codes HVAC setpoint alternatives "---" for LLMs; Shower codes them "A" | none |
| B13 | main:496 | Withheld-parameter list omits HVAC age, tank size, setpoint, and the free-text Appliance fields | low |
| B14 | main:519-521, 574 | Table 2 says the calculator uses house age; it uses HVAC age, which is missing from the table | low |
| **Group 2: panel's cheap-fix list** | | | |
| B15 | main:740 | State k=1 in Section 4.4 and that the ablation control is k=3 | none |
| B16 | main:1048 | "comes close on two of the three decision types" -> matches or beats A_H for two of four models | author |
| B17 | main:1116 | Recast the A_E-exemplar recommendation as an untested route | author |
| B18 | main:322-328 | Reframe RQ1 as a design proposition | author |
| B19 | main:1083 | Goodell et al. argued about convergence among clinical groups, not about agreement with this study | low |
| B20 | main:1077 | Neither cited paper predicts compressed scores | author |
| B21 | main:606 | Attari measured energy misperception, not that cost is "the criterion households estimate worst" | low |
| B22 | main:369 | zadeh1965 introduced fuzzy sets, not fuzzy AHP/TOPSIS numbers | low |
| B23 | main:1069 | "single forward pass" is false for the two reasoning models | low |
| B24 | main:734; supp:201 | Report temperature, top-p, max tokens, seed, DeepSeek reasoning off | none |
| B25 | main: 33 places | Cite supplement tables by number (Table S2.x) | none |
| **Group 3: calculator-audit text fixes** | | | |
| B26 | main:672; README:392; bib | EER formula source is Building America HSP (Hendron & Engebrecht 2010), not AHRI 210/240 | low |
| B27 | main:696 | Disclose heating = electric heat pump at the SEER-derived cooling EER | low |
| B28 | main:1088 | One limitation sentence: flat HVAC tariff vs Appliance TOU, wall R on whole envelope, PJM peak on every day | low |
| B29 | main:670 | Disclose the budget-penalty jump at u=1.5 and that no scenario reaches it | low |
| B30 | main:696 | Internal gains, solar gain and glazing fraction: label sources and assumptions | low |
| B31 | main:696; supp:576 | Envelope multipliers are our values, not a Manual J table | low |
| B32 | main:698 | 70 F heating optimum is our choice (HSP gives 71 F) | author |
| B33 | main:703 | Disclose the three inconsistent heating/cooling tests (1 of 70 winners) | low |
| B34 | main:722 | State that maintenance is "moderate" (1%/yr) for every scenario | none |
| B35 | main:624 | Bounds are 5th-95th percentiles of the 285 test+RAG scenarios; HVAC env bounds are derived | low |
| B36 | main:726 | Appliance "realized ... spans" are pooled percentiles; drop the ENERGY STAR cite there | low |
| B37 | main:728 | Shower "realized ... spans" are pooled percentiles; keep its three cites on the source facts | low |
| B38 | main:726; supp:765; bib | PECO rates and FirstEnergy multipliers cite the wrong documents | low |
| B39 | supp:765; main:726 | "PPL (Rate RTS)" mislabel; PPL rates do not match the cited GSC-1 tariff (disclose) | author |
| B40 | main:726 | "weekday summer rates": PECO's are December-May rates | none |
| B41 | main:726 | "appliance-specific tolerance ceilings" overstates what Paetz supports | low |
| B42 | bib:222 | paetz2012 has the wrong co-authors | none |
| B43 | supp:572 | kWh/cycle is not "drawn from the ENERGY STAR certified-products database"; rho values are pooled | low |
| B44 | supp:759 | Duquesne flat rate listed with a "2--9pm" window | none |
| B45 | main:608; supp:926 | CDC: 120 F is the circulation floor; the storage threshold is 140 F | low |
| B46 | main:728; bib | Season-dependent shower optimum is not in REU2016 (Ibanez-Rueda 2023; elasticity is ours) | low |
| B47 | main:728, 1088 | Mains temperature is our linear approximation, not Burch's model; drop zhang2023 | low |
| B48 | main:728 | 105 F delivery target is our convention; practicality curve is hand-set, not "calibrated" | low |
| B49 | main:608 | Tank availability (about 40 gal) is an assumption | none |
| B50 | main:620 | Pointer to Appliance/Shower "full derivations" in S1 that do not exist | none |
| B51 | supp:574 | Flow-tier text (2.5-3.0) differs from the code band (2.0-3.0]; 11 of 80 scenarios exceed the federal maximum | low |
| B52 | supp:565 | Disclose the hvac_age = 95 scenario | none |
| B53 | supp:570 | SEER 16-22 is the ordinary ENERGY STAR level, not "Most Efficient"; wall R tiers are ours | low |
| B54 | main:1071 | "typical of the Pennsylvania housing stock" -> scenario-set medians | low |
| B55 | supp:779 | Swing table is computed over the 285-scenario corpus | none |
| **Group 4: supplement** | | | |
| B56 | supp:1246 | DeepSeek's reasoning-scaffold drop explained with GPT-OSS's success rate | low |
| B57 | supp:1342-1343 | Dangling "per the main text's timestamp convention" | none |
| B58 | supp:142 | Alpha-sweep figure overfull by 2.2 pt | none |
| B59 | supp:655 | Hyperref bookmark warning on "Worked Example" | none |
| B60 | supp:930 | Disclose that both ablations compute tau_b on scores without the tie-break (coordinate with A4.8) | author |
| B61 | supp:201, 973 + tables | Optional: fix the other overfull boxes (published as supplied) | none |
| **Group 5: submission hygiene** | | | |
| B62 | main:22-23, 30-31, 349 | Remove co-author TODO comments and `todonotes` | none |
| B63 | supp:177, 1556 | Harmonize citation style with the main text | author |
| B64 | main:346; bib | PA emissions caption has no data source | low |
| B65 | bib | 14 uncited entries (harmless; optional tidy) | none |
| B66 | bib:456, 474 | BibTeX "empty pages" warnings | none |
| B67 | main:87-178, 242-277 | Optional: delete two unused plot macros from the main preamble | none |
| **Group 6: repository** | | | |
| B68 | README:3-5, 513-515 | One author listed; paper and CITATION.cff list two | none |
| B69 | README:33 | `git clone <repository-url>` placeholder | none |
| B70 | README:327 | R-11/13/19 contradicts the supplement tiers | none |
| B71 | README:329 | "true age in years -> kWh/cycle" is wrong | none |
| B72 | README:345, 392, 404, 416 | Range heading, EER source, mains model, heater efficiency | low |
| B73 | README:444, 450 | "Three ablation suites" lists four; CLAUDE.md pointer | none |
| B74 | README:12 | README research question differs from the paper's RQs | author |
| B75 | requirements.txt | Add matplotlib; pin torch | none |
| B76 | three calculators | Code comments that credit the wrong source | none |
| B77 | CLAUDE.md:66 | R-11/13/19 (author's file; needs approval) | author |
| B78 | paper/PAPER_STATUS.md | Stale section 1 and section 6 | none |

Counts: Group 1 = 14, Group 2 = 11, Group 3 = 30, Group 4 = 6, Group 5 = 6, Group 6 = 11
(78 items). Items marked **author**: B2, B10, B11, B16, B17, B18, B20, B32, B39, B60, B63,
B74, B77 (13). Already fixed or verified correct: 7 (section at the end).

---

## Handled in Part A

| Review or audit item | Why it is Part A's |
|---|---|
| Audit rows 1-2: provenance table tau 0.921/0.897/0.904/0.921 and "194 of 195" vs main A_H results | A1 (the two sets of A_H numbers) |
| Audit row 3 / cheap-fix 1: main:909 "most of them on HVAC" vs supp:704 "All of its A_H failures were HVAC" | A1.8 (GPT-OSS failures wording; numbers of record: all 117 are HVAC) |
| Audit row 6 / cheap-fix 4: prompt-ablation control is not the main benchmark | A4.6 and A4.8 (no-anchors ablation and its control mismatch). A4.8 already names the third reason, tau_b on scores without the tie-break; B60 extends it to the RAG ablation |
| Audit row 18 / cheap-fix 14 (third part): define "success-weighted" | A1.9 ("success-weighted" 84.7%) |
| Cheap-fix 19: A_E prompt drops A_D's anchors; Appliance "dirtiest at peak" anchor vs 6.2% contrast | A4.3-A4.5 (prompt disclosures) |
| Cheap-fix 22: abstract/conclusion scope, "in any domain with a validated modeling calculator", "physics-based" | A5 (abstract, title, "physics-based"; A5's scope swaps include README:18 "physics-based") |
| Cheap-fix 23: rescope "LLMs should not score" (main:304, 1112) | A4.2 and A5 (rescoping) |
| Cheap-fix 27: small environmental swing on HVAC and Appliance | A11.2 (environmental-criterion swing finding); B55 and A11.4 give the same caption fix |
| Cheap-fix 32: Zenodo DOI, EMS hardware and program-size fields | Not a text edit in either part: listed under "Your actions", Before submission (A9 corrects the availability statement's logging claim) |
| Panel "real issue" 1 (lookup baseline), 3 (GPM mechanism; README:144, 149), 4 (raw logs; README:73, main:1136), 5 (ensembling, regret, ties/input order, tokens), 6 (literature; main:320 "single correct value") | A2 (lookup), A3 (GPM), A9 (raw logs), A7 and A6 (ensembling, regret, tokens; ties and input order), A8 (literature) |
| Appliance super off-peak omission (PECO midnight-6 am, FirstEnergy 11 pm-6 am) | A10 |
| Shower gallons vs CO2; main:614 "cost and emissions move together" and main:1094 PJM blame for the Shower collapse | A11. B37 edits only the second clause of main:728; no item edits the first clause ("Energy, cost and water volume all follow from that mixing fraction, the flow rate and the duration"), which is loose but not wrong (A11 knock-ons) |
| Section 6.1 rewrite | A12 (deferred). B23 and B54 are one-phrase fixes inside Section 6.1; drop them if the A12 rewrite replaces those sentences |

---

## Group 1: number mismatches from the panel's consistency audit

### B1. DeepSeek's k=1 loss: say which difference "0.32" is

- **Where:** `paper/paper_draft_v2.tex:1000`; `paper/supplementary.tex:935`.
- **Problem:** Both files say retrieving one exemplar instead of three "costs DeepSeek $0.32$ in
  $\tau$" (main) and "DeepSeek lost 0.32 in Kendall's $\tau$ at $k=1$" (supplement). The
  main-text figure `\plotRagAblation` (main:200, 202) and Table S2.5 (supp:950, 952) show
  DeepSeek at 0.489 (k=3 control) and 0.182 (k=1): a difference of 0.307, which rounds to 0.31.
  `Analysis/RAG_Ablation/k1_vs_k3_bootstrap_ci.xlsx` explains the gap: the 0.32 is the mean
  *paired* difference, $-0.3157$, over the 89 scenarios both configurations scored (one
  scenario failed), with 95% percentile interval $[-0.471, -0.160]$, the interval supp:935
  already quotes. The figure shows unpaired means over all scored scenarios.
- **Why it matters:** a reader who subtracts the plotted bars gets 0.31 and sees a mismatch.
- **Options:** (a) keep 0.32 and name the basis (recommended: it matches the quoted
  interval); (b) change to 0.31 and drop the interval. One edit per file.
- **Edits:**

```old paper/paper_draft_v2.tex
but costs DeepSeek $0.32$ in $\tau$.
```
```new
but costs DeepSeek $0.32$ in $\tau$ (paired difference over the 89 scenarios both configurations scored; the unpaired means in Figure~\ref{fig:rag_ablation} differ by 0.31).
```
```old paper/supplementary.tex
while DeepSeek lost 0.32 in Kendall's $\tau$ at $k=1$.
```
```new
while DeepSeek lost 0.32 in Kendall's $\tau$ at $k=1$ (paired difference over the 89 scenarios both configurations scored; the unpaired means in Table~\ref{tab:rag_ablation_full} differ by 0.307).
```
- **Knock-on:** none elsewhere; README does not quote the figure.
- **Risk:** low. (review audit row 4; cheap-fix 2)

### B2. "The narrowest ordering margin either suite resolves is 0.13" is false

- **Where:** `paper/supplementary.tex:930`.
- **Problem:** The sentence reads: "Both ablation suites test whether a configuration preserves
  the architecture ordering, and the narrowest ordering margin either suite resolves is 0.13 in
  Kendall's $\tau$, so a correction that moves no test reference winner cannot reverse either
  suite's conclusions." Two parts are wrong.
  1. In the prompt ablation (Table S2.8, supp:1213-1220), the smallest gap between a model's
     lowest $\mathcal{A}_{\text{E}}$ variant and its highest $\mathcal{A}_{\text{D}}$ variant is
     0.010 for Qwen ($\mathcal{A}_{\text{E}}$ scale_0_10 0.102 vs $\mathcal{A}_{\text{D}}$
     cot_scaffold 0.092) and 0.013 for DeepSeek (0.180 vs 0.167). Gemini's is 0.033 and
     GPT-OSS's 0.101.
  2. The RAG ablation compares retrieval configurations of $\mathcal{A}_{\text{E}}$ only; it
     does not test the architecture ordering.
  The conclusion can still be defended on a different ground. The prompt ablation runs on the
  test scenarios, and supp:928 says the band correction changes no test reference ranking, so
  every per-scenario $\tau$ and Top-1 against the reference is identical under either band. One
  caveat stays: the exemplars $\mathcal{A}_{\text{E}}$ saw in both suites carried the earlier
  Shower comfort scores.
- **Why it matters:** a reviewer who reads Table S2.8 finds the stated margin wrong by a factor
  of 13, in the paragraph that argues the ablations need no re-collection.
- **Options:** (a) replace the number and the argument (recommended); (b) replace only the
  number, which leaves an argument a 0.010 margin does not support.
- **Edit:**

```old paper/supplementary.tex
Both ablation suites test whether a configuration preserves the architecture ordering, and the narrowest ordering margin either suite resolves is 0.13 in Kendall's $\tau$, so a correction that moves no test reference winner cannot reverse either suite's conclusions.
```
```new
The prompt ablation tests whether a variant preserves the architecture ordering, and its narrowest ordering margin is 0.010 in Kendall's $\tau$ (Qwen; 0.013 for DeepSeek). It runs on the test scenarios, where the correction changes no reference ranking, so its $\tau$ and Top-1 values are the same under either band. The RAG ablation compares retrieval configurations rather than architectures and runs on the RAG set, where the correction changes 2 of the 20 Shower rankings. In both suites, the exemplars shown to $\mathcal{A}_{\text{E}}$ carried the earlier Shower comfort scores.
```
- **Knock-on:** none.
- **Risk:** author (restates the reason the ablations were not re-collected). (review audit
  row 5; cheap-fix 3)

### B3. "No perturbation improved on the original prompt" holds for tau only

- **Where:** `paper/paper_draft_v2.tex:998`.
- **Problem:** "Under $\mathcal{A}_{\text{E}}$, no perturbation improved on the original
  prompt." Table S2.8 (supp:1229) shows GPT-OSS $\mathcal{A}_{\text{E}}$ Top-1 at 0.489 under
  scale_0_10 against 0.454 for the control, bolded as the best variant. The claim holds for
  Kendall's $\tau$ (the control is best for all four models).
- **Why it matters:** the supplement's own bold cell contradicts the sentence.
- **Options:** one; name the metric and the exception.
- **Edit:**

```old paper/paper_draft_v2.tex
Under $\mathcal{A}_{\text{E}}$, no perturbation improved on the original prompt.
```
```new
Under $\mathcal{A}_{\text{E}}$, no perturbation improved on the original prompt's Kendall's $\tau$, and one raised Top-1 (GPT-OSS under the rescaled response, 48.9\% against 45.4\%).
```
- **Knock-on:** A4.6 edits the same paragraph (a control-mismatch clause and an appended
  by-type sentence); the two edits touch different sentences.
- **Risk:** low. (review audit row 7; cheap-fix 5)

### B4. "Changed no model's top-ranked alternative" overstates a null result

- **Where:** `paper/paper_draft_v2.tex:996`; `README.md:152`.
- **Problem:** main:996 says order reversal "changed no model's top-ranked alternative";
  README:152 says it "never changed which alternative any model ranked first". The test behind
  both (supp:1337) reports "No model separated on the top-1 alternative ($p \geq 0.24$)": a
  non-significant difference, not zero change.
- **Why it matters:** reviewers read "no change" as an observed zero.
- **Options:** one.
- **Edits:**

```old paper/paper_draft_v2.tex
but changed no model's top-ranked alternative, and the two conditions differ
```
```new
but did not detectably change any model's top-ranked alternative ($p \geq 0.24$), and the two conditions differ
```
```old README.md
but never changed which alternative any model ranked first
```
```new
but did not detectably change which alternative any model ranked first (p >= 0.24)
```
- **Knock-on:** the next main-text sentence ("The calculator's error cancellation absorbs the
  perturbation before it reaches the ranking.") stays; it is an interpretation, and A3 leaves
  it unchanged.
- **Risk:** low. (review audit row 8; cheap-fix 6)

### B5. "Low-variance scores": the aggregates are stable, the scenario choices are not

- **Where:** `paper/paper_draft_v2.tex:1077`.
- **Problem:** "in our case $\mathcal{A}_{\text{D}}$, across multiple runs, had low-variance
  scores while still being far from correct". The run-to-run standard deviation of
  $\mathcal{A}_{\text{D}}$'s $\tau$ is small (0.014 Gemini, 0.041 DeepSeek, 0.045 GPT-OSS,
  0.039 Qwen; Table S2.16), but the ordering ablation shows the scenario-level choices move a
  lot: original and reversed orders pick the same alternative in only 48-75% of scenarios
  (Table S2.12, "Top-1 agreement" 0.482-0.748), which supp:1374 calls "run-to-run instability".
- **Why it matters:** the sentence says the scores are stable; the supplement says they are
  not.
- **Options:** one; say what is stable.
- **Edit:**

```old paper/paper_draft_v2.tex
had low-variance scores while still being far from correct
```
```new
had stable aggregate accuracy (run-to-run standard deviation of $\tau$ at most 0.045) while still being far from correct
```
- **Knock-on:** B20 edits the next-but-one sentence of the same paragraph.
- **Risk:** low. (review audit row 9; cheap-fix 7)

### B6. The alpha sweep never reproduces the design curvature pair

- **Where:** `paper/supplementary.tex:903` (protocol paragraph, supp:898-912).
- **Problem:** The sweep applies one $\alpha$ to Comfort and Practicality together
  (`Miscellaneous Scripts/validation/SensitivityAnalysis.py`, `_sweep_gt_scores`, lines 476-495).
  The design uses 1.5 for Comfort and 1.2 for Practicality, so no sweep point is the design:
  at $\alpha = 1.5$ the figure shows Gemini $\mathcal{A}_{\text{H}}$ 0.9268 and DeepSeek
  $\mathcal{A}_{\text{E}}$ 0.3087 (supp:161-169), against the design's 0.923 and 0.307
  (Table S2.3). The script also replaces the logarithmic function with the linear one at
  $\alpha = 1.0$ (`_log_value_function`, lines 451-460), while the paragraph says every point
  goes "through the logarithmic value function at that $\alpha$".
- **Why it matters:** a reader who compares the $\alpha=1.5$ point with the design value finds
  two numbers for one configuration.
- **Options:** one; add two sentences.
- **Edit:**

```old paper/supplementary.tex
Impact, which use the linear value function, do not change with $\alpha$.
```
```new
Impact, which use the linear value function, do not change with $\alpha$.
Each sweep point applies the same $\alpha$ to Comfort and Practicality, so no point
reproduces the design pair (1.5 for Comfort, 1.2 for Practicality), whose values are the
Design row of Table~\ref{tab:sensitivity_by_model}. At $\alpha = 1.0$ the sweep uses the
linear value function.
```
- **Knock-on:** main:765 ("We sweep the logarithmic shape parameter $\alpha$ over
  $\{1.0,\,1.2,\,1.5,\,2.0\}$") stays true enough; no change needed.
- **Risk:** none. (review audit row 10; cheap-fix 8)

### B7. "The MEREC vectors load onto Comfort" holds for the HVAC vector only

- **Where:** `paper/paper_draft_v2.tex:1012`; `README.md:442`.
- **Problem:** main:1012: "The MEREC vectors load onto Comfort, the one criterion that
  $\mathcal{A}_{\text{D}}$ estimates about as well as $\mathcal{A}_{\text{E}}$." Table S2.2
  (supp:816-819): MEREC HVAC puts 0.663 on Comfort and MEREC overall 0.404, but MEREC Appliance
  puts its largest weight on Practicality (0.456) and MEREC Shower is spread (0.251 / 0.245 /
  0.203 / 0.300). README:442 repeats the claim in general form ("MEREC weights -- which load
  heavily onto Comfort (0.663 for HVAC ...)").
- **Why it matters:** the per-type MEREC vector, the one the sensitivity table uses, does not
  load onto Comfort for two of three decision types.
- **Options:** one; name the HVAC vector.
- **Edits:**

```old paper/paper_draft_v2.tex
The MEREC vectors load onto Comfort, the one criterion that $\mathcal{A}_{\text{D}}$ estimates about as well as $\mathcal{A}_{\text{E}}$.
```
```new
The MEREC HVAC vector loads onto Comfort ($0.663$ against the design's $0.200$), the one criterion that $\mathcal{A}_{\text{D}}$ estimates about as well as $\mathcal{A}_{\text{E}}$.
```
```old README.md
MEREC weights -- which load heavily onto Comfort (0.663 for HVAC against the design's 0.200) rather than cost and emissions -- narrow the gap
```
```new
MEREC weights -- which on HVAC load heavily onto Comfort (0.663 against the design's 0.200) rather than cost and emissions -- narrow the gap
```
- **Knock-on:** main:1069 (Section 6.1) says MEREC weights "emphasize the criteria that
  distinguish the alternatives at hand", which is accurate; leave it.
- **Risk:** low. (review audit row 11; cheap-fix 9)

### B8. "All 20 cells" under "the alternative weight vectors"

- **Where:** `paper/paper_draft_v2.tex:612` and `:1012`; `README.md:441-442`.
- **Problem:** main:1012: "Under the alternative weight vectors, $\mathcal{A}_{\text{H}}$ stays
  ahead of $\mathcal{A}_{\text{E}}$ in all 20 model--weight-vector cells". Table S2.3 has five
  vectors (design, equal, entropy, MEREC per-type, MEREC HVAC) times four models = 20 cells, of
  which 16 use an alternative vector. main:612 has the same "all 20" after "Moving weight off
  these two criteria". The "at least 0.304" margin comes from an alternative cell (Gemini, MEREC
  per-type: 0.929 - 0.625), so it stays.
- **Why it matters:** the count mixes the design vector into "alternative" vectors.
- **Options:** one; say 16.
- **Edits:**

```old paper/paper_draft_v2.tex
ahead of example-guided LLM scoring in all 20 model--weight-vector cells (Section~\ref{sec:res-sensitivity})
```
```new
ahead of example-guided LLM scoring in all 16 cells that pair a model with an alternative weight vector (Section~\ref{sec:res-sensitivity})
```
```old paper/paper_draft_v2.tex
in all 20 model--weight-vector cells, by at least $0.304$ in Kendall's $\tau$.
```
```new
in all 16 model--weight-vector cells, by at least $0.304$ in Kendall's $\tau$.
```
```old README.md
it holds in all 20 model x weight-vector cells tested
```
```new
it holds in all 16 model x alternative-weight-vector cells tested (20 with the design vector)
```
```old README.md
reverse it for Gemini in one of the 20 cells
```
```new
reverse it for Gemini in one of the 16 alternative-vector cells
```
- **Knock-on:** none in the supplement (supp:836 says "the one cell", no count).
- **Risk:** none. (review audit row 12; cheap-fix 10)

### B9. "Seven configurations" means two different sets

- **Where:** `paper/paper_draft_v2.tex:761` and `:1000`.
- **Problem:** main:761 says the RAG ablation "compared seven configurations with a $k=3$
  control" and then lists seven items, one of which is the offline copy-only configuration.
  main:1000 says "for GPT-OSS and Qwen the seven configurations are indistinguishable", and
  supp:973 and supp:978 count "7 configurations" / "seven LLM configurations" as the control
  plus six LLM variants (7,560 calls = 4 x 7 x 90 x 3). The figure (main:185) shows six variants
  plus the control and omits copy-only.
- **Why it matters:** "seven" names eight things in one place and seven in another.
- **Options:** one; fix main:761 and make main:1000 explicit.
- **Edits:**

```old paper/paper_draft_v2.tex
and compared seven configurations with a $k=3$ control:
```
```new
and compared six LLM configurations and one offline configuration with a $k=3$ control:
```
```old paper/paper_draft_v2.tex
for GPT-OSS and Qwen the seven configurations are indistinguishable after Holm correction.
```
```new
for GPT-OSS and Qwen the seven LLM configurations, control included, are indistinguishable after Holm correction.
```
- **Knock-on:** none.
- **Risk:** none. (review audit row 13; cheap-fix 11)

### B10. The stated reason for the alpha values cannot be the real one

- **Where:** `paper/paper_draft_v2.tex:610`.
- **Problem:** "We set $\alpha = 1.5$ for Comfort and $\alpha = 1.2$ for Practicality a priori to
  introduce mild concavity, adjusting them only to keep values inside the 0--1 range". Eq. 4
  (main:450), $\ln(1+\alpha\tilde{x})/\ln(1+\alpha)$, maps $[0,1]$ onto $[0,1]$ for every
  $\alpha > 0$, so no choice of $\alpha$ can push a value outside that range.
- **Why it matters:** a reviewer can check this in one line and will ask what the reason was.
- **Options:** (a) delete the clause (recommended if the values were simply chosen);
  (b) replace it with the real reason, which only the author knows.
- **Edit (option a):**

```old paper/paper_draft_v2.tex
a priori to introduce mild concavity, adjusting them only to keep values inside the 0--1 range; we neither elicited nor fitted either value.
```
```new
a priori to introduce mild concavity; we neither elicited nor fitted either value.
```
- **Knock-on:** none.
- **Risk:** author. (review audit row 14; cheap-fix 12)

### B11. "19.2 quadrillion BTU ... of delivered energy" is likely total energy

- **Where:** `paper/paper_draft_v2.tex:341`.
- **Problem:** "the residential sector consumed 19.2 quadrillion BTU (5,627 TWh) of delivered
  energy in 2025 \cite{eia_mer2026}". In EIA's Monthly Energy Review (Table 2.1), residential
  consumption near 19-21 quads is the *total* that includes electrical system energy losses;
  delivered (end-use) residential energy is about 11-12 quads. The conversion 19.2 quads = 5,627
  TWh is arithmetically right (19.2e15 / 3,412 BTU per kWh). I could not open the August 2026
  MER from the repository.
- **Why it matters:** "delivered" understates by nothing but mislabels the quantity; an EMS
  energy reviewer will know the two MER columns.
- **Options:** (a) if the 19.2 figure is the MER "total" column, change one word (recommended
  after checking); (b) if it is the end-use column, keep the word and the item closes.
- **Edit (option a):**

```old paper/paper_draft_v2.tex
of delivered energy in 2025
```
```new
of total energy, including electrical system losses, in 2025
```
- **Knock-on:** none.
- **Risk:** author (verify against MER Table 2.1 before applying). (review audit row 15;
  cheap-fix 13)

### B12. Table 2 codes the HVAC setpoint alternatives as unseen by the LLMs

- **Where:** `paper/paper_draft_v2.tex:523` (Table 2, `tab:parameter_comparison`).
- **Problem:** The HVAC column lists "Indoor Temp (alt.) & --- & \checkmark", meaning the LLMs
  do not receive it. Every architecture receives the three setpoint alternatives (Table S1.2
  lists "Alternatives: 58--85 F, Off" under "Shown to every architecture"). The Shower column
  codes the same kind of field, "Duration (min) & A", with the table note "A = inferred from
  alternative".
- **Why it matters:** the table contradicts the prompts in S1 and its own Shower coding.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
Indoor Temp (alt.)  & ---        & \checkmark \\
```
```new
Indoor Temp (alt.)  & A          & \checkmark \\
```
- **Knock-on:** the Appliance column has no row for its alternatives (clock times); optional to
  add "Run Time (alt.) & A & \checkmark". Not proposed, to keep the table height.
- **Risk:** none. (review audit row 16; cheap-fix 14, first part)

### B13. The withheld-parameter list at main:496 is incomplete

- **Where:** `paper/paper_draft_v2.tex:496`.
- **Problem:** "we withhold each scenario's exact engineering parameters (R-value, SEER, GPM, kWh
  per cycle and occupancy flags)". Table S1.2 (supp:548-558) lists ten withheld fields: R-value,
  SEER, HVAC equipment age, occupancy context; appliance type, kWh per cycle, baseline run time;
  GPM, tank size, heater setpoint. Table 2 marks appliance type and baseline run time "T =
  free-text input": the question states them in words, and no structured field carries them.
- **Why it matters:** the list is the reader's definition of what $\mathcal{A}_{\text{H}}$
  estimates; it omits five of the ten.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
(R-value, SEER, GPM, kWh per cycle and occupancy flags)
```
```new
(R-value, SEER, HVAC equipment age and occupancy context for HVAC; kWh per cycle for Appliance, whose type and baseline run time appear only in the question's free text; GPM, tank size and heater setpoint for Shower)
```
- **Knock-on:** B14 adds HVAC age to Table 2.
- **Risk:** low. (review audit row 17; cheap-fix 14, second part)

### B14. Table 2 says the calculator uses house age; it uses HVAC age

- **Where:** `paper/paper_draft_v2.tex:519`, `:521`, `:574`.
- **Problem:** Row "House Age$^{b}$ & \checkmark & \checkmark" and footnote b: "LLMs receive a
  building-age range label (e.g., ``20+ Years''); the calculator uses exact HVAC age." The HVAC
  calculator never reads `house_age`; it reads `hvac_age`, a separate withheld field
  (Table S1.2). The footnote's example label does not exist: `sentinel_utils.house_age_to_band_label`
  produces "1-5 years", "6-10 years", ..., "21-30 years". HVAC age has no row of its own.
- **Why it matters:** the table conflates two fields, and the review flagged it.
- **Options:** one.
- **Edits:**

```old paper/paper_draft_v2.tex
House Age$^{b}$     & \checkmark & \checkmark \\
```
```new
House Age$^{b}$     & \checkmark & ---        \\
```
```old paper/paper_draft_v2.tex
SEER Rating         & ---        & \checkmark \\
```
```new
SEER Rating         & ---        & \checkmark \\
HVAC Age            & ---        & \checkmark \\
```
```old paper/paper_draft_v2.tex
$^{b}$LLMs receive a building-age range label (e.g., ``20+ Years''); the calculator uses exact HVAC age.
```
```new
$^{b}$LLMs receive a building-age range label (e.g., ``21--30 years''); the calculator does not use house age but uses the exact HVAC equipment age, which the LLMs do not receive.
```
- **Knock-on:** the HVAC minipage gains one row; the three minipages use separate
  `\arraystretch` values to align, so check the table's bottom rules line up after compiling.
- **Risk:** low. (HVAC calculator audit item 15; review R1 minor)

---

## Group 2: the panel's cheap-fix list

### B15. State k = 1 in Section 4.4

- **Where:** `paper/paper_draft_v2.tex:740`.
- **Problem:** The benchmark retrieves one exemplar ($k=1$); the main text never says so. Only
  supp:493 and supp:935 do, and the RAG ablation's control, which main:761 and the figure call
  "$k=3$", retrieves three. A reader of the main text cannot tell that the ablation control is
  not the benchmark configuration, or that DeepSeek's measured loss at $k=1$ (B1) applies to the
  benchmark.
- **Why it matters:** k is the one design parameter of $\mathcal{A}_{\text{E}}$.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
We chose the retrieval count from the ablation described in Section~\ref{sec:ablation-design}.
```
```new
We retrieve one worked example per scenario ($k=1$), a count we chose from the ablation described in Section~\ref{sec:ablation-design}, whose control condition retrieves three.
```
- **Knock-on:** the last sentence of main:740 lists "the number of retrieved examples" among
  S1 contents; leave it.
- **Risk:** none. (cheap-fix 18; review R2 major 4)

### B16. "Comes close on two of the three decision types"

- **Where:** `paper/paper_draft_v2.tex:1048` (Discussion preamble, before Section 6.1).
- **Problem:** "Third, a calculator driven by fixed constants, with no LLM at all, already comes
  close on two of the three decision types". Per the numbers of record, the fixed default
  ($\tau$ 0.933 HVAC, 0.800 Shower) beats $\mathcal{A}_{\text{H}}$ for DeepSeek (0.920) and Qwen
  (0.881) on HVAC and for DeepSeek and GPT-OSS (both 0.787) on Shower; main:1071 already says
  $\mathcal{A}_{\text{H}}$ "clears the default for only two of the four models each".
- **Why it matters:** "comes close" understates the paper's own result.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
already comes close on two of the three decision types, which limits how much the language model can contribute.
```
```new
already matches or beats LLM-parameterized reference scoring for two of the four models on two of the three decision types (HVAC and Shower), which limits how much the language model can contribute.
```
- **Knock-on:** A2.7 rewrites the same sentence and includes this swap; if you accept A2, apply
  A2.7 and skip B16.
- **Risk:** author (Discussion framing). (cheap-fix 25; review R1 minor, R4)

### B17. The A_E-exemplar recommendation after A_E loses to constants

- **Where:** `paper/paper_draft_v2.tex:1116` (Conclusion, last paragraph).
- **Problem:** "Retrieving exemplars scored under a household's own revealed preferences, in the
  style of $\mathcal{A}_{\text{E}}$, is the more plausible route to a system a household could
  adopt unchanged, and from our retrieval results we can anticipate what such a system would and
  would not inherit." Two paragraphs earlier (main:1112) the paper reports that the fixed default
  outranks $\mathcal{A}_{\text{E}}$ on overall $\tau$ for all four models.
- **Why it matters:** the Conclusion recommends the design its own results rank below a
  constant.
- **Options:** (a) recast as an untested route with the condition it must meet (recommended);
  (b) delete the sentence.
- **Edit (option a):**

```old paper/paper_draft_v2.tex
is the more plausible route to a system a household could adopt unchanged, and from our retrieval results we can anticipate what such a system would and would not inherit.
```
```new
is one untested route to a system a household could adopt unchanged; $\mathcal{A}_{\text{E}}$ as built ranks below the fixed default, so such a system would first have to close that gap.
```
- **Knock-on:** none.
- **Risk:** author (Conclusion). (cheap-fix 24; review R4)

### B18. RQ1 is a design proposition, not an empirical question

- **Where:** `paper/paper_draft_v2.tex:322-328`; the RQ2 pointer at `:837`.
- **Problem:** "RQ1: What are the possible architectures for integrating an LLM into an MCDA
  workflow?" No experiment answers it: the paper proposes three positions (main:316-318) and
  concedes a fourth, an LLM that supplies the weights (main:1081). The co-author's source comment
  at main:22 raises the same point. The handling editor asked for the reframing.
- **Why it matters:** an EMS editor reads an RQ the data cannot answer as a design flaw.
- **Options:** (a) a proposition plus one RQ (recommended); (b) keep two RQs but word RQ1 as
  "Where in an MCDA workflow can an LLM be placed, and what infrastructure does each placement
  need?", which is still not tested.
- **Edits (option a):**

```old paper/paper_draft_v2.tex
We pose two research questions:
```
```new
We make one design proposition and ask one research question:
```
```old paper/paper_draft_v2.tex
\item \textbf{RQ1}: What are the possible architectures for integrating an LLM into an MCDA workflow?
\item \textbf{RQ2}: How accurately does each reproduce a deterministic reference ranking?
```
```new
\item \textbf{Proposition}: An LLM can occupy three positions in an MCDA workflow: it can score the alternatives, score them with retrieved worked examples, or supply the inputs of a deterministic calculator.
\item \textbf{RQ}: How accurately does each position reproduce a deterministic reference ranking?
```
```old paper/paper_draft_v2.tex
We answer both questions by benchmarking the three architectures
```
```new
We test the proposition and answer the question by benchmarking the three architectures
```
```old paper/paper_draft_v2.tex
With that floor in place, we turn to RQ2 and compare the architectures model by model.
```
```new
With that floor in place, we turn to the research question and compare the architectures model by model.
```
- **Knock-on:** README:12 states a different single question (B74). The co-author comment at
  main:22 goes with B62.
- **Risk:** author. (cheap-fix 26; handling editor major 5)

### B19. Goodell et al. did not argue about agreement with this study

- **Where:** `paper/paper_draft_v2.tex:1083`.
- **Problem:** "\citet{goodell2025} argue that such independent agreement is evidence both that
  current LLMs calculate unreliably and that tool augmentation is a promising remedy". Their
  text (npj Digit. Med. 8:163, p. 8, from `temppapers/s41746-025-01475-8.pdf`): "the convergence
  of multiple research groups on similar solutions and findings strengthens the evidence for both
  the limitations of current LLMs in medical calculations and the promise of tool-augmented
  approaches." They argued about convergence among clinical groups; extending it to this study
  is our inference. The same page confirms the later sentence: they "did not determine whether
  those errors would have had a real clinical impact" and propose it as future work.
- **Why it matters:** misattributed inference.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
\citet{goodell2025} argue that such independent agreement is evidence both that
```
```new
\citet{goodell2025} read the convergence of several research groups on clinical calculation as evidence both that
```
- **Knock-on:** the clause "and our results add a second domain to that evidence" now states
  the extension as ours; keep it.
- **Risk:** low. (cheap-fix 28, first part)

### B20. "Where that literature predicts compressed scores"

- **Where:** `paper/paper_draft_v2.tex:1077`.
- **Problem:** "This miscalibration extends the scoring biases that \citet{wang2024fairescalers}
  and \citet{li2026scoringbias} documented ... Where that literature predicts compressed scores,
  $\mathcal{A}_{\text{D}}$'s within-scenario range runs 1.25--2.00 times the reference range".
  Wang et al. document position bias; the panel found no compression prediction in either
  paper. I could not open li2026scoringbias from the repository.
- **Why it matters:** a claim about what cited work predicts, unsupported by the citations.
- **Options:** (a) delete the clause (recommended unless the author can point to the passage);
  (b) cite a source that does predict compression.
- **Edit (option a):**

```old paper/paper_draft_v2.tex
Where that literature predicts compressed scores, $\mathcal{A}_{\text{D}}$'s within-scenario range runs
```
```new
$\mathcal{A}_{\text{D}}$'s within-scenario range runs
```
- **Knock-on:** the following sentence ("A model asked to score alternatives on a bounded scale
  can spread its scores as easily as it can compress them, so calibrating against scores that
  are ``too average'' can backfire.") still reads correctly.
- **Risk:** author. (cheap-fix 28, second part)

### B21. Attari et al. measured energy misperception, not cost as the worst-estimated criterion

- **Where:** `paper/paper_draft_v2.tex:606`.
- **Problem:** "Cost is also the criterion households estimate worst
  (Section~\ref{sec:lit-barriers}), so an external calculation adds the most there." The section
  it points to cites \citet{attari2010}, who measured perceived energy use and savings of
  activities. No cited work compares how well households estimate cost against how well they
  estimate emissions, comfort or practicality.
- **Why it matters:** the weight rationale rests on a comparison nobody measured.
- **Options:** one; state what Attari measured.
- **Edit:**

```old paper/paper_draft_v2.tex
Cost is also the criterion households estimate worst (Section~\ref{sec:lit-barriers}), so an external calculation adds the most there.
```
```new
Households also misjudge the energy use that drives cost (Section~\ref{sec:lit-barriers}), so an external calculation adds value there.
```
- **Knock-on:** README:105 says "households underestimate energy use by roughly 2.8x on average
  (Attari et al., 2010)", which is accurate.
- **Risk:** low. (cheap-fix 29; review R1 minor)

### B22. zadeh1965 cited for fuzzy AHP and fuzzy TOPSIS

- **Where:** `paper/paper_draft_v2.tex:369`.
- **Problem:** "Fuzzy variants such as fuzzy AHP and fuzzy TOPSIS address a related problem,
  imprecise judgments, by representing them as fuzzy numbers rather than crisp weights
  \cite{zadeh1965}." Zadeh (1965) introduced fuzzy sets; fuzzy AHP and TOPSIS came decades
  later.
- **Why it matters:** the citation supports the foundation, not the methods named.
- **Options:** one; attach the citation to what it supports.
- **Edit:**

```old paper/paper_draft_v2.tex
by representing them as fuzzy numbers rather than crisp weights \cite{zadeh1965}.
```
```new
by representing them with fuzzy sets \cite{zadeh1965} rather than crisp weights.
```
- **Knock-on:** none.
- **Risk:** low. (cheap-fix 29; review R1 minor)

### B23. "Single forward pass" with two reasoning models

- **Where:** `paper/paper_draft_v2.tex:1069` (Section 6.1).
- **Problem:** "an implicit calculation that direct and exemplar-anchored scoring alike must
  perform in a single forward pass". GPT-OSS runs at low reasoning effort and Gemini at minimal
  (`model_config.py`, `reasoning_effort`), so both produce a reasoning trace before the score.
- **Why it matters:** factually wrong for half the models.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
must perform in a single forward pass
```
```new
must perform within one response, with at most a low-effort reasoning trace
```
- **Knock-on:** drop if the deferred Section 6.1 rewrite (A12) removes the sentence.
- **Risk:** low. (cheap-fix 29; review R2 minor)

### B24. Report the sampling settings and DeepSeek's reasoning mode

- **Where:** `paper/paper_draft_v2.tex:734`; `paper/supplementary.tex:201`.
- **Problem:** Neither file reports temperature, top-p, output-length limit or seed. From the
  code: every call sends `temperature = 0.3` (`model_config.py:6`); no architecture sends
  `top_p`, `max_tokens` or `seed` (`Architectures/*.py` payloads), so the provider defaults
  apply. Reasoning payloads (`model_config.get_reasoning_payload`): GPT-OSS `low`, Gemini
  `minimal`, DeepSeek `none` (reasoning off), Qwen `none`. main:734 says "We ran each
  reasoning-capable model at its lowest available reasoning tier (low effort for GPT-OSS,
  minimal for Gemini)", which leaves DeepSeek's setting unstated; README calls it "none".
- **Why it matters:** reproducibility; the panel asked for these settings.
- **Options:** one.
- **Edits:**

```old paper/paper_draft_v2.tex
(low effort for GPT-OSS, minimal for Gemini)
```
```new
(low effort for GPT-OSS, minimal for Gemini, reasoning disabled for DeepSeek)
```
```old paper/supplementary.tex
DeepSeek V4 Flash (\texttt{deepseek/deepseek-v4-flash:exacto}, hybrid reasoning)
```
```new
DeepSeek V4 Flash (\texttt{deepseek/deepseek-v4-flash:exacto}, hybrid reasoning, run with reasoning disabled)
```
```old paper/supplementary.tex
We report API costs at OpenRouter's published prices as of August 1, 2026.
```
```new
Every call uses temperature 0.3 and leaves top-p and the output-length limit at the provider's defaults; we set no random seed. We report API costs at OpenRouter's published prices as of August 1, 2026.
```
- **Knock-on:** B61 changes the same supp:201 line's `\texttt` identifiers to `\nolinkurl`;
  apply B24 first or merge.
- **Risk:** none. (cheap-fix 30; review R2 minor)

### B25. Cite supplement tables by number

- **Where:** 36 occurrences, on 33 lines, of "Supplementary Material S1/S2" in `paper/paper_draft_v2.tex`.
- **Problem:** The main text points to "Supplementary Material S2" about 20 times without naming
  the table; the handling editor asked for "Table S2.x". The current numbering, from a
  diagnostic compile of the current `supplementary.tex` (scratchpad copy, aux file):
  Table S1.1 notation, Figure S1.1 scenario flow, Table S1.2 scenario fields, S1.3 housing
  mappings, S1.4 fixed-default constants, S1.5 failure modes, S1.6 TOU rates; Table S2.1 swing,
  S2.2 weight vectors, S2.3 sensitivity tau, S2.4 sensitivity Top-1, Figure S2.1 alpha sweep,
  Table S2.5 RAG ablation, Figures S2.2-S2.3 run-to-run variance, Table S2.6 effect sizes, S2.7
  paired bootstrap, S2.8 prompt ablation, S2.9 Friedman, S2.10 prompt pairwise, S2.11 parameter
  provenance, S2.12 McNemar ordering, S2.13 imputed, S2.14 score duplication, S2.15 criterion MAE,
  Figure S2.4 per-type results, Table S2.16 overall results.
- **Why it matters:** the reader has to hunt through a 26-page supplement.
- **Options:** (a) hard-code "Table S2.x" (recommended; apply after Part A's supplement edits,
  since the tables that A2.11, A4.8, A6.2, A7.2, A7.3 and A7.6 add would shift the numbers); (b) cross-reference with `xr`, which needs the
  supplement's `.aux` in the Overleaf project.
- **Edits (option a),** replacing only the phrase "Supplementary Material S2/S1" at each place
  where one table is meant; keep the phrase where a whole section is meant:

| main line | Current pointer is about | Replace the phrase with |
|---|---|---|
| 332 | weight vectors and per-model results | Tables S2.2 and S2.16 |
| 415 | notation | Table S1.1 |
| 478 | imputed repeat | Table S2.13 |
| 480, 482 | test families | keep (text section) |
| 494 (first) | RAG set | keep |
| 494 (second) | scenario flow | Figure S1.1 |
| 496 | field ranges, bands, tiers, housing | Tables S1.2 and S1.3 |
| 573 | tier-to-R mapping | keep (text section) |
| 582, 606 | entropy/MEREC vectors | Table S2.2 |
| 620 | Appliance/Shower detail | see B50 |
| 670 | monthly-cost equations | keep (text section) |
| 734, 738, 740, 1017, 1136 | identifiers, tie rate, prompts, prices, provider | keep |
| 745 | run counts | keep |
| 749 | fixed-default constants | Table S1.4 |
| 753 | ordering protocol | Table S2.12 |
| 757 | prompt cells and run counts | Table S2.8 |
| 765 (first) | alpha protocol | Figure S2.1 |
| 765 (second) | vectors and full matrix | Tables S2.2--S2.4 |
| 808 | provenance statistics | Table S2.11 (A1.7 edits the Cliff's delta range in the same parenthetical; no overlap) |
| 810 | copy-only values | Table S2.5 |
| 879 (first) | criterion MAE values | Table S2.15 |
| 879 (second) | per-model duplication shares | Table S2.14 |
| 889 | imputed protocol | Table S2.13 |
| 909 | GPT-OSS failures | Table S1.5 |
| 952 | per-model breakdown | Figure S2.4 |
| 994 | all checks | keep |
| 1059 | duplication | Table S2.14 |
| 1065 | random vs k=3 exemplars | Table S2.5 |
| 1069 | weight matrix | Tables S2.2 and S2.3 |
| 1081 | realized swings | Table S2.1 |

- **Knock-on:** none beyond the list.
- **Risk:** none. (cheap-fix 31; handling editor major 4)

---

## Group 3: calculator-audit text fixes

Evidence for this group is `paper/CALCULATOR_AUDIT.md`, which recomputed each reference in a
scratchpad copy of the calculator (each copy reproduced its shipped ground-truth file exactly)
and quotes each source verbatim. "W/R" there means reference winners / full rankings changed.

### B26. The EER formula comes from Building America HSP, not AHRI 210/240

- **Where:** `paper/paper_draft_v2.tex:672`; `README.md:392`; code comment
  `Ground Truth Calculators/HVACGroundTruthCalculator.py:136` (B76); new bib entry.
- **Problem:** main:672 derives EER from SEER with "(both rating quantities as AHRI defines them
  \cite{ahri2008})" next to Eq. 10, $\mathrm{EER} = 1.12\,S - 0.02\,S^2$; README:392 and the code
  comment attribute the quadratic itself to AHRI 210/240. The quadratic is the Building America
  House Simulation Protocols' Eq. 3 (Hendron & Engebrecht 2010): "approximate conversion from
  SEER to EER (Wassmer 2003): EER = -0.02 x SEER2 + 1.12 x SEER". The panel had guessed a BEopt
  source (Cutler et al. 2013); the audit found the HSP.
- **Why it matters:** a misattributed formula in the one calculator the paper gives in full.
- **Options:** one; add the HSP citation and keep ahri2008 for the rating definitions.
- **Edits:**

```old paper/paper_draft_v2.tex
divides it by an effective EER derived from SEER (both rating quantities as AHRI defines them \cite{ahri2008})
```
```new
divides it by an effective EER derived from SEER with the approximate conversion of the Building America House Simulation Protocols \cite{hendron2010hsp} (both rating quantities as AHRI defines them \cite{ahri2008})
```
```new-bib paper/cas-refs.bib
@techreport{hendron2010hsp,
  author = {R. Hendron and C. Engebrecht},
  title = {Building America House Simulation Protocols},
  institution = {National Renewable Energy Laboratory},
  number = {NREL/TP-550-49426},
  year = {2010},
  note = {Revised October 2010. Eq.~3 gives EER $= -0.02\,\mathrm{SEER}^2 + 1.12\,\mathrm{SEER}$, citing Wassmer (2003)},
  url = {https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/house_simulation_revised.pdf},
}
```
  (Verify the report number on the PDF's cover page.)
```old README.md
EER comes from rated SEER via the AHRI 210/240 quadratic (`EER = -0.02*SEER^2 + 1.12*SEER`)
```
```new
EER comes from rated SEER via the Building America House Simulation Protocols conversion (Hendron & Engebrecht 2010, Eq. 3, citing Wassmer 2003: `EER = -0.02*SEER^2 + 1.12*SEER`)
```
- **Knock-on:** B32 and B30 also cite `hendron2010hsp`.
- **Risk:** low. (cheap-fix 21; HVAC audit item 1; review R1 major 3)

### B27. Disclose that heating is an electric heat pump at the cooling EER

- **Where:** `paper/paper_draft_v2.tex:696`.
- **Problem:** The calculator divides the heating load by the same SEER-derived EER
  (`calculate_energy_consumption`, HVAC calc:130-156) and prices it at the flat electric rate
  with PJM factors. Every heating scenario is therefore an electric heat pump at its cooling
  efficiency (COP about 3.3), with no capacity or efficiency loss down to the test set's
  5 F minimum (Table S1.2). README:392 says so; the paper does not. Pennsylvania's on-site
  residential combustion is mostly natural gas and petroleum (the paper's own Figure 1).
  Audit impact: heating kWh x1.33 changes 4-6 of 70 test winners.
- **Why it matters:** the panel's handling editor and R1 both named it; an EMS reader in a
  gas-heated region will ask.
- **Options:** one sentence in the HVAC description (here) and one clause in Limitations (B28).
- **Edit:**

```old paper/paper_draft_v2.tex
Solar gain enters only in cooling season, and internal gain reverses sign in heating season because occupant and equipment heat offset the load the system must supply.
```
```new
Solar gain enters only in cooling season, and internal gain reverses sign in heating season because occupant and equipment heat offset the load the system must supply. The calculator uses the same SEER-derived EER in heating season, so it models every heating scenario as an electric heat pump at its cooling efficiency, with no loss of capacity or efficiency at low outdoor temperatures.
```
- **Knock-on:** B30 edits the first of these two sentences too; the merged text is in B30.
- **Risk:** low. (cheap-fix 20; HVAC audit item 2; review R1 major 2)

### B28. One limitation sentence for four undisclosed modeling choices

- **Where:** `paper/paper_draft_v2.tex:1088` (Limitations, first paragraph, last sentence);
  `paper/cas-refs.bib:377` (title line of `pjm2022emissions`).
- **Problem:** Four calculator choices appear nowhere in the paper:
  1. heating as an electric heat pump (B27);
  2. HVAC and Shower price electricity at a flat \$0.19/kWh, while the Appliance calculator uses
     each utility's time-of-use tariff for the same households (review R1 major 4). The reason
     exists in the paper (main:614: HVAC and Shower alternatives are evaluated at one time;
     Appliance alternatives differ in time) but is not tied to the tariff choice;
  3. the HVAC calculator applies the insulation tier's *wall* R-value to the whole conductive
     envelope ($m_h A_f$ in Eq. 9), roof and floor included (HVAC audit item 12);
  4. both calculators apply the PJM peak window (7 a.m.-11 p.m.) on every day, while PJM defines
     it as "all non-holiday weekdays from 7 a.m. to 11 p.m." (PJM 2022 emissions report, quoted
     in the HVAC audit, item 11; weekday-only changes 1 of 70 HVAC winners).
- **Why it matters:** each is a normative or simplifying choice a reviewer can find in the code.
- **Options:** one sentence appended to the paragraph that already lists calculator
  approximations.
- **Edit:**

```old paper/paper_draft_v2.tex
but the absolute MAE and RMSE values combine LLM extraction error with calculator imputation error.
```
```new
but the absolute MAE and RMSE values combine LLM extraction error with calculator imputation error. The calculators also simplify in four ways: every HVAC heating scenario is an electric heat pump at its SEER-derived cooling efficiency, so households that heat with gas or oil fall outside the model; HVAC and Shower electricity is priced at a flat \$0.19/kWh because their alternatives share one time, while Appliance alternatives, which differ in run time, are priced on each utility's time-of-use tariff; the insulation tier's wall R-value applies to the whole envelope; and the PJM peak window applies on every day, although PJM defines it for non-holiday weekdays \cite{pjm2022emissions}.
```
```old paper/cas-refs.bib
  title = {2018--2022 {CO2, SO2} and {NOX} Emission Rates},
```
```new
  title = {2018--2022 {CO2, SO2} and {NOX} Emission Rates},
  url = {https://www.pjm.com/-/media/DotCom/library/reports-notices/special-reports/2023/2022-emissions-report.ashx},
```
- **Knock-on:** B47 edits an earlier clause of the same paragraph (mains temperature).
- **Risk:** low. (cheap-fix 20; HVAC audit items 2, 11, 12; review R1 majors 2 and 4)

### B29. The budget-penalty jump at u = 1.5, and how often it fires

- **Where:** `paper/paper_draft_v2.tex:670`.
- **Problem:** Eq. 7 drops from $0.5e^{-1.5} \approx 0.11$ to 0 at $u = 1.5$, with a knee at
  $u = 0.8$; the paper states the constants are ours but not the discontinuity. The panel asked
  to count the rankings it decides. Read-only recomputation from `Ground Truth/ground_truth_hvac.xlsx`
  and `ground_truth_shower.xlsx` ($u = 90\,C_{8h}/B$ for HVAC, $27\,n\,C_{\text{shower}}/B$ for
  Shower; the reconstructed HVAC Energy Cost score matched the stored score in 315 of 315
  alternatives): no alternative in the 285 test and RAG scenarios reaches $u \geq 1.5$. Four HVAC
  alternatives fall in $[1.0, 1.5)$ and 13 HVAC plus one Shower alternative in $[0.8, 1.0)$;
  Shower's maximum is 0.905. The Appliance audit found a maximum Appliance utilization of 0.224.
  Replacing the jump with the continued exponential changes 0 of 105 HVAC rankings.
- **Why it matters:** the jump looks like an arbitrary cliff; the data show it never binds.
- **Options:** one sentence.
- **Edit:**

```old paper/paper_draft_v2.tex
The values 0.80, 2.5 and 1.5 and the exponential form are our own choices.
```
```new
The values 0.80, 2.5 and 1.5 and the exponential form are our own choices. The penalty drops from about 0.11 to 0 at $u = 1.5$, but no alternative in the 285 scenarios reaches that point; four HVAC alternatives fall between $u = 1.0$ and 1.5, and 14 alternatives (13 HVAC, one Shower) between 0.8 and 1.0.
```
- **Knock-on:** none.
- **Risk:** low. (cheap-fix 20; review R1 major 5)

### B30. Internal gains, solar gain and glazing: label sources and assumptions

- **Where:** `paper/paper_draft_v2.tex:696` (after Eq. 9-11).
- **Problem:** Eq. 9 uses $Q_{\mathrm{int}} = 400\,n + A_f + 800$ and
  $Q_{\mathrm{sol}} = 20\,(0.15\,A_f)$ with no source in the paper. The code cites ASHRAE
  Fundamentals Ch. 18 Table 1 for gains, which covers occupants only; 400 Btu/h per occupant is
  sensible plus latent (about 245 sensible; HSP Table 44 gives 230/190), inside a sensible-only
  balance. The 1.0 Btu/h per ft² and the 800 Btu/h are unsourced. The 15% glazing fraction is the
  IECC R405 standard reference design ("15 percent of the conditioned floor area"); the 20 Btu/h
  per ft² of glass is unsourced. Audit impact: 400 -> 245 changes 1-2 of 70 winners; solar
  20 -> 40, 3 of 70.
- **Why it matters:** equation constants without sources in the "given in full" calculator.
- **Options:** one; label them. (This merges with B27's sentence.)
- **Edit (supersedes the B27 edit; apply one of the two):**

```old paper/paper_draft_v2.tex
Solar gain enters only in cooling season, and internal gain reverses sign in heating season because occupant and equipment heat offset the load the system must supply.
```
```new
Solar gain enters only in cooling season, and internal gain reverses sign in heating season because occupant and equipment heat offset the load the system must supply. The glazing fraction of 0.15 is the IECC standard reference design \cite{iecc2021}; the 20\,BTU/hr per ft\textsuperscript{2} of glass, the 1.0\,BTU/hr per ft\textsuperscript{2} of equipment gain and the 800\,BTU/hr baseline are our assumptions, and the 400\,BTU/hr per occupant counts latent as well as sensible heat. The calculator uses the same SEER-derived EER in heating season, so it models every heating scenario as an electric heat pump at its cooling efficiency, with no loss of capacity or efficiency at low outdoor temperatures.
```
```new-bib paper/cas-refs.bib
@techreport{iecc2021,
  author = {{International Code Council}},
  title = {2021 International Energy Conservation Code},
  institution = {International Code Council},
  year = {2021},
  note = {Section R405, standard reference design: glazing area 15\% of conditioned floor area},
}
```
  (Verify the table number inside R405 for the edition cited.)
- **Knock-on:** the next sentence of main:696 ("The 800\,BTU/hr standby term keeps a
  zero-$\Delta T$ setpoint from producing exactly zero load.") stays.
- **Risk:** low. (HVAC audit items 6, 7)

### B31. The envelope multipliers are our values

- **Where:** `paper/paper_draft_v2.tex:696`; `paper/supplementary.tex:576`; code comment HVAC
  calc:62 (B76).
- **Problem:** supp:576 says $m_h$ scales exposed envelope area "following ACCA Manual~J exposure
  conventions \citep{accamanualj}"; main:672 places the multipliers inside the "ASHRAE-style
  balance \cite{accamanualj}". The audit found no Manual J table of such multipliers (Manual J is
  paywalled; nothing tabulates 1.7/1.5/1.2). Audit impact: x1.25 changes 2 of 70 winners.
- **Why it matters:** attributes our values to a standard.
- **Options:** one.
- **Edits:**

```old paper/supplementary.tex
following ACCA Manual~J exposure conventions \citep{accamanualj}:
```
```new
with values we set by exposure (they are not taken from a Manual~J table):
```
```old paper/paper_draft_v2.tex
$m_h$ the housing-type envelope multiplier (1.2 apartment and condo, 1.5 townhouse and rowhouse, 1.7 single-family)
```
```new
$m_h$ the housing-type envelope multiplier (1.2 apartment and condo, 1.5 townhouse and rowhouse, 1.7 single-family; our values)
```
- **Knock-on:** `accamanualj` stays cited at main:672 and main:724.
- **Risk:** low. (HVAC audit item 4)

### B32. The 70 F heating comfort optimum is our choice

- **Where:** `paper/paper_draft_v2.tex:698`.
- **Problem:** "Comfort uses a tent function anchored to setpoints near the centers of the
  ASHRAE 55 comfort zones ($76\,^\circ$F in cooling mode, $70\,^\circ$F in heating mode)". The
  code comment calls 70 F "~1F below its 71F midpoint"; the Building America HSP gives "heating:
  71F" as the optimum seasonal temperature citing ASHRAE 55-2004. This is the most
  rank-sensitive HVAC constant: 71 F would change 8 of 70 test winners and 16 of 70 rankings.
- **Why it matters:** the paper calls a choice a standard's center.
- **Options:** (a) state it as our choice with the HSP value (recommended); (b) leave as is.
- **Edit:**

```old paper/paper_draft_v2.tex
($76\,^\circ$F in cooling mode, $70\,^\circ$F in heating mode)
```
```new
($76\,^\circ$F in cooling mode; in heating mode we use $70\,^\circ$F, 1\,\textdegree{}F below the $71\,^\circ$F optimum of \citealt{hendron2010hsp})
```
  (If the harmonized citation style lacks `\citealt`, write "the House Simulation Protocols'
  $71\,^\circ$F optimum \cite{hendron2010hsp}".)
- **Knock-on:** README:394 "(76 F cooling, 70 F heating)" can stay.
- **Risk:** author (the sensitivity is large; the author may want a sentence on it).
  (HVAC audit item 3)

### B33. Disclose the three inconsistent heating/cooling tests

- **Where:** `paper/paper_draft_v2.tex:703` (after the Comfort equation).
- **Problem:** The HVAC calculator decides heating versus cooling three ways: Comfort uses
  "outdoor > 75 F" (calc:169), the Off alternative's free-float uses a 73 F test (calc:447), and
  the load and Practicality use "outdoor > setpoint" (calc:202, 483). A 79 F setpoint at 78 F
  outdoors takes the heating branch with zero load. The audit counts 3 test and 7 RAG
  alternatives affected; a single seasonal test would change 1 of 70 test winners and 2 of 70
  rankings.
- **Why it matters:** a small bug; disclosing it costs one sentence and pre-empts a code
  reviewer.
- **Options:** disclose (recommended, per the no-calculator-change decision); or fix the
  calculator and recompute offline (out of scope here).
- **Edit:**

```old paper/paper_draft_v2.tex
is the context-dependent optimal setpoint used as the peak of the tent function.
```
```new
is the context-dependent optimal setpoint used as the peak of the tent function. Comfort switches to heating mode at outdoor temperatures of $75\,^\circ$F or below, while the load and Practicality switch when the outdoor temperature falls below the setpoint; the two tests disagree for 3 test and 7 RAG alternatives and change 1 of the 70 HVAC reference winners.
```
- **Knock-on:** none.
- **Risk:** low. (HVAC audit item 8)

### B34. State that maintenance is "moderate" in every scenario

- **Where:** `paper/paper_draft_v2.tex:722`.
- **Problem:** Eq. 12 defines $D$ with "$\delta_{\mathrm{maint}}$ ... the base annual loss rate".
  The code (`_efficiency_degradation`, calc:178-191) has rates 0.5/1.0/1.5%/yr for good/moderate/
  poor upkeep, and every scenario uses the default `moderate` (calc:538). The paper does not say
  so, and the rates are unsourced.
- **Why it matters:** a reader cannot reproduce $D$ without the value.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
and $\delta_{\mathrm{maint}}$ is the base annual loss rate.
```
```new
and $\delta_{\mathrm{maint}}$ is the base annual loss rate, which we set to 0.01 (moderate maintenance) for every scenario.
```
- **Knock-on:** none.
- **Risk:** none. (HVAC audit item 17)

### B35. Normalization bounds: pooled percentiles, and HVAC environmental bounds are derived

- **Where:** `paper/paper_draft_v2.tex:624`; `README.md:345` (B72).
- **Problem:** "For Energy Cost and Environmental Impact, these endpoints are the 5th and 95th
  percentiles of the scenario set's own distribution rather than of national data." The three
  audits found every percentile bound is computed on the test and RAG scenarios together (285 in
  all; e.g., the HVAC cost bounds reproduce only on the pooled set). The HVAC Environmental Impact
  bounds 1.96-18.04 are not percentiles: main:645 correctly says they convert the cost-percentile
  kWh with the PJM factors (the actual percentiles are 2.03/17.66).
- **Why it matters:** "scenario set" reads as the 195-scenario test set, and the sentence
  contradicts main:645 for one cell.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
these endpoints are the 5th and 95th percentiles of the scenario set's own distribution rather than of national data.
```
```new
these endpoints are the 5th and 95th percentiles of the distribution over all 285 test and RAG scenarios rather than of national data; the HVAC Environmental Impact endpoints instead convert the HVAC cost percentiles to CO\textsubscript{2}, as described below.
```
- **Knock-on:** B36 and B37 relabel the Appliance and Shower "realized spans"; README:345
  heading (B72).
- **Risk:** low. (HVAC audit items 9, 10; Appliance audit item 10; Shower audit item 16)

### B36. Appliance "realized ... spans" are pooled percentiles

- **Where:** `paper/paper_draft_v2.tex:726`.
- **Problem:** "the realized per-cycle cost spans \$0.025--\$0.71 and emissions 0.288--3.643 lbs
  CO\textsubscript{2} \cite{energystar_products}". These are the pooled 5th/95th percentiles, the
  Table 4 bounds; the realized test-set span is \$0.021-\$1.12 and 0.215-3.643 lbs. The ENERGY STAR
  products citation cannot support a dataset percentile.
- **Why it matters:** "realized span" is wrong by a factor of 1.6 at the top.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
the realized per-cycle cost spans \$0.025--\$0.71 and emissions 0.288--3.643 lbs CO\textsubscript{2} \cite{energystar_products}.
```
```new
the 5th and 95th percentiles of per-cycle cost over the 285 test and RAG scenarios are \$0.025 and \$0.71, and of emissions 0.288 and 3.643 lbs CO\textsubscript{2}.
```
- **Knock-on:** `energystar_products` becomes uncited (BibTeX drops it; see B65).
- **Risk:** low. (Appliance audit item 10)

### B37. Shower "realized ... spans" are pooled percentiles

- **Where:** `paper/paper_draft_v2.tex:728`.
- **Problem:** "the realized per-shower cost spans \$0.14--\$1.14 and the water volume
  6.0--45.0 gallons \cite{epawatersense,reu2016,harrispoll2024}". These are rounded 5th/95th
  percentiles over the 80 Shower scenarios (test and RAG); realized spans are \$0.05-\$2.18 and
  2-72 gallons (9.2% and 6.7% of alternatives fall outside). The three citations support the
  flow rates (WaterSense), average duration (REU2016) and long-shower prevalence (Harris Poll),
  not the percentiles.
- **Why it matters:** as B36; and the citations sit on a claim they cannot support.
- **Options:** one; keep the citations on the facts they support, inside the same clause (Part A
  proposes no edit to the clause before the semicolon).
- **Edit:**

```old paper/paper_draft_v2.tex
the realized per-shower cost spans \$0.14--\$1.14 and the water volume 6.0--45.0 gallons \cite{epawatersense,reu2016,harrispoll2024}.
```
```new
the 5th and 95th percentiles over the 80 test and RAG Shower scenarios are \$0.14 and \$1.14 per shower and 6.0 and 45.0 gallons, from flow rates and durations set against \citet{epawatersense}, \citet{reu2016} and \citet{harrispoll2024}.
```
- **Knock-on:** none.
- **Risk:** low. (Shower audit item 16)

### B38. PECO rates and FirstEnergy multipliers cite the wrong documents

- **Where:** `paper/paper_draft_v2.tex:726`; `paper/supplementary.tex:765`; new bib entries.
- **Problem:**
  - PECO: the code's 0.320/0.076 \$/kWh are PECO's December 1, 2025-May 31, 2026 time-of-use
    generation charges excluding the 0.787 c transmission component ("Peak kWhs 32.747 31.960
    0.787 / Off-Peak 8.382 7.595 0.787", PECO's 2026 residential price-to-compare sheet). The
    paper cites `peco2021`, a 2021 net-metering FAQ that confirms the 2-6 p.m. weekday window but
    gives no prices. Keep `peco2021` for the window (main:614) and add the rate sheet.
  - FirstEnergy: the price-to-compare values match `firstenergy2025`; the multipliers
    (West Penn on-peak x1.6649, off-peak x0.8542, etc.) come from FirstEnergy Pennsylvania's
    tariff Supplement No. 20 (PA PUC document 1875621). `firstenergy2026`, the June 2026 PTC
    page, holds neither.
- **Why it matters:** a reviewer who opens `peco2021` or `firstenergy2026` will not find the
  numbers.
- **Options:** one.
- **Edits:**

```old paper/paper_draft_v2.tex
\cite{peco2021,ppl2025,firstenergy2025,firstenergy2026,duquesne2026}
```
```new
\cite{peco2021,peco2025tou,ppl2025,firstenergy2025,fepa_supp20,duquesne2026}
```
```old paper/supplementary.tex
PECO (Rate R-TOU) \citep{peco2021}
```
```new
PECO (Rate R-TOU) \citep{peco2021,peco2025tou}
```
```old paper/supplementary.tex
\citep{firstenergy2025,firstenergy2026}
```
```new
\citep{firstenergy2025,fepa_supp20}
```
```new-bib paper/cas-refs.bib
@techreport{peco2025tou,
  author = {{PECO Energy Company}},
  title = {Residential Price to Compare and Time-of-Use Generation Charges, December 1, 2025 -- May 31, 2026},
  institution = {PECO Energy Company},
  year = {2025},
  note = {Peak 32.747\,\textcent/kWh, off-peak 8.382\,\textcent/kWh, super off-peak 6.061\,\textcent/kWh, each including 0.787\,\textcent/kWh transmission},
  url = {AUTHOR: paste the full PECO contentstack PDF link},
}
@techreport{fepa_supp20,
  author = {{FirstEnergy Pennsylvania Electric Company}},
  title = {Electric Pa. P.U.C. Tariff, Supplement No. 20: Time-of-Use Default Service Multipliers},
  institution = {Pennsylvania Public Utility Commission},
  year = {AUTHOR: filing year},
  url = {https://www.puc.pa.gov/pcdocs/1875621.pdf},
}
```
  (Verify both titles and fill the two marked fields from the PDFs; the audit gives the PECO
  file name as `2026_RESIDENTIAL_Final_Electric_PTC_Effective_06-01-2026.pdf`.)
- **Knock-on:** `firstenergy2026` becomes uncited. The code comment at Appliance calc:31-32 also
  credits "FirstEnergy Corp. (2026)" for the multipliers (B76).
- **Risk:** low. (Appliance audit items 3, 4)

### B39. PPL: the "Rate RTS" label and rates that do not match the cited tariff

- **Where:** `paper/supplementary.tex:765` (and Table S1.6, supp:755).
- **Problem:**
  1. "PPL (Rate RTS) \citep{ppl2025}": RTS is PPL's Residential Thermal Storage rate. The
     time-of-use program is Generation Supply Charge-1 (GSC-1) "for Rate Schedule RS and RTS",
     which is what `ppl2025` is.
  2. The PPL rates in the calculator and Table S1.6 (0.160 / 0.070 \$/kWh) match no season of
     the cited Supplement 393: summer on-peak (2-6 p.m.) 13.333 c and off-peak 8.243 c; winter
     7.938 c and 6.471 c. Substituting the summer values, which match the modeled 2-6 p.m. window,
     changes no Appliance reference winner (0 of 65 test, 0 of 35 RAG) but changes energy scores
     in 9 test and 11 RAG scenarios, and PPL's peak-to-off-peak saving falls from 56% to 38%. The
     supplement's "cuts its per-cycle cost by 49--76\%" then becomes 38-76% (other utilities:
     PECO 76.3, West Penn 48.8, Penelec 49.7, Met-Ed 50.7; recomputed from Table S1.6).
- **Why it matters:** a cited tariff contradicts the table next to it.
- **Options:** (a) disclose the mismatch and its null rank effect (recommended under the
  no-calculator-change decision); (b) change the calculator's PPL rates and recompute offline
  (A_E exemplar scores would change, so this reopens reruns).
- **Edits (option a):**

```old paper/supplementary.tex
and PPL (Rate RTS) \citep{ppl2025}
```
```new
and PPL (GSC-1 time-of-use program for Rate Schedules RS and RTS) \citep{ppl2025}
```
```old paper/supplementary.tex
Shifting a dishwasher cycle from peak to off-peak cuts its per-cycle cost by 49--76\% across these five time-of-use utilities.
```
```new
Shifting a dishwasher cycle from peak to off-peak cuts its per-cycle cost by 49--76\% across these five time-of-use utilities. The PPL rates in the table do not match the GSC-1 supplement we cite, whose summer rates are 13.333 and 8.243\,\textcent/kWh; substituting them changes no Appliance reference winner in the test or RAG set and lowers the bottom of that range to 38\%.
```
- **Knock-on:** Appliance calc:36 comment "PPL Rate RTS" (B76).
- **Risk:** author (discloses a data error). (Appliance audit items 1, 2, 11, 13)

### B40. "Weekday summer rates"

- **Where:** `paper/paper_draft_v2.tex:726`.
- **Problem:** "The calculator applies weekday summer rates year-round". PECO's rates are its
  December-May rates (B38), PPL's match no season (B39), and FirstEnergy's are one
  price-to-compare times fixed multipliers. The calculator applies one rate pair per utility.
- **Why it matters:** "summer" is wrong for two of three utility groups.
- **Options:** one; delete a word.
- **Edit:**

```old paper/paper_draft_v2.tex
The calculator applies weekday summer rates year-round
```
```new
The calculator applies one weekday rate pair per utility year-round
```
- **Knock-on:** none.
- **Risk:** none. (Appliance audit item 2)

### B41. "Appliance-specific tolerance ceilings" overstates the source

- **Where:** `paper/paper_draft_v2.tex:726`.
- **Problem:** "Comfort and Practicality both decline with delay from the household's baseline
  run time against appliance-specific tolerance ceilings \cite{paetz2012,waseem2020}". Paetz et
  al. support only the dishwasher's 12 h ("postpone the dish-washer use by twelve hours without
  constraints", two residents); the washer's 8 h, the dryer's 6 h and the curve breakpoints
  (comfort 3/7/12 h; practicality 2/4/8/12 h) are ours; Waseem 2020 was inaccessible to the
  audit. The base curves do not depend on appliance type; the ceilings only scale a
  household-size penalty (`_max_acceptable_delay`, Appliance calc:89-96).
- **Why it matters:** attributes our values to two studies.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
Comfort and Practicality both decline with delay from the household's baseline run time against appliance-specific tolerance ceilings \cite{paetz2012,waseem2020}
```
```new
Comfort and Practicality both decline with delay from the household's baseline run time on curves we set, with a household-size penalty scaled by an appliance-specific delay ceiling (12\,h for dishwashers, following \citet{paetz2012}; 8\,h for washers and 6\,h for dryers, our values)
```
- **Knock-on:** main:608 keeps `\cite{paetz2012,waseem2020}` for the general statement about
  delay tolerance.
- **Risk:** low. (Appliance audit item 7)

### B42. paetz2012 lists the wrong co-authors

- **Where:** `paper/cas-refs.bib:222`.
- **Problem:** `author = {A. Paetz and E. Dutschke and W. Fichtner}`. The ACEEE 2012 paper
  "Demand Response with Smart Homes and Electric Scooters" is by A.-G. Paetz, T. Kaschub,
  P. Jochem and W. Fichtner.
- **Why it matters:** wrong reference list entry.
- **Options:** one.
- **Edit:**

```old paper/cas-refs.bib
  author = {A. Paetz and E. Dutschke and W. Fichtner},
```
```new
  author = {A.-G. Paetz and T. Kaschub and P. Jochem and W. Fichtner},
```
- **Knock-on:** none.
- **Risk:** none. (Appliance audit item 8)

### B43. kWh/cycle "drawn from the ENERGY STAR certified-products database"; pooled rho

- **Where:** `paper/supplementary.tex:572`.
- **Problem:** "an independent per-cycle energy value (kWh/cycle) drawn from the ENERGY STAR
  certified-products database". ENERGY STAR limits dishwashers to 240 kWh/yr at 215 cycles
  (about 1.12 kWh/cycle) and dryers to a CEF of at least 3.93 (about 2.15 kWh/cycle); 23 of 24
  test dryers and 8 of 20 test dishwashers exceed those limits, and ages run to 28-40 years. The
  Spearman values (0.36 / 0.38 / 0.69) and the 7-9-year dryer range (2.40-3.50) are computed on
  test and RAG together; test-only values are 0.10 / 0.19 / 0.62 and 2.80-3.00.
- **Why it matters:** a certified-products database cannot contain values above its own limit.
- **Options:** one.
- **Edits:**

```old paper/supplementary.tex
an independent per-cycle energy value (kWh/cycle) drawn from the ENERGY STAR certified-products database, and
```
```new
an independent per-cycle energy value (kWh/cycle) that we set per scenario (most dryer values and some dishwasher values exceed current ENERGY STAR limits, as older units do), and
```
```old paper/supplementary.tex
(Spearman's $\rho = 0.36$ for dishwashers, $0.38$ for dryers, and $0.69$ for washing machines)
```
```new
(Spearman's $\rho = 0.36$ for dishwashers, $0.38$ for dryers, and $0.69$ for washing machines, over the 285 test and RAG scenarios)
```
- **Knock-on:** README:329 (B71); Appliance calc:439-442 comment "strongly correlated" (B76).
- **Risk:** low. (Appliance audit items 9, 12, 14)

### B44. Duquesne's flat rate listed with a peak window

- **Where:** `paper/supplementary.tex:759` (Table S1.6).
- **Problem:** "Duquesne & 2--9pm & 0.1375 & 0.1375". A flat rate has no peak window; the code
  stores a placeholder window. (The audit could not verify 13.75 c; the June 2025 PTC was
  12.193 c, and `duquesne2026` has no URL. Rank-neutral by construction.)
- **Why it matters:** the table implies a TOU structure that does not exist.
- **Options:** one.
- **Edit:**

```old paper/supplementary.tex
Duquesne   & 2--9pm  & 0.1375 & 0.1375 \\
```
```new
Duquesne   & flat    & 0.1375 & 0.1375 \\
```
- **Knock-on:** none.
- **Risk:** none. (Appliance audit item 5)

### B45. CDC Legionella: 120 F is the circulation floor; storage guidance is above 140 F

- **Where:** `paper/paper_draft_v2.tex:608`; `paper/supplementary.tex:926`.
- **Problem:** main:608 says the Shower Comfort curve "penalizes heater setpoints below the CDC's
  \textit{Legionella} threshold \cite{cdc2026}"; supp:926 says the 120-140 F band is "anchored
  instead to CDC storage guidance". CDC's guidance (verbatim in the Shower audit): "Store hot
  water at temperatures above 140F (60C)" and "Ensure hot water in circulation doesn't fall below
  120F (49C)". So 120 F is the circulation floor, and the code's penalty *above* 140 F (standby
  loss) runs against CDC's storage advice; no scenario setpoint exceeds 140 F, so it never fires.
  supp:926 also calls the corrected 120-140 F band "The original function" (the panel's
  reproducibility reviewer flagged this; the earlier function used 110-130 F).
- **Why it matters:** a wrong public-health attribution in two places.
- **Options:** one; fix the attribution, label the 140 F cap as ours, fix "original".
- **Edits:**

```old paper/paper_draft_v2.tex
and penalizes heater setpoints below the CDC's \textit{Legionella} threshold \cite{cdc2026}
```
```new
and penalizes heater setpoints below the 120\,\textdegree{}F floor that the CDC sets for circulating hot water \cite{cdc2026}
```
```old paper/supplementary.tex
The original function uses 120--140\,\textdegree{}F, anchored instead to CDC storage guidance:
```
```new
The current function uses 120--140\,\textdegree{}F, anchored instead to the CDC's 120\,\textdegree{}F floor for circulating hot water:
```
```old paper/supplementary.tex
and above 140\,\textdegree{}F the tank adds standby loss without comfort benefit.
```
```new
and above 140\,\textdegree{}F, by our assumption, the tank adds standby loss without comfort benefit (the CDC recommends storing hot water above 140\,\textdegree{}F; no scenario setpoint exceeds it).
```
- **Knock-on:** main:728 "heater setpoints outside the safe band \cite{cdc2026}" can stay.
- **Risk:** low. (Shower audit item 6; review R3 major 4)

### B46. The season-dependent shower optimum is not in REU2016

- **Where:** `paper/paper_draft_v2.tex:728`; new bib entry.
- **Problem:** "Comfort penalizes duration away from a season-dependent optimum \cite{reu2016}".
  REU2016 supports the 7.8-minute average only; it has no seasonal data. The winter/summer cap
  (11.6 vs 8.8 min) comes from Ibáñez-Rueda et al. (2023), a self-reported survey of 945
  university students in Granada (Sustainable Water Resources Management, DOI
  10.1007/s40899-023-00905-3; the calculator's comment cites it). The +10% per 10.8 F elasticity
  and the 77 F anchor are our assumptions (Shower calc:53-64). This is the most rank-sensitive
  Shower assumption: removing the elasticity changes 7 of 60 test winners.
- **Why it matters:** cites a source for data it does not contain.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
Comfort penalizes duration away from a season-dependent optimum \cite{reu2016}
```
```new
Comfort penalizes duration away from an optimum that starts at the 7.8-minute average of \citet{reu2016} and, by our assumption, lengthens by 10\% per 10.8\,\textdegree{}F below 77\,\textdegree{}F outdoors, capped at the winter-to-summer ratio (11.6 against 8.8 minutes) that \citet{ibanezrueda2023} report for self-reported showers
```
```new-bib paper/cas-refs.bib
@article{ibanezrueda2023,
  author = {AUTHOR: fill from the DOI},
  title = {AUTHOR: fill from the DOI},
  journal = {Sustainable Water Resources Management},
  year = {2023},
  doi = {10.1007/s40899-023-00905-3},
}
```
- **Knock-on:** none.
- **Risk:** low. (Shower audit item 9)

### B47. Mains temperature is our linear approximation; drop zhang2023

- **Where:** `paper/paper_draft_v2.tex:728` and `:1088`; README:404 (B72); Shower calc:31-33
  comment (B76).
- **Problem:** main:728 derives the inlet temperature "from the outdoor temperature
  \cite{burch2007,zhang2023}"; main:1088 lists "mains water temperature interpolated linearly
  from outdoor temperature \cite{burch2007}" among unpublished relationships; README:404 calls it
  "NREL seasonal model". The code interpolates linearly between 45 F (outdoor at or below 32 F)
  and 65 F (at or above 75 F). Burch & Christensen give an annual sinusoid (annual mean plus about
  6 F, amplitude tied to the monthly range, with a phase lag), which yields about 47-69 F for
  Pittsburgh and 50-74 F for Philadelphia; ours runs 2-5 F low. Zhang et al. (2023) simulate Hong
  Kong showers and have no mains model.
- **Why it matters:** attributes our approximation to NREL.
- **Options:** one.
- **Edits:**

```old paper/paper_draft_v2.tex
derives the mains inlet temperature from the outdoor temperature \cite{burch2007,zhang2023}
```
```new
derives the mains inlet temperature from the outdoor temperature by linear interpolation between 45\,\textdegree{}F (outdoors at or below 32\,\textdegree{}F) and 65\,\textdegree{}F (at or above 75\,\textdegree{}F), our approximation to the seasonal model of \citet{burch2007},
```
```old paper/paper_draft_v2.tex
mains water temperature interpolated linearly from outdoor temperature \cite{burch2007}
```
```new
mains water temperature interpolated linearly from outdoor temperature (our approximation; \citet{burch2007} model it as an annual sinusoid)
```
- **Knock-on:** `zhang2023` becomes uncited in the paper; the Shower calc:42 and :133 comments
  still name it (B76).
- **Risk:** low. (Shower audit item 4)

### B48. The 105 F delivery target is our convention; the practicality curve is hand-set

- **Where:** `paper/paper_draft_v2.tex:728`.
- **Problem:** (1) "to reach a 105\,\textdegree{}F delivery target": uncited in the paper; the
  code credits Zhang et al., who assume 89.6-104 F (32-40 C) and recommend 33.5-35.7 C.
  (2) "Practicality penalizes duration on a separate curve calibrated to adoption likelihood": no
  calibration exists; the 3-minute minimum, the 5-minute breakpoint and the curve are hand-set
  (Shower audit item 11).
- **Why it matters:** "calibrated" claims a fit that was never made.
- **Options:** one.
- **Edits:**

```old paper/paper_draft_v2.tex
to reach a 105\,\textdegree{}F delivery target.
```
```new
to reach a 105\,\textdegree{}F delivery target, our convention.
```
```old paper/paper_draft_v2.tex
Practicality penalizes duration on a separate curve calibrated to adoption likelihood
```
```new
Practicality penalizes duration on a separate curve that we set by hand
```
- **Knock-on:** none.
- **Risk:** low. (Shower audit items 5, 11)

### B49. The tank's usable 40 gallons is an assumption

- **Where:** `paper/paper_draft_v2.tex:608`.
- **Problem:** "against the roughly 40 gallons the tank can usefully supply". The 0.8
  availability factor behind it is our assumption (main:1088 discloses it; main:608 does not).
- **Why it matters:** the worked example reads as measured.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
against the roughly 40 gallons the tank can usefully supply
```
```new
against the roughly 40 gallons we assume the tank can usefully supply
```
- **Knock-on:** none.
- **Risk:** none. (Shower audit item 13)

### B50. The pointer to Appliance and Shower "full derivations" in S1

- **Where:** `paper/paper_draft_v2.tex:620`.
- **Problem:** "We outline the Appliance and Shower calculators here and give their full
  derivations in Supplementary Material S1". S1 has no Appliance or Shower derivation; it has the
  monthly-cost conversions (Section "Monthly-Cost Conversions"), the TOU rates (Table S1.6) and
  the parameter bands.
- **Why it matters:** a dangling pointer.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
give their full derivations in Supplementary Material S1
```
```new
give their monthly-cost conversions, rate tables and parameter bands in Supplementary Material S1
```
- **Knock-on:** none.
- **Risk:** none. (Shower audit item 20)

### B51. Flow-tier text vs code, and GPM above the federal maximum

- **Where:** `paper/supplementary.tex:574`.
- **Problem:** The text gives `standard` as "2.5--3.0\,GPM"; the single-source helper
  `sentinel_utils.gpm_to_flow_rate_label` defines it as above 2.0 and up to 3.0. No scenario lies
  between 2.0 and 2.5, so no label changes. Eleven of the 80 Shower master scenarios
  (`Scenario Files/ShowerScenarios.xlsx`) sit at 3.5-4.0 GPM, above the 2.5 GPM federal maximum
  that the same sentence cites; the text does not say so.
- **Why it matters:** text disagrees with the code, and the dataset exceeds a limit the text
  cites without comment.
- **Options:** one.
- **Edits:**

```old paper/supplementary.tex
\texttt{standard} (2.5--3.0\,GPM, at or near
```
```new
\texttt{standard} ($>$2.0 to 3.0\,GPM; every standard scenario lies at 2.5--3.0\,GPM, at or near
```
```old paper/supplementary.tex
and \texttt{high\_flow} ($>$3.0\,GPM).
```
```new
and \texttt{high\_flow} ($>$3.0\,GPM; 11 of the 80 Shower scenarios sit at 3.5--4.0\,GPM, above the federal maximum, as fixtures installed before it took effect can).
```
- **Knock-on:** none.
- **Risk:** low. (Shower audit item 17)

### B52. Disclose the hvac_age = 95 scenario

- **Where:** `paper/supplementary.tex:565`.
- **Problem:** One HVAC scenario (Stroudsburg, SEER 8, house age 102; `Scenario Files/HVACScenarios.xlsx`
  row 30) has an HVAC age of 95 years, above $\mathcal{A}_{\text{H}}$'s own validation bound of
  60 (`LLM-Parameterized_Reference_Scoring.py:182`). It is rank-neutral: degradation reaches its
  30% cap at 40 years.
- **Why it matters:** implausible data a reviewer can find in the released workbook.
- **Options:** disclose (recommended); or edit the scenario (a data change, which would require
  the rebuild workflow).
- **Edit:**

```old paper/supplementary.tex
(\ref{app:rag_corpus}).
```
```new
(\ref{app:rag_corpus}). One HVAC scenario (Stroudsburg) carries an HVAC equipment age of 95 years, above the 60-year bound we apply to $\mathcal{A}_{\text{H}}$'s extractions; it does not affect its ranking, because efficiency degradation stops at 40 years.
```
- **Knock-on:** none.
- **Risk:** none. (HVAC audit item 16)

### B53. SEER 16-22 "Most Efficient" label; insulation tiers are wall values we set

- **Where:** `paper/supplementary.tex:570`.
- **Problem:** (1) "high-efficiency models (SEER~16--22), consistent with the ENERGY STAR Most
  Efficient threshold". ENERGY STAR v6.1 sets split central AC at 15.2 SEER2 and 12.0 EER2, the
  ordinary ENERGY STAR level (about SEER 16), not Most Efficient. (2) "Each insulation tier spans
  a range of R-values drawn from standard U.S. residential wall assemblies": CEC JA4.3 tabulates
  R-11, R-13 and R-15 for 2x4 walls and R-19 to R-22 for 2x6; the tier bands R-8-12 / 13-18 /
  19-24 are ours around those values.
- **Why it matters:** overstates two sources.
- **Options:** one.
- **Edits:**

```old paper/supplementary.tex
consistent with the ENERGY STAR Most Efficient threshold \citep{energystar_ac2023}.
```
```new
consistent with the ENERGY STAR threshold of 15.2~SEER2 \citep{energystar_ac2023}.
```
```old paper/supplementary.tex
Each insulation tier spans a range of R-values drawn from standard U.S.\ residential wall assemblies \citep{cec_ja43_2013,energystar_insulation2023}:
```
```new
Each insulation tier spans a range of wall R-values that we set around standard U.S.\ residential wall assemblies \citep{cec_ja43_2013,energystar_insulation2023}:
```
- **Knock-on:** README:327 and CLAUDE.md:66 (B70, B77).
- **Risk:** low. (HVAC audit items 12, 13)

### B54. "Typical values of the Pennsylvania housing stock"

- **Where:** `paper/paper_draft_v2.tex:1071` (Section 6.1).
- **Problem:** "On HVAC, an R-15, SEER-13 default sits near the typical values of the
  Pennsylvania housing stock these scenarios draw on." No citation; the audit found test-set
  medians of R-15.5 and SEER 13 (the HVAC-age default of 13 years sits below the test median
  of 18). The claim is about this dataset, not the state's stock.
- **Why it matters:** an uncited claim about the real housing stock.
- **Options:** one.
- **Edit:**

```old paper/paper_draft_v2.tex
sits near the typical values of the Pennsylvania housing stock these scenarios draw on.
```
```new
sits near the median R-value and SEER of the test scenarios.
```
- **Knock-on:** the paragraph's last sentence ("These results describe how closely the defaults
  match this dataset's housing stock...") already says the same thing. Drop if the deferred
  Section 6.1 rewrite (A12) replaces the sentence.
- **Risk:** low. (HVAC audit item 14)

### B55. Swing table: name the corpus

- **Where:** `paper/supplementary.tex:779` (Table S2.1 caption).
- **Problem:** The HVAC swings 0.027/0.032/0.086/0.015 and Shower 0.108/0.128/0.070/0.053
  reproduce only on the 285 test and RAG scenarios; test-only values are 0.025/0.028/0.083/0.013
  (HVAC) and 0.115/0.136/0.067/0.052 (Shower). The caption does not say.
- **Why it matters:** A11.2 quotes this table's pooled values for the environmental-swing finding.
- **Options:** one.
- **Edit:**

```old paper/supplementary.tex
\caption{Mean within-scenario swing (nominal weight $\times$ within-scenario score range) by criterion and decision type}
```
```new
\caption{Mean within-scenario swing (nominal weight $\times$ within-scenario score range) by criterion and decision type, over the 285 test and RAG scenarios}
```
- **Knock-on:** A11.4 proposes the identical caption; apply it once. A11.2 already names the
  285-scenario scope.
- **Risk:** none. (HVAC audit item 19; Shower audit item 21)

---

## Group 4: supplement

### B56. DeepSeek's reasoning-scaffold drop explained with GPT-OSS's success rate

- **Where:** `paper/supplementary.tex:1246`.
- **Problem:** The paragraph explains DeepSeek's $\mathcal{A}_{\text{E}}$ Top-1 drop (55.2% ->
  36.7%) and then says: "The reasoning-scaffold variant also has the lowest success rate in the
  matrix (0.961 for $\mathcal{A}_{\text{E}}$ with GPT-OSS, against 1.000 for the rescaled-response
  variant), so part of its effect is a parsing failure". 0.961 is GPT-OSS's rate. DeepSeek's own
  reasoning-scaffold $\mathcal{A}_{\text{E}}$ success rate is 0.999
  (`Analysis/Prompt_Ablation/prompt_ablation_summary.xlsx`, sheet `summary`, row
  cot_scaffold/AE/deepseek: 0.998974), so parsing failures do not explain DeepSeek's drop.
- **Why it matters:** the explanation uses another model's number and points the wrong way.
- **Options:** one.
- **Edit:**

```old paper/supplementary.tex
The reasoning-scaffold variant also has the lowest success rate in the matrix (0.961 for $\mathcal{A}_{\text{E}}$ with GPT-OSS, against 1.000 for the rescaled-response variant), so part of its effect is a parsing failure: the pipeline could not recover the scores from a long block of reasoning text.
```
```new
Parsing failures do not explain DeepSeek's drop: its reasoning-scaffold cell scored 0.999 of its scenario-runs. The lowest success rate in the matrix belongs to GPT-OSS's $\mathcal{A}_{\text{E}}$ reasoning-scaffold cell (0.961, against 1.000 for its rescaled-response cell), where the pipeline could not recover the scores from a long block of reasoning text.
```
- **Knock-on:** none.
- **Risk:** low. (cheap-fix 17)

### B57. Dangling "per the main text's timestamp convention"

- **Where:** `paper/supplementary.tex:1342-1343`.
- **Problem:** "five reversed-order extraction runs, per the main text's timestamp convention."
  The main text has no timestamp convention. (Whether runs carry timestamps is A9's topic.)
- **Why it matters:** a pointer to nothing.
- **Options:** one; delete the phrase.
- **Edit:**

```old paper/supplementary.tex
five reversed-order extraction runs, per the main text's timestamp
convention. \texttt{Miscellaneous Scripts/experiments/run\_hybrid\_ablation\_experiments.py}
```
```new
five reversed-order extraction runs.
\texttt{Miscellaneous Scripts/experiments/run\_hybrid\_ablation\_experiments.py}
```
- **Knock-on:** none.
- **Risk:** none. (review audit row 20; cheap-fix 16)

### B58. Alpha-sweep figure overfull by 2.2 pt

- **Where:** `paper/supplementary.tex:142` (`\plotAlphaSweep`).
- **Problem:** A diagnostic compile of the current file (scratchpad copy) logs "Overfull \hbox
  (2.23358pt too wide) in paragraph at lines 918--919". Three panels at 0.34\textwidth plus two
  1.6 cm gaps exceed the text width. With 1.5 cm the warning disappears (tested in the same
  scratchpad build).
- **Why it matters:** cosmetic; one number.
- **Options:** one.
- **Edit:**

```old paper/supplementary.tex
    group style={group size=3 by 1, horizontal sep=1.6cm},
```
```new
    group style={group size=3 by 1, horizontal sep=1.5cm},
```
- **Knock-on:** the main file has an unused copy of the macro (B67).
- **Risk:** none.

### B59. Hyperref bookmark warning on the "Worked Example" title

- **Where:** `paper/supplementary.tex:655`.
- **Problem:** The log shows "Token not allowed in a PDF string (Unicode): removing `subscript'
  on input line 655". The PDF-string argument is `{A_H}`; the other subsection titles use
  `{A\_D}` and `{A\_E}`. The fixed version compiles without the warning (tested).
- **Options:** one.
- **Edit:**

```old paper/supplementary.tex
\subsection{Worked Example: \texorpdfstring{$\mathcal{A}_{\text{H}}$}{A_H} HVAC Scenario}
```
```new
\subsection{Worked Example: \texorpdfstring{$\mathcal{A}_{\text{H}}$}{A\_H} HVAC Scenario}
```
- **Risk:** none.

### B60. Both ablations compute tau_b on scores without the benchmark's tie-break

- **Where:** `paper/supplementary.tex:930` (end of "Ablation Data Provenance"); coordinate with
  A4.8, which names the same tie-break difference for the prompt-ablation control at S L1237.
- **Problem (new finding, read-only check):** main:476 says the benchmark breaks every tie, so a
  scenario's $\tau$ is one of $-1, -\frac{1}{3}, \frac{1}{3}, 1$; `Analysis/per_scenario_metrics_all.csv`
  confirms only those four values. The ablation outputs do not follow that rule. In
  `Analysis/Prompt_Ablation/prompt_ablation_summary.xlsx` (sheet `per_scenario`, 30,420
  scenario-runs) the per-scenario $\tau$ also takes $\pm0.8165$ (1,739 rows), 0 (812), $\pm0.5$
  (17) and undefined (214): Kendall's $\tau_b$ on tied scores. The share of such values runs
  from 3.6% (reasoning-scaffold cells) to 12.3% ($\mathcal{A}_{\text{D}}$ control).
  `Analysis/RAG_Ablation/rag_ablation_results.xlsx` shows the same pattern (about 17% of rows).
  This is a third reason, after the 10 runs and the earlier Shower comfort function, why the
  prompt-ablation control differs from the main benchmark (e.g., $\mathcal{A}_{\text{D}}$ Qwen
  $-0.052$ against 0.010).
- **Why it matters:** the main text quotes ablation $\tau$ values as if computed the benchmark's
  way.
- **Options:** (a) disclose in S2 (recommended, no recomputation); (b) recompute both ablations'
  $\tau$ with the benchmark tie-break offline (the per-alternative scores are in the per-cell
  files), then update Tables S2.5 and S2.8 and the main-text figure: a larger job, outside this
  batch.
- **Edit (option a):**

```old paper/supplementary.tex
The headline results in the main text use the corrected reference throughout.
```
```new
The headline results in the main text use the corrected reference throughout. Both ablation suites also compute each scenario's Kendall's $\tau$ as $\tau_b$ on the raw aggregate scores, without the tie-break the main benchmark applies, so a choice set with tied scores takes a value such as $\pm0.816$ or 0, or no value when all three alternatives tie; 4--12\% of prompt-ablation scenario-runs per cell carry such values.
```
- **Knock-on:** A4.8's supplement note already names this reason for the prompt-ablation
  control; A4.6's main-text clause in Section 5.5 points to the supplement and needs no change.
- **Risk:** author (changes what the ablation numbers mean; option b may be preferred).

### B61. Optional: the remaining overfull boxes in the supplement

- **Where:** `paper/supplementary.tex:176` (the hyperref line the fix edits), `:201` (model identifiers, 100 pt), `:973` (a file path,
  134 pt), `:718-730` (Table S1.5, 93 pt), `:1518-1552` (Table S2.16, 52 pt twice),
  `:1280-1292` (Table S2.10, 21 pt), `:463-465` (exemplar lines, 45 pt).
- **Problem:** Elsevier publishes supplementary files as supplied, so text running into the
  margin stays visible. Two fixes tested in the scratchpad build remove the two worst:
  load `xurl` and set the model identifiers and the path with `\nolinkurl`, which breaks at
  slashes without creating links.
- **Edits (tested):**

```old paper/supplementary.tex
\usepackage[hidelinks]{hyperref}
```
```new
\usepackage{xurl}
\usepackage[hidelinks]{hyperref}
```
```old paper/supplementary.tex
\texttt{Analysis/RAG\_Ablation/rag\_ablation\_bootstrap\_ci.xlsx}
```
```new
\nolinkurl{Analysis/RAG_Ablation/rag_ablation_bootstrap_ci.xlsx}
```
  and at supp:201 replace each of `\texttt{openai/gpt-oss-20b:exacto}`,
  `\texttt{qwen/qwen3.5-9b:exacto}`, `\texttt{deepseek/deepseek-v4-flash:exacto}`,
  `\texttt{google/gemini-3.5-flash:exacto}` with the same text in `\nolinkurl{...}`.
  For Tables S1.5 and S2.16, `\setlength{\tabcolsep}{3pt}` before the tabular, or wrapping the
  tabular in `\resizebox{\textwidth}{!}{...}` (graphicx is loaded), would fit them; not tested.
- **Risk:** none.

---

## Group 5: submission hygiene

### B62. Co-author TODO comments and the todonotes package

- **Where:** `paper/paper_draft_v2.tex:22`, `:23`, `:30-31`, `:349`.
- **Problem:** Lines 22-23 hold the co-author's review comments as `%todo*:` source comments; line
  349 holds `%todo: ask about formatting (huang) and whether there shoud be a title`; line 31
  loads `todonotes`, and line 30 sets `\marginparwidth` for it. No `\todo` command remains in the
  body. Comments ship in the submitted source.
- **Why it matters:** the editor flagged them; the submission source is visible to reviewers.
- **Options:** one; delete after the author has acted on them (B18 answers line 22's third
  point).
- **Edits:** delete these lines entirely.

```old paper/paper_draft_v2.tex
%todo*:As said, you shouldn't have subsection right after a section title without any text
```
```new
```
```old paper/paper_draft_v2.tex
\setlength{\marginparwidth}{2cm}
\usepackage{todonotes}
```
```new
```
```old paper/paper_draft_v2.tex
%todo: ask about formatting (huang) and whether there shoud be a title
```
```new
```
  and delete line 22 (the single long `%todo*: he.huang 29 August, ...` line) the same way.
- **Knock-on:** check the compile after removing `todonotes`: it loads `xcolor` and `tikz`,
  which the preamble loads itself (lines 13, 28), so nothing should break.
- **Risk:** none. (cheap-fix 35)

### B63. Harmonize the citation style between main text and supplement

- **Where:** `paper/supplementary.tex:177`, `:1556`; `paper/paper_draft_v2.tex:1144`.
- **Problem:** The main text uses `elsarticle-num-names` (numeric); the supplement loads natbib
  with `authoryear` and `cas-model2-names` (author-year).
- **Why it matters:** the editor asked for one style.
- **Options:** (a) make the supplement numeric like the main text (recommended; two lines);
  (b) make both author-year: check the EMS Guide for Authors, since Elsevier journals accept any
  consistent style at first submission.
- **Edits (option a):**

```old paper/supplementary.tex
\usepackage[authoryear,longnamesfirst]{natbib}
```
```new
\usepackage[numbers,sort&compress]{natbib}
```
```old paper/supplementary.tex
\bibliographystyle{cas-model2-names}
```
```new
\bibliographystyle{elsarticle-num-names}
```
- **Knock-on:** the supplement's `\citet` calls then print "Mayer et al. [n]"; B32's `\citealt`
  suggestion falls back to the alternative wording.
- **Risk:** author (style choice). (cheap-fix 36)

### B64. Pennsylvania emissions figure caption lacks a data source

- **Where:** `paper/paper_draft_v2.tex:346`; new bib entry.
- **Problem:** "Pennsylvania residential emissions from on-site fuel combustion, by fuel,
  2005--2022." No source. The figure script (`paper/Images/make_pa_emissions_figures.py`)
  hard-codes MMTCO2e values by fuel; the repository's `Analysis/PA_GHG_Inventory_2026.pdf` is
  the Pennsylvania DEP eLibrary download page for "Pennsylvania Greenhouse Gas Inventory Report
  2026" (docId 11247211), not the report itself. The companion figure's caption (main:356)
  already names its source.
- **Why it matters:** the editor asked; the author decided to keep the figure (2026-09-24).
- **Options:** one; confirm the numbers came from that report first.
- **Edit:**

```old paper/paper_draft_v2.tex
\caption{Pennsylvania residential emissions from on-site fuel combustion, by fuel, 2005--2022.}
```
```new
\caption{Pennsylvania residential emissions from on-site fuel combustion, by fuel, 2005--2022 (data from \citet{padep_ghg2026}).}
```
```new-bib paper/cas-refs.bib
@techreport{padep_ghg2026,
  author = {{Pennsylvania Department of Environmental Protection}},
  title = {Pennsylvania Greenhouse Gas Inventory Report 2026},
  institution = {Pennsylvania Department of Environmental Protection},
  year = {2026},
  note = {DEP eLibrary document 11247211},
}
```
- **Risk:** low (author confirms the data source). (simulated panel's list of already-decided items)

### B65. Uncited bibliography entries

- **Where:** `paper/cas-refs.bib`.
- **Problem:** A cross-check of every `\cite` key in both files against the bib found 14 entries
  cited nowhere: aqilah2022, ariely2001, neep2015, ohler2020, roszkowska2026, nistsp1270,
  epa1974noise, doehesscore2021, zharova2024, abdidin2024, shen2021, marini2017, wilkes2005,
  rouleau2019. BibTeX omits them, so the reference list is unaffected. After B36, B38 and B47,
  energystar_products, firstenergy2026 and zhang2023 join the list. No cited key is missing.
- **Options:** delete them for tidiness, or leave them.
- **Risk:** none.

### B66. BibTeX "empty pages" warnings

- **Where:** `paper/cas-refs.bib:456` (lewis2020; the edited booktitle line is `:459`), `:474`
  (wei2022cot; booktitle `:477`); sclar2024promptsensitivity.
- **Problem:** The main build logs "empty pages in lewis2020", "... sclar2024promptsensitivity",
  "... wei2022cot". NeurIPS proceedings have page ranges; ICLR does not.
- **Edits:** add a `pages` line (verify each range on the proceedings page):

```old paper/cas-refs.bib
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS) 33},
```
```new
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS) 33},
  pages = {9459--9474},
```
```old paper/cas-refs.bib
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS) 35},
```
```new
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS) 35},
  pages = {24824--24837},
```
  Leave sclar2024promptsensitivity's warning (no pages exist).
- **Risk:** none.

### B67. Optional: two unused plot macros in the main preamble

- **Where:** `paper/paper_draft_v2.tex:87-178` (`\plotDecisionTypeByModel`) and `:242-277`
  (`\plotAlphaSweep`).
- **Problem:** Both figures moved to the supplement, which defines its own copies; the main text
  never calls these two (only `\plotCriterionMAEByModel` and `\plotRagAblation` are used). They
  add 130 lines of dead source that a reviewer reading the source may take for live data.
- **Options:** delete both `\newcommand` blocks, or leave them; output does not change.
- **Risk:** none.

---

## Group 6: repository

### B68. README lists one author

- **Where:** `README.md:3`, `:5`, `:513-515`.
- **Problem:** "**Author:** Ahaan Nigam" and "**Collaborator:** River Huang, Paul Scherrer
  Institut (PSI), Switzerland". The paper (main:291-302) and `CITATION.cff` list both as authors.
- **Edits:**

```old README.md
**Author:** Ahaan Nigam
```
```new
**Authors:** Ahaan Nigam; River Huang (Paul Scherrer Institut, Switzerland)
```
```old README.md
**Collaborator:** River Huang, Paul Scherrer Institut (PSI), Switzerland
```
```new
```
```old README.md
## Citation / Collaborator
```
```new
## Citation
```
- **Knock-on:** the paragraph under that heading ("This project is being developed into a
  journal paper with **River Huang ...**") can stay or point to `CITATION.cff`.
- **Risk:** none. (cheap-fix 34)

### B69. `git clone <repository-url>` placeholder

- **Where:** `README.md:33`.
- **Edit:** (URL from main:1130)

```old README.md
git clone <repository-url>
```
```new
git clone https://github.com/AN00927/LLM-MCDA-Paper.git
```
- **Risk:** none. (cheap-fix 34)

### B70. README R-value table contradicts the supplement

- **Where:** `README.md:327`.
- **Problem:** "| **HVAC - Insulation** | Poor / Medium / Good | R-11 / R-13 / R-19 | ..." The
  scenario data and supp:570 use tiers R-8-12, R-13-18, R-19-24, and the calculator scores each
  scenario's own R-value.
- **Edit:**

```old README.md
| **HVAC - Insulation** | Poor / Medium / Good | R-11 / R-13 / R-19 | CEC JA4.3; ENERGY STAR |
```
```new
| **HVAC - Insulation** | Poor / Medium / Good | scenario R-value (tiers R-8-12 / R-13-18 / R-19-24) | CEC JA4.3; ENERGY STAR |
```
- **Knock-on:** CLAUDE.md:66 (B77).
- **Risk:** none. (review audit row 19; cheap-fix 15)

### B71. README: "true age in years -> kWh/cycle"

- **Where:** `README.md:329`.
- **Problem:** The Appliance calculator never reads age; it scores the scenario's own kWh/cycle
  (supp:572). The values are not all ENERGY STAR-certified (B43).
- **Edit:**

```old README.md
| **Appliance - Age** | banded age label | true age in years -> kWh/cycle | ENERGY STAR certified datasets |
```
```new
| **Appliance - Age** | banded age label | scenario kWh/cycle (the calculator does not read age) | ENERGY STAR and DOE test procedures (cycles/year) |
```
- **Risk:** none. (Appliance audit item 14)

### B72. README: range heading, mains model, heater efficiency

- **Where:** `README.md:345`, `:404`, `:416` (the EER line, :392, is in B26).
- **Edits:**

```old README.md
### Reference Ranges (5th-95th percentile of scenario distributions)
```
```new
### Reference Ranges (5th-95th percentiles over the 285 test + RAG scenarios; HVAC environmental bounds convert the HVAC cost percentiles)
```
```old README.md
(45 F winter to 65 F summer, NREL seasonal model)
```
```new
(45 F at or below 32 F outdoors to 65 F at or above 75 F, a linear approximation to the Burch & Christensen (2007) seasonal model that runs about 2-5 F cool for Pennsylvania)
```
```old README.md
where eta = 0.92 (electric water-heater efficiency).
```
```new
where eta = 0.92 (electric water-heater efficiency; the federal minimum in 10 CFR 430.32(d) is 0.9307 - 0.0002 x V_r = 0.9207 for a 50-gal tank).
```
- **Risk:** low. (Shower audit items 2, 4; HVAC audit items 9, 10)

### B73. README: "Three ablation suites" lists four; the CLAUDE.md pointer

- **Where:** `README.md:450`, `:444`.
- **Problem:** "Three ablation suites, run on top of the main benchmark, ... All three cover the
  same four models" introduces four bullets (prompt, RAG, parameter provenance, alternative
  ordering). README:444 sends readers to `CLAUDE.md`, an agent operating guide, for the
  no-pooling convention.
- **Edits:**

```old README.md
Three ablation suites, run on top of the main benchmark,
```
```new
Four ablation suites, run on top of the main benchmark,
```
```old README.md
All three cover the same four models
```
```new
All four cover the same four models
```
```old README.md
Per the project's no-pooling-across-models convention (see `CLAUDE.md`),
```
```new
Per the project's no-pooling-across-models convention,
```
- **Knock-on:** the panel also suggested moving the rules README cites from CLAUDE.md into
  `docs/`; not proposed here (it creates files).
- **Risk:** none. (cheap-fix 34)

### B74. README research question differs from the paper's

- **Where:** `README.md:12`.
- **Problem:** README: "Which LLM-assisted architecture most accurately reproduces a deterministic
  reference ranking for rapid household energy decisions, and how consistently does that ordering
  hold across models of varying capability and cost?" The paper poses RQ1/RQ2 (main:324-325),
  which B18 may turn into a proposition plus one RQ.
- **Options:** copy the paper's final wording after B18 is decided.
- **Risk:** author (depends on B18). (review R3 minor)

### B75. requirements.txt: add matplotlib, pin torch

- **Where:** `requirements.txt:2-3` (chromadb, numpy) and `:13` (tabulate).
- **Problem:** `paper_pipeline/generate_grouped_bars_figure.py` (and the two figure scripts in
  `paper/Images/`) import matplotlib, which the file omits; torch, pulled in by
  sentence-transformers, is unpinned. The project `.venv` has matplotlib 3.11.0 and torch 2.11.0
  (dist-info folders in `.venv/Lib/site-packages`).
- **Edits:**

```old requirements.txt
chromadb==1.5.2
numpy==2.4.2
```
```new
chromadb==1.5.2
matplotlib==3.11.0
numpy==2.4.2
```
```old requirements.txt
tabulate==0.10.0
```
```new
tabulate==0.10.0
torch==2.11.0
```
- **Knock-on:** the `.venv` also has transformers 5.8.0; pinning it too would fix the embedding
  stack completely (optional).
- **Risk:** none. (cheap-fix 33; review R3 major 2)

### B76. Calculator code comments that credit the wrong source (comments only)

- **Where:** the three files in `Ground Truth Calculators/`. No code behavior changes; every
  edit below is inside a `#` comment or docstring.
- **Edits:**

HVAC, line 136 (EER source; see B26):
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
# EER = -0.02 * SEER^2 + 1.12 * SEER  (Source: AHRI Standard 210/240)
```
```new
# EER = -0.02 * SEER^2 + 1.12 * SEER  (Source: Building America House Simulation Protocols, Hendron & Engebrecht 2010, Eq. 3, citing Wassmer 2003)
```
HVAC, line 35 (ACH; ASHRAE 62.1 did not exist in 1989; the 1989 standard is 62-1989):
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
# modern/average-construction default (also the ASHRAE 62.1-1989 whole-house baseline).
```
```new
# modern/average-construction default (also the ASHRAE Standard 62-1989 minimum of 0.35 ACH in living areas).
```
HVAC, lines 28-30 (rate; the paper describes 0.19 as a bundled default-service rate):
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024 rising to
    # ~19-21 c/kWh through 2025 -- 0.19 is a defensible flat-rate proxy).
```
```new
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024). 0.19 is the bundled default-service
    # rate (supply + delivery + riders) the paper derives from PA PUC (2025), not an EIA figure.
```
HVAC, line 62 (envelope multipliers; see B31):
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
# Adjust by housing type. Typical multipliers from ACCA Manual J:
```
```new
# Adjust by housing type. Our multipliers, set by exposure (not a Manual J table):
```
HVAC, lines 82 and 119 (internal gains, cooling and heating branches; the same comment appears
twice, so apply the edit at both places; see B30):
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
        # Source: ASHRAE Handbook of Fundamentals, Chapter 18, Table 1
        internal_gains = (household_size * 400) + (square_footage * 1.0) + 800

        window_area
```
```new
        # Occupant gain per ASHRAE Fundamentals Ch. 18 Table 1 (400 = sensible + latent); 1.0/sqft and 800 are our assumptions
        internal_gains = (household_size * 400) + (square_footage * 1.0) + 800

        window_area
```
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
        # Same formula as cooling load: occupants + lighting/equipment + baseline
        # Source: ASHRAE Handbook of Fundamentals, Chapter 18, Table 1
```
```new
        # Same formula as cooling load: occupants + lighting/equipment + baseline
        # Occupant gain per ASHRAE Fundamentals Ch. 18 Table 1 (400 = sensible + latent); 1.0/sqft and 800 are our assumptions
```
HVAC, line 435 (free-float offsets; the paper, main:724, calls them our assumption):
```old Ground Truth Calculators/HVACGroundTruthCalculator.py
Sources: de Dear & Brager (2002) / ASHRAE 55-2020 (free-running adaptive
```
```new
Modeling assumption, not tabulated by these sources: de Dear & Brager (2002) / ASHRAE 55-2020 (free-running adaptive
```
Shower, line 18 (docstring; showers/day is an assumption, supp:613 says so):
```old Ground Truth Calculators/ShowerGroundTruthCalculator.py
- DeOreo et al. (2016). Average shower 7.8 min; 0.9 showers/person/day.
```
```new
- DeOreo et al. (2016). Average shower 7.8 min. (0.9 showers/person/day is our assumption.)
```
Shower, line 447:
```old Ground Truth Calculators/ShowerGroundTruthCalculator.py
showers_per_person_per_day=0.9  # Q21: REU2016 average
```
```new
showers_per_person_per_day=0.9  # assumption; Mayer et al. (1999) measured 0.75 showers+baths/person/day
```
Shower, lines 27-28 (same rate comment as HVAC):
```old Ground Truth Calculators/ShowerGroundTruthCalculator.py
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024 rising to
    # ~19-21 c/kWh through 2025 -- 0.19 is a defensible flat-rate proxy).
```
```new
    # (Table 2.10; PA residential avg 17.77 c/kWh in 2024). 0.19 is the bundled default-service
    # rate (supply + delivery + riders) the paper derives from PA PUC (2025), not an EIA figure.
```
Shower, line 32 (mains temperature; see B47):
```old Ground Truth Calculators/ShowerGroundTruthCalculator.py
# Sources: Burch & Christensen (2007), OSTI 981988; Maguire et al. (2013), NREL/TP-5500-58756.
```
```new
# Our linear approximation to Burch & Christensen (2007), OSTI 981988 (a sinusoid that runs ~2-5 F warmer for PA); see also Maguire et al. (2013), NREL/TP-5500-58756.
```
Shower, line 40 (heater efficiency; add the federal source):
```old Ground Truth Calculators/ShowerGroundTruthCalculator.py
#         Product Specifications (electric models 40-55 gal). Midpoint: 0.92.
```
```new
#         Product Specifications (electric models 40-55 gal). Midpoint: 0.92.
    # Federal minimum: 10 CFR 430.32(d), 0.9307 - 0.0002 x Vr = 0.9207 at 50 gal.
```
Shower, line 42 (delivery temperature; see B48):
```old Ground Truth Calculators/ShowerGroundTruthCalculator.py
# F, upper end of the comfortable shower delivery band (~98-105F); Zhang et al. (2023)
```
```new
# F, our delivery convention; Zhang et al. (2023) assume 89.6-104 F (32-40 C)
```
Appliance, lines 440-441 (the supplement calls the association moderate; see B43):
```old Ground Truth Calculators/ApplianceGroundTruthCalculator.py
# appliance type the dataset's per-cycle energy is strongly
```
```new
# appliance type the dataset's per-cycle energy is moderately
```
Appliance, line 36 (PPL label; see B39):
```old Ground Truth Calculators/ApplianceGroundTruthCalculator.py
# PPL Rate RTS: summer peak 2-6pm modeled;
```
```new
# PPL GSC-1 TOU (Rate Schedules RS/RTS); rates below do not match Supp. 393 (see paper S1): summer peak 2-6pm modeled;
```
Appliance, line 32 (FirstEnergy multipliers; see B38):
```old Ground Truth Calculators/ApplianceGroundTruthCalculator.py
# Jun-2025 PTCs (FirstEnergy Corp. (2025)) x fixed multipliers (FirstEnergy Corp. (2026))
```
```new
# Jun-2025 PTCs (FirstEnergy Corp. (2025)) x fixed multipliers (FE PA tariff Supplement No. 20, PA PUC doc 1875621)
```
- **Knock-on:** the Appliance comment at line 48 says the city-to-utility map was "verified
  against PA PUC service-territory maps"; the audit found six cities misassigned (Indiana,
  Carlisle, Reading, Lebanon, State College, Chambersburg; rank-neutral). Add a note only if the
  author wants the discrepancy recorded in code.
- **Risk:** none (comments only; calculators produce identical output).

### B77. CLAUDE.md: R-11/13/19 (the author's file; needs approval)

- **Where:** `CLAUDE.md:66`.
- **Problem:** "`insulation` (Poor/Medium/Good) ⟷ `r_value` (R-11/13/19)" contradicts the data
  (tiers R-8-12 / 13-18 / 19-24).
- **Edit (only with the author's approval):**

```old CLAUDE.md
(Poor/Medium/Good) ⟷ `r_value` (R-11/13/19)
```
```new
(Poor/Medium/Good) ⟷ `r_value` (tiers R-8–12 / R-13–18 / R-19–24)
```
- **Risk:** author (governance file).

### B78. PAPER_STATUS.md is stale

- **Where:** `paper/PAPER_STATUS.md:1` (title), `:13-40` (section 1) and `:164` (section 6).
- **Problem:** Section 1 calls itself the "single source of truth", names
  `paper/supplementary_material.tex` (now `supplementary.tex`) and reports a 34-page build
  (the current main PDF compiles to 28 pages). Section 6's open items are superseded by this
  proposal. Sessions that read this file first get wrong instructions.
- **Edits:**

```old paper/PAPER_STATUS.md
# Paper status — single source of truth
```
```new
# Paper status (historical; superseded)

**Current entry point: `paper/pass5/PASS5_PROPOSAL.md`.** Sections 1 and 6 below are
superseded; the rest is kept for history.
```
```old paper/PAPER_STATUS.md
## 1. Where things stand
```
```new
## 1. Where things stand (superseded 2026-09-25; see paper/pass5/PASS5_PROPOSAL.md)
```
```old paper/PAPER_STATUS.md
## 6. Open items
```
```new
## 6. Open items (superseded 2026-09-25; see paper/pass5/PASS5_PROPOSAL.md)
```
- **Knock-on:** the pointer target, `paper/pass5/PASS5_PROPOSAL.md`, is this file; it now exists.
- **Risk:** none.

---

## Already fixed or verified correct (no edit proposed)

1. **Showers per person per day:** supp:613 already labels 0.9 an assumption against Mayer et
   al.'s 0.75. Only the code comments remain (B76).
2. **HVAC free-float offsets:** main:724 already calls them "our modeling assumption"; only the
   code comment remains (B76).
3. **Budget-penalty constants:** main:670 already says "The values 0.80, 2.5 and 1.5 and the
   exponential form are our own choices"; B29 adds only the jump and its frequency.
4. **GONZALEZTORRES2022112428** (main:341, "20% of global CO2 emissions" and HVAC "roughly a
   third of global residential energy consumption"): the bib entry's own abstract says "a fifth
   of CO2 emissions in 2019" and "HVAC systems account for a third of residential consumption".
   Correct.
5. **heymann2026ai** (main:765, "under Monte Carlo weight uncertainty a ranking can hold at its
   extremes while its middle positions shift"): the paper (`temppapers/1-s2.0-S0142061526004035-main.pdf`)
   reports that "the best and worst alternatives are highly stable, while rank uncertainty is
   concentrated" in the middle positions. Correct.
6. **Dietz 7.4%** (main:341): Dietz et al. write "123 MtC/yr, or 7.4% of total national
   emissions" (`temppapers/dietz-...pdf`). Correct. The paper then applies the share to
   energy-related CO2 (4,904 Mt), a narrower base; optional wording "Applying the same share to
   the narrower base of" if the author wants it flagged.
7. **Goodell "future work" sentence** (main:1083, "they name that test as future work"):
   confirmed by the paper's p. 8 (see B19). Correct.

## How the old strings were checked

`Analysis/pass5/audit_old_strings.py` (read-only) extracts every old string in Parts A and B
(60 in Part A, 130 in Part B), searches the file each one names, and compares the line it
finds with the line the item states; it also flags old strings that overlap or share a file line
and checks Part A's insertion anchors. Its results are in
`Analysis/pass5/audit_old_strings_results.csv`. As of 2026-09-25, 189 of the 190 old strings
occur exactly once in their files, at the line the item states. The other one, A3.2's, is the
end of A3.1's new text and exists only after A3.1 is applied. Four pairs of items edit the same
span (B27/B30, A2.7/B16, A2.8/A4.2, A11.4/B55); each pair gives either identical new text or a
stated rule for which to apply. Part A's "Sentences edited by more than one item" lists them with
the same-paragraph pairs. The diagnostic compiles (B25, B58, B59, B61, B66) ran on copies of the
current files in the session scratchpad; nothing in `paper/` was written. See
`paper/pass5/SELF_CONTAINMENT_AUDIT.md` for the fixes this check prompted.

Part B's author ran no git command. The self-containment audit ran one read-only `git status`
and changed no git state.

---

# Not proposed, and why

- **No calculator changes.** The three calculator audits found no constant that contradicts its
  cited source in a way that forces a value change. The problems are misattributed citations,
  undisclosed assumptions and wrong wording, all fixable in text (Part B, Group 3). This matches
  your scope decision of 2026-08-11 to make no calculator changes for this revision. The rank-sensitive modeling choices are disclosed, not
  changed. Changing them would move these winners:
  - the 70 °F heating optimum: 8 of 70 HVAC winners would move at 71 °F (B32);
  - the season-dependent shower optimum: 7 of 60 Shower winners if removed (B46).
- **No reruns.** No finding needs new API data.
  - The Appliance super off-peak period is disclosed (A10, option A). The alternative, option B,
    is a calculator fix plus an A_E rerun on all 195 scenarios with timestamps, for about $5.60.
    That is offered in A10 but not recommended.
  - A full rerun of every API experiment would cost about $44. It is not needed, and the
    benchmark runs have no collection timestamps, so a rerun could not tell a fix apart from
    the provider changing its models in the meantime.
- **The full-audit alternate plan** was not started. It would audit every constant, formula,
  data row, prompt and statistic, fix errors in code, then recompute offline. It is an
  alternative to this pass, not a step after it, and it runs only if you ask for it by name.
- **Shower Environmental Impact stays in gallons, not CO₂.** Within a scenario the alternatives
  differ only in duration, so CO₂ would copy Energy Cost exactly on every alternative. Gallons at
  least vary 1.5× in cost per gallon across scenarios. A11 fixes the wording that blames PJM
  factors instead.
- **Discussion 6.1 rewrite deferred** (A12). A1–A4 change what it must say.
- **Floats stay in the main text.**
  - Moving Figures 1–2 to the supplement is closed: you decided against it on 2026-09-24,
    because reviewers dislike flipping to the supplement. Answer the panel's request in the
    response letter.
  - Merging Tables 3 and 4, and moving Table 7 or Figure 6 to the supplement, are rejected for
    the same reason.
  - `[H]` placement: measured, it saves no page at 28 pages.
  - Collapsing Table 8 to one sentence: it was the float left alone on a page, and after the
    previous revision pass's text cuts (2026-09-24) it no longer strands a page.
- **"Ground truth" in the literature-review sentence at main L373 and the Table 1 header stays.**
  There it describes *other* studies' validation targets, where "reference" would be ambiguous.
- **Six Pennsylvania cities are assigned to the wrong utility in the Appliance calculator:**
  Indiana, Carlisle, Reading, Lebanon, State College and Chambersburg. Not fixed, because the
  error is rank-neutral: 0 of 65 winners change. Fix it in code only if the reference is ever
  rebuilt.
- **Showers per person per day (0.9 against the source's 0.75 or 0.67) is not changed.** The
  change moves 0 of 60 rankings. The supplement already labels 0.9 as our assumption.
- **Seven paywalled references remain unverified:** keeneyraiffa1976, dyer1979,
  vonnitzsch1993, accamanualj, ashrae55_2020, huang2011 and aamodtplaza1994. They can't be
  checked without the texts. See "Your actions".

# Your actions

**Decisions, in this order:**
1. A1–A4. A2 is the one that changes the paper's contribution statement.
2. The abstract version and the title (A5).
3. Approve or strike A6–A11 and each Part B item. These Part B items touch a claim or a
   rationale only you know, so read them before approving: B2, B10, B11, B16, B17, B18, B20,
   B32, B39, B60, B63 and B74.
4. B77 edits your `CLAUDE.md` (R-11/13/19 → the supplement's tiers). It needs your explicit
   approval.

**Facts only you can supply:**
- **Gemini's A_E Shower rows:** runs 1, 3, 4 and 5 were re-collected (the commit is dated
  August 13). The paper doesn't disclose this. Confirm the scope of the re-collection so A9's
  collection-window sentence is right.
- **Collection dates:** file modification times can't date the runs, and commit dates give only
  upper bounds. If you want real dates in the supplement, check your OpenRouter activity log.
- **Bibliography fields marked "verify" in Part B:** Part B could not confirm these from files in
  the repository:
  - the PECO rate-sheet URL;
  - the year and title of FirstEnergy Supplement No. 20;
  - the Ibáñez-Rueda authors and title;
  - the Building America HSP report number;
  - the IECC table number;
  - the NeurIPS page ranges.
- **B10:** the real reason for the α values the sensitivity sweep uses. The stated reason can't
  be the real one.
- **B11:** whether "19.2 quadrillion BTU" is delivered or total energy (check the EIA Monthly
  Energy Review).
- **The seven paywalled references:** page numbers, if you own the texts.

**After the edits go in:**
- Compile the main text and the supplement in Overleaf.
- **The pipeline scripts would still write the superseded numbers:**
  `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py` (reports the five-run
  consensus arm as "extracted"), `Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py`
  (runs the provenance tests on that arm), `Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py`
  (builds the Table 6 values from the consensus workbook by default, A3) and the `GPTOSS_recovery`
  block in `paper_pipeline/generate_paper_results_numbers.py` (labels the unrecovered 0.897 / 91.7%
  as the recovered figures). A1 corrects the paper, but the next pipeline run would
  bring the old numbers back until those scripts are updated. Say if you want a code change for
  that. It was out of scope tonight, because the scripts were read-only.
- Rerun the number audit and the simulated review after the text batch. The panel's 20-row
  consistency table and `NUMBERS_OF_RECORD.csv` are the regression checklist.

**Before submission:**
- Mint a Zenodo DOI for the release tag.
- Add the EMS hardware and program-size fields.
- Prepare the highlights and a graphical abstract.
- Strip the co-author TODO comments and the `todonotes` package (B62).

---

# Execution order (author decisions of 2026-09-25)

The author has now decided most items. Where a decision below conflicts with a recommendation in
Part A or Part B, the decision wins. Three gates are still open. A step marked with a gate must
not start until the author has settled that gate.

## Open gates

- **G1: rerun.** Pick one:
  - (a) no rerun;
  - (b) fix the calculators, rescore A_H, A_D and the baselines offline, and re-collect only
    A_E and its ablation arms;
  - (c) fix the calculators and re-collect every experiment in one window, with UTC timestamps
    and raw per-call logs.

  The author leans toward (c) and toward option B of the Appliance super off-peak item (A10).
  Any calculator change alters the exemplar scores A_E displays, so A_E must be re-collected
  under (b) and (c).
- **G2: dataset-median baseline.** The shipped condition
  (`Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`, `compute_defaults()`
  and `HIDDEN_PARAMS`) swaps in the corpus median or mode for three facts every question states
  in plain words:
  - Appliance type becomes "dryer" in all 65 Appliance scenarios.
  - Baseline time becomes "2:00 PM".
  - HVAC occupancy becomes "occupied_all_day".

  The corpus it takes medians over (the standalone master sheets, 105 / 100 / 80 rows) also
  includes the 195 test scenarios. The author decides whether the condition keeps this form,
  or takes the stated facts from the scenario sheet the way it already takes household size
  and housing type, and computes the medians over the retrieval scenarios only. Either way no
  parser is involved.
- **G3: title.** The author has not chosen yet. The candidates are in item A5.

## Decisions

| Item | Decision | For the executor |
|---|---|---|
| A1 | **A1-a** (per-run numbers everywhere). A1-b is only an optional sentence about the five-run ensemble and isn't used. | Also fix the scripts that regenerate the ensemble numbers (Step 2). A1.3's dataset-median clause and A1.4–A1.7 wait for G2, because they compare against the dataset-median condition. |
| A2 | **Rejected.** No label-lookup or "fixed default + stated time" baseline appears anywhere: not in the paper, supplement or README. | Drop A2.1–A2.8 and A2.11–A2.12. Keep two factual corrections as ordinary fixes: L945 "exactly" becomes the measured rate (A2.10), and L1083 "the one parameter" is corrected because the run time is also read from the question. Leave out A2.9's parser sentence. Apply B16 on its own. |
| A3 | **A3-a.** | A3.1 and A3.3 (the mechanism sentences) don't depend on any gate. A3.4 and A3.5 (per-run Table 6 and the L945 numbers) take their numbers in Step 4. Skip the optional A3.2. |
| A4 | **All recommendations dropped.** The architectures deliberately don't receive the value functions, the bounds or the budget penalty; that is the study design. | Apply none of A4.2–A4.9. The only remaining work is making the abstract and the Conclusion (L1112) consistent. It happens in Step 5, after G2, and adds no wording about value functions. |
| A5 | **Version 1**, adapted and applied in Step 5. | Replace its last sentence (the lookup result) with the dataset-median result as G2 settles it. Delete "without the reference's value functions" from the direct-scoring clause (A4 decision). Take every number from the final numbers of record. Keep it at 150 words or fewer. Apply the scope swaps (main L328, L330, L415, optionally L873; README L18). |
| A6 | **The listed-order baseline and tie-break inflation are not mentioned anywhere.** | S L203 already lists the tie rates per model and architecture; apply only A6.1 (three corrected A_E rates), in Step 4. Drop A6.2–A6.4. |
| A7 | **Delete the L404 clause** (A7.1, recommended version). **Add the regret sentence** (A7.3). | Place the regret sentence where it reads best (L837 is the proposed spot) and take its numbers in Step 4. No ensemble table (A7.2). No token material in the paper (A7.4–A7.6 dropped). Document the DeepSeek A_D output-token anomaly in the repository only. |
| A8 | **Apply all:** the L320 replacement, the Jakeman/Bennett sentence and the BibTeX entries. | Step 1. |
| A9 | **No edits yet.** The per-run outputs of all 60 benchmark runs exist. What is missing is per-call raw response logs and collection timestamps: only the ordering experiment has raw logs, and no other copy was found on this machine. | Under G1(c), the new runs write both, so README L73 becomes true as written and the undisclosed Gemini A_E Shower re-collection disappears. Under G1(a), apply A9-a. |
| A10 | **Option B favored:** fix the calculator. | Part of G1. Don't disclose. |
| A11 | **A11-a.** | A11.1 and A11.3 go in Step 1. A11.2 (swing numbers) and A11.4 (caption) go in Step 4. |
| A12 | **Rewrite Discussion 6.1**, last. | Step 6. The rewrite accounts for whichever fixes G1 made and whichever limitations remain. |
| Part B | **Apply all**, adjusted by the decisions above. | Classify each item with the rule in Step 1. B16 applies on its own. For B60, fix the ablation pipeline so its tau uses the benchmark's tie-break, instead of disclosing. Items that disclose a calculator error become code fixes under G1(b)/(c) (Step 3). B77 (`CLAUDE.md`) needs the author's explicit approval. B63 (citation style) needs the author's choice. |

## Why this order

Every claim sits on numbers. The numbers sit on the reference calculators and the collected
runs, and the Discussion sits on the claims. Changing them in that order (code, then data, then
numbers, then claims, then Discussion) means each sentence is edited once. Editing prose before
its numbers are final means editing it twice.

## Steps

**Step 0: snapshot.** Before the first edit, copy `paper/paper_draft_v2.tex`,
`paper/supplementary.tex`, `paper/cas-refs.bib` and `README.md` to a new dated folder in
`C:\Users\Ahaan\LLM-MCDA-Paper-snapshots\`.

**Step 1: edits that no gate can change.** These can start now.
- The A8 edits, A3.1 and A3.3, the A7.1 deletion, and A11.1 and A11.3.
- Every Part B item that passes both tests below:
  - its new text contains no number computed from model outputs or from the reference
    calculators;
  - it doesn't describe calculator behaviour that Step 3 may change.

  In practice these are citation and attribution corrections, bibliography fixes, pointers and
  labels, submission hygiene (B62, B64–B67), supplement cosmetics (B57–B59, B61), and README and
  `requirements.txt` fixes that carry no computed number.
- Items that fail either test wait for Step 3 or Step 4.

**Step 2: pipeline code fixes.** These cost $0 and are needed under every G1 option.
1. Make every script that reports A_H use the per-run basis: each run scored separately, failed
   scenario-runs dropped, metrics averaged over runs.
   - `Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py`
   - `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py` (the "extracted" arm)
   - the `GPTOSS_recovery` block in `paper_pipeline/generate_paper_results_numbers.py`
   - the aggregate-workbook default in
     `Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py`

   `Analysis/pass5/d2_reproduce_ah_numbers.py` and `d3_gpm_mechanism.py` hold the reference
   implementations.
2. Compute the ablation suites' tau with the main benchmark's tie-break (B60).
3. Once G2 is settled, implement the dataset-median condition as decided.
4. Add scripted, reproducible outputs for:
   - the tie rates behind S L203 (no script for the published A_E values could be found);
   - the per-run regret;
   - a numbers-of-record CSV generator, starting from `paper/pass5/NUMBERS_OF_RECORD.csv`.
5. **Regression gate:** before and after these changes, the pipeline must reproduce the main
   text's per-run numbers exactly. Commit nothing; the author commits.

**Step 3 (gated on G1): calculator fixes and re-collection.** Skip under G1(a).
1. Fix the calculator errors the author approves. The candidates are in the Part B Group 3
   items and the A10 item: the super off-peak periods, the PPL rates and seasons, the six
   misassigned cities, the heating/cooling branch test, sensible-only internal gains, the
   `hvac_age` = 95 row, and the PJM weekday window. Each fix gets its own regression test.
2. Follow the refresh order in `CLAUDE.md`:
   1. calculator;
   2. regenerate `ground_truth_*.xlsx`;
   3. `sync_rag_ground_truth_scores.py`;
   4. `build_rag_index.py`, bumping `RAG_SCHEMA_VERSION` in both files if the embedding text
      changes.
3. Check that all four OpenRouter `:exacto` model IDs are still served, and record the current
   prices.
4. Re-collect per G1 in one window, with the UTC timestamp and the raw `*_raw.jsonl` log that
   the current code already writes.
5. Run `paper_pipeline/run_paper_pipeline.py`.

**Step 4: numbers.**
1. Regenerate the numbers-of-record CSV.
2. Apply every edit that carries a number, taking each value from the CSV:
   - A1-a;
   - A3.4 and A3.5;
   - A6.1;
   - A7.3;
   - A11.2 and A11.4;
   - Part B Group 1;
   - the A2.10 and L1083 corrections;
   - every other prose number the regeneration moved.
3. Under G1(c), this means refreshing every number in the paper and supplement. Diff the new
   CSV against `paper/pass5/NUMBERS_OF_RECORD.csv` to find them. Re-check every claim whose
   direction could flip:
   - per-model best/worst labels;
   - "for every model" statements;
   - significance calls;
   - the fixed-default comparisons;
   - the reversal cell under the MEREC HVAC weight vector.

**Step 5: claims that depend on G2.**
1. The L808 effect-size sentence, on the dataset-median condition as G2 settles it.
2. Abstract version 1, adapted as in the Decisions table.
3. Make the abstract and the Conclusion (L1112) consistent.
4. The scope swaps.
5. The title (G3).

**Step 6: Discussion 6.1 rewrite (A12).** About 800 words, four claims. Written last, from the
final numbers and from the limitations that remain after Step 3.

**Step 7: verification.**
1. Re-run the old-string check (`Analysis/pass5/audit_old_strings.py`) on any edit prepared
   before the files changed.
2. Diff the paper's numbers against the regenerated CSV.
3. Do a diagnostic compile: pdflatex, bibtex, then pdflatex twice.
4. Re-run the simulated EMS review; its 20-row consistency table is the regression checklist.
5. The author compiles in Overleaf.

## Rerun cost (for G1)

Estimates from the paper's per-run cost table (`tab:item8`, OpenRouter prices on the date given
in S1). Re-check the prices before running.

| Scope | Estimate |
|---|---|
| One run of all three architectures, all four models | ≈ $2.39 (Gemini $2.11, DeepSeek $0.13, Qwen $0.10, GPT-OSS $0.05) |
| Main benchmark, five runs | ≈ $12 (Gemini ≈ $10.5) |
| A_E only, all 195 scenarios, five runs | ≈ $5.6 |
| G1(b): A_E plus the A_E arms of the ablations | ≈ $6–20 |
| G1(c): every experiment (main, prompt and retrieval ablations, ordering arms, position bias) | ≈ $44, or $50–60 with retries and margin; Gemini is about 84% |

## Update 2026-09-25: gates settled

- **G1:** (c), a full fresh rerun, with Gemini 3.8 Flash replacing Gemini 3.5 Flash.
- **G2:** a pure median. Neither no-LLM baseline reads anything from the question, and the
  medians and modes are taken over the 90 retrieval scenarios only.
- **G3:** still open.

The calculator, baseline, pipeline and infrastructure work that has to come before the rerun
is in `paper/pass5/RERUN_PREP_PLAN.md`, which replaces Steps 2 and 3 above.
