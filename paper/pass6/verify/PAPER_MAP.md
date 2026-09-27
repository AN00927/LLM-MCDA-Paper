# Paper Structure Map

Generated 2026-09-26 from `paper_draft_v2.tex` (1148 lines) and `supplementary.tex` (1559 lines), before any Pass 6 edit. Line numbers are 1-indexed and shift after edits.

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
| section | Experimental Design | 487 | 767 | sec:experimental-design |
| - subsection | Decision Types and Scenario Dataset | 492 | 579 | sec:dataset |
| - subsection | Criteria and Weighting | 580 | 616 | sec:criteria-weighting |
| - subsection | Reference Calculators | 617 | 730 | sec:gt-calculators |
| - subsection | Models and Implementation | 731 | 742 | sec:models-implementation |
| - subsection | Baselines and Robustness Checks | 743 | 767 | sec:ablation-design |
| -- subsubsection | Non-LLM baselines and parameter provenance | 747 | 750 | sec:hybrid-ablation-methods |
| -- subsubsection | Alternative ordering | 751 | 754 | sec:alternative-order |
| -- subsubsection | Prompt ablation | 755 | 758 | sec:prompt-ablation-methods |
| -- subsubsection | RAG ablation | 759 | 762 | sec:rag-ablation-methods |
| -- subsubsection | Value-function curvature and weights | 763 | 767 | sec:sensitivity-methods |
| section | Results | 768 | 1044 | sec:results |
| - subsection | Does the Decision Need Per-Scenario Inference? | 773 | 834 | sec:res-baselines |
| - subsection | Which Integration Strategy Reproduces the Reference Ranking? | 835 | 911 | sec:res-ranking |
| - subsection | Where Does the Advantage Come From? | 912 | 949 | sec:res-extraction |
| - subsection | Where Does It Break Down? | 950 | 991 | sec:res-bytype |
| - subsection | Sensitivity and Robustness | 992 | 1014 | sec:res-sensitivity |
| - subsection | Efficiency and Cost | 1015 | 1044 | sec:res-efficiency |
| section | Discussion | 1045 | 1105 | sec:discussion |
| - subsection | Interpretation of Results | 1051 | 1073 | sec:interpretation |
| - subsection | What These Results Confirm and Qualify | 1074 | 1084 | sec:comparison |
| - subsection | Limitations of the Study | 1085 | 1096 | sec:limitations |
| - subsection | Future Work | 1097 | 1105 | sec:futurework |
| section | Conclusion | 1106 | 1143 | sec:conclusion |

### 1.3 Tables (11) and figures (6)
| Type | Start | End | Label | Caption start | Ref'd at |
|---|---|---|---|---|---|
| figure | 343 | 348 | fig:pa_residential_emissions | Pennsylvania residential emissions from on-site fuel combustion | 341 |
| figure | 353 | 358 | fig:lifestyle_emissions_impact | Emission-reduction potential of household actions | 351 |
| table | 375 | 399 | tab:llm-mcda-prior-work | Prior LLM--MCDA integration studies. | 373 |
| figure | 465 | 470 | fig:pipeline | Processing steps of the three integration architectures. | 463 |
| table | 498 | 577 | tab:parameter_comparison | Parameters received by the LLMs and by the | 496 |
| table | 584 | 604 | tab:item3 | MAVT criterion specification. | 582 |
| table | 626 | 644 | table:reference_ranges | MAVT normalization bounds by criterion and decision type. | 610, 624, 1053 |
| table | 777 | 805 | tab:incremental-contribution | Ranking accuracy relative to the fixed-default baseline. | 775 |
| table | 812 | 832 | tab:single-criterion-recovery | Reference winners recovered from a single criterion | 810 |
| figure | 839 | 844 | fig:grouped_bars | Overall accuracy by model and architecture. | 837, 846 |
| table | 848 | 876 | tab:dispersion | Within-scenario score dispersion for the strongest and weakest | 846 |
| figure | 881 | 886 | fig:mae_criterion | MAE by criterion, model and architecture. | 879 |
| table | 891 | 907 | tab:failure_arch_model | Failed scenario-runs by architecture and model | 889 |
| table | 916 | 943 | tab:extraction_accuracy | Extraction error and its effect on the top-ranked | 914, 1083 |
| table | 954 | 987 | tab:item7 | Ranking accuracy by decision type, best and worst | 952 |
| figure | 1003 | 1008 | fig:rag_ablation | Kendall's tau by retrieval configuration | 1000, 1065 |
| table | 1019 | 1042 | tab:item8 | Cost per run (USD) and total tokens per | 1017, 1136 |

### 1.4 TODO markers
| Line | Text |
|---|---|
| 22 | `%todo*: he.huang 29 August ...` threaded co-author comment (original vs literature-derived strategies; no A notation in the Introduction; "three architectures" vs experiment design) |
| 23 | `%todo*:As said, you shouldn't have subsection right after a section title without any text` |
| 349 | `%todo: ask about formatting (huang) and whether there shoud be a title` |

### 1.5 Bibliography
`\bibliographystyle{elsarticle-num-names}` 1144; `\bibliography{cas-refs}` 1145; `\end{document}` 1148.

## 2. supplementary.tex

### 2.1 Preamble
`\documentclass[11pt]{article}` 4. Packages: 5-13, 21 (listings), 39 (graphicx), 41-42 (tikz, pgfplots), 176 (hyperref), 177 (natbib). `\suppsection` macro 178-188. `\begin{document}` 196.

