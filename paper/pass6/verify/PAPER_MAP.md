# Paper Structure Map

Regenerated 2026-09-27 against the CURRENT `paper_draft_v2.tex` (1149 lines) and
`supplementary.tex` (1560 lines), superseding the 2026-09-26 (pre-Pass-6) version of
this map. Line numbers are 1-indexed and will shift again after further edits.

## 1. paper_draft_v2.tex

### 1.1 Preamble
| Item | Line(s) |
|---|---|
| `\documentclass[final,3p,times]{elsarticle}` | 1 |
| `\usepackage` list | 2 (inputenc), 3 (amssymb), 4 (float), 5 (placeins), 6 (amsmath), 7 (booktabs), 8 (array), 9 (textcomp), 10 (multirow), 11 (threeparttable), 12 (siunitx), 13 (xcolor[table]), 14 (xurl), 15 (hyperref), 16 (caption), 25 (pgfplots), 28 (tikz), 31 (todonotes), 32 (alltt) |
| `\begin{document}` | 288 |

### 1.2 Sections
| Level | Title | Start | End | Label |
|---|---|---|---|---|
| section | Introduction | 310 | 333 | sec:introduction |
| section | Literature Review | 334 | 411 | sec:lit-review |
| - subsection | Household Energy Decision-Making and Adoption Barriers | 338 | 363 | sec:lit-barriers |
| - subsection | MCDA and Its Automation | 364 | 400 | sec:lit-mcda |
| - subsection | LLM Numeracy and Tool Augmentation | 401 | 411 | sec:lit-numeracy |
| section | Methodology | 412 | 486 | sec:methodology |
| - subsection | MAVT Formulation | 417 | 453 | sec:mavt-design |
| - subsection | Integration Architectures | 454 | 473 | sec:architectures |
| - subsection | Evaluation Metrics | 474 | 486 | sec:eval-metrics |
| section | Experimental Design | 487 | 768 | sec:experimental-design |
| - subsection | Decision Types and Scenario Dataset | 492 | 580 | sec:dataset |
| - subsection | Criteria and Weighting | 581 | 617 | sec:criteria-weighting |
| - subsection | Reference Calculators | 618 | 731 | sec:gt-calculators |
| - subsection | Models and Implementation | 732 | 743 | sec:models-implementation |
| - subsection | Baselines and Robustness Checks | 744 | 768 | sec:ablation-design |
| -- subsubsection | Non-LLM baselines and parameter provenance | 748 | 751 | sec:hybrid-ablation-methods |
| -- subsubsection | Alternative ordering | 752 | 755 | sec:alternative-order |
| -- subsubsection | Prompt ablation | 756 | 759 | sec:prompt-ablation-methods |
| -- subsubsection | RAG ablation | 760 | 763 | sec:rag-ablation-methods |
| -- subsubsection | Value-function curvature and weights | 764 | 768 | sec:sensitivity-methods |
| section | Results | 769 | 1045 | sec:results |
| - subsection | Does the Decision Need Per-Scenario Inference? | 774 | 835 | sec:res-baselines |
| - subsection | Which Integration Strategy Reproduces the Reference Ranking? | 836 | 912 | sec:res-ranking |
| - subsection | Where Does the Advantage Come From? | 913 | 950 | sec:res-extraction |
| - subsection | Where Does It Break Down? | 951 | 992 | sec:res-bytype |
| - subsection | Sensitivity and Robustness | 993 | 1015 | sec:res-sensitivity |
| - subsection | Efficiency and Cost | 1016 | 1045 | sec:res-efficiency |
| section | Discussion | 1046 | 1106 | sec:discussion |
| - subsection | Interpretation of Results | 1052 | 1074 | sec:interpretation |
| - subsection | What These Results Confirm and Qualify | 1075 | 1085 | sec:comparison |
| - subsection | Limitations of the Study | 1086 | 1097 | sec:limitations |
| - subsection | Future Work | 1098 | 1106 | sec:futurework |
| section | Conclusion | 1107 | 1144 | sec:conclusion |

