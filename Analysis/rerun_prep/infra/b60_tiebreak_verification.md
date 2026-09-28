# B60 tie-break verification

## RAG ablation (Analysis/RAG_Ablation/rag_ablation_results.xlsx)

Per-alternative rows examined: 7830
Predicted ranks changed by the TIE_BREAK_PRIORITY fix: 47
Scenario-cells with an old (stored) tau value: 2554
  old tau values outside {-1,-1/3,1/3,1}: 3 (example values: [np.float64(-0.816497), np.float64(0.0), np.float64(0.816497)])
Scenario-cells with a new (rank-based) tau value: 2610
  new tau values outside {-1,-1/3,1/3,1}: 0 (should be 0; values if any: [])

## Position-bias control (per-model Output Files*/position_bias/*_reversed_run_01.xlsx)

Output Files DeepSeek V4 Flash: checked
Output Files Gemini 3.5 Flash: checked
Output Files GPT-OSS 20B: checked
Output Files Qwen3.5 9B: checked
Scenarios checked across models: 533
Tau values outside {-1,-1/3,1/3,1}: 0 (expected 0)

## Prompt ablation

Historical file cell_control_AD_deepseek_run_01.xlsx: 194 scenario tau values stored, 4 distinct values outside {-1,-1/3,1/3,1} (confirms the pre-fix bug was real): [np.float64(-0.816497), np.float64(-0.5), np.float64(0.0), np.float64(0.816497)]
This file has no per-alternative score or rank columns, so the fixed code cannot be re-run against it (nothing to feed it). Verified instead by exercising the patched scenario_metrics() directly below.
Patched scenario_metrics() on 2 constructed cases (one with a genuine predicted weighted_score tie): tau values = [0.33333333333333337, 0.33333333333333337]
Values outside {-1,-1/3,1/3,1}: [] (expected empty list)