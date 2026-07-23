# RAG Ablation Study

## Overview

- Sample size: 35
- Random seed: 13
- Scenarios evaluated: 35
- Result rows: 3045
- Output plots: `C:\Users\Ahaan\LLM-MCDA Paper\rag_ablation_top1_accuracy.png`, `C:\Users\Ahaan\LLM-MCDA Paper\rag_ablation_score_mae.png`, `C:\Users\Ahaan\LLM-MCDA Paper\rag_ablation_retrieval_distance.png`

## Ablation Configurations

| ablation_id | label | k | retrieval | embedding_model | include_hidden_params | include_scores | include_ranks | llm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_k3 | Control k=3 standard | 3 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | True |
| random_exemplars_k3 | Random exemplars k=3 | 3 | random | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | True |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 3 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | False | False | True |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 3 | similarity | sentence-transformers/all-MiniLM-L6-v2 | False | True | True | True |
| retrieval_k1 | Retrieval k=1 | 1 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | True |
| retrieval_k5 | Retrieval k=5 | 5 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | True |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 3 | similarity | sentence-transformers/paraphrase-MiniLM-L3-v2 | True | True | True | True |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 3 | similarity | sentence-transformers/all-MiniLM-L6-v2 | True | True | True | False |

## Overall Summary

| model_key | ablation_id | ablation_label | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy | mean_retrieval_distance | retrieval_count | api_calls | successful_calls | failed_calls | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 35 | 0.0722 | 0.0837 | 0.4052 | 0.4181 | 0.6571 | 0.8857 | 1.1626 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| deepseek | control_k3 | Control k=3 standard | 35 | 0.0827 | 0.0900 | 0.3481 | 0.3753 | 0.6286 | 0.8000 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | 35 | 0.1401 | 0.1543 | 0.0809 | 0.1127 | 0.3714 | 0.7714 | 0.0675 | 105.0000 | 105.0000 | 104.0000 | 1.0000 | 0.9905 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | 35 | 0.0742 | 0.0817 | 0.4588 | 0.4989 | 0.6286 | 0.8286 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | 35 | 0.1466 | 0.1592 | 0.2279 | 0.2303 | 0.5143 | 0.6571 | 0.4370 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| deepseek | retrieval_k1 | Retrieval k=1 | 35 | 0.0869 | 0.0994 | 0.4614 | 0.4676 | 0.6286 | 0.8286 | 0.0503 | 35.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| deepseek | retrieval_k5 | Retrieval k=5 | 35 | 0.0699 | 0.0767 | 0.5695 | 0.6133 | 0.5714 | 0.8857 | 0.0788 | 175.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 35 | 0.0612 | 0.0716 | 0.4467 | 0.4638 | 0.6571 | 0.8571 | 1.1626 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gemini | control_k3 | Control k=3 standard | 35 | 0.0711 | 0.0826 | 0.3419 | 0.3495 | 0.6286 | 0.7714 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | 35 | 0.1427 | 0.1626 | 0.1048 | 0.1000 | 0.4286 | 0.7429 | 0.0675 | 105.0000 | 105.0000 | 104.0000 | 1.0000 | 0.9905 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | 35 | 0.0725 | 0.0840 | 0.3090 | 0.3105 | 0.6286 | 0.7429 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | 35 | 0.1512 | 0.1688 | -0.0233 | -0.0390 | 0.3143 | 0.6286 | 0.4268 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gemini | retrieval_k1 | Retrieval k=1 | 35 | 0.0831 | 0.0962 | 0.3529 | 0.3382 | 0.5143 | 0.7429 | 0.0503 | 35.0000 | 105.0000 | 101.0000 | 4.0000 | 0.9619 |
| gemini | retrieval_k5 | Retrieval k=5 | 35 | 0.0605 | 0.0687 | 0.4805 | 0.5247 | 0.6857 | 0.8857 | 0.0788 | 175.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 35 | 0.0933 | 0.1085 | 0.2190 | 0.2143 | 0.4857 | 0.7143 | 1.1626 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | control_k3 | Control k=3 standard | 35 | 0.0870 | 0.1004 | 0.2000 | 0.2429 | 0.4857 | 0.7143 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | 35 | 0.1430 | 0.1638 | -0.0651 | -0.0868 | 0.3143 | 0.6286 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | 35 | 0.0934 | 0.1081 | 0.2000 | 0.2286 | 0.4571 | 0.7429 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | 35 | 0.1732 | 0.1931 | -0.0338 | -0.0467 | 0.2857 | 0.7143 | 0.4337 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | retrieval_k1 | Retrieval k=1 | 35 | 0.0987 | 0.1121 | 0.2676 | 0.2934 | 0.5714 | 0.7714 | 0.0503 | 35.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| gptoss | retrieval_k5 | Retrieval k=5 | 35 | 0.0923 | 0.1050 | 0.3281 | 0.3390 | 0.5143 | 0.8286 | 0.0788 | 175.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 35 | 0.0960 | 0.1074 | -0.0389 | -0.0412 | 0.4571 | 0.6857 | 0.0675 | 105.0000 | 0.0000 | 0.0000 | 0.0000 | N/A |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 35 | 0.0959 | 0.1112 | 0.2289 | 0.2676 | 0.4571 | 0.6857 | 1.1626 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| qwen | control_k3 | Control k=3 standard | 35 | 0.1029 | 0.1195 | 0.3773 | 0.3818 | 0.5714 | 0.7714 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | 35 | 0.1414 | 0.1567 | 0.3156 | 0.3282 | 0.5714 | 0.8286 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | 35 | 0.1014 | 0.1212 | 0.2323 | 0.2273 | 0.4571 | 0.8286 | 0.0675 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | 35 | 0.1363 | 0.1528 | 0.0818 | 0.0990 | 0.5143 | 0.6571 | 0.4364 | 105.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| qwen | retrieval_k1 | Retrieval k=1 | 35 | 0.1023 | 0.1168 | 0.3725 | 0.4265 | 0.6286 | 0.8571 | 0.0503 | 35.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |
| qwen | retrieval_k5 | Retrieval k=5 | 35 | 0.0916 | 0.1069 | 0.1667 | 0.1618 | 0.4286 | 0.6857 | 0.0788 | 175.0000 | 105.0000 | 105.0000 | 0.0000 | 1.0000 |

