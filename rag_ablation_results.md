# RAG Ablation Study

## Overview

- Sample size: all
- Random seed: None
- Scenarios evaluated: 90
- Result rows: 5940
- Output plots: None

## Ablation Configurations

_No rows._

## Overall Summary

| model_key | ablation_id | ablation_label | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy | mean_retrieval_distance | retrieval_count | api_calls | successful_calls | failed_calls | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 90 | 0.0876 | 0.0984 | 0.3463 | 0.3749 | 0.4889 | 0.8333 | 1.2152 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| deepseek | control_k3 | Control k=3 standard | 90 | 0.0884 | 0.0984 | 0.4887 | 0.5187 | 0.6333 | 0.8889 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | 90 | 0.1312 | 0.1465 | 0.0733 | 0.0841 | 0.4111 | 0.7000 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | 90 | 0.0874 | 0.0965 | 0.3911 | 0.4128 | 0.5889 | 0.8444 | 0.0723 | 270.0000 | 270.0000 | 269.0000 | 1.0000 | 0.9963 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | 90 | 0.1267 | 0.1432 | 0.0632 | 0.0675 | 0.3889 | 0.7444 | 0.4477 | 270.0000 | 270.0000 | 269.0000 | 1.0000 | 0.9963 |
| deepseek | retrieval_k1 | Retrieval k=1 | 90 | 0.0981 | 0.1114 | 0.1822 | 0.1782 | 0.4778 | 0.7778 | 0.0561 | 90.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| deepseek | retrieval_k5 | Retrieval k=5 | 90 | 0.0842 | 0.0941 | 0.3421 | 0.3663 | 0.5222 | 0.8111 | 0.0847 | 450.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 90 | 0.1127 | 0.1247 | 0.2268 | 0.2426 | 0.4444 | 0.7778 | 1.2152 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | control_k3 | Control k=3 standard | 90 | 0.1045 | 0.1209 | 0.1872 | 0.1682 | 0.4444 | 0.6667 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | 90 | 0.1577 | 0.1770 | 0.0609 | 0.0652 | 0.3333 | 0.7111 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | 90 | 0.1058 | 0.1212 | 0.1754 | 0.1844 | 0.4444 | 0.7111 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | 90 | 0.1634 | 0.1841 | 0.0222 | 0.0222 | 0.3444 | 0.6889 | 0.4469 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | retrieval_k1 | Retrieval k=1 | 90 | 0.1182 | 0.1377 | 0.2367 | 0.2304 | 0.4667 | 0.7556 | 0.0561 | 90.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gptoss | retrieval_k5 | Retrieval k=5 | 90 | 0.1016 | 0.1162 | 0.1124 | 0.1180 | 0.3889 | 0.7000 | 0.0847 | 450.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 90 | 0.1009 | 0.1159 | 0.0011 | 0.0173 | 0.4444 | 0.7222 | 0.0723 | 270.0000 | 0.0000 | 0.0000 | 0.0000 | N/A |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 90 | 0.1039 | 0.1163 | 0.1651 | 0.1640 | 0.4778 | 0.7333 | 1.2152 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| qwen | control_k3 | Control k=3 standard | 90 | 0.1019 | 0.1200 | 0.1535 | 0.1541 | 0.4333 | 0.7444 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | 90 | 0.1511 | 0.1683 | 0.0711 | 0.0763 | 0.4222 | 0.7556 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | 90 | 0.0988 | 0.1136 | 0.2730 | 0.2779 | 0.4667 | 0.7444 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | 90 | 0.1407 | 0.1568 | 0.2756 | 0.2969 | 0.5778 | 0.8444 | 0.4558 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| qwen | retrieval_k1 | Retrieval k=1 | 90 | 0.0968 | 0.1128 | 0.3056 | 0.2969 | 0.5222 | 0.8222 | 0.0561 | 90.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| qwen | retrieval_k5 | Retrieval k=5 | 90 | 0.0880 | 0.1002 | 0.2343 | 0.2708 | 0.4889 | 0.7667 | 0.0847 | 450.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |

## Summary by Decision Type

