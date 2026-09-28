# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Results file: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files Qwen3.5 9B\LLM-Parameterized_Reference_Scoring_results.xlsx`
- Matched scenarios: 195/195
- Unmatched scenarios: 0
- Counterfactual rows evaluated: 361

## Numeric Parameter Error Distribution

| n | n_valid | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 0.9746 | 1.2910 | 0.9746 | 0.5500 | 0.8533 | 0.3000 | 1.9200 | 2.1380 | 0.0000 | 0.0000 | Appliance | kwh_per_cycle |
| 70.0000 | 70.0000 | 6.1050 | 10.9094 | 6.1050 | 3.4750 | 9.1065 | 2.0000 | 8.0000 | 11.1000 | 0.0000 | 0.0000 | HVAC | hvac_age |
| 70.0000 | 70.0000 | 3.6993 | 4.3394 | 3.6993 | 3.4000 | 2.2848 | 2.0500 | 5.2000 | 6.4200 | 0.0000 | 0.0000 | HVAC | r_value |
| 70.0000 | 70.0000 | 1.5850 | 2.1411 | 1.5850 | 1.0000 | 1.4499 | 0.6000 | 2.1500 | 4.0000 | 0.0000 | 0.0000 | HVAC | seer |
| 60.0000 | 60.0000 | 0.2713 | 0.5010 | 0.2713 | 0.0500 | 0.4248 | 0.0000 | 0.5000 | 1.0000 | 0.0000 | 0.0000 | Shower | gpm |
| 60.0000 | 60.0000 | 8.9333 | 13.2048 | 8.9333 | 10.0000 | 9.8064 | 0.0000 | 10.0000 | 20.0000 | 0.0000 | 0.0000 | Shower | tank_size |
| 60.0000 | 60.0000 | 4.5833 | 8.1904 | 4.5833 | 0.0000 | 6.8452 | 0.0000 | 10.0000 | 15.0000 | 0.0000 | 0.0000 | Shower | water_heater_temp |

## Categorical Parameter Accuracy

| n | n_valid | accuracy | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | appliance |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | baseline_time |
| 70.0000 | 70.0000 | 0.7857 | 55.0000 | 15.0000 | 0.0000 | 0.0000 | HVAC | occupancy_context |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | n_error_cases_evaluated | n_top1_changes | conditional_change_probability | unconditional_change_probability |
| --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 61.0000 | 4.0000 | 0.0656 | 0.0615 |
| HVAC | hvac_age | 67.0000 | 0.0000 | 0.0000 | 0.0000 |
| HVAC | occupancy_context | 15.0000 | 1.0000 | 0.0667 | 0.0143 |
| HVAC | r_value | 70.0000 | 6.0000 | 0.0857 | 0.0857 |
| HVAC | seer | 60.0000 | 2.0000 | 0.0333 | 0.0286 |
| Shower | gpm | 30.0000 | 5.0000 | 0.1667 | 0.0833 |
| Shower | tank_size | 38.0000 | 1.0000 | 0.0263 | 0.0167 |
| Shower | water_heater_temp | 20.0000 | 1.0000 | 0.0500 | 0.0167 |

## Counterfactual Case Detail

| decision_type | parameter | ground_truth_top1 | counterfactual_top1 | changed |
| --- | --- | --- | --- | --- |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 71 | 71 | False |
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
| HVAC | hvac_age | 70 | 70 | False |
| HVAC | r_value | 71 | 71 | False |
| HVAC | seer | 71 | 71 | False |
| HVAC | hvac_age | 71 | 71 | False |
| HVAC | occupancy_context | 71 | 71 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | r_value | 69 | 69 | False |
| HVAC | seer | 69 | 69 | False |
| HVAC | hvac_age | 69 | 69 | False |
| HVAC | occupancy_context | 69 | 69 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 78 | 81 | True |
| HVAC | seer | 78 | 78 | False |
| HVAC | hvac_age | 78 | 78 | False |
| HVAC | occupancy_context | 78 | 78 | False |
| HVAC | r_value | 68 | 68 | False |
| HVAC | seer | 68 | 68 | False |
| HVAC | hvac_age | 68 | 68 | False |
| HVAC | r_value | 78 | 78 | False |
| HVAC | seer | 78 | 78 | False |