## Summary by Decision Type

| model_key | ablation_id | ablation_label | decision_type | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 12 | 0.0725 | 0.0910 | 0.6264 | 0.6778 | 0.8333 | 1.0000 |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 12 | 0.1022 | 0.1124 | 0.1389 | 0.1250 | 0.4167 | 0.9167 |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 11 | 0.0393 | 0.0445 | 0.4545 | 0.4545 | 0.7273 | 0.7273 |
| deepseek | control_k3 | Control k=3 standard | Appliance | 12 | 0.0902 | 0.1005 | 0.5000 | 0.5417 | 0.8333 | 0.8333 |
| deepseek | control_k3 | Control k=3 standard | HVAC | 12 | 0.1179 | 0.1273 | -0.0680 | -0.0722 | 0.3333 | 0.6667 |
| deepseek | control_k3 | Control k=3 standard | Shower | 11 | 0.0361 | 0.0380 | 0.6364 | 0.6818 | 0.7273 | 0.9091 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 12 | 0.1825 | 0.1986 | 0.2750 | 0.3527 | 0.6667 | 0.9167 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 12 | 0.1396 | 0.1542 | -0.1076 | -0.1485 | 0.0833 | 0.5833 |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 11 | 0.0944 | 0.1061 | 0.0575 | 0.1120 | 0.3636 | 0.8182 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 12 | 0.0728 | 0.0822 | 0.6514 | 0.6555 | 0.8333 | 0.9167 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 12 | 0.1110 | 0.1188 | 0.1924 | 0.2362 | 0.3333 | 0.6667 |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 11 | 0.0355 | 0.0408 | 0.5152 | 0.5909 | 0.7273 | 0.9091 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | Appliance | 12 | 0.1856 | 0.2033 | 0.1916 | 0.1860 | 0.5833 | 0.5833 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | HVAC | 12 | 0.1518 | 0.1609 | 0.3430 | 0.3415 | 0.5000 | 0.6667 |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | Shower | 11 | 0.0985 | 0.1093 | 0.1333 | 0.1500 | 0.4545 | 0.7273 |
| deepseek | retrieval_k1 | Retrieval k=1 | Appliance | 12 | 0.1097 | 0.1309 | 0.5000 | 0.5000 | 0.6667 | 0.8333 |
| deepseek | retrieval_k1 | Retrieval k=1 | HVAC | 12 | 0.1043 | 0.1117 | 0.2222 | 0.2083 | 0.4167 | 0.7500 |
| deepseek | retrieval_k1 | Retrieval k=1 | Shower | 11 | 0.0430 | 0.0518 | 0.6803 | 0.7151 | 0.8182 | 0.9091 |
| deepseek | retrieval_k5 | Retrieval k=5 | Appliance | 12 | 0.0679 | 0.0775 | 0.7069 | 0.7805 | 0.7500 | 1.0000 |
| deepseek | retrieval_k5 | Retrieval k=5 | HVAC | 12 | 0.1030 | 0.1092 | 0.4263 | 0.4248 | 0.3333 | 0.7500 |
| deepseek | retrieval_k5 | Retrieval k=5 | Shower | 11 | 0.0361 | 0.0404 | 0.5758 | 0.6364 | 0.6364 | 0.9091 |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 12 | 0.0605 | 0.0663 | 0.7222 | 0.7917 | 0.9167 | 1.0000 |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 12 | 0.0932 | 0.1151 | 0.0125 | -0.0112 | 0.4167 | 0.7500 |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 11 | 0.0270 | 0.0298 | 0.6197 | 0.6242 | 0.6364 | 0.8182 |
| gemini | control_k3 | Control k=3 standard | Appliance | 12 | 0.0705 | 0.0763 | 0.7472 | 0.7693 | 0.9167 | 0.9167 |
| gemini | control_k3 | Control k=3 standard | HVAC | 12 | 0.1095 | 0.1330 | -0.3180 | -0.3222 | 0.2500 | 0.5833 |
| gemini | control_k3 | Control k=3 standard | Shower | 11 | 0.0298 | 0.0343 | 0.6197 | 0.6242 | 0.7273 | 0.8182 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 12 | 0.1874 | 0.2121 | 0.1111 | 0.1250 | 0.5000 | 0.7500 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 12 | 0.1785 | 0.2062 | -0.0556 | -0.0833 | 0.4167 | 0.7500 |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 11 | 0.0549 | 0.0610 | 0.2727 | 0.2727 | 0.3636 | 0.7273 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 12 | 0.0703 | 0.0753 | 0.8027 | 0.8110 | 0.9167 | 0.9167 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 12 | 0.1148 | 0.1396 | -0.2778 | -0.2917 | 0.2500 | 0.5833 |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 11 | 0.0287 | 0.0328 | 0.4106 | 0.4213 | 0.7273 | 0.7273 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | Appliance | 12 | 0.1948 | 0.2223 | 0.0000 | -0.0417 | 0.2500 | 0.7500 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | HVAC | 12 | 0.1914 | 0.2095 | -0.1514 | -0.1555 | 0.2500 | 0.5833 |
| gemini | random_exemplars_k3 | Random exemplars k=3 | Shower | 11 | 0.0597 | 0.0659 | 0.0909 | 0.0909 | 0.4545 | 0.5455 |
| gemini | retrieval_k1 | Retrieval k=1 | Appliance | 12 | 0.0858 | 0.0975 | 0.6514 | 0.6555 | 0.6667 | 0.8333 |
| gemini | retrieval_k1 | Retrieval k=1 | HVAC | 12 | 0.1299 | 0.1520 | -0.2560 | -0.3060 | 0.1667 | 0.5833 |
| gemini | retrieval_k1 | Retrieval k=1 | Shower | 11 | 0.0291 | 0.0338 | 0.6364 | 0.6364 | 0.7273 | 0.8182 |
| gemini | retrieval_k5 | Retrieval k=5 | Appliance | 12 | 0.0697 | 0.0763 | 0.6667 | 0.7083 | 0.9167 | 0.9167 |
| gemini | retrieval_k5 | Retrieval k=5 | HVAC | 12 | 0.0832 | 0.0964 | 0.2069 | 0.2388 | 0.5000 | 0.8333 |
| gemini | retrieval_k5 | Retrieval k=5 | Shower | 11 | 0.0256 | 0.0301 | 0.5758 | 0.6364 | 0.6364 | 0.9091 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 12 | 0.1216 | 0.1428 | -0.0000 | -0.0417 | 0.3333 | 0.5000 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 12 | 0.1134 | 0.1298 | 0.3333 | 0.3750 | 0.5833 | 0.8333 |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 11 | 0.0406 | 0.0478 | 0.3333 | 0.3182 | 0.5455 | 0.8182 |
| gptoss | control_k3 | Control k=3 standard | Appliance | 12 | 0.1189 | 0.1336 | 0.2778 | 0.2917 | 0.5000 | 0.6667 |
| gptoss | control_k3 | Control k=3 standard | HVAC | 12 | 0.0941 | 0.1119 | 0.1111 | 0.1667 | 0.4167 | 0.7500 |
| gptoss | control_k3 | Control k=3 standard | Shower | 11 | 0.0443 | 0.0516 | 0.2121 | 0.2727 | 0.5455 | 0.7273 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 12 | 0.2147 | 0.2466 | -0.1348 | -0.1696 | 0.2500 | 0.5833 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 12 | 0.1475 | 0.1668 | -0.4545 | -0.5000 | 0.0833 | 0.4167 |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 11 | 0.0600 | 0.0702 | 0.3939 | 0.4091 | 0.6364 | 0.9091 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 12 | 0.1199 | 0.1370 | 0.1667 | 0.2083 | 0.4167 | 0.6667 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 12 | 0.1095 | 0.1302 | -0.0556 | -0.0417 | 0.3333 | 0.7500 |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 11 | 0.0471 | 0.0524 | 0.5152 | 0.5455 | 0.6364 | 0.8182 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | Appliance | 12 | 0.2954 | 0.3252 | -0.2931 | -0.3445 | 0.0833 | 0.5833 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | HVAC | 12 | 0.1409 | 0.1517 | 0.0000 | 0.0000 | 0.1667 | 0.8333 |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | Shower | 11 | 0.0751 | 0.0943 | 0.2121 | 0.2273 | 0.6364 | 0.7273 |
| gptoss | retrieval_k1 | Retrieval k=1 | Appliance | 12 | 0.1411 | 0.1642 | 0.2375 | 0.3028 | 0.5833 | 0.8333 |
| gptoss | retrieval_k1 | Retrieval k=1 | HVAC | 12 | 0.1144 | 0.1247 | 0.2778 | 0.2917 | 0.5833 | 0.8333 |
| gptoss | retrieval_k1 | Retrieval k=1 | Shower | 11 | 0.0353 | 0.0415 | 0.2894 | 0.2849 | 0.5455 | 0.6364 |
| gptoss | retrieval_k5 | Retrieval k=5 | Appliance | 12 | 0.1132 | 0.1327 | 0.2778 | 0.3333 | 0.4167 | 0.9167 |
| gptoss | retrieval_k5 | Retrieval k=5 | HVAC | 12 | 0.1100 | 0.1226 | 0.3889 | 0.3750 | 0.5833 | 0.8333 |
| gptoss | retrieval_k5 | Retrieval k=5 | Shower | 11 | 0.0501 | 0.0556 | 0.3167 | 0.3060 | 0.5455 | 0.7273 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Appliance | 12 | 0.1140 | 0.1297 | -0.1954 | -0.2151 | 0.3333 | 0.5833 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | HVAC | 12 | 0.1141 | 0.1261 | 0.1333 | 0.1500 | 0.4167 | 0.7500 |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Shower | 11 | 0.0565 | 0.0625 | N/A | N/A | 0.6364 | 0.7273 |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 12 | 0.1153 | 0.1272 | 0.5000 | 0.5417 | 0.5833 | 0.8333 |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 12 | 0.1179 | 0.1383 | 0.1182 | 0.1575 | 0.3333 | 0.5833 |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 11 | 0.0510 | 0.0641 | 0.0439 | 0.0787 | 0.4545 | 0.6364 |
| qwen | control_k3 | Control k=3 standard | Appliance | 12 | 0.1054 | 0.1256 | 0.5652 | 0.5915 | 0.7500 | 0.9167 |
| qwen | control_k3 | Control k=3 standard | HVAC | 12 | 0.1283 | 0.1373 | 0.1212 | 0.0909 | 0.4167 | 0.6667 |
| qwen | control_k3 | Control k=3 standard | Shower | 11 | 0.0726 | 0.0936 | 0.4333 | 0.4500 | 0.5455 | 0.7273 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 12 | 0.1803 | 0.1980 | 0.6361 | 0.6860 | 0.8333 | 1.0000 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 12 | 0.1441 | 0.1637 | -0.0773 | -0.1031 | 0.2500 | 0.6667 |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 11 | 0.0960 | 0.1040 | 0.3633 | 0.3732 | 0.6364 | 0.8182 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 12 | 0.1250 | 0.1487 | 0.4545 | 0.4091 | 0.6667 | 0.9167 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 12 | 0.1276 | 0.1521 | -0.1212 | -0.1364 | 0.1667 | 0.7500 |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 11 | 0.0471 | 0.0574 | 0.3636 | 0.4091 | 0.5455 | 0.8182 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | Appliance | 12 | 0.1688 | 0.1906 | 0.3583 | 0.3943 | 0.7500 | 0.7500 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | HVAC | 12 | 0.1594 | 0.1771 | 0.0556 | 0.0417 | 0.3333 | 0.5000 |
| qwen | random_exemplars_k3 | Random exemplars k=3 | Shower | 11 | 0.0756 | 0.0851 | -0.2518 | -0.2182 | 0.4545 | 0.7273 |
| qwen | retrieval_k1 | Retrieval k=1 | Appliance | 12 | 0.1084 | 0.1170 | 0.5556 | 0.6250 | 0.6667 | 1.0000 |
| qwen | retrieval_k1 | Retrieval k=1 | HVAC | 12 | 0.1345 | 0.1602 | 0.2931 | 0.3862 | 0.6667 | 0.8333 |
| qwen | retrieval_k1 | Retrieval k=1 | Shower | 11 | 0.0605 | 0.0694 | 0.2483 | 0.2366 | 0.5455 | 0.7273 |
| qwen | retrieval_k5 | Retrieval k=5 | Appliance | 12 | 0.0921 | 0.1073 | 0.3736 | 0.3638 | 0.5000 | 0.7500 |
| qwen | retrieval_k5 | Retrieval k=5 | HVAC | 12 | 0.1341 | 0.1543 | -0.2091 | -0.2029 | 0.3333 | 0.5833 |
| qwen | retrieval_k5 | Retrieval k=5 | Shower | 11 | 0.0448 | 0.0548 | 0.3167 | 0.3060 | 0.4545 | 0.7273 |

