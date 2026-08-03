# Metrics & Significance Calculation Pipeline

This document explains every calculation in the metrics and significance pipeline end-to-end: how raw scores become per-run metrics, how those metrics are pooled across runs and models, and how statistical significance is assessed.

---

## 1. Data Flow Overview

```
Raw per-run xlsx (3 architectures x 4 models x 5 runs = 60 files)
    |
    v
evaluate_architecture_metrics.py -- evaluates each architecture against ground truth
    |                    - matches scenarios by (question, location)
    |                    - computes MAE, RMSE, Kendall's tau, Top-1, Top-2
    |                    - outputs per-architecture metrics xlsx
    |
    v
calculate_per_run_metrics.py -- same metrics, but per individual run
    |                         - writes paper/per_run_metrics/per_run_metrics_{model}.csv
    |
    v
generate_paper_results_numbers.py -- pools per-run CSVs across all 4 models
    |                        - computes pooled means + stds (4 models x 5 runs = 20 values)
    |                        - computes per-model means, per-criterion breakdowns
    |                        - writes paper/numbers_master.csv
    |
    v
significance_testing.py -- statistical tests on per-scenario metrics
                          - ICC(2,1), Wilcoxon, Stouffer, Cliff's delta, bootstrap
                          - writes paper/per_run_metrics/significance_tests.xlsx
```

Each stage computes its own metrics from raw data rather than consuming pre-computed aggregates from the prior stage. The per-run CSV bridge is used only by generate_paper_results_numbers.py.

---

## 2. Sentinel Value (1928)

### Definition

A sentinel value of `1928` (int, float `1928.0`, or string `"1928"`) marks a failed/invalid score. Defined in `sentinel_utils.py`:

```python
SENTINEL_VALUE = 1928
SENTINEL_FLOAT = 1928.0
```

### Detection functions

| Function | File | What it does |
|----------|------|-------------|
| `is_sentinel(value)` | sentinel_utils.py | Coerces to float, checks `== 1928.0`. NaN returns False |
| `has_sentinel_scores(scores, criteria)` | sentinel_utils.py | Checks any criterion in dict is sentinel |
| `is_failed_row(row)` | evaluate_architecture_metrics.py | Checks if any score column in a row is sentinel |
| `_to_float_or_nan(val)` | evaluate_architecture_metrics.py | Returns NaN on any failure instead of sentinel |

### Handling approaches

There are two primary evaluation handling strategies, plus a standalone per-run imputed robustness check:

**Filtered mode (scenario-level exclusion — the primary method):**
- `filter_failed_scenarios()` groups by `arch_scenario_id`, checks if ANY alternative row has ANY criterion sentinel
- If so, ALL rows for that scenario are removed from metrics computation
- Used by: `evaluate_all()` filtered mode, `significance_testing.py`, `calculate_per_run_metrics.py`

**Method C (per-cell safe_mean):**
- `safe_mean(series)` in `generate_method_c_consensus.py`: requires >=3 non-NaN values out of 5 runs
- If fewer than 3 valid values, the cell stays NaN (row excluded from that criterion)
- Scores are averaged across runs BEFORE metrics computation

**Per-run imputed robustness check:**
- Standalone robustness analysis via `paper_pipeline/generate_imputed_robustness_tables.py`
- Imputes sentinels to 0.5 per run before MAVT ranking using building blocks `impute_failed_scores()` and `recompute_arch_ranks()`

---

## 3. Score Pipeline

### 3.1 Raw scores per architecture

Each architecture produces 4 criterion scores per alternative per scenario, on a 0-1 scale:

- `energy_cost`: dollar cost (lower is better)
- `environmental`: CO2 emissions or water volume (lower is better)
- `comfort`: thermal/time convenience (higher is better)
- `practicality`: adoptability (higher is better)

### 3.2 MAVT weighted sum

```python
s_j = 0.30 * energy_cost + 0.35 * environmental + 0.20 * comfort + 0.15 * practicality
```

Weights from `model_config.py.CRITERION_WEIGHTS`:

| Criterion | Weight |
|-----------|--------|
| Environmental | 0.35 |
| Energy Cost | 0.30 |
| Comfort | 0.20 |
| Practicality | 0.15 |

### 3.3 Tie-breaking

Ties broken by TIE_BREAK_PRIORITY: `["environmental", "energy_cost", "comfort", "practicality"]`

`_rank_with_deterministic_tiebreak()` sorts by `[weighted_score, tie_1, tie_2, tie_3, tie_4]` descending with mergesort for stable ordering. A UserWarning is emitted if any ties on weighted_score are detected.

