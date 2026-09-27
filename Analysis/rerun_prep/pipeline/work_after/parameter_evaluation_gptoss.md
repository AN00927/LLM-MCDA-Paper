# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Basis: each run evaluated on its own, failed scenario-runs dropped, rates and errors averaged over runs; counts summed over runs
- Run files: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\LLM-Parameterized_Reference_Scoring_results_run_01.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\LLM-Parameterized_Reference_Scoring_results_run_02.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\LLM-Parameterized_Reference_Scoring_results_run_03.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\LLM-Parameterized_Reference_Scoring_results_run_04.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\LLM-Parameterized_Reference_Scoring_results_run_05.xlsx`
- Scored scenario-runs: 858 (of 975 result rows across runs)
- Counterfactual rows evaluated: 1469

## Runs

| run | file | rows | scored | failed_scenario_runs | unmatched |
| --- | --- | --- | --- | --- | --- |
| 01 | LLM-Parameterized_Reference_Scoring_results_run_01.xlsx | 195 | 170 | 25 | 0 |
| 02 | LLM-Parameterized_Reference_Scoring_results_run_02.xlsx | 195 | 169 | 26 | 0 |
| 03 | LLM-Parameterized_Reference_Scoring_results_run_03.xlsx | 195 | 174 | 21 | 0 |
| 04 | LLM-Parameterized_Reference_Scoring_results_run_04.xlsx | 195 | 175 | 20 | 0 |
| 05 | LLM-Parameterized_Reference_Scoring_results_run_05.xlsx | 195 | 170 | 25 | 0 |

## Numeric Parameter Error Distribution

| decision_type | parameter | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n | n_valid | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 0.4534 | 0.5953 | 0.4534 | 0.4080 | 0.3882 | 0.2180 | 0.5500 | 0.8740 | 325 | 325 | 0 | 0 | 5 |
| HVAC | hvac_age | 9.3394 | 14.8869 | 9.3394 | 6.4000 | 11.6681 | 2.6000 | 12.8500 | 19.1800 | 233 | 233 | 0 | 0 | 5 |
| HVAC | r_value | 4.4114 | 5.1960 | 4.4114 | 3.8000 | 2.7643 | 2.4000 | 6.2000 | 7.9200 | 233 | 233 | 0 | 0 | 5 |
| HVAC | seer | 2.2084 | 2.7843 | 2.2084 | 2.0000 | 1.7133 | 1.0000 | 3.4000 | 4.5000 | 233 | 233 | 0 | 0 | 5 |
| Shower | gpm | 0.4490 | 0.6569 | 0.4490 | 0.5000 | 0.4833 | 0.0000 | 0.5000 | 1.1000 | 300 | 300 | 0 | 0 | 5 |
| Shower | tank_size | 8.6333 | 12.1352 | 8.6333 | 10.0000 | 8.5968 | 0.0000 | 10.0000 | 19.1000 | 300 | 300 | 0 | 0 | 5 |
| Shower | water_heater_temp | 4.8167 | 8.6069 | 4.8167 | 0.0000 | 7.1926 | 0.0000 | 10.0000 | 15.0000 | 300 | 300 | 0 | 0 | 5 |

## Categorical Parameter Accuracy

| decision_type | parameter | accuracy | n | n_valid | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | appliance | 1.0000 | 325 | 325 | 325 | 0 | 0 | 0 | 5 |
| Appliance | baseline_time | 1.0000 | 325 | 325 | 325 | 0 | 0 | 0 | 5 |
| HVAC | occupancy_context | 0.7376 | 233 | 233 | 172 | 61 | 0 | 0 | 5 |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | conditional_change_probability | unconditional_change_probability | n_error_cases_evaluated | n_top1_changes | n_runs |
| --- | --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 0.0136 | 0.0123 | 294 | 4 | 5 |
| HVAC | hvac_age | 0.0000 | 0.0000 | 217 | 0 | 5 |
| HVAC | occupancy_context | 0.0167 | 0.0045 | 61 | 1 | 5 |
| HVAC | r_value | 0.0261 | 0.0256 | 229 | 6 | 5 |
| HVAC | seer | 0.0515 | 0.0425 | 195 | 10 | 5 |
| Shower | gpm | 0.2708 | 0.1600 | 178 | 48 | 5 |
| Shower | tank_size | 0.0053 | 0.0033 | 193 | 1 | 5 |
| Shower | water_heater_temp | 0.0491 | 0.0167 | 102 | 5 | 5 |

## Counterfactual Case Detail

| scenario_id | decision_type | parameter | ground_truth_top1 | counterfactual_top1 | changed | run |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | HVAC | r_value | 76 | 76 | False | 01 |
| 1 | HVAC | seer | 76 | 76 | False | 01 |
| 1 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 2 | HVAC | r_value | 71 | 71 | False | 01 |
| 2 | HVAC | hvac_age | 71 | 71 | False | 01 |
| 7 | HVAC | r_value | 70 | 70 | False | 01 |
| 7 | HVAC | seer | 70 | 70 | False | 01 |
| 7 | HVAC | hvac_age | 70 | 70 | False | 01 |
| 8 | HVAC | r_value | 76 | 76 | False | 01 |
| 8 | HVAC | seer | 76 | 76 | False | 01 |
| 8 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 9 | HVAC | r_value | 70 | 70 | False | 01 |
| 9 | HVAC | hvac_age | 70 | 70 | False | 01 |
| 10 | HVAC | r_value | 71 | 71 | False | 01 |
| 10 | HVAC | seer | 71 | 71 | False | 01 |
| 11 | HVAC | r_value | 76 | 76 | False | 01 |
| 11 | HVAC | seer | 76 | 76 | False | 01 |
| 11 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 13 | HVAC | r_value | 76 | 76 | False | 01 |
| 13 | HVAC | seer | 76 | 76 | False | 01 |
| 13 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 13 | HVAC | occupancy_context | 76 | 76 | False | 01 |
| 15 | HVAC | r_value | 78 | 78 | False | 01 |
| 15 | HVAC | seer | 78 | 78 | False | 01 |
| 15 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 15 | HVAC | occupancy_context | 78 | 78 | False | 01 |
| 16 | HVAC | r_value | 68 | 68 | False | 01 |
| 16 | HVAC | seer | 68 | 68 | False | 01 |
| 16 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 16 | HVAC | occupancy_context | 68 | 68 | False | 01 |
| 18 | HVAC | r_value | 78 | 78 | False | 01 |
| 18 | HVAC | seer | 78 | 78 | False | 01 |
| 18 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 20 | HVAC | r_value | 69 | 69 | False | 01 |
| 20 | HVAC | seer | 69 | 69 | False | 01 |
| 20 | HVAC | hvac_age | 69 | 69 | False | 01 |
| 20 | HVAC | occupancy_context | 69 | 69 | False | 01 |
| 21 | HVAC | r_value | 68 | 68 | False | 01 |
| 21 | HVAC | seer | 68 | 68 | False | 01 |
| 21 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 22 | HVAC | r_value | 78 | 78 | False | 01 |
| 22 | HVAC | seer | 78 | 78 | False | 01 |
| 22 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 24 | HVAC | r_value | 78 | 78 | False | 01 |
| 24 | HVAC | seer | 78 | 78 | False | 01 |
| 26 | HVAC | r_value | 69 | 69 | False | 01 |
| 26 | HVAC | seer | 69 | 69 | False | 01 |
| 26 | HVAC | hvac_age | 69 | 69 | False | 01 |
| 27 | HVAC | r_value | 69 | 69 | False | 01 |
| 27 | HVAC | seer | 69 | 69 | False | 01 |

