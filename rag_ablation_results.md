# RAG Ablation Study

## Overview

- Sample size: all
- Random seed: None
- Scenarios evaluated: 90
- Result rows: 7830
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
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 90 | 0.0711 | 0.0795 | 0.5174 | 0.5577 | 0.7222 | 0.8667 | 1.2152 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gemini | control_k3 | Control k=3 standard | 90 | 0.0705 | 0.0801 | 0.3868 | 0.4041 | 0.5667 | 0.8111 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | 90 | 0.1427 | 0.1619 | 0.2037 | 0.2167 | 0.4000 | 0.7556 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | 90 | 0.0779 | 0.0892 | 0.4367 | 0.4470 | 0.6111 | 0.8000 | 0.0723 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | 90 | 0.1391 | 0.1565 | 0.1774 | 0.1804 | 0.4333 | 0.7333 | 0.4469 | 270.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gemini | retrieval_k1 | Retrieval k=1 | 90 | 0.0968 | 0.1088 | 0.3774 | 0.3748 | 0.5778 | 0.8333 | 0.0561 | 90.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
| gemini | retrieval_k5 | Retrieval k=5 | 90 | 0.0691 | 0.0778 | 0.4313 | 0.4430 | 0.6444 | 0.8222 | 0.0847 | 450.0000 | 270.0000 | 270.0000 | 0.0000 | 1.0000 |
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
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 35 | 0.0657 | 0.0751 | 0.6709 | 0.7105 | 0.8000 | 0.9429 |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 35 | 0.1030 | 0.1136 | 0.2319 | 0.2885 | 0.5429 | 0.7714 |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 20 | 0.0249 | 0.0277 | 0.7483 | 0.7616 | 0.9000 | 0.9000 |
| gemini | control_k3 | Control k=3 standard | Appliance | 35 | 0.0653 | 0.0743 | 0.6848 | 0.7209 | 0.7714 | 0.9429 |
| gemini | control_k3 | Control k=3 standard | HVAC | 35 | 0.0992 | 0.1128 | 0.0762 | 0.0714 | 0.3429 | 0.6857 |
| gemini | control_k3 | Control k=3 standard | Shower | 20 | 0.0293 | 0.0331 | 0.4092 | 0.4317 | 0.6000 | 0.8000 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 35 | 0.1877 | 0.2142 | 0.1810 | 0.1857 | 0.4857 | 0.7429 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 35 | 0.1502 | 0.1695 | 0.1524 | 0.1571 | 0.2857 | 0.7714 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 20 | 0.0507 | 0.0569 | 0.3333 | 0.3750 | 0.4500 | 0.7500 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 35 | 0.0671 | 0.0753 | 0.7090 | 0.7247 | 0.8286 | 0.9143 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 35 | 0.1168 | 0.1355 | 0.1471 | 0.1533 | 0.3429 | 0.6857 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 20 | 0.0288 | 0.0324 | 0.4667 | 0.4750 | 0.7000 | 0.8000 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | Appliance | 35 | 0.1848 | 0.2108 | 0.1757 | 0.1676 | 0.4571 | 0.7429 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | HVAC | 35 | 0.1416 | 0.1576 | 0.0190 | 0.0286 | 0.2857 | 0.7143 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | Shower | 20 | 0.0547 | 0.0595 | 0.4575 | 0.4683 | 0.6500 | 0.7500 |
| gemini | retrieval_k1 | Retrieval k=1 | Appliance | 35 | 0.0893 | 0.1022 | 0.4605 | 0.4742 | 0.6571 | 0.8857 |
| gemini | retrieval_k1 | Retrieval k=1 | HVAC | 35 | 0.1397 | 0.1551 | 0.1862 | 0.1610 | 0.4000 | 0.7714 |
| gemini | retrieval_k1 | Retrieval k=1 | Shower | 20 | 0.0349 | 0.0393 | 0.5667 | 0.5750 | 0.7500 | 0.8500 |
| gemini | retrieval_k5 | Retrieval k=5 | Appliance | 35 | 0.0662 | 0.0737 | 0.6233 | 0.6533 | 0.8286 | 0.9143 |
| gemini | retrieval_k5 | Retrieval k=5 | HVAC | 35 | 0.0966 | 0.1090 | 0.1376 | 0.1247 | 0.4000 | 0.7143 |
| gemini | retrieval_k5 | Retrieval k=5 | Shower | 20 | 0.0263 | 0.0302 | 0.6092 | 0.6317 | 0.7500 | 0.8500 |
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
| qwen | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 PM | 0.5112 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 AM | 0.5112 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 9:00 PM | 0.5112 | 1.0000 | 2:00 PM | 2:00 PM |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 74 | 0.4853 | 0.8165 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 81 | 0.4853 | 0.8165 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 77 | 0.4853 | 0.8165 | 77 | 74 |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_28 | It's just past 9 AM and I need to run the dryer. When should I start it? | 9:00 AM | 0.4763 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_28 | It's just past 9 AM and I need to run the dryer. When should I start it? | 2:00 PM | 0.4763 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_28 | It's just past 9 AM and I need to run the dryer. When should I start it? | 10:00 PM | 0.4763 | 0.3333 | 9:00 AM | 9:00 AM |  |
| gemini | retrieval_k1 | HVAC | hvac_19 | I'm stepping out for a few hours, what heat temperature should I set for the condo? | 69 | 0.4747 | 0.8165 | 69 | 66 |  |
| gemini | retrieval_k1 | HVAC | hvac_19 | I'm stepping out for a few hours, what heat temperature should I set for the condo? | 62 | 0.4747 | 0.8165 | 69 | 66 |  |
| gemini | retrieval_k1 | HVAC | hvac_19 | I'm stepping out for a few hours, what heat temperature should I set for the condo? | 66 | 0.4747 | 0.8165 | 69 | 66 |  |
| qwen | alternate_embedding_k3 | HVAC | hvac_20 | With 3 people home, what heat temperature should I set? | 70 | 0.4538 | -1.0000 | 70 | 65 |  |
| qwen | alternate_embedding_k3 | HVAC | hvac_20 | With 3 people home, what heat temperature should I set? | 65 | 0.4538 | -1.0000 | 70 | 65 |  |
| qwen | alternate_embedding_k3 | HVAC | hvac_20 | With 3 people home, what heat temperature should I set? | 68 | 0.4538 | -1.0000 | 70 | 65 |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 8:00 AM | 0.4433 | 0.3333 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 3:00 PM | 0.4433 | 0.3333 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 11:00 PM | 0.4433 | 0.3333 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 5:00 PM | 0.4368 | 0.3333 | 9:00 AM | 9:00 AM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_2 | It's just past 9 AM, when should I run the dryer? | 5:00 PM | 0.4368 | 0.3333 | 9:00 AM | 1:00 PM |  |

## Friedman Tests (non-parametric omnibus, per model)

Chi-squared statistic for each metric across all ablation configurations, run separately within each model. Holm-Bonferroni is applied once across the whole (model x metric) family; read `p_holm`, not `p_value`.

