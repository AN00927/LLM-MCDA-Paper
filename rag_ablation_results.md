# RAG Ablation Study

## Overview

- Sample size: 15
- Random seed: 13
- Scenarios evaluated: 12
- Result rows: 1305
- Output plots: None

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
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 12 | 0.0755 | 0.0836 | 0.4100 | 0.4911 | N/A | N/A | 1.2260 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| deepseek | control_k3 | Control k=3 standard | 12 | 0.1042 | 0.1161 | 0.0022 | -0.0488 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | 12 | 0.1432 | 0.1606 | -0.0345 | -0.0089 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | 12 | 0.0981 | 0.1071 | 0.3533 | 0.3488 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | 12 | 0.1522 | 0.1661 | 0.0607 | 0.0810 | N/A | N/A | 0.4423 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| deepseek | retrieval_k1 | Retrieval k=1 | 12 | 0.0888 | 0.1053 | 0.3878 | 0.3911 | N/A | N/A | 0.0546 | 15.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| deepseek | retrieval_k5 | Retrieval k=5 | 12 | 0.0952 | 0.1051 | 0.1678 | 0.1756 | N/A | N/A | 0.0799 | 75.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 12 | 0.0679 | 0.0795 | 0.4000 | 0.4000 | N/A | N/A | 1.2260 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | control_k3 | Control k=3 standard | 12 | 0.0638 | 0.0732 | 0.1111 | 0.1667 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | 12 | 0.1225 | 0.1412 | -0.0789 | -0.0756 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | 12 | 0.0823 | 0.0920 | 0.2000 | 0.2000 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | random_exemplars_k3 | Random exemplars k=3 | 12 | 0.1457 | 0.1624 | 0.0345 | 0.0423 | N/A | N/A | 0.4242 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | retrieval_k1 | Retrieval k=1 | 12 | 0.0746 | 0.0884 | 0.3456 | 0.3423 | N/A | N/A | 0.0546 | 15.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gemini | retrieval_k5 | Retrieval k=5 | 12 | 0.0714 | 0.0790 | 0.3433 | 0.3577 | N/A | N/A | 0.0799 | 75.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 12 | 0.0812 | 0.0912 | 0.1456 | 0.1423 | N/A | N/A | 1.2260 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | control_k3 | Control k=3 standard | 12 | 0.0732 | 0.0899 | 0.2444 | 0.2667 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | 12 | 0.1591 | 0.1815 | -0.0444 | -0.0333 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | 12 | 0.0909 | 0.1008 | 0.3655 | 0.3911 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | 12 | 0.1395 | 0.1642 | 0.1755 | 0.1488 | N/A | N/A | 0.4306 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | retrieval_k1 | Retrieval k=1 | 12 | 0.0732 | 0.0851 | 0.2889 | 0.3000 | N/A | N/A | 0.0546 | 15.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| gptoss | retrieval_k5 | Retrieval k=5 | 12 | 0.0994 | 0.1082 | 0.0667 | 0.1000 | N/A | N/A | 0.0799 | 75.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | 12 | 0.0978 | 0.1082 | 0.0000 | 0.0625 | N/A | N/A | 0.0678 | 45.0000 | 0.0000 | 0.0000 | 0.0000 | N/A |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | 12 | 0.0975 | 0.1104 | 0.2544 | 0.2577 | N/A | N/A | 1.2260 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| qwen | control_k3 | Control k=3 standard | 12 | 0.0961 | 0.1090 | 0.2122 | 0.2089 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | 12 | 0.1739 | 0.1922 | 0.0476 | 0.0714 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | 12 | 0.1202 | 0.1314 | 0.2000 | 0.2333 | N/A | N/A | 0.0678 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| qwen | random_exemplars_k3 | Random exemplars k=3 | 12 | 0.1504 | 0.1626 | 0.0567 | 0.0423 | N/A | N/A | 0.4361 | 45.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| qwen | retrieval_k1 | Retrieval k=1 | 12 | 0.0925 | 0.1053 | 0.4222 | 0.5000 | N/A | N/A | 0.0546 | 15.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |
| qwen | retrieval_k5 | Retrieval k=5 | 12 | 0.0800 | 0.0949 | 0.1678 | 0.2089 | N/A | N/A | 0.0799 | 75.0000 | 45.0000 | 45.0000 | 0.0000 | N/A |

