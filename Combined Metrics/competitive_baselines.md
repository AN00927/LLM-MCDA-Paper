# P1.5 - competitive baselines

Estimator: per-run mean, then mean across runs (aggregation A, decision D6).
FixedDefault and the single-criterion baselines are deterministic and
model-independent; they are repeated against each model for comparison.

## A_E vs FixedDefault, per model and decision type

| Model | Decision type | A_E tau | FD tau | d tau | A_E Top-1 | FD Top-1 | d Top-1 |
|---|---|---|---|---|---|---|---|
| deepseek | Overall | 0.2530 | 0.5795 | -0.3265 | 0.4831 | 0.6359 | -0.1528 |
| deepseek | HVAC | 0.0305 | 0.7905 | -0.7600 | 0.2972 | 0.7714 | -0.4742 |
| deepseek | Appliance | 0.2872 | 0.1795 | +0.1077 | 0.6000 | 0.3231 | +0.2769 |
| deepseek | Shower | 0.4756 | 0.7667 | -0.2911 | 0.5734 | 0.8167 | -0.2433 |
| gemini | Overall | 0.2985 | 0.5795 | -0.2810 | 0.4749 | 0.6359 | -0.1610 |
| gemini | HVAC | -0.1181 | 0.7905 | -0.9086 | 0.1514 | 0.7714 | -0.6200 |
| gemini | Appliance | 0.3026 | 0.1795 | +0.1231 | 0.5446 | 0.3231 | +0.2215 |
| gemini | Shower | 0.7800 | 0.7667 | +0.0133 | 0.7767 | 0.8167 | -0.0400 |
| gptoss | Overall | 0.2342 | 0.5795 | -0.3453 | 0.4646 | 0.6359 | -0.1713 |
| gptoss | HVAC | 0.2019 | 0.7905 | -0.5886 | 0.4029 | 0.7714 | -0.3685 |
| gptoss | Appliance | -0.0728 | 0.1795 | -0.2523 | 0.3262 | 0.3231 | +0.0031 |
| gptoss | Shower | 0.6044 | 0.7667 | -0.1623 | 0.6867 | 0.8167 | -0.1300 |
| qwen | Overall | 0.1474 | 0.5795 | -0.4321 | 0.4390 | 0.6359 | -0.1969 |
| qwen | HVAC | 0.0590 | 0.7905 | -0.7315 | 0.3543 | 0.7714 | -0.4171 |
| qwen | Appliance | 0.1487 | 0.1795 | -0.0308 | 0.4738 | 0.3231 | +0.1507 |
| qwen | Shower | 0.2489 | 0.7667 | -0.5178 | 0.5000 | 0.8167 | -0.3167 |

**A_E beats FixedDefault in 3 of 16 cells on tau and 4 of 16 on Top-1.**

## A_E vs the NearestNeighbor copy baseline (k = 1), per model and decision type

| Model | Decision type | A_E tau | NN tau | d tau | A_E Top-1 | NN Top-1 | d Top-1 |
|---|---|---|---|---|---|---|---|
| deepseek | Overall | 0.2530 | 0.3744 | -0.1214 | 0.4831 | 0.6462 | -0.1631 |
| deepseek | HVAC | 0.0305 | 0.1810 | -0.1505 | 0.2972 | 0.5143 | -0.2171 |
| deepseek | Appliance | 0.2872 | 0.4667 | -0.1795 | 0.6000 | 0.7231 | -0.1231 |
| deepseek | Shower | 0.4756 | 0.5000 | -0.0244 | 0.5734 | 0.7167 | -0.1433 |
| gemini | Overall | 0.2985 | 0.3744 | -0.0759 | 0.4749 | 0.6462 | -0.1713 |
| gemini | HVAC | -0.1181 | 0.1810 | -0.2991 | 0.1514 | 0.5143 | -0.3629 |
| gemini | Appliance | 0.3026 | 0.4667 | -0.1641 | 0.5446 | 0.7231 | -0.1785 |
| gemini | Shower | 0.7800 | 0.5000 | +0.2800 | 0.7767 | 0.7167 | +0.0600 |
| gptoss | Overall | 0.2342 | 0.3744 | -0.1402 | 0.4646 | 0.6462 | -0.1816 |
| gptoss | HVAC | 0.2019 | 0.1810 | +0.0209 | 0.4029 | 0.5143 | -0.1114 |
| gptoss | Appliance | -0.0728 | 0.4667 | -0.5395 | 0.3262 | 0.7231 | -0.3969 |
| gptoss | Shower | 0.6044 | 0.5000 | +0.1044 | 0.6867 | 0.7167 | -0.0300 |
| qwen | Overall | 0.1474 | 0.3744 | -0.2270 | 0.4390 | 0.6462 | -0.2072 |
| qwen | HVAC | 0.0590 | 0.1810 | -0.1220 | 0.3543 | 0.5143 | -0.1600 |
| qwen | Appliance | 0.1487 | 0.4667 | -0.3180 | 0.4738 | 0.7231 | -0.2493 |
| qwen | Shower | 0.2489 | 0.5000 | -0.2511 | 0.5000 | 0.7167 | -0.2167 |