## Highest Score-MAE Cases

| model_key | ablation_id | decision_type | source_scenario_id | question | alternative | score_mae | kendall_tau | gt_top1 | pred_top1 | error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gptoss | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 PM | 0.5420 | -0.3333 | 2:00 PM | 9:00 PM |  |
| gptoss | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 9:00 PM | 0.5420 | -0.3333 | 2:00 PM | 9:00 PM |  |
| gptoss | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 AM | 0.5420 | -0.3333 | 2:00 PM | 9:00 PM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 AM | 0.5087 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 PM | 0.5087 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 9:00 PM | 0.5087 | 1.0000 | 2:00 PM | 2:00 PM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 3:00 PM | 0.4467 | 0.0000 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 8:00 AM | 0.4467 | 0.0000 | 8:00 AM | 8:00 AM |  |
| qwen | descriptions_no_scores_ranks | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 11:00 PM | 0.4467 | 0.0000 | 8:00 AM | 8:00 AM |  |
| gemini | random_exemplars_k3 | HVAC | hvac_22 | We're done for the day, what heat temperature should I set overnight? | 68 | 0.4452 | 0.3333 | 68 | 68 |  |
| gemini | random_exemplars_k3 | HVAC | hvac_22 | We're done for the day, what heat temperature should I set overnight? | 64 | 0.4452 | 0.3333 | 68 | 68 |  |
| gemini | random_exemplars_k3 | HVAC | hvac_22 | We're done for the day, what heat temperature should I set overnight? | 72 | 0.4452 | 0.3333 | 68 | 68 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 81 | 0.4270 | -0.8165 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 77 | 0.4270 | -0.8165 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | hvac_25 | With 1 person home, what AC temperature should I set? | 74 | 0.4270 | -0.8165 | 77 | 74 |  |
| gemini | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 9:00 PM | 0.4153 | -0.3333 | 2:00 PM | 9:00 PM |  |
| gemini | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 PM | 0.4153 | -0.3333 | 2:00 PM | 9:00 PM |  |
| gemini | random_exemplars_k3 | Appliance | appliance_24 | It's around 2 in the afternoon and I need to run the dryer. When should I start it? | 2:00 AM | 0.4153 | -0.3333 | 2:00 PM | 9:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 8:00 AM | 0.4017 | -1.0000 | 8:00 AM | 3:00 PM |  |
| qwen | random_exemplars_k3 | Appliance | appliance_31 | It's around 8 in the morning and I need to run the dryer. When should I start it? | 11:00 PM | 0.4017 | -1.0000 | 8:00 AM | 3:00 PM |  |