| model_key | metric | chi2 | p_value | df | n_scenarios | n_configs | p_holm | significant_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | kendall_tau | 43.3216 | 0.0000 | 6 | 77 | 7 | 7.051606622463138e-07 | True |
| deepseek | score_mae | 62.0928 | 0.0000 | 6 | 90 | 7 | 1.5202460589458976e-10 | True |
| deepseek | score_rmse | 67.9149 | 0.0000 | 6 | 90 | 7 | 1.0936229662162663e-11 | True |
| deepseek | top1_accuracy | 20.9372 | 0.0019 | 6 | 90 | 7 | 0.00941455731425981 | True |
| gemini | kendall_tau | 21.2666 | 0.0016 | 6 | 90 | 7 | 0.009856970827496998 | True |
| gemini | score_mae | 155.3541 | 0.0000 | 6 | 90 | 7 | 9.123213414849161e-30 | True |
| gemini | score_rmse | 154.6213 | 0.0000 | 6 | 90 | 7 | 1.2223063464707673e-29 | True |
| gemini | top1_accuracy | 43.7228 | 0.0000 | 6 | 90 | 7 | 6.711443015914067e-07 | True |
| gptoss | kendall_tau | 15.3804 | 0.0175 | 6 | 89 | 7 | 0.06998313931856305 | False |
| gptoss | score_mae | 75.9194 | 0.0000 | 6 | 90 | 7 | 2.978322054167352e-13 | True |
| gptoss | score_rmse | 75.4082 | 0.0000 | 6 | 90 | 7 | 3.4791556525647666e-13 | True |
| gptoss | top1_accuracy | 8.1041 | 0.2306 | 6 | 90 | 7 | 0.6917243843065054 | False |
| qwen | kendall_tau | 7.6750 | 0.2629 | 6 | 78 | 7 | 0.5257935016800347 | False |
| qwen | score_mae | 84.7722 | 0.0000 | 6 | 90 | 7 | 4.783983741774706e-15 | True |
| qwen | score_rmse | 84.8439 | 0.0000 | 6 | 90 | 7 | 4.978930818032763e-15 | True |
| qwen | top1_accuracy | 6.7728 | 0.3424 | 6 | 90 | 7 | 0.3423673685841852 | False |

## Post-hoc Pairwise Wilcoxon Tests (Holm-corrected, within model)

Pairwise differences within each model, computed only for (model, metric) cells whose Friedman omnibus survived the family correction above, and Holm-corrected within their own (model x metric) family.

