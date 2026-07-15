# Comprehensive Revision Plan — Statistical Metrics & Analysis

**Status:** ACTIVE — user has approved
**Last updated:** 2026-07-15

---

## Table of Contents

1. [Metric Suite Decisions](#1-metric-suite-decisions)
2. [Statistical Rigor: Pseudo-Replication Fix](#2-statistical-rigore-pseudo-replication-fix)
3. [Statistical Methods to Implement](#3-statistical-methods-to-implement)
4. [RAG Ablation Expansion](#4-rag-ablation-expansion)
5. [Manuscript Table & Figure Layouts](#5-manuscript-table--figure-layouts)
6. [Manuscript Text Changes](#6-manuscript-text-changes)
7. [Code Changes](#7-code-changes)
8. [Bug Fixes & Cleanup](#8-bug-fixes--cleanup)
9. [Constraints & Non-Goals](#9-constraints--non-goals)
10. [Execution Order](#10-execution-order)

---

## 1. Metric Suite Decisions

### Primary metrics (main text, §4)
| Metric | Role | Justification |
|--------|------|---------------|
| **MAE** | Score-level error magnitude | Core evidence of extraction fidelity |
| **RMSE** | Score-level error concentration | Penalizes tail errors; ratio with MAE reveals error distribution shape |
| **RMSE/MAE ratio** | Error concentration index | New explicit column. AH highest (2.06) — reflects concentrated tail from GPM estimation cases |
| **Top-1** | Decision correctness | Binary: is the recommended alternative genuinely the best? |
| **Kendall's τ** | Rank correlation | Ordinal agreement between predicted and true rankings |

### Dropped metrics
| Metric | Reason |
|--------|--------|
| **Spearman's ρ** | 0 rank ties out of 2,339 scenarios (deterministic tiebreaker guarantees unique ranks). Max \|ρ − τ\ = 0.059. Redundant with τ and provides no additional information. Remove from all code output, tables, figures, and prose. |
| **Top-2** | Move to appendix ONLY. No interpretive discussion in main text. Retained in appendix figures for completeness. |

### Design rules
- **Never report pooled numbers.** Every metric is reported per model (Gemini, DeepSeek, GPT-OSS, Qwen). Pooled means are computed internally but not displayed as primary results.
- **RMSE/MAE ratio** is always shown alongside MAE and RMSE in the same table.

---

## 2. Statistical Rigor: Pseudo-Replication Fix

### The problem
Current pipeline in `generate_numbers_master.py` pools 4 models × 5 runs = 20 values per cell as if they were independent observations. They are not: the 5 runs share the same model (non-independent), and the 4 models share the same scenarios (non-independent). This inflates effective sample size and makes p-values artificially small.

### Solution: Two-tier approach

**Tier 1 (Primary): Linear mixed-effects model**
- Model: `metric ~ architecture + (1|model) + (1|scenario)`
- Fixed effect: architecture (D, E, H)
- Random intercepts: model (4 levels), scenario (195 levels)
- Accounts for both sources of non-independence
- Implementation: `statsmodels.MixedLM` or `pingouin.mixed_anova`
- Report: F-statistic, p-value, variance decomposition (ICC)

**Tier 2 (Robustness): Per-model Wilcoxon + Stouffer combination**
- For each model independently: Wilcoxon signed-rank test on per-scenario τ (or MAE) between adjacent architecture pairs
- Combine p-values across 4 models using Stouffer's Z method
- This is fully non-parametric and makes no distributional assumptions
- Report: per-model p-values + combined Stouffer Z and combined p

### Current Wilcoxon claim in paper (line 1028)
> "Pairwise differences between architectures are significant under Wilcoxon signed-rank testing (p < 0.001 for each adjacent pair), paired on per-scenario Kendall's τ, pooled across all models and runs."

**This has NO corresponding code anywhere in the repository.** Must be implemented from scratch.

---

## 3. Statistical Methods to Implement

### 3A. Intraclass Correlation Coefficient (ICC)
**Purpose:** Decompose total variance into between-model, between-scenario, and residual components.

**Implementation:**
```python
# ICC(2,1) — two-way random, single measures, consistency
# From per_run_metrics_all.csv: 60 rows (4 models × 3 architectures × 5 runs)
# For each architecture separately:
#   ICC = σ²_model / (σ²_model + σ²_scenario + σ²_residual)
# Using pingouin: pingoin.icc(data, targets='scenario', raters='model', 
#                             fid=False, two_way_mixed=True)
```

**Report in paper:** ICC table per architecture per metric. Shows how much of the metric variation comes from model choice vs. scenario difficulty vs. residual noise.

### 3B. Bootstrap Confidence Intervals
**Purpose:** Provide CIs that don't rely on normality assumptions.

**Implementation:**
- 10,000 bootstrap resamples
- Resample scenarios with replacement, keep all models within each scenario
- Compute metric for each resample
- Report: point estimate, 95% BCa CI (bias-corrected and accelerated)
- Per metric, per architecture, per model

**Report in paper:** Table with point estimate ± 95% BCa CI for each primary metric.

### 3C. Mixed-Model Significance Tests
**Purpose:** Test whether architecture differences are statistically significant after accounting for pseudo-replication.

**Implementation:**
- For each pairwise comparison (D vs E, E vs H):
  - Dependent variable: per-scenario metric difference
  - Model: `difference ~ 1 + (1|model)` (intercept-only with random effect for model)
  - Test: whether intercept ≠ 0
  - Also test with `(1|model) + (1|scenario)` when feasible
- Report: coefficient, SE, t-statistic, p-value

### 3D. Per-Model Wilcoxon + Stouffer
**Purpose:** Non-parametric robustness check for mixed-model results.

**Implementation:**
```python
# For each model m and each adjacent pair (D vs E, E vs H):
#   stat, p = scipy.stats.wilcoxon(metric_D_m, metric_E_m, alternative='two-sided')
# Stouffer combination across 4 models:
#   Z = sum(z_i) / sqrt(k)  where z_i = norm.ppf(1 - p_i/2)
#   p_combined = 2 * (1 - norm.cdf(abs(Z)))
```

**Report in paper:** Table with per-model Wilcoxon p-values + Stouffer combined p.

### 3E. Effect Sizes
**Purpose:** Quantify magnitude of architecture differences, not just significance.

**Cohen's d** (continuous metrics: MAE, RMSE):
```
d = (mean_metric_AH - mean_metric_AD) / pooled_sd
```

**Rank-biserial correlation** (for Wilcoxon):
```
r = Z_stat / sqrt(N)
```

**Cliff's delta** (non-parametric effect size):
```
δ = (# A > B - # A < B) / (n_A × n_B)
```
Interpretation: |δ| < 0.147 negligible, < 0.33 small, < 0.474 medium, else large.

**Report in paper:** Effect sizes alongside p-values in significance tables.

---

## 4. RAG Ablation Expansion

### Current state
- 12 scenarios in subset (underpowered — noted as TODO at paper line 1111-1112)
- `top1_accuracy` and `top2_accuracy` columns show N/A in xlsx (code bug fixed at `RunRAGAblations.py` lines 1103-1104 but xlsx not regenerated)

### Target state
- **35 scenarios** (not 25) — guarantees every stratum is covered
- Stratum coverage analysis:
  - HVAC: up to 11 strata (insulation × system_type × house_age combinations)
  - Appliance: up to 9 strata
  - Shower: 4 strata (low_flow/standard × tank_size bands)
  - 35 scenarios = min_allocation ≥ non_empty_strata_count for every type

### Code changes in `CreateRepresentativeSample.py`
- Modify `stratified_sample_by_features()` (line 126) to enforce `min_allocation >= len(non_empty_strata)` per decision type before proportional fill
- Ensure total is exactly 35

### Code changes in `RunRAGAblations.py`
- Add Friedman test across 6 configurations (non-parametric omnibus)
- Add post-hoc Wilcoxon signed-rank with Holm-Bonferroni correction
- Add Cliff's delta for pairwise configuration comparisons
- Add bootstrap CIs for each configuration's τ
- All statistical tests must have explanatory comments in code

### Ablation metrics to report
- Kendall's τ (existing)
- Top-1 accuracy (currently N/A — must regenerate xlsx)
- 95% bootstrap CI for τ per configuration
- Friedman χ² and p-value
- Post-hoc pairwise Cliff's delta + adjusted p-values

### Stale file cleanup
After regenerating: delete old `rag_ablation_results.md`, old xlsx outputs, old standalone scenario files that were derived from the old 12-scenario subset.

---

## 5. Manuscript Table & Figure Layouts

All layouts approved by user. Top-2 columns appear ONLY in appendix tables, never in main text.

### Table 5: Overall Metrics by Model (MODIFY existing, paper ~L1002-1022)
Replace the three separate figures (ranking accuracy by model, MAE by model, RMSE by model) with a SINGLE consolidated table. Remove the three individual figures.

```
Table 5. Overall ranking and score-error metrics by model (5-run mean, 195 scenarios)
┌─────────────────────────────────────────────────────────────────────────────┐
│         │         τ        │  Top-1 (%)  │  MAE      │  RMSE     │ RMSE/  │
│         │                  │             │           │           │  MAE   │
├─────────────────────────────────────────────────────────────────────────────┤
│         │ AD     AE     AH │ AD   AE  AH │ AD   AE AH│ AD   AE AH│ AD AE AH│
│ Gemini  │ .176  .388  .925│36.7 54.4 93.3│.207 .131 .052│.283 .167 .107│1.37 1.28 2.06│
│ DeepSeek│ .145  .341  .897│40.0 49.7 92.3│.219 .138 .061│.295 .179 .107│1.35 1.30 1.75│
│ GPT-OSS │ .051  .329  .897│33.8 52.3 92.3│.222 .143 .049│.303 .180 .105│1.37 1.26 2.14│
│ Qwen    │ .019  .264  .880│31.8 50.3 90.3│.227 .139 .043│.311 .183 .159│1.37 1.32 3.70│
│ Mean    │ .098  .331  .900│35.6 51.7 92.1│.219 .138 .051│.298 .177 .120│1.37 1.29 2.41│
└─────────────────────────────────────────────────────────────────────────────┘
```
- Bold best architecture per model per metric
- Remove Spearman's ρ column entirely
- Add RMSE/MAE ratio column (new)
- No per-model figures for individual metrics (folded into this one table)

### Table 6: Criterion-Level MAE (MODIFY existing, paper ~L1038-1059)
Keep existing table structure (4 criteria × 3 architectures). Change caption from "pooled across 4 models" to "by architecture" (since we are no longer pooling). Add per-model breakdown figure below.

```
Table 6. MAE per criterion by architecture (5-run mean, 195 scenarios)
Same structure as current Table (tab:item6), but caption updated.
No structural changes needed — this table is already correct.
```

### Table 7: Performance by Decision Type (MODIFY existing, paper ~L1074-1094)
Remove Top-2 columns from this table (appendix only). Keep τ and Top-1.

```
Table 7. Ranking accuracy by decision type (5-run mean, 195 scenarios)
┌──────────────────────────────────────────────────────────────┐
│        │     AD       │     AE       │     AH       │
│        │ τ    Top-1(%)│ τ    Top-1(%)│ τ    Top-1(%)│
├──────────────────────────────────────────────────────────────┤
│HVAC    │ .031  32.5   │ .107  33.6   │ .936  92.5   │
│Appliance│-.100  25.8  │ .282  53.8   │ .944  96.9   │
│Shower  │ .381  49.2   │ .669  70.4   │ .817  85.4   │
│Overall │ .095  35.4   │ .339  51.7   │ .902  91.7   │
└──────────────────────────────────────────────────────────────┘
```
- Top-2 columns REMOVED from main text
- This table shrinks from 9 data columns to 6

### Table 8: RAG Ablation (REPLACE existing, paper ~L1115-1137)
New expanded table for 35-scenario ablation with statistical tests.

```
Table 8. RAG ablation: Kendall's τ with 95% bootstrap CI (35 scenarios)
┌───────────────────────────────────────────────────────────┐
│ Configuration                 │ τ (95% CI)    │ Top-1(%) │
├───────────────────────────────────────────────────────────┤
│ Control (k=3, all-MiniLM-L6-v2)│ 0.XXX [.XX,.XX]│ XX.X    │
│ Nearest-neighbor (offline)     │ 0.XXX [.XX,.XX]│ XX.X    │
│ retrieval_k=1                  │ 0.XXX [.XX,.XX]│ XX.X    │
│ retrieval_k=5                  │ 0.XXX [.XX,.XX]│ XX.X    │
│ Alt. embedding (paraphrase-L3) │ 0.XXX [.XX,.XX]│ XX.X    │
│ exemplars_no_hidden_params     │ 0.XXX [.XX,.XX]│ XX.X    │
│ descriptions_no_scores_ranks   │ 0.XXX [.XX,.XX]│ XX.X    │
└───────────────────────────────────────────────────────────┘
Friedman χ²(6) = XX.X, p < 0.001
Post-hoc pairwise comparisons: see Appendix Table Xₐ.
```

### Appendix Table A1: Top-2 by Decision Type (NEW, appendix only)
Top-2 columns from current Table 7, moved here. No interpretive text — just the data.

```
Appendix Table A1. Top-2 accuracy by decision type (%)
Same as Table 7 but with Top-2 columns only, no discussion.
```

### Appendix Table A2: Significance Tests (NEW)
```
Appendix Table A2. Pairwise architecture comparisons
┌──────────────────────────────────────────────────────────────────────────┐
│                  │ Mixed Model        │ Wilcoxon (per-model)           │
│ Comparison       │ Coef  SE   p       │ Gemini  DeepSeek GPT-OSS Qwen │
│                  │                     │ + Stouffer combined p          │
├──────────────────────────────────────────────────────────────────────────┤
│ τ: AD vs AE      │                     │                               │
│ τ: AE vs AH      │                     │                               │
│ MAE: AD vs AE    │                     │                               │
│ MAE: AE vs AH    │                     │                               │
│ RMSE: AD vs AE   │                     │                               │
│ RMSE: AE vs AH   │                     │                               │
│ Top-1: AD vs AE  │                     │                               │
│ Top-1: AE vs AH  │                     │                               │
└──────────────────────────────────────────────────────────────────────────┘
Effect sizes (Cohen's d for continuous; rank-biserial for Wilcoxon) in adjacent column.
```

### Appendix Table A3: Bootstrap CIs (NEW)
```
Appendix Table A3. Bootstrap 95% BCa confidence intervals for primary metrics
┌─────────────────────────────────────────────────────┐
│ Metric │ Architecture │ Point Est │ 95% BCa CI      │
├─────────────────────────────────────────────────────┤
│ τ      │ AD           │           │                 │
│ τ      │ AE           │           │                 │
│ τ      │ AH           │           │                 │
│ MAE    │ AD           │           │                 │
│ ...    │ ...          │           │                 │
└─────────────────────────────────────────────────────┘
Per-model and pooled rows.
```

### Appendix Table A4: ICC Variance Decomposition (NEW)
```
Appendix Table A4. Intraclass correlation coefficients
┌──────────────────────────────────────────────────────────┐
│               │ τ                │ MAE              │
│ Architecture  │ σ²_mdl  σ²_sce  │ σ²_mdl  σ²_sce  │
├──────────────────────────────────────────────────────────┤
│ AD            │                   │                   │
│ AE            │                   │                   │
│ AH            │                   │                   │
└──────────────────────────────────────────────────────────┘
σ²_mdl = between-model variance fraction
σ²_sce = between-scenario variance fraction
1 - σ²_mdl - σ²_sce = residual
```

### Appendix Table A5: RAG Ablation Post-Hoc (NEW)
```
Appendix Table A5. RAG ablation: pairwise Cliff's δ with Holm-adjusted p-values
(6 configurations, 15 pairwise comparisons)
```

### Figures
- **Remove** the three separate per-model metric figures (ranking accuracy by model, MAE by model, RMSE by model) — replaced by consolidated Table 5
- **Keep** criterion-level MAE figure (fig:mae_criterion)
- **Keep** decision-type τ figure (fig:tau_decision)
- **Keep** RAG ablation figure (fig:rag_ablation) — update for 35 scenarios
- **Keep** all boxplot variance figures
- **Keep** cost table figure
- **No new figures** for statistical tests — reported in tables within appendix

---

## 6. Manuscript Text Changes

### §4.1 Overall Ranking Accuracy (paper ~L1024-1032)

**Line 1030 — RMSE/MAE sentence (Option B — rewrite):**
Current text claims "no large errors dominate." This conflicts with AH's RMSE/MAE ratio of 2.06 (highest of three), indicating concentrated tail errors from GPM-estimation cases.

**New text (draft):**
> The MAE and RMSE values quantify how closely each architecture's scores match the ground truth. AH achieves overall MAE of 0.051 on the 0–1 MAVT scale, meaning score predictions deviate from the true value by roughly 5% on average. Its RMSE of 0.105 yields an RMSE/MAE ratio of 2.06 — the highest among the three architectures — indicating that while average error is low, a small number of scenarios (primarily shower cases requiring GPM estimation) produce larger deviations that pull RMSE above twice the MAE. AD MAE of 0.219 means individual scores routinely miss by more than 0.2 points, and AE at 0.138 falls in between.

**Line 1028 — Wilcoxon claim:**
Must add code implementation AND expand text to describe the statistical method. Explain what Wilcoxon signed-rank tests, how it was applied (paired on per-scenario τ, per model), and how the p < 0.001 was computed (Stouffer combination across models).

**Line 1267 — Spearman reference in variance paragraph:**
Current: "Full per-metric distributions (MAE, RMSE, Top-1 accuracy, Spearman's ρ) appear in Appendix"
Change to: "Full per-metric distributions (MAE, RMSE, Top-1 accuracy) appear in Appendix"
Remove Spearman's ρ reference.

### New text to add (mixed throughout §4):
- Explain ICC variance decomposition when first referenced
- Explain bootstrap CI methodology when first referenced
- Explain mixed model when first referenced
- Explain effect sizes when first referenced
- Each statistical method gets a brief plain-language explanation in the text (1-2 sentences) alongside the formal statement

### Section 4.1 tension (flagged for author decision)
The current sentence "no large errors dominate" at line 1030 conflicts with the RMSE/MAE ratio of 2.06 for AH. Option B rewording above resolves this by acknowledging the tail while noting the errors are concentrated in specific cases.

---

## 7. Code Changes

### 7A. `CalculateMetrics.py` (Miscellaneous Scripts/)
**Path:** `/mnt/c/Users/Ahaan/LLM-MCDA Paper/Miscellaneous Scripts/CalculateMetrics.py`

| Change | Location | Detail |
|--------|----------|--------|
| Remove Spearman's ρ from `compute_ranking_metrics()` | Line 789-791, 808 | Delete `spearman_rho` computation and return key |
| Remove Top-2 from main output | Line 801-804, 810 | Move `top2_accuracy` to optional/appendix-only output |
| Add RMSE/MAE ratio | After line 808 | Compute and return `rmse_mae_ratio` |
| Remove Spearman references from print statements | Lines 1187, 1223 | Delete or replace with ratio output |
| Remove Top-2 from print statements | Lines 1190-1191, 1226-1227 | Delete |
| Update metric map | Line 1270-1271 | Remove `spearman_rho`, add `rmse_mae_ratio` |

### 7B. `generate_numbers_master.py`
**Path:** `/mnt/c/Users/Ahaan/LLM-MCDA Paper/generate_numbers_master.py`

| Change | Location | Detail |
|--------|----------|--------|
| Fix `ddof=0` → `ddof=1` | Lines 61, 81, 90, 110, 120, 188-190 | Population std → sample std |
| Remove Spearman from `metric_map_5` | Line 48 | Delete `"spearman_rho": "rho"` |
| Remove Top-2 from `metric_map_5` | Line 50 | Delete `"top2_accuracy": "Top-2"` |
| Remove Spearman/Top-2 from per-type maps | Lines 98, 141 | Delete corresponding entries |
| Add RMSE/MAE ratio to metric maps | After line 50 | Add `"rmse_mae_ratio": "RMSE/MAE"` |

### 7C. NEW: `compute_confidence_intervals.py`
**Path:** `/mnt/c/Users/Ahaan/LLM-MCDA Paper/Miscellaneous Scripts/compute_confidence_intervals.py`

- Read `per_run_metrics_all.csv`
- Bootstrap 10,000 resamples per metric per architecture per model
- Compute BCa 95% CI
- Output: table-ready xlsx with point estimate + CI bounds
- Statistical explanation in module docstring and inline comments

### 7D. NEW: `significance_testing.py`
**Path:** `/mnt/c/Users/Ahaan/LLM-MCDA Paper/Miscellaneous Scripts/significance_testing.py`

- Read `per_run_metrics_all.csv`
- Implement: mixed model (statsmodels MixedLM), per-model Wilcoxon, Stouffer combination, Cohen's d, rank-biserial r, Cliff's delta
- Output: table-ready results for Appendix Tables A2-A5
- Every statistical test has a docstring explaining what it tests, why, and how to interpret the result
- Output is plain text table + xlsx

### 7E. `CreateRepresentativeSample.py`
**Path:** `/mnt/c/Users/Ahaan/LLM-MCDA Paper/Miscellaneous Scripts/CreateRepresentativeSample.py`

| Change | Location | Detail |
|--------|----------|--------|
| Enforce min_allocation ≥ non_empty_strata_count | `stratified_sample_by_features()` line 126 | Before proportional fill, ensure every non-empty stratum gets at least 1 |
| Target 35 scenarios total | Same function | Adjust allocation logic |

### 7F. `RunRAGAblations.py`
**Path:** `/mnt/c/Users/Ahaan/LLM-MCDA Paper/Miscellaneous Scripts/RunRAGAblations.py`

| Change | Location | Detail |
|--------|----------|--------|
| Add Friedman test | New function | Across 6 configurations per metric |
| Add post-hoc Wilcoxon + Holm-Bonferroni | New function | Pairwise comparisons after significant Friedman |
| Add Cliff's delta | New function | Non-parametric effect size for each pair |
| Add bootstrap CI per configuration | New function | 10,000 resamples, BCa CI |
| Add statistical explanations | Throughout | Docstrings and inline comments for every test |

### 7G. `paper/per_run_metrics/per_run_metrics_all.csv`
- After code changes to CalculateMetrics, regenerate this file
- Remove `spearman_rho` column
- Keep `top2_accuracy` column (used by appendix tables)
- Add `rmse_mae_ratio` column

---

## 8. Bug Fixes & Cleanup

### Typo
- **Line 861:** `APPROPPRIATE CAPTION HERE` → proper caption text for the pipeline figure (leave as placeholder — user said don't fix placeholders we didn't discuss, BUT this is a typo in the placeholder itself, not a content placeholder. Fix the spelling: `APPROPRIATE`)

### ddof fix
- `generate_numbers_master.py`: All `ddof=0` → `ddof=1` (lines 61, 81, 90, 110, 120, 188-190)
- This changes all reported ± values in the paper — numbers must be recomputed

### Stale files
- Delete old `rag_ablation_results.md` (12-scenario results)
- Delete old standalone `*Scenarios.xlsx` RAG files (if rebuilt from consolidated)
- Delete old xlsx outputs from RunRAGAblations that have N/A bugs
- Regenerate `per_run_metrics_all.csv` after code changes

### Existing tables — MODIFY, not replace
- Table 6 (criterion MAE): caption update only
- Table 7 (by decision type): remove Top-2 columns
- Table 8 (RAG ablation): replace with expanded 35-scenario version
- Table 5 (overall): replace three figures with consolidated table
- All other existing tables: unchanged

---

## 9. Constraints & Non-Goals

### Hard constraints
- **Never edit Introduction, Literature Review, or initial Methodology** (up to MAVT framework design §2.2) without explicit user consultation
- **Never commit or push** without explicit user permission
- **Placeholders:** Do NOT fix `[PLACEHOLDER: INSERT...]`, `[EXPLAIN WQH]`, corrupted characters, or content placeholders. Only fix the APPROPPRIATE → APPROPRIATE typo.
- **Use /stop-slop skill** for all prose changes
- **Every statistical test gets:** (1) explanation in code comments, (2) explanation in paper text
- **All values per model** — never pool as primary result
- **Fit on page** — design tables to fit correctly in the two-column ACM format
- **Top-2 never in main text** — appendix only, no interpretive discussion

### Non-goals (not doing in this revision)
- Pipeline diagram (user explicitly said don't)
- Reducing shower interpolation text
- Modifying Introduction/Literature Review
- Creating new figures for statistical tests (tables only in appendix)
- Token/cost analysis tables (separate workstream, not part of this metrics revision)
- GPT-OSS per-run graphic (separate workstream)

---

## 10. Execution Order

### Phase 1: Code Infrastructure (no paper changes yet)
1. **Fix `ddof=0` → `ddof=1`** in `generate_numbers_master.py` — affects all ± values
2. **Remove Spearman's ρ** from `CalculateMetrics.py` (`compute_ranking_metrics`)
3. **Remove Top-2** from main output path in `CalculateMetrics.py` (keep in data for appendix)
4. **Add RMSE/MAE ratio** to `CalculateMetrics.py`
5. **Update `generate_numbers_master.py`** metric maps (remove ρ, remove Top-2 from main, add ratio)
6. **Regenerate `per_run_metrics_all.csv`** with updated metrics
7. **Fix `CreateRepresentativeSample.py`** stratum guarantee for 35 scenarios
8. **Re-run RAG ablation** with expanded 35-scenario subset (regenerate xlsx)

### Phase 2: Statistical Scripts (new files)
9. **Write `compute_confidence_intervals.py`** — bootstrap BCa CIs
10. **Write `significance_testing.py`** — mixed model, Wilcoxon, Stouffer, effect sizes, ICC
11. **Run both scripts** and verify output tables match expected structure

### Phase 3: RAG Ablation Enhancement
12. **Update `RunRAGAblations.py`** — add Friedman, post-hoc, Cliff's delta, bootstrap CI
13. **Run updated ablation** on 35-scenario subset
14. **Verify no N/A** in output xlsx (top1/top2 bug was code-fixed, xlsx stale)

### Phase 4: Manuscript Updates
15. **Replace three per-model metric figures** with consolidated Table 5
16. **Modify Table 7** — remove Top-2 columns
17. **Update Table 6 caption** — "pooled across 4 models" → "by architecture"
18. **Replace Table 8** — RAG ablation with 35-scenario results + statistical tests
19. **Fix Section 4.1 text** — RMSE/MAE sentence (Option B), Wilcoxon explanation
20. **Remove Spearman reference** from variance paragraph (line 1267)
21. **Add statistical method explanations** throughout §4
22. **Add Appendix Tables A1-A5** — Top-2, significance tests, bootstrap CIs, ICC, post-hoc
23. **Fix APPROPPRIATE typo** (line 861)

### Phase 5: Cleanup & Verification
24. **Delete stale files** — old ablation results, old xlsx outputs
25. **Verify all numbers** in paper match regenerated outputs
26. **Run linter/typecheck** if available
27. **Check page fit** — ensure all tables/appendix fit in ACM format
28. **Final review** — run /stop-slop on all new/modified prose

---

## Appendix: File Reference

| File | Purpose | Changes |
|------|---------|---------|
| `paper/paper_draft_working.tex` | Active manuscript (2160 lines) | Tables, figures, prose |
| `Miscellaneous Scripts/CalculateMetrics.py` | Core metric computation | Remove ρ, add ratio, adjust Top-2 |
| `generate_numbers_master.py` | Pooled table generation | ddof fix, metric map updates |
| `paper/per_run_metrics/per_run_metrics_all.csv` | 60-row per-run data | Regenerate after code changes |
| `paper_pipeline/calculate_per_run_metrics.py` | Per-run metric computation | May need regeneration |
| `Miscellaneous Scripts/CreateRepresentativeSample.py` | RAG sample selection | Stratum guarantee |
| `Miscellaneous Scripts/RunRAGAblations.py` | RAG ablation runner | Statistical tests, 35 scenarios |
| `Miscellaneous Scripts/compute_confidence_intervals.py` | NEW: bootstrap CIs | Create from scratch |
| `Miscellaneous Scripts/significance_testing.py` | NEW: significance tests | Create from scratch |
| `model_config.py` | 4 models × 5 runs structure | No changes |
| `Architectures/*.py` | Three architecture files | No changes |
| `paper/cas-refs.bib` | Bibliography | No changes (known bugs left alone) |
