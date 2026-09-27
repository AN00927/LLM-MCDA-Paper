# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Basis: each run evaluated on its own, failed scenario-runs dropped, rates and errors averaged over runs; counts summed over runs
- Run files: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files DeepSeek V4 Flash\LLM-Parameterized_Reference_Scoring_results_run_01.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files DeepSeek V4 Flash\LLM-Parameterized_Reference_Scoring_results_run_02.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files DeepSeek V4 Flash\LLM-Parameterized_Reference_Scoring_results_run_03.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files DeepSeek V4 Flash\LLM-Parameterized_Reference_Scoring_results_run_04.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files DeepSeek V4 Flash\LLM-Parameterized_Reference_Scoring_results_run_05.xlsx`
- Scored scenario-runs: 974 (of 975 result rows across runs)
- Counterfactual rows evaluated: 1780

## Runs

| run | file | rows | scored | failed_scenario_runs | unmatched |
| --- | --- | --- | --- | --- | --- |
| 01 | LLM-Parameterized_Reference_Scoring_results_run_01.xlsx | 195 | 195 | 0 | 0 |
| 02 | LLM-Parameterized_Reference_Scoring_results_run_02.xlsx | 195 | 194 | 1 | 0 |
| 03 | LLM-Parameterized_Reference_Scoring_results_run_03.xlsx | 195 | 195 | 0 | 0 |
| 04 | LLM-Parameterized_Reference_Scoring_results_run_04.xlsx | 195 | 195 | 0 | 0 |
| 05 | LLM-Parameterized_Reference_Scoring_results_run_05.xlsx | 195 | 195 | 0 | 0 |

## Numeric Parameter Error Distribution

| decision_type | parameter | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n | n_valid | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 0.3626 | 0.5062 | 0.3626 | 0.2760 | 0.3558 | 0.1260 | 0.5240 | 0.7140 | 325 | 325 | 0 | 0 | 5 |
| HVAC | hvac_age | 8.3508 | 12.9276 | 8.3508 | 5.7000 | 9.8919 | 2.0000 | 12.8500 | 17.6800 | 349 | 349 | 0 | 0 | 5 |
| HVAC | r_value | 3.2163 | 4.0328 | 3.2163 | 2.8000 | 2.4397 | 2.0000 | 4.0000 | 5.9700 | 349 | 349 | 0 | 0 | 5 |
| HVAC | seer | 1.6505 | 2.1923 | 1.6505 | 1.1000 | 1.4531 | 0.8000 | 2.2000 | 3.2800 | 349 | 349 | 0 | 0 | 5 |
| Shower | gpm | 0.3697 | 0.5272 | 0.3697 | 0.4000 | 0.3786 | 0.0000 | 0.4500 | 0.9000 | 300 | 300 | 0 | 0 | 5 |
| Shower | tank_size | 7.2000 | 11.2419 | 7.2000 | 8.0000 | 8.6731 | 0.0000 | 10.0000 | 14.4000 | 300 | 300 | 0 | 0 | 5 |
| Shower | water_heater_temp | 8.8500 | 12.6457 | 8.8500 | 7.5000 | 9.0504 | 0.0000 | 18.0000 | 19.0000 | 300 | 300 | 0 | 0 | 5 |

## Categorical Parameter Accuracy

| decision_type | parameter | accuracy | n | n_valid | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | appliance | 1.0000 | 325 | 325 | 325 | 0 | 0 | 0 | 5 |
| Appliance | baseline_time | 1.0000 | 325 | 325 | 325 | 0 | 0 | 0 | 5 |
| HVAC | occupancy_context | 0.8224 | 349 | 349 | 287 | 62 | 0 | 0 | 5 |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | conditional_change_probability | unconditional_change_probability | n_error_cases_evaluated | n_top1_changes | n_runs |
| --- | --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 0.0170 | 0.0154 | 294 | 5 | 5 |
| HVAC | hvac_age | 0.0000 | 0.0000 | 323 | 0 | 5 |
| HVAC | occupancy_context | 0.0812 | 0.0143 | 62 | 5 | 5 |
| HVAC | r_value | 0.0425 | 0.0401 | 329 | 14 | 5 |
| HVAC | seer | 0.0482 | 0.0373 | 270 | 13 | 5 |
| Shower | gpm | 0.2494 | 0.1500 | 180 | 45 | 5 |
| Shower | tank_size | 0.0173 | 0.0100 | 161 | 3 | 5 |
| Shower | water_heater_temp | 0.0437 | 0.0233 | 161 | 7 | 5 |

## Counterfactual Case Detail

| scenario_id | decision_type | parameter | ground_truth_top1 | counterfactual_top1 | changed | run |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | HVAC | r_value | 76 | 76 | False | 01 |
| 1 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 2 | HVAC | r_value | 71 | 71 | False | 01 |
| 2 | HVAC | seer | 71 | 71 | False | 01 |
| 2 | HVAC | hvac_age | 71 | 71 | False | 01 |
| 3 | HVAC | r_value | 77 | 77 | False | 01 |
| 3 | HVAC | seer | 77 | 77 | False | 01 |
| 3 | HVAC | hvac_age | 77 | 77 | False | 01 |
| 4 | HVAC | r_value | 68 | 68 | False | 01 |
| 4 | HVAC | seer | 68 | 68 | False | 01 |
| 4 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 5 | HVAC | r_value | 77 | 77 | False | 01 |
| 5 | HVAC | hvac_age | 77 | 77 | False | 01 |
| 6 | HVAC | r_value | 78 | 78 | False | 01 |
| 6 | HVAC | seer | 78 | 78 | False | 01 |
| 6 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 7 | HVAC | r_value | 70 | 70 | False | 01 |
| 7 | HVAC | seer | 70 | 70 | False | 01 |
| 7 | HVAC | hvac_age | 70 | 70 | False | 01 |
| 8 | HVAC | r_value | 76 | 76 | False | 01 |
| 8 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 9 | HVAC | r_value | 70 | 70 | False | 01 |
| 9 | HVAC | hvac_age | 70 | 70 | False | 01 |
| 10 | HVAC | r_value | 71 | 71 | False | 01 |
| 10 | HVAC | seer | 71 | 71 | False | 01 |
| 10 | HVAC | hvac_age | 71 | 71 | False | 01 |
| 11 | HVAC | r_value | 76 | 76 | False | 01 |
| 11 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 12 | HVAC | r_value | 69 | 69 | False | 01 |
| 12 | HVAC | hvac_age | 69 | 69 | False | 01 |
| 12 | HVAC | occupancy_context | 69 | 69 | False | 01 |
| 13 | HVAC | r_value | 76 | 76 | False | 01 |
| 13 | HVAC | seer | 76 | 76 | False | 01 |
| 13 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 13 | HVAC | occupancy_context | 76 | 76 | False | 01 |
| 14 | HVAC | r_value | 76 | 76 | False | 01 |
| 14 | HVAC | seer | 76 | 76 | False | 01 |
| 14 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 15 | HVAC | r_value | 78 | 78 | False | 01 |
| 15 | HVAC | seer | 78 | 78 | False | 01 |
| 15 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 15 | HVAC | occupancy_context | 78 | 78 | False | 01 |
| 16 | HVAC | seer | 68 | 68 | False | 01 |
| 16 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 17 | HVAC | r_value | 78 | 78 | False | 01 |
| 17 | HVAC | seer | 78 | 78 | False | 01 |
| 17 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 17 | HVAC | occupancy_context | 78 | 78 | False | 01 |
| 18 | HVAC | seer | 78 | 78 | False | 01 |
| 18 | HVAC | hvac_age | 78 | 78 | False | 01 |

