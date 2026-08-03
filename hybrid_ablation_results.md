# AH Parameter-Provenance Ablation

Arms: true (ceiling) / extracted (actual) / order_reversed / default (floor).

| model | arm | n_scored | success_rate | kendall_tau | top1_accuracy | mae |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| deepseek | extracted | 195 | 1.0000 | 0.9043 | 0.9128 | 0.0411 |
| deepseek | extracted_per_run | 974 | 0.9990 | 0.8973 | 0.9076 | 0.0457 |
| deepseek | order_control | 585 | 1.0000 | 0.8974 | 0.9060 | 0.0472 |
| deepseek | order_reversed | 975 | 1.0000 | 0.9009 | 0.9097 | 0.0454 |
| deepseek | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |
| gemini | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| gemini | extracted | 195 | 1.0000 | 0.9214 | 0.9282 | 0.0469 |
| gemini | extracted_per_run | 975 | 1.0000 | 0.9234 | 0.9313 | 0.0475 |
| gemini | order_control | 585 | 1.0000 | 0.9293 | 0.9385 | 0.0452 |
| gemini | order_reversed | 975 | 1.0000 | 0.9262 | 0.9364 | 0.0465 |
| gemini | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |
| gptoss | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| gptoss | extracted | 194 | 0.9949 | 0.9210 | 0.9433 | 0.0463 |
| gptoss | extracted_per_run | 858 | 0.8800 | 0.8967 | 0.9161 | 0.0517 |
| gptoss | order_control | 514 | 0.8786 | 0.8988 | 0.9144 | 0.0516 |
| gptoss | order_reversed | 867 | 0.8892 | 0.8970 | 0.9077 | 0.0525 |
| gptoss | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |
| qwen | true_params | 195 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| qwen | extracted | 195 | 1.0000 | 0.8974 | 0.9128 | 0.0659 |
| qwen | extracted_per_run | 973 | 0.9979 | 0.8801 | 0.8972 | 0.0716 |
| qwen | order_control | 585 | 1.0000 | 0.8895 | 0.9077 | 0.0735 |
| qwen | order_reversed | 975 | 1.0000 | 0.8913 | 0.9036 | 0.0724 |
| qwen | default_params | 195 | 1.0000 | 0.6410 | 0.7692 | 0.1222 |

## Alternative-order arm

Exact label-permutation test, pooled basis, over the 13 runs (5 shipped, 3 control, 5 reversed; shipped+control form the reference group). Separation is mean within-group agreement minus mean between-group agreement; p is the fraction of the 1287 relabelings matching or beating it. Floor p = 0.00078.

| model | n_reversed_runs | perm_choice_separation | perm_choice_p | perm_param_separation | perm_param_p | perm_n_relabelings |
| --- | --- | --- | --- | --- | --- | --- |
| qwen | 5 | -0.0012 | 0.6791 | 0.0543 | 0.0008 | 1287 |
| gptoss | 5 | -0.0039 | 0.8384 | 0.0041 | 0.3023 | 1287 |
| deepseek | 5 | -0.0045 | 0.9534 | -0.0158 | 0.4499 | 1287 |
| gemini | 5 | 0.0005 | 0.2354 | 0.0471 | 0.0008 | 1287 |

Descriptive agreement bands:

| model | within_shipped_choice_agreement_mean | within_reversed_choice_agreement_mean | between_choice_agreement_mean | within_shipped_param_identity_mean | within_reversed_param_identity_mean | between_param_identity_mean |
| --- | --- | --- | --- | --- | --- | --- |
| qwen | 0.9526 | 0.9513 | 0.9521 | 0.5788 | 0.5651 | 0.5155 |
| gptoss | 0.9253 | 0.9305 | 0.9327 | 0.3800 | 0.3782 | 0.3703 |
| deepseek | 0.9563 | 0.9836 | 0.9682 | 0.4230 | 0.6703 | 0.5163 |
| gemini | 0.9969 | 0.9959 | 0.9936 | 0.8497 | 0.8626 | 0.7996 |