### 3.4 Ground truth matching

Scenarios are matched by content-based key `(question, location)`, not by scenario_id. Disambiguation uses parameter pairs:
- HVAC: outdoor_temp match (+100)
- Appliance: appliance_age match (+100)
- Shower: outdoor_temp + gpm + household_size + utility_budget + housing_type

Each matching alternative adds +1. Best score wins. Warnings on ties or unmatched scenarios.

### 3.5 Alternative normalization

For matching, alternative values are normalized:
- **Appliance**: extract time pattern ("2:00 PM") with `extract_time_from_alt()`
- **HVAC**: handle "off_X" patterns, integer conversion
- **Shower**: integer/float duration

---

## 4. Per-Run Metrics — Functions

All functions below are in `evaluate_architecture_metrics.py` unless noted. They operate on a `merged_df` containing `arch_*` and `gt_*` columns.

### 4.1 `compute_criterion_metrics(merged_df)`

For each criterion `c in {energy_cost, environmental, comfort, practicality}`:

1. Extract `gt_{c}` and `arch_{c}` columns
2. Drop pairs where either is NaN
3. Compute:

   ```
   MAE_c = mean(|arch_i - gt_i|)
   RMSE_c = sqrt(mean((arch_i - gt_i)^2))
   ```

4. Accumulate `all_abs_errors` and `all_sq_errors` across all criteria
5. Overall:
   ```
   Overall MAE = nanmean(all_abs_errors)
   Overall RMSE = sqrt(nanmean(all_sq_errors))
   Overall RMSE/MAE = Overall RMSE / Overall MAE
   ```

### 4.2 `compute_ranking_metrics(merged_df)`

For each scenario (by `arch_scenario_id`):

1. Skip if < 2 alternatives or any rank is NaN
2. **Kendall's tau**: `scipy.stats.kendalltau(gt_rank, arch_rank)`. With n=3 alternatives, per-scenario tau can only be -1, -1/3, 1/3, or 1. If all ranks identical in either set, returns 1.0 if exact match else 0.0.
3. Final tau = mean of per-scenario taus (arithmetic mean over all valid scenarios)
4. **Top-1**: GT best (rank 1) == architecture best (rank 1), compared by normalized alternative string
5. **Top-2**: Two definitions exist:
   - `evaluate_architecture_metrics.py`: Intersection of GT top-2 set and architecture top-2 set is non-empty
   - `calculate_per_run_metrics.py`: GT top-1 is in architecture top-2 set

### 4.3 `compute_failure_rate(arch_df)`

Detects sentinel 1928 via `pd.to_numeric(errors="coerce")`. For LLM-Parameterized_Reference_Scoring, also breaks down by extraction vs calculation failures.

### 4.4 `_load_diagnostics_json(path, arch_name)`

Loads diagnostics JSON files next to run xlsx files. Two schemas:
- Direct/Example architectures: counters like `EXTRACTION_INVALID_JSON`, `FAILED_MISSING_SCORE`
- LLM-Parameterized_Reference_Scoring: additional `FAILED_EXTRACTION_*` and `FAILED_GROUND_TRUTH_*` counters

---

## 5. Per-Run-Then-Average Protocol (Method A)

This is the primary evaluation protocol.

1. For each (model, architecture) combination, there are 5 independent runs
2. Each run is evaluated independently through `compute_criterion_metrics()` and `compute_ranking_metrics()`
3. This produces 5 estimates per metric
4. Final metric = mean of 5 estimates ± sample std (ddof=1)

The std deviation quantifies run-to-run stability. Confidence intervals use t-distribution:
```
CI = mean ± t_0.975,4 * std / sqrt(5)
```

This is implemented in `calculate_per_run_metrics.py`, which:
- Discovers run files matching `{arch}_results_run_*.xlsx`
- Calls `filter_failed_scenarios()` to remove sentinel-containing scenarios
- Calls `compute_criterion_metrics()` + `compute_ranking_metrics_local()` (local variant with different Top-2)
- Records per-model metrics in `paper/per_run_metrics/per_run_metrics_{model_key}.{xlsx,csv}`

---

## 6. Alternative Aggregation Methods

### 6.1 Method C (mean-aggregate-then-evaluate)

In `generate_method_c_consensus.py`:

1. Load all 5 run xlsx files for an architecture
2. Coerce scores to numeric, set sentinel 1928 to NaN
3. Group by `(scenario_id, alternative)`, apply `safe_mean` (requires >=3 valid entries)
4. Recompute weighted scores and ranks
5. Compute metrics once on the consensus ranking
6. Compare to Method A: Method A tau vs Method C tau, with difference column