## Summary by Decision Type

| model_key | ablation_id | ablation_label | decision_type | n_scenarios | score_mae | score_rmse | kendall_tau | spearman_rho | top1_accuracy | top2_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 5 | 0.0559 | 0.0689 | 0.3333 | 0.4000 | N/A | N/A |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 5 | 0.1167 | 0.1219 | 0.4300 | 0.5732 | N/A | N/A |
| deepseek | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 5 | 0.0538 | 0.0600 | 0.4667 | 0.5000 | N/A | N/A |
| deepseek | control_k3 | Control k=3 standard | Appliance | 5 | 0.0811 | 0.0982 | 0.0667 | 0.0000 | N/A | N/A |
| deepseek | control_k3 | Control k=3 standard | HVAC | 5 | 0.1698 | 0.1818 | -0.2966 | -0.3732 | N/A | N/A |
| deepseek | control_k3 | Control k=3 standard | Shower | 5 | 0.0618 | 0.0684 | 0.2367 | 0.2268 | N/A | N/A |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 5 | 0.1691 | 0.1939 | -0.0667 | 0.0000 | N/A | N/A |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 5 | 0.1634 | 0.1789 | -0.2000 | -0.2000 | N/A | N/A |
| deepseek | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 5 | 0.0972 | 0.1088 | 0.1633 | 0.1732 | N/A | N/A |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 5 | 0.0707 | 0.0817 | 0.6599 | 0.6464 | N/A | N/A |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 5 | 0.1717 | 0.1819 | 0.0667 | 0.1000 | N/A | N/A |
| deepseek | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 5 | 0.0519 | 0.0577 | 0.3333 | 0.3000 | N/A | N/A |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | Appliance | 5 | 0.1722 | 0.2014 | -0.1208 | -0.0915 | N/A | N/A |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | HVAC | 5 | 0.2069 | 0.2128 | -0.0667 | -0.1000 | N/A | N/A |
| deepseek | random_exemplars_k3 | Random exemplars k=3 | Shower | 5 | 0.0774 | 0.0841 | 0.3333 | 0.4000 | N/A | N/A |
| deepseek | retrieval_k1 | Retrieval k=1 | Appliance | 5 | 0.1080 | 0.1340 | 0.3333 | 0.3000 | N/A | N/A |
| deepseek | retrieval_k1 | Retrieval k=1 | HVAC | 5 | 0.1053 | 0.1108 | 0.3633 | 0.3732 | N/A | N/A |
| deepseek | retrieval_k1 | Retrieval k=1 | Shower | 5 | 0.0532 | 0.0709 | 0.4667 | 0.5000 | N/A | N/A |
| deepseek | retrieval_k5 | Retrieval k=5 | Appliance | 5 | 0.0879 | 0.0972 | 0.3333 | 0.4000 | N/A | N/A |
| deepseek | retrieval_k5 | Retrieval k=5 | HVAC | 5 | 0.1654 | 0.1804 | -0.2966 | -0.2732 | N/A | N/A |
| deepseek | retrieval_k5 | Retrieval k=5 | Shower | 5 | 0.0324 | 0.0377 | 0.4667 | 0.4000 | N/A | N/A |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 5 | 0.0625 | 0.0689 | 0.7333 | 0.8000 | N/A | N/A |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 5 | 0.1012 | 0.1255 | 0.0000 | 0.0000 | N/A | N/A |
| gemini | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 5 | 0.0400 | 0.0442 | 0.4667 | 0.4000 | N/A | N/A |
| gemini | control_k3 | Control k=3 standard | Appliance | 5 | 0.0789 | 0.0857 | 0.2966 | 0.3732 | N/A | N/A |
| gemini | control_k3 | Control k=3 standard | HVAC | 5 | 0.0749 | 0.0890 | -0.4300 | -0.3732 | N/A | N/A |
| gemini | control_k3 | Control k=3 standard | Shower | 5 | 0.0376 | 0.0450 | 0.4667 | 0.5000 | N/A | N/A |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 5 | 0.1528 | 0.1864 | -0.1034 | -0.1268 | N/A | N/A |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 5 | 0.1556 | 0.1721 | -0.4667 | -0.5000 | N/A | N/A |
| gemini | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 5 | 0.0593 | 0.0652 | 0.3333 | 0.4000 | N/A | N/A |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 5 | 0.0763 | 0.0840 | 0.4667 | 0.5000 | N/A | N/A |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 5 | 0.1316 | 0.1478 | -0.2000 | -0.2000 | N/A | N/A |
| gemini | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 5 | 0.0392 | 0.0443 | 0.3333 | 0.3000 | N/A | N/A |
| gemini | random_exemplars_k3 | Random exemplars k=3 | Appliance | 5 | 0.1817 | 0.2081 | 0.0667 | 0.1000 | N/A | N/A |
| gemini | random_exemplars_k3 | Random exemplars k=3 | HVAC | 5 | 0.1798 | 0.1970 | -0.4300 | -0.4732 | N/A | N/A |
| gemini | random_exemplars_k3 | Random exemplars k=3 | Shower | 5 | 0.0756 | 0.0821 | 0.4667 | 0.5000 | N/A | N/A |
| gemini | retrieval_k1 | Retrieval k=1 | Appliance | 5 | 0.0934 | 0.1103 | 0.6000 | 0.6000 | N/A | N/A |
| gemini | retrieval_k1 | Retrieval k=1 | HVAC | 5 | 0.0904 | 0.1064 | -0.1633 | -0.1732 | N/A | N/A |
| gemini | retrieval_k1 | Retrieval k=1 | Shower | 5 | 0.0400 | 0.0485 | 0.6000 | 0.6000 | N/A | N/A |
| gemini | retrieval_k5 | Retrieval k=5 | Appliance | 5 | 0.0651 | 0.0677 | 0.6300 | 0.6732 | N/A | N/A |
| gemini | retrieval_k5 | Retrieval k=5 | HVAC | 5 | 0.1111 | 0.1245 | -0.0667 | -0.1000 | N/A | N/A |
| gemini | retrieval_k5 | Retrieval k=5 | Shower | 5 | 0.0380 | 0.0447 | 0.4667 | 0.5000 | N/A | N/A |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 5 | 0.0941 | 0.1015 | 0.4000 | 0.4000 | N/A | N/A |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 5 | 0.1049 | 0.1206 | -0.0300 | -0.0732 | N/A | N/A |
| gptoss | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 5 | 0.0447 | 0.0514 | 0.0667 | 0.1000 | N/A | N/A |
| gptoss | control_k3 | Control k=3 standard | Appliance | 5 | 0.1039 | 0.1206 | 0.4667 | 0.5000 | N/A | N/A |
| gptoss | control_k3 | Control k=3 standard | HVAC | 5 | 0.0735 | 0.0951 | 0.0300 | 0.0732 | N/A | N/A |
| gptoss | control_k3 | Control k=3 standard | Shower | 5 | 0.0421 | 0.0540 | 0.2367 | 0.2268 | N/A | N/A |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 5 | 0.2080 | 0.2490 | -0.0667 | -0.1000 | N/A | N/A |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 5 | 0.1645 | 0.1781 | -0.1333 | -0.1000 | N/A | N/A |
| gptoss | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 5 | 0.1047 | 0.1175 | 0.0667 | 0.1000 | N/A | N/A |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 5 | 0.1161 | 0.1294 | 0.2000 | 0.2000 | N/A | N/A |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 5 | 0.1143 | 0.1252 | 0.4667 | 0.5000 | N/A | N/A |
| gptoss | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 5 | 0.0423 | 0.0478 | 0.4300 | 0.4732 | N/A | N/A |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | Appliance | 5 | 0.2211 | 0.2757 | -0.2000 | -0.3000 | N/A | N/A |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | HVAC | 5 | 0.1163 | 0.1262 | 0.2966 | 0.2732 | N/A | N/A |
| gptoss | random_exemplars_k3 | Random exemplars k=3 | Shower | 5 | 0.0812 | 0.0908 | 0.4300 | 0.4732 | N/A | N/A |
| gptoss | retrieval_k1 | Retrieval k=1 | Appliance | 5 | 0.0996 | 0.1207 | -0.0667 | -0.1000 | N/A | N/A |
| gptoss | retrieval_k1 | Retrieval k=1 | HVAC | 5 | 0.0584 | 0.0644 | 0.4667 | 0.5000 | N/A | N/A |
| gptoss | retrieval_k1 | Retrieval k=1 | Shower | 5 | 0.0615 | 0.0704 | 0.4667 | 0.5000 | N/A | N/A |
| gptoss | retrieval_k5 | Retrieval k=5 | Appliance | 5 | 0.1275 | 0.1401 | 0.3333 | 0.4000 | N/A | N/A |
| gptoss | retrieval_k5 | Retrieval k=5 | HVAC | 5 | 0.1203 | 0.1289 | -0.2000 | -0.2000 | N/A | N/A |
| gptoss | retrieval_k5 | Retrieval k=5 | Shower | 5 | 0.0502 | 0.0557 | 0.0667 | 0.1000 | N/A | N/A |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Appliance | 5 | 0.0977 | 0.1077 | -0.1208 | -0.0915 | N/A | N/A |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | HVAC | 5 | 0.1257 | 0.1388 | 0.1208 | 0.2165 | N/A | N/A |
| offline | nearest_neighbor_k3 | Nearest-neighbor prediction k=3 | Shower | 5 | 0.0700 | 0.0781 | N/A | N/A | N/A | N/A |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Appliance | 5 | 0.0919 | 0.1022 | 0.7333 | 0.8000 | N/A | N/A |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | HVAC | 5 | 0.1418 | 0.1524 | 0.0000 | 0.0000 | N/A | N/A |
| qwen | alternate_embedding_k3 | Alternate embedding k=3 (sentence-transformers/paraphrase-MiniLM-L3-v2) | Shower | 5 | 0.0588 | 0.0766 | 0.0300 | -0.0268 | N/A | N/A |
| qwen | control_k3 | Control k=3 standard | Appliance | 5 | 0.0764 | 0.0929 | 0.4667 | 0.6000 | N/A | N/A |
| qwen | control_k3 | Control k=3 standard | HVAC | 5 | 0.1504 | 0.1556 | 0.1034 | 0.0268 | N/A | N/A |
| qwen | control_k3 | Control k=3 standard | Shower | 5 | 0.0616 | 0.0785 | 0.0667 | 0.0000 | N/A | N/A |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | Appliance | 5 | 0.1677 | 0.1962 | 0.0966 | 0.0732 | N/A | N/A |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | HVAC | 5 | 0.2147 | 0.2325 | 0.1667 | 0.2500 | N/A | N/A |
| qwen | descriptions_no_scores_ranks | Descriptions without scores or ranks | Shower | 5 | 0.1393 | 0.1479 | -0.0966 | -0.0732 | N/A | N/A |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | Appliance | 5 | 0.1143 | 0.1289 | 0.4300 | 0.4732 | N/A | N/A |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | HVAC | 5 | 0.1923 | 0.2050 | 0.1034 | 0.1268 | N/A | N/A |
| qwen | exemplars_no_hidden_params | Exemplars without hidden parameters | Shower | 5 | 0.0540 | 0.0604 | 0.0667 | 0.1000 | N/A | N/A |
| qwen | random_exemplars_k3 | Random exemplars k=3 | Appliance | 5 | 0.1652 | 0.1719 | 0.0667 | 0.0000 | N/A | N/A |
| qwen | random_exemplars_k3 | Random exemplars k=3 | HVAC | 5 | 0.1828 | 0.1984 | 0.0000 | 0.0000 | N/A | N/A |
| qwen | random_exemplars_k3 | Random exemplars k=3 | Shower | 5 | 0.1032 | 0.1173 | 0.1034 | 0.1268 | N/A | N/A |
| qwen | retrieval_k1 | Retrieval k=1 | Appliance | 5 | 0.1030 | 0.1170 | 0.6000 | 0.7000 | N/A | N/A |
| qwen | retrieval_k1 | Retrieval k=1 | HVAC | 5 | 0.1178 | 0.1336 | 0.2000 | 0.3000 | N/A | N/A |
| qwen | retrieval_k1 | Retrieval k=1 | Shower | 5 | 0.0568 | 0.0653 | 0.4667 | 0.5000 | N/A | N/A |
| qwen | retrieval_k5 | Retrieval k=5 | Appliance | 5 | 0.0476 | 0.0574 | 0.5333 | 0.6000 | N/A | N/A |
| qwen | retrieval_k5 | Retrieval k=5 | HVAC | 5 | 0.1459 | 0.1681 | -0.1633 | -0.1732 | N/A | N/A |
| qwen | retrieval_k5 | Retrieval k=5 | Shower | 5 | 0.0466 | 0.0594 | 0.1333 | 0.2000 | N/A | N/A |

