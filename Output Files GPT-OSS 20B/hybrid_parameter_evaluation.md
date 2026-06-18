# Hybrid Parameter Extraction Evaluation

## Overview

- Results file: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\hybrid_results.xlsx`
- Matched scenarios: 181/195
- Unmatched scenarios: 14
- Counterfactual rows evaluated: 0

## Numeric Parameter Error Distribution

| n | n_valid | MAE | RMSE | mean_abs_error | median_abs_error | std_abs_error | p25_abs_error | p75_abs_error | p90_abs_error | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 65.0000 | Appliance | kwh_per_cycle |
| 70.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 70.0000 | HVAC | hvac_age |
| 70.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 70.0000 | HVAC | r_value |
| 70.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 70.0000 | HVAC | seer |
| 46.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 46.0000 | Shower | gpm |
| 46.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 46.0000 | Shower | tank_size |
| 46.0000 | 0.0000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.0000 | 46.0000 | Shower | water_heater_temp |

## Categorical Parameter Accuracy

| n | n_valid | accuracy | n_correct | n_incorrect | n_missing_gt | n_missing_extracted | decision_type | parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65.0000 | 0.0000 | N/A | 0.0000 | 0.0000 | 0.0000 | 65.0000 | Appliance | appliance |
| 65.0000 | 0.0000 | N/A | 0.0000 | 0.0000 | 0.0000 | 65.0000 | Appliance | baseline_time |
| 70.0000 | 0.0000 | N/A | 0.0000 | 0.0000 | 0.0000 | 70.0000 | HVAC | occupancy_context |

## Counterfactual Top-1 Sensitivity

_No rows._