| model_key | ablation_id | ablation_label | decision_type | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 35 | 0.0881 | 0.1026 | 0.4667 | 0.5143 | 0.6286 | 0.8857 |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 35 | 0.1179 | 0.1289 | 0.0926 | 0.0990 | 0.2286 | 0.7714 |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 20 | 0.0340 | 0.0380 | 0.5667 | 0.6000 | 0.7000 | 0.8500 |
| deepseek | control_k3 | Control k=3 standard | Appliance | 35 | 0.0842 | 0.0978 | 0.5333 | 0.5714 | 0.6857 | 0.9714 |
| deepseek | control_k3 | Control k=3 standard | HVAC | 35 | 0.1216 | 0.1294 | 0.3436 | 0.3616 | 0.4571 | 0.8000 |
| deepseek | control_k3 | Control k=3 standard | Shower | 20 | 0.0379 | 0.0453 | 0.6575 | 0.6933 | 0.8500 | 0.9000 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 35 | 0.1717 | 0.1934 | 0.1038 | 0.1352 | 0.4571 | 0.7429 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 35 | 0.1237 | 0.1361 | 0.0202 | 0.0152 | 0.3429 | 0.6286 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 20 | 0.0733 | 0.0828 | 0.1111 | 0.1111 | 0.4500 | 0.7500 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 35 | 0.0890 | 0.1010 | 0.3922 | 0.4265 | 0.5143 | 0.9143 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 35 | 0.1161 | 0.1240 | 0.2279 | 0.2450 | 0.5714 | 0.7714 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 20 | 0.0346 | 0.0407 | 0.6667 | 0.6750 | 0.7500 | 0.8500 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | Appliance | 35 | 0.1513 | 0.1747 | 0.0216 | 0.0305 | 0.4000 | 0.8000 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | HVAC | 35 | 0.1263 | 0.1406 | 0.0672 | 0.0576 | 0.3143 | 0.6857 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | Shower | 20 | 0.0845 | 0.0925 | 0.1307 | 0.1508 | 0.5000 | 0.7500 |
| deepseek | retrieval_k1 | Retrieval k=1 | Appliance | 35 | 0.1016 | 0.1203 | 0.3333 | 0.3286 | 0.5429 | 0.9143 |
| deepseek | retrieval_k1 | Retrieval k=1 | HVAC | 35 | 0.1260 | 0.1376 | -0.0900 | -0.1105 | 0.3429 | 0.5714 |
| deepseek | retrieval_k1 | Retrieval k=1 | Shower | 20 | 0.0433 | 0.0498 | 0.3942 | 0.4201 | 0.6000 | 0.9000 |
| deepseek | retrieval_k5 | Retrieval k=5 | Appliance | 35 | 0.0865 | 0.1000 | 0.3714 | 0.4000 | 0.6000 | 0.8286 |
| deepseek | retrieval_k5 | Retrieval k=5 | HVAC | 35 | 0.1115 | 0.1211 | 0.0818 | 0.0911 | 0.2857 | 0.7143 |
| deepseek | retrieval_k5 | Retrieval k=5 | Shower | 20 | 0.0326 | 0.0366 | 0.7333 | 0.7750 | 0.8000 | 0.9500 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 35 | 0.1315 | 0.1480 | 0.1757 | 0.1962 | 0.3714 | 0.6857 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 35 | 0.1393 | 0.1512 | 0.1790 | 0.1847 | 0.4571 | 0.8000 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 20 | 0.0334 | 0.0373 | 0.4000 | 0.4250 | 0.5500 | 0.9000 |
| gptoss | control_k3 | Control k=3 standard | Appliance | 35 | 0.1225 | 0.1424 | 0.1238 | 0.0857 | 0.3714 | 0.6571 |
| gptoss | control_k3 | Control k=3 standard | HVAC | 35 | 0.1252 | 0.1433 | 0.1481 | 0.1324 | 0.4571 | 0.6000 |
| gptoss | control_k3 | Control k=3 standard | Shower | 20 | 0.0369 | 0.0442 | 0.3667 | 0.3750 | 0.5500 | 0.8000 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 35 | 0.2265 | 0.2595 | -0.1376 | -0.1533 | 0.2000 | 0.6571 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 35 | 0.1365 | 0.1466 | 0.1143 | 0.1286 | 0.3429 | 0.7143 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 20 | 0.0743 | 0.0860 | 0.3150 | 0.3366 | 0.5500 | 0.8000 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 35 | 0.1271 | 0.1474 | 0.1186 | 0.1247 | 0.3714 | 0.7143 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 35 | 0.1246 | 0.1415 | 0.0414 | 0.0457 | 0.3714 | 0.6571 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 20 | 0.0357 | 0.0398 | 0.5092 | 0.5317 | 0.7000 | 0.8000 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | Appliance | 35 | 0.2308 | 0.2670 | -0.0476 | -0.0571 | 0.2857 | 0.6286 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | HVAC | 35 | 0.1446 | 0.1560 | 0.0857 | 0.0714 | 0.4000 | 0.7143 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | Shower | 20 | 0.0785 | 0.0882 | 0.0333 | 0.0750 | 0.3500 | 0.7500 |
| gptoss | retrieval_k1 | Retrieval k=1 | Appliance | 35 | 0.1480 | 0.1781 | 0.1948 | 0.1819 | 0.4286 | 0.7714 |
| gptoss | retrieval_k1 | Retrieval k=1 | HVAC | 35 | 0.1312 | 0.1464 | 0.0762 | 0.0571 | 0.3714 | 0.6286 |
| gptoss | retrieval_k1 | Retrieval k=1 | Shower | 20 | 0.0435 | 0.0520 | 0.5908 | 0.6183 | 0.7000 | 0.9500 |
| gptoss | retrieval_k5 | Retrieval k=5 | Appliance | 35 | 0.1213 | 0.1384 | 0.0719 | 0.0895 | 0.3429 | 0.7143 |
| gptoss | retrieval_k5 | Retrieval k=5 | HVAC | 35 | 0.1220 | 0.1389 | -0.0152 | -0.0186 | 0.3143 | 0.6286 |
| gptoss | retrieval_k5 | Retrieval k=5 | Shower | 20 | 0.0315 | 0.0377 | 0.4000 | 0.4000 | 0.6000 | 0.8000 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Appliance | 35 | 0.1023 | 0.1176 | 0.0323 | 0.0552 | 0.4000 | 0.7429 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | HVAC | 35 | 0.1269 | 0.1466 | -0.0345 | -0.0261 | 0.3429 | 0.6571 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Shower | 20 | 0.0532 | 0.0592 | N/A | N/A | 0.7000 | 0.8000 |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 35 | 0.1143 | 0.1292 | 0.4348 | 0.4588 | 0.6000 | 0.8286 |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 35 | 0.1282 | 0.1398 | -0.1237 | -0.1615 | 0.2857 | 0.6286 |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 20 | 0.0433 | 0.0528 | 0.1833 | 0.2000 | 0.6000 | 0.7500 |
| qwen | control_k3 | Control k=3 standard | Appliance | 35 | 0.1105 | 0.1310 | 0.3429 | 0.3571 | 0.5429 | 0.8571 |
| qwen | control_k3 | Control k=3 standard | HVAC | 35 | 0.1185 | 0.1353 | -0.0867 | -0.0934 | 0.2571 | 0.6000 |
| qwen | control_k3 | Control k=3 standard | Shower | 20 | 0.0579 | 0.0738 | 0.2425 | 0.2317 | 0.5500 | 0.8000 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 35 | 0.1907 | 0.2123 | 0.2939 | 0.3263 | 0.5429 | 0.8857 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 35 | 0.1437 | 0.1615 | -0.1905 | -0.2143 | 0.2857 | 0.5714 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 20 | 0.0946 | 0.1033 | 0.1658 | 0.1772 | 0.4500 | 0.8500 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 35 | 0.1164 | 0.1336 | 0.3705 | 0.3781 | 0.5714 | 0.8286 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 35 | 0.1121 | 0.1285 | 0.1907 | 0.2019 | 0.4000 | 0.6571 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 20 | 0.0446 | 0.0523 | 0.2425 | 0.2317 | 0.4000 | 0.7500 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | Appliance | 35 | 0.1822 | 0.1982 | 0.4605 | 0.5028 | 0.7429 | 0.9714 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | HVAC | 35 | 0.1331 | 0.1534 | 0.1376 | 0.1390 | 0.4286 | 0.7429 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | Shower | 20 | 0.0814 | 0.0906 | 0.1894 | 0.2086 | 0.5500 | 0.8000 |
| qwen | retrieval_k1 | Retrieval k=1 | Appliance | 35 | 0.1027 | 0.1221 | 0.3567 | 0.3390 | 0.5429 | 0.8571 |
| qwen | retrieval_k1 | Retrieval k=1 | HVAC | 35 | 0.1154 | 0.1316 | 0.2605 | 0.2457 | 0.4571 | 0.7714 |
| qwen | retrieval_k1 | Retrieval k=1 | Shower | 20 | 0.0541 | 0.0636 | 0.2947 | 0.3139 | 0.6000 | 0.8500 |
| qwen | retrieval_k5 | Retrieval k=5 | Appliance | 35 | 0.0939 | 0.1092 | 0.3505 | 0.3990 | 0.5429 | 0.8286 |
| qwen | retrieval_k5 | Retrieval k=5 | HVAC | 35 | 0.1079 | 0.1203 | 0.1146 | 0.1250 | 0.4000 | 0.6857 |
| qwen | retrieval_k5 | Retrieval k=5 | Shower | 20 | 0.0426 | 0.0492 | 0.2225 | 0.2799 | 0.5500 | 0.8000 |

