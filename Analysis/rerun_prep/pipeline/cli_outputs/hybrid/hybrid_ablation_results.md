# AH Parameter-Provenance Ablation

Arms: extracted (per shipped run) / order_control / order_reversed / default (retrieval-set median, the floor). Multi-run arms: per-run mean over scored scenarios, then mean over runs.

| model | arm | n_scored | success_rate | kendall_tau | top1_accuracy | mae |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | extracted | 974 | 0.9990 | 0.8973 | 0.9076 | 0.0448 |
| deepseek | order_control | 585 | 1.0000 | 0.8974 | 0.9043 | 0.0455 |
| deepseek | order_reversed | 975 | 1.0000 | 0.9015 | 0.9108 | 0.0440 |
| deepseek | default_params | 195 | 1.0000 | 0.6410 | 0.7590 | 0.1327 |
| gemini | extracted | 975 | 1.0000 | 0.9234 | 0.9313 | 0.0477 |
| gemini | order_control | 585 | 1.0000 | 0.9293 | 0.9385 | 0.0454 |
| gemini | order_reversed | 975 | 1.0000 | 0.9262 | 0.9364 | 0.0466 |
| gemini | default_params | 195 | 1.0000 | 0.6410 | 0.7590 | 0.1327 |
| gptoss | extracted | 858 | 0.8800 | 0.8974 | 0.9173 | 0.0519 |
| gptoss | order_control | 514 | 0.8786 | 0.8985 | 0.9141 | 0.0517 |
| gptoss | order_reversed | 867 | 0.8892 | 0.8977 | 0.9088 | 0.0525 |
| gptoss | default_params | 195 | 1.0000 | 0.6410 | 0.7590 | 0.1327 |
| qwen | extracted | 973 | 0.9979 | 0.8801 | 0.8972 | 0.0718 |
| qwen | order_control | 585 | 1.0000 | 0.8895 | 0.9077 | 0.0736 |
| qwen | order_reversed | 975 | 1.0000 | 0.8913 | 0.9036 | 0.0725 |
| qwen | default_params | 195 | 1.0000 | 0.6410 | 0.7590 | 0.1327 |

Extraction gain over the dataset median, same scenarios per run:

| model | decision_type | extracted_tau | default_params_tau_same_scenarios | tau_gain | top1_gain |
| --- | --- | --- | --- | --- | --- |
| gptoss | Overall | 0.8974 | 0.5974 | 0.3000 | 0.1877 |
| gptoss | HVAC | 0.9429 | 0.9197 | 0.0232 | -0.0085 |
| gptoss | Appliance | 0.9672 | 0.1897 | 0.7774 | 0.4954 |
| gptoss | Shower | 0.7867 | 0.7889 | -0.0022 | 0.0067 |
| qwen | Overall | 0.8801 | 0.6410 | 0.2391 | 0.1377 |
| qwen | HVAC | 0.8813 | 0.9349 | -0.0536 | -0.0861 |
| qwen | Appliance | 0.9056 | 0.1897 | 0.7159 | 0.4369 |
| qwen | Shower | 0.8511 | 0.7889 | 0.0622 | 0.0733 |
| deepseek | Overall | 0.8973 | 0.6407 | 0.2567 | 0.1489 |
| deepseek | HVAC | 0.9198 | 0.9331 | -0.0134 | -0.0373 |
| deepseek | Appliance | 0.9754 | 0.1897 | 0.7856 | 0.4923 |
| deepseek | Shower | 0.7867 | 0.7889 | -0.0022 | -0.0067 |
| gemini | Overall | 0.9234 | 0.6410 | 0.2824 | 0.1723 |
| gemini | HVAC | 0.9771 | 0.9333 | 0.0438 | 0.0086 |
| gemini | Appliance | 0.9590 | 0.1897 | 0.7692 | 0.4769 |
| gemini | Shower | 0.8222 | 0.7889 | 0.0333 | 0.0333 |

## Alternative-order arm

Exact label-permutation test, pooled basis, over the 13 runs (5 shipped, 3 control, 5 reversed; shipped+control form the reference group). Separation is mean within-group agreement minus mean between-group agreement; p is the fraction of the 1287 relabelings matching or beating it. Floor p = 0.00078.

| model | n_reversed_runs | perm_choice_separation | perm_choice_p | perm_param_separation | perm_param_p | perm_n_relabelings |
| --- | --- | --- | --- | --- | --- | --- |
| gptoss | 5 | -0.0038 | 0.8462 | 0.0041 | 0.3023 | 1287 |
| qwen | 5 | -0.0012 | 0.6791 | 0.0543 | 0.0008 | 1287 |
| deepseek | 5 | -0.0042 | 0.9262 | -0.0158 | 0.4499 | 1287 |
| gemini | 5 | 0.0005 | 0.2354 | 0.0471 | 0.0008 | 1287 |

Descriptive agreement bands:

| model | within_shipped_choice_agreement_mean | within_reversed_choice_agreement_mean | between_choice_agreement_mean | within_shipped_param_identity_mean | within_reversed_param_identity_mean | between_param_identity_mean |
| --- | --- | --- | --- | --- | --- | --- |
| gptoss | 0.9278 | 0.9318 | 0.9342 | 0.3800 | 0.3782 | 0.3703 |
| qwen | 0.9526 | 0.9513 | 0.9521 | 0.5788 | 0.5651 | 0.5155 |
| deepseek | 0.9579 | 0.9836 | 0.9692 | 0.4230 | 0.6703 | 0.5163 |
| gemini | 0.9969 | 0.9959 | 0.9936 | 0.8497 | 0.8626 | 0.7996 |