Note: end lines are computed to the line before the next heading **at the same or a
higher level** (so a subsection's range swallows any subsubsections nested inside it,
and a section's range swallows its subsections).

### 1.3 Tables (11) and figures (6)
| Type | Start | End | Label | Caption start | Ref'd at |
|---|---|---|---|---|---|
| figure | 343 | 348 | fig:pa_residential_emissions | Pennsylvania residential emissions from on-site fuel combustion | 341 |
| figure | 353 | 358 | fig:lifestyle_emissions_impact | Emission-reduction potential of household actions | 351 |
| table | 375 | 399 | tab:llm-mcda-prior-work | Prior LLM--MCDA integration studies. | 373 |
| figure | 465 | 470 | fig:pipeline | Processing steps of the three integration architectures. | 463 |
| table | 498 | 578 | tab:parameter_comparison | Parameters received by the LLMs and by the | 496 |
| table | 585 | 605 | tab:item3 | MAVT criterion specification. | 583 |
| table | 627 | 645 | table:reference_ranges | MAVT normalization bounds by criterion and decision type. | 611, 625, 1054 |
| table | 778 | 806 | tab:incremental-contribution | Ranking accuracy relative to the fixed-default baseline. | 776 |
| table | 813 | 833 | tab:single-criterion-recovery | Reference winners recovered from a single criterion | 811 |
| figure | 840 | 845 | fig:grouped_bars | Overall accuracy by model and architecture. | 838, 847 |
| table | 849 | 877 | tab:dispersion | Within-scenario score dispersion for the strongest and weakest | 847 |
| figure | 882 | 887 | fig:mae_criterion | MAE by criterion, model and architecture. | 880 |
| table | 892 | 908 | tab:failure_arch_model | Failed scenario-runs by architecture and model, over five | 890 |
| table | 917 | 944 | tab:extraction_accuracy | Extraction error and its effect on the top-ranked | 915, 1084 |
| table | 955 | 988 | tab:item7 | Ranking accuracy by decision type, best and worst | 953 |
| figure | 1004 | 1009 | fig:rag_ablation | Kendall's tau by retrieval configuration | 1001, 1066 |
| table | 1020 | 1043 | tab:item8 | Cost per run (USD) and total tokens per | 1018, 1137 |

### 1.4 TODO markers
| Line | Text |
|---|---|
| 22 | `%todo*: he.huang 29 August ...` threaded co-author comment (unchanged from Pass-6 start: the three strategies are ours vs. literature-derived; drop $\mathcal{A}$ notation from the Introduction; "three architectures" vs. experiment-design framing) |
| 23 | `%todo*:As said, you shouldn't have subsection right after a section title without any text` |
| 349 | `%todo: ask about formatting (huang) and whether there shoud be a title` |

No `\todo{}` (todonotes) commands are used anywhere in the file; the `todonotes`
package (line 31) is loaded but unused. All three markers are unchanged since the
2026-09-26 snapshot (none of the diff hunks in Section 4 touch lines 22, 23 or 349).

### 1.5 Bibliography
`\bibliographystyle{elsarticle-num-names}` 1145; `\bibliography{cas-refs}` 1146; `\end{document}` 1148.

## 2. supplementary.tex

### 2.1 Preamble
`\documentclass[11pt]{article}` 4. Packages: 5-13 (geometry, amsmath/amssymb,
booktabs, multirow, threeparttable, alltt, float, textcomp, xcolor), 21 (listings),
39 (graphicx), 41-42 (tikz, pgfplots), **176 (xurl — new since the s1 snapshot)**,
177 (hyperref[hidelinks]), 178 (natbib[authoryear,longnamesfirst]). `\suppsection`
macro 181-188 (counter/section-numbering machinery), `\thesection`/`\thetable`/
`\thefigure`/`\theequation` renewcommands 189-192. `\title`/`\author`/`\date` 194-196
(new since the s1 snapshot, which went straight from the renewcommands to
`\begin{document}`). `\begin{document}` 197.

### 2.2 Sections
| Level | Title | Start | End | Label |
|---|---|---|---|---|
| suppsection | Extended Methods (S1) | 199 | 768 | app:model_routing |
| - subsection | Notation | 205 | 257 | app:notation |
| - subsection | Full Prompt Texts | 258 | 441 | app:prompts |
| -- subsubsection | A_D System Prompt | 263 | 331 | - |
| -- subsubsection | A_E System Prompt | 332 | 368 | - |
| -- subsubsection | A_H Extraction Prompt | 369 | 441 | - |
| - subsection | Retrieved Exemplar Rendering | 442 | 470 | - |
| - subsection | RAG Dataset Description | 471 | 513 | app:rag_corpus |
| - subsection | Scenario Fields by Decision Type | 514 | 567 | app:scenario_fields |
| - subsection | Parameter Ranges and Band Labels | 568 | 597 | app:parameter_ranges |
| - subsection | Monthly-Cost Conversions | 598 | 619 | app:monthly_cost |
| - subsection | Fixed-Default Constants | 620 | 655 | app:fixed_default |
| - subsection | Worked Example: A_H HVAC Scenario | 656 | 693 | app:hvac_worked |
| - subsection | GPT-OSS Extraction Failure Analysis | 694 | 735 | app:extraction_failure_analysis |
| - subsection | Pennsylvania Time-of-Use Rate Structure | 736 | 768 | app:tou_rates |
| suppsection | Extended Results and Robustness (S2) | 769 | 1556 | - |
| - subsection | Realized Criterion Swing | 771 | 795 | app:swing_weights |
| - subsection | Entropy and MEREC Weight Vectors | 796 | 827 | app:weights |
| - subsection | Full Sensitivity Analysis Results | 828 | 895 | app:sensitivity_full |
| - subsection | Value-Function Curvature Sweep: Recomputation Protocol | 896 | 923 | app:alpha_sweep |
| - subsection | Ablation Data Provenance | 924 | 932 | app:ablation_provenance |
| - subsection | RAG Ablation: Full Per-Configuration Table | 933 | 975 | app:rag_ablation_full |
| - subsection | RAG Ablation: Test-Family Bookkeeping | 976 | 980 | app:rag_ablation_significance |
| - subsection | Run-to-Run Variance: Full Distributions | 981 | 1109 | app:variance |
| - subsection | Statistical Significance Tests | 1110 | 1193 | app:significance |
| -- subsubsection | Pairwise Wilcoxon Tests, Reported Per Model | 1117 | 1122 | - |
| -- subsubsection | Effect Sizes | 1123 | 1153 | - |
| -- subsubsection | Bootstrap Confidence Intervals | 1154 | 1193 | - |
| - subsection | Prompt Ablation: Full Results Table | 1194 | 1239 | app:prompt-ablation-full |
| - subsection | Prompt Ablation Significance | 1240 | 1296 | app:prompt-ablation-significance |
| - subsection | Parameter-Source Ablation Significance | 1297 | 1334 | app:paramprov-significance |
| - subsection | Alternative-Ordering Ablation: Full Statistics | 1335 | 1376 | app:alternative-order-full |
| - subsection | Imputed Robustness Check | 1377 | 1413 | app:imputed |
| - subsection | Criterion Score Duplication | 1414 | 1454 | app:score_duplication |
| - subsection | Criterion Error: Numerical Values | 1455 | 1496 | app:criterion_mae |
| - subsection | Per-Decision-Type Results by Model | 1497 | 1506 | app:per_model_results |
| - subsection | Overall Results: Numerical Values | 1507 | 1556 | app:numerical_results |

### 2.3 Tables (22) and figures (5)
(Adds a caption column beyond the pre-Pass-6 map, per this generation's explicit
requirement to record caption-start text for every table/figure in both files.)

| Type | Start | End | Label | Caption start | Ref'd at |
|---|---|---|---|---|---|
| table | 210 | 256 | tab:notation | Notation used in the main text | 208 |
| figure | 507 | 512 | fig:full-flow-mcda | Division of the 285 scenarios into test and | 505 |
| table | 525 | 563 | tab:scenario_fields | Scenario fields by decision type over the 195 | 518 |
| table | 579 | 594 | tab:housing_mappings | Housing-type mappings used by the reference calculators | 577 |
| table | 632 | 654 | tab:fixed_default_constants | Fixed-default constant values by decision type | 626 |
| table | 715 | 731 | tab:failure_modes | Nonzero-firing failure mode counts per architecture and model | 713 |
| table | 744 | 764 | tab:tou_rates | Pennsylvania utility TOU rate structure | 741 |
| table* | 776 | 794 | tab:swing_weights | Mean within-scenario swing (nominal weight x within-scenario | 774 |
| table | 801 | 824 | tab:weight_comparison | A priori, entropy and MEREC weight vectors. | 799 |
| table* | 838 | 863 | tab:sensitivity_by_model | Kendall's tau by model and architecture under five | 832 |
| table* | 864 | 889 | tab:sensitivity_top1 | Sensitivity analysis: Top-1 accuracy (%) by model and | 833 |
| figure | 917 | 922 | fig:alpha_sweep | Kendall's tau across the alpha sweep. | 915 |
| table | 938 | 972 | tab:rag_ablation_full | RAG ablation: Kendall's tau and MAE by configuration | 936 |
| figure* | 986 | 1041 | fig:violin_tau | Violin plots of Kendall's tau across five runs | 984 |
| figure* | 1043 | 1106 | fig:violin_rmse | Strip plots of Overall RMSE across five runs | 984 |
| table | 1127 | 1152 | tab:effect_sizes | Cliff's delta effect sizes for pairwise architecture comparisons, | 1121, 1125 |
| table | 1158 | 1190 | tab:bootstrap_paired | Paired architecture differences from the same cluster bootstrap | 1156 |
| table* | 1199 | 1236 | tab:prompt_ablation | Prompt-sensitivity ablation: Kendall's tau and Top-1 accuracy | 1197 |
| table | 1249 | 1270 | tab:prompt_friedman | Prompt ablation: Friedman omnibus tests for A_E, | 1245 |
| table | 1274 | 1293 | tab:prompt_pairwise | Prompt ablation: significant pairwise comparisons (Holm-corrected post-hoc, | 1245 |
| table* | 1302 | 1327 | tab:param_provenance | Ranking accuracy of A_H with LLM-extracted and dataset-median | 1300 |
| table | 1351 | 1371 | tab:mcnemar_order | Alternative-ordering McNemar tests for A_D top-1 correctness, | 1349 |
| table | 1382 | 1410 | tab:imputed_comparison | Comparison of per-run-then-average (Method A) vs per-run | 1380 |
| table | 1421 | 1453 | tab:score_duplication | Criterion score duplication by decision type | 1417 |
| table | 1460 | 1493 | tab:mae_by_criterion | MAE by criterion, model, and architecture (five-run mean) | 1458 |
| figure | 1500 | 1505 | app:decision_type_full_figures | Results by decision type and model: (a--c) | 1499 |
| table | 1512 | 1553 | tab:overall_by_model | Overall performance by model (5-run mean +/- std, | 1108, 1510 |

### 2.4 TODO markers
None. No `%TODO`, `%todo`, or `\todo{}` markers anywhere in the file.

### 2.5 Bibliography
`\bibliographystyle{cas-model2-names}` 1557; `\bibliography{cas-refs}` 1558; `\end{document}` 1560.

## 3. Cross-references to appendix/supplement content

Neither file uses `\ref{app:...}` or `\cref{...}` from the main text into the
supplement (or vice versa) — the shared bibliography aside, the two documents
compile separately and all cross-document pointers are literal prose (e.g.
"Table S2.2", "Section~\ref{sec:res-sensitivity}", "Supplementary Material S1"),
not LaTeX `\ref`/`\cref` commands. All `\ref{...}` and `\cref{...}` uses found are
in-document only (main text to its own tables/figures/equations/sections, and
likewise within the supplement). The literal supplement pointers from
`paper_draft_v2.tex`, with their current line numbers, are:

| Line | Pointer text | Points to (supplement) |
|---|---|---|
| 415 | "The notation is in Table S1.1." | tab:notation |
| 332 | "...are in Tables S2.2 and S2.16." | tab:weight_comparison, tab:overall_by_model |
| 478 | "...in Table S2.13 we repeat..." | (S2.13 imputed-aggregation table) |
| 494 | "...(Supplementary Material S1)." / "...in Figure S1.1." | app:model_routing / fig:full-flow-mcda |
| 496 | "...are in Tables S1.2 and S1.3." | (S1.2/S1.3 field-range tables) |
| 607 | "...(Table S2.2)." | tab:weight_comparison |
| 621 | "...in Supplementary Material S1;" | app:model_routing |
| 741 | "...are in Supplementary Material S1." | app:model_routing |
| 750 | "...(Table S1.4)," | tab:fixed_default_constants |
| 754 | "...(protocol details in Table S2.12)." | tab:mcnemar_order (family) |
| 758 | "...(cells and run counts in Table S2.8)." | app:prompt-ablation-full family |
| 766 | "...(protocol in Figure S2.1)." / "...(vectors and full matrix in Tables S2.2--S2.4)." | fig:alpha_sweep / tab:weight_comparison |
| 809 | "...full statistics in Table S2.11)." | app:paramprov-significance family |
| 811 | "...full values in Table S2.5)." | tab:rag_ablation_full |
| 880 | "...(numerical values in Table S2.15)." | tab:mae_by_criterion |
| 890 | "...(Table S2.13)." | imputed-aggregation table |
| 910 | "...(Table S1.5)," | tab:failure_modes |
| 953 | "...full per-model breakdown in Figure S2.4." | app:decision_type_full_figures |
| 1054 | (Table~\ref{table:reference_ranges} — in-document, not a supplement pointer) | n/a |
| 1066 | "...(Table S2.5)." | tab:rag_ablation_full |
| 1070 | "...(full matrix in Tables S2.2 and S2.3)." | tab:weight_comparison |
| 1082 | "...are in Table S2.1)." | tab:swing_weights |
| 1131, 1137, 1143 | Software/data-availability and supplementary-material paragraphs (prose, no pointer) | — |

## 4. Diff vs s1_snapshot

Snapshots are the pre-Pass-6 copies in `paper/pass6/s1_snapshot/`. Commands run:
`diff paper/pass6/s1_snapshot/<file> paper/<file>` (paper_draft_v2.tex,
supplementary.tex, cas-refs.bib) and `diff paper/pass6/s1_snapshot/README.md README.md`.

### 4.1 paper_draft_v2.tex — 42 hunks (all single-line changes except one 1-line addition)
| Current line(s) | What changed |
|---|---|
| 320 | Broadened "tasks whose correct answer does not depend on anyone's preferences..." list back down to "calculations with a single correct value" (removed the gao2023pal/schick2023toolformer/pan2023logiclm/liu2023llmp/ramamonjison2023nl4opt/ahmaditeshnizi2024optimus citation list from this sentence) |
| 322 | "We pose two research questions" -> "We make one design proposition and ask one research question" |
| 324-325 | Replaced RQ1/RQ2 itemized pair with a single Proposition + RQ pair |
| 328 | "We answer both questions by..." -> "We test the proposition and answer the question by..." |
| 332 | "...are in Supplementary Material S2." -> "...are in Tables S2.2 and S2.16." (made the pointer specific) |
| 346 | Figure caption: added "(data from \citet{padep_ghg2026})" attribution |
| 369 | "...by representing them as fuzzy numbers rather than crisp weights \cite{zadeh1965}." -> "...by representing them with fuzzy sets \cite{zadeh1965} rather than crisp weights." (citation moved, wording tightened) |
| 404 | Dropped trailing clause "...so averaging several scoring runs might likewise improve MCDA scores." |
| 408 | Removed the "model can write a program.../call a calculator.../state a problem formally..." sentence (tool-augmentation examples) from this paragraph |
| 415 | "...is in Supplementary Material S1." -> "...is in Table S1.1." (specific pointer) |
| 476 | Added sentence "Environmental modelling guidance recommends choosing performance criteria to fit the model's purpose and combining several of them rather than relying on one \cite{jakeman2006tensteps,bennett2013characterising}." |
| 478 | "...in Supplementary Material S2 we repeat..." -> "...in Table S2.13 we repeat..." |
| 494 | "...in Supplementary Material S1." -> "...in Figure S1.1." (specific pointer) |
| 496 | Parenthetical list of withheld parameters expanded per decision type; "...are in Supplementary Material S1." -> "...are in Tables S1.2 and S1.3." |
| 519 | Table row "House Age$^b$": Calc. column changed from checkmark to "---" |
| 522 | Added new table row "HVAC Age & --- & \checkmark" |
| 524 | Table row "Indoor Temp (alt.)": LLMs column changed from "---" to "A" |
| 575 | Footnote $^b$ reworded: clarifies the calculator uses exact HVAC equipment age (not house age), which the LLMs never receive |
| 607 | "Cost is also the criterion households estimate worst..." -> "Households also misjudge the energy use that drives cost..."; "...(Supplementary Material S2)." -> "...(Table S2.2)." |
| 615 | Rewrote why HVAC/Shower criteria don't separate: replaced "single time...cost and emissions move together...grid whose intensity varied independently..." with an expanded explanation distinguishing HVAC (shared energy use) and Shower (duration scaling) mechanisms |
| 621 | "...give their full derivations in Supplementary Material S1" -> "...give their monthly-cost conversions, rate tables and parameter bands in Supplementary Material S1" |
| 741 | Added explicit statement "We retrieve one worked example per scenario ($k=1$)...whose control condition retrieves three." |
| 750 | "...(Supplementary Material S1)," -> "...(Table S1.4)," |
| 754 | "...(protocol details in Supplementary Material S2)." -> "...(protocol details in Table S2.12)." |
| 758 | "...(cells and run counts in Supplementary Material S2)." -> "...(cells and run counts in Table S2.8)." |
| 766 | "...(protocol in Supplementary Material S2)." -> "...(protocol in Figure S2.1)."; "...(vectors and full matrix in Supplementary Material S2)." -> "...(...in Tables S2.2--S2.4)." |
| 809 | "...full statistics in Supplementary Material S2)." -> "...full statistics in Table S2.11)." |
| 811 | "...full values in Supplementary Material S2)." -> "...full values in Table S2.5)." |
| 838 | "...we turn to RQ2 and compare..." -> "...we turn to the research question and compare..." (consistent with the RQ1/RQ2 -> single-RQ change at line 324-325) |
| 880 | "...(numerical values in Supplementary Material S2)." -> "...(numerical values in Table S2.15)." |
| 890 | "...(Supplementary Material S2)." -> "...(Table S2.13)." |
| 910 | "...(Supplementary Material S1)," -> "...(Table S1.5)," |
| 953 | "...full per-model breakdown in Supplementary Material S2." -> "...full per-model breakdown in Figure S2.4." |
| 1049 | "...already comes close on two of the three decision types..." -> "...already matches or beats LLM-parameterized reference scoring for two of the four models on two of the three decision types (HVAC and Shower)..." (claim made more precise/quantified) |
| 1058 | Rewrote the GPM-cancellation mechanism explanation: old text said GPM "multiplies against each alternative's own duration...breaks the cancellation"; new text explains cost/water are jointly proportional to GPM*duration, rescaling gaps without reordering except Comfort gaps stay fixed, changing the winner only when it led narrowly |
| 1060 | "...(Supplementary Material S2):" -> "...(Table S2.14):" |
| 1066 | "...(Supplementary Material S2)." -> "...(Table S2.5)." |
| 1070 | "...(Section~\ref{sec:res-sensitivity}; full matrix in Supplementary Material S2)." -> "...(...in Tables S2.2 and S2.3)."; and "...must perform in a single forward pass..." -> "...must perform within one response, with at most a low-effort reasoning trace..." |
| 1078 | Removed sentence "This miscalibration extends...Where that literature predicts compressed scores, $\mathcal{A}_{\text{D}}$'s within-scenario range runs..." was shortened — the clause "Where that literature predicts compressed scores," was deleted, leaving the range statement as a standalone sentence |
| 1082 | "...are in Supplementary Material S2)." -> "...are in Table S2.1)." |
| 1084 | "...argue that such independent agreement is evidence..." -> "...read the convergence of several research groups on clinical calculation as evidence..." |
| 1095 | Rewrote the HVAC/Shower criterion-collapse explanation: old text attributed it directly to "PJM's marginal emissions intensity does not vary independently of retail price"; new text attributes it to "the three alternatives of an HVAC or Shower scenario share one time of use, and Shower cost and water volume both scale with duration" |

### 4.2 supplementary.tex — 6 hunks
| Current line(s) | What changed |
|---|---|
| 142 | `\alpha` sweep plot: `horizontal sep=1.6cm` -> `1.5cm` in the tikz groupplot style |
| 176 | Added `\usepackage{xurl}` |
| 202 | Model-identifier typesetting: `\texttt{...}` -> `\nolinkurl{...}` for the four OpenRouter model IDs (hyperref-safe line breaking) |
| 656 | `\texorpdfstring{$\mathcal{A}_{\text{H}}$}{A_H}` -> `{A\_H}` (escaped underscore in the PDF-string fallback) |
| 974 | Path typesetting: `\texttt{Analysis/RAG\_Ablation/rag\_ablation\_bootstrap\_ci.xlsx}` -> `\nolinkurl{Analysis/RAG_Ablation/rag_ablation_bootstrap_ci.xlsx}` |
| 1343-1344 | Dropped trailing clause "per the main text's timestamp convention" after "five reversed-order extraction runs." |

### 4.3 cas-refs.bib — 10 hunks (855 lines now vs. 872 in the snapshot)
| Current line(s) | What changed |
|---|---|
| ~212 (deletion) | Removed unused `@techreport{neep2015}` (NEEP clothes-dryer baseline study) |
| 214 | `paetz2012` author list corrected: "A. Paetz and E. Dutschke and W. Fichtner" -> "A.-G. Paetz and T. Kaschub and P. Jochem and W. Fichtner" |
| ~399 (deletion) | Removed unused `@article{ohler2020}` (Ohler/Loomis/Ilves Energy Star savings study) |
| 442 | Added `pages = {9459--9474}` to `lewis2020` (RAG paper) |
| 461 | Added `pages = {24824--24837}` to `wei2022cot` (chain-of-thought paper) |
| ~482 (deletion) | Removed unused `@article{roszkowska2026}` (entropy/normalization MCDA paper) |
| ~497 (deletion) | Removed three unused techreports: `nistsp1270`, `epa1974noise`, `doehesscore2021` |
| ~551 (deletion) | Removed unused `@article{zharova2024}` (explainable multi-agent recommender) |
| ~609 (deletion) | Removed five unused water-heating/CFD references: `abdidin2024`, `shen2021`, `marini2017`, `wilkes2005`, `rouleau2019` |
| 758-854 | Added nine new entries: `padep_ghg2026` (PA GHG inventory, now cited at line 346 of the main paper), and the tool-augmentation/environmental-modelling citations `gao2023pal`, `schick2023toolformer`, `liu2023llmp`, `pan2023logiclm`, `ramamonjison2023nl4opt`, `ahmaditeshnizi2024optimus`, `jakeman2006tensteps`, `bennett2013characterising` (the last two now cited at main-paper line 476) |

### 4.4 README.md — 5 hunks
| Current line(s) | What changed |
|---|---|
| 33 | `git clone <repository-url>` -> `git clone https://github.com/AN00927/LLM-MCDA-Paper.git` (placeholder filled in with the real repo URL) |
| 349-350 | HVAC Energy Cost reference range: "$0.38 - $3.29" -> "$0.19 - $3.21"; HVAC Environmental Impact range: "1.96 - 18.04 lbs CO2" -> "0.97 - 17.59 lbs CO2" (updated reference-range figures; note these no longer match the $0.38--$3.29 / 1.96--18.04 figures still in `paper_draft_v2.tex` lines 638-639/646 and Table~\ref{table:reference_ranges} — worth flagging to the user as a possible inconsistency, not fixed here since it is outside this task's scope) |
| 444 | Dropped parenthetical "(see `CLAUDE.md`)" after "no-pooling-across-models convention" |
| 450 | "Three ablation suites..." / "All three cover..." -> "Four ablation suites..." / "All four cover..." (ablation-suite count corrected) |
| 513 | Heading "## Citation / Collaborator" -> "## Citation" |