## Paired Wilcoxon, A_E vs each baseline (per model; Holm over all 16 tests)

| Model | Baseline | Metric | A_E | Baseline | diff | n pairs | n non-zero | p | p Holm | rank-biserial |
|---|---|---|---|---|---|---|---|---|---|---|
| gptoss | FixedDefault | tau | 0.2342 | 0.5795 | -0.3453 | 195 | 174 | 1.04e-10 | 1.56e-09 | -0.564 |
| gptoss | FixedDefault | Top-1 | 0.4646 | 0.6359 | -0.1713 | 195 | 144 | 0.000179 | 0.00125 | -0.358 |
| gptoss | NearestNeighbor | tau | 0.2342 | 0.3744 | -0.1402 | 195 | 172 | 0.0253 | 0.0506 | -0.197 |
| gptoss | NearestNeighbor | Top-1 | 0.4646 | 0.6462 | -0.1815 | 195 | 147 | 4e-05 | 0.00032 | -0.388 |
| qwen | FixedDefault | tau | 0.1474 | 0.5795 | -0.4321 | 195 | 185 | 1.6e-12 | 2.56e-11 | -0.598 |
| qwen | FixedDefault | Top-1 | 0.4390 | 0.6359 | -0.1969 | 195 | 167 | 3.55e-05 | 0.000319 | -0.367 |
| qwen | NearestNeighbor | tau | 0.1474 | 0.3744 | -0.2270 | 195 | 183 | 1.66e-05 | 0.000199 | -0.367 |
| qwen | NearestNeighbor | Top-1 | 0.4390 | 0.6462 | -0.2072 | 195 | 160 | 1.87e-06 | 2.43e-05 | -0.433 |
| deepseek | FixedDefault | tau | 0.2530 | 0.5795 | -0.3265 | 195 | 178 | 2.54e-09 | 3.55e-08 | -0.515 |
| deepseek | FixedDefault | Top-1 | 0.4831 | 0.6359 | -0.1528 | 195 | 164 | 0.00328 | 0.0131 | -0.263 |
| deepseek | NearestNeighbor | tau | 0.2530 | 0.3744 | -0.1214 | 195 | 166 | 0.00709 | 0.0213 | -0.241 |
| deepseek | NearestNeighbor | Top-1 | 0.4831 | 0.6462 | -0.1631 | 195 | 137 | 2.73e-05 | 0.000273 | -0.411 |
| gemini | FixedDefault | tau | 0.2985 | 0.5795 | -0.2810 | 195 | 137 | 2.01e-05 | 0.000221 | -0.418 |
| gemini | FixedDefault | Top-1 | 0.4749 | 0.6359 | -0.1610 | 195 | 114 | 0.00163 | 0.00816 | -0.323 |
| gemini | NearestNeighbor | tau | 0.2985 | 0.3744 | -0.0759 | 195 | 132 | 0.216 | 0.216 | -0.124 |
| gemini | NearestNeighbor | Top-1 | 0.4749 | 0.6462 | -0.1713 | 195 | 96 | 0.000252 | 0.00151 | -0.413 |

## Single-criterion argmax baseline, per decision type

| Decision type | n | Criterion | tau | Top-1 |
|---|---|---|---|---|
| HVAC | 70 | energy_cost | -0.1714 | 0.1429 |
| HVAC | 70 | environmental | -0.1714 | 0.1429 |
| HVAC | 70 | comfort | 0.6143 | 0.7857 |
| HVAC | 70 | practicality | 0.1667 | 0.3690 |
| Appliance | 65 | energy_cost | 0.0359 | 0.4026 |
| Appliance | 65 | environmental | -0.0615 | 0.3231 |
| Appliance | 65 | comfort | 0.7949 | 0.8769 |
| Appliance | 65 | practicality | 0.7897 | 0.8615 |
| Shower | 60 | energy_cost | 0.6889 | 0.7222 |
| Shower | 60 | environmental | 0.6889 | 0.7306 |
| Shower | 60 | comfort | -0.1778 | 0.1917 |
| Shower | 60 | practicality | -0.3500 | 0.2083 |

## Strongest single criterion per decision type

| Decision type | Criterion | tau | Top-1 |
|---|---|---|---|
| Appliance | comfort | 0.7949 | 0.8769 |
| HVAC | comfort | 0.6143 | 0.7857 |
| Shower | environmental | 0.6889 | 0.7306 |
