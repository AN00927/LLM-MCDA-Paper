# Task 1: All .tex Edits — Update Paper with Final Results

## File to Edit

`paper/paper_draft_working.tex` (876 lines, in `/mnt/c/Users/Ahaan/LLM-MCDA Paper/`)

## Pooled Data to Use (4-model average: GPT-OSS 20B, Qwen 3.5 9B, DeepSeek V4 Flash, Gemini 3.5 Flash)

### Overall Metrics (5-run mean, 195 scenarios)
| Metric | Pure Prompting | RAG-Enhanced | LLM-Parameterized_Reference_Scoring |
|--------|---------------|-------------|-----------------------------------|
| Kendall's tau | 0.095 | 0.339 | 0.902 |
| Spearman's rho | 0.097 | 0.369 | 0.912 |
| Top-1 Accuracy (%) | 35.4 | 51.7 | 91.7 |
| Top-2 Accuracy (%) | 67.7 | 80.9 | 97.8 |
| Overall MAE | 0.219 | 0.138 | 0.051 |
| Overall RMSE | 0.283 | 0.201 | 0.105 |

### Per-Criterion MAE (pooled)
| Criterion | Pure | RAG | LLM-Parameterized_Reference_Scoring |
|-----------|------|-----|-----|
| Energy Cost | 0.240 | 0.147 | 0.077 |
| Environmental | 0.260 | 0.141 | 0.098 |
| Comfort | 0.171 | 0.134 | 0.010 |
| Practicality | 0.206 | 0.129 | 0.020 |

### Per-Decision-Type Kendall's tau (pooled)
| Decision Type | Pure | RAG | LLM-Parameterized_Reference_Scoring |
|---------------|------|-----|-----|
| HVAC | 0.031 | 0.107 | 0.936 |
| Appliance | -0.100 | 0.282 | 0.944 |
| Shower | 0.381 | 0.669 | 0.817 |

### Per-Decision-Type Top-1 / Top-2 Accuracies (pooled)
HVAC: Pure 32.5/68.9, RAG 33.6/70.4, LLM-Parameterized_Reference_Scoring 92.5/98.9
Appliance: Pure 25.8/55.4, RAG 53.8/80.8, LLM-Parameterized_Reference_Scoring 96.9/99.2
Shower: Pure 49.2/79.6, RAG 70.4/93.3, LLM-Parameterized_Reference_Scoring 85.4/95.0

### Per-Decision-Type MAE (pooled)
HVAC: Pure 0.204, RAG 0.152, LLM-Parameterized_Reference_Scoring 0.042
Appliance: Pure 0.269, RAG 0.152, LLM-Parameterized_Reference_Scoring 0.067
Shower: Pure 0.183, RAG 0.106, LLM-Parameterized_Reference_Scoring 0.045

### Costs (per run of 195 scenarios)
| Architecture | Gemini | DeepSeek | GPT-OSS | Qwen |
|-------------|--------|----------|---------|------|
| Pure Prompting | ~$0.80 | ~$0.10 | ~$0.02 | ~$0.02 |
| RAG-Enhanced | ~$1.28 | ~$0.09 | ~$0.03 | ~$0.03 |
| LLM-Parameterized_Reference_Scoring | ~$0.28 | ~$0.01 | ~$0.01 | ~$0.01 |

API Calls per run: Pure=585, RAG=585, LLM-Parameterized_Reference_Scoring=195

### Failure Rates
- Gemini 3.5 Flash: 0% across all architectures
- DeepSeek V4 Flash: 0% across all architectures
- GPT-OSS 20B: 0% Pure/RAG, 12.8% extraction failures on LLM-Parameterized_Reference_Scoring (recovered by multi-run averaging, 0% scenario failure after matching)
- Qwen 3.5 9B: 0% across all architectures

### Sensitivity Analysis (Gemini 3.5 Flash)
Architecture ordering preserved across all 9 weight perturbations (tau range 0.901-0.945 for LLM-Parameterized_Reference_Scoring, 0.374-0.463 for RAG, 0.180-0.323 for Pure).

### RAG Ablation Key Findings (subset of 12 scenarios)
- Nearest-neighbor baseline: tau=0.000 (random level)
- descriptions_no_scores_ranks worst across all models (tau as low as -0.079 for Gemini)
- retrieval_k=1 often beats k=3 control
- Alternate embedding (paraphrase-MiniLM-L3-v2) helps Appliance (tau=0.733 Gemini)
- exemplars_no_hidden_params: similar to control overall but improves on some models

## Changes to Make (in order)

### 1. Sections Renumbering
Subsections 3.4 (currently Token Usage) → becomes 3.5. New subsection 3.4 (RAG Ablation) inserted before it. Both labels in text and references.

