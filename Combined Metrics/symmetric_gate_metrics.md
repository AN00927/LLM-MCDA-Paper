# Symmetric-gate metrics, S_int (P1.3)

Every architecture restricted to the scenarios all three completed, so the
arms are compared over one population rather than three.

- `S_int_strict` -- scored by all three architectures in **every** run
- `S_int_loose` -- scored by all three in **at least one** run each

Per plan D4 this is a supplement robustness check, not a headline
replacement. N is reported with every number.

## Gate sizes

| Model | Strict | Loose | of |
|---|---|---|---|
| deepseek | 193 | 195 | 195 |
| gemini | 195 | 195 | 195 |
| gptoss | 153 | 193 | 195 |
| qwen | 187 | 195 | 195 |

## Overall metrics under the strict gate

| Model | Arch | n all | n strict | tau all | tau strict | delta | Top-1 all | Top-1 strict | delta |
|---|---|---|---|---|---|---|---|---|---|
| deepseek | A_D | 195 | 193 | 0.1248 | 0.1233 | -0.0015 | 0.3908 | 0.3896 | -0.0012 |
| deepseek | A_E | 195 | 193 | 0.2533 | 0.2553 | +0.0020 | 0.4836 | 0.4870 | +0.0034 |
| deepseek | A_H | 195 | 193 | 0.8582 | 0.8577 | -0.0005 | 0.8880 | 0.8870 | -0.0010 |
| gemini | A_D | 195 | 195 | 0.1788 | 0.1788 | +0.0000 | 0.3979 | 0.3979 | +0.0000 |
| gemini | A_E | 195 | 195 | 0.2985 | 0.2985 | +0.0000 | 0.4749 | 0.4749 | +0.0000 |
| gemini | A_H | 195 | 195 | 0.8913 | 0.8913 | +0.0000 | 0.9015 | 0.9015 | +0.0000 |
| gptoss | A_D | 195 | 153 | 0.0325 | 0.0118 | -0.0207 | 0.3405 | 0.3294 | -0.0111 |
| gptoss | A_E | 195 | 153 | 0.2342 | 0.2227 | -0.0115 | 0.4646 | 0.4680 | +0.0034 |
| gptoss | A_H | 193 | 153 | 0.8819 | 0.8928 | +0.0109 | 0.9035 | 0.9163 | +0.0128 |
| qwen | A_D | 195 | 187 | 0.0055 | 0.0068 | +0.0013 | 0.3112 | 0.3112 | +0.0000 |
| qwen | A_E | 195 | 187 | 0.1474 | 0.1622 | +0.0148 | 0.4390 | 0.4513 | +0.0123 |
| qwen | A_H | 195 | 187 | 0.8359 | 0.8453 | +0.0094 | 0.8646 | 0.8706 | +0.0060 |