## Highest Score-MAE Cases

| model_key | ablation_id | decision_type | source_scenario_id | question | alternative | score_mae | kendall_tau | gt_top1 | pred_top1 | error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 9:00 PM | 0.5112 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 PM | 0.5112 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 AM | 0.5112 | 1.0000 | 2:00 PM | 2:00 PM |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 81 | 0.4853 | 0.8165 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 74 | 0.4853 | 0.8165 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 77 | 0.4853 | 0.8165 | 77 | 74 |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_28 | It's just past 9 AM and I need to run the dryer. When should I start it? | 10:00 PM | 0.4763 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_28 | It's just past 9 AM and I need to run the dryer. When should I start it? | 2:00 PM | 0.4763 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_28 | It's just past 9 AM and I need to run the dryer. When should I start it? | 9:00 AM | 0.4763 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | alternate_embedding_k3 | HVAC | hvac_20 | With 3 people home, what heat temperature should I set? | 65 | 0.4538 | -1.0000 | 70 | 65 |  |
| qwen | alternate_embedding_k3 | HVAC | hvac_20 | With 3 people home, what heat temperature should I set? | 68 | 0.4538 | -1.0000 | 70 | 65 |  |
| qwen | alternate_embedding_k3 | HVAC | hvac_20 | With 3 people home, what heat temperature should I set? | 70 | 0.4538 | -1.0000 | 70 | 65 |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 8:00 AM | 0.4433 | 0.3333 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 11:00 PM | 0.4433 | 0.3333 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 3:00 PM | 0.4433 | 0.3333 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 5:00 PM | 0.4368 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 1:00 PM | 0.4368 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 5:00 PM | 0.4368 | 0.3333 | 9:00 AM | 1:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 1:00 PM | 0.4368 | 0.3333 | 9:00 AM | 1:00 PM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 9:00 AM | 0.4368 | 0.3333 | 9:00 AM | 9:00 AM |  |

