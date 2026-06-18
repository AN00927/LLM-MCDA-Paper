# RAG Ablation Study

## Overview

- Sample size: 2
- Random seed: 13
- Scenarios evaluated: 2
- Result rows: 6
- Output plots: None

## Ablation Configurations

| ablation_id | label | k | retrieval | embedding_model | include_hidden_params | include_scores | include_ranks | llm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_k3 | Control k=3 standard | 3 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | True |

## Overall Summary

| ablation_id | ablation_label | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy | mean_retrieval_distance | retrieval_count | api_calls | successful_calls | failed_calls | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_k3 | Control k=3 standard | 2 | 4.0753 | 4.2414 | 0.3333 | 0.5000 | N/A | N/A | 0.0822 | 6.0000 | 6.0000 | 6.0000 | 0.0000 | N/A |

## Summary by Decision Type

| ablation_id | ablation_label | decision_type | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_k3 | Control k=3 standard | Appliance | 1 | 3.4562 | 3.7597 | 0.3333 | 0.5000 | N/A | N/A |
| control_k3 | Control k=3 standard | HVAC | 1 | 4.6945 | 4.7232 | 0.3333 | 0.5000 | N/A | N/A |

## Highest Score-MAE Cases

| ablation_id | decision_type | source_scenario_id | question | alternative | score_mae | kendall_tau | gt_top1 | pred_top1 | error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_k3 | HVAC | 32 | I'm gone most of the day, what heat temperature should I set? | 60 | 4.6945 | 0.3333 | 68 | 64 |  |
| control_k3 | HVAC | 32 | I'm gone most of the day, what heat temperature should I set? | 64 | 4.6945 | 0.3333 | 68 | 64 |  |
| control_k3 | HVAC | 32 | I'm gone most of the day, what heat temperature should I set? | 68 | 4.6945 | 0.3333 | 68 | 64 |  |
| control_k3 | Appliance | 31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 8:00 AM | 3.4562 | 0.3333 | 8:00 AM | 11:00 PM |  |
| control_k3 | Appliance | 31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 3:00 PM | 3.4562 | 0.3333 | 8:00 AM | 11:00 PM |  |
| control_k3 | Appliance | 31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 11:00 PM | 3.4562 | 0.3333 | 8:00 AM | 11:00 PM |  |