### 2.2 Sections
| Level | Title | Start | End | Label |
|---|---|---|---|---|
| suppsection | Extended Methods (S1) | 198 | 203 | app:model_routing |
| - subsection | Notation | 204 | 256 | app:notation |
| - subsection | Full Prompt Texts | 257 | 440 | app:prompts |
| -- subsubsection | A_D System Prompt | 262 | 330 | - |
| -- subsubsection | A_E System Prompt | 331 | 367 | - |
| -- subsubsection | A_H Extraction Prompt | 368 | 440 | - |
| - subsection | Retrieved Exemplar Rendering | 441 | 469 | - |
| - subsection | RAG Dataset Description | 470 | 512 | app:rag_corpus |
| - subsection | Scenario Fields by Decision Type | 513 | 566 | app:scenario_fields |
| - subsection | Parameter Ranges and Band Labels | 567 | 596 | app:parameter_ranges |
| - subsection | Monthly-Cost Conversions | 597 | 618 | app:monthly_cost |
| - subsection | Fixed-Default Constants | 619 | 654 | app:fixed_default |
| - subsection | Worked Example: A_H HVAC Scenario | 655 | 692 | app:hvac_worked |
| - subsection | GPT-OSS Extraction Failure Analysis | 693 | 734 | app:extraction_failure_analysis |
| - subsection | Pennsylvania Time-of-Use Rate Structure | 735 | 767 | app:tou_rates |
| suppsection | Extended Results and Robustness (S2) | 768 | 769 | - |
| - subsection | Realized Criterion Swing | 770 | 794 | app:swing_weights |
| - subsection | Entropy and MEREC Weight Vectors | 795 | 826 | app:weights |
| - subsection | Full Sensitivity Analysis Results | 827 | 894 | app:sensitivity_full |
| - subsection | Value-Function Curvature Sweep: Recomputation Protocol | 895 | 922 | app:alpha_sweep |
| - subsection | Ablation Data Provenance | 923 | 931 | app:ablation_provenance |
| - subsection | RAG Ablation: Full Per-Configuration Table | 932 | 974 | app:rag_ablation_full |
| - subsection | RAG Ablation: Test-Family Bookkeeping | 975 | 979 | app:rag_ablation_significance |
| - subsection | Run-to-Run Variance: Full Distributions | 980 | 1108 | app:variance |
| - subsection | Statistical Significance Tests | 1109 | 1192 | app:significance |
| -- subsubsection | Pairwise Wilcoxon Tests, Reported Per Model | 1116 | 1121 | - |
| -- subsubsection | Effect Sizes | 1122 | 1152 | - |
| -- subsubsection | Bootstrap Confidence Intervals | 1153 | 1192 | - |
| - subsection | Prompt Ablation: Full Results Table | 1193 | 1238 | app:prompt-ablation-full |
| - subsection | Prompt Ablation Significance | 1239 | 1295 | app:prompt-ablation-significance |
| - subsection | Parameter-Source Ablation Significance | 1296 | 1333 | app:paramprov-significance |
| - subsection | Alternative-Ordering Ablation: Full Statistics | 1334 | 1375 | app:alternative-order-full |
| - subsection | Imputed Robustness Check | 1376 | 1412 | app:imputed |
| - subsection | Criterion Score Duplication | 1413 | 1453 | app:score_duplication |
| - subsection | Criterion Error: Numerical Values | 1454 | 1495 | app:criterion_mae |
| - subsection | Per-Decision-Type Results by Model | 1496 | 1505 | app:per_model_results |
| - subsection | Overall Results: Numerical Values | 1506 | 1554 | app:numerical_results |

### 2.3 Tables (22) and figures (5)
| Type | Start | End | Label | Ref'd at |
|---|---|---|---|---|
| table | 209 | 255 | tab:notation | 207 |
| figure | 506 | 511 | fig:full-flow-mcda | 504 |
| table | 524 | 562 | tab:scenario_fields | 517 |
| table | 578 | 593 | tab:housing_mappings | 576 |
| table | 631 | 653 | tab:fixed_default_constants | 625 |
| table | 714 | 730 | tab:failure_modes | 712 |
| table | 743 | 763 | tab:tou_rates | 740 |
| table* | 775 | 793 | tab:swing_weights | 773 |
| table | 800 | 823 | tab:weight_comparison | 798 |
| table* | 837 | 862 | tab:sensitivity_by_model | 831 |
| table* | 863 | 888 | tab:sensitivity_top1 | 832 |
| figure | 916 | 921 | fig:alpha_sweep | 914 |
| table | 937 | 971 | tab:rag_ablation_full | 935 |
| figure* | 985 | 1040 | fig:violin_tau | 983 |
| figure* | 1042 | 1105 | fig:violin_rmse | 983 |
| table | 1126 | 1151 | tab:effect_sizes | 1120, 1124 |
| table | 1157 | 1189 | tab:bootstrap_paired | 1155 |
| table* | 1198 | 1235 | tab:prompt_ablation | 1196 |
| table | 1248 | 1269 | tab:prompt_friedman | 1244 |
| table | 1273 | 1292 | tab:prompt_pairwise | 1244 |
| table* | 1301 | 1326 | tab:param_provenance | 1299 |
| table | 1350 | 1370 | tab:mcnemar_order | 1348 |
| table | 1381 | 1409 | tab:imputed_comparison | 1379 |
| table | 1420 | 1452 | tab:score_duplication | 1416 |
| table | 1459 | 1492 | tab:mae_by_criterion | 1457 |
| figure | 1499 | 1504 | app:decision_type_full_figures | 1498 |
| table | 1511 | 1552 | tab:overall_by_model | 1107, 1509 |

### 2.4 TODO markers
None.

### 2.5 Bibliography
`\bibliographystyle{cas-model2-names}` 1556; `\bibliography{cas-refs}` 1557; `\end{document}` 1559.
