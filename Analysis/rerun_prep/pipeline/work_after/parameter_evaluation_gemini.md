# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Basis: each run evaluated on its own, failed scenario-runs dropped, rates and errors averaged over runs; counts summed over runs
- Run files: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Gemini 3.5 Flash\LLM-Parameterized_Reference_Scoring_results_run_01.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Gemini 3.5 Flash\LLM-Parameterized_Reference_Scoring_results_run_02.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Gemini 3.5 Flash\LLM-Parameterized_Reference_Scoring_results_run_03.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Gemini 3.5 Flash\LLM-Parameterized_Reference_Scoring_results_run_04.xlsx`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Gemini 3.5 Flash\LLM-Parameterized_Reference_Scoring_results_run_05.xlsx`
- Scored scenario-runs: 975 (of 975 result rows across runs)
- Counterfactual rows evaluated: 1651

## Runs

| run | file | rows | scored | failed_scenario_runs | unmatched |
| --- | --- | --- | --- | --- | --- |
| 01 | LLM-Parameterized_Reference_Scoring_results_run_01.xlsx | 195 | 195 | 0 | 0 |
| 02 | LLM-Parameterized_Reference_Scoring_results_run_02.xlsx | 195 | 195 | 0 | 0 |
| 03 | LLM-Parameterized_Reference_Scoring_results_run_03.xlsx | 195 | 195 | 0 | 0 |
| 04 | LLM-Parameterized_Reference_Scoring_results_run_04.xlsx | 195 | 195 | 0 | 0 |
| 05 | LLM-Parameterized_Reference_Scoring_results_run_05.xlsx | 195 | 195 | 0 | 0 |

## Numeric Parameter Error Distribution

| decision_type | parameter | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n | n_valid | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 0.5480 | 0.7206 | 0.5480 | 0.3600 | 0.4716 | 0.1840 | 1.0100 | 1.1296 | 325 | 325 | 0 | 0 | 5 |
| HVAC | hvac_age | 7.7943 | 13.4947 | 7.7943 | 4.9000 | 11.0955 | 1.2500 | 10.9500 | 17.0200 | 350 | 350 | 0 | 0 | 5 |
| HVAC | r_value | 1.8057 | 2.3270 | 1.8057 | 1.1000 | 1.4782 | 1.0000 | 3.0000 | 4.0000 | 350 | 350 | 0 | 0 | 5 |
| HVAC | seer | 1.3757 | 1.9486 | 1.3757 | 1.0000 | 1.3899 | 0.0750 | 2.0000 | 3.0800 | 350 | 350 | 0 | 0 | 5 |
| Shower | gpm | 0.3667 | 0.5774 | 0.3667 | 0.2500 | 0.4497 | 0.0000 | 0.5000 | 1.0000 | 300 | 300 | 0 | 0 | 5 |
| Shower | tank_size | 6.7333 | 11.8251 | 6.7333 | 0.0000 | 9.8026 | 0.0000 | 10.0000 | 20.0000 | 300 | 300 | 0 | 0 | 5 |
| Shower | water_heater_temp | 4.5833 | 8.1904 | 4.5833 | 0.0000 | 6.8452 | 0.0000 | 10.0000 | 15.0000 | 300 | 300 | 0 | 0 | 5 |

## Categorical Parameter Accuracy

| decision_type | parameter | accuracy | n | n_valid | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | n_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Appliance | appliance | 0.9385 | 325 | 325 | 305 | 20 | 0 | 0 | 5 |
| Appliance | baseline_time | 1.0000 | 325 | 325 | 325 | 0 | 0 | 0 | 5 |
| HVAC | occupancy_context | 0.8000 | 350 | 350 | 280 | 70 | 0 | 0 | 5 |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | conditional_change_probability | unconditional_change_probability | n_error_cases_evaluated | n_top1_changes | n_runs |
| --- | --- | --- | --- | --- | --- | --- |
| Appliance | appliance | 0.0000 | 0.0000 | 20 | 0 | 5 |
| Appliance | kwh_per_cycle | 0.0308 | 0.0308 | 325 | 10 | 5 |
| HVAC | hvac_age | 0.0000 | 0.0000 | 315 | 0 | 5 |
| HVAC | occupancy_context | 0.0716 | 0.0143 | 70 | 5 | 5 |
| HVAC | r_value | 0.0000 | 0.0000 | 283 | 0 | 5 |
| HVAC | seer | 0.0508 | 0.0371 | 256 | 13 | 5 |
| Shower | gpm | 0.2333 | 0.1167 | 150 | 35 | 5 |
| Shower | tank_size | 0.0000 | 0.0000 | 132 | 0 | 5 |
| Shower | water_heater_temp | 0.0500 | 0.0167 | 100 | 5 | 5 |

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
| 4 | HVAC | seer | 68 | 68 | False | 01 |
| 4 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 5 | HVAC | r_value | 77 | 77 | False | 01 |
| 5 | HVAC | hvac_age | 77 | 77 | False | 01 |
| 5 | HVAC | occupancy_context | 77 | 77 | False | 01 |
| 6 | HVAC | r_value | 78 | 78 | False | 01 |
| 6 | HVAC | seer | 78 | 78 | False | 01 |
| 6 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 7 | HVAC | r_value | 70 | 70 | False | 01 |
| 7 | HVAC | seer | 70 | 70 | False | 01 |
| 7 | HVAC | hvac_age | 70 | 70 | False | 01 |
| 8 | HVAC | r_value | 76 | 76 | False | 01 |
| 8 | HVAC | seer | 76 | 76 | False | 01 |
| 8 | HVAC | hvac_age | 76 | 76 | False | 01 |
| 9 | HVAC | r_value | 70 | 70 | False | 01 |
| 9 | HVAC | seer | 70 | 70 | False | 01 |
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
| 16 | HVAC | r_value | 68 | 68 | False | 01 |
| 16 | HVAC | seer | 68 | 68 | False | 01 |
| 16 | HVAC | hvac_age | 68 | 68 | False | 01 |
| 17 | HVAC | seer | 78 | 78 | False | 01 |
| 17 | HVAC | hvac_age | 78 | 78 | False | 01 |
| 17 | HVAC | occupancy_context | 78 | 78 | False | 01 |
| 18 | HVAC | r_value | 78 | 78 | False | 01 |