## Highest Score-MAE Cases

| model_key | ablation_id | decision_type | source_scenario_id | question | alternative | score_mae | kendall_tau | gt_top1 | pred_top1 | error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen | exemplars_no_hidden_params | HVAC | 25 | With 1 person home, what AC temperature should I set? | 74 | 0.4420 | -0.3333 | 77 | 74 |  |
| qwen | exemplars_no_hidden_params | HVAC | 25 | With 1 person home, what AC temperature should I set? | 77 | 0.4420 | -0.3333 | 77 | 74 |  |
| qwen | exemplars_no_hidden_params | HVAC | 25 | With 1 person home, what AC temperature should I set? | 81 | 0.4420 | -0.3333 | 77 | 74 |  |
| deepseek | control_k3 | HVAC | 25 | With 1 person home, what AC temperature should I set? | 77 | 0.4137 | -0.8165 | 77 | 81 |  |
| deepseek | control_k3 | HVAC | 25 | With 1 person home, what AC temperature should I set? | 81 | 0.4137 | -0.8165 | 77 | 81 |  |
| deepseek | control_k3 | HVAC | 25 | With 1 person home, what AC temperature should I set? | 74 | 0.4137 | -0.8165 | 77 | 81 |  |
| qwen | control_k3 | HVAC | 25 | With 1 person home, what AC temperature should I set? | 81 | 0.4003 | -0.3333 | 77 | 81 |  |
| qwen | control_k3 | HVAC | 25 | With 1 person home, what AC temperature should I set? | 77 | 0.4003 | -0.3333 | 77 | 81 |  |
| qwen | control_k3 | HVAC | 25 | With 1 person home, what AC temperature should I set? | 74 | 0.4003 | -0.3333 | 77 | 81 |  |
| deepseek | exemplars_no_hidden_params | HVAC | 25 | With 1 person home, what AC temperature should I set? | 81 | 0.3987 | 0.3333 | 77 | 74 |  |
| deepseek | exemplars_no_hidden_params | HVAC | 25 | With 1 person home, what AC temperature should I set? | 74 | 0.3987 | 0.3333 | 77 | 74 |  |
| deepseek | exemplars_no_hidden_params | HVAC | 25 | With 1 person home, what AC temperature should I set? | 77 | 0.3987 | 0.3333 | 77 | 74 |  |
| gemini | random_exemplars_k3 | HVAC | 16 | I'm heading out for the day, what heat temperature should I set? | 68 | 0.3512 | -0.3333 | 68 | 65 |  |
| gemini | random_exemplars_k3 | HVAC | 16 | I'm heading out for the day, what heat temperature should I set? | 71 | 0.3512 | -0.3333 | 68 | 65 |  |
| gemini | random_exemplars_k3 | HVAC | 16 | I'm heading out for the day, what heat temperature should I set? | 65 | 0.3512 | -0.3333 | 68 | 65 |  |
| qwen | descriptions_no_scores_ranks | HVAC | 16 | I'm heading out for the day, what heat temperature should I set? | 68 | 0.3487 | 0.3333 | 68 | 71 |  |
| qwen | descriptions_no_scores_ranks | HVAC | 16 | I'm heading out for the day, what heat temperature should I set? | 71 | 0.3487 | 0.3333 | 68 | 71 |  |
| qwen | descriptions_no_scores_ranks | HVAC | 16 | I'm heading out for the day, what heat temperature should I set? | 65 | 0.3487 | 0.3333 | 68 | 71 |  |
| gptoss | random_exemplars_k3 | Appliance | 3 | It's just past 9 AM and I need to run the washing machine. When should I start it? | 12:00 AM | 0.3305 | -0.3333 | 9:00 AM | 12:00 AM |  |
| gptoss | random_exemplars_k3 | Appliance | 3 | It's just past 9 AM and I need to run the washing machine. When should I start it? | 9:00 AM | 0.3305 | -0.3333 | 9:00 AM | 12:00 AM |  |