### 6.2 Per-run imputed robustness building blocks

In `evaluate_architecture_metrics.py`:
- `impute_failed_scores(df, impute_value=0.5)` replaces sentinel 1928 in `arch_*` columns with 0.5 (scale midpoint).
- `recompute_arch_ranks(df)` recomputes weighted scores and ranks after imputation.
- Used as building blocks by `paper_pipeline/generate_imputed_robustness_tables.py` for per-run imputed robustness checking.

---

## 7. Per-Criterion Breakdown

Each criterion (energy_cost, environmental, comfort, practicality) has its own MAE and RMSE computed independently.

In `generate_paper_results_numbers.py`, per-criterion MAEs are reported:

- **Pooled**: mean of 20 values (4 models x 5 runs) for that criterion x architecture
- **Best/worst model**: model with minimum/maximum mean overall_MAE per architecture

Table 6 in the paper: for each architecture, best model, worst model, and pooled (4-model) values for each criterion MAE.

---

## 8. Per-Decision-Type Breakdown

Metrics are computed separately for each decision type by filtering merged_df:

- HVAC: 70 scenarios
- Appliance: 65 scenarios
- Shower: 60 scenarios

`compute_criterion_metrics()` and `compute_ranking_metrics()` are called on each filtered subset.

In `generate_paper_results_numbers.py`, per-type metrics are:
- **Pooled**: mean across all 20 values per architecture x decision type for tau and Top-1
- **Best/worst**: model with max/min mean tau per architecture x decision type

---

## 9. Cross-Model Pooling (generate_paper_results_numbers.py)

`generate_paper_results_numbers.py` reads per-run CSVs from all 4 models and computes:

### Pooled overall (Table 5)
For each architecture, collects metric values from all 20 runs (4 models x 5 runs):
```python
pooled_mean = np.mean(vals)   # 20 values
pooled_sd   = np.std(vals, ddof=1)  # sample std
```

### Per-model means
For each architecture x model combination, mean and std of its 5 runs.

### Per-type arithmetic mean (for Incremental Contribution table)
For each run, averages tau across decision types:
```python
run_means = sub.groupby('run')[['kendall_tau','top1_accuracy']].mean()
```
Then aggregates those run-level means across all runs. This prevents HVAC's higher scenario count from dominating.

### GPT-OSS recovery breakdown
For GPT-OSS A_H, each of 5 runs' individual metrics are listed, plus pooled values.

---

## 10. Statistical Significance Tests

All in `significance_testing.py`. These tests operate on per-scenario metric vectors (195 values per architecture per model), NOT on aggregate values.

The pipeline:
1. For each model x architecture: load 5 runs, match to GT, filter failed scenarios
2. Compute per-scenario metrics: `kendall_tau`, `top1_accuracy`, `overall_mae`, `overall_rmse`, `overall_rmse_mae_ratio`
3. Average across 5 runs per scenario (mean of run-level metrics by scenario_id)
4. This produces one 195-element vector per architecture per model

### 10.1 ICC(2,1) — Intraclass Correlation Coefficient

**What it measures**: Proportion of total metric variance attributable to between-model differences.

**Data**: Per-run aggregate CSV (`per_run_metrics_all.csv`), filtered to "Overall" decision type.

**Formula**:
```
MS_model = variance of 4 model means (between-model)
MS_error = mean of 4 within-model variances (pooled within-model)
ICC = (MS_model - MS_error) / (MS_model + (k-1) * MS_error)  where k = 5 runs
sigma2_model = (MS_model - MS_error) / (MS_model + (k-1) * MS_error + MS_error)
sigma2_residual = MS_error / (MS_model + (k-1) * MS_error + MS_error)
```

**Results from paper**:
- MAE: ICC = 0.80-0.83 → model choice drives error
- Top-1: ICC = 0.08-0.27 → scenario difficulty drives accuracy (not model)

### 10.2 Mixed-Effects Model

**What it does**: Estimates average architecture-pair difference accounting for model-level variance.

For each architecture pair (A vs B) and each metric M:
```
d_ms = M_A(m,s) - M_B(m,s)  -- difference per model m, scenario s
Model: d_ms = mu + u_m + e_ms
  mu = fixed intercept (average difference)
  u_m ~ N(0, sigma2_u) -- random intercept per model
  e_ms ~ N(0, sigma2_e) -- residual
```

Fitted via `statsmodels.MixedLM` with REML. Fallback to normal approximation if singular.

### 10.3 Wilcoxon Signed-Rank Test

