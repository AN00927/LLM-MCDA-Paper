# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Basis: each run evaluated on its own, failed scenario-runs dropped, rates and errors averaged over runs; counts summed over runs
- Run files: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Qwen3.5 9B\LLM-Parameterized_Reference_Scoring_results_run_01.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Qwen3.5 9B\LLM-Parameterized_Reference_Scoring_results_run_02.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Qwen3.5 9B\LLM-Parameterized_Reference_Scoring_results_run_03.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Qwen3.5 9B\LLM-Parameterized_Reference_Scoring_results_run_04.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Qwen3.5 9B\LLM-Parameterized_Reference_Scoring_results_run_05.xlsx`
- Scored scenario-runs: 973 (of 975 result rows across runs)
- Counterfactual rows evaluated: 1683

## Runs

| run | file | rows | scored | failed_scenario_runs | unmatched |
| --- | --- | --- | --- | --- | --- |
| 01 | LLM-Parameterized_Reference_Scoring_results_run_01.xlsx | 195 | 194 | 1 | 0 |
| 02 | LLM-Parameterized_Reference_Scoring_results_run_02.xlsx | 195 | 195 | 0 | 0 |
| 03 | LLM-Parameterized_Reference_Scoring_results_run_03.xlsx | 195 | 195 | 0 | 0 |
| 04 | LLM-Parameterized_Reference_Scoring_results_run_04.xlsx | 195 | 194 | 1 | 0 |
| 05 | LLM-Parameterized_Reference_Scoring_results_run_05.xlsx | 195 | 195 | 0 | 0 |

## Numeric Parameter Error Distribution

| decision_type | parameter | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n | n_valid | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 0.9983 | 1.3205 | 0.9983 | 0.5900 | 0.8706 | 0.3100 | 2.0360 | 2.1684 | 325 | 325 | 0 | 0 | 5 |
| HVAC | hvac_age | 6.4129 | 11.2736 | 6.4129 | 4.2000 | 9.3349 | 1.8500 | 8.5000 | 13.0800 | 348 | 348 | 0 | 0 | 5 |
| HVAC | r_value | 4.4629 | 5.2604 | 4.4629 | 4.0000 | 2.8011 | 2.6000 | 5.8500 | 8.8100 | 348 | 348 | 0 | 0 | 5 |
| HVAC | seer | 1.6264 | 2.2226 | 1.6264 | 1.0000 | 1.5255 | 0.8000 | 2.0000 | 3.8400 | 348 | 348 | 0 | 0 | 5 |
| Shower | gpm | 0.3047 | 0.5889 | 0.3047 | 0.0000 | 0.5074 | 0.0000 | 0.5000 | 1.0000 | 300 | 300 | 0 | 0 | 5 |
| Shower | tank_size | 8.9333 | 13.3043 | 8.9333 | 10.0000 | 9.9418 | 0.0000 | 10.0000 | 20.0000 | 300 | 300 | 0 | 0 | 5 |
| Shower | water_heater_temp | 4.5833 | 8.1904 | 4.5833 | 0.0000 | 6.8452 | 0.0000 | 10.0000 | 15.0000 | 300 | 300 | 0 | 0 | 5 |

## Categorical Parameter Accuracy

| decision_type | parameter | accuracy | n | n_valid | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | appliance | 1.0000 | 325 | 325 | 325 | 0 | 0 | 0 | 5 |
| Appliance | baseline_time | 0.9969 | 325 | 325 | 324 | 1 | 0 | 0 | 5 |
| HVAC | occupancy_context | 0.7873 | 348 | 348 | 274 | 74 | 0 | 0 | 5 |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | conditional_change_probability | unconditional_change_probability | n_error_cases_evaluated | n_top1_changes | n_runs |
| --- | --- | --- | --- | --- | --- | --- |
| Appliance | baseline_time | 0.0000 | 0.0000 | 1 | 0 | 1 |
| Appliance | kwh_per_cycle | 0.0800 | 0.0708 | 287 | 23 | 5 |
| HVAC | hvac_age | 0.0000 | 0.0000 | 320 | 0 | 5 |
| HVAC | occupancy_context | 0.0543 | 0.0115 | 74 | 4 | 5 |
| HVAC | r_value | 0.0930 | 0.0919 | 344 | 32 | 5 |
| HVAC | seer | 0.0372 | 0.0287 | 269 | 10 | 5 |
| Shower | gpm | 0.2562 | 0.0933 | 108 | 28 | 5 |
| Shower | tank_size | 0.0278 | 0.0167 | 180 | 5 | 5 |
| Shower | water_heater_temp | 0.0500 | 0.0167 | 100 | 5 | 5 |

## Counterfactual Case Detail

| scenario_id | decision_type | parameter | ground_truth_top1 | counterfactual_top1 | changed | run |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | HVAC | r_value | 76 | 76 | False | 01 |
| 1 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 2 | HVAC | r_value | 71 | 71 | False | 01 |
| 2 | HVAC | hvac_age | 71 | 71 | False | 01 |
| 3 | HVAC | r_value | 77 | 77 | False | 01 |
| 3 | HVAC | seer | 77 | 77 | False | 01 |
| 3 | HVAC | hvac_age | 77 | 77 | False | 01 |
| 4 | HVAC | r_value | 68 | 68 | False | 01 |
| 4 | HVAC | seer | 68 | 68 | False | 01 |
| 4 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 5 | HVAC | r_value | 77 | 77 | False | 01 |
| 5 | HVAC | seer | 77 | 77 | False | 01 |
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
| 10 | HVAC | occupancy_context | 71 | 71 | False | 01 |
| 11 | HVAC | r_value | 76 | 76 | False | 01 |
| 11 | HVAC | seer | 76 | 76 | False | 01 |
| 12 | HVAC | r_value | 69 | 69 | False | 01 |
| 12 | HVAC | seer | 69 | 69 | False | 01 |
| 12 | HVAC | hvac_age | 69 | 69 | False | 01 |
| 12 | HVAC | occupancy_context | 69 | 69 | False | 01 |
| 13 | HVAC | r_value | 76 | 76 | False | 01 |
| 13 | HVAC | seer | 76 | 76 | False | 01 |
| 13 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 14 | HVAC | r_value | 76 | 76 | False | 01 |
| 14 | HVAC | seer | 76 | 76 | False | 01 |
| 14 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 15 | HVAC | r_value | 78 | 81 | True | 01 |
| 15 | HVAC | seer | 78 | 78 | False | 01 |
| 15 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 15 | HVAC | occupancy_context | 78 | 78 | False | 01 |
| 16 | HVAC | seer | 68 | 68 | False | 01 |
| 16 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 17 | HVAC | r_value | 78 | 78 | False | 01 |
| 17 | HVAC | seer | 78 | 78 | False | 01 |
| 18 | HVAC | r_value | 78 | 78 | False | 01 |
| 18 | HVAC | seer | 78 | 78 | False | 01 |
| 18 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 18 | HVAC | occupancy_context | 78 | 78 | False | 01 |

