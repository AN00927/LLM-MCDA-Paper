# RAG Ablation Study

## Overview

- Sample size: 3
- Random seed: 13
- Scenarios evaluated: 3
- Result rows: 9
- Output plots: `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\rag_ablation_score_mae.png`, `C:\Users\Ahaan\LLM-MCDA Paper\Output Files GPT-OSS 20B\rag_ablation_retrieval_distance.png`

## Ablation Configurations

| ablation_id | label | k | retrieval | embedding_model | include_hidden_params | include_scores | include_ranks | llm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 3 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | False |

## Overall Summary

| ablation_id | ablation_label | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy | mean_retrieval_distance | retrieval_count | api_calls | successful_calls | failed_calls | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 3 | 1.3252 | 1.3841 | 0.8165 | 0.8660 | N/A | N/A | 0.0685 | 9.0000 | 0.0000 | 0.0000 | 0.0000 | N/A |

## Summary by Decision Type

| ablation_id | ablation_label | decision_type | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Appliance | 1 | 1.4788 | 1.5818 | 0.8165 | 0.8660 | N/A | N/A |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | HVAC | 1 | 2.1279 | 2.1830 | 0.8165 | 0.8660 | N/A | N/A |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Shower | 1 | 0.3688 | 0.3875 | N/A | N/A | N/A | N/A |

## Highest Score-MAE Cases

| ablation_id | decision_type | source_scenario_id | question | alternative | score_mae | kendall_tau | gt_top1 | pred_top1 | error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nearest_neighbor_k3 | HVAC | 32 | I'm gone most of the day, what heat temperature should I set? | 60 | 2.1279 | 0.8165 | 68 | 68 |  |
| nearest_neighbor_k3 | HVAC | 32 | I'm gone most of the day, what heat temperature should I set? | 64 | 2.1279 | 0.8165 | 68 | 68 |  |
| nearest_neighbor_k3 | HVAC | 32 | I'm gone most of the day, what heat temperature should I set? | 68 | 2.1279 | 0.8165 | 68 | 68 |  |
| nearest_neighbor_k3 | Appliance | 31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 8:00 AM | 1.4788 | 0.8165 | 8:00 AM | 8:00 AM |  |
| nearest_neighbor_k3 | Appliance | 31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 3:00 PM | 1.4788 | 0.8165 | 8:00 AM | 8:00 AM |  |
| nearest_neighbor_k3 | Appliance | 31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 11:00 PM | 1.4788 | 0.8165 | 8:00 AM | 8:00 AM |  |
| nearest_neighbor_k3 | Shower | 17 | How long should I shower? | 3 | 0.3688 | N/A | 3 | 3 |  |
| nearest_neighbor_k3 | Shower | 17 | How long should I shower? | 5 | 0.3688 | N/A | 3 | 3 |  |
| nearest_neighbor_k3 | Shower | 17 | How long should I shower? | 8 | 0.3688 | N/A | 3 | 3 |  |