**Non-parametric** paired test — no normality assumption.

For each model individually, n = 195 paired observations (scenarios):

1. Compute differences d_i = metric_A(i) - metric_B(i)
2. Drop zero-differences
3. Rank absolute differences, assign signs
4. `T = min(sum positive ranks, sum negative ranks)`
5. Normal approximation:
   ```
   mu_T = n(n+1)/4
   sigma_T = sqrt(n(n+1)(2n+1)/24)
   z = (T - mu_T - 0.5*sign(mu_T-T)) / sigma_T  # continuity correction
   ```
6. Two-sided p-value from z
7. Holm-Bonferroni correction across 4 models

### 10.4 Stouffer Z Combination

Combines per-model Wilcoxon z-scores into one aggregate:

```
Z_combined = sum(z_i) / sqrt(k)  where k = number of models (4)
p_combined = 2 * (1 - Phi(|Z_combined|))  # two-sided
```

Non-finite z values excluded.

### 10.5 Effect Sizes

**Cohen's d** (paired):
```
d = mean(a - b) / std(a - b)
```

**Rank-biserial correlation**:
```
r = Z_Wilcoxon / sqrt(n)
```

**Cliff's delta**:
```
delta = (sum_i sum_j [I(a_i > b_j) - I(a_i < b_j)]) / (n_A * n_B)
```

Thresholds: <0.147 negligible, <0.33 small, <0.474 medium, >=0.474 large.

### 10.6 Bootstrap Confidence Intervals

10,000 resamples with replacement (195 scenarios each). BCa (bias-corrected and accelerated) intervals for each metric per architecture per model. No overlap between A_H and other architectures on any metric.

---

## 11. Failure Analysis Pipeline

In `analyze_benchmark_failures.py`:

1. Scans every row of every per-run xlsx for 1928 sentinel
2. Checks each of 4 score columns via `float(val) == 1928`
3. Records scenario_id, decision_type, architecture, model, run, failed criteria
4. Merges with diagnostics JSON files for failure-mode breakdown
5. Merges with `TestScenarios.xlsx` for parameter clustering

**LaTeX tables produced**:
- Failure counts per architecture x model (summed across 5 runs)
- Failure mode breakdown (invalid JSON, missing score, out-of-bounds, etc.)
- Failure by decision type (HVAC/Appliance/Shower)
- Parameter clustering: top-5 parameter combos per type (e.g., HVAC + outdoor_temp > 95F + Poor insulation)

---

## 12. RAG Ablation Tests

In `run_rag_ablation_experiments.py`, using a 35-scenario subset:

### 12.1 Configurations tested
Seven configurations against a `k=3` control:
- Retrieval k=1, k=5
- Alternate embedding model
- Hidden params excluded from exemplars
- Scores excluded from exemplars
- Random exemplars (instead of similarity-ranked)
- Nearest-neighbor offline baseline (copy scores without LLM)

### 12.2 Friedman test (non-parametric)
Tests whether configurations differ significantly:
```
Q = 12/(n*k*(k+1)) * sum(R_j^2) - 3*n*(k+1)
```
where R_j = sum of ranks for configuration j, n = 35 scenarios, k = 7 configurations
p-value via chi-square with k-1 df.

### 12.3 Post-hoc Wilcoxon (Holm-corrected)
Pairwise comparisons between configurations. Results: retrieval k variants, embedding, and hidden-params form a statistically indistinguishable cluster (p_Holm > 0.97). Removing scores or using random retrieval significantly degrades performance (p_Holm < 0.003).

### 12.4 Bootstrap CIs
10,000 resamples, 2.5th and 97.5th percentiles for each configuration's tau and MAE.

---

## References

| File | Role |
|------|------|
| `model_config.py` | Constants: CRITERION_WEIGHTS, TIE_BREAK_PRIORITY, MODEL_SPECS |
| `sentinel_utils.py` | is_sentinel, has_sentinel_scores, apply_mavt_ranking |
| `evaluate_architecture_metrics.py` | Central metrics engine: matching, filtering, all metrics |
| `calculate_per_run_metrics.py` | Per-run wrapper (Method A) |
| `generate_paper_results_numbers.py` | Cross-model pooling, numbers_master.csv |
| `generate_method_c_consensus.py` | Method C comparison (safe_mean, consensus) |
| `analyze_benchmark_failures.py` | Failure detection, LaTeX tables |
| `significance_testing.py` | ICC, Wilcoxon, Stouffer, Cliff's delta, mixed model |
| `run_rag_ablation_experiments.py` | RAG ablation: Friedman, bootstrap, post-hoc |