## Friedman Tests (non-parametric omnibus)

Chi-squared statistic for each metric across all ablation configurations.

| metric | chi2 | p_value | df | n_scenarios | n_configs | p_holm | significant_holm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| kendall_tau | 9.8964 | 0.1945 | 7 | 60 | 8 | 0.38904362309330986 | False |
| score_mae | 80.0518 | 0.0000 | 7 | 90 | 8 | 5.3777109154775326e-14 | True |
| score_rmse | 78.9963 | 0.0000 | 7 | 90 | 8 | 6.619230628430016e-14 | True |
| top1_accuracy | 8.6667 | 0.2775 | 7 | 90 | 8 | 0.27748196606419 | False |

## Post-hoc Pairwise Wilcoxon Tests (Holm-corrected)

Significant pairwise differences after Holm-Bonferroni correction.

| metric | config_i | config_j | statistic | p_value | cliff_delta | cliff_delta_interpretation | n_pairs | p_holm | significant_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score_mae | random_exemplars_k3 | retrieval_k5 | 658.0000 | 0.0000 | 0.3464 | medium | 90 | 0.0000 | True |
| score_mae | descriptions_no_scores_ranks | nearest_neighbor_k3 | 701.0000 | 0.0000 | 0.3509 | medium | 90 | 0.0000 | True |
| score_mae | descriptions_no_scores_ranks | retrieval_k5 | 719.0000 | 0.0000 | 0.3502 | medium | 90 | 0.0000 | True |
| score_mae | nearest_neighbor_k3 | random_exemplars_k3 | 724.0000 | 0.0000 | -0.3462 | medium | 90 | 0.0000 | True |
| score_mae | control_k3 | random_exemplars_k3 | 744.5000 | 0.0000 | -0.3262 | small | 90 | 0.0000 | True |
| score_mae | control_k3 | descriptions_no_scores_ranks | 754.0000 | 0.0000 | -0.3264 | small | 90 | 0.0000 | True |
| score_mae | exemplars_no_hidden_params | random_exemplars_k3 | 821.0000 | 0.0000 | -0.3217 | small | 90 | 0.0000 | True |
| score_mae | descriptions_no_scores_ranks | exemplars_no_hidden_params | 826.0000 | 0.0000 | 0.3173 | small | 90 | 0.0000 | True |
| score_mae | alternate_embedding_k3 | random_exemplars_k3 | 952.0000 | 0.0000 | -0.3021 | small | 90 | 0.0002 | True |
| score_mae | random_exemplars_k3 | retrieval_k1 | 966.0000 | 0.0000 | 0.2733 | small | 90 | 0.0003 | True |
| score_mae | alternate_embedding_k3 | descriptions_no_scores_ranks | 1103.0000 | 0.0001 | -0.2821 | small | 90 | 0.0026 | True |
| score_mae | descriptions_no_scores_ranks | retrieval_k1 | 1166.0000 | 0.0004 | 0.2527 | small | 90 | 0.0066 | True |
| score_mae | retrieval_k1 | retrieval_k5 | 1540.0000 | 0.0411 | 0.1152 | negligible | 90 | 0.6584 | False |
| score_mae | nearest_neighbor_k3 | retrieval_k1 | 1571.0000 | 0.0552 | -0.1007 | negligible | 90 | 0.8280 | False |
| score_mae | control_k3 | retrieval_k1 | 1615.5000 | 0.1541 | -0.0885 | negligible | 90 | 1.0000 | False |
| score_mae | exemplars_no_hidden_params | retrieval_k5 | 1630.0000 | 0.1723 | 0.0451 | negligible | 90 | 1.0000 | False |
| score_mae | alternate_embedding_k3 | nearest_neighbor_k3 | 1751.0000 | 0.2329 | 0.0544 | negligible | 90 | 1.0000 | False |
| score_mae | exemplars_no_hidden_params | retrieval_k1 | 1714.0000 | 0.2379 | -0.0758 | negligible | 90 | 1.0000 | False |
| score_mae | alternate_embedding_k3 | retrieval_k5 | 1754.0000 | 0.3093 | 0.0680 | negligible | 90 | 1.0000 | False |
| score_mae | exemplars_no_hidden_params | nearest_neighbor_k3 | 1836.0000 | 0.3948 | 0.0252 | negligible | 90 | 1.0000 | False |
| score_mae | alternate_embedding_k3 | exemplars_no_hidden_params | 1759.0000 | 0.4077 | 0.0247 | negligible | 90 | 1.0000 | False |
| score_mae | alternate_embedding_k3 | control_k3 | 1688.0000 | 0.4320 | 0.0473 | negligible | 90 | 1.0000 | False |
| score_mae | control_k3 | retrieval_k5 | 1733.0000 | 0.4436 | 0.0219 | negligible | 90 | 1.0000 | False |
| score_mae | alternate_embedding_k3 | retrieval_k1 | 1861.0000 | 0.4530 | -0.0548 | negligible | 90 | 1.0000 | False |
| score_mae | descriptions_no_scores_ranks | random_exemplars_k3 | 1904.5000 | 0.6885 | -0.0127 | negligible | 90 | 1.0000 | False |
| score_mae | nearest_neighbor_k3 | retrieval_k5 | 1949.0000 | 0.6919 | 0.0043 | negligible | 90 | 1.0000 | False |
| score_mae | control_k3 | exemplars_no_hidden_params | 1856.0000 | 0.8061 | -0.0160 | negligible | 90 | 1.0000 | False |
| score_mae | control_k3 | nearest_neighbor_k3 | 2006.0000 | 0.8674 | 0.0168 | negligible | 90 | 0.8674 | False |
| score_rmse | random_exemplars_k3 | retrieval_k5 | 715.0000 | 0.0000 | 0.3422 | medium | 90 | 0.0000 | True |
| score_rmse | control_k3 | random_exemplars_k3 | 769.0000 | 0.0000 | -0.3183 | small | 90 | 0.0000 | True |
| score_rmse | nearest_neighbor_k3 | random_exemplars_k3 | 786.0000 | 0.0000 | -0.3420 | medium | 90 | 0.0000 | True |
| score_rmse | descriptions_no_scores_ranks | retrieval_k5 | 791.0000 | 0.0000 | 0.3351 | medium | 90 | 0.0000 | True |
| score_rmse | descriptions_no_scores_ranks | nearest_neighbor_k3 | 796.0000 | 0.0000 | 0.3351 | medium | 90 | 0.0000 | True |
| score_rmse | exemplars_no_hidden_params | random_exemplars_k3 | 814.0000 | 0.0000 | -0.3106 | small | 90 | 0.0000 | True |
| score_rmse | descriptions_no_scores_ranks | exemplars_no_hidden_params | 842.0000 | 0.0000 | 0.3007 | small | 90 | 0.0000 | True |
| score_rmse | control_k3 | descriptions_no_scores_ranks | 859.0000 | 0.0000 | -0.2993 | small | 90 | 0.0000 | True |
| score_rmse | alternate_embedding_k3 | random_exemplars_k3 | 870.0000 | 0.0000 | -0.3158 | small | 90 | 0.0000 | True |
| score_rmse | random_exemplars_k3 | retrieval_k1 | 1018.0000 | 0.0000 | 0.2509 | small | 90 | 0.0007 | True |
| score_rmse | alternate_embedding_k3 | descriptions_no_scores_ranks | 1039.0000 | 0.0000 | -0.2894 | small | 90 | 0.0009 | True |
| score_rmse | descriptions_no_scores_ranks | retrieval_k1 | 1212.0000 | 0.0008 | 0.2267 | small | 90 | 0.0132 | True |
| score_rmse | retrieval_k1 | retrieval_k5 | 1534.0000 | 0.0388 | 0.1138 | negligible | 90 | 0.6210 | False |
| score_rmse | nearest_neighbor_k3 | retrieval_k1 | 1565.0000 | 0.0522 | -0.1049 | negligible | 90 | 0.7831 | False |
| score_rmse | exemplars_no_hidden_params | retrieval_k5 | 1618.0000 | 0.1572 | 0.0468 | negligible | 90 | 1.0000 | False |
| score_rmse | control_k3 | retrieval_k1 | 1710.0000 | 0.1745 | -0.0881 | negligible | 90 | 1.0000 | False |
| score_rmse | alternate_embedding_k3 | retrieval_k1 | 1721.0000 | 0.1889 | -0.0746 | negligible | 90 | 1.0000 | False |
| score_rmse | control_k3 | retrieval_k5 | 1613.0000 | 0.2027 | 0.0284 | negligible | 90 | 1.0000 | False |
| score_rmse | exemplars_no_hidden_params | retrieval_k1 | 1734.0000 | 0.2072 | -0.0765 | negligible | 90 | 1.0000 | False |
| score_rmse | alternate_embedding_k3 | nearest_neighbor_k3 | 1836.0000 | 0.3948 | 0.0427 | negligible | 90 | 1.0000 | False |
| score_rmse | exemplars_no_hidden_params | nearest_neighbor_k3 | 1838.0000 | 0.3992 | 0.0291 | negligible | 90 | 1.0000 | False |
| score_rmse | alternate_embedding_k3 | retrieval_k5 | 1819.0000 | 0.4528 | 0.0530 | negligible | 90 | 1.0000 | False |
| score_rmse | nearest_neighbor_k3 | retrieval_k5 | 1919.0000 | 0.6051 | 0.0069 | negligible | 90 | 1.0000 | False |
| score_rmse | descriptions_no_scores_ranks | random_exemplars_k3 | 1926.0000 | 0.6249 | -0.0175 | negligible | 90 | 1.0000 | False |
| score_rmse | control_k3 | nearest_neighbor_k3 | 1958.0000 | 0.7188 | 0.0331 | negligible | 90 | 1.0000 | False |
| score_rmse | alternate_embedding_k3 | exemplars_no_hidden_params | 1874.0000 | 0.7267 | 0.0083 | negligible | 90 | 1.0000 | False |
| score_rmse | alternate_embedding_k3 | control_k3 | 1820.0000 | 0.8279 | 0.0216 | negligible | 90 | 1.0000 | False |
| score_rmse | control_k3 | exemplars_no_hidden_params | 1912.0000 | 0.9932 | -0.0098 | negligible | 90 | 0.9932 | False |

