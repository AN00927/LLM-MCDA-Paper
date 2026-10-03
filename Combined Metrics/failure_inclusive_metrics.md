# Failure-inclusive metrics (P1.2), sensitivity analysis

**Not the headline.** The paper's headline applies the S4 failure rule
(failed = Top-1 wrong, tau 0, chance MAE, all scenarios in the denominator);
the `*_headline` columns of the xlsx hold it. `S_ok` below is scored-only
(sensitivity) and `S_all` is D2 chance imputation (Top-1 1/3), also a
sensitivity row.

D2 convention: each failed scenario receives the **chance value of its own
metric** -- tau 0, rho 0, Top-1 1/3, Top-2 2/3 (rho's chance value is
derived by direct enumeration over all 6 permutations of 3 items in the
script's `CHANCE` comment, not assumed). This is imputation at the metric
level, not the 0.5-at-criterion-score level used by
`generate_imputed_robustness_tables.py`; the two are different operations,
not two settings of one operation.

D1: the inclusive number **pairs with** the conditional number. Neither
replaces the other.

**Coverage gap:** MAE/RMSE are NOT reported here under any chance
convention. Error metrics have no principled chance value the way rank
metrics do (no null model has a defined expected MAE/RMSE the way a random
permutation has an expected tau/rho/top-k). An availability-inclusive MAE
is available only from `generate_imputed_robustness_tables.py`'s 0.5-at-
criterion-score convention, which is a different operation from this one.

## Overall

| Model | Arch | Failed/run | tau S_ok | tau S_all | delta | Top-1 S_ok | Top-1 S_all | delta |
|---|---|---|---|---|---|---|---|---|
| deepseek | A_D | 0.0 | 0.1248 | 0.1248 | +0.0000 | 0.3908 | 0.3908 | +0.0000 |
| gemini | A_D | 0.0 | 0.1788 | 0.1788 | +0.0000 | 0.3979 | 0.3979 | +0.0000 |
| gptoss | A_D | 0.0 | 0.0325 | 0.0325 | +0.0000 | 0.3405 | 0.3405 | +0.0000 |
| qwen | A_D | 2.2 | 0.0055 | 0.0055 | -0.0000 | 0.3112 | 0.3115 | +0.0003 |
| deepseek | A_E | 0.2 | 0.2533 | 0.2530 | -0.0003 | 0.4836 | 0.4834 | -0.0002 |
| gemini | A_E | 0.0 | 0.2985 | 0.2985 | +0.0000 | 0.4749 | 0.4749 | +0.0000 |
| gptoss | A_E | 0.0 | 0.2342 | 0.2342 | +0.0000 | 0.4646 | 0.4646 | +0.0000 |
| qwen | A_E | 0.0 | 0.1474 | 0.1474 | +0.0000 | 0.4390 | 0.4390 | +0.0000 |
| deepseek | A_H | 0.4 | 0.8582 | 0.8564 | -0.0018 | 0.8880 | 0.8868 | -0.0011 |
| gemini | A_H | 0.0 | 0.8913 | 0.8913 | +0.0000 | 0.9015 | 0.9015 | +0.0000 |
| gptoss | A_H | 17.0 | 0.8819 | 0.8048 | -0.0771 | 0.9035 | 0.8537 | -0.0499 |
| qwen | A_H | 0.0 | 0.8359 | 0.8359 | +0.0000 | 0.8646 | 0.8646 | +0.0000 |

## GPT-OSS A_H by decision type (concentrated-failure cell)

| Scope | n | Failed/run | tau S_ok | tau S_all | delta | Top-1 S_ok | Top-1 S_all | delta |
|---|---|---|---|---|---|---|---|---|
| Appliance | 65 | 0.0 | 0.9487 | 0.9487 | +0.0000 | 0.9631 | 0.9631 | +0.0000 |
| HVAC | 70 | 16.4 | 0.8589 | 0.6571 | -0.2018 | 0.8922 | 0.7610 | -0.1313 |
| Overall | 195 | 17.0 | 0.8819 | 0.8048 | -0.0771 | 0.9035 | 0.8537 | -0.0499 |
| Shower | 60 | 0.6 | 0.8294 | 0.8211 | -0.0083 | 0.8485 | 0.8433 | -0.0052 |

## Full coverage: every model x architecture x scope cell

One table per rank metric. Every row is per-model (no pooling across
models); `Overall` is the 195-scenario total, not a mean of the three
decision types.

### Kendall's tau

| Model | Arch | Scope | n | Failed/run (mean) | Failed/run (max) | kendall_tau S_ok | kendall_tau S_all | delta |
|---|---|---|---|---|---|---|---|---|
| deepseek | A_D | Appliance | 65 | 0.0 | 0 | 0.0421 | 0.0421 | +0.0000 |
| deepseek | A_D | HVAC | 70 | 0.0 | 0 | -0.1105 | -0.1105 | +0.0000 |
| deepseek | A_D | Overall | 195 | 0.0 | 0 | 0.1248 | 0.1248 | +0.0000 |
| deepseek | A_D | Shower | 60 | 0.0 | 0 | 0.4889 | 0.4889 | +0.0000 |
| gemini | A_D | Appliance | 65 | 0.0 | 0 | 0.1097 | 0.1097 | +0.0000 |
| gemini | A_D | HVAC | 70 | 0.0 | 0 | -0.2000 | -0.2000 | +0.0000 |
| gemini | A_D | Overall | 195 | 0.0 | 0 | 0.1788 | 0.1788 | +0.0000 |
| gemini | A_D | Shower | 60 | 0.0 | 0 | 0.6956 | 0.6956 | +0.0000 |
| gptoss | A_D | Appliance | 65 | 0.0 | 0 | -0.1138 | -0.1138 | +0.0000 |
| gptoss | A_D | HVAC | 70 | 0.0 | 0 | 0.0914 | 0.0914 | +0.0000 |
| gptoss | A_D | Overall | 195 | 0.0 | 0 | 0.0325 | 0.0325 | +0.0000 |
| gptoss | A_D | Shower | 60 | 0.0 | 0 | 0.1222 | 0.1222 | +0.0000 |
| qwen | A_D | Appliance | 65 | 0.0 | 0 | -0.0544 | -0.0544 | +0.0000 |
| qwen | A_D | HVAC | 70 | 2.2 | 3 | -0.0147 | -0.0143 | +0.0004 |
| qwen | A_D | Overall | 195 | 2.2 | 3 | 0.0055 | 0.0055 | -0.0000 |
| qwen | A_D | Shower | 60 | 0.0 | 0 | 0.0933 | 0.0933 | +0.0000 |
| deepseek | A_E | Appliance | 65 | 0.2 | 1 | 0.2879 | 0.2872 | -0.0007 |
| deepseek | A_E | HVAC | 70 | 0.0 | 0 | 0.0305 | 0.0305 | +0.0000 |
| deepseek | A_E | Overall | 195 | 0.2 | 1 | 0.2533 | 0.2530 | -0.0003 |
| deepseek | A_E | Shower | 60 | 0.0 | 0 | 0.4756 | 0.4756 | +0.0000 |
| gemini | A_E | Appliance | 65 | 0.0 | 0 | 0.3026 | 0.3026 | +0.0000 |
| gemini | A_E | HVAC | 70 | 0.0 | 0 | -0.1181 | -0.1181 | +0.0000 |
| gemini | A_E | Overall | 195 | 0.0 | 0 | 0.2985 | 0.2985 | +0.0000 |
| gemini | A_E | Shower | 60 | 0.0 | 0 | 0.7800 | 0.7800 | +0.0000 |
| gptoss | A_E | Appliance | 65 | 0.0 | 0 | -0.0728 | -0.0728 | +0.0000 |
| gptoss | A_E | HVAC | 70 | 0.0 | 0 | 0.2019 | 0.2019 | +0.0000 |
| gptoss | A_E | Overall | 195 | 0.0 | 0 | 0.2342 | 0.2342 | +0.0000 |
| gptoss | A_E | Shower | 60 | 0.0 | 0 | 0.6044 | 0.6044 | +0.0000 |
| qwen | A_E | Appliance | 65 | 0.0 | 0 | 0.1487 | 0.1487 | +0.0000 |
| qwen | A_E | HVAC | 70 | 0.0 | 0 | 0.0590 | 0.0590 | +0.0000 |
| qwen | A_E | Overall | 195 | 0.0 | 0 | 0.1474 | 0.1474 | +0.0000 |
| qwen | A_E | Shower | 60 | 0.0 | 0 | 0.2489 | 0.2489 | +0.0000 |
| deepseek | A_H | Appliance | 65 | 0.0 | 0 | 0.9467 | 0.9467 | +0.0000 |
| deepseek | A_H | HVAC | 70 | 0.4 | 1 | 0.7950 | 0.7905 | -0.0046 |
| deepseek | A_H | Overall | 195 | 0.4 | 1 | 0.8582 | 0.8564 | -0.0018 |
| deepseek | A_H | Shower | 60 | 0.0 | 0 | 0.8356 | 0.8356 | +0.0000 |
| gemini | A_H | Appliance | 65 | 0.0 | 0 | 0.9446 | 0.9446 | +0.0000 |
| gemini | A_H | HVAC | 70 | 0.0 | 0 | 0.8724 | 0.8724 | +0.0000 |
| gemini | A_H | Overall | 195 | 0.0 | 0 | 0.8913 | 0.8913 | +0.0000 |
| gemini | A_H | Shower | 60 | 0.0 | 0 | 0.8556 | 0.8556 | +0.0000 |
| gptoss | A_H | Appliance | 65 | 0.0 | 0 | 0.9487 | 0.9487 | +0.0000 |
| gptoss | A_H | HVAC | 70 | 16.4 | 19 | 0.8589 | 0.6571 | -0.2018 |
| gptoss | A_H | Overall | 195 | 17.0 | 19 | 0.8819 | 0.8048 | -0.0771 |
| gptoss | A_H | Shower | 60 | 0.6 | 1 | 0.8294 | 0.8211 | -0.0083 |
| qwen | A_H | Appliance | 65 | 0.0 | 0 | 0.9077 | 0.9077 | +0.0000 |
| qwen | A_H | HVAC | 70 | 0.0 | 0 | 0.7543 | 0.7543 | +0.0000 |
| qwen | A_H | Overall | 195 | 0.0 | 0 | 0.8359 | 0.8359 | +0.0000 |
| qwen | A_H | Shower | 60 | 0.0 | 0 | 0.8533 | 0.8533 | +0.0000 |

### Spearman's rho

| Model | Arch | Scope | n | Failed/run (mean) | Failed/run (max) | spearman_rho S_ok | spearman_rho S_all | delta |
|---|---|---|---|---|---|---|---|---|
| deepseek | A_D | Appliance | 65 | 0.0 | 0 | 0.0369 | 0.0369 | +0.0000 |
| deepseek | A_D | HVAC | 70 | 0.0 | 0 | -0.1200 | -0.1200 | +0.0000 |
| deepseek | A_D | Overall | 195 | 0.0 | 0 | 0.1313 | 0.1313 | +0.0000 |
| deepseek | A_D | Shower | 60 | 0.0 | 0 | 0.5267 | 0.5267 | +0.0000 |
| gemini | A_D | Appliance | 65 | 0.0 | 0 | 0.0785 | 0.0785 | +0.0000 |
| gemini | A_D | HVAC | 70 | 0.0 | 0 | -0.1771 | -0.1771 | +0.0000 |
| gemini | A_D | Overall | 195 | 0.0 | 0 | 0.1836 | 0.1836 | +0.0000 |
| gemini | A_D | Shower | 60 | 0.0 | 0 | 0.7183 | 0.7183 | +0.0000 |
| gptoss | A_D | Appliance | 65 | 0.0 | 0 | -0.1215 | -0.1215 | +0.0000 |
| gptoss | A_D | HVAC | 70 | 0.0 | 0 | 0.1114 | 0.1114 | +0.0000 |
| gptoss | A_D | Overall | 195 | 0.0 | 0 | 0.0379 | 0.0379 | +0.0000 |
| gptoss | A_D | Shower | 60 | 0.0 | 0 | 0.1250 | 0.1250 | +0.0000 |
| qwen | A_D | Appliance | 65 | 0.0 | 0 | -0.0646 | -0.0646 | +0.0000 |
| qwen | A_D | HVAC | 70 | 2.2 | 3 | -0.0221 | -0.0214 | +0.0007 |
| qwen | A_D | Overall | 195 | 2.2 | 3 | -0.0006 | -0.0005 | +0.0001 |
| qwen | A_D | Shower | 60 | 0.0 | 0 | 0.0933 | 0.0933 | +0.0000 |
| deepseek | A_E | Appliance | 65 | 0.2 | 1 | 0.3131 | 0.3123 | -0.0008 |
| deepseek | A_E | HVAC | 70 | 0.0 | 0 | 0.0243 | 0.0243 | +0.0000 |
| deepseek | A_E | Overall | 195 | 0.2 | 1 | 0.2695 | 0.2692 | -0.0003 |
| deepseek | A_E | Shower | 60 | 0.0 | 0 | 0.5083 | 0.5083 | +0.0000 |
| gemini | A_E | Appliance | 65 | 0.0 | 0 | 0.3200 | 0.3200 | +0.0000 |
| gemini | A_E | HVAC | 70 | 0.0 | 0 | -0.0929 | -0.0929 | +0.0000 |
| gemini | A_E | Overall | 195 | 0.0 | 0 | 0.3210 | 0.3210 | +0.0000 |
| gemini | A_E | Shower | 60 | 0.0 | 0 | 0.8050 | 0.8050 | +0.0000 |
| gptoss | A_E | Appliance | 65 | 0.0 | 0 | -0.0815 | -0.0815 | +0.0000 |
| gptoss | A_E | HVAC | 70 | 0.0 | 0 | 0.2171 | 0.2171 | +0.0000 |
| gptoss | A_E | Overall | 195 | 0.0 | 0 | 0.2508 | 0.2508 | +0.0000 |
| gptoss | A_E | Shower | 60 | 0.0 | 0 | 0.6500 | 0.6500 | +0.0000 |
| qwen | A_E | Appliance | 65 | 0.0 | 0 | 0.1692 | 0.1692 | +0.0000 |
| qwen | A_E | HVAC | 70 | 0.0 | 0 | 0.0614 | 0.0614 | +0.0000 |
| qwen | A_E | Overall | 195 | 0.0 | 0 | 0.1590 | 0.1590 | +0.0000 |
| qwen | A_E | Shower | 60 | 0.0 | 0 | 0.2617 | 0.2617 | +0.0000 |
| deepseek | A_H | Appliance | 65 | 0.0 | 0 | 0.9600 | 0.9600 | +0.0000 |
| deepseek | A_H | HVAC | 70 | 0.4 | 1 | 0.8176 | 0.8129 | -0.0047 |
| deepseek | A_H | Overall | 195 | 0.4 | 1 | 0.8762 | 0.8744 | -0.0018 |
| deepseek | A_H | Shower | 60 | 0.0 | 0 | 0.8533 | 0.8533 | +0.0000 |
| gemini | A_H | Appliance | 65 | 0.0 | 0 | 0.9585 | 0.9585 | +0.0000 |
| gemini | A_H | HVAC | 70 | 0.0 | 0 | 0.8886 | 0.8886 | +0.0000 |
| gemini | A_H | Overall | 195 | 0.0 | 0 | 0.9077 | 0.9077 | +0.0000 |
| gemini | A_H | Shower | 60 | 0.0 | 0 | 0.8750 | 0.8750 | +0.0000 |
| gptoss | A_H | Appliance | 65 | 0.0 | 0 | 0.9615 | 0.9615 | +0.0000 |
| gptoss | A_H | HVAC | 70 | 16.4 | 19 | 0.8850 | 0.6771 | -0.2078 |
| gptoss | A_H | Overall | 195 | 17.0 | 19 | 0.8979 | 0.8195 | -0.0784 |
| gptoss | A_H | Shower | 60 | 0.6 | 1 | 0.8401 | 0.8317 | -0.0084 |
| qwen | A_H | Appliance | 65 | 0.0 | 0 | 0.9185 | 0.9185 | +0.0000 |
| qwen | A_H | HVAC | 70 | 0.0 | 0 | 0.7829 | 0.7829 | +0.0000 |
| qwen | A_H | Overall | 195 | 0.0 | 0 | 0.8518 | 0.8518 | +0.0000 |
| qwen | A_H | Shower | 60 | 0.0 | 0 | 0.8600 | 0.8600 | +0.0000 |

### Top-1 accuracy

| Model | Arch | Scope | n | Failed/run (mean) | Failed/run (max) | top1_accuracy S_ok | top1_accuracy S_all | delta |
|---|---|---|---|---|---|---|---|---|
| deepseek | A_D | Appliance | 65 | 0.0 | 0 | 0.3538 | 0.3538 | +0.0000 |
| deepseek | A_D | HVAC | 70 | 0.0 | 0 | 0.2600 | 0.2600 | +0.0000 |
| deepseek | A_D | Overall | 195 | 0.0 | 0 | 0.3908 | 0.3908 | +0.0000 |
| deepseek | A_D | Shower | 60 | 0.0 | 0 | 0.5833 | 0.5833 | +0.0000 |
| gemini | A_D | Appliance | 65 | 0.0 | 0 | 0.3631 | 0.3631 | +0.0000 |
| gemini | A_D | HVAC | 70 | 0.0 | 0 | 0.1914 | 0.1914 | +0.0000 |
| gemini | A_D | Overall | 195 | 0.0 | 0 | 0.3979 | 0.3979 | +0.0000 |
| gemini | A_D | Shower | 60 | 0.0 | 0 | 0.6767 | 0.6767 | +0.0000 |
| gptoss | A_D | Appliance | 65 | 0.0 | 0 | 0.3385 | 0.3385 | +0.0000 |
| gptoss | A_D | HVAC | 70 | 0.0 | 0 | 0.3457 | 0.3457 | +0.0000 |
| gptoss | A_D | Overall | 195 | 0.0 | 0 | 0.3405 | 0.3405 | +0.0000 |
| gptoss | A_D | Shower | 60 | 0.0 | 0 | 0.3367 | 0.3367 | +0.0000 |
| qwen | A_D | Appliance | 65 | 0.0 | 0 | 0.2462 | 0.2462 | +0.0000 |
| qwen | A_D | HVAC | 70 | 2.2 | 3 | 0.3038 | 0.3048 | +0.0009 |
| qwen | A_D | Overall | 195 | 2.2 | 3 | 0.3112 | 0.3115 | +0.0003 |
| qwen | A_D | Shower | 60 | 0.0 | 0 | 0.3900 | 0.3900 | +0.0000 |
| deepseek | A_E | Appliance | 65 | 0.2 | 1 | 0.6019 | 0.6010 | -0.0008 |
| deepseek | A_E | HVAC | 70 | 0.0 | 0 | 0.2971 | 0.2971 | +0.0000 |
| deepseek | A_E | Overall | 195 | 0.2 | 1 | 0.4836 | 0.4834 | -0.0002 |
| deepseek | A_E | Shower | 60 | 0.0 | 0 | 0.5733 | 0.5733 | +0.0000 |
| gemini | A_E | Appliance | 65 | 0.0 | 0 | 0.5446 | 0.5446 | +0.0000 |
| gemini | A_E | HVAC | 70 | 0.0 | 0 | 0.1514 | 0.1514 | +0.0000 |
| gemini | A_E | Overall | 195 | 0.0 | 0 | 0.4749 | 0.4749 | +0.0000 |
| gemini | A_E | Shower | 60 | 0.0 | 0 | 0.7767 | 0.7767 | +0.0000 |
| gptoss | A_E | Appliance | 65 | 0.0 | 0 | 0.3262 | 0.3262 | +0.0000 |
| gptoss | A_E | HVAC | 70 | 0.0 | 0 | 0.4029 | 0.4029 | +0.0000 |
| gptoss | A_E | Overall | 195 | 0.0 | 0 | 0.4646 | 0.4646 | +0.0000 |
| gptoss | A_E | Shower | 60 | 0.0 | 0 | 0.6867 | 0.6867 | +0.0000 |
| qwen | A_E | Appliance | 65 | 0.0 | 0 | 0.4738 | 0.4738 | +0.0000 |
| qwen | A_E | HVAC | 70 | 0.0 | 0 | 0.3543 | 0.3543 | +0.0000 |
| qwen | A_E | Overall | 195 | 0.0 | 0 | 0.4390 | 0.4390 | +0.0000 |
| qwen | A_E | Shower | 60 | 0.0 | 0 | 0.5000 | 0.5000 | +0.0000 |
| deepseek | A_H | Appliance | 65 | 0.0 | 0 | 0.9692 | 0.9692 | +0.0000 |
| deepseek | A_H | HVAC | 70 | 0.4 | 1 | 0.8477 | 0.8448 | -0.0030 |
| deepseek | A_H | Overall | 195 | 0.4 | 1 | 0.8880 | 0.8868 | -0.0011 |
| deepseek | A_H | Shower | 60 | 0.0 | 0 | 0.8467 | 0.8467 | +0.0000 |
| gemini | A_H | Appliance | 65 | 0.0 | 0 | 0.9538 | 0.9538 | +0.0000 |
| gemini | A_H | HVAC | 70 | 0.0 | 0 | 0.8829 | 0.8829 | +0.0000 |
| gemini | A_H | Overall | 195 | 0.0 | 0 | 0.9015 | 0.9015 | +0.0000 |
| gemini | A_H | Shower | 60 | 0.0 | 0 | 0.8667 | 0.8667 | +0.0000 |
| gptoss | A_H | Appliance | 65 | 0.0 | 0 | 0.9631 | 0.9631 | +0.0000 |
| gptoss | A_H | HVAC | 70 | 16.4 | 19 | 0.8922 | 0.7610 | -0.1313 |
| gptoss | A_H | Overall | 195 | 17.0 | 19 | 0.9035 | 0.8537 | -0.0499 |
| gptoss | A_H | Shower | 60 | 0.6 | 1 | 0.8485 | 0.8433 | -0.0052 |
| qwen | A_H | Appliance | 65 | 0.0 | 0 | 0.9385 | 0.9385 | +0.0000 |
| qwen | A_H | HVAC | 70 | 0.0 | 0 | 0.7743 | 0.7743 | +0.0000 |
| qwen | A_H | Overall | 195 | 0.0 | 0 | 0.8646 | 0.8646 | +0.0000 |
| qwen | A_H | Shower | 60 | 0.0 | 0 | 0.8900 | 0.8900 | +0.0000 |

### Top-2 accuracy

| Model | Arch | Scope | n | Failed/run (mean) | Failed/run (max) | top2_accuracy S_ok | top2_accuracy S_all | delta |
|---|---|---|---|---|---|---|---|---|
| deepseek | A_D | Appliance | 65 | 0.0 | 0 | 0.6769 | 0.6769 | +0.0000 |
| deepseek | A_D | HVAC | 70 | 0.0 | 0 | 0.6400 | 0.6400 | +0.0000 |
| deepseek | A_D | Overall | 195 | 0.0 | 0 | 0.7292 | 0.7292 | +0.0000 |
| deepseek | A_D | Shower | 60 | 0.0 | 0 | 0.8900 | 0.8900 | +0.0000 |
| gemini | A_D | Appliance | 65 | 0.0 | 0 | 0.6892 | 0.6892 | +0.0000 |
| gemini | A_D | HVAC | 70 | 0.0 | 0 | 0.5229 | 0.5229 | +0.0000 |
| gemini | A_D | Overall | 195 | 0.0 | 0 | 0.7026 | 0.7026 | +0.0000 |
| gemini | A_D | Shower | 60 | 0.0 | 0 | 0.9267 | 0.9267 | +0.0000 |
| gptoss | A_D | Appliance | 65 | 0.0 | 0 | 0.6092 | 0.6092 | +0.0000 |
| gptoss | A_D | HVAC | 70 | 0.0 | 0 | 0.7171 | 0.7171 | +0.0000 |
| gptoss | A_D | Overall | 195 | 0.0 | 0 | 0.6656 | 0.6656 | +0.0000 |
| gptoss | A_D | Shower | 60 | 0.0 | 0 | 0.6667 | 0.6667 | +0.0000 |
| qwen | A_D | Appliance | 65 | 0.0 | 0 | 0.6831 | 0.6831 | +0.0000 |
| qwen | A_D | HVAC | 70 | 2.2 | 3 | 0.6371 | 0.6381 | +0.0010 |
| qwen | A_D | Overall | 195 | 2.2 | 3 | 0.6722 | 0.6721 | -0.0000 |
| qwen | A_D | Shower | 60 | 0.0 | 0 | 0.7000 | 0.7000 | +0.0000 |
| deepseek | A_E | Appliance | 65 | 0.2 | 1 | 0.8425 | 0.8421 | -0.0004 |
| deepseek | A_E | HVAC | 70 | 0.0 | 0 | 0.7171 | 0.7171 | +0.0000 |
| deepseek | A_E | Overall | 195 | 0.2 | 1 | 0.8173 | 0.8171 | -0.0002 |
| deepseek | A_E | Shower | 60 | 0.0 | 0 | 0.9067 | 0.9067 | +0.0000 |
| gemini | A_E | Appliance | 65 | 0.0 | 0 | 0.7908 | 0.7908 | +0.0000 |
| gemini | A_E | HVAC | 70 | 0.0 | 0 | 0.5857 | 0.5857 | +0.0000 |
| gemini | A_E | Overall | 195 | 0.0 | 0 | 0.7713 | 0.7713 | +0.0000 |
| gemini | A_E | Shower | 60 | 0.0 | 0 | 0.9667 | 0.9667 | +0.0000 |
| gptoss | A_E | Appliance | 65 | 0.0 | 0 | 0.6123 | 0.6123 | +0.0000 |
| gptoss | A_E | HVAC | 70 | 0.0 | 0 | 0.7629 | 0.7629 | +0.0000 |
| gptoss | A_E | Overall | 195 | 0.0 | 0 | 0.7631 | 0.7631 | +0.0000 |
| gptoss | A_E | Shower | 60 | 0.0 | 0 | 0.9267 | 0.9267 | +0.0000 |
| qwen | A_E | Appliance | 65 | 0.0 | 0 | 0.7477 | 0.7477 | +0.0000 |
| qwen | A_E | HVAC | 70 | 0.0 | 0 | 0.7457 | 0.7457 | +0.0000 |
| qwen | A_E | Overall | 195 | 0.0 | 0 | 0.7395 | 0.7395 | +0.0000 |
| qwen | A_E | Shower | 60 | 0.0 | 0 | 0.7233 | 0.7233 | +0.0000 |
| deepseek | A_H | Appliance | 65 | 0.0 | 0 | 1.0000 | 1.0000 | +0.0000 |
| deepseek | A_H | HVAC | 70 | 0.4 | 1 | 0.9454 | 0.9438 | -0.0016 |
| deepseek | A_H | Overall | 195 | 0.4 | 1 | 0.9671 | 0.9665 | -0.0006 |
| deepseek | A_H | Shower | 60 | 0.0 | 0 | 0.9567 | 0.9567 | +0.0000 |
| gemini | A_H | Appliance | 65 | 0.0 | 0 | 1.0000 | 1.0000 | +0.0000 |
| gemini | A_H | HVAC | 70 | 0.0 | 0 | 0.9714 | 0.9714 | +0.0000 |
| gemini | A_H | Overall | 195 | 0.0 | 0 | 0.9795 | 0.9795 | +0.0000 |
| gemini | A_H | Shower | 60 | 0.0 | 0 | 0.9667 | 0.9667 | +0.0000 |
| gptoss | A_H | Appliance | 65 | 0.0 | 0 | 1.0000 | 1.0000 | +0.0000 |
| gptoss | A_H | HVAC | 70 | 16.4 | 19 | 0.9890 | 0.9133 | -0.0757 |
| gptoss | A_H | Overall | 195 | 17.0 | 19 | 0.9787 | 0.9515 | -0.0273 |
| gptoss | A_H | Shower | 60 | 0.6 | 1 | 0.9462 | 0.9433 | -0.0028 |
| qwen | A_H | Appliance | 65 | 0.0 | 0 | 0.9877 | 0.9877 | +0.0000 |
| qwen | A_H | HVAC | 70 | 0.0 | 0 | 0.9371 | 0.9371 | +0.0000 |
| qwen | A_H | Overall | 195 | 0.0 | 0 | 0.9600 | 0.9600 | +0.0000 |
| qwen | A_H | Shower | 60 | 0.0 | 0 | 0.9567 | 0.9567 | +0.0000 |
