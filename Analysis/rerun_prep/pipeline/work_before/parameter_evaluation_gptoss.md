# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Results file: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\LLM-Parameterized_Reference_Scoring_results.xlsx`
- Matched scenarios: 195/195
- Unmatched scenarios: 0
- Counterfactual rows evaluated: 399

## Numeric Parameter Error Distribution

| n | n_valid | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 0.4248 | 0.5263 | 0.4248 | 0.3800 | 0.3132 | 0.2500 | 0.5500 | 0.6800 | 0.0000 | 0.0000 | Appliance | kwh_per_cycle |
| 70.0000 | 69.0000 | 8.4551 | 13.8678 | 8.4551 | 5.5000 | 11.0727 | 2.0000 | 12.4000 | 17.7800 | 0.0000 | 1.0000 | HVAC | hvac_age |
| 70.0000 | 69.0000 | 3.5942 | 4.3060 | 3.5942 | 3.0000 | 2.3888 | 2.0000 | 5.0000 | 6.6000 | 0.0000 | 1.0000 | HVAC | r_value |
| 70.0000 | 69.0000 | 2.1349 | 2.7062 | 2.1349 | 2.0000 | 1.6751 | 1.0000 | 3.0000 | 4.0500 | 0.0000 | 1.0000 | HVAC | seer |
| 60.0000 | 60.0000 | 0.2557 | 0.3851 | 0.2557 | 0.1000 | 0.2904 | 0.0800 | 0.5000 | 0.6000 | 0.0000 | 0.0000 | Shower | gpm |
| 60.0000 | 60.0000 | 8.1000 | 11.1878 | 8.1000 | 8.0000 | 7.7824 | 2.0000 | 10.0000 | 16.0000 | 0.0000 | 0.0000 | Shower | tank_size |
| 60.0000 | 60.0000 | 4.7167 | 7.9844 | 4.7167 | 0.0000 | 6.4967 | 0.0000 | 10.0000 | 15.0000 | 0.0000 | 0.0000 | Shower | water_heater_temp |

## Categorical Parameter Accuracy

| n | n_valid | accuracy | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | appliance |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | baseline_time |
| 70.0000 | 69.0000 | 0.7536 | 52.0000 | 17.0000 | 0.0000 | 1.0000 | HVAC | occupancy_context |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | n_error_cases_evaluated | n_top1_changes | conditional_change_probability | unconditional_change_probability |
| --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 64.0000 | 1.0000 | 0.0156 | 0.0154 |
| HVAC | hvac_age | 65.0000 | 0.0000 | 0.0000 | 0.0000 |
| HVAC | occupancy_context | 17.0000 | 0.0000 | 0.0000 | 0.0000 |
| HVAC | r_value | 69.0000 | 1.0000 | 0.0145 | 0.0143 |
| HVAC | seer | 61.0000 | 3.0000 | 0.0492 | 0.0429 |
| Shower | gpm | 46.0000 | 8.0000 | 0.1739 | 0.1333 |
| Shower | tank_size | 53.0000 | 0.0000 | 0.0000 | 0.0000 |
| Shower | water_heater_temp | 24.0000 | 1.0000 | 0.0417 | 0.0167 |

## Counterfactual Case Detail

| decision_type | parameter | ground_truth_top1 | counterfactual_top1 | changed |
| --- | --- | --- | --- | --- |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 71 | 71 | False |
| HVAC | seer | 71 | 71 | False |
| HVAC | hvac_age | 71 | 71 | False |
| HVAC | r_value | 77 | 77 | False |
| HVAC | seer | 77 | 77 | False |
| HVAC | hvac_age | 77 | 77 | False |
| HVAC | r_value | 68 | 68 | False |
| HVAC | seer | 68 | 68 | False |
| HVAC | hvac_age | 68 | 68 | False |
| HVAC | r_value | 77 | 77 | False |
| HVAC | seer | 77 | 77 | False |
| HVAC | hvac_age | 77 | 77 | False |
| HVAC | occupancy_context | 77 | 77 | False |
| HVAC | r_value | 78 | 78 | False |
| HVAC | seer | 78 | 78 | False |
| HVAC | hvac_age | 78 | 78 | False |
| HVAC | r_value | 70 | 70 | False |
| HVAC | seer | 70 | 70 | False |
| HVAC | hvac_age | 70 | 70 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 70 | 70 | False |
| HVAC | seer | 70 | 70 | False |
| HVAC | hvac_age | 70 | 70 | False |
| HVAC | r_value | 71 | 71 | False |
| HVAC | seer | 71 | 71 | False |
| HVAC | hvac_age | 71 | 71 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 69 | 69 | False |
| HVAC | seer | 69 | 69 | False |
| HVAC | hvac_age | 69 | 69 | False |
| HVAC | occupancy_context | 69 | 69 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | occupancy_context | 76 | 76 | False |
| HVAC | r_value | 78 | 78 | False |
| HVAC | seer | 78 | 78 | False |
| HVAC | hvac_age | 78 | 78 | False |
| HVAC | occupancy_context | 78 | 78 | False |
| HVAC | r_value | 68 | 68 | False |
| HVAC | seer | 68 | 68 | False |
| HVAC | hvac_age | 68 | 68 | False |
| HVAC | occupancy_context | 68 | 68 | False |

