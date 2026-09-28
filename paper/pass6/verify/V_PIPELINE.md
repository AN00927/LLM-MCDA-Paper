# V_PIPELINE: independent verification of the pre-rerun pipeline work

Written 2026-09-26 by a Phase V verification agent. Scope: the nine pipeline checks in the
coordinator's brief (tie rounding, code-path consistency, A_H key override, baselines, pooled
rows, cost table, sentinels, numbers of record, gate), plus the coordinator's extra lead on the
hybrid ablation's `build_scenario`. No paid API call. The only git commands were read-only
(`git diff`, `git status --short`, `git diff --stat`, `git diff --quiet`). Scratch outputs are in
`C:\Users\Ahaan\AppData\Local\Temp\claude\c--Users-Ahaan-LLM-MCDA-Paper\68915bc4-ce9d-42b7-bc8b-bc1fac60115c\scratchpad\v_pipe\`
(`gate/`, `paths/`, `nor/`). Python: `.venv/Scripts/python.exe`. Several runs needed
`OPENBLAS_NUM_THREADS=1` because the machine was short of memory; one scipy import failed
transiently while another process was busy, and it worked on retry.

**Concurrent edits.** Other agents have uncommitted edits in the working tree to
`run_rag_ablation_experiments.py`, `run_prompt_ablation_experiments.py` and
`run_hybrid_ablation_experiments.py`: raw-log provenance and `collected_utc`. I edited
`run_hybrid_ablation_experiments.py` only inside `build_scenario`, well away from their hunks.
I did not touch the RAG-ablation file (see D5).

## Summary of results

| # | Check | Result |
|---|---|---|
| 1 | Pipeline gate on old data | **PASS.** Only the known Gemini A_H tie cells differ. |
| 2 | Tie rounding everywhere | **FAIL (known).** Two per-run architecture sites and three aggregate sites don't round. One more non-architecture gap: RAG-ablation Top-1 (D5, latent). |
| 3 | Code-path consistency and `question` | **PASS.** Four paths give identical scores on all 195 scenarios with the new calculators. Every path passes `question`. Two budget fallbacks hardened (applied). |
| 4 | A_H key-override risk | **Risk confirmed, never realised.** 0 extra keys in 6,240 raw responses, and 3,780/3,780 stored scenario-runs re-score identically under restricted keys. The fix is still needed before the rerun (D2). |
| 5 | Baselines read nothing from the question | **PASS.** Independent medians and modes match. 195/195 NN queries equal A_E's. |
| 6 | Pooled rows | **NOTE.** `RobustnessComparison` pools four models but nothing prints it. |
| 7 | Cost table prices | **FAIL.** Prices come from `model_config` label strings, and the architectures log no `usage.cost` or provider. |
| 8 | Sentinel discipline | **PASS.** |
| 9 | Numbers-of-record generator | **FAIL (coverage).** Only 37/122 rows can be regenerated. The 37 match 37/37. |

---

## 1. Pipeline gate on the current (old) data: PASS

**Command.** I copied `pipeline_gate.py` and `gate_checks.py` to scratch `gate/`, repointed
`PROJECT_ROOT` at the repo (outputs go to scratch; nothing in `Analysis/rerun_prep/pipeline/` was
overwritten), copied the committed `before.csv`, then ran:
```
python pipeline_gate.py after ; python pipeline_gate.py diff ; python gate_checks.py
```

**Result:**
- G1: 66/68
- G2: 33/36
- G3: 48/48
- G4: 5/5

The only failures are the five known cells: Gemini overall tau, Gemini HVAC tau, and
`AH_tau_gemini`, `AH_tau_inclusive_gemini`, `AH_tau_gemini_HVAC`. In each, 0.923 becomes 0.920 and
HVAC 0.977 becomes 0.968. The cause is the tie rule on HVAC test scenario 5, where alternatives 74
and 80 tie exactly at 0.7775.

My `after.csv` (1,236 rows) equals the committed `Analysis/rerun_prep/pipeline/after.csv` value for
value, with 0 differences. I re-ran the gate after my two edits (Section 3) and it again matched
the committed `after.csv` exactly (see "Gate after edits" at the end).

**The 18 AH rows of NUMBERS_OF_RECORD that G2 doesn't check,** checked by hand against the gate
output:
- **Unchanged:** `AH_gptoss_success_weighted_{tau,top1}_text` (0.790 / 84.7), `AH_failures_total`
  (120), `AH_gptoss_failures_HVAC` (117), `AH_gptoss_failed_all_runs` (1: 194 scenarios per run
  after recovery).
- **Moves by the same tie effect:** `AH_tau_range_L*` becomes 0.880–0.920.
- **Move by approved changes:**
  - `AH_table_best/worst_dtau_vs_FD`: 0.310 becomes 0.293 (0.296 without the tie effect), and
    0.266 becomes 0.253. This is the fixed-default change.
  - `AH_dtau_vs_FD_*_not_in_paper`: DeepSeek becomes 0.270 and GPT-OSS 0.313.
  - `AH_gptoss_recovery_tau`: 0.897 becomes 0.904. This is D2's recovery correction.

No other difference.

## 2. Tie rounding: every place that ranks by a weighted sum

`sentinel_utils.apply_mavt_ranking` (L343-404) rounds each weighted sum to `MAVT_ROUND_DECIMALS`
= 10 (L23, L377), then sorts on `(ws, *TIE_BREAK_PRIORITY scores)`, descending and stable.

| Location | What it ranks | Same rule? |
|---|---|---|
| `Ground Truth Calculators/{HVAC,Appliance,Shower}GroundTruthCalculator.py` (L679 / L616 / L518) and `Analysis/rerun_prep/calc_new/*` (L764 / L659 / L521) | Reference ranks | **Yes**: they call `sentinel_utils.apply_mavt_ranking` |
| `Architectures/Direct_LLM_Scoring.py` L513 (per-run ranks; import L69) | A_D per-run ranks, which the metrics use | **Yes**: it imports the shared function, so new A_D runs are already rounded |
| `Architectures/Direct_LLM_Scoring.py` L819-830 | Five-run aggregate `*_results.xlsx` | **No** (unrounded `ws`; `sort_values` at L828-829) |
| `Architectures/Example-Guided_LLM_Scoring.py` L658-700, local `apply_mavt_ranking`, sum at L669-674, sort at L686-688, called at L762 | **A_E per-run ranks** | **No** |
| `Architectures/Example-Guided_LLM_Scoring.py` L1096-1107 | Aggregate workbook | **No** |
| `Architectures/LLM-Parameterized_Reference_Scoring.py` L721-761, local `apply_mavt_ranking`, sum at L729-735, sort at L744-749, called at L919 (and L800/L830/L900 on sentinel paths) | **A_H per-run ranks** | **No** |
| `Architectures/LLM-Parameterized_Reference_Scoring.py` L1314-1325 | Aggregate workbook | **No** |
| `evaluate_architecture_metrics.py` L108-133 `_rank_with_deterministic_tiebreak` (used by `recompute_arch_ranks` L758-790 and imported by `validation/SensitivityAnalysis.py` L30, L218-221) | Imputed and weight-vector re-ranking | **Yes** (L121) |
| `run_baseline_models.py` L93-107, L391-401; FD via `apply_mavt_ranking` L265 | FD, random and uniform baselines | **Yes** |
| `evaluate_parameter_extraction.py` L142-159 | Counterfactual Top-1 | **Yes** (shared function) |
| `experiments/run_hybrid_ablation_experiments.py` L782-783, L1096, L1113 | All arms and the reference | **Yes** (shared function) |
| `experiments/run_prompt_ablation_experiments.py` L552 (pred) and reference `rank` column L612-619; Top-1 from ranks L646-647 | Prompt-ablation tau and Top-1 | **Yes** |
| `experiments/run_position_bias_control.py` | Drives A_D `run_scenario`, so it uses the shared function | **Yes** |
| `experiments/run_rag_ablation_experiments.py` L718-721, L818-821 (ranks, used for tau) | RAG-ablation tau | **Yes** |
| `experiments/run_rag_ablation_experiments.py` **L867** (`gt_top1` = sort by `mavt_score`) and **L869** (`pred_order` = sort by unrounded `weighted_score`) | RAG-ablation **Top-1 / Top-2** | **No**: raw-sum sort, input order on ties, no `TIE_BREAK_PRIORITY`. Latent: on the shipped `rag_ablation_results.xlsx`, rank-based Top-1 equals the stored Top-1 in 2,610/2,610 scenario rows. See D5. |
| `experiments/run_rag_ablation_experiments.py` L673-684 `rank_from_scores` | Unused (superseded) | n/a |
| `paper_pipeline/compute_tie_rates.py` L96-114 | Tie **detection** (diagnostic), `round(.,9)` and `EPS = 1e-9` | Compatible (detection only) |
| `paper_pipeline/compute_regret.py` L79-88 | Uses the stored `gt_rank` / `arch_rank` | Yes |
| `paper_pipeline/competitive_baselines.py` L114-121; `compute_dispersion_diagnostics.py` L188-210 | **Single-criterion** argmax, ties by first occurrence | Different by design (a single criterion, not a weighted sum). NOTE |
| `calculate_per_run_metrics.py`, `evaluate_baseline_metrics.py`, `significance_testing.py` | Consume stored ranks | n/a |
| `emit_per_model_pvalues.py` L66, `test_mechanics.py` L177, `rag_ablation` L1076 | argsort of p-values (Holm), not alternatives | n/a |

**Architecture lines needing the rounding (don't edit; for the lead):**
- **Per-run (MATERIAL, they produce the ranks the metrics use):**
  - `Example-Guided_LLM_Scoring.py` **L674**: `valid_pairs.append((idx, weighted_sum))`. The sort
    key is L686, the sort L688.
  - `LLM-Parameterized_Reference_Scoring.py` **L735**: same. The sort key is L747, the sort L749.
  - Minimal diff for each (plus `MAVT_ROUND_DECIMALS` added to the `from sentinel_utils import (...)`
    block, A_E L39-49 and A_H L43-51):
    ```diff
    -        valid_pairs.append((idx, weighted_sum))
    +        valid_pairs.append((idx, round(weighted_sum, MAVT_ROUND_DECIMALS)))
    ```
- **Aggregate workbooks (MINOR; no pipeline script reads them any more; they now use per-run files
  everywhere):**
  - `Direct_LLM_Scoring.py` L819-824 (sort L828-829)
  - `Example-Guided_LLM_Scoring.py` L1096-1101 (sort L1105-1106)
  - `LLM-Parameterized_Reference_Scoring.py` L1314-1319 (sort L1323-1324)
  - Minimal diff for each (plus the import in Direct, L65-75):
    ```diff
    -            )
    +            ).round(MAVT_ROUND_DECIMALS)
                 avg.loc[valid_idx, "weighted_score"] = ws
    ```

  A_D's per-run path needs nothing.

## 3. Consistency across code paths

**Same installed calculators, not copies.** Every path loads `Ground Truth Calculators/*.py`:
- A_H (`_load_calculator_class`, L60-91)
- hybrid ablation (`_load_calculator`, L222-236)
- `evaluate_parameter_extraction.py` (L44-60)
- `run_baseline_models.py`: a `sys.path` import. I confirmed with `inspect.getfile` that it
  resolves to `Ground Truth Calculators/`. The only other copies on disk are under
  `Analysis/rerun_prep/{calc_new,hvac/shipped,appliance/shipped}`, which are not on any path.

`sync_rag_ground_truth_scores.py` runs no calculator. It copies the scores in
`Ground Truth/ground_truth_*.xlsx` into the RAG sheets, so `question` doesn't apply to it. The
prompt and RAG ablations use stored reference ranks and no calculator.

**Fields.** The new calculators read these scenario keys:
- HVAC: `question`, `hvac_mode` (optional override), `outdoor_temp`, `r_value`, `seer`,
  `hvac_age`, `household_size`, `square_footage`, `housing_type`, `occupancy_context`,
  `utility_budget`, `alternatives`, plus defaulted `ceiling_height`, `electricity_rate`,
  `maintenance_level`.
- Appliance: `location` (mapped to the utility by `_utility_for_location`; there is no `city`
  field), `appliance`, `kwh_per_cycle`, `baseline_time`, `household_size`, `housing_type`,
  `utility_budget`, `alternative_1..3`.
- Shower: `gpm`, `tank_size`, `water_heater_temp`, `outdoor_temp`, `household_size`,
  `utility_budget`, `alternative_1..3`.

**Every path passes `question`:**
- reference batch
- A_H (full Test row)
- hybrid `build_scenario` L712
- `evaluate_parameter_extraction._build_ground_truth_scenario` L215
- `run_baseline_models.build_scenario_from_test` L161

Every Appliance path passes `location`. No path passes `hvac_mode`, so the question decides the
mode everywhere, and no path builds a calculator scenario without `question`.

**Test by actual scoring** (`paths/compare_paths.py`). With the NEW calculators (`calc_new`
patched in) and true hidden parameters, I scored all 195 Test scenarios four ways:
1. the reference batch-style dict from the master row (with its `int()` casts and occupancy
   normalisation);
2. A_H's real `score_with_ground_truth` on the full Test row;
3. hybrid `build_scenario` + `score_scenario`;
4. `evaluate_parameter_extraction` `_build_ground_truth_scenario`.

**Result:** 195/195 give identical criterion scores (1e-10) on every path, with no errors. The HVAC
mode read from the Test question equals the mode read from the master question in 70/70 (37 cool,
33 heat).

The paths agree for these reasons:
- The Test and master questions are the same string, because the hybrid and epe paths match on
  question + location.
- The masters' `r_value`, `seer`, `hvac_age`, `household_size`, `square_footage`,
  `utility_budget` and `outdoor_temp` are all integers, so the reference's `int()` casts lose
  nothing.
- The banded Test fields (`insulation`, `house_age`, `appliance_age`, `flow_rate`) that A_H
  carries in are not read by any calculator's scoring.

The DM arm and the FD baseline also run cleanly through the new calculators on all 195 scenarios:
0 errors and 0 sentinels (`paths/baselines_newcalc.py`).

**Extra lead (b): `utility_budget` fallback.** The hybrid (L720, old) and
`evaluate_parameter_extraction` (3 sites, old L225/L231/L243) used
`float(gt_row.get("utility_budget", 0) or 0)`. All three new calculators skip the budget penalty
when the budget is 0 or less:
- HVAC `calc_new` L673
- Appliance L532
- Shower L444 and L248

So a missing budget would have silently scored the option with no penalty, which is a neutral
default. No row is affected: 0 missing or zero budgets in the three masters and in the Test sheet.
**Fixed (applied), behaviour-neutral on current data:**

`Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`:
```diff
-        "utility_budget": float(gt_row.get("utility_budget", 0) or 0),
+        # A missing budget must fail loudly: 0 would silently switch the
+        # calculators' budget penalty off (they skip it when budget <= 0).
+        "utility_budget": _required_float(gt_row, "utility_budget"),
     }
 ...
         base.update({"outdoor_temp": float(gt_row["outdoor_temp"])})
+    # Only the hidden parameters of this decision type may be overridden; any
+    # other key (question, location, hvac_mode, ...) comes from the sheet.
+    allowed = set(HIDDEN_PARAMS[decision_type]["numeric"]) | set(HIDDEN_PARAMS[decision_type]["categorical"])
+    unexpected = set(params) - allowed
+    if unexpected:
+        raise ValueError(f"{decision_type}: unexpected parameter keys {sorted(unexpected)}")
     base.update(params)
     return base
+
+
+def _required_float(row: pd.Series, key: str) -> float:
+    value = _to_float(row.get(key))
+    if pd.isna(value):
+        raise ValueError(f"master row has no numeric {key!r}: {row.get(key)!r}")
+    return value
```

`Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py`: a new
`_required_float` helper (L73-79, same body and docstring as above), and all three
`"utility_budget": float(gt_row.get("utility_budget", 0) or 0)` became
`"utility_budget": _required_float(gt_row, "utility_budget")` (now L231, L237, L249).

**Extra lead (c): hybrid `base.update(params)`.** It was already restricted in practice, because
every `params` source is built from `HIDDEN_PARAMS` only:
- `extracted_params` L788-802
- `true_params` L805-811
- `compute_defaults` L680-698
- the order arms (through `extracted_params`)

The added guard makes that explicit. After both edits I re-ran the checks and nothing moved:
- 195/195 identical in `compare_paths.py`;
- 3,780/3,780 identical in `rescore_stored.py`;
- DM and FD with 0 errors;
- the gate re-run matched the committed `after.csv`.

## 4. A_H key-override risk

**Merge site.** `Architectures/LLM-Parameterized_Reference_Scoring.py` **L652**:
`gt_scenario = {**scenario, **extracted_result['parameters']}`. Only `alternatives` and
`alternative_1..3` are re-imposed afterwards (L653-655). Any other key the model returns inside
`parameters` would override the Test row's value: `question` (and with it the HVAC mode),
`hvac_mode` (which the new HVAC calculator treats as an explicit override, `calc_new` L220-227),
`location` (and with it the Appliance utility and tariff), `outdoor_temp`, `utility_budget`,
`household_size`, `square_footage`, `housing_type`, and `electricity_rate`, `ceiling_height`,
`maintenance_level` (which the calculator otherwise defaults).

**What the prompt requests.** `UNIFIED_EXTRACTION_PROMPT` L250-297, enforced as required keys at
L577-582:
- HVAC: `r_value`, `seer`, `hvac_age`, `occupancy_context`
- Appliance: `appliance`, `kwh_per_cycle`, `baseline_time`
- Shower: `gpm`, `tank_size`, `water_heater_temp`

Nothing checks the absence of other keys. `_validate_numeric_params` (L195-216) range-checks only
the requested numeric keys.

**Historical data.**
- The main-benchmark A_H runs have no raw response log. The per-run xlsx keep only the
  `extracted_*` columns for the requested keys, so extra keys would be invisible there.
- The only raw A_H extraction responses are the order-reversal logs,
  `Output Files*/hybrid_order_reversal/AH_extraction_order_*_raw.jsonl`: 8 files × 195 per model.
  I parsed every response with A_H's own parsing rule. **Extra keys inside `parameters`:
  DeepSeek 0/1,560, Gemini 0/1,560, GPT-OSS 0/1,560, Qwen 0/1,560. Extra top-level keys: 0.**
- Indirect check on the main runs (`paths/rescore_stored.py`). I re-scored every stored A_H
  scenario-run from its stored `extracted_*` values through the key-restricted hybrid path with the
  shipped calculators. Result: DeepSeek 974/974, Gemini 975/975, GPT-OSS 858/858 and Qwen 973/973
  identical to the stored criterion scores; 1 / 0 / 117 / 2 failed scenario-runs skipped. So no
  unrequested key ever changed a stored A_H score.

**Proposed minimal diff (not applied; architecture file):**
```diff
@@ module level, after the prompt (e.g. after L297)
+# The only keys an extraction may set; everything else comes from the scenario sheet.
+EXTRACTION_PARAM_KEYS = {
+    'HVAC': ('r_value', 'seer', 'hvac_age', 'occupancy_context'),
+    'Appliance': ('appliance', 'kwh_per_cycle', 'baseline_time'),
+    'Shower': ('gpm', 'tank_size', 'water_heater_temp'),
+}
@@ L577-582 (optional, keeps one source of truth)
-            if decision_type == 'HVAC':
-                required_params = ['r_value', 'seer', 'hvac_age', 'occupancy_context']
-            elif decision_type == 'Appliance':
-                required_params = ['appliance', 'kwh_per_cycle', 'baseline_time']
-            elif decision_type == 'Shower':
-                required_params = ['gpm', 'tank_size', 'water_heater_temp']
+            required_params = list(EXTRACTION_PARAM_KEYS[decision_type])
@@ L652
-    gt_scenario = {**scenario, **extracted_result['parameters']}
+    allowed = EXTRACTION_PARAM_KEYS[extracted_result['decision_type']]
+    params = {k: v for k, v in extracted_result['parameters'].items() if k in allowed}
+    gt_scenario = {**scenario, **params}
```

`decision_type` has already been checked against the sheet's type (L566-574), so the lookup can't
fail. This matches the coordinator's draft key sets exactly.

Alternative: treat an extra key as `FAILED_EXTRACTION_INVALID_PARAMETERS`. That is stricter, but
it would turn a harmless extra key into a sentinel. Given 0/6,240 historically, either choice has
no effect on the old data; the filter is the minimal one.

## 5. Baselines read nothing from the question

I read `Miscellaneous Scripts/core-automation/run_baseline_models.py` end to end.
- **FD** (`build_scenario_from_test` L154-227):
  - The question is copied into the scenario only, for the HVAC calculator's own mode reading.
  - Appliance type = `retrieval_set_appliance_mode()` (L140-150) = `compute_defaults()`, which
    gives `dryer`. kWh = `APPLIANCE_DEFAULT_KWH_PER_CYCLE['dryer']` = 2.10.
  - Occupancy, baseline time, GPM, tank and setpoint are plain constants (L62, L69, L75-77).
- **NN** (L350-388): the Test row is passed as-is.
- **Regex:**
  - L117/L119/L126 normalise alternative labels;
  - L193 takes the first number of the `appliance_age` band (a homeowner field, not the question).
- **`.lower()`:** L123 (alternative) and L224/L374/L413/L450 (blank-alternative checks).
- There is no `in question`, no keyword parser, and no read of `row['question']` other than the
  pass-throughs L161, L269, L315, L382, L424, L457.

**PASS.**

**Dataset-median rows and values.** `compute_defaults` (hybrid L673-698) takes the master rows
that no Test row matches (`retrieval_set_rows`, L625-670) and asserts they equal the RAG sheets
on location, household size, budget and housing type.

I recomputed independently:
- numeric medians straight from `HVACRagScenarios.xlsx` / `ApplianceRAGScenarios.xlsx` /
  `ShowerRAGScenarios.xlsx`, deduplicated by `scenario_id`;
- the categorical modes by joining each RAG scenario to its master row on
  question + location + household size + budget + housing type.

The join matched 35/35, 35/35 and 20/20.

| Parameter | Independent | `compute_defaults()` |
|---|---|---|
| R-value / SEER / HVAC age | 16.0 / 13.0 / 16.0 | same |
| occupancy (raw label) | `standard` 14/35 (next: `unoccupied_8hr` 6) | `standard` |
| kWh/cycle | 1.2 | 1.2 |
| appliance | `dryer` 13/35 (washing_machine 11, dishwasher 11) | `dryer` |
| baseline time (normalised) | `9:00 AM` 6/35 (next: 10:00 AM 4, 2:00 PM 4) | `9:00 AM` |
| GPM / tank / setpoint | 2.25 / 45.0 / 120.0 | same |

No mode is tied. Under the calculator's occupancy mapping, occupied_all_day is 18/35, so the mode
doesn't depend on the mapping. **PASS.**

**NN query parity.** For each of the 195 Test rows I built A_E's query
(`read_table_clean` with A_E's `keep_str_cols`, then `format_embedding_text(row.to_dict())`) and
the NN's query (`{**row.to_dict(), ...}` as in L364-371). They are equal in 195/195. **PASS.**

Scenario-data typos I came across (`6pm` / `8am` in `ApplianceScenarios.xlsx` rows 98-99) are
already rows 33-34 of `SCENARIO_FIXES.md`. I added nothing.

## 6. Pooled rows

`paper_pipeline/generate_paper_results_numbers.py` has three cross-model aggregates:
- **`RobustnessComparison`** (L386-409): `MethodA` and `Imputed` are the mean over all four
  models' runs per architecture. Values: A_D 0.0927/0.0944, A_E 0.2743/0.2740, A_H 0.8996/0.8709
  (tau); A_H MAE 0.0540/0.0605; A_H Top-1 91.3/89.3.
  - I searched `paper_draft_v2.tex` and `supplementary.tex` for each value at 3 and 4 dp and as
    percentages. Every hit is a coincidence: plot coordinates, bootstrap CIs, S L856 weight
    vectors, main L789 Δ, S L1337 separation. **The paper doesn't print them.**
  - The supplement's `tab:imputed_comparison` (S L1384-1406) is per model and comes from
    `generate_imputed_robustness_tables.py`, which also writes a four-model `pooled` sheet (L352-375)
    and prints "pooled tau". Also unprinted.
- **`IncrementalContribution` LLM rows** (L232-258): the model is picked by the mean of the three
  per-type values, not by Overall. This is the known "best label" issue; it is per model, not
  pooled.
- **`analyze_benchmark_failures.py` L148:** `tab:failure_modes_bymode` sums counts across models.
  The supplement prints the per-model `tab:failure_modes` instead (S L716). Main
  `tab:failure_arch_model` (L891-907) has a "Total" column summing counts across models, but the
  per-model cells sit next to it. These are counts, not metrics.

**NOTE:** nothing pooled is printed. Suggestion (not applied; outside my fix scope because it
changes shipped CSV categories): drop `RobustnessComparison` and the imputed `pooled` sheet, or
make them per model.

## 7. Cost table (`Table8_cost_per_run`): FAIL

**Code path.** `generate_paper_results_numbers.py` L108-164:
- tokens: the mean over runs of `total_tokens_input` / `total_tokens_output` from each
  architecture's `*_results_diagnostics_run_*.json`;
- prices: `_parse_prices(spec["label"])` (L129-133), a regex on the **label string** in
  `model_config.MODEL_SPECS`.

The labels are hand-typed and have already drifted:
- the `deepseek` label is V4.1's $0.14/$0.42 while the ID is `deepseek-v4-flash-0731`
  (handoff: $0.021/$0.32);
- GPT-OSS was relabelled for `:floor`.

The gate's G4-info row shows these label edits already re-price the OLD tokens.

**Raw logs.** None of the three architectures logs a cost, a serving provider or a generation id:
- The `query_openrouter` payloads (Direct L180ff, A_E L205ff, A_H L319-326) request no usage
  accounting.
- They read only `usage.prompt_tokens`, `completion_tokens`, `total_tokens` and
  `completion_tokens_details.reasoning_tokens` (Direct L214-231, A_E L240-259, A_H L359-378).
- `RAW_LOG.record` (A_H L489-501) stores the prompt, response, tokens and latency only.
- The shipped main-benchmark runs have no raw log at all, only diagnostics JSON with token totals.

Another agent's uncommitted edits add `_response_meta` (usage, provider, id, finish_reason) to the
RAG and prompt ablations and an `api_diag` pass-through to the hybrid order arm. The comment there
says "once the architecture logs them", so the architectures are still missing it.

**Proposed fix:**
1. In each architecture's `query_openrouter`, add `"usage": {"include": True}` to the payload and
   return `data.get("usage")` (full, including `cost`), `data.get("provider")`, `data.get("id")`
   and `data.get("model")`.
2. Record them in `RAW_LOG.record` and sum `usage.cost` into the diagnostics JSON
   (`total_cost_usd`).
3. In `generate_paper_results_numbers.py`, price Table 8 from the summed `total_cost_usd`. Fall
   back to label prices only for runs without it, and mark those rows `priced_from_label`.

Items 1-2 touch the architecture files, so they are for the lead and need the author's go-ahead.
Item 3 is small but only meaningful once 1-2 land; not applied.

## 8. Sentinel discipline in the changed scripts: PASS

- **Hybrid:**
  - `extracted_params` returns None on a sentinel or missing value (L788-802);
  - `scenario_metrics` returns None if either side has a sentinel (L766-770);
  - `_sentinel_failed_sids` drops failed scenario-runs from every mean.
- **Significance script:** pairs only non-failed run means.
- **`run_baseline_models`:** a calculator exception gives 1928 on every alternative;
  `apply_mavt_ranking` excludes sentinel alternatives.
- **NN prediction:** a missing exemplar value becomes SENTINEL and is ranked out.
- **`evaluate_parameter_extraction`:** failed scenario-runs are flagged (L256-267) and dropped.
  Counterfactual exceptions are recorded with `error` and excluded from P(change | error)
  (L578-579).
- **`compute_regret` and `compute_tie_rates`:** go through `cprm.filter_failed_scenarios`.
- **`generate_paper_results_numbers`:** its recovery reuses the per-run scorer.

No 1928 reaches an average or a ranking.

Two NOTEs, outside the changed scripts:
- `calc_new` HVAC `normalize_occupancy_context` (L380-405) maps any unrecognised label, and None,
  to `occupied_all_day`. An LLM label like `occupied_evening` is silently read as all-day instead
  of surfacing as a sentinel. Calculator scope; flag to the calculator verifier.
- `compute_defaults` returns `""` for an all-blank categorical and NaN for an all-blank numeric.
  Neither can fire on current data.

## 9. Numbers-of-record generator: FAIL (coverage)

**Command:**
`python paper_pipeline/build_numbers_of_record.py --output-dir <scratch>/nor`. This is read-only
on `paper/pass5/NUMBERS_OF_RECORD.csv`.

**Result.** 37/122 rows regenerated, and 37/37 match the value on record. I diffed the output
against `paper/pass5/NUMBERS_OF_RECORD.csv`. Note that `AH_tau_gemini` regenerates 0.923 because
it reads the stored ranks.

**85 rows it can't produce, by owning script:**
- `run_hybrid_ablation_experiments.py` (34):
  - `PROV_extracted_{tau,top1,mae}_*`
  - `PROV_extracted_tau_*_{HVAC,Appliance,Shower}`
  - `PROV_median_*`
  - `PROV_gptoss_194of195` (a Set B quantity that no longer exists)
  - `MEDIAN_tau_text`, `MEDIAN_top1_text`, `MEDIAN_tau_{HVAC,Appliance,Shower}`
- `Analysis/pass5/d2_reproduce_ah_numbers.py` (35). Handoff Section 3E says never run it for new
  outputs.
  - Section C: `EFFECT_range_text`, `EFFECT_like_for_like_*` (5).
  - Sections C/D: `EFFECT_like_for_like_*_{type}` (12).
  - Section E: `AH_gptoss_recovery_tau` (1).
  - Unlabelled (17):
    - `AH_tau_inclusive_*` and `AH_top1_inclusive_*` (8)
    - `AH_gptoss_success_weighted_{tau,top1}_text`
    - `AH_table_{best,worst}_dtau_vs_FD`
    - `AH_dtau_vs_FD_{deepseek,gptoss}_not_in_paper`
    - `AH_gptoss_failures_HVAC`, `AH_gptoss_failed_all_runs`
    - `MEDIAN_tau_gptoss_same_scenarios`
- `test_hybrid_ablation_significance.py` (12): `SIG_cliff_{kendall_tau,top1,mae}_*`.
- `evaluate_baseline_metrics.py` (4): `FD_tau_{overall,HVAC,Appliance,Shower}`.

**Proposed fix (not applied; more than a small fix).** Extend `build_numbers_of_record.py` to
read the outputs the rerun will produce:
- `hybrid_ablation_summary.xlsx`: `summary`, `summary_by_type` and `like_for_like` sheets, with the
  `extracted` arm, never `extracted_per_run`;
- `hybrid_ablation_pairwise_tests.xlsx`;
- `Output Files/Baselines/baseline_metrics.csv`;
- `per_run_metrics_all.csv`, for the inclusive and failure counts;
- `numbers_master.csv` `GPTOSS_recovery`.

Every piece of arithmetic already exists in `pipeline_gate.py` (`arm_aggregate`, the
DM/FD like-for-like blocks), which reproduced all of these rows on the old data. Retire the `PROV_*`
Set B rows.

---

## Discrepancies

| id | severity | description | evidence | proposed fix | applied? |
|---|---|---|---|---|---|
| D1 | MATERIAL | A_E and A_H per-run rankings break exact MAVT ties by float noise; the reference uses the rounded rule | `Example-Guided_LLM_Scoring.py:674` (key L686, sort L688); `LLM-Parameterized_Reference_Scoring.py:735` (key L747, sort L749). Pipeline report 9.1: 5/975 Gemini A_H, 12/965 Gemini A_E scenario-runs affected on old data | `round(weighted_sum, MAVT_ROUND_DECIMALS)` at both append sites, plus the import | No (architecture) |
| D2 | MATERIAL | A_H merges extracted params over the scenario without restricting keys, so `question`, `hvac_mode`, `location` etc. could be overridden | `LLM-Parameterized_Reference_Scoring.py:652`; required keys L577-582. Never realised: 0/6,240 raw responses; 3,780/3,780 stored scenario-runs re-score identically | Filter to `EXTRACTION_PARAM_KEYS[decision_type]` (diff in Section 4) | No (architecture) |
| D3 | MATERIAL | Cost table priced from hand-typed `model_config` label strings; architectures log no `usage.cost`, provider or generation id | `generate_paper_results_numbers.py:129-164`; A_H `:319-326`, `:359-378`, `:489-501`; the DeepSeek label is V4.1's price for the 0731 ID | Request usage accounting, log usage, cost and provider per call, sum cost in diagnostics, price Table 8 from it (Section 7) | No (architecture and author) |
| D4 | MATERIAL (process) | `build_numbers_of_record.py` regenerates only 37/122 rows; 35 of the rest are owned by an `Analysis/pass5` script the handoff forbids running | scratch `nor/numbers_of_record_regenerated.csv`; generator docstring L8-17 | Extend it to the hybrid, significance and baseline outputs (Section 9) | No |
| D5 | MINOR | RAG-ablation Top-1 / Top-2 sort raw sums with no tie-break, inconsistent with its own tau (which uses tie-broken ranks) | `run_rag_ablation_experiments.py:867`, `:869`; 0/2,610 rows differ on shipped data | `gt_top1 = min(common, key=lambda a: gt_by_alt[a]["rank"])`; `pred_order = sorted(ranked_common, key=lambda a: pred_by_alt[a]["rank"])` | No: another agent has uncommitted edits in this file |
| D6 | MINOR | Aggregate workbooks rank on unrounded sums | `Direct_LLM_Scoring.py:819-829`, `Example-Guided_LLM_Scoring.py:1096-1106`, `LLM-Parameterized_Reference_Scoring.py:1314-1324`; no pipeline script reads them | `.round(MAVT_ROUND_DECIMALS)` on `ws` | No (architecture) |
| D7 | MINOR | Missing `utility_budget` silently became 0, which turns the budget penalty off | old hybrid L720; old epe L225/L231/L243; calc_new HVAC L673, Appliance L532, Shower L444; 0 affected rows | Raise on a missing budget; hybrid also guards `params` keys | **Yes** (hybrid L720-747, epe L73-79, L231, L237, L249) |
| D8 | NOTE | `RobustnessComparison` and the imputed `pooled` sheet average across four models | `generate_paper_results_numbers.py:386-409`; `generate_imputed_robustness_tables.py:352-375`; not printed in the paper | Drop, or make per model | No |
| D9 | NOTE | `calc_new` HVAC maps unknown or None occupancy labels to `occupied_all_day` (a neutral default) | `calc_new/HVACGroundTruthCalculator.py:387-405` | Return None and raise, so the scenario gets the sentinel; for the calculator verifier | No (calculator) |
| D10 | NOTE | Single-criterion baselines break ties by first occurrence, not `TIE_BREAK_PRIORITY` | `competitive_baselines.py:114-121`, `compute_dispersion_diagnostics.py:188-210` | Leave (a single criterion, not a weighted sum), or document | No |
| D11 | NOTE | The known tie cells move on old data: Gemini A_H tau 0.923 → 0.920 (HVAC 0.977 → 0.968); `AH_tau_range` becomes 0.880–0.920 | gate G1/G2 | Moot after the rerun | n/a |

## Files changed by this agent

- `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py` (`build_scenario` and new
  `_required_float`)
- `Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py` (new `_required_float`;
  3 budget sites)
- `paper/pass6/verify/V_PIPELINE.md` (this file)

Scratch only: `gate/` (gate copies and outputs), `paths/compare_paths.py`, `paths/rescore_stored.py`,
`paths/baselines_newcalc.py`, `paths/path_compare.csv`, `nor/numbers_of_record_regenerated.csv`.

Git: read-only commands only (`git diff`, `git diff --stat`, `git diff --quiet`,
`git status --short`). No commit, checkout, stash or reset.