### 2. Abstract (line 37)
Replace: `\textit{[Quantitative claims in this paragraph are BLOCKED...]}` with 2 sentences using the pooled numbers. Use stop-slop.

### 3. Section 2.1 — Scenario justification (line 138)
Replace PLACEHOLDER NOTE with:
"The 195 test / 90 RAG split provides a 2.17:1 test-to-RAG ratio sufficient for retrieval coverage; HVAC is overrepresented (70 test + 35 RAG) due to its higher parameter dimensionality (R-value, SEER, age, occupancy, insulation tier)."

### 4. Section 2.4 — Architecture Implementations (last paragraph, line 571)
Remove the `\textit{[BLOCKED: update model descriptions...]}` block.

Replace the model descriptions with:
`The study evaluates four models spanning a range of capability, reasoning support, and cost: GPT-OSS-20B (reasoning, low effort), Qwen~3.5~9B (non-reasoning), DeepSeek~V4~Flash (hybrid reasoning), and Gemini~3.5~Flash (reasoning, minimal effort).`

Also fix N_RUNS from 10 to 5 wherever stated (lines 571, 629, etc.).

### 5. Section 3 — Results (lines 597-655)
Remove ALL `[NOTE: ...]` and `[CONFIRM AFTER RUNNING ...]` blocks. Replace with actual text.

**Subsection 3.1:** Write ~3 paragraphs covering:
- Headline: LLM-Parameterized_Reference_Scoring dominates (tau=0.902, Top-1=91.7%)
- RAG-Enhanced second (tau=0.339), Pure Prompting near-random (tau=0.095)
- Architecture ordering holds across all 4 models, all sensitivity scenarios
- 5-run mean, 195 scenarios

**Subsection 3.2:** Write ~2 paragraphs on criterion-level error:
- LLM-Parameterized_Reference_Scoring near-zero comfort/practicality MAE is structural
- RAG/Pure error concentrated on Energy Cost and Environmental
- Comfort MAE tiny for LLM-Parameterized_Reference_Scoring (0.010) since it uses same calculator

**Subsection 3.3:** Write ~2 paragraphs:
- LLM-Parameterized_Reference_Scoring excels on all three types (tau 0.817-0.944)
- Shower weakest due to GPM estimation limits
- RAG fails on HVAC (tau=0.107), best on Shower (tau=0.669)
- Pure near-random on HVAC/Appliance, best on Shower (tau=0.381)

**Subsection 3.4 (NEW):** Write ~2 paragraphs RAG Ablation:
- 12-scenario sample, 8 configurations, 5 models
- Key finding: nearest-neighbor offline baseline tau=0.000 (random)
- retrieval_k=1 and exemplars_no_hidden_params match or exceed k=3
- Alternate embedding helps Appliance specifically

**Subsection 3.5 (was 3.4):** Write ~2 paragraphs on efficiency/cost:
- LLM-Parameterized_Reference_Scoring cheapest AND best (1 call/scenario, ~$0.01-$0.28)
- Pure 2-6x cost of LLM-Parameterized_Reference_Scoring
- RAG most expensive (highest token count)
- Failure rates near-zero for all but GPT-OSS LLM-Parameterized_Reference_Scoring

### 6. Tables 5-9 — Replace Entirely

**Table 5 (Overall Performance)** — Replace current with pooled data table.
**Table 6 (Criterion-Level MAE)** — Replace with per-criterion pooled data.
**Table 7 (By Decision Type)** — Replace with per-decision-type pooled data.
**Table 8 (Cost/Efficiency)** — Replace with cost table + API calls + failure rates.
**Table 9 (NEW)** — RAG ablation summary.

### 7. Section 4 Discussion/Limitations
Replace `[CONFIRM AFTER RUNNING]` with actual findings:
- Remove "single run at T=0.3 without confidence intervals" line (line 629)
- State architecture ordering holds across all models
- Per-decision-type patterns confirmed
- RAG ablation discussion paragraph

### 8. Section 4.2 Future Work
Replace `[CONFIRM AFTER RUNNING]` with actual findings.
- Multi-model benchmark completed, LLM-Parameterized_Reference_Scoring advantage robust
- N=5 runs per model completed
- Per-decision-type variation discussed

### 9. Section 5 Conclusion
Remove `[NOTE: placeholder]` and `[CONFIRM AFTER RUNNING]`.
Fill in bracketed claims with pooled numbers.
Use stop-slop.

### 10. Table 4 caption
Remove "BLOCKED in this draft" note.

## Other Instructions

- Apply stop-slop to ALL new prose
- Keep existing mathematical notation, equation references, and citations intact
- Do not change section level or restructuring beyond the new 3.4 subsection
- Do not change Literature Review or Methodology (except 2.1/2.4)