## Friedman Tests (non-parametric omnibus)

Chi-squared statistic for each metric across all ablation configurations.

| metric | chi2 | p_value | df | n_scenarios | n_configs |
| --- | --- | --- | --- | --- | --- |
| kendall_tau | 12.4477 | 0.0868 | 7 | 21 | 8 |
| score_mae | 37.5314 | 0.0000 | 7 | 35 | 8 |
| score_rmse | 36.6743 | 0.0000 | 7 | 35 | 8 |
| top1_accuracy | 12.2267 | 0.0933 | 7 | 35 | 8 |

## Post-hoc Pairwise Wilcoxon Tests (Holm-corrected)

Significant pairwise differences after Holm-Bonferroni correction.

| config_i | config_j | statistic | p_value | cliff_delta | cliff_delta_interpretation | n_pairs | p_holm | significant_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_k3 | random_exemplars_k3 | 51.0000 | 0.0000 | -0.4645 | medium | 35 | 0.0001 | True |
| exemplars_no_hidden_params | random_exemplars_k3 | 73.0000 | 0.0000 | -0.4220 | medium | 35 | 0.0006 | True |
| random_exemplars_k3 | retrieval_k5 | 83.0000 | 0.0001 | 0.4367 | medium | 35 | 0.0014 | True |
| alternate_embedding_k3 | random_exemplars_k3 | 86.0000 | 0.0001 | -0.4220 | medium | 35 | 0.0018 | True |
| nearest_neighbor_k3 | random_exemplars_k3 | 91.0000 | 0.0001 | -0.4139 | medium | 35 | 0.0026 | True |
| random_exemplars_k3 | retrieval_k1 | 92.0000 | 0.0001 | 0.3943 | medium | 35 | 0.0027 | True |
| alternate_embedding_k3 | descriptions_no_scores_ranks | 116.0000 | 0.0007 | -0.3061 | small | 35 | 0.0161 | True |
| control_k3 | descriptions_no_scores_ranks | 121.0000 | 0.0010 | -0.3584 | medium | 35 | 0.0216 | True |
| descriptions_no_scores_ranks | retrieval_k5 | 129.0000 | 0.0017 | 0.2914 | small | 35 | 0.0346 | True |
| descriptions_no_scores_ranks | exemplars_no_hidden_params | 141.0000 | 0.0036 | 0.2980 | small | 35 | 0.0682 | False |
| descriptions_no_scores_ranks | nearest_neighbor_k3 | 155.0000 | 0.0078 | 0.2424 | small | 35 | 0.1406 | False |
| descriptions_no_scores_ranks | retrieval_k1 | 156.0000 | 0.0082 | 0.2800 | small | 35 | 0.1400 | False |
| descriptions_no_scores_ranks | random_exemplars_k3 | 211.0000 | 0.0902 | -0.1641 | small | 35 | 1.0000 | False |
| nearest_neighbor_k3 | retrieval_k5 | 229.0000 | 0.1633 | 0.0580 | negligible | 35 | 1.0000 | False |
| control_k3 | retrieval_k1 | 236.0000 | 0.2012 | -0.0661 | negligible | 35 | 1.0000 | False |
| control_k3 | nearest_neighbor_k3 | 263.0000 | 0.4036 | -0.0776 | negligible | 35 | 1.0000 | False |
| exemplars_no_hidden_params | retrieval_k1 | 267.5000 | 0.4366 | 0.0073 | negligible | 35 | 1.0000 | False |
| control_k3 | exemplars_no_hidden_params | 240.0000 | 0.4693 | -0.0539 | negligible | 35 | 1.0000 | False |
| retrieval_k1 | retrieval_k5 | 272.0000 | 0.4911 | 0.0171 | negligible | 35 | 1.0000 | False |
| exemplars_no_hidden_params | nearest_neighbor_k3 | 281.0000 | 0.5876 | -0.0563 | negligible | 35 | 1.0000 | False |
| exemplars_no_hidden_params | retrieval_k5 | 280.5000 | 0.7713 | -0.0033 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | control_k3 | 297.0000 | 0.7771 | 0.0588 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | nearest_neighbor_k3 | 298.0000 | 0.7896 | -0.0596 | negligible | 35 | 1.0000 | False |
| control_k3 | retrieval_k5 | 275.0000 | 0.9217 | -0.0310 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | retrieval_k5 | 312.0000 | 0.9678 | -0.0286 | negligible | 35 | 1.0000 | False |
| nearest_neighbor_k3 | retrieval_k1 | 312.0000 | 0.9678 | 0.0335 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | exemplars_no_hidden_params | 313.0000 | 0.9806 | -0.0204 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | retrieval_k1 | 313.0000 | 0.9806 | 0.0057 | negligible | 35 | 0.9806 | False |
| control_k3 | random_exemplars_k3 | 51.0000 | 0.0000 | -0.4841 | large | 35 | 0.0001 | True |
| random_exemplars_k3 | retrieval_k5 | 74.0000 | 0.0000 | 0.4302 | medium | 35 | 0.0006 | True |
| exemplars_no_hidden_params | random_exemplars_k3 | 76.0000 | 0.0000 | -0.4302 | medium | 35 | 0.0007 | True |
| nearest_neighbor_k3 | random_exemplars_k3 | 77.0000 | 0.0000 | -0.4335 | medium | 35 | 0.0008 | True |
| random_exemplars_k3 | retrieval_k1 | 80.0000 | 0.0000 | 0.4253 | medium | 35 | 0.0010 | True |
| alternate_embedding_k3 | random_exemplars_k3 | 81.0000 | 0.0000 | -0.4204 | medium | 35 | 0.0010 | True |
| control_k3 | descriptions_no_scores_ranks | 108.0000 | 0.0004 | -0.3780 | medium | 35 | 0.0091 | True |
| descriptions_no_scores_ranks | retrieval_k5 | 123.0000 | 0.0012 | 0.2947 | small | 35 | 0.0246 | True |
| alternate_embedding_k3 | descriptions_no_scores_ranks | 124.0000 | 0.0013 | -0.2980 | small | 35 | 0.0251 | True |
| descriptions_no_scores_ranks | exemplars_no_hidden_params | 134.0000 | 0.0024 | 0.3094 | small | 35 | 0.0449 | True |
| descriptions_no_scores_ranks | retrieval_k1 | 137.0000 | 0.0028 | 0.2996 | small | 35 | 0.0510 | False |
| descriptions_no_scores_ranks | nearest_neighbor_k3 | 143.0000 | 0.0040 | 0.2718 | small | 35 | 0.0685 | False |
| nearest_neighbor_k3 | retrieval_k5 | 231.0000 | 0.1736 | 0.0645 | negligible | 35 | 1.0000 | False |
| descriptions_no_scores_ranks | random_exemplars_k3 | 235.0000 | 0.1954 | -0.1380 | negligible | 35 | 1.0000 | False |
| control_k3 | retrieval_k1 | 246.0000 | 0.2655 | -0.0351 | negligible | 35 | 1.0000 | False |
| control_k3 | nearest_neighbor_k3 | 272.0000 | 0.4911 | -0.0792 | negligible | 35 | 1.0000 | False |
| exemplars_no_hidden_params | nearest_neighbor_k3 | 272.0000 | 0.4911 | -0.0531 | negligible | 35 | 1.0000 | False |
| retrieval_k1 | retrieval_k5 | 283.0000 | 0.6101 | 0.0204 | negligible | 35 | 1.0000 | False |
| exemplars_no_hidden_params | retrieval_k1 | 285.0000 | 0.6330 | 0.0155 | negligible | 35 | 1.0000 | False |
| control_k3 | exemplars_no_hidden_params | 273.0000 | 0.6753 | -0.0490 | negligible | 35 | 1.0000 | False |
| exemplars_no_hidden_params | retrieval_k5 | 274.0000 | 0.6879 | 0.0016 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | control_k3 | 299.0000 | 0.8020 | 0.0629 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | retrieval_k1 | 306.0000 | 0.8907 | 0.0220 | negligible | 35 | 1.0000 | False |
| nearest_neighbor_k3 | retrieval_k1 | 308.0000 | 0.9163 | 0.0302 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | nearest_neighbor_k3 | 310.0000 | 0.9420 | -0.0400 | negligible | 35 | 1.0000 | False |
| control_k3 | retrieval_k5 | 278.0000 | 0.9644 | -0.0465 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | exemplars_no_hidden_params | 313.0000 | 0.9806 | -0.0155 | negligible | 35 | 1.0000 | False |
| alternate_embedding_k3 | retrieval_k5 | 314.0000 | 0.9935 | -0.0106 | negligible | 35 | 0.9935 | False |

