# XLSX Schema Map

This map covers the current XLSX files in the workspace and classifies each column as `text`, `numeric`, or `time-like` for a safe XLSX workflow.

## Rules

- Preserve all time-like values as text so Excel does not auto-coerce them.
- Keep blank placeholder columns blank in XLSX rather than filling them with guessed values.
- Treat identifier columns such as `scenario_id`, `rank`, and pair counts as numeric integers.
- Keep summary metrics as numeric, even when they are displayed with many decimals.

## File Map

| File | Suggested sheet name | Text columns | Numeric columns | Time-like columns | Notes |
| --- | --- | --- | --- | --- | --- |
| `Scenario Files/ApplianceScenarios.xlsx` | `ApplianceScenarios` | `Description`, `Location`, `Appliance`, `Housing Type` | `Utility Budget`, `Occupants`, `kwh/cycle`, `Appliance Age/Type` | `Baseline Time`, `Alternative 1`, `Alternative 2`, `Alternative 3` | Time fields must stay text. `Appliance Age/Type` is numeric in the current file despite the name. |
| `Scenario Files/ApplianceRAGScenarios.xlsx` | `ApplianceRAGScenarios` | `description`, `location`, `appliance`, `housing_type`, `alternative` | `scenario_id`, `utility_budget`, `appliance_age_type`, `occupants`, `kwh_per_cycle`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_cost`, `raw_emissions` | none | `alternative` contains time strings such as `2:00 AM`, so it should be stored as text. |
| `Scenario Files/HVACScenarios.xlsx` | `HVACScenarios` | `Question`, `Location`, `Insulation`, `Housing Type`, `Occupancy context` | `Square Footage`, `Household Size`, `Utility Budget`, `Outdoor Temp`, `House Age`, `R-Value`, `HVAC Age`, `SEER`, `Alternative 1`, `Alternative 2`, `Alternative 3` | none | Alternative values are temperature setpoints, not times. |
| `Scenario Files/HVACRagScenarios.xlsx` | `HVACRagScenarios` | `question`, `location`, `insulation`, `housing_type` | `scenario_id`, `square_footage`, `household_size`, `utility_budget`, `outdoor_temp`, `house_age`, `alternative`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_emissions` | none | `utility_budget` sometimes appears with a dollar sign and spacing in the source file, but the underlying field is numeric. |
| `Scenario Files/ShowerScenarios.xlsx` | `ShowerScenarios` | `Description`, `Location`, `Housing Type` | `Occupants`, `Tank Size`, `GPM`, `Utility Budget`, `Outdoor Temp`, `Water Heater Temp`, `Alternative 1`, `Alternative 2`, `Alternative 3` | none | All alternatives are numeric durations. |
| `Scenario Files/ShowerRAGScenarios.xlsx` | `ShowerRAGScenarios` | `description`, `location`, `housing_type` | `scenario_id`, `occupants`, `gpm`, `utility_budget`, `outdoor_temp`, `alternative`, `duration_min`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_water_gallons` | none | `alternative` and `duration_min` are numeric. |
| `Scenario Files/TestScenarios.xlsx` | `TestScenarios` | `Decision Type`, `Question`, `Location`, `Insulation`, `Housing Type` | `Square Footage`, `Household Size`, `Utility Budget`, `Outdoor Temp`, `House Age`, `Alternative 1`, `Alternative 2`, `Alternative 3` | none | `Appliance Age` and `Flow rate` are empty placeholders in the current file; preserve them as blank optional columns if they remain in the XLSX version. |
| `Ground Truth/ground_truth_appliance.xlsx` | `GroundTruth_Appliance` | `description`, `location`, `appliance`, `housing_type`, `alternative` | `scenario_id`, `utility_budget`, `appliance_age_type`, `occupants`, `kwh_per_cycle`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_cost`, `raw_emissions` | none | Same pattern as `ApplianceRAGScenarios.xlsx`; keep `alternative` as text because it is a time string. |
| `Ground Truth/ground_truth_hvac.xlsx` | `GroundTruth_HVAC` | `question`, `location`, `insulation`, `housing_type` | `scenario_id`, `square_footage`, `household_size`, `utility_budget`, `outdoor_temp`, `house_age`, `alternative`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_emissions` | none | `Appliance Age` and `Flow rate` are blank placeholders in the source and should stay blank if retained. |
| `Ground Truth/ground_truth_shower.xlsx` | `GroundTruth_Shower` | `description`, `location`, `housing_type` | `scenario_id`, `occupants`, `gpm`, `utility_budget`, `outdoor_temp`, `alternative`, `duration_min`, `energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `rank`, `raw_kwh`, `raw_cost`, `raw_water_gallons` | none | Same structure as `ShowerRAGScenarios.xlsx`. |
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

- Make copies of the original CSVs first, then convert the copies to XLSX.
- After conversion, update readers from `read_csv` to `read_excel` (or use the shared table reader).
- Keep scenario time strings and any schedule-like alternatives as text in Excel.