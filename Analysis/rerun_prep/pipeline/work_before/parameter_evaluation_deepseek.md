# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation

## Overview

- Results file: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files DeepSeek V4 Flash\LLM-Parameterized_Reference_Scoring_results.xlsx`
- Matched scenarios: 195/195
- Unmatched scenarios: 0
- Counterfactual rows evaluated: 415

## Numeric Parameter Error Distribution

| n | n_valid | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 0.3410 | 0.4681 | 0.3410 | 0.2500 | 0.3231 | 0.1500 | 0.5000 | 0.6640 | 0.0000 | 0.0000 | Appliance | kwh_per_cycle |
| 70.0000 | 70.0000 | 8.4621 | 13.5921 | 8.4621 | 5.5000 | 10.7134 | 2.0000 | 12.2500 | 17.6600 | 0.0000 | 0.0000 | HVAC | hvac_age |
| 70.0000 | 70.0000 | 2.3121 | 2.8652 | 2.3121 | 2.0000 | 1.7044 | 1.0000 | 3.0000 | 4.2800 | 0.0000 | 0.0000 | HVAC | r_value |
| 70.0000 | 70.0000 | 1.6021 | 2.0638 | 1.6021 | 1.1000 | 1.3104 | 0.8000 | 2.3500 | 3.2000 | 0.0000 | 0.0000 | HVAC | seer |
| 60.0000 | 60.0000 | 0.3680 | 0.5009 | 0.3680 | 0.3600 | 0.3427 | 0.0800 | 0.4625 | 0.8000 | 0.0000 | 0.0000 | Shower | gpm |
| 60.0000 | 60.0000 | 6.9333 | 10.3392 | 6.9333 | 6.0000 | 7.7347 | 0.0000 | 10.0000 | 15.1000 | 0.0000 | 0.0000 | Shower | tank_size |
| 60.0000 | 60.0000 | 8.3167 | 10.6716 | 8.3167 | 7.0000 | 6.7435 | 3.5000 | 15.2500 | 16.0000 | 0.0000 | 0.0000 | Shower | water_heater_temp |

## Categorical Parameter Accuracy

| n | n_valid | accuracy | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | appliance |
| 65.0000 | 65.0000 | 1.0000 | 65.0000 | 0.0000 | 0.0000 | 0.0000 | Appliance | baseline_time |
| 70.0000 | 70.0000 | 0.8143 | 57.0000 | 13.0000 | 0.0000 | 0.0000 | HVAC | occupancy_context |

## Counterfactual Top-1 Sensitivity

| decision_type | parameter | n_error_cases_evaluated | n_top1_changes | conditional_change_probability | unconditional_change_probability |
| --- | --- | --- | --- | --- | --- |
| Appliance | kwh_per_cycle | 63.0000 | 1.0000 | 0.0159 | 0.0154 |
| HVAC | hvac_age | 66.0000 | 0.0000 | 0.0000 | 0.0000 |
| HVAC | occupancy_context | 13.0000 | 1.0000 | 0.0769 | 0.0143 |
| HVAC | r_value | 68.0000 | 1.0000 | 0.0147 | 0.0143 |
| HVAC | seer | 63.0000 | 2.0000 | 0.0317 | 0.0286 |
| Shower | gpm | 54.0000 | 10.0000 | 0.1852 | 0.1667 |
| Shower | tank_size | 40.0000 | 1.0000 | 0.0250 | 0.0167 |
| Shower | water_heater_temp | 48.0000 | 2.0000 | 0.0417 | 0.0333 |

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
| HVAC | r_value | 78 | 81 | True |
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
| HVAC | r_value | 76 | 76 | False |
| HVAC | seer | 76 | 76 | False |
| HVAC | hvac_age | 76 | 76 | False |
| HVAC | r_value | 78 | 78 | False |
| HVAC | seer | 78 | 78 | False |
| HVAC | hvac_age | 78 | 78 | False |
| HVAC | occupancy_context | 78 | 78 | False |
| HVAC | r_value | 68 | 68 | False |