## Bootstrap 95% Confidence Intervals

Percentile-method 95% CIs for each configuration's mean metric value.

| ablation_id | ablation_label | point_estimate | ci_lower | ci_upper | metric |
| --- | --- | --- | --- | --- | --- |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.3257 | 0.2075 | 0.4432 | kendall_tau |
| control_k3 | Control k=3 standard | 0.3159 | 0.2029 | 0.4262 | kendall_tau |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1088 | -0.0079 | 0.2191 | kendall_tau |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 0.2999 | 0.1815 | 0.4131 | kendall_tau |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | -0.0389 | -0.3333 | 0.2611 | kendall_tau |
| random_exemplars_k3 | Random exemplars k=3 | 0.0617 | -0.0584 | 0.1826 | kendall_tau |
| retrieval_k1 | Retrieval k=1 | 0.3636 | 0.2495 | 0.4737 | kendall_tau |
| retrieval_k5 | Retrieval k=5 | 0.3878 | 0.2850 | 0.4861 | kendall_tau |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.0807 | 0.0703 | 0.0917 | score_mae |
| control_k3 | Control k=3 standard | 0.0859 | 0.0735 | 0.0991 | score_mae |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.1418 | 0.1263 | 0.1579 | score_mae |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 0.0854 | 0.0735 | 0.0978 | score_mae |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.0960 | 0.0754 | 0.1178 | score_mae |
| random_exemplars_k3 | Random exemplars k=3 | 0.1518 | 0.1338 | 0.1701 | score_mae |
| retrieval_k1 | Retrieval k=1 | 0.0927 | 0.0804 | 0.1057 | score_mae |
| retrieval_k5 | Retrieval k=5 | 0.0786 | 0.0679 | 0.0899 | score_mae |
| alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 0.5643 | 0.4786 | 0.6429 | top1_accuracy |
| control_k3 | Control k=3 standard | 0.5786 | 0.5000 | 0.6571 | top1_accuracy |
| descriptions_no_scores_ranks | Descriptions without scores or ranks | 0.4214 | 0.3429 | 0.5071 | top1_accuracy |
| exemplars_no_hidden_params | Exemplars without hidden parameters | 0.5429 | 0.4571 | 0.6286 | top1_accuracy |
| nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 0.4571 | 0.2857 | 0.6286 | top1_accuracy |
| random_exemplars_k3 | Random exemplars k=3 | 0.4071 | 0.3286 | 0.4929 | top1_accuracy |
| retrieval_k1 | Retrieval k=1 | 0.5857 | 0.5000 | 0.6714 | top1_accuracy |
| retrieval_k5 | Retrieval k=5 | 0.5500 | 0.4643 | 0.6357 | top1_accuracy |