| model_key | metric | config_i | config_j | statistic | p_value | cliff_delta | cliff_delta_interpretation | n_pairs | p_holm | significant_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | kendall_tau | control_k3 | random_exemplars_k3 | 334.5000 | 0.0000 | 0.3977 | medium | 77 | 0.0002 | True |
| deepseek | kendall_tau | control_k3 | descriptions_no_scores_ranks | 457.0000 | 0.0001 | 0.3852 | medium | 77 | 0.0019 | True |
| deepseek | kendall_tau | control_k3 | retrieval_k1 | 218.5000 | 0.0001 | 0.2468 | small | 77 | 0.0027 | True |
| deepseek | kendall_tau | exemplars_no_hidden_params | random_exemplars_k3 | 495.0000 | 0.0019 | 0.2896 | small | 77 | 0.0347 | True |
| deepseek | kendall_tau | random_exemplars_k3 | retrieval_k5 | 532.0000 | 0.0076 | -0.2628 | small | 77 | 0.1288 | False |
| deepseek | kendall_tau | alternate_embedding_k3 | random_exemplars_k3 | 553.5000 | 0.0077 | 0.2613 | small | 77 | 0.1227 | False |
| deepseek | kendall_tau | descriptions_no_scores_ranks | exemplars_no_hidden_params | 625.5000 | 0.0086 | -0.2761 | small | 77 | 0.1292 | False |
| deepseek | kendall_tau | alternate_embedding_k3 | descriptions_no_scores_ranks | 521.0000 | 0.0094 | 0.2474 | small | 77 | 0.1310 | False |
| deepseek | kendall_tau | descriptions_no_scores_ranks | retrieval_k5 | 671.5000 | 0.0135 | -0.2516 | small | 77 | 0.1757 | False |
| deepseek | kendall_tau | control_k3 | retrieval_k5 | 248.0000 | 0.0174 | 0.1157 | negligible | 77 | 0.2084 | False |
| deepseek | kendall_tau | exemplars_no_hidden_params | retrieval_k1 | 401.5000 | 0.0220 | 0.1518 | small | 77 | 0.2421 | False |
| deepseek | kendall_tau | control_k3 | exemplars_no_hidden_params | 170.0000 | 0.0285 | 0.0918 | negligible | 77 | 0.2847 | False |
| deepseek | kendall_tau | retrieval_k1 | retrieval_k5 | 330.5000 | 0.0342 | -0.1248 | negligible | 77 | 0.3075 | False |
| deepseek | kendall_tau | alternate_embedding_k3 | control_k3 | 330.5000 | 0.0540 | -0.1343 | negligible | 77 | 0.4322 | False |
| deepseek | kendall_tau | alternate_embedding_k3 | retrieval_k1 | 392.0000 | 0.0677 | 0.1235 | negligible | 77 | 0.4741 | False |
| deepseek | kendall_tau | random_exemplars_k3 | retrieval_k1 | 917.0000 | 0.1646 | -0.1332 | negligible | 77 | 0.9874 | False |
| deepseek | kendall_tau | descriptions_no_scores_ranks | retrieval_k1 | 868.0000 | 0.3370 | -0.1184 | negligible | 77 | 1.0000 | False |
| deepseek | kendall_tau | alternate_embedding_k3 | exemplars_no_hidden_params | 360.0000 | 0.6747 | -0.0337 | negligible | 77 | 1.0000 | False |
| deepseek | kendall_tau | descriptions_no_scores_ranks | random_exemplars_k3 | 1001.5000 | 0.7962 | 0.0138 | negligible | 77 | 1.0000 | False |
| deepseek | kendall_tau | exemplars_no_hidden_params | retrieval_k5 | 477.0000 | 0.8323 | 0.0229 | negligible | 77 | 1.0000 | False |
| deepseek | kendall_tau | alternate_embedding_k3 | retrieval_k5 | 506.5000 | 0.9006 | -0.0130 | negligible | 77 | 0.9006 | False |
| deepseek | score_mae | descriptions_no_scores_ranks | retrieval_k5 | 753.0000 | 0.0000 | 0.4001 | medium | 90 | 0.0000 | True |
| deepseek | score_mae | alternate_embedding_k3 | descriptions_no_scores_ranks | 816.0000 | 0.0000 | -0.3656 | medium | 90 | 0.0000 | True |
| deepseek | score_mae | control_k3 | descriptions_no_scores_ranks | 899.0000 | 0.0000 | -0.3815 | medium | 90 | 0.0001 | True |
| deepseek | score_mae | descriptions_no_scores_ranks | exemplars_no_hidden_params | 914.0000 | 0.0000 | 0.3789 | medium | 90 | 0.0001 | True |
| deepseek | score_mae | random_exemplars_k3 | retrieval_k5 | 936.0000 | 0.0000 | 0.3696 | medium | 90 | 0.0001 | True |
| deepseek | score_mae | alternate_embedding_k3 | random_exemplars_k3 | 964.5000 | 0.0000 | -0.3431 | medium | 90 | 0.0002 | True |
| deepseek | score_mae | control_k3 | random_exemplars_k3 | 1045.0000 | 0.0001 | -0.3611 | medium | 90 | 0.0008 | True |
| deepseek | score_mae | exemplars_no_hidden_params | random_exemplars_k3 | 1053.5000 | 0.0001 | -0.3594 | medium | 90 | 0.0009 | True |
| deepseek | score_mae | descriptions_no_scores_ranks | retrieval_k1 | 1245.0000 | 0.0012 | 0.2730 | small | 90 | 0.0161 | True |
| deepseek | score_mae | random_exemplars_k3 | retrieval_k1 | 1359.0000 | 0.0056 | 0.2436 | small | 90 | 0.0672 | False |
| deepseek | score_mae | retrieval_k1 | retrieval_k5 | 1395.0000 | 0.0192 | 0.1296 | negligible | 90 | 0.2107 | False |
| deepseek | score_mae | control_k3 | retrieval_k1 | 1426.0000 | 0.0556 | -0.1149 | negligible | 90 | 0.5562 | False |
| deepseek | score_mae | alternate_embedding_k3 | retrieval_k1 | 1465.5000 | 0.0577 | -0.1002 | negligible | 90 | 0.5190 | False |
| deepseek | score_mae | exemplars_no_hidden_params | retrieval_k1 | 1470.0000 | 0.0846 | -0.1112 | negligible | 90 | 0.6769 | False |
| deepseek | score_mae | descriptions_no_scores_ranks | random_exemplars_k3 | 1745.0000 | 0.2235 | 0.0523 | negligible | 90 | 1.0000 | False |
| deepseek | score_mae | alternate_embedding_k3 | control_k3 | 1656.0000 | 0.3557 | 0.0194 | negligible | 90 | 1.0000 | False |
| deepseek | score_mae | alternate_embedding_k3 | exemplars_no_hidden_params | 1620.5000 | 0.4632 | 0.0180 | negligible | 90 | 1.0000 | False |
| deepseek | score_mae | control_k3 | exemplars_no_hidden_params | 1244.5000 | 0.5601 | -0.0083 | negligible | 90 | 1.0000 | False |
| deepseek | score_mae | alternate_embedding_k3 | retrieval_k5 | 1757.0000 | 0.6250 | 0.0259 | negligible | 90 | 1.0000 | False |
| deepseek | score_mae | exemplars_no_hidden_params | retrieval_k5 | 1557.0000 | 0.6260 | 0.0151 | negligible | 90 | 1.0000 | False |
| deepseek | score_mae | control_k3 | retrieval_k5 | 1738.0000 | 0.9819 | 0.0083 | negligible | 90 | 0.9819 | False |
| deepseek | score_rmse | descriptions_no_scores_ranks | retrieval_k5 | 733.0000 | 0.0000 | 0.4015 | medium | 90 | 0.0000 | True |
| deepseek | score_rmse | alternate_embedding_k3 | descriptions_no_scores_ranks | 819.0000 | 0.0000 | -0.3654 | medium | 90 | 0.0000 | True |
| deepseek | score_rmse | random_exemplars_k3 | retrieval_k5 | 824.0000 | 0.0000 | 0.3889 | medium | 90 | 0.0000 | True |
| deepseek | score_rmse | control_k3 | descriptions_no_scores_ranks | 864.0000 | 0.0000 | -0.3810 | medium | 90 | 0.0000 | True |
| deepseek | score_rmse | descriptions_no_scores_ranks | exemplars_no_hidden_params | 889.0000 | 0.0000 | 0.3928 | medium | 90 | 0.0001 | True |
| deepseek | score_rmse | alternate_embedding_k3 | random_exemplars_k3 | 902.0000 | 0.0000 | -0.3580 | medium | 90 | 0.0001 | True |
| deepseek | score_rmse | control_k3 | random_exemplars_k3 | 930.0000 | 0.0000 | -0.3726 | medium | 90 | 0.0001 | True |
| deepseek | score_rmse | exemplars_no_hidden_params | random_exemplars_k3 | 950.0000 | 0.0000 | -0.3812 | medium | 90 | 0.0001 | True |
| deepseek | score_rmse | descriptions_no_scores_ranks | retrieval_k1 | 1249.0000 | 0.0013 | 0.2677 | small | 90 | 0.0171 | True |
| deepseek | score_rmse | random_exemplars_k3 | retrieval_k1 | 1283.0000 | 0.0021 | 0.2489 | small | 90 | 0.0252 | True |
| deepseek | score_rmse | retrieval_k1 | retrieval_k5 | 1339.0000 | 0.0100 | 0.1305 | negligible | 90 | 0.1101 | False |
| deepseek | score_rmse | control_k3 | retrieval_k1 | 1399.0000 | 0.0293 | -0.1190 | negligible | 90 | 0.2928 | False |
| deepseek | score_rmse | exemplars_no_hidden_params | retrieval_k1 | 1393.0000 | 0.0398 | -0.1257 | negligible | 90 | 0.3579 | False |
| deepseek | score_rmse | alternate_embedding_k3 | retrieval_k1 | 1433.0000 | 0.0418 | -0.0989 | negligible | 90 | 0.3342 | False |
| deepseek | score_rmse | alternate_embedding_k3 | exemplars_no_hidden_params | 1612.0000 | 0.4404 | 0.0201 | negligible | 90 | 1.0000 | False |
| deepseek | score_rmse | descriptions_no_scores_ranks | random_exemplars_k3 | 1865.0000 | 0.4628 | 0.0267 | negligible | 90 | 1.0000 | False |
| deepseek | score_rmse | control_k3 | exemplars_no_hidden_params | 1290.0000 | 0.4759 | -0.0079 | negligible | 90 | 1.0000 | False |
| deepseek | score_rmse | alternate_embedding_k3 | control_k3 | 1711.0000 | 0.4922 | 0.0170 | negligible | 90 | 1.0000 | False |
| deepseek | score_rmse | alternate_embedding_k3 | retrieval_k5 | 1795.0000 | 0.7451 | 0.0272 | negligible | 90 | 1.0000 | False |
| deepseek | score_rmse | exemplars_no_hidden_params | retrieval_k5 | 1613.0000 | 0.8230 | 0.0173 | negligible | 90 | 1.0000 | False |
| deepseek | score_rmse | control_k3 | retrieval_k5 | 1699.0000 | 0.8417 | 0.0083 | negligible | 90 | 0.8417 | False |
| deepseek | top1_accuracy | control_k3 | random_exemplars_k3 | 215.0000 | 0.0007 | 0.2444 | small | 90 | 0.0144 | True |
| deepseek | top1_accuracy | control_k3 | descriptions_no_scores_ranks | 236.5000 | 0.0020 | 0.2222 | small | 90 | 0.0406 | True |
| deepseek | top1_accuracy | exemplars_no_hidden_params | random_exemplars_k3 | 367.5000 | 0.0094 | 0.2000 | small | 90 | 0.1781 | False |
| deepseek | top1_accuracy | control_k3 | retrieval_k1 | 148.5000 | 0.0133 | 0.1556 | small | 90 | 0.2399 | False |
| deepseek | top1_accuracy | descriptions_no_scores_ranks | exemplars_no_hidden_params | 279.5000 | 0.0136 | -0.1778 | small | 90 | 0.2304 | False |
| deepseek | top1_accuracy | alternate_embedding_k3 | control_k3 | 144.0000 | 0.0196 | -0.1444 | negligible | 90 | 0.3128 | False |
| deepseek | top1_accuracy | control_k3 | retrieval_k5 | 108.0000 | 0.0499 | 0.1111 | negligible | 90 | 0.7479 | False |
| deepseek | top1_accuracy | exemplars_no_hidden_params | retrieval_k1 | 108.0000 | 0.0499 | 0.1111 | negligible | 90 | 0.6980 | False |
| deepseek | top1_accuracy | random_exemplars_k3 | retrieval_k5 | 399.5000 | 0.0768 | -0.1333 | negligible | 90 | 0.9990 | False |
| deepseek | top1_accuracy | alternate_embedding_k3 | exemplars_no_hidden_params | 204.0000 | 0.1172 | -0.1000 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | descriptions_no_scores_ranks | retrieval_k5 | 382.5000 | 0.1317 | -0.1111 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | alternate_embedding_k3 | random_exemplars_k3 | 414.0000 | 0.1797 | 0.1000 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | alternate_embedding_k3 | descriptions_no_scores_ranks | 221.0000 | 0.2230 | 0.0778 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | random_exemplars_k3 | retrieval_k1 | 405.0000 | 0.2278 | -0.0889 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | exemplars_no_hidden_params | retrieval_k5 | 214.5000 | 0.2888 | 0.0667 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | descriptions_no_scores_ranks | retrieval_k1 | 277.5000 | 0.3173 | -0.0667 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | control_k3 | exemplars_no_hidden_params | 125.0000 | 0.4142 | 0.0444 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | retrieval_k1 | retrieval_k5 | 262.5000 | 0.4927 | -0.0444 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | alternate_embedding_k3 | retrieval_k5 | 224.0000 | 0.5900 | -0.0333 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | descriptions_no_scores_ranks | random_exemplars_k3 | 517.0000 | 0.7681 | 0.0222 | negligible | 90 | 1.0000 | False |
| deepseek | top1_accuracy | alternate_embedding_k3 | retrieval_k1 | 182.0000 | 0.8474 | 0.0111 | negligible | 90 | 0.8474 | False |
| gemini | kendall_tau | alternate_embedding_k3 | random_exemplars_k3 | 270.5000 | 0.0001 | 0.3007 | small | 90 | 0.0015 | True |
| gemini | kendall_tau | alternate_embedding_k3 | descriptions_no_scores_ranks | 444.5000 | 0.0008 | 0.2848 | small | 90 | 0.0158 | True |
| gemini | kendall_tau | exemplars_no_hidden_params | random_exemplars_k3 | 329.0000 | 0.0016 | 0.2258 | small | 90 | 0.0297 | True |
| gemini | kendall_tau | random_exemplars_k3 | retrieval_k5 | 571.5000 | 0.0069 | -0.2242 | small | 90 | 0.1248 | False |
| gemini | kendall_tau | descriptions_no_scores_ranks | retrieval_k5 | 672.0000 | 0.0132 | -0.2022 | small | 90 | 0.2241 | False |
| gemini | kendall_tau | descriptions_no_scores_ranks | exemplars_no_hidden_params | 539.5000 | 0.0134 | -0.2058 | small | 90 | 0.2141 | False |
| gemini | kendall_tau | control_k3 | random_exemplars_k3 | 372.0000 | 0.0159 | 0.1904 | small | 90 | 0.2381 | False |
| gemini | kendall_tau | random_exemplars_k3 | retrieval_k1 | 589.0000 | 0.0245 | -0.1731 | small | 90 | 0.3432 | False |
| gemini | kendall_tau | alternate_embedding_k3 | control_k3 | 194.5000 | 0.0271 | 0.0947 | negligible | 90 | 0.3524 | False |
| gemini | kendall_tau | alternate_embedding_k3 | retrieval_k1 | 502.0000 | 0.0571 | 0.1109 | negligible | 90 | 0.6851 | False |
| gemini | kendall_tau | control_k3 | descriptions_no_scores_ranks | 572.5000 | 0.0632 | 0.1705 | small | 90 | 0.6957 | False |
| gemini | kendall_tau | descriptions_no_scores_ranks | retrieval_k1 | 709.0000 | 0.0876 | -0.1525 | small | 90 | 0.8759 | False |
| gemini | kendall_tau | alternate_embedding_k3 | exemplars_no_hidden_params | 175.5000 | 0.1507 | 0.0675 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | alternate_embedding_k3 | retrieval_k5 | 217.5000 | 0.1695 | 0.0705 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | control_k3 | exemplars_no_hidden_params | 146.5000 | 0.1860 | -0.0295 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | control_k3 | retrieval_k5 | 329.0000 | 0.3903 | -0.0284 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | exemplars_no_hidden_params | retrieval_k1 | 612.0000 | 0.4800 | 0.0483 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | descriptions_no_scores_ranks | random_exemplars_k3 | 247.0000 | 0.5450 | 0.0240 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | retrieval_k1 | retrieval_k5 | 625.0000 | 0.5585 | -0.0505 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | control_k3 | retrieval_k1 | 759.5000 | 0.7515 | 0.0169 | negligible | 90 | 1.0000 | False |
| gemini | kendall_tau | exemplars_no_hidden_params | retrieval_k5 | 256.0000 | 0.8805 | -0.0006 | negligible | 90 | 0.8805 | False |
| gemini | score_mae | descriptions_no_scores_ranks | retrieval_k5 | 258.0000 | 0.0000 | 0.5344 | large | 90 | 0.0000 | True |
| gemini | score_mae | random_exemplars_k3 | retrieval_k5 | 301.0000 | 0.0000 | 0.5172 | large | 90 | 0.0000 | True |
| gemini | score_mae | alternate_embedding_k3 | descriptions_no_scores_ranks | 307.0000 | 0.0000 | -0.5167 | large | 90 | 0.0000 | True |
| gemini | score_mae | control_k3 | descriptions_no_scores_ranks | 356.0000 | 0.0000 | -0.5207 | large | 90 | 0.0000 | True |
| gemini | score_mae | alternate_embedding_k3 | random_exemplars_k3 | 360.0000 | 0.0000 | -0.5022 | large | 90 | 0.0000 | True |
| gemini | score_mae | control_k3 | random_exemplars_k3 | 369.0000 | 0.0000 | -0.5086 | large | 90 | 0.0000 | True |
| gemini | score_mae | descriptions_no_scores_ranks | exemplars_no_hidden_params | 492.0000 | 0.0000 | 0.4698 | medium | 90 | 0.0000 | True |
| gemini | score_mae | exemplars_no_hidden_params | random_exemplars_k3 | 531.0000 | 0.0000 | -0.4547 | medium | 90 | 0.0000 | True |
| gemini | score_mae | descriptions_no_scores_ranks | retrieval_k1 | 828.0000 | 0.0000 | 0.3317 | medium | 90 | 0.0000 | True |
| gemini | score_mae | random_exemplars_k3 | retrieval_k1 | 868.0000 | 0.0000 | 0.3047 | small | 90 | 0.0000 | True |
| gemini | score_mae | retrieval_k1 | retrieval_k5 | 971.0000 | 0.0000 | 0.1981 | small | 90 | 0.0004 | True |
| gemini | score_mae | control_k3 | retrieval_k1 | 1011.0000 | 0.0002 | -0.1891 | small | 90 | 0.0021 | True |
| gemini | score_mae | alternate_embedding_k3 | retrieval_k1 | 1044.5000 | 0.0002 | -0.1891 | small | 90 | 0.0021 | True |
| gemini | score_mae | exemplars_no_hidden_params | retrieval_k1 | 1208.5000 | 0.0101 | -0.1328 | negligible | 90 | 0.0811 | False |
| gemini | score_mae | exemplars_no_hidden_params | retrieval_k5 | 1194.5000 | 0.0848 | 0.0643 | negligible | 90 | 0.5937 | False |
| gemini | score_mae | control_k3 | exemplars_no_hidden_params | 714.5000 | 0.0970 | -0.0485 | negligible | 90 | 0.5823 | False |
| gemini | score_mae | alternate_embedding_k3 | exemplars_no_hidden_params | 1347.5000 | 0.3364 | -0.0574 | negligible | 90 | 1.0000 | False |
| gemini | score_mae | descriptions_no_scores_ranks | random_exemplars_k3 | 1723.0000 | 0.4189 | 0.0317 | negligible | 90 | 1.0000 | False |
| gemini | score_mae | control_k3 | retrieval_k5 | 1407.5000 | 0.7738 | 0.0212 | negligible | 90 | 1.0000 | False |
| gemini | score_mae | alternate_embedding_k3 | retrieval_k5 | 1608.0000 | 0.9541 | 0.0131 | negligible | 90 | 1.0000 | False |
| gemini | score_mae | alternate_embedding_k3 | control_k3 | 1493.5000 | 0.9676 | -0.0158 | negligible | 90 | 0.9676 | False |
| gemini | score_rmse | descriptions_no_scores_ranks | retrieval_k5 | 221.0000 | 0.0000 | 0.5417 | large | 90 | 0.0000 | True |
| gemini | score_rmse | random_exemplars_k3 | retrieval_k5 | 256.0000 | 0.0000 | 0.5311 | large | 90 | 0.0000 | True |
| gemini | score_rmse | alternate_embedding_k3 | descriptions_no_scores_ranks | 266.0000 | 0.0000 | -0.5274 | large | 90 | 0.0000 | True |
| gemini | score_rmse | alternate_embedding_k3 | random_exemplars_k3 | 312.0000 | 0.0000 | -0.5156 | large | 90 | 0.0000 | True |
| gemini | score_rmse | control_k3 | descriptions_no_scores_ranks | 368.0000 | 0.0000 | -0.5185 | large | 90 | 0.0000 | True |
| gemini | score_rmse | control_k3 | random_exemplars_k3 | 382.0000 | 0.0000 | -0.5077 | large | 90 | 0.0000 | True |
| gemini | score_rmse | descriptions_no_scores_ranks | exemplars_no_hidden_params | 485.0000 | 0.0000 | 0.4721 | medium | 90 | 0.0000 | True |
| gemini | score_rmse | exemplars_no_hidden_params | random_exemplars_k3 | 541.0000 | 0.0000 | -0.4607 | medium | 90 | 0.0000 | True |
| gemini | score_rmse | descriptions_no_scores_ranks | retrieval_k1 | 753.0000 | 0.0000 | 0.3304 | medium | 90 | 0.0000 | True |
| gemini | score_rmse | random_exemplars_k3 | retrieval_k1 | 841.0000 | 0.0000 | 0.3123 | small | 90 | 0.0000 | True |
| gemini | score_rmse | retrieval_k1 | retrieval_k5 | 901.0000 | 0.0000 | 0.1970 | small | 90 | 0.0001 | True |
| gemini | score_rmse | alternate_embedding_k3 | retrieval_k1 | 1059.0000 | 0.0002 | -0.1940 | small | 90 | 0.0018 | True |
| gemini | score_rmse | control_k3 | retrieval_k1 | 1013.0000 | 0.0002 | -0.1774 | small | 90 | 0.0020 | True |
| gemini | score_rmse | exemplars_no_hidden_params | retrieval_k1 | 1215.0000 | 0.0110 | -0.1317 | negligible | 90 | 0.0882 | False |
| gemini | score_rmse | exemplars_no_hidden_params | retrieval_k5 | 1200.0000 | 0.0633 | 0.0683 | negligible | 90 | 0.4431 | False |
| gemini | score_rmse | control_k3 | exemplars_no_hidden_params | 738.0000 | 0.0945 | -0.0326 | negligible | 90 | 0.5670 | False |
| gemini | score_rmse | descriptions_no_scores_ranks | random_exemplars_k3 | 1712.0000 | 0.3060 | 0.0358 | negligible | 90 | 1.0000 | False |
| gemini | score_rmse | alternate_embedding_k3 | exemplars_no_hidden_params | 1432.0000 | 0.3672 | -0.0586 | negligible | 90 | 1.0000 | False |
| gemini | score_rmse | control_k3 | retrieval_k5 | 1389.0000 | 0.5679 | 0.0342 | negligible | 90 | 1.0000 | False |
| gemini | score_rmse | alternate_embedding_k3 | retrieval_k5 | 1591.0000 | 0.8894 | 0.0060 | negligible | 90 | 1.0000 | False |
| gemini | score_rmse | alternate_embedding_k3 | control_k3 | 1530.0000 | 0.9583 | -0.0283 | negligible | 90 | 0.9583 | False |
| gemini | top1_accuracy | alternate_embedding_k3 | descriptions_no_scores_ranks | 184.0000 | 0.0000 | 0.3222 | small | 90 | 0.0003 | True |
| gemini | top1_accuracy | alternate_embedding_k3 | random_exemplars_k3 | 143.5000 | 0.0000 | 0.2889 | small | 90 | 0.0008 | True |
| gemini | top1_accuracy | descriptions_no_scores_ranks | retrieval_k5 | 215.0000 | 0.0007 | -0.2444 | small | 90 | 0.0131 | True |
| gemini | top1_accuracy | alternate_embedding_k3 | control_k3 | 19.0000 | 0.0010 | 0.1556 | small | 90 | 0.0174 | True |
| gemini | top1_accuracy | descriptions_no_scores_ranks | exemplars_no_hidden_params | 200.0000 | 0.0023 | -0.2111 | small | 90 | 0.0399 | True |
| gemini | top1_accuracy | random_exemplars_k3 | retrieval_k5 | 231.0000 | 0.0030 | -0.2111 | small | 90 | 0.0481 | True |
| gemini | top1_accuracy | exemplars_no_hidden_params | random_exemplars_k3 | 214.5000 | 0.0094 | 0.1778 | small | 90 | 0.1417 | False |
| gemini | top1_accuracy | descriptions_no_scores_ranks | retrieval_k1 | 214.5000 | 0.0094 | -0.1778 | small | 90 | 0.1322 | False |
| gemini | top1_accuracy | alternate_embedding_k3 | retrieval_k1 | 98.0000 | 0.0124 | 0.1444 | negligible | 90 | 0.1606 | False |
| gemini | top1_accuracy | alternate_embedding_k3 | exemplars_no_hidden_params | 25.5000 | 0.0124 | 0.1111 | negligible | 90 | 0.1490 | False |
| gemini | top1_accuracy | control_k3 | descriptions_no_scores_ranks | 240.0000 | 0.0163 | 0.1667 | small | 90 | 0.1794 | False |
| gemini | top1_accuracy | random_exemplars_k3 | retrieval_k1 | 198.0000 | 0.0280 | -0.1444 | negligible | 90 | 0.2799 | False |
| gemini | top1_accuracy | control_k3 | random_exemplars_k3 | 253.5000 | 0.0516 | 0.1333 | negligible | 90 | 0.4642 | False |
| gemini | top1_accuracy | control_k3 | retrieval_k5 | 32.0000 | 0.0707 | -0.0778 | negligible | 90 | 0.5656 | False |
| gemini | top1_accuracy | alternate_embedding_k3 | retrieval_k5 | 77.0000 | 0.1266 | 0.0778 | negligible | 90 | 0.8864 | False |
| gemini | top1_accuracy | control_k3 | exemplars_no_hidden_params | 9.0000 | 0.1573 | -0.0444 | negligible | 90 | 0.9438 | False |
| gemini | top1_accuracy | retrieval_k1 | retrieval_k5 | 186.0000 | 0.2733 | -0.0667 | negligible | 90 | 1.0000 | False |
| gemini | top1_accuracy | exemplars_no_hidden_params | retrieval_k5 | 15.0000 | 0.3173 | -0.0333 | negligible | 90 | 1.0000 | False |
| gemini | top1_accuracy | descriptions_no_scores_ranks | random_exemplars_k3 | 48.0000 | 0.4386 | -0.0333 | negligible | 90 | 1.0000 | False |
| gemini | top1_accuracy | exemplars_no_hidden_params | retrieval_k1 | 168.0000 | 0.5637 | 0.0333 | negligible | 90 | 1.0000 | False |
| gemini | top1_accuracy | control_k3 | retrieval_k1 | 156.0000 | 0.8415 | -0.0111 | negligible | 90 | 0.8415 | False |
| gptoss | score_mae | random_exemplars_k3 | retrieval_k5 | 658.0000 | 0.0000 | 0.3464 | medium | 90 | 0.0000 | True |
| gptoss | score_mae | descriptions_no_scores_ranks | retrieval_k5 | 719.0000 | 0.0000 | 0.3502 | medium | 90 | 0.0000 | True |
| gptoss | score_mae | control_k3 | random_exemplars_k3 | 744.5000 | 0.0000 | -0.3262 | small | 90 | 0.0000 | True |
| gptoss | score_mae | control_k3 | descriptions_no_scores_ranks | 754.0000 | 0.0000 | -0.3264 | small | 90 | 0.0000 | True |
| gptoss | score_mae | exemplars_no_hidden_params | random_exemplars_k3 | 821.0000 | 0.0000 | -0.3217 | small | 90 | 0.0000 | True |
| gptoss | score_mae | descriptions_no_scores_ranks | exemplars_no_hidden_params | 826.0000 | 0.0000 | 0.3173 | small | 90 | 0.0000 | True |
| gptoss | score_mae | alternate_embedding_k3 | random_exemplars_k3 | 952.0000 | 0.0000 | -0.3021 | small | 90 | 0.0002 | True |
| gptoss | score_mae | random_exemplars_k3 | retrieval_k1 | 966.0000 | 0.0000 | 0.2733 | small | 90 | 0.0002 | True |
| gptoss | score_mae | alternate_embedding_k3 | descriptions_no_scores_ranks | 1103.0000 | 0.0001 | -0.2821 | small | 90 | 0.0019 | True |
| gptoss | score_mae | descriptions_no_scores_ranks | retrieval_k1 | 1166.0000 | 0.0004 | 0.2527 | small | 90 | 0.0047 | True |
| gptoss | score_mae | retrieval_k1 | retrieval_k5 | 1540.0000 | 0.0411 | 0.1152 | negligible | 90 | 0.4526 | False |
| gptoss | score_mae | control_k3 | retrieval_k1 | 1615.5000 | 0.1541 | -0.0885 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | exemplars_no_hidden_params | retrieval_k5 | 1630.0000 | 0.1723 | 0.0451 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | exemplars_no_hidden_params | retrieval_k1 | 1714.0000 | 0.2379 | -0.0758 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | alternate_embedding_k3 | retrieval_k5 | 1754.0000 | 0.3093 | 0.0680 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | alternate_embedding_k3 | exemplars_no_hidden_params | 1759.0000 | 0.4077 | 0.0247 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | alternate_embedding_k3 | control_k3 | 1688.0000 | 0.4320 | 0.0473 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | control_k3 | retrieval_k5 | 1733.0000 | 0.4436 | 0.0219 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | alternate_embedding_k3 | retrieval_k1 | 1861.0000 | 0.4530 | -0.0548 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | descriptions_no_scores_ranks | random_exemplars_k3 | 1904.5000 | 0.6885 | -0.0127 | negligible | 90 | 1.0000 | False |
| gptoss | score_mae | control_k3 | exemplars_no_hidden_params | 1856.0000 | 0.8061 | -0.0160 | negligible | 90 | 0.8061 | False |
| gptoss | score_rmse | random_exemplars_k3 | retrieval_k5 | 715.0000 | 0.0000 | 0.3422 | medium | 90 | 0.0000 | True |
| gptoss | score_rmse | control_k3 | random_exemplars_k3 | 769.0000 | 0.0000 | -0.3183 | small | 90 | 0.0000 | True |
| gptoss | score_rmse | descriptions_no_scores_ranks | retrieval_k5 | 791.0000 | 0.0000 | 0.3351 | medium | 90 | 0.0000 | True |
| gptoss | score_rmse | exemplars_no_hidden_params | random_exemplars_k3 | 814.0000 | 0.0000 | -0.3106 | small | 90 | 0.0000 | True |
| gptoss | score_rmse | descriptions_no_scores_ranks | exemplars_no_hidden_params | 842.0000 | 0.0000 | 0.3007 | small | 90 | 0.0000 | True |
| gptoss | score_rmse | control_k3 | descriptions_no_scores_ranks | 859.0000 | 0.0000 | -0.2993 | small | 90 | 0.0000 | True |
| gptoss | score_rmse | alternate_embedding_k3 | random_exemplars_k3 | 870.0000 | 0.0000 | -0.3158 | small | 90 | 0.0000 | True |
| gptoss | score_rmse | random_exemplars_k3 | retrieval_k1 | 1018.0000 | 0.0000 | 0.2509 | small | 90 | 0.0005 | True |
| gptoss | score_rmse | alternate_embedding_k3 | descriptions_no_scores_ranks | 1039.0000 | 0.0000 | -0.2894 | small | 90 | 0.0006 | True |
| gptoss | score_rmse | descriptions_no_scores_ranks | retrieval_k1 | 1212.0000 | 0.0008 | 0.2267 | small | 90 | 0.0093 | True |
| gptoss | score_rmse | retrieval_k1 | retrieval_k5 | 1534.0000 | 0.0388 | 0.1138 | negligible | 90 | 0.4269 | False |
| gptoss | score_rmse | exemplars_no_hidden_params | retrieval_k5 | 1618.0000 | 0.1572 | 0.0468 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | control_k3 | retrieval_k1 | 1710.0000 | 0.1745 | -0.0881 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | alternate_embedding_k3 | retrieval_k1 | 1721.0000 | 0.1889 | -0.0746 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | control_k3 | retrieval_k5 | 1613.0000 | 0.2027 | 0.0284 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | exemplars_no_hidden_params | retrieval_k1 | 1734.0000 | 0.2072 | -0.0765 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | alternate_embedding_k3 | retrieval_k5 | 1819.0000 | 0.4528 | 0.0530 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | descriptions_no_scores_ranks | random_exemplars_k3 | 1926.0000 | 0.6249 | -0.0175 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | alternate_embedding_k3 | exemplars_no_hidden_params | 1874.0000 | 0.7267 | 0.0083 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | alternate_embedding_k3 | control_k3 | 1820.0000 | 0.8279 | 0.0216 | negligible | 90 | 1.0000 | False |
| gptoss | score_rmse | control_k3 | exemplars_no_hidden_params | 1912.0000 | 0.9932 | -0.0098 | negligible | 90 | 0.9932 | False |
| qwen | score_mae | descriptions_no_scores_ranks | retrieval_k5 | 555.0000 | 0.0000 | 0.4072 | medium | 90 | 0.0000 | True |
| qwen | score_mae | descriptions_no_scores_ranks | retrieval_k1 | 652.0000 | 0.0000 | 0.3616 | medium | 90 | 0.0000 | True |
| qwen | score_mae | random_exemplars_k3 | retrieval_k5 | 746.0000 | 0.0000 | 0.3691 | medium | 90 | 0.0000 | True |
| qwen | score_mae | descriptions_no_scores_ranks | exemplars_no_hidden_params | 790.5000 | 0.0000 | 0.3338 | medium | 90 | 0.0000 | True |
| qwen | score_mae | control_k3 | descriptions_no_scores_ranks | 811.0000 | 0.0000 | -0.3125 | small | 90 | 0.0000 | True |
| qwen | score_mae | alternate_embedding_k3 | descriptions_no_scores_ranks | 838.0000 | 0.0000 | -0.2960 | small | 90 | 0.0000 | True |
| qwen | score_mae | random_exemplars_k3 | retrieval_k1 | 930.0000 | 0.0000 | 0.3222 | small | 90 | 0.0001 | True |
| qwen | score_mae | exemplars_no_hidden_params | random_exemplars_k3 | 1060.0000 | 0.0001 | -0.2910 | small | 90 | 0.0010 | True |
| qwen | score_mae | alternate_embedding_k3 | random_exemplars_k3 | 1069.0000 | 0.0001 | -0.2564 | small | 90 | 0.0011 | True |
| qwen | score_mae | control_k3 | random_exemplars_k3 | 1123.0000 | 0.0002 | -0.2695 | small | 90 | 0.0024 | True |
| qwen | score_mae | control_k3 | retrieval_k5 | 1292.5000 | 0.0085 | 0.0867 | negligible | 90 | 0.0938 | False |
| qwen | score_mae | retrieval_k1 | retrieval_k5 | 1472.0000 | 0.0300 | 0.0585 | negligible | 90 | 0.2997 | False |
| qwen | score_mae | alternate_embedding_k3 | retrieval_k5 | 1556.0000 | 0.0480 | 0.1131 | negligible | 90 | 0.4317 | False |
| qwen | score_mae | exemplars_no_hidden_params | retrieval_k5 | 1651.5000 | 0.2022 | 0.0747 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | descriptions_no_scores_ranks | random_exemplars_k3 | 1695.0000 | 0.2084 | 0.0506 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | alternate_embedding_k3 | retrieval_k1 | 1920.5000 | 0.6093 | 0.0494 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | control_k3 | retrieval_k1 | 1898.0000 | 0.6690 | 0.0267 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | control_k3 | exemplars_no_hidden_params | 1869.5000 | 0.7127 | 0.0148 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | alternate_embedding_k3 | exemplars_no_hidden_params | 1910.0000 | 0.8417 | 0.0321 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | alternate_embedding_k3 | control_k3 | 2031.5000 | 0.9487 | 0.0212 | negligible | 90 | 1.0000 | False |
| qwen | score_mae | exemplars_no_hidden_params | retrieval_k1 | 2040.0000 | 0.9759 | 0.0177 | negligible | 90 | 0.9759 | False |
| qwen | score_rmse | descriptions_no_scores_ranks | retrieval_k5 | 550.0000 | 0.0000 | 0.4042 | medium | 90 | 0.0000 | True |
| qwen | score_rmse | descriptions_no_scores_ranks | retrieval_k1 | 596.0000 | 0.0000 | 0.3457 | medium | 90 | 0.0000 | True |
| qwen | score_rmse | random_exemplars_k3 | retrieval_k5 | 667.0000 | 0.0000 | 0.3788 | medium | 90 | 0.0000 | True |
| qwen | score_rmse | descriptions_no_scores_ranks | exemplars_no_hidden_params | 756.0000 | 0.0000 | 0.3205 | small | 90 | 0.0000 | True |
| qwen | score_rmse | alternate_embedding_k3 | descriptions_no_scores_ranks | 804.0000 | 0.0000 | -0.3054 | small | 90 | 0.0000 | True |
| qwen | score_rmse | control_k3 | descriptions_no_scores_ranks | 935.0000 | 0.0000 | -0.2798 | small | 90 | 0.0001 | True |
| qwen | score_rmse | random_exemplars_k3 | retrieval_k1 | 961.0000 | 0.0000 | 0.3114 | small | 90 | 0.0002 | True |
| qwen | score_rmse | alternate_embedding_k3 | random_exemplars_k3 | 986.0000 | 0.0000 | -0.2674 | small | 90 | 0.0003 | True |
| qwen | score_rmse | exemplars_no_hidden_params | random_exemplars_k3 | 1038.0000 | 0.0000 | -0.2832 | small | 90 | 0.0006 | True |
| qwen | score_rmse | control_k3 | random_exemplars_k3 | 1197.0000 | 0.0006 | -0.2437 | small | 90 | 0.0075 | True |
| qwen | score_rmse | control_k3 | retrieval_k5 | 1193.0000 | 0.0023 | 0.1135 | negligible | 90 | 0.0250 | True |
| qwen | score_rmse | retrieval_k1 | retrieval_k5 | 1420.0000 | 0.0116 | 0.0723 | negligible | 90 | 0.1157 | False |
| qwen | score_rmse | alternate_embedding_k3 | retrieval_k5 | 1601.0000 | 0.0724 | 0.1062 | negligible | 90 | 0.6516 | False |
| qwen | score_rmse | exemplars_no_hidden_params | retrieval_k5 | 1605.0000 | 0.1039 | 0.0783 | negligible | 90 | 0.8311 | False |
| qwen | score_rmse | descriptions_no_scores_ranks | random_exemplars_k3 | 1745.0000 | 0.2235 | 0.0427 | negligible | 90 | 1.0000 | False |
| qwen | score_rmse | control_k3 | exemplars_no_hidden_params | 1769.0000 | 0.3394 | 0.0399 | negligible | 90 | 1.0000 | False |
| qwen | score_rmse | control_k3 | retrieval_k1 | 1919.0000 | 0.6051 | 0.0417 | negligible | 90 | 1.0000 | False |
| qwen | score_rmse | alternate_embedding_k3 | control_k3 | 1958.0000 | 0.7188 | -0.0180 | negligible | 90 | 1.0000 | False |
| qwen | score_rmse | exemplars_no_hidden_params | retrieval_k1 | 1967.0000 | 0.7460 | 0.0084 | negligible | 90 | 1.0000 | False |
| qwen | score_rmse | alternate_embedding_k3 | exemplars_no_hidden_params | 2020.0000 | 0.9119 | 0.0143 | negligible | 90 | 1.0000 | False |
| qwen | score_rmse | alternate_embedding_k3 | retrieval_k1 | 2035.0000 | 0.9599 | 0.0332 | negligible | 90 | 0.9599 | False |

