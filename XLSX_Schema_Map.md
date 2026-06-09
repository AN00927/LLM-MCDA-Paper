# XLSX Schema Map

This map covers the current XLSX files in the workspace and classifies each column as `text`, `numeric`, or `time-like` for a safe XLSX workflow. **All column names use the canonical snake_case form established by the normalization pass.**

## Rules

- Preserve all time-like values as text so Excel does not auto-coerce them.
- Keep blank placeholder columns blank in XLSX rather than filling them with guessed values.
- Treat identifier columns such as `scenario_id`, `rank`, and pair counts as numeric integers.
- Keep summary metrics as numeric, even when they are displayed with many decimals.

## File Map

| File | Suggested sheet name | Text columns | Numeric columns | Time-like columns | Notes |
| --- | --- | --- | --- | --- | --- |
| `Scenario Files/ApplianceScenarios.xlsx` | `ApplianceScenarios` | `question`, `location`, `appliance`, `housing_type` | `utility_budget`, `household_size`, `kwh_per_cycle`, `appliance_age` | `baseline_time`, `alternative_1`, `alternative_2`, `alternative_3` | Time fields must stay text. `appliance_age` is numeric. |
| `Scenario Files/ApplianceRAGScenarios.xlsx` | `ApplianceRAGScenarios` | `question`, `location`, `appliance`, `housing_type`, `alternative` | `scenario_id`, `utility_budget`, `appliance_age`, `household_size`, `kwh_per_cycle`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_cost`, `raw_emissions` | none | `alternative` contains time strings such as `2:00 AM`, so it should be stored as text. `appliance_age` is stored as raw years (numeric) here but is rendered as a band label (`appliance_age_to_band_label`, 3-yr ≤12 then 5-yr) in the RAG embedding and exemplar display, so it matches the banded `appliance_age` on the TestScenarios query side. |
| `Scenario Files/HVACScenarios.xlsx` | `HVACScenarios` | `question`, `location`, `insulation`, `housing_type`, `occupancy_context` | `square_footage`, `household_size`, `utility_budget`, `outdoor_temp`, `house_age`, `r_value`, `hvac_age`, `seer`, `alternative_1`, `alternative_2`, `alternative_3` | none | Alternative values are temperature setpoints, not times. |
| `Scenario Files/HVACRagScenarios.xlsx` | `HVACRagScenarios` | `question`, `location`, `insulation`, `housing_type` | `scenario_id`, `square_footage`, `household_size`, `utility_budget`, `outdoor_temp`, `house_age`, `alternative`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_emissions` | none | `utility_budget` sometimes appears with a dollar sign and spacing in the source file, but the underlying field is numeric. |
| `Scenario Files/ShowerScenarios.xlsx` | `ShowerScenarios` | `question`, `location`, `housing_type` | `household_size`, `tank_size`, `gpm`, `utility_budget`, `outdoor_temp`, `water_heater_temp`, `alternative_1`, `alternative_2`, `alternative_3` | none | All alternatives are numeric durations. |
| `Scenario Files/ShowerRAGScenarios.xlsx` | `ShowerRAGScenarios` | `question`, `location`, `housing_type` | `scenario_id`, `household_size`, `gpm`, `utility_budget`, `outdoor_temp`, `alternative`, `duration_min`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_water_gallons` | none | `alternative` and `duration_min` are numeric. |
| `Scenario Files/TestScenarios.xlsx` | `TestScenarios` | `decision_type`, `question`, `location`, `insulation`, `housing_type`, `house_age`, `appliance_age`, `flow_rate`, `alternative_1`, `alternative_2`, `alternative_3` | `square_footage`, `household_size`, `utility_budget`, `outdoor_temp` | none | Architecture-facing (LLM-input) sheet: stores **generalized band labels**, not raw numbers. `house_age` = building-age range label (5-yr bands ≤20, then 10-yr); `appliance_age` = appliance-age range label (3-yr bands ≤12: `1-3/4-6/7-9/10-12 years`, then 5-yr bands); `flow_rate` = `low_flow/standard/high_flow`. Each label column is populated only for its decision type and blank otherwise. No `hvac_age`/`gpm` columns. All three label helpers live in `sentinel_utils` (single source of truth, also used by BuildRAG embedding). Alternatives are text (HVAC setpoints incl. `Off`, appliance times, shower durations). |
| `Ground Truth/ground_truth_appliance.xlsx` | `GroundTruth_Appliance` | `question`, `location`, `appliance`, `housing_type`, `alternative` | `scenario_id`, `utility_budget`, `appliance_age`, `household_size`, `kwh_per_cycle`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_cost`, `raw_emissions` | none | Same pattern as `ApplianceRAGScenarios.xlsx`; keep `alternative` as text because it is a time string. |
| `Ground Truth/ground_truth_hvac.xlsx` | `GroundTruth_HVAC` | `question`, `location`, `insulation`, `housing_type` | `scenario_id`, `square_footage`, `household_size`, `utility_budget`, `outdoor_temp`, `house_age`, `alternative`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_emissions` | none | `appliance_age` and `flow_rate` are blank placeholders in the source and should stay blank if retained. |
| `Ground Truth/ground_truth_shower.xlsx` | `GroundTruth_Shower` | `question`, `location`, `housing_type` | `scenario_id`, `household_size`, `gpm`, `utility_budget`, `outdoor_temp`, `alternative`, `duration_min`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_water_gallons` | none | Same structure as `ShowerRAGScenarios.xlsx`. |
| `Scoring Logic and Documentation/method/entropy_weights.xlsx` | `EntropyWeights` | `criterion` | `subjective_weight`, `entropy_weight_overall`, `entropy_weight_hvac`, `entropy_weight_appliance`, `entropy_weight_shower`, `abs_diff_overall`, `abs_diff_hvac`, `abs_diff_appliance`, `abs_diff_shower` | none | Pure numeric summary table with one text key column. |
| `Scoring Logic and Documentation/method/implied_weights_summary.xlsx` | `ImpliedWeightsSummary` | `scope`, `criterion` | `n_pairs`, `implied_weight`, `subjective_weight`, `diff`, `pairwise_sign_acc`, `r2_pairwise` | none | `scope` is a grouping label, not a numeric field. |
| `Scoring Logic and Documentation/method/merec_weights_summary.xlsx` | `MERECWeightsSummary` | `scope`, `criterion` | `n_scenarios`, `merec_weight`, `weight_std_dev`, `subjective_weight`, `diff`, `zero_var_scenarios` | none | Pure numeric summary table with one text grouping column. |

## Workbook Plan

If you want a clean XLSX migration with minimal cross-file coupling, use one workbook per family plus one workbook for method summaries:

1. `appliance_workbook.xlsx` for `ApplianceScenarios`, `ApplianceRAGScenarios`, and `GroundTruth_Appliance`.
2. `hvac_workbook.xlsx` for `HVACScenarios`, `HVACRagScenarios`, `TestScenarios`, and `GroundTruth_HVAC`.
3. `shower_workbook.xlsx` for `ShowerScenarios`, `ShowerRAGScenarios`, and `GroundTruth_Shower`.
4. `method_weights_workbook.xlsx` for `EntropyWeights`, `ImpliedWeightsSummary`, and `MERECWeightsSummary`.

## Conversion Notes

- Make copies of the original files first.
- After conversion, update readers from `read_csv` to `read_excel` (or use the shared table reader).
- Keep scenario time strings and any schedule-like alternatives as text in Excel.
