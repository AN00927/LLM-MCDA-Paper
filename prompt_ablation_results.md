# Prompt-Sensitivity Ablation (A_D / A_E)

- Scenarios per cell: 195
- Runs per cell: 10
- Models: deepseek, gptoss, qwen
- Workers: 8

Note: A_E's shipped system prompt contains no per-criterion calibration anchors (RAG supplies scored exemplars instead), so for A_E the no_anchors arm is identical to control by construction and is skipped rather than billed twice.

## Summary (mean over runs; SD is run-to-run)

| variant | architecture | model | n_runs | kendall_tau | kendall_tau_sd | top1_accuracy | top1_accuracy_sd | mean_criterion_sd | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_anchors | AD | deepseek | 10 | 0.1474 | 0.0214 | 0.4582 | 0.0230 | 0.1553 | 0.9995 |
| no_anchors | AD | gptoss | 10 | 0.0993 | 0.0368 | 0.3679 | 0.0228 | 0.1510 | 0.9995 |
| no_anchors | AD | qwen | 10 | 0.0243 | 0.0397 | 0.3713 | 0.0290 | 0.1454 | 1.0000 |

## Per-run detail

| variant | architecture | model | run | n_scenarios | n_scored | kendall_tau | top1_accuracy | mean_criterion_sd | total_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_anchors | AD | deepseek | 1 | 195 | 195 | 0.1404 | 0.4513 | 0.1592 | 198151 |
| no_anchors | AD | deepseek | 2 | 195 | 195 | 0.1518 | 0.4308 | 0.1576 | 198146 |
| no_anchors | AD | deepseek | 3 | 195 | 195 | 0.1286 | 0.4462 | 0.1563 | 198068 |
| no_anchors | AD | deepseek | 4 | 195 | 195 | 0.1330 | 0.4410 | 0.1574 | 198149 |
| no_anchors | AD | deepseek | 5 | 195 | 195 | 0.1663 | 0.4769 | 0.1544 | 198145 |
| no_anchors | AD | deepseek | 6 | 195 | 195 | 0.1719 | 0.4821 | 0.1550 | 198027 |
| no_anchors | AD | deepseek | 7 | 195 | 195 | 0.1806 | 0.4821 | 0.1537 | 198017 |
| no_anchors | AD | deepseek | 8 | 195 | 194 | 0.1331 | 0.4742 | 0.1559 | 198075 |
| no_anchors | AD | deepseek | 9 | 195 | 195 | 0.1134 | 0.4205 | 0.1517 | 198028 |
| no_anchors | AD | deepseek | 10 | 195 | 195 | 0.1546 | 0.4769 | 0.1524 | 198045 |
| no_anchors | AD | gptoss | 1 | 195 | 194 | 0.0475 | 0.3351 | 0.1486 | 306767 |
| no_anchors | AD | gptoss | 2 | 195 | 195 | 0.1132 | 0.3744 | 0.1493 | 303777 |
| no_anchors | AD | gptoss | 3 | 195 | 195 | 0.1011 | 0.3590 | 0.1519 | 303348 |
| no_anchors | AD | gptoss | 4 | 195 | 195 | 0.1285 | 0.4000 | 0.1505 | 304923 |
| no_anchors | AD | gptoss | 5 | 195 | 195 | 0.1463 | 0.3590 | 0.1514 | 305771 |
| no_anchors | AD | gptoss | 6 | 195 | 195 | 0.1380 | 0.4000 | 0.1525 | 305834 |
| no_anchors | AD | gptoss | 7 | 195 | 195 | 0.0879 | 0.3795 | 0.1524 | 302976 |
| no_anchors | AD | gptoss | 8 | 195 | 195 | 0.0925 | 0.3538 | 0.1508 | 303512 |
| no_anchors | AD | gptoss | 9 | 195 | 195 | 0.1058 | 0.3795 | 0.1485 | 302045 |
| no_anchors | AD | gptoss | 10 | 195 | 195 | 0.0321 | 0.3385 | 0.1537 | 302403 |
| no_anchors | AD | qwen | 1 | 195 | 195 | -0.0183 | 0.3487 | 0.1443 | 213238 |
| no_anchors | AD | qwen | 2 | 195 | 195 | 0.0254 | 0.3641 | 0.1458 | 213100 |
| no_anchors | AD | qwen | 3 | 195 | 195 | 0.1035 | 0.4308 | 0.1449 | 213146 |
| no_anchors | AD | qwen | 4 | 195 | 195 | -0.0247 | 0.3487 | 0.1492 | 213208 |
| no_anchors | AD | qwen | 5 | 195 | 195 | 0.0510 | 0.3641 | 0.1462 | 213208 |
| no_anchors | AD | qwen | 6 | 195 | 195 | 0.0382 | 0.3949 | 0.1416 | 213266 |
| no_anchors | AD | qwen | 7 | 195 | 195 | 0.0080 | 0.3744 | 0.1461 | 213183 |
| no_anchors | AD | qwen | 8 | 195 | 195 | 0.0467 | 0.4000 | 0.1487 | 213204 |
| no_anchors | AD | qwen | 9 | 195 | 195 | -0.0197 | 0.3436 | 0.1452 | 213205 |
| no_anchors | AD | qwen | 10 | 195 | 195 | 0.0332 | 0.3436 | 0.1421 | 213166 |