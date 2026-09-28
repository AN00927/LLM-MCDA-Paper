# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Results file: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Gemini 3.5 Flash\LLM-Parameterized_Reference_Scoring_results.xlsx`
- Matched scenarios: 195/195
- Unmatched scenarios: 0
- Counterfactual rows evaluated: 337

## Numeric Parameter Error Distribution

| n | n_valid | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 0.5412 | 0.7130 | 0.5412 | 0.3500 | 0.4678 | 0.1500 | 1.0000 | 1.1200 | 0.0000 | 0.0000 | Appliance | kwh_per_cycle |
| 70.0000 | 70.0000 | 7.6400 | 13.4012 | 7.6400 | 4.1000 | 11.0897 | 1.0000 | 10.8500 | 16.4600 | 0.0000 | 0.0000 | HVAC | hvac_age |
| 70.0000 | 70.0000 | 1.7657 | 2.2768 | 1.7657 | 1.0000 | 1.4478 | 1.0000 | 3.0000 | 4.0000 | 0.0000 | 0.0000 | HVAC | r_value |
| 70.0000 | 70.0000 | 1.3129 | 1.9012 | 1.3129 | 1.0000 | 1.3850 | 0.2000 | 2.0000 | 3.2400 | 0.0000 | 0.0000 | HVAC | seer |
| 60.0000 | 60.0000 | 0.3667 | 0.5774 | 0.3667 | 0.2500 | 0.4497 | 0.0000 | 0.5000 | 1.0000 | 0.0000 | 0.0000 | Shower | gpm |
| 60.0000 | 60.0000 | 6.7333 | 11.8025 | 6.7333 | 0.0000 | 9.7752 | 0.0000 | 10.0000 | 20.0000 | 0.0000 | 0.0000 | Shower | tank_size |
| 60.0000 | 60.0000 | 4.5833 | 8.1904 | 4.5833 | 0.0000 | 6.8452 | 0.0000 | 10.0000 | 15.0000 | 0.0000 | 0.0000 | Shower | water_heater_temp |

## Categorical Parameter Accuracy

| n | n_valid | accuracy | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 0.9385 | 61.0000 | 4.0000 | 0.0000 | 0.0000 | Appliance | appliance |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | baseline_time |
| 70.0000 | 70.0000 | 0.8000 | 56.0000 | 14.0000 | 0.0000 | 0.0000 | HVAC | occupancy_context |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | n_error_cases_evaluated | n_top1_changes | conditional_change_probability | unconditional_change_probability |
| --- | --- | --- | --- | --- | --- |
| Appliance | appliance | 4.0000 | 0.0000 | 0.0000 | 0.0000 |
| Appliance | kwh_per_cycle | 65.0000 | 2.0000 | 0.0308 | 0.0308 |
| HVAC | hvac_age | 64.0000 | 0.0000 | 0.0000 | 0.0000 |
| HVAC | occupancy_context | 14.0000 | 1.0000 | 0.0714 | 0.0143 |
| HVAC | r_value | 59.0000 | 0.0000 | 0.0000 | 0.0000 |
| HVAC | seer | 53.0000 | 4.0000 | 0.0755 | 0.0571 |
| Shower | gpm | 30.0000 | 7.0000 | 0.2333 | 0.1167 |
| Shower | tank_size | 28.0000 | 0.0000 | 0.0000 | 0.0000 |
| Shower | water_heater_temp | 20.0000 | 1.0000 | 0.0500 | 0.0167 |

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
| HVAC | seer | 68 | 68 | False |
| HVAC | hvac_age | 68 | 68 | False |
| HVAC | r_value | 77 | 77 | False |
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
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 69 | 69 | False |
| HVAC | hvac_age | 69 | 69 | False |
| HVAC | occupancy_context | 69 | 69 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | occupancy_context | 76 | 76 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 78 | 78 | False |
| HVAC | seer | 78 | 78 | False |
| HVAC | hvac_age | 78 | 78 | False |
| HVAC | r_value | 68 | 68 | False |
| HVAC | seer | 68 | 68 | False |
| HVAC | hvac_age | 68 | 68 | False |
| HVAC | occupancy_context | 68 | 68 | False |
| HVAC | seer | 78 | 78 | False |
| HVAC | hvac_age | 78 | 78 | False |