## Bootstrap 95% Confidence Intervals (per model)

Percentile-method 95% CIs for each configuration's mean metric value, computed within each model rather than pooled across models.

| model_key | ablation_id | ablation_label | point_estimate | ci_lower | ci_upper | metric |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.3463 | 0.2185 | 0.4753 | kendall_tau |
| deepseek | control_k3 | Control k=3 standard | 0.4887 | 0.3667 | 0.6082 | kendall_tau |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.0733 | -0.0595 | 0.2043 | kendall_tau |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.3911 | 0.2555 | 0.5208 | kendall_tau |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | 0.0632 | -0.0765 | 0.2043 | kendall_tau |
| deepseek | retrieval_k1 | Retrieval k=1 | 0.1822 | 0.0372 | 0.3181 | kendall_tau |
| deepseek | retrieval_k5 | Retrieval k=5 | 0.3421 | 0.2022 | 0.4745 | kendall_tau |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.0876 | 0.0752 | 0.1007 | score_mae |
| deepseek | control_k3 | Control k=3 standard | 0.0884 | 0.0741 | 0.1044 | score_mae |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1312 | 0.1164 | 0.1465 | score_mae |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.0874 | 0.0740 | 0.1022 | score_mae |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | 0.1267 | 0.1125 | 0.1414 | score_mae |
| deepseek | retrieval_k1 | Retrieval k=1 | 0.0981 | 0.0850 | 0.1116 | score_mae |
| deepseek | retrieval_k5 | Retrieval k=5 | 0.0842 | 0.0719 | 0.0973 | score_mae |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.4889 | 0.3889 | 0.5889 | top1_accuracy |
| deepseek | control_k3 | Control k=3 standard | 0.6333 | 0.5333 | 0.7333 | top1_accuracy |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.4111 | 0.3111 | 0.5111 | top1_accuracy |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.5889 | 0.4889 | 0.6889 | top1_accuracy |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | 0.3889 | 0.2889 | 0.4889 | top1_accuracy |
| deepseek | retrieval_k1 | Retrieval k=1 | 0.4778 | 0.3778 | 0.5778 | top1_accuracy |
| deepseek | retrieval_k5 | Retrieval k=5 | 0.5222 | 0.4222 | 0.6222 | top1_accuracy |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.5174 | 0.3824 | 0.6450 | kendall_tau |
| gemini | control_k3 | Control k=3 standard | 0.3868 | 0.2400 | 0.5296 | kendall_tau |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.2037 | 0.0687 | 0.3367 | kendall_tau |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.4367 | 0.2992 | 0.5639 | kendall_tau |
| gemini | random_exemplars_k3 | Random exemplars k=3 | 0.1774 | 0.0433 | 0.3137 | kendall_tau |
| gemini | retrieval_k1 | Retrieval k=1 | 0.3774 | 0.2379 | 0.5133 | kendall_tau |
| gemini | retrieval_k5 | Retrieval k=5 | 0.4313 | 0.2991 | 0.5609 | kendall_tau |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.0711 | 0.0593 | 0.0842 | score_mae |
| gemini | control_k3 | Control k=3 standard | 0.0705 | 0.0594 | 0.0827 | score_mae |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1427 | 0.1246 | 0.1613 | score_mae |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.0779 | 0.0648 | 0.0923 | score_mae |
| gemini | random_exemplars_k3 | Random exemplars k=3 | 0.1391 | 0.1208 | 0.1584 | score_mae |
| gemini | retrieval_k1 | Retrieval k=1 | 0.0968 | 0.0812 | 0.1143 | score_mae |
| gemini | retrieval_k5 | Retrieval k=5 | 0.0691 | 0.0577 | 0.0815 | score_mae |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.7222 | 0.6333 | 0.8111 | top1_accuracy |
| gemini | control_k3 | Control k=3 standard | 0.5667 | 0.4667 | 0.6667 | top1_accuracy |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.4000 | 0.3000 | 0.5000 | top1_accuracy |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.6111 | 0.5111 | 0.7111 | top1_accuracy |
| gemini | random_exemplars_k3 | Random exemplars k=3 | 0.4333 | 0.3333 | 0.5333 | top1_accuracy |
| gemini | retrieval_k1 | Retrieval k=1 | 0.5778 | 0.4778 | 0.6778 | top1_accuracy |
| gemini | retrieval_k5 | Retrieval k=5 | 0.6444 | 0.5444 | 0.7444 | top1_accuracy |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.2268 | 0.0943 | 0.3602 | kendall_tau |
| gptoss | control_k3 | Control k=3 standard | 0.1872 | 0.0444 | 0.3333 | kendall_tau |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.0609 | -0.0754 | 0.1952 | kendall_tau |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.1754 | 0.0272 | 0.3198 | kendall_tau |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | 0.0222 | -0.1074 | 0.1494 | kendall_tau |
| gptoss | retrieval_k1 | Retrieval k=1 | 0.2367 | 0.0976 | 0.3730 | kendall_tau |
| gptoss | retrieval_k5 | Retrieval k=5 | 0.1124 | -0.0337 | 0.2639 | kendall_tau |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.1127 | 0.0961 | 0.1302 | score_mae |
| gptoss | control_k3 | Control k=3 standard | 0.1045 | 0.0899 | 0.1203 | score_mae |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1577 | 0.1383 | 0.1773 | score_mae |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.1058 | 0.0913 | 0.1212 | score_mae |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | 0.1634 | 0.1418 | 0.1852 | score_mae |
| gptoss | retrieval_k1 | Retrieval k=1 | 0.1182 | 0.1013 | 0.1355 | score_mae |
| gptoss | retrieval_k5 | Retrieval k=5 | 0.1016 | 0.0870 | 0.1170 | score_mae |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.4444 | 0.3444 | 0.5444 | top1_accuracy |
| gptoss | control_k3 | Control k=3 standard | 0.4444 | 0.3444 | 0.5444 | top1_accuracy |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.3333 | 0.2333 | 0.4333 | top1_accuracy |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.4444 | 0.3444 | 0.5444 | top1_accuracy |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | 0.3444 | 0.2444 | 0.4444 | top1_accuracy |
| gptoss | retrieval_k1 | Retrieval k=1 | 0.4667 | 0.3667 | 0.5667 | top1_accuracy |
| gptoss | retrieval_k5 | Retrieval k=5 | 0.3889 | 0.2889 | 0.4889 | top1_accuracy |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.0011 | -0.1725 | 0.1753 | kendall_tau |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.1009 | 0.0878 | 0.1153 | score_mae |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.4444 | 0.3444 | 0.5444 | top1_accuracy |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.1651 | 0.0148 | 0.3171 | kendall_tau |
| qwen | control_k3 | Control k=3 standard | 0.1535 | 0.0098 | 0.2959 | kendall_tau |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.0711 | -0.0690 | 0.2128 | kendall_tau |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.2730 | 0.1369 | 0.4067 | kendall_tau |
| qwen | random_exemplars_k3 | Random exemplars k=3 | 0.2756 | 0.1491 | 0.3981 | kendall_tau |
| qwen | retrieval_k1 | Retrieval k=1 | 0.3056 | 0.1644 | 0.4434 | kendall_tau |
| qwen | retrieval_k5 | Retrieval k=5 | 0.2343 | 0.1027 | 0.3617 | kendall_tau |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.1039 | 0.0894 | 0.1197 | score_mae |
| qwen | control_k3 | Control k=3 standard | 0.1019 | 0.0868 | 0.1171 | score_mae |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1511 | 0.1311 | 0.1722 | score_mae |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.0988 | 0.0851 | 0.1132 | score_mae |
| qwen | random_exemplars_k3 | Random exemplars k=3 | 0.1407 | 0.1220 | 0.1606 | score_mae |
| qwen | retrieval_k1 | Retrieval k=1 | 0.0968 | 0.0838 | 0.1109 | score_mae |
| qwen | retrieval_k5 | Retrieval k=5 | 0.0880 | 0.0761 | 0.1003 | score_mae |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.4778 | 0.3778 | 0.5778 | top1_accuracy |
| qwen | control_k3 | Control k=3 standard | 0.4333 | 0.3333 | 0.5333 | top1_accuracy |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.4222 | 0.3222 | 0.5222 | top1_accuracy |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | 0.4667 | 0.3667 | 0.5667 | top1_accuracy |
| qwen | random_exemplars_k3 | Random exemplars k=3 | 0.5778 | 0.4778 | 0.6778 | top1_accuracy |
| qwen | retrieval_k1 | Retrieval k=1 | 0.5222 | 0.4222 | 0.6222 | top1_accuracy |
| qwen | retrieval_k5 | Retrieval k=5 | 0.4889 | 0.3889 | 0.5889 | top1_accuracy |