## Bootstrap 95% Confidence Intervals

Percentile-method 95% CIs for each configuration's mean metric value.

| ablation_id | ablation_label | point_estimate | ci_lower | ci_upper | metric |
| --- | --- | --- | --- | --- | --- |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.2466 | 0.1657 | 0.3241 | kendall_tau |
| control_k3 | Control k=3 standard | 0.2757 | 0.1939 | 0.3561 | kendall_tau |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.0683 | -0.0105 | 0.1493 | kendall_tau |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 0.2790 | 0.1995 | 0.3592 | kendall_tau |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.0011 | -0.1753 | 0.1722 | kendall_tau |
| random_exemplars_k3 | Random exemplars k=3 | 0.1206 | 0.0442 | 0.1961 | kendall_tau |
| retrieval_k1 | Retrieval k=1 | 0.2413 | 0.1596 | 0.3254 | kendall_tau |
| retrieval_k5 | Retrieval k=5 | 0.2296 | 0.1464 | 0.3107 | kendall_tau |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.1014 | 0.0928 | 0.1105 | score_mae |
| control_k3 | Control k=3 standard | 0.0983 | 0.0899 | 0.1072 | score_mae |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1466 | 0.1362 | 0.1578 | score_mae |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 0.0974 | 0.0893 | 0.1057 | score_mae |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.1009 | 0.0877 | 0.1153 | score_mae |
| random_exemplars_k3 | Random exemplars k=3 | 0.1436 | 0.1329 | 0.1548 | score_mae |
| retrieval_k1 | Retrieval k=1 | 0.1044 | 0.0958 | 0.1134 | score_mae |
| retrieval_k5 | Retrieval k=5 | 0.0913 | 0.0838 | 0.0991 | score_mae |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.4704 | 0.4111 | 0.5296 | top1_accuracy |
| control_k3 | Control k=3 standard | 0.5037 | 0.4444 | 0.5630 | top1_accuracy |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.3889 | 0.3296 | 0.4481 | top1_accuracy |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 0.5000 | 0.4407 | 0.5593 | top1_accuracy |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.4444 | 0.3444 | 0.5444 | top1_accuracy |
| random_exemplars_k3 | Random exemplars k=3 | 0.4370 | 0.3778 | 0.4963 | top1_accuracy |
| retrieval_k1 | Retrieval k=1 | 0.4889 | 0.4296 | 0.5481 | top1_accuracy |
| retrieval_k5 | Retrieval k=5 | 0.4667 | 0.4074 | 0.5259 | top1_accuracy |

